"""Where a release may be cut from (R206; the operator, 14 Nov): a dev build
on the branch it was built on, a stable release or a release candidate only
on a commit that is on main. tools/release-place.sh is what the tag's
workflow asks before anything is built to publish; nothing asked before,
and the six newest tags sat on the working branch."""
import os
import shutil
import subprocess
import tempfile
import unittest

HERE = os.path.dirname(os.path.abspath(__file__))
TOOL = os.path.normpath(os.path.join(HERE, "..", "..", "..", "tools", "release-place.sh"))


class Place(unittest.TestCase):
    def setUp(self):
        self.d = tempfile.mkdtemp()
        self.addCleanup(shutil.rmtree, self.d, True)
        self.git("init", "-q", "-b", "main")
        self.commit("one")
        self.git("update-ref", "refs/remotes/origin/main", "HEAD")
        self.on_main = self.git("rev-parse", "HEAD").strip()
        self.git("checkout", "-q", "-b", "claude/work")
        self.commit("two")
        self.on_branch = self.git("rev-parse", "HEAD").strip()

    def git(self, *argv):
        return subprocess.run(["git", "-c", "user.name=t", "-c", "user.email=t@t", "-c", "commit.gpgsign=false", *argv],
                              cwd=self.d, capture_output=True, text=True, check=True).stdout

    def commit(self, said):
        with open(os.path.join(self.d, "f"), "a") as f:
            f.write(said + "\n")
        self.git("add", "-A")
        self.git("commit", "-q", "-m", said)

    def ask(self, *argv):
        p = subprocess.run(["bash", TOOL, *argv], cwd=self.d, capture_output=True, text=True, check=False)
        return p.returncode, (p.stdout + p.stderr).strip()

    def test_a_dev_build_goes_on_wherever_it_was_built(self):
        rc, said = self.ask("v0.9.0-dev.5400", self.on_branch)
        self.assertEqual(rc, 0, said)
        self.assertIn("a dev build: tagged on the branch it was built on", said)
        self.assertEqual(self.ask("v0.9.0-dev.5400", self.on_main)[0], 0)
        # The commit not named: the one checked out.
        self.assertEqual(self.ask("v0.9.0-dev.5400")[0], 0)

    def test_a_stable_release_and_a_candidate_only_from_main(self):
        for tag, word in (("v0.9.0", "a stable release"), ("v0.9.0-rc.2", "a rc pre-release"), ("v1.0.0-beta.1", "a beta pre-release")):
            rc, said = self.ask(tag, self.on_branch)
            self.assertEqual(rc, 1, said)
            self.assertIn(f"{tag} is {word}, which is cut from main", said)
            self.assertIn("is not on main", said)
            self.assertIn("or cut a dev build", said)
            rc, said = self.ask(tag, self.on_main)
            self.assertEqual(rc, 0, said)
            self.assertIn("is on main", said)
        # Merged since: the same commit is on main now.
        self.git("update-ref", "refs/remotes/origin/main", self.on_branch)
        self.assertEqual(self.ask("v0.9.0", self.on_branch)[0], 0)

    def test_main_not_fetched_is_said_and_refused(self):
        self.git("update-ref", "-d", "refs/remotes/origin/main")
        rc, said = self.ask("v0.9.0", self.on_branch)
        self.assertEqual(rc, 1)
        self.assertIn("origin/main is not known here (fetch it first)", said)
        # A dev build needs no main.
        self.assertEqual(self.ask("v0.9.0-dev.7", self.on_branch)[0], 0)

    def test_what_is_no_releases_name_is_said_as_that(self):
        for tag in ("", "0.9.0", "v0.9", "vnext", "v0.9.0-dev", "v0.9.0-", "v0.9.0-DEV.1", "android-v1.2.3", "v0.9.0-dev.x"):
            rc, said = self.ask(tag, self.on_main)
            self.assertEqual(rc, 2, (tag, said))
            self.assertIn("not a release's tag", said)
        self.assertEqual(self.ask("v0.9.0", "no-such-commit")[0], 1)


if __name__ == "__main__":
    unittest.main()
