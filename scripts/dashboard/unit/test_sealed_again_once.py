"""Migration 0043 (B1190): a git token, a setting's secret and a forge token
an account gave, each left sealed in the format from before 27 Oct
(BBSEAL1) because only the signing keys' pass rewrote it, are sealed again
in today's format by the round the migration asks of the start, and open to
what they held; the ask is gone once the round is clean, and a start with
no ask runs no round."""
import base64
import hashlib
import hmac
import importlib
import json
import os
import shutil
import sys
import tempfile
import unittest
from pathlib import Path

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))
import accountkeys  # noqa: E402
import gitcreds     # noqa: E402
import installkey   # noqa: E402
import settings     # noqa: E402
import signing      # noqa: E402


def v1(data, key=None):
    """`data` sealed as a build before 27 Oct sealed it (BBSEAL1)."""
    enc, mac = signing._subkeys(key)
    nonce = os.urandom(16)
    ct = bytes(a ^ b for a, b in zip(data, signing._stream(enc, nonce, len(data)), strict=True))
    return signing.MAGIC1 + nonce + ct + hmac.new(mac, signing.MAGIC1 + nonce + ct, hashlib.sha256).digest()


def write_json(p, d, mode=0o644):  # noqa: ARG001 (statefile.write_json's shape)
    Path(p).write_text(json.dumps(d))


class SealedAgainOnce(unittest.TestCase):
    def setUp(self):
        self.d = Path(tempfile.mkdtemp())
        self.addCleanup(shutil.rmtree, self.d, True)
        (self.d / "key").write_bytes(b"k" * 64)
        self.addCleanup(setattr, signing, "MASTER", signing.MASTER)
        self.addCleanup(setattr, signing, "PREVIOUS", signing.PREVIOUS)
        for k in ("seal", "unseal", "sealing"):
            self.addCleanup(setattr, settings, k, getattr(settings, k))
        signing.load_master(str(self.d / "key"))
        signing.PREVIOUS = None
        gitcreds.configure(state=self.d, seal_fn=signing.seal, unseal_fn=signing.unseal,
                           sealing_fn=lambda: signing.MASTER is not None)
        settings.configure(write_json=write_json, state=self.d)
        settings.seal, settings.unseal = signing.seal, signing.unseal
        settings.sealing = lambda: signing.MASTER is not None
        accountkeys.configure(state=self.d)
        installkey.configure(passes=(gitcreds.seal_all, settings.seal_all, accountkeys.seal_all),
                             nodes_previous=lambda: 0, again=self.d / "seal-again")
        self.addCleanup(installkey.configure, passes=(), nodes_previous=None)
        # What an install from before 27 Oct kept.
        (self.d / "gitcreds").mkdir()
        (self.d / "gitcreds" / "web").write_text(
            gitcreds.SEALED + base64.b64encode(v1(b"https://x:tok@github.com")).decode() + "\n")
        (self.d / "settings.json").write_text(json.dumps(
            {"tunnel_token": settings.SEALED + base64.b64encode(v1(b"tunnel-secret")).decode()}))
        k = accountkeys.key_of("u_00000001")
        (self.d / "account-secrets.json").write_text(json.dumps({"u_00000001": {"forges": {"a1b2c3": {
            "host": "github.com", "sealed": base64.b64encode(v1(b"https://me:pat@github.com", k)).decode(),
            "login": "me", "scheme": "https", "at": 1}}}}))
        self.k = k

    def blobs(self):
        git = (self.d / "gitcreds" / "web").read_text().strip()
        st = json.loads((self.d / "settings.json").read_text())["tunnel_token"]
        fg = json.loads((self.d / "account-secrets.json").read_text())["u_00000001"]["forges"]["a1b2c3"]["sealed"]
        return {"git": base64.b64decode(git[len(gitcreds.SEALED):]),
                "setting": base64.b64decode(st[len(settings.SEALED):]),
                "forge": base64.b64decode(fg)}

    def test_the_round_it_asks_for_seals_each_in_todays_format(self):
        importlib.import_module("statemigrations.0043_sealed_again_once").run({"state": str(self.d)})
        self.assertTrue((self.d / "seal-again").is_file())
        self.assertGreaterEqual(installkey.settle(asked_only=True), 3)
        b = self.blobs()
        self.assertEqual({n: signing.old_format(x) for n, x in b.items()}, {"git": False, "setting": False, "forge": False})
        self.assertTrue(all(x.startswith(signing.MAGIC) for x in b.values()))
        self.assertEqual(signing.unseal(b["git"]), b"https://x:tok@github.com")
        self.assertEqual(signing.unseal(b["setting"]), b"tunnel-secret")
        self.assertEqual(signing.open_with(self.k, b["forge"]), b"https://me:pat@github.com")
        self.assertFalse((self.d / "seal-again").exists(), "the ask is gone once the round is clean")

    def test_no_ask_no_round(self):
        before = self.blobs()
        self.assertEqual(installkey.settle(asked_only=True), 0)
        self.assertEqual(installkey.settle(), 0, "no key before today's and no ask")
        self.assertEqual(self.blobs(), before)

    def test_asked_twice_seals_the_same_things(self):
        m = importlib.import_module("statemigrations.0043_sealed_again_once")
        m.run({"state": str(self.d)})
        m.run({"state": str(self.d)})
        installkey.settle(asked_only=True)
        once = {n: signing.unseal(x) if n != "forge" else signing.open_with(self.k, x) for n, x in self.blobs().items()}
        m.run({"state": str(self.d)})
        installkey.settle(asked_only=True)
        self.assertEqual({n: signing.unseal(x) if n != "forge" else signing.open_with(self.k, x)
                          for n, x in self.blobs().items()}, once)


if __name__ == "__main__":
    unittest.main()
