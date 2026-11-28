"""Migration 0036: roles from before areas (grants, a flat nodes list)
and accounts with one role and no list, written in today's shape once. What
roles.py makes of each migrated role is what its reader made of the old shape
on 26 Nov, before that reader was deleted (frozen here)."""
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
import roles  # noqa: E402

LEGACY = {
    "A": {"grants": [{"cap": "work", "scope": "projects"}, {"cap": "read"}], "note": "x"},
    "B": {"grants": [{"cap": "*", "scope": "all"}]},
    "C": {"grants": [{"cap": "node", "scope": "all"}, {"cap": "toolchains-write"}], "nodes": ["n_1", "n_2"]},
    "D": {"scope": "global", "perms": {"nodes": "write", "jobs": "read"}, "nodes": ["n_9"]},
    "E": {"scope": "projects", "perms": {"projects": "read"}},
    "F": {"scope": "global", "perms": {"nodes": "write"}, "only": {"nodes": {"n_3": "read"}}, "nodes": ["n_4"]},
}
# roles._clean of each LEGACY role on 26 Nov, with the old reader in it.
FROZEN = {'A': {'builtin': False, 'note': 'x', 'only': {}, 'perms': {'projects': 'write'}, 'scope': 'projects'},
 'B': {'builtin': False,
       'note': '',
       'only': {},
       'perms': {'accounts': 'write',
                 'clusters': 'write',
                 'configure': 'write',
                 'containers': 'write',
                 'controller': 'write',
                 'curate': 'write',
                 'deploy': 'write',
                 'files': 'write',
                 'gitauth': 'write',
                 'install': 'write',
                 'jobs': 'write',
                 'newprojects': 'write',
                 'nodes': 'write',
                 'projects': 'write',
                 'releases': 'write',
                 'runner': 'write',
                 'schedules': 'write',
                 'settings': 'write',
                 'storage': 'write',
                 'terminal': 'write',
                 'vms': 'write'},
       'scope': 'global'},
 'C': {'builtin': False,
       'note': '',
       'only': {'install': {'n_1': 'write', 'n_2': 'write'}, 'nodes': {'n_1': 'write', 'n_2': 'write'}},
       'perms': {'install': 'write', 'nodes': 'write'},
       'scope': 'global'},
 'D': {'builtin': False,
       'note': '',
       'only': {'jobs': {'n_9': 'read'}, 'nodes': {'n_9': 'write'}},
       'perms': {'jobs': 'read', 'nodes': 'write'},
       'scope': 'global'},
 'E': {'builtin': False, 'note': '', 'only': {}, 'perms': {'projects': 'read'}, 'scope': 'projects'},
 'F': {'builtin': False,
       'note': '',
       'only': {'nodes': {'n_3': 'read'}},
       'perms': {'nodes': 'read'},
       'scope': 'global'}}


class RolesInAreas(unittest.TestCase):
    def setUp(self):
        self.d = Path(tempfile.mkdtemp())
        self.addCleanup(shutil.rmtree, self.d, True)
        self.mig = importlib.import_module("statemigrations.0036_roles_in_areas")

    def test_each_old_role_reads_as_it_did_and_the_file_holds_one_shape(self):
        (self.d / "roles.json").write_text(json.dumps({"roles": copy.deepcopy(LEGACY), "two_factor": ["A"]}))
        os.chmod(self.d / "roles.json", 0o600)
        self.mig.run({"state": str(self.d)})
        d = json.loads((self.d / "roles.json").read_text())
        self.assertEqual({n: roles._clean(copy.deepcopy(r)) for n, r in d["roles"].items()}, FROZEN)
        self.assertFalse(any("grants" in r or "nodes" in r for r in d["roles"].values()))
        self.assertEqual(d["two_factor"], ["A"])
        self.assertEqual((self.d / "roles.json").stat().st_mode & 0o777, 0o600)
        before = (self.d / "roles.json").read_text()
        self.mig.run({"state": str(self.d)})
        self.assertEqual((self.d / "roles.json").read_text(), before, "run again: as it left it")

    def test_an_account_with_one_role_gets_its_list(self):
        (self.d / "users.json").write_text(json.dumps({"users": {"ann": {"role": "admin"}, "bob": {"role": "user", "roles": ["dev"]}, "cy": {}}}))
        self.mig.run({"state": str(self.d)})
        us = json.loads((self.d / "users.json").read_text())["users"]
        self.assertEqual({n: u["roles"] for n, u in us.items()}, {"ann": ["admin"], "bob": ["dev"], "cy": ["user"]})
        self.assertEqual([roles.roles_of(u) for u in us.values()], [["admin"], ["dev"], ["user"]])


if __name__ == "__main__":
    unittest.main()
