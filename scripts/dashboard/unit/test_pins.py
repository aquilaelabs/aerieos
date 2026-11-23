"""tools/pins.py: the tool that moves a pin. An install takes the pin its
entry carries and asks nobody what is newest, so a newer version arrives
as a change to the row, proposed here from the row's own data: how its
newest version is found, and how the new file's digest is learned. Against
a table of made-up rows, with the network stood in for: check says what
would move and writes nothing, move rewrites only what changed and raises
the row's rev, a row moves whole or not at all, pin turns an
origin-checked row into a pinned one, and verify names a file that is not
its pin."""
import difflib
import hashlib
import importlib.util
import json
import os
import shutil
import sys
import tempfile
import unittest
import urllib.error
from unittest import mock

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))
import packformat  # noqa: E402
from sdkstore import REPO, sdkmeta  # noqa: E402

spec = importlib.util.spec_from_file_location("pins_tool", os.path.join(REPO, "tools", "pins.py"))
pins = importlib.util.module_from_spec(spec)
spec.loader.exec_module(pins)

GO = "https://dl.example.org/{version}.{plat}.tar.gz"
PLATS = {"linux/amd64": "linux-amd64", "linux/arm64": "linux-arm64"}
MOVING = "https://get.example.org/kit-latest.AppImage"


def sha(data, algo="sha256"):
    return hashlib.new(algo, data.encode()).hexdigest()


def go_url(version, plat):
    return GO.format(version=version, plat=PLATS[plat])


class Case(unittest.TestCase):
    """A table of rows, and the vendors they ask: `pages` are the documents
    a resolver or a publisher's statement is read from, `files` what each
    address answers when it is downloaded."""

    def setUp(self):
        self.d = tempfile.mkdtemp()
        self.addCleanup(shutil.rmtree, self.d, True)
        self.table = os.path.join(self.d, "toolchains.json")
        self.pages, self.files, self.refs, self.fetched = {}, {}, "", []
        self.release("go1.99.0")
        self.files[MOVING] = "the app, as first pinned"
        self.rows = [
            # A versioned download for two platforms, its digest stated beside it.
            {"name": "go", "label": "Go", "probe": "go", "about": "Go.", "platforms": list(PLATS), "layout": {"bin": ["bin"], "env": {}},
             "source": {"kind": "tarball", "url": {p: GO.replace("{plat}", PLATS[p]) for p in PLATS},
                        "version": {"resolver": "text", "url": "https://dl.example.org/VERSION"},
                        "checksum": {"from": "pin", "version": "go1.99.0", "sha256": {p: sha(self.files[go_url("go1.99.0", p)]) for p in PLATS},
                                     "found": {"from": "file", "url": "{url}.sha256"}}}},
            # A vendor's one moving file: no version, nothing to track.
            {"name": "app", "label": "App", "probe": "app", "about": "An app.", "platforms": ["linux/amd64"], "layout": {"bin": ["bin"], "env": {}},
             "source": {"kind": "script", "url": MOVING, "run": ["sh", "{script}"], "checksum": {"from": "pin", "sha256": sha(self.files[MOVING])}}},
            # Not pinned: checked against what its origin says on the day.
            {"name": "raw", "label": "Raw", "probe": "raw", "about": "Raw.", "platforms": list(PLATS), "layout": {"bin": ["bin"], "env": {}},
             "source": {"kind": "tarball", "url": {p: GO.replace("{plat}", PLATS[p]) for p in PLATS},
                        "version": {"resolver": "text", "url": "https://dl.example.org/VERSION"},
                        "checksum": {"from": "file", "url": "{url}.sha256"}}},
        ]
        self.write()
        for name, stand_in in (("get", self.get), ("final_url", mock.Mock(side_effect=AssertionError("asked for a redirect"))),
                               ("git_refs", lambda url, *refs: self.refs)):
            p = mock.patch.object(sdkmeta, name, stand_in)
            p.start()
            self.addCleanup(p.stop)
        p = mock.patch.object(pins, "hashed", self.hashed)
        p.start()
        self.addCleanup(p.stop)

    def release(self, version, state=True):
        """The vendor publishes `version`: its files, each with its
        sha256 stated beside it where `state`."""
        self.pages["https://dl.example.org/VERSION"] = version + "\n"
        for plat in PLATS:
            url = go_url(version, plat)
            self.files[url] = f"{version} for {plat}"
            if state:
                self.pages[url + ".sha256"] = f"{sha(self.files[url])}  {url.rsplit('/', 1)[-1]}\n"

    def gone(self, url):
        e = urllib.error.HTTPError(url, 404, "Not Found", None, None)
        e.close()
        raise e

    def get(self, url, decode=True):
        if url not in self.pages:
            self.gone(url)
        body = self.pages[url] if isinstance(self.pages[url], str) else json.dumps(self.pages[url])
        return body if decode else body.encode()

    def hashed(self, url, also=""):
        self.fetched.append(url)
        if url not in self.files:
            self.gone(url)
        data = self.files[url]
        return {"sha256": sha(data), **({also: sha(data, also)} if also else {}), "bytes": len(data)}

    def write(self):
        pins.save(self.table, {"_comment": ["a table of made-up rows"], "toolchains": self.rows})

    def read(self):
        with open(self.table, encoding="utf-8") as f:
            return f.read()

    def row(self, name):
        return next(r for r in json.loads(self.read())["toolchains"] if r["name"] == name)

    def run_tool(self, *argv):
        said = []
        rc = pins.main([*argv, "--file", self.table], out=said.append)
        return rc, "\n".join(said)


class Check(Case):
    def test_nothing_would_move_and_nothing_is_written(self):
        before = self.read()
        rc, out = self.run_tool("check")
        self.assertEqual(rc, 0, out)
        self.assertIn("go: its download is at go1.99.0 (its resolver finds the version it is pinned to)", out)
        self.assertIn("app: its download is at the pinned bytes (its address still answers the pinned bytes)", out)
        self.assertIn("nothing would move", out)
        self.assertNotIn("raw", out, "a row that is not pinned is not asked about, unless it is named")
        self.assertEqual(self.read(), before)
        # A versioned file is not downloaded to be checked; the one with no version is asked for its bytes.
        self.assertEqual(self.fetched, [MOVING])
        rc, out = self.run_tool("check", "raw")
        self.assertEqual((rc, out.splitlines()[0]), (0, "raw: not pinned (its download is checked against what its own origin says at the moment of the install (file), "
                                                        "not against a pin or a signature its entry carries)"))

    def test_it_says_a_newer_version_and_exits_3(self):
        before = self.read()
        self.release("go1.100.0")
        rc, out = self.run_tool("check", "go")
        self.assertEqual(rc, 3, out)
        self.assertIn("go: its download go1.99.0 to go1.100.0", out)
        for plat in PLATS:
            self.assertIn(f"    {plat}  sha256 {sha(self.files[go_url('go1.100.0', plat)])}  stated by {go_url('go1.100.0', plat)}.sha256", out)
        self.assertIn("1 row(s) would move", out)
        self.assertEqual(self.read(), before, "a check writes nothing")
        self.assertEqual(self.fetched, [], "and where the publisher states a sha256, nothing is downloaded")

    def test_it_says_when_a_file_with_no_version_no_longer_answers_the_pinned_bytes(self):
        self.files[MOVING] = "the app, as its vendor rebuilt it"
        rc, out = self.run_tool("check", "app")
        self.assertEqual(rc, 3, out)
        self.assertIn(f"app: its download the pinned bytes to other bytes (its vendor changed the file at {MOVING})", out)

    def test_an_error_is_said_by_name_and_exits_1(self):
        del self.pages["https://dl.example.org/VERSION"]
        rc, out = self.run_tool("check")
        self.assertEqual(rc, 1, out)
        self.assertIn("go: ", out)
        self.assertIn("https://dl.example.org/VERSION answered 404", out)
        self.assertIn("app: its download is at the pinned bytes", out, "the next row is still asked")
        rc, out = self.run_tool("check", "nope")
        self.assertEqual((rc, out), (1, "pins: no toolchain named nope in the table"))


