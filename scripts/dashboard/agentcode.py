"""The other coding agents on the nodes (R95 step 2): which version of
Codex CLI and Copilot CLI each node runs, what the latest is, and the one
way each is installed, updated or removed.

claudecode.py's pattern, for every row of the agent table that has a
Toolchains row and is not Claude (agents.installable()): installed into
the session account's home on a node, never by the provisioner, its
version probed on the heartbeat (the census's session.<reported>), the
newest release asked of the npm registry once after the controller starts,
then on the toolchains' clock and on a press of Check for updates, and the
install, update or removal a job the agent runs as the session account,
then pins root-owned where the agent is root.

UPDATING IS A PERSON'S, NEVER A SESSION'S, as for Claude Code: the node
handler is an administrator's and refuses a session's token, and the
agent's own sessions on the node are ended first.
"""
import http.client
import json
import os
import re
import threading
import time
import urllib.request

import agents

VER = re.compile(r"(\d+\.\d+\.\d+)")

nodes = None               # nodes.py
claudecode = None          # claudecode.py: Claude Code's own row (R145) beside the others
node_sessions = None       # server.node_tmux_sessions
tmux_base = None           # server.tmux_base
audit = None
_lock = threading.Lock()
_latest = {}               # {agent id: {version, at, error, checking}}
_pressed = {}              # {(agent id, node id): when}, as claudecode's
catalog_entry = None       # server: the signed index's official entry of this name, or None
fetch_pack = None          # toolpacks.fetch
_recipes = {}              # {(agent id, commit): (the catalog's recipe there or None, when read, why not)}
RECIPE_MISS_S = 300        # a pack that could not be fetched is asked again after this long


def configure(*, nodes_module, node_sessions, tmux_base, audit=None, claude=None, catalog_entry=None, fetch_pack=None):
    globals().update(nodes=nodes_module, node_sessions=node_sessions,
                     tmux_base=tmux_base, audit=audit, claudecode=claude,
                     catalog_entry=catalog_entry, fetch_pack=fetch_pack)


def recipe(agent_id):
    """(recipe, "catalog" or "release"): how this agent is installed, as
    the node is handed it with every install, update and removal (R169 step
    13). The agent table's own, which shipped with this release, unless the
    catalog's signed index pins this agent's pack at a commit whose recipe
    has a higher rev: then the catalog's, fetched at that commit with its
    archive's sha256 checked and the manifest held to its shape, as any
    pack's is. A catalog that does not answer, a pack that is refused or
    one no newer than the table leaves the table's. Read once per commit
    and kept while the controller runs."""
    a = agents.get(agent_id)
    own = a.install if a else None
    entry = catalog_entry(a.id) if a and catalog_entry else None
    if not entry or not fetch_pack:
        return own, "release"
    key = (a.id, entry["commit"])
    with _lock:
        had = _recipes.get(key)
    if not had or (had[2] and time.time() - had[1] > RECIPE_MISS_S):
        got = fetch_pack(entry["url"], entry["commit"], (), entry["sha256"], entry.get("path", ""))
        theirs = None if got.get("error") else ((got.get("manifest") or {}).get("agent") or {}).get("install")
        had = (theirs, time.time(), got.get("error") or "")
        with _lock:
            _recipes[key] = had
    theirs = had[0]
    if theirs and (not own or theirs["rev"] > own["rev"]):
        return theirs, "catalog"
    return own, "release"


def recipe_spec(agent_id):
    """A job's spec words for the recipe: {recipe, recipe_from}, or {} for
    an agent with none (an agent from before this runs its own table)."""
    r, where = recipe(agent_id)
    return {"recipe": r, "recipe_from": where} if r else {}


def tracked():
    """The agents this module keeps: installable, and not Claude, whose
    own is claudecode.py."""
    return tuple(a for a in agents.installable() if a.id != "claude")


def _agent(agent_id):
    a = agents.get(agent_id)
    if not a or a not in tracked():
        raise KeyError(agent_id)
    return a


