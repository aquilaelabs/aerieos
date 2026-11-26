"""workspace.py: snapshots and the artifact store (docs/nodes.md §6, phase 6).

The tree is edited HERE (/workspace is the projects share, the only writable
copy) and built THERE, on a node. Nothing network-mounts /workspace onto a
node (§6 says why, four times over); instead a job carries a snapshot of the
working tree, dirty edits included, and the node materializes it into a
job-scoped directory that is deleted after. What a build produces comes
back the same way and lands in the project's dist/, which is already the one
place the Artifacts view reads, with a provenance record beside it saying
what built it, from what, and where.

What this module owns:

  - snapshot(project): the working tree as git sees it (tracked plus
    untracked, minus ignored and minus .git) as one uncompressed tar under
    /config/snapshots, named by its sha256. Uncompressed on purpose: the
    digest is of the bytes, and an unchanged tree makes byte-identical tar
    (owner and mode normalized, mtimes kept), so the node's by-digest cache
    means an unchanged tree transfers nothing. The last few per project are
    kept; a snapshot is a job's input and not a backup.
  - snapshot_at(project, ref): the tree as committed at a branch, tag or
    commit, by git archive, kept the same way: what a deploy ships.
  - path_for(digest): what the agent's `source` verb serves.
  - artifact_put(job, name, body): a file a job uploaded, into dist/ under a
    name the node chose and this side sanitized, plus dist/.provenance/ with
    the chain (job, node, source digest, command, sha256).
  - bundle(): bb and its library plus the toolchain catalog as one tar, which
    is what a node needs to run `aerie toolchains install` against its own toolchain
    store: the toolchain recipes stay in one catalog (§6) and travel to the
    node by digest, like the agent itself does.
"""

import hashlib
import json
import os
import re
import subprocess
import sys
import tarfile
import threading
import time
from pathlib import Path

import artifacts  # noqa: E402

HERE = Path(__file__).resolve().parent
REPO = HERE.parent.parent
# What the bundle is made of and how its files are listed, from scripts/lib
# (which the image carries beside this directory): the build's signer reads
# the same module.
if str(HERE.parent / "lib") not in sys.path:
    sys.path.insert(0, str(HERE.parent / "lib"))
import bundleparts  # noqa: E402
WORKSPACE = None
SNAPS = None
paths = None              # set by server.py: paths.py, where what grows is kept
KEEP_PER_PROJECT = 5
ARTIFACT_MAX = 1024 * 1024 * 1024        # a gigabyte: an APK is 30MB, an installer 300
_lock = threading.Lock()
_bundle = {}
# The tool packs' catalog rows (toolpacks.catalog_json, R77), handed over by
# the server: the bundle carries them as config/toolpacks.json beside the
# shipped catalog, which is how a node installs a pack by name.
packs_json = None
# The shipped catalog with a row's newer recipe from the vetted catalog in
# its place (catalogrows.text, R234 step 4), "" when there is none: the
# bundle carries it beside config/toolchains.json, as CATALOG_ROWS.
toolchains_json = None
# ...and the packs made on the controller, each a git bundle carried as
# config/toolpacks/NAME.bundle (toolpacks.hosted_files): [(arcname, path)].
packs_files = None
# The controller's own git dir for reading a tree (git._own, B153), set by
# the server: a deploy's tree is read through it, so a filter driver or a
# hook the tree's config names is never this process's to run. None in a
# module test, where the tree is read as it is.
own_git = None


def configure(*, workspace, state):
    globals()["WORKSPACE"] = Path(workspace)
    globals()["SNAPS"] = Path(state) / "snapshots"


def _snaps():
    """Where jobs' trees are kept: the Settings page's choice when the server
    has handed this module paths.py, read at use so a move applies to the
    next one; the state directory's own otherwise (a module test)."""
    return paths.of("job-snapshots") if paths else SNAPS


# ---------------------------------------------------------------------------
# snapshots

def _files(root):
    """The files a snapshot carries. Git's view when there is one (tracked
    and untracked, minus ignored), so build/ and node_modules/ stay behind
    without anybody listing them; every file but .git otherwise. dist/ is
    left out either way: it is the shelf the artifacts come BACK to, and
    shipping last week's APK to the node for it to ignore is waste."""
    names = None
    if (root / ".git").exists():
        try:
            p = subprocess.run(["git", "-C", str(root), "ls-files", "-z", "--cached",
                                "--others", "--exclude-standard"],
                               capture_output=True, timeout=120, check=False)
            if p.returncode == 0:
                names = [n for n in p.stdout.decode("utf-8", "surrogateescape").split("\0") if n]
        except (OSError, subprocess.SubprocessError):
            names = None
    if names is None:
        names = []
        for d, dirs, files in os.walk(root):
            dirs[:] = [x for x in dirs if x != ".git"]
            for f in files:
                names.append(os.path.relpath(os.path.join(d, f), root))
    return sorted(n for n in set(names) if not n.startswith("dist/") and n != "dist")


