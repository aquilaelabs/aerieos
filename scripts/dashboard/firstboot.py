"""A prepared configuration's first boot on the controller (R161 step 8).

The stick's root step (image/mkosi.extra/usr/lib/aerieos-os/firstboot-take)
takes builderbot/firstboot.json off the ESP before the controller starts and
hands it over at /run/aerieos-os/firstboot/firstboot.json with what it did
to the machine itself (the hostname, the time zone). At start this applies
the rest it can: the owner (a name and a password hash; none leaves the
first-run page to ask), the people (by name and role, their SMB password's
NT hash with them), and first_run: skip marks the setup page finished unless
the plan names disks, which that page walks through. What
needs disks adopted first (the shares, the pools, the array) and the apps
are kept for the piece that adopts them, said as waiting. The handed file is
removed; what is kept in /config/firstboot.json never holds the password
hash nor an SMB hash. The own node's row draws the report (view()).

Format 1:
    {"format": 1, "first_run": "skip" | "ask",
     "machine": {"hostname", "timezone", "network": {...}, "kernel_args", "features"},
     "hold_first_start": true | false,
     "owner": {"name", "password_hash"},
     "people": [{"name", "role", "smb_nt"}],
     "shares": [...], "pools": [...], "array": {...}, "apps": [...]}
"""
import json
import os
import re
import time
from pathlib import Path

RUN = Path(os.environ.get("BB_FIRSTBOOT_RUN", "/run/aerieos-os/firstboot/firstboot.json"))
STATE = None
# The name a pool may be mounted under (adopt.POOL_RE, nodes._adopt_want).
POOL_NAME = re.compile(r"[a-z][a-z0-9_-]{0,31}")
PCI_ADDR = re.compile(r"[0-9a-fA-F]{4}:[0-9a-fA-F]{2}:[0-9a-fA-F]{2}\.[0-7]")
write_json = users = settings = None
hold_first = lambda: None    # noqa: E731 (held.arm_first, R161 step 11)
WAITS = {"shares": "a share is served from a pool or the array once they are adopted",
         "pools": "adopted on the Nodes page, under The old system's disks: Check, then Adopt",
         "array": "adopted on the Nodes page, under The old system's disks: Check, then Adopt",
         "apps": "an app is a container made from New container once its folders' disks are here"}


def configure(*, state, write_json_fn, users_mod, settings_mod, hold_first_fn=None):
    globals().update(STATE=Path(state), write_json=write_json_fn, users=users_mod, settings=settings_mod)
    if hold_first_fn:
        globals()["hold_first"] = hold_first_fn


def _file():
    return STATE / "firstboot.json"


def apply(path=None):
    """Apply what the stick's first boot handed over, once. The report, or
    None when nothing was handed over."""
    path = Path(path or RUN)
    try:
        handed = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, ValueError):
        return None
    cfg = handed.get("config") if isinstance(handed, dict) else None
    done, waiting, failed = [], [], []
    for k, v in ((handed or {}).get("machine") or {}).items():
        # The boot's arguments and features say what they did in words, a
        # refusal starting "not set".
        ok = v == "applied" or (k in ("kernel_args", "features") and isinstance(v, str) and not v.startswith("not set"))
        (done if ok else failed).append({"what": {"kernel_args": "kernel arguments"}.get(k, k), "said": v})
    if isinstance(cfg, dict):
        owner = cfg.get("owner") or {}
        if owner.get("password_hash"):
            r = users.adopt(owner, cfg.get("people") or [])
            if r.get("error"):
                failed.append({"what": "accounts", "said": r["error"]})
            else:
                done.append({"what": "accounts", "said": ", ".join(r["made"])})
                failed += [{"what": f"account {n or '(no name)'}", "said": why} for n, why in r["skipped"]]
                # A plan that names disks keeps the setup page: it is where
                # they are walked through, in the order they have to happen.
                if cfg.get("first_run") == "skip" and not adopt_want(cfg):
                    settings.set_many({"setup_done": True})
                    done.append({"what": "first run", "said": "skipped: the owner signs in"})
        else:
            waiting.append({"what": "accounts", "said": "no owner's password came with it: the first-run page makes the owner"})
        # Held on the disks (R161 step 11): the start this configuration came
        # with shows them on the Nodes page before anything mounts.
        if cfg.get("hold_first_start"):
            hold_first()
            done.append({"what": "first start", "said": "held: Start on This controller once the disks are as they should be"})
        for k, why in WAITS.items():
            if cfg.get(k):
                waiting.append({"what": k, "said": why, "count": len(cfg[k]) if isinstance(cfg[k], list) else 1})
        # Kept for the pieces that adopt the rest, the password hash and the
        # SMB hashes taken out: those are on the accounts, and nowhere else.
        kept = {k: v for k, v in cfg.items() if k not in ("owner", "people")}
        kept["owner"] = {"name": owner.get("name", "")} if owner else {}
        kept["people"] = [{"name": p.get("name", ""), "role": p.get("role", "user")} for p in cfg.get("people") or [] if isinstance(p, dict)]
    else:
        kept = None
        failed.append({"what": "file", "said": "the prepared configuration could not be read: make the stick again with the USB maker, which writes it, "
                                               "or set this machine up on its first-run page without one"})
    report = {"at": int(time.time()), "done": done, "waiting": waiting, "failed": failed, "config": kept}
    write_json(_file(), report)
    try:
        path.unlink()
    except OSError:
        pass
    return report


