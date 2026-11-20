"""tools/pins.py over images: a container image is held by the digest of
what is pulled, and the tool moves that pin as it moves a download's.
Against a table of made-up services and a compose file, with a stand-in
answering in the registries' place: check says where a tag serves another
digest and writes nothing, move writes the digest the tag serves now and
raises the row's rev, a tag whose list lacks a platform the row needs
holds the row, pin gives an image its first digest, verify reads each
pinned manifest by its digest, and a compose file's image lines are
rewritten with nothing else of it touched."""
import hashlib
import importlib.util
import json
import os
import shutil
import sys
import tempfile
import unittest

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))
import imageregistry  # noqa: E402
import packformat  # noqa: E402
import services  # noqa: E402
from sdkstore import REPO  # noqa: E402
from test_imageregistry import Registry  # noqa: E402

spec = importlib.util.spec_from_file_location("pins_tool", os.path.join(REPO, "tools", "pins.py"))
pins = importlib.util.module_from_spec(spec)
spec.loader.exec_module(pins)


def listed(*plats, salt=""):
    """A manifest list's bytes for those platforms, and its digest."""
    body = json.dumps({"schemaVersion": 2, "mediaType": imageregistry.INDEXES[0], "salt": salt, "manifests": [
        {"digest": "sha256:" + hashlib.sha256(p.encode()).hexdigest(), "platform": dict(zip(("os", "architecture"), p.split("/"), strict=True))} for p in plats]}).encode()
    return body, "sha256:" + hashlib.sha256(body).hexdigest()


BOTH = ("linux/amd64", "linux/arm64")
WEB, WEB_D = listed(*BOTH)
DB, DB_D = listed(*BOTH, salt="db")
NEWER, NEWER_D = listed(*BOTH, salt="rebuilt")
ONE_ARCH, ONE_ARCH_D = listed("linux/amd64", salt="amd64 alone")

COMPOSE = f"""# an app
services:
  web:
    image: reg.example/app/web:1.2@{WEB_D}   # the app itself
    ports:
      - "${{PORT}}:80"
  db:
    image: "db:16"
    environment:
      NOTE: 'image: db:16'
"""


class Case(unittest.TestCase):
    def setUp(self):
        self.d = tempfile.mkdtemp()
        self.addCleanup(shutil.rmtree, self.d, True)
        self.table = os.path.join(self.d, "service-images.json")
        self.manifests = {("reg.example", "app/web", "1.2"): WEB, ("reg.example", "app/web", WEB_D): WEB,
                          (imageregistry.DEFAULT_HOST, "library/db", "16"): DB, (imageregistry.DEFAULT_HOST, "library/db", DB_D): DB}
        self.registry = Registry(self.manifests, realm="https://auth.example/token")
        self.addCleanup(setattr, imageregistry, "_open", imageregistry._open)
        imageregistry._open = self.registry
        self.rows = [{"name": "site", "rev": 3, "platforms": list(BOTH),
                      "images": {"web": f"reg.example/app/web:1.2@{WEB_D}", "db": f"db:16@{DB_D}"}}]
        self.write()

    def write(self):
        pins.save(self.table, {"_comment": "made up", "services": self.rows})

    def read(self):
        with open(self.table, encoding="utf-8") as f:
            return f.read()

    def run_tool(self, *argv):
        out = []
        return pins.main([*argv, "--file", self.table], out.append), "\n".join(out)

    def rebuilt(self):
        """The tag 1.2 served anew: another list, under another digest."""
        self.manifests[("reg.example", "app/web", "1.2")] = NEWER
        self.manifests[("reg.example", "app/web", NEWER_D)] = NEWER


