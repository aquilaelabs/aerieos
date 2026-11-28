"""A session is a caller of its own kind: its token answers a
principal with no role's rights and no account's id. What keeps something by
a caller's id keeps nothing for a session unless it asked whose by name;
the person it works for is its seat, and the account behind it is found by
that seat where a route means the person."""
import os
import sys
import tempfile
import unittest

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))
import users  # noqa: E402


class Kind(unittest.TestCase):
    def setUp(self):
        from statefile import write_json
        users.configure(state=tempfile.mkdtemp(), write_json=write_json)
        users.claim("ann", "a-good-password")
        self.uid = users.get("ann")["uid"]

    def test_a_token_answers_a_session_with_no_uid_and_no_role_of_a_person(self):
        me = users.session_principal(users.mint_session("alpha", uid=self.uid))
        self.assertEqual((me["kind"], me["role"], me["session"], me["seat"]), ("session", "session", "alpha", self.uid))
        self.assertNotIn("uid", me)
        self.assertEqual(users.uid_of(me), "", "nothing is kept by a session's id")
        self.assertEqual(users.seat_of(me), self.uid)
        self.assertEqual(users.whose(me), self.uid, "the person it works for, where a route asks by name")
        self.assertFalse(users.is_admin(me), "whoever its person is")
        self.assertEqual(users.account_of(me)["name"], "ann")

    def test_one_minted_for_nobody_has_no_seat(self):
        me = users.session_principal(users.mint_session("alpha"))
        self.assertEqual((users.uid_of(me), users.seat_of(me), users.whose(me)), ("", "", ""))
        self.assertIs(users.account_of(me), me, "no account stands behind it")

    def test_a_person_is_themselves(self):
        ann = dict(users.get("ann"), name="ann")
        self.assertEqual((users.uid_of(ann), users.seat_of(ann), users.whose(ann)), (self.uid, "", self.uid))

    def test_the_role_names_are_not_an_account_s_to_take(self):
        import roles
        self.assertIn("session", roles.RESERVED)

    def test_a_renewed_token_is_the_same_session(self):
        me = users.session_principal(users.mint_session("alpha", uid=self.uid))
        again = users.with_reads(me, ["beta"])
        self.assertEqual((again["seat"], again["reads"], again["kind"]), (self.uid, ["beta"], "session"))


if __name__ == "__main__":
    unittest.main()
