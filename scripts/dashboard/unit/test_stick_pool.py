"""A stick written rarely (R161 step 10): on a stick boot the initramfs puts
the logs and the journal in memory and holds docker, containerd and libvirt
until a system pool is named; the system-pool tool says the stick's state
and refuses a pool it cannot take; the agent reports it and runs the move
as a system job; the controller keeps the report to its shape and takes the
verb only for a stick, and only for a pool the machine has mounted."""
import json
import os
import subprocess
import sys
import tempfile
import unittest
from unittest import mock

HERE = os.path.dirname(os.path.abspath(__file__))
DASH = os.path.join(HERE, "..")
ROOT = os.path.abspath(os.path.join(HERE, "..", "..", ".."))
EXTRA = os.path.join(ROOT, "image", "mkosi.extra")
TOOL = os.path.join(EXTRA, "usr", "lib", "aerieos-os", "system-pool")
sys.path.insert(0, DASH)
import agentpkg  # noqa: E402


def read(*p):
    with open(os.path.join(*p), encoding="utf-8") as f:
        return f.read()


class Job:
    def __init__(self):
        self.out = []

    def say(self, s):
        self.out.append(s)


class TheImage(unittest.TestCase):
    def test_a_stick_boot_alone_keeps_the_logs_in_memory_and_holds_docker(self):
        s = read(EXTRA, "etc", "initramfs-tools", "scripts", "init-bottom", "aerieos-os")
        block = s[s.index('if [ "$stick" = 1 ]; then'):]
        self.assertIn("aerietoram=1) stick=1", s)
        self.assertIn("commit=60", block)
        self.assertIn('tmpfs "${rootmnt}/var/log"', block)
        self.assertIn("Storage=volatile", block)
        self.assertIn("ConditionPathExists=/run/aerieos-os/system-pool-ready", block)
        self.assertIn('"${rootmnt}/usr/lib/systemd', block, "written into the root's tmpfs: this boot alone")
        unit = read(EXTRA, "usr", "lib", "systemd", "system", "aerieos-os-system-pool.service")
        self.assertIn("ConditionKernelCommandLine=aerietoram=1", unit)
        self.assertIn("Before=containerd.service docker.service libvirtd.service", unit)
        self.assertIn("Restart=on-failure", unit)
        self.assertIn("aerieos-os-system-pool.service", read(ROOT, "image", "mkosi.postinst"))
        self.assertTrue(os.access(TOOL, os.X_OK))

    def tool(self, d, *argv, stick=True):
        with open(os.path.join(d, "cmd"), "w") as f:
            f.write("aerieslot=a aerietoram=1\n" if stick else "aerieslot=a\n")
        with open(os.path.join(d, "env"), "w") as f:
            f.write(f"SDK_ROOT={d}/sdk\nWORKSPACE={d}/ws\n")
        env = dict(os.environ, BB_OS_WORK=f"{d}/work", BB_OS_RUN=f"{d}/run", BB_CMDLINE=f"{d}/cmd", BB_CONTROLLER_ENV=f"{d}/env",
                   BB_SP_DOCKER=f"{d}/docker", BB_SP_CONTAINERD=f"{d}/containerd", BB_SP_LIBVIRT=f"{d}/libvirt",
                   BB_SP_HOME=f"{d}/home", BB_SP_WORKSPACE=f"{d}/workspace", BB_SP_NO_SYSTEMCTL="1")
        return subprocess.run(["bash", TOOL, *argv], capture_output=True, text=True, env=env, check=False)

    def test_the_tool_says_what_is_on_the_stick_and_refuses_what_it_cannot_take(self):
        with tempfile.TemporaryDirectory() as d:
            os.makedirs(f"{d}/docker")
            with open(f"{d}/docker/x", "w") as f:
                f.write("x")
            got = json.loads(self.tool(d, "status").stdout)
            self.assertEqual((got["stick"], got["pool"], got["ready"], got["on_stick"]), (True, "", False, ["docker"]))
            self.assertIn("no system pool named yet", self.tool(d, "apply").stdout)
            self.assertEqual(self.tool(d, "set", "relative").returncode, 2)
            r = self.tool(d, "set", f"{d}/nopool")
            self.assertEqual(r.returncode, 2)
            self.assertIn("is not a mounted pool", r.stderr)
            self.assertEqual(json.loads(self.tool(d, "status", stick=False).stdout), {"stick": False})

    def test_set_moves_nothing_through_a_bind_that_will_not_go(self):
        # B613 (B476's hazard): a place still a mount after the umount (two
        # binds stacked) would carry the copy and the delete through to the
        # old pool. Fakes stand in for findmnt and umount: the place reads
        # as mounted as many times as the counter says, and umount counts
        # down (or does nothing, for a bind that will not go).
        with tempfile.TemporaryDirectory() as d:
            os.makedirs(f"{d}/docker")
            os.makedirs(f"{d}/pool")
            with open(f"{d}/docker/x", "w") as f:
                f.write("x")
            fakes = f"{d}/bin"
            os.makedirs(fakes)
            with open(f"{fakes}/findmnt", "w") as f:
                f.write(f'#!/bin/sh\ncase "$*" in *--target*) exit 0;; esac\n'
                        f'n=$(cat {d}/stacked 2>/dev/null || echo 0)\nfor a; do last=$a; done\n[ "$n" -gt 0 ] && case "$*" in *docker*) echo "$last";; esac\nexit 0\n')
            with open(f"{fakes}/umount", "w") as f:
                f.write(f'#!/bin/sh\n[ -e {d}/stuck ] && exit 0\nn=$(cat {d}/stacked)\necho $((n - 1)) > {d}/stacked\n')
            with open(f"{fakes}/mount", "w") as f:
                f.write("#!/bin/sh\nexit 0\n")
            for p in ("findmnt", "umount", "mount"):
                os.chmod(f"{fakes}/{p}", 0o755)
            env = {"PATH": fakes + ":" + os.environ["PATH"], "BB_SP_MOUNTED": "1", "BB_SP_NO_MOUNT": "1"}
            with open(f"{d}/stacked", "w") as f:
                f.write("2\n")
            with open(f"{d}/stuck", "w") as f:
                f.write("")
            with mock.patch.dict(os.environ, env):
                r = self.tool(d, "set", f"{d}/pool")
                self.assertEqual(r.returncode, 1, r.stderr)
                self.assertIn("is busy and stays where it is", r.stderr)
                self.assertTrue(os.path.isfile(f"{d}/docker/x"), "nothing deleted through the bind")
                self.assertFalse(os.path.exists(f"{d}/pool/aerieos-system/docker/x"), "nothing copied")
                self.assertEqual(json.loads(self.tool(d, "status").stdout)["pool"], "", "the pool is not named")
                # Two binds stacked, each letting go: unmounted twice, then moved.
                os.unlink(f"{d}/stuck")
                r = self.tool(d, "set", f"{d}/pool")
                self.assertEqual(r.returncode, 0, r.stderr)
                self.assertEqual(read(d, "stacked").strip(), "0")
                self.assertTrue(os.path.isfile(f"{d}/pool/aerieos-system/docker/x"))
                self.assertFalse(os.path.exists(f"{d}/docker/x"))

    def test_another_installs_data_on_a_pool_is_never_taken(self):
        # The operator, 6 Nov: a reinstall over an old system never takes its
        # data (containers, VMs, spaces, the accounts' homes with their
        # sign-ins); that comes over only through a move token.
        with tempfile.TemporaryDirectory() as d:
            os.makedirs(f"{d}/docker")
            os.makedirs(f"{d}/pool/aerieos-system/home/bb/.claude")
            with open(f"{d}/pool/aerieos-system/home/bb/.claude/.credentials.json", "w") as f:
                f.write("theirs")
            fakes = f"{d}/bin"
            os.makedirs(fakes)
            for p, body in (("findmnt", "#!/bin/sh\nexit 0\n"), ("umount", "#!/bin/sh\nexit 0\n"), ("mount", "#!/bin/sh\nexit 0\n")):
                with open(f"{fakes}/{p}", "w") as f:
                    f.write(body)
                os.chmod(f"{fakes}/{p}", 0o755)
            env = {"PATH": fakes + ":" + os.environ["PATH"], "BB_SP_MOUNTED": "1", "BB_SP_NO_MOUNT": "1"}
            with mock.patch.dict(os.environ, env):
                for mark in (None, "someone-else"):
                    if mark:
                        with open(f"{d}/pool/aerieos-system/.aerieos-install", "w") as f:
                            f.write(mark)
                    r = self.tool(d, "set", f"{d}/pool")
                    self.assertEqual(r.returncode, 3, r.stderr)
                    self.assertIn("another AerieOS install's data", r.stderr)
                    self.assertIn("move token", r.stderr)
                    self.assertEqual(json.loads(self.tool(d, "status").stdout)["pool"], "", "the pool is not named")
                self.assertEqual(read(d, "pool", "aerieos-system", ".aerieos-install"), "someone-else", "nothing on it touched")
                # A pool with nothing of another's is taken, and marked as this install's.
                os.makedirs(f"{d}/pool2")
                r = self.tool(d, "set", f"{d}/pool2")
                self.assertEqual(r.returncode, 0, r.stderr)
                self.assertEqual(read(d, "pool2", "aerieos-system", ".aerieos-install"), read(d, "work", "install-id")[:64])
                # ...and set again by the same install, holding its own data now.
                self.assertEqual(self.tool(d, "set", f"{d}/pool2").returncode, 0)
                # A pool in memory (the stick's own root, a tmpfs) is never one (B719).
                os.makedirs(f"{d}/pool3")
                for fst in ("tmpfs", "overlay"):
                    with mock.patch.dict(os.environ, {"BB_SP_FSTYPE": fst}):
                        r = self.tool(d, "set", f"{d}/pool3")
                    self.assertEqual(r.returncode, 2, fst)
                    self.assertIn("is not on a disk", r.stderr)
                    self.assertFalse(os.path.exists(f"{d}/pool3/aerieos-system"), "nothing moved")

    def test_the_projects_are_held_until_they_have_a_place_on_the_disks(self):
        # The operator, 1 Nov: never on the stick, on any stick.
        with tempfile.TemporaryDirectory() as d:
            with mock.patch.dict(os.environ, {"BB_SP_NO_MOUNT": "1"}):
                r = self.tool(d, "apply")
                self.assertIn("the spaces are held", r.stdout)
                self.assertEqual(json.loads(self.tool(d, "status").stdout)["projects_home"], "held")
                os.makedirs(f"{d}/share/projects")
                self.tool(d, "projects", f"{d}/share/projects")
                self.assertEqual(json.loads(self.tool(d, "status").stdout)["projects_home"], "folder")
                self.assertNotIn("held", self.tool(d, "apply").stdout)

    def test_a_home_on_the_stick_moves_to_the_pool_through_the_images_mount(self):
        # B669: /home and /workspace are bound from the data partition, so they
        # read as mounted and must still move, and nothing is left behind.
        with tempfile.TemporaryDirectory() as d:
            os.makedirs(f"{d}/home/ada"); open(f"{d}/home/ada/.signin", "w").close()
            os.makedirs(f"{d}/pool")
            fakes = f"{d}/fakes"
            os.makedirs(fakes)
            for p in ("mount", "umount", "findmnt"):
                with open(f"{fakes}/{p}", "w") as f:
                    f.write("#!/bin/sh\nexit 0\n")
                os.chmod(f"{fakes}/{p}", 0o755)
            with mock.patch.dict(os.environ, {"BB_SP_NO_MOUNT": "1", "BB_SP_MOUNTED": "1", "PATH": fakes + ":" + os.environ["PATH"]}):
                r = self.tool(d, "set", f"{d}/pool")
            self.assertEqual(r.returncode, 0, r.stderr)
            self.assertTrue(os.path.exists(f"{d}/pool/aerieos-system/home/ada/.signin"), r.stdout)
            self.assertEqual(os.listdir(f"{d}/home"), [], "off the stick")

    def test_a_folder_on_the_disks_is_named_the_projects_folder_and_let_go(self):
        # R163 (the operator, 1 Nov): a controller moved here without its
        # repositories takes the folder another system kept them in.
        with tempfile.TemporaryDirectory() as d:
            share = f"{d}/mnt/user/projects"
            for p in ("alpha", "beta"):
                os.makedirs(f"{share}/{p}")
            os.makedirs(f"{d}/ws/left")
            was = 0o775
            os.chmod(share, was)
            env = {"BB_SP_NO_MOUNT": "1"}

            def run(*argv, stick=True):
                with mock.patch.dict(os.environ, env):
                    return self.tool(d, *argv, stick=stick)
            self.assertEqual(run("projects", "relative").returncode, 2)
            self.assertEqual(run("projects", f"{d}/mnt/user/../user/projects").returncode, 2, "no .. in the path")
            self.assertIn("is not a folder", run("projects", f"{d}/nowhere").stderr)
            self.assertIn("the spaces folder itself", run("projects", f"{d}/ws/left").stderr)
            self.assertEqual(run("projects", share, stick=False).returncode, 2, "a stick's alone")
            r = run("projects", share, "alpha", "beta", "gamma")
            self.assertEqual(r.returncode, 0, r.stderr)
            self.assertIn("holds 2 of the controller's 3 spaces; not there: gamma", r.stdout)
            self.assertIn("stays underneath", r.stdout, "what the folder held before is said, never deleted")
            self.assertTrue(os.path.isdir(f"{d}/ws/left"))
            got = json.loads(run("status").stdout)
            self.assertEqual(got["projects"], share)
            self.assertNotIn("projects", got["on_stick"], "the named folder is no longer the stick's to hold")
            self.assertIn(f"the spaces are {share}", run("apply").stdout)
            # Who had it is kept on the disks, and Let it go gives it back
            # (B665); the second naming writes nothing over the first's record.
            back = f"{share}/.aerieos-give-back.sh"
            with open(back) as f:
                said = f.read()
            self.assertIn(f"chown -R {os.getuid()}:{os.getgid()} .", said)
            self.assertIn(f"chmod {oct(was)[2:]} .", said)
            self.assertIn(back, run("projects", share).stdout)
            os.chmod(share, 0o750)
            # The folder's copy is its files' owner's to change: what is
            # added there never runs as root (B719).
            with open(back, "a") as f:
                f.write(f"touch {d}/ran-as-root\n")
            r = run("projects", "--release")
            self.assertFalse(os.path.exists(f"{d}/ran-as-root"), "Let it go runs root's own copy, never the folder's")
            self.assertIn("no longer the spaces folder; its files stay", r.stdout)
            self.assertIn("given back to who had it", r.stdout)
            self.assertEqual(os.stat(share).st_mode & 0o7777, was)
            self.assertFalse(os.path.exists(back), "the record goes with the giving back")
            self.assertEqual(json.loads(run("status").stdout)["projects"], "")
            self.assertTrue(os.path.isdir(f"{share}/alpha"))
            self.assertIn("not a stick boot", self.tool(d, "apply", stick=False).stdout)


