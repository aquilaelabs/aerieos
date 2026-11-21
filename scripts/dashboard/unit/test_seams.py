"""The controller's test seams are read in one place (seams.py) and only
where it is AerieOS's own source tree's, told by where the file is: the
tree's Dockerfile and its tools/ beside it, which no image and no
bare-metal install lays out. An environment says nothing about it, so the
browser harness's whole block of variables, pasted into an install's
compose override or env file, swaps no trust root and turns no check off,
which a marker variable in that same block never could (the second audit
of 21 Nov)."""
import importlib
import importlib.util
import os
import re
import shutil
import sys
import tempfile
import unittest
from unittest import mock

HERE = os.path.dirname(os.path.abspath(__file__))
DASH = os.path.join(HERE, "..")
REPO = os.path.abspath(os.path.join(HERE, "..", "..", ".."))
sys.path.insert(0, DASH)
import seams  # noqa: E402
import toolpacks  # noqa: E402


def harness_env():
    """The variables the browser harness starts the server with, as its
    block in run.sh writes them: what an administrator might paste."""
    with open(os.path.join(DASH, "test", "run.sh"), encoding="utf-8") as f:
        run = f.read()
    block = run[:run.index('python3 "$DASH/server.py" >> "$S/server.log"')]
    block = block[block.rindex("( env "):]
    return {k: (v.strip('"') or "x").replace("$S", "/tmp/s").replace("$DASH", "/tmp/d") for k, v in re.findall(r"\b([A-Z][A-Z0-9_]+)=(\"[^\"]*\"|\S*)", block)}


