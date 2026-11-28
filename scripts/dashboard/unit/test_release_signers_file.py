"""config/release-signers: who may sign a release, in every install.
The audit of 20 Nov found the file held no key, no install carried it (the
Dockerfile copied the two key files beside it and not this one, and the
bare-metal layout and the OS image are made from those lines), and the
stick maker's copy was typed by hand, so every check against it said
"skipped". Here: its dev lines are config/aerieos-release.pub's keys as
OpenSSH writes them, written by tools/release-signers.py and held by `aerie
lint` with the stick maker's copy; a real signature by such a key verifies
against its line and in its own namespace alone; and the image and a
bare-metal release carry the file where the verifiers read it."""
import importlib.util
import os
import shutil
import subprocess
import sys
import tempfile
import unittest

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.normpath(os.path.join(HERE, "..", "..", ".."))
LIB = os.path.join(ROOT, "scripts", "lib")
TOOL = os.path.join(ROOT, "tools", "release-signers.py")
CHECKS = os.path.join(LIB, "lint-checks.py")
sys.path.insert(0, LIB)
import releasepub  # noqa: E402

spec = importlib.util.spec_from_file_location("release_signers_under_test", TOOL)
gen = importlib.util.module_from_spec(spec)
spec.loader.exec_module(gen)

K1, K2 = "11" * 32, "22" * 32
HEAD = ("# Who may sign a release.\n#\n# Dev builds publish by themselves: written here,\n# never typed.\n#\n"
        "# Stable releases are signed by their key's holder.\n")


def read(*rel):
    with open(os.path.join(ROOT, *rel), encoding="utf-8") as f:
        return f.read()


def dev(hexkey):
    return f'aerieos-dev namespaces="aerieos-dev" {gen.ssh_key(hexkey)}'


class Tree(unittest.TestCase):
    """A tree with the three files and the tools that read them, in a folder."""
    def setUp(self):
        self.d = tempfile.mkdtemp()
        self.addCleanup(shutil.rmtree, self.d, True)
        for sub in ("config", "tools", os.path.join("scripts", "lib")):
            os.makedirs(os.path.join(self.d, sub))
        shutil.copy(TOOL, os.path.join(self.d, "tools"))
        shutil.copy(os.path.join(LIB, "releasepub.py"), os.path.join(self.d, "scripts", "lib"))
        self.put("config/aerieos-release.pub", f"# the key and its spare\n{releasepub.NAME} {K1}\n{releasepub.NAME} {K2}\n")
        self.put("config/release-signers", HEAD)
        self.put("tools/aerieos-stick.py", 'X = 1\nRELEASE_SIGNERS = """\n"""\nY = 2\n')

    def put(self, rel, text):
        with open(os.path.join(self.d, rel), "w", encoding="utf-8") as f:
            f.write(text)

    def get(self, rel):
        with open(os.path.join(self.d, rel), encoding="utf-8") as f:
            return f.read()

    def tool(self, *argv):
        r = subprocess.run([sys.executable, os.path.join(self.d, "tools", "release-signers.py"), *argv],
                           capture_output=True, text=True, timeout=60, check=False)
        return r.returncode, r.stdout + r.stderr

    def lint(self):
        r = subprocess.run([sys.executable, CHECKS, "releasesigners"], cwd=self.d, capture_output=True, text=True,
                           timeout=60, check=False)
        return r.returncode, r.stdout + r.stderr