class TheAgent(unittest.TestCase):
    def setUp(self):
        self.agent = agentpkg.load("aerieos_agent_stick")
        self.av = sys.modules[self.agent.Agent.__module__.rsplit(".", 1)[0] + ".osimage"]

    def test_the_census_reads_the_tool(self):
        with tempfile.TemporaryDirectory() as d:
            fake = os.path.join(d, "system-pool")
            with open(fake, "w") as f:
                f.write('echo \'{"stick": true, "pool": "/mnt/fast", "ready": true, "on_stick": ["projects"], "written_kb": 2048, "boot_written_kb": 12}\'\n')
            with mock.patch.dict(os.environ, {"BB_OS_POOL": fake}):
                got = self.av.stick_status()
            self.assertEqual(got, {"stick": True, "pool": "/mnt/fast", "ready": True, "on_stick": ["projects"], "written_kb": 2048, "boot_written_kb": 12,
                                   "projects": "", "projects_bound": False, "projects_home": ""})
            with mock.patch.dict(os.environ, {"BB_OS_POOL": os.path.join(d, "none")}):
                self.assertEqual(self.av.stick_status(), {})

    def test_the_job_refuses_a_machine_without_the_tool_and_a_relative_path(self):
        av = self.av

        class A(av.OsImageMixin):
            def _sh(self, job, argv, **kw):
                self.ran = argv
                return 0

            def hello_again(self, why):
                self.said = why
        with tempfile.TemporaryDirectory() as d:
            with mock.patch.dict(os.environ, {"BB_OS_POOL": os.path.join(d, "none")}):
                self.assertEqual(A()._apply_system_pool(Job(), {"path": "/mnt/fast"}), ("failed", 77))
            with open(os.path.join(d, "tool"), "w"):
                pass
            with mock.patch.dict(os.environ, {"BB_OS_POOL": os.path.join(d, "tool")}):
                self.assertEqual(A()._apply_system_pool(Job(), {"path": "mnt"}), ("failed", 64))
                a = A()
                self.assertEqual(a._apply_system_pool(Job(), {"path": "/mnt/fast"}), ("succeeded", 0))
                self.assertEqual(a.ran[-2:], ["set", "/mnt/fast"])