def snapshot(project):
    """The tree, now, as one tar; {digest, files, bytes, tar} or {error}."""
    root = WORKSPACE / project
    if not root.is_dir():
        return {"error": f"no space directory for {project}"}
    files = _files(root)
    snaps = _snaps()
    snaps.mkdir(parents=True, exist_ok=True)
    tmp = snaps / f".{project}.{os.getpid()}.{threading.get_ident()}.tar"
    n = size = 0
    with open(tmp, "wb") as fh, tarfile.open(fileobj=fh, mode="w", format=tarfile.PAX_FORMAT) as tar:
        for rel in files:
            p = root / rel
            try:
                if p.is_symlink():
                    # A link that stays inside the tree travels as a link
                    # (B281: the node built a different tree without them);
                    # one that points out of it is left behind, since the
                    # node's extraction refuses it and would refuse the lot.
                    target = os.readlink(p)
                    inside = (not os.path.isabs(target)
                              and not os.path.normpath(os.path.join(os.path.dirname(rel), target)).startswith(".."))
                    if not inside:
                        continue
                    ti = tar.gettarinfo(str(p), arcname=rel)
                    ti.uid = ti.gid = 0
                    ti.uname = ti.gname = ""
                    ti.mtime = int(ti.mtime)
                    tar.addfile(ti)
                    n += 1
                    continue
                if not p.is_file():
                    continue
                ti = tar.gettarinfo(str(p), arcname=rel)
            except OSError:
                continue
            # Normalized so the digest is of the tree and not of who owns it
            # on this box; mtimes are kept because build tools read them.
            ti.uid = ti.gid = 0
            ti.uname = ti.gname = ""
            ti.mtime = int(ti.mtime)
            ti.mode = 0o755 if ti.mode & 0o100 else 0o644
            with open(p, "rb") as f:
                tar.addfile(ti, f)
            n += 1
            size += ti.size
    h = hashlib.sha256()
    with open(tmp, "rb") as f:
        for chunk in iter(lambda: f.read(1 << 20), b""):
            h.update(chunk)
    hexd = h.hexdigest()
    final = snaps / f"{hexd}.tar"
    with _lock:
        os.replace(tmp, final)
        meta = {"project": project, "at": int(time.time()), "files": n,
                "bytes": size, "tar": final.stat().st_size}
        (snaps / f"{hexd}.json").write_text(json.dumps(meta))
        _prune(project)
    return {"digest": "sha256:" + hexd} | meta


