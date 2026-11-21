"""What the installer keeps between runs is in a directory of its account's own.

/tmp is every account's. A keyring found lying there verified the next
signed install, and a document found there was taken as what an upstream
published. So a publisher's keys are dearmored every time, into the
caller's own directory for that one check, and a fetched document or
sdkmanager's table is kept only in a directory this account made 0700 and
still owns, with no bit for anybody else: one that is a link, a file,
another mode or another account's is not used, and nothing planted in it or
at the names used before is read."""
import hashlib
import os
import shutil
import subprocess
import sys
import tempfile
import unittest
from unittest import mock

HERE = os.path.dirname(os.path.abspath(__file__))
LIB = os.path.normpath(os.path.join(HERE, "..", "..", "lib"))
sys.path.insert(0, LIB)
import sdkmeta  # noqa: E402

WHERE = sdkmeta.CACHE_DIR


class Documents(unittest.TestCase):
    def setUp(self):
        self.d = tempfile.mkdtemp()
        self.addCleanup(shutil.rmtree, self.d, True)
        self.cache = os.path.join(self.d, "cache")
        p = mock.patch.multiple(sdkmeta, CACHE_DIR=self.cache, CACHE_TTL=900)
        p.start()
        self.addCleanup(p.stop)

    def plant(self, key, body=b"planted"):
        with open(os.path.join(self.cache, hashlib.sha256(key.encode()).hexdigest()[:32]), "wb") as f:
            f.write(body)

    def test_a_directory_of_its_own_is_made_private_and_used(self):
        self.assertEqual(sdkmeta.cache_dir(), self.cache)
        self.assertEqual(os.stat(self.cache).st_mode & 0o777, 0o700)
        self.assertEqual(sdkmeta._cached("GET x", lambda: b"fetched"), b"fetched")
        self.assertEqual(sdkmeta._cached("GET x", lambda: b"again"), b"fetched", "kept for the next ask")

    def test_one_that_others_may_write_or_read_is_not_used(self):
        for mode in (0o755, 0o777, 0o770, 0o701, 0o704):
            shutil.rmtree(self.cache, ignore_errors=True)
            os.mkdir(self.cache)
            os.chmod(self.cache, mode)
            self.plant("GET x")
            self.assertEqual(sdkmeta.cache_dir(), "", oct(mode))
            self.assertEqual(sdkmeta._cached("GET x", lambda: b"fetched"), b"fetched", oct(mode))

    def test_a_link_or_a_file_at_its_name_is_not_used(self):
        real = os.path.join(self.d, "elsewhere")
        os.mkdir(real, 0o700)
        os.symlink(real, self.cache)
        self.plant("GET x")
        self.assertEqual(sdkmeta.cache_dir(), "")
        self.assertEqual(sdkmeta._cached("GET x", lambda: b"fetched"), b"fetched")
        self.assertEqual(len(os.listdir(real)), 1, "and nothing is written through it")
        os.unlink(self.cache)
        with open(self.cache, "w"):
            pass
        self.assertEqual(sdkmeta.cache_dir(), "")

    def test_another_account_s_directory_is_not_used(self):
        os.mkdir(self.cache, 0o700)
        self.plant("GET x")
        with mock.patch.object(sdkmeta.os, "geteuid", lambda: os.getuid() + 1):
            self.assertEqual(sdkmeta.cache_dir(), "")
            self.assertEqual(sdkmeta._cached("GET x", lambda: b"fetched"), b"fetched")

    def test_the_directory_is_named_for_this_account(self):
        self.assertEqual(os.path.basename(WHERE), f"bb-sdk-cache-{os.getuid()}")


