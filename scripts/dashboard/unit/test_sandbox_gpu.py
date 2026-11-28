"""bb-sandbox's gpu-driver and gpu-container verbs, run as the bash they are against stand-in
tools. The agent and server suites stub bb-sandbox whole, so nothing
ran this script's own lines, and its `set -euo pipefail` ended a real
install without a word on the dev node: the lookup of the installed
branch asked dpkg for packages that were not there. This runs the helper
extracted from the provisioner, with apt, dpkg, modinfo, ubuntu-drivers and
id stood in for, and reads what it ran and what it said."""
import base64
import hashlib
import json
import os
import re
import shutil
import stat
import subprocess
import tempfile
import unittest

HERE = os.path.dirname(os.path.abspath(__file__))
PROVISIONER = os.path.join(HERE, "..", "..", "..", "nodes", "provision-linux.sh")
REAL = ("bash", "sh", "cat", "grep", "awk", "sed", "sort", "tail", "head", "tr", "seq", "sleep",
        "basename", "cut", "uname", "rm", "chmod", "printf", "env", "readlink", "mktemp", "dirname", "ls", "date")


class GpuDriver(unittest.TestCase):
    def setUp(self):
        self.dir = tempfile.mkdtemp()
        self.addCleanup(shutil.rmtree, self.dir, True)
        self.bin = os.path.join(self.dir, "bin")
        os.mkdir(self.bin)
        with open(os.environ.get("BB_TEST_PROVISIONER") or PROVISIONER, encoding="utf-8") as f:
            text = f.read()
        m = re.search(r"^cat > \"\$BBSANDBOX_TMP\" <<'BBSANDBOX'\n(.*?)^BBSANDBOX$", text, re.S | re.M)
        self.helper = os.path.join(self.dir, "bb-sandbox")
        # The display's files under the scratch directory, not the machine's:
        # a node running these tests with a card and the display up has the
        # real ones, root's, and a removal here met them (30 Sep).
        body = m.group(1)
        for var, name in (("GPU_STATE", "gpu-state"), ("GPU_CONF", "gpu.conf"), ("GPU_LOG", "xorg.log")):
            body, k = re.subn(rf"^{var}=.*$", f"{var}={os.path.join(self.dir, name)}", body, flags=re.M)
            self.assertEqual(k, 1, var)
        with open(self.helper, "w", encoding="utf-8") as f:
            f.write(body)
        for t in REAL:
            real = shutil.which(t)
            if real:
                os.symlink(real, os.path.join(self.bin, t))
        self.log = os.path.join(self.dir, "ran")
        self.state = os.path.join(self.dir, "installed")      # "VERSION PACKAGE" once a driver is on
        self.tool("id", 'echo 0')
        self.tool("lspci", 'echo "04:00.0 VGA compatible controller [0300]: NVIDIA Corporation GA104 [GeForce RTX 3070 Ti] [10de:2482]"')
        self.tool("pgrep", "exit 1")
        self.tool("nvidia-smi", "exit 9")
        self.tool("modinfo", f'[ -s "{self.state}" ] && {{ cut -d" " -f1 "{self.state}"; exit 0; }}; exit 1')
        self.tool("dpkg-query", f'''case "$*" in
  *nvidia-driver\\**) [ -s "{self.state}" ] && {{ echo "$(cut -d' ' -f2 "{self.state}") ii "; exit 0; }}; exit 1 ;;
  *) [ -s "{self.state}" ] && echo "$(cut -d' ' -f2 "{self.state}") ii "; echo "libnvidia-gl-610 ii "; echo "firefox ii "; exit 0 ;;
esac''')
        self.tool("apt-get", f'echo "apt-get $*" >> "{self.log}"; case "$*" in *purge*) rm -f "{self.state}" ;; esac; exit 0')
        self.tool("ubuntu-drivers", f'''echo "ubuntu-drivers $*" >> "{self.log}"
case "$2" in nvidia:610) echo "610.57.04 nvidia-driver-610" > "{self.state}" ;; *) echo "595.91.07 nvidia-driver-595-open" > "{self.state}" ;; esac''')

    def tool(self, name, body):
        f = os.path.join(self.bin, name)
        if os.path.lexists(f):
            os.remove(f)             # a link to the real tool, not the tool
        with open(f, "w") as h:
            h.write("#!/bin/sh\n" + body + "\n")
        os.chmod(f, os.stat(f).st_mode | stat.S_IEXEC)

    def run_helper(self, *args, env=None):
        p = subprocess.run([shutil.which("bash"), self.helper, *args], capture_output=True, text=True,
                           timeout=60, check=False, env={"PATH": self.bin, "HOME": self.dir, **(env or {})})
        ran = ""
        if os.path.exists(self.log):
            with open(self.log) as f:
                ran = f.read()
        return p.returncode, p.stdout + p.stderr, ran

    def toolkit(self):
        """Stand-ins for what the container toolkit's verbs touch: NVIDIA's
        package source over curl, docker, nvidia-ctk and systemctl, and
        the helper's two files moved under the scratch directory."""
        self.list = os.path.join(self.dir, "nvidia-container-toolkit.list")
        self.key = os.path.join(self.dir, "nvidia-container-toolkit-keyring.asc")
        self.ctk = os.path.join(self.dir, "toolkit")
        with open(self.helper, encoding="utf-8") as f:
            text = f.read()
        text, n = re.subn(r"^NVCT_LIST=.*$", f"NVCT_LIST={self.list}", text, flags=re.M)
        text, k = re.subn(r"^NVCT_KEY=.*$", f"NVCT_KEY={self.key}", text, flags=re.M)
        self.daemon = os.path.join(self.dir, "daemon.json")
        text, j = re.subn(r"^NVCT_DOCKER=.*$", f"NVCT_DOCKER={self.daemon}", text, flags=re.M)
        self.assertEqual((n, k, j), (1, 1, 1))
        real = shutil.which("python3")
        if real and not os.path.exists(os.path.join(self.bin, "python3")):
            os.symlink(real, os.path.join(self.bin, "python3"))
        with open(self.helper, "w", encoding="utf-8") as f:
            f.write(text)
        # Nothing of the source is fetched: the key is the helper's own, and
        # its one line is written here. A curl that ran would be on the record.
        self.tool("curl", f'echo "curl $*" >> "{self.log}"; exit 22')
        # Docker lists the runtime once it has been told (configured) and has
        # read its configuration again: on a reload, or only on a restart
        # where the test takes self.reloads away.
        self.told = os.path.join(self.dir, "configured")
        self.listed = os.path.join(self.dir, "listed")
        self.reloads = os.path.join(self.dir, "reloads")
        with open(self.reloads, "w") as f:
            f.write("1")
        self.tool("docker", f"""if [ -e "{self.listed}" ]; then echo '{{"nvidia":{{}},"runc":{{}}}}'; else echo '{{"runc":{{}}}}'; fi""")
        self.tool("nvidia-ctk", f"""echo "nvidia-ctk $*" >> "{self.log}"
case "$*" in *--unset*) rm -f "{self.told}" ;; *) echo 1 > "{self.told}" ;; esac""")
        self.tool("systemctl", f"""echo "systemctl $*" >> "{self.log}"
case "$1" in reload) [ -e "{self.reloads}" ] || exit 0 ;; esac
if [ -e "{self.told}" ]; then echo 1 > "{self.listed}"; else rm -f "{self.listed}"; fi""")
        self.tool("apt-get", f'''echo "apt-get $*" >> "{self.log}"
case "$*" in
  *install*nvidia-container-toolkit*) echo on > "{self.ctk}" ;;
  *purge*) rm -f "{self.ctk}" "{self.state}" ;;
esac; exit 0''')
        self.tool("dpkg-query", f'''[ -s "{self.ctk}" ] && {{ echo "nvidia-container-toolkit ii "; echo "libnvidia-container1 ii "; }}
echo "docker-ce ii "; exit 0''')

    def driver_on(self):
        with open(self.state, "w") as f:
            f.write("610.57.04 nvidia-driver-610\n")

    def carried_key(self):
        """NVIDIA's key as the helper carries it (nvct_key)."""
        with open(self.helper, encoding="utf-8") as f:
            return re.search(r"^    cat <<'NVCTKEY'\n(.*?\n)NVCTKEY$", f.read(), re.S | re.M).group(1)

    def test_the_carried_key_is_the_one_its_comment_names(self):
        """The version 4 fingerprint of the key in the script, worked out
        here (the SHA-1 of its public key packet, as RFC 4880 hashes it),
        is the one written beside it, with where it was read and when."""
        key = self.carried_key()
        self.assertTrue(key.startswith("-----BEGIN PGP PUBLIC KEY BLOCK-----\n"))
        raw = base64.b64decode("".join(key.split("\n\n", 1)[1].split("\n=", 1)[0].split()))
        self.assertEqual((raw[0], raw[3]), (0x99, 4))
        n = int.from_bytes(raw[1:3], "big")
        got = hashlib.sha1(b"\x99" + raw[1:3] + raw[3:3 + n]).hexdigest().upper()  # noqa: S324 (a fingerprint is SHA-1 by definition)
        self.assertEqual(got, "C95B321B61E88C1809C4F759DDCAE044F796ECB0")
        with open(self.helper, encoding="utf-8") as f:
            said = f.read()
        said = said[said.index("# nvct_key:"):said.index("nvct_key() {")]
        self.assertIn("C95B 321B 61E8 8C18 09C4  F759 DDCA E044 F796 ECB0", said)
        self.assertIn("https://nvidia.github.io/libnvidia-container/gpgkey", said)
        self.assertIn("20 Nov 2026", said)
        # One key, in the two places that hold NVIDIA's source to it: a
        # provisioned machine's, and the AerieOS image's build.
        image = os.path.join(os.path.dirname(PROVISIONER), "..", "image", "mkosi.sandbox", "etc", "apt", "keyrings", "nvidia-container-toolkit.asc")
        with open(image, encoding="utf-8") as f:
            self.assertEqual(f.read(), key)

    def test_nothing_of_the_source_is_fetched_while_installing(self):
        with open(self.helper, encoding="utf-8") as f:
            text = f.read()
        body = text[text.index("cmd_gpu_container() {"):text.index("# --- features ---")]
        self.assertNotRegex(body, r"\b(?:curl|wget)\b")

    def test_the_toolkit_adds_nvidias_source_installs_and_reloads_docker(self):
        self.toolkit()
        self.driver_on()
        rc, said, ran = self.run_helper("gpu-container", "install")
        self.assertEqual(rc, 0, said)
        with open(self.list) as f:
            src = f.read()
        self.assertEqual(src, f"deb [signed-by={self.key}] https://nvidia.github.io/libnvidia-container/stable/deb/$(ARCH) /\n")
        # The key is the one the helper carries, whole, and nobody was asked for one.
        with open(self.key) as f:
            key = f.read()
        self.assertEqual(key, self.carried_key())
        self.assertNotIn("curl", ran)
        lines = ran.splitlines()
        install = next(i for i, ln in enumerate(lines) if " install " in ln and "nvidia-container-toolkit" in ln)
        self.assertIn("DPkg::Lock::Timeout", lines[install])
        configure = lines.index("nvidia-ctk runtime configure --runtime=docker")
        self.assertLess(install, configure)
        self.assertLess(configure, lines.index("systemctl reload docker"))
        self.assertNotIn("systemctl restart docker", lines)
        self.assertIn("running containers keep running", said)

    def test_a_docker_that_does_not_take_the_runtime_on_a_reload_is_restarted(self):
        self.toolkit()
        self.driver_on()
        os.remove(self.reloads)
        rc, said, ran = self.run_helper("gpu-container", "install")
        self.assertEqual(rc, 0, said)
        lines = ran.splitlines()
        self.assertLess(lines.index("systemctl reload docker"), lines.index("systemctl restart docker"))
        self.assertIn("stays down until it is started again", said)

    def test_the_toolkit_waits_for_the_driver(self):
        self.toolkit()
        rc, said, ran = self.run_helper("gpu-container", "install")
        self.assertNotEqual(rc, 0)
        self.assertIn("driver is not installed", said)
        self.assertEqual(ran, "")
        self.assertFalse(os.path.exists(self.list))

    def test_a_source_that_does_not_answer_is_apts_to_say(self):
        """Nothing is fetched to add the source, so nothing that answers in
        NVIDIA's place can hand over a key or a list: a source that does not
        answer, or answers with what the carried key did not sign, is met
        by apt, and the install ends on what apt said."""
        self.toolkit()
        self.driver_on()
        self.tool("curl", f'echo "curl $*" >> "{self.log}"; echo "<html>moved</html>"')
        self.tool("apt-get", f'''echo "apt-get $*" >> "{self.log}"
case "$*" in *install*) echo "E: Unable to locate package nvidia-container-toolkit" >&2; exit 100 ;; esac; exit 0''')
        rc, said, ran = self.run_helper("gpu-container", "install")
        self.assertNotEqual(rc, 0)
        self.assertIn("E: Unable to locate package nvidia-container-toolkit", said)
        self.assertIn("apt could not install it", said)
        self.assertNotIn("curl", ran)
        self.assertNotIn("nvidia-ctk", ran)
        with open(self.key) as f:
            self.assertEqual(f.read(), self.carried_key(), "the key on the machine is the carried one whatever answered")

    def test_removing_the_toolkit_takes_its_source_with_it(self):
        self.toolkit()
        for f in (self.list, self.key, self.ctk):
            with open(f, "w") as h:
                h.write("x\n")
        rc, said, ran = self.run_helper("gpu-container", "remove")
        self.assertEqual(rc, 0, said)
        purge = [ln for ln in ran.splitlines() if " purge " in ln][0]
        self.assertIn("nvidia-container-toolkit", purge)
        self.assertIn("libnvidia-container1", purge)
        self.assertNotIn("docker-ce", purge)
        self.assertIn("systemctl reload docker", ran)
        self.assertNotIn("systemctl restart docker", ran)
        self.assertFalse(os.path.exists(self.list) or os.path.exists(self.key))

    def removed(self, config):
        self.toolkit()
        with open(self.ctk, "w") as h:
            h.write("x\n")
        if config is not None:
            with open(self.daemon, "w") as h:
                h.write(config if isinstance(config, str) else json.dumps(config))
        rc, said, ran = self.run_helper("gpu-container", "remove")
        self.assertEqual(rc, 0, said)
        try:
            with open(self.daemon) as h:
                return h.read(), said
        except OSError:
            return None, said

    def test_removal_takes_the_runtime_out_of_dockers_configuration_and_nothing_else(self):
        nv = {"args": [], "path": "nvidia-container-runtime"}
        got, _ = self.removed({"labels": ["builderbot.sandbox=1"], "runtimes": {"nvidia": nv}})
        self.assertEqual(json.loads(got), {"labels": ["builderbot.sandbox=1"]})
        got, _ = self.removed({"default-runtime": "nvidia", "runtimes": {"nvidia": nv, "kata": {"path": "kata"}}})
        self.assertEqual(json.loads(got), {"runtimes": {"kata": {"path": "kata"}}})

    def test_a_docker_that_goes_on_listing_the_runtime_is_said(self):
        self.toolkit()
        for f in (self.ctk, self.listed):
            with open(f, "w") as h:
                h.write("x\n")
        self.tool("systemctl", f'echo "systemctl $*" >> "{self.log}"')      # a reload that drops nothing
        rc, said, _ = self.run_helper("gpu-container", "remove")
        self.assertEqual(rc, 0, said)
        self.assertIn("goes on listing the nvidia runtime until it next restarts", said)

    def test_a_configuration_without_the_runtime_is_left_as_it_is(self):
        text = '{"labels":   ["builderbot.sandbox=1"]}\n'
        self.assertEqual(self.removed(text)[0], text)

    def test_a_machine_with_no_docker_configuration_gets_none(self):
        self.assertIsNone(self.removed(None)[0])

    def test_a_configuration_that_does_not_parse_is_said_and_left(self):
        got, said = self.removed("{not json")
        self.assertEqual(got, "{not json")
        self.assertIn("could not take the nvidia runtime out", said)

    def machine(self, *running):
        """A pgrep that answers from a list of command lines, the way the
        real one does for -x (the name, fifteen characters of it) and -f
        (the whole line, as a pattern); and a sleep that does not."""
        ps = os.path.join(self.dir, "ps")
        with open(ps, "w") as f:
            f.write("".join(line + "\n" for line in running))
        self.tool("pgrep", f"""case "$1" in
  -x) while read -r line; do for w in $line; do case "$w" in -*) continue ;; esac
        n="${{w##*/}}"; [ "$(printf '%.15s' "$n")" = "$2" ] && exit 0; done; done < "{ps}"; exit 1 ;;
  -f) grep -Eq -- "$2" "{ps}" ;;
  *) exit 1 ;;
esac""")
        self.tool("sleep", f': > "{ps}"')

    def test_ubuntus_shutdown_helper_is_not_an_upgrade_in_progress(self):
        self.machine("/usr/bin/python3 /usr/share/unattended-upgrades/unattended-upgrade-shutdown --wait-for-signal")
        rc, said, ran = self.run_helper("gpu-driver", "refresh")
        self.assertEqual(rc, 0, said)
        self.assertNotIn("waiting for the machine's own apt", said)
        self.assertIn("update", ran)

    def test_a_real_upgrade_or_an_apt_of_the_machines_own_is_waited_for(self):
        for line in ("/usr/bin/python3 /usr/bin/unattended-upgrade", "apt-get -y install something", "/usr/bin/dpkg --configure -a"):
            self.machine(line)
            rc, said, _ = self.run_helper("gpu-driver", "refresh")
            self.assertEqual(rc, 0, said)
            self.assertIn("waiting for the machine's own apt", said, line)

    def test_a_picked_branch_on_a_machine_with_no_driver(self):
        rc, said, ran = self.run_helper("gpu-driver", "install", "nvidia-driver-610")
        self.assertEqual(rc, 0, said)
        self.assertIn("ubuntu-drivers install nvidia:610", ran)
        self.assertIn("installed the NVIDIA driver 610.57.04", said)
        self.assertIn("takes the card at the next boot", said)

    def test_the_recommended_one_when_none_is_named(self):
        rc, said, ran = self.run_helper("gpu-driver", "install")
        self.assertEqual(rc, 0, said)
        self.assertRegex(ran, r"ubuntu-drivers install\n")
        self.assertIn("installed the NVIDIA driver 595.91.07", said)

    def test_a_name_that_is_not_a_driver_package_is_refused(self):
        rc, said, ran = self.run_helper("gpu-driver", "install", "nvidia-driver-610; reboot")
        self.assertNotEqual(rc, 0)
        self.assertIn("is not a driver package", said)
        self.assertNotIn("ubuntu-drivers", ran)

    def test_another_branch_waits_for_the_installed_one_to_be_removed(self):
        with open(self.state, "w") as f:
            f.write("595.91.07 nvidia-driver-595-open\n")
        rc, said, ran = self.run_helper("gpu-driver", "install", "nvidia-driver-610")
        self.assertNotEqual(rc, 0)
        self.assertIn("remove it first", said)
        self.assertNotIn("ubuntu-drivers", ran)

    def test_an_update_asks_apt_for_the_metapackages_not_every_package(self):
        # bb-sandbox, 8 Oct: --only-upgrade over every NVIDIA package held
        # the running kernel's module at the old version and apt refused.
        with open(self.state, "w") as f:
            f.write("595.91.07 nvidia-driver-595-open\n")
        self.tool("dpkg-query", '''case "$*" in
  *nvidia-driver\\**) echo "nvidia-driver-595-open ii " ;;
  *) for p in nvidia-driver-595-open linux-modules-nvidia-595-open-generic linux-modules-nvidia-595-open-7.0.0-34-generic \\
              libnvidia-gl-595 nvidia-kernel-common-595 firefox; do echo "$p ii "; done ;;
esac''')
        rc, said, ran = self.run_helper("gpu-driver", "install")
        self.assertEqual(rc, 0, said)
        inst = [ln for ln in ran.splitlines() if " install " in ln][0]
        self.assertNotIn("--only-upgrade", inst)
        self.assertEqual(sorted(inst.split()[-2:]), ["linux-modules-nvidia-595-open-generic", "nvidia-driver-595-open"])
        self.assertNotIn("ubuntu-drivers", ran)

    def test_a_driver_built_for_the_newest_kernel_alone_is_the_installed_one(self):
        # 8 Oct: the update's module was on 7.0.0-38 only, the machine on -34.
        mods = os.path.join(self.dir, "modules")
        for k in ("7.0.0-34-generic", "7.0.0-38-generic", "kernel"):
            os.makedirs(os.path.join(mods, k))
        self.tool("uname", 'echo 7.0.0-34-generic')
        self.tool("modinfo", '[ "$1" = -k ] && [ "$2" = 7.0.0-38-generic ] && { echo 595.99.02; exit 0; }; exit 1')
        self.tool("dpkg-query", '''case "$*" in
  *nvidia-driver\\**) echo "nvidia-driver-595-open ii " ;;
  *) echo "nvidia-driver-595-open ii "; echo "linux-modules-nvidia-595-open-generic ii " ;;
esac''')
        rc, said, ran = self.run_helper("gpu-driver", "install", env={"GPU_MODULES": mods})
        self.assertEqual(rc, 0, said)
        self.assertIn("595.99.02 is installed; bringing it up to date", said)
        self.assertNotIn("ubuntu-drivers", ran)

    def test_remove_purges_the_drivers_packages_and_only_those(self):
        with open(self.state, "w") as f:
            f.write("610.57.04 nvidia-driver-610\n")
        rc, said, ran = self.run_helper("gpu-driver", "remove")
        self.assertEqual(rc, 0, said)
        purge = [ln for ln in ran.splitlines() if " purge " in ln][0]
        self.assertIn("nvidia-driver-610", purge)
        self.assertIn("libnvidia-gl-610", purge)
        self.assertNotIn("firefox", purge)
        self.assertIn("DPkg::Lock::Timeout", purge)

    def test_refresh_reads_the_package_lists_again(self):
        rc, said, ran = self.run_helper("gpu-driver", "refresh")
        self.assertEqual(rc, 0, said)
        self.assertIn("update", ran)

    def test_the_display_does_not_install_the_driver(self):
        rc, said, ran = self.run_helper("gpu")
        self.assertNotEqual(rc, 0)
        self.assertIn("from the Library", said)
        self.assertEqual(ran, "")


if __name__ == "__main__":
    unittest.main()
