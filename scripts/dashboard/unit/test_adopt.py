"""Another NAS's array and its pools taken as they are (R163 step 8, the
agent's adopt.py): each data disk found by the serial the plan names and mounted
with the filesystem it holds, read-only unless writable was picked, the
parity disk left alone, the pools writable, its paths kept, and the
merged trees with a read-only disk marked so; anything that does not match
is refused and nothing mounted. The module never formats, wipes,
partitions or upgrades a disk (R163 step 5's hard rules), which is read off
its own text."""
import os
import re
import tempfile
import unittest

import agentpkg  # noqa: E402

agent = agentpkg.load("aerieos_agent_adopt")
adopt = agent.module("adopt")

DISKS = [
    {"name": "sda", "by_id": "/dev/disk/by-id/ata-WDC_WD80EFAX_AAA111", "serial": "AAA111", "model": "WDC WD80EFAX",
     "parts": [{"name": "sda1"}], "system": False, "mounted": False},
    {"name": "sdb", "by_id": "/dev/disk/by-id/ata-WDC_WD80EFAX_BBB222", "serial": "BBB222", "model": "WDC WD80EFAX",
     "parts": [{"name": "sdb1"}], "system": False, "mounted": False},
    {"name": "sdc", "by_id": "/dev/disk/by-id/ata-ST10000_PPP999", "serial": "PPP999", "model": "ST10000",
     "parts": [{"name": "sdc1"}], "system": False, "mounted": False},
    {"name": "nvme0n1", "by_id": "/dev/disk/by-id/nvme-Samsung_970_CCC333", "serial": "CCC333", "model": "Samsung 970",
     "parts": [{"name": "nvme0n1p1"}], "system": False, "mounted": False},
    {"name": "sdz", "by_id": "/dev/disk/by-id/usb-Builder_Stick", "serial": "STICK", "model": "Stick",
     "parts": [{"name": "sdz1"}], "system": True, "mounted": True},
]
BLK = {"sda1": {"TYPE": "xfs", "UUID": "u-a"}, "sdb1": {"TYPE": "btrfs", "UUID": "u-b"}, "sdc1": {},
       "nvme0n1p1": {"TYPE": "btrfs", "UUID": "u-cache"}}
WANT = {"data": [{"slot": "disk1", "id": "WDC_WD80EFAX_AAA111", "fs": "xfs"},
                 {"slot": "disk2", "id": "WDC_WD80EFAX_BBB222", "fs": "btrfs"}],
        "parity": [{"slot": "parity", "id": "ST10000_PPP999"}],
        "pools": [{"name": "cache", "fs": "btrfs", "uuid": "u-cache", "disk_id": "Samsung_970_CCC333"}]}


def plan(want=WANT, disks=DISKS, blk=BLK):
    return adopt.plan(want, disks, blk=lambda n: blk.get(n, {}))