class Written(Tree):
    def test_the_dev_lines_are_written_from_the_release_key_file_and_the_stick_maker_follows(self):
        rc, said = self.lint()
        self.assertEqual(rc, 1, said)
        self.assertIn("[FAIL] config/release-signers: its aerieos-dev lines are not config/aerieos-release.pub's keys", said)
        self.assertEqual(self.tool("--write")[0], 0)
        text = self.get("config/release-signers")
        # Under the comment that heads them, the key the builds sign with
        # first, and every other line as it was.
        self.assertEqual(text, HEAD.replace("# never typed.\n", f"# never typed.\n{dev(K1)}\n{dev(K2)}\n"))
        self.assertEqual(self.get("tools/aerieos-stick.py"),
                         f'X = 1\nRELEASE_SIGNERS = """\n{dev(K1)}\n{dev(K2)}\n"""\nY = 2\n')
        rc, said = self.lint()
        self.assertEqual((rc, said.count("[ok]")), (0, 1), said)
        # Written again, nothing moves.
        rc, said = self.tool("--write")
        self.assertEqual(rc, 0)
        self.assertIn("nothing to write", said)

    def test_a_key_that_moved_is_a_red_lint_until_it_is_written_again(self):
        self.tool("--write")
        self.put("config/aerieos-release.pub", f"{releasepub.NAME} {K2}\n")
        rc, said = self.lint()
        self.assertEqual(rc, 1)
        self.assertIn("the release key or its spare moved, or a line was typed", said)
        self.assertEqual(self.tool("--write")[0], 0)
        self.assertEqual(gen.key_lines(self.get("config/release-signers")), [dev(K2)])
        self.assertEqual(self.lint()[0], 0)

    def test_the_stable_signers_line_is_kept_and_reaches_the_stick_maker(self):
        stable = f'aerieos-release namespaces="aerieos-release" {gen.ssh_key("33" * 32)} aerieos-release'
        self.put("config/release-signers", HEAD + stable + "\n")
        self.assertEqual(self.tool("--write")[0], 0)
        self.assertEqual(gen.key_lines(self.get("config/release-signers")), [dev(K1), dev(K2), stable])
        self.assertIn(stable + '\n"""', self.get("tools/aerieos-stick.py"))
        self.assertEqual(self.lint()[0], 0, self.lint()[1])


class Held(Tree):
    def setUp(self):
        super().setUp()
        self.tool("--write")
        self.good = self.get("config/release-signers")

    def fails(self, why):
        rc, said = self.lint()
        self.assertEqual(rc, 1, said)
        self.assertIn(why, said)

    def test_a_stick_maker_with_other_lines_fails(self):
        self.put("tools/aerieos-stick.py", f'RELEASE_SIGNERS = """\n{dev(K1)}\n"""\n')
        self.fails("tools/aerieos-stick.py: its RELEASE_SIGNERS is not config/release-signers' lines")
        self.put("tools/aerieos-stick.py", "X = 1\n")
        self.fails("has no RELEASE_SIGNERS")

    def test_a_typed_dev_line_fails(self):
        self.put("config/release-signers", self.good + dev("44" * 32) + "\n")
        self.fails("its aerieos-dev lines are not config/aerieos-release.pub's keys")

    def test_a_line_that_is_no_signer_fails(self):
        for line in (gen.ssh_key(K1),                                                   # a bare key: any principal, any namespace
                     f"aerieos-dev {gen.ssh_key(K1)}",                                  # no namespace: it could sign a stable release
                     f'somebody namespaces="aerieos-release" {gen.ssh_key("33" * 32)}',
                     'aerieos-release namespaces="aerieos-release" ssh-rsa AAAA'):
            self.put("config/release-signers", self.good + line + "\n")
            self.fails("is not a signer")

    def test_a_signer_given_the_other_channels_namespace_fails(self):
        self.put("config/release-signers", self.good + f'aerieos-dev namespaces="aerieos-release" {gen.ssh_key(K1)}\n')
        self.fails("aerieos-dev is given the namespace aerieos-release")

    def test_the_release_builds_key_named_a_stable_signer_fails(self):
        # The custody the two namespaces are for: the key CI holds signs dev
        # builds, never a stable release.
        self.put("config/release-signers", self.good + f'aerieos-release namespaces="aerieos-release" {gen.ssh_key(K2)}\n')
        self.fails("a stable release is signed by a key CI never has")

    def test_a_release_key_file_that_names_no_key_fails(self):
        self.put("config/aerieos-release.pub", "# nothing\n")
        self.fails("names no key to write the dev lines from")

    def test_a_signers_file_that_is_gone_fails(self):
        os.unlink(os.path.join(self.d, "config", "release-signers"))
        self.fails("config/release-signers cannot be read")


