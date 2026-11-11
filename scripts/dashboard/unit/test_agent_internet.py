"""Whether a node reaches the internet, as its census says it (B770): asked
at most every ten minutes, but a "no" from the agent's first minutes is
asked again after one, since the first look is at boot, before the network
is up, and stood for ten minutes on a machine that had it."""
import socket
import time
import unittest
from unittest import mock

import agentpkg  # noqa: E402

agent = agentpkg.load("aerieos_agent")
census = next(m for m in agent._mods if m.__name__.endswith(".census"))


class Internet(unittest.TestCase):
    def setUp(self):
        self.was = dict(census._NET)
        self.addCleanup(lambda: (census._NET.clear(), census._NET.update(self.was)))
        census._NET.update(at=0.0, ok=None, first=0.0)
        self.now = 1_000_000.0
        self.up = False
        self.asked = 0

    def connect(self, *a, **k):
        self.asked += 1
        if not self.up:
            raise OSError("network is unreachable")
        return mock.Mock()

    def ask(self, after=0):
        self.now += after
        with mock.patch.object(socket, "create_connection", self.connect), mock.patch.object(time, "time", lambda: self.now):
            return census._internet()

    def test_a_no_at_boot_is_asked_again_after_a_minute_and_a_yes_stands_ten(self):
        self.assertFalse(self.ask())
        asked = self.asked
        self.assertFalse(self.ask(after=30))
        self.assertEqual(self.asked, asked, "within the minute the answer stands")
        self.up = True
        self.assertTrue(self.ask(after=40), "the network came up: a minute on, the row says so")
        asked = self.asked
        self.up = False
        self.assertTrue(self.ask(after=500))
        self.assertEqual(self.asked, asked, "a yes stands for ten minutes")
        self.assertFalse(self.ask(after=200))

    def test_a_machine_with_none_is_not_asked_every_minute_for_ever(self):
        self.assertFalse(self.ask())
        self.assertFalse(self.ask(after=census.NET_YOUNG_S + 61))
        asked = self.asked
        self.assertFalse(self.ask(after=120))
        self.assertEqual(self.asked, asked, "past its first quarter of an hour a no stands ten minutes too")
        self.assertFalse(self.ask(after=census.NET_EVERY))
        self.assertGreater(self.asked, asked)


if __name__ == "__main__":
    unittest.main()
