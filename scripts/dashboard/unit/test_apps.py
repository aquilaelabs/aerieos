"""apps: the seed file read once and put aside, the release a controller's
version picks, and the files kept only when their sha256 matches (R272
steps 3 and 4)."""
import hashlib
import json
import os
import shutil
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path
from unittest import mock

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))
import apps  # noqa: E402

REL = "aerieos-release"
KEY = {}


def setUpModule():
    """The key a stable release's list is signed with, named by the install
    these tests stand up: an install that names no signer takes nothing."""
    if not shutil.which("ssh-keygen"):
        return
    d = tempfile.mkdtemp()
    unittest.addModuleCleanup(shutil.rmtree, d, True)
    path = os.path.join(d, "release")
    subprocess.run(["ssh-keygen", "-q", "-t", "ed25519", "-N", "", "-C", "release", "-f", path], check=True,
                   stdin=subprocess.DEVNULL, timeout=30)
    with open(path + ".pub", encoding="utf-8") as f:
        kt, kb = f.read().split()[:2]
    KEY.update(path=path, line=f'{REL} namespaces="{REL}" {kt} {kb} {REL}')


@unittest.skipUnless(shutil.which("ssh-keygen"), "ssh-keygen is not here to sign a release's list with")
class Apps(unittest.TestCase):
    def setUp(self):
        self.tmp = Path(tempfile.mkdtemp())
        self.settings = {"apps_android": True, "apps_vscode": True, "apps_companion": True}

        def write(path, data):
            Path(path).parent.mkdir(parents=True, exist_ok=True)
            Path(path).write_text(json.dumps(data))
        apps.configure(state=self.tmp, version=lambda: "0.7.0-dev.12+abc", setting=self.settings.get,
                       write_json=write)
        self.dev = True
        apps.unvetted_ok = lambda: self.dev
        # An install that names the stable key, every release here signed by
        # it over its files' own bytes: these are the sha256's own rules, and
        # the signed list's are test_release_signing.py's.
        (self.tmp / "release-signers").write_text(KEY["line"] + "\n")
        named = mock.patch.object(apps, "SIGNERS", str(self.tmp / "release-signers"))
        named.start()
        self.addCleanup(named.stop)

    def release(self, tag, files, bad=()):
        rel = self.tmp / "rel"
        rel.mkdir(exist_ok=True)
        assets = []
        for name in files:
            body = name.encode()
            (rel / name).write_bytes(body)
            sha = "0" * 64 if name in bad else hashlib.sha256(body).hexdigest()
            (rel / (name + ".sha256")).write_text(f"{sha}  {name}\n")
            assets += [{"name": name, "browser_download_url": f"file://{rel / name}"},
                       {"name": name + ".sha256", "browser_download_url": f"file://{rel / name}.sha256"}]
        sums = rel / "SHA256SUMS"
        sums.write_text("".join(f"{hashlib.sha256(n.encode()).hexdigest()}  {n}\n" for n in files))
        (rel / "SHA256SUMS.sig").unlink(missing_ok=True)
        subprocess.run(["ssh-keygen", "-Y", "sign", "-q", "-f", KEY["path"], "-n", REL, str(sums)], check=True,
                       stdin=subprocess.DEVNULL, capture_output=True, timeout=30)
        assets += [{"name": "SHA256SUMS", "browser_download_url": f"file://{sums}"},
                   {"name": "SHA256SUMS.sig", "browser_download_url": f"file://{sums}.sig"}]
        return {"tag_name": tag, "assets": assets}

    def test_the_container_edition_s_image_is_held_to_its_signed_release(self):
        # R290 step 3 (the operator, 26 Nov): the registry's image under this
        # build's version against the one its signed list names.
        digest = "sha256:" + "ab" * 32
        ref = f"ghcr.io/aquilaelabs/aerieos@{digest}"
        rel = self.tmp / "img"
        rel.mkdir()
        name = "aerieos-image-0.7.0-dev.12.digest"
        (rel / name).write_text(ref + "\n")
        sums = rel / "SHA256SUMS"
        sums.write_text(f"{hashlib.sha256((ref + chr(10)).encode()).hexdigest()}  {name}\n")
        subprocess.run(["ssh-keygen", "-Y", "sign", "-q", "-f", KEY["path"], "-n", REL, str(sums)], check=True,
                       stdin=subprocess.DEVNULL, capture_output=True, timeout=30)
        release = {"tag_name": "v0.7.0-dev.12", "assets": [
            {"name": name, "browser_download_url": f"file://{rel / name}"},
            {"name": "SHA256SUMS", "browser_download_url": f"file://{sums}"},
            {"name": "SHA256SUMS.sig", "browser_download_url": f"file://{sums}.sig"}]}
        asked = []

        def registry(serves):
            return lambda r: (asked.append(r), (serves, ""))[1]
        conf = dict(state=self.tmp, version=lambda: "0.7.0-dev.12+abc", setting=self.settings.get,
                    write_json=lambda p, d: (Path(p).parent.mkdir(parents=True, exist_ok=True), Path(p).write_text(json.dumps(d))))
        apps.configure(**conf, container=lambda: True, registry_digest=registry(digest))
        got = apps.own_image([release])
        self.assertEqual(got, {"version": "0.7.0-dev.12", "signed": ref, "registry": digest, "ok": True})
        self.assertEqual(asked, ["ghcr.io/aquilaelabs/aerieos:0.7.0-dev.12"], "the tag a person pulls this version by")
        apps.configure(**conf, container=lambda: True, registry_digest=registry("sha256:" + "cd" * 32))
        self.assertIs(apps.own_image([release])["ok"], False)
        apps.configure(**conf, container=lambda: False, registry_digest=registry(digest))
        self.assertEqual(apps.own_image([release]), {}, "bare metal holds its bundle to the list instead")
        apps.configure(**conf, container=lambda: True, registry_digest=registry(digest))
        self.assertEqual(apps.own_image([{**release, "tag_name": "v0.7.0-dev.11"}]), {}, "no release for this build")
        # The digest file changed after the list was signed: not taken.
        (rel / name).write_text(f"ghcr.io/aquilaelabs/aerieos@sha256:{'ef' * 32}\n")
        self.assertIn("not the file", apps.own_image([release])["said"])
        # The bell's row where they differ, and none where they agree.
        apps.write_json(apps.INDEX, {"image": {"version": "0.7.0-dev.12", "registry": "sha256:" + "cd" * 32, "ok": False}})
        self.assertEqual([r["kind"] for r in apps.image_attention("n_own")], ["image-signed"])
        apps.write_json(apps.INDEX, {"image": {"version": "0.7.0-dev.12", "ok": True}})
        self.assertEqual(apps.image_attention("n_own"), [])

    def test_a_build_belongs_to_its_release(self):
        self.assertEqual(apps.base_version("0.7.0-dev.3160+43218c1"), "0.7.0")
        self.assertEqual(apps.base_version("v1.2.3"), "1.2.3")

    def test_the_matching_release_else_the_newest_published(self):
        rels = [{"tag_name": "v0.8.0", "draft": True}, {"tag_name": "v0.7.1"}, {"tag_name": "v0.7.0"}]
        self.assertEqual(apps._pick(rels, "0.7.0"), (rels[2], True))
        self.assertEqual(apps._pick(rels, "0.9.0"), (rels[1], False))

    def test_only_what_matches_its_sha256_is_kept_and_served(self):
        rel = self.release("v0.7.0", ["aerieos-app-0.7.0.apk", "aerieos-vscode-0.7.0.vsix",
                                      "aerieos-companion-0.7.0.exe", "aerieos-companion-0.7.0.pyz"],
                           bad={"aerieos-companion-0.7.0.pyz"})
        (self.tmp / "releases.json").write_text(json.dumps([rel]))
        apps.RELEASES_URL = f"file://{self.tmp / 'releases.json'}"
        v = apps.check()
        held = {a["name"]: [f["file"] for f in a["files"]] for a in v["apps"]}
        self.assertEqual(held["companion"], ["aerieos-companion-0.7.0.exe"])
        self.assertIn("does not match its sha256", v["problem"])
        self.assertTrue(apps.path("android", "aerieos-app-0.7.0.apk"))
        self.assertIsNone(apps.path("android", "../index.json"))
        self.assertIsNone(apps.path("companion", "aerieos-companion-0.7.0.pyz"))

    def test_a_release_with_no_file_of_an_app_says_so_on_its_row(self):
        # 0.5.3 went out with no APK: every install's Apps page said its look
        # at the release did not work, where the look was fine.
        rel = self.release("v0.7.0", ["aerieos-vscode-0.7.0.vsix", "aerieos-companion-0.7.0.exe"])
        (self.tmp / "releases.json").write_text(json.dumps([rel]))
        apps.RELEASES_URL = f"file://{self.tmp / 'releases.json'}"
        v = apps.check()
        rows = {a["name"]: a for a in v["apps"]}
        self.assertEqual(rows["android"]["absent"], "v0.7.0")
        self.assertEqual(rows["android"]["files"], [])
        self.assertEqual(rows["vscode"]["absent"], "")
        self.assertIn("aerieos-companion-0.7.0.pyz not in v0.7.0", v["problem"])
        self.assertNotIn("Android", v["problem"])

    def test_the_file_named_for_the_release_is_taken_never_an_older_ones(self):
        # An older release's file and its signed list attached to the newest
        # were served as current (review of 22 Nov): the version in the
        # name is the one asked for, as the OS updater and the installer ask.
        rel = self.release("v0.7.0", ["aerieos-app-0.6.9.apk", "aerieos-vscode-0.6.9.vsix", "aerieos-vscode-0.7.0.vsix"])
        (self.tmp / "releases.json").write_text(json.dumps([rel]))
        apps.RELEASES_URL = f"file://{self.tmp / 'releases.json'}"
        v = apps.check()
        rows = {a["name"]: a for a in v["apps"]}
        self.assertEqual([f["file"] for f in rows["vscode"]["files"]], ["aerieos-vscode-0.7.0.vsix"])
        self.assertEqual((rows["android"]["files"], rows["android"]["absent"]), ([], "v0.7.0"))
        self.assertIsNone(apps.path("android", "aerieos-app-0.6.9.apk"))

    def test_the_companion_and_the_extension_are_dev_features(self):
        # The operator, 20 Oct: offered, fetched and served only with Offer
        # dev features on; the Android app is not one.
        rel = self.release("v0.7.0", ["aerieos-app-0.7.0.apk", "aerieos-vscode-0.7.0.vsix",
                                      "aerieos-companion-0.7.0.exe"])
        (self.tmp / "releases.json").write_text(json.dumps([rel]))
        apps.RELEASES_URL = f"file://{self.tmp / 'releases.json'}"
        apps.check()
        self.assertTrue(apps.path("vscode", "aerieos-vscode-0.7.0.vsix"))
        self.dev = False
        self.assertEqual([a["name"] for a in apps.view()["apps"]], ["android"])
        self.assertFalse(apps.offered("vscode") or apps.offered("companion"))
        self.assertIsNone(apps.path("vscode", "aerieos-vscode-0.7.0.vsix"))
        self.assertIsNone(apps.path("companion", "aerieos-companion-0.7.0.exe"))
        self.assertTrue(apps.path("android", "aerieos-app-0.7.0.apk"))

    def test_the_seed_is_read_once_and_put_aside(self):
        (self.tmp / "seed.json").write_text(json.dumps({"version": 1, "apps": ["companion"]}))
        got = {}
        self.assertEqual(apps.seed(got.update), {"apps_android": False, "apps_vscode": False, "apps_companion": True})
        self.assertEqual(got["apps_companion"], True)
        self.assertFalse((self.tmp / "seed.json").exists())
        self.assertTrue((self.tmp / "seed.json.applied").exists())
        self.assertEqual(apps.seed(got.update), {})

    def test_a_release_is_taken_on_its_signed_list_or_refused_never_unchecked(self):
        # _signed_list answers a list or a refusal with its reason, so
        # nothing reads a release whose files were checked against nothing
        # (the audit of 21 Nov: the branches for one were dead code).
        rel = {"tag_name": "v1.2.3-dev.4", "assets": []}
        with mock.patch.object(apps, "signers", lambda: []):
            self.assertEqual(apps._signed_list(rel), (None, "", apps.NO_SIGNER))
        with mock.patch.object(apps, "signers", lambda: ["aerieos-dev namespaces=\"aerieos-dev\" ssh-ed25519 AAAA aerieos-dev"]):
            listed, said, why = apps._signed_list(rel)
            self.assertEqual((listed, said), (None, ""))
            self.assertIn("carries no signed list", why)
        import releasecheck
        for mod in (apps, releasecheck):
            with open(mod.__file__, encoding="utf-8") as f:
                code = "\n".join(ln for ln in f.read().splitlines() if not ln.lstrip().startswith("#"))
            self.assertNotIn("listed is not None", code, mod.__name__)
            self.assertNotIn("refused or signature", code, mod.__name__)
        self.assertNotIn("listed is None or", open(apps.__file__, encoding="utf-8").read())


if __name__ == "__main__":
    unittest.main()
