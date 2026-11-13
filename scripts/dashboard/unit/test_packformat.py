"""The catalog's format number (R234): a manifest says the format it needs,
an entry repeats it, an install too old for one says so and adds nothing,
and a manifest that was valid at a number stays valid at every later one.

unit/packformat/N/ keeps manifests written in format N, as a release that
reads N took them: format 1's are a tool pack, a wrapped tool, a pack's
agent with named hook shapes, a shipped toolchain, a shipped agent, a
service and a Docker app, the last four as v0.9.0-dev.5236 carried them.
Each must pass this build's validators for good; `aerie lint` holds the
files a release shipped unchanged."""
import json
import os
import sys
import unittest
from pathlib import Path

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))
import catalogindex  # noqa: E402
import library  # noqa: E402
import nasapps  # noqa: E402
import packformat  # noqa: E402
import toolpacks  # noqa: E402

KEPT = Path(__file__).parent / "packformat"
ENTRY = {"name": "jdk", "url": "https://example.com/jdk", "commit": "a" * 40, "sha256": "b" * 64, "tier": "vetted"}


def kept(n):
    return sorted(p for p in (KEPT / str(n)).glob("*.json") if not p.name.endswith(".bbapp.json"))


class Kept(unittest.TestCase):
    def test_every_format_this_build_reads_has_manifests_kept(self):
        self.assertEqual(sorted(int(p.name) for p in KEPT.iterdir()), list(range(1, packformat.FORMAT + 1)))
        self.assertEqual(sorted(packformat.FORMATS), list(range(1, packformat.FORMAT + 1)), "and each says what it added")
        for n in range(1, packformat.FORMAT + 1):
            self.assertTrue(kept(n), n)

    def test_a_manifest_valid_at_a_number_is_valid_at_every_later_one(self):
        for n in range(1, packformat.FORMAT + 1):
            for p in kept(n):
                m = json.loads(p.read_text())
                got, errors = toolpacks.validate(m)
                self.assertEqual(errors, [], f"{p.parent.name}/{p.name}")
                self.assertEqual(got["format"], n if n > 1 else packformat.of(m), p.name)
                self.assertEqual(packformat.of(m), n, f"{p.name} says the format its folder is")

    def test_a_docker_app_s_manifest_and_compose_are_held_the_same_way(self):
        for n in range(1, packformat.FORMAT + 1):
            for p in sorted((KEPT / str(n)).glob("*.bbapp.json")):
                meta = json.loads(p.read_text())
                self.assertEqual(packformat.of(meta), n, p.name)
                self.assertIsInstance(int(meta["port"]), int)
                seen = nasapps.check(p.with_name(p.name.replace(".bbapp.json", ".compose.yml")).read_text())
                self.assertFalse(seen.get("error"), (p.name, seen))


