"""Migration 0040 (R205): an account made before 7 Oct that never pinned
read every space (or the old "*" default) as pinned; it is given that set as
its own list once, so no entry means nothing pinned for everybody. Each
account's pinned spaces read as projects.load_project_pins with
users.starts_unpinned read them on 27 Nov: FROZEN, with and without "*"."""
import copy
import importlib
import json
import os
import shutil
import sys
import tempfile
import unittest
from pathlib import Path

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))
import projects  # noqa: E402

PROJECTS = ["alpha", "beta", "gamma"]
USERS = json.loads(r'''{"users": {"old_never": {"uid": "u_old1", "role": "owner"}, "old_pinned": {"uid": "u_old2", "role": "member"}, "fresh_never": {"uid": "u_new1", "role": "member", "pins_empty": true}, "fresh_pinned": {"uid": "u_new2", "role": "member", "pins_empty": true}}}''')
CASES = json.loads(r'''{"star": {"*": ["beta"], "u_old2": ["gamma"], "u_new2": ["alpha"]}, "nostar": {"u_old2": ["gamma"], "u_new2": ["alpha"]}}''')
# Each account's pinned spaces on 27 Nov, with the old shapes' readers in them.
FROZEN = json.loads(r'''{"star": {"old_never": ["beta"], "old_pinned": ["gamma"], "fresh_never": [], "fresh_pinned": ["alpha"]}, "nostar": {"old_never": ["alpha", "beta", "gamma"], "old_pinned": ["gamma"], "fresh_never": [], "fresh_pinned": ["alpha"]}}''')


class PinsByAccount(unittest.TestCase):
    def state(self, pins):
        t = Path(tempfile.mkdtemp())
        self.addCleanup(shutil.rmtree, t, True)
        (t / "users.json").write_text(json.dumps(copy.deepcopy(USERS)))
        os.chmod(t / "users.json", 0o600)
        (t / "pinned-projects.json").write_text(json.dumps(copy.deepcopy(pins)))
        was = projects.STATE
        projects.STATE = t
        self.addCleanup(setattr, projects, "STATE", was)
        return t

    def migrate(self, t):
        importlib.import_module("statemigrations.0040_pins_by_account").run({"state": str(t), "project_names": lambda: PROJECTS})

    def test_each_account_keeps_the_spaces_its_home_showed(self):
        for case, pins in CASES.items():
            t = self.state(pins)
            self.migrate(t)
            got = {name: [k for k in PROJECTS if k in projects.load_project_pins(a["uid"])] for name, a in USERS["users"].items()}
            self.assertEqual(got, FROZEN[case], case)
            stored = json.loads((t / "pinned-projects.json").read_text())
            self.assertNotIn("*", stored)
            self.assertEqual(json.loads((t / "users.json").read_text()), USERS, "the accounts are read, never written")

    def test_it_is_idempotent(self):
        t = self.state(CASES["nostar"])
        self.migrate(t)
        once = ((t / "users.json").read_text(), (t / "pinned-projects.json").read_text())
        self.migrate(t)
        self.assertEqual(((t / "users.json").read_text(), (t / "pinned-projects.json").read_text()), once)


if __name__ == "__main__":
    unittest.main()
