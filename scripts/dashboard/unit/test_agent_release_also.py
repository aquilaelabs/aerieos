"""A node trusts the key a build of somebody's own is signed with, once a
person adds it at the node's console (release.also, node.json's
release_also): an agent update or a list of root's tools signed by an added
key is taken and said as what it is, beside the release key and its spare.
Four at most, each a key, added and dropped only at the console: the running
agent's own saves keep the file's list and nothing a controller sends
reaches it. A node.json from before the list loads as it always did."""
import contextlib
import io
import json
import os
import sys
import tarfile
import tempfile
import unittest
from unittest import mock

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)
sys.path.insert(0, os.path.join(HERE, ".."))
import agentpkg  # noqa: E402
import nodes  # noqa: E402
from cryptography.hazmat.primitives.asymmetric.ed25519 import Ed25519PrivateKey  # noqa: E402

DIGEST = "sha256:" + "ab" * 32
FILES = {"nodes/provision-linux.sh": b"#!/bin/sh\necho provision\n", "nodes/bb-session": b"#!/bin/sh\necho session\n",
         "nodes/bb-netcut": b"#!/bin/sh\necho netcut\n", "nodes/families/debian.sh": b"family=debian\n"}


def pair():
    k = Ed25519PrivateKey.generate()
    return k, k.public_key().public_bytes_raw().hex()


class Case(unittest.TestCase):
    def setUp(self):
        self.agent = agentpkg.load("aerieos_agent_release_also")
        self.release, self.stores, self.cli = (self.agent.module(m) for m in ("release", "stores", "cli"))
        self.d = tempfile.mkdtemp()
        self.nj = os.path.join(self.d, "node.json")
        self.agent.NODE_JSON = self.nj
        self.k, self.pub = pair()
        self.s, self.spare = pair()
        self.m, self.mine = pair()

    def sign(self, key, digest=DIGEST, message=None):
        return key.sign((message or self.release.MESSAGE) + digest.encode()).hex()

    def write(self, state):
        with open(self.nj, "w") as f:
            json.dump(state, f)

    def read(self):
        with open(self.nj) as f:
            return json.load(f)

    def console(self, *args, at_console=True):
        """A console verb as a person at the machine runs it; what it printed."""
        out = io.StringIO()
        with contextlib.redirect_stdout(out), \
                mock.patch.object(self.cli, "_at_console", (lambda what: None) if at_console else self.cli._at_console):
            self.cli.main(list(args))
        return out.getvalue()


