"""aerie tests bisect (R55): the first commit between GOOD and BAD where a
suite fails, found by halving, with a stand-in harness that fails at a
commit carrying a file the fourth commit adds; a suite with flakes on
record runs three times a commit, and --check counts only its own FAIL."""
import os
import shutil
import subprocess
import sys
import tempfile
import unittest

HERE = os.path.dirname(os.path.abspath(__file__))
BISECT = os.path.abspath(os.path.join(HERE, "..", "..", "lib", "bisect-suite.py"))
HARNESS = """#!/bin/bash
# SUITE --at SHA: fails where the commit has `bad`, saying so as a FAIL line.
echo "$3" >> "$(dirname "$0")/ran"
if git cat-file -e "$3:bad" 2>/dev/null; then echo "FAIL  the card opens"; exit 1; fi
echo "PASS  the card opens"
"""


class Bisect(unittest.TestCase):
    def setUp(self):
        self.d = tempfile.mkdtemp()
        self.addCleanup(shutil.rmtree, self.d, ignore_errors=True)
        g = ["git", "-C", self.d, "-c", "user.name=t", "-c", "user.email=t@t"]
        subprocess.run(g[:3] + ["init", "-q"], check=True)
        self.shas = []
        for i in range(1, 8):
            open(os.path.join(self.d, f"f{i}"), "w").write(str(i))
            if i == 4:
                open(os.path.join(self.d, "bad"), "w").write("x")
            subprocess.run(g + ["add", "-A"], check=True)
            subprocess.run(g + ["commit", "-qm", f"commit {i}"], check=True)
            self.shas.append(subprocess.run(g[:3] + ["rev-parse", "HEAD"], capture_output=True, text=True).stdout.strip())
        self.harness = os.path.join(self.d, "run.sh")
        open(self.harness, "w").write(HARNESS)
        self.flakes = os.path.join(self.d, "flakes.tsv")

    def bisect(self, *extra):
        r = subprocess.run([sys.executable, BISECT, "--harness", self.harness, "--flakes", self.flakes, "cards",
                            self.shas[0], self.shas[-1], *extra], capture_output=True, text=True, cwd=self.d)
        ran = open(os.path.join(self.d, "ran")).read().split() if os.path.exists(os.path.join(self.d, "ran")) else []
        return r, ran

    def test_the_first_failing_commit_is_named(self):
        r, ran = self.bisect()
        self.assertEqual(r.returncode, 0, r.stdout + r.stderr)
        self.assertIn(f"the first commit where cards fails: {self.shas[3][:9]} commit 4", r.stdout)
        self.assertLessEqual(len(set(ran)), 4, "halved, not every commit")

    def test_a_suite_that_has_flaked_runs_more_than_once_a_commit(self):
        open(self.flakes, "w").write("1794700000\tcards\t8\t9\tthe card opens\n")
        r, ran = self.bisect()
        self.assertIn("2 of 2 failed", r.stdout)
        self.assertIn(f"{self.shas[3][:9]} commit 4", r.stdout.splitlines()[-2])

    def test_a_check_it_does_not_print_finds_nothing(self):
        r, _ = self.bisect("--check", "a check nobody prints")
        self.assertEqual(r.returncode, 1)
        self.assertIn("passes at", r.stdout)


if __name__ == "__main__":
    unittest.main()
