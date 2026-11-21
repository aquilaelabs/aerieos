"""A refused agent update is one phrase where a person reads it.

A node that refused its controller's agent said why in a paragraph: what
was wrong, the first characters of every key it takes, and two commands for
its console. That paragraph was the job's error, and the bell's row was
made of it. Now the refusal is a Refusal: its cause alone, one phrase, is
the job's error, and the whole of it stays in the job's log and the node's
own. An agent from before this still sends the paragraph, and so may any
failed update, so the controller cuts whatever arrives to a first phrase
with no key characters and no command before a row is made of it."""
import os
import re
import sys
import unittest

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)
sys.path.insert(0, os.path.join(HERE, ".."))
import nodes  # noqa: E402
import test_agent_first_signed as first  # noqa: E402

# What an agent from before this sent as a refused update's error, whole.
OLD_WORDS = ("refused: its signature is not the pinned release key's. This node takes only updates signed by the release key "
             "it pinned (2eb9add8c0659630…) or its spare (9f1c0a77d2e45b18…) or a key added at its console (aa11bb22cc33dd44…). "
             "A build made outside AerieOS's release builds is unsigned unless its builder signs it with a key of their own. "
             "At this machine's own console: sudo aerieos-agent release-key add HEX trusts that builder's key, "
             "sudo aerieos-agent unsigned on allows unsigned builds")
A_PHRASE = re.compile(r"[^\n]{1,120}")


def reads_as_a_row(test, said):
    test.assertTrue(A_PHRASE.fullmatch(said), said)
    test.assertIsNone(re.search(r"[0-9a-f]{8,}", said), f"no key or digest characters: {said}")
    test.assertIsNone(re.search(r"\bsudo\b|aerieos-agent|release-key|unsigned on", said), f"no console command: {said}")
    test.assertNotIn(". ", said, f"one sentence: {said}")
    test.assertFalse(said.startswith("refused"), said)


class TheControllersCut(unittest.TestCase):
    def test_a_paragraph_from_an_older_agent_is_its_first_phrase(self):
        self.assertEqual(nodes.refusal_phrase(OLD_WORDS), "its signature is not the pinned release key's")

    def test_whatever_a_failed_update_said_reads_as_a_row(self):
        for said, want in (
                ("refused: the controller sent no signature with it. This node takes only updates signed by the release key it pinned (2eb9add8c0659630…). x",
                 "the controller sent no signature with it"),
                ("older than the agent this node runs", "older than the agent this node runs"),
                ("its signature is under no key this node trusts", "its signature is under no key this node trusts"),
                ("busy with j_12 (exec: make): not retried; press Update agent again when they finish",
                 "busy with j_12 (exec: make): not retried; press Update agent again when they finish"),
                ("digest mismatch: wanted sha256:0123456789abcdef…, got sha256:fedcba9876543210…", "digest mismatch: wanted , got"),
                ("refused: this agent (0.9.463) is older than the agent this node runs (0.9.490). At this machine's own console: "
                 "sudo aerieos-agent older on lets an older agent be put back", "this agent (0.9.463) is older than the agent this node runs (0.9.490)"),
                ("the new agent does not start on this node, so it was not installed: Traceback (most recent call last): " + "x" * 300, None),
                ("", "it was refused"), (None, "it was refused"), ("refused: ", "it was refused"),
                ("run sudo aerieos-agent unsigned on", "run")):
            got = nodes.refusal_phrase(said)
            reads_as_a_row(self, got)
            if want is not None:
                self.assertEqual(got, want, said)

    def test_the_held_sentence_of_the_controller_s_own_is_one_too(self):
        with open(os.path.join(HERE, "..", "nodes.py"), encoding="utf-8") as f:
            text = f.read()
        self.assertNotIn("unsigned on at its console allows this one", text)
        self.assertIn('", and this controller\'s build is unsigned")', text)
        for said in ("it takes only agent updates a release signed, and this controller's build is unsigned",
                     "it takes only agent updates signed by a key added at its console, and this controller's build is unsigned"):
            reads_as_a_row(self, said)


class TheAgentsRefusal(first.Update):
    """The agent's own: the job's error is the cause, the log the whole."""

    def test_a_refused_update_s_error_is_its_cause_and_its_log_the_whole(self):
        logged = []
        self.agent.log = logged.append
        other, _ = first.pair()
        _, added = first.pair()
        self.write(dict(first.RECORD, release_key=self.pub, release_spare=self.spare, release_also=[added]))
        for spec, cause in (({"sig": self.sign(other, first.digest(first.NEW))}, "its signature is under no key this node trusts"),
                            ({}, "the controller sent no signature with it")):
            (state, code), job = self.update(**spec)
            self.assertEqual((state, code), ("failed", 77))
            self.assertEqual(job.why, cause)
            reads_as_a_row(self, job.why)
            self.assertEqual(nodes.refusal_phrase(job.why), cause, "and the controller passes a cause through as it is")
            # The whole of it, for whoever reads the job's log or the node's.
            for whole in (job.said, logged[-1]):
                self.assertIn(f"refused: {cause}. This node takes only updates signed by the release key it pinned ({self.pub[:16]}…)", whole)
                self.assertIn("unsigned on allows unsigned builds", whole)
            self.assertEqual(self.installed(), b"OLD")

    def test_the_rule_s_refusal_carries_its_cause(self):
        ok, said = self.release.may_install({"release_key": self.pub}, first.digest(first.NEW), "", None)
        self.assertFalse(ok)
        self.assertEqual(said.cause, "the controller sent no signature with it")
        self.assertTrue(said.startswith("refused: the controller sent no signature with it. This node takes only updates signed by"))


class TheBell(unittest.TestCase):
    def test_the_row_is_made_of_the_phrase(self):
        with open(os.path.join(HERE, "..", "nodes.py"), encoding="utf-8") as f:
            text = f.read()
        self.assertIn('"failed": refusal_phrase(last.get("error") or "it failed")', text)
        self.assertIn('return refusal_phrase(last.get("error") or "it refused this build\'s signature")', text)
        with open(os.path.join(HERE, "..", "page-bell.js"), encoding="utf-8") as f:
            page = f.read()
        self.assertIn("its last update failed: ${esc(a.failed)}", page)
        self.assertIn("${esc(a.held)}", page)


for _name in dir(first.Update):
    if _name.startswith("test_") and _name not in vars(TheAgentsRefusal):
        setattr(TheAgentsRefusal, _name, None)

if __name__ == "__main__":
    unittest.main()
