"""Enroll script on an enrolled node's row (R210): the script is built from
the row's own answers, the system among them, with no dialog."""
import os
import sys
import unittest

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, os.path.join(HERE, ".."))
import nodes  # noqa: E402


class RowAnswers(unittest.TestCase):
    def test_a_lan_node_answers_with_the_browsers_address(self):
        n = {"id": "n_1", "name": "shed", "config": {"user": "bb", "system": "rocky"},
             "reported": {"os": "linux x86_64 Ubuntu 24.04"}}
        a = nodes.row_answers(n, "http://192.168.1.10:7680")
        self.assertEqual((a["node"], a["name"], a["reach"], a["controller"], a["system"], a["sessions"], a["host_only"]),
                         ("n_1", "shed", "lan", "http://192.168.1.10:7680", "rocky", True, False))
        self.assertEqual((a["door"], a["door_host"], a["tunnel_addr"], a["nginx"]), ("", "", "", False))

    def test_a_public_node_answers_with_its_own_hostname_and_door(self):
        n = {"id": "n_2", "name": "vps", "config": {"user": "ops", "host_only": True, "nginx": True,
                                                    "tunnel": {"kind": "public", "host": "bb.example.com"},
                                                    "door": {"kind": "cloudflared", "host": "ssh.example.com"}},
             "reported": {"os": "linux x86_64 Debian GNU/Linux 12"}}
        a = nodes.row_answers(n, "http://192.168.1.10:7680")
        self.assertEqual((a["reach"], a["controller"], a["host_only"], a["sessions"], a["nginx"], a["user"]),
                         ("public", "https://bb.example.com", True, False, True, "ops"))
        self.assertEqual((a["door"], a["door_host"], a["system"]), ("cloudflared", "ssh.example.com", "debian"))

    def test_a_wireguard_node_carries_its_tunnel_address(self):
        n = {"id": "n_3", "name": "far", "config": {"tunnel": {"kind": "wireguard", "addr": "10.6.0.5"}}, "reported": {}}
        a = nodes.row_answers(n, "http://10.6.0.1:7680")
        self.assertEqual((a["reach"], a["tunnel_addr"], a["system"]), ("wireguard", "10.6.0.5", "ubuntu"))

    def test_the_system_recorded_wins_over_the_census(self):
        self.assertEqual(nodes.system_of({"config": {"system": "rocky"}, "reported": {"os": "linux x86_64 Ubuntu"}}), "rocky")
        self.assertEqual(nodes.system_of({"config": {"system": "nonesuch"}, "reported": {"os": "linux x86_64 Ubuntu"}}), "ubuntu")
        self.assertEqual(nodes.system_of({"config": {}, "reported": {"os": "linux x86_64 Fedora Linux 40"}}), "fedora")
        self.assertEqual(nodes.system_of({"config": {}, "reported": {}}), "ubuntu")


if __name__ == "__main__":
    unittest.main()
