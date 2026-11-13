"""The root agent does file work in an account's folder as that account
(R240; the audit of 13 Nov: root opened, chmod'ed, chowned and uploaded by
path inside folders a job or session account owns, so a link left at the
name was followed with root's reach).

base.acting_as() gives the calling thread the account's file identity
(setfsuid, setfsgid and the thread's own groups), base.as_root() takes
root's back for a file of the agent's own in the middle of it, and
base.fs_probe() tries it for real before anything relies on it. Most of
this needs root to see for real, which a suite is not: the calls are held
here with a stand-in for libc, and the last class runs only as root."""
import os
import shutil
import tempfile
import threading
import unittest
from unittest import mock

import agentpkg  # noqa: E402

agent = agentpkg.load("aerieos_agent_fs_as")
agent.log = lambda *a, **k: None
agent.log_once = lambda *a, **k: None
base = agent.module("base")


class Libc:
    """setfsuid, setfsgid and syscall as the kernel answers them for one
    thread: each returns what was there before, 0xFFFFFFFF asks and changes
    nothing."""

    def __init__(self, refuse=None):
        self.uid, self.gid, self.groups, self.calls, self.refuse = 0, 0, [0, 27], [], refuse

    def setfsuid(self, v):
        was, v = self.uid, v.value
        if v != 0xFFFFFFFF and v != self.refuse:
            self.uid = v
            self.calls.append(("uid", v))
        return was

    def setfsgid(self, v):
        was, v = self.gid, v.value
        if v != 0xFFFFFFFF:
            self.gid = v
            self.calls.append(("gid", v))
        return was

    def syscall(self, nr, n, arr):
        self.groups = list(arr)[:n.value]
        self.calls.append(("groups", tuple(self.groups)))
        return 0


class Bracket(unittest.TestCase):
    def acting(self, lib, groups=(0, 27)):
        return (mock.patch.object(base, "_fs_libc", lambda: lib),
                mock.patch.object(base.os, "geteuid", lambda: 0, create=True),
                mock.patch.object(base.os, "getgroups", lambda: list(lib.groups)),
                mock.patch.object(base, "_ACTING", threading.local()))

    def test_the_accounts_identity_inside_and_roots_again_after(self):
        lib = Libc()
        a, b, c, d = self.acting(lib)
        with a, b, c, d:
            with base.acting_as((1001, 1002)):
                self.assertEqual((lib.uid, lib.gid, lib.groups), (1001, 1002, []))
                # The groups go first and the user last: with the user gone, so is the right to change them.
                self.assertEqual(lib.calls[:3], [("groups", ()), ("gid", 1002), ("uid", 1001)])
                with base.as_root():
                    self.assertEqual((lib.uid, lib.gid, lib.groups), (0, 0, [0, 27]))
                self.assertEqual((lib.uid, lib.gid, lib.groups), (1001, 1002, []))
            self.assertEqual((lib.uid, lib.gid, lib.groups), (0, 0, [0, 27]))

    def test_whatever_is_raised_inside_root_comes_back(self):
        lib = Libc()
        a, b, c, d = self.acting(lib)
        with a, b, c, d:
            with self.assertRaises(PermissionError):
                with base.acting_as({"user": 1001, "group": 1002, "extra_groups": [5]}):
                    raise PermissionError("the link led to root's file")
            self.assertEqual((lib.uid, lib.gid, lib.groups), (0, 0, [0, 27]))

    def test_an_identity_that_is_not_taken_is_an_error_and_not_a_guess(self):
        lib = Libc(refuse=1001)
        a, b, c, d = self.acting(lib)
        ran = []
        with a, b, c, d:
            with self.assertRaises(OSError):
                with base.acting_as((1001, 1002)):
                    ran.append("as root after all")
            self.assertEqual((ran, lib.uid, lib.gid, lib.groups), ([], 0, 0, [0, 27]))

    def test_nobody_to_act_as_changes_nothing(self):
        lib = Libc()
        a, b, c, d = self.acting(lib)
        with a, b, c, d:
            for who in (None, {}, (0, 0), {"user": 0, "group": 0}, ("bb", 5), {"user": None}):
                with base.acting_as(who):
                    pass
            self.assertEqual(lib.calls, [])
        # ...and an agent that is not root is already whoever it is.
        with mock.patch.object(base, "_fs_libc", lambda: lib), base.acting_as((1001, 1002)):
            pass
        self.assertEqual(lib.calls, [] if os.geteuid() else lib.calls)

    def test_a_machine_that_does_not_hold_it_does_the_work_as_before_and_says_so(self):
        said = []
        with mock.patch.object(base, "_FS_HOLDS", {}), mock.patch.object(base.os, "geteuid", lambda: 0, create=True), \
                mock.patch.object(base, "fs_probe", lambda who: (False, "a link to root's own file was followed and read")), \
                mock.patch.object(base, "log", said.append), mock.patch.object(base, "acting_as", lambda who: who):
            self.assertIsNone(base.fs_holds((1001, 1002)))
            self.assertIsNone(base.fs_holds((1001, 1002)))
        self.assertEqual(len(said), 1)
        self.assertIn("done as root on this machine, as before", said[0])
        with mock.patch.object(base, "_FS_HOLDS", {}), mock.patch.object(base.os, "geteuid", lambda: 0, create=True), \
                mock.patch.object(base, "fs_probe", lambda who: (True, "")), mock.patch.object(base, "log", said.append), \
                mock.patch.object(base, "acting_as", lambda who: who):
            self.assertEqual(base.fs_holds({"user": 1001, "group": 1002}), (1001, 1002))

    def test_not_root_there_is_nothing_to_try(self):
        if os.geteuid() == 0:
            self.skipTest("run as root")
        self.assertEqual(base.fs_probe((1001, 1002)), (None, "this agent is not root"))


