"""Older versions kept (R201): a version an update pushes out of its slot is
kept as files on the data partition with its configuration's copy, on GRUB's
menu and This machine; only an image that can boot that way, the oldest going
first, never stopping the update. A visit lasts one boot: the configuration a
visit needs goes in and comes back when it ends."""
import os
import subprocess
import sys
import tarfile
import tempfile
import unittest
from unittest import mock

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, os.path.join(HERE, ".."))
import agentpkg  # noqa: E402

ROOT = os.path.abspath(os.path.join(HERE, "..", "..", ".."))
EXTRA = os.path.join(ROOT, "image", "mkosi.extra")
OS = os.path.join(EXTRA, "usr", "lib", "builderbot-os")
agent = agentpkg.load("builderbot_agent_kept")
av = sys.modules[agent.Agent.__module__.rsplit(".", 1)[0] + ".osimage"]


def read(*p):
    with open(os.path.join(*p), encoding="utf-8") as f:
        return f.read()


class Job:
    def __init__(self):
        self.out = []

    def say(self, s):
        self.out.append(s)


class World:
    def __init__(self, d):
        self.d = d
        self.env = {"BB_OS_WORK": os.path.join(d, "work"), "BB_OS_ESP": os.path.join(d, "esp"), "BB_CMDLINE": os.path.join(d, "cmdline")}
        os.makedirs(os.path.join(d, "esp", "grub"))
        os.makedirs(os.path.join(d, "work"))
        open(self.env["BB_CMDLINE"], "w").write("bbslot=a\n")

    def slot(self, ver, boots=True, state=False):
        """A slot holding `ver`: the partition's file and its kernel's folder."""
        dev = os.path.join(self.d, f"dev-{ver}")
        root = b"hsqs" + b"\0" * 36 + (4096).to_bytes(8, "little") + b"r" * (4096 - 48)
        open(dev, "wb").write(root + b"\xff" * 8192)
        where = os.path.join(self.d, f"esp-{ver}")
        os.makedirs(where)
        for p in ("vmlinuz", "initrd"):
            open(os.path.join(where, p), "w").write(p)
        open(os.path.join(where, "release"), "w").write(f"BUILDERBOT_OS_VERSION={ver}\n" + ("BUILDERBOT_OS_BOOTS_KEPT=1\n" if boots else ""))
        if state:
            os.makedirs(os.path.join(self.env["BB_OS_WORK"], "before"), exist_ok=True)
            open(os.path.join(self.env["BB_OS_WORK"], "before", f"{ver}.tar.gz"), "w").write("copy")
        return dev, where