class Check(Case):
    def test_nothing_would_move_and_nothing_is_written(self):
        was = self.read()
        code, said = self.run_tool("check")
        self.assertEqual(code, 0, said)
        self.assertIn(f"site: its image web is at 1.2 {WEB_D[7:19]} (its registry serves the digest it is pinned to)", said)
        self.assertIn("nothing would move", said)
        self.assertEqual(self.read(), was)
        self.assertTrue(all(m == "HEAD" or "auth.example" in u for m, u, _ in self.registry.asked), "a tag at its pin is asked for its digest and nothing more")

    def test_it_says_a_tag_that_serves_another_digest_and_exits_3(self):
        self.rebuilt()
        was = self.read()
        code, said = self.run_tool("check")
        self.assertEqual(code, 3, said)
        self.assertIn(f"site: its image web 1.2 {WEB_D[7:19]} to 1.2 {NEWER_D[7:19]} (read from its registry: a list for linux/amd64, linux/arm64)", said)
        self.assertIn("1 row(s) would move", said)
        self.assertEqual(self.read(), was, "check writes nothing")

    def test_a_tag_that_does_not_exist_is_said_by_name_and_exits_1(self):
        self.rows[0]["images"]["web"] = f"reg.example/app/web:9.9@{WEB_D}"
        self.write()
        code, said = self.run_tool("check")
        self.assertEqual(code, 1, said)
        self.assertIn("site: could not be asked: its image web could not be learned (reg.example has no app/web:9.9)", said)

    def test_a_list_that_lacks_a_platform_the_row_needs_holds_it_where_it_is(self):
        self.manifests[("reg.example", "app/web", "1.2")] = ONE_ARCH
        self.manifests[("reg.example", "app/web", ONE_ARCH_D)] = ONE_ARCH
        code, said = self.run_tool("check")
        self.assertEqual(code, 0, said)
        self.assertIn("reg.example/app/web:1.2 is served for linux/amd64 now, and not for linux/arm64: it stays where it is", said)
        self.assertIn("1 row(s) wait", said)
        code, said = self.run_tool("move")
        self.assertEqual(code, 1, said)
        self.assertIn("site: left as it was", said)
        self.assertIn(WEB_D, self.read())


class Move(Case):
    def test_it_writes_the_digest_the_tag_serves_now_and_raises_the_rev(self):
        self.rebuilt()
        was = self.read()
        code, said = self.run_tool("move")
        self.assertEqual(code, 0, said)
        self.assertIn("site: rev 3 to 4", said)
        now = self.read()
        self.assertEqual(now, was.replace(WEB_D, NEWER_D).replace('"rev": 3', '"rev": 4'), "the digest and the rev, and no other line")
        self.assertEqual(self.run_tool("check")[0], 0, "and then nothing would move")

    def test_pin_gives_an_image_written_with_its_tag_alone_its_first_digest(self):
        self.rows[0]["images"]["db"] = "db:16"
        self.write()
        code, said = self.run_tool("check", "site")
        self.assertIn("site: not pinned (db:16 names no digest)", said)
        code, said = self.run_tool("move", "site")
        self.assertEqual(code, 1, "a row with an image not pinned yet is pin's")
        code, said = self.run_tool("pin", "site")
        self.assertEqual(code, 0, said)
        self.assertIn(f"site: its image db pinned at 16 {DB_D[7:19]}", said)
        self.assertEqual(json.loads(self.read())["services"][0]["images"], {"web": f"reg.example/app/web:1.2@{WEB_D}", "db": f"db:16@{DB_D}"})
        self.assertIn("pinned already", self.run_tool("pin", "site")[1])


class Verify(Case):
    def test_each_pinned_manifest_is_read_by_its_digest(self):
        code, said = self.run_tool("verify")
        self.assertEqual(code, 0, said)
        self.assertIn(f"site: its image web is its pin (a list for linux/amd64, linux/arm64, sha256 {WEB_D[7:19]})", said)
        self.assertTrue(any(u.endswith(f"/manifests/{WEB_D}") for _, u, _ in self.registry.asked), "by the digest, never the tag beside it")

    def test_one_its_registry_no_longer_serves_fails_naming_it(self):
        del self.manifests[(imageregistry.DEFAULT_HOST, "library/db", DB_D)]
        code, said = self.run_tool("verify")
        self.assertEqual(code, 1, said)
        self.assertIn(f"site: NOT VERIFIED: its image db, db:16@{DB_D}", said)

    def test_a_list_that_is_not_for_the_platform_asked_fails(self):
        self.rows[0]["images"]["web"] = f"reg.example/app/web:1.2@{ONE_ARCH_D}"
        self.manifests[("reg.example", "app/web", ONE_ARCH_D)] = ONE_ARCH
        self.write()
        code, said = self.run_tool("verify", "--platform", "linux/arm64")
        self.assertEqual(code, 1, said)
        self.assertIn("is a list for linux/amd64, and not for linux/arm64", said)


