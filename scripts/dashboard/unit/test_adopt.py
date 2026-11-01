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

agent = agentpkg.load("builderbot_agent_adopt")
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
    def test_disks_by_serial_read_only_with_their_paths(self):
        p = plan()
        self.assertEqual(p["refused"], [])
        got = {m["where"]: (m["what"], m["fs"], m["ro"]) for m in p["mounts"]}
        self.assertEqual(got, {"/mnt/disk1": ("UUID=u-a", "xfs", True), "/mnt/disk2": ("UUID=u-b", "btrfs", True),
                               "/mnt/cache": ("UUID=u-cache", "btrfs", False)})
        self.assertEqual(p["merged"]["/mnt/user"], ["/mnt/cache=RW", "/mnt/disk1=RO", "/mnt/disk2=RO"])
        self.assertEqual(p["merged"]["/mnt/user0"], ["/mnt/disk1=RO", "/mnt/disk2=RO"])
        self.assertEqual(p["parity"], [{"slot": "parity", "dev": "sdc"}])
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
        self.assertIn("UUID=u-a /mnt/disk1 xfs ro,defaults,nofail,noatime 0 0", text)
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

    def test_a_bad_shape_is_refused_before_any_job(self):
        for bad in ({"data": [{"slot": "disk0", "id": "X", "fs": "xfs"}]},
                    {"data": [{"slot": "disk1", "id": "a b;rm", "fs": "xfs"}]},
                    {"data": [{"slot": "disk1", "id": "X", "fs": "ext4"}]},
                    {"pools": [{"name": "Cache!", "fs": "btrfs"}]},
                    {"parity": [{"id": "X"}]}):
            w, why = self.want({"want": bad})
            self.assertIsNone(w, bad)
            self.assertTrue(why)
