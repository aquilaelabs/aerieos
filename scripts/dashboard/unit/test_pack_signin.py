"""A pack's coding agent signed in from the page (R233 step 6): the flow its
pack describes as data (toolpacks.py), the job the controller names for it
(agents.py), how the flow reads in its job's log (signin.py), the driver
that works the program's own screens on the node (login-flow.py), what the
node reads back (login-list.py) and what it seals and watches (the agent's
tokens.py and tokenwatch.py).

The program here is a made-up one, heron, that signs in as Antigravity CLI
1.5.6 was seen to on 12 Nov: a menu answered with Enter, a link drawn
wrapped to the terminal's width with a terminal link beside it, a field the
code is typed into, and then a first-run screen it stays on. Never a real
account."""
import copy
import json
import os
import pty
import select
import shutil
import subprocess
import sys
import tempfile
import time
import unittest

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, os.path.join(HERE, ".."))
sys.path.insert(0, HERE)
import agentpkg  # noqa: E402
import agents  # noqa: E402
import signin  # noqa: E402
import toolpacks  # noqa: E402

LIB = os.path.join(HERE, "..", "..", "lib")
FLOW = os.path.join(LIB, "login-flow.py")
LIST = os.path.join(LIB, "login-list.py")
KEPT = ".heron/cli/oauth-token"
LINK = "https://accounts.heron.example/o/oauth2/auth?client_id=heron-cli&scope=" + "+".join(f"scope{i}" for i in range(40)) + "&state=abc123"

HERON = {"name": "heron", "format": 2, "label": "Heron", "about": "A coding agent that signs in on a screen of its own.",
         "platforms": ["linux/amd64"], "install": {"steps": [["sh", "{dir}/install.sh"]]}, "layout": {"bin": ["bin"], "tool": "bin/heron"},
         "agent": {"name": "Heron", "product": "Heron CLI", "provider": "Heron Labs", "command": "heron",
                   "briefing": {"how": "flag-file", "flag": "--rules"},
                   "hooks": {"file": ".heron/hooks.json", "shape": "grouped", "payload": "camel",
                             "events": {"pre": "PreToolUse", "prompt": "UserPromptSubmit", "stop": "Stop"}},
                   "signin": {"login": ["heron"],
                              "flow": {"url": "https://accounts.heron.example/o/oauth2/",
                                       "answers": [{"when": "Select login method", "send": ""}],
                                       "prompt": "paste the authorization code",
                                       "refused": "code was not accepted",
                                       "kept": KEPT}}}}

# The program: raw keys, a menu, the link wrapped at 80 columns whatever the
# terminal's width (and whole in a terminal link), a code field, and after a
# good code the file its sign-in is kept in, then a screen it never leaves.
PROGRAM = r'''#!/usr/bin/env python3
import os, sys, termios, time, tty
LINK = %(link)r
KIND = os.environ.get("HERON_KIND", "paste")
out = lambda s: (sys.stdout.write(s), sys.stdout.flush())
home = os.environ["HOME"]
open(os.path.join(home, "heron.pid"), "w").write(str(os.getpid()))
open(os.path.join(home, "heron.cols"), "w").write(str(os.get_terminal_size().columns))
open(os.path.join(home, "heron.token"), "w").write(os.environ.get("BB_TOKEN", ""))
tty.setraw(0)
def key():
    return os.read(0, 1)
def keep():
    p = os.path.join(home, %(kept)r)
    os.makedirs(os.path.dirname(p), exist_ok=True)
    open(p, "w").write('{"access": "not-a-real-token"}')
out("\x1b[2J\x1b[H\x1b[1mWelcome to Heron.\x1b[0m You are currently not signed in.\r\n Select\x1b[1Clogin\x1b[1Cmethod:\r\n > 1. Heron OAuth\r\n   2. A cloud project\r\n")
while key() != b"\r":
    pass
if KIND == "device":
    out("\x1b[2J\x1b[HOpen " + LINK + "\r\nand enter the one-time code: \x1b[1mWXYZ-1234\x1b[0m\r\n")
    time.sleep(1.5)
    keep()
    out("\r\nSigned in.\r\n")
    sys.exit(0)
wrapped = "\r\n".join(LINK[i:i + 80] for i in range(0, len(LINK), 80))
out("\x1b[2J\x1b[HYour browser should open automatically. If not:\r\n" + wrapped + "\r\n\r\n"
    "\x1b]8;;" + LINK + "\x1b\\Click here to authenticate\x1b]8;;\x1b\\\r\n"
    "If you aren't redirected, \x1b[1mpaste the authorization code\x1b[0m below:\r\n > ")
while True:
    code = b""
    while True:
        k = key()
        if k == b"\r":
            break
        code += k
        out(k.decode() + " \b")
    if code == b"good-code":
        keep()
        out("\x1b[2J\x1b[HWelcome! Choose your color scheme\r\n > dark\r\n   light\r\n")
        time.sleep(600)
    out("\r\n\u28ef Signing in...")
    time.sleep(0.3)
    out("\r\u28df \x1b[31mThat code was not accepted. Try again.\x1b[0m\r\n > ")
''' % {"link": LINK, "kept": KEPT}


