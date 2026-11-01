"""http://THE-MACHINE/ finds the dashboard (R202): a redirect on port 80 on a
controller's own machine that lets go for nginx and for a compose job; nginx
itself never points a request at the dashboard."""
import os
import socket
import sys
import threading
import time
import unittest
from unittest import mock

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))
import agentpkg  # noqa: E402
import nginxproxy as npx  # noqa: E402

agent = agentpkg.load("builderbot_agent_http80")
h = sys.modules[agent.Agent.__module__.rsplit(".", 1)[0] + ".http80"]


class Answer(unittest.TestCase):
    def loc(self, head, **kw):
        out = h.answer(head, 7680, **kw).decode()
        self.assertTrue(out.startswith("HTTP/1.1 302 Found\r\n"))
        return [ln for ln in out.split("\r\n") if ln.startswith("Location: ")][0][10:]

    def test_it_sends_the_browser_to_the_dashboard_on_the_name_it_used(self):
        self.assertEqual(self.loc(b"GET /a?b=1 HTTP/1.1\r\nHost: tower.lan\r\n\r\n"), "http://tower.lan:7680/a?b=1")
        self.assertEqual(self.loc(b"GET / HTTP/1.1\r\nHost: 192.168.1.15:80\r\n\r\n"), "http://192.168.1.15:7680/")
        self.assertEqual(self.loc(b"GET / HTTP/1.1\r\nHost: [fe80::1]:80\r\n\r\n", scheme="https"), "https://[fe80::1]:7680/")

    def test_what_it_reads_goes_nowhere_but_that_line(self):
        for head in (b"GET / HTTP/1.1\r\nHost: evil\r\nX: y\r\n\r\n", b"GET /x\rSet-Cookie:a HTTP/1.1\r\nHost: a b\r\n\r\n", b"", b"\xff\xfe"):
            self.assertNotIn(b"Set-Cookie", h.answer(head, 7680))
        self.assertEqual(self.loc(b"GET / HTTP/1.1\r\nHost: a b<script>\r\n\r\n", here="tower"), "http://tower:7680/")
        self.assertEqual(self.loc(b"GET //x y HTTP/1.1\r\n\r\n", here="tower"), "http://tower:7680/")


class TheLoop(unittest.TestCase):
    def free_port(self):
        with socket.socket() as s:
            s.bind(("127.0.0.1", 0))
            return s.getsockname()[1]

    def held(self, port):
        with socket.socket() as s:
            s.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
            try:
                s.bind(("0.0.0.0", port))
                return False
            except OSError:
                return True

    def until(self, what, want):
        for _ in range(60):
            if what() == want:
                return True
            time.sleep(0.1)
        return False

    def test_it_takes_the_port_and_lets_go_for_a_compose_job_and_for_nginx(self):
        port = self.free_port()
        nginx = [False]
        with mock.patch.object(h, "docker_look", lambda: (False, nginx[0])), mock.patch.object(h, "CHECK_S", 0.1), \
                mock.patch.object(h, "scheme_of", lambda p: "http"):
            threading.Thread(target=h._loop, args=(port,), daemon=True).start()
            self.assertTrue(self.until(lambda: self.held(port), True), "it takes a free port")
            with socket.create_connection(("127.0.0.1", port), timeout=3) as c:
                c.sendall(b"GET / HTTP/1.1\r\nHost: tower\r\n\r\n")
                self.assertIn(b":7680/", c.recv(1000))
            with h.paused():
                self.assertTrue(self.until(lambda: self.held(port), False), "it lets go for a compose job")
            self.assertTrue(self.until(lambda: self.held(port), True), "and takes it back when free")
            nginx[0] = True
            self.assertTrue(self.until(lambda: self.held(port), False), "it lets go for nginx")
            nginx[0] = False
            self.assertTrue(self.until(lambda: self.held(port), True))
            nginx[0] = True

    def test_it_runs_on_a_controllers_own_machine_alone(self):
        with mock.patch.dict(os.environ, {"BB_OWN_NODE_MARK": "/nonexistent/own-node"}):
            self.assertFalse(h.start())


class Nginx(unittest.TestCase):
    def test_nginx_never_points_a_stranger_at_the_dashboard(self):
        # The operator, 1 Nov: a name nothing routes is closed, on every
        # machine, the controller's own too.
        routes = npx.clean_routes([{"host": "a.example", "path": "/", "port": 8080}])
        conf = npx.nginx_conf(routes, {})
        self.assertIn("listen 80 default_server; server_name _; return 444;", conf)
        self.assertNotIn("302", conf)


if __name__ == "__main__":
    unittest.main()
