"""An enrollment names its controller as https, with the pin of the
controller's own key (R267 step 15).

On the LAN and behind WireGuard a node dials the controller's own port,
which answers a handshake under the install's own key in every Connection
mode. The controller asks the address the node is to dial for a handshake
itself (tls.node_reach): answered under its own key, the Enroll script and
the Nodes page's token-only commands name https at the same address and
carry the pin, for curl (--pinnedpubkey on every fetch the provisioner
makes from the controller) and for the agent (--pin at enrollment). Where
that address answers no handshake (a proxy in front that speaks only http)
the words are as they were, and the node moves by itself afterwards if it
can. A hostname whose certificate the system's authorities take keeps its
name and is held to them. The public-hostname reach is unchanged.

Real sockets on loopback, the dashboard's own tls.py serving, and the
provisioner's fetch made for real with curl where curl is here."""
import os
import re
import shutil
import ssl
import subprocess
import sys
import tempfile
import threading
import unittest
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from unittest import mock

HERE = os.path.dirname(os.path.abspath(__file__))
REPO = os.path.normpath(os.path.join(HERE, "..", "..", ".."))
sys.path.insert(0, os.path.join(HERE, ".."))
import enrollscript as es  # noqa: E402
import nodes  # noqa: E402
import signing  # noqa: E402
import tls  # noqa: E402

PIN_RE = r"sha256//[A-Za-z0-9+/]{43}="
ROUTER = """[Interface]
PrivateKey = cHJpdmF0ZWtleXByaXZhdGVrZXlwcml2YXRla2V5MDA=
Address = 10.6.0.5/32

[Peer]
PublicKey = cHVibGlja2V5cHVibGlja2V5cHVibGlja2V5cHViMDA=
AllowedIPs = 0.0.0.0/0
Endpoint = home.example.net:51820
"""


class Handler(BaseHTTPRequestHandler):
    def do_GET(self):
        self.server.asked.append((self.path, self.headers.get("Authorization", ""), isinstance(self.connection, ssl.SSLSocket)))
        body = b"#!/bin/sh\n# the agent\n"
        self.send_response(200)
        self.send_header("X-Agent-Digest", "sha256:" + "ab" * 32)
        self.send_header("Content-Length", str(len(body)))
        self.end_headers()
        self.wfile.write(body)

    def log_message(self, format, *args):
        del format, args


class Both(tls.WrapOnItsThread, ThreadingHTTPServer):
    daemon_threads = True

    def handle_error(self, request, client_address):
        del request, client_address


class PlainOnly(ThreadingHTTPServer):
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

    def serve(self, kind=Both):
        srv = kind(("127.0.0.1", 0), Handler)
        srv.asked = []
        threading.Thread(target=srv.serve_forever, daemon=True).start()
        self.addCleanup(srv.shutdown)
        self.addCleanup(srv.server_close)
        return srv


