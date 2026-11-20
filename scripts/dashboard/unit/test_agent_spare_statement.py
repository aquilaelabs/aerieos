"""A node that pinned the release key pins its spare by itself (R267 step
16). A release's build signs, with the release key itself, a statement that
names the spare, under a line of its own: tools/sign-agent.py writes it into
agent.sig when the key it signs with is the first one
config/aerieos-release.pub names and the file names a spare, and --check
holds it. The controller hands it on in every hello and beside every agent
update. A node that holds the first key and no spare pins the spare named
when the statement's signature is the key's it pinned, says so once, and
reports the spare as it reports its keys. Nothing else changes a key: a
controller's own word adds none, a node that has a spare keeps it, a node
whose console chose to pin no key is left as it is, a statement under any
other key (one added at the console among them) pins nothing, and a
builder's key makes no such statement. An agent from before this reads
neither field, and everything it does read is where it was."""
import json
import os
import shutil
import subprocess
import sys
import tempfile
import threading
import unittest
from unittest import mock

HERE = os.path.dirname(os.path.abspath(__file__))
REPO = os.path.normpath(os.path.join(HERE, "..", "..", ".."))
sys.path.insert(0, HERE)
sys.path.insert(0, os.path.join(HERE, ".."))
sys.path.insert(0, os.path.join(REPO, "scripts", "lib"))
import agentpkg  # noqa: E402
import bundleparts  # noqa: E402
import enrollscript  # noqa: E402
import nodes  # noqa: E402
from cryptography.hazmat.primitives.asymmetric.ed25519 import Ed25519PrivateKey  # noqa: E402

DIGEST = "sha256:" + "ab" * 32
NEW = b"#!/bin/sh\n# an agent build from before the start check\n"
RECORD = {"node_id": "n_1", "token": "bbn_1", "controller": "http://127.0.0.1:1", "stores": {"data": "/srv/data"}}


def pair():
    k = Ed25519PrivateKey.generate()
    return k, k.public_key().public_bytes_raw().hex()


class Case(unittest.TestCase):
    def setUp(self):
        self.agent = agentpkg.load("aerieos_agent_spare_statement")
        self.said = []
        self.agent.log = lambda msg, *a, **k: self.said.append(msg)
        self.release, self.stores = self.agent.module("release"), self.agent.module("stores")
        self.d = tempfile.mkdtemp()
        self.addCleanup(shutil.rmtree, self.d, True)
        self.nj = os.path.join(self.d, "node.json")
        self.agent.NODE_JSON = self.nj
        self.k, self.pub = pair()
        self.s, self.spare = pair()

    def statement(self, by=None, names=None):
        """The words a build signs: `by` says its spare is `names`."""
        names = names or self.spare
        return {"key": names, "sig": (by or self.k).sign(self.release.SPARE_MESSAGE + names.encode()).hex()}

    def write(self, state):
        with open(self.nj, "w") as f:
            json.dump(state, f)

    def read(self):
        with open(self.nj) as f:
            return json.load(f)


