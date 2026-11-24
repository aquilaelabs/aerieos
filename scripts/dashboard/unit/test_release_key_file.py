"""config/aerieos-release.pub has one reader (scripts/lib/releasepub.py): the
Enroll script answered no key at all for a file with a third line or a
malformed one, so every node enrolled after that pinned nothing, with no
word, while tools/sign-agent.py took the same file's first two lines
whatever they held. Both read it there now, and aerie lint fails on a file
that does not parse to one key or two."""
import importlib.util
import os
import shutil
import subprocess
import sys
import tempfile
import unittest

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.normpath(os.path.join(HERE, "..", "..", ".."))
LIB = os.path.join(ROOT, "scripts", "lib")
CHECKS = os.path.join(LIB, "lint-checks.py")
SIGNER = os.path.join(ROOT, "tools", "sign-agent.py")
sys.path.insert(0, os.path.join(HERE, ".."))
sys.path.insert(0, LIB)
import enrollscript  # noqa: E402
import releasepub  # noqa: E402

A, B, C = "a1" * 32, "b2" * 32, "c3" * 32
NAME = "aerieos-release-ed25519"
HEAD = "# AerieOS's release key, public half\n#   " + NAME + " <64 hex characters>\n\n"
# Each form of the file, with the keys it names: none where it does not parse.
FORMS = {
    "the key": (f"{NAME} {A}\n", [A]),
    "the key and its spare": (f"{NAME} {A}\n{NAME} {B}\n", [A, B]),
    "the same key twice": (f"{NAME} {A}\n{NAME} {A}\n", [A]),
    "capitals": (f"{NAME} {A.upper()}\n", [A]),
    "no newline at its end, and spaces around a line": (f"  {NAME}   {A}  ", [A]),
    "a third line": (f"{NAME} {A}\n{NAME} {B}\n{NAME} {C}\n", []),
    "a key too short": (f"{NAME} {A}\n{NAME} {B[:60]}\n", []),
    "a key that is not hex": (f"{NAME} {A}\n{NAME} {'zz' * 32}\n", []),
    "a line without the name": (f"{NAME} {A}\n{B}\n", []),
    "another name": (f"ssh-ed25519 {A}\n", []),
    "words after the key": (f"{NAME} {A} the release\n", []),
    "a merge left in it": (f"<<<<<<< ours\n{NAME} {A}\n=======\n{NAME} {B}\n>>>>>>> theirs\n", []),
    "no key at all": ("", []),
}


def signer():
    spec = importlib.util.spec_from_file_location("sign_agent_under_test", SIGNER)
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