class WhatTheAddressAnswers(Case):
    def test_its_own_key_there_names_https_at_the_same_address_with_the_pin(self):
        port = self.serve().server_port
        want = (f"https://127.0.0.1:{port}", self.pin)
        self.assertRegex(self.pin, "^" + PIN_RE + "$")
        for url in (f"http://127.0.0.1:{port}", f"http://127.0.0.1:{port}/", f"https://127.0.0.1:{port}"):
            self.assertEqual(tls.node_reach(url), want, url)
        # In every Connection mode: http above, and the install's own certificate as the page's.
        tls.apply({"tls_mode": "self", "tls_host": "bb.example.test"}.get, names=["127.0.0.1"])
        self.assertEqual(tls.node_reach(f"http://127.0.0.1:{port}"), want)

    def test_an_address_that_answers_no_handshake_is_left_as_it_was(self):
        proxy = self.serve(PlainOnly).server_port
        for url in (f"http://127.0.0.1:{proxy}", f"https://127.0.0.1:{proxy}"):
            self.assertEqual(tls.node_reach(url), (url, ""), "a proxy that speaks only http")
        closed = self.serve()
        closed.shutdown()
        closed.server_close()
        url = f"http://127.0.0.1:{closed.server_port}"
        self.assertEqual(tls.node_reach(url), (url, ""), "nothing listens there")
        for bad in ("", "192.168.1.10", "ftp://192.168.1.10", "http://192.168.1.10:port"):
            self.assertEqual(tls.node_reach(bad), (bad, ""))

    def test_another_key_there_is_not_this_controllers_and_names_no_pin(self):
        port = self.serve().server_port
        mine = self.pin
        # The port's certificate is another install's now: this one's key is not what answers.
        with mock.patch.object(tls, "key_pin", lambda: tls.key_pin_of(tls.self_signed(["127.0.0.1"])[0])):
            for url in (f"http://127.0.0.1:{port}", f"https://127.0.0.1:{port}"):
                self.assertEqual(tls.node_reach(url), (url, ""))
        self.assertEqual(tls.node_reach(f"http://127.0.0.1:{port}")[1], mine)

    def test_a_name_the_systems_authorities_take_keeps_its_name_and_is_held_to_them(self):
        other = ssl.PEM_cert_to_DER_cert(tls.self_signed(["bb.example.test"])[0])
        asked = []

        def presented(host, port, verify, timeout):
            asked.append((host, port, verify))
            return other
        with mock.patch.object(tls, "_presented", presented):
            self.assertEqual(tls.node_reach("https://bb.example.test:7680"), ("https://bb.example.test:7680", "ca"))
            # Over plain http a name is not moved to its certificate: nothing says the name's port passes TLS to this controller.
            self.assertEqual(tls.node_reach("http://bb.example.test:7680"), ("http://bb.example.test:7680", ""))
        self.assertEqual(asked[:2], [("bb.example.test", 7680, False), ("bb.example.test", 7680, True)])
        # For real: a certificate nobody vouches for, at a name, is neither this controller's key nor the authorities'.
        self.assertIsNone(tls._presented("127.0.0.1", self.serve().server_port, True, 2), "an address has no name to check")

    def test_with_no_certificate_loaded_nothing_is_asked_and_nothing_named(self):
        tls._ctx = None
        with mock.patch.object(tls, "_presented", side_effect=AssertionError("nothing is dialed")):
            self.assertEqual(tls.node_reach("http://192.168.1.10:7680"), ("http://192.168.1.10:7680", ""))

    def test_in_the_acme_mode_an_address_meets_the_installs_own_key(self):
        cert, key = tls.self_signed(["bb.example.test"])
        tls._keep(cert, key, tls.ACME, ["bb.example.test"])
        st = tls.apply({"tls_mode": "acme", "tls_host": "bb.example.test"}.get, names=["127.0.0.1"])
        self.assertEqual((st["kind"], st["pin"]), ("acme", self.pin))
        port = self.serve().server_port
        self.assertEqual(tls.node_reach(f"http://127.0.0.1:{port}"), (f"https://127.0.0.1:{port}", self.pin))


