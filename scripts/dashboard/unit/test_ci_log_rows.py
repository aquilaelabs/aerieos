"""aerie ci-log's list of the kept logs, once a release's tag keeps one log
for several jobs (R206): the lint, the unit tier and the browser suites run
before anything is built to publish, each adds its part under the first's
head, and the run reads as its worst job's result, where the first job to
finish said only how it went itself."""
import os
import shutil
import subprocess
import tempfile
import unittest

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.abspath(os.path.join(HERE, "..", "..", ".."))
AERIE = os.path.join(ROOT, "scripts", "aerie")


class Rows(unittest.TestCase):
    def setUp(self):
        self.d = tempfile.mkdtemp()
        self.addCleanup(shutil.rmtree, self.d, True)
        self.logs = os.path.join(self.d, os.path.basename(ROOT))
        os.makedirs(self.logs)

    def keep(self, name, text, age):
        p = os.path.join(self.logs, name + ".log")
        with open(p, "w") as f:
            f.write(text)
        os.utime(p, (1_700_000_000 - age, 1_700_000_000 - age))

    def listed(self):
        p = subprocess.run(["bash", AERIE, "ci-log", "--list"], cwd=ROOT, capture_output=True, text=True, check=False,
                           env=dict(os.environ, BB_RELAYED="1", BB_CI_LOG_DIR=self.d))
        return {ln.split()[0]: ln for ln in p.stdout.splitlines() if ln.startswith("  ")}

    def test_a_run_of_several_jobs_reads_as_its_worst(self):
        self.keep("900-1", "# build image on o/aerieos\nrun: 900\n\nlint: clean\n\nresult: success\n\n== unit ==\nOK\n\nresult: success\n"
                           "\n== dashboard ==\nFAIL  a check\n\nresult: failure\n\n== the run ==\njob build: skipped\nresult: failure\n", 30)
        self.keep("901-1", "# lint on o/aerieos\n\nresult: success\n\n== unit ==\nresult: success\n", 20)
        self.keep("902-1", "# build image on o/aerieos\n\nresult: success\n\n== unit ==\nresult: cancelled\n", 10)
        self.keep("903-1", "# dashboard tests on o/aerieos\n\nstill going\n", 0)
        got = self.listed()
        self.assertRegex(got["900-1"], r"build image\s+failure")
        self.assertRegex(got["901-1"], r"lint\s+success")
        self.assertRegex(got["902-1"], r"build image\s+cancelled")
        self.assertIn("(unfinished)", got["903-1"])

    def test_every_job_adds_to_the_runs_log_and_none_begins_it_again(self):
        # The workflows that keep a log: the head is written only where the
        # log is new, so a later job of the same run cannot take what an
        # earlier one wrote.
        for wf, opens in (("lint.yml", 2), ("dashboard.yml", 1), ("build-image.yml", 1)):
            with open(os.path.join(ROOT, ".github", "workflows", wf), encoding="utf-8") as f:
                text = f.read()
            self.assertEqual(text.count('if [ -s "$log" ]; then'), opens, wf)
            for block in text.split('if [ -s "$log" ]; then')[1:]:
                self.assertIn('} > "$log"', block.split("\n          fi\n")[0], wf)
            # ...and nothing writes over it outside that guard.
            self.assertEqual(text.count('} > "$log"'), opens, wf)


if __name__ == "__main__":
    unittest.main()
