"""Docker's own package source is held to a key the provisioner carries,
on each family that adds it: Debian's and Ubuntu's apt
repository and the RHEL family's rpm one. The key was fetched from Docker at
the moment of every enrollment (its gpg piped into `gpg --dearmor`, and a
docker-ce.repo whose gpgkey line names an address), so it arrived with the
packages it was to check. docker_key carries both keys, as door_key and
nvct_key carry theirs, and the family writes the copy.

Read as text for what must not come back, and run as the bash it is: a
family's docker_install against stand-ins for the package managers, writing
under a scratch directory."""
import base64
import hashlib
import os
import re
import shutil
import stat
import subprocess
import tempfile
import unittest

HERE = os.path.dirname(os.path.abspath(__file__))
NODES = os.path.join(HERE, "..", "..", "..", "nodes")
CORE = os.path.join(NODES, "provision-linux.sh")
FAMILIES = ("alpine", "arch", "deb", "gentoo", "rhel", "suse", "void")
# The families that add Docker's own source; the rest take the distribution's package.
OWN_SOURCE = ("deb", "rhel")
REAL = ("bash", "sh", "cat", "grep", "seq", "sleep", "install", "chmod", "mkdir", "tr", "cut", "rm", "env", "printf")
# The fingerprints as Docker's own install instructions state them
# (docker_key's comment says where each key was read, and when).
FINGERPRINTS = {"deb": "9DC858229FC7DD38854AE2D88D81803C0EBFCD88",
                "rpm": "060A61C51B558A7F742B77AAC52FEB6B621E9F35"}


def core():
    with open(CORE, encoding="utf-8") as f:
        return f.read()


def family(name):
    with open(os.path.join(NODES, "families", name + ".sh"), encoding="utf-8") as f:
        return f.read()


def docker_functions():
    """The core's docker_key and docker_suite: its text from the first's comment to the second's end."""
    src = core()
    a = src.index("# docker_key KIND:")
    b = src.index("\n}\n", src.index("docker_suite() {", a)) + 3
    return src[a:b]


def docker_install(name):
    """A family's docker_install, whole."""
    text = family(name)
    a = text.index("docker_install() {")
    return text[a:text.index("\n}\n", a) + 3]


def carried_key(kind):
    """The armored key docker_key carries under `kind`, as the script's text has it."""
    m = re.search(rf"^        {kind}\) cat <<'DOCKERKEY'\n(.*?)\nDOCKERKEY$", core(), re.S | re.M)
    return m.group(1) + "\n"


def fingerprint(armored):
    """An armored OpenPGP key's version 4 fingerprint: the SHA-1 of its
    first packet, the public key, as RFC 4880 hashes it."""
    body = armored.split("\n\n", 1)[1].split("\n=", 1)[0]
    raw = base64.b64decode("".join(body.split()))
    assert raw[0] == 0x99 and raw[3] == 4, "an old-format version 4 public key packet"
    n = int.from_bytes(raw[1:3], "big")
    return hashlib.sha1(b"\x99" + raw[1:3] + raw[3:3 + n]).hexdigest().upper()  # noqa: S324 (the fingerprint is SHA-1 by definition)


class NoKeyFetched(unittest.TestCase):
    """What must not come back, read out of the scripts."""

    def test_no_familys_docker_install_fetches_a_key(self):
        for f in FAMILIES:
            body = "\n".join(ln for ln in docker_install(f).splitlines() if not ln.lstrip().startswith("#"))
            self.assertNotRegex(body, r"gpg --dearmor|\|\s*gpg\b|/gpg\b|gpgkey=https|rpm --import https|--gpg-auto-import-keys|recv-keys", f)
            self.assertNotIn("docker-ce.repo\" -o", body, f"{f}: a repository file fetched names a key to fetch")
            self.assertEqual(re.findall(r"\b(?:curl|wget)\b.*", body), [], f"{f}: docker_install fetches nothing itself")
            if f in OWN_SOURCE:
                self.assertRegex(body, r"docker_key (deb|rpm) > ", f)
            else:
                self.assertNotIn("download.docker.com", body, f)

    def test_the_core_asks_dockers_address_only_which_suite_exists(self):
        src = "\n".join(ln for ln in core().splitlines() if not ln.lstrip().startswith("#"))
        asked = [ln.strip() for ln in src.splitlines() if "https://download.docker.com" in ln]
        self.assertEqual(len(asked), 2, asked)
        self.assertTrue(any(ln.startswith("if curl -fsI --max-time 10 https://download.docker.com/ ") for ln in asked), "the pre-flight: does it answer")
        self.assertTrue(any(ln.endswith('/dists/${try}/Release"; then') for ln in asked), "docker_suite: which suite")

    def test_the_rpm_repository_names_the_carried_key_and_no_address(self):
        body = docker_install("rhel")
        self.assertIn('"gpgkey=file://${DOCKER_KEYS}/RPM-GPG-KEY-docker"', body)
        self.assertIn('"gpgcheck=1"', body)


