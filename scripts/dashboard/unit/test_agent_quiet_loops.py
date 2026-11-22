"""The node agent's loops start fewer processes (R228 step 18): a firewall
table in place is listed every TABLE_LOOK_S and not every two seconds, the
accounts and their groups are read once a minute and afresh when the agent
changes one, and its controller client makes one TLS context of each kind."""
import os
import sys
import types
import unittest

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import agentpkg  # noqa: E402

agent = agentpkg.load("aerieos_agent_quiet_loops")


class Tables(unittest.TestCase):
    def setUp(self):
        self.ran = []
        self.code = 0
        real = agent.sessnet.subprocess.run

        def fake(argv, **k):
            self.ran.append(argv[:3])
            return types.SimpleNamespace(returncode=self.code, stdout="", stderr="")
        agent.sessnet.subprocess.run = fake
        self.addCleanup(setattr, agent.sessnet.subprocess, "run", real)
        self.sn = agent.sessnet.SessionNet.__new__(agent.sessnet.SessionNet)
        self.sn.looked = {}

    def test_a_table_is_listed_once_a_look(self):
        gone = [self.sn.table_gone("t", 1000.0 + i * 2) for i in range(10)]
        self.assertEqual(gone, [False] * 10)
        self.assertEqual(len(self.ran), 1)
        self.sn.table_gone("t", 1000.0 + agent.sessnet.TABLE_LOOK_S + 1)
        self.assertEqual(len(self.ran), 2)

    def test_a_table_gone_is_said_at_the_next_look(self):
        self.sn.table_gone("t", 1000.0)
        self.code = 1
        self.assertFalse(self.sn.table_gone("t", 1010.0))
        self.assertTrue(self.sn.table_gone("t", 1000.0 + agent.sessnet.TABLE_LOOK_S))


class Accounts(unittest.TestCase):
    def setUp(self):
        agent.accounts.accounts_moved()
        self.addCleanup(agent.accounts.accounts_moved)

    def test_a_lookup_is_kept_and_forgotten_when_an_account_moves(self):
        reads = []
        read = lambda: reads.append(1) or len(reads)  # noqa: E731
        self.assertEqual([agent.accounts.kept_lookup("k", read) for _ in range(3)], [1, 1, 1])
        agent.accounts.accounts_moved()
        self.assertEqual(agent.accounts.kept_lookup("k", read), 2)


class Contexts(unittest.TestCase):
    def test_one_context_of_each_kind(self):
        a, b = agent.controller._context(False), agent.controller._context(False)
        self.assertIs(a, b)
        self.assertFalse(a.check_hostname)
        c = agent.controller._context(True)
        self.assertIsNot(a, c)
        self.assertTrue(c.check_hostname)


if __name__ == "__main__":
    unittest.main()
