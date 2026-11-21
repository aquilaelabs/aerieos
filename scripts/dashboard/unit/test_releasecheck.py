"""A newer release for a bare-metal install (R90 step 5, releasecheck.py):
the newest published release read, said as newer than the build running
only when it is, on the bell only on a bare-metal install, and nothing of
it on a container install."""
import hashlib
import json
import os
import shutil
import subprocess
import sys
import tempfile
import unittest
from unittest import mock

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))
import apps  # noqa: E402
import releasecheck  # noqa: E402


class ReleaseCheck(unittest.TestCase):
    def setUp(self):
        d = tempfile.mkdtemp()
        self.addCleanup(lambda: None)
        rows = [{"tag_name": "v0.9.1", "draft": True, "html_url": "x"},
                # A dev build's tag on a release marked stable: the tag is
                # what says which release it is, so no stable release.
                {"tag_name": "v1.0.0-dev.1", "prerelease": False},
                {"tag_name": "v0.9.0", "html_url": "https://example/v0.9.0"},
                {"tag_name": "v0.8.2"}, {"tag_name": "junk"},
                {"tag_name": "v0.9.1-dev.4500", "prerelease": True, "html_url": "https://example/dev4500"},
                {"tag_name": "v0.9.1-dev.4400", "prerelease": True},
                {"tag_name": "v0.9.2-dev.9", "draft": True, "prerelease": True}]
        path = os.path.join(d, "releases.json")
        with open(path, "w") as f:
            json.dump(rows, f)
        self.was = releasecheck.RELEASES_URL
        releasecheck.RELEASES_URL = "file://" + path
        self.addCleanup(setattr, releasecheck, "RELEASES_URL", self.was)
        # What the check keeps is the module's, shared with any test that ran
        # before in this process (B731): set to nothing before, as after.
        clear = lambda: releasecheck._latest.update(version="", tag="", at=0, error="", url="",  # noqa: E731
                                                    dev={"version": "", "tag": "", "url": ""})
        clear()
        self.addCleanup(clear)

    def test_the_newest_published_release_and_whether_it_is_newer(self):
        releasecheck.configure(version=lambda: "0.8.2", bare_metal=lambda: True)
        got = releasecheck.check()
        self.assertEqual((got["version"], got["tag"], got["error"]), ("0.9.0", "v0.9.0", ""),
                         "a draft and a dev build's tag marked stable are passed over")
        self.assertEqual(releasecheck.newer(), "0.9.0")
        self.assertEqual(releasecheck.attention("n_own")[0]["key"], "release:0.9.0")
        self.assertEqual(releasecheck.status()["newer"], "0.9.0")
        # Up to date, or ahead (a dev build of the next version): nothing.
        releasecheck.configure(version=lambda: "0.9.0", bare_metal=lambda: True)
        self.assertEqual(releasecheck.newer(), "")
        self.assertEqual(releasecheck.attention("n_own"), [])
        releasecheck.configure(version=lambda: "0.9.1-dev.12+abc", bare_metal=lambda: True)
        self.assertEqual(releasecheck.newer(), "", "a dev build past the release is not behind it")
        # B618: a dev build heading for the release stands below it on the
        # normal channel too, so one that picked Releases again moves to it.
        releasecheck.configure(version=lambda: "0.9.0-dev.4400+abc", bare_metal=lambda: True, channel=lambda: "normal")
        self.assertEqual(releasecheck.newer(), "0.9.0", "a dev build moves to the release it was heading for")
        # A container install: nothing drawn, whatever the release.
        releasecheck.configure(version=lambda: "0.8.2", bare_metal=lambda: False)
        self.assertEqual((releasecheck.status(), releasecheck.attention("n_own")), ({}, []))

    def test_a_registry_that_does_not_answer_is_said(self):
        releasecheck.RELEASES_URL = "file:///nonexistent/releases.json"
        releasecheck.configure(version=lambda: "0.8.2", bare_metal=lambda: True, channel=lambda: "normal", debug=lambda: False)
        got = releasecheck.check()
        self.assertIn("did not answer", got["error"])
        self.assertEqual(releasecheck.newer(), "")

    def test_the_stable_channel_goes_by_the_tag_whatever_the_flag_beside_it_says(self):
        # The flag is the git host's, and whoever can edit a release flips
        # it: a dev build marked stable is no stable release, and a stable
        # release is one whether or not it is marked a pre-release. Who may
        # have signed its files follows the same reading of the tag.
        rows = [{"tag_name": "v1.1.0-dev.7", "prerelease": False, "html_url": "x"},
                {"tag_name": "v1.1.0-rc.8", "prerelease": False},
                {"tag_name": "v1.0.1", "prerelease": True, "html_url": "https://example/v1.0.1"},
                {"tag_name": "v1.0.0", "prerelease": False}]
        d = tempfile.mkdtemp()
        with open(os.path.join(d, "releases.json"), "w") as f:
            json.dump(rows, f)
        releasecheck.RELEASES_URL = "file://" + os.path.join(d, "releases.json")
        releasecheck.configure(version=lambda: "1.0.0", bare_metal=lambda: True, channel=lambda: "normal")
        got = releasecheck.check()
        self.assertEqual((got["version"], got["tag"], got["url"]), ("1.0.1", "v1.0.1", "https://example/v1.0.1"))
        self.assertEqual(releasecheck.newer(), "1.0.1", "never 1.1.0-dev.7 or 1.1.0-rc.8, marked stable as they are")
        self.assertEqual(got["dev"]["version"], "", "the dev channel takes a pre-release's tag marked as one, as before")
        for tag, kind in (("v1.0.1", "stable"), ("v1.1.0-dev.7", "pre"), ("v1.1.0-rc.8", "pre"), ("1.0.1", ""), ("junk", "")):
            self.assertEqual(releasecheck.tag_kind(tag), kind, tag)

    def test_a_named_release_line_is_followed_on_both_channels(self):
        # A stick written with BB_RELEASE_LINE=0.9 is offered 0.9's releases
        # and dev builds alone, never 0.10's; no line, or none that reads as
        # one, follows every release.
        rows = [{"tag_name": "v0.10.0", "html_url": "https://example/v0.10.0"},
                {"tag_name": "v0.10.1-dev.20", "prerelease": True},
                {"tag_name": "v0.9.3", "html_url": "https://example/v0.9.3"},
                {"tag_name": "v0.9.4-dev.12", "prerelease": True}]
        d = tempfile.mkdtemp()
        with open(os.path.join(d, "releases.json"), "w") as f:
            json.dump(rows, f)
        releasecheck.RELEASES_URL = "file://" + os.path.join(d, "releases.json")
        for named, stable, dev in (("0.9", "0.9.3", "0.9.4-dev.12"), ("v0.10", "0.10.0", "0.10.1-dev.20"),
                                   ("", "0.10.0", "0.10.1-dev.20"), ("junk", "0.10.0", "0.10.1-dev.20")):
            with mock.patch.dict(os.environ, {"BB_RELEASE_LINE": named}):
                releasecheck.configure(version=lambda: "0.9.2", bare_metal=lambda: True, channel=lambda: "normal")
                got = releasecheck.check()
                self.assertEqual((got["version"], got["dev"]["version"]), (stable, dev), named)
                self.assertEqual(releasecheck.newer(), stable, named)
                releasecheck.configure(version=lambda: "0.9.2", bare_metal=lambda: True, channel=lambda: "dev")
                self.assertEqual(releasecheck.newer(), dev, named)
        # A line is the environment's, the same for the life of the process:
        # the record is new as a start's.
        releasecheck._latest.update(version="", tag="", at=0, error="", url="", dev={"version": "", "tag": "", "url": ""})
        with mock.patch.dict(os.environ, {"BB_RELEASE_LINE": "0.8"}):
            releasecheck.configure(version=lambda: "0.9.2", bare_metal=lambda: True, channel=lambda: "normal")
            got = releasecheck.check()
            self.assertEqual(got["error"], "no published release on the 0.8 line")
            self.assertEqual(releasecheck.newer(), "")


    def test_the_dev_channel_takes_pre_releases_and_debug_mode_picks_any(self):
        # R179: the normal channel passes a pre-release over; the dev
        # channel takes the newest dev build's and ranks it against the releases.
        releasecheck.configure(version=lambda: "0.9.0", bare_metal=lambda: True, channel=lambda: "dev")
        got = releasecheck.check()
        self.assertEqual((got["version"], got["dev"]["version"], got["dev"]["tag"]), ("0.9.0", "0.9.1-dev.4500", "v0.9.1-dev.4500"),
                         "the newest pre-release whose tag is a dev build's, never a draft")
        self.assertEqual(releasecheck.newer(), "0.9.1-dev.4500", "on the dev channel a release moves to the dev build past it")
        self.assertEqual(releasecheck.status()["channel"], "dev")
        releasecheck.configure(version=lambda: "0.9.1-dev.4450+abc1234", bare_metal=lambda: True, channel=lambda: "dev", debug=lambda: True)
        self.assertEqual(releasecheck.newer(), "0.9.1-dev.4500", "a dev build moves to a later dev build")
        releasecheck.configure(version=lambda: "0.9.1-dev.4600+abc1234", bare_metal=lambda: True, channel=lambda: "dev", debug=lambda: True)
        self.assertEqual(releasecheck.newer(), "", "...and not to an earlier one")
        releasecheck.configure(version=lambda: "0.9.1-dev.4600+abc1234", bare_metal=lambda: True, channel=lambda: "normal", debug=lambda: True)
        self.assertEqual(releasecheck.newer(), "", "the normal channel never offers a dev build")
        releasecheck.configure(version=lambda: "0.9.0", bare_metal=lambda: True, channel=lambda: "dev")
        self.assertEqual(releasecheck.status()["pick"], [], "only debug mode picks a version")
        releasecheck.configure(version=lambda: "0.9.0", bare_metal=lambda: True, channel=lambda: "dev", debug=lambda: True)
        tags = [v["tag"] for v in releasecheck.status()["pick"]]
        self.assertIn("v0.9.1-dev.4500", tags)
        self.assertEqual(tags, sorted(tags, key=lambda t: releasecheck.rank(t.lstrip("v")), reverse=True), "newest first")
        self.assertEqual(releasecheck.rank("0.9.0"), (0, 9, 0, 10 ** 9))
        self.assertEqual(releasecheck.rank("v0.9.0-dev.12+abcdef0"), (0, 9, 0, 12))
        # Any name is a pre-release on the dev channel, ordered by the
        # commit's ordinal it carries, whatever it is called (R218).
        self.assertEqual(releasecheck.rank("v0.9.0-rc.14"), (0, 9, 0, 14))
        self.assertGreater(releasecheck.rank("0.9.0-rc.14"), releasecheck.rank("0.9.0-dev.13"))
        self.assertLess(releasecheck.rank("0.9.0-rc.14"), releasecheck.rank("0.9.0"))
        self.assertIsNone(releasecheck.rank("0.9.0-RC 1"))


