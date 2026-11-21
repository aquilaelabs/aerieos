"""The vetted catalog's index (R169 step 2): signed by the maintainers'
key, verified against the public half the install ships before an entry
is read, a tampered or re-signed index refused with the one before kept,
each entry held to its shape, and a withdrawn pack the install holds put
on the bell."""
import json
import os
import time
import shutil
import sys
import tempfile
import unittest
from unittest import mock

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))
import catalogindex  # noqa: E402

try:
    from cryptography.hazmat.primitives import serialization
    from cryptography.hazmat.primitives.asymmetric import ed25519
    HAVE = True
except ImportError:
    HAVE = False

ENTRY = {"name": "ghidra", "url": "https://example.com/packs/ghidra", "commit": "a" * 40, "sha256": "b" * 64, "tier": "vetted", "withdrawn": False,
         "about": "a decompiler", "platforms": ["linux/amd64"]}


@unittest.skipUnless(HAVE, "the cryptography library signs the test's index")
class Index(unittest.TestCase):
    def setUp(self):
        self.d = tempfile.mkdtemp()
        self.addCleanup(shutil.rmtree, self.d, True)
        catalogindex.configure(state=self.d)
        catalogindex._cache.update(at=0.0, index=None, error="")
        self.priv = ed25519.Ed25519PrivateKey.generate()
        self.pub = self.priv.public_key().public_bytes(serialization.Encoding.Raw, serialization.PublicFormat.Raw)
        pubfile = os.path.join(self.d, "catalog.pub")
        open(pubfile, "w").write("builderbot-catalog-ed25519 " + self.pub.hex() + "\n")
        catalogindex.PUB_FILE = pubfile

    def signed(self, packs, generated="2026-10-28T00:00:00Z"):
        """index.json and index.sig over it; `generated` None leaves the date out."""
        data = json.dumps({"version": 1, **({} if generated is None else {"generated": generated}), "packs": packs}).encode()
        sig = "builderbot-catalog-ed25519-signature " + self.priv.sign(data).hex() + "\n"
        return data, sig

    def served(self, packs, generated="2026-10-28T00:00:00Z"):
        """What stands in for the network: the catalog answering this index, signed."""
        data, sig = self.signed(packs, generated)
        files = {"index.json": data, "index.sig": sig.encode()}
        return lambda u: files[u.rsplit("/", 1)[1]]

    def on_disk(self):
        with open(os.path.join(self.d, "catalog-index.json"), encoding="utf-8") as f:
            return json.load(f)

    def test_an_older_signed_index_is_refused_and_the_kept_one_still_answers(self):
        # Whoever can answer at the catalog's address can serve an index the
        # maintainers signed once and have replaced since: its signature is
        # good, and what the catalog withdrew since would come back.
        url = "https://catalog.example/"
        now = catalogindex.fetch(url, opener=self.served([dict(ENTRY, withdrawn=True)], "2026-10-29T00:00:00Z"))
        self.assertNotIn("error", now, now)
        replay = self.served([ENTRY], "2026-10-28T23:59:59Z")
        r = catalogindex.fetch(url, opener=replay)
        self.assertEqual(r.get("error"), "the index the catalog answered is refused: it was made 2026-10-28T23:59:59Z, "
                                         "before the index kept here (2026-10-29T00:00:00Z); the one kept stays in use")
        self.assertEqual(r["index"]["generated"], "2026-10-29T00:00:00Z", "the one kept answers beside the reason")
        self.assertTrue(r["index"]["packs"][0]["withdrawn"])
        self.assertEqual(self.on_disk()["generated"], "2026-10-29T00:00:00Z", "and is what stays under the state")
        self.assertEqual(catalogindex.withdrawn(["ghidra"]), ["ghidra"], "what the catalog withdrew stays withdrawn")
        # As the Library reads it (server.py's catalog_error): the kept index
        # and the reason, on a press of Refresh and on the reads after it,
        # which do not ask again for five minutes.
        seen = catalogindex.index(url, fresh=True, opener=replay)
        self.assertIn("before the index kept here", seen["error"])
        self.assertEqual(seen["index"]["generated"], "2026-10-29T00:00:00Z")
        kept = self.on_disk()
        kept["fetched_at"] = 0
        with open(os.path.join(self.d, "catalog-index.json"), "w", encoding="utf-8") as f:
            json.dump(kept, f)
        catalogindex._cache.update(at=0.0, index=None)
        again = catalogindex.index(url, opener=down_fail)
        self.assertEqual((again["error"], again["index"]["generated"]), (seen["error"], "2026-10-29T00:00:00Z"))
        # After a restart the rule reads the copy under the state.
        catalogindex._cache.update(at=0.0, index=None, missed={})
        self.assertIn("before the index kept here", catalogindex.fetch(url, opener=replay)["error"])
        self.assertEqual(self.on_disk()["generated"], "2026-10-29T00:00:00Z")

    def test_a_newer_index_is_taken_and_one_of_the_same_moment_too(self):
        url = "https://catalog.example/"
        catalogindex.fetch(url, opener=self.served([ENTRY], "2026-10-29T00:00:00Z"))
        r = catalogindex.fetch(url, opener=self.served([ENTRY, dict(ENTRY, name="newer")], "2026-10-29T00:00:01Z"))
        self.assertNotIn("error", r, r)
        self.assertEqual((self.on_disk()["generated"], len(self.on_disk()["packs"])), ("2026-10-29T00:00:01Z", 2))
        # The same moment and other bytes: taken. The catalog's signing does
        # not stamp the index yet, so two indexes can carry one date, and an
        # install is not kept from the catalog's newest over that.
        same = catalogindex.fetch(url, opener=self.served([dict(ENTRY, name="other")], "2026-10-29T00:00:01Z"))
        self.assertNotIn("error", same, same)
        self.assertEqual([p["name"] for p in self.on_disk()["packs"]], ["other"])
        # ...and the same index read again is simply read again.
        self.assertNotIn("error", catalogindex.fetch(url, opener=self.served([dict(ENTRY, name="other")], "2026-10-29T00:00:01Z")))

    def test_an_index_that_does_not_say_when_it_was_made_is_no_way_round(self):
        url = "https://catalog.example/"
        catalogindex.fetch(url, opener=self.served([dict(ENTRY, withdrawn=True)], "2026-10-29T00:00:00Z"))
        # No date, an empty one, a word (which sorts after every date as
        # text), a day alone, a date that is none, a number, another zone,
        # a stamp with something after it.
        for odd in (None, "", "x", "zzzz", "2026-10-30", "2026-13-40T00:00:00Z", 20261030000000, "2026-10-30T00:00:00+00:00", "2026-10-30T00:00:00Z "):
            r = catalogindex.fetch(url, opener=self.served([ENTRY], odd))
            self.assertEqual(r.get("error"), "the index the catalog answered is refused: it does not say when it was made, "
                                             "and the index kept here was made 2026-10-29T00:00:00Z; the one kept stays in use", repr(odd))
            self.assertEqual(r["index"]["generated"], "2026-10-29T00:00:00Z", repr(odd))
            self.assertEqual(self.on_disk()["generated"], "2026-10-29T00:00:00Z", repr(odd))

    def test_with_nothing_dated_kept_there_is_nothing_to_be_older_than(self):
        # A first read takes what is signed, dated or not, and a kept index
        # with no date of its own gives way to any signed one: no install is
        # locked out of the catalog by what it holds.
        url = "https://catalog.example/"
        first = catalogindex.fetch(url, opener=self.served([ENTRY], None))
        self.assertNotIn("error", first, first)
        self.assertEqual(self.on_disk()["generated"], "")
        self.assertNotIn("error", catalogindex.fetch(url, opener=self.served([ENTRY], "x")))
        self.assertNotIn("error", catalogindex.fetch(url, opener=self.served([ENTRY], "2026-10-29T00:00:00Z")))
        # Once a dated one is kept, one with no date is refused again.
        self.assertIn("does not say when it was made", catalogindex.fetch(url, opener=self.served([ENTRY], None))["error"])
        # The index kept is one address's (B443): another catalog's first
        # answer is not measured against it.
        other = catalogindex.fetch("https://other.example/", opener=self.served([ENTRY], "2026-10-01T00:00:00Z"))
        self.assertNotIn("error", other, other)

    def test_the_mirror_answers_for_a_silent_catalog_only_when_it_is_not_the_older(self):
        # The one comparison (older) picks between the kept index and the
        # imported mirror's too.
        url = "https://catalog.example/"
        catalogindex.fetch(url, opener=self.served([ENTRY], "2026-10-29T00:00:00Z"))
        self.addCleanup(setattr, catalogindex, "mirror_index", None)

        def down(u):
            raise OSError("no route")
        for mirror_made, answers in (("2026-10-28T00:00:00Z", False), ("2026-10-29T00:00:00Z", True), ("2026-11-01T00:00:00Z", True), ("x", False), ("", False)):
            catalogindex.mirror_index = lambda g=mirror_made: {"generated": g, "packs": [], "mirror": True}
            got = catalogindex.fetch(url, opener=down)["index"]
            self.assertEqual(bool(got.get("mirror")), answers, mirror_made)

    def test_an_imported_mirror_is_a_floor_under_what_the_catalog_answers(self):
        # Two signed indexes and no word in either on which is the newest:
        # a mirror a person imported after the catalog's own was made
        # answers in its place, on the read that fetched, the reads after it
        # and the one a press makes without asking; what is kept for the
        # address stays the catalog's own, and a catalog that moves past the
        # mirror answers again.
        url = "https://catalog.example/"
        self.addCleanup(setattr, catalogindex, "mirror_index", None)
        catalogindex.mirror_index = lambda: {"generated": "2026-11-01T00:00:00Z", "packs": [], "mirror": True}
        got = catalogindex.fetch(url, self.served([ENTRY], "2026-10-28T00:00:00Z"))
        self.assertTrue(got["index"].get("mirror"), got)
        self.assertEqual(self.on_disk()["generated"], "2026-10-28T00:00:00Z")
        self.assertTrue(catalogindex.index(url)["index"].get("mirror"))
        self.assertTrue(catalogindex.known(url).get("mirror"))
        # ...and from the copy kept on disk, after a restart.
        catalogindex._cache.update(at=0.0, index=None, error="")
        self.assertTrue(catalogindex.index(url)["index"].get("mirror"))
        # The catalog's own, once it is the newer; one of the same moment as
        # the mirror is the catalog's too.
        for made in ("2026-11-01T00:00:00Z", "2026-11-02T00:00:00Z"):
            got = catalogindex.fetch(url, self.served([ENTRY], made))
            self.assertFalse(got["index"].get("mirror"), made)
            self.assertEqual(got["index"]["generated"], made)
        self.assertFalse(catalogindex.known(url).get("mirror"))
        # A mirror that says no date, or none imported, is no floor.
        catalogindex.mirror_index = lambda: {"packs": [], "mirror": True}
        self.assertFalse(catalogindex.index(url)["index"].get("mirror"))
        catalogindex.mirror_index = lambda: None
        self.assertFalse(catalogindex.index(url)["index"].get("mirror"))

    def test_a_signed_index_is_read_and_a_tampered_one_refused_with_the_last_kept(self):
        data, sig = self.signed([ENTRY, {"name": "Bad Name", "url": "https://x", "commit": "c" * 40, "sha256": "d" * 64}])
        files = {"index.json": data, "index.sig": sig.encode()}
        r = catalogindex.fetch("https://catalog.example/", opener=lambda u: files[u.rsplit("/", 1)[1]])
        self.assertNotIn("error", r, r)
        self.assertEqual([p["name"] for p in r["index"]["packs"]], ["ghidra"], "an entry out of shape is left out")
        self.assertEqual(r["index"]["packs"][0]["tier"], "vetted")
        self.assertTrue(os.path.exists(os.path.join(self.d, "catalog-index.json")))
        # Changed on the way: refused, the one before answered beside the reason.
        tampered = data.replace(b'"withdrawn": false', b'"withdrawn": true')
        files2 = {"index.json": tampered, "index.sig": sig.encode()}
        r2 = catalogindex.fetch("https://catalog.example/", opener=lambda u: files2[u.rsplit("/", 1)[1]])
        self.assertIn("does not match", r2["error"])
        self.assertEqual([p["name"] for p in r2["index"]["packs"]], ["ghidra"], "the index kept before stands")
        # Signed by another key: the same refusal.
        other = ed25519.Ed25519PrivateKey.generate()
        files3 = {"index.json": data, "index.sig": ("builderbot-catalog-ed25519-signature " + other.sign(data).hex()).encode()}
        self.assertIn("does not match", catalogindex.fetch("https://catalog.example/", opener=lambda u: files3[u.rsplit("/", 1)[1]])["error"])
        # The network gone: the one before, with the reason.
        def down(u):
            raise OSError("no route")
        r4 = catalogindex.fetch("https://catalog.example/", opener=down)
        self.assertIn("did not answer", r4["error"])
        self.assertEqual(len(r4["index"]["packs"]), 1)
        # Another address under Controller settings: neither the cache nor
        # the kept index is the old catalog's answer (B443).
        r5 = catalogindex.index("https://other.example/", opener=down)
        self.assertIn("did not answer", r5["error"])
        self.assertIsNone(r5["index"])
        self.assertEqual(len(catalogindex.index("https://catalog.example/", opener=down)["index"]["packs"]), 1)

    def test_the_index_as_last_read_is_answered_without_asking(self):
        # What a press on Update reads: never the network.
        self.assertIsNone(catalogindex.known("https://catalog.example/"))
        data, sig = self.signed([ENTRY])
        catalogindex.fetch("https://catalog.example/", opener=lambda u: data if u.endswith("index.json") else sig.encode())
        asked = []
        real = catalogindex.urllib.request.urlopen
        catalogindex.urllib.request.urlopen = lambda *a, **k: asked.append(a) or (_ for _ in ()).throw(OSError("asked"))
        self.addCleanup(setattr, catalogindex.urllib.request, "urlopen", real)
        self.assertEqual([p["name"] for p in catalogindex.known("https://catalog.example/")["packs"]], ["ghidra"])
        catalogindex._cache.update(at=0.0, index=None, error="")
        self.assertEqual([p["name"] for p in catalogindex.known("https://catalog.example/")["packs"]], ["ghidra"], "from the copy kept under the state")
        self.assertIsNone(catalogindex.known("https://other.example/"))
        self.assertEqual(asked, [])

    def test_when_the_index_in_use_was_made_is_said_where_a_person_sees_it(self):
        # An address that keeps answering one signed index never brings a
        # newer one, and nothing expires it: Controller settings' Vetted
        # catalog group says when the index in use was made, with when it
        # was read, from what is kept and never from the network.
        self.assertIsNone(catalogindex.said("https://catalog.example/"), "none read yet")
        before = int(time.time())
        catalogindex.fetch("https://catalog.example/", opener=self.served([ENTRY], "2026-10-28T00:00:00Z"))
        asked = []
        real = catalogindex.urllib.request.urlopen
        catalogindex.urllib.request.urlopen = lambda *a, **k: asked.append(a) or (_ for _ in ()).throw(OSError("asked"))
        self.addCleanup(setattr, catalogindex.urllib.request, "urlopen", real)
        got = catalogindex.said("https://catalog.example/")
        self.assertEqual(got["made"], "2026-10-28T00:00:00Z")
        self.assertGreaterEqual(got["read"], before)
        # The same index answered again weeks later is still the one made then.
        catalogindex._cache.update(at=0.0, index=None, error="")
        self.assertEqual(catalogindex.said("https://catalog.example/")["made"], "2026-10-28T00:00:00Z", "from the copy kept under the state")
        self.assertEqual(asked, [])
        # One that does not say when it was made says so as nothing, never as a word that reads like a date.
        with mock.patch.object(catalogindex, "known", lambda url=None: {"generated": "soon", "packs": []}):
            self.assertEqual(catalogindex.said(), {"made": "", "read": 0})
        # The page draws it in the group's own words, and the status hands it to an administrator alone.
        dash = os.path.join(os.path.dirname(__file__), "..")
        with open(os.path.join(dash, "tab-settings.js"), encoding="utf-8") as f:
            page = f.read()
        self.assertIn('`The index in use was made ${esc(i.made || "at an unknown time")}${i.read ? `, read ${esc(ago(i.read))}` : ""}.`', page)
        with open(os.path.join(dash, "server.py"), encoding="utf-8") as f:
            self.assertIn('"catalog_index": catalogindex.said(settings.get("catalog_url") or None) if users.is_admin(who) else None,', f.read())

    def test_an_index_signed_by_the_spare_is_read_as_one_signed_by_the_key(self):
        # R232: the install ships the key and its spare; an index signed by
        # either is read, and a third key's is still refused.
        data, sig = self.signed([ENTRY])
        spare = ed25519.Ed25519PrivateKey.generate()
        spare_pub = spare.public_key().public_bytes(serialization.Encoding.Raw, serialization.PublicFormat.Raw)
        other = ed25519.Ed25519PrivateKey.generate()
        open(catalogindex.PUB_FILE, "a").write("builderbot-catalog-ed25519 " + spare_pub.hex() + "\n")
        self.assertEqual(catalogindex._pubkeys(), [self.pub, spare_pub])
        self.assertEqual(catalogindex.verify(data, sig), "")
        self.assertEqual(catalogindex.verify(data, "builderbot-catalog-ed25519-signature " + spare.sign(data).hex()), "")
        self.assertIn("does not match", catalogindex.verify(data, "builderbot-catalog-ed25519-signature " + other.sign(data).hex()))
        # A file of three keys, or one with a line that is not a key, is no key at all.
        open(catalogindex.PUB_FILE, "a").write("builderbot-catalog-ed25519 " + spare_pub.hex() + "\n")
        self.assertEqual(catalogindex._pubkeys(), [])
        self.assertIn("ships no catalog key", catalogindex.verify(data, sig))

    def test_without_a_shipped_key_nothing_is_trusted(self):
        catalogindex.PUB_FILE = os.path.join(self.d, "none.pub")
        data, sig = self.signed([ENTRY])
        self.assertIn("ships no catalog key", catalogindex.verify(data, sig))

    def test_a_withdrawn_pack_the_install_holds_is_on_the_bell(self):
        data, sig = self.signed([dict(ENTRY, withdrawn=True), dict(ENTRY, name="fine")])
        files = {"index.json": data, "index.sig": sig.encode()}
        catalogindex.fetch("https://catalog.example/", opener=lambda u: files[u.rsplit("/", 1)[1]])
        self.assertEqual(catalogindex.withdrawn(["ghidra", "fine", "other"]), ["ghidra"])
        rows = catalogindex.attention(["ghidra", "fine"])
        self.assertEqual((rows[0]["kind"], rows[0]["name"], rows[0]["key"]), ("pack", "ghidra", "pack:withdrawn:ghidra"))
        self.assertIn("remove it", rows[0]["said"])
        # Within the hour the kept copy answers without the network.
        self.assertEqual(len(catalogindex.index("https://catalog.example/", opener=down_fail)["index"]["packs"]), 2)


