"""Registry images kept up to date (imagecheck.py, R195): an image reference
read into its registry, repository and tag; a node's pulled digest compared
with what the registry serves; a container behind until Update pulls it."""
import json
import os
import shutil
import sys
import tempfile
import unittest
from pathlib import Path

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))
import imagecheck  # noqa: E402


def write_json(path, d):
    Path(path).write_text(json.dumps(d))


class FakeDevapp:
    MAIN = "main"
    SYSTEM = "System"
    DOCKER = "docker"

    def __init__(self, cfg, pulled):
        self.cfg, self.pulled = cfg, pulled

    def _load(self):
        return {"radarr": {"main": {"source": "file", "node": "n1"}}, "site": {"main": {"node": "n1"}},
                "nginx-vps": {"main": {"source": "file", "node": "n1", "for": "System"}}}

    def owner_of(self, p, i):
        return "System" if p == "nginx-vps" else p

    def _instance_node(self, p, i):
        return "n1"

    def _pname(self, p, i):
        return p

    def on_node(self, nid):
        import contextlib
        return contextlib.nullcontext()

    def _config(self, p, i):
        return self.cfg.get(p)

    def _services(self, cfg):
        return cfg.get("services") or {}

    def _run(self, argv, timeout=0):
        img = argv[-1]
        if img not in self.pulled:
            return {"code": 1, "out": "Error: No such image"}
        return {"code": 0, "out": json.dumps([f"{img.rsplit(':', 1)[0]}@{self.pulled[img]}"])}