class Decided(Case):
    def test_the_pinned_keys_statement_names_the_spare_to_pin(self):
        self.assertEqual(self.release.spare_pin({"release_key": self.pub}, self.statement()), self.spare)
        # Keys added at the console beside the release key change nothing of it.
        _, mine = pair()
        self.assertEqual(self.release.spare_pin({"release_key": self.pub, "release_also": [mine]}, self.statement()), self.spare)

    def test_a_node_that_has_a_spare_keeps_it(self):
        _, theirs = pair()
        for held in (self.spare, theirs):
            self.assertEqual(self.release.spare_pin({"release_key": self.pub, "release_spare": held}, self.statement()), "")

    def test_a_node_whose_console_chose_its_keys_is_left_as_it_is(self):
        for state in ({"release_unpinned": True}, {"release_unpinned": True, "release_key": self.pub},
                      {"release_unpinned": True, "release_also": [self.pub]}):
            self.assertEqual(self.release.spare_pin(state, self.statement()), "", state)

    def test_a_node_with_no_release_key_pins_nothing_from_it(self):
        for state in ({}, {"release_also": [self.pub]}, {"release_spare": self.spare}):
            self.assertEqual(self.release.spare_pin(state, self.statement()), "", state)

    def test_a_statement_under_any_other_key_pins_nothing(self):
        other, theirs = pair()
        state = {"release_key": self.pub, "release_also": [theirs]}
        # Another key's word, a key added at the console among them, and the spare's word for itself.
        self.assertEqual(self.release.spare_pin(state, self.statement(by=other)), "")
        self.assertEqual(self.release.spare_pin(state, self.statement(by=self.s)), "")
        # The right key's word for another key is not a word for this one.
        said = self.statement()
        self.assertEqual(self.release.spare_pin(state, dict(said, key=theirs)), "")
        # ...and a key is not its own spare.
        self.assertEqual(self.release.spare_pin(state, self.statement(names=self.pub)), "")

    def test_a_controllers_own_word_adds_no_key(self):
        state = {"release_key": self.pub}
        sig = self.statement()["sig"]
        for said in (None, "", self.spare, [self.spare], {}, {"key": self.spare}, {"key": self.spare, "sig": ""},
                     {"key": self.spare, "sig": "00" * 64}, {"key": self.spare, "sig": 7}, {"key": 7, "sig": sig},
                     {"key": "nope", "sig": sig}, {"sig": sig}):
            self.assertEqual(self.release.spare_pin(state, said), "", said)

    def test_a_signature_made_for_anything_else_names_no_spare(self):
        # The release key's signature over an agent, root's tools or a
        # bundle's list whose "digest" were the spare's hex is no statement.
        for line in (self.release.MESSAGE, self.release.TOOLS_MESSAGE, self.release.BUNDLE_MESSAGE):
            said = {"key": self.spare, "sig": self.k.sign(line + self.spare.encode()).hex()}
            self.assertEqual(self.release.spare_pin({"release_key": self.pub}, said), "", line)
        # ...and the statement passes as none of them.
        for line in (self.release.MESSAGE, self.release.TOOLS_MESSAGE, self.release.BUNDLE_MESSAGE):
            self.assertTrue(self.release.verify(self.pub, "sha256:" + self.spare, self.statement()["sig"], line))


class Written(Case):
    def test_the_spare_is_written_beside_the_key_as_the_console_writes_it(self):
        self.write(dict(RECORD, release_key=self.pub))
        self.assertTrue(self.stores.pin_spare(self.pub, self.spare))
        self.assertEqual(self.read(), dict(RECORD, release_key=self.pub, release_spare=self.spare))
        self.assertEqual(os.stat(self.nj).st_mode & 0o777, 0o600)
        self.assertEqual([n for n in os.listdir(self.d) if n not in ("node.json", ".node.json.lock")], [], "no half-written file is left")
        # The agent's own save, from a copy made before, keeps it; and it is in what the node reports.
        self.stores.save_state(dict(RECORD, token="bbn_2"))
        self.assertEqual(self.read(), dict(RECORD, token="bbn_2", release_key=self.pub, release_spare=self.spare))
        self.assertEqual(self.stores.console_said()["release_spare"], self.spare)

    def test_what_a_person_did_at_the_console_meanwhile_stands(self):
        _, theirs = pair()
        for held in ({"release_key": self.pub, "release_spare": theirs}, {"release_key": theirs}, {},
                     {"release_unpinned": True}, {"release_key": self.pub, "release_unpinned": True}):
            self.write(dict(RECORD, **held))
            self.assertFalse(self.stores.pin_spare(self.pub, self.spare), held)
            self.assertEqual(self.read(), dict(RECORD, **held))
        self.write(dict(RECORD, release_key=self.pub))
        for bad in ("", "nope", self.pub):
            self.assertFalse(self.stores.pin_spare(self.pub, bad))
        self.assertEqual(self.read(), dict(RECORD, release_key=self.pub))

    def test_a_record_that_cannot_be_read_or_written_is_an_error_and_stays_as_it_was(self):
        with self.assertRaises(OSError):
            self.stores.pin_spare(self.pub, self.spare)
        was = dict(RECORD, release_key=self.pub)
        self.write(was)
        with mock.patch.object(self.stores.os, "replace", side_effect=OSError(28, "No space left on device")), self.assertRaises(OSError):
            self.stores.pin_spare(self.pub, self.spare)
        self.assertEqual(self.read(), was)


