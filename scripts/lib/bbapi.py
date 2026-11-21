"""The controller's API, from `aerie`: one client for the verbs that reach it.

bb used to carry four copies of the same twelve lines: build a Request to
http://127.0.0.1:<port>, send the auth header, decode the answer or the
error. Each assumed the dashboard was on the loopback, which was true for as
long as bb only ran on the controller. Since roadmap #24 a session runs ON A
NODE, where the controller is at BB_CONTROLLER over the LAN and possibly
https with a self-signed certificate, and then the four copies would each
have needed the same three changes.

So this is where those changes live:

  * the URL is BB_CONTROLLER when set (the agent exports it into every
    session it starts), the loopback otherwise;
  * https is verified by PIN, not by CA, exactly as the node agent verifies
    it: BB_CONTROLLER_PIN is the pin the node holds, the controller's key
    (KEY_PIN's form, which any certificate over that key passes) or the
    certificate digest the node learned at enrollment, and a different one
    is refused. No pin and https is allowed and unverified, which is the
    node's own choice at enrollment, repeated here;
  * the auth header is whatever bb_auth_or_die produced: a session token
    (Bearer) or a name:password for the command (Basic).

Standard library only, like everything else bb runs, and loaded by path from
the lib directory beside bb (BB_LIB) so the checkout's copy runs with the
checkout's bb.
"""
import base64
import errno
import secrets
import hashlib
import http.client
import itertools
import json
import os
import ssl
import sys
import time
import urllib.parse

import scopedir


def keep_token(tok):
    """A renewed session token, written where bb_token_now reads: the same
    per-project file bb-tty writes when a tab is opened, so a session in use
    never runs out (users.renewal). The project comes from the token itself
    rather than the environment, because bb runs with BB_PROJECT set and a
    hook may not. Best effort: a token that could not be kept is a token
    that expires on schedule, which is what happened before. Returns "" when
    it was kept and why not otherwise, so `aerie token keep` (the agent's idle
    refresh) can say so rather than succeed at nothing."""
    try:
        raw = tok[len("bbs_"):]
        project = base64.urlsafe_b64decode(raw + "=" * (-len(raw) % 4)).decode().split("|")[0]
        if not project or "/" in project:
            return "the token names no space"
        # The account's own folder for the space (B159).
        d = scopedir.scope_dir(project)
        os.makedirs(d, mode=0o700, exist_ok=True)
        # A unique temporary name, not a fixed one: the agent refreshes this
        # file for a session that is idle (R27) while the session's own bb may
        # be writing it, and two writers sharing `token.new` is the race that
        # cost B165 elsewhere in this tree.
        tmp = os.path.join(d, f"token.{os.getpid()}.{secrets.token_hex(4)}.new")
        with open(os.open(tmp, os.O_WRONLY | os.O_CREAT | os.O_TRUNC, 0o600), "w") as f:
            f.write(tok + "\n")
        os.replace(tmp, os.path.join(d, "token"))
    except (OSError, ValueError, UnicodeDecodeError) as e:
        return f"{type(e).__name__}: {e}"
    return ""


# A pin of the controller's key, as the node agent reads it (its
# controller.py, which says why): this, then the base64 of the sha256 of
# the certificate's SubjectPublicKeyInfo. The agent hands a session this
# form only where this file reads it (it looks for this line).
KEY_PIN = "sha256//"


def _tlv(buf, at):
    """(tag, where its value starts, where it ends) of the DER element at `at`."""
    tag, n = buf[at], buf[at + 1]
    at += 2
    if n & 0x80:
        k = n & 0x7F
        if not 1 <= k <= 4:
            raise ValueError("not a DER length")
        n = int.from_bytes(buf[at:at + k], "big")
        at += k
    if at + n > len(buf):
        raise ValueError("a DER element runs past its buffer")
    return tag, at, at + n


def key_pin_of(der):
    """The pin of the key a DER certificate carries, or "": its
    SubjectPublicKeyInfo found by stepping over the fields before it, as
    the agent finds it (controller.spki_of; a test holds the two, and
    bb-session's, to each other and to the cryptography library)."""
    try:
        tag, at, end = _tlv(der, 0)
        if tag != 0x30:
            return ""
        tag, at, end = _tlv(der, at)
        if tag != 0x30:
            return ""
        tag, _, after = _tlv(der, at)
        if tag == 0xA0:
            at = after
        for _ in range(5):
            _, _, at = _tlv(der, at)
        tag, _, after = _tlv(der, at)
        if tag != 0x30 or after > end:
            return ""
    except (IndexError, ValueError, TypeError):
        return ""
    return KEY_PIN + base64.b64encode(hashlib.sha256(bytes(der[at:after])).digest()).decode()


def url():
    return (os.environ.get("BB_CONTROLLER")
            or f"http://127.0.0.1:{os.environ.get('DASHBOARD_PORT', '7680')}").rstrip("/")


