"""A node that holds its controller to a key follows a move under a key.

With a move armed, three failed hellos made a key-pinned node knock at the
move's address with no pin at all: its token, and on a refusal every token
it held before, went to whoever answered there, and the answer's address
and pin were written as they came, plain http and the CA word among them.
Now the hello that arms a move names the new home's key (the controller's
own, which goes there with its state), the node knocks under it, or under
the key it holds where none was named, and from the answer it takes only
an https address of the one shape and a key's pin. A node on plain http
knocks as it did.

Real sockets on loopback, served by the dashboard's own tls.py."""
import json
import os
import ssl
import sys
import threading
from http.server import BaseHTTPRequestHandler
from unittest import mock

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)
sys.path.insert(0, os.path.join(HERE, ".."))
import nodes  # noqa: E402
import test_agent_key_pin as kp  # noqa: E402
import tls  # noqa: E402

EXPECT = "c" * 64
TOKEN, OLD_TOKEN = "bbn_this-nodes-token", "bbn_the-one-before"


class Home(BaseHTTPRequestHandler):
    """A controller's new home: it knows the node by `server.knows`, answers
    a knock with `server.answer`, and keeps every token it was shown."""
    protocol_version = "HTTP/1.0"

    def say(self, status, body):
        raw = json.dumps(body).encode()
        self.send_response(status)
        self.send_header("Content-Length", str(len(raw)))
        self.end_headers()
        self.wfile.write(raw)

    def do_POST(self):
        body = json.loads(self.rfile.read(int(self.headers.get("Content-Length") or 0)) or b"{}")
        over_tls = isinstance(self.connection, ssl.SSLSocket)
        shown = self.headers.get("Authorization", "")[len("Bearer "):]
        self.server.shown.append((self.path.rsplit("/", 1)[-1], over_tls, shown, body.get("tokens")))
        if self.path.endswith("/recover"):
            if self.server.knows in (body.get("tokens") or []):
                self.server.knows = "bbn_fresh"
                return self.say(200, {"ok": True, "token": "bbn_fresh"})
            return self.say(401, {"error": "unknown token"})
        if shown != self.server.knows:
            return self.say(401, {"error": "unknown token"})
        return self.say(200, self.server.answer)

    def log_message(self, format, *args):
        del format, args


class Case(kp.Case):
    def setUp(self):
        super().setUp()
        self.mod = sys.modules[self.agent.Agent.__module__]
        self.saved = []
        self.mod.save_state = lambda st: self.saved.append(dict(st))

    def home(self, kind=kp.Both, knows=TOKEN, **answer):
        srv = kind(("127.0.0.1", 0), Home)
        srv.shown, srv.knows, srv.answer = [], knows, {"answer": EXPECT, "url": "", "pin": "", **answer}
        threading.Thread(target=srv.serve_forever, daemon=True).start()
        self.addCleanup(srv.shutdown)
        self.addCleanup(srv.server_close)
        return srv

    def state(self, to, held, **move):
        return {"controller": "https://127.0.0.1:1", "token": TOKEN, "pin": held, "node_id": "n_1",
                "past_tokens": [[OLD_TOKEN, 1]], "move": {"url": to, "expect": EXPECT, **move}}

    def an_impostor(self):
        """Somebody else at the move's address: another key, and every word of the right answer."""
        other = tls.self_signed(["127.0.0.1"])
        was = tls._ctx
        ctx = ssl.SSLContext(ssl.PROTOCOL_TLS_SERVER)
        cert, key = os.path.join(self.tmp, "imp-cert.pem"), os.path.join(self.tmp, "imp-key.pem")
        with open(cert, "w") as f:
            f.write(other[0])
        with open(key, "w") as f:
            f.write(other[1])
        ctx.load_cert_chain(cert, key)
        srv = self.home()
        tls._ctx = ctx
        self.addCleanup(lambda: setattr(tls, "_ctx", was))
        return srv, was


