"""Taking a retired node's directory off a toolchain store (R196) works on
the node (R246; the audit of 13 Nov): the controller queues a toolchain job
with action clean and the agent refused every action outside install,
remove, sysdeps and check before it reached the branch that does it."""
import os
import shutil
import tempfile
import unittest
from unittest import mock

import agentpkg  # noqa: E402

agent = agentpkg.load("aerieos_agent_store_clean")
agent.log = lambda *a, **k: None


class Job:
    def __init__(self):
        self.said = ""

    def say(self, text):
        self.said += text

    def step(self, name):
        pass


class Clean(unittest.TestCase):
    def setUp(self):
        self.base = tempfile.mkdtemp()
        self.addCleanup(shutil.rmtree, self.base, True)
        for name in ("n_dead1234", "n_mine5678", "notanode"):
            os.makedirs(os.path.join(self.base, name, "jdk"))
        self.a = object.__new__(agent.Agent)
        self.a.state = {"user": "builder", "stores": {"toolchains": self.base}}
        self.a.drop_privileges = lambda env: {}
        self.a.bundle = lambda job, who: "/bundle"
        self.a.hello = lambda *x, **k: None
        self.a.refresh_netcut_tool = lambda: None

    def clean(self, names, users=()):
        work = agent.module("work")
        job = Job()
        with mock.patch.object(work, "tc_root", lambda state: os.path.join(self.base, "n_mine5678")), \
                mock.patch.object(work, "tc_scope", lambda: "n_mine5678"), \
                mock.patch.object(work, "tc_users", lambda d: list(users)):
            return self.a.toolchain(job, {"action": "clean", "names": names}), job

    def test_a_retired_nodes_directory_goes(self):
        got, job = self.clean(["n_dead1234"])
        self.assertEqual(got, ("succeeded", 0), job.said)
        self.assertFalse(os.path.exists(os.path.join(self.base, "n_dead1234")))
        self.assertIn("taking", job.said)

    def test_never_its_own_and_never_what_is_not_a_nodes(self):
        for name in ("n_mine5678", "notanode", "n_gone0000"):
            got, job = self.clean([name])
            self.assertEqual(got, ("failed", 1), name)
            self.assertIn("is not a directory this node may take off the store", job.said)
        self.assertTrue(os.path.isdir(os.path.join(self.base, "n_mine5678")))
        self.assertTrue(os.path.isdir(os.path.join(self.base, "notanode")))

    def test_nothing_running_from_it(self):
        got, _ = self.clean(["n_dead1234"], users=[{"pid": 7, "what": "java", "project": ""}])
        self.assertEqual(got, ("failed", 1))
        self.assertTrue(os.path.isdir(os.path.join(self.base, "n_dead1234")))

    def test_an_action_nobody_knows_is_still_refused(self):
        job = Job()
        with mock.patch.object(agent.module("work"), "tc_root", lambda state: self.base):
            self.assertEqual(self.a.toolchain(job, {"action": "erase", "names": ["x"]}), ("failed", 64))


if __name__ == "__main__":
    unittest.main()
