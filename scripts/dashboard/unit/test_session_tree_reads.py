"""What a node's view takes from what a session can write, its space's tree
and its home: the CI logs it binds are the folder the controller names with
a terminal, never the name in the tree's git config; a worktree is
made only of a repository whose .git is its own; the folders a bind
lands on are made through no link a session left; and the mapped
tree is no way to root."""
import importlib.machinery
import importlib.util
import os
import re
import shlex
import shutil
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path
from unittest import mock

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.abspath(os.path.join(HERE, "..", "..", ".."))
sys.path.insert(0, os.path.join(HERE, ".."))
import projects  # noqa: E402


def load(name, path):
    loader = importlib.machinery.SourceFileLoader(name, path)
    spec = importlib.util.spec_from_loader(name, loader)
    mod = importlib.util.module_from_spec(spec)
    loader.exec_module(mod)
    return mod


session = load("bb_session_tree_reads", os.path.join(ROOT, "nodes", "bb-session"))


def run(cmd, cwd=None, timeout=120, env=None, split_err=False, register=None):
    p = subprocess.run(cmd, cwd=cwd, capture_output=True, text=True, env=env, timeout=timeout, check=False)
    return {"cmd": shlex.join(cmd), "code": p.returncode, "out": p.stdout or "", "err": p.stderr or ""}


class CiRepository(unittest.TestCase):
    def setUp(self):
        self.d = tempfile.mkdtemp()
        self.addCleanup(shutil.rmtree, self.d, True)
        p = mock.patch.object(session, "REPOS", os.path.join(self.d, "run", "repos.json"))
        p.start()
        self.addCleanup(p.stop)

    def test_the_repository_is_kept_as_the_controller_said_it(self):
        session.repo_keep({"project": "mine", "repo": "mine-repo"})
        session.repo_keep({"project": "other", "repo": "theirs"})
        self.assertEqual((session.repo_of("mine"), session.repo_of("other")), ("mine-repo", "theirs"))
        self.assertEqual(oct(os.stat(session.REPOS).st_mode & 0o777), "0o600")

    def test_none_said_is_none_bound(self):
        self.assertEqual(session.repo_of("mine"), "")
        session.repo_keep({"project": "mine"})
        self.assertEqual(session.repo_of("mine"), "")

    def test_a_name_that_is_no_folder_name_is_kept_as_none(self):
        for bad in ("../other", ".hidden", "a/b", "x" * 101):
            session.repo_keep({"project": "mine", "repo": bad})
            self.assertEqual(session.repo_of("mine"), "", bad)

    def test_the_view_no_longer_reads_the_trees_config(self):
        with open(os.path.join(ROOT, "nodes", "bb-session"), encoding="utf-8") as f:
            text = f.read()
        self.assertNotIn(".git/config", text)
        self.assertIn("repo = repo_of(project)", text)

    def test_the_controller_names_it_from_its_own_tree(self):
        tmp = Path(tempfile.mkdtemp())
        self.addCleanup(shutil.rmtree, tmp, True)
        (tmp / "ws" / "app").mkdir(parents=True)
        projects.configure(run=run, workspace=tmp / "ws", agent_keys=lambda: [], gh_authed=lambda: False,
                           ensure_deploy_alias=lambda *a: "", project_name=re.compile(r"[A-Za-z0-9._-]+"),
                           state=tmp, home=tmp, write_json=lambda p, d: None)
        subprocess.run(["git", "init", "-q", str(tmp / "ws" / "app")], check=True)
        self.assertEqual(projects.ci_repo_name("app"), "")
        subprocess.run(["git", "-C", str(tmp / "ws" / "app"), "remote", "add", "origin",
                        "https://example.test/Owner/The-App.git"], check=True)
        self.assertEqual(projects.ci_repo_name("app"), "The-App")


