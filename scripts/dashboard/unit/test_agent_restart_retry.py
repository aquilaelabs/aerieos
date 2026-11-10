"""A controller restarting (an update) refuses connections for a minute: the
agent's work poll knows it by what the call says and asks again every few
seconds rather than backing off to a minute (B760)."""
import os
import sys
import unittest

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "..", "agent"))
from aerieos_agent import agent as agentmod  # noqa: E402


class Restarting(unittest.TestCase):
    def test_what_a_restart_says_is_known(self):
        for said in ("ConnectionRefusedError: [Errno 111] Connection refused",
                     "RemoteDisconnected: Remote end closed connection without response",
                     "ConnectionResetError: [Errno 104] Connection reset by peer"):
            self.assertTrue(agentmod.RESTARTING.search(said), said)

    def test_anything_else_is_not(self):
        for said in ("TimeoutError: timed out", "unknown token", "URLError: <urlopen error [Errno -2] Name or service not known>"):
            self.assertFalse(agentmod.RESTARTING.search(said), said)


if __name__ == "__main__":
    unittest.main()
