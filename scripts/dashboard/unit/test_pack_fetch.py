"""Declared downloads (R234, pack format 3; the operator, 13 Nov: what a
pack's install takes from somewhere else had no paper trail, and after the
receipt, a way to stop what is not declared). A manifest lists each download
with its address, its sha256 and the file it is kept as; the recipe a node
is handed carries them; the node fetches each, holds it to its sha256, and
runs the install steps with no network where it can cut it, saying which."""
import hashlib
import json
import os
import shutil
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))
import packformat  # noqa: E402
import toolpacks  # noqa: E402

LIB = os.path.join(os.path.dirname(__file__), "..", "..", "lib")
KEPT = Path(__file__).parent / "packformat" / "3" / "hexkit.json"
H = "ab" * 32


def manifest(**install):
    m = json.loads(KEPT.read_text())
    m["install"].update(install)
    return m


class Manifest(unittest.TestCase):
    def test_a_declared_download_is_kept_as_said(self):
        got, errors = toolpacks.validate(manifest())
        self.assertEqual(errors, [])
        self.assertEqual(got["fetch"], [{"url": "https://github.com/hexkit/hexkit/releases/download/v1.4.2/hexkit-linux.tar.gz",
                                         "sha256": "9f86d081884c7d659a2feaa0c55ad015a3bf4f1b2b0b822cd15d6c15b0f00a08", "to": "dl/hexkit-linux.tar.gz"}])
        # The host it fetches from is one of its touches, said or not.
        self.assertEqual(got["touches"]["hosts"], ["github.com"])
        # A pack that declares none says none, and is what it was.
        m = manifest()
        del m["install"]["fetch"]
        m["format"], m["framework"] = 2, "2.1"
        got, errors = toolpacks.validate(m)
        self.assertEqual((errors, got["fetch"]), ([], []))

    def test_it_is_pack_format_3(self):
        self.assertGreaterEqual(packformat.FORMAT, 3)
        m = manifest()
        m["format"], m["framework"] = 2, "2.1"
        _, errors = toolpacks.validate(m)
        self.assertEqual(errors, ['install.fetch (declared downloads) is pack format 3\'s: the manifest says "format": 3'])

    def test_each_is_an_https_address_a_sha256_and_a_file_inside_the_pack(self):
        good = {"url": "https://example.com/a.tgz", "sha256": H, "to": "dl/a.tgz"}
        for bad in ({**good, "url": "http://example.com/a.tgz"}, {**good, "url": "file:///etc/passwd"}, {**good, "url": "https://exa mple.com/a"},
                    {**good, "sha256": "abc"}, {**good, "sha256": H.upper()}, {**good, "to": "../a.tgz"}, {**good, "to": "/tmp/a.tgz"},
                    {**good, "to": "bbtool.json"}, {**good, "run": "rm -rf /"}, "https://example.com/a.tgz"):
            _, errors = toolpacks.validate(manifest(fetch=[bad]))
            self.assertTrue(any(e.startswith("install.fetch 1 is {url, sha256, to}") for e in errors), (bad, errors))
        # Two kept as one file: the second is refused.
        _, errors = toolpacks.validate(manifest(fetch=[good, {**good, "url": "https://example.com/b.tgz"}]))
        self.assertTrue(any(e.startswith("install.fetch 2 is") for e in errors), errors)
        _, errors = toolpacks.validate(manifest(fetch=[dict(good, to=f"dl/{i}") for i in range(toolpacks.FETCH_MAX + 1)]))
        self.assertTrue(any(e.startswith(f"install.fetch lists up to {toolpacks.FETCH_MAX}") for e in errors), errors)
        _, errors = toolpacks.validate(manifest(fetch="https://example.com/a.tgz"))
        self.assertTrue(any(e.startswith("install.fetch lists up to") for e in errors), errors)

    def test_the_recipe_a_node_is_handed(self):
        got, _ = toolpacks.validate(manifest())
        row = toolpacks.recipe({"manifest": got, "url": "https://example.com/hexkit", "commit": "c" * 40})
        self.assertEqual(row["source"]["fetch"], got["fetch"])
        self.assertIs(row["source"]["offline"], True)
        m = manifest()
        del m["install"]["fetch"]
        m["format"], m["framework"] = 2, "2.1"
        got, _ = toolpacks.validate(m)
        src = toolpacks.recipe({"manifest": got, "url": "https://example.com/hexkit", "commit": "c" * 40})["source"]
        self.assertTrue("fetch" not in src and "offline" not in src)
        # A pack kept before declared downloads has no such key at all.
        got.pop("fetch")
        self.assertNotIn("fetch", toolpacks.recipe({"manifest": got, "url": "https://example.com/hexkit", "commit": "c" * 40})["source"])


