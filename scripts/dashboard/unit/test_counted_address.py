"""The wrong-password hold counts the client, not the door (R243; the audit
of 13 Nov): keyed on the socket's own address it held everybody behind the
tunnel or a reverse proxy together, since they are one address there, after
a hundred wrong passwords from anyone. Behind a proxy this install trusts,
the address that proxy passes on is the one counted; from anybody else the
header is a client's own words and is ignored."""
import os
import sys
import unittest

sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)), ".."))
import users  # noqa: E402

TUNNEL = ["127.0.0.0/8", "::1"]


class Counted(unittest.TestCase):
    def test_with_no_proxy_trusted_the_socket_is_the_address_whatever_the_header_says(self):
        self.assertEqual(users.counted_address("203.0.113.9", "10.0.0.1"), "203.0.113.9")
        self.assertEqual(users.counted_address("203.0.113.9", "10.0.0.1, 10.0.0.2", ["192.168.1.20"]), "203.0.113.9")
        # ...which is what keeps a client from naming a new address for every guess.
        self.assertEqual(users.counted_address("127.0.0.1", "198.51.100.7"), "127.0.0.1")

    def test_behind_the_tunnel_each_visitor_is_their_own_address(self):
        self.assertEqual(users.counted_address("127.0.0.1", "198.51.100.7", TUNNEL), "198.51.100.7")
        self.assertEqual(users.counted_address("::1", "2001:db8::5", TUNNEL), "2001:db8::5")
        self.assertEqual(users.counted_address("::ffff:127.0.0.1", "198.51.100.7", TUNNEL), "198.51.100.7")
        # What a visitor wrote in front of the proxy's own entry is not believed.
        self.assertEqual(users.counted_address("127.0.0.1", "1.2.3.4, 198.51.100.7", TUNNEL), "198.51.100.7")

    def test_a_chain_of_trusted_proxies_is_walked_from_the_door_outward(self):
        trusted = ["192.168.1.20", "10.0.0.0/8"]
        self.assertEqual(users.counted_address("192.168.1.20", "198.51.100.7, 10.0.0.3", trusted), "198.51.100.7")
        # Every hop trusted, or no header: the door itself.
        self.assertEqual(users.counted_address("192.168.1.20", "10.0.0.3", trusted), "192.168.1.20")
        self.assertEqual(users.counted_address("192.168.1.20", "", trusted), "192.168.1.20")

    def test_what_is_not_an_address_is_not_believed(self):
        self.assertEqual(users.counted_address("127.0.0.1", "198.51.100.7, nonsense", TUNNEL), "127.0.0.1")
        self.assertEqual(users.counted_address("127.0.0.1", "unknown", TUNNEL), "127.0.0.1")
        self.assertEqual(users.counted_address("192.168.1.20", "198.51.100.7", ["not a network", "192.168.1.20"]), "198.51.100.7")
        self.assertEqual(users.counted_address("", "198.51.100.7", TUNNEL), "")
        self.assertEqual(users.counted_address("a-socket-with-no-address", "198.51.100.7", TUNNEL), "a-socket-with-no-address")

    def test_the_hold_is_then_one_visitors_and_not_the_doors(self):
        # A hundred wrong from one visitor behind the tunnel: that visitor is held, the next is not.
        bad, good = users.counted_address("127.0.0.1", "198.51.100.7", TUNNEL), users.counted_address("127.0.0.1", "198.51.100.8", TUNNEL)
        saved = dict(users._pw_misses)
        self.addCleanup(lambda: (users._pw_misses.clear(), users._pw_misses.update(saved)))
        users._pw_misses.clear()
        for n in range(users.PW_HOLD_AFTER):
            users.pw_missed(f"guess-{n}", bad)
        self.assertGreater(users.pw_held(bad), 0)
        self.assertEqual(users.pw_held(good), 0)


if __name__ == "__main__":
    unittest.main()
