"""The USB stick maker (R161 step 5, tools/aerieos-stick.py): the disks
listed off the system's own tools, the system disk and a fixed disk never
written, an image written whole from its xz and read back, a sha256 that
does not match refused before anything is written."""
import hashlib
import importlib.util
import io
import json
import lzma
import os
import stat
import subprocess
import sys
import tempfile
import unittest
from unittest import mock

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.abspath(os.path.join(HERE, "..", "..", ".."))
TOOL = os.path.join(ROOT, "tools", "aerieos-stick.py")


def load():
    spec = importlib.util.spec_from_file_location("aerieos_stick", TOOL)
    m = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(m)
    return m


# The system on a partition, as it always is: the disk's own mount points
# are empty, and a USB disk the machine booted from is no stick (B474).
LSBLK = '{"blockdevices": [{"name": "sda", "size": 512110190592, "model": "Samsung SSD", "rm": false, "tran": "sata", "type": "disk", "mountpoints": [null],' \
        ' "children": [{"name": "sda2", "type": "part", "mountpoints": ["/"]}]},' \
        '{"name": "sdb", "size": 32000000000, "model": "Ultra Fit", "rm": true, "tran": "usb", "type": "disk", "mountpoints": [null],' \
        ' "children": [{"name": "sdb1", "type": "part", "mountpoints": ["/media/u/BACKUP"]}]},' \
        '{"name": "sdc", "size": 1000000000000, "model": "T7", "rm": false, "tran": "usb", "type": "disk", "mountpoints": [null],' \
        ' "children": [{"name": "sdc1", "type": "part", "mountpoints": ["/boot/efi"]}, {"name": "sdc2", "type": "part", "mountpoints": ["/"]}]},' \
        '{"name": "loop0", "size": 1, "type": "loop", "mountpoints": []}]}'


