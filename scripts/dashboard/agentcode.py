"""The coding agents on the nodes (R95 step 2, R145): which version of
Claude Code, Codex CLI, Copilot CLI and the others each node runs, what the
latest is, and the one way each is installed, updated or removed.

One pattern for every row of the agent table that has a row in the Library
(agents.installable()). A session runs on a node, and the node carries the
agent in the session account's home, installed there on purpose and never
by the provisioner. The node's agent probes its version on every heartbeat
(the census's session.<reported>), so the controller always knows what
each node runs. What is out is asked of the row's own source, an npm
registry or the installer's `latest` file, once after the controller
starts, then on the toolchains' clock (weekly, and when a node starts) and
on a press of Check for updates in the Library. A node behind says so on
its row, and in the bell's coding agents row for the node
(toolchains.agent_attention), which opens the Library on that node.

UPDATING IS A PERSON'S, NEVER A SESSION'S. Install in the Library is an
administrator's action (the node handler refuses anybody else, a session's
token included); it ends that agent's sessions on the node first, since a
conversation mid-turn is the wrong place to swap the binary under, and
queues a job the node's agent runs as the session account: the installer,
then, where the node's agent is root, a copy of the binary into a
root-owned directory the session's PATH reads before the account's own.
That copy is what a session runs and what the account cannot write, so
`claude update` typed in a session changes nothing that runs, and Claude
Code's auto-updater is off there already (bb-tty exports
DISABLE_AUTOUPDATER). Nobody starts the sessions again: the project rows
do, when a person presses them; while the job runs those starts are held
with the reason.

No bb verb reaches any of this, on purpose. What is Claude Code's alone,
a session needing it to start at all, is claudecode.py.
"""
import http.client
import json
import os
import re
import threading
import time
import urllib.request

import agents
import checks
from vers import vkey

VER = re.compile(r"(\d+\.\d+\.\d+)")
# What update and start_hold say, by key, where the agent's row has no
# wording of its own (Agent.says): {product} and {name} are the row's,
# {node} and {project} the names a person reads.
SAYS = {
    "no_account": "{node} runs no session account, so there is nowhere for {product} to go",
    "hold": ("{product} is updating on {node}: start {name} on {project} again when its "
             "row on the Installed page comes back"),
}

nodes = None               # nodes.py: node, node_list, job, job_add, jobs_for, session_kill, reported_set
node_sessions = None       # server.node_tmux_sessions
tmux_base = None           # server.tmux_base
audit = None
_lock = threading.Lock()
_latest = {}               # {agent id: {version, at, error, checking}}
# {(agent id, node id): when} for an update pressed and not yet queued:
# ending the node's sessions comes first and is a round trip each, and in
# those seconds the hold read nothing, so a project's Claude button was live
# and a press on it started a session the update was about to end (the
# operator, 29 Sep). The job is the fact once it exists; this is the fact
# until then.
_pressed = {}
catalog_entry = None       # server: the signed index's official entry of this name, or None
fetch_pack = None          # toolpacks.fetch
_recipes = {}              # {(agent id, commit): (the catalog's recipe there or None, when read, why not)}
RECIPE_MISS_S = 300        # a pack that could not be fetched is asked again after this long
_warming = threading.Event()   # a read-ahead of the catalog's recipes is running


def configure(*, nodes_module, node_sessions, tmux_base, audit=None, catalog_entry=None, fetch_pack=None):
    globals().update(nodes=nodes_module, node_sessions=node_sessions,
                     tmux_base=tmux_base, audit=audit,
                     catalog_entry=catalog_entry, fetch_pack=fetch_pack)


def _ahead(a):
    """The catalog's entry for this agent when the signed index says its
    recipe is newer than the table's (the entry's install_rev), else None.
    Nothing is fetched to know: the index as last read says it."""
    entry = catalog_entry(a.id) if a and a.install and catalog_entry and fetch_pack else None
    return entry if entry and int(entry.get("install_rev") or 0) > a.install["rev"] else None


def recipe(agent_id):
    """(recipe, "catalog" or "release"): how this agent is installed, as
    the node is handed it with every install, update and removal (R169 step
    13). The agent table's own, which shipped with this release, unless the
    catalog's signed index pins this agent's pack with a higher rev: then
    the catalog's, fetched at that commit with its archive's sha256 checked
    and the manifest held to its shape, as any pack's is. A pack that is
    refused, or one no newer than the table after all, leaves the table's.

    The network is asked only when the index names a newer recipe not read
    yet, once per commit (warm reads it ahead, behind the Library): a press
    on Update otherwise waits for nothing, which matters, since the node's
    sessions are ended right after and a slow press ended none (the node
    had stopped counting as live)."""
    a = agents.get(agent_id)
    own = a.install if a else None
    entry = _ahead(a)
    if not entry:
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
    if theirs and theirs["rev"] > own["rev"]:
        return theirs, "catalog"
    return own, "release"


