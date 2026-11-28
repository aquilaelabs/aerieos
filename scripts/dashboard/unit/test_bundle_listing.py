"""The list of the files a release ships in the bundle, and
the bundle the controller packs around it.

scripts/lib/bundleparts.py says which files those are and lists them one
way: a line a file, its sha256 and its name, in the names' order, with
Python's bytecode left out. The controller packs the bundle from the same
files and carries the list as nodes/bundle.list, made from the very bytes
the tar holds; the release's signature over the list rides beside it where
the build made one; and the catalog's newer rows ride as a member of their
own, so config/toolchains.json is the shipped file byte for byte."""
import hashlib
import io
import json
import os
import pathlib
import shutil
import sys
import tarfile
import tempfile
import unittest
from contextlib import redirect_stdout
from unittest import mock

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, os.path.join(HERE, ".."))
sys.path.insert(0, os.path.join(HERE, "..", "..", "lib"))
import bundleparts  # noqa: E402
import workspace  # noqa: E402

SHIPPED = b'{"toolchains": [{"name": "zig", "rev": 1}]}\n'
TREE = {"scripts/aerie": b"#!/bin/bash\necho aerie\n", "scripts/lib/sdk.sh": b"sdk\n", "scripts/lib/sdkmeta.py": b"meta = 1\n",
        "scripts/lib/__pycache__/sdkmeta.cpython-312.pyc": b"\x00bytecode", "scripts/lib/stray.pyc": b"\x00more",
        "scripts/lib/.DS_Store": b"finder", "config/toolchains.json": SHIPPED,
        "config/release-keys/README.md": b"keys\n", "nodes/bb-session": b"#!/bin/sh\n",
        "scripts/dashboard/server.py": b"not a part\n"}


def tree(files=TREE):
    root = tempfile.mkdtemp()
    for name, data in files.items():
        os.makedirs(os.path.dirname(os.path.join(root, name)), exist_ok=True)
        with open(os.path.join(root, name), "wb") as f:
            f.write(data)
    return root


class Listing(unittest.TestCase):
    def setUp(self):
        self.root = tree()
        self.addCleanup(shutil.rmtree, self.root, True)

    def test_the_files_are_the_parts_own_by_name_and_no_bytecode(self):
        got = bundleparts.files(self.root)
        names = [n for n, _p in got]
        self.assertEqual(names, ["config/release-keys/README.md", "config/toolchains.json", "nodes/bb-session",
                                 "scripts/aerie", "scripts/lib/sdk.sh", "scripts/lib/sdkmeta.py"])
        self.assertEqual(names, sorted(names), "in the names' order")
        self.assertTrue(all(os.path.isfile(p) for _n, p in got))
        self.assertIn("nodes/provision-linux.sh", bundleparts.missing(self.root), "a part that is not there is named")
        self.assertNotIn("scripts/lib", bundleparts.missing(self.root))

    def test_the_list_is_a_line_a_file_in_the_form_of_a_sums_file(self):
        text, digest = bundleparts.listing(self.root)
        lines = text.splitlines()
        self.assertTrue(text.endswith("\n"))
        self.assertEqual(lines[1], hashlib.sha256(SHIPPED).hexdigest() + "  config/toolchains.json")
        self.assertEqual([ln.split("  ", 1)[1] for ln in lines], [n for n, _p in bundleparts.files(self.root)])
        self.assertTrue(all(len(ln.split("  ", 1)[0]) == 64 for ln in lines))
        self.assertEqual(digest, "sha256:" + hashlib.sha256(text.encode()).hexdigest())

    def test_the_digest_is_the_same_however_the_files_are_handed_over(self):
        text, digest = bundleparts.listing(self.root)
        self.assertEqual(bundleparts.listing(self.root), (text, digest), "asked again")
        as_bytes = [(n, pathlib.Path(p).read_bytes()) for n, p in reversed(bundleparts.files(self.root))]
        self.assertEqual(bundleparts.listing(as_bytes), (text, digest), "from the bytes, in another order")
        self.assertEqual(bundleparts.listing(pathlib.Path(self.root)), (text, digest), "from a Path")
        # Another tree with the same files lists the same, bytecode or none.
        other = tree({k: v for k, v in TREE.items() if "pyc" not in k})
        self.addCleanup(shutil.rmtree, other, True)
        self.assertEqual(bundleparts.listing(other), (text, digest))
        with open(os.path.join(other, "scripts", "lib", "sdk.sh"), "ab") as f:
            f.write(b"# one more line\n")
        self.assertNotEqual(bundleparts.listing(other)[1], digest, "a changed file moves it")
        with self.assertRaises(ValueError):
            bundleparts.listing([("scripts/a\nb", b"")])

    def test_the_controllers_name_for_the_parts_is_this_one(self):
        self.assertIs(workspace.BUNDLE_PARTS, bundleparts.PARTS)