def cleaned(m=HERON):
    got, errors = toolpacks.validate(m)
    assert not errors, errors
    return got["pack_agent"]


def with_flow(**change):
    m = copy.deepcopy(HERON)
    for k, v in change.items():
        if v is None:
            m["agent"]["signin"]["flow"].pop(k, None)
        else:
            m["agent"]["signin"]["flow"][k] = v
    return m


class TheFlowAsData(unittest.TestCase):
    def test_a_flow_is_kept_as_what_the_driver_reads(self):
        flow = cleaned()["signin"]["flow"]
        self.assertEqual(flow, {"url": "https://accounts.heron.example/o/oauth2/", "prompt": "paste the authorization code", "code_after": "",
                                "refused": "code was not accepted",
                                "answers": [{"when": "Select login method", "send": ""}], "kept": KEPT, "logout": []})

    def test_a_manifest_with_a_flow_needs_no_newer_format_than_its_hooks_do(self):
        # What an earlier build leaves out without the rest meaning anything
        # else: there the agent signs in in its terminal, as before.
        got, errors = toolpacks.validate(HERON)
        self.assertEqual((errors, got["format"]), ([], 2))

    def test_nothing_in_a_flow_is_a_pattern_or_a_command_line(self):
        for change, word in (({"url": "https://accounts.heron.example/(.*)"}, "flow.url"), ({"url": "http://accounts.heron.example/"}, "flow.url"),
                             ({"url": "https://localhost/"}, "flow.url"), ({"prompt": "paste.*code$"}, "flow.prompt"),
                             ({"answers": [{"when": "Select login method", "send": "rm -rf /"}]}, "flow.answers"),
                             ({"answers": [{"when": "x" * 90, "send": "1"}]}, "flow.answers"),
                             ({"answers": [{"when": "Trust this folder", "send": "y"}] * 5}, "flow.answers"),
                             ({"kept": "../.ssh/id_ed25519"}, "flow.kept"), ({"kept": "/etc/passwd"}, "flow.kept"), ({"kept": None}, "flow.kept"),
                             ({"logout": ["sh", "-c", "curl"]}, "flow.logout")):
            _, errors = toolpacks.validate(with_flow(**change))
            self.assertTrue(any(word in e for e in errors), (change, errors))

    def test_a_flow_takes_a_code_back_or_shows_one_never_both_or_neither(self):
        for change in ({"code_after": "enter the one-time code"}, {"prompt": None}):
            _, errors = toolpacks.validate(with_flow(**change))
            self.assertTrue(any("one of them" in e for e in errors), (change, errors))
        flow = cleaned(with_flow(prompt=None, code_after="enter the one-time code"))["signin"]["flow"]
        self.assertEqual((flow["prompt"], flow["code_after"]), ("", "enter the one-time code"))

    def test_a_flow_needs_the_command_that_starts_it(self):
        m = copy.deepcopy(HERON)
        del m["agent"]["signin"]["login"]
        _, errors = toolpacks.validate(m)
        self.assertTrue(any("signin.login" in e for e in errors), errors)


