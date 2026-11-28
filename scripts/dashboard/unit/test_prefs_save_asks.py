"""What a save of a space's settings asks of the person saving is a table
(prefs.SAVE_ASKS): each row a change, what it asks and what it refuses.
server.py's handler walks it and holds no permission of its own, and the
route record's names for /api/prefs are read off it. Here the table is
walked as the handler walks it, a change at a time."""
import ast
import json
import os
import shutil
import sys
import tempfile
import unittest
from pathlib import Path

HERE = os.path.dirname(os.path.abspath(__file__))
DASH = os.path.normpath(os.path.join(HERE, ".."))
sys.path.insert(0, DASH)
sys.path.insert(0, os.path.normpath(os.path.join(DASH, "..", "lib")))
import prefs  # noqa: E402
import registry  # noqa: E402
import repos  # noqa: E402
import routegates  # noqa: E402


def write_json(p, d, mode=0o644):
    Path(p).write_text(json.dumps(d))


class Asks(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.mkdtemp()
        self.addCleanup(shutil.rmtree, self.tmp, True)
        ws = Path(self.tmp) / "ws"
        for n in ("app", "lib"):
            (ws / n).mkdir(parents=True)
        registry.configure(state=self.tmp, workspace=ws, write_json=write_json)
        registry.sync()
        repos.configure(state=self.tmp, write_json=write_json, registry=registry, workspace=ws)
        prefs.configure(write_json=write_json, state=self.tmp)
        prefs.configure_repos(project_of=repos.project_of, members=repos.members, is_repos=registry.is_repos)
        self.nodes = {"n1": {"name": "one", "agent": {"addr": "10.0.0.5"}}, "n2": {"name": "two", "state": "disabled"},
                      "h1": {"name": "host"}}
        self.up, self.debug, self.told = True, True, []
        was = {k: getattr(prefs, k) for k in ("WORKSPACE", "pin_instances", "end_agents", "net_nudge", "node_of", "host_only", "nodes_up",
                                              "debug_available", "held_changed")}
        self.addCleanup(lambda: prefs.__dict__.update(was, _repos=None))
        prefs.configure_dialog(WORKSPACE=ws, pin_instances=lambda name: [], end_agents=lambda *a, **k: None,
                               net_nudge=lambda: self.told.append("net"), node_of=self.nodes.get, host_only=lambda n: n == "h1",
                               nodes_up=lambda: self.up, debug_available=lambda: self.debug, held_changed=lambda: self.told.append("held"))

    def walk(self, req, allowed=True):
        """The rows this save meets, as the handler meets them: [(ask, the
        nodes it is asked of)], and the first refusal a row made."""
        met = []
        for ask, changes, on, fits in prefs.SAVE_ASKS:
            if not changes("app", req):
                continue
            if ask:
                met.append((ask, on("app", req) if on else None))
            if fits and (no := fits("app", req)):
                return met, no
        return met, None

    def test_a_save_that_changes_nothing_asks_nothing(self):
        cur = prefs.get("app")
        same = {"project": "app", **{k: cur[k] for k in ("node", "nodes", "hosts", "reads", "sees", "reaches", "devbuild", "installpacks",
                                                         "makevms", "vm_caps", "kube", "discord", "diag", "log_from", "build")}}
        met, no = self.walk(same)
        self.assertEqual((met, no), ([], None))
        # ...and what is the asker's own on the space is anybody's on it.
        self.assertEqual(self.walk({"project": "app", "model": "opus", "git_name": "A"}), ([], None))

    def test_each_change_asks_what_is_its_own(self):
        for req, want in (
                ({"node": "n1"}, [("node", ["n1"]), ("space:settings", None)]),
                ({"nodes": ["n1"], "node": "n1"}, [("node", ["n1", "n1"]), ("space:settings", None)]),
                ({"hosts": ["h1"]}, [("node", ["h1"]), ("space:settings", None)]),
                ({"reads": ["lib"]}, [("owner", None), ("space:settings", None)]),
                ({"sees": ["/mnt/x"]}, [("node", [""]), ("space:settings", None)]),
                ({"reaches": ["10.9.9.9:443"]}, [("nodes-write", None), ("space:settings", None)]),
                ({"diag": True}, [("debug", None), ("space:settings", None)]),
                ({"log_from": ["n1"]}, [("debug", None), ("space:settings", None)]),
                ({"devbuild": "ask"}, [("docker-write", None), ("space:settings", None)]),
                ({"installpacks": "auto"}, [("curate", None), ("space:settings", None)]),
                ({"makevms": "ask"}, [("space:vms-write", None), ("space:settings", None)]),
                ({"vm_caps": {"count": 9, "vcpus": 8, "mem_mb": 16384, "disk_gb": 200}}, [("space:vms-write", None), ("space:settings", None)]),
                ({"kube": "ask"}, [("space:deploy", None), ("space:settings", None)]),
                ({"discord": "ask"}, [("space:settings", None), ("space:settings", None)]),
                ({"build": "make"}, [("space:settings", None)])):
            met, no = self.walk({"project": "app", **req})
            self.assertEqual((met, no), (want, None), req)

    def test_a_node_that_only_hosts_or_is_disabled_holds_no_space(self):
        _, no = self.walk({"project": "app", "node": "h1"})
        self.assertEqual(no[1], 400)
        self.assertIn("host hosts containers only", no[0]["error"])
        _, no = self.walk({"project": "app", "nodes": ["n1", "n2"], "node": "n1"})
        self.assertEqual((no[1], no[0]["error"]), (400, "two is disabled on the Nodes page: Enable it there first"))
        # Sent with the value it has, a node is still looked at: the dialog
        # sends it on every save, and a node disabled since is said.
        prefs.set_prefs("app", node="n1", workspace=prefs.WORKSPACE)
        self.nodes["n1"]["state"] = "disabled"
        met, no = self.walk({"project": "app", "node": "n1"})
        self.assertEqual(met, [])
        self.assertIn("one is disabled", no[0]["error"])
        # With no node store, nothing of a node is known to refuse.
        self.up = False
        self.assertIsNone(self.walk({"project": "app", "node": "h1"})[1])

    def test_a_hosting_node_must_be_one_and_an_address_is_never_the_node_itself(self):
        met, no = self.walk({"project": "app", "hosts": ["n1"]})
        self.assertEqual(met, [("node", ["n1"])], "asked before it is refused")
        self.assertIn("one is not a hosting-only node", no[0]["error"])
        prefs.set_prefs("app", nodes=["n1"], node="n1", workspace=prefs.WORKSPACE)
        met, no = self.walk({"project": "app", "reaches": ["10.0.0.5:8080"]})
        self.assertEqual(met, [("nodes-write", None)])
        self.assertEqual((no[1], no[0]["error"][:28]), (400, "10.0.0.5:8080 is one itself:"))
        self.assertIsNone(self.walk({"project": "app", "reaches": ["10.0.0.6:8080"]})[1])

    def test_a_debug_grant_is_refused_where_debug_mode_cannot_be_on_before_anybody_is_asked(self):
        self.debug = False
        met, no = self.walk({"project": "app", "diag": True})
        self.assertEqual((met, no), ([], ({"error": "the debug options are not available on this controller"}, 403)))
        # A grant taken off is always allowed.
        self.debug = True
        prefs.set_prefs("app", diag=True, workspace=prefs.WORKSPACE)
        self.debug = False
        self.assertEqual(self.walk({"project": "app", "diag": False}), ([("debug", None), ("space:settings", None)], None))
        self.assertTrue(prefs.debug_only({"project": "app", "diag": False, "log_from": []}))
        self.assertFalse(prefs.debug_only({"project": "app", "diag": False, "build": "make"}))

    def test_what_follows_a_change_is_told_once_it_is_saved(self):
        got, status = prefs.dialog_saved("app", {"project": "app", "reaches": ["10.9.9.9:443"]}, "u_0000aaaa")
        self.assertEqual((status, self.told), (200, ["net"]), got)
        self.told.clear()
        prefs.dialog_saved("app", {"project": "app", "node": "n1", "nodes": ["n1"]}, "u_0000aaaa")
        self.assertEqual(self.told.count("held"), 1, "the synced nodes hear that the space's node set moved")
        self.told.clear()
        prefs.dialog_saved("app", {"project": "app", "node": "n1", "nodes": ["n1"], "reaches": ["10.9.9.9:443"]}, "u_0000aaaa")
        self.assertEqual(self.told, [], "the same again is no change")
        self.up = False
        prefs.dialog_saved("app", {"project": "app", "reads": ["lib"]}, "u_0000aaaa")
        self.assertEqual(self.told, [], "no node store, nobody to tell")

    def test_a_part_the_module_holds_no_place_for_is_refused(self):
        with self.assertRaises(TypeError) as e:
            prefs.configure_dialog(net_nudge=lambda: None, nod_of=dict.get)
        self.assertIn("prefs takes nothing called nod_of", str(e.exception))


class Handler(unittest.TestCase):
    """The handler walks the table and names no permission of its own."""
    def setUp(self):
        with open(os.path.join(DASH, "server.py"), encoding="utf-8") as f:
            self.tree = ast.parse(f.read())
        self.fns = routegates.handlers_of(self.tree)

    def test_it_holds_no_permission_of_its_own(self):
        fn = self.fns["_prefs_post"]
        words = {n.value for n in ast.walk(fn) if isinstance(n, ast.Constant) and isinstance(n.value, str)} - {ast.get_docstring(fn)}
        named = {row[0].split(":")[-1] for row in prefs.SAVE_ASKS if row[0] not in ("", "node", "owner")}
        self.assertEqual(words & named, set(), "a permission belongs in prefs.SAVE_ASKS")
        self.assertLess(fn.end_lineno - fn.lineno, 40)
        self.assertTrue(any(isinstance(n, ast.For) and ast.unparse(n.iter) == "prefs.SAVE_ASKS" for n in ast.walk(fn)))

    def test_the_route_record_s_names_are_the_table_s(self):
        self.assertEqual(routegates.table_asks("prefs", "SAVE_ASKS"),
                         ["node:node", "node:node", "owner", "node:node", "nodes-write", "debug", "docker-write", "curate", "vms-write",
                          "deploy", "settings", "settings"])
        self.assertEqual(routegates.asks(self.fns["_prefs_post"], self.fns),
                         ["space", "unlocked", "node:node", "owner", "nodes-write", "debug", "docker-write", "curate", "vms-write", "deploy", "settings"])
        self.assertEqual(routegates.table_asks("prefs", "NO_SUCH_ASKS"), [])
        self.assertEqual(routegates.table_asks("no_such_module", "SAVE_ASKS"), [])

    def test_every_row_is_an_ask_a_change_and_what_it_may_refuse(self):
        for ask, changes, on, fits in prefs.SAVE_ASKS:
            self.assertTrue(callable(changes))
            self.assertEqual(ask == "node", on is not None, f"{ask}: only an ask of nodes names them")
            self.assertTrue(ask or fits, "a row that asks nothing refuses something")


if __name__ == "__main__":
    unittest.main()
