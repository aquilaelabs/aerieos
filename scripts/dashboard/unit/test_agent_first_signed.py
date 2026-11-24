"""A node with no key pins AerieOS's release key on its first signed update
(release.first_pin). Its controller names the release keys its own build
carries beside every update; when the update's signature is under one of
them, the node installs it and pins that one key, the one the signature
held under, and the job says so. A second key the controller named is its
bare word and pins nothing: the spare is pinned on the pinned key's own
signed statement, in the same update where it carries one. An update with no signature, or
one under another key, is taken as it was and said as unchecked, and pins
nothing. A node that has any key is unchanged: what a controller names is
never read there, and neither is a node whose console chose to pin no key
(release-key none, node.json's release_unpinned): it takes the update, says
whose choice that was, and pins nothing until a person pins a key there
again. The pin is written into node.json whole, as the console writes it,
and one that cannot be written installs nothing."""
import hashlib
import json
import os
import sys
import tempfile
import threading
import unittest
from unittest import mock

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)
sys.path.insert(0, os.path.join(HERE, ".."))
import agentpkg  # noqa: E402
import enrollscript  # noqa: E402
import nodes  # noqa: E402
from cryptography.hazmat.primitives.asymmetric.ed25519 import Ed25519PrivateKey  # noqa: E402

DIGEST = "sha256:" + "ab" * 32
# An update as a node is sent one: this tree's agent by its version, with no start check in it.
NEW = agentpkg.an_agent()
RECORD = {"node_id": "n_1", "token": "bbn_1", "controller": "http://127.0.0.1:1", "stores": {"data": "/srv/data"}}


def pair():
    k = Ed25519PrivateKey.generate()
    return k, k.public_key().public_bytes_raw().hex()


def digest(body):
    return "sha256:" + hashlib.sha256(body).hexdigest()


class Case(unittest.TestCase):
    def setUp(self):
        self.agent = agentpkg.load("aerieos_agent_first_signed")
        self.agent.log = lambda *a, **k: None
        self.release, self.stores = self.agent.module("release"), self.agent.module("stores")
        self.d = tempfile.mkdtemp()
        self.nj = os.path.join(self.d, "node.json")
        self.agent.NODE_JSON = self.nj
        self.k, self.pub = pair()
        self.s, self.spare = pair()

    def sign(self, key, of=DIGEST):
        return key.sign(self.release.MESSAGE + of.encode()).hex()

    def write(self, state):
        with open(self.nj, "w") as f:
            json.dump(state, f)

    def read(self):
        with open(self.nj) as f:
            return json.load(f)


