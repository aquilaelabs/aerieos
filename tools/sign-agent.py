#!/usr/bin/env python3
"""Sign what a build sends its nodes with AerieOS's release key (R227 step 1,
R267 step 6).

A node that pinned the release key takes an agent update only when a
signature under it covers the update's digest, and the bundle it fetches
from its controller only when one covers the list of the files a release
ships in it (scripts/agent/aerieos_agent/release.py). This makes those
signatures at build time, from the key a release build is handed and no
controller holds. scripts/agent/agent.sig carries three, each under a line
of its own so none passes as another: over the agent's zip, over the tools
root installs from the bundle, and over the list of every file the bundle
ships (scripts/lib/bundleparts.py: aerie, its library, the shipped catalog,
the publishers' keys, root's tools, the hooks).

    tools/sign-agent.py --keygen
        a new key pair, printed once: the private half for the build's
        secret (AERIEOS_RELEASE_KEY), the public half for
        config/aerieos-release.pub, which is committed.
    AERIEOS_RELEASE_KEY=... tools/sign-agent.py
        writes scripts/agent/agent.sig for the agent, root's tools and the
        bundle's files as this tree holds them. With no key in the
        environment it writes nothing and says so: a build from a branch
        ships unsigned.
    tools/sign-agent.py --check
        whether scripts/agent/agent.sig is the committed public key's
        signature over this tree's agent, root's tools and the bundle's
        files, all three: exit 0 when it is, 1 when not.
    tools/sign-agent.py --digests
        the three digests this tree would be signed as, one a line with its
        name, and nothing written: for comparing a build with a checkout
        (the Nodes page's status names the bundle's as `files`).
    tools/sign-agent.py --builder-keygen FILE
        a builder's own key, for whoever builds a controller on their own
        machine: the private half written to FILE (never printed), the
        public half printed with the command that adds it at a node's
        console. Not a release key: it goes in no repository.
    tools/sign-agent.py --builder FILE [--out SIG]
        signs this tree's agent, root's tools and the bundle's files with
        the key in FILE, whatever config/aerieos-release.pub names: a node
        takes the build
        once a person has added the key at its console (aerieos-agent
        release-key add), and no other node does. tools/build-image-here.sh
        runs this after its build.

The key never goes on a command line and is never printed after --keygen.
The bytes signed are release.MESSAGE and the digest the controller's hello
names, so the signature is of the sources (bundle.py builds the same zip
from the same sources anywhere). The bundle's list is of the tree's files
as they are, so it is signed from the tree the image is built from and
nothing may rewrite one of those files on the way into the image
(scripts/dashboard/unit/test_bundle_files_in_image.py).
"""
import hashlib
import importlib
import json
import os
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
AGENT = os.path.join(HERE, "..", "scripts", "agent")
SIG = os.path.join(AGENT, "agent.sig")
# The committed public key; a test names another file.
PUB = os.environ.get("AERIEOS_RELEASE_PUB") or os.path.join(HERE, "..", "config", "aerieos-release.pub")


def _load(name):
    """One of the agent's own modules, as the agent loads it (its package)."""
    if AGENT not in sys.path:
        sys.path.insert(0, AGENT)
    return importlib.import_module("aerieos_agent." + name)


def digest():
    return "sha256:" + hashlib.sha256(_load("bundle").build(AGENT)).hexdigest()


def tools_digest():
    """The digest of the tools root installs from the bundle, as this tree
    holds them and as a node works it out from the bundle it was sent
    (release.tools_digest): the files base.ROOT_TOOLS names and the
    provisioner's family files, each by its name in the bundle."""
    root = os.path.join(HERE, "..")
    names = list(_load("base").ROOT_TOOLS)
    fam = os.path.join(root, "nodes", "families")
    for d, _dirs, files in os.walk(fam):
        names += [os.path.relpath(os.path.join(d, f), root).replace(os.sep, "/") for f in files]
    held = {}
    for name in names:
        with open(os.path.join(root, name), "rb") as f:
            held[name] = f.read()
    return _load("release").tools_digest(held)


def _lib(name):
    """One of scripts/lib's modules, which the controller reads too."""
    lib = os.path.join(HERE, "..", "scripts", "lib")
    if lib not in sys.path:
        sys.path.insert(0, lib)
    return importlib.import_module(name)


def bundle_digest():
    """The digest of the list of the files a release ships in the bundle,
    as this tree holds them: what the controller's bundle carries as
    nodes/bundle.list when its install's files are these, and what a node
    works out from the list it was sent (scripts/lib/bundleparts.py)."""
    return _lib("bundleparts").listing(os.path.join(HERE, ".."))[1]


def _pub():
    """(keys, why) as the file's one reader answers (scripts/lib/releasepub.py,
    the Enroll script's and aerie lint's too): the keys it names, or none and
    what is wrong with it."""
    return _lib("releasepub").read(PUB)


