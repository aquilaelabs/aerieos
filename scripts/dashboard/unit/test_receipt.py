"""An install's receipt (R234; the operator, 13 Nov: what a pack's install
downloads from somewhere else had no paper trail). The installer writes
every file that landed with its sha256 and one hash over them all
(sdkmeta.receipt), the agent reads the summary into its census, the
controller keeps the shape it knows, and an installed pack's row says what
the receipt shows: a copy from an earlier manifest, the same manifest
having left other files there before, and another node's copy differing."""
import os
import shutil
import sys
import tempfile
import unittest
from unittest import mock

import agentpkg  # noqa: E402

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))
sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "..", "lib"))
import sdkmeta  # noqa: E402

agent = agentpkg.load("aerieos_agent_receipt")
C1, C2 = "a" * 40, "b" * 40


def put(root, rel, text="x", mode=0o644):
    full = os.path.join(root, rel)
    os.makedirs(os.path.dirname(full), exist_ok=True)
    with open(full, "w") as f:
        f.write(text)
    os.chmod(full, mode)


class Receipt(unittest.TestCase):
    def store(self):
        root = tempfile.mkdtemp()
        self.addCleanup(shutil.rmtree, root, True)
        return root

    def pack(self, store, name="hexkit", fetched="one"):
        d = os.path.join(store, name)
        put(d, "bbtool.json", "{}")
        put(d, "install.sh", "#!/bin/sh\n", 0o755)
        # What its install steps fetched from somewhere else.
        put(d, "bin/hexkit", fetched, 0o755)
        os.symlink("hexkit", os.path.join(d, "bin", "hk"))
        # What a receipt leaves out: git's own, AerieOS's marks, compiled python.
        put(d, ".git/HEAD", "ref")
        put(d, ".bb-verified", "sha1\t" + C1 + "\tthe commit\n")
        put(d, "verbs/__pycache__/report.cpython-312.pyc", "moment")
        put(d, "verbs/old.pyc", "moment")
        return d

    def read(self, d):
        with open(os.path.join(d, ".bb-receipt")) as f:
            head, *rows = f.read().splitlines()
        return head.split("\t"), rows

    def test_every_file_that_landed(self):
        store = self.store()
        d = self.pack(store)
        said = sdkmeta.receipt(d, C1)
        head, rows = self.read(d)
        self.assertEqual(head[:2], ["1", C1])
        self.assertEqual([r.split("  ")[-1] for r in rows], ["bbtool.json", "bin/hexkit", "bin/hk", "install.sh"])
        self.assertEqual(int(head[3]), 4)
        self.assertEqual(int(head[4]), len("{}") + len("one") + len("#!/bin/sh\n"))
        self.assertEqual(head[6], "")
        self.assertRegex(head[2], r"^[0-9a-f]{64}$")
        # A file says whether it runs, a link where it points.
        self.assertTrue(rows[1].split("  ")[1] == "x" and rows[0].split("  ")[1] == "-", rows)
        self.assertEqual(rows[2], "link  hexkit  bin/hk")
        self.assertIn("receipt: 4 files", said)
        # The store's own log, which a remove and a reinstall leave alone.
        with open(os.path.join(store, ".bb-receipts")) as f:
            log = [ln.split("\t") for ln in f.read().splitlines()]
        self.assertEqual([(r[1], r[2], r[3]) for r in log], [("hexkit", C1, head[2])])

    def test_the_same_files_are_the_same_receipt(self):
        a, b = self.pack(self.store()), self.pack(self.store())
        sdkmeta.receipt(a, C1)
        sdkmeta.receipt(b, C1)
        self.assertEqual(self.read(a)[0][2], self.read(b)[0][2])
        # ...written again over itself, it does not count its own file.
        sdkmeta.receipt(a, C1)
        self.assertEqual(self.read(a)[0][2], self.read(b)[0][2])

    def test_what_was_fetched_changed(self):
        store = self.store()
        d = self.pack(store, fetched="one")
        sdkmeta.receipt(d, C1)
        first = self.read(d)[0][2]
        # Removed and installed again from the same commit: its install
        # fetched something else this time.
        shutil.rmtree(d)
        d = self.pack(store, fetched="two")
        said = sdkmeta.receipt(d, C1)
        head, _ = self.read(d)
        self.assertNotEqual(head[2], first)
        self.assertEqual(head[6], first)
        self.assertIn("the same commit made " + first[:12], said)
        # From another commit, other files are what was asked for.
        shutil.rmtree(d)
        d = self.pack(store, fetched="three")
        sdkmeta.receipt(d, C2)
        self.assertEqual(self.read(d)[0][6], "")

    def test_the_agent_reads_each_summary(self):
        store = self.store()
        d = self.pack(store)
        sdkmeta.receipt(d, C1)
        head, _ = self.read(d)
        os.makedirs(os.path.join(store, "old"))
        put(os.path.join(store, "bad"), ".bb-receipt", "1\t" + C1 + "\tnot-a-hash\t1\t1\t1\t\n")
        put(os.path.join(store, "newer"), ".bb-receipt", "9\twhatever\n")
        mod = sys.modules[agent.sdk_receipts.__module__]
        with mock.patch.object(mod, "tc_root", lambda state: store):
            got = agent.sdk_receipts({})
        self.assertEqual(set(got), {"hexkit"})
        self.assertEqual({k: got["hexkit"][k] for k in ("commit", "tree", "files", "before")},
                         {"commit": C1, "tree": head[2], "files": 4, "before": ""})

    def test_the_controller_keeps_the_shape_it_knows(self):
        import nodes  # noqa: PLC0415
        t = "c" * 64
        out = nodes._census({"toolchain_receipts": {
            "hexkit": {"commit": C1, "tree": t, "files": 4, "bytes": 15, "at": 1700000000, "before": "d" * 64, "extra": "dropped"},
            "evil": {"commit": C1, "tree": "$(rm -rf /)", "files": 1}, "odd": "not a dict",
            "junk": {"commit": "zz; rm", "tree": t, "files": "many", "bytes": 1, "at": 1}}})
        self.assertEqual(out["toolchain_receipts"], {"hexkit": {"commit": C1, "tree": t, "files": 4, "bytes": 15, "at": 1700000000, "before": "d" * 64}})

    def test_what_a_row_says(self):
        import toolchains  # noqa: PLC0415
        t1, t2 = "1" * 64, "2" * 64
        mine = {"toolchain_receipts": {"hexkit": {"commit": C1, "tree": t1, "files": 4, "bytes": 15, "at": 5, "before": ""}}}

        class Nodes:
            others = []

            @staticmethod
            def node_list():
                return [{"id": "n_me", "name": "me", "reported": mine}, *Nodes.others]

        with mock.patch.object(toolchains, "nodes", Nodes):
            row = {"source": {"commit": C1}}
            got = toolchains.receipt_of("n_me", mine, "hexkit", row)
            self.assertEqual((got["tree"], got["stale"], got["before"], got["differs"]), (t1, "", "", []))
            # The manifest kept now is a later one: the copy there is stale.
            self.assertEqual(toolchains.receipt_of("n_me", mine, "hexkit", {"source": {"commit": C2}})["stale"], C2)
            # Another node's copy of the same manifest is other files; one
            # from another manifest, or the same files, is not said.
            Nodes.others = [{"id": "n_a", "name": "alder", "reported": {"toolchain_receipts": {"hexkit": {"commit": C1, "tree": t2}}}},
                            {"id": "n_b", "name": "birch", "reported": {"toolchain_receipts": {"hexkit": {"commit": C2, "tree": t2}}}},
                            {"id": "n_c", "name": "cedar", "reported": {"toolchain_receipts": {"hexkit": {"commit": C1, "tree": t1}}}}]
            self.assertEqual(toolchains.receipt_of("n_me", mine, "hexkit", row)["differs"], [{"node": "alder", "tree": t2}])
            # Installed before receipts, or by an agent from before them.
            self.assertIsNone(toolchains.receipt_of("n_me", {}, "hexkit", row))
            self.assertIsNone(toolchains.receipt_of("n_me", mine, "other", row))


if __name__ == "__main__":
    unittest.main()
