"""/api/version's actions are a table (server.VERSION_ACTS): whose each is,
what a person is asked, the dial a session's ask goes through, and the one
call. The handler walks a row and holds no flow of its own; the flow of a
release asked for is version.asked_release, and a draft's reading and
publishing releasefiles'. Here the real handler is driven with a stand-in
for the request, and the two modules' halves on their own."""
import os
import sys
import tempfile
import unittest
from unittest import mock

HERE = os.path.dirname(os.path.abspath(__file__))
DASH = os.path.normpath(os.path.join(HERE, ".."))
sys.path.insert(0, DASH)
_tmp = tempfile.mkdtemp()
for _k in ("DASHBOARD_STATE", "WORKSPACE"):
    os.environ.setdefault(_k, os.path.join(_tmp, _k.lower()))
    os.makedirs(os.environ[_k], exist_ok=True)
_argv, sys.argv = sys.argv, ["server.py"]
import server  # noqa: E402  (importing it runs nothing: wire() is main()'s)
sys.argv = _argv
import releasefiles  # noqa: E402
import version  # noqa: E402


class Asker:
    """What the handler reads of a request: who asks, and each gate's answer."""
    def __init__(self, who, refused=(), dial="auto", own=True):
        self.who, self.refused, self.dial, self.own = who, refused, dial, own
        self.asked, self.dialed, self.said, self.changed = [], [], None, None

    def _project_asked(self, req):
        return req.get("project")

    def _who(self):
        return self.who

    def _principal(self):
        return "who:asks"

    def _json(self, payload, status=200):
        self.said = (payload, status)

    def _session_elsewhere(self, name, words):
        if self.who.get("session") and not self.own:
            self._json({"error": words}, 403)
            return True
        return False

    def _refused(self, action, name=None):
        self.asked.append((action, name))
        if action in self.refused:
            self._json({"error": f"no {action}"}, 403)
            return True
        return False

    def _dialed(self, name, dial, instead="", person=False):
        self.dialed.append(dial)
        if self.dial is None:
            self._json({"error": "the dial says deny" + instead}, 403)
        return self.dial

    def _release_change(self, act, name, req, who):
        self.changed = act


PERSON = {"name": "ann", "uid": "u_1"}
SESSION = {"name": "ann", "uid": "u_1", "session": "app"}