class Makers(unittest.TestCase):
    """Who a tool is by (the operator, 12 Nov): a line a card draws, from a
    manifest, an index entry or a shipped row; said wrong it is nobody."""

    def test_a_maker_is_one_line_of_plain_words(self):
        self.assertEqual(packformat.maker_of({"maker": "  Eclipse   Adoptium "}), "Eclipse Adoptium")
        self.assertEqual(packformat.maker_of({"maker": "Kornel Lesi\u0144ski"}), "Kornel Lesi\u0144ski")
        for bad in ("", "x" * 61, "<b>Google</b>", "a\x1b[31m", 7, None, ["Google"], "{name}"):
            self.assertEqual(packformat.maker_of({"maker": bad}), "", repr(bad))
        self.assertEqual(packformat.maker_of("Google"), "")

    def test_credits_name_each_tool_and_who_it_is_by(self):
        got = packformat.credits_of({"credits": [{"name": "ruff", "maker": "Astral"}, {"name": "fd"}, {"maker": "nobody's tool"}, "x", {"name": "<i>"}]})
        self.assertEqual(got, [{"name": "ruff", "maker": "Astral"}, {"name": "fd", "maker": ""}])
        self.assertEqual(len(packformat.credits_of({"credits": [{"name": f"t{i}"} for i in range(40)]})), packformat.CREDITS_MAX)

    def test_a_manifest_and_an_index_entry_carry_them_and_a_wrong_one_is_said(self):
        m = json.loads((KEPT / "1" / "hexkit.json").read_text())
        got, errors = toolpacks.validate({**m, "framework": "2.1", "maker": "Example Labs", "credits": [{"name": "hexdump", "maker": "the util-linux project"}]})
        self.assertEqual((errors, got["maker"], got["credits"]), ([], "Example Labs", [{"name": "hexdump", "maker": "the util-linux project"}]))
        got, errors = toolpacks.validate(m)
        self.assertEqual((errors, got["maker"], got["credits"]), ([], "", []), "a manifest from before the key says nobody, and is as valid")
        self.assertTrue(any("maker is who the tool is by" in e for e in toolpacks.validate({**m, "framework": "2.1", "maker": "<b>x</b>"})[1]))
        self.assertTrue(any("credits lists" in e for e in toolpacks.validate({**m, "framework": "2.1", "credits": [{"maker": "no name"}]})[1]))
        idx, why = catalogindex.parse(json.dumps({"version": 1, "packs": [{**ENTRY, "maker": "Eclipse Adoptium"}, {**ENTRY, "name": "plain"}]}).encode())
        self.assertEqual((why, idx["packs"][0]["maker"], "maker" in idx["packs"][1]), ("", "Eclipse Adoptium", False))

    def test_every_shipped_row_agent_and_app_names_its_maker(self):
        root = Path(__file__).resolve().parents[3]
        rows = json.loads((root / "config" / "toolchains.json").read_text())["toolchains"]
        self.assertEqual([r["name"] for r in rows if not packformat.maker_of(r)], [])
        for r in rows:
            self.assertEqual(packformat.credits_of(r), r.get("credits") or [], r["name"])
            if r["maker"] == "AerieOS":
                self.assertGreater(len(r.get("credits") or []), 1, f"{r['name']}: a toolchain AerieOS put together credits each maker's tool in it")
        self.assertEqual([k for k, v in nasapps.APPS.items() if not packformat.maker_of(v)], [])
        import agents
        self.assertEqual([a.id for a in agents.TABLE if not (library.AGENT_MAKERS.get(a.id) or a.provider)], [])