def adopt_want(cfg):
    """What the stick's plan names to adopt (R163 step 9), as the
    storage-adopt request takes it: the data disks by slot and serial with
    their filesystem, the parity disks to leave alone, the pools by name and
    UUID; an encrypted disk is listed apart with why, since its key is not
    asked for yet. None when the plan names no disk or pool."""
    ar = (cfg or {}).get("array") if isinstance((cfg or {}).get("array"), dict) else {}
    data, skipped = [], []
    for x in ar.get("disks") or []:
        if not isinstance(x, dict) or not x.get("id"):
            continue
        fs = str(x.get("fs") or "").lower()
        if fs.startswith("luks"):
            skipped.append({"slot": x.get("slot", ""), "id": x["id"], "why": "encrypted: its key is not asked for yet"})
        elif fs in ("xfs", "btrfs", "zfs"):
            data.append({"slot": str(x.get("slot") or ""), "id": str(x["id"]), "fs": fs})
        else:
            skipped.append({"slot": x.get("slot", ""), "id": x["id"], "why": f"its filesystem is {fs or 'not said'}"})
    parity = [{"slot": str(x.get("slot") or "parity"), "id": str(x["id"])} for x in ar.get("parity") or [] if isinstance(x, dict) and x.get("id")]
    # A pool the adopt cannot take is set apart with why, as a disk is: one
    # left in the request would fail its shape check whole, and nothing of
    # the stick's would adopt (B612).
    pools = []
    for p in (cfg or {}).get("pools") or []:
        if not isinstance(p, dict) or not p.get("name"):
            continue
        name, fs, uuid = str(p["name"]), str(p.get("fs") or "").lower(), str(p.get("uuid") or "")
        if fs.startswith("luks"):
            skipped.append({"slot": name, "id": uuid or name, "why": "encrypted: its key is not asked for yet"})
        elif fs not in ("xfs", "btrfs", "zfs"):
            skipped.append({"slot": name, "id": uuid or name, "why": f"its filesystem is {fs or 'not said'}"})
        elif not POOL_NAME.fullmatch(name):
            skipped.append({"slot": name, "id": uuid or name, "why": "its name is not one a pool can be mounted under here (a lowercase letter, then lowercase letters, digits, - and _)"})
        else:
            pools.append({"name": name, "fs": fs, "uuid": uuid})
    # A cache disk the old system kept in its array's cache slot (B625: no
    # config/pools, as before its pools), offered as a pool named for its
    # slot and found by its disk, since no pool record names its UUID.
    for x in ar.get("cache") or []:
        if not isinstance(x, dict) or not x.get("id"):
            continue
        name, fs = str(x.get("slot") or "cache"), str(x.get("fs") or "").lower()
        if any(p["name"] == name for p in pools) or any(s["slot"] == name for s in skipped):
            continue
        if fs.startswith("luks"):
            skipped.append({"slot": name, "id": str(x["id"]), "why": "encrypted: its key is not asked for yet"})
        elif fs not in ("xfs", "btrfs", "zfs"):
            skipped.append({"slot": name, "id": str(x["id"]), "why": f"its filesystem is {fs or 'not said'}"})
        elif not POOL_NAME.fullmatch(name):
            skipped.append({"slot": name, "id": str(x["id"]), "why": "its name is not one a pool can be mounted under here (a lowercase letter, then lowercase letters, digits, - and _)"})
        else:
            pools.append({"name": name, "fs": fs, "uuid": "", "disk_id": str(x["id"])})
    if not data and not pools:
        return None
    return {"want": {"data": data, "parity": parity, "pools": pools}, "skipped": skipped}


