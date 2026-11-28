"""aerie map show prints a definition whole: each one called NAME,
or the one holding FILE:LINE, headed by where it is and its comment."""
import os
import shutil
import sys
import tempfile
import unittest
from pathlib import Path

sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "..", "lib"))
import codemap  # noqa: E402

PAGE = """// Draw the list.
function draw(el){
  el.textContent = said(1);
}
function said(n){
  return String(n);
}
"""
OTHER = """function draw(){
  return 0;
}
"""


class Show(unittest.TestCase):
    def setUp(self):
        self.d = tempfile.mkdtemp()
        self.addCleanup(shutil.rmtree, self.d, ignore_errors=True)
        Path(self.d, "a.js").write_text(PAGE)
        Path(self.d, "b.js").write_text(OTHER)
        self.idx = codemap.build(self.d)

    def show(self, name, first=False):
        return codemap.q_show(self.idx, name, self.d, first)

    def test_each_definition_by_its_name_whole(self):
        out = self.show("draw")
        heads = [x for x in out if x.startswith("== ")]
        self.assertEqual(len(heads), 2, out)
        self.assertTrue(any(x.startswith("== a.js:2 to 4") for x in heads), out)
        self.assertIn("     3    el.textContent = said(1);", out)
        self.assertTrue(out[-1].startswith("(2 definitions called draw"), out)
        self.assertEqual(len([x for x in self.show("draw", first=True) if x.startswith("== ")]), 1)

    def test_the_one_holding_a_line(self):
        out = self.show("a.js:6")
        self.assertTrue(out[0].startswith("== a.js:5 to 7"), out)
        self.assertIn("     6    return String(n);", out)

    def test_a_miss_names_the_nearest(self):
        out = self.show("sayd")
        self.assertEqual(len(out), 1)
        self.assertTrue(out[0].startswith("nothing defines sayd"), out)
        self.assertIn("said", out[0])


if __name__ == "__main__":
    unittest.main()
