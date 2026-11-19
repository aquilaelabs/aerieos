"""Claude Code on the nodes: what is Claude Code's alone.

Claude Code is one of the coding agents agentcode.py keeps: its version on
each node, what the latest is, and its install, update and removal are that
module's, asked for "claude". What no other agent has is here. A session
needs Claude Code, so a node without it holds its spaces' starts and says
where it is installed (R145: the Library installs it on purpose, never the
provisioner), and the status payload carries each node's version against
the latest for the page.
"""
import agentcode
import agents

JOB = agents.get("claude").update_job      # "claude-update", from the agent table


def _agent_nodes():
    """The nodes a session can run on, as the node store lists them."""
    nodes = agentcode.nodes
    return [n for n in (nodes.node_list() if nodes else []) if n.get("kind") == "agent"]


def rows():
    out = {}
    for n in _agent_nodes():
        out[n["id"]] = {"name": n["name"], "installed": agentcode.installed(n, "claude"),
                        "behind": agentcode.behind(n, "claude"),
                        "updating": agentcode.updating(n["id"], "claude"), "live": bool(n.get("live"))}
    return out


def payload():
    """What the Nodes page reads: the latest known, when it was asked, and
    each agent node's own version against it."""
    cur = agentcode.latest("claude")
    return {"latest": cur["version"], "checked": cur["at"], "error": cur["error"],
            "checking": cur["checking"], "nodes": rows()}


def holds(reap=False):
    """{node id: why} while no session can start on a node's Claude Code:
    while it is being updated (the project rows start them again after),
    and where it is not installed at all, which the Library
    does on purpose (R145: the provisioner no longer installs it).

    reap: only the holds that end a session already running, for the
    sweep. Not installed is not one: a running session shows it was there,
    so the reading is stale or wrong, and the sweep ended the harness's
    sessions every second on it (B540); agentcode.remove ends them itself."""
    out = {}
    for n in _agent_nodes():
        if agentcode.updating(n["id"], "claude"):
            out[n["id"]] = (f"Claude Code is updating on {n['name']}: its Claude sessions were ended for "
                            "it, and start again from the space rows when it is done")
        elif missing(n) and not reap:
            out[n["id"]] = (f"Claude Code is not installed on {n['name']}: the Library installs it")
    return out


def missing_nodes():
    """The ids of the agent nodes that run sessions and have no Claude Code."""
    return {n["id"] for n in _agent_nodes() if missing(n)}


def missing(n):
    """True when a node runs a session account and has measured no Claude
    Code for it: a session there has nothing to run."""
    se = (n.get("reported") or {}).get("session") or {}
    return bool(se.get("up")) and not agentcode.installed(n, "claude")
