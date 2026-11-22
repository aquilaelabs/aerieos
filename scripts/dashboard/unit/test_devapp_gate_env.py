"""A rebuild that finds new keys in .env.example rewrites the env of the
instance it rebuilt, and no other: a second instance's gate once wrote over
the main instance's env, its secrets with it."""
import json
import os
import shutil
import sys
import tempfile
import unittest
from pathlib import Path

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))
import devapp  # noqa: E402


def write_json(path, d):
    with open(path, "w") as f:
        json.dump(d, f)


class GateEnv(unittest.TestCase):
    def setUp(self):
        self.tmp = Path(tempfile.mkdtemp(prefix="gateenv-"))
        self.was = {k: getattr(devapp, k, None) for k in
                    ("WORKSPACE", "STATE", "FILE", "OWNERS", "ENVDIR", "write_json", "label_of")}
        ws, st = self.tmp / "ws", self.tmp / "state"
        st.mkdir()
        devapp.configure(workspace=ws, state=st, write_json=write_json)
        p = ws / "web"
        p.mkdir(parents=True)
        (p / "docker-compose.yml").write_text("services: {}\n")
        (p / ".env.example").write_text("SECRET=\nNEW_KEY=\n")
        r = devapp.create_instance("web", "staging")
        self.assertTrue(r.get("ok"), r)
        self.staging = devapp.instance_key("web", "staging")
        devapp.write_env("web", "SECRET=main-secret\n")
        devapp.write_env("web", "SECRET=staging-secret\n", self.staging)

    def tearDown(self):
        for k, v in self.was.items():
            setattr(devapp, k, v)
        shutil.rmtree(self.tmp, ignore_errors=True)

    def test_a_second_instances_gate_rewrites_its_own_env(self):
        devapp._gate_env("web", self.staging)
        self.assertEqual(devapp.read_env("web"), "SECRET=main-secret\n")
        got = devapp.read_env("web", self.staging)
        self.assertIn("NEW_KEY=", got)
        self.assertIn("# old: SECRET=staging-secret", got)

    def test_the_main_instances_gate_leaves_the_second_alone(self):
        devapp._gate_env("web")
        self.assertEqual(devapp.read_env("web", self.staging), "SECRET=staging-secret\n")
        self.assertIn("# old: SECRET=main-secret", devapp.read_env("web"))


if __name__ == "__main__":
    unittest.main()
