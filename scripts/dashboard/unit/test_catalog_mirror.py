"""A mirror of the vetted catalog (R169 step 6): tools/catalog-mirror.py
makes one from a signed index, the controller imports it only when the
signature is the maintainers' and every pinned repository is in it, refuses
an older one, answers its index when the catalog does not, and fetches a
pinned pack from its bundle with the repository gone, keeping it hosted."""
import hashlib
import importlib.util
import json
import os
import shutil
import subprocess
import sys
import tarfile
import tempfile
import unittest
from unittest import mock

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, os.path.join(HERE, ".."))
import catalogindex  # noqa: E402
import catalogmirror  # noqa: E402
import packformat  # noqa: E402
import statefile  # noqa: E402
import toolpacks  # noqa: E402

try:
    from cryptography.hazmat.primitives import serialization
    from cryptography.hazmat.primitives.asymmetric import ed25519
    HAVE = True
except ImportError:
    HAVE = False

TOOL = os.path.join(HERE, "..", "..", "..", "tools", "catalog-mirror.py")
PACK = {"name": "hexkit", "label": "Hex kit", "about": "Looks inside binaries.", "platforms": ["linux/amd64"],
        "install": {"steps": [["sh", "{dir}/install.sh"]], "verify": ["{dir}/bin/hexkit", "--version"]},
        "layout": {"bin": ["bin"], "tool": "bin/hexkit"},
        "verbs": {"dump": {"about": "A file's bytes as hex.", "usage": "FILE", "run": ["{dir}/bin/hexkit", "dump", "{args}"]}}}


def git(*a, cwd):
    return subprocess.run(["git", *a], cwd=cwd, check=True, capture_output=True, text=True,
                          env=dict(os.environ, GIT_AUTHOR_NAME="t", GIT_AUTHOR_EMAIL="t@t", GIT_COMMITTER_NAME="t",
                                   GIT_COMMITTER_EMAIL="t@t")).stdout.strip()