def share_requests(cfg):
    """The plan's shares as storage-share's set-many takes them (R163 step
    9), each served from the merged tree where its files were: SMB as its
    security said (public: everybody as a guest; secure: everybody reads as a
    guest and its writers write; private: the people on its lists, each as read
    or write), NFS to the hosts its export named, a Time Machine share kept one.
    What cannot be carried is said beside each. ([rows], [notes])."""
    rows, notes = [], []
    for s in (cfg or {}).get("shares") or []:
        if not isinstance(s, dict) or not s.get("name"):
            continue
        name = str(s["name"])
        sec = str(s.get("security") or "public")
        people = [p for p in [*(s.get("read") or []), *(s.get("write") or [])] if isinstance(p, str) and p]
        smb = {"on": s.get("smb") is True, "guest": False, "ro": False, "tm": s.get("time_machine") is True, "users": [], "readers": []}
        if smb["on"]:
            if sec == "public":
                smb["guest"] = True
            elif sec == "secure":
                # As it was: everybody reads as a guest, its writers by name.
                writers = [p for p in s.get("write") or [] if isinstance(p, str) and p]
                smb["guest"] = True
                if writers:
                    smb["users"] = writers
                else:
                    smb["ro"] = True
            else:
                writers = sorted({p for p in s.get("write") or [] if isinstance(p, str) and p})
                smb["users"] = writers
                smb["readers"] = sorted({p for p in s.get("read") or [] if isinstance(p, str) and p and p not in writers})
                if not people:
                    notes.append({"name": name, "said": "private with nobody on its lists: kept as a folder, not exported"})
                    smb["on"] = False
        clients, ro = [], False
        for rule in str(s.get("nfs_clients") or "").split():
            host = rule.split("(", 1)[0]
            if host:
                clients.append(host)
                ro = ro or "(ro" in rule or ",ro" in rule
        nfs = {"on": s.get("nfs") is True, "ro": ro, "clients": clients or (["*"] if s.get("nfs") and s.get("nfs_security") == "public" else [])}
        if nfs["on"] and not nfs["clients"]:
            notes.append({"name": name, "said": "NFS with no host named: not exported"})
            nfs["on"] = False
        # Exported or not, it is a share: one nothing serves stays internal.
        rows.append({"name": name, "path": f"/mnt/user/{name}", "smb": smb, "nfs": nfs})
    return rows, notes


def kept_config():
    """The stick's configuration as kept (no password or SMB hash in it),
    or {}."""
    try:
        d = json.loads(_file().read_text(encoding="utf-8"))
    except (OSError, ValueError):
        return {}
    return d.get("config") if isinstance(d.get("config"), dict) else {}


def mover_moves(pools, cfg=None):
    """Each share's places on an array taken over (R163 step 3), as the
    old system had them: [{share, land, from, to}], land where its new
    files go (a pool, or the array) and the mover's from and to (both empty
    when it leaves the share be). A share that wrote to a pool and moved to
    the array or a second pool later (cache yes) lands on its pool and moves
    off it; one kept on the array and moved onto its pool (prefer) the other
    way; one kept on its pool (only) stays there; the rest (cache no, or a
    pool not here) land on the array."""
    cfg = kept_config() if cfg is None else cfg
    out = {}
    for s in (cfg or {}).get("shares") or []:
        if not isinstance(s, dict) or not s.get("name"):
            continue
        name, c, p, p2 = str(s["name"]), str(s.get("cache") or "no"), str(s.get("pool") or ""), str(s.get("pool2") or "")
        other = p2 if p2 in pools and p2 != p else "array"
        if c in ("yes", "prefer", "only") and p in pools:
            mv = {"yes": (p, other), "prefer": (other, p)}.get(c, ("", ""))
            out[name] = {"share": name, "land": p, "from": mv[0], "to": mv[1]}
        else:
            out[name] = {"share": name, "land": "array", "from": "", "to": ""}
    return list(out.values())[:128]


