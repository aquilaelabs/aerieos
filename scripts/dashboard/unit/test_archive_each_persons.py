"""State 25: the one archived list becomes each account's, every existing
account given it as it stood; idempotent; and projects.py reads and writes
an archive by the account."""
import importlib
import json
import os
import sys
import tempfile
import threading
import unittest
from pathlib import Path

sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)), ".."))


class Migration(unittest.TestCase):
    def setUp(self):
        self.d = tempfile.mkdtemp()
        self.mig = importlib.import_module("statemigrations.0025_archive_each_persons")
        self.file = Path(self.d) / self.mig.FILE
        (Path(self.d) / "users.json").write_text(json.dumps({"users": {
            "sean": {"uid": "u_0a1b2c3d"}, "kim": {"uid": "u_11112222"}, "broken": "x"}}))

    def test_every_account_is_given_the_list_as_it_stood(self):
        self.file.write_text(json.dumps(["web", "shop", 3]))
        os.chmod(self.file, 0o640)
        self.mig.run({"state": self.d})
        got = json.loads(self.file.read_text())
        self.assertEqual(got, {"u_0a1b2c3d": ["shop", "web"], "u_11112222": ["shop", "web"]})
        self.assertEqual(self.file.stat().st_mode & 0o777, 0o640, "with the mode it had")
        before = self.file.stat().st_mtime_ns
        self.mig.run({"state": self.d})
        self.assertEqual(json.loads(self.file.read_text()), got, "a second run changes nothing")
        self.assertEqual(self.file.stat().st_mtime_ns, before, "and writes nothing")

    def test_no_file_or_not_a_list_is_left(self):
        self.mig.run({"state": self.d})
        self.assertFalse(self.file.exists())
        for text in ("{not json", json.dumps({"u_1": ["web"]})):
            self.file.write_text(text)
            self.mig.run({"state": self.d})
            self.assertEqual(self.file.read_text(), text)

    def test_the_file_is_the_one_projects_keeps(self):
        import projects
        was = projects.STATE
        projects.STATE = Path(self.d)
        self.addCleanup(lambda: setattr(projects, "STATE", was))
        self.assertEqual(projects._archived_file().name, self.mig.FILE)


class EachPersons(unittest.TestCase):
    def setUp(self):
        import projects
        self.p = projects
        self.d = Path(tempfile.mkdtemp())
        self.was = (projects.STATE, projects.WORKSPACE, projects.write_json, projects.lock)
        (self.d / "ws" / "web").mkdir(parents=True)
        (self.d / "ws" / "shop").mkdir(parents=True)
        projects.STATE, projects.WORKSPACE = self.d, self.d / "ws"
        projects.write_json = lambda f, d, **_: Path(f).write_text(json.dumps(d))
        projects.lock = threading.Lock()
        self.addCleanup(lambda: setattr(projects, "STATE", self.was[0]))
        self.addCleanup(lambda: setattr(projects, "WORKSPACE", self.was[1]))
        self.addCleanup(lambda: setattr(projects, "write_json", self.was[2]))
        self.addCleanup(lambda: setattr(projects, "lock", self.was[3]))

    def test_an_archive_is_the_accounts_alone(self):
        r, code = self.p.archive_verb("u_a", "web", True)
        self.assertEqual((code, r["archived"]), (200, True))
        self.assertEqual(self.p.load_archived("u_a"), ["web"])
        self.assertEqual(self.p.load_archived("u_b"), [], "nobody else's page changes")
        self.p.archive_verb("u_b", "shop", True)
        self.assertEqual(self.p.load_archived("u_a"), ["web"])
        self.p.archive_verb("u_a", "web", False)
        self.assertEqual(self.p.load_archived("u_a"), [])
        self.assertEqual(self.p.load_archived("u_b"), ["shop"])
        self.assertTrue(self.p.app_flags("shop", "u_b")["archived"])
        self.assertFalse(self.p.app_flags("shop", "u_a")["archived"])

    def test_an_unknown_space_is_refused(self):
        r, code = self.p.archive_verb("u_a", "nope", True)
        self.assertEqual(code, 400)


if __name__ == "__main__":
    unittest.main()
