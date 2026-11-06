"""An end heard late leaves a newer session alone: Restart ends a session and
starts one under the same name, and an agent whose held poll was down (the
controller restarting) heard the end after the new one started and ended it
as its terminal opened. The controller sends how long ago each end was asked;
a session made since is not ended."""
import os
import sys
import time
import unittest

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)
import agentpkg  # noqa: E402
agent = agentpkg.load("kill_late")


class KillLate(unittest.TestCase):
    def setUp(self):
        self.a = object.__new__(agent.Agent)
        self.killed, self.made = [], {}

        def tmux(argv, timeout=10):
            name = argv[argv.index("-t") + 1].lstrip("=")
            if argv[0] == "display-message":
                return f"{self.made[name]}\n" if name in self.made else None
            self.killed.append(name)
            return ""
        self.a._tmux = tmux

    def test_a_session_made_after_the_ask_stays(self):
        now = int(time.time())
        self.made = {"u_1~claude-app": now - 3, "u_1~claude-old": now - 600}
        self.a.kill_sessions(["u_1~claude-app", "u_1~claude-old"],
                             ages={"u_1~claude-app": 20, "u_1~claude-old": 20})
        self.assertEqual(self.killed, ["u_1~claude-old"])

    def test_without_ages_every_name_ends(self):
        self.made = {"u_1~claude-app": int(time.time())}
        self.a.kill_sessions(["u_1~claude-app", "u_1~gone"])
        self.assertEqual(self.killed, ["u_1~claude-app", "u_1~gone"])


if __name__ == "__main__":
    unittest.main()
