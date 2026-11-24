"""Backups off the machine (R162 step 5): the controller's record held to
its shapes and summarized for Home and the bell, and the agent's job
copying with rsync, each run hard-linked to the one before, the oldest
pruned, a failed run leaving nothing, and a destination not mounted
refused so nothing lands on the system disk."""
import json
import os
import shutil
import sys
import tempfile
import unittest
from unittest import mock

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, os.path.join(HERE, ".."))
import agentpkg  # noqa: E402
import storebackups  # noqa: E402


class TheRecord(unittest.TestCase):
    def setUp(self):
        self.d = tempfile.mkdtemp()
        self.addCleanup(shutil.rmtree, self.d, True)
        storebackups.configure(state=self.d, write_json=lambda p, v: open(p, "w").write(json.dumps(v)))

    def test_held_to_its_shapes_and_summarized(self):
        self.assertIn("name is a letter", storebackups.set_backup({"name": "Bad!", "source": "/mnt/tank/m", "dest": "/mnt/other/b"})["error"])
        self.assertIn("folders under /mnt", storebackups.set_backup({"name": "m", "source": "/home/x", "dest": "/mnt/other/b"})["error"])
        self.assertIn("other than inside", storebackups.set_backup({"name": "m", "source": "/mnt/tank", "dest": "/mnt/tank/backups"})["error"])
        self.assertIn("1 to 365", storebackups.set_backup({"name": "m", "source": "/mnt/tank/m", "dest": "/mnt/other/b", "keep": 0})["error"])
        r = storebackups.set_backup({"name": "media", "source": "/mnt/tank/media/", "dest": "/mnt/other/usb", "keep": 5})["backup"]
        self.assertEqual((r["source"], r["dest"], r["keep"], r["on"]), ("/mnt/tank/media", "/mnt/other/usb", 5, True))
        self.assertEqual(storebackups.wanted(), [{"id": r["id"], "name": "media", "source": "/mnt/tank/media", "dest": "/mnt/other/usb", "keep": 5}])
        self.assertIn("taken", storebackups.set_backup({"name": "media", "source": "/mnt/a", "dest": "/mnt/b"})["error"])
        storebackups.set_backup({"name": "state", "source": "/var/lib/aerieos-controller", "dest": "/mnt/array/backups"})
        now = 1_700_000_000
        sm = storebackups.summary([{"name": "media", "ok": True, "last_at": now - 3600}, {"name": "state", "ok": False, "last_at": now - 100, "error": "rsync exit 23"}],
                                  scheduled_names={"media", "state"}, now=now)
        self.assertEqual((sm["count"], sm["failed"], sm["stale"], sm["newest_ok_at"]), (2, ["state"], [], now - 3600))
        sm = storebackups.summary([{"name": "media", "ok": True, "last_at": now - 3 * 86400}], scheduled_names={"media", "state"}, now=now)
        self.assertEqual((sm["failed"], sm["stale"]), ([], ["media", "state"]), "an old good run and one that never ran are stale, scheduled")
        self.assertEqual(storebackups.summary([], scheduled_names=set(), now=now)["stale"], [], "unscheduled, never stale")
        self.assertTrue(storebackups.remove(r["id"])["ok"])


