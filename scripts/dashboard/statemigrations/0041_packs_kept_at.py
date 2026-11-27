"""State 40 to 41: every pack kept from a folder of a repository names the
commit it is kept under here.

A pack kept from a folder (R170 step 6) is in a repository of its own on the
controller, and a node fetches it at that repository's commit. A record from
before 11 Nov said no `kept_at`, and toolpacks.py read the repository's head
in its place each time; that head is written into the record here once, as
toolpacks.py read it on 27 Nov, and the reading goes (R205).

Idempotent. Never edited once shipped (stateversion.py).
"""
import json
import os
import re
import subprocess
from pathlib import Path

# toolpacks.NAME on 27 Nov 2026.
NAME = re.compile(r"^[a-z][a-z0-9-]{1,39}$")


def _head(repo):
    try:
        r = subprocess.run(["git", "--git-dir", str(repo), "rev-parse", "-q", "--verify", "refs/heads/main"],
                           capture_output=True, text=True, timeout=30, check=False)
    except (OSError, subprocess.SubprocessError):
        return ""
    return r.stdout.strip() if r.returncode == 0 else ""


def run(ctx):
    state = Path(ctx["state"])
    f = state / "toolpacks.json"
    try:
        d = json.loads(f.read_text())
    except (OSError, ValueError):
        return
    packs = d.get("packs") if isinstance(d, dict) else None
    if not isinstance(packs, dict):
        return
    moved = False
    for name, rec in packs.items():
        if not isinstance(rec, dict) or not (rec.get("hosted") and rec.get("path")) or rec.get("kept_at"):
            continue
        if not NAME.fullmatch(str(rec.get("name") or name)):
            continue
        head = _head(state / "toolpacks" / f"{rec.get('name') or name}.git")
        if head:
            rec["kept_at"] = head
            moved = True
    if not moved:
        return
    tmp = f.with_name(f.name + ".tmp")
    tmp.write_text(json.dumps(d, indent=1))
    os.chmod(tmp, f.stat().st_mode & 0o777)
    os.replace(tmp, f)
