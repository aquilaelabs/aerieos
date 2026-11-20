#!/usr/bin/env python3
"""Sign the agent a build ships with AerieOS's release key (R227 step 1).

A node that pinned the release key takes an agent update only when a
signature under it covers the update's digest (scripts/agent/aerieos_agent/
release.py). This makes that signature at build time, from the key a
release build is handed and no controller holds:

    tools/sign-agent.py --keygen
        a new key pair, printed once: the private half for the build's
        secret (AERIEOS_RELEASE_KEY), the public half for
        config/aerieos-release.pub, which is committed.
    AERIEOS_RELEASE_KEY=... tools/sign-agent.py
        writes scripts/agent/agent.sig for the agent as this tree builds it.
        With no key in the environment it writes nothing and says so: a
        build from a branch ships unsigned.
    tools/sign-agent.py --check
        whether scripts/agent/agent.sig is the committed public key's
        signature over this tree's agent: exit 0 when it is, 1 when not.

The key never goes on a command line and is never printed after --keygen.
The bytes signed are release.MESSAGE and the digest the controller's hello
names, so the signature is of the sources (bundle.py builds the same zip
from the same sources anywhere).
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


def _pub():
    """(keys, why) as the file's one reader answers (scripts/lib/releasepub.py,
    the Enroll script's and aerie lint's too): the keys it names, or none and
    what is wrong with it."""
    lib = os.path.join(HERE, "..", "scripts", "lib")
    if lib not in sys.path:
        sys.path.insert(0, lib)
    import releasepub
    return releasepub.read(PUB)


def public_keys():
    """The keys the committed file names: the one the builds sign with, then
    its spare (R232). A node pins both, so a build signed by either is taken."""
    return _pub()[0]


def public_key():
    return (public_keys() or [""])[0]


def main(argv):
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
        return 1 if why or twhy else 0
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
    d, t = digest(), tools_digest()
    out = {"digest": d, "sig": key.sign(release.MESSAGE + d.encode()).hex(), "key": pub,
           # The tools root installs from the bundle, under a line of their
           # own: the controller puts this in the bundle it serves.
           "tools": {"digest": t, "sig": key.sign(release.TOOLS_MESSAGE + t.encode()).hex()}}
    with open(SIG, "w", encoding="utf-8") as f:
        json.dump(out, f)
        f.write("\n")
    print(f"signed the agent {d[:19]}… and root's tools {t[:19]}… with the "
          + ("spare release key" if pub in public_keys()[1:] else "release key") + f" {pub[:16]}…")
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
