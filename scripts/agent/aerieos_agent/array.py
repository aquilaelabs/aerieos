"""An Unraid-style array on the controller's own machine (R162 step 2):
disks of mixed sizes, each its own XFS or btrfs filesystem, pooled into one
tree by mergerfs with parity on one or two disks kept by SnapRAID, which
is periodic rather than real time: a file written since the last sync is
unprotected until the next, and the page says so. AerieOS's own record
(/etc/builderbot/array.json, written whole by the storage-array job) is
what snapraid.conf and the array's fstab lines are rendered from; the
census reads the record, each disk's room and the state file the last
sync, scrub or check left. Disks are named to the record by their
/dev/disk/by-id links and mounted by filesystem UUID, so the array follows
its disks across ports and reboots. A disk that holds anything is refused
unless the job says to wipe it, and nothing is ever made on the system
disk; destroying the array unmounts it and forgets it, every data disk's
files left as they are, readable on any Linux.
"""
import contextlib
import json
import os
import re
import shutil
import subprocess
import tempfile
import time

from .disks import disks_now, moved
from .pools import by_id, _out

RECORD = "/etc/builderbot/array.json"
STATE = "/var/lib/builderbot/array-state.json"
SNAPRAID_CONF = "/etc/snapraid.conf"
FSTAB = "/etc/fstab"
MARK = "# builderbot-array"
MOUNT = "/mnt/array"
ADOPTED_MOUNT = "/mnt/user"
# A share as the mover takes it (the share rule of shares.py), and a place
# its files are: a pool by its name, or the array (the data disks merged,
# /mnt/user0).
MOVE_SHARE = re.compile(r"(?=.{1,63}$)[A-Za-z0-9][A-Za-z0-9_.-]*(?: [A-Za-z0-9_.-]+)*")
MOVE_PLACE = re.compile(r"array|[a-z][a-z0-9_-]{0,31}")
MAX_MOVES = 128
DISKS = "/mnt/disks"
PARITY = "/mnt/parity"
CONTENT = "/var/lib/builderbot/snapraid.content"
FS = ("xfs", "btrfs")
# mergerfs's create policies as the page offers them.
POLICIES = {"mfs": "most free space", "lfs": "fill up (least free space)", "epmfs": "existing path, then most free space", "ff": "first disk with room"}
ACTIONS = ("create", "add", "replace", "sync", "scrub", "check", "verify", "takeover", "mover", "moves", "destroy")
MAX_DATA, MAX_PARITY = 24, 2
NAME_RE = re.compile(r"[a-z][a-z0-9]{0,31}")
SLOT_RE = re.compile(r"(d|p)([1-9][0-9]?)")


def _env(k, d):
    return os.environ.get(k) or d


def read_record():
    try:
        with open(_env("BB_ARRAY_RECORD", RECORD), encoding="utf-8") as f:
            r = json.load(f)
        return r if isinstance(r, dict) and isinstance(r.get("data"), list) else {}
    except (OSError, ValueError):
        return {}


def write_record(rec):
    path = _env("BB_ARRAY_RECORD", RECORD)
    os.makedirs(os.path.dirname(path), exist_ok=True)
    tmp = path + ".new"
    with open(tmp, "w", encoding="utf-8") as f:
        json.dump(rec, f, indent=1, sort_keys=True)
    os.chmod(tmp, 0o644)
    os.replace(tmp, path)


def _state():
    try:
        with open(_env("BB_ARRAY_STATE", STATE), encoding="utf-8") as f:
            s = json.load(f)
        return s if isinstance(s, dict) else {}
    except (OSError, ValueError):
        return {}


def _state_set(**kw):
    s = _state()
    s.update(kw)
    path = _env("BB_ARRAY_STATE", STATE)
    os.makedirs(os.path.dirname(path), exist_ok=True)
    with open(path + ".new", "w", encoding="utf-8") as f:
        json.dump(s, f)
    os.replace(path + ".new", path)


def mount_of(kind, slot):
    return f"{DISKS}/d{slot}" if kind == "d" else f"{PARITY}/p{slot}"


def slot_mount(kind, x):
    """Where a slot's disk is: its own path for a disk another system's
    array had (R163 step 3: /mnt/diskN, kept), the array's otherwise."""
    return str(x.get("where") or "") or mount_of(kind, int(x["slot"]))


def merged_of(rec):
    """The merged tree over the data disks: the old system's /mnt/user for
    an array taken over (its pools before its disks), /mnt/array otherwise."""
    return ADOPTED_MOUNT if rec.get("adopted") else MOUNT


def moves_of(raw, pools=None):
    """Each share's places as the record keeps them, from what was asked:
    [{share, land, from, to}]. land is where its new files go (a pool, or
    the array); the mover takes its files from one place to another, from
    and to both set and different, or both empty when it leaves the share
    be. A pool not in `pools`, where that is given, or an entry in another
    shape is left out; one entry per share, the last said winning."""
    def ok(p):
        return bool(MOVE_PLACE.fullmatch(p)) and (pools is None or p == "array" or p in pools)
    out = {}
    for x in raw or []:
        if not isinstance(x, dict):
            continue
        s = str(x.get("share") or "")
        land, frm, to = (str(x.get(k) or "") for k in ("land", "from", "to"))
        if not MOVE_SHARE.fullmatch(s) or not ok(land) or bool(frm) != bool(to) or (frm and (not ok(frm) or not ok(to) or frm == to)):
            continue
        out[s] = {"share": s, "land": land, "from": frm, "to": to}
    return list(out.values())[:MAX_MOVES]


def moves_said(moves):
    """Each share's places in a line a person reads."""
    word = {"array": "the array"}
    return [f"{m['share']}: new files land on {word.get(m['land'], m['land'])}"
            + (f"; the mover takes them from {word.get(m['from'], m['from'])} to {word.get(m['to'], m['to'])}" if m["from"] else "; the mover leaves it")
            for m in moves]


def place_of(root, place, share):
    """A share's folder in a place: on a pool, or across the data disks."""
    return os.path.join(root, "user0" if place == "array" else place, share)


def _mounted(path):
    """Whether something is mounted at `path`: what the mover and SnapRAID
    ask before they write under it."""
    return os.path.ismount(path)