class Plan(unittest.TestCase):
    def test_a_pool_with_no_uuid_is_found_by_its_disk(self):
        # B625: a cache disk the old system kept in its array's cache slot
        # has no pool record to name its UUID; its disk id finds it.
        p = plan({"data": [], "pools": [{"name": "cache", "fs": "btrfs", "uuid": "", "disk_id": "Samsung_970_CCC333"}]})
        self.assertEqual([m["where"] for m in p["mounts"]], ["/mnt/cache"], p)
        self.assertIn("UUID=u-cache", p["mounts"][0]["what"])
        p = plan({"data": [], "pools": [{"name": "cache", "fs": "btrfs", "uuid": "", "disk_id": "Samsung_970_GONE"}]})
        self.assertEqual(p["mounts"], [])
        self.assertTrue(any("Samsung_970_GONE is not on this machine" in r for r in p["refused"]), p["refused"])

    def test_disks_by_serial_read_only_with_their_paths(self):
        p = plan()
        self.assertEqual(p["refused"], [])
        got = {m["where"]: (m["what"], m["fs"], m["ro"]) for m in p["mounts"]}
        self.assertEqual(got, {"/mnt/disk1": ("UUID=u-a", "xfs", True), "/mnt/disk2": ("UUID=u-b", "btrfs", True),
                               "/mnt/cache": ("UUID=u-cache", "btrfs", False)})
        self.assertEqual(p["merged"]["/mnt/user"], ["/mnt/cache=RW", "/mnt/disk1=RO", "/mnt/disk2=RO"])
        self.assertEqual(p["merged"]["/mnt/user0"], ["/mnt/disk1=RO", "/mnt/disk2=RO"])
        self.assertEqual(p["parity"], [{"slot": "parity", "dev": "sdc", "id": "ST10000_PPP999"}], "kept by its id, which a takeover finds it by")
        self.assertTrue(any("left alone" in s for s in p["said"]))

    def test_writable_says_what_it_costs(self):
        p = plan({**WANT, "writable": True})
        self.assertTrue(all(not m["ro"] for m in p["mounts"]))
        self.assertIn("/mnt/disk1=RW", p["merged"]["/mnt/user"])
        self.assertTrue(any("parity sync" in s for s in p["said"]))

    def test_a_disk_not_here_or_not_holding_what_the_plan_said_is_refused(self):
        p = plan({"data": [{"slot": "disk1", "id": "NOPE_000", "fs": "xfs"},
                           {"slot": "disk2", "id": "WDC_WD80EFAX_BBB222", "fs": "xfs"}]})
        self.assertEqual(len(p["refused"]), 2, p["refused"])
        self.assertEqual(p["mounts"], [])

    def test_the_system_disk_a_mounted_one_or_one_named_twice_is_refused(self):
        p = plan({"data": [{"slot": "disk1", "id": "Builder_Stick", "fs": "xfs"},
                           {"slot": "disk2", "id": "WDC_WD80EFAX_AAA111", "fs": "xfs"},
                           {"slot": "disk3", "id": "WDC_WD80EFAX_AAA111", "fs": "xfs"}]})
        self.assertTrue(any("system disk" in r for r in p["refused"]), p["refused"])
        self.assertTrue(any("named twice" in r for r in p["refused"]), p["refused"])

    def test_an_encrypted_disk_says_its_key_is_not_asked_yet(self):
        p = plan({"data": [{"slot": "disk1", "id": "WDC_WD80EFAX_AAA111", "fs": "luks:xfs"}]})
        self.assertTrue(any("key" in r for r in p["refused"]), p["refused"])

    def test_a_pool_cannot_take_the_merged_trees_names(self):
        p = plan({"pools": [{"name": "user", "fs": "btrfs", "uuid": "u-cache"}]})
        self.assertTrue(p["refused"])

    def test_zfs_is_imported_without_force_and_read_only_on_a_data_disk(self):
        blk = {**BLK, "sda1": {"TYPE": "zfs_member", "LABEL": "disk1"}}
        p = plan({"data": [{"slot": "disk1", "id": "WDC_WD80EFAX_AAA111", "fs": "zfs"}]}, blk=blk)
        self.assertEqual(p["zfs"], [{"pool": "disk1", "where": "/mnt/disk1", "readonly": True, "slot": "disk1"}])


class Fstab(unittest.TestCase):
    def test_lines_are_marked_nofail_and_the_merged_tree_waits_for_its_branches(self):
        text = adopt.render_fstab(plan())
        lines = text.splitlines()
        self.assertTrue(all(ln.endswith(adopt.MARK) for ln in lines))
        self.assertIn("UUID=u-a /mnt/disk1 xfs ro,norecovery,defaults,nofail,noatime 0 0", text)
        self.assertIn("UUID=u-b /mnt/disk2 btrfs ro,rescue=nologreplay,defaults,nofail,noatime 0 0", text)
        self.assertIn("UUID=u-cache /mnt/cache btrfs defaults,nofail,noatime 0 0", text)
        user = next(ln for ln in lines if " /mnt/user fuse.mergerfs " in ln)
        self.assertTrue(user.startswith("/mnt/cache=RW:/mnt/disk1=RO:/mnt/disk2=RO "))
        self.assertIn("category.create=ff", user)
        self.assertIn("x-systemd.requires-mounts-for=/mnt/disk1", user)

    def test_written_beside_what_fstab_holds_and_taken_out_whole(self):
        d = tempfile.mkdtemp()
        path = os.path.join(d, "fstab")
        with open(path, "w") as f:
            f.write("UUID=root / ext4 defaults 0 1\n")
        os.environ["BB_ADOPT_FSTAB"] = path
        self.addCleanup(os.environ.pop, "BB_ADOPT_FSTAB", None)
        adopt.write_fstab(plan())
        with open(path) as f:
            self.assertIn("/mnt/disk1", f.read())
        adopt.write_fstab({})
        with open(path) as f:
            self.assertEqual(f.read(), "UUID=root / ext4 defaults 0 1\n")


