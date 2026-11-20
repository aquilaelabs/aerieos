"""State 26 to 27: no tool pack is kept under the name of a toolchain AerieOS
ships.

A session's `aerie tool install jdk` was looked up among the vetted
catalog's packs, where every shipped toolchain is listed too as an official
pack, and a person's Allow kept that pack here under the toolchain's own
name. The record changed no node (the catalog drops a pack named as a
shipped row), but `aerie tool search` called the toolchain added here, the
Library's Remove of it was refused while any node's store held the
toolchain, and its repository and bundle sat under the state. A shipped
name is asked for as the toolchain now and no add keeps a pack under one,
so the ones kept before go here, each with its kept copy (its repository
and its bundle under toolpacks/, its icon), without anybody's press.

Which names are shipped is read from config/toolchains.json beside this
build, as it stands when this runs. Every other pack is left as it is. The
kept copy goes before the record does, so a start cut short between the two
finds the record again and finishes. Idempotent. Never edited once shipped
(stateversion.py).
"""
import json
import re
import shutil
import sys
from pathlib import Path

FILE = "toolpacks.json"
# A pack's name as toolpacks.py takes one: what a kept copy's files are
# named by, so nothing else is made into a path here.
NAME = re.compile(r"^[a-z][a-z0-9-]{1,39}$")
ICONS = ("png", "webp", "svg")
TOOLCHAINS = Path(__file__).resolve().parents[3] / "config" / "toolchains.json"


def shipped():
    """The names of the toolchains this build ships, or none where its
    table cannot be read: then nothing is taken for a shipped name."""
    try:
        rows = json.loads(TOOLCHAINS.read_text())["toolchains"]
    except (OSError, ValueError, KeyError, TypeError):
        return set()
    if not isinstance(rows, list):
        return set()
    return {r["name"] for r in rows if isinstance(r, dict) and isinstance(r.get("name"), str)}


def run(ctx):
    state = Path(ctx["state"])
    f = state / FILE
    try:
        d = json.loads(f.read_text())
    except (OSError, ValueError):
        return
    packs = d.get("packs") if isinstance(d, dict) else None
    if not isinstance(packs, dict):
        return
    gone = sorted(set(packs) & shipped())
    if not gone:
        return
    for name in gone:
        if NAME.fullmatch(name):
            shutil.rmtree(state / "toolpacks" / f"{name}.git", ignore_errors=True)
            (state / "toolpacks" / f"{name}.bundle").unlink(missing_ok=True)
            for ext in ICONS:
                (state / "pack-icons" / f"{name}.{ext}").unlink(missing_ok=True)
        packs.pop(name)
    sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
    import statefile
    statefile.write_json(f, d, mode=f.stat().st_mode & 0o777)