class Move(Case):
    def test_it_rewrites_only_what_changed_for_every_platform_and_raises_the_rev(self):
        before = self.read().splitlines()
        self.release("go1.100.0")
        rc, out = self.run_tool("move")
        self.assertEqual(rc, 0, out)
        self.assertIn("go: its download go1.99.0 to go1.100.0", out)
        self.assertIn("go: rev 1 to 2", out)
        self.assertIn("app: nothing to move", out)
        diff = [ln for ln in difflib.unified_diff(before, self.read().splitlines(), lineterm="", n=0) if ln[:2] not in ("--", "++", "@@")]
        gone, new = [ln[1:].strip() for ln in diff if ln[0] == "-"], [ln[1:].strip() for ln in diff if ln[0] == "+"]
        old_sums = [sha(f"go1.99.0 for {p}") for p in PLATS]
        new_sums = [sha(f"go1.100.0 for {p}") for p in PLATS]
        # The version, a digest a platform, and the rev with the comma before it: no other line of the file.
        self.assertEqual(gone, ['"version": "go1.99.0",', f'"linux/amd64": "{old_sums[0]}",', f'"linux/arm64": "{old_sums[1]}"', "}"])
        self.assertEqual(new, ['"version": "go1.100.0",', f'"linux/amd64": "{new_sums[0]}",', f'"linux/arm64": "{new_sums[1]}"', "},", '"rev": 2'])
        go = self.row("go")
        self.assertEqual(go["source"]["checksum"]["found"], {"from": "file", "url": "{url}.sha256"}, "how the next one is found stays")
        self.assertEqual((packformat.held(go)[0], self.row("app").get("rev")), ("pinned", None))
        # Again with nothing newer: nothing moves, and the file is not touched.
        text = self.read()
        rc, out = self.run_tool("move")
        self.assertEqual((rc, self.read()), (0, text), out)
        # The next one raises it again.
        self.release("go1.101.0")
        rc, out = self.run_tool("move", "go")
        self.assertEqual((rc, self.row("go")["rev"]), (0, 3), out)

    def test_a_row_moves_whole_or_not_at_all(self):
        self.release("go1.100.0")
        self.files[MOVING] = "the app, as its vendor rebuilt it"
        # One platform's file is not out yet: no statement, and no file.
        arm = go_url("go1.100.0", "linux/arm64")
        del self.pages[arm + ".sha256"], self.files[arm]
        before = self.row("go")
        # A check says the row waits, and counts nothing of it as moving.
        rc, out = self.run_tool("check", "go")
        self.assertEqual(rc, 0, out)
        waits = f"its resolver finds go1.100.0, and linux/arm64 could not be learned ({arm}.sha256 answered 404)"
        self.assertIn(f"go: its download is at go1.99.0 ({waits}: it stays where it is)", out)
        self.assertIn("nothing would move; 1 row(s) wait for a release that is not out for every platform they name", out)
        rc, out = self.run_tool("move")
        self.assertEqual(rc, 1, out)
        self.assertIn(f"go: left as it was: {waits}", out)
        self.assertEqual(self.row("go"), before, "not one platform of it moved")
        # The row beside it moved all the same: its vendor's file re-pinned.
        self.assertIn("app: rev 1 to 2", out)
        self.assertEqual(self.row("app")["source"]["checksum"], {"from": "pin", "sha256": sha("the app, as its vendor rebuilt it")})

    def test_a_version_may_be_named_in_the_resolver_s_place(self):
        self.release("go1.100.0")
        self.release("go1.101.0")
        rc, out = self.run_tool("move", "go", "--version", "go1.100.0")
        self.assertEqual((rc, self.row("go")["source"]["checksum"]["version"]), (0, "go1.100.0"), out)
        # The version it has, named again, moves nothing.
        text = self.read()
        rc, out = self.run_tool("move", "go", "--version", "go1.100.0")
        self.assertEqual((rc, self.read()), (0, text), out)
        self.assertEqual(self.run_tool("move", "--version", "go1.101.0")[0], 1, "one row is named with it")

    def test_a_digest_its_publisher_states_as_a_sha1_is_hashed_here_and_held_to_it(self):
        self.release("go1.100.0", state=False)
        for plat in PLATS:
            url = go_url("go1.100.0", plat)
            self.pages[url + ".sha256"] = sha(self.files[url], "sha1") + "\n"
        rc, out = self.run_tool("move", "go")
        self.assertEqual(rc, 0, out)
        amd = go_url("go1.100.0", "linux/amd64")
        self.assertIn(f"sha256 {sha(self.files[amd])}  downloaded and hashed here ({len(self.files[amd])} bytes), its sha1 matching {amd}.sha256", out)
        self.assertEqual(sorted(self.fetched), sorted(go_url("go1.100.0", p) for p in PLATS))
        # A file that is not what its publisher states is refused, and the row stays.
        self.release("go1.101.0", state=False)
        for plat in PLATS:
            self.pages[go_url("go1.101.0", plat) + ".sha256"] = "0" * 40 + "\n"
        before = self.row("go")
        rc, out = self.run_tool("move", "go")
        self.assertEqual((rc, self.row("go")), (1, before), out)
        self.assertIn("answers a file whose sha1 is", out)


