"""What an entry's downloads are held to (pack format 5; the operator, 20
Nov: everything AerieOS installs from somewhere else is held to something,
by one mechanism of the pack format that works the same for a row it ships
and for anybody's pack). A manifest's declared downloads take a platform
and a publisher's signature, the pack carries the key, and an installer
that downloads the rest says so in a sentence; a shipped row's source takes
the same shapes; and one function reads an entry and answers one of three
words: pinned, installer or open, with why."""
import copy
import json
import os
import sys
import unittest
from pathlib import Path
from unittest import mock

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))
import catalogrows  # noqa: E402
import packformat  # noqa: E402
import toolpacks  # noqa: E402

ROOT = Path(__file__).resolve().parents[3]
KEPT = Path(__file__).parent / "packformat"
H = "ab" * 32
KEY = json.loads((KEPT / "5" / "tern.json").read_text())["install"]["keyring"]["tern.asc"]
SENTENCE = "Its installer downloads the compiler from releases.example.org."
# Where the rows AerieOS ships stand: the ones whose every download is held
# to something the row carries, and the ones whose pinned installer
# downloads the rest. Every other row reads open, and waits for its pin.
SHIPPED_PINNED = ["ffmpeg", "go", "jdk", "node", "swift", "zig"]
SHIPPED_INSTALLER = []


def kept(n, name):
    return json.loads((KEPT / str(n) / f"{name}.json").read_text())


def manifest(**install):
    m = kept(5, "quill")
    m["install"] = {**m["install"], **install}
    return m


def errors_of(m, **kw):
    return toolpacks.validate(m, **kw)[1]


