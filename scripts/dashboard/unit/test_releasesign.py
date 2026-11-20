"""releasesign.py (R106): a release's APK built unsigned in CI and signed on
the project's node with its sideload key. Against a stand-in for
GitHub's API, its artifact storage and its upload host on a local port: the
run's bb-release-apk-TAG artifact is fetched (its storage never handed the
token), each APK signed and attached under its name less -unsigned with its
sha256 and a notes line giving the key's fingerprint, a second look signs
nothing twice, and a failure is kept for the bell and signed again on a
press. Only the tag's own run is signed from (a pull request's, a fork's, a
branch's, one by hand, one of another workflow and one on another commit
are each refused with the reason), and a release that carries its signed
APK is signed again only for a tag a person names. What would stop a
release is said before it: no key, an app mapped
to none of several, the project's node offline or without its tools. Once
an APK is attached, the project's workflows that sign the release's list of
files are started for the tag, and one that could not be is said with what
a person does instead. Where
a toolchain store with the jdk and build-tools is here, a real APK is signed
end to end by the real agent's side of the job (signnode.py)."""
import glob
import hashlib
import io
import json
import os
import re
import shutil
import subprocess
import sys
import tempfile
import threading
import time
import unittest
import zipfile
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))
import cilogs  # noqa: E402
import forgerelease  # noqa: E402
import releasesign  # noqa: E402
import signing  # noqa: E402
import signnode  # noqa: E402

SEEN = []
REL = {}
# What the stand-in says of runs beyond its four: a tag's own run, still
# going or ended, with the APK it handed over (R206 step 1).
MORE = []
# The artifacts each run handed over, by run; the commit each tag names, and
# the tags that are annotated (their ref names a tag object, which names it).
ARTS = {}
TAGS = {}
ANNOTATED = set()
C7, C8 = "7" * 40, "8" * 40
# The workflow that builds the APK: started by a release, and called as a
# job of the tag's own run, which is how a release that makes itself in CI
# hands its APK over (build-image.yml calling android-app.yml).
FLOW = """name: android app
on:
  release: {types: [published]}
  workflow_call: {inputs: {tag: {type: string, default: ""}}}
jobs:
  build:
    runs-on: ubuntu-24.04
    steps:
      - uses: actions/upload-artifact@cf430e030ddbb5b0abf93d22962f4752f3646cd9   # v7.0.2
        with:
          name: bb-release-apk-${{ github.event.release.tag_name || inputs.tag }}
"""
TAGRUN = """name: release
on: {push: {tags: ["v*"]}}
jobs:
  # uses: ./.github/workflows/lint.yml
  android:
    uses: ./.github/workflows/android.yml
    with: {tag: "${{ github.ref_name }}"}
"""
BUILDS, RELEASES = ".github/workflows/android.yml", ".github/workflows/release.yml"


def run(rid, tag, **over):
    """A run as GitHub lists the one a tag's push starts: the event, the tag
    as its head_branch, the tag's commit, the file of the workflow the push
    started (the caller of the one that uploads), and the repository itself
    as where its commit came from."""
    return {"id": rid, "event": "push", "head_branch": tag, "head_sha": TAGS.get(tag, "0" * 40), "path": RELEASES,
            "status": "completed", "conclusion": "success", "run_attempt": 1,
            "repository": {"full_name": "o/app"}, "head_repository": {"full_name": "o/app"}} | over


def handed(tag):
    return [{"id": 77, "name": f"bb-release-apk-{tag}", "expired": False}]
GRADLE = 'android {\n    defaultConfig {\n        applicationId = "dev.example.app"\n    }\n}\n'


def artifact_zip():
    b = io.BytesIO()
    with zipfile.ZipFile(b, "w") as z:
        z.writestr("app-0.7.0-unsigned.apk", b"unsigned apk bytes")
    return b.getvalue()


