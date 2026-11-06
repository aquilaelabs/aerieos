"""R208 step 6: a project's Agents may dials are the defaults for every
repository in it; a repository's notebook sets one apart as its own
override, and "inherit" gives it back."""
import json
import os
import shutil
import sys
import tempfile
import unittest
from pathlib import Path

sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)), ".."))
import prefs  # noqa: E402
import registry  # noqa: E402
import repos  # noqa: E402


def write_json(p, d, mode=0o644):
    Path(p).write_text(json.dumps(d))


class Overrides(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.mkdtemp()
        self.addCleanup(shutil.rmtree, self.tmp, True)
        ws = Path(self.tmp) / "ws"
        for n in ("app", "server"):
            (ws / n).mkdir(parents=True)
        registry.configure(state=self.tmp, workspace=ws, write_json=write_json)
        registry.sync()
        repos.configure(state=self.tmp, write_json=write_json, registry=registry, workspace=ws)
        prefs.configure(write_json=write_json, state=self.tmp)
        prefs.configure_repos(project_of=repos.project_of, members=repos.members, is_repos=registry.is_repos)
        self.addCleanup(lambda: prefs.__dict__.update(_repos=None))
        self.key = repos.create("Shop")["key"]
        for d in ("app", "server"):
            self.assertTrue(repos.add(self.key, d).get("ok"))

    def test_a_repository_inherits_the_projects_dials_until_its_notebook_sets_one(self):
        # The project's own door sets the defaults.
        r = prefs.set_prefs("app", scope="project", makevms="auto", gate={"roadmap": "ask"})
        self.assertTrue(r.get("ok"), r)
        for repo in ("app", "server"):
            got = prefs.get(repo)
            self.assertEqual((got["makevms"], got["gate"]["roadmap"], got["overrides"]), ("auto", "ask", []), repo)
            self.assertEqual((got["project_dials"]["makevms"], got["project_dials"]["gate"]["roadmap"]), ("auto", "ask"))
        # The notebook sets one repository apart.
        r = prefs.set_prefs("server", makevms="deny", gate={"roadmap": "auto", "bugs": "inherit"})
        self.assertTrue(r.get("ok"), r)
        got = prefs.get("server")
        self.assertEqual((got["makevms"], got["gate"]["roadmap"], got["overrides"]), ("deny", "auto", ["gate.roadmap", "makevms"]))
        self.assertEqual(prefs.get("app")["makevms"], "auto", "the other repository still inherits")
        self.assertEqual(prefs.get(self.key)["makevms"], "auto", "...and the space's default stands")
        # The project's default moves under the one that inherits, not the override.
        prefs.set_prefs("app", scope="project", makevms="ask")
        self.assertEqual((prefs.get("app")["makevms"], prefs.get("server")["makevms"]), ("ask", "deny"))
        # Inherit gives the override back.
        r = prefs.set_prefs("server", makevms="inherit", gate={"roadmap": "inherit"})
        self.assertTrue(r.get("ok"), r)
        got = prefs.get("server")
        self.assertEqual((got["makevms"], got["gate"]["roadmap"], got["overrides"]), ("ask", "ask", []))
        raw = json.loads((Path(self.tmp) / "claude-prefs.json").read_text())["projects"]
        self.assertNotIn("overrides", raw.get("server") or {}, "no override is stored as none")

    def test_the_test_run_pick_and_a_bad_name_are_held(self):
        prefs.set_prefs("app", scope="project", test_change="restart")
        self.assertEqual(prefs.get("server")["test_change"], "restart")
        prefs.set_prefs("server", test_change="wait")
        self.assertEqual((prefs.get("server")["test_change"], prefs.get("server")["overrides"]), ("wait", ["test_change"]))
        self.assertIn("not a dial", prefs._set_prefs("server", overrides={"node": True}).get("error", ""))

    def test_a_record_from_before_the_list_keeps_what_its_notebook_set(self):
        # A released install's repository record: its gate values stored,
        # no overrides list. Each stays that repository's own.
        f = Path(self.tmp) / "claude-prefs.json"
        d = json.loads(f.read_text()) if f.is_file() else {"projects": {}}
        d.setdefault("projects", {})["server"] = {"gate": {"bugs": "deny"}, "pc": "auto"}
        f.write_text(json.dumps(d))
        prefs._cache.update(mtime=None, data=None) if hasattr(prefs, "_cache") else None
        prefs.set_prefs("app", scope="project", pc="deny", gate={"bugs": "auto"})
        got = prefs.get("server")
        self.assertEqual((got["gate"]["bugs"], got["pc"], got["overrides"]), ("deny", "auto", ["gate.bugs", "pc"]))
        # Lifted, it reads the project's, and stays lifted after the save.
        prefs.set_prefs("server", pc="inherit", gate={"bugs": "inherit"})
        got = prefs.get("server")
        self.assertEqual((got["gate"]["bugs"], got["pc"], got["overrides"]), ("auto", "deny", []))

    def test_a_project_made_around_a_repository_takes_its_dials_as_defaults(self):
        prefs.set_prefs("app", gate={"roadmap": "ask"}, devbuild="auto")      # app's own, as a notebook writes
        prefs.adopt(self.key, "app")
        got = prefs.get("app")
        self.assertEqual((got["gate"]["roadmap"], got["devbuild"], got["overrides"]), ("ask", "auto", []),
                         "the dials moved to the space; the repository inherits them")
        self.assertEqual((prefs.get("server")["gate"]["roadmap"], prefs.get("server")["devbuild"]), ("ask", "auto"))

    def test_a_project_with_no_repository_reads_inherit_as_nothing(self):
        key = repos.create("Media server")["key"]
        r = prefs.set_prefs(key, makevms="inherit", gate={"roadmap": "inherit"})
        self.assertTrue(r.get("ok"), r)
        self.assertEqual(prefs.get(key)["makevms"], "deny")



    def test_a_repository_narrows_its_spaces_hosting_nodes_and_sets_its_test_node_apart(self):
        # R223: the space's hosting nodes are its own list; a repository keeps
        # its containers off some of them, never adding one; Test node is a
        # dial a repository may set apart.
        r = prefs.set_prefs("app", scope="project", node="n_cccccccc", hosts=["n_aaaaaaaa", "n_bbbbbbbb"], test_node="")
        self.assertTrue(r.get("ok"), r)
        r = prefs.set_prefs("server", hosts_off=["n_aaaaaaaa"], test_node="n_cccccccc")
        self.assertTrue(r.get("ok"), r)
        srv, app = prefs.get("server"), prefs.get("app")
        self.assertEqual((srv["hosts"], srv["space_hosts"]), (["n_bbbbbbbb"], ["n_aaaaaaaa", "n_bbbbbbbb"]))
        self.assertEqual(app["hosts"], ["n_aaaaaaaa", "n_bbbbbbbb"], "the other repository keeps the space's whole list")
        self.assertEqual(prefs.get(self.key)["hosts"], ["n_aaaaaaaa", "n_bbbbbbbb"], "...and the space's own is untouched")
        self.assertEqual((srv["test_node"], app["test_node"]), ("n_cccccccc", ""))
        self.assertIn("test_node", srv["overrides"])
        prefs.set_prefs("server", test_node="inherit", hosts_off=[])
        srv = prefs.get("server")
        self.assertEqual((srv["test_node"], srv["hosts"]), ("", ["n_aaaaaaaa", "n_bbbbbbbb"]))

if __name__ == "__main__":
    unittest.main()
