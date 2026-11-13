"""The shipped agents signed in by the one driver a pack's agent is (R234
step 6): each row of the agents' table says its sign-in as the data a
manifest carries, held by the manifest's own validator, and
scripts/lib/login-flow.py runs each program from it. The programs here are
stand-ins that draw the screens the real ones drew on 12 Nov (Claude Code,
Codex CLI 0.164.0, Copilot CLI, Grok Build); never a real account."""
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
sys.path.insert(0, os.path.join(HERE, "..", "..", "agent"))
import agents  # noqa: E402
import toolpacks  # noqa: E402
from aerieos_agent import base, tokens, tokenwatch  # noqa: E402

FLOW = os.path.join(HERE, "..", "..", "lib", "login-flow.py")
LIST = os.path.join(HERE, "..", "..", "lib", "login-list.py")

LINK = ("https://claude.com/cai/oauth/authorize?code=true&client_id=9d1c250a&response_type=code"
        "&redirect_uri=https%3A%2F%2Fplatform.claude.com%2Foauth%2Fcode%2Fcallback&scope=org%3Acreate_api_key"
        "+user%3Aprofile&code_challenge=1Hwngyh1Ihh80Q&code_challenge_method=S256&state=XPQEcWJxK6HQ")
PROGRAMS = {
    # Claude Code: the link, wrapped at the terminal's width, then a prompt
    # with no newline; it ends itself, clean when it took the code.
    "claude": r'''#!/usr/bin/env python3
import os, sys, json
if sys.argv[1:] == ["auth", "logout"]:
    os.unlink(os.path.expanduser("~/.claude/.credentials.json")); sys.exit(0)
assert sys.argv[1:] == ["auth", "login"], sys.argv
w = os.get_terminal_size().columns
link = "%s"
print("Browser didn't open? Use the url below to sign in (c to copy)\n")
print("\n".join(link[i:i + w] for i in range(0, len(link), w)))
sys.stdout.write("\nPaste code here if prompted > "); sys.stdout.flush()
code = sys.stdin.readline().strip()
if code != "good-code":
    print("\nOAuth error: Invalid code. Please make sure the full code was copied"); sys.exit(1)
with open(os.path.expanduser("~/.claude/.credentials.json"), "w") as f: f.write('{"claudeAiOauth": {}}')
with open(os.path.expanduser("~/.claude.json"), "w") as f: json.dump({"oauthAccount": {"emailAddress": "me@example.invalid"}}, f)
print("\nLogin successful.")
''' % LINK,
    # Codex CLI 0.164.0's device login.
    "codex": r'''#!/usr/bin/env python3
import os, sys, time, json, base64
if sys.argv[1:] == ["logout"]:
    os.unlink(os.path.expanduser("~/.codex/auth.json")); print("Successfully logged out"); sys.exit(0)
assert sys.argv[1:] == ["login", "--device-auth"], sys.argv
sys.stdout.write("\r\nWelcome to Codex [v\x1b[90m0.164.0\x1b[0m]\r\n\x1b[90mOpenAI's command-line coding agent\x1b[0m\r\n\r\n"
  "Follow these steps to sign in with ChatGPT using device code authorization:\r\n\r\n"
  "1. Open this link in your browser and sign in to your account\r\n   \x1b[94mhttps://auth.openai.com/codex/device\x1b[0m\r\n\r\n"
  "2. Enter this one-time code \x1b[90m(expires in 15 minutes)\x1b[0m\r\n   \x1b[94mEPT0-QARQH\x1b[0m\r\n\r\n"
  "\x1b[90mContinue only if you started this login in Codex. If a website or another person gave you this code, cancel.\x1b[0m\r\n\r\n")
sys.stdout.flush()
time.sleep(1.5)
if os.environ.get("FAKE_REFUSE"):
    print("Error: device auth timed out after 15 minutes"); sys.exit(1)
enc = lambda d: base64.urlsafe_b64encode(json.dumps(d).encode()).decode().rstrip("=")
os.makedirs(os.path.expanduser("~/.codex"), exist_ok=True)
with open(os.path.expanduser("~/.codex/auth.json"), "w") as f:
    json.dump({"tokens": {"id_token": enc({"alg": "none"}) + "." + enc({"email": "me@example.invalid", "https://api.openai.com/auth": {"chatgpt_plan_type": "plus"}}) + ".sig"}}, f)
print("Successfully logged in")
''',
    # Copilot CLI: its link and code on one line, then, with no keyring, a
    # question it waits at.
    "copilot": r'''#!/usr/bin/env python3
import os, sys, time, json
assert sys.argv[1:] == ["login", "--device-code"], sys.argv
with open(os.path.expanduser("~/copilot.env"), "w") as f: f.write(os.environ.get("COPILOT_AUTO_UPDATE", "(unset)"))
sys.stdout.write("To authenticate, visit https://github.com/login/device and enter code D52E-959A\r\nWaiting for authorization...\r\n"
  "\x1b]52;p!;RDUyRS05NTlB;\x07\x1b]52;c;RDUyRS05NTlB\x07Failed to open browser. Please visit https://github.com/login/device and enter the code D52E-959A manually.\r\n")
sys.stdout.flush()
time.sleep(1.2)
sys.stdout.write("No system keyring is available. Store the token in the plaintext config file? (y/N) "); sys.stdout.flush()
if sys.stdin.readline().strip().lower() != "y":
    print("Not signed in."); sys.exit(1)
os.makedirs(os.path.expanduser("~/.copilot"), exist_ok=True)
with open(os.path.expanduser("~/.copilot/config.json"), "w") as f:
    f.write("// managed\n" + json.dumps({"lastLoggedInUser": {"login": "octo"}, "copilot_tokens": {"x": "gho_x"}, "theme": "dark"}))
print("Signed in as octo")
''',
    # Grok Build's device code.
    "grok": r'''#!/usr/bin/env python3
import os, sys, time, json
if sys.argv[1:] == ["logout"]:
    os.unlink(os.path.expanduser("~/.grok/auth.json")); sys.exit(0)
assert sys.argv[1:] == ["login", "--device-auth"], sys.argv
assert os.environ.get("GROK_DISABLE_AUTOUPDATER") == "1"
sys.stdout.write("\r\nTo sign in, open this URL in your browser:\r\n\r\n  https://accounts.x.ai/oauth2/device?user_code=5CEY-7C5K\r\n\r\n"
  "  (Could not open browser automatically: open the URL above manually.)\r\n\r\nConfirm this code in your browser:\r\n\r\n  5CEY-7C5K\r\n\r\n"
  "\x1b[90mOnly continue with a code you requested. Don't share it with anyone.\x1b[0m\r\n\r\nWaiting for authorization...\r\n")
sys.stdout.flush()
time.sleep(1.5)
os.makedirs(os.path.expanduser("~/.grok"), exist_ok=True)
with open(os.path.expanduser("~/.grok/auth.json"), "w") as f: json.dump({"token": "opaque"}, f)
''',
}


