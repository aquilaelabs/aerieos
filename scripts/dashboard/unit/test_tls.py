"""The dashboard's own TLS (R158 step 2): the mode read from the settings,
a self-signed pair made for the names and kept with its key sealed, one
socket serving https and http by the first byte, and the status the
Connection section and the Doctor read.

And what a node's channel is pinned to (R267 step 15): the install's own
certificate is there and loaded in every mode, http among them, with what a
browser at http:// gets unchanged; its key is kept when the certificate is
remade, so the key's pin outlives every renewal; in the acme mode the
name's certificate answers its name and the install's own everything else;
an install that kept the name's pair in cert.pem has it carried to its own
files; the key is sealed again when the install key changes; and curl's
--pinnedpubkey takes the pin for real."""
import base64
import hashlib
import http.client
import json
import os
import shutil
import socket
import ssl
import subprocess
import sys
import tempfile
import threading
import time
import unittest
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))
import signing  # noqa: E402
import tls      # noqa: E402

KEY = bytes(range(32))


class Mode(unittest.TestCase):
    def test_the_mode_reads_as_set_else_from_the_hostname(self):
        self.assertEqual(tls.mode_of({"tls_mode": "", "tls_host": ""}.get), "http")
        self.assertEqual(tls.mode_of({"tls_mode": "", "tls_host": "bb.example.com"}.get), "self")
        self.assertEqual(tls.mode_of({"tls_mode": "http", "tls_host": "bb.example.com"}.get), "http")
        self.assertEqual(tls.mode_of({"tls_mode": "ACME", "tls_host": "x"}.get), "acme")


