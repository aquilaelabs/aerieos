"""What a login shell reads is words of a known shape, each in single quotes.

/etc/profile.d/builderbot-session.sh is sourced by every login shell of the
session account. The agent and the provisioner each write the toolchain
store's path and the controller's address into it, so a store is taken only
at a plain path (letters, digits and . _ / + @ -, no .. part), a
controller's address is one shape (http or https, a host, a port or none),
and either one found in another shape is left out of the file: a node whose
record already holds such a path keeps its store, and a re-enrollment does
not move it back onto the default."""
import os
import re
import shutil
import subprocess
import tempfile
import types
import unittest
from unittest import mock

import agentpkg  # noqa: E402

HERE = os.path.dirname(os.path.abspath(__file__))
REPO = os.path.normpath(os.path.join(HERE, "..", "..", ".."))
agent = agentpkg.load("aerieos_agent_shell_shapes")
agent.log = lambda *a, **k: None
agent.log_once = lambda *a, **k: None
stores = agent.module("stores")
configplane = agent.module("configplane")
controller = agent.module("controller")

HOSTILE_PATHS = ['/mnt/x"; touch /tmp/pwned; "', "/mnt/$(id)", "/mnt/`id`", "/mnt/a;b", "/mnt/a'b", "/mnt/a\nb", "/mnt/a&b",
                 "/mnt/a|b", "/mnt/a>b", "/mnt/a\\b", "/mnt/a(b)", "/mnt/a*", "/mnt/~x", "/mnt/a,b", "/mnt/a:b", "/mnt/a=b"]
HOSTILE_URLS = ['http://h"; id; "', "http://h/$(id)", "http://h/`id`", "http://h;id", "http://h/path", "http://h/a/b",
                "http://user@h", "http://h:port", "http://h:123456", "ftp://h", "https://", "http://-h", "http://h?x=1",
                "http://h#x", "http://h'x", "http://h x", "http://h\n", "HTTP://h", "http://[::1", "http://::1]"]


class Shapes(unittest.TestCase):
    def test_a_store_s_path(self):
        for p in ("/mnt/tank/bb/toolchains", "/var/lib/aerieos/x", "/mnt/user@host/a+b/c.d_e-f", "/srv/t/n_0123abcd"):
            self.assertTrue(stores.path_plain(p), p)
        for p in [*HOSTILE_PATHS, "", "relative/x", "/mnt/../etc", "/mnt/a/..", "/mnt/a b"]:
            self.assertFalse(stores.path_plain(p), p)

    def test_a_new_store_is_taken_only_at_a_plain_path(self):
        for p in HOSTILE_PATHS:
            self.assertTrue(stores.store_path_ok(p), p)
        self.assertEqual(stores.store_path_ok("/mnt/tank/bb/toolchains"), "")

    def test_a_store_a_node_already_has_stays_where_it_is(self):
        """A path from before the shape was held, in the node's own record,
        is kept by an enrollment run again: the store does not move back
        onto the default."""
        cli = agent.module("cli")
        default = dict(agent.DEFAULT_STORES)
        had = {"stores": {"toolchains": "/mnt/tank,one/tc", "data": "/mnt/tank/data"}}
        got = cli.stores_kept(dict(default), set(), had)
        self.assertEqual(got["toolchains"], "/mnt/tank,one/tc")
        self.assertEqual(got["data"], "/mnt/tank/data")
        # ...and what was never a place for a store is still not kept.
        got = cli.stores_kept(dict(default), set(), {"stores": {"toolchains": "/etc"}})
        self.assertEqual(got["toolchains"], default["toolchains"])

    def test_the_controller_s_address(self):
        for u in ("http://10.0.0.5:8080", "https://aerie.example.org", "https://aerie.example.org/", "http://[fd00::1]:8080",
                  "https://[::1]", "http://box", "https://a-b.c.d:443"):
            self.assertTrue(controller.address_ok(u), u)
        for u in [*HOSTILE_URLS, "", None, 5]:
            self.assertFalse(controller.address_ok(u), u)
        self.assertTrue(controller.address_ok("https://h", https=True))
        self.assertFalse(controller.address_ok("http://h", https=True))


