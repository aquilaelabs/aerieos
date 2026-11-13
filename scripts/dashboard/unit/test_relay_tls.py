"""The node's relay port over TLS, and a request good once (R243; the audit
of 13 Nov): terminals, the file explorer's requests and a VM's screen
crossed the LAN as plain websockets, the opening request signed and good for
two minutes with nothing remembering which had been used. The TLS layer on
real sockets, the relay's own listener taking it (and a plain request
still), the controller's side refusing any certificate but the one the node
reported, and a request refused the second time."""
import hashlib
import hmac
import os
import shutil
import socket
import sys
import tempfile
import threading
import time
import unittest
import urllib.parse
from unittest import mock

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, os.path.join(HERE, ".."))
sys.path.insert(0, os.path.join(HERE, "..", "..", "agent"))
from aerieos_agent import files, relaytls, screen, term  # noqa: E402
import fileexplorer  # noqa: E402
import termws  # noqa: E402

KEY = screen.screen_key("bbn_secret")
HAVE_OPENSSL = shutil.which("openssl") is not None


def answer(c, until=b""):
    """What the relay said to one request: its first line and body, to the
    end, or as far as `until` where the far end is slow to close."""
    c.settimeout(10)
    buf = b""
    try:
        while not (until and until in buf):
            got = c.recv(65536)
            if not got:
                break
            buf += got
    except OSError:
        pass
    c.close()
    return buf.decode("latin-1")