class Unnamed(http.client.HTTPSConnection):
    """A TLS connection that sends no server name: what a connection held
    to a key's pin is. The controller answers a handshake that asks for its
    hostname with that name's certificate, which is another key's, and
    every other handshake with the install's own, the one a node pinned: a
    node that dials by the hostname and said so was answered with a key it
    refuses. The pin is the whole check, so nothing is lost by not naming
    who is dialed."""

    def connect(self):
        http.client.HTTPConnection.connect(self)
        self.sock = self._context.wrap_socket(self.sock, server_hostname=None)


def _conn(timeout):
    u = urllib.parse.urlsplit(url())
    # A setting typed by hand with no scheme ("controller.lan:7680") parses
    # with no host at all, and a port that is not a number raises: both used
    # to escape as a TypeError traceback from every bb verb (B179). As OSError
    # they are what the callers already turn into {"error": ...}, naming it.
    try:
        port = u.port or (443 if u.scheme == "https" else 80)
    except ValueError:
        port = 0
    if not u.hostname or not port or u.scheme not in ("http", "https"):
        raise OSError(f"BB_CONTROLLER {url()!r} is not an address: it wants "
                      "http://HOST:PORT or https://HOST:PORT")
    if u.scheme != "https":
        return http.client.HTTPConnection(u.hostname, port, timeout=timeout), u.path.rstrip("/")
    ctx = ssl.create_default_context()
    pin = os.environ.get("BB_CONTROLLER_PIN", "")
    if pin == "ca":
        # A node enrolled by a public hostname (--reach public): the name's
        # own certificate by the system's CAs, as the agent's client checks
        # it (controller.py's CA). Nothing is pinned: what the node sees is
        # the edge's certificate, which changes. Compared to a digest, as
        # every other pin is, this was refused, and no aerie verb in a
        # session on such a node reached its controller (R243).
        return http.client.HTTPSConnection(u.hostname, port, timeout=timeout, context=ctx), u.path.rstrip("/")  # nosemgrep: python.lang.security.audit.httpsconnection-detected.httpsconnection-detected
    ctx.check_hostname = False
    ctx.verify_mode = ssl.CERT_NONE                 # the pin below is the check
    # Pinned on first use, see the agent. A key's pin sends no server name
    # (Unnamed), as the agent's connection does not.
    c = (Unnamed if pin.startswith(KEY_PIN) else http.client.HTTPSConnection)(  # nosemgrep: python.lang.security.audit.httpsconnection-detected.httpsconnection-detected
        u.hostname, port, timeout=timeout, context=ctx)
    c.connect()
    der = c.sock.getpeercert(True)
    if pin.startswith(KEY_PIN):
        # The controller's key: any certificate over it, and no other.
        if key_pin_of(der) != pin:
            c.close()
            raise OSError(f"controller key changed: pinned {pin[:19]}…, presented another")
        return c, u.path.rstrip("/")
    seen = "sha256:" + hashlib.sha256(der).hexdigest()
    if pin and seen != pin:
        c.close()
        raise OSError(f"controller certificate changed: pinned {pin[:19]}…, "
                      f"presented {seen[:19]}…")
    return c, u.path.rstrip("/")


def call(path, body=None, auth="", method="", timeout=30):
    """One request; the decoded JSON answer, or {"error": ...}.

    The shape every caller in bb already handled: an HTTP error whose body
    is JSON comes back as that JSON (the server's own sentence), any other
    failure as an error string. POST when a body is given, GET otherwise."""
    return request(path, body, auth, method, timeout)[1]


# How long a call waits for a controller that refuses the connection (R251):
# it is restarting after an update most of the time, which takes under a
# minute, and a session that failed there treated the update as a real
# failure and changed course. Ninety seconds by default; a hook, which runs
# under a timeout of its own, sets BB_CONTROLLER_WAIT=0.
WAIT_STEPS = (2, 3, 5, 5, 10, 10, 15, 15, 15, 15)
# A connection that reached no server, beside a refused one: worth asking again.
UNREACHED = frozenset({errno.EHOSTUNREACH, errno.ENETUNREACH})


def _gate_down():
    """Tell the session's gate (bb-gate, the PreToolUse hook) at once that the
    controller did not answer, so the next tool call is held rather than let
    through by the twenty seconds a fine check is trusted for (R251)."""
    project = os.environ.get("BB_PROJECT", "")
    if not project or "/" in project:
        return
    sf = scopedir.scope_dir(project, "gate")
    try:
        os.makedirs(os.path.dirname(sf), mode=0o700, exist_ok=True)
        with open(sf, "w") as f:
            json.dump({"ok": False, "at": time.time()}, f)
    except OSError:
        pass


