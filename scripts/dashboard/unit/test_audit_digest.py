"""The audit's digest of a mutation's parameters is keyed by the install's
own key (B726): a plain sha256 of a body holding one short secret could be
guessed offline by anyone reading the audit; keyed, the same parameters
still read as the same digest on this install."""
import hashlib
import json
import os
import shutil
import sys
import tempfile
import unittest

sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)), ".."))
import db  # noqa: E402


class AuditDigest(unittest.TestCase):
    def setUp(self):
        self.st = tempfile.mkdtemp()
        self.addCleanup(shutil.rmtree, self.st, True)
        db.configure(state=self.st)
        db.migrate()

    def digests(self):
        return [r["params"] if isinstance(r, dict) else r[0] for r in db._rows("SELECT params FROM audit ORDER BY rowid")]

    def test_keyed_and_steady(self):
        params = {"password": "hunter2"}
        db.audit("user:ann", "signing-backup", "alpha", params)
        db.audit("user:ann", "signing-backup", "alpha", params)
        a, b = self.digests()
        self.assertEqual(a, b, "the same parameters, the same digest")
        plain = hashlib.sha256(json.dumps(params, sort_keys=True).encode()).hexdigest()[:12]
        self.assertNotIn(plain, a, "never the plain hash")
        self.assertTrue(a.startswith("mac:"))
        key = os.path.join(self.st, ".audit-key")
        self.assertEqual(os.stat(key).st_mode & 0o777, 0o600)
        self.assertEqual(len(open(key, "rb").read()), 32)


if __name__ == "__main__":
    unittest.main()