class Manifest(unittest.TestCase):
    def test_the_kept_manifests_of_format_5_use_each_new_part(self):
        self.assertEqual(packformat.FORMAT, 5)
        self.assertEqual(packformat.VERSION, "5.2")
        quill, _ = toolpacks.validate(kept(5, "quill"))
        self.assertEqual([(f["to"], f.get("platform")) for f in quill["fetch"]],
                         [("dl/quill.tar.gz", "linux/amd64"), ("dl/quill.tar.gz", "linux/arm64"), ("dl/rules.tar.gz", None)])
        tern, _ = toolpacks.validate(kept(5, "tern"))
        self.assertEqual(tern["fetch"], [{"url": "https://downloads.tern.example.org/2.4.0/tern-2.4.0-linux.tar.xz", "sha256": "", "to": "dl/tern.tar.xz",
                                          "signed": {"sig": "https://downloads.tern.example.org/2.4.0/tern-2.4.0-linux.tar.xz.sig", "keys": "tern.asc"}}])
        self.assertEqual(list(tern["keyring"]), ["tern.asc"])
        self.assertEqual(tern["touches"]["hosts"], ["downloads.tern.example.org"], "the host of a download and of its signature are its touches")
        kestrel, _ = toolpacks.validate(kept(5, "kestrel"))
        self.assertTrue(kestrel["online"].startswith("Its installer, kestrel-up, downloads the compiler"))
        self.assertEqual(sorted(kestrel["touches"]["hosts"]), ["get.kestrel.example.org", "releases.kestrel.example.org"])
        osprey, errors = toolpacks.validate(kept(5, "osprey"), official=True)
        self.assertEqual((errors, osprey["shipped"]["source"]["checksum"]["from"]), ([], "pin"))

    def test_a_manifest_from_before_is_kept_as_it_was(self):
        got, errors = toolpacks.validate(kept(3, "hexkit"))
        self.assertEqual(errors, [])
        self.assertTrue("keyring" not in got and "online" not in got)
        self.assertEqual(sorted(got["fetch"][0]), ["sha256", "to", "url"])

    def test_what_is_new_says_format_5(self):
        for n, part in ((3, "install.fetch's platform"), (4, "install.fetch's platform")):
            m = dict(kept(5, "quill"), format=n, framework=f"{n}.2")
            self.assertEqual(errors_of(m), [f'{part} is pack format 5\'s: the manifest says "format": 5'], n)
        m = dict(kept(5, "tern"), format=3, framework="3.2")
        self.assertEqual(errors_of(m), ['install.fetch\'s signed, install.keyring are pack format 5\'s: the manifest says "format": 5'])
        m = dict(kept(5, "kestrel"), format=4, framework="4.2")
        self.assertEqual(errors_of(m), ['install.online is pack format 5\'s: the manifest says "format": 5'])
        # An official pack's recipe is held to the number as a pack is.
        m = dict(kept(5, "osprey"), format=4, framework="4.2")
        self.assertEqual(errors_of(m, official=True), ['what shipped.source says of its downloads is pack format 5\'s: the manifest says "format": 5'])

    def test_a_download_is_held_by_exactly_one_of_a_sha256_and_a_signature(self):
        good = {"url": "https://example.com/a.tgz", "to": "dl/a.tgz"}
        signed = {"sig": "https://example.com/a.tgz.sig", "keys": "pub.asc"}
        ring = {"pub.asc": KEY}
        self.assertEqual(errors_of(manifest(fetch=[{**good, "signed": signed}], keyring=ring)), [])
        self.assertEqual(errors_of(manifest(fetch=[{**good, "sha256": H}])), [])
        for bad in ({**good}, {**good, "sha256": H, "signed": signed}, {**good, "signed": {"sig": signed["sig"]}},
                    {**good, "signed": {**signed, "sig": "http://example.com/a.sig"}}, {**good, "signed": {**signed, "keys": "../pub.asc"}},
                    {**good, "signed": {**signed, "also": 1}}, {**good, "signed": "pub.asc"}):
            got = errors_of(manifest(fetch=[bad], keyring=ring))
            self.assertTrue(any(e.startswith("install.fetch 1 is {url, sha256, to}") for e in got), (bad, got))

    def test_a_pack_carries_the_key_its_download_is_checked_with(self):
        f = [{"url": "https://example.com/a.tgz", "to": "dl/a.tgz", "signed": {"sig": "https://example.com/a.tgz.sig", "keys": "pub.asc"}}]
        self.assertEqual(errors_of(manifest(fetch=f)), ["install.fetch's dl/a.tgz is signed under pub.asc, which install.keyring does not carry: "
                                                          "a pack carries the public key its download is checked with"])
        self.assertEqual(errors_of(manifest(fetch=f, keyring={"other.asc": KEY})), ["install.fetch's dl/a.tgz is signed under pub.asc, which install.keyring does not carry: "
                                                                                   "a pack carries the public key its download is checked with"])
        for bad in ({}, {"pub.asc": "not a key"}, {"pub.asc": KEY[:-40]}, {"../pub.asc": KEY}, {"pub.asc": 7}, [KEY],
                    {f"k{i}.asc": KEY for i in range(packformat.KEYRING_MOST + 1)},
                    {"pub.asc": KEY.replace("=RHfr", "A" * (packformat.KEY_MAX + 1))}):
            got = errors_of(manifest(keyring=bad))
            self.assertTrue(any(e.startswith(f"install.keyring maps up to {packformat.KEYRING_MOST} plain file names") for e in got), (str(bad)[:60], got))

    def test_a_platform_is_one_aerieos_names_and_a_file_is_kept_once_for_a_machine(self):
        a = {"url": "https://example.com/a.tgz", "sha256": H, "to": "dl/a.tgz"}
        for plats in (("linux/amd64", "linux/arm64"), ("linux/*", "darwin/*"), ("linux/amd64", "darwin/amd64")):
            self.assertEqual(errors_of(manifest(fetch=[{**a, "platform": plats[0]}, {**a, "platform": plats[1]}])), [], plats)
        for plats in (("linux/amd64", "linux/amd64"), ("linux/*", "linux/arm64"), ("linux/amd64", None), (None, None)):
            rows = [{**a, **({"platform": p} if p else {})} for p in plats]
            self.assertTrue(any(e.startswith("install.fetch 2 is") for e in errors_of(manifest(fetch=rows))), plats)
        for bad in ("linux", "plan9/amd64", "*", "linux/x86_64", 7):
            self.assertTrue(any(e.startswith("install.fetch 1 is") for e in errors_of(manifest(fetch=[{**a, "platform": bad}]))), bad)

    def test_online_is_one_sentence(self):
        self.assertEqual(errors_of(manifest(online=SENTENCE)), [])
        for bad in ("", "short", "x" * (packformat.ONLINE_MAX + 1), "It runs <script>alert(1)</script> for you.", 7, ["a sentence in a list"], True):
            got = errors_of(manifest(online=bad))
            self.assertTrue(any(e.startswith("install.online is one sentence") for e in got), (bad, got))
        got, _ = toolpacks.validate(manifest(online="  Its installer\n downloads   the rest from example.org.  "))
        self.assertEqual(got["online"], "Its installer downloads the rest from example.org.", "kept as one line")

    def test_an_empty_list_declares_that_it_downloads_nothing_from_format_5(self):
        wren = kept(5, "wren")
        self.assertEqual(wren["install"]["fetch"], [])
        got, errors = toolpacks.validate(wren)
        self.assertEqual((errors, got["fetch"], got["offline"]), ([], [], True))
        row = toolpacks.recipe({"manifest": got, "url": "https://example.com/wren", "commit": "c" * 40})
        self.assertTrue(row["source"]["offline"] is True and "fetch" not in row["source"], "its steps are cut, with nothing to fetch first")
        for doc in (wren, got, row):
            self.assertEqual(packformat.held(doc), ("pinned", packformat.PINNED_SAID))
        # Before format 5 an empty list declared nothing, and means what it meant.
        for n in (3, 4):
            old = dict(wren, format=n, framework=f"{n}.2")
            got, errors = toolpacks.validate(old)
            self.assertEqual((errors, "offline" in got), ([], False), n)
            row = toolpacks.recipe({"manifest": got, "url": "https://example.com/wren", "commit": "c" * 40})
            self.assertNotIn("offline", row["source"], n)
            for doc in (old, got, row):
                self.assertEqual(packformat.held(doc)[0], "open", n)
        # One that says nothing of its downloads at format 5 is as it was too.
        plain = copy.deepcopy(wren)
        del plain["install"]["fetch"]
        self.assertEqual((packformat.declares_none(plain), packformat.held(plain)[0], "offline" in toolpacks.validate(plain)[0]), (False, "open", False))
        # ...and an installer that downloads the rest keeps the network, whatever else it declares.
        both = copy.deepcopy(wren)
        both["install"]["online"] = SENTENCE
        got, errors = toolpacks.validate(both)
        src = toolpacks.recipe({"manifest": got, "url": "https://example.com/wren", "commit": "c" * 40})["source"]
        self.assertEqual((errors, src["online"], "offline" in src, packformat.held(both)), ([], SENTENCE, False, ("installer", SENTENCE)))

    def test_a_download_says_the_version_it_is_and_how_a_newer_one_is_found(self):
        # The kept manifest: two platforms' files that move together, one
        # held by a signature, and one with no version at all.
        heron, errors = toolpacks.validate(kept(5, "heron"))
        self.assertEqual(errors, [])
        self.assertEqual([(f.get("version"), (f.get("track") or {}).get("resolver"), (f.get("found") or {}).get("from")) for f in heron["fetch"]],
                         [("2.7.1", "github-release", "github-asset"), ("2.7.1", "github-release", "github-asset"), ("2026.10", "match", None), (None, None, None)])
        # What is fetched is the address with its own version filled in: on the page, and in the row a node is handed.
        said = packformat.downloads_said(heron["fetch"])
        self.assertEqual([d["url"] for d in said][:3], ["https://github.com/heron-schema/heron/releases/download/v2.7.1/heron-2.7.1-linux-x64.tar.gz",
                                                        "https://github.com/heron-schema/heron/releases/download/v2.7.1/heron-2.7.1-linux-arm64.tar.gz",
                                                        "https://schemas.heron.example.org/std/2026.10/std.tar.gz"])
        self.assertEqual(said[2]["sig"], "https://schemas.heron.example.org/std/2026.10/std.tar.gz.sig")
        self.assertTrue(all(sorted(d) == ["held", "keys", "platform", "sha256", "sig", "to", "url"] for d in said), "the same seven keys")
        row = toolpacks.recipe({"manifest": heron, "url": "https://example.com/heron", "commit": "c" * 40})
        self.assertEqual(row["source"]["fetch"][0]["version"], "2.7.1")
        self.assertEqual(packformat.held(kept(5, "heron")), ("pinned", packformat.PINNED_SAID))
        # They are format 5's.
        self.assertEqual(errors_of(dict(kept(5, "heron"), format=4, framework="4.2")),
                         ['install.fetch\'s found, install.fetch\'s platform, install.fetch\'s signed, install.fetch\'s track, install.fetch\'s version, '
                          'install.keyring are pack format 5\'s: the manifest says "format": 5'])
        a = {"url": "https://example.com/{version}/a.tgz", "sha256": H, "to": "dl/a.tgz", "version": "1.2.3"}
        track = {"resolver": "github-release", "repo": "a/a"}
        signed = {"sig": "https://example.com/{version}/a.tgz.sig", "keys": "pub.asc"}
        for good in (a, {**a, "track": track}, {**a, "track": track, "found": {"from": "file", "url": "{url}.sha256"}},
                     {**a, "url": "https://example.com/a.tgz", "found": {"from": "zsync"}}):
            self.assertEqual(errors_of(manifest(fetch=[good])), [], good)
        self.assertEqual(errors_of(manifest(fetch=[{"url": a["url"], "to": "dl/a.tgz", "version": "1.2.3", "signed": signed, "track": track}], keyring={"pub.asc": KEY})), [])
        for bad, why in (({**a, "version": "1.2.3 beta"}, "install.fetch 1's version is not a version"),
                         ({k: v for k, v in a.items() if k != "version"}, "install.fetch 1 has {version} in its address and says no version to fill it with"),
                         ({**a, "url": "https://example.com/a.tgz", "version": None, "track": track}, "install.fetch 1 says track and no version"),
                         ({**a, "track": {"resolver": "ask-the-vendor"}}, "install.fetch 1's track is how a newer version is found, by one of: text, github-release"),
                         ({**a, "track": "github-release"}, "install.fetch 1's track is how a newer version is found"),
                         ({**a, "found": {"from": "pin"}}, "install.fetch 1's found is how a newer file's digest is learned from its publisher"),
                         ({**a, "found": "github-asset"}, "install.fetch 1's found is how a newer file's digest is learned")):
            got = errors_of(manifest(fetch=[{k: v for k, v in bad.items() if v is not None}]))
            self.assertTrue(any(e.startswith(why) for e in got), (bad, got))
        got = errors_of(manifest(fetch=[{"url": a["url"], "to": "dl/a.tgz", "version": "1.2.3", "signed": signed, "found": {"from": "none"}}], keyring={"pub.asc": KEY}))
        self.assertEqual(got, ["install.fetch 1 says found and is held by a signature: there is no digest to learn"])
        # The name it is kept as takes no version: the steps read one path whatever the pin.
        self.assertTrue(any(e.startswith("install.fetch 1 is {url, sha256, to}") for e in errors_of(manifest(fetch=[{**a, "to": "dl/a-{version}.tgz"}]))))

    def test_the_recipe_a_node_is_handed_carries_them(self):
        rec = lambda name: {"manifest": toolpacks.validate(kept(5, name))[0], "url": "https://example.com/p", "commit": "c" * 40}  # noqa: E731
        src = toolpacks.recipe(rec("tern"))["source"]
        self.assertEqual((src["fetch"][0]["signed"]["keys"], list(src["keyring"]), src["offline"]), ("tern.asc", ["tern.asc"], True))
        src = toolpacks.recipe(rec("quill"))["source"]
        self.assertEqual(([f.get("platform") for f in src["fetch"]], src["offline"], "keyring" in src), (["linux/amd64", "linux/arm64", None], True, False))
        # One whose installer downloads the rest keeps the network: its
        # sentence goes in the cut's place.
        src = toolpacks.recipe(rec("kestrel"))["source"]
        self.assertTrue(src["online"].startswith("Its installer, kestrel-up") and "offline" not in src and len(src["fetch"]) == 1)


