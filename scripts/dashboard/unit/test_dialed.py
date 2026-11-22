"""A space's Agents-may dial as server.py's handlers ask it (_dialed), and
the three changes to a published release that share one path under the
release's dial (RELEASE_CHANGES, _release_change). Held here without a
server: the helper, the path and the two tables are lifted out of server.py's
source and run against stand-ins that record what was asked of them."""
import ast
import collections
import os
import sys
import unittest

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, os.path.join(HERE, ".."))
from fields import field  # noqa: E402

SERVER = open(os.path.join(HERE, "..", "server.py"), encoding="utf-8").read()
TABLES = ("DIALS", "ReleaseChange", "RELEASE_CHANGES")
LIFTED = ("_dialed", "_release_change", "_result", "_refused")
SESSION = {"name": "session:alpha", "session": "alpha"}
PERSON = {"name": "olga", "uid": "u_1"}


class Recorder:
    """A module's stand-in: every call is kept, and answers what the test
    said that name answers (a dict that is the plan, by default)."""

    def __init__(self, log, name, answers):
        self._log, self._name, self._answers = log, name, answers

    def __getattr__(self, attr):
        return Recorder(self._log, f"{self._name}.{attr}", self._answers)

    def __call__(self, *a, **kw):
        self._log.append((self._name, a, kw))
        got = self._answers.get(self._name, {"tag": "v1.0.0"})
        return got(*a, **kw) if callable(got) else got


def source():
    """The tables' assignments and the lifted methods as one piece of
    source, in the file's order, read off server.py once."""
    tree = ast.parse(SERVER)
    lines = SERVER.splitlines()
    tables = [n for n in tree.body if isinstance(n, ast.Assign) and getattr(n.targets[0], "id", "") in TABLES]
    cls = next(n for n in tree.body if isinstance(n, ast.ClassDef) and n.name == "Handler")
    methods = [f for f in cls.body if isinstance(f, ast.FunctionDef) and f.name in LIFTED]
    return "\n".join(["\n".join(lines[n.lineno - 1:n.end_lineno]) for n in tables] + ["class Lifted:"]
                     + ["\n".join(lines[f.lineno - 1:f.end_lineno]) for f in methods])


CODE = compile(source(), "server.py", "exec")


def lifted(answers):
    """(stand-in handler class, the log its modules write, the tables)."""
    log = []
    ns = {"collections": collections, "field": field}
    for name in ("prefs", "forgerelease", "phone", "version", "users", "membership",
                 "_release_remover", "_release_withdrawer", "_release_editor"):
        ns[name] = Recorder(log, name, answers)
    exec(CODE, ns)      # noqa: S102 (the repository's own source, read from beside this test)

    class Stand(ns["Lifted"]):
        def __init__(self, who):
            self.who, self.said = who, []

        def _who(self):
            return self.who

        def _principal(self):
            return "user:" + self.who["name"]

        def _json(self, obj, code=200):
            self.said.append((code, obj))

    return Stand, log, ns


def answers(dial="ask", **more):
    return {"prefs.get": {"release": dial, "sign": dial, "keys": dial}, "users.may": "", "users.account_of": lambda who: who,
            "membership.owner_of": "u_1", "membership.owner_name": "olga", "version.current_tag": ("v0.9.0", ""),
            "phone.ask_release_remove": {"ok": True, "id": 3}, "phone.ask_release_withdraw": {"ok": True, "id": 4},
            "phone.ask_release_edit": {"ok": True, "id": 5},
            "_release_remover": ({"removed": 1}, 200), "_release_withdrawer": ({"withdrawn": 1}, 200),
            "_release_editor": ({"edited": 1}, 200), **more}


def called(log, name):
    return [row for row in log if row[0] == name]