def down_fail(u):
    raise AssertionError("the kept index should have answered")


class Made(unittest.TestCase):
    def test_an_index_s_date_is_read_as_a_time_and_compared_one_way(self):
        made, older = catalogindex.made, catalogindex.older
        self.assertEqual(made({"generated": "1970-01-01T00:00:10Z"}), 10)
        self.assertLess(made({"generated": "2026-10-28T23:59:59Z"}), made({"generated": "2026-10-29T00:00:00Z"}))
        for odd in (None, {}, {"generated": None}, {"generated": ""}, {"generated": "x"}, {"generated": 7}, {"generated": "2026-02-30T00:00:00Z"},
                    {"generated": "2026-10-29 00:00:00Z"}, {"generated": "2026-10-29T00:00:00"}, {"generated": "2026-10-29T00:00:00Z\n"}):
            self.assertIsNone(made(odd), odd)
        new, old = {"generated": "2026-10-29T00:00:00Z"}, {"generated": "2026-10-28T00:00:00Z"}
        self.assertEqual(older(new, old), "")
        self.assertEqual(older(new, dict(new, packs=[1])), "", "the same moment is not older")
        self.assertEqual(older(old, new), "it was made 2026-10-28T00:00:00Z, before the index kept here (2026-10-29T00:00:00Z)")
        self.assertEqual(older(old, new, "the mirror held here"), "it was made 2026-10-28T00:00:00Z, before the mirror held here (2026-10-29T00:00:00Z)")
        self.assertEqual(older({"generated": "zzzz"}, new), "it does not say when it was made, and the index kept here was made 2026-10-29T00:00:00Z")
        self.assertEqual(older(old, None), "")
        self.assertEqual(older(old, {"generated": "zzzz"}), "", "a kept index with no date refuses nothing")
        self.assertEqual(older({}, {}), "")

    def test_a_release_says_the_oldest_index_it_takes(self):
        # An install that holds none yet has nothing to be older than: the
        # file beside the maintainers' key says the oldest it takes.
        older, floor = catalogindex.older, catalogindex.floor
        d = tempfile.mkdtemp()
        self.addCleanup(shutil.rmtree, d, True)
        was = catalogindex.PUB_FILE
        catalogindex.PUB_FILE = os.path.join(d, "catalog.pub")
        self.addCleanup(setattr, catalogindex, "PUB_FILE", was)
        self.assertEqual(floor(), (None, ""), "no file: no floor")
        self.assertEqual(older({"generated": "2020-01-01T00:00:00Z"}, None), "")
        with open(os.path.join(d, "catalog-floor"), "w") as f:
            f.write("# the oldest taken\n2026-10-29T00:00:00Z\n")
        self.assertEqual(floor()[1], "2026-10-29T00:00:00Z")
        self.assertEqual(older({"generated": "2026-10-28T23:59:59Z"}, None),
                         "it was made 2026-10-28T23:59:59Z, before the oldest this AerieOS takes (2026-10-29T00:00:00Z)")
        self.assertIn("does not say when it was made", older({"packs": []}, None))
        self.assertEqual(older({"generated": "2026-10-29T00:00:00Z"}, None), "", "the floor's own moment is taken")
        self.assertEqual(older({"generated": "2026-10-30T00:00:00Z"}, {"generated": "2026-10-29T12:00:00Z"}), "")
        for junk in ("", "soon\n", "2026-10-29T00:00:00Z\n2026-10-30T00:00:00Z\n", "2026-13-45T00:00:00Z\n"):
            with open(os.path.join(d, "catalog-floor"), "w") as f:
                f.write(junk)
            self.assertEqual(floor(), (None, ""), junk)

    def test_the_floor_this_tree_ships_is_a_moment_and_not_ahead_of_today(self):
        root = os.path.dirname(os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))))
        was = catalogindex.PUB_FILE
        catalogindex.PUB_FILE = os.path.join(root, "config", "catalog.pub")
        self.addCleanup(setattr, catalogindex, "PUB_FILE", was)
        when, said = catalogindex.floor()
        self.assertIsNotNone(when, "config/catalog-floor is one line, a moment as an index says its own")
        self.assertLess(when, time.time())
        self.assertIn("COPY config/catalog-floor /opt/aerieos/config/catalog-floor\n", open(os.path.join(root, "Dockerfile")).read())