@unittest.skipUnless(shutil.which("gpg"), "no gpg here")
class Keyring(unittest.TestCase):
    def setUp(self):
        self.d = tempfile.mkdtemp()
        self.addCleanup(shutil.rmtree, self.d, True)
        home = os.path.join(self.d, "gnupg")
        os.makedirs(home, mode=0o700)
        env = dict(os.environ, GNUPGHOME=home)
        subprocess.run(["gpg", "--batch", "--passphrase", "", "--quick-generate-key", "Publisher <p@example.com>", "ed25519", "sign", "0"],
                       env=env, capture_output=True, check=True)
        self.keys = os.path.join(self.d, "keys")
        os.makedirs(self.keys)
        self.asc = subprocess.run(["gpg", "--batch", "--armor", "--export"], env=env, capture_output=True, check=True).stdout
        with open(os.path.join(self.keys, "pub.asc"), "wb") as f:
            f.write(self.asc)
        self.cache = os.path.join(self.d, "cache")
        p = mock.patch.multiple(sdkmeta, KEYS_DIR=self.keys, CACHE_DIR=self.cache)
        p.start()
        self.addCleanup(p.stop)

    def test_a_keyring_lying_at_the_name_used_before_is_not_the_one_read(self):
        os.mkdir(self.cache, 0o700)
        planted = os.path.join(self.cache, "keys-" + hashlib.sha256(self.asc).hexdigest()[:16] + ".gpg")
        with open(planted, "wb") as f:
            f.write(b"a stranger's keys")
        into = os.path.join(self.d, "check")
        os.mkdir(into, 0o700)
        ring = sdkmeta.keyring("pub.asc", None, into)
        self.assertEqual(os.path.dirname(ring), into)
        with open(ring, "rb") as f:
            self.assertNotEqual(f.read(), b"a stranger's keys")
        again = sdkmeta.keyring("pub.asc", None, into)
        self.assertNotEqual(ring, again, "made again every time it is asked for")

    def test_the_command_makes_it_in_the_directory_it_is_handed(self):
        into = os.path.join(self.d, "check")
        os.mkdir(into, 0o700)
        with mock.patch("builtins.print") as said:
            sdkmeta.main(["keyring", "pub.asc", "", into])
        self.assertEqual(os.path.dirname(said.call_args[0][0]), into)


class TheShell(unittest.TestCase):
    """sdk.sh's own: the directory it keeps sdkmanager's table in."""

    def setUp(self):
        self.d = tempfile.mkdtemp()
        self.addCleanup(shutil.rmtree, self.d, True)
        self.mine = os.path.join(self.d, f"bb-sdk-cache-{os.getuid()}")
        self.bin = os.path.join(self.d, "bin")
        os.mkdir(self.bin)
        with open(os.path.join(self.bin, "sdkmanager"), "w") as f:
            f.write("#!/bin/sh\necho 'Available Packages: the real table'\n")
        os.chmod(os.path.join(self.bin, "sdkmanager"), 0o755)

    def sh(self, script):
        p = subprocess.run(["bash", "-c", f'set -euo pipefail\n. "{LIB}/common.sh"\n. "{LIB}/sdk.sh"\nsdk_root_flag() {{ echo --x; }}\n' + script],
                           capture_output=True, text=True, check=False, timeout=60,
                           env={"PATH": f"{self.bin}:/usr/bin:/bin", "TMPDIR": self.d, "HOME": self.d})
        return p.returncode, p.stdout, p.stderr

    def test_the_table_is_kept_in_a_private_directory_of_this_account_s(self):
        rc, out, err = self.sh("sdk_android_list; sdk_cache_dir")
        self.assertEqual(rc, 0, err)
        self.assertIn("the real table", out)
        self.assertEqual(out.strip().splitlines()[-1], self.mine)
        self.assertEqual(os.stat(self.mine).st_mode & 0o777, 0o700)
        self.assertTrue(os.path.isfile(os.path.join(self.mine, "sdk-list.cache")))

    def test_a_table_planted_at_the_name_used_before_is_not_read(self):
        with open(os.path.join(self.d, "bb-sdk-list.cache"), "w") as f:
            f.write("Available Packages: a planted table\n")
        rc, out, _ = self.sh("sdk_android_list")
        self.assertEqual((rc, out), (0, "Available Packages: the real table\n"))

    def test_a_directory_that_is_not_private_or_is_a_link_keeps_nothing(self):
        for make in ("open", "link", "file"):
            shutil.rmtree(self.mine, ignore_errors=True)
            if os.path.lexists(self.mine):
                os.unlink(self.mine)
            elsewhere = os.path.join(self.d, "elsewhere-" + make)
            os.mkdir(elsewhere, 0o700)
            planted = elsewhere
            if make == "open":
                os.mkdir(self.mine)
                os.chmod(self.mine, 0o755)
                planted = self.mine
            elif make == "link":
                os.symlink(elsewhere, self.mine)
            else:
                with open(self.mine, "w"):
                    pass
            if make != "file":
                with open(os.path.join(planted, "sdk-list.cache"), "w") as f:
                    f.write("Available Packages: a planted table\n")
            rc, out, err = self.sh("sdk_cache_dir && echo used; sdk_android_list; sdk_android_list_forget")
            self.assertEqual((rc, out), (0, "Available Packages: the real table\n"), (make, err))
            if make != "file":
                self.assertTrue(os.path.isfile(os.path.join(planted, "sdk-list.cache")), "nothing there is touched")


if __name__ == "__main__":
    unittest.main()
