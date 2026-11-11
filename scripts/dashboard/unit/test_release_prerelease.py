"""Releases of any name and what they owe the changelog (R217), in a scratch
repository: a pre-release (dev, rc, any word) takes Unreleased as its own
section in a commit of its own and is tagged on it; a stable release gathers
the pre-releases since the last stable one; and a release is refused while a
bug fixed since the last release, which that release carried, has no Fixed
line or answer."""
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
import releasegaps  # noqa: E402
import version  # noqa: E402

GIT_ENV = {"GIT_AUTHOR_NAME": "t", "GIT_AUTHOR_EMAIL": "t@example.com",
           "GIT_COMMITTER_NAME": "t", "GIT_COMMITTER_EMAIL": "t@example.com"}


class PreRelease(unittest.TestCase):
    def setUp(self):
        self.ws = Path(tempfile.mkdtemp())
        self.addCleanup(shutil.rmtree, self.ws, ignore_errors=True)
        # version._git pauses before asking a failed read again; here a
        # failed read (no such tag, no remote) is the answer every time.
        p = mock.patch.object(version.time, "sleep", lambda s: None)
        p.start()
        self.addCleanup(p.stop)
        st = self.ws / ".state"
        st.mkdir()
        bugs.configure(write_json=lambda p, d: Path(p).write_text(__import__("json").dumps(d)), state=st)
        version.configure(workspace=self.ws, state=st, write_json=lambda *_a, **_k: None,
                          bugs_mod=bugs, changelog_mod=changelog)
        releasegaps.configure(version_mod=version, bugs_mod=bugs, changelog_mod=changelog)
        self.app = self.ws / "app"
        self.app.mkdir()
        self.git("init", "-q", "-b", "main")
        (self.app / "VERSION").write_text("1.1.0\n")
        (self.app / "app.py").write_text("def total(xs):\n    return sum(xs) + 1  # off by one here\n")
        (self.app / "CHANGELOG.md").write_text("# Changelog\n\n## 1.0.0: 2025-12-01\n\n### Added\n\n- Old (0001111)\n")
        self.commit("start")
        self.git("tag", "-a", "v1.0.0", "-m", "1.0.0")

    def git(self, *a):
        r = subprocess.run(["git", "-C", str(self.app), *a], capture_output=True, text=True,
                           env={**os.environ, **GIT_ENV}, check=True)
        return r.stdout.strip()

    def commit(self, msg):
        self.git("add", "-A")
        self.git("commit", "-q", "-m", msg)
        return self.git("rev-parse", "--short=7", "HEAD")

    def log(self, text, cat):
        changelog.add(self.app, text, sha=self.git("rev-parse", "--short=7", "HEAD"), cat=cat)
        self.commit("changelog")

    def release(self, **k):
        return version.release("app", env=GIT_ENV, push=False, **k)

    def test_dev_takes_unreleased_and_tags_the_commit_after(self):
        self.log("A new thing", "Added")
        n = int(self.git("rev-list", "--count", "HEAD"))
        plan = version.release_plan("app", dev=True)
        self.assertEqual(plan["tag"], f"v1.1.0-dev.{n + 1}")
        r = self.release(dev=True)
        self.assertEqual(r.get("tag"), f"v1.1.0-dev.{n + 1}", r)
        self.assertTrue(r.get("section"))
        text = (self.app / "CHANGELOG.md").read_text()
        self.assertIn(f"## 1.1.0-dev.{n + 1}: ", text)
        self.assertNotIn("## Unreleased", text)
        self.assertEqual(self.git("rev-list", "-n", "1", "--abbrev-commit", "--abbrev=7", r["tag"]), r["sha"])

    def test_a_lines_own_stamp_is_kept_and_heads_is_resolved(self):
        # B702: the cut cited the commit that introduced every line, over
        # the change a line named by hand; HEAD's stamp is still resolved.
        change = self.commit_file("a.py", "a = 1\n", "the change")
        self.git("commit", "-q", "--allow-empty", "-m", "between")
        changelog.add(self.app, f"Named by hand ({change})", cat="Fixed")
        self.commit("changelog by hand")
        self.log("Stamped with HEAD", "Added")
        intro = self.git("rev-parse", "--short=7", "HEAD")
        r = self.release(dev=True)
        text = (self.app / "CHANGELOG.md").read_text()
        self.assertIn(f"- Named by hand ({change})", text, r)
        self.assertIn(f"- Stamped with HEAD ({intro})", text)

    def test_a_line_committed_after_its_change_keeps_naming_the_change(self):
        # B710: the change, then its line in a commit of the changelog's
        # alone, stamped with the change: the cut kept naming the line's
        # commit, the one after.
        change = self.commit_file("b.py", "b = 1\n", "the change")
        self.log("Said after its change", "Fixed")
        # And a line that lands with its change still names that commit.
        (self.app / "c.py").write_text("c = 1\n")
        changelog.add(self.app, "Said with its change", sha=self.git("rev-parse", "--short=7", "HEAD"), cat="Added")
        together = self.commit("change and line")
        self.release(dev=True)
        text = (self.app / "CHANGELOG.md").read_text()
        self.assertIn(f"- Said after its change ({change})", text)
        self.assertIn(f"- Said with its change ({together})", text)

    def commit_file(self, name, body, msg):
        (self.app / name).write_text(body)
        return self.commit(msg)

    def test_any_name_numbered_by_the_commit(self):
        self.log("First", "Added")
        n = int(self.git("rev-list", "--count", "HEAD"))
        self.assertEqual(self.release(pre="rc").get("tag"), f"v1.1.0-rc.{n + 1}")
        self.log("Second", "Added")
        self.assertEqual(self.release(pre="beta").get("tag"), f"v1.1.0-beta.{n + 3}")
        self.assertIn("error", self.release(pre="Not ok"))

    def test_no_lines_no_section_commit(self):
        n = int(self.git("rev-list", "--count", "HEAD"))
        r = self.release(dev=True)
        self.assertEqual(r.get("tag"), f"v1.1.0-dev.{n}")
        self.assertFalse(r.get("section"))

    def test_stable_gathers_the_pre_releases(self):
        self.log("A new thing", "Added")
        self.release(pre="beta")
        self.log("Another", "Changed")
        r = self.release()
        self.assertEqual(r.get("tag"), "v1.1.0", r)
        text = (self.app / "CHANGELOG.md").read_text()
        self.assertIn("## 1.1.0: ", text)
        self.assertNotIn("1.1.0-beta.1", text)
        self.assertIn("- A new thing", text)
        self.assertIn("- Another", text)

    def file_bug(self, title):
        stamp = version.render("app").get("forms", {}).get("semver")
        b = bugs.add("app", title, by="you", severity="low", seen_in=stamp)["bug"]
        return b["id"]

    def test_a_carried_bug_is_owed_a_line(self):
        n = self.file_bug("The total is off by one")
        self.release(pre="rc")
        (self.app / "app.py").write_text("def total(xs):\n    return sum(xs)\n")
        sha = self.commit(f"The total is right (B{n})")
        bugs.set_status("app", n, "fixed", "fixed")
        g = releasegaps.gaps("app")
        self.assertTrue(g["since"].startswith("v1.1.0-rc."), g)
        self.assertEqual([r["id"] for r in g["owed"]], [n])
        self.assertIn("error", version.release_plan("app", pre="rc"))
        changelog.add(self.app, "The total was off by one", sha=sha, cat="Fixed")
        self.commit("changelog")
        self.assertEqual(releasegaps.gaps("app")["owed"], [])
        self.assertNotIn("error", version.release_plan("app", pre="rc"))

    def test_an_answer_or_a_test_only_fix_owes_nothing(self):
        n = self.file_bug("The total is off by one")
        self.release(pre="rc")
        (self.app / "app.py").write_text("def total(xs):\n    return sum(xs)\n")
        self.commit(f"The total is right (B{n})")
        bugs.set_status("app", n, "fixed", "fixed")
        bugs.edit("app", n, notes="[06 Nov] Changelog: no line: nobody could reach it")
        self.assertEqual(releasegaps.gaps("app")["owed"], [])
        m = self.file_bug("A test is flaky")
        (self.app / "test").mkdir()
        (self.app / "test" / "t.py").write_text("ok = True\n")
        self.commit(f"The flaky test waits (B{m})")
        bugs.set_status("app", m, "fixed", "fixed")
        self.assertEqual(releasegaps.gaps("app")["owed"], [])

    def test_a_stamp_on_no_branch_reads_by_its_date(self):
        # B700: a commit a history rewrite left on no branch resolves and is
        # in no tag's history; the bug closed weeks before is not owed.
        self.git("checkout", "-q", "-b", "gone")
        (self.app / "x.py").write_text("x = 1\n")
        lost = self.commit("on a branch that goes")
        self.git("checkout", "-q", "main")
        self.git("branch", "-q", "-D", "gone")
        n = bugs.add("app", "An old one", by="you", severity="low", seen_in=f"1.0.0-dev.1+{lost}")["bug"]["id"]
        bugs.set_status("app", n, "fixed", "fixed")
        with bugs._lock:
            d = bugs.load()
            b = next(x for x in d["projects"]["app"] if x["id"] == n)
            b["fixed_in"], b["closed_at"] = f"1.0.0-dev.1+{lost}", 1000
            bugs.save(d)
        self.release(pre="rc")
        self.assertEqual(releasegaps.gaps("app")["owed"], [])

    def test_a_bug_born_after_the_release_owes_nothing(self):
        self.release(pre="rc")
        (self.app / "new.py").write_text("x = 1\n")
        self.commit("new code")
        n = self.file_bug("The new code is wrong")
        (self.app / "new.py").write_text("x = 2\n")
        self.commit(f"The new code is right (B{n})")
        bugs.set_status("app", n, "fixed", "fixed")
        self.assertEqual(releasegaps.gaps("app")["owed"], [])

    def test_a_long_tracker_asks_git_no_more(self):
        # Hundreds of bugs fixed before the release: the walk reads history
        # once, not once a bug (it ran for minutes on a slow tree).
        for i in range(40):
            n = self.file_bug(f"Old bug {i}")
            bugs.set_status("app", n, "fixed", "fixed")
        self.release(pre="rc")
        asked = []
        run = subprocess.run

        def counted(cmd, *a, **k):
            asked.append(cmd)
            return run(cmd, *a, **k)
        with mock.patch.object(subprocess, "run", counted):
            self.assertEqual(releasegaps.gaps("app")["owed"], [])
        self.assertLess(len(asked), 12, [c[3:5] for c in asked])

    def test_a_bug_another_s_number_starts_is_not_named_by_it(self):
        a = self.file_bug("The total is off by one")
        self.release(pre="rc")
        (self.app / "app.py").write_text("def total(xs):\n    return sum(xs)\n")
        sha = self.commit(f"Two lines\n\nThe total is right: B{a}\nand B{a}7 is another")
        bugs.set_status("app", a, "fixed", "fixed")
        b = next(x for x in bugs.load()["projects"]["app"] if x["id"] == a)
        self.assertEqual(releasegaps.fix_commits("app", b, releasegaps.last_release("app")), [sha])
        self.assertEqual(releasegaps.fix_commits("app", {**b, "id": int(f"{a}7"), "fixed_in": ""},
                                                 releasegaps.last_release("app")), [sha])
        self.assertEqual(releasegaps.fix_commits("app", {**b, "id": int(f"{a}9"), "fixed_in": ""},
                                                 releasegaps.last_release("app")), [])


if __name__ == "__main__":
    unittest.main()
