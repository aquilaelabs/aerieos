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

    def test_the_projects_on_the_old_machine_run_on_this_one(self):
        d = tempfile.mkdtemp()
        aside, state = os.path.join(d, "aside"), os.path.join(d, "state")
        os.makedirs(aside)
        os.makedirs(state)
        db(os.path.join(aside, "builderbot.db"), [("n_here", "tower", True, "online")], [("t_here", "n_here")])
        db(os.path.join(state, "builderbot.db"), [("n_old", "oldbox", True, "online"), ("n_far", "draconis", False, "online")], [])
        with open(os.path.join(state, "claude-prefs.json"), "w") as f:
            json.dump({"projects": {"web": {"node": "n_old", "nodes": ["n_old", "n_far"]}, "api": {"node": "n_far", "nodes": ["n_far"]}}, "users": {}}, f)
        with open(os.path.join(state, "move.json"), "w") as f:
            json.dump({"nodes": ["n_old", "n_far"], "here_bare_metal": True}, f)
        said = move.carry_here(aside, state)
        p = json.load(open(os.path.join(state, "claude-prefs.json")))["projects"]
        self.assertEqual(p["web"], {"node": "n_here", "nodes": ["n_here", "n_far"]})
        self.assertEqual(p["api"], {"node": "n_far", "nodes": ["n_far"]})
        self.assertEqual(json.load(open(os.path.join(state, "move.json")))["nodes"], ["n_far"], "the old machine is not waited for")
        self.assertTrue(any("1 space that ran" in x for x in said), said)

    def test_a_container_install_has_no_machine_to_hand_on(self):
        # The old home ran in a container: a node it marked as its own is a
        # node like any other, never retired here, its spaces kept on it.
        d = tempfile.mkdtemp()
        aside, state = os.path.join(d, "aside"), os.path.join(d, "state")
        os.makedirs(aside)
        os.makedirs(state)
        db(os.path.join(aside, "builderbot.db"), [("n_here", "tower", True, "online")], [("t_here", "n_here")])
        db(os.path.join(state, "builderbot.db"), [("n_vm", "sandbox", True, "online")], [])
        with open(os.path.join(state, "claude-prefs.json"), "w") as f:
            json.dump({"projects": {"demo": {"node": "n_vm", "nodes": ["n_vm"]}}, "users": {}}, f)
        said = move.carry_here(aside, state, source_bare_metal=False)
        c = sqlite3.connect(os.path.join(state, "builderbot.db"))
        self.assertEqual(dict(c.execute("SELECT id, state FROM nodes").fetchall()), {"n_here": "online", "n_vm": "online"})
        self.assertEqual(json.load(open(os.path.join(state, "claude-prefs.json")))["projects"]["demo"]["node"], "n_vm")
        self.assertFalse(any("space" in x for x in said), said)

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