@unittest.skipUnless(HAVE_OPENSSL, "openssl makes the node's certificate")
class Relay(unittest.TestCase):
    """The relay's own listener code (ScreenRelay._one) on a real socket."""

    @classmethod
    def setUpClass(cls):
        cls.d = tempfile.mkdtemp()
        cls.crt, cls.key, cls.pin = relaytls.cert(cls.d)
        cls.ctx = relaytls.server_context(cls.crt, cls.key)
        cls.srv = socket.socket()
        cls.srv.bind(("127.0.0.1", 0))
        cls.srv.listen(16)
        cls.port = cls.srv.getsockname()[1]
        cls.took = []

        def serve():
            while True:
                try:
                    conn, _ = cls.srv.accept()
                except OSError:
                    return
                threading.Thread(target=screen.ScreenRelay._one, args=(conn, [KEY], lambda: {}, cls.ctx), daemon=True).start()
        threading.Thread(target=serve, daemon=True).start()

    @classmethod
    def tearDownClass(cls):
        cls.srv.close()
        shutil.rmtree(cls.d, True)

    def term_request(self, nonce="", when=None, key=KEY):
        blob = term.pack({"kind": "rw", "argv": ["sh"], "cols": 80, "rows": 24})
        when = int(time.time()) if when is None else when
        q = {"a": blob, "t": when, "s": term.sign(key, relaytls.subject(blob, nonce), when), **({"n": nonce} if nonce else {})}
        return (f"GET /term?{urllib.parse.urlencode(q)} HTTP/1.1\r\nHost: node\r\nUpgrade: websocket\r\n"
                "Connection: Upgrade\r\nSec-WebSocket-Key: abc\r\nSec-WebSocket-Version: 13\r\n\r\n").encode()

    def ask(self, request, pin=None):
        c = relaytls.connect("127.0.0.1", self.port, self.pin if pin is None else pin, timeout=10)
        c.sendall(request)
        return answer(c)

    def test_the_certificate_is_made_once_and_is_the_nodes_alone(self):
        self.assertTrue(self.pin.startswith("sha256:") and len(self.pin) == 71)
        self.assertEqual(os.stat(self.key).st_mode & 0o777, 0o600)
        self.assertEqual(relaytls.cert(self.d), (self.crt, self.key, self.pin), "a second start reads the one it has")
        self.assertEqual(relaytls.fingerprint(os.path.join(self.d, "nothing.crt")), "")
        with mock.patch.object(relaytls.subprocess, "run", side_effect=OSError("no openssl")):
            self.assertEqual(relaytls.cert(os.path.join(self.d, "elsewhere")), ("", "", ""), "no openssl: no certificate, and the relay stays plain")

    def test_a_signed_request_is_served_over_tls_and_once(self):
        # Signed, with a value of its own: past the checks (no terminal programs here, so it says that).
        req = self.term_request(nonce="aa11")
        self.assertIn("this node's terminals are not up", self.ask(req))
        # The very same request again, as somebody who read it off the wire would send it.
        said = self.ask(req)
        self.assertIn("403", said.split("\r\n")[0])
        self.assertIn("this request was used already", said)
        # Another request is its own.
        self.assertIn("this node's terminals are not up", self.ask(self.term_request(nonce="bb22")))
        # Not signed by the node's controller: no, whatever value it carries.
        self.assertIn("not signed by this node's controller", self.ask(self.term_request(nonce="cc33", key=screen.screen_key("another"))))
        # The value is part of what is signed: taking it off, or changing it, is no signature.
        blob = term.pack({"kind": "rw", "argv": ["sh"], "cols": 80, "rows": 24})
        when = int(time.time())
        forged = urllib.parse.urlencode({"a": blob, "t": when, "s": term.sign(KEY, relaytls.subject(blob, "dd44"), when), "n": "ee55"})
        self.assertIn("not signed", self.ask(f"GET /term?{forged} HTTP/1.1\r\nHost: node\r\n\r\n".encode()))

    def test_a_controller_from_before_is_still_served_plain_and_unvalued(self):
        # Put back to an older build, the controller speaks neither: its terminals still open.
        req = self.term_request()
        self.assertIn("this node's terminals are not up", self.ask(req, pin=""))
        self.assertIn("this node's terminals are not up", self.ask(req, pin=""), "with no value there is nothing to remember, as before")

    def test_the_controller_takes_the_reported_certificate_and_no_other(self):
        with self.assertRaises(relaytls.Refused) as e:
            relaytls.connect("127.0.0.1", self.port, "sha256:" + "0" * 64, timeout=10)
        self.assertIn("another certificate than the one the node reported", str(e.exception))
        # A node that said it has one, and whoever answers does not speak TLS: the TLS was taken off on the way.
        dumb = socket.socket()
        dumb.bind(("127.0.0.1", 0))
        dumb.listen(1)
        self.addCleanup(dumb.close)

        def plain():
            c, _ = dumb.accept()
            c.recv(100)
            c.sendall(b"HTTP/1.1 400 no\r\n\r\n")
            c.close()
        threading.Thread(target=plain, daemon=True).start()
        with self.assertRaises(relaytls.Refused) as e:
            relaytls.connect("127.0.0.1", dumb.getsockname()[1], self.pin, timeout=10)
        self.assertIn("did not take TLS", str(e.exception))

    def test_nothing_readable_crosses_the_wire(self):
        wire = bytearray()
        tap = socket.socket()
        tap.bind(("127.0.0.1", 0))
        tap.listen(1)
        self.addCleanup(tap.close)

        def between():
            c, _ = tap.accept()
            u = socket.create_connection(("127.0.0.1", self.port))

            def carry(a, b):
                while True:
                    try:
                        got = a.recv(65536)
                    except OSError:
                        break
                    if not got:
                        break
                    wire.extend(got)
                    try:
                        b.sendall(got)
                    except OSError:
                        break
                for s in (a, b):
                    try:
                        s.close()
                    except OSError:
                        pass
            threading.Thread(target=carry, args=(c, u), daemon=True).start()
            carry(u, c)
        threading.Thread(target=between, daemon=True).start()
        c = relaytls.connect("127.0.0.1", tap.getsockname()[1], self.pin, timeout=10)
        c.sendall(self.term_request(nonce="ff66"))
        said = answer(c, until=b"terminals are not up")
        self.assertIn("this node's terminals are not up", said)
        time.sleep(0.2)
        self.assertGreater(len(wire), 500)
        for words in (b"GET /term", b"terminals are not up", b"Sec-WebSocket"):
            self.assertNotIn(words, bytes(wire))

    def test_a_long_stream_both_ways_arrives_whole(self):
        # The pump itself: a megabyte each way through TLS, against an echo behind the same accept.
        echo = socket.socket()
        echo.bind(("127.0.0.1", 0))
        echo.listen(1)
        self.addCleanup(echo.close)

        def serve():
            conn, _ = echo.accept()
            c = relaytls.accept(conn, self.ctx)
            while True:
                got = c.recv(65536)
                if not got:
                    break
                c.sendall(got[::-1])
            c.close()
        threading.Thread(target=serve, daemon=True).start()
        c = relaytls.connect("127.0.0.1", echo.getsockname()[1], self.pin, timeout=10)
        chunk = os.urandom(4096)
        got = bytearray()
        threading.Thread(target=lambda: [c.sendall(chunk) for _ in range(256)], daemon=True).start()
        c.settimeout(30)
        while len(got) < 4096 * 256:
            part = c.recv(65536)
            if not part:
                break
            got += part
        c.close()
        self.assertEqual(len(got), 4096 * 256)
        self.assertEqual(bytes(got[:4096]), chunk[::-1])


class Once(unittest.TestCase):
    def test_a_signature_is_good_once_and_forgotten_after_its_time(self):
        with mock.patch.dict(relaytls._USED, {}, clear=True):
            self.assertTrue(relaytls.once("sig-a", now=1000))
            self.assertFalse(relaytls.once("sig-a", now=1001))
            self.assertTrue(relaytls.once("sig-b", now=1001))
            self.assertTrue(relaytls.once("sig-a", now=1000 + 601), "past any time it could be good for")
        self.assertEqual(relaytls.subject("blob", "abc"), "blob.abc")
        self.assertEqual(relaytls.subject("blob", ""), "blob", "a request with no value is signed as it always was")


