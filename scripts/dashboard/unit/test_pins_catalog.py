"""tools/pins.py over what this tree ships and over a checkout of the
catalog. With nothing named, check asks every table this tree ships that
carries a pin, so a release's pass is one command. With --catalog DIR every
folder under the catalog's packs/ is a row, read from the file that holds
its pins and written back to it: a pack's declared downloads and what it
asks a package manager for, a shipped toolchain's recipe, a coding agent's
install recipe, the images a service runs, and the images a Docker app's
compose names. Against a scratch catalog made here, with the network
stood in for."""
import hashlib
import importlib.util
import json
import os
import shutil
import sys
import tempfile
import unittest
import urllib.error
from pathlib import Path
from unittest import mock

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))
import catalogrows  # noqa: E402
import imageregistry  # noqa: E402
import packformat  # noqa: E402
import toolpacks  # noqa: E402
from sdkstore import REPO, sdkmeta  # noqa: E402
from test_imageregistry import Registry  # noqa: E402

spec = importlib.util.spec_from_file_location("pins_tool", os.path.join(REPO, "tools", "pins.py"))
pins = importlib.util.module_from_spec(spec)
spec.loader.exec_module(pins)

BOTH = ("linux/amd64", "linux/arm64")
TRACK = {"resolver": "text", "url": "https://dl.example.org/KIT"}
KIT = "https://dl.example.org/kit-{version}.tgz"
LOGO = "https://dl.example.org/logo.svg"
FILES = "https://files.example.org/"


def sha(data):
    return hashlib.sha256(data.encode()).hexdigest()


def listed(*plats, salt=""):
    """A manifest list's bytes for those platforms, and its digest."""
    body = json.dumps({"schemaVersion": 2, "mediaType": imageregistry.INDEXES[0], "salt": salt, "manifests": [
        {"digest": "sha256:" + hashlib.sha256(p.encode()).hexdigest(), "platform": dict(zip(("os", "architecture"), p.split("/"), strict=True))} for p in plats]}).encode()
    return body, "sha256:" + hashlib.sha256(body).hexdigest()


WEB, WEB_D = listed(*BOTH)
NEWER, NEWER_D = listed(*BOTH, salt="rebuilt")
COMPOSE = f"""# an app
services:
  web:
    image: reg.example/app/web:1.2@{WEB_D}   # the app itself
    ports:
      - "${{PORT}}:80"
"""


def text(m):
    """A manifest as the catalog's folders hold one."""
    return json.dumps(m, indent=1, sort_keys=True) + "\n"


class Case(unittest.TestCase):
    """The vendors a row asks: `pages` are the documents a resolver or a
    publisher's statement is read from, `files` what each address answers
    when it is downloaded, `manifests` what the registries serve."""

    def setUp(self):
        self.d = tempfile.mkdtemp()
        self.addCleanup(shutil.rmtree, self.d, True)
        self.pages, self.files, self.fetched = {TRACK["url"]: "1.4.0\n"}, {KIT.format(version="1.4.0"): "kit 1.4.0", LOGO: "a logo"}, []
        self.manifests = {("reg.example", "app/web", "1.2"): WEB, ("reg.example", "app/web", WEB_D): WEB}
        self.registry = Registry(self.manifests)
        self.addCleanup(setattr, imageregistry, "_open", imageregistry._open)
        imageregistry._open = self.registry
        for mod, name, stand_in in ((sdkmeta, "get", self.get), (sdkmeta, "final_url", mock.Mock(side_effect=AssertionError("asked for a redirect"))),
                                    (pins, "hashed", self.hashed), (pins, "pip_resolved", self.pip_resolved)):
            p = mock.patch.object(mod, name, stand_in)
            p.start()
            self.addCleanup(p.stop)
        self.wheels = [{"name": "alpha", "version": "1.0", "wheels": [{"url": FILES + "alpha-1.0-py3-none-any.whl", "hashes": {"sha256": sha("alpha 1.0")}}]}]

    def gone(self, url):
        e = urllib.error.HTTPError(url, 404, "Not Found", None, None)
        e.close()
        raise e

    def get(self, url, decode=True):
        if url not in self.pages:
            self.gone(url)
        return self.pages[url] if decode else self.pages[url].encode()

    def hashed(self, url, also=""):
        self.fetched.append(url)
        if url not in self.files:
            self.gone(url)
        return {"sha256": sha(self.files[url]), "bytes": len(self.files[url])}

    def pip_resolved(self, requirements, python, target):
        return json.loads(json.dumps(self.wheels))

    def tool(self, *argv):
        said = []
        rc = pins.main(list(argv), out=said.append)
        return rc, "\n".join(said)


