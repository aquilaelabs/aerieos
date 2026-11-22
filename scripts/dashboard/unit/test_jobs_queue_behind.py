"""A second system job pressed while one runs on a node is queued, not
refused, and handed over once the first has ended; a light one (a quick
root command) neither waits nor is waited for. A toolchain or image job
waits the same way through the gate toolchains.py hands in (store_gate)."""
import os
import sys
import unittest

sys.path.insert(0, os.path.dirname(__file__))
sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))
import nodes  # noqa: E402
from test_update_gate import Gate  # noqa: E402


class SystemQueue(Gate):
    def test_a_second_system_job_waits_for_the_first(self):
        self.job("s1", "system", state="running", spec='{"apply": "storage"}')
        self.job("s2", "system", spec='{"apply": "network"}')
        self.assertIsNone(nodes.job_next(self.n, 0))
        nodes._exec("UPDATE jobs SET state = 'succeeded' WHERE id = 's1'")
        self.assertEqual(nodes.job_next(self.n, 0)["id"], "s2")

    def test_a_light_one_passes(self):
        self.job("s1", "system", state="running", spec='{"apply": "storage"}')
        self.job("r1", "system", spec='{"apply": "root", "light": true}')
        self.assertEqual(nodes.job_next(self.n, 0)["id"], "r1")

    def test_the_store_gate_holds_a_toolchain_job(self):
        self.job("t1", "toolchain", spec='{"action": "install", "names": ["jdk"]}')
        saved = nodes.store_gate
        self.addCleanup(setattr, nodes, "store_gate", saved)
        nodes.store_gate = lambda j, nid: True
        self.assertIsNone(nodes.job_next(self.n, 0))
        nodes.store_gate = lambda j, nid: False
        self.assertEqual(nodes.job_next(self.n, 0)["id"], "t1")


class SigninPasses(Gate):
    def test_a_sign_in_is_handed_out_past_a_full_slot_and_holds_none(self):
        nodes._exec("UPDATE nodes SET concurrency = 1 WHERE id = ?", (self.n,))
        self.job("b1", "build", state="running")
        self.job("l1", "claude-login", spec='{"uid": "u_1", "timeout": 900}')
        self.job("b2", "build")
        self.assertEqual(nodes.job_next(self.n, 0)["id"], "l1", "a person's sign-in does not wait for a build")
        nodes._exec("UPDATE jobs SET state = 'succeeded' WHERE id = 'b1'")
        self.assertEqual(nodes.job_next(self.n, 0)["id"], "b2", "...and a build does not wait for a sign-in left open")


class SessionGone(Gate):
    def test_a_kill_is_gone_once_a_heartbeat_after_it_was_taken_lacks_it(self):
        name = "u_1~claude-web"
        nodes._exec("UPDATE nodes SET reported = ? WHERE id = ?", ('{"sessions": [{"name": "%s"}]}' % name, self.n))
        nodes._kill_taken.pop((self.n, name), None)
        self.assertFalse(nodes.session_gone(self.n, name), "not before the agent has taken the kill")
        nodes._kill_taken[(self.n, name)] = 100.0
        nodes._sessions_at[self.n] = 50.0
        nodes._exec("UPDATE nodes SET reported = ? WHERE id = ?", ('{"sessions": []}', self.n))
        self.assertFalse(nodes.session_gone(self.n, name), "nor on a heartbeat from before it")
        nodes._sessions_at[self.n] = 150.0
        self.assertTrue(nodes.session_gone(self.n, name), "...and gone on one after it that lacks it")
        nodes._exec("UPDATE nodes SET reported = ? WHERE id = ?", ('{"sessions": [{"name": "%s"}]}' % name, self.n))
        self.assertFalse(nodes.session_gone(self.n, name), "still listed after it, still there")


if __name__ == "__main__":
    unittest.main()
