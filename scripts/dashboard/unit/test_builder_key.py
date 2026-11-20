"""Somebody who builds a controller on their own machine signs its node agent
with a builder's key of their own (tools/sign-agent.py --builder-keygen and
--builder): the private half stays in a file of that account's alone, the
signature is over this tree's agent, root's tools and the bundle's files
(the last held in test_sign_bundle_files.py), a node takes the build once the
key is added at its console and not before, and a release key is refused as
a builder's."""
import json
import os
import shutil
import stat
import subprocess
import sys
import tempfile
import unittest

REPO = os.path.normpath(os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "..", ".."))
SIGNER = os.path.join(REPO, "tools", "sign-agent.py")
sys.path.insert(0, os.path.join(REPO, "scripts", "agent"))


class BuilderKey(unittest.TestCase):
    def setUp(self):
        self.d = tempfile.mkdtemp()
        self.addCleanup(shutil.rmtree, self.d, True)
        self.key = os.path.join(self.d, "keys", "key")

    def signer(self, *args, env=None):
        return subprocess.run([sys.executable, SIGNER, *args], capture_output=True, text=True, env={**os.environ, **(env or {})})

    def make_key(self):
        r = self.signer("--builder-keygen", self.key)
        self.assertEqual(r.returncode, 0, r.stderr)
        return next(ln.strip() for ln in r.stdout.splitlines() if len(ln.strip()) == 64)

    def test_the_key_is_made_once_and_its_private_half_is_never_said(self):
        pub = self.make_key()
        self.assertEqual(stat.S_IMODE(os.stat(self.key).st_mode), 0o600, "the private half is this account's alone")
        with open(self.key) as f:
            seed = f.read().strip()
        r = self.signer("--builder-keygen", self.key)
        self.assertEqual(r.returncode, 0, r.stderr)
        self.assertIn("kept", r.stdout)
        self.assertIn(pub, r.stdout, "asked again, the same key is said, not another made")
        self.assertNotIn(seed, r.stdout)
        with open(self.key) as f:
            self.assertEqual(f.read().strip(), seed)
        self.assertIn(f"release-key add {pub}", r.stdout, "the command a person runs at a node's console is said")

    def test_a_build_is_signed_over_this_tree_and_a_node_takes_it_once_the_key_is_added(self):
        pub = self.make_key()
        out = os.path.join(self.d, "agent.sig")
        r = self.signer("--builder", self.key, "--out", out)
        self.assertEqual(r.returncode, 0, r.stderr)
        self.assertIn(f"release-key add {pub}", r.stdout)
        with open(out) as f:
            sig = json.load(f)
        from aerieos_agent import release
        self.assertEqual(sig["key"], pub)
        self.assertEqual(release.verify(pub, sig["digest"], sig["sig"]), "")
        self.assertEqual(release.verify(pub, sig["tools"]["digest"], sig["tools"]["sig"], release.TOOLS_MESSAGE), "")
        pinned = {"release_key": "ab" * 32}
        self.assertFalse(release.may_install(pinned, sig["digest"], sig["sig"])[0], "a node that has not added the key refuses it")
        ok, said = release.may_install({**pinned, "release_also": [pub]}, sig["digest"], sig["sig"])
        self.assertTrue(ok)
        self.assertIn("added at this node's console", said)
        self.assertTrue(release.may_keep_tools({**pinned, "release_also": [pub]}, sig["tools"]["digest"], sig["tools"]["sig"])[0])

    def test_a_file_that_holds_no_key_signs_nothing(self):
        os.makedirs(os.path.dirname(self.key))
        with open(self.key, "w") as f:
            f.write("not a key\n")
        out = os.path.join(self.d, "agent.sig")
        r = self.signer("--builder", self.key, "--out", out)
        self.assertEqual(r.returncode, 2)
        self.assertIn("does not hold a builder's key", r.stderr)
        self.assertFalse(os.path.exists(out))
        r = self.signer("--builder", os.path.join(self.d, "nowhere"), "--out", out)
        self.assertEqual(r.returncode, 2)
        self.assertFalse(os.path.exists(out))

    def test_a_release_key_is_not_a_builders(self):
        # The release's own key signs in the release's build, and nowhere else.
        from cryptography.hazmat.primitives.asymmetric.ed25519 import Ed25519PrivateKey
        k = Ed25519PrivateKey.generate()
        os.makedirs(os.path.dirname(self.key))
        with open(self.key, "w") as f:
            f.write(k.private_bytes_raw().hex() + "\n")
        named = os.path.join(self.d, "release.pub")
        with open(named, "w") as f:
            f.write(f"aerieos-release-ed25519 {k.public_key().public_bytes_raw().hex()}\n")
        out = os.path.join(self.d, "x.sig")
        r = self.signer("--builder", self.key, "--out", out, env={"AERIEOS_RELEASE_PUB": named})
        self.assertEqual(r.returncode, 2)
        self.assertIn("release key, not a builder's", r.stderr)
        self.assertFalse(os.path.exists(out))


if __name__ == "__main__":
    unittest.main()
