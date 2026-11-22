"""aerie devapp rebuild when the rebuilt container stops as it starts (B804):
a controller refusing its state exits at once, and the verb read it running
in that moment and said 'is up' with exit 0. It looks again a few seconds
on, and one that has stopped by then is said and fails."""
import http.server
import json
import os
import subprocess
import sys
import threading
import unittest

HERE = os.path.dirname(__file__)
VERBS = os.path.join(HERE, "..", "..", "lib", "devapp-verbs.py")


class Fake(http.server.BaseHTTPRequestHandler):
    """The controller: the rebuild is queued and succeeds; the instance's
    state reads running on the first look after it and, when `stops`, not
    running on every look after that."""
    built = "old"
    looks = 0
    stops = True

    def log_message(self, format, *args):  # noqa: A002 (the base class's name)
        del format, args

    def _send(self, d):
        b = json.dumps(d).encode()
        self.send_response(200)
        self.send_header("Content-Type", "application/json")
        self.send_header("Content-Length", str(len(b)))
        self.end_headers()
        self.wfile.write(b)

    def do_POST(self):  # noqa: N802 (the base class's name)
        b = json.loads(self.rfile.read(int(self.headers.get("Content-Length") or 0)))
        if b.get("action") == "state":
            running = True
            if Fake.built == "new":
                Fake.looks += 1
                running = not (Fake.stops and Fake.looks > 1)
            self._send({"state": {"name": "site", "built_rev": Fake.built, "running": running, "job": {}}})
            return
        Fake.built = "new"
        self._send({"ok": True, "job": "j_1", "started": True})

    def do_GET(self):  # noqa: N802 (the base class's name)
        self._send({"id": "j_1", "state": "succeeded"})


class RebuiltAndStopped(unittest.TestCase):
    def setUp(self):
        Fake.built, Fake.looks = "old", 0
        self.srv = http.server.ThreadingHTTPServer(("127.0.0.1", 0), Fake)
        threading.Thread(target=self.srv.serve_forever, daemon=True).start()

    def tearDown(self):
        self.srv.shutdown()
        self.srv.server_close()

    def run_rebuild(self):
        env = dict(os.environ, BB_CONTROLLER=f"http://127.0.0.1:{self.srv.server_address[1]}",
                   BB_PROJECT="web", BB_AUTH_HEADER="Bearer x", BB_DEV_CONTAINER="site",
                   BB_CONTROLLER_WAIT="0", PYTHONPATH=os.path.join(HERE, "..", "..", "lib"))
        return subprocess.run([sys.executable, VERBS, "rebuild"], env=env, capture_output=True,
                              text=True, timeout=90, check=False)

    def test_a_container_that_stops_as_it_starts_is_not_called_up(self):
        Fake.stops = True
        r = self.run_rebuild()
        self.assertNotEqual(r.returncode, 0, r.stdout)
        self.assertIn("started and stopped within seconds", r.stdout)
        self.assertNotIn("is up", r.stdout)
        self.assertIn("aerie devapp log", r.stderr)

    def test_one_that_stays_running_is_up(self):
        Fake.stops = False
        r = self.run_rebuild()
        self.assertEqual(r.returncode, 0, r.stderr)
        self.assertIn("is up", r.stdout)
        self.assertGreaterEqual(Fake.looks, 3)


if __name__ == "__main__":
    unittest.main()
