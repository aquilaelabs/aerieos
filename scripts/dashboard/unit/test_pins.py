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