def snapshot_at(project, ref):
    """The tree as committed at `ref` (a branch, a tag or a commit), as one
    tar kept as snapshot() keeps one: what a deploy ships (R281 step 4) is
    what was committed, never a working tree's edits. Read through the
    controller's own git dir (own_git). git archive's own tar,
    whose bytes are the commit's alone (its time on every file, root its
    owner), so the same commit is the same digest and the node's cache
    holds it. dist/ is left out as snapshot() leaves it.
    {digest, commit, tag, files, bytes, tar} or {error}, `tag` the ref
    where it is a tag of that commit."""
    root = WORKSPACE / project
    ref = str(ref or "").strip()
    if not (root / ".git").exists():
        return {"error": f"{project} is not a git repository"}
    if not ref or ref.startswith("-") or not re.fullmatch(r"[\w./@^~+-]{1,200}", ref):
        return {"error": "pick a branch, a tag or a commit"}
    own = own_git(root) if own_git else None
    if own_git and not own:
        return {"error": f"{project}'s repository could not be read safely"}
    git = ["git", f"--git-dir={own}"] if own else ["git", "-C", str(root)]

    def commit_of(name):
        try:
            got = subprocess.run([*git, "rev-parse", "--verify", "--quiet", f"{name}^{{commit}}"],
                                 capture_output=True, text=True, timeout=30, check=False)
        except (OSError, subprocess.SubprocessError):
            return ""
        out = got.stdout.strip()
        return out if got.returncode == 0 and re.fullmatch(r"[0-9a-f]{40,64}", out) else ""
    commit = commit_of(ref)
    if not commit:
        return {"error": f"{ref} is no commit in {project}"}
    # A release's tag names its image: the ref itself where it is a tag of
    # this commit.
    tag = ref if re.fullmatch(r"[A-Za-z0-9_][A-Za-z0-9_.-]{0,127}", ref) and commit_of(f"refs/tags/{ref}") == commit else ""
    snaps = _snaps()
    snaps.mkdir(parents=True, exist_ok=True)
    tmp = snaps / f".{project}.{os.getpid()}.{threading.get_ident()}.tar"
    try:
        with open(tmp, "wb") as fh:
            p = subprocess.run([*git, "-c", "tar.umask=022", "archive", "--format=tar", commit,
                                "--", ".", ":(exclude)dist"], stdout=fh, stderr=subprocess.PIPE, timeout=300, check=False)
    except (OSError, subprocess.SubprocessError) as e:
        tmp.unlink(missing_ok=True)
        return {"error": f"git archive: {e}"}
    if p.returncode:
        tmp.unlink(missing_ok=True)
        return {"error": "git archive: " + (p.stderr.decode(errors="replace").strip().splitlines() or ["failed"])[-1]}
    n = size = 0
    with tarfile.open(tmp) as tar:
        for ti in tar:
            if ti.isfile():
                n += 1
                size += ti.size
            elif ti.issym():
                n += 1
    h = hashlib.sha256()
    with open(tmp, "rb") as f:
        for chunk in iter(lambda: f.read(1 << 20), b""):
            h.update(chunk)
    hexd = h.hexdigest()
    final = snaps / f"{hexd}.tar"
    with _lock:
        os.replace(tmp, final)
        meta = {"project": project, "at": int(time.time()), "commit": commit, "tag": tag, "files": n,
                "bytes": size, "tar": final.stat().st_size}
        (snaps / f"{hexd}.json").write_text(json.dumps(meta))
        _prune(project)
    return {"digest": "sha256:" + hexd} | meta


def _prune(project):
    """Keep the newest few per project. A job still queued against an older
    one gets 'no such snapshot' from the node and fails plainly, which is
    the honest answer to a tree that has moved on five times since."""
    have = []
    for mp in _snaps().glob("*.json"):
        try:
            m = json.loads(mp.read_text())
        except (OSError, ValueError):
            continue
        if m.get("project") == project:
            have.append((m.get("at", 0), mp))
    have.sort(reverse=True)
    for _, mp in have[KEEP_PER_PROJECT:]:
        for p in (mp, mp.with_suffix(".tar")):
            try:
                p.unlink()
            except OSError:
                pass


def path_for(digest):
    """The tar for a digest, or None. The digest is the file name, so a
    node asking for one it made up gets nothing rather than a path."""
    m = re.fullmatch(r"(?:sha256:)?([0-9a-f]{64})", str(digest or ""))
    if not m or _snaps() is None:
        return None
    p = _snaps() / f"{m.group(1)}.tar"
    return p if p.is_file() else None


# ---------------------------------------------------------------------------
# artifacts

def _safe_name(name):
    """A dist/ path a node may write: at most two levels, plain characters,
    no dots-only parts. The node chose it from the job's outputs globs; this
    side decides whether it is a name at all."""
    parts = [p for p in str(name or "").replace("\\", "/").split("/") if p]
    if not parts or len(parts) > 2:
        return None
    for p in parts:
        if not re.fullmatch(r"[A-Za-z0-9][A-Za-z0-9._+-]{0,120}", p) or set(p) <= {"."}:
            return None
    return "/".join(parts)


