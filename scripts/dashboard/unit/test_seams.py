"""The controller's test seams are honored in one place and only beside the
harness's marker (seams.py): a pack fetched from a repository on disk, the
services' images read from another file. The variable alone, left or put
in an install's environment, turns nothing off; the browser suites'
harness and the export tool set the marker beside it."""
import importlib
import os
import re
import sys
import unittest
from unittest import mock

HERE = os.path.dirname(os.path.abspath(__file__))
DASH = os.path.join(HERE, "..")
REPO = os.path.abspath(os.path.join(HERE, "..", "..", ".."))
sys.path.insert(0, DASH)
import seams  # noqa: E402
import toolpacks  # noqa: E402


class Seams(unittest.TestCase):
    def env(self, **more):
        clean = {k: v for k, v in os.environ.items() if k not in (seams.MARK, *seams.NAMES)}
        return mock.patch.dict(os.environ, {**clean, **more}, clear=True)

    def test_a_seam_is_honored_only_beside_the_marker(self):
        for name in seams.NAMES:
            with self.env(**{name: "1"}):
                self.assertEqual((seams.on(), seams.get(name)), (False, ""), name)
            with self.env(**{name: "1", seams.MARK: "1"}):
                self.assertEqual((seams.on(), seams.get(name)), (True, "1"), name)
            with self.env(**{name: "1", seams.MARK: "yes"}):
                self.assertEqual(seams.get(name), "", "the marker is 1 and nothing else")
        with self.env(**{seams.MARK: "1"}):
            self.assertEqual(seams.get(seams.NAMES[0]), "")
            # What is not a seam is not read through here at all.
            self.assertRaises(KeyError, seams.get, "INSTALL_KEY")

    def test_a_pack_on_disk_is_refused_with_the_variable_alone(self):
        commit, sha = "a" * 40, "b" * 64
        with self.env(BB_TOOLPACKS_FILE_URLS="1"):
            self.assertEqual(toolpacks.fetch("file:///tmp/no-such-pack", commit).get("error"),
                             "a pack is a git repository's address: https://host/owner/repo")
            self.assertEqual(toolpacks.fetch_folder("file:///tmp/no-such-pack", commit, sha, "packs/x", ("bbtool.json",)).get("error"),
                             "a catalog entry is a git repository's address: https://host/owner/repo")
        with self.env(BB_TOOLPACKS_FILE_URLS="1", BB_SEAMS="1"):
            for got in (toolpacks.fetch("file:///tmp/no-such-pack", commit), toolpacks.fetch_folder("file:///tmp/no-such-pack", commit, sha, "packs/x", ("bbtool.json",))):
                self.assertNotIn("git repository's address", got.get("error", ""), "its address is taken, and the fetch is what fails")

    def test_the_services_images_are_the_shipped_file_s_with_the_variable_alone(self):
        import services
        shipped = os.path.join(os.path.abspath(DASH), "service-images.json")
        try:
            with self.env(BB_SERVICE_IMAGES_FILE="/tmp/other-images.json"):
                self.assertEqual(os.path.abspath(importlib.reload(services).IMAGES_FILE), shipped)
            with self.env(BB_SERVICE_IMAGES_FILE="/tmp/other-images.json", BB_SEAMS="1"):
                self.assertEqual(importlib.reload(services).IMAGES_FILE, "/tmp/other-images.json")
        finally:
            importlib.reload(services)

    def test_nothing_else_of_the_dashboard_reads_a_seam_s_variable_and_the_harness_sets_the_marker(self):
        for name in sorted(os.listdir(DASH)):
            if name.endswith(".py") and name != "seams.py":
                with open(os.path.join(DASH, name), encoding="utf-8") as f:
                    code = "\n".join(ln for ln in f.read().splitlines() if not ln.lstrip().startswith("#"))
                for seam in seams.NAMES:
                    self.assertNotRegex(code, rf"environ[^\n]*{seam}", f"{name} reads {seam} past seams.py")
        with open(os.path.join(DASH, "test", "run.sh"), encoding="utf-8") as f:
            run = f.read()
        self.assertIn("BB_TOOLPACKS_FILE_URLS=1 BB_SEAMS=1 \\\n", run)
        self.assertIn("BB_SERVICE_IMAGES_FILE=", run)
        with open(os.path.join(REPO, "tools", "packs-export.py"), encoding="utf-8") as f:
            self.assertIn('os.environ.update(BB_TOOLPACKS_FILE_URLS="1", BB_SEAMS="1")', f.read())
        # And none is a setting an install is told of.
        with open(os.path.join(REPO, "docs", "reference.md"), encoding="utf-8") as f:
            ref = f.read()
        for word in (seams.MARK, *seams.NAMES):
            self.assertIsNone(re.search(rf"\b{word}\b", ref), word)


if __name__ == "__main__":
    unittest.main()
