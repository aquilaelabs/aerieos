#!/usr/bin/env python3
"""aerie tests root: the root tier (R240 step 5, R3 step 8).

What the root agent and the root helpers do in a folder an account controls
is only seen for real by root: a suite's node is an ordinary account, where
acting as another changes nothing, and the browser harness refuses to run
as root at all. The modules of scripts/dashboard/roottier plant a link
where root works and see that root's own file is as it was.

    roottier.py [--here] [MODULE...]

As root, in a container: tools/root-tier.sh runs it in a throwaway one of
the controller's image, CI on every release, and `aerie devapp test
root-tier` in a space's dev instance. It makes folders, files and links
under a temporary folder and nowhere else, and still refuses a machine
that is not a container unless --here says this one is meant. A test that
skips here proved nothing, so a skip fails the tier.
"""
import os
import sys
import unittest

HERE = os.path.dirname(os.path.abspath(__file__))
TIER = os.path.normpath(os.path.join(HERE, "..", "dashboard", "roottier"))


def in_container():
    return os.path.exists("/.dockerenv") or os.path.exists("/run/.containerenv") or bool(os.environ.get("container"))


def refusal(uid, contained, here):
    """Why the tier does not run as it was started, or ""."""
    if uid != 0:
        return ("the root tier runs as root, which this is not: tools/root-tier.sh IMAGE runs it in a throwaway "
                "container where docker answers, and `aerie devapp test root-tier` in a space's dev instance")
    if not contained and not here:
        return ("this is root on a machine, not in a container: the root tier works under a temporary folder alone, "
                "and --here says this machine is meant")
    return ""


def main(argv):
    here = "--here" in argv
    names = [a for a in argv if not a.startswith("-")]
    no = refusal(os.geteuid(), in_container(), here)
    if no:
        print(f"[root-tier] {no}", file=sys.stderr)
        return 2
    sys.path.insert(0, TIER)
    load = unittest.defaultTestLoader
    suite = load.loadTestsFromNames(names) if names else load.discover(TIER, pattern="test_*.py", top_level_dir=TIER)
    r = unittest.TextTestRunner(verbosity=2).run(suite)
    for test, why in r.skipped:
        print(f"[root-tier] skipped, which proves nothing here: {test.id()} ({why})", file=sys.stderr)
    whole = r.wasSuccessful() and not r.skipped and r.testsRun > 0
    if r.testsRun == 0:
        print("[root-tier] no test ran", file=sys.stderr)
    print(f"[root-tier] {r.testsRun} ran as root: {'every one holds' if whole else 'NOT every one holds'}")
    return 0 if whole else 1


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
