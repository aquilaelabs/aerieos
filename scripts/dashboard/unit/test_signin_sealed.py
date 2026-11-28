"""A sealed sign-in is a sign-in, whoever looks (a
restart said Claude was signed out on a node that held the sign-in, and
signing in again showed only after a reload).

The check a terminal runs reads the home as the account, which cannot read
root's seal: a link the node left to a copy that is closed now is a sign-in
(login-list.closed_seal), never a sign-out. The controller believes no
sign-out for a node whose census holds the account's seal
(claudegrant.sealed_on). And a report moves the page's token
(claudegrant.rev), so the page re-reads at once."""
import importlib.util
import json
import os
import shutil
import sys
import tempfile
import time
import unittest
from pathlib import Path

HERE = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(HERE))
import claudegrant  # noqa: E402

spec = importlib.util.spec_from_file_location("loginlist_sealed", HERE.parent / "lib" / "login-list.py")
assert spec and spec.loader
loginlist = importlib.util.module_from_spec(spec)
spec.loader.exec_module(loginlist)


class ClosedSeal(unittest.TestCase):
    def setUp(self):
        tmp = tempfile.mkdtemp()
        self.addCleanup(shutil.rmtree, tmp, True)
        self.home = os.path.join(tmp, "users", "u_12345678")
        os.makedirs(os.path.join(self.home, ".claude"))
        os.makedirs(os.path.join(self.home, ".codex"))
        for name, value in (("OPEN_DIR", os.path.join(tmp, "open")), ("SEAL_DIR", os.path.join(tmp, "seals"))):
            saved = getattr(loginlist, name)
            setattr(loginlist, name, value)
            self.addCleanup(setattr, loginlist, name, saved)
        self.open = os.path.join(loginlist.OPEN_DIR, "u_12345678")
        with open(os.path.join(self.home, ".claude.json"), "w") as f:
            json.dump({"oauthAccount": {"emailAddress": "me@example.test"}}, f)

    def link(self, rel, to):
        os.symlink(to, os.path.join(self.home, rel))

    def who(self, agent):
        return loginlist.who_of(self.home, agent, loginlist.signins()[agent])

    def test_claude_with_its_copy_closed_is_signed_in_as_its_config_says(self):
        self.link(os.path.join(".claude", ".credentials.json"), os.path.join(self.open, "claude.json"))
        self.assertEqual(self.who("claude")["email"], "me@example.test")

    def test_claude_with_its_copy_open_is_signed_in_as_before(self):
        os.makedirs(self.open)
        with open(os.path.join(self.open, "claude.json"), "w") as f:
            f.write("{}")
        self.link(os.path.join(".claude", ".credentials.json"), os.path.join(self.open, "claude.json"))
        self.assertEqual(self.who("claude")["email"], "me@example.test")

    def test_claude_with_no_sign_in_file_is_signed_out(self):
        self.assertIsNone(self.who("claude"))

    def test_a_link_to_anywhere_else_that_is_gone_is_no_sign_in(self):
        self.link(os.path.join(".claude", ".credentials.json"), "/nowhere/claude.json")
        self.assertIsNone(self.who("claude"))

    def test_where_the_seals_can_be_read_a_seal_that_is_gone_is_a_sign_out(self):
        os.makedirs(os.path.join(loginlist.SEAL_DIR, "u_12345678"))
        self.link(os.path.join(".claude", ".credentials.json"), os.path.join(self.open, "claude.json"))
        self.assertIsNone(self.who("claude"))

    def test_an_agent_whose_one_file_is_closed_is_unread_never_signed_out(self):
        self.link(os.path.join(".codex", "auth.json"), os.path.join(self.open, "codex.json"))
        got = self.who("codex")
        self.assertEqual(got, {"error": "sealed here, its copy not open now"})


class SealedOn(unittest.TestCase):
    CENSUS = {"E": "ab", "sealed": {"u_12345678": {"claude": {"R": "01", "K": "", "email": "me@example.test", "plan": ""}}}}

    def test_a_census_holding_the_accounts_seal_is_a_sign_in(self):
        self.assertTrue(claudegrant.sealed_on(self.CENSUS, "u_12345678"))
        self.assertTrue(claudegrant.sealed_on(self.CENSUS, "u_12345678", "claude"))

    def test_another_agent_another_account_or_no_census_is_not(self):
        self.assertFalse(claudegrant.sealed_on(self.CENSUS, "u_12345678", "codex"))
        self.assertFalse(claudegrant.sealed_on(self.CENSUS, "u_87654321"))
        self.assertFalse(claudegrant.sealed_on(self.CENSUS, ""))
        for none in (None, {}, {"sealed": []}, {"sealed": {"u_12345678": "x"}}):
            self.assertFalse(claudegrant.sealed_on(none, "u_12345678"), none)

    def test_the_handler_asks_it_before_a_sign_out_is_written(self):
        text = (HERE / "server.py").read_text(encoding="utf-8")
        at = text.index("claudegrant.sealed_on(")
        self.assertLess(at, text.index("r = claudegrant.report(home_for(uid), nid"))
        self.assertIn('return self._json({"ok": True, "sealed": True})', text[at:at + 700])


class Rev(unittest.TestCase):
    def test_a_report_moves_the_accounts_token_and_no_other(self):
        tmp = Path(tempfile.mkdtemp())
        self.addCleanup(shutil.rmtree, tmp, True)
        mine, theirs = tmp / "mine", tmp / "theirs"
        self.assertEqual(claudegrant.rev(str(mine)), 0)
        claudegrant.report(str(mine), "n_1", "me@example.test")
        first = claudegrant.rev(str(mine))
        self.assertGreater(first, 0)
        self.assertEqual(claudegrant.rev(str(theirs)), 0)
        time.sleep(0.01)
        claudegrant.report(str(mine), "n_1", "", signed_in=False, agent="codex")
        claudegrant.report(str(mine), "n_1", "me@example.test", agent="codex")
        self.assertGreater(claudegrant.rev(str(mine)), first)
        self.assertEqual(claudegrant.rev(""), 0)

    def test_the_page_re_reads_on_it(self):
        self.assertIn('onRev("signins", () => refresh());', (HERE / "page-boot.js").read_text(encoding="utf-8"))
        self.assertIn('"signins": claudegrant.rev(', (HERE / "server.py").read_text(encoding="utf-8"))


if __name__ == "__main__":
    unittest.main()
