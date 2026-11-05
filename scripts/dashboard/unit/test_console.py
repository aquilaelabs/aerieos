"""A way in at AerieOS's console (R194): the admin account made from
the kept hash at every start with sudo, locked where none is kept, nothing
done off AerieOS; and the controller's hash of a password, made by
openssl so neither the job nor its record holds the password."""
import os
import re
import subprocess
import tempfile
import unittest

import agentpkg  # noqa: E402

console = agentpkg.load("aerieos_agent_console").module("console")
H = "$6$abcdefgh$" + "A" * 86


class Calls:
    def __init__(self, have):
        self.calls, self.have = [], have

    def __call__(self, argv, **kw):
        self.calls.append(argv)
        rc = 0 if argv[0] != "getent" or self.have else 2
        return subprocess.CompletedProcess(argv, rc, b"", b"")


class Apply(unittest.TestCase):
    def setUp(self):
        d = tempfile.mkdtemp()
        self.rel, self.hash = os.path.join(d, "release"), os.path.join(d, "hash")
        open(self.rel, "w").write("BUILDERBOT_OS_VERSION=1\n")
        os.environ.update(BB_OS_RELEASE=self.rel, BB_CONSOLE_HASH=self.hash)
        self.addCleanup(lambda: [os.environ.pop(k, None) for k in ("BB_OS_RELEASE", "BB_CONSOLE_HASH")])
        self.euid = os.geteuid
        os.geteuid = lambda: 0
        self.addCleanup(lambda: setattr(os, "geteuid", self.euid))

    def test_made_with_sudo_and_given_the_kept_hash(self):
        open(self.hash, "w").write(H + "\n")
        c = Calls(have=False)
        self.assertEqual(console.apply(run=c), 0)
        self.assertIn(["useradd", "-m", "-s", "/bin/bash", "-G", "sudo", "admin"], c.calls)
        self.assertIn(["usermod", "-p", H, "admin"], c.calls)
        self.assertEqual(console.console_now(), {"os": True, "set": True})

    def test_locked_where_no_hash_is_kept(self):
        c = Calls(have=True)
        console.apply(run=c)
        self.assertIn(["usermod", "-L", "admin"], c.calls)
        self.assertEqual(console.console_now(), {"os": True, "set": False})

    def test_nothing_off_builderbot_os(self):
        os.unlink(self.rel)
        c = Calls(have=False)
        self.assertEqual(console.apply(run=c), 0)
        self.assertEqual(c.calls, [])
        self.assertEqual(console.console_now(), {})


class Hash(unittest.TestCase):
    def test_openssl_makes_the_hash_the_agent_takes(self):
        r = subprocess.run(["openssl", "passwd", "-6", "-stdin"], input="correct horse battery\n", capture_output=True, text=True, check=False)
        self.assertEqual(r.returncode, 0)
        self.assertTrue(console.HASH_RE.fullmatch(r.stdout.strip()), r.stdout)
        self.assertFalse(re.search("horse", r.stdout))


if __name__ == "__main__":
    unittest.main()
