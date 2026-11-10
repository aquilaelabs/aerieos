"""What was pressed behind a running job is not dropped without a word by a
restart: the controller's own waiting installs are kept and taken up again,
and a space job that waited says it was not started, its claim taken back."""
import json
import os
import sys
import tempfile
import unittest
from pathlib import Path

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))
import projects  # noqa: E402
import statefile  # noqa: E402
import toolchains  # noqa: E402


class Installs(unittest.TestCase):
    def setUp(self):
        self.d = Path(tempfile.mkdtemp())
        saved = (toolchains.STATE, toolchains.write_json, toolchains._tc_waiter)
        self.addCleanup(lambda: (setattr(toolchains, "STATE", saved[0]), setattr(toolchains, "write_json", saved[1]),
                                 setattr(toolchains, "_tc_waiter", saved[2]), toolchains._tc_next.clear(),
                                 toolchains._tc_waiting.update(thread=None)))
        toolchains.STATE, toolchains.write_json = self.d, statefile.write_json
        toolchains._tc_waiter = lambda: None
        toolchains._tc_next.clear()
        toolchains._tc_waiting.update(thread=None)

    def test_kept_while_they_wait_and_taken_up_again(self):
        name = toolchains.TOOLCHAINS[0]["name"]
        with toolchains._tc_lock:
            toolchains._tc_next.append(("install", [name]))
            toolchains._tc_next_keep()
        self.assertEqual(json.loads((self.d / "toolchain-queue.json").read_text())["waiting"],
                         [{"action": "install", "names": [name]}])
        toolchains._tc_next.clear()
        toolchains._tc_next_load()
        self.assertEqual(toolchains._tc_next, [("install", [name])])
        with toolchains._tc_lock:
            toolchains._tc_next.clear()
            toolchains._tc_next_keep()
        self.assertFalse((self.d / "toolchain-queue.json").exists(), "nothing waiting, no file")

    def test_a_name_the_catalog_does_not_hold_is_not_taken_up(self):
        (self.d / "toolchain-queue.json").write_text(json.dumps({"waiting": [{"action": "install", "names": ["; rm -rf /"]},
                                                                             {"action": "sudo", "names": ["x"]}]}))
        toolchains._tc_next_load()
        self.assertEqual(toolchains._tc_next, [])


class SpaceJobs(unittest.TestCase):
    def test_a_waiting_clone_is_said_and_its_empty_folder_freed(self):
        d = Path(tempfile.mkdtemp())
        ws = d / "ws"
        (ws / "queued").mkdir(parents=True)
        (ws / "begun").mkdir()
        (ws / "begun" / "file").write_text("x")
        saved = (projects.STATE, projects.WORKSPACE, projects._unmade, projects.forget_token, list(projects._earlier))
        self.addCleanup(lambda: (setattr(projects, "STATE", saved[0]), setattr(projects, "WORKSPACE", saved[1]),
                                 setattr(projects, "_unmade", saved[2]), setattr(projects, "forget_token", saved[3]),
                                 projects._earlier.clear(), projects._earlier.extend(saved[4])))
        unmade = []
        projects.STATE, projects.WORKSPACE = d, ws
        projects._unmade, projects.forget_token = unmade.append, lambda n: None
        projects._earlier.clear()
        (d / "space-jobs-waiting.json").write_text(json.dumps({"waiting": [{"kind": "clone", "name": "queued"},
                                                                           {"kind": "clone", "name": "begun"}]}))
        self.assertEqual(projects.dropped_at_restart(), ["queued", "begun"])
        self.assertFalse((ws / "queued").exists(), "claimed and never reached: freed")
        self.assertTrue((ws / "begun" / "file").exists(), "a folder with anything in it is left")
        self.assertEqual(unmade, ["queued"])
        self.assertIn("press it again", projects._earlier[0]["error"])
        self.assertFalse((d / "space-jobs-waiting.json").exists())
        self.assertEqual(projects.dropped_at_restart(), [], "said once")


if __name__ == "__main__":
    unittest.main()