class Pin(Case):
    def test_an_origin_checked_row_becomes_a_pin_and_keeps_how_its_digest_is_found(self):
        self.assertEqual(packformat.held(self.row("raw"))[0], "open")
        rc, out = self.run_tool("pin", "raw")
        self.assertEqual(rc, 0, out)
        raw = self.row("raw")
        self.assertEqual(raw["source"]["checksum"], {"from": "pin", "version": "go1.99.0", "sha256": {p: sha(f"go1.99.0 for {p}") for p in PLATS},
                                                     "found": {"from": "file", "url": "{url}.sha256"}})
        self.assertEqual((raw["rev"], packformat.held(raw)[0], packformat.source_refused(raw["source"])), (2, "pinned", ""))
        self.assertIn("raw: rev 1 to 2; it reads pinned", out)
        # From here it moves as a pinned row does.
        self.release("go1.100.0")
        rc, out = self.run_tool("move", "raw")
        self.assertEqual((rc, self.row("raw")["source"]["checksum"]["version"], self.row("raw")["rev"]), (0, "go1.100.0", 3), out)
        # One pinned already is moved, not pinned again; one with nothing to pin says so.
        self.assertEqual(self.run_tool("pin", "go"), (1, "pins: go is left as it was: it is pinned already: tools/pins.py move go moves it"))
        # One whose file cannot be learned for every platform is left as it was, by name.
        self.rows[2]["source"]["checksum"] = {"from": "file", "url": "{url}.sha256"}
        self.write()
        del self.pages[go_url("go1.100.0", "linux/arm64") + ".sha256"], self.files[go_url("go1.100.0", "linux/arm64")]
        before = self.read()
        rc, out = self.run_tool("pin", "raw")
        self.assertEqual((rc, self.read()), (1, before), out)
        self.assertTrue(out.startswith("pins: raw is left as it was: linux/arm64 could not be learned ("), out)

    def test_a_resolver_that_supplies_the_address_has_it_written_beside_the_digest(self):
        asset = lambda tag, name: {"name": name, "browser_download_url": f"https://github.com/a/a/releases/download/{tag}/{name}"}  # noqa: E731
        self.pages["https://api.github.com/repos/a/a/releases?per_page=100"] = [
            {"tag_name": "build-8", "published_at": "2026-01-01T00:00:00Z", "assets": [asset("build-8", "kit-N-8-x64.tar.xz"), asset("build-8", "kit-N-8-arm64.tar.xz")]}]
        urls = {"linux/amd64": "https://github.com/a/a/releases/download/build-8/kit-N-8-x64.tar.xz",
                "linux/arm64": "https://github.com/a/a/releases/download/build-8/kit-N-8-arm64.tar.xz"}
        for u in urls.values():
            self.files[u] = "built " + u
        self.rows.append({"name": "kit", "label": "Kit", "probe": "kit", "about": "Kit.", "platforms": list(PLATS), "layout": {"bin": ["bin"], "env": {}},
                          "source": {"kind": "tarball", "url": {p: "https://github.com/a/a/releases/latest/download/kit-latest.tar.xz" for p in PLATS},
                                     "version": {"resolver": "github-release", "repo": "a/a", "tag": "^build-",
                                                 "asset": {"linux/amd64": "-x64\\.tar\\.xz$", "linux/arm64": "-arm64\\.tar\\.xz$"}},
                                     "checksum": {"from": "none", "why": "its publisher states none"}}})
        self.write()
        rc, out = self.run_tool("pin", "kit")
        self.assertEqual(rc, 0, out)
        src = self.row("kit")["source"]
        self.assertEqual(src["url"], urls)
        self.assertEqual(src["checksum"], {"from": "pin", "version": "build-8", "sha256": {p: sha("built " + u) for p, u in urls.items()}})
        self.assertIn("downloaded and hashed here", out)

    def test_a_repository_is_pinned_and_moved_by_its_track(self):
        self.refs = "".join(f"{c * 40}\trefs/tags/{t}\n" for c, t in (("1", "3.9.0"), ("2", "3.10.0"), ("3", "3.11.0-0.1.pre")))
        self.rows.append({"name": "sdk", "label": "SDK", "probe": "sdk", "about": "An SDK.", "platforms": ["linux/*"], "layout": {"bin": ["bin"], "env": {}},
                          "source": {"kind": "git", "url": "https://example.com/sdk.git", "branch": "stable", "depth": 1,
                                     "track": {"resolver": "git-tag", "match": "^\\d+\\.\\d+\\.\\d+$"}}})
        self.write()
        rc, out = self.run_tool("pin", "sdk")
        self.assertEqual(rc, 0, out)
        src = self.row("sdk")["source"]
        self.assertEqual((src["commit"], src["tag"], self.row("sdk")["rev"]), ("2" * 40, "3.10.0", 2))
        rc, out = self.run_tool("check", "sdk")
        self.assertEqual(rc, 0, out)
        self.assertIn("sdk: its commit is at 3.10.0 222222222222", out)
        self.refs += f"{'4' * 40}\trefs/tags/3.10.1\n"
        rc, out = self.run_tool("check", "sdk")
        self.assertEqual(rc, 3, out)
        self.assertIn("sdk: its commit 3.10.0 222222222222 to 3.10.1 444444444444", out)
        rc, out = self.run_tool("move", "sdk")
        src = self.row("sdk")["source"]
        self.assertEqual((rc, src["commit"], src["tag"], self.row("sdk")["rev"]), (0, "4" * 40, "3.10.1", 3), out)
        # A release's check: the tag is still at the pinned commit, or says where it went.
        self.assertEqual(self.run_tool("verify", "sdk")[0], 0)
        self.refs = self.refs.replace(f"{'4' * 40}\trefs/tags/3.10.1", f"{'5' * 40}\trefs/tags/3.10.1")
        rc, out = self.run_tool("verify", "sdk")
        self.assertEqual(rc, 1, out)
        self.assertIn(f"sdk: NOT ITS PIN: the tag 3.10.1 of https://example.com/sdk.git is at {'5' * 40}, and the row pins {'4' * 40}", out)


class Declared(Case):
    def test_downloads_that_share_a_track_move_together_and_one_with_none_is_asked_for_its_bytes(self):
        track = {"resolver": "text", "url": "https://dl.example.org/VERSION"}
        logo = "https://dl.example.org/logo.svg"
        self.files[logo] = "a logo"
        fetch = [{"url": GO.replace("{plat}", PLATS[p]), "version": "go1.99.0", "sha256": sha(f"go1.99.0 for {p}"), "to": "dl/go.tar.gz", "platform": p,
                  "track": track, "found": {"from": "file", "url": "{url}.sha256"}} for p in PLATS]
        fetch.append({"url": logo, "sha256": sha("a logo"), "to": "dl/logo.svg"})
        self.rows.append({"name": "set", "label": "Set", "probe": "set", "about": "A set.", "platforms": list(PLATS), "layout": {"bin": ["bin"], "env": {}},
                          "source": {"kind": "command", "run": ["sh", "{dir}/dl/setup.sh"], "fetch": fetch}})
        self.write()
        rc, out = self.run_tool("check", "set")
        self.assertEqual(rc, 0, out)
        self.release("go1.100.0")
        rc, out = self.run_tool("move", "set")
        self.assertEqual(rc, 0, out)
        got = self.row("set")["source"]["fetch"]
        self.assertEqual([(f.get("version"), f["sha256"]) for f in got],
                         [("go1.100.0", sha("go1.100.0 for linux/amd64")), ("go1.100.0", sha("go1.100.0 for linux/arm64")), (None, sha("a logo"))])
        self.assertEqual((got[0]["url"], got[0]["to"], self.row("set")["rev"]), (GO.replace("{plat}", "linux-amd64"), "dl/go.tar.gz", 2), "the address and the name stay")
        self.assertIn("set: dl/go.tar.gz for linux/arm64 go1.99.0", out)
        # The file with no version, changed by its vendor.
        self.files[logo] = "another logo"
        rc, out = self.run_tool("check", "set")
        self.assertEqual(rc, 3, out)
        self.assertIn(f"set: dl/logo.svg {sha('a logo')[:12]} to {sha('another logo')[:12]}", out)

    def tools_row(self):
        """A row of two tools, each a declared download with a track of its
        own, written as a person writes one before its first pin: the
        address, the track, and no digest."""
        self.pages["https://lint.example.org/VERSION"] = "3.1\n"
        lint = "https://lint.example.org/{version}/lint.tar.gz"
        self.files[lint.replace("{version}", "3.1")] = "lint 3.1"
        self.pages[lint.replace("{version}", "3.1") + ".sha256"] = sha("lint 3.1") + "\n"
        fetch = [{"url": GO.replace("{plat}", "linux-amd64"), "version": "go1.0", "to": "dl/go.tar.gz", "platform": "linux/amd64",
                  "track": {"resolver": "text", "url": "https://dl.example.org/VERSION"}, "found": {"from": "file", "url": "{url}.sha256"}},
                 {"url": lint, "version": "0", "to": "dl/lint.tar.gz", "track": {"resolver": "text", "url": "https://lint.example.org/VERSION"},
                  "found": {"from": "file", "url": "{url}.sha256"}}]
        self.rows.append({"name": "tools", "label": "Tools", "probe": "tools", "about": "Two tools.", "platforms": ["linux/amd64"], "layout": {"bin": ["bin"], "env": {}},
                          "source": {"kind": "command", "run": ["sh", "-c", "tar -xzf {dir}/dl/go.tar.gz -C {dir}"], "fetch": fetch}})
        self.write()
        return lint

    def test_pin_fills_in_the_downloads_a_row_declares_with_no_digest_yet(self):
        self.tools_row()
        # Until then it is nobody's to check or move, and reads as it is.
        rc, out = self.run_tool("check", "tools")
        self.assertEqual((rc, out.splitlines()[0]), (0, "tools: not pinned (dl/go.tar.gz is held to nothing its entry carries: no sha256, and no signature under a key in it)"), out)
        self.assertEqual(self.run_tool("move", "tools")[0], 1)
        rc, out = self.run_tool("pin", "tools")
        self.assertEqual(rc, 0, out)
        got = self.row("tools")["source"]["fetch"]
        self.assertEqual([(f["version"], f["sha256"]) for f in got], [("go1.99.0", sha("go1.99.0 for linux/amd64")), ("3.1", sha("lint 3.1"))])
        self.assertIn(f"tools: dl/go.tar.gz for linux/amd64 pinned at go1.99.0 {sha('go1.99.0 for linux/amd64')[:12]} (stated by ", out)
        self.assertIn("tools: rev 1 to 2; it reads pinned", out)
        self.assertEqual(self.fetched, [], "each digest is its publisher's own statement: nothing was downloaded")
        # Pinned, it is moved and not pinned again.
        self.assertEqual(self.run_tool("pin", "tools"), (1, "pins: tools is left as it was: it is pinned already: tools/pins.py move tools moves it"))

    def test_each_track_moves_by_itself_and_one_that_cannot_be_learned_leaves_the_row(self):
        lint = self.tools_row()
        self.assertEqual(self.run_tool("pin", "tools")[0], 0)
        # One tool has a newer release: it moves, and the other stays.
        self.pages["https://lint.example.org/VERSION"] = "3.2\n"
        self.files[lint.replace("{version}", "3.2")] = "lint 3.2"
        self.pages[lint.replace("{version}", "3.2") + ".sha256"] = sha("lint 3.2") + "\n"
        rc, out = self.run_tool("move", "tools")
        self.assertEqual(rc, 0, out)
        got = self.row("tools")["source"]["fetch"]
        self.assertEqual([(f["version"], f["sha256"]) for f in got], [("go1.99.0", sha("go1.99.0 for linux/amd64")), ("3.2", sha("lint 3.2"))])
        self.assertIn(f"tools: dl/lint.tar.gz 3.1 {sha('lint 3.1')[:12]} to 3.2 {sha('lint 3.2')[:12]}", out)
        self.assertNotIn("dl/go.tar.gz", out, "what did not move is not said to have")
        # Both have one, and one's file is not out: the row moves whole or not at all, and says which.
        self.release("go1.100.0")
        self.pages["https://lint.example.org/VERSION"] = "3.3\n"
        before = self.row("tools")
        rc, out = self.run_tool("move", "tools")
        self.assertEqual((rc, self.row("tools")), (1, before), out)
        self.assertIn("tools: left as it was: dl/lint.tar.gz could not be learned (https://lint.example.org/3.3/lint.tar.gz.sha256 answered 404)", out)


