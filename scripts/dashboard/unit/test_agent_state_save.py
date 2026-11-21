"""node.json saved from many threads at once is always whole JSON, holds the
last save, and leaves no temporary file beside it: two saves through one
fixed .tmp could interleave into a file no start reads, and the node had to
be enrolled again at its console."""
import json
import os
import tempfile
import threading
import unittest
import agentpkg  # noqa: E402

agent = agentpkg.load("aerieos_agent")
stores = agent.module("stores")


class Saves(unittest.TestCase):
    def setUp(self):
        self.d = tempfile.mkdtemp()
        self.path = os.path.join(self.d, "node.json")
        self.was = stores.NODE_JSON
        stores.NODE_JSON = self.path

    def tearDown(self):
        stores.NODE_JSON = self.was

    def test_many_threads_saving_at_once_leave_one_whole_file(self):
        state = stores.State({"node_id": "n_1", "token": "bbn_0", "jobs": {}})
        bad = []

        def saver(i):
            for k in range(40):
                state["token"] = f"bbn_{i}_{k}"
                # Changed while another walks it: a value inside the record
                # changed in place takes the record's lock as its own do.
                with stores.STATE_LOCK:
                    state["jobs"][f"{i}-{k}"] = k
                try:
                    stores.save_state(state)
                except Exception as e:                  # noqa: BLE001
                    bad.append(repr(e))
        ts = [threading.Thread(target=saver, args=(i,)) for i in range(8)]
        for t in ts:
            t.start()
        for t in ts:
            t.join()
        self.assertEqual(bad, [])
        with open(self.path) as f:
            got = json.load(f)
        self.assertEqual(got["node_id"], "n_1")
        self.assertEqual(len(got["jobs"]), 8 * 40)
        self.assertEqual(sorted(n for n in os.listdir(self.d) if n != ".node.json.lock"), ["node.json"],
                         "no temporary file is left beside it")
        self.assertEqual(oct(os.stat(self.path).st_mode & 0o777), "0o600")

    def test_a_save_that_fails_leaves_the_file_as_it_was_and_no_temporary(self):
        stores.save_state({"node_id": "n_1", "token": "bbn_a"})

        class Odd:
            pass
        with self.assertRaises(TypeError):
            stores.save_state({"node_id": "n_1", "token": Odd()})
        with open(self.path) as f:
            self.assertEqual(json.load(f)["token"], "bbn_a")
        self.assertEqual(sorted(n for n in os.listdir(self.d) if n != ".node.json.lock"), ["node.json"])


if __name__ == "__main__":
    unittest.main()
