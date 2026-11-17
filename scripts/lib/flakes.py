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
    flakes.py list --file F [--days N] [--bugs BUGLIST]
    flakes.py of-log RUNLOG
    flakes.py said --file F [--commit C] SUITE      the last sighting, as a bug's note says it
    flakes.py bug-for --bugs BUGLIST SUITE          the open bug that names the suite, if one does

Each line also keeps what the check waited for (R250 step 2): the harness's
[wait] line under the first FAIL, or the error that stopped the suite, so
the gate can note a sighting's cause on the suite's bug as it happens.
"""
import os
import re
import sys
import time

BANNER = re.compile(r"\[dashboard-test\] == (\S+?)(?:\.mjs)?(?: again)? ==")
# What a failure waited for: the harness's own diagnosis under a FAIL, or
# the error a suite stopped on (a timeout, a route handled twice).
WAITED = re.compile(r"^\[wait\] ")
STOPPED = re.compile(r"^(?:page|route|locator|frame|browser)\.\w+: |^(?:\w*Error|TimeoutError): ")
FLAKY = re.compile(r"WARN: flaky: (.+?) failed in the whole run and passed again alone")


def first_fails(logs):
    """{suite: its first FAIL line} from a run's logs, each suite's lines
    being what follows its banner up to the next one."""
    return {s: c for s, (c, _w) in fails_and_causes(logs).items()}


def fails_and_causes(logs):
    """{suite: (its first FAIL line, what it waited for)} from a run's logs:
    the [wait] line under that FAIL, or the error the suite stopped on when
    it stopped before any FAIL or after it, whichever comes first."""
    out = {}
    for path in logs:
        try:
            with open(path, encoding="utf-8", errors="replace") as f:
                suite, check, cause = "", None, None
                for line in f:
                    m = BANNER.search(line)
                    if m:
                        if suite and suite not in out and (check or cause):
                            out[suite] = (check or "", cause or "")
                        suite = "" if " again ==" in line else m.group(1)
                        check, cause = None, None
                        continue
                    if not suite or suite in out:
                        continue
                    if line.startswith("FAIL") and check is None:
                        check = " ".join(line[4:].split())[:200]
                    elif cause is None and (WAITED.match(line) and check is not None or STOPPED.match(line)):
                        cause = " ".join(line.split())[:240]
                if suite and suite not in out and (check or cause):
                    out[suite] = (check or "", cause or "")
        except OSError:
            continue
    return out


def record(path, suites, workers, load, logs, now=None):
    """One line for each flaky suite of a run. The lines written."""
    fails = fails_and_causes(logs)
    at = int(now if now is not None else time.time())
    rows = []
    for s in suites:
        name = os.path.basename(s).removesuffix(".mjs")
        if not re.fullmatch(r"[A-Za-z0-9_.-]{1,80}", name):
            continue
        check, cause = (x.replace("\t", " ") for x in fails.get(name, ("", "")))
        rows.append(f"{at}\t{name}\t{workers}\t{load}\t{check}" + (f"\t{cause}" if cause else "") + "\n")
    if rows:
        os.makedirs(os.path.dirname(os.path.abspath(path)), exist_ok=True)
        with open(path, "a", encoding="utf-8") as f:
            f.writelines(rows)
    return rows


def read(path):
    """[(at, suite, workers, load, check)], oldest first; a line that is not one is passed over."""
    return [r[:5] for r in read_causes(path)]


def read_causes(path):
    """read's rows with what each waited for, "" on a line that kept none."""
    out = []
    try:
        with open(path, encoding="utf-8", errors="replace") as f:
            for line in f:
                p = line.rstrip("\n").split("\t")
                if len(p) >= 5 and p[0].isdigit():
                    out.append((int(p[0]), p[1], p[2], p[3], p[4], p[5] if len(p) > 5 else ""))
    except OSError:
        pass
    return out


# An open bug's line as aerie bug list prints it.
BUG_LINE = re.compile(r"^\s*\[ \]\s+(B\d+)\s+\(\w+\)\s+(.*)$")


def bug_for(suite, bug_lines):
    """The open bug that names the suite in its title (`devapp.mjs`,
    `test/devapp.mjs`, or `devapp's` first), the newest; "" if none does."""
    name = suite.removesuffix(".mjs")
    pat = re.compile(rf"(?<![\w-]){re.escape(name)}(?:\.mjs\b|'s\b)")
    found = [m.group(1) for m in map(BUG_LINE.match, bug_lines) if m and pat.search(m.group(2)[:200])]
    return max(found, key=lambda b: int(b[1:]), default="")


def said(rows, suite, commit=""):
    """The suite's last sighting as a bug's note says it, "" with none."""
    name = suite.removesuffix(".mjs")
    mine = [r for r in rows if r[1] == name]
    if not mine:
        return ""
    at, _s, workers, load, check, cause = mine[-1]
    when = time.strftime("%d %b %H:%M", time.localtime(at))
    return (f"{when}: flaked again in a gate{f' at {commit}' if commit else ''} ({workers} workers, load {load}), "
            f"{len(mine)} sightings on record; it failed '{check or 'before its first check'}'"
            + (f", having waited: {cause}" if cause else "") + "; passed when run again alone")


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
        bugs = []
        if opt("--bugs"):
            with open(opt("--bugs"), encoding="utf-8", errors="replace") as f:
                bugs = f.read().splitlines()
        causes = {r[1]: r[5] for r in read_causes(opt("--file")) if r[5]}
        for suite, n, last, check in got:
            b = bug_for(suite, bugs) if bugs else ""
            print(f"  {suite:<18} {n:>3}x  last {time.strftime('%d %b %H:%M', time.localtime(last))}"
                  + (f"  {b}" if b else "") + (f"  {check[:110]}" if check else ""))
            if causes.get(suite):
                print(f"  {'':<18}       waited: {causes[suite][:140]}")
        return 0
    if argv[:1] == ["said"] and len(argv) > 1:
        text = said(read_causes(opt("--file")), argv[-1], opt("--commit"))
        if not text:
            return 1
        print(text)
        return 0
    if argv[:1] == ["bug-for"] and len(argv) > 1:
        try:
            with open(opt("--bugs"), encoding="utf-8", errors="replace") as f:
                lines = f.read().splitlines()
        except OSError:
            return 1
        b = bug_for(argv[-1], lines)
        if b:
            print(b)
        return 0 if b else 1
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