class Profile(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.mkdtemp()
        self.addCleanup(shutil.rmtree, self.tmp, True)
        self.profile = os.path.join(self.tmp, "builderbot-session.sh")
        with open(self.profile, "w") as f:
            f.write("# from the provisioner\n")
        self.canary = os.path.join(self.tmp, "pwned")

    def written(self, root, ctl, who="builder", pin=""):
        a = object.__new__(agent.Agent)
        a.SESSION_PROFILE = self.profile
        a.state = {"pin": pin}
        a.ctl = types.SimpleNamespace(url=ctl)
        a.session_account = lambda: who
        with mock.patch.object(configplane.os, "geteuid", lambda: 0), \
                mock.patch.object(configplane, "tc_root", lambda st: root):
            a.write_session_profile()
        with open(self.profile) as f:
            return f.read()

    def sourced(self, text, who="builder"):
        """The file read by a shell that is the session account: what it
        exported, with a canary no line of it may touch."""
        script = os.path.join(self.tmp, "run.sh")
        with open(script, "w") as f:
            f.write(f"id() {{ echo {who}; }}\nhostname() {{ echo box; }}\n. {self.profile}\n"
                    'printf "%s\\n%s\\n%s\\n" "$BB_CONTROLLER" "$BB_CONTROLLER_PIN" "$PATH"\n')
        p = subprocess.run(["sh", script], capture_output=True, text=True, timeout=20, check=False,
                           env={"PATH": "/usr/bin:/bin", "HOME": "/home/builder"})
        self.assertEqual(p.returncode, 0, p.stderr + text)
        self.assertEqual(p.stderr, "", text)
        self.assertFalse(os.path.exists(self.canary), text)
        return p.stdout.split("\n")

    def test_plain_values_are_written_in_single_quotes_and_read_back(self):
        pin = "sha256//" + "A" * 43 + "="
        text = self.written("/mnt/tank/tc/n_0123abcd", "https://aerie.example.org:8443", pin=pin)
        self.assertIn("export BB_CONTROLLER='https://aerie.example.org:8443'\n", text)
        self.assertIn(f"export BB_CONTROLLER_PIN='{pin}'\n", text)
        self.assertIn("PATH='/mnt/tank/tc/n_0123abcd/.bb/current/scripts':\"$PATH\"\n", text)
        os.makedirs("/tmp") if not os.path.isdir("/tmp") else None
        ctl, got_pin, path = self.sourced(text)[:3]
        self.assertEqual((ctl, got_pin), ("https://aerie.example.org:8443", pin))
        self.assertTrue(path.startswith("/home/builder/.local/bin:"))

    def test_a_store_at_another_shape_is_left_out_and_nothing_of_it_runs(self):
        for bad in HOSTILE_PATHS + [f"/mnt/x'; touch {self.tmp}/pwned; '", f"/mnt/$(touch {self.tmp}/pwned)"]:
            text = self.written(bad, "http://10.0.0.5:8080")
            self.assertNotIn(".bb/current/scripts", text, bad)
            self.assertIn("export BB_CONTROLLER='http://10.0.0.5:8080'\n", text)
            self.sourced(text)

    def test_an_address_at_another_shape_is_left_out_and_nothing_of_it_runs(self):
        for bad in HOSTILE_URLS + [f"http://h'; touch {self.tmp}/pwned; '", f"http://$(touch {self.tmp}/pwned)"]:
            text = self.written("/mnt/tank/tc", bad, pin="sha256//" + "A" * 43 + "=")
            self.assertNotIn("BB_CONTROLLER", text, bad)
            self.assertIn("PATH='/mnt/tank/tc/.bb/current/scripts'", text)
            self.sourced(text)

    def test_an_account_whose_name_is_not_plain_leaves_the_file_as_it_was(self):
        for who in ("*)\n touch /tmp/x;;", "a b", "", "a|b", "$(id)"):
            self.assertEqual(self.written("/mnt/tank/tc", "http://h", who=who), "# from the provisioner\n")


class Provisioner(unittest.TestCase):
    """The provisioner's first write of the same file, run as it is in the
    script with the file's place stood in for."""

    def setUp(self):
        self.tmp = tempfile.mkdtemp()
        self.addCleanup(shutil.rmtree, self.tmp, True)
        with open(os.path.join(REPO, "nodes", "provision-linux.sh"), encoding="utf-8") as f:
            text = f.read()
        m = re.search(r'\n(    prof_ctl="\$\{CONTROLLER%/\}".*?\} > /etc/profile\.d/builderbot-session\.sh\n    fi\n)', text, re.S)
        self.assertTrue(m, "the provisioner writes the session profile from held values")
        self.out = os.path.join(self.tmp, "profile.sh")
        self.piece = m.group(1).replace("/etc/profile.d/builderbot-session.sh", self.out)

    def write(self, ctl, store, name="builder", key=""):
        if os.path.exists(self.out):
            os.unlink(self.out)
        p = subprocess.run(["bash", "-c", self.piece], capture_output=True, text=True, timeout=20, check=False,
                           env={"PATH": "/usr/bin:/bin", "CONTROLLER": ctl, "STORE_TOOLCHAINS": store, "SESSION_NAME": name,
                                "CTL_KEY": key})
        self.assertEqual((p.returncode, p.stderr), (0, ""))
        if not os.path.exists(self.out):
            return None
        with open(self.out) as f:
            return f.read()

    def test_plain_values_are_written_quoted(self):
        key = "sha256//" + "A" * 43 + "="
        text = self.write("https://aerie.example.org:8443/", "/mnt/tank/tc", key=key)
        self.assertIn("    builder)\n", text)
        self.assertIn("        export BB_CONTROLLER='https://aerie.example.org:8443'\n", text)
        self.assertIn(f"        export BB_CONTROLLER_PIN='{key}'\n", text)
        self.assertIn("        [ -d '/mnt/tank/tc/.bb/current/scripts' ] \\\n"
                      "            && PATH='/mnt/tank/tc/.bb/current/scripts':\"$PATH\"\n", text)
        self.assertEqual(subprocess.run(["sh", "-n", self.out], capture_output=True, check=False).returncode, 0)

    def test_values_of_another_shape_are_left_out(self):
        for bad in HOSTILE_URLS:
            if "\n" in bad:
                continue
            text = self.write(bad, "/mnt/tank/tc")
            self.assertNotIn("BB_CONTROLLER", text, bad)
        for bad in [*HOSTILE_PATHS, "/mnt/../etc"]:
            text = self.write("http://h", bad)
            self.assertNotIn("current/scripts", text, bad)
            self.assertIn("export BB_CONTROLLER='http://h'\n", text)
        self.assertIsNone(self.write("http://h", "/mnt/tank/tc", name="a b"))


if __name__ == "__main__":
    unittest.main()