class OnTheNode(Case):
    """The running agent: the hello's answer, and an update's spec."""

    def setUp(self):
        super().setUp()
        self.me = os.path.join(self.d, "aerieos-agent")
        with open(self.me, "wb") as f:
            f.write(b"OLD")
        self.agent.own_path = lambda: self.me
        self.agent.own_digest = lambda: "sha256:" + "0" * 64
        self.a = object.__new__(self.agent.Agent)
        self.a.state, self.a.jobs, self.a.lock = dict(RECORD), {}, threading.Lock()
        self.a.hello_at = 5

    def hello(self, **named):
        self.a.shipped_named({"digest": DIGEST, "version": "0.9.999", "sig": "ab" * 64, "release_keys": [self.pub, self.spare], **named})

    def test_a_hello_that_carries_the_statement_pins_the_spare_and_says_so_once(self):
        self.write(dict(RECORD, release_key=self.pub))
        self.hello(release_spare_sig=self.statement())
        self.assertEqual(self.read(), dict(RECORD, release_key=self.pub, release_spare=self.spare))
        pinned = [m for m in self.said if "pinned the release key's spare" in m]
        self.assertEqual(len(pinned), 1, self.said)
        self.assertIn(f"({self.spare[:16]}…)", pinned[0])
        self.assertNotIn(self.spare, pinned[0], "a log line names a key by its first characters")
        self.assertEqual(self.a.hello_at, 0, "a hello follows, so the row reads the spare now")
        # What the hello named of the update is kept as before.
        self.assertEqual((self.a.controller_digest, self.a.controller_sig, self.a.controller_keys),
                         (DIGEST, "ab" * 64, [self.pub, self.spare]))
        # The next hello says the same and nothing happens: not said again, no hello asked for.
        self.a.hello_at = 5
        self.hello(release_spare_sig=self.statement())
        self.assertEqual(len([m for m in self.said if "pinned the release key's spare" in m]), 1)
        self.assertEqual(self.a.hello_at, 5)
        # The census the node reports carries the spare, shortened, as it carries the key.
        said = self.stores.console_said()
        self.assertEqual((said["release_key"], said["release_spare"]), (self.pub, self.spare))

    def test_a_hello_with_no_statement_or_another_keys_changes_nothing(self):
        other, _ = pair()
        was = dict(RECORD, release_key=self.pub)
        self.write(was)
        for named in ({}, {"release_spare_sig": self.statement(by=other)}, {"release_spare_sig": self.spare},
                      {"release_spare_sig": {"key": self.spare}}):
            self.hello(**named)
            self.assertEqual(self.read(), was, named)
        self.assertEqual((self.said, self.a.hello_at), ([], 5))
        # A hello that names nothing of the agent at all is read as before.
        self.a.shipped_named(None)
        self.assertEqual((self.a.controller_digest, self.a.controller_sig, self.a.controller_keys), ("", "", []))

    def test_a_node_whose_console_chose_or_has_a_spare_is_left_as_it_is(self):
        _, theirs = pair()
        for held in ({"release_key": self.pub, "release_spare": theirs}, {"release_unpinned": True}, {},
                     {"release_also": [self.pub]}):
            was = dict(RECORD, **held)
            self.write(was)
            self.hello(release_spare_sig=self.statement())
            self.assertEqual(self.read(), was, held)
        self.assertEqual(self.said, [])

    def test_a_spare_that_cannot_be_written_is_tried_again_and_nothing_is_lost(self):
        was = dict(RECORD, release_key=self.pub)
        self.write(was)
        with mock.patch.object(self.stores.os, "replace", side_effect=OSError(28, "No space left on device")):
            self.hello(release_spare_sig=self.statement())
        self.assertEqual(self.read(), was)
        self.assertEqual(self.a.hello_at, 5)
        self.hello(release_spare_sig=self.statement())
        self.assertEqual(self.read(), dict(was, release_spare=self.spare))

    def update(self, body=NEW, **spec):
        class Ctl:
            @staticmethod
            def call(*args, **kw):
                return 200, body

        class Job:
            job, why, installed, said = {"id": "j_up"}, "", False, ""

            def say(self, text):
                self.said += text

        self.a.ctl, job = Ctl(), Job()
        self.a.controller_digest = self.a.controller_sig = ""
        return self.a.self_update(job, spec), job

    def test_an_update_that_carries_the_statement_pins_the_spare_and_is_judged_by_both(self):
        import hashlib
        got = "sha256:" + hashlib.sha256(NEW).hexdigest()
        self.write(dict(RECORD, release_key=self.pub))
        # Signed by the spare alone: refused by a node that holds the first key only...
        by_spare = self.s.sign(self.release.MESSAGE + got.encode()).hex()
        (state, code), job = self.update(sig=by_spare)
        self.assertEqual((state, code), ("failed", 77), job.said)
        # ...and taken once the release key's own word names that spare.
        (state, code), job = self.update(sig=by_spare, release_spare_sig=self.statement())
        self.assertEqual((state, code, job.installed), ("succeeded", 0, True), job.said)
        self.assertIn("pinned the release key's spare", job.said)
        self.assertIn("signed by the spare release key this node pinned", job.said)
        self.assertEqual(self.read(), dict(RECORD, release_key=self.pub, release_spare=self.spare))

    def test_a_statement_under_another_key_does_not_carry_an_update_in(self):
        import hashlib
        got = "sha256:" + hashlib.sha256(NEW).hexdigest()
        other, theirs = pair()
        was = dict(RECORD, release_key=self.pub)
        self.write(was)
        # A controller that makes a key, calls it the spare and signs with it.
        said = {"key": theirs, "sig": other.sign(self.release.SPARE_MESSAGE + theirs.encode()).hex()}
        (state, code), job = self.update(sig=other.sign(self.release.MESSAGE + got.encode()).hex(), release_spare_sig=said)
        self.assertEqual((state, code, job.installed), ("failed", 77, False), job.said)
        self.assertEqual(self.read(), was)
        with open(self.me, "rb") as f:
            self.assertEqual(f.read(), b"OLD")


