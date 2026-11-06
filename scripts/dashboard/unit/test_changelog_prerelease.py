"""changelog.roll with pre-releases: a pre-release of any name takes
Unreleased as its own section, and a stable release gathers every
pre-release section since the last stable one with Unreleased."""
import os
import sys
import tempfile
import unittest

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))
import changelog  # noqa: E402

FILE = """# Changelog

## Unreleased

### Fixed

- C (ccc1111)

## 1.1.0-rc.1: 2026-01-02

### Added

- B (bbb1111)

### Fixed

- Only in a pre-release (ddd1111)

## 1.1.0-dev.5: 2026-01-01

### Added

- A (aaa1111)
- B (bbb2222)

## 1.0.0: 2025-12-01

### Added

- Old (0001111)
"""


class PreRelease(unittest.TestCase):
    def setUp(self):
        self.d = tempfile.mkdtemp()
        self.write(FILE)

    def write(self, text):
        with open(os.path.join(self.d, changelog.FILE), "w") as f:
            f.write(text)

    def text(self):
        with open(os.path.join(self.d, changelog.FILE)) as f:
            return f.read()

    def test_titles(self):
        for t in ("1.2.0-dev.4951", "1.2.0-rc.2: 2026-01-01", "1.2.0-beta", "1.2.0-nightly.7 2026"):
            self.assertTrue(changelog.is_pre(t), t)
        for t in ("1.2.0", "1.2.0: 2026-01-01", "Unreleased"):
            self.assertFalse(changelog.is_pre(t), t)
        self.assertEqual(changelog.since_stable(FILE), ["1.1.0-rc.1: 2026-01-02", "1.1.0-dev.5: 2026-01-01"])

    def test_pre_release_takes_unreleased(self):
        self.assertTrue(changelog.roll(self.d, "1.1.0-beta.1", "2026-01-03"))
        t = self.text()
        self.assertIn("## 1.1.0-beta.1: 2026-01-03\n\n### Fixed\n\n- C (ccc1111)", t)
        self.assertNotIn("## Unreleased", t)
        self.assertIn("## 1.1.0-rc.1: 2026-01-02", t)

    def test_stable_gathers_since_the_last_stable(self):
        self.assertTrue(changelog.roll(self.d, "1.1.0", "2026-01-04",
                                       keep=lambda e: e["text"] != "Only in a pre-release"))
        t = self.text()
        want = ("## 1.1.0: 2026-01-04\n\n### Added\n\n- A (aaa1111)\n- B (bbb2222, bbb1111)\n\n"
                "### Fixed\n\n- C (ccc1111)\n\n## 1.0.0: 2025-12-01")
        self.assertIn(want, t)
        self.assertNotIn("rc.1", t)
        self.assertNotIn("dev.5", t)
        self.assertNotIn("Only in a pre-release", t)

    def test_stable_with_nothing_unreleased_still_gathers(self):
        self.write(FILE.replace("## Unreleased\n\n### Fixed\n\n- C (ccc1111)\n\n", ""))
        self.assertTrue(changelog.roll(self.d, "1.1.0", "2026-01-04"))
        self.assertIn("## 1.1.0: 2026-01-04\n\n### Added\n\n- A (aaa1111)", self.text())

    def test_nothing_to_roll(self):
        self.write("# Changelog\n\n## 1.0.0: 2025-12-01\n\n- Old\n")
        self.assertFalse(changelog.roll(self.d, "1.1.0-dev.9", "2026-01-04"))
        self.assertFalse(changelog.roll(self.d, "1.1.0", "2026-01-04"))


if __name__ == "__main__":
    unittest.main()
