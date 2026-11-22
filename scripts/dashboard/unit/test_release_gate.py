"""Nothing is published that the checks have not passed (R206; the audit of
13 Nov, the operator's choices of 14 Nov): a release's tag runs the place
check, aerie lint with the unit tier, and every browser suite, and each job
that pushes an image or makes or fills a release waits for all three. A tag
ran none of them, CI's lint was its own copy of seven of aerie lint's
checks, no workflow ran the unit tier, and the suites ran only for a change
under scripts/dashboard. The workflows' own shape, read as YAML."""
import hashlib
import os
import shutil
import subprocess
import tempfile
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

    def test_the_job_that_holds_the_key_asks_the_default_branch_s_rule_first(self):
        # The audit of 21 Nov: a dev build's tag passed on any commit, and
        # the rule that said so was the tag's own copy. Each job that holds
        # the key takes the default branch's copy of the rule and its list
        # of branches and asks it, in steps before the one that holds the
        # key and that hold no secret themselves.
        for name, job_name, tag in (("build-image.yml", "signature", "${{ github.ref_name }}"), ("seal-release.yml", "seal", "${{ inputs.tag }}")):
            steps = load(name)["jobs"][job_name]["steps"]
            key = next(i for i, s in enumerate(steps) if "secrets.AERIEOS_RELEASE_KEY" in str(s))
            took = next(i for i, s in enumerate(steps) if (s.get("with") or {}).get("path") == "trusted")
            asked = next(i for i, s in enumerate(steps) if "release-place.sh" in str(s.get("run") or ""))
            self.assertLess(took, asked, name)
            self.assertLess(asked, key, f"{name}: asked before the key is in any step's environment")
            self.assertEqual(steps[took]["with"]["ref"], "${{ github.event.repository.default_branch }}", name)
            self.assertEqual(steps[took]["with"]["sparse-checkout"].split(), ["tools/release-place.sh", "tools/release-branches"], name)
            self.assertRegex(steps[took]["uses"], r"^actions/checkout@[0-9a-f]{40}$")
            run = steps[asked]["run"]
            self.assertIn("rule=trusted/tools", run)
            # A default branch without the rule signs nothing: the tag's own copy is never asked.
            self.assertNotIn("rule=tools", run, name)
            self.assertIn("exit 1", run.split("fi")[0], name)
            self.assertIn('bash "$rule/release-place.sh" "$TAG" "$GITHUB_SHA" origin/main "$rule/release-branches"', run)
            self.assertIn("git fetch --no-tags origin '+refs/heads/*:refs/remotes/origin/*'", run, "the branches as the remote holds them")
            self.assertEqual(steps[asked]["env"], {"TAG": tag}, "the tag reaches the script by its environment")
            for s in steps[:key]:
                self.assertNotIn("secrets.", str(s), f"{name}: nothing before the key's step holds a secret")
            # The tag's own checkout is whole, so a commit's place on a branch can be told.
            own = next(s for s in steps if str(s.get("uses", "")).startswith("actions/checkout@") and (s.get("with") or {}).get("path") is None)
            self.assertEqual(own["with"]["fetch-depth"], 0, name)
        # The tag's first check reads every branch head too, and a rehearsal says it and never fails on it.
        self.assertIn("'+refs/heads/*:refs/remotes/origin/*'", runs(load("build-image.yml")["jobs"]["place"]))
        self.assertIn('bash tools/release-place.sh "v${base}-dev.1" "$GITHUB_SHA" origin/main \\\n', runs(load("release-rehearsal.yml")["jobs"]["place"]).replace("\\\n", "\\\n"))
        self.assertIn("|| echo \"::notice title=No dev build from this commit", runs(load("release-rehearsal.yml")["jobs"]["place"]))

    def test_a_release_s_app_is_built_where_no_pull_request_s_job_runs(self):
        # The runner a pull request's lint and suites run on built the APK
        # a release carries. A tag's own run builds it on a hosted runner.
        build = load("android-app.yml")["jobs"]["build"]
        self.assertEqual(build["runs-on"], "${{ fromJSON(((github.event_name == 'push' && startsWith(github.ref, 'refs/tags/v')) || inputs.hosted) "
                                           "&& '[\"ubuntu-24.04\"]' || '[\"self-hosted\", \"bb-sandbox\"]') }}")
        # ...and a rehearsal builds it there too, so the first tag is not the first hosted build.
        on = load("android-app.yml")["on"]
        for how in ("workflow_dispatch", "workflow_call"):
            self.assertEqual((on[how]["inputs"]["hosted"]["type"], on[how]["inputs"]["hosted"]["default"]), ("boolean", False), how)
        self.assertEqual(load("release-rehearsal.yml")["jobs"]["android"]["with"], {"hosted": True, "rehearse": True})
        # ...and hands its unsigned APK to the rehearsal's dry seal alone,
        # under a name the controller never fetches, which signs it with a
        # key of its own and has the seal hold it to that key on the
        # runner's apksigner, as a tag's seal does (v0.9.0-dev.6049's found
        # no signer in build-tools 37's way of saying one).
        steps = load("android-app.yml")["jobs"]["build"]["steps"]
        given = next(x for x in steps if x.get("name") == "Hand the unsigned APK to the rehearsal's dry seal")
        self.assertEqual((given["if"], given["with"]["name"]), ("inputs.rehearse && steps.name.outputs.tag == ''", "rehearsal-apk"))
        self.assertNotIn("bb-release-apk-", given["with"]["name"])
        seal = next(x for x in load("release-rehearsal.yml")["jobs"]["manifest"]["steps"] if x.get("id") == "seal")
        for said in ('"$aps" sign --ks "$RUNNER_TEMP/rehearsal.ks"', 'signers=(--apk-signers "$dry/apk-signers")',
                     "(apksigner verifies it as signed by a certificate config/apk-signers names)",
                     "is signed by a certificate config/apk-signers does not name"):
            self.assertIn(said, seal["run"])
        # Every file the build resolves is held to its sha256 (the audit of
        # 21 Nov: nothing held the release APK's Gradle dependencies to
        # their bytes): each plugin and library the build files name is in
        # the verification metadata, each artifact with a sha256 and none
        # trusted by a rule in its place.
        import re
        import xml.etree.ElementTree as ET
        android = os.path.join(WF, "..", "..", "apps", "android")
        meta = ET.parse(os.path.join(android, "gradle", "verification-metadata.xml")).getroot()
        ns = {"v": "https://schema.gradle.org/dependency-verification"}
        self.assertEqual(meta.find("v:configuration/v:verify-metadata", ns).text, "true")
        self.assertIsNone(meta.find("v:configuration/v:trusted-artifacts", ns), "no artifact trusted by a pattern")
        held = {(c.get("group"), c.get("name"), c.get("version")) for c in meta.find("v:components", ns)}
        for c in meta.find("v:components", ns):
            for a in c.findall("v:artifact", ns):
                self.assertTrue(a.findall("v:sha256", ns), f"{c.get('name')} {a.get('name')} is held to a sha256")
        named = ""
        for f in ("build.gradle.kts", os.path.join("app", "build.gradle.kts")):
            with open(os.path.join(android, f), encoding="utf-8") as fh:
                named += fh.read()
        plugins = re.findall(r'id\("([\w.]+)"\) version "([\w.-]+)"', named)
        self.assertTrue(plugins)
        for pid, ver in plugins:
            self.assertIn((pid, f"{pid}.gradle.plugin", ver), held, pid)
        libs = re.findall(r'implementation\("([\w.-]+):([\w.-]+):([\w.-]+)"\)', named)
        self.assertTrue(libs)
        for lib in libs:
            self.assertIn(lib, held, ":".join(lib))
        java = next(s for s in build["steps"] if "JAVA_HOME_17_X64" in str(s.get("run") or ""))
        self.assertEqual(java["if"], "runner.environment == 'github-hosted'")
        land = next(s for s in build["steps"] if s.get("name", "").startswith("Land it in"))
        self.assertEqual(land["if"], "runner.environment == 'self-hosted'")
        # Every job a pull request starts on the self-hosted runner refuses a fork's.
        for name in ("lint.yml", "dashboard.yml"):
            wf = load(name)
            self.assertIn("pull_request", wf["on"])
            for job, body in wf["jobs"].items():
                if "self-hosted" in str(body.get("runs-on")):
                    self.assertEqual(body["if"], "github.event_name != 'pull_request' || github.event.pull_request.head.repo.full_name == github.repository", f"{name} {job}")
        # ...and no other workflow that runs there is started by a pull request.
        for name in sorted(os.listdir(WF)):
            wf = load(name)
            if name not in ("lint.yml", "dashboard.yml") and "self-hosted" in str(wf["jobs"]):
                self.assertNotIn("pull_request", wf["on"], name)
                self.assertNotIn("pull_request_target", wf["on"], name)

    def test_a_branch_s_build_never_takes_a_release_s_image_tag(self):
        # A run by hand from a branch called dev, latest or 0.9 pushed its
        # image under the tag people follow.
        build = load("build-image.yml")["jobs"]["build"]
        meta = next(s for s in build["steps"] if s.get("id") == "meta")["with"]
        tags = [ln.strip() for ln in meta["tags"].splitlines() if ln.strip() and not ln.strip().startswith("#")]
        self.assertEqual(tags, ["type=raw,value=main,enable=${{ github.ref == 'refs/heads/main' }}",
                                "type=ref,event=branch,prefix=branch-,enable=${{ github.ref != 'refs/heads/main' }}",
                                "type=ref,event=pr", "type=sha,format=short", "type=schedule,pattern={{date 'YYYYMMDD'}}",
                                "type=semver,pattern={{version}}"])
        self.assertEqual(meta["flavor"], "latest=false")

    def test_the_iso_and_the_stick_are_held_to_what_their_build_put_out_before_they_are_attested(self):
        osi = load("os-image.yml")
        outs = osi["on"]["workflow_call"]["outputs"]
        self.assertEqual({k: v["value"] for k, v in outs.items()},
                         {"iso-sha256": "${{ jobs.appliance.outputs.iso }}", "stick-sha256": "${{ jobs.appliance.outputs.stick }}"})
        job = osi["jobs"]["appliance"]
        self.assertEqual(job["outputs"], {"iso": "${{ steps.sums.outputs.iso }}", "stick": "${{ steps.sums.outputs.stick }}"})
        sums = next(i for i, s in enumerate(job["steps"]) if s.get("id") == "sums")
        up = next(i for i, s in enumerate(job["steps"]) if (s.get("with") or {}).get("name") == "aerieos-os")
        self.assertLess(sums, up, "hashed where it was built, before it leaves the job")
        last = load("build-image.yml")["jobs"]["release"]
        held = next(i for i, s in enumerate(last["steps"]) if s.get("name", "").startswith("The ISO and the stick are the files"))
        att = next(i for i, s in enumerate(last["steps"]) if s.get("id") == "attest")
        self.assertLess(held, att)
        self.assertEqual(last["steps"][held]["env"], {"ISO": "${{ needs.appliance.outputs.iso-sha256 }}", "STICK": "${{ needs.appliance.outputs.stick-sha256 }}"})
        # The step itself, run on a folder: the files the build hashed pass, and a file changed on the way does not.
        d = tempfile.mkdtemp()
        self.addCleanup(shutil.rmtree, d, True)
        os.makedirs(os.path.join(d, "out"))
        for name, body in (("aerieos-os-1.2.3.iso", b"an iso"), ("aerieos-os-1.2.3.stick.raw.xz", b"a stick")):
            with open(os.path.join(d, "out", name), "wb") as f:
                f.write(body)
        env = dict(os.environ, ISO=hashlib.sha256(b"an iso").hexdigest(), STICK=hashlib.sha256(b"a stick").hexdigest())
        run = lambda e: subprocess.run(["bash", "-c", last["steps"][held]["run"]], cwd=d, env=e, capture_output=True, text=True, check=False)  # noqa: E731
        self.assertEqual(run(env).returncode, 0, run(env).stderr)
        for bad in (dict(env, ISO=hashlib.sha256(b"another iso").hexdigest()), dict(env, STICK=""), dict(env, ISO="not a digest")):
            r = run(bad)
            self.assertEqual(r.returncode, 1, r.stdout)
            self.assertIn("::error::", r.stdout)
        with open(os.path.join(d, "out", "aerieos-os-1.2.3.iso"), "wb") as f:
            f.write(b"an iso, changed in the artifact store")
        self.assertIn("is not the ISO as the OS image's build made it", run(env).stdout)

    def test_what_a_job_that_holds_a_secret_installs_is_held_to_a_hash_and_a_rehearsal_holds_none(self):
        # The companion's Windows job holds the code-signing certificate and attests the two .exe.
        build = load("companion-app.yml")["jobs"]["build"]
        text = runs(build)
        self.assertIn("--require-hashes --only-binary :all:", text)
        self.assertIn("-r tools/companion-requirements.txt", text)
        self.assertNotRegex(text, r"pip install[^\n]*\bpyinstaller\b")
        with open(os.path.join(WF, "..", "..", "tools", "companion-requirements.txt"), encoding="utf-8") as f:
            lines = [ln.rstrip() for ln in f if ln.strip() and not ln.startswith("#")]
        names = [ln.split("==")[0] for ln in lines if not ln.startswith(" ")]
        self.assertIn("pyinstaller", names)
        for i, ln in enumerate(lines):
            if not ln.startswith(" "):
                self.assertRegex(ln, r"^[a-z0-9-]+==[0-9][0-9A-Za-z.]*( \\)?$", ln)
                self.assertRegex(lines[i + 1], r"^    --hash=sha256:[0-9a-f]{64}( \\)?$", f"{ln}: held to a hash")
        # A rehearsal runs from any branch and is handed no secret, as its header says.
        wf = load("release-rehearsal.yml")
        for name, job in wf["jobs"].items():
            self.assertNotIn("secrets", job, name)
            self.assertNotIn("${{ secrets.", str(job), name)
        self.assertEqual(list(wf["on"]), ["workflow_dispatch"])
        # ...and the certificate is no repository secret any run is handed:
        # the Windows job reads it from the windows-signing environment,
        # which it names on a tag's ref alone and which admits v* tags.
        self.assertNotIn("secrets", load("build-image.yml")["jobs"]["apps"])
        companion = load("companion-app.yml")
        self.assertNotIn("secrets", companion["on"]["workflow_call"])
        self.assertEqual(build["environment"], "${{ startsWith(github.ref, 'refs/tags/v') && 'windows-signing' || '' }}")
        for name, job in companion["jobs"].items():
            if name != "build":
                self.assertNotIn("${{ secrets.", str(job), name)
                self.assertNotIn("environment", job, name)
        with open(os.path.join(WF, "..", "..", "docs", "versions.md"), encoding="utf-8") as f:
            self.assertIn("New environment\n  `windows-signing`", f.read())

    @unittest.skipUnless(shutil.which("ssh-keygen"), "ssh-keygen is not here")
    def test_the_tags_people_follow_move_onto_a_published_sealed_release_s_own_digest(self):
        # publish-release.yml's step, run with gh and docker stood in: the
        # tags move only for a release that is published and whose signed
        # list names the image, and onto that digest, never onto whatever
        # the registry serves under the version's tag.
        wf = load("publish-release.yml")
        steps = wf["jobs"]["follow"]["steps"]
        self.assertEqual(steps[0]["with"]["sparse-checkout"].split(), ["config/release-signers"])
        step = steps[-1]
        self.assertEqual(step["env"], {"TAG": "${{ github.event.release.tag_name || inputs.tag }}", "GH_TOKEN": "${{ github.token }}"})
        d = tempfile.mkdtemp()
        self.addCleanup(shutil.rmtree, d, True)
        os.makedirs(os.path.join(d, "bin"))
        os.makedirs(os.path.join(d, "config"))
        os.makedirs(os.path.join(d, "served"))
        digest = "sha256:" + "ab" * 32
        img = "ghcr.io/aquilaelabs/aerieos"

        def key(who):
            path = os.path.join(d, who)
            subprocess.run(["ssh-keygen", "-q", "-t", "ed25519", "-N", "", "-C", who, "-f", path], check=True, stdin=subprocess.DEVNULL)
            with open(path + ".pub") as f:
                return path, " ".join(f.read().split()[:2])
        dev, rel, stranger = key("key-dev"), key("key-stable"), key("key-stranger")
        with open(os.path.join(d, "config", "release-signers"), "w") as f:
            f.write(f'aerieos-dev namespaces="aerieos-dev" {dev[1]}\naerieos-release namespaces="aerieos-release" {rel[1]}\n')
        with open(os.path.join(d, "bin", "gh"), "w") as f:
            f.write(f"""#!/bin/bash
case "$1 $2" in
  "release view") [ -f "{d}/draft" ] && echo true || {{ [ -d "{d}/served" ] && echo false; }} ;;
  "release download")
    dir=""; while [ $# -gt 0 ]; do [ "$1" = --dir ] && dir="$2"; shift; done
    cp "{d}"/served/* "$dir"/ 2>/dev/null; exit 0 ;;
esac
""")
        with open(os.path.join(d, "bin", "docker"), "w") as f:
            f.write(f'#!/bin/bash\necho "$*" >> "{d}/docker.log"\n')
        for n in ("gh", "docker"):
            os.chmod(os.path.join(d, "bin", n), 0o755)

        def seal(ver, who, ns, ref=None, listed=True):
            served = os.path.join(d, "served")
            shutil.rmtree(served)
            os.makedirs(served)
            name = f"aerieos-image-{ver}.digest"
            with open(os.path.join(served, name), "w") as f:
                f.write((ref or f"{img}@{digest}") + "\n")
            with open(os.path.join(served, name), "rb") as f:
                h = hashlib.sha256(f.read()).hexdigest()
            with open(os.path.join(served, "SHA256SUMS"), "w") as f:
                f.write((f"{h}  {name}\n" if listed else "") + "c" * 64 + "  another.bin\n")
            subprocess.run(["ssh-keygen", "-Y", "sign", "-q", "-f", who[0], "-n", ns, os.path.join(served, "SHA256SUMS")], check=True,
                           stdin=subprocess.DEVNULL, capture_output=True)

        def move(tag):
            log = os.path.join(d, "docker.log")
            if os.path.exists(log):
                os.unlink(log)
            env = dict(os.environ, TAG=tag, GH_TOKEN="t", REGISTRY="ghcr.io", IMAGE_NAME="aquilaelabs/AerieOS", GITHUB_REPOSITORY="aquilaelabs/aerieos",
                       GITHUB_STEP_SUMMARY=os.path.join(d, "summary"), PATH=os.path.join(d, "bin") + ":" + os.environ["PATH"])
            r = subprocess.run(["bash", "-c", step["run"]], cwd=d, env=env, capture_output=True, text=True, check=False)
            shutil.rmtree(os.path.join(d, "rel"), ignore_errors=True)
            made = [ln for ln in (open(log).read().splitlines() if os.path.exists(log) else []) if "imagetools create" in ln]
            return r.returncode, r.stdout + r.stderr, made
        # A dev build, sealed by the dev key: :dev moves onto the digest its list names.
        seal("0.9.1-dev.7", dev, "aerieos-dev")
        rc, said, made = move("v0.9.1-dev.7")
        self.assertEqual((rc, made), (0, [f"buildx imagetools create -t {img}:dev {img}@{digest}"]), said)
        # A stable release, sealed by its own key: :dev, :latest and :0.9.
        seal("0.9.1", rel, "aerieos-release")
        rc, said, made = move("v0.9.1")
        self.assertEqual((rc, [m.split(" -t ")[1] for m in made]), (0, [f"{img}:{t} {img}@{digest}" for t in ("dev", "latest", "0.9")]), said)
        # What moves nothing, each said: a draft; a stable release sealed by
        # the dev key; a stranger's signature; a list that does not name the
        # digest file; a digest file naming another image or a tag; no list.
        for setup, why in ((lambda: (seal("0.9.1", rel, "aerieos-release"), open(os.path.join(d, "draft"), "w").close()), "has no published release"),
                           (lambda: seal("0.9.1", dev, "aerieos-dev"), "is signed by no key config/release-signers names for it"),
                           (lambda: seal("0.9.1", stranger, "aerieos-release"), "is signed by no key"),
                           (lambda: seal("0.9.1", rel, "aerieos-release", listed=False), "is not the file v0.9.1's signed list names"),
                           (lambda: seal("0.9.1", rel, "aerieos-release", ref=f"ghcr.io/someone/else@{digest}"), "which is not ghcr.io/aquilaelabs/aerieos by a digest"),
                           (lambda: seal("0.9.1", rel, "aerieos-release", ref=f"{img}:0.9.1"), "which is not ghcr.io/aquilaelabs/aerieos by a digest"),
                           (lambda: (shutil.rmtree(os.path.join(d, "served")), os.makedirs(os.path.join(d, "served"))), "it is not sealed")):
            if os.path.exists(os.path.join(d, "draft")):
                os.unlink(os.path.join(d, "draft"))
            setup()
            rc, said, made = move("v0.9.1")
            self.assertEqual((rc, made), (1, []), said)
            self.assertIn(why, said)
        # Nothing follows the version's own tag in the registry any more.
        self.assertNotIn('"$img:$ver"', step["run"])

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
                steps = body.get("steps") or []
                for i, s in enumerate(steps):
                    if not str(s.get("uses", "")).startswith("actions/attest-build-provenance@") or s["id"].endswith("-again"):
                        continue
                    self.assertRegex(s["uses"], r"@[0-9a-f]{40}$", "pinned by commit")
                    perms = body["permissions"]
                    self.assertEqual((perms.get("id-token"), perms.get("attestations")), ("write", "write"), f"{name} {job}")
                    # Asked once more after a wait where the transparency
                    # log did not answer (v0.9.0-dev.6094): the same files,
                    # by the same action, only where the first failed.
                    self.assertIs(s["continue-on-error"], True, f"{name} {job}")
                    wait, again = steps[i + 1], steps[i + 2]
                    first = f"steps.{s['id']}.outcome == 'failure'"
                    self.assertEqual(wait["run"], "sleep 60")
                    self.assertEqual((again["id"], again["uses"], again["with"]), (s["id"] + "-again", s["uses"], s["with"]))
                    for later in (wait, again):
                        self.assertEqual(later["if"], f"{s['if']} && {first}" if s.get("if") else first, f"{name} {job}")
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
        bundle = {s.get("id"): s for s in load("build-image.yml")["jobs"]["bundle"]["steps"]}
        self.assertEqual(bundle["attest-bundle"]["with"], {"subject-path": "${{ steps.pack.outputs.name }}"})
        # The release is made with the bundle of whichever asking answered.
        made = next(s for s in load("build-image.yml")["jobs"]["release"]["steps"] if s.get("name") == "Make the release, with every file and the notes")
        self.assertEqual(made["env"]["BUNDLE"], "${{ steps.attest-again.outputs.bundle-path || steps.attest.outputs.bundle-path }}")
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
        self.assertIn('python3 tools/release-sign.py seal "$TAG" --commit "$GITHUB_SHA" --wait 600 --out "$RUNNER_TEMP/sealed"', text)
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
