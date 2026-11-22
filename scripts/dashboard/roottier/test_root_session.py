"""The root helper that starts sessions, and an account's terminal server,
as root for real (R240 steps 3 and 4; the audit of 13 Nov).

bb-session keeps what the controller granted each account where only root
writes, and holds an account's own user to it: an account that could write
that record would grant itself every space on the node. It makes an
account's worktree with git run as the tree's owner and no files laid out,
so nothing the repository's own configuration names runs outside a view.
And an account's terminal server starts on AerieOS's own settings, so a
line a session left in ~/.tmux.conf runs nothing outside one."""
import collections
import contextlib
import importlib.machinery
import importlib.util
import io
import json
import os
import shutil
import unittest
from unittest import mock

import world


def load(name, path):
    loader = importlib.machinery.SourceFileLoader(name, path)
    spec = importlib.util.spec_from_loader(name, loader)
    mod = importlib.util.module_from_spec(spec)
    loader.exec_module(mod)
    return mod


session = load("bb_session_root_tier", os.path.join(world.ROOT, "nodes", "bb-session"))
NAME, UID, GID = world.account()
WHO = (UID, GID)
ME = "u_0123abcd"


class Grants(unittest.TestCase):
    def setUp(self):
        self.w = world.World(self)
        self.run = self.w.folder("run")
        p = mock.patch.object(session, "GRANTS", os.path.join(self.run, "grants"))
        p.start()
        self.addCleanup(p.stop)

    def test_what_root_keeps_an_account_can_neither_read_nor_change(self):
        session.grant_keep(ME, {"project": "alpha", "reads": ["libs"]})
        path = os.path.join(session.GRANTS, ME + ".json")
        with open(path) as f:
            before = f.read()
        wider = json.dumps({"alpha": {"reads": [], "works": [], "sees": ["/"]}, "beta": {"reads": [], "works": [], "sees": []}})
        tries = {
            "read it": f"cat {path}",
            "write it": f"echo '{wider}' > {path}",
            "leave another beside it": f"echo '{wider}' > {session.GRANTS}/u_9999ffff.json",
            "leave a link for the next write": f"ln -s {self.w.secret} {path}.new",
            "put a folder of its own in the record's place": f"mv {session.GRANTS} {session.GRANTS}.was && mkdir {session.GRANTS}",
        }
        for what, cmd in tries.items():
            r = world.as_account(WHO, ["sh", "-c", cmd])
            self.assertNotEqual(r.returncode, 0, f"an account could {what}: {r.stdout}{r.stderr}")
        with open(path) as f:
            self.assertEqual(f.read(), before)
        self.assertEqual(sorted(os.listdir(session.GRANTS)), [ME + ".json"])
        # ...so the account enters what it was granted and nothing else.
        session.grant_hold(ME, {"project": "alpha", "reads": ["libs"]})
        for a in ({"project": "beta"}, {"project": "alpha", "sees": ["/"]}):
            with self.assertRaises(session.Refused):
                session.grant_hold(ME, a)
        with self.assertRaises(session.Refused):
            session.grant_hold("u_9999ffff", {"project": "alpha"})
        self.assertEqual(self.w.intact(), "")

    def test_the_next_grant_is_written_past_nothing_an_account_left(self):
        # The record's folder is root's from the start; were a link ever at
        # the name the next write uses, it is not followed.
        session.grant_keep(ME, {"project": "alpha"})
        os.symlink(self.w.secret, os.path.join(session.GRANTS, ME + ".json.new"))
        with self.assertRaises(OSError):
            session.grant_keep(ME, {"project": "beta"})
        self.assertEqual(self.w.intact(), "")


