"""What a person is told when a container cannot be asked for:
one sentence each, naming the way forward, with no command in it."""
import os
import sys
import unittest
from unittest import mock

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))
import containers  # noqa: E402
import devapp  # noqa: E402


class Refusals(unittest.TestCase):
    def test_a_name_the_store_has_is_refused_in_one_sentence(self):
        with mock.patch.object(devapp, "_load", lambda: {"sonarr": {}}):
            why = containers.name_free("sonarr")
        self.assertEqual(why, "sonarr already exists here, so change that container rather than asking for it again")

    def test_a_build_from_a_relative_path_is_refused_in_one_sentence(self):
        with mock.patch.object(containers, "relative_builds", lambda c, e="": ["app", "worker"]):
            why = containers.build_refusal("site", "services: {}")
        self.assertEqual(why, "site builds app, worker from a relative path, which a container written here has no tree for: "
                              "build from an absolute path or a git URL, or send the space's own compose file to Docker from its Artifacts view")
        self.assertNotIn("aerie ", why)
        with mock.patch.object(containers, "relative_builds", lambda c, e="": []):
            self.assertEqual(containers.build_refusal("site", "services: {}"), "")


if __name__ == "__main__":
    unittest.main()
