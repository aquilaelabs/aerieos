"""A node whose own console switched root commands off (R227 step 2) is not
asked for one: the controller says the node's sentence before a person is
asked to allow a command, before an administrator's own is queued, and
names it in what the node reports."""
import os
import sys
import tempfile
import unittest

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))
import nodes  # noqa: E402

CENSUS = {"cpu": 2, "mem_mb": 4096, "arch": "x86_64", "system": "linux", "sandbox": True}


class RootOff(unittest.TestCase):
    def setUp(self):
        nodes.configure(state=tempfile.mkdtemp())
        mint = nodes.enroll_mint("user:test", "box")
        nodes.enroll(nodes.authenticate(mint["token"]), CENSUS, "10.0.0.5", user="bb")
        self.nid = mint["id"]

    def test_the_census_carries_it_and_only_true_is_true(self):
        self.assertIs(nodes._census({**CENSUS, "root_off": True})["root_off"], True)
        for said in (None, "yes", 1, False):
            self.assertIs(nodes._census({**CENSUS, "root_off": said})["root_off"], False, said)

    def test_a_node_switched_off_is_refused_in_its_own_words(self):
        n = nodes.node(self.nid)
        self.assertEqual(nodes.root_off(n), "")
        self.assertEqual(nodes.root_refused(n), "")
        nodes.hello(self.nid, {**CENSUS, "root_off": True}, "10.0.0.5")
        n = nodes.node(self.nid)
        self.assertIn("switched off at its own console", nodes.root_off(n))
        self.assertIn("sudo aerieos-agent root-asks on", nodes.root_off(n))
        self.assertEqual(nodes.root_refused(n), nodes.root_off(n), "a session's ask is refused with the same sentence")
        r = nodes.root_wait("user:ann", self.nid, ["true"], why="a test")
        self.assertEqual(r, {"error": nodes.root_off(n)}, "an administrator's own is not queued either")
        nodes.hello(self.nid, CENSUS, "10.0.0.5")
        self.assertEqual(nodes.root_off(nodes.node(self.nid)), "", "switched back on there, it is taken off here")


if __name__ == "__main__":
    unittest.main()
