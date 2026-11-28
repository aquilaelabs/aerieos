"""agentids.py: the one list of the coding agents that ship, held to the
dashboard's table of them (agents.py), to the case in bb-tty that passes
over them before it asks whether a name is a pack's agent, and to the two
copies a node's own programs carry (the agent's and bb-session's, neither
of which can read this folder); and the packs' rows, which read as nothing
from a file that is not there or not a list."""
import json
import os
import re
import sys
import tempfile
import unittest
import unittest.mock

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, os.path.join(HERE, ".."))
sys.path.insert(0, os.path.join(HERE, "..", "..", "lib"))
import agentids  # noqa: E402
import agents  # noqa: E402
sys.path.insert(0, HERE)
import agentpkg  # noqa: E402


class Shipped(unittest.TestCase):
    def test_the_list_is_the_dashboard_s_table(self):
        self.assertEqual(list(agentids.SHIPPED), [a.id for a in agents.TABLE])
        self.assertEqual(agents.IDS, agentids.SHIPPED)

    def test_the_copies_a_node_s_programs_carry_are_this_list(self):
        self.assertEqual(tuple(agentpkg.load("aerieos_agent").AGENT_IDS), agentids.SHIPPED)
        with open(os.path.join(HERE, "..", "..", "..", "nodes", "bb-session"), encoding="utf-8") as f:
            m = re.search(r"^AGENT_IDS = \(([^)]*)\)$", f.read(), re.M)
        self.assertIsNotNone(m, "bb-session's own list of the shipped agents")
        self.assertEqual(tuple(re.findall(r'"(\w+)"', m.group(1))), agentids.SHIPPED)

    def test_bb_tty_passes_over_each_before_asking_for_a_pack_s_agent(self):
        with open(os.path.join(HERE, "..", "bb-tty"), encoding="utf-8") as f:
            text = f.read()
        m = re.search(r'case "\$pa" in ([a-z|]+)\|\*\[!a-z0-9\]\*\) ;;', text)
        self.assertIsNotNone(m, "the case that tells a pack's agent from the names that are not one")
        self.assertEqual(m.group(1).split("|"), [*agentids.SHIPPED, "shell", "ctr"])


class Rows(unittest.TestCase):
    def rows(self, text):
        with tempfile.TemporaryDirectory() as d:
            p = os.path.join(d, "toolpacks.json")
            if text is not None:
                with open(p, "w", encoding="utf-8") as f:
                    f.write(text)
            with unittest.mock.patch.dict(os.environ, {"BB_TOOLPACKS_JSON": p}):
                return agentids.pack_rows(HERE)

    def test_the_rows_of_the_file_named(self):
        self.assertEqual(self.rows(json.dumps({"toolchains": [{"name": "kite"}, "odd"]})), [{"name": "kite"}, "odd"])

    def test_nothing_from_a_file_that_is_missing_or_is_not_one(self):
        for text in (None, "not json", "[]", json.dumps({"toolchains": {"name": "kite"}}), json.dumps({})):
            self.assertEqual(self.rows(text), [], text)

    def test_the_bundle_s_own_file_is_two_folders_up_from_the_caller(self):
        with unittest.mock.patch.dict(os.environ):
            os.environ.pop("BB_TOOLPACKS_JSON", None)
            self.assertEqual(os.path.normpath(agentids.packs_file(os.path.join("/b", "scripts", "lib"))),
                             os.path.join("/b", "config", "toolpacks.json"))


if __name__ == "__main__":
    unittest.main()
