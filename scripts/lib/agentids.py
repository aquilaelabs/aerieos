"""The coding agents that ship with AerieOS, by id, and the tool packs a
bundle carries, for the programs that have to tell the one from the other.

    SHIPPED            the shipped agents' ids
    packs_file(here)   the bundle's config/toolpacks.json
    pack_rows(here)    its rows

A pack that brings a coding agent never takes a shipped agent's name, so
whoever reads a pack's agent passes over these five first: login-list.py
(how a pack's agent signs in), bb-agent-hook (how one is held to its hooks)
and bb-tty, whose case of the targets that are no pack's names the same five
beside its own shell and ctr. The dashboard's table of the agents is
agents.py, and unit/test_agentids.py holds this list and bb-tty's to it.
Here, standard library only, because a node carries this folder and its root
reads a sign-in with nothing else on its path (python3 -I login-list.py).
"""
import json
import os

SHIPPED = ("claude", "codex", "copilot", "grok", "open")


def packs_file(here):
    """The tool packs this bundle carries, beside its catalog, or the file
    BB_TOOLPACKS_JSON names. `here` is the caller's own folder, two below
    the bundle's root, as the caller reads its own path: login-list.py as it
    was started, bb-agent-hook with its links followed, since a hook may be
    reached through one and the bundle is where the link leads."""
    return os.environ.get("BB_TOOLPACKS_JSON") or os.path.join(here, "..", "..", "config", "toolpacks.json")


def pack_rows(here):
    """That file's rows as it has them, [] when it cannot be read or holds
    no list of them. A row is checked by its reader: not every one is a
    dict, and few bring an agent."""
    try:
        with open(packs_file(here), encoding="utf-8") as f:
            rows = json.load(f).get("toolchains") or []
    except (OSError, ValueError, AttributeError):
        return []
    return rows if isinstance(rows, list) else []
