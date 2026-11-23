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


class World(unittest.TestCase):
    """One enrolled node and what this controller ships."""

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

    def pins(self, unsigned_ok=False):
        nodes._exec("UPDATE nodes SET reported = json_set(reported, '$.release_key', ?, '$.unsigned_ok', json(?)) WHERE id = ?",
                    ("2eb9add8c0659630", "true" if unsigned_ok else "false", self.nid))


class AutoUpdate(World):
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
            # Nor on a person's press (B1108): the job could only fail
            # there, and what keeps it is said where the press was, and in
            # every line that says the node is behind.
            said = nodes.node_update_agent("user:test", self.nid)
            self.assertFalse(said.get("job"))
            self.assertEqual(said.get("error"), "box refuses this controller's agent: the build is unsigned")
            self.assertEqual(nodes.agent_stale(nodes.node(self.nid)),
                             f"box runs agent {self.ours['version']} and refuses this controller's build of "
                             f"{self.ours['version']}: the build is unsigned")
            self.assertNotIn("Update agent", nodes.agent_stale(nodes.node(self.nid)))
            with mock.patch.object(nodes, "turns_of", lambda n: []):
                row = nodes.tab_view([nodes.node(self.nid)], True)["nodes"][0]
            self.assertEqual(row.get("update_held"), "the build is unsigned")
            self.assertEqual(self.queued(), [])

    def test_a_session_s_job_on_a_node_that_refuses_the_build_does_not_wait_for_it(self):
        # bb waits up to 150 s for an update the controller sends by itself
        # where agent_behind is true (bbapi._agent_wait): none comes here.
        self.runs(self.ours["version"])
        self.pins()
        with mock.patch.object(nodes, "agent_sig", lambda digest=None: ""):
            got = nodes.job_add("user:test", {"node": self.nid}, "exec", {"cmd": ["true"]})
        self.assertFalse(got.get("agent_behind"), got)
        self.assertIn("refuses this controller's build", got.get("error", ""))
        with mock.patch.object(nodes, "agent_sig", lambda digest=None: "ab" * 64):
            got = nodes.job_add("user:test", {"node": self.nid}, "exec", {"cmd": ["true"]})
        self.assertTrue(got.get("agent_behind"), "a build it takes is worth the wait")

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


class AgentDir(unittest.TestCase):
    def test_the_agent_shipped_is_another_folder_only_in_the_source_tree(self):
        # Every node runs what this controller ships as root: a folder an
        # install's environment names is never it.
        import importlib
        import seams
        tree = os.path.normpath(os.path.join(HERE, "..", "..", "agent"))
        try:
            with mock.patch.dict(os.environ, {"BB_AGENT_DIR": "/tmp/planted-agent"}):
                with mock.patch.object(seams, "IN_TREE", False):
                    importlib.reload(nodes)
                    self.assertEqual(os.path.normpath(str(nodes.AGENT_DIR)), tree)
                with mock.patch.object(seams, "IN_TREE", True):
                    importlib.reload(nodes)
                    self.assertEqual(str(nodes.AGENT_DIR), "/tmp/planted-agent", "a test world's own copy, in the tree")
        finally:
            importlib.reload(nodes)


