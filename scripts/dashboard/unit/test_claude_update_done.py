"""A Claude Code update's row says the new version the moment its job ends
(B249), read off the job's last line, which names the version the way
`claude --version` prints it, its own "(Claude Code)" included (B167)."""
import os
import sys
import unittest

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))
import agentcode  # noqa: E402


class Nodes:
    def __init__(self, log):
        self.log, self.set = log, []

    def job(self, jid, with_log=False):
        return {"id": jid, "log": self.log, "spec": {}}

    def reported_set(self, nid, key, sub, value):
        self.set.append((nid, key, sub, value))


class UpdateDone(unittest.TestCase):
    def setUp(self):
        self.addCleanup(setattr, agentcode, "nodes", agentcode.nodes)

    def test_the_version_the_agent_writes_reaches_the_row(self):
        for line, want in (("Claude Code 2.1.306 (Claude Code) is what a session here runs now", "2.1.306"),
                           ("Claude Code 2.1.306 is what a session here runs now", "2.1.306")):
            agentcode.nodes = Nodes("pinned it\n" + line + "\n")
            agentcode.update_done({"id": "j1", "type": "claude-update", "node": "n1"}, "succeeded")
            self.assertEqual(agentcode.nodes.set, [("n1", "session", "claude", f"{want} (Claude Code)")], line)

    def test_a_removal_leaves_none_on_the_row(self):
        agentcode.nodes = Nodes("")
        agentcode.update_done({"id": "j1", "type": "claude-update", "node": "n1", "spec": {"action": "remove"}}, "succeeded")
        self.assertEqual(agentcode.nodes.set, [("n1", "session", "claude", "")])


if __name__ == "__main__":
    unittest.main()
