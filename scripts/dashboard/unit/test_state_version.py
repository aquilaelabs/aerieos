"""/config's state version (R79): a fresh /config is stamped, one newer
than the build or older than it migrates from is refused in one sentence,
one about to move is copied first (the newest three kept, what grows left
out), and the numbered migrations past the stamp run once, in order, each
stamped as it lands. And migration 0001, the one-off migrators that ran at
every start before the stamp, folded into one that runs once."""
import io
import json
import os
import shutil
import sqlite3
import sys
import tempfile
import unittest
from contextlib import redirect_stdout
from pathlib import Path
from unittest import mock

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))
import stateversion as sv  # noqa: E402


def write_json(p, d, mode=0o644):
    with open(p, "w") as f:
        json.dump(d, f)


class Gate(unittest.TestCase):
    def setUp(self):
        self.state = Path(tempfile.mkdtemp())
        self.addCleanup(shutil.rmtree, self.state, True)
        self.cur = sv.current()

    def stamp(self, n, by="9.9.9"):
        (self.state / "state.json").write_text(json.dumps({"state": n, "by": by}))

    def lived_in(self):
        (self.state / "users.json").write_text('{"users": {}}')
        (self.state / "logs").mkdir()
        (self.state / "logs" / "dashboard.log").write_text("big\n")
        (self.state / "wiki" / "alpha").mkdir(parents=True)
        (self.state / "wiki" / "alpha" / "Home.md").write_text("# Home\n")
        (self.state / "roadmap.json.lock").write_text("")
        db = sqlite3.connect(self.state / "builderbot.db")
        db.execute("PRAGMA journal_mode=WAL")
        db.execute("CREATE TABLE t (x)")
        db.execute("INSERT INTO t VALUES (7)")
        db.commit()
        return db

    def test_this_build_writes_its_newest_migration(self):
        self.assertGreaterEqual(self.cur, 1, "0.5.0 is state 1")
        self.assertEqual(self.cur, sv.migrations()[-1][0])
        self.assertLessEqual(sv.SUPPORTED_FROM, self.cur)

    def test_a_fresh_config_is_stamped_current_with_nothing_copied(self):
        self.assertEqual(sv.gate(self.state, "0.5.0"), self.cur)
        self.assertEqual(sv.read(self.state), (self.cur, "0.5.0"))
        self.assertFalse((self.state / "backups").exists())

    def test_a_config_a_step_behind_is_copied_before_it_moves(self):
        db = self.lived_in()
        self.addCleanup(db.close)
        self.stamp(self.cur - 1, "0.8.0")
        with mock.patch.object(sv, "SUPPORTED_FROM", self.cur - 1), redirect_stdout(io.StringIO()):
            self.assertEqual(sv.gate(self.state, "0.9.0"), self.cur - 1)
        dest = self.state / "backups" / "before-0.9.0"
        self.assertTrue((dest / "users.json").is_file())
        self.assertTrue((dest / "wiki" / "alpha" / "Home.md").is_file(), "the wiki is state")
        self.assertFalse((dest / "logs").exists(), "logs are not")
        self.assertFalse((dest / "roadmap.json.lock").exists())
        self.assertFalse((dest / "backups").exists())
        got = sqlite3.connect(dest / "builderbot.db").execute("SELECT x FROM t").fetchall()
        self.assertEqual(got, [(7,)], "the database copied whole, its WAL folded in")
        self.assertEqual(sv.read(self.state), (self.cur - 1, "0.8.0"), "the stamp moves when the migrations have run")

    def test_a_second_try_keeps_the_first_copy(self):
        self.lived_in().close()
        self.stamp(self.cur - 1, "0.8.0")
        with mock.patch.object(sv, "SUPPORTED_FROM", self.cur - 1), redirect_stdout(io.StringIO()):
            sv.gate(self.state, "0.9.0")
            (self.state / "users.json").write_text('{"half": "migrated"}')
            sv.gate(self.state, "0.9.0")
        self.assertEqual((self.state / "backups" / "before-0.9.0" / "users.json").read_text(), '{"users": {}}')

    def test_a_copy_put_back_is_used_once(self):
        # The copy goes with what it replaced, so a later start of that
        # version copies afresh rather than reusing the first try's.
        (self.state / "users.json").write_text('{"v": "old"}')
        sv.backup(self.state, "0.9.0")
        (self.state / "users.json").write_text('{"v": "migrated"}')
        aside = sv.restore(self.state, "0.9.0")
        self.assertEqual((self.state / "users.json").read_text(), '{"v": "old"}')
        self.assertEqual((Path(aside) / "users.json").read_text(), '{"v": "migrated"}', "what it held, kept")
        self.assertFalse((self.state / "backups" / "before-0.9.0").exists())
        self.assertTrue((Path(aside) / "used-before-0.9.0").is_dir())
        (self.state / "users.json").write_text('{"v": "a week on"}')
        sv.backup(self.state, "0.9.0")
        self.assertEqual((self.state / "backups" / "before-0.9.0" / "users.json").read_text(), '{"v": "a week on"}')

    def test_a_restore_that_fails_leaves_the_state_as_it_was(self):
        (self.state / "users.json").write_text('{"v": "old"}')
        (self.state / "roadmap.json").write_text('{"r": "old"}')
        sv.backup(self.state, "0.9.0")
        (self.state / "users.json").write_text('{"v": "migrated"}')
        (self.state / "roadmap.json").write_text('{"r": "migrated"}')
        real, calls = os.replace, []

        def flaky(a, b):
            calls.append(a)
            if len(calls) == 4:
                raise OSError(28, "No space left on device")
            return real(a, b)
        with mock.patch.object(sv.os, "replace", flaky), self.assertRaises(OSError):
            sv.restore(self.state, "0.9.0")
        self.assertEqual((self.state / "users.json").read_text(), '{"v": "migrated"}')
        self.assertEqual((self.state / "roadmap.json").read_text(), '{"r": "migrated"}')
        self.assertTrue((self.state / "backups" / "before-0.9.0" / "users.json").is_file(), "the copy is still there to try again")

    def test_the_newest_three_copies_are_kept(self):
        (self.state / "users.json").write_text("{}")
        for i, v in enumerate(("0.5.0", "0.5.1", "0.5.2", "0.6.0")):
            sv.backup(self.state, v)
            os.utime(self.state / "backups" / f"before-{v}", (1000 + i, 1000 + i))
        self.assertEqual(sorted(p.name for p in (self.state / "backups").iterdir()),
                         ["before-0.5.1", "before-0.5.2", "before-0.6.0"])

    def test_a_newer_config_is_refused_naming_the_copy_to_restore(self):
        (self.state / "users.json").write_text("{}")
        sv.backup(self.state, "0.9.0")
        self.stamp(self.cur + 1, "0.9.0")
        why = sv.refusal(self.state, "0.5.0")
        self.assertIn("Downgrades are not supported", why)
        self.assertIn("0.9.0", why)
        self.assertIn(str(self.state / "backups" / "before-0.9.0"), why)
        self.assertNotIn("—", why)
        err = io.StringIO()
        with mock.patch.object(sys, "stderr", err), self.assertRaises(SystemExit) as cm:
            sv.gate(self.state, "0.5.0")
        self.assertEqual(cm.exception.code, 78)
        self.assertIn("will not start", err.getvalue())
        self.assertEqual(sv.read(self.state)[0], self.cur + 1, "nothing written")

    def test_nothing_older_than_the_floor_starts_and_it_says_to_install_fresh(self):
        # The operator, 1 Nov: AerieOS starts here, and 0.6, 0.7 and 0.8 have no path.
        self.stamp(sv.SUPPORTED_FROM, "0.9.0")
        self.assertEqual(sv.refusal(self.state, "0.9.0"), "", "the floor is what the controller moving over holds")
        for n, by in ((sv.SUPPORTED_FROM - 1, "0.8.2"), (2, "0.6.0"), (0, "")):
            self.stamp(n, by)
            why = sv.refusal(self.state, "0.9.0")
            self.assertIn("install fresh", why)
            self.assertIn("install.md#upgrading", why)
        (self.state / "state.json").unlink()
        self.lived_in().close()
        self.assertIn("install fresh", sv.refusal(self.state, "0.9.0"), "a lived-in /config from before the stamp is state 0")
        with mock.patch.object(sv, "SUPPORTED_FROM", 0):
            self.assertEqual(sv.refusal(self.state, "0.5.0"), "", "a build with no floor migrates from 0")

    def test_an_unreadable_stamp_is_refused_rather_than_guessed(self):
        (self.state / "state.json").write_text("{nope")
        self.assertIn("cannot be read", sv.refusal(self.state, "0.5.0"))
        (self.state / "state.json").write_text('{"state": "1"}')
        self.assertIn("no state number", sv.refusal(self.state, "0.5.0"))

    def test_the_entrypoint_check_says_the_same(self):
        self.stamp(self.cur + 5)
        err = io.StringIO()
        with mock.patch.object(sys, "stderr", err):
            self.assertEqual(sv.main(["check", str(self.state)]), 78)
        self.assertIn("Downgrades are not supported", err.getvalue())
        self.stamp(self.cur)
        self.assertEqual(sv.main(["check", str(self.state)]), 0)


