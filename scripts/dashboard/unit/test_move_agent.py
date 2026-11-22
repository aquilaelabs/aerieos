"""A node following its controller to a new home (R90 step 12): the move
off the hello kept in node.json, the knock on the new address with the
node's own token, the answer checked against the challenge it holds, and
the controller re-adopted or the knock refused."""
import os
import sys
import unittest

sys.path.insert(0, os.path.join(os.path.dirname(__file__)))
import agentpkg  # noqa: E402


class Knock(unittest.TestCase):
    def setUp(self):
        self.agent = agentpkg.load("aerieos_agent_move")
        self.mod = sys.modules[self.agent.Agent.__module__]
        self.saved = []
        self.mod.save_state = lambda st: self.saved.append(dict(st))
        self.a = object.__new__(self.agent.Agent)
        self.a.state = {"controller": "https://old.example", "token": "tok", "pin": "", "node_id": "n_1",
                        "move": {"url": "https://new.example", "expect": "c" * 64}}
        self.a.quiet = 0
        self.a.hello_at = 1
        self.a.ctl = None

    def fake(self, status, answer, url="", pin=""):
        calls = []

        class Ctl:
            def __init__(self, u, token, p=""):
                calls.append((u, token, p))

            def call(self, verb, body=None, timeout=30, **kw):
                calls.append((verb, body))
                return status, {"answer": answer, "url": url, "pin": pin}
        self.mod.Controller = Ctl
        return calls

    def test_the_right_answer_moves_the_node(self):
        calls = self.fake(200, "c" * 64, url="https://new.example/", pin="AA:BB")
        self.assertTrue(self.a.knock())
        self.assertEqual(calls[0], ("https://new.example", "tok", ""), "knocked with the node's own token, no pin yet")
        self.assertEqual(calls[1], ("moved", {"node": "n_1"}))
        self.assertEqual((self.a.state["controller"], self.a.state["pin"]), ("https://new.example", "AA:BB"))
        self.assertNotIn("move", self.a.state)
        self.assertTrue(self.saved and self.saved[-1]["controller"] == "https://new.example")
        self.assertEqual(self.a.hello_at, 0, "a hello to the new home comes next")

    def test_a_token_the_new_home_never_saw_is_taken_back_by_an_older_one(self):
        # B935: a hello after the bundle was packed handed this node a token
        # the new home does not know; it holds the one before among its past.
        self.a.state.update(token="bbn_new", past_tokens=[["bbn_old", 1]])
        calls, answers = [], iter([(401, {"error": "unknown token"}),
                                   (200, {"ok": True, "token": "bbn_fresh"}),
                                   (200, {"answer": "c" * 64, "url": "", "pin": ""})])

        class Ctl:
            seen_pin = "sha256:seen"

            def __init__(self, u, token, p=""):
                self.token = token
                calls.append((u, token, p))

            def call(self, verb, body=None, timeout=30, **kw):
                calls.append((verb, body, self.token))
                return next(answers)
        self.mod.Controller = Ctl
        self.assertTrue(self.a.knock())
        self.assertEqual(calls[2], ("recover", {"node": "n_1", "tokens": ["bbn_new", "bbn_old"]}, "bbn_new"),
                         "its newest first, then the month's past")
        self.assertEqual(calls[3], ("moved", {"node": "n_1"}, "bbn_fresh"), "knocked again with the token taken back")
        self.assertEqual((self.a.state["token"], self.a.state["past_tokens"][0][0]), ("bbn_fresh", "bbn_new"))
        # B936: no address in the answer keeps the one knocked at, pinned to
        # the certificate met there.
        self.assertEqual((self.a.state["controller"], self.a.state["pin"]), ("https://new.example", "sha256:seen"))

    def test_a_knock_no_token_takes_back_says_where_the_line_is(self):
        self.a.state.update(token="bbn_new", past_tokens=[])

        class Ctl:
            def __init__(self, u, token, p=""):
                self.token = token

            def call(self, verb, body=None, timeout=30, **kw):
                return 401, {"error": "unknown token"}
        self.mod.Controller = Ctl
        ok, why = self.mod.follow(self.a.state)
        self.assertFalse(ok)
        self.assertIn("run the line its Nodes page gives it there", why)

    def test_a_wrong_or_missing_answer_leaves_the_node_where_it_is(self):
        self.fake(200, "d" * 64)
        self.assertFalse(self.a.knock())
        self.assertEqual(self.a.state["controller"], "https://old.example")
        self.fake(404, "")
        self.assertFalse(self.a.knock())
        self.a.state.pop("move")
        self.assertFalse(self.a.knock(), "nothing to knock on")

    def test_a_late_node_takes_the_challenge_the_moved_answer_carries(self):
        # R175 step 2: a node that never heard the move while it was armed
        # hears it in the old controller's "moved" answer, and knocks.
        self.a.state.pop("move")
        self.assertFalse(self.a.move_hint({"url": "https://new.example"}), "no challenge, nothing taken")
        self.assertTrue(self.a.move_hint({"url": "https://new.example", "expect": "e" * 64}))
        self.assertEqual(self.a.state["move"], {"url": "https://new.example", "expect": "e" * 64})
        self.assertFalse(self.a.move_hint({"url": "https://other.example", "expect": "f" * 64}), "one held is kept")
        self.fake(200, "e" * 64, url="https://new.example/")
        self.assertTrue(self.a.knock())
        self.assertEqual(self.a.state["controller"], "https://new.example")

    def test_follow_by_hand_and_the_state_read_again(self):
        # R175 step 3: the follow verb's knock with a line's url and
        # challenge, and the running agent re-reading node.json while its
        # controller stays quiet.
        self.a.state.pop("move")
        calls = self.fake(200, "g" * 64, url="https://new.example/", pin="CC:DD")
        ok, why = self.mod.follow(self.a.state, "https://new.example", "g" * 64)
        self.assertTrue(ok, why)
        self.assertEqual(calls[1], ("moved", {"node": "n_1"}))
        self.assertEqual((self.a.state["controller"], self.a.state["pin"]), ("https://new.example", "CC:DD"))
        self.assertFalse(self.mod.follow({"token": "t"}, "", "")[0], "nothing to knock on")
        self.a.state = {"controller": "https://old.example", "token": "tok", "pin": "", "node_id": "n_1"}
        self.mod.load_state = lambda: {"controller": "https://new.example", "token": "tok", "pin": "EE:FF"}
        self.assertTrue(self.a.reread_state())
        self.assertEqual((self.a.state["controller"], self.a.state["pin"], self.a.hello_at), ("https://new.example", "EE:FF", 0))
        self.assertFalse(self.a.reread_state(), "the same controller: nothing to take")


if __name__ == "__main__":
    unittest.main()
