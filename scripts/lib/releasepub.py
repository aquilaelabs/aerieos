"""config/aerieos-release.pub, read one way.

The file names AerieOS's release key and its spare, a line each:

    aerieos-release-ed25519 <64 hex characters>

Three things read it: the Enroll script, which hands a node the keys to pin
(scripts/dashboard/enrollscript.py), the build's signer, which holds the
key a build signs with to them (tools/sign-agent.py), and `aerie lint`. They
read it here, so they cannot disagree: the Enroll script took a file with a
third line or a malformed one as naming no key at all, and every node
enrolled after that pinned nothing, with no word, while the signer took its
first two lines whatever they held.

A file that does not parse answers no keys and why, never some of them: a
key dropped quietly is a node that takes its updates on a controller's word.
`aerie lint` fails on the why (lint-checks.py releasekey), so such a file is a
red build before it is an image.

Stdlib only.
"""
import re

NAME = "aerieos-release-ed25519"
_LINE = re.compile(NAME + r"\s+([0-9a-f]{64})", re.I)


def parse(text):
    """(keys, why) for the file's text: the key the builds sign with, then
    its spare where a second line names one, and "" for why; or [] and what
    is wrong with it. A blank line and a line that starts with # are not
    read; every other line is a key in the form above, and the file names
    one or two of them (the same key twice is that key once)."""
    keys = []
    for n, raw in enumerate(str(text or "").splitlines(), 1):
        line = raw.strip()
        if not line or line.startswith("#"):
            continue
        m = _LINE.fullmatch(line)
        if not m:
            return [], f"line {n} is not a key: a line is {NAME} and 64 hex characters"
        keys.append(m.group(1).lower())
    keys = list(dict.fromkeys(keys))
    if not keys:
        return [], "it names no key"
    if len(keys) > 2:
        return [], f"it names {len(keys)} keys: a release has one, and one spare"
    return keys, ""


def read(path):
    """parse() of the file at `path`; a file that cannot be read names no
    key, and says so."""
    try:
        with open(path, encoding="utf-8") as f:
            return parse(f.read())
    except (OSError, UnicodeDecodeError) as e:
        return [], f"it cannot be read ({getattr(e, 'strerror', None) or e})"
