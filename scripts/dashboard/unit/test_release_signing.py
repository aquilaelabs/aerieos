"""Release signing (R199): a release's SHA256SUMS signed by a key the install
already holds is what an update is taken on, so whoever changes the
repository or a release can build and attest one but not hand it to an
install. Here with a real key made by ssh-keygen: a signed list verifies and
is read, a changed list or another key's signature is refused, the OS
updater and the stick maker each hold to it, and the stick maker's keys are
config/release-signers' own."""
import importlib.util
import os
import shutil
import subprocess
import tempfile
import unittest

import agentpkg  # noqa: E402

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.normpath(os.path.join(HERE, "..", "..", ".."))
osimage = agentpkg.load("aerieos_agent_signing").module("osimage")
spec = importlib.util.spec_from_file_location("bbstick_signing", os.path.join(ROOT, "tools", "aerieos-stick.py"))
stick = importlib.util.module_from_spec(spec)
spec.loader.exec_module(stick)
NS = "aerieos-release"


@unittest.skipUnless(shutil.which("ssh-keygen"), "no ssh-keygen here")
class Signing(unittest.TestCase):
    def setUp(self):
        self.d = tempfile.mkdtemp()
        self.addCleanup(shutil.rmtree, self.d, True)
        self.key = os.path.join(self.d, "key")
        subprocess.run(["ssh-keygen", "-q", "-t", "ed25519", "-N", "", "-C", NS, "-f", self.key], check=True, stdin=subprocess.DEVNULL, timeout=30)
        kt, kb = open(self.key + ".pub").read().split()[:2]
        self.line = f'{NS} namespaces="{NS}" {kt} {kb}'
        self.image = os.path.join(self.d, "aerieos-os-0.9.0.stick.raw.xz")
        open(self.image, "wb").write(b"the image")
        import hashlib
        self.digest = hashlib.sha256(b"the image").hexdigest()

    def sign(self, lines, key=None):
        sums = os.path.join(self.d, "SHA256SUMS")
        open(sums, "w").write("\n".join(lines) + "\n")
        if os.path.exists(sums + ".sig"):
            os.remove(sums + ".sig")    # ssh-keygen asks before replacing one
        subprocess.run(["ssh-keygen", "-Y", "sign", "-q", "-f", key or self.key, "-n", NS, sums], check=True, stdin=subprocess.DEVNULL, timeout=30)
        return sums, sums + ".sig"

    def test_a_signed_list_verifies_and_is_read(self):
        sums, sig = self.sign([f"{self.digest}  aerieos-os-0.9.0.stick.raw.xz", "a" * 64 + "  other.iso"])
        self.assertEqual(osimage.sums_verify(sums, sig, [self.line]),
                         {"aerieos-os-0.9.0.stick.raw.xz": self.digest, "other.iso": "a" * 64})

    def test_a_changed_list_or_another_keys_signature_is_refused(self):
        sums, sig = self.sign([f"{self.digest}  x"])
        with open(sums, "a") as f:
            f.write("b" * 64 + "  evil\n")
        self.assertIsNone(osimage.sums_verify(sums, sig, [self.line]))
        other = os.path.join(self.d, "other")
        subprocess.run(["ssh-keygen", "-q", "-t", "ed25519", "-N", "", "-C", "other", "-f", other], check=True, stdin=subprocess.DEVNULL, timeout=30)
        sums, sig = self.sign([f"{self.digest}  x"], key=other)
        self.assertIsNone(osimage.sums_verify(sums, sig, [self.line]))

    def test_the_stick_maker_holds_an_image_to_its_releases_signature(self):
        sums, sig = self.sign([f"{self.digest}  aerieos-os-0.9.0.stick.raw.xz"])

        def fetch(url, dest, say_progress=True):
            shutil.copyfile(sig if url.endswith(".sig") else sums, dest)
        said = []

        def die(s):
            raise SystemExit(s)
        with unittest.mock.patch.multiple(stick, RELEASE_SIGNERS=self.line + "\n", fetch=fetch, say=said.append, die=die):
            stick.signed("v0.9.0", self.image)
            self.assertTrue(any("signed by AerieOS's release key" in s for s in said))
            open(self.image, "wb").write(b"another image")
            with self.assertRaises(SystemExit):
                stick.signed("v0.9.0", self.image)
        self.assertEqual(stick.tag_of(self.image), "v0.9.0")


class Pinned(unittest.TestCase):
    def test_the_stick_makers_keys_are_config_release_signers(self):
        with open(os.path.join(ROOT, "config", "release-signers"), encoding="utf-8") as f:
            want = [ln.strip() for ln in f if ln.strip() and not ln.lstrip().startswith("#")]
        self.assertEqual([ln.strip() for ln in stick.signers()], want)


import unittest.mock  # noqa: E402

if __name__ == "__main__":
    unittest.main()