class TheControllersBundle(unittest.TestCase):
    def setUp(self):
        self.root = tree()
        self.addCleanup(shutil.rmtree, self.root, True)
        self.said = io.StringIO()
        self.newer = ""
        for p in (mock.patch.object(workspace, "REPO", pathlib.Path(self.root)), mock.patch.object(workspace, "_bundle", {}),
                  mock.patch.object(workspace, "_bundle_missing", set()), mock.patch.object(workspace, "packs_json", None),
                  mock.patch.object(workspace, "packs_files", None),
                  mock.patch.object(workspace, "toolchains_json", lambda shipped: self.newer)):
            p.start()
            self.addCleanup(p.stop)

    def bundle(self):
        with redirect_stdout(self.said):
            return workspace.bundle()

    def members(self, body):
        with tarfile.open(fileobj=io.BytesIO(body)) as tar:
            return {m.name: tar.extractfile(m).read() for m in tar.getmembers()}

    def sign(self, digest, part="bundle"):
        os.makedirs(os.path.join(self.root, "scripts", "agent"), exist_ok=True)
        with open(os.path.join(self.root, "scripts", "agent", "agent.sig"), "w") as f:
            json.dump({"digest": "sha256:" + "00" * 32, "sig": "ab" * 64, part: {"digest": digest, "sig": "cd" * 64}}, f)

    def test_it_carries_the_list_of_its_own_bytes_and_no_bytecode(self):
        b = self.bundle()
        got = self.members(b["body"])
        text = got.pop(workspace.BUNDLE_LIST).decode()
        self.assertEqual(sorted(got), [n for n, _p in bundleparts.files(self.root)], "the release's files and nothing else")
        self.assertFalse([n for n in got if n.endswith(".pyc") or "__pycache__" in n or n.endswith(".DS_Store")])
        self.assertEqual(text, "".join(f"{hashlib.sha256(got[n]).hexdigest()}  {n}\n" for n in sorted(got)),
                         "the list is of the bytes the tar holds")
        self.assertEqual((text, b["files"]), bundleparts.listing(self.root), "and is the one a signer makes from the tree")
        self.assertIs(b["files_signed"], False)
        self.assertNotIn(workspace.BUNDLE_SIG, got, "a build from a branch signs nothing")

    def test_the_same_files_make_the_same_bundle_at_every_start(self):
        first = self.bundle()
        workspace._bundle.clear()
        self.assertEqual(self.bundle()["digest"], first["digest"], "a restart sends no node a new bundle")

    def test_the_shipped_catalog_goes_as_it_is_and_the_newer_rows_beside_it(self):
        before = self.bundle()
        self.newer = '{"toolchains": [{"name": "zig", "rev": 2}]}\n'
        after = self.bundle()
        got = self.members(after["body"])
        self.assertEqual(got["config/toolchains.json"], SHIPPED, "byte for byte the shipped file")
        self.assertEqual(got[workspace.CATALOG_ROWS].decode(), self.newer)
        self.assertNotEqual(after["digest"], before["digest"], "the bundle moves with the catalog's rows")
        self.assertEqual(after["files"], before["files"], "and the list a release signs does not")
        self.assertNotIn(workspace.CATALOG_ROWS, self.members(before["body"]))

    def test_the_signature_rides_only_with_a_signed_build_and_is_passed_on_as_it_is(self):
        listed = self.bundle()["files"]
        self.sign(listed)
        b = self.bundle()
        got = self.members(b["body"])
        self.assertEqual(json.loads(got[workspace.BUNDLE_SIG]), {"digest": listed, "sig": "cd" * 64})
        self.assertIs(b["files_signed"], True)
        self.assertEqual(b["files"], listed)
        self.assertNotIn("not the ones this build signed", self.said.getvalue())
        self.assertNotIn("nodes/root-tools.sig", got, "no second signature over root's tools alone")
        # A part that is not a signature rides nowhere.
        with open(os.path.join(self.root, "scripts", "agent", "agent.sig"), "w") as f:
            json.dump({"bundle": {"digest": listed, "sig": "not one"}}, f)
        self.assertNotIn(workspace.BUNDLE_SIG, self.members(self.bundle()["body"]))

    def test_files_that_are_not_the_ones_signed_are_said_once(self):
        self.sign("sha256:" + "11" * 32)
        b = self.bundle()
        self.assertIs(b["files_signed"], False)
        self.assertIn(workspace.BUNDLE_SIG, self.members(b["body"]), "passed on all the same: the node is the one that checks")
        workspace._bundle.clear()
        self.bundle()
        said = self.said.getvalue()
        self.assertEqual(said.count("are not the ones this build signed"), 1, said)
        self.assertIn("a node that pinned a release key refuses them", said)

    def test_the_real_tree_lists_as_the_signer_would(self):
        root = pathlib.Path(HERE).parents[2]
        with mock.patch.object(workspace, "REPO", root):
            b = self.bundle()
        got = self.members(b["body"])
        self.assertEqual(got[workspace.BUNDLE_LIST].decode(), bundleparts.listing(root)[0])
        self.assertEqual(got["config/toolchains.json"], (root / "config" / "toolchains.json").read_bytes())


class TheNodesStatus(unittest.TestCase):
    """An administrator's read of the Nodes page says which list of files
    this install's bundle ships and whether its build signed it, so an
    install can be held against a checkout (tools/sign-agent.py --digests)."""

    def test_it_names_the_list_and_whether_the_build_signed_it(self):
        import nodes
        nodes.configure(state=tempfile.mkdtemp())
        listed = bundleparts.listing(pathlib.Path(HERE).parents[2])[1]
        with mock.patch.object(nodes, "bundle_files", lambda: (listed, True)):
            got = nodes.tab_view([], True)["agent"]
            self.assertEqual((got["files"], got["files_signed"]), (listed[7:23], True))
            self.assertEqual(len(got["files"]), 16)
            self.assertEqual(nodes.tab_view([], False)["agent"], {}, "an administrator's alone")
        with mock.patch.object(nodes, "bundle_files", lambda: ("", False)):
            got = nodes.tab_view([], True)["agent"]
            self.assertEqual((got["files"], got["files_signed"]), ("", False))


if __name__ == "__main__":
    unittest.main()
