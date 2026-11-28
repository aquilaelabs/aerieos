"""A state file that goes bad while the controller runs keeps a copy.

At start an unreadable file in /config is copied aside before any loader
reads it as empty. One that went bad afterwards (a hand edit with a
syntax error, a restore cut short) was read as empty by its loader and the
next write saved that over it: one bug filed, and every space's rows and
history were gone. Its loader keeps a copy now, once for each state of the
file, and says so on the log; what is written next is the change alone, as
before, and the copy is what a person mends from."""
import contextlib
import io
import json
import os
import sys
import tempfile
import unittest
from pathlib import Path

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))
import devapp  # noqa: E402
import roadmap  # noqa: E402
import statefile  # noqa: E402

BAD = '{"projects": {"alpha": {"items": [{"id": 1, "text": "kept"'


def write_json(p, d, mode=0o644):
    del mode
    Path(p).write_text(json.dumps(d))


def copies(folder, name):
    return sorted(f for f in os.listdir(folder) if f.startswith(name + ".unreadable-"))


class Kept(unittest.TestCase):
    def setUp(self):
        self.dir = tempfile.mkdtemp()
        self.log = io.StringIO()

    def quiet(self):
        return contextlib.redirect_stderr(self.log)

    def test_the_roadmap_cut_short_keeps_a_copy_before_the_next_write(self):
        roadmap.configure(state=self.dir, write_json=write_json)
        Path(roadmap.FILE).write_text(BAD)
        with self.quiet():
            roadmap.add("alpha", "a new one")
            roadmap.add("alpha", "and another")
        kept = copies(os.path.dirname(roadmap.FILE), os.path.basename(roadmap.FILE))
        self.assertEqual(len(kept), 1, "one copy, however often it is read")
        self.assertEqual(Path(os.path.dirname(roadmap.FILE), kept[0]).read_text(), BAD)
        self.assertIn("cannot be read", self.log.getvalue())
        self.assertIn(kept[0], self.log.getvalue())

    def test_a_store_file_and_the_containers_store_keep_one_too(self):
        path = os.path.join(self.dir, "phone.json")
        Path(path).write_text("{not json")
        st = statefile.Store(lambda: path)
        with self.quiet():
            self.assertEqual(st.load(), {})
            self.assertEqual(st.load(), {})
        self.assertEqual(len(copies(self.dir, "phone.json")), 1)
        cached = os.path.join(self.dir, "router.json")
        Path(cached).write_text("[1, 2")
        with self.quiet():
            self.assertEqual(statefile.Store(lambda: cached, cached=True).load(), {})
        self.assertEqual(len(copies(self.dir, "router.json")), 1)
        devapp.configure(workspace=self.dir, state=self.dir, write_json=write_json)
        Path(devapp.FILE).write_text('{"alpha": {"web": {"port"')
        with self.quiet():
            self.assertEqual(devapp._load(), {})
        self.assertEqual(len(copies(os.path.dirname(devapp.FILE), os.path.basename(devapp.FILE))), 1)

    def test_a_missing_file_is_a_first_one_and_keeps_nothing(self):
        roadmap.configure(state=self.dir, write_json=write_json)
        with self.quiet():
            roadmap.add("alpha", "the first")
        self.assertEqual([f for f in os.listdir(self.dir) if ".unreadable-" in f], [])
        self.assertEqual(self.log.getvalue(), "")


if __name__ == "__main__":
    unittest.main()