FILES = "https://files.example.org/"
REGISTRY = "https://registry.example.org/"


def wheel(name, data):
    """A wheel as a resolver lists it: its address, and the sha256 its
    index states for it."""
    return {"url": FILES + name, "hashes": {"sha256": sha(data)}}


def integrity(data, algo="sha512"):
    import base64  # noqa: PLC0415
    return f"{algo}-" + base64.b64encode(hashlib.new(algo, data.encode()).digest()).decode()


class Locks(Case):
    """What a package manager installs, held as declared downloads: the
    row says what it asks pip or npm for, a resolver stood in for here
    says which exact files that is, and each becomes a download of the row
    under the lock's directory, with the file the install step reads."""

    AMD, ARM = "x86_64-manylinux_2_28", "aarch64-manylinux_2_28"

    def setUp(self):
        super().setUp()
        self.asked = []
        # What the index holds, by the platform asked for: the wheels that fit it.
        self.index = {
            self.AMD: [{"name": "alpha", "version": "1.0", "wheels": [wheel("alpha-1.0-py3-none-any.whl", "alpha 1.0")]},
                       {"name": "beta", "version": "2.0", "wheels": [wheel("beta-2.0-cp39-abi3-manylinux_2_28_x86_64.whl", "beta abi3"),
                                                                     wheel("beta-2.0-cp312-cp312-manylinux2014_x86_64.manylinux_2_17_x86_64.whl", "beta old"),
                                                                     wheel("beta-2.0-cp312-cp312-manylinux_2_27_x86_64.manylinux_2_28_x86_64.whl", "beta amd")]},
                       {"name": "gamma", "version": "3.0", "wheels": [wheel("gamma-3.0-py3-none-manylinux_2_17_x86_64.whl", "gamma amd")]}],
            self.ARM: [{"name": "alpha", "version": "1.0", "wheels": [wheel("alpha-1.0-py3-none-any.whl", "alpha 1.0")]},
                       {"name": "beta", "version": "2.0", "wheels": [wheel("beta-2.0-cp312-cp312-manylinux_2_28_aarch64.whl", "beta arm")]}],
        }
        self.manifest = {"private": True, "dependencies": {"a": "^1.0.0", "@s/b": "^2.0.0"}}
        self.lock = {"name": "entry", "lockfileVersion": 3, "requires": True, "packages": {
            "": {"dependencies": {"a": "^1.0.0", "@s/b": "^2.0.0"}},
            "node_modules/a": {"version": "1.0.0", "resolved": REGISTRY + "a/-/a-1.0.0.tgz", "integrity": integrity("a 1.0.0"), "bin": {"a": "cli.js"}},
            "node_modules/@s/b": {"version": "2.0.0", "resolved": REGISTRY + "@s/b/-/b-2.0.0.tgz", "integrity": integrity("b 2.0.0")},
            "node_modules/@s/b/node_modules/a": {"version": "0.9.0", "resolved": REGISTRY + "a/-/a-0.9.0.tgz", "integrity": integrity("a 0.9.0", "sha1")},
            "node_modules/watcher": {"version": "4.0.0", "resolved": REGISTRY + "watcher/-/watcher-4.0.0.tgz", "integrity": integrity("watcher"),
                                     "optional": True, "os": ["darwin"]},
            "node_modules/native-linux-x64-musl": {"version": "5.0.0", "resolved": REGISTRY + "native-linux-x64-musl/-/native-linux-x64-musl-5.0.0.tgz",
                                                   "integrity": integrity("native musl"), "optional": True, "os": ["linux"], "cpu": ["x64"], "libc": ["musl"]},
            "node_modules/native-win32": {"version": "5.0.0", "resolved": REGISTRY + "native-win32/-/native-win32-5.0.0.tgz", "integrity": integrity("native win"),
                                          "optional": True, "os": ["win32"]}}}
        for data, url in (("a 1.0.0", "a/-/a-1.0.0.tgz"), ("b 2.0.0", "@s/b/-/b-2.0.0.tgz"), ("a 0.9.0", "a/-/a-0.9.0.tgz"), ("watcher", "watcher/-/watcher-4.0.0.tgz"),
                          ("native musl", "native-linux-x64-musl/-/native-linux-x64-musl-5.0.0.tgz")):
            self.files[REGISTRY + url] = data
        for name, stand_in in (("pip_resolved", self.pip_resolved), ("npm_resolved", self.npm_resolved)):
            p = mock.patch.object(pins, name, stand_in)
            p.start()
            self.addCleanup(p.stop)

    def pip_resolved(self, requirements, python, target):
        self.asked.append((tuple(requirements), python, target))
        return json.loads(json.dumps(self.index[target]))

    def npm_resolved(self, requirements):
        self.asked.append(tuple(requirements))
        return json.loads(json.dumps(self.manifest)), json.loads(json.dumps(self.lock))

    def pip_row(self, **lock):
        """A command that installs what pip resolves, with a download of
        its own beside the lock: written as a person writes it, with no
        file of the lock's yet."""
        logo = "https://dl.example.org/logo.svg"
        self.files[logo] = "a logo"
        self.rows.append({"name": "kit", "label": "Kit", "probe": "kit", "about": "A kit.", "platforms": list(PLATS), "layout": {"bin": ["bin"], "env": {}},
                          "source": {"kind": "command", "run": ["sh", "-c", "pip install --no-index --find-links {dir}/dl/pip -r {dir}/dl/pip/requirements.txt"],
                                     "fetch": [{"url": logo, "sha256": sha("a logo"), "to": "dl/logo.svg"}],
                                     "lock": [{"kind": "pip", "to": "dl/pip", "requirements": ["alpha", "beta>=2"], "python": "3.12",
                                               "for": {"linux/amd64": self.AMD, "linux/arm64": self.ARM}, **lock}]}})
        self.write()

    def test_pin_resolves_a_pip_lock_to_one_wheel_a_package_for_each_platform(self):
        self.pip_row()
        self.assertEqual(self.run_tool("check", "kit")[1].splitlines()[0][:16], "kit: not pinned ")
        rc, out = self.run_tool("pin", "kit")
        self.assertEqual(rc, 0, out)
        self.assertEqual(self.asked, [(("alpha", "beta>=2"), "3.12", self.AMD), (("alpha", "beta>=2"), "3.12", self.ARM)])
        src = self.row("kit")["source"]
        # The row's own download first, as it was; then the lock's: a pure wheel once for every platform, a built one
        # for its platform (the one built for this interpreter and the newest baseline, of the three that fit), and
        # a package only one platform needs for that one alone.
        self.assertEqual([(f["to"], f.get("platform"), f["sha256"]) for f in src["fetch"]], [
            ("dl/logo.svg", None, sha("a logo")),
            ("dl/pip/alpha-1.0-py3-none-any.whl", None, sha("alpha 1.0")),
            ("dl/pip/beta-2.0-cp312-cp312-manylinux_2_27_x86_64.manylinux_2_28_x86_64.whl", "linux/amd64", sha("beta amd")),
            ("dl/pip/beta-2.0-cp312-cp312-manylinux_2_28_aarch64.whl", "linux/arm64", sha("beta arm")),
            ("dl/pip/gamma-3.0-py3-none-manylinux_2_17_x86_64.whl", "linux/amd64", sha("gamma amd"))])
        self.assertEqual(src["fetch"][2]["url"], FILES + "beta-2.0-cp312-cp312-manylinux_2_27_x86_64.manylinux_2_28_x86_64.whl")
        # What the install step requires: each package at its version, with the sha256 of each platform's wheel.
        self.assertEqual(src["files"], {"dl/pip/requirements.txt":
                                        f"alpha==1.0 --hash=sha256:{sha('alpha 1.0')}\n"
                                        + "beta==2.0" + "".join(f" --hash=sha256:{s}" for s in sorted((sha("beta amd"), sha("beta arm")))) + "\n"
                                        + f"gamma==3.0 ; (sys_platform == 'linux' and platform_machine == 'x86_64') --hash=sha256:{sha('gamma amd')}\n"})
        self.assertIn("kit: its pip lock (dl/pip) pinned at 4 file(s)", out)
        self.assertIn("kit: rev 1 to 2; it reads pinned", out)
        self.assertEqual((packformat.source_refused(src), self.fetched), ("", []), "the index states each digest: nothing was downloaded")

    def test_check_says_when_a_lock_would_resolve_otherwise_and_move_replaces_its_set_whole(self):
        self.pip_row()
        self.assertEqual(self.run_tool("pin", "kit")[0], 0)
        rc, out = self.run_tool("check", "kit")
        self.assertEqual(rc, 0, out)
        self.assertIn("kit: its pip lock (dl/pip) is at 4 file(s) (its resolver finds the set it holds)", out)
        # A newer beta for one platform, a package gone, one added.
        self.index[self.AMD][1] = {"name": "beta", "version": "2.1", "wheels": [wheel("beta-2.1-cp312-cp312-manylinux_2_28_x86_64.whl", "beta 2.1 amd")]}
        self.index[self.AMD][2] = {"name": "delta", "version": "0.4", "wheels": [wheel("delta-0.4-py3-none-any.whl", "delta")]}
        before = self.read()
        rc, out = self.run_tool("check", "kit")
        self.assertEqual((rc, self.read()), (3, before), out)
        self.assertIn("kit: its pip lock (dl/pip) 4 file(s) to 4 file(s) (beta 2.0 to 2.1, 2.0; delta 0.4 added; gamma 3.0 gone)", out)
        rc, out = self.run_tool("move", "kit")
        self.assertEqual(rc, 0, out)
        src = self.row("kit")["source"]
        self.assertEqual([(f["to"], f.get("platform")) for f in src["fetch"]], [
            ("dl/logo.svg", None), ("dl/pip/alpha-1.0-py3-none-any.whl", None), ("dl/pip/beta-2.0-cp312-cp312-manylinux_2_28_aarch64.whl", "linux/arm64"),
            ("dl/pip/beta-2.1-cp312-cp312-manylinux_2_28_x86_64.whl", "linux/amd64"), ("dl/pip/delta-0.4-py3-none-any.whl", "linux/amd64")])
        # A version one platform alone is at says which, and the row's own download was left alone.
        self.assertIn("beta==2.1 ; (sys_platform == 'linux' and platform_machine == 'x86_64') --hash=sha256:" + sha("beta 2.1 amd"), src["files"]["dl/pip/requirements.txt"])
        self.assertIn("beta==2.0 ; (sys_platform == 'linux' and platform_machine == 'aarch64') --hash=sha256:" + sha("beta arm"), src["files"]["dl/pip/requirements.txt"])
        self.assertEqual((src["fetch"][0], self.row("kit")["rev"]), ({"url": "https://dl.example.org/logo.svg", "sha256": sha("a logo"), "to": "dl/logo.svg"}, 3))
        self.assertEqual(self.run_tool("check", "kit")[0], 0)

    def test_a_package_with_no_wheel_is_refused_by_name_and_the_row_stays(self):
        self.pip_row()
        self.index[self.ARM].append({"name": "epsilon", "version": "0.1", "sdist": {"url": FILES + "epsilon-0.1.tar.gz", "hashes": {"sha256": sha("src")}}})
        before = self.read()
        rc, out = self.run_tool("pin", "kit")
        self.assertEqual((rc, self.read()), (1, before), out)
        self.assertEqual(out, "pins: kit is left as it was: its pip lock (dl/pip) could not be resolved (epsilon 0.1 has no wheel for linux/arm64: "
                              "a source distribution runs its own code at install, and is not taken)")

    def test_a_wheel_is_picked_for_the_interpreter_then_the_stable_abi_then_the_newest_baseline(self):
        order = ["kit-1-py3-none-any.whl", "kit-1-py3-none-manylinux_2_17_x86_64.whl", "kit-1-cp39-abi3-manylinux_2_28_x86_64.whl",
                 "kit-1-cp311-abi3-manylinux2014_x86_64.manylinux_2_17_x86_64.whl", "kit-1-cp311-abi3-manylinux_2_28_x86_64.whl",
                 "kit-1-cp312-cp312-manylinux1_x86_64.manylinux_2_5_x86_64.whl", "kit-1-cp312-cp312-manylinux2014_x86_64.whl",
                 "kit-1-cp312-cp312-manylinux_2_28_x86_64.whl"]
        self.assertEqual(sorted(reversed(order), key=pins.wheel_rank), order)

    def npm_row(self, platforms=("linux/amd64", "darwin/*")):
        self.rows.append({"name": "srv", "label": "Srv", "probe": "srv", "about": "A server.", "platforms": list(platforms), "layout": {"bin": ["node_modules/.bin"], "env": {}},
                          "source": {"kind": "command", "run": ["sh", "-c", "npm ci --offline --prefix {dir}"],
                                     "lock": [{"kind": "npm", "to": "dl/npm", "requirements": ["a", "@s/b@2"]}]}})
        self.write()

    def test_pin_resolves_an_npm_lock_to_a_tarball_a_package_hashed_here_and_held_to_the_lock(self):
        self.npm_row()
        rc, out = self.run_tool("pin", "srv")
        self.assertEqual(rc, 0, out)
        self.assertEqual(self.asked, [("a", "@s/b@2")])
        src = self.row("srv")["source"]
        # Every package of the lock, a nested one beside the one it shadows; one for another system named for it
        # (a musl build for a musl machine), and one for a system the row does not name left out.
        self.assertEqual([(f["to"], f.get("platform"), f["sha256"], f["url"]) for f in src["fetch"]], [
            ("dl/npm/a-0.9.0.tgz", None, sha("a 0.9.0"), REGISTRY + "a/-/a-0.9.0.tgz"),
            ("dl/npm/a-1.0.0.tgz", None, sha("a 1.0.0"), REGISTRY + "a/-/a-1.0.0.tgz"),
            ("dl/npm/native-linux-x64-musl-5.0.0.tgz", "linux-musl/amd64", sha("native musl"), REGISTRY + "native-linux-x64-musl/-/native-linux-x64-musl-5.0.0.tgz"),
            ("dl/npm/s-b-2.0.0.tgz", None, sha("b 2.0.0"), REGISTRY + "@s/b/-/b-2.0.0.tgz"),
            ("dl/npm/watcher-4.0.0.tgz", "darwin/*", sha("watcher"), REGISTRY + "watcher/-/watcher-4.0.0.tgz")])
        # What npm installs by, carried by the row: the project and its lock, whole.
        self.assertEqual(json.loads(src["files"]["dl/npm/package.json"]), self.manifest)
        self.assertEqual(json.loads(src["files"]["dl/npm/package-lock.json"]), self.lock)
        self.assertEqual((packformat.source_refused(src), packformat.held(self.row("srv"))[0]), ("", "pinned"))
        self.assertEqual(len(self.fetched), 5, "the registry states no sha256: each tarball was downloaded and hashed, once")
        # Held, nothing is downloaded again to say it is as it was.
        self.fetched.clear()
        rc, out = self.run_tool("check", "srv")
        self.assertEqual((rc, self.fetched), (0, []), out)
        self.assertIn("srv: its npm lock (dl/npm) is at 5 file(s)", out)
        # A newer package: only its tarball is fetched, and the set moves whole.
        self.lock["packages"]["node_modules/a"].update(version="1.1.0", resolved=REGISTRY + "a/-/a-1.1.0.tgz", integrity=integrity("a 1.1.0"))
        self.files[REGISTRY + "a/-/a-1.1.0.tgz"] = "a 1.1.0"
        rc, out = self.run_tool("move", "srv")
        self.assertEqual((rc, self.fetched), (0, [REGISTRY + "a/-/a-1.1.0.tgz"]), out)
        self.assertIn("srv: its npm lock (dl/npm) 5 file(s) to 5 file(s) (a 1.0.0 to 1.1.0)", out)
        self.assertEqual([f["to"] for f in self.row("srv")["source"]["fetch"]][:2], ["dl/npm/a-0.9.0.tgz", "dl/npm/a-1.1.0.tgz"])

    def test_a_tarball_that_is_not_what_its_lock_states_is_refused(self):
        self.npm_row()
        self.files[REGISTRY + "@s/b/-/b-2.0.0.tgz"] = "something else"
        before = self.read()
        rc, out = self.run_tool("pin", "srv")
        self.assertEqual((rc, self.read()), (1, before), out)
        self.assertIn("srv is left as it was: its npm lock (dl/npm) could not be resolved (https://registry.example.org/@s/b/-/b-2.0.0.tgz answers a file whose sha512 is", out)

    def test_a_package_of_a_lock_is_for_the_platforms_its_os_cpu_and_libc_name(self):
        every = ["linux/amd64", "linux/arm64", "darwin/*"]
        for pkg, named, want in (({}, every, None),
                                 ({"os": ["darwin"]}, every, ["darwin/*"]),
                                 ({"os": ["darwin"]}, ["linux/*"], []),
                                 ({"os": ["linux"], "cpu": ["x64"], "libc": ["glibc"]}, every, ["linux/amd64"]),
                                 ({"os": ["linux"], "cpu": ["x64"], "libc": ["musl"]}, every, ["linux-musl/amd64"]),
                                 ({"os": ["linux"], "cpu": ["arm64"]}, ["linux/amd64"], []),
                                 ({"os": ["linux"]}, ["linux/*"], ["linux/*"]),
                                 ({"os": ["!win32"]}, ["linux/amd64"], ["linux/amd64"]),
                                 ({"cpu": ["x64"]}, every, ["linux/amd64", "darwin/amd64"]),
                                 ({"os": ["win32"]}, every, [])):
            self.assertEqual(pins.npm_platforms(pkg, named), want, (pkg, named))