class Knock(Case):
    def test_a_key_pinned_node_knocks_under_the_key_it_holds_and_keeps_it(self):
        srv = self.home()
        st = self.state(f"https://127.0.0.1:{srv.server_port}", self.pin)
        self.assertEqual(self.mod.follow(st), (True, ""))
        self.assertEqual((st["controller"], st["pin"]), (f"https://127.0.0.1:{srv.server_port}", self.pin))
        self.assertNotIn("move", st)
        self.assertEqual(srv.shown, [("moved", True, TOKEN, None)])

    def test_an_address_named_as_http_is_asked_over_tls_on_the_same_port(self):
        srv = self.home()
        st = self.state(f"http://127.0.0.1:{srv.server_port}", self.pin)
        self.assertEqual(self.mod.follow(st), (True, ""))
        self.assertEqual((st["controller"], st["pin"]), (f"https://127.0.0.1:{srv.server_port}", self.pin))
        self.assertEqual(srv.shown, [("moved", True, TOKEN, None)], "never over plain http")

    def test_somebody_else_at_the_address_is_shown_no_token(self):
        srv, _ = self.an_impostor()
        st = self.state(f"https://127.0.0.1:{srv.server_port}", self.pin)
        ok, why = self.mod.follow(st)
        self.assertFalse(ok)
        self.assertIn("did not answer under the pin this node knocks with", why)
        self.assertEqual(srv.shown, [], "not its token, and none of the ones before")
        self.assertEqual((st["pin"], st["controller"]), (self.pin, "https://127.0.0.1:1"))
        self.assertIn("move", st, "it knocks again next time")
        self.assertEqual(self.saved, [])

    def test_a_new_home_that_speaks_only_http_is_shown_no_token(self):
        srv = self.home(kp.PlainOnly)
        st = self.state(f"http://127.0.0.1:{srv.server_port}", self.pin)
        self.assertFalse(self.mod.follow(st)[0])
        self.assertEqual(srv.shown, [])

    def test_the_key_the_arming_hello_named_is_the_one_knocked_under(self):
        # The move names the key of the home it goes to: a node that held
        # another key (or a certificate, from before keys were pinned)
        # knocks under the named one and holds it from there on.
        srv = self.home()
        for held in (self.another_key(), "sha256:" + "ab" * 32):
            st = self.state(f"https://127.0.0.1:{srv.server_port}", held, pin=self.pin)
            self.assertEqual(self.mod.follow(st), (True, ""), held)
            self.assertEqual(st["pin"], self.pin)
        # ...and one named a key that is not the home's stays where it is.
        srv.shown.clear()
        st = self.state(f"https://127.0.0.1:{srv.server_port}", self.pin, pin=self.another_key())
        self.assertFalse(self.mod.follow(st)[0])
        self.assertEqual(srv.shown, [])
        # What is not a key's pin is no name for one: the held key is knocked under.
        for junk in ("ca", "sha256:" + "ab" * 32, "", 7, "sha256//short="):
            st = self.state(f"https://127.0.0.1:{srv.server_port}", self.pin, pin=junk)
            self.assertEqual(self.mod.follow(st), (True, ""), junk)
            self.assertEqual(st["pin"], self.pin)

    def test_the_answer_writes_no_http_and_no_other_kind_of_pin(self):
        for answer, kept in (({"url": "http://evil.example", "pin": "ca"}, None),
                             ({"url": "http://127.0.0.1:9", "pin": ""}, None),
                             ({"url": "https://h.example/path", "pin": "sha256:" + "cd" * 32}, None),
                             ({"url": "https://h.example;id", "pin": ""}, None),
                             ({"url": "https://new.example:8443/", "pin": ""}, "https://new.example:8443")):
            srv = self.home(**answer)
            to = f"https://127.0.0.1:{srv.server_port}"
            st = self.state(to, self.pin)
            self.assertEqual(self.mod.follow(st), (True, ""), answer)
            self.assertEqual(st["controller"], kept or to, answer)
            self.assertEqual(st["pin"], self.pin, answer)
        # A key's pin the new home names for itself, over the pinned channel, is taken.
        other = self.another_key()
        srv = self.home(pin=other)
        st = self.state(f"https://127.0.0.1:{srv.server_port}", self.pin)
        self.assertEqual(self.mod.follow(st), (True, ""))
        self.assertEqual(st["pin"], other)

    def test_the_tokens_from_before_go_only_to_the_pinned_home(self):
        srv = self.home(knows=OLD_TOKEN)
        st = self.state(f"https://127.0.0.1:{srv.server_port}", self.pin)
        self.assertEqual(self.mod.follow(st), (True, ""))
        self.assertEqual([(s[0], s[1]) for s in srv.shown], [("moved", True), ("recover", True), ("moved", True)])
        self.assertEqual(st["token"], "bbn_fresh")

    def test_a_node_reached_through_a_public_hostname_stays_under_the_authorities(self):
        calls = []

        class Ctl:
            def __init__(self, u, token, p=""):
                calls.append((u, p))

            def call(self, verb, body=None, timeout=30, **kw):
                return 200, {"answer": EXPECT, "url": "https://aerie.example.org", "pin": "sha256:" + "ab" * 32}
        with mock.patch.object(self.mod, "Controller", Ctl):
            st = self.state("https://aerie.example.org", "ca")
            self.assertEqual(self.mod.follow(st), (True, ""))
            self.assertEqual(calls, [("https://aerie.example.org", "ca")])
            self.assertEqual((st["controller"], st["pin"]), ("https://aerie.example.org", "ca"))
            st = self.state("http://aerie.example.org", "ca")
            self.assertFalse(self.mod.follow(st)[0], "and never over plain http")

    def test_a_node_on_plain_http_knocks_as_it_did(self):
        srv = self.home(kp.PlainOnly)
        to = f"http://127.0.0.1:{srv.server_port}"
        st = self.state(to, "")
        st["controller"] = "http://127.0.0.1:1"
        self.assertEqual(self.mod.follow(st), (True, ""))
        self.assertEqual(st["controller"], to)
        self.assertNotIn("pin", st)
        self.assertEqual(srv.shown, [("moved", False, TOKEN, None)])

    def test_the_verb_at_the_console_knocks_under_the_held_key_or_the_one_it_is_handed(self):
        srv = self.home()
        to = f"https://127.0.0.1:{srv.server_port}"
        st = {"controller": "https://127.0.0.1:1", "token": TOKEN, "pin": self.another_key(), "node_id": "n_1"}
        self.assertFalse(self.mod.follow(dict(st), to, EXPECT)[0], "another key than the one held")
        got = dict(st)
        self.assertEqual(self.mod.follow(got, to, EXPECT, self.pin), (True, ""))
        self.assertEqual(got["pin"], self.pin)


