"""The provisioner's doors (cloudflared, Tailscale) come from a source the
machine's package manager verifies, on every family: the vendor's own
repository held to the vendor's key this repository carries, or the
distribution's own package, and a system with neither is told so. The
download each replaced (a release's binary dropped into /usr/local/bin, an
installer piped to a shell) was held to nothing and ran as root.

Read as text for what must not come back, and run as the bash it is: the
core's door functions with a family's file, against stand-ins for the
package managers, writing under a scratch directory."""
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
REAL = ("bash", "sh", "cat", "grep", "seq", "sleep", "install", "chmod", "mkdir", "tr", "cut", "rm", "env")
# The keys' fingerprints as each vendor's own instructions state them
# (door_key's comment says where each was read, and when).
FINGERPRINTS = {"cloudflared": "CC94B39C77AE7342A68B89628A682D308D4E5E73",
                "tailscale": "2596A99EAAB33821893C0A79458CA832957F5868"}
REFUSAL = "install {0} yourself and run this script again, which leaves an installed door as it is"


def core():
    with open(CORE, encoding="utf-8") as f:
        return f.read()


def family(name):
    with open(os.path.join(NODES, "families", name + ".sh"), encoding="utf-8") as f:
        return f.read()


def door_functions():
    """The core's door functions: its text from door_secret to the first door."""
    src = core()
    a = src.index("door_secret() {")
    return src[a:src.index('if [ "$DOOR" = cloudflared ]; then', a)]


def carried_key(name):
    """The armored key door_key carries under `name`, as the script's text has it."""
    m = re.search(rf"^        {name}\) cat <<'DOORKEY'\n(.*?)\nDOORKEY$", core(), re.S | re.M)
    return m.group(1) + "\n"


def fingerprint(armored):
    """An armored OpenPGP key's version 4 fingerprint: the SHA-1 of its
    first packet, the public key, as RFC 4880 hashes it."""
    body = armored.split("\n\n", 1)[1].split("\n=", 1)[0]
    raw = base64.b64decode("".join(body.split()))
    assert raw[0] == 0x99 and raw[3] == 4, "an old-format version 4 public key packet"
    n = int.from_bytes(raw[1:3], "big")
    return hashlib.sha1(b"\x99" + raw[1:3] + raw[3:3 + n]).hexdigest().upper()  # noqa: S324 (the fingerprint is SHA-1 by definition)


class NothingUnchecked(unittest.TestCase):
    """What must not come back, read out of the scripts."""

    def texts(self):
        return {"provision-linux.sh": core(), **{f + ".sh": family(f) for f in FAMILIES}}

    def test_no_download_is_piped_to_a_shell(self):
        piped = re.compile(r"\b(?:curl|wget)\b[^\n|]*\|\s*(?:sudo\s+)?(?:ba|da|z)?sh\b")
        for name, text in self.texts().items():
            code = "\n".join(ln for ln in text.splitlines() if not ln.lstrip().startswith("#"))
            self.assertEqual(piped.findall(code), [], name)

    def test_no_download_lands_in_usr_local_bin(self):
        for name, text in self.texts().items():
            for ln in text.splitlines():
                if ln.lstrip().startswith("#"):
                    continue
                if re.search(r"\b(?:curl|wget)\b", ln):
                    self.assertNotRegex(ln, r"/usr/local/s?bin", f"{name}: {ln.strip()[:120]}")

    def test_no_door_asks_for_whatever_is_latest(self):
        doors = core()
        doors = doors[doors.index("# --- a door in for SSH"):doors.index('say "docker"')]
        for gone in ("releases/latest", "install.sh", "cloudflared.new"):
            self.assertNotIn(gone, doors)
        # ...and the only program a door's block fetches is fetched by door_fetch.
        self.assertEqual(re.findall(r"^\s*(?:curl|wget)\b.*$", doors, re.M), [])
        self.assertEqual(len(re.findall(r"^\s+door_fetch (?:cloudflared|tailscale)$", doors, re.M)), 2)

    def test_no_family_fetches_a_key(self):
        """A key comes from door_key and from nowhere else: no family's door
        function asks the network for one."""
        for f in FAMILIES:
            text = family(f)
            body = text[text.index("door_install() {"):]
            self.assertNotRegex(body, r"gpgkey=https|--gpg-auto-import-keys|recv-keys|\|\s*gpg\b|rpm --import https", f)
            for ln in body.splitlines():
                if re.search(r"\b(?:curl|wget)\b", ln):
                    self.assertIn("/dists/", ln, f"{f}: a door's function reaches the network only to ask which suite exists")

    def test_self_update_stays_off_and_the_comment_says_who_updates_it(self):
        src = core()
        self.assertIn("--no-autoupdate tunnel run", src)
        self.assertNotIn("the one copy left behind", src)
        self.assertIn("Installed by the package manager, which is what moves it from here on", src)


