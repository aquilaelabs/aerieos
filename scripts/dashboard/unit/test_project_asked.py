"""The opening of a handler that works on one project (server.py's
_project_asked): where the name is read from, which refusal comes first,
that a read is asked Spaces Read on it and a write of an account that works
on the project. Held
here without a server: the helper and the three gates it stands on are
lifted out of server.py's source and run against a stand-in for the
accounts and the locks."""
import ast
import os
import sys
import unittest
import urllib.parse

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, os.path.join(HERE, ".."))
from fields import field  # noqa: E402

SERVER = open(os.path.join(HERE, "..", "server.py"), encoding="utf-8").read()
LIFTED = ("_project_asked", "_not_project", "_readonly", "_q")


class _Users:
    @staticmethod
    def may(who, action, project=None):
        return "" if project in who["works"] else "you were not given this space"

    @staticmethod
    def whose(who):
        return who["uid"]


class _Projects:
    @staticmethod
    def locked_out(name, uid):
        return {"error": f"{name} is locked"} if name == "locked" and uid != "u_owner" else None


def handler():
    """A class of the lifted methods, with the reply recorded."""
    lines = SERVER.splitlines()
    cls = next(n for n in ast.parse(SERVER).body if isinstance(n, ast.ClassDef) and n.name == "Handler")
    body = "\n".join("\n".join(lines[f.lineno - 1:f.end_lineno]) for f in cls.body
                     if isinstance(f, ast.FunctionDef) and f.name in LIFTED)
    ns = {"field": field, "urllib": urllib, "users": _Users, "projects": _Projects,
          "project_names": lambda who: who["sees"]}
    exec("class Lifted:\n" + body, ns)      # noqa: S102 (the repository's own source, read from beside this test)

    class Stand(ns["Lifted"]):
        def __init__(self, who, path="/api/x"):
            self.who, self.path, self.said = who, path, []

        def _who(self):
            return self.who

        # Spaces Read, the area's gate (_refused is the server's whole
        # dispatcher; what it answers for "read" is the account's reads).
        def _refused(self, action, name=None):
            assert action == "read", action
            if name in self.who.get("reads", self.who["sees"]):
                return False
            self.said.append((403, {"error": "your roles give no Spaces Read on it"}))
            return True

        def _json(self, obj, code=200):
            self.said.append((code, obj))

    return Stand


Stand = handler()
USER = {"uid": "u_user", "sees": ["alpha", "beta", "locked"], "works": ["alpha", "locked"]}
OWNER = {"uid": "u_owner", "sees": ["alpha", "locked"], "works": ["alpha", "locked"]}
# On beta by a role that gives it Containers alone (R277, the audit of 24 Nov).
BOXER = {"uid": "u_box", "sees": ["beta"], "works": [], "reads": []}


class Asked(unittest.TestCase):
    def test_the_helper_is_there_whole(self):
        for name in LIFTED:
            self.assertTrue(hasattr(Stand, name), name)

    def test_a_body_names_it_in_its_project_field(self):
        h = Stand(USER)
        self.assertEqual(h._project_asked({"project": "alpha"}), "alpha")
        self.assertEqual(h.said, [])

    def test_a_query_names_it_first_value_first(self):
        h = Stand(USER, "/api/x?n=3&project=alpha&project=beta")
        self.assertEqual(h._project_asked(), "alpha")
        self.assertEqual(h._project_asked(query={"project": ["beta"]}), "beta")
        self.assertEqual(h.said, [])

    def test_an_empty_body_is_not_the_query(self):
        # A body with no project is refused, whatever the address says.
        h = Stand(USER, "/api/x?project=alpha")
        self.assertIsNone(h._project_asked({}))
        self.assertEqual(h.said, [(400, {"error": "not a space"})])

    def test_no_project_and_one_not_seen_are_refused_by_name(self):
        for asked, words in (({}, "not a space"), ({"project": ""}, "not a space"),
                             ({"project": "ghost"}, "not a space: ghost"),
                             ({"project": ["alpha"]}, "not a space"), ({"project": 7}, "not a space")):
            h = Stand(USER)
            self.assertIsNone(h._project_asked(asked), asked)
            self.assertEqual(h.said, [(400, {"error": words})], asked)

    def test_a_read_is_not_asked_whether_the_account_works_on_it(self):
        h = Stand(USER)
        self.assertEqual(h._project_asked({"project": "beta"}), "beta")
        self.assertEqual(h.said, [])

    def test_a_read_asks_spaces_read_and_the_files_ask_their_own(self):
        h = Stand(BOXER)
        self.assertIsNone(h._project_asked({"project": "beta"}))
        self.assertEqual(h.said, [(403, {"error": "your roles give no Spaces Read on it"})])
        h = Stand(BOXER)
        self.assertEqual(h._project_asked({"project": "beta"}, files=True), "beta")
        self.assertEqual(h.said, [])

    def test_a_write_is_refused_where_the_account_only_sees_it(self):
        h = Stand(USER)
        self.assertIsNone(h._project_asked({"project": "beta"}, write=True))
        self.assertEqual(h.said, [(403, {"error": "you were not given this space"})])

    def test_not_a_space_is_heard_before_read_only(self):
        # One reply, and it is the first gate's: a name that is nothing is
        # not answered "not given".
        h = Stand(USER)
        self.assertIsNone(h._project_asked({"project": "ghost"}, write=True))
        self.assertEqual(h.said, [(400, {"error": "not a space: ghost"})])

    def test_a_write_into_a_locked_space_is_refused_to_all_but_who_it_holds_in(self):
        h = Stand(USER)
        self.assertIsNone(h._project_asked({"project": "locked"}, write=True))
        self.assertEqual(h.said, [(403, {"error": "locked is locked"})])
        h = Stand(OWNER)
        self.assertEqual(h._project_asked({"project": "locked"}, write=True), "locked")
        self.assertEqual(h._project_asked({"project": "locked"}), "locked")
        self.assertEqual(h.said, [])


if __name__ == "__main__":
    unittest.main()
