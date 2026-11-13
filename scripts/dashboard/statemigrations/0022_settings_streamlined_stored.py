"""State 21 to 22: the two settings a space no longer has, taken off the
file that holds them.

State 21 was written to do this and read prefs.json, a name nothing stores:
a space's settings are in claude-prefs.json, so no install was changed by
it. A repository whose daily snapshot switch was saved off stayed off, with
no control left to turn it back on, and a person's terminal colors for one
space stayed stored where nothing reads them.

A repository's switch saved off becomes 0 days kept, which takes none and
leaves the snapshots it has (the operator, 13 Nov), and the switch is taken
off. Each person's per-space terminal colors are taken off: Profile's Your
terminal sets them for every space. Idempotent. Never edited once shipped
(stateversion.py).
"""
import json
import sys
from pathlib import Path

FILE = "claude-prefs.json"


def run(ctx):
    f = Path(ctx["state"]) / FILE
    try:
        d = json.loads(f.read_text())
    except (OSError, ValueError):
        return
    if not isinstance(d, dict):
        return
    changed = False
    projects = d.get("projects")
    for rec in projects.values() if isinstance(projects, dict) else []:
        if isinstance(rec, dict) and "snapshots_on" in rec:
            if rec.get("snapshots_on") is False:
                rec["snapshot_days"] = 0
            rec.pop("snapshots_on", None)
            changed = True
    users = d.get("users")
    for mine in users.values() if isinstance(users, dict) else []:
        for rec in mine.values() if isinstance(mine, dict) else []:
            if isinstance(rec, dict) and "term_scheme" in rec:
                rec.pop("term_scheme", None)
                changed = True
    if not changed:
        return
    # Written as the controller writes it: a temporary name of its own,
    # flushed, then moved over the file.
    sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
    import statefile
    statefile.write_json(f, d, mode=f.stat().st_mode & 0o777)
