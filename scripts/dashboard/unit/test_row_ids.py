"""A row whose new id is already in its table goes in under another (R242;
the audit of 13 Nov): ids are 32 bits, an audit of two hundred thousand rows
meets one about every twenty thousand inserts, and the row was dropped with
a line in the log; a job that met one was an error to whoever asked."""
import os
import shutil
import sqlite3
import sys
import tempfile
import unittest
from unittest import mock

sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)), ".."))
import db  # noqa: E402


class RowIds(unittest.TestCase):
    def setUp(self):
        self.st = tempfile.mkdtemp()
        self.addCleanup(shutil.rmtree, self.st, True)
        db.configure(state=self.st)
        db.migrate()

    def ids(self):
        return [r["id"] for r in db._rows("SELECT id FROM audit ORDER BY rowid")]

    def test_an_audit_row_that_meets_an_id_goes_in_under_the_next(self):
        handed = iter(["a_00000001", "a_00000001", "a_00000001", "a_00000002"])
        with mock.patch.object(db, "mint", lambda prefix: next(handed)):
            db.audit("user:ann", "one", "alpha", {})
            db.audit("user:ann", "two", "alpha", {})
        self.assertEqual(self.ids(), ["a_00000001", "a_00000002"])
        self.assertEqual([r["action"] for r in db._rows("SELECT action FROM audit ORDER BY rowid")], ["one", "two"])

    def test_it_gives_up_after_a_few_and_only_a_taken_id_is_tried_again(self):
        db.audit("user:ann", "one", "alpha", {})
        taken = self.ids()[0]
        calls = []

        def put(rid):
            calls.append(rid)
            db._exec("INSERT INTO audit (id, at, principal, action, target, params) VALUES (?, 0, '', '', '', '')", (rid,))
        with mock.patch.object(db, "mint", lambda prefix: taken), self.assertRaises(sqlite3.IntegrityError):
            db.minted("a", put, tries=4)
        self.assertEqual(len(calls), 4)
        # Any other refusal is not an id's: said at once, never tried again.
        calls.clear()

        def bad(rid):
            calls.append(rid)
            db._exec("INSERT INTO audit (id, at, principal, action, target, params) VALUES (?, NULL, '', '', '', '')", (rid,))
        with self.assertRaises(sqlite3.IntegrityError):
            db.minted("a", bad)
        self.assertEqual(len(calls), 1)
        self.assertEqual(self.ids(), [taken])


if __name__ == "__main__":
    unittest.main()
