"""The array (R162 step 2): the agent renders snapraid.conf and the fstab
lines from its record, reads the array into the census, and holds the
storage-array job to its shapes (a parity disk at least as large as the
largest data disk, no held disk without wipe, never the system disk) before
mkfs, mergerfs or SnapRAID run; the controller keeps the census's array
to its shape and queues the job for the own machine alone."""
import os
import sys
import tempfile
import unittest
from unittest import mock

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, os.path.join(HERE, ".."))
import agentpkg  # noqa: E402

DISKS = [{"name": "sda", "model": "WDC", "serial": "A", "size_mb": 3815447, "system": False, "holds": "nothing", "parts": []},
         {"name": "sdb", "model": "WDC", "serial": "B", "size_mb": 1907729, "system": False, "holds": "nothing", "parts": []},
         {"name": "sdc", "model": "WDC", "serial": "C", "size_mb": 3815447, "system": False, "holds": "nothing", "parts": []},
         {"name": "sdd", "model": "WDC", "serial": "D", "size_mb": 7630885, "system": False, "holds": "", "parts": [{"name": "sdd1", "holds": "ext4, not mounted"}]},
         {"name": "nvme0n1", "model": "SSD", "serial": "S", "size_mb": 488386, "system": True, "holds": "", "parts": [{"name": "nvme0n1p2", "holds": "squashfs at /"}]}]
REC = {"policy": "epmfs", "data": [{"slot": 1, "id": "ata-WDC_A", "uuid": "1111", "fs": "xfs"}, {"slot": 2, "id": "ata-WDC_B", "uuid": "2222", "fs": "xfs"}],
       "parity": [{"slot": 1, "id": "ata-WDC_C", "uuid": "3333", "fs": "xfs"}]}


class Job:
    def __init__(self):
        self.log = []

    def say(self, s):
        self.log.append(s)

    def text(self):
        return "".join(self.log)