class TheAgent(unittest.TestCase):
    def setUp(self):
        self.agent = agentpkg.load("aerieos_agent_backups")
        self.bm = sys.modules[self.agent.Agent.__module__.rsplit(".", 1)[0] + ".backups"]
        self.d = tempfile.mkdtemp()
        self.addCleanup(shutil.rmtree, self.d, True)
        self.src, self.dest = os.path.join(self.d, "mnt", "tank", "media"), os.path.join(self.d, "mnt", "other", "usb")
        os.makedirs(self.src); os.makedirs(self.dest)
        open(os.path.join(self.src, "a.txt"), "w").write("hello")
        self.env = {"BB_BACKUPS_STATE": os.path.join(self.d, "state.json")}
        bm = self.bm
        ran = self.ran = []

        class A(bm.BackupsMixin):
            def __init__(self):
                self.state = {"store_backups": [{"id": "b_1", "name": "media", "source": "/mnt/tank/media", "dest": "/mnt/other/usb", "keep": 2}]}

            def _sh(self, job, argv, timeout=0, pass_fds=(), **kw):
                # rsync is handed held folders: kept here as the paths each
                # reaches now, by the descriptors it was handed.
                for x in argv:
                    if x.startswith("/proc/self/fd/"):
                        assert int(x.split("/")[4]) in pass_fds, (x, pass_fds)
                ran.append([os.path.realpath(x) if x.startswith("/proc/self/fd/") else x for x in argv])
                (getattr(self, "during", None) or (lambda: None))()
                # rsync's work: the partial folder filled.
                part = argv[-1].rstrip("/")
                os.makedirs(part, exist_ok=True); open(os.path.join(part, "a.txt"), "w").write("hello")
                return 0

            def hello_again(self, why):
                self.said = why
        self.A = A
        self.job = type("J", (), {"log": [], "say": lambda s, t: s.log.append(t), "text": lambda s: "".join(s.log)})()

    def run_job(self, a, cfg, stamp, mounted=True, swap_dest=True, owner=None):
        real = {"/mnt/tank/media": self.src, **({"/mnt/other/usb": self.dest} if swap_dest else {})}
        # Root here is this test's own account, unless a test says who.
        with mock.patch.dict(os.environ, self.env), mock.patch.object(self.bm.os, "geteuid", return_value=0), \
             mock.patch.object(self.bm, "OWNER", os.getuid() if owner is None else owner), \
             mock.patch.object(self.bm.shutil, "which", return_value="/usr/bin/rsync"), mock.patch.object(self.bm.time, "strftime", return_value=stamp), \
             mock.patch.object(self.bm.os.path, "ismount", side_effect=lambda p: mounted and p.startswith("/mnt/other/usb")), \
             mock.patch.object(self.bm, "_du_mb", return_value=1), mock.patch.object(self.bm, "log"):
            # The record's paths are real folders here: swapped in under the job.
            for r in a.state["store_backups"]:
                r["source"], r["dest"] = real.get(r["source"], r["source"]), real.get(r["dest"], r["dest"])
            with mock.patch.object(self.bm, "ROOTS", (self.d, "/mnt/")):
                got = a._apply_storage_backup(self.job, cfg)
            for r in a.state["store_backups"]:
                r["source"], r["dest"] = "/mnt/tank/media", "/mnt/other/usb"
            return got

    def test_runs_are_dated_linked_and_pruned(self):
        a = self.A()
        self.assertEqual(self.run_job(a, {"name": "media"}, "20261028-040000"), ("succeeded", 0), self.job.text())
        self.assertEqual(self.ran[-1][0], "/usr/bin/rsync")
        self.assertNotIn("--link-dest", self.ran[-1], "nothing before the first run")
        self.assertEqual(self.ran[-1][-2:], [os.path.realpath(self.src), os.path.realpath(os.path.join(self.dest, "media", "20261028-040000.partial"))])
        self.assertEqual(os.readlink(os.path.join(self.dest, "media", "latest")), "20261028-040000")
        self.run_job(a, {"name": "media"}, "20261029-040000")
        self.assertIn("--link-dest", self.ran[-1])
        self.assertEqual(self.ran[-1][self.ran[-1].index("--link-dest") + 1], os.path.realpath(os.path.join(self.dest, "media", "20261028-040000")))
        self.run_job(a, {"name": "media"}, "20261030-040000")
        kept = sorted(d for d in os.listdir(os.path.join(self.dest, "media")) if d[0].isdigit())
        self.assertEqual(kept, ["20261029-040000", "20261030-040000"], "two kept, the oldest pruned")
        st = json.load(open(self.env["BB_BACKUPS_STATE"]))["media"]
        self.assertEqual((st["ok"], st["runs"], st["size_mb"]), (True, 2, 1))
        with mock.patch.dict(os.environ, self.env):
            rows = self.bm.backups_now(a.state)
        self.assertEqual((rows[0]["name"], rows[0]["ok"], rows[0]["runs"]), ("media", True, 2))

    def test_a_destination_that_keeps_no_modes_takes_no_secrets(self):
        # B861: exFAT, FAT or a share with one mode for every file shows
        # root's copy to whoever can reach it: the controller's state is
        # refused there, and anything else goes with that said.
        a = self.A()
        with mock.patch.object(self.bm, "_keeps_modes", return_value=False), \
                mock.patch.object(self.bm, "STATE_ROOT", os.path.realpath(self.src)):
            self.assertEqual(self.run_job(a, {"name": "media"}, "20261028-040000"), ("failed", 64), self.job.text())
        self.assertIn("keeps no file modes", self.job.text())
        self.assertIn("controller's secrets", self.job.text())
        self.assertEqual(self.ran, [], "rsync is not run")
        self.assertEqual(os.listdir(os.path.join(self.dest, "media")), [], "the partial run is gone")
        self.job.log.clear()
        with mock.patch.object(self.bm, "_keeps_modes", return_value=False):
            self.assertEqual(self.run_job(a, {"name": "media"}, "20261029-040000"), ("succeeded", 0), self.job.text())
        self.assertIn("note:", self.job.text())

    def test_a_folder_that_kept_its_modes_is_told_from_one_that_did_not(self):
        fd = os.open(self.dest, os.O_RDONLY | os.O_DIRECTORY)
        self.addCleanup(os.close, fd)
        os.mkdir("run", 0o700, dir_fd=fd)
        self.assertTrue(self.bm._keeps_modes(fd, "run"))
        self.assertEqual(os.listdir(os.path.join(self.dest, "run")), [], "the probe file is gone")
        os.chmod(os.path.join(self.dest, "run"), 0o777)
        self.assertFalse(self.bm._keeps_modes(fd, "run"))

    def test_a_link_at_the_backups_name_is_refused(self):
        # A share user may write the destination: a link left at the
        # backup's name would take root's copy, and its deletions, anywhere.
        elsewhere = os.path.join(self.d, "etc")
        os.makedirs(elsewhere)
        open(os.path.join(elsewhere, "keep"), "w").write("root's own")
        os.symlink(elsewhere, os.path.join(self.dest, "media"))
        a = self.A()
        self.assertEqual(self.run_job(a, {"name": "media"}, "20261028-040000"), ("failed", 64), self.job.text())
        self.assertIn("leads somewhere else", self.job.text())
        self.assertEqual(self.ran, [], "rsync is not run")
        self.assertEqual(os.listdir(elsewhere), ["keep"])

    def test_a_runs_folder_not_roots_alone_is_refused(self):
        # A share user who made the backup's folder before its first run, or
        # a folder others may write: either could leave a name inside it for
        # root's copy to follow.
        runs = os.path.join(self.dest, "media")
        os.makedirs(runs)
        os.chmod(runs, 0o755)
        a = self.A()
        self.assertEqual(self.run_job(a, {"name": "media"}, "20261028-040000", owner=os.getuid() + 1), ("failed", 64), self.job.text())
        self.assertIn("is not root's alone", self.job.text())
        for mode in (0o777, 0o757):
            os.chmod(runs, mode)
            self.assertEqual(self.run_job(a, {"name": "media"}, "20261028-040000"), ("failed", 64), oct(mode))
        # The test stands this account's uid in for root's; where its group
        # has the same number (a runner's user and group often do), the
        # folder's group is root's in this model and may write it.
        if os.stat(runs).st_gid != os.getuid():
            os.chmod(runs, 0o775)
            self.assertEqual(self.run_job(a, {"name": "media"}, "20261028-040000"), ("failed", 64), "writable by a group not root's")
        self.assertEqual(self.ran, [], "rsync is not run")
        os.chmod(runs, 0o755)
        self.assertEqual(self.run_job(a, {"name": "media"}, "20261028-040000"), ("succeeded", 0), self.job.text())

    def test_an_smb_mounts_folder_is_roots_alone_without_an_acl(self):
        # What an SMB mount shows (uid=0, gid=0, dir_mode=0775) is root's
        # alone; group bits that are an ACL's mask are not.
        smb = os.stat_result((0o40775, 0, 0, 0, 0, 0) + (0,) * 4)
        with mock.patch.object(self.bm.os, "fstat", return_value=smb), mock.patch.object(self.bm, "_acl", return_value=False):
            self.assertTrue(self.bm._roots_alone(0))
        with mock.patch.object(self.bm.os, "fstat", return_value=smb), mock.patch.object(self.bm, "_acl", return_value=True):
            self.assertFalse(self.bm._roots_alone(0))
        with mock.patch.object(self.bm.os, "fstat", return_value=os.stat_result((0o40755, 0, 0, 0, 0, 1000) + (0,) * 4)):
            self.assertTrue(self.bm._roots_alone(0), "a group that may only read")
        with mock.patch.object(self.bm.os, "fstat", return_value=os.stat_result((0o40775, 0, 0, 0, 0, 1000) + (0,) * 4)):
            self.assertFalse(self.bm._roots_alone(0), "a group not root's that may write")

    def test_a_link_at_the_runs_partial_name_stops_the_run(self):
        # The audit's scenario: links left at the next seconds' run names,
        # to a folder of root's that rsync --delete would empty.
        victim = os.path.join(self.d, "victim")
        os.makedirs(victim)
        open(os.path.join(victim, "precious"), "w").write("root's own")
        runs = os.path.join(self.dest, "media")
        os.makedirs(runs)
        os.chmod(runs, 0o755)
        os.symlink(victim, os.path.join(runs, "20261028-040000.partial"))
        a = self.A()
        self.assertEqual(self.run_job(a, {"name": "media"}, "20261028-040000"), ("failed", 64), self.job.text())
        self.assertIn("something is already at", self.job.text())
        os.makedirs(os.path.join(runs, "20261028-050000"))
        self.assertEqual(self.run_job(a, {"name": "media"}, "20261028-050000"), ("failed", 64), "a run already at the name")
        self.assertEqual(self.ran, [])
        self.assertEqual(os.listdir(victim), ["precious"])

    def test_a_folder_swapped_while_the_copy_runs_takes_nothing_elsewhere(self):
        # The runs' folder renamed and a link left at its name while rsync
        # runs: the copy, the rename and `latest` stay in the folder held.
        victim = os.path.join(self.d, "victim")
        os.makedirs(victim)
        runs = os.path.join(self.dest, "media")
        a = self.A()

        def swap():
            os.rename(runs, runs + ".moved")
            os.symlink(victim, runs)
        a.during = swap
        self.assertEqual(self.run_job(a, {"name": "media"}, "20261028-040000"), ("succeeded", 0), self.job.text())
        self.assertEqual(os.listdir(victim), [])
        self.assertEqual(sorted(os.listdir(runs + ".moved")), ["20261028-040000", "latest"])
        self.assertEqual(os.readlink(os.path.join(runs + ".moved", "latest")), "20261028-040000")

    @unittest.skipUnless(shutil.which("rsync"), "no rsync here")
    def test_rsync_itself_copies_into_the_held_folder(self):
        import subprocess
        victim = os.path.join(self.d, "victim")
        os.makedirs(victim)
        open(os.path.join(victim, "precious"), "w").write("root's own")
        runs = os.path.join(self.dest, "media")
        a = self.A()

        def rsync(job, argv, timeout=0, pass_fds=()):
            # The runs' folder swapped for a link just before rsync starts.
            os.rename(runs, runs + ".moved")
            os.symlink(victim, runs)
            self.ran.append(argv)
            return subprocess.run([shutil.which("rsync"), "-a", "--delete"] + argv[-2:], pass_fds=pass_fds, check=False).returncode
        a._sh = rsync
        self.assertEqual(self.run_job(a, {"name": "media"}, "20261028-040000"), ("succeeded", 0), self.job.text())
        self.assertEqual(os.listdir(victim), ["precious"])
        self.assertEqual(open(os.path.join(runs + ".moved", "20261028-040000", "a.txt")).read(), "hello")

    def test_a_latest_that_leads_out_is_not_linked_to(self):
        a = self.A()
        self.run_job(a, {"name": "media"}, "20261028-040000")
        elsewhere = os.path.join(self.d, "etc")
        os.makedirs(elsewhere)
        latest = os.path.join(self.dest, "media", "latest")
        os.unlink(latest)
        os.symlink(elsewhere, latest)
        self.run_job(a, {"name": "media"}, "20261029-040000")
        self.assertNotIn("--link-dest", self.ran[-1])

    def test_what_fails_leaves_nothing_and_a_missing_mount_is_refused(self):
        a = self.A()
        self.assertEqual(self.run_job(a, {"name": "media"}, "x", mounted=False, swap_dest=False)[0], "failed")
        self.assertIn("nothing is mounted", self.job.text())
        self.assertEqual(self.ran, [])
        self.assertEqual(self.run_job(a, {"name": "nope"}, "x")[0], "failed")
        self.assertIn("no backup called nope", self.job.text())
        a2 = self.A()
        a2._sh = lambda job, argv, **kw: (self.ran.append(argv), 23)[1]
        self.assertEqual(self.run_job(a2, {"name": "media"}, "20261028-050000"), ("failed", 23))
        self.assertFalse(os.path.exists(os.path.join(self.dest, "media", "20261028-050000.partial")))
        self.assertFalse(os.path.exists(os.path.join(self.dest, "media", "20261028-050000")))
        self.assertEqual(json.load(open(self.env["BB_BACKUPS_STATE"]))["media"]["error"], "rsync exit 23")


