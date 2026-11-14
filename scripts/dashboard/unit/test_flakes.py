"""The harness remembers its flakes, and the pre-push gate fails on one
(R7 step 3; the operator's choice of 14 Nov: recorded and counted, a gate
fails on a flake in a suite it ran, a release's tag still counts it as
passed).

A suite that failed in a whole run and passed when run again was named in
the terminal and forgotten; tests-verdict dropped it from what went wrong
and the harness exited 0, so the same ten suites flaked for weeks with no
count of which or why."""
import importlib.util
import os
import shutil
import subprocess
import sys
import tempfile
import unittest

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.abspath(os.path.join(HERE, "..", "..", ".."))
LIB = os.path.join(ROOT, "scripts", "lib")
spec = importlib.util.spec_from_file_location("flakes_under_test", os.path.join(LIB, "flakes.py"))
flakes = importlib.util.module_from_spec(spec)
spec.loader.exec_module(flakes)

WORKER = """[dashboard-test] == cards.mjs ==
PASS  the card draws
FAIL  the back of the card opens on a press (still the front after 20000ms)
FAIL  ...and closes again
3 passed, 2 failed
[dashboard-test] == nodes.mjs ==
PASS  a node enrolls
12 passed, 0 failed
[dashboard-test] == devapp.mjs ==
FAIL  the instance comes up (state: starting)
"""
AGAIN = """[dashboard-test] == cards.mjs again ==
FAIL  a different check, in the rerun's own log
PASS  the card draws
"""
RUN = """[dashboard-test] workers: 477 passed, 3 failed across 8 workers, 49 suites; failed in the run: cards devapp
[dashboard-test] WARN: flaky: cards.mjs devapp.mjs failed in the whole run and passed again alone
[dashboard-test] took: 14m21s wall
"""


class Record(unittest.TestCase):
    def setUp(self):
        self.d = tempfile.mkdtemp()
        self.addCleanup(shutil.rmtree, self.d, True)
        self.file = os.path.join(self.d, ".bb-map", "flakes.tsv")
        self.logs = []
        for name, body in (("worker-1.log", WORKER), ("again-1.log", AGAIN)):
            p = os.path.join(self.d, name)
            with open(p, "w") as f:
                f.write(body)
            self.logs.append(p)

    def test_a_flake_is_a_line_with_the_first_check_that_failed_in_the_run(self):
        rows = flakes.record(self.file, ["cards.mjs", "devapp.mjs"], 8, "14.6", self.logs, now=1794700000)
        self.assertEqual(len(rows), 2)
        got = flakes.read(self.file)
        self.assertEqual(got[0], (1794700000, "cards", "8", "14.6",
                                  "the back of the card opens on a press (still the front after 20000ms)"))
        # The run's failure, never the rerun's: the rerun passed, or it would not be a flake.
        self.assertNotIn("different check", got[0][4])
        self.assertEqual(got[1][1:], ("devapp", "8", "14.6", "the instance comes up (state: starting)"))

    def test_one_with_no_log_to_read_is_still_recorded_and_a_name_that_is_not_one_is_not(self):
        flakes.record(self.file, ["sessions.mjs", "../../etc/passwd\tx"], 1, "0.4", [], now=1794700000)
        self.assertEqual(flakes.read(self.file), [(1794700000, "sessions", "1", "0.4", "")])
        self.assertEqual(flakes.record(self.file, [], 8, "1", self.logs), [])

    def test_they_are_counted_over_the_days_asked_the_most_often_first(self):
        day = 86400
        now = 1794700000
        flakes.record(self.file, ["cards.mjs"], 16, "40", self.logs, now=now - 40 * day)
        flakes.record(self.file, ["cards.mjs", "devapp.mjs"], 16, "45", self.logs, now=now - 3 * day)
        flakes.record(self.file, ["devapp.mjs"], 10, "14", [], now=now - 1 * day)
        flakes.record(self.file, ["devapp.mjs"], 10, "14", self.logs, now=now)
        got = flakes.counted(flakes.read(self.file), days=30, now=now)
        self.assertEqual([(s, n) for s, n, _at, _said in got], [("devapp", 3), ("cards", 1)])
        self.assertEqual(got[0][2:], (now, "the instance comes up (state: starting)"))
        self.assertEqual([(s, n) for s, n, _a, _c in flakes.counted(flakes.read(self.file), days=60, now=now)],
                         [("devapp", 3), ("cards", 2)])
        self.assertEqual(flakes.counted(flakes.read(os.path.join(self.d, "none.tsv")), now=now), [])

    def test_a_runs_log_says_which_were_flaky(self):
        self.assertEqual(flakes.of_log(RUN), ["cards", "devapp"])
        self.assertEqual(flakes.of_log("all 49 suites passed\n"), [])
        # The gate's own sentence about a flake is not read back as another.
        self.assertEqual(flakes.of_log("  FAIL  flaky in this gate: cards. Each failed in the run and passed when run again\n"), [])

    def test_the_verbs(self):
        run = lambda *a: subprocess.run([sys.executable, os.path.join(LIB, "flakes.py"), *a], capture_output=True, text=True, check=False)
        r = run("record", "--file", self.file, "--workers", "8", "--load", "12.5", "--logs", *self.logs, "--suites", "cards.mjs", "devapp.mjs")
        self.assertEqual(r.returncode, 0, r.stderr)
        r = run("list", "--file", self.file)
        self.assertIn("cards", r.stdout)
        self.assertIn("1x", r.stdout)
        self.assertIn("the back of the card opens", r.stdout)
        self.assertIn("no suite has been flaky", run("list", "--file", os.path.join(self.d, "none.tsv")).stdout)
        log = os.path.join(self.d, "run.log")
        with open(log, "w") as f:
            f.write(RUN)
        self.assertEqual(run("of-log", log).stdout.strip(), "cards devapp")


