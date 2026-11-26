"""State 31 to 32: a space's color is each person's alone.

A color was once a space's own, kept in its settings (claude-prefs.json).
Since colors moved to each person (project-colors.json), the space's own was
read only as where an account that had picked none started. Each account
with no colors of its own is given the ones it was being shown, so nobody's
cards change, and color is taken out of the spaces' settings, which no
longer hold one. An account made after this starts with none, as one that
cleared its own does.

The colors are written first and the settings after, so a start stopped
between the two runs this again and finds every account already holding its
own. Idempotent. Never edited once shipped (stateversion.py).
"""
import json
import os
from pathlib import Path

# The color names at this migration (prefs.COLORS).
COLORS = ("red", "orange", "yellow", "green", "teal", "blue", "violet", "pink")


def _read(f):
    try:
        d = json.loads(f.read_text())
    except (OSError, ValueError):
        return None
    return d if isinstance(d, dict) else None


def _write(f, d, mode):
    tmp = f.with_name(f.name + ".tmp")
    tmp.write_text(json.dumps(d, indent=1))
    os.chmod(tmp, f.stat().st_mode & 0o777 if f.exists() else mode)
    os.replace(tmp, f)


def run(ctx):
    state = Path(ctx["state"])
    pf = state / "claude-prefs.json"
    prefs = _read(pf)
    projects = prefs.get("projects") if prefs else None
    if not isinstance(projects, dict):
        return
    shown = {n: r["color"] for n, r in projects.items() if isinstance(r, dict) and r.get("color") in COLORS}
    if shown:
        people = _read(state / "users.json") or {}
        uids = [u.get("uid") for u in (people.get("users") or {}).values() if isinstance(u, dict) and u.get("uid")]
        cf = state / "project-colors.json"
        marks = _read(cf) or {}
        given = False
        for uid in uids:
            if str(uid) not in marks:
                marks[str(uid)] = dict(shown)
                given = True
        if given:
            _write(cf, marks, 0o644)
    if any(isinstance(r, dict) and "color" in r for r in projects.values()):
        for r in projects.values():
            if isinstance(r, dict):
                r.pop("color", None)
        _write(pf, prefs, 0o644)