def _open_paths():
    """Every file a process here holds open, by the path /proc names it:
    what the mover leaves in place. A FUSE tree's own process (mergerfs)
    holds the file underneath, so a file open through /mnt/user is seen
    on its disk or pool as well."""
    out = set()
    try:
        pids = [p for p in os.listdir("/proc") if p.isdigit()]
    except OSError:
        return out
    for pid in pids:
        fd = f"/proc/{pid}/fd"
        try:
            names = os.listdir(fd)
        except OSError:
            continue
        for n in names:
            with contextlib.suppress(OSError):
                out.add(os.readlink(os.path.join(fd, n)))
    return out


def unmounted_slots(rec):
    """The slots of the record whose disk is not mounted where SnapRAID
    reads it: any one stops a sync, scrub, check or fix, which would
    otherwise write the parity into memory or read a missing disk as
    emptied."""
    return [slot_mount(kind, x) for kind, key in (("d", "data"), ("p", "parity"))
            for x in rec.get(key) or [] if not _mounted(slot_mount(kind, x))]


def adopted_pools():
    """The pools in front of the data disks in the old system's merged
    tree, by name, in its order."""
    from . import adopt
    br = ((adopt.read_record().get("plan") or {}).get("merged") or {}).get(adopt.mnt() + "/user") or []
    names = [os.path.basename(str(b).split("=", 1)[0]) for b in br]
    return [n for n in names if not adopt.DATA_RE.fullmatch(n)]


def stale_content():
    """With no array recorded, any content file on the system is an earlier
    one's (B704): taken away before a new array's first sync, which would
    otherwise read it and refuse its disks as changed."""
    p = _env("BB_SNAPRAID_CONTENT", CONTENT)
    for x in (p, p + ".tmp", p + ".lock"):
        with contextlib.suppress(OSError):
            os.unlink(x)


def render_snapraid(rec):
    """snapraid.conf from the record: the parity files on the parity disks,
    a content file on the system and on every data disk, each data disk by
    its slot."""
    out = ["# Written by AerieOS (the Storage page): the array's SnapRAID layout. Do not edit; the page writes it whole.\n"]
    for p in rec.get("parity") or []:
        n = int(p["slot"])
        out.append(f"{'' if n == 1 else f'{n}-'}parity {slot_mount('p', p)}/snapraid.{'' if n == 1 else f'{n}-'}parity\n")
    out.append(f"content {CONTENT}\n")
    for d in rec.get("data") or []:
        out.append(f"content {slot_mount('d', d)}/.snapraid.content\n")
    for d in rec.get("data") or []:
        out.append(f"data d{int(d['slot'])} {slot_mount('d', d)}/\n")
    out.append("exclude *.unrecoverable\nexclude /lost+found/\nexclude .snapraid.content\nexclude /.Trash*/\nexclude .DS_Store\n"
               "blocksize 256\nhashsize 16\nautosave 500\n")
    return "".join(out)


def render_fstab(rec):
    """The array's fstab lines: each disk by UUID at its slot's mount
    (nofail, so a missing disk never holds the boot), and the merged tree
    over the data disks, with the record's create policy and 20 GB kept
    free on each before the next is picked."""
    lines = []
    # An array taken over keeps its data disks and its merged tree on the
    # adoption's own lines (adopt.render_fstab): only its parity is ours.
    for d in [] if rec.get("adopted") else rec.get("data") or []:
        lines.append(f"UUID={d['uuid']} {mount_of('d', int(d['slot']))} {d.get('fs', 'xfs')} defaults,nofail,noatime 0 0 {MARK}\n")
    for p in rec.get("parity") or []:
        lines.append(f"UUID={p['uuid']} {slot_mount('p', p)} {p.get('fs', 'xfs')} defaults,nofail,noatime 0 0 {MARK}\n")
    if rec.get("data") and not rec.get("adopted"):
        policy = rec.get("policy") if rec.get("policy") in POLICIES else "mfs"
        req = ",".join(f"x-systemd.requires-mounts-for={mount_of('d', int(d['slot']))}" for d in rec["data"])
        lines.append(f"{DISKS}/d* {MOUNT} fuse.mergerfs defaults,nofail,allow_other,use_ino,cache.files=off,dropcacheonclose=true,"
                     f"category.create={policy},moveonenospc=true,minfreespace=20G,fsname=bbarray,{req} 0 0 {MARK}\n")
    return "".join(lines)


def write_fstab(rec):
    path = _env("BB_ARRAY_FSTAB", FSTAB)
    try:
        with open(path, encoding="utf-8") as f:
            kept = [ln for ln in f.read().splitlines(True) if not ln.rstrip().endswith(MARK)]
    except OSError:
        kept = []
    text = "".join(kept)
    if text and not text.endswith("\n"):
        text += "\n"
    with open(path + ".new", "w", encoding="utf-8") as f:
        f.write(text + render_fstab(rec))
    os.chmod(path + ".new", 0o644)
    os.replace(path + ".new", path)


def _df(path):
    try:
        st = os.statvfs(path)
        return st.f_frsize * st.f_blocks // 1048576, st.f_frsize * (st.f_blocks - st.f_bavail) // 1048576
    except OSError:
        return 0, 0


def array_now():
    """{policy, mount, data: [{slot, id, fs, size_mb, used_mb, mounted}],
    parity: [...], last_sync, last_scrub, last_check, status, running} for
    the census; {} where no array is recorded."""
    rec = read_record()
    if not rec:
        return {}
    st = _state()

    def row(kind, x):
        m = slot_mount(kind, x)
        mounted = os.path.ismount(m)
        size, used = _df(m) if mounted else (0, 0)
        return {"slot": int(x["slot"]), "id": str(x.get("id") or "")[:120], "fs": str(x.get("fs") or "")[:8],
                "size_mb": size, "used_mb": used, "mounted": mounted}
    return {"policy": str(rec.get("policy") or "mfs"), "mount": merged_of(rec), "mounted": os.path.ismount(merged_of(rec)),
            "adopted": rec.get("adopted") is True, "moves": moves_of(rec.get("moves")), "last_move": int(st.get("last_move") or 0),
            "data": [row("d", d) for d in rec.get("data") or []][:MAX_DATA],
            "parity": [row("p", p) for p in rec.get("parity") or []][:MAX_PARITY],
            "last_sync": int(st.get("last_sync") or 0), "last_scrub": int(st.get("last_scrub") or 0),
            "last_check": int(st.get("last_check") or 0), "status": str(st.get("status") or "")[:400],
            "running": str(st.get("running") or "")[:16], "progress": str(st.get("progress") or "")[:40],
            # The last full parity check (R163 step 15); its key's presence
            # says this agent has the verb.
            "verify": st.get("verify") if isinstance(st.get("verify"), dict) else {}}


