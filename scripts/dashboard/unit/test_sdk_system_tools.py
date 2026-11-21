"""A download is checked with the system's own tools, whatever the PATH.

A pack's bin folder is ahead of the system's on every job's PATH, so a pack
that shipped a sha256sum, a gpgv or a curl would have checked every install
after it. An installed copy of the installer (an image's, a node's bundle)
finds the tools it fetches, checks, unpacks and cuts the network with in
the system's own folders alone. Only the source tree's copy, which is where
the tests run it, reads the caller's PATH: it is told apart by where the
file is (the tree's Dockerfile and unit tests beside it), which nothing in
an environment says.

The same rule holds what a test stands in for a check with: the file the
"is the network really cut" check reads, the helper that cuts it, another
catalog, a download from a file on disk, a script in place of an agent's
recipe. Each is a variable a test sets, and each is read only by the
source tree's copy. An installed copy reads none of them, whoever set
them, and is handed the one row held-run.sh runs as words, not as a
variable."""
import json
import hashlib
import os
import shutil
import subprocess
import sys
import tempfile
import unittest

HERE = os.path.dirname(os.path.abspath(__file__))
REPO = os.path.normpath(os.path.join(HERE, "..", "..", ".."))
LIB = os.path.join(REPO, "scripts", "lib")


class Installed(unittest.TestCase):
    def setUp(self):
        self.d = tempfile.mkdtemp()
        self.addCleanup(shutil.rmtree, self.d, True)
        # The installer as an install holds it: the library and the catalog,
        # and no source tree around them.
        self.lib = os.path.join(self.d, "opt", "scripts", "lib")
        shutil.copytree(LIB, self.lib, ignore=shutil.ignore_patterns("__pycache__"))
        os.makedirs(os.path.join(self.d, "opt", "config"))
        shutil.copy(os.path.join(REPO, "config", "toolchains.json"), os.path.join(self.d, "opt", "config"))
        # A pack's bin folder, ahead of the system's: every tool a check
        # uses, each saying yes.
        self.bin = os.path.join(self.d, "pack", "bin")
        os.makedirs(self.bin)
        self.want = "a" * 64
        for name, body in (("sha256sum", f'echo "{self.want}  $1"'), ("sha1sum", f'echo "{self.want}  $1"'),
                           ("gpgv", 'echo \'gpgv: Good signature from "Anyone"\' >&2; exit 0'), ("curl", "exit 0"),
                           ("tar", "exit 0"), ("unshare", 'shift $(($# - 1)); exec "$@"'), ("sudo", "exit 0"),
                           ("python3", "echo planted"), ("gpg", "exit 0")):
            path = os.path.join(self.bin, name)
            with open(path, "w") as f:
                f.write(f"#!/bin/sh\n{body}\n")
            os.chmod(path, 0o755)
        self.file = os.path.join(self.d, "download")
        with open(self.file, "w") as f:
            f.write("the bytes that came\n")

    def sh(self, lib, script):
        p = subprocess.run(["bash", "-c", f'set -euo pipefail\n. "{lib}/common.sh"\n. "{lib}/sdk.sh"\n' + script],
                           capture_output=True, text=True, check=False, timeout=60,
                           env={"PATH": f"{self.bin}:/usr/bin:/bin", "HOME": self.d, "TMPDIR": self.d})
        return p.returncode, p.stdout, p.stderr

    def test_an_install_s_copy_finds_its_tools_on_the_system_s_own_path(self):
        rc, out, err = self.sh(self.lib, 'echo "tree=[$SDK_IN_TREE]"; for t in sha256sum curl tar python3; do sdk_sys_path "$t"; done')
        self.assertEqual(rc, 0, err)
        lines = out.split()
        self.assertEqual(lines[0], "tree=[]")
        for where in lines[1:]:
            self.assertFalse(where.startswith(self.bin), where)
            self.assertIn(os.path.dirname(where), ("/usr/sbin", "/usr/bin", "/sbin", "/bin"))

    def test_a_pack_s_sha256sum_does_not_check_an_install(self):
        script = (f"sdk_meta() {{ printf 'sha256\\t{self.want}\\tits publisher\\n'; }}\n"
                  f'sdk_verify_download thing "{self.file}" https://x.example/thing.tar.gz 1 "{self.d}"\n')
        rc, out, err = self.sh(self.lib, script)
        self.assertNotEqual(rc, 0, "the pack's sha256sum said yes, and the system's said what the file is")
        self.assertIn(hashlib.sha256(b"the bytes that came\n").hexdigest(), out + err)
        self.assertFalse(os.path.exists(self.file), "the download is removed")
        self.assertFalse(os.path.exists(os.path.join(self.d, ".bb-verified")))

    def test_the_source_tree_s_copy_reads_the_caller_s_path(self):
        rc, out, err = self.sh(LIB, 'echo "tree=[$SDK_IN_TREE]"; sdk_sys_path sha256sum')
        self.assertEqual((rc, out.split()), (0, ["tree=[1]", os.path.join(self.bin, "sha256sum")]), err)

    def test_the_cut_is_made_with_the_system_s_unshare(self):
        rc, out, err = self.sh(self.lib, f'sdk_net_cut thing "{self.d}"; printf "%s\\n" "${{SDK_CUT[@]:-none}}"')
        self.assertEqual(rc, 0, err)
        self.assertNotIn(self.bin, out, "the pack's unshare is not what a step runs behind")

    def test_sdkmeta_finds_gpgv_the_same_way(self):
        for lib, tree in ((self.lib, False), (LIB, True)):
            p = subprocess.run([sys.executable, "-c", "import sdkmeta; print(sdkmeta.IN_TREE, sdkmeta.sys_tool('gpgv'))"],
                               capture_output=True, text=True, check=False, cwd=lib,
                               env={"PATH": f"{self.bin}:/usr/bin:/bin", "PYTHONPATH": lib, "SDK_SYS_PATH": self.bin})
            said, where = p.stdout.split()
            self.assertEqual(said, str(tree), p.stderr)
            self.assertEqual(where.startswith(self.bin), tree, where)