class Wired(unittest.TestCase):
    def read(self, *rel):
        with open(os.path.join(ROOT, *rel), encoding="utf-8") as f:
            return f.read()

    def test_the_harness_records_each_flake_it_names_on_both_its_paths(self):
        src = self.read("scripts", "dashboard", "test", "run.sh")
        self.assertEqual(src.count('warn "flaky: ${flaky[*]} failed in the whole run and passed again alone"'), 2)
        self.assertIn('flakes_record "$n" "${logs[*]}" "${flaky[@]}"', src)
        self.assertIn('flakes_record 1 "" "${flaky[@]}"', src)
        self.assertIn('--file "$(dirname "$SUITE_TIMES")/flakes.tsv"', src)
        # What the harness prints is what of_log reads.
        self.assertEqual(flakes.of_log("[dashboard-test] WARN: flaky: a.mjs failed in the whole run and passed again alone"), ["a"])

    def test_the_gate_fails_on_one_and_the_tags_gate_does_not_read_them(self):
        pre = self.read("scripts", "lib", "preflight.sh")
        at = pre.index('flk="$(python3 "$BB_LIB/flakes.py" of-log "$rl"')
        gate = pre[at:pre.index("    local c\n", at)]
        self.assertIn("rc=1", gate)
        self.assertIn("flaky in this gate", gate)
        for wf in ("dashboard.yml", "build-image.yml", "lint.yml"):
            self.assertNotIn("flakes.py", self.read(".github", "workflows", wf), wf)
        self.assertIn('python3 "$BB_LIB/flakes.py" list --file "${BB_REPO:-$PWD}/.bb-map/flakes.tsv"', self.read("scripts", "aerie"))

    def test_a_harness_change_fails_only_on_a_flake_the_change_itself_touches(self):
        # The operator, 14 Nov: when every suite runs only because lib.mjs
        # or run.sh changed, a flake in a suite the change does not touch by
        # itself is recorded and named, and does not fail the gate.
        pre = self.read("scripts", "lib", "preflight.sh")
        self.assertIn("scripts/dashboard/test/lib.mjs|scripts/dashboard/test/run.sh) all_dash=1; harness=1 ;;", pre)
        self.assertIn('touched=("${suites[@]}")', pre)
        self.assertIn("harness_only=1", pre)
        at = pre.index('if [ -n "$flk" ] && [ -n "$harness_only" ]; then')
        block = pre[at:pre.index("    local c\n", at)]
        self.assertIn('case " ${touched[*]:-} " in *" $x "*) fk="$fk $x" ;; *) fo="$fo $x" ;; esac', block)
        self.assertIn("NOTE  flaky, recorded and not failed", block)
        self.assertIn('flk="${fk# }"', block)
        # server.py with nothing to place it by reaches every suite itself: strict.
        self.assertIn("|| { all_dash=1; whole=1; } ;;", pre)
        self.assertIn('if [ -n "$whole" ] || { [ -n "$all_dash" ] && [ -z "$harness" ]; }; then', pre)

    def test_the_count_is_read_on_the_machine_the_runs_were_on(self):
        # A session's verbs go to the controller unless they are named as
        # this machine's own; the record is beside the tree the harness ran
        # from, and the controller answered "unknown: aerie tests flakes".
        self.assertIn('|"tests flakes"|"tests root"|', self.read("scripts", "aerie"))


if __name__ == "__main__":
    unittest.main()
