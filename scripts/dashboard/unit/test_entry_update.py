"""Update, for a container that runs an image by digest, means that its
entry names another (containers.entry_moved, repin): the app it was made
from, as the Library holds it now, or the service of AerieOS's it is. A
kept app takes the catalog's newer definition when the signed index pins
another commit of it (nasapps.refresh); the row then says the image with
the short digest it would move to, Update moves the compose file's image
lines and nothing else of it, and the registry is not asked about an image
held by its digest. A container somebody wrote by hand keeps the
registry's check."""
import json
import os
import sys
import tempfile
import unittest
from pathlib import Path
from unittest import mock

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))
import containers  # noqa: E402
import devapp  # noqa: E402
import imagecheck  # noqa: E402
import nasapps  # noqa: E402
import packformat  # noqa: E402
import router  # noqa: E402
import services  # noqa: E402

A, B, C = ("sha256:" + c * 64 for c in "abc")
MADE = f"""# made from the Library
services:
  web:
    image: ex/web:2@{A}   # the app
    ports:
      - "${{PORT}}:80"
  db:
    image: ex/db:16@{C}
"""
ENTRY = MADE.replace(A, B)
SNAP = {"id": "site", "name": "Site", "fields": [], "own": ["PORT"]}


class Moved(unittest.TestCase):
    def test_an_image_its_entry_names_by_another_digest_is_moved_to_it(self):
        moved = containers.images_moved
        self.assertEqual(moved([f"ex/web:2@{A}", f"ex/db:16@{C}"], [f"ex/web:2@{B}", f"ex/db:16@{C}"]), {f"ex/web:2@{A}": f"ex/web:2@{B}"})
        self.assertEqual(moved([f"ex/web:2@{A}"], [f"ex/web:2@{A}"]), {}, "the digest it runs: nothing to move")
        self.assertEqual(moved([f"ex/web:2@{A}"], [f"ex/web:3@{B}"]), {f"ex/web:2@{A}": f"ex/web:3@{B}"}, "a newer version is another tag and another digest")
        self.assertEqual(moved(["ex/web:2"], [f"ex/web:2@{B}"]), {"ex/web:2": f"ex/web:2@{B}"}, "one still run by its tag alone takes its entry's digest")
        self.assertEqual(moved([f"ex/web:2@{A}"], ["ex/web:3"]), {}, "an entry that names no digest moves nothing here")
        self.assertEqual(moved([f"ex/web:2@{A}"], [f"ex/other:2@{B}"]), {}, "an image the entry does not name is left alone")
        self.assertEqual(moved([f"ex/web:2@{A}"], [f"ex/web:2@{B}", f"ex/web:3@{C}"]), {}, "...and one it names twice")


class Row(unittest.TestCase):
    """What a container's row is offered, and what its Update writes."""

    def app(self, compose=ENTRY, made=MADE, snap=SNAP):
        for target, name, value in ((containers, "app_of", lambda name: snap), (containers, "_compose_of", lambda name: made),
                                    (nasapps, "_all", lambda: {"site": {"compose": compose}} if compose else {}),
                                    (devapp, "owner_of", lambda p, i: ""), (devapp, "is_file_source", lambda p: True)):
            p = mock.patch.object(target, name, value)
            p.start()
            self.addCleanup(p.stop)

    def test_update_is_offered_when_the_entry_s_digest_moved_and_says_the_short_digest(self):
        self.app()
        moved = containers.entry_moved("site-1")
        self.assertEqual(moved, {f"ex/web:2@{A}": f"ex/web:2@{B}"})
        self.assertEqual([packformat.image_said(to) for to in moved.values()], ["ex/web:2 (" + "b" * 12 + ")"])

    def test_nothing_is_offered_while_the_entry_names_what_it_runs_or_is_gone(self):
        self.app(compose=MADE)
        self.assertEqual(containers.entry_moved("site-1"), {})
        self.app(compose="")
        self.assertEqual(containers.entry_moved("site-1"), {}, "the app is not in the Library any more")

    def test_a_container_written_by_hand_has_no_entry_and_keeps_the_registry_s_check(self):
        self.app(snap=None, made="services:\n  web:\n    image: ex/web:2\n")
        self.assertEqual(containers.entry_images("mine"), [])
        with mock.patch.object(devapp, "is_file_source", lambda p: False):
            self.assertEqual(containers.entry_moved("a-space"), {}, "a space's own container came from no entry")
        self.assertEqual(containers.entry_moved("mine"), {})
        self.assertEqual(containers.repin("mine"), {})
        self.assertEqual(imagecheck.parse_ref("ex/web:2"), (imagecheck.imageregistry.DEFAULT_HOST, "ex/web", "2"), "its tag is still asked of its registry")

    def test_the_registry_is_not_asked_about_an_image_held_by_its_digest(self):
        class Devapp:
            def _config(self, project, instance):
                return {}

            def _services(self, cfg):
                return {"web": {"image": f"ex/web:2@{A}"}, "db": {"image": "ex/db:16"}, "built": {"image": "ex/built:1", "build": {"context": "."}}}
        with mock.patch.object(imagecheck, "devapp", Devapp()):
            self.assertEqual(imagecheck.registry_images("site-1", "main"), [("db", "ex/db:16")],
                             "a newer build of a tag is no update for an image run by its digest")

    def test_update_moves_the_image_lines_and_nothing_else_of_the_file(self):
        self.app()
        wrote = []
        with mock.patch.object(containers, "update_container", lambda name, text, env: wrote.append((name, text, env)) or {"ok": True}), \
                mock.patch.object(devapp, "read_env", lambda name, inst: "PORT=8080\n"):
            self.assertEqual(containers.repin("site-1"), {}, "written: the pull is the row's update, still to run")
        self.assertEqual(wrote, [("site-1", MADE.replace(A, B), "PORT=8080\n")], "its comments, its other lines and its environment as they were")
        with mock.patch.object(containers, "update_container", lambda *a: {"error": "compose will not read that"}), \
                mock.patch.object(devapp, "read_env", lambda name, inst: ""):
            self.assertEqual(containers.repin("site-1"), {"error": "compose will not read that"})