class Seams(Installed):
    ENV = {"BUILDERBOT_NET_DEV": "/tmp/planted-net-dev", "BUILDERBOT_NETCUT_BIN": "/tmp/planted-netcut",
           "BB_TOOLCHAINS_JSON": "/tmp/planted-catalog.json", "BB_TOOLPACKS_FILE_URLS": "1", "BB_SEAMS": "1"}

    def sh(self, lib, script):
        p = subprocess.run(["bash", "-c", f'set -euo pipefail\n. "{lib}/common.sh"\n. "{lib}/sdk.sh"\n' + script],
                           capture_output=True, text=True, check=False, timeout=60,
                           env={"PATH": "/usr/bin:/bin", "HOME": self.d, "TMPDIR": self.d, "BB_SCRIPTS": os.path.dirname(lib), **self.ENV})
        return p.returncode, p.stdout, p.stderr

    def test_an_install_s_copy_reads_none_of_them(self):
        rc, out, err = self.sh(self.lib, 'echo "$SDK_NET_DEV $SDK_NETCUT_BIN [$SDK_CATALOG]"')
        self.assertEqual((rc, out.split()), (0, ["/proc/self/net/dev", "/usr/local/sbin/bb-netcut", "[]"]), err)
        rc, out, err = self.sh(self.lib, 'sdk_https_only thing file:///etc/passwd; echo taken')
        self.assertNotEqual(rc, 0)
        self.assertIn("a declared download is fetched over https", err)
        self.assertNotIn("taken", out)
        p = subprocess.run([sys.executable, "-c", "import sdkmeta; print(sdkmeta.CATALOG)"], capture_output=True, text=True, check=False,
                           cwd=self.lib, env={"PATH": "/usr/bin:/bin", "PYTHONPATH": self.lib, **self.ENV})
        self.assertEqual(os.path.realpath(p.stdout.strip()), os.path.realpath(os.path.join(self.d, "opt", "config", "toolchains.json")), p.stderr)

    def test_the_source_tree_s_copy_reads_them(self):
        rc, out, err = self.sh(LIB, 'echo "$SDK_NET_DEV $SDK_NETCUT_BIN"; sdk_https_only thing file:///etc/passwd; echo taken')
        self.assertEqual((rc, out.split()), (0, ["/tmp/planted-net-dev", "/tmp/planted-netcut", "taken"]), err)
        p = subprocess.run([sys.executable, "-c", "import sdkmeta; print(sdkmeta.CATALOG)"], capture_output=True, text=True, check=False,
                           cwd=LIB, env={"PATH": "/usr/bin:/bin", "PYTHONPATH": LIB, **self.ENV})
        self.assertEqual(p.stdout.strip(), "/tmp/planted-catalog.json")

    def test_a_row_reaches_an_install_s_copy_as_words(self):
        """held-run.sh in an installed copy: the row on its standard input
        is the catalog its run reads, whatever BB_TOOLCHAINS_JSON says."""
        row = {"toolchains": [{"name": "kit", "source": {"kind": "command", "offline": True,
                                                          "fetch": [{"url": "https://127.0.0.1:1/kit.tgz", "sha256": "ab" * 32, "to": "dl/kit.tgz"}],
                                                          "steps": [["tar", "-xzf", "{dir}/dl/kit.tgz"]]}}]}
        catalog = os.path.join(self.d, "one-row.json")
        with open(catalog, "w") as f:
            json.dump(row, f)
        rc, out, err = self.sh(self.lib, f'SDK_CATALOG="{catalog}"; sdk_meta field kit source.kind')
        self.assertEqual((rc, out.strip()), (0, "command"), err)
        home = os.path.join(self.d, "home")
        os.makedirs(home)
        p = subprocess.run(["bash", os.path.join(self.lib, "held-run.sh"), "kit", f"home={home}"], input=json.dumps(row), capture_output=True,
                           text=True, check=False, timeout=120, env={"PATH": "/usr/bin:/bin", "HOME": home, **self.ENV})
        said = p.stdout + p.stderr
        self.assertEqual(p.returncode, 65, said)
        self.assertIn("fetching dl/kit.tgz from https://127.0.0.1:1/kit.tgz", said)
        self.assertIn("could not be fetched", said)

    def test_the_agent_reads_its_two_only_in_the_tree(self):
        pkg = os.path.join(REPO, "scripts", "agent")
        away = os.path.join(self.d, "node", "agent")
        shutil.copytree(os.path.join(pkg, "aerieos_agent"), os.path.join(away, "aerieos_agent"), ignore=shutil.ignore_patterns("__pycache__"))
        ask = "from aerieos_agent import base; print(base.IN_TREE, base.NETCUT_BIN, base.installer_stub('codex') or '-')"
        env = {"PATH": "/usr/bin:/bin", "BUILDERBOT_NETCUT_BIN": "/tmp/planted-netcut", "BUILDERBOT_CODEX_INSTALLER": "/tmp/planted.sh", "BB_SEAMS": "1"}
        for where, want in ((away, "False /usr/local/sbin/bb-netcut -"), (pkg, "True /tmp/planted-netcut /tmp/planted.sh")):
            p = subprocess.run([sys.executable, "-c", ask], capture_output=True, text=True, check=False, cwd=where,
                               env=dict(env, PYTHONPATH=where))
            self.assertEqual(p.stdout.strip(), want, p.stderr)


# The layout is Installed's own: its tests are its to run.
for _name in dir(Installed):
    if _name.startswith("test_") and _name not in vars(Seams):
        setattr(Seams, _name, None)


if __name__ == "__main__":
    unittest.main()
