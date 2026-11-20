"""The dashboard served over TLS where it can be had, http where it cannot
(R158 step 2; the operator, 27 Oct), and a node's channel over TLS under a
key it pinned, whatever a browser is served (R267 step 15).

One port, both ways: the listening socket peeks at a connection's first
byte and wraps the ones that open a TLS handshake (0x16) in a certificate
loaded here, and serves the rest as plain http, so a browser at http://...
is answered as it was while whoever opens with a handshake is answered
over TLS, and nothing of it is in the setup steps or the five places a
setting lands. The mode is a setting (Controller settings, Connection) and
says what a browser is meant to use: `http`, `self` (the install's own
certificate) or `acme` (a Let's Encrypt certificate for a hostname of the
controller's own, by a DNS-01 record through the Cloudflare API token,
since port 80 is not the dashboard's), with `""` reading as `self` where a
hostname is set and `http` otherwise.

The install's own certificate is there in every mode, http among them, so
the port always has something to answer a handshake with: made at the
first start for the names the controller knows itself by then (its
hostname setting, the tunnel's, the machine's name and addresses, else
`aerieos`), and remade a month before it ends or when a name is added.
Its KEY is made once and kept through every remake, so what a node pins
is the key (key_pin: the sha256 of its public half, as curl's
--pinnedpubkey reads it) and a remade certificate changes nothing for it.
In the `acme` mode the name's certificate answers a handshake that asks
for that name (SNI) and the install's own answers every other, so a node
that pinned the install's key at an address is not cut off when a
hostname is added.

Both pairs are kept under /config/tls, each certificate plain and each
private key sealed under the install key (listed on Controller, Keys) and
opened into a 0600 file under /run only while it is loaded: cert.pem and
key.pem are the install's own, acme-cert.pem and acme-key.pem the name's.
The agent channel and the terminal relay keep their own signatures either
way.
"""
import base64
import contextlib
import datetime
import json
import os
import socket
import ssl
import threading
import time
from pathlib import Path

STATE = None
seal = None
unseal = None
sealing = None
RUN_DIR = os.environ.get("BB_RUN_DIR") or "/run"
SELF_DAYS = 825                # Apple's limit for a certificate a browser will take
RENEW_BEFORE = 30 * 86400
SEALED = "bbseal:"
OWN, ACME = "self", "acme"     # the two pairs kept: the install's own, and the name's
FILES = {OWN: ("cert.pem", "key.pem"), ACME: ("acme-cert.pem", "acme-key.pem")}
PIN = "sha256//"               # a key's pin, as curl's --pinnedpubkey and the agent read it
_lock = threading.Lock()
_ctx = None                    # the ssl.SSLContext that answers a handshake, None when none loaded
_mode = "http"                 # the mode apply() last made so
_named = ()                    # the names the name's certificate answers, while it is loaded
_own_on = False                # whether the install's own pair is the one loaded to answer
_loaded = ""                   # the fingerprint _ctx was loaded from
_pending = {}                  # an ACME request going: {state, error, at}


def configure(*, state, seal_fn=None, unseal_fn=None, sealing_fn=None):
    globals().update(STATE=Path(state), seal=seal_fn, unseal=unseal_fn, sealing=sealing_fn)


def _dir():
    d = STATE / "tls"
    d.mkdir(parents=True, exist_ok=True, mode=0o700)
    return d


def _meta():
    try:
        d = json.loads((_dir() / "meta.json").read_text())
        return d if isinstance(d, dict) else {}
    except (OSError, ValueError):
        return {}


def _meta_save(d):
    tmp = _dir() / "meta.json.tmp"
    tmp.write_text(json.dumps(d))
    os.replace(tmp, _dir() / "meta.json")


def _key_text(kind=OWN):
    """A pair's private key, plain: opened where it was sealed."""
    try:
        raw = (_dir() / FILES[kind][1]).read_text().strip()
    except OSError:
        return ""
    if raw.startswith(SEALED):
        try:
            return unseal(base64.b64decode(raw[len(SEALED):])).decode() if unseal else ""
        except Exception:                                   # noqa: BLE001 (Locked: another key)
            return ""
    return raw