class Verify(Case):
    def test_each_pinned_file_is_downloaded_and_held_to_its_pin(self):
        rc, out = self.run_tool("verify", "--all")
        self.assertEqual(rc, 0, out)
        self.assertEqual(sorted(self.fetched), sorted([MOVING, *(go_url("go1.99.0", p) for p in PLATS)]))
        self.assertIn("every one of the 3 pinned file(s) asked for is its pin", out)
        # One platform alone.
        self.fetched.clear()
        rc, out = self.run_tool("verify", "go", "--platform", "linux/arm64")
        self.assertEqual((rc, self.fetched), (0, [go_url("go1.99.0", "linux/arm64")]), out)
        rc, out = self.run_tool("verify", "go", "--platform", "darwin/arm64")
        self.assertEqual(rc, 0, out)
        self.assertIn("go: it names no download for darwin/arm64", out)

    def test_a_file_that_is_not_its_pin_fails_naming_it(self):
        url = go_url("go1.99.0", "linux/arm64")
        self.files[url] = "something else"
        rc, out = self.run_tool("verify", "--all")
        self.assertEqual(rc, 1, out)
        self.assertIn(f"go: NOT ITS PIN: its download for linux/arm64, {url} answers sha256 {sha('something else')}, "
                      f"and the row pins {sha('go1.99.0 for linux/arm64')}", out)
        self.assertIn("1 of 3 pinned file(s) are not their pin", out)
        del self.files[url]
        rc, out = self.run_tool("verify", "go", "--all")
        self.assertEqual(rc, 1, out)
        self.assertIn(f"go: NOT VERIFIED: its download for linux/arm64, {url}: {url} answered 404", out)