class Framework(unittest.TestCase):
    """The framework's version is two numbers (the operator, 12 Nov): the
    format, which an install must read to run an entry, and a second for
    what was added that an earlier install leaves out; a manifest says the
    version it is written for, and what it uses is in that version."""

    def test_a_manifest_says_the_version_it_is_written_for_beside_its_format(self):
        self.assertEqual(packformat.framework_of({"format": 2, "framework": "2.1"}), (2, 1))
        self.assertEqual(packformat.framework_of({"format": 2}), (2, 0), "one that says none is its format's first")
        self.assertEqual(packformat.framework_of({}), (1, 0))
        self.assertEqual(packformat.framework_of({"framework": "2.1"}), (2, 1), "written for 2.1 and run by any install that reads format 1")
        for bad in (2.1, 2, "2", "2.x", "v2.1", "", "0.1", ["2.1"]):
            self.assertIsNone(packformat.framework_of({"framework": bad}), repr(bad))
        self.assertEqual(packformat.VERSION, f"{packformat.FORMAT}.{packformat.MINOR}")
        # The second number never resets: 2.2 is followed by 3.2 when the
        # format moves, and what brought it says so under the number it had.
        self.assertIn(packformat.MINOR, [y for _, y in packformat.ADDED], "each second number says what it added")

    def test_what_a_manifest_uses_is_in_the_version_it_says(self):
        m = json.loads((KEPT / "1" / "hexkit.json").read_text())
        _, errors = toolpacks.validate({**m, "maker": "Example Labs"})
        self.assertEqual(errors, ['maker is catalog framework 2.1\'s: the manifest says "framework": "2.1"'])
        self.assertEqual(toolpacks.validate({**m, "maker": "Example Labs", "framework": "2.1"})[1], [])
        self.assertEqual(toolpacks.validate({**m, "maker": "Example Labs", "framework": "3.4"})[1], [], "a later version holds what an earlier one brought")
        self.assertTrue(any("is before the format" in e for e in toolpacks.validate({**m, "format": 2, "framework": "1.0"})[1]))
        self.assertTrue(any('as "2.1"' in e for e in toolpacks.validate({**m, "framework": 2.1})[1]))
        heron = json.loads((KEPT / "2" / "heron.json").read_text())
        self.assertEqual(toolpacks.validate(heron)[1], [])
        del heron["framework"]
        self.assertTrue(any("signin.flow is catalog framework 2.1's" in e for e in toolpacks.validate(heron)[1]))

    def test_an_entry_written_for_a_later_second_number_is_taken_and_says_what_is_left_out(self):
        idx, why = catalogindex.parse(json.dumps({"version": 1, "formats": {"2": "0.9.0", "2.1": "0.9.0-dev.5300", "x": "y"},
                                                  "packs": [{**ENTRY, "format": 2, "framework": "2.7"}, {**ENTRY, "name": "plain"}]}).encode())
        self.assertEqual(why, "")
        self.assertEqual((idx["packs"][0]["framework"], "framework" in idx["packs"][1]), ("2.7", False))
        self.assertEqual(idx["formats"], {"2": "0.9.0", "2.1": "0.9.0-dev.5300"}, "the index says the first AerieOS that reads each version")
        self.assertEqual(catalogindex.too_new(idx["packs"][0], idx), "", "its format is one this build reads: it is taken")
        self.assertIn("written for catalog framework 2.7", packformat.ahead(idx["packs"][0]))
        self.assertEqual(packformat.ahead({"framework": packformat.VERSION}), "")

    def test_a_manifest_written_from_a_table_says_the_least_version_that_holds_what_it_uses(self):
        self.assertEqual(packformat.least({"maker": "Google"}), "2.1")
        self.assertEqual(packformat.least({"name": "plain"}), "")
        self.assertEqual(packformat.least({"format": 2}, [((2, 1), "signin.flow")]), "2.1")
        root = Path(__file__).resolve().parents[3]
        for f in sorted((root / "packs").glob("*/*/bbtool.json")):
            m = json.loads(f.read_text())
            # A shipped agent that says how it signs in says who is signed
            # in from a named file, which is 2.2's.
            want = "2.2" if (m.get("agent") or {}).get("signin") else "2.1"
            self.assertEqual(m.get("framework"), want, f"{f.parent.name} names its maker, which is framework 2.1's")
            if want == "2.2":
                self.assertTrue(toolpacks.validate(dict(m, framework="2.1"))[1], f"{f.parent.name}: what it uses is held to the version it says")


class Number(unittest.TestCase):
    def test_a_manifest_past_this_build_is_refused_in_one_sentence(self):
        m = json.loads((KEPT / "1" / "hexkit.json").read_text())
        got, errors = toolpacks.validate(dict(m, format=packformat.FORMAT + 1, agent={"anything": "a later format invents"}))
        self.assertIsNone(got)
        self.assertEqual(len(errors), 1, "never a list of rules written before it")
        self.assertIn(f"written in pack format {packformat.FORMAT + 1}, and this AerieOS reads up to {packformat.FORMAT}", errors[0])
        for bad in (0, "2", True, 2.0, -1):
            self.assertIn("a whole number from 1", toolpacks.validate(dict(m, format=bad))[1][0], bad)

    def test_what_a_manifest_uses_is_the_format_it_says(self):
        m = json.loads((KEPT / "2" / "gemini.json").read_text())
        del m["format"]
        _, errors = toolpacks.validate(m)
        self.assertEqual(errors, ['what its agent says of its own hooks is pack format 2\'s: the manifest says "format": 2'])
        one = json.loads((KEPT / "1" / "kite.json").read_text())
        self.assertEqual(toolpacks.validate(dict(one, format=2))[1], [], "a later number than it needs is still a number this build reads")

    def test_the_sentence_names_the_first_aerieos_that_reads_it_where_the_index_says(self):
        n = packformat.FORMAT + 1
        self.assertEqual(packformat.too_new(packformat.FORMAT), "")
        self.assertEqual(packformat.too_new(n), f"needs a newer AerieOS than this one (it is written in pack format {n}, and this AerieOS reads up to {packformat.FORMAT})")
        self.assertTrue(packformat.too_new(n, "0.10.0").startswith("needs AerieOS 0.10.0 or newer ("))


