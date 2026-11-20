"""The CI runners' pins (scripts/dashboard/runner-pins.json): one table that
says, for each runner a node installs, the version and the sha256 of the
exact file for every platform, written as a toolchain's pinned source is so
tools/pins.py moves it. The tool over a made-up table that lists its rows
under `runners`, with the network stood in for; and the shipped table
itself, read for what an install depends on."""
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

spec = importlib.util.spec_from_file_location("pins_tool_runners", os.path.join(REPO, "tools", "pins.py"))
pins = importlib.util.module_from_spec(spec)
spec.loader.exec_module(pins)

SHIPPED = os.path.join(REPO, "scripts", "dashboard", "runner-pins.json")
ARCHIVE = "https://ci.example.org/dl/v{version}/runner-{plat}-{version}.tar.gz"
PROGRAM = "https://forge.example.org/dl/v{version}/runner-{version}-{plat}"
PLATS = ("linux/amd64", "linux/arm64")


def sha(data):
    return hashlib.sha256(data.encode()).hexdigest()


def address(template, version, plat):
    return template.format(version=version, plat=plat.replace("/", "-"))


class ToolOverRunners(unittest.TestCase):
    """tools/pins.py --file over a table whose rows are under `runners`."""

    def setUp(self):
        self.d = tempfile.mkdtemp()
        self.addCleanup(shutil.rmtree, self.d, True)
        self.table = os.path.join(self.d, "runner-pins.json")
        self.pages, self.files, self.fetched = {}, {}, []
        self.release("3.1.0")
        self.rows = [
            # An archive, the newest version read off an API's answer, each digest in a list beside the files.
            {"name": "ci", "rev": 1,
             "source": {"kind": "tarball", "url": {p: ARCHIVE.replace("{plat}", p.replace("/", "-")) for p in PLATS},
                        "version": {"resolver": "match", "url": "https://ci.example.org/api/latest", "match": '"tag_name":\\s*"v([0-9.]+)"'},
                        "checksum": {"from": "pin", "version": "3.1.0", "sha256": {p: sha(self.files[address(ARCHIVE, "3.1.0", p)]) for p in PLATS},
                                     "found": {"from": "file", "url": "{base}/checksums.txt"}}}},
            # A program that is the file itself, not pinned yet.
            {"name": "forge",
             "source": {"kind": "script", "url": {p: PROGRAM.replace("{plat}", p.replace("/", "-")) for p in PLATS},
                        "version": {"resolver": "match", "url": "https://ci.example.org/api/latest", "match": '"tag_name":\\s*"v([0-9.]+)"'},
                        "checksum": {"from": "file", "url": "{base}/checksums.txt"}}},
        ]
        pins.save(self.table, {"_comment": "a table of made-up runners", "runners": self.rows})
        for target, name, stand_in in ((sdkmeta, "get", self.get), (pins, "hashed", self.hashed),
                                       (sdkmeta, "final_url", mock.Mock(side_effect=AssertionError("asked for a redirect")))):
            p = mock.patch.object(target, name, stand_in)
            p.start()
            self.addCleanup(p.stop)

    def release(self, version):
        """The publishers put `version` out: each file, and one list of digests beside them."""
        self.pages["https://ci.example.org/api/latest"] = json.dumps({"id": 7, "tag_name": "v" + version})
        for template in (ARCHIVE, PROGRAM):
            listed = []
            for plat in PLATS:
                url = address(template, version, plat)
                self.files[url] = f"{url} as published"
                listed.append(f"{sha(self.files[url])}  {url.rsplit('/', 1)[-1]}")
            self.pages[url.rsplit("/", 1)[0] + "/checksums.txt"] = "\n".join(listed) + "\n"

    def gone(self, url):
        e = urllib.error.HTTPError(url, 404, "Not Found", None, None)
        e.close()
        raise e

    def get(self, url, decode=True):
        if url not in self.pages:
            self.gone(url)
        return self.pages[url] if decode else self.pages[url].encode()

    def hashed(self, url, also=""):
        self.fetched.append(url)
        if url not in self.files:
            self.gone(url)
        return {"sha256": sha(self.files[url]), "bytes": len(self.files[url])}

    def doc(self):
        with open(self.table, encoding="utf-8") as f:
            return json.load(f)

    def row(self, name):
        return next(r for r in self.doc()["runners"] if r["name"] == name)

    def run_tool(self, *argv):
        said = []
        rc = pins.main([*argv, "--file", self.table], out=said.append)
        return rc, "\n".join(said)

    def test_check_reads_the_rows_and_writes_nothing(self):
        with open(self.table, encoding="utf-8") as f:
            before = f.read()
        rc, out = self.run_tool("check")
        self.assertEqual(rc, 0, out)
        self.assertIn("ci: its download is at 3.1.0 (its resolver finds the version it is pinned to)", out)
        self.assertNotIn("forge", out, "a row that is not pinned is not asked about, unless it is named")
        self.release("3.2.0")
        rc, out = self.run_tool("check")
        self.assertEqual(rc, 3, out)
        self.assertIn("ci: its download 3.1.0 to 3.2.0", out)
        for plat in PLATS:
            url = address(ARCHIVE, "3.2.0", plat)
            self.assertIn(f"    {plat}  sha256 {sha(self.files[url])}  stated by https://ci.example.org/dl/v3.2.0/checksums.txt", out)
        with open(self.table, encoding="utf-8") as f:
            self.assertEqual(f.read(), before)
        self.assertEqual(self.fetched, [], "where the publisher states a sha256, nothing is downloaded")

    def test_move_writes_the_version_and_every_platforms_digest_and_keeps_the_rest(self):
        self.release("3.2.0")
        rc, out = self.run_tool("move", "ci")
        self.assertEqual(rc, 0, out)
        self.assertIn("ci: rev 1 to 2", out)
        doc = self.doc()
        self.assertEqual(list(doc), ["_comment", "runners"], "the table is saved under the name it listed its rows by, and nothing of the tool's own")
        ck = self.row("ci")["source"]["checksum"]
        self.assertEqual(ck["version"], "3.2.0")
        self.assertEqual(ck["sha256"], {p: sha(self.files[address(ARCHIVE, "3.2.0", p)]) for p in PLATS})
        self.assertEqual(ck["found"], {"from": "file", "url": "{base}/checksums.txt"})
        self.assertEqual(self.row("forge"), self.rows[1], "the row beside it is as it was")

    def test_a_release_that_is_not_out_for_every_platform_moves_nothing(self):
        self.release("3.2.0")
        base = "https://ci.example.org/dl/v3.2.0/checksums.txt"
        # arm64's file is not out yet: the list states amd64's digest and the notes'.
        self.pages[base] = self.pages[base].splitlines()[0] + f"\n{sha('notes')}  NOTES.txt\n"
        del self.files[address(ARCHIVE, "3.2.0", "linux/arm64")]
        rc, out = self.run_tool("move", "ci")
        self.assertEqual(rc, 1, out)
        self.assertIn("ci: left as it was", out)
        self.assertEqual(self.row("ci"), self.rows[0])

    def test_pin_turns_an_origin_checked_runner_into_a_pinned_one(self):
        rc, out = self.run_tool("pin", "forge")
        self.assertEqual(rc, 0, out)
        self.assertIn("forge: its download pinned at 3.1.0", out)
        self.assertIn("it reads pinned", out)
        ck = self.row("forge")["source"]["checksum"]
        self.assertEqual((ck["from"], ck["version"]), ("pin", "3.1.0"))
        self.assertEqual(ck["sha256"], {p: sha(self.files[address(PROGRAM, "3.1.0", p)]) for p in PLATS})
        self.assertEqual(ck["found"], {"from": "file", "url": "{base}/checksums.txt"}, "how the next one is learned stays in the row")
        self.assertEqual(packformat.pin_refused(ck), "")

    def test_verify_names_a_file_that_is_not_its_pin(self):
        rc, out = self.run_tool("verify", "--all")
        self.assertEqual(rc, 0, out)
        self.assertIn("every one of the 2 pinned file(s) asked for is its pin", out)
        url = address(ARCHIVE, "3.1.0", "linux/arm64")
        self.files[url] = "another file at the same address"
        rc, out = self.run_tool("verify", "--all")
        self.assertEqual(rc, 1, out)
        self.assertIn(f"ci: NOT ITS PIN: its download for linux/arm64, {url} answers sha256 {sha(self.files[url])}, and the row pins "
                      f"{self.rows[0]['source']['checksum']['sha256']['linux/arm64']}", out)

    def test_a_name_the_table_lacks_and_a_file_that_is_no_table_are_said(self):
        self.assertEqual(self.run_tool("check", "nope"), (1, "pins: no runner named nope in the table"))
        with open(self.table, "w", encoding="utf-8") as f:
            json.dump({"rows": []}, f)
        rc, out = self.run_tool("check")
        self.assertEqual(rc, 1)
        self.assertIn("it has no list of toolchains or runners", out)


