"""The token before the last rotation tried when the controller does not
know the newest (B655): written to node.json first, taken for the next
call, once per rotation, and nothing to go back to without a rotation."""
import os
import sys
import unittest
from unittest import mock

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, os.path.join(HERE, "..", "..", "agent"))
from aerieos_agent import agent as agentmod  # noqa: E402


class Ctl:
    def __init__(self, token):
        self.token = token


def bare(token, prev=None):
    a = agentmod.Agent.__new__(agentmod.Agent)
    a.state = {"token": token, "node_id": "n_1"}
    a.ctl = Ctl(token)
    if prev is not None:
        a.prev_token = (prev, 0.0)
    return a


class TokenBack(unittest.TestCase):
    def test_the_token_before_is_taken_once(self):
        a, kept = bare("bbn_new", "bbn_old"), []
        with mock.patch.object(agentmod, "save_state", kept.append), mock.patch.object(agentmod, "log"):
            self.assertTrue(a.token_back())
            self.assertEqual(kept[-1]["token"], "bbn_old", "written before it is used")
            self.assertEqual((a.state["token"], a.ctl.token), ("bbn_old", "bbn_old"))
            self.assertFalse(a.token_back(), "once per rotation: the second refusal is a real one")

    def test_nothing_to_go_back_to_without_a_rotation(self):
        a = bare("bbn_only")
        with mock.patch.object(agentmod, "save_state"), mock.patch.object(agentmod, "log"):
            self.assertFalse(a.token_back())
        a = bare("bbn_same", "bbn_same")
        with mock.patch.object(agentmod, "save_state"), mock.patch.object(agentmod, "log"):
            self.assertFalse(a.token_back())

    def test_a_write_that_fails_keeps_the_newest(self):
        a = bare("bbn_new", "bbn_old")
        with mock.patch.object(agentmod, "save_state", side_effect=OSError(30, "read-only")), mock.patch.object(agentmod, "log"):
            self.assertFalse(a.token_back())
        self.assertEqual(a.state["token"], "bbn_new")




class Recovered(unittest.TestCase):
    """A controller restored from a backup (the operator, 6 Nov): the node
    keeps a month of its tokens, newest first, and offers them a chunk a call
    until the controller answers with a fresh one."""
    def test_each_rotation_keeps_the_one_before_and_a_month_alone(self):
        a = bare("bbn_1")
        a.state["past_tokens"] = [["bbn_ancient", 1]]
        with mock.patch.object(agentmod, "save_state"), mock.patch.object(agentmod, "log"):
            a.take_token("bbn_2")
            a.take_token("bbn_3")
        self.assertEqual([p[0] for p in a.state["past_tokens"]], ["bbn_2", "bbn_1"], "newest first, the month's alone")

    def test_the_past_is_offered_a_chunk_a_call_until_one_is_taken(self):
        a = bare("bbn_newest")
        a.state["past_tokens"] = [[f"bbn_{i}", 2000000000] for i in range(450)]
        calls = []

        def call(verb, body, timeout=30):
            calls.append((verb, len(body["tokens"]), body["node"]))
            return (200, {"ok": True, "token": "bbn_fresh"}) if len(calls) == 3 else (401, {"error": "unknown token"})
        a.ctl.call = call
        with mock.patch.object(agentmod, "save_state"), mock.patch.object(agentmod, "log"):
            self.assertTrue(a.recover_token())
        self.assertEqual(calls, [("recover", 200, "n_1"), ("recover", 200, "n_1"), ("recover", 50, "n_1")])
        self.assertEqual(a.state["token"], "bbn_fresh")
        a.ctl.call = lambda *x, **k: (0, {"error": "no answer"})
        with mock.patch.object(agentmod, "save_state"), mock.patch.object(agentmod, "log"):
            self.assertFalse(a.recover_token(), "no answer is not a refusal: tried again later")

if __name__ == "__main__":
    unittest.main()