class ClaimFromAShell(unittest.TestCase):
    """B436: the owner made from a shell on a new install, before its first
    start, leaves a stamped store, which that start takes as its own."""
    def test_a_claim_on_a_fresh_store_stamps_it(self):
        import subprocess
        here = Path(__file__).resolve().parent.parent
        with tempfile.TemporaryDirectory() as d:
            env = dict(os.environ, DASHBOARD_STATE=d, BB_USERS_PW="longenough1")
            r = subprocess.run([sys.executable, str(here.parent / "lib" / "users-verbs.py"), "claim", str(here / "users.py"), "owner1"],
                               env=env, capture_output=True, text=True, check=False)
            self.assertEqual(r.returncode, 0, r.stderr)
            self.assertEqual(sv.read(d)[0], sv.current())
            self.assertEqual(sv.refusal(d, "0.9.0"), "")


class Migrate(unittest.TestCase):
    """The runner, over a directory of migrations of the test's own."""
    def setUp(self):
        self.state = Path(tempfile.mkdtemp())
        self.mig = Path(tempfile.mkdtemp())
        self.addCleanup(shutil.rmtree, self.state, True)
        self.addCleanup(shutil.rmtree, self.mig, True)
        for n, body in ((1, "ctx['ran'].append(1)"), (2, "ctx['ran'].append(2)"),
                        (3, "ctx['ran'].append(3)\n    if ctx.get('fail'): raise ValueError('no')")):
            (self.mig / f"{n:04d}_m.py").write_text(f"def run(ctx):\n    {body}\n")
        patch = mock.patch.object(sv, "MIGRATIONS", self.mig)
        patch.start()
        self.addCleanup(patch.stop)
        # The runner's own behavior, below any floor a build sets.
        floor = mock.patch.object(sv, "SUPPORTED_FROM", 0)
        floor.start()
        self.addCleanup(floor.stop)
        (self.state / "users.json").write_text("{}")

    def test_each_runs_once_in_order_and_is_stamped(self):
        ctx = {"ran": []}
        with redirect_stdout(io.StringIO()):
            self.assertEqual(sv.migrate(self.state, ctx, "0.6.0"), [1, 2, 3])
            self.assertEqual(sv.migrate(self.state, ctx, "0.6.0"), [])
        self.assertEqual(ctx["ran"], [1, 2, 3])
        self.assertEqual(sv.read(self.state), (3, "0.6.0"))

    def listing(self):
        """Everything in the state but what a copy leaves where it is."""
        return {str(p.relative_to(self.state)): p.read_bytes() for p in sorted(self.state.rglob("*"))
                if p.is_file() and not sv._skipped(p.relative_to(self.state).parts[0])}

    def test_a_failure_puts_the_state_back_and_stops_the_start(self):
        # The operator, 13 Nov: it went on, the new build running on state
        # half changed, with one line in the log.
        (self.state / "state.json").write_text('{"state": 1, "by": "0.5.0"}')
        (self.state / "roadmap.json").write_text('{"items": [1, 2, 3]}')
        before = self.listing()
        ctx = {"ran": [], "fail": True}
        err = io.StringIO()
        with redirect_stdout(io.StringIO()), mock.patch.object(sv.sys, "stderr", err):
            sv.gate(self.state, "0.6.0")
            # What a migration that landed and one that failed half-way both left.
            (self.state / "roadmap.json").write_text('{"items": "half changed"}')
            with self.assertRaises(SystemExit) as e:
                sv.migrate(self.state, ctx)
        self.assertEqual(e.exception.code, 78)
        self.assertEqual(ctx["ran"], [2, 3], "2 landed, 3 failed")
        self.assertEqual(self.listing(), before, "the stamp and every file as before the update")
        self.assertEqual(sv.read(self.state), (1, "0.5.0"))
        note = (self.state / sv.FAILED_FILE).read_text()
        self.assertTrue(note.startswith("build 0.6.0\n"))
        self.assertIn("its migration 0003_m.py failed (ValueError: no)", note)
        self.assertIn("the 1 migration(s) before it were undone with it", note)
        self.assertIn("AerieOS 0.6.0 will not start", err.getvalue())
        self.assertIn("Start the release this /config ran before", err.getvalue())
        # What the failed start left is kept aside, never deleted.
        aside = [d for d in (self.state / "backups").iterdir() if d.name.startswith("rolled-back-")]
        self.assertEqual(len(aside), 1)
        self.assertEqual((aside[0] / "roadmap.json").read_text(), '{"items": "half changed"}')

        # The same build again: said again, nothing copied, nothing run.
        folders = sorted(p.name for p in (self.state / "backups").iterdir())
        err = io.StringIO()
        with mock.patch.object(sv.sys, "stderr", err), self.assertRaises(SystemExit) as e:
            sv.gate(self.state, "0.6.0")
        self.assertEqual(e.exception.code, 78)
        self.assertIn("It is not tried again by itself", err.getvalue())
        self.assertEqual(sorted(p.name for p in (self.state / "backups").iterdir()), folders)
        self.assertEqual(ctx["ran"], [2, 3])
        # ...and the boot's own question, and the supervisor's before it
        # starts the dashboard again, are answered the same: the container
        # stops with the sentence where it kept starting a server that ended.
        self.assertIn("It is not tried again by itself", sv.wont_start(self.state, "0.6.0"))
        self.assertEqual(sv.wont_start(self.state, "0.6.1"), "")
        with mock.patch.object(sv, "build_version", lambda: "0.6.0"), mock.patch.object(sv.sys, "stderr", io.StringIO()):
            self.assertEqual(sv.main(["check", str(self.state)]), 78)
        with mock.patch.object(sv, "build_version", lambda: "0.6.1"):
            self.assertEqual(sv.main(["check", str(self.state)]), 0)
        with open(os.path.join(os.path.dirname(os.path.abspath(sv.__file__)), "..", "supervisor.sh"), encoding="utf-8") as f:
            sup = f.read()
        self.assertLess(sup.index("stateversion.py check"), sup.index("starting it again"),
                        "the supervisor asks before it starts the dashboard again")

        # Another build is not held by it, and one that migrates clean takes the note away.
        ctx = {"ran": []}
        with redirect_stdout(io.StringIO()):
            sv.gate(self.state, "0.6.1")
            self.assertEqual(sv.migrate(self.state, ctx), [2, 3])
        self.assertFalse((self.state / sv.FAILED_FILE).exists())
        self.assertEqual(sv.read(self.state)[0], 3)

    def test_the_cause_fixed_and_the_note_removed_it_is_tried_again(self):
        (self.state / "state.json").write_text('{"state": 2, "by": "0.5.0"}')
        ctx = {"ran": [], "fail": True}
        with redirect_stdout(io.StringIO()), mock.patch.object(sv.sys, "stderr", io.StringIO()):
            sv.gate(self.state, "0.6.0")
            with self.assertRaises(SystemExit):
                sv.migrate(self.state, ctx)
        (self.state / sv.FAILED_FILE).unlink()
        ctx = {"ran": []}
        with redirect_stdout(io.StringIO()):
            sv.gate(self.state, "0.6.0")
            self.assertEqual(sv.migrate(self.state, ctx), [3])

    def test_a_build_of_the_same_name_that_migrates_again_takes_a_copy_of_its_own(self):
        # A dev build made twice from one commit, the second with a migration
        # more, which fails: what comes back is the state from just before
        # it, never the copy the first one took before its own migration.
        (self.state / "state.json").write_text('{"state": 2, "by": "0.5.0"}')
        ctx = {"ran": []}
        with redirect_stdout(io.StringIO()):
            sv.gate(self.state, "0.6.0")
            self.assertEqual(sv.migrate(self.state, ctx), [3])
        first = self.state / "backups" / "before-0.6.0"
        self.assertTrue((first / sv.LANDED).exists(), "the copy is marked: its update landed")
        (self.state / "roadmap.json").write_text('{"items": "written since the first update"}')
        (self.state / "state.json").write_text('{"state": 2, "by": "0.6.0"}')      # as if one more were to run
        ctx = {"ran": [], "fail": True}
        with redirect_stdout(io.StringIO()), mock.patch.object(sv.sys, "stderr", io.StringIO()):
            sv.gate(self.state, "0.6.0")
            with self.assertRaises(SystemExit):
                sv.migrate(self.state, ctx)
        self.assertEqual((self.state / "roadmap.json").read_text(), '{"items": "written since the first update"}')
        self.assertFalse((self.state / sv.LANDED).exists(), "the mark is the copy's, never the state's")
        kept = [d.name for d in (self.state / "backups").iterdir() if d.name.startswith("before-0.6.0~")]
        self.assertEqual(len(kept), 1, "and the first copy is still there, under a name of its own")

    def test_with_no_copy_to_put_back_it_goes_on_and_says_so(self):
        # Never the case after gate(), which takes the copy or holds every
        # migration: kept for a caller that runs them without it.
        (self.state / "state.json").write_text('{"state": 1}')
        ctx = {"ran": [], "fail": True}
        err = io.StringIO()
        with redirect_stdout(io.StringIO()), mock.patch.object(sv.sys, "stderr", err), \
                mock.patch.dict(sv._COPY, {"version": ""}):
            self.assertEqual(sv.migrate(self.state, ctx, "0.6.0"), [2])
        self.assertIn("could not be put back as it was", err.getvalue())
        self.assertEqual(sv.read(self.state)[0], 2)
        self.assertIn("0003_m.py failed", (self.state / sv.HELD_FILE).read_text())

    def test_no_copy_no_migration(self):
        with mock.patch.object(sv, "backup", side_effect=OSError("disk full")), \
                mock.patch.object(sv, "HELD", ""), redirect_stdout(io.StringIO()):
            sv.gate(self.state, "0.6.0")
            self.assertIn("disk full", sv.HELD)
            self.assertEqual(sv.migrate(self.state, {"ran": []}), [])
        self.assertEqual(sv.read(self.state), (None, ""))
        # B109: said where aerie doctor reads it, and cleared once nothing is held.
        self.assertIn("disk full", (self.state / sv.HELD_FILE).read_text())
        with mock.patch.object(sv, "HELD", ""), redirect_stdout(io.StringIO()):
            sv.gate(self.state, "0.6.0")
        self.assertFalse((self.state / sv.HELD_FILE).exists())

    @unittest.skipIf(os.geteuid() == 0, "root reads everything")
    def test_what_it_cannot_read_does_not_hold_the_upgrade(self):
        # B109: the root-only runner-tokens volume stopped every upgrade.
        (self.state / "users.json").write_text('{"users": {}}')
        (self.state / "wiki" / "alpha").mkdir(parents=True)
        rt = self.state / "runner-tokens"
        rt.mkdir()
        (rt / "n_1").write_text("secret")
        rt.chmod(0)
        secret = self.state / "wiki" / "alpha" / "hidden.md"
        secret.write_text("no")
        secret.chmod(0)
        self.addCleanup(rt.chmod, 0o700)
        with redirect_stdout(io.StringIO()) as out:
            sv.gate(self.state, "0.5.0")
        dest = self.state / "backups" / "before-0.5.0"
        self.assertTrue((dest / "users.json").is_file(), out.getvalue())
        self.assertFalse((dest / "runner-tokens").exists(), "its own volume, not copied")
        self.assertIn("wiki/alpha/hidden.md", (dest / "NOT-COPIED.txt").read_text())
        self.assertEqual(sv.HELD, "")


