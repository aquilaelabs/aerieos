"""A release is of the commit that is pushed, read from that commit (R206
step 4). The tag was judged by the controller's copy of the tree, where a
node's sync lands: files a session keeps out of git and a changed mode bit
refused every tag (B628). The release now asks origin where the branch is,
which must be the commit the tree is on; reads the version, the changelog
and the branch's line from a tree of that commit made for the purpose;
writes the changelog's commit there and pushes it; and cuts a stable
release or a named pre-release only from a commit on the branch builds come
from (the operator, 14 Nov). In scratch repositories with a remote."""
import os
import shutil
import subprocess
import sys
import tempfile
import threading
import unittest
from pathlib import Path
from unittest import mock

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))
import changelog  # noqa: E402
import version  # noqa: E402

GIT_ENV = {"GIT_AUTHOR_NAME": "t", "GIT_AUTHOR_EMAIL": "t@example.com",
           "GIT_COMMITTER_NAME": "t", "GIT_COMMITTER_EMAIL": "t@example.com"}


class Pushed(unittest.TestCase):
    def setUp(self):
        self.ws = Path(tempfile.mkdtemp())
        self.addCleanup(shutil.rmtree, self.ws, ignore_errors=True)
        p = mock.patch.object(version.time, "sleep", lambda s: None)
        p.start()
        self.addCleanup(p.stop)
        st = self.ws / ".state"
        st.mkdir()
        version.configure(workspace=self.ws, state=st, write_json=lambda *_a, **_k: None, changelog_mod=changelog)
        self.remote = self.ws / "remote.git"
        subprocess.run(["git", "init", "-q", "--bare", "-b", "main", str(self.remote)], check=True)
        self.app = self.ws / "app"
        self.app.mkdir()
        self.git("init", "-q", "-b", "main")
        (self.app / "VERSION").write_text("1.2.0\n")
        (self.app / "CHANGELOG.md").write_text("# Changelog\n\n## 1.1.0: 2025-12-01\n\n### Added\n\n- Old (0001111)\n")
        self.commit("start")
        self.git("remote", "add", "origin", str(self.remote))
        self.git("push", "-q", "origin", "main")
        self.git("fetch", "-q", "origin")

    def git(self, *a, cwd=None):
        r = subprocess.run(["git", "-C", str(cwd or self.app), *a], capture_output=True, text=True,
                           env={**os.environ, **GIT_ENV}, check=True)
        return r.stdout.strip()

    def commit(self, msg, cwd=None):
        self.git("add", "-A", cwd=cwd)
        self.git("commit", "-q", "--allow-empty", "-m", msg, cwd=cwd)
        return self.git("rev-parse", "--short=7", "HEAD", cwd=cwd)

    def remote_ref(self, ref):
        r = subprocess.run(["git", "-C", str(self.remote), "rev-parse", "--short=7", "--verify", "-q", ref],
                           capture_output=True, text=True, check=False)
        return r.stdout.strip()

    def both(self, **k):
        """The plan's answer and the release's, which refuse the same."""
        return version.release_plan("app", **k), version.release("app", env=GIT_ENV, **{("dev" if x == "dev" else x): v for x, v in k.items() if x != "stable"})

    def test_commits_not_pushed_are_named_and_nothing_is_tagged(self):
        self.commit("two")
        self.commit("three")
        for r in self.both(dev=True):
            self.assertIn("2 commits here are not pushed", r.get("error", ""), r)
            self.assertIn("Push (aerie git push), then release", r["error"])
        self.assertEqual(self.git("tag"), "")
        self.git("push", "-q", "origin", "main")
        r = version.release("app", env=GIT_ENV, dev=True)
        self.assertTrue(r.get("ok") and r.get("pushed"), r)
        self.assertEqual(self.remote_ref("refs/tags/v1.2.0-dev.3^{commit}"), self.git("rev-parse", "--short=7", "HEAD"))

    def test_a_remote_that_moved_on_or_apart_is_said(self):
        other = self.ws / "other"
        subprocess.run(["git", "clone", "-q", str(self.remote), str(other)], check=True)
        self.commit("theirs", cwd=other)
        self.git("push", "-q", "origin", "main", cwd=other)
        # This tree has never heard of that commit: it is fetched to tell
        # "moved past" from "apart", and the directory's files are not touched.
        for r in self.both(dev=True):
            self.assertIn("origin's main has moved past this tree", r.get("error", ""), r)
            self.assertIn("pull, then release", r["error"])
        self.commit("mine")
        self.assertIn("neither holds the other", version.release("app", env=GIT_ENV, dev=True)["error"])
        self.assertEqual(self.git("tag"), "")

    def test_a_branch_origin_does_not_have_and_a_tree_on_no_branch(self):
        self.git("checkout", "-q", "-b", "topic")
        self.commit("on topic")
        self.assertIn("topic is not on origin: push it", version.release_plan("app", dev=True)["error"])
        # On no branch, at the head of a pushed one: that branch's release.
        self.git("checkout", "-q", "--detach", "main")
        r = version.release("app", env=GIT_ENV, dev=True)
        self.assertTrue(r.get("ok") and r.get("pushed"), r)
        self.assertEqual(r["tag"], "v1.2.0-dev.1")
        # ...and at a commit that heads none: said.
        self.git("checkout", "-q", "--detach", "topic")
        self.assertIn("is the head of no branch on origin", version.release_plan("app", dev=True)["error"])

    def test_the_branchs_line_and_channel_are_read_though_the_tree_is_on_none(self):
        # A branch named for the release it works toward tags that line's dev
        # build (R112), and is a dev release unasked (R190): both read the
        # branch, which a tree of the bare commit does not have.
        self.git("checkout", "-q", "-b", "claude/1.3.0")
        self.commit("toward 1.3.0")
        self.git("push", "-q", "origin", "claude/1.3.0")
        self.git("fetch", "-q", "origin")
        p = version.release_plan("app")
        self.assertEqual((p.get("tag"), p.get("dev")), ("v1.3.0-dev.2", True), p)
        r = version.release("app", env=GIT_ENV, dev=True)
        self.assertEqual(r.get("tag"), "v1.3.0-dev.2", r)
        self.assertEqual(self.git("rev-parse", "--abbrev-ref", "HEAD"), "claude/1.3.0", "the directory stays on its branch")

    def test_the_changelogs_commit_is_made_off_the_directory_pushed_and_the_directory_follows(self):
        changelog.add(self.app, "A new thing", sha=self.git("rev-parse", "--short=7", "HEAD"), cat="Added")
        was = self.commit("changelog")
        self.git("push", "-q", "origin", "main")
        (self.app / "scratch.txt").write_text("a session's own file\n")
        r = version.release("app", env=GIT_ENV, dev=True)
        self.assertTrue(r.get("ok") and r.get("pushed"), r)
        self.assertEqual(r["tag"], "v1.2.0-dev.3", "tagged on the section's commit, the one after")
        sec = r["section"]
        self.assertNotEqual(sec, was)
        self.assertEqual(self.remote_ref("refs/heads/main"), sec, "the branch carries the section's commit")
        self.assertEqual(self.remote_ref("refs/tags/v1.2.0-dev.3^{commit}"), sec)
        # The directory was brought up to it, as a pull would, its own file left.
        self.assertEqual(self.git("rev-parse", "--short=7", "HEAD"), sec)
        self.assertIn("## 1.2.0-dev.3", (self.app / "CHANGELOG.md").read_text())
        self.assertTrue((self.app / "scratch.txt").exists())
        self.assertNotIn("note", r)

    def test_a_directory_that_cannot_follow_is_told_to_pull_and_the_release_stands(self):
        changelog.add(self.app, "A new thing", sha=self.git("rev-parse", "--short=7", "HEAD"), cat="Added")
        was = self.commit("changelog")
        self.git("push", "-q", "origin", "main")
        # The controller's copy with the changelog changed beside the commit.
        (self.app / "CHANGELOG.md").write_text((self.app / "CHANGELOG.md").read_text() + "\nscribble\n")
        r = version.release("app", env=GIT_ENV, dev=True)
        self.assertTrue(r.get("ok") and r.get("pushed"), r)
        self.assertNotIn("scribble", self.git("show", f"{r['tag']}:CHANGELOG.md"), "nothing of the directory is in the release")
        self.assertEqual(self.git("rev-parse", "--short=7", "HEAD"), was)
        self.assertIn("one commit behind it: pull", r["note"])
        self.assertIn("scribble", (self.app / "CHANGELOG.md").read_text(), "and nothing there is overwritten")

    def test_a_stable_release_or_a_candidate_is_cut_only_from_the_branch_builds_come_from(self):
        self.git("checkout", "-q", "-b", "work")
        self.commit("work")
        self.git("push", "-q", "origin", "work")
        self.git("fetch", "-q", "origin")
        for r in (version.release_plan("app", stable=True), version.release("app", env=GIT_ENV)):
            self.assertIn("v1.2.0 is a stable release, which is cut from main", r.get("error", ""), r)
            self.assertIn("is not on main", r["error"])
            self.assertIn("aerie version release --dev", r["error"])
        for r in (version.release_plan("app", pre="rc"), version.release("app", env=GIT_ENV, pre="rc")):
            self.assertIn("v1.2.0-rc.2 is a rc pre-release, which is cut from main", r.get("error", ""), r)
        self.assertEqual(self.git("tag"), "")
        # A dev build is tagged where it was built.
        r = version.release("app", env=GIT_ENV, dev=True)
        self.assertEqual((r.get("tag"), r.get("pushed")), ("v1.2.0-dev.2", True), r)
        # Merged into main, the same commit is on it: a candidate may be cut.
        self.git("checkout", "-q", "main")
        self.git("merge", "-q", "--ff-only", "work")
        self.git("push", "-q", "origin", "main")
        self.git("fetch", "-q", "origin")
        r = version.release("app", env=GIT_ENV, pre="rc")
        self.assertEqual((r.get("tag"), r.get("pushed")), ("v1.2.0-rc.2", True), r)
        r = version.release("app", env=GIT_ENV)
        self.assertEqual((r.get("tag"), r.get("pushed")), ("v1.2.0", True), r)

    def test_only_the_thread_releasing_reads_the_commits_tree(self):
        seen = {}
        sha = self.git("rev-parse", "HEAD")
        with version._commit_tree("app", sha, "main") as tree:
            self.assertEqual(version.root("app"), tree)
            self.assertEqual(version.branch_of("app"), "main")
            self.assertEqual(version.root("other"), self.ws / "other")
            t = threading.Thread(target=lambda: seen.update(root=version.root("app")))
            t.start()
            t.join()
            self.assertEqual(sorted(p.name for p in tree.iterdir()), [".git", "CHANGELOG.md", "VERSION"])
        self.assertEqual(seen["root"], self.ws / "app")
        self.assertEqual(version.root("app"), self.ws / "app")
        self.assertFalse(tree.exists())
        self.assertEqual(self.git("worktree", "list", "--porcelain").count("worktree "), 1)

    def test_no_origin_releases_the_trees_own_commit(self):
        self.git("remote", "remove", "origin")
        self.commit("local only")
        r = version.release("app", env=GIT_ENV, dev=True)
        self.assertTrue(r.get("ok"), r)
        self.assertEqual(r["tag"], "v1.2.0-dev.2")


if __name__ == "__main__":
    unittest.main()
