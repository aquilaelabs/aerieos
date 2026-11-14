"""A release is checked against the files its project lists in
.release-files at the release's tag, and one short of a file is a red row
on the bell naming the file and why (R190 step 4)."""
import json
import os
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path
from unittest import mock

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))
import releasefiles  # noqa: E402
import releasesign  # noqa: E402


def git(d, *a):
    subprocess.run(["git", "-C", str(d), *a], check=True, capture_output=True,
                   env={**os.environ, "GIT_AUTHOR_NAME": "t", "GIT_AUTHOR_EMAIL": "t@t.invalid",
                        "GIT_COMMITTER_NAME": "t", "GIT_COMMITTER_EMAIL": "t@t.invalid"})


class Files(unittest.TestCase):
    def setUp(self):
        self.ws, self.state = Path(tempfile.mkdtemp()), Path(tempfile.mkdtemp())
        d = self.ws / "app"
        d.mkdir()
        git(d, "init", "-q", "-b", "main")
        (d / ".release-files").write_text("# what a release carries\napp-@VER@.tar.gz\napp-@VER@.apk\napp-@VER@-*.iso\n")
        git(d, "add", ".release-files")
        git(d, "commit", "-q", "-m", "list")
        git(d, "tag", "v1.0.0-dev.5")
        # A later list does not change what the tagged release is held to.
        (d / ".release-files").write_text("app-@VER@.tar.gz\napp-@VER@.exe\n")
        git(d, "commit", "-q", "-am", "later")

        def write(f, data):
            Path(f).write_text(json.dumps(data))
        releasefiles.configure(state=self.state, workspace=self.ws, write_json_fn=write)
        releasesign.configure(state=self.state, workspace=self.ws, write_json_fn=write)

    def test_the_list_is_the_tags_with_its_version_filled_in(self):
        self.assertEqual(releasefiles.wanted("app", "v1.0.0-dev.5"),
                         ["app-1.0.0-dev.5.tar.gz", "app-1.0.0-dev.5.apk", "app-1.0.0-dev.5-*.iso"])

    def check(self, have, after=4 * 3600):
        releasefiles.expect("app", "v1.0.0-dev.5")
        with mock.patch.object(releasefiles.forgerelease, "_handle", return_value=("github", "GitHub", None)), \
                mock.patch.object(releasefiles.forgerelease, "_files_on",
                                  return_value=("https://h/r", {n: (1, 1, 1) for n in have})):
            import time
            releasefiles.check("app", now=time.time() + after)
        return releasefiles.attention(["app"])

    def test_a_whole_release_says_nothing(self):
        self.assertEqual(self.check(["app-1.0.0-dev.5.tar.gz", "app-1.0.0-dev.5.apk", "app-1.0.0-dev.5-x.iso"]), [])

    def test_a_missing_apk_is_said_with_why(self):
        rows = self.check(["app-1.0.0-dev.5.tar.gz", "app-1.0.0-dev.5-x.iso"])
        self.assertEqual(len(rows), 1)
        self.assertEqual(rows[0]["files"], ["app-1.0.0-dev.5.apk"])
        self.assertTrue(rows[0]["bad"])
        self.assertIn("has not signed it yet: the space's Signing view", rows[0]["why"])

    def gone_at(self, after):
        import time
        with mock.patch.object(releasefiles.forgerelease, "_handle", return_value=("github", "GitHub", None)), \
                mock.patch.object(releasefiles.forgerelease, "_files_on",
                                  side_effect=releasefiles.forgerelease.NoRelease("there is no release for v1.0.0-dev.5 on GitHub")):
            releasefiles.check("app", now=time.time() + after)
        return releasefiles.attention(["app"])

    def test_a_release_deleted_on_the_git_host_ends_its_watch_and_its_row(self):
        # B780: read once short of a file, then taken away on purpose.
        self.assertEqual(len(self.check(["app-1.0.0-dev.5.tar.gz"])), 1)
        self.assertEqual(self.gone_at(5 * 3600), [])

    def test_and_one_deleted_after_the_watch_gave_up_is_learned_of_within_a_day(self):
        self.assertEqual(len(self.check(["app-1.0.0-dev.5.tar.gz"])), 1)
        self.assertEqual(self.gone_at(4 * 3600 + 5 * 86400), [])

    def test_a_release_never_made_keeps_its_row(self):
        releasefiles.expect("app", "v1.0.0-dev.5")
        rows = self.gone_at(4 * 3600)
        self.assertEqual(len(rows), 1)
        self.assertIn("there is no release", rows[0]["why"])

    def test_nothing_is_checked_before_ci_has_had_its_time(self):
        self.assertEqual(self.check([], after=60), [])

    def test_a_project_with_no_list_is_never_expected(self):
        (self.ws / "bare").mkdir()
        git(self.ws / "bare", "init", "-q")
        releasefiles.expect("bare", "v1.0.0")
        self.assertNotIn("bare", json.loads((self.state / "release-files.json").read_text()) if
                         (self.state / "release-files.json").exists() else {})



