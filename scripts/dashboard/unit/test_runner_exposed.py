"""A runner registered to a public repository takes a stranger's pull
request (B761): its row says so, from what its host was last asked, never
on the page's own read."""
import io
import json
import os
import sys
import unittest
import urllib.error

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))
import runners  # noqa: E402


class Exposed(unittest.TestCase):
    def setUp(self):
        was = runners.urlopen
        self.addCleanup(setattr, runners, "urlopen", was)
        runners._public.clear()

    def test_github_says_public_or_not(self):
        runners.urlopen = lambda req, timeout=8: io.BytesIO(json.dumps({"private": False}).encode())
        self.assertIs(runners._ask_public("https://github.com/acme/tool"), True)
        runners.urlopen = lambda req, timeout=8: io.BytesIO(json.dumps({"private": True}).encode())
        self.assertIs(runners._ask_public("https://github.com/acme/tool"), False)

        def gone(req, timeout=8):
            raise urllib.error.HTTPError(req.full_url, 404, "Not Found", {}, None)
        runners.urlopen = gone
        self.assertIs(runners._ask_public("https://github.com/acme/tool"), False, "shown to nobody signed out: not public")
        self.assertIsNone(runners._ask_public("https://gitea.example/acme/tool"), "another host is not asked")

    def test_the_row_says_it_once_known(self):
        self.assertEqual(runners.exposed("", "box", True), "")
        runners._public["https://github.com/acme/tool"] = (9e12, True)
        said = runners.exposed("https://github.com/acme/tool", "box", True)
        self.assertIn("a pull request from anybody", said)
        self.assertIn("reaches Docker", said)
        self.assertNotIn("reaches Docker", runners.exposed("https://github.com/acme/tool", "box", False))
        runners._public["https://github.com/acme/quiet"] = (9e12, False)
        self.assertEqual(runners.exposed("https://github.com/acme/quiet", "box", True), "")


if __name__ == "__main__":
    unittest.main()
