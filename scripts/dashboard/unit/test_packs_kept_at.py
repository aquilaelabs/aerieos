"""Migration 0041 (R205): a pack kept from a folder of a repository, recorded
before 11 Nov without `kept_at`, is given its repository's head, which is
what toolpacks.py read in its place until 27 Nov; a node then fetches it at
the same commit. One that says it already, or is not kept from a folder, is
left as it is."""
import copy
import importlib
import json
import os
import shutil
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))
import toolpacks  # noqa: E402

GIT = ["git", "-c", "user.name=t", "-c", "user.email=t@t", "-c", "commit.gpgsign=false"]


class PacksKeptAt(unittest.TestCase):
    def setUp(self):
        self.d = Path(tempfile.mkdtemp())
        self.addCleanup(shutil.rmtree, self.d, True)
        work = self.d / "work"
        work.mkdir()
        subprocess.run([*GIT, "init", "-q", "-b", "main", str(work)], check=True)
        (work / "bbtool.json").write_text("{}")
        subprocess.run([*GIT, "-C", str(work), "add", "-A"], check=True)
        subprocess.run([*GIT, "-C", str(work), "commit", "-qm", "kept"], check=True)
        (self.d / "toolpacks").mkdir()
        subprocess.run([*GIT, "clone", "-q", "--bare", str(work), str(self.d / "toolpacks" / "kept-pack.git")], check=True)
        self.head = subprocess.run([*GIT, "-C", str(work), "rev-parse", "HEAD"], capture_output=True, text=True, check=True).stdout.strip()
        self.packs = {"packs": {
            "kept-pack": {"name": "kept-pack", "hosted": True, "path": "packs/x", "commit": "c" * 40},
            "said-pack": {"name": "said-pack", "hosted": True, "path": "packs/y", "commit": "c" * 40, "kept_at": "d" * 40},
            "pinned-pack": {"name": "pinned-pack", "commit": "e" * 40}}}
        self.f = self.d / "toolpacks.json"
        self.f.write_text(json.dumps(copy.deepcopy(self.packs)))
        os.chmod(self.f, 0o600)

    def run_it(self):
        importlib.import_module("statemigrations.0041_packs_kept_at").run({"state": str(self.d)})

    def test_each_is_fetched_at_the_commit_it_was_read_at(self):
        self.run_it()
        got = json.loads(self.f.read_text())["packs"]
        self.assertEqual(got["kept-pack"]["kept_at"], self.head, "the head toolpacks.py read in its place")
        self.assertEqual({n: toolpacks._bundle_commit(r) for n, r in got.items()},
                         {"kept-pack": self.head, "said-pack": "d" * 40, "pinned-pack": "e" * 40})
        self.assertEqual((got["said-pack"], got["pinned-pack"]), (self.packs["packs"]["said-pack"], self.packs["packs"]["pinned-pack"]))
        self.assertEqual(self.f.stat().st_mode & 0o777, 0o600)

    def test_it_is_idempotent(self):
        self.run_it()
        once = self.f.read_text()
        self.run_it()
        self.assertEqual(self.f.read_text(), once)


if __name__ == "__main__":
    unittest.main()