class TheTablesData(unittest.TestCase):
    def test_each_shipped_sign_in_is_what_a_manifest_may_say(self):
        for a in agents.TABLE:
            if not a.signin:
                self.assertFalse(a.login_job, f"{a.id} has a sign-in job and says no sign-in")
                continue
            errors = []
            got = toolpacks.signin_checked(a.signin, a.command, errors)
            self.assertEqual(errors, [], a.id)
            for k, v in a.signin["flow"].items():
                self.assertEqual(got["flow"][k], v, f"{a.id}: {k} is kept as written")
            self.assertTrue(a.login_job and a.logout_job, a.id)

    def test_every_agent_with_a_sign_in_job_describes_its_flow(self):
        self.assertEqual(sorted(agents.signs_in()), sorted(a.id for a in agents.TABLE if a.login_job))
        self.assertEqual(agents.flow_of("open"), None, "Any model signs in to nobody")

    def test_its_official_manifest_carries_it_and_says_the_framework_it_needs(self):
        for a in agents.TABLE:
            with open(os.path.join(HERE, "..", "..", "..", "packs", "agents", a.id, "bbtool.json"), encoding="utf-8") as f:
                m = json.load(f)
            self.assertEqual(m["agent"].get("signin"), a.signin, a.id)
            got, errors = toolpacks.validate(m)
            self.assertEqual(errors, [], a.id)
            if a.signin:
                self.assertEqual(got["agent"]["signin"]["flow"]["kept"], a.signin["flow"]["kept"])
                # The least that holds what it uses, whatever this build reads now.
                self.assertEqual(m.get("framework"), "2.2", f"{a.id}: who is signed in read from a named file is 2.2's")

    def test_who_and_forget_are_held_to_plain_keys(self):
        base = {"login": ["foo", "login"], "flow": {"url": "https://auth.example.com/", "code_after": "enter code", "kept": ".foo/auth.json"}}

        def check(**flow):
            errors = []
            toolpacks.signin_checked({**base, "flow": {**base["flow"], **flow}}, "foo", errors)
            return errors
        self.assertEqual(check(who={"email": ["account", "email"], "plan": ["account", "plan"], "named": "an Example account"}), [])
        self.assertEqual(check(forget={"keys": ["user"], "like": "token"}), [])
        for bad in ({"email": "account.email"}, {"email": []}, {"email": ["a b"]}, {"email": ["x"] * 7}, {"file": "/etc/passwd"},
                    {"file": "../x"}, {"named": "<b>"}, {"key_named": "an Example API key"}, "nobody"):
            self.assertTrue(check(who=bad), bad)
        for bad in ({}, {"keys": ["a b"]}, {"like": "T*"}, {"keys": ["x"], "file": "../y"}, ["user"]):
            self.assertTrue(check(forget=bad), bad)
        self.assertTrue(check(forget={"keys": ["user"]}, logout=["foo", "logout"]), "its own command or the keys, not both")


