"""State 34 to 35: the favorite spaces kept by account in every install.

pinned-projects.json was one flat list for everybody until 27 Sep, read as
everyone's default under "*" and written by account the first time anybody
pinned; an install where nobody has since keeps the list. Written as
{"*": [names]} here once, and projects.py reads one shape (R295).

Idempotent. Never edited once shipped (stateversion.py).
"""
import json
import os
from pathlib import Path


def run(ctx):
    f = Path(ctx["state"]) / "pinned-projects.json"
    try:
        v = json.loads(f.read_text())
    except (OSError, ValueError):
        return
    if not isinstance(v, list):
        return
    tmp = f.with_name(f.name + ".tmp")
    tmp.write_text(json.dumps({"*": sorted({x for x in v if isinstance(x, str)})}, indent=1))
    os.chmod(tmp, f.stat().st_mode & 0o777)
    os.replace(tmp, f)
