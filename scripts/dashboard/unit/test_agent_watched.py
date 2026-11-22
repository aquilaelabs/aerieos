"""One loop sees every job's child to its end (jobs.watched): the job's own
command, a system step, a command as root and an agent's installer each
wrote it out. What it answers: the child's exit code, whether it was killed
at its deadline, in the caller's own words, and whether the job was stopped;
and a job that cannot post, be canceled or hold a process still runs."""
import subprocess
import time
import unittest
import agentpkg  # noqa: E402
from test_agent_sh import FakeJob  # noqa: E402

agent = agentpkg.load("aerieos_agent")
jobs = agent.module("jobs")


def child(script):
    return subprocess.Popen(["sh", "-c", script], stdout=subprocess.PIPE, stderr=subprocess.STDOUT, start_new_session=True)


def said(job):
    return "".join(t for _, t in job.posts) + "".join(job.pending)


class Bare:
    """A stand-in that only hears: no flush, no cancel, no process kept."""
    __slots__ = ("heard",)

    def __init__(self):
        self.heard = []

    def say(self, text):
        self.heard.append(text)


class Watched(unittest.TestCase):
    def test_a_child_that_ends_answers_its_code_and_what_it_said(self):
        job = FakeJob()
        code, killed, stopped = jobs.watched(job, child("echo one; echo; echo two; exit 3"), 30)
        self.assertEqual((code, killed, stopped), (3, False, False))
        self.assertIn("one\n\ntwo\n", said(job))
        self.assertIsNone(job.proc)

    def test_blank_lines_are_left_out_where_the_caller_says_so(self):
        job = FakeJob()
        jobs.watched(job, child("echo one; echo; echo two"), 30, keep_blank=False)
        self.assertIn("one\ntwo\n", said(job))

    def test_one_past_its_deadline_is_killed_in_the_callers_words(self):
        job, t0 = FakeJob(), time.monotonic()
        code, killed, stopped = jobs.watched(job, child("echo began; sleep 60"), 1, late="the installer did not finish in time")
        self.assertTrue(killed)
        self.assertFalse(stopped)
        self.assertNotEqual(code, 0)
        self.assertLess(time.monotonic() - t0, 15)
        self.assertIn("the installer did not finish in time\n", said(job))

    def test_the_usual_words_say_how_long_it_had(self):
        job = FakeJob()
        jobs.watched(job, child("sleep 60"), 1.0)
        self.assertIn("timed out after 1s, killing it\n", said(job))

    def test_a_job_stopped_while_its_child_started_has_it_killed_at_once(self):
        job, t0 = FakeJob(), time.monotonic()
        job.canceled = True
        code, killed, stopped = jobs.watched(job, child("sleep 60"), 30)
        self.assertTrue(stopped)
        self.assertFalse(killed)
        self.assertLess(time.monotonic() - t0, 10)

    def test_a_job_that_can_only_hear_still_runs(self):
        job = Bare()
        code, killed, stopped = jobs.watched(job, child("echo heard"), 30)
        self.assertEqual((code, killed, stopped), (0, False, False))
        self.assertIn("heard\n", "".join(job.heard))


if __name__ == "__main__":
    unittest.main()