class GitHub(BaseHTTPRequestHandler):
    def log_message(self, *a):
        pass

    def answer(self, body, code=200, raw=None, ctype="application/json"):
        data = raw if raw is not None else json.dumps(body).encode()
        self.send_response(code)
        self.send_header("Content-Type", ctype)
        self.send_header("Content-Length", str(len(data)))
        self.end_headers()
        self.wfile.write(data)

    def do_GET(self):
        p = self.path
        SEEN.append(("GET", p, self.headers.get("Authorization")))
        if p.startswith("/storage/"):
            # GitHub's storage host: it must never be handed the token.
            return self.answer(None, raw=artifact_zip(), ctype="application/zip")
        if self.headers.get("Authorization") != "Bearer tok":
            return self.answer({"message": "Bad credentials"}, 401)
        if p.startswith("/repos/o/app/actions/runs?"):
            now = time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime())
            hour = time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime(time.time() - 3600))
            main = {"head_branch": "main", "head_sha": "a" * 40, "path": BUILDS}
            # v0.7.0's own run is its release's, of the workflow that builds
            # the APK; the rest are a run by hand, two pushes to main and a
            # release too old to hold anything.
            return self.answer({"workflow_runs": [
                *[{**m, "created_at": now, "updated_at": now} for m in MORE],
                run(22, "", event="workflow_dispatch", created_at=now, updated_at=now, **main),
                run(21, "v0.7.0", event="release", path=BUILDS, created_at=now),
                run(20, "", created_at=hour, updated_at=hour, **main),
                run(19, "", created_at=now, updated_at=now, conclusion="failure", **main),
                run(9, "v0.1.0", event="release", path=BUILDS, created_at="2020-01-01T00:00:00Z")]})
        if m := re.match(r"/repos/o/app/actions/runs/(\d+)/artifacts", p):
            return self.answer({"artifacts": ARTS.get(int(m.group(1)), [])})
        # A tag's ref: the commit, or for an annotated tag the tag object
        # that names it.
        if p.startswith("/repos/o/app/git/ref/tags/"):
            tag = p.rsplit("/", 1)[-1]
            if tag not in TAGS:
                return self.answer({"message": "Not Found"}, 404)
            obj = {"type": "tag", "sha": "b" * 40} if tag in ANNOTATED else {"type": "commit", "sha": TAGS[tag]}
            return self.answer({"ref": f"refs/tags/{tag}", "object": obj})
        if p == "/repos/o/app/git/tags/" + "b" * 40:
            return self.answer({"tag": sorted(ANNOTATED)[0], "object": {"type": "commit", "sha": TAGS[sorted(ANNOTATED)[0]]}})
        if p == "/repos/o/app/actions/artifacts/77/zip":
            self.send_response(302)
            self.send_header("Location", f"http://127.0.0.1:{self.server.server_address[1]}/storage/77.zip")
            self.send_header("Content-Length", "0")
            self.end_headers()
            return None
        if p.startswith("/repos/o/app/releases/tags/"):
            tag = p.rsplit("/", 1)[-1]
            return self.answer(REL[tag]) if tag in REL else self.answer({"message": "Not Found"}, 404)
        if p.startswith("/repos/o/app/releases?"):
            # The listed releases, where a draft is looked for by its tag.
            return self.answer([r for r in REL.values() if r.get("tag_name")])
        return self.answer({"message": "Not Found"}, 404)

    def do_POST(self):
        n = int(self.headers.get("Content-Length") or 0)
        raw = self.rfile.read(n)
        SEEN.append(("POST", self.path, raw))
        if self.path.startswith("/repos/o/app/releases/7/assets?name="):
            name = self.path.split("name=", 1)[1]
            REL["v0.7.0"]["assets"].append({"id": len([1 for m, _, _ in SEEN if m == "POST"]) + 100, "name": name})
            return self.answer({"id": 1, "browser_download_url": f"https://github.com/o/app/{name}"}, 201)
        if self.path.startswith("/repos/o/app/releases/8/assets?name="):
            name = self.path.split("name=", 1)[1]
            rel = next(r for r in REL.values() if r["id"] == 8)
            rel["assets"].append({"id": len(rel["assets"]) + 200, "name": name})
            return self.answer({"id": 2, "browser_download_url": f"https://github.com/o/app/{name}"}, 201)
        return self.answer({"message": "Not Found"}, 404)

    def do_PATCH(self):
        n = int(self.headers.get("Content-Length") or 0)
        b = json.loads(self.rfile.read(n))
        SEEN.append(("PATCH", self.path, b))
        rel = next(r for r in REL.values() if r["id"] == (8 if self.path.endswith("/releases/8") else 7))
        rel["body"] = b["body"]
        return self.answer(rel)

    def do_DELETE(self):
        SEEN.append(("DELETE", self.path, None))
        aid = int(self.path.rsplit("/", 1)[-1])
        REL["v0.7.0"]["assets"] = [a for a in REL["v0.7.0"]["assets"] if a["id"] != aid]
        self.send_response(204)
        self.end_headers()


class Base(unittest.TestCase):
    def setUp(self):
        SEEN.clear(); REL.clear(); MORE.clear(); ARTS.clear(); TAGS.clear(); ANNOTATED.clear()
        releasesign._bare.clear()
        TAGS.update({"v0.7.0": C7, "v0.8.0": C8, "v0.1.0": "1" * 40})
        ARTS.update({19: handed("v0.6.0"), 31: handed("v0.8.0"),
                     21: [*handed("v0.7.0"), {"id": 78, "name": "something-else", "expired": False}]})
        REL["v0.7.0"] = {"id": 7, "html_url": "https://github.com/o/app/releases/tag/v0.7.0",
                         "body": "### Added\n\n- A thing", "assets": []}
        self.srv = ThreadingHTTPServer(("127.0.0.1", 0), GitHub)
        threading.Thread(target=self.srv.serve_forever, daemon=True).start()
        self.addCleanup(self.srv.server_close)
        self.addCleanup(self.srv.shutdown)
        self.tmp = Path(tempfile.mkdtemp())
        self.addCleanup(shutil.rmtree, self.tmp, True)
        app = self.tmp / "ws" / "app"
        (app / ".github" / "workflows").mkdir(parents=True)
        (app / ".github" / "workflows" / "android.yml").write_text(FLOW)
        (app / ".github" / "workflows" / "release.yml").write_text(TAGRUN)
        (app / "app").mkdir()
        (app / "app" / "build.gradle.kts").write_text(GRADLE)
        (self.tmp / "gitcreds").mkdir()
        (self.tmp / "gitcreds" / "app").write_text("https://x:tok@github.com\n")

        def wj(path, d):
            Path(path).parent.mkdir(parents=True, exist_ok=True)
            Path(path).write_text(json.dumps(d))
        cilogs.configure(state=self.tmp, workspace=self.tmp / "ws",
                         push_record_fn={"app": {"repo": "o/app", "host": "github.com"}}.get)
        forgerelease.configure(state=self.tmp, workspace=self.tmp / "ws", write_json_fn=wj)
        releasesign.configure(state=self.tmp, workspace=self.tmp / "ws", write_json_fn=wj, projects=lambda: ["app"])
        signing.configure(state=self.tmp / "state", project_name=re.compile(r"[A-Za-z0-9._-]+"))
        # The token the look asks GitHub with, named here rather than read
        # through gitcreds, whose state another module in the tier leaves
        # pointed elsewhere: without it check() ends before the overdue
        # expectation is marked, and attention() had no row (B642).
        from unittest import mock
        tok = mock.patch.object(cilogs, "_token", lambda project, uid=None: "tok")
        tok.start()
        self.addCleanup(tok.stop)
        # The project's node, there and ready unless a test says otherwise.
        for k in ("node_of", "node_get", "node_tools", "node_refuses"):
            self.addCleanup(setattr, signing, k, getattr(signing, k))
        signing.node_of = lambda p: "n_1"
        signing.node_get = signing.node_tools = signing.node_refuses = None
        base = f"http://127.0.0.1:{self.srv.server_address[1]}"
        for mod, k in ((cilogs, "API"), (forgerelease, "API"), (forgerelease, "UPLOADS")):
            self.addCleanup(setattr, mod, k, getattr(mod, k))
            setattr(mod, k, base)
        # A kept sideload key, as signing.py writes one (its keystore is not
        # opened here: sign_release is stood in for, below).
        self.key("default")
        self.signed, self.fail_why = [], ""

        def fake_sign(project, src, out):
            self.signed.append((project, Path(src).read_bytes()))
            if self.fail_why:
                return {"error": self.fail_why}
            Path(out).write_bytes(b"signed:" + Path(src).read_bytes())
            return {"key": "default", "cert": "AB:CD", "package": "dev.example.app", "schemes": ["v2"]}
        self.addCleanup(setattr, signing, "sign_release", signing.sign_release)
        signing.sign_release = fake_sign

    def key(self, name, sha="AB:CD"):
        d = self.tmp / "state" / "signing" / "app" / name
        d.mkdir(parents=True, exist_ok=True)
        (d / "sideload.ks").write_bytes(b"ks")
        (d / "sideload.json").write_text(json.dumps({"route": "sideload", "key": name, "alias": name,
                                                     "sha256": sha, "store_pass": "p"}))
        releasesign._cache.clear()


