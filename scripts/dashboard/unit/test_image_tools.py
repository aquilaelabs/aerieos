"""The programs the controller's image takes from their vendors' releases
as it is built are pinned (R267 step 17): config/image-tools.json says, for
cloudflared, the linters, uv and mise, the version and the sha256 of the
exact file for each architecture, written as a toolchain's pinned source is
so tools/pins.py checks, moves and verifies it with the other tables. The
Dockerfile and the bare-metal installer fetch each through
scripts/lib/pin-fetch, which keeps a file only when it is the pinned bytes.
The newest release of the day of the build was taken before, held to
GitHub's word for it that day, so two builds of one commit could differ.

pin-fetch against a local server and a made-up table; the shipped table
read for what a build depends on; and the Dockerfile and the installer read
for what they ask of it."""
import hashlib
import http.server
import importlib.util
import json
import os
import re
import subprocess
import sys
import tempfile
import threading
import unittest
from unittest import mock

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))
import packformat  # noqa: E402
from sdkstore import REPO  # noqa: E402

spec = importlib.util.spec_from_file_location("pins_tool_image_tools", os.path.join(REPO, "tools", "pins.py"))
pins = importlib.util.module_from_spec(spec)
spec.loader.exec_module(pins)

FETCH = os.path.join(REPO, "scripts", "lib", "pin-fetch")
SHIPPED = os.path.join(REPO, "config", "image-tools.json")
BODY = b"the tool, version 9.1"


def text(*parts):
    with open(os.path.join(REPO, *parts), encoding="utf-8") as f:
        return f.read()


class Fake(http.server.BaseHTTPRequestHandler):
    pages = {}
    asked = []

    def do_GET(self):
        Fake.asked.append(self.path)
        body = self.pages.get(self.path)
        if body is None:
            self.send_response(404)
            self.end_headers()
            return
        self.send_response(200)
        self.send_header("Content-Length", str(len(body)))
        self.end_headers()
        self.wfile.write(body)

    def log_message(self, *a):
        pass


class PinFetch(unittest.TestCase):
    def setUp(self):
        self.srv = http.server.HTTPServer(("127.0.0.1", 0), Fake)
        threading.Thread(target=self.srv.serve_forever, daemon=True).start()
        self.addCleanup(self.srv.shutdown)
        self.addCleanup(self.srv.server_close)
        self.base = f"http://127.0.0.1:{self.srv.server_port}"
        self.d = tempfile.mkdtemp()
        self.table = os.path.join(self.d, "tools.json")
        Fake.pages, Fake.asked = {"/dl/v9.1/tool-9.1-amd64": BODY, "/dl/v9.1/tool-9.1-arm64": b"the arm one"}, []
        self.write([{"name": "tool", "source": {"kind": "script",
                                                "url": {"linux/amd64": self.base + "/dl/v{version}/tool-{version}-amd64",
                                                        "linux/arm64": self.base + "/dl/v{version}/tool-{version}-arm64"},
                                                "checksum": {"from": "pin", "version": "9.1",
                                                             "sha256": {"linux/amd64": hashlib.sha256(BODY).hexdigest(),
                                                                        "linux/arm64": hashlib.sha256(b"the arm one").hexdigest()}}}},
                    {"name": "one", "source": {"kind": "tarball", "url": self.base + "/dl/v{version}/tool-{version}-amd64",
                                               "checksum": {"from": "pin", "version": "9.1", "sha256": hashlib.sha256(BODY).hexdigest()}}},
                    {"name": "open", "source": {"kind": "script", "url": {"linux/amd64": self.base + "/dl/v{version}/tool-{version}-amd64"},
                                                "checksum": {"from": "github-asset"}}}])

    def write(self, rows):
        with open(self.table, "w") as f:
            json.dump({"tools": rows}, f)

    def run_it(self, name="tool", plat="linux/amd64", table=None):
        dest = os.path.join(self.d, "kept")
        p = subprocess.run(["bash", FETCH, table or self.table, name, plat, dest], capture_output=True, text=True, check=False, timeout=60)
        return p, dest

    def test_the_pinned_file_is_kept_and_its_version_said(self):
        p, dest = self.run_it()
        self.assertEqual((p.returncode, p.stdout.strip()), (0, "9.1"), p.stderr)
        with open(dest, "rb") as f:
            self.assertEqual(f.read(), BODY)
        self.assertEqual(Fake.asked, ["/dl/v9.1/tool-9.1-amd64"], "the one address the pin names, and nobody asked what is newest")
        p, dest = self.run_it(plat="linux/arm64")
        self.assertEqual(p.returncode, 0, p.stderr)
        with open(dest, "rb") as f:
            self.assertEqual(f.read(), b"the arm one")
        # A row with one address and one digest, whatever the platform asked for.
        self.assertEqual(self.run_it("one")[0].returncode, 0)

    def test_a_file_that_is_not_the_pinned_bytes_is_refused_and_nothing_replaced(self):
        dest = os.path.join(self.d, "kept")
        with open(dest, "w") as f:
            f.write("what was there")
        Fake.pages["/dl/v9.1/tool-9.1-amd64"] = b"another release under the same name"
        p, dest = self.run_it()
        self.assertEqual(p.returncode, 1)
        self.assertIn("tool 9.1 for linux/amd64 is not the pinned file", p.stderr)
        with open(dest) as f:
            self.assertEqual(f.read(), "what was there")
        del Fake.pages["/dl/v9.1/tool-9.1-amd64"]
        p, dest = self.run_it()
        self.assertEqual(p.returncode, 1)
        self.assertIn("could not download", p.stderr)
        with open(dest) as f:
            self.assertEqual(f.read(), "what was there")

    def test_what_the_table_does_not_pin_is_said_and_nothing_fetched(self):
        for args, why in ((("nosuch",), "pins nothing named nosuch"),
                          (("tool", "darwin/arm64"), "tool is not pinned for darwin/arm64"),
                          (("open",), "open is not pinned in")):
            p, dest = self.run_it(*args)
            self.assertEqual(p.returncode, 1, args)
            self.assertIn(why, p.stderr)
            self.assertFalse(os.path.exists(dest))
        p, _ = self.run_it(table=os.path.join(self.d, "nosuch.json"))
        self.assertEqual(p.returncode, 2)
        with open(self.table, "w") as f:
            f.write("not json")
        p, _ = self.run_it()
        self.assertEqual(p.returncode, 1)
        self.assertIn("is no table of pins", p.stderr)
        self.assertEqual(Fake.asked, [])


