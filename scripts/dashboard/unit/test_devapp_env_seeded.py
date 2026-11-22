"""An instance's env opens on its tree's .env.example, said as started from
it, only where there is one: the website's, whose tree has none, opened
empty and was said to have started from one (22 Nov)."""
import os
import sys
import unittest
from unittest import mock

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))
import devactions  # noqa: E402
import devapp  # noqa: E402


class Seeded(unittest.TestCase):
    def ask(self, stored, example):
        with mock.patch.object(devapp, "instances", lambda _p: ["main"]), \
                mock.patch.object(devapp, "read_env", lambda _p, _i: stored), \
                mock.patch.object(devapp, "starter", lambda _p, _i: example), \
                mock.patch.object(devapp, "missing_env", lambda _p, _i: []):
            return devactions.act("site", "main", "env-get", {})

    def test_an_example_seeds_the_box_and_says_so(self):
        got, code = self.ask("", "# Started from this space's .env.example.\nPORT=8080\n")
        self.assertEqual(code, 200)
        self.assertTrue(got["seeded"])
        self.assertIn("PORT=8080", got["text"])

    def test_a_tree_with_no_example_opens_empty_and_says_nothing_of_one(self):
        got, _ = self.ask("", "")
        self.assertEqual((got["text"], got["seeded"]), ("", False))

    def test_what_is_stored_is_shown_and_is_not_a_draft(self):
        got, _ = self.ask("STATS_USER=me\n", "PORT=8080\n")
        self.assertEqual((got["text"], got["seeded"]), ("STATS_USER=me\n", False))


if __name__ == "__main__":
    unittest.main()
