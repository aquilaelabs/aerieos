"""A job's secret_env: the node is handed it and merges it into the
job's environment as it does `env` (a job run by the root agent taking no
PATH or loader variable from it); every reader of the job is handed the
job without it; and its row keeps it no longer than the job runs."""
import json
import os
import sys
import tempfile
import unittest

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, os.path.join(HERE, ".."))
sys.path.insert(0, HERE)
import agentpkg  # noqa: E402
import nodes  # noqa: E402

SPEC = {"argv": ["sh", "-c", "deploy"], "env": {"IMAGE": "ghcr.io/ada/shop"},
        "secret_env": {"KUBE_TOKEN": "tok-123", "REGISTRY_PASSWORD": "pw-456", "PATH": "/evil"}, "timeout": 60}


class AgentSide(unittest.TestCase):
    def test_merged_as_env_is(self):
        spec_env = agentpkg.load("secretenv").module("jobs").spec_env
        self.assertEqual(spec_env(SPEC), {"IMAGE": "ghcr.io/ada/shop", "KUBE_TOKEN": "tok-123",
                                          "REGISTRY_PASSWORD": "pw-456", "PATH": "/evil"})
        self.assertNotIn("PATH", spec_env(SPEC, by_root=True), "the root agent takes no PATH from a job")
        self.assertEqual(spec_env({"secret_env": "not a map"}), {})


class ControllerSide(unittest.TestCase):
    def setUp(self):
        nodes.configure(state=tempfile.mkdtemp())
        mint = nodes.enroll_mint("user:test", "box")
        nodes.enroll(nodes.authenticate(mint["token"]), {"cpu": 2, "mem_mb": 4096, "arch": "x86_64",
                                                         "system": "linux", "session": {"up": True, "user": "b"}},
                     "10.0.0.5", user="bb")
        self.nid = mint["id"]

    def stored(self, jid):
        return json.loads(nodes._rows("SELECT spec FROM jobs WHERE id = ?", (jid,))[0]["spec"])

    def test_read_without_it_and_kept_only_while_it_runs(self):
        jid = nodes.job_add("user:test", {"node": self.nid}, "exec", dict(SPEC))["job"]
        self.assertNotIn("secret_env", nodes.job_read({"spec": self.stored(jid)})["spec"], "no reader is handed it")
        got = nodes.job_next(self.nid, 0)
        self.assertEqual(got["spec"]["secret_env"]["KUBE_TOKEN"], "tok-123", "the node is handed it")
        self.assertIn("secret_env", self.stored(jid), "kept while it runs")
        nodes.job_result(self.nid, jid, "succeeded", 0)
        self.assertNotIn("secret_env", self.stored(jid), "gone once it ends")
        self.assertEqual(self.stored(jid)["env"], SPEC["env"], "the rest of the spec stays")

    def test_a_job_canceled_before_it_ran_keeps_none(self):
        jid = nodes.job_add("user:test", {"node": self.nid}, "exec", dict(SPEC))["job"]
        nodes.job_cancel("user:test", jid)
        self.assertNotIn("secret_env", self.stored(jid))

    def test_the_sweep_takes_it_off_a_row_ended_any_other_way(self):
        jid = nodes.job_add("user:test", {"node": self.nid}, "exec", dict(SPEC))["job"]
        nodes._exec("UPDATE jobs SET state = 'failed', ended = 1 WHERE id = ?", (jid,))
        self.assertEqual(nodes.forget_secrets(), 1)
        self.assertNotIn("secret_env", self.stored(jid))
        self.assertEqual(nodes.forget_secrets(), 0)


if __name__ == "__main__":
    unittest.main()