class TheAgent(unittest.TestCase):
    def setUp(self):
        self.agent = agentpkg.load("aerieos_agent_array")
        self.am = sys.modules[self.agent.Agent.__module__.rsplit(".", 1)[0] + ".array"]
        self.d = tempfile.mkdtemp()
        self.env = {"BB_ARRAY_RECORD": os.path.join(self.d, "array.json"), "BB_ARRAY_STATE": os.path.join(self.d, "state.json"),
                    "BB_ARRAY_FSTAB": os.path.join(self.d, "fstab"), "BB_SNAPRAID_CONF": os.path.join(self.d, "snapraid.conf")}
        open(self.env["BB_ARRAY_FSTAB"], "w").write("UUID=root / ext4 defaults 0 1\n")
        am = self.am
        ran = self.ran = []

        self.fail_mkfs = ""

        class A(am.ArrayMixin):
            def _sh(inner, job, argv, timeout=0, **kw):
                ran.append(argv)
                return 1 if self.fail_mkfs and argv[0].startswith("mkfs") and argv[-1] == self.fail_mkfs else 0

            def hello_again(self, why):
                self.said = why
        self.A = A

    def test_the_files_are_rendered_from_the_record(self):
        conf = self.am.render_snapraid(REC)
        self.assertIn("parity /mnt/parity/p1/snapraid.parity\n", conf)
        self.assertNotIn("2-parity", conf)
        self.assertIn("content /var/lib/builderbot/snapraid.content\n", conf)
        self.assertIn("content /mnt/disks/d1/.snapraid.content\n", conf)
        self.assertIn("data d2 /mnt/disks/d2/\n", conf)
        two = self.am.render_snapraid({**REC, "parity": REC["parity"] + [{"slot": 2, "id": "x", "uuid": "4", "fs": "xfs"}]})
        self.assertIn("2-parity /mnt/parity/p2/snapraid.2-parity\n", two)
        fstab = self.am.render_fstab(REC)
        self.assertIn("UUID=1111 /mnt/disks/d1 xfs defaults,nofail,noatime 0 0 # builderbot-array\n", fstab)
        self.assertIn("UUID=3333 /mnt/parity/p1 xfs defaults,nofail,noatime 0 0 # builderbot-array\n", fstab)
        merged = [ln for ln in fstab.splitlines() if "fuse.mergerfs" in ln][0]
        self.assertTrue(merged.startswith("/mnt/disks/d* /mnt/array fuse.mergerfs "))
        self.assertIn("category.create=epmfs", merged)
        self.assertIn("minfreespace=20G", merged)
        self.assertIn("x-systemd.requires-mounts-for=/mnt/disks/d2", merged)
        with mock.patch.dict(os.environ, self.env):
            self.am.write_fstab(REC)
            self.am.write_fstab(REC)
            text = open(self.env["BB_ARRAY_FSTAB"]).read()
        self.assertEqual(text.count("# builderbot-array"), 4, "written whole each time, the rest of fstab kept")
        self.assertTrue(text.startswith("UUID=root / ext4 defaults 0 1\n"))

    def test_the_census_reads_the_record_the_mounts_and_the_state(self):
        with mock.patch.dict(os.environ, self.env):
            self.assertEqual(self.am.array_now(), {}, "no record, no array")
            self.am.write_record(REC)
            self.am._state_set(last_sync=1761624000, status="Everything OK", running="")
            with mock.patch.object(self.am.os.path, "ismount", side_effect=lambda p: p in ("/mnt/disks/d1", "/mnt/array")), \
                 mock.patch.object(self.am, "_df", return_value=(1000, 400)):
                got = self.am.array_now()
        self.assertEqual((got["policy"], got["mounted"], got["last_sync"], got["status"]), ("epmfs", True, 1761624000, "Everything OK"))
        self.assertEqual([(x["slot"], x["mounted"], x["size_mb"], x["used_mb"]) for x in got["data"]], [(1, True, 1000, 400), (2, False, 0, 0)])
        self.assertEqual(got["parity"][0]["id"], "ata-WDC_C")

    def run_job(self, cfg, rec=None):
        job = Job()
        with mock.patch.dict(os.environ, self.env):
            if rec is not None:
                self.am.write_record(rec)
            elif os.path.exists(self.env["BB_ARRAY_RECORD"]):
                os.unlink(self.env["BB_ARRAY_RECORD"])
            with mock.patch.object(self.am, "disks_now", return_value=DISKS), mock.patch.object(self.am.shutil, "which", side_effect=lambda t: f"/usr/bin/{t}"), \
                 mock.patch.object(self.am.os, "geteuid", return_value=0), mock.patch.object(self.am, "by_id", side_effect=lambda n: f"ata-{n}"), \
                 mock.patch.object(self.am, "_out", return_value="uuid-x\n"), mock.patch.object(self.am.os.path, "ismount", return_value=False), \
                 mock.patch.object(self.am.os, "makedirs"), mock.patch.object(self.am, "_df", return_value=(3815447, 10)):
                state, code = self.A()._apply_storage_array(job, cfg)
            return state, code, job.text(), self.am.read_record()

    def test_an_array_is_made_of_wiped_disks_and_synced_once(self):
        state, code, text, rec = self.run_job({"array": "create", "data": ["sda", "sdb"], "parity": ["sdc"], "fs": "xfs", "policy": "mfs"})
        self.assertEqual((state, code), ("succeeded", 0), text)
        argv = [a for a in self.ran if a[0] == "mkfs.xfs"]
        self.assertEqual([a[-1] for a in argv], ["/dev/sda", "/dev/sdb", "/dev/sdc"])
        self.assertEqual(argv[0][1:3], ["-L", "bb-d1"])
        self.assertEqual(argv[2][1:3], ["-L", "bb-p1"])
        self.assertNotIn("-f", argv[0], "mkfs keeps its own refusal where the job did not say to wipe")
        self.assertNotIn(["wipefs", "-a", "/dev/sda"], self.ran, "nothing to wipe without the word")
        self.assertEqual([a for a in self.ran if a[0] == "mount"], [["mount", "/mnt/disks/d1"], ["mount", "/mnt/disks/d2"], ["mount", "/mnt/parity/p1"], ["mount", "/mnt/array"]])
        self.assertEqual(self.ran[-1], ["/usr/bin/snapraid", "sync"])
        self.assertEqual([(d["slot"], d["id"], d["uuid"]) for d in rec["data"]], [(1, "ata-sda", "uuid-x"), (2, "ata-sdb", "uuid-x")])
        self.assertEqual(rec["policy"], "mfs")
        self.assertIn("data d2 /mnt/disks/d2/", open(self.env["BB_SNAPRAID_CONF"]).read())
        self.assertIn("fuse.mergerfs", open(self.env["BB_ARRAY_FSTAB"]).read())

    def test_a_create_that_stops_partway_says_which_disks_it_wrote(self):
        # B529: no record holds them, so the job names them.
        self.fail_mkfs = "/dev/sdc"
        state, code, text, rec = self.run_job({"array": "create", "data": ["sda", "sdb"], "parity": ["sdc"], "fs": "xfs", "policy": "mfs"})
        self.assertEqual(state, "failed", text)
        self.assertIn("sdc did not take xfs", text)
        self.assertIn("sda, sdb were formatted already and are in no array", text)

    def test_what_is_refused_runs_nothing(self):
        for cfg, rec, why in (({"array": "create", "data": ["sda"], "parity": ["sdb"]}, None, "at least as large"),
                              ({"array": "create", "data": ["sdd"], "parity": ["sda"]}, None, "holds ext4"),
                              ({"array": "create", "data": ["nvme0n1"], "parity": ["sda"]}, None, "system disk"),
                              ({"array": "create", "data": ["sda"], "parity": ["sda"]}, None, "each once"),
                              ({"array": "create", "data": ["sdb"], "parity": ["sda"], "policy": "random"}, None, "a policy one of"),
                              ({"array": "create", "data": ["sdb"], "parity": ["sda"]}, REC, "here already"),
                              ({"array": "sync"}, None, "no array here"),
                              ({"array": "destroy"}, REC, "the word array again"),
                              ({"array": "replace", "which": "d9", "new": "sda"}, REC, "has no d9"),
                              ({"array": "shrink"}, REC, "not an array action")):
            self.ran.clear()
            state, code, text, _ = self.run_job(cfg, rec)
            self.assertEqual(state, "failed", cfg)
            self.assertIn(why, text)
            self.assertEqual(self.ran, [], cfg)

    def test_a_disk_replaced_is_rebuilt_and_a_sync_is_one_at_a_time(self):
        state, code, text, rec = self.run_job({"array": "replace", "which": "d2", "new": "sdb", "wipe": True}, REC)
        self.assertEqual(state, "succeeded", text)
        self.assertIn(["wipefs", "-a", "/dev/sdb"], self.ran)
        self.assertEqual(self.ran[-2:], [["/usr/bin/snapraid", "fix", "-d", "d2"], ["/usr/bin/snapraid", "sync"]])
        self.assertEqual(rec["data"][1]["id"], "ata-sdb")
        self.ran.clear()
        state, code, text, rec = self.run_job({"array": "replace", "which": "p1", "new": "sda"}, REC)
        self.assertEqual(self.ran[-1], ["/usr/bin/snapraid", "sync", "-F"])
        with mock.patch.dict(os.environ, self.env):
            self.am._state_set(running="sync")
        state, code, text, _ = self.run_job({"array": "scrub"}, REC)
        self.assertEqual(state, "failed")
        self.assertIn("one at a time", text)
        with mock.patch.dict(os.environ, self.env):
            self.am._state_set(running="")
        content = os.path.join(self.d, "snapraid.content")
        open(content, "w").close()
        with mock.patch.dict(os.environ, {"BB_SNAPRAID_CONTENT": content}):
            state, code, text, _ = self.run_job({"array": "destroy", "confirm": "array"}, REC)
        self.assertEqual(state, "succeeded", text)
        self.assertFalse(os.path.exists(content), "B704: the next array's sync would read it as this one's")
        self.assertFalse(os.path.exists(self.env["BB_ARRAY_RECORD"]))
        self.assertNotIn("builderbot-array", open(self.env["BB_ARRAY_FSTAB"]).read())


    def test_a_parity_check_reads_everything_and_corrects_only_when_asked(self):
        # R163 step 15: a whole scrub, its findings read off SnapRAID's own
        # log (summary:error_*, and each file whose hash failed), the count
        # said, and the fix only with Correct: -e for the blocks SnapRAID
        # marked, and the files it named by name (as walked on the stick:
        # a silent change to a file is a file error -e fix does not touch).
        logs = {"scrub": "error:1:d1:TV Shows/a.bin: Data error at position 1, diff bits 62/128\n"
                         "summary:error_file:1\nsummary:error_io:0\nsummary:error_data:2\nsummary:exit:error\n",
                "-e": "summary:error_recovered:2\nsummary:error_unrecoverable:0\n",
                "-f": "fixed:1:d1:TV Shows/a.bin: Fixed\nsummary:error_recovered:0\nsummary:error_unrecoverable:1\n"}
        calls = []

        def watched(argv, say, progress, timeout=0):
            calls.append(argv[1:])
            log = argv[argv.index("-l") + 1]
            kind = "scrub" if "scrub" in argv else "-e" if "-e" in argv else "-f"
            with open(log, "w") as f:
                f.write(logs[kind])
            progress(55, 120)
            return (0, "")
        with mock.patch.object(self.am, "run_watched", side_effect=watched):
            state, code, text, _ = self.run_job({"array": "verify"}, REC)
            self.assertEqual(state, "succeeded", text)
            self.assertEqual([c[0] for c in calls], ["scrub"])
            self.assertIn("3 blocks differ from the parity; Correct what differs was not ticked, so nothing was written", text)
            with mock.patch.dict(os.environ, self.env):
                st = self.am._state()
            self.assertEqual((st["verify"]["found"], st["verify"]["fixed"], st["running"], st["progress"]), (3, 0, "", ""))
            calls.clear()
            state, code, text, _ = self.run_job({"array": "verify", "correct": True}, REC)
            self.assertEqual([[x for x in c if not x.startswith("/tmp")] for c in calls][1:],
                             [["-l", "-e", "fix"], ["-l", "fix", "-f", "/TV Shows/a.bin"]])
            self.assertIn("3 blocks differ from the parity: correcting them", text)
            with mock.patch.dict(os.environ, self.env):
                v = self.am.array_now()["verify"]
            self.assertEqual((v["found"], v["fixed"], v["unfixed"], v["corrected"], v["ok"]), (3, 2, 1, True, True))
        self.assertEqual(self.am.counts("  0 data errors\n  12 io errors"), {"data": 0, "io": 12})

    def test_progress_is_read_off_snapraids_redrawn_line(self):
        seen, said = [], []
        sh = "printf 'Scrubbing...\\n10%%, 100 MB, 50 MB/s, CPU 1%%, 0:10 ETA\\r60%%, 600 MB, 80 MB/s\\r\\n  0 data errors\\n'"
        rc, text = self.am.run_watched(["sh", "-c", sh], said.append, lambda p, r: seen.append((p, r)))
        self.assertEqual((rc, seen), (0, [(10, 50), (60, 80)]))
        self.assertIn("0 data errors", text)
        self.assertNotIn("ETA", "".join(said))


