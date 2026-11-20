"""The agent a node is handed is checked before it runs (the audit of the
paths around the release key, 20 Nov).

A running agent takes an update only when the release key it pinned signed
it. Around that check: the first agent, at enrollment, was fetched as root
and held only to a digest the same answer named, with the release key in
hand and unused, and the guest's and a Mac's path took an answer with no
digest at all; and a provisioner run again swapped a newer agent in on the
answer's digest alone, on a node that had pinned the key.

The Enroll script carries the digest of the agent the controller ships and
the release's signature over it; every path holds what arrives to them
before running it; and a run after the enrollment asks the installed agent
(check-update) before the swap. Each path here is the provisioner's own
lines, cut from the script and run under bash with curl, the agent and the
services stood in for."""
import functools
import os
import re
import shutil
import subprocess
import sys
import tempfile
import unittest

from cryptography.hazmat.primitives.asymmetric.ed25519 import Ed25519PrivateKey

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.normpath(os.path.join(HERE, "..", "..", ".."))
LINUX = os.path.join(ROOT, "nodes", "provision-linux.sh")
MAC = os.path.join(ROOT, "nodes", "provision-macos.sh")
sys.path.insert(0, os.path.join(HERE, ".."))
sys.path.insert(0, HERE)
import agentpkg  # noqa: E402
import enrollscript as es  # noqa: E402
import nodes  # noqa: E402

MESSAGE = b"aerieos agent v1\n"
AGENT = b"#!/usr/bin/env python3\nprint('the agent')\n"
# What somebody between the node and the controller would send in its place,
# with headers that agree with it.
OTHER = b"#!/usr/bin/env python3\nprint('not the agent')\n"


def digest_of(body):
    import hashlib
    return "sha256:" + hashlib.sha256(body).hexdigest()


def pair():
    k = Ed25519PrivateKey.generate()
    return k, k.public_key().public_bytes_raw().hex()


def signed(key, digest):
    return key.sign(MESSAGE + digest.encode()).hex()


def text(path):
    with open(path, encoding="utf-8") as f:
        return f.read()


def held(path):
    """The file's bytes, None where there is none."""
    if not os.path.exists(path):
        return None
    with open(path, "rb") as f:
        return f.read()


def between(script, start, end):
    """The script's own lines from the one that starts `start` through the
    one that starts `end`."""
    i = script.index(start)
    j = script.index(end, i)
    return script[i:script.index("\n", j) + 1]


def section(script, until):
    """The functions that check an agent, as the provisioner defines them."""
    i = script.index("# ---- the agent, checked before it runs")
    return re.search(r"^RELEASE_KEYS_RE=.*$", script, re.M).group(0) + "\n" + script[i:script.index(until, i)]


# The three ways an agent is first fetched, each as the script runs it.
PATHS = {
    "a managed node": (LINUX, "# ---- a GUEST node", "AGENT",
                       ('    hdr="$(mktemp)"\n    # Tried again on a transient answer (B747), as the own node',
                        '    chmod 755 "${AGENT}.new"; mv -f "${AGENT}.new" "$AGENT"\n    svc_stop aerieos-agent')),
    "a guest": (LINUX, "# ---- a GUEST node", "agent",
                ('    say "the agent, from ${CONTROLLER}"\n    local hdr want', '    chmod 755 "${agent}.new"; mv -f "${agent}.new" "$agent"')),
    "a Mac": (MAC, "# ---- taking it away", "AGENT",
              ('say "the agent, from ${CONTROLLER}"\nhdr="$(mktemp)"', 'chmod 755 "${AGENT}.new"; mv -f "${AGENT}.new" "$AGENT"')),
}
# curl, stood in for: the body and the headers the test laid down, to where
# the script asked for them.
STUBS = r'''
set -euo pipefail
say() { printf '\n== %s\n' "$*"; }
warn() { printf '\n!! %s\n' "$*" >&2; }
curl() {
    local out="" hdr=""
    while [ $# -gt 0 ]; do
        case "$1" in -D) hdr="$2"; shift 2 ;; -o) out="$2"; shift 2 ;; *) shift ;; esac
    done
    [ -f "$FIX/body" ] || return 22
    cat "$FIX/body" > "$out"
    [ -z "$hdr" ] || cat "$FIX/headers" > "$hdr"
}
shasum() { shift 2; sha256sum "$@"; }
svc_stop() { :; }
svc_restart() { echo "restarted $1"; }
'''
# Nothing here that can check a signature: Python without the library, an
# openssl that does not know the question, no swift.
NO_PYTHON_LIB = '''
python3() { case "${2:-}" in *Ed25519PublicKey*) echo nolib ;; *) command python3 "$@" ;; esac; }
'''
BLIND = NO_PYTHON_LIB + '''
openssl() { echo "pkeyutl: Unknown option: -rawin" >&2; return 1; }
swift() { return 127; }
'''