def artifact_put(job, name, stream, length, extra=None):
    """A file a job uploaded, into the project's dist/. {path, size, sha256}
    or {error}. Streamed to a temp file beside the target and renamed, so
    the tab never lists a half-written APK."""
    rel = _safe_name(name)
    if rel is None:
        return {"error": f"not a name an artifact may have: {name!r}"}
    project = (job or {}).get("project") or ""
    root = WORKSPACE / project
    if not project or not root.is_dir():
        return {"error": "the job has no space directory to land in"}
    if not 0 < length <= ARTIFACT_MAX:
        return {"error": f"an artifact is between 1 byte and {ARTIFACT_MAX >> 20}MB"}
    dest = root / "dist" / rel
    dest.parent.mkdir(parents=True, exist_ok=True)
    tmp = dest.with_name(f".{dest.name}.{job['id']}.part")
    h = hashlib.sha256()
    got = 0
    try:
        with open(tmp, "wb") as f:
            while got < length:
                chunk = stream.read(min(1 << 20, length - got))
                if not chunk:
                    break
                f.write(chunk)
                h.update(chunk)
                got += len(chunk)
        if got != length:
            tmp.unlink(missing_ok=True)
            return {"error": f"short upload: {got} of {length} bytes"}
        os.replace(tmp, dest)
    except OSError as e:
        tmp.unlink(missing_ok=True)
        return {"error": f"could not write {rel}: {e.strerror}"}
    spec = job.get("spec") or {}
    prov = {"job": job["id"], "node": job.get("node", ""), "type": job.get("type", ""),
            "source": job.get("source") or {}, "argv": spec.get("argv") or [],
            "requested_by": job.get("requested_by", ""), "at": int(time.time()),
            "sha256": h.hexdigest(), "size": got, "path": "dist/" + rel}
    # What the job adds about it: a sign job, what signed it (R106).
    prov.update(extra or {})
    pdir = root / "dist" / ".provenance"
    try:
        (pdir / (rel + ".json")).parent.mkdir(parents=True, exist_ok=True)
        (pdir / (rel + ".json")).write_text(json.dumps(prov, indent=1))
    except OSError:
        pass                                 # the artifact landed; the chain is best effort
    # A build landing is when the older ones are superseded, not when the
    # tab is next opened (the operator, 6 Oct).
    if "/" not in rel:
        try:
            artifacts.sweep_dev_builds(project, artifacts.dev_keep(project) if artifacts.dev_keep else artifacts.DEV_KEEP)
        except Exception as e:  # noqa: BLE001 (the artifact landed; the sweep is housekeeping)
            print(f"dashboard: dist sweep of {project}: {e}", flush=True)
    return {"path": "dist/" + rel, "size": got, "sha256": h.hexdigest()}


def file_path(project, rel):
    """A file under the project's dist/ a node may fetch as a job input:
    an APK to install on its emulator, say. dist/ only: the tree travels as
    a snapshot, and nothing else of a project is a node's to read."""
    rel = str(rel or "").replace("\\", "/")
    if rel.startswith("dist/"):
        rel = rel[5:]
    safe = _safe_name(rel)
    if safe is None or WORKSPACE is None:
        return None
    root = artifacts.dist_dir(WORKSPACE / project)
    if root is None:
        return None
    p = (root / safe).resolve()
    try:
        p.relative_to(root)
    except ValueError:
        return None
    return p if p.is_file() else None


def provenance(project, rel):
    """What built dist/<rel>, if a job did. None for a file somebody copied."""
    rel = str(rel or "")
    if rel.startswith("dist/"):
        rel = rel[5:]
    p = WORKSPACE / project / "dist" / ".provenance" / (rel + ".json")
    try:
        d = json.loads(p.read_text())
        return d if isinstance(d, dict) else None
    except (OSError, ValueError):
        return None


# ---------------------------------------------------------------------------
# the toolchain bundle

# What a release ships in the bundle, named in scripts/lib/bundleparts.py: the
# build's signer lists the same files from the tree (tools/sign-agent.py),
# and a node that pinned the release key holds what it is sent to that list.
BUNDLE_PARTS = bundleparts.PARTS


# What a bundle's build said already, each once (bundle()): a part it was
# built without, by name, and a list of files its build did not sign.
_bundle_missing = set()


# The list of the files a release ships in this bundle, each with its
# sha256, made from the very bytes the tar carries (bundleparts.listing), and
# the release's signature over that list's digest, where the build made one
# (the agent's base.BUNDLE_LIST and BUNDLE_SIG, release.may_keep_bundle).
BUNDLE_LIST = "nodes/bundle.list"
BUNDLE_SIG = "nodes/bundle.sig"
# The shipped catalog with the vetted catalog's newer rows in the shipped
# ones' places, as a member of its own: config/toolchains.json goes as the
# release shipped it, which is what the release signed, and the three
# readers on a node take this one where it is beside it (sdk.sh, sdkmeta.py,
# the agent's toolchains.read_catalog).
CATALOG_ROWS = "config/toolchains.catalog.json"


def _signed(part):
    """One part of scripts/agent/agent.sig as (digest, sig): the list of the
    bundle's files ("bundle"), which a release's build writes and a build
    from a branch does not. ("", "") where there is none, or its signature
    is not one."""
    try:
        d = json.loads((REPO / "scripts" / "agent" / "agent.sig").read_text())
        t = d.get(part) if isinstance(d, dict) else None
        if isinstance(t, dict) and re.fullmatch(r"[0-9a-f]{128}", str(t.get("sig") or "")):
            return str(t.get("digest") or "")[:80], t["sig"]
    except (OSError, ValueError):
        pass
    return "", ""


