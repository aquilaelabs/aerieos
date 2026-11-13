"""The network cut for a declared pack's install steps where the job account
cannot make a network namespace itself (R234): a distribution that keeps
user namespaces from unprivileged accounts refused the cut on the dev node
and on the session node on 13 Nov, and such a pack's steps ran with the
network. A managed node's root agent installs a helper (nodes/bb-netcut) and
the one sudo rule for it; the helper makes the namespace and runs what it is
handed as the caller again, never as root."""
import importlib.machinery
import importlib.util
import os
import pwd
import shutil
import stat
import subprocess
import sys
import tempfile
import threading
import unittest
from unittest import mock

import agentpkg  # noqa: E402

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.abspath(os.path.join(HERE, "..", "..", ".."))
sys.path.insert(0, os.path.join(HERE, ".."))
TOOL = os.path.join(ROOT, "nodes", "bb-netcut")


def load(name, path):
    loader = importlib.machinery.SourceFileLoader(name, path)
    spec = importlib.util.spec_from_loader(name, loader)
    mod = importlib.util.module_from_spec(spec)
    loader.exec_module(mod)
    return mod


netcut = load("bb_netcut", TOOL)
agent = agentpkg.load("aerieos_agent_netcut")
agent.log = lambda *a, **k: None
ME = pwd.getpwuid(os.getuid())


class Helper(unittest.TestCase):
    def test_what_it_runs_is_the_callers_and_never_roots(self):
        me = str(ME.pw_uid) if ME.pw_uid else "1"
        got = netcut.plan(["--", "sh", "-c", "true"], {"SUDO_UID": me, "LD_PRELOAD": "/tmp/x.so", "PATH": "/tmp/evil"}, 0)
        self.assertNotIsInstance(got, str, got)
        who, cmd, env = got
        self.assertEqual((str(who.pw_uid), cmd), (me, ["sh", "-c", "true"]))
        # A plain environment of the caller's, whatever sudo kept.
        self.assertEqual(set(env), {"PATH", "HOME", "USER", "LOGNAME", "SHELL", "LANG"})
        self.assertEqual((env["PATH"], env["HOME"], env["USER"]), (netcut.PATH, who.pw_dir, who.pw_name))

    def test_what_it_refuses(self):
        for argv, environ, euid, said in (
                ([], {"SUDO_UID": "1000"}, 0, "usage:"),
                (["--"], {"SUDO_UID": "1000"}, 0, "usage:"),
                (["--map-root-user", "sh"], {"SUDO_UID": "1000"}, 0, "usage:"),
                (["true"], {"SUDO_UID": "1000"}, 1000, "it is run through sudo"),
                # Root itself, or nobody sudo names: never run as root.
                (["true"], {}, 0, "never root"),
                (["true"], {"SUDO_UID": "0"}, 0, "never root"),
                (["true"], {"SUDO_UID": "1000; id"}, 0, "never root"),
                (["true"], {"SUDO_UID": "-1"}, 0, "never root"),
                (["true"], {"SUDO_UID": "4000000123"}, 0, "no account has the uid")):
            got = netcut.plan(argv, environ, euid)
            self.assertTrue(isinstance(got, str) and said in got, (argv, environ, euid, got))

    def test_run_by_an_account_it_does_nothing(self):
        if os.geteuid() == 0:
            self.skipTest("run as root")
        p = subprocess.run([sys.executable, "-I", TOOL, "sh", "-c", "echo ran"], capture_output=True, text=True, check=False)
        self.assertEqual((p.returncode, p.stdout), (64, ""))
        self.assertIn("it is run through sudo", p.stderr)

    def test_it_is_shipped_to_run(self):
        self.assertTrue(os.stat(TOOL).st_mode & stat.S_IXUSR)
        with open(TOOL, encoding="utf-8") as f:
            self.assertEqual(f.readline().strip(), "#!/usr/bin/python3 -I")
        import workspace  # noqa: PLC0415
        self.assertIn("nodes/bb-netcut", workspace.BUNDLE_PARTS)
        self.assertIn("nodes/bb-netcut", agent.ROOT_TOOLS)
        # The bundle is made from the image's own files, and one that is not
        # there is left out without a word: the dev node's first walk of this
        # had no helper for that reason.
        with open(os.path.join(ROOT, "Dockerfile"), encoding="utf-8") as f:
            image = f.read()
        for part in workspace.BUNDLE_PARTS:
            if part.startswith("nodes/"):
                self.assertRegex(image, rf"(?m)^COPY {part}/? /opt/aerieos/{part}/?$", part)


