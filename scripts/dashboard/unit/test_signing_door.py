"""/api/signing's actions are two tables (server.SIGNING_SESSION_ACTS and
SIGNING_PERSON_ACTS): a session signs under its dials and never holds a
key, a person lists, signs, manages the keys or sets the backup password by
what each asks. The handler walks a row; the flows are the signing
modules'. Here the real handler is driven with a stand-in for the request,
and the modules' halves on their own."""
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
import releasesign  # noqa: E402
import signing  # noqa: E402


class Asker:
    """What the handler reads of a request: who asks, and each gate's answer."""
    def __init__(self, who, refused=(), dial="auto", own=True, sees=True, locked=False):
        self.who, self.refused, self.dial, self.own, self.sees, self.locked = who, refused, dial, own, sees, locked
        self.asked, self.dialed, self.said = [], [], None

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

    def _not_project(self, name):
        if not self.sees:
            self._json({"error": "no such space"}, 404)
        return not self.sees

    def _readonly(self, name):
        self.asked.append("unlocked")
        if self.locked:
            self._json({"error": "locked"}, 403)
        return self.locked

    def _refused(self, action, name=None):
        self.asked.append(action)
        if action in self.refused:
            self._json({"error": f"no {action}"}, 403)
            return True
        return False

    def _dialed(self, name, dial, instead="", person=False):
        self.dialed.append(dial)
        if self.dial is None:
            self._json({"error": "the dial says deny" + instead}, 403)
        return self.dial


PERSON = {"name": "ann", "uid": "u_1"}
SESSION = {"name": "ann", "uid": "u_1", "session": "app"}


