"""A session's bb waits for its node's synced copy: up before a
relayed verb acts on the controller's copy, down after it changed it."""
import json
import os
import shutil
import sys
import tempfile
import threading
import time
import unittest

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, os.path.join(HERE, "..", "..", "lib"))
import syncwait  # noqa: E402


class Wait(unittest.TestCase):
    def setUp(self):
        self.ws = tempfile.mkdtemp()
        os.makedirs(os.path.join(self.ws, "alpha", ".git"))
        self.f = os.path.join(self.ws, "alpha", ".git", ".bbsync-state")
        self.env = os.environ.get("WORKSPACE")
        os.environ["WORKSPACE"] = self.ws
        syncwait.UP_S = syncwait.DOWN_S = 2

    def tearDown(self):
        shutil.rmtree(self.ws, ignore_errors=True)
        if self.env is None:
            os.environ.pop("WORKSPACE", None)
        else:
            os.environ["WORKSPACE"] = self.env

    def say(self, **kw):
        with open(self.f, "w") as fh:
            json.dump({"rev": 1, "pending": 0, "started": time.time(), "ready": True, "error": ""} | kw, fh)

    def later(self, s, **kw):
        t = threading.Timer(s, lambda: self.say(**kw))
        t.start()
        return t

    def test_no_synced_copy_is_nothing_to_wait_for(self):
        self.assertTrue(syncwait.up("beta"))
        self.assertTrue(syncwait.down("beta", 9))

    def test_up_waits_for_a_tick_that_began_after_it_was_asked(self):
        self.say(started=time.time() - 5)
        t = self.later(0.5)
        began = time.time()
        self.assertTrue(syncwait.up("alpha"))
        self.assertGreater(time.time() - began, 0.4)
        t.join()

    def test_up_is_not_done_while_something_waits_to_go_up(self):
        self.say(pending=2, error="alpha/a.txt: ConnectionRefusedError")
        self.assertFalse(syncwait.up("alpha"))

    def test_up_goes_on_waiting_while_the_copy_is_moving(self):
        # A minute's wait failed a push with thousands of changes
        # still going up; each fall in what is left buys another UP_S.
        syncwait.UP_S, syncwait.MOVING_S = 1, 10
        self.addCleanup(setattr, syncwait, "MOVING_S", 600)
        self.say(pending=30, started=time.time() - 5)
        ts = [self.later(0.6, pending=20, started=time.time() - 5), self.later(1.4, pending=10, started=time.time() - 5),
              self.later(2.2, pending=0)]
        began = time.time()
        self.assertTrue(syncwait.up("alpha"), "it was still moving, so the wait went past UP_S and saw it finish")
        self.assertGreater(time.time() - began, 2.0)
        for t in ts:
            t.join()

    def test_up_gives_up_once_the_copy_stops_moving(self):
        syncwait.UP_S, syncwait.MOVING_S = 1, 10
        self.addCleanup(setattr, syncwait, "MOVING_S", 600)
        self.say(pending=30, started=time.time() - 5)
        t = self.later(0.5, pending=25, started=time.time() - 5)
        began = time.time()
        self.assertFalse(syncwait.up("alpha"))
        self.assertLess(time.time() - began, 3, "one fall bought one more UP_S, and then it stood still")
        t.join()

    def test_down_waits_for_the_revision(self):
        self.say(rev=3)
        t = self.later(0.5, rev=5)
        self.assertTrue(syncwait.down("alpha", 5))
        t.join()
        self.assertFalse(syncwait.down("alpha", 9))


if __name__ == "__main__":
    unittest.main()