class Decided(Case):
    def test_a_first_update_under_a_named_key_is_taken_and_names_what_to_pin(self):
        named = [self.pub, self.spare]
        for signer in (self.k, self.s):
            sig = self.sign(signer)
            ok, said = self.release.may_install({}, DIGEST, sig, named)
            self.assertTrue(ok)
            key = signer.public_key().public_bytes_raw().hex()
            self.assertEqual(said, f"signed by a release key this node's controller names ({key[:16]}…), with none pinned here yet")
            self.assertEqual(self.release.first_pin({}, DIGEST, sig, named), [key], "the one the signature is under, and no other named")
        self.assertEqual(self.release.first_pin({}, DIGEST, self.sign(self.k), [self.pub]), [self.pub])

    def test_an_unsigned_or_wrongly_signed_first_update_is_taken_said_and_pins_nothing(self):
        other, _ = pair()
        named = [self.pub, self.spare]
        for sig, why in (("", "the controller sent no signature with it"),
                         (self.sign(other), "its signature is not under a release key the controller named"),
                         (self.sign(self.k, "sha256:" + "cd" * 32), "its signature is not under a release key the controller named"),
                         (self.k.sign(b"aerieos bundle v1\n" + DIGEST.encode()).hex(), "its signature is not under a release key")):
            ok, said = self.release.may_install({}, DIGEST, sig, named)
            self.assertTrue(ok)
            self.assertIn("not checked: no release key is pinned here", said)
            self.assertIn(why, said)
            self.assertEqual(self.release.first_pin({}, DIGEST, sig, named), [])

    def test_a_controller_that_names_no_keys_is_taken_as_before_and_said(self):
        # A controller from before the naming, or a build that carries none.
        sig = self.sign(self.k)
        for named in (None, [], "", [self.pub, "nope"], [self.pub, self.spare, pair()[1]], [5], {"a": self.pub}, self.pub):
            ok, said = self.release.may_install({}, DIGEST, sig, named)
            self.assertTrue(ok)
            self.assertEqual(said, "not checked: no release key is pinned here, and no release key was named to check its signature against")
            self.assertEqual(self.release.first_pin({}, DIGEST, sig, named), [], named)
        self.assertEqual(self.release.may_install({}, DIGEST, ""),
                         (True, "not checked: no release key is pinned here, and the controller sent no signature with it"))

    def test_a_node_that_has_any_key_is_unchanged_by_what_a_controller_names(self):
        t, theirs = pair()
        _, mine = pair()
        sig = self.sign(t)
        for state in ({"release_key": self.pub}, {"release_key": self.pub, "release_spare": self.spare}, {"release_spare": self.spare},
                      {"release_also": [mine]}, {"release_key": self.pub, "unsigned_ok": True}):
            self.assertEqual(self.release.first_pin(state, DIGEST, sig, [theirs]), [], state)
            self.assertEqual(self.release.may_install(state, DIGEST, sig, [theirs]), self.release.may_install(state, DIGEST, sig), state)
            self.assertNotIn(theirs[:16], self.release.may_install(state, DIGEST, sig, [theirs])[1])
        self.assertFalse(self.release.may_install({"release_key": self.pub}, DIGEST, sig, [theirs])[0])


    def test_a_node_whose_console_chose_no_key_pins_none_and_says_whose_choice(self):
        named = [self.pub, self.spare]
        chose = {"release_unpinned": True}
        for sig in (self.sign(self.k), self.sign(self.s), ""):
            self.assertEqual(self.release.may_install(chose, DIGEST, sig, named),
                             (True, "not checked: this node's console chose to pin no release key"))
            self.assertEqual(self.release.first_pin(chose, DIGEST, sig, named), [])
        self.assertTrue(self.release.unpinned(chose))
        # Only the console's own word is the choice: a record from before
        # the field, or one that holds anything else there, pins as built.
        for state in ({}, {"release_unpinned": False}, {"release_unpinned": "yes"}, {"release_unpinned": 1}, {"unsigned_ok": True}):
            self.assertFalse(self.release.unpinned(state), state)
            self.assertEqual(self.release.first_pin(state, DIGEST, self.sign(self.k), named), [self.pub], state)
        # A key trusted here is checked as ever, whatever was chosen before it.
        _, mine = pair()
        self.assertFalse(self.release.may_install({"release_unpinned": True, "release_also": [mine]}, DIGEST, self.sign(self.k), named)[0])