def on_each_path(test):
    """The test, once for each way an agent is first fetched."""
    @functools.wraps(test)
    def run(self):
        for path in PATHS:
            with self.subTest(path=path):
                test(self, path)
    return run


class Bash(unittest.TestCase):
    def setUp(self):
        self.d = tempfile.mkdtemp()
        self.addCleanup(shutil.rmtree, self.d, True)
        self.key, self.pub = pair()
        self.spare, self.spare_pub = pair()
        self.digest = digest_of(AGENT)
        self.sig = signed(self.key, self.digest)

    def lay(self, body, headers):
        """What the controller answers: the file, and its headers."""
        if body is None:
            for f in ("body", "headers"):
                if os.path.exists(os.path.join(self.d, f)):
                    os.unlink(os.path.join(self.d, f))
            return
        with open(os.path.join(self.d, "body"), "wb") as f:
            f.write(body)
        with open(os.path.join(self.d, "headers"), "w") as f:
            f.write("HTTP/1.1 200 OK\r\n" + "".join(f"{k}: {v}\r\n" for k, v in headers.items()) + "\r\n")

    def bash(self, script):
        r = subprocess.run(["bash", "-c", script], capture_output=True, text=True, timeout=120, check=False,
                           env=dict(os.environ, FIX=self.d), cwd=self.d)
        return r.returncode, r.stdout + r.stderr