class Door(unittest.TestCase):
    def ask(self, who, req, **kw):
        a = Asker(who, **kw)
        ran = []

        def stand_in(what):
            return lambda *args: (ran.append((what, args)), ({"ok": True, "by": what}, 200))[1]
        with mock.patch.object(version, "asked_release", stand_in("asked")), mock.patch.object(version, "verb", stand_in("verb")), \
                mock.patch.object(releasefiles, "drafts", stand_in("drafts")), mock.patch.object(releasefiles, "draft", stand_in("draft")), \
                mock.patch.object(server.users, "account_of", lambda who: {"name": "Ann"}), \
                mock.patch.object(server.db, "audit", lambda *args: ran.append(("audit", args))):
            server.Handler._version(a, {"project": "app", **req})
        return a, ran

    def test_a_session_s_release_goes_through_the_dial_and_a_look_through_none(self):
        a, ran = self.ask(SESSION, {"action": "release"}, dial="ask")
        self.assertEqual((a.dialed, a.asked), (["release"], []), "a session is under the dial, not a person's permission")
        self.assertEqual(ran, [("asked", ("app", {"project": "app", "action": "release"}, "ask", "Ann", "who:asks"))])
        a, ran = self.ask(SESSION, {"action": "release"}, dial=None)
        self.assertEqual((ran, a.said[1]), ([], 403))
        self.assertIn("a person cuts it with Release on the Artifacts view", a.said[0]["error"])
        a, ran = self.ask(SESSION, {"action": "release", "dry": True}, dial=None)
        self.assertEqual((a.dialed, ran[0][1][2]), ([], "dry"), "a look that makes nothing is under no dial")

    def test_a_session_on_another_space_is_told_what_it_does_instead(self):
        for act, words in (("release", "a session releases its own space and no other"),
                           ("release-drafts", "a session reads its own space's drafts and no other")):
            a, ran = self.ask(SESSION, {"action": act}, own=False)
            self.assertEqual((ran, a.said), ([], ({"error": words}, 403)))

    def test_a_person_s_look_asks_the_version_area_and_a_person_s_release_is_the_panel_s(self):
        a, ran = self.ask(PERSON, {"action": "release", "dry": True})
        self.assertEqual((a.asked, a.dialed, ran[0][0], ran[0][1][2]), ([("version", "app")], [], "asked", "dry"))
        a, ran = self.ask(PERSON, {"action": "release", "dry": True}, refused=("version",))
        self.assertEqual((ran, a.said[1]), ([], 403))
        a, ran = self.ask(PERSON, {"action": "release"})
        self.assertEqual((a.asked, ran[0][0]), ([("version", "app")], "verb"), "cut from the Artifacts view, by version.verb")
        self.assertEqual(ran[0][1][:2], ("app", "release"))

    def test_the_panel_s_actions_are_a_person_s_and_ask_is_anybody_s_on_the_space(self):
        for act in ("bump", "init", "unbump", "policy", "something new"):
            a, ran = self.ask(SESSION, {"action": act})
            self.assertEqual(ran, [], act)
            self.assertIn("a session moves its version with aerie version bump", a.said[0]["error"])
            a, ran = self.ask(PERSON, {"action": act}, refused=("version",))
            self.assertEqual((ran, a.asked), ([], [("version", "app")]), act)
            a, ran = self.ask(PERSON, {"action": act})
            self.assertEqual(ran[0][0], "verb", act)
        a, ran = self.ask(PERSON, {"action": "ask"}, refused=("version",))
        self.assertEqual((a.asked, ran[0][0]), ([], "verb"), "putting the question to the space's session asks nothing")
        a, ran = self.ask(SESSION, {"action": "ask"})
        self.assertEqual((ran, a.said[1]), ([], 403))

    def test_drafts_are_read_by_whoever_sees_the_space_and_published_by_a_person(self):
        a, ran = self.ask(PERSON, {"action": "release-drafts"}, refused=("version",))
        self.assertEqual((a.asked, ran), ([], [("drafts", ("app",))]))
        a, ran = self.ask(SESSION, {"action": "release-drafts"})
        self.assertEqual(ran, [("drafts", ("app",))])
        for act in ("release-draft-notes", "release-publish"):
            a, ran = self.ask(SESSION, {"action": act, "tag": "v1"})
            self.assertEqual((ran, a.said), ([], ({"error": "a release is published by a person, once its notes are read: the Artifacts view's Drafts"}, 403)))
            a, ran = self.ask(PERSON, {"action": act, "tag": "v1"}, refused=("version",))
            self.assertEqual(ran, [])
        a, ran = self.ask(PERSON, {"action": "release-draft-notes", "tag": "v1", "notes": "words"})
        self.assertEqual(ran, [("draft", ("app", "release-draft-notes", "v1", "words"))], "its notes kept: no row on the audit")
        a, ran = self.ask(PERSON, {"action": "release-publish", "tag": "v1", "notes": 7})
        self.assertEqual(ran, [("draft", ("app", "release-publish", "v1", None)), ("audit", ("who:asks", "release-publish", "app", {"tag": "v1"}))])

    def test_a_change_to_a_published_release_is_its_own_table_s(self):
        for act in server.RELEASE_CHANGES:
            a, ran = self.ask(PERSON, {"action": act})
            self.assertEqual((a.changed, ran), (act, []))

    def test_every_row_says_whose_it_is(self):
        for act, row in server.VERSION_ACTS.items():
            self.assertTrue(callable(row.run), act)
            self.assertTrue(row.persons or row.elsewhere, f"{act}: a session is told one or the other")
            self.assertEqual(bool(row.dial), bool(row.instead), act)


