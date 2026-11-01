"""A prepared configuration's first boot on the controller (R161 step 8).

The stick's root step (image/mkosi.extra/usr/lib/builderbot-os/firstboot-take)
takes builderbot/firstboot.json off the ESP before the controller starts and
hands it over at /run/builderbot-os/firstboot/firstboot.json with what it did
to the machine itself (the hostname, the time zone). At start this applies
the rest it can: the owner (a name and a password hash; none leaves the
first-run page to ask), the people (by name and role, their SMB password's
NT hash with them), and first_run: skip marks the setup page finished. What
needs disks adopted first (the shares, the pools, the array) and the apps
are kept for the piece that adopts them, said as waiting. The handed file is
removed; what is kept in /config/firstboot.json never holds the password
hash nor an SMB hash. This machine draws the report (view()).

Format 1:
    {"format": 1, "first_run": "skip" | "ask",
     "machine": {"hostname", "timezone", "network": {...}},
     "hold_first_start": true | false,
     "owner": {"name", "password_hash"},
     "people": [{"name", "role", "smb_nt"}],
     "shares": [...], "pools": [...], "array": {...}, "apps": [...]}
"""
import json
import os
import time
from pathlib import Path

RUN = Path(os.environ.get("BB_FIRSTBOOT_RUN", "/run/builderbot-os/firstboot/firstboot.json"))
STATE = None
write_json = users = settings = None
hold_first = lambda: None    # noqa: E731 (held.arm_first, R161 step 11)
WAITS = {"shares": "a share is served from a pool or the array, adopted first",
         "pools": "the pools are adopted from This machine's Storage, a later piece",
         "array": "the array is adopted by its disks' serials, a later piece",
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
        (done if v == "applied" else failed).append({"what": k, "said": v})
    if isinstance(cfg, dict):
        owner = cfg.get("owner") or {}
        if owner.get("password_hash"):
            r = users.adopt(owner, cfg.get("people") or [])
            if r.get("error"):
                failed.append({"what": "accounts", "said": r["error"]})
            else:
                done.append({"what": "accounts", "said": ", ".join(r["made"])})
                failed += [{"what": f"account {n or '(no name)'}", "said": why} for n, why in r["skipped"]]
                if cfg.get("first_run") == "skip":
                    settings.set_many({"setup_done": True})
                    done.append({"what": "first run", "said": "skipped: the owner signs in"})
        else:
            waiting.append({"what": "accounts", "said": "no owner's password came with it: the first-run page makes the owner"})
        # Held on the disks (R161 step 11): the start this configuration came
        # with shows them on This machine before anything mounts.
        if cfg.get("hold_first_start"):
            hold_first()
            done.append({"what": "first start", "said": "held: Start on This machine once the disks are as they should be"})
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
        failed.append({"what": "file", "said": "the prepared configuration could not be read"})
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
    pools = [{"name": str(p.get("name") or ""), "fs": str(p.get("fs") or "").lower(), "uuid": str(p.get("uuid") or "")}
             for p in (cfg or {}).get("pools") or [] if isinstance(p, dict) and p.get("name")]
    if not data and not pools:
        return None
    return {"want": {"data": data, "parity": parity, "pools": pools}, "skipped": skipped}


def share_requests(cfg):
    """The plan's shares as storage-share's set-many takes them (R163 step
    9), each served from the merged tree where its files were: SMB as its
    security said (public: everybody as a guest; secure: its writers by name,
    the guests' reading not carried and said so, or everybody as a read-only
    guest where it names no writer; private: the people on its lists by
    name), NFS to the hosts its export named, a Time Machine share kept one.
    What cannot be carried is said beside each. ([rows], [notes])."""
    rows, notes = [], []
    for s in (cfg or {}).get("shares") or []:
        if not isinstance(s, dict) or not s.get("name"):
            continue
        name = str(s["name"])
        sec = str(s.get("security") or "public")
        people = [p for p in [*(s.get("read") or []), *(s.get("write") or [])] if isinstance(p, str) and p]
        smb = {"on": s.get("smb") is True, "guest": False, "ro": False, "tm": s.get("time_machine") is True, "users": []}
        if smb["on"]:
            if sec == "public":
                smb["guest"] = True
            elif sec == "secure":
                writers = [p for p in s.get("write") or [] if isinstance(p, str) and p]
                if writers:
                    smb["users"] = writers
                    notes.append({"name": name, "said": "secure: its writers by name; everybody else's guest reading is not carried"})
                else:
                    smb.update(guest=True, ro=True)
            else:
                smb["users"] = sorted(set(people))
                if not people:
                    notes.append({"name": name, "said": "private with nobody on its lists: not served over SMB"})
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
        if not smb["on"] and not nfs["on"]:
            continue
        rows.append({"name": name, "path": f"/mnt/user/{name}", "smb": smb, "nfs": nfs})
    return rows, notes


def view():
    """This machine's section: what the stick's prepared configuration did,
    and what its plan names to adopt; None when this install had none."""
    try:
        d = json.loads(_file().read_text(encoding="utf-8"))
    except (OSError, ValueError):
        return None
    rows, notes = share_requests(d.get("config"))
    return {**{k: d.get(k) for k in ("at", "done", "waiting", "failed")}, "adopt": adopt_want(d.get("config")),
            "shares": {"rows": rows, "notes": notes} if rows or notes else None}
