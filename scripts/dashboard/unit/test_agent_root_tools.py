"""The tools root installs from the bundle are AerieOS's release where the
node pinned the release key (R227 step 1, held by the bundle's signed list
since R267 step 28), and a machine's console can switch off every root
command the controller sends (step 2).

The bundle's digest is the controller's word and moves with a person's tool
packs, so what a release signs is the list of the files it ships in it,
root's among them. Root keeps its copy only from a tar that list passed;
a second signature over root's files alone said nothing more, and is gone."""
import io
import json
import os
import sys
import tarfile
import tempfile
import unittest
from unittest import mock

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, os.path.join(HERE, "..", "..", "agent"))
sys.path.insert(0, os.path.join(HERE, ".."))
from aerieos_agent import cli, configplane, stores, workspace  # noqa: E402

FILES = {"nodes/provision-linux.sh": b"#!/bin/sh\necho provision\n", "nodes/bb-session": b"#!/bin/sh\necho session\n",
         "nodes/bb-netcut": b"#!/bin/sh\necho netcut\n", "nodes/families/debian.sh": b"family=debian\n"}


def bundle_tar(path, files, extra=None):
    with tarfile.open(path, "w") as tar:
        for name, data in dict(files, **(extra or {})).items():
            ti = tarfile.TarInfo(name)
            ti.size = len(data)
            tar.addfile(ti, io.BytesIO(data))


class Keep(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.mkdtemp()
        self.tools = os.path.join(self.tmp, "tools")
        os.makedirs(self.tools)
        self.tar = os.path.join(self.tmp, "bundle.tar")
        self.said = []
        p = mock.patch.object(workspace, "TOOLS_DIR", self.tools)
        p.start()
        self.addCleanup(p.stop)

    def keep(self, name):
        return workspace.WorkspaceMixin._keep_root_tools(self.tar, name, self.said.append)

    def current(self):
        link = os.path.join(self.tools, "current")
        return os.readlink(link) if os.path.islink(link) else ""

    def test_roots_own_files_are_lifted_out_and_nothing_else(self):
        bundle_tar(self.tar, FILES, extra={"scripts/aerie": b"not root's", "config/toolpacks.json": b"{}"})
        self.assertTrue(self.keep("aaaa"))
        self.assertEqual(self.current(), "aaaa")
        with open(os.path.join(self.tools, "aaaa", "nodes", "bb-session"), "rb") as f:
            self.assertEqual(f.read(), FILES["nodes/bb-session"])
        self.assertTrue(os.path.isfile(os.path.join(self.tools, "aaaa", "nodes", "families", "debian.sh")))
        self.assertFalse(os.path.exists(os.path.join(self.tools, "aaaa", "scripts")), "only root's own files are lifted out")
        self.assertEqual(self.said, [])
        self.assertTrue(self.keep("aaaa"), "the same bundle again: nothing to do")
        bundle_tar(self.tar, {**FILES, "nodes/bb-session": b"#!/bin/sh\necho newer\n"})
        self.assertTrue(self.keep("bbbb"))
        self.assertEqual(self.current(), "bbbb")
        self.assertFalse(os.path.exists(os.path.join(self.tools, "aaaa")), "the copy of another bundle goes")

    def test_only_a_tar_the_bundles_signed_list_passed_is_kept_from(self):
        # The keep is reached only past _bundle_checked (may_keep_bundle):
        # a refused bundle returns before root's copy is touched.
        with open(os.path.join(HERE, "..", "..", "agent", "aerieos_agent", "workspace.py"), encoding="utf-8") as f:
            text = f.read()
        checked = text.index("ok, said = self._bundle_checked(part, trust)")
        refused = text.index("return before", checked)
        kept = text.index("self._keep_root_tools(tar_path", checked)
        self.assertLess(refused, kept)
        self.assertNotIn("root-tools.sig", text)


class RootAsks(unittest.TestCase):
    """Step 2: the console's own word on root commands."""

    def setUp(self):
        self.tmp = tempfile.mkdtemp()
        self.node_json = os.path.join(self.tmp, "node.json")
        with open(self.node_json, "w") as f:
            json.dump({"node_id": "n_1", "token": "bbn_x"}, f)
        for mod in (stores, cli):
            p = mock.patch.object(mod, "NODE_JSON", self.node_json)
            p.start()
            self.addCleanup(p.stop)
        p = mock.patch.object(cli, "_at_console", lambda why: None)
        p.start()
        self.addCleanup(p.stop)

    def state(self):
        with open(self.node_json) as f:
            return json.load(f)

    def test_off_is_kept_in_node_json_and_outlives_the_agents_own_writes(self):
        with mock.patch("builtins.print"):
            cli.cmd_root_asks(["off"])
        self.assertIs(self.state().get("root_off"), True)
        self.assertEqual(stores.console_said(), {"root_off": True})
        # The running agent writes node.json whole from its own older copy.
        stores.save_state({"node_id": "n_1", "token": "bbn_newer"})
        self.assertIs(self.state().get("root_off"), True, "its copy does not undo the console")
        with mock.patch("builtins.print"):
            cli.cmd_root_asks(["on"])
        self.assertNotIn("root_off", self.state())

    def test_the_running_agent_tells_the_controller_at_its_next_turn(self):
        # The controller holds a root ask by the census, so a press at the
        # console is told at the agent's next turn and not at its next hello.
        from aerieos_agent import agent
        a = agent.Agent.__new__(agent.Agent)
        self.assertFalse(a.console_moved(), "the first look is no change")
        self.assertFalse(a.console_moved())
        with mock.patch("builtins.print"):
            cli.cmd_root_asks(["off"])
        self.assertTrue(a.console_moved(), "a press at the console")
        self.assertFalse(a.console_moved(), "...told once")
        with mock.patch("builtins.print"):
            cli.cmd_root_asks(["on"])
        self.assertTrue(a.console_moved())

    def test_only_on_or_off(self):
        with self.assertRaises(SystemExit):
            cli.cmd_root_asks(["maybe"])

    def test_a_root_command_is_refused_while_it_is_off(self):
        class Job:
            def __init__(self):
                self.out = []

            def say(self, text):
                self.out.append(text)

        cfg = {"argv": ["/bin/true"], "by": "ann", "why": "a test"}
        job = Job()
        with mock.patch.object(configplane, "console_said", lambda: {"root_off": True}), \
                mock.patch.object(configplane.subprocess, "Popen", side_effect=AssertionError("nothing may start")):
            got = configplane.ConfigPlaneMixin._apply_root(object(), job, cfg)
        self.assertEqual(got, ("failed", 77))
        self.assertIn("switched off at its own console", job.out[0])
        self.assertRegex(job.out[0], r"sudo (aerieos|builderbot)-agent root-asks on")


if __name__ == "__main__":
    unittest.main()
