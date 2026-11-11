"""A working session's mark turns in its title several times a second; which
frame a look caught is not news. The controller writes nothing and tells no
page for a frame, in a session report or a heartbeat, and the agent does not
send one; working turning to waiting is still told at once."""
import os
import sys
import tempfile
import unittest

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, os.path.join(HERE, ".."))
sys.path.insert(0, os.path.join(HERE, "..", "..", "agent"))
import nodes  # noqa: E402
from aerieos_agent import sessions as agent_sessions  # noqa: E402


def row(title, name="u_1~claude-app"):
    return {"name": name, "attached": False, "cwd": "/workspace/app", "created": 100, "title": title}


class Frames(unittest.TestCase):
    def setUp(self):
        nodes.configure(state=tempfile.mkdtemp())
        mint = nodes.enroll_mint("user:test", "box")
        nodes.enroll(nodes.authenticate(mint["token"]), {"cpu": 2, "mem_mb": 4096, "arch": "x86_64",
                                                         "system": "linux", "session": {"up": True, "user": "b"}},
                     "10.0.0.5", user="bb")
        self.nid = mint["id"]

    def rev(self):
        return nodes._rev[0] if isinstance(getattr(nodes, "_rev", None), list) else nodes.rev()

    def test_a_frame_is_not_told_and_a_turn_is(self):
        nodes.sessions_report(self.nid, [row("◐ Fix the login")])
        at = self.rev()
        for frame in "◓◑◒◐⠂⠐":
            nodes.sessions_report(self.nid, [row(f"{frame} Fix the login")])
        self.assertEqual(self.rev(), at, "a frame of the working mark moved the nodes token")
        self.assertTrue(nodes.node(self.nid)["reported"]["sessions"][0]["title"].endswith("Fix the login"))
        nodes.sessions_report(self.nid, [row("✳ Fix the login")])
        self.assertNotEqual(self.rev(), at, "working turned to waiting and no page was told")
        at = self.rev()
        nodes.sessions_report(self.nid, [row("◐ Another task")])
        self.assertNotEqual(self.rev(), at)
        at = self.rev()
        nodes.sessions_report(self.nid, [row("◐ Another task"), row("✳ Claude Code", "u_1~claude-web")])
        self.assertNotEqual(self.rev(), at, "a session started and no page was told")

    def test_a_heartbeat_on_another_frame_is_its_numbers_alone(self):
        nodes.heartbeat(self.nid, {"cpu_pct": 1, "sessions": [row("◐ Fix the login")]}, "10.0.0.5")
        at = self.rev()
        nodes.heartbeat(self.nid, {"cpu_pct": 2, "sessions": [row("◑ Fix the login")]}, "10.0.0.5")
        self.assertEqual(self.rev(), at)
        nodes.heartbeat(self.nid, {"cpu_pct": 3, "sessions": [row("✳ Fix the login")]}, "10.0.0.5")
        self.assertNotEqual(self.rev(), at)

    def test_the_agent_sends_a_change_and_not_a_frame(self):
        sent = []

        class Ctl:
            def call(self, verb, body, timeout=0):
                sent.append(body["sessions"][0]["title"])
                return 200, {}

        class Agent:
            session_up = True
            ctl = Ctl()
            now = [row("◐ Fix the login")]

            def sessions_now(self):
                return self.now
        a = Agent()
        w = agent_sessions.SessionWatch(a)
        w.step()                              # the first look is what the hello carried
        for title in ("◓ Fix the login", "◑ Fix the login", "⠂ Fix the login"):
            a.now = [row(title)]
            w.step()
        self.assertEqual(sent, [])
        a.now = [row("✳ Fix the login")]
        w.step()
        self.assertEqual(sent, ["✳ Fix the login"])
        self.assertEqual(agent_sessions.steady("plain title"), "plain title")
        self.assertEqual(agent_sessions.steady("é accent"), "é accent")
        self.assertEqual(agent_sessions.steady(""), "")


if __name__ == "__main__":
    unittest.main()
