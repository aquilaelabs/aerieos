#!/usr/bin/env python3
"""The harness remembers its flakes (R7 step 3).

A browser suite that fails in a whole run and passes when run again
without the run's load is flaky: named above the verdict, and until now
forgotten with the terminal's scroll. Each one is a line here, in
.bb-map/flakes.tsv beside the suites' timings: when, the suite, the first
check that failed in the run, how many workers the run had and the load it
ended under. `aerie tests flakes` counts them, and the pre-push gate fails on
one in a suite it ran, since every suite a gate runs is one the change
touches (the operator, 14 Nov); a release's tag still counts a flaky suite
as passed.

    flakes.py record --file F --workers N --load L [--logs LOG...] --suites A.mjs B.mjs
    flakes.py list --file F [--days N]
    flakes.py of-log RUNLOG
"""
import os
import re
import sys
import time

BANNER = re.compile(r"\[dashboard-test\] == (\S+?)(?:\.mjs)?(?: again)? ==")
FLAKY = re.compile(r"WARN: flaky: (.+?) failed in the whole run and passed again alone")


def first_fails(logs):
    """{suite: its first FAIL line} from a run's logs, each suite's lines
    being what follows its banner up to the next one."""
    out = {}
    for path in logs:
        try:
            with open(path, encoding="utf-8", errors="replace") as f:
                suite = ""
                for line in f:
                    m = BANNER.search(line)
                    if m:
                        suite = "" if " again ==" in line else m.group(1)
                        continue
                    if suite and suite not in out and line.startswith("FAIL"):
                        out[suite] = " ".join(line[4:].split())[:200]
        except OSError:
            continue
    return out


def record(path, suites, workers, load, logs, now=None):
    """One line for each flaky suite of a run. The lines written."""
    fails = first_fails(logs)
    at = int(now if now is not None else time.time())
    rows = []
    for s in suites:
        name = os.path.basename(s).removesuffix(".mjs")
        if not re.fullmatch(r"[A-Za-z0-9_.-]{1,80}", name):
            continue
        check = fails.get(name, "").replace("\t", " ")
        rows.append(f"{at}\t{name}\t{workers}\t{load}\t{check}\n")
    if rows:
        os.makedirs(os.path.dirname(os.path.abspath(path)), exist_ok=True)
        with open(path, "a", encoding="utf-8") as f:
            f.writelines(rows)
    return rows


def read(path):
    """[(at, suite, workers, load, check)], oldest first; a line that is not one is passed over."""
    out = []
    try:
        with open(path, encoding="utf-8", errors="replace") as f:
            for line in f:
                p = line.rstrip("\n").split("\t")
                if len(p) >= 5 and p[0].isdigit():
                    out.append((int(p[0]), p[1], p[2], p[3], p[4]))
    except OSError:
        pass
    return out


def counted(rows, days=30, now=None):
    """[(suite, times, last at, last check)] over the last `days`, the most often first."""
    cut = (now if now is not None else time.time()) - days * 86400
    by = {}
    for at, suite, _w, _l, check in rows:
        if at < cut:
            continue
        n, last, said = by.get(suite, (0, 0, ""))
        by[suite] = (n + 1, max(last, at), check if at >= last else said)
    return sorted(((s, n, last, said) for s, (n, last, said) in by.items()), key=lambda r: (-r[1], r[0]))


def of_log(text):
    """The suites a run's log names as flaky, in the order it named them."""
    out = []
    for m in FLAKY.finditer(text or ""):
        for name in m.group(1).split():
            name = name.removesuffix(".mjs")
            if name not in out:
                out.append(name)
    return out


def main(argv):
    def opt(name, default=""):
        return argv[argv.index(name) + 1] if name in argv and argv.index(name) + 1 < len(argv) else default

    def many(name):
        if name not in argv:
            return []
        out = []
        for a in argv[argv.index(name) + 1:]:
            if a.startswith("--"):
                break
            out.append(a)
        return out
    if argv[:1] == ["record"]:
        record(opt("--file"), many("--suites"), opt("--workers", "1"), opt("--load", "?"), many("--logs"))
        return 0
    if argv[:1] == ["list"]:
        days = int(opt("--days", "30") or 30)
        got = counted(read(opt("--file")), days)
        if not got:
            print(f"no suite has been flaky in the last {days} days on record here")
            return 0
        print(f"flaky in the last {days} days (failed in a whole run, passed when run again), the most often first:")
        for suite, n, last, said in got:
            print(f"  {suite:<18} {n:>3}x  last {time.strftime('%d %b %H:%M', time.localtime(last))}"
                  + (f"  {said[:110]}" if said else ""))
        return 0
    if argv[:1] == ["of-log"] and len(argv) > 1:
        try:
            with open(argv[1], encoding="utf-8", errors="replace") as f:
                print(" ".join(of_log(f.read())))
        except OSError:
            pass
        return 0
    print("usage: flakes.py record|list|of-log (see its head)", file=sys.stderr)
    return 2


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