class TheControllersRow(unittest.TestCase):
    def setUp(self):
        self.addCleanup(setattr, agents, "pack_source", agents.pack_source)

    def offer(self, *manifests):
        agents.pack_source = lambda: tuple((m["name"], m["label"], cleaned(m)) for m in manifests)

    def test_a_pack_agent_with_a_flow_is_signed_in_by_the_one_pair_of_jobs(self):
        self.offer(HERON)
        a = agents.get("heron")
        self.assertEqual((a.login_job, a.logout_job), ("agent-login", "agent-logout"))
        self.assertTrue(next(r for r in agents.page_rows() if r["id"] == "heron")["signin"])

    def test_one_that_describes_none_signs_in_in_its_terminal_as_before(self):
        m = copy.deepcopy(HERON)
        del m["agent"]["signin"]["flow"]
        self.offer(m)
        a = agents.get("heron")
        self.assertEqual((a.login_job, a.logout_job), ("", ""))
        self.assertFalse(next(r for r in agents.page_rows() if r["id"] == "heron")["signin"])
        self.assertIsNone(signin.flow_of("heron"))

    def test_the_card_reads_the_drivers_lines_from_the_jobs_log(self):
        self.offer(HERON)

        class Nodes:
            log = ""

            def job(self, _id):
                return {"state": "running", "log": self.log}

        n = Nodes()
        f = signin.NodeFlow(n, "n_1", "j_1", "node one", uid="u_0123abcd", agent="heron")
        self.assertEqual((f.state()["url"], f.state()["waiting"], f.state()["paste"]), ("", False, True))
        n.log = "signing in to heron on this machine; the URL follows\n[aerieos] open this link to sign in: " + LINK + "\n"
        self.assertEqual((f.state()["url"], f.state()["waiting"]), (LINK, False))
        n.log += "[aerieos] Paste code: the one that page gives you once you have signed in there\n"
        self.assertTrue(f.state()["waiting"])
        self.assertEqual(f.state()["agent"], "heron")

    def test_a_flow_that_failed_says_why_in_the_programs_words_without_the_drivers_mark(self):
        self.offer(HERON)

        class Nodes:
            def job(self, _id):
                return {"state": "failed", "log": "[aerieos] open this link to sign in: " + LINK + "\n[aerieos] Paste code: the one\n"
                                                  "[aerieos] Heron did not keep a sign-in after the code; its screen last said: That code was not accepted.\n"}

        got = signin.NodeFlow(Nodes(), "n_1", "j_1", "node one", uid="u_0123abcd", agent="heron").state()
        self.assertEqual((got["done"], got["ok"]), (True, False))
        self.assertEqual(got["error"], "Heron did not keep a sign-in after the code; its screen last said: That code was not accepted.")

    def test_a_flow_that_shows_a_code_draws_the_code_and_no_field(self):
        self.offer(with_flow(prompt=None, code_after="enter the one-time code"))
        self.assertFalse(signin.pastes("heron"))
        m = signin.PACK_FLOW["code"].search("[aerieos] then enter this code there: WXYZ-1234\n")
        self.assertEqual(m.group(1), "WXYZ-1234")
        self.assertTrue(signin.pastes("claude"))
        self.assertFalse(signin.pastes("codex"))

    def test_a_node_whose_agent_is_from_before_the_job_is_asked_to_update_first(self):
        self.offer(HERON)
        node = {"id": "n_1", "name": "node one", "kind": "agent", "state": "online", "live": True, "reported": {"session": {"up": True}},
                "agent": {"version": "0.9.428"}}
        self.assertIn("update it", signin.cannot(node, "heron"))
        self.assertEqual(signin.cannot(dict(node, agent={"version": f"0.9.{signin.PACK_FLOW_BUILD}"}), "heron"), "")
        self.assertEqual(signin.cannot(node, "codex"), "", "a shipped agent's job is one every agent of the window runs")


