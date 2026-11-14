"""A deploy key is kept sealed under the install key and opened only into
the ssh agent (R243; the audit of 13 Nov): the page said sealed and safe in
a copy of /config, and scripts/deploy-key kept each as a plain key file
with no passphrase, guarded by its mode alone. The helper itself, run here
on a store of its own against a real ssh-agent: what is on disk is never a
private key, a plain one from before is sealed the first time the keys are
loaded, an install key's change is followed, and an install with no key
keeps a key plain and says so."""
import importlib.util
import os
import shutil
import subprocess
import sys
import tempfile
import unittest

HERE = os.path.dirname(os.path.abspath(__file__))
SCRIPTS = os.path.abspath(os.path.join(HERE, "..", ".."))
HELPER = os.path.join(SCRIPTS, "deploy-key")
SEAL = os.path.join(SCRIPTS, "lib", "sealfile.py")
HAVE = all(shutil.which(t) for t in ("ssh-agent", "ssh-add", "ssh-keygen")) and importlib.util.find_spec("cryptography") is not None


@unittest.skipUnless(HAVE, "ssh's tools and the cryptography library are needed")
class Sealed(unittest.TestCase):
    def setUp(self):
        # Under /tmp by name: a socket's path is 108 characters at most.
        self.run_dir = tempfile.mkdtemp(prefix="dk", dir="/tmp")
        self.store = tempfile.mkdtemp()
        self.addCleanup(shutil.rmtree, self.run_dir, True)
        self.addCleanup(shutil.rmtree, self.store, True)
        self.sock = os.path.join(self.run_dir, "ssh-agent.sock")
        out = subprocess.run(["ssh-agent", "-a", self.sock], capture_output=True, text=True, check=True).stdout
        pid = out.split("SSH_AGENT_PID=")[1].split(";")[0]
        self.addCleanup(subprocess.run, ["kill", pid], check=False)
        self.key, self.prev = os.path.join(self.run_dir, "key"), os.path.join(self.run_dir, "key-previous")
        self.put_key("k" * 64)
        with open(os.path.join(self.run_dir, "install-key.where"), "w") as f:
            f.write(f"{self.key}\n{self.prev}\n")
        self.env = dict(os.environ, BB_RUN_DIR=self.run_dir, BB_DEPLOY_KEY_STORE=self.store)

    def put_key(self, text):
        with open(self.key, "w") as f:
            f.write(text)

    def dk(self, *argv, stdin=None):
        return subprocess.run(["bash", HELPER, *argv], input=stdin, capture_output=True, text=True, check=False, env=self.env)

    def loaded(self):
        p = subprocess.run(["ssh-add", "-l"], capture_output=True, text=True, check=False, env=dict(os.environ, SSH_AUTH_SOCK=self.sock))
        return sorted(ln.split()[2] for ln in p.stdout.splitlines() if len(ln.split()) > 2)

    def unload(self):
        subprocess.run(["ssh-add", "-D"], capture_output=True, check=False, env=dict(os.environ, SSH_AUTH_SOCK=self.sock))

    def plain_on_disk(self):
        out = []
        for name in os.listdir(self.store):
            with open(os.path.join(self.store, name), "rb") as f:
                if b"PRIVATE KEY" in f.read():
                    out.append(name)
        return out

    def test_a_key_made_or_pasted_is_sealed_on_disk_and_open_in_the_agent(self):
        p = self.dk("make", "app-deploy")
        self.assertEqual(p.returncode, 0, p.stderr)
        self.assertTrue(p.stdout.startswith("ssh-ed25519 "))
        self.assertEqual(sorted(os.listdir(self.store)), ["app-deploy.pub", "app-deploy.sealed"])
        self.assertEqual(os.stat(os.path.join(self.store, "app-deploy.sealed")).st_mode & 0o777, 0o600)
        self.assertEqual(self.plain_on_disk(), [])
        self.assertEqual(self.loaded(), ["app-deploy"])
        # Pasted: the same, and its name is the agent's name for it.
        subprocess.run(["ssh-keygen", "-q", "-t", "ed25519", "-N", "", "-C", "somebody@laptop", "-f", os.path.join(self.run_dir, "pasted")], check=True)
        with open(os.path.join(self.run_dir, "pasted")) as f:
            p = self.dk("store", "site-deploy", stdin=f.read())
        self.assertEqual(p.returncode, 0, p.stderr)
        self.assertEqual(self.plain_on_disk(), [])
        self.assertEqual(self.loaded(), ["app-deploy", "site-deploy"])
        self.assertEqual(self.dk("--list").stdout.split(), ["app-deploy", "site-deploy"])
        self.assertIn("kept already", self.dk("make", "app-deploy").stderr)
        # Forgotten: out of the agent and off the disk.
        self.assertEqual(self.dk("forget", "site-deploy").returncode, 0)
        self.assertEqual(self.loaded(), ["app-deploy"])
        self.assertEqual(sorted(os.listdir(self.store)), ["app-deploy.pub", "app-deploy.sealed"])

    def test_a_plain_key_from_before_is_sealed_when_the_keys_are_next_loaded(self):
        subprocess.run(["ssh-keygen", "-q", "-t", "ed25519", "-N", "", "-C", "old-deploy", "-f", os.path.join(self.store, "old-deploy")], check=True)
        self.assertEqual(self.plain_on_disk(), ["old-deploy"])
        p = self.dk("--load")
        self.assertEqual(p.stdout.strip(), "1", p.stderr)
        self.assertIn("old-deploy is sealed under the install key now", p.stderr)
        self.assertEqual(self.plain_on_disk(), [])
        self.assertEqual(sorted(os.listdir(self.store)), ["old-deploy.pub", "old-deploy.sealed"])
        self.assertEqual(self.loaded(), ["old-deploy"])
        # The next start loads it from its seal, and says nothing.
        self.unload()
        p = self.dk("--load")
        self.assertEqual((p.stdout.strip(), p.stderr.strip()), ("1", ""))
        self.assertEqual(self.loaded(), ["old-deploy"])

    def test_an_install_keys_change_is_followed(self):
        self.dk("make", "app-deploy")
        sealed = os.path.join(self.store, "app-deploy.sealed")
        shutil.copy(self.key, self.prev)
        self.put_key("n" * 64)
        # Under the key before: still opened, while that key is kept...
        self.unload()
        self.assertEqual(self.dk("--load").stdout.strip(), "1")
        self.assertNotEqual(subprocess.run([sys.executable, SEAL, "current", self.key], stdin=open(sealed, "rb"), check=False).returncode, 0)
        # ...and sealed again under today's by the pass the change runs.
        p = self.dk("--reseal")
        self.assertEqual((p.returncode, p.stdout.strip()), (0, "1"), p.stderr)
        self.assertEqual(subprocess.run([sys.executable, SEAL, "current", self.key], stdin=open(sealed, "rb"), check=False).returncode, 0)
        self.assertEqual(self.dk("--reseal").stdout.strip(), "0", "a second pass finds nothing to do")
        os.unlink(self.prev)
        self.unload()
        self.assertEqual(self.dk("--load").stdout.strip(), "1")
        # One sealed under a key that is gone is said, and the pass fails so the change keeps the old key.
        self.put_key("z" * 64)
        p = self.dk("--reseal")
        self.assertNotEqual(p.returncode, 0)
        self.assertIn("app-deploy could not be opened to seal it again", p.stderr)
        self.unload()
        p = self.dk("--load")
        self.assertEqual(p.stdout.strip(), "0")
        self.assertIn("could not load deploy key app-deploy", p.stderr)

    def test_with_no_install_key_a_key_is_kept_plain_and_that_is_said(self):
        os.unlink(os.path.join(self.run_dir, "install-key.where"))
        p = self.dk("make", "app-deploy")
        self.assertEqual(p.returncode, 0, p.stderr)
        self.assertIn("kept as a plain key file: this install has no install key", p.stderr)
        self.assertEqual(sorted(os.listdir(self.store)), ["app-deploy", "app-deploy.pub"])
        self.assertEqual(self.loaded(), ["app-deploy"])
        self.assertIn("no install key", self.dk("--reseal").stderr)

    def test_it_is_roots_alone_on_the_real_store(self):
        if os.geteuid() == 0:
            self.skipTest("root may")
        env = {k: v for k, v in self.env.items() if k != "BB_DEPLOY_KEY_STORE"}
        p = subprocess.run(["bash", HELPER, "--list"], capture_output=True, text=True, check=False, env=env)
        self.assertNotEqual(p.returncode, 0)
        self.assertIn("must run as root", p.stderr)


