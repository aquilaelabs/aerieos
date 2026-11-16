"""The code map's index is two files since format 5 (R228 step 16): what each
file calls and passes by name in a file of its own, read only when a
question asks for it, and the rule hook asks for several names at once."""
import builtins
import json
import os
import shutil
import sys
import tempfile
import unittest

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, os.path.join(HERE, "..", "..", "lib"))
import codemap  # noqa: E402
import rulehook  # noqa: E402


class Split(unittest.TestCase):
    def setUp(self):
        self.root = tempfile.mkdtemp()
        self.addCleanup(shutil.rmtree, self.root, True)
        with open(os.path.join(self.root, "a.py"), "w") as f:
            f.write("def f():\n    return g()\n\n\ndef g():\n    return 1\n")
        codemap.build(self.root)
        self.calls = os.path.join(self.root, codemap.INDEX_DIR, codemap.CALLS_FILE)

    def test_the_calls_are_a_file_of_their_own(self):
        with open(os.path.join(self.root, codemap.INDEX_DIR, codemap.INDEX_FILE)) as f:
            core = json.load(f)
        self.assertNotIn("calls", core["files"]["a.py"])
        with open(self.calls) as f:
            self.assertIn("calls", json.load(f)["files"]["a.py"])

    def test_a_definition_is_found_without_opening_the_calls(self):
        opened = []
        real = builtins.open

        def watch(f, *a, **k):
            opened.append(str(f))
            return real(f, *a, **k)
        builtins.open = watch
        self.addCleanup(setattr, builtins, "open", real)
        idx = codemap.load(self.root)
        self.assertTrue(codemap.q_find(idx, "g", self.root))
        self.assertFalse(any(p.endswith(codemap.CALLS_FILE) for p in opened))
        # ...while a question about callers reads them.
        self.assertIn(("g", "f"), {(c["name"], c["caller"]) for c in idx["calls"]})

    def test_calls_from_another_build_are_not_trusted(self):
        with open(self.calls) as f:
            got = json.load(f)
        got["built"] = 1
        got["files"]["a.py"]["calls"] = []
        with open(self.calls, "w") as f:
            json.dump(got, f)
        idx = codemap.load(self.root)
        self.assertIn(("g", "f"), {(c["name"], c["caller"]) for c in idx["calls"]})


class Answers(unittest.TestCase):
    def test_several_names_are_split_by_the_line_that_asks(self):
        out = ("$ aerie map find one\na.py:1 to 2  def\n    says: it\n"
               "$ aerie map find two\nnothing defines two\n")
        self.assertEqual(rulehook.find_answers(["one", "two", "three"], out),
                         [("one", ["a.py:1 to 2  def", "    says: it"]), ("two", ["nothing defines two"]),
                          ("three", [])])

    def test_one_name_is_the_whole_answer(self):
        self.assertEqual(rulehook.find_answers(["one"], "a.py:1 to 2  def\n"), [("one", ["a.py:1 to 2  def"])])


if __name__ == "__main__":
    unittest.main()