class Release(unittest.TestCase):
    """aerie version release, and the Artifacts view's Release, refuse a
    version with no snapshot where the tree keeps them."""
    def test_a_tree_that_keeps_snapshots_needs_this_ones(self):
        import version
        tree = Path(tempfile.mkdtemp())
        self.addCleanup(shutil.rmtree, tree, True)
        with mock.patch.object(version, "root", lambda _p: tree):
            self.assertEqual(version.no_upgrade_snapshot("p", "", "0.5.0"), "", "a tree that keeps none")
            snaps = tree / version.UPGRADE_SNAPSHOTS
            (snaps / "0.5.0").mkdir(parents=True)
            self.assertIn("tools/upgrade-snapshot.py", version.no_upgrade_snapshot("p", "", "0.5.0"))
            (snaps / "0.5.0" / "manifest.json").write_text("{}")
            self.assertEqual(version.no_upgrade_snapshot("p", "", "0.5.0"), "")
            self.assertIn("0.5.1", version.no_upgrade_snapshot("p", "", "0.5.1"))
            self.assertEqual(version.no_upgrade_snapshot("p", "android", "0.5.1"), "", "a component is its own")

    def test_and_one_taken_at_the_releases_own_state(self):
        import version
        tree = Path(tempfile.mkdtemp())
        self.addCleanup(shutil.rmtree, tree, True)
        (tree / "scripts" / "dashboard" / "statemigrations").mkdir(parents=True)
        for n in (19, 20, 21):
            (tree / "scripts" / "dashboard" / "statemigrations" / f"{n:04d}_m.py").write_text("def run(ctx): pass\n")
        snap = tree / version.UPGRADE_SNAPSHOTS / "0.9.0"
        snap.mkdir(parents=True)
        with mock.patch.object(version, "root", lambda _p: tree):
            (snap / "manifest.json").write_text('{"state": 19, "version": "0.9.0"}')
            said = version.no_upgrade_snapshot("p", "", "0.9.0")
            self.assertIn("was taken at state 19 and this tree is at 21", said)
            self.assertIn("tools/upgrade-snapshot.py again", said)
            (snap / "manifest.json").write_text('{"state": 21, "version": "0.9.0"}')
            self.assertEqual(version.no_upgrade_snapshot("p", "", "0.9.0"), "")
            # A manifest from before it carried its state is taken as it was.
            (snap / "manifest.json").write_text("{}")
            self.assertEqual(version.no_upgrade_snapshot("p", "", "0.9.0"), "")

    def test_a_snapshot_taken_again_keeps_the_older_one_beside_it(self):
        import importlib.util
        import stateversion
        spec = importlib.util.spec_from_file_location(
            "upgrade_snapshot", Path(__file__).resolve().parents[3] / "tools" / "upgrade-snapshot.py")
        tool = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(tool)
        top = Path(tempfile.mkdtemp())
        self.addCleanup(shutil.rmtree, top, True)
        out = top / "0.9.0"
        now = stateversion.current()
        no, yes = (lambda v: False), (lambda v: True)
        self.assertIsNone(tool.older_state(out, "0.9.0", no), "none there")
        out.mkdir()
        (out / "manifest.json").write_text(json.dumps({"state": now, "version": "0.9.0"}))
        self.assertIsNone(tool.older_state(out, "0.9.0", no), "taken at this tree's state: --force is still asked")
        (out / "manifest.json").write_text(json.dumps({"state": now - 1, "version": "0.9.0"}))
        self.assertIsNone(tool.older_state(out, "0.9.0", yes), "a release that shipped is never taken again")
        self.assertEqual(tool.older_state(out, "0.9.0", no), now - 1)
        (out / "config.tar.gz").write_text("the older one")
        dest = tool.keep_older(out, "0.9.0", now - 1)
        self.assertEqual(dest.name, f"0.9.0-state{now - 1}")
        self.assertEqual((dest / "config.tar.gz").read_text(), "the older one")
        self.assertFalse(out.exists())
        # Never over one kept before.
        out.mkdir()
        with self.assertRaises(SystemExit):
            tool.keep_older(out, "0.9.0", now - 1)


if __name__ == "__main__":
    unittest.main()
