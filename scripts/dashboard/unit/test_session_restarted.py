"""A session a person ended is off the lists at once, for the minute its node
may still report it; one made since under the same name, which is what
Restart starts, is listed (the operator, 19 Nov: the space's card said Start
agent for a minute after a restart, with the session running)."""
import os
import sys
import unittest

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, os.path.join(HERE, ".."))
import nodes  # noqa: E402


class Restarted(unittest.TestCase):
    def setUp(self):
        self.was = dict(nodes._ended)
        nodes._ended.clear()
        nodes._ended[("n_1", "u_1~claude-alpha")] = 1000.0

    def tearDown(self):
        nodes._ended.clear()
        nodes._ended.update(self.was)

    def test_the_one_ended_stays_off_for_its_minute(self):
        row = {"name": "u_1~claude-alpha", "created": 400}
        self.assertTrue(nodes.still_ending("n_1", row, now=1010.0))
        self.assertFalse(nodes.still_ending("n_1", row, now=1061.0))

    def test_one_made_since_is_listed_at_once(self):
        self.assertFalse(nodes.still_ending("n_1", {"name": "u_1~claude-alpha", "created": 1004}, now=1010.0))

    def test_a_row_that_does_not_say_when_it_was_made_is_the_old_one(self):
        self.assertTrue(nodes.still_ending("n_1", {"name": "u_1~claude-alpha"}, now=1010.0))
        self.assertTrue(nodes.still_ending("n_1", {"name": "u_1~claude-alpha", "created": "soon"}, now=1010.0))

    def test_another_session_or_another_node_is_not_touched(self):
        self.assertFalse(nodes.still_ending("n_1", {"name": "u_1~claude-beta", "created": 400}, now=1010.0))
        self.assertFalse(nodes.still_ending("n_2", {"name": "u_1~claude-alpha", "created": 400}, now=1010.0))
        self.assertFalse(nodes.still_ending("n_1", None, now=1010.0))


if __name__ == "__main__":
    unittest.main()
