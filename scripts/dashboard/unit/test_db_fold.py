"""The write-ahead log folded into the database (B654): after fold() the
-wal file is empty and the rows are in the database file itself, read by
a connection that never sees the log."""
import os
import shutil
import sqlite3
import sys
import tempfile
import unittest

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, os.path.join(HERE, ".."))
import db  # noqa: E402


class Fold(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.mkdtemp(prefix="dbfold-")
        db.configure(state=os.path.join(self.tmp, "state"))
        self.file = os.path.join(self.tmp, "state", "builderbot.db")

    def tearDown(self):
        shutil.rmtree(self.tmp, ignore_errors=True)

    def test_fold_empties_the_log_and_keeps_the_rows(self):
        for i in range(50):
            db.audit("test", "fold", f"row{i}", {"i": i})
        wal = self.file + "-wal"
        self.assertGreater(os.path.getsize(wal), 0, "the writes sit in the log before a fold")
        busy, frames, folded = db.fold()
        self.assertEqual(busy, 0)
        self.assertEqual(frames, folded)
        self.assertEqual(os.path.getsize(wal), 0, "a fold cuts the log back to nothing")
        # The file alone: a copy opened with no log beside it has every row.
        copy = os.path.join(self.tmp, "copy.db")
        shutil.copyfile(self.file, copy)
        c = sqlite3.connect(copy)
        try:
            n = c.execute("SELECT count(*) FROM audit WHERE action = 'fold'").fetchone()[0]
        finally:
            c.close()
        self.assertEqual(n, 50)

    def test_checkpoint_is_the_fold(self):
        db.audit("test", "fold", "one", {})
        db.checkpoint()
        self.assertEqual(os.path.getsize(self.file + "-wal"), 0)


if __name__ == "__main__":
    unittest.main()
