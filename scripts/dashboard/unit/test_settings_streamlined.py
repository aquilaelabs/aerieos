"""State 21 (R223): a repository's daily snapshot switch saved off becomes 0
days kept, and a person's per-space terminal colors go; idempotent."""
import importlib
import json
import os
import sys
import tempfile
import unittest
from pathlib import Path

sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)), ".."))


class Streamlined(unittest.TestCase):
    def test_the_switch_becomes_days_and_the_colors_go(self):
        mig = importlib.import_module("statemigrations.0021_settings_streamlined")
        d = tempfile.mkdtemp()
        f = Path(d) / "prefs.json"
        f.write_text(json.dumps({
            "projects": {"off": {"snapshots_on": False, "snapshot_days": 14}, "on": {"snapshots_on": True, "snapshot_days": 9},
                         "plain": {"build": "make"}},
            "users": {"u_1": {"off": {"term_scheme": "nord", "reply": "short"}}}}))
        mig.run({"state": d})
        got = json.loads(f.read_text())
        self.assertEqual(got["projects"]["off"], {"snapshot_days": 0})
        self.assertEqual(got["projects"]["on"], {"snapshot_days": 9})
        self.assertEqual(got["projects"]["plain"], {"build": "make"})
        self.assertEqual(got["users"]["u_1"]["off"], {"reply": "short"})
        mig.run({"state": d})
        self.assertEqual(json.loads(f.read_text()), got, "a second run changes nothing")


if __name__ == "__main__":
    unittest.main()
