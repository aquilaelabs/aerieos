"""State 24 to 25: an archive is each person's own.

archived-projects.json was one list for everybody: a space its owner or an
administrator archived was folded away under Archived on every account's
Spaces page. It is kept per account now, {uid: [space]}, as the favorites
are, and anybody signed in archives for themselves. So that nobody's page
changes on the upgrade, every account the controller has is given the list
as it stood; an account made after starts with nothing archived.
Idempotent. Never edited once shipped (stateversion.py).
"""
import json
import sys
from pathlib import Path

FILE = "archived-projects.json"


def run(ctx):
    state = Path(ctx["state"])
    f = state / FILE
    try:
        v = json.loads(f.read_text())
    except (OSError, ValueError):
        return
    if not isinstance(v, list):
        return                               # each person's already, or not a record
    names = sorted({x for x in v if isinstance(x, str)})
    try:
        u = json.loads((state / "users.json").read_text())
    except (OSError, ValueError):
        u = {}
    accounts = u.get("users") if isinstance(u, dict) else None
    uids = sorted({str(r["uid"]) for r in (accounts or {}).values() if isinstance(r, dict) and r.get("uid")})
    sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
    import statefile
    statefile.write_json(f, {uid: names for uid in uids}, mode=f.stat().st_mode & 0o777)
