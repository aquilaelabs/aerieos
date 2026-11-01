"""An array and pools another NAS made, taken as they are (R163 step 8): a
disk-per-filesystem array's data disks each mounted with the filesystem it
already holds, its parity disk left alone, its pools mounted writable, and
its paths kept (/mnt/diskN, /mnt/POOL, the merged /mnt/user and /mnt/user0)
so the containers and VMs that point at them find their files where they
were.

Nothing here makes, wipes, partitions or upgrades anything: there is no
mkfs, wipefs, partition tool or zpool upgrade in this module, and a unit test
holds that (the way back to the old system, R163 step 5). The data disks are
read-only unless the person picked writable, since a write the old system's
parity did not see leaves that parity stale until a parity sync on the way
back; the pools carry no such parity, so they are writable either way. A ZFS
pool is imported without -f and never upgraded; one the old system did not export
is refused with the reason, not forced.

What the person picked is a record (/etc/builderbot/adopted.json); the
fstab lines are rendered from it under their own mark, the merged trees by
mergerfs with the read-only disks marked so in the branch list, so a new
file lands on a pool. Release unmounts all of it and forgets it, every disk
as it was.
"""
import json
import os
import re
import shutil
import subprocess
import time
from typing import Callable

RECORD = "/etc/builderbot/adopted.json"
FSTAB = "/etc/fstab"
MARK = "# builderbot-adopted"
FS = ("xfs", "btrfs", "zfs")
ACTIONS = ("dry", "adopt", "release")
DATA_RE = re.compile(r"disk([1-9][0-9]?)")
POOL_RE = re.compile(r"[a-z][a-z0-9_-]{0,31}")
# Names a pool may not take: the merged trees under /mnt, and BuilderBot's.
NOT_POOLS = {"user", "user0", "disks", "remotes", "addons", "rootshare", "array", "parity", "cache-mover"}
# What blkid calls each filesystem.
BLK = {"xfs": "xfs", "btrfs": "btrfs", "zfs": "zfs_member"}


def _env(k, d):
    return os.environ.get(k) or d


def blkid(name):
    """{TYPE, UUID, LABEL, ...} of /dev/NAME as blkid reads it; {} for none."""
    try:
        out = subprocess.run(["blkid", "-o", "export", f"/dev/{name}"], capture_output=True, text=True, timeout=30, check=False).stdout
    except (OSError, subprocess.SubprocessError):
        return {}
    return dict(ln.split("=", 1) for ln in out.splitlines() if "=" in ln)


def find_disk(disks, disk_id):
    """The disk the old system named `disk_id` (its MODEL_SERIAL), by the
    /dev/disk/by-id link it ends or the serial it ends with; None."""
    uid = str(disk_id or "").strip()
    if not uid:
        return None
    for d in disks:
        link = os.path.basename(str(d.get("by_id") or ""))
        if link and (link == uid or link.endswith("-" + uid) or link.endswith("_" + uid)):
            return d
    for d in disks:
        serial = str(d.get("serial") or "").strip()
        if serial and len(serial) >= 4 and (uid == serial or uid.endswith("_" + serial)):
            return d
    return None


def holding(d, fs, blk):
    """(device name, blkid row) of the part of disk `d` that holds `fs`:
    the data is on the first partition, a whole-disk filesystem is
    taken as well; (None, {}) when nothing on it does."""
    for name in [p.get("name") for p in d.get("parts") or []] + [d.get("name")]:
        if not name:
            continue
        row = blk(name)
        if row.get("TYPE") == BLK.get(fs):
            return name, row
    return None, {}


