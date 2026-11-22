"""A space's synced copy on a node, kept in step by a root agent for real
(R240 step 1; the audit of 13 Nov, and the regression of the same day).

The unit tier runs the controller's sync and the agent's end to end in one
process (unit/test_wssync.py), as an ordinary account, where doing a tree's
file work as its owner changes nothing. Here the agent is root and the tree
is an account's: what the sync writes is that account's, a link a session
planted where the sync writes reaches nothing of root's, the agent's own
records stay root's (a removal goes up from there: 0.9.438 wrote it as the
owner, was refused, and no removal reached the controller), and a folder
root left in the tree is handed to its owner and to nothing outside it."""
import io
import json
import os
import unittest
import urllib.parse
from unittest import mock

import world

import test_wssync as unit                                   # noqa: E402 (the unit tier's two halves and its stand-ins)

base = unit.AGENT.module("base")
unit.AGENT.log = lambda *a, **k: None
unit.AGENT.log_once = lambda *a, **k: None
NAME, UID, GID = world.account()
WHO = (UID, GID)


class Wire(unit.Wire):
    """The controller is another machine: its half of each call is root's
    here whoever the agent's thread is acting as, and what arrives is
    written on the node as the agent's own Controller writes it, DEST.part
    then into place, by whoever the thread is then."""

    def call(self, verb, body, timeout=0):
        with base.as_root():
            return super().call(verb, body, timeout)

    def fetch(self, path, dest, timeout=0):
        with base.as_root():
            code, why = super().fetch(path, self.spool, timeout)
            data = b""
            if code == 200:
                with open(self.spool, "rb") as f:
                    data = f.read()
        if code != 200:
            return code, why
        try:
            with open(dest + ".part", "wb") as f:
                f.write(data)
            os.replace(dest + ".part", dest)
        except OSError as e:
            return 0, str(e)
        return 200, ""

    def upload(self, path, src, timeout=0):
        try:
            with open(src, "rb") as f:
                body = f.read()
        except OSError as e:
            return 0, {"error": f"{type(e).__name__}: {e}"}
        q = urllib.parse.parse_qs(path.partition("?")[2], keep_blank_values=True)
        with base.as_root():
            out, code = unit.ctl_sync.put(self.nid, q["project"][0], q, io.BytesIO(body), len(body))
        return code, json.loads(json.dumps(out))


class Agent(unit.Agent):
    def __init__(self, nid, data, spool):
        super().__init__(nid, data)
        self.ctl = Wire(nid)
        self.ctl.spool = spool

    def session_account(self):
        return NAME


