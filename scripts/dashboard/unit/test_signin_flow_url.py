"""A sign-in's link and code as the page offers them, read from a job's log:
the node's driver's lines (one each, R234 step 6), never the program's own
screen, which the driver reads on the node. The screens are the programs'
own, as each printed them on 12 Nov (Codex CLI 0.164.0, Copilot CLI, Grok
Build)."""
import os
import sys
import unittest

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))
import signin  # noqa: E402

CODEX = ("\r\nWelcome to Codex [v\x1b[90m0.164.0\x1b[0m]\r\n\x1b[90mOpenAI's command-line coding agent\x1b[0m\r\n\r\n"
         "Follow these steps to sign in with ChatGPT using device code authorization:\r\n\r\n"
         "1. Open this link in your browser and sign in to your account\r\n   \x1b[94mhttps://auth.openai.com/codex/device\x1b[0m\r\n\r\n"
         "2. Enter this one-time code \x1b[90m(expires in 15 minutes)\x1b[0m\r\n   \x1b[94mABCD-EFGH2\x1b[0m\r\n\r\n"
         "\x1b[90mContinue only if you started this login in Codex. If a website or another person gave you this code, cancel.\x1b[0m\r\n\r\n")
COPILOT = ("To authenticate, visit https://github.com/login/device and enter code 1A2B-3C4D\r\nWaiting for authorization...\r\n"
           "\x1b]52;p!;RDUyRS05NTlB;\x07\x1b]52;c;RDUyRS05NTlB\x07Failed to open browser. Please visit https://github.com/login/device "
           "and enter the code 1A2B-3C4D manually.\r\n")
GROK = ("\r\nTo sign in, open this URL in your browser:\r\n\r\n  https://accounts.x.ai/oauth2/device?user_code=WXYZ-9876\r\n\r\n"
        "  (Could not open browser automatically: open the URL above manually.)\r\n\r\nConfirm this code in your browser:\r\n\r\n"
        "  WXYZ-9876\r\n\r\n\x1b[90mOnly continue with a code you requested. Don't share it with anyone.\x1b[0m\r\n\r\nWaiting for authorization...\r\n")
CLAUDE = ("Opening browser to sign in...\r\nIf the browser didn't open, visit: https://claude.com/cai/oauth/authorize?code=true&client_id=abc"
          "&state=xyz\r\n\r\nPaste code here if prompted > ")


class Nodes:
    def __init__(self, log, state="running"):
        self.j = {"log": log, "state": state}

    def job(self, _id):
        return self.j


def read(agent, log):
    return signin.NodeFlow(Nodes(log), "n_1", "j_1", "node one", uid="u_1", agent=agent).state()


class TheDriversLines(unittest.TestCase):
    def test_every_agents_flow_reads_the_same(self):
        for agent, paste in (("claude", True), ("codex", False), ("copilot", False), ("grok", False)):
            log = "signing in\n[aerieos] open this link to sign in: https://example.org/a?b=c\n" + (
                "[aerieos] Paste code: the one that page gives you once you have signed in there\n" if paste
                else "[aerieos] then enter this code there: QRST-1234\n")
            got = read(agent, log)
            self.assertEqual((got["url"], got["code"], got["paste"], got["waiting"]),
                             ("https://example.org/a?b=c", "" if paste else "QRST-1234", paste, paste), agent)


class TheProgramsOwnScreen(unittest.TestCase):
    """The driver says the link and the code; a screen in the log is not
    read for either."""

    def test_no_screen_is_taken_for_a_link_or_a_code(self):
        for agent, screen in (("codex", CODEX), ("copilot", COPILOT), ("grok", GROK), ("claude", CLAUDE)):
            got = read(agent, screen)
            self.assertEqual((got["url"], got["code"]), ("", ""), agent)

    def test_the_drivers_line_is_read_past_the_ptys_carriage_returns_and_colors(self):
        got = read("codex", "\x1b[0m[aerieos] open this link to sign in: https://auth.openai.com/codex/device\r\n"
                            "[aerieos] then enter this code there: ABCD-EFGH2\r\n")
        self.assertEqual((got["url"], got["code"]), ("https://auth.openai.com/codex/device", "ABCD-EFGH2"))


if __name__ == "__main__":
    unittest.main()
