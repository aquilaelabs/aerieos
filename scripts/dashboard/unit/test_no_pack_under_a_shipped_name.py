"""State 27: a tool pack kept under the name of a toolchain AerieOS ships
(what an allowed `aerie tool install jdk` left, B1040) goes, with its kept
copy; every other pack is left as it is; a second run changes nothing; and
what is left is what toolpacks.py reads."""
import importlib
import json
import os
import shutil
import sys
import tempfile
import unittest
from pathlib import Path

sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)), ".."))
import statefile  # noqa: E402
import stateversion  # noqa: E402
import toolchains  # noqa: E402
import toolpacks  # noqa: E402

MANIFEST = {"name": "hexkit", "label": "Hex kit", "about": "Looks inside binaries.", "tier": "url", "format": 1,
            "platforms": ["linux/amd64"], "terms": [], "layout": {"bin": ["bin"], "tool": "bin/hexkit"}, "steps": [],
            "verbs": {"dump": {"about": "hex", "usage": "FILE", "run": ["{dir}/bin/hexkit", "{args}"]}}}


def record(name, **more):
    return {"name": name, "url": "https://example.com/catalog", "commit": "a" * 40, "manifest": dict(MANIFEST, name=name),
            "guidance": "", "by": "session:alpha (allowed by ann)", "at": 1763600000, "tier": "url", "sha256": "", **more}


