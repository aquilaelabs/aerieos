"""A node locked to its own console refuses a console password set from its
page (B1022), as every other system change is refused there: the job was
queued without asking the lock."""
import json
import os
import sys
import tempfile
import unittest

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))
import nodes  # noqa: E402


class Locked(unittest.TestCase):
    def setUp(self):
        nodes.configure(state=tempfile.mkdtemp())
        mint = nodes.enroll_mint("user:test", "own")
        nodes.enroll(nodes.authenticate(mint["token"]), {"cpu": 2, "mem_mb": 4096, "arch": "x86_64", "system": "linux",
                                                         "console": {"os": "aerieos"}, "session": {"up": True, "user": "b"}},
                     "own.lan", user="bb")
        self.nid = mint["id"]
        n = nodes.node(self.nid)
        conf = dict(n.get("config") or {}, own=True)
        nodes._exec("UPDATE nodes SET config = ?, reported = json_set(reported, '$.console', json(?)) WHERE id = ?",
                    (json.dumps(conf), json.dumps({"os": "aerieos"}), self.nid))

    def queued(self):
        return [j for j in nodes.jobs_for(node_id=self.nid, n=10, active=True) if j.get("type") == "system"]

    def test_a_locked_node_refuses_and_queues_nothing(self):
        nodes.node_lock("user:test", self.nid, True)
        r = nodes.node_console("user:test", self.nid, "", clear=True)
        self.assertIn("locked to its own console", r.get("error", ""))
        self.assertEqual(self.queued(), [])


if __name__ == "__main__":
    unittest.main()