class Dial(unittest.TestCase):
    def test_deny_is_refused_in_the_dial_s_sentence(self):
        said = {
            ("release", "; a person cuts it with Release on the Artifacts view"):
                "alpha's settings say Claude does not release it (Agents may: Tag and publish a release); "
                "a person cuts it with Release on the Artifacts view",
            ("sign", "; a person signs from the Artifacts view"):
                "alpha's settings say Claude does not sign its builds (Agents may: Sign a build); "
                "a person signs from the Artifacts view",
            ("sign", "; a person presses Look for unsigned APKs now in the Signing view"):
                "alpha's settings say Claude does not sign its builds (Agents may: Sign a build); "
                "a person presses Look for unsigned APKs now in the Signing view",
            ("keys", ""): "alpha's settings say Claude does not manage its signing keys (Agents may: Manage signing keys)",
        }
        for (dial, instead), words in said.items():
            stand, _, _ = lifted(answers("deny"))
            h = stand(SESSION)
            self.assertIsNone(h._dialed("alpha", dial, instead))
            self.assertEqual(h.said, [(403, {"error": words})])

    def test_ask_and_auto_come_back_and_nothing_is_said(self):
        for dial in ("ask", "auto"):
            stand, _, _ = lifted(answers(dial))
            h = stand(SESSION)
            self.assertEqual(h._dialed("alpha", "release"), dial)
            self.assertEqual(h.said, [])

    def test_a_dial_never_set_asks(self):
        for kept in (None, {}, {"release": ""}, {"release": None}):
            stand, _, _ = lifted(answers(**{"prefs.get": kept}))
            self.assertEqual(stand(SESSION)._dialed("alpha", "release"), "ask", kept)

    def test_a_person_is_under_no_dial_and_the_settings_are_not_read(self):
        stand, log, _ = lifted(answers("deny"))
        h = stand(PERSON)
        self.assertEqual(h._dialed("alpha", "release", person=True), "auto")
        self.assertEqual((h.said, log), ([], []))


