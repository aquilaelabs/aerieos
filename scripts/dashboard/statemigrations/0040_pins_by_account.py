"""State 39 to 40: every account's pinned spaces written as its own list.

An account made before 7 Oct carries no pins_empty mark, and until it pinned
something its Home read every space as pinned (no entry), or the old
everybody default under "*"; one made since starts with nothing pinned. Each
older account that never pinned is given, once, the set its Home showed on
27 Nov (the "*" default where there is one, else every space), so no entry
means nothing pinned for everybody; "*" goes, and the readers with it
(R205). The marks stay in users.json, read by nothing but a second run of
this, which they keep from taking a newer account that never pinned for an
older one.

Idempotent. Never edited once shipped (stateversion.py).
"""
import json
import os
from pathlib import Path


def _read(f):
    try:
        return json.loads(f.read_text())
    except (OSError, ValueError):
        return None


def _write(f, d):
    tmp = f.with_name(f.name + ".tmp")
    tmp.write_text(json.dumps(d, indent=1))
    os.chmod(tmp, f.stat().st_mode & 0o777)
    os.replace(tmp, f)


def run(ctx):
    state = Path(ctx["state"])
    uf, pf = state / "users.json", state / "pinned-projects.json"
    users = _read(uf)
    accounts = users.get("users") if isinstance(users, dict) else None
    if not isinstance(accounts, dict):
        return
    pins = _read(pf) if pf.exists() else {}
    pins = pins if isinstance(pins, dict) else {}
    every = None
    moved_pins = False
    for acct in accounts.values():
        if not isinstance(acct, dict):
            continue
        uid = str(acct.get("uid") or "")
        if not acct.get("pins_empty") and uid and uid not in pins:
            if "*" in pins:
                pins[uid] = sorted({x for x in (pins.get("*") or []) if isinstance(x, str)})
            else:
                every = every if every is not None else sorted(set(ctx["project_names"]()))
                pins[uid] = list(every)
            moved_pins = True
    if "*" in pins:
        pins.pop("*")
        moved_pins = True
    if moved_pins:
        if pf.exists():
            _write(pf, pins)
        else:
            pf.write_text(json.dumps(pins, indent=1))
            os.chmod(pf, 0o600)
