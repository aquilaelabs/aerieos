"""A shipped toolchain's recipe from the catalog when the catalog's is newer
(R234 step 4): every row comes back whole from its official pack's
manifest, a newer one is fetched at its pin and held to its shape, the
controller's table and the nodes' bundle carry it in the shipped row's
place, and the image's copy is what runs whenever the catalog's is no
newer or is one this build does not read."""
import copy
import io
import json
import os
import sys
import tarfile
import tempfile
import unittest
from pathlib import Path
from unittest import mock

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))
import catalogindex  # noqa: E402
import catalogrows  # noqa: E402
import toolpacks  # noqa: E402
import workspace  # noqa: E402

ROOT = Path(__file__).resolve().parents[3]
SHIPPED = json.loads((ROOT / "config" / "toolchains.json").read_text())["toolchains"]


def plain(row):
    """A row with nothing its layout says empty, which a manifest leaves out."""
    return {**row, "layout": {k: v for k, v in row["layout"].items() if v or k in ("bin", "env")}}


class Whole(unittest.TestCase):
    def test_every_shipped_row_comes_back_whole_from_its_manifest(self):
        for r in SHIPPED:
            self.assertEqual(catalogrows.row_of(catalogrows.manifest_of(r)), plain(r), r["name"])
            self.assertEqual(toolpacks.validate(catalogrows.manifest_of(r))[1], [], r["name"])

    def test_every_word_a_shipped_row_names_is_a_primitive_this_build_lists(self):
        for r in SHIPPED:
            self.assertIn(r["source"]["kind"], catalogrows.KINDS, r["name"])
            for x in catalogrows._named(r, "resolver"):
                self.assertIn(x, catalogrows.RESOLVERS, r["name"])
            self.assertIn((r["source"].get("checksum") or {}).get("from"), (None, *catalogrows.CHECKSUMS), r["name"])
            self.assertEqual(catalogrows.checked(dict(r, rev=2), r)[1], "", r["name"])

    def test_the_docs_list_the_same_primitives(self):
        doc = (ROOT / "docs" / "tool-packs.md").read_text()
        line = next(ln for ln in doc.splitlines() if ln.startswith("| An official toolchain's source"))
        for word in (*catalogrows.KINDS, *catalogrows.RESOLVERS, *catalogrows.CHECKSUMS):
            self.assertIn(f"`{word}`", line, word)


