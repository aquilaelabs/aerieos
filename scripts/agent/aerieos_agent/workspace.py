"""The workspace (docs/nodes.md section 6): a job's source on disk, its artifacts, and the bundle of bb."""
import contextlib
import glob
import hashlib
import json
import os
import re
import shutil
import tarfile
import threading
import time
from . import release
from .base import (BUNDLE_LIST, BUNDLE_SIG, LIST_MOST, REFUSED, REFUSED_MOST, ROOT_BUNDLE_DIR, ROOT_TOOLS, TOOLS_DIR, TOOLS_SIG,
                   fs_holds, hello_again, log)
from .stores import dir_bytes, load_state, tc_root


# How many of root's bundles are kept at most, whatever still runs from
# them: each is about 4 MB, and a session that outlives this many updates of
# its controller is one in a month of them.
BUNDLES_MOST = 40
# A terminal's hooks are written a moment before its session is entered.
BUNDLE_SLACK_S = 300
# One bundle is put in place at a time. A job's thread and the loop may each
# fetch one, and each download lands in a file of its own, is checked there,
# and only then takes the tar's one name under this lock, which is held until
# it is unpacked: the tar that was checked is the tar unpacked, whatever
# another thread was sent meanwhile.
_UNPACK = threading.Lock()


def sessions_from(proc="/proc", root=None):
    """What still runs from root's bundles: (when the oldest running session
    was entered, in epoch seconds, or None with none running; the bundle
    folders some process names on its command line). A session's coding
    agent runs its hooks from the bundle that was current when the session
    was entered, by its path, for as long as the session lives; a session
    is the bb-session enter at the head of its view. Read from /proc,
    which an agent that is root sees whole."""
    root = (root or ROOT_BUNDLE_DIR).rstrip("/") + "/"
    try:
        with open(os.path.join(proc, "stat")) as f:
            btime = next(int(line.split()[1]) for line in f if line.startswith("btime "))
        hz = os.sysconf("SC_CLK_TCK")
    except (OSError, ValueError, StopIteration):
        return None, set()
    oldest, named = None, set()
    for pid in os.listdir(proc):
        if not pid.isdigit():
            continue
        try:
            with open(os.path.join(proc, pid, "cmdline"), "rb") as f:
                argv = f.read().decode("utf-8", "replace").split("\0")
        except OSError:
            continue
        for a in argv:
            if a.startswith(root):
                named.add(a[len(root):].split("/", 1)[0])
        if not (any(a.rsplit("/", 1)[-1] == "bb-session" for a in argv[:4]) and "enter" in argv[:6]):
            continue
        try:
            with open(os.path.join(proc, pid, "stat")) as f:
                began = btime + int(f.read().rsplit(")", 1)[1].split()[19]) / hz
        except (OSError, ValueError, IndexError):
            continue
        oldest = began if oldest is None else min(oldest, began)
    return oldest, named


def stale_bundles(root, current, oldest=None, named=()):
    """The bundle folders under `root` that nothing can still be running
    from, oldest first. A bundle was current from its folder's time until
    the next one's, so it goes only when the next one arrived before the
    oldest running session was entered and no process names it. The current
    one and the two before it stay whatever runs, as before, and no more
    than BUNDLES_MOST are kept. Kept by count alone (the newest three), a
    session open across three updates of its controller lost the folder its
    hooks run from: each then failed as a program that could not be run,
    which a coding agent passes over, so the session went on with no gate,
    no refused commands and no notices, saying only 'Stop hook failed'."""
    def at(d):
        try:
            return os.path.getmtime(os.path.join(root, d))
        except OSError:
            return 0.0
    try:
        dirs = [d for d in os.listdir(root) if d not in (current, "current") and not d.startswith(".")
                and os.path.isdir(os.path.join(root, d)) and not os.path.islink(os.path.join(root, d))]
    except OSError:
        return []
    dirs.sort(key=at)                                  # oldest first; the current one follows them all
    drop = []
    for i, d in enumerate(dirs):
        if i >= len(dirs) - 2 or d in named:
            continue
        nxt = at(dirs[i + 1])
        if oldest is None or nxt <= oldest - BUNDLE_SLACK_S:
            drop.append(d)
    kept = [d for d in dirs if d not in drop]
    over = len(kept) + 1 - BUNDLES_MOST
    if over > 0:
        drop += kept[:over]
    return sorted(drop, key=at)


