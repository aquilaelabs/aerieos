"""A bad agent build cannot strand a node (R241; the audit of 13 Nov: a
self-update wrote the new file over the running one and kept nothing, under
a unit that restarts for ever, so one build that failed to load left every
node it reached needing a person at its console).

The new file is asked to load itself before it is installed; the file it
replaces is kept beside it; the zip's entry counts the starts of an agent on
trial and puts the old file back when the package cannot be loaded or never
reaches its controller; the agent ends the trial at its controller's first
answer and gives way after ten minutes without one; and a node that went
back says so, after which its controller no longer sends that build by
itself (the operator, 13 Nov)."""
import hashlib
import importlib.util
import io
import json
import os
import shutil
import subprocess
import sys
import tempfile
import threading
import unittest
import zipfile
from unittest import mock

import agentpkg  # noqa: E402

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, os.path.join(HERE, ".."))
import nodes  # noqa: E402

SRC = os.path.normpath(os.path.join(HERE, "..", "..", "agent"))
ENTRY = os.path.join(SRC, "builderbot-agent.py")


def _bundle():
    spec = importlib.util.spec_from_file_location("agent_bundle_wayback", os.path.join(SRC, "aerieos_agent", "bundle.py"))
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


def fake(says, cli=None):
    """An agent zip with the real entry and a package of one line, which
    says who it is and what it was started with; `cli` replaces that line."""
    buf = io.BytesIO()
    buf.write(b"#!/usr/bin/env python3\n")
    with zipfile.ZipFile(buf, "w") as z:
        z.write(ENTRY, "__main__.py")
        z.writestr("aerieos_agent/__init__.py", "")
        z.writestr("aerieos_agent/cli.py", cli if cli is not None else f"def main(argv):\n    print({says!r}, *argv)\n")
    return buf.getvalue()


def digest(body):
    return "sha256:" + hashlib.sha256(body).hexdigest()


class Entry(unittest.TestCase):
    """The zip's entry, which has to work when the package does not."""

    def setUp(self):
        self.d = tempfile.mkdtemp()
        self.addCleanup(shutil.rmtree, self.d, True)
        self.me = os.path.join(self.d, "aerieos-agent")

    def put(self, new, old=None, trial=None):
        with open(self.me, "wb") as f:
            f.write(new)
        if old is not None:
            with open(self.me + ".prev", "wb") as f:
                f.write(old)
        if trial is not None:
            with open(self.me + ".trial", "w") as f:
                json.dump(trial, f)

    def start(self, *argv):
        p = subprocess.run([sys.executable, self.me, *argv], capture_output=True, text=True, check=False, timeout=60)
        return p.returncode, p.stdout.strip(), p.stderr.strip()

    def note(self, ext):
        try:
            with open(self.me + ext) as f:
                return json.load(f)
        except OSError:
            return None

    def test_an_agent_on_trial_gets_three_starts(self):
        new, old = fake("NEW"), fake("OLD")
        self.put(new, old, {"digest": digest(new), "from": digest(old), "starts": 0, "at": 1})
        for n in (1, 2, 3):
            self.assertEqual(self.start("run"), (0, "NEW run", ""))
            self.assertEqual(self.note(".trial")["starts"], n)
        # The fourth, its note still there: the old file is back and it is
        # the one that starts, with why left for the controller.
        rc, out, err = self.start("run")
        self.assertEqual((rc, out), (0, "OLD run"))
        self.assertIn("the one before it is back", err)
        with open(self.me, "rb") as f:
            self.assertEqual(f.read(), old)
        self.assertIsNone(self.note(".trial"))
        self.assertFalse(os.path.exists(self.me + ".prev"))
        back = self.note(".back")
        self.assertEqual(back["digest"], digest(new))
        self.assertIn("started 3 times and never reached its controller", back["why"])
        # ...and the old one, with no note, simply runs from here on.
        self.assertEqual(self.start("run"), (0, "OLD run", ""))

    def test_a_package_that_cannot_be_loaded_goes_back_at_once(self):
        for broken in ("def main(argv:\n", "import a_library_this_machine_lacks\n", "raise SystemExit(3)\n"):
            new, old = fake("NEW", cli=broken), fake("OLD")
            self.put(new, old, {"digest": digest(new), "starts": 0})
            rc, out, _ = self.start("run")
            self.assertEqual((rc, out), (0, "OLD run"), broken)
            self.assertIn("could not be loaded", self.note(".back")["why"])
            os.unlink(self.me + ".back")

    def test_with_nothing_to_go_back_to_it_stays_as_it_is(self):
        new = fake("NEW", cli="def main(argv:\n")
        self.put(new, None, {"digest": digest(new), "starts": 0})
        rc, _, err = self.start("run")
        self.assertNotEqual(rc, 0)
        self.assertIn("SyntaxError", err)
        with open(self.me, "rb") as f:
            self.assertEqual(f.read(), new)
        # A good one past its starts with no old file: it runs on.
        good = fake("NEW")
        self.put(good, None, {"digest": digest(good), "starts": 9})
        self.assertEqual(self.start("run")[:2], (0, "NEW run"))

    def test_only_run_is_counted_and_no_note_is_no_trial(self):
        new, old = fake("NEW"), fake("OLD")
        self.put(new, old, {"digest": digest(new), "starts": 3})
        self.assertEqual(self.start("status"), (0, "NEW status", ""))
        self.assertEqual(self.note(".trial")["starts"], 3)
        os.unlink(self.me + ".trial")
        self.assertEqual(self.start("run"), (0, "NEW run", ""))
        self.assertTrue(os.path.exists(self.me + ".prev"), "an old file kept after a trial that passed is left alone")
        # A broken package with no trial is not anybody's update: no way back taken.
        self.put(fake("NEW", cli="def main(argv:\n"), old)
        self.assertNotEqual(self.start("run")[0], 0)
        self.assertTrue(os.path.exists(self.me + ".prev"))

    def test_an_agent_that_gives_way_says_why(self):
        new, old = fake("NEW"), fake("OLD")
        self.put(new, old, {"digest": digest(new), "starts": 1, "why": "ran 10 minutes and never reached its controller"})
        self.assertEqual(self.start("run")[:2], (0, "OLD run"))
        self.assertEqual(self.note(".back")["why"], "ran 10 minutes and never reached its controller")

    def test_the_entry_uses_nothing_of_the_package(self):
        with open(ENTRY, encoding="utf-8") as f:
            src = f.read()
        head = src.split('if __name__ == "__main__":')[0]
        self.assertNotIn("aerieos_agent", head.split('"""', 2)[2], "what holds the way back loads before the package and without it")


