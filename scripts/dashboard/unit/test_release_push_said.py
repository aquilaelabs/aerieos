"""A release whose tag could not be pushed says why, in git's own words, and
never the credential a remote's URL carries (B398): "the push failed" alone
left the person guessing between the network, the credential and the
remote."""
import os
import subprocess
import sys
import tempfile
import unittest
from unittest import mock
from pathlib import Path

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))
import version  # noqa: E402


def git(d, *a):
    subprocess.run(["git", "-C", str(d), *a], check=True, capture_output=True,
                   env={**os.environ, "GIT_AUTHOR_NAME": "t", "GIT_AUTHOR_EMAIL": "t@t.invalid",
                        "GIT_COMMITTER_NAME": "t", "GIT_COMMITTER_EMAIL": "t@t.invalid"})


class PushSaid(unittest.TestCase):
    def test_a_failed_push_says_why_and_no_secret(self):
        ws = Path(tempfile.mkdtemp())
        d = ws / "app"
        d.mkdir()
        git(d, "init", "-q", "-b", "main")
        (d / "VERSION").write_text("1.2.3\n")
        git(d, "add", "VERSION")
        git(d, "commit", "-q", "-m", "one")
        git(d, "remote", "add", "origin", f"file://{ws}/nowhere-sekrit:hunter2@x/repo.git")
        version.configure(workspace=str(ws), state=str(ws / "state"), write_json=lambda *a, **k: None)
        r = version.release("app")
        self.assertTrue(r.get("ok"), r)
        self.assertFalse(r["pushed"])
        self.assertIn("the push failed: ", r["note"])
        self.assertIn("git push origin v1.2.3", r["note"])