def _keep(cert_pem, key_pem, kind, names):
    """A pair kept under its own two files: the certificate plain, the key
    sealed where there is an install key."""
    d = _dir()
    (d / FILES[kind][0]).write_text(cert_pem.strip() + "\n")
    text = (SEALED + base64.b64encode(seal(key_pem.encode())).decode()) if (seal and sealing and sealing()) else key_pem
    fd = os.open(d / FILES[kind][1], os.O_WRONLY | os.O_CREAT | os.O_TRUNC, 0o600)
    with os.fdopen(fd, "w") as fh:
        fh.write(text + "\n")
    m = _meta()
    if kind == ACME:
        m["acme"] = {"names": list(names), "made": int(time.time())}
    else:
        m.update({"kind": OWN, "names": list(names), "made": int(time.time())})
    _meta_save(m)


def seal_all(again=False):
    """After the install key changed, or once there is one: each pair's
    private key sealed under today's (installkey's passes). Without it a
    key sealed under the install key before could no longer be opened once
    that one was let go, and the install's own, which a node pins, would
    have had to be made anew. How many were sealed."""
    if STATE is None or not (seal and sealing and sealing()):
        return 0
    n = 0
    with _lock:
        for kind in (OWN, ACME):
            path = _dir() / FILES[kind][1]
            try:
                raw = path.read_text().strip()
            except OSError:
                continue
            if not raw or (raw.startswith(SEALED) and not again):
                continue
            key = _key_text(kind)
            if not key:
                continue
            fd = os.open(str(path) + ".tmp", os.O_WRONLY | os.O_CREAT | os.O_TRUNC, 0o600)
            with os.fdopen(fd, "w") as fh:
                fh.write(SEALED + base64.b64encode(seal(key.encode())).decode() + "\n")
            os.replace(str(path) + ".tmp", path)
            n += 1
    return n


def _cert_text(kind=OWN):
    try:
        return (_dir() / FILES[kind][0]).read_text()
    except OSError:
        return ""


def _carry():
    """An install whose cert.pem held the name's certificate (one pair was
    kept, of whichever kind was in force) has it moved to the name's own two
    files, key and all as they are, so cert.pem and key.pem are free for
    the install's own pair, which apply() then makes."""
    m, d = _meta(), _dir()
    if m.get("kind") != ACME:
        return
    for was, now in zip(FILES[OWN], FILES[ACME], strict=True):
        if (d / was).exists():
            os.replace(d / was, d / now)
    m["acme"] = {"names": list(m.get("names") or []), "made": int(m.get("made") or 0)}
    m.update({"kind": OWN, "names": [], "made": 0})
    _meta_save(m)


def fingerprint(cert_pem=""):
    """The certificate's SHA-256 fingerprint, as the phone and the
    companion pin it (colon-separated hex), or ""."""
    pem = cert_pem or _cert_text()
    if "-----BEGIN CERTIFICATE-----" not in pem:
        return ""
    from cryptography import x509                           # noqa: PLC0415
    from cryptography.hazmat.primitives import hashes      # noqa: PLC0415
    first = pem.split("-----END CERTIFICATE-----")[0] + "-----END CERTIFICATE-----\n"
    digest = x509.load_pem_x509_certificate(first.encode()).fingerprint(hashes.SHA256())
    return ":".join(f"{b:02X}" for b in digest)


def key_pin_of(cert_pem):
    """The pin of the key a certificate carries: PIN and the base64 of the
    sha256 of its public half (the DER SubjectPublicKeyInfo), which is what
    curl's --pinnedpubkey takes and what the agent pins. It names the key
    and nothing else of the certificate, so it is the same for every
    certificate made with that key. "" for what is not a certificate."""
    if "-----BEGIN CERTIFICATE-----" not in (cert_pem or ""):
        return ""
    import hashlib                                          # noqa: PLC0415
    from cryptography import x509                           # noqa: PLC0415
    from cryptography.hazmat.primitives import serialization  # noqa: PLC0415
    first = cert_pem.split("-----END CERTIFICATE-----")[0] + "-----END CERTIFICATE-----\n"
    try:
        spki = x509.load_pem_x509_certificate(first.encode()).public_key().public_bytes(
            serialization.Encoding.DER, serialization.PublicFormat.SubjectPublicKeyInfo)
    except ValueError:
        return ""
    return PIN + base64.b64encode(hashlib.sha256(spki).digest()).decode()