def _cron_words(cron):
    """A timetable as a person says it, or "" for none."""
    if not cron:
        return ""
    import schedules
    return schedules.words(cron)


def mover_cron(cfg=None):
    """When the old system's mover ran, as five cron fields, or ""."""
    cfg = kept_config() if cfg is None else cfg
    c = str(((cfg or {}).get("sharing") or {}).get("mover") or "").strip()
    return c if re.fullmatch(r"[0-9*/,-]+( [0-9*/,-]+){4}", c) else ""


def met(waiting, done, reported):
    """The waits the machine has met since the report was written (B634):
    the array once a data disk the plan named is mounted, the pools once
    one is, the shares once the machine serves any; each moves to done with
    what is there now. The report on disk is left as written."""
    rep = reported if isinstance(reported, dict) else {}
    ad = rep.get("adopted") if isinstance(rep.get("adopted"), dict) else {}
    mounts = [m for m in (ad.get("mounts") or []) if isinstance(m, dict) and m.get("mounted")]
    disks = [m for m in mounts if str(m.get("where") or "").startswith("/mnt/disk")]
    pools = [m for m in mounts if m not in disks]
    shares = [x for x in (rep.get("shares") or []) if isinstance(x, dict)]
    said = {"array": f"adopted: {len(disks)} data disk{'s' if len(disks) != 1 else ''} mounted" if disks else "",
            "pools": f"adopted: {len(pools)} mounted" if pools else "",
            "shares": f"{len(shares)} served" if shares else ""}
    still, now = [], list(done)
    for w in waiting:
        what = w.get("what") if isinstance(w, dict) else ""
        if said.get(what):
            now.append({"what": what, "said": said[what], "count": w.get("count")})
        else:
            still.append(w)
    return still, now


def view(reported=None):
    """The own node's section: what the stick's prepared configuration did,
    and what its plan names to adopt; None when this install had none.
    `reported` is the machine's own node's census, which says which waits
    have been met since (B634)."""
    try:
        d = json.loads(_file().read_text(encoding="utf-8"))
    except (OSError, ValueError):
        return None
    cfg = d.get("config") if isinstance(d.get("config"), dict) else {}
    if reported:
        waiting, done = met(d.get("waiting") or [], d.get("done") or [], reported)
        d = {**d, "waiting": waiting, "done": done}
    rows, notes = share_requests(cfg)
    dk, vm = cfg.get("docker") if isinstance(cfg.get("docker"), dict) else {}, cfg.get("vms") if isinstance(cfg.get("vms"), dict) else {}
    nets = {str(k): {"subnet": str(v.get("subnet") or ""), "gateway": str(v.get("gateway") or "")}
            for k, v in (dk.get("networks") or {}).items() if isinstance(v, dict) and v.get("subnet")}
    aw = adopt_want(cfg)
    return {**{k: d.get(k) for k in ("at", "done", "waiting", "failed")}, "adopt": aw,
            # Each share's places for the takeover to start from, and when
            # the old system's mover ran.
            "moves": mover_moves([p["name"] for p in (aw or {}).get("want", {}).get("pools") or []], cfg) if aw else [],
            "mover_cron": mover_cron(cfg), "mover_words": _cron_words(mover_cron(cfg)),
            "shares": {"rows": rows, "notes": notes} if rows or notes else None,
            # Where the old system's containers and VMs are read from, and its
            # networks of fixed addresses (R163 steps 10, 11).
            "apps_from": {"docker": {"image": str(dk.get("image") or ""), "autostart_file": str(dk.get("autostart_file") or "")},
                          "vms": {"image": str(vm.get("image") or ""),
                                  # The devices it held for its VMs from boot (R163 step 16).
                                  "vfio": [str(a) for a in (vm.get("vfio") or [])[:32] if isinstance(a, str) and PCI_ADDR.fullmatch(a)]},
                          "networks": nets,
                          "containers": len(cfg.get("apps") or [])} if dk or vm or cfg.get("apps") else None}
