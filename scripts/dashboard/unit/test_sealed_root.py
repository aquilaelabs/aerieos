"""A root slot is sealed: its dm-verity tree follows the squashfs in the same
file (image/seal-root), the initrd that boots it carries the tree's root
hash and opens the slot through it, and an update holds a root to that hash
before it writes the slot and as the slot reads back. What can be held
without booting is held here: the script that seals, the reader an update
checks with, the initramfs's script run on its own lines, and that the
build, the ISO, the image's packages and the workflow each carry their
part. The boot itself is the image workflow's boot test."""
import os
import re
import shutil
import subprocess
import sys
import tempfile
import unittest

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.abspath(os.path.join(HERE, "..", "..", ".."))
IMG = os.path.join(ROOT, "image")
EXTRA = os.path.join(IMG, "mkosi.extra")
sys.path.insert(0, HERE)
import agentpkg  # noqa: E402
import sealedroot  # noqa: E402

agent = agentpkg.load("aerieos_agent_sealed")
av = sys.modules[agent.Agent.__module__.rsplit(".", 1)[0] + ".osimage"]
TOOLS = all(shutil.which(t) for t in ("veritysetup", "cpio", "mksquashfs"))


def read(*parts):
    with open(os.path.join(*parts), encoding="utf-8") as f:
        return f.read()


class Reader(unittest.TestCase):
    def setUp(self):
        t = tempfile.TemporaryDirectory()
        self.addCleanup(t.cleanup)
        self.d = t.name

    def put(self, name, data):
        p = os.path.join(self.d, name)
        with open(p, "wb") as f:
            f.write(data)
        return p

    def test_a_sealed_root_answers_to_its_hash_and_to_no_other(self):
        for blocks in (1, 2, 128, 129, 300):
            data, want = sealedroot.seal(sealedroot.root(blocks=blocks))
            p = self.put(f"r{blocks}", data + b"\xff" * 9000)        # a slot is longer than its root
            self.assertEqual(av.verity_why(p, want), "", blocks)
            self.assertIn("answers to another hash", av.verity_why(p, "0" * 64))
            with open(p, "rb") as f:
                self.assertEqual(av.slot_span(f), len(data), "the root and its tree, and none of the slot after them")

    def test_one_changed_byte_anywhere_in_it_is_said(self):
        data, want = sealedroot.seal(sealedroot.root(blocks=300))
        for at, what in ((100, "the squashfs's first block"), (200 * 4096 + 9, "a block in the middle"),
                         (300 * 4096 + 4096 + 40, "the tree's top level"), (len(data) - 4096 * 2, "the level over the data")):
            bad = bytearray(data)
            bad[at] ^= 1
            why = av.verity_why(self.put("bad", bytes(bad)), want)
            self.assertTrue(why, what)
            self.assertRegex(why, "changed or did not write|does not hold together|another hash", what)

    def test_a_root_with_no_tree_or_one_not_its_own_is_said(self):
        plain = sealedroot.root(blocks=4)
        self.assertEqual(av.verity_why(self.put("plain", plain.ljust(5 * 4096, b"\0")), "0" * 64), "has no dm-verity tree after its squashfs")
        with open(self.put("plain2", plain), "rb") as f:
            self.assertEqual(av.slot_span(f), len(plain), "a root built before roots were sealed is its squashfs")
        self.assertEqual(av.verity_why(self.put("empty", b"\0" * 8192), "0" * 64), "holds no squashfs")
        with open(self.put("empty2", b"\0" * 8192), "rb") as f:
            self.assertEqual(av.slot_span(f), 0)
        # A tree made for a root of another length, put after this one: not a seal.
        other, _ = sealedroot.seal(sealedroot.root(blocks=9))
        moved = plain.ljust(4 * 4096, b"\0") + other[9 * 4096:]
        self.assertEqual(av.verity_why(self.put("moved", moved), "0" * 64), "has no dm-verity tree after its squashfs")
        cut, want = sealedroot.seal(sealedroot.root(blocks=300))
        self.assertEqual(av.verity_why(self.put("cut", cut[:-4096]), want), "could not be read whole: it ends before its dm-verity tree does")
        self.assertEqual(av.verity_why(self.put("cut2", cut[:200 * 4096]), want), "has no dm-verity tree after its squashfs")