class Row(unittest.TestCase):
    """A shipped row's source takes the same shapes, held where the
    catalog's row is taken and written into its official pack's manifest."""

    def setUp(self):
        self.shipped = {"name": "go", "probe": "go", "label": "Go", "about": "The Go toolchain.", "maker": "Google", "platforms": ["linux/amd64"],
                        "layout": {"bin": ["bin"], "env": {}}, "terms": [],
                        "source": {"kind": "tarball", "url": "https://example.com/{version}.tar.gz", "checksum": {"from": "go-json"}}}

    def newer(self, **source):
        row = copy.deepcopy(self.shipped)
        row["rev"] = 2
        row["source"].update(source)
        return row

    def test_a_well_formed_source_is_taken_and_a_malformed_one_refused(self):
        fetch = [{"url": "https://example.com/extra.bin", "sha256": H, "to": "dl/extra.bin", "platform": "linux/amd64"}]
        for good in ({"fetch": fetch}, {"fetch": fetch, "online": SENTENCE}, {"offline": True}, {"keyring": {"go.asc": KEY}},
                     {"fetch": [{"url": "https://example.com/e.bin", "to": "e.bin", "signed": {"sig": "https://example.com/e.sig", "keys": "node.asc"}}]}):
            self.assertEqual(catalogrows.checked(self.newer(**good), self.shipped)[1], "", good)
        for bad, said in (({"fetch": [{"url": "http://example.com/x", "sha256": H, "to": "x"}]}, "source.fetch 1 is {url, sha256, to}"),
                          ({"fetch": "https://example.com/x"}, "source.fetch lists up to"),
                          ({"keyring": {"go.asc": "nope"}}, "source.keyring maps up to"),
                          ({"online": "x"}, "source.online is one sentence"),
                          ({"online": SENTENCE, "offline": True}, "source.online and source.offline are both said"),
                          ({"offline": "yes"}, "source.offline is true or false")):
            got, why = catalogrows.checked(self.newer(**bad), self.shipped)
            self.assertIsNone(got, bad)
            self.assertIn(said, why, bad)

    def test_how_a_newer_pin_is_found_is_held_to_its_shape_and_read_by_no_install(self):
        pin = {"from": "pin", "version": "go1.99.0", "sha256": H}
        # A pin's found is written as a checksum that asks the origin is, by one of the same kinds.
        for found in ({"from": "go-json"}, {"from": "json", "url": "https://example.com/{version}.json", "path": "0.sha256"}, {"from": "none", "why": "it states a sha1"}):
            row = self.newer(checksum={**pin, "found": found})
            self.assertEqual(catalogrows.checked(row, self.shipped)[1], "", found)
            self.assertEqual(packformat.held(row), ("pinned", packformat.PINNED_SAID), "and the word is the pin's, whatever found says")
        for found in ({"from": "pin"}, {"from": "ask-the-vendor"}, "go-json", {}):
            got, why = catalogrows.checked(self.newer(checksum={**pin, "found": found}), self.shipped)
            self.assertIsNone(got, found)
            self.assertIn("its pin's found is how a newer file's digest is learned from its publisher, from one of: json, android-repo", why)
        self.assertEqual(sorted(packformat.FOUND_FROM), sorted(c for c in catalogrows.CHECKSUMS if c != "pin"))
        # A repository: the commit, the tag it is fetched under, and how the commit to pin is found.
        git = {"kind": "git", "url": "https://example.com/kit.git", "branch": "stable", "commit": "c" * 40}
        shipped = {**self.shipped, "source": {"kind": "git", "url": "https://example.com/kit.git", "branch": "stable"}}
        for good in ({}, {"tag": "3.50.1"}, {"tag": "v3.50.1", "track": {"resolver": "git-tag", "match": "^v\\d+\\.\\d+\\.\\d+$"}},
                     {"track": {"resolver": "git-branch", "branch": "stable"}}):
            row = {**shipped, "rev": 2, "source": {**git, **good}}
            self.assertEqual(catalogrows.checked(row, shipped)[1], "", good)
        for bad, said in (({"commit": "c0ffee"}, "source.commit is a commit's whole hash"), ({"commit": "C" * 40}, "source.commit is a commit's whole hash"),
                          ({"tag": "a..b"}, "source.tag is the tag"), ({"tag": 7}, "source.tag is the tag"),
                          ({"track": {"resolver": "github-release", "repo": "a/a"}}, "source.track is how a newer version is found, by one of: git-tag, git-branch"),
                          ({"track": "git-tag"}, "source.track is how a newer version is found")):
            got, why = catalogrows.checked({**shipped, "rev": 2, "source": {**git, **bad}}, shipped)
            self.assertIsNone(got, bad)
            self.assertIn(said, why, bad)
        # A tag with no commit pins nothing, and a download says source.version, not track.
        self.assertIn("source.tag is the tag", catalogrows.checked({**shipped, "rev": 2, "source": {"kind": "git", "url": git["url"], "tag": "3.50.1"}}, shipped)[1])
        self.assertIn("a source of another kind says source.version", catalogrows.checked(self.newer(track={"resolver": "git-tag"}), self.shipped)[1])
        for word in ("match", "git-tag", "git-branch"):
            self.assertIn(word, catalogrows.RESOLVERS)
        # A repository that names its tag or its track is format 5's.
        self.assertEqual((packformat.source_format({**git, "tag": "3.50.1"}), packformat.source_format({**git, "track": {"resolver": "git-tag"}}),
                          packformat.source_format({"kind": "git", "url": git["url"], "branch": "stable"})), (5, 5, 1))

    def test_its_official_pack_says_format_5_and_comes_back_whole(self):
        self.assertEqual(packformat.source_format(self.shipped["source"]), 1)
        self.assertNotIn("format", catalogrows.manifest_of(self.shipped))
        for part in ({"checksum": {"from": "pin", "version": "go1.99.0", "sha256": H}}, {"offline": True}, {"online": SENTENCE},
                     {"fetch": [{"url": "https://example.com/e.bin", "sha256": H, "to": "e.bin"}]}, {"keyring": {"go.asc": KEY}},
                     {"then": [{"run": ["{dir}/bin/go", "version"]}]}):
            row = self.newer(**part)
            m = catalogrows.manifest_of(row)
            self.assertEqual((m["format"], m["framework"]), (5, "5.1"), part)
            self.assertEqual(toolpacks.validate(m, official=True)[1], [], part)
            self.assertEqual(catalogrows.row_of(m), row, part)
            # An install from before format 5 is told so in one sentence, and its own row stays.
            self.assertEqual(toolpacks.validate(dict(m, format=4), official=True)[1],
                             ['what shipped.source says of its downloads is pack format 5\'s: the manifest says "format": 5'], part)
        # A script's follow-up steps are format 1's, as they always ran.
        self.assertEqual(packformat.source_format({"kind": "script", "then": [{"run": ["x"]}]}), 1)

    def test_every_shipped_row_is_one_the_format_takes_and_says_5_where_its_entry_holds_its_downloads(self):
        rows = json.loads((ROOT / "config" / "toolchains.json").read_text())["toolchains"]
        self.assertEqual([r["name"] for r in rows if packformat.source_refused(r.get("source"))], [])
        # A row that pins, declares or says online is format 5's, and its
        # official pack says so; the two held by a signature alone, and the
        # rows that are still open, say nothing new.
        for r in rows:
            word = packformat.held(r)[0]
            self.assertEqual(packformat.source_format(r["source"]), 1 if word == "open" or r["name"] in ("node", "swift") else 5, r["name"])
            self.assertEqual(catalogrows.manifest_of(r).get("format", 1), packformat.source_format(r["source"]), r["name"])