class ShippedTable(unittest.TestCase):
    def setUp(self):
        self.text = text("config", "image-tools.json")
        self.doc = json.loads(self.text)
        self.rows = {r["name"]: r for r in self.doc["tools"]}

    def test_it_is_laid_out_as_the_tool_saves_it(self):
        self.assertEqual(json.dumps(self.doc, indent=2, ensure_ascii=False) + "\n", self.text, "a move's diff is then the lines that changed")

    def test_every_row_is_a_whole_pin_for_every_platform_it_offers(self):
        self.assertEqual(sorted(self.rows), ["actionlint", "cloudflared", "hadolint", "mise", "ruff", "uv", "yq"])
        for name, row in self.rows.items():
            src = row["source"]
            ck = src["checksum"]
            self.assertEqual(packformat.pin_refused(ck), "", name)
            self.assertEqual(packformat.source_refused(src), "", name)
            self.assertEqual(packformat.held(row)[0], "pinned", name)
            self.assertIsInstance(ck["sha256"], dict, name)
            self.assertEqual(sorted(ck["sha256"]), sorted(src["url"]), f"{name}: a digest for every address, and no other")
            self.assertTrue(ck["version"], name)
            for plat, url in src["url"].items():
                self.assertRegex(plat, r"^linux/(amd64|arm64)$", name)
                self.assertRegex(url, r"^https://github\.com/[A-Za-z0-9._/{}-]+$", f"{name} {plat}")
                self.assertIn("/releases/download/", url, f"{name} {plat}")
                self.assertIn("{version}", url, f"{name} {plat}: the address names the version, so a pin is one release's file")
                self.assertRegex(ck["sha256"][plat], r"^[0-9a-f]{64}$", f"{name} {plat}")
            self.assertEqual(packformat.track_refused(src["version"], "source.version"), "", name)
            self.assertEqual(packformat.found_refused(ck["found"]), "", name)

    def test_the_tool_reads_it_with_the_other_tables(self):
        self.assertIn((SHIPPED, ""), [(os.path.normpath(t), a) for t, a in pins.SHIPPED], "check with nothing named asks it too")
        self.assertIn("tools", pins.LISTS)
        with mock.patch.dict(pins.VERBS, {"check": lambda doc, names, opts, out: out(",".join(r["name"] for r in pins.chosen(doc, names))) or 0}):
            said = []
            self.assertEqual(pins.main(["check", "--file", SHIPPED], out=said.append), 0, said)
        self.assertEqual(said, ["hadolint,yq,actionlint,ruff,uv,mise,cloudflared"])

    def test_pin_fetch_names_the_address_the_tool_verifies(self):
        # What pin-fetch downloads for a row is what tools/pins.py verify holds to the pin.
        for name, row in self.rows.items():
            for plat, (url, digest) in pins.pinned_files(row).items():
                ck = row["source"]["checksum"]
                self.assertEqual(url, row["source"]["url"][plat].replace("{version}", ck["version"]), f"{name} {plat}")
                self.assertEqual(digest, ck["sha256"][plat], f"{name} {plat}")


