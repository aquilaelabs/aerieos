"""State 28 to 29: the static analysis scan's schedule row goes.

The scan was the first built-in schedule, kept in schedules.json under the
id "scan". It has been the Scanners page's own for a long time, and the row
stayed in the file, unlisted, for a build that would read it again; none
that an install updates from does. The row goes, and every other schedule
is left as it is.

Idempotent. Never edited once shipped (stateversion.py).
"""
import json
import os
from pathlib import Path

SCAN_ID = "scan"


def run(ctx):
    f = Path(ctx["state"]) / "schedules.json"
    try:
        d = json.loads(f.read_text())
    except (OSError, ValueError):
        return
    if not isinstance(d, dict) or not isinstance(d.get("schedules"), dict) or SCAN_ID not in d["schedules"]:
        return
    del d["schedules"][SCAN_ID]
    tmp = f.with_name(f.name + ".tmp")
    tmp.write_text(json.dumps(d, indent=1))
    os.chmod(tmp, f.stat().st_mode & 0o777)
    os.replace(tmp, f)
