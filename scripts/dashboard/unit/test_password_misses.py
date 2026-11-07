"""Wrong passwords counted at every door (B721): an address past its quarter
hour's allowance is held without the password being looked at, an account
is only slowed, and a name with no account costs what a wrong password does."""
import os
import sys
import time
import unittest
from unittest import mock

sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)), ".."))
import users  # noqa: E402


class Misses(unittest.TestCase):
    def setUp(self):
        users._pw_misses.clear()
        self.addCleanup(users._pw_misses.clear)

    def test_an_address_is_held_and_an_account_only_slowed(self):
        with mock.patch.object(users, "get", return_value=None), mock.patch.object(users, "check_password", return_value=False), \
             mock.patch.object(users.time, "sleep") as slept:
            for _ in range(users.PW_HOLD_AFTER):
                self.assertIsNone(users.authenticate("owner", "guess", where="10.0.0.9"))
            self.assertTrue(users.pw_held("10.0.0.9"), "held past the allowance")
            self.assertFalse(users.pw_held("10.0.0.10"), "another address is not")
            self.assertLessEqual(max(c.args[0] for c in slept.call_args_list), 5.0, "an account is slowed, never locked")
        with mock.patch.object(users, "get", return_value={"name": "owner", "password": "x"}), \
             mock.patch.object(users, "check_password", return_value=True) as checked:
            self.assertIsNone(users.authenticate("owner", "right", where="10.0.0.9"), "held: not even the right one")
            checked.assert_not_called()
            self.assertTrue(users.authenticate("owner", "right", where="10.0.0.10"), "the owner from elsewhere signs in")

    def test_a_name_with_no_account_still_costs_a_hash(self):
        with mock.patch.object(users, "get", return_value=None), mock.patch.object(users, "check_password", return_value=False) as checked:
            self.assertIsNone(users.authenticate("nobody", "x"))
        checked.assert_called_once()
        self.assertEqual(checked.call_args.args[0], users._NOBODY)

    def test_the_count_ages_out(self):
        now = time.time()
        users._pw_misses["at:10.0.0.9"] = [now - users.PW_WINDOW - 1] * users.PW_HOLD_AFTER
        self.assertFalse(users.pw_held("10.0.0.9"))


if __name__ == "__main__":
    unittest.main()
