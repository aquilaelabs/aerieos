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
import tempfile
import time
import xml.etree.ElementTree as ET
from typing import Callable

RECORD = "/etc/builderbot/adopted.json"
FSTAB = "/etc/fstab"
MARK = "# builderbot-adopted"
FS = ("xfs", "btrfs", "zfs")
ACTIONS = ("dry", "adopt", "release", "read-apps", "define-vms", "docker-network", "vm")
# What may be done to an adopted VM: the VMs page acts only on its own.
VM_OPS = {"start": ["start"], "shutdown": ["shutdown"], "off": ["destroy"],
          "autostart-on": ["autostart"], "autostart-off": ["autostart", "--disable"]}
DATA_RE = re.compile(r"disk([1-9][0-9]?)")
POOL_RE = re.compile(r"[a-z][a-z0-9_-]{0,31}")
# Names a pool may not take: the merged trees under /mnt, and AerieOS's.
NOT_POOLS = {"user", "user0", "disks", "remotes", "addons", "rootshare", "array", "parity", "other", "cache-mover"}
# What a read-only mount adds so the filesystem writes nothing at all.
NO_REPLAY = {"xfs": "norecovery", "btrfs": "rescue=nologreplay"}
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


def blkid_file(path):
    """blkid's word on an image file (its TYPE); {} for none."""
    try:
        out = subprocess.run(["blkid", "-o", "export", path], capture_output=True, text=True, timeout=30, check=False).stdout
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


def mnt():
    """Where the old paths go: /mnt, or under BB_ADOPT_ROOT for a proof
    that must not touch the machine's own."""
    return _env("BB_ADOPT_ROOT", "") + "/mnt"


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

    def free(where, what):
        # Something of this machine's at the old path already (a pool of its
        # own by the same name): the old system's is not laid over it.
        if os.path.ismount(where):
            no(f"{what}: {where} has something mounted on it already on this machine")
            return False
        return True

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
        where = f"{mnt()}/{slot}"
        if not free(where, what):
            continue
        data.append(slot)
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
        where = f"{mnt()}/{name}"
        if not free(where, what):
            continue
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

    disks_ = [f"{mnt()}/{s}" for s in sorted(data, key=lambda s: int(s[4:]))]
    tag = "RO" if not writable else "RW"
    if disks_ or pools:
        out["merged"][f"{mnt()}/user"] = [f"{mnt()}/{p}=RW" for p in pools] + [f"{p}={tag}" for p in disks_]
        parts = ([f"the pools ({', '.join(pools)})"] if pools else []) \
            + ([f"the data disks{' (read-only: new files land on a pool)' if not writable else ''}"] if disks_ else [])
        say(f"{mnt()}/user: " + " and ".join(parts) + " merged, as the old system's was")
    if disks_:
        out["merged"][f"{mnt()}/user0"] = [f"{p}={tag}" for p in disks_]
        say(f"{mnt()}/user0: the data disks alone, as the old system's was")
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
        # Read-only is not enough on its own: XFS replays its log and btrfs
        # its log tree even on a read-only mount, which writes the disk
        # behind the old parity's back (the proof of 1 Nov caught an XFS
        # image changed by a plain ro mount). These write nothing; a disk
        # whose journal needs replaying then refuses to mount and says so.
        opts = (f"ro,{NO_REPLAY.get(m['fs'], '')}," if m.get("ro") else "") + "defaults,nofail,noatime"
        opts = opts.replace(",,", ",")
        lines.append(f"{m['what']} {m['where']} {m['fs']} {opts} 0 0 {MARK}\n")
    for where, branches in (p.get("merged") or {}).items():
        create = "ff" if where.endswith("/user") else "mfs"
        req = ",".join(f"x-systemd.requires-mounts-for={b.split('=')[0]}" for b in branches)
        lines.append(f"{':'.join(branches)} {where} fuse.mergerfs defaults,nofail,allow_other,use_ino,cache.files=off,"
                     f"dropcacheonclose=true,category.create={create},moveonenospc=true,minfreespace=10G,fsname=adopted-{os.path.basename(where)},{req} 0 0 {MARK}\n")
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