@unittest.skipUnless(HAVE, "the cryptography library signs the test's index")
class Mirror(unittest.TestCase):
    def setUp(self):
        self.d = tempfile.mkdtemp()
        self.addCleanup(shutil.rmtree, self.d, True)
        self.priv = ed25519.Ed25519PrivateKey.generate()
        pub = self.priv.public_key().public_bytes(serialization.Encoding.Raw, serialization.PublicFormat.Raw)
        pubfile = os.path.join(self.d, "catalog.pub")
        with open(pubfile, "w") as f:
            f.write("builderbot-catalog-ed25519 " + pub.hex() + "\n")
        was = catalogindex.PUB_FILE
        catalogindex.PUB_FILE = pubfile
        self.addCleanup(setattr, catalogindex, "PUB_FILE", was)
        for seam in ("BB_TOOLPACKS_FILE_URLS", "BB_SEAMS"):
            os.environ[seam] = "1"
            self.addCleanup(os.environ.pop, seam, None)
        self.state = os.path.join(self.d, "state")
        os.makedirs(self.state)
        catalogindex.configure(state=self.state)
        catalogindex._cache.update(at=0.0, index=None, error="", missed={})
        catalogmirror.configure(state=self.state, unpack=self.unpack)
        catalogindex.mirror_index = catalogmirror.index
        toolpacks.configure(state=self.state, write_json=statefile.write_json)
        toolpacks.mirror_bundle = catalogmirror.bundle
        self.addCleanup(setattr, catalogindex, "mirror_index", None)
        self.addCleanup(setattr, toolpacks, "mirror_bundle", None)
        self.repo = os.path.join(self.d, "pack")
        os.makedirs(os.path.join(self.repo, "bin"))
        with open(os.path.join(self.repo, "bbtool.json"), "w") as f:
            json.dump(PACK, f)
        with open(os.path.join(self.repo, "bin", "hexkit"), "w") as f:
            f.write("#!/bin/sh\necho hexkit\n")
        git("init", "-q", cwd=self.repo)
        git("add", "-A", cwd=self.repo)
        git("commit", "-qm", "pack", cwd=self.repo)
        self.commit = git("rev-parse", "HEAD", cwd=self.repo)
        tar = subprocess.run(["git", "archive", "--format=tar", self.commit], cwd=self.repo, capture_output=True, check=True).stdout
        self.sha = hashlib.sha256(tar).hexdigest()
        # The index takes https addresses alone: git is pointed at the
        # repository on disk while the mirror is made, and nothing after.
        self.url = "https://example.com/packs/hexkit"

    def unpack(self, aid, dest):
        with tarfile.open(aid) as t:
            t.extractall(dest, filter="data")
        return {"files": 1}

    def catalog(self, generated, sign_with=None, **more):
        """A catalog checkout: index.json pinning the pack, index.sig over it.
        `more` is what else the entry says."""
        c = tempfile.mkdtemp(dir=self.d)
        data = json.dumps({"version": 1, "generated": generated, "packs": [
            {"name": "hexkit", "url": self.url, "commit": self.commit, "sha256": self.sha, "tier": "vetted", "about": "x", "platforms": ["linux/amd64"],
             **more}]}).encode()
        with open(os.path.join(c, "index.json"), "wb") as f:
            f.write(data)
        with open(os.path.join(c, "index.sig"), "w") as f:
            f.write("builderbot-catalog-ed25519-signature " + (sign_with or self.priv).sign(data).hex() + "\n")
        return c

    def make(self, catalog_dir):
        out = os.path.join(self.d, f"mirror-{len(os.listdir(self.d))}.tar.gz")
        spec = importlib.util.spec_from_file_location("catalog_mirror_tool", TOOL)
        mod = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(mod)
        here = {"GIT_CONFIG_COUNT": "1", "GIT_CONFIG_KEY_0": f"url.file://{self.repo}.insteadOf", "GIT_CONFIG_VALUE_0": self.url}
        with mock.patch.object(sys, "argv", ["catalog-mirror.py", out, "--from-dir", catalog_dir]), mock.patch.dict(os.environ, here):
            mod.main()
        return out

    def test_a_mirror_is_made_imported_and_installs_with_the_repository_gone(self):
        arc = self.make(self.catalog("2026-10-29T10:00:00Z"))
        got = catalogmirror.take(arc, 1000)
        self.assertTrue(got.get("ok"), got)
        self.assertEqual(catalogmirror.held(), {"generated": "2026-10-29T10:00:00Z", "packs": 1, "repos": 1, "imported_at": 1000})
        # The repository gone: the pack comes from the mirror's bundle.
        os.rename(self.repo, self.repo + ".gone")
        self.assertIsNotNone(catalogmirror.bundle(self.url, self.commit))
        self.assertIsNone(catalogmirror.bundle(self.url, "f" * 40))
        seen = toolpacks.fetch(self.url, self.commit, sha256=self.sha)
        self.assertNotIn("error", seen, seen)
        self.assertEqual(seen["manifest"]["name"], "hexkit")
        kept = toolpacks.add(self.url, self.commit, "operator", sha256=self.sha, tier="vetted")
        self.assertTrue(kept.get("ok"), kept)
        rec = toolpacks.packs()["hexkit"]
        self.assertEqual((rec.get("hosted"), rec["tier"], rec["url"], rec["commit"]), (True, "vetted", self.url, self.commit),
                         "kept hosted, so the nodes take it from the controller")
        # The catalog not answering: the mirror's index answers.
        def down(u):
            raise OSError("no route")
        r = catalogindex.index("https://catalog.example/", opener=down)
        self.assertIn("did not answer", r["error"])
        self.assertTrue(r["index"]["mirror"])
        self.assertEqual([p["name"] for p in r["index"]["packs"]], ["hexkit"])

    def test_a_mirror_holds_every_pin_an_entry_keeps(self):
        # An entry that moved to a newer pack format keeps the pin of the
        # one before: the mirror holds both commits, so it serves a build
        # that reads the newer format and one that reads only the older.
        with open(os.path.join(self.repo, "bbtool.json"), "w") as f:
            json.dump({**PACK, "about": "Looks inside binaries, more closely."}, f)
        git("commit", "-qam", "the pack, again", cwd=self.repo)
        newer = git("rev-parse", "HEAD", cwd=self.repo)
        tar = subprocess.run(["git", "archive", "--format=tar", newer], cwd=self.repo, capture_output=True, check=True).stdout
        past = packformat.FORMAT + 1
        arc = self.make(self.catalog("2026-10-29T10:00:00Z", commit=newer, sha256=hashlib.sha256(tar).hexdigest(), format=past,
                                     older=[{"format": 1, "commit": self.commit, "sha256": self.sha, "platforms": ["linux/amd64"]}]))
        with tarfile.open(arc) as t:
            t.extractall(os.path.join(self.d, "look"), filter="data")
        heads = catalogmirror._heads(os.path.join(self.d, "look", "catalog-mirror", "repos", f"{catalogmirror.key(self.url)}.bundle"))
        self.assertEqual(heads, {self.commit, newer})
        # This build reads the older pin alone, and installs it from the mirror.
        self.assertTrue(catalogmirror.take(arc, 1000).get("ok"))
        os.rename(self.repo, self.repo + ".gone")
        e = catalogindex.named(catalogmirror.index(), "hexkit")
        self.assertEqual(e["commit"], self.commit)
        self.assertNotIn("error", toolpacks.fetch(self.url, e["commit"], sha256=e["sha256"]))
        with mock.patch.object(packformat, "FORMAT", past):
            self.assertEqual(catalogindex.named(catalogmirror.index(), "hexkit")["commit"], newer)
            self.assertIsNotNone(catalogmirror.bundle(self.url, newer))

    def test_an_import_is_refused_unsigned_incomplete_or_older(self):
        other = ed25519.Ed25519PrivateKey.generate()
        self.assertIn("does not match", catalogmirror.take(self.make_unsigned(other), 1).get("error", ""))
        self.assertTrue(catalogmirror.take(self.make(self.catalog("2026-10-29T10:00:00Z")), 1).get("ok"))
        self.assertIn("before the mirror held here", catalogmirror.take(self.make(self.catalog("2026-10-28T10:00:00Z")), 2)["error"])
        # A mirror missing a pinned repository.
        arc = self.make(self.catalog("2026-10-30T10:00:00Z"))
        bare = os.path.join(self.d, "bare.tar.gz")
        with tarfile.open(arc) as src, tarfile.open(bare, "w:gz") as dst:
            for m in src.getmembers():
                if not m.name.endswith(".bundle"):
                    dst.addfile(m, src.extractfile(m) if m.isfile() else None)
        self.assertIn("lacks the repository of hexkit", catalogmirror.take(bare, 3)["error"])
        self.assertEqual(catalogmirror.held()["generated"], "2026-10-29T10:00:00Z", "the one held stands")
        self.assertEqual(catalogmirror.forget(), {"ok": True})
        self.assertIsNone(catalogmirror.held())

    def test_an_import_is_measured_as_the_catalog_s_own_answer_is(self):
        # One rule for two signed indexes (catalogindex.older), here and on
        # the network: a mirror that does not say when it was made is not a
        # way past the one held, one of the same moment is taken, and a
        # word in the date's place does not hold every later mirror off.
        self.assertTrue(catalogmirror.take(self.make(self.catalog("2026-10-29T10:00:00Z")), 1).get("ok"))
        for odd in ("x", "", "2026-10-30"):
            self.assertEqual(catalogmirror.take(self.make(self.catalog(odd)), 2).get("error"),
                             "not imported: it does not say when it was made, and the mirror held here was made 2026-10-29T10:00:00Z", repr(odd))
        self.assertEqual(catalogmirror.take(self.make(self.catalog("2026-10-29T09:59:59Z")), 3).get("error"),
                         "not imported: it was made 2026-10-29T09:59:59Z, before the mirror held here (2026-10-29T10:00:00Z)")
        self.assertEqual(catalogmirror.held()["imported_at"], 1, "the one held stands")
        self.assertTrue(catalogmirror.take(self.make(self.catalog("2026-10-29T10:00:00Z")), 4).get("ok"), "the same moment is taken")
        self.assertEqual(catalogmirror.forget(), {"ok": True})
        self.assertTrue(catalogmirror.take(self.make(self.catalog("zzzz")), 5).get("ok"), "with none held, a mirror with no date is taken")
        self.assertTrue(catalogmirror.take(self.make(self.catalog("2026-10-30T10:00:00Z")), 6).get("ok"), "and gives way to a dated one")
        self.assertEqual(catalogmirror.held()["generated"], "2026-10-30T10:00:00Z")

    def test_an_archive_on_disk_is_taken_once_per_mirror(self):
        arc = self.make(self.catalog("2026-10-29T10:00:00Z"))
        self.assertTrue(catalogmirror.take_file(arc, 5).get("ok"))
        self.assertEqual(catalogmirror.take_file(arc, 6), {"ok": True, "same": True}, "the same mirror is not taken again at every boot")
        self.assertEqual(catalogmirror.held()["imported_at"], 5)
        self.assertIn("could not be read", catalogmirror.take_file(os.path.join(self.d, "none.tar.gz"), 7)["error"])

    def make_unsigned(self, key):
        # The tool refuses a bad signature itself, so the archive is made by
        # hand: a good mirror whose index.sig another key made.
        good = self.make(self.catalog("2026-10-29T09:00:00Z"))
        bad = os.path.join(self.d, "bad.tar.gz")
        data = json.dumps({"version": 1, "generated": "x", "packs": []}).encode()
        with tarfile.open(good) as src, tarfile.open(bad, "w:gz") as dst:
            for m in src.getmembers():
                if m.name.endswith("index.json") or m.name.endswith("index.sig"):
                    body = data if m.name.endswith("index.json") else ("builderbot-catalog-ed25519-signature " + key.sign(data).hex() + "\n").encode()
                    m.size = len(body)
                    import io
                    dst.addfile(m, io.BytesIO(body))
                else:
                    dst.addfile(m, src.extractfile(m) if m.isfile() else None)
        return bad


if __name__ == "__main__":
    unittest.main()