class Signs(Base):
    def test_the_runs_unsigned_apk_is_signed_and_attached_with_its_fingerprint(self):
        r = releasesign.check("app")
        self.assertEqual(r["signed"], ["v0.7.0"], r)
        self.assertEqual(self.signed, [("app", b"unsigned apk bytes")])
        # The storage host was never handed the token.
        self.assertEqual([a for m, p, a in SEEN if p.startswith("/storage/")], [None])
        ups = {p.split("name=", 1)[1]: raw for m, p, raw in SEEN if m == "POST"}
        self.assertEqual(sorted(ups), ["app-0.7.0.apk", "app-0.7.0.apk.sha256"])
        self.assertEqual(ups["app-0.7.0.apk"], b"signed:unsigned apk bytes")
        want = hashlib.sha256(b"signed:unsigned apk bytes").hexdigest()
        self.assertEqual(ups["app-0.7.0.apk.sha256"].decode(), f"{want}  app-0.7.0.apk\n")
        body = REL["v0.7.0"]["body"]
        self.assertIn("### Added\n\n- A thing", body)
        self.assertTrue(body.endswith("Signed by AerieOS: app-0.7.0.apk with the sideload key default, "
                                      "certificate SHA-256 AB:CD"), body)
        st = releasesign.status("app")
        self.assertEqual(st["signed"][0]["tag"], "v0.7.0")
        self.assertEqual(st["signed"][0]["cert"], "AB:CD")
        # The run older than an artifact is kept is not asked about.
        self.assertFalse([p for m, p, a in SEEN if "/runs/9/" in p])

    def test_a_second_look_signs_nothing_twice(self):
        releasesign.check("app")
        n = len(self.signed)
        asked = len([p for m, p, a in SEEN if "/runs/20/artifacts" in p])
        self.assertEqual(releasesign.check("app")["signed"], [])
        self.assertEqual(len(self.signed), n)
        # ...and a run that handed over nothing is not asked about again.
        self.assertEqual(len([p for m, p, a in SEEN if "/runs/20/artifacts" in p]), asked)

    def test_a_run_that_only_just_ended_is_asked_about_again(self):
        # GitHub can list a run as ended before it lists its artifact (B467).
        releasesign.check("app")
        asked = len([p for m, p, a in SEEN if "/runs/22/artifacts" in p])
        releasesign.check("app")
        self.assertEqual(len([p for m, p, a in SEEN if "/runs/22/artifacts" in p]), asked + 1)

    def test_a_failed_signing_is_said_on_the_bell_and_signed_again_on_a_press(self):
        self.fail_why = "app-0.7.0-unsigned.apk: no key"
        r = releasesign.check("app")
        self.assertEqual(r["failed"], ["v0.7.0"])
        self.assertFalse([1 for m, _, _ in SEEN if m == "POST"], "nothing is attached when signing fails")
        rows = [a for a in releasesign.attention(["app"]) if a["bad"]]
        self.assertEqual(len(rows), 1)
        self.assertEqual((rows[0]["tag"], rows[0]["kind"]), ("v0.7.0", "release-sign"))
        self.assertIn("no key", rows[0]["why"])
        self.assertTrue(rows[0]["key"].startswith("rsign:app|v0.7.0@"))
        # Not tried again at once by the loop...
        self.assertEqual(releasesign.check("app")["failed"], [])
        # ...but on a press, and the red row goes once it is signed.
        self.fail_why = ""
        self.assertEqual(releasesign.check("app", force=True)["signed"], ["v0.7.0"])
        self.assertFalse([a for a in releasesign.attention(["app"]) if a["bad"]])
        self.assertFalse(releasesign.status("app")["failed"])

    def test_a_look_moves_the_token_as_it_starts_and_ends(self):
        # The Signing view re-reads on it, so a press is followed to its end
        # rather than read once a few seconds on, mid-look.
        was = releasesign.rev()
        self.assertTrue(releasesign._claim("app"))
        self.assertTrue(releasesign.status("app")["looking"])
        self.assertGreater(releasesign.rev(), was)
        mid = releasesign.rev()
        releasesign.check("app")
        releasesign._release("app")
        self.assertGreater(releasesign.rev(), mid)
        self.assertFalse(releasesign.status("app")["looking"])

    def test_a_release_whose_apk_never_came_is_said(self):
        # The look expect() starts on a thread of its own is the test's here,
        # as OneRun's are: run beside the test it saved the file over the
        # backdated expectation, and nothing was due (B921).
        self.addCleanup(setattr, releasesign, "check_soon", releasesign.check_soon)
        releasesign.check_soon = lambda *a, **k: False
        releasesign.expect("app", "v0.9.0")
        d = json.loads((self.tmp / "release-signing.json").read_text())
        d["app"]["expect"]["v0.9.0"] = int(time.time()) - releasesign.EXPECT_S - 5
        (self.tmp / "release-signing.json").write_text(json.dumps(d))
        releasesign.check("app")
        bad = [a for a in releasesign.attention(["app"]) if a["bad"]]
        self.assertEqual([a["tag"] for a in bad], ["v0.9.0"])
        self.assertIn("no run that passed handed over an unsigned APK", bad[0]["why"])
        self.assertIn("aerie ci-log", bad[0]["why"])

    def test_a_run_that_failed_hands_over_nothing(self):
        # Run 19 failed with an APK among its artifacts: never asked about.
        releasesign.check("app")
        self.assertFalse([p for m, p, a in SEEN if "/runs/19/" in p])
        self.assertNotIn("v0.6.0", [r["tag"] for r in releasesign.status("app").get("last", {}).get("runs", [])])