class AsCiEnds(unittest.TestCase):
    """The check runs as the tag's runs end (R206 step 6), where it ran
    three hours after the tag whatever CI was doing; a complete release is
    said once, and the app the controller signs is waited for."""
    TAG = "v1.0.0-dev.5"
    ALL = ["app-1.0.0-dev.5.tar.gz", "app-1.0.0-dev.5.apk", "app-1.0.0-dev.5-x.iso"]

    def setUp(self):
        Files.setUp(self)
        self.said = []
        releasefiles.configure(state=self.state, workspace=self.ws,
                               write_json_fn=lambda f, d: Path(f).write_text(json.dumps(d)),
                               said_fn=lambda *a: self.said.append(a))
        self.addCleanup(releasefiles.configure, state=self.state, workspace=self.ws, write_json_fn=None)
        self.runs, self.have, self.draft = [], list(self.ALL), False
        self.no_release = False

        def files_on(*a):
            if self.no_release:
                raise releasefiles.forgerelease.NoRelease("there is no release for v1.0.0-dev.5 on GitHub")
            return "https://h/r", {n: (1, 1, 1) for n in self.have}
        for p in (mock.patch.object(releasefiles, "runs", lambda project, tag: self.runs),
                  mock.patch.object(releasefiles, "_is_draft", lambda project, tag: self.draft),
                  mock.patch.object(releasefiles.forgerelease, "_handle", return_value=("github", "GitHub", None)),
                  mock.patch.object(releasefiles.forgerelease, "_files_on", files_on)):
            p.start()
            self.addCleanup(p.stop)
        releasefiles.expect("app", self.TAG)
        import time
        self.t0 = time.time()

    def at(self, minutes):
        releasefiles.check("app", now=self.t0 + minutes * 60)
        return releasefiles.attention(["app"])

    def run_(self, how="", name="build and push image"):
        return {"name": name, "going": not how, "how": how, "url": "https://h/run/1"}

    def test_while_a_run_is_going_nothing_is_said_however_long_it_takes(self):
        self.runs, self.have = [self.run_()], []
        for minutes in (5, 200, 600):
            self.assertEqual(self.at(minutes), [], f"at {minutes} minutes")
        self.assertEqual(self.said, [])

    def test_a_whole_release_is_said_complete_once_as_its_runs_end(self):
        self.runs = [self.run_()]
        self.at(5)
        self.runs = [self.run_("passed")]
        self.assertEqual(self.at(12), [], "minutes after the tag, not three hours")
        self.assertEqual(self.said, [("app", self.TAG, 3, False)])
        self.at(20)
        self.at(400)
        self.assertEqual(len(self.said), 1, "once")
        self.assertEqual(releasefiles.complete_words("App", self.TAG, 3, False),
                         "v1.0.0-dev.5 of App is complete: every file it must carry is on it (3), and it is published")
        self.assertIn("a draft until its notes are read", releasefiles.complete_words("App", "v1.0.0", 17, True))

    def test_a_file_ci_did_not_attach_names_the_run_that_failed(self):
        self.runs = [self.run_("failed"), self.run_("passed", "publish release")]
        self.have = ["app-1.0.0-dev.5.tar.gz", "app-1.0.0-dev.5.apk"]
        rows = self.at(10)
        self.assertEqual([r["files"] for r in rows], [["app-1.0.0-dev.5-*.iso"]])
        self.assertIn("CI did not attach it: build and push image failed (https://h/run/1)", rows[0]["why"])
        self.assertEqual(self.said, [])
        # Run again and whole: the row goes, and it is said complete.
        self.runs, self.have = [self.run_("passed")], list(self.ALL)
        self.assertEqual(self.at(40), [])
        self.assertEqual(len(self.said), 1)

    def test_a_build_that_failed_before_the_release_was_made_says_so(self):
        self.runs, self.no_release = [self.run_("was canceled")], True
        rows = self.at(15)
        self.assertEqual(len(rows), 1)
        self.assertIn("its build made no release: build and push image was canceled (https://h/run/1)", rows[0]["why"])

    def test_the_app_the_controller_signs_is_waited_for_and_said_if_it_does_not_come(self):
        self.runs, self.have = [self.run_("passed")], ["app-1.0.0-dev.5.tar.gz", "app-1.0.0-dev.5-x.iso"]
        self.assertEqual(self.at(10), [], "on its way: not said at the first look")
        self.assertEqual(self.at(25), [])
        rows = self.at(10 + releasefiles.SIGN_GRACE_S // 60 + 1)
        self.assertEqual([r["files"] for r in rows], [["app-1.0.0-dev.5.apk"]])
        # ...and it coming later ends the row and says the release complete.
        self.have = list(self.ALL)
        self.assertEqual(self.at(60), [])
        self.assertEqual(len(self.said), 1)

    def test_a_signing_that_failed_is_said_at_once(self):
        self.runs, self.have = [self.run_("passed")], ["app-1.0.0-dev.5.tar.gz", "app-1.0.0-dev.5-x.iso"]
        (self.state / "release-signing.json").write_text(json.dumps(
            {"app": {"failed": {self.TAG: {"why": "no sideload key", "at": 1, "run": 2}}}}))
        rows = self.at(10)
        self.assertIn("the controller could not sign it: no sideload key", rows[0]["why"])

    def test_a_tag_that_started_no_run_keeps_the_three_hours(self):
        self.runs, self.have = [], []
        self.assertEqual(self.at(60), [])
        self.assertEqual(len(self.at(181)), 1)


class TheRuns(unittest.TestCase):
    def test_a_tags_runs_are_read_with_how_each_ended(self):
        rows = {"workflow_runs": [
            {"name": "build and push image", "head_branch": "v1.0.0", "status": "in_progress", "conclusion": None, "html_url": "u1"},
            {"name": "publish release", "head_branch": "v1.0.0", "status": "completed", "conclusion": "success", "html_url": "u2"},
            {"name": "old", "head_branch": "v1.0.0", "status": "completed", "conclusion": "cancelled", "html_url": "u3"},
            {"name": "x", "head_branch": "v1.0.0", "status": "completed", "conclusion": "failure", "html_url": "u4"},
            {"name": "another tag's", "head_branch": "v1.0.0-dev.1", "status": "completed", "conclusion": "success"}]}
        asked = []

        def get(path, token):
            asked.append(path)
            return rows
        with mock.patch.object(releasefiles.cilogs, "repo_of", lambda p: "o/app"), \
                mock.patch.object(releasefiles.cilogs, "_token", lambda p: "tok"), \
                mock.patch.object(releasefiles.cilogs, "_get", get):
            got = releasefiles.runs("app", "v1.0.0")
        self.assertEqual(asked, ["/repos/o/app/actions/runs?branch=v1.0.0&per_page=50"])
        self.assertEqual([(r["name"], r["going"], r["how"]) for r in got],
                         [("build and push image", True, ""), ("publish release", False, "passed"),
                          ("old", False, "was canceled"), ("x", False, "failed")])
        # Not on GitHub, or no token: cannot be read, and the three hours stand.
        with mock.patch.object(releasefiles.cilogs, "repo_of", lambda p: ""):
            self.assertIsNone(releasefiles.runs("app", "v1.0.0"))


if __name__ == "__main__":
    unittest.main()
