"""While a landing replaces the state, no other thread's state file lands in
it: refused at once, never held, since a writer made to wait
while holding its module's lock would stop the landing. The landing's own
thread writes; a folder elsewhere is untouched; a landing that put the old
state back lets the writers go on."""
import os
import sys
import tempfile
import threading
import unittest

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))
import statefile  # noqa: E402


def in_thread(fn):
    out = []
    def run():
        try:
            out.append(fn())
        except Exception as e:      # noqa: BLE001 (the test reads what was raised)
            out.append(e)
    t = threading.Thread(target=run)
    t.start()
    t.join()
    return out[0]


class Latch(unittest.TestCase):
    def setUp(self):
        self.state, self.other = tempfile.mkdtemp(), tempfile.mkdtemp()
        self.addCleanup(statefile.landing_over)

    def test_another_thread_is_refused_and_the_lander_writes(self):
        f = os.path.join(self.state, "users.json")
        statefile.write_json(f, {"was": 1})
        statefile.landing_begins(self.state)
        got = in_thread(lambda: statefile.write_json(f, {"old": "controller"}))
        self.assertIsInstance(got, statefile.Landing)
        self.assertIn("being replaced", str(got))
        got = in_thread(lambda: statefile.write_text(os.path.join(self.state, "sub", "note.txt"), "x"))
        self.assertIsInstance(got, statefile.Landing, "a folder under it too")
        self.assertEqual(open(f).read().strip(), '{\n  "was": 1\n}')
        self.assertEqual([n for n in os.listdir(self.state) if n.endswith(".tmp")], [], "and it left no temporary behind")
        statefile.write_json(f, {"new": "state"})          # the landing's own thread
        self.assertIn('"new"', open(f).read())

    def test_a_folder_elsewhere_is_not_held(self):
        statefile.landing_begins(self.state)
        self.assertIsNone(in_thread(lambda: statefile.write_json(os.path.join(self.other, "a.json"), {})))

    def test_the_old_state_back_lets_writers_go_on(self):
        f = os.path.join(self.state, "users.json")
        statefile.landing_begins(self.state)
        statefile.landing_over()
        self.assertIsNone(in_thread(lambda: statefile.write_json(f, {"on": 1})))


if __name__ == "__main__":
    unittest.main()