class OneReader(unittest.TestCase):
    def setUp(self):
        self.d = tempfile.mkdtemp()
        self.addCleanup(shutil.rmtree, self.d, True)
        self.pub = os.path.join(self.d, "release.pub")
        self.addCleanup(setattr, enrollscript, "RELEASE_PUB", enrollscript.RELEASE_PUB)
        enrollscript.RELEASE_PUB = self.pub
        self.signer = signer()
        self.signer.PUB = self.pub

    def put(self, text):
        with open(self.pub, "w", encoding="utf-8") as f:
            f.write(HEAD + text)

    def test_each_form_reads_as_its_keys_or_as_none_and_why(self):
        for form, (text, want) in FORMS.items():
            keys, why = releasepub.parse(HEAD + text)
            self.assertEqual(keys, want, form)
            self.assertEqual(bool(why), not want, f"{form}: a file that names no key says why ({why!r})")
        self.assertIn("line 6", releasepub.parse(HEAD + FORMS["a third line"][0].replace(C, "nope"))[1])
        self.assertIn("3 keys", releasepub.parse(HEAD + FORMS["a third line"][0])[1])
        self.assertIn("names no key", releasepub.parse(HEAD)[1])

    def test_the_enroll_script_and_the_signer_read_the_same_keys(self):
        for form, (text, want) in FORMS.items():
            self.put(text)
            self.assertEqual(enrollscript.release_keys(), want, form)
            self.assertEqual(self.signer.public_keys(), want, form)
            self.assertEqual(enrollscript.release_key(), self.signer.public_key(), form)
            self.assertEqual(bool(enrollscript.release_keys_why()), not want, form)
        os.unlink(self.pub)
        self.assertEqual((enrollscript.release_keys(), self.signer.public_keys()), ([], []))
        self.assertIn("cannot be read", enrollscript.release_keys_why())

    def test_the_signer_signs_nothing_over_a_file_that_does_not_parse(self):
        from cryptography.hazmat.primitives.asymmetric.ed25519 import Ed25519PrivateKey
        sig = os.path.join(ROOT, "scripts", "agent", "agent.sig")
        # The tree's own file, held as test_agent_release_sig holds it
        # (alone_with, the same lock by name): put back here while that test
        # stood between unlinking it and reading it, it found one (B1109).
        import fcntl
        import hashlib
        lock = open(os.path.join(tempfile.gettempdir(), "aerieos-agent-sig-"
                                 + hashlib.sha256(os.path.realpath(sig).encode()).hexdigest()[:16] + ".lock"), "w")
        fcntl.flock(lock, fcntl.LOCK_EX)
        self.addCleanup(lock.close)
        had = open(sig).read() if os.path.exists(sig) else None
        self.addCleanup(lambda: open(sig, "w").write(had) if had is not None else (os.path.exists(sig) and os.unlink(sig)))
        k = Ed25519PrivateKey.generate()
        mine = k.public_key().public_bytes_raw().hex()
        # Its own key on the first line, and a third line below: the signer
        # took the first two and signed.
        self.put(f"{NAME} {mine}\n{NAME} {B}\n{NAME} {C}\n")
        r = subprocess.run([sys.executable, SIGNER], capture_output=True, text=True, timeout=60, check=False,
                           env=dict(os.environ, AERIEOS_RELEASE_PUB=self.pub, AERIEOS_RELEASE_KEY=k.private_bytes_raw().hex()))
        self.assertEqual(r.returncode, 2, r.stdout + r.stderr)
        self.assertIn("it names 3 keys", r.stderr)
        self.assertIn("nothing is signed", r.stderr)
        r = subprocess.run([sys.executable, SIGNER, "--check"], capture_output=True, text=True, timeout=60, check=False,
                           env=dict(os.environ, AERIEOS_RELEASE_PUB=self.pub))
        self.assertEqual(r.returncode, 1, r.stdout + r.stderr)


class HeldByLint(unittest.TestCase):
    def check(self, text):
        d = tempfile.mkdtemp()
        self.addCleanup(shutil.rmtree, d, True)
        os.makedirs(os.path.join(d, "config"))
        if text is not None:
            with open(os.path.join(d, "config", "aerieos-release.pub"), "w", encoding="utf-8") as f:
                f.write(HEAD + text)
        p = subprocess.run([sys.executable, CHECKS, "releasekey"], cwd=d, capture_output=True, text=True, check=False)
        return p.returncode, p.stdout

    def test_a_file_that_does_not_parse_fails_lint(self):
        for form, (text, want) in FORMS.items():
            rc, said = self.check(text)
            self.assertEqual(rc, 0 if want else 1, f"{form}: {said}")
            self.assertIn("[ok]" if want else "[FAIL] config/aerieos-release.pub: ", said, form)
        self.assertIn("and its spare", self.check(FORMS["the key and its spare"][0])[1])
        self.assertNotIn("spare", self.check(FORMS["the key"][0])[1])
        rc, said = self.check(None)
        self.assertEqual(rc, 1, "a file that is not there fails too")
        self.assertIn("cannot be read", said)

    def test_the_committed_file_passes_and_lint_runs_the_check(self):
        p = subprocess.run([sys.executable, CHECKS, "releasekey"], cwd=ROOT, capture_output=True, text=True, check=False)
        self.assertEqual((p.returncode, p.stdout.count("[ok]")), (0, 1), p.stdout)
        self.assertEqual(len(releasepub.read(os.path.join(ROOT, "config", "aerieos-release.pub"))[0]), 2,
                         "the repository names the release key and its spare")
        aerie = open(os.path.join(ROOT, "scripts", "aerie"), encoding="utf-8").read()
        self.assertIn('python3 "$BB_LIB/lint-checks.py" releasekey || rc=1', aerie)


if __name__ == "__main__":
    unittest.main()
