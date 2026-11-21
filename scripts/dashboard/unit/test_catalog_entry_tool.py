"""The catalog's index entries, written from the folders they pin
(catalogentry.py, tools/packs-export.py --catalog DIR): an entry of any
folder under the catalog's packs/ is read from that folder's own manifest
at a commit, with the sha256 an install's fetch holds it to; what is the
entry's own is kept; a pin is placed by its pack format, so an entry that
moves to a newer format keeps the pin it had as an older one; and an older
pin goes only when its format is named. Against a scratch catalog made
here."""
import contextlib
import importlib.util
import io
import json
import os
import shutil
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path
from unittest import mock

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))
import catalogentry  # noqa: E402
import catalogindex  # noqa: E402
import packformat  # noqa: E402
import toolpacks  # noqa: E402

ROOT = Path(__file__).resolve().parents[3]
DIGEST = "sha256:" + "c" * 64
PACK = {"name": "hexkit", "label": "Hex kit", "about": "Looks inside binaries.", "maker": "Hex Works", "framework": "2.1", "format": 2,
        "platforms": ["linux/amd64"], "works_with": ["0.9"],
        "install": {"steps": [["sh", "{dir}/install.sh"]]}, "layout": {"bin": ["bin"], "tool": "bin/hexkit"},
        "verbs": {"dump": {"about": "A file's bytes as hex.", "usage": "FILE", "run": ["{dir}/bin/hexkit", "dump", "{args}"]}}}
# The same pack held: every download declared, which is pack format 5's.
HELD = {**PACK, "format": 5, "framework": "5.2", "platforms": ["linux/amd64", "linux/arm64"], "works_with": [],
        "install": {"steps": PACK["install"]["steps"], "fetch": [{"url": "https://dl.example.com/hexkit.tgz", "sha256": "a" * 64, "to": "hexkit.tgz"}]}}
APP = {"name": "whoami", "label": "whoami", "about": "A tiny web server.", "maker": "Traefik Labs", "framework": "2.1", "port": 8089,
       "platforms": ["linux/amd64", "linux/arm64"]}
COMPOSE = 'services:\n  whoami:\n    image: traefik/whoami:v1.10.4\n    ports:\n      - "${PORT}:80"\n'


def tool():
    spec = importlib.util.spec_from_file_location("packs_export_tool", ROOT / "tools" / "packs-export.py")
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


