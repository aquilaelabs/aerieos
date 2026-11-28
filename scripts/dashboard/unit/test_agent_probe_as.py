"""The root agent asks a binary for its version as the account that owns
it, as root only where the binary and every folder above it are root's
alone, and as nobody otherwise (a build or a session could replace
the toolchain store's java or its own claude, which root ran). The name is
looked at once and the file it led to is what runs: a link in a store the
jobs account writes could otherwise be pointed at a root-owned program for
the look and at its own file for the run."""
import os
import shutil
import stat
import sys
import tempfile
import unittest
from unittest import mock

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "..", "agent"))
from aerieos_agent import base  # noqa: E402

ROOTS = {"user": 65534, "group": 65534, "extra_groups": []}


def st(uid, mode, kind=stat.S_IFREG):
    return mock.Mock(st_uid=uid, st_gid=uid, st_mode=kind | mode)


class ProbeAs(unittest.TestCase):
    def as_(self, uid, mode, folders=None):
        """What a root agent decides for /s/jdk/bin/java, owned by `uid`
        with `mode`, its folders root's 755 unless `folders` says."""
        folders = folders or {}

        def stat_of(p):
            if p == "/s/jdk/bin/java":
                return st(uid, mode)
            return folders.get(p) or st(0, 0o755, stat.S_IFDIR)
        with mock.patch.object(base.os, "geteuid", return_value=0), \
                mock.patch.object(base.os.path, "realpath", lambda p: p), \
                mock.patch.object(base.os, "stat", stat_of):
            return base._probe_as("/s/jdk/bin/java")

    def test_a_binary_an_account_owns_runs_as_that_account(self):
        self.assertEqual(self.as_(1001, 0o755), {"executable": "/s/jdk/bin/java", "user": 1001, "group": 1001, "extra_groups": []})

    def test_one_root_owns_that_others_may_write_runs_as_nobody(self):
        self.assertEqual(self.as_(0, 0o775)["user"], 65534)
        self.assertEqual(self.as_(0, 0o757)["user"], 65534)

    def test_one_root_owns_in_a_folder_an_account_writes_runs_as_nobody(self):
        self.assertEqual(self.as_(0, 0o755, {"/s/jdk": st(1001, 0o755, stat.S_IFDIR)})["user"], 65534)
        self.assertEqual(self.as_(0, 0o755, {"/s": st(0, 0o777, stat.S_IFDIR)})["user"], 65534)

    def test_one_root_alone_may_write_runs_as_root(self):
        self.assertEqual(self.as_(0, 0o755), {"executable": "/s/jdk/bin/java"})

    def test_nothing_there_runs_as_nobody(self):
        with mock.patch.object(base.os, "geteuid", return_value=0):
            self.assertEqual(base._probe_as("/nowhere/at/all/java"), ROOTS)

    def test_not_root_changes_nothing(self):
        with mock.patch.object(base.os, "geteuid", return_value=1000):
            self.assertEqual(base._probe_as("/bin/sh"), {})

    def test_a_link_runs_the_file_it_led_to_when_looked_at(self):
        true = os.path.realpath(shutil.which("true") or "/bin/true")
        d = tempfile.mkdtemp()
        self.addCleanup(shutil.rmtree, d, True)
        link = os.path.join(d, "java")
        os.symlink(true, link)                  # the account's link, to a program root's alone
        ran = []

        def run(argv, **kw):
            ran.append((argv, kw))
            return mock.Mock(stdout="1.0", stderr="", returncode=0)
        with mock.patch.object(base.os, "geteuid", return_value=0), mock.patch.object(base.subprocess, "run", run):
            base._probe([link, "--version"])
        argv, kw = ran[0]
        self.assertEqual(argv, [link, "--version"], "the name it was asked by is its argv[0]")
        self.assertEqual(kw.get("executable"), true, "and what runs is the file the look found, whatever the link says by then")
        if base._root_alone(true):
            self.assertNotIn("user", kw)
        else:
            self.assertEqual(kw.get("user"), 65534)


if __name__ == "__main__":
    unittest.main()