# A workflow that signs a release's list of its files: started by hand, and
# named for by its concurrency group, as AerieOS's seal-release.yml is.
SEALFLOW = """name: seal release
on:
  workflow_dispatch:
    inputs:
      tag: {required: true}
concurrency:
  group: bb-release-seal-${{ inputs.tag }}
jobs:
  seal:
    runs-on: ubuntu-24.04
    steps: [{run: "true"}]
"""


class Seals(Base):
    """Once a release's signed APK is attached, the workflows in the
    project's tree that sign its list of files are started for the tag."""

    def setUp(self):
        super().setUp()
        self.flows = self.tmp / "ws" / "app" / ".github" / "workflows"
        (self.flows / "seal.yml").write_text(SEALFLOW)
        self.started, self.answer = [], ({"dispatched": "seal.yml"}, 200)

        def dispatch(project, wf, ref, inputs):
            # Where the release stood when it was asked: the APK is on it.
            self.started.append((project, wf, ref, inputs, sorted(a["name"] for a in REL["v0.7.0"]["assets"])))
            return self.answer
        self.addCleanup(setattr, releasesign, "dispatch_fn", releasesign.dispatch_fn)
        releasesign.dispatch_fn = dispatch

    def test_the_sealing_workflow_is_started_for_the_tag_once_the_apk_is_attached(self):
        self.assertEqual(releasesign.sealing("app"), ["seal.yml"])
        self.assertEqual(releasesign.check("app")["signed"], ["v0.7.0"])
        self.assertEqual(self.started, [("app", "seal.yml", "v0.7.0", {"tag": "v0.7.0"}, ["app-0.7.0.apk", "app-0.7.0.apk.sha256"])])
        row = next(x for x in releasesign.status("app")["last"]["runs"] if x["tag"] == "v0.7.0")
        self.assertEqual((row["state"], row["why"]), ("signed", "seal.yml started to sign the release's list of files"))
        self.assertFalse(releasesign.status("app")["failed"])
        self.assertFalse([a for a in releasesign.attention(["app"]) if a["bad"]])
        # A look that signs nothing starts nothing.
        releasesign.check("app")
        self.assertEqual(len(self.started), 1)

    def test_one_that_could_not_be_started_is_said_with_what_a_person_does_instead(self):
        self.answer = ({"error": "the host said 403: Resource not accessible by personal access token"}, 400)
        self.assertEqual(releasesign.check("app")["signed"], ["v0.7.0"], "the APK is signed and attached all the same")
        st = releasesign.status("app")
        self.assertEqual(st["signed"][0]["tag"], "v0.7.0")
        want = ("v0.7.0's signed APK is attached, and its list of files is not signed yet: seal.yml (the host said 403: "
                "Resource not accessible by personal access token) could not be started for it. Start it by hand from the "
                "repository's Actions page: Run workflow, from the tag v0.7.0, with v0.7.0 as its tag")
        self.assertEqual(next(x for x in st["last"]["runs"] if x["tag"] == "v0.7.0")["why"], want)
        self.assertEqual([(f["tag"], f["why"]) for f in st["failed"]], [("v0.7.0", want)])
        rows = [a for a in releasesign.attention(["app"]) if a["bad"]]
        self.assertEqual([(a["tag"], a["sealing"], a["why"]) for a in rows], [("v0.7.0", True, want)])
        # Not started again by a later look, which signs nothing; the APK
        # signed again for the tag, with the workflow started, clears it.
        releasesign.check("app")
        self.assertEqual(len(self.started), 1)
        self.answer = ({"dispatched": "seal.yml"}, 200)
        self.assertEqual(releasesign.check("app", again="v0.7.0")["signed"], ["v0.7.0"])
        self.assertEqual(len(self.started), 2)
        self.assertFalse([a for a in releasesign.attention(["app"]) if a["bad"]])
        # A dispatch that raises is a row too, never the look's end.
        releasesign.dispatch_fn = lambda *a: 1 / 0
        self.assertEqual(releasesign.check("app", again="v0.7.0")["signed"], ["v0.7.0"])
        self.assertIn("seal.yml (ZeroDivisionError", releasesign.attention(["app"])[-1]["why"])

    def test_a_signing_that_failed_starts_nothing_and_is_a_plain_failure(self):
        self.fail_why = "app-0.7.0-unsigned.apk: no key"
        self.assertEqual(releasesign.check("app")["failed"], ["v0.7.0"])
        self.assertEqual(self.started, [])
        self.assertEqual([a["sealing"] for a in releasesign.attention(["app"]) if a["bad"]], [False])

    def test_only_a_workflow_that_names_the_group_and_is_started_by_hand_is_one(self):
        (self.flows / "seal.yml").write_text(SEALFLOW.replace("  workflow_dispatch:\n    inputs:\n      tag: {required: true}\n",
                                                              "  push: {tags: ['v*']}\n"))
        (self.flows / "notes.yml").write_text("# this one only mentions bb-release-seal-TAG and workflow_dispatch:\n"
                                              "on:\n  workflow_dispatch:\njobs: {}\n")
        self.assertEqual(releasesign.sealing("app"), [])
        self.assertEqual(releasesign.check("app")["signed"], ["v0.7.0"])
        self.assertEqual(self.started, [])
        row = next(x for x in releasesign.status("app")["last"]["runs"] if x["tag"] == "v0.7.0")
        self.assertEqual((row["state"], row["why"]), ("signed", ""), "a space with no such workflow is as it was")
        # ...and the one that hands over the APK is no sealing workflow, nor
        # the sealing one a workflow that hands one over.
        (self.flows / "seal.yml").write_text(SEALFLOW)
        self.assertEqual(releasesign.sealing("app"), ["seal.yml"])
        self.assertEqual(releasesign.handing("app"), {BUILDS, RELEASES})

    def test_a_release_that_keeps_its_apk_starts_nothing(self):
        REL["v0.7.0"]["body"] = "notes\n\nSigned by AerieOS: app-0.7.0.apk with the sideload key default, certificate SHA-256 AB:CD"
        self.assertEqual(releasesign.check("app")["signed"], [])
        self.assertEqual(self.started, [])