class Controller(unittest.TestCase):
    """The controller's half: the statement its build carries, passed on in
    every hello and beside every agent update, and nothing of what an
    earlier agent reads moved."""

    def setUp(self):
        nodes.configure(state=tempfile.mkdtemp())
        nodes._auto_tried.clear()
        mint = nodes.enroll_mint("user:test", "box")
        self.census = {"cpu": 2, "mem_mb": 4096, "arch": "x86_64", "system": "linux", "session": {"up": True, "user": "b"}}
        nodes.enroll(nodes.authenticate(mint["token"]), self.census, "box.lan", user="bb")
        self.nid = mint["id"]
        self.d = tempfile.mkdtemp()
        self.addCleanup(shutil.rmtree, self.d, True)
        self.k, self.pub = pair()
        _, self.spare = pair()

    def spec(self):
        nodes._exec("UPDATE nodes SET agent = json_set(agent, '$.digest', ?) WHERE id = ?", ("sha256:" + "0" * 64, self.nid))
        r = nodes.node_update_agent("user:test", self.nid)
        self.assertTrue(r.get("job"), r)
        return next(j for j in nodes.jobs_for(node_id=self.nid, n=10, active=True) if j["id"] == r["job"])["spec"]

    def sig_file(self, **parts):
        with open(os.path.join(self.d, "agent.sig"), "w") as f:
            json.dump({"digest": DIGEST, "sig": "ab" * 64, "key": self.pub, **parts}, f)

    def test_the_statement_is_read_from_the_builds_signature_file_as_it_is(self):
        import pathlib
        said = {"key": self.spare, "sig": "cd" * 64}
        with mock.patch.object(nodes, "AGENT_DIR", pathlib.Path(self.d)):
            self.assertEqual(nodes.agent_spare_said(), {}, "no signature file: an unsigned build")
            self.sig_file()
            self.assertEqual(nodes.agent_spare_said(), {}, "a build the spare or a builder signed carries none")
            self.sig_file(spare=said)
            self.assertEqual(nodes.agent_spare_said(), {"release_spare_sig": said})
            for bad in ("x", [], {"key": self.spare}, {"key": "nope", "sig": "cd" * 64}, {"key": self.spare, "sig": "cd"}):
                self.sig_file(spare=bad)
                self.assertEqual(nodes.agent_spare_said(), {}, bad)

    def test_the_hello_and_the_update_carry_it_beside_what_they_carried(self):
        said = {"release_spare_sig": {"key": self.spare, "sig": "cd" * 64}}
        with mock.patch.object(nodes, "agent_spare_said", lambda: {}):
            hello, spec = nodes.hello(self.nid, self.census, "box.lan")["agent"], self.spec()
        self.assertNotIn("release_spare_sig", hello)
        self.assertNotIn("release_spare_sig", spec)
        for j in nodes.jobs_for(node_id=self.nid, n=10, active=True):
            nodes._exec("UPDATE jobs SET state = 'canceled' WHERE id = ?", (j["id"],))
        with mock.patch.object(nodes, "agent_spare_said", lambda: said):
            hello2, spec2 = nodes.hello(self.nid, self.census, "box.lan")["agent"], self.spec()
        # An agent from before this reads digest, version, sig and release_keys: each is where and what it was.
        self.assertEqual({k: v for k, v in hello2.items() if k != "release_spare_sig"}, hello)
        self.assertEqual({k: v for k, v in spec2.items() if k != "release_spare_sig"}, spec)
        self.assertEqual((hello2["release_spare_sig"], spec2["release_spare_sig"]), (said["release_spare_sig"],) * 2)
        self.assertEqual(hello2["release_keys"], enrollscript.release_keys())

    def test_the_page_is_told_whether_this_build_vouches_for_its_spare(self):
        for said, want in (({}, False), ({"release_spare_sig": {"key": self.spare, "sig": "cd" * 64}}, True)):
            with mock.patch.object(nodes, "agent_spare_said", lambda said=said: said):
                self.assertIs(nodes.tab_view([], True)["agent"]["spare_said"], want)


