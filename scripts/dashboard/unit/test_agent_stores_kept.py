"""A node enrolling again keeps its stores where they are (B658): a role
the flags left at its default takes the path the node's record has."""
import os
import sys
import unittest

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, os.path.join(HERE, "..", "..", "agent"))
from aerieos_agent import cli  # noqa: E402
from aerieos_agent.base import DEFAULT_STORES  # noqa: E402


class StoresKept(unittest.TestCase):
    def test_a_role_left_at_its_default_keeps_the_path_the_record_has(self):
        had = {"stores": {"toolchains": "/mnt/SDK", "data": "/var/lib/builderbot/data"}}
        got = cli.stores_kept(dict(DEFAULT_STORES), set(), had)
        self.assertEqual(got["toolchains"], "/mnt/SDK")
        self.assertEqual(got["data"], DEFAULT_STORES["data"])
        self.assertEqual(got["cache"], DEFAULT_STORES["cache"])

    def test_a_role_the_flags_named_wins(self):
        had = {"stores": {"toolchains": "/mnt/SDK"}}
        stores = dict(DEFAULT_STORES) | {"toolchains": "/srv/tc"}
        self.assertEqual(cli.stores_kept(stores, {"toolchains"}, had)["toolchains"], "/srv/tc")
        stores = dict(DEFAULT_STORES)
        self.assertEqual(cli.stores_kept(stores, {"toolchains"}, had)["toolchains"], DEFAULT_STORES["toolchains"])

    def test_a_first_enrollment_and_a_bad_record_change_nothing(self):
        self.assertEqual(cli.stores_kept(dict(DEFAULT_STORES), set(), {}), DEFAULT_STORES)
        self.assertEqual(cli.stores_kept(dict(DEFAULT_STORES), set(), {"stores": {"toolchains": "relative", "nonesuch": "/x"}}),
                         DEFAULT_STORES)
        self.assertEqual(cli.stores_kept(dict(DEFAULT_STORES), set(), {"stores": {"toolchains": "/"}}), DEFAULT_STORES)


if __name__ == "__main__":
    unittest.main()