class Folders(unittest.TestCase):
    def test_an_entry_in_a_folder_keeps_its_path_and_a_bad_one_is_dropped(self):
        # R170 step 6: the catalog's own packs live in folders of its repository.
        good = {**ENTRY, "name": "jdk", "path": "packs/official/jdk", "kind": "app"}
        bad = {**ENTRY, "name": "evil", "path": "../etc"}
        plain = {**ENTRY, "name": "plain"}
        idx, why = catalogindex.parse(json.dumps({"version": 1, "generated": "x", "packs": [good, bad, plain]}).encode())
        self.assertEqual(why, "")
        self.assertEqual([(p["name"], p["path"], p["kind"]) for p in idx["packs"]], [("jdk", "packs/official/jdk", "app"), ("plain", "", "pack")])


class Kinds(unittest.TestCase):
    def test_an_entrys_kind_and_folder_are_kept(self):
        # R170 steps 6 and 7, R172: a pack, a Docker app or a service, in a folder of its repository.
        rows = [{**ENTRY, "name": "jdk", "path": "packs/official/jdk"}, {**ENTRY, "name": "whoami", "kind": "app", "path": "packs/apps/whoami"},
                {**ENTRY, "name": "model-router", "kind": "service"}, {**ENTRY, "name": "evil", "path": "../etc"}, {**ENTRY, "name": "odd", "kind": "thing"}]
        idx, why = catalogindex.parse(json.dumps({"version": 1, "generated": "x", "packs": rows}).encode())
        self.assertEqual(why, "")
        self.assertEqual([(p["name"], p["kind"], p["path"]) for p in idx["packs"]],
                         [("jdk", "pack", "packs/official/jdk"), ("whoami", "app", "packs/apps/whoami"), ("model-router", "service", ""), ("odd", "pack", "")])