def public_keys():
    """The keys the committed file names: the one the builds sign with, then
    its spare (R232). A node pins both, so a build signed by either is taken."""
    return _pub()[0]


def public_key():
    return (public_keys() or [""])[0]


def _write(key, path):
    """The signature file for this tree's agent, root's tools and the
    bundle's files under `key`, written to `path`: what was signed, in
    words (each digest shortened)."""
    release = _load("release")
    d, t, b = digest(), tools_digest(), bundle_digest()
    out = {"digest": d, "sig": key.sign(release.MESSAGE + d.encode()).hex(), "key": key.public_key().public_bytes_raw().hex(),
           # The tools root installs from the bundle, under a line of their
           # own: the controller puts this in the bundle it serves.
           "tools": {"digest": t, "sig": key.sign(release.TOOLS_MESSAGE + t.encode()).hex()},
           # ...and the list of every file a release ships in that bundle,
           # under a third line: the controller passes it on beside the list.
           "bundle": {"digest": b, "sig": key.sign(release.BUNDLE_MESSAGE + b.encode()).hex()}}
    with open(path, "w", encoding="utf-8") as f:
        json.dump(out, f)
        f.write("\n")
    return f"the agent {d[:19]}…, root's tools {t[:19]}… and the bundle's files {b[:19]}…"


def _console(pub):
    """What a person does with a builder's public key, said once."""
    return ("A node that pinned AerieOS's release key takes a build signed with this one once a person adds it at that\n"
            f"node's own console:  sudo aerieos-agent release-key add {pub}\n"
            "A node whose agent is from before that verb (it answers that the release key is 64 hex characters, and\n"
            "changes nothing) cannot be told the key yet, and refuses the build that would teach it. There, once:\n"
            "  sudo aerieos-agent unsigned on    then let its agent update (Update agent on its row, or wait)\n"
            f"  sudo aerieos-agent release-key add {pub}\n"
            "  sudo aerieos-agent unsigned off")


def _builder_keygen(args, Ed25519PrivateKey):
    """--builder-keygen FILE: a builder's key made where none is, its private
    half in FILE for this machine's account alone; one that is there is kept
    and its public half said again."""
    if len(args) != 1:
        print("usage: tools/sign-agent.py --builder-keygen FILE", file=sys.stderr)
        return 2
    path = args[0]
    if os.path.exists(path):
        key = _builder_key(path, Ed25519PrivateKey)
        if key is None:
            return 2
        print(f"{path} holds a builder's key already; it is kept. Its public half:")
    else:
        key = Ed25519PrivateKey.generate()
        os.makedirs(os.path.dirname(os.path.abspath(path)), mode=0o700, exist_ok=True)
        fd = os.open(path, os.O_WRONLY | os.O_CREAT | os.O_EXCL, 0o600)
        with os.fdopen(fd, "w", encoding="utf-8") as f:
            f.write(key.private_bytes_raw().hex() + "\n")
        print(f"made a builder's key at {path} (keep it on this machine; it is not a release key and goes in no repository). "
              "Its public half:")
    pub = key.public_key().public_bytes_raw().hex()
    print("  " + pub)
    print(_console(pub))
    return 0


def _builder_key(path, Ed25519PrivateKey):
    """The key a builder's file holds, or None with the reason said."""
    try:
        with open(path, encoding="utf-8") as f:
            seed = f.read().strip().lower()
        return Ed25519PrivateKey.from_private_bytes(bytes.fromhex(seed))
    except OSError as e:
        print(f"the builder's key at {path} cannot be read ({e.strerror or e})", file=sys.stderr)
    except ValueError:
        print(f"{path} does not hold a builder's key: 64 hex characters, as --builder-keygen writes", file=sys.stderr)
    return None


def _builder_sign(args, Ed25519PrivateKey):
    """--builder FILE [--out SIG]: this tree's agent, root's tools and the
    bundle's files signed with a builder's own key, whatever the committed
    file names."""
    out = SIG
    if "--out" in args:
        i = args.index("--out")
        out, args = (args[i + 1] if i + 1 < len(args) else ""), args[:i] + args[i + 2:]
    if len(args) != 1 or not out:
        print("usage: tools/sign-agent.py --builder FILE [--out SIG]", file=sys.stderr)
        return 2
    key = _builder_key(args[0], Ed25519PrivateKey)
    if key is None:
        return 2
    pub = key.public_key().public_bytes_raw().hex()
    if pub in public_keys():
        print("that is a release key, not a builder's: a release's build signs with AERIEOS_RELEASE_KEY", file=sys.stderr)
        return 2
    print(f"signed {_write(key, out)} with this builder's key {pub[:16]}…")
    print(_console(pub))
    return 0