def latest_url(a):
    """The registry's answer for this agent, or a test's file:// stand-in
    (BB_CODEX_LATEST_URL, BB_COPILOT_LATEST_URL, BB_GROK_LATEST_URL)."""
    return os.environ.get(f"BB_{a.id.upper()}_LATEST_URL") or a.latest_url


def check(agent_id):
    """Ask what the latest release of this agent is, now. The record."""
    a = _agent(agent_id)
    with _lock:
        rec = _latest.setdefault(a.id, {"version": "", "at": 0, "error": "", "checking": False})
        if rec["checking"]:
            return dict(rec)
        rec["checking"] = True
    version, error = "", ""
    try:
        with urllib.request.urlopen(latest_url(a), timeout=15) as r:   # noqa: S310 (a fixed https URL from the table, or a test's file://)  # nosemgrep: python.lang.security.audit.dynamic-urllib-use-detected.dynamic-urllib-use-detected
            text = r.read(65536).decode("utf-8", "replace").strip()
        try:
            got = str((json.loads(text) or {}).get("version") or "")
        except (ValueError, AttributeError):
            got = text
        m = VER.match(got)
        if m:
            version = m.group(1)
        else:
            error = f"unexpected answer from the registry: {got[:40]!r}"
    except (OSError, http.client.HTTPException, ValueError) as e:
        error = f"could not reach the registry: {e}"[:200]
    with _lock:
        rec = _latest[a.id]
        rec.update(checking=False, at=int(time.time()), error=error)
        if version:
            rec["version"] = version
        return dict(rec)


def check_all():
    return {a.id: check(a.id) for a in tracked()}


def latest(agent_id):
    with _lock:
        return dict(_latest.get(agent_id) or {"version": "", "at": 0, "error": "", "checking": False})


def installed(n, agent_id):
    """The version a node reports for this agent, or "": `0.163.0` out of
    `codex-cli 0.163.0`, `1.0.102` out of `GitHub Copilot CLI 1.0.102.`"""
    a = agents.get(agent_id)
    if not a:
        return ""
    m = VER.search(str(((n.get("reported") or {}).get("session") or {}).get(a.reported) or ""))
    return m.group(1) if m else ""


def _tup(v):
    return tuple(int(x) for x in v.split("."))


def behind(n, agent_id):
    i, cur = installed(n, agent_id), latest(agent_id)["version"]
    return bool(i and cur and _tup(i) < _tup(cur))


def updating(node_id, agent_id):
    """True while this agent's job is queued or running on the node."""
    if nodes is None:
        return False
    a = agents.get(agent_id)
    if time.time() - _pressed.get((agent_id, node_id), 0) < 120:
        return True
    return any(j.get("type") == a.update_job
               for j in nodes.jobs_for(node_id, n=20, type=a.update_job, active=True))


def start_hold(project, node_id, agent_id):
    """A sentence when a session of this agent on this node has to wait,
    or "": its update running there holds every start until it ends, as
    Claude Code's does (claudecode.start_hold, R95 step 18)."""
    n = nodes.node(node_id) if nodes else None
    a = agents.get(agent_id)
    if not n or not a or n.get("kind") != "agent":
        return ""
    if updating(node_id, agent_id):
        return (f"{a.product} is updating on {n['name']}: start {a.name} on {project} again when its "
                "row on the Installed page comes back")
    return ""


def _end_sessions(node_id, a):
    """End this agent's sessions on the node, before its binary is swapped."""
    ended = []
    for s in node_sessions() if node_sessions else []:
        got, _stem = agents.of_session(tmux_base(s["name"]))
        if s.get("node_id") == node_id and got is a:
            r = nodes.session_kill(node_id, s.get("node_name") or s["name"])
            if not r.get("error"):
                ended.append(s["name"])
    return ended


