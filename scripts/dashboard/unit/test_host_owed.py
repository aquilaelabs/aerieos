"""What the git host owes a repository's own workflows (R267 step 29): read
from the workflows as text (version.host_wants), asked of GitHub
(forgeaccess.owed), and a release refused while any is owed
(version.host_owed). Nothing in it names an environment or a secret: each
comes from the repository's own files."""
import os
import sys
import tempfile
import unittest
from pathlib import Path
from unittest import mock

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))
import forgeaccess  # noqa: E402
import version  # noqa: E402

RELEASE = """name: build
on:
  push:
    tags: ["v*"]
  pull_request:
jobs:
  build:
    runs-on: ubuntu-24.04
    steps:
      - run: echo ${{ secrets.GITHUB_TOKEN }}
  publish:
    environment: release
    runs-on: ubuntu-24.04
    steps:
      - run: sign
        env:
          KEY: ${{ secrets.RELEASE_KEY }}
"""
WINDOWS = """on: workflow_call
jobs:
  windows:
    environment: ${{ startsWith(github.ref, 'refs/tags/v') && 'windows-signing' || '' }}
    steps:
      - run: echo ${{ secrets.WIN_PFX }}
  other:
    environment:
      name: docs
    steps:
      - run: true
"""


class Wants(unittest.TestCase):
    def setUp(self):
        self.d = Path(tempfile.mkdtemp())
        (self.d / ".github" / "workflows").mkdir(parents=True)
        (self.d / ".github" / "workflows" / "build.yml").write_text(RELEASE)
        (self.d / ".github" / "workflows" / "windows.yml").write_text(WINDOWS)
        p = mock.patch.object(version, "root", lambda project: self.d)
        p.start()
        self.addCleanup(p.stop)

    def test_each_environment_its_jobs_secrets_and_the_triggers(self):
        got = version.host_wants("x")
        self.assertEqual(got, {"environments": {"release": ["RELEASE_KEY"], "windows-signing": ["WIN_PFX"], "docs": []},
                               "tags": True, "pull_requests": True})

    def test_a_tree_with_no_workflows_asks_nothing(self):
        with mock.patch.object(version, "root", lambda project: Path(tempfile.mkdtemp())):
            self.assertEqual(version.host_wants("x"), {"environments": {}, "tags": False, "pull_requests": False})

    def test_a_release_is_refused_while_anything_is_owed_and_not_for_what_cannot_be_read(self):
        rows = [{"what": "the environment release waits for a required reviewer", "state": "owed", "why": "add one"},
                {"what": "a tag is made only under a ruleset", "state": "unknown", "why": "the token may not read it"}]
        with mock.patch.object(version, "owes", lambda project, wants: rows):
            why = version.host_owed("x", "")
        self.assertIn("the environment release waits for a required reviewer: add one", why)
        self.assertNotIn("ruleset", why)
        with mock.patch.object(version, "owes", lambda project, wants: rows[1:]):
            self.assertEqual(version.host_owed("x", ""), "")
        with mock.patch.object(version, "owes", None):
            self.assertEqual(version.host_owed("x", ""), "", "a controller that cannot ask says nothing")


class Owed(unittest.TestCase):
    WANTS = {"environments": {"release": ["RELEASE_KEY"], "windows-signing": ["WIN_PFX"]}, "tags": True, "pull_requests": True}

    def ask(self, answers):
        t = {"forge": {"kind": "github"}, "repo": "o/r", "host": "github.com", "scheme": "https", "token": "x"}
        asked = []

        def call(_t, method, path, data=None, raw=False):
            asked.append((method, path))
            for prefix, answer in answers.items():
                if path.startswith("/repos/o/r" + prefix):
                    return answer[0], answer[1], {}
            return 404, {}, {}
        with mock.patch.object(forgeaccess, "target_of", lambda p: t), mock.patch.object(forgeaccess, "_call", call):
            rows = forgeaccess.owed("x", self.WANTS)
        self.assertTrue(all(m == "GET" for m, _p in asked), "it only reads")
        return {r["what"]: (r["state"], r["why"]) for r in rows}

    def test_all_that_is_owed_is_said_with_where_to_set_it(self):
        got = self.ask({"/environments/release": (200, {"protection_rules": [{"type": "wait_timer"}]}),
                        "/actions/secrets": (200, {"secrets": [{"name": "RELEASE_KEY"}, {"name": "OTHER"}]}),
                        "/rulesets": (200, [{"target": "branch", "enforcement": "active"}]),
                        "/actions/permissions/fork-pr-contributor-approval": (200, {"approval_policy": "first_time_contributors"})})
        self.assertEqual(got["the environment release waits for a required reviewer"][0], "owed")
        self.assertIn("Settings, Environments, release", got["the environment release waits for a required reviewer"][1])
        self.assertEqual(got["the environment windows-signing waits for a required reviewer"],
                         ("owed", "o/r has no environment windows-signing: make it under Settings, Environments, with a required reviewer"))
        self.assertEqual(got["no repository-level secret stands in for one an environment holds"][0], "owed")
        self.assertIn("RELEASE_KEY", got["no repository-level secret stands in for one an environment holds"][1])
        self.assertEqual(got["a tag is made only under a ruleset"][0], "owed")
        self.assertEqual(got["an outside contributor's pull request runs only once approved"][0], "owed")

    def test_all_set_is_ok(self):
        reviewed = (200, {"protection_rules": [{"type": "required_reviewers", "reviewers": [{"type": "User"}]}]})
        got = self.ask({"/environments/release": reviewed, "/environments/windows-signing": reviewed,
                        "/actions/secrets": (200, {"secrets": [{"name": "OTHER"}]}),
                        "/rulesets": (200, [{"target": "tag", "enforcement": "active"}]),
                        "/actions/permissions/fork-pr-contributor-approval": (200, {"approval_policy": "all_external_contributors"})})
        self.assertEqual({s for s, _w in got.values()}, {"ok"})

    def test_what_the_token_may_not_read_is_unknown_with_the_permission(self):
        got = self.ask({"/environments": (403, {}), "/actions/secrets": (403, {}), "/rulesets": (403, {}),
                        "/actions/permissions": (403, {})})
        self.assertEqual(got["the environment release waits for a required reviewer"],
                         ("unknown", "the token may not read it (it needs Environments: read)"))
        self.assertEqual(got["a tag is made only under a ruleset"], ("unknown", "the token may not read it (it needs Administration: read)"))

    def test_another_host_is_not_asked(self):
        t = {"forge": {"kind": "gitea"}, "repo": "o/r"}
        with mock.patch.object(forgeaccess, "target_of", lambda p: t), \
                mock.patch.object(forgeaccess, "_call", side_effect=AssertionError("nothing is asked")):
            rows = forgeaccess.owed("x", self.WANTS)
        self.assertEqual([r["state"] for r in rows], ["unknown"])


if __name__ == "__main__":
    unittest.main()
