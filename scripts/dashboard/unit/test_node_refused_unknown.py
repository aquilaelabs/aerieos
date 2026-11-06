"""A hello with a token this controller has no record of (B652): the row
of the node it names says it is turned away, only when that node is quiet
anyway, so a stranger naming a live node cannot paint it refused."""
import os
import sys
import time
import unittest
from unittest import mock

sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)), ".."))
import nodes  # noqa: E402


class UnknownToken(unittest.TestCase):
    def said(self, row, nid: object = "n_02529b69"):
        with mock.patch.object(nodes, "node", return_value=row), mock.patch.object(nodes, "_refused") as ref:
            nodes.refused_unknown(nid)
        return ref.call_args[0] if ref.called else None

    def test_a_quiet_node_says_its_credential_is_not_known_here(self):
        got = self.said({"kind": "agent", "agent": {"last_seen": int(time.time()) - 3600}})
        self.assertEqual(got[0], "n_02529b69")
        self.assertIn("no record of its credential", got[1])

    def test_a_live_node_a_retired_one_or_no_node_is_left_alone(self):
        self.assertIsNone(self.said({"kind": "agent", "agent": {"last_seen": int(time.time()) - 30}}))
        self.assertIsNone(self.said({"kind": "agent", "state": "retired", "agent": {}}))
        self.assertIsNone(self.said({"kind": "local"}))
        self.assertIsNone(self.said(None))
        for bad in ("", "local", "n_../x", 5, None):
            self.assertIsNone(self.said({"kind": "agent", "agent": {}}, bad), bad)


if __name__ == "__main__":
    unittest.main()
