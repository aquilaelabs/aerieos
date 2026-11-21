"""The programs the controller's image takes from their vendors' releases
as it is built are pinned (R267 step 17): config/image-tools.json says, for
cloudflared, the linters, uv and mise, the version and the sha256 of the
exact file for each architecture, written as a toolchain's pinned source is
so tools/pins.py checks, moves and verifies it with the other tables. The
Dockerfile and the bare-metal installer fetch each through
scripts/lib/pin-fetch, which keeps a file only when it is the pinned bytes.
The newest release of the day of the build was taken before, held to
GitHub's word for it that day, so two builds of one commit could differ.
noVNC's source is a row of the same table. What the image takes from npm
(Playwright, web-ext) is installed by a committed lock, a folder a program
under config/image-npm, with `npm ci --ignore-scripts`, by the Dockerfile
and the installer alike; and the image it is built FROM is named by its
digest. The pin tool reads both with the other tables.

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
        self.assertEqual(sorted(self.rows), ["actionlint", "cloudflared", "hadolint", "mise", "novnc", "ruff", "uv", "yq"])
        for name, row in self.rows.items():
            src = row["source"]
            ck = src["checksum"]
            self.assertEqual(packformat.pin_refused(ck), "", name)
            self.assertEqual(packformat.source_refused(src), "", name)
            self.assertEqual(packformat.held(row)[0], "pinned", name)
            if name == "novnc":
                # One file for every platform: its release's source at the
                # tag, whose publisher states no digest for it.
                self.assertRegex(ck["sha256"], r"^[0-9a-f]{64}$")
                self.assertEqual(src["url"], "https://github.com/novnc/noVNC/archive/refs/tags/v{version}.tar.gz")
                self.assertEqual((ck["found"], packformat.track_refused(src["version"], "source.version")), ({"from": "none"}, ""))
                continue
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
        self.assertEqual(said, ["hadolint,yq,actionlint,ruff,uv,mise,cloudflared,novnc"])

    def test_pin_fetch_names_the_address_the_tool_verifies(self):
        # What pin-fetch downloads for a row is what tools/pins.py verify holds to the pin.
        for name, row in self.rows.items():
            for plat, (url, digest) in pins.pinned_files(row).items():
                ck = row["source"]["checksum"]
                of = lambda v, plat=plat: v[plat] if isinstance(v, dict) else v  # noqa: E731
                self.assertEqual(url, of(row["source"]["url"]).replace("{version}", ck["version"]), f"{name} {plat}")
                self.assertEqual(digest, of(ck["sha256"]), f"{name} {plat}")


class WhatNpmInstalls(unittest.TestCase):
    """config/image-npm: a folder a program, its lock what `npm ci` installs
    by; the pin tool's rows for them, with npm stood in."""

    def lock(self, name, version, deps=()):
        packages = {"": {"name": f"aerieos-image-{name}", "dependencies": {name: version}}}
        for n, v in ((name, version), *deps):
            packages[f"node_modules/{n}"] = {"version": v, "resolved": f"https://registry.npmjs.org/{n}/-/{n}-{v}.tgz", "integrity": "sha512-" + "A" * 86 + "=="}
        return {"name": f"aerieos-image-{name}", "lockfileVersion": 3, "requires": True, "packages": packages}

    def folder(self, version="1.0.0", deps=(("dep", "2.0.0"),)):
        root = tempfile.mkdtemp()
        os.makedirs(os.path.join(root, "tool"))
        with open(os.path.join(root, "tool", "package.json"), "w") as f:
            json.dump({"name": "aerieos-image-tool", "private": True, "dependencies": {"tool": version}}, f)
        with open(os.path.join(root, "tool", "package-lock.json"), "w") as f:
            json.dump(self.lock("tool", version, deps), f)
        return root

    def test_each_shipped_program_is_one_version_and_a_lock_that_holds_every_package(self):
        doc = pins.npm_doc(pins.IMAGE_NPM)
        self.assertEqual([r["name"] for r in doc["tools"]], ["npm-playwright", "npm-web-ext"])
        for row in doc["tools"]:
            self.assertEqual(pins.npm_refused(row), "", row["name"])
            self.assertTrue(pins.is_pinned(row))
            (name, version), = pins.npm_wanted(row).items()
            self.assertEqual("npm-" + name, row["name"])
            self.assertRegex(version, r"^\d+\.\d+\.\d+$")
            packages = pins.npm_packages(row["npm"]["lock"])
            self.assertEqual(packages[f"node_modules/{name}"][0], version, "the lock holds the version asked for")
            for path, (_v, url, integrity) in packages.items():
                self.assertRegex(url, r"^https://registry\.npmjs\.org/", path)
                self.assertRegex(integrity, r"^sha512-[A-Za-z0-9+/]{86}==$", path)
            # Laid out as the tool writes them, so a move's diff is the lines that changed.
            for f, what in (("package.json", row["npm"]["manifest"]), ("package-lock.json", row["npm"]["lock"])):
                self.assertEqual(text("config", "image-npm", name, f), json.dumps(what, indent=2, ensure_ascii=False) + "\n", f"{name}/{f}")

    def test_what_is_not_a_lock_that_holds_is_said(self):
        root = self.folder()
        row = pins.npm_doc(root)["tools"][0]
        self.assertEqual(pins.npm_refused(row), "")
        for change, why in ((lambda r: r["npm"]["manifest"]["dependencies"].update(tool="^1.0.0"), "which is no one version"),
                            (lambda r: r["npm"]["manifest"]["dependencies"].update(tool="latest"), "which is no one version"),
                            (lambda r: r["npm"]["manifest"]["dependencies"].update(tool="1.0.1"), "was not written for its package.json"),
                            (lambda r: r["npm"].update(lock={}), "it has no package-lock.json"),
                            (lambda r: r["npm"]["lock"]["packages"]["node_modules/dep"].pop("integrity"), "dep is held to nothing in its lock"),
                            (lambda r: r["npm"]["lock"]["packages"]["node_modules/dep"].update(integrity="sha1-abc"), "dep is held to nothing in its lock"),
                            (lambda r: r["npm"]["lock"]["packages"]["node_modules/dep"].update(resolved="http://registry.example/dep.tgz"), "dep is held to nothing in its lock"),
                            (lambda r: r["npm"]["lock"]["packages"]["node_modules/dep"].update(resolved="git+ssh://git@example.com/dep.git"), "dep is held to nothing in its lock")):
            bad = pins.npm_doc(root)["tools"][0]
            change(bad)
            self.assertIn(why, pins.npm_refused(bad))
            self.assertFalse(pins.is_pinned(bad))

    def test_check_says_a_newer_version_and_a_lock_that_would_change_and_move_writes_both_files(self):
        root = self.folder()
        newest = {"tool": "1.0.0"}
        locks = lambda manifest: self.lock("tool", manifest["dependencies"]["tool"], (("dep", "2.0.0" if manifest["dependencies"]["tool"] == "1.0.0" else "2.1.0"),))  # noqa: E731
        with mock.patch.object(pins, "npm_newest", lambda name: newest[name]), mock.patch.object(pins, "npm_project", lambda manifest: locks(manifest)):
            said = []
            self.assertEqual(pins.main(["check", "--file", root], out=said.append), 0, said)
            self.assertEqual(said, ["npm-tool: tool is at 1.0.0", "npm-tool: its lock is at 2 package(s) (npm writes the lock it holds)", "nothing would move"])
            newest["tool"] = "1.1.0"
            said.clear()
            self.assertEqual(pins.main(["check", "--file", root], out=said.append), 3, said)
            self.assertEqual(said[:2], ["npm-tool: tool 1.0.0 to 1.1.0", "npm-tool: its lock 2 package(s) to 2 package(s) (tool 1.0.0 to 1.1.0; dep 2.0.0 to 2.1.0)"])
            self.assertEqual(json.load(open(os.path.join(root, "tool", "package.json")))["dependencies"], {"tool": "1.0.0"}, "check writes nothing")
            said.clear()
            self.assertEqual(pins.main(["move", "--file", root], out=said.append), 0, said)
            got = pins.npm_doc(root)["tools"][0]
            self.assertEqual((pins.npm_wanted(got), pins.npm_refused(got)), ({"tool": "1.1.0"}, ""))
            self.assertEqual({p: v[0] for p, v in pins.npm_packages(got["npm"]["lock"]).items()}, {"node_modules/tool": "1.1.0", "node_modules/dep": "2.1.0"})
            self.assertNotIn("rev", json.load(open(os.path.join(root, "tool", "package.json"))))
            # A lock npm would write otherwise for the same version (a range under it moved) is a move too.
            locks2 = lambda manifest: self.lock("tool", "1.1.0", (("dep", "2.2.0"),))  # noqa: E731
            with mock.patch.object(pins, "npm_project", locks2):
                said.clear()
                self.assertEqual(pins.main(["check", "--file", root], out=said.append), 3, said)
                self.assertIn("dep 2.1.0 to 2.2.0", said[1])

    def test_a_program_with_no_lock_yet_is_pinned_at_the_version_it_asks_for(self):
        root = self.folder()
        os.unlink(os.path.join(root, "tool", "package-lock.json"))
        with mock.patch.object(pins, "npm_newest", lambda name: "9.9.9"), mock.patch.object(pins, "npm_project", lambda m: self.lock("tool", m["dependencies"]["tool"])):
            said = []
            self.assertEqual(pins.main(["check", "--file", root], out=said.append), 0, said)
            self.assertEqual(pins.main(["pin", "npm-tool", "--file", root], out=said.append), 0, said)
        got = pins.npm_doc(root)["tools"][0]
        self.assertEqual((pins.npm_wanted(got), pins.npm_refused(got)), ({"tool": "1.0.0"}, ""))

    def test_check_with_nothing_named_asks_them_and_the_base_image_too(self):
        with mock.patch.object(pins, "run", lambda verb, docs, names, opts, out: [n for d in docs for n in pins.names_of(d)]):
            names = pins.main(["check"], out=lambda s: None)
        for name in ("npm-playwright", "npm-web-ext", "image-base", "novnc", "zig"):
            self.assertIn(name, names)
        self.assertEqual(len(names), len(set(names)), "no two rows of what this tree ships share a name")


