"""What an offer's downloads are held to, said before it is added (pack
format 5): an index entry carries the word its manifest reads (`held`:
pinned, installer or open) and, for an installer, the manifest's own
sentence (`online`); the index's parse keeps both, and the Library's row
for an entry not kept here carries `held` in the shape a kept pack's and
a kept app's row has, {word, why}."""
import json
import os
import sys
import unittest

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))
import catalogindex  # noqa: E402
import library  # noqa: E402
import nasapps  # noqa: E402
import packformat  # noqa: E402
import toolpacks  # noqa: E402

SENTENCE = "Its installer downloads the SDK's packages from dl.example.com by itself."
PACK = {"name": "hexkit", "label": "Hex kit", "about": "Looks inside binaries.", "platforms": ["linux/amd64"], "format": 5,
        "install": {"steps": [["sh", "{dir}/install.sh"]], "fetch": [{"url": "https://dl.example.com/hexkit.tgz", "sha256": "a" * 64, "to": "hexkit.tgz"}]},
        "layout": {"bin": ["bin"], "tool": "bin/hexkit"},
        "verbs": {"dump": {"about": "A file's bytes as hex.", "usage": "FILE", "run": ["{dir}/bin/hexkit", "dump", "{args}"]}}}
DIGEST = "sha256:" + "c" * 64


def entry(name="hexkit", **more):
    return {"name": name, "url": "https://example.com/hexkit", "path": f"packs/{name}", "commit": "1" * 40, "sha256": "b" * 64, "tier": "vetted",
            "about": "Looks inside binaries.", "platforms": ["linux/amd64"], "format": 5, **more}


def parsed(*entries):
    idx, why = catalogindex.parse(json.dumps({"version": 1, "packs": list(entries)}).encode())
    assert not why, why
    return idx


def held_of(manifest):
    clean, errors = toolpacks.validate(manifest)
    assert not errors, errors
    return packformat.held_of(clean)


class Word(unittest.TestCase):
    def test_what_an_entry_says_of_each_manifest(self):
        pinned = held_of(PACK)
        self.assertEqual(packformat.held_entry(pinned), {"held": "pinned"})
        installer = held_of({**PACK, "install": {**PACK["install"], "online": "  " + SENTENCE.replace(" by ", "   by ") + " "}})
        self.assertEqual(packformat.held_entry(installer), {"held": "installer", "online": SENTENCE})
        opened = held_of({**PACK, "format": 1, "install": {"steps": PACK["install"]["steps"]}})
        self.assertEqual(packformat.held_entry(opened), {"held": "open"}, "what is held to nothing is the manifest's to say, not the entry's")
        self.assertEqual(packformat.held_entry(packformat.held({"service": {}, "images": {"web": "nginx:1.27@" + DIGEST}})), {"held": "pinned"})
        self.assertEqual(packformat.held_entry({"word": "sealed", "why": "a later build's word"}), {})
        self.assertEqual(packformat.held_entry(None), {})

    def test_an_app_s_word_is_its_images(self):
        compose = f"services:\n  web:\n    image: traefik/whoami:v1.10.4@{DIGEST}\n"
        self.assertEqual(packformat.held_entry(nasapps.held_of({"compose": compose})), {"held": "pinned"})
        self.assertEqual(packformat.held_entry(nasapps.held_of({"compose": compose.replace("@" + DIGEST, "")})), {"held": "open"})

    def test_parse_keeps_the_word_and_an_installer_s_sentence(self):
        got = {e["name"]: e for e in parsed(
            entry("pinned", held="pinned", online=SENTENCE), entry("installer", held="installer", online=SENTENCE), entry("bare", held="installer"),
            entry("opened", held="open"), entry("later", held="sealed"), entry("none"), entry("odd", held="installer", online="<b>"),
            entry("moved", format=6, held="pinned", older=[{"format": 5, "commit": "2" * 40, "sha256": "d" * 64, "held": "installer", "online": SENTENCE}]),
        )["packs"]}
        self.assertEqual({n: (e.get("held"), e.get("online")) for n, e in got.items() if n != "moved"},
                         {"pinned": ("pinned", None), "installer": ("installer", SENTENCE), "bare": ("installer", None), "opened": ("open", None),
                          "later": (None, None), "none": (None, None), "odd": ("installer", None)})
        # The word is the pinned manifest's: an older pin says its own.
        self.assertEqual((got["moved"]["held"], got["moved"]["older"][0]["held"], got["moved"]["older"][0]["online"]), ("pinned", "installer", SENTENCE))
        at5 = packformat.pin_for(got["moved"], reads=5)
        self.assertEqual((at5["held"], at5["online"]), ("installer", SENTENCE))
        self.assertEqual((packformat.pin_for(got["moved"], reads=6)["held"], packformat.pin_for(got["moved"], reads=6).get("online")), ("pinned", None))

    def test_an_offer_s_row_carries_the_word_and_why(self):
        idx = parsed(entry("pinned", held="pinned"), entry("installer", held="installer", online=SENTENCE), entry("bare", held="installer"),
                     entry("opened", held="open"), entry("none"), entry("whoami", kind="app", held="pinned"), entry("loose", kind="app", held="open"))
        rows = {r["name"]: r for r in library.rows({"items": [], "platform": "linux/amd64"}, [], [], idx, {})}
        self.assertEqual({n: r["held"] for n, r in rows.items()}, {
            "pinned": {"word": "pinned", "why": packformat.PINNED_SAID},
            "installer": {"word": "installer", "why": SENTENCE},
            "bare": {"word": "installer", "why": packformat.OFFER_INSTALLER},
            "opened": {"word": "open", "why": packformat.OFFER_OPEN},
            "none": None,
            "whoami": {"word": "pinned", "why": packformat.IMAGES_SAID},
            "loose": {"word": "open", "why": packformat.OFFER_OPEN}})
        for r in rows.values():
            for line in ([r["held"]["why"]] if r["held"] else []):
                self.assertLessEqual(len(line), packformat.ONLINE_MAX)
                self.assertNotIn("\n", line)

    def test_an_offer_reads_as_the_pack_kept_from_it_would(self):
        # The word on an offer is the word the same manifest's card says
        # once it is kept, and an installer's sentence is the same sentence.
        for manifest in (PACK, {**PACK, "install": {**PACK["install"], "online": SENTENCE}}, {**PACK, "format": 1, "install": {"steps": PACK["install"]["steps"]}}):
            kept = held_of(manifest)
            offer = packformat.held_offer(parsed(entry(**packformat.held_entry(kept)))["packs"][0])
            self.assertEqual(offer["word"], kept["word"])
            if kept["word"] != "open":
                self.assertEqual(offer["why"], kept["why"])


if __name__ == "__main__":
    unittest.main()