class FirstAgent(Bash):
    """Enrollment, on each path: the agent that arrives is held to what the
    script carries before it is put in place."""

    def enroll(self, path, *, body=AGENT, headers=None, digest="", sig="", key="", pre=""):
        script, until, var, (start, end) = PATHS[path]
        src = text(script)
        self.lay(body, {"X-Agent-Digest": digest_of(body)} if headers is None else headers)
        installed = os.path.join(self.d, "installed-agent")
        if os.path.exists(installed):
            os.unlink(installed)
        run = (STUBS + section(src, until) + pre
               + f"CONTROLLER=http://controller.example:7680; TOKEN=bbe_x\n{var}={installed!r}\n"
               + f"AGENT_DIGEST={digest!r}; AGENT_SIG={sig!r}; RELEASE_KEY={key!r}\n"
               + "path() {\n" + between(src, start, end).replace("svc_stop aerieos-agent", "") + "}\npath\necho PUT-IN-PLACE\n")
        rc, said = self.bash(run)
        there = os.path.exists(installed)
        self.assertEqual(there, "PUT-IN-PLACE" in said, said)
        self.assertFalse(os.path.exists(installed + ".new") and not there, f"what was refused is not left lying about: {said}")
        return rc, there, said

    @on_each_path
    def test_the_agent_the_script_was_made_for_signed_by_the_release_goes_in(self, path):
        rc, there, said = self.enroll(path, digest=self.digest, sig=self.sig, key=self.pub)
        self.assertEqual((rc, there), (0, True), said)
        self.assertIn(f"signed by AerieOS's release key ({self.pub[:16]}", said)
        # ...and under the spare, named as that.
        rc, there, said = self.enroll(path, digest=self.digest, sig=signed(self.spare, self.digest),
                                      key=f"{self.pub},{self.spare_pub}")
        self.assertEqual((rc, there), (0, True), said)
        self.assertIn(f"signed by the spare of AerieOS's release key ({self.spare_pub[:16]}", said)

    @on_each_path
    def test_another_agent_than_the_script_was_made_for_is_refused(self, path):
        # Its own headers agree with it, as whoever sends it would have them:
        # the digest the answer names is not what it is held to.
        rc, there, said = self.enroll(path, body=OTHER, digest=self.digest, sig=self.sig, key=self.pub)
        self.assertEqual((rc, there), (1, False), said)
        self.assertIn("is not the one this enrollment was made for", said)
        self.assertIn("none of it was run", said)
        # With no signature in the script either (a build from a branch).
        rc, there, said = self.enroll(path, body=OTHER, digest=self.digest, key=self.pub)
        self.assertEqual((rc, there), (1, False), said)

    @on_each_path
    def test_a_signature_that_is_not_the_release_keys_is_refused(self, path):
        other, _ = pair()
        rc, there, said = self.enroll(path, digest=self.digest, sig=signed(other, self.digest), key=self.pub)
        self.assertEqual((rc, there), (1, False), said)
        self.assertIn(f"is not the release key's ({self.pub[:16]}", said)
        # The release's signature, over another agent than this one.
        rc, there, said = self.enroll(path, digest=self.digest, sig=signed(self.key, digest_of(OTHER)), key=self.pub)
        self.assertEqual((rc, there), (1, False), said)
        # A signature with no key to check it under is not a pass.
        rc, there, said = self.enroll(path, digest=self.digest, sig=self.sig)
        self.assertEqual((rc, there), (1, False), said)
        self.assertIn("no release key to check it under", said)

    @on_each_path
    def test_a_signature_this_machine_cannot_check_is_refused_with_the_reason(self, path):
        rc, there, said = self.enroll(path, digest=self.digest, sig=self.sig, key=self.pub, pre=BLIND)
        self.assertEqual((rc, there), (1, False), said)
        self.assertIn("this machine cannot check one", said)
        self.assertIn("no cryptography library", said)

    @on_each_path
    def test_openssl_checks_it_where_python_has_no_library(self, path):
        r = subprocess.run(["openssl", "version"], capture_output=True, text=True, check=False)
        if not r.stdout.startswith("OpenSSL 3"):
            self.skipTest(f"no OpenSSL 3 here ({r.stdout.strip() or 'no openssl'})")
        other, _ = pair()
        rc, there, said = self.enroll(path, digest=self.digest, sig=signed(self.spare, self.digest),
                                      key=f"{self.pub},{self.spare_pub}", pre=NO_PYTHON_LIB)
        self.assertEqual((rc, there), (0, True), said)
        self.assertIn("signed by the spare of AerieOS's release key", said)
        rc, there, said = self.enroll(path, digest=self.digest, sig=signed(other, self.digest),
                                      key=f"{self.pub},{self.spare_pub}", pre=NO_PYTHON_LIB)
        self.assertEqual((rc, there), (1, False), said)
        self.assertIn("is not the release key's", said)

    @on_each_path
    def test_a_build_with_no_signature_enrolls_and_says_so(self, path):
        rc, there, said = self.enroll(path, digest=self.digest, key=self.pub)
        self.assertEqual((rc, there), (0, True), said)
        self.assertIn("No release signature came with it", said)
        self.assertIn("nothing says an AerieOS release built this agent", said)
        self.assertIn("pins the release key all the same", said)
        self.assertNotIn("signed by", said)

    @on_each_path
    def test_a_script_from_an_older_controller_still_enrolls_and_says_what_was_not_checked(self, path):
        # The key and nothing else, as the Enroll script carried it; and a
        # saved token-only command, which carried nothing.
        rc, there, said = self.enroll(path, key=self.pub)
        self.assertEqual((rc, there), (0, True), said)
        self.assertIn("by the digest the controller sent with it and nothing else", said)
        self.assertNotIn("No release key came", said)
        rc, there, said = self.enroll(path)
        self.assertEqual((rc, there), (0, True), said)
        self.assertIn("carries no digest and no signature", said)
        self.assertIn("No release key came with this enrollment", said)
        # ...held to the controller's own digest all the same.
        rc, there, said = self.enroll(path, headers={"X-Agent-Digest": digest_of(OTHER)})
        self.assertEqual((rc, there), (1, False), said)
        self.assertIn("does not match the digest the controller sent", said)

    @on_each_path
    def test_an_answer_with_no_digest_is_refused_on_every_path(self, path):
        # The guest's and the Mac's took it as it came.
        rc, there, said = self.enroll(path, headers={})
        self.assertEqual((rc, there), (1, False), said)
        self.assertIn("is not AerieOS's", said)
        self.assertIn("no digest", said)
        rc, there, said = self.enroll(path, body=b"", headers={}, digest=self.digest)
        self.assertEqual((rc, there), (1, False), f"nothing arriving is not the agent: {said}")

    def test_the_arguments_are_read_by_both_provisioners_and_a_cut_one_is_said_at_once(self):
        for script in (LINUX, MAC):
            src = text(script)
            for flag, var in (("--release-key", "RELEASE_KEY"), ("--agent-digest", "AGENT_DIGEST"), ("--agent-sig", "AGENT_SIG")):
                self.assertIn(f'{flag}) {var}="$2"; shift 2 ;;', src, script)
            # Before anything is looked at or changed: the script ends on it.
            for args, word in ((["--agent-digest", "sha256:abc"], "--agent-digest takes"),
                               (["--agent-sig", "abc"], "--agent-sig takes"),
                               (["--release-key", "abc"], "--release-key takes")):
                r = subprocess.run(["bash", script, "--controller", "http://controller.example:7680", "--token", "bbe_x", *args],
                                   capture_output=True, text=True, timeout=30, check=False)
                self.assertEqual(r.returncode, 1, r.stdout + r.stderr)
                self.assertIn(word, r.stderr)
                self.assertEqual(r.stdout, "", "nothing was begun")

    def test_the_two_provisioners_make_the_same_check(self):
        linux, mac = text(LINUX), text(MAC)
        py = re.compile(r"^RELEASE_VERIFY_PY='(.*?)^'$", re.S | re.M)
        self.assertEqual(py.search(linux).group(1), py.search(mac).group(1))
        self.assertIn('b"aerieos agent v1\\n" + digest.encode()', py.search(linux).group(1))
        for name in ("hex_bytes", "agent_sent"):
            body = re.compile(rf"^{name}\(\) \{{\n.*?^\}}$", re.S | re.M)
            self.assertEqual(body.search(linux).group(0), body.search(mac).group(0), name)
        # What the release signs, as the agent's own check has it.
        release = agentpkg.load("aerieos_agent_enroll_checked").module("release")
        self.assertEqual(release.MESSAGE, MESSAGE)
        self.assertIn('"aerieos agent v1\\n" + a[3]', mac)
        self.assertEqual(release.verify(self.pub, self.digest, self.sig), "")


