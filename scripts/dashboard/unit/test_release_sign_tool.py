"""tools/release-sign.py: the list of a release's files is made from
the files themselves and signed in the namespace of who holds the key. The
audit of 20 Nov found `sign` wrote SHA256SUMS from the .sha256 files the
release carries, so whoever replaced a file and its sha256 got the
signature too. Here against a stand-in for GitHub's API on a local port,
with real keys and ssh-keygen: `seal` (CI, the release build's key from
AERIEOS_RELEASE_KEY, the namespace aerieos-dev) refuses a stable tag, a
release short of a file and a key no install names, and makes a signature
the verifiers take for a dev build; `sign` (the stable key's holder,
aerieos-release) hashes each file's bytes and stops at a sha256 file that
lies. Either way each file of a release is held to the build attestation
of the workflow that builds it, whatever sha256 sits beside it, and the
Android app, which no build attests, to its signature by a certificate
config/apk-signers names (stand-ins for gh and apksigner), and neither
tool missing is let by; a release sealed already is sealed again the
same, and a folder is sealed dry with a key made for the run, as the
rehearsal does. GitHub's answers, a download and gh's check are asked
again where the network failed them, and a 404 is not."""
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
# The certificate the stand-in apksigner says signed the app, and another.
CERT, OTHER_CERT = "de66" * 16, "0bad" * 16
# What the stand-in serves: {tag: {name: bytes}}; the paths it answers 503
# for, as many times as each says; and every path it was asked.
RELEASES, FLAKY, HITS = {}, {}, []


