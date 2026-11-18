"""A self-hosted runner is busy while a job of its own runs, and listening
while its listener runs, whichever bin folder it runs from: a runner that
updated itself runs from bin.VERSION/, which the checks under bin/ alone read
as idle (B755: the .env sync restarted it under the job) and as not listening
(B971: its row said Reinstall runner while it took jobs)."""
import os
import sys
import tempfile
import unittest

sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)), ".."))
import agentpkg  # noqa: E402

runners = agentpkg.load("aerieos_agent_runner_busy").module("runners")


class RunnerBusy(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.mkdtemp()
        self.d = os.path.join(self.tmp, "actions-runner")
        self.proc = os.path.join(self.tmp, "proc")
        for sub in ("bin", "bin.2.330.0"):
            os.makedirs(os.path.join(self.d, sub))
            open(os.path.join(self.d, sub, "Runner.Worker"), "w").close()
        os.makedirs(self.proc)

    def ps(self, pid, *argv):
        os.makedirs(os.path.join(self.proc, str(pid)))
        with open(os.path.join(self.proc, str(pid), "cmdline"), "wb") as f:
            f.write(b"\0".join(a.encode() for a in argv) + b"\0")

    def test_idle_with_only_its_listener(self):
        self.ps(10, os.path.join(self.d, "bin.2.330.0", "Runner.Listener"), "run")
        self.assertFalse(runners.runner_busy(self.d, proc=self.proc))

    def test_a_job_from_an_updated_runners_bin_is_busy(self):
        self.ps(11, os.path.join(self.d, "bin.2.330.0", "Runner.Worker"), "spawnclient", "107", "110")
        self.assertTrue(runners.runner_busy(self.d, proc=self.proc))

    def test_a_job_from_bin_is_busy_and_another_runners_is_not_this_ones(self):
        self.ps(12, "/home/other/actions-runner/bin/Runner.Worker", "spawnclient")
        self.assertFalse(runners.runner_busy(self.d, proc=self.proc), "another runner's job")
        self.ps(13, os.path.join(self.d, "bin", "Runner.Worker"), "spawnclient")
        self.assertTrue(runners.runner_busy(self.d, proc=self.proc))

    def test_a_listener_from_an_updated_runners_bin_is_listening(self):
        self.assertFalse(runners._runner_runs(self.d, "Listener", proc=self.proc))
        self.ps(14, os.path.join(self.d, "bin.2.338.2", "Runner.Listener"), "run", "--startuptype", "service")
        self.assertTrue(runners._runner_runs(self.d, "Listener", proc=self.proc))

    def test_a_listener_from_bin_is_listening(self):
        self.ps(15, os.path.join(self.d, "bin", "Runner.Listener"), "run")
        self.assertTrue(runners._runner_runs(self.d, "Listener", proc=self.proc))

    def test_a_slots_runner_is_not_the_folder_above_it(self):
        # A runner registered in RUNNER_DIR itself, from before a node held
        # several, is not the one in RUNNER_DIR/<slot> beneath it.
        self.ps(16, os.path.join(self.d, "slot", "bin", "Runner.Listener"), "run")
        self.ps(17, os.path.join(self.d, "slot", "bin.2.338.2", "Runner.Worker"), "spawnclient")
        self.assertFalse(runners._runner_runs(self.d, "Listener", proc=self.proc))
        self.assertFalse(runners.runner_busy(self.d, proc=self.proc))
        self.assertTrue(runners._runner_runs(os.path.join(self.d, "slot"), "Listener", proc=self.proc))


if __name__ == "__main__":
    unittest.main()
