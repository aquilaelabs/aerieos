"""The bell's Claude Code update counts the Claude sessions running on the
node, which the update ends, not the projects bound to it (B57: it said 5, 6
or 7 projects with 0 or 1 sessions running)."""
import os
import sys
import unittest

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))
import agents  # noqa: E402
import toolchains  # noqa: E402

NODE = {"id": "n1", "name": "box", "kind": "agent", "state": "online", "live": True, "reported": {}}


class Sessions(unittest.TestCase):
    def bell(self, rows):
        class Nodes:
            @staticmethod
            def node_list(**k):
                return [NODE]

            @staticmethod
            def node_sessions():
                return {"n1": ("box", rows)}

            def __getattr__(self, name):
                return lambda *a, **k: []

        class Claude:
            tracked = staticmethod(lambda: (agents.get("claude"),))
            behind = staticmethod(lambda n, aid: True)
            updating = staticmethod(lambda nid, aid: False)
            installed = staticmethod(lambda n, aid: "2.0.1")
            latest = staticmethod(lambda aid: {"version": "2.0.2"})
            # What an install brings: the newest, for a recipe that pins no program.
            offered = staticmethod(lambda aid: "2.0.2")

        was = toolchains.nodes, toolchains.last_check, toolchains.agentcode
        toolchains.nodes, toolchains.agentcode = Nodes(), Claude()
        toolchains.last_check = lambda nid: ({}, None)
        try:
            bound = {"alpha": "n1", "beta": "n1", "ep.silon": "n1", "gamma": "n1", "far": "n2"}
            # The coding agents' own row (R95: the coding agents'), not the
            # toolchains'.
            self.assertFalse([r for r in toolchains.attention(bound) if r["kind"] == "toolchain"])
            got = [r for r in toolchains.agent_attention(bound) if r["kind"] == "agents"]
            self.assertEqual([r["tools"] for r in got],
                             [[{"name": "claude-code", "label": "Claude Code", "from": "2.0.1", "to": "2.0.2"}]])
            return got
        finally:
            toolchains.nodes, toolchains.last_check, toolchains.agentcode = was

    def test_no_session_running_counts_none(self):
        (row,) = self.bell([{"name": "shell-alpha"}])
        self.assertEqual(row["sessions"], 0)
        self.assertEqual(row["projects"], [])

    def test_each_running_session_is_counted_and_its_project_named(self):
        (row,) = self.bell([{"name": "claude-alpha"}, {"name": "u_0123abcd~claude-alpha"},
                            {"name": "claude-ep_silon"}, {"name": "shell-beta"}])
        self.assertEqual(row["sessions"], 3)
        self.assertEqual(row["projects"], ["alpha", "ep.silon"])


if __name__ == "__main__":
    unittest.main()
