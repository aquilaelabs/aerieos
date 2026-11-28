"""A release signs the list of every file its bundle ships:
tools/sign-agent.py writes a second part to agent.sig beside the agent's,
over the digest of the list scripts/lib/bundleparts.py makes of the tree
(root's tools among its files), under a line of its own. --check holds that part too, so a shipped
file changed after the signing fails a release's tag; a builder's key signs
it as a release's does; and --digests says what a tree would be signed as.

The signer reads the tree it sits in, so each test runs a copy of it in a
tree of its own: the bundle's files, the agent's sources and the tool."""
import io
import json
import os
import pathlib
import shutil
import subprocess
import sys
import tarfile
import tempfile
import unittest
from contextlib import redirect_stdout
from unittest import mock

HERE = os.path.dirname(os.path.abspath(__file__))
REPO = os.path.normpath(os.path.join(HERE, "..", "..", ".."))
sys.path.insert(0, os.path.join(REPO, "scripts", "agent"))
sys.path.insert(0, os.path.join(HERE, ".."))
sys.path.insert(0, os.path.join(REPO, "scripts", "lib"))
import bundleparts  # noqa: E402
import workspace  # noqa: E402
from aerieos_agent import release  # noqa: E402
from cryptography.hazmat.primitives.asymmetric.ed25519 import Ed25519PrivateKey  # noqa: E402


def pair():
    k = Ed25519PrivateKey.generate()
    return k, k.public_key().public_bytes_raw().hex()


