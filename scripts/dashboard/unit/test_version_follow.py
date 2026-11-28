"""aerie version follow: what a release
owes once it is out, done by each repository of the space in its own
.aerie/after-release, in the space's order, handed the tag and a checkout of
it; a repository outside the space is never run, and --check says what is
still owed."""
import json
import os
import subprocess
import tempfile
import unittest
from pathlib import Path

HERE = Path(__file__).resolve().parent
AERIE = HERE.parent.parent / "aerie"
GIT_ENV = {"GIT_AUTHOR_NAME": "t", "GIT_AUTHOR_EMAIL": "t@example.test", "GIT_COMMITTER_NAME": "t",
           "GIT_COMMITTER_EMAIL": "t@example.test", "GIT_CONFIG_GLOBAL": os.devnull, "GIT_CONFIG_NOSYSTEM": "1"}


class Follow(unittest.TestCase):
    def setUp(self):
        self.ws = Path(tempfile.mkdtemp())
        self.state = Path(tempfile.mkdtemp())
        # A space of two repositories, alpha and beta, and gamma beside it in no space of theirs.
        (self.state / "projects.json").write_text(json.dumps({"projects": {
            "alpha": {"state": "live"}, "beta": {"state": "live"}, "gamma": {"state": "live"}, "sp": {"state": "repos"}}}))
        (self.state / "project-repos.json").write_text(json.dumps({"projects": {"sp": {"members": ["alpha", "beta"]}}}))
        for r in ("alpha", "beta", "gamma"):
            d = self.ws / r
            d.mkdir()
            self.git(d, "init", "-q", "-b", "main")
            (d / "VERSION").write_text("1.0.0\n")
            (d / ".aerie").mkdir()
            s = d / ".aerie" / "after-release"
            s.write_text("#!/bin/sh\n"
                         f"[ \"${{2:-}}\" = --check ] && {{ echo \"{r} owes $1\"; exit 1; }}\n"
                         f"echo \"{r} did $1 with $(cat \"$AERIEOS_TREE/VERSION\")\" >> \"{self.ws}/done\"\n"
                         f"echo \"{r} did $1\"\n")
            s.chmod(0o755)
            self.git(d, "add", "-A")
            self.git(d, "commit", "-q", "-m", "start")
        self.git(self.ws / "alpha", "tag", "-a", "v1.0.0", "-m", "1.0.0")

    def git(self, d, *a):
        subprocess.run(["git", "-C", str(d), *a], check=True, capture_output=True, env={**os.environ, **GIT_ENV})

    def follow(self, *a):
        env = {**os.environ, **GIT_ENV, "WORKSPACE": str(self.ws), "DASHBOARD_STATE": str(self.state),
               "BB_PROJECT": "alpha", "BB_VERSION_PROJECT": "alpha", "BB_RELAYED": "1"}
        return subprocess.run(["bash", str(AERIE), "version", "follow", *a], cwd=str(self.ws / "alpha"),
                              capture_output=True, text=True, env=env, check=False)

    def test_check_asks_each_repository_of_the_space_and_none_outside_it(self):
        p = self.follow("v1.0.0", "--check")
        self.assertEqual(p.returncode, 1, p.stdout + p.stderr)
        self.assertIn("alpha: alpha owes v1.0.0", p.stdout)
        self.assertIn("beta: beta owes v1.0.0", p.stdout)
        self.assertNotIn("gamma", p.stdout + p.stderr)
        self.assertFalse((self.ws / "done").exists())
        # ...and the checkout it was handed is gone.
        self.assertEqual(subprocess.run(["git", "-C", str(self.ws / "alpha"), "worktree", "list"], capture_output=True,
                                        text=True, check=True).stdout.count("\n"), 1)

    def test_a_tag_this_repository_has_not_is_refused(self):
        p = self.follow("v9.9.9", "--check")
        self.assertNotEqual(p.returncode, 0)
        self.assertIn("no tag v9.9.9 here", p.stdout + p.stderr)

    def test_the_space_lists_its_repositories_for_the_verb(self):
        p = subprocess.run(["python3", str(HERE.parent.parent / "lib" / "settings-verbs.py"), "show", str(HERE.parent), "alpha"],
                           env={**os.environ, "DASHBOARD_STATE": str(self.state), "BB_SETTINGS_JSON": "1",
                                "PYTHONPATH": str(HERE.parent.parent / "lib"), "BB_WORKSPACE": str(self.ws)},
                           capture_output=True, text=True, check=False)
        self.assertEqual(p.returncode, 0, p.stderr)
        self.assertEqual(json.loads(p.stdout).get("space_repos"), ["alpha", "beta"])


if __name__ == "__main__":
    unittest.main()