class CarriedKeys(unittest.TestCase):
    def test_each_key_is_the_one_its_comment_names(self):
        said = core()
        said = said[said.index("# door_key NAME:"):said.index("door_key() {")]
        for name, want in FINGERPRINTS.items():
            key = carried_key(name)
            self.assertTrue(key.startswith("-----BEGIN PGP PUBLIC KEY BLOCK-----\n"), name)
            self.assertTrue(key.rstrip("\n").endswith("-----END PGP PUBLIC KEY BLOCK-----"), name)
            self.assertEqual(fingerprint(key), want, name)
            spaced = " ".join(want[i:i + 4] for i in range(0, 40, 4))
            self.assertIn(spaced[:24] + " " + spaced[24:], said, f"{name}: the comment states the fingerprint")
        self.assertIn("20 Nov 2026", said)
        self.assertIn("https://pkg.cloudflare.com/", said)
        self.assertIn("https://pkgs.tailscale.com/", said)

    @unittest.skipUnless(shutil.which("gpg"), "no gpg here")
    def test_gpg_reads_each_as_one_key_with_that_fingerprint(self):
        for name, want in FINGERPRINTS.items():
            with tempfile.TemporaryDirectory() as d:
                p = subprocess.run(["gpg", "--batch", "--show-keys", "--with-colons"], input=carried_key(name), capture_output=True,
                                   text=True, timeout=60, check=False, env={**os.environ, "GNUPGHOME": d})
            fprs = [ln.split(":")[9] for ln in p.stdout.splitlines() if ln.startswith("fpr:")]
            self.assertEqual(fprs[:1], [want], p.stderr)
            self.assertEqual(sum(ln.startswith("pub:") for ln in p.stdout.splitlines()), 1, name)


