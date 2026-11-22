#!/usr/bin/env python3
"""config/release-signers and the stick maker's copy of it, written from what
each is a copy of, so neither is typed and neither can drift.

    tools/release-signers.py --check    say what differs or is malformed; exit 1
    tools/release-signers.py --write    write both

config/release-signers names who may sign a release's SHA256SUMS, in
ssh-keygen's allowed signers form, and the namespace says for which channel:

    aerieos-dev namespaces="aerieos-dev" ssh-ed25519 AAAA...
        the key the release build signs a dev build's list with, and its
        spare: config/aerieos-release.pub's keys (scripts/lib/releasepub.py
        is that file's one reader), the same Ed25519 keys written as OpenSSH
        public keys. These lines are written here.
    aerieos-release namespaces="aerieos-release" ssh-ed25519 AAAA... aerieos-release
        the key a stable release is signed with, on its holder's own machine:
        the line tools/release-sign.py key prints, committed by hand. Left as
        it is here, and held to its form.

tools/aerieos-stick.py is one file a person downloads, so it carries the key
lines in RELEASE_SIGNERS; they are config/release-signers' own, written here.
`aerie lint` runs --check (lint-checks.py releasesigners).

Stdlib only.
"""
import base64
import os
import re
import sys

ROOT = os.path.normpath(os.path.join(os.path.dirname(os.path.abspath(__file__)), ".."))
PUB = os.path.join(ROOT, "config", "aerieos-release.pub")
SIGNERS = os.path.join(ROOT, "config", "release-signers")
STICK = os.path.join(ROOT, "tools", "aerieos-stick.py")
DEV, RELEASE = "aerieos-dev", "aerieos-release"
# A key line: who, the one namespace that who may sign in, the key, a comment.
LINE = re.compile(r'(aerieos-dev|aerieos-release) namespaces="(aerieos-dev|aerieos-release)" '
                  r"(ssh-ed25519|sk-ssh-ed25519@openssh\.com) ([A-Za-z0-9+/]+=*)(?: \S.*)?")
# Where the dev lines go when the file holds none yet.
MARK = "# Dev builds"
BLOCK = re.compile(r'^RELEASE_SIGNERS = """\n(.*?)^"""$', re.S | re.M)


def ssh_key(hexkey):
    """An Ed25519 public key's 64 hex characters as OpenSSH writes it:
    ssh-ed25519 and the base64 of the key type and the key, each behind its
    length."""
    def field(b):
        return len(b).to_bytes(4, "big") + b
    return "ssh-ed25519 " + base64.b64encode(field(b"ssh-ed25519") + field(bytes.fromhex(hexkey))).decode()


def dev_lines(pub=None):
    """(lines, why): the dev lines config/aerieos-release.pub's keys make, the
    key the builds sign with first, or [] and why the file names no key."""
    sys.path.insert(0, os.path.join(ROOT, "scripts", "lib"))
    import releasepub                                               # noqa: E402, PLC0415
    keys, why = releasepub.read(pub or PUB)
    return [f'{DEV} namespaces="{DEV}" {ssh_key(k)}' for k in keys], why


def key_lines(text):
    """The lines of a signers file that are not blank and not a comment."""
    return [ln.strip() for ln in text.splitlines() if ln.strip() and not ln.lstrip().startswith("#")]


def with_dev(text, lines):
    """The signers file's text with its dev lines replaced by `lines`, where
    the first of them was, or under the comment that heads them; every other
    line as it is. None when there is no place for them."""
    rows = text.splitlines()
    at = next((i for i, ln in enumerate(rows) if ln.split(" ", 1)[0] == DEV), None)
    if at is None:
        at = next((i + 1 for i, ln in enumerate(rows) if ln.startswith(MARK)), None)
        if at is None:
            return None
        # ...past the rest of that comment.
        while at < len(rows) and rows[at].startswith("#") and rows[at].strip() != "#":
            at += 1
    keep = [(i, ln) for i, ln in enumerate(rows) if ln.split(" ", 1)[0] != DEV]
    out = [ln for i, ln in keep if i < at] + list(lines) + [ln for i, ln in keep if i >= at]
    return "\n".join(out) + "\n"


def with_block(text, lines):
    """The stick maker's source with RELEASE_SIGNERS holding `lines`, or None
    when it has no such block."""
    if not BLOCK.search(text):
        return None
    body = "".join(ln + "\n" for ln in lines)
    return BLOCK.sub(lambda m: 'RELEASE_SIGNERS = """\n' + body + '"""', text, count=1)


