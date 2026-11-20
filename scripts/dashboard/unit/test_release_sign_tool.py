"""tools/release-sign.py (R199): the list of a release's files is made from
the files themselves and signed in the namespace of who holds the key. The
audit of 20 Nov found `sign` wrote SHA256SUMS from the .sha256 files the
release carries, so whoever replaced a file and its sha256 got the
signature too. Here against a stand-in for GitHub's API on a local port,
with real keys and ssh-keygen: `seal` (CI, the release build's key from
AERIEOS_RELEASE_KEY, the namespace aerieos-dev) refuses a stable tag, a
release short of a file and a key no install names, and makes a signature
the verifiers take for a dev build; `sign` (the stable key's holder,
aerieos-release) hashes each file's bytes, stops at a sha256 file that
lies and at a file nothing vouches for, and holds an attestation to the
release workflow at the tag."""
import contextlib
import hashlib
import importlib.util
import io
import json
import os
import shutil
import stat
import subprocess
import sys
import tempfile
import threading
import unittest
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from unittest import mock

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.normpath(os.path.join(HERE, "..", "..", ".."))
sys.path.insert(0, os.path.join(HERE, ".."))
import agentpkg  # noqa: E402


def load(name, rel):
    spec = importlib.util.spec_from_file_location(name, os.path.join(ROOT, *rel))
    m = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(m)
    return m


tool = load("release_sign_under_test", ("tools", "release-sign.py"))
gen = load("release_signers_for_sign", ("tools", "release-signers.py"))
stick = load("bbstick_for_sign", ("tools", "aerieos-stick.py"))
osimage = agentpkg.load("aerieos_agent_sign_tool").module("osimage")

try:
    from cryptography.hazmat.primitives import serialization as ser
    from cryptography.hazmat.primitives.asymmetric.ed25519 import Ed25519PrivateKey
except ImportError:
    Ed25519PrivateKey = None

COMMIT = "7" * 40
# What the stand-in serves: {tag: {name: bytes}}.
RELEASES = {}


class GitHub(BaseHTTPRequestHandler):
    def log_message(self, *a):
        pass

    def do_GET(self):
        base = f"http://127.0.0.1:{self.server.server_port}"
        path = self.path.split("?")[0]
        body = None
        if path == "/releases":
            body = json.dumps([{"tag_name": t, "draft": True,
                                "assets": [{"name": n, "url": f"{base}/asset/{t}/{n}"} for n in files]}
                               for t, files in RELEASES.items()]).encode()
        elif path.startswith("/git/ref/tags/"):
            body = json.dumps({"object": {"sha": COMMIT, "type": "commit"}}).encode()
        elif path.startswith("/asset/"):
            _, _, t, n = path.split("/", 3)
            body = RELEASES.get(t, {}).get(n)
        if body is None:
            self.send_error(404)
            return
        self.send_response(200)
        self.send_header("Content-Length", str(len(body)))
        self.end_headers()
        self.wfile.write(body)


def sha(b):
    return hashlib.sha256(b).hexdigest()


def release(ver, without=()):
    """A release's files as its jobs attach them: each with its sha256, the
    ISO's attestation bundle beside it."""
    out = {}
    for n in (f"aerieos-controller-{ver}.tar.gz", f"aerieos-app-{ver}.apk", f"aerieos-os-{ver}.iso"):
        if n not in without:
            out[n] = f"the bytes of {n}".encode()
            out[n + ".sha256"] = f"{sha(out[n])}  {n}\n".encode()
    out[f"aerieos-os-{ver}.attestation.jsonl"] = b"{}\n"
    return out