class Keeping(unittest.TestCase):
    def setUp(self):
        t = tempfile.TemporaryDirectory()
        self.addCleanup(t.cleanup)
        self.w = World(t.name)
        p = mock.patch.dict(os.environ, self.w.env)
        p.start()
        self.addCleanup(p.stop)

    def keep(self, ver, keep=3, **kw):
        said = []
        av.keep_slot(said.append, *self.w.slot(ver, **kw), keep)
        return "".join(said)

    def test_a_version_pushed_out_is_kept_and_on_the_menu(self):
        self.assertIn("kept as an older version", self.keep("0.9.1", state=True))
        rows = av.kept_list()
        self.assertEqual([(r["version"], r["state"]) for r in rows], [("0.9.1", True)])
        d = os.path.join(av.kept_dir(), "0.9.1")
        self.assertEqual(os.path.getsize(os.path.join(d, "root.squashfs")), 4096, "the squashfs's own bytes, not the partition's")
        menu = read(self.w.env["BB_OS_ESP"], "grub", "kept.cfg")
        for word in ('submenu "Older versions" --id older', "--id kept-0.9.1", "bbkept=0.9.1", ",gpt5)", "/lib/builderbot-os/kept/0.9.1/vmlinuz",
                     "root=/dev/loop0", "panic=15", "export bb_data"):
            self.assertIn(word, menu)

    def test_the_oldest_goes_first_and_none_is_none(self):
        for i, v in enumerate(("0.9.1", "0.9.2", "0.9.3", "0.9.4")):
            self.keep(v)
            os.utime(os.path.join(av.kept_dir(), v, "root.squashfs"), (1000 + i, 1000 + i))
        self.assertEqual([r["version"] for r in av.kept_list()], ["0.9.4", "0.9.3", "0.9.2"])
        self.keep("0.9.5", keep=0)
        self.assertEqual(av.kept_list(), [])
        self.assertEqual(read(self.w.env["BB_OS_ESP"], "grub", "kept.cfg"), "", "an empty menu")

    def test_what_is_not_kept_is_said_and_stops_nothing(self):
        self.assertIn("built before", self.keep("0.9.0", boots=False))
        self.assertEqual(av.kept_list(), [])
        said = []
        av.keep_slot(said.append, os.path.join(self.w.d, "nodev"), os.path.join(self.w.d, "noslot"))
        self.assertEqual(said, [], "an empty slot has nothing to say")
        dev, where = self.w.slot("0.9.6")
        open(dev, "wb").write(b"not a squashfs" * 10)
        av.keep_slot(said.append, dev, where)
        self.assertIn("does not hold a squashfs", "".join(said))
        with mock.patch.object(av.os, "statvfs", return_value=mock.Mock(f_bavail=1, f_frsize=4096)):
            self.assertIn("too little room", self.keep("0.9.7"))
        dev, where = self.w.slot("0.9.8")
        os.unlink(os.path.join(where, "initrd"))
        said = []
        av.keep_slot(said.append, dev, where)
        self.assertIn("was not kept", "".join(said), "a failure is said, and raises nothing")
        self.assertFalse(os.path.exists(os.path.join(av.kept_dir(), "0.9.8.new")), "nothing half kept")

    def test_the_job_boots_one_next_or_removes_it(self):
        self.keep("0.9.1")

        class A(av.OsImageMixin):
            ran = []

            def _sh(self, job, argv, **kw):
                self.ran.append(argv)
                return 0

            def hello_again(self, why):
                pass
        tool = os.path.join(self.w.d, "slot")
        open(tool, "w").close()
        with mock.patch.dict(os.environ, {"BB_OS_SLOT": tool}):
            self.assertEqual(A()._apply_os_kept(Job(), {"verb": "next", "version": "0.9.1"}), ("succeeded", 0))
            self.assertEqual(A.ran[-1][-2:], ["kept-next", "0.9.1"])
            self.assertEqual(A()._apply_os_kept(Job(), {"verb": "next", "version": "../../etc"}), ("failed", 64))
            self.assertEqual(A()._apply_os_kept(Job(), {"verb": "other", "version": "0.9.1"}), ("failed", 64))
            open(self.w.env["BB_CMDLINE"], "w").write("bbslot=a bbkept=0.9.1\n")
            self.assertEqual(av.kept_boot(), "0.9.1")
            self.assertEqual(A()._apply_os_kept(Job(), {"verb": "remove", "version": "0.9.1"}), ("failed", 65), "not the one running")
            open(self.w.env["BB_CMDLINE"], "w").write("bbslot=a\n")
            self.assertEqual(A()._apply_os_kept(Job(), {"verb": "remove", "version": "0.9.1"}), ("succeeded", 0))
            self.assertEqual(A.ran[-1][-1], "kept-next", "and no boot of it stays named")
        self.assertEqual(av.kept_list(), [])