# ---- the containers and VMs another system ran (R163 steps 10 and 11) ----
# Its Docker and libvirt keep their state in image files on the disks just
# adopted; each is opened read-only (loop, no journal replayed) to read what
# ran: the containers set to start with the machine and the exact image each
# ran by digest, and each VM's definition, whether it starts with the
# machine and its UEFI variables. Nothing in either file is changed, and
# neither is ever run.
APPS = "/var/lib/builderbot/adopted-apps.json"
NVRAM_KEPT = "/var/lib/builderbot/adopted-nvram"
NVRAM_DIR = "/var/lib/libvirt/qemu/nvram"
VM_NAME_RE = re.compile(r"[A-Za-z0-9][A-Za-z0-9 ._-]{0,63}")
NET_RE = re.compile(r"[A-Za-z0-9][A-Za-z0-9._-]{0,31}")
CIDR_RE = re.compile(r"\d{1,3}(\.\d{1,3}){3}/\d{1,2}")
IP_RE = re.compile(r"\d{1,3}(\.\d{1,3}){3}")


def read_docker_root(root, autostart_name=""):
    """What a Docker data directory says ran: {"autostart": [names],
    "containers": {name: {"image", "digest"}}}. The digest is the image's
    repo@sha256 the daemon pulled, so the same image runs again."""
    out = {"autostart": [], "containers": {}}
    if autostart_name and "/" not in autostart_name:
        try:
            with open(os.path.join(root, autostart_name), encoding="utf-8") as f:
                out["autostart"] = [ln.split()[0] for ln in f if ln.strip()][:256]
        except OSError:
            pass
    digests = {}
    for drv in sorted(os.listdir(os.path.join(root, "image"))) if os.path.isdir(os.path.join(root, "image")) else []:
        try:
            with open(os.path.join(root, "image", drv, "repositories.json"), encoding="utf-8") as f:
                repos = json.load(f).get("Repositories") or {}
        except (OSError, ValueError):
            continue
        for refs in repos.values():
            for ref, iid in (refs or {}).items():
                if "@sha256:" in ref:
                    digests.setdefault(iid, ref)
    cdir = os.path.join(root, "containers")
    for cid in sorted(os.listdir(cdir)) if os.path.isdir(cdir) else []:
        try:
            with open(os.path.join(cdir, cid, "config.v2.json"), encoding="utf-8") as f:
                c = json.load(f)
        except (OSError, ValueError):
            continue
        name = str(c.get("Name") or "").lstrip("/")
        if not name:
            continue
        out["containers"][name] = {"image": str((c.get("Config") or {}).get("Image") or ""),
                                   "digest": digests.get(str(c.get("Image") or ""), "")}
    return out


def read_libvirt_root(root):
    """What a libvirt configuration directory defines: [{"name", "xml",
    "autostart", "nvram": the variables file here or ""}]."""
    out = []
    q = os.path.join(root, "qemu")
    for fn in sorted(os.listdir(q)) if os.path.isdir(q) else []:
        if not fn.endswith(".xml"):
            continue
        try:
            with open(os.path.join(q, fn), encoding="utf-8") as f:
                xml = f.read()
            dom = ET.fromstring(xml)
        except (OSError, ET.ParseError):
            continue
        name = (dom.findtext("name") or "").strip()
        if not VM_NAME_RE.fullmatch(name):
            continue
        nv = (dom.findtext("os/nvram") or "").strip()
        kept = os.path.join(q, "nvram", os.path.basename(nv)) if nv else ""
        out.append({"name": name, "xml": xml, "autostart": os.path.exists(os.path.join(q, "autostart", fn)),
                    "nvram": kept if kept and os.path.isfile(kept) else ""})
    return out[:64]


