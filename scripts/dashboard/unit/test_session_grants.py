"""A session's helpers run nothing a session wrote outside its view, and an
account enters only the spaces the controller granted it (R240 steps 3 and
4; the audit of 13 Nov).

bb-session worktree ran git outside every view on a repository a session
writes, with two configuration keys switched off: laying a worktree's files
out runs whatever filter the repository's configuration names. It makes the
worktree with no files now, and the session that first enters it lays them
out inside its view. And bb-session enter held an account's own user to
being that account and to nothing about the space, so anything running as
it outside a view could enter any space on the node: it is held to what the
controller granted, which the root half keeps where only root writes."""
import importlib.machinery
import importlib.util
import json
import os
import shutil
import subprocess
import tempfile
import unittest
from unittest import mock

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.abspath(os.path.join(HERE, "..", "..", ".."))


def load(name, path):
    loader = importlib.machinery.SourceFileLoader(name, path)
    spec = importlib.util.spec_from_loader(name, loader)
    mod = importlib.util.module_from_spec(spec)
    loader.exec_module(mod)
    return mod


session = load("bb_session_grants", os.path.join(ROOT, "nodes", "bb-session"))
ME, OTHER = "u_0123abcd", "u_9999ffff"


def git(cwd, *argv):
    return subprocess.run(["git", "-c", "user.name=t", "-c", "user.email=t@t", "-c", "commit.gpgsign=false", *argv],
                          cwd=cwd, capture_output=True, text=True, check=False,
                          env={**os.environ, "GIT_CONFIG_GLOBAL": "/dev/null", "GIT_CONFIG_NOSYSTEM": "1"})


class Grants(unittest.TestCase):
    def setUp(self):
        self.d = tempfile.mkdtemp()
        self.addCleanup(shutil.rmtree, self.d, True)
        p = mock.patch.object(session, "GRANTS", os.path.join(self.d, "grants"))
        p.start()
        self.addCleanup(p.stop)

    def test_what_the_controller_granted_is_what_an_account_enters(self):
        with self.assertRaises(session.Refused) as e:
            session.grant_hold(ME, {"project": "alpha"})
        self.assertIn(f"the controller has granted {ME} no terminal on alpha", str(e.exception))
        session.grant_keep(ME, {"uid": ME, "project": "alpha", "reads": ["libs"], "works": ["alpha-site"], "sees": ["/mnt/media"]})
        session.grant_hold(ME, {"project": "alpha"})
        session.grant_hold(ME, {"project": "alpha", "reads": ["libs"], "works": ["alpha-site"], "sees": ["/mnt/media"]})
        # Another space, another account, and more than was granted: refused.
        for a, said in (({"project": "beta"}, "no terminal on beta"),
                        ({"project": "alpha", "reads": ["libs", "secrets"]}, "not granted to read secrets"),
                        ({"project": "alpha", "works": ["beta"]}, "not granted to work in beta"),
                        ({"project": "alpha", "sees": ["/etc"]}, "not granted to see /etc")):
            with self.assertRaises(session.Refused) as e:
                session.grant_hold(ME, a)
            self.assertIn(said, str(e.exception))
        with self.assertRaises(session.Refused):
            session.grant_hold(OTHER, {"project": "alpha"})

    def test_it_is_kept_where_only_root_writes_and_widens_for_a_running_session(self):
        session.grant_keep(ME, {"project": "alpha", "reads": ["libs"]})
        # The settings moved and a terminal was opened again: a session of
        # the earlier grant, still running, is started again as it was.
        session.grant_keep(ME, {"project": "alpha", "reads": ["tools"]})
        session.grant_hold(ME, {"project": "alpha", "reads": ["libs", "tools"]})
        path = os.path.join(session.GRANTS, ME + ".json")
        self.assertEqual(os.stat(session.GRANTS).st_mode & 0o777, 0o700)
        self.assertEqual(os.stat(path).st_mode & 0o777, 0o600)
        with open(path) as f:
            self.assertEqual(sorted(json.load(f)["alpha"]["reads"]), ["libs", "tools"])

    def test_an_answer_that_names_no_space_or_no_account_keeps_nothing(self):
        for account, got in ((ME, {}), (ME, {"project": "../etc"}), ("root", {"project": "alpha"}), ("", {"project": "alpha"})):
            session.grant_keep(account, got)
        self.assertFalse(os.path.isdir(session.GRANTS) and os.listdir(session.GRANTS))
        # A record somebody spoiled reads as no grant, never as every grant.
        os.makedirs(session.GRANTS)
        with open(os.path.join(session.GRANTS, ME + ".json"), "w") as f:
            f.write("[not a record")
        with self.assertRaises(session.Refused):
            session.grant_hold(ME, {"project": "alpha"})

    def test_enter_holds_an_accounts_own_user_and_not_the_nodes_session_account(self):
        c = {"ACCOUNT_USERS": "on", "SESSION_USER": "builder"}
        a = {"project": "alpha", "account": ME, "env": "/nowhere", "home": "/home/x"}
        with mock.patch.object(session, "caller", lambda c, account: ("bbu-0123abcd", 2001, 2001)):
            with self.assertRaises(session.Refused) as e:
                session.enter(c, a, ["true"])
            self.assertIn("no terminal on alpha", str(e.exception))
        # The session account is the node's own: past the grant, to the next check.
        with mock.patch.object(session, "caller", lambda c, account: ("builder", 1000, 1000)):
            with self.assertRaises(session.Refused) as e:
                session.enter(c, a, ["true"])
            self.assertIn("environment file", str(e.exception))