class OnTheNode(unittest.TestCase):
    def setUp(self):
        self.d = tempfile.mkdtemp()
        self.addCleanup(shutil.rmtree, self.d, True)
        self.home = os.path.join(self.d, "users", "u_0123abcd")
        self.bin = os.path.join(self.d, "bin")
        os.makedirs(self.home), os.makedirs(self.bin)
        with open(os.path.join(self.bin, "heron"), "w") as f:
            f.write(PROGRAM)
        os.chmod(os.path.join(self.bin, "heron"), 0o755)
        self.packs = os.path.join(self.d, "toolpacks.json")
        self.write_packs(HERON)
        self.env = {"HOME": self.home, "PATH": self.bin + ":" + os.environ["PATH"], "BB_TOOLPACKS_JSON": self.packs, "BB_NODE": "node one",
                    "BB_FLOW_KEEP_S": "3", "LANG": "C.UTF-8"}

    def write_packs(self, m):
        with open(self.packs, "w") as f:
            json.dump({"toolchains": [{"name": m["name"], "agent": cleaned(m)}]}, f)

    def flow(self, *answers, env=None, limit=40):
        """The driver run as the job runs it, under a terminal: each of
        `answers` is (the words waited for, the line typed then). The log,
        and how it ended."""
        master, slave = pty.openpty()
        p = subprocess.Popen([sys.executable, FLOW, "in", "heron"], stdin=slave, stdout=slave, stderr=slave, env=dict(self.env, **(env or {})),
                             start_new_session=True, close_fds=True)
        os.close(slave)
        self.addCleanup(lambda: p.poll() is None and p.kill())
        log, todo, until = "", list(answers), time.time() + limit
        while time.time() < until:
            r, _, _ = select.select([master], [], [], 0.2)
            if r:
                try:
                    chunk = os.read(master, 65536)
                except OSError:
                    break
                if not chunk:
                    break
                log += chunk.decode("utf-8", "replace")
            if todo and todo[0][0] in log:
                os.write(master, (todo.pop(0)[1] + "\n").encode())
            if p.poll() is not None and not r:
                break
        os.close(master)
        return log, p.wait(timeout=10)

    def gone(self):
        with open(os.path.join(self.home, "heron.pid")) as f:
            pid = int(f.read())
        for _ in range(50):
            try:
                os.kill(pid, 0)
            except ProcessLookupError:
                return True
            time.sleep(0.1)
        return False

    def test_the_link_goes_up_whole_the_code_comes_down_and_the_program_is_ended_once_signed_in(self):
        log, code = self.flow(("Paste code", "good-code"), env={"BB_TOKEN": "the-flows-own-token"})
        self.assertNotRegex(log, r"g ?o ?o ?d ?- ?c ?o ?d ?e")
        self.assertEqual(code, 0, log)
        with open(os.path.join(self.home, "heron.token")) as f:
            self.assertEqual(f.read(), "", "what the flow reports with is not handed to the program signing in")
        self.assertEqual(signin.PACK_FLOW["url"].search(log).group(0), LINK, "whole, though the program wraps it at 80 columns")
        self.assertIn("[aerieos] signed in to Heron on node one", log)
        self.assertTrue(os.path.getsize(os.path.join(self.home, KEPT)) > 0)
        self.assertTrue(self.gone(), "what it asks after the sign-in is the person's own to answer, in their first session")
        self.assertNotIn("good-code", log, "the code is typed into the program and never said back up the log")
        self.assertNotIn("Welcome to Heron", log, "the program's screen is not the log")
        with open(os.path.join(self.home, "heron.cols")) as f:
            self.assertGreaterEqual(int(f.read()), 1000, "a terminal wide enough that a link is one row")

    def test_a_code_the_program_does_not_take_fails_in_its_own_words(self):
        t0 = time.time()
        log, code = self.flow(("Paste code", "bad-code"), env={"BB_FLOW_KEEP_S": "60"})
        self.assertEqual(code, 1, log)
        self.assertLess(time.time() - t0, 20, "ended when the program said so, not after the wait for a sign-in to be kept")
        last = [ln for ln in log.splitlines() if ln.strip()][-1]
        self.assertIn("Heron did not keep a sign-in after the code", last)
        self.assertIn("That code was not accepted", last)
        self.assertNotIn("bad-code", log, "its field echoes what is typed, and the echo is not the program's answer")
        self.assertNotRegex(last, r"b ?a ?d ?- ?c ?o ?d ?e")
        self.assertNotRegex(last, "[\x00-\x1f\u2800-\u28ff]", "no control characters and no spinner in what a person reads")

    def test_with_no_words_for_a_refusal_it_is_noticed_after_the_wait(self):
        self.write_packs(with_flow(refused=None))
        log, code = self.flow(("Paste code", "bad-code"))
        self.assertEqual(code, 1, log)
        self.assertIn("That code was not accepted", [ln for ln in log.splitlines() if ln.strip()][-1])
        self.assertFalse(os.path.exists(os.path.join(self.home, KEPT)))
        self.assertTrue(self.gone())

    def test_a_flow_that_shows_a_code_says_the_link_and_the_code_and_types_nothing_back(self):
        self.write_packs(with_flow(prompt=None, code_after="enter the one-time code"))
        log, code = self.flow(env={"HERON_KIND": "device"})
        self.assertEqual(code, 0, log)
        self.assertEqual(signin.PACK_FLOW["url"].search(log).group(0), LINK)
        self.assertEqual(signin.PACK_FLOW["code"].search(log).group(1), "WXYZ-1234")
        self.assertNotIn("Paste code", log)

    def test_signed_in_already_starts_nothing(self):
        os.makedirs(os.path.dirname(os.path.join(self.home, KEPT)))
        with open(os.path.join(self.home, KEPT), "w") as f:
            f.write("{}")
        log, code = self.flow()
        self.assertEqual(code, 0)
        self.assertIn("already signed in to Heron here", log)
        self.assertFalse(os.path.exists(os.path.join(self.home, "heron.pid")))

    def test_a_program_that_is_not_here_says_where_it_is_installed(self):
        os.unlink(os.path.join(self.bin, "heron"))
        log, code = self.flow()
        self.assertEqual(code, 1)
        self.assertIn("Heron CLI is not installed on this machine", log)

    def run_flow(self, *argv):
        return subprocess.run([sys.executable, FLOW, *argv], env=self.env, capture_output=True, text=True, check=False)

    def test_only_an_agent_this_bundles_packs_describe_a_flow_for(self):
        self.assertEqual(self.run_flow("has", "heron").returncode, 0)
        for other in ("otter", "codex", "claude", "../heron"):
            self.assertEqual(self.run_flow("has", other).returncode, 1, other)
        m = copy.deepcopy(HERON)
        del m["agent"]["signin"]["flow"]
        self.write_packs(m)
        self.assertEqual(self.run_flow("has", "heron").returncode, 1)

    def test_a_sign_out_removes_the_file_the_sign_in_is_kept_in(self):
        p = os.path.join(self.home, KEPT)
        os.makedirs(os.path.dirname(p))
        with open(p, "w") as f:
            f.write("{}")
        got = self.run_flow("out", "heron")
        self.assertEqual(got.returncode, 0, got.stdout + got.stderr)
        self.assertFalse(os.path.lexists(p))
        self.assertIn("signed out of Heron on node one", got.stdout)
        self.assertEqual(self.run_flow("out", "heron").returncode, 0, "signed out already is signed out")

    def listed(self):
        p = subprocess.run([sys.executable, "-I", LIST], env={"BB_USERS_DIR": os.path.join(self.d, "users"), "PATH": os.environ["PATH"],
                                                             "BB_TOOLPACKS_JSON": self.packs}, capture_output=True, text=True, check=True)
        return json.loads(p.stdout)[0]["agents"]

    def test_the_node_says_who_is_signed_in_from_the_kept_file(self):
        self.assertNotIn("heron", self.listed())
        p = os.path.join(self.home, KEPT)
        os.makedirs(os.path.dirname(p))
        with open(p, "w") as f:
            f.write('{"access": "opaque", "refresh": "opaque"}')
        self.assertEqual(self.listed()["heron"], {"email": "Heron Labs account", "plan": ""}, "whose account it is, where no token names an email")
        import base64
        claims = base64.urlsafe_b64encode(json.dumps({"email": "pat@example.invalid"}).encode()).decode().rstrip("=")
        with open(p, "w") as f:
            json.dump({"id": f"e30.{claims}.sig"}, f)
        self.assertEqual(self.listed()["heron"]["email"], "pat@example.invalid")
        with open(p, "w") as f:
            f.write("")
        self.assertNotIn("heron", self.listed(), "an empty file is no sign-in")


