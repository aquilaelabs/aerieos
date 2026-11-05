"""R208: a project with no repository is a place to run an agent that
builds containers and VMs: its folder, its briefing, its guard and its
dials, with no git and no notebook."""
import json
import os
import shutil
import sys
import tempfile
import unittest
from pathlib import Path

sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)), ".."))
import preamble  # noqa: E402
import registry  # noqa: E402
import repos  # noqa: E402
import rules  # noqa: E402


def write_json(p, d, mode=0o644):
    Path(p).write_text(json.dumps(d))


class WorkFolder(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.mkdtemp()
        self.addCleanup(shutil.rmtree, self.tmp, True)
        self.ws = Path(self.tmp) / "ws"
        (self.ws / "app").mkdir(parents=True)
        registry.configure(state=self.tmp, workspace=self.ws, write_json=write_json)
        registry.sync()
        repos.configure(state=self.tmp, write_json=write_json, registry=registry, workspace=self.ws)

    def test_a_new_project_has_a_plain_folder_with_its_mark(self):
        got = repos.create("Media server")
        key = got["key"]
        d = self.ws / key
        self.assertTrue(d.is_dir(), "its folder is there from the start")
        mark = json.loads((d / repos.MARK).read_text())
        self.assertEqual((mark["name"], mark["id"], mark["repository"]), ("Media server", got["id"], None))
        self.assertFalse((d / ".git").exists())
        self.assertTrue(repos.is_work(key))
        self.assertEqual(repos.empty_keys(), [key])
        registry.sync()
        self.assertTrue(registry.is_repos(key), "a sync leaves a space's folder as the space's")
        self.assertFalse(registry.is_project(key), "...and never lists it as a repository")

    def test_a_repository_added_makes_it_a_coding_project(self):
        key = repos.create("Shop")["key"]
        self.assertTrue(repos.add(key, "app").get("ok"))
        self.assertFalse(repos.is_work(key))
        self.assertEqual(repos.empty_keys(), [])
        self.assertFalse(repos.is_work("app"), "a repository is not one either")

    def test_work_folder_is_made_again_when_missing_and_delete_removes_it(self):
        key = repos.create("Lab")["key"]
        shutil.rmtree(self.ws / key)
        self.assertEqual(repos.work_folder(key), self.ws / key)
        self.assertTrue((self.ws / key / repos.MARK).is_file())
        (self.ws / key / "compose.yml").write_text("services: {}\n")
        self.assertTrue(repos.delete(key).get("ok"))
        self.assertFalse((self.ws / key).exists(), "its folder and what a session laid out go with it")
        self.assertIsNone(repos.work_folder("app"), "a repository's folder is not a work folder")


class Briefing(unittest.TestCase):
    def setUp(self):
        self.was = {k: getattr(preamble, k) for k in ("work_of", "label_of", "id_of", "prefs_mod", "version_policy",
                                                       "project_fn", "repos_fn")}
        self.addCleanup(lambda: [setattr(preamble, k, v) for k, v in self.was.items()])
        preamble.work_of = lambda p: p == "media"
        preamble.label_of = lambda p: {"media": "Media server"}.get(p, p)
        preamble.id_of = lambda p: {"media": "P9"}.get(p, "")
        preamble.project_fn = None
        preamble.repos_fn = None
        preamble.version_policy = lambda p: "minor"

        class Prefs:
            @staticmethod
            def get(p):
                return {"makevms": "auto", "gate": {"roadmap": "ask"}}
        preamble.prefs_mod = Prefs

    def test_the_identity_line_says_what_there_is_and_is_not(self):
        said = preamble.identity_line("media")
        self.assertIn("shown as Media server; its id is P9", said)
        for w in ("no repository", "no notebook", "`aerie container new`", "`aerie vm`", "/workspace/media"):
            self.assertIn(w, said)

    def test_only_the_dials_that_need_no_code_are_said(self):
        said = preamble.dials_line("media")
        self.assertIn("Make VMs auto", said)
        self.assertIn("Run its container deny", said)
        self.assertNotIn("Add to roadmap", said)
        self.assertNotIn("Sign a build", said)
        self.assertNotIn("Move the version", said)
        plain = preamble.dials_line("app")
        self.assertIn("Add to roadmap ask", plain)
        self.assertIn("Move the version minor", plain)

    def test_the_code_topics_are_gated_on_a_repository(self):
        tmp = tempfile.mkdtemp()
        self.addCleanup(shutil.rmtree, tmp, True)
        t = Path(tmp) / "briefing.md"
        t.write_text("core\n<!-- BUILDERBOT:CORE-END -->\n<!-- BUILDERBOT:TOPICS -->\n\n"
                     "<!-- BUILDERBOT:IF code repo:any -->\n## Git\n<!-- BUILDERBOT:TOPIC git: pushing -->\n\ngit words\n"
                     "<!-- BUILDERBOT:END -->\n\n## Containers\n<!-- BUILDERBOT:TOPIC containers: stacks -->\n\nstack words\n")
        was = preamble.BRIEFING_PATHS
        preamble.BRIEFING_PATHS = [t]
        self.addCleanup(lambda: setattr(preamble, "BRIEFING_PATHS", was))
        work = preamble.briefing("media")
        self.assertNotIn("git words", work)
        self.assertIn("stack words", work)
        self.assertIn("git words", preamble.briefing("app"))

    def test_the_parts_leave_out_the_notebook(self):
        class Store:
            @staticmethod
            def brief(p):
                return "ROADMAP LINES"

            @staticmethod
            def fitted(p, share):
                return "the rules", ""
        was = (preamble.roadmap_mod, preamble.bugs_mod, preamble.rules_mod)
        preamble.roadmap_mod = preamble.bugs_mod = preamble.rules_mod = Store
        self.addCleanup(lambda: setattr(preamble, "roadmap_mod", was[0]) or setattr(preamble, "bugs_mod", was[1])
                        or setattr(preamble, "rules_mod", was[2]))
        names = [n for n, _, _ in preamble.parts("media")]
        self.assertNotIn("roadmap", names)
        self.assertNotIn("bugs", names)
        self.assertIn("rules", names)


class Guard(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.mkdtemp()
        self.addCleanup(shutil.rmtree, self.tmp, True)
        rules.configure(write_json=write_json, state=self.tmp)
        rules.work_of = lambda p: p == "media"
        self.addCleanup(lambda: setattr(rules, "work_of", None))

    def test_git_and_the_notebook_verbs_are_refused_with_why(self):
        hit = rules.refusing("media", "git status")
        self.assertIsNotNone(hit)
        self.assertEqual(hit[0]["name"], "no-repository")
        self.assertIn("no repository", hit[0]["text"])
        for cmd in ("aerie roadmap add 'x'", "aerie build", "aerie devapp rebuild", "aerie version policy"):
            self.assertIsNotNone(rules.refusing("media", cmd), cmd)
        for cmd in ("aerie container new", "aerie devapp ls", "aerie vm ls", "aerie -p app roadmap", "aerie rules show x",
                    "aerie report 'x'", "ls"):
            self.assertIsNone(rules.refusing("media", cmd), cmd)
        self.assertIsNone(rules.refusing("app", "git status"), "a repository's space keeps git")


if __name__ == "__main__":
    unittest.main()
