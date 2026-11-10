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
import importlib.util
import json
import os
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
AGENT = os.path.join(HERE, "..", "scripts", "agent")
SIG = os.path.join(AGENT, "agent.sig")
# The committed public key; a test names another file.
PUB = os.environ.get("AERIEOS_RELEASE_PUB") or os.path.join(HERE, "..", "config", "aerieos-release.pub")


def _load(name):
    spec = importlib.util.spec_from_file_location(name, os.path.join(AGENT, "aerieos_agent", name + ".py"))
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


def digest():
    return "sha256:" + hashlib.sha256(_load("bundle").build(AGENT)).hexdigest()


def public_key():
    try:
        with open(PUB, encoding="utf-8") as f:
            return next((ln.split()[-1].strip().lower() for ln in f if ln.strip() and not ln.startswith("#")), "")
    except OSError:
        return ""


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
        print("public (one line added to config/aerieos-release.pub, committed):")
        print("  aerieos-release-ed25519 " + key.public_key().public_bytes_raw().hex())
        return 0
    if argv[:1] == ["--check"]:
        try:
            with open(SIG, encoding="utf-8") as f:
                got = json.load(f)
        except (OSError, ValueError) as e:
            print(f"no usable {os.path.relpath(SIG)}: {e}")
            return 1
        why = "it is for another agent than this tree builds" if got.get("digest") != digest() \
            else release.verify(public_key(), got.get("digest"), got.get("sig"))
        print(f"{os.path.relpath(SIG)}: " + (why or f"signed by {public_key()[:16]}… for {digest()[:19]}…"))
        return 1 if why else 0
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
    if public_key() and public_key() != pub:
        print(f"AERIEOS_RELEASE_KEY is not the key config/aerieos-release.pub names ({public_key()[:16]}…): "
              "nodes pinned to that one would refuse this build, so nothing is signed", file=sys.stderr)
        return 2
    d = digest()
    out = {"digest": d, "sig": key.sign(release.MESSAGE + d.encode()).hex(), "key": pub}
    with open(SIG, "w", encoding="utf-8") as f:
        json.dump(out, f)
        f.write("\n")
    print(f"signed the agent {d[:19]}… with the release key {pub[:16]}…")
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
