"""A node that trusts a key takes no signed agent older than the one it runs.

A signature says who made an agent, not when: every agent the release key
ever signed carries a good one, and an old one put back on a node reopens
what the ones after it closed. The zip's own version is under the
signature, so a node reads it from the bytes it checked and refuses one
whose BUILD is below its own, or that names none, in one phrase a page can
say. A person who means to go back says so at the node's console (older
on), as the word for unsigned builds is said. A node that trusts no key is
as it was, and so is the way back a failed update takes by itself, which is
the file the node kept and nothing a controller sends."""
import io
import json
import os
import sys
import unittest
import zipfile
from unittest import mock

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)
import agentpkg  # noqa: E402
import test_agent_first_signed as first  # noqa: E402

VERSION = agentpkg.version()
WINDOW, BUILD = VERSION.rsplit(".", 1)[0], int(VERSION.rsplit(".", 1)[1])
OLDER = agentpkg.an_agent(f"{WINDOW}.{BUILD - 1}")
SAME = agentpkg.an_agent(note="the same number, another file")
NEWER = agentpkg.an_agent(f"{WINDOW}.{BUILD + 1}")
# One from before the agent was a zip, and a zip whose package says no version.
SCRIPT = b"#!/usr/bin/env python3\nAGENT_VERSION = \"0.9.400\"\n"


def no_version():
    buf = io.BytesIO()
    with zipfile.ZipFile(buf, "w") as z:
        z.writestr("aerieos_agent/__init__.py", "# nothing\n")
    return buf.getvalue()


class Rule(first.Case):
    def judge(self, state, body, key=None):
        sig = self.sign(key or self.k, first.digest(body))
        return self.release.may_install(state, first.digest(body), sig, None, body)

    def test_the_version_is_read_from_the_zip_itself(self):
        self.assertEqual(self.release.agent_build(agentpkg.an_agent("0.9.463")), (463, "0.9.463"))
        self.assertEqual(self.release.agent_build(agentpkg.an_agent("1.2.1000")), (1000, "1.2.1000"))
        for body in (SCRIPT, no_version(), b"", b"PK\x03\x04 cut short"):
            self.assertEqual(self.release.agent_build(body), (None, ""))
        self.assertEqual(self.release.own_build(), BUILD)

    def test_an_older_signed_agent_is_refused_in_one_phrase(self):
        pinned = {"release_key": self.pub, "release_spare": self.spare}
        for body, key in ((OLDER, self.k), (OLDER, self.s), (SCRIPT, self.k), (no_version(), self.k)):
            ok, said = self.judge(pinned, body, key)
            self.assertFalse(ok)
            self.assertEqual(said.cause, "older than the agent this node runs")
            self.assertTrue(said.startswith("refused: this agent ("), said)
            self.assertIn("older on", said)
        # One added at the console signs for a build, and is held the same way.
        t, theirs = first.pair()
        ok, said = self.judge({"release_also": [theirs]}, OLDER, t)
        self.assertEqual((ok, said.cause), (False, "older than the agent this node runs"))

    def test_the_same_number_and_a_newer_one_are_taken(self):
        pinned = {"release_key": self.pub}
        for body in (SAME, NEWER, first.NEW):
            self.assertEqual(self.judge(pinned, body), (True, f"signed by the release key this node pinned ({self.pub[:16]}…)"))

    def test_the_console_s_word_lets_an_older_one_back(self):
        ok, said = self.judge({"release_key": self.pub, "older_ok": True}, OLDER)
        self.assertEqual((ok, said), (True, f"signed by the release key this node pinned ({self.pub[:16]}…)"))
        # ...and it is the console's alone: anything but true is no word.
        for word in ("yes", 1, None):
            self.assertFalse(self.judge({"release_key": self.pub, "older_ok": word}, OLDER)[0])

    def test_a_node_that_trusts_no_key_is_as_it_was(self):
        ok, said = self.judge({}, OLDER)
        self.assertTrue(ok)
        self.assertIn("no release key is pinned here", said)
        # ...and one whose console allows unsigned builds takes an unsigned one of any age.
        ok, said = self.release.may_install({"release_key": self.pub, "unsigned_ok": True}, first.digest(OLDER), "", None, OLDER)
        self.assertTrue(ok)
        self.assertIn("this node's console allows unsigned builds", said)

    def test_a_check_without_the_bytes_is_the_signature_s_alone(self):
        sig = self.sign(self.k, first.digest(OLDER))
        self.assertTrue(self.release.may_install({"release_key": self.pub}, first.digest(OLDER), sig)[0])


