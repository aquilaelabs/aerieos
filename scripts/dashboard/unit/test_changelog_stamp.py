"""changelog.add: a line that names its own commit keeps that stamp alone."""
import os
import sys
import tempfile
import unittest

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))
import changelog  # noqa: E402


class Stamp(unittest.TestCase):
    def setUp(self):
        self.d = tempfile.mkdtemp()

    def line(self):
        with open(os.path.join(self.d, changelog.FILE)) as f:
            return [x for x in f.read().splitlines() if x.startswith("- ")][-1]

    def test_own_stamp_kept_alone(self):
        changelog.add(self.d, "A fix written later (1234abc)", sha="9999fff", cat="Fixed")
        self.assertEqual(self.line(), "- A fix written later (1234abc)")

    def test_head_used_when_none_named(self):
        changelog.add(self.d, "A change", sha="9999fff", cat="Added")
        self.assertEqual(self.line(), "- A change (9999fff)")

    def test_head_named_once(self):
        changelog.add(self.d, "A change (9999fff)", sha="9999fff", cat="Added")
        self.assertEqual(self.line(), "- A change (9999fff)")


if __name__ == "__main__":
    unittest.main()