class Sync(unittest.TestCase):
    def setUp(self):
        self.w = world.World(self)
        top = self.w.top
        unit.db.configure(state=self.w.folder("state", mode=0o700))
        self.ws = self.w.folder("controller", mode=0o700)
        unit.write(f"{self.ws}/alpha/a.txt", "one\n")
        unit.write(f"{self.ws}/alpha/src/b.py", "print('b')\n")
        os.symlink("src/b.py", f"{self.ws}/alpha/b-link")
        unit.write(f"{self.ws}/alpha/.git/HEAD", "ref: refs/heads/main\n")
        unit.ctl_sync._index.clear()
        unit.ctl_sync._scanned.clear()
        unit.ctl_sync._conflicts.clear()
        unit.Nodes.hints.clear()
        unit.ctl_sync.configure(workspace=self.ws, nodes_module=unit.Nodes,
                                bound_nodes=lambda p: ["n1"] if p == "alpha" else [])
        unit.ctl_sync.configure_projects(lambda: ["alpha"])
        unit.ctl_sync.configure_reads(lambda p: [])
        # The node: its data store root's alone, its workspace a folder anybody passes through.
        self.data = self.w.folder("n1-data", mode=0o700)
        os.makedirs(os.path.join(self.data, "sync"), mode=0o700)
        self.root = self.w.folder("n1-workspace")
        self.tree = os.path.join(self.root, "alpha")
        self.sync = unit.node_sync.WorkspaceSync(Agent("n1", self.data, os.path.join(top, "state", "spool")), root=self.root)

    def turn(self, times=2):
        for _ in range(times):
            unit.ctl_sync._scanned.clear()
            mine = {p: r for n, p, r in unit.Nodes.hints if n == "n1"}
            unit.Nodes.hints[:] = [h for h in unit.Nodes.hints if h[0] != "n1"]
            if mine:
                self.sync.nudge(mine)
            self.sync.step()

    def down(self, times=3):
        """What the controller holds now, brought to the node."""
        unit.ctl_sync.changed("alpha")
        self.sync.nudge({"alpha": 0})
        self.turn(times)

    def session(self, fn):
        """Something a session does in the tree: as the account, as it would be."""
        with base.acting_as(WHO):
            fn()

    def owners(self, top):
        """{relative path: uid} of everything under `top`, links as themselves."""
        out = {".": os.lstat(top).st_uid}
        for d, dirs, files in os.walk(top):
            for name in (*dirs, *files):
                p = os.path.join(d, name)
                out[os.path.relpath(p, top)] = os.lstat(p).st_uid
        return out

    def test_the_copy_is_the_accounts_and_the_records_are_roots(self):
        self.turn()
        got = self.owners(self.tree)
        self.assertIn("src/b.py", got)
        self.assertEqual({k: v for k, v in got.items() if v != UID}, {}, "everything in the tree is its owner's")
        self.assertEqual({k: v for k, v in self.owners(self.data).items() if v != 0}, {}, "and the agent's records root's")
        self.assertEqual(self.w.intact(), "")

    def test_a_save_a_removal_and_a_link_go_up_and_a_change_comes_down(self):
        self.turn()
        at = lambda rel: os.path.join(self.tree, rel)          # noqa: E731

        def edits():
            unit.write(at("a.txt"), "two\n")
            unit.write(at("src/new.py"), "new\n")
            os.remove(at("src/b.py"))
            os.remove(at("b-link"))
            os.symlink("src/new.py", at("b-link"))
        self.session(edits)
        unit.write(f"{self.ws}/alpha/from-the-controller.txt", "down\n")
        self.down()
        self.assertEqual(unit.read(f"{self.ws}/alpha/a.txt"), "two\n")
        self.assertEqual(unit.read(f"{self.ws}/alpha/src/new.py"), "new\n")
        self.assertFalse(os.path.exists(f"{self.ws}/alpha/src/b.py"), "the removal reached the controller")
        self.assertEqual(os.readlink(f"{self.ws}/alpha/b-link"), "src/new.py")
        self.assertEqual(unit.read(at("from-the-controller.txt")), "down\n")
        self.assertEqual(os.lstat(at("from-the-controller.txt")).st_uid, UID)
        self.assertEqual({k: v for k, v in self.owners(self.data).items() if v != 0}, {})

    def test_a_link_planted_where_the_sync_writes_reaches_nothing_of_roots(self):
        self.turn()
        at = lambda rel: os.path.join(self.tree, rel)          # noqa: E731
        tmp = unit.node_sync.TMP

        def plant():
            os.symlink(self.w.secret, at(f"src/{tmp}new.py.part"))
            os.symlink(os.path.join(self.w.vault, "planted"), at(f"{tmp}top.txt.part"))
            os.symlink(self.w.secret, at(f"src/{tmp}other.py"))
        self.session(plant)
        for rel in ("src/new.py", "top.txt", "src/other.py"):
            unit.write(f"{self.ws}/alpha/{rel}", "from the controller\n")
        self.down()
        self.assertEqual(self.w.intact(), "")
        self.assertFalse(os.path.exists(at("src/new.py")), "refused as the account would be, not written through")
        self.assertFalse(os.path.exists(at("top.txt")))
        # A link at the file's own temporary name is replaced, not followed.
        self.assertEqual(unit.read(at("src/other.py")), "from the controller\n")
        # The links gone, the same files arrive.
        self.session(lambda: [os.remove(at(f"src/{tmp}new.py.part")), os.remove(at(f"{tmp}top.txt.part"))])
        self.down()
        self.assertEqual(unit.read(at("src/new.py")), "from the controller\n")
        self.assertEqual(unit.read(at("top.txt")), "from the controller\n")
        self.assertEqual(self.w.intact(), "")

    def test_a_folder_root_left_in_the_tree_is_handed_to_its_owner_alone(self):
        self.turn()
        at = lambda rel: os.path.join(self.tree, rel)          # noqa: E731
        # What a container that runs as root leaves: a folder the owner may
        # not write, and a link out of the tree beside it.
        os.mkdir(at("build"), 0o755)
        unit.write(at("build/made-by-a-container"), "x\n")
        os.symlink(self.w.vault, at("build/way-out"))
        unit.write(f"{self.ws}/alpha/build/out.txt", "built\n")
        with mock.patch.object(unit.node_sync, "CLAIM_EVERY", 0):
            self.down(times=4)
        self.assertEqual(unit.read(at("build/out.txt")), "built\n", "handed over, and the change tried again")
        got = self.owners(at("build"))
        self.assertEqual({k: v for k, v in got.items() if v != UID}, {})
        self.assertEqual(os.stat(self.w.vault).st_uid, 0, "the link is its owner's now; where it leads is not")
        self.assertEqual(self.w.intact(), "")


if __name__ == "__main__":
    unittest.main()