class Stick(unittest.TestCase):
    def setUp(self):
        self.m = load()
        self.d = tempfile.mkdtemp()
        p = os.path.join(self.d, "lsblk")
        with open(p, "w") as f:
            f.write(f"#!/bin/sh\ncase \"$*\" in *MOUNTPOINTS\\ /dev/*) echo '';; *) cat <<'EOF'\n{LSBLK}\nEOF\n;; esac\n")
        os.chmod(p, stat.S_IRWXU)
        self.env = mock.patch.dict(os.environ, {"PATH": self.d + ":" + os.environ.get("PATH", "")})
        self.env.start(); self.addCleanup(self.env.stop)
        self.linux = mock.patch.object(self.m.platform, "system", return_value="Linux")
        self.linux.start(); self.addCleanup(self.linux.stop)

    def test_the_disks_are_listed_and_only_a_removable_one_may_be_written(self):
        rows = self.m.disks()
        self.assertEqual([(r["id"], r["removable"], r["system"]) for r in rows],
                         [("/dev/sda", False, True), ("/dev/sdb", True, False), ("/dev/sdc", True, True)])
        for dev in ("/dev/sda", "/dev/sdc"):
            with self.assertRaises(SystemExit):
                self.m.pick(dev)
        with self.assertRaises(SystemExit):
            self.m.pick("/dev/sdz")
        self.assertEqual(self.m.pick("/dev/sdb")["model"], "Ultra Fit")
        # B614: what is mounted on it is in its name, so the confirmation
        # tells a backup disk of the stick's make and size from the stick.
        self.assertEqual(self.m.named(self.m.pick("/dev/sdb")), "Ultra Fit, 32.0 GB, mounted at /media/u/BACKUP")
        self.assertEqual(rows[0]["mounts"], ["/"])

    def test_a_mac_lists_where_each_disk_is_mounted_and_marks_the_disk_it_runs_from(self):
        # B614 and B617: an exFAT stick's volume is on the disk itself, an
        # APFS volume on the synthesized disk whose physical store points
        # back; a Mac booted from an external disk lists it as external.
        import plistlib

        def pl(d):
            return plistlib.dumps(d).decode()
        listing = {"AllDisksAndPartitions": [
            {"DeviceIdentifier": "disk2", "Partitions": [{"DeviceIdentifier": "disk2s1", "MountPoint": "/Volumes/BACKUP"}]},
            {"DeviceIdentifier": "disk3", "Partitions": [{"DeviceIdentifier": "disk3s2", "Content": "Apple_APFS"}]},
            {"DeviceIdentifier": "disk4", "APFSPhysicalStores": [{"DeviceIdentifier": "disk3s2"}],
             "APFSVolumes": [{"DeviceIdentifier": "disk4s1", "MountPoint": "/Volumes/Photos"}, {"DeviceIdentifier": "disk4s2"}]},
            {"DeviceIdentifier": "disk5", "Partitions": [{"DeviceIdentifier": "disk5s2", "Content": "Apple_APFS"}]}]}
        info = {"/": {"APFSPhysicalStores": [{"DeviceIdentifier": "disk5s2"}], "ParentWholeDisk": "disk6"},
                "disk2": {"TotalSize": 32000000000, "MediaName": "Ultra Fit", "RemovableMediaOrExternalDevice": True},
                "disk3": {"TotalSize": 1000000000000, "MediaName": "T7", "RemovableMediaOrExternalDevice": True},
                "disk5": {"TotalSize": 500000000000, "MediaName": "Boot SSD", "RemovableMediaOrExternalDevice": True}}

        def run(cmd, **_kw):
            if cmd[:2] == ["diskutil", "list"]:
                out = {**listing, "WholeDisks": ["disk2", "disk3", "disk5"]} if "physical" in cmd else listing
            else:
                out = info[cmd[-1]]
            return subprocess.CompletedProcess(cmd, 0, pl(out), "")
        with mock.patch.object(self.m.platform, "system", return_value="Darwin"), mock.patch.object(self.m.subprocess, "run", run):
            rows = self.m.disks()
            self.assertEqual([(r["id"], r["system"], r["mounts"]) for r in rows],
                             [("/dev/disk2", False, ["/Volumes/BACKUP"]), ("/dev/disk3", False, ["/Volumes/Photos"]), ("/dev/disk5", True, [])])
            self.assertEqual(self.m.named(rows[1]), "T7, 1000.0 GB, mounted at /Volumes/Photos")
            with self.assertRaises(SystemExit):
                self.m.pick("/dev/disk5")

    def test_a_write_that_stops_is_said_with_what_to_do(self):
        # B615: the stick pulled part way raised out of the tool as a traceback.
        import argparse
        img = os.path.join(self.d, "aerieos-os-0.9.0.stick.raw.xz")
        with lzma.open(img, "wb") as f:
            f.write(b"\0" * 4096)
        a = argparse.Namespace(disk="/dev/sdb", image=img, release=None, channel="normal", set=None, config=None, mirror=None, yes=True, no_verify=True)
        with mock.patch.object(self.m, "write_image", side_effect=OSError(5, "Input/output error")), \
                mock.patch.object(self.m.shutil, "which", return_value=None), mock.patch.object(self.m, "say"), \
                mock.patch.object(self.m, "die", side_effect=SystemExit) as die, self.assertRaises(SystemExit):
            self.m.cmd_write(a)
        self.assertIn("the write stopped (Input/output error): the stick was unplugged or is failing", die.call_args[0][0])
        self.assertIn("write it again", die.call_args[0][0])

    def test_a_disk_on_windows_is_written_and_read_with_windows_own_calls(self):
        import ctypes
        disk = bytearray(8192)
        at = [0]
        closed = []

        class Fn:
            def __init__(self, f):
                self.f, self.argtypes = f, None

            def __call__(self, *a):
                return self.f(*a)

        def write(h, b, n, done, _o):
            disk[at[0]:at[0] + n] = b[:n]
            at[0] += n
            done._obj.value = n
            return 1

        def read(h, buf, n, done, _o):
            got = bytes(disk[at[0]:at[0] + n])
            ctypes.memmove(buf, got, len(got))
            at[0] += len(got)
            done._obj.value = len(got)
            return 1

        def seek(h, pos, _new, _how):
            at[0] = pos
            return 1
        k = type("K", (), {})()
        k.WriteFile, k.ReadFile, k.SetFilePointerEx = Fn(write), Fn(read), Fn(seek)
        k.FlushFileBuffers, k.CloseHandle = Fn(lambda h: 1), Fn(closed.append)
        with mock.patch.object(ctypes, "WinDLL", create=True, return_value=k):
            with self.m.WinDisk(7, [8, 9]) as d:
                d.write(b"x" * 4096)
                d.sync()
                d.seek(0)
                self.assertEqual(d.read(4096), b"x" * 4096)
        self.assertEqual(closed, [7, 8, 9], "the disk and its volumes let go when it closes")

    def test_a_write_met_with_not_ready_is_tried_again_and_said_once(self):
        # 2 Nov: the first write after diskpart's clean met 'The device is not
        # ready' (Windows error 21), shown as IsADirectoryError, and the
        # maker stopped with nothing written.
        import ctypes
        refusals = [21, 21]
        at, said, slept = [0], [], []

        class Fn:
            def __init__(self, f):
                self.f, self.argtypes = f, None

            def __call__(self, *a):
                return self.f(*a)

        def write(h, b, n, done, _o):
            if refusals:
                refusals.pop()
                return 0
            at[0] += n
            done._obj.value = n
            return 1
        k = type("K", (), {})()
        k.WriteFile, k.SetFilePointerEx = Fn(write), Fn(lambda h, pos, _n, _w: 1)
        k.ReadFile = k.FlushFileBuffers = k.CloseHandle = Fn(lambda *a: 1)
        with mock.patch.object(ctypes, "WinDLL", create=True, return_value=k), \
                mock.patch.object(ctypes, "get_last_error", create=True, return_value=21), \
                mock.patch.object(ctypes, "FormatError", create=True, return_value="The device is not ready."), \
                mock.patch.multiple(self.m, say=said.append), mock.patch.object(self.m.time, "sleep", slept.append):
            d = self.m.WinDisk(7)
            self.assertEqual(d.write(b"x" * 4096), 4096)
            self.assertEqual(d.pos, 4096)
            self.assertEqual(len(slept), 2)
            self.assertEqual(len([s for s in said if "not ready yet" in s]), 1, "said once, not per second")
            refusals.extend([21] * 5)
            with self.assertRaises(self.m.DiskError) as e:
                d.write(b"x" * 4096, patience=3)
            self.assertIn("not ready after 3 seconds", str(e.exception))
            self.assertEqual(type(e.exception).__name__, "DiskError")
            # Any other refusal is said at once, with Windows' words.
            refusals[:] = [5]
            with mock.patch.object(ctypes, "get_last_error", create=True, return_value=5), \
                    mock.patch.object(ctypes, "FormatError", create=True, return_value="Access is denied."):
                with self.assertRaises(self.m.DiskError) as e:
                    d.write(b"x" * 4096)
            self.assertIn("Access is denied. (Windows error 5)", str(e.exception))

    def test_a_write_refused_after_the_clean_opens_the_disk_again(self):
        # 2 Nov, the maker on a stick: 'not ready' on the first write, then
        # 'access denied' on the same handle a second later, since Windows
        # had looked the disk over again; the handle is closed and the disk
        # opened and locked anew, then the write goes on where it was.
        import ctypes
        errs = [5, 21]
        handles, at, said, closed = [7], [0], [], []

        class Fn:
            def __init__(self, f):
                self.f, self.argtypes = f, None

            def __call__(self, *a):
                return self.f(*a)

        def write(h, b, n, done, _o):
            if errs:
                return 0
            at[0] += n
            done._obj.value = n
            return 1

        def reopen():
            handles.append(handles[-1] + 1)
            return handles[-1]
        seeks = []
        k = type("K", (), {})()
        k.WriteFile, k.SetFilePointerEx = Fn(write), Fn(lambda h, pos, _n, _w: seeks.append((h, pos)) or 1)
        k.ReadFile = k.FlushFileBuffers = Fn(lambda *a: 1)
        k.CloseHandle = Fn(closed.append)
        with mock.patch.object(ctypes, "WinDLL", create=True, return_value=k), \
                mock.patch.object(ctypes, "get_last_error", create=True, side_effect=lambda: errs.pop() if errs else 0), \
                mock.patch.object(ctypes, "FormatError", create=True, return_value="x"), \
                mock.patch.multiple(self.m, say=said.append), mock.patch.object(self.m.time, "sleep", lambda s: None):
            d = self.m.WinDisk(7, reopen=reopen)
            d.write(b"x" * 4096)
            self.assertEqual(d.write(b"y" * 4096), 4096)
        self.assertEqual(handles, [7, 8, 9], "opened again on each refusal")
        self.assertEqual(closed, [7, 8], "the handle from before closed each time")
        self.assertEqual(seeks, [(8, 0), (9, 0)], "the pointer back where the write belongs, on the new handle")
        self.assertEqual(d.h, 9)
        self.assertEqual(d.pos, 8192)
        self.assertEqual(len([s for s in said if "opening it again" in s]), 1)
        # Without a way to open again, access denied is said at once.
        errs[:] = [5]
        with mock.patch.object(ctypes, "WinDLL", create=True, return_value=k), \
                mock.patch.object(ctypes, "get_last_error", create=True, return_value=5), \
                mock.patch.object(ctypes, "FormatError", create=True, return_value="Access is denied."):
            with self.assertRaises(self.m.DiskError):
                self.m.WinDisk(7).write(b"z" * 4096)

    def test_a_disk_on_windows_is_cleared_before_it_is_written(self):
        answers = [1, 0]
        scripts = []

        def run(cmd, **_kw):
            scripts.append(open(cmd[-1]).read())
            return subprocess.CompletedProcess(cmd, answers.pop(0), "", "Virtual Disk Service error: access is denied")
        said = []
        with mock.patch.object(self.m.subprocess, "run", run), mock.patch.object(self.m.time, "sleep"), \
                mock.patch.object(self.m, "say", said.append):
            self.m.clean_disk(5)
            self.assertEqual(scripts[0], "select disk 5\nclean\n")
            self.assertEqual(len(scripts), 2, "tried again once it was refused")
            answers.extend([1] * 4)
            with mock.patch.object(self.m, "die", side_effect=SystemExit) as die, self.assertRaises(SystemExit):
                self.m.clean_disk(5)
            self.assertIn("access is denied", die.call_args[0][0])

    def test_the_write_is_whole_sectors_as_windows_asks(self):
        pieces = [b"a" * 1000, b"b" * (3 << 20), b"c" * 70001, b"d" * 5]
        out = list(self.m.sectors(iter(pieces)))
        self.assertTrue(all(len(p) % (1 << 20) == 0 for p in out[:-1]), [len(p) for p in out])
        self.assertEqual(len(out[-1]) % self.m.SECTOR, 0)
        joined = b"".join(out)
        whole = b"".join(pieces)
        self.assertEqual(joined[:len(whole)], whole)
        self.assertEqual(joined[len(whole):], bytes(len(joined) - len(whole)))

    def test_a_disk_on_windows_is_named_with_its_drive_letters(self):
        disks = '[{"Number":0,"Size":512110190592,"FriendlyName":"Samsung SSD","BusType":"NVMe","IsSystem":true,"IsBoot":true},' \
                '{"Number":2,"Size":31457280000,"FriendlyName":"SanDisk Ultra","BusType":"USB","IsSystem":false,"IsBoot":false}]'
        parts = '[{"DiskNumber":0,"DriveLetter":"C"},{"DiskNumber":2,"DriveLetter":"F"},{"DiskNumber":2,"DriveLetter":"E"}]'

        def ps(cmd, **_kw):
            return subprocess.CompletedProcess(cmd, 0, parts if "Get-Partition" in cmd[-1] else disks, "")
        with mock.patch.object(self.m.platform, "system", return_value="Windows"), mock.patch.object(self.m.subprocess, "run", ps):
            rows = self.m.disks()
        self.assertEqual([r["letters"] for r in rows], [["C:"], ["E:", "F:"]])
        self.assertEqual(self.m.named(rows[1]), "SanDisk Ultra, 31.5 GB, E: F:")
        self.assertEqual(self.m.named({"model": "", "size": 0}), "unnamed, 0.0 GB")

    def test_the_newest_release_is_the_newest_that_carries_a_stick_image(self):
        img = [{"name": "aerieos-os-0.9.0-dev.4724.stick.raw.xz"}]
        # A build from before the name carries a stick image named for the
        # old product: not this tool's (2 Nov, the maker took dev.4750's).
        old = [{"name": "builderbot-os-0.9.0-dev.4740.stick.raw.xz"}]
        rows = [{"tag_name": "v0.9.0-dev.4740", "prerelease": True, "assets": old},
                {"tag_name": "v0.9.0-dev.4724", "prerelease": True, "assets": img},
                {"tag_name": "v0.9.0-dev.4706", "prerelease": True, "assets": []},
                {"tag_name": "v0.8.2", "prerelease": False, "assets": []}]
        said, got = [], []

        def die(s):
            raise SystemExit(s)

        def fetch(url, dest, say_progress=True):
            got.append(url)
            raise SystemExit("fetched")
        with mock.patch.object(self.m.urllib.request, "urlopen", side_effect=lambda *a, **k: io.BytesIO(json.dumps(rows).encode())), \
                mock.patch.multiple(self.m, die=die, say=said.append, fetch=fetch):
            with self.assertRaises(SystemExit) as e:
                self.m.release_image("latest", "normal")
            self.assertIn("pick the dev channel", str(e.exception))
            rows.insert(0, {"tag_name": "v0.9.0-dev.4730", "prerelease": True, "assets": []})
            with self.assertRaises(SystemExit):
                self.m.release_image("latest", "dev")
        self.assertTrue(got[0].endswith("/v0.9.0-dev.4724/aerieos-os-0.9.0-dev.4724.stick.raw.xz"), got)
        self.assertIn("v0.9.0-dev.4730 carries no stick image", said[0])

    def test_a_named_release_without_a_stick_image_is_said_plainly(self):
        def die(s):
            raise SystemExit(s)

        def fetch(url, dest, say_progress=True):
            raise self.m.urllib.error.HTTPError(url, 404, "Not Found", {}, None)
        with mock.patch.multiple(self.m, die=die, say=lambda s: None, fetch=fetch):
            with self.assertRaises(SystemExit) as e:
                self.m.release_image("v0.8.2")
        self.assertIn("the v0.8.2 release carries no stick image", str(e.exception))

    def test_an_image_is_checked_against_its_build_attestation_where_gh_is(self):
        # R191 step 2: the bundle from GitHub's public API, gh verify --bundle.
        import io
        import json
        img = os.path.join(self.d, "aerieos-os-1.0.0.stick.raw.xz")
        with open(img, "wb") as f:
            f.write(b"image")
        gh = os.path.join(self.d, "gh")
        for rc, answer, ok in ((0, {"attestations": [{"bundle": {"x": 1}}]}, True),
                               (1, {"attestations": [{"bundle": {"x": 1}}]}, False),
                               (0, {"attestations": []}, False)):
            with open(gh, "w") as f:
                f.write(f"#!/bin/sh\n[ \"$4\" = --bundle ] || exit 9\nexit {rc}\n")
            os.chmod(gh, stat.S_IRWXU)
            with mock.patch.object(self.m.urllib.request, "urlopen", return_value=io.BytesIO(json.dumps(answer).encode())):
                if ok:
                    self.m.attested(img)
                else:
                    with self.assertRaises(SystemExit):
                        self.m.attested(img)
        os.unlink(gh)
        self.m.attested(img)  # no gh: said, and the sha256 is what held

    def test_an_image_is_written_whole_from_its_xz_and_read_back(self):
        raw = os.urandom(3 << 20) + b"\0" * (1 << 20)
        img = os.path.join(self.d, "aerieos-os-0.9.0.stick.raw.xz")
        with lzma.open(img, "wb") as f:
            f.write(raw)
        dev = os.path.join(self.d, "stick.img")
        with open(dev, "wb") as f:
            f.write(b"\xff" * len(raw))
        with mock.patch.object(self.m, "open_disk", side_effect=lambda d: open(d, "r+b", buffering=0)):
            self.m.write_image(img, dev)
        self.assertEqual(open(dev, "rb").read(), raw)
        with open(dev, "r+b") as f:
            f.seek(100); f.write(b"x")
        with self.assertRaises(SystemExit):
            self.m.verify(dev, len(raw), hashlib.sha256(raw).hexdigest())

    def test_a_sha256_that_does_not_match_is_refused(self):
        img = os.path.join(self.d, "x.xz")
        open(img, "wb").write(b"data")
        open(img + ".sha256", "w").write("0" * 64 + "  x.xz\n")
        with self.assertRaises(SystemExit):
            self.m.check_sha(img, img + ".sha256")
        open(img + ".sha256", "w").write(hashlib.sha256(b"data").hexdigest() + "  x.xz\n")
        self.m.check_sha(img, img + ".sha256")

    def test_the_tool_says_how(self):
        r = subprocess.run([sys.executable, TOOL, "--help"], capture_output=True, text=True, check=False)
        self.assertEqual(r.returncode, 0)
        self.assertIn("write DISK", r.stdout)
        self.assertIn("--set KEY=VALUE", r.stdout)
        w = subprocess.run([sys.executable, TOOL, "write", "--help"], capture_output=True, text=True, check=False).stdout
        self.assertIn("--set KEY=VALUE", w)
        self.assertIn("--channel", w, "the dev channel is anyone's to pick (the operator, 2 Nov)")

    def stick_with_env(self, at):
        """An image whose aerieos.env starts `at` bytes in, as lay-disk lays it."""
        block = self.m.ENV_MARK + b": KEY=VALUE lines the boot reads (TZ, BB_RELEASE_LINE, BB_HOSTNAME, BB_NET_*)\n"
        block += b" " * (self.m.ENV_SIZE - 1 - len(block)) + b"\n"
        raw = os.urandom(at) + block + os.urandom((3 << 20) - at)
        img = os.path.join(self.d, "aerieos-os-0.9.0.stick.raw.xz")
        with lzma.open(img, "wb") as f:
            f.write(raw)
        dev = os.path.join(self.d, "stick.img")
        with open(dev, "wb") as f:
            f.write(b"\xff" * len(raw))
        return raw, img, dev

    def test_set_writes_its_lines_into_the_sticks_env_file_even_across_two_chunks(self):
        # R161 step 12: the 4 KiB on the stick, found by its marker and written
        # in place, the file's size and everything around it as they were.
        for at in (1 << 20, (1 << 20) - 100):            # inside a chunk, and across the line
            raw, img, dev = self.stick_with_env(at)
            with mock.patch.object(self.m, "CHUNK", 1 << 20), \
                    mock.patch.object(self.m, "open_disk", side_effect=lambda d: open(d, "r+b", buffering=0)):
                self.m.write_image(img, dev, sets=["TZ=Europe/Berlin", "BB_RELEASE_LINE=0.9", "BB_NET_DNS=1.1.1.1,9.9.9.9"])
            got = open(dev, "rb").read()
            self.assertEqual(len(got), len(raw))
            self.assertEqual(got[:at], raw[:at])
            self.assertEqual(got[at + self.m.ENV_SIZE:], raw[at + self.m.ENV_SIZE:])
            env = got[at:at + self.m.ENV_SIZE].decode()
            self.assertTrue(env.startswith("# aerieos.env AERIE-STICK-ENV-1"))
            self.assertEqual([x for x in env.splitlines() if "=" in x and not x.startswith("#")], ["TZ=Europe/Berlin", "BB_RELEASE_LINE=0.9", "BB_NET_DNS=1.1.1.1,9.9.9.9"])

    def test_config_writes_the_prepared_configuration_beside_the_env_file(self):
        # R161 step 8: firstboot.json's 64 KiB behind its own marker, the two
        # files written in one pass, the rest of the image as it was.
        import json
        env = self.m.ENV_MARK + b": x\n"
        env += b" " * (self.m.ENV_SIZE - 1 - len(env)) + b"\n"
        boot = self.m.BOOT_MARK + b" " * (self.m.BOOT_SIZE - 1 - len(self.m.BOOT_MARK)) + b"\n"
        a, b = (1 << 20) - 50, (2 << 20) - 3000          # each across a chunk's end
        raw = os.urandom(a) + env + os.urandom(b - a - len(env)) + boot + os.urandom(1 << 20)
        img = os.path.join(self.d, "i.stick.raw.xz")
        with lzma.open(img, "wb") as f:
            f.write(raw)
        dev = os.path.join(self.d, "stick.img")
        open(dev, "wb").write(b"\xff" * len(raw))
        cfg = os.path.join(self.d, "plan.json")
        json.dump({"format": 1, "machine": {"hostname": "tower"}, "first_run": "skip"}, open(cfg, "w"))
        with mock.patch.object(self.m, "CHUNK", 1 << 20), \
                mock.patch.object(self.m, "open_disk", side_effect=lambda d: open(d, "r+b", buffering=0)):
            self.m.write_image(img, dev, sets=["TZ=UTC"], config=cfg)
        got = open(dev, "rb").read()
        whole = len(raw) + (-len(raw) % self.m.SECTOR)    # the write ends on a whole sector
        self.assertEqual(len(got), whole)
        self.assertEqual(got[len(raw):], bytes(whole - len(raw)))
        self.assertIn(b"\nTZ=UTC\n", got[a:a + self.m.ENV_SIZE])
        lines = got[b:b + self.m.BOOT_SIZE].decode().split("\n", 1)
        self.assertEqual(lines[0], "AERIE-FIRSTBOOT-1")
        self.assertEqual(json.loads(lines[1])["machine"]["hostname"], "tower")
        self.assertEqual(got[b + self.m.BOOT_SIZE:len(raw)], raw[b + self.m.BOOT_SIZE:])
        json.dump({"machine": {}}, open(cfg, "w"))
        with self.assertRaises(SystemExit):
            self.m.boot_block(cfg)

    def test_mirror_writes_the_catalogs_mirror_into_its_slot(self):
        # R169 step 6: catalog-mirror.bin's 64 MiB behind its marker, the
        # archive's length on the next line; held smaller here, the slot's
        # shape the same.
        import io
        import tarfile
        arc = os.path.join(self.d, "m.tar.gz")
        with tarfile.open(arc, "w:gz") as t:
            body = b'{"version": 1, "packs": []}'
            ti = tarfile.TarInfo("catalog-mirror/index.json")
            ti.size = len(body)
            t.addfile(ti, io.BytesIO(body))
        size = 1 << 20
        slot = self.m.MIRROR_MARK + b"000000000000\n"
        slot += b" " * (size - 1 - len(slot)) + b"\n"
        a = (3 << 20) - 100
        raw = os.urandom(a) + slot + os.urandom(1 << 20)
        img = os.path.join(self.d, "m.stick.raw.xz")
        with lzma.open(img, "wb") as f:
            f.write(raw)
        dev = os.path.join(self.d, "stick-m.img")
        open(dev, "wb").write(b"\xff" * len(raw))
        with mock.patch.object(self.m, "CHUNK", 1 << 20), mock.patch.object(self.m, "MIRROR_SIZE", size), \
                mock.patch.object(self.m, "open_disk", side_effect=lambda d: open(d, "r+b", buffering=0)):
            self.m.write_image(img, dev, mirror=arc)
        got = open(dev, "rb").read()
        whole = len(raw) + (-len(raw) % self.m.SECTOR)    # the write ends on a whole sector
        self.assertEqual(len(got), whole)
        self.assertEqual(got[len(raw):], bytes(whole - len(raw)))
        head = got[a:a + len(self.m.MIRROR_MARK) + 13]
        n = int(head[len(self.m.MIRROR_MARK):-1])
        self.assertEqual(n, os.path.getsize(arc))
        self.assertEqual(got[a + len(head):a + len(head) + n], open(arc, "rb").read())
        self.assertEqual(got[a + size:len(raw)], raw[a + size:])
        open(os.path.join(self.d, "not.tar.gz"), "wb").write(b"nope")
        with self.assertRaises(SystemExit):
            self.m.mirror_block(os.path.join(self.d, "not.tar.gz"))

    def test_set_is_refused_on_a_bad_line_and_on_an_image_with_no_env_file(self):
        with self.assertRaises(SystemExit):
            self.m.env_block(["tz=Europe/Berlin"])
        with self.assertRaises(SystemExit):
            self.m.env_block(["TZ=Europe/Berlin; rm -rf /"])
        img = os.path.join(self.d, "old.stick.raw.xz")
        with lzma.open(img, "wb") as f:
            f.write(os.urandom(1 << 20))
        dev = os.path.join(self.d, "stick.img")
        open(dev, "wb").write(b"\xff" * (1 << 20))
        with mock.patch.object(self.m, "open_disk", side_effect=lambda d: open(d, "r+b", buffering=0)), \
                self.assertRaises(SystemExit):
            self.m.write_image(img, dev, sets=["TZ=Europe/Berlin"])


if __name__ == "__main__":
    unittest.main()
