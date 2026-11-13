"""States 21 and 22 (R223): a repository's daily snapshot switch saved off
becomes 0 days kept, and a person's per-space terminal colors go; idempotent.
State 21 was written for it and read a file nothing stores, so it changed no
install, and this file's own test wrote that same name and passed. State 22
does it on the file prefs.py keeps, and the test asks prefs.py for the name."""
import importlib
import json
import os
import sys
import tempfile
import unittest
from pathlib import Path

sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)), ".."))

OLD = {"projects": {"off": {"snapshots_on": False, "snapshot_days": 14}, "on": {"snapshots_on": True, "snapshot_days": 9},
                    "plain": {"build": "make"}},
       "users": {"u_1": {"off": {"term_scheme": "nord", "reply": "short"}}}}


class Stored(unittest.TestCase):
    def setUp(self):
        import prefs
        self.d = tempfile.mkdtemp()
        was = prefs.FILE
        prefs.configure(write_json=lambda *a, **k: None, state=self.d)
        self.file = Path(prefs.FILE)
        self.addCleanup(lambda: setattr(prefs, "FILE", was))

    def test_the_switch_becomes_days_and_the_colors_go_on_the_file_settings_are_kept_in(self):
        mig = importlib.import_module("statemigrations.0022_settings_streamlined_stored")
        self.assertEqual(self.file.name, mig.FILE, "the migration's file is the one prefs.py stores")
        self.file.write_text(json.dumps(OLD))
        os.chmod(self.file, 0o640)
        mig.run({"state": self.d})
        got = json.loads(self.file.read_text())
        self.assertEqual(got["projects"]["off"], {"snapshot_days": 0})
        self.assertEqual(got["projects"]["on"], {"snapshot_days": 9})
        self.assertEqual(got["projects"]["plain"], {"build": "make"})
        self.assertEqual(got["users"]["u_1"]["off"], {"reply": "short"})
        self.assertEqual(self.file.stat().st_mode & 0o777, 0o640, "with the mode it had")
        self.assertEqual(sorted(os.listdir(self.d)), [mig.FILE], "and nothing left beside it")
        before = self.file.stat().st_mtime_ns
        mig.run({"state": self.d})
        self.assertEqual(json.loads(self.file.read_text()), got, "a second run changes nothing")
        self.assertEqual(self.file.stat().st_mtime_ns, before, "and writes nothing")

    def test_a_file_that_is_not_there_or_not_a_record_is_left(self):
        mig = importlib.import_module("statemigrations.0022_settings_streamlined_stored")
        mig.run({"state": self.d})
        self.assertEqual(os.listdir(self.d), [])
        for text in ("[1, 2]", "{not json", json.dumps({"projects": [], "users": {"u_1": "x"}})):
            self.file.write_text(text)
            mig.run({"state": self.d})
            self.assertEqual(self.file.read_text(), text)

    def test_state_21_reads_a_name_nothing_stores(self):
        # Kept as shipped, never edited: what it does to an install is nothing.
        mig = importlib.import_module("statemigrations.0021_settings_streamlined")
        self.file.write_text(json.dumps(OLD))
        mig.run({"state": self.d})
        self.assertEqual(json.loads(self.file.read_text()), OLD)


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