PROGRESS_RE = re.compile(r"(\d{1,3})%,\s*(\d+) MB(?:,\s*(\d+) MB/s)?")
COUNT_RE = re.compile(r"(\d+) (file|io|data|recovered|unrecoverable) errors?")


def counts(text):
    """SnapRAID's closing counts: {"file", "io", "data", "recovered",
    "unrecoverable"} errors, the last of each it said."""
    out = {}
    for n, kind in COUNT_RE.findall(text or ""):
        out[kind] = int(n)
    return out


def scrub_log(path):
    """SnapRAID's log of a run (-l): ({"file", "io", "data", "recovered",
    "unrecoverable"} from its summary, [each file it named with an error,
    relative to its disk])."""
    counts_, files = {}, []
    try:
        with open(path, encoding="utf-8", errors="replace") as f:
            for line in f:
                m = re.match(r"summary:error_(file|io|data|recovered|unrecoverable):(\d+)", line)
                if m:
                    counts_[m.group(1)] = int(m.group(2))
                m = re.match(r"error:\d+:[^:]+:(.+?): \w+ error", line)
                if m and m.group(1) not in files:
                    files.append(m.group(1))
    except OSError:
        pass
    return counts_, files[:1000]


def run_watched(argv, say, progress, timeout=172800):
    """A SnapRAID run whose lines go to the job and whose progress line
    ("45%, 1234 MB, 120 MB/s ...", redrawn with a carriage return) is handed
    to `progress` as it moves: (exit code, all it said)."""
    proc = subprocess.Popen(argv, stdout=subprocess.PIPE, stderr=subprocess.STDOUT)
    said, buf, end = [], b"", time.time() + timeout
    while True:
        chunk = proc.stdout.read1(4096) if hasattr(proc.stdout, "read1") else proc.stdout.read(4096)
        if not chunk:
            break
        buf += chunk
        while True:
            cut = min([i for i in (buf.find(b"\n"), buf.find(b"\r")) if i >= 0], default=-1)
            if cut < 0:
                break
            line, buf = buf[:cut].decode("utf-8", "replace"), buf[cut + 1:]
            m = PROGRESS_RE.search(line)
            if m:
                progress(int(m.group(1)), int(m.group(3) or 0))
            elif line.strip():
                said.append(line)
                say(line + "\n")
        if time.time() > end:
            proc.kill()
            say("stopped: it ran past its time\n")
            break
    if buf.strip():
        said.append(buf.decode("utf-8", "replace"))
        say(said[-1] + "\n")
    return proc.wait(), "\n".join(said)


