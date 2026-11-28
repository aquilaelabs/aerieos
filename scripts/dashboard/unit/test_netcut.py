"""The network cut for a declared pack's install steps where the job account
cannot make a network namespace itself: a distribution that keeps
user namespaces from unprivileged accounts refused the cut on the dev node
and on the session node on 13 Nov, and such a pack's steps ran with the
network. A managed node's root agent installs a helper (nodes/bb-netcut) and
the one sudo rule for it; the helper makes the namespace and runs what it is
handed as the caller again, never as root."""
import importlib.machinery
import io
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

    def test_a_root_agent_names_the_account_as_sudo_does_and_gets_the_same(self):
        # The node's agent, root, runs it with no sudo for the steps of a
        # coding agent's install (sessions.agent_install): it starts it
        # with the account's uid where sudo would have put the caller's,
        # and nothing else of sudo's. The same plan: the command as that
        # account, the plain environment, and root still nobody's to name.
        me = str(ME.pw_uid) if ME.pw_uid else "1"
        started = {"PATH": "/usr/local/sbin:/usr/local/bin:/usr/sbin:/usr/bin:/sbin:/bin", "LANG": "C.UTF-8", "SUDO_UID": me}
        cmd = ["env", "HOME=/somewhere/else", "SUDO_UID=0", "bash", "held-run.sh", "--run", "/home/x/.cache/aerie-held.1", "X CLI"]
        got = netcut.plan(cmd, started, 0)
        self.assertNotIsInstance(got, str, got)
        who, argv, env = got
        self.assertEqual((str(who.pw_uid), argv, env["HOME"], env["USER"]), (me, cmd, who.pw_dir, who.pw_name))
        self.assertEqual(got[1:], netcut.plan(cmd, {**started, "SUDO_USER": who.pw_name, "SUDO_GID": str(who.pw_gid), "SUDO_COMMAND": "x"}, 0)[1:])
        self.assertIn("never root", netcut.plan(cmd, {**started, "SUDO_UID": "0"}, 0))
        self.assertIn("it is run through sudo", netcut.plan(cmd, started, int(me)), "and an account that starts it itself gets nothing")
        # What the agent starts it with is those three words and no more.
        with open(os.path.join(ROOT, "scripts", "agent", "aerieos_agent", "sessions.py"), encoding="utf-8") as f:
            self.assertIn('"SUDO_UID": str(who["user"])', f.read())

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

    def test_the_step_keeps_no_group_but_its_own(self):
        # A cut of the network alone leaves every socket on the disk in
        # reach, and the jobs account of a node not beside its controller is
        # in the docker group: a step that kept it could ask the docker
        # daemon for a container with the network and the host's root.
        who = ME if ME.pw_uid else pwd.getpwuid(1)
        now = {"uid": 0, "groups": [0]}
        ran = []

        refuse = []

        class Libc:
            def unshare(self, flags):
                ran.append(("unshare", flags.value))
                return 0

            def mount(self, src, at, kind, flags, data):
                ran.append(("mount", at.value, kind.value, flags.value, data.value, now["uid"]))
                return -1 if at.value in refuse else 0

            def prctl(self, *a):
                ran.append(("prctl", a[0].value))
                return 0

        def setuid(u):
            now["uid"] = u

        def setgroups(g):
            now["groups"] = list(g)

        def initgroups(name, gid):
            now["groups"] = [gid, 999]          # the account's groups, docker's among them

        def execvpe(path, argv, env):
            ran.append(("exec", argv, list(now["groups"]), now["uid"], env.get("BB_NETCUT_RUN")))

        def run():
            del ran[:]
            now.update(uid=0, groups=[0])
            with mock.patch.object(netcut.ctypes, "CDLL", lambda *a, **k: Libc()), \
                    mock.patch.object(netcut.ctypes, "get_errno", lambda: 1), \
                    mock.patch.multiple(netcut.os, geteuid=lambda: now["uid"], getuid=lambda: now["uid"], setuid=setuid,
                                        setgid=lambda g: None, setgroups=setgroups, initgroups=initgroups,
                                        getgroups=lambda: list(now["groups"]), execvpe=execvpe), \
                    mock.patch.object(netcut.os.path, "islink", lambda p: p == "/var/run"), \
                    mock.patch.dict(netcut.os.environ, {"SUDO_UID": str(who.pw_uid)}), \
                    mock.patch.object(netcut.sys, "stderr", io.StringIO()) as said:
                netcut.main(["true"])
            return said.getvalue()
        run()
        self.assertEqual(ran[0], ("unshare", netcut.CLONE_NEWNET))
        self.assertEqual(ran[-1], ("exec", ["true"], [], who.pw_uid, "covered"), "run as the caller, with none of its other groups")
        # The final audit's 5: a mount namespace of its own, private, with an
        # empty tmpfs over /run, made as root before the drop; /var/run is a
        # link to it here, and covered with it.
        self.assertEqual(ran[1], ("unshare", netcut.CLONE_NEWNS))
        self.assertEqual(ran[2], ("mount", b"/", None, netcut.MS_REC | netcut.MS_PRIVATE, None, 0))
        self.assertEqual(ran[3], ("mount", b"/run", b"tmpfs", netcut.MS_NOSUID | netcut.MS_NODEV | netcut.MS_NOEXEC, b"mode=0755,size=1m", 0))
        self.assertEqual([r[0] for r in ran[4:]], ["prctl", "exec"])
        # A machine that refuses the mount: the step runs as it did before
        # the cover, and is not told it was covered.
        refuse.append(b"/run")
        said = run()
        self.assertEqual(ran[-1], ("exec", ["true"], [], who.pw_uid, None))
        self.assertIn("/run is left as it is", said)

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


class VirtiofsdWrap(unittest.TestCase):
    """The VM host feature's virtiofsd wrapper kept as the bundle's
    provisioner writes it: it checks a shared folder at every
    start, and a node that had the feature kept the old one otherwise."""

    def test_a_node_with_the_wrapper_takes_the_bundles_and_one_without_gets_none(self):
        root = tempfile.mkdtemp()
        self.addCleanup(shutil.rmtree, root, True)
        tools = os.path.join(root, "tools", "current", "nodes")
        os.makedirs(tools)
        shutil.copy(os.path.join(os.path.dirname(TOOL), "provision-linux.sh"), tools)
        wrap = os.path.join(root, "builderbot-virtiofsd")
        cp, hw = agent.module("configplane"), agent.module("vmhw")
        a = object.__new__(agent.Agent)
        a.tool_lock = threading.Lock()
        for target, name, value in ((cp, "TOOLS_DIR", os.path.join(root, "tools")), (hw, "VIRTIOFSD_WRAP", wrap),
                                    (cp.os, "geteuid", lambda: 0), (cp.os, "chown", lambda *x: None)):
            p = mock.patch.object(target, name, value)
            p.start()
            self.addCleanup(p.stop)
        a.refresh_virtiofsd_wrap()
        self.assertFalse(os.path.exists(wrap), "no feature, no wrapper")
        with open(wrap, "w") as f:
            f.write("#!/bin/sh\nexec virtiofsd \"$@\"\n")
        a.refresh_virtiofsd_wrap()
        with open(wrap) as f:
            got = f.read()
        self.assertIn('[ "$here" = "$dir" ]', got)
        self.assertIn("--modcaps=-fowner:-fsetid:-setfcap:-mknod", got)
        self.assertEqual(stat.S_IMODE(os.stat(wrap).st_mode), 0o755)
