"""db.script: a numbered migration's SQL (statemigrations/NNNN_*.sql, R295)
run in one transaction, all of it or none."""
import os
import shutil
import sqlite3
import sys
import tempfile
import unittest

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, os.path.join(HERE, ".."))
import db  # noqa: E402


class Script(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.mkdtemp(prefix="dbscript-")
        self.addCleanup(shutil.rmtree, self.tmp, True)
        db.configure(state=os.path.join(self.tmp, "state"))

    def test_all_of_it_or_none(self):
        # Statements apart by a blank line, migrations/0001's contract.
        db.script("CREATE TABLE kept (x INTEGER);\n\nINSERT INTO kept (x) VALUES (1);\n")
        self.assertEqual(db._rows("SELECT x FROM kept"), [{"x": 1}])
        with self.assertRaises(sqlite3.Error):
            db.script("INSERT INTO kept (x) VALUES (2);\n\nINSERT INTO nowhere (x) VALUES (3);\n")
        self.assertEqual(db._rows("SELECT x FROM kept"), [{"x": 1}], "the half that ran is rolled back")


if __name__ == "__main__":
    unittest.main()