class Changes(unittest.TestCase):
    WORDS = {"release-remove": ("changes", ", which taking a file off its release is part of; a person removes it on the forge"),
             "release-withdraw": ("withdraws", ", which withdrawing one is part of; a person deletes it on the forge"),
             "release-edit": ("edits", ", which an edit of its release is part of; a person edits it on the forge")}
    DOER = {"release-remove": "_release_remover", "release-withdraw": "_release_withdrawer", "release-edit": "_release_editor"}
    ASK = {"release-remove": "phone.ask_release_remove", "release-withdraw": "phone.ask_release_withdraw",
           "release-edit": "phone.ask_release_edit"}

    def run_one(self, act, who, dial="ask", req=None, **more):
        stand, log, _ = lifted(answers(dial, **more))
        h = stand(who)
        h._release_change(act, "alpha", {"tag": "v1.0.0", "why": "a broken build", **(req or {})}, who)
        return h.said, log

    def test_the_table_is_the_three(self):
        _, _, ns = lifted(answers())
        self.assertEqual(sorted(ns["RELEASE_CHANGES"]), sorted(self.WORDS))

    def test_a_session_changes_its_own_space_s_release_and_no_other(self):
        for act, (does, _) in self.WORDS.items():
            stand, log, _ = lifted(answers("auto"))
            h = stand(SESSION)
            h._release_change(act, "beta", {"tag": "v1.0.0"}, SESSION)
            self.assertEqual(h.said, [(403, {"error": f"a session {does} its own space's release and no other"})])
            self.assertEqual(log, [], act)

    def test_deny_refuses_a_session_before_a_plan_is_made(self):
        for act, (_, instead) in self.WORDS.items():
            said, log = self.run_one(act, SESSION, "deny")
            self.assertEqual(said, [(403, {"error": "alpha's settings say Claude does not release it "
                                                    "(Agents may: Tag and publish a release)" + instead})])
            self.assertEqual([row[0] for row in log], ["prefs.get"], act)

    def test_ask_queues_the_request_for_the_owner_with_who_asked(self):
        for act in self.WORDS:
            said, log = self.run_one(act, SESSION, "ask")
            self.assertEqual(said[0][0], 200, act)
            (_, args, kw), = called(log, self.ASK[act])
            self.assertEqual(args, ("a broken build", "alpha", {"tag": "v1.0.0"}, "u_1", "olga"))
            self.assertEqual(kw, {"asker_name": "session:alpha", "principal": "user:session:alpha"})
            self.assertEqual(called(log, self.DOER[act]), [], act)

    def test_auto_does_it_now_but_a_withdrawal_always_asks(self):
        for act in self.WORDS:
            said, log = self.run_one(act, SESSION, "auto")
            asked, done = called(log, self.ASK[act]), called(log, self.DOER[act])
            if act == "release-withdraw":
                self.assertEqual((len(asked), len(done)), (1, 0))
            else:
                self.assertEqual((len(asked), len(done)), (0, 1))
                self.assertEqual(done[0][1], ("alpha", {"tag": "v1.0.0"}, "session:alpha", "user:session:alpha"))

    def test_a_person_with_the_version_area_does_it_whatever_the_dial(self):
        for act in self.WORDS:
            said, log = self.run_one(act, PERSON, "deny")
            self.assertEqual(said[0][0], 200, act)
            self.assertEqual(len(called(log, self.DOER[act])), 1, act)
            self.assertEqual(called(log, "prefs.get") + called(log, self.ASK[act]), [], act)
            self.assertEqual(called(log, "users.may")[0][1][1:], ("version", "alpha"))

    def test_a_person_without_it_is_refused_first(self):
        for act in self.WORDS:
            said, log = self.run_one(act, PERSON, **{"users.may": "the version area is not yours here"})
            self.assertEqual(said, [(403, {"error": "the version area is not yours here"})])
            self.assertEqual([row[0] for row in log], ["users.may"], act)

    def test_a_plan_refused_is_said_and_nobody_is_asked(self):
        plans = {"release-remove": "forgerelease.remove_plan", "release-withdraw": "forgerelease.withdraw_plan",
                 "release-edit": "forgerelease.edit_plan"}
        for act, plan in plans.items():
            said, log = self.run_one(act, SESSION, "ask", **{plan: {"error": "no such release"}})
            self.assertEqual(said, [(400, {"error": "no such release"})])
            self.assertEqual(called(log, self.ASK[act]) + called(log, self.DOER[act]), [], act)

    def test_the_newest_tag_stands_for_one_not_named_except_in_a_withdrawal(self):
        for act in self.WORDS:
            said, log = self.run_one(act, SESSION, "ask", req={"tag": "", "component": "app"})
            newest = called(log, "version.current_tag")
            plan = next(row for row in log if row[0].startswith("forgerelease."))
            if act == "release-withdraw":
                self.assertEqual((newest, plan[1][:2]), ([], ("alpha", "")))
            else:
                self.assertEqual((newest[0][1], plan[1][:2]), (("alpha", "app"), ("alpha", "v0.9.0")))

    def test_no_tag_to_fall_to_is_said(self):
        for act in ("release-remove", "release-edit"):
            said, log = self.run_one(act, SESSION, "ask", req={"tag": ""}, **{"version.current_tag": ("", "nothing is released yet")})
            self.assertEqual(said, [(400, {"error": "nothing is released yet"})])
            self.assertEqual(called(log, "prefs.get"), [], act)

    def test_what_is_planned_is_read_from_the_body_by_its_type(self):
        _, log = self.run_one("release-remove", SESSION, req={"remove": ["a.apk"]})
        self.assertEqual(called(log, "forgerelease.remove_plan")[0][1], ("alpha", "v1.0.0", ["a.apk"]))
        _, log = self.run_one("release-remove", SESSION, req={"remove": "a.apk"})
        self.assertEqual(called(log, "forgerelease.remove_plan")[0][1], ("alpha", "v1.0.0", []))
        _, log = self.run_one("release-edit", SESSION, req={"notes": "new", "attach": ["b.apk"]})
        self.assertEqual(called(log, "forgerelease.edit_plan")[0][1], ("alpha", "v1.0.0", "new", ["b.apk"]))
        _, log = self.run_one("release-edit", SESSION, req={"notes": 7, "attach": "b.apk"})
        self.assertEqual(called(log, "forgerelease.edit_plan")[0][1], ("alpha", "v1.0.0", None, []))


if __name__ == "__main__":
    unittest.main()
