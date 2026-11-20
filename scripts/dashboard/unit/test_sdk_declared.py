"""Declared downloads for every kind of source (pack format 5). What an
entry fetches besides its own source is named in the entry (source.fetch, a
pack's install.fetch), each file held to its sha256 or to its publisher's
signature under a key the entry carries, one named for a platform fetched
on that platform alone; AerieOS fetches and checks them before anything of
the entry runs, and what runs then runs with no network, unless the entry
says in a sentence that its installer downloads the rest (source.online).
One code path in sdk.sh for a script, a tarball, a command and a
repository, proved here by whole installs from files on disk."""
import os
import shutil
import subprocess
import sys
import tempfile
import unittest
from unittest import mock

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))
import sdkstore  # noqa: E402
from sdkstore import OTHER, PLATFORM, sdkmeta  # noqa: E402

SENTENCE = "Its installer downloads the compiler's components from static.example.org."
# An installer that needs the declared file to be there already, and says
# whether it ran behind the cut.
INSTALLER = """#!/bin/sh
touch "{mark}"
[ -f "$1/dl/data.bin" ] || {{ echo "the declared file is not here yet"; exit 9; }}
mkdir -p "$1/bin"
printf '#!/bin/sh\\necho kit holds %s\\n' "$(cat "$1/dl/data.bin")" > "$1/bin/kit"
chmod +x "$1/bin/kit"
echo "run=${{CUT:-no}}" >> "$1/ran-how"
"""
NO_CUT = "unshare() { return 1; }\n"


def gpg_key(home, who):
    os.makedirs(home, mode=0o700)
    env = dict(os.environ, GNUPGHOME=home)
    subprocess.run(["gpg", "--batch", "--passphrase", "", "--quick-gen-key", who, "ed25519", "sign", "never"],
                   env=env, capture_output=True, check=True)
    armored = subprocess.run(["gpg", "--batch", "--armor", "--export"], env=env, capture_output=True, check=True).stdout.decode()
    return env, armored


class Base(unittest.TestCase):
    def setUp(self):
        self.root = tempfile.mkdtemp()
        self.addCleanup(shutil.rmtree, self.root, True)
        self.s = sdkstore.Store(self.root)
        self.mark = os.path.join(self.root, "installer-ran")
        self.data_url, self.data_sha = self.s.file("data.bin", "forty-two")

    def kit(self, **source):
        """A script row whose installer needs dl/data.bin, which it declares."""
        url, sha = self.s.file("kit-install.sh", INSTALLER.format(mark=self.mark))
        src = {"kind": "script", "url": url, "run": ["sh", "{script}", "{dir}"], "checksum": {"from": "pin", "sha256": sha},
               "fetch": [{"url": self.data_url, "sha256": self.data_sha, "to": "dl/data.bin"}],
               "then": [{"run": ["sh", "-c", "echo then=${CUT:-no} >> {dir}/ran-how"]}],
               "verify": ["sh", "-c", "echo verify=${CUT:-no} >> {dir}/ran-how; {dir}/bin/kit"], **source}
        self.s.row("kit", {k: v for k, v in src.items() if v is not None})
        return sha

    def receipt(self, name):
        return self.s.read(name, ".bb-receipt").splitlines()[0].split("\t")


class Script(Base):
    def test_its_declared_download_is_fetched_and_checked_before_its_installer_runs(self):
        sha = self.kit()
        rc, out = self.s.sh("sdk_install kit", PATH=self.s.can_cut())
        self.assertEqual(rc, 0, out)
        self.assertIn("verified: sha256 matches what kit declares for dl/data.bin", out)
        self.assertIn("kit holds forty-two", out, "the installer found the file there, and the verify ran what it made")
        self.assertLess(out.index("verified: sha256 matches what kit declares"), out.index("kit declares its downloads: its steps run with no network"))
        # Everything of the entry that ran, ran behind the cut.
        self.assertEqual(self.s.read("kit", "ran-how").split(), ["run=yes", "then=yes", "verify=yes"])
        self.assertEqual(self.s.read("kit", ".bb-net"), "cut\n")
        # ...and what landed is written down, under the digest its installer was held to.
        head = self.receipt("kit")
        self.assertEqual((head[1], head[7]), (sha, "cut"))
        self.assertIn("its steps ran with no network", out)

    def test_one_that_answers_another_file_stops_before_anything_runs(self):
        self.kit(fetch=[{"url": self.data_url, "sha256": "0" * 64, "to": "dl/data.bin"}])
        rc, out = self.s.sh("sdk_install kit; echo went-on", PATH=self.s.can_cut())
        self.assertNotEqual(rc, 0)
        self.assertIn(f"answered a file whose sha256 is {self.data_sha}, and its manifest declares {'0' * 64}: nothing is installed", out)
        self.assertNotIn("went-on", out)
        self.assertFalse(os.path.exists(self.mark), "the installer never ran")
        self.assertFalse(os.path.exists(self.s.dir("kit")), "and nothing is left installed")

    def test_a_node_that_cannot_cut_says_so_and_the_receipt_does_too(self):
        self.kit()
        rc, out = self.s.sh(NO_CUT + "sdk_install kit")
        self.assertEqual(rc, 0, out)
        self.assertIn("this node cannot cut the network for a step", out)
        self.assertEqual(self.s.read("kit", "ran-how").split(), ["run=no", "then=no", "verify=no"])
        self.assertEqual((self.s.read("kit", ".bb-net"), self.receipt("kit")[7]), ("open\n", "open"))

    def test_a_row_that_declares_nothing_is_installed_as_it_always_was(self):
        self.kit(fetch=None, run=["sh", "-c", "mkdir -p {dir}/dl {dir}/bin; echo x > {dir}/dl/data.bin; sh {script} {dir}"])
        rc, out = self.s.sh("sdk_install kit", PATH=self.s.can_cut())
        self.assertEqual(rc, 0, out)
        self.assertEqual(self.s.read("kit", "ran-how").split(), ["run=no", "then=no", "verify=no"])
        self.assertFalse(os.path.exists(os.path.join(self.s.dir("kit"), ".bb-net")))
        self.assertFalse(os.path.exists(os.path.join(self.s.dir("kit"), ".bb-receipt")))

    def test_offline_alone_cuts_the_steps_of_a_row_that_downloads_nothing_more(self):
        self.kit(fetch=None, offline=True, run=["sh", "-c", "mkdir -p {dir}/dl; echo x > {dir}/dl/data.bin; sh {script} {dir}"])
        rc, out = self.s.sh("sdk_install kit", PATH=self.s.can_cut())
        self.assertEqual(rc, 0, out)
        self.assertEqual(self.s.read("kit", "ran-how").split(), ["run=yes", "then=yes", "verify=yes"])