class Shipped(Case):
    """Three made-up tables in the places of the ones this tree ships."""

    def setUp(self):
        super().setUp()
        self.files["https://dl.example.org/runner.tgz"] = "a runner"
        pin = {"from": "pin", "sha256": sha("kit 1.4.0"), "version": "1.4.0"}
        self.paths = {
            "toolchains": {"toolchains": [{"name": "kit", "label": "Kit", "probe": "kit", "about": "A kit.", "platforms": ["linux/amd64"],
                                           "layout": {"bin": ["bin"], "env": {}},
                                           "source": {"kind": "tarball", "url": KIT, "version": TRACK, "checksum": pin}}]},
            "agents": {"recipes": {"lark": {"rev": 1, "fetch": [{"url": LOGO, "sha256": sha("a logo"), "to": "dl/install.sh"}],
                                            "online": "Its installer downloads the rest from get.example.org.", "steps": [["bash", "{dir}/dl/install.sh"]],
                                            "pin": None, "env": {}, "bin": ".local/bin/lark", "also": [], "fresh": ""}}},
            "runners": {"runners": [{"name": "forge", "source": {"kind": "tarball", "url": "https://dl.example.org/runner.tgz",
                                                              "checksum": {"from": "pin", "sha256": sha("a runner")}}}]},
            "services": {"services": [{"name": "site", "rev": 3, "platforms": list(BOTH), "images": {"web": f"reg.example/app/web:1.2@{WEB_D}"}}]},
        }
        for name, doc in self.paths.items():
            pins.save(os.path.join(self.d, name + ".json"), doc)
        at = lambda name: os.path.join(self.d, name + ".json")  # noqa: E731
        p = mock.patch.object(pins, "SHIPPED", ((at("toolchains"), at("agents")), (at("runners"), ""), (at("services"), "")))
        p.start()
        self.addCleanup(p.stop)

    def test_check_with_nothing_named_asks_every_table_this_tree_ships(self):
        rc, out = self.tool("check")
        self.assertEqual(rc, 0, out)
        self.assertEqual(out.splitlines(), [
            "kit: its download is at 1.4.0 (its resolver finds the version it is pinned to)",
            "lark: dl/install.sh is at " + sha("a logo")[:12] + " (downloaded and hashed here (6 bytes): its publisher states no digest for it)",
            "forge: its download is at the pinned bytes (its address still answers the pinned bytes)",
            f"site: its image web is at 1.2 {WEB_D[7:19]} (its registry serves the digest it is pinned to)",
            "nothing would move"])

    def test_one_table_that_would_move_is_the_whole_run_s_answer(self):
        self.manifests[("reg.example", "app/web", "1.2")] = NEWER
        self.manifests[("reg.example", "app/web", NEWER_D)] = NEWER
        before = {n: Path(self.d, n + ".json").read_text() for n in self.paths}
        rc, out = self.tool("check")
        self.assertEqual(rc, 3, out)
        self.assertEqual(out.splitlines()[-1], "1 row(s) would move")
        self.files["https://dl.example.org/runner.tgz"] = "another runner"
        rc, out = self.tool("check")
        self.assertEqual((rc, out.splitlines()[-1]), (3, "2 row(s) would move"))
        self.assertIn("forge: its download the pinned bytes to other bytes", out)
        del self.pages[TRACK["url"]]
        rc, out = self.tool("check")
        self.assertEqual(rc, 1, "a row that could not be asked is the run's answer")
        self.assertIn("kit: could not be asked", out)
        self.assertEqual({n: Path(self.d, n + ".json").read_text() for n in self.paths}, before, "check writes nothing")

    def test_the_tables_this_tree_ships_are_the_ones_read(self):
        real = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(real)
        self.assertEqual([(os.path.relpath(t, REPO), os.path.relpath(a, REPO) if a else "") for t, a in real.SHIPPED],
                         [("config/toolchains.json", "scripts/dashboard/agent-recipes.json"), ("scripts/dashboard/runner-pins.json", ""),
                          ("scripts/dashboard/service-images.json", ""), ("config/image-tools.json", "")])
        for table, recipes in real.SHIPPED:
            doc = real.table_doc(table, recipes)
            self.assertTrue(real.table(doc), table)
        # A name, or a table named, is asked of that table alone, as before.
        rc, out = self.tool("check", "--file", os.path.join(self.d, "runners.json"))
        self.assertEqual((rc, out.splitlines()), (0, ["forge: its download is at the pinned bytes (its address still answers the pinned bytes)", "nothing would move"]))


