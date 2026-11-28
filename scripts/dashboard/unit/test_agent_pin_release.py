"""An agent the vendor installs as a release folder (Codex CLI: bin/codex,
bin/codex-code-mode-host, codex-resources) is pinned whole, with the command
and its helpers links into it, so it finds its helpers beside itself
(only bin/codex was copied, and every command a Codex session ran failed).

What is pinned is read out of the account's home by a process of the
account and written by root: root follows no name there, and what the
account's process sends is held to plain files, folders and links that stay
inside the pinned folder."""
import io
import os
import stat
import tarfile
import types
import sys
import tempfile
import unittest
from unittest import mock

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)
import agentpkg  # noqa: E402
agent = agentpkg.load("aerieos_agent_pin_release")


def release(root, version):
    os.makedirs(os.path.join(root, "bin"))
    os.makedirs(os.path.join(root, "codex-resources"))
    for f in ("codex", "codex-code-mode-host"):
        with open(os.path.join(root, "bin", f), "w") as fh:
            fh.write(f"#!/bin/sh\necho {f} {version}\n")
        os.chmod(os.path.join(root, "bin", f), 0o755)
    with open(os.path.join(root, "codex-resources", "rg"), "w") as fh:
        fh.write("rg")


class PinRelease(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.mkdtemp()
        self.pin = os.path.join(self.tmp, "agents", "codex")
        os.makedirs(self.pin)

    def test_the_whole_release_is_pinned_and_the_helper_sits_beside_the_command(self):
        src = os.path.join(self.tmp, "rel1")
        release(src, "0.163.0")
        agent._pin_release(self.pin, "codex", src)
        for f in ("codex", "codex-code-mode-host"):
            self.assertTrue(os.path.islink(os.path.join(self.pin, f)), f)
            self.assertTrue(os.access(os.path.join(self.pin, f), os.X_OK), f)
        real = os.path.realpath(os.path.join(self.pin, "codex"))
        self.assertTrue(os.path.exists(os.path.join(os.path.dirname(real), "codex-code-mode-host")))
        self.assertTrue(os.path.exists(os.path.join(self.pin, "release", "codex-resources", "rg")))

    def test_an_update_replaces_the_release_whole(self):
        a, b = os.path.join(self.tmp, "rel1"), os.path.join(self.tmp, "rel2")
        release(a, "0.163.0")
        release(b, "0.164.0")
        agent._pin_release(self.pin, "codex", a)
        agent._pin_release(self.pin, "codex", b)
        with open(os.path.join(self.pin, "codex")) as fh:
            self.assertIn("0.164.0", fh.read())
        self.assertFalse(os.path.exists(os.path.join(self.pin, ".release.old")))
        self.assertFalse(os.path.exists(os.path.join(self.pin, ".release.new")))


class ReadAsTheAccount(unittest.TestCase):
    WHO = {"user": 1234, "group": 1234, "extra_groups": []}

    def setUp(self):
        self.tmp = tempfile.mkdtemp()
        self.sessions = agent.module("sessions")

    def started(self, out):
        """Popen stood in for: what it was asked, and `out` as what the
        account's process wrote."""
        asked = []

        def popen(argv, **kw):
            asked.append((argv, kw))
            return types.SimpleNamespace(stdout=io.BytesIO(out), wait=lambda: 0)
        return asked, mock.patch.object(self.sessions.subprocess, "Popen", popen)

    def test_one_binary_is_read_by_the_account_s_process_and_written_by_root(self):
        asked, patched = self.started(b"#!/bin/sh\necho 1.2.3\n")
        dest = os.path.join(self.tmp, "claude.new")
        os.symlink(os.path.join(self.tmp, "elsewhere"), dest)     # left from before: replaced, not followed
        with patched, mock.patch.object(self.sessions.shutil, "copy2", side_effect=AssertionError("root read the account's file")):
            self.sessions._file_as(self.WHO, "/home/builder/.local/bin/claude", dest)
        (argv, kw), = asked
        self.assertEqual(argv, ["cat", "--", "/home/builder/.local/bin/claude"])
        self.assertEqual((kw["user"], kw["group"], kw["extra_groups"]), (1234, 1234, []))
        self.assertFalse(os.path.islink(dest))
        self.assertFalse(os.path.exists(os.path.join(self.tmp, "elsewhere")))
        self.assertEqual(stat.S_IMODE(os.stat(dest).st_mode), 0o755)
        with open(dest, "rb") as f:
            self.assertEqual(f.read(), b"#!/bin/sh\necho 1.2.3\n")

    def test_a_file_the_account_cannot_read_is_not_pinned(self):
        src = os.path.join(self.tmp, "gone")
        dest = os.path.join(self.tmp, "claude.new")
        with self.assertRaises(OSError):
            self.sessions._file_as({}, src, dest)
        self.assertFalse(os.path.exists(dest))

    def a_tar(self, members):
        buf = io.BytesIO()
        with tarfile.open(fileobj=buf, mode="w|") as tar:
            for name, kind, data in members:
                info = tarfile.TarInfo(name)
                if kind == "dir":
                    info.type, info.mode = tarfile.DIRTYPE, 0o700
                elif kind == "link":
                    info.type, info.linkname = tarfile.SYMTYPE, data
                elif kind == "fifo":
                    info.type = tarfile.FIFOTYPE
                else:
                    info.size, info.mode = len(data), kind
                tar.addfile(info, io.BytesIO(data) if isinstance(data, bytes) else None)
        return buf.getvalue()

    def test_a_release_is_read_by_the_account_s_process(self):
        asked, patched = self.started(self.a_tar([("./bin", "dir", None), ("./bin/codex", 0o700, b"x"),
                                                  ("./notes", 0o600, b"n"), ("./bin/also", "link", "codex"),
                                                  ("./pipe", "fifo", None)]))
        new = os.path.join(self.tmp, "new")
        with patched:
            self.sessions._tree_as(self.WHO, "/home/builder/.codex/pkg", new)
        (argv, kw), = asked
        self.assertEqual(argv[-1], "/home/builder/.codex/pkg")
        self.assertEqual(kw["user"], 1234)
        self.assertEqual(stat.S_IMODE(os.stat(os.path.join(new, "bin", "codex")).st_mode), 0o755)
        self.assertEqual(stat.S_IMODE(os.stat(os.path.join(new, "notes")).st_mode), 0o644)
        self.assertEqual(stat.S_IMODE(os.stat(os.path.join(new, "bin")).st_mode), 0o755)
        self.assertEqual(os.readlink(os.path.join(new, "bin", "also")), "codex")
        self.assertFalse(os.path.lexists(os.path.join(new, "pipe")), "nothing but files, folders and links")

    def test_what_the_account_sends_cannot_leave_the_folder(self):
        outside = os.path.join(self.tmp, "outside")
        os.makedirs(outside)
        for members in ([("../outside/x", 0o644, b"x")],
                        [(outside + "/x", 0o644, b"x")],
                        # A link out, then a file through it.
                        [("./out", "link", outside), ("./out/x", 0o644, b"x")],
                        [("./out", "link", "../outside"), ("./out/x", 0o644, b"x")]):
            new = os.path.join(self.tmp, "new")
            _asked, patched = self.started(self.a_tar(members))
            with self.subTest(members=members), patched:
                try:
                    self.sessions._tree_as(self.WHO, "/home/builder/rel", new)
                except OSError:
                    pass
                self.assertEqual(os.listdir(outside), [])
                self.assertFalse(os.path.lexists(os.path.join(new, "out")), "a link that leaves is not made")
            import shutil
            shutil.rmtree(new, ignore_errors=True)

    def test_a_chain_of_links_each_inside_by_its_words_is_refused(self):
        # A link deep in the folder back to its top, and a link whose words
        # go down through it and up again: each reads as inside, and the
        # second leads out once the first is followed.
        outside = os.path.join(self.tmp, "home", "writable-by-account")
        os.makedirs(outside)
        deep = [f"d{i}" for i in range(12)]
        members = [("./bin", "dir", None)] + [("./" + "/".join(deep[:i + 1]), "dir", None) for i in range(12)]
        members.append(("./" + "/".join(deep) + "/L", "link", "/".join([".."] * 12)))
        new = os.path.join(self.tmp, "pin", ".release.new")
        up = "/".join([".."] + deep + ["L"] + [".."] * 13)
        members.append(("./bin/codex-helper", "link", up + outside + "/codex-helper"))
        os.makedirs(os.path.dirname(new))
        _asked, patched = self.started(self.a_tar(members))
        with patched, self.assertRaises(OSError) as said:
            self.sessions._tree_as(self.WHO, "/home/builder/rel", new)
        self.assertIn("leads outside the folder", str(said.exception))
        self.assertFalse(os.path.lexists(new), "and nothing of it is left for a pin to take")


class ReleaseRoot(unittest.TestCase):
    """Only a link into a vendor's own folder pins a release whole:
    Copilot CLI's binary IS the file in ~/.local/bin, and its "release" was
    the account's whole ~/.local."""

    def setUp(self):
        self.home = tempfile.mkdtemp()
        os.makedirs(os.path.join(self.home, ".local", "bin"))

    def test_a_link_into_the_vendor_s_folder_is_a_release(self):
        rel = os.path.join(self.home, ".codex", "packages", "standalone", "0.164.0")
        release(rel, "0.164.0")
        exe = os.path.join(self.home, ".local", "bin", "codex")
        os.symlink(os.path.join(rel, "bin", "codex"), exe)
        self.assertEqual(agent._release_root(exe, os.path.realpath(exe), self.home), os.path.realpath(rel))

    def test_a_binary_in_local_bin_is_one_binary(self):
        exe = os.path.join(self.home, ".local", "bin", "copilot")
        with open(exe, "w") as f:
            f.write("#!/bin/sh\n")
        self.assertEqual(agent._release_root(exe, os.path.realpath(exe), self.home), "")


if __name__ == "__main__":
    unittest.main()
