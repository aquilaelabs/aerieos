#!/usr/bin/env python3
"""What a root helper written in shell keeps, sealed under the install key
as the controller seals its own secrets (dashboard/signing.py): the deploy
keys, which were plain files guarded by their mode alone, so a copy of
/config taken as root carried every one of them ready to use (R243).

    sealfile.py seal KEYFILE [PREVIOUS]     stdin sealed to stdout under the key in KEYFILE
    sealfile.py open KEYFILE [PREVIOUS]     a seal on stdin opened to stdout, under KEYFILE's
                                            key or, while a change of the install key keeps
                                            it, the one in PREVIOUS
    sealfile.py current KEYFILE [PREVIOUS]  exit 0 when the seal on stdin is under today's
                                            key and today's format, else 1

KEYFILE is the install key's file as boot settled it (BB_SIGNING_SECRET_FILE)
and PREVIOUS the key before it (BB_INSTALL_KEY_PREVIOUS_FILE). Exit 3: no
install key there. Exit 4: the vetted cipher is not on this machine, and
nothing is sealed with another. Exit 5: sealed under a key that is not
there. Nothing is ever written but stdout.
"""
import os
import sys
from pathlib import Path


def main(argv):
    if len(argv) not in (2, 3) or argv[0] not in ("seal", "open", "current"):
        print("usage: sealfile.py seal|open|current KEYFILE [PREVIOUS]", file=sys.stderr)
        return 2
    verb, key = argv[0], Path(argv[1])
    # Always named, so a previous key in this process's own environment is never the one read.
    os.environ["BB_INSTALL_KEY_PREVIOUS_FILE"] = argv[2] if len(argv) == 3 else os.devnull
    sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "dashboard"))
    import signing
    if not signing.load_master(key):
        print(f"no install key in {key}", file=sys.stderr)
        return 3
    if not signing._have_aead():
        print("the cryptography library is not on this machine: nothing is sealed or opened without it", file=sys.stderr)
        return 4
    data = sys.stdin.buffer.read()
    if verb == "seal":
        sys.stdout.buffer.write(signing.seal(data))
        return 0
    if verb == "current":
        return 0 if signing.current(data) else 1
    try:
        sys.stdout.buffer.write(signing.unseal(data))
    except signing.Locked as e:
        print(str(e), file=sys.stderr)
        return 5
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
