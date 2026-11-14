"""TLS for the node's relay port (R243): the terminals, the file explorer's
requests and a VM's screen crossed the LAN as plain websockets, so anybody
on the network read what was typed in a shell. Both ends keep the code they
had, written for a plain socket: the TLS is done here, in one thread per
connection that carries bytes between the encrypted socket and one end of
a local pair, and the other end of the pair is what the existing code is
handed.

The node's side makes itself a certificate once (cert: by the cryptography
library where the node has it, else openssl's command line, since ssl
cannot make one) and says its sha256 in the hello; the controller's side refuses any
certificate but that one (connect: the pin), so nobody between them can take
the TLS off. Shared by both ends: the controller loads this file from the
agent's package, as it does term.py.
"""
import hashlib
import os
import select
import socket
import ssl
import subprocess
import threading
import time

CHUNK = 65536
HIGH = 1 << 20          # held for a side that is not reading, before the other is not read either
HANDSHAKE_S = 15


# ---- a request good once -------------------------------------------------------
#
# A request to the relay is signed over what it asks and the second it was
# made, and is good for two minutes either side (the clocks' skew). Nothing
# remembered which had been used, so one read off the wire could be sent
# again inside that time. The controller now adds a value of its own making
# to what it signs, and the relay takes each signature once.
_USED = {}
_USED_LOCK = threading.Lock()


def subject(what, nonce):
    """What is signed: the request, and the controller's own value where it sent one."""
    return f"{what}.{nonce}" if nonce else str(what)


def once(sig, keep_s=600, now=None):
    """True the first time this signature is seen, False after: kept for
    longer than any signature is good for, then forgotten."""
    now = time.time() if now is None else now
    with _USED_LOCK:
        if len(_USED) > 4096:
            for k in [k for k, t in _USED.items() if t <= now]:
                del _USED[k]
        if _USED.get(sig, 0) > now:
            return False
        _USED[sig] = now + keep_s
        return True


class Refused(OSError):
    """The other end is not the node the controller pinned, or would not speak TLS."""


def fingerprint(cert_pem_path):
    """sha256:HEX of the certificate in a PEM file, as connect() compares it; "" where there is none."""
    try:
        with open(cert_pem_path, encoding="ascii") as f:
            der = ssl.PEM_cert_to_DER_cert(f.read())
    except (OSError, ValueError):
        return ""
    return "sha256:" + hashlib.sha256(der).hexdigest()


def _made_by_library(crt, key):
    """The pair written by the cryptography library, which a node has for
    sealing sign-ins: True when it did. Nothing to install, nothing to run."""
    try:
        import datetime
        from cryptography import x509
        from cryptography.hazmat.primitives import hashes, serialization
        from cryptography.hazmat.primitives.asymmetric import ec
        from cryptography.x509.oid import NameOID
    except ImportError:
        return False
    k = ec.generate_private_key(ec.SECP256R1())
    who = x509.Name([x509.NameAttribute(NameOID.COMMON_NAME, "aerieos-node-relay")])
    now = datetime.datetime.now(datetime.timezone.utc)
    c = (x509.CertificateBuilder().subject_name(who).issuer_name(who).public_key(k.public_key())
         .serial_number(x509.random_serial_number()).not_valid_before(now - datetime.timedelta(days=1))
         .not_valid_after(now + datetime.timedelta(days=3650)).sign(k, hashes.SHA256()))
    with open(key, "wb") as f:
        f.write(k.private_bytes(serialization.Encoding.PEM, serialization.PrivateFormat.PKCS8, serialization.NoEncryption()))
    with open(crt, "wb") as f:
        f.write(c.public_bytes(serialization.Encoding.PEM))
    return True


def _made_by_openssl(crt, key):
    """The pair written by openssl's command line, where the library is not on the machine."""
    p = subprocess.run(["openssl", "req", "-x509", "-newkey", "ec", "-pkeyopt", "ec_paramgen_curve:prime256v1",
                        "-nodes", "-days", "3650", "-subj", "/CN=aerieos-node-relay", "-keyout", key, "-out", crt],
                       capture_output=True, timeout=60, check=False)
    return p.returncode == 0


def cert(folder, name="relay"):
    """The node's own certificate and key in `folder` (made once, P-256,
    self-signed, the key 0600): (cert path, key path, fingerprint). Made by
    itself, with nothing for a person to do: by the cryptography library a
    node has for sealing sign-ins, else by openssl's command line. ("", "",
    "") only on a machine with neither, where the relay stays plain."""
    crt, key = os.path.join(folder, f"{name}.crt"), os.path.join(folder, f"{name}.key")
    if not (os.path.isfile(crt) and os.path.isfile(key) and fingerprint(crt)):
        try:
            os.makedirs(folder, exist_ok=True)
            old = os.umask(0o077)
            try:
                made = False
                for make in (_made_by_library, _made_by_openssl):
                    try:
                        made = make(crt + ".new", key + ".new")
                    except (OSError, ValueError, subprocess.SubprocessError):
                        made = False
                    if made:
                        break
            finally:
                os.umask(old)
            if not made:
                return "", "", ""
            os.replace(key + ".new", key)
            os.replace(crt + ".new", crt)
        except OSError:
            return "", "", ""
    fp = fingerprint(crt)
    return (crt, key, fp) if fp else ("", "", "")


