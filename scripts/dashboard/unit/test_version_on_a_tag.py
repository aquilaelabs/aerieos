"""A build of a pre-release's tag reports what the tag says (R206 step 9;
R217's one clock for every name). The image's workflow stamped the tag's own
words in shell while `aerie version` said X.Y.Z-dev.N+sha of the same commit,
and read a release candidate's tag as a dev build; the workflow asks the tool
now, so the tool has to know the tag. In a scratch repository."""
import os
import shutil
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path
from unittest import mock

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))
import version  # noqa: E402

GIT_ENV = {"GIT_AUTHOR_NAME": "t", "GIT_AUTHOR_EMAIL": "t@example.com",
           "GIT_COMMITTER_NAME": "t", "GIT_COMMITTER_EMAIL": "t@example.com"}


class OnATag(unittest.TestCase):
    def setUp(self):
        self.ws = Path(tempfile.mkdtemp())
        self.addCleanup(shutil.rmtree, self.ws, ignore_errors=True)
        p = mock.patch.object(version.time, "sleep", lambda s: None)
        p.start()
        self.addCleanup(p.stop)
        st = self.ws / ".state"
        st.mkdir()
        version.configure(workspace=self.ws, state=st, write_json=lambda *_a, **_k: None)
        self.app = self.ws / "app"
        (self.app / "ext").mkdir(parents=True)
        self.git("init", "-q", "-b", "main")
        (self.app / "VERSION").write_text("1.2.0\n")
        (self.app / "ext" / "VERSION").write_text("0.3.0\n")
        self.git("add", "-A")
        self.git("commit", "-q", "-m", "start")
        (self.app / "a.txt").write_text("a\n")
        self.git("add", "-A")
        self.git("commit", "-q", "-m", "two")
        self.sha = self.git("rev-parse", "--short=7", "HEAD")
        e = mock.patch.dict(os.environ, {}, clear=False)
        e.start()
        self.addCleanup(e.stop)
        os.environ.pop("BB_VERSION_TAG", None)

    def git(self, *a):
        r = subprocess.run(["git", "-C", str(self.app), *a], capture_output=True, text=True,
                           env={**os.environ, **GIT_ENV}, check=True)
        return r.stdout.strip()

    def forms(self, comp=""):
        return version.render("app", comp)["forms"]

    def test_no_tag_is_a_dev_build_with_its_commit(self):
        f = self.forms()
        self.assertEqual(f["semver"], f"1.2.0-dev.2+{self.sha}")
        self.assertEqual(f["file"], f"1.2.0-dev.2-{self.sha}")

    def test_a_dev_tag_and_a_release_candidates_are_what_they_say(self):
        self.git("tag", "v1.2.0-dev.2")
        f = self.forms()
        self.assertEqual((f["semver"], f["file"], f["pep440"]), ("1.2.0-dev.2", "1.2.0-dev.2", "1.2.0.dev2"))
        # The forms Windows compares stay a build's, by the ordinal.
        self.assertEqual((f["code"], f["quad"], f["msi"]), ("2", "1.2.0.2", "1.2.2"))
        self.assertFalse(version.parts("app")["released"], "a pre-release is not the release")
        self.git("tag", "-d", "v1.2.0-dev.2")
        self.git("tag", "-a", "v1.2.0-rc.2", "-m", "rc")
        f = self.forms()
        self.assertEqual((f["semver"], f["file"], f["pep440"]), ("1.2.0-rc.2", "1.2.0-rc.2", "1.2.0rc2"))
        self.git("tag", "-d", "v1.2.0-rc.2")
        self.git("tag", "v1.2.0-nightly.2")
        self.assertEqual(self.forms()["pep440"], "1.2.0.dev2+nightly")

    def test_an_uncommitted_change_on_the_tag_is_said(self):
        self.git("tag", "v1.2.0-dev.2")
        (self.app / "a.txt").write_text("changed\n")
        f = self.forms()
        self.assertEqual((f["semver"], f["file"], f["pep440"]), ("1.2.0-dev.2+dirty", "1.2.0-dev.2-dirty", "1.2.0.dev2+dirty"))

    def test_several_tags_on_one_commit(self):
        self.git("tag", "v1.2.0-dev.2")
        self.git("tag", "v1.2.0-rc.2")
        self.assertEqual(self.forms()["semver"], "1.2.0-rc.2", "a named pre-release before a dev build's")
        # The tag a build was started for, where its workflow names it.
        os.environ["BB_VERSION_TAG"] = "v1.2.0-dev.2"
        self.assertEqual(self.forms()["semver"], "1.2.0-dev.2")
        os.environ["BB_VERSION_TAG"] = "v9.9.9-dev.2"
        self.assertEqual(self.forms()["semver"], "1.2.0-rc.2", "a tag that is not on this commit names nothing")
        os.environ.pop("BB_VERSION_TAG")
        # The release's own tag is the release, whatever else is here.
        self.git("tag", "v1.2.0")
        self.assertEqual(self.forms()["semver"], "1.2.0")
        self.assertTrue(version.parts("app")["released"])

    def test_a_tag_for_the_line_the_branch_works_toward(self):
        # A branch working toward 1.3.0 tags v1.3.0-dev.N while VERSION says
        # 1.2.0; a tag's workflow checks out no branch, and still says the tag.
        self.git("tag", "v1.3.0-dev.2")
        self.git("checkout", "-q", "--detach", "HEAD")
        self.assertEqual(self.forms()["semver"], "1.3.0-dev.2")

    def test_a_components_tag_is_its_own(self):
        self.git("tag", "v1.2.0-dev.2")
        self.assertIn("-dev.", self.forms("ext")["semver"])
        self.assertIn("+", self.forms("ext")["semver"], "the tree's tag says nothing of the component")
        n = self.forms("ext")["code"]
        self.git("tag", f"ext-v0.3.0-rc.{n}")
        self.assertEqual(self.forms("ext")["semver"], f"0.3.0-rc.{n}")
        self.assertEqual(self.forms()["semver"], "1.2.0-dev.2")

    def test_what_is_not_a_pre_release_tag(self):
        for t in ("v1.2.0-dev", "v1.2.0-Dev.2", "1.2.0-dev.2", "v1.2-dev.2", "nightly", "v1.2.0-dev.2-extra"):
            self.assertEqual(version.pre_on_head([t], "1.2.0"), "", t)
        self.assertEqual(version.pre_on_head(["ext-v1.2.0-dev.2"], "1.2.0"), "")
        self.assertEqual(version.pre_on_head(["ext-v1.2.0-dev.2"], "1.2.0", "ext"), "1.2.0-dev.2")


if __name__ == "__main__":
    unittest.main()