@unittest.skipUnless(TOOLS, "veritysetup, cpio and mksquashfs are not all here")
class TheRealTool(unittest.TestCase):
    """image/seal-root with the real veritysetup, read by the reader and
    matched by the test's own writer."""
    def setUp(self):
        t = tempfile.TemporaryDirectory()
        self.addCleanup(t.cleanup)
        self.d = t.name
        tree = os.path.join(self.d, "tree")
        os.mkdir(tree)
        for i in range(4):
            with open(os.path.join(tree, f"f{i}"), "wb") as f:
                f.write(os.urandom(300000))
        self.sq, self.initrd = os.path.join(self.d, "root.squashfs"), os.path.join(self.d, "initrd")
        subprocess.run(["mksquashfs", tree, self.sq, "-comp", "zstd", "-noappend", "-quiet"], check=True, capture_output=True)
        with open(self.initrd, "wb") as f:
            f.write(b"an initrd of some length that is no multiple of four.")

    def seal(self, sq=None, initrd=None):
        return subprocess.run(["bash", os.path.join(IMG, "seal-root"), sq or self.sq, initrd or self.initrd], capture_output=True, text=True,
                              env=dict(os.environ, SOURCE_DATE_EPOCH="1700000000"), check=False)

    def test_it_seals_a_root_the_reader_takes_and_says_its_hash(self):
        with open(self.sq, "rb") as f:
            before = f.read()
        r = self.seal()
        self.assertEqual(r.returncode, 0, r.stderr)
        want = r.stdout.strip()
        self.assertRegex(want, r"^[0-9a-f]{64}$")
        self.assertEqual(av.verity_why(self.sq, want), "")
        size = os.path.getsize(self.sq)
        with open(self.sq, "rb") as f:
            self.assertEqual(av.slot_span(f), size)
            f.seek(0)
            sealed = f.read()
        self.assertTrue(sealed.startswith(before), "the squashfs's own bytes are as they were")
        # The initrd: begun again on a 512-byte boundary, the file's line in clear.
        with open(self.initrd, "rb") as f:
            tail = f.read()
        self.assertEqual(tail[512:518], b"070701", "a newc archive where the kernel looks for the next one")
        self.assertIn(f"HASH={want}\nBYTES={size}\n".encode(), tail)
        self.assertNotIn(b"070701", tail[:512])
        # The test's own writer makes the tree veritysetup made, from its salt.
        salt = sealed[len(before) + 88:len(before) + 88 + 32]
        mine, mine_hash = sealedroot.seal(before, salt)
        self.assertEqual(mine_hash, want)
        self.assertEqual(mine[len(before) + 4096:], sealed[len(before) + 4096:], "every level of the tree, where veritysetup put it")

    def test_the_same_root_seals_to_the_same_bytes_and_a_sealed_one_is_not_sealed_again(self):
        sq2, initrd2 = self.sq + ".2", self.initrd + ".2"
        shutil.copyfile(self.sq, sq2)
        shutil.copyfile(self.initrd, initrd2)
        a, b = self.seal(), self.seal(sq2, initrd2)
        self.assertEqual((a.returncode, a.stdout), (0, b.stdout), a.stderr + b.stderr)
        for one, two in ((self.sq, sq2), (self.initrd, initrd2)):
            with open(one, "rb") as f, open(two, "rb") as g:
                self.assertEqual(f.read(), g.read())
        again = self.seal()
        self.assertEqual(again.returncode, 1)
        self.assertIn("sealed already", again.stderr)

    def test_a_byte_changed_after_sealing_is_what_veritysetup_and_the_reader_both_refuse(self):
        want = self.seal().stdout.strip()
        with open(self.sq, "r+b") as f:
            f.seek(70000)
            b = f.read(1)
            f.seek(70000)
            f.write(bytes([b[0] ^ 1]))
        self.assertIn("changed or did not write", av.verity_why(self.sq, want))


