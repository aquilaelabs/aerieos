"""A share that stops answering costs the agent one stuck thread, not its
turns: a store's statvfs is waited on for seconds and then read as not
answering, the other mounts are looked at on a thread of their own, and an
NFS mount tries once a pass instead of mount.nfs's two minutes."""
import os
import threading
import time
import unittest
from unittest import mock
import agentpkg  # noqa: E402

agent = agentpkg.load("aerieos_agent")
base = agent.module("base")
stores = agent.module("stores")
extmounts = agent.module("extmounts")


class Stat(unittest.TestCase):
    def setUp(self):
        self.gate = threading.Event()
        real = os.statvfs

        def statvfs(path):
            if path.startswith("/dead"):
                self.gate.wait(30)
            return real("/")
        self.patch = mock.patch.object(base.os, "statvfs", side_effect=statvfs)
        self.patch.start()

    def tearDown(self):
        self.gate.set()
        self.patch.stop()

    def test_a_dead_path_is_given_up_on_in_its_time_and_not_asked_again_while_out(self):
        t0 = time.monotonic()
        with self.assertRaises(base.StatTimeout):
            base.statvfs_within("/dead/a", limit=0.3)
        self.assertLess(time.monotonic() - t0, 2)
        t1 = time.monotonic()
        with self.assertRaises(base.StatTimeout):
            base.statvfs_within("/dead/a", limit=5)
        self.assertLess(time.monotonic() - t1, 0.5, "the call still out is not joined by another")
        self.assertIsNotNone(base.statvfs_within("/", limit=1), "a live path answers")
        self.gate.set()
        time.sleep(0.2)
        self.assertIsNotNone(base.statvfs_within("/dead/a", limit=1), "once it answers it is asked again")

    def test_a_store_that_does_not_answer_reads_as_stuck_and_the_rest_are_measured(self):
        with mock.patch.object(base, "_stat_out", {}):
            t0 = time.monotonic()
            got = stores._stores({"data": "/dead/data", "cache": "/"})
        self.assertLess(time.monotonic() - t0, 5)
        self.assertEqual(got["data"], {"path": "/dead/data", "free_mb": None, "total_mb": None, "stuck": True})
        self.assertIsNotNone(got["cache"]["free_mb"])


class Mounts(unittest.TestCase):
    def test_an_nfs_mount_tries_once(self):
        a = extmounts.ExtMountsMixin()
        argv = a._ext_argv({"kind": "nfs", "name": "exp", "host": "nas", "path": "/export"}, "/mnt/other/exp")
        self.assertIn("retry=0", argv[-1])

    def test_the_pass_runs_on_its_own_thread_once(self):
        a = extmounts.ExtMountsMixin()
        ran = threading.Event()
        with mock.patch.object(extmounts.ExtMountsMixin, "ext_mounts_pass", side_effect=lambda *x, **k: ran.set()):
            a.ext_mounts_start()
            first = a._ext_thread
            a.ext_mounts_start()
            self.assertIs(a._ext_thread, first)
            self.assertTrue(ran.wait(5))
        self.assertEqual(first.name, "extmounts")

    def test_a_mount_that_does_not_finish_is_said_on_its_row(self):
        a = extmounts.ExtMountsMixin()
        a.state = {"ext_mounts": [{"id": "x_1", "kind": "nfs", "name": "exp", "host": "nas", "path": "/export", "on": True}]}
        root = os.path.join(os.environ.get("TMPDIR", "/tmp"), f"ext-{os.getpid()}")

        def run(argv, **kw):
            raise extmounts.subprocess.TimeoutExpired(argv, 120)
        with mock.patch.dict(os.environ, {"BB_OTHER_ROOT": root}), mock.patch.object(extmounts.os, "geteuid", return_value=0), \
                mock.patch.object(extmounts, "save_state"), mock.patch.object(extmounts.subprocess, "run", side_effect=run), \
                mock.patch.object(extmounts.os.path, "ismount", return_value=False):
            a.ext_mounts_pass()
        self.assertEqual(a.state["ext_errors"], {"x_1": "did not answer in two minutes"})


if __name__ == "__main__":
    unittest.main()
