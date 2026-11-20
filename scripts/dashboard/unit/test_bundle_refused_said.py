"""A node that refused this controller's bundle is said to a person (R267
step 6). The refusal was in the node's own log and its jobs' and nowhere
else: its row said nothing, the controller saw only terminals on another
bundle, and a container's shell there waited 45 seconds for an update the
node would never take.

The node reports the refusal in its census while it stands (the digest and
its reason). The controller keeps it to its shape, puts one row a node on
the bell while the digest refused is the bundle it serves now, hands the
Nodes page the same words on the node's row, and does not wait for such a
node's terminals to take the bundle."""
import os
import shutil
import sys
import tempfile
import unittest
from unittest import mock

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, os.path.join(HERE, ".."))
import bellseen  # noqa: E402
import nodes  # noqa: E402
from statefile import write_json  # noqa: E402

NOW = "sha256:" + "ab" * 32            # the bundle this controller serves
BEFORE = "sha256:" + "cd" * 32         # one it served before
WHY = ("this bundle's files are not ones signed by a key this node trusts (scripts/aerie is changed: its bytes are not the "
       "ones the release signed), so this node keeps the bundle it has. This node takes only what is signed by the release "
       "key it pinned (2eb9add8c0659630…). At this machine's own console: sudo aerieos-agent release-key add HEX trusts "
       "that builder's key, sudo aerieos-agent unsigned on allows unsigned builds")


# What was wrong, as one phrase: what a current agent reports, and what is
# read out of an earlier one's whole refusal.
CAUSE = "scripts/aerie is changed: its bytes are not the ones the release signed"
# A whole refusal as an agent from before the phrase sent it, key and all.
PINNED = ("this bundle's files are not ones signed by a key this node trusts (the controller sent no signature with it), so this "
          "node keeps the bundle it has. This node takes only what is signed by the release key it pinned (2eb9add8c0659634…) "
          "or its spare (5999f8948f031093…). At this machine's own console: sudo aerieos-agent release-key add HEX trusts that "
          "builder's key, sudo aerieos-agent unsigned on allows unsigned builds")


def box(nid="n_1", name="box", refused=NOW, runs=BEFORE, live=True, why=WHY, **more):
    """A node as the registry hands it: its terminals up on `runs`, saying
    it refused `refused` (None for a node that says nothing of the kind)."""
    rep = {"session": {"up": True, "bundle": runs, "ctr": True}}
    if refused:
        rep["bundle_refused"] = {"digest": refused, "why": why}
    return {"id": nid, "name": name, "kind": "agent", "state": "online", "live": live, "reported": rep, "config": {}, **more}


class Kept(unittest.TestCase):
    """What the census's field is kept as."""

    def test_the_digest_and_the_words_are_kept_to_their_shape(self):
        got = nodes._census({"bundle_refused": {"digest": NOW, "why": "it is\x07 changed (key 2eb9…)\n" + "w" * 900, "x": 1}})
        self.assertEqual(got["bundle_refused"]["digest"], NOW)
        self.assertTrue(got["bundle_refused"]["why"].startswith("it is  changed (key 2eb9…) www"))
        self.assertEqual(len(got["bundle_refused"]["why"]), 600, "bounded")
        self.assertEqual(sorted(got["bundle_refused"]), ["digest", "why"])

    def test_nothing_is_kept_of_a_node_that_refuses_none_or_names_no_digest(self):
        for said in ({}, {"bundle_refused": {}}, {"bundle_refused": {"digest": "", "why": "x"}},
                     {"bundle_refused": {"digest": "sha256:short", "why": "x"}}, {"bundle_refused": "refused"},
                     {"bundle_refused": {"digest": NOW + "0", "why": "x"}}):
            self.assertNotIn("bundle_refused", nodes._census(said), said)


