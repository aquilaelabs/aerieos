"""An apply uses a target that already is this node's store as it is
(B661): the marker, the node's own toolchain folder, or a folder this agent
made for the store before says so, and a folder of someone else's files
does not."""
import os
import sys
import tempfile
import unittest

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, os.path.join(HERE, "..", "..", "agent"))
from aerieos_agent import stores  # noqa: E402


class StoreHere(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.root = self.tmp.name

    def tearDown(self):
        self.tmp.cleanup()

    def test_the_marker_says_a_store(self):
        p = os.path.join(self.root, "sdk")
        os.makedirs(p)
        with open(os.path.join(p, stores.STORE_ID_FILE), "w") as f:
            f.write("st_abc\n")
        self.assertEqual(stores.store_here(p, "artifacts", "n_9381e721"), "marked")

    def test_this_nodes_own_folder_says_a_toolchain_store(self):
        p = os.path.join(self.root, "sdk")
        os.makedirs(os.path.join(p, "n_9381e721"))
        self.assertEqual(stores.store_here(p, "toolchains", "n_9381e721"), "mine")
        # Another node's folder is not this node's, and the folder means
        # nothing for a role that does not scope by node.
        self.assertEqual(stores.store_here(p, "toolchains", "n_00000000"), "")
        self.assertEqual(stores.store_here(p, "artifacts", "n_9381e721"), "")

    def test_a_folder_this_agent_made_before_is_its_own(self):
        p = os.path.join(self.root, "artifacts", "shed")
        os.makedirs(p)
        with open(os.path.join(p, "a.apk"), "w") as f:
            f.write("x")
        self.assertEqual(stores.store_here(p, "artifacts", "n_9381e721", made=[p]), "own")
        self.assertEqual(stores.store_here(p + "/", "artifacts", "n_9381e721", made=[p]), "own")

    def test_somebody_elses_files_are_not_a_store(self):
        p = os.path.join(self.root, "stuff")
        os.makedirs(p)
        with open(os.path.join(p, "notes.txt"), "w") as f:
            f.write("x")
        self.assertEqual(stores.store_here(p, "artifacts", "n_9381e721"), "")
        self.assertEqual(stores.store_here(os.path.join(self.root, "missing"), "toolchains", "n_9381e721"), "")


if __name__ == "__main__":
    unittest.main()