class Asked(unittest.TestCase):
    """version.asked_release: the refusals a release would meet, before a
    rehearsal is spent or anybody is asked."""
    def run_it(self, mode, req=None, plan=None, ready=None, stuck=""):
        made = []
        plan = plan or {"tag": "v1.2.0", "sha": "abc", "dev": False, "channel": "stable", "pre": ""}
        parts = dict(readiness=lambda name, fresh=False: ready or {"wanted": False, "why": ""}, unstartable=lambda name: stuck,
                     releaser=lambda *a, **k: (made.append(("made", a, k)), ({"ok": True, "tag": "v1.2.0"}, 200))[1],
                     ask_release=lambda *a, **k: (made.append(("asked", a, k)), {"ok": True, "queued": True})[1],
                     owner_of=lambda name: "u_owner", owner_name=lambda name: "Olu", git_env=lambda: {}, may_push=lambda name: True)
        with mock.patch.multiple(version, **parts), mock.patch.object(version, "release_plan", lambda *a, **k: dict(plan)):
            got = version.asked_release("app", {"why": "the fix", **(req or {})}, mode, "Ann", "who:asks")
        return got, made

    def test_a_look_says_the_plan_and_makes_nothing(self):
        (got, status), made = self.run_it("dry")
        self.assertEqual((status, got["ok"], got["tag"], made), (200, True, "v1.2.0", []))
        (got, status), made = self.run_it("dry", ready={"wanted": True, "why": "no sideload key"})
        self.assertEqual((status, got["unsigned"], made), (200, "no sideload key", []), "said, not refused: it may go without and be signed after")

    def test_what_the_release_would_meet_is_said_before_anybody_is_asked(self):
        (got, status), made = self.run_it("ask", plan={"error": "nothing to release"})
        self.assertEqual((got, status, made), ({"error": "nothing to release"}, 400, []))
        for mode in ("ask", "auto"):
            (got, status), made = self.run_it(mode, ready={"wanted": True, "why": "no sideload key"})
            self.assertEqual((status, got["unsigned"], made), (409, "no sideload key", []), mode)
            self.assertIn("v1.2.0's Android APK could not be signed: no sideload key", got["error"])
        (got, status), made = self.run_it("ask", req={"unsigned": True}, ready={"wanted": True, "why": "no sideload key"})
        self.assertEqual((status, made[0][0]), (200, "asked"), "--without-apk")
        (got, status), made = self.run_it("ask", stuck="the release environment has no approver")
        self.assertEqual((status, made), (409, []))
        self.assertIn("v1.2.0 would stay a draft: the release environment has no approver", got["error"])
        (got, status), made = self.run_it("dry", stuck="the release environment has no approver")
        self.assertEqual(status, 409, "a rehearsal is not spent on it either")

    def test_auto_makes_it_and_ask_queues_it_for_the_owner(self):
        (got, status), made = self.run_it("auto", stuck="said by the release itself where it is auto")
        self.assertEqual((status, got["channel"], made[0][0], made[0][1]), (200, "stable", "made", ("app", "", "Ann", "who:asks")))
        (got, status), made = self.run_it("ask")
        self.assertEqual((status, got["queued"], got["channel"]), (200, True, "stable"))
        what, args, kw = made[0]
        self.assertEqual((what, args[0], args[1], args[4], args[5], kw["asker_name"], kw["principal"]), ("asked", "the fix", "app", "u_owner", "Olu", "Ann", "who:asks"))


class Drafts(unittest.TestCase):
    def test_the_drafts_carry_what_each_still_lacks_and_no_page_is_no_drafts(self):
        fr = releasefiles.forgerelease
        with mock.patch.object(fr, "drafts", lambda p: {"drafts": [{"tag": "v1"}, {"tag": "v2"}]}), \
                mock.patch.object(releasefiles, "missing", lambda p, tag: (["app.apk"], "url") if tag == "v1" else (_ for _ in ()).throw(fr.Refused("no token"))):
            got, status = releasefiles.drafts("app")
        self.assertEqual((status, got["drafts"]), (200, [{"tag": "v1", "missing": ["app.apk"]}, {"tag": "v2", "missing": [], "missing_error": "no token"}]))
        with mock.patch.object(fr, "drafts", lambda p: {"error": "no git host"}):
            self.assertEqual(releasefiles.drafts("app"), ({"drafts": [], "why": "no git host"}, 200))

    def test_notes_are_kept_and_a_publish_names_what_is_missing_first(self):
        fr = releasefiles.forgerelease
        seen = []
        with mock.patch.object(fr, "draft_notes", lambda p, tag, notes: (seen.append(("notes", tag, notes)), {"ok": True})[1]), \
                mock.patch.object(fr, "publish_draft", lambda p, tag, notes, miss: (seen.append(("publish", tag, notes, miss)), {"error": "it lacks app.apk"})[1]), \
                mock.patch.object(releasefiles, "missing", lambda p, tag: (["app.apk"], "url")):
            self.assertEqual(releasefiles.draft("app", "release-draft-notes", "v1", None), ({"ok": True}, 200))
            self.assertEqual(releasefiles.draft("app", "release-publish", "v1", "words"), ({"error": "it lacks app.apk"}, 400))
        self.assertEqual(seen, [("notes", "v1", ""), ("publish", "v1", "words", ["app.apk"])])
        with mock.patch.object(releasefiles, "missing", lambda p, tag: (_ for _ in ()).throw(fr.Refused("no such release"))):
            self.assertEqual(releasefiles.draft("app", "release-publish", "v9", None), ({"error": "no such release"}, 400))


if __name__ == "__main__":
    unittest.main()
