"""The route record (server.py's ROUTES): every route of the dashboard's API
once, with everything the dispatcher holds about it, and the tables read off
it. Held here without a server: the record agrees with itself, each route
names a gate and a handler there is, no route is taken by an earlier prefix,
and each table is what the record says."""
import ast
import collections
import os
import re
import sys
import unittest

HERE = os.path.dirname(os.path.abspath(__file__))
SERVER = open(os.path.join(HERE, "..", "server.py"), encoding="utf-8").read()
TABLES = ("GET_ROUTES", "POST_ROUTES", "ROUTE_GATES", "SESSION_ROUTES", "SESSION_ACTIONS", "SESSION_INSTEAD",
          "STREAMED_POSTS", "MAX_BODY_FOR", "OWN_WRITE_ROUTES", "WORK_REFUSED", "QUIET_POSTS")


def tables(source):
    """What a server.py's source makes of the route tables and the record,
    by name: each top-level statement that assigns one, and the record's own
    addition to the body caps, run in the file's order and nothing else of
    the file, since importing the server opens its state."""
    ns = {"collections": collections}
    for node in ast.parse(source).body:
        named = isinstance(node, ast.Assign) and getattr(node.targets[0], "id", "") in TABLES + ("Route", "ROUTES")
        added = (isinstance(node, ast.Expr) and isinstance(node.value, ast.Call)
                 and ast.unparse(node.value.func) == "MAX_BODY_FOR.update")
        if named or added:
            exec(compile(ast.Module([node], []), "server.py", "exec"), ns)  # noqa: S102 (the repository's own source)  # nosemgrep: python.lang.security.audit.exec-detected.exec-detected
    return ns


NOW = tables(SERVER)
ROUTES = NOW.get("ROUTES", ())
MATCHED = [r for r in ROUTES if r.how != "door"]


class Record(unittest.TestCase):
    def test_every_route_is_whole(self):
        self.assertGreater(len(MATCHED), 150)
        for r in ROUTES:
            self.assertIn(r.method, ("GET", "POST"), r)
            self.assertIn(r.how, ("exact", "prefix", "door"), r)
            self.assertTrue(r.path.startswith("/"), r)
            self.assertRegex(SERVER, r"(?m)^    def " + re.escape(r.handler) + r"\(self", f"{r.path} names a method the handler has not")
        for r in MATCHED:
            g = r.gate
            self.assertTrue(g == "handler" or (isinstance(g, tuple) and len(g) == 2 and g[0] in ("owner", "person") and g[1]),
                            f"{r.method} {r.path} names no gate")

    def test_a_handler_s_routes_say_one_thing(self):
        # The gate and a session's reach are asked by handler (route_gate),
        # so a handler two routes name is one answer.
        said = {}
        for r in MATCHED:
            self.assertEqual(said.setdefault(r.handler, (r.gate, r.session, r.instead)), (r.gate, r.session, r.instead), r.handler)

    def test_a_path_s_routes_say_one_thing(self):
        # What a space with no repository is refused is asked by path
        # (_work_refused), for the GET and the POST alike.
        said = {}
        for r in MATCHED:
            self.assertEqual(said.setdefault(r.path, r.needs_repo), r.needs_repo, r.path)
        self.assertEqual(len({(r.method, r.path) for r in ROUTES}), len(ROUTES), "a route written twice")

    def test_a_session_s_reach_is_said_one_way(self):
        for r in MATCHED:
            self.assertTrue(r.session in (False, True) or (isinstance(r.session, tuple) and r.session), r)
            if r.session:
                self.assertEqual(r.gate, "handler", f"{r.handler}: a person's or the owner's gate refuses every session")
            if isinstance(r.session, tuple):
                self.assertTrue(r.instead, f"{r.handler} names actions and not what the refusal of another says")
            if r.session is True:
                self.assertEqual(r.instead, "", f"{r.handler} is a session's whole, with words for a refusal there is not")

    def test_what_only_a_post_has(self):
        for r in ROUTES:
            if r.method == "GET":
                self.assertEqual((r.streamed, r.max_body, r.own_write, r.quiet), (False, None, False, False), r)
            self.assertEqual(r.streamed, r.how == "door", r)
            self.assertTrue(r.max_body is None or r.max_body > 64 * 1024, r)
            self.assertTrue(r.quiet in (False, True) or (isinstance(r.quiet, tuple) and r.quiet), r)
            if r.how == "door":
                self.assertEqual((r.gate, r.session), (None, False), r)

    def test_no_route_is_taken_by_an_earlier_prefix(self):
        for method in ("GET", "POST"):
            rows = [r for r in MATCHED if r.method == method]
            for i, r in enumerate(rows):
                for later in rows[i + 1:]:
                    self.assertFalse(r.how == "prefix" and later.path.startswith(r.path),
                                     f"{method} {later.path} is after {r.path}, which takes it")

    def test_the_tables_are_the_record_s(self):
        for method, name in (("GET", "GET_ROUTES"), ("POST", "POST_ROUTES")):
            self.assertEqual(NOW[name], tuple((r.how, r.path, r.handler) for r in MATCHED if r.method == method))
        self.assertEqual(set(NOW["ROUTE_GATES"]), {r.handler for r in MATCHED})
        self.assertEqual(NOW["SESSION_ROUTES"], {r.handler for r in MATCHED if r.session})
        self.assertEqual(set(NOW["SESSION_ACTIONS"]) | set(NOW["SESSION_INSTEAD"]), {r.handler for r in MATCHED if r.instead})
        self.assertEqual(sorted(NOW["STREAMED_POSTS"]), sorted(r.path for r in ROUTES if r.how == "door"))


class Quiet(unittest.TestCase):
    """What is left out of the audit: a route whole, or its hook kinds or
    actions by name (R228 step 7, B998)."""

    def quiet_post(self):
        ns = {"QUIET_POSTS": NOW["QUIET_POSTS"]}
        fn = next(n for n in ast.parse(SERVER).body if isinstance(n, ast.FunctionDef) and n.name == "_quiet_post")
        exec(compile(ast.Module([fn], []), "server.py", "exec"), ns)  # noqa: S102 (the repository's own source)  # nosemgrep: python.lang.security.audit.exec-detected.exec-detected
        return ns["_quiet_post"]

    def test_a_waiting_session_s_reads_of_its_ask_are_left_out_and_the_ask_is_kept(self):
        # A session waiting on an ask reads its outcome every second for up
        # to fifteen minutes: an hour of it was 3,600 rows of the 200,000.
        quiet = self.quiet_post()
        self.assertTrue(quiet("/api/phone", {"action": "outcome", "id": 3}))
        for kept in ("ask", "use", "answer", ""):
            self.assertFalse(quiet("/api/phone", {"action": kept}), kept)
        self.assertTrue(quiet("/api/v1/hook", {"kind": "turn"}))
        self.assertFalse(quiet("/api/v1/hook", {"kind": "asked"}))
        self.assertTrue(quiet("/api/presence", {}))


if __name__ == "__main__":
    sys.exit(unittest.main())