class Signer(unittest.TestCase):
    """tools/sign-agent.py makes the statement and --check holds it. The
    signer reads the tree it sits in, so each test runs a copy of it in a
    tree of its own."""

    def setUp(self):
        self.t = tempfile.mkdtemp()
        self.addCleanup(shutil.rmtree, self.t, True)
        for name, path in bundleparts.files(REPO):
            os.makedirs(os.path.dirname(os.path.join(self.t, name)), exist_ok=True)
            shutil.copy(path, os.path.join(self.t, name))
        shutil.copytree(os.path.join(REPO, "scripts", "agent"), os.path.join(self.t, "scripts", "agent"),
                        ignore=shutil.ignore_patterns("__pycache__", "agent.sig"))
        os.makedirs(os.path.join(self.t, "tools"))
        shutil.copy(os.path.join(REPO, "tools", "sign-agent.py"), os.path.join(self.t, "tools"))
        self.sig = os.path.join(self.t, "scripts", "agent", "agent.sig")
        self.k, self.pub = pair()
        self.s, self.spare = pair()
        self.named = os.path.join(self.t, "release.pub")
        self.names(self.pub, self.spare)
        sys.path.insert(0, os.path.join(REPO, "scripts", "agent"))
        from aerieos_agent import release
        self.release = release

    def names(self, *keys):
        with open(self.named, "w") as f:
            f.write("".join(f"aerieos-release-ed25519 {k}\n" for k in keys))

    def signer(self, *args, key=None):
        env = {**os.environ, "AERIEOS_RELEASE_PUB": self.named}
        env.pop("AERIEOS_RELEASE_KEY", None)
        if key is not None:
            env["AERIEOS_RELEASE_KEY"] = key.private_bytes_raw().hex()
        return subprocess.run([sys.executable, os.path.join(self.t, "tools", "sign-agent.py"), *args],
                              capture_output=True, text=True, env=env, timeout=120, check=False)

    def read_sig(self, path=None):
        with open(path or self.sig) as f:
            return json.load(f)

    def put_sig(self, got):
        with open(self.sig, "w") as f:
            json.dump(got, f)

    def test_the_release_key_states_its_spare_and_a_node_pins_it_from_that(self):
        r = self.signer(key=self.k)
        self.assertEqual(r.returncode, 0, r.stdout + r.stderr)
        self.assertIn(f"and named its spare {self.spare[:16]}…", r.stdout)
        said = self.read_sig()["spare"]
        self.assertEqual(said["key"], self.spare)
        self.assertEqual(self.release.spare_said(self.pub, said), self.spare)
        self.assertEqual(self.release.spare_pin({"release_key": self.pub}, said), self.spare)
        self.assertEqual(self.release.spare_pin({"release_key": self.spare}, said), "", "the spare's holder is told nothing by it")
        r = self.signer("--check")
        self.assertEqual(r.returncode, 0, r.stdout)
        self.assertIn(f"the spare: named by {self.pub[:16]}… as {self.spare[:16]}…", r.stdout)

    def test_check_fails_a_release_keys_build_whose_statement_is_missing_or_wrong(self):
        self.assertEqual(self.signer(key=self.k).returncode, 0)
        whole = self.read_sig()
        other, theirs = pair()
        for spare, why in ((None, "it does not name the release key's spare"),
                           ({"key": theirs, "sig": whole["spare"]["sig"]}, "its statement of the spare is not signed by the release key"),
                           ({"key": theirs, "sig": other.sign(self.release.SPARE_MESSAGE + theirs.encode()).hex()},
                            "its statement of the spare is not signed by the release key"),
                           ({"key": theirs, "sig": self.k.sign(self.release.SPARE_MESSAGE + theirs.encode()).hex()},
                            "it names another spare than"),
                           ("nope", "its statement of the spare is not signed by the release key")):
            got = dict(whole)
            if spare is None:
                del got["spare"]
            else:
                got["spare"] = spare
            self.put_sig(got)
            r = self.signer("--check")
            self.assertEqual(r.returncode, 1, r.stdout)
            self.assertIn("the spare: " + why, r.stdout)
            self.assertIn("the bundle's files: signed by", r.stdout, "the other parts still stand")
        self.put_sig(whole)
        self.assertEqual(self.signer("--check").returncode, 0)

    def test_the_spare_a_file_with_one_key_and_a_builder_state_nothing(self):
        # Signed by the spare: the first key did not sign, so nothing says what its spare is.
        r = self.signer(key=self.s)
        self.assertEqual(r.returncode, 0, r.stdout + r.stderr)
        self.assertIn("with the spare release key", r.stdout)
        self.assertNotIn("named its spare", r.stdout)
        self.assertNotIn("spare", self.read_sig())
        r = self.signer("--check")
        self.assertEqual(r.returncode, 0, r.stdout)
        self.assertNotIn("the spare:", r.stdout)
        # A file that names one key has no spare to state.
        self.names(self.pub)
        r = self.signer(key=self.k)
        self.assertEqual(r.returncode, 0, r.stdout + r.stderr)
        self.assertNotIn("spare", self.read_sig())
        self.assertEqual(self.signer("--check").returncode, 0)
        # ...and a statement left in a file whose key file names none fails the check.
        self.put_sig(dict(self.read_sig(), spare={"key": self.spare, "sig": self.k.sign(self.release.SPARE_MESSAGE + self.spare.encode()).hex()}))
        r = self.signer("--check")
        self.assertEqual(r.returncode, 1, r.stdout)
        self.assertIn("the spare: it names a spare and", r.stdout)
        # A builder's key is no release key: its build says nothing of a spare.
        self.names(self.pub, self.spare)
        key = os.path.join(self.t, "builder.key")
        out = os.path.join(self.t, "builder.sig")
        self.assertEqual(self.signer("--builder-keygen", key).returncode, 0)
        r = self.signer("--builder", key, "--out", out)
        self.assertEqual(r.returncode, 0, r.stdout + r.stderr)
        self.assertNotIn("spare", self.read_sig(out))


if __name__ == "__main__":
    unittest.main()
