"""A session's token reaches the routes its table names and nothing else
(R227 step 4). Held here without a server: the table names only routes there
are, every path a session-side client names (aerie, its library, bb-tty and
the hooks) is in it, and the dispatcher's question refuses a session on any
other route before the route's own gate is read."""
import glob
import os
import re
import sys
import unittest

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.normpath(os.path.join(HERE, "..", "..", ".."))
SERVER = open(os.path.join(HERE, "..", "server.py"), encoding="utf-8").read()


def table(name):
    a = SERVER.index(f"\n{name} = (")
    return re.findall(r'\("(exact|prefix)",\s*"([^"]+)",\s*"(_[a-z_0-9]+)"\)', SERVER[a:SERVER.index("\n)\n", a)])


def names_between(opening, closing):
    a = SERVER.index(opening)
    return set(re.findall(r'"(_[a-z_0-9]+)"', SERVER[a:SERVER.index(closing, a)]))


GET, POST = table("GET_ROUTES"), table("POST_ROUTES")
GATES = set(re.findall(r'^    "(_[a-z_0-9]+)":', SERVER[SERVER.index("\nROUTE_GATES = {"):SERVER.index("\n}\n", SERVER.index("\nROUTE_GATES = {"))], re.M))
SESSION = names_between("\nSESSION_ROUTES = frozenset({", "\n})\n")

# The scripts that hold a session's token: aerie and what it runs, the
# terminal's launcher and the coding agents' hooks.
CLIENTS = ([os.path.join(ROOT, "scripts", "aerie")]
           + glob.glob(os.path.join(ROOT, "scripts", "lib", "*.py")) + glob.glob(os.path.join(ROOT, "scripts", "lib", "*.sh"))
           + glob.glob(os.path.join(ROOT, "scripts", "lib", "*.mjs"))
           + [f for f in glob.glob(os.path.join(ROOT, "scripts", "dashboard", "bb-*")) if os.path.isfile(f)])
# A path such a script names that is not the controller's: a lab's git host.
NOT_OURS = {"/api/healthz"}


def handlers(path):
    out = set()
    for routes in (GET, POST):
        for how, route, name in routes:
            if (path.split("?")[0] == route) if how == "exact" else path.startswith(route):
                out.add(name)
                break
    return out


class Table(unittest.TestCase):
    def test_it_names_only_routes_there_are(self):
        named = {n for _, _, n in GET + POST}
        self.assertTrue(len(SESSION) >= 30, SESSION)
        self.assertEqual(sorted(SESSION - named), [], "a name in the table with no route")
        self.assertEqual(sorted(SESSION - GATES), [], "a name in the table with no line in ROUTE_GATES")

    def test_every_path_a_session_s_client_names_is_in_it(self):
        missing = {}
        for f in CLIENTS:
            with open(f, encoding="utf-8", errors="replace") as fh:
                text = fh.read()
            for path in set(re.findall(r"(/api/[A-Za-z0-9_/-]+)", text)):
                path = path.rstrip("/")
                if path in NOT_OURS:
                    continue
                hs = handlers(path)
                # A path a client names reaches a route, and one of the
                # routes it reaches (its GET or its POST) is a session's.
                if not hs or not (hs & SESSION):
                    missing.setdefault(path, set()).add(os.path.basename(f))
        self.assertEqual({p: sorted(fs) for p, fs in missing.items()}, {},
                         "a session-side script names a path the session's table does not: the verb would be refused")

    def test_what_served_a_session_and_was_a_person_s_is_not_in_it(self):
        # The routes the inventory of 15 Nov found serving a session with no
        # session's verb behind them: the accounts, the page's reads, the
        # person's chat, layout and presence, a bug written as a person, and
        # typing into or ending the person's sessions.
        for name in ("_get_users", "_get_status", "_get_revs", "_get_live", "_get_home", "_get_findings", "_get_roles",
                     "_chat", "_layout", "_presence", "_bugs", "_say", "_send", "_session", "_roadmap", "_users", "_prefs_post"):
            self.assertIn(name, GATES, name)
            self.assertNotIn(name, SESSION, name)


