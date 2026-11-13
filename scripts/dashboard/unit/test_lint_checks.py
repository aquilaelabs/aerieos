"""aerie lint's own checks (scripts/lib/lint-checks.py), which had no test
(R246; the audit of 13 Nov): the layout check answered 1 for a tracked file
its page does not name and the dispatcher dropped it, so lint printed FAIL
and was clean; and the checks that compare against the newest release took
git's version sort, which puts v0.9.0-dev.5341 above v0.9.0."""
import importlib.util
import os
import shutil
import subprocess
import sys
import tempfile
import unittest

HERE = os.path.dirname(os.path.abspath(__file__))
LIB = os.path.normpath(os.path.join(HERE, "..", "..", "lib"))
TOOL = os.path.join(LIB, "lint-checks.py")
sys.path.insert(0, LIB)
spec = importlib.util.spec_from_file_location("lint_checks_under_test", TOOL)
checks = importlib.util.module_from_spec(spec)
spec.loader.exec_module(checks)


class NewestRelease(unittest.TestCase):
    def test_a_release_is_above_the_pre_releases_that_lead_to_it(self):
        f = checks.newest_release
        self.assertEqual(f(["v0.9.0-dev.5173", "v0.9.0-dev.5341", "v0.9.0"]), "v0.9.0")
        self.assertEqual(f(["v0.9.0-dev.5341", "v0.9.0-dev.5173"]), "v0.9.0-dev.5341")
        self.assertEqual(f(["v0.9.0", "v0.9.0-rc.2", "v0.9.0-dev.9999"]), "v0.9.0")
        # ...and the next version's first build is above the last release.
        self.assertEqual(f(["v0.9.0", "v0.10.0-dev.1", "v0.9.1"]), "v0.10.0-dev.1")
        self.assertEqual(f(["v0.9.2", "v0.9.10"]), "v0.9.10")
        self.assertEqual(f(["vetted", "v1", "nightly"]), "")
        self.assertEqual(f([]), "")


class Verdicts(unittest.TestCase):
    def setUp(self):
        self.d = tempfile.mkdtemp()
        self.addCleanup(shutil.rmtree, self.d, True)
        os.makedirs(os.path.join(self.d, "docs"))
        self.git("init", "-q")

    def git(self, *argv):
        subprocess.run(["git", "-c", "user.name=t", "-c", "user.email=t@t", "-c", "commit.gpgsign=false", *argv],
                       cwd=self.d, capture_output=True, check=True)

    def put(self, rel, text):
        with open(os.path.join(self.d, rel), "w") as f:
            f.write(text)

    def run_check(self, verb):
        p = subprocess.run([sys.executable, TOOL, verb], cwd=self.d, capture_output=True, text=True, check=False)
        return p.returncode, p.stdout

    def test_a_file_the_layout_page_does_not_name_fails_lint(self):
        self.put("docs/layout.md", "The tree:\n\n```\ndocs/layout.md   this page\nREADME.md        the front page\n```\n")
        self.put("README.md", "words\n")
        self.git("add", "-A")
        self.assertEqual(self.run_check("layout")[0], 0)
        self.put("unnamed.py", "x = 1\n")
        self.git("add", "-A")
        rc, said = self.run_check("layout")
        self.assertIn("[FAIL] 1 tracked file(s) docs/layout.md does not name: unnamed.py", said)
        self.assertEqual(rc, 1, "what the check prints is what lint is told")

    def test_every_check_is_one_the_dispatcher_knows(self):
        self.assertEqual(set(checks.CHECKS), {"runner", "xml", "settings", "layout", "hosted", "channels", "shipped",
                                              "formats", "packs", "unraid", "changelog", "dupes"})


# The word AerieOS's own rule keeps to its XML files, spelled here in two
# halves so this file is not itself a finding of that rule.
WORD = "Un" + "raid"


class OwnRules(unittest.TestCase):
    """AerieOS's house rules are for AerieOS's own tree: aerie lint ran its
    Unraid-word, changelog-id and twice-defined checks on every space's
    project."""

    def test_a_spaces_project_is_not_held_to_them(self):
        d = tempfile.mkdtemp()
        self.addCleanup(shutil.rmtree, d, True)

        def git(*argv):
            subprocess.run(["git", "-c", "user.name=t", "-c", "user.email=t@t", "-c", "commit.gpgsign=false", *argv],
                           cwd=d, capture_output=True, check=True)
        git("init", "-q")
        with open(os.path.join(d, "README.md"), "w") as f:
            f.write("# An app\nIt runs on " + WORD + ".\n")
        with open(os.path.join(d, "CHANGELOG.md"), "w") as f:
            f.write("# Changelog\n- Fixed B12 and R7.\n")
        git("add", "-A")
        git("commit", "-qm", "one")
        aerie = os.path.normpath(os.path.join(LIB, "..", "aerie"))
        p = subprocess.run(["bash", aerie, "lint"], cwd=d, capture_output=True, text=True, check=False,
                           env={k: v for k, v in os.environ.items() if not k.startswith(("BB_", "BUILDERBOT_", "DASHBOARD_"))})
        said = p.stdout + p.stderr
        self.assertEqual(p.returncode, 0, said[-600:])
        for own in ("== " + WORD.lower(), "== changelog", "names defined twice", "agent version"):
            self.assertNotIn(own, said)
        self.assertIn("lint:", said)


if __name__ == "__main__":
    unittest.main()