class TheBaseImage(unittest.TestCase):
    """The Dockerfile's FROM line names the base image by its tag and the
    digest of its list, and the pin tool reads and rewrites that line."""

    def test_the_image_is_built_from_a_digest(self):
        doc = pins.dockerfile_doc(os.path.join(REPO, "Dockerfile"))
        (row,) = doc["services"]
        self.assertEqual((row["name"], row["platforms"]), ("image-base", ["linux/amd64"]))
        (ref,) = row["images"].values()
        self.assertRegex(ref, r"^ubuntu:24\.04@sha256:[0-9a-f]{64}$")
        self.assertTrue(pins.is_pinned(row))
        self.assertEqual(pins.row_refused(row), "")
        build = text(".github", "workflows", "build-image.yml")
        self.assertIn("platforms: linux/amd64", build, "the platform the row is held for is the one the image is built for")

    def test_a_from_line_is_read_and_rewritten_and_nothing_else_of_the_file(self):
        was = "sha256:" + "a" * 64
        now = "sha256:" + "b" * 64
        src = ("# syntax=docker/dockerfile:1\nFROM --platform=$BUILDPLATFORM golang:1.24@" + was + " AS build\nRUN echo FROM ubuntu:1 > /x\n"
               "FROM ubuntu:24.04@" + was + "\nCOPY --from=build /x /x\nFROM build AS again\nFROM scratch\n")
        d = tempfile.mkdtemp()
        path = os.path.join(d, "Dockerfile")
        with open(path, "w") as f:
            f.write(src)
        doc = pins.dockerfile_doc(path)
        self.assertEqual(list(doc["services"][0]["images"]), ["golang:1.24@" + was, "ubuntu:24.04@" + was], "an earlier stage and scratch are no image")
        learned = lambda row, ref: {"ref": ref.replace(was, now) if ref.startswith("ubuntu") else ref, "how": "read from its registry", "held": ""}  # noqa: E731
        with mock.patch.object(pins, "image_learned", learned):
            said = []
            self.assertEqual(pins.main(["check", "--file", path], out=said.append), 3, said)
            self.assertEqual(open(path).read(), src, "check writes nothing")
            self.assertEqual(pins.main(["move", "--file", path], out=said.append), 0, said)
        self.assertEqual(open(path).read(), src.replace("FROM ubuntu:24.04@" + was, "FROM ubuntu:24.04@" + now))
        # A base named by its tag alone is not pinned, and check says so.
        with open(path, "w") as f:
            f.write("FROM ubuntu:24.04\n")
        said = []
        pins.main(["check", "--file", path], out=said.append)
        self.assertIn("image-base: not pinned (ubuntu:24.04 names no digest)", said)


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
                                 ("uv", "linux/amd64"), ("mise", "linux/amd64"), ("novnc", "linux/amd64"), ("cloudflared", "linux/${arch}")])
        self.assertEqual(len(re.findall(r"\bbb-pin-fetch \S", src)), 8, "every fetch is one the table names")
        # noVNC is a row like the others: no pin of its own in the Dockerfile, and nothing fetched beside the table.
        self.assertNotRegex(src, r"(?m)^ARG NOVNC")
        code = "\n".join(ln for ln in src.splitlines() if not ln.lstrip().startswith("#"))
        self.assertNotIn("curl -fsSL -o /tmp/novnc", code)
        self.assertNotIn("pipx install", src, "nothing is whatever a package index serves that day")
        rows = {r["name"]: r for r in json.loads(text("config", "image-tools.json"))["tools"]}
        for name, plat in asked:
            digests = rows[name]["source"]["checksum"]["sha256"]
            for p in (["linux/amd64", "linux/arm64"] if "${arch}" in plat else [plat]):
                self.assertTrue(isinstance(digests, str) or p in digests, f"{name}: pinned for {p}, which the image asks for")
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
        # What npm installs is its lock's set and nothing else: no install
        # by name, every install with nobody's script run, each program
        # linked where NODE_PATH and the PATH find it.
        self.assertNotRegex(code, r"npm (install|i|add)\b")
        self.assertIn("COPY config/image-npm /usr/local/lib/aerieos-npm\n", src)
        self.assertEqual(re.findall(r"npm ci[^\n;]*", code),
                         ["npm ci --ignore-scripts --no-audit --prefix /usr/local/lib/aerieos-npm/playwright",
                          "npm ci --ignore-scripts --no-audit --prefix /usr/local/lib/aerieos-npm/web-ext"])
        for name in ("playwright", "web-ext"):
            self.assertIn(f'ln -s /usr/local/lib/aerieos-npm/{name}/node_modules/{name} "$(npm root -g)/{name}"', code)
            self.assertIn(f"ln -s /usr/local/lib/aerieos-npm/{name}/node_modules/.bin/{name} /usr/local/bin/{name}", code)
            self.assertLess(src.index("COPY config/image-npm"), src.index(f"aerieos-npm/{name};"))
        self.assertIn("NODE_PATH=/usr/lib/node_modules", src, "where a require() of the image's Playwright still resolves")
        # And the image it starts from is a digest, not whatever a tag serves that day.
        self.assertEqual(re.findall(r"(?m)^FROM (\S+)", src), [next(iter(pins.dockerfile_doc(os.path.join(REPO, "Dockerfile"))["services"][0]["images"]))])
        self.assertRegex(re.findall(r"(?m)^FROM (\S+)", src)[0], r"@sha256:[0-9a-f]{64}$")

    def test_the_installer_takes_the_same_pins(self):
        src = text("nodes", "install-controller.sh")
        self.assertNotIn("gh-fetch", src)
        self.assertNotIn(" latest ", src[src.index("extras() {"):src.index("# ---- the account and its folders")])
        self.assertIn('local pf="$TREE/scripts/lib/pin-fetch" pins="$TREE/config/image-tools.json"', src)
        asked = [n for n, _p in self.asks(src, 'bash "\\$pf"')]
        self.assertEqual(asked, ["hadolint", "yq", "actionlint", "ruff", "uv", "mise", "cloudflared"])
        self.assertNotIn("pipx install", src)
        # noVNC from the same table, as the tree being laid out pins it, and
        # no second copy of a pin scraped out of the Dockerfile.
        self.assertIn('bash "$t/scripts/lib/pin-fetch" "$t/config/image-tools.json" novnc linux/amd64', src)
        self.assertNotIn("dockerfile_arg", src)
        self.assertNotIn("NOVNC_SHA256", src)
        # The npm programs by their locks, as the image: nothing by name alone.
        code = "\n".join(ln for ln in src.splitlines() if not ln.lstrip().startswith("#"))
        self.assertNotRegex(code, r"npm (install|i|add)\b")
        self.assertIn('npm ci --ignore-scripts --no-audit --no-fund --prefix "$d"', code)
        self.assertIn('npm_program "$TREE" "$bin" || miss+=("$bin")', code)
        rows = {r["name"]: r for r in json.loads(text("config", "image-tools.json"))["tools"]}
        # On arm64 it takes what the image would: uv, mise and cloudflared are pinned there too.
        for name in ("uv", "mise", "cloudflared"):
            self.assertIn("linux/arm64", rows[name]["source"]["checksum"]["sha256"], name)

    def test_the_installer_installs_a_program_by_its_lock_and_links_it(self):
        # npm_program with npm stood in: the tree's two files land in the
        # prefix, npm is asked for exactly the lock's set with nobody's
        # script run, and the program is linked into the global modules and
        # onto the PATH; a tree with no lock for it installs nothing.
        d = tempfile.mkdtemp()
        tree, bin_, root = os.path.join(d, "tree"), os.path.join(d, "bin"), os.path.join(d, "root")
        os.makedirs(os.path.join(tree, "config", "image-npm", "tool"))
        os.makedirs(bin_)
        for f in ("package.json", "package-lock.json"):
            with open(os.path.join(tree, "config", "image-npm", "tool", f), "w") as fh:
                fh.write("{}\n")
        with open(os.path.join(bin_, "npm"), "w") as f:
            f.write(f"""#!/bin/bash
echo "$*" >> "{d}/npm.log"
case "$1" in
  root) echo "{root}/usr/lib/node_modules" ;;
  ci) p="${{@: -1}}"; mkdir -p "$p/node_modules/tool" "$p/node_modules/.bin"; echo x > "$p/node_modules/tool/index.js"; printf '#!/bin/sh\necho tool 1.0.0\n' > "$p/node_modules/.bin/tool"; chmod +x "$p/node_modules/.bin/tool" ;;
esac
""")
        os.chmod(os.path.join(bin_, "npm"), 0o755)
        env = dict(os.environ, BB_INSTALL_ROOT=root, NO_FETCH="1", PATH=bin_ + ":" + os.environ["PATH"])
        pre = f'set -euo pipefail\nBB_CONTROLLER_LIB=1 . "{os.path.join(REPO, "nodes", "install-controller.sh")}"\n'
        r = subprocess.run(["bash", "-c", pre + f'npm_program "{tree}" tool && ! npm_program "{tree}" other'], capture_output=True, text=True, timeout=60, check=False, env=env)
        self.assertEqual(r.returncode, 0, r.stderr)
        prefix = os.path.join(root, "usr", "local", "lib", "aerieos-npm", "tool")
        self.assertEqual(sorted(os.listdir(prefix)), ["node_modules", "package-lock.json", "package.json"])
        log = open(os.path.join(d, "npm.log")).read().splitlines()
        self.assertEqual(log, [f"ci --ignore-scripts --no-audit --no-fund --prefix {prefix}", "root -g"])
        self.assertEqual(os.path.realpath(os.path.join(root, "usr", "lib", "node_modules", "tool")), os.path.join(prefix, "node_modules", "tool"))
        self.assertEqual(subprocess.run([os.path.join(root, "usr", "local", "bin", "tool")], capture_output=True, text=True, check=False).stdout, "tool 1.0.0\n")

    def test_the_build_hands_the_image_no_token_for_it(self):
        self.assertNotIn("gh_token", text(".github", "workflows", "build-image.yml"))
        self.assertFalse(os.path.exists(os.path.join(REPO, "scripts", "lib", "gh-fetch")))


if __name__ == "__main__":
    unittest.main()
