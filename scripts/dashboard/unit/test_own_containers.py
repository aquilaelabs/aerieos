"""Containers on the controller's own machine (B743): the job and session
accounts stay off docker, so the root agent runs docker itself, with the
system's programs alone and its compose files where the job account cannot
touch them; what a compose reads of the host is put in front of a person, and
a session's build there waits for one."""
import os
import shutil
import stat
import sys
import tempfile
import unittest
from unittest import mock

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)
sys.path.insert(0, os.path.normpath(os.path.join(HERE, "..")))
import agentpkg  # noqa: E402
import devapp  # noqa: E402
import devactions  # noqa: E402

AGENT = agentpkg.load("own_containers")
work = AGENT.module("work")
base = AGENT.module("base")
WHO = {"user": 1234, "group": 1234}


class Job:
    canceled = False

    def __init__(self):
        self.execs, self.outputs, self.said = [], [], []

    def say(self, s):
        self.said.append(s)

    def step(self, s):
        pass

    def exec(self, spec):
        self.execs.append(spec)
        return "succeeded", 0


class Box(work.WorkMixin):
    def __init__(self, tmp, by_root):
        self.state = {"stores": {"data": os.path.join(tmp, "store")}}
        self.by_root = by_root
        self.owned = []

    def docker_by_root(self):
        return self.by_root

    def drop_privileges(self, env):
        return dict(WHO)

    def own_dir(self, path, who):
        self.owned.append(path)
        os.makedirs(path, exist_ok=True)


SPEC = {"name": "web", "files": {"docker-compose.yml": "services: {}\n"},
        "plan": [{"name": "checking out", "as_job": True, "argv": ["sh", "-c", "git archive"], "env": {}},
                 {"name": "starting", "argv": ["docker", "compose", "-f", "{cdir}/docker-compose.yml", "up"],
                  "env": {"BB_INSTANCE_ENV": "{cdir}/instance.env"}}]}