class Own(Base):
    """Only the release's own run is signed from: any run of the repository
    can write an artifact named for a tag, a pull request's from a fork
    among them, and each one that is not the tag's own is refused with the
    reason, nothing of it fetched."""

    def setUp(self):
        super().setUp()
        # v0.7.0's release run hands over nothing here: the run each test
        # adds is the only one naming the tag.
        ARTS.pop(21)
        self.addCleanup(setattr, releasesign, "check_soon", releasesign.check_soon)
        releasesign.check_soon = lambda *a, **k: False

    def other(self, rid=41, tag="v0.7.0", **over):
        MORE.insert(0, run(rid, tag, **over))
        ARTS[rid] = handed(tag)

    def rows(self, tag="v0.7.0"):
        return [r for r in json.loads((self.tmp / "release-signing.json").read_text())["app"]["last"]["runs"]
                if r["tag"] == tag]

    def refused(self, *words, tag="v0.7.0"):
        r = releasesign.check("app", force=True)
        self.assertEqual((r["signed"], self.signed), ([], []), "nothing of it is signed")
        self.assertFalse([p for m, p, a in SEEN if "/actions/artifacts/" in p], "nothing of it is fetched")
        self.assertFalse([1 for m, _, _ in SEEN if m in ("POST", "PATCH", "DELETE")], "the release is not touched")
        rows = self.rows(tag)
        self.assertEqual([(x["run"], x["state"]) for x in rows], [(41, "refused")], rows)
        for w in words:
            self.assertIn(w, rows[0]["why"])
        return rows[0]["why"]

    def test_the_tags_own_push_through_the_calling_workflow_is_signed(self):
        # The shape a release that makes itself in CI has: the push of an
        # annotated tag, a run of the workflow that calls the one that
        # uploads, on the commit the tag object names.
        ANNOTATED.add("v0.7.0")
        self.other()
        self.assertEqual(releasesign.check("app")["signed"], ["v0.7.0"])
        self.assertEqual(self.signed, [("app", b"unsigned apk bytes")])
        self.assertEqual([(x["run"], x["state"]) for x in self.rows()], [(41, "signed")])
        self.assertTrue([p for m, p, a in SEEN if p == "/repos/o/app/git/tags/" + "b" * 40],
                        "the tag object was followed to its commit")

    def test_a_pull_requests_run_is_refused(self):
        # Its branch named as the tag is, in the repository itself.
        self.other(event="pull_request", head_sha="d" * 40)
        self.refused("a pull request started it", "only from the run the tag v0.7.0 itself started")

    def test_a_forks_run_is_refused(self):
        self.other(head_repository={"full_name": "mallory/app"})
        self.refused("its commit came from mallory/app, not from o/app", "a fork's run is never signed")
        # ...and one whose fork is gone, which GitHub names nothing for.
        MORE[0]["head_repository"] = None
        self.refused("a repository GitHub no longer names")

    def test_a_branchs_push_is_refused(self):
        self.other(head_branch="main")
        self.refused("it ran on main, not on the tag v0.7.0")

    def test_a_run_on_another_commit_than_the_tags_is_refused(self):
        self.other(head_sha="d" * 40)
        self.refused("it ran on commit dddddddddddd", "the tag v0.7.0 names 777777777777")

    def test_a_run_of_another_workflow_file_is_refused(self):
        self.other(path=".github/workflows/lint.yml")
        self.refused("it is a run of .github/workflows/lint.yml",
                     ".github/workflows/android.yml, .github/workflows/release.yml")

    def test_a_run_by_hand_is_refused_and_says_what_to_run(self):
        self.other(event="workflow_dispatch")
        self.refused("it was started by hand", "Re-run all jobs")

    def test_a_run_for_a_tag_that_is_not_on_the_forge_is_refused(self):
        self.other(tag="v0.7.5")
        REL["v0.7.5"] = REL["v0.7.0"]
        self.refused("the tag v0.7.5 is not on GitHub", tag="v0.7.5")

    def test_the_workflows_that_hand_over_are_the_uploader_and_its_callers(self):
        # A commented call is no call: release.yml names lint.yml in one.
        (self.tmp / "ws" / "app" / ".github" / "workflows" / "lint.yml").write_text("name: lint\non: push\n")
        self.assertEqual(releasesign.handing("app"), {BUILDS, RELEASES})

    def test_a_second_run_for_a_signed_tag_is_not_signed_until_a_person_asks(self):
        ARTS[21] = handed("v0.7.0")
        self.assertEqual(releasesign.check("app")["signed"], ["v0.7.0"])
        first = REL["v0.7.0"]["body"]
        # The tag's run built again under a new number: its own in every
        # field, and the release already carries the APK.
        self.other()
        n = len(SEEN)
        self.assertEqual(releasesign.check("app", force=True)["signed"], [])
        self.assertEqual(len(self.signed), 1)
        self.assertFalse([1 for m, _, _ in SEEN[n:] if m in ("POST", "PATCH", "DELETE")], "the published file stays")
        row = [x for x in self.rows() if x["run"] == 41][0]
        self.assertEqual(row["state"], "not signed again")
        self.assertIn("v0.7.0's release already carries app-0.7.0.apk", row["why"])
        self.assertIn('aerie sign release --again v0.7.0 --why "..."', row["why"])
        self.assertFalse([a for a in releasesign.attention(["app"]) if a["bad"]], "and it is no failure")
        # A person names the tag: the newest of its own runs is signed, the
        # files replaced and the notes' line with them, once.
        self.assertEqual(releasesign.check("app", force=True, again="v0.7.0")["signed"], ["v0.7.0"])
        self.assertEqual(len(self.signed), 2)
        self.assertEqual(len([1 for m, p, _ in SEEN if m == "DELETE"]), 2, "the APK and its sha256, replaced")
        self.assertEqual(REL["v0.7.0"]["body"], first)
        self.assertEqual(sorted(a["name"] for a in REL["v0.7.0"]["assets"]), ["app-0.7.0.apk", "app-0.7.0.apk.sha256"])
        self.assertEqual([(x["run"], x["state"]) for x in self.rows()], [(41, "signed"), (21, "signed before")])
        self.assertEqual(releasesign.status("app")["signed"][0]["run"], 41)
        # ...and the look after it signs nothing again.
        self.assertEqual(releasesign.check("app", force=True)["signed"], [])
        self.assertEqual(len(self.signed), 2)

    def test_the_same_run_run_again_is_signed_again_only_for_the_tag_asked(self):
        ARTS[21] = handed("v0.7.0")
        releasesign.check("app")
        self.assertEqual(releasesign.check("app", force=True, again="v0.8.0")["signed"], [])
        self.assertEqual(len(self.signed), 1)
        said = json.loads((self.tmp / "release-signing.json").read_text())["app"]["last"]["said"]
        self.assertIn("v0.8.0 was not signed again: no run of the last 3 days still holds an unsigned APK for it", said[0])
        self.assertIn("Re-run all jobs", said[0])
        self.assertEqual(releasesign.check("app", again="v0.7.0")["signed"], ["v0.7.0"])
        self.assertEqual(len(self.signed), 2)
        self.assertNotIn("said", json.loads((self.tmp / "release-signing.json").read_text())["app"]["last"])

    def test_a_release_another_controller_signed_is_left_alone(self):
        # This controller has no record of the tag; the release says it.
        REL["v0.7.0"].update(body="### Added\n\n- A thing\n\nSigned by AerieOS: an old line",
                             assets=[{"id": 5, "name": "app-0.7.0.apk"}])
        self.other()
        releasesign.expect("app", "v0.7.0")
        self.assertEqual(releasesign.check("app")["signed"], [])
        self.assertEqual(self.signed, [])
        self.assertFalse([p for m, p, a in SEEN if "/actions/artifacts/" in p])
        row = self.rows()[0]
        self.assertEqual(row["state"], "not signed again")
        self.assertIn("already carries an APK its notes say AerieOS signed", row["why"])
        # Not waited for either: no row in twelve hours for an APK that is there.
        self.assertEqual(releasesign.status("app")["expect"], [])
        # A person names it: the one of the same name is replaced, not left
        # beside it, and the old line goes.
        self.assertEqual(releasesign.check("app", again="v0.7.0")["signed"], ["v0.7.0"])
        self.assertIn(("DELETE", "/repos/o/app/releases/assets/5", None), SEEN)
        self.assertNotIn("an old line", REL["v0.7.0"]["body"])
        self.assertEqual(REL["v0.7.0"]["body"].count("Signed by AerieOS:"), 1)

    def test_a_refusal_is_asked_for_a_tag_asked_again_too(self):
        # Asking again is no way around whose run it is.
        ARTS[21] = handed("v0.7.0")
        releasesign.check("app")
        self.other(event="pull_request")
        self.assertEqual(releasesign.check("app", again="v0.7.0")["signed"], ["v0.7.0"])
        self.assertEqual([(x["run"], x["state"]) for x in self.rows()], [(41, "refused"), (21, "signed")])

    def test_an_expected_releases_refused_run_is_said_on_the_bell_until_its_own_signs(self):
        releasesign.expect("app", "v0.7.0")
        self.other(event="workflow_dispatch")
        self.assertEqual(releasesign.check("app")["failed"], ["v0.7.0"])
        bad = [a for a in releasesign.attention(["app"]) if a["bad"]]
        self.assertEqual([a["tag"] for a in bad], ["v0.7.0"])
        self.assertIn("run 41 handed over an unsigned APK for v0.7.0 and was refused: it was started by hand", bad[0]["why"])
        # Said once: the same refusal at the next look is the same row, so
        # one put away stays away.
        key = bad[0]["key"]
        time.sleep(1.1)
        self.assertEqual(releasesign.check("app")["failed"], [])
        self.assertEqual([a["key"] for a in releasesign.attention(["app"]) if a["bad"]], [key])
        self.assertTrue(releasesign.due("app"), "still waited for")
        # The tag's own run hands its APK over: signed, and the row goes.
        self.other(rid=42)
        self.assertEqual(releasesign.check("app")["signed"], ["v0.7.0"])
        self.assertFalse([a for a in releasesign.attention(["app"]) if a["bad"]])

    def test_a_refused_run_for_a_tag_nobody_waits_for_is_no_bell_row(self):
        self.other(event="pull_request")
        self.refused("a pull request started it")
        self.assertFalse([a for a in releasesign.attention(["app"]) if a["bad"]])

    def test_an_overdue_release_names_the_run_that_was_refused(self):
        releasesign.expect("app", "v0.7.0")
        d = json.loads((self.tmp / "release-signing.json").read_text())
        d["app"]["expect"]["v0.7.0"] = int(time.time()) - releasesign.EXPECT_S - 5
        (self.tmp / "release-signing.json").write_text(json.dumps(d))
        self.other(head_branch="main")
        releasesign.check("app")
        bad = [a for a in releasesign.attention(["app"]) if a["bad"]]
        self.assertEqual(len(bad), 1)
        self.assertIn("no run of v0.7.0's own handed over an unsigned APK within 12 hours: run 41 did and was "
                      "refused, since it ran on main, not on the tag v0.7.0", bad[0]["why"])


