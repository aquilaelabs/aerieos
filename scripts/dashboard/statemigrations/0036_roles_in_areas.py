"""State 35 to 36: every role and account in the shape today's build reads.

A role from before R152 (7 Oct) kept `grants` on actions rather than a scope
and areas, and one from before R255 (16 Oct) kept its node areas as one flat
`nodes` list; an account from before R137 kept one `role` and no `roles`
list. roles.py and users.py read each as today's on the way in, and the file
followed only when a role or an account was next saved, so an install that
has not since still holds them. Written here once, with the tables as they
stood when this was written (a migration never reads a module, which moves
on), and the readers are gone (R295).

Idempotent. Never edited once shipped (stateversion.py).
"""
import json
import os
from pathlib import Path

# roles.CAP_AREA, roles.AREA_KEYS, roles.PROJECT_AREAS and roles.NODE_AREAS
# on 26 Nov 2026.
CAP_AREA = {'admin': ['accounts', 'write'],
 'clusters': ['clusters', 'write'],
 'clusters-read': ['clusters', 'read'],
 'command-pin': ['controller', 'write'],
 'configure': ['configure', 'write'],
 'configure-read': ['configure', 'read'],
 'containers-read': ['containers', 'read'],
 'controller': ['controller', 'write'],
 'controller-read': ['controller', 'read'],
 'create': ['newprojects', 'write'],
 'curate': ['curate', 'write'],
 'debug': ['controller', 'write'],
 'deploy': ['deploy', 'write'],
 'deploy-read': ['deploy', 'read'],
 'docker-any': ['containers', 'write'],
 'docker-read': ['containers', 'read'],
 'docker-write': ['containers', 'write'],
 'ftp': ['files', 'write'],
 'git-auth': ['gitauth', 'write'],
 'jobs': ['jobs', 'write'],
 'lock': ['settings', 'write'],
 'node': ['nodes', 'write'],
 'nodes-read': ['nodes', 'read'],
 'nodes-write': ['nodes', 'write'],
 'read': ['projects', 'read'],
 'rename': ['settings', 'write'],
 'runner': ['runner', 'write'],
 'runner-read': ['runner', 'read'],
 'schedules': ['schedules', 'write'],
 'schedules-read': ['schedules', 'read'],
 'settings': ['settings', 'write'],
 'signing': ['releases', 'write'],
 'terminal': ['terminal', 'write'],
 'terminal-any': ['terminal', 'write'],
 'toolchains-write': ['install', 'write'],
 'trash': ['settings', 'write'],
 'trash-any': ['settings', 'write'],
 'version': ['releases', 'write'],
 'vms-read': ['vms', 'read'],
 'vms-write': ['vms', 'write'],
 'work': ['projects', 'write']}
AREA_KEYS = ('projects', 'settings', 'releases', 'gitauth', 'files', 'containers', 'vms', 'terminal', 'deploy', 'nodes', 'clusters', 'install', 'configure', 'curate', 'jobs', 'schedules', 'runner', 'accounts', 'newprojects', 'controller', 'storage')
PROJECT_AREAS = ('containers', 'deploy', 'files', 'gitauth', 'projects', 'releases', 'settings', 'terminal', 'vms')
NODE_AREAS = ('configure', 'install', 'jobs', 'newprojects', 'nodes', 'storage')
LEVELS = ("read", "write")


def _from_grants(gs):
    perms, scope = {}, "projects"
    for g in gs if isinstance(gs, list) else []:
        if not isinstance(g, dict):
            continue
        cap = str(g.get("cap") or "")
        pairs = [(a, "write") for a in AREA_KEYS] if cap == "*" else [tuple(CAP_AREA[cap])] if cap in CAP_AREA else []
        for area, lvl in pairs:
            if perms.get(area) != "write":
                perms[area] = lvl
        if g.get("scope") == "all":
            scope = "global"
    if scope == "projects" and any(a not in PROJECT_AREAS for a in perms):
        scope = "global"
    return scope, perms


def _write(f, d):
    tmp = f.with_name(f.name + ".tmp")
    tmp.write_text(json.dumps(d, indent=1))
    os.chmod(tmp, f.stat().st_mode & 0o777)
    os.replace(tmp, f)


def _roles(state):
    f = Path(state) / "roles.json"
    try:
        d = json.loads(f.read_text())
    except (OSError, ValueError):
        return
    rs = d.get("roles") if isinstance(d, dict) else None
    if not isinstance(rs, dict):
        return
    moved = False
    for r in rs.values():
        if not isinstance(r, dict):
            continue
        if "grants" in r:
            if "perms" not in r:
                r["scope"], r["perms"] = _from_grants(r.get("grants"))
            r.pop("grants")
            moved = True
        if "nodes" in r:
            raw = r.pop("nodes")
            nodes = sorted({str(n)[:40] for n in raw if str(n).strip()})[:64] if isinstance(raw, list) else []
            perms = r.get("perms") if isinstance(r.get("perms"), dict) else {}
            if nodes and not r.get("only") and r.get("scope") == "global":
                r["only"] = {a: {n: perms[a] for n in nodes} for a in sorted(NODE_AREAS) if perms.get(a) in LEVELS}
            moved = True
    if moved:
        _write(f, d)


def _accounts(state):
    f = Path(state) / "users.json"
    try:
        d = json.loads(f.read_text())
    except (OSError, ValueError):
        return
    us = d.get("users") if isinstance(d, dict) else None
    if not isinstance(us, dict):
        return
    moved = False
    for u in us.values():
        if isinstance(u, dict) and not isinstance(u.get("roles"), list):
            u["roles"] = [str(u.get("role") or "user")]
            moved = True
    if moved:
        _write(f, d)


def run(ctx):
    _roles(ctx["state"])
    _accounts(ctx["state"])
