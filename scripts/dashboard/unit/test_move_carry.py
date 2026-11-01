"""A controller moved onto a machine that already has its own node and a
stick's plan (move.carry_here, the operator 1 Nov): the machine's own node
and its tokens come across into the state put in place, the old home's own
node is retired there, the stick's plan is kept, and nothing the moved state
had of its own is replaced."""
import json
import os
import sqlite3
import sys
import tempfile
import unittest

sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)), ".."))
import move  # noqa: E402

SCHEMA = open(os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "migrations", "0001_init.sql")).read()


def db(path, nodes, tokens):
    c = sqlite3.connect(path)
    c.executescript(SCHEMA)
    for nid, name, own, state in nodes:
        c.execute("INSERT INTO nodes (id, name, kind, pool, created, state, concurrency, ssh_addr, capabilities, services, labels, agent, reported, routing, config) "
                  "VALUES (?, ?, 'agent', '', 1, ?, 1, '', '{}', '{}', '{}', '{}', '{}', '{}', ?)", (nid, name, state, json.dumps({"own": True} if own else {})))
    for tid, nid in tokens:
        c.execute("INSERT INTO tokens (id, kind, node_id, secret_hash, created, expires, revoked, uses) VALUES (?, 'node', ?, 'h', 1, NULL, 0, 0)", (tid, nid))
    c.commit()
    c.close()


class Carry(unittest.TestCase):
    def test_the_own_node_and_the_plan_come_across(self):
        d = tempfile.mkdtemp()
        aside, state = os.path.join(d, "aside"), os.path.join(d, "state")
        os.makedirs(aside)
        os.makedirs(state)
        db(os.path.join(aside, "builderbot.db"), [("n_here", "tower", True, "online")], [("t_here", "n_here")])
        db(os.path.join(state, "builderbot.db"), [("n_old", "oldbox", True, "online"), ("n_far", "draconis", False, "online")],
           [("t_far", "n_far")])
        open(os.path.join(aside, "firstboot.json"), "w").write('{"config": {"pools": []}}')
        said = move.carry_here(aside, state)
        c = sqlite3.connect(os.path.join(state, "builderbot.db"))
        rows = dict(c.execute("SELECT id, state FROM nodes").fetchall())
        toks = [r[0] for r in c.execute("SELECT id FROM tokens")]
        self.assertEqual(rows, {"n_here": "online", "n_old": "retired", "n_far": "online"})
        self.assertEqual(sorted(toks), ["t_far", "t_here"])
        self.assertTrue(os.path.isfile(os.path.join(state, "firstboot.json")))
        self.assertEqual(len(said), 2, said)

    def test_nothing_the_moved_state_has_is_replaced(self):
        d = tempfile.mkdtemp()
        aside, state = os.path.join(d, "aside"), os.path.join(d, "state")
        os.makedirs(aside)
        os.makedirs(state)
        db(os.path.join(aside, "builderbot.db"), [("n_same", "tower", True, "online")], [])
        db(os.path.join(state, "builderbot.db"), [("n_same", "tower-moved", False, "online")], [])
        open(os.path.join(state, "firstboot.json"), "w").write("kept")
        open(os.path.join(aside, "firstboot.json"), "w").write("other")
        move.carry_here(aside, state)
        c = sqlite3.connect(os.path.join(state, "builderbot.db"))
        self.assertEqual(c.execute("SELECT name FROM nodes WHERE id = 'n_same'").fetchone()[0], "tower-moved")
        self.assertEqual(open(os.path.join(state, "firstboot.json")).read(), "kept")


if __name__ == "__main__":
    unittest.main()