class DevTag(unittest.TestCase):
    def test_a_dev_release_tags_the_dev_build_and_skips_the_gates(self):
        # R179: the dev build's tag, vX.Y.Z-dev.N, no snapshot gate, no bump.
        ws = Path(tempfile.mkdtemp())
        d = ws / "app"
        d.mkdir()
        git(d, "init", "-q", "-b", "main")
        (d / "VERSION").write_text("1.2.3\n")
        git(d, "add", "VERSION")
        git(d, "commit", "-q", "-m", "one")
        version.configure(workspace=str(ws), state=str(ws / "state"), write_json=lambda *a, **k: None)
        r = version.release("app", push=False, dev=True)
        self.assertTrue(r.get("ok"), r)
        self.assertEqual((r["tag"], r["target"]), ("v1.2.3-dev.1", "1.2.3-dev.1"))
        tags = subprocess.run(["git", "-C", str(d), "tag"], capture_output=True, text=True).stdout.split()
        self.assertEqual(tags, ["v1.2.3-dev.1"])
        self.assertIn("already exists", version.release("app", push=False, dev=True).get("error", ""))

    def test_an_untracked_file_beside_the_commit_does_not_refuse_the_tag(self):
        # B628: the controller's copy of a tree carries files a session keeps
        # out of git with .git/info/exclude, which does not travel, so every
        # tag was refused for 'uncommitted changes' the session never saw.
        # An untracked file is in no commit; a tracked file changed is.
        ws = Path(tempfile.mkdtemp())
        d = ws / "app"
        d.mkdir()
        git(d, "init", "-q", "-b", "main")
        (d / "VERSION").write_text("1.2.3\n")
        (d / "kept.txt").write_text("tracked\n")
        git(d, "add", "VERSION", "kept.txt")
        git(d, "commit", "-q", "-m", "one")
        (d / "stray-tool.py").write_text("untracked\n")
        version.configure(workspace=str(ws), state=str(ws / "state"), write_json=lambda *a, **k: None)
        p = version.release_plan("app", dev=True)
        self.assertFalse(p.get("error"), p)
        (d / "kept.txt").write_text("changed\n")
        p = version.release_plan("app", dev=True)
        self.assertIn("uncommitted changes", p.get("error", ""), p)
        self.assertIn("kept.txt", p["error"], "the changed file is named")
        self.assertNotIn("stray-tool.py", p["error"])
        self.assertIn("uncommitted changes", version.release("app", push=False, dev=True).get("error", ""))
        git(d, "checkout", "--", "kept.txt")
        # The VERSION file itself is the one untracked file that counts: the
        # tag's number comes from it, so it has to be in the commit.
        (d / "VERSION").write_text("1.2.4\n")
        p = version.release_plan("app", dev=True)
        self.assertIn("uncommitted changes", p.get("error", ""), p)
        self.assertIn("VERSION", p["error"])
        git(d, "checkout", "--", "VERSION")
        r = version.release("app", push=False, dev=True)
        self.assertTrue(r.get("ok"), r)
        self.assertTrue((d / "stray-tool.py").exists(), "the untracked file is left where it was")

    def test_a_dev_release_is_planned_as_its_own_tag_on_the_branchs_line(self):
        # A session's dev release is planned before anybody is asked: as the
        # plain tag, it was refused as the last release's (v0.8.2 already
        # exists); and on a branch whose line is past VERSION it is that
        # line's dev build, as the build's own stamp reads it.
        ws = Path(tempfile.mkdtemp())
        d = ws / "app"
        d.mkdir()
        git(d, "init", "-q", "-b", "main")
        (d / "VERSION").write_text("1.2.3\n")
        git(d, "add", "VERSION")
        git(d, "commit", "-q", "-m", "one")
        git(d, "tag", "-a", "v1.2.3", "-m", "x")
        git(d, "commit", "-q", "--allow-empty", "-m", "two")
        version.configure(workspace=str(ws), state=str(ws / "state"), write_json=lambda *a, **k: None)
        self.assertIn("already exists", version.release_plan("app").get("error", ""))
        self.assertEqual(version.release_plan("app", dev=True).get("tag"), "v1.2.3-dev.2")
        # ...and needs no /config snapshot where the tree keeps them, as
        # release() has it: a dev build is no release an install upgrades from.
        (d / version.UPGRADE_SNAPSHOTS).mkdir(parents=True)
        self.assertEqual(version.release_plan("app", dev=True).get("tag"), "v1.2.3-dev.2")
        with mock.patch.object(version, "line", lambda project: "1.3.0"):
            self.assertEqual(version.release_plan("app", dev=True).get("tag"), "v1.3.0-dev.2")
            self.assertEqual(version.release("app", push=False, dev=True).get("tag"), "v1.3.0-dev.2")


class Finish(unittest.TestCase):
    def test_a_tag_pushed_by_hand_finishes_the_release(self):
        """B399: the release's push failed and the tag went up by hand; the
        release again is its page on the forge, nothing tagged twice."""
        ws = Path(tempfile.mkdtemp())
        remote = ws / "remote.git"
        subprocess.run(["git", "init", "-q", "--bare", str(remote)], check=True)
        d = ws / "app"
        d.mkdir()
        git(d, "init", "-q", "-b", "main")
        (d / "VERSION").write_text("1.2.3\n")
        git(d, "add", "VERSION")
        git(d, "commit", "-q", "-m", "one")
        git(d, "remote", "add", "origin", str(remote))
        git(d, "tag", "-a", "v1.2.3", "-m", "x")
        version.configure(workspace=str(ws), state=str(ws / "state"), write_json=lambda *a, **k: None)
        # Made here, never pushed: releasing again pushes it.
        self.assertTrue(version.release_plan("app").get("finish"))
        r = version.release("app")
        self.assertTrue(r.get("ok") and r.get("pushed") and r.get("finished"), r)
        ls = subprocess.run(["git", "-C", str(d), "ls-remote", "--tags", "origin"], capture_output=True, text=True)
        self.assertIn("refs/tags/v1.2.3", ls.stdout)
        # ...and on the remote already (pushed by hand): what is left is its page.
        r = version.release("app")
        self.assertTrue(r.get("ok") and r.get("pushed") and r.get("finished"), r)


if __name__ == "__main__":
    unittest.main()
