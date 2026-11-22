"""bb-session's worktree verb takes a pack's coding agent as it takes a
shipped one (B783): the agents it knows are the five AerieOS ships and the
ones the node's own bundle lists with an adapter, and a branch is the
agent's own, AGENT/NAME. A name the bundle does not list is refused, so
the verb makes no tree under a word a caller invents."""
import importlib.machinery
import importlib.util
import json
import os
import tempfile
import unittest
from pathlib import Path

PATH = Path(__file__).resolve().parents[3] / "nodes" / "bb-session"


def load():
    loader = importlib.machinery.SourceFileLoader("bb_session_agents", str(PATH))
    spec = importlib.util.spec_from_loader("bb_session_agents", loader)
    m = importlib.util.module_from_spec(spec)
    loader.exec_module(m)
    return m


class Agents(unittest.TestCase):
    def setUp(self):
        self.s = load()
        self.d = tempfile.mkdtemp()
        os.makedirs(os.path.join(self.d, "config"))
        Path(self.d, "config", "toolpacks.json").write_text(json.dumps({"toolchains": [
            {"name": "gemini", "agent": {"command": "agy"}}, {"name": "hexkit"}, {"name": "claude", "agent": {}},
            {"name": "Bad-Name", "agent": {}}, {"name": "otter", "agent": "yes"}]}))
        self.c = {"BUNDLE": self.d}

    def test_the_pack_agents_are_the_bundle_s_rows_with_an_adapter(self):
        self.assertEqual(self.s.pack_agents(self.c), ("gemini",))
        self.assertEqual(self.s.pack_agents({"BUNDLE": ""}), ())
        self.assertEqual(self.s.pack_agents({"BUNDLE": os.path.join(self.d, "nowhere")}), ())

    def test_a_shipped_agent_and_a_pack_s_each_take_a_branch_of_their_own(self):
        for agent, branch, ok in (("claude", "claude/pat", True), ("grok", "grok/pat-2", True), ("gemini", "gemini/pat", True),
                                  ("gemini", "gemini/pat.smith@x-3", True), ("gemini", "claude/pat", False), ("gemini", "gemini/", False),
                                  ("gemini", "gemini/../x", False), ("otter", "otter/pat", False), ("hexkit", "hexkit/pat", False),
                                  ("release", "release/1", False), ("", "/pat", False)):
            self.assertEqual(self.s.agent_branch(self.c, agent, branch), ok, (agent, branch))

    def test_with_no_bundle_the_shipped_agents_are_as_before(self):
        self.assertTrue(self.s.agent_branch({"BUNDLE": ""}, "codex", "codex/pat"))
        self.assertFalse(self.s.agent_branch({"BUNDLE": ""}, "gemini", "gemini/pat"))


if __name__ == "__main__":
    unittest.main()
