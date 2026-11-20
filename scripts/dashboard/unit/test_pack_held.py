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

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))
import catalogrows  # noqa: E402
import packformat  # noqa: E402
import toolpacks  # noqa: E402

ROOT = Path(__file__).resolve().parents[3]
KEPT = Path(__file__).parent / "packformat"
H = "ab" * 32
KEY = json.loads((KEPT / "5" / "tern.json").read_text())["install"]["keyring"]["tern.asc"]
SENTENCE = "Its installer downloads the compiler from releases.example.org."


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

    def test_no_shipped_row_or_exported_pack_moved(self):
        rows = json.loads((ROOT / "config" / "toolchains.json").read_text())["toolchains"]
        self.assertEqual([r["name"] for r in rows if packformat.source_format(r.get("source")) != 1], [])
        self.assertEqual([r["name"] for r in rows if packformat.source_refused(r.get("source"))], [])


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
        self.word({"name": "t", "source": {**tar, "offline": True, "verify": ["{dir}/bin/t"]}}, "pinned")
        self.word({"name": "t", "source": {"kind": "script", "url": "https://example.com/i.sh", "run": ["sh", "{script}"], "checksum": pin,
                                           "fetch": [{"url": "https://example.com/a", "sha256": H, "to": "a"}]}}, "pinned")
        # A publisher's signature under a key the entry names holds a download as a pin does.
        self.word({"name": "s", "source": {"kind": "tarball", "url": "https://example.com/s.tgz", "checksum": {"from": "signature", "sig": "{url}.sig", "keys": "swift.asc"}}}, "pinned")
        self.word({"name": "n", "source": {"kind": "tarball", "url": "https://example.com/n.tgz", "offline": True, "verify": ["x"],
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
                         ({"kind": "script", "url": "https://x.example/i.sh", "run": ["sh", "{script}"], "checksum": pin}, "its install steps run with the network"),
                         ({"kind": "tarball", "url": "https://x.example/a", "checksum": pin, "verify": ["{dir}/bin/a"]}, "its install steps run with the network"),
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
        # checksum list does; the rest wait for their pins.
        self.assertEqual(words["flutter"][0], "open")
        self.assertEqual(words["go"][0], "open")


if __name__ == "__main__":
    unittest.main()
