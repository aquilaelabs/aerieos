"""A way in at AerieOS's console (R194): the admin account made from
the kept hash at every start with sudo, locked where none is kept, nothing
done off AerieOS; and the controller's hash of a password, made by
openssl so neither the job nor its record holds the password."""
import os
import re
import subprocess
import sys
import tempfile
import unittest
from unittest import mock

import agentpkg  # noqa: E402

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))
import nodes  # noqa: E402

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
        self.open = os.path.join(d, "open")
        open(self.rel, "w").write("BUILDERBOT_OS_VERSION=1\n")
        os.environ.update(BB_OS_RELEASE=self.rel, BB_CONSOLE_HASH=self.hash, BB_CONSOLE_OPEN=self.open, BB_CONSOLE_DOOR="door")
        self.addCleanup(lambda: [os.environ.pop(k, None) for k in ("BB_OS_RELEASE", "BB_CONSOLE_HASH", "BB_CONSOLE_OPEN", "BB_CONSOLE_DOOR")])
        self.euid = os.geteuid
        os.geteuid = lambda: 0
        self.addCleanup(lambda: setattr(os, "geteuid", self.euid))

    def test_made_with_sudo_and_given_the_kept_hash(self):
        open(self.hash, "w").write(H + "\n")
        c = Calls(have=False)
        self.assertEqual(console.apply(run=c), 0)
        self.assertIn(["useradd", "-m", "-s", "/bin/bash", "-G", "sudo", "admin"], c.calls)
        self.assertIn(["usermod", "-p", H, "admin"], c.calls)
        self.assertEqual(console.console_now(), {"os": True, "set": True, "open": False})

    def test_locked_where_no_hash_is_kept(self):
        c = Calls(have=True)
        console.apply(run=c)
        self.assertIn(["usermod", "-L", "admin"], c.calls)
        self.assertEqual(console.console_now(), {"os": True, "set": False, "open": False})

    def test_an_open_login_is_left_open_at_a_start(self):
        open(self.open, "w").close()
        c = Calls(have=True)
        self.assertEqual(console.apply(run=c), 0)
        self.assertEqual(c.calls, [], "neither locked nor closed while the machine is first set up")
        self.assertEqual(console.console_now(), {"os": True, "set": False, "open": True})

    def test_a_password_set_closes_the_open_login_and_gives_the_hash(self):
        open(self.open, "w").close()
        open(self.hash, "w").write(H + "\n")
        c = Calls(have=True)
        self.assertEqual(console.apply(run=c), 0)
        self.assertEqual(c.calls[0], ["door", "close"])
        self.assertIn(["usermod", "-p", H, "admin"], c.calls)

    def test_closing_what_is_not_open_does_nothing(self):
        c = Calls(have=True)
        self.assertEqual(console.close_door(run=c), 0)
        self.assertEqual(c.calls, [])

    def test_a_door_that_will_not_run_is_said_not_raised(self):
        open(self.open, "w").close()
        def gone(argv, **kw):
            raise FileNotFoundError(argv[0])
        self.assertEqual(console.close_door(run=gone), 1)

    def test_nothing_off_builderbot_os(self):
        os.unlink(self.rel)
        c = Calls(have=False)
        self.assertEqual(console.apply(run=c), 0)
        self.assertEqual(c.calls, [])
        self.assertEqual(console.console_now(), {})


class SetupEnding(unittest.TestCase):
    """The controller tells a machine to close its open login once setup has
    ended, from the census, and not on every poll."""

    def due(self, over, reported):
        with mock.patch.object(nodes, "setup_over", lambda: over), mock.patch.object(nodes, "node", lambda nid: {"reported": reported}):
            return nodes._console_close_due("n1")

    def setUp(self):
        nodes._console_asked.clear()
        self.open = {"console": {"os": True, "set": False, "open": True}}

    def test_only_once_setup_has_ended(self):
        self.assertFalse(self.due(False, self.open))
        self.assertTrue(self.due(True, self.open))

    def test_only_where_the_census_says_it_is_open(self):
        self.assertFalse(self.due(True, {"console": {"os": True, "set": False, "open": False}}))
        self.assertFalse(self.due(True, {}))

    def test_asked_again_only_after_a_minute(self):
        self.assertTrue(self.due(True, self.open))
        self.assertFalse(self.due(True, self.open))
        nodes._console_asked["n1"] -= 61
        self.assertTrue(self.due(True, self.open))


class Hash(unittest.TestCase):
    def test_openssl_makes_the_hash_the_agent_takes(self):
        r = subprocess.run(["openssl", "passwd", "-6", "-stdin"], input="correct horse battery\n", capture_output=True, text=True, check=False)
        self.assertEqual(r.returncode, 0)
        self.assertTrue(console.HASH_RE.fullmatch(r.stdout.strip()), r.stdout)
        self.assertFalse(re.search("horse", r.stdout))


if __name__ == "__main__":
    unittest.main()