def plan(want, disks, blk=blkid):
    """What adopting `want` would do on this machine, and what stands in its
    way: {"mounts": [...], "zfs": [...], "merged": {...}, "parity": [...],
    "said": [lines], "refused": [lines]}. Nothing is changed by it.

    `want` is the stick's plan as the Storage page hands it on: {"data":
    [{"slot": "disk1", "id", "fs"}], "parity": [{"slot", "id"}], "pools":
    [{"name", "fs", "uuid", "disk_id"}], "writable": bool}."""
    out = {"mounts": [], "zfs": [], "merged": {}, "parity": [], "said": [], "refused": []}
    # Each device read once, however many questions are asked of it.
    memo, read = {}, blk
    blk = lambda n: memo[n] if n in memo else memo.setdefault(n, read(n))    # noqa: E731
    writable = want.get("writable") is True
    no = out["refused"].append
    say = out["said"].append
    seen = set()

    def usable(d, what):
        if d is None:
            no(f"{what} is not on this machine (no disk with that serial)")
            return False
        if d["name"] in seen:
            no(f"{what} is {d['name']}, named twice")
            return False
        seen.add(d["name"])
        if d.get("system"):
            no(f"{what} is {d['name']}, this machine's system disk")
            return False
        if d.get("mounted"):
            no(f"{what} is {d['name']}, which has something mounted on it already")
            return False
        return True

    data = []
    for x in want.get("data") or []:
        slot = str(x.get("slot") or "")
        m = DATA_RE.fullmatch(slot)
        fs = str(x.get("fs") or "")
        what = f"{slot or 'a data disk'} ({x.get('id') or 'no id'})"
        if not m:
            no(f"{what}: a data disk's slot is disk1 to disk99")
            continue
        if fs not in FS:
            no(f"{what}: its filesystem is {fs or 'not said'}; XFS, btrfs and ZFS are taken"
               + (" (an encrypted disk needs its key, which is not asked for yet)" if "luks" in fs else ""))
            continue
        d = find_disk(disks, x.get("id"))
        if not usable(d, what):
            continue
        part, row = holding(d, fs, blk)
        if not part:
            no(f"{what} is {d['name']}, and nothing on it is the {fs} the old system named: it is left alone")
            continue
        data.append(slot)
        where = f"/mnt/{slot}"
        if fs == "zfs":
            pool = row.get("LABEL") or slot
            out["zfs"].append({"pool": pool, "where": where, "readonly": not writable, "slot": slot})
            say(f"{slot}: {d['name']} ({d.get('model') or 'disk'}), the ZFS pool {pool} imported{' read-only' if not writable else ''} at {where}")
        else:
            uuid = row.get("UUID", "")
            if not uuid:
                no(f"{what}: {part} gives no filesystem UUID to mount it by")
                continue
            out["mounts"].append({"what": f"UUID={uuid}", "where": where, "fs": fs, "ro": not writable, "dev": part})
            say(f"{slot}: {d['name']} ({d.get('model') or 'disk'}), its {fs} on {part} at {where}, {'read-only' if not writable else 'writable'}")

    for x in want.get("parity") or []:
        d = find_disk(disks, x.get("id"))
        what = f"{x.get('slot') or 'parity'} ({x.get('id') or 'no id'})"
        if d is None:
            say(f"{what}: not on this machine; nothing is done with parity in any case")
            continue
        seen.add(d["name"])
        out["parity"].append({"slot": str(x.get("slot") or "parity"), "dev": d["name"]})
        say(f"{what}: {d['name']}, left alone: never mounted or written")

    pools = []
    for x in want.get("pools") or []:
        name, fs, uuid = str(x.get("name") or ""), str(x.get("fs") or ""), str(x.get("uuid") or "")
        what = f"the pool {name or '(no name)'}"
        if not POOL_RE.fullmatch(name) or name in NOT_POOLS or DATA_RE.fullmatch(name):
            no(f"{what}: not a name a pool can be mounted under here")
            continue
        if fs not in FS:
            no(f"{what}: its filesystem is {fs or 'not said'}; XFS, btrfs and ZFS are taken")
            continue
        where = f"/mnt/{name}"
        if fs == "zfs":
            pools.append(name)
            out["zfs"].append({"pool": name, "where": where, "readonly": False, "slot": name})
            say(f"{name}: the ZFS pool imported as it is at {where}, writable")
            continue
        # A pool may span disks (btrfs), so it is found by its filesystem's
        # UUID on any of them; the plan's disk id names one of them.
        hit = None
        for d in disks:
            for n in [p.get("name") for p in d.get("parts") or []] + [d.get("name")]:
                if n and blk(n).get("UUID") == uuid and blk(n).get("TYPE") == BLK[fs]:
                    hit = (d, n)
                    break
            if hit:
                break
        if not uuid or not hit:
            no(f"{what}: no disk here holds its {fs} (UUID {uuid or 'not said'})")
            continue
        d, part = hit
        if d.get("system") or d.get("mounted"):
            no(f"{what} is on {d['name']}, which is {'the system disk' if d.get('system') else 'mounted already'}")
            continue
        pools.append(name)
        out["mounts"].append({"what": f"UUID={uuid}", "where": where, "fs": fs, "ro": False, "dev": part})
        say(f"{name}: {fs} on {part} at {where}, writable")

    disks_ = [f"/mnt/{s}" for s in sorted(data, key=lambda s: int(s[4:]))]
    tag = "RO" if not writable else "RW"
    if disks_ or pools:
        out["merged"]["/mnt/user"] = [f"/mnt/{p}=RW" for p in pools] + [f"{p}={tag}" for p in disks_]
        parts = ([f"the pools ({', '.join(pools)})"] if pools else []) \
            + ([f"the data disks{' (read-only: new files land on a pool)' if not writable else ''}"] if disks_ else [])
        say("/mnt/user: " + " and ".join(parts) + " merged, as the old system's was")
    if disks_:
        out["merged"]["/mnt/user0"] = [f"{p}={tag}" for p in disks_]
        say("/mnt/user0: the data disks alone, as the old system's was")
    if not writable and disks_:
        say("The old system's parity stays good: nothing on a data disk is written while they are read-only")
    elif disks_:
        say("Writable: a file written to a data disk here is one the old system's parity did not see; going back to it then "
            "takes a parity sync, which leaves the array unprotected until it ends")
    return out


