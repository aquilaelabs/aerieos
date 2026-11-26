"""Migrations 0034 and 0035 (R295): a space's `devtest` boolean written as
`tests_in`, and the favorites' flat list from before 27 Sep written by
account, once each, so the readers take one shape."""
import importlib
import json
import os
import shutil
import sys
import tempfile
import unittest
from pathlib import Path

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))


class TestsIn(unittest.TestCase):
    def setUp(self):
        self.d = Path(tempfile.mkdtemp())
        self.addCleanup(shutil.rmtree, self.d, True)
        self.f = self.d / "claude-prefs.json"
        self.mig = importlib.import_module("statemigrations.0034_tests_in_written")

    def test_devtest_is_written_as_where_the_tests_run_and_nothing_else_moves(self):
        self.f.write_text(json.dumps({"projects": {"a": {"devtest": True, "model": "opus"}, "b": {"devtest": False},
                                                   "c": {"devtest": True, "tests_in": "up"}, "d": {"tests_in": "only"}},
                                      "users": {"u": {"x": 1}}}))
        os.chmod(self.f, 0o600)
        self.mig.run({"state": str(self.d)})
        self.assertEqual(json.loads(self.f.read_text()), {"projects": {"a": {"model": "opus", "tests_in": "only"}, "b": {},
                                                                       "c": {"tests_in": "up"}, "d": {"tests_in": "only"}},
                                                          "users": {"u": {"x": 1}}})
        self.assertEqual(self.f.stat().st_mode & 0o777, 0o600)
        before = self.f.read_text()
        self.mig.run({"state": str(self.d)})
        self.assertEqual(self.f.read_text(), before, "run again: as it left it")

    def test_no_file_and_a_file_that_is_not_json_are_left(self):
        self.mig.run({"state": str(self.d)})
        self.assertFalse(self.f.exists())
        self.f.write_text("not json")
        self.mig.run({"state": str(self.d)})
        self.assertEqual(self.f.read_text(), "not json")



class Favorites(unittest.TestCase):
    def setUp(self):
        self.d = Path(tempfile.mkdtemp())
        self.addCleanup(shutil.rmtree, self.d, True)
        self.f = self.d / "pinned-projects.json"
        self.mig = importlib.import_module("statemigrations.0035_favorites_by_account")

    def test_the_flat_list_is_everyones_default_and_one_by_account_is_left(self):
        self.f.write_text(json.dumps(["web", "api", "web", 3]))
        os.chmod(self.f, 0o640)
        self.mig.run({"state": str(self.d)})
        self.assertEqual(json.loads(self.f.read_text()), {"*": ["api", "web"]})
        self.assertEqual(self.f.stat().st_mode & 0o777, 0o640)
        kept = json.dumps({"u_1": ["web"]})
        self.f.write_text(kept)
        self.mig.run({"state": str(self.d)})
        self.assertEqual(self.f.read_text(), kept)


if __name__ == "__main__":
    unittest.main()
