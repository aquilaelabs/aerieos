"""The agent's record in memory, changed by its threads while it is saved
(the leftovers audit, 21 Nov). The census thread, the job threads and the
configuration plane change node.json's copy while the loop saves it, and
the dump hid the race behind twenty tries with a sleep between them. Every
change now takes one lock (stores.STATE_LOCK, which State takes for each of
its own), save_state holds it from reading the console's keys in to writing
the file, and a change its caller holds the lock around lands whole in
every save: a new token is never written over by a save of the old."""
import json
import os
import shutil
import tempfile
import threading
import time
import unittest
from types import SimpleNamespace
from unittest import mock

import agentpkg


class Case(unittest.TestCase):
    def setUp(self):
        self.agent = agentpkg.load("state_lock")
        self.agent.log = lambda *a, **k: None
        self.stores = self.agent.module("stores")
        self.d = tempfile.mkdtemp()
        self.addCleanup(shutil.rmtree, self.d, True)
        self.nj = os.path.join(self.d, "node.json")
        with open(self.nj, "w") as f:
            json.dump({"node_id": "n_1", "token": "bbn_1", "controller": "http://ctl:7680", "release_key": "ab" * 32}, f)
        self.agent.NODE_JSON = self.nj

    def read(self):
        with open(self.nj) as f:
            return json.load(f)

    def free(self):
        """Whether another thread could take the lock now."""
        got = []
        L = self.stores.STATE_LOCK
        t = threading.Thread(target=lambda: got.append(L.acquire(timeout=0) and (L.release() or True)))
        t.start()
        t.join()
        return got[0]


class Lock(Case):
    def test_the_running_agent_holds_its_record_as_a_state(self):
        st = self.stores.load_state()
        self.assertIsInstance(st, self.stores.State)
        self.assertIsInstance(st, dict)
        self.assertEqual(st["node_id"], "n_1")
        self.assertFalse(hasattr(self.stores, "_dumps"), "no tries and no sleep: the dump is taken under the lock")

    def test_every_change_waits_for_the_lock(self):
        st = self.stores.load_state()
        changes = {"set": lambda: st.__setitem__("a", 1), "del": lambda: st.__delitem__("controller"),
                   "pop": lambda: st.pop("token", None), "popitem": st.popitem, "setdefault": lambda: st.setdefault("c", 3),
                   "update": lambda: st.update(b=2), "|=": lambda: st.__ior__({"d": 4}), "clear": st.clear, "copy": st.copy}
        for name, change in changes.items():
            st.update(node_id="n_1", token="bbn_1", controller="http://ctl:7680")
            held, let_go, done = threading.Event(), threading.Event(), threading.Event()

            def hold(held=held, let_go=let_go):
                with self.stores.STATE_LOCK:
                    held.set()
                    let_go.wait(5)
            t = threading.Thread(target=hold)
            t.start()
            held.wait(5)
            w = threading.Thread(target=lambda c=change, done=done: (c(), done.set()))
            w.start()
            self.assertFalse(done.wait(0.1), f"{name} waited for the lock")
            let_go.set()
            t.join(5)
            w.join(5)
            self.assertTrue(done.is_set(), name)
        self.assertIs(type(st.copy()), dict, "a copy is a plain dict")

    def test_the_dump_and_the_write_are_under_the_lock(self):
        st = self.stores.load_state()
        seen = []
        dumps = json.dumps

        def watched(obj, **kw):
            seen.append(self.free())
            return dumps(obj, **kw)
        with mock.patch.object(self.stores.json, "dumps", watched):
            self.stores.save_state(st)
        self.assertEqual(seen, [False])
        self.assertTrue(self.free())

    def test_threads_that_change_the_record_while_it_is_saved(self):
        st = self.stores.load_state()
        stop, errors = threading.Event(), []

        def churn(i):
            n = 0
            while not stop.is_set():
                n += 1
                try:
                    # The record grows and shrinks under the dump...
                    st[f"k{i}_{n % 40}"] = {"n": n, "list": list(range(n % 30))}
                    st.pop(f"k{i}_{(n + 20) % 40}", None)
                    # ...and a change made as one step goes in whole.
                    with self.stores.STATE_LOCK:
                        st["pair_a"] = n
                        st["pair_b"] = n
                except Exception as e:                       # noqa: BLE001 (what the test counts)
                    errors.append(e)
        threads = [threading.Thread(target=churn, args=(i,)) for i in range(4)]
        for t in threads:
            t.start()
        saved = []
        try:
            for _ in range(150):
                self.stores.save_state(st)
                saved.append(self.read())
        finally:
            stop.set()
            for t in threads:
                t.join(5)
        self.assertEqual(errors, [])
        self.assertEqual(len(saved), 150)
        self.assertTrue(all(s.get("pair_a") == s.get("pair_b") for s in saved), "a change made as one step lands whole")
        self.assertTrue(all(s["release_key"] == "ab" * 32 and s["node_id"] == "n_1" for s in saved))

    def test_a_new_token_is_never_written_over_by_a_save_of_the_old(self):
        a = object.__new__(self.agent.Agent)
        a.state, a.ctl = self.stores.load_state(), SimpleNamespace(token="bbn_1")
        real, started, go = self.stores._save, threading.Event(), threading.Event()

        def slow(state, console, d):
            if state.get("token") == "bbn_2" and not started.is_set():
                started.set()
                go.wait(5)
            real(state, console, d)
        with mock.patch.object(self.stores, "_save", slow):
            t = threading.Thread(target=a.take_token, args=("bbn_2",))
            t.start()
            started.wait(5)
            # Another thread's save of the record while the new token is
            # being written: it waits, and then saves the record holding it.
            other = threading.Thread(target=self.stores.save_state, args=(a.state,))
            other.start()
            time.sleep(0.1)
            self.assertTrue(other.is_alive(), "the other save waits for the token's change")
            go.set()
            t.join(5)
            other.join(5)
        self.assertEqual((self.read()["token"], a.state["token"], a.ctl.token), ("bbn_2", "bbn_2", "bbn_2"))
        self.assertEqual(self.read()["past_tokens"][0][0], "bbn_1")


if __name__ == "__main__":
    unittest.main()