class TheWords(unittest.TestCase):
    """The Enroll script's words, and the token-only commands', for each reach."""
    PIN = "sha256//" + "A" * 43 + "="

    def run_line(self, ans):
        s = es.build(ans, name="box", user="bb", token="bbe_x", expires=0, provisioner=b"x")
        return next(x for x in s.splitlines() if x.startswith('bash "$dir/provision-linux.sh"')), s

    def test_the_script_names_what_it_was_handed_for_each_reach(self):
        lan = es.check({"reach": "lan", "controller": "http://192.168.1.10:7680"})
        run, _ = self.run_line(lan | {"controller": "https://192.168.1.10:7680", "controller_pin": self.PIN})
        self.assertIn(f"--controller 'https://192.168.1.10:7680' --token 'bbe_x' --controller-pin '{self.PIN}'", run)
        run, _ = self.run_line(lan | {"controller_pin": ""})
        self.assertIn("--controller 'http://192.168.1.10:7680' --token 'bbe_x'", run)
        self.assertNotIn("--controller-pin", run)
        wg = es.check({"reach": "wireguard", "controller": "http://192.168.1.16:7680", "wg_conf": ROUTER})
        run, _ = self.run_line(wg | {"controller": "https://192.168.1.16:7680", "controller_pin": self.PIN})
        self.assertIn(f"--controller 'https://192.168.1.16:7680' --token 'bbe_x' --controller-pin '{self.PIN}'", run)
        self.assertIn('--wg-conf "$dir/bb.conf"', run)
        run, _ = self.run_line(es.check({"reach": "lan", "controller": "https://bb.example.test:7680"}) | {"controller_pin": "ca"})
        self.assertIn("--controller 'https://bb.example.test:7680' --token 'bbe_x' --controller-pin 'ca'", run)
        public = es.check({"reach": "public", "controller": "https://bb.example.com"})
        run, _ = self.run_line(public)
        self.assertIn("--controller 'https://bb.example.com'", run)
        self.assertIn("--reach public", run)
        self.assertNotIn("--controller-pin", run)

    def test_the_token_only_commands_words(self):
        self.assertEqual(es.reach_words("https://192.168.1.10:7680", self.PIN),
                         {"url": "https://192.168.1.10:7680", "curl": f"-k --pinnedpubkey {self.PIN}",
                          "provisioner": f"--controller-pin {self.PIN}", "agent": f"--pin {self.PIN}"})
        self.assertEqual(es.reach_words("https://bb.example.test", "ca"),
                         {"url": "https://bb.example.test", "curl": "", "provisioner": "--controller-pin ca", "agent": "--pin ca"})
        for none in ("", "sha256:" + "0" * 64, "x; rm -rf /", self.PIN + " x"):
            self.assertEqual(es.reach_words("http://192.168.1.10:7680", none),
                             {"url": "http://192.168.1.10:7680", "curl": "", "provisioner": "", "agent": ""}, none)


class FromTheController(unittest.TestCase):
    """nodes.py's half: the address asked about before anything is minted, and what the page is handed."""
    PIN = "sha256//" + "B" * 43 + "="

    def setUp(self):
        nodes.configure(state=tempfile.mkdtemp())
        # Reaching the controller through WireGuard is offered behind dev features.
        import forges
        was = nodes.forges, forges.unvetted_ok
        nodes.forges, forges.unvetted_ok = forges, lambda: True
        self.addCleanup(lambda: (setattr(nodes, "forges", was[0]), setattr(forges, "unvetted_ok", was[1])))
        self.asked = []

    def reach(self, answer):
        def said(url):
            self.asked.append(url)
            return answer(url)
        return mock.patch.object(nodes, "tls_reach", said)

    def moved(self, url):
        return re.sub(r"^http:", "https:", url), self.PIN

    def run_line(self, r):
        self.assertNotIn("error", r, r)
        return next(x for x in r["script"].splitlines() if x.startswith('bash "$dir/provision-linux.sh"'))

    def test_the_script_for_the_lan_and_for_wireguard_names_https_and_the_pin(self):
        with self.reach(self.moved):
            run = self.run_line(nodes.enroll_script("user:test", {"name": "lanbox", "reach": "lan", "controller": "http://192.168.1.10:7680"}))
            self.assertIn("--controller 'https://192.168.1.10:7680' --token 'bbe_", run)
            self.assertIn(f"--controller-pin '{self.PIN}'", run)
            r = nodes.enroll_script("user:test", {"name": "wgbox", "reach": "wireguard", "controller": "http://192.168.1.16:7680", "wg_conf": ROUTER})
            run = self.run_line(r)
            self.assertIn("--controller 'https://192.168.1.16:7680'", run)
            self.assertIn(f"--controller-pin '{self.PIN}'", run)
            self.assertIn("tcp dport 7680 accept", r["home"], "the router's rule names the same port")
        self.assertEqual(self.asked, ["http://192.168.1.10:7680", "http://192.168.1.16:7680"])

    def test_a_public_hostname_is_not_asked_about_and_carries_no_pin(self):
        with self.reach(self.moved):
            run = self.run_line(nodes.enroll_script("user:test", {"name": "vps", "reach": "public", "controller": "https://bb.example.com"}))
        self.assertIn("--controller 'https://bb.example.com'", run)
        self.assertNotIn("--controller-pin", run)
        self.assertEqual(self.asked, [])

    def test_an_address_that_answers_no_tls_gets_the_words_it_always_did(self):
        with self.reach(lambda url: (url, "")):
            run = self.run_line(nodes.enroll_script("user:test", {"name": "proxied", "reach": "lan", "controller": "http://proxy.lan"}))
        self.assertIn("--controller 'http://proxy.lan' --token 'bbe_", run)
        self.assertNotIn("--controller-pin", run)
        # ...and with nothing set by a server at all, as before this.
        run = self.run_line(nodes.enroll_script("user:test", {"name": "plain", "reach": "lan", "controller": "http://192.168.1.10:7680"}))
        self.assertIn("--controller 'http://192.168.1.10:7680'", run)

    def test_the_page_is_handed_the_address_and_each_commands_words(self):
        plain = nodes.enroll_pins()
        self.assertEqual(sorted(plain), ["agent", "provisioner", "words"], "a shell that names its own address gets no pin for it")
        with self.reach(self.moved):
            got = nodes.enroll_pins("http://192.168.1.10:7680")
        self.assertEqual((got["url"], got["curl"]), ("https://192.168.1.10:7680", f"-k --pinnedpubkey {self.PIN}"))
        self.assertEqual(got["provisioner"], f"{plain['provisioner']} --controller-pin {self.PIN}")
        self.assertEqual(got["agent"], f"{plain['agent']} --pin {self.PIN}")
        self.assertEqual(got["words"], plain["words"])
        with self.reach(lambda url: (url, "")):
            got = nodes.enroll_pins("http://proxy.lan")
        self.assertEqual((got["url"], got["curl"], got["provisioner"], got["agent"]),
                         ("http://proxy.lan", "", plain["provisioner"], plain["agent"]))
        # The verb the page presses: a token, and the words for the address it sent.
        with self.reach(self.moved):
            r = nodes.verb("user:test", {"action": "enroll", "name": "tokbox", "controller": "http://192.168.1.10:7680"})
        self.assertEqual((r[0]["pins"]["url"], r[1]), ("https://192.168.1.10:7680", 200), r)