class Trusted(Case):
    def test_an_update_signed_by_an_added_key_is_taken_and_said_as_such(self):
        state = {"release_key": self.pub, "release_spare": self.spare, "release_also": [self.mine]}
        ok, said = self.release.may_install(state, DIGEST, self.sign(self.m))
        self.assertTrue(ok, said)
        self.assertEqual(said, f"signed by a key added at this node's console ({self.mine[:16]}…)")
        # The release key and its spare are still said as themselves.
        for signer, words in ((self.k, "signed by the release key this node pinned"), (self.s, "signed by the spare release key")):
            ok, said = self.release.may_install(state, DIGEST, self.sign(signer))
            self.assertTrue(ok, said)
            self.assertIn(words, said)
        # Without the list, the same signature is nobody's here.
        self.assertFalse(self.release.may_install({"release_key": self.pub}, DIGEST, self.sign(self.m))[0])

    def test_keys_is_the_release_key_and_its_spare_and_trusted_is_every_key(self):
        state = {"release_key": self.pub, "release_spare": self.spare, "release_also": [self.mine, self.pub]}
        self.assertEqual(self.release.keys(state), [self.pub, self.spare])
        self.assertEqual(self.release.also(state), [self.mine, self.pub])
        self.assertEqual(self.release.trusted(state), [self.pub, self.spare, self.mine])
        # What is not a key is passed over, and no more than four are read.
        six = [pair()[1] for _ in range(6)]
        self.assertEqual(self.release.also({"release_also": ["nope", 5, None, six[0].upper(), six[0]] + six[1:]}), six[:4])
        for junk in (None, "", self.mine, {"a": self.mine}, 7):
            self.assertEqual(self.release.also({"release_also": junk}), [], junk)

    def test_a_node_with_only_an_added_key_takes_what_it_signed_and_nothing_unsigned(self):
        state = {"release_also": [self.mine]}
        ok, said = self.release.may_install(state, DIGEST, self.sign(self.m))
        self.assertTrue(ok, said)
        self.assertIn("a key added at this node's console", said)
        ok, said = self.release.may_install(state, DIGEST, "")
        self.assertFalse(ok)
        self.assertIn(f"a key added at its console ({self.mine[:16]}…)", said)
        ok, said = self.release.may_install(state, DIGEST, self.sign(self.k))
        self.assertFalse(ok)
        self.assertIn("under no key this node trusts", said)
        ok, said = self.release.may_install(dict(state, unsigned_ok=True), DIGEST, "")
        self.assertTrue(ok)
        self.assertIn("console allows unsigned", said)

    def test_a_refusal_names_every_key_and_what_the_console_can_do(self):
        other, _ = pair()
        _, second = pair()
        state = {"release_key": self.pub, "release_spare": self.spare, "release_also": [self.mine, second]}
        ok, said = self.release.may_install(state, DIGEST, self.sign(other))
        self.assertFalse(ok)
        self.assertIn(f"the release key it pinned ({self.pub[:16]}…) or its spare ({self.spare[:16]}…) or one of the keys added "
                      f"at its console ({self.mine[:16]}…, {second[:16]}…)", said)
        # What is so, and the two things a person at the console can do.
        self.assertNotIn("built from a branch", said)
        self.assertIn("unsigned unless its builder signs it with a key of their own", said)
        self.assertRegex(said, r"sudo (aerieos|builderbot)-agent release-key add HEX trusts that builder's key")
        self.assertRegex(said, r"sudo (aerieos|builderbot)-agent unsigned on allows unsigned builds")
        # A node with the release key alone is told the same two.
        ok, said = self.release.may_install({"release_key": self.pub}, DIGEST, "")
        self.assertFalse(ok)
        self.assertNotIn("built from a branch", said)
        self.assertRegex(said, r"release-key add HEX")
        self.assertIn(f"only updates signed by the release key it pinned ({self.pub[:16]}…). ", said)


class RootTools(Case):
    def bundle(self, sig):
        tar = os.path.join(self.d, "bundle.tar")
        held = dict(FILES)
        if sig is not None:
            held[self.agent.TOOLS_SIG] = json.dumps({"sig": sig}).encode()
        with tarfile.open(tar, "w") as t:
            for name, data in held.items():
                ti = tarfile.TarInfo(name)
                ti.size = len(data)
                t.addfile(ti, io.BytesIO(data))
        return tar

    def test_roots_tools_signed_by_an_added_key_are_kept_and_said_as_such(self):
        workspace = self.agent.module("workspace")
        tools, said = os.path.join(self.d, "tools"), []
        os.makedirs(tools)
        sig = self.sign(self.m, self.release.tools_digest(FILES), self.release.TOOLS_MESSAGE)
        with mock.patch.object(workspace, "TOOLS_DIR", tools):
            keep = workspace.WorkspaceMixin._keep_root_tools
            # A node that pinned the release key alone keeps the copy it has...
            self.assertFalse(keep(self.bundle(sig), "aaaa", said.append, {"release_key": self.pub}))
            self.assertIn("root keeps the copy it has", said[0])
            self.assertRegex(said[0], r"release-key add HEX")
            self.assertNotIn("built from a branch", said[0])
            del said[:]
            # ...and one whose console added the builder's key keeps these.
            self.assertTrue(keep(self.bundle(sig), "aaaa", said.append, {"release_key": self.pub, "release_also": [self.mine]}))
            self.assertEqual(said, [f"root's tools are signed by a key added at this node's console ({self.mine[:16]}…)\n"])
            self.assertEqual(os.readlink(os.path.join(tools, "current")), "aaaa")
            # The agent's signature under the same key is not the tools'.
            self.assertFalse(keep(self.bundle(self.sign(self.m, self.release.tools_digest(FILES))), "bbbb", said.append,
                                  {"release_also": [self.mine]}))


