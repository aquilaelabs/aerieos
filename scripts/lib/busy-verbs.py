"""Behind `aerie node busy` and `aerie node wait-quiet` (cmd_node in bb, R108):
whether the node this session is on is quiet enough to time anything on.

The controller's answer (busy.report) is the node's last heartbeat joined
with the jobs and the working Claude sessions there; the load right now is
read here as well, from /proc/loadavg, which a session's view shares with
the whole machine, because a heartbeat is up to 25 s old.

Arguments: the verb (busy or wait-quiet), then its options. BB_PROJECT and
BB_BUSY_NODE come from bb. The auth header is bbapi's own (BB_AUTH_HEADER,
from aerie)."""
import json
import os
import sys
import time
import urllib.parse

import bbapi
from say import need

project = os.environ.get("BB_PROJECT", "")
node = os.environ.get("BB_BUSY_NODE", "")
RANK = {"quiet": 0, "busy": 1, "saturated": 2, "unknown": 3}


def now_load():
    try:
        with open("/proc/loadavg") as f:
            return float(f.read().split()[0])
    except (OSError, ValueError, IndexError):
        return None


def now_mem():
    """The machine's memory now, (total MB, used MB), as the heartbeat counts
    it (what MemAvailable does not leave free), or None."""
    m = {}
    try:
        with open("/proc/meminfo") as f:
            for line in f:
                k, _, v = line.partition(":")
                if k in ("MemTotal", "MemAvailable"):
                    m[k] = int(v.split()[0]) // 1024
    except (OSError, ValueError, IndexError):
        return None
    return (m["MemTotal"], m["MemTotal"] - m["MemAvailable"]) if len(m) == 2 and m["MemTotal"] else None


def ask():
    q = urllib.parse.urlencode({"project": project, "node": node})
    d = bbapi.call(f"/api/node-busy?{q}")
    need(d)
    # The load now, from here, where it is fresher than the heartbeat:
    # a machine that filled up since says so at once.
    load = now_load()
    cores = int(d.get("cores") or 0) or os.cpu_count() or 1
    if load is not None:
        d["load_now"] = load
        if load / cores >= 1.0 and d["verdict"] in ("quiet", "busy"):
            d["verdict"] = "saturated"
            d["why"] = [f"load {load:g} on {cores} cores right now"] + d["why"]
        elif load / cores >= 0.5 and d["verdict"] == "quiet":
            d["verdict"] = "busy"
            d["why"] = [f"load {load:g} on {cores} cores right now"]
    # ...and its memory now (R271): a build or an emulator that filled it
    # since the heartbeat says so at once, as the controller's verdict
    # would on the next one (busy.py: 92% used is saturated).
    mem = now_mem()
    if mem:
        d["mem_mb"], d["mem_used_mb"] = mem
        if mem[1] * 100 >= 92 * mem[0] and d["verdict"] in ("quiet", "busy"):
            d["verdict"] = "saturated"
            d["why"] = [f"memory {mem[1] * 100 // mem[0]}% used right now"] + d["why"]
    return d


def show(d):
    print(f"{d['node']}: {d['verdict']}" + (f" ({'; '.join(d['why'])})" if d["why"] else ""))
    gb = lambda mb: f"{(mb or 0) / 1024:.1f} GB"  # noqa: E731
    print(f"  cpu      {d.get('cpu_pct')}% over the last heartbeat, load {d.get('load1')}"
          + (f" then and {d['load_now']:g} now" if d.get("load_now") is not None else "")
          + f", {d.get('cores')} cores")
    if d.get("mem_mb"):
        print(f"  memory   {gb(d.get('mem_used_mb'))} of {gb(d.get('mem_mb'))} in use now")
    if d.get("gpu_mem_mb"):
        print(f"  gpu      {d.get('gpu_pct')}%, {gb(d.get('gpu_mem_used_mb'))} of {gb(d.get('gpu_mem_mb'))}"
              + (f", {d['gpu_procs']} computing" if d.get("gpu_procs") else ""))
        # ...and what holds it, by kind (B532): an emulator that filled the
        # card while it booted read as a mystery.
        held = {k: v for k, v in (d.get("gpu_mem_kinds") or {}).items() if v}
        if held:
            print("  gpu mem  " + ", ".join(f"{k} {gb(v)}" for k, v in sorted(held.items(), key=lambda kv: -kv[1])))
    kinds = {k: v for k, v in (d.get("kinds") or {}).items() if v}
    if kinds:
        print("  running  " + ", ".join(f"{v} {k}" for k, v in sorted(kinds.items())))
    if d.get("jobs"):
        print("  jobs     " + ", ".join(f"{v} {k}" for k, v in sorted(d["jobs"].items())))
    print(f"  claude   {d.get('sessions_working', 0)} session(s) working, this one included")
    if d["verdict"] != "quiet":
        print("  a timing taken now is the machine's as much as the code's: say the load with it, "
              "or aerie node wait-quiet first")


def main(argv):
    verb, rest = (argv[0] if argv else "busy"), argv[1:]
    if verb == "busy":
        d = ask()
        if "--json" in rest:
            print(json.dumps(d, indent=1))
        else:
            show(d)
        return 0
    if verb == "wait-quiet":
        level, timeout = "quiet", 600
        it = iter(rest)
        for a in it:
            if a == "--level":
                level = next(it, "quiet")
            elif a == "--timeout":
                timeout = int(next(it, "600"))
            else:
                sys.exit("[builderbot] ERROR: aerie node wait-quiet [--level quiet|busy] [--timeout SECONDS]")
        if level not in ("quiet", "busy"):
            sys.exit("[builderbot] ERROR: --level is quiet or busy")
        start, calm = time.time(), 0
        while True:
            d = ask()
            # Twice in a row, ten seconds apart: one quiet reading between
            # two builds is a gap, not a quiet machine.
            calm = calm + 1 if RANK[d["verdict"]] <= RANK[level] else 0
            if calm >= 2:
                print(f"[builderbot] {d['node']} is {d['verdict']}: measure now", file=sys.stderr)
                return 0
            if time.time() - start > timeout:
                print(f"[builderbot] {d['node']} was not {level} in {timeout} s: it is {d['verdict']} "
                      f"({'; '.join(d['why'])}); a timing taken now says so with it", file=sys.stderr)
                return 1
            time.sleep(10)
    sys.exit("[builderbot] ERROR: aerie node busy [--json] | wait-quiet [--level quiet|busy] [--timeout SECONDS]")


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
