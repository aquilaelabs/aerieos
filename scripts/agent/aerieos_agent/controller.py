"""The connection to the controller."""
import base64
import hashlib
import http.client
import json
import os
import re
import shutil
import ssl
import urllib.request
from . import AGENT_VERSION


# ---------------------------------------------------------------------------
# the connection

# One TLS context of each kind a process (R228 step 18): one made for every
# request read the system's CA store each time, 4 to 7 ms a call. `verify`
# is the CA-checked kind (a public hostname); the other checks nothing
# itself, its caller comparing the certificate with the pin.
_CONTEXTS = {}


def _context(verify):
    got = _CONTEXTS.get(verify)
    if got is None:
        got = ssl.create_default_context()
        if not verify:
            got.check_hostname = False
            got.verify_mode = ssl.CERT_NONE
        _CONTEXTS[verify] = got
    return got


# A pin of the controller's KEY: this, then the base64 of the sha256 of the
# key's public half (the certificate's SubjectPublicKeyInfo, in DER), which
# is the form curl's --pinnedpubkey takes, so the Enroll script hands one
# word to both. It names the key and nothing else of the certificate: the
# controller remakes its certificate over the same key, and the pin holds.
KEY_PIN = "sha256//"


def _tlv(buf, at):
    """(tag, where its value starts, where it ends) of the DER element at
    `at`; ValueError for one that runs past the buffer."""
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


def spki_of(der):
    """The SubjectPublicKeyInfo of a DER certificate, whole, or b"". It is
    the seventh field of the certificate's body, after the optional version
    and the serial number, signature algorithm, issuer, validity and
    subject: found by stepping over those, with no library, since this
    package is the standard library alone and the standard library hands
    out the certificate but not its key. Nothing is decided here but where
    the field is: what does not parse as a certificate has no key, and a
    pin then matches nothing."""
    try:
        tag, at, end = _tlv(der, 0)                 # Certificate
        if tag != 0x30:
            return b""
        tag, at, end = _tlv(der, at)                # its body, tbsCertificate
        if tag != 0x30:
            return b""
        tag, _, after = _tlv(der, at)
        if tag == 0xA0:                             # [0] version, where there is one
            at = after
        for _ in range(5):                          # serial, signature, issuer, validity, subject
            _, _, at = _tlv(der, at)
        tag, _, after = _tlv(der, at)
        if tag != 0x30 or after > end:
            return b""
        return bytes(der[at:after])
    except (IndexError, ValueError, TypeError):
        return b""


def key_pin_of(der):
    """The pin of the key a DER certificate carries (KEY_PIN's form), or ""."""
    spki = spki_of(der)
    return KEY_PIN + base64.b64encode(hashlib.sha256(spki).digest()).decode() if spki else ""


# The controller's address, the one shape taken from another's word (a
# move's answer) and the only one written where a shell reads it
# (/etc/profile.d): http or https, a host of letters, digits, dots and
# hyphens or an IPv6 literal in brackets, a port or none, and no path past
# a single slash.
ADDRESS = re.compile(r"(https?)://(?:\[[0-9A-Fa-f:.]{2,45}\]|[A-Za-z0-9][A-Za-z0-9.-]{0,252})(?::[0-9]{1,5})?/?")


# The pin that is no pin: the name's certificate, by the system's authorities.
CA_PIN = "ca"


def address_ok(url, https=False):
    """Whether `url` is of the controller's one shape (ADDRESS); with
    `https`, of that scheme alone."""
    m = ADDRESS.fullmatch(url) if isinstance(url, str) else None
    return bool(m) and (not https or m.group(1) == "https")


