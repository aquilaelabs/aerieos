"""The route record says what each handler asks, and says it truly.

A route whose handler refuses for itself carries ("handler", NAME, ...): the
names of everything that handler asks of its caller. They are derived from
the handler's own checks (scripts/lib/routegates.py), and this holds the
record equal to the derivation, so who may reach a route is read in the
table, a check added to a handler shows in the table's diff, and the routes
that refuse nobody signed in are a list somebody has to change on purpose."""
import ast
import os
import sys
import unittest

HERE = os.path.dirname(os.path.abspath(__file__))
DASH = os.path.normpath(os.path.join(HERE, ".."))
sys.path.insert(0, os.path.normpath(os.path.join(DASH, "..", "lib")))
import routegates  # noqa: E402

with open(os.path.join(DASH, "server.py"), encoding="utf-8") as _f:
    SERVER = _f.read()
TREE = ast.parse(SERVER)
HANDLERS = routegates.handlers_of(TREE)
ROWS = [(method, how, path, fn, ast.literal_eval(gate) if gate is not None else None)
        for method, how, path, fn, gate, _el in routegates.routes_of(TREE)]
# What a dispatcher-gated route's handler asks besides (Route's asks).
MORE = {(method, path): next((ast.literal_eval(k.value) for k in el.keywords if k.arg == "asks"), ())
        for method, _how, path, _fn, _gate, el in routegates.routes_of(TREE)}

# The routes that refuse nobody who is signed in, each for its reason. A new
# one is added here by whoever decided it should be so.
REFUSE_NOBODY = {
    "open": {
        "GET /api/apps": "the companion apps this controller offers, as the Library's cards show them",
        "GET /api/help": "the docs the image ships",
        "GET /api/global-rules": "the rules every session is handed already",
    },
    "seen": {
        "GET /api/revs": "the revisions of what this account sees",
        "GET /api/live": "the sessions on the spaces this account sees",
        "GET /api/status": "the status read, cut to this account",
        "GET /api/findings": "the findings of the spaces this account sees",
        "GET /api/meta": "the build this is, and for a session its node's agent",
        "GET /api/welcome": "AerieOS's own changelog and where this account last looked",
        "GET /api/pack-icon": "a pack's or an app's icon",
        "POST /api/v1/claude-login": "a session's token saying what its account is signed in to on its node",
        "POST /api/v1/hook": "a session's hooks, under the account its token names",
        "POST /api/pc": "a session's word with a PC lent to its space",
    },
    "own": {
        "GET /api/notices": "what the page said to this account",
        "POST /api/notices": "the same, kept or cleared",
        "POST /api/layout": "this account's open tabs",
        "POST /api/bell": "this account's bell",
    },
}


class Record(unittest.TestCase):
    def test_every_handler_gated_route_names_what_its_handler_asks(self):
        wrong = []
        for method, _how, path, fn, gate in ROWS:
            if not gate or gate[0] != "handler":
                continue
            asks = tuple(routegates.asks(HANDLERS[fn], HANDLERS))
            if gate[1:] != asks:
                wrong.append(f"{method} {path}: the record says {gate[1:]}, {fn} asks {asks}")
        self.assertEqual(wrong, [], "write the handler's asks into its Route (routegates.asks)")

    def test_a_route_the_dispatcher_gates_names_what_its_handler_asks_besides(self):
        # The owner's, an administrator's or a person's at the dispatcher,
        # and then the handler's own checks: the record says both. One that
        # asks nothing more carries no asks at all.
        wrong, named = [], 0
        for method, _how, path, fn, gate in ROWS:
            if not gate:
                continue
            said = MORE[(method, path)]
            if gate[0] == "handler":
                if said:
                    wrong.append(f"{method} {path}: a handler gate names its asks in the gate, never in asks as well")
                continue
            asks = tuple(routegates.asks(HANDLERS[fn], HANDLERS)) if fn in HANDLERS else ()
            want = () if asks in (("open",), ("seen",), ("own",)) else asks
            named += bool(want)
            if said != want:
                wrong.append(f"{method} {path}: the record says asks={said}, {fn} asks {want}")
        self.assertEqual(wrong, [], "write the handler's asks into its Route (routegates.asks)")
        self.assertGreater(named, 10, "the routes were found")

    def test_no_route_is_left_saying_only_that_its_handler_decides(self):
        bare = [f"{m} {p}" for m, _h, p, _f, g in ROWS if g == "handler" or g == ("handler",)]
        self.assertEqual(bare, [])
        self.assertGreater(sum(1 for *_x, g in ROWS if g and g[0] == "handler"), 150)

    def test_the_streamed_doors_name_theirs_too(self):
        doors = {p: g for _m, how, p, _f, g in ROWS if how == "door"}
        self.assertEqual(doors, {"/api/upload-archive": ("handler", "create"), "/api/vms-iso-upload": ("handler", "vms-write"),
                                 "/api/move-land": ("handler", "owner"), "/api/node-files/upload": ("handler", "admin")})

    def test_the_routes_that_refuse_nobody_are_these(self):
        for kind, want in REFUSE_NOBODY.items():
            have = sorted(f"{m} {p}" for m, _h, p, _f, g in ROWS if g == ("handler", kind))
            self.assertEqual(have, sorted(want), f"the routes whose handler asks only `{kind}`")


class Derived(unittest.TestCase):
    def asks(self, body):
        cls = ast.parse("class Handler:\n" + "\n".join("    " + line for line in body.strip("\n").split("\n")))
        fns = routegates.handlers_of(cls)
        return routegates.asks(fns["_x"], fns)

    def test_a_permission_a_space_and_a_node_are_named_as_asked(self):
        self.assertEqual(self.asks('''
def _x(self, req):
    if not (name := self._project_asked(req, write=True)):
        return None
    if self._refused("settings", name) or self._refused_on_node("configure", req["node"]):
        return None
    mode = self._dialed(name, "release", "")
    return self._json({})
'''), ["space", "unlocked", "settings", "node:configure", "dial:release"])

    def test_a_helper_s_checks_are_its_caller_s(self):
        self.assertEqual(self.asks('''
def _x(self):
    return self._inner("alpha")
def _inner(self, name):
    if self._refused("signing", name):
        return None
    return self._json({})
'''), ["signing"])

    def test_one_that_refuses_nobody_says_which_kind(self):
        self.assertEqual(self.asks("def _x(self):\n    return self._json(docs.listing())"), ["open"])
        self.assertEqual(self.asks("def _x(self):\n    return self._json(view(self._who()))"), ["seen"])
        self.assertEqual(self.asks("def _x(self, req):\n    return self._json(*notes.act(users.uid_of(self._who()), req))"), ["own"])


if __name__ == "__main__":
    unittest.main()