class CarriedKeys(unittest.TestCase):
    def test_each_key_is_the_one_its_comment_names(self):
        said = core()
        said = said[said.index("# docker_key KIND:"):said.index("docker_key() {")]
        for kind, want in FINGERPRINTS.items():
            key = carried_key(kind)
            self.assertTrue(key.startswith("-----BEGIN PGP PUBLIC KEY BLOCK-----\n"), kind)
            self.assertTrue(key.rstrip("\n").endswith("-----END PGP PUBLIC KEY BLOCK-----"), kind)
            self.assertEqual(fingerprint(key), want, kind)
            spaced = " ".join(want[i:i + 4] for i in range(0, 40, 4))
            self.assertIn(spaced[:24] + " " + spaced[24:], said, f"{kind}: the comment states the fingerprint")
        self.assertIn("20 Nov 2026", said)
        self.assertIn("https://download.docker.com/linux/ubuntu/gpg", said)
        self.assertIn("https://download.docker.com/linux/centos/gpg", said)
        self.assertNotEqual(carried_key("deb"), carried_key("rpm"))

    @unittest.skipUnless(shutil.which("gpg"), "no gpg here")
    def test_gpg_reads_each_as_one_key_with_that_fingerprint(self):
        for kind, want in FINGERPRINTS.items():
            with tempfile.TemporaryDirectory() as d:
                p = subprocess.run(["gpg", "--batch", "--show-keys", "--with-colons"], input=carried_key(kind), capture_output=True,
                                   text=True, timeout=60, check=False, env={**os.environ, "GNUPGHOME": d})
            fprs = [ln.split(":")[9] for ln in p.stdout.splitlines() if ln.startswith("fpr:")]
            self.assertEqual(fprs[:1], [want], p.stderr)
            self.assertEqual(sum(ln.startswith("pub:") for ln in p.stdout.splitlines()), 1, kind)
            uid = next(ln.split(":")[9] for ln in p.stdout.splitlines() if ln.startswith("uid:"))
            self.assertEqual(uid, f"Docker Release (CE {kind}) <docker@docker.com>")


