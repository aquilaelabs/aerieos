"""A System container on a node (syscontainer.py), what nginx and the
model router share: the name and the directory slug, whether it is on a
node, the indent of a config's text in its two ways of ending a line, and
deploy, apply and remove with each caller's own step run where it was."""
import os
import sys
import unittest

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))
import syscontainer  # noqa: E402


class Devapp:
    MAIN, SYSTEM = "main", "System"

    def __init__(self, recs, said):
        self.recs, self.said = recs, said

    def is_file_source(self, name):
        return name in self.recs

    def _read_rec(self, name, inst):
        return dict(self.recs.get(name) or {})

    def forget_container(self, name):
        self.said.append(("forget", name))
        self.recs.pop(name, None)


class Manager:
    """containers and devactions in one: each call said, each answer set."""

    def __init__(self, devapp, said, write=None, build=None, gone=None):
        self.devapp, self.said = devapp, said
        self.write, self.build, self.gone = write or {"ok": True}, build or {"job": "j-1"}, gone or {"ok": True}

    def create_container(self, name, text, env, node="", for_project=""):
        self.said.append(("create", name, text, env, node, for_project))
        return self.write

    def update_container(self, name, text, env):
        self.said.append(("update", name, text, env))
        return self.write

    def rebuild(self, name, inst, gate=True):
        self.said.append(("rebuild", name, inst, gate))
        return self.build

    def remove_instance(self, name, inst):
        self.said.append(("remove", name, inst))
        return self.gone


NODES = [{"id": "n1", "state": "online"}, {"id": "n2", "state": "online"}, {"id": "old", "state": "retired"}]


class Names(unittest.TestCase):
    def test_the_name_is_the_prefix_and_the_node_s_name_as_compose_takes_it(self):
        self.assertEqual(syscontainer.container_name("nginx", "VPS Box"), "nginx-vps-box")
        self.assertEqual(syscontainer.container_name("router", "--"), "router-node")
        self.assertEqual(syscontainer.container_name("scanners", ""), "scanners-node")
        self.assertEqual(len(syscontainer.container_name("nginx", "x" * 90)), 60)

    def test_a_node_s_id_is_one_directory_name(self):
        self.assertEqual(syscontainer.node_slug("n-1_a"), "n-1_a")
        self.assertEqual(syscontainer.node_slug("../n 1"), "___n_1")

    def test_deployed_is_written_here_and_bound_to_this_node(self):
        dv = Devapp({"nginx-a": {"node": "n1"}}, [])
        self.assertTrue(syscontainer.deployed(dv, "nginx-a", "n1"))
        self.assertFalse(syscontainer.deployed(dv, "nginx-a", "n2"))
        self.assertFalse(syscontainer.deployed(dv, "nginx-b", "n1"))


class Indent(unittest.TestCase):
    def test_a_line_ends_at_a_newline_and_the_trailing_ones_go(self):
        self.assertEqual(syscontainer.indent("a\n\nb\n\n", 2), "  a\n\n  b")
        self.assertEqual(syscontainer.indent("a\r\nb\x0cc\n", 2), "  a\r\n  b\x0cc", "a pasted certificate's own line ends stay in the line")
        self.assertEqual(syscontainer.indent("", 6), "")

    def test_every_break_ends_a_line_and_only_the_last_one_goes(self):
        self.assertEqual(syscontainer.indent("a\n\nb\n\n", 2, every_break=True), "  a\n\n  b\n")
        self.assertEqual(syscontainer.indent("a\r\nb\x0cc\n", 2, every_break=True), "  a\n  b\n  c")
        self.assertEqual(syscontainer.indent("", 6, every_break=True), "")