class Console(Case):
    def test_add_and_drop_at_the_console(self):
        self.write({"node_id": "n_1", "token": "bbn_1", "release_key": self.pub})
        said = self.console("release-key", "add", self.mine.upper())
        self.assertIn(f"added {self.mine[:16]}…", said)
        self.assertEqual(self.read(), {"node_id": "n_1", "token": "bbn_1", "release_key": self.pub, "release_also": [self.mine]})
        # The bare verb shows them whole, beside the release key.
        shown = self.console("release-key")
        self.assertIn(f"release key: {self.pub}", shown)
        self.assertIn(f"added here:  {self.mine}", shown)
        # Twice is once, and the release key is not added beside itself.
        self.assertIn("already", self.console("release-key", "add", self.mine))
        self.assertIn("nothing added", self.console("release-key", "add", self.pub))
        self.assertEqual(self.read()["release_also"], [self.mine])
        # Pinning the release key again, or dropping it, leaves the added ones.
        self.console("release-key", f"{self.pub},{self.spare}")
        self.assertEqual(self.read()["release_also"], [self.mine])
        self.assertIn("still takes only agent updates signed by the key added here", self.console("release-key", "none"))
        self.assertEqual(self.read(), {"node_id": "n_1", "token": "bbn_1", "release_also": [self.mine], "release_unpinned": True})
        self.assertIn("release key: none pinned, by this console's choice\n", self.console("release-key"))
        self.assertIn("unsigned builds: refused", self.console("release-key"))
        said = self.console("release-key", "drop", self.mine)
        self.assertIn(f"dropped {self.mine[:16]}…", said)
        self.assertEqual(self.read(), {"node_id": "n_1", "token": "bbn_1", "release_unpinned": True})
        self.assertIn("taken on the controller's word", self.console("release-key"))

    def test_dropping_the_release_key_is_a_choice_kept_until_one_is_pinned_again(self):
        self.write({"node_id": "n_1", "token": "bbn_1", "release_key": self.pub, "release_spare": self.spare})
        said = self.console("release-key", "none")
        self.assertIn("takes what its controller sends, checked against nothing", said)
        self.assertIn("will not pin a release key by itself until one is pinned here again", said)
        self.assertEqual(self.read(), {"node_id": "n_1", "token": "bbn_1", "release_unpinned": True})
        shown = self.console("release-key")
        self.assertIn("release key: none pinned, by this console's choice", shown)
        self.assertIn("this node pins no key by itself", shown)
        self.assertNotIn("pins that key", shown)
        # Adding a builder's key leaves the choice as it is: the node trusts a key again all the same.
        self.console("release-key", "add", self.mine)
        self.assertEqual(self.read(), {"node_id": "n_1", "token": "bbn_1", "release_unpinned": True, "release_also": [self.mine]})
        self.console("release-key", "drop", self.mine)
        # Pinning one again at the console ends it.
        self.console("release-key", f"{self.pub},{self.spare}")
        self.assertEqual(self.read(), {"node_id": "n_1", "token": "bbn_1", "release_key": self.pub, "release_spare": self.spare})
        # A node that never chose says what will pin one.
        self.write({"node_id": "n_1", "token": "bbn_1"})
        self.assertIn("the first one signed by a release key it names pins that key", self.console("release-key"))

    def test_an_enrollment_keeps_the_choice_unless_it_names_a_key(self):
        cli = self.cli

        class Ctl:
            CA = "ca"

            def __init__(self, url, token, pin):
                self.url, self.host, self.scheme = url, "h", "http"

            def call(self, verb, body, timeout=30):
                return 200, {"node_id": "n_1", "token": "bbn_x", "name": "box", "capabilities": []}

        def enroll(*more):
            with mock.patch.object(cli, "Controller", Ctl), mock.patch.object(cli, "census", lambda state: {}), \
                    mock.patch.object(cli, "make_store", lambda p: {}), mock.patch.object(cli, "store_path_ok", lambda p, **kw: ""), \
                    contextlib.redirect_stdout(io.StringIO()):
                cli.cmd_enroll(["--controller", "http://c", "--token", "bbe_t", *more])
            return self.read()
        self.write({"node_id": "n_1", "token": "bbn_old", "stores": {}, "release_unpinned": True})
        got = enroll()
        self.assertEqual((got["token"], got.get("release_unpinned"), got.get("release_key")), ("bbn_x", True, None))
        got = enroll("--release-key", f"{self.pub},{self.spare}")
        self.assertEqual((got.get("release_key"), got.get("release_spare")), (self.pub, self.spare))
        self.assertNotIn("release_unpinned", got)
        # A record from before the choice was kept gains none by enrolling.
        self.write({"node_id": "n_1", "token": "bbn_old", "stores": {}})
        self.assertNotIn("release_unpinned", enroll())

    def test_a_fifth_key_a_malformed_one_and_one_not_there_are_refused(self):
        four = [pair()[1] for _ in range(4)]
        self.write({"node_id": "n_1", "token": "bbn_1"})
        for k in four:
            self.console("release-key", "add", k)
        self.assertEqual(self.read()["release_also"], four)
        with self.assertRaises(SystemExit) as e:
            self.console("release-key", "add", self.mine)
        self.assertIn("4 added keys, the most it keeps", str(e.exception))
        for bad in (["nope"], [self.mine[:-1]], [self.mine + "0"], [self.mine[:-1] + "g"], [f"{self.mine},{self.spare}"],
                    [self.mine, self.spare], []):
            for verb in ("add", "drop"):
                with self.assertRaises(SystemExit, msg=(verb, bad)) as e:
                    self.console("release-key", verb, *bad)
                self.assertIn("one key as 64 hex characters", str(e.exception))
        with self.assertRaises(SystemExit) as e:
            self.console("release-key", "drop", self.mine)
        self.assertIn("is not a key added here", str(e.exception))
        self.assertEqual(self.read()["release_also"], four, "none of them changed the list")
        # One dropped makes room for the fifth.
        self.console("release-key", "drop", four[1])
        self.console("release-key", "add", self.mine)
        self.assertEqual(self.read()["release_also"], [four[0], four[2], four[3], self.mine])

    def test_add_and_drop_take_a_person_at_the_machine(self):
        # Root on a terminal, as pinning the release key does: a job the
        # controller sends has neither.
        self.write({"node_id": "n_1", "token": "bbn_1", "release_also": [self.mine]})
        _, theirs = pair()
        for euid, tty in ((1000, True), (0, False)):
            with mock.patch("os.geteuid", lambda euid=euid: euid), mock.patch.object(sys, "stdin", mock.Mock(isatty=lambda tty=tty: tty)):
                for args in (("add", theirs), ("drop", self.mine)):
                    with self.assertRaises(SystemExit):
                        self.console("release-key", *args, at_console=False)
        self.assertEqual(self.read()["release_also"], [self.mine])

    def test_an_enrollment_keeps_the_keys_added_here(self):
        cli = self.cli
        self.write({"node_id": "n_1", "token": "bbn_old", "stores": {}, "release_key": self.pub, "release_also": [self.mine]})

        class Ctl:
            CA = "ca"

            def __init__(self, url, token, pin):
                self.url, self.host, self.scheme = url, "h", "http"

            def call(self, verb, body, timeout=30):
                return 200, {"node_id": "n_1", "token": "bbn_x", "name": "box", "capabilities": []}

        with mock.patch.object(cli, "Controller", Ctl), mock.patch.object(cli, "census", lambda state: {}), \
                mock.patch.object(cli, "make_store", lambda p: {}), mock.patch.object(cli, "store_path_ok", lambda p, **kw: ""), \
                contextlib.redirect_stdout(io.StringIO()):
            cli.cmd_enroll(["--controller", "http://c", "--token", "bbe_t", "--release-key", f"{self.pub},{self.spare}"])
        got = self.read()
        self.assertEqual((got["token"], got["release_key"], got["release_spare"], got["release_also"]),
                         ("bbn_x", self.pub, self.spare, [self.mine]))


