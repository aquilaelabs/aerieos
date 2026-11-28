"""Migration 0044: a forge token kept before entries had ids (keyed
by its host, with no host of its own) and one kept with a port's colon as
git's credential lines write it (%3a) each come out naming the host
accountkeys._entries made of them until 27 Nov, so the account's Keys page
and the projects linked to an entry read the same as before, with the
token's seal untouched."""
import copy
import importlib
import json
import os
import shutil
import sys
import tempfile
import unittest
import urllib.parse
from pathlib import Path

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))
import accountkeys  # noqa: E402

OLD = {"u_00000001": {"forges": {
    "github.com": {"sealed": "c2VhbGVk", "login": "me", "scheme": "https", "at": 3},
    "a1b2c3": {"host": "192.168.1.16%3A3000", "sealed": "b3RoZXI=", "login": "me", "scheme": "http", "at": 2},
    "d4e5f6": {"host": "gitlab.com", "sealed": "dGhpcmQ=", "login": "you", "scheme": "https", "at": 1}}},
       "u_00000002": {"forges": {}}}


def old_reader(d, uid):
    """accountkeys._entries before 0044."""
    fs = (d.get(uid) or {}).get("forges") or {}
    return {fid: dict(f, host=urllib.parse.unquote(str(f.get("host") or fid)).lower())
            for fid, f in fs.items() if isinstance(f, dict)}


class ForgesNameHost(unittest.TestCase):
    def setUp(self):
        self.d = Path(tempfile.mkdtemp())
        self.addCleanup(shutil.rmtree, self.d, True)
        self.f = self.d / "account-secrets.json"
        self.f.write_text(json.dumps(OLD))
        os.chmod(self.f, 0o600)
        accountkeys.configure(state=self.d)

    def run_it(self):
        importlib.import_module("statemigrations.0044_forges_name_host").run({"state": str(self.d)})

    def test_each_entry_names_the_host_it_was_read_as(self):
        self.run_it()
        for uid in OLD:
            self.assertEqual(accountkeys._entries(uid), old_reader(copy.deepcopy(OLD), uid))
        got = json.loads(self.f.read_text())["u_00000001"]["forges"]
        self.assertEqual({fid: (f["host"], f["sealed"]) for fid, f in got.items()},
                         {"github.com": ("github.com", "c2VhbGVk"), "a1b2c3": ("192.168.1.16:3000", "b3RoZXI="),
                          "d4e5f6": ("gitlab.com", "dGhpcmQ=")})
        self.assertEqual(accountkeys.entry_for("u_00000001", host="192.168.1.16:3000")["login"], "me")
        self.assertEqual(self.f.stat().st_mode & 0o777, 0o600)

    def test_it_is_idempotent(self):
        self.run_it()
        once = self.f.read_text()
        self.run_it()
        self.assertEqual(self.f.read_text(), once)


if __name__ == "__main__":
    unittest.main()