class Signed(unittest.TestCase):
    def setUp(self):
        self.t = tempfile.mkdtemp()
        self.addCleanup(shutil.rmtree, self.t, True)
        for name, path in bundleparts.files(REPO):
            os.makedirs(os.path.dirname(os.path.join(self.t, name)), exist_ok=True)
            shutil.copy(path, os.path.join(self.t, name))
        shutil.copytree(os.path.join(REPO, "scripts", "agent"), os.path.join(self.t, "scripts", "agent"),
                        ignore=shutil.ignore_patterns("__pycache__", "agent.sig"), dirs_exist_ok=True)
        os.makedirs(os.path.join(self.t, "tools"))
        shutil.copy(os.path.join(REPO, "tools", "sign-agent.py"), os.path.join(self.t, "tools"))
        self.sig = os.path.join(self.t, "scripts", "agent", "agent.sig")
        self.k, self.pub = pair()
        self.named = os.path.join(self.t, "release.pub")
        with open(self.named, "w") as f:
            f.write(f"aerieos-release-ed25519 {self.pub}\n")

    def signer(self, *args, key=None):
        env = {**os.environ, "AERIEOS_RELEASE_PUB": self.named}
        env.pop("AERIEOS_RELEASE_KEY", None)
        if key is not None:
            env["AERIEOS_RELEASE_KEY"] = key.private_bytes_raw().hex()
        return subprocess.run([sys.executable, os.path.join(self.t, "tools", "sign-agent.py"), *args],
                              capture_output=True, text=True, env=env, timeout=120, check=False)

    def read_sig(self, path=None):
        with open(path or self.sig) as f:
            return json.load(f)

    def test_the_list_of_the_bundles_files_is_signed_under_a_line_of_its_own(self):
        r = self.signer(key=self.k)
        self.assertEqual(r.returncode, 0, r.stdout + r.stderr)
        self.assertIn("and the bundle's files", r.stdout)
        part = self.read_sig()["bundle"]
        self.assertEqual(part["digest"], bundleparts.listing(self.t)[1], "the list of this tree's files")
        self.assertEqual(release.verify(self.pub, part["digest"], part["sig"], release.BUNDLE_MESSAGE), "")
        for other in (release.MESSAGE, b"aerieos root tools v1\n"):
            self.assertIn("not the pinned", release.verify(self.pub, part["digest"], part["sig"], other), "it passes as no other")
        self.assertNotIn("tools", self.read_sig(), "no second signature over root's tools alone (R267 step 28)")
        # The controller built from this tree lists the same files and passes the signature on.
        with mock.patch.object(workspace, "REPO", pathlib.Path(self.t)), mock.patch.object(workspace, "_bundle", {}), \
                mock.patch.object(workspace, "_bundle_missing", set()), mock.patch.object(workspace, "packs_json", None), \
                mock.patch.object(workspace, "packs_files", None), mock.patch.object(workspace, "toolchains_json", None), \
                redirect_stdout(io.StringIO()) as said:
            b = workspace.bundle()
        self.assertEqual((b["files"], b["files_signed"]), (part["digest"], True), said.getvalue())
        with tarfile.open(fileobj=io.BytesIO(b["body"])) as tar:
            self.assertEqual(json.load(tar.extractfile(workspace.BUNDLE_SIG)), part)

    def test_check_holds_the_bundles_files_and_fails_once_one_changed(self):
        self.assertEqual(self.signer(key=self.k).returncode, 0)
        r = self.signer("--check")
        self.assertEqual(r.returncode, 0, r.stdout)
        self.assertIn("the bundle's files: signed by", r.stdout)
        # Bytecode a run left behind is no part of the list.
        os.makedirs(os.path.join(self.t, "scripts", "lib", "__pycache__"), exist_ok=True)
        with open(os.path.join(self.t, "scripts", "lib", "__pycache__", "sdkmeta.cpython-312.pyc"), "wb") as f:
            f.write(b"\x00")
        self.assertEqual(self.signer("--check").returncode, 0)
        # A shipped file that is neither the agent's nor root's, changed after the signing.
        with open(os.path.join(self.t, "scripts", "lib", "sdk.sh"), "a") as f:
            f.write("# changed after the signing\n")
        r = self.signer("--check")
        self.assertEqual(r.returncode, 1, r.stdout)
        self.assertIn("signed by", r.stdout.splitlines()[0], "the agent's part still stands")
        self.assertIn("the bundle's files: it is for other files than this tree's bundle ships", r.stdout)

    def test_a_signature_without_the_part_is_not_whole(self):
        self.assertEqual(self.signer(key=self.k).returncode, 0)
        got = self.read_sig()
        del got["bundle"]
        with open(self.sig, "w") as f:
            json.dump(got, f)
        r = self.signer("--check")
        self.assertEqual(r.returncode, 1, r.stdout)
        self.assertIn("the bundle's files: it carries no signature for the files the bundle ships", r.stdout)
        # ...and one made for the agent does not stand in for it.
        got["bundle"] = {"digest": got["digest"], "sig": got["sig"]}
        with open(self.sig, "w") as f:
            json.dump(got, f)
        self.assertEqual(self.signer("--check").returncode, 1)

    def test_a_builders_key_signs_it_too(self):
        key = os.path.join(self.t, "keys", "key")
        r = self.signer("--builder-keygen", key)
        self.assertEqual(r.returncode, 0, r.stderr)
        pub = next(ln.strip() for ln in r.stdout.splitlines() if len(ln.strip()) == 64)
        out = os.path.join(self.t, "builder.sig")
        r = self.signer("--builder", key, "--out", out)
        self.assertEqual(r.returncode, 0, r.stderr)
        self.assertIn("and the bundle's files", r.stdout)
        part = self.read_sig(out)["bundle"]
        self.assertEqual(part["digest"], bundleparts.listing(self.t)[1])
        self.assertEqual(release.verify(pub, part["digest"], part["sig"], release.BUNDLE_MESSAGE), "")

    def test_digests_says_the_two_and_writes_nothing(self):
        r = self.signer("--digests")
        self.assertEqual(r.returncode, 0, r.stderr)
        got = dict(ln.split() for ln in r.stdout.splitlines())
        self.assertEqual(sorted(got), ["agent", "bundle"])
        self.assertTrue(all(v.startswith("sha256:") and len(v) == 71 for v in got.values()), got)
        self.assertEqual(got["bundle"], bundleparts.listing(self.t)[1])
        self.assertFalse(os.path.exists(self.sig), "nothing is written")
        self.assertEqual(self.signer(key=self.k).returncode, 0)
        signed = self.read_sig()
        self.assertEqual((signed["digest"], signed["bundle"]["digest"]),
                         (got["agent"], got["bundle"]), "they are what a signing signs")


if __name__ == "__main__":
    unittest.main()
