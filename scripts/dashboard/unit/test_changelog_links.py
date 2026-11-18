"""Bugs, commits and changelog lines tied in the notebook (R255): a bug keeps
the commits that fixed it and the words of the lines that answer it, never a
number in the public file; its row finds each line and the release that
carried it, a line reworded, merged or saved from the editor keeps its bugs,
and the release check counts a tie as an answer."""
import json
import os
import shutil
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path
from unittest import mock

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))
import bugs  # noqa: E402
import changelog  # noqa: E402
import roadmap  # noqa: E402


def write_json(p, d, mode=0o644):  # noqa: ARG001  (statefile's signature)
    Path(p).write_text(json.dumps(d))


def git(d, *a):
    return subprocess.run(["git", "-C", str(d), *a], capture_output=True, text=True, check=True).stdout.strip()


class Links(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.mkdtemp()
        self.addCleanup(shutil.rmtree, self.tmp, True)
        self.ws = Path(self.tmp) / "ws"
        self.d = self.ws / "p"
        self.d.mkdir(parents=True)
        git(self.d, "init", "-q")
        (self.d / "a.txt").write_text("one\n")
        git(self.d, "add", "-A")
        git(self.d, "-c", "user.name=t", "-c", "user.email=t@t", "commit", "-qm", "one")
        self.head = git(self.d, "rev-parse", "--short=7", "HEAD")
        bugs.configure(write_json=write_json, state=self.tmp, workspace=str(self.ws),
                       changelog_refs=lambda p, k, linked=None, commits=None: roadmap.changelog_refs(p, k, linked, commits),
                       changelog_lines=roadmap.unreleased_lines)
        self.env = mock.patch.dict(os.environ, {"WORKSPACE": str(self.ws)})
        self.env.start()
        self.addCleanup(self.env.stop)
        self.bug = bugs.add("p", "A move did not land")["bug"]["id"]
        self.other = bugs.add("p", "Something else")["bug"]["id"]
        self.was = changelog.relinked
        changelog.relinked = lambda _d, olds, new: bugs.relink_changelog("p", olds, new)
        self.addCleanup(setattr, changelog, "relinked", self.was)

    def row(self, n):
        return next(b for b in bugs.payload("p")["bugs"] if b["id"] == n)

    def test_a_line_is_tied_found_by_its_words_and_followed_through_an_edit(self):
        changelog.add(str(self.d), "A move lands on a stick", sha="1a2b3c4", cat="Fixed")
        self.assertTrue(bugs.link_changelog("p", self.bug, "A move lands on a stick").get("ok"))
        self.assertTrue(bugs.link_changelog("p", self.bug, "A move lands on a stick").get("ok"), "tied twice is tied once")
        self.assertEqual(self.row(self.bug)["changelog"], ["A move lands on a stick"])
        self.assertNotIn(f"B{self.bug}", (self.d / changelog.FILE).read_text(), "the public file names its commit alone")
        p = bugs.payload("p")
        self.assertEqual(p["changelog"].get(f"B{self.bug}"),
                         [{"in": "Unreleased", "text": "A move lands on a stick (1a2b3c4)",
                           "words": "A move lands on a stick", "tied": True}])
        self.assertNotIn(f"B{self.other}", p["changelog"])
        self.assertEqual(p["lines"], [{"words": "A move lands on a stick", "cat": "Fixed"}])
        n = changelog.numbered(str(self.d))[0][0]
        self.assertTrue(changelog.edit(str(self.d), n, "A move lands on a stick that keeps deploy keys", sha="5d6e7f8").get("ok"))
        self.assertEqual(self.row(self.bug)["changelog"], ["A move lands on a stick that keeps deploy keys"])
        self.assertTrue(bugs.unlink_changelog("p", self.bug, "A move lands on a stick that keeps deploy keys").get("ok"))
        self.assertNotIn("changelog", self.row(self.bug))

    def test_a_merge_ties_both_lines_bugs_to_the_one_line(self):
        changelog.add(str(self.d), "One half", sha="1111111", cat="Fixed")
        changelog.add(str(self.d), "The other half", sha="2222222", cat="Fixed")
        bugs.link_changelog("p", self.bug, "One half")
        bugs.link_changelog("p", self.other, "The other half")
        ns = [r[0] for r in changelog.numbered(str(self.d))]
        self.assertTrue(changelog.merge(str(self.d), ns, "Both halves").get("ok"))
        self.assertEqual((self.row(self.bug)["changelog"], self.row(self.other)["changelog"]), (["Both halves"], ["Both halves"]))

    def test_the_editors_save_carries_a_reworded_lines_ties(self):
        changelog.add(str(self.d), "Old words", sha="1111111", cat="Fixed")
        changelog.add(str(self.d), "Kept as it was", sha="2222222", cat="Fixed")
        bugs.link_changelog("p", self.bug, "Old words")
        gs = changelog.groups(str(self.d))
        gs[0]["entries"][0]["text"] = "New words for the same change"
        self.assertTrue(changelog.put(str(self.d), gs).get("ok"))
        self.assertEqual(self.row(self.bug)["changelog"], ["New words for the same change"])

    def test_the_refs_read_a_release_section_too(self):
        (self.d / changelog.FILE).write_text("# Changelog\n\n## Unreleased\n\n## 0.9.0-dev.6000 - 2026-11-19\n\n### Fixed\n\n"
                                             "- A move lands on a stick (1a2b3c4, 5d6e7f8)\n")
        got = roadmap.changelog_refs("p", "B", {"B9": ["A move lands on a stick"]})
        self.assertEqual(got, {"B9": [{"in": "0.9.0-dev.6000", "text": "A move lands on a stick (1a2b3c4, 5d6e7f8)",
                                       "words": "A move lands on a stick", "tied": True}]})

    def test_a_fix_records_its_commit_and_finds_the_lines_naming_it(self):
        r = bugs.set_status("p", self.bug, "fixed", note="it lands")
        self.assertEqual(r["bug"].get("commits"), [self.head], "closed on a clean tree: the commit it is on")
        changelog.add(str(self.d), "A move lands on a stick", sha=self.head, cat="Fixed")
        refs = bugs.payload("p")["changelog"]
        self.assertEqual(refs.get(f"B{self.bug}"), [{"in": "Unreleased", "text": f"A move lands on a stick ({self.head})",
                                                     "words": "A move lands on a stick", "by": "commit"}])
        self.assertEqual(bugs.set_status("p", self.bug, "open")["bug"].get("commits"), None, "reopened, it names none")

    def test_fixed_in_is_edited_and_only_takes_a_commit_the_repository_holds(self):
        r = bugs.set_status("p", self.bug, "fixed", note="by hand", commits=[self.head])
        self.assertEqual(r["bug"]["commits"], [self.head])
        self.assertIn("no commit", bugs.set_status("p", self.other, "fixed", commits=["deadbee"]).get("error", ""))
        self.assertIn("no commit", bugs.fixed_by("p", self.bug, add=["0000000"]).get("error", ""))
        self.assertNotIn("commits", bugs.fixed_by("p", self.bug, drop=[self.head])["bug"])
        self.assertEqual(bugs.fixed_by("p", self.bug, add=[self.head])["bug"]["commits"], [self.head])

    def test_no_line_is_kept_as_the_answer_and_wants_a_reason(self):
        self.assertIn("only a fixed bug", bugs.no_line("p", self.bug, "never released").get("error", ""))
        bugs.set_status("p", self.bug, "fixed")
        self.assertIn("say why", bugs.no_line("p", self.bug, "  ").get("error", ""))
        self.assertTrue(bugs.no_line("p", self.bug, "no release had it").get("ok"))
        self.assertRegex(self.row(self.bug)["notes"], r"Changelog: needs no line: no release had it$")


class Gate(unittest.TestCase):
    """A repository's Releases setting: owed lines refuse, or go out said."""

    def test_warn_lets_it_go_with_the_owed_lines_said(self):
        import version
        with mock.patch.object(version, "_gaps_refusal", return_value="2 bug(s) ... have no Fixed line"):
            version.release_gate = None
            self.assertEqual(version._gaps_check("p"), ("2 bug(s) ... have no Fixed line", ""))
            version.release_gate = lambda p: "warn"
            why, owed = version._gaps_check("p")
            self.assertEqual(why, "")
            self.assertIn("have no Fixed line", owed)
            version.release_gate = lambda p: 1 / 0
            self.assertTrue(version._gaps_check("p")[0], "a setting that cannot be read refuses")
        version.release_gate = None


if __name__ == "__main__":
    unittest.main()
