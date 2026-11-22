"""What each of a release's files is for (R255): a repository's Releases
settings (the gate and the described files), the table built from the files a
release holds, put over its notes once, and a repository's own
docs/release-notes/downloads.md standing in for it."""
import os
import shutil
import sys
import tempfile
import unittest
from pathlib import Path

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))
import forgerelease  # noqa: E402
import prefs  # noqa: E402
import statefile  # noqa: E402


class Settings(unittest.TestCase):
    def setUp(self):
        self.state = tempfile.mkdtemp()
        self.addCleanup(shutil.rmtree, self.state, True)
        os.makedirs(os.path.join(self.state, "ws", "alpha"))
        prefs.configure(write_json=statefile.write_json, state=self.state)

    def test_defaults_and_what_is_kept(self):
        p = prefs.get("alpha")
        self.assertEqual((p["release_gate"], p["files_table"], p["files"]), ("refuse", True, []))
        self.assertIn("error", prefs.set_prefs("alpha", release_gate="maybe"))
        self.assertNotIn("error", prefs.set_prefs("alpha", release_gate="warn", files_table=False,
                                                  files=[{"name": "app-@VER@.apk", "what": "The Android app"},
                                                         {"name": "app-@VER@.apk", "what": "twice"}, {"name": " ", "what": "no name"}]))
        p = prefs.get("alpha")
        self.assertEqual((p["release_gate"], p["files_table"]), ("warn", False))
        self.assertEqual(p["files"], [{"name": "app-@VER@.apk", "what": "The Android app"}], "a name once, and none empty")
        prefs.set_prefs("alpha", release_gate="refuse", files_table=True, files=[])
        self.assertNotIn("release_gate", (prefs._load()["projects"].get("alpha") or {}), "a default is not stored")


class Table(unittest.TestCase):
    def setUp(self):
        self.ws = Path(tempfile.mkdtemp())
        self.addCleanup(shutil.rmtree, self.ws, True)
        (self.ws / "alpha").mkdir()
        self.was = (forgerelease.WORKSPACE if hasattr(forgerelease, "WORKSPACE") else None, forgerelease.files_setting)
        forgerelease.WORKSPACE = self.ws
        self.rows = [{"name": "app-@VER@.apk", "what": "The Android app"}, {"name": "server-*.tar.gz", "what": "The server | for Linux"}]
        forgerelease.files_setting = lambda p: (True, self.rows)

    def tearDown(self):
        forgerelease.WORKSPACE, forgerelease.files_setting = self.was

    def test_a_row_for_each_file_the_release_holds(self):
        names = ["app-1.2.0.apk", "server-1.2.0.tar.gz", "notes.pdf", "app-1.2.0.apk.sha256", "server-1.2.0.tar.gz.sha256"]
        t = forgerelease.files_table("alpha", names, tag="v1.2.0")
        self.assertEqual(t.splitlines(), [
            "### Which download is for what", "", "| File | What it is for |", "|---|---|",
            "| `app-1.2.0.apk` | The Android app |",
            "| `server-1.2.0.tar.gz` | The server \\| for Linux |",
            "| `notes.pdf` |  |",
            "| `*.sha256` | The checksum or signature of the file of the same name, to check a download; nothing to install. |"])
        self.assertEqual(forgerelease.undescribed("alpha", names, tag="v1.2.0"), ["notes.pdf"])

    def test_put_over_the_notes_once_and_not_when_switched_off(self):
        once = forgerelease.with_files_table("alpha", "### Fixed\n\n- A thing", ["app-1.2.0.apk"], tag="v1.2.0")
        self.assertTrue(once.startswith("### Which download is for what"))
        self.assertTrue(once.endswith("- A thing"))
        self.assertEqual(forgerelease.with_files_table("alpha", once, ["app-1.2.0.apk"], tag="v1.2.0"), once)
        forgerelease.files_setting = lambda p: (False, self.rows)
        self.assertEqual(forgerelease.with_files_table("alpha", "notes", ["app-1.2.0.apk"], tag="v1.2.0"), "notes")
        self.assertEqual(forgerelease.undescribed("alpha", ["notes.pdf"], tag="v1.2.0"), [])

    def test_the_repositorys_own_file_stands_in(self):
        own = self.ws / "alpha" / "docs" / "release-notes"
        own.mkdir(parents=True)
        (own / "downloads.md").write_text("### Which download is for what\n\n`app-@VER@.apk` from @REPO@ at @TAG@\n")
        t = forgerelease.files_table("alpha", ["anything"], tag="v1.2.0", repo="o/r")
        self.assertEqual(t, "### Which download is for what\n\n`app-1.2.0.apk` from o/r at v1.2.0")
        self.assertEqual(forgerelease.undescribed("alpha", ["anything"], tag="v1.2.0"), [])

    def test_no_files_no_table(self):
        self.assertEqual(forgerelease.files_table("alpha", [], tag="v1.2.0"), "")


if __name__ == "__main__":
    unittest.main()
