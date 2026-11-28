"""A person's own time zone: kept with the account's own
preferences when it is a zone this machine knows, refused in words when it
is not, and the hours of their quiet windows on the bell, which read the
controller's clock before."""
import os
import sys
import unittest

sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)), ".."))
import reach  # noqa: E402
import users  # noqa: E402

# 03:00 UTC on 26 Nov 2025: 19:00 the day before in Los Angeles, noon in Tokyo.
AT = 1764126000
NIGHT = {"from": "22:00", "to": "07:00"}


class Zone(unittest.TestCase):
    def test_a_zone_this_machine_knows(self):
        self.assertTrue(users.zone_ok("Europe/London"))
        self.assertTrue(users.zone_ok("UTC"))
        for bad in ("Mars/Base", "../etc/passwd", "Europe/London/../x", "", "a" * 70):
            self.assertFalse(users.zone_ok(bad), bad)

    def test_own_prefs_keeps_one_refuses_another_and_clears(self):
        saved = {}
        was = users.prefs_set
        self.addCleanup(lambda: setattr(users, "prefs_set", was))
        users.prefs_set = lambda name, keep: saved.update(keep) or {"ok": True}
        self.assertEqual(users.own_prefs("ada", {"tz": "Asia/Tokyo"})[1], 200)
        self.assertEqual(saved["tz"], "Asia/Tokyo")
        r, status = users.own_prefs("ada", {"tz": "Mars/Base"})
        self.assertEqual(status, 400)
        self.assertIn("not a time zone", r["error"])
        self.assertEqual(users.own_prefs("ada", {"tz": ""})[1], 200)
        self.assertEqual(saved["tz"], "", "none is the controller's clock again")

    def test_quiet_hours_are_the_person_s(self):
        self.assertTrue(reach._in_quiet(NIGHT, AT, "UTC"))
        self.assertFalse(reach._in_quiet(NIGHT, AT, "America/Los_Angeles"))
        self.assertFalse(reach._in_quiet(NIGHT, AT, "Asia/Tokyo"))
        self.assertTrue(reach._in_quiet({"from": "11:00", "to": "13:00"}, AT, "Asia/Tokyo"))


if __name__ == "__main__":
    unittest.main()