class Node(unittest.TestCase):
    """sdk.sh's half, its catalog answered by a stand-in for sdk_meta."""

    def setUp(self):
        self.root = tempfile.mkdtemp()
        self.addCleanup(shutil.rmtree, self.root, True)
        self.d = os.path.join(self.root, "hexkit")
        os.makedirs(self.d)
        self.dl = os.path.join(self.root, "a.tgz")
        with open(self.dl, "wb") as f:
            f.write(b"the archive")

    def run_sh(self, fields, body, unshare=None, env=None):
        """`fields` answers `sdk_meta field hexkit PATH`; `unshare`, where
        given, stands in for the node's own: "no" refuses every namespace.
        No helper of the machine's own is reached for: `env` names one."""
        table = "\n".join(f"        {k!r}) printf '%s\\n' {v!r} ;;" for k, v in fields.items())
        fake = ""
        if unshare == "no":
            fake = 'unshare() { return 1; }\n'
        script = f"""
source {LIB}/common.sh
source {LIB}/sdk.sh
sdk_meta() {{
    [ "$1" = field ] || return 0
    case "$3" in
{table}
        *) printf '\\n' ;;
    esac
}}
{fake}{body}
"""
        p = subprocess.run(["bash", "-c", script], capture_output=True, text=True, check=False,
                           env={**os.environ, "BB_TOOLPACKS_FILE_URLS": "1",
                                "BUILDERBOT_NETCUT_BIN": os.path.join(self.root, "no-helper"), **(env or {})})
        return p.returncode, p.stdout + p.stderr

    def fields(self, sha, url=None, to="dl/a.tgz"):
        return {"source.fetch.0.url": url or f"file://{self.dl}", "source.fetch.0.sha256": sha, "source.fetch.0.to": to}

    def test_a_download_that_matches_is_kept_where_the_manifest_says(self):
        sha = hashlib.sha256(b"the archive").hexdigest()
        rc, out = self.run_sh(self.fields(sha), f"sdk_fetch_declared hexkit {self.d}")
        self.assertEqual(rc, 0, out)
        with open(os.path.join(self.d, "dl", "a.tgz"), "rb") as f:
            self.assertEqual(f.read(), b"the archive")
        self.assertIn("verified: sha256 matches what hexkit declares for dl/a.tgz", out)
        self.assertEqual([n for n in os.listdir(self.d) if n.startswith(".bb-fetch")], [])

    def test_one_that_does_not_match_installs_nothing(self):
        rc, out = self.run_sh(self.fields("0" * 64), f"sdk_fetch_declared hexkit {self.d}; echo went-on")
        self.assertNotEqual(rc, 0)
        self.assertIn("answered a file whose sha256 is " + hashlib.sha256(b"the archive").hexdigest(), out)
        self.assertIn("its manifest declares " + "0" * 64, out)
        self.assertNotIn("went-on", out)
        self.assertFalse(os.path.exists(os.path.join(self.d, "dl", "a.tgz")))
        self.assertEqual([n for n in os.listdir(self.d) if n.startswith(".bb-fetch")], [], "and the bad file is not left behind")

    def test_only_https_and_only_inside_the_pack(self):
        sha = hashlib.sha256(b"the archive").hexdigest()
        rc, out = self.run_sh(self.fields(sha, url="http://example.com/a.tgz"), f"sdk_fetch_declared hexkit {self.d}")
        self.assertTrue(rc != 0 and "is fetched over https" in out, out)
        rc, out = self.run_sh(self.fields(sha, to="../escaped.tgz"), f"sdk_fetch_declared hexkit {self.d}")
        self.assertTrue(rc != 0 and "is kept inside the pack" in out, out)
        self.assertFalse(os.path.exists(os.path.join(self.root, "escaped.tgz")))

    def test_a_node_that_cannot_cut_the_network_says_so_and_goes_on(self):
        rc, out = self.run_sh({}, f'sdk_net_cut hexkit {self.d}; echo "cut=${{#SDK_CUT[@]}}"; cat {self.d}/.bb-net', unshare="no")
        self.assertEqual(rc, 0, out)
        self.assertIn("this node cannot cut the network for a step", out)
        self.assertIn("cut=0", out)
        self.assertIn("open", out.splitlines()[-1])

    def helper(self, sudo_ok=True):
        """A stand-in for a managed node's helper and for sudo: sudo starts
        what it is handed with a plain environment, as the real one does, and
        the helper says it was the way in."""
        bin_ = os.path.join(self.root, "bin")
        os.makedirs(bin_)
        tool = os.path.join(self.root, "bb-netcut")
        for path, text in ((tool, '#!/bin/sh\nVIA=helper exec env "$@"\n'),
                           (os.path.join(bin_, "sudo"),
                            '#!/bin/sh\n[ "$1" = -n ] && shift\n' + ('exec env -i PATH=/usr/bin:/bin "$@"\n' if sudo_ok else 'exit 1\n'))):
            with open(path, "w") as f:
                f.write(text)
            os.chmod(path, 0o755)
        tmp = os.path.join(self.root, "tmp")
        os.makedirs(tmp)
        return {"BUILDERBOT_NETCUT_BIN": tool, "PATH": bin_ + os.pathsep + os.environ.get("PATH", "/usr/bin:/bin"), "TMPDIR": tmp}, tmp

    def test_where_the_account_cannot_the_nodes_helper_cuts_it(self):
        env, tmp = self.helper()
        body = (f'sdk_net_cut hexkit {self.d}; cat {self.d}/.bb-net; '
                'env STEP_SAYS="two words" "${SDK_CUT[@]}" sh -c \'echo "step=$STEP_SAYS via=$VIA arg=$1"\' _ "an arg"; '
                '"${SDK_CUT[@]}" sh -c "exit 7"; echo "rc=$?"')
        rc, out = self.run_sh({}, body, unshare="no", env=env)
        self.assertEqual(rc, 0, out)
        self.assertIn("its steps run with no network", out)
        lines = out.splitlines()
        self.assertIn("cut", lines)
        # The step's own environment and words reach it through sudo's plain
        # one, and what it exits with comes back.
        self.assertIn("step=two words via=helper arg=an arg", lines)
        self.assertIn("rc=7", lines)
        self.assertEqual(os.listdir(tmp), [], "the environment's file is not left behind")

    def test_a_helper_sudo_refuses_is_no_cut(self):
        env, _ = self.helper(sudo_ok=False)
        rc, out = self.run_sh({}, f'sdk_net_cut hexkit {self.d}; echo "cut=${{#SDK_CUT[@]}}"; cat {self.d}/.bb-net', unshare="no", env=env)
        self.assertEqual(rc, 0, out)
        self.assertIn("this node cannot cut the network for a step", out)
        self.assertIn("cut=0", out)

    def test_a_node_that_can_runs_a_step_with_no_network(self):
        probe = subprocess.run(["unshare", "--user", "--map-root-user", "--net", "true"], capture_output=True, check=False)
        if probe.returncode != 0:
            self.skipTest("this machine cannot make a network namespace without root")
        body = (f'sdk_net_cut hexkit {self.d}; cat {self.d}/.bb-net; '
                'env "${SDK_CUT[@]}" sh -c \'ls /sys/class/net | tr "\\n" " "; echo; touch "$0/made"; id -u\' ' + self.d)
        rc, out = self.run_sh({}, body)
        self.assertEqual(rc, 0, out)
        self.assertIn("its steps run with no network", out)
        lines = out.splitlines()
        self.assertIn("cut", lines)
        # Nothing but the loopback, which is down; and what it makes is the account's own.
        self.assertTrue(any(ln.split() == ["lo"] for ln in lines), out)
        self.assertEqual(os.stat(os.path.join(self.d, "made")).st_uid, os.getuid())


if __name__ == "__main__":
    unittest.main()
