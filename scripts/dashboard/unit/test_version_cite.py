"""A cut dates the changelog's entries from one walk of its history,
where each entry was a `git log -S` of its own: the commit that
added an entry's line is the one it names, a stamp given by hand is kept,
and an entry asks git nothing more once the history is read."""
import os
import shutil
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))
import version  # noqa: E402

GIT = ["git", "-c", "user.name=t", "-c", "user.email=t@t", "-c", "commit.gpgsign=false"]


class Cite(unittest.TestCase):
    def setUp(self):
        self.ws = Path(tempfile.mkdtemp())
        self.addCleanup(shutil.rmtree, self.ws, ignore_errors=True)
        version.configure(workspace=self.ws, state=self.ws / ".state", write_json=lambda *a, **k: None)
        version._git_kept.clear()
        self.p = self.ws / "app"
        self.p.mkdir()
        subprocess.run([*GIT, "init", "-q", "-b", "main", str(self.p)], check=True)
        self.lines = []

    def commit(self, name, text):
        (self.p / name).write_text(text)
        subprocess.run([*GIT, "-C", str(self.p), "add", name], check=True)
        subprocess.run([*GIT, "-C", str(self.p), "commit", "-qm", "c"], check=True)
        return subprocess.run([*GIT, "-C", str(self.p), "rev-parse", "--short=7", "HEAD"],
                              check=True, capture_output=True, text=True).stdout.strip()

    def entry(self, text):
        self.lines.append(f"- {text}")
        return self.commit("CHANGELOG.md", "## Unreleased\n\n### Changed\n\n" + "\n".join(self.lines) + "\n")

    def test_each_entry_names_the_commit_that_added_it(self):
        self.commit("a.txt", "a\n")
        one = self.entry("The first change (abc1234)")
        self.commit("b.txt", "b\n")
        two = self.entry("The second change")
        # A later commit that moves the first line leaves it its own.
        self.lines.reverse()
        self.commit("CHANGELOG.md", "## Unreleased\n\n### Changed\n\n" + "\n".join(self.lines) + "\n")
        hist = version._changelog_added("app", "CHANGELOG.md")
        self.assertEqual(version._cite("app", "CHANGELOG.md", "The second change", (), hist), [two])
        # A stamp given by hand, naming another change, is kept.
        self.assertEqual(version._cite("app", "CHANGELOG.md", "The first change", ["abc1234"], hist), ["abc1234"])
        # The same answer as the history read for the one entry.
        self.assertEqual(version._cite("app", "CHANGELOG.md", "The second change"), [two])
        self.assertNotEqual(one, two)

    def test_an_entry_the_history_does_not_hold_keeps_what_it_had(self):
        self.entry("Something")
        hist = version._changelog_added("app", "CHANGELOG.md")
        self.assertEqual(version._cite("app", "CHANGELOG.md", "Never written", ["1234567"], hist), ["1234567"])
        self.assertEqual(version._cite("app", "CHANGELOG.md", "Never written", (), hist), [])

    def test_given_the_history_an_unstamped_entry_asks_git_nothing(self):
        for i in range(6):
            self.commit(f"f{i}.txt", f"{i}\n")
            self.entry(f"Change number {i}")
        hist = version._changelog_added("app", "CHANGELOG.md")
        calls = []
        real = version._git
        version._git = lambda *a, **k: calls.append(a) or real(*a, **k)
        self.addCleanup(setattr, version, "_git", real)
        got = [version._cite("app", "CHANGELOG.md", f"Change number {i}", (), hist) for i in range(6)]
        self.assertEqual(calls, [])
        self.assertEqual(len({g[0] for g in got if len(g) == 1}), 6)


if __name__ == "__main__":
    unittest.main()