def rewrite_domain(xml, emulator, ovmf_pair, nvram_path, lan):
    """A domain another system defined, as this machine runs it: its own
    QEMU, its own UEFI firmware and a variables file of its own, and an
    interface on a bridge put on the LAN through `lan` (macvtap, as this
    machine's own VMs are). Its disks, passthrough and the rest kept as
    they were. (xml, [what changed])."""
    dom = ET.fromstring(xml)
    said = []
    dev = dom.find("devices")
    em = dev.find("emulator") if dev is not None else None
    if em is not None and emulator and (em.text or "").strip() != emulator:
        said.append(f"QEMU is {emulator} here")
        em.text = emulator
    loader = dom.find("os/loader")
    if loader is not None and ovmf_pair:
        loader.text = ovmf_pair[0]
        loader.set("readonly", "yes")
        loader.set("type", "pflash")
        loader.attrib.pop("secure", None)
        said.append(f"UEFI from {ovmf_pair[0]}")
        nv = dom.find("os/nvram")
        if nv is None:
            nv = ET.SubElement(dom.find("os"), "nvram")
        nv.text = nvram_path
        nv.set("template", ovmf_pair[1])
    for iface in (dev.findall("interface") if dev is not None else []):
        if iface.get("type") == "bridge" and lan:
            src = iface.find("source")
            br = src.get("bridge", "") if src is not None else ""
            iface.set("type", "direct")
            if src is None:
                src = ET.SubElement(iface, "source")
            src.attrib.clear()
            src.set("dev", lan)
            src.set("mode", "bridge")
            said.append(f"its network {br or 'bridge'} is the LAN through {lan} (this machine cannot reach it, other machines can)")
    return ET.tostring(dom, encoding="unicode"), said


def read_apps():
    try:
        with open(_env("BB_ADOPT_APPS", APPS), encoding="utf-8") as f:
            d = json.load(f)
        return d if isinstance(d, dict) else {}
    except (OSError, ValueError):
        return {}


def apps_now():
    """For the census: what the image files said, without the definitions."""
    d = read_apps()
    if not d:
        return {}
    dk = d.get("docker") or {}
    return {"docker": {"autostart": list(dk.get("autostart") or [])[:256],
                       "digests": {k: str(v.get("digest") or "")[:200] for k, v in list((dk.get("containers") or {}).items())[:256]}},
            "vms": [{"name": v["name"], "autostart": bool(v.get("autostart")), "nvram": bool(v.get("nvram"))} for v in d.get("vms") or []][:64],
            "said": [str(x)[:300] for x in d.get("said") or []][:16]}


