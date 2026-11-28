"""A node's held poll waits on a lock of its own, not the store's:
it scans for work outside the wake's lock, a wake that lands while it
scans is not missed, and a job is handed over only while it is still queued."""
import os
import sys
import tempfile
import threading
import time
import unittest

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, os.path.join(HERE, ".."))
import db  # noqa: E402
import nodes  # noqa: E402


class HeldPoll(unittest.TestCase):
    def setUp(self):
        nodes.configure(state=tempfile.mkdtemp())
        mint = nodes.enroll_mint("user:test", "box")
        nodes.enroll(nodes.authenticate(mint["token"]), {"cpu": 2, "mem_mb": 4096, "arch": "x86_64",
                                                         "system": "linux", "session": {"up": True, "user": "b"}},
                     "10.0.0.5", user="bb")
        self.nid = mint["id"]

    def queue(self):
        return nodes.job_add("user:test", {"node": self.nid}, "system",
                             {"apply": "uninstall", "config": {}, "timeout": 900})["job"]

    def test_a_job_queued_while_the_poll_waits_is_handed_to_it_at_once(self):
        got = {}
        t = threading.Thread(target=lambda: got.update(j=nodes.job_next(self.nid, 20)))
        t.start()
        time.sleep(0.3)
        t0 = time.monotonic()
        jid = self.queue()
        t.join(10)
        self.assertEqual((got.get("j") or {}).get("id"), jid)
        self.assertLess(time.monotonic() - t0, 2.0)

    def test_a_waiting_poll_holds_nothing_of_the_store(self):
        t = threading.Thread(target=lambda: nodes.job_next(self.nid, 2))
        t.start()
        time.sleep(0.3)
        took = db._lock.acquire(timeout=0.5)
        if took:
            db._lock.release()
        t.join(10)
        self.assertTrue(took)

    def test_a_wake_while_it_scans_is_not_missed(self):
        # The first look finds nothing, and a job is queued (and its wake
        # sent) before the poll goes back to waiting: it looks again at once
        # rather than sleeping out its five seconds.
        real = nodes._job_next_scan
        queued = {}

        def first_empty(node_id, runner):
            if not queued:
                got = real(node_id, runner)
                queued["id"] = self.queue()
                return got
            return real(node_id, runner)
        nodes._job_next_scan = first_empty
        self.addCleanup(setattr, nodes, "_job_next_scan", real)
        t0 = time.monotonic()
        got = nodes.job_next(self.nid, 20)
        self.assertEqual((got or {}).get("id"), queued.get("id"))
        self.assertLess(time.monotonic() - t0, 2.0)

    def test_a_job_another_poll_took_meanwhile_is_not_handed_over(self):
        jid = self.queue()
        real = nodes._job_out

        def taken_meanwhile(row):
            # Another node's poll claims it between this one's read and its claim.
            nodes._exec("UPDATE jobs SET state = 'assigned', node = 'n_other' WHERE id = ?", (jid,))
            return real(row)
        nodes._job_out = taken_meanwhile
        self.addCleanup(setattr, nodes, "_job_out", real)
        self.assertIsNone(nodes.job_next(self.nid, 0))
        self.assertEqual((nodes.job(jid, with_log=False) or {}).get("node"), "n_other")


if __name__ == "__main__":
    unittest.main()
