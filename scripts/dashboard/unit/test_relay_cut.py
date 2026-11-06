"""bbrelay._cut: a relayed verb's output comes back whole up to OUT_MAX, and a
cut is said on stderr rather than handing back a document missing its start."""
import os
import sys
import unittest

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))
import bbrelay  # noqa: E402


class Cut(unittest.TestCase):
    def test_whole_under_the_cap(self):
        out = "x" * 300_000
        self.assertEqual(bbrelay._cut(out, ""), {"out": out, "err": ""})

    def test_cut_is_said(self):
        r = bbrelay._cut("a" * (bbrelay.OUT_MAX + 5), "before")
        self.assertEqual(len(r["out"]), bbrelay.OUT_MAX)
        self.assertIn("only the last", r["err"])
        self.assertTrue(r["err"].endswith("before"))


if __name__ == "__main__":
    unittest.main()