class Held(unittest.TestCase):
    """The three words, from the entry alone."""

    def word(self, doc, word, why=""):
        got = packformat.held(doc)
        self.assertEqual(got[0], word, got)
        self.assertIn(why, got[1], got)
        self.assertIn(got[0], packformat.HELD_WORDS)
        return got

    def test_pinned(self):
        pin = {"from": "pin", "version": "1.2.3", "sha256": {"linux/amd64": H}}
        tar = {"kind": "tarball", "url": "https://example.com/{version}.tgz", "checksum": pin}
        self.word({"name": "t", "source": tar}, "pinned", "every download it makes is held")
        # What it runs afterwards is cut by the pin alone: offline need not be said, and may be.
        self.word({"name": "t", "source": {**tar, "verify": ["{dir}/bin/t"], "then": [{"run": ["{dir}/bin/t", "setup"]}]}}, "pinned")
        self.word({"name": "t", "source": {**tar, "offline": True, "verify": ["{dir}/bin/t"]}}, "pinned")
        self.word({"name": "i", "source": {"kind": "script", "url": "https://example.com/i.sh", "run": ["sh", "{script}"], "checksum": pin}}, "pinned")
        self.word({"name": "t", "source": {"kind": "script", "url": "https://example.com/i.sh", "run": ["sh", "{script}"], "checksum": pin,
                                           "fetch": [{"url": "https://example.com/a", "sha256": H, "to": "a"}]}}, "pinned")
        # A publisher's signature under a key the entry names holds a download as a pin does.
        self.word({"name": "s", "source": {"kind": "tarball", "url": "https://example.com/s.tgz", "verify": ["x"],
                                           "checksum": {"from": "signature", "sig": "{url}.sig", "keys": "swift.asc"}}}, "pinned")
        self.word({"name": "n", "source": {"kind": "tarball", "url": "https://example.com/n.tgz", "verify": ["x"],
                                           "checksum": {"from": "file", "url": "{base}/SUMS", "signed": {"sig": "{base}/SUMS.sig", "keys": "node.asc"}}}}, "pinned")
        # A pack is fetched at a commit; what it declares is held, and its steps are cut.
        self.word(kept(3, "hexkit"), "pinned")
        self.word(kept(5, "quill"), "pinned")
        self.word(kept(5, "tern"), "pinned")
        self.word(kept(5, "osprey"), "pinned")
        # ...as the validator keeps it, and as the row a node is handed.
        clean, _ = toolpacks.validate(kept(5, "tern"))
        self.word(clean, "pinned")
        self.word(toolpacks.recipe({"manifest": clean, "url": "https://example.com/tern", "commit": "c" * 40}), "pinned")
        # One that runs nothing and fetches nothing more is its commit.
        self.word({"name": "files", "install": {}, "verbs": {}}, "pinned")

    def test_installer(self):
        self.word(kept(5, "kestrel"), "installer", "Its installer, kestrel-up, downloads the compiler and the standard library")
        clean, _ = toolpacks.validate(kept(5, "kestrel"))
        self.word(toolpacks.recipe({"manifest": clean, "url": "https://example.com/k", "commit": "c" * 40}), "installer", "kestrel-up")
        self.word({"name": "r", "source": {"kind": "script", "url": "https://example.com/init.sh", "run": ["sh", "{script}"], "online": SENTENCE,
                                           "checksum": {"from": "pin", "sha256": H}}}, "installer", SENTENCE)
        # A package another row's program installs has no download of its
        # own: with the sentence it is that installer's, by its shape and
        # whatever it is called.
        self.word({"name": "kit:extras", "requires": ["kit-tools"], "source": {"kind": "sdkmanager", "package": "extras", "online": SENTENCE}}, "installer", SENTENCE)
        # A repository at a commit whose warm-up downloads the rest.
        self.word({"name": "f", "source": {"kind": "git", "url": "https://example.com/f.git", "branch": "stable", "commit": "c" * 40, "tag": "3.50.1",
                                           "track": {"resolver": "git-tag", "match": "^\\d"}, "warm": ["{dir}/bin/f", "--version"], "online": SENTENCE}},
                  "installer", SENTENCE)

    def test_open_says_which_part(self):
        pin = {"from": "pin", "sha256": H}
        for src, why in (({"kind": "tarball", "url": "https://x.example/a", "checksum": {"from": "go-json"}}, "what its own origin says at the moment of the install (go-json)"),
                         ({"kind": "tarball", "url": "https://x.example/a", "checksum": {"from": "file", "url": "{url}.sha256"}}, "its own origin says"),
                         ({"kind": "script", "url": "https://x.example/a", "run": ["x"], "checksum": {"from": "none", "why": "it is a moving script"}}, "checked against nothing: it is a moving script"),
                         ({"kind": "tarball", "url": "https://x.example/a"}, "says nothing to check its download against"),
                         ({"kind": "tarball", "url": "https://x.example/a", "checksum": {"from": "pin", "sha256": "abc"}}, "its pin's sha256 is not 64 hex digits"),
                         ({"kind": "git", "url": "https://x.example/r", "branch": "stable"}, "at a branch, with no commit"),
                         ({"kind": "sdkmanager", "package": "ndk"}, "its own package manager downloads it"),
                         ({"kind": "command", "run": ["tool", "install"]}, "its install steps run with the network"),
                         ({"kind": "git", "url": "https://x.example/r", "commit": "c" * 40, "then": [{"run": ["{dir}/setup"]}]}, "its install steps run with the network"),
                         ({"kind": "tarball", "url": "https://x.example/a", "checksum": pin, "fetch": [{"url": "https://x.example/b", "to": "dl/b"}]}, "dl/b is held to nothing its entry carries")):
            self.word({"name": "x", "source": src}, "open", why)
        # A pack with steps that declares nothing: what they fetch is anybody's guess.
        self.word(kept(1, "hexkit"), "open", "its install steps run with the network")
        # A pack names a key it does not carry.
        m = kept(5, "tern")
        del m["install"]["keyring"]
        self.word(m, "open", "dl/tern.tar.xz is held to nothing its entry carries")
        # What AerieOS installs by a job of its own is not in an entry.
        self.word(kept(1, "model-router"), "open", "how it is installed is not in its entry")
        self.word(kept(1, "grok"), "open", "how it is installed is not in its entry")
        for odd in (None, "x", [], {}):
            self.assertEqual(packformat.held(odd)[0], "open")

    def test_every_shipped_row_has_a_word(self):
        rows = json.loads((ROOT / "config" / "toolchains.json").read_text())["toolchains"]
        words = {r["name"]: packformat.held(r) for r in rows}
        self.assertTrue(all(w in packformat.HELD_WORDS and why for w, why in words.values()))
        # Swift's download carries its publisher's signature, and Node's
        # checksum list does; the others here carry the sha256 of their
        # exact file. What they run is cut by that. The rest wait for
        # their pins.
        self.assertEqual(sorted(n for n, (w, _why) in words.items() if w == "pinned"), SHIPPED_PINNED)
        self.assertEqual(sorted(n for n, (w, _why) in words.items() if w == "installer"), SHIPPED_INSTALLER)
        # An installer's sentence is the row's own, and says where the rest comes from.
        for name in SHIPPED_INSTALLER:
            self.assertEqual(words[name][1], " ".join(next(r for r in rows if r["name"] == name)["source"]["online"].split()), name)
        # Every pinned row says how its newer pin is found, or is held by a signature that needs none.
        for r in rows:
            src = r["source"]
            if (src.get("checksum") or {}).get("from") == "pin":
                self.assertEqual(packformat.pin_refused(src["checksum"]), "", r["name"])
                plats = src["url"] if isinstance(src.get("url"), dict) else None
                self.assertEqual(sorted(src["checksum"]["sha256"]) if plats else None, sorted(plats) if plats else None, f"{r['name']}: a digest for every platform it names")


