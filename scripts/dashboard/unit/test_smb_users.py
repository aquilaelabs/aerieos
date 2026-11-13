"""SMB passwords for the accounts (R164 step 1): the NT hash Samba keeps,
set and cleared on Profile, handed to the own machine's hello, a share's
names resolved to Unix users, and the shares a person reaches."""
import json
import os
import shutil
import sys
import tempfile
import unittest
from unittest import mock

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))
import users  # noqa: E402


class SmbPasswords(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.mkdtemp()
        self.addCleanup(shutil.rmtree, self.tmp, True)
        users.configure(state=self.tmp, write_json=lambda p, d: open(p, "w").write(json.dumps(d)))
        with users._lock:
            d = users.load()
            d["users"]["ada"] = {"uid": "u_0a1b2c3d", "role": "admin", "projects": [], "password": "x", "created": 0, "seen": 0}
            d["users"]["bob"] = {"uid": "u_deadbeef", "role": "user", "roles": ["media"], "projects": [], "password": "x", "created": 0, "seen": 0}
            users._save(d)

    def test_the_hash_is_the_one_samba_keeps(self):
        # RFC 1320's vectors through the NT form, and the hash of "password" every tool prints.
        self.assertEqual(users.nt_hash("password"), "8846F7EAEE8FB117AD06BDD830B7586C")
        self.assertEqual(users.nt_hash(""), "31D6CFE0D16AE931B73C59D7E0C089C0")
        self.assertEqual(users._md4(b"abc").hex(), "a448017aaf21d8525fc10ae87aa6729d")
        # The one written out, used where the system's OpenSSL keeps MD4 back: the same answers.
        for text, want in ((b"", "31d6cfe0d16ae931b73c59d7e0c089c0"), (b"a", "bde52cb31de33e46245e05fbdbd6fb24"),
                           (b"abc", "a448017aaf21d8525fc10ae87aa6729d"), (b"message digest", "d9130a8164549fe818874806e1c7014b"),
                           (b"abcdefghijklmnopqrstuvwxyz", "d79e1c308aa5bbcdeea8ed63df412da9")):
            self.assertEqual(users._md4_here(text).hex(), want)
            self.assertEqual(users._md4(text).hex(), want)
        with mock.patch.object(users.hashlib, "new", side_effect=ValueError("unsupported hash type md4")):
            self.assertEqual(users._md4(b"abc").hex(), "a448017aaf21d8525fc10ae87aa6729d")
        self.assertEqual(users._md4(b"12345678901234567890123456789012345678901234567890123456789012345678901234567890").hex(),
                         "e33b4ddc9c38f2199c3e7b164fcc0536")

    def test_set_and_cleared_and_handed_over_as_the_unix_user(self):
        self.assertIn("8 characters", users.set_smb_password("ada", "short")["error"])
        self.assertIn("no account", users.set_smb_password("nobody", "longenough")["error"])
        self.assertEqual(users.set_smb_password("ada", "correct horse")["set"], True)
        self.assertEqual(users.smb_users(), [{"user": "bbu-0a1b2c3d", "nt": users.nt_hash("correct horse"), "name": "ada"}])
        self.assertNotIn("smb_nt", users.all_users()[0], "a listing never carries it")
        self.assertEqual(users.set_smb_password("ada", "")["set"], False)
        self.assertEqual(users.smb_users(), [])
        self.assertNotIn("smb_nt", users.get("ada"))

    def test_a_shares_names_resolve_to_unix_users(self):
        with mock.patch.object(users.roles, "roles_of", side_effect=lambda u: [u.get("role", "user")] + list(u.get("roles") or [])):
            self.assertEqual(users.smb_resolve(["ada", "role:media", "nas", " ", "ada"]), (["bbu-0a1b2c3d", "bbu-deadbeef", "nas"], ""))
            self.assertEqual(users.smb_resolve(["role:nobody-has-it"])[1], "nobody holds the role nobody-has-it")
            self.assertIn("not an account", users.smb_resolve(["Bad Name!"])[1])
        self.assertEqual(users.smb_names(), {"bbu-0a1b2c3d": "ada", "bbu-deadbeef": "bob"})

    def test_the_shares_a_person_reaches_with_the_address(self):
        import nodes
        own = {"id": "n1", "name": "nas", "kind": "agent", "config": {"own": True},
               "reported": {"hostname": "nas", "network": {"addresses": ["192.168.1.20/24"]}, "features": {"shares": {"smb": True}},
                            "shares": [{"name": "media", "smb": {"on": True, "guest": True, "ro": False, "tm": False, "users": []}},
                                       {"name": "docs", "smb": {"on": True, "guest": False, "ro": True, "tm": False, "users": ["bbu-0a1b2c3d"]}},
                                       {"name": "tm", "smb": {"on": True, "guest": False, "ro": False, "tm": True, "users": ["bbu-deadbeef"]}},
                                       {"name": "nfsonly", "smb": {"on": False}, "nfs": {"on": True}}]}}
        with mock.patch.object(nodes, "node_list", return_value=[{"id": "n0", "kind": "agent", "config": {}}, own]):
            got = nodes.smb_shares_for("u_0a1b2c3d")
            self.assertEqual((got["host"], got["address"]), ("nas", "192.168.1.20"))
            self.assertEqual([(r["name"], r["ro"], r["guest"]) for r in got["rows"]], [("media", False, True), ("docs", True, False)])
            self.assertEqual([r["name"] for r in nodes.smb_shares_for("u_deadbeef")["rows"]], ["media", "tm"])
        with mock.patch.object(nodes, "node_list", return_value=[{"id": "n0", "kind": "agent", "config": {}}]):
            self.assertIsNone(nodes.smb_shares_for("u_0a1b2c3d"), "no own machine: the section is not drawn")
        own["reported"]["features"] = {}
        with mock.patch.object(nodes, "node_list", return_value=[own]):
            self.assertIsNone(nodes.smb_shares_for("u_0a1b2c3d"), "an own machine without Samba: not drawn either")


class FollowsTheSignIn(unittest.TestCase):
    """One name and one password (the operator, 4 Nov): a share lists people,
    and on a machine that serves shares a person's sign-in opens them."""

    def setUp(self):
        import tempfile
        import users
        self.users = users
        self.tmp = tempfile.mkdtemp()
        self.patch = mock.patch.object(users, "load", self._load), mock.patch.object(users, "_save", self._save)
        for p in self.patch:
            p.start()
        self.d = {"users": {"sean": {"uid": "u_0a1b2c3d", "password": "x"}}}
        # A share names sean, unless a test says otherwise.
        self.named = {"bbu-0a1b2c3d"}
        named = mock.patch.object(users, "share_named", lambda: self.named)
        named.start()
        self.addCleanup(named.stop)

    def tearDown(self):
        for p in self.patch:
            p.stop()

    def _load(self):
        return self.d

    def _save(self, d):
        self.d = d

    def test_a_password_set_opens_the_shares_on_a_machine_that_serves_them(self):
        u = self.users
        with mock.patch.dict(os.environ, {"BB_INSTALL": "bare-metal"}):
            u._smb_follow(self.d["users"]["sean"], "correct-horse")
        got = self.d["users"]["sean"]
        self.assertEqual(got["smb_nt"], u.nt_hash("correct-horse"))
        self.assertTrue(got["smb_follows"])
        self.assertEqual(u.smb_users(), [{"user": "bbu-0a1b2c3d", "nt": got["smb_nt"], "name": "sean"}])

    def test_nothing_is_kept_where_no_shares_are_served(self):
        with mock.patch.dict(os.environ, {"BB_INSTALL": ""}):
            self.users._smb_follow(self.d["users"]["sean"], "correct-horse")
            self.users.smb_take_up("sean", "correct-horse")
        self.assertNotIn("smb_nt", self.d["users"]["sean"])

    def test_a_password_set_apart_is_not_followed(self):
        u = self.users
        with mock.patch.dict(os.environ, {"BB_INSTALL": "bare-metal"}):
            u._smb_follow(self.d["users"]["sean"], "correct-horse")
            u.set_smb_password("sean", "a-separate-one")
            apart = self.d["users"]["sean"]["smb_nt"]
            u._smb_follow(self.d["users"]["sean"], "another-sign-in")
        self.assertEqual(apart, u.nt_hash("a-separate-one"))
        self.assertEqual(self.d["users"]["sean"]["smb_nt"], apart)
        self.assertNotIn("smb_follows", self.d["users"]["sean"])

    def test_a_person_who_came_by_a_move_is_taken_up_when_they_sign_in(self):
        u = self.users
        with mock.patch.dict(os.environ, {"BB_INSTALL": "bare-metal"}):
            u.smb_take_up("sean", "proved-just-now")
        self.assertEqual(self.d["users"]["sean"]["smb_nt"], u.nt_hash("proved-just-now"))

    def test_an_account_no_share_names_has_no_share_password(self):
        # The NT hash is far weaker than the password's own hash, and was
        # kept for every account at every sign-in (the operator, 13 Nov).
        u = self.users
        self.d["users"]["mia"] = {"uid": "u_11112222", "password": "x"}
        with mock.patch.dict(os.environ, {"BB_INSTALL": "bare-metal"}):
            self.assertFalse(u._smb_follow(self.d["users"]["mia"], "correct-horse"))
            u.smb_take_up("mia", "correct-horse")
            self.assertNotIn("smb_nt", self.d["users"]["mia"])
            # Named since: made from the password as they next sign in.
            self.named = {"bbu-0a1b2c3d", "bbu-11112222"}
            u.smb_take_up("mia", "correct-horse")
            self.assertEqual(self.d["users"]["mia"]["smb_nt"], u.nt_hash("correct-horse"))
            self.assertTrue(self.d["users"]["mia"]["smb_follows"])
            # ...and the same sign-in again writes nothing.
            saves = []
            with mock.patch.object(u, "_save", lambda d: saves.append(1)):
                u.smb_take_up("mia", "correct-horse")
            self.assertEqual(saves, [])

    def test_one_that_followed_goes_when_no_share_names_the_account_any_more(self):
        u = self.users
        with mock.patch.dict(os.environ, {"BB_INSTALL": "bare-metal"}):
            u.smb_take_up("sean", "correct-horse")
            self.assertIn("smb_nt", self.d["users"]["sean"])
            self.named = set()
            # The machine is never handed it, and it is off the record.
            self.assertEqual(u.smb_users(), [])
            for k in ("smb_nt", "smb_at", "smb_follows"):
                self.assertNotIn(k, self.d["users"]["sean"])
            # At a sign-in too, and a second pass finds nothing.
            self.named = {"bbu-0a1b2c3d"}
            u.smb_take_up("sean", "correct-horse")
            self.named = set()
            u.smb_take_up("sean", "correct-horse")
            self.assertNotIn("smb_nt", self.d["users"]["sean"])
            self.assertEqual(u.smb_prune(), 0)

    def test_one_set_apart_stays_whoever_is_named(self):
        u = self.users
        self.named = set()
        with mock.patch.dict(os.environ, {"BB_INSTALL": "bare-metal"}):
            u.set_smb_password("sean", "a-separate-one")
            u.smb_take_up("sean", "correct-horse")
            self.assertEqual(u.smb_prune(), 0)
            self.assertEqual(u.smb_users(), [{"user": "bbu-0a1b2c3d", "nt": u.nt_hash("a-separate-one"), "name": "sean"}])

    def test_while_nobody_can_say_who_is_named_what_is_there_is_kept_and_nothing_is_made(self):
        u = self.users
        self.d["users"]["mia"] = {"uid": "u_11112222", "password": "x"}
        with mock.patch.dict(os.environ, {"BB_INSTALL": "bare-metal"}):
            u.smb_take_up("sean", "correct-horse")
            self.named = None
            u.smb_take_up("mia", "correct-horse")
            self.assertNotIn("smb_nt", self.d["users"]["mia"])
            self.assertEqual(u.smb_prune(), 0)
            # A password changed meanwhile keeps the one that is there in step.
            self.assertTrue(u._smb_follow(self.d["users"]["sean"], "a-new-password"))
            self.assertEqual(self.d["users"]["sean"]["smb_nt"], u.nt_hash("a-new-password"))
            # The question failing is nobody's sign-in failing.
            with mock.patch.object(u, "share_named", lambda: 1 / 0):
                u.smb_take_up("sean", "a-new-password")
            self.assertEqual(self.d["users"]["sean"]["smb_nt"], u.nt_hash("a-new-password"))

    def test_who_is_named_is_a_shares_users_and_readers_on_the_own_machine(self):
        import nodes
        own = {"id": "n1", "kind": "agent", "config": {"own": True},
               "reported": {"shares": [{"name": "docs", "smb": {"on": True, "users": ["bbu-0a1b2c3d"], "readers": ["bbu-11112222"]}},
                                       {"name": "everybody", "smb": {"on": True, "guest": True, "users": []}},
                                       {"name": "off", "smb": {"on": False, "users": ["bbu-99999999"]}}]}}
        other = {"id": "n2", "kind": "agent", "config": {}, "reported": {"shares": [{"name": "x", "smb": {"on": True, "users": ["bbu-77777777"]}}]}}
        with mock.patch.object(nodes, "node_list", return_value=[other, own]):
            self.assertEqual(nodes.smb_named(), {"bbu-0a1b2c3d", "bbu-11112222"})
        with mock.patch.object(nodes, "node_list", return_value=[other, {"id": "n1", "kind": "agent", "config": {"own": True}, "reported": {}}]):
            self.assertIsNone(nodes.smb_named(), "the own machine has not said what it has")
        with mock.patch.object(nodes, "node_list", return_value=[other]):
            self.assertIsNone(nodes.smb_named())


class Migration(unittest.TestCase):
    """State 23: the hashes that were made for everybody are taken away from
    every account no share names."""

    def test_only_an_account_a_share_names_keeps_one_that_followed(self):
        import importlib
        import sqlite3
        mig = importlib.import_module("statemigrations.0023_share_hash_only_with_a_share")
        d = tempfile.mkdtemp()
        self.addCleanup(shutil.rmtree, d, True)
        f = os.path.join(d, "users.json")
        people = {"users": {
            "named": {"uid": "u_0a1b2c3d", "smb_nt": "A" * 32, "smb_at": 5, "smb_follows": True},
            "reader": {"uid": "u_0000beef", "smb_nt": "B" * 32, "smb_at": 5, "smb_follows": True},
            "nobody": {"uid": "u_11112222", "smb_nt": "C" * 32, "smb_at": 5, "smb_follows": True, "password": "kept"},
            "apart": {"uid": "u_33334444", "smb_nt": "D" * 32, "smb_at": 5},
            "plain": {"uid": "u_55556666", "password": "x"}}}
        with open(f, "w") as fh:
            json.dump(people, fh)
        os.chmod(f, 0o600)
        con = sqlite3.connect(os.path.join(d, "builderbot.db"))
        con.execute("CREATE TABLE nodes (id TEXT, kind TEXT, config TEXT, reported TEXT)")
        con.execute("INSERT INTO nodes VALUES ('local', 'local', '{}', '{}')")
        con.execute("INSERT INTO nodes VALUES ('n1', 'agent', ?, ?)", (json.dumps({"own": True}), json.dumps(
            {"shares": [{"name": "docs", "smb": {"on": True, "users": ["bbu-0a1b2c3d"], "readers": ["bbu-0000beef"]}},
                        {"name": "off", "smb": {"on": False, "users": ["bbu-11112222"]}}]})))
        con.execute("INSERT INTO nodes VALUES ('n2', 'agent', '{}', ?)", (json.dumps(
            {"shares": [{"name": "elsewhere", "smb": {"on": True, "users": ["bbu-11112222"]}}]}),))
        con.commit()
        con.close()
        mig.run({"state": d})
        with open(f) as fh:
            got = json.load(fh)["users"]
        self.assertEqual(got["named"], people["users"]["named"])
        self.assertEqual(got["reader"], people["users"]["reader"])
        self.assertEqual(got["nobody"], {"uid": "u_11112222", "password": "kept"}, "named on another node's share, or one switched off, is not named")
        self.assertEqual(got["apart"], people["users"]["apart"], "one set apart is its person's")
        self.assertEqual(got["plain"], people["users"]["plain"])
        self.assertEqual(os.stat(f).st_mode & 0o777, 0o600)
        before = os.stat(f).st_mtime_ns
        mig.run({"state": d})
        self.assertEqual(os.stat(f).st_mtime_ns, before, "a second run writes nothing")

    def test_with_no_own_machine_no_share_is_served_and_every_followed_one_goes(self):
        import importlib
        mig = importlib.import_module("statemigrations.0023_share_hash_only_with_a_share")
        d = tempfile.mkdtemp()
        self.addCleanup(shutil.rmtree, d, True)
        f = os.path.join(d, "users.json")
        with open(f, "w") as fh:
            json.dump({"users": {"a": {"uid": "u_0a1b2c3d", "smb_nt": "A" * 32, "smb_follows": True},
                                 "b": {"uid": "u_33334444", "smb_nt": "D" * 32}}}, fh)
        mig.run({"state": d})
        with open(f) as fh:
            got = json.load(fh)["users"]
        self.assertEqual(got, {"a": {"uid": "u_0a1b2c3d"}, "b": {"uid": "u_33334444", "smb_nt": "D" * 32}})
        # Not there, or not a record: left.
        os.unlink(f)
        mig.run({"state": d})
        self.assertFalse(os.path.exists(f))


if __name__ == "__main__":
    unittest.main()
