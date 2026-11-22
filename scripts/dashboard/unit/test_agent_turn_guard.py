"""A part of the agent's turn that raises is that part's alone, and a turn
that raises is followed by the next one, never the end of the agent: one
exception ended the process with no bye, its jobs orphaned and read lost."""
import unittest
from unittest import mock
import agentpkg  # noqa: E402

agent = agentpkg.load("aerieos_agent")


class TurnPart(unittest.TestCase):
    def test_a_part_that_raises_says_nothing_and_is_logged_once(self):
        said = []
        turn = {}

        def boom():
            raise TimeoutError("mount took too long")
        with mock.patch.object(agent.module("agent"), "log_once", side_effect=lambda k, m, **kw: said.append((k, m))):
            self.assertIsNone(agent.turn_part(turn, "array", boom))
            self.assertEqual(agent.turn_part(turn, "tokens", lambda: 7), 7)
        self.assertEqual([k for k, _ in said], ["turn-array"])
        self.assertIn("TimeoutError: mount took too long", said[0][1])
        self.assertIn("boom", said[0][1], "where it raised is said with it")

    def test_a_slow_part_is_timed_into_the_turn(self):
        turn = {}
        clock = iter([10.0, 10.5])
        with mock.patch.object(agent.module("agent").time, "monotonic", side_effect=lambda: next(clock)):
            agent.turn_part(turn, "sample", lambda: {})
        self.assertEqual(turn, {"sample": 500})


class KeepTurning(unittest.TestCase):
    def test_a_turn_that_raises_is_followed_by_the_next(self):
        calls = []

        def turns():
            calls.append(1)
            if len(calls) < 3:
                raise KeyError("held")
            raise SystemExit(0)
        with mock.patch.object(agent.module("agent"), "log_once") as said, \
                mock.patch.object(agent.module("agent").time, "sleep") as slept:
            with self.assertRaises(SystemExit):
                agent.keep_turning(turns, pause=5)
        self.assertEqual(len(calls), 3, "a stop still ends it; a fault does not")
        self.assertEqual(said.call_count, 2)
        self.assertEqual([c.args for c in slept.call_args_list], [(5,), (5,)])


if __name__ == "__main__":
    unittest.main()