class Doors(unittest.TestCase):
    """door_fetch run for a family against stand-ins for its tools."""

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
        # Every tool a family could reach for, each writing what it was asked.
        for t in ("apt-get", "dnf", "rpm", "zypper", "pacman", "apk", "xbps-install", "emerge", "curl", "wget", "gpg", "systemctl"):
            self.tool(t)
        self.tool("dpkg", 'echo amd64')
        self.tool("dpkg-query", "exit 1")

    def tool(self, name, body="exit 0"):
        f = os.path.join(self.bin, name)
        with open(f, "w", encoding="utf-8") as h:
            h.write(f'#!/bin/sh\necho "{name} $*" >> "{self.log}"\n{body}\n')
        os.chmod(f, os.stat(f).st_mode | stat.S_IEXEC)

    def fetch(self, fam, door, os_release, image=False):
        """(exit code, what it said, the lines its tools were run with)."""
        text = family(fam)
        for var, path in (("DOOR_KEYS", self.keys), ("DOOR_SOURCES", self.sources)):
            text, n = re.subn(rf"^{var}=.*$", f"{var}={path}", text, flags=re.M)
            self.assertEqual(n, 1 if fam in ("deb", "rhel", "suse") else 0, f"{fam} {var}")
        pre = "".join(f'{k}="{v}"\n' for k, v in {"ID": "", "ID_LIKE": "", "VERSION_ID": "", "VERSION_CODENAME": "",
                                                    "UBUNTU_CODENAME": "", "INIT": "systemd", **os_release}.items())
        script = os.path.join(self.dir, "run.sh")
        with open(script, "w", encoding="utf-8") as f:
            f.write("#!/usr/bin/env bash\nset -euo pipefail\n" + pre
                    + 'warn() { printf \'\\n!! %s\\n\' "$*" >&2; }\n'
                    + f'svc_enable() {{ echo "svc_enable $*" >> "{self.log}"; }}\n'
                    + door_functions() + text + f'\ndoor_fetch {door}\necho fetched\n')
        release = os.path.join(self.dir, "os-image-release")
        if image:
            with open(release, "w", encoding="utf-8") as f:
                f.write("AerieOS\n")
        p = subprocess.run([shutil.which("bash"), script], capture_output=True, text=True, timeout=60, check=False,
                           env={"PATH": self.bin, "HOME": self.dir, "BB_OS_RELEASE": release})
        ran = []
        if os.path.exists(self.log):
            with open(self.log, encoding="utf-8") as f:
                ran = f.read().splitlines()
            os.remove(self.log)
        return p.returncode, p.stdout + p.stderr, ran

    def read(self, *parts):
        with open(os.path.join(self.dir, *parts), encoding="utf-8") as f:
            return f.read()

    def assert_fetched_no_key(self, ran):
        """Nothing a door's install ran asked the network for a key or a script."""
        for ln in ran:
            if ln.startswith(("curl ", "wget ")):
                self.assertRegex(ln, r"/dists/[a-z]+/InRelease$", ln)
            self.assertNotRegex(ln, r"^gpg |auto-import|recv-keys|\.gpg\b", ln)

    # -- Debian and Ubuntu ------------------------------------------------------
    def test_deb_cloudflared_is_the_vendors_repository_held_to_the_carried_key(self):
        code, out, ran = self.fetch("deb", "cloudflared", {"ID": "ubuntu", "ID_LIKE": "debian", "VERSION_CODENAME": "noble", "UBUNTU_CODENAME": "noble"})
        self.assertEqual(code, 0, out)
        self.assertEqual(self.read("keys", "cloudflared.asc"), carried_key("cloudflared"))
        self.assertEqual(self.read("sources", "cloudflared.list"),
                         f"deb [arch=amd64 signed-by={self.keys}/cloudflared.asc] https://pkg.cloudflare.com/cloudflared any main\n")
        update = next(i for i, ln in enumerate(ran) if ln.startswith("apt-get update"))
        install = next(i for i, ln in enumerate(ran) if ln.startswith("apt-get") and " install " in ln)
        self.assertLess(update, install)
        self.assertTrue(ran[install].endswith(" cloudflared"), ran[install])
        self.assertFalse([ln for ln in ran if ln.startswith(("curl", "svc_enable"))], ran)
        self.assert_fetched_no_key(ran)

    def test_deb_tailscale_names_the_distribution_and_the_release(self):
        for os_release, dist, suite in (
                ({"ID": "ubuntu", "ID_LIKE": "debian", "VERSION_CODENAME": "noble", "UBUNTU_CODENAME": "noble"}, "ubuntu", "noble"),
                ({"ID": "linuxmint", "ID_LIKE": "ubuntu debian", "VERSION_CODENAME": "wilma", "UBUNTU_CODENAME": "noble"}, "ubuntu", "noble"),
                ({"ID": "debian", "VERSION_CODENAME": "trixie"}, "debian", "trixie"),
                ({"ID": "raspbian", "ID_LIKE": "debian", "VERSION_CODENAME": "bookworm"}, "raspbian", "bookworm")):
            code, out, ran = self.fetch("deb", "tailscale", os_release)
            self.assertEqual(code, 0, out)
            self.assertEqual(self.read("keys", "tailscale.asc"), carried_key("tailscale"))
            self.assertEqual(self.read("sources", "tailscale.list"),
                             f"deb [arch=amd64 signed-by={self.keys}/tailscale.asc] https://pkgs.tailscale.com/stable/{dist} {suite} main\n")
            self.assertIn(f"curl -fs -o /dev/null --max-time 15 https://pkgs.tailscale.com/stable/{dist}/dists/{suite}/InRelease", ran)
            self.assertTrue([ln for ln in ran if ln.startswith("apt-get") and ln.endswith(" install -y -qq tailscale")], ran)
            self.assertEqual(ran[-1], "svc_enable tailscaled")
            self.assert_fetched_no_key(ran)

    def test_deb_tailscale_falls_back_to_a_suite_the_repository_has(self):
        self.tool("curl", 'case "$*" in *"/dists/trixie/"*) exit 0 ;; *) exit 22 ;; esac')
        code, out, ran = self.fetch("deb", "tailscale", {"ID": "kali", "ID_LIKE": "debian", "VERSION_CODENAME": "kali-rolling"})
        self.assertEqual(code, 0, out)
        self.assertIn("https://pkgs.tailscale.com/stable/debian trixie main", self.read("sources", "tailscale.list"))
        self.assertEqual([ln.rsplit("/dists/", 1)[1] for ln in ran if ln.startswith("curl")], ["kali-rolling/InRelease", "trixie/InRelease"])

    def test_deb_with_no_suite_answering_says_so_and_installs_nothing(self):
        self.tool("curl", "exit 22")
        code, out, ran = self.fetch("deb", "tailscale", {"ID": "debian", "VERSION_CODENAME": "trixie"})
        self.assertEqual(code, 1)
        self.assertIn("answers for none of the suites tried (trixie, trixie bookworm)", out)
        self.assertIn("!! tailscale did not install from the package source this system verifies it by", out)
        self.assertFalse([ln for ln in ran if ln.startswith("apt-get")], ran)
        self.assertFalse(os.path.exists(os.path.join(self.sources, "tailscale.list")))

    def test_an_aerieos_disk_is_refused_with_what_a_person_can_do(self):
        code, out, ran = self.fetch("deb", "cloudflared", {"ID": "debian", "VERSION_CODENAME": "trixie"}, image=True)
        self.assertEqual(code, 1)
        self.assertIn("!! this system has no verified source for cloudflared (an AerieOS disk's packages are its image's, which carries no "
                      "cloudflared): " + REFUSAL.format("cloudflared"), out)
        self.assertEqual(ran, [])
        self.assertFalse(os.path.exists(self.keys))

    def test_a_package_manager_that_fails_ends_the_run(self):
        self.tool("apt-get", 'case "$*" in *install*) echo "E: Unable to locate package cloudflared" >&2; exit 100 ;; esac; exit 0')
        code, out, _ran = self.fetch("deb", "cloudflared", {"ID": "debian", "VERSION_CODENAME": "trixie"})
        self.assertEqual(code, 1)
        self.assertIn("E: Unable to locate package cloudflared", out)
        self.assertIn("!! cloudflared did not install from the package source this system verifies it by; what the package manager said is above", out)
        self.assertNotIn("fetched", out)

    # -- RHEL and its rebuilds, Fedora -------------------------------------------
    def test_rhel_cloudflared_holds_each_package_to_the_carried_key(self):
        code, out, ran = self.fetch("rhel", "cloudflared", {"ID": "rocky", "ID_LIKE": "rhel centos fedora", "VERSION_ID": "9.8"})
        self.assertEqual(code, 0, out)
        self.assertEqual(self.read("keys", "RPM-GPG-KEY-cloudflared"), carried_key("cloudflared"))
        self.assertEqual(self.read("sources", "cloudflared.repo").splitlines(),
                         ["[cloudflared-stable]", "name=cloudflared stable", "baseurl=https://pkg.cloudflare.com/cloudflared/rpm", "enabled=1",
                          "gpgcheck=1", "repo_gpgcheck=0", f"gpgkey=file://{self.keys}/RPM-GPG-KEY-cloudflared"])
        self.assertEqual(ran, ["dnf -y -q install cloudflared"])

    def test_rhel_tailscale_names_the_repository_its_vendor_lays_out(self):
        for os_release, at in (({"ID": "rocky", "ID_LIKE": "rhel centos fedora", "VERSION_ID": "9.8"}, "fedora"),
                               ({"ID": "almalinux", "ID_LIKE": "rhel centos fedora", "VERSION_ID": "10.1"}, "fedora"),
                               ({"ID": "fedora", "VERSION_ID": "44"}, "fedora"),
                               ({"ID": "rhel", "ID_LIKE": "fedora", "VERSION_ID": "9.6"}, "rhel/9"),
                               ({"ID": "centos", "ID_LIKE": "rhel fedora", "VERSION_ID": "10"}, "centos/10")):
            code, out, ran = self.fetch("rhel", "tailscale", os_release)
            self.assertEqual(code, 0, out)
            self.assertEqual(self.read("keys", "RPM-GPG-KEY-tailscale"), carried_key("tailscale"))
            repo = self.read("sources", "tailscale.repo").splitlines()
            self.assertIn(f"baseurl=https://pkgs.tailscale.com/stable/{at}/$basearch", repo)
            for line in ("gpgcheck=1", "repo_gpgcheck=1", f"gpgkey=file://{self.keys}/RPM-GPG-KEY-tailscale"):
                self.assertIn(line, repo)
            self.assertEqual(ran, ["dnf -y -q install tailscale", "svc_enable tailscaled"])

    # -- openSUSE and SLES --------------------------------------------------------
    def test_suse_takes_the_distributions_own_package_where_it_carries_one(self):
        code, out, ran = self.fetch("suse", "cloudflared", {"ID": "opensuse-tumbleweed", "ID_LIKE": "opensuse suse", "VERSION_ID": "20261118"})
        self.assertEqual(code, 0, out)
        self.assertEqual(ran, ["zypper -n -q search --match-exact cloudflared", "zypper -n -q install -y cloudflared"])
        self.assertEqual(os.listdir(self.sources), [])

    def test_suse_takes_the_vendors_repository_where_the_distribution_has_none(self):
        self.tool("zypper", 'case "$*" in *search*) exit 104 ;; esac; exit 0')
        for door, os_release, base, index in (
                ("tailscale", {"ID": "opensuse-leap", "ID_LIKE": "suse opensuse", "VERSION_ID": "15.6"},
                 "https://pkgs.tailscale.com/stable/opensuse/leap/15.6/$basearch", "1"),
                ("tailscale", {"ID": "opensuse-tumbleweed", "ID_LIKE": "opensuse suse", "VERSION_ID": "20261118"},
                 "https://pkgs.tailscale.com/stable/opensuse/tumbleweed/$basearch", "1"),
                ("cloudflared", {"ID": "sles", "ID_LIKE": "suse", "VERSION_ID": "15.6"}, "https://pkg.cloudflare.com/cloudflared/rpm", "0")):
            code, out, ran = self.fetch("suse", door, os_release)
            self.assertEqual(code, 0, out)
            self.assertEqual(self.read("keys", f"RPM-GPG-KEY-{door}"), carried_key(door))
            repo = self.read("sources", f"{door}.repo").splitlines()
            for line in (f"[{door}-stable]", f"baseurl={base}", "gpgcheck=1", f"repo_gpgcheck={index}", "pkg_gpgcheck=1",
                         f"gpgkey=file://{self.keys}/RPM-GPG-KEY-{door}"):
                self.assertIn(line, repo)
            self.assertEqual(ran[:4], [f"zypper -n -q search --match-exact {door}", f"rpm --import {self.keys}/RPM-GPG-KEY-{door}",
                                       f"zypper -n -q refresh {door}-stable", f"zypper -n -q install -y {door}"])
            self.assert_fetched_no_key(ran)

    # -- the families whose own repositories carry a door --------------------------
    def test_the_distributions_own_package_is_asked_for_by_its_manager(self):
        for fam, os_release, door, want in (
                ("arch", {"ID": "arch"}, "cloudflared", ["pacman -S --noconfirm --needed --quiet cloudflared"]),
                ("arch", {"ID": "arch"}, "tailscale", ["pacman -S --noconfirm --needed --quiet tailscale", "svc_enable tailscaled"]),
                ("void", {"ID": "void", "INIT": "runit"}, "cloudflared", ["xbps-install -y cloudflared"]),
                ("void", {"ID": "void", "INIT": "runit"}, "tailscale", ["xbps-install -y tailscale", "svc_enable tailscaled"]),
                ("alpine", {"ID": "alpine", "INIT": "openrc"}, "tailscale", ["apk add -q tailscale", "svc_enable tailscale"]),
                ("gentoo", {"ID": "gentoo", "INIT": "openrc"}, "cloudflared", ["emerge --quiet --noreplace --getbinpkg net-vpn/cloudflared"]),
                ("gentoo", {"ID": "gentoo", "INIT": "openrc"}, "tailscale",
                 ["emerge --quiet --noreplace --getbinpkg net-vpn/tailscale", "svc_enable tailscale"]),
                ("gentoo", {"ID": "gentoo", "INIT": "systemd"}, "tailscale",
                 ["emerge --quiet --noreplace --getbinpkg net-vpn/tailscale", "svc_enable tailscaled"])):
            code, out, ran = self.fetch(fam, door, os_release)
            self.assertEqual((code, ran), (0, want), f"{fam} {door}: {out}")
            self.assertFalse(os.path.exists(self.keys), f"{fam} {door}: a distribution's package needs no vendor's key")

    def test_alpine_has_no_verified_source_for_cloudflared_and_says_so(self):
        code, out, ran = self.fetch("alpine", "cloudflared", {"ID": "alpine", "INIT": "openrc"})
        self.assertEqual(code, 1)
        self.assertEqual(ran, [])
        self.assertIn("!! this system has no verified source for cloudflared (no repository of an Alpine release carries it, and Cloudflare "
                      "publishes no package for apk): " + REFUSAL.format("cloudflared"), out)
        self.assertEqual(out.count("\n!! "), 1, "one sentence")

    def test_every_family_answers_for_both_doors(self):
        """Each family's file has the function, and a door it does not know
        is a refusal, never a download."""
        for fam in FAMILIES:
            self.assertRegex(family(fam), r"(?m)^door_install\(\) \{$", fam)
            code, out, ran = self.fetch(fam, "sshuttle", {"ID": fam})
            self.assertEqual(code, 1, fam)
            self.assertIn("this system has no verified source for sshuttle: " + REFUSAL.format("sshuttle"), out)
            self.assertEqual(ran, [], fam)
            self.assertFalse(os.path.exists(self.keys), fam)


if __name__ == "__main__":
    unittest.main()
