"""The unit tier runs a module that failed once more, alone, and one that
passes then does not fail the tier (R206; the operator's rule for a suite,
14 Nov). The tier gates every release's tag since CI runs it, and a module
can fail for the company it kept: a bucket's modules share a process, so
what one leaves set is there for the next (a helper's path, a switch in the
environment), and a test bound to a clock loses with sixteen at once."""
import os
import shutil
import subprocess
import sys
import tempfile
import unittest

HERE = os.path.dirname(os.path.abspath(__file__))
TOOL = os.path.abspath(os.path.join(HERE, "..", "..", "lib", "unitpar.py"))

# One module leaves a switch on in the process; the next fails when it finds
# it on. Alone, in its own process, the second passes.
LEAKS = "import os, unittest\nclass T(unittest.TestCase):\n    def test_it(self):\n        os.environ['UNITPAR_LEFT_ON'] = '1'\n"
MINDS = ("import os, unittest\nclass T(unittest.TestCase):\n    def test_it(self):\n"
         "        self.assertNotIn('UNITPAR_LEFT_ON', os.environ, 'left on by the module before')\n")
BROKEN = "import unittest\nclass T(unittest.TestCase):\n    def test_it(self):\n        self.assertEqual(1, 2, 'wrong whoever is beside it')\n"
FINE = "import unittest\nclass T(unittest.TestCase):\n    def test_it(self):\n        pass\n"


class Alone(unittest.TestCase):
    def setUp(self):
        self.d = tempfile.mkdtemp()
        self.addCleanup(shutil.rmtree, self.d, True)

    def tier(self, mods, workers=1):
        for name, text in mods.items():
            with open(os.path.join(self.d, name + ".py"), "w", encoding="utf-8") as f:
                f.write(text)
        # One bucket, the leaking module first: the last run's timings say
        # which is longest, and the longest is dealt first.
        times = os.path.join(self.d, "times.tsv")
        with open(times, "w", encoding="utf-8") as f:
            f.write("".join(f"{m}\t{9 - i}\n" for i, m in enumerate(sorted(mods))))
        env = {k: v for k, v in os.environ.items() if k != "UNITPAR_LEFT_ON"}
        return subprocess.run([sys.executable, TOOL, self.d, times, str(workers)], capture_output=True, text=True,
                              timeout=120, check=False, env=env)

    def test_a_module_that_fails_in_company_and_passes_alone_is_flaky_and_the_tier_passes(self):
        r = self.tier({"test_a_leaks": LEAKS, "test_b_minds": MINDS, "test_c_fine": FINE})
        self.assertEqual(r.returncode, 0, r.stdout + r.stderr)
        self.assertIn("left on by the module before", r.stdout, "what it said in company is kept above")
        self.assertIn("== test_b_minds failed in the whole run: once more, alone", r.stdout)
        self.assertIn("flaky: test_b_minds failed in the whole run and passed again alone", r.stdout)
        self.assertTrue(r.stdout.rstrip().endswith("OK"), r.stdout[-200:])

    def test_a_module_that_fails_alone_too_fails_the_tier_with_its_own_count(self):
        r = self.tier({"test_a_leaks": LEAKS, "test_b_minds": MINDS, "test_c_broken": BROKEN})
        self.assertEqual(r.returncode, 1, r.stdout + r.stderr)
        self.assertIn("flaky: test_b_minds", r.stdout)
        self.assertNotIn("test_c_broken failed in the whole run and passed", r.stdout)
        self.assertEqual(r.stdout.count("AssertionError: 1 != 2"), 2, "said in the whole run and again alone")
        self.assertTrue(r.stdout.rstrip().endswith("FAILED (failures=1)"), r.stdout[-200:])

    def test_a_tier_with_nothing_wrong_runs_nothing_twice(self):
        r = self.tier({"test_a_fine": FINE, "test_b_fine": FINE}, workers=2)
        self.assertEqual(r.returncode, 0, r.stdout + r.stderr)
        self.assertNotIn("once more, alone", r.stdout)
        self.assertIn("Ran 2 tests", r.stdout)


if __name__ == "__main__":
    unittest.main()
