"""A node's channel to its controller over TLS, under the controller's key
(R267 step 15).

The agent takes a pin of the controller's public key, in the form curl's
--pinnedpubkey takes (sha256// and the base64 of the sha256 of the key's
SubjectPublicKeyInfo): the right key is taken, another is refused, and a
remade certificate over the same key is taken. The certificate-digest form
is as it was: a remade certificate is another certificate. The same pin is
read by what a session dials with (scripts/lib/bbapi.py) and by root's
check before a terminal (nodes/bb-session), each with a copy of the few
lines that find the key in a certificate, held here to each other and to
the cryptography library.

A node enrolled over plain http moves by itself: its controller's hello
names the key's pin, the agent asks the same address over https under it,
and once that answers as its controller it keeps https and the pin in
node.json and nothing takes it back. Where it does not answer the node
stays as it is and its census says why. A node that pinned the certificate
moves its pin to the key when that certificate is over the key named. An
agent from before this is answered as it was.

Real sockets on loopback throughout, served by the dashboard's own tls.py."""
import base64
import datetime
import hashlib
import importlib.machinery
import importlib.util
import json
import os
import shutil
import ssl
import sys
import tempfile
import threading
import unittest
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from unittest import mock

HERE = os.path.dirname(os.path.abspath(__file__))
REPO = os.path.normpath(os.path.join(HERE, "..", "..", ".."))
sys.path.insert(0, HERE)
sys.path.insert(0, os.path.join(HERE, ".."))
sys.path.insert(0, os.path.join(REPO, "scripts", "lib"))
import agentpkg  # noqa: E402
import bbapi  # noqa: E402
import nodes  # noqa: E402
import signing  # noqa: E402
import tls  # noqa: E402

TOKEN = "bbn_this-nodes-token"


def by_library(der):
    """A key's pin by the cryptography library alone."""
    from cryptography import x509
    from cryptography.hazmat.primitives import serialization
    spki = x509.load_der_x509_certificate(der).public_key().public_bytes(
        serialization.Encoding.DER, serialization.PublicFormat.SubjectPublicKeyInfo)
    return "sha256//" + base64.b64encode(hashlib.sha256(spki).digest()).decode()


def der_of(pem):
    return ssl.PEM_cert_to_DER_cert(pem.split("-----END CERTIFICATE-----")[0] + "-----END CERTIFICATE-----\n")


def cert_with(key, names=("example.test",), serial=None):
    """A self-signed certificate over `key`, DER: for kinds of key tls.py does not make."""
    from cryptography import x509
    from cryptography.hazmat.primitives import hashes, serialization
    from cryptography.hazmat.primitives.asymmetric import ed25519
    from cryptography.x509.oid import NameOID
    now = datetime.datetime.now(datetime.timezone.utc)
    name = x509.Name([x509.NameAttribute(NameOID.COMMON_NAME, names[0])])
    b = (x509.CertificateBuilder().subject_name(name).issuer_name(name).public_key(key.public_key())
         .serial_number(serial or x509.random_serial_number()).not_valid_before(now)
         .not_valid_after(now + datetime.timedelta(days=30))
         .add_extension(x509.SubjectAlternativeName([x509.DNSName(n) for n in names]), critical=False))
    return b.sign(key, None if isinstance(key, ed25519.Ed25519PrivateKey) else hashes.SHA256()).public_bytes(serialization.Encoding.DER)


def bb_session():
    """nodes/bb-session as a module: it has no .py to import it by."""
    loader = importlib.machinery.SourceFileLoader("bb_session_under_test", os.path.join(REPO, "nodes", "bb-session"))
    spec = importlib.util.spec_from_loader(loader.name, loader)
    mod = importlib.util.module_from_spec(spec)
    loader.exec_module(mod)
    return mod


