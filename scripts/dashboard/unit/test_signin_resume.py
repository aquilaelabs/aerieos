"""A sign-in still going on a node is its account's flow again after the
controller restarts: the flow is a job there, which a restart
does not end, and the page reads it from the job's log; kept in memory
alone, a person half-way through had a job running and a page saying none."""
import os
import sys
import unittest

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))
import signin  # noqa: E402


class FakeNodes:
    def __init__(self, going, jobs):
        self.going, self.jobs, self.typed = going, jobs, []

    def jobs_going(self, who):
        return self.going if who == "user:signin" else []

    def node(self, nid):
        return {"id": nid, "name": "box"}

    def job(self, jid):
        return self.jobs.get(jid)

    def job_input(self, jid, text):
        self.typed.append((jid, text))
        return {"ok": True}


class Resume(unittest.TestCase):
    def setUp(self):
        self.was = signin.nodes
        signin._flows.clear()
        self.addCleanup(lambda: (setattr(signin, "nodes", self.was), signin._flows.clear()))

    def test_a_running_sign_in_is_found_again_with_its_link(self):
        signin.nodes = FakeNodes(
            [{"id": "j_1", "node": "n_1", "spec": {"uid": "u_ann", "agent": "claude"}},
             {"id": "j_2", "node": "", "spec": {"uid": "u_bob"}},       # no node yet: nothing to read
             {"id": "j_3", "node": "n_1", "spec": {}}],                 # nobody's
            {"j_1": {"state": "running", "log": "[aerieos] open this link to sign in: https://claude.ai/oauth/authorize?code=true&client_id=abc\n"}})
        self.assertEqual(signin.resume(), 1)
        st = signin.state("u_ann")
        self.assertTrue(st["running"] and st["url"].startswith("https://claude.ai/oauth/authorize"), st)
        self.assertEqual((st["node"], st["on"], st["job"]), ("n_1", "box", "j_1"))
        self.assertEqual(signin.submit("the-code", "u_ann"), {"ok": True})
        self.assertEqual(signin.nodes.typed, [("j_1", "the-code")])
        self.assertFalse(signin.state("u_bob")["running"])

    def test_nothing_without_nodes(self):
        signin.nodes = None
        self.assertEqual(signin.resume(), 0)


if __name__ == "__main__":
    unittest.main()