class ShippedTable(unittest.TestCase):
    """The table AerieOS ships: what an install of a runner depends on."""

    def setUp(self):
        with open(SHIPPED, encoding="utf-8") as f:
            self.text = f.read()
        self.doc = json.loads(self.text)
        self.rows = {r["name"]: r for r in self.doc["runners"]}

    def test_it_is_laid_out_as_the_tool_saves_it(self):
        self.assertEqual(json.dumps(self.doc, indent=2, ensure_ascii=False) + "\n", self.text, "a move's diff is then the lines that changed")

    def test_each_kind_of_git_host_a_runner_registers_with_has_a_row(self):
        # nodes.node_runner takes these two, and the row is looked up by that word.
        self.assertEqual(sorted(self.rows), ["gitea", "github"])

    def test_every_row_is_a_whole_pin_for_every_platform_it_offers(self):
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
                self.assertRegex(url, r"^https://(github\.com|gitea\.com)/[A-Za-z0-9._/{}-]+$", f"{name} {plat}")
                self.assertIn("{version}", url, f"{name} {plat}: the address names the version, so a pin is one release's file")
            self.assertEqual(packformat.track_refused(src["version"], "source.version"), "", name)
            self.assertEqual(packformat.found_refused(ck["found"]), "", name)
        self.assertEqual(sorted(self.rows["github"]["source"]["url"]), ["darwin/amd64", "darwin/arm64", "linux/amd64", "linux/arm64"])
        self.assertEqual(sorted(self.rows["gitea"]["source"]["url"]), ["linux/amd64", "linux/arm64"])

    def test_the_tool_reads_it_as_a_table(self):
        with mock.patch.dict(pins.VERBS, {"check": lambda doc, names, opts, out: out(",".join(r["name"] for r in pins.chosen(doc, names))) or 0}):
            said = []
            self.assertEqual(pins.main(["check", "--file", SHIPPED], out=said.append), 0, said)
        self.assertEqual(said, ["github,gitea"])


if __name__ == "__main__":
    unittest.main()