class Gate(unittest.TestCase):
    """route_gate itself, lifted out of server.py with the tables it reads."""

    @classmethod
    def setUpClass(cls):
        a = SERVER.index("\nROUTE_GATES = {")
        b = SERVER.index("\ndef route_gate(name, me, action=None):")
        c = SERVER.index("\n\n\n", b)

        class _Users:
            @staticmethod
            def account_of(me):
                return me

            @staticmethod
            def is_owner(me):
                return (me or {}).get("role") == "owner"
        ns = {"users": _Users}
        exec(SERVER[a:c], ns)      # noqa: S102 (the repository's own source, read from beside this test)
        cls.ns = ns

    def test_a_session_is_refused_everywhere_but_its_table(self):
        gate, sess = self.ns["route_gate"], {"name": "session:alpha", "kind": "session", "session": "alpha", "role": "session", "seat": "u_1"}
        for name in sorted(GATES):
            why = gate(name, sess)
            if name in SESSION:
                self.assertEqual(why, "", name)
            else:
                self.assertTrue(why, f"{name} serves a session")
        self.assertIn("a session's token does not reach this", gate("_get_users", sess))

    def test_the_refusal_says_what_a_session_does_instead(self):
        # The words the handlers used to answer a session with themselves:
        # which verb is its own way to the same thing.
        gate, sess = self.ns["route_gate"], {"name": "session:alpha", "kind": "session", "session": "alpha", "role": "session", "seat": "u_1"}
        for name, words in (("_git_act", "aerie git"), ("_pending", "cannot answer for itself"), ("_artifacts", "aerie capture prune"),
                            ("_rules", "being held to"), ("_schedules", "a session has no say"), ("_roadmap", "aerie roadmap"),
                            ("_bugs", "aerie bug")):
            why = gate(name, sess)
            self.assertTrue(why.startswith("a session's token does not reach this"), why)
            self.assertIn(words, why, name)
        # Where only some of a route's actions are a session's, the gate
        # holds which, once the body is read: asked with no action (a GET),
        # the route answers; with one of its own, it answers; with another,
        # the refusal is the handler's own sentence.
        self.assertEqual(gate("_phone", sess), "")
        self.assertEqual(gate("_phone", sess, "ask"), "")
        self.assertEqual(gate("_phone", sess, "pair"), "a session asks; a person answers")
        self.assertIn("outside the session's view", gate("_jobs", sess, "run"))
        self.assertEqual(gate("_jobs", sess, "cancel"), "")
        self.assertIn("aerie tool install", gate("_toolpacks", sess, "remove"))
        self.assertIn("aerie sign", gate("_signing", sess, "list"))
        self.assertIn("by its person", gate("_transcripts", sess, "delete"))
        self.assertEqual(gate("_transcripts", sess, "label"), "")
        self.assertEqual(gate("_phone", {"name": "ann", "role": "user"}, "pair"), "", "a person's actions are the handler's to hold")
        self.assertEqual(sorted(set(self.ns["SESSION_ACTIONS"]) - SESSION), [], "actions named for a route outside the table")
        # A route a person's or the owner's gate holds says that gate's own words.
        self.assertIn("aerie changelog add", gate("_changelog", sess))
        self.assertEqual(sorted(set(self.ns["SESSION_INSTEAD"]) & SESSION), [], "a hint for a route the session reaches")
        self.assertEqual(sorted(set(self.ns["SESSION_INSTEAD"]) - GATES), [], "a hint for a route there is not")

    def test_a_person_is_asked_what_the_route_asks(self):
        gate = self.ns["route_gate"]
        self.assertEqual(gate("_get_users", {"name": "ann", "role": "user"}), "", "the handler holds its own")
        self.assertTrue(gate("_backup", {"name": "ann", "role": "user"}), "the owner's")
        self.assertEqual(gate("_backup", {"name": "own", "role": "owner"}), "")
        self.assertTrue(gate("_no_such_route", {"name": "own", "role": "owner"}), "a route with no line is nobody's")


if __name__ == "__main__":
    sys.exit(unittest.main())
