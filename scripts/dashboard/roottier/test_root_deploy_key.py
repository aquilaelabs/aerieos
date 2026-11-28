"""The deploy-key helper's store is root's alone, checked as root for real.

The store sits under a folder the dashboard's account owns, so that account
can rename it aside and put a folder of its own in its place. The helper
enters the store and checks the folder it stands in: one another account
put there is refused before a key is read from it or written to it, and
root's own is used as before."""
import os
import subprocess
import unittest

import world

HERE = os.path.dirname(os.path.abspath(__file__))
HELPER = os.path.abspath(os.path.join(HERE, "..", "..", "deploy-key"))
NAME, UID, GID = world.account()
WHO = (UID, GID)


def helper(store, *argv, run_dir):
    env = dict(os.environ, BB_DEPLOY_KEY_STORE=store, BB_RUN_DIR=run_dir)
    return subprocess.run(["bash", HELPER, *argv], capture_output=True, text=True, check=False, env=env)


class TheStore(unittest.TestCase):
    def setUp(self):
        self.w = world.World(self)
        self.run_dir = self.w.folder("run")

    def test_a_folder_another_account_put_in_its_place_is_refused(self):
        theirs = self.w.folder("deploy-keys", WHO, 0o700)
        p = helper(theirs, "--list", run_dir=self.run_dir)
        self.assertNotEqual(p.returncode, 0, p.stdout)
        self.assertIn("not root's alone", p.stderr)
        self.assertIn(NAME, p.stderr)

    def test_no_key_is_made_in_it(self):
        # Refused before ssh-keygen is reached, so nothing here needs it.
        theirs = self.w.folder("deploy-keys", WHO, 0o700)
        p = helper(theirs, "make", "site", run_dir=self.run_dir)
        self.assertNotEqual(p.returncode, 0, p.stdout)
        self.assertEqual(os.listdir(theirs), [])

    def test_a_link_to_a_folder_of_theirs_is_refused_too(self):
        theirs = self.w.folder("elsewhere", WHO, 0o700)
        link = os.path.join(os.path.dirname(theirs), "deploy-keys")
        os.symlink(theirs, link)
        p = helper(link, "--list", run_dir=self.run_dir)
        self.assertNotEqual(p.returncode, 0, p.stdout)
        self.assertIn("not root's alone", p.stderr)

    def test_roots_own_store_is_used_and_closed_to_the_rest(self):
        mine = self.w.folder("deploy-keys", None, 0o755)
        with open(os.path.join(mine, "site.pub"), "w") as f:
            f.write("ssh-ed25519 AAAA site\n")
        p = helper(mine, "--list", run_dir=self.run_dir)
        self.assertEqual((p.returncode, p.stdout.split()), (0, ["site"]), p.stderr)
        self.assertEqual(os.stat(mine).st_mode & 0o777, 0o700)


if __name__ == "__main__":
    unittest.main()
