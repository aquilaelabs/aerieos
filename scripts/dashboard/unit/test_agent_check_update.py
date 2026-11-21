"""check-update FILE [SIG]: the node's own rule for an agent update
(release.may_install), asked from outside the agent by whatever swaps an
agent in itself, the provisioner first. It reads node.json and the file,
says one line, exits 0 when the file may be installed and 77 when it is
refused, and writes nothing: no key is pinned by asking."""
import contextlib
import hashlib
import importlib.util
import io
import json
import os
import subprocess
import sys
import tempfile
import unittest

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)
import agentpkg  # noqa: E402
from cryptography.hazmat.primitives.asymmetric.ed25519 import Ed25519PrivateKey  # noqa: E402

SRC = os.path.normpath(os.path.join(HERE, "..", "..", "agent"))
# An update as a node is sent one: this tree's agent by its version, with no start check in it.
NEW = agentpkg.an_agent()
DIGEST = "sha256:" + hashlib.sha256(NEW).hexdigest()
RECORD = {"node_id": "n_1", "token": "bbn_1", "controller": "http://127.0.0.1:1"}


def pair():
    k = Ed25519PrivateKey.generate()
    return k, k.public_key().public_bytes_raw().hex()


class CheckUpdate(unittest.TestCase):
    def setUp(self):
        self.agent = agentpkg.load("aerieos_agent_check_update")
        self.release, self.cli = self.agent.module("release"), self.agent.module("cli")
        self.d = tempfile.mkdtemp()
        self.nj = os.path.join(self.d, "node.json")
        self.agent.NODE_JSON = self.nj
        self.new = os.path.join(self.d, "aerieos-agent.new")
        with open(self.new, "wb") as f:
            f.write(NEW)
        self.k, self.pub = pair()
        self.s, self.spare = pair()
        self.m, self.mine = pair()

    def sign(self, key, of=DIGEST):
        return key.sign(self.release.MESSAGE + of.encode()).hex()

    def write(self, state):
        with open(self.nj, "w") as f:
            json.dump(state, f)

    def held(self):
        """Every file in the node's folder, with what it holds."""
        out = {}
        for n in sorted(os.listdir(self.d)):
            with open(os.path.join(self.d, n), "rb") as f:
                out[n] = f.read()
        return out

    def check(self, *args):
        """(exit code, what it said) for check-update with these arguments,
        having changed nothing in the node's folder."""
        before = self.held()
        out, err, code = io.StringIO(), io.StringIO(), 0
        with contextlib.redirect_stdout(out), contextlib.redirect_stderr(err):
            try:
                self.cli.main(["check-update", *args])
            except SystemExit as e:
                code = e.code
        self.assertEqual(self.held(), before, "check-update writes nothing")
        return code, (out.getvalue() + err.getvalue()).strip()

    def test_a_pinned_node_takes_what_a_key_it_trusts_signed(self):
        self.write(dict(RECORD, release_key=self.pub, release_spare=self.spare, release_also=[self.mine]))
        for signer, words in ((self.k, f"signed by the release key this node pinned ({self.pub[:16]}…)"),
                              (self.s, f"signed by the spare release key this node pinned ({self.spare[:16]}…)"),
                              (self.m, f"signed by a key added at this node's console ({self.mine[:16]}…)")):
            self.assertEqual(self.check(self.new, self.sign(signer)), (0, words))

    def test_a_pinned_node_refuses_an_unsigned_or_wrongly_signed_file_with_77(self):
        other, _ = pair()
        self.write(dict(RECORD, release_key=self.pub))
        for args in ((self.new,), (self.new, ""), (self.new, self.sign(other)), (self.new, self.sign(self.k, "sha256:" + "cd" * 32)),
                     (self.new, "not a signature")):
            code, said = self.check(*args)
            self.assertEqual(code, 77, args)
            self.assertTrue(said.startswith("refused: "), said)
            self.assertIn(f"only updates signed by the release key it pinned ({self.pub[:16]}…)", said)
            self.assertRegex(said, r"sudo (aerieos|builderbot)-agent release-key add HEX")
            self.assertRegex(said, r"sudo (aerieos|builderbot)-agent unsigned on")
        # The file is what is checked: another file under the same signature is refused.
        with open(self.new, "ab") as f:
            f.write(b"# and one more line\n")
        self.assertEqual(self.check(self.new, self.sign(self.k))[0], 77)

    def test_a_node_whose_console_allows_unsigned_builds_takes_one_and_says_so(self):
        self.write(dict(RECORD, release_key=self.pub, unsigned_ok=True))
        code, said = self.check(self.new)
        self.assertEqual(code, 0)
        self.assertIn("this node's console allows unsigned builds", said)

    def test_a_node_with_no_key_takes_it_unchecked_and_asking_pins_nothing(self):
        self.write(RECORD)
        self.assertEqual(self.check(self.new),
                         (0, "not checked: no release key is pinned here, and the controller sent no signature with it"))
        # A signature a release key would verify pins nothing here: the
        # asking is not the update.
        code, said = self.check(self.new, self.sign(self.k))
        self.assertEqual(code, 0)
        self.assertIn("not checked: no release key is pinned here", said)
        with open(self.nj) as f:
            self.assertEqual(json.load(f), RECORD)

    def test_a_node_whose_console_chose_no_key_takes_it_and_says_whose_choice(self):
        self.write(dict(RECORD, release_unpinned=True))
        for args in ((self.new,), (self.new, self.sign(self.k))):
            self.assertEqual(self.check(*args), (0, "not checked: this node's console chose to pin no release key"))

    def test_a_machine_with_no_record_has_pinned_nothing(self):
        code, said = self.check(self.new, self.sign(self.k))
        self.assertEqual(code, 0)
        self.assertIn("not checked: no release key is pinned here", said)
        self.assertFalse(os.path.exists(self.nj))
        # A record no agent could start on either is said, not guessed at.
        for held in ("not json", "[]"):
            with open(self.nj, "w") as f:
                f.write(held)
            code, said = self.check(self.new)
            self.assertEqual(code, 0)
            self.assertIn("is not a node's record", said)

    def test_the_signature_may_be_a_file_that_holds_it(self):
        self.write(dict(RECORD, release_key=self.pub))
        sig = os.path.join(self.d, "agent.sig")
        for held in (self.sign(self.k) + "\n", json.dumps({"key": self.pub, "digest": DIGEST, "sig": self.sign(self.k)})):
            with open(sig, "w") as f:
                f.write(held)
            self.assertEqual(self.check(self.new, sig)[0], 0, held)
        with open(sig, "w") as f:
            json.dump({"digest": DIGEST}, f)
        self.assertEqual(self.check(self.new, sig)[0], 77, "a file that holds no signature is no signature")

    def test_a_file_that_cannot_be_read_is_refused_and_a_wrong_call_is_said(self):
        self.write(RECORD)
        code, said = self.check(os.path.join(self.d, "nothing-here"))
        self.assertEqual(code, 77)
        self.assertIn("could not be read", said)
        for args in ((), ("",), (self.new, "a", "b")):
            code, said = self.check(*args)
            self.assertEqual(code, 64, args)
            self.assertIn("check-update takes the agent file", said)

    def test_the_agent_file_itself_answers_as_the_provisioner_calls_it(self):
        # "$AGENT" check-update "$NEW" "$SIG": the zip a node runs, the exit
        # code a shell reads.
        spec = importlib.util.spec_from_file_location("agent_bundle_check_update", os.path.join(SRC, "aerieos_agent", "bundle.py"))
        bundle = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(bundle)
        agent = os.path.join(self.d, "aerieos-agent")
        with open(agent, "wb") as f:
            f.write(bundle.build(SRC))
        self.write(dict(RECORD, release_key=self.pub))
        env = dict(os.environ, BUILDERBOT_NODE_JSON=self.nj)

        def run(*args):
            r = subprocess.run([sys.executable, agent, "check-update", *args], env=env, capture_output=True, text=True,
                               timeout=60, check=False, stdin=subprocess.DEVNULL)
            return r.returncode, r.stdout.strip()
        self.assertEqual(run(self.new, self.sign(self.k)), (0, f"signed by the release key this node pinned ({self.pub[:16]}…)"))
        code, said = run(self.new, "")
        self.assertEqual(code, 77)
        self.assertTrue(said.startswith("refused: the controller sent no signature with it."), said)
        with open(self.nj) as f:
            self.assertEqual(json.load(f), dict(RECORD, release_key=self.pub))


if __name__ == "__main__":
    unittest.main()
