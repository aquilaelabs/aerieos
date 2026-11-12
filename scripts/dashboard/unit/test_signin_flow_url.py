"""A sign-in's link and code as the page offers them, read from a job's log
whichever wrote it: the node's driver (one line each, R234 step 6), or the
program's own screen, from a node whose bundle is from before the driver ran
the shipped agents' sign-ins. The screens are the programs' own, as each
printed them on 12 Nov (Codex CLI 0.164.0, Copilot CLI, Grok Build).

Codex prints its link in color, and the link must end where the color code
begins, or the page opens an address OpenAI answers with 'your session
ended' (B235)."""
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
    """A node whose bundle is from before: the same data reads the screen."""

    def test_codex_link_ends_at_its_color_code(self):
        got = read("codex", CODEX)
        self.assertEqual((got["url"], got["code"], got["paste"]), ("https://auth.openai.com/codex/device", "ABCD-EFGH2", False))

    def test_copilot_link_and_code(self):
        got = read("copilot", COPILOT)
        self.assertEqual((got["url"], got["code"]), ("https://github.com/login/device", "1A2B-3C4D"))

    def test_grok_link_and_code(self):
        got = read("grok", GROK)
        self.assertEqual((got["url"], got["code"]), ("https://accounts.x.ai/oauth2/device?user_code=WXYZ-9876", "WXYZ-9876"))

    def test_claudes_link_and_its_prompt(self):
        got = read("claude", CLAUDE)
        self.assertEqual(got["url"], "https://claude.com/cai/oauth/authorize?code=true&client_id=abc&state=xyz")
        self.assertEqual((got["code"], got["paste"], got["waiting"]), ("", True, True))

    def test_a_link_without_color_is_taken_whole(self):
        self.assertEqual(read("codex", "open https://auth.openai.com/codex/device?x=1 now")["url"], "https://auth.openai.com/codex/device?x=1")

    def test_nothing_is_a_link_before_one_is_printed(self):
        got = read("codex", "signing in to codex on this machine; the URL follows\n")
        self.assertEqual((got["url"], got["code"]), ("", ""))


if __name__ == "__main__":
    unittest.main()
