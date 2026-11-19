"""A session that works a whole turn with no hook heard is marked as working
unguarded: a coding agent passes over a hook it cannot run, so the session
says nothing, and the heartbeat is the other witness the controller has."""
import os
import sys
import unittest
from unittest import mock

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))
import turns  # noqa: E402

K = "u_1~claude-alpha"


class Quiet(unittest.TestCase):
    def setUp(self):
        for d in (turns._heard, turns._watch, turns._claims, turns._ended, turns._waiting):
            d.clear()

    def beat(self, at, working, present=(K,)):
        turns.watch("n_1", set(present), {K} if working else set(), now=at)

    def hook(self, at):
        with mock.patch.object(turns.time, "time", return_value=at):
            turns.heard(K)

    def test_a_turn_with_its_hooks_heard_is_not_marked(self):
        self.beat(1000, False)
        self.hook(1020)                      # the prompt's hooks, a moment before the spinner
        self.beat(1025, True)
        self.beat(1300, True)
        self.hook(1310)                      # the stop's
        self.beat(1325, False)
        self.beat(1400, False)
        self.assertEqual(turns.unguarded(), [])

    def test_a_turn_begun_and_ended_with_nothing_heard_is_marked_until_a_hook_speaks(self):
        self.hook(500)                       # an earlier turn's, long before
        self.beat(1000, False)
        self.beat(1025, True)
        self.beat(1300, True)
        self.beat(1325, False)
        self.assertEqual(turns.unguarded(), [], "a stop's word is waited for first")
        self.beat(1325 + turns.END_GRACE, False)
        self.assertEqual(turns.unguarded(), [("n_1", K, 1025)])
        self.beat(2000, True)
        self.assertEqual(len(turns.unguarded()), 1, "it stays marked while nothing is heard")
        self.hook(2010)
        self.assertEqual(turns.unguarded(), [])

    def test_a_stretch_under_way_when_the_watch_began_is_never_judged(self):
        self.beat(1000, True)                # the controller came up mid-turn: its claim was lost with it
        self.beat(1300, True)
        self.beat(1325, False)
        self.beat(1400, False)
        self.assertEqual(turns.unguarded(), [])

    def test_a_turn_stopped_by_hand_is_known_by_its_prompt(self):
        self.beat(1000, False)
        self.hook(1020)
        self.beat(1025, True)
        self.beat(1100, False)               # Esc: no stop hook runs
        self.beat(1200, False)
        self.assertEqual(turns.unguarded(), [])

    def test_a_session_that_is_gone_is_forgotten(self):
        self.beat(1000, False)
        self.beat(1025, True)
        self.beat(1100, False)
        self.beat(1200, False)
        self.assertEqual(len(turns.unguarded()), 1)
        self.beat(1225, False, present=())
        self.assertEqual(turns.unguarded(), [])


if __name__ == "__main__":
    unittest.main()