def request(path, body=None, auth="", method="", timeout=30):
    """call(), with the HTTP status beside the answer: (status, answer).

    The status is None when nothing answered at all: no connection, a
    timeout, a pin that did not match. call() cannot say that, because a
    refusal the server words ("not signed in") and a refused connection both
    come back as {"error": sentence}, and telling them apart by the wording
    is how bb-gate came to report an expired token as AerieOS being down.

    A refused connection, or one that found no route to the host (B771),
    is waited out (R251): the request never reached a server, so asking
    again cannot do anything twice. So is a GET the server
    hung up on before answering; a POST it may have read is not sent again."""
    try:
        budget = max(0, int(os.environ.get("BB_CONTROLLER_WAIT", "90")))
    except ValueError:
        budget = 90
    waited, said = 0, False
    # The steps, then the last one again until the budget is spent (B772:
    # they add up to 95s, and a longer BB_CONTROLLER_WAIT was cut there).
    for step in itertools.chain(WAIT_STEPS, itertools.repeat(WAIT_STEPS[-1])):
        st, got, again = _request_once(path, body, auth, method, timeout)
        if not again:
            if said and st is not None:
                print("[builderbot] the controller is back", file=sys.stderr)
            if budget and isinstance(got, dict) and got.get("agent_behind"):
                return _agent_wait(path, body, auth, method, timeout, st, got)
            return st, got
        if not said:
            _gate_down()
        if waited + step > budget:
            break
        if not said:
            print(f"[builderbot] the controller is not answering (restarting after an update?): "
                  f"waiting up to {budget}s", file=sys.stderr)
            said = True
        time.sleep(step)
        waited += step
    return None, {"error": f"the controller did not answer{f' for {waited}s' if waited else ''} ({got.get('error')}): "
                           "it is restarting after an update, or down. Wait and try again; if it stays "
                           "down, write where you are and what is next to your notes and end the turn, "
                           "and the operator checks the container"}


# How long a job refused only because its node's agent is behind waits for
# that agent's update (R253): the controller queues it itself once the node is
# idle, and it lands in under a minute; the job was refused, so asking again
# does nothing twice.
AGENT_WAIT_S = 150


def _agent_wait(path, body, auth, method, timeout, st, got):
    waited = 0
    print("[builderbot] the node's agent is behind this controller and is being updated: "
          f"waiting up to {AGENT_WAIT_S}s to send this", file=sys.stderr)
    while waited < AGENT_WAIT_S:
        time.sleep(10)
        waited += 10
        st, got, _again = _request_once(path, body, auth, method, timeout)
        if not (isinstance(got, dict) and got.get("agent_behind")):
            print("[builderbot] the node's agent is current: sent", file=sys.stderr)
            return st, got
    got = dict(got)
    got["error"] = (f"{got.get('error') or 'the node is behind'} (waited {waited}s for its agent's update; "
                    "if it is still busy, try again once its jobs finish, or press Update agent on its row)")
    return st, got


def _request_once(path, body, auth, method, timeout):
    """One attempt: (status, answer, worth asking again)."""
    hdrs = {"Authorization": auth or os.environ.get("BB_AUTH_HEADER", "")}
    data = None
    if body is not None:
        data = json.dumps(body).encode()
        hdrs["Content-Type"] = "application/json"
    try:
        c, base = _conn(timeout)
        c.request(method or ("POST" if body is not None else "GET"), base + path, data, hdrs)
        r = c.getresponse()
        payload = r.read()
        fresh = r.getheader("X-BB-Session", "")
        c.close()
    except ConnectionRefusedError as e:
        return None, {"error": str(e)}, True
    except http.client.RemoteDisconnected as e:
        if (method or ("POST" if body is not None else "GET")) == "GET":
            return None, {"error": str(e)}, True
        # A POST it may have read is not sent again here; the answer says so
        # and carries hung_up, so a verb that can look whether its ask landed
        # (a rebuild's job) looks and asks again itself (B803).
        return None, {"error": f"{e}: the controller hung up before answering, so it may or may not "
                               "have done it", "hung_up": True}, False
    except OSError as e:
        # The gap while a controller's container is replaced can answer "no
        # route to host" rather than a refusal (B771): no server was reached
        # either way, so it is waited out the same.
        if e.errno in UNREACHED:
            return None, {"error": str(e)}, True
        return None, {"error": str(e)}, False
    except http.client.HTTPException as e:
        return None, {"error": str(e)}, False
    if fresh and fresh.startswith("bbs_"):
        keep_token(fresh)
    if r.status == 204 or not payload:
        return r.status, ({} if r.status < 400 else {"error": f"HTTP {r.status}"}), False
    try:
        got = json.loads(payload)
    except ValueError:
        return r.status, {"error": f"HTTP {r.status}"}, False
    if r.status >= 400 and isinstance(got, dict) and not got.get("error"):
        got["error"] = f"HTTP {r.status}"
    return r.status, got, False