class Controller:
    """One controller, one credential, one way to talk to it.

    TLS is verified by PIN, not by CA, in one of two forms. The controller's
    KEY (KEY_PIN and the key's digest) is what the Enroll script carries and
    what a node moves to by itself: every connection must present a
    certificate over that key, whatever else the certificate says, so the
    controller's own renewals pass. The certificate's digest (sha256: and
    hex) is the form from before, given with --pin or trusted on first use
    and printed so it can be checked: every later connection must present
    that very certificate. A LAN dashboard with a self-signed certificate is
    exactly the case, and a CA is a later layer (docs/nodes.md §4). Plain
    http is allowed and said plainly: the token then travels in the clear,
    which is no worse than the dashboard's own credential already does on
    that network, and no better.
    """

    # The pin that means "no pin: the hostname's public certificate, by the
    # system's CAs" (R170): a controller behind Cloudflare presents the
    # edge's certificate, which changes under it and is not the controller's.
    CA = CA_PIN

    def __init__(self, url, token, pin="", door="agent"):
        u = urllib.parse.urlsplit(url)
        if u.scheme not in ("http", "https") or not u.hostname:
            raise SystemExit(f"controller URL is not http(s)://host[:port]: {url}")
        self.url, self.token, self.pin = url.rstrip("/"), token, pin
        self.scheme, self.host = u.scheme, u.hostname
        self.port = u.port or (443 if u.scheme == "https" else 80)
        self.base = u.path.rstrip("/")
        # Which door it speaks to: the agent's, or a person's device's
        # (/api/v1/device/, R270), whose app reuses this connection whole.
        self.door = door
        # Sent with every request beside the token: the companion's
        # X-BB-Door, the door's compatibility window (R270 step 9).
        self.headers = {}

    def _conn(self, timeout):
        if self.scheme == "http":
            return http.client.HTTPConnection(self.host, self.port, timeout=timeout)
        ctx = _context(self.pin == self.CA)
        if self.pin == self.CA:
            # A public hostname (R170): the system's CAs and the name, as a
            # browser would; nothing is pinned, since the certificate the
            # node sees is Cloudflare's edge's and not the controller's.
            c = http.client.HTTPSConnection(self.host, self.port, timeout=timeout, context=ctx)  # nosemgrep: python.lang.security.audit.httpsconnection-detected.httpsconnection-detected (its own CA, verified: ctx)
            c.connect()
            self.seen_pin = self.CA
            return c
        # The pin below is the check (_context made this one without a CA's).
        # The certificate is pinned on first use and any other refused; a CA
        # check would refuse the self-signed one a home proxy serves.
        # nosemgrep: httpsconnection-detected
        c = http.client.HTTPSConnection(self.host, self.port, timeout=timeout,  # nosemgrep: python.lang.security.audit.httpsconnection-detected.httpsconnection-detected (its own CA, verified: ctx)
                                        context=ctx)
        c.connect()
        der = c.sock.getpeercert(True)
        seen = "sha256:" + hashlib.sha256(der).hexdigest()
        # The key this certificate is over, for whoever asks whether the
        # controller's named key is the one just met (the agent's move).
        self.seen_key = key_pin_of(der)
        if self.pin.startswith(KEY_PIN):
            # The key pinned: any certificate over it passes, no other does.
            if self.seen_key != self.pin:
                c.close()
                raise ssl.SSLError(f"controller key changed: pinned {self.pin[:19]}…, "
                                   f"presented {self.seen_key[:19] or 'no key this node can read'}…")
            self.seen_pin = self.pin
            return c
        if self.pin and seen != self.pin:
            c.close()
            raise ssl.SSLError(f"controller certificate changed: pinned "
                               f"{self.pin[:19]}…, presented {seen[:19]}…")
        self.seen_pin = seen
        return c

    def call(self, verb, body=None, timeout=30, method="POST", raw=False):
        """(status, decoded body). Status 0 means no answer at all
        (the controller is down or unreachable), and is the case the loop
        backs off on rather than treating as a refusal."""
        try:
            c = self._conn(timeout)
            hdrs = {"Authorization": "Bearer " + self.token,
                    "User-Agent": f"builderbot-agent/{AGENT_VERSION}", **self.headers}
            data = None
            if body is not None:
                data = json.dumps(body).encode()
                hdrs["Content-Type"] = "application/json"
            c.request(method, f"{self.base}/api/v1/{self.door}/{verb}", data, hdrs)
            r = c.getresponse()
            payload = r.read()
            c.close()
        except (OSError, http.client.HTTPException) as e:
            return 0, {"error": f"{type(e).__name__}: {e}"}
        if raw:
            return r.status, payload
        if r.status == 204 or not payload:
            return r.status, {}
        try:
            return r.status, json.loads(payload)
        except ValueError:
            return r.status, {"error": payload[:200].decode("utf-8", "replace")}

    def fetch(self, path, dest, timeout=600):
        """GET a large body straight to a file. (status, digest-header).
        The snapshot and the bundle both arrive this way, and neither
        belongs in memory twice."""
        try:
            c = self._conn(timeout)
            c.request("GET", f"{self.base}/api/v1/{self.door}/{path}", None,
                      {"Authorization": "Bearer " + self.token,
                       "User-Agent": f"builderbot-agent/{AGENT_VERSION}", **self.headers})
            r = c.getresponse()
            if r.status != 200:
                r.read()
                c.close()
                return r.status, ""
            tmp = dest + ".part"
            with open(tmp, "wb") as f:
                shutil.copyfileobj(r, f)
            c.close()
            os.replace(tmp, dest)
            return 200, (r.getheader("X-Snapshot-Digest") or r.getheader("X-Bundle-Digest") or "")
        except (OSError, http.client.HTTPException) as e:
            return 0, str(e)

    def upload_pieces(self, path, src, piece, timeout=600, say=None):
        """upload() in pieces of `piece` bytes, each its own request with
        offset and total in the query (relocate.data_put takes them): what
        a body limit on the way (Cloudflare's 100 MB, R170) asks for. The
        last piece's answer is the whole upload's; a piece the controller
        says it has already is not sent again."""
        size = os.path.getsize(src)
        sep = "&" if "?" in path else "?"
        off = 0
        while True:
            n = min(piece, size - off)
            code, r = self.upload(f"{path}{sep}offset={off}&total={size}", src, timeout=timeout,
                                  offset=off, length=n)
            if code != 200:
                return code, r
            off = int((r or {}).get("bytes") or off + n)
            if say and off < size:
                say(off)
            if off >= size or not (r or {}).get("more"):
                return code, r

    def upload(self, path, src, timeout=600, offset=0, length=None):
        """POST a file as the raw body, or `length` bytes of it from
        `offset` (a transcript's new tail: the file may grow while it is
        sent, and only what was asked for goes). (status, decoded answer)."""
        try:
            size = os.path.getsize(src) - offset if length is None else length
            c = self._conn(timeout)
            c.putrequest("POST", f"{self.base}/api/v1/{self.door}/{path}")
            c.putheader("Authorization", "Bearer " + self.token)
            c.putheader("User-Agent", f"builderbot-agent/{AGENT_VERSION}")
            for k, v in self.headers.items():
                c.putheader(k, v)
            c.putheader("Content-Type", "application/octet-stream")
            c.putheader("Content-Length", str(size))
            c.endheaders()
            with open(src, "rb") as f:
                f.seek(offset)
                left = size
                while left > 0:
                    chunk = f.read(min(1 << 20, left))
                    if not chunk:
                        raise OSError(f"{src} is shorter than when it was measured")
                    c.send(chunk)
                    left -= len(chunk)
            r = c.getresponse()
            payload = r.read()
            c.close()
        except (OSError, http.client.HTTPException) as e:
            return 0, {"error": f"{type(e).__name__}: {e}"}
        try:
            return r.status, json.loads(payload) if payload else {}
        except ValueError:
            return r.status, {"error": payload[:200].decode("utf-8", "replace")}
