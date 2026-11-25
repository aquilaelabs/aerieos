"""Migration 0031: a role that read a space's notebook through another of
its areas is given Spaces Read, and nothing else about any role changes."""
import importlib
import json
import os
import shutil
import sys
import tempfile
import unittest

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))
mig = importlib.import_module("statemigrations.0031_spaces_read_kept")


class SpacesReadKept(unittest.TestCase):
    def setUp(self):
        self.dir = tempfile.mkdtemp(prefix="spaces-read-")
        self.addCleanup(shutil.rmtree, self.dir, True)
        self.f = os.path.join(self.dir, "roles.json")

    def write(self, d):
        with open(self.f, "w") as f:
            json.dump(d, f)
        os.chmod(self.f, 0o600)

    def read(self):
        with open(self.f) as f:
            return json.load(f)

    def test_a_role_on_another_area_reads_and_the_rest_stay(self):
        self.write({"roles": {
            "keeper": {"scope": "projects", "perms": {"containers": "write"}, "note": "", "only": {}},
            "lister": {"scope": "projects", "perms": {"files": "read", "vms": "read"}, "note": "", "only": {}},
            "fleet": {"scope": "global", "perms": {"terminal": "write", "nodes": "write"}, "note": "", "only": {}},
            "builder": {"scope": "projects", "perms": {"projects": "write", "files": "write"}, "note": "", "only": {}},
            "reviewer": {"scope": "projects", "perms": {"projects": "read"}, "note": "", "only": {}},
            "nodesman": {"scope": "global", "perms": {"nodes": "write", "install": "read"},
                         "note": "", "only": {"install": {"n_1": "read"}}},
            "empty": {"scope": "projects", "perms": {}, "note": "", "only": {}},
            "old": {"grants": [{"cap": "docker-write"}]},
        }, "two_factor": ["keeper"]})
        mig.run({"state": self.dir})
        got = self.read()
        r = got["roles"]
        self.assertEqual(r["keeper"]["perms"], {"containers": "write", "projects": "read"})
        self.assertEqual(r["lister"]["perms"], {"files": "read", "vms": "read", "projects": "read"})
        self.assertEqual(r["fleet"]["perms"], {"terminal": "write", "nodes": "write", "projects": "read"})
        self.assertEqual(r["fleet"]["scope"], "global")
        self.assertEqual(r["builder"]["perms"], {"projects": "write", "files": "write"}, "Write is kept, never lowered")
        self.assertEqual(r["reviewer"]["perms"], {"projects": "read"})
        self.assertEqual(r["nodesman"]["perms"], {"nodes": "write", "install": "read"}, "no space area, nothing given")
        self.assertEqual(r["nodesman"]["only"], {"install": {"n_1": "read"}})
        self.assertEqual(r["empty"]["perms"], {})
        self.assertEqual(r["old"], {"grants": [{"cap": "docker-write"}]})
        self.assertEqual(got["two_factor"], ["keeper"])
        self.assertEqual(os.stat(self.f).st_mode & 0o777, 0o600)
        before = os.stat(self.f).st_mtime_ns
        mig.run({"state": self.dir})   # again: as it left it, not written
        self.assertEqual(os.stat(self.f).st_mtime_ns, before)

    def test_the_roles_page_reads_it_as_spaces_read_on_that_space_alone(self):
        import roles
        self.write({"roles": {"keeper": {"scope": "projects", "perms": {"containers": "write"}, "note": "", "only": {}}}})
        was = (roles.FILE, roles.write_json)
        self.addCleanup(lambda: setattr(roles, "FILE", was[0]) or setattr(roles, "write_json", was[1]))
        roles.configure(state=self.dir, write_json=None)
        u = {"name": "bea", "role": "user", "roles": ["user"], "projects": ["alpha"],
             "project_roles": {"alpha": ["keeper"]}}
        self.assertFalse(roles.granted(u, "read", "alpha"), "before: refused, as the audit left it")
        mig.run({"state": self.dir})
        self.assertTrue(roles.granted(u, "read", "alpha"), "after: reads the space it is given on")
        self.assertFalse(roles.granted(u, "work", "alpha"), "and no more than read")
        self.assertFalse(roles.granted(u, "read", "beta"), "nor another space")

    def test_nothing_to_give_leaves_the_file_unwritten(self):
        self.write({"roles": {"reviewer": {"scope": "projects", "perms": {"projects": "read", "files": "read"}}}})
        before = os.stat(self.f).st_mtime_ns
        mig.run({"state": self.dir})
        self.assertEqual(os.stat(self.f).st_mtime_ns, before)

    def test_no_file_or_an_unreadable_one_is_left(self):
        mig.run({"state": self.dir})
        self.assertFalse(os.path.exists(self.f))
        with open(self.f, "w") as f:
            f.write("{not json")
        mig.run({"state": self.dir})
        with open(self.f) as f:
            self.assertEqual(f.read(), "{not json")
        self.write({"roles": ["not", "a", "map"]})
        mig.run({"state": self.dir})
        self.assertEqual(self.read(), {"roles": ["not", "a", "map"]})


if __name__ == "__main__":
    unittest.main()