def render_fstab(p):
    """The fstab lines of plan `p` under this module's mark: each disk or
    pool by UUID (nofail, so a missing one never holds the boot), then the
    merged trees, which wait for their branches."""
    lines = []
    for m in p.get("mounts") or []:
        opts = ("ro," if m.get("ro") else "") + "defaults,nofail,noatime"
        lines.append(f"{m['what']} {m['where']} {m['fs']} {opts} 0 0 {MARK}\n")
    for where, branches in (p.get("merged") or {}).items():
        create = "ff" if where == "/mnt/user" else "mfs"
        req = ",".join(f"x-systemd.requires-mounts-for={b.split('=')[0]}" for b in branches)
        lines.append(f"{':'.join(branches)} {where} fuse.mergerfs defaults,nofail,allow_other,use_ino,cache.files=off,"
                     f"dropcacheonclose=true,category.create={create},moveonenospc=true,minfreespace=10G,fsname=adopted{where[5:]},{req} 0 0 {MARK}\n")
    return "".join(lines)


def write_fstab(p):
    path = _env("BB_ADOPT_FSTAB", FSTAB)
    try:
        with open(path, encoding="utf-8") as f:
            kept = [ln for ln in f.read().splitlines(True) if not ln.rstrip().endswith(MARK)]
    except OSError:
        kept = []
    text = "".join(kept)
    if text and not text.endswith("\n"):
        text += "\n"
    with open(path + ".new", "w", encoding="utf-8") as f:
        f.write(text + (render_fstab(p) if p else ""))
    os.chmod(path + ".new", 0o644)
    os.replace(path + ".new", path)


def read_record():
    try:
        with open(_env("BB_ADOPT_RECORD", RECORD), encoding="utf-8") as f:
            rec = json.load(f)
        return rec if isinstance(rec, dict) else {}
    except (OSError, ValueError):
        return {}


def write_record(rec):
    path = _env("BB_ADOPT_RECORD", RECORD)
    if not rec:
        try:
            os.unlink(path)
        except OSError:
            pass
        return
    os.makedirs(os.path.dirname(path), exist_ok=True)
    with open(path + ".new", "w", encoding="utf-8") as f:
        json.dump(rec, f, indent=1)
    os.replace(path + ".new", path)


def adopted_now():
    """For the census: what was adopted and whether each piece is mounted
    now; {} where nothing was."""
    rec = read_record()
    p = rec.get("plan") or {}
    if not p:
        return {}
    rows = [{"where": m["where"], "fs": m["fs"], "ro": bool(m.get("ro")), "mounted": os.path.ismount(m["where"])}
            for m in p.get("mounts") or []]
    rows += [{"where": z["where"], "fs": "zfs", "ro": bool(z.get("readonly")), "mounted": os.path.ismount(z["where"])}
             for z in p.get("zfs") or []]
    return {"from": str(rec.get("from") or "adopted")[:16], "writable": rec.get("writable") is True, "at": int(rec.get("at") or 0),
            "mounts": rows[:64], "merged": {w: os.path.ismount(w) for w in (p.get("merged") or {})},
            "parity": [str(x.get("dev") or "") for x in p.get("parity") or []][:2]}