def main(argv):
    if argv[:1] == ["--digests"]:
        # Read-only, and with no key or signature in it: what this tree
        # would be signed as, for a person holding a build against it.
        print(f"agent   {digest()}\ntools   {tools_digest()}\nbundle  {bundle_digest()}")
        return 0
    try:
        from cryptography.hazmat.primitives.asymmetric.ed25519 import Ed25519PrivateKey
    except ImportError:
        # Said, with a way that installs nothing on this machine: a NAS's own
        # Python has no pip worth using, and a traceback named neither.
        print("this needs Python's cryptography library, which this machine's Python does not have. Either\n"
              "  python3 -m pip install cryptography\n"
              "or, installing nothing here, from the repository's folder:\n"
              "  docker run --rm -v \"$PWD\":/src -w /src python:3.12-slim \\\n"
              "    sh -c 'pip install -q cryptography && python3 tools/sign-agent.py " + " ".join(argv) + "'",
              file=sys.stderr)
        return 3
    release = _load("release")
    if argv[:1] == ["--keygen"]:
        key = Ed25519PrivateKey.generate()
        print("private (the build's secret AERIEOS_RELEASE_KEY; keep it nowhere else):")
        print("  " + key.private_bytes_raw().hex())
        print("public (one line added to config/aerieos-release.pub, committed: the first line is the key")
        print("the builds sign with, a second is its spare, whose private half is kept apart from the build's):")
        print("  aerieos-release-ed25519 " + key.public_key().public_bytes_raw().hex())
        return 0
    if argv[:1] == ["--check"]:
        try:
            with open(SIG, encoding="utf-8") as f:
                got = json.load(f)
        except (OSError, ValueError) as e:
            print(f"no usable {os.path.relpath(SIG)}: {e}")
            return 1
        if _pub()[1]:
            print(f"{os.path.relpath(PUB)}: {_pub()[1]}, so there is no key to check {os.path.relpath(SIG)} under")
            return 1
        why, by = "it is for another agent than this tree builds", ""
        if got.get("digest") == digest():
            # Under either key the file names: the builds' own, or its spare.
            for k in public_keys() or [""]:
                why = release.verify(k, got.get("digest"), got.get("sig"))
                if not why:
                    by = k
                    break
        print(f"{os.path.relpath(SIG)}: " + (why or f"signed by {by[:16]}… for {digest()[:19]}…"))
        # ...and root's tools, signed beside it under their own line.
        tools = got.get("tools") if isinstance(got.get("tools"), dict) else {}
        twhy = "it carries no signature for the tools root installs" if not tools else \
            "it is for other tools than this tree holds" if tools.get("digest") != tools_digest() else \
            next((w for w in [release.verify(by or public_key(), tools.get("digest"), tools.get("sig"), release.TOOLS_MESSAGE)] if w), "")
        print(f"{os.path.relpath(SIG)}: root's tools: " + (twhy or f"signed by {(by or public_key())[:16]}… for {tools_digest()[:19]}…"))
        # ...and the list of the bundle's files, under the third line: a
        # file of them changed after the signing is a signature that is not
        # whole, which is what fails a release's tag.
        part = got.get("bundle") if isinstance(got.get("bundle"), dict) else {}
        bwhy = "it carries no signature for the files the bundle ships" if not part else \
            "it is for other files than this tree's bundle ships" if part.get("digest") != bundle_digest() else \
            release.verify(by or public_key(), part.get("digest"), part.get("sig"), release.BUNDLE_MESSAGE)
        print(f"{os.path.relpath(SIG)}: the bundle's files: " + (bwhy or f"signed by {(by or public_key())[:16]}… for {bundle_digest()[:19]}…"))
        return 1 if why or twhy or bwhy else 0
    if argv[:1] == ["--builder-keygen"]:
        return _builder_keygen(argv[1:], Ed25519PrivateKey)
    if argv[:1] == ["--builder"]:
        return _builder_sign(argv[1:], Ed25519PrivateKey)
    seed = os.environ.get("AERIEOS_RELEASE_KEY", "").strip().lower()
    if not seed:
        print("no AERIEOS_RELEASE_KEY in the environment: the agent ships unsigned, as a build from a branch does")
        return 0
    try:
        key = Ed25519PrivateKey.from_private_bytes(bytes.fromhex(seed))
    except ValueError:
        print("AERIEOS_RELEASE_KEY is not a release key: 64 hex characters, as --keygen prints", file=sys.stderr)
        return 2
    pub = key.public_key().public_bytes_raw().hex()
    # A file that does not parse names no key a node could pin, and the
    # Enroll script would hand new nodes none: nothing is signed over that.
    if _pub()[1]:
        print(f"{os.path.relpath(PUB)}: {_pub()[1]}, so no node could pin a key from it and nothing is signed", file=sys.stderr)
        return 2
    if pub not in public_keys():
        print("AERIEOS_RELEASE_KEY is not a key config/aerieos-release.pub names ("
              + ", ".join(k[:16] + "…" for k in public_keys()) + "): nodes pinned to those would refuse this build, "
              "so nothing is signed", file=sys.stderr)
        return 2
    print(f"signed {_write(key, SIG)} with the "
          + ("spare release key" if pub in public_keys()[1:] else "release key") + f" {pub[:16]}…")
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
