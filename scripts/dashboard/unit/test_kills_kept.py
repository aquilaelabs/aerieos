"""A session's End is kept until its node takes it (R227 step 13): it was
held in memory, so one pressed just before the controller restarted was
forgotten and the row it took off the page came back. Kept in the store with
when it was asked, taken once, and dropped when nobody took it in a day."""
import os
import sys
import tempfile
import time
import unittest

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))
import nodes  # noqa: E402

CENSUS = {"cpu": 2, "mem_mb": 4096, "arch": "x86_64", "system": "linux"}


class Kept(unittest.TestCase):
    def setUp(self):
        self.state = tempfile.mkdtemp()
        nodes.configure(state=self.state)
        mint = nodes.enroll_mint("user:test", "box")
        nodes.enroll(nodes.authenticate(mint["token"]), CENSUS, "10.0.0.5", user="bb")
        self.nid = mint["id"]

    def test_an_end_outlives_a_restart_and_is_taken_once(self):
        self.assertEqual(nodes.session_kill(self.nid, "u_1~claude-app"), {"ok": True, "queued": True})
        nodes.configure(state=self.state)          # the controller started again on the same state
        took = nodes._kills_take(self.nid)
        self.assertEqual(list(took), ["u_1~claude-app"])
        self.assertLess(time.time() - took["u_1~claude-app"], 5, "with when it was asked")
        self.assertEqual(nodes._kills_take(self.nid), {}, "taken once")

    def test_asked_twice_is_one_end_with_the_later_time(self):
        nodes.session_kill(self.nid, "u_1~claude-app")
        first = nodes._rows("SELECT at FROM kills")[0]["at"]
        time.sleep(0.01)
        nodes.session_kill(self.nid, "u_1~claude-app")
        rows = nodes._rows("SELECT at FROM kills")
        self.assertEqual(len(rows), 1)
        self.assertGreater(rows[0]["at"], first)

    def test_one_nobody_took_in_a_day_is_dropped(self):
        nodes.session_kill(self.nid, "u_1~claude-old")
        nodes._exec("UPDATE kills SET at = ?", (time.time() - nodes.KILL_KEEP_S - 60,))
        self.assertEqual(nodes._kills_take(self.nid), {})
        self.assertEqual(nodes._rows("SELECT * FROM kills"), [], "and off the table")

    def test_another_node_s_are_left_for_it(self):
        nodes.session_kill(self.nid, "u_1~claude-app")
        self.assertEqual(nodes._kills_take("n_ffffffff"), {})
        self.assertEqual(len(nodes._kills_take(self.nid)), 1)


if __name__ == "__main__":
    unittest.main()
