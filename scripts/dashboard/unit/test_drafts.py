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
        rel = {"id": 7, "tag_name": "v1.0.0", "draft": True, "html_url": "https://x/r", "body": "### Added\n\n- A thing"}
        sent = []

        def req(method, url, token, body=None, **kw):
            sent.append((method, body))
            if "/git/ref/tags/" in url:
                return {"ref": "refs/tags/v1.0.0"}
            return rel if method == "GET" else {**rel, "draft": False}
        with mock.patch.object(forgerelease, "_handle", return_value=("github", "GitHub", (REPO, "tok"))), \
                mock.patch.object(forgerelease, "_req", req):
            r = forgerelease.publish_draft("p", "v1.0.0", notes="read and corrected")
            self.assertTrue(r.get("ok"), r)
            # The tag goes with it: GitHub drops a draft's tag patched without one (B696).
            # ...as a stable release, the latest only if it is the newest (R206 step 3).
            self.assertEqual(sent[-1], ("PATCH", {"draft": False, "tag_name": "v1.0.0", "prerelease": False,
                                                  "make_latest": "legacy", "body": "read and corrected"}))
            rel["draft"] = False
            self.assertIn("published already", forgerelease.publish_draft("p", "v1.0.0")["error"])


class Holds(unittest.TestCase):
    """What Publish checks beyond the files (R206 step 3): the tag is on the
    git host, and the notes are not CI's placeholder. A draft published from
    the git host's form with its tag field emptied went out as untagged-ID
    (B636), and 4818's notes said nothing."""

    def world(self, rel, tag_there=True):
        self.sent = []

        def req(method, url, token, body=None, **kw):
            self.sent.append((method, url, body))
            if "/git/ref/tags/" in url:
                return {"ref": url.rsplit("/", 1)[-1]} if tag_there else None
            if method == "GET" and "/releases?per_page=30" in url:
                return [rel]
            return rel if method == "GET" else {**rel, "draft": False}
        for p in (mock.patch.object(forgerelease, "_handle", return_value=("github", "GitHub", (REPO, "tok"))),
                  mock.patch.object(forgerelease, "_req", req)):
            p.start()
            self.addCleanup(p.stop)

    def test_placeholder_notes_are_told_apart_from_notes(self):
        for notes in ("", "  \n", "AerieOS 1.0.0: see CHANGELOG.md.", "## Downloads\n\n- the.iso\n\nAerieOS 1.0.0-dev.3: see CHANGELOG.md.",
                      "AerieOS 1.0.0: see CHANGELOG.md.\nSigned by AerieOS: app.apk with the sideload key default"):
            self.assertTrue(forgerelease.placeholder_notes(notes), notes)
        for notes in ("### Added\n\n- A thing", "Fixes the update. Details: see CHANGELOG.md for the list\n\n- one"):
            self.assertFalse(forgerelease.placeholder_notes(notes), notes)

    def test_a_tag_is_a_pre_release_by_what_follows_its_version(self):
        self.assertEqual([forgerelease.is_pre(t) for t in ("v1.0.0", "v1.0.0-dev.3", "v1.0.0-rc.1", "ext-v0.3.0", "ext-v0.3.0-dev.4")],
                         [False, True, True, False, True])

    def test_a_draft_whose_tag_is_not_on_the_host_is_not_published(self):
        self.world({"id": 7, "tag_name": "v1.0.0-dev.3", "draft": True, "body": "### Added\n\n- A thing"}, tag_there=False)
        r = forgerelease.publish_draft("p", "v1.0.0-dev.3")
        self.assertIn("the tag v1.0.0-dev.3 is not on GitHub", r["error"])
        self.assertIn("push the tag first", r["error"])
        self.assertEqual([h["what"] for h in r["holds"]], ["tag"])
        self.assertFalse([m for m, _, _ in self.sent if m == "PATCH"], "nothing was published")

    def test_placeholder_notes_hold_it_until_the_box_says_something(self):
        self.world({"id": 7, "tag_name": "v1.0.0-dev.3", "draft": True, "body": "AerieOS 1.0.0-dev.3: see CHANGELOG.md."})
        r = forgerelease.publish_draft("p", "v1.0.0-dev.3")
        self.assertIn("the notes are the placeholder", r["error"])
        self.assertFalse([m for m, _, _ in self.sent if m == "PATCH"])
        # The notes as they would go out are what is read: the box's.
        r = forgerelease.publish_draft("p", "v1.0.0-dev.3", notes="### Fixed\n\n- The update")
        self.assertTrue(r.get("ok"), r)
        # A pre-release is published as one and never the latest, whatever the draft was marked.
        self.assertEqual(self.sent[-1][2], {"draft": False, "tag_name": "v1.0.0-dev.3", "prerelease": True,
                                            "make_latest": "false", "body": "### Fixed\n\n- The update"})

    def test_the_drafts_list_says_each_ones_holds_and_finds_one_that_lost_its_tag(self):
        # Published from the form with its tag field emptied, GitHub names
        # it untagged-ID: listed under the tag it is titled for.
        self.world({"id": 7, "tag_name": "untagged-abc123", "name": "v1.0.0-dev.3", "draft": True, "prerelease": True,
                    "body": "AerieOS 1.0.0-dev.3: see CHANGELOG.md.", "html_url": "u"}, tag_there=False)
        d = forgerelease.drafts("p")["drafts"]
        self.assertEqual([x["tag"] for x in d], ["v1.0.0-dev.3"])
        self.assertEqual([h["what"] for h in d[0]["holds"]], ["tag", "notes"])


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