class TheProvisioner(Case):
    """provision-linux.sh and provision-macos.sh: every fetch from the controller under the pin."""

    def text(self, name):
        with open(os.path.join(REPO, "nodes", name)) as f:
            return f.read()

    def test_every_fetch_from_the_controller_carries_the_pin_and_the_agent_is_handed_it(self):
        for name in ("provision-linux.sh", "provision-macos.sh"):
            text = self.text(name)
            # A line that runs curl (not one that names it in a sentence) against the controller: its
            # address on the line, or the line after for a fetch written over two.
            lines = text.splitlines()
            at = ("${CONTROLLER%/}", "${PIN_URL%/}")
            fetches = [ln for i, ln in enumerate(lines)
                       if re.match(r'\s*(if |\|\| |code="\$\()?curl ', ln)
                       and (any(a in ln for a in at) or (ln.rstrip().endswith("\\") and any(a in lines[i + 1] for a in at)))]
            self.assertGreaterEqual(len(fetches), 2 if name.endswith("macos.sh") else 5, name)
            for ln in fetches:
                # The one fetch that is a public hostname's own check is by the system's authorities.
                if 'curl -s -o /dev/null -D "$rhdr"' in ln:
                    continue
                # A run again on an enrolled node holds it to the pin its record keeps.
                self.assertTrue('--pinnedpubkey "$CTL_KEY"' in ln or '--pinnedpubkey "$held"' in ln, f"{name}: {ln.strip()[:120]}")
                # ...and a fetch held to a key dials the address, the name as its Host header.
                if name == "provision-linux.sh":
                    self.assertIn('${PIN_HOST[@]+"${PIN_HOST[@]}"}', ln, ln.strip()[:120])
            enrolls = len(re.findall(r'(?m)^\s*(?:BUILDERBOT_NODE_JSON="\$\w+" )?(?:python3 )?"\$(?:AGENT|agent)" enroll\b', text))
            self.assertEqual((enrolls, text.count('${CONTROLLER_PIN:+--pin "$CONTROLLER_PIN"}')),
                             ((1, 1) if name.endswith("macos.sh") else (2, 2)), f"{name}: every enroll is handed the pin")
            self.assertIn("--controller-pin) CONTROLLER_PIN=", text)

    def test_a_pin_that_goes_with_nothing_or_is_no_pin_is_said_before_anything_runs(self):
        for name in ("provision-linux.sh", "provision-macos.sh"):
            script = os.path.join(REPO, "nodes", name)
            for args, why in ((["--controller", "http://192.0.2.1:7680", "--controller-pin", self.pin], "is what an https controller is held to"),
                              (["--controller", "https://192.0.2.1:7680", "--controller-pin", "sha256:" + "0" * 64], "--controller-pin takes the controller's key"),
                              (["--controller", "https://192.0.2.1:7680", "--controller-pin", self.pin[:-3]], "--controller-pin takes the controller's key")):
                r = subprocess.run(["bash", script, *args, "--token", "bbe_x", "--check"], capture_output=True, text=True, timeout=60, check=False)
                self.assertEqual(r.returncode, 1, (name, args, r.stdout[-300:], r.stderr[-300:]))
                self.assertIn(why, r.stderr)

    @unittest.skipUnless(shutil.which("curl"), "curl is not here")
    def test_the_provisioners_fetch_is_made_under_the_pin_for_real(self):
        srv = self.serve()
        text = self.text("provision-linux.sh")
        # The managed node's download, as the provisioner writes it, run as it runs it.
        m = re.search(r"\n(    pinned_at [^\n]*\n    curl -fsSL \$\{CTL_KEY:\+-k --pinnedpubkey \"\$CTL_KEY\"\} [^\n]*--retry 6 [^\n]*\\\n[^\n]*-o \"\$\{AGENT\}\.new\")", text)
        self.assertTrue(m, "the provisioner's download of the agent")
        helper = re.search(r"^pinned_at\(\) \{\n.*?^\}\n", text, re.M | re.S).group(0)
        fetch = helper + m.group(1).replace("--retry 6 --retry-delay 3 --retry-connrefused", "--max-time 10")

        def run(key, host="127.0.0.1"):
            out, hdr = os.path.join(self.tmp, "agent"), os.path.join(self.tmp, "hdr")
            for f in (out + ".new", hdr):
                if os.path.exists(f):
                    os.unlink(f)
            env = dict(os.environ, CTL_KEY=key, TOKEN="bbe_once", CONTROLLER=f"https://{host}:{srv.server_port}", AGENT=out, hdr=hdr)
            r = subprocess.run(["bash", "-euo", "pipefail", "-c", fetch], env=env, capture_output=True, text=True, timeout=60, check=False)
            return r, out + ".new"
        r, got = run(self.pin)
        self.assertEqual(r.returncode, 0, r.stderr)
        with open(got, "rb") as f:
            self.assertEqual(f.read(), b"#!/bin/sh\n# the agent\n")
        self.assertEqual(srv.asked, [("/api/v1/agent/download", "Bearer bbe_once", True)])
        # Another key at the address: nothing fetched, and the token never sent.
        other = tls.key_pin_of(tls.self_signed(["127.0.0.1"])[0])
        r, got = run(other)
        self.assertNotEqual(r.returncode, 0)
        self.assertFalse(os.path.exists(got) and os.path.getsize(got))
        self.assertEqual(len(srv.asked), 1, "the enroll token was not sent to a key that is not the pinned one")
        # With no pin the same line is the fetch it always was: by the system's authorities, which this certificate fails.
        r, got = run("")
        self.assertNotEqual(r.returncode, 0)
        self.assertEqual(len(srv.asked), 1)
        # A name the controller holds a public certificate for: asked by that
        # name, it answers with that certificate, whose key is not the one
        # pinned. Dialed by its address with no server name, it is the
        # install's own key that answers.
        if not subprocess.run(["getent", "ahosts", "localhost"], capture_output=True, check=False).stdout.startswith(b"127.0.0.1"):
            return
        cert, key = tls.self_signed(["localhost"])
        tls._keep(cert, key, tls.ACME, ["localhost"])
        tls.apply({"tls_mode": "acme", "tls_host": "localhost"}.get, names=["127.0.0.1"])
        self.assertEqual(tls.key_pin(), self.pin, "the install's own key is unchanged")
        r, got = run(self.pin, host="localhost")
        self.assertEqual(r.returncode, 0, r.stderr)
        self.assertEqual(srv.asked[-1], ("/api/v1/agent/download", "Bearer bbe_once", True))


if __name__ == "__main__":
    unittest.main()
