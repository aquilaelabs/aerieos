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


if __name__ == "__main__":
    unittest.main()