class Sites(unittest.TestCase):
    """Where the agent does that work."""

    def setUp(self):
        self.d = tempfile.mkdtemp()
        self.addCleanup(shutil.rmtree, self.d, True)

    def test_the_sync_makes_nothing_under_a_link(self):
        ws = agent.module("wssync")
        root, elsewhere = os.path.join(self.d, "workspace"), os.path.join(self.d, "elsewhere")
        os.makedirs(root)
        os.makedirs(elsewhere)
        os.symlink(elsewhere, os.path.join(root, ".worktrees"))
        sync = object.__new__(ws.WorkspaceSync)
        sync.root, sync.agent = root, type("A", (), {"session_account": lambda self: ""})()
        with self.assertRaises(OSError) as e:
            sync.mkdirs(os.path.join(root, ".worktrees", "alpha", "u_12345678"), "")
        self.assertIn("is a link, so nothing is made under it", str(e.exception))
        self.assertEqual(os.listdir(elsewhere), [])
        # A real folder all the way down is made as it was.
        sync.mkdirs(os.path.join(root, "alpha"), "src/deep")
        self.assertTrue(os.path.isdir(os.path.join(root, "alpha", "src", "deep")))

    def test_a_folder_the_owner_may_not_write_is_refused_as_that(self):
        # Walked on the dev node: a folder a container left root's refused the
        # download, the download swallowed why, and the sync said "the
        # controller answered 0", so it never handed the folder to its owner.
        if os.geteuid() == 0:
            self.skipTest("root may write anywhere")
        ws = agent.module("wssync")
        root = os.path.join(self.d, "workspace")
        top = os.path.join(root, "alpha")
        os.makedirs(os.path.join(top, "made-by-a-container"))
        os.chmod(os.path.join(top, "made-by-a-container"), 0o555)
        self.addCleanup(os.chmod, os.path.join(top, "made-by-a-container"), 0o755)
        asked = []
        sync = object.__new__(ws.WorkspaceSync)
        sync.root = root
        sync.agent = type("A", (), {"session_account": lambda self: "",
                                    "ctl": type("C", (), {"fetch": staticmethod(lambda *a, **k: asked.append(a) or (200, ""))})()})()
        p = type("P", (), {"name": "alpha", "denied": False, "error": ""})()
        with self.assertRaises(PermissionError):
            sync.fetch(p, top, "made-by-a-container/new.txt", "sha", 0o644)
        self.assertEqual(asked, [], "nothing is downloaded where it cannot be written")
        # ...and a download that fails for a reason of its own says the reason.
        sync.agent.ctl.fetch = lambda *a, **k: (0, "the connection was reset")
        with self.assertRaises(OSError) as e:
            sync.fetch(p, top, "plain.txt", "sha", 0o644)
        self.assertIn("plain.txt was not fetched: the connection was reset", str(e.exception))
        self.assertEqual([n for n in os.listdir(top) if n.startswith(".bbsync")], [], "nothing half-written is left")

    def test_what_root_left_in_a_tree_becomes_its_owners_and_nothing_outside_it(self):
        ws = agent.module("wssync")
        top, outside = os.path.join(self.d, "alpha"), os.path.join(self.d, "outside")
        os.makedirs(os.path.join(top, "build"))
        os.makedirs(outside)
        for p in (os.path.join(top, "build", "made-by-a-container"), os.path.join(top, "mine"), os.path.join(outside, "roots")):
            with open(p, "w") as f:
                f.write("x")
        os.symlink(outside, os.path.join(top, "way-out"))
        sync = object.__new__(ws.WorkspaceSync)
        sync.owner = lambda: (1001, 1002)
        roots = {"build", "made-by-a-container", "roots", "way-out"}
        real_stat, took = os.stat, []

        class Roots:
            """A stat whose owner is root, for the names this test says are root's."""

            def __init__(self, s):
                self.s = s

            def __getattr__(self, k):
                return 0 if k == "st_uid" else getattr(self.s, k)

        def stat(name, *a, **k):
            s = real_stat(name, *a, **k)
            # Only claim's own look, which names an entry inside a folder's descriptor.
            return Roots(s) if "dir_fd" in k and os.path.basename(str(name)) in roots else s

        with mock.patch.object(ws.os, "stat", stat), \
                mock.patch.object(ws.os, "chown", lambda name, u, g, dir_fd=None, follow_symlinks=True: took.append((name, u, g, follow_symlinks))):
            n = sync.claim(top)
        self.assertEqual(sorted(t[0] for t in took), ["build", "made-by-a-container", "way-out"])
        self.assertEqual(n, 3)
        # The link itself, never what it points at; nothing was walked through it.
        self.assertTrue(all(t[1:] == (1001, 1002, False) for t in took))
        self.assertNotIn("roots", [t[0] for t in took])

    def test_a_folder_is_given_to_the_account_by_itself_and_not_through_a_link(self):
        wsm = agent.module("workspace")
        a = object.__new__(agent.Agent)
        real, link = os.path.join(self.d, "real"), os.path.join(self.d, "store")
        os.makedirs(real)
        os.symlink(real, link)
        gave = []
        with mock.patch.object(wsm.os, "fchown", lambda fd, u, g: gave.append((os.readlink(f"/proc/self/fd/{fd}"), u, g))):
            a.own_dir(link, {"user": 1001, "group": 1002})
            self.assertEqual(gave, [], "a link left at the folder's name is not followed")
            a.own_dir(real, {"user": 1001, "group": 1002})
        self.assertEqual(gave, [(real, 1001, 1002)])

    def test_artifacts_are_found_and_read_as_the_jobs_account(self):
        wsm = agent.module("workspace")
        a = object.__new__(agent.Agent)
        base_dir = os.path.join(self.d, "ws")
        os.makedirs(os.path.join(base_dir, "dist"))
        with open(os.path.join(base_dir, "dist", "app.apk"), "w") as f:
            f.write("apk")
        as_who, sent = [], []

        class Hold:
            def __init__(self, who):
                self.who = who

            def __enter__(self):
                as_who.append(self.who)

            def __exit__(self, *x):
                as_who.append("root again")

        class Ctl:
            @staticmethod
            def upload(path, src):
                sent.append((src, as_who[-1]))
                return 200, {"path": "dist/app.apk", "size": 3, "sha256": "s"}

        class Job:
            job, outputs = {"id": "j1"}, []

            def say(self, t):
                pass

        a.ctl, a.drop_privileges = Ctl(), lambda env: {"user": 1001, "group": 1002}
        with mock.patch.object(wsm, "fs_holds", Hold):
            a.deliver(Job(), base_dir, ["dist/*.apk"])
        self.assertEqual(sent, [(os.path.join(base_dir, "dist", "app.apk"), {"user": 1001, "group": 1002})])
        self.assertEqual(as_who[-1], "root again")