class Controller(unittest.TestCase):
    """The controller's callers: what they sign, and what they are told of a node."""

    def test_the_file_explorers_request_is_signed_with_a_value_where_the_node_takes_one_once(self):
        was = fileexplorer.subject_fn
        self.addCleanup(lambda: setattr(fileexplorer, "subject_fn", was))
        fileexplorer.subject_fn = relaytls.subject
        line = fileexplorer._request_line(KEY, {"op": "list", "root": "/mnt/a", "path": ""}, once=True)
        q = urllib.parse.parse_qs(urllib.parse.urlsplit(line).query)
        blob, nonce, sig, when = q["a"][0], q["n"][0], q["s"][0], q["t"][0]
        self.assertEqual(len(nonce), 24)
        self.assertTrue(files.signed(KEY, relaytls.subject(blob, nonce), when, sig), "the node's own check takes it")
        self.assertFalse(files.signed(KEY, blob, when, sig), "and not with the value left off")
        self.assertNotEqual(fileexplorer._request_line(KEY, {"op": "list", "root": "/mnt/a", "path": ""}, once=True), line,
                            "two of the same request in one second are two signatures")
        # A node from before: signed as it always was.
        old = fileexplorer._request_line(KEY, {"op": "list", "root": "/mnt/a", "path": ""})
        q = urllib.parse.parse_qs(urllib.parse.urlsplit(old).query)
        self.assertNotIn("n", q)
        self.assertEqual(q["s"][0], hmac.new(KEY.encode(), f"files.{q['a'][0]}.{q['t'][0]}".encode(), hashlib.sha256).hexdigest())

    def test_what_the_controller_is_told_of_a_nodes_relay(self):
        import nodes
        reported = {"n_new": {"reported": {"relay": {"tls": "sha256:" + "a" * 64, "once": True}}},
                    "n_no_openssl": {"reported": {"relay": {"tls": "", "once": True}}},
                    "n_before": {"reported": {"session": {"screen": 7684}}}}
        with mock.patch.object(nodes, "node", lambda nid: reported.get(nid)):
            self.assertEqual(nodes.relay_of("n_new"), {"pin": "sha256:" + "a" * 64, "once": True})
            self.assertEqual(nodes.relay_of("n_no_openssl"), {"pin": "", "once": True})
            self.assertEqual(nodes.relay_of("n_before"), {"pin": "", "once": False}, "an agent from before: plain and unvalued, as it was")
            self.assertEqual(nodes.relay_of("n_gone"), {"pin": "", "once": False})

    def test_a_nodes_report_of_its_relay_is_kept_by_the_controller(self):
        # A report is kept key by key (nodes._census): the relay's was not
        # named there, so the certificate never reached the controller and
        # every terminal went over the plain way, which the walk on the dev
        # pair showed where the test above, which hands relay_of a node,
        # could not.
        import nodes
        pin = "sha256:" + "a" * 64
        self.assertEqual(nodes._census({"relay": {"tls": pin, "once": True}}).get("relay"), {"tls": pin, "once": True})
        self.assertEqual(nodes._census({"relay": {"tls": "", "once": True}}).get("relay"), {"tls": "", "once": True})
        # What is not a certificate's sha256 is no pin; what is not True is not once.
        self.assertEqual(nodes._census({"relay": {"tls": "sha256:zz", "once": "yes"}}).get("relay"), {"tls": "", "once": False})
        self.assertEqual(nodes._census({"relay": {"tls": pin + "; rm -rf /"}}).get("relay"), {"tls": "", "once": False})
        self.assertNotIn("relay", nodes._census({"relay": "tls"}))
        self.assertNotIn("relay", nodes._census({}), "an agent from before says nothing, and is spoken to as before")
        # ...and through to what the callers ask.
        kept = {"reported": nodes._census({"relay": {"tls": pin, "once": True}})}
        with mock.patch.object(nodes, "node", lambda nid: kept):
            self.assertEqual(nodes.relay_of("n1"), {"pin": pin, "once": True})

    def test_the_controller_loads_the_agents_own_tls(self):
        was = termws.AGENT_DIR
        self.addCleanup(lambda: (setattr(termws, "AGENT_DIR", was), termws._term.pop("tls", None)))
        termws._term.pop("tls", None)
        termws.AGENT_DIR = os.path.join(HERE, "..", "..", "agent")
        rt = termws.relaytls()
        self.assertTrue(callable(rt.connect) and callable(rt.subject) and issubclass(rt.Refused, OSError))
        self.assertIs(termws.relaytls(), rt, "loaded once")


if __name__ == "__main__":
    unittest.main()