class Scratch(unittest.TestCase):
    def setUp(self):
        self.d = tempfile.mkdtemp()
        self.addCleanup(shutil.rmtree, self.d, True)
        self.cat = os.path.join(self.d, "catalog")
        os.makedirs(self.cat)
        self.git("init", "-q", "-b", "main")
        self.put("index.json", {"version": 1, "generated": "2026-11-01T00:00:00Z", "formats": {"2": "0.9.0"}, "packs": []})
        self.put("packs/aerie/hexkit/bbtool.json", PACK)
        self.put("packs/apps/whoami/bbapp.json", APP)
        self.put("packs/apps/whoami/compose.yml", COMPOSE)
        self.first = self.commit("the catalog")
        env = mock.patch.dict(os.environ, {"BB_TOOLPACKS_FILE_URLS": "1", "BB_SEAMS": "1"})
        env.start()
        self.addCleanup(env.stop)
        self.tool = tool()
        self.url = "file://" + self.cat

    def git(self, *a):
        env = dict(os.environ, GIT_AUTHOR_NAME="t", GIT_AUTHOR_EMAIL="t@t", GIT_COMMITTER_NAME="t", GIT_COMMITTER_EMAIL="t@t")
        return subprocess.run(["git", "-C", self.cat, *a], capture_output=True, text=True, check=True, env=env).stdout.strip()

    def put(self, rel, what):
        p = Path(self.cat, rel)
        p.parent.mkdir(parents=True, exist_ok=True)
        p.write_text(what if isinstance(what, str) else json.dumps(what, indent=1) + "\n")

    def commit(self, said):
        self.git("add", "-A")
        self.git("commit", "-qm", said)
        return self.git("rev-parse", "HEAD")

    def run_tool(self, *argv):
        out = io.StringIO()
        with contextlib.redirect_stdout(out):
            code = self.tool.main(["--catalog", self.cat, *argv])
        return code, out.getvalue()

    def index(self):
        return json.loads(Path(self.cat, "index.json").read_text())

    def entry(self, name):
        return next(p for p in self.index()["packs"] if p["name"] == name)

    def test_an_entry_is_written_from_its_folder_s_own_manifest(self):
        code, said = self.run_tool("--entry", "packs/aerie/hexkit", "packs/apps/whoami", "--tier", "aerie", "--topics", "devtools,security")
        self.assertEqual(code, 0, said)
        pack, app = self.entry("hexkit"), self.entry("whoami")
        today = pack["added"]
        self.assertRegex(today, r"^20\d\d-\d\d-\d\d$")
        self.assertEqual(pack, {"name": "hexkit", "url": "https://github.com/aquilaelabs/aerieos-catalog", "commit": self.first, "path": "packs/aerie/hexkit",
                                "sha256": pack["sha256"], "tier": "aerie", "withdrawn": False, "about": "Looks inside binaries.", "platforms": ["linux/amd64"],
                                "format": 2, "label": "Hex kit", "maker": "Hex Works", "framework": "2.1", "works_with": ["0.9"], "held": "open",
                                "topics": ["devtools", "security"], "added": today})
        self.assertEqual(app, {"name": "whoami", "kind": "app", "url": "https://github.com/aquilaelabs/aerieos-catalog", "commit": self.first,
                               "path": "packs/apps/whoami", "sha256": app["sha256"], "tier": "aerie", "withdrawn": False, "about": "A tiny web server.",
                               "platforms": ["linux/amd64", "linux/arm64"], "maker": "Traefik Labs", "framework": "2.1", "held": "open",
                               "topics": ["devtools", "security"], "added": today})
        # The sha256 is the one an install's fetch holds the folder to.
        self.assertNotIn("error", toolpacks.fetch(self.url, pack["commit"], (), pack["sha256"], pack["path"]))
        self.assertNotIn("error", toolpacks.fetch_folder(self.url, app["commit"], app["sha256"], app["path"], ("bbapp.json",)))
        # ...the index is one an install parses, and each entry is what its folder says.
        idx, why = catalogindex.parse(Path(self.cat, "index.json").read_bytes())
        self.assertEqual((why, [e["name"] for e in idx["packs"]]), ("", ["hexkit", "whoami"]))
        for e in (pack, app):
            self.assertEqual(catalogentry.differs(e, self.url), [], e["name"])
        self.assertEqual(self.index()["formats"], {"2": "0.9.0"}, "what the index says beside its entries is kept")
        self.assertNotEqual(self.index()["generated"], "2026-11-01T00:00:00Z")

    def test_what_is_refused_writes_nothing(self):
        before = Path(self.cat, "index.json").read_text()
        for argv, said in ((["--entry", "packs/aerie/hexkit"], "name its tier with --tier"),
                           (["--entry", "packs/aerie/hexkit", "--tier", "official"], "name its tier with --tier"),
                           (["--entry", "packs/aerie/nothing", "--tier", "aerie"], "it is not in the catalog at"),
                           (["--entry", "tools", "--tier", "aerie"], "an entry's folder is under the catalog's packs/"),
                           (["--entry", "packs/aerie/hexkit", "--tier", "aerie", "--topics", "gardening"], "not one of the catalog's"),
                           (["--entry", "packs/aerie/hexkit", "--tier", "aerie", "--commit", "nowhere"], "nowhere is no commit of the catalog"),
                           (["--drop-older", "five"], "--drop-older names the pack format")):
            code, out = self.run_tool(*argv)
            self.assertEqual(code, 1, argv)
            self.assertIn(said, out, argv)
            self.assertEqual(Path(self.cat, "index.json").read_text(), before, argv)
        # A manifest an install would refuse is no entry.
        self.put("packs/aerie/hexkit/bbtool.json", {**PACK, "verbs": {}})
        self.commit("no verbs")
        code, out = self.run_tool("--entry", "packs/aerie/hexkit", "--tier", "aerie")
        self.assertEqual(code, 1)
        self.assertIn("verbs names at least one command", out)
        # ...and packs/ must be committed: an entry pins a commit that holds its folder.
        self.put("packs/aerie/hexkit/bbtool.json", PACK)
        code, out = self.run_tool("--entry", "packs/aerie/hexkit", "--tier", "aerie")
        self.assertEqual(code, 1)
        self.assertIn("packs/ in the catalog is not committed", out)

    def test_the_entry_s_own_is_kept_and_an_unchanged_folder_keeps_its_pin(self):
        self.run_tool("--entry", "packs/aerie/hexkit", "--tier", "vetted", "--topics", "security")
        idx = self.index()
        idx["packs"][0].update(added="2026-10-01", withdrawn=True, url="https://github.com/hexworks/hexkit-pack", note="a key of a later tool's")
        self.put("index.json", idx)
        # Another folder changes: a new commit, and this folder as it was.
        self.put("packs/apps/whoami/compose.yml", COMPOSE.replace("v1.10.4", "v1.10.5"))
        self.commit("whoami moves")
        was = self.entry("hexkit")
        code, out = self.run_tool("--entry", "packs/aerie/hexkit")
        self.assertEqual(code, 0, out)
        self.assertIn("hexkit: as the index has it", out)
        self.assertIn("is as it was: nothing to write", out)
        self.assertEqual(self.entry("hexkit"), was, "its tier, topics, day, withdrawn, address and pin, all as they were")
        # Its own folder changes: the pin moves, and the rest stays.
        self.put("packs/aerie/hexkit/bbtool.json", {**PACK, "about": "Looks inside binaries, closely.", "platforms": ["linux/amd64", "linux/arm64"]})
        second = self.commit("hexkit moves")
        code, out = self.run_tool("--entry", "packs/aerie/hexkit")
        got = self.entry("hexkit")
        self.assertIn(f"hexkit: pinned at {second[:12]}", out)
        self.assertEqual((got["commit"], got["about"], got["platforms"]), (second, "Looks inside binaries, closely.", ["linux/amd64", "linux/arm64"]))
        self.assertEqual({k: got[k] for k in ("tier", "topics", "added", "withdrawn", "url", "note")},
                         {k: was[k] for k in ("tier", "topics", "added", "withdrawn", "url", "note")})
        self.assertNotIn("older", got, "the same format again: the newest pin is replaced, and nothing is kept beside it")

    def test_a_move_to_a_newer_format_keeps_the_pin_it_had(self):
        self.run_tool("--entry", "packs/aerie/hexkit", "--tier", "aerie")
        first = self.entry("hexkit")
        self.put("packs/aerie/hexkit/bbtool.json", HELD)
        second = self.commit("hexkit, held")
        code, out = self.run_tool("--entry", "packs/aerie/hexkit")
        self.assertEqual(code, 0, out)
        self.assertIn("hexkit: pack format 2 to 5: its format 2 pin is kept as an older one", out)
        self.assertIn("formats does not say which AerieOS first reads pack format 5", out)
        got = self.entry("hexkit")
        self.assertEqual((got["commit"], got["format"], got["framework"], got["held"], got["platforms"]),
                         (second, 5, "5.2", "pinned", ["linux/amd64", "linux/arm64"]))
        self.assertNotIn("works_with", got, "the newest manifest names no release line, and nothing of the older pin is carried into it")
        self.assertEqual(got["older"], [{"format": 2, "framework": "2.1", "commit": self.first, "sha256": first["sha256"], "platforms": ["linux/amd64"],
                                         "label": "Hex kit", "works_with": ["0.9"], "held": "open"}])
        self.assertEqual(packformat.older_refused(got), "")
        # Each build is answered the pin it reads, and each is what its folder says there.
        at2, at5 = packformat.pin_for(got, reads=4), packformat.pin_for(got, reads=5)
        self.assertEqual((at2["commit"], at2["held"], at5["commit"]), (self.first, "open", second))
        for e in (at2, at5):
            self.assertEqual(catalogentry.differs(e, self.url), [])
        self.assertEqual(catalogindex.parse(Path(self.cat, "index.json").read_bytes())[0]["packs"][0]["older"][0]["commit"], self.first)
        # Run again, and with another move in the newest format: the older pin stays as it is.
        self.assertIn("as the index has it", self.run_tool("--entry", "packs/aerie/hexkit")[1])
        self.put("packs/aerie/hexkit/bbtool.json", {**HELD, "about": "Looks inside binaries, held."})
        third = self.commit("hexkit, again")
        self.run_tool("--entry", "packs/aerie/hexkit")
        self.assertEqual((self.entry("hexkit")["commit"], self.entry("hexkit")["older"]), (third, got["older"]))

    def test_an_earlier_format_s_pin_moves_beside_the_newest(self):
        self.run_tool("--entry", "packs/aerie/hexkit", "--tier", "aerie")
        self.put("packs/aerie/hexkit/bbtool.json", HELD)
        second = self.commit("hexkit, held")
        self.run_tool("--entry", "packs/aerie/hexkit")
        self.commit("the index")
        # A fix to the format 2 manifest, on a branch from where it was.
        self.git("checkout", "-q", "-b", "format-2", self.first)
        self.put("packs/aerie/hexkit/bbtool.json", {**PACK, "platforms": ["linux/amd64", "linux/arm64"]})
        fixed = self.commit("the format 2 manifest, for arm64 too")
        self.git("checkout", "-q", "main")
        code, out = self.run_tool("--entry", "packs/aerie/hexkit", "--commit", "format-2")
        self.assertEqual(code, 0, out)
        self.assertIn("hexkit: its pack format 2 pin moved, beside its newest (5)", out)
        got = self.entry("hexkit")
        self.assertEqual((got["commit"], got["format"]), (second, 5), "the newest pin stays")
        self.assertEqual([(o["format"], o["commit"], o["platforms"]) for o in got["older"]], [(2, fixed, ["linux/amd64", "linux/arm64"])])
        self.assertEqual(catalogentry.differs(packformat.pin_for(got, reads=2), self.url), [])

    def test_an_older_pin_goes_only_when_its_format_is_named(self):
        self.run_tool("--entry", "packs/aerie/hexkit", "packs/apps/whoami", "--tier", "aerie")
        self.put("packs/aerie/hexkit/bbtool.json", HELD)
        self.commit("hexkit, held")
        self.run_tool("--entry", "packs/aerie/hexkit")
        before = self.index()
        code, out = self.run_tool("--drop-older", "1")
        self.assertEqual(code, 0, out)
        self.assertIn("dropped 0 older pin(s) written in pack format 1", out)
        self.assertEqual(self.index(), before, "nothing went: the index is left alone, its date with it")
        self.assertIn("is as it was: nothing to write", out)
        code, out = self.run_tool("--drop-older", "2")
        self.assertIn("dropped 1 older pin(s) written in pack format 2", out)
        got = self.index()["packs"]
        self.assertEqual(got, [{k: v for k, v in e.items() if k != "older"} for e in before["packs"]], "the pin of that format, and nothing else")
        self.assertIsNone(packformat.pin_for(got[0], reads=2), "a build that reads only format 2 is no longer served")

    def test_an_entry_that_says_another_word_than_its_folder_is_said(self):
        self.run_tool("--entry", "packs/aerie/hexkit", "packs/apps/whoami", "--tier", "aerie")
        e = self.entry("hexkit")
        self.assertEqual(catalogentry.differs({**e, "held": "pinned", "platforms": ["linux/arm64"], "format": 5}, self.url),
                         ["the entry says format 5 and its manifest 2", "the entry says platforms ['linux/arm64'] and its manifest ['linux/amd64']",
                          "the entry says held pinned and its manifest open"])
        self.assertEqual(catalogentry.differs({k: v for k, v in e.items() if k not in ("held", "label")}, self.url),
                         ["the entry says held (nothing) and its manifest open"], "a label may be left out; the word may not")
        self.assertIn("has no bbtool.json", catalogentry.differs({**self.entry("whoami"), "kind": "pack"}, self.url)[0], "an app read as a pack")
        self.assertIn("not what the catalog vetted", catalogentry.differs({**e, "sha256": "0" * 64}, self.url)[0])

    def test_the_official_entries_are_written_from_the_folders_this_tree_exports(self):
        # An official entry the index has from before, at a commit where its
        # folder held an earlier manifest: its own is kept, and its pin too.
        self.put("packs/official/go/bbtool.json", {"name": "go"})
        old = self.commit("go, as it was")
        self.put("index.json", {**self.index(), "packs": [
            {"name": "go", "url": "https://github.com/aquilaelabs/aerieos-catalog", "commit": old, "path": "packs/official/go", "sha256": "1" * 64,
             "tier": "official", "withdrawn": False, "about": "Go.", "platforms": ["linux/amd64"], "maker": "Google", "framework": "2.1",
             "topics": ["languages"], "added": "2026-10-28"},
            {"name": "gone", "url": "https://github.com/aquilaelabs/aerieos-catalog", "commit": old, "path": "packs/official/gone", "sha256": "2" * 64,
             "tier": "official", "about": "A row no longer shipped.", "platforms": ["linux/amd64"], "maker": "Nobody"}]})
        self.run_tool("--entry", "packs/aerie/hexkit", "--tier", "aerie")
        self.assertEqual(self.run_tool()[0], 0, "the official packs written under the catalog's packs/")
        head = self.commit("the official packs")
        code, out = self.run_tool("--index")
        self.assertEqual(code, 0, out)
        want = self.tool.catalog_dir_paths(self.cat)
        got = self.index()["packs"]
        self.assertEqual([e["name"] for e in got], [name for _p, _m, name in want] + ["gone", "hexkit"], "the official entries, then the others as they were")
        self.assertTrue(all(e["tier"] == "official" and e["commit"] == head and e["held"] in packformat.HELD_WORDS for e in got[:-2]))
        # An official entry this tree does not export is not this tool's to
        # take away: a release listed in the catalog may still take it.
        self.assertEqual(next(e for e in got if e["name"] == "gone")["commit"], old)
        self.assertIn("gone is an official entry this tree does not export: kept as it was", out)
        # ...and a new one says that it names no topics yet, and how to.
        self.assertIn("names no topics", out)
        self.assertNotIn("go names no topics", out)
        go = next(e for e in got if e["name"] == "go")
        manifest = json.loads(Path(self.cat, "packs/official/go/bbtool.json").read_text())
        self.assertEqual((go["format"], go["topics"], go["added"], go["shipped_rev"]), (manifest["format"], ["languages"], "2026-10-28", manifest["shipped"]["rev"]))
        self.assertEqual(go["older"], [{"format": 1, "framework": "2.1", "commit": old, "sha256": "1" * 64, "platforms": ["linux/amd64"]}])
        self.assertIn(f"go: pack format 1 to {manifest['format']}: its format 1 pin is kept as an older one", out)
        # Every one is an entry an install parses, and says what its folder says.
        idx, why = catalogindex.parse(Path(self.cat, "index.json").read_bytes())
        self.assertEqual((why, len(idx["packs"])), ("", len(got)), why)
        for name in ("go", "diagrams", "claude", "model-router", "android-emulator"):
            e = next(e for e in got if e["name"] == name)
            self.assertEqual(catalogentry.differs(packformat.pin_for(e), self.url), [], name)
        agent = next(e for e in got if e["name"] == "claude")
        self.assertEqual((agent["held"], agent.get("online")),
                         tuple(packformat.held_entry(packformat.agent_held(json.loads(Path(self.cat, "packs/agents/claude/bbtool.json").read_text())["agent"]["install"])).get(k)
                               for k in ("held", "online")))
        self.assertEqual(next(e for e in got if e["name"] == "model-router")["kind"], "service")
        # Written again with nothing changed, it is the same index but for its date.
        self.assertEqual(self.run_tool("--index", "--drop-older", "1")[0], 0)
        again = self.index()["packs"]
        self.assertEqual(again, [{k: v for k, v in e.items() if k != "older"} for e in got], "and the format named is the one dropped")