class Migration(unittest.TestCase):
    def setUp(self):
        self.d = Path(tempfile.mkdtemp())
        self.addCleanup(shutil.rmtree, self.d, True)
        self.mig = importlib.import_module("statemigrations.0027_no_pack_under_a_shipped_name")
        self.file = self.d / self.mig.FILE

    def keep(self, packs):
        """The packs' records, and for each one kept hosted its repository,
        its bundle and an icon, as toolpacks.py lays them out."""
        self.file.write_text(json.dumps({"packs": packs}, indent=2) + "\n")
        os.chmod(self.file, 0o640)
        for name, rec in packs.items():
            if isinstance(rec, dict) and rec.get("hosted"):
                (self.d / "toolpacks" / f"{name}.git" / "objects").mkdir(parents=True)
                (self.d / "toolpacks" / f"{name}.git" / "HEAD").write_text("ref: refs/heads/main\n")
                (self.d / "toolpacks" / f"{name}.bundle").write_bytes(b"bundle")
                (self.d / "pack-icons").mkdir(exist_ok=True)
                (self.d / "pack-icons" / f"{name}.png").write_bytes(b"png")

    def kept(self):
        return sorted(str(p.relative_to(self.d)) for p in self.d.rglob("*") if p.is_file())

    def test_a_pack_named_as_a_shipped_toolchain_goes_with_its_kept_copy(self):
        self.assertIn("jdk", self.mig.shipped(), "the toolchain the stray pack was kept under")
        self.assertEqual(self.mig.shipped(), {r["name"] for r in toolchains.load_toolchains()}, "the names this build ships, as the add refuses them")
        packs = {"jdk": record("jdk", hosted=True, path="packs/official/jdk", tier="official", sha256="c" * 64, kept_at="d" * 40),
                 "hexkit": record("hexkit", hosted=True), "byaddress": record("byaddress"), "go": record("go")}
        self.keep(packs)
        self.mig.run({"state": self.d})
        got = json.loads(self.file.read_text())
        self.assertEqual(got, {"packs": {"hexkit": packs["hexkit"], "byaddress": packs["byaddress"]}}, "every other pack is as it was")
        self.assertEqual(self.file.stat().st_mode & 0o777, 0o640, "with the mode the file had")
        self.assertEqual(self.kept(), ["pack-icons/hexkit.png", "toolpacks.json", "toolpacks/hexkit.bundle", "toolpacks/hexkit.git/HEAD"])
        self.assertFalse((self.d / "toolpacks" / "jdk.git").exists(), "its repository here goes whole")
        # A second run changes nothing and writes nothing.
        before = (self.file.read_bytes(), self.file.stat().st_mtime_ns, self.kept())
        self.mig.run({"state": self.d})
        self.assertEqual((self.file.read_bytes(), self.file.stat().st_mtime_ns, self.kept()), before)
        # What is left is what the Library and aerie tool search read.
        was = (toolpacks.FILE, toolpacks.write_json, toolpacks.HOSTED, toolpacks.unpack)
        self.addCleanup(lambda: toolpacks.__dict__.update(FILE=was[0], write_json=was[1], HOSTED=was[2], unpack=was[3]))
        toolpacks.configure(state=self.d, write_json=statefile.write_json)
        self.assertEqual(sorted(toolpacks.packs()), ["byaddress", "hexkit"])
        self.assertEqual([r["name"] for r in toolpacks.recipes()], ["byaddress", "hexkit"])
        self.assertEqual([arc for arc, _ in toolpacks.hosted_files()], ["config/toolpacks/hexkit.bundle"])

    def test_a_start_cut_short_between_the_copy_and_the_record_finishes(self):
        # The kept copy goes first: a record still there with its copy gone
        # is found again and taken.
        self.keep({"jdk": record("jdk", hosted=True), "hexkit": record("hexkit", hosted=True)})
        shutil.rmtree(self.d / "toolpacks" / "jdk.git")
        (self.d / "toolpacks" / "jdk.bundle").unlink()
        self.mig.run({"state": self.d})
        self.assertEqual(sorted(json.loads(self.file.read_text())["packs"]), ["hexkit"])

    def test_nothing_to_take_writes_nothing(self):
        self.mig.run({"state": self.d})
        self.assertFalse(self.file.exists(), "no file is not made into one")
        for text in ("{not json", json.dumps(["jdk"]), json.dumps({"packs": ["jdk"]}),
                     json.dumps({"packs": {"hexkit": record("hexkit")}})):
            self.file.write_text(text)
            before = self.file.stat().st_mtime_ns
            self.mig.run({"state": self.d})
            self.assertEqual((self.file.read_text(), self.file.stat().st_mtime_ns), (text, before))

    def test_a_table_that_cannot_be_read_takes_nothing(self):
        self.keep({"jdk": record("jdk", hosted=True)})
        was = self.mig.TOOLCHAINS
        self.addCleanup(setattr, self.mig, "TOOLCHAINS", was)
        self.mig.TOOLCHAINS = self.d / "no-such-table.json"
        self.assertEqual(self.mig.shipped(), set())
        self.mig.run({"state": self.d})
        self.assertEqual(sorted(json.loads(self.file.read_text())["packs"]), ["jdk"])
        self.assertTrue((self.d / "toolpacks" / "jdk.git").is_dir())

    def test_it_is_the_state_this_build_writes_and_runs_from_the_one_before(self):
        self.assertGreaterEqual(stateversion.current(), 27)
        self.assertIn(27, [n for n, _ in stateversion.migrations()])
        # Through the door every upgrade takes: a /config at state 26 that
        # holds the stray pack is copied, migrated and stamped.
        (self.d / "users.json").write_text(json.dumps({"users": {}}))
        self.keep({"jdk": record("jdk", hosted=True), "hexkit": record("hexkit")})
        stateversion.stamp(self.d, 26, "0.9.0-dev.1")
        import contextlib
        import io
        with contextlib.redirect_stdout(io.StringIO()):
            self.assertEqual(stateversion.gate(self.d, "0.9.0-dev.2"), 26)
            ran = stateversion.migrate(self.d, {"state": self.d}, "0.9.0-dev.2")
        self.assertEqual(ran[0], 27)
        self.assertEqual(stateversion.read(self.d)[0], stateversion.current())
        self.assertEqual(sorted(json.loads(self.file.read_text())["packs"]), ["hexkit"])
        copy = self.d / "backups" / "before-0.9.0-dev.2"
        self.assertEqual(sorted(json.loads((copy / "toolpacks.json").read_text())["packs"]), ["hexkit", "jdk"],
                         "the copy taken before it keeps the record as it stood")
        self.assertTrue((copy / "toolpacks" / "jdk.bundle").is_file())


if __name__ == "__main__":
    unittest.main()