class Deploy(unittest.TestCase):
    def deploy(self, recs, **answers):
        said = []
        dv = Devapp(recs, said)
        m = Manager(dv, said, **answers)
        got = syscontainer.deploy("n1", "nginx-a", lambda: said.append("text") or "services: {}", m, m, dv, lambda: NODES,
                                  first=lambda: said.append("first"), made=lambda: said.append("made"))
        return got, said

    def test_made_as_system_s_and_built_with_each_step_in_its_place(self):
        got, said = self.deploy({})
        self.assertEqual(got, {"ok": True, "name": "nginx-a", "job": "j-1"})
        self.assertEqual(said, ["first", "text", ("create", "nginx-a", "services: {}", "", "n1", "System"), "made",
                                ("rebuild", "nginx-a", "main", False)])

    def test_a_name_this_node_or_a_live_one_holds_is_refused_before_anything_is_done(self):
        for was in ("n1", "n2"):
            got, said = self.deploy({"nginx-a": {"node": was}})
            self.assertEqual((got, said), ({"error": "nginx-a is already on the Containers page"}, []), was)

    def test_a_name_left_by_a_node_that_is_gone_is_taken(self):
        for was in ("old", "never-heard-of", None):
            got, said = self.deploy({"nginx-a": {"node": was}})
            self.assertEqual(got["job"], "j-1", was)
            self.assertEqual(said[:2], [("forget", "nginx-a"), "first"], was)

    def test_a_refused_write_is_the_answer_and_nothing_is_stamped_or_built(self):
        got, said = self.deploy({}, write={"error": "no room"})
        self.assertEqual(got, {"error": "no room"})
        self.assertEqual(said[-1][0], "create")

    def test_made_but_not_built_is_said_as_a_note(self):
        got, said = self.deploy({}, build={"error": "the node is away"})
        self.assertEqual(got, {"ok": True, "name": "nginx-a", "note": "made, but not built: the node is away"})
        self.assertIn("made", said)


class ApplyAndRemove(unittest.TestCase):
    def run_on(self, recs, fn, **answers):
        said = []
        dv = Devapp(recs, said)
        return fn(Manager(dv, said, **answers), dv, said), said

    def apply(self, recs, **answers):
        return self.run_on(recs, lambda m, dv, said: syscontainer.apply(
            "router-a", lambda: said.append("text") or "x", m, m, dv, first=lambda: said.append("first")), **answers)

    def test_apply_does_nothing_where_it_is_not_deployed(self):
        self.assertEqual(self.apply({}), ({"ok": True, "deployed": False}, []))

    def test_apply_writes_the_file_and_rebuilds(self):
        got, said = self.apply({"router-a": {"node": "n1"}})
        self.assertEqual(got, {"ok": True, "deployed": True, "job": "j-1"})
        self.assertEqual(said, ["first", "text", ("update", "router-a", "x", ""), ("rebuild", "router-a", "main", False)])
        self.assertEqual(self.apply({"router-a": {}}, write={"error": "not valid"})[0], {"error": "not valid"})
        self.assertEqual(self.apply({"router-a": {}}, build={"error": "away"})[0],
                         {"ok": True, "deployed": True, "note": "saved, but not rebuilt: away"})

    def test_remove_answers_as_the_manager_did_and_runs_gone_after_it(self):
        def remove(m, dv, said):
            return syscontainer.remove("router-a", m, dv, gone=lambda: said.append("gone"))
        self.assertEqual(self.run_on({}, remove), ({"error": "router-a is not on the Containers page"}, []))
        self.assertEqual(self.run_on({"router-a": {}}, remove), ({"ok": True}, [("remove", "router-a", "main"), "gone"]))
        got, said = self.run_on({"router-a": {}}, remove, gone={"error": "busy"})
        self.assertEqual((got, said[-1]), ({"error": "busy"}, "gone"), "gone runs whatever the manager answered")
        self.assertEqual(self.run_on({"router-a": {}}, lambda m, dv, said: syscontainer.remove("router-a", m, dv))[0], {"ok": True})


if __name__ == "__main__":
    unittest.main()