class Catalog(Case):
    """A scratch catalog: a pack that declares its downloads and a pip
    lock, a shipped toolchain's pack, a coding agent's, a service's, and a
    Docker app."""

    def setUp(self):
        super().setUp()
        self.cat = os.path.join(self.d, "catalog")
        self.pack = {"name": "kit", "label": "Kit", "about": "A kit.", "maker": "Kit Works", "format": 5, "framework": "5.2", "platforms": ["linux/amd64"],
                     "install": {"steps": [["sh", "{dir}/install.sh"]],
                                 "fetch": [{"url": KIT, "version": "1.4.0", "sha256": sha("kit 1.4.0"), "to": "dl/kit.tgz", "track": TRACK},
                                           {"url": LOGO, "sha256": sha("a logo"), "to": "dl/logo.svg"}]},
                     "layout": {"bin": ["bin"], "tool": "bin/kit"},
                     "verbs": {"run": {"about": "Runs it.", "usage": "", "run": ["{dir}/bin/kit", "{args}"]}}}
        self.put("packs/aerie/kit/bbtool.json", text(self.pack))
        # The packs AerieOS's own tables write, as this tree holds them.
        for rel in ("official/go", "agents/claude", "services/nginx"):
            self.put(f"packs/{rel}/bbtool.json", Path(REPO, "packs", rel, "bbtool.json").read_text())
        self.go = json.loads(Path(REPO, "packs/official/go/bbtool.json").read_text())
        self.claude = json.loads(Path(REPO, "packs/agents/claude/bbtool.json").read_text())
        self.nginx = json.loads(Path(REPO, "packs/services/nginx/bbtool.json").read_text())
        self.put("packs/apps/web/bbapp.json", json.dumps({"name": "web", "label": "Web", "about": "An app.", "port": 8080, "platforms": list(BOTH), "format": 5}))
        self.put("packs/apps/web/compose.yml", COMPOSE)
        self.put("index.json", "{}\n")
        # Its vendors as they stand: every pinned file answers its pin.
        row = catalogrows.row_of(self.go)
        self.pages[row["source"]["version"]["url"]] = row["source"]["checksum"]["version"] + "\n"
        # A coding agent's row goes by the name its row in the Library has.
        self.agent = pins.agent_rows({"claude": self.claude["agent"]["install"]})[0]["name"]
        self.script = self.claude["agent"]["install"]["fetch"][0]
        self.files[self.script["url"]] = "the installer, as pinned"
        self.script_was = self.script["sha256"]
        ref = packformat.image_parts(self.nginx["images"]["nginx"])
        self.nginx_at = (imageregistry.DEFAULT_HOST, "library/" + ref["name"], ref["tag"])
        self.manifests[self.nginx_at] = WEB
        self.manifests[(*self.nginx_at[:2], WEB_D)] = WEB
        self.nginx_now = f"{ref['name']}:{ref['tag']}@{WEB_D}"

    def put(self, rel, body):
        p = Path(self.cat, rel)
        p.parent.mkdir(parents=True, exist_ok=True)
        p.write_text(body)

    def read(self, rel):
        return Path(self.cat, rel).read_text()

    def catalog(self, *argv):
        return self.tool(*argv, "--catalog", self.cat)

    def snapshot(self):
        return {str(p.relative_to(self.cat)): p.read_text() for p in sorted(Path(self.cat).rglob("*")) if p.is_file()}

    def test_every_folder_is_a_row_read_from_the_file_that_holds_its_pins(self):
        docs, bad = pins.catalog_docs(self.cat)
        self.assertEqual(bad, [])
        self.assertEqual([(pins.names_of(d), (d.get("_pack") or {}).get("kind", "compose")) for d in docs],
                         [(["kit"], "pack"), ([self.agent], "agent"), (["web"], "compose"), (["go"], "shipped"), (["nginx"], "service")])
        app = next(d for d in docs if d.get("_compose"))
        self.assertEqual(pins.table(app)[0]["platforms"], list(BOTH), "an app's images are held for the platforms its manifest names")
        # A shipped toolchain's pack is its row, whole: written back, it is the manifest it was.
        for name in sorted(os.listdir(os.path.join(REPO, "packs", "official"))):
            m = json.loads(Path(REPO, "packs", "official", name, "bbtool.json").read_text())
            self.assertEqual(catalogrows.manifest_of(catalogrows.row_of(m)), m, name)

    def test_check_says_what_would_move_and_writes_nothing(self):
        before = self.snapshot()
        rc, out = self.catalog("check")
        # The agent's moving script answers other bytes than its pin, and
        # the service's tag another digest: two rows of the five.
        self.assertEqual(rc, 3, out)
        self.assertIn("kit: dl/kit.tgz is at 1.4.0 " + sha("kit 1.4.0")[:12] + " (its track finds the version it is pinned to)", out)
        self.assertIn("kit: dl/logo.svg is at " + sha("a logo")[:12], out)
        self.assertIn(f"{self.agent}: {self.script['to']} {self.script_was[:12]} to {sha('the installer, as pinned')[:12]}", out)
        self.assertIn(f"web: reg.example/app/web is at 1.2 {WEB_D[7:19]} (its registry serves the digest it is pinned to)", out)
        self.assertIn("go: its download is at ", out)
        self.assertIn(f"nginx: its image nginx {self.nginx_at[2]} ", out)
        self.assertEqual(out.splitlines()[-1], "2 row(s) would move")
        self.assertEqual(self.snapshot(), before)
        # One named is asked alone; a name the catalog has not is said.
        rc, out = self.catalog("check", "kit")
        self.assertEqual((rc, len(out.splitlines())), (0, 3), out)
        rc, out = self.catalog("check", "nothing")
        self.assertEqual((rc, out), (1, "pins: no pack or app of the catalog named nothing"))

    def test_move_writes_each_manifest_where_it_lies_and_nothing_else_of_it(self):
        self.pages[TRACK["url"]] = "1.5.0\n"
        self.files[KIT.format(version="1.5.0")] = "kit 1.5.0"
        self.manifests[("reg.example", "app/web", "1.2")] = NEWER
        self.manifests[("reg.example", "app/web", NEWER_D)] = NEWER
        before = self.snapshot()
        rc, out = self.catalog("move")
        self.assertEqual(rc, 0, out)
        after = self.snapshot()
        self.assertEqual(sorted(k for k in after if after[k] != before[k]),
                         ["packs/aerie/kit/bbtool.json", "packs/agents/claude/bbtool.json", "packs/apps/web/compose.yml", "packs/services/nginx/bbtool.json"])
        self.assertEqual(set(after), set(before))
        # A pack: the version and the digest of the download that moved, and no other line.
        self.assertEqual(after["packs/aerie/kit/bbtool.json"],
                         before["packs/aerie/kit/bbtool.json"].replace('"version": "1.4.0"', '"version": "1.5.0"').replace(sha("kit 1.4.0"), sha("kit 1.5.0")))
        self.assertIn("kit: dl/kit.tgz 1.4.0 " + sha("kit 1.4.0")[:12] + " to 1.5.0 " + sha("kit 1.5.0")[:12], out)
        self.assertNotIn("kit: rev", out, "a pack is pinned by the commit it is at: it has no rev to raise")
        # A coding agent's recipe: its download's digest, and its rev.
        rev = self.claude["agent"]["install"]["rev"]
        self.assertEqual(after["packs/agents/claude/bbtool.json"],
                         before["packs/agents/claude/bbtool.json"].replace(self.script_was, sha("the installer, as pinned")).replace(f'"rev": {rev},', f'"rev": {rev + 1},'))
        self.assertIn(f"{self.agent}: rev {rev} to {rev + 1}", out)
        # A service's images and an app's compose: the digest alone.
        self.assertEqual(after["packs/services/nginx/bbtool.json"], before["packs/services/nginx/bbtool.json"].replace(self.nginx["images"]["nginx"], self.nginx_now))
        self.assertEqual(after["packs/apps/web/compose.yml"], COMPOSE.replace(WEB_D, NEWER_D))
        self.assertIn("go: nothing to move", out)
        # Each is still a manifest an install takes, and then nothing would move.
        for rel, official in (("aerie/kit", False), ("agents/claude", True), ("services/nginx", True)):
            self.assertEqual(toolpacks.validate(json.loads(after[f"packs/{rel}/bbtool.json"]), (), official=official)[1], [], rel)
        self.assertEqual(self.catalog("check")[0], 0)

    def test_a_shipped_toolchain_s_pack_moves_as_its_row_does(self):
        row = catalogrows.row_of(self.go)
        was = row["source"]["checksum"]["version"]
        new = "go9.99.0"
        self.pages[row["source"]["version"]["url"]] = new + "\n"
        self.pages["https://go.dev/dl/?mode=json&include=all"] = json.dumps([{"version": new, "stable": True, "files": [
            {"filename": u.rsplit("/", 1)[-1].replace("{version}", new), "sha256": sha(new + plat)} for plat, u in row["source"]["url"].items()]}])
        rc, out = self.catalog("move", "go")
        self.assertEqual(rc, 0, out)
        got = json.loads(self.read("packs/official/go/bbtool.json"))
        self.assertEqual(self.read("packs/official/go/bbtool.json"), text(got), "laid out as it was")
        self.assertEqual((got["shipped"]["source"]["checksum"]["version"], got["shipped"]["rev"]), (new, self.go["shipped"]["rev"] + 1))
        self.assertEqual(got["shipped"]["source"]["checksum"]["sha256"], {plat: sha(new + plat) for plat in row["source"]["url"]})
        self.assertEqual({k: v for k, v in got.items() if k != "shipped"}, {k: v for k, v in self.go.items() if k != "shipped"})
        self.assertIn(f"go: its download {was} to {new}", out)
        self.assertEqual(toolpacks.validate(got, (), official=True)[1], [])

    def test_a_pack_s_lock_is_resolved_into_its_folder(self):
        # Written as a person writes it: what pip is asked for, and no file of the lock's yet.
        self.pack["install"]["lock"] = [{"kind": "pip", "to": "dl/pip", "requirements": ["alpha"], "python": "3.12", "for": {"linux/amd64": "x86_64-manylinux_2_28"}}]
        self.put("packs/aerie/kit/bbtool.json", text(self.pack))
        self.assertIn("kit: not pinned", self.catalog("check", "kit")[1])
        rc, out = self.catalog("pin", "kit")
        self.assertEqual(rc, 0, out)
        self.assertIn("kit: its pip lock (dl/pip) pinned at 1 file(s)", out)
        self.assertIn("kit: it reads pinned", out)
        got = json.loads(self.read("packs/aerie/kit/bbtool.json"))
        self.assertEqual([f["to"] for f in got["install"]["fetch"]], ["dl/kit.tgz", "dl/logo.svg", "dl/pip/alpha-1.0-py3-none-any.whl"])
        self.assertNotIn("files", got["install"], "what a lock installs by is a file of the pack's folder, not of its manifest")
        self.assertEqual(self.read("packs/aerie/kit/dl/pip/requirements.txt"), f"alpha==1.0 --hash=sha256:{sha('alpha 1.0')}\n")
        self.assertEqual(toolpacks.validate(got)[1], [])
        self.assertEqual(self.catalog("check", "kit")[0], 0, "and then its resolver finds the set it holds")
        # The set moves: the manifest's downloads and the folder's file with it.
        self.wheels = [{"name": "alpha", "version": "1.1", "wheels": [{"url": FILES + "alpha-1.1-py3-none-any.whl", "hashes": {"sha256": sha("alpha 1.1")}}]}]
        self.assertEqual(self.catalog("check", "kit")[0], 3)
        self.assertEqual(self.catalog("move", "kit")[0], 0)
        self.assertEqual([f["to"] for f in json.loads(self.read("packs/aerie/kit/bbtool.json"))["install"]["fetch"]][-1], "dl/pip/alpha-1.1-py3-none-any.whl")
        self.assertEqual(self.read("packs/aerie/kit/dl/pip/requirements.txt"), f"alpha==1.1 --hash=sha256:{sha('alpha 1.1')}\n")

    def test_pin_gives_an_app_s_image_its_first_digest_and_verify_holds_every_file(self):
        self.put("packs/apps/web/compose.yml", COMPOSE.replace("@" + WEB_D, ""))
        self.assertIn("web: not pinned (reg.example/app/web:1.2 names no digest)", self.catalog("check")[1])
        rc, out = self.catalog("pin", "web")
        self.assertEqual((rc, self.read("packs/apps/web/compose.yml")), (0, COMPOSE), out)
        self.assertEqual(self.catalog("pin")[1], "pins: pin takes one NAME")
        # Verify: each pinned file downloaded and held to its pin, each image read by its digest.
        self.files[self.script["url"]] = "the installer, moved since"
        self.manifests[(imageregistry.DEFAULT_HOST, self.nginx_at[1], packformat.image_digest(self.nginx["images"]["nginx"]))] = WEB
        rc, out = self.catalog("verify", "kit", "web", self.agent)
        self.assertEqual(rc, 1, out)
        self.assertIn("kit: dl/kit.tgz is its pin (9 bytes, sha256 " + sha("kit 1.4.0")[:12] + ")", out)
        self.assertIn("web: reg.example/app/web is its pin (a list for linux/amd64, linux/arm64", out)
        self.assertIn(f"{self.agent}: NOT ITS PIN: {self.script['to']}", out)
        self.assertEqual(out.splitlines()[-1], "1 of 4 pinned file(s) are not their pin")

    def test_a_manifest_that_would_no_longer_be_one_is_left_and_a_folder_that_cannot_be_read_is_said(self):
        self.put("packs/aerie/odd/bbtool.json", "{ not json")
        rc, out = self.catalog("check", "kit")
        self.assertEqual(rc, 1)
        self.assertIn("pins: cannot read packs/aerie/odd:", out)
        os.remove(os.path.join(self.cat, "packs/aerie/odd/bbtool.json"))
        # A pack whose manifest an install would refuse (a verb gone) is not written.
        broken = {**self.pack, "verbs": {}}
        self.put("packs/aerie/kit/bbtool.json", text(broken))
        self.pages[TRACK["url"]] = "1.5.0\n"
        self.files[KIT.format(version="1.5.0")] = "kit 1.5.0"
        rc, out = self.catalog("move", "kit")
        self.assertEqual(rc, 1, out)
        self.assertIn("kit: its manifest is left as it was: what it would become is refused: verbs names at least one command", out)
        self.assertEqual(self.read("packs/aerie/kit/bbtool.json"), text(broken))
        self.assertEqual(self.tool("check", "--catalog", self.cat, "--file", "x")[1],
                         "--file, --compose and --catalog each name what is read in the table's place: one of them")
        self.assertIn("it is no checkout of the catalog", self.tool("check", "--catalog", self.d)[1])

    def test_a_manifest_laid_out_by_hand_keeps_its_indent_and_its_order(self):
        by_hand = json.dumps(self.pack, indent=4)
        self.assertEqual(pins.laid_out(text(self.pack), self.pack), {"indent": 1, "sort_keys": True, "ensure_ascii": False})
        self.assertEqual(pins.laid_out(by_hand + "\n", self.pack), {"indent": 4, "sort_keys": False, "ensure_ascii": False})
        odd = by_hand.replace('"name": "kit",', '"name":   "kit",') + "\n"
        self.assertEqual(pins.laid_out(odd, self.pack), {"indent": 4, "sort_keys": False, "ensure_ascii": False})
        self.put("packs/aerie/kit/bbtool.json", by_hand + "\n")
        self.pages[TRACK["url"]] = "1.5.0\n"
        self.files[KIT.format(version="1.5.0")] = "kit 1.5.0"
        self.assertEqual(self.catalog("move", "kit")[0], 0)
        self.assertEqual(self.read("packs/aerie/kit/bbtool.json"), (by_hand + "\n").replace('"version": "1.4.0"', '"version": "1.5.0"').replace(sha("kit 1.4.0"), sha("kit 1.5.0")))


if __name__ == "__main__":
    unittest.main()