class Tiers(unittest.TestCase):
    """Who stands behind an entry (the operator, 12 Nov): Packaged by Aerie,
    Verified and Vetted are what a person reads; the stored words stay."""

    def test_the_index_s_words_are_kept_and_one_not_met_reads_as_vetted(self):
        idx, why = catalogindex.parse(json.dumps({"version": 1, "packs": [dict(ENTRY, name=f"p{i}", tier=t) for i, t in
                                                                           enumerate(("official", "aerie", "verified", "vetted", "platinum", None))]}).encode())
        self.assertEqual(why, "")
        self.assertEqual([p["tier"] for p in idx["packs"]], ["official", "aerie", "verified", "vetted", "vetted", "vetted"])

    def test_what_a_person_reads_for_each(self):
        self.assertEqual([packformat.TIER_WORDS[t] for t in packformat.TIERS], ["Packaged by Aerie", "Packaged by Aerie", "Verified", "Vetted"])
        rows = library.rows({"items": []}, [], [], {"packs": [dict(ENTRY, name=f"p{i}", tier=t) for i, t in enumerate(("aerie", "verified", "vetted"))]}, {})
        self.assertEqual([(r["tier"], library.TIER_WORDS[r["tier"]]) for r in rows],
                         [("official", "Packaged by Aerie"), ("verified", "Verified"), ("vetted", "Vetted")])

    def test_a_pack_s_agent_is_offered_from_any_signed_tier_and_never_from_an_address(self):
        m, errors = toolpacks.validate(json.loads((KEPT / "1" / "kite.json").read_text()))
        self.assertEqual(errors, [])
        for tier, offered in (("official", True), ("aerie", True), ("verified", True), ("vetted", True), ("url", False), ("here", False)):
            self.assertEqual(bool(toolpacks.offers_agent({"manifest": m, "tier": tier})), offered, tier)


class Index(unittest.TestCase):
    def index(self, *packs, **top):
        idx, why = catalogindex.parse(json.dumps({"version": 1, "packs": list(packs), **top}).encode())
        self.assertEqual(why, "")
        return idx

    def test_an_entry_repeats_its_manifest_s_format(self):
        n = packformat.FORMAT + 1
        idx = self.index(ENTRY, dict(ENTRY, name="later", format=n), dict(ENTRY, name="odd", format="3"), formats={str(n): "0.10.0", "x": "y"})
        self.assertEqual([(p["name"], p.get("format")) for p in idx["packs"]], [("jdk", None), ("later", n)], "one whose format is no number is no entry")
        self.assertEqual(idx["formats"], {str(n): "0.10.0"})
        self.assertEqual(catalogindex.too_new(idx["packs"][0], idx), "")
        self.assertTrue(catalogindex.too_new(idx["packs"][1], idx).startswith("needs AerieOS 0.10.0 or newer"))

    def test_the_library_lists_one_past_this_build_with_nothing_to_press(self):
        n = packformat.FORMAT + 1
        idx = self.index(dict(ENTRY, name="now"), dict(ENTRY, name="later", format=n), dict(ENTRY, name="laterapp", kind="app", format=n),
                         formats={str(n): "0.10.0"})
        by = {r["name"]: r for r in library.rows({"items": []}, [], [], idx, {})}
        self.assertEqual((by["now"]["verb"], by["now"].get("too_new")), ("add", None))
        for name in ("later", "laterapp"):
            self.assertEqual(by[name]["verb"], "", name)
            self.assertTrue(by[name]["too_new"].startswith("needs AerieOS 0.10.0 or newer"), name)

    def test_a_kept_pack_is_not_offered_a_pin_past_this_build(self):
        n = packformat.FORMAT + 1
        node = {"items": [{"name": "otter", "label": "Otter", "installed": "1", "pack": {"tier": "vetted", "url": ENTRY["url"], "commit": "c" * 40}}]}
        row = lambda idx: next(r for r in library.rows(node, [], [], idx, {}) if r["name"] == "otter")  # noqa: E731
        self.assertTrue(row(self.index(dict(ENTRY, name="otter")))["repin"])
        self.assertIsNone(row(self.index(dict(ENTRY, name="otter", format=n)))["repin"])


if __name__ == "__main__":
    unittest.main()
