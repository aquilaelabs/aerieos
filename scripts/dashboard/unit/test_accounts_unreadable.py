"""An accounts file that is there and cannot be read is not a fresh install
(B763): no first account is made over it, nothing is saved over it, and a
state file written is on the disk before its name points at it."""
import json
import os
import sys
import tempfile
import unittest
from pathlib import Path

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))
import statefile  # noqa: E402
import users  # noqa: E402


class Unreadable(unittest.TestCase):
    def setUp(self):
        self.d = Path(tempfile.mkdtemp())
        self.was = users._file
        users._file = lambda: self.d / "users.json"
        self.addCleanup(setattr, users, "_file", self.was)

    def test_a_missing_file_is_a_fresh_install(self):
        self.assertEqual(users.unreadable(), "")
        self.assertTrue(users.fresh())

    def test_one_cut_short_is_not(self):
        (self.d / "users.json").write_text('{"users": {"ann": {"uid": "u_1')
        self.assertIn("cannot be read", users.unreadable())
        self.assertFalse(users.fresh())
        self.assertIn("cannot be read", users.claim("mallory", "a-long-password").get("error", ""))
        with self.assertRaises(OSError):
            users._save({"users": {}})
        self.assertEqual((self.d / "users.json").read_text(), '{"users": {"ann": {"uid": "u_1', "left as it was")

    def test_an_empty_file_and_one_of_another_shape_are_not(self):
        (self.d / "users.json").write_text("")
        self.assertTrue(users.unreadable())
        (self.d / "users.json").write_text("[]")
        self.assertIn("not an accounts file", users.unreadable())

    def test_a_good_one_reads(self):
        (self.d / "users.json").write_text(json.dumps({"users": {}}))
        self.assertEqual(users.unreadable(), "")


class Scan(unittest.TestCase):
    def test_the_unreadable_are_named_and_a_copy_kept(self):
        d = tempfile.mkdtemp()
        Path(d, "good.json").write_text("{}")
        Path(d, "bad.json").write_text('{"a": ')
        Path(d, "notes.txt").write_text("not state")
        got = statefile.unreadable(d)
        self.assertEqual([n for n, _ in got], ["bad.json"])
        kept = statefile.set_aside(d, "bad.json")
        self.assertTrue(kept.startswith("bad.json.unreadable-"))
        self.assertEqual(Path(d, kept).read_text(), '{"a": ')

    def test_a_write_is_synced_and_whole(self):
        d = tempfile.mkdtemp()
        synced = []
        was = os.fsync
        os.fsync = lambda fd: synced.append(fd)
        self.addCleanup(setattr, os, "fsync", was)
        statefile.write_json(os.path.join(d, "x.json"), {"a": 1})
        self.assertEqual(len(synced), 2, "the file, then the folder its name is in")
        self.assertEqual(json.loads(Path(d, "x.json").read_text()), {"a": 1})


class Frozen(unittest.TestCase):
    def test_no_state_file_lands_while_a_copy_is_taken(self):
        import threading
        import time
        d = tempfile.mkdtemp()
        f = os.path.join(d, "x.json")
        statefile.write_json(f, {"n": 1})
        landed = []

        def writer():
            statefile.write_json(f, {"n": 2})
            landed.append(time.monotonic())
        with statefile.frozen():
            t = threading.Thread(target=writer)
            t.start()
            time.sleep(0.2)
            self.assertEqual(json.loads(Path(f).read_text()), {"n": 1}, "held while the copy is taken")
            self.assertEqual(landed, [])
            statefile.write_json(os.path.join(d, "mine.json"), {}), "the thread taking the copy may still write"
        t.join(5)
        self.assertEqual(json.loads(Path(f).read_text()), {"n": 2}, "and lands once it is over")


class OneLock(unittest.TestCase):
    def test_the_lock_is_the_files_own_and_reentrant(self):
        d = tempfile.mkdtemp()
        lock = statefile.FileLock(lambda: os.path.join(d, "users.json"))
        with lock:
            with lock:
                pass
            self.assertTrue(os.path.exists(os.path.join(d, "users.json.lock")))
        none = statefile.FileLock(lambda: None)
        with none:
            pass


if __name__ == "__main__":
    unittest.main()