class HardRules(unittest.TestCase):
    def test_nothing_in_it_formats_wipes_partitions_or_upgrades(self):
        with open(adopt.__file__) as f:
            code = "\n".join(ln for ln in f.read().splitlines() if not ln.lstrip().startswith("#"))
        # The docstring names the tools it never uses; the code may not.
        body = code.split('"""', 2)[2]
        for word in ("mkfs", "wipefs", "sgdisk", "parted", "fdisk", "sfdisk", '"upgrade"', "zpool upgrade", "-f\"", "\"-f"):
            self.assertNotIn(word, body, f"{word} has no place in adopt.py")
        self.assertFalse(re.search(r'\["zpool", "import"[^\]]*"-f"', body))

    def test_the_way_back_stays_open(self):
        # R163 step 5: no btrfs feature the old kernel may not read, no ZFS
        # upgrade, in the adoption or the takeover; the takeover formats the
        # parity partition alone (test_array.Takeover holds that by running it).
        here = os.path.dirname(adopt.__file__)
        for name in ("adopt.py", "array.py"):
            with open(os.path.join(here, name)) as f:
                code = "\n".join(ln for ln in f.read().splitlines() if not ln.lstrip().startswith("#"))
            # What the docstrings say they never use is not code.
            code = re.sub(r'"""(?:.|\n)*?"""', "", code)
            for word in ("btrfstune", '"balance"', '"convert"', "zpool upgrade", '"upgrade"', '"-O"', "zfs set feature"):
                self.assertNotIn(word, code, f"{word} has no place in {name}")


if __name__ == "__main__":
    unittest.main()


class Request(unittest.TestCase):
    """The controller's half (nodes._adopt_want): each field's shape checked
    before a job is made, the agent checking each against the machine."""

    def setUp(self):
        import sys
        sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)), ".."))
        import nodes
        self.want = nodes._adopt_want

    def test_a_good_request_passes_whole(self):
        w, why = self.want({"want": {**WANT, "writable": True, "from": "nas"}})
        self.assertEqual(why, "")
        self.assertEqual([d["slot"] for d in w["data"]], ["disk1", "disk2"])
        self.assertTrue(w["writable"])
        self.assertEqual(w["pools"][0]["name"], "cache")

    def test_a_pools_disk_id_is_kept_and_checked(self):
        w, why = self.want({"want": WANT})
        self.assertEqual(why, "")
        self.assertEqual(w["pools"][0].get("disk_id"), "Samsung_970_CCC333")
        w, why = self.want({"want": {"pools": [{"name": "cache", "fs": "btrfs", "disk_id": "a b;rm"}]}})
        self.assertIsNone(w)
        self.assertIn("disk_id", why)

    def test_a_bad_shape_is_refused_before_any_job(self):
        for bad in ({"data": [{"slot": "disk0", "id": "X", "fs": "xfs"}]},
                    {"data": [{"slot": "disk1", "id": "a b;rm", "fs": "xfs"}]},
                    {"data": [{"slot": "disk1", "id": "X", "fs": "ext4"}]},
                    {"pools": [{"name": "Cache!", "fs": "btrfs"}]},
                    {"parity": [{"id": "X"}]}):
            w, why = self.want({"want": bad})
            self.assertIsNone(w, bad)
            self.assertTrue(why)