class ArrayMixin:
    """Agent's array jobs: one of the parts class Agent (agent.py) is made of."""

    def array_pass(self):
        """Once a minute: a recorded array whose mounts are missing (a disk
        back after a reboot without it) mounted again from fstab."""
        rec = read_record()
        if not rec or os.geteuid() != 0:
            return
        # An array taken over: the adoption's pass mounts its data disks
        # and its merged tree; only the parity is this one's.
        for kind, key in (("p", "parity"),) if rec.get("adopted") else (("d", "data"), ("p", "parity")):
            for x in rec.get(key) or []:
                m = slot_mount(kind, x)
                if not os.path.ismount(m) and os.path.isdir(m):
                    subprocess.run(["mount", m], capture_output=True, timeout=60, check=False)
        # The merged tree only over every data disk mounted: mergerfs reads
        # its glob at mount, and a disk missing then is left out of it.
        if rec.get("data") and not rec.get("adopted") and not os.path.ismount(MOUNT) and os.path.isdir(MOUNT) \
                and all(os.path.ismount(slot_mount("d", x)) for x in rec["data"]):
            subprocess.run(["mount", MOUNT], capture_output=True, timeout=60, check=False)

    def _mover(self, job, moves, root=None, age_s=600):
        """The mover, for an array taken over: each share's files from the
        place its entry names to the other (a pool, or the data disks by
        /mnt/user0). Left for next time, said: a file written in the last ten
        minutes, one a process holds open, and one whose path is on the other
        side already (the copy there is the one the merged tree shows, and it
        is never overwritten). Nothing moves unless both places are mounted
        (an empty mount point is the stick's memory) and neither share folder
        is a link. The folders it empties are removed, the share's own and
        any it did not empty kept. 0, or rsync's exit."""
        from . import adopt
        root = root or adopt.mnt()
        say, worst = job.say, 0
        now = time.time()
        held = None
        for mv in moves:
            if not mv.get("from") or not mv.get("to"):
                continue
            said = {"array": "the data disks"}
            src, dst = place_of(root, mv["from"], mv["share"]), place_of(root, mv["to"], mv["share"])
            if not os.path.isdir(src) or os.path.islink(src):
                if os.path.islink(src):
                    say(f"{mv['share']}: its folder on {said.get(mv['from'], mv['from'])} is a link, and the mover never follows one: left\n")
                continue
            down = [said.get(k, k) for k, d in ((mv["from"], src), (mv["to"], dst)) if not _mounted(os.path.dirname(d))]
            if down:
                say(f"{mv['share']}: {' and '.join(down)} {'is' if len(down) == 1 else 'are'} not mounted, so nothing moves "
                    "(a file put in an empty mount point would be in memory)\n")
                worst = worst or 1
                continue
            if os.path.islink(dst) or (os.path.exists(dst) and not os.path.isdir(dst)):
                say(f"{mv['share']}: its folder on {said.get(mv['to'], mv['to'])} is a link or not a folder, and the mover never writes through one: left\n")
                continue
            if held is None:
                held = _open_paths()
            files, kept, busy = [], 0, 0
            for here, _dirs, names in os.walk(src):
                for nm in names:
                    f = os.path.join(here, nm)
                    rel = os.path.relpath(f, src)
                    try:
                        st = os.lstat(f)
                    except OSError:
                        continue
                    if now - st.st_mtime < age_s:
                        continue
                    if f in held or os.path.join(root, "user", mv["share"], rel) in held:
                        busy += 1
                        continue
                    if os.path.lexists(os.path.join(dst, rel)):
                        kept += 1
                        continue
                    files.append(rel)
            if kept:
                say(f"{mv['share']}: {kept} file{'' if kept == 1 else 's'} left on {said.get(mv['from'], mv['from'])}: "
                    f"the same path is on {said.get(mv['to'], mv['to'])} already, and that copy is never overwritten\n")
            if busy:
                say(f"{mv['share']}: {busy} file{'' if busy == 1 else 's'} held open by a program, left for next time\n")
            if not files:
                continue
            with tempfile.NamedTemporaryFile("w", delete=False, suffix=".list") as fl:
                fl.write("".join(x + "\0" for x in files))
            try:
                say(f"{mv['share']}: {len(files)} file{'' if len(files) == 1 else 's'} from {said.get(mv['from'], mv['from'])} to {said.get(mv['to'], mv['to'])}\n")
                # rsync itself leaves a source in place whose size or time
                # changed while it was copied; --ignore-existing keeps a file
                # that appeared on the other side since the list was made.
                rc = self._sh(job, ["rsync", "-aHAXS", "--ignore-existing", "--remove-source-files", "--from0",
                                    f"--files-from={fl.name}", src + "/", dst + "/"], timeout=86400)
            finally:
                os.unlink(fl.name)
            worst = worst or rc
            emptied = set()
            for rel in files:
                d = os.path.dirname(rel)
                while d:
                    emptied.add(d)
                    d = os.path.dirname(d)
            for d in sorted(emptied, key=lambda x: -x.count("/")):
                with contextlib.suppress(OSError):
                    os.rmdir(os.path.join(src, d))
        return worst

    def _landing(self, say, moves, pools, root=None):
        """Where each share's new files land: the merged tree of an array
        taken over puts a new file on the first pool that holds its folder,
        and on the data disks where none does (mergerfs's epff). So a share
        landing on a pool has its folder made there, and one landing on the
        array has its folder on the data disks; every other pool's folder of
        it is removed when empty. A folder with anything in it is never
        touched: new files may land there until the mover empties it, said."""
        from . import adopt
        root = root or adopt.mnt()
        for mv in moves:
            s, land = mv["share"], mv["land"]
            here = place_of(root, land, s)
            if not os.path.isdir(here) and os.path.ismount(os.path.dirname(here)):
                try:
                    st = os.stat(os.path.join(root, "user", s))
                except OSError:
                    st = None
                try:
                    os.mkdir(here, 0o777)
                    if st:
                        os.chmod(here, st.st_mode & 0o7777)
                        os.chown(here, st.st_uid, st.st_gid)
                except OSError as e:
                    say(f"{s}: its folder could not be made on {land} ({e.strerror}), so its new files land where its folder already is\n")
                    continue
            for p in pools:
                d = os.path.join(root, p, s)
                if p == land or not os.path.isdir(d):
                    continue
                # A mount or a btrfs subvolume (a device of its own) is left
                # as it is, even empty.
                if os.path.ismount(d) or os.stat(d).st_dev != os.stat(os.path.dirname(d)).st_dev:
                    continue
                try:
                    os.rmdir(d)
                except OSError:
                    say(f"{s}: files are still on {p}, so its new files may land there until the mover takes them\n")

    def _array_takeover(self, job, cfg, rec, disks, snapraid, settle, run_snapraid):
        """Take an adopted array over (R163 step 3): its data disks made
        writable where they are (/mnt/diskN, never formatted or
        repartitioned), SnapRAID's parity on its old parity disk's first
        partition, given a filesystem (its partition table never rewritten),
        and the first sync, which builds the parity from nothing. SnapRAID's
        content files are the only new thing on a data disk. `dry` says it
        all and changes nothing. (state, code)."""
        from . import adopt
        from .pools import by_id
        say, dry = job.say, cfg.get("dry") is True
        arec = adopt.read_record()
        plan_ = arec.get("plan") or {}
        if rec:
            say("refused: an array is here already\n")
            return "failed", 66
        if not plan_.get("mounts"):
            say("refused: nothing is adopted here: the old system's disks are adopted first\n")
            return "failed", 66
        datas = [m for m in plan_["mounts"] if adopt.DATA_RE.fullmatch(os.path.basename(m["where"]))]
        if plan_.get("zfs") and any(adopt.DATA_RE.fullmatch(str(z.get("slot") or "")) for z in plan_["zfs"]):
            say("refused: a ZFS data disk is not taken into SnapRAID here yet\n")
            return "failed", 64
        if not datas:
            say("refused: no adopted data disk to take over\n")
            return "failed", 66
        if not dry and str(cfg.get("confirm") or "") != "parity":
            say("refused: taking the array over overwrites the old parity, and takes the word parity as the confirmation\n")
            return "failed", 64
        if not dry and not shutil.which("mkfs.xfs"):
            say("refused: no mkfs.xfs on this machine to give the parity partition its filesystem; install Storage on its Features section first\n")
            return "failed", 65
        # The parity disk found again by what the adoption read of it (its
        # by-id link or serial), never by the kernel name it had then: a
        # stick plugged in or a reboot moves sdX to another disk, which this
        # would format (B718).
        pars = []
        for x in (plan_.get("parity") or [])[:MAX_PARITY]:
            if not x.get("id"):
                say(f"refused: the parity disk was adopted as {x.get('dev') or 'a disk'} by its name alone, which may be another disk now: "
                    "release the adoption and adopt the old system again (Read only) so its parity disk is known by its serial, then take it over\n")
                return "failed", 66
            d = adopt.find_disk(list(disks.values()), x["id"])
            if d is not None:
                pars.append(d)
        if not pars:
            say("refused: the old system's parity disk is not on this machine: SnapRAID's parity needs a disk of its own\n")
            return "failed", 66
        unmounted = [m["where"] for m in datas if not _mounted(m["where"])]
        if unmounted:
            say(f"refused: {', '.join(unmounted)} {'is' if len(unmounted) == 1 else 'are'} not mounted: every data disk is mounted read-only "
                "before the array is taken over\n")
            return "failed", 66
        biggest = max(_df(m["where"])[0] for m in datas)
        parity, slot = [], 0
        for d in pars:
            slot += 1
            parts = d.get("parts") or []
            if d.get("system") or d.get("mounted"):
                say(f"refused: {d['name']}, the old parity disk, is {'the system disk' if d.get('system') else 'mounted'}\n")
                return "failed", 65
            if not parts:
                say(f"refused: {d['name']}, the old parity disk, has no partition, and its partition table is never rewritten here\n")
                return "failed", 65
            part = parts[0]["name"]
            held = parts[0].get("holds") or ""
            # A takeover that stopped after the parity took its filesystem
            # is taken up again: the partition this gave it, by its label.
            again = held == "xfs" and _out(["blkid", "-s", "LABEL", "-o", "value", f"/dev/{part}"]).strip() == f"aerie-p{slot}"
            if held not in ("nothing", "") and not again:
                say(f"refused: {part}, the old parity disk's partition, holds {held}: only a partition holding no filesystem is given one\n")
                return "failed", 65
            if d.get("size_mb", 0) < biggest:
                say(f"refused: {d['name']} is smaller than the largest data disk, so it cannot hold SnapRAID's parity\n")
                return "failed", 64
            parity.append({"slot": slot, "dev": d["name"], "part": part, "again": again})
        say("Taking the array over, as SnapRAID's: " + "; ".join(f"{os.path.basename(m['where'])} at {m['where']}, made writable where it is" for m in datas) + "\n")
        for p in parity:
            say(f"p{p['slot']}: {p['part']} on {p['dev']} given an xfs filesystem for SnapRAID's parity file; the old system's parity on it is gone, "
                "so going back to it takes its own parity sync\n")
        say("The first sync builds the parity from nothing: the array is unprotected until it ends, hours for a large one\n")
        # Each share's places (where its new files land, and the mover's
        # from and to), held to the pools in front of the data disks.
        pools = adopted_pools()
        moves = moves_of(cfg.get("moves"), pools)
        for line in moves_said(moves):
            say(line + "\n")
        if dry:
            say("dry run: nothing changed\n")
            return "succeeded", 0
        # The data disks writable, where they are.
        plan_["mounts"] = [{**m, "ro": False} if m in datas else m for m in plan_["mounts"]]
        plan_["merged"] = {w: [b[:-3] + "=RW" if b.endswith("=RO") else b for b in br] for w, br in (plan_.get("merged") or {}).items()}
        # A new file lands on the first pool holding its share's folder, and
        # on the data disks where none does: each share's landing is then
        # where its folder is (_landing), as the old system's was per share.
        plan_["user_create"] = "epff"
        arec.update(plan=plan_, writable=True)
        adopt.write_record(arec)
        adopt.write_fstab(plan_)
        for w in sorted(plan_.get("merged") or {}, reverse=True):
            if os.path.ismount(w):
                self._sh(job, ["umount", "-l", w], timeout=60)
        for m in datas:
            if os.path.ismount(m["where"]):
                self._sh(job, ["umount", m["where"]], timeout=120)
            if self._sh(job, ["mount", "-T", adopt._env("BB_ADOPT_FSTAB", adopt.FSTAB), m["where"]], timeout=120) != 0:
                for w in sorted(plan_.get("merged") or {}):
                    self._sh(job, ["mount", "-T", adopt._env("BB_ADOPT_FSTAB", adopt.FSTAB), w], timeout=60)
                say(f"{m['where']} did not mount writable (above): stopped before the parity disk was touched. The disks before it are "
                    "writable now, so the old system's parity no longer matches them; run the takeover again once it mounts\n")
                return "failed", 1
        for w in sorted(plan_.get("merged") or {}):
            self._sh(job, ["mount", "-T", adopt._env("BB_ADOPT_FSTAB", adopt.FSTAB), w], timeout=60)
        self._landing(say, moves, pools)
        new = {"policy": "adopted", "adopted": True, "data": [], "parity": [], "moves": moves}
        for m in datas:
            new["data"].append({"slot": int(os.path.basename(m["where"])[4:]), "id": m.get("what", ""), "uuid": m["what"].split("=", 1)[-1],
                                "fs": m["fs"], "where": m["where"]})
        for p in parity:
            if p["again"]:
                say(f"{p['part']} has the xfs an earlier takeover gave it: kept\n")
            elif self._sh(job, ["mkfs.xfs", "-L", f"aerie-p{p['slot']}", f"/dev/{p['part']}"], timeout=600) != 0:
                say(f"{p['part']} did not take xfs (above): the data disks are writable, and no parity is kept yet\n")
                return "failed", 1
            uuid = _out(["blkid", "-s", "UUID", "-o", "value", f"/dev/{p['part']}"]).strip()
            if not uuid:
                say(f"{p['part']} was given xfs but blkid gives it no UUID to mount it by: the data disks are writable, and no parity is kept yet; "
                    "run the takeover again\n")
                return "failed", 1
            new["parity"].append({"slot": p["slot"], "id": by_id(p["dev"]), "uuid": uuid, "fs": "xfs"})
        rec.clear()
        rec.update(new)
        stale_content()
        settle()
        for p in new["parity"]:
            m = slot_mount("p", p)
            os.makedirs(m, exist_ok=True)
            if not os.path.ismount(m) and self._sh(job, ["mount", m], timeout=60) != 0:
                say(f"{m} did not mount (above): run Sync now once it does\n")
                return "failed", 1
        arec["taken"] = True
        adopt.write_record(arec)
        say("building the parity: the array is unprotected until this ends\n")
        rc = run_snapraid("sync", key="last_sync")
        self.hello_again("the array was taken over")
        return ("succeeded", 0) if rc == 0 else ("failed", rc)

    def _apply_storage_array(self, job, cfg):
        say = job.say
        mergerfs, snapraid = shutil.which("mergerfs"), shutil.which("snapraid")
        if not mergerfs or not snapraid or os.geteuid() != 0:
            say("refused: an array is made by mergerfs and SnapRAID as root, and this agent lacks one of them or is not root (the storage feature installs them)\n")
            return "failed", 77
        action = str(cfg.get("array") or "")
        if action not in ACTIONS:
            say(f"refused: {action or 'no action'} is not an array action (one of {', '.join(ACTIONS)})\n")
            return "failed", 64
        rec = read_record()
        disks = {d["name"]: d for d in disks_now(smart=False)}
        wipe = cfg.get("wipe") is True

        def disk_ok(n):
            d = disks.get(n)
            if not d:
                say(f"refused: {n} is not a disk this machine lists\n")
                return False
            if d.get("system"):
                say(f"refused: {n} is the system disk, which never goes into the array\n")
                return False
            if (why := moved(n, d, cfg.get("ids"))):
                say(f"refused: {why}\n")
                return False
            # Anything mounted on it is in use, wipe or not.
            if d.get("mounted"):
                say(f"refused: {n} has something mounted on it\n")
                return False
            held = [p for p in d.get("parts") or [] if p.get("holds") not in ("nothing", "")] or ([d] if d.get("holds") not in ("nothing", "") else [])
            # ...and a partition table at all is something, though blkid may
            # not know what its partitions hold (an encrypted volume, a raw
            # image): only a wipe the job asked for overwrites it.
            if (held or d.get("parts")) and not wipe:
                said = held[0].get("holds") if held else "partitions"
                say(f"refused: {n} holds {said}; the job must say to wipe it\n")
                return False
            return True

        def make_fs(n, fs, label):
            """The whole disk one filesystem, labeled; its UUID back, or ""
            with why said."""
            if wipe and self._sh(job, ["wipefs", "-a", f"/dev/{n}"], timeout=120) != 0:
                say(f"{n}'s old signatures did not come off (wipefs above): it is not formatted\n")
                return ""
            # -f only where the job said to wipe: without it mkfs keeps its own
            # refusal of a disk that holds something it can see.
            force = ["-f"] if wipe else []
            argv = ["mkfs.xfs", *force, "-L", label, f"/dev/{n}"] if fs == "xfs" else ["mkfs.btrfs", *force, "-L", label, f"/dev/{n}"]
            if self._sh(job, argv, timeout=600) != 0:
                say(f"{n} did not take {fs} (above)\n")
                return ""
            uuid = _out(["blkid", "-s", "UUID", "-o", "value", f"/dev/{n}"]).strip()
            if not uuid:
                say(f"{n} was formatted but blkid gives it no UUID\n")
            return uuid

        def mount_all():
            for kind, key in (("d", "data"), ("p", "parity")):
                for x in rec.get(key) or []:
                    m = mount_of(kind, int(x["slot"]))
                    os.makedirs(m, exist_ok=True)
                    if not os.path.ismount(m) and self._sh(job, ["mount", m], timeout=60) != 0:
                        return False
            os.makedirs(MOUNT, exist_ok=True)
            if os.path.ismount(MOUNT):
                # mergerfs reads its branches' glob at mount: the tree is
                # remounted so a disk added or replaced is in it (a file
                # open through it at that moment sees an error once).
                self._sh(job, ["umount", "-l", MOUNT], timeout=60)
            return self._sh(job, ["mount", MOUNT], timeout=60) == 0

        def settle():
            write_fstab(rec)
            with open(_env("BB_SNAPRAID_CONF", SNAPRAID_CONF) + ".new", "w", encoding="utf-8") as f:
                f.write(render_snapraid(rec))
            os.replace(_env("BB_SNAPRAID_CONF", SNAPRAID_CONF) + ".new", _env("BB_SNAPRAID_CONF", SNAPRAID_CONF))
            os.makedirs(os.path.dirname(CONTENT), exist_ok=True)
            write_record(rec)

        def run_snapraid(what, *extra, key=None, timeout=86400):
            missing = unmounted_slots(rec)
            if missing:
                say(f"refused: {', '.join(missing)} {'is' if len(missing) == 1 else 'are'} not mounted, and SnapRAID run without "
                    f"{'it' if len(missing) == 1 else 'them'} would write its parity into memory or read a missing disk as emptied: "
                    "nothing run\n")
                return 65
            _state_set(running=what)
            try:
                rc = self._sh(job, [snapraid, what, *extra], timeout=timeout)
            finally:
                _state_set(running="")
            if rc == 0 and key:
                _state_set(**{key: int(time.time())})
            return rc

        fs = str(cfg.get("fs") or "xfs")
        if action == "create":
            data = [str(x) for x in (cfg.get("data") or []) if isinstance(x, str)]
            parity = [str(x) for x in (cfg.get("parity") or []) if isinstance(x, str)]
            policy = str(cfg.get("policy") or "mfs")
            if rec:
                say("refused: an array is here already; add to it, or destroy it first\n")
                return "failed", 66
            if fs not in FS or policy not in POLICIES:
                say(f"refused: a filesystem is one of {', '.join(FS)} and a policy one of {', '.join(POLICIES)}\n")
                return "failed", 64
            if not 1 <= len(data) <= MAX_DATA or not 1 <= len(parity) <= MAX_PARITY or len(set(data + parity)) != len(data) + len(parity):
                say(f"refused: an array takes 1 to {MAX_DATA} data disks and 1 or {MAX_PARITY} parity disks, each once; {len(data)} and {len(parity)} named\n")
                return "failed", 64
            if not all(disk_ok(n) for n in data + parity):
                return "failed", 65
            biggest = max(disks[n]["size_mb"] for n in data)
            small = [n for n in parity if disks[n]["size_mb"] < biggest]
            if small:
                say(f"refused: a parity disk is at least as large as the largest data disk; {', '.join(small)} is smaller\n")
                return "failed", 64
            # The tool first, before any disk is written: a missing one was
            # found after the first disk's table was already wiped.
            if not shutil.which("mkfs.xfs" if fs == "xfs" else "mkfs.btrfs"):
                say(f"refused: no mkfs for {fs} on this machine; install Storage on its Features section first\n")
                return "failed", 65
            stale_content()
            rec = {"policy": policy, "data": [], "parity": [], "made": int(time.time())}
            say(f"array create: {len(data)} data disk(s) as {fs}, {len(parity)} parity, {POLICIES[policy]}\n")
            done = []

            def stopped(n):
                # What was written before the stop, said, since no record of
                # an array holds it: those disks are formatted and in none.
                left = [x for x in done if x != n]
                if not left:
                    say("the array was not made; no disk was written before the stop\n")
                else:
                    one = len(left) == 1
                    say(f"the array was not made; {', '.join(left)} {'was' if one else 'were'} formatted already and "
                        f"{'is' if one else 'are'} in no array: create again with wipe to use {'it' if one else 'them'}\n")
                return "failed", 1
            for i, n in enumerate(data, 1):
                uuid = make_fs(n, fs, f"bb-d{i}")
                if not uuid:
                    return stopped(n)
                done.append(n)
                rec["data"].append({"slot": i, "id": by_id(n), "uuid": uuid, "fs": fs})
            for i, n in enumerate(parity, 1):
                uuid = make_fs(n, fs, f"bb-p{i}")
                if not uuid:
                    return stopped(n)
                done.append(n)
                rec["parity"].append({"slot": i, "id": by_id(n), "uuid": uuid, "fs": fs})
            settle()
            if not mount_all():
                return "failed", 1
            rc = run_snapraid("sync", key="last_sync", timeout=3600)
        elif action in ("add", "replace") and rec.get("adopted"):
            say("refused: an array taken over keeps its disks as the old system laid them out; adding or replacing a disk is not done on it yet\n")
            return "failed", 64
        elif action == "takeover":
            return self._array_takeover(job, cfg, rec, disks, snapraid, settle, run_snapraid)
        elif action == "moves":
            # A share's places changed (where its new files land, the
            # mover's from and to), the rest kept.
            if not rec.get("adopted"):
                say("refused: a share's places are for an array taken over, whose pools are in front of its data disks\n")
                return "failed", 66
            pools = adopted_pools()
            asked = moves_of(cfg.get("moves"), pools)
            if not asked or len(asked) != len(cfg.get("moves") or []):
                say(f"refused: each share's places are a pool in front of the data disks ({', '.join(pools) or 'none'}) or the array, the mover's two different\n")
                return "failed", 64
            kept = {m["share"]: m for m in moves_of(rec.get("moves"))}
            kept.update({m["share"]: m for m in asked})
            rec["moves"] = list(kept.values())[:MAX_MOVES]
            write_record(rec)
            for line in moves_said(asked):
                say(line + "\n")
            self._landing(say, asked, pools)
            rc = 0
        elif action == "mover":
            if not rec.get("adopted"):
                say("refused: the mover is for an array taken over, whose pools take new files first\n")
                return "failed", 66
            if _state().get("running"):
                say(f"refused: a {_state()['running']} is running on the array already; one at a time\n")
                return "failed", 75
            _state_set(running="mover")
            try:
                moves = moves_of(rec.get("moves"))
                rc = self._mover(job, moves)
                self._landing(say, moves, adopted_pools())
            finally:
                _state_set(running="")
            if rc == 0:
                _state_set(last_move=int(time.time()))
            self.hello_again("the mover ran")
            return ("succeeded", 0) if rc == 0 else ("failed", rc)
        elif action == "add":
            n = str(cfg.get("disk") or "")
            if not rec:
                say("refused: no array here yet\n")
                return "failed", 66
            if len(rec["data"]) >= MAX_DATA or not disk_ok(n):
                return "failed", 65
            fs = rec["data"][0].get("fs", "xfs") if rec["data"] else fs
            biggest = max(disks[n]["size_mb"], *(_df(mount_of("d", int(d["slot"])))[0] for d in rec["data"]))
            small = [p for p in rec["parity"] if _df(mount_of("p", int(p["slot"])))[0] < biggest]
            if small:
                say(f"refused: {n} is larger than the parity disk p{small[0]['slot']}; parity is at least as large as every data disk\n")
                return "failed", 64
            slot = max((int(d["slot"]) for d in rec["data"]), default=0) + 1
            say(f"array add: {n} as d{slot}, {fs}\n")
            uuid = make_fs(n, fs, f"bb-d{slot}")
            if not uuid:
                return "failed", 1
            rec["data"].append({"slot": slot, "id": by_id(n), "uuid": uuid, "fs": fs})
            settle()
            if not mount_all():
                return "failed", 1
            rc = run_snapraid("sync", key="last_sync")
        elif action == "replace":
            which, n = str(cfg.get("which") or ""), str(cfg.get("new") or "")
            m = SLOT_RE.fullmatch(which)
            if not rec or not m:
                say(f"refused: replace takes the slot to replace (d2, p1) and the new disk; {which or 'nothing'} named\n")
                return "failed", 64
            kind, slot = m.group(1), int(m.group(2))
            rows = rec["data"] if kind == "d" else rec["parity"]
            old = next((x for x in rows if int(x["slot"]) == slot), None)
            if not old:
                say(f"refused: the array has no {which}\n")
                return "failed", 66
            if not disk_ok(n):
                return "failed", 65
            if kind == "d":
                biggest = max(disks[n]["size_mb"], *(_df(mount_of("d", int(d["slot"])))[0] for d in rec["data"] if int(d["slot"]) != slot))
                if any(_df(mount_of("p", int(p["slot"])))[0] < biggest for p in rec["parity"]):
                    say(f"refused: {n} is larger than a parity disk; parity is at least as large as every data disk\n")
                    return "failed", 64
            else:
                biggest = max((_df(mount_of("d", int(d["slot"])))[0] for d in rec["data"]), default=0)
                if disks[n]["size_mb"] < biggest:
                    say(f"refused: {n} is smaller than the largest data disk, which a parity disk may not be\n")
                    return "failed", 64
            mnt = mount_of(kind, slot)
            if os.path.ismount(mnt):
                self._sh(job, ["umount", "-l", mnt], timeout=60)
            say(f"array replace {which}: {old.get('id')} with {n} ({by_id(n)})\n")
            uuid = make_fs(n, old.get("fs", fs), f"bb-{which}")
            if not uuid:
                return "failed", 1
            old.update(id=by_id(n), uuid=uuid)
            settle()
            if not mount_all():
                return "failed", 1
            if kind == "d":
                say(f"rebuilding d{slot} from parity: the array is readable meanwhile, slower\n")
                rc = run_snapraid("fix", "-d", f"d{slot}")
                if rc == 0:
                    rc = run_snapraid("sync", key="last_sync")
            else:
                say(f"rebuilding parity on p{slot}: the array is unprotected until this ends\n")
                rc = run_snapraid("sync", "-F", key="last_sync")
        elif action == "verify":
            # Check parity (R163 step 15): every block of every data disk
            # read back against the parity, not the scrub's sampled part;
            # what differs is corrected only when asked, its count said first.
            if not rec:
                say("refused: no array here yet\n")
                return "failed", 66
            if _state().get("running"):
                say(f"refused: a {_state()['running']} is running on the array already; one at a time\n")
                return "failed", 75
            missing = unmounted_slots(rec)
            if missing:
                say(f"refused: {', '.join(missing)} {'is' if len(missing) == 1 else 'are'} not mounted: nothing is read or corrected "
                    "until every disk of the array is\n")
                return "failed", 65
            _state_set(running="verify", progress="")
            last = [0.0]

            def progressed(pct, rate):
                if time.time() - last[0] >= 10 or pct >= 100:
                    last[0] = time.time()
                    _state_set(progress=f"{pct}%" + (f", {rate} MB/s" if rate else ""))
            try:
                say("reading every block of every data disk back against the parity: hours for a large array\n")
                with tempfile.TemporaryDirectory() as td:
                    log1 = os.path.join(td, "scrub.log")
                    rc, _text = run_watched([snapraid, "scrub", "-p", "full", "-l", log1], say, progressed)
                    c, files = scrub_log(log1)
                    found = c.get("data", 0) + c.get("io", 0) + c.get("file", 0)
                    fixed = unfixed = 0
                    if found and cfg.get("correct") is True:
                        say(f"{found} block{'' if found == 1 else 's'} differ from the parity: correcting them\n")
                        _state_set(running="fix", progress="")
                        # SnapRAID marks a block whose parity was wrong for
                        # -e; a file whose own hash failed it names in its
                        # log, and is fixed by name.
                        runs = [[snapraid, "-e", "fix"]]
                        plain = [f for f in files if not re.search(r"[*?\[\]\\]", f)]
                        if files and len(plain) == len(files) and len(files) <= 200:
                            runs.append([snapraid, "fix", *[x for f in files for x in ("-f", "/" + f)]])
                        elif files:
                            runs.append([snapraid, "fix"])
                        for k, argv in enumerate(runs):
                            logk = os.path.join(td, f"fix{k}.log")
                            run_watched([*argv[:1], "-l", logk, *argv[1:]], say, progressed)
                            ck, _f = scrub_log(logk)
                            fixed += ck.get("recovered", 0)
                            unfixed += ck.get("unrecoverable", 0)
                        unfixed = max(unfixed, found - fixed) if not fixed and not unfixed else unfixed
                    elif found:
                        say(f"{found} block{'' if found == 1 else 's'} differ from the parity; Correct what differs was not ticked, so nothing was written\n")
                    if found:
                        rc = 0
                _state_set(last_verify=int(time.time()), verify={"at": int(time.time()), "ok": rc == 0, "found": found,
                                                                  "fixed": fixed, "unfixed": unfixed,
                                                                  "corrected": cfg.get("correct") is True})
            finally:
                _state_set(running="", progress="")
        elif action in ("sync", "scrub", "check"):
            if not rec:
                say("refused: no array here yet\n")
                return "failed", 66
            if _state().get("running"):
                say(f"refused: a {_state()['running']} is running on the array already; one at a time\n")
                return "failed", 75
            if action == "check":
                rc = run_snapraid("status", key="last_check", timeout=3600)
                _state_set(status=" ".join(job.text().splitlines()[-3:])[:400] if hasattr(job, "text") else "")
            elif action == "sync":
                rc = run_snapraid("sync", key="last_sync")
            else:
                rc = run_snapraid("scrub", key="last_scrub")
        else:
            if not rec:
                say("refused: no array here yet\n")
                return "failed", 66
            if str(cfg.get("confirm") or "") != "array":
                say("refused: destroying the array takes the word array again as the confirmation\n")
                return "failed", 64
            # SnapRAID's content files go with it, on the system and on each
            # data disk, or the next array's first sync reads them as this
            # one's and refuses its disks as changed (B704); on a disk taken
            # over from another system they are what this machine added.
            for path in [_env("BB_SNAPRAID_CONTENT", CONTENT)] + [os.path.join(slot_mount("d", d), ".snapraid.content") for d in rec.get("data") or []]:
                for p_ in (path, path + ".tmp", path + ".lock"):
                    with contextlib.suppress(OSError):
                        os.unlink(p_)
            if rec.get("adopted"):
                # Its data disks and /mnt/user stay the adoption's, writable;
                # the parity disk is unmounted and its SnapRAID parity forgotten.
                say("array destroy: SnapRAID's parity forgotten and its disk unmounted; the data disks stay where they are, as adopted\n")
            else:
                say("array destroy: unmounted and forgotten; every data disk keeps its files, readable on any Linux\n")
                if os.path.ismount(MOUNT):
                    self._sh(job, ["umount", "-l", MOUNT], timeout=60)
            for kind, key in (("p", "parity"),) if rec.get("adopted") else (("d", "data"), ("p", "parity")):
                for x in rec.get(key) or []:
                    m = slot_mount(kind, x)
                    if os.path.ismount(m):
                        self._sh(job, ["umount", "-l", m], timeout=60)
            if rec.get("adopted"):
                from . import adopt
                arec = adopt.read_record()
                if arec:
                    arec.pop("taken", None)
                    adopt.write_record(arec)
            rec = {}
            write_fstab(rec)
            for path in (_env("BB_ARRAY_RECORD", RECORD), _env("BB_SNAPRAID_CONF", SNAPRAID_CONF), _env("BB_ARRAY_STATE", STATE)):
                try:
                    os.unlink(path)
                except OSError:
                    pass
            rc = 0
        self.hello_again(f"the array: {action}")
        return ("succeeded", 0) if rc == 0 else ("failed", rc)