class Rule(unittest.TestCase):
    def test_the_one_command_and_nothing_else(self):
        text = agent.netcut_sudoers("builder", "/usr/local/sbin/bb-netcut")
        rules = [ln for ln in text.splitlines() if ln and not ln.startswith("#")]
        self.assertEqual(rules, ["Defaults!/usr/local/sbin/bb-netcut !use_pty, !lecture",
                                 "builder ALL=(root) NOPASSWD: /usr/local/sbin/bb-netcut"])
        visudo = shutil.which("visudo") or next((p for p in ("/usr/sbin/visudo", "/sbin/visudo") if os.path.exists(p)), "")
        if visudo:
            with tempfile.NamedTemporaryFile("w", suffix=".sudoers") as f:
                f.write(text)
                f.flush()
                p = subprocess.run([visudo, "-cf", f.name], capture_output=True, text=True, check=False)
            self.assertEqual(p.returncode, 0, p.stdout + p.stderr)


class Installed(unittest.TestCase):
    def node(self, user="builder", euid=0, stamp=True, shipped=True):
        root = tempfile.mkdtemp()
        self.addCleanup(shutil.rmtree, root, True)
        tools = os.path.join(root, "tools")
        if shipped:
            os.makedirs(os.path.join(tools, "current", "nodes"))
            shutil.copy(TOOL, os.path.join(tools, "current", "nodes", "bb-netcut"))
        stampf = os.path.join(root, "bb-sandbox")
        if stamp:
            with open(stampf, "w") as f:
                f.write("#!/bin/sh\n")
        cp = agent.module("configplane")
        a = object.__new__(agent.Agent)
        a.state = {"user": user}
        a.tool_lock = threading.Lock()
        tool, rule = os.path.join(root, "sbin", "bb-netcut"), os.path.join(root, "sudoers.d", "builderbot-netcut")
        for name, value in (("TOOLS_DIR", tools), ("SANDBOX_BIN", stampf), ("NETCUT_BIN", tool), ("NETCUT_SUDOERS", rule)):
            p = mock.patch.object(cp, name, value)
            p.start()
            self.addCleanup(p.stop)
        for target, name, value in ((cp.os, "geteuid", lambda: euid), (cp.os, "chown", lambda *a: None),
                                    (cp.shutil, "which", lambda n: None)):
            p = mock.patch.object(target, name, value)
            p.start()
            self.addCleanup(p.stop)
        return a, tool, rule

    def test_a_managed_node_gets_the_helper_and_its_rule(self):
        a, tool, rule = self.node()
        a.refresh_netcut_tool()
        with open(TOOL, encoding="utf-8") as want, open(tool, encoding="utf-8") as got:
            self.assertEqual(got.read(), want.read())
        self.assertEqual(stat.S_IMODE(os.stat(tool).st_mode), 0o755)
        self.assertEqual(stat.S_IMODE(os.stat(rule).st_mode), 0o440)
        with open(rule, encoding="utf-8") as f:
            self.assertIn(f"builder ALL=(root) NOPASSWD: {tool}\n", f.read())
        # Written once: the same again leaves both alone.
        before = (os.stat(tool).st_mtime_ns, os.stat(rule).st_mtime_ns, os.stat(tool).st_ino)
        a.refresh_netcut_tool()
        self.assertEqual((os.stat(tool).st_mtime_ns, os.stat(rule).st_mtime_ns, os.stat(tool).st_ino), before)

    def test_no_other_node_does(self):
        # An agent that is not root, a machine that was never a sandbox, jobs
        # that run as root on purpose, a bundle from before the helper.
        for kw in ({"euid": 1000}, {"stamp": False}, {"user": "root"}, {"user": ""}, {"shipped": False}):
            a, tool, rule = self.node(**kw)
            a.refresh_netcut_tool()
            self.assertFalse(os.path.exists(tool) or os.path.exists(rule), kw)

    def test_an_install_asks_for_it(self):
        work = agent.module("work")
        a = object.__new__(agent.Agent)
        a.state = {"user": "builder"}
        asked = []
        a.drop_privileges = lambda env: {}
        a.bundle = lambda job, who: "/bundle"
        a.refresh_netcut_tool = lambda: asked.append("netcut")
        a.hello = lambda *x, **k: None
        a.session_renew = lambda: None
        a._system_deps = lambda job, name, into: True

        class Job:
            def say(self, text):
                pass

            def step(self, name):
                pass

        with mock.patch.object(work, "tc_root", lambda state: "/store"), \
                mock.patch.object(work, "read_catalog", lambda into: {}), \
                mock.patch.object(work, "tc_dir", lambda *x: ""), \
                mock.patch.object(work, "tc_verbs", lambda *x: []):
            self.assertEqual(a.toolchain(Job(), {"action": "remove", "names": ["hexkit"]}), ("succeeded", 0))
            self.assertEqual(asked, [])
            self.assertEqual(a.toolchain(Job(), {"action": "install", "names": ["hexkit"]}), ("succeeded", 0))
            self.assertEqual(asked, ["netcut"])


if __name__ == "__main__":
    unittest.main()
