"""A job ends when its own process and its group have, even when a process
that left the group still holds its output: the loop waited for the pipe to
close, so such a job ran on for ever and held every update of the agent as
busy. What is still in the job's own group is its work, waited for as before."""
import os
import signal
import tempfile
import time
import unittest
from unittest import mock
import agentpkg  # noqa: E402
from test_agent_sh import FakeJob  # noqa: E402

agent = agentpkg.load("aerieos_agent")
jobs = agent.module("jobs")


class Held(unittest.TestCase):
    def setUp(self):
        self.d = tempfile.mkdtemp()
        self.pidf = os.path.join(self.d, "pid")

    def tearDown(self):
        try:
            with open(self.pidf) as f:
                os.kill(int(f.read().strip()), signal.SIGKILL)
        except (OSError, ValueError):
            pass

    def run_sh(self, script, timeout=30):
        job = FakeJob()
        t0 = time.monotonic()
        with mock.patch.object(jobs, "TAIL_S", 1):
            rc = agent.Agent._sh(None, job, ["sh", "-c", script], timeout=timeout)
        return rc, "".join(t for _, t in job.posts) + "".join(job.pending), time.monotonic() - t0

    def test_a_process_that_left_the_group_holding_the_output_is_not_waited_for(self):
        rc, said, took = self.run_sh(f"setsid sh -c 'echo $$ > {self.pidf}; exec sleep 60' & echo started")
        self.assertEqual(rc, 0)
        self.assertLess(took, 10, "the job ended with its own process, not with the pipe")
        self.assertIn("started", said)
        self.assertIn("left its group; not waited for", said)

    def test_work_still_in_the_group_is_waited_for(self):
        rc, said, took = self.run_sh("(sleep 1.5; echo late) & echo early")
        self.assertEqual(rc, 0)
        self.assertIn("late", said, "a child in the job's own group is its work")
        self.assertNotIn("not waited for", said)
        self.assertGreater(took, 1.2)


if __name__ == "__main__":
    unittest.main()
