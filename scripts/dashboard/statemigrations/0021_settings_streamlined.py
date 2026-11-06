"""State 20 to 21: two settings a space no longer has (R223, the operator,
7 Nov: fewer controls across a space and its repositories).

A repository's daily snapshot switch is gone, since keeping 0 days already
says none: one saved off becomes 0 days kept, and the switch is taken off.
A person's terminal colors for one space are gone, since Profile's Your
terminal sets them for every space: each per-space choice is taken off, and
the terminal reads Profile's. Idempotent. Never edited once shipped
(stateversion.py).
"""
import json
import os
from pathlib import Path


def run(ctx):
    f = Path(ctx["state"]) / "prefs.json"
    try:
        d = json.loads(f.read_text())
    except (OSError, ValueError):
        return
    if not isinstance(d, dict):
        return
    changed = False
    for rec in (d.get("projects") or {}).values():
        if isinstance(rec, dict) and "snapshots_on" in rec:
            if rec.get("snapshots_on") is False:
                rec["snapshot_days"] = 0
            rec.pop("snapshots_on", None)
            changed = True
    for mine in (d.get("users") or {}).values():
        for rec in (mine or {}).values() if isinstance(mine, dict) else []:
            if isinstance(rec, dict) and "term_scheme" in rec:
                rec.pop("term_scheme", None)
                changed = True
    if not changed:
        return
    tmp = f.with_name(f.name + ".new")
    tmp.write_text(json.dumps(d))
    os.replace(tmp, f)
