"""Every account a Unix user of its own on every node, and the coding
agents' sign-ins sealed there:
there is no switch for either, a key an older build left reads as
on, and a hosting-only node, which runs no sessions, is neither."""
import sys
import tempfile
import unittest
from pathlib import Path
from unittest import mock

HERE = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(HERE))


class AlwaysOn(unittest.TestCase):
    def test_on_wherever_sessions_run_and_the_switches_refuse(self):
        import nodes
        saved = nodes.node, nodes.can_seal
        self.addCleanup(lambda: (setattr(nodes, "node", saved[0]), setattr(nodes, "can_seal", saved[1])))
        conf = {"a": {}, "h": {"host_only": True}, "x": {"account_users": False, "token_seal": False}}
        nodes.node = lambda nid: {"id": nid, "kind": "agent", "config": conf[nid]}
        nodes.can_seal = lambda: True
        self.assertEqual((nodes.account_users_on("a"), nodes.token_seal_on("a")), (True, True))
        self.assertEqual((nodes.account_users_on("h"), nodes.token_seal_on("h")), (False, False),
                         "a hosting-only node runs no sessions")
        self.assertEqual((nodes.account_users_on("x"), nodes.token_seal_on("x")), (True, True),
                         "a key an older build left reads as on")
        # ...and sealing waits on an install key to make each account's key from.
        nodes.can_seal = lambda: False
        self.assertEqual((nodes.account_users_on("a"), nodes.token_seal_on("a")), (True, False))

    def test_no_switch_is_left_to_ask_for(self):
        # The switches' verbs answered "went in 0.9.0" for a page from 0.8;
        # they are unknown actions now, with no handler behind them.
        import nodes
        for name in ("node_account_users", "node_token_seal", "node_session_net", "node_container_net"):
            self.assertFalse(hasattr(nodes, name), name)
        for act in ("account-users", "token-seal"):
            self.assertEqual(nodes.verb("user:t", {"action": act, "id": "a", "on": True}), ({"error": "unknown action"}, 400))


class Hello(unittest.TestCase):
    def test_the_hello_hands_a_node_the_publics_it_seals_with_and_no_others(self):
        # The format before's publics served only nodes that sealed the old
        # way; a node seals with the X25519 publics alone.
        import nodes
        nodes.configure(state=tempfile.mkdtemp())
        mint = nodes.enroll_mint("user:test", "box")
        nodes.enroll(nodes.authenticate(mint["token"]), {"cpu": 2, "mem_mb": 4096, "arch": "x86_64", "system": "linux",
                                                         "session": {"up": True, "user": "b"}}, "box.lan", user="bb")
        asked = []

        def pubs(nid, *old):
            asked.append(old)
            return {"u_00000001": "ab" * 32}
        with mock.patch.object(nodes, "token_pubs", pubs), mock.patch.object(nodes, "can_seal", lambda: True):
            r = nodes.hello(mint["id"], {"cpu": 2, "mem_mb": 4096, "arch": "x86_64", "system": "linux"}, "box.lan")
        self.assertIs(r["token_seal"], True)
        self.assertEqual(r["token_pubs2"], {"u_00000001": "ab" * 32})
        self.assertNotIn("token_pubs", r)
        self.assertEqual(asked, [()], "asked once, for the X25519 publics")


if __name__ == "__main__":
    unittest.main()
