"""Nothing is published that the checks have not passed (R206; the audit of
13 Nov, the operator's choices of 14 Nov): a release's tag runs the place
check, aerie lint with the unit tier, and every browser suite, and each job
that pushes an image or makes or fills a release waits for all three. A tag
ran none of them, CI's lint was its own copy of seven of aerie lint's
checks, no workflow ran the unit tier, and the suites ran only for a change
under scripts/dashboard. The workflows' own shape, read as YAML."""
import os
import unittest

try:
    import yaml
except ImportError:                                            # pragma: no cover
    yaml = None

HERE = os.path.dirname(os.path.abspath(__file__))
WF = os.path.abspath(os.path.join(HERE, "..", "..", "..", ".github", "workflows"))
GATE = {"place", "lint", "suites"}
TAG_ONLY = "startsWith(github.ref, 'refs/tags/v')"


def load(name):
    with open(os.path.join(WF, name), encoding="utf-8") as f:
        d = yaml.safe_load(f)
    # YAML reads the key `on` as true.
    d["on"] = d.get("on", d.get(True))
    return d


def needs(job):
    n = job.get("needs") or []
    return {n} if isinstance(n, str) else set(n)


def runs(job):
    return "\n".join(str(s.get("run") or "") for s in job.get("steps") or [])


