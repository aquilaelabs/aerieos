"""Which of the registry's rows are nodes work can go to, for the modules
that are handed the node list and import nothing of nodes.py."""


def live_agents(rows):
    """The agent nodes of `rows` that are enrolled and not retired: the ones
    a service, a scanner, a VM or a storage reading can be on."""
    return [n for n in rows if n.get("kind") == "agent" and n.get("state") not in ("retired", "pending")]
