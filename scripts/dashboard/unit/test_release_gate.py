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
        self.assertEqual(needs(last), GATE | {"signature", "build", "upgrade", "bundle", "apps", "android", "appliance"},
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
        # It makes the draft and publishes nothing: a release is whole only
        # with its signed list, which is made after the Android app lands.
        self.assertNotIn("--publish-when-whole", text)
        self.assertNotIn("actions", last["permissions"])
        self.assertIn("tools", next(s for s in last["steps"] if str(s.get("uses", "")).startswith("actions/checkout@"))["with"]["sparse-checkout"])
        # The run's record names every job's result.
        self.assertEqual(needs(jobs["record"]), needs(last) | {"release"})
        for n in needs(jobs["record"]):
            self.assertIn(f"{n}=${{{{ needs.{n}.result }}}}", str(jobs["record"]["steps"]))

    def test_the_release_key_is_read_by_one_job_on_a_tag_and_by_the_seal(self):
        # The audit of 20 Nov: every build signed the agent (a push to main,
        # the weekly rebuild, a run by hand from any branch, the OS image's
        # branch pushes), in the job that built the image, with a library
        # installed unpinned in the step that held the key, and a tag with
        # no key set shipped an unsigned agent green.
        key = "secrets.AERIEOS_RELEASE_KEY"
        readers = {}
        for name in sorted(os.listdir(WF)):
            for job, body in load(name)["jobs"].items():
                if key in str(body):
                    readers[(name, job)] = body
        self.assertEqual(sorted(readers), [("build-image.yml", "signature"), ("seal-release.yml", "seal")])
        for (name, job), body in readers.items():
            self.assertEqual(body["environment"], "release", f"{name} {job}: the key's environment")
            holds = [s for s in body["steps"] if key in str(s)]
            self.assertEqual(len(holds), 1, f"{name} {job}: one step holds the key")
            self.assertNotIn("pip", holds[0]["run"], "nothing is installed where the key is")
            self.assertNotIn("uses", holds[0])
            # The library comes from the hash-pinned list, in a step before it that holds no secret.
            lib = next(i for i, s in enumerate(body["steps"]) if "tools/release-lib.sh" in str(s.get("run") or ""))
            self.assertLess(lib, body["steps"].index(holds[0]))
            self.assertNotIn("secrets.", str(body["steps"][lib]))
            self.assertEqual(holds[0]["env"]["PYTHONPATH"], "${{ runner.temp }}/release-lib")
        for name in sorted(os.listdir(WF)):
            with open(os.path.join(WF, name), encoding="utf-8") as f:
                text = f.read()
            self.assertNotIn("pip install --quiet --user cryptography", text, name)
            self.assertNotIn("secrets: inherit", text, f"{name}: a called workflow is handed the secrets it reads, by name")
        sig = load("build-image.yml")["jobs"]["signature"]
        self.assertEqual(sig["if"], TAG_ONLY)
        self.assertTrue(GATE <= needs(sig))
        text = runs(sig)
        self.assertIn("python3 tools/sign-agent.py --check ||", text, "a tag whose agent is not signed fails")
        self.assertIn("exit 1", text)
        up = next(s["with"] for s in sig["steps"] if str(s.get("uses", "")).startswith("actions/upload-artifact@"))
        self.assertEqual((up["name"], up["path"], up["retention-days"]), ("agent-signature", "scripts/agent/agent.sig", 1))
        # What packs the agent takes that signature and checks it, on a tag alone.
        jobs = load("build-image.yml")["jobs"]
        for name in ("build", "bundle"):
            self.assertIn("signature", needs(jobs[name]), name)
            take = next(s for s in jobs[name]["steps"] if (s.get("with") or {}).get("name") == "agent-signature")
            self.assertEqual(take["with"]["path"], "scripts/agent")
            self.assertIn("sign-agent.py --check", runs(jobs[name]))
        self.assertEqual(next(s for s in jobs["build"]["steps"] if (s.get("with") or {}).get("name") == "agent-signature")["if"], TAG_ONLY)
        self.assertIn("refs/tags/v*)", runs(jobs["build"]))
        self.assertIn("the agent ships unsigned", runs(jobs["build"]))
        # The OS image is handed no secret: a tag's takes the run's signature, a branch's none.
        osi = load("os-image.yml")
        self.assertNotIn("secrets", osi["on"]["workflow_call"])
        self.assertEqual(osi["on"]["workflow_call"]["inputs"]["agent-signature"], {"type": "boolean", "default": False})
        self.assertNotIn("secrets", jobs["appliance"])
        self.assertEqual(jobs["appliance"]["with"], {"agent-signature": "${{ startsWith(github.ref, 'refs/tags/v') }}"})
        self.assertEqual(needs(jobs["appliance"]), {"signature"})
        for part in ("!cancelled()", "!contains(needs.*.result, 'failure')", "startsWith(github.ref, 'refs/tags/v')", "inputs.appliance", "'schedule'"):
            self.assertIn(part, jobs["appliance"]["if"])
        take = next(s for s in osi["jobs"]["appliance"]["steps"] if (s.get("with") or {}).get("name") == "agent-signature")
        self.assertEqual(take["if"], "inputs.agent-signature")
        self.assertNotIn("release-rehearsal.yml", [n for n, _ in readers])

    def test_every_file_a_release_builds_is_attested_by_the_job_named_for_it(self):
        # The two .exe, the .pyz and the .vsix had none; the seal takes
        # each file from the workflow tools/release-sign.py names for it.
        import importlib.util
        spec = importlib.util.spec_from_file_location("release_sign_for_gate", os.path.join(WF, "..", "..", "tools", "release-sign.py"))
        tool = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(tool)

        def attests(name):
            out = {}
            for job, body in load(name)["jobs"].items():
                for s in body.get("steps") or []:
                    if str(s.get("uses", "")).startswith("actions/attest-build-provenance@"):
                        self.assertRegex(s["uses"], r"@[0-9a-f]{40}$", "pinned by commit")
                        perms = body["permissions"]
                        self.assertEqual((perms.get("id-token"), perms.get("attestations")), ("write", "write"), f"{name} {job}")
                        out[job] = (s["with"]["subject-path"].split(), s.get("if"))
            return out
        got = {name: attests(name) for name in tool.WORKFLOWS}
        self.assertEqual(sorted(got["companion-app.yml"]), ["build", "portable"])
        self.assertEqual(sorted(got["build-image.yml"]), ["bundle", "release"])
        for job, (_paths, cond) in got["companion-app.yml"].items():
            self.assertEqual(cond, "env.TAG != ''", f"{job}: for a release alone, never a rehearsal's files")
        # Each file the table names is a pattern some attesting step of that
        # workflow covers, and each attested pattern is in the table.
        import fnmatch
        for name, pats in tool.WORKFLOWS.items():
            subjects = [os.path.basename(p) for paths, _ in got[name].values() for p in paths if "*" in p]
            for pat in pats:
                if pat.startswith("aerieos-controller-"):
                    continue    # the bundle's step names its one file by the step that packed it
                self.assertTrue(any(fnmatch.fnmatchcase(pat.replace("*", "1.2.3"), s) for s in subjects), f"{name} attests no {pat}")
            for s in subjects:
                self.assertTrue(any(fnmatch.fnmatchcase(s.replace("*", "1.2.3"), p) for p in pats), f"{name} attests {s}, which the seal's table does not name")
        self.assertEqual(load("build-image.yml")["jobs"]["bundle"]["steps"][-3]["with"], {"subject-path": "${{ steps.pack.outputs.name }}"})
        # Both callers grant what the called jobs name.
        for name in ("build-image.yml", "release-rehearsal.yml"):
            self.assertEqual(load(name)["jobs"]["apps"]["permissions"],
                             {"contents": "write", "id-token": "write", "attestations": "write"}, name)
        # The image keeps its plain manifest, and is named by a digest file instead.
        build = load("build-image.yml")["jobs"]["build"]
        push = next(s for s in build["steps"] if s.get("id") == "push")
        self.assertIs(push["with"]["provenance"], False)
        last = load("build-image.yml")["jobs"]["release"]
        self.assertIn('printf \'%s@%s\\n\' "$img" "$DIGEST" > "out/aerieos-image-${GITHUB_REF_NAME#v}.digest"', runs(last))
        self.assertIn("out/aerieos-image-*.digest", runs(last))
        with open(os.path.join(WF, "..", "..", ".release-files"), encoding="utf-8") as f:
            self.assertIn("aerieos-image-@VER@.digest\n", f.read())

    def test_the_seal_is_its_own_workflow_started_for_a_tag_and_publishes_a_dev_build_once_whole(self):
        wf = load("seal-release.yml")
        self.assertEqual(list(wf["on"]), ["workflow_dispatch"])
        self.assertEqual(wf["on"]["workflow_dispatch"]["inputs"]["tag"]["required"], True)
        self.assertEqual(wf["permissions"], {"contents": "read"})
        # What the controller finds it by (releasesign.SEAL), outside a comment.
        self.assertEqual(wf["concurrency"], {"group": "bb-release-seal-${{ inputs.tag }}", "cancel-in-progress": False})
        job = wf["jobs"]["seal"]
        self.assertEqual(job["environment"], "release")
        self.assertEqual(job["permissions"], {"contents": "write", "attestations": "read", "actions": "write"})
        steps = job["steps"]
        self.assertIn('[ "$GITHUB_REF" != "refs/tags/$TAG" ]', steps[0]["run"], "run from the tag it seals")
        self.assertIn("seal=false", steps[0]["run"], "a stable release is its holder's to sign")
        for s in steps[1:]:
            self.assertIn("steps.tag.outputs.seal == 'true'", s["if"])
        text = runs(job)
        self.assertIn('python3 tools/release-sign.py seal "$TAG" --commit "$GITHUB_SHA" --attested --wait 600 --out "$RUNNER_TEMP/sealed"', text)
        self.assertIn('bash tools/release-attach.sh "$TAG" "$RUNNER_TEMP/sealed/SHA256SUMS" "$RUNNER_TEMP/sealed/SHA256SUMS.sig"', text)
        last = steps[-1]
        self.assertIn("contains(inputs.tag, '-dev.')", last["if"])
        self.assertIn('bash tools/release-attach.sh "$TAG" --publish-when-whole .release-files', last["run"])
        self.assertIn("gh workflow run publish-release.yml", last["run"])
        # The tag is never written into a script: it reaches each step by its environment.
        for s in steps:
            self.assertNotIn("${{ inputs.tag }}", str(s.get("run") or ""))
        # Every action in it is pinned by commit.
        for s in steps:
            if "uses" in s:
                self.assertRegex(s["uses"], r"@[0-9a-f]{40}$")
        # No other workflow names the marker, so the controller starts this one alone.
        for name in sorted(os.listdir(WF)):
            if name != "seal-release.yml":
                with open(os.path.join(WF, name), encoding="utf-8") as f:
                    self.assertNotIn("bb-release-seal-", f.read(), name)
        with open(os.path.join(WF, "seal-release.yml"), encoding="utf-8") as f:
            self.assertNotIn("bb-release-apk-", f.read(), "it hands over no APK, and must not read as a workflow that does")

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
        # The seal's own steps, dry: the pinned library, then the list made
        # and signed with a key of the run's own and verified, with no
        # secret read and no environment named.
        m = jobs["manifest"]
        self.assertNotIn("environment", m)
        self.assertNotIn("${{ secrets.", str(m))
        lib = next(s for s in m["steps"] if s.get("id") == "lib")
        seal = next(s for s in m["steps"] if s.get("id") == "seal")
        self.assertEqual(lib["run"], 'bash tools/release-lib.sh "$RUNNER_TEMP/release-lib"')
        self.assertLess(m["steps"].index(lib), m["steps"].index(seal))
        for part in ("secrets.token_hex(32)", "tools/release-sign.py signer >", '--from "$dry/files" --signers "$dry/release-signers"',
                     'ssh-keygen -Y verify -f "$dry/release-signers" -I aerieos-dev -n aerieos-dev',
                     "if ssh-keygen -Y verify -f config/release-signers"):
            self.assertIn(part, seal["run"])
        self.assertNotIn("--attested", seal["run"])
        say = m["steps"][-1]
        self.assertEqual(say["env"]["SEAL"], "${{ steps.seal.outcome }}")
        self.assertIn('[ "$SEAL" = success ] ||', say["run"])
        # The files a release gains after its run are not counted against it.
        self.assertIn("aerieos-image-*.digest|SHA256SUMS|SHA256SUMS.sig) later+=", say["run"])

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