class Pair(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.mkdtemp()
        self.addCleanup(shutil.rmtree, self.tmp, True)
        self.was = signing.MASTER, signing.PREVIOUS
        signing.MASTER, signing.PREVIOUS = KEY, None
        self.addCleanup(lambda: setattr(signing, "MASTER", self.was[0]) or setattr(signing, "PREVIOUS", self.was[1]))
        tls.RUN_DIR = self.tmp
        tls.configure(state=self.tmp, seal_fn=signing.seal, unseal_fn=signing.unseal,
                      sealing_fn=lambda: signing.MASTER is not None)
        tls._ctx, tls._pending = None, {}
        self.addCleanup(lambda: setattr(tls, "_ctx", None))

    def test_self_signed_for_the_names_kept_with_the_key_sealed(self):
        st = tls.apply({"tls_mode": "self", "tls_host": "bb.example.com"}.get, names=["192.168.1.10"])
        self.assertEqual((st["mode"], st["on"], st["kind"]), ("self", True, "self"))
        self.assertIn("bb.example.com", st["names"])
        self.assertRegex(st["fingerprint"], r"^([0-9A-F]{2}:){31}[0-9A-F]{2}$")
        self.assertGreater(st["expires"], 0)
        self.assertTrue(st["key_sealed"])
        raw = open(os.path.join(self.tmp, "tls", "key.pem")).read()
        self.assertTrue(raw.startswith("bbseal:") and "PRIVATE KEY" not in raw)
        self.assertIn("BEGIN CERTIFICATE", tls.certificate_pem())
        self.assertEqual([f for f in os.listdir(self.tmp) if f.startswith("builderbot-tls-")], [], "the opened key is gone after the load")
        # Applied again with the same names: the pair stays.
        fp = st["fingerprint"]
        self.assertEqual(tls.apply({"tls_mode": "self", "tls_host": "bb.example.com"}.get, names=["192.168.1.10"])["fingerprint"], fp)
        # Off again: no context, the pair kept for next time.
        self.assertFalse(tls.apply({"tls_mode": "http", "tls_host": "bb.example.com"}.get)["on"])
        self.assertTrue(os.path.exists(os.path.join(self.tmp, "tls", "cert.pem")))

    def test_one_port_serves_both(self):
        tls.apply({"tls_mode": "self", "tls_host": "localhost"}.get, names=["127.0.0.1"])

        class H(BaseHTTPRequestHandler):
            def do_GET(self):
                body = json.dumps({"tls": isinstance(self.connection, ssl.SSLSocket)}).encode()
                self.send_response(200); self.send_header("Content-Length", str(len(body))); self.end_headers()
                self.wfile.write(body)

            def log_message(self, format, *args):
                del format, args

        class S(tls.WrapOnItsThread, ThreadingHTTPServer):
            daemon_threads = True

        srv = S(("127.0.0.1", 0), H)
        threading.Thread(target=srv.serve_forever, daemon=True).start()
        self.addCleanup(srv.shutdown)
        port = srv.server_port
        plain = http.client.HTTPConnection("127.0.0.1", port, timeout=5)
        plain.request("GET", "/"); self.assertEqual(json.loads(plain.getresponse().read()), {"tls": False})
        ctx = ssl.create_default_context()
        ctx.check_hostname = False
        ctx.verify_mode = ssl.CERT_NONE
        sec = http.client.HTTPSConnection("127.0.0.1", port, timeout=5, context=ctx)
        sec.request("GET", "/"); self.assertEqual(json.loads(sec.getresponse().read()), {"tls": True})
        # The certificate served is the one kept.
        with socket.create_connection(("127.0.0.1", port), timeout=5) as raw, ctx.wrap_socket(raw, server_hostname="localhost") as s:
            der = s.getpeercert(binary_form=True)
        from cryptography import x509
        from cryptography.hazmat.primitives import hashes
        got = ":".join(f"{b:02X}" for b in x509.load_der_x509_certificate(der).fingerprint(hashes.SHA256()))
        self.assertEqual(got, tls.fingerprint())
        # A connection that sends nothing holds nobody else up (R228 step 3):
        # its first byte is waited for on its own thread, not the accept one.
        with socket.create_connection(("127.0.0.1", port), timeout=5):
            t0 = time.monotonic()
            quick = http.client.HTTPConnection("127.0.0.1", port, timeout=5)
            quick.request("GET", "/")
            self.assertEqual(json.loads(quick.getresponse().read()), {"tls": False})
            self.assertLess(time.monotonic() - t0, 2.0)


class H(BaseHTTPRequestHandler):
    def do_GET(self):
        body = json.dumps({"tls": isinstance(self.connection, ssl.SSLSocket)}).encode()
        self.send_response(200)
        self.send_header("Content-Length", str(len(body)))
        self.end_headers()
        self.wfile.write(body)

    def log_message(self, format, *args):
        del format, args


class S(tls.WrapOnItsThread, ThreadingHTTPServer):
    daemon_threads = True

    def handle_error(self, request, client_address):
        # A client that leaves mid-handshake (a pin that does not match) is the test's own doing.
        del request, client_address


def pin_of_der(der):
    """A key's pin worked out from what a handshake presented, with the
    cryptography library and nothing of tls.py's."""
    from cryptography import x509
    from cryptography.hazmat.primitives import serialization
    spki = x509.load_der_x509_certificate(der).public_key().public_bytes(
        serialization.Encoding.DER, serialization.PublicFormat.SubjectPublicKeyInfo)
    return "sha256//" + base64.b64encode(hashlib.sha256(spki).digest()).decode()


class Own(unittest.TestCase):
    """The install's own pair, in every mode."""

    def setUp(self):
        self.tmp = tempfile.mkdtemp()
        self.addCleanup(shutil.rmtree, self.tmp, True)
        self.was = signing.MASTER, signing.PREVIOUS
        signing.MASTER, signing.PREVIOUS = KEY, None
        self.addCleanup(lambda: setattr(signing, "MASTER", self.was[0]) or setattr(signing, "PREVIOUS", self.was[1]))
        tls.RUN_DIR = self.tmp
        tls.configure(state=self.tmp, seal_fn=signing.seal, unseal_fn=signing.unseal,
                      sealing_fn=lambda: signing.MASTER is not None)
        tls._ctx, tls._pending, tls._mode = None, {}, "http"
        self.addCleanup(lambda: setattr(tls, "_ctx", None))

    def serve(self):
        srv = S(("127.0.0.1", 0), H)
        threading.Thread(target=srv.serve_forever, daemon=True).start()
        self.addCleanup(srv.shutdown)
        return srv.server_port

    def presented(self, port, name=None):
        """The certificate the port answers a handshake with, asked for `name` or for none."""
        ctx = ssl.create_default_context()
        ctx.check_hostname = False
        ctx.verify_mode = ssl.CERT_NONE
        with socket.create_connection(("127.0.0.1", port), timeout=5) as raw, ctx.wrap_socket(raw, server_hostname=name) as c:
            return c.getpeercert(binary_form=True)

    def kept(self, name):
        with open(os.path.join(self.tmp, "tls", name)) as f:
            return f.read()

    def test_the_http_mode_holds_a_certificate_and_a_browser_at_http_gets_what_it_got(self):
        st = tls.apply({"tls_mode": "http", "tls_host": ""}.get)
        self.assertEqual((st["mode"], st["on"]), ("http", False), "the Connection section still reads http")
        self.assertRegex(st["pin"], r"^sha256//[A-Za-z0-9+/]{43}=$")
        self.assertEqual(st["names"], ["aerieos"], "with no name or address known, it names aerieos")
        self.assertTrue(self.kept("key.pem").startswith("bbseal:"))
        port = self.serve()
        plain = http.client.HTTPConnection("127.0.0.1", port, timeout=5)
        plain.request("GET", "/")
        r = plain.getresponse()
        self.assertEqual((r.status, json.loads(r.read())), (200, {"tls": False}))
        # ...and whoever opens with a handshake is answered under the install's own key.
        self.assertEqual(pin_of_der(self.presented(port)), st["pin"])
        self.assertEqual(tls.key_pin(), st["pin"])
        # The mode with no setting at all is the same.
        self.assertEqual(tls.apply({}.get)["pin"], st["pin"])

    def test_the_key_is_kept_when_the_certificate_is_remade(self):
        first = tls.apply({"tls_mode": "http"}.get, names=["192.168.1.10"])
        key = tls._key_text()
        # A name added: a new certificate over the same key, the names it had kept.
        second = tls.apply({"tls_mode": "self", "tls_host": "bb.example.com"}.get, names=["192.168.1.10"])
        self.assertNotEqual(second["fingerprint"], first["fingerprint"])
        self.assertEqual(second["pin"], first["pin"])
        self.assertEqual(tls._key_text(), key)
        self.assertEqual(set(second["names"]), {"192.168.1.10", "bb.example.com"})
        # Near its end: remade, the key kept.
        was = tls.RENEW_BEFORE
        self.addCleanup(setattr, tls, "RENEW_BEFORE", was)
        tls.RENEW_BEFORE = (tls.SELF_DAYS + 1) * 86400
        self.assertTrue(tls.own_due())
        third = tls.apply({"tls_mode": "self", "tls_host": "bb.example.com"}.get, names=["192.168.1.10"])
        tls.RENEW_BEFORE = was
        self.assertFalse(tls.own_due())
        self.assertNotEqual(third["fingerprint"], second["fingerprint"])
        self.assertEqual(third["pin"], first["pin"])
        # ...and what the port presents after it is the new certificate under the pinned key.
        port = self.serve()
        der = self.presented(port)
        self.assertEqual(pin_of_der(der), first["pin"])
        self.assertEqual(":".join(f"{b:02X}" for b in hashlib.sha256(der).digest()), third["fingerprint"])

    def named_pair(self, name):
        """A stand-in for the name's certificate: another key's, for `name`."""
        cert, key = tls.self_signed([name])
        tls._keep(cert, key, tls.ACME, [name])
        return tls.key_pin_of(cert)

    def test_the_names_certificate_answers_its_name_and_the_installs_own_everything_else(self):
        own = tls.apply({"tls_mode": "acme", "tls_host": "bb.example.com"}.get, names=["192.168.1.10"])
        self.assertEqual((own["on"], own["kind"]), (True, "self"), "until the name's comes, the install's own answers")
        theirs = self.named_pair("bb.example.com")
        with tls._lock:
            tls._ctx = tls._load_context()
        st = tls.status({"tls_mode": "acme", "tls_host": "bb.example.com"}.get)
        self.assertEqual((st["kind"], st["names"], st["pin"]), ("acme", ["bb.example.com"], own["pin"]))
        self.assertNotEqual(theirs, own["pin"])
        self.assertIn("BEGIN CERTIFICATE", tls.certificate_pem())
        self.assertEqual(tls.key_pin_of(tls.certificate_pem()), theirs, "Download is the certificate a browser meets")
        port = self.serve()
        self.assertEqual(pin_of_der(self.presented(port, "bb.example.com")), theirs)
        self.assertEqual(pin_of_der(self.presented(port, "BB.Example.com")), theirs)
        for other in (None, "other.example.com", "example.com"):
            self.assertEqual(pin_of_der(self.presented(port, other)), own["pin"], other)
        # Applied again (a start, a setting saved): both stay, each under its own files.
        again = tls.apply({"tls_mode": "acme", "tls_host": "bb.example.com"}.get, names=["192.168.1.10"])
        self.assertEqual((again["kind"], again["pin"]), ("acme", own["pin"]))
        # Out of the acme mode the install's own answers every name, the name's pair kept for next time.
        self.assertEqual(tls.apply({"tls_mode": "self", "tls_host": "bb.example.com"}.get)["kind"], "self")
        self.assertEqual(pin_of_der(self.presented(port, "bb.example.com")), own["pin"])
        self.assertTrue(os.path.exists(os.path.join(self.tmp, "tls", "acme-cert.pem")))
        self.assertFalse(tls.renew_due())

    def test_a_wildcard_answers_one_label_deep(self):
        self.assertTrue(tls._answers(("*.example.com",), "bb.example.com"))
        self.assertFalse(tls._answers(("*.example.com",), "a.bb.example.com"))
        self.assertFalse(tls._answers(("*.example.com",), "example.com"))

    def test_an_install_that_kept_the_names_pair_in_cert_pem_has_it_carried(self):
        # As a build before this kept it: one pair, of the kind in force.
        # The numbered migration moves it to the name's own files, and the
        # start after it makes the install's own pair beside it.
        import importlib
        cert, key = tls.self_signed(["bb.example.com"])
        d = os.path.join(self.tmp, "tls")
        os.makedirs(d, mode=0o700)
        with open(os.path.join(d, "cert.pem"), "w") as f:
            f.write(cert)
        with open(os.path.join(d, "key.pem"), "w") as f:
            f.write("bbseal:" + base64.b64encode(signing.seal(key.encode())).decode() + "\n")
        with open(os.path.join(d, "meta.json"), "w") as f:
            json.dump({"kind": "acme", "names": ["bb.example.com"], "made": 5}, f)
        mig = importlib.import_module("statemigrations.0028_a_pair_for_the_name")
        mig.run({"state": self.tmp})
        with open(os.path.join(d, "meta.json")) as f:
            self.assertEqual(json.load(f), {"kind": "self", "names": [], "made": 0, "acme": {"names": ["bb.example.com"], "made": 5}})
        self.assertFalse(os.path.exists(os.path.join(d, "cert.pem")) or os.path.exists(os.path.join(d, "key.pem")))
        mig.run({"state": self.tmp})   # run again: as it left it
        st = tls.apply({"tls_mode": "acme", "tls_host": "bb.example.com"}.get, names=["192.168.1.10"])
        self.assertEqual(self.kept("acme-cert.pem"), cert)
        self.assertEqual(tls._key_text(tls.ACME).strip(), key.strip())
        self.assertEqual((st["kind"], st["on"]), ("acme", True))
        self.assertEqual(tls.key_pin_of(tls.certificate_pem()), tls.key_pin_of(cert))
        self.assertNotEqual(st["pin"], tls.key_pin_of(cert), "the install's own pair is made beside it, with a key of its own")
        self.assertEqual(json.loads(self.kept("meta.json"))["acme"], {"names": ["bb.example.com"], "made": 5})
        # An install's own pair of before (the self mode) is kept as it is: certificate, key and all.
        tls._ctx = None
        shutil.rmtree(d)
        cert, key = tls.self_signed(["bb.example.com", "192.168.1.10"])
        tls._keep(cert, key, "self", ["bb.example.com", "192.168.1.10"])
        before = self.kept("meta.json")
        mig.run({"state": self.tmp})
        self.assertEqual(self.kept("meta.json"), before, "the install's own pair is not the migration's to move")
        st = tls.apply({"tls_mode": "self", "tls_host": "bb.example.com"}.get, names=["192.168.1.10"])
        self.assertEqual((self.kept("cert.pem"), st["pin"]), (cert, tls.key_pin_of(cert)))

    def test_the_key_is_sealed_again_when_the_install_key_changes(self):
        pin = tls.apply({"tls_mode": "http"}.get)["pin"]
        self.named_pair("bb.example.com")
        signing.MASTER, signing.PREVIOUS = bytes(range(1, 33)), KEY
        self.assertEqual(tls.seal_all(again=True), 2)
        signing.PREVIOUS = None                       # the one before let go
        tls._ctx = None
        self.assertEqual(tls.apply({"tls_mode": "http"}.get)["pin"], pin, "the same key, opened under today's")
        self.assertTrue(tls._key_text(tls.ACME))
        # A key kept in the open before there was an install key is sealed once there is one.
        plain = tls._key_text()
        with open(os.path.join(self.tmp, "tls", "key.pem"), "w") as f:
            f.write(plain + "\n")
        self.assertEqual(tls.seal_all(), 1)
        self.assertTrue(self.kept("key.pem").startswith("bbseal:"))
        self.assertEqual(tls.seal_all(), 0)

    def test_a_key_that_cannot_be_opened_is_the_one_case_a_new_one_is_made(self):
        import contextlib
        import io
        pin = tls.apply({"tls_mode": "http"}.get)["pin"]
        signing.MASTER = bytes(range(2, 34))          # another install key, the old one gone
        tls._ctx = None
        said = io.StringIO()
        with contextlib.redirect_stdout(said):
            st = tls.apply({"tls_mode": "http"}.get)
        self.assertTrue(st["pin"])
        self.assertNotEqual(st["pin"], pin)
        self.assertIn("a new one is made", said.getvalue())

    def test_nothing_names_a_pin_while_nothing_is_loaded(self):
        self.assertEqual(tls.key_pin(), "")
        tls.apply({"tls_mode": "http"}.get)
        self.assertTrue(tls.key_pin())
        tls._ctx = None
        self.assertEqual(tls.key_pin(), "")
        self.assertEqual(tls.key_pin_of("not a certificate"), "")

    @unittest.skipUnless(shutil.which("curl"), "curl is not here")
    def test_curl_takes_the_pin_and_refuses_another_key(self):
        st = tls.apply({"tls_mode": "http"}.get, names=["127.0.0.1"])
        port = self.serve()

        def curl(pin):
            return subprocess.run(["curl", "-sS", "-k", "--max-time", "10", "--pinnedpubkey", pin, f"https://127.0.0.1:{port}/"],
                                  capture_output=True, text=True, timeout=30, check=False)
        r = curl(st["pin"])
        self.assertEqual((r.returncode, json.loads(r.stdout or "{}")), (0, {"tls": True}), r.stderr)
        other = tls.key_pin_of(tls.self_signed(["127.0.0.1"])[0])
        r = curl(other)
        self.assertNotEqual(r.returncode, 0)
        self.assertEqual(r.stdout, "", "nothing is sent to a key that is not the pinned one")
        # A remade certificate under the same key is taken by the same pin.
        was = tls.RENEW_BEFORE
        tls.RENEW_BEFORE = (tls.SELF_DAYS + 1) * 86400
        try:
            again = tls.apply({"tls_mode": "http"}.get, names=["127.0.0.1"])
        finally:
            tls.RENEW_BEFORE = was
        self.assertNotEqual(again["fingerprint"], st["fingerprint"])
        self.assertEqual(curl(st["pin"]).returncode, 0)


if __name__ == "__main__":
    unittest.main()