class Takeover(unittest.TestCase):
    """R163 steps 3 and 5: an adopted array taken over as SnapRAID's. The
    data disks are made writable where they are and never formatted; the
    old parity disk's first partition is the one thing given a filesystem;
    SnapRAID's content files are the only new thing on a data disk; Release
    waits until the array is destroyed."""
    def setUp(self):
        self.agent = agentpkg.load("aerieos_agent_takeover")
        self.am = sys.modules[self.agent.Agent.__module__.rsplit(".", 1)[0] + ".array"]
        self.ad = sys.modules[self.agent.Agent.__module__.rsplit(".", 1)[0] + ".adopt"]
        self.d = tempfile.mkdtemp()
        self.env = {"BB_ARRAY_RECORD": os.path.join(self.d, "array.json"), "BB_ARRAY_STATE": os.path.join(self.d, "state.json"),
                    "BB_ARRAY_FSTAB": os.path.join(self.d, "fstab"), "BB_SNAPRAID_CONF": os.path.join(self.d, "snapraid.conf"),
                    "BB_ADOPT_RECORD": os.path.join(self.d, "adopted.json"), "BB_ADOPT_FSTAB": os.path.join(self.d, "fstab")}
        with open(self.env["BB_ARRAY_FSTAB"], "w") as f:
            f.write("UUID=root / ext4 defaults 0 1\n")
        self.plan = {"mounts": [{"what": "UUID=aaaa", "where": "/mnt/disk1", "fs": "xfs", "ro": True, "dev": "sdb1"},
                                {"what": "UUID=bbbb", "where": "/mnt/disk2", "fs": "btrfs", "ro": True, "dev": "sdc1"},
                                {"what": "UUID=cccc", "where": "/mnt/cache", "fs": "btrfs", "ro": False, "dev": "nvme0n1p1"}],
                     "zfs": [], "parity": [{"slot": "parity", "dev": "sdd"}],
                     "merged": {"/mnt/user": ["/mnt/cache=RW", "/mnt/disk1=RO", "/mnt/disk2=RO"], "/mnt/user0": ["/mnt/disk1=RO", "/mnt/disk2=RO"]}}
        self.disks = [{"name": "sdb", "size_mb": 4000000, "parts": [{"name": "sdb1", "holds": "xfs at /mnt/disk1"}], "mounted": True},
                      {"name": "sdc", "size_mb": 4000000, "parts": [{"name": "sdc1", "holds": "btrfs at /mnt/disk2"}], "mounted": True},
                      {"name": "sdd", "size_mb": 8000000, "parts": [{"name": "sdd1", "holds": "nothing"}]},
                      {"name": "nvme0n1", "size_mb": 1000000, "system": True, "parts": [{"name": "nvme0n1p2", "holds": "squashfs at /"}]}]
        ran = self.ran = []

        class A(self.am.ArrayMixin, self.ad.AdoptMixin):
            def _sh(inner, job, argv, timeout=0, **kw):
                ran.append(argv)
                return 0

            def hello_again(self, why):
                self.said = why
        self.A = A

    def adopt(self, **kw):
        with mock.patch.dict(os.environ, self.env):
            self.ad.write_record({"plan": self.plan, "writable": False, **kw})

    def take(self, cfg):
        job = Job()
        with mock.patch.dict(os.environ, self.env), mock.patch.object(self.am, "disks_now", return_value=self.disks), \
             mock.patch.object(self.am.shutil, "which", side_effect=lambda t: f"/usr/bin/{t}"), mock.patch.object(self.am.os, "geteuid", return_value=0), \
             mock.patch.object(self.am, "_df", return_value=(3815447, 10)), mock.patch.object(self.am, "_out", return_value="pppp\n"), \
             mock.patch.object(self.am.os.path, "ismount", return_value=False), mock.patch.object(self.am.os, "makedirs"):
            state, code = self.A()._apply_storage_array(job, cfg)
            return state, code, job.text(), self.am.read_record(), self.ad.read_record()

    def test_a_dry_run_says_it_all_and_changes_nothing(self):
        self.adopt()
        state, code, text, rec, arec = self.take({"array": "takeover", "dry": True})
        self.assertEqual(state, "succeeded", text)
        self.assertEqual(self.ran, [])
        self.assertIn("sdd1 on sdd given an xfs filesystem for SnapRAID's parity file", text)
        self.assertIn("unprotected until it ends", text)
        self.assertEqual((rec, arec.get("writable")), ({}, False))

    def test_only_the_parity_partition_is_formatted_and_the_data_disks_stay_where_they_are(self):
        self.adopt()
        state, code, text, rec, arec = self.take({"array": "takeover", "moves": [{"share": "TV Shows", "land": "cache", "from": "cache", "to": "array"},
                                                                                {"share": "x;y", "land": "cache"}, {"share": "isos", "land": "gone"}]})
        self.assertEqual(state, "succeeded", text)
        made = [a for a in self.ran if a[0].startswith(("mkfs", "wipefs", "sgdisk", "parted", "fdisk", "sfdisk"))]
        self.assertEqual(made, [["mkfs.xfs", "-L", "aerie-p1", "/dev/sdd1"]], "the parity partition alone, never a data disk, never a partition table")
        self.assertIn(["mount", "-T", self.env["BB_ADOPT_FSTAB"], "/mnt/disk1"], self.ran)
        self.assertEqual(self.ran[-1], ["/usr/bin/snapraid", "sync"])
        self.assertTrue(rec["adopted"])
        self.assertEqual([(d["slot"], d["where"]) for d in rec["data"]], [(1, "/mnt/disk1"), (2, "/mnt/disk2")])
        self.assertEqual(rec["moves"], [{"share": "TV Shows", "land": "cache", "from": "cache", "to": "array"}], "a pool not in front of the disks is left out")
        self.assertIn("TV Shows: new files land on cache; the mover takes them from cache to the array", text)
        # Each share lands where its folder is from now on, at every boot.
        with open(self.env["BB_ADOPT_FSTAB"]) as f:
            user = next(ln for ln in f if " /mnt/user fuse.mergerfs" in ln)
        self.assertIn("category.create=epff", user)
        self.assertTrue(arec["taken"] and arec["writable"])
        self.assertFalse([m for m in arec["plan"]["mounts"] if m["ro"]])
        self.assertEqual(arec["plan"]["merged"]["/mnt/user"], ["/mnt/cache=RW", "/mnt/disk1=RW", "/mnt/disk2=RW"])
        conf = self.am.render_snapraid(rec)
        on_data = [ln for ln in conf.splitlines() if "/mnt/disk" in ln and not ln.startswith("data ")]
        self.assertEqual(on_data, ["content /mnt/disk1/.snapraid.content", "content /mnt/disk2/.snapraid.content"],
                         "SnapRAID's content files are the only new thing on a data disk")
        self.assertIn("parity /mnt/parity/p1/snapraid.parity", conf)
        lines = [ln for ln in self.am.render_fstab(rec).splitlines()]
        self.assertEqual(len(lines), 1, "the data disks and /mnt/user stay the adoption's lines")
        self.assertIn("/mnt/parity/p1 xfs", lines[0])
        with mock.patch.dict(os.environ, self.env):
            self.assertEqual(self.am.array_now()["mount"], "/mnt/user")
        # Release waits; add and replace are refused.
        job = Job()
        with mock.patch.dict(os.environ, self.env), mock.patch.object(self.ad.shutil, "which", return_value="/usr/bin/x"), \
             mock.patch.object(self.ad.os, "geteuid", return_value=0):
            st, _c = self.A()._apply_storage_adopt(job, {"adopt": "release"})
        self.assertEqual(st, "failed")
        self.assertIn("destroy the array", job.text())
        st, _c, text, _r, _a = self.take({"array": "replace", "which": "d1", "new": "sdd"})
        self.assertIn("not done on it yet", text)

    def test_a_parity_disk_with_no_partition_or_holding_a_filesystem_is_refused(self):
        self.adopt()
        self.disks[2]["parts"] = []
        state, code, text, rec, _a = self.take({"array": "takeover"})
        self.assertIn("never rewritten", text)
        self.disks[2]["parts"] = [{"name": "sdd1", "holds": "ext4, not mounted"}]
        state, code, text, rec, _a = self.take({"array": "takeover"})
        self.assertIn("holds ext4", text)
        self.assertEqual((rec, [a for a in self.ran if a[0].startswith("mkfs")]), ({}, []))

    def test_the_mover_takes_old_files_off_the_pool_and_leaves_new_ones(self):
        root = tempfile.mkdtemp()
        src = os.path.join(root, "cache", "TV Shows", "s1")
        os.makedirs(src)
        old, new = os.path.join(src, "e1.mkv"), os.path.join(src, "e2.mkv")
        for f in (old, new):
            open(f, "w").close()
        os.utime(old, (1000, 1000))
        seen = []

        class M(self.am.ArrayMixin):
            def _sh(inner, job, argv, timeout=0, **kw):
                lst = next(a for a in argv if a.startswith("--files-from="))[13:]
                seen.append((argv[:3], open(lst).read(), argv[-2:]))
                return 0
        job = Job()
        os.makedirs(os.path.join(root, "user0", "isos"))
        os.utime(os.path.join(root, "user0", "isos"))
        open(os.path.join(root, "user0", "isos", "old.iso"), "w").close()
        os.utime(os.path.join(root, "user0", "isos", "old.iso"), (1000, 1000))
        rc = M()._mover(job, [{"share": "TV Shows", "land": "cache", "from": "cache", "to": "array"}, {"share": "none", "land": "cache", "from": "cache", "to": "array"},
                              {"share": "isos", "land": "fast", "from": "array", "to": "fast"}, {"share": "appdata", "land": "cache", "from": "", "to": ""}], root=root)
        self.assertEqual(rc, 0)
        self.assertEqual(seen, [(["rsync", "-aHAX", "--remove-source-files"], "s1/e1.mkv\n",
                                 [os.path.join(root, "cache", "TV Shows") + "/", os.path.join(root, "user0", "TV Shows") + "/"]),
                                (["rsync", "-aHAX", "--remove-source-files"], "old.iso\n",
                                 [os.path.join(root, "user0", "isos") + "/", os.path.join(root, "fast", "isos") + "/"])])
        self.assertIn("isos: 1 file from the data disks to fast", job.text())

    def test_a_share_lands_where_its_folder_is_and_nothing_with_files_is_touched(self):
        root = tempfile.mkdtemp()
        for d in ("user/TV Shows", "cache", "fast", "user0", "cache/backups", "fast/backups", "fast/TV Shows/s1", "cache/vol"):
            os.makedirs(os.path.join(root, d), exist_ok=True)
        os.chmod(os.path.join(root, "user", "TV Shows"), 0o2775)
        said = []
        mounts = {os.path.join(root, x) for x in ("cache", "fast", "user0")}
        with mock.patch.object(self.am.os.path, "ismount", side_effect=lambda p: p in mounts), mock.patch.object(self.am.os, "chown"):
            self.A()._landing(said.append, [{"share": "TV Shows", "land": "cache", "from": "cache", "to": "array"},
                                            {"share": "backups", "land": "array", "from": "", "to": ""},
                                            {"share": "gone", "land": "nowhere", "from": "", "to": ""}], ["cache", "fast"], root=root)
        self.assertTrue(os.path.isdir(os.path.join(root, "cache", "TV Shows")), "made on the pool it lands on")
        self.assertEqual(os.stat(os.path.join(root, "cache", "TV Shows")).st_mode & 0o7777, 0o2775, "made as the share's own folder is")
        self.assertTrue(os.path.isdir(os.path.join(root, "fast", "TV Shows", "s1")), "a folder with something in it is never touched")
        self.assertIn("TV Shows: files are still on fast, so its new files may land there until the mover takes them\n", said)
        self.assertTrue(os.path.isdir(os.path.join(root, "user0", "backups")), "a share landing on the array has its folder on the data disks")
        self.assertFalse(os.path.exists(os.path.join(root, "cache", "backups")) or os.path.exists(os.path.join(root, "fast", "backups")),
                         "and its empty folders on the pools removed")
        self.assertFalse(os.path.exists(os.path.join(root, "nowhere")), "nothing made where no pool is mounted")

    def test_a_shares_places_change_one_at_a_time(self):
        self.adopt(taken=True)
        with mock.patch.dict(os.environ, self.env):
            self.am.write_record({"policy": "adopted", "adopted": True, "data": [{"slot": 1, "where": "/mnt/disk1"}], "parity": [],
                                  "moves": [{"share": "TV Shows", "land": "cache", "from": "cache", "to": "array"}, {"share": "isos", "land": "array", "from": "", "to": ""}]})
        state, code, text, rec, _a = self.take({"array": "moves", "moves": [{"share": "isos", "land": "cache", "from": "array", "to": "cache"}]})
        self.assertEqual(state, "succeeded", text)
        self.assertEqual(rec["moves"], [{"share": "TV Shows", "land": "cache", "from": "cache", "to": "array"}, {"share": "isos", "land": "cache", "from": "array", "to": "cache"}])
        for bad in ([{"share": "isos", "land": "tank"}], [{"share": "isos", "land": "cache", "from": "cache", "to": "cache"}], [{"share": "isos", "land": "cache", "from": "cache"}], []):
            state, code, text, rec2, _a = self.take({"array": "moves", "moves": bad})
            self.assertEqual((state, rec2["moves"]), ("failed", rec["moves"]), bad)


