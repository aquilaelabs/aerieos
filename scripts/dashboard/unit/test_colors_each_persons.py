"""statemigrations 0032 (R294 step 14): a space's color, kept in its settings
before colors were each person's, becomes the own colors of every account that
had picked none, so nobody's cards change, and leaves the settings; an account
with colors of its own keeps exactly them; run twice, nothing more moves."""
import importlib
import json
import os
import sys
import tempfile
import unittest
from pathlib import Path

sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)), ".."))
m0032 = importlib.import_module("statemigrations.0032_colors_each_persons")


class ColorsEachPersons(unittest.TestCase):
    def setUp(self):
        self.d = tempfile.TemporaryDirectory()
        self.addCleanup(self.d.cleanup)
        self.state = Path(self.d.name)
        (self.state / "claude-prefs.json").write_text(json.dumps({"projects": {
            "alpha": {"color": "teal", "build": "make"}, "beta": {"color": ""}, "gamma": {"color": "plaid"}, "delta": {"node": "n_1"}}}))
        (self.state / "users.json").write_text(json.dumps({"users": {
            "owner": {"uid": "u_1"}, "ada": {"uid": "u_2"}, "cy": {"uid": "u_3"}}}))
        (self.state / "project-colors.json").write_text(json.dumps({"u_2": {"beta": "red"}}))

    def read(self, name):
        return json.loads((self.state / name).read_text())

    def test_each_account_keeps_what_it_was_shown_and_the_settings_hold_none(self):
        m0032.run({"state": str(self.state)})
        marks = self.read("project-colors.json")
        self.assertEqual(marks["u_1"], {"alpha": "teal"}, "picked none: given the space colors it was shown")
        self.assertEqual(marks["u_3"], {"alpha": "teal"})
        self.assertEqual(marks["u_2"], {"beta": "red"}, "its own, as they were")
        projects = self.read("claude-prefs.json")["projects"]
        self.assertFalse(any("color" in r for r in projects.values()), projects)
        self.assertEqual(projects["alpha"]["build"], "make", "the rest of a space's settings are left as they are")

    def test_twice_is_once(self):
        m0032.run({"state": str(self.state)})
        first = (self.read("project-colors.json"), self.read("claude-prefs.json"))
        m0032.run({"state": str(self.state)})
        self.assertEqual((self.read("project-colors.json"), self.read("claude-prefs.json")), first)

    def test_no_space_color_writes_no_colors(self):
        (self.state / "claude-prefs.json").write_text(json.dumps({"projects": {"alpha": {"node": "n_1"}}}))
        (self.state / "project-colors.json").unlink()
        m0032.run({"state": str(self.state)})
        self.assertFalse((self.state / "project-colors.json").exists())


if __name__ == "__main__":
    unittest.main()