class Door(unittest.TestCase):
    def ask(self, who, req, wants=True, owner="u_1", **kw):
        a = Asker(who, **kw)
        ran = []

        def stand_in(what, answer=None):
            return lambda *args, **kwargs: (ran.append((what, args, kwargs)), answer or ({"ok": True, "by": what}, 200))[1]
        with mock.patch.object(signing, "asked_keys", stand_in("keys")), mock.patch.object(signing, "asked_sign", stand_in("sign")), \
                mock.patch.object(signing, "asked", stand_in("person")), mock.patch.object(signing, "start", stand_in("start")), \
                mock.patch.object(signing, "set_backup_password", stand_in("password")), \
                mock.patch.object(releasesign, "looked", stand_in("looked")), mock.patch.object(releasesign, "asked", stand_in("release")), \
                mock.patch.object(releasesign, "signed_now", stand_in("now")), mock.patch.object(releasesign, "wants", lambda name: wants), \
                mock.patch.object(server.users, "account_of", lambda who: {"name": "Ann"}), mock.patch.object(server.users, "uid_of", lambda who: who.get("uid")), \
                mock.patch.object(server.membership, "owner_of", lambda name: owner), mock.patch.object(server.membership, "owner_name", lambda name: "Olu"):
            server.Handler._signing(a, {"project": "app", **req})
        return a, [(what, args) for what, args, _kw in ran]

    def test_a_session_signs_under_its_dials_and_reads_its_status_under_none(self):
        a, ran = self.ask(SESSION, {"action": "release"}, dial=None)
        self.assertEqual((a.dialed, ran), ([], [("looked", ("app",))]))
        a, ran = self.ask(SESSION, {"file": "app.apk"}, dial="ask")
        self.assertEqual((a.dialed, ran[0][0], ran[0][1][2:]), (["sign"], "sign", ("ask", "Ann", "who:asks")))
        a, ran = self.ask(SESSION, {"action": "sign"}, dial=None)
        self.assertEqual(ran, [])
        self.assertIn("a person signs from the Artifacts view", a.said[0]["error"])
        for act in ("keys", "generate", "map", "rotate"):
            a, ran = self.ask(SESSION, {"action": act})
            self.assertEqual((a.dialed, ran[0][0], ran[0][1][:2], ran[0][1][3:]), (["keys"], "keys", ("app", act), ("auto", "Ann")), act)
            a, ran = self.ask(SESSION, {"action": act}, dial=None)
            self.assertEqual(ran, [], act)
        self.assertEqual(a.asked, [], "a session is never asked a person's permission here")

    def test_a_session_s_retry_is_refused_for_what_it_is_before_its_dial_is_read(self):
        a, ran = self.ask(SESSION, {"action": "release-sign"}, wants=False, dial=None)
        self.assertEqual((a.dialed, ran, a.said[1]), ([], [], 400))
        self.assertIn("app's workflows hand over no unsigned APK to sign", a.said[0]["error"])
        a, ran = self.ask(SESSION, {"action": "release-sign", "tag": "not a tag!"})
        self.assertEqual((a.dialed, a.said), ([], ({"error": "--again needs a release's tag after it, as aerie sign status lists them"}, 400)))
        a, ran = self.ask(SESSION, {"action": "release-sign", "tag": "v1.2.0"}, dial="ask")
        self.assertEqual((a.dialed, ran[0][0], ran[0][1][2:]), (["sign"], "release", ("ask", "Ann")))
        a, ran = self.ask(SESSION, {"action": "release-sign"}, dial=None)
        self.assertEqual(ran, [])
        self.assertIn("a person presses Look for unsigned APKs now in the Signing view", a.said[0]["error"])

    def test_a_session_on_another_space_is_told_how_it_signs(self):
        for act in ("", "release", "keys", "release-sign", "list"):
            a, ran = self.ask(SESSION, {"action": act}, own=False)
            self.assertEqual((ran, a.said), ([], ({"error": server.SIGNING_ELSEWHERE}, 403)), act)

    def test_a_person_is_asked_what_each_action_is_for(self):
        a, ran = self.ask(PERSON, {"action": "list"}, refused=("signing",))
        self.assertEqual((a.asked, ran[0][0]), ([], "person"), "listing is for whoever sees the space")
        a, ran = self.ask(PERSON, {"action": "list"}, sees=False)
        self.assertEqual((ran, a.said[1]), ([], 404))
        a, ran = self.ask(PERSON, {"action": "sign", "file": "app.apk", "route": "sideload", "key": "k"}, refused=("signing",))
        self.assertEqual((a.asked, ran), (["unlocked"], [("start", ("who:asks", "app", "app.apk", "sideload", "k"))]), "signing a build is working on the space")
        a, ran = self.ask(PERSON, {"action": "sign"}, locked=True)
        self.assertEqual(ran, [])
        for act in ("put", "generate", "remove", "backup", "", "something new"):
            a, ran = self.ask(PERSON, {"action": act}, refused=("signing",))
            self.assertEqual((a.asked, ran), (["signing"], []), act)
            a, ran = self.ask(PERSON, {"action": act})
            self.assertEqual(ran[0][0], "person", act)
        a, ran = self.ask(PERSON, {"action": "release-sign", "tag": "v1"})
        self.assertEqual((a.asked, ran), (["signing"], [("now", ("app", "v1"))]))

    def test_the_backup_password_is_the_space_s_owner_s_alone(self):
        a, ran = self.ask(PERSON, {"action": "backup-password", "current": "a", "new": "b"}, owner="u_other")
        self.assertEqual((ran, a.said), ([], ({"error": "only app's owner (Olu) sets its backup password"}, 403)))
        a, ran = self.ask(PERSON, {"action": "backup-password", "current": "a", "new": "b"}, refused=("signing",))
        self.assertEqual((a.asked, ran), ([], [("password", ("app", "a", "b"))]), "no role's permission stands in for owning the space")

    def test_every_row_has_its_call_and_a_dial_says_what_a_person_does_instead(self):
        for table in (server.SIGNING_SESSION_ACTS, server.SIGNING_PERSON_ACTS):
            for act, row in table.items():
                self.assertTrue(callable(row.run), act)
        for act, row in server.SIGNING_SESSION_ACTS.items():
            self.assertFalse(row.ask, f"{act}: a session is under a dial, never a person's permission")
        for act, row in server.SIGNING_PERSON_ACTS.items():
            self.assertFalse(row.dial, act)
            self.assertEqual(row.ask == "space-owner", bool(row.owner_does), act)


