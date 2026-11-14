#!/usr/bin/env python3
"""aerie tests unit, across the machine's cores (R130).

The unit tier ran as one unittest process, 1460 tests in about 155 s on
bb-sandbox's eight cores with seven of them idle; its slowest module alone
is under 30 s. Here each module is a unit of work: the modules are dealt,
longest first by the seconds the last run measured, to the emptiest of N
buckets, each bucket one process that runs its modules in turn and times
each, all at once. The output is each failing bucket's own, then one
summary in unittest's words, which is what a reader of the tier's tail
already reads.

A module that fails in the whole run is run once more, alone, in a process
of its own; one that passes then is said as flaky and does not fail the
tier, as a browser suite that passes alone does not (the operator, 14 Nov).
The tier gates every release's tag, and a module can fail for the company
it kept: the modules of a bucket share a process, so what one leaves set is
there for the next, and a test bound to a clock loses to sixteen at once.

    unitpar.py DIR TIMES [WORKERS]
    unitpar.py --bucket DIR MODULE...     (one bucket, run by the first form)
"""
import io
import json
import os
import subprocess
import sys
import time
import unittest


def modules(d):
    return sorted(f[:-3] for f in os.listdir(d) if f.startswith("test_") and f.endswith(".py"))


def load_times(path):
    out = {}
    try:
        with open(path) as f:
            for line in f:
                name, _, secs = line.rstrip("\n").partition("\t")
                try:
                    out[name] = float(secs)
                except ValueError:
                    pass
    except OSError:
        pass
    return out


def plan(mods, times, n):
    """Longest first, each to the bucket with the least so far; a module
    never measured counts as the median of those that were."""
    known = sorted(times[m] for m in mods if m in times)
    guess = known[len(known) // 2] if known else 1.0
    buckets = [[0.0, []] for _ in range(max(1, n))]
    for m in sorted(mods, key=lambda m: -times.get(m, guess)):
        b = min(buckets, key=lambda b: b[0])
        b[0] += times.get(m, guess)
        b[1].append(m)
    return [b[1] for b in buckets if b[1]]


def bucket(d, mods):
    """Run these modules in turn, each timed; the report on stdout's last
    line as JSON, what failed above it in unittest's words."""
    os.chdir(d)
    sys.path.insert(0, d)
    report = {"ran": 0, "failures": 0, "errors": 0, "skipped": 0, "times": {}, "failed": {}}
    for m in mods:
        t0 = time.time()
        buf = io.StringIO()
        try:
            suite = unittest.defaultTestLoader.loadTestsFromName(m)
        except Exception as e:                                # noqa: BLE001 (an import that fails is a failure)
            print(f"ERROR: {m} did not load: {type(e).__name__}: {e}")
            report["errors"] += 1
            report["failed"][m] = [0, 1]
            continue
        r = unittest.TextTestRunner(stream=buf, verbosity=0).run(suite)
        report["times"][m] = round(time.time() - t0, 2)
        report["ran"] += r.testsRun
        report["failures"] += len(r.failures)
        report["errors"] += len(r.errors)
        report["skipped"] += len(r.skipped)
        if not r.wasSuccessful():
            report["failed"][m] = [len(r.failures), len(r.errors)]
            sys.stdout.write(buf.getvalue().split("\n" + "-" * 70 + "\nRan ")[0] + "\n")
    print(json.dumps(report))
    return 0


def main(argv):
    if argv and argv[0] == "--bucket":
        return bucket(argv[1], argv[2:])
    # Below everything else on the machine, as the browser suites are: the
    # emulator, a docker build and a session's own work come first.
    try:
        os.nice(19 - os.nice(0))
    except OSError:
        pass
    d, tpath = argv[0], argv[1]
    n = int(argv[2]) if len(argv) > 2 else (os.cpu_count() or 1)
    mods = modules(d)
    times = load_times(tpath)
    t0 = time.time()
    procs = [subprocess.Popen([sys.executable, os.path.abspath(__file__), "--bucket", d, *group],
                              stdout=subprocess.PIPE, stderr=subprocess.STDOUT, text=True)
             for group in plan(mods, times, n)]
    ran = failures = errors = skipped = 0
    broke = False
    new_times = {}
    failed = {}
    for p in procs:
        out, _ = p.communicate()
        lines = out.rstrip("\n").split("\n")
        try:
            rep = json.loads(lines[-1])
            body = "\n".join(lines[:-1])
        except (ValueError, IndexError):
            rep, body, broke = {}, out, True
        if body.strip():
            sys.stdout.write(body + "\n")
        ran += rep.get("ran", 0)
        failures += rep.get("failures", 0)
        errors += rep.get("errors", 0)
        skipped += rep.get("skipped", 0)
        new_times.update(rep.get("times") or {})
        failed.update(rep.get("failed") or {})
    # Once more, alone, for each module that failed: in a process of its own,
    # one at a time, with the machine to itself. What it says then is its
    # result; what it said in company is above, for whoever reads why.
    flaky = []
    for m in sorted(failed):
        was = failed[m]
        print(f"== {m} failed in the whole run: once more, alone")
        sys.stdout.flush()
        try:
            out = subprocess.run([sys.executable, os.path.abspath(__file__), "--bucket", d, m],
                                 stdout=subprocess.PIPE, stderr=subprocess.STDOUT, text=True, check=False).stdout
            lines = out.rstrip("\n").split("\n")
            rep = json.loads(lines[-1])
        except (OSError, ValueError, IndexError):
            continue
        failures -= was[0]
        errors -= was[1]
        failures += rep.get("failures", 0)
        errors += rep.get("errors", 0)
        if rep.get("failures") or rep.get("errors"):
            if "\n".join(lines[:-1]).strip():
                sys.stdout.write("\n".join(lines[:-1]) + "\n")
        else:
            flaky.append(m)
    if flaky:
        print(f"flaky: {', '.join(flaky)} failed in the whole run and passed again alone")
    try:
        os.makedirs(os.path.dirname(tpath) or ".", exist_ok=True)
        with open(tpath + ".new", "w") as f:
            for k in sorted({**times, **new_times}):
                if k in mods:
                    f.write(f"{k}\t{new_times.get(k, times.get(k))}\n")
        os.replace(tpath + ".new", tpath)
    except OSError:
        pass
    wall = time.time() - t0
    print("-" * 70)
    print(f"Ran {ran} tests in {wall:.3f}s, {len(procs)} at once (the slowest module "
          f"{max(new_times.values(), default=0):.0f}s)")
    print()
    if failures or errors or broke:
        parts = [f"failures={failures}"] if failures else []
        parts += [f"errors={errors}"] if errors else []
        print(f"FAILED ({', '.join(parts) or 'a bucket ended without its report'})")
        return 1
    print("OK" + (f" (skipped={skipped})" if skipped else ""))
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