class Said(unittest.TestCase):
    def setUp(self):
        p = mock.patch.object(nodes, "bundle_digest", lambda: NOW)
        p.start()
        self.addCleanup(p.stop)

    def rows(self, *listed):
        with mock.patch.object(nodes, "node_list", return_value=list(listed)):
            return nodes.bundle_attention()

    def test_the_bell_has_a_row_for_a_node_that_refused_the_bundle_served_now(self):
        row, = self.rows(box())
        self.assertEqual((row["kind"], row["node"], row["id"]), ("bundle-refused", "box", "n_1"))
        # One phrase: what was wrong, with the file the node named. An agent
        # that sent its whole refusal (this WHY) is read down to that phrase,
        # and one that sends the phrase alone is said as it is.
        self.assertEqual(row["why"], CAUSE)
        self.assertEqual(self.rows(box(why=CAUSE))[0]["why"], CAUSE)
        # Nothing of which keys the node takes, and no paragraph under the row.
        self.assertNotIn("more", row)
        for said in (row["why"], self.rows(box(why=PINNED))[0]["why"]):
            self.assertNotIn("…", said)
            self.assertNotIn("release-key", said)
        self.assertEqual(self.rows(box(why=PINNED))[0]["why"], "the controller sent no signature with it")
        self.assertEqual(self.rows(box(why="it holds scripts/x, which is a link"))[0]["why"], "it holds scripts/x, which is a link")
        self.assertLessEqual(len(self.rows(box(why="x" * 900))[0]["why"]), 200)
        self.assertEqual(row["key"], "bundle:n_1@" + "ab" * 8)

    def test_only_while_the_digest_refused_is_the_one_served(self):
        self.assertEqual(self.rows(box(refused=BEFORE)), [], "it refused a bundle this controller no longer serves")
        self.assertEqual(self.rows(box(refused=None)), [], "it reports no refusal: the row is gone by itself")
        self.assertEqual(len(self.rows(box())), 1)
        with mock.patch.object(nodes, "bundle_digest", lambda: BEFORE):
            self.assertEqual(self.rows(box()), [], "the bundle moved: the refusal was of another")

    def test_one_row_a_node_and_none_for_one_that_is_away(self):
        got = self.rows(box(), box("n_2", "tower"), box("n_3", "quiet", refused=None), box("n_4", "off", live=False),
                        {**box("n_5", "here"), "kind": "local"})
        self.assertEqual([(r["id"], r["node"]) for r in got], [("n_1", "box"), ("n_2", "tower")])
        self.assertEqual(len({r["key"] for r in got}), 2)

    def test_the_bundle_is_not_looked_at_when_no_node_reports_a_refusal(self):
        with mock.patch.object(nodes, "bundle_digest", side_effect=AssertionError("a look at every file of the bundle")):
            self.assertEqual(self.rows(box(refused=None), box("n_2", refused=None)), [])

    def test_a_node_that_gave_no_words_still_has_a_reason(self):
        row, = self.rows(box(why=""))
        self.assertEqual(row["why"], "it is not signed by a key that node trusts")

    def test_put_away_it_stays_away_until_the_bundle_moves(self):
        tmp = tempfile.mkdtemp()
        self.addCleanup(shutil.rmtree, tmp, True)
        bellseen.configure(state=tmp, write_json=write_json)
        rows = self.rows(box())
        out, hidden = bellseen.filter_rows("u1", rows)
        self.assertEqual((len(out), hidden), (1, 0))
        bellseen.dismiss("u1", [out[0]["key"]])
        self.assertEqual(bellseen.filter_rows("u1", rows), ([], 1))
        self.assertEqual(len(bellseen.filter_rows("u2", rows)[0]), 1, "one account's dismissal")
        with mock.patch.object(nodes, "bundle_digest", lambda: BEFORE):
            again = self.rows(box(refused=BEFORE))
        self.assertEqual(len(bellseen.filter_rows("u1", again)[0]), 1, "another bundle refused is said again")

    def test_the_nodes_page_row_carries_what_was_wrong(self):
        nodes.configure(state=tempfile.mkdtemp())
        rows = [box(), box("n_2", "tower", refused=BEFORE), box("n_3", "quiet", refused=None)]
        with mock.patch.object(nodes, "turns_of", lambda n: []), mock.patch.object(nodes, "spark_of", lambda nid: []):
            got = nodes.tab_view(rows, False)["nodes"]
        self.assertEqual(got[0]["bundle_held"], CAUSE)
        self.assertNotIn("bundle_held", got[1])
        self.assertNotIn("bundle_held", got[2])


class NotWaitedFor(unittest.TestCase):
    """A container's shell waits for a node's terminals to take this
    controller's bundle, and not for a node that refused it."""

    def setUp(self):
        p = mock.patch.object(nodes, "bundle_digest", lambda: NOW)
        p.start()
        self.addCleanup(p.stop)
        self.asked, self.naps = [], []

    def wait(self, *seen, limit=0.2):
        """session_bundle_wait over the node as it reads at each look."""
        looks = list(seen)
        with mock.patch.object(nodes, "node", lambda nid: looks.pop(0) if len(looks) > 1 else looks[0]):
            return nodes.session_bundle_wait("n_1", self.asked.append, limit=limit, nap=lambda s: self.naps.append(s))

    def test_terminals_on_another_bundle_are_due_and_waited_for(self):
        behind = box(refused=None)
        self.assertTrue(nodes.session_bundle_due(behind))
        got = self.wait(behind, behind, box(refused=None, runs=NOW))
        self.assertEqual(got["reported"]["session"]["bundle"], NOW, "it took the bundle within the wait")
        self.assertEqual((self.asked, len(self.naps)), (["n_1"], 2), "asked to check in once, looked again twice")
        self.assertFalse(nodes.session_bundle_due(got))

    def test_a_node_that_never_takes_it_is_waited_for_no_longer_than_the_limit(self):
        behind = box(refused=None)
        got = self.wait(behind, limit=0.05)
        self.assertTrue(nodes.session_bundle_due(got), "still due: the caller says it did not take the update")
        self.assertEqual(self.asked, ["n_1"])

    def test_a_node_that_refused_this_bundle_is_not_waited_for(self):
        self.assertFalse(nodes.session_bundle_due(box()))
        got = self.wait(box())
        self.assertEqual((self.asked, self.naps), ([], []), "neither asked nor waited for: it goes on with the bundle it has")
        self.assertTrue(got["reported"]["session"]["up"])

    def test_the_wait_ends_the_moment_the_node_reports_the_refusal(self):
        behind = box(refused=None)
        got = self.wait(behind, behind, box(), limit=30)
        self.assertEqual(len(self.naps), 2)
        self.assertEqual(got["reported"]["bundle_refused"]["digest"], NOW)

    def test_a_refusal_of_another_bundle_does_not_end_the_wait(self):
        other = box(refused=BEFORE, runs="sha256:" + "ef" * 32)
        self.assertTrue(nodes.session_bundle_due(other), "it refused one before: this one it may yet take")

    def test_what_is_not_due_a_wait(self):
        for n in (None, box(refused=None, runs=NOW), box(refused=None, live=False), {**box(refused=None), "state": "retired"},
                  {**box(refused=None), "config": {"host_only": True}}, {**box(refused=None), "reported": {}},
                  {**box(refused=None), "reported": {"session": {"up": False, "bundle": BEFORE}}}):
            self.assertFalse(nodes.session_bundle_due(n), n)
        with mock.patch.object(nodes, "bundle_digest", lambda: ""):
            self.assertFalse(nodes.session_bundle_due(box(refused=None)), "a controller that names no bundle")


if __name__ == "__main__":
    unittest.main()
