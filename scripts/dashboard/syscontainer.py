"""A System container on a node: one compose file, written and built as
AerieOS's own.

nginx (nginxproxy.py) and the model router (router.py) are each one compose
file generated from what their module keeps, written through
containers.create_container as a System container on a node and built by a
compose job there, so the Containers page lists it with Up, Down and its
log. What the two do alike is here as plain functions handed what differs:
the name, the compose text, and what one of them does on the way. nginx
pins its image before a new file is made and claims a container from
before System existed before a saved one is; the router stamps its record
once the container is made and clears it once the container is gone. Each
module keeps its own deploy, apply and remove, which call these.

The Scanners (scanners.py) are a compose job of their own on the node and
never a written container, so of this file they use the name and the
directory slug alone.

`containers`, `devactions` and `devapp` are handed to each function as the
server hands them to the two modules, so a test passes its own; hands
is those three for a caller that was handed none.
"""
import re


def hands():
    """(containers, devactions, devapp): the modules a written container is
    made, built and removed through. Imported when asked, since containers
    reads the services' modules itself."""
    import containers                                       # noqa: PLC0415
    import devactions                                       # noqa: PLC0415
    import devapp                                           # noqa: PLC0415
    return containers, devactions, devapp


def node_slug(nid):
    """A node's id as one directory name under the state directory."""
    return re.sub(r"[^A-Za-z0-9_-]", "_", str(nid))


def container_name(prefix, node):
    """PREFIX-<node>, kept to the characters a compose project name may
    have and to sixty of them. `node` is the node's name, or its id where
    it has none."""
    base = re.sub(r"[^a-z0-9-]", "-", str(node).lower()).strip("-") or "node"
    return f"{prefix}-{base}"[:60]


def deployed(devapp, name, nid):
    """Whether the container of that name is on this node: written by
    AerieOS (a file source under its name) and bound to this node."""
    return bool(devapp.is_file_source(name) and devapp._read_rec(name, devapp.MAIN).get("node") == nid)


def indent(text, n, every_break=False):
    """`text` moved n spaces in for a compose config's block scalar, an
    empty line left empty. A line ends at a newline alone and the text's
    trailing newlines are dropped; with every_break it ends wherever
    str.splitlines ends one (a carriage return, a form feed and the Unicode
    separators too) and only the last line's own break is dropped."""
    pad = " " * n
    lines = text.splitlines() if every_break else text.rstrip("\n").split("\n")
    return "\n".join(pad + ln if ln else "" for ln in lines)


def deploy(nid, name, text, containers, devactions, devapp, node_list, first=None, made=None):
    """The container made on the node from its compose file, then built:
    {ok, name, job}, {ok, name, note} when it was made and the build could
    not start, or {error}. `text` makes the compose file once the name is
    known to be free, after `first` where one is given; `made` runs once
    the container is written, before it is built."""
    if devapp.is_file_source(name):
        # The name is the node's name: one left by an uninstalled node of the
        # same name, whose machine is gone, is this node's to take.
        was = devapp._read_rec(name, devapp.MAIN).get("node")
        live = {n["id"] for n in node_list() if n.get("state") != "retired"}
        if was == nid or was in live:
            return {"error": f"{name} is already on the Containers page"}
        devapp.forget_container(name)
    if first:
        first()
    # AerieOS's own: System's, which no picker sets.
    r = containers.create_container(name, text(), "", node=nid, for_project=devapp.SYSTEM)
    if r.get("error"):
        return r
    if made:
        made()
    b = devactions.rebuild(name, devapp.MAIN, gate=False)
    if b.get("error"):
        return {"ok": True, "name": name, "note": f"made, but not built: {b['error']}"}
    return {"ok": True, "name": name, "job": b.get("job")}


def apply(name, text, containers, devactions, devapp, first=None):
    """A deployed container given its new compose file and rebuilt, so what
    was saved is what runs; nothing to do where it is not deployed yet.
    `text` makes the file once the container is known to be there, after
    `first` where one is given."""
    if not devapp.is_file_source(name):
        return {"ok": True, "deployed": False}
    if first:
        first()
    r = containers.update_container(name, text(), "")
    if r.get("error"):
        return r
    b = devactions.rebuild(name, devapp.MAIN, gate=False)
    if b.get("error"):
        return {"ok": True, "deployed": True, "note": f"saved, but not rebuilt: {b['error']}"}
    return {"ok": True, "deployed": True, "job": b.get("job")}


def remove(name, devactions, devapp, gone=None):
    """The container taken out of the manager like any written one, and
    what that answered. `gone` runs after it, whatever the answer was."""
    if not devapp.is_file_source(name):
        return {"error": f"{name} is not on the Containers page"}
    r = devactions.remove_instance(name, devapp.MAIN)
    if gone:
        gone()
    return r