class Carried(unittest.TestCase):
    """What the controller puts in an enrollment, and beside the download."""

    def setUp(self):
        d = tempfile.mkdtemp()
        self.addCleanup(shutil.rmtree, d, True)
        self.a, self.b = "a1" * 32, "b2" * 32
        self.pub = os.path.join(d, "release.pub")
        self.addCleanup(setattr, es, "RELEASE_PUB", es.RELEASE_PUB)
        es.RELEASE_PUB = self.pub
        self.keys(self.a, self.b)
        self.digest, self.sig = "sha256:" + "0f" * 32, "5e" * 64

    def keys(self, *keys):
        with open(self.pub, "w") as f:
            f.write("".join(f"aerieos-release-ed25519 {k}\n" for k in keys))

    def test_the_key_the_digest_and_the_signature_where_there_is_one(self):
        self.assertEqual(es.pins({"digest": self.digest, "sig": self.sig}),
                         ["--release-key", f"{self.a},{self.b}", "--agent-digest", self.digest, "--agent-sig", self.sig])
        # A build made outside the release's: the digest, and no signature.
        self.assertEqual(es.pins({"digest": self.digest, "sig": ""}),
                         ["--release-key", f"{self.a},{self.b}", "--agent-digest", self.digest])
        self.assertEqual(es.pins(), ["--release-key", f"{self.a},{self.b}"])
        self.assertEqual(es.pins({"digest": "", "sig": self.sig}), ["--release-key", f"{self.a},{self.b}"],
                         "no signature without the digest it is over")
        self.assertEqual(es.pins({"digest": "sha256:nope; rm -rf /", "sig": "$(id)"}), ["--release-key", f"{self.a},{self.b}"],
                         "only what is a digest and a signature reaches a command line")
        # No key to check a signature under: the provisioner would refuse one.
        self.keys()
        self.assertEqual(es.pins({"digest": self.digest, "sig": self.sig}), ["--agent-digest", self.digest])

    def test_the_enroll_script_carries_them_to_the_provisioner(self):
        ans = es.check({"reach": "lan", "controller": "http://192.168.1.16:7680"})

        def run(**kw):
            s = es.build(ans, name="box", user="bb", token="bbe_x", expires=0, provisioner=b"x", **kw)
            return next(x for x in s.splitlines() if x.startswith('bash "$dir/provision-linux.sh"'))
        line = run(agent={"digest": self.digest, "sig": self.sig})
        self.assertIn(f" --release-key {self.a},{self.b} --agent-digest {self.digest} --agent-sig {self.sig} ", line + " ")
        line = run(agent={"digest": self.digest, "sig": ""})
        self.assertIn(f"--agent-digest {self.digest}", line)
        self.assertNotIn("--agent-sig", line)
        self.assertNotIn("--agent-", run(), "a caller that names no agent carries the key alone, as before")

    def test_the_script_made_for_a_node_carries_what_this_controller_ships(self):
        ours = {"body": AGENT, "digest": digest_of(AGENT), "version": "1.1"}
        self.addCleanup(setattr, nodes, "agent_file", nodes.agent_file)
        self.addCleanup(setattr, nodes, "agent_sig", nodes.agent_sig)
        nodes.agent_file = lambda: ours
        nodes.agent_sig = lambda digest=None: self.sig if digest == ours["digest"] else ""
        self.assertEqual(nodes.agent_carried(), {"digest": ours["digest"], "sig": self.sig})
        nodes.agent_sig = lambda digest=None: ""
        self.assertEqual(nodes.agent_carried(), {"digest": ours["digest"], "sig": ""})
        self.assertIn("agent=agent_carried()", text(os.path.join(HERE, "..", "nodes.py")))

if __name__ == "__main__":
    unittest.main()