class FromTheStick(unittest.TestCase):
    """What the stick's plan names to adopt (firstboot.adopt_want, R163
    step 9): data disks by slot and serial, parity left alone, pools by
    UUID, an encrypted disk set apart with why."""

    def setUp(self):
        import sys
        sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)), ".."))
        import firstboot
        self.want = firstboot.adopt_want

    def test_the_plan_becomes_the_request(self):
        cfg = {"array": {"disks": [{"slot": "disk1", "id": "WDC_A1", "fs": "xfs"}, {"slot": "disk2", "id": "WDC_B2", "fs": "luks:xfs"},
                                   {"slot": "disk3", "id": "WDC_C3", "fs": "BTRFS"}],
                         "parity": [{"slot": "parity", "id": "ST_P"}]},
               "pools": [{"name": "cache", "fs": "btrfs", "uuid": "u-1"}]}
        got = self.want(cfg)
        self.assertEqual(got["want"]["data"], [{"slot": "disk1", "id": "WDC_A1", "fs": "xfs"}, {"slot": "disk3", "id": "WDC_C3", "fs": "btrfs"}])
        self.assertEqual(got["want"]["parity"], [{"slot": "parity", "id": "ST_P"}])
        self.assertEqual(got["want"]["pools"], [{"name": "cache", "fs": "btrfs", "uuid": "u-1"}])
        self.assertEqual([s["id"] for s in got["skipped"]], ["WDC_B2"])
        # ...and the controller takes it whole.
        import nodes
        w, why = nodes._adopt_want({"want": got["want"]})
        self.assertEqual(why, "")

    def test_a_cache_in_the_arrays_slot_is_offered_as_a_pool_by_its_disk(self):
        # B625: an old system with no pool records kept its cache in the
        # array's cache slot; the plan offers it as the pool cache.
        cfg = {"array": {"disks": [{"slot": "disk1", "id": "WDC_A1", "fs": "xfs"}],
                         "cache": [{"slot": "cache", "id": "Samsung_X", "fs": "btrfs"}, {"slot": "cache2", "id": "Crucial_Y", "fs": "LUKS:btrfs"}]}}
        got = self.want(cfg)
        self.assertEqual(got["want"]["pools"], [{"name": "cache", "fs": "btrfs", "uuid": "", "disk_id": "Samsung_X"}])
        self.assertEqual([(s["slot"], s["why"]) for s in got["skipped"]], [("cache2", "encrypted: its key is not asked for yet")])
        # ...and not twice when a pool record names it already.
        cfg["pools"] = [{"name": "cache", "fs": "btrfs", "uuid": "u-1"}]
        self.assertEqual([p["name"] for p in self.want(cfg)["want"]["pools"]], ["cache"])

    def test_a_pool_the_adopt_cannot_take_is_set_apart_not_the_whole_request(self):
        # B612: an encrypted pool, one with no filesystem the adopt takes, or
        # one named as no pool can be here, left in the request failed its
        # shape check whole, and nothing of the stick's adopted.
        cfg = {"array": {"disks": [{"slot": "disk1", "id": "WDC_A1", "fs": "xfs"}]},
               "pools": [{"name": "cache", "fs": "LUKS:btrfs", "uuid": "u-1"}, {"name": "spare", "fs": "auto", "uuid": ""},
                         {"name": "Fast", "fs": "zfs", "uuid": ""}, {"name": "nvme", "fs": "btrfs", "uuid": "u-4"}]}
        got = self.want(cfg)
        self.assertEqual(got["want"]["pools"], [{"name": "nvme", "fs": "btrfs", "uuid": "u-4"}])
        self.assertEqual([(s["slot"], s["why"]) for s in got["skipped"]],
                         [("cache", "encrypted: its key is not asked for yet"), ("spare", "its filesystem is auto"),
                          ("Fast", "its name is not one a pool can be mounted under here (a lowercase letter, then lowercase letters, digits, - and _)")])
        import nodes
        _w, why = nodes._adopt_want({"want": got["want"]})
        self.assertEqual(why, "")
        # Only pools that cannot be taken: the disk still adopts.
        got = self.want({"array": {"disks": [{"slot": "disk1", "id": "WDC_A1", "fs": "xfs"}]}, "pools": [{"name": "cache", "fs": "luks:xfs"}]})
        self.assertEqual((len(got["want"]["data"]), got["want"]["pools"], len(got["skipped"])), (1, [], 1))

    def test_a_plan_with_no_disk_or_pool_offers_nothing(self):
        self.assertIsNone(self.want({}))
        self.assertIsNone(self.want({"array": {"disks": []}}))


class SharesFromTheStick(unittest.TestCase):
    """The plan's shares as storage-share's set-many takes them
    (firstboot.share_requests, R163 step 9)."""

    def setUp(self):
        import sys
        sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)), ".."))
        import firstboot
        self.req = firstboot.share_requests

    def test_each_security_carried_as_it_can_be(self):
        rows, notes = self.req({"shares": [
            {"name": "media", "smb": True, "security": "public"},
            {"name": "docs", "smb": True, "security": "secure", "write": ["ann"]},
            {"name": "isos", "smb": True, "security": "secure"},
            {"name": "home", "smb": True, "security": "private", "read": ["bob"], "write": ["ann"], "time_machine": True},
            {"name": "backup", "nfs": True, "nfs_clients": "192.168.1.0/24(rw) 10.0.0.5(ro)"},
            {"name": "lonely", "smb": True, "security": "private"}]})
        by = {r["name"]: r for r in rows}
        self.assertEqual(by["media"]["path"], "/mnt/user/media")
        self.assertTrue(by["media"]["smb"]["guest"])
        # Secure as it was: everybody reads, its writers write.
        self.assertTrue(by["docs"]["smb"]["guest"])
        self.assertEqual(by["docs"]["smb"]["users"], ["ann"])
        self.assertTrue(by["isos"]["smb"]["guest"] and by["isos"]["smb"]["ro"])
        # Private as it was: each person read or write.
        self.assertEqual(by["home"]["smb"]["users"], ["ann"])
        self.assertEqual(by["home"]["smb"]["readers"], ["bob"])
        self.assertTrue(by["home"]["smb"]["tm"])
        self.assertEqual(by["backup"]["nfs"]["clients"], ["192.168.1.0/24", "10.0.0.5"])
        # Nobody on its lists: still a share, a folder, and not exported.
        self.assertFalse(by["lonely"]["smb"]["on"])
        self.assertEqual({n["name"] for n in notes}, {"lonely"})