def key_pin():
    """The pin of the install's own key, while the port answers a handshake
    with it: what an enrollment carries and a hello names, for a node to
    hold its channel to. "" while no certificate is loaded, so nothing is
    told to pin a key the port cannot answer under."""
    if _ctx is None or not _own_on:
        return ""
    with contextlib.suppress(Exception):                    # noqa: BLE001 (a damaged file: no pin)
        return key_pin_of(_cert_text())
    return ""


def _cert_facts(pem):
    from cryptography import x509                           # noqa: PLC0415
    first = pem.split("-----END CERTIFICATE-----")[0] + "-----END CERTIFICATE-----\n"
    c = x509.load_pem_x509_certificate(first.encode())
    try:
        alt = c.extensions.get_extension_for_class(x509.SubjectAlternativeName).value
        names = list(alt.get_values_for_type(x509.DNSName)) + [str(a) for a in alt.get_values_for_type(x509.IPAddress)]
    except x509.ExtensionNotFound:
        names = []
    return {"expires": int(c.not_valid_after_utc.timestamp()), "names": names,
            "issuer": ", ".join(a.value for a in c.issuer), "self": c.issuer == c.subject}


def self_signed(names, key_pem=""):
    """A self-signed pair for these names and the addresses among them,
    SELF_DAYS long: (cert PEM, key PEM). With `key_pem` the certificate is
    made over that key, which is how the install's own is remade: the key
    stays, so whoever pinned it sees a new certificate and the same key."""
    import ipaddress                                        # noqa: PLC0415
    from cryptography import x509                           # noqa: PLC0415
    from cryptography.hazmat.primitives import hashes, serialization  # noqa: PLC0415
    from cryptography.hazmat.primitives.asymmetric import ec  # noqa: PLC0415
    from cryptography.x509.oid import NameOID               # noqa: PLC0415
    names = [n.strip().lower() for n in names if n and n.strip()] or [DEFAULT_NAME]
    key = serialization.load_pem_private_key(key_pem.encode(), None) if key_pem else ec.generate_private_key(ec.SECP256R1())
    alts = []
    for n in names:
        try:
            alts.append(x509.IPAddress(ipaddress.ip_address(n)))
        except ValueError:
            alts.append(x509.DNSName(n))
    now = datetime.datetime.now(datetime.timezone.utc)
    subject = x509.Name([x509.NameAttribute(NameOID.COMMON_NAME, names[0][:64]),
                         x509.NameAttribute(NameOID.ORGANIZATION_NAME, "AerieOS")])
    cert = (x509.CertificateBuilder().subject_name(subject).issuer_name(subject).public_key(key.public_key())
            .serial_number(x509.random_serial_number()).not_valid_before(now - datetime.timedelta(days=1))
            .not_valid_after(now + datetime.timedelta(days=SELF_DAYS))
            .add_extension(x509.SubjectAlternativeName(alts), critical=False)
            .add_extension(x509.BasicConstraints(ca=False, path_length=None), critical=True)
            .sign(key, hashes.SHA256()))
    return (cert.public_bytes(serialization.Encoding.PEM).decode(),
            key.private_bytes(serialization.Encoding.PEM, serialization.PrivateFormat.PKCS8,
                              serialization.NoEncryption()).decode())


# What the install's own certificate names where the controller knows no
# name or address of its own: the pin is of the key, so a node asks for no
# name at all, and a browser warns whatever it says.
DEFAULT_NAME = "aerieos"


def mode_of(settings_get):
    """The mode in force from the settings: `""` reads as self where a
    hostname is set and http otherwise."""
    m = str(settings_get("tls_mode") or "").strip().lower()
    if m in ("http", "self", "acme"):
        return m
    return "self" if str(settings_get("tls_host") or "").strip() else "http"


def _shown(mode):
    """Which pair the Connection section speaks of: the name's where the
    mode is acme and one is kept, else the install's own."""
    return ACME if mode == ACME and _cert_text(ACME) else OWN


def status(settings_get):
    """What the Connection section and the Doctor show: the mode, whether a
    browser is served over TLS as the mode says (`on`: the port answers a
    node's handshake in every mode, which is not what this says), the kind,
    names, fingerprint and expiry of the certificate a browser meets, an
    ACME request going, and the pin of the install's own key."""
    mode = mode_of(settings_get)
    kind = _shown(mode)
    pem = _cert_text(kind)
    facts = {}
    if pem:
        with contextlib.suppress(Exception):                # noqa: BLE001 (a damaged file: no facts)
            facts = _cert_facts(pem)
    return {"mode": mode, "on": mode != "http" and _ctx is not None, "host": str(settings_get("tls_host") or "").strip(),
            "fingerprint": fingerprint(pem) if pem else "", "expires": facts.get("expires", 0),
            "names": facts.get("names", []), "issuer": facts.get("issuer", ""), "kind": kind if pem else "",
            "pending": dict(_pending), "key_sealed": _key_sealed(), "pin": key_pin()}


