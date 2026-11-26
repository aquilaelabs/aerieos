"""Migration 0033: every space owner's role is given Deploy Write, as a new
owner role is made with it, and no other role changes."""
import importlib
import json
import os
import shutil
import sys
import tempfile
import unittest

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))
mig = importlib.import_module("statemigrations.0033_owners_deploy")
import roles  # noqa: E402


class OwnersDeploy(unittest.TestCase):
    def setUp(self):
        self.dir = tempfile.mkdtemp(prefix="owners-deploy-")
        self.addCleanup(shutil.rmtree, self.dir, True)
        self.f = os.path.join(self.dir, "roles.json")

    def write(self, d):
        with open(self.f, "w") as f:
            json.dump(d, f)
        os.chmod(self.f, 0o600)

    def read(self):
        with open(self.f) as f:
            return json.load(f)

    def test_owners_deploy_and_the_rest_stay(self):
        before = {"projects": "write", "settings": "write", "containers": "write"}
        self.write({"roles": {
            "shop_owner": {"scope": "projects", "perms": dict(before), "note": "the owner of shop", "only": {}},
            "lab_owner": {"scope": "projects", "perms": dict(before, deploy="read"), "note": "the owner of lab", "only": {}},
            "keeper": {"scope": "projects", "perms": {"containers": "write"}, "note": "", "only": {}},
            "fake_owner": {"scope": "global", "perms": {"nodes": "write"}, "note": "the owner of nothing", "only": {}},
            "named_owner": {"scope": "projects", "perms": {"projects": "read"}, "note": "made by hand", "only": {}},
        }, "two_factor": ["keeper"]})
        mig.run({"state": self.dir})
        r = self.read()["roles"]
        self.assertEqual(r["shop_owner"]["perms"], dict(before, deploy="write"))
        self.assertEqual(r["lab_owner"]["perms"]["deploy"], "write", "Read is raised to Write on an owner's")
        self.assertEqual(r["keeper"]["perms"], {"containers": "write"})
        self.assertEqual(r["fake_owner"]["perms"], {"nodes": "write"}, "a global role is nobody's owner role")
        self.assertEqual(r["named_owner"]["perms"], {"projects": "read"}, "a role named _owner by hand is not one")
        self.assertEqual(self.read()["two_factor"], ["keeper"])
        self.assertEqual(oct(os.stat(self.f).st_mode & 0o777), "0o600", "the file's mode is kept")
        was = self.read()
        mig.run({"state": self.dir})
        self.assertEqual(self.read(), was, "idempotent")

    def test_a_new_owner_role_deploys(self):
        self.assertEqual(roles.OWNER_PERMS.get("deploy"), "write")

    def test_no_file_no_roles(self):
        mig.run({"state": self.dir})
        self.assertFalse(os.path.exists(self.f))
        self.write({"two_factor": []})
        mig.run({"state": self.dir})
        self.assertEqual(self.read(), {"two_factor": []})


if __name__ == "__main__":
    unittest.main()