class Worktree(unittest.TestCase):
    def setUp(self):
        self.w = world.World(self)
        self.ws = self.w.folder("workspace")
        self.src = self.w.folder("workspace/alpha", WHO)
        self.ran = os.path.join(self.src, "the-filter-ran")
        self.hooked = os.path.join(self.src, "the-hook-ran")
        env = {"PATH": os.environ.get("PATH", "/usr/bin:/bin"), "HOME": self.src, "GIT_CONFIG_NOSYSTEM": "1",
               "GIT_CONFIG_GLOBAL": "/dev/null"}
        self.git = lambda cwd, *argv: world.as_account(
            WHO, ["git", "-c", "user.name=t", "-c", "user.email=t@t", "-c", "commit.gpgsign=false", *argv], cwd=cwd, env=env)
        # What a session of the space writes: a file, the attribute that
        # marks it, and the repository's own configuration and hook naming
        # commands for laying it out.
        script = (f"git init -q -b main . && echo plain > a.txt && echo '*.txt filter=planted' > .gitattributes"
                  f" && git add -A && git -c user.name=t -c user.email=t@t -c commit.gpgsign=false commit -qm one"
                  f" && git config filter.planted.smudge \"sh -c 'touch {self.ran}; cat'\""
                  f" && printf '#!/bin/sh\\ntouch {self.hooked}\\n' > .git/hooks/post-checkout && chmod +x .git/hooks/post-checkout")
        r = world.as_account(WHO, ["sh", "-c", script], cwd=self.src, env=env)
        self.assertEqual(r.returncode, 0, r.stderr)

    def test_root_makes_it_with_no_files_and_nothing_of_the_repositorys_runs(self):
        user = collections.namedtuple("P", "pw_name")(session.ACCOUNT_USER + ME[2:])
        real = session.pwd.getpwuid
        out = io.StringIO()
        with mock.patch.dict(os.environ, {"SUDO_UID": "64001"}), \
                mock.patch.object(session.pwd, "getpwuid", lambda uid: user if uid == 64001 else real(uid)), \
                contextlib.redirect_stdout(out):
            session.worktree({"ACCOUNT_USERS": "on", "WORKSPACE": self.ws}, ["alpha", "claude", "1", "claude/x"])
        wt = out.getvalue().strip()
        self.assertEqual(wt, os.path.join(self.ws, ".worktrees", "alpha", ME))
        self.assertEqual(os.listdir(wt), [".git"])
        self.assertFalse(os.path.exists(self.ran), "the repository's filter ran outside a view")
        self.assertFalse(os.path.exists(self.hooked), "the repository's hook ran outside a view")
        self.assertTrue(session.worktree_unfilled(wt))
        for d in (os.path.join(self.ws, ".worktrees"), os.path.join(self.ws, ".worktrees", "alpha"), wt):
            self.assertEqual(os.lstat(d).st_uid, UID, f"{d} is the tree owner's: git ran as it, not as root")
        # The session that enters it lays the files out, where both are its own to run.
        r = self.git(wt, "checkout", "-q", "-f", "HEAD")
        self.assertEqual(r.returncode, 0, r.stderr)
        self.assertTrue(os.path.exists(self.ran), "the filter is real: it runs for the session itself")
        self.assertFalse(session.worktree_unfilled(wt))


class TerminalServer(unittest.TestCase):
    def setUp(self):
        self.w = world.World(self)
        self.home = self.w.folder("home", WHO, mode=0o700)
        self.ran = os.path.join(self.home, "the-line-ran")
        conf = os.path.join(self.home, ".tmux.conf")
        with open(conf, "w") as f:
            f.write(f"run-shell 'touch {self.ran}'\n")
        os.chown(conf, UID, GID)
        with open(os.path.join(world.DASH, "bb-tty"), encoding="utf-8") as f:
            src = f.read()
        start = src.index('if [ -n "${BB_TTY_GRANT:-}" ]; then\n    BB_TMUX_OWN=')
        self.block = src[start:src.index("fi\n", start) + 3].replace("${0%/*}", world.DASH)

    def started(self, env):
        """An account's terminal server started the way bb-tty starts it,
        with a session that leaves its own mark, then ended; whether the
        line in ~/.tmux.conf ran."""
        mark = os.path.join(self.home, "the-session-started")
        for f in (self.ran, mark):
            with contextlib.suppress(OSError):
                os.remove(f)
        script = self.block + (f"tmux -L rt new-session -d -s t 'touch {mark}; sleep 5' || exit 9\n"
                               "sleep 1.5\ntmux -L rt kill-server 2>/dev/null\ntrue\n")
        r = world.as_account(WHO, ["bash", "-c", script], cwd=self.home,
                             env={"PATH": os.environ.get("PATH", "/usr/bin:/bin"), "HOME": self.home,
                                  "TMUX_TMPDIR": self.home, "TERM": "xterm", **env})
        self.assertEqual(r.returncode, 0, f"tmux did not start: {r.stdout}{r.stderr}")
        self.assertTrue(os.path.exists(mark), "the server ran no session, so what it read proves nothing")
        return os.path.exists(self.ran)

    def test_a_line_left_in_the_accounts_tmux_conf_runs_nothing(self):
        self.assertIsNotNone(shutil.which("tmux"), "the root tier needs tmux, which the controller's image carries")
        self.assertTrue(self.started({}), "tmux by itself reads ~/.tmux.conf: the line is real")
        self.assertFalse(self.started({"BB_TTY_GRANT": json.dumps({"uid": ME})}),
                         "started for an account's own user, it read ~/.tmux.conf")


if __name__ == "__main__":
    unittest.main()