def _key_sealed():
    try:
        return (_dir() / FILES[OWN][1]).read_text().startswith(SEALED)
    except OSError:
        return False


def certificate_pem():
    """The certificate a browser meets, alone, for Download: what a phone
    or the companion pins. The name's in the acme mode once it is kept,
    else the install's own."""
    return _cert_text(_shown(_mode))


def _context_of(kind):
    """An SSLContext from one pair kept, its key opened into RUN_DIR only
    for the load; None when there is no such pair or it will not load."""
    pem, key = _cert_text(kind), _key_text(kind)
    if not pem or not key:
        return None
    ctx = ssl.create_default_context(ssl.Purpose.CLIENT_AUTH)
    ctx.minimum_version = ssl.TLSVersion.TLSv1_2
    kf = Path(RUN_DIR) / f"builderbot-tls-{os.getpid()}-{kind}.pem"
    try:
        fd = os.open(kf, os.O_WRONLY | os.O_CREAT | os.O_TRUNC, 0o600)
        with os.fdopen(fd, "w") as fh:
            fh.write(key)
        ctx.load_cert_chain(str(_dir() / FILES[kind][0]), str(kf))
    except (OSError, ssl.SSLError) as e:
        print(f"dashboard: tls: the {'name' if kind == ACME else 'install'}'s certificate did not load: {e}", flush=True)
        return None
    finally:
        with contextlib.suppress(OSError):
            kf.unlink()
    return ctx


def _load_context(mode=None):
    """What answers a handshake: the install's own pair, and in the acme
    mode the name's for a handshake that asks for one of its names (SNI),
    the install's own for every other. Where the install's own will not
    load the name's answers alone; None when neither does."""
    global _loaded, _named, _own_on
    mode = _mode if mode is None else mode
    own = _context_of(OWN)
    named = _context_of(ACME) if mode == ACME else None
    _named, _own_on = (), own is not None
    if named is not None:
        with contextlib.suppress(Exception):                # noqa: BLE001 (a damaged file: no names, so the install's own answers)
            _named = tuple(n.lower() for n in _cert_facts(_cert_text(ACME))["names"])
    if own is None:
        _loaded = fingerprint(_cert_text(ACME)) if named is not None else ""
        return named
    if named is not None and _named:
        names = _named

        def pick(sock, asked, _was):
            # The name's certificate for its name, the install's own otherwise.
            if asked and _answers(names, asked):
                sock.context = named
        own.sni_callback = pick
    _loaded = fingerprint(_cert_text())
    return own


def _answers(names, asked):
    """Whether a certificate for `names` answers the name a handshake asks
    for: the name itself, or a wildcard one label deep."""
    asked = str(asked).lower().rstrip(".")
    return any(n == asked or (n.startswith("*.") and "." in asked and asked.split(".", 1)[1] == n[2:]) for n in names)


def _own_kept(want):
    """The install's own pair made where there is none, and remade over the
    same key where it is not self-signed, is within RENEW_BEFORE of its
    end, or does not name every one of `want` (the names it has are kept:
    it only ever gains one). A key that cannot be opened (sealed under an
    install key this install no longer holds) is the one case a new key is
    made, said in the log: every node that pinned the old one is then one
    whose channel is refused until it is enrolled again."""
    pem, key = _cert_text(), _key_text()
    facts = {}
    if pem:
        with contextlib.suppress(Exception):                # noqa: BLE001
            facts = _cert_facts(pem)
    if key:
        try:
            from cryptography.hazmat.primitives import serialization  # noqa: PLC0415
            serialization.load_pem_private_key(key.encode(), None)
        except (ValueError, TypeError):
            key = ""
    if pem and not key:
        print("dashboard: tls: the install's own key cannot be opened, so a new one is made: a node that pinned the "
              "old one is refused its channel until it is enrolled again", flush=True)
    had = [n for n in facts.get("names", []) if n] if key and facts.get("self") else []
    names = list(dict.fromkeys(had + [n.strip().lower() for n in want if n and n.strip()])) or [DEFAULT_NAME]
    if (pem and key and facts.get("self") and facts.get("expires", 0) - time.time() >= RENEW_BEFORE
            and not set(names) - set(facts.get("names", []))):
        return
    cert, key = self_signed(names, key)
    _keep(cert, key, OWN, names)