class TheBoot(unittest.TestCase):
    def test_the_menu_and_the_initramfs_know_a_kept_version(self):
        g = read(ROOT, "image", "grub.cfg")
        self.assertIn('set default="older>kept-${bb_kept_next}"', g)
        self.assertIn("save_env bb_kept_next", g, "the word is spent, so it is one boot")
        self.assertIn("source $prefix/kept.cfg", g)
        init = read(EXTRA, "etc", "initramfs-tools", "scripts", "local-top", "builderbot-os-toram")
        self.assertIn("bbkept=*", init)
        self.assertIn("/run/bbdata/lib/builderbot-os/kept/$kept/root.squashfs", init)
        self.assertIn("umount /run/bbdata", init, "free for init-bottom to mount read-write")
        self.assertIn("BUILDERBOT_OS_BOOTS_KEPT=1", read(ROOT, "image", "build.sh"))
        self.assertIn("boot-menu", read(EXTRA, "usr", "lib", "systemd", "system", "builderbot-os-restore.service"))

    def test_the_boot_menu_follows_the_image_but_not_on_a_visit(self):
        with tempfile.TemporaryDirectory() as d:
            os.makedirs(os.path.join(d, "grub"))
            open(os.path.join(d, "grub", "grub.cfg"), "w").write("old")
            open(os.path.join(d, "new"), "w").write("new")
            open(os.path.join(d, "cmd"), "w").write("bbslot=a bbkept=0.9.1\n")
            env = dict(os.environ, BB_ESP=d, BB_OS_GRUBCFG=os.path.join(d, "new"), BB_CMDLINE=os.path.join(d, "cmd"))
            tool = os.path.join(OS, "boot-menu")
            subprocess.run(["bash", tool], env=env, check=True)
            self.assertEqual(read(d, "grub", "grub.cfg"), "old")
            open(os.path.join(d, "cmd"), "w").write("bbslot=a\n")
            subprocess.run(["bash", tool], env=env, check=True)
            self.assertEqual(read(d, "grub", "grub.cfg"), "new")

    def test_a_visit_takes_its_configuration_and_gives_yours_back(self):
        with tempfile.TemporaryDirectory() as d:
            slot = os.path.join(d, "slot")
            open(slot, "w").write('#!/bin/sh\necho no\n')
            opt = os.path.join(d, "opt")
            os.makedirs(os.path.join(opt, "scripts", "dashboard"))
            open(os.path.join(opt, "scripts", "dashboard", "stateversion.py"), "w").write("import sys\nsys.exit(78)\n")
            rel = os.path.join(d, "release")
            open(rel, "w").write("BUILDERBOT_OS_VERSION=0.9.1\n")
            state = os.path.join(d, "var", "config")
            os.makedirs(state)
            open(os.path.join(state, "state.json"), "w").write("yours")
            os.makedirs(os.path.join(d, "old", "config"))
            open(os.path.join(d, "old", "config", "state.json"), "w").write("its")
            kept = os.path.join(d, "work", "kept", "0.9.1")
            os.makedirs(kept)
            with tarfile.open(os.path.join(kept, "state.tar.gz"), "w:gz") as t:
                t.add(os.path.join(d, "old", "config"), arcname="config")
            cmd = os.path.join(d, "cmd")
            env = dict(os.environ, BB_OS_SLOT=slot, BB_OS_WORK=os.path.join(d, "work"), BB_OS_STATE=state, BB_OS_OPT=opt, BB_OS_RELEASE=rel, BB_CMDLINE=cmd)
            tool = os.path.join(OS, "restore-before")
            open(cmd, "w").write("bbslot=a bbkept=0.9.1\n")
            r = subprocess.run(["bash", tool], env=env, capture_output=True, text=True, check=False)
            self.assertEqual(r.returncode, 0, r.stderr)
            self.assertEqual(read(state, "state.json"), "its", r.stdout)
            open(os.path.join(state, "state.json"), "w").write("its, changed on the visit")
            open(cmd, "w").write("bbslot=a\n")
            r = subprocess.run(["bash", tool], env=env, capture_output=True, text=True, check=False)
            self.assertEqual(r.returncode, 0, r.stderr)
            self.assertEqual(read(state, "state.json"), "yours", r.stdout)
            self.assertFalse(os.path.exists(os.path.join(d, "work", "kept-set-aside")))
            seen = [x for x in os.listdir(os.path.join(d, "work")) if x.endswith("-visit")]
            self.assertEqual(read(d, "work", seen[0], "config", "state.json"), "its, changed on the visit", "never deleted")


class TheController(unittest.TestCase):
    def test_the_census_keeps_the_shape_and_the_verb_is_the_machines(self):
        import nodes
        got = nodes._census({"os_kept": {"booted": "0.9.1;x", "versions": [{"version": "0.9.1", "mb": 2048, "at": 5, "state": True, "evil": 1}, "no"]}})
        self.assertEqual(got["os_kept"], {"booted": "0.9.1x", "versions": [{"version": "0.9.1", "mb": 2048, "at": 5, "state": True}]})
        self.assertNotIn("os_kept", nodes._census({"os_kept": {"versions": [], "booted": ""}}))
        nodes.configure(state=tempfile.mkdtemp())
        self.assertEqual(nodes.node_os_kept("user:t", "n_nothere", "next", "0.9.1").get("error"), "no such node")


if __name__ == "__main__":
    unittest.main()