@unittest.skipUnless(yaml, "PyYAML reads the workflows")
class Gate(unittest.TestCase):
    def test_a_tag_runs_the_three_checks_and_every_publishing_job_waits_for_them(self):
        jobs = load("build-image.yml")["jobs"]
        for name in GATE:
            self.assertEqual(jobs[name].get("if"), TAG_ONLY, name)
        self.assertEqual(jobs["lint"]["uses"], "./.github/workflows/lint.yml")
        self.assertEqual(jobs["suites"]["uses"], "./.github/workflows/dashboard.yml")
        self.assertIn("tools/release-place.sh", runs(jobs["place"]))
        self.assertIn("origin/main", runs(jobs["place"]))
        # The image, and everything signed or handed on for the release.
        for name in ("build", "bundle", "apps", "android", "release"):
            self.assertTrue(GATE <= needs(jobs[name]), f"{name} waits for {sorted(GATE - needs(jobs[name]))}")
        # A job that needs one that failed does not run by itself; the image's build says so in
        # words, since it also runs where the three are skipped (a push to main, the weekly rebuild).
        cond = jobs["build"]["if"]
        for part in ("!cancelled()", "!contains(needs.*.result, 'failure')", "!contains(needs.*.result, 'cancelled')"):
            self.assertIn(part, cond)
        for name in ("bundle", "apps", "android", "release"):
            self.assertEqual(jobs[name].get("if"), TAG_ONLY, f"{name}: no always() or !cancelled() to run past a failed check")
        # Every job that publishes is one of these or waits on one that is.
        for name, job in jobs.items():
            text = runs(job) + str(job.get("steps") or "")
            if any(w in text for w in ("release-attach.sh", "build-push-action", "gh release", "imagetools create")):
                self.assertTrue(GATE <= needs(job), f"{name} publishes and does not wait for the checks")
        # ...and the run's record names each check's result.
        self.assertTrue(GATE <= needs(jobs["record"]))

    def test_one_run_builds_everything_and_its_last_job_makes_the_release_once(self):
        # Step 1: four jobs in three workflows each made or looked for the
        # tag's release (two drafts for one tag, 2 Nov), and the bundle's job
        # started the apps' workflows by name.
        jobs = load("build-image.yml")["jobs"]
        last = jobs["release"]
        self.assertEqual(needs(last), GATE | {"build", "upgrade", "bundle", "apps", "android", "appliance"},
                         "the release waits for everything it carries, the image started on every release's /config among it")
        self.assertEqual(jobs["apps"]["uses"], "./.github/workflows/companion-app.yml")
        self.assertEqual(jobs["apps"]["with"], {"tag": "${{ github.ref_name }}", "hand-on": True})
        self.assertEqual(jobs["android"]["uses"], "./.github/workflows/android-app.yml")
        self.assertEqual(jobs["android"]["with"], {"tag": "${{ github.ref_name }}"})
        # One job makes the release or touches it, and none starts a workflow that would.
        makers = [n for n, j in jobs.items() if "release-attach.sh" in runs(j) or "gh release" in runs(j)]
        self.assertEqual(makers, ["release"])
        for name, job in jobs.items():
            for wf in ("android-app.yml", "companion-app.yml"):
                self.assertNotIn(f"gh workflow run {wf}", runs(job), name)
                self.assertNotIn('gh workflow run "$wf"', runs(job), name)
            # ...and of the jobs with steps of their own, it alone may write
            # the repository's releases (the apps' workflow is granted what
            # it asks for when it is run by hand, and hands on here).
            if name != "release" and "uses" not in job:
                self.assertNotEqual((job.get("permissions") or {}).get("contents"), "write", name)
        # The bundle and the notes are handed on, and the last job gathers
        # every release-* artifact and the OS image's.
        ups = [s["with"] for s in jobs["bundle"]["steps"] if str(s.get("uses", "")).startswith("actions/upload-artifact@")]
        self.assertEqual([u["name"] for u in ups], ["release-bundle"])
        self.assertIn("notes.md", ups[0]["path"])
        self.assertEqual(ups[0]["retention-days"], 1)
        downs = [s["with"] for s in last["steps"] if str(s.get("uses", "")).startswith("actions/download-artifact@")]
        self.assertIn({"name": "aerieos-os", "path": "out"}, downs)
        self.assertIn({"pattern": "release-*", "path": "rel", "merge-multiple": True}, downs)
        text = runs(last)
        self.assertIn('bash tools/release-attach.sh "$tag" --notes rel/notes.md', text)
        self.assertIn("--publish-when-whole .release-files", text)
        self.assertIn("tools", next(s for s in last["steps"] if str(s.get("uses", "")).startswith("actions/checkout@"))["with"]["sparse-checkout"])
        # The run's record names every job's result.
        self.assertEqual(needs(jobs["record"]), needs(last) | {"release"})
        for n in needs(jobs["record"]):
            self.assertIn(f"{n}=${{{{ needs.{n}.result }}}}", str(jobs["record"]["steps"]))

    def test_the_apps_hand_their_files_on_or_attach_them_never_both(self):
        wf = load("companion-app.yml")
        self.assertEqual(wf["on"]["workflow_call"]["inputs"]["hand-on"], {"type": "boolean", "default": False})
        names = []
        for job in wf["jobs"].values():
            attach = [s for s in job["steps"] if "release-attach.sh" in str(s.get("run") or "")]
            hand = [s for s in job["steps"] if str(s.get("uses", "")).startswith("actions/upload-artifact@")]
            self.assertEqual([s["if"] for s in attach], ["env.TAG != '' && !inputs.hand-on"])
            self.assertEqual([s["if"] for s in hand], ["inputs.hand-on"])
            names.append(hand[0]["with"]["name"])
            self.assertEqual(hand[0]["with"]["retention-days"], 1)
            self.assertIn(".sha256", hand[0]["with"]["path"])
        self.assertEqual(sorted(names), ["release-apps-portable", "release-apps-windows"])
        # The Windows job is handed its version by the Linux one: aerie
        # version does not load on Windows, and a rehearsal's .exe failed there.
        self.assertEqual(wf["jobs"]["build"]["needs"], "portable")
        self.assertEqual(wf["jobs"]["build"]["env"]["VER"], "${{ needs.portable.outputs.version }}")
        self.assertNotIn("scripts/aerie", runs(wf["jobs"]["build"]))
        # A run by hand for a tag is not the tag's own run: neither cancels the other.
        for name in ("companion-app.yml", "android-app.yml"):
            self.assertIn("${{ github.workflow }}", load(name)["concurrency"]["group"], name)

    def test_the_rehearsal_gathers_what_was_built_and_reads_the_list_as_the_last_job_does(self):
        jobs = load("release-rehearsal.yml")["jobs"]
        self.assertEqual(jobs["apps"]["with"], {"hand-on": True})
        self.assertIn("release-bundle", str(jobs["bundle"]["steps"]))
        m = jobs["manifest"]
        downs = [s["with"] for s in m["steps"] if str(s.get("uses", "")).startswith("actions/download-artifact@")]
        self.assertIn({"pattern": "release-*", "path": "rel", "merge-multiple": True}, downs)
        self.assertIn("tools/release-missing.sh .release-files", runs(m))
        # ...and publishes nothing: no job of it may write a release.
        for name, job in jobs.items():
            self.assertNotIn("release-attach.sh", runs(job), name)

    def test_every_workflow_says_what_its_token_may_do(self):
        # With none said, a job takes the repository's own default, which
        # may be to write: three workflows said nothing.
        for name in sorted(os.listdir(WF)):
            if name.endswith(".yml"):
                self.assertIsNotNone(load(name).get("permissions"), f"{name} names no default for its token")
        for name in ("build-image.yml", "lint.yml", "dashboard.yml", "os-image.yml", "release-rehearsal.yml"):
            self.assertEqual(load(name)["permissions"], {"contents": "read"}, name)

    def test_the_image_is_stamped_by_aerie_version_and_a_tag_it_disagrees_with_fails(self):
        # Step 9: the build's shell worked the version out again, and said a
        # release candidate's tag where the tool said a dev build.
        build = load("build-image.yml")["jobs"]["build"]
        step = next(s for s in build["steps"] if s.get("id") == "ver")
        run = step["run"]
        self.assertIn("bash scripts/aerie version --semver", run)
        self.assertIn('BB_VERSION_TAG="$tag"', run)
        self.assertNotIn("rev-list", run)
        self.assertNotIn("describe", run)
        self.assertIn('[ "$v" != "${tag#v}" ]', run)
        self.assertIn("exit 1", run)
        # The full history the tool counts, checked out before it.
        first = next(s for s in build["steps"] if str(s.get("uses", "")).startswith("actions/checkout@"))
        self.assertEqual(first["with"]["fetch-depth"], 0)

    def test_a_rehearsal_runs_what_a_tag_is_held_to_and_publishes_nothing(self):
        wf = load("release-rehearsal.yml")
        jobs = wf["jobs"]
        self.assertEqual(jobs["lint"]["uses"], "./.github/workflows/lint.yml")
        self.assertEqual(jobs["suites"]["uses"], "./.github/workflows/dashboard.yml")
        self.assertIn("tools/release-place.sh", runs(jobs["place"]))
        self.assertTrue(GATE <= needs(jobs["manifest"]))
        self.assertEqual(wf["permissions"], {"contents": "read"}, "nothing here can write a release")
        for name, job in jobs.items():
            self.assertNotIn("release-attach.sh", runs(job), name)

    def test_ci_lint_is_aerie_lint_with_nothing_skipped_and_the_unit_tier(self):
        wf = load("lint.yml")
        self.assertIn("workflow_call", wf["on"])
        self.assertIn("pull_request", wf["on"])
        lint, unit = wf["jobs"]["lint"], wf["jobs"]["unit"]
        step = next(s for s in lint["steps"] if "scripts/aerie lint" in str(s.get("run") or ""))
        self.assertEqual(step["env"], {"BB_RELAYED": "1", "BB_LINT_STRICT": "1"})
        # No copy of a check kept beside it: the one list is aerie lint's.
        for own in ("shellcheck -x", "hadolint Dockerfile", "ruff check", "actionlint -color", "docker compose --env-file"):
            self.assertNotIn(own, runs(lint))
        self.assertIn("scripts/aerie tests unit", runs(unit))
        for job in (lint, unit):
            self.assertEqual(job["runs-on"], ["self-hosted", "bb-sandbox"])
            self.assertIn("head.repo.full_name == github.repository", job["if"], "never a fork's request on this runner")
        # The whole history and the tags: the agent's version and the shipped migrations are measured against them.
        self.assertEqual(lint["steps"][0]["with"], {"fetch-depth": 0})

    def test_a_missing_tool_fails_a_strict_lint(self):
        with open(os.path.join(WF, "..", "..", "scripts", "aerie"), encoding="utf-8") as f:
            text = f.read()
        need = text[text.index("    need() { # need TOOL"):]
        need = need[:need.index("\n    }\n")]
        strict = need[need.index("BB_LINT_STRICT"):]
        self.assertIn("rc=1", strict[:strict.index("on_node")], "said as a failure before any skip is")

    def test_the_suites_run_for_everything_they_test_and_cannot_hold_the_runner(self):
        wf = load("dashboard.yml")
        self.assertIn("workflow_call", wf["on"])
        paths = set(wf["on"]["pull_request"]["paths"])
        for p in ("scripts/dashboard/**", "scripts/agent/**", "scripts/lib/**", "scripts/aerie", "nodes/**", "Dockerfile"):
            self.assertIn(p, paths)
        job = wf["jobs"]["dashboard"]
        self.assertLessEqual(int(job["timeout-minutes"]), 180)
        self.assertIn("scripts/dashboard/test/run.sh", runs(job))


if __name__ == "__main__":
    unittest.main()
