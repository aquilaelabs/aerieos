"""bb-session and the agent's folder under its two names (R204): the folder
is /var/lib/aerieos or, on a machine provisioned before that name,
/var/lib/builderbot, with the other name a link to it. The layout names the
stores under one and the runner's folder under the other, so the plan reads
each by where it really is: the folder is covered whichever name is the
link, and the runner's folder, gone under that cover, is not a step."""
import importlib.machinery
import importlib.util
import os
import pwd
import tempfile
import unittest
from unittest import mock

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.abspath(os.path.join(HERE, "..", "..", ".."))


def load(name, path):
    loader = importlib.machinery.SourceFileLoader(name, path)
    spec = importlib.util.spec_from_loader(name, loader)
    mod = importlib.util.module_from_spec(spec)
    loader.exec_module(mod)
    return mod


session = load("bb_session_names", os.path.join(ROOT, "nodes", "bb-session"))
ME = pwd.getpwuid(os.getuid()).pw_name


class Names(unittest.TestCase):
    def machine(self, real, link):
        """A stand-in machine whose agent folder is `real`, `link` a link to it."""
        d = os.path.realpath(tempfile.mkdtemp())
        self.addCleanup(lambda: __import__("shutil").rmtree(d, True))
        self.account = "u_0000abcd"
        for p in (f"var/lib/{real}/data/ci-logs/app", f"var/lib/{real}/artifacts/app", f"var/lib/{real}/runner",
                  f"var/lib/{real}/agent", f"var/lib/{real}/cache/other", "workspace/app",
                  f"home/builder/users/{self.account}", "usr", "etc"):
            os.makedirs(f"{d}/{p}")
        if link:
            os.symlink(real, f"{d}/var/lib/{link}")
        return d

    def plan(self, d, c):
        a = {"project": "app", "account": self.account, "home": f"{d}/home/builder/users/{self.account}", "cwd": f"{d}/workspace/app"}
        base = {"SESSION_USER": ME, "WORKSPACE": f"{d}/workspace", "HOME_ROOT": f"{d}/home/builder", "HIDE": "", "TOOLCHAINS_STORE": ""}
        env = {"BB_SESSION_ROOT": d, "BB_SESSION_MOUNTS": "/nonexistent/mounts", "BB_SESSION_WALL": "/nonexistent/wall",
               "BB_SESSION_MARKS": "/nonexistent/x"}
        with mock.patch.dict(os.environ, env):
            return session.plan(dict(base, **c), a, None)

    def check(self, d, real, steps):
        folder = f"{d}/var/lib/{real}"
        self.assertIn(("tmpfs", folder, "mode=0755"), steps, "the agent's folder is covered where it really is")
        self.assertIn(("tmpfs", f"{folder}/data", "mode=0755"), steps)
        self.assertIn(("bind", f"{session.STAGE}/data/ci-logs/app", f"{folder}/data/ci-logs/app"), steps)
        self.assertFalse([s for s in steps if s[0] == "hide" and "runner" in s[1]],
                         "the runner's folder is under the cover already: nothing to mount on")
        made = [s[-1] if s[0].startswith("bind") else s[1] for s in steps]
        self.assertFalse([p for p in made if f"/var/lib/{'aerieos' if real == 'builderbot' else 'builderbot'}" in p],
                         "no step names a path through the link")

    def test_the_old_folder_with_the_new_name_a_link(self):
        d = self.machine("builderbot", "aerieos")
        # As a node provisioned before the name has it once its agent has
        # restarted: the stores as node.json recorded them, the runner and
        # the agent's folder under the name that answers now.
        steps = self.plan(d, {"DATA_STORE": f"{d}/var/lib/builderbot/data", "ARTIFACTS_STORE": f"{d}/var/lib/builderbot/artifacts",
                              "RUNNER_DIR": f"{d}/var/lib/aerieos/runner", "STATE_DIR": f"{d}/var/lib/aerieos"})
        self.check(d, "builderbot", steps)

    def test_the_new_folder_with_the_old_name_a_link(self):
        d = self.machine("aerieos", "builderbot")
        # As the Enroll script leaves it: the folder moved, the old name a
        # link, the stores still recorded under the old name.
        steps = self.plan(d, {"DATA_STORE": f"{d}/var/lib/builderbot/data", "ARTIFACTS_STORE": f"{d}/var/lib/builderbot/artifacts",
                              "RUNNER_DIR": f"{d}/var/lib/aerieos/runner", "STATE_DIR": f"{d}/var/lib/builderbot"})
        self.check(d, "aerieos", steps)

    def test_the_new_folder_alone(self):
        d = self.machine("aerieos", "")
        steps = self.plan(d, {"DATA_STORE": f"{d}/var/lib/aerieos/data", "ARTIFACTS_STORE": f"{d}/var/lib/aerieos/artifacts",
                              "RUNNER_DIR": f"{d}/var/lib/aerieos/runner", "STATE_DIR": f"{d}/var/lib/aerieos"})
        self.check(d, "aerieos", steps)

    def test_the_layout_names_the_folder_that_is_there(self):
        d = self.machine("aerieos", "")
        conf = f"{d}/conf"
        with open(conf, "w") as f:
            f.write("SESSION_USER=builder\n")
        os.chmod(conf, 0o644)
        for there, want in ((("/a", "/b"), "/a"), ((f"{d}/nowhere", f"{d}/var/lib/aerieos"), f"{d}/var/lib/aerieos")):
            with mock.patch.dict(os.environ, {"BB_SESSION_CONF": conf}), mock.patch.object(session, "AGENT_DIRS", there):
                self.assertEqual(session.conf()["STATE_DIR"], want)
        with open(conf, "a") as f:
            f.write("STATE_DIR=/somewhere/said\n")
        with mock.patch.dict(os.environ, {"BB_SESSION_CONF": conf}):
            self.assertEqual(session.conf()["STATE_DIR"], "/somewhere/said")


if __name__ == "__main__":
    unittest.main()
