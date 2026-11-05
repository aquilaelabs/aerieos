"""State 19 to 20: the boot stamp on tabs.json in the new shape.

The controller tells a new run of its machine from a restart of itself by a
pair of numbers, whose first was /proc/stat's btime and is now the kernel's id
for the boot, since btime moves whenever the clock is stepped. A stamp written
in this same boot in the old shape is rewritten in the new one, so an update
with no restart of the machine does not read as a new run and close the
session tabs. A stamp from any other boot is left, and reads as what it is.
Idempotent. Never edited once shipped (stateversion.py).
"""
import json
import os
from pathlib import Path


def run(ctx):
    f = Path(ctx["state"]) / "tabs.json"
    try:
        d = json.loads(f.read_text())
        start = Path("/proc/1/stat").read_text().rsplit(")", 1)[1].split()[19]
        btime = next(ln for ln in Path("/proc/stat").read_text().splitlines()
                     if ln.startswith("btime ")).split()[1]
        first = int(Path("/proc/sys/kernel/random/boot_id").read_text()[:8], 16)
    except (OSError, ValueError, IndexError, StopIteration):
        return
    if not isinstance(d, dict) or d.get("boot") != f"{btime}.{start}":
        return
    d["boot"] = f"{first}.{start}"
    tmp = f.with_name(f.name + ".new")
    tmp.write_text(json.dumps(d))
    os.replace(tmp, f)