class SealedAndWatched(unittest.TestCase):
    def setUp(self):
        self.d = tempfile.mkdtemp()
        self.addCleanup(shutil.rmtree, self.d, True)
        os.makedirs(os.path.join(self.d, "current", "config"))
        with open(os.path.join(self.d, "current", "config", "toolpacks.json"), "w") as f:
            json.dump({"toolchains": [{"name": "heron", "agent": cleaned()}, {"name": "ftp"},
                                      {"name": "codex", "agent": cleaned()},
                                      {"name": "sly", "agent": dict(cleaned(), signin={"flow": {"kept": "../../etc/shadow", "url": "https://x.example/"}})}]}, f)
        self.node = agentpkg.load("packsignin")
        self.node.ROOT_BUNDLE_DIR = self.d

    def test_the_agent_reads_each_pack_agents_kept_file_from_its_root_bundle(self):
        self.assertEqual(self.node.pack_signins(), {"heron": {"kept": KEPT, "provider": "Heron Labs"}},
                         "never a shipped agent's name, never a path out of the home")

    def test_its_file_is_sealed_beside_the_shipped_agents(self):
        tokens = self.node.module("tokens")
        self.assertIn(("heron", KEPT), tokens.files())
        self.assertEqual(tokens.files()[:len(tokens.FILES)], tokens.FILES)
        self.assertEqual(tokens.about("heron", b'{"access": "opaque"}', "/nowhere")["email"], "Heron Labs account")

    def test_its_folder_is_watched_for_readers(self):
        tw = self.node.module("tokenwatch")
        self.assertEqual(tw.watched()[".heron/cli"], "oauth-token")
        self.assertEqual(tw.watched()[".claude"], ".credentials.json")

    def test_a_sign_in_asked_for_before_the_nodes_bundle_caught_up_fetches_the_bundle_first(self):
        # The pack gained its flow a moment ago: the controller's bundle has
        # it, the copy kept on the node is from before.
        import types
        old = os.path.join(self.d, "old")
        os.makedirs(os.path.join(old, "config"))
        with open(os.path.join(old, "config", "toolpacks.json"), "w") as f:
            json.dump({"toolchains": [{"name": "heron", "agent": dict(cleaned(), signin={"file": "", "env": ""})}]}, f)
        said, fetched = [], []
        job = types.SimpleNamespace(say=said.append, agent=types.SimpleNamespace(bundle=lambda j, who: fetched.append(1) or os.path.join(self.d, "store")))
        new = os.path.realpath(os.path.join(self.d, "current"))
        self.assertEqual(self.node.Job.pack_bundle(job, "heron", new, {}, True), new)
        self.assertEqual(fetched, [], "a bundle that carries it is used as it is")
        self.assertEqual(self.node.Job.pack_bundle(job, "heron", old, {}, True), new, "root's copy, as the fetch left it")
        self.assertEqual((fetched, said), ([1], []))
        self.assertEqual(self.node.Job.pack_bundle(job, "otter", old, {}, True), "")
        self.assertIn("no tool pack on this node brings a coding agent called 'otter'", said[-1])

    def test_no_bundle_is_no_pack_agents(self):
        self.node.ROOT_BUNDLE_DIR = os.path.join(self.d, "nowhere")
        self.assertEqual(self.node.pack_signins(), {})
        self.assertEqual(self.node.module("tokens").files(), self.node.module("tokens").FILES)


if __name__ == "__main__":
    unittest.main()