class Signed(Case):
    """A row held by its publisher's signature carries the version it
    installs: a signature says who published a file, not which release.
    check says one that carries none, pin gives it the one its resolver
    finds, and move writes a newer one once every platform's file at it
    answers with its signature, or is named in the signed list."""

    def setUp(self):
        super().setUp()
        self.rows += [
            # The download signed itself, a file for every platform.
            {"name": "kit", "label": "Kit", "probe": "kit", "about": "Kit.", "platforms": list(PLATS), "layout": {"bin": ["bin"], "env": {}},
             "source": {"kind": "tarball", "url": {p: GO.replace("{plat}", PLATS[p]) for p in PLATS},
                        "version": {"resolver": "text", "url": "https://dl.example.org/VERSION"},
                        "checksum": {"from": "signature", "sig": "{url}.sig", "keys": "kit.asc"}}},
            # Its list of digests signed.
            {"name": "lst", "label": "List", "probe": "lst", "about": "List.", "platforms": list(PLATS), "layout": {"bin": ["bin"], "env": {}},
             "source": {"kind": "tarball", "url": {p: GO.replace("{plat}", PLATS[p]) for p in PLATS},
                        "version": {"resolver": "text", "url": "https://dl.example.org/VERSION"},
                        "checksum": {"from": "file", "url": "{base}/SUMS", "signed": {"sig": "{base}/SUMS.sig", "keys": "kit.asc"}}}}]
        self.write()
        self.signed("go1.99.0")
        p = mock.patch.object(pins, "answers", self.answers)
        p.start()
        self.addCleanup(p.stop)
        p = mock.patch.object(sdkmeta, "signed_by", lambda data, sig, keys, tc=None: "Kit's release team" if sig == b"good" else sdkmeta.die("no"))
        p.start()
        self.addCleanup(p.stop)

    def signed(self, version, plats=PLATS):
        """`version`'s files each with its signature beside it, and its signed list."""
        self.pages["https://dl.example.org/SUMS"] = "".join(f"{sha(self.files[go_url(version, p)])}  {go_url(version, p).rsplit('/', 1)[-1]}\n"
                                                            for p in PLATS if go_url(version, p) in self.files)
        self.pages["https://dl.example.org/SUMS.sig"] = "good"
        for p in plats:
            self.files[go_url(version, p) + ".sig"] = "a signature"

    def answers(self, url):
        if url not in self.files and url not in self.pages:
            self.gone(url)

    def test_one_with_no_version_is_said_and_pin_gives_it_the_one_its_resolver_finds(self):
        # A signature says who published a file, never which release it is:
        # with no version the row reads open, and once pinned, pinned.
        self.assertEqual(packformat.held(self.row("kit"))[0], "open")
        rc, out = self.run_tool("check")
        self.assertEqual(rc, 3, out)
        for name in ("kit", "lst"):
            self.assertIn(f"{name}: held by its publisher's signature and carrying no version: tools/pins.py pin {name} writes", out)
        for name in ("kit", "lst"):
            rc, out = self.run_tool("pin", name)
            self.assertEqual(rc, 0, out)
            self.assertIn(f"{name}: its version pinned at go1.99.0", out)
            row = self.row(name)
            self.assertEqual((row["source"]["checksum"]["version"], row["rev"], sdkmeta.signed_version(row)), ("go1.99.0", 2, "go1.99.0"))
            self.assertNotIn("sha256", row["source"]["checksum"], "the signature stays the check")
            self.assertEqual(packformat.held(row)[0], "pinned")
        rc, out = self.run_tool("check")
        self.assertEqual(rc, 0, out)
        self.assertIn("kit: its version is at go1.99.0 (its resolver finds the version it carries)", out)
        self.assertEqual(self.run_tool("pin", "kit")[0], 1, "pinned already: move moves it")

    def test_move_writes_a_newer_version_once_every_platform_is_signed(self):
        for name in ("kit", "lst"):
            self.run_tool("pin", name)
        self.release("go1.100.0")
        # Not out signed for arm64 yet: both rows wait, said, and nothing moves.
        self.signed("go1.100.0", ["linux/amd64"])
        self.pages["https://dl.example.org/SUMS"] = self.pages["https://dl.example.org/SUMS"].splitlines(True)[0] + "0" * 64 + "  other.tar.gz\n"
        rc, out = self.run_tool("check", "kit", "lst")
        self.assertEqual(rc, 0, out)
        self.assertIn("kit: its version is at go1.99.0 (its resolver finds go1.100.0, and linux/arm64 could not be learned", out)
        self.assertIn("lst: its version is at go1.99.0 (its resolver finds go1.100.0, and linux/arm64 could not be learned", out)
        before = self.read()
        self.assertEqual(self.run_tool("move", "kit", "lst")[0], 1)
        self.assertEqual(self.read(), before, "a row moves whole")
        # Out for both: the version moves and nothing else of the row.
        self.signed("go1.100.0")
        rc, out = self.run_tool("move", "kit", "lst")
        self.assertEqual(rc, 0, out)
        self.assertIn("kit: its version go1.99.0 to go1.100.0", out)
        for name in ("kit", "lst"):
            self.assertEqual((self.row(name)["source"]["checksum"]["version"], self.row(name)["rev"]), ("go1.100.0", 3))
        self.assertEqual(self.fetched, [], "nothing is downloaded whole to move a signed row")
        # A list whose signature does not hold is not moved to.
        self.release("go1.101.0")
        self.signed("go1.101.0")
        self.pages["https://dl.example.org/SUMS.sig"] = "forged"
        rc, out = self.run_tool("move", "lst")
        self.assertEqual((rc, self.row("lst")["source"]["checksum"]["version"]), (1, "go1.100.0"), out)
        rc, out = self.run_tool("verify", "kit")
        self.assertIn("kit: its download at go1.100.0 is held by its publisher's signature, which an install checks", out)

    def test_every_shipped_signed_row_carries_its_version(self):
        for row in pins.table(pins.load(pins.TABLE)):
            if pins.signed_row(row) and not sdkmeta.pin_of(row):
                self.assertTrue(sdkmeta.signed_version(row), f"{row['name']} reads pinned and carries no version")
                self.assertTrue(pins.is_pinned(row), row["name"])


