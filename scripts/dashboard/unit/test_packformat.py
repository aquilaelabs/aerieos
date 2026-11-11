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