class Platform(Base):
    def test_one_for_another_machine_is_left_out(self):
        gone = "file://" + os.path.join(self.s.files, "not-built-for-this-machine.bin")
        self.kit(fetch=[{"url": self.data_url, "sha256": self.data_sha, "to": "dl/data.bin", "platform": PLATFORM.split("/")[0] + "/*"},
                        {"url": gone, "sha256": "1" * 64, "to": "dl/theirs.bin", "platform": OTHER}])
        rc, out = self.s.sh("sdk_install kit", PATH=self.s.can_cut())
        self.assertEqual(rc, 0, out)
        self.assertIn(f"leaving out dl/theirs.bin: it is for {OTHER}", out)
        self.assertEqual(sorted(os.listdir(os.path.join(self.s.dir("kit"), "dl"))), ["data.bin"])

    def test_the_lookup_is_the_one_a_row_s_address_takes(self):
        system, arch = PLATFORM.split("/")
        self.assertTrue(sdkmeta.on_platform(PLATFORM) and sdkmeta.on_platform(f"{system}/*") and sdkmeta.on_platform(""))
        self.assertFalse(sdkmeta.on_platform(OTHER) or sdkmeta.on_platform(f"{system}/{'arm64' if arch == 'amd64' else 'amd64'}"))
        row = {"source": {"fetch": [{"url": "https://example.com/a", "to": "a", "platform": OTHER}, {"url": "https://example.com/b", "to": "b"},
                                    {"url": "https://example.com/c", "to": "c", "platform": PLATFORM}, "junk"]}}
        self.assertEqual([f["to"] for f in sdkmeta.declared(row)], ["b", "c"])
        # What an install would download counts this machine's alone.
        self.assertEqual(sdkmeta.download_urls({"name": "x", "source": {"kind": "git", "download": {"resolver": "approximate"}, **row["source"]}}),
                         ["https://example.com/b", "https://example.com/c"])


class Online(Base):
    def test_an_installer_that_downloads_the_rest_keeps_the_network_and_says_why(self):
        sha = self.kit(online=SENTENCE)
        rc, out = self.s.sh("sdk_install kit", PATH=self.s.can_cut())
        self.assertEqual(rc, 0, out)
        # What it declares is fetched and checked all the same, before it runs.
        self.assertIn("verified: sha256 matches what kit declares for dl/data.bin", out)
        self.assertIn("kit keeps the network for its steps, as its entry says: " + SENTENCE, out)
        self.assertNotIn("its steps run with no network", out)
        self.assertEqual(self.s.read("kit", "ran-how").split(), ["run=no", "then=no", "verify=no"], "nothing was cut, though this node could")
        self.assertEqual(self.s.read("kit", ".bb-net"), f"online\n{SENTENCE}\n")
        head = self.receipt("kit")
        self.assertEqual((head[1], head[7], head[8]), (sha, "online", SENTENCE))
        self.assertIn("its steps kept the network, as its entry says: " + SENTENCE, out, "the receipt's own words say it")