class TheController(unittest.TestCase):
    def test_the_census_the_verb_and_the_bell(self):
        import nodes
        got = nodes._census({"store_backups": [{"id": "b_1", "name": "media", "last_at": 5, "ok": True, "error": "", "size_mb": 10, "runs": 2, "took_s": 3}, {"name": "Bad"}]})
        self.assertEqual(got["store_backups"], [{"id": "b_1", "name": "media", "last_at": 5, "ok": True, "error": "", "size_mb": 10, "runs": 2, "took_s": 3}])
        nodes.configure(state=tempfile.mkdtemp())
        self.assertEqual(nodes.node_storage_backup("user:t", "n_none", "media")["error"], "no such node")
        own = {"id": "n1", "name": "nas", "kind": "agent", "live": True, "config": {"own": True},
               "reported": {"administers": True, "store_backups": [{"name": "media", "ok": False, "last_at": 100, "error": "rsync exit 23"}]}}
        with mock.patch.object(nodes, "node", return_value=own), mock.patch.object(nodes, "own_machine", return_value=True), \
             mock.patch.object(nodes, "node_locked", return_value=""), mock.patch.object(nodes, "system_job_for", return_value=None), \
             mock.patch.object(nodes, "audit"), mock.patch.object(nodes, "store_backups", lambda: [{"name": "media"}]), \
             mock.patch.object(nodes, "job_add", side_effect=lambda *a: {"ok": True, "job": "j1", "spec": a[3]}) as add:
            self.assertIn("not a backup on the record", nodes.node_storage_backup("user:t", "n1", "other")["error"])
            self.assertTrue(nodes.node_storage_backup("user:t", "n1", "media").get("ok"))
            self.assertEqual(add.call_args[0][3], {"apply": "storage-backup", "config": {"name": "media"}, "timeout": 86400})
        with mock.patch.object(nodes, "node_list", return_value=[own]), \
             mock.patch.object(nodes, "backup_summary", lambda rows: {"failed": ["media"], "stale": ["state"]}):
            got = nodes.backup_attention()
        self.assertEqual([(r["kind"], r["what"], r["bad"]) for r in got], [("backup", "failed", True), ("backup", "stale", False)])
        self.assertIn("rsync exit 23", got[0]["said"])
        self.assertIn("never run", got[1]["said"])


if __name__ == "__main__":
    unittest.main()