class Handler(BaseHTTPRequestHandler):
    """Enough of a controller: any GET, and a POST that knows this node's token."""
    protocol_version = "HTTP/1.0"

    def answer(self, status, body):
        raw = json.dumps(body).encode()
        self.send_response(status)
        self.send_header("Content-Length", str(len(raw)))
        self.end_headers()
        self.wfile.write(raw)

    def do_GET(self):
        self.answer(200, {"tls": isinstance(self.connection, ssl.SSLSocket)})

    def do_POST(self):
        self.rfile.read(int(self.headers.get("Content-Length") or 0))
        self.server.asked.append((self.path, isinstance(self.connection, ssl.SSLSocket)))
        if self.path.endswith("/enroll") and self.headers.get("Authorization", "").startswith("Bearer bbe_"):
            return self.answer(200, {"node_id": "n_0a1b2c3d", "token": TOKEN, "name": "box", "capabilities": []})
        if self.headers.get("Authorization") != "Bearer " + TOKEN:
            return self.answer(401, {"error": "unknown token"})
        return self.answer(200, {"ok": True, "tls": isinstance(self.connection, ssl.SSLSocket)})

    def log_message(self, format, *args):
        del format, args


class Both(tls.WrapOnItsThread, ThreadingHTTPServer):
    """The dashboard's listener: one port, a handshake wrapped, the rest plain."""
    daemon_threads = True

    def handle_error(self, request, client_address):
        del request, client_address          # a client that leaves mid-handshake is the test's own doing


class PlainOnly(ThreadingHTTPServer):
    """What a proxy that speaks only http is from a node's side: no handshake answered."""
    daemon_threads = True

    def handle_error(self, request, client_address):
        del request, client_address


