"""Update checks on one clock: each check's cadence a setting, weekly
unless set, off meaning only Check now; the release's last run stamped so a
restart does not ask again; a node's own version check its config's."""
import json
import os
import shutil
import sys
import tempfile
import unittest
from pathlib import Path

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))
import checks  # noqa: E402
import settings  # noqa: E402
import toolchains  # noqa: E402


class Checks(unittest.TestCase):
    def setUp(self):
        self.tmp = Path(tempfile.mkdtemp())
        self.addCleanup(shutil.rmtree, self.tmp, True)
        saved = (settings.FILE, settings.write_json)
        self.addCleanup(lambda: (setattr(settings, "FILE", saved[0]), setattr(settings, "write_json", saved[1])))
        settings.configure(write_json=lambda p, d: Path(p).write_text(json.dumps(d)), state=self.tmp)
        self.ran = []
        # ...and checks' own, which a later module in this process read with
        # this test's directory long gone.
        kept = (checks.STATE, checks.settings)
        self.addCleanup(lambda: (setattr(checks, "STATE", kept[0]), setattr(checks, "settings", kept[1])))
        checks.configure(state=self.tmp, settings_mod=settings, last={"images": lambda: 1000},
                         run={"images": lambda: self.ran.append("images"), "release": lambda: None})

    def test_weekly_unless_set_and_off_is_only_check_now(self):
        self.assertEqual(checks.cadence("images"), "weekly")
        self.assertTrue(checks.due("images", 0, now=7 * 86400))
        self.assertFalse(checks.due("images", 1, now=7 * 86400))
        self.assertTrue(settings.set_many({"check_images": "daily"}).get("ok"))
        self.assertTrue(checks.due("images", 1, now=86401))
        settings.set_many({"check_images": "off"})
        self.assertIsNone(checks.every("images"))
        self.assertFalse(checks.due("images", 0, now=10 ** 10))
        self.assertIn("error", settings.set_many({"check_images": "hourly"}))

    def test_the_release_is_stamped_and_the_view_says_when_each_last_ran(self):
        self.assertEqual(checks.stamped("release"), 0)
        checks.stamp("release", 1234)
        self.assertEqual(checks.stamped("release"), 1234)
        v = checks.view()
        self.assertEqual(v["images"], {"cadence": "weekly", "at": 1000})
        self.assertEqual(v["release"]["at"], 1234)
        self.assertNotIn("nginx", v, "a check this install has not is not drawn")

    def test_check_now_runs_it_and_refuses_one_not_here(self):
        import time
        self.assertEqual(checks.run_now("images"), {"ok": True})
        for _ in range(50):
            if self.ran:
                break
            time.sleep(0.02)
        self.assertEqual(self.ran, ["images"])
        self.assertIn("error", checks.run_now("nginx"))

    def test_a_nodes_own_cadence_is_its_config(self):
        self.assertEqual(toolchains.node_check_every({"config": {}}), 7 * 86400)
        self.assertEqual(toolchains.node_check_every({"config": {"check_versions": "daily"}}), 86400)
        self.assertIsNone(toolchains.node_check_every({"config": {"check_versions": "off"}}))



class Guarded(unittest.TestCase):
    """A fetch that raises what its own except does not name leaves no check
    in flight for good: the next ask fetches again."""

    def test_a_raising_fetch_is_its_error_and_the_next_ask_fetches(self):
        import threading
        lock, rec, asked = threading.Lock(), {"checking": False}, []

        def bad():
            asked.append(1)
            raise TypeError("'NoneType' object is not subscriptable")
        got = checks.guarded(lock, lambda: rec, bad)
        self.assertIn("the check failed: 'NoneType'", got["error"])
        self.assertFalse(rec["checking"])
        checks.guarded(lock, lambda: rec, lambda: (asked.append(2) or ({"latest": "1.0"}, "")))
        self.assertEqual(asked, [1, 2])
        self.assertEqual((rec["latest"], rec["error"]), ("1.0", ""))

    def test_a_keep_that_fails_still_brings_the_flag_down(self):
        import threading
        lock, flag = threading.Lock(), {"checking": False}

        def keep(_r):
            raise OSError("disk full")
        with self.assertRaises(OSError):
            checks.guarded(lock, dict, lambda: ({}, ""), keep=keep, flag=flag)
        self.assertFalse(flag["checking"])

if __name__ == "__main__":
    unittest.main()
