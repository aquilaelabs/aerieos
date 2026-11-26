"""A browser's sign-in held to that browser (R158 step 8, R288): another
browser's cookie is refused, and so is one sent with no User-Agent at all
once the sign-in is bound, where a stolen cookie sent bare used to pass."""
import os
import sys
import tempfile
import unittest
from pathlib import Path

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))
import logins  # noqa: E402

FIREFOX = "Mozilla/5.0 (X11; Linux x86_64; rv:140.0) Gecko/20100101 Firefox/140.0"
CHROME = "Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/141.0 Safari/537.36"


class Bound(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        logins.configure(state=Path(self.tmp.name))

    def test_held_to_its_browser(self):
        lid = logins.mint("u1", "web", ua=FIREFOX, ip="10.0.0.2")
        self.assertTrue(logins.seen("u1", lid, FIREFOX))
        self.assertFalse(logins.seen("u1", lid, CHROME), "another browser's")
        self.assertFalse(logins.seen("u1", lid, ""), "a bare request, once bound")
        self.assertTrue(logins.seen("u1", lid, FIREFOX), "and its own still")


if __name__ == "__main__":
    unittest.main()