class Committed(unittest.TestCase):
    def test_the_repositorys_files_pass_and_lint_runs_the_check(self):
        p = subprocess.run([sys.executable, CHECKS, "releasesigners"], cwd=ROOT, capture_output=True, text=True, check=False)
        self.assertEqual((p.returncode, p.stdout.count("[ok]")), (0, 1), p.stdout + p.stderr)
        aerie = read("scripts", "aerie")
        self.assertIn('python3 "$BB_LIB/lint-checks.py" releasesigners || rc=1', aerie)

    def test_the_file_names_the_release_key_and_its_spare_for_dev_builds(self):
        keys, why = releasepub.read(os.path.join(ROOT, "config", "aerieos-release.pub"))
        self.assertEqual(why, "")
        lines = gen.key_lines(read("config", "release-signers"))
        self.assertEqual([ln for ln in lines if ln.startswith("aerieos-dev ")], [dev(k) for k in keys])
        self.assertTrue(lines, "a file with no key line is every check skipped")

    def test_the_image_carries_it_where_the_verifiers_read_it(self):
        text = read("Dockerfile")
        self.assertIn("COPY config/release-signers /opt/aerieos/config/release-signers", text)
        # ...which is the path the OS updater reads, and the folder the
        # installer and the Library's downloads look in beside themselves.
        agent = read("scripts", "agent", "aerieos_agent", "osimage.py")
        self.assertIn('SIGNERS = "/opt/aerieos/config/release-signers"', agent)

    def test_a_bare_metal_release_is_laid_out_with_it(self):
        d = tempfile.mkdtemp()
        self.addCleanup(shutil.rmtree, d, True)
        rel = os.path.join(d, "opt", "aerieos-releases", "1.2.3")
        os.makedirs(os.path.dirname(rel))
        installer = os.path.join(ROOT, "nodes", "install-controller.sh")
        r = subprocess.run(["bash", "-c", f'set -euo pipefail\nBB_CONTROLLER_LIB=1 . "{installer}"\nlay_out "{ROOT}" "{rel}" 1.2.3 abc'],
                           capture_output=True, text=True, timeout=120, check=False,
                           env=dict(os.environ, BB_INSTALL_ROOT=d, NO_FETCH="1"))
        self.assertEqual(r.returncode, 0, r.stderr)
        with open(os.path.join(rel, "config", "release-signers"), encoding="utf-8") as f:
            self.assertEqual(f.read(), read("config", "release-signers"))


@unittest.skipUnless(shutil.which("ssh-keygen"), "no ssh-keygen here")
class TheLineIsTheKey(unittest.TestCase):
    """A signature made with the key behind 64 hex characters verifies
    against the line written from them, in the namespace the line names and
    no other."""
    def test_a_signature_by_the_key_verifies_against_its_line_in_its_namespace_alone(self):
        try:
            from cryptography.hazmat.primitives import serialization as ser
            from cryptography.hazmat.primitives.asymmetric.ed25519 import Ed25519PrivateKey
        except ImportError:
            self.skipTest("no cryptography here to make a key from its seed")
        d = tempfile.mkdtemp()
        self.addCleanup(shutil.rmtree, d, True)
        k = Ed25519PrivateKey.generate()
        key = os.path.join(d, "key")
        with open(os.open(key, os.O_WRONLY | os.O_CREAT | os.O_EXCL, 0o600), "wb") as f:
            f.write(k.private_bytes(ser.Encoding.PEM, ser.PrivateFormat.OpenSSH, ser.NoEncryption()))
        pub = k.public_key().public_bytes(ser.Encoding.Raw, ser.PublicFormat.Raw).hex()
        signers = os.path.join(d, "signers")
        with open(signers, "w", encoding="utf-8") as f:
            f.write(f"# a comment\n{dev(pub)}\n")
        sums = os.path.join(d, "SHA256SUMS")
        with open(sums, "w", encoding="utf-8") as f:
            f.write("a" * 64 + "  x\n")

        def verifies(sign_ns, ask_ns):
            if os.path.exists(sums + ".sig"):
                os.unlink(sums + ".sig")
            subprocess.run(["ssh-keygen", "-Y", "sign", "-q", "-f", key, "-n", sign_ns, sums], check=True,
                           stdin=subprocess.DEVNULL, capture_output=True, timeout=30)
            with open(sums, "rb") as fh:
                return subprocess.run(["ssh-keygen", "-Y", "verify", "-f", signers, "-I", ask_ns, "-n", ask_ns, "-s", sums + ".sig"],
                                      stdin=fh, capture_output=True, timeout=30, check=False).returncode == 0
        self.assertTrue(verifies("aerieos-dev", "aerieos-dev"))
        # The same key signing as a stable release's is no stable signer.
        self.assertFalse(verifies("aerieos-release", "aerieos-release"))
        self.assertFalse(verifies("aerieos-dev", "aerieos-release"))


if __name__ == "__main__":
    unittest.main()
