"""A session whose program has ended: its pane stays with what it
said (remain-on-exit), so the tmux session lives on; the agent says so with
its exit status, and the controller counts it as over, where it read as
running until somebody pressed Restart."""
import os
import sys
import unittest
from unittest import mock

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, os.path.join(HERE, ".."))
sys.path.insert(0, os.path.join(HERE, "..", "..", "agent"))
import nodes  # noqa: E402
from aerieos_agent import sessions as agent_sessions  # noqa: E402


class Agent(unittest.TestCase):
    def test_a_dead_pane_is_said_with_its_exit(self):
        me = agent_sessions.SessionsMixin()
        me._tmux = lambda argv, **k: ("u_1~claude-alpha\t1\t0\t/workspace/alpha\t1795456335\t1\t1\t✳ Claude Code\n"
                                      "u_1~claude-beta\t1\t1\t/workspace/beta\t1795456300\t0\t\t✳ Claude Code\n"
                                      "u_1~claude-beta\t0\t1\t/workspace/beta\t1795456300\t0\t\tsome other pane\n")
        rows = me.sessions_now()
        self.assertEqual([r["name"] for r in rows], ["u_1~claude-alpha", "u_1~claude-beta"])
        self.assertEqual((rows[0].get("dead"), rows[0].get("exit"), rows[0]["title"]), (True, 1, "✳ Claude Code"))
        self.assertNotIn("dead", rows[1])


class Controller(unittest.TestCase):
    def test_the_row_keeps_it_and_the_running_sessions_leave_it_out(self):
        rows = nodes._session_rows([{"name": "u_1~claude-alpha", "dead": True, "exit": 1, "title": "x"},
                                    {"name": "u_1~claude-beta", "title": "y"},
                                    {"name": "u_1~claude-gamma", "dead": True, "exit": "rm -rf"}])
        self.assertEqual((rows[0]["dead"], rows[0]["exit"]), (True, 1))
        self.assertNotIn("dead", rows[1])
        self.assertIsNone(rows[2]["exit"])
        node = {"id": "n_1", "name": "box", "kind": "agent", "state": "online", "live": True,
                "reported": {"sessions": rows}}
        with mock.patch.object(nodes, "node_list", lambda: [node]), \
             mock.patch.object(nodes, "still_ending", lambda nid, r, now: False):
            self.assertEqual([r["name"] for r in nodes.node_sessions()["n_1"][1]], ["u_1~claude-beta"])


if __name__ == "__main__":
    unittest.main()
