"""An index entry's older pins (the operator, 20 Nov): a pack that moved
to a newer pack format keeps the pin of the manifest written in the one
before, and a build that reads only that one is offered it, with nothing
said of the newer. One function answers the entry as a build takes it
(packformat.pin_for), and every reader of the index goes through it: the
Library's offers and its newer-pin rows, adding a pack or an app, a kept
app's refresh, a shipped toolchain's newer row, a shipped coding agent's
newer recipe, the mirror's import and the card of an entry too new.

The build here stands at pack format 5, whatever this tree reads, and the
entries' newest pins are written in format 6."""
import copy
import json
import os
import shutil
import sys
import tempfile
import unittest
from pathlib import Path
from unittest import mock

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))
import agentcode  # noqa: E402
import agents  # noqa: E402
import catalogindex  # noqa: E402
import catalogmirror  # noqa: E402
import catalogrows  # noqa: E402
import library  # noqa: E402
import nasapps  # noqa: E402
import packformat  # noqa: E402
import toolpacks  # noqa: E402

ROOT = Path(__file__).resolve().parents[3]
URL = "https://example.com/hexkit"
NEW, OLD, OLDEST = "6" * 40, "5" * 40, "4" * 40


def entry(name="hexkit", **more):
    """An entry whose newest pin is format 6 and which keeps its format 5
    pin beside it, with what that manifest gave the entry."""
    return {"name": name, "url": URL, "path": f"packs/{name}", "tier": "vetted", "maker": "Hex Works", "about": "Looks inside binaries.",
            "withdrawn": False, "format": 6, "framework": "6.0", "commit": NEW, "sha256": "a" * 64, "platforms": ["linux/amd64", "linux/arm64"],
            "label": "Hex kit 2", "works_with": ["0.11"],
            "older": [{"format": 5, "framework": "5.2", "commit": OLD, "sha256": "b" * 64, "platforms": ["linux/amd64"], "label": "Hex kit"}],
            **more}


def parsed(*entries, **more):
    idx, why = catalogindex.parse(json.dumps({"version": 1, "generated": "2026-11-20T00:00:00Z", "packs": list(entries), **more}).encode())
    assert not why, why
    return idx


class At5(unittest.TestCase):
    """A build that reads pack format 5 and nothing past it."""

    def setUp(self):
        for mod, name, value in ((packformat, "FORMAT", 5), (packformat, "MINOR", 2), (packformat, "VERSION", "5.2")):
            p = mock.patch.object(mod, name, value)
            p.start()
            self.addCleanup(p.stop)