class TheNodesAgent(unittest.TestCase):
    """The node's agent carries no dashboard module, so its copy of where
    each sign-in is kept and whom it names is held to the table here."""

    def test_its_copy_is_the_tables(self):
        self.assertEqual(sorted(base.SIGNINS), sorted(agents.signs_in()))
        for agent, row in base.SIGNINS.items():
            a, flow = agents.get(agent), agents.flow_of(agent)
            self.assertEqual((row["kept"], row["provider"], row.get("who")), (flow["kept"], a.provider, flow.get("who")), agent)

    def test_what_is_sealed_and_watched_follows_from_it(self):
        self.assertEqual(dict(tokens.FILES), {a: os.path.join(*r["kept"].split("/")) for a, r in base.SIGNINS.items()})
        self.assertEqual(tokenwatch.TOKENS, {".claude": ".credentials.json", ".codex": "auth.json", ".copilot": "config.json", ".grok": "auth.json"})

    def test_a_seals_header_names_whom_the_open_file_would(self):
        enc = lambda d: __import__("base64").urlsafe_b64encode(json.dumps(d).encode()).decode().rstrip("=")  # noqa: E731
        idt = enc({"alg": "none"}) + "." + enc({"email": "me@example.invalid", "https://api.openai.com/auth": {"chatgpt_plan_type": "plus"}}) + ".sig"
        self.assertEqual(tokens.about("codex", json.dumps({"tokens": {"id_token": idt}}).encode(), "/nowhere"),
                         {"agent": "codex", "email": "me@example.invalid", "plan": "plus"})
        self.assertEqual(tokens.about("codex", b'{"OPENAI_API_KEY": "sk-not-real"}', "/nowhere"),
                         {"agent": "codex", "email": "an OpenAI API key", "plan": "API"})
        self.assertEqual(tokens.about("codex", b"{}", "/nowhere"), {"agent": "codex", "email": "", "plan": ""})
        self.assertEqual(tokens.about("grok", b'{"token": "opaque"}', "/nowhere"), {"agent": "grok", "email": "an xAI account"})
        self.assertEqual(tokens.about("grok", json.dumps({"s": {"access_token": idt}}).encode(), "/nowhere"), {"agent": "grok", "email": "me@example.invalid"})
        self.assertEqual(tokens.about("grok", b"not json", "/nowhere"), {"agent": "grok"})
        self.assertEqual(tokens.about("copilot", b'// managed\n{"lastLoggedInUser": {"login": "octo"}}', "/nowhere"), {"agent": "copilot", "email": "octo"})
        d = tempfile.mkdtemp()
        self.addCleanup(shutil.rmtree, d, True)
        with open(os.path.join(d, ".claude.json"), "w") as f:
            json.dump({"oauthAccount": {"emailAddress": "me@example.invalid"}}, f)
        self.assertEqual(tokens.about("claude", b'{"claudeAiOauth": {}}', d), {"agent": "claude", "email": "me@example.invalid"})
        self.assertEqual(tokens.about("claude", b"{}", "/nowhere"), {"agent": "claude"})
        self.assertEqual(tokens.about("nobody", b"{}", "/nowhere"), {"agent": "nobody"})