class Mkdirs(unittest.TestCase):
    def setUp(self):
        self.d = os.path.realpath(tempfile.mkdtemp())
        self.addCleanup(shutil.rmtree, self.d, True)
        self.me = (os.getuid(), os.getgid())
        self.home = os.path.join(self.d, "home")
        self.elsewhere = os.path.join(self.d, "elsewhere")
        os.makedirs(self.home)
        os.makedirs(self.elsewhere)

    def test_the_folders_are_made_and_given_to_the_account(self):
        session._mkdirs(os.path.join(self.home, ".claude", "sessions"), *self.me)
        self.assertTrue(os.path.isdir(os.path.join(self.home, ".claude", "sessions")))
        session._mkdirs(os.path.join(self.home, ".claude", "sessions"), *self.me)   # there already: nothing to do

    def test_a_link_the_account_left_is_not_walked_through(self):
        os.symlink(self.elsewhere, os.path.join(self.home, ".claude"))
        with self.assertRaisesRegex(OSError, "link along it"):
            session._mkdirs(os.path.join(self.home, ".claude", "sessions"), *self.me)
        self.assertEqual(os.listdir(self.elsewhere), [])

    def test_a_file_in_the_way_is_no_folder(self):
        with open(os.path.join(self.home, ".claude"), "w") as f:
            f.write("x")
        with self.assertRaises(OSError):
            session._mkdirs(os.path.join(self.home, ".claude", "sessions"), *self.me)


class Idmap(unittest.TestCase):
    def test_root_is_mapped_on_neither_side(self):
        # A tree root owns is not one to write as the account, nor is
        # an account root; asked for either, no namespace is made.
        for owner, account in (((0, 1000), (2000, 2000)), ((1000, 0), (2000, 2000)),
                               ((1000, 1000), (0, 2000)), ((1000, 1000), (2000, 0))):
            with mock.patch.object(session.os, "fork", side_effect=AssertionError("forked")):
                self.assertIsNone(session.idmap_userns(owner, account))

    def test_the_mapped_tree_honors_no_set_id_program_or_device(self):
        with open(os.path.join(ROOT, "nodes", "bb-session"), encoding="utf-8") as f:
            text = f.read()
        self.assertIn("_MountAttr(MOUNT_ATTR_IDMAP | MOUNT_ATTR_NOSUID | MOUNT_ATTR_NODEV, 0, 0, userns)", text)


class OwnRepository(unittest.TestCase):
    def setUp(self):
        self.d = os.path.realpath(tempfile.mkdtemp())
        self.addCleanup(shutil.rmtree, self.d, True)
        for name in ("mine", "theirs"):
            os.makedirs(os.path.join(self.d, name, ".git"))
        self.mine = os.path.join(self.d, "mine")

    def write(self, rel, text):
        with open(os.path.join(self.mine, rel), "w") as f:
            f.write(text)

    def test_its_own_git_folder_is_a_repository(self):
        self.assertTrue(session._own_repository(self.mine))

    def test_a_git_folder_that_is_a_link_is_not(self):
        shutil.rmtree(os.path.join(self.mine, ".git"))
        os.symlink(os.path.join(self.d, "theirs", ".git"), os.path.join(self.mine, ".git"))
        self.assertFalse(session._own_repository(self.mine))

    def test_a_gitfile_naming_a_folder_inside_it_is_one(self):
        os.rename(os.path.join(self.mine, ".git"), os.path.join(self.mine, ".gitdir"))
        self.write(".git", "gitdir: .gitdir\n")
        self.assertTrue(session._own_repository(self.mine))

    def test_a_gitfile_naming_another_spaces_repository_is_not(self):
        shutil.rmtree(os.path.join(self.mine, ".git"))
        self.write(".git", f"gitdir: {self.d}/theirs/.git\n")
        self.assertFalse(session._own_repository(self.mine))
        self.write(".git", "gitdir: ../theirs/.git\n")
        self.assertFalse(session._own_repository(self.mine))

    def test_a_gitfile_that_is_a_link_a_fifo_or_says_nothing_is_not(self):
        shutil.rmtree(os.path.join(self.mine, ".git"))
        os.makedirs(os.path.join(self.mine, ".gitdir"))
        self.write("elsewhere", "gitdir: .gitdir\n")
        os.symlink(os.path.join(self.mine, "elsewhere"), os.path.join(self.mine, ".git"))
        self.assertFalse(session._own_repository(self.mine))
        os.remove(os.path.join(self.mine, ".git"))
        os.mkfifo(os.path.join(self.mine, ".git"))
        self.assertFalse(session._own_repository(self.mine))
        os.remove(os.path.join(self.mine, ".git"))
        self.write(".git", "not a gitfile\n")
        self.assertFalse(session._own_repository(self.mine))


if __name__ == "__main__":
    unittest.main()