class Shape(At5):
    def test_the_entry_as_each_build_takes_it(self):
        e = entry()
        new = packformat.pin_for(e, reads=6)
        self.assertEqual((new["commit"], new["format"], new["label"], new["works_with"]), (NEW, 6, "Hex kit 2", ["0.11"]))
        self.assertNotIn("older", new)
        old = packformat.pin_for(e)
        self.assertEqual(old, {"name": "hexkit", "url": URL, "path": "packs/hexkit", "tier": "vetted", "maker": "Hex Works", "about": "Looks inside binaries.",
                               "withdrawn": False, "format": 5, "framework": "5.2", "commit": OLD, "sha256": "b" * 64, "platforms": ["linux/amd64"],
                               "label": "Hex kit"},
                         "the entry's own fields under the older pin, and nothing of the newest pin carried over (its works_with)")
        self.assertIsNone(packformat.pin_for(e, reads=4), "no pin a build at format 4 reads")
        self.assertEqual(e["commit"], NEW, "the entry itself is left as it was")

    def test_an_entry_with_no_older_pins_is_itself(self):
        plain = {k: v for k, v in entry().items() if k != "older"}
        self.assertIs(packformat.pin_for(plain, reads=6), plain)
        self.assertIsNone(packformat.pin_for(plain))
        self.assertIsNone(packformat.pin_for({"name": "x", "format": "six"}))
        self.assertIsNone(packformat.pin_for(None))

    def test_the_newest_readable_of_several(self):
        e = entry(format=7, older=[{"format": 6, "commit": NEW, "sha256": "a" * 64}, {"format": 5, "commit": OLD, "sha256": "b" * 64},
                                   {"format": 3, "commit": OLDEST, "sha256": "c" * 64}])
        self.assertEqual([(packformat.pin_for(e, reads=n) or {}).get("commit") for n in (7, 6, 5, 4, 3, 2)],
                         [NEW, NEW, OLD, OLDEST, OLDEST, None])

    def test_what_an_older_list_must_be(self):
        ok = entry()
        self.assertEqual(packformat.older_refused(ok), "")
        self.assertEqual(packformat.older_refused({k: v for k, v in ok.items() if k != "older"}), "")
        pin = ok["older"][0]
        for older, said in (
                ({}, "older lists up to"), ([], "older lists up to"), ([pin] * 9, "older lists up to"),
                ([{**pin, "format": 6}], "at or after 6"), ([{**pin, "format": 7}], "at or after 6"),
                ([pin, {**pin, "commit": OLDEST}], "at or after 5"),
                ([{**pin, "format": 4}, pin], "at or after 4"),
                ([{k: v for k, v in pin.items() if k != "format"}], "an older pin says its format"),
                ([{**pin, "format": True}], "an older pin says its format"),
                ([{**pin, "commit": "abc"}], "an older pin says its format"),
                ([{**pin, "sha256": "B" * 64}], "an older pin says its format"),
                (["5"], "an older pin says its format"),
                ([{**pin, "tier": "official"}], "an older pin says tier, which the entry says once"),
                ([{**pin, "url": "https://example.com/other"}], "an older pin says url"),
        ):
            bad = {**ok, "older": older}
            self.assertIn(said, packformat.older_refused(bad), older)
            self.assertIsNone(packformat.pin_for(bad), "an older list that is not the format's is read as none")
        self.assertEqual(packformat.older_refused({**ok, "older": [{**pin, "signed_by": "a later build's key"}]}), "",
                         "a key no build has met yet is left for the build that reads it")

    def test_parse_keeps_the_older_pins_each_held_to_its_shape(self):
        got = parsed(entry(older=[{"format": 5, "framework": "5.2", "commit": OLD, "sha256": "b" * 64, "platforms": ["linux/amd64", 7], "label": " Hex kit ",
                                   "works_with": ["0.10"], "install_rev": 3, "shipped_rev": 4, "later": "left out"},
                                  {"format": 1, "commit": OLDEST, "sha256": "c" * 64}]))["packs"][0]
        self.assertEqual(got["older"], [
            {"format": 5, "framework": "5.2", "commit": OLD, "sha256": "b" * 64, "platforms": ["linux/amd64"], "label": "Hex kit",
             "works_with": ["0.10"], "install_rev": 3, "shipped_rev": 4},
            {"format": 1, "commit": OLDEST, "sha256": "c" * 64, "platforms": []}])
        self.assertEqual((got["commit"], got["format"]), (NEW, 6), "the entry's own fields stay its newest pin")
        self.assertEqual(packformat.pin_for(got)["commit"], OLD)
        self.assertEqual(packformat.pin_for(got, reads=4)["commit"], OLDEST)

    def test_parse_drops_an_older_list_that_is_not_one_and_keeps_the_entry(self):
        for older in ("x", [], [{"format": 6, "commit": OLD, "sha256": "b" * 64}], [{"format": 5, "commit": OLD}],
                      [{"format": 5, "commit": OLD, "sha256": "b" * 64}, {"format": 5, "commit": OLDEST, "sha256": "c" * 64}]):
            got = parsed(entry(older=older, withdrawn=True))["packs"]
            self.assertEqual(len(got), 1, older)
            self.assertNotIn("older", got[0], older)
            self.assertEqual((got[0]["commit"], got[0]["withdrawn"]), (NEW, True), "its newest pin and its own word stand")
        self.assertEqual(parsed({k: v for k, v in entry().items() if k != "older"})["packs"][0].get("older"), None)

    def test_an_index_as_a_build_takes_it(self):
        idx = parsed(entry(), entry("plain", format=5, older=None), entry("late", older=None),
                     entry("later", format=8, older=[{"format": 7, "commit": NEW, "sha256": "a" * 64}, {"format": 6, "commit": OLD, "sha256": "b" * 64}]),
                     formats={"6": "0.11.0", "7": "0.12.0", "8": "0.13.0"})
        got = {e["name"]: e for e in packformat.taken(idx)}
        self.assertEqual(list(got), ["hexkit", "plain", "late", "later"], "every entry once, in the index's order")
        self.assertTrue(all("older" not in e for e in got.values()))
        self.assertEqual((got["hexkit"]["commit"], got["hexkit"]["format"]), (OLD, 5))
        self.assertEqual(catalogindex.too_new(got["hexkit"], idx), "")
        self.assertEqual(got["plain"]["commit"], NEW)
        self.assertIn("pack format 6", catalogindex.too_new(got["late"], idx))
        # No pin of it is readable: it is answered at the oldest it has,
        # so what it needs is the least AerieOS that would take it.
        self.assertEqual((got["later"]["commit"], got["later"]["format"]), (OLD, 6))
        self.assertEqual(catalogindex.too_new(got["later"], idx),
                         "needs AerieOS 0.11.0 or newer (it is written in pack format 6, and this AerieOS reads up to 5)")
        self.assertEqual(packformat.taken(None), [])
        self.assertEqual([e["commit"] for e in packformat.taken(idx, reads=6)], [NEW, NEW, NEW, OLD])