class OneRun(Base):
    """The tag's own run hands the APK over and makes the release as its
    last job (R206 step 1): the artifact is there hours before the release,
    and the run is not over until the release is whole."""

    def setUp(self):
        super().setUp()
        # The draft fallback knows GitHub's address from when it was read;
        # here that address is the stand-in's.
        self.addCleanup(setattr, forgerelease, "_BY_TAG", forgerelease._BY_TAG)
        forgerelease._BY_TAG = re.compile(re.escape(forgerelease.API) + r"/repos/([^/?#]+/[^/?#]+)/releases/tags/([^/?#]+)")
        # A release expected starts a look on a thread of its own: here each
        # look is the test's, one at a time.
        self.addCleanup(setattr, releasesign, "check_soon", releasesign.check_soon)
        releasesign.check_soon = lambda *a, **k: False

    def going(self):
        # The tag's push, annotated as Release makes it, on the workflow
        # that calls the one that builds the APK.
        ANNOTATED.add("v0.8.0")
        MORE.append(run(31, "v0.8.0", status="in_progress", conclusion=None))

    def made(self, draft=True):
        REL["v0.8.0"] = {"id": 8, "tag_name": "v0.8.0", "draft": draft, "body": "notes",
                         "html_url": "https://github.com/o/app/releases/tag/v0.8.0", "assets": []}

    def looks(self):
        return [r for r in json.loads((self.tmp / "release-signing.json").read_text())["app"]["last"]["runs"] if r["tag"] == "v0.8.0"]

    def test_a_run_still_going_is_left_until_its_release_is_made_and_is_no_failure(self):
        self.going()
        releasesign.expect("app", "v0.8.0")
        for _ in (1, 2):
            r = releasesign.check("app")
            self.assertNotIn("v0.8.0", r["signed"] + r["failed"])
            self.assertEqual([x["state"] for x in self.looks()], ["its run has not made the release yet"])
        # Nothing more fetched or signed than v0.7.0's own, nothing on the
        # bell, and still due.
        self.assertEqual(len([1 for m, p, a in SEEN if p == "/repos/o/app/actions/artifacts/77/zip"]), 1)
        self.assertEqual(len(self.signed), 1)
        self.assertFalse([a for a in releasesign.attention(["app"]) if a["bad"]])
        self.assertTrue(releasesign.due("app"))
        self.assertEqual(json.loads((self.tmp / "release-signing.json").read_text())["app"]["failed"], {})

    def test_it_is_signed_at_the_look_after_the_release_is_made_draft_or_not(self):
        self.going()
        releasesign.expect("app", "v0.8.0")
        releasesign.check("app")
        n = len(self.signed)
        # A draft is never found by its tag: it is found among the listed.
        self.made(draft=True)
        was = REL.pop("v0.8.0")
        REL["draft-of-v0.8.0"] = was
        r = releasesign.check("app")
        self.assertEqual(r["signed"], ["v0.8.0"], r)
        self.assertEqual(len(self.signed), n + 1)
        self.assertEqual(sorted(a["name"] for a in was["assets"]), ["app-0.7.0.apk", "app-0.7.0.apk.sha256"])
        self.assertFalse(releasesign.due("app") and "v0.8.0" in json.loads(
            (self.tmp / "release-signing.json").read_text())["app"]["expect"], "no longer expected once signed")
        # The draft is said back a draft, with its tag (B590, B696).
        patch = [b for m, p, b in SEEN if m == "PATCH" and p.endswith("/releases/8")][-1]
        self.assertEqual((patch["draft"], patch["tag_name"]), (True, "v0.8.0"))
        # Signed once: the run going on, and then ended, signs nothing again.
        self.assertEqual(releasesign.check("app")["signed"], [])
        MORE[0].update(status="completed", conclusion="success")
        self.assertEqual(releasesign.check("app")["signed"], [])
        self.assertEqual(len(self.signed), n + 1)

    def test_a_run_still_going_is_asked_about_again_and_one_that_then_fails_is_dropped(self):
        MORE.append(run(32, "v0.8.1", status="queued", conclusion=None))
        releasesign.check("app")
        asked = len([p for m, p, a in SEEN if "/runs/32/artifacts" in p])
        releasesign.check("app")
        self.assertEqual(len([p for m, p, a in SEEN if "/runs/32/artifacts" in p]), asked + 1, "it may hand its APK over yet")
        MORE[0].update(status="completed", conclusion="failure")
        releasesign.check("app")
        self.assertEqual(len([p for m, p, a in SEEN if "/runs/32/artifacts" in p]), asked + 1)

    def test_an_expected_release_is_looked_for_at_once_and_due_until_signed(self):
        self.assertTrue(releasesign.due("app"))        # never scanned
        releasesign.check("app")
        self.assertFalse(releasesign.due("app"))
        d = json.loads((self.tmp / "release-signing.json").read_text())
        d["app"]["expect"]["v0.8.0"] = int(time.time())
        (self.tmp / "release-signing.json").write_text(json.dumps(d))
        self.assertTrue(releasesign.due("app"))