class WhatReadsIt(unittest.TestCase):
    """The Dockerfile and the bare-metal installer ask the table, and nothing asks for the newest."""

    def asks(self, src, fetch):
        return re.findall(rf'{fetch} "?\$?[\w/.{{}}-]*"? ([a-z]+) "?(linux/\$\{{arch\}}|linux/amd64|\$plat)"?', src)

    def test_the_dockerfile_takes_each_tool_as_the_table_pins_it(self):
        src = text("Dockerfile")
        self.assertNotIn("gh-fetch", src)
        self.assertNotIn("gh_token", src, "nothing asks GitHub's API as the image is built")
        self.assertEqual(re.findall(r"^\s*bb-\S+ .*\blatest\b.*$", src, re.M), [])
        self.assertIn("COPY config/image-tools.json /opt/aerieos/config/image-tools.json\n", src)
        self.assertIn("COPY scripts/lib/pin-fetch /usr/local/bin/bb-pin-fetch\n", src)
        asked = self.asks(src, "bb-pin-fetch")
        self.assertEqual(asked, [("hadolint", "linux/amd64"), ("yq", "linux/amd64"), ("actionlint", "linux/amd64"), ("ruff", "linux/amd64"),
                                 ("uv", "linux/amd64"), ("mise", "linux/amd64"), ("cloudflared", "linux/${arch}")])
        self.assertEqual(len(re.findall(r"\bbb-pin-fetch \S", src)), 7, "every fetch is one the table names")
        self.assertNotIn("pipx install", src, "nothing is whatever a package index serves that day")
        rows = {r["name"]: r for r in json.loads(text("config", "image-tools.json"))["tools"]}
        for name, plat in asked:
            for p in (["linux/amd64", "linux/arm64"] if "${arch}" in plat else [plat]):
                self.assertIn(p, rows[name]["source"]["checksum"]["sha256"], f"{name}: pinned for {p}, which the image asks for")
        # The table is copied before the first fetch reads it.
        self.assertLess(src.index("COPY config/image-tools.json"), src.index("bb-pin-fetch \"$pins\" hadolint"))

    def test_the_image_fetches_no_key_and_no_newest_release_as_it_is_built(self):
        # Each package source is held to its publisher's key as the tree
        # carries it, and what npm installs is named at one version.
        src = text("Dockerfile")
        code = "\n".join(ln for ln in src.splitlines() if not ln.lstrip().startswith("#"))
        self.assertNotRegex(code, r"curl[^\n]*(gpg|keyring|\.asc|\.key)", "no key is fetched at build time")
        self.assertNotRegex(code, r"curl[^\n|]*\|\s*(ba)?sh\b", "nothing fetched is piped to a shell")
        self.assertIn("COPY config/apt-keys/ /tmp/apt-keys/\n", src)
        for name in ("nodesource", "github-cli", "docker"):
            key = text("config", "apt-keys", f"{name}.asc")
            self.assertEqual((key.count("-----BEGIN PGP PUBLIC KEY BLOCK-----"), key.count("-----END PGP PUBLIC KEY BLOCK-----")), (1, 1), name)
            self.assertIn(f"< /tmp/apt-keys/{name}.asc", src, name)
        # Docker's is the one key, here and where a node is set up.
        prov = re.search(r"deb\) cat <<'DOCKERKEY'\n(.*?)\nDOCKERKEY", text("nodes", "provision-linux.sh"), re.S)
        self.assertEqual(prov.group(1).strip(), text("config", "apt-keys", "docker.asc").strip())
        for m in re.finditer(r"npm install -g[^\n;]*", code):
            self.assertRegex(m.group(0), r'"[a-z-]+@\$\{[A-Z_]+_VERSION\}"', m.group(0))
        for arg in ("PLAYWRIGHT_VERSION", "WEB_EXT_VERSION"):
            self.assertRegex(src, rf"(?m)^ARG {arg}=\d+\.\d+\.\d+$")

    def test_the_installer_takes_the_same_pins(self):
        src = text("nodes", "install-controller.sh")
        self.assertNotIn("gh-fetch", src)
        self.assertNotIn(" latest ", src[src.index("extras() {"):src.index("# ---- the account and its folders")])
        self.assertIn('local pf="$TREE/scripts/lib/pin-fetch" pins="$TREE/config/image-tools.json"', src)
        asked = [n for n, _p in self.asks(src, 'bash "\\$pf"')]
        self.assertEqual(asked, ["hadolint", "yq", "actionlint", "ruff", "uv", "mise", "cloudflared"])
        self.assertNotIn("pipx install", src)
        rows = {r["name"]: r for r in json.loads(text("config", "image-tools.json"))["tools"]}
        # On arm64 it takes what the image would: uv, mise and cloudflared are pinned there too.
        for name in ("uv", "mise", "cloudflared"):
            self.assertIn("linux/arm64", rows[name]["source"]["checksum"]["sha256"], name)

    def test_the_build_hands_the_image_no_token_for_it(self):
        self.assertNotIn("gh_token", text(".github", "workflows", "build-image.yml"))
        self.assertFalse(os.path.exists(os.path.join(REPO, "scripts", "lib", "gh-fetch")))


if __name__ == "__main__":
    unittest.main()