class OnTheNode(unittest.TestCase):
    def setUp(self):
        self.d = tempfile.mkdtemp()
        self.addCleanup(shutil.rmtree, self.d, True)
        self.home = os.path.join(self.d, "users", "u_0123abcd")
        self.bin = os.path.join(self.d, "bin")
        os.makedirs(self.home), os.makedirs(self.bin)
        for name, text in PROGRAMS.items():
            with open(os.path.join(self.bin, name), "w") as f:
                f.write(text)
            os.chmod(os.path.join(self.bin, name), 0o755)
        # Its own programs and the system's, never this machine's agents.
        self.env = {"HOME": self.home, "PATH": self.bin + ":/usr/bin:/bin", "BB_NODE": "node one", "BB_FLOW_KEEP_S": "3",
                    "BB_TOOLPACKS_JSON": os.path.join(self.d, "none.json"), "LANG": "C.UTF-8"}

    def flow(self, agent, *answers, env=None, limit=40):
        """The driver run as the job runs it, under a terminal: each of
        `answers` is (the words waited for, the line typed then)."""
        master, slave = pty.openpty()
        p = subprocess.Popen([sys.executable, FLOW, "in", agent], stdin=slave, stdout=slave, stderr=slave, env=dict(self.env, **(env or {})),
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

    def out(self, agent):
        return subprocess.run([sys.executable, FLOW, "out", agent], env=self.env, capture_output=True, text=True, check=False)

    def listed(self):
        p = subprocess.run([sys.executable, LIST], env={"BB_USERS_DIR": os.path.dirname(self.home), "PATH": os.environ["PATH"],
                                                       "BB_TOOLPACKS_JSON": self.env["BB_TOOLPACKS_JSON"]}, capture_output=True, text=True, check=True)
        return json.loads(p.stdout)[0]

    def test_claude_the_link_whole_the_code_typed_and_signed_in_when_it_ends_clean(self):
        log, code = self.flow("claude", ("Paste code", "good-code"))
        self.assertEqual(code, 0, log)
        self.assertIn(f"[aerieos] open this link to sign in: {LINK}\r\n", log, "one row of a wide terminal, never wrapped")
        self.assertIn("[aerieos] signed in to Claude on node one", log)
        self.assertNotIn("good-code", log, "the code is typed into the program and never said back up the log")
        self.assertNotIn("Browser didn't open", log, "the program's screen is not the log")
        self.assertEqual(self.listed()["email"], "me@example.invalid")
        self.assertEqual(self.out("claude").returncode, 0)
        self.assertEqual(self.listed()["email"], "")

    def test_claude_a_code_it_does_not_take_fails_in_its_own_words(self):
        log, code = self.flow("claude", ("Paste code", "not-the-code"))
        self.assertEqual(code, 1, log)
        self.assertIn("Claude did not keep a sign-in after the code; its screen last said:", log)
        self.assertIn("OAuth error: Invalid code", log)
        self.assertNotIn("not-the-code", log)

    def test_codex_the_link_and_the_code_and_who_from_its_id_token(self):
        log, code = self.flow("codex")
        self.assertEqual(code, 0, log)
        self.assertIn("[aerieos] open this link to sign in: https://auth.openai.com/codex/device\r\n", log)
        self.assertIn("[aerieos] then enter this code there: EPT0-QARQH\r\n", log)
        self.assertIn("[aerieos] signed in to ChatGPT on node one", log)
        self.assertEqual(self.listed()["agents"]["codex"], {"email": "me@example.invalid", "plan": "plus"})
        self.assertEqual(self.out("codex").returncode, 0)
        self.assertNotIn("codex", self.listed()["agents"])

    def test_codex_a_login_that_fails_says_why_in_its_words(self):
        log, code = self.flow("codex", env={"FAKE_REFUSE": "1"})
        self.assertEqual(code, 1, log)
        self.assertIn("ChatGPT did not keep a sign-in; its screen last said:", log)
        self.assertIn("Error: device auth timed out after 15 minutes", log)

    def test_copilot_its_question_is_answered_its_updater_off_and_its_sign_out_forgets_the_login_alone(self):
        log, code = self.flow("copilot")
        self.assertEqual(code, 0, log)
        self.assertIn("[aerieos] open this link to sign in: https://github.com/login/device\r\n", log)
        self.assertIn("[aerieos] then enter this code there: D52E-959A\r\n", log)
        with open(os.path.join(self.home, "copilot.env")) as f:
            self.assertEqual(f.read(), "false", "what its row says its sign-in runs with")
        self.assertEqual(self.listed()["agents"]["copilot"], {"email": "octo", "plan": ""})
        got = self.out("copilot")
        self.assertEqual(got.returncode, 0, got.stdout + got.stderr)
        with open(os.path.join(self.home, ".copilot", "config.json")) as f:
            text = f.read()
        self.assertTrue(text.startswith("// managed\n"))
        self.assertEqual(json.loads(text.split("\n", 1)[1]), {"theme": "dark"}, "its settings stay; the login and the token go")
        self.assertNotIn("copilot", self.listed()["agents"])

    def test_grok_the_link_with_its_code_and_an_account_that_names_nobody(self):
        log, code = self.flow("grok")
        self.assertEqual(code, 0, log)
        self.assertIn("[aerieos] open this link to sign in: https://accounts.x.ai/oauth2/device?user_code=5CEY-7C5K\r\n", log)
        self.assertIn("[aerieos] then enter this code there: 5CEY-7C5K\r\n", log)
        self.assertEqual(self.listed()["agents"]["grok"], {"email": "an xAI account", "plan": ""})
        self.assertEqual(self.out("grok").returncode, 0)
        self.assertNotIn("grok", self.listed()["agents"])

    def test_a_program_that_is_not_here_says_where_it_is_installed(self):
        os.unlink(os.path.join(self.bin, "grok"))
        log, code = self.flow("grok")
        self.assertEqual(code, 1)
        self.assertIn("Grok Build is not installed on this machine: Install on Grok's card in the Library", log)


if __name__ == "__main__":
    unittest.main()
