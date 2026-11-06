"""A GitHub release updated here keeps its tag (B696): every PATCH sends
tag_name, since GitHub moves a draft patched without it to a name of its own
(untagged-ID), and a draft already moved is found by its title."""
import os
import sys
import unittest
from unittest import mock

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))
import forgerelease  # noqa: E402

DRAFT = {"id": 7, "draft": True, "tag_name": "v1.0.0-dev.3", "name": "v1.0.0-dev.3", "assets": [], "html_url": "u"}


class TagKept(unittest.TestCase):
    def setUp(self):
        self.calls = []

        def req(method, url, token, body=None, data=None, ctype=""):
            self.calls.append((method, url, body))
            return dict(DRAFT) if method == "GET" else {}
        for p in (mock.patch.object(forgerelease, "_req", req),
                  mock.patch.object(forgerelease, "_handle", lambda project: ("github", "GitHub", ("o/r", "t")))):
            p.start()
            self.addCleanup(p.stop)

    def patches(self):
        return [b for m, _, b in self.calls if m == "PATCH"]

    def test_notes_and_publish_send_the_tag(self):
        self.assertTrue(forgerelease.draft_notes("app", "v1.0.0-dev.3", "notes").get("ok"))
        self.assertTrue(forgerelease.publish_draft("app", "v1.0.0-dev.3", "notes").get("ok"))
        self.assertTrue(all(b.get("tag_name") == "v1.0.0-dev.3" for b in self.patches()))

    def test_an_edit_sends_the_tag(self):
        forgerelease._github_edit("app", "o/r", "t", "v1.0.0-dev.3", "notes", [])
        self.assertEqual([b.get("tag_name") for b in self.patches()], ["v1.0.0-dev.3"])

    def test_a_draft_that_lost_its_tag_is_found_by_its_title(self):
        moved = dict(DRAFT, tag_name="untagged-abc")
        with mock.patch.object(forgerelease, "_req", lambda *a, **k: [moved]):
            self.assertEqual(forgerelease._draft_by_tag("o/r", "v1.0.0-dev.3", "t")["id"], 7)
            self.assertIsNone(forgerelease._draft_by_tag("o/r", "v1.0.0-dev.4", "t"))


if __name__ == "__main__":
    unittest.main()