class Written(Case):
    def test_the_choice_to_pin_none_is_kept_and_nothing_is_written_over_it(self):
        chose = dict(RECORD, release_unpinned=True)
        self.write(chose)
        self.assertFalse(self.stores.pin_release([self.pub, self.spare]))
        self.assertEqual(self.read(), chose)
        # The agent's own saves keep the file's word for it: a copy from
        # before the choice does not take it away, and one cannot make it.
        self.assertIn("release_unpinned", self.stores.CONSOLE_KEYS)
        self.stores.save_state(dict(RECORD, token="bbn_2"))
        self.assertEqual(self.read(), dict(chose, token="bbn_2"))
        self.assertEqual(self.stores.console_said(), {"release_unpinned": True})
        self.write(RECORD)
        self.stores.save_state(dict(RECORD, token="bbn_3", release_unpinned=True))
        self.assertEqual(self.read(), dict(RECORD, token="bbn_3"))

    def test_the_pin_is_written_into_the_record_as_the_console_writes_it(self):
        self.write(RECORD)
        self.assertTrue(self.stores.pin_release([self.pub, self.spare]))
        self.assertEqual(self.read(), dict(RECORD, release_key=self.pub, release_spare=self.spare))
        self.assertEqual(os.stat(self.nj).st_mode & 0o777, 0o600)
        self.assertEqual([n for n in os.listdir(self.d) if n not in ("node.json", ".node.json.lock")], [], "no half-written file is left")
        # The agent's own save, from a copy made before, keeps it.
        self.stores.save_state(dict(RECORD, token="bbn_2"))
        self.assertEqual(self.read(), dict(RECORD, token="bbn_2", release_key=self.pub, release_spare=self.spare))

    def test_a_key_already_there_is_never_replaced_or_joined(self):
        _, theirs = pair()
        _, mine = pair()
        for held in ({"release_key": self.pub}, {"release_spare": self.spare}, {"release_also": [mine]}):
            self.write(dict(RECORD, **held))
            self.assertFalse(self.stores.pin_release([theirs]))
            self.assertEqual(self.read(), dict(RECORD, **held))
        # What is not a key, or more than a key and its spare, pins nothing.
        self.write(RECORD)
        for bad in ([], ["nope"], [self.pub, "nope"], [self.pub, self.spare, theirs]):
            self.assertFalse(self.stores.pin_release(bad))
        self.assertEqual(self.read(), RECORD)

    def test_a_record_that_cannot_be_read_or_written_is_an_error_and_stays_as_it_was(self):
        with self.assertRaises(OSError):
            self.stores.pin_release([self.pub])
        self.assertFalse(os.path.exists(self.nj))
        with open(self.nj, "w") as f:
            f.write("not json")
        with self.assertRaises(ValueError):
            self.stores.pin_release([self.pub])
        self.write(RECORD)
        with mock.patch.object(self.stores.os, "replace", side_effect=OSError(28, "No space left on device")), self.assertRaises(OSError):
            self.stores.pin_release([self.pub])
        self.assertEqual(self.read(), RECORD)
        self.assertEqual([n for n in os.listdir(self.d) if n not in ("node.json", ".node.json.lock")], [])


