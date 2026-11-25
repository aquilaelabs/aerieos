"""State 30 to 31: a role that reached a space's notebook keeps reading it.

A space's notebook and code are read on Spaces Read on that space, as the
area's sentence on the Roles page says. Before, being on the space through
any role read them, so a role given for another of a space's areas
(its containers, its files, its terminal) read its notebook and code too,
and an account holding only that role would find them refused after the
update. Each role of the install's own that holds another of a space's
areas, and no level of Spaces, is given Spaces Read, so it reads what it
read before and reaches nothing new: a role given on a space reads that
space, an Everywhere one the spaces its holder is on. A role that already
holds Spaces at either level, and one holding only the controller's or the
nodes' areas, is left as it is; the built-in roles are not in the file.

Idempotent. Never edited once shipped (stateversion.py).
"""
import json
import os
from pathlib import Path

# A space's areas as they are at this migration, Spaces itself apart.
SPACE_AREAS = ("settings", "releases", "gitauth", "files", "containers", "vms", "terminal")
LEVELS = ("read", "write")


def run(ctx):
    f = Path(ctx["state"]) / "roles.json"
    try:
        d = json.loads(f.read_text())
    except (OSError, ValueError):
        return
    roles = d.get("roles") if isinstance(d, dict) else None
    if not isinstance(roles, dict):
        return
    moved = False
    for r in roles.values():
        perms = r.get("perms") if isinstance(r, dict) else None
        if not isinstance(perms, dict) or perms.get("projects") in LEVELS:
            continue
        if any(perms.get(a) in LEVELS for a in SPACE_AREAS):
            perms["projects"] = "read"
            moved = True
    if not moved:
        return
    tmp = f.with_name(f.name + ".tmp")
    tmp.write_text(json.dumps(d, indent=1))
    os.chmod(tmp, f.stat().st_mode & 0o777)
    os.replace(tmp, f)
