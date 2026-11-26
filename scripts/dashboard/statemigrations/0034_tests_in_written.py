"""State 33 to 34: where a space's tests run, written as one of its three
places in every record.

A record from before 24 Sep kept it as the boolean `devtest` (true: only in
the dev instance). prefs.py read it as `tests_in` on the way in and the file
followed at the next save of any space, so an install nobody saved a space on
since still holds it. Rewritten here once, and the reader is gone (R295).

Idempotent. Never edited once shipped (stateversion.py).
"""
import json
import os
from pathlib import Path


def run(ctx):
    f = Path(ctx["state"]) / "claude-prefs.json"
    try:
        d = json.loads(f.read_text())
    except (OSError, ValueError):
        return
    projects = d.get("projects") if isinstance(d, dict) else None
    if not isinstance(projects, dict):
        return
    moved = False
    for rec in projects.values():
        if isinstance(rec, dict) and "devtest" in rec:
            if rec.pop("devtest") is True and "tests_in" not in rec:
                rec["tests_in"] = "only"
            moved = True
    if not moved:
        return
    tmp = f.with_name(f.name + ".tmp")
    tmp.write_text(json.dumps(d, indent=1))
    os.chmod(tmp, f.stat().st_mode & 0o777)
    os.replace(tmp, f)
