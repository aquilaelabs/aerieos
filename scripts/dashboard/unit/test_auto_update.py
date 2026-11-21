"""A node's agent behind this controller inside its window is updated by the
controller itself once the node is idle (R253); one with a job in flight is
left until it is idle, one from another window is the operator's press, an
attempt is not repeated within AUTO_UPDATE_EVERY, and a node that will
refuse the build for want of a release's signature is not sent it unasked."""
import os
import sys
import tempfile
import unittest
from unittest import mock

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, os.path.join(HERE, ".."))
import nodes  # noqa: E402


class AutoUpdate(unittest.TestCase):
    def setUp(self):
        nodes.configure(state=tempfile.mkdtemp())
        nodes._auto_tried.clear()
        mint = nodes.enroll_mint("user:test", "box")
        nodes.enroll(nodes.authenticate(mint["token"]), {"cpu": 2, "mem_mb": 4096, "arch": "x86_64",
                                                         "system": "linux", "session": {"up": True, "user": "b"}},
                     "box.lan", user="bb")
        self.nid = mint["id"]
        self.ours = nodes.agent_file()

    def runs(self, version):
        nodes._exec("UPDATE nodes SET agent = json_set(agent, '$.digest', ?, '$.version', ?) WHERE id = ?",
                    ("sha256:" + "0" * 64, version, self.nid))

    def queued(self):
        return [j for j in nodes.jobs_for(node_id=self.nid, n=10, active=True) if j.get("type") == "self-update"]

    def test_an_idle_node_behind_inside_the_window_is_updated(self):
        self.runs(self.ours["version"])
        self.assertTrue(nodes.agent_stale(nodes.node(self.nid)), "the same number, another file: behind")
        self.assertTrue(nodes.auto_update(self.nid))
        self.assertEqual(len(self.queued()), 1)
        self.assertIsNone(nodes.auto_update(self.nid), "not asked again while one is queued, nor within the wait")

    def test_a_busy_node_waits_and_another_window_is_the_operators(self):
        self.runs(self.ours["version"])
        with mock.patch.object(nodes, "agent_stale", lambda n: "behind"), \
             mock.patch.object(nodes, "jobs_for", lambda **k: [{"id": "j_busy"}]):
            self.assertIsNone(nodes.auto_update(self.nid), "a job in flight: left until the node is idle")
        nodes._auto_tried.clear()
        self.runs("0.1.1")
        with mock.patch.object(nodes, "agent_stale", lambda n: "behind"):
            self.assertIsNone(nodes.auto_update(self.nid), "another window ends sessions: the operator presses it")
        self.runs("harness")
        self.assertIsNone(nodes.auto_update(self.nid), "a version with no window is no proof of the same one")
        self.assertEqual(self.queued(), [])

    def pins(self, unsigned_ok=False):
        nodes._exec("UPDATE nodes SET reported = json_set(reported, '$.release_key', ?, '$.unsigned_ok', json(?)) WHERE id = ?",
                    ("2eb9add8c0659630", "true" if unsigned_ok else "false", self.nid))

    def test_a_node_taking_only_signed_updates_is_not_sent_an_unsigned_build_by_itself(self):
        # It refuses it, and asked again it refuses it again: a failed job
        # every two minutes on a controller built from a branch.
        self.runs(self.ours["version"])
        self.pins()
        with mock.patch.object(nodes, "agent_sig", lambda digest=None: ""):
            self.assertIn("signed", nodes.unsigned_refused(nodes.node(self.nid)))
            self.assertIsNone(nodes.auto_update(self.nid))
            self.assertEqual(self.queued(), [], "nothing queued for a node that will refuse it")
            row = next(a for a in nodes.attention({}) if a.get("id") == self.nid) if nodes.node(self.nid).get("live") else None
            if row:
                self.assertFalse(row["auto"])
                self.assertIn("signed", row["held"])
            # A person's press still sends it: the node says why itself.
            self.assertTrue(nodes.node_update_agent("user:test", self.nid).get("job"))

    def test_with_a_signature_or_unsigned_builds_allowed_it_is_sent(self):
        self.runs(self.ours["version"])
        self.pins()
        with mock.patch.object(nodes, "agent_sig", lambda digest=None: "ab" * 64):
            self.assertEqual(nodes.unsigned_refused(nodes.node(self.nid)), "")
            self.assertTrue(nodes.auto_update(self.nid), "a signed build is sent to a node that pinned the key")
        nodes._auto_tried.clear()
        for j in self.queued():
            nodes.job_result(self.nid, j["id"], "failed", 75, "busy")
        self.pins(unsigned_ok=True)
        with mock.patch.object(nodes, "agent_sig", lambda digest=None: ""):
            self.assertEqual(nodes.unsigned_refused(nodes.node(self.nid)), "")
            self.assertTrue(nodes.auto_update(self.nid), "its console allows unsigned builds")

    def test_a_signature_the_node_refused_is_not_sent_again_until_the_build_moves(self):
        self.runs(self.ours["version"])
        job = nodes.auto_update(self.nid)
        self.assertTrue(job)
        nodes.job_result(self.nid, self.queued()[0]["id"], "failed", 77,
                         "refused: the signature is not the release key's. This node takes only updates signed by it")
        nodes._auto_tried.clear()
        self.assertEqual(nodes.unsigned_refused(nodes.node(self.nid)), "the signature is not the release key's",
                         "one phrase of what it said, for the row")
        self.assertIsNone(nodes.auto_update(self.nid), "the same build, the same answer: not asked again")
        self.assertEqual(self.queued(), [])
        # Another build is another question.
        other = dict(self.ours, digest="sha256:" + "1" * 64)
        with mock.patch.object(nodes, "agent_file", lambda: other):
            self.assertEqual(nodes.unsigned_refused(nodes.node(self.nid)), "")


if __name__ == "__main__":
    unittest.main()
