"""A download is checked with the system's own tools, whatever the PATH.

A pack's bin folder is ahead of the system's on every job's PATH, so a pack
that shipped a sha256sum, a gpgv or a curl would have checked every install
after it. An installed copy of the installer (an image's, a node's bundle)
finds the tools it fetches, checks, unpacks and cuts the network with in
the system's own folders alone. Only the source tree's copy, which is where
the tests run it, reads the caller's PATH: it is told apart by where the
file is (the tree's Dockerfile and unit tests beside it), which nothing in
an environment says."""
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
        rc, _out, err = self.sh(self.lib, script)
        self.assertNotEqual(rc, 0, "the pack's sha256sum said yes, and the system's said what the file is")
        self.assertIn(hashlib.sha256(b"the bytes that came\n").hexdigest(), err)
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


if __name__ == "__main__":
    unittest.main()