def _bundle_sig():
    """The bundle's bundle.sig as text, or "": {"digest", "sig"} from the
    part of scripts/agent/agent.sig that signs the list of the bundle's
    files. Passed on as it is: this side holds no key and checks nothing,
    since the node is the one that must not take this controller's word."""
    digest, sig = _signed("bundle")
    return json.dumps({"digest": digest, "sig": sig}) if sig else ""


def bundle():
    """bb, its library and the catalog as one tar: {body, digest, files,
    files_signed}. Rebuilt when any of its files moves, so a node
    installing a toolchain runs the recipes this controller ships right
    now, by digest. `files` is the digest of the list of what a release
    ships in it, as this install holds those files, and `files_signed`
    whether this build's signature names that same list."""
    pairs = bundleparts.files(REPO, BUNDLE_PARTS)
    stamp = [(name, int(os.stat(path).st_mtime_ns)) for name, path in pairs]
    packs = packs_json() if packs_json else ""
    hosted = packs_files() if packs_files else []
    stamp.extend(int(p.stat().st_mtime_ns) for _, p in hosted)
    shipped = REPO / "config" / "toolchains.json"
    newer = toolchains_json(shipped.read_text()) if toolchains_json and shipped.is_file() else ""
    # The release's signatures over the tools root installs from this bundle
    # (R227 step 1) and over the list of every file it ships (R267 step 6),
    # where the build made them: beside the agent's, in the file
    # tools/sign-agent.py writes, and each carried as a member of its own.
    bundle_sig = _bundle_sig()
    key = hash((tuple(stamp), packs, newer, bundle_sig))
    if _bundle.get("key") != key:
        import io
        for part in bundleparts.missing(REPO, BUNDLE_PARTS):
            # Said by name, once a build: a part this image does not
            # hold was left out without a word, and the node that
            # needed it found out by not having it (the audit of 13
            # Nov: bb-netcut, until the Dockerfile named it).
            if part not in _bundle_missing:
                _bundle_missing.add(part)
                print(f"dashboard: the bundle a node fetches is missing {part}: this install does not hold it",
                      flush=True)
        buf, held, newest = io.BytesIO(), [], 0
        with tarfile.open(fileobj=buf, mode="w", format=tarfile.PAX_FORMAT) as tar:
            for name, path in pairs:
                ti = tar.gettarinfo(path, arcname=name)
                ti.uid = ti.gid = 0
                ti.uname = ti.gname = ""
                # Read once: the bytes the tar carries are the bytes listed.
                with open(path, "rb") as fh:
                    data = fh.read()
                ti.size = len(data)
                tar.addfile(ti, io.BytesIO(data))
                held.append((name, data))
                newest = max(newest, int(ti.mtime))
            text, listed = bundleparts.listing(held)
            # What this side adds beside the release's files. Each carries
            # the newest of those files' times, not this moment's: the same
            # files make the same tar at every start, so a controller that
            # restarts sends no node a new bundle for it.
            for name, data in ((BUNDLE_LIST, text), (BUNDLE_SIG, bundle_sig),
                               # The catalog's newer rows, beside the shipped
                               # file and never in its place.
                               (CATALOG_ROWS, newer), ("config/toolpacks.json", packs)):
                if data:
                    data = data.encode("utf-8")
                    ti = tarfile.TarInfo(name)
                    ti.size, ti.mode, ti.mtime = len(data), 0o644, newest
                    tar.addfile(ti, io.BytesIO(data))
            for arc, f in hosted:
                ti = tar.gettarinfo(str(f), arcname=arc)
                ti.uid = ti.gid = 0
                ti.uname = ti.gname = ""
                ti.mode = 0o644
                with open(f, "rb") as fh:
                    tar.addfile(ti, fh)
        signed = _signed("bundle")[0]
        if signed and signed != listed and "not signed" not in _bundle_missing:
            # Once a build, and no guess at which file: a build's signature
            # is over the files it was made from, and an install whose files
            # are others (one edited in place, a part missing) is refused
            # by every node that pinned a key.
            _bundle_missing.add("not signed")
            print("dashboard: the files in the bundle a node fetches are not the ones this build signed "
                  f"(they list as {listed[7:23]}, the signature is for {signed[7:23]}): "
                  "a node that pinned a release key refuses them and keeps the bundle it has", flush=True)
        body = buf.getvalue()
        _bundle.update(key=key, body=body, files=listed, files_signed=bool(signed) and signed == listed,
                       digest="sha256:" + hashlib.sha256(body).hexdigest())
    return {"body": _bundle["body"], "digest": _bundle["digest"],
            "files": _bundle["files"], "files_signed": _bundle["files_signed"]}