class Service(unittest.TestCase):
    """One of AerieOS's own with no pin of its own: its row's Update writes
    its file again from its entry."""

    def test_a_service_s_row_is_offered_the_images_its_entry_names_now(self):
        self.assertTrue(services.updates("router"))
        self.assertFalse(services.updates("nginx"), "nginx is pinned on its record and moved from its own page and row")
        refs = services.images("model-router")
        made = "services:\n  litellm:\n    image: " + refs["litellm"].replace(packformat.image_digest(refs["litellm"]), A) + "\n  db:\n    image: " + refs["db"] + "\n"
        ran = []
        with mock.patch.object(devapp, "owner_of", lambda p, i: devapp.SYSTEM), mock.patch.object(devapp, "_instance_node", lambda p, i: "n1"), \
                mock.patch.object(devapp, "is_file_source", lambda p: True), \
                mock.patch.object(services, "container_names", lambda nid: {"router-box": "router", "nginx-box": "nginx"}), \
                mock.patch.object(containers, "_compose_of", lambda name: made), \
                mock.patch.object(router, "service_update", lambda nid, by="": ran.append(nid) or {"ok": True, "job": "j1"}):
            self.assertEqual(list(containers.entry_moved("router-box").values()), [refs["litellm"]])
            self.assertEqual(containers.entry_moved("nginx-box"), {})
            self.assertEqual(containers.repin("router-box"), {"done": {"ok": True, "job": "j1"}}, "its own module writes and rebuilds it")
        self.assertEqual(ran, ["n1"])


class Kept(unittest.TestCase):
    """A kept app takes the catalog's newer definition: the signed index
    pins another commit of its folder."""

    def setUp(self):
        self.tmp = Path(tempfile.mkdtemp())
        nasapps.configure(state=self.tmp, write_json=lambda p, d: Path(p).write_text(json.dumps(d)))
        nasapps._trying.clear()
        self.entry = {"name": "site", "kind": "app", "url": "https://example.com/catalog", "commit": "1" * 40, "sha256": "f" * 64,
                      "path": "packs/apps/site", "tier": "aerie", "format": 5}
        self.served = {"1" * 40: MADE, "2" * 40: ENTRY}
        self.asked = []

    def fetch(self, url, commit, sha256, path, names, cap=None):
        self.asked.append(commit)
        meta = {"name": "site", "label": "Site", "about": "A site.", "port": 8080, "format": 5, "framework": "5.2", "maker": "Example Labs"}
        return {"files": {"bbapp.json": json.dumps(meta).encode(), "compose.yml": self.served[commit].encode()}}

    def test_a_newer_pin_is_fetched_and_kept_and_who_kept_it_stays(self):
        self.assertEqual(nasapps.add_catalog(self.entry, by="ann", fetch=self.fetch).get("app"), "site")
        index = {"packs": [self.entry]}
        self.assertEqual(nasapps.wanted(index), [], "the pin it is kept at")
        newer = {**self.entry, "commit": "2" * 40}
        index = {"packs": [newer]}
        self.assertEqual([n for n, _ in nasapps.wanted(index)], ["site"])
        self.assertEqual(nasapps.refresh(index, self.fetch), [("site", "")])
        rec = nasapps._load()["site"]
        self.assertEqual((rec["compose"], rec["pin"]["commit"], rec["by"]), (ENTRY, "2" * 40, "ann"))
        self.assertEqual(nasapps.wanted(index), [])
        self.assertEqual(next(a for a in nasapps.catalog() if a["id"] == "site")["held"]["word"], "pinned")

    def test_only_its_own_folder_s_entry_is_taken_and_a_failure_waits_an_hour(self):
        nasapps.add_catalog(self.entry, by="ann", fetch=self.fetch)
        for other in ({"url": "https://example.com/other"}, {"path": "packs/apps/else"}, {"withdrawn": True}, {"kind": "pack"},
                      {"format": packformat.FORMAT + 1}):
            self.assertEqual(nasapps.wanted({"packs": [{**self.entry, "commit": "2" * 40, **other}]}), [], other)
        self.served["2" * 40] = MADE.replace(f"@{C}", "")
        index = {"packs": [{**self.entry, "commit": "2" * 40}]}
        said = nasapps.refresh(index, self.fetch)
        self.assertIn("names no digest", said[0][1], "a format 5 app that names an image by its tag alone is not taken")
        self.assertEqual(nasapps._load()["site"]["pin"]["commit"], "1" * 40, "and the one kept stays")
        asked = len(self.asked)
        self.assertEqual(nasapps.refresh(index, self.fetch), [], "asked again in an hour, not on every read")
        self.assertEqual(len(self.asked), asked)


if __name__ == "__main__":
    unittest.main()
