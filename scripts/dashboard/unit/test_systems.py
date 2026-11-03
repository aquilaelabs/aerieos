"""Enroll node's systems (R204, R97): a vetted one is offered as it is, and
one that cannot be walked here says why beside its dev tag."""
import os
import sys
import unittest

sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)), ".."))
import forges  # noqa: E402
import systems  # noqa: E402


class Offered(unittest.TestCase):
    def setUp(self):
        self.addCleanup(setattr, forges, "unvetted_ok", forges.unvetted_ok)

    def test_a_system_that_cannot_be_walked_says_why(self):
        forges.unvetted_ok = lambda: True
        got = {s["id"]: s for s in systems.offered()}
        self.assertIn("no cloud image", got["void"]["why"])
        self.assertIn("rolling", got["gentoo"]["why"])
        self.assertIn("subscription", got["rhel"]["why"])
        self.assertNotIn("why", got["ubuntu"])
        forges.unvetted_ok = lambda: False
        self.assertNotIn("void", {s["id"] for s in systems.offered()}, "a dev system is offered only behind Offer dev features")


if __name__ == "__main__":
    unittest.main()


class OfOs(unittest.TestCase):
    """The system a census names (R210): what a row enrolled before the
    system was recorded on it gets its script built for."""
    def test_the_census_names_the_system(self):
        for text, want in (("linux x86_64 Ubuntu 24.04.2 LTS", "ubuntu"), ("linux x86_64 Rocky Linux 9.4", "rocky"),
                           ("linux aarch64 Debian GNU/Linux 12 (bookworm)", "debian"), ("linux x86_64 AlmaLinux 9.4", "almalinux"),
                           ("linux x86_64 Red Hat Enterprise Linux 9.4", "rhel"), ("linux x86_64 openSUSE Leap 15.6", "opensuse"),
                           ("linux x86_64 Arch Linux", "arch"), ("linux x86_64 Raspbian GNU/Linux 12", "debian"),
                           ("linux x86_64", ""), ("", "")):
            self.assertEqual(systems.of_os(text), want, text)
