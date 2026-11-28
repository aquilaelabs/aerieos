"""sessionsasked: which account's terminals the controller opened on each
node, for which space, so a node's heartbeat is handed a
fresh session token only for a pair it was given already."""
import os
import pathlib
import sys
import tempfile
import unittest

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))
import sessionsasked  # noqa: E402
import statefile  # noqa: E402


class Asked(unittest.TestCase):
    def setUp(self):
        self.d = pathlib.Path(tempfile.mkdtemp())
        sessionsasked.configure(state=self.d, write_json_fn=statefile.write_json)

    def test_a_pair_is_asked_only_on_the_node_its_terminal_opened_on(self):
        sessionsasked.note("n_a", "u_1", "alpha", now=1000)
        self.assertTrue(sessionsasked.asked("n_a", "u_1", "alpha", now=1001))
        self.assertFalse(sessionsasked.asked("n_b", "u_1", "alpha", now=1001), "another node")
        self.assertFalse(sessionsasked.asked("n_a", "u_2", "alpha", now=1001), "another account")
        self.assertFalse(sessionsasked.asked("n_a", "u_1", "beta", now=1001), "another space")
        self.assertEqual(oct((self.d / "sessions-asked.json").stat().st_mode & 0o777), "0o600")

    def test_a_pair_lasts_a_month_from_when_it_was_last_seen(self):
        sessionsasked.note("n_a", "u_1", "alpha", now=1000)
        month = sessionsasked.KEEP_S
        self.assertTrue(sessionsasked.asked("n_a", "u_1", "alpha", now=1000 + month - 10), "seen, so kept")
        self.assertTrue(sessionsasked.asked("n_a", "u_1", "alpha", now=1000 + 2 * month - 20), "a running session keeps it")
        self.assertFalse(sessionsasked.asked("n_a", "u_1", "alpha", now=1000 + 4 * month), "a month unseen and it goes")

    def test_nothing_is_kept_without_a_node_an_account_and_a_space(self):
        sessionsasked.note("", "u_1", "alpha")
        sessionsasked.note("n_a", "", "alpha")
        sessionsasked.note("n_a", "u_1", "")
        self.assertFalse((self.d / "sessions-asked.json").exists())


if __name__ == "__main__":
    unittest.main()
