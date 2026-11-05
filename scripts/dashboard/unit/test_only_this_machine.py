"""What a landing move asks of the nodes: every install has its built-in row,
so that row cannot count against it, or a move could never land anywhere."""
import sys
import unittest
from pathlib import Path
from unittest import mock

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

import nodes  # noqa: E402

LOCAL = {"id": "local", "kind": "local", "config": {}}
OWN = {"id": "n_a", "kind": "agent", "config": {"own": True}}
OTHER = {"id": "n_b", "kind": "agent", "config": {}}


class OnlyThisMachine(unittest.TestCase):
    def says(self, *rows):
        with mock.patch.object(nodes, "node_list", return_value=list(rows)):
            return nodes.only_this_machine()

    def test_a_container_install_has_only_its_built_in_row(self):
        self.assertTrue(self.says(LOCAL))

    def test_a_machine_of_its_own_adds_itself(self):
        self.assertTrue(self.says(LOCAL, OWN))

    def test_any_other_node_is_something_a_move_would_replace(self):
        self.assertFalse(self.says(LOCAL, OTHER))
        self.assertFalse(self.says(LOCAL, OWN, OTHER))


if __name__ == "__main__":
    unittest.main()
