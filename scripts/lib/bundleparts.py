"""What a release ships in the bundle a node fetches, said one way.

A node fetches aerie, its library, the catalog and root's tools from its
controller as one tar. Three things have to agree on which files those are
and what they hold: the controller, which packs the tar from its install's
own files (scripts/dashboard/workspace.py bundle); the build's signer, which
signs the list of them as the tree holds them (tools/sign-agent.py); and a
node that pinned AerieOS's release key, which holds every file it is sent to
that signed list (the agent's release.may_keep_bundle). They read the parts
and make the list here, so a file one of them counts and another does not is
not possible.

The list is one line a file, its sha256 and its name in the bundle with two
spaces between, in the names' order: the form of a SHA256SUMS file. What is
signed is the digest of that text.

Python's bytecode is no part of it: the image compiles the scripts where it
is built and a checkout holds none, so a list that counted it would differ
between the two for no change in any file a person wrote. Neither is the
file a Mac's file manager leaves in a folder, which no image is sent.

Stdlib only, and importable alone: the signer loads it without the
dashboard.
"""
import hashlib
import os

# bb-tty and the two hooks it writes into a session's settings ride along
# since roadmap #24: a node runs sessions from this same bundle. NOT the
# rest of scripts/dashboard (the notebook modules, users.py, server.py),
# because a node has no /config for them to read; the verbs that need them
# are relayed back to the controller (server._bb_relay).
PARTS = ("scripts/aerie", "scripts/lib", "config/toolchains.json",
         # The publishers' release keys a download is checked against (R137).
         "config/release-keys",
         "nodes/provision-linux.sh", "nodes/families",
         # The root helper that builds a session's view, which the
         # agent installs from here on a sandbox node (R35).
         "nodes/bb-session",
         # ...and the one that cuts the network for a declared pack's
         # install steps where the job account cannot (R234).
         "nodes/bb-netcut",
         "scripts/dashboard/bb-tty", "scripts/dashboard/bb-work-note",
         "scripts/dashboard/bb-prompt-relay", "scripts/dashboard/bb-check-relay",
         "scripts/dashboard/bb-rule-hook",
         # ...and the other coding agents' one hook, which runs these
         # (R95 step 6): their hooks files name it in this bundle.
         "scripts/dashboard/bb-agent-hook",
         # ...and the agents' table it reads the aerie verbs a session
         # is not asked about from (bb-agent-hook --allow, and an
         # agent approved by its hook): without it no session on a
         # node was handed them.
         "scripts/dashboard/agents.py",
         # ...and what trusts Codex's for a launch (B284).
         "scripts/dashboard/bb-codex-trust",
         # The gate, which refuses every tool call while the
         # controller is not answering, so a node's sessions stop for
         # an update the same way the controller's do.
         "scripts/dashboard/bb-gate",
         # The record documents aerie design show NAME, aerie wiki and bb
         # roadmap --format print, which the verbs in scripts/lib
         # import from beside the dashboard (B426: a node's bb
         # had no records module).
         "scripts/dashboard/records.py",
         # ...and the agent package's __init__.py, whose AGENT_VERSION says
         # which build these files are: a node that pinned a release key
         # takes none older than its own agent (the agent's
         # release.BUNDLE_BUILD, may_keep_bundle).
         "scripts/agent/aerieos_agent/__init__.py")

# What is under a part and is not one of its files: Python's caches, which
# an image holds and a checkout does not, and a Mac's folder file.
SKIP_DIRS = ("__pycache__",)
SKIP_FILES = (".DS_Store",)
SKIP_ENDS = (".pyc",)


def missing(root, parts=PARTS):
    """The parts `root` does not hold, in the parts' order."""
    return [p for p in parts if not os.path.exists(os.path.join(str(root), p))]


def files(root, parts=PARTS):
    """Every file under the parts as `root` holds them: (its name in the
    bundle, its path) pairs in the names' order. A part that is not there
    gives none (missing() names it)."""
    root, out = str(root), {}
    for part in parts:
        top = os.path.join(root, part)
        if os.path.isfile(top):
            out[part] = top
            continue
        for d, dirs, names in os.walk(top):
            dirs[:] = [x for x in dirs if x not in SKIP_DIRS]
            for n in names:
                path = os.path.join(d, n)
                if n in SKIP_FILES or n.endswith(SKIP_ENDS) or not os.path.isfile(path):
                    continue
                out[os.path.relpath(path, root).replace(os.sep, "/")] = path
    return sorted(out.items())


def _sha256(what):
    """The sha256 of a file's bytes: `what` is the bytes, or a path to them."""
    if isinstance(what, (bytes, bytearray)):
        return hashlib.sha256(what).hexdigest()
    h = hashlib.sha256()
    with open(what, "rb") as f:
        for chunk in iter(lambda: f.read(1 << 20), b""):
            h.update(chunk)
    return h.hexdigest()


def listing(of):
    """(text, digest): the list of a bundle's files and what a release
    signs for it. `of` is a tree's root, whose files() are listed, or pairs
    of (name in the bundle, the file's bytes or its path). A name is on one
    line, so one that holds a line break is refused."""
    pairs = files(of) if isinstance(of, (str, os.PathLike)) else of
    held = {}
    for name, what in pairs:
        if "\n" in name or "\r" in name:
            raise ValueError(f"a file's name holds a line break: {name!r}")
        held[name] = _sha256(what)
    text = "".join(f"{held[name]}  {name}\n" for name in sorted(held))
    return text, "sha256:" + hashlib.sha256(text.encode("utf-8")).hexdigest()
