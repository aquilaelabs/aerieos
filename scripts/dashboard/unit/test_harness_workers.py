"""How many suites the browser harness runs at once, and how it runs the
ones that failed again (R228 step 19; measured 14 Nov on sixteen cores, a
quiet machine: eight workers 9m16s with nothing failed, ten 14m21s with
three suites run again, sixteen 39m54s with ten).

BB_TEST_WORKERS is what a test run on a node may use at most, every core
unless the node says, and the harness took all of it: a suite is a server,
a browser and its node, so the box ran at twice its cores. It takes half
the cores at most now, and reruns three at a time, each on a port picked
for it. The harness is the test of itself; this holds its arithmetic and
the shape of its reruns."""
import os
import subprocess
import unittest

HERE = os.path.dirname(os.path.abspath(__file__))
RUN = os.path.abspath(os.path.join(HERE, "..", "test", "run.sh"))
with open(RUN, encoding="utf-8") as f:
    SRC = f.read()


def workers(asked, cores, own=""):
    """What the harness's own lines make of BB_TEST_WORKERS=asked on a
    machine of `cores`, with BB_TEST_SUITES_AT_ONCE=own: (workers, said)."""
    start = SRC.index("    _half=$(( ($(nproc")
    block = SRC[start:SRC.index("    esac\n", start) + len("    esac\n")]
    script = (f"nproc() {{ echo {cores}; }}\nlog() {{ echo \"said: $*\"; }}\n_n={asked}\n"
              + (f"BB_TEST_SUITES_AT_ONCE={own}\n" if own else "") + block + 'echo "n=$_n"\n')
    r = subprocess.run(["bash", "-c", script], capture_output=True, text=True, check=True,
                       env={"PATH": os.environ.get("PATH", "/usr/bin:/bin")})
    out = r.stdout.splitlines()
    return int(out[-1][2:]), " ".join(x for x in out if x.startswith("said: "))


class Workers(unittest.TestCase):
    def test_half_the_cores_at_most_and_it_says_so(self):
        n, said = workers(16, 16)
        self.assertEqual(n, 8)
        self.assertIn("workers: 8, half this machine's cores, of the 16 a test run here may use", said)
        self.assertIn("BB_TEST_SUITES_AT_ONCE", said)
        self.assertEqual(workers(10, 16)[0], 8)
        self.assertEqual(workers(4, 4)[0], 2)
        self.assertEqual(workers(3, 3)[0], 2, "half of three cores, rounded up")
        self.assertEqual(workers(2, 1)[0], 1)

    def test_fewer_than_half_is_left_as_asked_and_nothing_is_said(self):
        self.assertEqual(workers(3, 16), (3, ""))
        self.assertEqual(workers(8, 16), (8, ""))

    def test_the_harnesss_own_number_is_taken_as_it_is(self):
        self.assertEqual(workers(16, 16, own="12"), (12, ""))
        self.assertEqual(workers(4, 16, own="6"), (6, ""))
        # ...and one that is no number is no choice.
        self.assertEqual(workers(16, 16, own="lots")[0], 8)
        self.assertEqual(workers(16, 16, own="0")[0], 8)


class Reruns(unittest.TestCase):
    def test_they_run_three_at_a_time_each_on_a_port_picked_for_it(self):
        start = SRC.index("    # Once more for each suite that failed, in a world of its own, three at")
        block = SRC[start:SRC.index("    if [ \"${#flaky[@]}\" -gt 0 ]; then", start)]
        self.assertIn('at_once="${BB_TEST_RERUNS_AT_ONCE:-3}"', block)
        self.assertIn('mapfile -t rports < <(free_ports "${#failed[@]}")', block)
        self.assertIn('BB_TEST_WORKER=again BB_TEST_AGAIN=1 DASHBOARD_TEST_PORT="${rports[k]}"', block)
        self.assertIn("for ((j = 0; j < ${#failed[@]}; j += at_once)); do", block)
        # Each is waited for by its own pid, so one that fails again is a failure and never lost among the others.
        self.assertIn('if wait "${rpids[k]}"; then', block)
        self.assertIn("again_failed+=(", block)
        self.assertIn("rc=1", block)
        # One that failed beside the other reruns is run once more by itself before it is a failure.
        self.assertIn('beside+=("$t")', block)
        self.assertIn('for t in "${beside[@]}"; do', block)
        self.assertIn("once more, by itself", block)
        # ...and ended with the run if the run is.
        self.assertIn('WORKER_PIDS+=("$!")', block)


class InFlight(unittest.TestCase):
    def test_a_request_a_reload_cut_off_is_not_counted_for_good(self):
        with open(os.path.join(HERE, "..", "test", "lib.mjs"), encoding="utf-8") as f:
            lib = f.read()
        self.assertIn("if (own) open.clear();", lib)
        self.assertIn("r.isNavigationRequest() && r.frame() === page.mainFrame()", lib)
        self.assertIn("if (at >= cut) n++;", lib)
        self.assertNotIn("inFlight++", lib, "a count that goes up and down never comes back from a request with no end")

    def test_a_predicate_that_answers_with_a_promise_is_asked_until_it_is_true(self):
        # Playwright takes the Promise as the answer at its first look
        # (probed 14 Nov: one call, 23 ms, for a predicate that resolves
        # false), so a wait on the server's answer written with an async
        # function waited for nothing; the suites' wrapper asks it itself.
        with open(os.path.join(HERE, "..", "test", "lib.mjs"), encoding="utf-8") as f:
            lib = f.read()
        self.assertIn('args[0].constructor?.name === "AsyncFunction"', lib)
        self.assertIn("return await (promised ? asked() : real(...args));", lib)
        self.assertIn("if (await h.evaluate(v => !!v)) return h;", lib)
        self.assertIn('e.name = "TimeoutError";', lib)


if __name__ == "__main__":
    unittest.main()
