"""What a node's heartbeat says of each account's plugins and MCP servers
(plugins.report): written when it differs from what is kept, and only then,
since it arrives on every heartbeat; a row with neither drops that node."""
import json
import os
import shutil
import sys
import tempfile
import unittest

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))
import plugins  # noqa: E402


def write_json(path, d):
    with open(path, "w") as f:
        json.dump(d, f)


ROW = {"uid": "u_abc", "plugins": [{"id": "fmt@market", "version": "1.2", "enabled": True}],
       "mcp": {"claude": ["github"]}}


class Report(unittest.TestCase):
    def setUp(self):
        self.d = tempfile.mkdtemp()
        self.addCleanup(shutil.rmtree, self.d, True)
        plugins.configure(state=self.d, write_json=write_json)

    def test_written_once_then_only_when_it_differs(self):
        self.assertTrue(plugins.report("n_1", [ROW]))
        got = plugins.of("u_abc")
        self.assertEqual([(g["node"], [p["id"] for p in g["plugins"]], g["mcp"]) for g in got],
                         [("n_1", ["fmt@market"], {"claude": ["github"]})])
        self.assertFalse(plugins.report("n_1", [ROW]), "the same report again costs no write")
        self.assertTrue(plugins.report("n_1", [{**ROW, "mcp": {"claude": ["github", "linear"]}}]))
        self.assertEqual(plugins.of("u_abc")[0]["mcp"], {"claude": ["github", "linear"]})

    def test_a_row_with_neither_drops_that_node(self):
        plugins.report("n_1", [ROW])
        plugins.report("n_2", [ROW])
        self.assertTrue(plugins.report("n_1", [{"uid": "u_abc"}]))
        self.assertEqual([g["node"] for g in plugins.of("u_abc")], ["n_2"])
        self.assertTrue(plugins.report("n_2", [{"uid": "u_abc", "plugins": None}]))
        self.assertEqual(plugins.of("u_abc"), [])


if __name__ == "__main__":
    unittest.main()
