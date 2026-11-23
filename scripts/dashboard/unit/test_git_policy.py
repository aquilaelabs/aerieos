"""aerie git policy's printer (scripts/lib/git-policy.py, B734): the first line
says whether a push can happen at all, from the push state aerie settings
--json carries, before the policy under it."""
import json
import os
import subprocess
import sys
import tempfile
import unittest

PRINTER = os.path.join(os.path.dirname(__file__), "..", "..", "lib", "git-policy.py")


def policy(rec):
    r = subprocess.run([sys.executable, PRINTER], input=json.dumps(rec), capture_output=True, text=True, check=False)
    return r.stdout


class GitPolicy(unittest.TestCase):
    def test_no_rights_says_so_first(self):
        out = policy({"gitpol": {"push": "allow"}, "push": {"rights": False, "auth": "token"}})
        self.assertTrue(out.startswith("push at all:     no: this space was given no push rights"), out)
        self.assertIn("push its branch: allow", out)

    def test_https_with_no_credential_says_so(self):
        out = policy({"push": {"rights": True, "auth": "none"}})
        self.assertIn("no: its remote is https and the controller holds no credential", out.splitlines()[0])

    def test_a_key_or_a_token_is_a_yes(self):
        self.assertIn("yes (the key its ssh address carries)", policy({"push": {"rights": True, "auth": "ssh"}}).splitlines()[0])
        self.assertIn("yes (the token the controller holds)", policy({"push": {"rights": True, "auth": "token"}}).splitlines()[0])

    def test_a_record_without_the_state_prints_the_policy_alone(self):
        out = policy({"gitpol": {"push": "deny", "main": "deny"}})
        self.assertTrue(out.startswith("push its branch: deny"), out)

    def test_the_hold_on_a_sensitive_push(self):
        self.assertIn("hold a sensitive push: hold", policy({"gitpol": {}}))
        self.assertIn("hold a sensitive push: off (the space's policy lets a push go unread)",
                      policy({"gitpol": {"scan": "off"}}))


class PushState(unittest.TestCase):
    """Whether an https remote has a credential, read off the repository's
    credential.helper (B1118): git-credential-bb on the space's token file
    is one, as git's store in the form older installs wrote is."""
    def _state(self, helper):
        # push_state alone, read out of the verbs' file: loading the file runs
        # the verb its command line names.
        import ast
        src = open(os.path.join(os.path.dirname(__file__), "..", "..", "lib", "settings-verbs.py")).read()
        fn = next(n for n in ast.parse(src).body if isinstance(n, ast.FunctionDef) and n.name == "push_state")
        ns = {"json": json, "os": os}
        exec(compile(ast.Module(body=[fn], type_ignores=[]), "settings-verbs.py", "exec"), ns)
        ws, state = tempfile.mkdtemp(), tempfile.mkdtemp()
        tree = os.path.join(ws, "alpha")
        env = {**os.environ, "GIT_CONFIG_GLOBAL": os.devnull, "GIT_CONFIG_NOSYSTEM": "1"}
        subprocess.run(["git", "init", "-q", tree], check=True, env=env)
        subprocess.run(["git", "-C", tree, "remote", "add", "origin", "https://forge.example/o/alpha.git"], check=True, env=env)
        if helper:
            subprocess.run(["git", "-C", tree, "config", "--local", "--add", "credential.helper", helper], check=True, env=env)
        with open(os.path.join(state, "push-rights.json"), "w") as f:
            json.dump({"alpha": {"how": "token"}}, f)
        old = os.environ.get("WORKSPACE")
        os.environ["WORKSPACE"] = ws
        try:
            return ns["push_state"](state, "alpha")
        finally:
            if old is None:
                os.environ.pop("WORKSPACE", None)
            else:
                os.environ["WORKSPACE"] = old

    def test_the_credential_helper_is_a_token(self):
        st = self._state("!/opt/aerieos/scripts/dashboard/git-credential-bb /config/gitcreds/alpha")
        self.assertEqual(st, {"rights": True, "auth": "token"})

    def test_the_older_store_is_a_token_too(self):
        self.assertEqual(self._state("store --file=/config/gitcreds/alpha")["auth"], "token")

    def test_none_is_none(self):
        self.assertEqual(self._state("")["auth"], "none")


class Prefs(unittest.TestCase):
    """The hold is a third key of the git policy with its own two values
    (the operator, 15 Oct): hold by default, off to let a push go unread."""
    def test_scan_takes_hold_or_off(self):
        sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))
        import prefs

        def write_json(path, data):
            with open(path, "w") as f:
                json.dump(data, f)
        prefs.configure(write_json=write_json, state=tempfile.mkdtemp())
        self.assertEqual(prefs.get("alpha")["gitpol"], {"push": "allow", "main": "deny", "scan": "hold"})
        self.assertNotIn("error", prefs.set_prefs("alpha", gitpol={"scan": "off"}))
        self.assertEqual(prefs.get("alpha")["gitpol"], {"push": "allow", "main": "deny", "scan": "off"})
        self.assertIn("hold or off", prefs.set_prefs("alpha", gitpol={"scan": "allow"})["error"])
        self.assertIn("allow or deny", prefs.set_prefs("alpha", gitpol={"push": "off"})["error"])


if __name__ == "__main__":
    unittest.main()