class AdoptMixin:
    """The agent's storage-adopt job: one of the parts class Agent is made of."""
    _sh: "Callable[..., int]"
    hello_again: "Callable[..., None]"

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
                subprocess.run(["mount", "-T", _env("BB_ADOPT_FSTAB", FSTAB), m["where"]], capture_output=True, timeout=60, check=False)
        for where in p.get("merged") or {}:
            if not os.path.ismount(where) and os.path.isdir(where):
                subprocess.run(["mount", "-T", _env("BB_ADOPT_FSTAB", FSTAB), where], capture_output=True, timeout=60, check=False)

    def _zfs_import(self, job, z):
        """Import one pool as it is: no -f, never upgraded; read-only where
        asked. The rc."""
        argv = ["zpool", "import", "-o", "cachefile=none"] + (["-o", "readonly=on"] if z.get("readonly") else []) + [z["pool"]]
        if job is None:
            return subprocess.run(argv, capture_output=True, timeout=120, check=False).returncode
        return self._sh(job, argv, timeout=120)

    def _mount_image(self, job, img):
        """An image file opened read-only at a folder of its own, its journal
        not replayed: the folder, or "" with why said."""
        if not (img.startswith("/mnt/") and ".." not in img.split("/") and os.path.isfile(img)):
            job.say(f"{img or 'no image'} is not a file under /mnt here\n")
            return ""
        fs = blkid_file(img).get("TYPE", "")
        if fs not in ("btrfs", "xfs", "ext4"):
            job.say(f"{img} holds {fs or 'nothing blkid knows'}, not the btrfs, XFS or ext4 an image file is\n")
            return ""
        d = tempfile.mkdtemp(prefix="bb-adopt-")
        opts = "loop,ro," + {"xfs": "norecovery", "btrfs": "rescue=nologreplay", "ext4": "noload"}[fs]
        if self._sh(job, ["mount", "-o", opts, img, d], timeout=60) != 0:
            os.rmdir(d)
            return ""
        return d

    def _unmount_image(self, job, d):
        if d and os.path.ismount(d):
            self._sh(job, ["umount", d], timeout=60)
        if d:
            try:
                os.rmdir(d)
            except OSError:
                pass

    def _apply_apps(self, job, action, cfg):
        """read-apps, define-vms and docker-network (R163 steps 10, 11)."""
        say = job.say
        if action == "read-apps":
            got, said = {}, []
            dk = cfg.get("docker") if isinstance(cfg.get("docker"), dict) else {}
            vm = cfg.get("vms") if isinstance(cfg.get("vms"), dict) else {}
            for what, spec in (("docker", dk), ("vms", vm)):
                img = str(spec.get("image") or "")
                if not img:
                    continue
                d = self._mount_image(job, img)
                if not d:
                    said.append(f"{what}: {img} was not read (above)")
                    continue
                try:
                    if what == "docker":
                        got["docker"] = read_docker_root(d, str(spec.get("autostart_file") or ""))
                        n = len(got["docker"]["containers"])
                        said.append(f"Docker: {n} container{'' if n == 1 else 's'} ran, {len(got['docker']['autostart'])} started with the machine")
                    else:
                        doms = read_libvirt_root(d)
                        os.makedirs(NVRAM_KEPT, exist_ok=True)
                        for x in doms:
                            if x["nvram"]:
                                keep = os.path.join(NVRAM_KEPT, re.sub(r"[^A-Za-z0-9._-]", "_", x["name"]) + ".fd")
                                shutil.copyfile(x["nvram"], keep)
                                x["nvram"] = keep
                        got["vms"] = doms
                        said.append(f"VMs: {len(doms)} defined, {sum(1 for x in doms if x['autostart'])} started with the machine")
                finally:
                    self._unmount_image(job, d)
            got["said"] = said
            path = _env("BB_ADOPT_APPS", APPS)
            os.makedirs(os.path.dirname(path), exist_ok=True)
            with open(path + ".new", "w", encoding="utf-8") as f:
                json.dump(got, f)
            os.replace(path + ".new", path)
            for line in said:
                say(line + "\n")
            self.hello_again("the old system's containers and VMs were read")
            return ("succeeded", 0) if ("docker" in got or "vms" in got) else ("failed", 1)
        if action == "vm":
            name, op = str(cfg.get("name") or ""), str(cfg.get("op") or "")
            if op not in VM_OPS or name not in {x["name"] for x in read_apps().get("vms") or []}:
                say("refused: an adopted VM by its name, and start, shutdown, off, autostart-on or autostart-off\n")
                return "failed", 64
            argv = ["virsh", "-c", "qemu:///system", VM_OPS[op][0], name, *VM_OPS[op][1:]]
            rc = self._sh(job, argv, timeout=120)
            self.hello_again(f"the VM {name}: {op}")
            return ("succeeded", 0) if rc == 0 else ("failed", rc)
        if action == "docker-network":
            name, subnet, gw = str(cfg.get("name") or ""), str(cfg.get("subnet") or ""), str(cfg.get("gateway") or "")
            if not NET_RE.fullmatch(name) or not CIDR_RE.fullmatch(subnet) or (gw and not IP_RE.fullmatch(gw)):
                say("refused: a network is a name, a subnet like 192.168.1.0/24 and a gateway address\n")
                return "failed", 64
            if subprocess.run(["docker", "network", "inspect", name], capture_output=True, timeout=30, check=False).returncode == 0:
                say(f"the network {name} is here already\n")
                return "succeeded", 0
            from .vms import lan_iface
            lan = lan_iface()
            if not lan:
                say("refused: this machine has no wired interface for a network of fixed addresses on the LAN\n")
                return "failed", 65
            rc = self._sh(job, ["docker", "network", "create", "-d", "macvlan", "--subnet", subnet, *(["--gateway", gw] if gw else []),
                                "-o", f"parent={lan}", name], timeout=60)
            if rc == 0:
                say(f"the network {name}: {subnet} on {lan}, each container at its own address (this machine cannot reach them there, other machines can)\n")
            return ("succeeded", 0) if rc == 0 else ("failed", rc)
        # define-vms: each named domain of what read-apps kept, as this machine runs it.
        from .vms import lan_iface, ovmf
        doms = {x["name"]: x for x in read_apps().get("vms") or []}
        names = [str(n) for n in (cfg.get("names") or []) if isinstance(n, str)][:64]
        if not names or not shutil.which("virsh"):
            say("refused: name the VMs to define, on a machine with libvirt (the VM host feature)\n")
            return "failed", 64
        have = {n.strip() for n in subprocess.run(["virsh", "-c", "qemu:///system", "list", "--all", "--name"], capture_output=True, text=True,
                                                  timeout=30, check=False).stdout.splitlines() if n.strip()}
        emulator = shutil.which("qemu-system-x86_64") or ""
        pair, lan, bad = ovmf(), lan_iface(), []
        for n in names:
            x = doms.get(n)
            if not x:
                say(f"{n}: not one the old system defined\n")
                bad.append(n)
                continue
            if n in have:
                say(f"{n}: defined here already, left as it is\n")
                continue
            nv = os.path.join(NVRAM_DIR, re.sub(r"[^A-Za-z0-9._-]", "_", n) + "_VARS.fd")
            xml, said = rewrite_domain(x["xml"], emulator, pair, nv, lan)
            if pair and "<loader" in x["xml"]:
                os.makedirs(NVRAM_DIR, exist_ok=True)
                # The old variables where they fit this firmware (the same
                # size), else a fresh copy: its boot entries are then made
                # again from the disk, which a guest's fallback loader does.
                old = x.get("nvram") or ""
                if old and os.path.getsize(old) == os.path.getsize(pair[1]):
                    shutil.copyfile(old, nv)
                else:
                    shutil.copyfile(pair[1], nv)
                    said.append("its UEFI variables start fresh (the old ones are another firmware's size)")
            with tempfile.NamedTemporaryFile("w", suffix=".xml", delete=False) as f:
                f.write(xml)
            try:
                rc = self._sh(job, ["virsh", "-c", "qemu:///system", "define", f.name], timeout=60)
            finally:
                os.unlink(f.name)
            if rc != 0:
                bad.append(n)
                continue
            if x.get("autostart"):
                self._sh(job, ["virsh", "-c", "qemu:///system", "autostart", n], timeout=30)
                said.append("starts with the machine, as it did")
            say(f"{n}: defined; " + "; ".join(said) + "\n")
        self.hello_again("VMs were defined")
        return ("succeeded", 0) if not bad else ("failed", 1)

    def _apply_storage_adopt(self, job, cfg):
        say = job.say
        action = str(cfg.get("adopt") or "")
        if action not in ACTIONS:
            say(f"refused: {action or 'no action'} is not one of {', '.join(ACTIONS)}\n")
            return "failed", 64
        if action != "dry" and os.geteuid() != 0:
            say("refused: adopting disks mounts them, which this agent cannot as it is not root\n")
            return "failed", 77
        if action in ("read-apps", "define-vms", "docker-network", "vm"):
            return self._apply_apps(job, action, cfg)
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
            if self._sh(job, ["mount", "-T", _env("BB_ADOPT_FSTAB", FSTAB), m["where"]], timeout=60) != 0:
                failed.append(m["where"])
                if m.get("ro"):
                    say(f"{m['where']} would not mount without its journal replayed, which writes the disk: mount it once on the "
                        "old system and shut that down cleanly, or adopt writable\n")
        for where in p["merged"]:
            if self._sh(job, ["mount", "-T", _env("BB_ADOPT_FSTAB", FSTAB), where], timeout=60) != 0:
                failed.append(where)
        if failed:
            say(f"adopted, but not mounted yet: {', '.join(failed)}; tried again every minute, and Release undoes all of it\n")
            return "failed", 1
        say("adopted: every disk and pool mounted as it was, its paths kept\n")
        return "succeeded", 0
