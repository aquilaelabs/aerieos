"""A bug closed on a node waits for the node's commits to reach the
controller (scripts/lib/relay.py): `aerie bug fix` records the commit that
fixed it, read off the controller's copy, and a commit made a moment before
had not reached it, so the close was refused as naming no such commit. A
note on a bug reads no tree and is sent at once."""
import json
import os
import shutil
import subprocess
import sys
import tempfile
import threading
import time
import unittest
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer

LIB = os.path.join(os.path.dirname(__file__), "..", "..", "lib")


class Controller(BaseHTTPRequestHandler):
    seen = []

    def do_POST(self):
        n = int(self.headers.get("Content-Length") or 0)
        Controller.seen.append((time.time(), json.loads(self.rfile.read(n) or b"{}").get("argv")))
        data = json.dumps({"code": 0, "out": "ok\n", "err": ""}).encode()
        self.send_response(200)
        self.send_header("Content-Type", "application/json")
        self.send_header("Content-Length", str(len(data)))
        self.end_headers()
        self.wfile.write(data)

    def log_message(self, format, *args):     # noqa: A002 (the base class's name)
        pass


class RelayBugWaits(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.mkdtemp()
        self.addCleanup(shutil.rmtree, self.tmp, True)
        self.repo = os.path.join(self.tmp, "alpha")
        subprocess.run(["git", "init", "-q", self.repo], check=True)
        self.state = os.path.join(self.repo, ".git", ".bbsync-state")
        self.srv = ThreadingHTTPServer(("127.0.0.1", 0), Controller)
        threading.Thread(target=self.srv.serve_forever, daemon=True).start()
        self.addCleanup(self.srv.server_close)
        self.addCleanup(self.srv.shutdown)
        Controller.seen = []
        self.env = {**os.environ, "BB_CONTROLLER": f"http://127.0.0.1:{self.srv.server_port}",
                    "BB_AUTH_HEADER": "Bearer x", "BB_RELAY_PROJECT": "alpha", "HOME": self.tmp,
                    "WORKSPACE": self.tmp}
        self.env.pop("BB_CONTROLLER_PIN", None)

    def sync(self, pending, started):
        with open(self.state, "w") as f:
            json.dump({"rev": 1, "pending": pending, "started": started}, f)

    def relay(self, *words):
        return subprocess.run([sys.executable, os.path.join(LIB, "relay.py"), "", *words], cwd=self.repo,
                              env=self.env, capture_output=True, text=True, timeout=90, check=False)

    def caught_up_after(self, seconds):
        def later():
            time.sleep(seconds)
            self.sync(0, time.time())
        t = threading.Thread(target=later, daemon=True)
        t.start()
        return time.time() + seconds

    def test_a_fix_is_sent_once_the_commit_has_gone_up(self):
        for words in (("bug", "fix", "B7", "it lands", "--commit", "abc1234"), ("bug", "fixed-in", "B7", "abc1234")):
            Controller.seen = []
            self.sync(1, 0)
            ready = self.caught_up_after(0.8)
            r = self.relay(*words)
            self.assertEqual(r.returncode, 0, r.stderr)
            self.assertEqual([a for _, a in Controller.seen], [list(words)])
            self.assertGreaterEqual(Controller.seen[0][0], ready, f"{words[1]} waited for the copy to be in step")

    def test_a_note_is_sent_at_once(self):
        self.sync(1, 0)
        asked = time.time()
        r = self.relay("bug", "note", "B7", "seen again")
        self.assertEqual(r.returncode, 0, r.stderr)
        self.assertLess(Controller.seen[0][0] - asked, 5, "nothing to wait for")


if __name__ == "__main__":
    unittest.main()