class GitHub(BaseHTTPRequestHandler):
    def log_message(self, *a):
        pass

    def do_GET(self):
        base = f"http://127.0.0.1:{self.server.server_port}"
        path = self.path.split("?")[0]
        HITS.append(path)
        if FLAKY.get(path):
            FLAKY[path] -= 1
            self.send_error(503)
            return
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
        FLAKY.clear()
        HITS.clear()
        self.d = tempfile.mkdtemp()
        self.addCleanup(shutil.rmtree, self.d, True)
        self.signers = os.path.join(self.d, "release-signers")
        self.files = os.path.join(self.d, ".release-files")
        with open(self.files, "w") as f:
            f.write("# what a release carries\naerieos-controller-@VER@.tar.gz\naerieos-controller-@VER@.tar.gz.sha256\n"
                    "aerieos-app-@VER@.apk\naerieos-os-@VER@.iso\naerieos-os-@VER@.attestation.jsonl\nSHA256SUMS\nSHA256SUMS.sig\n")
        self.out = os.path.join(self.d, "out")
        # Neither gh nor apksigner is here unless a test stands one in, on
        # whatever machine this runs: a hosted runner carries both. Seal and
        # Sign stand both in, and a test takes one away.
        self.gh = self.aps = None
        self.apk_signers = os.path.join(self.d, "apk-signers")
        with open(self.apk_signers, "w") as f:
            f.write(f"# the app's certificate\n{tool.fingerprint(CERT)}\n")
        self.made = []
        real_which, real_mkdtemp = shutil.which, tempfile.mkdtemp

        def mkdtemp(*a, **k):
            self.made.append(real_mkdtemp(*a, **k))
            return self.made[-1]
        for p in (mock.patch.multiple(tool, API=f"http://127.0.0.1:{self.srv.server_port}", SIGNERS=self.signers, FILES=self.files,
                                      APK_SIGNERS=self.apk_signers, POLL=0.2, RETRY_WAIT=0),
                  mock.patch.object(tool.shutil, "which",
                                    side_effect=lambda n: self.gh if n == "gh" else self.aps if n == "apksigner" else real_which(n)),
                  mock.patch.object(tool.tempfile, "mkdtemp", side_effect=mkdtemp),
                  mock.patch.dict(os.environ, {"GH_TOKEN": "t", "ANDROID_HOME": "", "ANDROID_SDK_ROOT": "", "GITHUB_ACTIONS": ""})):
            p.start()
            self.addCleanup(p.stop)

    def stand_in(self, name, body):
        """A stand-in for a tool the release is checked with, which says what
        it was asked in NAME.log."""
        path = os.path.join(self.d, name)
        with open(path, "w") as f:
            f.write(f'#!/bin/sh\necho "$*" >> "{self.d}/{name}.log"\n{body}\n')
        os.chmod(path, stat.S_IRWXU)
        return path

    def fake_gh(self):
        self.gh = self.stand_in("gh", 'exit "${FAKE_GH_RC:-0}"')

    def fake_apksigner(self):
        # What apksigner verify --print-certs prints: each signer's
        # certificate, and a source stamp's, which is nobody's signature; as
        # build-tools up to 36 say it, or with FAKE_APS_FORM=37 as 37 does,
        # the scheme first (what GitHub's runner said for v0.9.0-dev.6049).
        self.aps = self.stand_in("apksigner", '[ "${FAKE_APS_RC:-0}" = 0 ] || { echo "DOES NOT VERIFY" >&2; exit 1; }\n'
                                 'if [ "${FAKE_APS_FORM:-}" = 37 ]; then\n'
                                 'echo "V3.0 Signer: certificate DN: CN=AerieOS"\n'
                                 f'echo "V3.0 Signer: certificate SHA-256 digest: ${{FAKE_APS_CERT:-{CERT}}}"\n'
                                 f'echo "Source Stamp Signer: certificate SHA-256 digest: {"f" * 64}"\n'
                                 'else\n'
                                 'echo "Signer #1 certificate DN: CN=AerieOS"\n'
                                 f'echo "Signer #1 certificate SHA-256 digest: ${{FAKE_APS_CERT:-{CERT}}}"\n'
                                 f'echo "Source Stamp Signer certificate SHA-256 digest: {"f" * 64}"\n'
                                 'fi')

    def asked(self, name):
        with open(os.path.join(self.d, name + ".log")) as f:
            return f.read()

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
        self.fake_gh()
        self.fake_apksigner()

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

    def test_the_app_is_held_to_its_signature_and_every_other_file_to_its_builder(self):
        tag, apk = "v0.9.1-dev.7", "aerieos-app-0.9.1-dev.7.apk"
        RELEASES[tag] = release("0.9.1-dev.7")
        RELEASES[tag]["aerieos-companion-0.9.1-dev.7.exe"] = b"the companion"
        RELEASES[tag]["aerieos-companion-0.9.1-dev.7.exe.sha256"] = (sha(b"the companion") + "  the companion\n").encode()
        code, said = self.run_tool("seal", tag, "--out", self.out, env=self.env)
        self.assertEqual(code, 0, said)
        self.assertIn(f"{apk}  ({apk}.sha256 matches and apksigner verifies it as signed by a certificate config/apk-signers names)", said)
        self.assertIn("verify --print-certs ", self.asked("apksigner"))
        # Each other file's attestation was asked of the workflow that
        # builds it: the companion's of the workflow the release calls.
        log = self.asked("gh")
        self.assertNotIn(apk, log)
        self.assertEqual(log.count("attestation verify"), 3, log)
        exe = tool.identity(tag, "aerieos-companion-0.9.1-dev.7.exe")
        at = "https://github.com/aquilaelabs/aerieos/.github/workflows/"
        self.assertIn("--cert-identity-regex " + exe, log)
        # ...at the commit the tag names, on a hosted runner: a tag's name
        # alone is what a moved tag and a run started again would carry too.
        for line in [ln for ln in log.splitlines() if "attestation verify" in ln]:
            self.assertIn(f"--deny-self-hosted-runners --source-digest {COMMIT}", line)
        self.assertRegex(at + f"companion-app.yml@refs/tags/{tag}", exe)
        self.assertNotRegex(at + f"build-image.yml@refs/tags/{tag}", exe)
        self.assertEqual(log.count(tool.identity(tag, "aerieos-os-0.9.1-dev.7.iso")), 2, "the bundle and the ISO, of the release workflow")
        # A file the table names nowhere is taken from the workflows it
        # names and from no other.
        new = tool.identity(tag, "aerieos-something-new.bin")
        for flow, takes in (("build-image.yml", True), ("companion-app.yml", True), ("lint.yml", False), ("seal-release.yml", False)):
            (self.assertRegex if takes else self.assertNotRegex)(at + f"{flow}@refs/tags/{tag}", new)
        # Signed by a certificate the file does not name: refused, naming it.
        os.remove(os.path.join(self.out, "SHA256SUMS"))
        code, said = self.run_tool("seal", tag, "--out", self.out, env=self.env | {"FAKE_APS_CERT": OTHER_CERT})
        self.assertEqual(code, 1)
        self.assertIn(f"{apk} is signed by a certificate config/apk-signers does not name ({tool.fingerprint(OTHER_CERT)})", said)
        self.assertFalse(os.path.exists(os.path.join(self.out, "SHA256SUMS")))
        # ...unless another file is named that does.
        mine = os.path.join(self.d, "mine")
        with open(mine, "w") as f:
            f.write(f"{OTHER_CERT}  # a fork's own key\n")
        self.assertEqual(self.run_tool("seal", tag, "--apk-signers", mine, "--out", self.out,
                                       env=self.env | {"FAKE_APS_CERT": OTHER_CERT})[0], 0)
        # Not signed at all: refused with apksigner's own reason.
        code, said = self.run_tool("seal", tag, "--out", self.out, env=self.env | {"FAKE_APS_RC": "1"})
        self.assertEqual(code, 1)
        self.assertIn(f"{apk} is not an APK apksigner verifies as signed: DOES NOT VERIFY", said)
        # A file with no attestation is refused, naming who should have made
        # it, though its sha256 matches: whoever replaced the file could
        # replace that too.
        code, said = self.run_tool("seal", tag, "--out", self.out, env=self.env | {"FAKE_GH_RC": "1"})
        self.assertEqual(code, 1)
        self.assertIn("aerieos-companion-0.9.1-dev.7.exe has no build attestation by companion-app.yml at v0.9.1-dev.7, "
                      f"from commit {COMMIT[:12]}, that verifies (gh said: it gave no reason)", said)

    def test_a_release_is_not_sealed_where_gh_or_apksigner_is_not_here_to_check_it(self):
        tag = "v0.9.1-dev.7"
        RELEASES[tag] = release("0.9.1-dev.7")
        self.aps = None
        code, said = self.run_tool("seal", tag, "--out", self.out, env=self.env)
        self.assertEqual(code, 1)
        self.assertIn("apksigner is not here to check the Android app's signature with", said)
        self.assertFalse(os.path.exists(os.path.join(self.out, "SHA256SUMS")))
        self.gh = None
        code, said = self.run_tool("seal", tag, "--out", self.out, env=self.env)
        self.assertEqual(code, 1)
        self.assertIn("gh is not here to verify each file's build attestation with", said)
        self.assertFalse(os.path.exists(os.path.join(self.out, "SHA256SUMS")))

    def test_each_way_apksigner_says_a_signer_is_read_and_a_source_stamp_is_never_one(self):
        tag, apk = "v0.9.1-dev.7", "aerieos-app-0.9.1-dev.7.apk"
        RELEASES[tag] = release("0.9.1-dev.7")
        self.fake_apksigner()
        env = self.env | {"FAKE_APS_FORM": "37"}
        code, said = self.run_tool("seal", tag, "--out", self.out, env=env)
        self.assertEqual(code, 0, said)
        self.assertIn(f"{apk}  ({apk}.sha256 matches and apksigner verifies it as signed by a certificate config/apk-signers names)", said)
        os.remove(os.path.join(self.out, "SHA256SUMS"))
        code, said = self.run_tool("seal", tag, "--out", self.out, env=env | {"FAKE_APS_CERT": OTHER_CERT})
        self.assertEqual(code, 1)
        self.assertIn(f"is signed by a certificate config/apk-signers does not name ({tool.fingerprint(OTHER_CERT)})", said)
        # Lines as each build-tools prints them (35 and 36, then 37, for a
        # key signed alone and one rotated to a successor), the scheme's
        # other lines and a stamp's in either form taken by nothing.
        a, b, stamp = "a" * 64, "b" * 64, "f" * 64
        said = "\n".join([
            "Signer #1 certificate DN: CN=AerieOS", f"Signer #1 certificate SHA-256 digest: {a}",
            "Signer #1 certificate SHA-1 digest: " + "c" * 40,
            f"Signer (minSdkVersion=33, maxSdkVersion=2147483647) certificate SHA-256 digest: {b}",
            f"V3.0 Signer: certificate SHA-256 digest: {a.upper()}", f"V3.1 Signer: certificate SHA-256 digest: {b}",
            f"V2 Signer: certificate SHA-256 digest: {a}",
            f"Source Stamp Signer certificate SHA-256 digest: {stamp}",
            f"Source Stamp Signer: certificate SHA-256 digest: {stamp}"])
        self.assertEqual([m.group(1).lower() for m in tool.SIGNER_CERT.finditer(said)], [a, b, a, b, a])

    def test_apksigner_is_found_in_the_newest_build_tools_of_the_sdk_a_runner_carries(self):
        sdk = os.path.join(self.d, "sdk")
        for ver in ("34.0.0", "35.0.1", "9.0.0"):
            os.makedirs(os.path.join(sdk, "build-tools", ver))
            with open(os.path.join(sdk, "build-tools", ver, "apksigner"), "w") as f:
                f.write("#!/bin/sh\n")
            os.chmod(os.path.join(sdk, "build-tools", ver, "apksigner"), stat.S_IRWXU)
        self.aps = None
        self.assertEqual(tool.apksigner(), "")
        with mock.patch.dict(os.environ, {"ANDROID_HOME": sdk}):
            self.assertEqual(tool.apksigner(), os.path.join(sdk, "build-tools", "35.0.1", "apksigner"))
        # The committed file names the certificate every release's notes give.
        with mock.patch.object(tool, "APK_SIGNERS", os.path.join(ROOT, "config", "apk-signers")):
            self.assertEqual([tool.fingerprint(c) for c in tool.apk_signers()],
                             ["DE:66:E7:9C:EE:81:22:51:55:AB:7D:00:85:79:64:CE:9F:F8:0A:FF:A5:56:BA:D9:73:9C:EB:F1:57:D4:D7:0F"])
        self.assertEqual(tool.apk_signers(os.path.join(self.d, "none")), [])

    def test_a_release_sealed_already_is_sealed_again_the_same_and_replaced_with_each_change_said(self):
        tag, apk = "v0.9.1-dev.7", "aerieos-app-0.9.1-dev.7.apk"
        RELEASES[tag] = release("0.9.1-dev.7")
        self.assertEqual(self.run_tool("seal", tag, "--out", self.out, env=self.env)[0], 0)
        first = {}
        for n in ("SHA256SUMS", "SHA256SUMS.sig"):
            with open(os.path.join(self.out, n), "rb") as f:
                first[n] = RELEASES[tag][n] = f.read()
        # Run again for a release that carries its list: the same two files.
        again = os.path.join(self.d, "again")
        code, said = self.run_tool("seal", tag, "--out", again, env=self.env)
        self.assertEqual(code, 0, said)
        self.assertIn("is sealed already with this very list", said)
        for n, was in first.items():
            with open(os.path.join(again, n), "rb") as f:
                self.assertEqual(f.read(), was, n)
        # The app replaced since (signed again on a controller): its
        # signature vouches for it, so the list is replaced, and it says
        # what changed.
        RELEASES[tag][apk] = b"the app signed again"
        RELEASES[tag][apk + ".sha256"] = f"{sha(b'the app signed again')}  {apk}\n".encode()
        third = os.path.join(self.d, "third")
        code, said = self.run_tool("seal", tag, "--out", third, env=self.env | {"GITHUB_ACTIONS": "true"})
        self.assertEqual(code, 0, said)
        self.assertIn(f"its files have changed since: {apk} was {sha(b'the bytes of ' + apk.encode())[:12]} and is", said)
        self.assertIn("so the list is replaced by the one made now", said)
        self.assertIn("::warning title=The release's signed list is replaced::", said)
        with open(os.path.join(third, "SHA256SUMS")) as f:
            self.assertIn(f"{sha(b'the app signed again')}  {apk}", f.read())

    def test_a_folder_is_sealed_dry_with_a_key_made_for_the_run(self):
        # What the rehearsal does: a key of its own, the signers file
        # written for it, the files a branch built, and no release read.
        k = Ed25519PrivateKey.generate()
        env = {"AERIEOS_RELEASE_KEY": k.private_bytes(ser.Encoding.Raw, ser.PrivateFormat.Raw, ser.NoEncryption()).hex()}
        code, line = self.run_tool("signer", env=env)
        self.assertEqual(code, 0, line)
        self.assertRegex(line, r'^aerieos-dev namespaces="aerieos-dev" ssh-ed25519 [A-Za-z0-9+/=]+\n$')
        mine = os.path.join(self.d, "dry-signers")
        with open(mine, "w") as f:
            f.write(line)
        files = os.path.join(self.d, "built")
        os.makedirs(files)
        for n, b in release("0.9.1-dev.7", without=("aerieos-app-0.9.1-dev.7.apk",)).items():
            with open(os.path.join(files, n), "wb") as f:
                f.write(b)
        with mock.patch.object(tool, "API", "http://127.0.0.1:9/unreachable"):
            code, said = self.run_tool("seal", "v0.9.1-dev.0", "--from", files, "--signers", mine, "--out", self.out, env=env)
        self.assertEqual(code, 0, said)
        self.assertIn("which are no release's", said)
        self.assertIn("sealed the folder: 2 files in SHA256SUMS", said)
        self.assertFalse(os.path.exists(os.path.join(self.d, "gh.log")), "a folder's files are asked no attestation")
        self.assertEqual(sorted(self.lists()), ["aerieos-controller-0.9.1-dev.7.tar.gz", "aerieos-os-0.9.1-dev.7.iso"])
        self.assertEqual(sorted(os.listdir(files)), sorted(release("0.9.1-dev.7", without=("aerieos-app-0.9.1-dev.7.apk",))),
                         "the folder's files are left as they were")
        # ssh-keygen takes it against the run's own file, and no install
        # does: the committed signers do not name the key.
        sums = os.path.join(self.out, "SHA256SUMS")
        with open(sums, "rb") as f:
            self.assertEqual(subprocess.run(["ssh-keygen", "-Y", "verify", "-f", mine, "-I", "aerieos-dev", "-n", "aerieos-dev",
                                             "-s", sums + ".sig"], stdin=f, capture_output=True, timeout=30).returncode, 0)
        code, said = self.run_tool("seal", "v0.9.1-dev.0", "--from", files, "--out", self.out, env=env)
        self.assertEqual(code, 1)
        self.assertIn("is not one config/release-signers names for dev builds", said)
        # A stable tag is refused for a folder too, and a sha256 that lies stops it.
        self.assertEqual(self.run_tool("seal", "v0.9.1", "--from", files, "--signers", mine, "--out", self.out, env=env)[0], 1)
        with open(os.path.join(files, "aerieos-os-0.9.1-dev.7.iso"), "wb") as f:
            f.write(b"another image")
        code, said = self.run_tool("seal", "v0.9.1-dev.0", "--from", files, "--signers", mine, "--out", self.out, env=env)
        self.assertEqual(code, 1)
        self.assertIn("the release contradicts itself", said)


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
        self.fake_gh()
        self.fake_apksigner()

    def sign(self, tag, *more, env=None):
        return self.run_tool("sign", tag, "--key", self.key, "--commit", COMMIT, "--out", self.out, *more, env=env)

    def test_a_stable_release_is_signed_from_its_files_bytes_in_the_stable_namespace(self):
        RELEASES["v0.9.1"] = release("0.9.1")
        code, said = self.sign("v0.9.1")
        self.assertEqual(code, 0, said)
        want = {n: sha(b) for n, b in RELEASES["v0.9.1"].items() if not n.endswith((".sha256", ".attestation.jsonl"))}
        self.assertEqual(self.lists(), want)
        self.assertEqual(self.taken("v0.9.1"), (want, "AerieOS's release key", ""))
        self.assertIn("aerieos-os-0.9.1.iso  (aerieos-os-0.9.1.iso.sha256 matches and its build attestation verifies)", said)
        self.assertIn("aerieos-app-0.9.1.apk  (aerieos-app-0.9.1.apk.sha256 matches and apksigner verifies it", said)

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
        # ...and with both replaced, what holds is what vouches for the
        # file beyond the release's word: a build's file with no
        # attestation is refused (what the review of 22 Nov found sign let
        # by), and the app is held to its signature.
        RELEASES["v0.9.1"] = release("0.9.1")
        RELEASES["v0.9.1"]["aerieos-os-0.9.1.iso"] = b"another image"
        RELEASES["v0.9.1"]["aerieos-os-0.9.1.iso.sha256"] = (sha(b"another image") + "  x\n").encode()
        code, said = self.sign("v0.9.1", env={"FAKE_GH_RC": "1"})
        self.assertEqual(code, 1)
        self.assertIn("aerieos-controller-0.9.1.tar.gz has no build attestation by build-image.yml at v0.9.1", said)
        self.assertFalse(os.path.exists(os.path.join(self.out, "SHA256SUMS")))
        RELEASES["v0.9.1"]["aerieos-app-0.9.1.apk"] = b"another app"
        RELEASES["v0.9.1"]["aerieos-app-0.9.1.apk.sha256"] = (sha(b"another app") + "  x\n").encode()
        code, said = self.sign("v0.9.1", env={"FAKE_APS_CERT": OTHER_CERT})
        self.assertEqual(code, 1)
        self.assertIn("aerieos-app-0.9.1.apk is signed by a certificate config/apk-signers does not name", said)

    def test_a_release_is_not_signed_without_gh_or_apksigner_and_an_attestation_is_held_to_the_tags_workflow(self):
        RELEASES["v0.9.1"] = release("0.9.1")
        del RELEASES["v0.9.1"]["aerieos-os-0.9.1.iso.sha256"]
        # Neither tool missing is let by on the stable key holder's machine:
        # a sha256 beside a file is the release's own word.
        gh, self.gh = self.gh, None
        code, said = self.sign("v0.9.1")
        self.assertEqual(code, 1)
        self.assertIn("gh is not here to verify each file's build attestation with", said)
        self.gh, self.aps = gh, None
        code, said = self.sign("v0.9.1")
        self.assertEqual(code, 1)
        self.assertIn("apksigner is not here to check the Android app's signature with", said)
        self.fake_apksigner()
        # A gh that verifies: the file is taken on its attestation, asked
        # for by the release workflow at this very tag.
        code, said = self.sign("v0.9.1")
        self.assertEqual(code, 0, said)
        self.assertIn("aerieos-os-0.9.1.iso  (its build attestation verifies)", said)
        log = self.asked("gh")
        self.assertIn("attestation verify", log)
        iso = tool.identity("v0.9.1", "aerieos-os-0.9.1.iso")
        self.assertIn("--cert-identity-regex " + iso, log)
        self.assertIn(f"--deny-self-hosted-runners --source-digest {COMMIT}", log)
        # The Android app is asked no attestation: no build attests it.
        self.assertEqual(log.count("attestation verify"), 2, log)
        at = "https://github.com/aquilaelabs/aerieos/.github/workflows/"
        self.assertRegex(at + "build-image.yml@refs/tags/v0.9.1", iso)
        for other in (at + "build-image.yml@refs/tags/v0.9.10",
                      at + "build-image.yml@refs/heads/main",
                      at + "lint.yml@refs/tags/v0.9.1",
                      # The companion's workflow attests the companion's files alone.
                      at + "companion-app.yml@refs/tags/v0.9.1",
                      "https://github.com/somebody/aerieos/.github/workflows/build-image.yml@refs/tags/v0.9.1"):
            self.assertNotRegex(other, iso)
        # A file with a sha256 that matches and no attestation is refused.
        RELEASES["v0.9.1"] = release("0.9.1")
        code, said = self.sign("v0.9.1", env={"FAKE_GH_RC": "1"})
        self.assertEqual(code, 1)
        self.assertIn(f"has no build attestation by build-image.yml at v0.9.1, from commit {COMMIT[:12]}, that verifies", said)

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