class Taken(unittest.TestCase):
    def setUp(self):
        self.d = tempfile.mkdtemp()
        catalogrows.configure(state=self.d, write_json=lambda p, v: Path(p).write_text(json.dumps(v)))
        catalogrows._trying.clear()
        self.addCleanup(lambda: catalogrows.configure(state="/nonexistent", write_json=lambda *a: None))
        self.zig = next(r for r in SHIPPED if r["name"] == "zig")
        self.newer = copy.deepcopy(self.zig)
        self.newer["rev"] = 2
        self.newer["source"]["version"]["url"] = "https://ziglang.org/download/index-v2.json"
        self.fetched = []

    def entry(self, name="zig", rev=2, **more):
        return {"name": name, "url": "https://github.com/aquilaelabs/aerieos-catalog", "commit": "a" * 40, "sha256": "b" * 64,
                "path": f"packs/official/{name}", "tier": "official", "kind": "pack", **({"shipped_rev": rev} if rev else {}), **more}

    def fetch(self, row):
        def run(url, commit, sha256, path, names):
            self.fetched.append(path)
            return {"files": {"bbtool.json": json.dumps(catalogrows.manifest_of(row)).encode()}}
        return run

    def refresh(self, row=None, **entry):
        return catalogrows.refresh({"packs": [self.entry(**entry)]}, self.fetch(row or self.newer), SHIPPED, toolpacks.validate)

    def test_a_newer_row_is_fetched_once_and_stands_in_the_shipped_one_s_place(self):
        self.assertEqual(self.refresh(), [("zig", "")])
        got = catalogrows.merged(SHIPPED)
        self.assertEqual(next(r for r in got if r["name"] == "zig")["source"]["version"]["url"], "https://ziglang.org/download/index-v2.json")
        self.assertEqual([r["name"] for r in got], [r["name"] for r in SHIPPED], "in its place, nothing added or moved")
        self.assertEqual(sum(a != b for a, b in zip(got, SHIPPED, strict=True)), 1)
        self.assertEqual(self.refresh(), [], "it has it: nothing is wanted")
        self.assertEqual(self.fetched, ["packs/official/zig"])

    def test_the_index_s_parse_keeps_the_rev_an_entry_says(self):
        idx, why = catalogindex.parse(json.dumps({"version": 1, "packs": [self.entry(), self.entry(name="jdk", rev=None), self.entry(name="go", rev=1)]}).encode())
        self.assertEqual(why, "")
        self.assertEqual([p.get("shipped_rev") for p in idx["packs"]], [2, None, None])
        self.assertEqual([n for n, _e in catalogrows.wanted(idx, SHIPPED)], ["zig"])

    def test_an_entry_no_newer_than_the_shipped_row_is_never_fetched(self):
        self.assertEqual(self.refresh(rev=1), [])
        self.assertEqual(self.refresh(rev=None), [])
        self.assertEqual(catalogrows.refresh({"packs": [self.entry(tier="vetted")]}, self.fetch(self.newer), SHIPPED), [], "an official entry's alone")
        self.assertEqual(self.fetched, [])
        self.assertEqual(catalogrows.merged(SHIPPED), SHIPPED)

    def test_a_row_this_build_does_not_read_is_refused_and_the_shipped_one_stays(self):
        for change, said in (({"source": {**self.zig["source"], "kind": "appimage"}}, "its source is not one of"),
                             ({"source": {**self.zig["source"], "version": {"resolver": "crates-index", "url": "https://x.example"}}}, "crates-index, which this AerieOS does not carry"),
                             ({"source": {**self.zig["source"], "checksum": {"from": "minisign"}}}, "by minisign, which this AerieOS does not carry"),
                             ({"probe": "sh"}, "its name or its probe is not the shipped row's"),
                             ({"platforms": ["plan9/amd64"]}, "platforms lists where it works"),
                             ({"rev": 1}, "no newer than the shipped row")):
            catalogrows._trying.clear()
            self.fetched.clear()
            got = self.refresh(row={**self.newer, **change})
            self.assertEqual(len(got), 1, change)
            self.assertIn(said, got[0][1], change)
            self.assertEqual(catalogrows.merged(SHIPPED), SHIPPED, change)
        # A fetch that fails (the sha256 differs, no network) keeps nothing,
        # and is not asked again on the next read.
        catalogrows._trying.clear()
        bad = lambda *a: {"error": "its archive's sha256 differs, so it is refused"}  # noqa: E731
        self.assertEqual(catalogrows.refresh({"packs": [self.entry()]}, bad, SHIPPED), [("zig", "its archive's sha256 differs, so it is refused")])
        self.assertEqual(catalogrows.refresh({"packs": [self.entry()]}, bad, SHIPPED), [])
        self.assertEqual(catalogrows.kept(), {})

    def test_a_row_an_upgrade_caught_up_with_is_dropped(self):
        self.refresh()
        after = [dict(r, rev=2) if r["name"] == "zig" else r for r in SHIPPED]
        self.assertEqual(catalogrows.merged(after), after, "the image's own is as new: it is the one used")
        catalogrows.refresh({"packs": []}, self.fetch(self.newer), after)
        self.assertEqual(catalogrows.kept(), {})

    def test_the_bundle_the_nodes_install_from_carries_it(self):
        shipped_text = (ROOT / "config" / "toolchains.json").read_text()
        self.assertEqual(catalogrows.text(shipped_text), "", "nothing kept: the file goes as it is")
        self.refresh()
        doc = json.loads(catalogrows.text(shipped_text))
        self.assertEqual(sorted(doc), sorted(json.loads(shipped_text)), "everything beside the rows as it was")
        with mock.patch.object(workspace, "toolchains_json", catalogrows.text), mock.patch.object(workspace, "packs_json", None), \
                mock.patch.object(workspace, "packs_files", None), mock.patch.object(workspace, "REPO", ROOT), \
                mock.patch.dict(workspace._bundle, {}, clear=True):
            body = workspace.bundle()["body"]
        with tarfile.open(fileobj=io.BytesIO(body)) as tar:
            got = json.load(tar.extractfile("config/toolchains.json"))
        self.assertEqual(next(r for r in got["toolchains"] if r["name"] == "zig")["rev"], 2)
        self.assertEqual(len(got["toolchains"]), len(SHIPPED))


if __name__ == "__main__":
    unittest.main()