class Readers(At5):
    def tc(self, *items):
        return {"items": list(items), "platform": "linux/amd64"}

    def test_the_library_offers_the_older_pin_and_says_nothing_of_the_newer(self):
        idx = parsed(entry(), entry("whoami", kind="app"), formats={"6": "0.11.0"})
        with mock.patch.object(library, "fits", lambda m: m.get("works_with") != ["0.11"]):
            rows = {r["name"]: r for r in library.rows(self.tc(), [], [], idx, {})}
        pack, app = rows["hexkit"], rows["whoami"]
        self.assertEqual(pack["catalog"], {"url": URL, "commit": OLD, "sha256": "b" * 64, "path": "packs/hexkit"})
        self.assertEqual((pack["verb"], pack["label"], pack["framework"], pack["platforms"], pack["latest"]),
                         ("add", "Hex kit", "5.2", ["linux/amd64"], OLD[:12]))
        self.assertEqual((app["kind"], app["verb"], app["catalog"]["commit"]), ("app", "install", OLD))
        for r in (pack, app):
            self.assertNotIn("too_new", r)
            self.assertNotIn("ahead", r, "nothing is said of the pin it cannot use")
        self.assertEqual(library.browse(list(rows.values()), kinds=library.KINDS)["facts"]["not_this_build"], 0)

    def test_the_card_of_an_entry_with_no_readable_pin_is_too_new(self):
        idx = parsed(entry(older=None), entry("later", format=7, older=[{"format": 6, "commit": OLD, "sha256": "b" * 64}]), formats={"6": "0.11.0", "7": "0.12.0"})
        rows = {r["name"]: r for r in library.rows(self.tc(), [], [], idx, {})}
        for name in ("hexkit", "later"):
            self.assertEqual(rows[name]["too_new"], "needs AerieOS 0.11.0 or newer (it is written in pack format 6, and this AerieOS reads up to 5)", name)
            self.assertEqual(rows[name]["verb"], "")
        self.assertEqual(library.browse(list(rows.values()), kinds=library.KINDS)["facts"]["not_this_build"], 2)

    def test_a_pack_kept_from_the_older_pin_is_offered_the_newer_only_by_a_build_that_reads_it(self):
        def kept(commit):
            return {"name": "hexkit", "installed": True, "pack": {"url": URL, "commit": commit, "path": "packs/hexkit", "tier": "vetted", "verbs": ["dump"]}}
        idx = parsed(entry())

        def repin(commit):
            return next(r for r in library.rows(self.tc(kept(commit)), [], [], idx, {}) if r["name"] == "hexkit")["repin"]
        self.assertIsNone(repin(OLD), "kept at the pin this build takes: nothing newer for it")
        self.assertEqual(repin(OLDEST)["commit"], OLD, "kept from before it: the pin offered is the one this build reads")
        with mock.patch.object(packformat, "FORMAT", 6):
            self.assertEqual(repin(OLD), {"url": URL, "commit": NEW, "sha256": "a" * 64, "path": "packs/hexkit", "tier": "vetted"})

    def test_adding_a_pack_or_an_app_reads_the_older_pin(self):
        idx = parsed(entry(), entry("whoami", kind="app"), entry("gone", withdrawn=True), entry("late", older=None))
        self.assertEqual(catalogindex.named(idx, "hexkit")["commit"], OLD)
        self.assertEqual(catalogindex.named(idx, "whoami", kind="app")["commit"], OLD)
        self.assertIsNone(catalogindex.named(idx, "whoami"), "an app is no pack")
        self.assertIsNone(catalogindex.named(idx, "gone"))
        # What a page asks to add is the pin this build takes, or nothing.
        self.assertEqual(catalogindex.pinning(idx, URL, OLD, "b" * 64, "packs/hexkit")["tier"], "vetted")
        self.assertIsNone(catalogindex.pinning(idx, URL, NEW, "a" * 64, "packs/hexkit"), "the newest pin is not this build's to add")
        # One with no readable pin is answered for the caller to say what it needs.
        self.assertIn("pack format 6", catalogindex.too_new(catalogindex.named(idx, "late"), idx))

    def test_an_app_is_kept_and_refreshed_at_the_older_pin(self):
        tmp = Path(tempfile.mkdtemp())
        self.addCleanup(shutil.rmtree, tmp, True)
        nasapps.configure(state=tmp, write_json=lambda p, d: Path(p).write_text(json.dumps(d)))
        nasapps._trying.clear()
        asked = []

        def fetch(url, commit, sha256, path, files, cap=0):
            asked.append(commit)
            return {"files": {"bbapp.json": json.dumps({"name": "whoami", "label": "whoami", "about": "A tiny web server.", "port": 8089,
                                                        "platforms": ["linux/amd64"]}).encode(),
                              "compose.yml": b'services:\n  whoami:\n    image: traefik/whoami:v1.10.4\n    ports:\n      - "${PORT}:80"\n'}}
        idx = parsed(entry("whoami", kind="app"))
        self.assertEqual(nasapps.add_catalog(catalogindex.named(idx, "whoami", kind="app"), by="ann", fetch=fetch).get("app"), "whoami")
        self.assertEqual((asked, nasapps._load()["whoami"]["pin"]["commit"]), ([OLD], OLD))
        self.assertEqual(nasapps.wanted(idx), [], "kept at the pin this build takes: the newer one is not wanted")
        self.assertEqual(nasapps.refresh(idx, fetch), [])
        # The older pin itself moves (a fix to the format 5 manifest): taken.
        moved = copy.deepcopy(entry("whoami", kind="app"))
        moved["older"][0]["commit"] = OLDEST
        self.assertEqual(nasapps.refresh(parsed(moved), fetch), [("whoami", "")])
        self.assertEqual((asked, nasapps._load()["whoami"]["pin"]["commit"]), ([OLD, OLDEST], OLDEST))
        with mock.patch.object(packformat, "FORMAT", 6):
            self.assertEqual([(n, e["commit"]) for n, e in nasapps.wanted(parsed(moved))], [("whoami", NEW)])

    def test_a_shipped_toolchain_s_newer_row_is_the_older_pin_s(self):
        shipped = json.loads((ROOT / "config" / "toolchains.json").read_text())["toolchains"]
        d = tempfile.mkdtemp()
        self.addCleanup(shutil.rmtree, d, True)
        catalogrows.configure(state=d, write_json=lambda p, v: Path(p).write_text(json.dumps(v)))
        catalogrows._trying.clear()
        self.addCleanup(lambda: catalogrows.configure(state="/nonexistent", write_json=lambda *a: None))
        zig = next(r for r in shipped if r["name"] == "zig")
        rev = catalogrows.rev_of(zig)
        asked = []

        def fetch(url, commit, sha256, path, names):
            asked.append(commit)
            return {"files": {"bbtool.json": json.dumps(catalogrows.manifest_of(dict(zig, rev=rev + 1))).encode()}}

        def zig_entry(newest, older):
            e = entry("zig", tier="official", shipped_rev=newest)
            e["older"][0].update({"shipped_rev": older} if older else {})
            return parsed(e)
        # The newest pin's recipe is past the shipped row, the older pin's
        # is not: a build at format 5 wants nothing.
        self.assertEqual(catalogrows.wanted(zig_entry(rev + 5, rev), shipped), [])
        self.assertEqual(catalogrows.refresh(zig_entry(rev + 5, None), fetch, shipped, toolpacks.validate), [])
        self.assertEqual(asked, [])
        # The older pin's is newer too: fetched at the older commit.
        idx = zig_entry(rev + 5, rev + 1)
        self.assertEqual([(n, e["commit"], e["shipped_rev"]) for n, e in catalogrows.wanted(idx, shipped)], [("zig", OLD, rev + 1)])
        self.assertEqual(catalogrows.refresh(idx, fetch, shipped, toolpacks.validate), [("zig", "")])
        self.assertEqual((asked, catalogrows.kept()["zig"]["commit"]), ([OLD], OLD))
        # An entry with no pin this build reads is left, with nothing fetched or said.
        catalogrows._trying.clear()
        late = entry("zig", tier="official", shipped_rev=rev + 9, older=None)
        self.assertEqual(catalogrows.refresh(parsed(late), fetch, shipped, toolpacks.validate), [])
        self.assertEqual(asked, [OLD])

    def test_a_shipped_agent_s_newer_recipe_is_the_older_pin_s(self):
        was = (agentcode.catalog_entry, agentcode.fetch_pack, dict(agentcode._recipes))
        self.addCleanup(lambda: (setattr(agentcode, "catalog_entry", was[0]), setattr(agentcode, "fetch_pack", was[1]),
                                 agentcode._recipes.clear(), agentcode._recipes.update(was[2])))
        agentcode._recipes.clear()
        own = agents.get("codex").install
        asked = []

        def fetch(url, commit, shipped, sha256, path, official=False):
            asked.append(commit)
            return {"manifest": {"agent": {"install": {**own, "rev": own["rev"] + 1}}}}
        agentcode.fetch_pack = fetch

        def codex(newest, older):
            e = entry("codex", tier="official", install_rev=newest)
            e["older"][0].update({"install_rev": older} if older else {})
            return parsed(e)
        idx = codex(own["rev"] + 5, own["rev"])
        agentcode.catalog_entry = lambda name: catalogindex.official(idx, name)
        self.assertEqual(agentcode.recipe("codex"), (own, "release"), "the pin this build takes is no newer than its own")
        self.assertEqual(asked, [])
        idx = codex(own["rev"] + 5, own["rev"] + 1)
        got, where = agentcode.recipe("codex")
        self.assertEqual((got["rev"], where, asked), (own["rev"] + 1, "catalog", [OLD]))
        # No pin this build reads: the entry names no recipe it could run.
        idx = parsed(entry("codex", tier="official", install_rev=own["rev"] + 9, older=None))
        agentcode._recipes.clear()
        self.assertIsNone(catalogindex.official(idx, "codex"))
        self.assertEqual(agentcode.recipe("codex"), (own, "release"))
        self.assertEqual(asked, [OLD])

    def test_a_mirror_is_held_to_the_pin_this_build_would_fetch(self):
        state = tempfile.mkdtemp()
        self.addCleanup(shutil.rmtree, state, True)
        catalogmirror.configure(state=state)
        self.addCleanup(catalogmirror.configure, state=None)
        idx = parsed(entry())

        def take(heads):
            """A mirror whose bundle for the entry's repository holds `heads`."""
            def unpack(d):
                (d / "repos").mkdir()
                (d / "index.json").write_text("{}")
                (d / "repos" / f"{catalogmirror.key(URL)}.bundle").write_text("a bundle")
                return {"files": 1}
            with mock.patch.object(catalogmirror, "_read", lambda d: (idx, None)), mock.patch.object(catalogmirror, "_heads", lambda b: set(heads)):
                return catalogmirror._take(unpack, 1)
        self.assertEqual(take({NEW}).get("error"), "not imported: it lacks the repository of hexkit at the commit the index pins")
        self.assertTrue(take({OLD}).get("ok"), "the older pin is the one this build fetches")
        with mock.patch.object(packformat, "FORMAT", 6):
            self.assertIn("lacks the repository of hexkit", take({OLD}).get("error", ""))
            self.assertTrue(take({OLD, NEW}).get("ok"))


if __name__ == "__main__":
    unittest.main()
