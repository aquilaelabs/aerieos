"""Every release starts a draft (the operator, 1 Nov): a draft is found by
its tag where GitHub's by-tag look-up cannot see one, it is published only
when whole, the update check sees drafts only with the debug-mode token on
the dev channel, and that token is debug mode's alone."""
import io
import json
import os
import shutil
import sys
import tempfile
import unittest
import urllib.error
from pathlib import Path
from unittest import mock

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))
import forgerelease  # noqa: E402
import releasecheck  # noqa: E402
import settings  # noqa: E402

API = forgerelease.API
REPO = "owner/proj"


def answer(rows_by_url):
    """A urlopen that answers JSON by URL, 404 for one it does not know."""
    def urlopen(req, timeout=None, context=None):
        url = req.full_url if hasattr(req, "full_url") else req
        if url in rows_by_url:
            return io.BytesIO(json.dumps(rows_by_url[url]).encode())
        raise urllib.error.HTTPError(url, 404, "Not Found", {}, io.BytesIO(b"{}"))
    return urlopen


class Drafts(unittest.TestCase):
    def test_a_draft_is_found_by_its_tag_among_the_listed(self):
        draft = {"id": 7, "tag_name": "v1.0.0-dev.3", "draft": True, "body": "notes"}
        listed = {f"{API}/repos/{REPO}/releases?per_page=50&page=1": [{"id": 6, "tag_name": "v1.0.0-dev.2"}, draft]}
        with mock.patch.object(forgerelease.urllib.request, "urlopen", answer(listed)):
            got = forgerelease._req("GET", f"{API}/repos/{REPO}/releases/tags/v1.0.0-dev.3", "tok")
            self.assertEqual(got["id"], 7)
            self.assertIsNone(forgerelease._req("GET", f"{API}/repos/{REPO}/releases/tags/v9.9.9", "tok"))

    def test_a_draft_is_published_only_when_whole(self):
        self.assertIn("not whole yet: the.apk", forgerelease.publish_draft("p", "v1.0.0", missing=["the.apk"])["error"])
        rel = {"id": 7, "tag_name": "v1.0.0", "draft": True, "html_url": "https://x/r"}
        sent = []

        def req(method, url, token, body=None, **kw):
            sent.append((method, body))
            return rel if method == "GET" else {**rel, "draft": False}
        with mock.patch.object(forgerelease, "_handle", return_value=("github", "GitHub", (REPO, "tok"))), \
                mock.patch.object(forgerelease, "_req", req):
            r = forgerelease.publish_draft("p", "v1.0.0", notes="read and corrected")
            self.assertTrue(r.get("ok"), r)
            # The tag goes with it: GitHub drops a draft's tag patched without one (B696).
            self.assertEqual(sent[-1], ("PATCH", {"draft": False, "tag_name": "v1.0.0", "body": "read and corrected"}))
            rel["draft"] = False
            self.assertIn("published already", forgerelease.publish_draft("p", "v1.0.0")["error"])


class TheSigningAttach(unittest.TestCase):
    def test_the_apks_attach_leaves_a_draft_a_draft(self):
        # B590: its notes sent alone published v0.9.0-dev.4750 unread.
        import releasesign
        sent = []

        def req(method, url, token, body=None, **kw):
            sent.append((method, body))
            return {"id": 7, "draft": True, "body": "notes", "assets": [], "html_url": "u"} if method == "GET" else {}
        with mock.patch.object(forgerelease, "_req", req):
            releasesign._attach("p", REPO, "tok", "v1.0.0-dev.3", [], ["signed with the space's key"])
        self.assertEqual(sent[-1][0], "PATCH")
        self.assertIs(sent[-1][1]["draft"], True)
        self.assertEqual(sent[-1][1]["tag_name"], "v1.0.0-dev.3")


class TheCheck(unittest.TestCase):
    def setUp(self):
        self.rows = [{"tag_name": "v1.0.0", "html_url": "u0"},
                     {"tag_name": "v1.0.1-dev.5", "prerelease": True, "html_url": "u5"},
                     {"tag_name": "v1.0.1-dev.9", "prerelease": True, "draft": True, "html_url": "u9",
                      "assets": [{"name": "aerieos-os-1.0.1-dev.9.iso", "url": "https://api.github.com/repos/o/r/releases/assets/1"}]}]
        self.asked = []

        def urlopen(req, timeout=None):
            self.asked.append(req.unredirected_hdrs.get("Authorization", ""))
            return io.BytesIO(json.dumps(self.rows).encode())
        for k, v in (("urlopen", urlopen),):
            p = mock.patch.object(releasecheck.urllib.request, k, v)
            p.start()
            self.addCleanup(p.stop)
        p = mock.patch.object(releasecheck, "RELEASES_URL", "https://api.github.com/repos/o/r/releases")
        p.start()
        self.addCleanup(p.stop)
        releasecheck._drafts.clear()

    def configure(self, channel, token):
        releasecheck.configure(version=lambda: "1.0.0", bare_metal=lambda: True, channel=lambda: channel, debug=lambda: True,
                               draft_token=lambda: token)

    def test_drafts_are_seen_with_the_token_on_the_dev_channel_alone(self):
        self.configure("dev", "tok")
        rec = releasecheck.check()
        self.assertEqual(self.asked[-1], "Bearer tok")
        self.assertEqual((rec["dev"]["tag"], rec["dev"]["draft"]), ("v1.0.1-dev.9", True))
        self.assertTrue(releasecheck.is_draft("v1.0.1-dev.9"))
        self.configure("dev", "")
        rec = releasecheck.check()
        self.assertEqual(self.asked[-1], "", "no token, nothing sent")
        self.assertEqual(rec["dev"]["tag"], "v1.0.1-dev.5", "a draft is not seen without it")
        self.configure("normal", "tok")
        releasecheck.check()
        self.assertEqual(self.asked[-1], "", "the normal channel never sends it")
        self.assertFalse(releasecheck.is_draft("v1.0.1-dev.9"))


class TheToken(unittest.TestCase):
    def setUp(self):
        self.tmp = Path(tempfile.mkdtemp())
        self.addCleanup(shutil.rmtree, self.tmp, True)
        saved = (settings.FILE, settings.write_json, os.environ.get("DEBUG_MODE"))

        def back():
            settings.FILE, settings.write_json = saved[:2]
            os.environ.pop("DEBUG_MODE", None) if saved[2] is None else os.environ.__setitem__("DEBUG_MODE", saved[2])
        self.addCleanup(back)
        settings.FILE, settings.write_json = self.tmp / "settings.json", lambda p, d: Path(p).write_text(json.dumps(d))

    def test_the_token_is_debug_modes_alone(self):
        os.environ.pop("DEBUG_MODE", None)
        self.assertIn("debug mode", settings.set_many({"release_token": "ghp_x"}).get("error", ""))
        os.environ["DEBUG_MODE"] = "1"
        self.assertTrue(settings.set_many({"release_token": "ghp_x"}).get("ok"))
        self.assertEqual(settings.secret("release_token"), "ghp_x")
        self.assertNotIn("ghp_x", json.dumps(settings.effective().get("release_token")), "never sent back to the page")
        os.environ.pop("DEBUG_MODE")
        settings.reset_debug()
        self.assertEqual(settings.secret("release_token"), "", "cleared at a start out of debug mode")


if __name__ == "__main__":
    unittest.main()