class Update(Case):
    """The self-update itself, on a node whose agent is a file in a folder
    of the test's own."""

    def setUp(self):
        super().setUp()
        self.me = os.path.join(self.d, "aerieos-agent")
        with open(self.me, "wb") as f:
            f.write(b"OLD")
        self.agent.own_path = lambda: self.me
        self.agent.own_digest = lambda: digest(b"OLD")
        self.write(RECORD)

    def update(self, body=NEW, hello=None, **spec):
        a = object.__new__(self.agent.Agent)
        a.state, a.jobs, a.lock, a.controller_digest, a.controller_sig = dict(RECORD), {}, threading.Lock(), "", ""
        if hello is not None:
            a.controller_sig, a.controller_keys = hello.get("sig", ""), hello.get("release_keys", [])
            a.controller_spare = hello.get("release_spare_sig")

        class Ctl:
            @staticmethod
            def call(*args, **kw):
                return 200, body

        class Job:
            job, why, installed, said = {"id": "j_up"}, "", False, ""

            def say(self, text):
                self.said += text

        a.ctl, job = Ctl(), Job()
        return a.self_update(job, spec), job

    def installed(self):
        with open(self.me, "rb") as f:
            return f.read()

    def beside(self):
        return sorted(n for n in os.listdir(self.d) if n not in ("aerieos-agent", "node.json", ".node.json.lock"))

    def statement(self, by=None, names=None):
        """The release key's own word that `names` is its spare, as of this
        agent's build."""
        names, build = names or self.spare, self.release.own_build()
        return {"key": names, "build": build, "build_sig": (by or self.k).sign(self.release.spare_built(names, build)).hex()}

    def test_the_first_signed_update_is_installed_and_pins_the_key_it_is_under(self):
        (state, code), job = self.update(sig=self.sign(self.k, digest(NEW)), release_keys=[self.pub, self.spare],
                                         release_spare_sig=self.statement())
        self.assertEqual((state, code, job.installed), ("succeeded", 0, True), job.said)
        self.assertEqual(self.installed(), NEW)
        self.assertEqual(self.read(), dict(RECORD, release_key=self.pub, release_spare=self.spare))
        self.assertIn(f"pinned AerieOS's release key on this first signed update ({self.pub[:16]}…): from here", job.said)
        self.assertIn(f"pinned the release key's spare ({self.spare[:16]}…), named by the release key this node pinned", job.said)
        # From here it is a pinned node: the next one is checked.
        with open(self.me, "wb") as f:
            f.write(b"OLD")
        other = agentpkg.an_agent(note="another build")
        (state, code), job = self.update(other)
        self.assertEqual((state, code), ("failed", 77))
        self.assertEqual(self.installed(), b"OLD")
        (state, code), job = self.update(other, sig=self.sign(self.s, digest(other)))
        self.assertEqual((state, code), ("succeeded", 0), job.said)
        self.assertIn("signed by the spare release key this node pinned", job.said)
        self.assertNotIn("first signed update", job.said)

    def test_a_second_key_is_pinned_on_the_first_s_signed_word_alone(self):
        (state, code), job = self.update(sig=self.sign(self.k, digest(NEW)), release_keys=[self.pub])
        self.assertEqual((state, code), ("succeeded", 0), job.said)
        self.assertEqual(self.read(), dict(RECORD, release_key=self.pub))
        self.assertIn(f"pinned AerieOS's release key on this first signed update ({self.pub[:16]}…): from here", job.said)
        self.write(RECORD)
        with open(self.me, "wb") as f:
            f.write(b"OLD")
        # A second key named with no statement of the first's is the
        # controller's bare word: the first is pinned and it is not.
        (state, code), job = self.update(sig=self.sign(self.k, digest(NEW)), release_keys=[self.pub, self.spare])
        self.assertEqual((state, code), ("succeeded", 0), job.said)
        self.assertEqual(self.read(), dict(RECORD, release_key=self.pub))
        # ...and neither is one under a statement another key signed.
        other, theirs = pair()
        self.write(RECORD)
        with open(self.me, "wb") as f:
            f.write(b"OLD")
        (state, code), job = self.update(sig=self.sign(self.k, digest(NEW)), release_keys=[self.pub, theirs],
                                         release_spare_sig=self.statement(by=other, names=theirs))
        self.assertEqual(self.read(), dict(RECORD, release_key=self.pub))
        # An update the spare signed pins the spare, the one key it is under.
        self.write(RECORD)
        with open(self.me, "wb") as f:
            f.write(b"OLD")
        (state, code), job = self.update(sig=self.sign(self.s, digest(NEW)), release_keys=[self.pub, self.spare])
        self.assertEqual((state, code), ("succeeded", 0), job.said)
        self.assertEqual(self.read(), dict(RECORD, release_key=self.spare))

    def test_the_keys_and_the_signature_the_hello_named_serve_a_spec_that_names_none(self):
        (state, code), job = self.update(hello={"sig": self.sign(self.k, digest(NEW)), "release_keys": [self.pub, self.spare],
                                                "release_spare_sig": self.statement()})
        self.assertEqual((state, code), ("succeeded", 0), job.said)
        self.assertEqual(self.read(), dict(RECORD, release_key=self.pub, release_spare=self.spare))

    def test_an_unsigned_or_wrongly_signed_first_update_is_installed_said_and_pins_nothing(self):
        other, _ = pair()
        for spec in ({}, {"release_keys": [self.pub, self.spare]},
                     {"sig": self.sign(other, digest(NEW)), "release_keys": [self.pub, self.spare]},
                     {"sig": self.sign(self.k, digest(NEW))},
                     {"sig": self.sign(self.k, digest(NEW)), "release_keys": [self.pub, "nope"]}):
            with open(self.me, "wb") as f:
                f.write(b"OLD")
            (state, code), job = self.update(**spec)
            self.assertEqual((state, code, job.installed), ("succeeded", 0, True), (spec, job.said))
            self.assertEqual(self.installed(), NEW)
            self.assertIn("not checked: no release key is pinned here", job.said)
            self.assertNotIn("pinned AerieOS's release key", job.said)
            self.assertEqual(self.read(), RECORD, spec)

    def test_a_signed_update_pins_nothing_where_the_console_chose_no_key(self):
        chose = dict(RECORD, release_unpinned=True)
        self.write(chose)
        for spec in ({"sig": self.sign(self.k, digest(NEW)), "release_keys": [self.pub, self.spare]}, {}):
            with open(self.me, "wb") as f:
                f.write(b"OLD")
            (state, code), job = self.update(**spec)
            self.assertEqual((state, code, job.installed), ("succeeded", 0, True), job.said)
            self.assertEqual(self.installed(), NEW)
            self.assertIn("not checked: this node's console chose to pin no release key", job.said)
            self.assertNotIn("pinned AerieOS's release key", job.said)
            self.assertEqual(self.read(), chose)
        # The hello's names pin nothing there either.
        with open(self.me, "wb") as f:
            f.write(b"OLD")
        (state, code), job = self.update(hello={"sig": self.sign(self.k, digest(NEW)), "release_keys": [self.pub]})
        self.assertEqual((state, code), ("succeeded", 0), job.said)
        self.assertEqual(self.read(), chose)
        # A record from before the choice was kept, the same update: pinned.
        self.write(RECORD)
        with open(self.me, "wb") as f:
            f.write(b"OLD")
        (state, code), job = self.update(sig=self.sign(self.k, digest(NEW)), release_keys=[self.pub, self.spare])
        self.assertEqual((state, code), ("succeeded", 0), job.said)
        self.assertEqual(self.read(), dict(RECORD, release_key=self.pub))

    def test_a_choice_made_at_the_console_meanwhile_stands(self):
        mod = self.agent.module("agent")

        def console_says_none(path):
            self.write(dict(RECORD, release_unpinned=True))
            return True, "selfcheck ok"
        with mock.patch.object(mod, "selfcheck", console_says_none):
            (state, code), job = self.update(sig=self.sign(self.k, digest(NEW)), release_keys=[self.pub])
        self.assertEqual((state, code), ("succeeded", 0), job.said)
        self.assertIn("this node's console chose to pin no release key", job.said)
        self.assertNotIn("pinned AerieOS's release key", job.said)
        self.assertEqual(self.read(), dict(RECORD, release_unpinned=True))

    def test_a_pinned_node_is_unchanged_by_the_keys_a_controller_names(self):
        t, theirs = pair()
        _, mine = pair()
        for held in ({"release_key": self.pub}, {"release_also": [mine]}):
            self.write(dict(RECORD, **held))
            (state, code), job = self.update(sig=self.sign(t, digest(NEW)), release_keys=[theirs])
            self.assertEqual((state, code, job.installed), ("failed", 77, False), job.said)
            # The job's error is the refusal's cause, and its log the whole of it.
            self.assertIn(job.why, ("its signature is not the pinned release key's", "its signature is under no key this node trusts"))
            self.assertIn("refused: " + job.why, job.said)
            self.assertEqual(self.installed(), b"OLD")
            self.assertEqual(self.read(), dict(RECORD, **held))
            self.assertEqual(self.beside(), [])

    def test_nothing_a_spec_carries_changes_what_the_console_decides(self):
        _, theirs = pair()
        _, mine = pair()
        self.write(dict(RECORD, release_also=[mine], unsigned_ok=True))
        m = Ed25519PrivateKey.generate()
        (state, code), job = self.update(sig=self.sign(m, digest(NEW)), release_keys=[theirs], release_also=[theirs],
                                         release_key=theirs, release_spare=theirs, unsigned_ok=False, root_off=True)
        self.assertEqual((state, code), ("succeeded", 0), job.said)
        self.assertIn("console allows unsigned builds", job.said)
        self.assertEqual(self.read(), dict(RECORD, release_also=[mine], unsigned_ok=True))
        # ...and on a node with no key, the first pin sets the two release
        # fields and no other: no list, no switch.
        self.write(RECORD)
        with open(self.me, "wb") as f:
            f.write(b"OLD")
        (state, code), job = self.update(sig=self.sign(self.k, digest(NEW)), release_keys=[self.pub], release_also=[theirs],
                                         unsigned_ok=True, root_off=True)
        self.assertEqual((state, code), ("succeeded", 0), job.said)
        self.assertEqual(self.read(), dict(RECORD, release_key=self.pub))

    def test_a_pin_that_cannot_be_written_installs_nothing(self):
        mod = self.agent.module("agent")
        spec = {"sig": self.sign(self.k, digest(NEW)), "release_keys": [self.pub, self.spare]}
        # A build that passed its start check, so its trial had begun.
        with mock.patch.object(mod, "selfcheck", lambda path: (True, "selfcheck ok")), \
                mock.patch.object(self.stores, "_save", side_effect=OSError(28, "No space left on device")):
            (state, code), job = self.update(**spec)
        self.assertEqual((state, code, job.installed), ("failed", 73, False), job.said)
        self.assertIn("could not be pinned here", job.why)
        self.assertIn("so nothing was installed", job.why)
        self.assertEqual(self.installed(), b"OLD")
        self.assertEqual(self.read(), RECORD)
        # The old agent kept beside itself is all that is left: no new file
        # waiting, and no note of a trial for an agent that was not installed.
        self.assertEqual(self.beside(), ["aerieos-agent.prev"])
        # The same update, once the record can be written, is the first signed one.
        (state, code), job = self.update(**spec)
        self.assertEqual((state, code), ("succeeded", 0), job.said)
        self.assertEqual(self.read(), dict(RECORD, release_key=self.pub))

    def test_a_key_pinned_at_the_console_meanwhile_stands_and_judges_the_update(self):
        mod = self.agent.module("agent")
        _, theirs = pair()
        spec = {"sig": self.sign(self.k, digest(NEW)), "release_keys": [self.pub]}

        def console_pins(key):
            def check(path):
                self.write(dict(RECORD, release_key=key))
                return True, "selfcheck ok"
            return check
        # Another key, pinned while the new file was being checked: refused.
        with mock.patch.object(mod, "selfcheck", console_pins(theirs)):
            (state, code), job = self.update(**spec)
        self.assertEqual((state, code, job.installed), ("failed", 77, False), job.said)
        self.assertEqual(self.installed(), b"OLD")
        self.assertEqual(self.read(), dict(RECORD, release_key=theirs))
        self.assertEqual(self.beside(), ["aerieos-agent.prev"])
        # The same key, pinned there by a person: taken, and theirs is what stands.
        self.write(RECORD)
        with mock.patch.object(mod, "selfcheck", console_pins(self.pub)):
            (state, code), job = self.update(**spec)
        self.assertEqual((state, code), ("succeeded", 0), job.said)
        self.assertIn("signed by the release key this node pinned", job.said)
        self.assertNotIn("first signed update", job.said)
        self.assertEqual(self.read(), dict(RECORD, release_key=self.pub))