class Before(Base):
    def test_the_key_that_signs_releases_is_named(self):
        r = releasesign.readiness("app")
        self.assertTrue(r["wanted"])
        self.assertEqual(r["packages"], ["dev.example.app"])
        self.assertEqual([(k["package"], k["key"], k["sha256"]) for k in r["keys"]],
                         [("dev.example.app", "default", "AB:CD")])
        self.assertEqual(r["why"], "")
        self.assertEqual(releasesign.attention(["app"]), [])

    def test_no_sideload_key_is_said_on_the_bell_before_the_release(self):
        shutil.rmtree(self.tmp / "state" / "signing" / "app" / "default")
        releasesign._cache.clear()
        rows = releasesign.attention(["app"])
        self.assertEqual(len(rows), 1)
        self.assertFalse(rows[0]["bad"])
        self.assertIn("has no sideload signing key", rows[0]["why"])
        self.assertTrue(rows[0]["key"].startswith("rsign:app@"))

    def test_several_keys_and_no_mapping_is_said(self):
        shutil.rmtree(self.tmp / "state" / "signing" / "app" / "default")
        self.key("watch"); self.key("phone", "EF:01")
        why = releasesign.readiness("app")["why"]
        self.assertIn("dev.example.app is mapped to no key", why)
        self.assertIn("map it in the Signing view", why)
        (self.tmp / "state" / "signing" / "app" / "map.json").write_text(json.dumps({"dev.example.app": "phone"}))
        releasesign._cache.clear()
        r = releasesign.readiness("app")
        self.assertEqual((r["why"], r["keys"][0]["key"], r["keys"][0]["sha256"]), ("", "phone", "EF:01"))

    def test_a_rotated_key_signs_releases_with_its_successor(self):
        self.key("next", "99:99")
        d = self.tmp / "state" / "signing" / "app"
        rec = json.loads((d / "default" / "sideload.json").read_text())
        (d / "default" / "sideload.json").write_text(json.dumps(rec | {"retired_for": "next"}))
        releasesign._cache.clear()
        self.assertEqual(releasesign.readiness("app")["keys"][0]["key"], "next")

    def test_the_nodes_state_is_said(self):
        # The node it is signed on, in its words: offline, or without the
        # build-tools, which a rotation's proof and an APK need.
        n = {"id": "n_1", "name": "bb-sandbox", "state": "online", "kind": "agent", "live": False}
        signing.node_get = lambda nid: n
        r = releasesign.readiness("app", fresh=True)
        self.assertIn("app's node bb-sandbox is offline", r["why"])
        self.assertEqual(r["node"], "bb-sandbox")
        n["live"] = True
        signing.node_tools = lambda node: {"jdk", "android-tools"}
        self.assertIn("has no Android SDK Build-Tools", releasesign.readiness("app", fresh=True)["why"])
        signing.node_tools = lambda node: {"jdk", "android-tools", "android:build-tools"}
        self.assertEqual(releasesign.readiness("app", fresh=True)["why"], "")

    def test_a_project_whose_workflows_hand_over_nothing_is_left_alone(self):
        (self.tmp / "ws" / "app" / ".github" / "workflows" / "android.yml").write_text("name: x\n")
        releasesign._cache.clear()
        self.assertFalse(releasesign.readiness("app")["wanted"])
        shutil.rmtree(self.tmp / "state" / "signing" / "app" / "default")
        releasesign._cache.clear()
        self.assertEqual(releasesign.attention(["app"]), [])

    def test_an_unsigned_build_is_never_one_of_a_releases_files(self):
        dist = self.tmp / "ws" / "app" / "dist"
        dist.mkdir()
        (dist / "app-0.7.0-65298e0-unsigned.apk").write_bytes(b"x")
        self.assertEqual(forgerelease.assets("app", "65298e0"), [])
        (dist / "app-0.7.0-65298e0-release.apk").write_bytes(b"x")
        self.assertEqual([f.name for f in forgerelease.assets("app", "65298e0")], ["app-0.7.0-65298e0-release.apk"])




