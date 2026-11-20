"""A declared download held by its publisher's signature (pack format 5):
`signed` in the sha256's place, checked with gpgv under a key the entry
itself carries (source.keyring, a pack's install.keyring), which wins over
the shipped file of that name; the same keys hold a row's own signed
download and a signed checksum file. Whole installs from files on disk,
with a throwaway key in a private gpg home standing in for the publisher's
and a second for a stranger's."""
import json
import os
import shutil
import subprocess
import sys
import tempfile
import unittest
from unittest import mock

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))
import sdkstore  # noqa: E402
from sdkstore import sdkmeta  # noqa: E402


def gpg_key(home, who):
    os.makedirs(home, mode=0o700)
    env = dict(os.environ, GNUPGHOME=home)
    subprocess.run(["gpg", "--batch", "--passphrase", "", "--quick-gen-key", who, "ed25519", "sign", "never"],
                   env=env, capture_output=True, check=True)
    armored = subprocess.run(["gpg", "--batch", "--armor", "--export"], env=env, capture_output=True, check=True).stdout.decode()
    return env, armored


@unittest.skipUnless(shutil.which("gpg") and shutil.which("gpgv"), "no gpg here")
class Signed(sdkstore.KitCase):
    """A download held by its publisher's signature, under a key the entry
    carries. A throwaway key in a private gpg home stands in for the
    publisher's, and a second for a stranger's."""

    @classmethod
    def setUpClass(cls):
        cls.keys = tempfile.mkdtemp()
        cls.addClassCleanup(shutil.rmtree, cls.keys, True)
        cls.pub, cls.pub_asc = gpg_key(os.path.join(cls.keys, "pub"), "Kit Publisher <kit@example.com>")
        _, cls.other_asc = gpg_key(os.path.join(cls.keys, "stranger"), "Stranger <s@example.com>")

    def sign(self, name):
        path = os.path.join(self.s.files, name)
        subprocess.run(["gpg", "--batch", "--yes", "--detach-sign", "-o", path + ".sig", path], env=self.pub, capture_output=True, check=True)
        return "file://" + path + ".sig"

    def signed_kit(self, keyring):
        sig = self.sign("data.bin")
        # As a pack's recipe hands it over: the sha256 a signed one has none of is empty.
        self.kit(fetch=[{"url": self.data_url, "sha256": "", "to": "dl/data.bin", "signed": {"sig": sig, "keys": "kit.asc"}}], keyring=keyring)

    def test_the_right_key_in_the_entry_s_keyring_passes(self):
        self.signed_kit({"kit.asc": self.pub_asc})
        rc, out = self.s.sh("sdk_install kit", PATH=self.s.can_cut())
        self.assertEqual(rc, 0, out)
        self.assertIn("verified: dl/data.bin is signed by Kit Publisher <kit@example.com> (kit.asc)", out)
        self.assertEqual(self.s.read("kit", "ran-how").split(), ["run=yes", "then=yes", "verify=yes"])
        self.assertEqual([n for n in os.listdir(self.s.dir("kit")) if n.startswith(".bb-fetch")], [], "neither the file's nor the signature's leftover")

    def test_another_key_or_a_changed_file_is_refused_before_anything_runs(self):
        self.signed_kit({"kit.asc": self.other_asc})
        rc, out = self.s.sh("sdk_install kit; echo went-on", PATH=self.s.can_cut())
        self.assertNotEqual(rc, 0)
        self.assertIn("answered a file that does not carry its publisher's signature under kit.asc", out)
        self.assertIn("nothing is installed", out)
        self.assertFalse(os.path.exists(self.mark) or os.path.exists(self.s.dir("kit")) or "went-on" in out)
        # The right key, and a file changed since it was signed.
        self.signed_kit({"kit.asc": self.pub_asc})
        self.s.file("data.bin", "forty-three")
        rc, out = self.s.sh("sdk_install kit", PATH=self.s.can_cut())
        self.assertNotEqual(rc, 0)
        self.assertIn("does not carry its publisher's signature under kit.asc", out)
        self.assertFalse(os.path.exists(self.mark) or os.path.exists(self.s.dir("kit")))

    def test_keys_the_entry_does_not_carry_and_nobody_ships_are_refused(self):
        self.signed_kit(None)
        rc, out = self.s.sh("sdk_install kit", PATH=self.s.can_cut())
        self.assertNotEqual(rc, 0)
        self.assertIn("no release keys named 'kit.asc' beside the catalog, and its entry carries none", out)
        self.assertIn("kit: no keys named kit.asc to check dl/data.bin with", out)
        self.assertFalse(os.path.exists(self.mark))

    def test_one_function_resolves_a_key_name_for_an_entry(self):
        shipped = os.path.join(self.root, "release-keys")
        os.makedirs(shipped)
        with open(os.path.join(shipped, "kit.asc"), "w") as f:
            f.write(self.other_asc)
        row = {"name": "kit", "source": {"keyring": {"kit.asc": self.pub_asc}}}
        with mock.patch.multiple(sdkmeta, KEYS_DIR=shipped, CACHE_DIR=os.path.join(self.root, "cache")):
            carried, theirs = sdkmeta.keyring("kit.asc", row), sdkmeta.keyring("kit.asc")
            self.assertNotEqual(carried, theirs, "the entry's own key wins over the shipped file of that name")
            self.assertEqual(sdkmeta.keyring("kit.asc", {"name": "plain", "source": {}}), theirs, "an entry that carries none reads the shipped one")
            # The same keys hold a checksum file's signature (checksum.file.signed).
            data = b"ab" * 32 + b"  kit.tar.gz\n"
            with open(os.path.join(self.root, "sums"), "wb") as f:
                f.write(data)
            subprocess.run(["gpg", "--batch", "--yes", "--detach-sign", "-o", os.path.join(self.root, "sums.sig"), os.path.join(self.root, "sums")],
                           env=self.pub, capture_output=True, check=True)
            with open(os.path.join(self.root, "sums.sig"), "rb") as f:
                sig = f.read()
            self.assertIn("Kit Publisher", sdkmeta.signed_by(data, sig, "kit.asc", row))
            with self.assertRaises(SystemExit):
                sdkmeta.signed_by(data, sig, "kit.asc")
            # A name is a plain file name: a path's last part is what is read.
            self.assertEqual(sdkmeta.keyring("../elsewhere/kit.asc", row), carried)
            for bad in ("", "no such.asc", "missing.asc"):
                with self.assertRaises(SystemExit):
                    sdkmeta.keyring(bad, row)

    def test_a_row_s_own_download_signed_by_its_publisher_takes_the_entry_s_key(self):
        url, _ = self.s.tarball("tool-1.0.tar.gz", {"tool-1.0/bin/tool": "#!/bin/sh\necho tool one\n"})
        sig = self.sign("tool-1.0.tar.gz")
        self.s.row("tool", {"kind": "tarball", "url": url, "strip": 1, "checksum": {"from": "signature", "sig": sig, "keys": "kit.asc"},
                            "keyring": {"kit.asc": self.pub_asc}, "verify": ["{dir}/bin/tool"]})
        rc, out = self.s.sh("sdk_install tool")
        self.assertEqual(rc, 0, out)
        self.assertEqual(self.s.read("tool", ".bb-verified"), "gpg\t\tsigned by Kit Publisher <kit@example.com>\n")
        self.s.sh("sdk_remove tool")
        self.s.row("tool", {**self.s.rows["tool"]["source"], "keyring": {"kit.asc": self.other_asc}})
        rc, out = self.s.sh("sdk_install tool")
        self.assertTrue(rc != 0 and "does not carry its publisher's signature" in out, out)
        self.assertFalse(os.path.exists(self.s.dir("tool")))

    def test_swift_s_recipe_runs_its_verify_behind_the_cut(self):
        # The shipped row's own source: its address and its signature's
        # files on disk, its version not asked for, and the publisher's
        # keys it names carried by the row, as a row may.
        with open(os.path.join(sdkstore.REPO, "config", "toolchains.json")) as f:
            src = next(r for r in json.load(f)["toolchains"] if r["name"] == "swift")["source"]
        self.assertEqual((src["checksum"]["from"], src["checksum"]["keys"]), ("signature", "swift.asc"))
        url, _ = self.s.tarball("swift-9.9-RELEASE.tar.gz", {"swift-9.9-RELEASE/usr/bin/swift": "#!/bin/sh\necho \"Swift version 9.9 cut=${CUT:-no}\"\n"})
        sig = self.sign("swift-9.9-RELEASE.tar.gz")
        self.s.row("swift", {**{k: v for k, v in src.items() if k != "version"}, "url": url,
                             "checksum": {**src["checksum"], "sig": sig}, "keyring": {"swift.asc": self.pub_asc}})
        rc, out = self.s.sh("sdk_install swift", PATH=self.s.can_cut())
        self.assertEqual(rc, 0, out)
        self.assertIn("Swift version 9.9 cut=yes", out, "swift --version runs with no network, and runs")
        self.assertEqual(self.s.read("swift", ".bb-verified"), "gpg\t\tsigned by Kit Publisher <kit@example.com>\n")
        self.assertEqual(self.s.read("swift", ".bb-net"), "cut\n")
        head = self.receipt("swift")
        self.assertEqual((head[1], head[7]), ("", "cut"), "it now leaves a receipt, with no digest to file it under")


if __name__ == "__main__":
    unittest.main()