def apply(settings_get, names=()):
    """The mode as the settings say, made so, and the install's own pair
    kept in every mode (_own_kept) for `names` (the hostname and the
    addresses the page is reached at), then what answers a handshake
    loaded. Returns status()."""
    global _ctx, _mode
    mode = mode_of(settings_get)
    with _lock:
        _carry()
        host = str(settings_get("tls_host") or "").strip()
        _own_kept([n for n in [host, *names] if n])
        _mode = mode
        _ctx = _load_context(mode)
    return status(settings_get)


def issue_acme(settings_get, directory, account_pem, present, cleanup, on_done=None):
    """A Let's Encrypt pair for the hostname, by DNS-01 (present and cleanup
    are nginxproxy's Cloudflare hooks), in the background; loaded when it
    comes, said in status().pending meanwhile."""
    host = str(settings_get("tls_host") or "").strip().lower()
    email = str(settings_get("tls_email") or "").strip()
    if not host:
        return {"error": "an ACME certificate is for a hostname: set the Connection section's hostname first"}
    if _pending.get("state") not in (None, "failed", "done"):
        return {"error": f"a certificate for {host} is being asked for already"}
    _pending.update({"state": "asking", "error": "", "at": int(time.time()), "host": host})

    def go():
        global _ctx
        import acme                                         # noqa: PLC0415
        try:
            client = acme.Client(directory, account_pem, contact=f"mailto:{email}" if email else "")
            _pending.update({"state": "ordering"})
            chain, key = client.issue([host], "dns-01", present, cleanup)
            with _lock:
                _keep(chain, key, ACME, [host])
                _ctx = _load_context()
            _pending.update({"state": "done", "error": ""})
        except Exception as e:                              # noqa: BLE001 (said, never silent)
            _pending.update({"state": "failed", "error": str(e)[:300]})
            print(f"dashboard: tls: acme for {host}: {e}", flush=True)
        if on_done:
            with contextlib.suppress(Exception):            # noqa: BLE001
                on_done(_pending.get("state") == "done", _pending.get("error", ""))
    threading.Thread(target=go, name="tls-acme", daemon=True).start()
    return {"ok": True, "started": True, "host": host}


def _due(kind):
    pem = _cert_text(kind)
    if not pem:
        return False
    try:
        return _cert_facts(pem)["expires"] - time.time() < RENEW_BEFORE
    except Exception:                                       # noqa: BLE001
        return False


def own_due():
    """Whether the install's own certificate is to be made or remade: none
    kept, or it ends within RENEW_BEFORE. apply() does it, in any mode."""
    return not _cert_text() or _due(OWN)


def renew_due():
    """Whether the name's certificate ends within RENEW_BEFORE: what Let's
    Encrypt is asked again for."""
    return _due(ACME)


def wrap(sock, peek_timeout=5.0):
    """A just-accepted socket, wrapped in TLS when its first byte opens a
    handshake and a context is loaded, else as it came: a browser or a node
    that speaks plain http is served plain http in every mode. A connection
    that sends nothing within peek_timeout is served plain, which a client
    that waits for a banner would have been anyway."""
    ctx = _ctx
    if ctx is None:
        return sock
    was = sock.gettimeout()
    try:
        sock.settimeout(peek_timeout)
        try:
            head = sock.recv(1, socket.MSG_PEEK)
        except (TimeoutError, OSError):
            head = b""
    finally:
        sock.settimeout(was)
    if head != b"\x16":
        return sock
    try:
        return ctx.wrap_socket(sock, server_side=True, do_handshake_on_connect=False)
    except (ssl.SSLError, OSError):
        return sock


class WrapOnItsThread:
    """A threading server's mixin: each connection is wrapped (wrap) on the
    thread that serves it (R228 step 3). wrap waits up to its peek_timeout
    for a first byte, and in get_request, on the one accept thread, a
    connection that sent nothing held every other behind it that long."""

    def process_request_thread(self, request, client_address):
        super().process_request_thread(wrap(request), client_address)


def over_tls(connection):
    return isinstance(connection, ssl.SSLSocket)
