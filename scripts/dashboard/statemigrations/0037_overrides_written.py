"""State 36 to 37: each repository's record names the dials it sets apart
from its space.

A record from before 3 Nov (every released install's then) kept no
`overrides` list, and prefs.py read each dial it stored a value for, away
from that dial's default, as set apart. Written here once with the dials and
defaults as they stood when this was written (a migration never reads a
module, which moves on), and the reader takes the list alone (R295).

Idempotent. Never edited once shipped (stateversion.py).
"""
import json
import os
from pathlib import Path

# prefs.OVERRIDABLE, DIAL_DEFAULTS, GATE_KINDS, GATE_MODES and GATE_EXTRA on 26 Nov 2026.
OVERRIDABLE = ('devbuild', 'makevms', 'kube', 'discord', 'installpacks', 'report', 'sign', 'keys', 'release', 'pc', 'test_change', 'test_node')
DIAL_DEFAULTS = {'devbuild': 'deny', 'makevms': 'deny', 'kube': 'deny', 'discord': 'deny', 'installpacks': 'ask', 'report': 'auto', 'sign': 'ask', 'keys': 'ask', 'release': 'ask', 'pc': 'deny', 'test_change': 'wait', 'test_node': ''}
GATE_KINDS = ('roadmap', 'bugs', 'rules', 'settings', 'design', 'wiki')
GATE_MODES = ('auto', 'ask', 'deny')
GATE_EXTRA = {'wiki': ('hidden',)}


def _set_apart(rec):
    got = {f for f in OVERRIDABLE if rec.get(f) not in (None, DIAL_DEFAULTS[f])}
    gate = rec.get("gate") if isinstance(rec.get("gate"), dict) else {}
    got |= {f"gate.{k}" for k in GATE_KINDS
            if gate.get(k) not in (None, "auto") and (gate.get(k) in GATE_MODES or gate.get(k) in GATE_EXTRA.get(k, ()))}
    return sorted(got)


def run(ctx):
    f = Path(ctx["state"]) / "claude-prefs.json"
    try:
        d = json.loads(f.read_text())
    except (OSError, ValueError):
        return
    projects = d.get("projects") if isinstance(d, dict) else None
    if not isinstance(projects, dict):
        return
    moved = False
    for rec in projects.values():
        if isinstance(rec, dict) and not isinstance(rec.get("overrides"), list):
            rec["overrides"] = _set_apart(rec)
            moved = True
    if not moved:
        return
    tmp = f.with_name(f.name + ".tmp")
    tmp.write_text(json.dumps(d, indent=1))
    os.chmod(tmp, f.stat().st_mode & 0o777)
    os.replace(tmp, f)
