"""An archive is each account's own: projects.py reads and writes it by the
account."""
import json
import os
import sys
import tempfile
import threading
import unittest
from pathlib import Path

sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)), ".."))


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
