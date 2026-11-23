"""aerie roadmap lists an item a line (B993).

The bare verb, where the briefing and the roadmap's own guard send a
session, printed every item's details and every step, finished ones too:
557 KB for 121 items, of which an agent keeps only the start, while the
listing marked the whole of it read. It prints an item a line with how many
of its steps are open; `aerie roadmap show N` prints one whole, and --full
every one so."""
import json
import os
import subprocess
import sys
import tempfile
import unittest

HERE = os.path.dirname(os.path.abspath(__file__))
REPO = os.path.normpath(os.path.join(HERE, "..", "..", ".."))
VERBS = os.path.join(REPO, "scripts", "lib", "roadmap-verbs.py")
ROADMAP = os.path.join(REPO, "scripts", "dashboard", "roadmap.py")
ITEM = {"id": 7, "text": "a plan with a long story", "info": "THE DECISIONS " * 40, "by": "claude",
        "steps": [{"text": "the first, done", "done": True, "info": "how it went " * 20},
                  {"text": "the second, still to do"}]}


class Listing(unittest.TestCase):
    def run_verbs(self, *argv):
        with tempfile.TemporaryDirectory() as d:
            with open(os.path.join(d, "roadmap.json"), "w", encoding="utf-8") as f:
                json.dump({"projects": {"alpha": [ITEM]}}, f)
            p = subprocess.run([sys.executable, VERBS, ROADMAP, "alpha", *argv], capture_output=True, text=True,
                               timeout=60, check=False, cwd="/", env=dict(os.environ, DASHBOARD_STATE=d))
        self.assertEqual(p.returncode, 0, p.stderr)
        return p.stdout

    def test_the_bare_list_is_an_item_a_line(self):
        out = self.run_verbs()
        self.assertIn("R7  a plan with a long story (claude)  (1 of 2 steps open)", out)
        self.assertNotIn("THE DECISIONS", out)
        self.assertNotIn("the first, done", out)
        self.assertIn("aerie roadmap show N", out)

    def test_full_prints_each_whole(self):
        out = self.run_verbs("--full")
        self.assertIn("THE DECISIONS", out)
        self.assertIn("1. the first, done  (done)", out)
        self.assertIn("2. the second, still to do", out)
        self.assertNotIn("steps open", out)
        self.assertEqual(self.run_verbs("list", "--full"), out)


if __name__ == "__main__":
    unittest.main()
