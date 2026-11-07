"""What a relayed verb's apply does to this tree (scripts/lib/relay.py): a
ref the controller moved that is the branch checked out here moves by a
fast-forward, the index and the files with it (B711: update-ref moved the
branch alone, and the next commit carried the old CHANGELOG.md back over the
section a release had committed). Proven against a stand-in controller."""
import json
import os
import shutil
import subprocess
import sys
import tempfile
import threading
import unittest
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer

LIB = os.path.join(os.path.dirname(__file__), "..", "..", "lib")


class Controller(BaseHTTPRequestHandler):
    refs = []

    def do_POST(self):
        n = int(self.headers.get("Content-Length") or 0)
        self.rfile.read(n)
        out = {"code": 0, "out": "", "err": "", "apply": {"refs": Controller.refs}}
        data = json.dumps(out).encode()
        self.send_response(200)
        self.send_header("Content-Type", "application/json")
        self.send_header("Content-Length", str(len(data)))
        self.end_headers()
        self.wfile.write(data)

    def log_message(self, format, *args):     # noqa: A002 (the base class's name)
        pass


class RelayApply(unittest.TestCase):
    def git(self, *a):
        return subprocess.run(["git", *a], cwd=self.repo, capture_output=True, text=True, check=True).stdout.strip()

    def setUp(self):
        self.tmp = tempfile.mkdtemp()
        self.addCleanup(shutil.rmtree, self.tmp, True)
        self.repo = os.path.join(self.tmp, "alpha")
        os.makedirs(self.repo)
        subprocess.run(["git", "init", "-q", "-b", "topic", self.repo], check=True)
        for k, v in (("user.name", "t"), ("user.email", "t@example.invalid")):
            self.git("config", k, v)
        with open(os.path.join(self.repo, "CHANGELOG.md"), "w") as f:
            f.write("## Unreleased\n")
        self.git("add", "-A")
        self.git("commit", "-q", "-m", "a")
        self.a = self.git("rev-parse", "HEAD")
        # The controller's commit on the same branch, its objects here (as
        # the apply's bundle leaves them) and the branch not yet moved.
        blob = subprocess.run(["git", "hash-object", "-w", "--stdin"], cwd=self.repo, input="## 1.0.0-dev.2\n",
                              capture_output=True, text=True, check=True).stdout.strip()
        tree = subprocess.run(["git", "mktree"], cwd=self.repo, input=f"100644 blob {blob}\tCHANGELOG.md\n",
                              capture_output=True, text=True, check=True).stdout.strip()
        self.b = self.git("commit-tree", tree, "-p", self.a, "-m", "the section")
        self.srv = ThreadingHTTPServer(("127.0.0.1", 0), Controller)
        threading.Thread(target=self.srv.serve_forever, daemon=True).start()
        self.addCleanup(self.srv.server_close)
        self.addCleanup(self.srv.shutdown)
        Controller.refs = [["refs/heads/topic", self.b], ["refs/remotes/origin/topic", self.b]]
        self.env = {**os.environ, "BB_CONTROLLER": f"http://127.0.0.1:{self.srv.server_port}",
                    "BB_AUTH_HEADER": "Bearer x", "BB_RELAY_PROJECT": "alpha", "HOME": self.tmp}
        self.env.pop("BB_CONTROLLER_PIN", None)

    def relay(self, *words):
        return subprocess.run([sys.executable, os.path.join(LIB, "relay.py"), "", *words], cwd=self.repo,
                              env=self.env, capture_output=True, text=True, timeout=60, check=False)

    def test_the_branch_checked_out_moves_with_its_files(self):
        r = self.relay("version", "release", "--dev")
        self.assertEqual(r.returncode, 0, r.stderr)
        self.assertEqual(self.git("rev-parse", "HEAD"), self.b)
        self.assertEqual(self.git("rev-parse", "refs/remotes/origin/topic"), self.b, "the other refs as before")
        self.assertEqual(self.git("status", "--porcelain"), "", "the index and the files moved with it")
        with open(os.path.join(self.repo, "CHANGELOG.md")) as f:
            self.assertEqual(f.read(), "## 1.0.0-dev.2\n")

    def test_a_change_in_the_way_leaves_the_branch_and_says_so(self):
        with open(os.path.join(self.repo, "CHANGELOG.md"), "w") as f:
            f.write("## Unreleased\n- mine\n")
        r = self.relay("version", "release", "--dev")
        self.assertNotEqual(r.returncode, 0)
        self.assertIn("could not follow it by a fast-forward", r.stderr)
        self.assertEqual(self.git("rev-parse", "HEAD"), self.a, "never moved under a change")


if __name__ == "__main__":
    unittest.main()
