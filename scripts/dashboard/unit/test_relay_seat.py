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
                mock.patch.object(users, "_session_key", lambda: b"k" * 32):
            bbrelay.run(me, {"argv": ["diag", "reports"]}, "space")
        return got.get("env") or {}

    def test_the_relayed_verb_runs_as_the_sessions_account(self):
        env = self.run_as({"name": "session:space", "session": "space", "seat": "u_1234abcd"})
        with mock.patch.object(users, "_session_key", lambda: b"k" * 32):
            who = users.session_principal(env["BB_TOKEN"])
        self.assertEqual((who["session"], who["seat"]), ("space", "u_1234abcd"))
        self.assertEqual(env.get("BB_ACCOUNT_UID"), "u_1234abcd")

    def test_a_person_at_a_nodes_console_is_no_session_and_mints_no_seat(self):
        env = self.run_as({"name": "ann", "uid": "u_aaaa1111"})
        with mock.patch.object(users, "_session_key", lambda: b"k" * 32):
            who = users.session_principal(env["BB_TOKEN"])
        self.assertEqual(who["seat"], "")


if __name__ == "__main__":
    unittest.main()