class Initramfs(unittest.TestCase):
    """scripts/local-top/aerieos-os-verity, its own lines run with the
    initramfs's library, the hash file, the command line and veritysetup
    stood in for."""
    def run_it(self, cmdline, conf="HASH=" + "ab" * 32 + "\nBYTES=12288\n", opens=True, used=5000):
        with tempfile.TemporaryDirectory() as d:
            dev = os.path.join(d, "slot")
            with open(dev, "wb") as f:
                f.write(b"hsqs" + b"\0" * 36 + used.to_bytes(8, "little") + b"\0" * 9000)
            for name, text in (("cmdline", cmdline.replace("DEV", dev) + "\n"), ("functions", 'panic() { echo "PANIC: $*"; exit 9; }\n')):
                with open(os.path.join(d, name), "w") as f:
                    f.write(text)
            if conf is not None:
                with open(os.path.join(d, "verity"), "w") as f:
                    f.write(conf)
            os.mkdir(os.path.join(d, "bin"))
            with open(os.path.join(d, "bin", "veritysetup"), "w") as f:
                f.write(f'#!/bin/sh\necho "$*" > {d}/asked\n' + (f"touch {d}/aerieroot\n" if opens else 'echo "Verification of root hash failed."; exit 1\n'))
            with open(os.path.join(d, "bin", "modprobe"), "w") as f:
                f.write(f'#!/bin/sh\necho "$*" >> {d}/modules\n')
            for t in ("veritysetup", "modprobe"):
                os.chmod(os.path.join(d, "bin", t), 0o755)
            script = read(EXTRA, "etc", "initramfs-tools", "scripts", "local-top", "aerieos-os-verity")
            for old, new in ((". /scripts/functions", f". {d}/functions"), ("/etc/aerieos-verity", f"{d}/verity"), ("/proc/cmdline", f"{d}/cmdline"),
                             ("/conf/param.conf", f"{d}/param.conf"), ("/dev/mapper/aerieroot", f"{d}/aerieroot"), ("/dev/kmsg", f"{d}/kmsg"),
                             ("[ ! -b ", "[ ! -e "), ("[ -b ", "[ -e "), ("/dev/*) dev=", f"{d}/*) dev="), ("sleep 0.1", "true")):
                self.assertIn(old, script, old)
                script = script.replace(old, new)
            r = subprocess.run(["sh", "-c", script], capture_output=True, text=True, env=dict(os.environ, PATH=f"{d}/bin:" + os.environ["PATH"]), check=False)
            got = {n: (read(d, n) if os.path.exists(os.path.join(d, n)) else "") for n in ("asked", "param.conf", "modules")}
            return r, got, dev

    def test_the_slot_is_opened_through_its_tree_and_the_boot_mounts_the_verified_root(self):
        r, got, dev = self.run_it("root=DEV rootfstype=squashfs aerieslot=a")
        self.assertEqual(r.returncode, 0, r.stdout + r.stderr)
        # The tree starts at the first 4096-byte block after the squashfs's 5000 bytes.
        self.assertEqual(got["asked"].split(), ["open", dev, "aerieroot", dev, "ab" * 32, "--hash-offset=8192"])
        self.assertEqual(got["param.conf"], f"ROOT={os.path.dirname(dev)}/aerieroot\n")
        self.assertEqual(got["modules"].split(), ["-q", "dm_mod", "-q", "dm_verity"])

    def test_a_slot_that_does_not_answer_to_the_hash_stops_the_boot_saying_so(self):
        r, got, _ = self.run_it("root=DEV aerieslot=a", opens=False)
        self.assertEqual(r.returncode, 9)
        self.assertIn("PANIC: AerieOS: the root on", r.stdout)
        self.assertIn("is not the one this version was built with", r.stdout)
        self.assertIn("pick the other slot from the boot menu", r.stdout)
        self.assertEqual(got["param.conf"], "", "nothing is mounted in its place")

    def test_an_initrd_with_no_hash_and_the_iso_booted_live_mount_as_before(self):
        for cmdline, conf in (("root=DEV aerieslot=a", None), ("boot=live root=DEV", "HASH=" + "ab" * 32 + "\n"), ("root=DEV", "BYTES=1\n")):
            r, got, _ = self.run_it(cmdline, conf=conf)
            self.assertEqual((r.returncode, got["asked"], got["param.conf"]), (0, "", ""), cmdline)

    def test_a_boot_that_names_nothing_to_verify_stops(self):
        r, _, _ = self.run_it("rootfstype=squashfs")
        self.assertEqual(r.returncode, 9)
        self.assertIn("named no root to verify", r.stdout)

    def test_it_runs_after_the_copy_into_memory_which_takes_the_tree_too(self):
        script = read(EXTRA, "etc", "initramfs-tools", "scripts", "local-top", "aerieos-os-verity")
        self.assertIn('PREREQ="aerieos-os-toram"', script)
        toram = read(EXTRA, "etc", "initramfs-tools", "scripts", "local-top", "aerieos-os-toram")
        self.assertIn('BYTES:*) [ "$v" -gt "$bytes" ] && bytes="$v"', toram)
        self.assertLess(toram.index("/etc/aerieos-verity"), toram.index('mb=$(( (bytes + 1048575) / 1048576 ))'))

    def test_the_initramfs_carries_veritysetup_and_the_verity_target(self):
        hook = read(EXTRA, "etc", "initramfs-tools", "hooks", "aerieos-os")
        self.assertIn("copy_exec /usr/sbin/veritysetup /sbin", hook)
        self.assertIn("manual_add_modules dm_verity", hook)
        mods = read(EXTRA, "etc", "initramfs-tools", "modules").split()
        self.assertIn("dm_verity", mods)
        self.assertIn("dm_mod", mods)
        self.assertRegex(read(IMG, "mkosi.conf"), r"(?m)^\s+cryptsetup-bin$")
        mode = os.stat(os.path.join(EXTRA, "etc", "initramfs-tools", "scripts", "local-top", "aerieos-os-verity")).st_mode
        self.assertTrue(mode & 0o111, "an initramfs script that is not executable is not run")