class Shipped(unittest.TestCase):
    def test_a_coding_agent_s_entry_says_its_recipe_s_rev(self):
        # R169 step 13: an install fetches an agent's pack only when the
        # index says its install recipe is newer than the release's.
        packs = [dict(ENTRY, name="open", tier="official", path="packs/agents/open", install_rev=3),
                 dict(ENTRY, name="grok", tier="official", path="packs/agents/grok", install_rev="3"),
                 dict(ENTRY, name="codex", tier="official", path="packs/agents/codex", install_rev=True),
                 ENTRY]
        idx, why = catalogindex.parse(json.dumps({"version": 1, "packs": packs}).encode())
        self.assertEqual(why, "")
        self.assertEqual([p.get("install_rev") for p in idx["packs"]], [3, None, None, None])

    def test_a_pack_that_brings_a_coding_agent_keeps_its_mark(self):
        # The Library files its card with the agents before it is installed.
        packs = [dict(ENTRY, name="gemini", agent=True), dict(ENTRY, name="otter", agent="yes"), ENTRY]
        idx, why = catalogindex.parse(json.dumps({"version": 1, "packs": packs}).encode())
        self.assertEqual(why, "")
        self.assertEqual([p.get("agent") for p in idx["packs"]], [True, None, None])

    def test_an_entry_s_label_is_what_its_card_is_called_before_it_is_kept(self):
        import library
        idx, why = catalogindex.parse(json.dumps({"version": 1, "packs": [dict(ENTRY, name="gemini", label=" Gemini "), dict(ENTRY, name="otter", label=7)]}).encode())
        self.assertEqual(why, "")
        self.assertEqual([p.get("label") for p in idx["packs"]], ["Gemini", None])
        by = {r["name"]: r["label"] for r in library.rows({"items": []}, [], [], idx, {})}
        self.assertEqual(by, {"gemini": "Gemini", "otter": "otter"})

    def test_the_image_carries_the_key_the_index_is_checked_against(self):
        # Left out, every released install said it ships no catalog key and
        # trusted no index (B451); a bare-metal install lays out by the same lines.
        root = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", "..", ".."))
        with open(os.path.join(root, "Dockerfile"), encoding="utf-8") as f:
            self.assertIn("COPY config/catalog.pub /opt/aerieos/config/catalog.pub", f.read())
        self.assertIsNotNone(catalogindex._pubkey(os.path.join(root, "config", "catalog.pub")))
        # ...with its spare on the second line (R232), a key of its own.
        keys = catalogindex._pubkeys(os.path.join(root, "config", "catalog.pub"))
        self.assertEqual(len(set(keys)), 2, "the repository names a spare for the catalog's key")


if __name__ == "__main__":
    unittest.main()