class NotTheControllers(Case):
    def test_the_agents_own_save_keeps_the_files_list(self):
        _, theirs = pair()
        self.write({"node_id": "n_1", "token": "bbn_1", "release_key": self.pub, "release_also": [self.mine]})
        running = {"node_id": "n_1", "token": "bbn_1"}
        # A copy that names another key, more keys, or none: the file's stand.
        for held in ({"release_also": [theirs]}, {"release_also": [self.mine, theirs]}, {"release_also": []}, {}):
            self.stores.save_state(dict(running, token="bbn_2", **held))
            self.assertEqual(self.read(), {"node_id": "n_1", "token": "bbn_2", "release_key": self.pub, "release_also": [self.mine]})
        # ...and a file with none gets none from the agent's copy.
        self.write({"node_id": "n_1", "token": "bbn_2"})
        self.stores.save_state(dict(running, token="bbn_3", release_also=[theirs]))
        self.assertEqual(self.read(), {"node_id": "n_1", "token": "bbn_3"})
        self.assertIn("release_also", self.stores.CONSOLE_KEYS)

    def test_the_controller_keeps_what_the_node_reports_shortened(self):
        out = {}
        nodes._c_release({"release_key": self.pub[:16], "release_also": [self.mine[:16], self.mine, "nope", 5, None]}, out)
        self.assertEqual(out["release_also"], [self.mine[:16], self.mine[:16]])
        for junk in (None, "x", {"a": 1}, 5):
            nodes._c_release({"release_also": junk}, out)
            self.assertEqual(out["release_also"], [], junk)
        nodes._c_release({"release_also": [pair()[1] for _ in range(9)]}, out)
        self.assertEqual(len(out["release_also"]), 4)
        # ...and the console's choice to pin no key, as it keeps unsigned_ok: its own word only.
        self.assertFalse(out["release_unpinned"])
        for said, kept in ((True, True), (1, False), ("yes", False), (None, False)):
            nodes._c_release({"release_unpinned": said}, out)
            self.assertIs(out["release_unpinned"], kept, said)
        self.assertIn("release_unpinned", next(keys for keys, fn in nodes.CENSUS if fn is nodes._c_release))
        self.assertIn("release_also", next(keys for keys, fn in nodes.CENSUS if fn is nodes._c_release))


class FromBefore(Case):
    def test_a_record_from_before_the_list_loads_as_it_did(self):
        before = {"node_id": "n_1", "token": "bbn_1", "controller": "https://c", "release_key": self.pub,
                  "release_spare": self.spare, "unsigned_ok": True, "root_off": True, "stores": {"data": "/srv/data"}}
        self.write(before)
        state = self.stores.load_state()
        self.assertEqual(state, before)
        self.assertEqual(self.release.also(state), [])
        self.assertFalse(self.release.unpinned(state))
        self.assertEqual(self.release.trusted(state), self.release.keys(state))
        self.assertEqual(self.release.may_install(state, DIGEST, self.sign(self.k)),
                         (True, f"signed by the release key this node pinned ({self.pub[:16]}…)"))
        self.assertEqual(self.release.may_install({}, DIGEST, "")[0], True)
        # The agent's own save writes it back as it was, with no list.
        self.stores.save_state(dict(state))
        self.assertEqual(self.read(), before)
        self.assertEqual(self.stores.console_said(), {k: before[k] for k in ("release_key", "release_spare", "unsigned_ok", "root_off")})


if __name__ == "__main__":
    unittest.main()