class Tool(unittest.TestCase):
    """lib/sealfile.py: the controller's own seal, for a helper in shell."""

    def run_it(self, *argv, data=b""):
        return subprocess.run([sys.executable, SEAL, *argv], input=data, capture_output=True, check=False)

    @unittest.skipUnless(importlib.util.find_spec("cryptography") is not None, "the cryptography library is needed")
    def test_sealed_opened_and_refused(self):
        d = tempfile.mkdtemp()
        self.addCleanup(shutil.rmtree, d, True)
        key, other = os.path.join(d, "key"), os.path.join(d, "other")
        for path, text in ((key, "k" * 64), (other, "o" * 64)):
            with open(path, "w") as f:
                f.write(text)
        blob = self.run_it("seal", key, data=b"a private key").stdout
        self.assertTrue(blob.startswith(b"BBSEAL2"), "the vetted format, never the older one")
        self.assertNotIn(b"a private key", blob)
        self.assertEqual(self.run_it("open", key, data=blob).stdout, b"a private key")
        self.assertEqual(self.run_it("current", key, data=blob).returncode, 0)
        # Another install's key: refused, and nothing written.
        p = self.run_it("open", other, data=blob)
        self.assertEqual((p.returncode, p.stdout), (5, b""))
        self.assertEqual(self.run_it("current", other, data=blob).returncode, 1)
        # ...opened by the key before, while a change keeps it.
        self.assertEqual(self.run_it("open", other, key, data=blob).stdout, b"a private key")
        self.assertEqual(self.run_it("seal", os.path.join(d, "nothing"), data=b"x").returncode, 3)
        self.assertEqual(self.run_it("seal").returncode, 2)