class Compose(Case):
    """A compose file in the table's place: a Docker app's, in the catalog."""

    def setUp(self):
        super().setUp()
        os.mkdir(os.path.join(self.d, "notes"))
        self.file = os.path.join(self.d, "notes", "compose.yml")
        with open(self.file, "w", encoding="utf-8") as f:
            f.write(COMPOSE)

    def tool(self, *argv):
        out = []
        return pins.main([*argv, "--compose", self.file], out.append), "\n".join(out)

    def text(self):
        with open(self.file, encoding="utf-8") as f:
            return f.read()

    def test_an_image_with_no_digest_is_pinned_and_only_its_line_changes(self):
        code, said = self.tool("check")
        self.assertIn("notes: not pinned (db:16 names no digest)", said, "the row is named for the file's folder")
        self.assertEqual(self.text(), COMPOSE)
        code, said = self.tool("pin")
        self.assertEqual(code, 0, said)
        self.assertIn(f"notes: db pinned at 16 {DB_D[7:19]}", said)
        self.assertEqual(self.text(), COMPOSE.replace('image: "db:16"', f'image: "db:16@{DB_D}"'), "its comments, its quotes and every other line as they were")

    def test_check_and_move_ask_each_image_s_tag(self):
        self.tool("pin")
        self.assertEqual(self.tool("check")[0], 0)
        self.rebuilt()
        code, said = self.tool("check")
        self.assertEqual(code, 3, said)
        self.assertIn(f"notes: reg.example/app/web 1.2 {WEB_D[7:19]} to 1.2 {NEWER_D[7:19]}", said)
        pinned = self.text()
        code, said = self.tool("move")
        self.assertEqual(code, 0, said)
        self.assertEqual(self.text(), pinned.replace(WEB_D, NEWER_D))
        self.assertNotIn("rev", said, "a compose file has no rev to raise")
        self.assertEqual(self.tool("verify")[0], 0)

    def test_a_file_that_names_no_image_is_said(self):
        with open(self.file, "w", encoding="utf-8") as f:
            f.write("services: {}\n")
        code, said = self.tool("check")
        self.assertEqual(code, 1)
        self.assertIn("it names no image", said)


class Shipped(unittest.TestCase):
    def test_the_services_images_are_each_a_tag_and_a_digest_and_what_their_entries_carry(self):
        with open(pins.SERVICES, encoding="utf-8") as f:
            rows = json.load(f)["services"]
        self.assertEqual(sorted(r["name"] for r in rows), sorted(m["name"] for m in services.packs()), "a row a service, by its pack's name")
        for r in rows:
            self.assertTrue(pins.is_pinned(r), r["name"])
            self.assertEqual(packformat.images_checked(r["images"]), (r["images"], []), r["name"])
            self.assertEqual(services.images(r["name"]), r["images"])
            self.assertEqual(set(r["platforms"]), set(next(m for m in services.packs() if m["name"] == r["name"])["platforms"]),
                             f"{r['name']}: a move is held to the platforms its pack is for")

    def test_the_tool_names_no_registry_and_no_image(self):
        with open(os.path.join(REPO, "tools", "pins.py"), encoding="utf-8") as f:
            text = f.read().lower()
        with open(pins.SERVICES, encoding="utf-8") as f:
            rows = json.load(f)["services"]
        names = {packformat.image_parts(ref)["name"] for r in rows for ref in r["images"].values()}
        hosts = {n.split("/")[0] for n in names if "." in n.split("/")[0]} | {imageregistry.DEFAULT_HOST, "docker.io", "ghcr.io", "lscr.io", "quay.io"}
        self.assertEqual(sorted(w for w in names | hosts if w in text), [],
                         "the tool asks the registry a reference names: no host and no image is written in it")


if __name__ == "__main__":
    unittest.main()