# ---- a real APK, signed on the node with its own tools ----------------------

def jar():
    jars = sorted(glob.glob(os.path.join(signnode.STORE_BT, "android", "platforms", "android-*", "android.jar"))) \
        if signnode.STORE_BT else []
    return jars[0] if jars else ""


JAR = jar()


@unittest.skipUnless(JAR, "no toolchain store with the jdk, build-tools and a platform here")
class RealSigning(unittest.TestCase):
    def setUp(self):
        self.tmp = Path(tempfile.mkdtemp())
        self.addCleanup(shutil.rmtree, self.tmp, True)
        signing.configure(state=self.tmp / "state", project_name=re.compile(r"[A-Za-z0-9._-]+"))
        self.node = signnode.install(self, signing, str(self.tmp / "data"), store=signnode.STORE_BT)
        self.bt = os.path.dirname(signnode.agent.module("keyops").build_tools(signnode.STORE_BT)["apksigner"])
        jdk = os.path.join(signnode.STORE_BT, "jdk")
        self.env = dict(os.environ, JAVA_HOME=jdk, PATH=os.path.join(jdk, "bin") + os.pathsep + os.environ["PATH"])
        signing.set_backup_password("app", "", "a-backup-password")
        man = self.tmp / "AndroidManifest.xml"
        man.write_text('<manifest xmlns:android="http://schemas.android.com/apk/res/android" '
                       'package="dev.example.app"><uses-sdk android:minSdkVersion="26"/></manifest>')
        self.apk = self.tmp / "app-unsigned.apk"
        subprocess.run([os.path.join(self.bt, "aapt2"), "link", "-o", str(self.apk), "-I", JAR,
                        "--manifest", str(man)], check=True, capture_output=True)

    def test_an_unsigned_apk_is_signed_on_the_node_with_the_kept_key(self):
        r, st = signing.generate("app", "sideload", "default")
        self.assertEqual(st, 200, r)
        out = self.tmp / "app.apk"
        got = signing.sign_release("app", self.apk, out)
        self.assertNotIn("error", got, got)
        self.assertEqual((got["key"], got["package"]), ("default", "dev.example.app"))
        self.assertEqual(got["cert"], r["key"]["sha256"])
        v = subprocess.run([os.path.join(self.bt, "apksigner"), "verify", "--print-certs", str(out)],
                           capture_output=True, text=True, env=self.env)
        self.assertEqual(v.returncode, 0, v.stderr)
        self.assertIn(r["key"]["sha256"].replace(":", "").lower(), v.stdout.lower())
        job = [j for j in self.node.jobs.values() if j["spec"]["op"] == "release"][0]
        self.assertEqual((job["type"], job["state"]), ("sign-key", "succeeded"), job["log"])
        self.assertEqual(os.listdir(self.tmp / "signwork" / "key"), [])
        self.assertFalse((self.tmp / "data" / "sign-key").exists(), "never on the data store (B315)")
        self.assertEqual(signing._handover, {})

    def test_a_rotated_key_signs_with_the_proof(self):
        signing.generate("app", "sideload", "default")
        signing.generate("app", "sideload", "next")
        self.assertEqual(signing.rotate("app", "default", "next")[1], 200)
        got = signing.sign_release("app", self.apk, self.tmp / "app.apk")
        self.assertEqual((got.get("key"), got.get("rotated_from")), ("next", "default"), got)

    def test_no_key_is_refused_before_anything_is_signed(self):
        got = signing.sign_release("app", self.apk, self.tmp / "app.apk")
        self.assertIn("has no sideload signing key", got["error"])
        self.assertFalse((self.tmp / "app.apk").exists())


if __name__ == "__main__":
    unittest.main()
