"""A job that is waited for is waited for in one place (nodes._await_job):
its row once it has ended, heard at the wake its end makes, or None when
the time is up. The four that wait on one (a command, a line into a
session, a root command, a node's Test) each keep their own answer, their
own cancel and their own words for a job that never answered."""
import os
import sys
import threading
import time
import unittest
from unittest import mock

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, os.path.join(HERE, ".."))
import nodes  # noqa: E402

NODE = {"id": "n1", "name": "box", "kind": "agent", "state": "online", "live": True, "config": {}, "reported": {"sandbox": True}}


def ended(state="succeeded", code=0, log=""):
    return {"id": "j1", "state": state, "exit_code": code, "log": log}


class TheWait(unittest.TestCase):
    def test_an_ended_job_is_its_row_at_the_first_look(self):
        with mock.patch.object(nodes, "job", return_value=ended()) as look:
            self.assertEqual(nodes._await_job("j1", 30), ended())
        self.assertEqual(look.call_count, 1)

    def test_an_end_is_heard_at_its_wake_and_not_at_the_next_look(self):
        rows = [{"id": "j1", "state": "running"}]

        def end():
            rows[0] = ended("failed", 2)
            nodes._notify()
        t = threading.Timer(0.1, end)
        t.start()
        at = time.time()
        # A look a minute apart: only the wake can be what answers in time.
        with mock.patch.object(nodes, "job", side_effect=lambda jid: rows[0]), mock.patch.object(nodes, "WAIT_LOOK_S", 60.0):
            j = nodes._await_job("j1", 30)
        t.join()
        self.assertEqual(j["state"], "failed")
        self.assertLess(time.time() - at, 20)

    def test_a_job_that_never_ends_is_none_once_the_time_and_its_grace_are_up(self):
        at = time.time()
        with mock.patch.object(nodes, "job", return_value={"id": "j1", "state": "running"}) as look, \
             mock.patch.object(nodes, "WAIT_LOOK_S", 0.02):
            self.assertIsNone(nodes._await_job("j1", 0.05, grace=0.05))
        self.assertGreaterEqual(time.time() - at, 0.1)
        self.assertGreater(look.call_count, 1)
        # A row that is gone is waited for the same way, never read.
        with mock.patch.object(nodes, "job", return_value=None):
            self.assertIsNone(nodes._await_job("j1", 0, grace=0.02))


