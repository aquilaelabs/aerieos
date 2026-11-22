"""Migration 0030: a house rule written when the command was called bb says
aerie, in its words, its reason, its check and what it refuses, and nothing
that only looks like the old name changes."""
import importlib
import json
import os
import shutil
import sys
import tempfile
import unittest

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))
mig = importlib.import_module("statemigrations.0030_rules_say_aerie")


class RulesSayAerie(unittest.TestCase):
    def setUp(self):
        self.dir = tempfile.mkdtemp(prefix="rules-aerie-")
        self.addCleanup(shutil.rmtree, self.dir, True)
        self.f = os.path.join(self.dir, "rules.json")

    def write(self, d):
        with open(self.f, "w") as f:
            json.dump(d, f)
        os.chmod(self.f, 0o600)

    def read(self):
        with open(self.f) as f:
            return json.load(f)

    def test_each_field_says_aerie_and_lookalikes_stay(self):
        self.write({"projects": {"web": {"rules": [
            {"name": "tests", "text": "Run `bb tests run`, or bb dashboard test FILE; bb -p other roadmap too.",
             "why": "bb lint is the set CI runs", "check": "bb rules check voice",
             "refuse": ["bb git push --force", "apt install"], "by": "claude"},
            {"name": "hosts", "text": "bb-sandbox runs it; bb_setting reads it; the bb label stays; a bbb test; dbb tests."}]},
            "__global__": {"disabled": ["x"]}}, "other": 1})
        mig.run({"state": self.dir})
        r = self.read()
        got = r["projects"]["web"]["rules"]
        self.assertEqual(got[0]["text"], "Run `aerie tests run`, or aerie dashboard test FILE; aerie -p other roadmap too.")
        self.assertEqual(got[0]["why"], "aerie lint is the set CI runs")
        self.assertEqual(got[0]["check"], "aerie rules check voice")
        self.assertEqual(got[0]["refuse"], ["aerie git push --force", "apt install"])
        self.assertEqual(got[1]["text"], "bb-sandbox runs it; bb_setting reads it; the bb label stays; a bbb test; dbb tests.")
        self.assertEqual(r["other"], 1)
        self.assertEqual(r["projects"]["__global__"], {"disabled": ["x"]})
        self.assertEqual(os.stat(self.f).st_mode & 0o777, 0o600)
        before = os.stat(self.f).st_mtime_ns
        mig.run({"state": self.dir})   # again: as it left it, not written
        self.assertEqual(os.stat(self.f).st_mtime_ns, before)

    def test_no_file_or_an_unreadable_one_is_left(self):
        mig.run({"state": self.dir})
        self.assertFalse(os.path.exists(self.f))
        with open(self.f, "w") as f:
            f.write("{not json")
        mig.run({"state": self.dir})
        with open(self.f) as f:
            self.assertEqual(f.read(), "{not json")


if __name__ == "__main__":
    unittest.main()