class Neighbors(unittest.TestCase):
    """What this change nearly broke: its helper was first called _who, the
    name of the function that reads who a pack's coding agent is signed in
    as, and replaced it without a word. Lint's twice-defined check caught
    it; no test did, so this one holds that function to its work."""

    def test_a_pack_agents_who_is_still_read(self):
        import json
        d = tempfile.mkdtemp()
        self.addCleanup(shutil.rmtree, d, True)
        os.makedirs(os.path.join(d, "config"))
        who = {"file": ".gemini/account.json", "email": ["account", "email"], "named": "Google account"}
        with open(os.path.join(d, "config", "toolpacks.json"), "w") as f:
            json.dump({"toolchains": [{"name": "gemini", "agent": {"provider": "Google", "signin": {"flow": {
                "kept": ".gemini/oauth.json", "who": who}}}}]}, f)
        with mock.patch.dict(base._pack_kept, {"stamp": None, "rows": {}}):
            got = base.pack_signins(d)
        self.assertEqual(got["gemini"], {"kept": ".gemini/oauth.json", "provider": "Google", "who": who})
        # ...and what it is handed is still held to plain words and a plain path.
        self.assertIsNone(base._who({"file": "/etc/passwd", "email": ["a b"], "named": "x"}))
        self.assertIsNone(base._who((1001, 1002)))


@unittest.skipUnless(os.geteuid() == 0, "the real thing needs root")
class AsRoot(unittest.TestCase):
    def test_this_machine_holds_it(self):
        import pwd
        nobody = pwd.getpwnam("nobody")
        ok, why = base.fs_probe((nobody.pw_uid, nobody.pw_gid))
        self.assertTrue(ok, why)


if __name__ == "__main__":
    unittest.main()