class Update(first.Update):
    def pinned(self, **more):
        self.write(dict(first.RECORD, release_key=self.pub, **more))

    def test_an_older_signed_update_installs_nothing_and_says_why(self):
        self.pinned()
        (state, code), job = self.update(OLDER, sig=self.sign(self.k, first.digest(OLDER)))
        self.assertEqual((state, code, job.installed), ("failed", 77, False))
        self.assertEqual(self.installed(), b"OLD")
        self.assertEqual(self.beside(), [], "nothing is left beside the agent")
        self.assertEqual(job.why.cause, "older than the agent this node runs")
        self.assertIn(f"refused: this agent ({WINDOW}.{BUILD - 1}) is older than the agent this node runs ({VERSION})", job.said)

    def test_a_newer_one_and_one_the_console_let_back_are_installed(self):
        self.pinned()
        (state, code), job = self.update(NEWER, sig=self.sign(self.k, first.digest(NEWER)))
        self.assertEqual((state, code, self.installed()), ("succeeded", 0, NEWER), job.said)
        with open(self.me, "wb") as f:
            f.write(b"OLD")
        self.pinned(older_ok=True)
        (state, code), job = self.update(OLDER, sig=self.sign(self.k, first.digest(OLDER)))
        self.assertEqual((state, code, self.installed()), ("succeeded", 0, OLDER), job.said)

    def test_the_way_back_a_failed_update_takes_is_the_kept_file_and_asks_nothing(self):
        """The entry puts FILE.prev back by itself: it reads no signature
        and no version, so the floor does not stand in its way."""
        with open(os.path.join(agentpkg.PKG, "..", "builderbot-agent.py"), encoding="utf-8") as f:
            entry = f.read()
        self.assertIn(".prev", entry)
        self.assertNotIn("may_install", entry)
        self.assertNotIn("release", entry.replace("released", ""))


class Console(first.Case):
    def test_older_on_and_off_are_kept_as_the_console_s_and_survive_the_agent_s_saves(self):
        cli = self.agent.module("cli")
        self.write(dict(first.RECORD, release_key=self.pub))
        with mock.patch.object(cli, "_at_console", lambda what: None), mock.patch("builtins.print") as said:
            cli.main(["older", "on"])
            self.assertTrue(self.read()["older_ok"])
            self.assertIn("until older off", said.call_args[0][0])
            # The running agent holds an older copy of the record and saves it whole.
            self.stores.save_state(dict(first.RECORD, release_key=self.pub, token="bbn_2"))
            self.assertEqual((self.read()["older_ok"], self.read()["token"]), (True, "bbn_2"))
            cli.main(["older", "off"])
            self.assertNotIn("older_ok", self.read())
            self.stores.save_state(dict(first.RECORD, release_key=self.pub, older_ok=True))
            self.assertNotIn("older_ok", self.read(), "a copy in memory never says it for the console")
            with self.assertRaises(SystemExit):
                cli.main(["older", "maybe"])

    def test_it_is_a_person_s_at_the_console(self):
        cli = self.agent.module("cli")
        self.write(dict(first.RECORD))
        with mock.patch.object(cli.sys.stdin, "isatty", lambda: False), self.assertRaises(SystemExit):
            cli.main(["older", "on"])
        self.assertNotIn("older_ok", self.read())

    def test_the_census_says_it(self):
        self.write(dict(first.RECORD, older_ok=True))
        self.assertTrue(self.stores.console_said().get("older_ok"))
        with open(os.path.join(agentpkg.PKG, "census.py"), encoding="utf-8") as f:
            self.assertIn('"older_ok": console_said().get("older_ok") is True', f.read())
        self.assertEqual(json.loads(json.dumps(self.read()))["older_ok"], True)


# The harness is the first-pin tests' own: its tests are theirs to run.
for _mine, _theirs in ((Rule, first.Case), (Update, first.Update), (Console, first.Case)):
    for _name in dir(_theirs):
        if _name.startswith("test_") and _name not in vars(_mine):
            setattr(_mine, _name, None)


if __name__ == "__main__":
    unittest.main()
