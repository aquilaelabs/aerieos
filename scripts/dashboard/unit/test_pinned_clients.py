"""The three clients that reach the controller from a node read its pin the
same way (R243; the audit of 13 Nov): the agent's (controller.py), a
session's aerie (lib/bbapi.py) and the root session helper's own
(nodes/bb-session, which imports nothing a session could change, so the
three cannot be one module). A node enrolled by a public hostname is given
the pin 'ca': the name's own certificate by the system's CAs, nothing
pinned. The agent alone understood it; the other two compared it to a
digest and refused, so on such a node no aerie verb reached the controller
and no terminal opened. One table here drives all three."""
import hashlib
import http.client
import importlib.machinery
import importlib.util
import os
import ssl
import sys
import unittest
from unittest import mock

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.abspath(os.path.join(HERE, "..", "..", ".."))
sys.path.insert(0, HERE)
sys.path.insert(0, os.path.join(ROOT, "scripts", "lib"))
import agentpkg  # noqa: E402
import bbapi  # noqa: E402

CERT = b"the certificate the door presents"
SEEN = "sha256:" + hashlib.sha256(CERT).hexdigest()
OTHER = "sha256:" + "0" * 64


class Door:
    """http.client.HTTPSConnection, answering with CERT and remembering how it was asked."""
    made = []

    def __init__(self, host, port, timeout=None, context=None):
        self.host, self.context, self.closed = host, context, False
        self.sock = mock.Mock()
        self.sock.getpeercert.return_value = CERT
        Door.made.append(self)

    def connect(self):
        pass

    def close(self):
        self.closed = True

    def request(self, *a, **k):
        pass

    def getresponse(self):
        r = mock.Mock()
        r.status = 200
        r.read.return_value = b"{}"
        return r


def by_the_cas(ctx):
    return ctx.verify_mode == ssl.CERT_REQUIRED and ctx.check_hostname is True


def agent(pin):
    Controller = agentpkg.load("controller").module("controller").Controller
    Controller("https://controller.example:7680", "tok", pin)._conn(5)


def session(pin):
    with mock.patch.dict(os.environ, {"BB_CONTROLLER": "https://controller.example:7680", "BB_CONTROLLER_PIN": pin}):
        bbapi._conn(5)


def helper(pin):
    loader = importlib.machinery.SourceFileLoader("bb_session_pins", os.path.join(ROOT, "nodes", "bb-session"))
    spec = importlib.util.spec_from_loader("bb_session_pins", loader)
    mod = importlib.util.module_from_spec(spec)
    loader.exec_module(mod)
    mod._grant({"CONTROLLER": "https://controller.example:7680", "CONTROLLER_PIN": pin}, "sh:1:alpha", "bbs_abcdefgh", False)


class Pins(unittest.TestCase):
    def ask(self, client, pin):
        Door.made.clear()
        with mock.patch.object(http.client, "HTTPSConnection", Door):
            try:
                client(pin)
            except Exception as e:                             # noqa: BLE001 (each client refuses in its own words)
                return "refused", Door.made[-1], str(e)
        return "reached", Door.made[-1], ""

    def test_all_three_read_a_pin_the_same_way(self):
        for name, client in (("the agent", agent), ("a session's aerie", session), ("the session helper", helper)):
            with self.subTest(client=name):
                # The certificate's own digest: reached, and the CAs are not asked (a home proxy's is self-signed).
                how, door, _ = self.ask(client, SEEN)
                self.assertEqual(how, "reached")
                self.assertFalse(by_the_cas(door.context))
                # Another certificate than the one pinned: refused, and the connection shut.
                how, door, why = self.ask(client, OTHER)
                self.assertEqual(how, "refused", name)
                self.assertTrue(door.closed)
                self.assertRegex(why, "certificate")
                # A public hostname: the name's certificate by the system's CAs, and no digest compared.
                how, door, why = self.ask(client, "ca")
                self.assertEqual(how, "reached", f"{name}: {why}")
                self.assertTrue(by_the_cas(door.context), name)
                door.sock.getpeercert.assert_not_called()
                # No pin yet (the first contact): reached, to be pinned.
                how, door, _ = self.ask(client, "")
                self.assertEqual(how, "reached")


if __name__ == "__main__":
    unittest.main()
