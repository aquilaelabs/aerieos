"""The move token given on the first page is kept for the landing (the
operator, 10 Nov: the walk asked for it twice), sealed across a restart and
dropped when the move lands; and a move to an address of the local network
names the nodes that dial in from outside it (move.far_nodes)."""
import os
import sys
import tempfile
import unittest
from pathlib import Path

sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)), ".."))
import move  # noqa: E402

TOKEN = "A" * 43


class SetupToken(unittest.TestCase):
    def setUp(self):
        self.was = (move.STATE, move.seal, move.unseal)
        move.STATE = Path(tempfile.mkdtemp())
        move.seal = lambda b: b"sealed:" + b
        move.unseal = lambda b: b[len(b"sealed:"):] if b.startswith(b"sealed:") else (_ for _ in ()).throw(ValueError("locked"))
        move.drop_setup_token()

    def tearDown(self):
        move.drop_setup_token()
        move.STATE, move.seal, move.unseal = self.was

    def test_kept_across_a_restart_and_dropped(self):
        move.keep_setup_token(TOKEN)
        self.assertEqual(move.setup_token(), TOKEN)
        move._setup_token["tok"] = ""                # a restart: memory gone, the seal read
        self.assertEqual(move.setup_token(), TOKEN)
        self.assertEqual(oct((move.STATE / move.SETUP_TOKEN_FILE).stat().st_mode & 0o777), "0o600")
        move.drop_setup_token()
        self.assertEqual(move.setup_token(), "")
        self.assertFalse((move.STATE / move.SETUP_TOKEN_FILE).exists())

    def test_a_password_that_is_not_a_token_is_not_kept(self):
        move.keep_setup_token("hunter2")
        self.assertEqual(move.setup_token(), "")

    def test_no_install_key_keeps_it_in_memory(self):
        move.seal = lambda b: (_ for _ in ()).throw(RuntimeError("no install key"))
        move.keep_setup_token(TOKEN)
        self.assertEqual(move.setup_token(), TOKEN)
        self.assertFalse((move.STATE / move.SETUP_TOKEN_FILE).exists())


class FarNodes(unittest.TestCase):
    def test_a_lan_address_names_the_nodes_outside(self):
        nodes = [("draconis", "15.204.9.32"), ("sandbox", "192.168.1.16"), ("odd", "")]
        self.assertEqual(move.far_nodes("http://192.168.1.15:7680", nodes), ["draconis"])

    def test_a_node_at_the_home_tunnels_hostname_follows_there(self):
        nodes = [("draconis", "15.204.9.32", "aerie.example.com"), ("vps2", "15.204.9.33", "")]
        self.assertEqual(move.far_nodes("http://192.168.1.15:7680", nodes), ["vps2"], "one enrolled at the public hostname keeps it")
        said = move.far_said(["vps2"], "http://192.168.1.15:7680")
        self.assertIn("Reach from outside", said)
        self.assertNotIn("the line the new home", said, "that line names the new home's local address too")

    def test_a_public_name_or_address_names_none(self):
        self.assertEqual(move.far_nodes("https://aerie.example.com", [("draconis", "15.204.9.32")]), [])
        self.assertEqual(move.far_nodes("https://15.204.9.40", [("draconis", "15.204.9.32")]), [])


if __name__ == "__main__":
    unittest.main()
