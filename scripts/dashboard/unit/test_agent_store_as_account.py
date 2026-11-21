"""Root runs and follows nothing the jobs account owns in the toolchain store.

The store, its copy of the bundle under .bb and every binary in it are the
jobs account's to replace. A root agent therefore asks the store's versions
with root's own copy of aerie run as that account, has the store's copy of
the bundle unpacked by a process of the account, reaches .bb and what is
under it by the folders themselves (never through a link left at a name),
writes a pack's settings the same way and only into this node's own store,
and runs the store's aapt2 in a sign job as the account."""
import io
import os
import shutil
import stat
import tarfile
import tempfile
import types
import unittest
from unittest import mock

import agentpkg  # noqa: E402

agent = agentpkg.load("aerieos_agent_store_as_account")
agent.log = lambda *a, **k: None
toolchains = agent.module("toolchains")
workspace = agent.module("workspace")
packconfig = agent.module("packconfig")
base = agent.module("base")

WHO = {"user": 1234, "group": 1234, "extra_groups": []}


def a_tar(path, files):
    with tarfile.open(path, "w") as tar:
        for name, data in files.items():
            info = tarfile.TarInfo(name)
            info.size = len(data)
            info.mode = 0o644
            tar.addfile(info, io.BytesIO(data))


class Tmp(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.mkdtemp()
        self.addCleanup(shutil.rmtree, self.tmp, True)
        self.store = os.path.join(self.tmp, "store")
        os.makedirs(self.store)


class Versions(Tmp):
    def ask(self, euid, user="builder"):
        rooted = os.path.join(self.tmp, "rootbundle")
        for d in (os.path.join(rooted, "current"), os.path.join(self.store, ".bb", "0123456789abcdef")):
            os.makedirs(os.path.join(d, "scripts"))
            with open(os.path.join(d, "scripts", "aerie"), "w") as f:
                f.write("#!/bin/bash\n")
        ran = []

        def run(argv, **kw):
            ran.append((argv, kw))
            return types.SimpleNamespace(stdout="jdk\t21.0.1\t-\t-\n", stderr="", returncode=0)
        pw = types.SimpleNamespace(pw_uid=1234, pw_gid=1234, pw_dir="/home/builder")
        with mock.patch.object(toolchains, "tc_root", lambda st: self.store), \
                mock.patch.object(toolchains, "ROOT_BUNDLE_DIR", rooted), \
                mock.patch.object(toolchains.os, "geteuid", lambda: euid), \
                mock.patch("pwd.getpwnam", lambda name: pw), \
                mock.patch.object(toolchains.subprocess, "run", run):
            got = toolchains.sdk_versions({"user": user, "stores": {"toolchains": self.tmp}})
        return got, ran, rooted

    def test_root_runs_its_own_copy_as_the_jobs_account(self):
        got, ran, rooted = self.ask(0)
        self.assertEqual(got, {"jdk": "21.0.1"})
        (argv, kw), = ran
        self.assertEqual(argv[1], os.path.join(rooted, "current", "scripts", "aerie"), "root's copy, not the store's")
        self.assertEqual((kw["user"], kw["group"], kw["extra_groups"]), (1234, 1234, []))
        self.assertEqual(kw["env"]["HOME"], "/home/builder")

    def test_root_with_no_copy_of_its_own_runs_nothing(self):
        with mock.patch.object(toolchains, "tc_root", lambda st: self.store), \
                mock.patch.object(toolchains, "ROOT_BUNDLE_DIR", os.path.join(self.tmp, "none")), \
                mock.patch.object(toolchains.os, "geteuid", lambda: 0), \
                mock.patch("pwd.getpwnam", lambda name: types.SimpleNamespace(pw_uid=1, pw_gid=1, pw_dir="/h")), \
                mock.patch.object(toolchains.subprocess, "run", side_effect=AssertionError("ran something")):
            os.makedirs(os.path.join(self.store, ".bb", "0123456789abcdef", "scripts"))
            with open(os.path.join(self.store, ".bb", "0123456789abcdef", "scripts", "aerie"), "w") as f:
                f.write("#!/bin/bash\n")
            self.assertEqual(toolchains.sdk_versions({"user": "builder"}), {})

    def test_an_account_that_is_gone_is_asked_nothing(self):
        def gone(name):
            raise KeyError(name)
        with mock.patch.object(toolchains, "tc_root", lambda st: self.store), \
                mock.patch.object(toolchains.os, "geteuid", lambda: 0), \
                mock.patch("pwd.getpwnam", gone), \
                mock.patch.object(toolchains.subprocess, "run", side_effect=AssertionError("ran something")):
            self.assertEqual(toolchains.sdk_versions({"user": "builder"}), {})

    def test_an_agent_that_is_not_root_runs_the_store_s_copy_as_itself(self):
        got, ran, _rooted = self.ask(1000)
        (argv, kw), = ran
        self.assertTrue(argv[1].startswith(os.path.join(self.store, ".bb")))
        self.assertNotIn("user", kw)


class Unpack(Tmp):
    FILES = {"scripts/aerie": b"#!/bin/bash\n", "scripts/dashboard/bb-tty": b"#!/bin/sh\n", "config/toolchains.json": b"{}"}

    def setUp(self):
        super().setUp()
        self.tar = os.path.join(self.tmp, "bundle.tar")
        a_tar(self.tar, self.FILES)
        self.bb = os.path.join(self.store, ".bb")
        os.makedirs(self.bb)

    def test_the_bundle_is_unpacked_whole_and_current_points_at_it(self):
        made, why = workspace.WorkspaceMixin._unpack_in_store(self.tar, self.bb, "0123456789abcdef", {})
        self.assertEqual((made, why), (True, ""))
        into = os.path.join(self.bb, "0123456789abcdef")
        self.assertTrue(os.access(os.path.join(into, "scripts", "aerie"), os.X_OK))
        self.assertTrue(os.access(os.path.join(into, "scripts", "dashboard", "bb-tty"), os.X_OK))
        self.assertEqual(os.readlink(os.path.join(self.bb, "current")), "0123456789abcdef")
        self.assertFalse(os.path.exists(into + ".new"))
        self.assertEqual(workspace.WorkspaceMixin._unpack_in_store(self.tar, self.bb, "0123456789abcdef", {}), (False, ""))

    def test_a_half_unpacked_folder_from_before_is_not_a_bundle(self):
        os.makedirs(os.path.join(self.bb, "0123456789abcdef.new", "left"))
        self.assertEqual(workspace.WorkspaceMixin._unpack_in_store(self.tar, self.bb, "0123456789abcdef", {})[0], True)
        self.assertFalse(os.path.exists(os.path.join(self.bb, "0123456789abcdef", "left")))

    def test_a_tar_that_cannot_be_unpacked_is_said(self):
        with open(self.tar, "wb") as f:
            f.write(b"not a tar")
        made, why = workspace.WorkspaceMixin._unpack_in_store(self.tar, self.bb, "0123456789abcdef", {})
        self.assertIsNone(made)
        self.assertTrue(why)

    def test_the_process_that_unpacks_is_the_account_s(self):
        ran = {}

        def run(argv, **kw):
            ran.update(kw, argv=argv)
            return types.SimpleNamespace(stdout="unpacked\n", stderr="", returncode=0)
        with mock.patch.object(workspace.subprocess, "run", run):
            workspace.WorkspaceMixin._unpack_in_store(self.tar, self.bb, "0123456789abcdef", WHO)
        self.assertEqual((ran["user"], ran["group"], ran["extra_groups"]), (1234, 1234, []))
        self.assertEqual(ran["argv"][-2:], [self.bb, "0123456789abcdef"])

    def test_bundle_unpacks_through_that_process_and_owns_nothing_by_path(self):
        """bundle() as root: the store's copy made by the account's process,
        with no walk of it by root afterwards."""
        import hashlib
        a = object.__new__(agent.Agent)
        a.state = {"user": "builder", "stores": {"toolchains": self.tmp}}
        a.session_up = a.session_bundle = a.session_stale = a.session_digest = ""
        with open(self.tar, "rb") as f:
            body = f.read()
        digest = "sha256:" + hashlib.sha256(body).hexdigest()

        class Ctl:
            def fetch(_, path, dest, timeout=600):
                with open(dest, "wb") as f:
                    f.write(body)
                return 200, digest
        a.ctl = Ctl()
        asked = []

        def unpack(tar_path, bbdir, name, who):
            asked.append((bbdir, name, who))
            return workspace.WorkspaceMixin._unpack_in_store(tar_path, bbdir, name, {})
        tools = os.path.join(self.tmp, "tools")
        with mock.patch.object(workspace, "tc_root", lambda st: self.store), \
                mock.patch.object(workspace, "TOOLS_DIR", tools), \
                mock.patch.object(workspace.os, "geteuid", lambda: 0), \
                mock.patch.object(workspace.os, "fchown", lambda *a, **k: None), \
                mock.patch.object(workspace.os, "lchown", side_effect=AssertionError("root owned a path in the store")), \
                mock.patch.object(workspace.os, "chown", side_effect=AssertionError("root owned a path in the store")), \
                mock.patch.object(workspace.release, "trusted", lambda st: []), \
                mock.patch.object(agent.Agent, "_keep_root_tools", staticmethod(lambda *a, **k: None)), \
                mock.patch.object(agent.Agent, "_keep_root_bundle", staticmethod(lambda *a, **k: None)), \
                mock.patch.object(agent.Agent, "_unpack_in_store", staticmethod(unpack)), \
                mock.patch.object(workspace, "load_state", lambda: a.state):
            into = a.bundle(None, WHO)
        self.assertEqual(asked, [(self.bb, os.path.basename(into), WHO)])
        self.assertTrue(os.path.isfile(os.path.join(into, "scripts", "aerie")))


class TakeBb(Tmp):
    def take(self):
        owned = []
        with mock.patch.object(workspace.os, "geteuid", lambda: 0), \
                mock.patch.object(workspace.os, "fchown", lambda fd, u, g: owned.append((os.fstat(fd).st_ino, u, g))):
            workspace.WorkspaceMixin._take_bb(self.store, WHO)
        return owned

    def test_a_folder_is_given_to_the_account_by_itself(self):
        owned = self.take()
        self.assertEqual(owned, [(os.stat(os.path.join(self.store, ".bb")).st_ino, 1234, 1234)])

    def test_a_link_left_at_its_name_is_taken_away_and_not_followed(self):
        elsewhere = os.path.join(self.tmp, "etc")
        os.makedirs(elsewhere)
        os.symlink(elsewhere, os.path.join(self.store, ".bb"))
        owned = self.take()
        bb = os.path.join(self.store, ".bb")
        self.assertFalse(os.path.islink(bb))
        self.assertTrue(os.path.isdir(bb))
        self.assertNotIn(os.stat(elsewhere).st_ino, [o[0] for o in owned], "the link's target was not given away")
        self.assertEqual(os.listdir(elsewhere), [])

    def test_a_share_that_keeps_no_owner_still_gives_a_folder(self):
        # An NFS export with all_squash, or a FUSE share, refuses every
        # chown: everything there is everybody's one account already, and
        # the store's .bb is made and used as it is (the dev node's store).
        import errno

        def refuse(code):
            def chown(fd, u, g):
                raise OSError(code, os.strerror(code))
            return chown
        for code in (errno.EPERM, errno.EINVAL):
            shutil.rmtree(os.path.join(self.store, ".bb"), ignore_errors=True)
            with mock.patch.object(workspace.os, "geteuid", lambda: 0), mock.patch.object(workspace.os, "fchown", refuse(code)):
                workspace.WorkspaceMixin._take_bb(self.store, WHO)
            self.assertTrue(os.path.isdir(os.path.join(self.store, ".bb")), code)
        # Anything else is said, as before.
        with mock.patch.object(workspace.os, "geteuid", lambda: 0), mock.patch.object(workspace.os, "fchown", refuse(errno.EIO)), \
                self.assertRaises(OSError):
            workspace.WorkspaceMixin._take_bb(self.store, WHO)

    def test_a_store_that_is_a_link_is_refused(self):
        real = os.path.join(self.tmp, "real")
        os.makedirs(real)
        shutil.rmtree(self.store)
        os.symlink(real, self.store)
        with self.assertRaises(OSError):
            self.take()
        self.assertEqual(os.listdir(real), [])


class Prune(Tmp):
    def test_a_link_among_the_bundles_is_not_followed(self):
        bb = os.path.join(self.store, ".bb")
        os.makedirs(bb)
        precious = os.path.join(self.tmp, "precious")
        os.makedirs(os.path.join(precious, "deep"))
        with open(os.path.join(precious, "deep", "file"), "w") as f:
            f.write("x")
        names = [f"{i:016x}" for i in range(8)]
        for i, n in enumerate(names):
            os.makedirs(os.path.join(bb, n, "scripts"))
            # A link inside an old bundle, and one at an old bundle's name.
            os.symlink(precious, os.path.join(bb, n, "scripts", "out"))
            os.utime(os.path.join(bb, n), (1000 + i, 1000 + i))
        os.symlink(precious, os.path.join(bb, "f" * 16))
        workspace.WorkspaceMixin.prune_bundles(bb, os.path.join(bb, names[-1]))
        left = sorted(n for n in os.listdir(bb) if n != "f" * 16)
        self.assertEqual(left, names[3:], "the five newest are kept")
        self.assertTrue(os.path.isfile(os.path.join(precious, "deep", "file")))

    def test_a_link_at_bb_itself_prunes_nothing(self):
        elsewhere = os.path.join(self.tmp, "elsewhere")
        for i in range(8):
            os.makedirs(os.path.join(elsewhere, f"{i:016x}"))
        os.symlink(elsewhere, os.path.join(self.store, ".bb"))
        workspace.WorkspaceMixin.prune_bundles(os.path.join(self.store, ".bb"), "")
        self.assertEqual(len(os.listdir(elsewhere)), 8)


class Fake(agent.PackConfigMixin):
    def session_account(self):
        return "nobody-here"


class PackSettings(Tmp):
    def test_a_link_at_bb_or_config_is_replaced_and_never_written_through(self):
        for name in (".bb", "config"):
            with self.subTest(name=name):
                store = os.path.join(self.tmp, "s-" + name)
                elsewhere = os.path.join(self.tmp, "e-" + name)
                os.makedirs(store)
                os.makedirs(elsewhere)
                if name == ".bb":
                    os.symlink(elsewhere, os.path.join(store, ".bb"))
                else:
                    os.makedirs(os.path.join(store, ".bb"))
                    os.symlink(elsewhere, os.path.join(store, ".bb", "config"))
                Fake().pack_config_want([{"pack": "hexkit", "store": store, "env": {"HEX_KEY": "k1"}}])
                self.assertEqual(os.listdir(elsewhere), [], "nothing went through the link")
                d = os.path.join(store, ".bb", "config")
                self.assertFalse(os.path.islink(os.path.join(store, ".bb")))
                self.assertFalse(os.path.islink(d))
                with open(os.path.join(d, "hexkit.env")) as f:
                    self.assertEqual(f.read(), "HEX_KEY=k1\n")

    def test_a_link_at_a_file_s_name_is_replaced_not_followed(self):
        d = os.path.join(self.store, ".bb", "config")
        os.makedirs(d)
        target = os.path.join(self.tmp, "target")
        with open(target, "w") as f:
            f.write("root's own\n")
        os.symlink(target, os.path.join(d, "hexkit.env"))
        os.symlink(target, os.path.join(d, "hexkit.env.tmp"))
        Fake().pack_config_want([{"pack": "hexkit", "store": self.store, "env": {"HEX_KEY": "k1"}}])
        with open(target) as f:
            self.assertEqual(f.read(), "root's own\n")
        self.assertFalse(os.path.islink(os.path.join(d, "hexkit.env")))
        self.assertEqual(stat.S_IMODE(os.stat(os.path.join(d, "hexkit.env")).st_mode), 0o600)

    def test_root_writes_only_into_this_node_s_own_store(self):
        other = os.path.join(self.tmp, "other")
        os.makedirs(other)
        a = Fake()
        a.state = {}
        with mock.patch.object(packconfig, "tc_root", lambda st: self.store), \
                mock.patch.object(packconfig.os, "geteuid", lambda: 0), \
                mock.patch.object(packconfig.os, "fchown", lambda *a, **k: None):
            a.pack_config_want([{"pack": "hexkit", "store": other, "env": {"A": "1"}},
                                {"pack": "hexkit", "store": self.store + "/", "env": {"A": "1"}}])
        self.assertEqual(os.listdir(other), [])
        self.assertTrue(os.path.isfile(os.path.join(self.store, ".bb", "config", "hexkit.env")))


class Sign(Tmp):
    def test_the_store_s_aapt2_runs_as_the_jobs_account(self):
        """A sign job of an .apk: the package is asked of the store's aapt2
        by a process of the account, after the build was fetched into a
        folder still root's alone."""
        bt = os.path.join(self.store, "android", "build-tools", "35.0.0")
        os.makedirs(bt)
        for n in ("zipalign", "apksigner", "aapt2"):
            with open(os.path.join(bt, n), "w") as f:
                f.write("#!/bin/sh\n")
            os.chmod(os.path.join(bt, n), 0o755)
        a = object.__new__(agent.Agent)
        a.state = {"user": "builder", "stores": {"data": self.tmp}}
        a.session_account = lambda: "sessions"
        a.drop_privileges = lambda env: dict(WHO)
        events = []

        class Ctl:
            def fetch(_, path, dest, timeout=600):
                events.append(("fetch", stat.S_IMODE(os.stat(os.path.dirname(dest)).st_mode)))
                with open(dest, "wb") as f:
                    f.write(b"apk")
                return 200, {}

            def call(_, verb, body=None, timeout=30):
                return 500, {"error": "stop here"}
        a.ctl = Ctl()

        def run(argv, **kw):
            events.append(("run", os.path.basename(argv[0]), kw.get("user")))
            return types.SimpleNamespace(stdout="org.example.app\n", stderr="", returncode=0)

        class Job:
            job, outputs, lines = {"id": "j_1"}, [], []

            def say(self, t):
                self.lines.append(t)
        work = agent.module("work")
        with mock.patch.object(work, "tc_root", lambda st: self.store), \
                mock.patch.object(work, "SIGN_WORK", os.path.join(self.tmp, "signwork")), \
                mock.patch.object(work.os, "geteuid", lambda: 0), \
                mock.patch.object(work.os, "chown", lambda p, u, g: events.append(("chown", os.path.basename(p)))), \
                mock.patch.object(work.subprocess, "run", run):
            a.sign(Job(), {"route": "play", "file": "app/build/app.apk"})
        self.assertEqual(events[0], ("fetch", 0o700))
        self.assertEqual([e for e in events if e[0] == "chown"], [("chown", "in.apk"), ("chown", "j_1")],
                         "the folder is given away after the fetch")
        self.assertIn(("run", "aapt2", 1234), events)


class Private(Tmp):
    def test_a_key_file_is_given_away_by_the_file_itself(self):
        keyops = agent.module("keyops")
        owned = []
        with mock.patch.object(keyops.os, "fchown", lambda fd, u, g: owned.append((os.fstat(fd).st_ino, u, g))), \
                mock.patch.object(keyops.os, "chown", side_effect=AssertionError("owned by name")):
            path = keyops.private(self.tmp, "key", b"secret", WHO)
        self.assertEqual(owned, [(os.stat(path).st_ino, 1234, 1234)])
        self.assertEqual(stat.S_IMODE(os.stat(path).st_mode), 0o600)

    def test_a_link_left_at_the_key_s_name_is_refused(self):
        keyops = agent.module("keyops")
        os.symlink(os.path.join(self.tmp, "elsewhere"), os.path.join(self.tmp, "key"))
        with self.assertRaises(OSError):
            keyops.private(self.tmp, "key", b"secret", None)
        self.assertFalse(os.path.exists(os.path.join(self.tmp, "elsewhere")))


class WriteAtomic(Tmp):
    """base.write_atomic in a folder an account may write (a home, a
    store): a link left at the temporary name is taken away, never written
    or owned through."""

    def test_a_link_at_the_temporary_name_is_not_written_or_owned_through(self):
        target = os.path.join(self.tmp, "roots-own")
        with open(target, "w") as f:
            f.write("as it was\n")
        path = os.path.join(self.store, "claude.json")
        os.symlink(target, path + ".new")
        owned = []
        with mock.patch.object(base.os, "fchown", lambda fd, u, g: owned.append((os.fstat(fd).st_ino, u, g))), \
                mock.patch.object(base.os, "chown", side_effect=AssertionError("owned by name")):
            base.write_atomic(path, "the token\n", mode=0o600, uid=1234, gid=1234)
        with open(target) as f:
            self.assertEqual(f.read(), "as it was\n")
        self.assertFalse(os.path.islink(path))
        with open(path) as f:
            self.assertEqual(f.read(), "the token\n")
        self.assertEqual(owned, [(os.stat(path).st_ino, 1234, 1234)])
        self.assertNotEqual(os.stat(target).st_ino, owned[0][0])
        self.assertEqual(stat.S_IMODE(os.stat(path).st_mode), 0o600)

    def test_a_plain_write_is_as_before(self):
        path = os.path.join(self.store, "x.json")
        base.write_atomic(path, b"one")
        base.write_atomic(path, "two")
        with open(path) as f:
            self.assertEqual(f.read(), "two")
        self.assertFalse(os.path.exists(path + ".new"))


if __name__ == "__main__":
    unittest.main()