class Boot(unittest.TestCase):
    """Boot leaves root the two paths (lib/boot.sh install_key_where): sudo
    hands the helper none of the boot's environment."""

    def sh(self, body, env):
        pre = f'set -euo pipefail\n. "{SCRIPTS}/lib/common.sh"\n. "{SCRIPTS}/lib/boot.sh"\n'
        return subprocess.run(["bash", "-c", pre + body], capture_output=True, text=True, timeout=60, check=False, env=dict(os.environ, **env))

    def test_what_the_helper_says_at_boot_reaches_the_log(self):
        # The boot threw its words away, so a key it could not load, or one
        # it had just sealed, was never said (met on the dev instance's walk).
        with open(os.path.join(SCRIPTS, "lib", "boot.sh"), encoding="utf-8") as f:
            line = next(ln for ln in f if "deploy-key --load" in ln and not ln.lstrip().startswith("#"))
        self.assertNotIn("2>/dev/null", line)

    def test_the_deploy_keys_are_loaded_once_the_install_key_is_settled(self):
        # They are sealed under it. Loaded from setup_ssh_agent, which runs
        # before install_key_file, a new container had no key to open them
        # with and loaded none (the dev instance, the first rebuild after
        # its key was sealed): both boots load them after, before the hooks.
        boot = open(os.path.join(SCRIPTS, "lib", "boot.sh"), encoding="utf-8").read()
        agent = boot[boot.index("\nsetup_ssh_agent() {"):]
        agent = agent[:agent.index("\n}\n")]
        self.assertNotIn("deploy-key --load", "\n".join(ln for ln in agent.splitlines() if not ln.lstrip().startswith("#")))
        self.assertIn("\nload_deploy_keys() {", boot)
        for f in ("entrypoint.sh", "host-boot.sh"):
            text = open(os.path.join(SCRIPTS, f), encoding="utf-8").read()
            main = text[text.index("main() {"):]
            calls = [ln.strip() for ln in main[:main.index("\n}\n")].splitlines()
                     if ln.strip() in ("setup_ssh_agent", "install_key_file", "load_deploy_keys", "run_hooks")]
            self.assertEqual(calls, ["setup_ssh_agent", "install_key_file", "load_deploy_keys", "run_hooks"], f)

    def test_a_new_containers_boot_opens_a_sealed_key(self):
        # The same order run for real, on a store of its own: the agent
        # first, then the key's place written, then the keys loaded.
        if not HAVE:
            self.skipTest("ssh's tools and the cryptography library are needed")
        run_dir, store, secrets = tempfile.mkdtemp(prefix="dk", dir="/tmp"), tempfile.mkdtemp(), tempfile.mkdtemp()
        for d in (run_dir, store, secrets):
            self.addCleanup(shutil.rmtree, d, True)
        sock = os.path.join(run_dir, "ssh-agent.sock")
        out = subprocess.run(["ssh-agent", "-a", sock], capture_output=True, text=True, check=True).stdout
        self.addCleanup(subprocess.run, ["kill", out.split("SSH_AGENT_PID=")[1].split(";")[0]], check=False)
        env = {"BB_RUN_DIR": run_dir, "BB_DEPLOY_KEY_STORE": store, "BB_SECRETS_DIR": secrets, "DASHBOARD_STATE": tempfile.mkdtemp()}
        self.addCleanup(shutil.rmtree, env["DASHBOARD_STATE"], True)
        helper = os.path.join(SCRIPTS, "deploy-key")
        # A first boot settles the key; a key is made while it runs.
        self.assertEqual(self.sh("BB_ACCOUNT=$(id -un); install_key_made", env).returncode, 0)
        made = subprocess.run(["bash", helper, "make", "app-deploy"], capture_output=True, text=True, check=False, env=dict(os.environ, **env))
        self.assertEqual(made.returncode, 0, made.stderr)
        self.assertEqual(sorted(os.listdir(store)), ["app-deploy.pub", "app-deploy.sealed"])
        # A new container: nothing of /run from before.
        subprocess.run(["ssh-add", "-D"], capture_output=True, check=False, env=dict(os.environ, SSH_AUTH_SOCK=sock))
        os.unlink(os.path.join(run_dir, "install-key.where"))
        early = subprocess.run(["bash", helper, "--load"], capture_output=True, text=True, check=False, env=dict(os.environ, **env))
        self.assertEqual(early.stdout.strip(), "0", "before the key's place is written there is nothing to open it with")
        self.assertIn("this install's key is not here to open it", early.stderr)
        self.assertEqual(self.sh("BB_ACCOUNT=$(id -un); install_key_made", env).returncode, 0)
        late = subprocess.run(["bash", helper, "--load"], capture_output=True, text=True, check=False, env=dict(os.environ, **env))
        self.assertEqual((late.stdout.strip(), late.stderr.strip()), ("1", ""))

    def test_a_key_the_install_made_and_one_from_the_environment(self):
        run, secrets, state = tempfile.mkdtemp(), tempfile.mkdtemp(), tempfile.mkdtemp()
        for d in (run, secrets, state):
            self.addCleanup(shutil.rmtree, d, True)
        where = os.path.join(run, "install-key.where")
        r = self.sh("BB_ACCOUNT=$(id -un); install_key_made", {"BB_RUN_DIR": run, "BB_SECRETS_DIR": secrets, "DASHBOARD_STATE": state})
        self.assertEqual(r.returncode, 0, r.stderr)
        with open(where) as f:
            self.assertEqual(f.read().splitlines(), [f"{secrets}/install-key/key", f"{secrets}/install-key/key-previous"])
        self.assertEqual(os.stat(where).st_mode & 0o777, 0o600)
        # Set in the environment: the file boot writes it to, and the one before beside it.
        d = tempfile.mkdtemp()
        self.addCleanup(shutil.rmtree, d, True)
        body = (f'eval "$(declare -f install_key_file | sed "s#/run/builderbot-key#{d}/key#")"\n'
                "BB_ACCOUNT=$(id -un); install_key_file")
        r = self.sh(body, {"BB_RUN_DIR": run, "BB_SECRETS_DIR": "/nonexistent", "INSTALL_KEY": "k" * 32})
        self.assertEqual(r.returncode, 0, r.stderr)
        with open(where) as f:
            self.assertEqual(f.read().splitlines(), [f"{d}/key", f"{d}/key-previous"])
        # A key too short to seal with: nothing is named.
        r = self.sh(body, {"BB_RUN_DIR": run, "BB_SECRETS_DIR": "/nonexistent", "INSTALL_KEY": "short"})
        self.assertEqual(r.returncode, 0, r.stderr)
        self.assertFalse(os.path.exists(where))


if __name__ == "__main__":
    unittest.main()