@unittest.skipUnless(shutil.which("ssh-keygen"), "no ssh-keygen here")
class SignedImage(unittest.TestCase):
    """The container image a release names as its own (R199): one line in
    the release, in its signed list of files, read from the newest release
    whose list this install takes. Real keys and ssh-keygen; the releases
    and their files are a folder's."""
    A, B = "sha256:" + "a" * 64, "sha256:" + "b" * 64
    OWN = "ghcr.io/aquilaelabs/aerieos"

    def setUp(self):
        self.d = tempfile.mkdtemp()
        self.addCleanup(shutil.rmtree, self.d, True)
        self.key = os.path.join(self.d, "key")
        subprocess.run(["ssh-keygen", "-q", "-t", "ed25519", "-N", "", "-f", self.key], check=True,
                       stdin=subprocess.DEVNULL, timeout=30)
        with open(self.key + ".pub") as f:
            pub = " ".join(f.read().split()[:2])
        signers = os.path.join(self.d, "release-signers")
        with open(signers, "w") as f:
            f.write(f'aerieos-dev namespaces="aerieos-dev" {pub}\n')
        for p in (mock.patch.object(apps, "SIGNERS", signers),
                  mock.patch.object(releasecheck, "RELEASES_URL", "file://" + os.path.join(self.d, "releases.json"))):
            p.start()
            self.addCleanup(p.stop)
        self.rows = []

    def release(self, tag, digest=None, sign=True, **row):
        """A published release: its image's line when `digest`, another
        file, and the list of both, signed for dev builds unless not."""
        folder = os.path.join(self.d, tag)
        os.makedirs(folder)
        ver = tag.lstrip("v")
        files = {f"aerieos-controller-{ver}.tar.gz": b"a bundle"}
        if digest:
            files[f"aerieos-image-{ver}.digest"] = f"{self.OWN}@{digest}\n".encode()
        files["SHA256SUMS"] = "".join(f"{hashlib.sha256(b).hexdigest()}  {n}\n" for n, b in files.items()).encode()
        for n, b in files.items():
            with open(os.path.join(folder, n), "wb") as f:
                f.write(b)
        names = list(files)
        if sign:
            subprocess.run(["ssh-keygen", "-q", "-Y", "sign", "-f", self.key, "-n", "aerieos-dev", os.path.join(folder, "SHA256SUMS")],
                           check=True, stdin=subprocess.DEVNULL, capture_output=True, timeout=30)
            names.append("SHA256SUMS.sig")
        self.rows.append({"tag_name": tag, "prerelease": "-" in tag,
                          "assets": [{"name": n, "browser_download_url": "file://" + os.path.join(folder, n)} for n in names]} | row)
        with open(os.path.join(self.d, "releases.json"), "w") as f:
            json.dump(self.rows, f)
        return folder

    def test_the_newest_signed_release_names_its_image_by_digest(self):
        self.release("v0.9.1-dev.4400", self.A)
        self.release("v0.9.1-dev.4500", self.B)
        self.release("v0.9.1-dev.4600", self.A, draft=True)
        self.assertEqual(releasecheck.signed_image("dev"),
                         {"tag": "v0.9.1-dev.4500", "image": self.OWN, "digest": self.B, "ref": f"{self.OWN}@{self.B}",
                          "signed": "signed by the key AerieOS's dev builds are signed with"},
                         "the newest published, never a draft")
        # :latest follows the stable releases, and none is published.
        self.assertEqual(releasecheck.signed_image("latest"), {"why": "there is no published release"})

    def test_a_release_whose_list_is_not_taken_is_passed_over_for_the_one_before(self):
        self.release("v0.9.1-dev.4500", self.A)
        self.release("v0.9.1-dev.4600", self.B, sign=False)
        got = releasecheck.signed_image("dev")
        self.assertEqual((got["tag"], got["digest"]), ("v0.9.1-dev.4500", self.A), "an unsigned release's word is nobody's")
        # With none signed, why not is said and no image is named.
        self.rows.clear()
        self.release("v0.9.1-dev.4700", self.B, sign=False)
        got = releasecheck.signed_image("dev")
        self.assertNotIn("digest", got)
        self.assertIn("carries no signed list of its files", got["why"])

    def test_a_signed_release_that_names_no_image_ends_the_look(self):
        # Never the image of the release before it in its place: the tag
        # people follow serves the newest release's.
        self.release("v0.9.1-dev.4500", self.A)
        self.release("v0.9.1-dev.4600")
        got = releasecheck.signed_image("dev")
        self.assertEqual(got["tag"], "v0.9.1-dev.4600")
        self.assertNotIn("digest", got)
        self.assertIn("is signed and names no image", got["why"])

    def test_an_image_file_that_is_not_the_one_the_list_names_is_said(self):
        folder = self.release("v0.9.1-dev.4500", self.A)
        with open(os.path.join(folder, "aerieos-image-0.9.1-dev.4500.digest"), "w") as f:
            f.write(f"{self.OWN}@{self.B}\n")
        got = releasecheck.signed_image("dev")
        self.assertNotIn("digest", got)
        self.assertIn("is not the file its signed list names", got["why"])
        # ...and so is a line that is no image by digest, signed or not.
        self.rows.clear()
        folder = self.release("v0.9.1-dev.4800", "latest")
        self.assertIn("is not the file its signed list names", releasecheck.signed_image("dev")["why"])
        # The releases not answering is said too.
        with mock.patch.object(releasecheck, "RELEASES_URL", "file:///nonexistent/releases.json"):
            self.assertIn("the releases did not answer", releasecheck.signed_image("dev")["why"])


if __name__ == "__main__":
    unittest.main()
