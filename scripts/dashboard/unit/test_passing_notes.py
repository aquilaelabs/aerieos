"""Notes of the moment (which session is editing which file) are replaced
whole like any state file and not waited onto the disk, and a session whose
last note is past its hour is dropped as the next one is written."""
import json
import os
import sys
import tempfile
import time
import unittest
from pathlib import Path
from unittest import mock

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))
import overlap  # noqa: E402
import statefile  # noqa: E402


class PassingNotes(unittest.TestCase):
    def setUp(self):
        self.tmp = Path(tempfile.mkdtemp())

    def test_a_state_file_is_waited_onto_the_disk_and_a_note_is_not(self):
        with mock.patch.object(statefile.os, "fsync") as synced:
            statefile.write_json(self.tmp / "kept.json", {"a": 1})
            kept = synced.call_count
            statefile.write_json(self.tmp / "note.json", {"a": 1}, sync=False)
            self.assertGreaterEqual(kept, 1)
            self.assertEqual(synced.call_count, kept, "a note of the moment waited on the disk")
        self.assertEqual(json.loads((self.tmp / "note.json").read_text()), {"a": 1})
        self.assertEqual([p.name for p in self.tmp.iterdir() if p.name.endswith(".tmp")], [])

    def test_a_session_past_its_hour_is_dropped_as_the_next_note_is_written(self):
        overlap.configure(state=self.tmp, workspace=self.tmp,
                          write_json=lambda p, d: statefile.write_json(p, d, sync=False))
        overlap.note("app", "u_1~claude-app", "a.py", "f")
        overlap.note("web", "u_2~claude-web", "b.py")
        f = overlap._file()
        d = json.loads(Path(f).read_text())
        d["web"]["u_2~claude-web"]["at"] = int(time.time()) - overlap.NOTE_TTL - 60
        d["old"] = {"u_3~claude-old": {"files": {}, "at": 5}}
        Path(f).write_text(json.dumps(d))
        overlap.note("app", "u_1~claude-app", "c.py")
        d = json.loads(Path(f).read_text())
        self.assertEqual(set(d), {"app"})
        self.assertEqual(set(d["app"]["u_1~claude-app"]["files"]), {"a.py", "c.py"})


if __name__ == "__main__":
    unittest.main()