def warm():
    """Read, in a thread of its own, each newer recipe the index names
    that has not been read yet. Called from the Library's read: by the time
    a person presses Update the recipe is here. Nothing starts when there
    is nothing newer, which is nearly always."""
    with _lock:
        todo = [a.id for a in agents.TABLE if (e := _ahead(a)) and (a.id, e["commit"]) not in _recipes]
        if not todo or _warming.is_set():
            return
        _warming.set()

    def work():
        try:
            for aid in todo:
                recipe(aid)
        except Exception as e:                                      # noqa: BLE001 (a thread must not die loudly)
            print(f"dashboard: coding agent recipes: {e}", flush=True)
        finally:
            _warming.clear()
    threading.Thread(target=work, name="agent-recipes", daemon=True).start()


def recipe_spec(agent_id):
    """A job's spec words for the recipe: {recipe, recipe_from}, or {} for
    an agent with none (an agent from before this runs its own table)."""
    r, where = recipe(agent_id)
    return {"recipe": r, "recipe_from": where} if r else {}


def tracked():
    """The agents this module keeps: every one the Library installs, Claude
    first."""
    return agents.installable()


def _agent(agent_id):
    a = agents.get(agent_id)
    if not a or a not in tracked():
        raise KeyError(agent_id)
    return a


def _say(a, key, **names):
    """One of SAYS for this agent, in its row's own wording where it has one."""
    return ((a.says or {}).get(key) or SAYS[key]).format(product=a.product, name=a.name, **names)


def latest_url(a):
    """Where this agent's newest release is asked: its registry's answer or
    its installer's own `latest` file, or a test's file:// stand-in
    (BB_CLAUDE_LATEST_URL, BB_CODEX_LATEST_URL, BB_COPILOT_LATEST_URL,
    BB_GROK_LATEST_URL)."""
    return os.environ.get(f"BB_{a.id.upper()}_LATEST_URL") or a.latest_url or a.latest_file


def check(agent_id):
    """Ask what the latest release of this agent is, now. The record."""
    a = _agent(agent_id)
    # What answers, as an error names it: a row's `latest` file is its
    # maker's download service's, anything else a registry's.
    asked = "download service" if a.latest_file else "registry"

    def read():
        version, error = "", ""
        try:
            with urllib.request.urlopen(latest_url(a), timeout=15) as r:   # noqa: S310 (a fixed https URL from the table, or a test's file://)  # nosemgrep: python.lang.security.audit.dynamic-urllib-use-detected.dynamic-urllib-use-detected
                text = r.read(65536).decode("utf-8", "replace").strip()
            # A registry's document names the version, and one that answers
            # plainly is read as it stands; a `latest` file is only ever the
            # version itself, so a document there is not an answer.
            try:
                got = text if a.latest_file else str((json.loads(text) or {}).get("version") or "")
            except (ValueError, AttributeError):
                got = text
            m = VER.match(got)
            if m:
                version = m.group(1)
            else:
                error = f"unexpected answer from the {asked}: {got[:40]!r}"
        except (OSError, http.client.HTTPException, ValueError) as e:   # URLError and a timeout are OSErrors; a bad URL is a ValueError
            error = f"could not reach the {asked}: {e}"[:200]
        return ({"version": version} if version else {}), error
    return checks.guarded(
        _lock, lambda: _latest.setdefault(a.id, {"version": "", "at": 0, "error": "", "checking": False}), read)


def check_all():
    return {a.id: check(a.id) for a in tracked()}


def latest(agent_id):
    with _lock:
        return dict(_latest.get(agent_id) or {"version": "", "at": 0, "error": "", "checking": False})


def installed(n, agent_id):
    """The version a node reports for this agent, or "" (no session account,
    or none of this agent for it): `1.2.3` out of `1.2.3 (Claude Code)`,
    `0.163.0` out of `codex-cli 0.163.0`, `1.0.102` out of
    `GitHub Copilot CLI 1.0.102.`"""
    a = agents.get(agent_id)
    if not a:
        return ""
    m = VER.search(str(((n.get("reported") or {}).get("session") or {}).get(a.reported) or ""))
    return m.group(1) if m else ""


def behind(n, agent_id):
    i, cur = installed(n, agent_id), latest(agent_id)["version"]
    return bool(i and cur and vkey(i) < vkey(cur))


def updating(node_id, agent_id):
    """True while this agent's job is queued or running on the node: the
    fact the holds and the rows read, taken from the job list rather than a
    flag, so a restart cannot leave a hold up with nothing behind it."""
    if nodes is None:
        return False
    a = agents.get(agent_id)
    if time.time() - _pressed.get((agent_id, node_id), 0) < 120:
        return True
    return any(j.get("type") == a.update_job
               for j in nodes.jobs_for(node_id, n=20, type=a.update_job, active=True))