def server_context(crt, key):
    ctx = ssl.SSLContext(ssl.PROTOCOL_TLS_SERVER)
    ctx.minimum_version = ssl.TLSVersion.TLSv1_2
    ctx.load_cert_chain(crt, key)
    return ctx


def looks_tls(conn, wait=10):
    """Whether the first byte waiting on `conn` opens a TLS handshake (0x16);
    False for a plain request, or nothing in time. Nothing is read off."""
    conn.settimeout(wait)
    try:
        first = conn.recv(1, socket.MSG_PEEK)
    except OSError:
        return False
    finally:
        conn.settimeout(None)
    return first == b"\x16"


def _plain_end(tls):
    """The plain end of a pair whose other end is pumped to and from `tls`."""
    ours, theirs = socket.socketpair()
    threading.Thread(target=_pump, args=(tls, theirs), name="relay-tls", daemon=True).start()
    return ours


def accept(conn, ctx):
    """A connection that opened with TLS, taken: the plain socket the relay's
    code is handed. OSError where the handshake fails."""
    conn.settimeout(HANDSHAKE_S)
    tls = ctx.wrap_socket(conn, server_side=True)
    return _plain_end(tls)


def connect(host, port, pin="", timeout=15):
    """A connection to a node's relay: over TLS where the node said it has a
    certificate (`pin`, its sha256), refused when the one presented is
    another; the plain socket itself where it said none. What comes back
    reads and writes as a plain socket either way."""
    up = socket.create_connection((host, port), timeout=timeout)
    if not pin:
        return up
    ctx = ssl.SSLContext(ssl.PROTOCOL_TLS_CLIENT)
    ctx.minimum_version = ssl.TLSVersion.TLSv1_2
    ctx.check_hostname = False
    ctx.verify_mode = ssl.CERT_NONE                # the pin below is the check: the certificate is the node's own
    try:
        up.settimeout(HANDSHAKE_S)
        tls = ctx.wrap_socket(up)
        seen = "sha256:" + hashlib.sha256(tls.getpeercert(True) or b"").hexdigest()
    except (OSError, ssl.SSLError) as e:
        up.close()
        raise Refused(f"the node's relay did not take TLS, though it said it does ({e})") from e
    if seen != pin:
        tls.close()
        raise Refused("the node's relay presented another certificate than the one the node reported: "
                      "something stands between the controller and the node")
    return _plain_end(tls)


def _pump(tls, plain):
    """Bytes both ways between the TLS socket and the plain end until either
    closes; what one side has not taken is held, to a limit, and then the
    other is not read. One thread does both directions: an SSL object is
    not for two threads at once."""
    to_tls, to_plain = bytearray(), bytearray()
    tls_open = plain_open = True
    try:
        tls.setblocking(False)
        plain.setblocking(False)
        while True:
            if not tls_open and not to_plain:
                break
            if not plain_open and not to_tls:
                break
            rd = []
            if tls_open and len(to_plain) < HIGH:
                rd.append(tls)
            if plain_open and len(to_tls) < HIGH:
                rd.append(plain)
            wr = ([tls] if to_tls else []) + ([plain] if to_plain else [])
            pending = tls_open and tls.pending() > 0 and len(to_plain) < HIGH
            r, w, _ = select.select(rd, wr, [], 0 if pending else 30)
            if tls in r or pending:
                try:
                    got = tls.recv(CHUNK)
                    if got:
                        to_plain += got
                    else:
                        tls_open = False
                except (ssl.SSLWantReadError, ssl.SSLWantWriteError):
                    pass
                except (OSError, ssl.SSLError):
                    tls_open = False
            if plain in r:
                try:
                    got = plain.recv(CHUNK)
                    if got:
                        to_tls += got
                    else:
                        plain_open = False
                except BlockingIOError:
                    pass
                except OSError:
                    plain_open = False
            if to_tls and (tls in w or not wr):
                try:
                    del to_tls[:tls.send(bytes(to_tls[:CHUNK]))]
                except (ssl.SSLWantReadError, ssl.SSLWantWriteError, BlockingIOError):
                    pass
                except (OSError, ssl.SSLError):
                    to_tls.clear()
                    tls_open = plain_open = False
            if to_plain and (plain in w or not wr):
                try:
                    del to_plain[:plain.send(bytes(to_plain[:CHUNK]))]
                except BlockingIOError:
                    pass
                except OSError:
                    to_plain.clear()
                    tls_open = plain_open = False
    finally:
        for s in (tls, plain):
            try:
                s.close()
            except OSError:
                pass