class ComposeHere(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.mkdtemp()
        self.addCleanup(shutil.rmtree, self.tmp, True)
        self.own = os.path.join(self.tmp, "aerieos-docker", "compose")
        p = mock.patch.object(work, "OWN_COMPOSE", self.own)
        p.start()
        self.addCleanup(p.stop)
        q = mock.patch.object(work.shutil, "which", lambda name: "/usr/bin/docker")
        q.start()
        self.addCleanup(q.stop)
        r = mock.patch.object(work, "sdk_env", lambda state: {"PATH": "/store/bin:/usr/bin", "JAVA_HOME": "/store/jdk"})
        r.start()
        self.addCleanup(r.stop)

    def run_it(self, by_root):
        box, job = Box(self.tmp, by_root), Job()
        got = box.compose(job, dict(SPEC))
        self.assertEqual(got, ("succeeded", 0))
        return box, job

    def test_the_compose_folder_is_out_of_the_job_accounts_reach(self):
        box, job = self.run_it(True)
        cdir = os.path.join(self.own, "web")
        self.assertEqual(box.owned, [], "not handed to the job account")
        self.assertEqual(stat.S_IMODE(os.stat(cdir).st_mode), 0o700)
        self.assertTrue(os.path.isfile(os.path.join(cdir, "docker-compose.yml")))
        self.assertEqual(job.execs[1]["argv"][3], cdir + "/docker-compose.yml")

    def test_docker_runs_on_the_systems_programs_alone(self):
        _, job = self.run_it(True)
        up = job.execs[1]
        self.assertTrue(up["docker"])
        self.assertNotIn("/store", up["env"]["PATH"])
        self.assertNotIn("JAVA_HOME", up["env"])
        self.assertEqual(up["env"]["HOME"], "/root")
        self.assertEqual(up["env"]["BB_INSTANCE_ENV"], os.path.join(self.own, "web", "instance.env"))

    def test_a_step_with_no_docker_in_it_stays_the_job_accounts(self):
        _, job = self.run_it(True)
        co = job.execs[0]
        self.assertNotIn("docker", co)
        self.assertEqual(co["cwd"], "/tmp", "a folder that account may enter")
        self.assertIn("/store", co["env"]["PATH"])

    def test_any_other_node_is_as_it_was(self):
        box, job = self.run_it(False)
        cdir = os.path.join(self.tmp, "store", "compose", "web")
        self.assertEqual(box.owned, [cdir])
        self.assertFalse(os.path.exists(self.own))
        up = job.execs[1]
        self.assertNotIn("docker", up)
        self.assertEqual(up["cwd"], cdir)
        self.assertIn("/store", up["env"]["PATH"])


class TheWall(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.mkdtemp()
        self.addCleanup(shutil.rmtree, self.tmp, True)
        self.wall = os.path.join(self.tmp, "wall")

    def ask(self, euid=0):
        mod = AGENT.module("agent")
        with mock.patch.object(mod, "SESSION_WALL", self.wall), mock.patch.object(mod.os, "geteuid", lambda: euid):
            return mod.Agent.docker_by_root(object())

    def test_only_a_root_agent_behind_a_written_wall(self):
        self.assertFalse(self.ask(), "no wall file: an ordinary node")
        with open(self.wall, "w", encoding="utf-8"):
            pass
        self.assertFalse(self.ask(), "an empty one is none")
        with open(self.wall, "w", encoding="utf-8") as f:
            f.write("ACCOUNT=aerieos\n")
        self.assertTrue(self.ask())
        self.assertFalse(self.ask(euid=1000), "an agent that is not root has no docker to give")


class WhatItReads(unittest.TestCase):
    def setUp(self):
        p = mock.patch.object(devapp, "WORKSPACE", devapp.Path("/workspace") if hasattr(devapp, "Path") else None)
        p.start()
        self.addCleanup(p.stop)

    def said(self, sv, **top):
        return " | ".join(devapp.risks("web", {"services": {"app": sv}, **top}))

    def test_an_env_file_from_the_system_is_named(self):
        self.assertIn("reads /var/lib/aerieos/config/env", self.said({"env_file": ["/var/lib/aerieos/config/env"]}))

    def test_a_build_of_the_system_is_named(self):
        self.assertIn("reads /etc", self.said({"build": {"context": "/etc"}}))

    def test_a_secret_or_a_config_from_the_system_is_named(self):
        got = self.said({}, secrets={"k": {"file": "/etc/shadow"}}, configs={"c": {"file": "/root/x"}})
        self.assertIn("k (secret) is read from /etc/shadow", got)
        self.assertIn("c (config) is read from /root/x", got)

    def test_the_system_pool_is_the_system_whatever_the_pool_is_called(self):
        self.assertIn("mounts /mnt/fast/aerieos-system/home", self.said({"volumes": ["/mnt/fast/aerieos-system/home:/h"]}))

    def test_the_spaces_own_tree_and_the_instance_env_are_not(self):
        self.assertEqual(self.said({"env_file": ["/workspace/web/.env", "/var/x/compose/web/instance.env"],
                                    "build": {"context": "/workspace/web"}}), "")
        self.assertEqual(self.said({"volumes": ["/mnt/media:/m"]}), "")


class BehindTheWall(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.mkdtemp()
        self.addCleanup(shutil.rmtree, self.tmp, True)
        wall = os.path.join(self.tmp, "wall")
        with open(wall, "w", encoding="utf-8") as f:
            f.write("ACCOUNT=aerieos\nCOVER=/srv/aerieos/projects:/var/lib/aerieos-controller\n")
        for attr, v in (("WALL_FILE", wall), ("WORKSPACE", devapp.Path("/srv/aerieos/projects"))):
            p = mock.patch.object(devapp, attr, v)
            p.start()
            self.addCleanup(p.stop)

    def said(self, *binds):
        return " | ".join(devapp.risks("web", {"services": {"app": {"volumes": list(binds)}}}))

    def test_another_spaces_tree_is_named(self):
        self.assertIn("/srv/aerieos/projects/other", self.said("/srv/aerieos/projects/other:/o"))

    def test_the_parent_of_what_it_covers_is_named(self):
        self.assertIn("mounts /srv/aerieos", self.said("/srv/aerieos:/o"))

    def test_this_spaces_tree_is_not(self):
        self.assertEqual(self.said("/srv/aerieos/projects/web/data:/d"), "")


class ASessionsBuild(unittest.TestCase):
    def run_it(self, dial, own, reach=()):
        act, ask = mock.Mock(return_value=({"ok": True}, 200)), mock.Mock(return_value={"ok": True, "asked": True})
        with mock.patch.object(devactions, "act", act), mock.patch.object(devactions, "ask_rebuild", ask, create=True), \
                mock.patch.object(devactions.devapp, "on_own_machine", lambda *a: own), \
                mock.patch.object(devactions.devapp, "unacked_risks", lambda *a: list(reach)), \
                mock.patch.object(devactions.devapp, "pname", lambda p, i: p), \
                mock.patch.object(devactions.devapp, "field", lambda req, k: "", create=True), \
                mock.patch.object(devactions, "say", lambda *a: None, create=True), \
                mock.patch.object(devactions, "users", mock.Mock(account_of=lambda me: {}, uid_of=lambda me: "u", is_admin=lambda a: False)), \
                mock.patch.object(devactions, "acting_as", mock.MagicMock(), create=True):
            devactions.request("web", "main", "rebuild", {}, me={"session": "web"}, principal="session:web", dial=dial)
        return act.called, ask.called

    def test_auto_on_the_controllers_machine_waits_for_a_person(self):
        self.assertEqual(self.run_it("auto", True), (False, True))

    def test_auto_anywhere_else_is_auto(self):
        self.assertEqual(self.run_it("auto", False), (True, False))

    def test_auto_waits_for_a_person_when_the_compose_reaches_the_host(self):
        # The operator, 10 Nov: auto runs at once unless the file asks for
        # more than its own folder that no person has acknowledged.
        self.assertEqual(self.run_it("auto", False, reach=["app runs privileged: root on the host, in effect"]), (False, True))


if __name__ == "__main__":
    unittest.main()