class Update(unittest.TestCase):
    """The agent's own half: the new file checked, the old one kept."""

    def setUp(self):
        self.agent = agentpkg.load("aerieos_agent_wayback")
        self.agent.log = lambda *a, **k: None
        self.d = tempfile.mkdtemp()
        self.addCleanup(shutil.rmtree, self.d, True)
        self.me = os.path.join(self.d, "aerieos-agent")
        self.old = fake("OLD")
        with open(self.me, "wb") as f:
            f.write(self.old)
        self.agent.own_path = lambda: self.me
        self.agent.own_digest = lambda: digest(self.old)
        nj = os.path.join(self.d, "node.json")
        with open(nj, "w") as f:
            json.dump({"node_id": "n_x", "controller": "http://127.0.0.1:1", "token": "t"}, f)
        p = mock.patch.dict(os.environ, {"BUILDERBOT_NODE_JSON": nj})
        p.start()
        self.addCleanup(p.stop)
        self.real = _bundle().build(SRC)

    def update(self, body, **spec):
        a = object.__new__(self.agent.Agent)
        a.state, a.jobs, a.lock, a.controller_digest, a.controller_sig = {}, {}, threading.Lock(), "", ""

        class Ctl:
            @staticmethod
            def call(*args, **kw):
                return 200, body

        class Job:
            job, why, installed, said = {"id": "j_up"}, "", False, ""

            def say(self, text):
                self.said += text

        a.ctl, job = Ctl(), Job()
        mod = self.agent.module("agent")
        with mock.patch.object(self.agent.module("release"), "may_install", lambda *x: (True, "")), \
                mock.patch.object(mod, "load_state", dict):
            return a.self_update(job, spec), job

    def read(self, ext=""):
        with open(self.me + ext, "rb") as f:
            return f.read()

    def note(self, ext):
        try:
            return json.loads(self.read(ext))
        except OSError:
            return None

    def test_a_build_that_loads_is_installed_with_the_old_one_kept(self):
        (state, code), job = self.update(self.real)
        self.assertEqual((state, code, job.installed), ("succeeded", 0, True), job.said)
        self.assertEqual(self.read(), self.real)
        self.assertEqual(self.read(".prev"), self.old)
        trial = self.note(".trial")
        self.assertEqual((trial["digest"], trial["from"], trial["starts"]), (digest(self.real), digest(self.old), 0))
        self.assertIn("selfcheck ok", job.said)
        self.assertFalse(os.path.exists(self.me + ".new"))

    def test_a_build_that_does_not_load_is_never_installed(self):
        buf = io.BytesIO(self.real)
        out = io.BytesIO()
        with zipfile.ZipFile(buf) as zin, zipfile.ZipFile(out, "w") as zout:
            for info in zin.infolist():
                data = zin.read(info)
                if info.filename == "aerieos_agent/sessions.py":
                    data = b"def broken(:\n" + data
                zout.writestr(info, data)
        (state, code), job = self.update(out.getvalue())
        self.assertEqual((state, code, job.installed), ("failed", 78, False))
        self.assertIn("does not start on this node, so it was not installed", job.why)
        self.assertIn("SyntaxError", job.why)
        self.assertEqual(self.read(), self.old)
        self.assertEqual([n for n in os.listdir(self.d) if n not in ("aerieos-agent", "node.json")], [])

    def test_a_module_loaded_only_for_its_work_is_compiled_too(self):
        out = io.BytesIO()
        with zipfile.ZipFile(io.BytesIO(self.real)) as zin, zipfile.ZipFile(out, "w") as zout:
            for info in zin.infolist():
                zout.writestr(info, zin.read(info))
            zout.writestr("aerieos_agent/later.py", "import a_library_this_machine_lacks\n")
        # One that would only fail when run does not refuse the update...
        self.assertEqual(self.update(out.getvalue())[0], ("succeeded", 0))
        out2 = io.BytesIO()
        with zipfile.ZipFile(io.BytesIO(self.real)) as zin, zipfile.ZipFile(out2, "w") as zout:
            for info in zin.infolist():
                zout.writestr(info, zin.read(info))
            zout.writestr("aerieos_agent/later.py", "def broken(:\n")
        with open(self.me, "wb") as f:
            f.write(self.old)
        # ...and one that cannot be compiled does.
        self.assertEqual(self.update(out2.getvalue())[0], ("failed", 78))

    def test_a_build_from_before_the_check_is_installed_as_every_build_was(self):
        older = fake("OLDER BUILD")
        (state, code), job = self.update(older)
        self.assertEqual((state, code), ("succeeded", 0))
        self.assertIn("from before the start check", job.said)
        self.assertEqual(self.read(), older)
        self.assertEqual(self.read(".prev"), self.old)
        self.assertIsNone(self.note(".trial"), "its entry holds no way back, so nothing is on trial")

    def test_one_it_went_back_from_is_a_persons_to_send_again(self):
        with open(self.me + ".back", "w") as f:
            json.dump({"digest": digest(self.real), "at": 5, "why": "could not be loaded"}, f)
        (state, code), job = self.update(self.real)
        self.assertEqual((state, code), ("failed", 79))
        self.assertIn("went back from this build already (could not be loaded)", job.why)
        self.assertEqual(self.read(), self.old)
        self.assertEqual(self.update(self.real, again=True)[0], ("succeeded", 0))

    def test_the_trial_ends_at_the_controllers_first_answer(self):
        base = self.agent.module("base")
        for ext in (".trial", ".back", ".prev"):
            with open(self.me + ext, "w") as f:
                json.dump({"digest": "sha256:" + "a" * 64, "starts": 1, "why": "x"} if ext != ".prev" else {}, f)
        self.assertEqual(base.back_note()["digest"], "sha256:" + "a" * 64)
        self.assertTrue(base.trial_passed())
        self.assertEqual((base.trial_note(), base.back_note()), (None, None))
        self.assertTrue(os.path.exists(self.me + ".prev"))
        self.assertFalse(base.trial_passed(), "no trial, nothing passed")

    def test_ten_minutes_without_its_controller_and_it_gives_way(self):
        self.assertEqual(self.agent.TRIAL_S, 600)
        a = object.__new__(self.agent.Agent)
        went = []
        a.reexec = lambda: went.append("again")
        with open(self.me + ".prev", "wb") as f:
            f.write(self.old)
        with open(self.me + ".trial", "w") as f:
            json.dump({"digest": digest(self.real), "starts": 1}, f)
        # One that was answered meanwhile stays.
        a.hello_said = True
        a.trial_over()
        self.assertEqual((went, "why" in self.note(".trial")), ([], False))
        a.hello_said = False
        a.trial_over()
        self.assertEqual(went, ["again"])
        self.assertEqual(self.note(".trial")["why"], "ran 10 minutes and never reached its controller")
        # With no old file there is nothing to give way to.
        os.unlink(self.me + ".prev")
        with open(self.me + ".trial", "w") as f:
            json.dump({"digest": digest(self.real), "starts": 1}, f)
        a.trial_over()
        self.assertEqual(went, ["again"])