class TheAgentsProjectsFolder(unittest.TestCase):
    def test_the_job_names_the_folder_and_the_projects_or_lets_it_go(self):
        av = sys.modules[agentpkg.load("aerieos_agent_stick2").Agent.__module__.rsplit(".", 1)[0] + ".osimage"]

        class A(av.OsImageMixin):
            def _sh(self, job, argv, **kw):
                self.ran = argv
                return 0

            def hello_again(self, why):
                self.said = why
        with tempfile.TemporaryDirectory() as d:
            with open(os.path.join(d, "tool"), "w"):
                pass
            with mock.patch.dict(os.environ, {"BB_OS_POOL": os.path.join(d, "tool")}):
                self.assertEqual(A()._apply_projects_folder(Job(), {"path": "mnt"}), ("failed", 64))
                a = A()
                self.assertEqual(a._apply_projects_folder(Job(), {"path": "/mnt/user/projects", "names": ["alpha", "../x", ".hidden", 3]}),
                                 ("succeeded", 0))
                self.assertEqual(a.ran[-3:], ["projects", "/mnt/user/projects", "alpha"], "only plain space names reach the tool")
                a._apply_projects_folder(Job(), {"release": True})
                self.assertEqual(a.ran[-2:], ["projects", "--release"])


class TheController(unittest.TestCase):
    def test_a_stick_holds_new_projects_until_they_have_a_place(self):
        import nodes
        import projects
        own = {"id": "n_1", "own": True, "reported": {"os_stick": {"stick": True, "projects_home": "held"}}}
        with mock.patch.object(nodes, "node_list", return_value=[own]), mock.patch.object(nodes, "own_machine", lambda n: n.get("own")):
            self.assertTrue(nodes.on_stick())
            self.assertIn("never kept on it", nodes.workspace_held())
            with mock.patch.object(projects, "held", nodes.workspace_held):
                body, code = projects.create({"mode": "init", "name": "x"})
            self.assertEqual(code, 409)
            self.assertIn("never kept on it", body["error"])
            own["reported"]["os_stick"]["projects_home"] = "folder"
            self.assertIn("waiting for its disks", nodes.workspace_held())
            own["reported"]["os_stick"]["projects_bound"] = True
            self.assertEqual(nodes.workspace_held(), "")
            own["reported"]["os_stick"] = {"stick": False}
            self.assertFalse(nodes.on_stick())
            self.assertEqual(nodes.workspace_held(), "")

    def test_a_projects_folder_lies_inside_the_adopted_disks_writable(self):
        import nodes
        n = {"reported": {"adopted": {"writable": True, "merged": {"/mnt/user": True},
                                      "mounts": [{"where": "/mnt/disk1", "mounted": True, "ro": False}]},
                          "pools": [{"mount": "/mnt/fast"}]}}
        self.assertEqual(nodes.projects_folder_places(n), {"/mnt/user": True, "/mnt/disk1": True, "/mnt/fast": True})
        n["reported"]["adopted"]["writable"] = False
        n["reported"]["adopted"]["mounts"][0]["ro"] = True
        self.assertEqual(nodes.projects_folder_places(n)["/mnt/user"], False)

    def test_the_census_keeps_the_stick_to_its_shape(self):
        import nodes
        got = nodes._census({"os_stick": {"stick": True, "pool": "/mnt/fast", "ready": True, "on_stick": ["projects", "evil"],
                                          "written_kb": 2048, "boot_written_kb": -1}})
        self.assertEqual(got["os_stick"], {"stick": True, "pool": "/mnt/fast", "ready": True, "on_stick": ["projects"],
                                           "written_kb": 2048, "boot_written_kb": None, "projects": "", "projects_bound": False, "projects_home": ""})
        self.assertNotIn("os_stick", nodes._census({"os_stick": {"stick": False}}))

    def test_the_verb_is_a_sticks(self):
        import nodes
        state = tempfile.mkdtemp()
        nodes.configure(state=state)
        tok = subprocess.run([sys.executable, os.path.join(ROOT, "scripts", "lib", "nodes-verbs.py"), "enroll-token",
                              os.path.join(DASH, "nodes.py"), "nas", "--own"],
                             env=dict(os.environ, DASHBOARD_STATE=state), capture_output=True, text=True, check=False)
        self.assertEqual(tok.returncode, 0, tok.stderr)
        n = next(x for x in nodes.node_list() if x["name"] == "nas")
        self.assertIn("does not run AerieOS from a stick", nodes.node_system_pool("user:t", n["id"], "/mnt/fast").get("error", ""))
        self.assertEqual(nodes.node_system_pool("user:t", "n_nothere", "/mnt/fast").get("error"), "no such node")
        self.assertIn("does not run AerieOS from a stick", nodes.node_projects_folder("user:t", n["id"], "/mnt/user/projects").get("error", ""))
        self.assertEqual(nodes.node_projects_folder("user:t", "n_nothere", "/mnt/user/projects").get("error"), "no such node")

    def test_an_adopted_pool_is_a_system_pool_whatever_its_filesystem(self):
        import nodes
        rep = {"adopted": {"mounts": [{"where": "/mnt/cache", "fs": "btrfs", "ro": False, "mounted": True},
                                      {"where": "/mnt/fast", "fs": "xfs", "ro": False, "mounted": False},
                                      {"where": "/mnt/ro", "fs": "xfs", "ro": True, "mounted": True},
                                      {"where": "/mnt/disk1", "fs": "xfs", "ro": False, "mounted": True},
                                      {"where": "/mnt/disk12", "fs": "btrfs", "ro": False, "mounted": True}]}}
        # Not one not mounted, not one read only, and not a data disk, which
        # carries the old system's parity.
        self.assertEqual(nodes.adopted_pools(rep), ["/mnt/cache"])
        self.assertEqual(nodes.adopted_pools({}), [])
        self.assertEqual(nodes.adopted_pools(None), [])


if __name__ == "__main__":
    unittest.main()