class Armed(Case):
    def test_the_hello_that_arms_a_move_names_the_controller_s_key(self):
        """nodes.hello's `move`: the address and challenge as before, and
        the pin of this controller's own key where its port answers under
        one; an agent from before this reads past it."""
        with open(os.path.join(HERE, "..", "nodes.py"), encoding="utf-8") as f:
            text = f.read()
        self.assertIn('moving = {**moving, "pin": tls_pin()}', text)
        self.assertEqual(tls.key_pin(), self.pin)
        self.assertTrue(callable(nodes.tls_pin))

    def test_the_agent_keeps_the_named_key_with_the_move(self):
        a = object.__new__(self.agent.Agent)
        a.state = {"controller": "https://127.0.0.1:1", "token": TOKEN, "pin": self.pin}
        self.assertTrue(a.move_hint({"url": "https://new.example", "expect": EXPECT, "pin": self.pin}))
        self.assertEqual(a.state["move"], {"url": "https://new.example", "expect": EXPECT, "pin": self.pin})
        a.state.pop("move")
        self.assertTrue(a.move_hint({"url": "https://new.example", "expect": EXPECT, "pin": "ca"}))
        self.assertEqual(a.state["move"], {"url": "https://new.example", "expect": EXPECT})



if __name__ == "__main__":
    import unittest
    unittest.main()
