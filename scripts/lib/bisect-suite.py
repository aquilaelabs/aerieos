#!/usr/bin/env python3
"""Behind `aerie tests bisect SUITE GOOD BAD` (R55): the first commit
between GOOD (where the suite passes) and BAD (where it fails) at which it
fails, found by halving the commits between, each run with the harness's
--at, which copies the commit rather than the working tree.

A commit fails when the suite fails there, or with --check WORDS when a
FAIL line holding those words is printed. A suite with flakes on record
(.bb-map/flakes.tsv) is run three times a commit unless --times says, and a
commit counts as failing when most of its runs failed; each commit's tally
is said as it is read, and the logs are kept in a folder named at the end.

    bisect-suite.py --harness RUN_SH --flakes FILE SUITE GOOD BAD [--check WORDS] [--times N]
"""
import argparse
import os
import subprocess
import sys
import tempfile
import time


def git(*args):
    return subprocess.run(["git", *args], capture_output=True, text=True, check=True).stdout.strip()


def flaked(path, suite):
    """Whether the suite has a flake on record."""
    base = suite[:-4] if suite.endswith(".mjs") else suite
    try:
        with open(path, encoding="utf-8") as f:
            return any(base in line.split("\t")[1:2] or (base + ".mjs") in line.split("\t")[1:2] for line in f)
    except OSError:
        return False


def run_at(harness, suite, sha, check, log):
    """One run of the suite at a commit: True when it failed."""
    with open(log, "w", encoding="utf-8") as out:
        rc = subprocess.run(["bash", harness, suite, "--at", sha], stdout=out, stderr=subprocess.STDOUT).returncode
    if not check:
        return rc != 0
    with open(log, encoding="utf-8", errors="replace") as f:
        return any(line.startswith("FAIL") and check in line for line in f)


def main(argv):
    ap = argparse.ArgumentParser(prog="aerie tests bisect")
    ap.add_argument("--harness", required=True)
    ap.add_argument("--flakes", default="")
    ap.add_argument("suite")
    ap.add_argument("good")
    ap.add_argument("bad")
    ap.add_argument("--check", default="")
    ap.add_argument("--times", type=int, default=0)
    a = ap.parse_args(argv)
    try:
        good, bad = git("rev-parse", "--verify", a.good + "^{commit}"), git("rev-parse", "--verify", a.bad + "^{commit}")
        between = git("rev-list", "--reverse", "--ancestry-path", f"{good}..{bad}").split()
    except subprocess.CalledProcessError as e:
        sys.exit(f"[builderbot] ERROR: {(e.stderr or '').strip() or 'not commits of this repository'}")
    if not between or between[-1] != bad:
        sys.exit(f"[builderbot] ERROR: {a.bad} does not come after {a.good} on one line of history")
    times = a.times or (3 if a.flakes and flaked(a.flakes, a.suite) else 1)
    logs = tempfile.mkdtemp(prefix="bb-bisect.")
    said = f" (a FAIL line holding {a.check!r})" if a.check else ""
    print(f"bisect {a.suite}{said}: {len(between)} commit(s) after {good[:9]}, up to {bad[:9]}; "
          f"{times} run(s) a commit{' (it has flaked before)' if times > 1 and not a.times else ''}", flush=True)
    seen = {}

    def fails(sha):
        if sha in seen:
            return seen[sha]
        bad_runs = 0
        for i in range(times):
            t = time.time()
            if run_at(a.harness, a.suite, sha, a.check, os.path.join(logs, f"{sha[:9]}-{i + 1}.log")):
                bad_runs += 1
            if bad_runs * 2 > times or (i + 1 - bad_runs) * 2 > times:
                break
        ran = i + 1
        seen[sha] = bad_runs * 2 > ran
        subj = git("log", "-1", "--format=%s", sha)[:70]
        print(f"  {sha[:9]} {'fails' if seen[sha] else 'passes'} ({bad_runs} of {ran} failed, "
              f"{int(time.time() - t)}s the last)  {subj}", flush=True)
        return seen[sha]

    if not fails(bad):
        print(f"{a.suite} passes at {bad[:9]}: nothing to find; logs in {logs}")
        return 1
    lo, hi = -1, len(between) - 1           # between[lo] passes (GOOD), between[hi] fails
    while hi - lo > 1:
        mid = (lo + hi) // 2
        if fails(between[mid]):
            hi = mid
        else:
            lo = mid
    first = between[hi]
    print(f"the first commit where {a.suite} fails{said}: {first[:9]} {git('log', '-1', '--format=%s', first)}")
    print(f"logs in {logs}")
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
