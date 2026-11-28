"""A burst of asks keeps the ones still waiting.

The ask list kept the newest twenty whatever their state, and every phone
use is an ask, auto-allowed ones too: twenty phone operations from one
session dropped another session's root ask from the bell before anybody had
answered it, and its verb ended 'no such request'. Now every ask still
waiting or running stays, and of those that are over the newest twenty."""
import os
import sys
import unittest

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))
import phone  # noqa: E402


class Burst(unittest.TestCase):
    def setUp(self):
        self.was = list(phone._reqs)
        phone._reqs.clear()

    def tearDown(self):
        phone._reqs[:] = self.was

    def ask(self, kind="root"):
        return phone._queue(kind, "a reason", ["true"], "n_1", "box", "alpha", "claude", "u1", "Owner")["id"]

    def test_a_root_ask_outlives_thirty_phone_uses_after_it(self):
        waiting = self.ask("root")
        for _ in range(30):
            rid = self.ask("phone")
            with phone._lock:
                next(r for r in phone._reqs if r["id"] == rid).update(state="done", code=0)
        # The list is cut as an ask comes in.
        last = self.ask("phone")
        ids = [r["id"] for r in phone._reqs]
        self.assertIn(waiting, ids, "still waiting for its answer: kept")
        self.assertIn(last, ids)
        over = [r for r in phone._reqs if r["state"] == "done"]
        self.assertEqual(len(over), phone.MAX_REQS, "the newest twenty of those that are over")
        self.assertEqual(over[-1]["id"], last - 1)

    def test_a_runaway_of_waiting_asks_is_still_bounded(self):
        for _ in range(phone.MAX_LIVE + 5):
            self.ask("root")
        self.assertEqual(len(phone._reqs), phone.MAX_LIVE)


if __name__ == "__main__":
    unittest.main()
