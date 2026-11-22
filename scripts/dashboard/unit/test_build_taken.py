"""Test on a node says whether the node takes what this controller ships.

Its round trip proves the channel. Whether the node would take this
controller's next agent and its bundle is another question, and the one a
person asks after pinning a key or adding a builder's at a console: answered
from what the node reports of its trust and the key this build is signed
under, in one phrase with no key in it.
"""
import os
import sys
import unittest
from unittest import mock

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))
import nodes  # noqa: E402

REL, SPARE, MINE, OTHER = "2e" * 32, "59" * 32, "ab" * 32, "cd" * 32


def box(**rep):
    return {"id": "n_1", "name": "box", "kind": "agent", "reported": rep}


class Taken(unittest.TestCase):
    def said(self, signed_by, **rep):
        with mock.patch.object(nodes, "agent_sig_key", lambda: signed_by):
            return nodes.build_taken(box(**rep))

    def test_a_node_with_no_key_takes_whatever_comes(self):
        self.assertEqual(self.said(""), (True, "takes whatever this controller sends: no key is pinned there"))
        self.assertEqual(self.said(MINE)[0], True)

    def test_a_build_signed_by_a_key_the_node_trusts_is_taken_and_said_as_which(self):
        pinned = {"release_key": REL[:16], "release_spare": SPARE[:16], "release_also": [MINE[:16]], "unsigned_ok": False}
        self.assertEqual(self.said(REL, **pinned), (True, "takes this controller's builds, signed by the release key"))
        self.assertEqual(self.said(SPARE, **pinned), (True, "takes this controller's builds, signed by the release key's spare"))
        self.assertEqual(self.said(MINE, **pinned), (True, "takes this controller's builds, signed by a key added at its console"))

    def test_one_it_does_not_trust_is_refused_unless_its_console_allows_unsigned_builds(self):
        pinned = {"release_key": REL[:16], "release_spare": SPARE[:16], "release_also": []}
        self.assertEqual(self.said(OTHER, **pinned), (False, "will not take this controller's builds: they are signed by a key it does not trust"))
        self.assertEqual(self.said("", **pinned), (False, "will not take this controller's builds: they are unsigned"))
        self.assertEqual(self.said("", unsigned_ok=True, **pinned),
                         (True, "takes this controller's builds unchecked: its console allows unsigned builds"))
        # A key added at the console and no release key pinned is trust too.
        self.assertEqual(self.said("", release_also=[MINE[:16]])[0], False)

    def test_nothing_it_says_carries_a_key(self):
        for by in ("", REL, MINE, OTHER):
            for rep in ({}, {"release_key": REL[:16]}, {"release_key": REL[:16], "release_also": [MINE[:16]], "unsigned_ok": True}):
                words = self.said(by, **rep)[1]
                self.assertNotRegex(words, r"[0-9a-f]{8}")
                self.assertLess(len(words), 100)

    def test_the_key_a_build_is_signed_under_is_read_only_beside_a_signature_for_this_agent(self):
        with mock.patch.object(nodes, "agent_sig", lambda digest=None: ""):
            self.assertEqual(nodes.agent_sig_key(), "")


if __name__ == "__main__":
    unittest.main()