class Installed(unittest.TestCase):
    """docker_install run for a family against stand-ins for its tools."""

    def setUp(self):
        self.dir = tempfile.mkdtemp()
        self.addCleanup(shutil.rmtree, self.dir, True)
        self.bin = os.path.join(self.dir, "bin")
        self.keys = os.path.join(self.dir, "keys")
        self.sources = os.path.join(self.dir, "sources")
        self.log = os.path.join(self.dir, "ran")
        for d in (self.bin, self.sources):
            os.mkdir(d)
        for t in REAL:
            real = shutil.which(t)
            if real:
                os.symlink(real, os.path.join(self.bin, t))
        for t in ("apt-get", "dnf", "rpm", "curl", "wget", "gpg", "systemctl"):
            self.tool(t)
        self.tool("dpkg", 'echo amd64')

    def tool(self, name, body="exit 0"):
        f = os.path.join(self.bin, name)
        with open(f, "w", encoding="utf-8") as h:
            h.write(f'#!/bin/sh\necho "{name} $*" >> "{self.log}"\n{body}\n')
        os.chmod(f, os.stat(f).st_mode | stat.S_IEXEC)

    def install(self, fam, os_release):
        """(exit code, what it said, the lines its tools were run with)."""
        text = family(fam)
        for var, path in (("DOCKER_KEYS", self.keys), ("DOCKER_SOURCES", self.sources)):
            text, n = re.subn(rf"^{var}=.*$", f"{var}={path}", text, flags=re.M)
            self.assertEqual(n, 1, f"{fam} {var}")
        pre = "".join(f'{k}="{v}"\n' for k, v in {"ID": "", "ID_LIKE": "", "VERSION_ID": "", "VERSION_CODENAME": "",
                                                    "UBUNTU_CODENAME": "", "INIT": "systemd", **os_release}.items())
        script = os.path.join(self.dir, "run.sh")
        with open(script, "w", encoding="utf-8") as f:
            f.write("#!/usr/bin/env bash\nset -euo pipefail\n" + pre + docker_functions() + text + "\ndocker_install\necho installed\n")
        p = subprocess.run([shutil.which("bash"), script], capture_output=True, text=True, timeout=60, check=False,
                           env={"PATH": self.bin, "HOME": self.dir, "BB_OS_RELEASE": os.path.join(self.dir, "no-image")})
        ran = []
        if os.path.exists(self.log):
            with open(self.log, encoding="utf-8") as f:
                ran = f.read().splitlines()
        return p.returncode, p.stdout + p.stderr, ran

    def read(self, *parts):
        with open(os.path.join(self.dir, *parts), encoding="utf-8") as f:
            return f.read()

    def assert_no_key_fetched(self, ran):
        for ln in ran:
            if ln.startswith(("curl ", "wget ")):
                self.assertRegex(ln, r"/dists/[a-z]+/Release$", ln)
            self.assertNotRegex(ln, r"^gpg |^rpm --import|auto-import|recv-keys|/gpg\b|docker-ce\.repo", ln)

    def test_debian_and_ubuntu_are_held_to_the_carried_key(self):
        for os_release, at, suite in (({"ID": "ubuntu", "ID_LIKE": "debian", "VERSION_CODENAME": "noble", "UBUNTU_CODENAME": "noble"}, "ubuntu", "noble"),
                                      ({"ID": "debian", "VERSION_CODENAME": "trixie"}, "debian", "trixie")):
            # A keyring an earlier run fetched, which the new line no longer names.
            os.makedirs(self.keys, exist_ok=True)
            with open(os.path.join(self.keys, "docker.gpg"), "wb") as f:
                f.write(b"fetched at an enrollment before")
            code, out, ran = self.install("deb", os_release)
            self.assertEqual(code, 0, out)
            self.assertEqual(self.read("keys", "docker.asc"), carried_key("deb"))
            self.assertEqual(stat.S_IMODE(os.stat(os.path.join(self.keys, "docker.asc")).st_mode), 0o644)
            self.assertFalse(os.path.exists(os.path.join(self.keys, "docker.gpg")), "the fetched keyring is gone with the line that named it")
            self.assertEqual(self.read("sources", "docker.list"),
                             f"deb [arch=amd64 signed-by={self.keys}/docker.asc] https://download.docker.com/linux/{at} {suite} stable\n")
            update = next(i for i, ln in enumerate(ran) if ln.startswith("apt-get update"))
            install = next(i for i, ln in enumerate(ran) if ln.startswith("apt-get") and " install " in ln)
            self.assertLess(update, install)
            self.assertIn("docker-ce", ran[install])
            self.assert_no_key_fetched(ran)
            os.remove(self.log)

    def test_the_rhel_family_is_held_to_the_carried_key(self):
        for os_release, at in (({"ID": "rocky", "ID_LIKE": "rhel centos fedora", "VERSION_ID": "9.5"}, "centos"),
                               ({"ID": "fedora", "VERSION_ID": "43"}, "fedora"),
                               ({"ID": "rhel", "VERSION_ID": "10.0"}, "rhel")):
            code, out, ran = self.install("rhel", os_release)
            self.assertEqual(code, 0, out)
            self.assertEqual(self.read("keys", "RPM-GPG-KEY-docker"), carried_key("rpm"))
            self.assertEqual(self.read("sources", "docker-ce.repo").splitlines(),
                             ["[docker-ce-stable]", "name=Docker CE Stable - $basearch",
                              f"baseurl=https://download.docker.com/linux/{at}/$releasever/$basearch/stable",
                              "enabled=1", "gpgcheck=1", f"gpgkey=file://{self.keys}/RPM-GPG-KEY-docker"])
            self.assertTrue(any(ln.startswith("dnf") and " install " in ln and "docker-ce" in ln for ln in ran), ran)
            self.assert_no_key_fetched(ran)
            self.assertFalse([ln for ln in ran if ln.startswith(("curl", "wget"))], "nothing is fetched to set the source up")
            os.remove(self.log)

    def test_a_key_that_cannot_be_written_ends_the_run_before_anything_is_installed(self):
        with open(self.keys, "w") as f:           # a file where the keys' directory would be
            f.write("")
        for fam, os_release in (("deb", {"ID": "debian", "VERSION_CODENAME": "trixie"}), ("rhel", {"ID": "rocky", "VERSION_ID": "9.5"})):
            code, out, ran = self.install(fam, os_release)
            self.assertNotEqual(code, 0, out)
            self.assertNotIn("installed", out)
            self.assertFalse([ln for ln in ran if " install " in ln and "docker" in ln], ran)
            if os.path.exists(self.log):
                os.remove(self.log)


if __name__ == "__main__":
    unittest.main()