class TheFour(unittest.TestCase):
    def setUp(self):
        self.calls = []

        def rec(name, answer=None):
            def f(*a, **k):
                self.calls.append((name, a, k))
                return answer
            return f
        self.fakes = dict(node=lambda node_id: dict(NODE), job_add=rec("add", {"ok": True, "job": "j1"}),
                          job_cancel=rec("cancel"), job_forget=rec("forget"), audit=rec("audit"),
                          _no_answer=rec("no_answer", "box did not pick the job up"))

    def run_it(self, row, fn, *args, **kwargs):
        """One of the four, its job ending as `row` (None: never)."""
        self.calls.clear()
        waits = []

        def wait(job_id, timeout, grace=10):
            waits.append((job_id, timeout, grace))
            return row
        with mock.patch.multiple(nodes, _await_job=wait, **self.fakes):
            r = getattr(nodes, fn)(*args, **kwargs)
        self.waits = waits
        return r

    def named(self, name):
        return [(a, k) for n, a, k in self.calls if n == name]

    def test_a_command_answers_its_code_and_output_and_takes_back_one_never_answered(self):
        r = self.run_it(ended(log="exec\nLinux 6\n"), "run_wait", "user:t", "n1", ["uname"], timeout=5)
        self.assertEqual(r, {"code": 0, "out": "Linux 6\n", "job": "j1", "state": "succeeded"})
        self.assertEqual(self.waits, [("j1", 5, 10)])
        self.assertEqual(self.named("forget") + self.named("cancel"), [])
        self.assertEqual(self.run_it(ended("failed", None), "run_wait", "user:t", "n1", ["x"])["code"], 1)
        self.run_it(ended(), "run_wait", "user:t", "n1", ["docker", "ps"], forget=True)
        self.assertEqual(self.named("forget"), [(("j1",), {})])
        r = self.run_it(None, "run_wait", "user:t", "n1", ["uname"], timeout=5)
        self.assertEqual(r, {"error": "box did not pick the job up"})
        self.assertEqual(self.named("no_answer"), [(("j1", "n1", 5), {})])
        self.assertEqual(self.named("cancel"), [(("user:t", "j1"), {})])

    def test_a_line_answers_sent_or_typed_and_is_canceled_as_the_dashboard(self):
        self.assertEqual(self.run_it(ended(), "tell_wait", "n1", "s1", "hi"), {"ok": True, "sent": True, "text": "hi", "job": "j1"})
        self.assertEqual(self.waits, [("j1", 20, 10)])
        self.assertEqual(self.run_it(ended("failed", 3), "tell_wait", "n1", "s1", "hi"),
                         {"ok": True, "sent": False, "typed": True, "text": "hi", "job": "j1"})
        self.assertEqual(self.run_it(ended("failed", 1, "tell\nno such session\n\n"), "tell_wait", "n1", "s1", "hi"),
                         {"error": "no such session"})
        self.assertEqual(self.run_it(ended("failed", 1), "tell_wait", "n1", "s1", "hi"), {"error": "the send failed on box (exit 1)"})
        r = self.run_it(None, "tell_wait", "n1", "s1", "hi", timeout=3, who="user:ann")
        self.assertEqual(r, {"error": "the agent on box took the send but did not report back within 3s"})
        self.assertEqual(self.named("add")[0][0][0], "user:ann")
        self.assertEqual(self.named("cancel"), [(("dashboard", "j1"), {})])

    def test_a_root_command_answers_its_whole_log_and_is_canceled_as_who_asked(self):
        r = self.run_it(ended(log="exec\nroot\n"), "root_wait", "user:t", "n1", ["id", "-un"], why="a test", timeout=7)
        self.assertEqual(r, {"code": 0, "out": "exec\nroot\n", "job": "j1", "state": "succeeded"})
        self.assertEqual(self.waits, [("j1", 7, 10)])
        self.assertEqual(self.named("audit"), [(("user:t", "root-run", "n1", {"argv": ["id", "-un"], "why": "a test", "job": "j1"}), {})])
        r = self.run_it(None, "root_wait", "user:t", "n1", ["true"], timeout=7)
        self.assertEqual(r, {"error": "box did not pick the job up"})
        self.assertEqual(self.named("no_answer"), [(("j1", "n1", 7), {})])
        self.assertEqual(self.named("cancel"), [(("user:t", "j1"), {})])

    def test_a_nodes_test_waits_fifteen_seconds_in_all_and_cancels_nothing(self):
        with mock.patch.object(nodes.db, "audit") as audit:
            r = self.run_it(ended(log="exec\nLinux 6 x86_64\n"), "agent_test", "user:t", dict(NODE))
            self.assertEqual(r, {"on": True, "why": "exec\nLinux 6 x86_64",
                                 "trust": {"ok": True, "said": "takes whatever this controller sends: no key is pinned there"}})
            self.assertEqual(self.waits, [("j1", 15, 0)])
            audit.assert_called_once_with("user:t", "node-test", "n1", {"on": True})
            self.assertEqual(self.run_it(ended("failed", 127), "agent_test", "user:t", dict(NODE)), {"on": False, "why": "failed (exit 127)"})
            audit.reset_mock()
            r = self.run_it(None, "agent_test", "user:t", dict(NODE))
            self.assertEqual(r, {"on": False, "why": "the agent took the job but did not report back within 15s"})
            audit.assert_not_called()
        self.assertEqual(self.named("cancel"), [])


if __name__ == "__main__":
    unittest.main()