class Build(unittest.TestCase):
    def test_the_root_is_sealed_before_anything_copies_it(self):
        b = read(IMG, "build.sh")
        seal = b.index('bash "$HERE/seal-root" "$OUT/$NAME.root.squashfs" "$OUT/$NAME.initrd" > "$OUT/$NAME.verity"')
        self.assertLess(b.index('mksquashfs "$TREE" "$OUT/$NAME.root.squashfs"'), seal)
        for after in ('bash "$HERE/lay-disk" "$LOOP"', 'cp "$OUT/$NAME.root.squashfs" "$ISO/live/filesystem.squashfs"',
                      'install -m 0644 "$OUT/$NAME.initrd" "$ISO/live/initrd"', 'install -m 0644 "$OUT/$NAME.verity" "$ISO/live/verity"'):
            self.assertLess(seal, b.index(after), after)
        self.assertEqual(av.PIECES_SINCE, {"verity": "live/verity"})
        # The slot's room is measured with its tree.
        self.assertLess(seal, b.rindex("SQ_MIB=$(("))

    def test_the_workflow_that_builds_the_image_has_the_tools(self):
        w = read(ROOT, ".github", "workflows", "os-image.yml")
        line = next(ln for ln in w.splitlines() if "apt_tools squashfs-tools" in ln)
        self.assertIn(" cryptsetup-bin ", line)
        self.assertIn(" cpio ", line)

    def test_the_readers_block_and_fan_are_the_scripts(self):
        s = read(IMG, "seal-root")
        self.assertIn(f"BLOCK={av.VERITY_BLOCK}", s)
        self.assertIn(f"n=$(( (n + {av.VERITY_FAN - 1}) / {av.VERITY_FAN} ))", s)
        self.assertIn("--hash=sha256", s)
        self.assertTrue(re.search(r"(?m)^set -euo pipefail$", s))


if __name__ == "__main__":
    unittest.main()