class Case(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.mkdtemp()
        self.addCleanup(shutil.rmtree, self.tmp, True)
        self.was = signing.MASTER, signing.PREVIOUS
        signing.MASTER, signing.PREVIOUS = bytes(range(32)), None
        self.addCleanup(lambda: setattr(signing, "MASTER", self.was[0]) or setattr(signing, "PREVIOUS", self.was[1]))
        tls.RUN_DIR = self.tmp
        tls.configure(state=self.tmp, seal_fn=signing.seal, unseal_fn=signing.unseal,
                      sealing_fn=lambda: signing.MASTER is not None)
        tls._ctx, tls._pending, tls._mode = None, {}, "http"
        self.addCleanup(lambda: setattr(tls, "_ctx", None))
        self.pin = tls.apply({"tls_mode": "http"}.get, names=["127.0.0.1"])["pin"]
        self.agent = agentpkg.load("aerieos_agent_key_pin")
        self.said = []
        self.agent.log = lambda msg, *a, **k: self.said.append(msg)
        self.controller = self.agent.module("controller")

    def serve(self, kind=Both):
        srv = kind(("127.0.0.1", 0), Handler)
        srv.asked = []
        threading.Thread(target=srv.serve_forever, daemon=True).start()
        self.addCleanup(srv.shutdown)
        self.addCleanup(srv.server_close)
        return srv

    def remake(self):
        """The install's own certificate made again, as a month before its end."""
        was = tls.RENEW_BEFORE
        tls.RENEW_BEFORE = (tls.SELF_DAYS + 1) * 86400
        try:
            return tls.apply({"tls_mode": "http"}.get, names=["127.0.0.1"])
        finally:
            tls.RENEW_BEFORE = was

    def another_key(self):
        """The pin of a key that is not the controller's."""
        return tls.key_pin_of(tls.self_signed(["127.0.0.1"])[0])


class TheKeyInACertificate(Case):
    def test_the_three_copies_find_the_key_the_library_finds(self):
        from cryptography.hazmat.primitives.asymmetric import ec, ed25519, rsa
        session = bb_session()
        ders = [der_of(tls.certificate_pem()),
                cert_with(ec.generate_private_key(ec.SECP384R1())),
                cert_with(rsa.generate_private_key(public_exponent=65537, key_size=2048), names=("a.test", "b.test")),
                cert_with(rsa.generate_private_key(public_exponent=65537, key_size=4096)),
                cert_with(ed25519.Ed25519PrivateKey.generate(), serial=1)]
        for der in ders:
            want = by_library(der)
            self.assertRegex(want, r"^sha256//[A-Za-z0-9+/]{43}=$")
            self.assertEqual(self.controller.key_pin_of(der), want)
            self.assertEqual(bbapi.key_pin_of(der), want)
            self.assertEqual(session.key_pin_of(der), want)
        self.assertEqual(tls.key_pin_of(tls.certificate_pem()), by_library(ders[0]), "and the controller says the same of its own")
        # The three say they read a key's pin in the line the agent looks for.
        for path in (os.path.join(REPO, "scripts", "lib", "bbapi.py"), os.path.join(REPO, "nodes", "bb-session")):
            with open(path) as f:
                self.assertIn(f'KEY_PIN = "{self.controller.KEY_PIN}"', f.read(), path)

    def test_what_is_not_a_certificate_has_no_key(self):
        session = bb_session()
        good = der_of(tls.certificate_pem())
        for bad in (b"", b"\x30", b"\x30\x03\x02\x01\x01", good[:40], good[:-1] + b"", b"\x30\x84\xff\xff\xff\xff", b"x" * 64, None):
            for find in (self.controller.key_pin_of, bbapi.key_pin_of, session.key_pin_of):
                got = find(bad)
                self.assertTrue(got == "" or got == by_library(good), (bad, got))
        self.assertEqual(self.controller.key_pin_of(b"x" * 64), "")
        self.assertEqual(self.controller.spki_of(good[:40]), b"")


class TheAgentsPin(Case):
    def call(self, port, pin, token=TOKEN):
        ctl = self.controller.Controller(f"https://127.0.0.1:{port}", token, pin)
        return ctl, ctl.call("beat", {}, timeout=10)

    def test_the_right_key_is_taken_and_another_refused(self):
        srv = self.serve()
        ctl, (st, r) = self.call(srv.server_port, self.pin)
        self.assertEqual((st, r), (200, {"ok": True, "tls": True}))
        self.assertEqual((ctl.seen_pin, ctl.seen_key), (self.pin, self.pin))
        ctl, (st, r) = self.call(srv.server_port, self.another_key())
        self.assertEqual(st, 0)
        self.assertIn("controller key changed", r["error"])
        self.assertEqual(len(srv.asked), 1, "nothing was sent to a key that is not the pinned one: no token left this node")

    def test_a_remade_certificate_under_the_same_key_is_taken(self):
        srv = self.serve()
        cert_pin = "sha256:" + hashlib.sha256(der_of(tls.certificate_pem())).hexdigest()
        self.assertEqual(self.call(srv.server_port, self.pin)[1][0], 200)
        self.assertEqual(self.call(srv.server_port, cert_pin)[1][0], 200, "the certificate's own digest, the form from before")
        again = self.remake()
        self.assertEqual(again["pin"], self.pin)
        self.assertEqual(self.call(srv.server_port, self.pin)[1][0], 200, "a new certificate, the pinned key")
        # The certificate-digest form is as it was: another certificate is refused.
        st, r = self.call(srv.server_port, cert_pin)[1]
        self.assertEqual(st, 0)
        self.assertIn("controller certificate changed", r["error"])

    def test_no_pin_meets_the_certificate_and_says_what_it_saw_as_before(self):
        srv = self.serve()
        ctl, (st, _r) = self.call(srv.server_port, "")
        self.assertEqual(st, 200)
        self.assertEqual(ctl.seen_pin, "sha256:" + hashlib.sha256(der_of(tls.certificate_pem())).hexdigest())

    def test_a_sessions_aerie_and_roots_check_read_the_same_pin(self):
        srv = self.serve()
        url = f"https://127.0.0.1:{srv.server_port}"
        with mock.patch.dict(os.environ, {"BB_CONTROLLER": url, "BB_CONTROLLER_PIN": self.pin, "BB_CONTROLLER_WAIT": "0"}):
            self.assertEqual(bbapi.call("/api/v1/agent/beat", {}, auth="Bearer " + TOKEN), {"ok": True, "tls": True})
            self.remake()
            self.assertEqual(bbapi.call("/api/v1/agent/beat", {}, auth="Bearer " + TOKEN), {"ok": True, "tls": True})
        with mock.patch.dict(os.environ, {"BB_CONTROLLER": url, "BB_CONTROLLER_PIN": self.another_key(), "BB_CONTROLLER_WAIT": "0"}):
            self.assertIn("controller key changed", bbapi.call("/api/v1/agent/beat", {}, auth="Bearer " + TOKEN)["error"])
        session = bb_session()
        st, got = session._grant({"CONTROLLER": url, "CONTROLLER_PIN": self.pin}, "web", TOKEN, False)
        self.assertEqual((st, got.get("ok")), (200, True))
        with self.assertRaises(session.Refused) as no:
            session._grant({"CONTROLLER": url, "CONTROLLER_PIN": self.another_key()}, "web", TOKEN, False)
        self.assertIn("the controller's key is not the one this node pinned", str(no.exception))
        # The certificate's digest, as before, in both.
        cert_pin = "sha256:" + hashlib.sha256(der_of(tls.certificate_pem())).hexdigest()
        self.assertEqual(session._grant({"CONTROLLER": url, "CONTROLLER_PIN": cert_pin}, "web", TOKEN, False)[0], 200)
        with self.assertRaises(session.Refused) as no:
            session._grant({"CONTROLLER": url, "CONTROLLER_PIN": "sha256:" + "0" * 64}, "web", TOKEN, False)
        self.assertIn("the controller's certificate is not the one this node pinned", str(no.exception))


class Enrolling(Case):
    """`enroll --pin`, as the provisioner runs it with what the Enroll script carried."""

    def enroll(self, port, *more):
        import contextlib
        import io
        cli = self.agent.module("cli")
        self.agent.NODE_JSON = os.path.join(self.tmp, "node.json")
        cli.census, cli.make_store, cli.store_path_ok = (lambda state: {}), (lambda path: {}), (lambda path, **kw: "")
        said = io.StringIO()
        with contextlib.redirect_stdout(said):
            cli.cmd_enroll(["--controller", f"https://127.0.0.1:{port}", "--token", "bbe_once", *more])
        with open(os.path.join(self.tmp, "node.json")) as f:
            return json.load(f), said.getvalue()

    def test_the_key_the_enrollment_carried_is_pinned_and_another_refuses_before_the_token_goes(self):
        srv = self.serve()
        state, said = self.enroll(srv.server_port, "--pin", self.pin)
        self.assertEqual((state["controller"], state["pin"], state["token"]), (f"https://127.0.0.1:{srv.server_port}", self.pin, TOKEN))
        self.assertIn("pinned the controller's key", said)
        self.assertNotIn("on first use", said)
        self.assertEqual(self.agent.module("census").channel_now(state), {"scheme": "https", "pin": "key"})
        asked = len(srv.asked)
        with self.assertRaises(SystemExit) as no:
            self.enroll(srv.server_port, "--pin", self.another_key())
        self.assertIn("controller key changed", str(no.exception))
        self.assertEqual(len(srv.asked), asked, "the enroll token was not sent to a key that is not the pinned one")
        # With no pin given the certificate is pinned on first use, as before.
        state, said = self.enroll(srv.server_port)
        self.assertEqual(state["pin"], "sha256:" + hashlib.sha256(der_of(tls.certificate_pem())).hexdigest())
        self.assertIn("on first use", said)


class TheMove(Case):
    """A node enrolled over plain http, at its controller's hello."""

    def setUp(self):
        super().setUp()
        self.nj = os.path.join(self.tmp, "node.json")
        self.agent.NODE_JSON = self.nj
        self.store = os.path.join(self.tmp, "store")
        # Nothing of this machine's own: root's bundle and bb-session are the test's, and not there yet.
        self.agent.ROOT_BUNDLE_DIR = os.path.join(self.tmp, "root-bundle")
        self.agent.SESSION_BIN = os.path.join(self.tmp, "bb-session")
        self.agent.CHANNEL.clear()
        # This node's own folder under its toolchain store, where the bundle its terminals run is.
        os.makedirs(self.store)
        self.assertEqual(self.agent.module("stores").use_scope(self.store, "n_0a1b2c3d"), "n_0a1b2c3d")

    def node(self, url, pin=""):
        state = {"node_id": "n_0a1b2c3d", "token": TOKEN, "controller": url, "stores": {"toolchains": self.store},
                 **({"pin": pin} if pin else {})}
        with open(self.nj, "w") as f:
            json.dump(state, f)
        a = object.__new__(self.agent.Agent)
        a.state, a.hello_at, a.census_asked = state, 5, False
        a.ctl = self.controller.Controller(url, TOKEN, pin)
        a.term_kinds = {"rw": {"env": {"BB_CONTROLLER": url, "BB_CONTROLLER_PIN": pin, "PATH": "/bin"}}}
        a.followed = []
        for step in ("tty_env_write", "refresh_session_tool", "write_session_profile"):
            fn = (lambda name: lambda: a.followed.append(name))(step)
            fn.__name__ = step
            setattr(a, step, fn)
        return a

    def kept(self):
        with open(self.nj) as f:
            return json.load(f)

    def channel(self, a):
        return self.agent.module("census").channel_now(a.state)

    def test_a_probe_that_passes_keeps_https_and_the_pin_and_is_not_undone(self):
        srv = self.serve()
        port = srv.server_port
        a = self.node(f"http://127.0.0.1:{port}")
        self.assertEqual(self.channel(a), {"scheme": "http", "pin": "none"})
        self.assertTrue(a.channel_move({"pin": self.pin}))
        self.assertEqual(srv.asked, [("/api/v1/agent/beat", True)], "asked once, over TLS, as this node")
        want = f"https://127.0.0.1:{port}"
        kept = self.kept()
        self.assertEqual((kept["controller"], kept["pin"], kept["scheme"]), (want, self.pin, "https"))
        self.assertEqual((a.ctl.url, a.ctl.pin, a.ctl.scheme), (want, self.pin, "https"))
        self.assertEqual(a.term_kinds["rw"]["env"], {"BB_CONTROLLER": want, "BB_CONTROLLER_PIN": self.pin, "PATH": "/bin"})
        self.assertEqual(a.followed, ["tty_env_write", "refresh_session_tool", "write_session_profile"])
        self.assertEqual(a.hello_at, 0, "a hello follows, so its row reads the channel now")
        self.assertEqual(self.channel(a), {"scheme": "https", "pin": "key"})
        moved = [m for m in self.said if "does not go back to plain http by itself" in m]
        self.assertEqual(len(moved), 1, self.said)
        self.assertNotIn(self.pin, moved[0])
        # What it does from here goes over TLS, under the key.
        self.assertEqual(a.ctl.call("beat", {}, timeout=10), (200, {"ok": True, "tls": True}))
        # Nothing takes it back: a hello that names no pin, none at all, another key, or the same again.
        a.hello_at = 5
        for named in (None, {}, {"pin": ""}, {"pin": "http"}, {"pin": self.another_key()}, {"pin": self.pin}):
            self.assertFalse(a.channel_move(named), named)
            self.assertEqual((a.ctl.url, a.ctl.pin, self.kept()["controller"], self.kept()["pin"]), (want, self.pin, want, self.pin))
        self.assertEqual((a.hello_at, len(srv.asked)), (5, 2))

    def test_a_port_that_passes_no_tls_leaves_the_node_as_it_is_and_says_so(self):
        srv = self.serve(PlainOnly)
        url = f"http://127.0.0.1:{srv.server_port}"
        a = self.node(url)
        self.assertFalse(a.channel_move({"pin": self.pin}))
        self.assertEqual((a.ctl.url, a.ctl.scheme, self.kept()["controller"]), (url, "http", url))
        self.assertNotIn("pin", self.kept())
        self.assertEqual(self.channel(a), {"scheme": "http", "pin": "none", "why": "its controller's address does not answer over TLS"})
        self.assertEqual(a.followed, [])
        self.assertTrue(any("the channel stays plain http" in m for m in self.said), self.said)
        # It still works as it did.
        self.assertEqual(a.ctl.call("beat", {}, timeout=10)[0], 200)
        # Once the address answers over TLS it moves, and what it said is gone.
        a.ctl = self.controller.Controller(f"http://127.0.0.1:{self.serve().server_port}", TOKEN, "")
        self.assertTrue(a.channel_move({"pin": self.pin}))
        self.assertEqual(self.channel(a), {"scheme": "https", "pin": "key"})

    def test_another_key_or_another_controller_at_the_address_is_not_moved_to(self):
        srv = self.serve()
        url = f"http://127.0.0.1:{srv.server_port}"
        # The address answers TLS under a key that is not the one named.
        a = self.node(url)
        self.assertFalse(a.channel_move({"pin": self.another_key()}))
        self.assertEqual((a.ctl.url, self.kept()["controller"], len(srv.asked)), (url, url, 0))
        self.assertEqual(self.channel(a)["why"], "its controller's address does not answer over TLS")
        # Under the key, but not as this node's controller (its token is not known there).
        a = self.node(url)
        a.state["token"] = "bbn_another"
        self.assertFalse(a.channel_move({"pin": self.pin}))
        self.assertEqual((a.ctl.url, self.kept()["controller"]), (url, url))
        self.assertEqual(self.channel(a)["why"], "its controller answered 401 over TLS")

    def test_session_tools_from_before_a_key_pin_hold_the_move(self):
        srv = self.serve()
        url = f"http://127.0.0.1:{srv.server_port}"
        a = self.node(url)
        lib = os.path.join(self.store, "n_0a1b2c3d", ".bb", "current", "scripts", "lib")
        os.makedirs(lib)
        with open(os.path.join(lib, "bbapi.py"), "w") as f:
            f.write("# a client from before: it takes any pin for a certificate's digest\n")
        self.assertFalse(a.channel_move({"pin": self.pin}))
        self.assertEqual((a.ctl.url, srv.asked), (url, []))
        self.assertEqual(self.channel(a)["why"], "its session tools are from before a pinned channel")
        # The controller's bundle arrives, root's copy and bb-session with it: it moves.
        shutil.copy(os.path.join(REPO, "scripts", "lib", "bbapi.py"), lib)
        os.makedirs(os.path.join(self.tmp, "root-bundle", "current", "scripts", "lib"))
        shutil.copy(os.path.join(REPO, "scripts", "lib", "bbapi.py"), os.path.join(self.tmp, "root-bundle", "current", "scripts", "lib"))
        shutil.copy(os.path.join(REPO, "nodes", "bb-session"), os.path.join(self.tmp, "bb-session"))
        self.assertEqual(a.channel_reads_key(), "")
        self.assertTrue(a.channel_move({"pin": self.pin}))
        # ...and a bb-session from before holds it the same way.
        a = self.node(url)
        with open(os.path.join(self.tmp, "bb-session"), "w") as f:
            f.write("#!/usr/bin/python3\n")
        self.assertFalse(a.channel_move({"pin": self.pin}))
        self.assertEqual(a.channel_reads_key(), os.path.join(self.tmp, "bb-session"))

    def test_a_node_that_pinned_the_certificate_pins_the_key_it_is_over(self):
        srv = self.serve()
        url = f"https://127.0.0.1:{srv.server_port}"
        cert_pin = "sha256:" + hashlib.sha256(der_of(tls.certificate_pem())).hexdigest()
        a = self.node(url, cert_pin)
        self.assertEqual(self.channel(a), {"scheme": "https", "pin": "cert"})
        self.assertEqual(a.ctl.call("beat", {}, timeout=10)[0], 200)            # the hello this follows
        # A key that is not the one its certificate is over is not taken on the controller's word.
        self.assertFalse(a.channel_move({"pin": self.another_key()}))
        self.assertEqual(self.kept()["pin"], cert_pin)
        self.assertTrue(a.channel_move({"pin": self.pin}))
        self.assertEqual((self.kept()["controller"], self.kept()["pin"], a.ctl.pin), (url, self.pin, self.pin))
        self.assertEqual(self.channel(a), {"scheme": "https", "pin": "key"})
        # The certificate is remade: the node that would have been refused goes on.
        self.remake()
        self.assertEqual(a.ctl.call("beat", {}, timeout=10)[0], 200)

    def test_a_node_reached_through_a_public_hostname_is_left_to_its_authorities(self):
        a = self.node("https://bb.example.test", "ca")
        self.assertFalse(a.channel_move({"pin": self.pin}))
        self.assertEqual((self.kept()["pin"], self.channel(a)), ("ca", {"scheme": "https", "pin": "ca"}))
        a = self.node("http://127.0.0.1:9")
        a.state["reach"] = "public"
        self.assertFalse(a.channel_move({"pin": self.pin}))
        self.assertEqual(a.ctl.scheme, "http")


class TheController(unittest.TestCase):
    """The controller's half: the pin its hello names, and what it keeps and says of a node's channel."""

    def setUp(self):
        nodes.configure(state=tempfile.mkdtemp())
        nodes._auto_tried.clear()
        mint = nodes.enroll_mint("user:test", "box")
        self.census = {"cpu": 2, "mem_mb": 4096, "arch": "x86_64", "system": "linux", "session": {"up": True, "user": "b"}}
        nodes.enroll(nodes.authenticate(mint["token"]), self.census, "box.lan", user="bb")
        self.nid = mint["id"]

    def test_an_old_agents_hello_is_answered_as_before_with_the_pin_beside_it(self):
        self.assertEqual(nodes.tls_pin(), "", "nothing names a pin until the server hands this module the certificate's")
        before = nodes.hello(self.nid, self.census, "box.lan")
        self.assertNotIn("tls", before)
        pin = "sha256//" + "A" * 43 + "="
        with mock.patch.object(nodes, "tls_pin", lambda: pin):
            after = nodes.hello(self.nid, self.census, "box.lan")
        self.assertEqual(after["tls"], {"pin": pin})
        # Everything an agent read before is there, with the same value: the answer only gained a field.
        skip = {"tls", "session_tokens", "token"}
        self.assertEqual({k: v for k, v in after.items() if k not in skip}, {k: v for k, v in before.items() if k not in skip})
        self.assertEqual(set(after) - set(before), {"tls"})

    def test_a_nodes_channel_is_kept_by_its_kind_and_said_in_a_phrase(self):
        def reported(channel):
            nodes.hello(self.nid, dict(self.census, **({"channel": channel} if channel is not None else {})), "box.lan")
            return nodes.node(self.nid)
        n = reported(None)
        self.assertNotIn("channel", n["reported"])
        self.assertEqual(nodes.channel_said(n), "", "an agent from before this says nothing of it, and neither does its row")
        n = reported({"scheme": "http", "pin": "none", "why": "its controller's address does not answer over TLS"})
        self.assertEqual(n["reported"]["channel"], {"scheme": "http", "pin": "none", "why": "its controller's address does not answer over TLS"})
        self.assertEqual(nodes.channel_said(n), "over plain http")
        with mock.patch.object(nodes, "turns_of", lambda n: []):
            row = nodes.tab_view([dict(n, kind="agent")], True)["nodes"][0]
        self.assertEqual(row["channel_said"], "over plain http")
        n = reported({"scheme": "https", "pin": "key"})
        self.assertEqual((n["reported"]["channel"], nodes.channel_said(n)), ({"scheme": "https", "pin": "key"}, ""))
        with mock.patch.object(nodes, "turns_of", lambda n: []):
            self.assertNotIn("channel_said", nodes.tab_view([dict(n, kind="agent")], True)["nodes"][0])
        # What is not one of the words is not kept as said.
        for bad in ("http", {"scheme": "gopher"}, {"scheme": "https", "pin": "sha256//" + "A" * 43 + "="}, []):
            n = reported(bad)
            self.assertNotIn("sha256//", json.dumps(n["reported"].get("channel") or {}))
            self.assertIn((n["reported"].get("channel") or {}).get("pin", "none"), ("none",))


if __name__ == "__main__":
    unittest.main()
