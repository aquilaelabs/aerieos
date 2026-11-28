"""Migration 0037: a repository record from before it named the dials
it sets apart is given the list, made as prefs.py's reader made it
from the values stored, which on 26 Nov read as FROZEN."""
import copy
import importlib
import json
import os
import shutil
import sys
import tempfile
import unittest
from pathlib import Path

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))
import prefs  # noqa: E402

RECS = {"a": {"devbuild": "auto", "sign": "ask", "gate": {"roadmap": "deny", "wiki": "hidden", "bugs": "auto", "rules": "nonsense"}},
        "b": {"overrides": ["kube"], "kube": "auto"}, "c": {}, "d": {"test_node": "n_1", "report": "auto", "pc": "ask"}}
# prefs._overrides_of of each record on 26 Nov, with the reader of the old shape in it.
FROZEN = {"a": ["devbuild", "gate.roadmap", "gate.wiki"], "b": ["kube"], "c": [], "d": ["pc", "test_node"]}


class OverridesWritten(unittest.TestCase):
    def test_each_record_names_what_it_set_apart_as_it_was_read(self):
        d = Path(tempfile.mkdtemp())
        self.addCleanup(shutil.rmtree, d, True)
        f = d / "claude-prefs.json"
        f.write_text(json.dumps({"projects": copy.deepcopy(RECS), "users": {"u": 1}}))
        os.chmod(f, 0o600)
        importlib.import_module("statemigrations.0037_overrides_written").run({"state": str(d)})
        got = json.loads(f.read_text())
        self.assertEqual({n: prefs._overrides_of(r) for n, r in got["projects"].items()}, FROZEN)
        self.assertTrue(all(isinstance(r.get("overrides"), list) for r in got["projects"].values()))
        self.assertEqual((got["users"], f.stat().st_mode & 0o777), ({"u": 1}, 0o600))


if __name__ == "__main__":
    unittest.main()
