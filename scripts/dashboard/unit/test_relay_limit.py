"""A relayed release has longer than any other verb before the controller
ends it (B717): ended at three minutes it printed nothing and was half made."""
import os
import sys
import unittest

sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)), ".."))
import bbrelay  # noqa: E402


class Limit(unittest.TestCase):
    def test_a_release_and_a_rehearsal_have_longer(self):
        self.assertEqual(bbrelay.relay_limit(["version", "release", "--dev", "--why", "x"]), bbrelay.RELAY_LONG_S)
        self.assertEqual(bbrelay.relay_limit(["version", "rehearse"]), bbrelay.RELAY_LONG_S)
        self.assertGreater(bbrelay.RELAY_LONG_S, 240, "past version-verbs.py's own wait on the controller")

    def test_every_other_verb_keeps_three_minutes(self):
        for argv in (["version"], ["version", "bump"], ["bug", "add", "release"], ["roadmap"]):
            self.assertEqual(bbrelay.relay_limit(argv), bbrelay.RELAY_S, argv)


if __name__ == "__main__":
    unittest.main()