class Said(unittest.TestCase):
    """Where a person reads an entry: the rows the Library and the Installed
    page are answered with, and Look before a pack is added."""

    def test_every_row_of_the_table_carries_its_word(self):
        import toolchains  # noqa: PLC0415
        self.assertTrue(toolchains.TOOLCHAINS)
        for p in toolchains.TOOLCHAINS:
            self.assertIn(p["held"]["word"], packformat.HELD_WORDS, p["name"])
            self.assertTrue(p["held"]["why"], p["name"])
        # A pack among them is read from the row a node is handed.
        clean, _ = toolpacks.validate(kept(5, "kestrel"))
        rows = toolchains.load_toolchains([toolpacks.recipe({"manifest": clean, "url": "https://example.com/k", "commit": "c" * 40})])
        row = next(r for r in rows if r["name"] == "kestrel")
        self.assertEqual(row["held"]["word"], "installer")
        self.assertTrue(row["held"]["why"].startswith("Its installer, kestrel-up, downloads"))

    def test_a_node_s_rows_and_the_library_s_answer_it(self):
        import library  # noqa: PLC0415
        import toolchains  # noqa: PLC0415

        class Nodes:
            @staticmethod
            def node(nid):
                return {"id": nid, "name": "box", "live": True, "reported": {"platform": "linux/amd64", "store_dirs": {"top": [], "android": []}}}

            @staticmethod
            def node_list():
                return []

            @staticmethod
            def jobs_for(**_kw):
                return []

        clean, _ = toolpacks.validate(kept(5, "tern"))
        packed = toolchains.load_toolchains([toolpacks.recipe({"manifest": clean, "url": "https://example.com/t", "commit": "c" * 40})])
        with mock.patch.object(toolchains, "nodes", Nodes), mock.patch.object(toolchains, "TOOLCHAINS", packed):
            payload = toolchains.payload_for_node("n_1")
        items = {i["name"]: i for i in payload["items"]}
        self.assertEqual(items["tern"]["held"], {"word": "pinned", "why": packformat.PINNED_SAID})
        self.assertEqual((items["playwright"]["held"]["word"], items["go"]["held"]["word"]), ("open", "pinned"))
        rows = {r["name"]: r for r in library.rows(payload, [], [], {"packs": []}, {})}
        self.assertEqual(rows["tern"]["held"], items["tern"]["held"])
        self.assertEqual((rows["tern"]["kind"], rows["playwright"]["kind"], rows["playwright"]["held"]["word"]), ("pack", "toolchain", "open"))

    def test_each_declared_download_says_how_it_is_held_and_the_platform_it_is_for(self):
        tern, quill = kept(5, "tern"), kept(5, "quill")
        signed = {"to": "dl/tern.tar.xz", "url": "https://downloads.tern.example.org/2.4.0/tern-2.4.0-linux.tar.xz", "held": "signed", "sha256": "",
                  "keys": "tern.asc", "sig": "https://downloads.tern.example.org/2.4.0/tern-2.4.0-linux.tar.xz.sig", "platform": ""}
        # The same from the manifest as written, as the validator keeps it, and from the row a node is handed.
        clean, _ = toolpacks.validate(tern)
        row = toolpacks.recipe({"manifest": clean, "url": "https://example.com/t", "commit": "c" * 40})
        for fetch in (tern["install"]["fetch"], clean["fetch"], row["source"]["fetch"]):
            self.assertEqual(packformat.downloads_said(fetch), [signed])
        got = packformat.downloads_said(quill["install"]["fetch"])
        self.assertEqual([(d["to"], d["held"], d["sha256"][:8], d["keys"], d["sig"], d["platform"]) for d in got],
                         [("dl/quill.tar.gz", "sha256", "2c26b46b", "", "", "linux/amd64"), ("dl/quill.tar.gz", "sha256", "fcde2b2e", "", "", "linux/arm64"),
                          ("dl/rules.tar.gz", "sha256", "9f86d081", "", "", "")])
        self.assertTrue(all(sorted(d) == ["held", "keys", "platform", "sha256", "sig", "to", "url"] and all(isinstance(v, str) for v in d.values()) for d in got))
        # For one machine: its own, and the ones for every platform.
        self.assertEqual([(d["to"], d["platform"]) for d in packformat.downloads_said(quill["install"]["fetch"], "linux/arm64")],
                         [("dl/quill.tar.gz", "linux/arm64"), ("dl/rules.tar.gz", "")])
        self.assertTrue(packformat.fits_machine("linux/*", "linux/arm64") and packformat.fits_machine("", "linux/arm64") and packformat.fits_machine("darwin/arm64", ""))
        self.assertFalse(packformat.fits_machine("darwin/*", "linux/arm64") or packformat.fits_machine("linux/amd64", "linux/arm64"))
        # One held to nothing says so by saying neither; what is no download is left out.
        self.assertEqual(packformat.downloads_said([{"url": "https://example.com/x", "to": "x"}, "junk", {"to": "no address"}]),
                         [{"to": "x", "url": "https://example.com/x", "held": "", "sha256": "", "keys": "", "sig": "", "platform": ""}])
        self.assertEqual(packformat.downloads_said(None), [])

    def test_a_row_and_a_receipt_list_them_and_what_look_reads_compares_key_for_key(self):
        import library  # noqa: PLC0415
        import toolchains  # noqa: PLC0415
        recs = []
        for name in ("tern", "quill"):
            clean, _ = toolpacks.validate(kept(5, name))
            recs.append(toolpacks.recipe({"manifest": clean, "url": f"https://example.com/{name}", "commit": "c" * 40}))
            # What the row keeps of its downloads is what Look reads of the
            # same manifest, byte for byte: the page marks a difference as changed.
            row = next(r for r in toolchains.load_toolchains(recs) if r["name"] == name)
            self.assertEqual(json.dumps(row["pack"]["fetch"]), json.dumps(clean["fetch"]), name)
            self.assertEqual(row["pack"]["downloads"], packformat.downloads_said(clean["fetch"]), name)
            self.assertEqual(row["downloads"], row["pack"]["downloads"], name)
        # A pack from before format 5 keeps the three keys it had.
        old, _ = toolpacks.validate(kept(3, "hexkit"))
        row = next(r for r in toolchains.load_toolchains([toolpacks.recipe({"manifest": old, "url": "https://example.com/h", "commit": "c" * 40})]) if r["name"] == "hexkit")
        self.assertEqual([sorted(f) for f in row["pack"]["fetch"]], [["sha256", "to", "url"]])
        self.assertEqual([d["held"] for d in row["downloads"]], ["sha256"])

        tree = "1" * 64
        reported = {"store_dirs": {"top": ["quill", "tern"], "android": []},
                    "toolchain_receipts": {n: {"commit": "c" * 40, "tree": tree, "files": 3, "bytes": 9, "at": 5, "before": "", "net": "cut"} for n in ("quill", "tern")}}

        class Nodes:
            @staticmethod
            def node(nid):
                return {"id": nid, "name": "box", "live": True, "os": "linux", "arch": "aarch64", "reported": reported}

            @staticmethod
            def node_list():
                return []

            @staticmethod
            def jobs_for(**_kw):
                return []

        with mock.patch.object(toolchains, "nodes", Nodes), mock.patch.object(toolchains, "TOOLCHAINS", toolchains.load_toolchains(recs)):
            payload = toolchains.payload_for_node("n_1")
        items = {i["name"]: i for i in payload["items"]}
        # The row lists every platform's; its receipt on this node, the ones this node fetched.
        self.assertEqual([d["platform"] for d in items["quill"]["downloads"]], ["linux/amd64", "linux/arm64", ""])
        self.assertEqual([(d["to"], d["held"], d["platform"]) for d in items["quill"]["receipt"]["downloads"]],
                         [("dl/quill.tar.gz", "sha256", "linux/arm64"), ("dl/rules.tar.gz", "sha256", "")])
        self.assertEqual([(d["to"], d["held"], d["keys"], d["sha256"]) for d in items["tern"]["receipt"]["downloads"]], [("dl/tern.tar.xz", "signed", "tern.asc", "")])
        self.assertEqual(items["go"]["downloads"], [])
        rows = {r["name"]: r for r in library.rows(payload, [], [], {"packs": []}, {})}
        self.assertEqual(rows["tern"]["downloads"], items["tern"]["downloads"])
        self.assertEqual(rows["quill"]["receipt"]["downloads"], items["quill"]["receipt"]["downloads"])

    def test_look_says_it_before_a_pack_is_added(self):
        read = lambda name: lambda rel, cap: json.dumps(kept(5, name)).encode() if rel == toolpacks.MANIFEST else None  # noqa: E731
        self.assertEqual(toolpacks._examine(read("quill"), (), "none")["held"], {"word": "pinned", "why": packformat.PINNED_SAID})
        self.assertEqual(toolpacks._examine(read("kestrel"), (), "none")["held"]["word"], "installer")
        # ...and each download with how it is held, beside the manifest the page reads today.
        seen = toolpacks._examine(read("tern"), (), "none")
        self.assertEqual([(d["to"], d["held"], d["keys"]) for d in seen["downloads"]], [("dl/tern.tar.xz", "signed", "tern.asc")])
        self.assertEqual(seen["manifest"]["fetch"][0]["sha256"], "", "a signed one keeps an empty sha256, which the page reads")
        self.assertEqual([d["platform"] for d in toolpacks._examine(read("quill"), (), "none")["downloads"]], ["linux/amd64", "linux/arm64", ""])
        got = toolpacks._examine(lambda rel, cap: json.dumps(kept(1, "hexkit")).encode() if rel == toolpacks.MANIFEST else b"its guidance", (), "none")
        self.assertEqual((got["held"]["word"], got["held"]["why"]), ("open", "its install steps run with the network, and its entry does not say what they fetch"))


if __name__ == "__main__":
    unittest.main()