class TheController(unittest.TestCase):
    def test_the_census_keeps_the_array_to_its_shape(self):
        import nodes
        got = nodes._census({"array": {"policy": "mfs<b>", "mount": "/mnt/array", "mounted": True, "last_sync": "x", "last_scrub": 5, "status": "ok", "running": "",
                                       "data": [{"slot": 1, "id": "ata-A", "fs": "xfs", "size_mb": 10, "used_mb": 2, "mounted": True}, {"slot": 0}, "junk"],
                                       "parity": [{"slot": 1, "id": "ata-P", "fs": "xfs", "size_mb": 10, "used_mb": 1, "mounted": "yes"}]}})
        self.assertEqual(got["array"], {"policy": "mfsb", "mount": "/mnt/array", "mounted": True, "last_sync": 0, "last_scrub": 5, "last_check": 0, "status": "ok", "running": "", "progress": "", "adopted": False, "last_move": 0,
                                        "data": [{"slot": 1, "id": "ata-A", "fs": "xfs", "size_mb": 10, "used_mb": 2, "mounted": True}],
                                        "parity": [{"slot": 1, "id": "ata-P", "fs": "xfs", "size_mb": 10, "used_mb": 1, "mounted": False}]})
        self.assertEqual(nodes._census({"array": {"data": []}})["array"], {})

    def test_each_shares_places_are_held_to_the_adopted_pools(self):
        # R163: where a share's new files land and the mover's from and to,
        # set on the takeover or later, each a pool in front of the data
        # disks or the array.
        import nodes
        nodes.configure(state=tempfile.mkdtemp())
        ad = {"mounts": [{"where": "/mnt/disk1"}, {"where": "/mnt/cache"}, {"where": "/mnt/fast"}], "taken": False, "parity": ["sdd"]}
        n = {"id": "n1", "name": "box", "kind": "agent", "live": True, "config": {"own": True},
             "reported": {"administers": True, "features": {"storage": {"mergerfs": True, "snapraid": True}}, "disks": DISKS, "array": {}, "adopted": ad}}
        with mock.patch.object(nodes, "node", return_value=n), mock.patch.object(nodes, "own_machine", return_value=True), \
             mock.patch.object(nodes, "node_locked", return_value=""), mock.patch.object(nodes, "system_job_for", return_value=None), \
             mock.patch.object(nodes, "audit"), mock.patch.object(nodes, "job_add", side_effect=lambda *a: {"ok": True, "job": "j1", "spec": a[3]}) as add:
            mv = [{"share": "TV Shows", "land": "cache", "from": "cache", "to": "array"}, {"share": "isos", "land": "fast", "from": "array", "to": "fast"}]
            r = nodes.node_storage_array("user:t", "n1", {"array": "takeover", "dry": True, "moves": mv})
            self.assertTrue(r.get("ok"), r)
            self.assertEqual(add.call_args[0][3]["config"]["moves"], mv)
            for bad, said in (([{"share": "isos", "land": "tank"}], "tank is not a pool"), ([{"share": "isos", "land": "cache", "from": "cache", "to": "cache"}], "from one place to another"),
                              ([{"share": "a;b", "land": "cache"}], "not a share's name"), ([{"share": "isos", "land": ""}], "land is a pool")):
                self.assertIn(said, nodes.node_storage_array("user:t", "n1", {"array": "takeover", "dry": True, "moves": bad}).get("error", ""), bad)
            # Without the person's, the stick's plan as the old system had it.
            with mock.patch("firstboot.kept_config", return_value={"shares": [{"name": "TV Shows", "cache": "yes", "pool": "cache"}]}):
                nodes.node_storage_array("user:t", "n1", {"array": "takeover", "dry": True})
            self.assertEqual(add.call_args[0][3]["config"]["moves"], [{"share": "TV Shows", "land": "cache", "from": "cache", "to": "array"}])
            # Later, one share at a time, from an agent that has it.
            n["reported"]["array"] = {"data": [{"slot": 1}], "adopted": True, "moves": 3}
            self.assertIn("from before", nodes.node_storage_array("user:t", "n1", {"array": "moves", "moves": mv[:1]})["error"])
            n["reported"]["array"]["moves"] = []
            r = nodes.node_storage_array("user:t", "n1", {"array": "moves", "moves": mv[1:]})
            self.assertEqual(add.call_args[0][3]["config"], {"array": "moves", "moves": mv[1:]}, r)
            self.assertIn("no share's places", nodes.node_storage_array("user:t", "n1", {"array": "moves", "moves": []})["error"])

    def test_the_verb_is_the_own_machines_and_holds_the_shapes(self):
        import nodes
        nodes.configure(state=tempfile.mkdtemp())
        self.assertEqual(nodes.node_storage_array("user:t", "n_none", {"array": "sync"})["error"], "no such node")
        n = {"id": "n1", "name": "box", "kind": "agent", "live": True, "config": {"own": True},
             "reported": {"administers": True, "features": {"storage": {"mergerfs": True, "snapraid": True}}, "disks": DISKS, "array": {}}}
        with mock.patch.object(nodes, "node", return_value=n), mock.patch.object(nodes, "own_machine", return_value=True), \
             mock.patch.object(nodes, "node_locked", return_value=""), mock.patch.object(nodes, "system_job_for", return_value=None), \
             mock.patch.object(nodes, "audit"), mock.patch.object(nodes, "job_add", side_effect=lambda *a: {"ok": True, "job": "j1", "spec": a[3]}) as add:
            self.assertIn("at least as large", nodes.node_storage_array("user:t", "n1", {"array": "create", "data": ["sda"], "parity": ["sdb"]})["error"])
            self.assertIn("system disk", nodes.node_storage_array("user:t", "n1", {"array": "create", "data": ["nvme0n1"], "parity": ["sda"]})["error"])
            self.assertIn("no array on the machine", nodes.node_storage_array("user:t", "n1", {"array": "sync"})["error"])
            self.assertEqual(add.call_count, 0)
            r = nodes.node_storage_array("user:t", "n1", {"array": "create", "data": ["sdb", "sda"], "parity": ["sdc"], "fs": "btrfs", "policy": "lfs", "wipe": True})
            self.assertTrue(r.get("ok"), r)
            self.assertEqual(add.call_args[0][3]["config"], {"array": "create", "data": ["sdb", "sda"], "parity": ["sdc"], "fs": "btrfs", "policy": "lfs", "wipe": True,
                             # Each disk as the person saw it, for the agent to hold its name to (B527).
                             "ids": {"sdb": {"by_id": "", "serial": "B"}, "sda": {"by_id": "", "serial": "A"},
                                     "sdc": {"by_id": "", "serial": "C"}}})
            self.assertEqual(add.call_args[0][3]["timeout"], 86400)
            n["reported"]["array"] = {"data": [{"slot": 1}], "parity": [{"slot": 1}]}
            self.assertIn("one of d1, p1", nodes.node_storage_array("user:t", "n1", {"array": "replace", "which": "d3", "new": "sdb"})["error"])
            self.assertIn("typed again", nodes.node_storage_array("user:t", "n1", {"array": "destroy"})["error"])
            r = nodes.node_storage_array("user:t", "n1", {"array": "check"})
            self.assertEqual(add.call_args[0][3]["timeout"], 900)
            self.assertIn("from before Check parity", nodes.node_storage_array("user:t", "n1", {"array": "verify"})["error"])
            n["reported"]["array"]["verify"] = {}
            r = nodes.node_storage_array("user:t", "n1", {"array": "verify", "correct": True})
            self.assertTrue(r.get("ok"), r)
            self.assertEqual((add.call_args[0][3]["config"], add.call_args[0][3]["timeout"]), ({"array": "verify", "correct": True}, 172800))

    def test_a_parity_checks_result_is_on_the_bell(self):
        import nodes
        base = {"id": "n1", "name": "box", "kind": "agent", "reported": {"array": {"data": [{"slot": 1, "mounted": True}], "parity": []}}}
        def rows(v):
            base["reported"]["array"]["verify"] = v
            with mock.patch.object(nodes, "node_list", return_value=[base]), mock.patch.object(nodes, "own_machine", return_value=True):
                return [r for r in nodes.storage_attention() if r["what"] == "parity"]
        self.assertEqual(rows({}), [])
        clean = rows({"at": 100, "ok": True, "found": 0})[0]
        self.assertEqual((clean["bad"], clean["said"]), (False, "the array's parity check read every block back: all good"))
        part = rows({"at": 101, "ok": True, "found": 3, "fixed": 2, "unfixed": 1, "corrected": True})[0]
        self.assertTrue(part["bad"])
        self.assertIn("3 blocks differing: 2 corrected, 1 could not be", part["said"])
        self.assertIn("Correct to fix them", rows({"at": 102, "ok": True, "found": 4})[0]["said"])


if __name__ == "__main__":
    unittest.main()
