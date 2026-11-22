"""The Library however big the catalog grows (R256): the index's topics and
the day each entry was added are read, an index past what this build reads
says so rather than dropping the rest unsaid (B975), and one look at the
Library is narrowed, counted and paged on the server: the front page's
shelves of eight, a list a page at a time, every chip's count under the
other narrowings, and what runs only on other systems counted and left out
until asked for."""
import json
import os
import sys
import unittest

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))
import catalogindex  # noqa: E402
import library  # noqa: E402
import packformat  # noqa: E402

ENTRY = {"url": "https://example.com/p", "commit": "a" * 40, "sha256": "b" * 64, "tier": "vetted", "about": "a tool"}
KINDS = ("agent", "toolchain", "pack", "service", "app", "companion")


def catalog(n):
    """An index of n packs and a tenth as many apps, topics and days set."""
    topics = list(packformat.TOPICS)
    packs = [{**ENTRY, "name": f"p{i:05d}", "label": f"Pack {i}", "topics": [topics[i % len(topics)]],
              "added": f"2026-{1 + i % 12:02d}-{1 + i % 28:02d}", "platforms": ["linux/amd64"] if i % 7 else ["darwin/arm64"],
              "tier": "official" if i % 5 == 0 else "vetted"} for i in range(n)]
    packs += [{**ENTRY, "name": f"a{i:04d}", "kind": "app", "label": f"App {i}", "topics": ["media"]} for i in range(n // 10)]
    return packs


class Index(unittest.TestCase):
    def test_topics_and_the_day_added_are_read_and_a_word_not_the_catalogs_left_out(self):
        packs = [dict(ENTRY, name="one", topics=["media", "nope", "media", "web", "ai", "home"], added="2026-11-18"),
                 dict(ENTRY, name="two", topics="media", added="yesterday")]
        idx, why = catalogindex.parse(json.dumps({"version": 1, "packs": packs}).encode())
        self.assertEqual(why, "")
        self.assertEqual([(p.get("topics"), p.get("added")) for p in idx["packs"]],
                         [(["media", "web", "ai"], "2026-11-18"), (None, None)])
        self.assertEqual(packformat.topics_refused({"topics": ["media", "web"]}), "")
        self.assertIn("not one of the catalog's", packformat.topics_refused({"topics": ["films"]}))
        self.assertIn("one to 3", packformat.topics_refused({"topics": []}))
        self.assertEqual(packformat.topics_refused({}), "", "an entry not tagged yet passes")

    def test_an_index_past_what_this_build_reads_says_how_many_more(self):
        was = catalogindex.ENTRIES_MOST
        catalogindex.ENTRIES_MOST = 50
        self.addCleanup(setattr, catalogindex, "ENTRIES_MOST", was)
        idx, why = catalogindex.parse(json.dumps({"version": 1, "packs": catalog(60)}).encode())
        self.assertEqual((why, len(idx["packs"]), idx.get("past")), ("", 50, 16))
        self.assertGreaterEqual(was, 20000, "tens of thousands, where 2,000 was the most before")


class Browse(unittest.TestCase):
    def setUp(self):
        idx, _ = catalogindex.parse(json.dumps({"version": 1, "packs": catalog(3000)}).encode())
        self.rows = library.rows({"items": [], "platform": "linux/amd64"}, [], [], idx, {})

    def look(self, **k):
        return library.browse(self.rows, kinds=KINDS, **k)

    def test_the_front_page_is_shelves_of_eight_never_the_whole_catalog(self):
        b = self.look()
        self.assertEqual([(s["kind"], len(s["rows"])) for s in b["shelves"]], [("pack", 8), ("app", 8)])
        self.assertEqual(b["shelves"][0]["total"], 3000 - 429, "the ones for other systems left out of the count")
        self.assertTrue(all(r["tier"] == "official" for r in b["shelves"][0]["rows"]), "Packaged by Aerie first")
        self.assertNotIn("rows", b)
        self.assertLess(len(json.dumps(b)), 40000, "a few shelves, not 3,300 cards")

    def test_a_list_comes_a_page_at_a_time_in_its_order(self):
        b = self.look(kind="pack", sort="name", limit=30)
        self.assertEqual((len(b["rows"]), b["total"]), (30, 2571))
        nxt = self.look(kind="pack", sort="name", limit=30, offset=30)
        self.assertEqual(len({r["name"] for r in b["rows"]} & {r["name"] for r in nxt["rows"]}), 0, "the next page is the next 30")
        self.assertEqual(self.look(kind="pack", limit=500)["rows"].__len__(), library.PAGE_MOST, "a page is 60 at most")
        newest = self.look(kind="pack", sort="added", limit=5)["rows"]
        self.assertEqual([r["added_at"] for r in newest], sorted((r["added_at"] for r in newest), reverse=True))

    def test_every_chip_counts_under_the_other_narrowings(self):
        b = self.look(topic="media")
        self.assertEqual(b["counts"]["kind"]["app"], 300)
        self.assertEqual(b["counts"]["kind"]["pack"], sum(1 for r in self.rows if r["kind"] == "pack" and "media" in r.get("topics", []) and not r["wrong_platform"]))
        # The topics count under the kind and the source, not the topic picked,
        # so the pulldown says what each other one would give.
        self.assertEqual(sum(b["counts"]["topic"].values()), 2571 + 300, "every row here has one topic")
        self.assertEqual(set(b["counts"]["tier"]), {"official", "vetted"})

    def test_what_runs_only_elsewhere_is_counted_and_shown_when_asked(self):
        hid = self.look(kind="pack")
        shown = self.look(kind="pack", here=False)
        self.assertEqual((hid["hidden"], shown["hidden"], shown["total"] - hid["total"]), (429, 0, 429))
        self.assertEqual(hid["facts"]["other_platform"], 429)

    def test_a_search_puts_the_name_first(self):
        b = self.look(q="p00043")
        self.assertEqual(b["rows"][0]["name"], "p00043")
        self.assertEqual(self.look(q="pack 42 nothing-like-it")["total"], 0)


if __name__ == "__main__":
    unittest.main()
