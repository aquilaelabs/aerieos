"""A deploy's tree: workspace.snapshot_at is the tree as
committed at a branch, a tag or a commit, never the working tree's edits,
by git archive, so the same commit is the same digest; dist/ stays behind;
and what is not a commit is said so."""
import os
import shutil
import subprocess
import sys
import tarfile
import tempfile
import unittest
from pathlib import Path

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))
import workspace  # noqa: E402

GIT = {"GIT_AUTHOR_NAME": "t", "GIT_AUTHOR_EMAIL": "t@example.invalid", "GIT_COMMITTER_NAME": "t",
       "GIT_COMMITTER_EMAIL": "t@example.invalid", "GIT_CONFIG_NOSYSTEM": "1", "HOME": "/nonexistent"}


class SnapshotAt(unittest.TestCase):
    def setUp(self):
        self.tmp = Path(tempfile.mkdtemp())
        self.addCleanup(shutil.rmtree, self.tmp, True)
        self.tree = self.tmp / "ws" / "shop"
        (self.tree / "deploy" / "chart").mkdir(parents=True)
        (self.tree / "dist").mkdir()
        (self.tree / "deploy" / "chart" / "Chart.yaml").write_text("name: shop\n")
        (self.tree / "run.sh").write_text("#!/bin/sh\n")
        os.chmod(self.tree / "run.sh", 0o755)
        (self.tree / "dist" / "old.apk").write_text("a build\n")
        self.git("init", "-q", "-b", "main")
        self.git("add", "-A")
        self.git("commit", "-qm", "one")
        self.git("tag", "v1")
        workspace.configure(workspace=self.tmp / "ws", state=self.tmp / "state")

    def git(self, *a):
        return subprocess.run(["git", "-C", str(self.tree), *a], env=os.environ | GIT, check=True,
                              capture_output=True, text=True).stdout.strip()

    def names(self, got):
        with tarfile.open(workspace.path_for(got["digest"])) as t:
            return {m.name: m for m in t}

    def test_the_commit_not_the_working_tree(self):
        (self.tree / "deploy" / "chart" / "Chart.yaml").write_text("name: edited, not committed\n")
        (self.tree / "loose.txt").write_text("untracked\n")
        got = workspace.snapshot_at("shop", "main")
        self.assertNotIn("error", got, got)
        self.assertEqual(got["commit"], self.git("rev-parse", "HEAD"))
        have = self.names(got)
        self.assertIn("deploy/chart/Chart.yaml", have)
        self.assertNotIn("loose.txt", have, "nothing the commit does not hold")
        self.assertFalse(any(n.startswith("dist") for n in have), "dist/ stays behind")
        self.assertEqual(have["run.sh"].mode & 0o777, 0o755)
        self.assertEqual(have["deploy/chart/Chart.yaml"].mode & 0o777, 0o644)
        with tarfile.open(workspace.path_for(got["digest"])) as t:
            f = t.extractfile("deploy/chart/Chart.yaml")
            self.assertIsNotNone(f)
            self.assertEqual(f.read() if f else b"", b"name: shop\n")

    def test_the_same_commit_is_the_same_digest(self):
        a = workspace.snapshot_at("shop", "v1")
        b = workspace.snapshot_at("shop", self.git("rev-parse", "HEAD"))
        self.assertEqual(a["digest"], b["digest"])
        (self.tree / "next.txt").write_text("two\n")
        self.git("add", "-A")
        self.git("commit", "-qm", "two")
        self.assertNotEqual(workspace.snapshot_at("shop", "main")["digest"], a["digest"])

    def test_what_is_no_commit(self):
        self.assertIn("no commit", workspace.snapshot_at("shop", "nope")["error"])
        for bad in ("", "--output=/tmp/x", "a b", "main;id"):
            self.assertIn("error", workspace.snapshot_at("shop", bad), bad)
        (self.tmp / "ws" / "plain").mkdir()
        self.assertIn("not a git repository", workspace.snapshot_at("plain", "main")["error"])


if __name__ == "__main__":
    unittest.main()
