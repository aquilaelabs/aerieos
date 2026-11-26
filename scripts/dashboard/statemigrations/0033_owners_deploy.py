"""State 32 to 33: a space's owner deploys it.

Deploy is a space's area from this state on (Read: its Kubernetes
environments and what runs in them; Write: deploy, roll back, restart and
scale). A space's owner holds every one of its areas at Write through the
role made for them (NAME_owner, scope projects, its note "the owner of
NAME"), and a new owner role is made with Deploy among them; each owner
role already in the file is given Deploy Write, so an owner from before can
deploy their own space as one made after can (the operator, 25 Nov). Any
other role is left as it is: Deploy is given by whoever gives roles. The
built-in roles are not in the file, and hold every area already.

Idempotent. Never edited once shipped (stateversion.py).
"""
import json
import os
from pathlib import Path


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
    for n, r in roles.items():
        if not (isinstance(r, dict) and str(n).endswith("_owner") and r.get("scope") == "projects"
                and str(r.get("note") or "").startswith("the owner of ")):
            continue
        perms = r.get("perms")
        if isinstance(perms, dict) and perms.get("deploy") != "write":
            perms["deploy"] = "write"
            moved = True
    if not moved:
        return
    tmp = f.with_name(f.name + ".tmp")
    tmp.write_text(json.dumps(d, indent=1))
    os.chmod(tmp, f.stat().st_mode & 0o777)
    os.replace(tmp, f)