class Controller(unittest.TestCase):
    """Its controller: the word kept, and that build no longer sent unasked."""

    def setUp(self):
        nodes.configure(state=tempfile.mkdtemp())
        nodes._auto_tried.clear()
        mint = nodes.enroll_mint("user:test", "box")
        nodes.enroll(nodes.authenticate(mint["token"]), {"cpu": 2, "mem_mb": 4096, "arch": "x86_64",
                                                         "system": "linux", "session": {"up": True, "user": "b"}},
                     "box.lan", user="bb")
        self.nid = mint["id"]
        self.ours = nodes.agent_file()
        self.theirs = "sha256:" + "0" * 64

    def hello(self, back=None):
        return nodes.hello(self.nid, {"cpu": 2, "mem_mb": 4096, "arch": "x86_64", "system": "linux"}, "box.lan",
                           self.ours["version"], self.theirs, [], back=back)

    def queued(self):
        return [j for j in nodes.jobs_for(node_id=self.nid, n=10, active=True) if j.get("type") == "self-update"]

    def test_what_a_node_says_is_held_to_its_shapes(self):
        good = {"digest": self.ours["digest"], "at": 1700000000, "why": "could not be loaded (SyntaxError: x)"}
        self.assertEqual(nodes.agent_back({**good, "extra": "dropped"}), good)
        self.assertEqual(nodes.agent_back({**good, "at": "soon", "why": "a\nb\x1b[31m"})["at"], 0)
        self.assertNotIn("\n", nodes.agent_back({**good, "why": "a\nb"})["why"])
        self.assertEqual(len(nodes.agent_back({**good, "why": "w" * 900})["why"]), 300)
        for bad in (None, "went back", {}, {"digest": "$(rm -rf /)"}, {"digest": "sha256:short"}):
            self.assertIsNone(nodes.agent_back(bad), bad)

    def test_a_node_that_went_back_is_not_sent_that_build_again_unasked(self):
        self.hello()
        nodes._auto_tried.clear()
        for j in self.queued():
            nodes._exec("UPDATE jobs SET state = 'failed' WHERE id = ?", (j["id"],))
        self.hello({"digest": self.ours["digest"], "at": 5, "why": "could not be loaded"})
        n = nodes.node(self.nid)
        self.assertEqual(n["agent"]["back"]["why"], "could not be loaded")
        self.assertEqual(nodes.went_back(n), "could not be loaded")
        nodes._auto_tried.clear()
        self.assertIsNone(nodes.auto_update(self.nid))
        self.assertEqual(self.queued(), [])
        # A person's press asks again, and says so to the node.
        r = nodes.node_update_agent("user:test", self.nid)
        self.assertTrue(r.get("ok"), r)
        self.assertIs(self.queued()[0]["spec"].get("again"), True)
        # The controller's own never does.
        nodes._exec("UPDATE jobs SET state = 'failed' WHERE node = ?", (self.nid,))
        r = nodes.node_update_agent("system:auto-update", self.nid)
        self.assertNotIn("again", self.queued()[0]["spec"])

    def test_one_it_went_back_from_long_ago_holds_nothing(self):
        # Another build than the one this controller ships now: sent as any is.
        self.hello({"digest": "sha256:" + "9" * 64, "at": 5, "why": "could not be loaded"})
        self.assertEqual(nodes.went_back(nodes.node(self.nid)), "")
        for j in self.queued():
            nodes._exec("UPDATE jobs SET state = 'failed' WHERE id = ?", (j["id"],))
        nodes._auto_tried.clear()
        self.assertTrue(nodes.auto_update(self.nid))
        # ...and a hello that says none takes the word away.
        self.hello()
        self.assertNotIn("back", nodes.node(self.nid)["agent"])

    def test_the_bell_says_it_and_stops_promising_an_update(self):
        self.hello()
        with mock.patch.object(nodes, "node_list", lambda: [{**nodes.node(self.nid), "live": True}]):
            row = next(r for r in nodes.attention({}) if r.get("kind") == "agent")
        self.assertEqual((row["back"], row["auto"]), ("", True))
        self.hello({"digest": self.ours["digest"], "at": 5, "why": "started 3 times and never reached its controller"})
        with mock.patch.object(nodes, "node_list", lambda: [{**nodes.node(self.nid), "live": True}]):
            row = next(r for r in nodes.attention({}) if r.get("kind") == "agent")
        self.assertEqual((row["back"], row["auto"]), ("started 3 times and never reached its controller", False))

    def test_a_busy_refusal_says_who_asks_again(self):
        self.hello()
        self.assertEqual(nodes._update_again(self.nid), "asked again once the node is idle")
        self.hello({"digest": self.ours["digest"], "at": 5, "why": "x"})
        self.assertIn("press Update agent again", nodes._update_again(self.nid))
        nodes._exec("UPDATE nodes SET agent = json_set(agent, '$.version', '0.1.1', '$.back', NULL) WHERE id = ?", (self.nid,))
        self.assertIn("press Update agent again", nodes._update_again(self.nid), "across a window it is a person's")


if __name__ == "__main__":
    unittest.main()
