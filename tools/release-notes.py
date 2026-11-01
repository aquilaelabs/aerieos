#!/usr/bin/env python3
"""A dev build's release notes: only what is new since the release before it.

    tools/release-notes.py TAG

The changelog's Unreleased section at TAG, less the lines it already held at
the last published release before it, under their headings. Unreleased only
grows between two stable releases, so the section whole repeated every earlier
dev build's lines. Published, not merely tagged: a draft nobody published, or a
tag with no release, showed nobody its lines, so they come with this one. A line
is the same line whatever commit it names at its end. Python's own library, git
and gh, for CI; without gh, the tag before.
"""
import re
import shutil
import subprocess
import sys

HASH = re.compile(r"\s*\([0-9a-f]{7,40}\)\s*$")


def git(*args):
    r = subprocess.run(["git", *args], capture_output=True, text=True, check=False)
    return r.stdout if r.returncode == 0 else None


def unreleased(text):
    """[(heading, line)] of the Unreleased section's lines, in order."""
    out, on, head = [], False, ""
    for line in (text or "").splitlines():
        if line.startswith("## "):
            if on:
                break
            on = line.strip() == "## Unreleased"
        elif on and line.startswith("### "):
            head = line.strip()
        elif on and line.strip():
            out.append((head, line.rstrip()))
    return out


def key(line):
    return HASH.sub("", line)


def notes(now, before, since=""):
    """The markdown: what `now` holds of Unreleased that `before` did not."""
    had = {key(line) for _, line in unreleased(before)}
    new = [(h, line) for h, line in unreleased(now) if key(line) not in had]
    lead = f"What changed since {since}." if since else ""
    if not new:
        return (lead + "\n\n" if lead else "") + "Nothing a person would see.\n"
    blocks, head = [lead] if lead else [], None
    for h, line in new:
        if h != head or not blocks:
            blocks += [h, ""] if h else [""]
            head = h
        blocks[-1] += ("\n" if blocks[-1] else "") + line
    return "\n\n".join(blocks) + "\n"


def published():
    """The tags of the published releases, or None where gh cannot say."""
    r = subprocess.run(["gh", "release", "list", "--exclude-drafts", "--limit", "200", "--json", "tagName", "--jq", ".[].tagName"],
                       capture_output=True, text=True, check=False) if shutil.which("gh") else None
    return set(r.stdout.split()) if r is not None and r.returncode == 0 else None


def since_of(tag, shown):
    """The newest tag before `tag` in its history that was published (`shown`,
    None for any tag), or ""."""
    tags = (git("tag", "--merged", f"{tag}^", "--list", "v*", "--sort=-creatordate") or "").split()
    return next((t for t in tags if shown is None or t in shown), "")


def main(argv):
    if len(argv) != 2:
        print(__doc__, file=sys.stderr)
        return 64
    tag = argv[1]
    now = git("show", f"{tag}:CHANGELOG.md")
    if now is None:
        print(f"release-notes: no CHANGELOG.md at {tag}", file=sys.stderr)
        return 1
    since = since_of(tag, published())
    before = git("show", f"{since}:CHANGELOG.md") if since else ""
    sys.stdout.write(notes(now, before or "", since))
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv))
