"""A space's test node that cannot be used ends the test run with why (B994).

aerie tests run, aerie dashboard test and the gate each asked
tests_away_node whether the suites go to the space's test node, with its
stderr thrown away: a node named in the settings and offline, gone or not
the session's was read as no test node, and the suites ran on the session's
own machine with its workers, saying nothing. The real functions are run
here from scripts/aerie, with the settings and the node check stood in."""
import os
import re
import subprocess
import tempfile
import textwrap
import unittest

HERE = os.path.dirname(os.path.abspath(__file__))
AERIE = open(os.path.join(HERE, "..", "..", "aerie"), encoding="utf-8").read()


def function(name):
    m = re.search(rf"(?ms)^{name}\(\) {{\n.*?^}}\n", AERIE)
    assert m, name
    return m.group(0)


class Refused(unittest.TestCase):
    def run_it(self, away_rc, away_out="", away_err=""):
        with tempfile.TemporaryDirectory() as d:
            with open(os.path.join(d, "tests-away.py"), "w", encoding="utf-8") as f:
                f.write(f"import sys\nsys.stdout.write({away_out!r})\nsys.stderr.write({away_err!r})\nsys.exit({away_rc})\n")
            stub = os.path.join(d, "aerie-stub")
            with open(stub, "w", encoding="utf-8") as f:
                f.write('#!/bin/sh\necho \'{"test_node": "n_away"}\'\n')
            os.chmod(stub, 0o755)
            script = textwrap.dedent("""\
                set -euo pipefail
                bb_auth_or_die() { echo "Bearer x"; }
                """) + function("tests_away_node") + function("tests_go_away") + textwrap.dedent(f"""\
                BB_LIB={d}
                if tests_go_away alpha; then echo away; else echo here; fi
                echo after
                """)
            # $0 is the stub, as scripts/aerie is its own: its settings name the node.
            return subprocess.run(["bash", "-c", script, stub], capture_output=True, text=True, timeout=60, check=False)

    def test_a_test_node_that_cannot_be_used_ends_the_run_with_why(self):
        p = self.run_it(1, away_err="[builderbot] ERROR: the test node box is offline: the suites would wait on it\n")
        self.assertEqual(p.returncode, 1, p.stdout + p.stderr)
        self.assertIn("the test node box is offline", p.stderr)
        self.assertNotIn("here", p.stdout, "never run here in its place")
        self.assertNotIn("after", p.stdout)

    def test_one_that_answers_sends_the_suites_there_and_none_runs_them_here(self):
        self.assertEqual(self.run_it(0, away_out="n_away\nbox\n4\n0\n[]\n").stdout, "away\nafter\n")
        self.assertEqual(self.run_it(0).stdout, "here\nafter\n")


if __name__ == "__main__":
    unittest.main()