@unittest.skipUnless(shutil.which("ssh-keygen"), "no ssh-keygen here")
class Tool(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.srv = ThreadingHTTPServer(("127.0.0.1", 0), GitHub)
        threading.Thread(target=cls.srv.serve_forever, daemon=True).start()

    @classmethod
    def tearDownClass(cls):
        cls.srv.shutdown()
        cls.srv.server_close()

    def setUp(self):
        RELEASES.clear()
        self.d = tempfile.mkdtemp()
        self.addCleanup(shutil.rmtree, self.d, True)
        self.signers = os.path.join(self.d, "release-signers")
        self.files = os.path.join(self.d, ".release-files")
        with open(self.files, "w") as f:
            f.write("# what a release carries\naerieos-controller-@VER@.tar.gz\naerieos-controller-@VER@.tar.gz.sha256\n"
                    "aerieos-app-@VER@.apk\naerieos-os-@VER@.iso\naerieos-os-@VER@.attestation.jsonl\nSHA256SUMS\nSHA256SUMS.sig\n")
        self.out = os.path.join(self.d, "out")
        self.gh = None
        self.made = []
        real_which, real_mkdtemp = shutil.which, tempfile.mkdtemp

        def mkdtemp(*a, **k):
            self.made.append(real_mkdtemp(*a, **k))
            return self.made[-1]
        for p in (mock.patch.multiple(tool, API=f"http://127.0.0.1:{self.srv.server_port}", SIGNERS=self.signers, FILES=self.files, POLL=0.2),
                  mock.patch.object(tool.shutil, "which", side_effect=lambda n: self.gh if n == "gh" else real_which(n)),
                  mock.patch.object(tool.tempfile, "mkdtemp", side_effect=mkdtemp),
                  mock.patch.dict(os.environ, {"GH_TOKEN": "t"})):
            p.start()
            self.addCleanup(p.stop)

    def run_tool(self, *argv, env=None):
        """(exit code, what it printed) of the tool's own main."""
        out = io.StringIO()
        with mock.patch.dict(os.environ, env or {}), contextlib.redirect_stdout(out), contextlib.redirect_stderr(out):
            try:
                tool.main(list(argv))
                code = 0
            except SystemExit as e:
                code = e.code
        return code, out.getvalue()

    def lists(self):
        with open(os.path.join(self.out, "SHA256SUMS"), encoding="utf-8") as f:
            return dict(reversed(ln.split()) for ln in f)

    def keys_named(self):
        with open(self.signers, encoding="utf-8") as f:
            return [ln.strip() for ln in f if ln.strip() and not ln.startswith("#")]

    def taken(self, tag):
        """What the OS updater makes of the list and signature left in out."""
        sums = os.path.join(self.out, "SHA256SUMS")
        return osimage.signed_list(tag, sums, sums + ".sig", self.keys_named())


@unittest.skipUnless(Ed25519PrivateKey, "no cryptography here to make the release build's key with")
class Seal(Tool):
    def setUp(self):
        super().setUp()
        k = Ed25519PrivateKey.generate()
        self.seed = k.private_bytes(ser.Encoding.Raw, ser.PrivateFormat.Raw, ser.NoEncryption()).hex()
        pub = k.public_key().public_bytes(ser.Encoding.Raw, ser.PublicFormat.Raw).hex()
        # The line the generator writes from config/aerieos-release.pub's hex.
        with open(self.signers, "w") as f:
            f.write(f'# dev builds\naerieos-dev namespaces="aerieos-dev" {gen.ssh_key(pub)}\n')
        self.env = {"AERIEOS_RELEASE_KEY": self.seed}

    def test_a_stable_tag_is_refused_before_anything_is_read(self):
        with mock.patch.object(tool, "API", "http://127.0.0.1:9/unreachable"):
            code, said = self.run_tool("seal", "v0.9.1", "--out", self.out, env=self.env)
        self.assertEqual(code, 1)
        self.assertIn("a stable release is signed by its key's holder, not by CI", said)
        self.assertFalse(os.path.exists(self.out))
        code, said = self.run_tool("seal", "nightly", "--out", self.out, env=self.env)
        self.assertEqual(code, 1)
        self.assertIn("is not a pre-release's tag", said)

    def test_a_dev_build_is_sealed_from_its_files_bytes_and_the_verifiers_take_it(self):
        tag = "v0.9.1-dev.7"
        RELEASES[tag] = release("0.9.1-dev.7")
        code, said = self.run_tool("seal", tag, "--out", self.out, "--commit", COMMIT[:12], env=self.env)
        self.assertEqual(code, 0, said)
        want = {n: sha(b) for n, b in RELEASES[tag].items() if not n.endswith((".sha256", ".attestation.jsonl"))}
        self.assertEqual(self.lists(), want, "every file but the sha256 files and the attestation bundle, by its own bytes")
        self.assertIn(f"sealed {tag}: 3 files in SHA256SUMS, signed in aerieos-dev", said)
        self.assertIn(f"{os.path.join(self.out, 'SHA256SUMS')} {os.path.join(self.out, 'SHA256SUMS.sig')}", said)
        for n, digest in want.items():
            self.assertIn(f"{digest}  {n}", said, "it prints what it signed")
        # The OS updater takes it for the dev build, and for nothing stable.
        listed, who, why = self.taken(tag)
        self.assertEqual((listed, who, why), (want, "the key AerieOS's dev builds are signed with", ""))
        self.assertIn("no stable signer is named yet", self.taken("v0.9.1")[2])
        # ...and so does the stick maker.
        def fetch(url, dest, say_progress=True):
            shutil.copyfile(os.path.join(self.out, url.rsplit("/", 1)[1]), dest)
        with mock.patch.multiple(stick, RELEASE_SIGNERS="\n".join(self.keys_named()) + "\n", fetch=fetch, say=lambda s: None):
            self.assertEqual(stick.signed_list(tag, "aerieos-os-0.9.1-dev.7.iso")[0], want)
        # The key was on disk only while ssh-keygen read it, and nothing of
        # the release's files is left beside the list.
        self.assertTrue([d for d in self.made if "aerieos-seal-" in d])
        self.assertFalse([d for d in self.made if "aerieos-seal-" in d and os.path.exists(d)])
        self.assertEqual(sorted(os.listdir(self.out)), ["SHA256SUMS", "SHA256SUMS.sig"])
        self.assertNotIn(self.seed, said)

    def test_a_stable_signer_named_too_changes_nothing_for_a_stable_tag(self):
        # The custody: with a stable signer named, the release build's
        # signature still makes no stable release.
        tag = "v0.9.1-dev.7"
        RELEASES[tag] = release("0.9.1-dev.7")
        self.assertEqual(self.run_tool("seal", tag, "--out", self.out, env=self.env)[0], 0)
        other = os.path.join(self.d, "stable")
        subprocess.run(["ssh-keygen", "-q", "-t", "ed25519", "-N", "", "-f", other], check=True, stdin=subprocess.DEVNULL, timeout=30)
        with open(other + ".pub") as f, open(self.signers, "a") as g:
            g.write('aerieos-release namespaces="aerieos-release" ' + " ".join(f.read().split()[:2]) + " aerieos-release\n")
        self.assertIsNone(self.taken("v0.9.1")[0])
        self.assertIn("its list is signed by the key dev builds are signed with", self.taken("v0.9.1")[2])

    def test_a_release_short_of_a_file_is_not_sealed(self):
        tag = "v0.9.1-dev.7"
        RELEASES[tag] = release("0.9.1-dev.7", without=("aerieos-app-0.9.1-dev.7.apk",))
        code, said = self.run_tool("seal", tag, "--out", self.out, env=self.env)
        self.assertEqual(code, 3, said)
        self.assertIn("is not whole: aerieos-app-0.9.1-dev.7.apk still missing", said)
        self.assertFalse(os.path.exists(self.out))
        # ...and is, once the file a controller attaches has landed within the wait.
        threading.Timer(0.5, lambda: RELEASES.__setitem__(tag, release("0.9.1-dev.7"))).start()
        code, said = self.run_tool("seal", tag, "--out", self.out, "--wait", "20", env=self.env)
        self.assertEqual(code, 0, said)
        self.assertIn("aerieos-app-0.9.1-dev.7.apk", self.lists())

    def test_a_key_no_install_names_leaves_nothing_to_attach(self):
        tag = "v0.9.1-dev.7"
        RELEASES[tag] = release("0.9.1-dev.7")
        code, said = self.run_tool("seal", tag, "--out", self.out, env={"AERIEOS_RELEASE_KEY": "ab" * 32})
        self.assertEqual(code, 1)
        self.assertIn("is not one config/release-signers names for dev builds", said)
        self.assertFalse(os.path.exists(os.path.join(self.out, "SHA256SUMS.sig")))
        for bad in ("", "nothex"):
            code, said = self.run_tool("seal", tag, "--out", self.out, env={"AERIEOS_RELEASE_KEY": bad})
            self.assertEqual(code, 1)
            self.assertIn("AERIEOS_RELEASE_KEY is not the release build's key", said)

    def test_a_tag_moved_since_the_build_started_is_not_sealed(self):
        tag = "v0.9.1-dev.7"
        RELEASES[tag] = release("0.9.1-dev.7")
        code, said = self.run_tool("seal", tag, "--out", self.out, "--commit", "8" * 40, env=self.env)
        self.assertEqual(code, 1)
        self.assertIn("the tag was moved", said)


class Sign(Tool):
    def setUp(self):
        super().setUp()
        self.key = os.path.join(self.d, "key")
        subprocess.run(["ssh-keygen", "-q", "-t", "ed25519", "-N", "", "-C", "aerieos-release", "-f", self.key], check=True,
                       stdin=subprocess.DEVNULL, timeout=30)
        with open(self.key + ".pub") as f:
            kt, kb = f.read().split()[:2]
        with open(self.signers, "w") as f:
            f.write(f'aerieos-release namespaces="aerieos-release" {kt} {kb} aerieos-release\n')

    def sign(self, tag, *more):
        return self.run_tool("sign", tag, "--key", self.key, "--commit", COMMIT, "--out", self.out, *more)

    def test_a_stable_release_is_signed_from_its_files_bytes_in_the_stable_namespace(self):
        RELEASES["v0.9.1"] = release("0.9.1")
        code, said = self.sign("v0.9.1")
        self.assertEqual(code, 0, said)
        want = {n: sha(b) for n, b in RELEASES["v0.9.1"].items() if not n.endswith((".sha256", ".attestation.jsonl"))}
        self.assertEqual(self.lists(), want)
        self.assertEqual(self.taken("v0.9.1"), (want, "AerieOS's release key", ""))
        self.assertIn("gh is not here, so no build attestation is checked", said)

    def test_a_sha256_file_that_lies_is_caught_because_the_bytes_are_hashed(self):
        # What the audit found: the list was written from these files, so a
        # replaced file with its sha256 replaced beside it was signed.
        RELEASES["v0.9.1"] = release("0.9.1")
        RELEASES["v0.9.1"]["aerieos-app-0.9.1.apk"] = b"another app"
        code, said = self.sign("v0.9.1")
        self.assertEqual(code, 1)
        self.assertIn("aerieos-app-0.9.1.apk.sha256 says", said)
        self.assertIn("the release contradicts itself", said)
        self.assertFalse(os.path.exists(os.path.join(self.out, "SHA256SUMS")))
        # ...and with both replaced, the list holds the bytes that are there,
        # which is what its signer is shown before the signature is made.
        RELEASES["v0.9.1"]["aerieos-app-0.9.1.apk.sha256"] = (sha(b"another app") + "  x\n").encode()
        code, said = self.sign("v0.9.1")
        self.assertEqual(code, 0, said)
        self.assertEqual(self.lists()["aerieos-app-0.9.1.apk"], sha(b"another app"))

    def test_a_file_nothing_vouches_for_is_refused_and_an_attestation_is_held_to_the_tags_workflow(self):
        RELEASES["v0.9.1"] = release("0.9.1")
        del RELEASES["v0.9.1"]["aerieos-os-0.9.1.iso.sha256"]
        code, said = self.sign("v0.9.1")
        self.assertEqual(code, 1)
        self.assertIn("aerieos-os-0.9.1.iso has neither a sha256 beside it that matches nor a build attestation that verifies", said)
        # A gh that verifies: the file is taken on its attestation, asked
        # for by the release workflow at this very tag.
        self.gh = os.path.join(self.d, "gh")
        with open(self.gh, "w") as f:
            f.write(f'#!/bin/sh\necho "$*" >> "{self.d}/gh.log"\nexit "${{FAKE_GH_RC:-0}}"\n')
        os.chmod(self.gh, stat.S_IRWXU)
        code, said = self.sign("v0.9.1")
        self.assertEqual(code, 0, said)
        self.assertIn("aerieos-os-0.9.1.iso  (its build attestation verifies)", said)
        with open(os.path.join(self.d, "gh.log")) as f:
            log = f.read()
        self.assertIn("attestation verify", log)
        self.assertIn("--cert-identity-regex " + tool.identity("v0.9.1"), log)
        self.assertRegex("https://github.com/aquilaelabs/aerieos/.github/workflows/build-image.yml@refs/tags/v0.9.1", tool.identity("v0.9.1"))
        for other in ("https://github.com/aquilaelabs/aerieos/.github/workflows/build-image.yml@refs/tags/v0.9.10",
                      "https://github.com/aquilaelabs/aerieos/.github/workflows/build-image.yml@refs/heads/main",
                      "https://github.com/aquilaelabs/aerieos/.github/workflows/lint.yml@refs/tags/v0.9.1",
                      "https://github.com/somebody/aerieos/.github/workflows/build-image.yml@refs/tags/v0.9.1"):
            self.assertNotRegex(other, tool.identity("v0.9.1"))
        # --attested: a file with a sha256 and no attestation is refused too.
        with mock.patch.dict(os.environ, {"FAKE_GH_RC": "1"}):
            RELEASES["v0.9.1"] = release("0.9.1")
            self.assertEqual(self.sign("v0.9.1")[0], 0)
            code, said = self.sign("v0.9.1", "--attested")
        self.assertEqual(code, 1)
        self.assertIn("--attested asks for one", said)

    def test_a_release_short_of_a_file_or_on_another_commit_is_not_signed(self):
        RELEASES["v0.9.1"] = release("0.9.1", without=("aerieos-os-0.9.1.iso",))
        code, said = self.sign("v0.9.1")
        self.assertEqual(code, 3)
        self.assertIn("aerieos-os-0.9.1.iso still missing", said)
        RELEASES["v0.9.1"] = release("0.9.1")
        code, said = self.run_tool("sign", "v0.9.1", "--key", self.key, "--commit", "8" * 12, "--out", self.out)
        self.assertEqual(code, 1)
        self.assertIn("not signed (the tag was moved", said)

    def test_a_key_that_is_not_the_stable_signer_named_is_said(self):
        RELEASES["v0.9.1"] = release("0.9.1")
        other = os.path.join(self.d, "other")
        subprocess.run(["ssh-keygen", "-q", "-t", "ed25519", "-N", "", "-f", other], check=True, stdin=subprocess.DEVNULL, timeout=30)
        code, said = self.run_tool("sign", "v0.9.1", "--key", other, "--commit", COMMIT, "--out", self.out)
        self.assertEqual(code, 1)
        self.assertIn("is not the stable signer config/release-signers names", said)
        self.assertFalse(os.path.exists(os.path.join(self.out, "SHA256SUMS.sig")))


class TheList(unittest.TestCase):
    def test_what_the_list_names_and_what_a_release_lacks(self):
        self.assertEqual([n for n in ("a.iso", "a.iso.sha256", "a.attestation.jsonl", "SHA256SUMS", "SHA256SUMS.sig", "a.apk")
                          if tool.listed(n)], ["a.iso", "a.apk"])
        d = tempfile.mkdtemp()
        self.addCleanup(shutil.rmtree, d, True)
        path = os.path.join(d, "list")
        with open(path, "w") as f:
            f.write("# files\nx-@VER@.iso\nx-@VER@-*.bin\nSHA256SUMS\nSHA256SUMS.sig\n")
        self.assertEqual(tool.missing(["x-1.2.3.iso"], "1.2.3", path), ["x-1.2.3-*.bin"])
        self.assertEqual(tool.missing(["x-1.2.3.iso", "x-1.2.3-arm.bin"], "1.2.3", path), [])
        self.assertIsNone(tool.missing([], "1.2.3", os.path.join(d, "none")))

    def test_the_repositorys_release_is_not_whole_without_its_signed_list(self):
        with open(os.path.join(ROOT, ".release-files"), encoding="utf-8") as f:
            names = [ln.strip() for ln in f if ln.strip() and not ln.startswith("#")]
        self.assertIn("SHA256SUMS", names)
        self.assertIn("SHA256SUMS.sig", names)
        # ...by the reading the last job publishes a dev build on.
        ver = "0.9.1-dev.7"
        have = [n.replace("@VER@", ver) for n in names if n not in ("SHA256SUMS", "SHA256SUMS.sig")]
        r = subprocess.run(["bash", os.path.join(ROOT, "tools", "release-missing.sh"), os.path.join(ROOT, ".release-files"), ver, *have],
                           capture_output=True, text=True, timeout=30, check=False)
        self.assertEqual(r.stdout.split(), ["SHA256SUMS", "SHA256SUMS.sig"], r.stderr)
        # ...and the signing tools hold a release to the same list.
        self.assertEqual(tool.missing(have, ver), [])


if __name__ == "__main__":
    unittest.main()