def update(principal, node_id, agent_id):
    """Queue the install or update of this agent on the node, its sessions
    there ended first. The caller has decided who may ask."""
    a = _agent(agent_id)
    n = nodes.node(node_id) if nodes else None
    if not n:
        return {"error": "no such node"}
    if n.get("kind") != "agent":
        return {"error": f"only an agent node runs {a.product}"}
    if not n.get("live"):
        return {"error": f"{n['name']} is not dialing in; nothing reaches it right now"}
    if not ((n.get("reported") or {}).get("session") or {}).get("up"):
        return {"error": f"{n['name']} runs no session account, so there is nowhere for {a.product} to go"}
    # The same press while it is queued or running is that job (no second
    # one); another of this agent's waits behind it (nodes.job_waits).
    if (same := next((j["id"] for j in nodes.jobs_for(node_id, n=20, type=a.update_job, active=True) if ((j.get("spec") or {}).get("action") or "update") == "update"), "")):
        return {"ok": True, "job": same, "already": True}
    _pressed[(a.id, node_id)] = time.time()
    try:
        # Read before its sessions are ended: a catalog asked for the first
        # time takes a moment, and nothing should be down while it does.
        how = recipe_spec(a.id)
        ended = _end_sessions(node_id, a)
        r = nodes.job_add(principal, {"node": node_id}, a.update_job,
                          {"timeout": 900, "to": latest(a.id)["version"], "ended": ended, **how})
    finally:
        _pressed.pop((a.id, node_id), None)
    if r.get("ok"):
        if audit:
            audit(principal, f"node-{a.id}-update", node_id, {"to": latest(a.id)["version"], "ended": ended,
                                                             "recipe": how.get("recipe_from", "")})
        r = r | {"ended": ended}
    return r


def remove(principal, node_id, agent_id):
    """Queue the job that takes this agent off the node, its sessions ended."""
    a = _agent(agent_id)
    n = nodes.node(node_id) if nodes else None
    if not n or n.get("kind") != "agent":
        return {"error": f"only an agent node runs {a.product}"}
    if not installed(n, a.id):
        return {"error": f"{a.product} is not installed on {n['name']}"}
    # The same press while it is queued or running is that job (no second
    # one); another of this agent's waits behind it (nodes.job_waits).
    if (same := next((j["id"] for j in nodes.jobs_for(node_id, n=20, type=a.update_job, active=True) if ((j.get("spec") or {}).get("action") or "update") == "remove"), "")):
        return {"ok": True, "job": same, "already": True}
    how = recipe_spec(a.id)
    ended = _end_sessions(node_id, a)
    r = nodes.job_add(principal, {"node": node_id}, a.update_job, {"timeout": 300, "action": "remove", "ended": ended, **how})
    if r.get("ok") and audit:
        audit(principal, f"node-{a.id}-remove", node_id, {"ended": ended})
    return r


def update_done(job, state):
    """The census catches up with an install the moment it finishes, as
    claudecode.update_done does for Claude Code (B249): the job's last line
    names what it measured."""
    if state != "succeeded" or nodes is None or not job:
        return None
    a = next((x for x in tracked() if x.update_job == job.get("type")), None)
    if not a:
        return None
    full = nodes.job(job["id"], with_log=True) or {}
    if (job.get("spec") or full.get("spec") or {}).get("action") == "remove":
        nodes.reported_set(job["node"], "session", a.reported, "")
        return None
    m = re.search(re.escape(a.product) + r" (\d[\w.+-]*) is what a session here runs now", full.get("log") or "")
    if m:
        nodes.reported_set(job["node"], "session", a.reported, m.group(1))
    return None


def row(n, agent_id):
    """This agent as a row of the Library and the Installed page, in claude_row's
    shape, or None on a node that runs no session account."""
    a = agents.get(agent_id)
    se = (n.get("reported") or {}).get("session") or {}
    if not a or n.get("kind") != "agent" or not se.get("up") or (n.get("config") or {}).get("host_only"):
        return None
    inst = installed(n, a.id)
    cur = latest(a.id)
    job = next(iter(nodes.jobs_for(node_id=n["id"], type=a.update_job, n=1) or []), None) if nodes else None
    running = updating(n["id"], a.id)
    failed = (job or {}).get("state") == "failed" and not running
    return {"name": a.tool, "agent": a.id, "label": a.product, "for": a.name,
            "installed": inst, "latest": cur.get("version") or "",
            "state": ("absent" if not inst else "update" if behind(n, a.id) else "current"),
            "managed": bool((n.get("reported") or {}).get("sandbox")), "here": bool(inst),
            "running": running, "action": ((job or {}).get("spec") or {}).get("action") or "install",
            "error": str((job or {}).get("error") or "")[:200] if failed else "",
            "checked": int(cur.get("at") or 0), "check_error": cur.get("error") or ""}


