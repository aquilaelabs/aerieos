"""An agent update is AerieOS's own release where the node pinned the
release key (R227 step 1): taken with a signature under that key over its
digest, refused without one, taken unsigned only where the node's console
said so, and taken as before by a node that pinned nothing. The console's
choices outlive the running agent's own writes of node.json."""
import json
import os
import subprocess
import sys
import tempfile
import unittest

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, os.path.join(HERE, "..", "..", "agent"))
from aerieos_agent import release, stores  # noqa: E402
from cryptography.hazmat.primitives.asymmetric.ed25519 import Ed25519PrivateKey  # noqa: E402

DIGEST = "sha256:" + "ab" * 32


def pair():
    k = Ed25519PrivateKey.generate()
    return k, k.public_key().public_bytes_raw().hex()


class Verify(unittest.TestCase):
    def test_the_release_keys_signature_over_the_digest_passes(self):
        k, pub = pair()
        sig = k.sign(release.MESSAGE + DIGEST.encode()).hex()
        self.assertEqual(release.verify(pub, DIGEST, sig), "")
        ok, said = release.may_install({"release_key": pub}, DIGEST, sig)
        self.assertTrue(ok)
        self.assertIn("signed by the release key", said)

    def test_another_key_another_digest_or_no_signature_does_not(self):
        k, pub = pair()
        other, _ = pair()
        sig = k.sign(release.MESSAGE + DIGEST.encode()).hex()
        self.assertIn("not the pinned release key's", release.verify(pub, DIGEST, other.sign(release.MESSAGE + DIGEST.encode()).hex()))
        self.assertIn("not the pinned release key's", release.verify(pub, "sha256:" + "cd" * 32, sig))
        self.assertIn("no signature", release.verify(pub, DIGEST, ""))
        self.assertIn("not the pinned", release.verify(pub, DIGEST, k.sign(DIGEST.encode()).hex()), "a signature of the bare digest is not this one")

    def test_a_pinned_node_refuses_an_unsigned_update_unless_its_console_allows(self):
        _, pub = pair()
        ok, said = release.may_install({"release_key": pub}, DIGEST, "")
        self.assertFalse(ok)
        self.assertIn("sudo builderbot-agent unsigned on", said)
        ok, said = release.may_install({"release_key": pub, "unsigned_ok": True}, DIGEST, "")
        self.assertTrue(ok)
        self.assertIn("console allows unsigned", said)

    def test_a_node_that_pinned_nothing_updates_as_before(self):
        self.assertEqual(release.may_install({}, DIGEST, ""), (True, ""))
        self.assertEqual(release.may_install({"release_key": "not a key"}, DIGEST, ""), (True, ""))


class Console(unittest.TestCase):
    def test_what_the_console_wrote_outlives_the_agents_own_save(self):
        d = tempfile.mkdtemp()
        was = stores.NODE_JSON
        stores.NODE_JSON = os.path.join(d, "node.json")
        self.addCleanup(setattr, stores, "NODE_JSON", was)
        running = {"node_id": "n_1", "token": "bbn_old"}                # the agent's copy, from before
        stores.save_state(dict(running), console=True)
        _, pub = pair()
        stores.save_state({"node_id": "n_1", "token": "bbn_old", "release_key": pub, "unsigned_ok": True}, console=True)
        stores.save_state(dict(running, token="bbn_new"))               # a token handed over: the agent writes its copy
        got = json.load(open(stores.NODE_JSON))
        self.assertEqual((got["token"], got["release_key"], got["unsigned_ok"]), ("bbn_new", pub, True))
        stores.save_state({"node_id": "n_1", "token": "bbn_new", "release_key": pub}, console=True)   # unsigned off, at the console
        stores.save_state(dict(running, token="bbn_3", unsigned_ok=True))                             # a stale copy cannot put it back
        self.assertNotIn("unsigned_ok", json.load(open(stores.NODE_JSON)))
        self.assertEqual(stores.console_said(), {"release_key": pub})


class Signer(unittest.TestCase):
    """tools/sign-agent.py signs this tree's agent, and what it writes passes."""
    def test_what_the_build_signs_is_what_a_node_checks(self):
        tool = os.path.join(HERE, "..", "..", "..", "tools", "sign-agent.py")
        sig = os.path.join(HERE, "..", "..", "agent", "agent.sig")
        had = open(sig).read() if os.path.exists(sig) else None
        self.addCleanup(lambda: open(sig, "w").write(had) if had is not None else (os.path.exists(sig) and os.unlink(sig)))
        k, pub = pair()
        # A key of the test's own, named as the committed file names the real one.
        d = tempfile.mkdtemp()
        mine = os.path.join(d, "release.pub")
        open(mine, "w").write(f"# a test's key\naerieos-release-ed25519 {pub}\n")
        env = dict(os.environ, AERIEOS_RELEASE_PUB=mine)
        r = subprocess.run([sys.executable, tool], env=dict(env, AERIEOS_RELEASE_KEY=k.private_bytes_raw().hex()),
                           capture_output=True, text=True, timeout=60, check=False)
        self.assertEqual(r.returncode, 0, r.stdout + r.stderr)
        got = json.load(open(sig))
        self.assertEqual(got["key"], pub)
        self.assertEqual(release.verify(pub, got["digest"], got["sig"]), "")
        r = subprocess.run([sys.executable, tool, "--check"], env=env, capture_output=True, text=True, timeout=60, check=False)
        self.assertEqual(r.returncode, 0, r.stdout)
        # A key that is not the one the file names signs nothing: nodes
        # pinned to the named one would refuse what it signed.
        os.unlink(sig)
        other, _ = pair()
        r = subprocess.run([sys.executable, tool], env=dict(env, AERIEOS_RELEASE_KEY=other.private_bytes_raw().hex()),
                           capture_output=True, text=True, timeout=60, check=False)
        self.assertEqual(r.returncode, 2)
        self.assertFalse(os.path.exists(sig))
        r = subprocess.run([sys.executable, tool], env={k2: v for k2, v in env.items() if k2 != "AERIEOS_RELEASE_KEY"},
                           capture_output=True, text=True, timeout=60, check=False)
        self.assertIn("ships unsigned", r.stdout)

    def test_the_committed_key_is_one_a_node_can_pin(self):
        sys.path.insert(0, os.path.join(HERE, ".."))
        import enrollscript
        key = enrollscript.release_key()
        self.assertEqual(release.clean_key(key), key)
        self.assertTrue(key, "the repository names AerieOS's release key")


if __name__ == "__main__":
    unittest.main()