class Retried(Tool):
    """What the network drops is asked again; what the server says is not."""

    def test_a_download_and_an_answer_dropped_once_are_asked_again_and_a_404_is_not(self):
        RELEASES["v0.9.1"] = release("0.9.1")
        FLAKY["/asset/v0.9.1/aerieos-os-0.9.1.iso"] = 2
        FLAKY["/releases"] = 1
        work = os.path.join(self.d, "work")
        os.makedirs(work)
        rel = tool.release_of("v0.9.1")
        self.assertEqual(HITS.count("/releases"), 2)
        _path, digest, _ = tool.Release(rel).fetch("aerieos-os-0.9.1.iso", work)
        self.assertEqual(digest, sha(b"the bytes of aerieos-os-0.9.1.iso"))
        self.assertEqual(HITS.count("/asset/v0.9.1/aerieos-os-0.9.1.iso"), 3)
        # Dropped more times than it is asked: the last answer is raised.
        FLAKY["/asset/v0.9.1/aerieos-os-0.9.1.iso"] = tool.TRIES
        with self.assertRaises(tool.urllib.error.HTTPError):
            tool.Release(rel).fetch("aerieos-os-0.9.1.iso", work)
        HITS.clear()
        with self.assertRaises(tool.urllib.error.HTTPError):
            tool.get(tool.API + "/asset/v0.9.1/nothing", raw=True)
        self.assertEqual(HITS, ["/asset/v0.9.1/nothing"], "a 404 is the same the next time")

    def test_gh_is_asked_again_and_its_last_reason_is_said(self):
        # The transparency log's 404 for a minute after an attestation is
        # made (v0.9.0-dev.6094's run): the second asking verifies.
        count = os.path.join(self.d, "count")
        gh = self.stand_in("gh", f'echo x >> "{count}"\n'
                                 f'[ "$(wc -l < "{count}")" -ge "${{FAKE_GH_OK_AT:-2}}" ] && exit 0\n'
                                 'echo "error fetching tlog entry - (404) Not Found" >&2; exit 1')
        f = os.path.join(self.d, "file")
        with open(f, "wb") as out:
            out.write(b"x")
        self.assertEqual(tool.attested(gh, f, "v0.9.1", "aerieos-os-0.9.1.iso", COMMIT), "")
        self.assertEqual(self.asked("gh").count("attestation verify"), 2)
        os.remove(count)
        with mock.patch.dict(os.environ, {"FAKE_GH_OK_AT": "99"}):
            self.assertEqual(tool.attested(gh, f, "v0.9.1", "aerieos-os-0.9.1.iso", COMMIT),
                             "error fetching tlog entry - (404) Not Found")
        self.assertEqual(self.asked("gh").count("attestation verify"), 2 + tool.TRIES)


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