def claude_row(n):
    """Claude Code as a row of the Library and the Installed page (R145, R95), or None on
    a node that runs no session account: what a Claude session there runs,
    installed on purpose rather than by the provisioner. The version is the
    census's (claude --version as the session account); the latest is
    claudecode's check; the job behind install, update and remove is
    claudecode's, which ends the node's Claude sessions first."""
    se = (n.get("reported") or {}).get("session") or {}
    # A hosting-only node runs no session, so nothing there runs Claude
    # Code: no row, whatever its census says (the operator, 11 Oct).
    if not claudecode or n.get("kind") != "agent" or not se.get("up") or (n.get("config") or {}).get("host_only"):
        return None
    inst = claudecode.installed(n)
    cur = claudecode.latest()
    job = next(iter(nodes.jobs_for(node_id=n["id"], type=claudecode.JOB, n=1) or []), None) if nodes else None
    running = claudecode.updating(n["id"])
    failed = (job or {}).get("state") == "failed" and not running
    return {"name": "claude-code", "agent": "claude", "label": "Claude Code", "for": "Claude", "installed": inst,
            "latest": cur.get("version") or "",
            "state": ("absent" if not inst else "update" if claudecode.behind(n) else "current"),
            "managed": bool((n.get("reported") or {}).get("sandbox")), "here": bool(inst),
            "running": running, "action": ((job or {}).get("spec") or {}).get("action") or "install",
            "error": str((job or {}).get("error") or "")[:200] if failed else "",
            "checked": int(cur.get("at") or 0), "check_error": cur.get("error") or ""}


def rows(n):
    """Every coding agent's row for a node in the Library and on the Installed page, Claude's first."""
    return [r for r in (claude_row(n), *(row(n, a.id) for a in tracked())) if r]


def verb(principal, req):
    """The coding agents' presses in the Library and on the Installed page (R95, the operator 22 Oct: the one way an
    agent is installed): install (or update), remove or check, for one
    agent on one node. The caller has decided who may. (payload, status)."""
    action = str(req.get("action") or "")
    nid = str(req.get("node") or "")
    if action == "check":
        out = {"ok": True}
        if claudecode:
            c = claudecode.check()
            out["claude"] = {"version": c.get("version") or "", "error": c.get("error") or ""}
        for aid, c in check_all().items():
            out[aid] = {"version": c.get("version") or "", "error": c.get("error") or ""}
        return out, 200
    a = agents.get(req.get("agent"))
    if action not in ("install", "remove") or not a or not a.tool:
        return {"error": "install, remove or check, for one of the coding agents"}, 400
    if a.id == "claude":
        if not claudecode:
            return {"error": "Claude Code is not managed here"}, 400
        r = claudecode.update(principal, nid) if action == "install" else claudecode.remove(principal, nid)
    else:
        r = update(principal, nid, a.id) if action == "install" else remove(principal, nid, a.id)
    return r, (400 if r.get("error") else 200)


def start(delay=None):
    """One check of each soon after the controller starts; after that on the
    toolchains' clock and on a press, as Claude Code's."""
    wait = float(os.environ.get("BB_CLAUDE_CHECK_DELAY") or 20) if delay is None else delay

    def once():
        time.sleep(wait)
        try:
            check_all()
        except Exception as e:                                      # noqa: BLE001 (a thread must not die loudly)
            print(f"dashboard: coding agent check: {e}", flush=True)
    threading.Thread(target=once, name="agent-code", daemon=True).start()