class Flows(unittest.TestCase):
    """What the handler's rows call, with the phone and the owner stood in for."""
    def setUp(self):
        self.made = []
        said = lambda what, answer: lambda *a, **k: (self.made.append((what, a, k)), answer)[1]   # noqa: E731
        p = mock.patch.multiple(signing, ask_sign=said("ask_sign", {"ok": True, "queued": True}), ask_keys=said("ask_keys", {"error": "nobody to ask"}),
                                owner_of=lambda name: "u_owner", owner_name=lambda name: "", may=lambda who, action, name: "no Signing Write",
                                uid_of=lambda who: who.get("uid"), release_status=lambda name: {"key": "default"})
        p.start()
        self.addCleanup(p.stop)
        q = mock.patch.multiple(releasesign, ask_release_sign=said("ask_release_sign", {"ok": True}), owner_of=lambda name: "u_owner", owner_name=lambda name: "Olu")
        q.start()
        self.addCleanup(q.stop)

    def test_a_key_is_listed_made_or_proposed_by_what_the_dial_says(self):
        with mock.patch.object(signing, "listing", lambda name: ({"keys": []}, 200)), mock.patch.object(signing, "needs_lock", lambda name: None), \
                mock.patch.object(signing, "change", lambda act, name, args, by="": ({"ok": True, "args": args, "by": by}, 200)):
            self.assertEqual(signing.asked_keys("app", "keys", {}, "ask", "Ann"), ({"keys": []}, 200))
            got, status = signing.asked_keys("app", "generate", {"route": "sideload"}, "auto", "Ann")
            self.assertEqual((status, got["args"], got["by"]), (200, {"key": "default", "route": "sideload"}, "claude"))
            got, status = signing.asked_keys("app", "rotate", {"from": "a", "to": "b", "why": "old"}, "ask", "Ann")
            self.assertEqual((status, got), (400, {"error": "nobody to ask"}))
            what, args, kw = self.made[-1]
            self.assertEqual((what, args, kw), ("ask_keys", ("old", "app", "rotate", {"from": "a", "to": "b"}, "u_owner", "the space's owner"), {"asker_name": "Ann"}))
            self.assertEqual(signing.asked_keys("app", "map", {"package": "com.x", "key": "k"}, "auto", "Ann")[0]["args"], {"package": "com.x", "key": "k"})
        with mock.patch.object(signing, "needs_lock", lambda name: ({"error": "set a backup password first"}, 409)):
            self.assertEqual(signing.asked_keys("app", "generate", {}, "ask", "Ann"), ({"error": "set a backup password first"}, 409))

    def test_a_build_is_signed_or_asked_about_once_it_could_be_signed_at_all(self):
        with mock.patch.object(signing, "refusal", lambda name, f, r, k: ({"error": "no such file"}, 404)):
            self.assertEqual(signing.asked_sign("app", {"file": "x"}, "auto", "Ann", "p"), ({"error": "no such file"}, 404))
        with mock.patch.object(signing, "refusal", lambda name, f, r, k: None), \
                mock.patch.object(signing, "start", lambda principal, name, f, r, k="": ({"ok": True, "job": "j1", "as": principal}, 200)):
            self.assertEqual(signing.asked_sign("app", {"file": "x"}, "auto", "Ann", "p")[0]["as"], "p")
            got, status = signing.asked_sign("app", {"file": "x", "route": "sideload", "key": "k", "why": "ship"}, "ask", "Ann", "p")
            self.assertEqual((status, got["queued"]), (200, True))
            what, args, kw = self.made[-1]
            self.assertEqual((what, args, kw), ("ask_sign", ("ship", "app", "x", "sideload", "u_owner", "the space's owner"), {"asker_name": "Ann", "principal": "p", "key": "k"}))

    def test_a_person_s_list_says_what_the_view_draws_beside_it(self):
        with mock.patch.object(signing, "verb", lambda req, by="": ({"keys": [], "by": by}, 200)):
            got, status = signing.asked({"action": "list", "project": "app"}, {"uid": "u_owner"}, by="olu")
            self.assertEqual(got, {"keys": [], "by": "olu", "why": "no Signing Write", "may_backup": False, "may_lock": True, "release": {"key": "default"}})
            self.assertEqual(signing.asked({"action": "put", "project": "app"}, {"uid": "u_1"}, by="ann"), ({"keys": [], "by": "ann"}, 200))
        with mock.patch.object(signing, "verb", lambda req, by="": ({"error": "no such space"}, 404)):
            self.assertEqual(signing.asked({"action": "list", "project": "app"}, {"uid": "u_1"}), ({"error": "no such space"}, 404))

    def test_a_key_change_is_one_of_three(self):
        with mock.patch.object(signing, "generate", lambda p, route, key, by="": ("generate", p, route, key, by)), \
                mock.patch.object(signing, "set_map", lambda p, package, key: ("map", p, package, key)), \
                mock.patch.object(signing, "rotate", lambda p, a, b, by="": ("rotate", p, a, b, by)):
            self.assertEqual(signing.change("generate", "app", {"route": "sideload"}, by="claude"), ("generate", "app", "sideload", "default", "claude"))
            self.assertEqual(signing.change("map", "app", {"package": "com.x", "key": "k"}), ("map", "app", "com.x", "k"))
            self.assertEqual(signing.change("rotate", "app", {"from": "a", "to": "b"}, by="olu"), ("rotate", "app", "a", "b", "olu"))
        self.assertEqual(signing.change("remove", "app", {}), ({"error": "not a key change: remove"}, 400))

    def test_a_look_for_release_apks_is_started_asked_about_or_refused_for_what_it_is(self):
        looks = []
        with mock.patch.object(releasesign, "check_soon", lambda p, force=False, again="": (looks.append((p, force, again)), not again)[1]), \
                mock.patch.object(releasesign, "wants", lambda p: p == "app"), mock.patch.object(releasesign, "status", lambda p: {"key": "default"}), \
                mock.patch.object(releasesign, "attention", lambda ps: []):
            self.assertEqual(releasesign.sign_now("app"), ({"ok": True, "started": True, "said": "looking for unsigned release APKs to sign"}, 200))
            self.assertEqual(releasesign.sign_now("app", "v1")[1], 409, "a look already going was not asked for the tag")
            self.assertEqual(releasesign.unsignable("lib", "", "x")[1], 400)
            self.assertEqual(releasesign.unsignable("app", "bad tag!", "its own words"), ({"error": "its own words"}, 400))
            self.assertIsNone(releasesign.unsignable("app", "v1.2.0", "x"))
            self.assertEqual(releasesign.looked("app"), ({"release": {"key": "default"}, "attention": []}, 200))
            self.assertEqual(releasesign.asked("app", {}, "auto", "Ann")[0]["started"], True)
            self.assertEqual(releasesign.asked("app", {"tag": "v1", "why": "again"}, "auto", "Ann"), ({"ok": True}, 200), "a release signed again is the owner's answer whatever the dial")
            what, args, kw = self.made[-1]
            self.assertEqual((what, args, kw), ("ask_release_sign", ("again", "app", "u_owner", "Olu"), {"asker_name": "Ann", "tag": "v1"}))
            self.assertEqual(releasesign.asked("app", {}, "ask", "Ann"), ({"ok": True}, 200))
            self.assertEqual(releasesign.signed_now("app", "bad tag!"), ({"error": "not a release's tag"}, 400))
            got, status = releasesign.signed_now("app", "")
            self.assertEqual((status, got["release"], got["started"]), (200, {"key": "default"}, True))
        self.assertEqual(looks[0], ("app", True, ""))


if __name__ == "__main__":
    unittest.main()
