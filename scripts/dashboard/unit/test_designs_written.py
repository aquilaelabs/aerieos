"""Migration 0038 (R205): a design record in an older shape (a language
from before themes, choices and rules kept on the language, notes from
before rules, a page with no rules) is written in today's shape, and reads
as design.py's reader of the old shapes read it on 27 Nov: FROZEN."""
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
import design  # noqa: E402

RECS = json.loads(r'''{"pre_themes": {"language": {"scheme": "nostromo", "colors": {"bg": "#000000", "accent": "#FF0000"}, "more": [{"name": "extra", "hex": "#123456", "means": "a sixth"}], "font": "mono", "rules": "Keep it calm.", "scope": "the app"}, "pages": [{"name": "home", "text": "the first page"}], "next": 2, "by": "you", "at": 5}, "unknown_scheme": {"language": {"scheme": "zzz", "colors": {"ink": "#eeeeee"}}, "pages": []}, "carried": {"language": {"themes": [{"name": "Night", "mode": "dark", "colors": [{"name": "bg", "hex": "#111111"}]}, {"name": "Day", "mode": "light", "colors": [], "corners": "square"}], "corners": "custom", "custom": {"corners": "radii"}, "rules": [{"name": "radii", "text": "Corners are 3px."}]}, "pages": [{"name": "q", "text": "x", "rules": "A page's notes."}]}, "choices_no_theme": {"language": {"density": "compact", "rules": "Notes only."}}, "modern": {"language": {"themes": [{"name": "Default", "mode": "dark", "colors": [{"name": "bg", "hex": "#0d1117"}], "rules": [{"name": "a", "text": "b"}]}], "scope": "s"}, "pages": [{"name": "p", "text": "t", "rules": [{"name": "c", "text": "d"}]}], "next": 3}}''')
# design._record of each on 27 Nov, with the readers of the old shapes in it.
FROZEN = json.loads(r'''{"pre_themes": {"language": {"themes": [{"name": "Nostromo", "mode": "dark", "colors": [{"name": "bg", "hex": "#000000", "means": "the page"}, {"name": "panel", "hex": "#29333c", "means": "a raised box, a card, a bar"}, {"name": "ink", "hex": "#ecf5fd", "means": "the text"}, {"name": "dim", "hex": "#b4c3d2", "means": "secondary text and labels"}, {"name": "line", "hex": "#50606e", "means": "hairlines and borders"}, {"name": "accent", "hex": "#ff0000", "means": "the one color that means \"this is the one\": the active tab, the primary button, a link"}, {"name": "warn", "hex": "#ffd166", "means": "a warning"}, {"name": "bad", "hex": "#ff5f45", "means": "an error, a destructive verb"}, {"name": "note", "hex": "#3da5f9", "means": "an informational mark"}, {"name": "good", "hex": "#9ad07a", "means": "success: a passing check, a legal move, a safe state"}, {"name": "extra", "hex": "#123456", "means": "a sixth"}], "light": [], "rules": [], "font": "mono", "corners": "", "density": "", "motion": "", "fonts": "", "custom": {}}], "scope": "the app"}, "pages": [{"name": "home", "text": "the first page", "rules": []}], "next": 2, "by": "you", "at": 5}, "unknown_scheme": {"language": {"themes": [{"name": "Custom", "mode": "dark", "colors": [{"name": "bg", "hex": "#172136", "means": "the page"}, {"name": "panel", "hex": "#24314b", "means": "a raised box, a card, a bar"}, {"name": "ink", "hex": "#eeeeee", "means": "the text"}, {"name": "dim", "hex": "#b2c2db", "means": "secondary text and labels"}, {"name": "line", "hex": "#455e89", "means": "hairlines and borders"}, {"name": "accent", "hex": "#00c1fd", "means": "the one color that means \"this is the one\": the active tab, the primary button, a link"}, {"name": "warn", "hex": "#d29922", "means": "a warning"}, {"name": "bad", "hex": "#f8524a", "means": "an error, a destructive verb"}, {"name": "note", "hex": "#37a5fb", "means": "an informational mark"}, {"name": "good", "hex": "#56d364", "means": "success: a passing check, a legal move, a safe state"}], "light": [], "rules": [], "font": "", "corners": "", "density": "", "motion": "", "fonts": "", "custom": {}}], "scope": ""}, "pages": [], "next": 1, "by": "", "at": 0}, "carried": {"language": {"themes": [{"name": "Night", "mode": "dark", "colors": [{"name": "bg", "hex": "#111111", "means": ""}], "light": [], "rules": [{"name": "radii", "text": "Corners are 3px.", "words": [], "paths": []}], "font": "", "corners": "custom", "density": "", "motion": "", "fonts": "", "custom": {"corners": "radii"}}, {"name": "Day", "mode": "light", "colors": [], "light": [], "rules": [], "font": "", "corners": "square", "density": "", "motion": "", "fonts": "", "custom": {}}], "scope": ""}, "pages": [{"name": "q", "text": "x", "rules": []}], "next": 1, "by": "", "at": 0}, "choices_no_theme": {"language": {"themes": [{"name": "Default", "mode": "dark", "colors": [], "light": [], "rules": [], "font": "", "corners": "", "density": "compact", "motion": "", "fonts": "", "custom": {}}], "scope": ""}, "pages": [], "next": 1, "by": "", "at": 0}, "modern": {"language": {"themes": [{"name": "Default", "mode": "dark", "colors": [{"name": "bg", "hex": "#0d1117", "means": ""}], "light": [], "rules": [{"name": "a", "text": "b", "words": [], "paths": []}], "font": "", "corners": "", "density": "", "motion": "", "fonts": "", "custom": {}}], "scope": "s"}, "pages": [{"name": "p", "text": "t", "rules": [{"name": "c", "text": "d"}]}], "next": 3, "by": "", "at": 0}}''')


class DesignsWritten(unittest.TestCase):
    def setUp(self):
        self.d = Path(tempfile.mkdtemp())
        self.addCleanup(shutil.rmtree, self.d, True)
        self.f = self.d / "designs.json"
        self.f.write_text(json.dumps(copy.deepcopy(RECS)))
        os.chmod(self.f, 0o600)
        self.run_it = lambda: importlib.import_module("statemigrations.0038_designs_written").run({"state": str(self.d)})

    def test_each_record_reads_as_the_old_reader_read_it(self):
        self.run_it()
        got = json.loads(self.f.read_text())
        self.assertEqual({k: design._record(got, k) for k in RECS}, FROZEN)
        self.assertEqual(self.f.stat().st_mode & 0o777, 0o600)
        lang = got["pre_themes"]["language"]
        self.assertEqual(sorted(lang), ["scope", "themes"], "nothing of the old shape is left on the language")

    def test_it_is_idempotent_and_leaves_a_modern_record_alone(self):
        self.run_it()
        once = self.f.read_text()
        self.run_it()
        self.assertEqual(self.f.read_text(), once)
        self.assertEqual(json.loads(once)["modern"], RECS["modern"])


if __name__ == "__main__":
    unittest.main()
