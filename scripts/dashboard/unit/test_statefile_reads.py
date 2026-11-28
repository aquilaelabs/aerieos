"""A state file is read once while it stays the same file:
statefile.read_text and read_json keep its text by what the file is on disk,
a request looks at it once, and nothing a caller does to its copy reaches
another's."""
import builtins
import os
import sys
import tempfile
import unittest

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, os.path.join(HERE, ".."))
import statefile  # noqa: E402


class Reads(unittest.TestCase):
    def setUp(self):
        self.dir = tempfile.mkdtemp()
        self.path = os.path.join(self.dir, "thing.json")
        statefile.write_json(self.path, {"n": 1})
        self.opens = 0
        real = builtins.open

        def counting(f, *a, **k):
            if str(f) == self.path:
                self.opens += 1
            return real(f, *a, **k)
        builtins.open = counting
        self.addCleanup(setattr, builtins, "open", real)
        self.addCleanup(statefile.end_request)

    def settle(self):
        # Counted as still at once: the racy window (statefile.RACY_NS) is the
        # one test of its own below, and utime cannot age a file's ctime.
        was = statefile.RACY_NS
        statefile.RACY_NS = 0
        self.addCleanup(setattr, statefile, "RACY_NS", was)

    def test_a_still_file_is_read_once(self):
        self.settle()
        self.assertEqual(statefile.read_json(self.path), {"n": 1})
        before = self.opens
        for _ in range(5):
            self.assertEqual(statefile.read_json(self.path), {"n": 1})
        self.assertEqual(self.opens, before)

    def test_a_write_through_here_is_read_at_once(self):
        self.settle()
        statefile.read_json(self.path)
        statefile.write_json(self.path, {"n": 2})
        self.assertEqual(statefile.read_json(self.path), {"n": 2})

    def test_a_file_just_changed_never_matches_what_was_kept(self):
        # A filesystem whose clock moves in ticks leaves inode, size and times
        # as they were after a write in place of the same size within a tick:
        # a file changed within the racy window is never the same file twice,
        # so it is read again until it has been still that long.
        self.assertNotEqual(statefile.sig(self.path), statefile.sig(self.path))
        self.settle()
        self.assertEqual(statefile.sig(self.path), statefile.sig(self.path))

    def test_each_caller_has_its_own_copy(self):
        self.settle()
        a = statefile.read_json(self.path) or {}
        a["n"] = 99
        self.assertEqual(statefile.read_json(self.path), {"n": 1})

    def test_a_request_looks_once_and_sees_its_own_writes(self):
        statefile.begin_request()
        statefile.read_json(self.path)
        before = self.opens
        statefile.read_json(self.path)
        statefile.read_json(self.path)
        self.assertEqual(self.opens, before)
        self.assertEqual(statefile.writes_here(), statefile.writes_here())
        wrote = statefile.writes_here()
        statefile.write_json(self.path, {"n": 4})
        self.assertEqual(statefile.writes_here(), wrote + 1)
        self.assertEqual(statefile.read_json(self.path), {"n": 4})

    def test_a_missing_file_is_the_default(self):
        self.assertEqual(statefile.read_json(os.path.join(self.dir, "none.json"), {"x": 0}), {"x": 0})


if __name__ == "__main__":
    unittest.main()