class Controller(unittest.TestCase):
    """The controller's half: the keys its build carries, named beside every
    agent update and in every hello."""

    def setUp(self):
        nodes.configure(state=tempfile.mkdtemp())
        nodes._auto_tried.clear()
        mint = nodes.enroll_mint("user:test", "box")
        self.census = {"cpu": 2, "mem_mb": 4096, "arch": "x86_64", "system": "linux", "session": {"up": True, "user": "b"}}
        nodes.enroll(nodes.authenticate(mint["token"]), self.census, "box.lan", user="bb")
        self.nid = mint["id"]

    def spec(self):
        nodes._exec("UPDATE nodes SET agent = json_set(agent, '$.digest', ?) WHERE id = ?", ("sha256:" + "0" * 64, self.nid))
        r = nodes.node_update_agent("user:test", self.nid)
        self.assertTrue(r.get("job"), r)
        return next(j for j in nodes.jobs_for(node_id=self.nid, n=10, active=True) if j["id"] == r["job"])["spec"]

    def test_the_update_and_the_hello_name_the_keys_this_build_carries(self):
        keys = enrollscript.release_keys()
        self.assertEqual(len(keys), 2, "the repository names the release key and its spare")
        self.assertEqual(self.spec()["release_keys"], keys)
        self.assertEqual(nodes.hello(self.nid, self.census, "box.lan")["agent"]["release_keys"], keys)

    def test_a_build_that_names_no_key_names_none(self):
        with mock.patch.object(enrollscript, "release_keys", lambda: []):
            self.assertNotIn("release_keys", self.spec())
            self.assertNotIn("release_keys", nodes.hello(self.nid, self.census, "box.lan")["agent"])


if __name__ == "__main__":
    unittest.main()