def problems(pub=None, signers=None, stick=None):
    """What is wrong, a sentence each; nothing when the file's dev lines are
    config/aerieos-release.pub's, every line is in its form, no stable signer
    is a key the release build holds, and the stick maker carries the same."""
    signers, stick = signers or SIGNERS, stick or STICK
    want, why = dev_lines(pub)
    if why:
        return [f"config/aerieos-release.pub names no key to write the dev lines from: {why}"]
    try:
        with open(signers, encoding="utf-8") as f:
            text = f.read()
    except (OSError, UnicodeDecodeError) as e:
        return [f"config/release-signers cannot be read ({getattr(e, 'strerror', None) or e}): every install checks a release against it"]
    bad = []
    have = key_lines(text)
    for ln in have:
        m = LINE.fullmatch(ln)
        if not m:
            bad.append(f'config/release-signers: "{ln[:60]}" is not a signer: a line is aerieos-dev or aerieos-release, '
                       'namespaces="the same", and an Ed25519 key as OpenSSH writes it')
        elif m.group(1) != m.group(2):
            bad.append(f"config/release-signers: {m.group(1)} is given the namespace {m.group(2)}: "
                       "a signer signs in the namespace it is named for, so the channels stay apart")
    if bad:
        return bad
    if [ln for ln in have if ln.startswith(DEV + " ")] != want:
        bad.append("config/release-signers: its aerieos-dev lines are not config/aerieos-release.pub's keys "
                   "(the release key or its spare moved, or a line was typed): tools/release-signers.py --write writes them")
    held = {LINE.fullmatch(ln).group(4) for ln in want}
    for ln in have:
        m = LINE.fullmatch(ln)
        if m.group(1) == RELEASE and m.group(4) in held:
            bad.append("config/release-signers: an aerieos-release line names a key of config/aerieos-release.pub, which "
                       "the release build holds: a stable release is signed by a key CI never has")
    try:
        with open(stick, encoding="utf-8") as f:
            m = BLOCK.search(f.read())
    except (OSError, UnicodeDecodeError) as e:
        return [*bad, f"tools/aerieos-stick.py cannot be read ({getattr(e, 'strerror', None) or e})"]
    if not m:
        bad.append('tools/aerieos-stick.py has no RELEASE_SIGNERS = """ block to hold the signers in')
    elif m.group(1) != "".join(ln + "\n" for ln in have):
        bad.append("tools/aerieos-stick.py: its RELEASE_SIGNERS is not config/release-signers' lines, so a stick would be "
                   "checked against other keys than an install's: tools/release-signers.py --write writes it")
    return bad


def write(pub=None, signers=None, stick=None):
    """Both written; what changed, or why nothing could be."""
    signers, stick = signers or SIGNERS, stick or STICK
    want, why = dev_lines(pub)
    if why:
        return [], f"config/aerieos-release.pub names no key: {why}"
    with open(signers, encoding="utf-8") as f:
        was = f.read()
    now = with_dev(was, want)
    if now is None:
        return [], f'config/release-signers has no aerieos-dev line and no "{MARK}" comment to put them under'
    changed = []
    if now != was:
        with open(signers, "w", encoding="utf-8", newline="\n") as f:
            f.write(now)
        changed.append("config/release-signers")
    with open(stick, encoding="utf-8") as f:
        was = f.read()
    code = with_block(was, key_lines(now))
    if code is None:
        return changed, 'tools/aerieos-stick.py has no RELEASE_SIGNERS = """ block'
    if code != was:
        with open(stick, "w", encoding="utf-8", newline="\n") as f:
            f.write(code)
        changed.append("tools/aerieos-stick.py")
    return changed, ""


def main(argv=None):
    args = sys.argv[1:] if argv is None else argv
    if args == ["--write"]:
        changed, why = write()
        for c in changed:
            print(f"wrote {c}")
        if why:
            print(f"release-signers: {why}", file=sys.stderr)
            return 1
        if not changed:
            print("nothing to write: both are as their sources say")
        return 0
    if args == ["--check"]:
        bad = problems()
        for b in bad:
            print(f"  [FAIL] {b}")
        if not bad:
            n = len(key_lines(open(SIGNERS, encoding="utf-8").read()))
            print(f"  [ok]   config/release-signers' dev lines are config/aerieos-release.pub's keys, and the stick maker "
                  f"carries the same {n} signer{'s' if n != 1 else ''}")
        return 1 if bad else 0
    print(__doc__)
    return 0 if args in ([], ["--help"], ["-h"]) else 2


if __name__ == "__main__":
    sys.exit(main())
