"""A verb waiting on an ask rides out a read nothing answered.

waits.outcome polls the ask once a second; one read that timed out ended
the verb with a bare 'The read operation timed out', exit 0, and nothing
said of the ask. A silent read is asked again now, a minute's worth in a
row, and a verb that gives up says the ask was made and its number."""
import os
import sys
import unittest
from unittest import mock

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, os.path.join(HERE, "..", "..", "lib"))
import waits  # noqa: E402


class RideOut(unittest.TestCase):
    def test_a_silent_read_is_asked_again(self):
        answers = iter([(None, {"error": "The read operation timed out"}), (None, {"error": "timed out"}),
                        (200, {"state": "waiting"}), (200, {"state": "done", "code": 0, "out": "ok"})])
        with mock.patch.object(waits.time, "sleep", lambda s: None), \
             mock.patch.object(waits.bbapi, "request", lambda *a, **k: next(answers)):
            self.assertEqual(waits.outcome("", 7, "denied")["out"], "ok")

    def test_a_controller_gone_quiet_ends_the_wait_saying_the_ask_was_made(self):
        with mock.patch.object(waits.time, "sleep", lambda s: None), \
             mock.patch.object(waits.bbapi, "request", lambda *a, **k: (None, {"error": "timed out"})), \
             self.assertRaises(SystemExit) as e:
            waits.outcome("", 7, "denied")
        self.assertIn("ask #7 was made", str(e.exception.code))


if __name__ == "__main__":
    unittest.main()