class Newer(World):
    """A controller gone back to an older image (a backup restored under
    one), its nodes still on the signed agents the newer one sent them: a
    node that pinned a release key refuses an older agent, so one sent was
    a failed job, and the node was held for good, its spaces waiting."""

    def ahead(self, window=False):
        major, minor, build = (int(x) for x in self.ours["version"].split("."))
        return f"{major}.{minor + 1}.0" if window else f"{major}.{minor}.{build + 3}"

    def row(self):
        with mock.patch.object(nodes, "node_list", lambda: [{**nodes.node(self.nid), "live": True}]):
            return next((r for r in nodes.attention({}) if r.get("id") == self.nid), None)

    def test_a_newer_build_in_the_window_is_current(self):
        self.runs(self.ahead())
        self.pins()
        n = nodes.node(self.nid)
        self.assertEqual(nodes.agent_newer(n), "build")
        self.assertEqual(nodes.agent_stale(n), "", "nothing is removed inside a window: it works with this controller")
        self.assertIsNone(nodes.auto_update(self.nid))
        self.assertEqual(self.queued(), [], "the older build is not sent to be refused")
        self.assertIsNone(self.row(), "and the bell says nothing of it")
        r = nodes.job_add("user:test", {"node": self.nid}, "toolchain", {"action": "install", "names": ["go"]})
        self.assertTrue(r.get("ok"), r)

    def test_its_refusal_of_the_older_bundle_is_no_bell_row(self):
        # Gone back, a node on a newer agent refuses the older bundle and
        # keeps the newer one it has: no news. Refused for anything else, or
        # by a node that is not ahead, the row stands.
        self.runs(self.ahead())
        serving = "sha256:" + "a" * 64
        # As an agent reports it: the refusal's cause alone (its release.BUNDLE_OLDER).
        said = f"its files are {nodes.AGENT_OLDER}"
        rec = nodes.node(self.nid)
        rec.setdefault("reported", {})["bundle_refused"] = {"digest": serving, "why": said}
        with mock.patch.object(nodes, "node_list", lambda: [{**rec, "live": True}]), \
                mock.patch.object(nodes, "bundle_digest", lambda: serving), mock.patch.object(nodes, "node", lambda nid: rec):
            self.assertEqual(nodes.bundle_attention(), [])
            rec["reported"]["bundle_refused"]["why"] = "it is not signed by a key this node trusts"
            self.assertEqual([r["kind"] for r in nodes.bundle_attention()], ["bundle-refused"])
            rec["reported"]["bundle_refused"]["why"] = said
            rec["agent"] = {**(rec.get("agent") or {}), "version": self.ours["version"]}
            self.assertEqual([r["kind"] for r in nodes.bundle_attention()], ["bundle-refused"], "a node not ahead still says it")

    def test_one_from_a_newer_window_is_held_and_said_as_newer(self):
        self.runs(self.ahead(window=True))
        n = nodes.node(self.nid)
        self.assertEqual(nodes.agent_newer(n), "window")
        why = nodes.agent_stale(n)
        self.assertIn("newer than this controller works with", why)
        self.assertNotIn("too old", why)
        self.assertIsNone(nodes.auto_update(self.nid))
        row = self.row()
        self.assertTrue(row["window"] and row["newer"], row)

    def test_an_older_window_and_build_are_behind_as_ever(self):
        major, minor, build = (int(x) for x in self.ours["version"].split("."))
        for v, gap in ((f"{major}.{minor}.{max(0, build - 1)}", False), (f"{major}.{max(0, minor - 1)}.{build + 50}", True)):
            self.runs(v)
            n = nodes.node(self.nid)
            self.assertEqual(nodes.agent_newer(n), "", v)
            self.assertTrue(nodes.agent_stale(n), v)
            self.assertEqual(nodes.agent_gap(n), gap, v)
        self.runs("harness")
        self.assertEqual(nodes.agent_newer(nodes.node(self.nid)), "", "a version with no window is neither")

    def test_a_refusal_for_its_age_says_so_on_the_bell(self):
        self.runs(self.ours["version"])
        self.pins()
        with mock.patch.object(nodes, "agent_sig", lambda digest=None: "ab" * 64):
            self.assertTrue(nodes.auto_update(self.nid))
            nodes.job_result(self.nid, self.queued()[0]["id"], "failed", 77, nodes.AGENT_OLDER)
            row = self.row()
        self.assertTrue(row["older"], row)
        self.assertFalse(row["auto"])

    def test_the_age_phrase_is_the_agents(self):
        import agentpkg  # noqa: PLC0415
        self.assertEqual(nodes.AGENT_OLDER, agentpkg.load("auto_update_older").module("release").OLDER)


if __name__ == "__main__":
    unittest.main()
