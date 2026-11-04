"""A dev build's notes are what Unreleased gained since the tag before (the
operator, 1 Nov), where each release repeated the whole section."""
import importlib.util
import os
import subprocess
import tempfile
import unittest

HERE = os.path.dirname(os.path.abspath(__file__))
spec = importlib.util.spec_from_file_location("release_notes", os.path.join(HERE, "..", "..", "..", "tools", "release-notes.py"))
rn = importlib.util.module_from_spec(spec)
spec.loader.exec_module(rn)
OLD = "# Changelog\n\n## Unreleased\n\n### Added\n\n- One (abc1234)\n\n### Fixed\n\n- Two\n\n## 0.8.0: 2026-01-01\n\n### Added\n\n- Old\n"
NEW = "# Changelog\n\n## Unreleased\n\n### Added\n\n- One (def5678)\n- Three (abc1234)\n\n### Fixed\n\n- Two\n\n### Upgrading\n\n- Four\n\n## 0.8.0: 2026-01-01\n\n### Added\n\n- Old\n"


class Notes(unittest.TestCase):
    def test_only_what_is_new_under_its_heading(self):
        got = rn.notes(NEW, OLD, "v1.0.0-dev.1")
        self.assertEqual(got, "What changed since v1.0.0-dev.1.\n\n### Added\n\n- Three (abc1234)\n\n### Upgrading\n\n- Four\n")
        self.assertNotIn("- One", got, "a line is the same whatever commit it names")
        self.assertNotIn("Old", got, "nothing from a dated section")

    def test_nothing_new_is_said_and_no_tag_before_is_all(self):
        self.assertIn("Nothing a person would see", rn.notes(OLD, OLD, "v1"))
        # ...and where the commits are read, since the build is not empty.
        self.assertIn("[the commits](https://x/compare/v1...v2) say what moved", rn.notes(OLD, OLD, "v1", "https://x/compare/v1...v2"))
        self.assertIn("- One", rn.notes(OLD, "", ""))

    def test_from_the_tags_in_git(self):
        with tempfile.TemporaryDirectory() as d:
            def g(*a):
                subprocess.run(["git", "-c", "user.name=t", "-c", "user.email=t@t", "-c", "tag.gpgsign=false", *a], cwd=d, check=True, capture_output=True)
            g("init", "-q", "-b", "main")
            for text, tag in ((OLD, "v1.0.0-dev.1"), (NEW, "v1.0.0-dev.2")):
                with open(os.path.join(d, "CHANGELOG.md"), "w") as f:
                    f.write(text)
                g("add", "CHANGELOG.md")
                g("commit", "-qm", tag)
                g("tag", tag)
            tool = os.path.join(HERE, "..", "..", "..", "tools", "release-notes.py")
            r = subprocess.run(["python3", os.path.abspath(tool), "v1.0.0-dev.2"], cwd=d, capture_output=True, text=True, check=True)
            self.assertIn("since v1.0.0-dev.1", r.stdout)
            self.assertIn("- Three", r.stdout)
            self.assertNotIn("- Two", r.stdout)
            # A tag nobody saw published is not what this one is compared with.
            here = os.getcwd()
            os.chdir(d)
            try:
                self.assertEqual(rn.since_of("v1.0.0-dev.2", {"v1.0.0-dev.1"}), "v1.0.0-dev.1")
                self.assertEqual(rn.since_of("v1.0.0-dev.2", set()), "", "nothing published before: every line")
                self.assertEqual(rn.since_of("v1.0.0-dev.2", None), "v1.0.0-dev.1")
            finally:
                os.chdir(here)


if __name__ == "__main__":
    unittest.main()
