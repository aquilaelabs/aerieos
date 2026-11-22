"""A job's timeout is a clock, and it ends what the job started (R246; the
audit of 13 Nov): jobs.stream looked at its deadline only when a line
arrived, so a child that printed nothing was never ended, and a timed-out
command was killed alone and then waited on, for as long as anything it had
started held its pipe."""
import os
import shutil
import subprocess
import sys
import tempfile
import time
import unittest

sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)), ".."))
import jobs  # noqa: E402


class Run:
    def __init__(self):
        self.said, self.held = "", []

    def line(self, text):
        self.said += text

    def hold(self, proc):
        self.held.append(proc)


def alive(pid):
    try:
        os.kill(pid, 0)
    except OSError:
        return False
    # A zombie still answers kill 0: read what it is.
    try:
        with open(f"/proc/{pid}/stat") as f:
            return f.read().rsplit(")", 1)[1].split()[0] != "Z"
    except OSError:
        return False


class Stream(unittest.TestCase):
    def setUp(self):
        self.d = tempfile.mkdtemp()
        self.addCleanup(shutil.rmtree, self.d, True)

    def test_a_job_that_says_nothing_still_runs_out_of_time(self):
        run, t0 = Run(), time.time()
        got = jobs.stream(["sh", "-c", "sleep 30"], run, 1)
        self.assertLess(time.time() - t0, 8)
        self.assertEqual(got["code"], 124)
        self.assertIn("timed out after 1s", run.said)

    def test_what_it_started_goes_with_it(self):
        pidf = os.path.join(self.d, "child.pid")
        run, t0 = Run(), time.time()
        got = jobs.stream(["sh", "-c", f"sleep 60 & echo $! > {pidf}; echo started; wait"], run, 1)
        self.assertLess(time.time() - t0, 8)
        self.assertEqual(got["code"], 124)
        self.assertIn("started", run.said)
        with open(pidf) as f:
            child = int(f.read())
        for _ in range(40):
            if not alive(child):
                break
            time.sleep(0.1)
        self.assertFalse(alive(child), "the sleep the job started was ended with it")

    def test_one_that_ends_in_time_is_as_it_was(self):
        run = Run()
        got = jobs.stream(["sh", "-c", "echo one; echo two; exit 3"], run, 30)
        self.assertEqual((got["code"], got["out"]), (3, "one\ntwo\n"))
        self.assertNotIn("timed out", run.said)

    def test_a_job_that_ignores_term_is_killed(self):
        run, t0 = Run(), time.time()
        got = jobs.stream(["sh", "-c", "trap '' TERM; echo deaf; sleep 60"], run, 1)
        self.assertLess(time.time() - t0, 12)
        self.assertEqual(got["code"], 124)


class End(unittest.TestCase):
    def test_a_grandchild_holding_the_pipe_does_not_hold_the_caller(self):
        # server.run's case without a group of its own: the child is ended,
        # and the wait on its output is bounded where it was not.
        p = subprocess.Popen(["sh", "-c", "sleep 20 & echo $!; wait"], stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True)
        child = int(p.stdout.readline())
        self.addCleanup(lambda: alive(child) and os.kill(child, 9))
        t0 = time.time()
        jobs.end(p, grouped=False, grace=1)
        self.assertLess(time.time() - t0, 4)
        self.assertIsNotNone(p.poll())
        self.assertTrue(p.stdout.closed)


if __name__ == "__main__":
    unittest.main()