class WorkspaceMixin:
    """Agent's workspace methods: one of the parts class Agent (agent.py) is made of."""

    # -- the workspace (docs/nodes.md §6, phase 6) ------------------------------
    def own_dir(self, path, who):
        """Make a directory the enrolled account can use: a job runs as it,
        and this process is root."""
        os.makedirs(path, exist_ok=True)
        if who:
            # By the folder itself, never through a link left at its name.
            with contextlib.suppress(OSError):
                fd = os.open(path, os.O_RDONLY | os.O_DIRECTORY | os.O_NOFOLLOW)
                try:
                    os.fchown(fd, who["user"], who["group"])
                finally:
                    os.close(fd)

    def materialize(self, job, src, who):
        """The job's source, on disk: the snapshot by digest, from the
        cache store when this node has fetched it before and from the
        controller otherwise, checked against its digest either way, then
        unpacked into a directory of the job's own under the data store."""
        stores = self.state.get("stores") or {}
        digest = str(src.get("digest") or "")
        hexd = digest.split(":", 1)[-1]
        if not re.fullmatch(r"[0-9a-f]{64}", hexd):
            job.say(f"refused: not a snapshot digest: {digest!r}\n")
            return None
        snaps = os.path.join(stores.get("cache") or "/tmp", "snapshots")
        os.makedirs(snaps, exist_ok=True)
        tar_path = os.path.join(snaps, hexd + ".tar")
        if not os.path.isfile(tar_path):
            job.say(f"fetching snapshot {hexd[:12]}…\n")
            st, _ = self.ctl.fetch(f"source?digest={hexd}", tar_path)
            if st != 200:
                job.say(f"the controller has no snapshot {hexd[:12]} ({st}): the tree "
                        "has moved on; queue the job again\n")
                return None
        h = hashlib.sha256()
        with open(tar_path, "rb") as f:
            for chunk in iter(lambda: f.read(1 << 20), b""):
                h.update(chunk)
        if h.hexdigest() != hexd:
            os.remove(tar_path)
            job.say("the cached snapshot did not match its digest; dropped it. Queue the job again\n")
            return None
        ws = os.path.join(stores.get("data") or "/tmp", "jobs", job.job["id"], "workspace")
        shutil.rmtree(os.path.dirname(ws), ignore_errors=True)
        os.makedirs(ws)
        with tarfile.open(tar_path) as tar:
            # Python 3.12's filter refuses paths that escape the target;
            # older interpreters get the members checked by hand.
            if hasattr(tarfile, "data_filter"):
                tar.extractall(ws, filter="data")
            else:
                for m in tar.getmembers():
                    if m.name.startswith("/") or ".." in m.name.split("/"):
                        raise RuntimeError(f"snapshot member escapes the workspace: {m.name}")
                tar.extractall(ws)
        if who:
            for d, _dirs, files in os.walk(os.path.dirname(ws)):
                for x in [d] + [os.path.join(d, f) for f in files]:
                    with contextlib.suppress(OSError):
                        os.lchown(x, who["user"], who["group"])
        return ws

    def finish_workspace(self, job, ws, spec, state):
        """After the command: on success upload what the outputs globs
        match and delete the job's directory; on failure keep it for
        inspection and drop the older kept one for the same project, so
        a run of failures does not fill the store."""
        jobdir = os.path.dirname(ws)
        project = str((job.job.get("source") or {}).get("project") or "")
        # What the build took on this node, its workspace and the project's
        # cache as it left them, measured before the workspace goes: the
        # Artifacts view shows it and the next build's room check wants at
        # least that much free (R110 step 7).
        cache = os.path.join(((self.state.get("stores") or {}).get("cache") or "/tmp"),
                             re.sub(r"[^A-Za-z0-9._-]", "_", project or "project"))
        took = {"kind": "room", "workspace": dir_bytes(jobdir), "cache": dir_bytes(cache)}
        if took["workspace"] is not None:
            job.outputs.append(took)
        if state == "succeeded":
            self.deliver(job, ws, spec.get("outputs") or [])
            shutil.rmtree(jobdir, ignore_errors=True)
            return
        # Kept: this one. Dropped: any earlier kept failure of the same project.
        marker = os.path.join(jobdir, "project")
        with contextlib.suppress(OSError):
            with open(marker, "w") as f:
                f.write(project)
        jobs_root = os.path.dirname(jobdir)
        for other in os.listdir(jobs_root) if os.path.isdir(jobs_root) else []:
            od = os.path.join(jobs_root, other)
            if od == jobdir or other in self.jobs:
                continue
            try:
                with open(os.path.join(od, "project")) as f:
                    if f.read() == project:
                        shutil.rmtree(od, ignore_errors=True)
            except OSError:
                continue
        job.say(f"the workspace is kept at {ws} for a look; the next failure of "
                f"{project or 'this space'} replaces it\n")
        job.outputs.append({"kind": "workspace", "path": ws})

    def deliver(self, job, base, outputs):
        """Upload what the outputs globs match under `base` as artifacts.
        dist/<basename>, which is what a person looks for; two matches
        sharing a name are told apart by the directory the second came
        from, so a debug and a release APK of the same name both arrive."""
        seen = set()
        # Found and read as the job's account (base.acting_as): root opened
        # whatever a glob in the job's workspace named, so a link there to a
        # file only root reads went up as the space's artifact.
        who = self.drop_privileges({})
        for pat in list(outputs)[:16]:
            with fs_holds(who):
                hits = [h for h in sorted(glob.glob(os.path.join(base, str(pat)), recursive=True)) if os.path.isfile(h)]
            for hit in hits:
                rel = os.path.relpath(hit, base)
                name = os.path.basename(rel)
                if name in seen:
                    parent = os.path.basename(os.path.dirname(rel)) or "2"
                    name = f"{parent}-{name}"
                seen.add(name)
                with fs_holds(who):
                    st, r = self.ctl.upload(f"artifact?job={job.job['id']}&name={name}", hit)
                if st == 200 and not r.get("error"):
                    job.say(f"artifact {r['path']} ({os.path.getsize(hit)} bytes)\n")
                    job.outputs.append({"kind": "artifact", "path": r["path"],
                                        "size": r.get("size"), "sha256": r.get("sha256")})
                else:
                    job.say(f"could not deliver {rel}: {r.get('error') or st}\n")

    def bundle(self, job, who):
        """bb, its library and the catalog, from the controller by digest
        into the toolchain store; the directory it runs from, or '' when it
        could not be fetched. Shared by toolchain jobs, bb verbs, and (with
        no job, so `job` may be None and the log is this process's) the
        sessions this node runs (roadmap #24). `.bb/current` points at the
        newest unpacked copy, which is what a shell on this node puts on its
        PATH.

        On a node that trusts a release key the bundle is held to the list
        of files its release signed before any of it is unpacked
        (release.may_keep_bundle, R267 step 6). One that fails is unpacked
        nowhere, and the answer is the bundle this node had before, the
        directory `.bb/current` points at, or '' with none. The refusal is
        remembered with the digest and with what this node trusted, so the
        same bundle under the same trust is not fetched again: a job's log
        is told why each time, this process's log once. The controller is
        told too, in the census (REFUSED), for as long as the refusal
        stands, so the node's row and the bell say it."""
        say = job.say if job else (lambda t: log(t.rstrip("\n")))
        store = tc_root(self.state)
        if not store:
            say("refused: this node has no toolchain store\n")
            return ""
        self.own_dir(store, who)
        bbdir = os.path.join(store, ".bb")
        os.makedirs(bbdir, exist_ok=True)
        # What this node trusts, read from the file its console writes (as
        # an update's check does), not this process's copy.
        try:
            trust = load_state()
        except SystemExit:
            trust = self.state
        trusts = (tuple(release.trusted(trust)), release.unsigned_ok(trust))
        # Refused already, and nothing moved since: the controller's last
        # hello names the same bundle and the console trusts what it did.
        # A press at the console, or another bundle named, fetches again.
        was, named = getattr(self, "bundle_refused", None), getattr(self, "bundle_named", "")
        if was and named and was["digest"] == named and was["trust"] == trusts:
            # Still said to the controller, which may have named another
            # bundle in between and come back to this one.
            self._refusal_reported(was["digest"], was["why"])
            if job:
                job.say(was["why"] + "\n")
            return self._bundle_before(bbdir, job.say if job else None)
        # The tar lands where only root writes when this agent is root: a
        # path in the job's store is the job's to replace with a symlink.
        root = os.geteuid() == 0
        if root:
            os.makedirs(TOOLS_DIR, mode=0o700, exist_ok=True)
            os.chmod(TOOLS_DIR, 0o700)
        tar_path = os.path.join(TOOLS_DIR if root else bbdir, "bundle.tar")
        # This call's own download, beside it: checked under this name, and
        # given the tar's name only once it is to be unpacked (_UNPACK).
        part = f"{tar_path}.{threading.get_ident()}"
        st, digest = self.ctl.fetch("download?what=bundle", part)
        if st != 200:
            say(f"could not fetch aerie from the controller ({st})\n")
            return ""
        hexd = digest.split(":", 1)[-1]
        # The bytes are what the header says they are, or nothing here runs
        # them: the digest names the bundle everywhere else.
        h = hashlib.sha256()
        with open(part, "rb") as f:
            for chunk in iter(lambda: f.read(1 << 20), b""):
                h.update(chunk)
        if not hexd or h.hexdigest() != hexd:
            say(f"refused: the bundle's bytes do not match the digest the controller named ({hexd[:12]})\n")
            with contextlib.suppress(OSError):
                os.unlink(part)
            return ""
        into = os.path.join(bbdir, hexd[:16] or "bundle")
        # Every file in it is the one its release signed, or none of it is
        # unpacked: not here, not as root's tools, not as root's bundle.
        ok, said = self._bundle_checked(part, trust)
        if not ok:
            with contextlib.suppress(OSError):
                os.unlink(part)
            say(said + "\n")
            self.bundle_refused = {"digest": digest, "trust": trusts, "why": said}
            self._refusal_reported(digest, said)
            before = self._bundle_before(bbdir, say)
            if before and not self.session_digest:
                # What the terminals run is said to the controller by its
                # digest. The one before is known here by its folder, the
                # first 16 of it, unless it is this very bundle, unpacked
                # while this node still took it.
                self.session_digest = digest if before == into else "sha256:" + os.path.basename(before)
            return before
        self.bundle_refused = None
        self._refusal_reported("", "")
        with _UNPACK:
            os.replace(part, tar_path)
            # A download a stopped agent left half done, an hour on.
            with contextlib.suppress(OSError):
                for left in os.listdir(os.path.dirname(tar_path)):
                    at = os.path.join(os.path.dirname(tar_path), left)
                    if left.startswith("bundle.tar.") and time.time() - os.path.getmtime(at) > 3600:
                        os.unlink(at)
            if said and not os.path.isdir(into):
                # Said as the bundle arrives, not by every job that fetches it.
                say(said + "\n")
            if root:
                self._keep_root_tools(tar_path, hexd[:16] or "bundle", say, trust)
                self._keep_root_bundle(tar_path, hexd[:16] or "bundle", say)
            if not os.path.isdir(into):
                with tarfile.open(tar_path) as tar:
                    if hasattr(tarfile, "data_filter"):
                        tar.extractall(into, filter="data")
                    else:
                        tar.extractall(into)
                os.chmod(os.path.join(into, "scripts", "aerie"), 0o755)
                # The old name is in the bundle only for an agent not yet updated.
                with contextlib.suppress(OSError):
                    os.unlink(os.path.join(into, "scripts", "bb"))
                for x in ("bb-tty", "bb-work-note", "bb-prompt-relay"):
                    with contextlib.suppress(OSError):
                        os.chmod(os.path.join(into, "scripts", "dashboard", x), 0o755)
                say(f"aerie {hexd[:12]} unpacked into {into}\n")
            with contextlib.suppress(OSError):
                tmp = os.path.join(bbdir, ".current.new")
                if os.path.lexists(tmp):
                    os.unlink(tmp)
                os.symlink(os.path.basename(into), tmp)
                os.replace(tmp, os.path.join(bbdir, "current"))
        if who:
            for d, _dirs, files in os.walk(into):
                for x in [d] + [os.path.join(d, f) for f in files]:
                    with contextlib.suppress(OSError):
                        os.lchown(x, who["user"], who["group"])
        # Fetched by a job while the terminals open an older copy: leave the
        # change to the loop's session_check, which owns the session half;
        # this may be a job's thread. Without this the terminals opened
        # whatever bundle they were set up on until the next hello, up to ten
        # minutes, and a bb-tty that old looked for a transcript where the
        # bundle before it kept them.
        self.prune_bundles(bbdir, into)
        if self.session_up and self.session_bundle and digest != self.session_bundle:
            self.session_stale = into
        self.session_digest = digest
        return into

    def _refusal_reported(self, digest, said):
        """What the census says of a refused bundle (REFUSED), kept in step:
        the digest and the reason in this node's words without their
        leading "refused: ", bounded; nothing once a bundle is taken. A
        change is told with a hello now and not at the next one, up to ten
        minutes on: the controller says it to a person from the census."""
        why = said[len("refused: "):] if said.startswith("refused: ") else said
        if len(why) > REFUSED_MOST:
            why = why[:REFUSED_MOST - 1].rstrip() + "…"
        now = {"digest": digest, "why": why} if digest else {}
        if now == REFUSED:
            return
        if now:
            REFUSED.update(now)
        else:
            REFUSED.clear()
        hello_again(self, "the controller's bundle was refused here" if now else "the controller's bundle is taken now")

    @staticmethod
    def _bundle_before(bbdir, say=None):
        """The bundle this node goes on with when the controller's is
        refused: the directory `.bb/current` points at, or '' when there is
        none that holds aerie. Said where there is somebody to say it to."""
        cur = os.path.join(bbdir, "current")
        try:
            name = os.readlink(cur)
        except OSError:
            name = ""
        into = os.path.join(bbdir, name) if name and "/" not in name else os.path.realpath(cur) if name else ""
        if not (into and os.path.isfile(os.path.join(into, "scripts", "aerie"))):
            into = ""
        if say:
            say(f"this node goes on with the bundle it had before ({os.path.basename(into)[:12]})\n" if into
                else "this node has no bundle from before to go on with\n")
        return into

    @staticmethod
    def _bundle_checked(tar_path, trust):
        """(ok, words) for the tar just fetched, before any of it is
        unpacked: release.may_keep_bundle's answer over the list the tar
        carries, the signature beside it and the sha256 of every member.
        A node that trusts no key reads nothing here and keeps it, as
        before; one that does and cannot read the tar refuses it."""
        if not release.trusted(trust or {}):
            return True, ""
        text, sig, members = b"", "", {}
        try:
            with tarfile.open(tar_path) as tar:
                for m in tar:
                    if m.isdir():
                        # A folder carries no bytes. One that names a way
                        # out of where the bundle is unpacked is no folder
                        # of a bundle.
                        if m.name.startswith("/") or ".." in m.name.split("/"):
                            members[m.name] = "a folder outside the bundle"
                        continue
                    if m.name in members:
                        # Unpacked, the later one would be the file kept.
                        members[m.name] = "there twice"
                        continue
                    src = tar.extractfile(m) if m.isfile() else None
                    if src is None:
                        members[m.name] = "a link" if m.issym() or m.islnk() else "not a plain file"
                        continue
                    h, keep = hashlib.sha256(), []
                    wanted = (m.name == BUNDLE_LIST and m.size <= LIST_MOST) or (m.name == BUNDLE_SIG and m.size <= 4096)
                    while True:
                        chunk = src.read(1 << 20)
                        if not chunk:
                            break
                        h.update(chunk)
                        if wanted:
                            keep.append(chunk)
                    members[m.name] = h.hexdigest()
                    if wanted and m.name == BUNDLE_LIST:
                        text = b"".join(keep)
                    elif wanted:
                        with contextlib.suppress(ValueError, AttributeError):
                            sig = str(json.loads(b"".join(keep).decode("utf-8", "replace")).get("sig") or "")
        except (OSError, tarfile.TarError, EOFError) as e:
            return False, f"refused: the bundle cannot be read as a tar ({e}), so this node keeps the bundle it has"
        return release.may_keep_bundle(trust, text, sig, members)

    @staticmethod
    def _keep_root_tools(tar_path, name, say, trust=None):
        """Root's own copy of the tools it installs, lifted straight out of
        the checked tar into TOOLS_DIR/<name>/, and TOOLS_DIR/current pointed
        at it; the copies of other bundles go. On a node that pinned
        AerieOS's release key, only when the release signed those files
        (release.may_keep_tools, R227 step 1): the bundle's digest is the
        controller's word, and these are what root runs. Refused, root
        keeps the copy it has, and the job says why. Whether it was kept."""
        into = os.path.join(TOOLS_DIR, name)
        # This bundle's already, checked when it was kept: nothing to do,
        # and nothing said again on every job that fetches the bundle.
        if os.path.isdir(into) and os.path.realpath(os.path.join(TOOLS_DIR, "current")) == os.path.realpath(into):
            return True
        try:
            with tarfile.open(tar_path) as tar:
                files, sig = {}, ""
                for m in tar.getmembers():
                    rel = m.name.lstrip("./")
                    if rel == TOOLS_SIG and m.isfile() and m.size <= 4096:
                        with contextlib.suppress(ValueError, AttributeError):
                            sig = str(json.loads(tar.extractfile(m).read().decode("utf-8", "replace")).get("sig") or "")
                        continue
                    # ...and the provisioner's family files (R204), which it
                    # sources from beside itself.
                    if (rel not in ROOT_TOOLS and not rel.startswith("nodes/families/")) or not m.isfile():
                        continue
                    src = tar.extractfile(m)
                    if src is not None:
                        files[rel] = src.read()
                ok, said = release.may_keep_tools(trust or {}, release.tools_digest(files), sig)
                if said:
                    say(said + "\n")
                if not ok:
                    return False
                for rel, data in files.items():
                    dest = os.path.join(into, rel)
                    os.makedirs(os.path.dirname(dest), mode=0o700, exist_ok=True)
                    fd = os.open(dest + ".new", os.O_WRONLY | os.O_CREAT | os.O_TRUNC | os.O_NOFOLLOW, 0o600)
                    with os.fdopen(fd, "wb") as out:
                        out.write(data)
                    os.replace(dest + ".new", dest)
            tmp = os.path.join(TOOLS_DIR, ".current.new")
            if os.path.lexists(tmp):
                os.unlink(tmp)
            os.symlink(name, tmp)
            os.replace(tmp, os.path.join(TOOLS_DIR, "current"))
            for other in os.listdir(TOOLS_DIR):
                if other not in (name, "current", "bundle.tar") and os.path.isdir(os.path.join(TOOLS_DIR, other)):
                    shutil.rmtree(os.path.join(TOOLS_DIR, other), ignore_errors=True)
        except (OSError, tarfile.TarError) as e:
            say(f"could not keep root's copy of the bundle's tools: {e}\n")
            return False
        return True

    @staticmethod
    def _keep_root_bundle(tar_path, name, say):
        """The whole bundle, root-owned and nobody else's to write, unpacked
        from the checked tar into ROOT_BUNDLE_DIR/<name>/ and current pointed
        at it (R125): what bb-session tty starts a terminal from. The ones
        before it are kept while a session entered under them still runs
        (stale_bundles)."""
        into = os.path.join(ROOT_BUNDLE_DIR, name)
        try:
            os.makedirs(ROOT_BUNDLE_DIR, mode=0o755, exist_ok=True)
            os.chmod(ROOT_BUNDLE_DIR, 0o755)
            if not os.path.isdir(into):
                tmp = into + ".new"
                shutil.rmtree(tmp, ignore_errors=True)
                with tarfile.open(tar_path) as tar:
                    if hasattr(tarfile, "data_filter"):
                        tar.extractall(tmp, filter="data")
                    else:
                        tar.extractall(tmp)
                for d, dirs, files in os.walk(tmp):
                    for x in [d] + [os.path.join(d, f) for f in dirs + files]:
                        if os.path.islink(x):
                            continue
                        os.chown(x, 0, 0)
                        st = os.stat(x)
                        os.chmod(x, (st.st_mode & 0o755) | (0o755 if os.path.isdir(x) else 0o644))
                for x in ("scripts/aerie", "scripts/dashboard/bb-tty", "scripts/dashboard/bb-work-note",
                          "scripts/dashboard/bb-prompt-relay"):
                    with contextlib.suppress(OSError):
                        os.chmod(os.path.join(tmp, x), 0o755)
                os.replace(tmp, into)
            cur = os.path.join(ROOT_BUNDLE_DIR, "current")
            try:
                was = os.readlink(cur)
            except OSError:
                was = ""
            link = os.path.join(ROOT_BUNDLE_DIR, ".current.new")
            if os.path.lexists(link):
                os.unlink(link)
            os.symlink(name, link)
            os.replace(link, cur)
            if was != name:
                # Its time is when it became current, which is what the
                # one before it is kept by: a folder already here (a
                # controller gone back a build) is current from now.
                os.utime(into)
            oldest, named = sessions_from()
            for old in stale_bundles(ROOT_BUNDLE_DIR, name, oldest, named):
                shutil.rmtree(os.path.join(ROOT_BUNDLE_DIR, old), ignore_errors=True)
        except (OSError, tarfile.TarError) as e:
            say(f"could not keep root's copy of the bundle: {e}\n")

    @staticmethod
    def prune_bundles(bbdir, keep):
        """Drop the bundles nothing is going to run again.

        Every delivery unpacks into a directory named for its digest, and
        nothing removed them: 33 of them in four days on the first node to be
        looked at, one per commit that touches bb. Small each, unbounded
        together.

        What has to survive: the newest, which the terminals run and `current`
        names, and the three newest, which versions() probes for an SDK
        inventory. A shell holds `current` on its PATH, never a digest, so
        nothing older is run again.
        """
        keep_n = 5
        try:
            names = [d for d in os.listdir(bbdir) if len(d) == 16
                     and all(c in "0123456789abcdef" for c in d)]
            dirs = [os.path.join(bbdir, d) for d in names
                    if os.path.isdir(os.path.join(bbdir, d))]
            dirs.sort(key=os.path.getmtime, reverse=True)
        except OSError:
            return
        for d in dirs[keep_n:]:
            with contextlib.suppress(OSError):
                if d != keep:
                    shutil.rmtree(d)

    def artifact_dir(self, project, who=None, make=True):
        """This node's copy of one project's artifacts. Per project, because
        a node may be several projects' node and two of them may both ship
        an app-release.apk."""
        root = (self.state.get("stores") or {}).get("artifacts") or ""
        if not root:
            return ""
        name = re.sub(r"[^A-Za-z0-9._-]", "_", str(project or "")) or "_"
        d = os.path.join(root, name)
        if make:
            self.own_dir(d, who)
        return d