class Kinds(Base):
    """The same call in each of the other shapes."""

    def test_a_tarball_s_follow_up_steps_and_verify_run_behind_the_cut(self):
        url, sha = self.s.tarball("tool-1.0.tar.gz", {"tool-1.0/bin/tool": "#!/bin/sh\necho \"tool $(cat \"$(dirname \"$0\")/../dl/data.bin\")\"\n"})
        self.s.row("tool", {"kind": "tarball", "url": url, "strip": 1, "checksum": {"from": "pin", "version": "1.0", "sha256": sha},
                            "fetch": [{"url": self.data_url, "sha256": self.data_sha, "to": "dl/data.bin"}],
                            "then": [{"run": ["sh", "-c", "echo then=${CUT:-no} >> {dir}/ran-how"]}],
                            "verify": ["sh", "-c", "echo verify=${CUT:-no} >> {dir}/ran-how; {dir}/bin/tool"]})
        rc, out = self.s.sh("sdk_install tool", PATH=self.s.can_cut())
        self.assertEqual(rc, 0, out)
        self.assertIn("tool forty-two", out)
        self.assertEqual(self.s.read("tool", "ran-how").split(), ["then=yes", "verify=yes"])
        self.assertEqual(self.receipt("tool")[1], sha)

    def test_a_command_runs_behind_it(self):
        self.s.row("cmd", {"kind": "command", "run": ["sh", "-c", "cp {dir}/dl/data.bin {dir}/copied; echo run=${CUT:-no} > {dir}/ran-how"],
                           "fetch": [{"url": self.data_url, "sha256": self.data_sha, "to": "dl/data.bin"}]})
        rc, out = self.s.sh("sdk_install cmd", PATH=self.s.can_cut())
        self.assertEqual(rc, 0, out)
        self.assertEqual((self.s.read("cmd", "copied"), self.s.read("cmd", "ran-how")), ("forty-two", "run=yes\n"))
        self.assertEqual(self.receipt("cmd")[7], "cut")
        # One that fails behind the cut says where to look.
        self.s.sh("sdk_remove cmd")
        self.s.row("cmd", {"kind": "command", "run": ["false"], "offline": True})
        rc, out = self.s.sh("sdk_install cmd", PATH=self.s.can_cut())
        self.assertTrue(rc != 0 and "it ran with no network: what it fetches is declared in its entry" in out, out)

    def repo(self):
        """A repository on disk with one commit: (its address, the commit)."""
        d = os.path.join(self.root, "repo")
        os.makedirs(d)
        with open(os.path.join(d, "install.sh"), "w") as f:
            f.write("#!/bin/sh\nmkdir -p \"$1/bin\"\ncp \"$1/dl/data.bin\" \"$1/bin/payload\"\necho then=${CUT:-no} >> \"$1/ran-how\"\n")
        git = ["git", "-C", d, "-c", "user.name=t", "-c", "user.email=t@example.com", "-c", "init.defaultBranch=main"]
        for args in (["init", "-q"], ["add", "-A"], ["commit", "-q", "-m", "one"]):
            subprocess.run([*git, *args], check=True, capture_output=True)
        return d, subprocess.run([*git, "rev-parse", "HEAD"], check=True, capture_output=True, text=True).stdout.strip()

    def test_a_pinned_repository_s_warm_up_steps_and_verify_run_behind_it(self):
        url, commit = self.repo()
        src = {"kind": "git", "url": url, "commit": commit, "fresh_only": True, "offline": True,
               "fetch": [{"url": self.data_url, "sha256": self.data_sha, "to": "dl/data.bin"}],
               "warm": ["sh", "-c", "echo warm=${CUT:-no} >> {dir}/ran-how"], "warm_note": "warming",
               "then": [{"run": ["sh", "{dir}/install.sh", "{dir}"]}],
               "verify": ["sh", "-c", "echo verify=${CUT:-no} >> {dir}/ran-how; cat {dir}/bin/payload"]}
        self.s.row("pack", src)
        rc, out = self.s.sh("sdk_install pack", PATH=self.s.can_cut())
        self.assertEqual(rc, 0, out)
        self.assertEqual(self.s.read("pack", "ran-how").split(), ["warm=yes", "then=yes", "verify=yes"])
        head = self.receipt("pack")
        self.assertEqual((head[1], head[7]), (commit, "cut"))
        # The same repository saying its installer downloads the rest.
        self.s.sh("sdk_remove pack")
        self.s.row("pack", {**{k: v for k, v in src.items() if k != "offline"}, "online": SENTENCE})
        rc, out = self.s.sh("sdk_install pack", PATH=self.s.can_cut())
        self.assertEqual(rc, 0, out)
        self.assertEqual(self.s.read("pack", "ran-how").split(), ["warm=no", "then=no", "verify=no"])
        self.assertEqual(self.receipt("pack")[7:], ["online", SENTENCE])
        self.assertIn("its steps kept the network, as its entry says: " + SENTENCE, out)


@unittest.skipUnless(shutil.which("gpg") and shutil.which("gpgv"), "no gpg here")
class Signed(Base):
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
        self.kit(fetch=[{"url": self.data_url, "to": "dl/data.bin", "signed": {"sig": sig, "keys": "kit.asc"}}], keyring=keyring)

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


if __name__ == "__main__":
    unittest.main()