class Seams(unittest.TestCase):
    def env(self, **more):
        clean = {k: v for k, v in os.environ.items() if k not in seams.SEAMS and not seams.LATEST.fullmatch(k)}
        return mock.patch.dict(os.environ, {**clean, **more}, clear=True)

    def test_the_source_tree_is_told_by_where_the_file_is(self):
        self.assertTrue(seams.IN_TREE, "the unit tests run in the source tree")
        # A layout as an install has it: the Dockerfile's COPY lines under
        # /opt/aerieos, and what a bare-metal install adds (the Dockerfile
        # itself, its installer, its env file's template). Nothing under
        # tools/, so the same file there reads no seam.
        with open(os.path.join(REPO, "Dockerfile"), encoding="utf-8") as f:
            dests = re.findall(r"^COPY \S+ (/opt/aerieos\S*)$", f.read(), re.M)
        self.assertTrue(dests)
        self.assertFalse([d for d in dests if d.startswith(("/opt/aerieos/tools", "/opt/aerieos/Dockerfile"))], dests)
        with open(os.path.join(REPO, "nodes", "install-controller.sh"), encoding="utf-8") as f:
            sh = f.read()
        lay = sh[sh.index("lay_out() {"):]
        lay = lay[:lay.index("\n}\n")]
        extras = re.findall(r'install -m \d+ "\$t/(\S+)" "\$dir\.partial/', lay)
        self.assertEqual(sorted(extras), ["Dockerfile", "config/controller.env", "nodes/install-controller.sh"])
        top = tempfile.mkdtemp()
        self.addCleanup(shutil.rmtree, top, True)
        dash = os.path.join(top, "scripts", "dashboard")
        os.makedirs(os.path.join(dash, "unit"))
        shutil.copy(os.path.join(DASH, "seams.py"), dash)
        open(os.path.join(top, "Dockerfile"), "w").close()

        def load():
            spec = importlib.util.spec_from_file_location("seams_laid_out", os.path.join(dash, "seams.py"))
            m = importlib.util.module_from_spec(spec)
            spec.loader.exec_module(m)
            return m
        laid = load()
        self.assertFalse(laid.IN_TREE, "a bare-metal layout: its Dockerfile and its unit tests, and no tools/")
        with self.env(**harness_env()):
            for name in laid.SEAMS:
                self.assertEqual(laid.get(name, "the shipped one"), "the shipped one", name)
        os.makedirs(os.path.join(top, "tools"))
        self.assertTrue(load().IN_TREE, "a checkout, or the harness's copy of one")

    def test_a_seam_is_read_in_the_tree_alone(self):
        for name in seams.SEAMS:
            with self.env(**{name: "/tmp/planted"}):
                self.assertEqual(seams.get(name, "shipped"), "/tmp/planted", name)
                with mock.patch.object(seams, "IN_TREE", False):
                    self.assertEqual(seams.get(name, "shipped"), "shipped", name)
        with self.env(BB_CLAUDE_LATEST_URL="file:///tmp/x", BB_COPILOT_CLI_LATEST_URL="file:///tmp/y"):
            self.assertEqual((seams.latest_url("claude"), seams.latest_url("copilot-cli")), ("file:///tmp/x", "file:///tmp/y"))
            with mock.patch.object(seams, "IN_TREE", False):
                self.assertEqual(seams.latest_url("claude"), "")
        # What is not a seam is not read through here at all.
        self.assertRaises(KeyError, seams.get, "INSTALL_KEY")
        self.assertRaises(KeyError, seams.get, "BB_SEAMS")
        for name, what in seams.SEAMS.items():
            self.assertTrue(what, f"{name} says what it stands in for")

    def test_the_harness_block_pasted_into_an_install_swaps_no_trust_root(self):
        env = harness_env()
        for name in ("BB_RELEASE_SIGNERS", "BB_APPS_RELEASES_URL", "BB_IMAGE_DIGESTS_FILE", "BB_DOCKER_BIN", "BB_CLOUDFLARED",
                     "BB_SERVICE_IMAGES_FILE", "BB_TOOLPACKS_FILE_URLS", "BB_CLAUDE_LATEST_URL", "BB_BIN", "BB_TUNNEL_ROUTE_BASE"):
            self.assertIn(name, env, f"the harness sets {name}")
        import agentcode
        import agents
        import apps
        import imagecheck
        import nginxproxy
        import releasecheck
        import services
        import tunnel
        mods = (apps, releasecheck, imagecheck, services, tunnel, nginxproxy)
        shipped_signers = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(apps.__file__))), "..", "config", "release-signers")
        try:
            with self.env(**env), mock.patch.object(seams, "IN_TREE", False):
                for m in mods:
                    importlib.reload(m)
                self.assertEqual(os.path.normpath(apps.SIGNERS), os.path.normpath(shipped_signers))
                self.assertEqual(apps.RELEASES_URL, "https://api.github.com/repos/aquilaelabs/aerieos/releases")
                self.assertEqual(releasecheck.RELEASES_URL, apps.RELEASES_URL)
                self.assertEqual(imagecheck.DIGESTS_FILE, "")
                self.assertEqual(os.path.basename(services.IMAGES_FILE), "service-images.json")
                self.assertEqual(os.path.dirname(os.path.abspath(services.IMAGES_FILE)), os.path.abspath(DASH))
                self.assertEqual((tunnel.BIN, tunnel.ROUTE_BASE), ("cloudflared", ""))
                claude = agents.get("claude")
                self.assertEqual(agentcode.latest_url(claude), claude.latest_url or claude.latest_file)
                commit, sha = "a" * 40, "b" * 64
                self.assertEqual(toolpacks.fetch("file:///tmp/no-such-pack", commit).get("error"),
                                 "a pack is a git repository's address: https://host/owner/repo")
                self.assertEqual(toolpacks.fetch_folder("file:///tmp/no-such-pack", commit, sha, "packs/x", ("bbtool.json",)).get("error"),
                                 "a catalog entry is a git repository's address: https://host/owner/repo")
            with self.env(BB_TOOLPACKS_FILE_URLS="1"):
                for got in (toolpacks.fetch("file:///tmp/no-such-pack", commit),
                            toolpacks.fetch_folder("file:///tmp/no-such-pack", commit, sha, "packs/x", ("bbtool.json",))):
                    self.assertNotIn("git repository's address", got.get("error", ""), "in the tree its address is taken, and the fetch is what fails")
            # Certificates are asked of Let's Encrypt: an install's
            # environment names no other authority, a test of the tree may.
            with self.env(**env, BB_ACME_DIRECTORY="https://ca.example/directory"):
                with mock.patch.object(seams, "IN_TREE", False):
                    importlib.reload(nginxproxy)
                    self.assertEqual(nginxproxy.ACME_DIRECTORY, "https://acme-v02.api.letsencrypt.org/directory")
                importlib.reload(nginxproxy)
                self.assertEqual(nginxproxy.ACME_DIRECTORY, "https://ca.example/directory")
        finally:
            for m in mods:
                importlib.reload(m)

    def test_nothing_else_of_the_dashboard_reads_a_seam_s_variable(self):
        for name in sorted(os.listdir(DASH)):
            if name.endswith(".py") and name != "seams.py":
                with open(os.path.join(DASH, name), encoding="utf-8") as f:
                    code = "\n".join(ln for ln in f.read().splitlines() if not ln.lstrip().startswith("#"))
                for seam in seams.SEAMS:
                    self.assertNotRegex(code, rf"(environ|getenv)[^\n]*\b{seam}\b", f"{name} reads {seam} past seams.py")
                self.assertNotRegex(code, r"(environ|getenv)[^\n]*_LATEST_URL", f"{name} reads an agent's stand-in past seams.py")
                self.assertNotIn("BB_SEAMS", code, name)
        for path in (os.path.join(DASH, "test", "run.sh"), os.path.join(REPO, "tools", "packs-export.py")):
            with open(path, encoding="utf-8") as f:
                self.assertNotIn("BB_SEAMS", f.read(), path)
        # And none is a setting an install is told of.
        with open(os.path.join(REPO, "docs", "reference.md"), encoding="utf-8") as f:
            ref = f.read()
        for word in seams.SEAMS:
            self.assertIsNone(re.search(rf"\b{word}\b", ref), word)


if __name__ == "__main__":
    unittest.main()