def start_hold(project, node_id, agent_id):
    """A sentence when a session of this agent on this node has to wait,
    or "": its update running there holds every start until it ends (R95
    step 18). Nothing updates by itself: a node stays on what it has until
    Update is pressed (the switch that updated a node behind before a
    session started went on 7 Oct, the operator's)."""
    n = nodes.node(node_id) if nodes else None
    a = agents.get(agent_id)
    if not n or not a or n.get("kind") != "agent":
        return ""
    if updating(node_id, agent_id):
        return _say(a, "hold", node=n["name"], project=project)
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
    there ended first. The caller has already decided who may ask: the node
    handler, which is an administrator's and refuses a session's token."""
    a = _agent(agent_id)
    n = nodes.node(node_id) if nodes else None
    if not n:
        return {"error": "no such node"}
    if n.get("kind") != "agent":
        return {"error": f"only an agent node runs {a.product}"}
    if not n.get("live"):
        return {"error": f"{n['name']} is not dialing in; nothing reaches it right now"}
    if not ((n.get("reported") or {}).get("session") or {}).get("up"):
        return {"error": _say(a, "no_account", node=n["name"])}
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
    """Queue the job that takes this agent off the node (R145), the update
    job's other action, its sessions there ended first."""
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
    """The census catches up with an install the moment it finishes (B249).
    The version the controller compares rides the node's census, which
    rides its hello every ten minutes, so the bell and the row said an
    update was out for up to ten minutes after the job installed it. The
    job's last line names what it measured, and that is what the row says
    until the next hello replaces the whole record. The node says hello
    right after as well; this covers the seconds between, and a hello that
    did not land."""
    if state != "succeeded" or nodes is None or not job:
        return None
    a = next((x for x in tracked() if x.update_job == job.get("type")), None)
    if not a:
        return None
    full = nodes.job(job["id"], with_log=True) or {}
    # A removal (R145): none now, so the row and the session gate say so
    # before the next hello does.
    if (job.get("spec") or full.get("spec") or {}).get("action") == "remove":
        nodes.reported_set(job["node"], "session", a.reported, "")
        return None
    # The node writes the version as the program's --version prints it,
    # what follows the number included (Claude Code's own "(Claude Code)",
    # B167): matched with or without it, and kept on the value, which is
    # how the census itself reads.
    m = re.search(re.escape(a.product) + r" (\d[\w.+-]*)(?:" + re.escape(a.census_suffix)
                  + r")? is what a session here runs now", full.get("log") or "")
    if m:
        nodes.reported_set(job["node"], "session", a.reported, m.group(1) + a.census_suffix)
    return None


def row(n, agent_id):
    """This agent as a row of the Library and the Installed page (R145,
    R95), or None on a node that runs no session account: what a session
    of it there runs, installed on purpose rather than by the provisioner.
    The version is the census's (the program's --version as the session
    account), the latest this module's check, and the job behind install,
    update and remove this module's, which ends the agent's sessions on the
    node first."""
    a = agents.get(agent_id)
    se = (n.get("reported") or {}).get("session") or {}
    # A hosting-only node runs no session, so nothing there runs a coding
    # agent: no row, whatever its census says (the operator, 11 Oct).
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


def rows(n):
    """Every coding agent's row for a node in the Library and on the Installed page, Claude's first."""
    return [r for r in (row(n, a.id) for a in tracked()) if r]


def verb(principal, req):
    """The coding agents' presses in the Library and on the Installed page (R95, the operator 22 Oct: the one way an
    agent is installed): install (or update), remove or check, for one
    agent on one node. The caller has decided who may. (payload, status)."""
    action = str(req.get("action") or "")
    nid = str(req.get("node") or "")
    if action == "check":
        out = {"ok": True}
        for aid, c in check_all().items():
            out[aid] = {"version": c.get("version") or "", "error": c.get("error") or ""}
        return out, 200
    a = agents.get(req.get("agent"))
    if action not in ("install", "remove") or not a or not a.tool:
        return {"error": "install, remove or check, for one of the coding agents"}, 400
    r = update(principal, nid, a.id) if action == "install" else remove(principal, nid, a.id)
    return r, (400 if r.get("error") else 200)


def start(delay=None):
    """One check of each soon after the controller starts. After that each
    is asked on the toolchains' own clock (toolchains.node_checks_due:
    weekly, and when a node starts) and on a press of Check for updates,
    like every toolchain (R145). The update itself is never on a clock: a
    press."""
    wait = float(os.environ.get("BB_CLAUDE_CHECK_DELAY") or 20) if delay is None else delay

    def once():
        time.sleep(wait)
        try:
            check_all()
        except Exception as e:                                      # noqa: BLE001 (a thread must not die loudly)
            print(f"dashboard: coding agent check: {e}", flush=True)
    threading.Thread(target=once, name="agent-code", daemon=True).start()