class AdoptMixin:
    """The agent's storage-adopt job: one of the parts class Agent is made of."""
    _sh: "Callable[..., int]"

    def adopt_pass(self):
        """Once a minute: an adopted disk or pool whose mount is missing (it
        was slow to appear at boot) mounted again, then the merged trees."""
        rec = read_record()
        p = rec.get("plan") or {}
        if not p or os.geteuid() != 0:
            return
        for z in p.get("zfs") or []:
            if not os.path.ismount(z["where"]):
                self._zfs_import(None, z)
        for m in p.get("mounts") or []:
            if not os.path.ismount(m["where"]) and os.path.isdir(m["where"]):
                subprocess.run(["mount", m["where"]], capture_output=True, timeout=60, check=False)
        for where in p.get("merged") or {}:
            if not os.path.ismount(where) and os.path.isdir(where):
                subprocess.run(["mount", where], capture_output=True, timeout=60, check=False)

    def _zfs_import(self, job, z):
        """Import one pool as it is: no -f, never upgraded; read-only where
        asked. The rc."""
        argv = ["zpool", "import", "-o", "cachefile=none"] + (["-o", "readonly=on"] if z.get("readonly") else []) + [z["pool"]]
        if job is None:
            return subprocess.run(argv, capture_output=True, timeout=120, check=False).returncode
        return self._sh(job, argv, timeout=120)

    def _apply_storage_adopt(self, job, cfg):
        say = job.say
        action = str(cfg.get("adopt") or "")
        if action not in ACTIONS:
            say(f"refused: {action or 'no action'} is not one of {', '.join(ACTIONS)}\n")
            return "failed", 64
        if action != "dry" and os.geteuid() != 0:
            say("refused: adopting disks mounts them, which this agent cannot as it is not root\n")
            return "failed", 77
        rec = read_record()
        if action == "release":
            p = rec.get("plan") or {}
            if not p:
                say("nothing is adopted here\n")
                return "succeeded", 0
            for where in p.get("merged") or {}:
                if os.path.ismount(where):
                    self._sh(job, ["umount", where], timeout=60)
            for m in p.get("mounts") or []:
                if os.path.ismount(m["where"]):
                    self._sh(job, ["umount", m["where"]], timeout=60)
            for z in p.get("zfs") or []:
                self._sh(job, ["zpool", "export", z["pool"]], timeout=120)
            busy = [w for w in [*(p.get("merged") or {}), *(m["where"] for m in p.get("mounts") or [])] if os.path.ismount(w)]
            if busy:
                say(f"still mounted, so nothing was forgotten: {', '.join(busy)} (something has a file open there)\n")
                return "failed", 1
            write_fstab({})
            write_record({})
            say("released: every adopted disk and pool unmounted and forgotten, each as it was\n")
            return "succeeded", 0
        if rec.get("plan") and action == "adopt":
            say("refused: disks are adopted here already; release them first\n")
            return "failed", 66
        from .disks import disks_now
        want = cfg.get("want") if isinstance(cfg.get("want"), dict) else {}
        p = plan(want, disks_now(smart=False))
        for line in p["said"]:
            say(line + "\n")
        for line in p["refused"]:
            say("refused: " + line + "\n")
        if action == "dry":
            say("a dry run: nothing was mounted\n" if not p["refused"] else "a dry run: what is refused above stops the adoption\n")
            return ("succeeded", 0) if not p["refused"] else ("failed", 65)
        if p["refused"]:
            say("nothing was mounted\n")
            return "failed", 65
        if p.get("merged") and not shutil.which("mergerfs"):
            say("refused: no mergerfs on this machine for /mnt/user; install Storage on its Features section first\n")
            return "failed", 65
        if p.get("zfs") and not shutil.which("zpool"):
            say("refused: a ZFS pool or disk is named and this machine has no zpool; install Storage on its Features section first\n")
            return "failed", 65
        for m in [*p["mounts"], *({"where": w} for w in p["merged"])]:
            os.makedirs(m["where"], exist_ok=True)
        write_fstab(p)
        write_record({"plan": p, "writable": want.get("writable") is True, "from": str(want.get("from") or "adopted")[:16],
                      "at": int(time.time())})
        failed = []
        for z in p["zfs"]:
            if self._zfs_import(job, z) != 0:
                failed.append(z["where"])
                say(f"{z['pool']} was not imported (above): a pool the old system did not export says it was in use on another system, "
                    "and it is not forced\n")
        for m in p["mounts"]:
            if self._sh(job, ["mount", m["where"]], timeout=60) != 0:
                failed.append(m["where"])
        for where in p["merged"]:
            if self._sh(job, ["mount", where], timeout=60) != 0:
                failed.append(where)
        if failed:
            say(f"adopted, but not mounted yet: {', '.join(failed)}; tried again every minute, and Release undoes all of it\n")
            return "failed", 1
        say("adopted: every disk and pool mounted as it was, its paths kept\n")
        return "succeeded", 0