class ImageCheck(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.mkdtemp()
        self.addCleanup(shutil.rmtree, self.tmp, True)
        A, B = "sha256:" + "a" * 64, "sha256:" + "b" * 64
        self.A, self.B = A, B
        self.dv = FakeDevapp({"radarr": {"services": {"app": {"image": "lscr.io/linuxserver/radarr:latest"},
                                                      "db": {"image": "mariadb:11"}}},
                              "site": {"services": {"web": {"build": {"context": "."}},
                                                    "db": {"image": "mariadb:11"},
                                                    "cache": {"image": "redis@" + A}}}},
                             {"lscr.io/linuxserver/radarr:latest": A, "mariadb:11": B})
        imagecheck.configure(state=self.tmp, write_json=write_json, devapp_module=self.dv)
        self.addCleanup(setattr, imagecheck, "DIGESTS_FILE", imagecheck.DIGESTS_FILE)
        imagecheck.DIGESTS_FILE = f"{self.tmp}/digests.json"
        write_json(imagecheck.DIGESTS_FILE, {"lscr.io/linuxserver/radarr:latest": B, "mariadb:11": B})

    def test_a_reference_is_read_as_a_registry_would(self):
        self.assertEqual(imagecheck.parse_ref("mariadb:11"), ("registry-1.docker.io", "library/mariadb", "11"))
        self.assertEqual(imagecheck.parse_ref("linuxserver/radarr"), ("registry-1.docker.io", "linuxserver/radarr", "latest"))
        self.assertEqual(imagecheck.parse_ref("ghcr.io/aquilaelabs/aerieos:latest"),
                         ("ghcr.io", "aquilaelabs/aerieos", "latest"))
        self.assertEqual(imagecheck.parse_ref("localhost:5000/app:1"), ("localhost:5000", "app", "1"))
        self.assertIsNone(imagecheck.parse_ref("nginx:1.29-alpine@sha256:" + "c" * 64), "pinned by digest: not asked")

    def test_only_registry_images_by_tag_are_asked(self):
        self.assertEqual(imagecheck.registry_images("site", "main"), [("db", "mariadb:11")],
                         "not the built one, not the one pinned by digest")

    def test_behind_until_updated_and_the_bell_row(self):
        r = imagecheck.check()
        self.assertEqual((r["checked"], r["behind"]), (2, 1), "nginx (System) is its own tab's")
        self.assertEqual([b["image"] for b in imagecheck.of("radarr")["behind"]], ["lscr.io/linuxserver/radarr:latest"],
                         "radarr's moved; its mariadb is the registry's own")
        self.assertEqual(imagecheck.of("site")["behind"], [])
        self.assertGreater(imagecheck.last_at(), 0)
        rows = imagecheck.attention(lambda nid: {"n1": "vps"}[nid])
        self.assertEqual([(r["kind"], r["node"], r["containers"]) for r in rows],
                         [("image", "vps", [{"name": "radarr", "images": ["lscr.io/linuxserver/radarr:latest"]}])])
        imagecheck.forget("radarr")
        self.assertEqual(imagecheck.of("radarr")["behind"], [], "Update pulled it")
        self.assertEqual(imagecheck.attention(lambda nid: nid), [])

    def test_the_bell_row_holds_only_the_projects_the_account_may_act_on(self):
        imagecheck.check()
        self.assertEqual(imagecheck.of("radarr")["project"], "radarr", "the check records whose it is")
        self.assertEqual(imagecheck.attention(lambda nid: nid, allowed=lambda p: p == "site"), [],
                         "radarr's update is news only to who may act on radarr")
        self.assertEqual(len(imagecheck.attention(lambda nid: nid, allowed=lambda p: p == "radarr")), 1)
        # An answer from before the check recorded the project: found by name.
        d = json.loads(imagecheck._file().read_text())
        d["radarr"].pop("project")
        write_json(imagecheck._file(), d)
        self.assertEqual(len(imagecheck.attention(lambda nid: nid, allowed=lambda p: p == "radarr")), 1)

    def test_an_image_never_pulled_is_not_compared_and_a_registry_that_will_not_say_is_said(self):
        self.dv.pulled.pop("mariadb:11")
        write_json(imagecheck.DIGESTS_FILE, {"lscr.io/linuxserver/radarr:latest": self.A})
        imagecheck.check()
        self.assertEqual(imagecheck.of("radarr")["behind"], [])
        self.assertEqual(imagecheck.of("site")["error"], "", "never pulled: nothing asked")


class OwnImage(unittest.TestCase):
    """AerieOS's own image, followed by a tag, is held to the digest the
    newest signed release names (R199): said by that digest where the tag
    serves it, and said plainly where the tag serves another."""
    OWN = "ghcr.io/aquilaelabs/aerieos"

    def setUp(self):
        self.tmp = tempfile.mkdtemp()
        self.addCleanup(shutil.rmtree, self.tmp, True)
        self.OLD, self.NEW, self.ODD = ("sha256:" + c * 64 for c in "abc")
        self.dv = FakeDevapp({"workshop": {"services": {"app": {"image": self.OWN + ":dev"}}},
                              "radarr": {"services": {"app": {"image": "lscr.io/linuxserver/radarr:latest"}}}},
                             {self.OWN + ":dev": self.OLD, "lscr.io/linuxserver/radarr:latest": self.OLD})
        imagecheck.configure(state=self.tmp, write_json=write_json, devapp_module=self.dv)
        self.addCleanup(setattr, imagecheck, "DIGESTS_FILE", imagecheck.DIGESTS_FILE)
        imagecheck.DIGESTS_FILE = f"{self.tmp}/digests.json"
        self.serves(self.NEW)
        self.asked = []
        self.names = {"tag": "v0.9.0-dev.5300", "image": self.OWN, "digest": self.NEW, "ref": f"{self.OWN}@{self.NEW}",
                      "signed": "signed by the key AerieOS's dev builds are signed with"}

        def signed_image(follow):
            self.asked.append(follow)
            if isinstance(self.names, Exception):
                raise self.names
            return self.names
        self.addCleanup(setattr, imagecheck.releasecheck, "signed_image", imagecheck.releasecheck.signed_image)
        imagecheck.releasecheck.signed_image = signed_image

    def serves(self, digest):
        write_json(imagecheck.DIGESTS_FILE, {self.OWN + ":dev": digest, "lscr.io/linuxserver/radarr:latest": self.NEW})

    def test_an_update_the_newest_signed_release_names_is_said_by_its_digest(self):
        got = imagecheck.check_instance("workshop", "main")
        self.assertEqual(got["behind"], [{"service": "app", "image": self.OWN + ":dev", "to": self.NEW,
                                          "signed": f"{self.OWN}@{self.NEW}, v0.9.0-dev.5300's own image, signed by the key "
                                                    "AerieOS's dev builds are signed with"}])
        self.assertEqual((got["said"], got["error"], self.asked), ([], "", ["dev"]))
        # Up to date with what the release names: nothing behind, nothing said.
        self.dv.pulled[self.OWN + ":dev"] = self.NEW
        got = imagecheck.check_instance("workshop", "main")
        self.assertEqual((got["behind"], got["said"]), ([], []))

    def test_a_tag_that_serves_another_image_than_the_signed_release_names_is_said_and_offers_no_update(self):
        self.serves(self.ODD)
        got = imagecheck.check_instance("workshop", "main")
        self.assertEqual(got["behind"], [], "no update is offered from the tag")
        self.assertEqual(got["said"], [
            f"{self.OWN}:dev serves {self.ODD} now, which is not the image the newest signed release names "
            f"(v0.9.0-dev.5300: {self.OWN}@{self.NEW}, signed by the key AerieOS's dev builds are signed with). "
            "The registry's tag was moved by something other than that release's publication, or a newer release is "
            "not signed yet, so no update is offered from the tag; the signed image is pulled by its digest"])
        # ...whatever the container runs, the one the tag serves included.
        self.dv.pulled[self.OWN + ":dev"] = self.ODD
        self.assertEqual(len(imagecheck.check_instance("workshop", "main")["said"]), 1)

    def test_where_no_release_says_the_row_is_as_any_other_images(self):
        for names in ({"why": "v0.9.0-dev.5200 carries no signed list of its files"}, RuntimeError("no network"),
                      # A release that names another repository's image says nothing of this one.
                      {"tag": "v1", "image": "ghcr.io/somebody/else", "digest": self.ODD, "ref": "x", "signed": "y"}):
            self.names = names
            got = imagecheck.check_instance("workshop", "main")
            self.assertEqual((got["behind"], got["said"]), ([{"service": "app", "image": self.OWN + ":dev", "to": self.NEW}], []))

    def test_no_other_image_asks_the_releases_and_one_check_asks_once(self):
        imagecheck.check_instance("radarr", "main")
        self.assertEqual(self.asked, [])
        self.assertEqual(imagecheck.release_image(self.OWN + ":0.9.0"), {}, "a version's own tag is no tag a publication moves")
        self.assertEqual(imagecheck.release_image("ghcr.io/somebody/aerieos:dev"), {})
        memo = {}
        for _ in range(3):
            imagecheck.check_instance("workshop", "main", memo)
        self.assertEqual(self.asked, ["dev"])


if __name__ == "__main__":
    unittest.main()