class Worktree(unittest.TestCase):
    def setUp(self):
        self.d = tempfile.mkdtemp()
        self.addCleanup(shutil.rmtree, self.d, True)
        self.src = os.path.join(self.d, "alpha")
        os.makedirs(self.src)
        git(self.src, "init", "-q", "-b", "main")
        with open(os.path.join(self.src, "a.txt"), "w") as f:
            f.write("plain\n")
        with open(os.path.join(self.src, ".gitattributes"), "w") as f:
            f.write("*.txt filter=planted\n")
        git(self.src, "add", "-A")
        git(self.src, "commit", "-qm", "one")
        # What a session of the space can write: the repository's own
        # configuration, naming a command for the paths its attributes mark.
        self.ran = os.path.join(self.d, "the-filter-ran")
        git(self.src, "config", "filter.planted.smudge", f"sh -c 'touch {self.ran}; cat'")

    def test_a_worktree_made_with_no_files_runs_nothing_of_the_repositorys(self):
        with open(os.path.join(ROOT, "nodes", "bb-session"), encoding="utf-8") as f:
            self.assertIn('"worktree", "add", "--no-checkout"', f.read())
        wt = os.path.join(self.d, "wt")
        r = git(self.src, "-c", "core.hooksPath=/dev/null", "-c", "core.fsmonitor=false", "worktree", "add", "--no-checkout", "-b", "claude/x", wt)
        self.assertEqual(r.returncode, 0, r.stderr)
        self.assertFalse(os.path.exists(self.ran), "nothing the repository's configuration names ran outside a view")
        self.assertEqual(os.listdir(wt), [".git"])
        self.assertTrue(session.worktree_unfilled(wt))
        # The session that enters it lays the files out, where the filter is its own to run.
        self.assertEqual(git(wt, "checkout", "-q", "-f", "HEAD").returncode, 0)
        self.assertTrue(os.path.exists(self.ran))
        self.assertTrue(os.path.isfile(os.path.join(wt, "a.txt")))
        self.assertFalse(session.worktree_unfilled(wt))

    def test_the_same_made_the_old_way_ran_it(self):
        # Why two keys switched off were not enough.
        wt = os.path.join(self.d, "wt-old")
        git(self.src, "-c", "core.hooksPath=/dev/null", "-c", "core.fsmonitor=false", "worktree", "add", "-b", "claude/y", wt)
        self.assertTrue(os.path.exists(self.ran))

    def test_only_an_unfilled_worktree_is_one(self):
        self.assertFalse(session.worktree_unfilled(self.src), "a repository's own folder")
        self.assertFalse(session.worktree_unfilled(self.d), "no repository")
        odd = os.path.join(self.d, "odd")
        os.makedirs(odd)
        with open(os.path.join(odd, ".git"), "w") as f:
            f.write("not a gitdir line\n")
        self.assertFalse(session.worktree_unfilled(odd))
        with open(os.path.join(odd, ".git"), "w") as f:
            f.write("gitdir: /nowhere/at/all\n")
        self.assertFalse(session.worktree_unfilled(odd))


class Launcher(unittest.TestCase):
    def test_an_accounts_terminal_server_reads_nothing_from_its_home(self):
        with open(os.path.join(ROOT, "scripts", "dashboard", "bb-tty"), encoding="utf-8") as f:
            src = f.read()
        start = src.index('if [ -n "${BB_TTY_GRANT:-}" ]; then\n    BB_TMUX_OWN=')
        block = src[start:src.index("fi\n", start) + 3].replace("${0%/*}", "/bundle/scripts/dashboard")
        d = tempfile.mkdtemp()
        self.addCleanup(shutil.rmtree, d, True)
        # The two functions, run with stand-ins for the programs: what each is started with.
        for prog in ("tmux", "git"):
            with open(os.path.join(d, prog), "w") as f:
                f.write('#!/bin/sh\necho "$0 $* global=${GIT_CONFIG_GLOBAL-unset}"\n')
            os.chmod(os.path.join(d, prog), 0o755)
        script = block + 'tmux start-server\ngit config user.name\necho "outside=${GIT_CONFIG_GLOBAL-unset}"\n'
        path = d + os.pathsep + os.environ.get("PATH", "/usr/bin:/bin")
        # Started by the root helper for an account's own user: the grant is in its environment.
        p = subprocess.run(["bash", "-c", script], capture_output=True, text=True, check=False,
                           env={"PATH": path, "BB_TTY_GRANT": '{"uid": "u_0123abcd"}'})
        self.assertEqual(p.returncode, 0, p.stderr)
        lines = p.stdout.splitlines()
        self.assertEqual(lines[0], f"{d}/tmux -f /bundle/scripts/dashboard/../lib/tmux.conf start-server global=unset")
        # git is left as the account's: this script's own calls only ask, and
        # one of them is the account's commit identity, which is in its
        # global configuration (a wrapper that hid that configuration
        # stopped every session from starting under the suite).
        self.assertEqual(lines[1], f"{d}/git config user.name global=unset")
        self.assertEqual(lines[2], "outside=unset")
        # Anybody else's (the controller's own terminal, the session account, a suite): tmux as it is.
        p = subprocess.run(["bash", "-c", script], capture_output=True, text=True, check=False, env={"PATH": path})
        self.assertEqual(p.stdout.splitlines()[0], f"{d}/tmux start-server global=unset")


if __name__ == "__main__":
    unittest.main()