if __name__ == "__main__":
    unittest.main()


class NeverBack(unittest.TestCase):
    """A pin moved in the catalog between releases raises a recipe's rev
    there. Written over from a tree that has not taken the move, the catalog
    would go back to the older recipe: the export refuses, naming the pack."""

    def setUp(self):
        self.d = tempfile.mkdtemp()
        self.addCleanup(shutil.rmtree, self.d, True)
        self.t = tool()

    def test_a_revision_is_read_wherever_a_pack_carries_it(self):
        rev = self.t._rev
        self.assertEqual(rev({"shipped": {"rev": 3}}), 3)
        self.assertEqual(rev({"agent": {"install": {"rev": 4}}}), 4)
        self.assertEqual(rev({"service": {"kind": "router"}}), 0)
        self.assertEqual(rev({"shipped": {"rev": True}}), 0)
        self.assertEqual(rev(None), 0)

    def test_a_later_recipe_in_the_catalog_is_not_written_over(self):
        self.t.catalog_write(self.d)                    # the folders, as this tree has them
        self.assertEqual(self.t.catalog_ahead(self.d), [])
        path, mine, name = next(x for x in self.t.catalog_dir_paths(self.d) if self.t._rev(x[1]))
        with open(path, encoding="utf-8") as f:
            there = json.load(f)
        if isinstance(there.get("shipped"), dict) and there["shipped"].get("rev"):
            there["shipped"]["rev"] += 1
        else:
            there["agent"]["install"]["rev"] += 1
        with open(path, "w", encoding="utf-8") as f:
            json.dump(there, f)
        self.assertEqual(self.t.catalog_ahead(self.d), [(name, self.t._rev(mine) + 1, self.t._rev(mine))])
        with self.assertRaises(SystemExit) as e:
            self.t.catalog_write(self.d)
        self.assertIn(name, str(e.exception))
        self.assertIn("tools/pins.py move", str(e.exception))
        with open(path, encoding="utf-8") as f:
            self.assertEqual(json.load(f), there, "nothing was written")