class Agents(Case):
    """The coding agents' install recipes are rows of the tool too, read
    from the one file that holds them and written back there: an installer
    with a version in its address, a program a platform, a vendor's one
    moving script, and a recipe of the older form, which pins nothing."""

    INSTALL = "https://dl.example.org/{version}/install.sh"
    PROG = "https://dl.example.org/{version}/kite-{plat}.tar.gz"
    SCRIPT = "https://get.example.org/kite/install.sh"
    TRACK = {"resolver": "text", "url": "https://dl.example.org/KITE"}

    def setUp(self):
        super().setUp()
        self.recipes = os.path.join(self.d, "agent-recipes.json")
        self.out("1.4.0")
        self.files[self.SCRIPT] = "a moving installer, as first pinned"
        rest = {"pin": None, "env": {}, "bin": ".local/bin/kite", "also": [], "fresh": ""}
        pins.save(self.recipes, {"recipes": {
            # Its vendor's installer as each release carries it, its sha256 stated beside it.
            "kite": {"rev": 2, "fetch": [{"url": self.INSTALL, "version": "1.4.0", "sha256": sha(self.files[self.INSTALL.format(version="1.4.0")]), "to": "dl/install.sh",
                                          "track": self.TRACK, "found": {"from": "file", "url": "{url}.sha256"}}],
                     "online": "Its installer downloads the build for this machine from dl.example.org.", "steps": [["sh", "{dir}/dl/install.sh"]],
                     **rest, "pin": ["KITE_VERSION", "{v}"]},
            # The program itself, a file a platform, its vendor stating no digest.
            "wren": {"rev": 5, "fetch": [{"url": self.PROG.replace("{plat}", PLATS[p]), "version": "1.4.0", "sha256": sha(self.files[self.prog("1.4.0", p)]),
                                          "to": "dl/kite.tar.gz", "platform": p, "track": self.TRACK} for p in PLATS],
                     "steps": [["mkdir", "-p", "{home}/.local/bin"], ["tar", "-xzf", "{dir}/dl/kite.tar.gz", "-C", "{home}/.local/bin"]], **rest},
            # A vendor's one moving script: no version, nothing to track.
            "lark": {"rev": 1, "fetch": [{"url": self.SCRIPT, "sha256": sha(self.files[self.SCRIPT]), "to": "dl/install.sh"}],
                     "online": "Its installer downloads the rest from get.example.org.", "steps": [["bash", "{dir}/dl/install.sh"]], **rest},
            # The older form: a vendor's installer handed to a shell as it arrives.
            "pipit": {"rev": 1, "script": "curl -fsSL https://get.example.org/pipit | bash", **rest},
        }})

    def prog(self, version, plat):
        return self.PROG.format(version=version, plat=PLATS[plat])

    def out(self, version):
        """The vendor publishes `version`: its installer with its sha256
        beside it, and its program for each platform."""
        self.pages[self.TRACK["url"]] = version + "\n"
        url = self.INSTALL.format(version=version)
        self.files[url] = f"the installer of {version}"
        self.pages[url + ".sha256"] = f"{sha(self.files[url])}  install.sh\n"
        for plat in PLATS:
            self.files[self.prog(version, plat)] = f"kite {version} for {plat}"

    def run_tool(self, *argv):
        said = []
        rc = pins.main([*argv, "--file", self.table, "--agents", self.recipes], out=said.append)
        return rc, "\n".join(said)

    def recipe(self, name):
        with open(self.recipes, encoding="utf-8") as f:
            return json.load(f)["recipes"][name]

    def test_check_asks_each_recipe_by_its_own_data_and_writes_nothing(self):
        with open(self.recipes, encoding="utf-8") as f:
            before = f.read()
        rc, out = self.run_tool("check")
        self.assertEqual(rc, 0, out)
        self.assertIn("kite: dl/install.sh is at 1.4.0 " + sha(self.files[self.INSTALL.format(version="1.4.0")])[:12] + " (its track finds the version it is pinned to)", out)
        self.assertIn("wren: dl/kite.tar.gz for linux/arm64 is at 1.4.0", out)
        self.assertIn("lark: dl/install.sh is at " + sha(self.files[self.SCRIPT])[:12], out)
        self.assertNotIn("pipit", out, "a recipe that pins nothing is not asked about, unless it is named")
        # A file with a version is not downloaded to be checked; the moving script is asked for its bytes.
        self.assertEqual([u for u in self.fetched if "kite" in u], [self.SCRIPT])
        with open(self.recipes, encoding="utf-8") as f:
            self.assertEqual(f.read(), before)
        rc, out = self.run_tool("check", "pipit")
        self.assertEqual((rc, out.splitlines()[0]), (0, f"pipit: not pinned ({packformat.PIPED_SAID})"))
        # The table's rows are asked beside them, as before.
        self.assertIn("go: its download is at go1.99.0", self.run_tool("check")[1])

    def test_move_writes_the_new_pin_into_the_recipes_and_leaves_the_table(self):
        table = self.read()
        self.out("1.5.0")
        rc, out = self.run_tool("check", "kite", "wren", "lark")
        self.assertEqual(rc, 3, out)
        self.assertIn("2 row(s) would move", out)
        rc, out = self.run_tool("move", "kite", "wren")
        self.assertEqual(rc, 0, out)
        kite, wren = self.recipe("kite"), self.recipe("wren")
        new = self.INSTALL.format(version="1.5.0")
        self.assertEqual((kite["rev"], kite["fetch"][0]["version"], kite["fetch"][0]["sha256"]), (3, "1.5.0", sha(self.files[new])))
        self.assertIn(f"stated by {new}.sha256", out, "its publisher's own statement, with nothing downloaded")
        self.assertNotIn(new, self.fetched)
        # The address keeps its {version}, and everything a node reads beside the pin is as it was.
        self.assertEqual((kite["fetch"][0]["url"], kite["steps"], kite["online"][:13], kite["pin"]), (self.INSTALL, [["sh", "{dir}/dl/install.sh"]], "Its installer", ["KITE_VERSION", "{v}"]))
        # A program a platform moves as one set: its vendor states no digest, so each file is hashed here.
        self.assertEqual((wren["rev"], [(f["platform"], f["version"], f["sha256"]) for f in wren["fetch"]]),
                         (6, [(p, "1.5.0", sha(self.files[self.prog("1.5.0", p)])) for p in PLATS]))
        self.assertIn("downloaded and hashed here", out)
        self.assertEqual(self.recipe("lark")["rev"], 1, "a recipe that was not named is left alone")
        self.assertEqual(self.read(), table, "no row of the table moved, so the table is not written")
        self.assertEqual(self.run_tool("check")[0], 0)

    def test_a_moving_script_that_changed_is_said_and_re_pinned(self):
        self.files[self.SCRIPT] = "a moving installer, edited by its vendor"
        rc, out = self.run_tool("check", "lark")
        self.assertEqual(rc, 3, out)
        self.assertIn("lark: dl/install.sh " + sha("a moving installer, as first pinned")[:12] + " to " + sha(self.files[self.SCRIPT])[:12], out)
        rc, out = self.run_tool("verify", "lark")
        self.assertEqual(rc, 1, out)
        self.assertIn(f"lark: NOT ITS PIN: dl/install.sh, {self.SCRIPT} answers sha256 {sha(self.files[self.SCRIPT])}", out)
        rc, out = self.run_tool("move", "lark")
        self.assertEqual(rc, 0, out)
        self.assertEqual((self.recipe("lark")["rev"], self.recipe("lark")["fetch"][0]["sha256"]), (2, sha(self.files[self.SCRIPT])))
        self.assertEqual(self.run_tool("verify", "lark")[0], 0)

    def test_verify_holds_each_recipe_s_file_for_a_platform_to_its_pin(self):
        rc, out = self.run_tool("verify", "kite", "wren", "--platform", "linux/arm64")
        self.assertEqual(rc, 0, out)
        self.assertIn("kite: dl/install.sh is its pin", out)
        self.assertIn("wren: dl/kite.tar.gz for linux/arm64 is its pin", out)
        self.assertNotIn("linux/amd64", out)
        self.assertIn("every one of the 2 pinned file(s) asked for is its pin", out)

    def test_the_shipped_recipes_are_the_rows_beside_the_shipped_table(self):
        # With no file named: the one copy the agent table reads, each
        # under the name its row in the Library has.
        import agents  # noqa: PLC0415
        doc = pins.load(pins.AGENTS)
        self.assertEqual(doc["recipes"], {a.id: a.install for a in agents.TABLE})
        rows = pins.agent_rows(doc["recipes"])
        self.assertEqual([r["name"] for r in rows], [a.tool for a in agents.TABLE])
        self.assertTrue(all(pins.is_pinned(r) for r in rows), "every shipped recipe holds what it fetches")
        self.assertEqual(sorted(packformat.held(r)[0] for r in rows), sorted(packformat.agent_held(a.install)["word"] for a in agents.TABLE))


class Asks(unittest.TestCase):
    def test_it_names_no_vendor_and_leaves_sdkmeta_as_it_found_it(self):
        with open(os.path.join(REPO, "tools", "pins.py"), encoding="utf-8") as f:
            text = f.read().lower()
        with open(os.path.join(REPO, "config", "toolchains.json"), encoding="utf-8") as f:
            rows = json.load(f)["toolchains"]
        hosts = {h for r in rows for h in [sdkmeta.source_host(r)] if h}
        makers = {str(r.get("maker") or "").lower() for r in rows} - {"", "aerieos"}
        self.assertEqual(sorted(w for w in hosts | makers if w in text), [],
                         "the tool reads a row's own data: no row's host or maker is written in it")
        die, plat = sdkmeta.die, sdkmeta.AS_PLATFORM
        with pins.As("linux/arm64"):
            self.assertEqual(sdkmeta.AS_PLATFORM, "linux/arm64")
            with self.assertRaises(pins.Refused):
                sdkmeta.die("it cannot be read")
        self.assertEqual((sdkmeta.die, sdkmeta.AS_PLATFORM), (die, plat))


if __name__ == "__main__":
    unittest.main()
