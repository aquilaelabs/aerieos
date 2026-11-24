"""A verb a node's session relays runs on the controller as that session,
for the account it works for: the token the relay hands the verb names the
session's seat. Minted with none, `aerie diag reports` from a node was
refused as an account without the debug grant whatever the account held,
since the gate found no account behind the call."""
import os
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path
from unittest import mock

sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)), ".."))
import bbrelay  # noqa: E402
import users  # noqa: E402


class Seat(unittest.TestCase):
    @staticmethod
    def accounts():
        return {"users": {"dana": {"uid": "u_1234abcd"}, "ann": {"uid": "u_aaaa1111"}}}

    def principal(self, tok):
        with mock.patch.object(users, "_session_key", lambda: b"k" * 32), mock.patch.object(users, "load", self.accounts):
            return users.session_principal(tok)

    def run_as(self, me):
        ws = Path(tempfile.mkdtemp())
        (ws / "space").mkdir()
        got = {}

        def run(argv, **kw):
            got["env"] = kw.get("env") or {}
            return subprocess.CompletedProcess(argv, 0, "", "")
        prefs = mock.Mock()
        prefs.get.return_value = {"gitpol": {}}
        with mock.patch.object(bbrelay, "users", users), \
                mock.patch.object(bbrelay, "WORKSPACE", ws, create=True), \
                mock.patch.object(bbrelay, "STATE", ws, create=True), \
                mock.patch.object(bbrelay, "prefs", prefs, create=True), \
                mock.patch.object(bbrelay.subprocess, "run", side_effect=run), \
                mock.patch.object(users, "_session_key", lambda: b"k" * 32), \
                mock.patch.object(users, "load", self.accounts):
            bbrelay.run(me, {"argv": ["diag", "reports"]}, "space")
        return got.get("env") or {}

    def test_the_relayed_verb_runs_as_the_sessions_account(self):
        env = self.run_as({"name": "session:space", "session": "space", "seat": "u_1234abcd"})
        who = self.principal(env["BB_TOKEN"])
        self.assertEqual((who["session"], who["seat"]), ("space", "u_1234abcd"))
        self.assertEqual(env.get("BB_ACCOUNT_UID"), "u_1234abcd")

    def test_a_persons_relayed_verb_runs_as_that_person(self):
        # R277 (the audit of 24 Nov): minted for nobody, it ran held to the
        # space's dials alone, never to the person's own roles.
        env = self.run_as({"name": "ann", "uid": "u_aaaa1111"})
        self.assertEqual(self.principal(env["BB_TOKEN"])["seat"], "u_aaaa1111")

    def test_a_token_for_an_account_that_is_gone_is_no_token(self):
        env = self.run_as({"name": "session:space", "session": "space", "seat": "u_1234abcd"})
        with mock.patch.object(users, "_session_key", lambda: b"k" * 32), \
                mock.patch.object(users, "load", lambda: {"users": {"ann": {"uid": "u_aaaa1111"}}}):
            self.assertIsNone(users.session_principal(env["BB_TOKEN"]))


if __name__ == "__main__":
    unittest.main()
