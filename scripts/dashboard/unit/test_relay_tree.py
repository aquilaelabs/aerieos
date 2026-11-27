"""The tree a relayed verb runs in (bbrelay.tree_of): the space's directory
or one of its worktrees on the share, and anything else the space's
directory, said as not the one asked for, so a verb that writes its tree
(aerie changelog add) is refused rather than written somewhere else
(B1131: a worktree in a node's /tmp had its line land in the project)."""
import os
import shutil
import sys
import tempfile
import unittest
from pathlib import Path

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))
import bbrelay  # noqa: E402


class TreeOf(unittest.TestCase):
    def setUp(self):
        self.ws = Path(tempfile.mkdtemp())
        self.addCleanup(shutil.rmtree, self.ws, True)
        (self.ws / "alpha" / "sub").mkdir(parents=True)
        (self.ws / ".worktrees" / "alpha" / "u_1").mkdir(parents=True)
        (self.ws / "beta").mkdir()
        self.was = bbrelay.WORKSPACE
        bbrelay.WORKSPACE = self.ws
        self.addCleanup(setattr, bbrelay, "WORKSPACE", self.was)

    def test_its_own_trees_are_taken(self):
        home = (self.ws / "alpha").resolve()
        self.assertEqual(bbrelay.tree_of("alpha", ""), (self.ws / "alpha", True))
        self.assertEqual(bbrelay.tree_of("alpha", str(self.ws / "alpha")), (home, True))
        self.assertEqual(bbrelay.tree_of("alpha", str(self.ws / "alpha" / "sub")), ((self.ws / "alpha" / "sub").resolve(), True))
        wt = self.ws / ".worktrees" / "alpha" / "u_1"
        self.assertEqual(bbrelay.tree_of("alpha", str(wt)), (wt.resolve(), True))

    def test_any_other_runs_at_home_and_says_it_was_not_the_one_asked(self):
        for other in ("/tmp/nowhere-the-controller-sees", str(self.ws / "beta"), str(self.ws / ".worktrees" / "beta")):
            self.assertEqual(bbrelay.tree_of("alpha", other), (self.ws / "alpha", False), other)


if __name__ == "__main__":
    unittest.main()
