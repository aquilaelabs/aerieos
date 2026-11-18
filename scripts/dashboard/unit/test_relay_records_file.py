"""A records file named on a node reaches the controller (B962): `aerie bug
add --from FILE` and `aerie roadmap add --from FILE` were relayed with the
path alone, and the controller's copy of the tree holds nothing in dist/ or
/tmp, so the read said No such file for a file that was there. The node's
side reads it and sends it as the verb's stdin, the words saying --from -,
and the controller hands it to that verb and to no other."""
import json
import os
import shutil
import subprocess
import sys
import tempfile
import threading
import unittest
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from unittest import mock

sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)), ".."))
import bbrelay  # noqa: E402

LIB = os.path.join(os.path.dirname(__file__), "..", "..", "lib")


class Controller(BaseHTTPRequestHandler):
    seen = []

    def do_POST(self):
        n = int(self.headers.get("Content-Length") or 0)
        Controller.seen.append(json.loads(self.rfile.read(n) or b"{}"))
        data = json.dumps({"code": 0, "out": "filed B9\n", "err": ""}).encode()
        self.send_response(200)
        self.send_header("Content-Type", "application/json")
        self.send_header("Content-Length", str(len(data)))
        self.end_headers()
        self.wfile.write(data)

    def log_message(self, format, *args):     # noqa: A002 (the base class's name)
        pass


class NodeSide(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.mkdtemp()
        self.addCleanup(shutil.rmtree, self.tmp, True)
        self.srv = ThreadingHTTPServer(("127.0.0.1", 0), Controller)
        threading.Thread(target=self.srv.serve_forever, daemon=True).start()
        self.addCleanup(self.srv.server_close)
        self.addCleanup(self.srv.shutdown)
        Controller.seen = []
        self.env = {**os.environ, "BB_CONTROLLER": f"http://127.0.0.1:{self.srv.server_port}",
                    "BB_AUTH_HEADER": "Bearer x", "BB_RELAY_PROJECT": "alpha", "HOME": self.tmp,
                    "WORKSPACE": self.tmp}
        self.env.pop("BB_CONTROLLER_PIN", None)

    def relay(self, *words):
        return subprocess.run([sys.executable, os.path.join(LIB, "relay.py"), "", *words], cwd=self.tmp,
                              env=self.env, capture_output=True, text=True, timeout=60, check=False)

    def test_the_file_goes_as_stdin(self):
        f = Path(self.tmp) / "x.json"
        f.write_text('{"kind": "bugs", "records": [{"title": "One"}]}')
        for verb in ("bug", "roadmap"):
            Controller.seen = []
            r = self.relay(verb, "add", "--from", str(f))
            self.assertEqual(r.returncode, 0, r.stderr)
            self.assertEqual(Controller.seen[0]["argv"], [verb, "add", "--from", "-"])
            self.assertEqual(Controller.seen[0]["stdin"], f.read_text())

    def test_a_missing_file_is_said_here(self):
        r = self.relay("bug", "add", "--from", os.path.join(self.tmp, "nope.json"))
        self.assertNotEqual(r.returncode, 0)
        self.assertIn("No such file", r.stderr)
        self.assertEqual(Controller.seen, [], "nothing sent")

    def test_other_words_carry_no_stdin(self):
        self.relay("bug", "add", "a title", "--repro", "--from here")
        self.assertNotIn("stdin", Controller.seen[0])


class ControllerSide(unittest.TestCase):
    def ran(self, argv, stdin):
        seen = {}

        def fake(cmd, **kw):
            seen.update(kw)
            return subprocess.CompletedProcess(cmd, 0, "ok\n", "")
        users = mock.Mock(mint_session=lambda p: "t", seat_of=lambda me: "")
        with tempfile.TemporaryDirectory() as ws, mock.patch.object(bbrelay, "WORKSPACE", Path(ws)), \
                mock.patch.object(bbrelay, "users", users), mock.patch.object(bbrelay.subprocess, "run", fake):
            (Path(ws) / "alpha").mkdir()
            out, status = bbrelay.run({"session": False}, {"argv": argv, "stdin": stdin, "cwd": ""}, "alpha")
        return out, status, seen

    def test_stdin_reaches_a_from_dash_verb_and_no_other(self):
        _out, status, kw = self.ran(["bug", "add", "--from", "-"], "{}")
        self.assertEqual((status, kw.get("input")), (200, "{}"))
        _out, _status, kw = self.ran(["bug", "list"], "{}")
        self.assertNotIn("input", kw)
        self.assertEqual(kw.get("stdin"), subprocess.DEVNULL)


if __name__ == "__main__":
    unittest.main()
