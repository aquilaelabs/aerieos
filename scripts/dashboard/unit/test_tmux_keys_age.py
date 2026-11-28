"""Keys sent to a session on a node are typed only while they are recent.

A node that did not answer kept what was sent to its sessions (keys, a
console's line, Send to Claude) with no age and no cap, and typed it, Enter
included, into whatever session held that name when it came back, a day
later. A kill queued the same way already carried its age; these are kept
beside when each was asked now, dropped past two minutes, and at most 64
wait."""
import os
import sys
import tempfile
import unittest
from unittest import mock

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))
import nodes  # noqa: E402


class Age(unittest.TestCase):
    def setUp(self):
        nodes.configure(state=tempfile.mkdtemp())
        nodes._tmux_ops.clear()
        mint = nodes.enroll_mint("user:test", "box")
        nodes.enroll(nodes.authenticate(mint["token"]), {"cpu": 2, "mem_mb": 4096, "arch": "x86_64",
                                                         "system": "linux", "session": {"up": True, "user": "b"}},
                     "box.lan", user="bb")
        self.nid = mint["id"]

    def keys(self, word):
        return {"session": "claude-alpha", "argv": ["send-keys", "-t", "claude-alpha", word, "Enter"]}

    def test_keys_asked_a_moment_ago_are_typed_and_old_ones_never(self):
        now = 1_800_000_000.0
        with mock.patch.object(nodes.time, "time", lambda: now):
            nodes.session_tmux(self.nid, [self.keys("old")])
        with mock.patch.object(nodes.time, "time", lambda: now + nodes.TMUX_KEEP_S + 1):
            nodes.session_tmux(self.nid, [self.keys("new")])
            got = nodes._tmux_take(self.nid)
        self.assertEqual([op["argv"][3] for op in got], ["new"], "the one asked a day ago is dropped, never typed")
        self.assertEqual(nodes._tmux_take(self.nid), [], "taken once")

    def test_a_node_away_holds_at_most_its_cap(self):
        for i in range(nodes.TMUX_OPS_MAX + 10):
            nodes.session_tmux(self.nid, [self.keys(str(i))])
        got = nodes._tmux_take(self.nid)
        self.assertEqual(len(got), nodes.TMUX_OPS_MAX)
        self.assertEqual(got[-1]["argv"][3], str(nodes.TMUX_OPS_MAX + 9), "the newest kept, in order")


if __name__ == "__main__":
    unittest.main()
