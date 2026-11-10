"""Moving a controller to another home without losing its nodes (R90 step
12): from a container to another container on another host, from a
container to bare metal, and back.

Prepare to move on the old controller arms the move: a move token shown
once, a key derived from it kept here, and from then on every node hears
on its hello where the controller is going and a challenge of its own that
only a holder of the key answers. The move stays armed until it is
forgotten or it lands (R175: no life on the token, so a controller is
prepared days ahead and a node off for a weekend still hears it). The
bundle is packed fresh under that key each time it is downloaded or pulled,
so what moves is the state at the moment of moving: the whole state (the
JSON records, the database, the stores paths.py may have moved: project
snapshots, the git relay, the Git view's area, images), the canonical
repositories under the workspace when asked (left out when both homes mount
the same share), the deploy key, and what is sealed under the install key,
with the install key itself carried only when the person ticks it. The new
install's first run takes the bundle and the token, or the old controller's
address and the token and pulls the bundle from it, holds it to the version
gate (never onto an older build), restores it and restarts; each node knocks
on the new address when the old goes quiet, checks the answer and re-adopts
the controller by itself. The landing is told both ways under the move key
(the new controller tells the old, the old asks the new), and the old one
marks itself moved on either: read-only, saying where it went, and handing
a node that never heard the move its challenge in the same breath, so a
late node knocks and follows too. A node that outlived the old controller
is followed by hand with one line the new controller's Nodes page gives
(the agent's follow verb), never enrolled again.

The bundle's shape: a header line BBMOVE1, a JSON manifest (version, state
version, made at, the old address, what it carries, the sha256 of the
token, nothing secret, and a MAC under the bundle's key over the rest), a
newline, then the sealed tar.gz (ChaCha20-Poly1305 under HKDF(token)), whose
first entry, bundle.json, says the manifest carries that MAC.
"""
import base64
import contextlib
import errno
import hashlib
import hmac
import io
import json
import os
import re
import secrets
import shutil
import ssl
import tarfile
import tempfile
import threading
import time
import urllib.error
import urllib.parse
import urllib.request
import zlib

import stateversion
from pathlib import Path

STATE = Path("/config")
WORKSPACE = Path("/workspace")
SECRETS = ""
HEADER = b"BBMOVE1\n"
# A stick's backup (R161 step 4, backup.py): the same bundle sealed under a
# password's key, with its own header, opened by restore with the key.
BACKUP_HEADER = b"BBBACKUP1\n"
# What the state carries that is nobody's to move: logs, CI logs, the job
# trees, the apps fetched from the releases, this module's own output.
# The install key kept beside the state (an install with no secrets folder,
# lib/boot.sh install_key_made) is left out too: it travels only as the
# ticked install-key entry, as the one under the secrets does (B720).
LEAVE = {"os-draft", "logs", "ci-logs", "snapshots", "apps", "move", "csp-reports.json", "held.json", "clean-shutdown", "booted", "hold-next",
         ".install-key"}

_lock = threading.Lock()
write_json = None
seal = None
unseal = None
open_with = None
checkpoint = lambda: None     # noqa: E731 (configured: db.checkpoint)



# What a bundle is called: .aeriemove, and .bbmove from an install older than the name.
BUNDLE_SUFFIXES = (".aeriemove", ".bbmove")


def _key_beside_state(key, state_dir):
    """A carried install key where an install with no secrets folder keeps
    its own: the server hands this over to installkey.landed (B599)."""
    keydir = Path(state_dir) / ".install-key"
    keydir.mkdir(parents=True, exist_ok=True, mode=0o700)
    with open(keydir / "key", "wb") as f:
        f.write(key)
    os.chmod(keydir / "key", 0o600)


install_landed_key = _key_beside_state
state_version = lambda: 0           # noqa: E731
build_version = lambda: ""          # noqa: E731
install_key = lambda: b""           # noqa: E731
store_paths = lambda: {}            # noqa: E731
page_url = lambda: ""               # noqa: E731
node_ids = lambda: []               # noqa: E731
bare_metal = lambda: False          # noqa: E731
node_name = lambda nid: nid         # noqa: E731
audit = lambda who, what, detail: None    # noqa: E731
# The other controller, asked over HTTP(S): a wait of this many seconds.
PEER_TIMEOUT = 15
# How often the loop asks or tells (server._move_loop), and how long a
# fetch's nonce is good: a replayed fetch repacks the state for nobody.
TICK_S = 60
NONCE_LIFE = 600


def configure(*, state, workspace, secrets_dir, write_json_fn, seal_fn, open_fn, state_version_fn, build_version_fn,
              install_key_fn, store_paths_fn, page_url_fn, node_ids_fn, bare_metal_fn, node_name_fn=None, audit_fn=None):
    globals().update(STATE=Path(state), WORKSPACE=Path(workspace), SECRETS=secrets_dir or "", write_json=write_json_fn,
                     seal=seal_fn, open_with=open_fn, state_version=state_version_fn, build_version=build_version_fn,
                     install_key=install_key_fn, store_paths=store_paths_fn, page_url=page_url_fn, node_ids=node_ids_fn,
                     bare_metal=bare_metal_fn, node_name=node_name_fn or (lambda nid: nid),
                     audit=audit_fn or (lambda who, what, detail: None))


def _file():
    return STATE / "move.json"


def _load():
    try:
        with open(_file()) as f:
            d = json.load(f)
    except (OSError, ValueError):
        d = {}
    return d if isinstance(d, dict) else {}


def _save(d):
    write_json(_file(), d)


def new_token():
    return base64.urlsafe_b64encode(secrets.token_bytes(32)).decode().rstrip("=")


# The account the first page makes for a person moving a controller here,
# whose password is the move token, and which goes when the move lands.
SETUP_ACCOUNT = "setup"


# The move token the person gave on the first page, kept for the landing
# (the operator, 10 Nov: the walk asked for it twice). Sealed under the
# install key where there is one, since the walk's steps restart the
# controller; in memory where there is none yet. Dropped when the move
# lands or the setup ends.
SETUP_TOKEN_FILE = "move-setup-token.sealed"
_setup_token = {"tok": ""}


def keep_setup_token(token):
    if not token_shaped(token):
        return
    _setup_token["tok"] = token
    if seal is None:
        return
    with contextlib.suppress(Exception):     # noqa: BLE001 (no install key yet: memory alone)
        blob = seal(token.encode())
        f = STATE / SETUP_TOKEN_FILE
        tmp = f.with_name(f.name + ".new")
        with open(tmp, "wb") as g:
            g.write(blob)
        os.chmod(tmp, 0o600)
        os.replace(tmp, f)


def setup_token():
    """The token kept from the first page, or ""."""
    if _setup_token["tok"]:
        return _setup_token["tok"]
    if unseal is None:
        return ""
    try:
        tok = unseal((STATE / SETUP_TOKEN_FILE).read_bytes()).decode()
    except Exception:                        # noqa: BLE001 (missing, or under a key no longer here)
        return ""
    if token_shaped(tok):
        _setup_token["tok"] = tok
        return tok
    return ""


def drop_setup_token(state_dir=None):
    _setup_token["tok"] = ""
    with contextlib.suppress(OSError):
        (Path(state_dir or STATE) / SETUP_TOKEN_FILE).unlink()


def token_shaped(token):
    """Whether a string could be what new_token() printed. Only the shape: a
    move token is proved against its bundle when the move lands."""
    return bool(re.fullmatch(r"[A-Za-z0-9_-]{43}", str(token or "")))


def key_of(token):
    """The sealing key from the token: HKDF-SHA256 with a fixed info."""
    from cryptography.hazmat.primitives import hashes
    from cryptography.hazmat.primitives.kdf.hkdf import HKDF
    return HKDF(algorithm=hashes.SHA256(), length=32, salt=None, info=b"builderbot move v1").derive(token.encode())


def token_hash(token):
    return hashlib.sha256(b"builderbot move token\0" + token.encode()).hexdigest()


def challenge(key, nid):
    """What the old controller tells a node to expect, and the answer only
    a holder of the key gives (the new controller, once restored)."""
    return hmac.new(key, b"challenge\0" + str(nid).encode(), hashlib.sha256).hexdigest()


# The proofs the two controllers show each other (R175), each an HMAC under
# the move key over what it is for, so one is never good for another, and
# none of them is the token or opens the bundle.
def landed_proof(key, at):
    """The new controller's word that the bundle landed, at `at`."""
    return hmac.new(key, b"landed\0" + str(int(at)).encode(), hashlib.sha256).hexdigest()


def asked_proof(key, nonce):
    """The old controller's question, did it land here: fresh each time."""
    return hmac.new(key, b"asked\0" + str(nonce).encode(), hashlib.sha256).hexdigest()


def fetch_proof(key, nonce):
    """The new controller's right to pull the bundle, once per nonce."""
    return hmac.new(key, b"fetch\0" + str(nonce).encode(), hashlib.sha256).hexdigest()


def _key():
    try:
        return base64.b64decode(_load()["key_b64"])
    except (KeyError, ValueError):
        return b""


def armed():
    """An armed move on this, the old, controller: prepared and not
    forgotten, whether or not it has landed; never on the controller the
    state landed on (its record came with the bundle)."""
    d = _load()
    return bool(d.get("made_at") and d.get("key_b64") and not d.get("restored_at"))


def status():
    """What Controller settings shows: a move armed (where to, when, how
    many nodes have heard it, when the bundle was last packed and its
    size), or this controller moved (where to, how it learned), or nothing."""
    d = _load()
    out = {"prepared": False, "moved": False}
    if d.get("moved_to"):
        out.update(moved=True, to=d["moved_to"], at=d.get("moved_at", 0), how=d.get("moved_how", "pressed"),
                   landed_at=int(d.get("landed_at") or 0))
    if d.get("made_at") and not d.get("used") and not d.get("restored_at"):
        ids = list(node_ids())
        heard = [nid for nid in ids if nid in (d.get("told") or [])]
        out.update(prepared=True, to=d.get("to", ""), made_at=d["made_at"], heard=len(heard), nodes=len(ids),
                   bundle=d.get("bundle", ""), packed_at=int(d.get("packed_at") or 0), size=int(d.get("size") or 0),
                   repos=bool(d.get("repos")), carries_key=bool(d.get("carries_key")),
                   stores=d.get("stores") if isinstance(d.get("stores"), list) else sorted(k for k in (store_paths() or {}) if k not in STORES_OFF),
                   asked_at=int(d.get("asked_at") or 0), asked_error=d.get("asked_error", ""))
    return out


def bundle_path():
    d = _load()
    p = STATE / "move" / str(d.get("bundle") or "")
    return p if d.get("bundle") and p.is_file() else None


# Inside the state and never carried: what a landing or a reset set aside, and
# a landing's own spool and working folder.
NEVER_PACKED = (".moved-", ".move-", ".reset-")
# The landing's mark while the state is being swapped (B622), under the
# state folder and never packed; left behind only by a landing cut midway.
LANDING_MARK = ".move-landing.json"


def cut_landing(state_dir=None):
    """A landing cut midway, as its mark says: {at, stamp, aside, from}, or
    None. The mark is written before the state is swapped and taken off
    once the landing's record is written, so one found at a start names a
    state that is part old and part new (B622)."""
    try:
        d = json.loads(((state_dir or STATE) / LANDING_MARK).read_text())
    except (OSError, ValueError):
        return None
    return d if isinstance(d, dict) and d.get("stamp") else None


def cut_landing_rows():
    """The bell's row for a landing cut midway (B622): what is where, and
    that landing the same bundle with its token again finishes it."""
    c = cut_landing()
    if not c:
        return []
    when = time.strftime("%d %b %H:%M", time.localtime(int(c.get("at") or 0)))
    aside = os.path.basename(str(c.get("aside") or ""))
    return [{"kind": "move", "id": f"cut-{c['stamp']}", "bad": True, "key": f"movecut:{c['stamp']}",
             "why": f"A move's landing was cut midway on {when}: what is here is part of what was and part of the bundle, "
                    f"and what was here is kept whole in {aside} under the state folder. Land the same bundle again with its "
                    "token from Controller settings, Move a controller here, which finishes it; a first-run page shown "
                    "meanwhile is not a fresh install."}]


def _tar_tree(tar, src, arc, leave=()):
    src = Path(src)
    if not src.exists():
        return 0
    n = 0
    for p in sorted(src.rglob("*")):
        rel = p.relative_to(src)
        if rel.parts and (rel.parts[0] in leave or rel.parts[0].startswith(NEVER_PACKED)):
            continue
        # A link goes as a link, never followed (a repository's committed
        # links, node_modules/.bin): skipped, a moved repository showed them
        # deleted and a commit -a deleted them for good (B556). The restore
        # takes back only one that stays inside what it restores.
        if p.is_symlink():
            tar.add(str(p), arcname=f"{arc}/{rel.as_posix()}", recursive=False)
            n += 1
            continue
        if not (p.is_file() or p.is_dir()):
            continue
        if p.is_file():
            tar.add(str(p), arcname=f"{arc}/{rel.as_posix()}", recursive=False)
            n += 1
    return n


# The stores a bundle leaves out unless ticked (R175 step 7): what LEAVE
# leaves out of the state when they live under it.
STORES_OFF = {"logs", "job-snapshots"}
# What the secrets folder holds that is not the secrets: the install key's
# folder (installkey.py), carried only by its own tick (B619).
SECRETS_LEAVE = {"install-key"}


# How long a piece is measured for (B432: the workspace on a share took
# minutes and the section never drew): past it the size is "at least".
SIZE_BUDGET_S = 1.0
_sizes = {}      # path: (at, bytes, over), kept a while


def _size_of(src, leave=(), budget=None):
    """(bytes, over) under a tree, symlinks not followed, within
    SIZE_BUDGET_S: `over` says the walk stopped and the bytes are a floor.
    Kept for ten minutes per path."""
    src = Path(src)
    if not src.exists():
        return 0, False
    key = (str(src), tuple(sorted(leave)))
    got = _sizes.get(key)
    if got and time.time() - got[0] < 600:
        return got[1], got[2]
    n, over, t0 = 0, False, time.monotonic()
    for root, dirs, files in os.walk(src):
        rel = Path(root).relative_to(src)
        if rel.parts and rel.parts[0] in leave:
            dirs[:] = []
            continue
        for f in files:
            try:
                st = os.lstat(os.path.join(root, f))
            except OSError:
                continue
            if not os.path.islink(os.path.join(root, f)):
                n += st.st_size
        if time.monotonic() - t0 > (SIZE_BUDGET_S if budget is None else budget):
            over = True
            break
    _sizes[key] = (time.time(), n, over)
    return n, over


# A piece whose walk ran out of time is walked whole once more behind the
# page, so the next read says its size rather than a floor; one at a time.
SIZE_BEHIND_S = 120
_behind = threading.Lock()


def _measure_behind(jobs):
    def run():
        with _behind:
            for path, leave in jobs:
                _sizes.pop((str(Path(path)), tuple(sorted(leave))), None)
                with contextlib.suppress(OSError):
                    _size_of(path, leave, budget=SIZE_BEHIND_S)
    if not _behind.locked():
        threading.Thread(target=run, name="move-sizes", daemon=True).start()


def pieces():
    """What a bundle may carry, each with its size here, for the ticks on
    Controller settings (R175 step 7): the state always; each store kept
    outside it (on unless it is logs or the job trees); the repositories
    (off: both homes may mount the same share); the install key (off: the
    new home asks for it)."""
    # Each tree walked beside the others, so the page waits a walk's budget
    # once rather than once per piece (two seconds and more on a cold read).
    asked = []

    def piece(key, label, about, path, on, fixed=False, leave=()):
        row = {"key": key, "label": label, "about": about, "size": 0, "over": False, "on": on, "fixed": fixed}
        asked.append((row, path, tuple(leave)))
        return row
    out = [piece("state", "The state", "accounts, nodes, spaces, settings, the notebooks, the database, what is sealed", STATE, True, True, LEAVE)]
    for kind, path in (store_paths() or {}).items():
        if path and not str(path).startswith(str(STATE)):
            out.append(piece(f"store:{kind}", kind, str(path), path, kind not in STORES_OFF))
    if SECRETS and Path(SECRETS).is_dir():
        if os.access(SECRETS, os.R_OK | os.X_OK):
            out.append(piece("secrets", "The deploy key and the secrets", SECRETS, SECRETS, True, True, leave=SECRETS_LEAVE))
        else:
            # Root's alone on a machine of its own: the dashboard cannot
            # list it, and a walk of it carried nothing without a word (B728).
            out.append({"key": "secrets", "label": "The deploy key and the secrets", "size": 0, "on": False, "fixed": True,
                        "about": f"{SECRETS} is root's alone here, so a bundle carries none of it: copy its *.env files "
                                 "and ssh/ to the new home by hand, as root"})
    out.append(piece("repos", "The repositories", f"{WORKSPACE}: leave off when the new home reaches the same folder, a share both mount, or the disks the new machine adopts, where the Nodes page names it as the spaces folder", WORKSPACE, False))
    out.append({"key": "install_key", "label": "The install key", "about": "else the new home asks for it", "size": len(install_key() or b""), "on": False})
    from concurrent.futures import ThreadPoolExecutor
    with ThreadPoolExecutor(max_workers=max(1, len(asked))) as pool:
        got = list(pool.map(lambda a: _size_of(a[1], a[2]), asked))
    for (row, _, _), (size, over) in zip(asked, got, strict=True):
        row["size"], row["over"] = size, over
    behind = [(path, leave) for (row, path, leave) in asked if row["over"]]
    if behind:
        _measure_behind(behind)
    return out


# A bundle's body (format 2, B558): the gzipped tar sealed a PIECE at a
# time as it is made, each piece's seal over its number and whether it is the
# last, so no piece can be dropped, repeated, moved or cut off unseen, and
# neither end ever holds more than a piece. Format 1, the tar sealed whole in
# memory, is still opened.
FORMAT = 2
PIECE = 8 << 20


class _Sealer:
    """A file to write the tar into: each PIECE sealed under `key` and
    written to `f` as its length (4 bytes) and its seal."""

    def __init__(self, f, key):
        self.f, self.key, self.buf, self.n = f, key, bytearray(), 0

    def _out(self, data, last):
        blob = seal(self.n.to_bytes(8, "big") + (b"\1" if last else b"\0") + bytes(data), self.key)
        self.f.write(len(blob).to_bytes(4, "big") + blob)
        self.n += 1

    def write(self, b):
        self.buf += b
        while len(self.buf) >= PIECE:
            self._out(self.buf[:PIECE], False)
            del self.buf[:PIECE]
        return len(b)

    def finish(self):
        self._out(self.buf, True)
        self.buf = bytearray()


class _Opener:
    """The tar back out of a format 2 body, a piece at a time: each piece
    opened under `key` and held to its number; the body must end on the
    piece marked last, and nothing after it. ValueError otherwise."""

    def __init__(self, f, key):
        self.f, self.key, self.buf, self.n, self.done = f, key, b"", 0, False

    def _next(self):
        head = self.f.read(4)
        if len(head) < 4:
            raise ValueError("the bundle ends before its last piece")
        size = int.from_bytes(head, "big")
        if size > PIECE + 256:
            raise ValueError("a piece of the bundle is larger than any written")
        blob = self.f.read(size)
        try:
            data = open_with(self.key, blob)
        except Exception as e:                                     # noqa: BLE001 (Locked, or a damaged piece)
            raise ValueError("a piece of the bundle did not open") from e
        if len(data) < 9 or int.from_bytes(data[:8], "big") != self.n:
            raise ValueError("the bundle's pieces are out of order")
        self.n += 1
        self.done = data[8:9] == b"\1"
        if self.done and self.f.read(1):
            raise ValueError("the bundle goes on past its last piece")
        self.buf += data[9:]

    def close(self):
        self.f.close()

    def read(self, n=-1):
        while not self.done and (n < 0 or len(self.buf) < n):
            self._next()
        if n < 0:
            out, self.buf = self.buf, b""
        else:
            out, self.buf = self.buf[:n], self.buf[n:]
        return out


def split_form(src, content_type, file_field, dest, small=64 << 10):
    """A multipart form read from the file `src` a megabyte at a time (a
    landing's upload, B558: never whole in memory): the `file_field` part
    written to `dest`, each other part kept as text up to `small` bytes.
    Returns (fields, whether the file part came with any bytes); ValueError
    for a form it cannot read."""
    import re as _re
    m = _re.search(r'boundary="?([^";]+)"?', content_type or "")
    if not m:
        raise ValueError("the upload is not a form")
    delim = b"\r\n--" + m.group(1).encode()
    fields, got_file, buf = {}, False, b"\r\n"
    name, sink, out = None, None, None
    with open(src, "rb") as f, open(dest, "wb") as fout:
        def more():
            return f.read(1 << 20)
        state = "start"
        while True:
            if state in ("start", "body"):
                at = buf.find(delim)
                if at < 0:
                    keep = len(delim) + 4
                    if state == "body" and len(buf) > keep:
                        sink(buf[:-keep])
                        buf = buf[-keep:]
                    chunk = more()
                    if not chunk:
                        raise ValueError("the upload ends inside its form")
                    buf += chunk
                    continue
                if state == "body":
                    sink(buf[:at])
                    if out is not None:
                        # A handful of fields is all a landing's form has
                        # (B720): a form of thousands kept each in memory.
                        if name not in fields and len(fields) >= 16:
                            raise ValueError("the form has more fields than a landing's")
                        fields[name] = bytes(out).decode("utf-8", "replace").strip()
                buf = buf[at + len(delim):]
                while len(buf) < 2:
                    chunk = more()
                    if not chunk:
                        raise ValueError("the upload ends inside its form")
                    buf += chunk
                if buf[:2] == b"--":
                    return fields, got_file
                state = "head"
            else:
                at = buf.find(b"\r\n\r\n")
                if at < 0:
                    if len(buf) > 16 << 10:
                        raise ValueError("a part of the form has headers past 16 KiB")
                    chunk = more()
                    if not chunk:
                        raise ValueError("the upload ends inside its form")
                    buf += chunk
                    continue
                head = buf[:at].decode("utf-8", "replace")
                buf = buf[at + 4:]
                nm = _re.search(r'name="([^"]*)"', head)
                name = nm.group(1) if nm else ""
                if name == file_field:
                    out = None

                    def sink(b):
                        nonlocal got_file
                        if b:
                            got_file = True
                            fout.write(b)
                else:
                    out = bytearray()

                    def sink(b, out=out, name=name):
                        out.extend(b)
                        if len(out) > small:
                            raise ValueError(f"the form's {name or 'unnamed'} field is past {small} bytes")
                state = "body"


# The manifest line is plain, read before anything is opened, so it is held
# to the body by a MAC under the bundle's key, checked once the body is
# unpacked and before anything here changes (B724). A bundle that carries
# the mark below as its first sealed entry has one, so a MAC taken off the
# line is caught too; a bundle made before (no mark) lands as it did.
MANIFEST_MARK = "bundle.json"


def _manifest_mac(key, m):
    body = json.dumps({k: v for k, v in m.items() if k != "mac"}, sort_keys=True, separators=(",", ":")).encode()
    return hmac.new(hmac.new(key, b"builderbot bundle manifest", hashlib.sha256).digest(), body, hashlib.sha256).hexdigest()


def _manifest_held(path, key, work):
    """Why the manifest line is not the one the bundle was sealed with, or
    "" when it is (or the bundle is from before manifests were held)."""
    try:
        mark = json.loads((Path(work) / MANIFEST_MARK).read_text())
    except (OSError, ValueError):
        mark = None
    if not isinstance(mark, dict) or not mark.get("mac"):
        return ""
    try:
        with open(path, "rb") as f:
            f.readline()
            m = json.loads(f.readline())
    except (OSError, ValueError):
        m = None
    if not isinstance(m, dict) or not hmac.compare_digest(str(m.get("mac") or ""), _manifest_mac(key, m)):
        return "the bundle's outer details were changed after it was made (its kind, origin or version): nothing here was changed"
    return ""


# The manifest's room ahead of the body: the line is padded to it with
# spaces (whitespace JSON reads past), so the body is written once, in
# place, rather than to a file beside it and copied after, which needed
# twice the bundle's size free on the disk it was packed on.
MANIFEST_SLOT = 64 << 10


def write_bundle(dest, header, manifest, key, **pack_kw):
    """A bundle written to `dest` as it is packed, never whole in memory:
    `header`, the manifest line (`manifest(counts)`, a dict, its format
    set here), then the body sealed under `key` a piece at a time. The
    manifest names the body's counts, so its line is a slot of spaces
    filled in once the body is written. Returns (manifest, counts)."""
    dest = Path(dest)
    # The database's log folded into it first, so the copy is not torn (B601).
    with contextlib.suppress(Exception):
        checkpoint()
    with open(dest, "wb") as out:
        out.write(header)
        out.write(b" " * (MANIFEST_SLOT - 1) + b"\n")
        sealer = _Sealer(out, key)
        with tarfile.open(fileobj=sealer, mode="w|gz") as tar:
            mark = json.dumps({"mac": True}).encode()
            info = tarfile.TarInfo(MANIFEST_MARK)
            info.size, info.mtime, info.mode = len(mark), int(time.time()), 0o600
            tar.addfile(info, io.BytesIO(mark))
            counts = _pack_into(tar, **pack_kw)
        sealer.finish()
        m = dict(manifest(counts), format=FORMAT)
        m["mac"] = _manifest_mac(key, m)
        line = json.dumps(m).encode()
        if len(line) >= MANIFEST_SLOT:
            raise OSError(f"the bundle's details ran past their {MANIFEST_SLOT >> 10} KiB")
        out.seek(len(header))
        out.write(line + b" " * (MANIFEST_SLOT - 1 - len(line)))
    return m, counts


def pack(repos=False, carry_key=False, stores=None):
    """The tree a move or a backup carries, as one gzipped tar in memory (a
    small tree, as the tests make; a bundle is write_bundle's, streamed).
    Returns (bytes, counts)."""
    buf = io.BytesIO()
    with tarfile.open(fileobj=buf, mode="w:gz") as tar:
        counts = _pack_into(tar, repos=repos, carry_key=carry_key, stores=stores)
    return buf.getvalue(), counts


DB_FILES = ("builderbot.db", "builderbot.db-wal", "builderbot.db-shm", "builderbot.db-journal")


def _db_snapshot():
    """A consistent copy of the state's database, by SQLite's backup, in a
    file under the state the walk never packs (.move-); None where there is
    no database there or it could not be read, and the file goes as it is."""
    src = STATE / DB_FILES[0]
    if not src.is_file():
        return None
    import sqlite3
    dest = STATE / f".move-db-{os.getpid()}-{threading.get_ident()}"
    try:
        a = sqlite3.connect(f"file:{src}?mode=ro", uri=True, timeout=30)
        try:
            b = sqlite3.connect(str(dest))
            try:
                a.backup(b)
            finally:
                b.close()
        finally:
            a.close()
        os.chmod(dest, 0o600)
        return dest
    except (sqlite3.Error, OSError):
        dest.unlink(missing_ok=True)
        return None


def _pack_into(tar, repos=False, carry_key=False, stores=None):
    """Into `tar`, the tree a move or a backup carries: the state without
    its logs and job trees, the stores kept outside it (`stores` names the
    kinds; None is every kind but STORES_OFF), the repositories when asked,
    the secrets, the install key when asked. Returns the counts."""
    counts = {}
    # The database by SQLite's own backup, never as a file copy (B720):
    # the server writes it all the while (its minute's fold among it), and
    # a copy read across a write is torn. The file and its log are left out
    # of the walk, the snapshot put in their place.
    # ...and the files beside it at that same moment: no state file lands
    # while the database is copied and the state is walked (statefile.frozen),
    # so the bundle is not an account from before a change and its secrets
    # from after it.
    import statefile                                        # noqa: PLC0415
    with statefile.frozen():
        snap = _db_snapshot()
        try:
            counts["state"] = _tar_tree(tar, STATE, "state", leave=LEAVE | (set(DB_FILES) if snap else set()))
            if snap:
                tar.add(str(snap), arcname=f"state/{DB_FILES[0]}", recursive=False)
        finally:
            if snap:
                snap.unlink(missing_ok=True)
    for kind, path in (store_paths() or {}).items():
        if path and not str(path).startswith(str(STATE)) and (kind in stores if stores is not None else kind not in STORES_OFF):
            counts[kind] = _tar_tree(tar, path, f"stores/{kind}")
    if repos:
        counts["repos"] = _tar_tree(tar, WORKSPACE, "workspace")
    # The install key's own folder under the secrets (lib/boot.sh
    # install_key_made) stays out: the key travels only as the entry below,
    # when ticked (B619).
    if SECRETS and Path(SECRETS).is_dir():
        counts["secrets"] = _tar_tree(tar, SECRETS, "secrets", leave=SECRETS_LEAVE)
    if carry_key:
        k = install_key() or b""
        if k:
            info = tarfile.TarInfo("install-key")
            info.size = len(k)
            info.mtime = int(time.time())
            tar.addfile(info, io.BytesIO(k))
            counts["install_key"] = 1
    return counts


def prepare(principal, to, repos=False, carry_key=False, stores=None):
    """The move armed: a new token, returned once and never kept, its key
    kept here, the nodes told from the next hello, and a first bundle
    packed under it (repacked fresh by each download or pull). `stores`
    names the store kinds it carries (None: every kind but STORES_OFF)."""
    to = str(to or "").strip().rstrip("/")
    if to and not to.startswith(("http://", "https://")):
        return {"error": "the new home's address is where its page will be reached, as http:// or https://"}
    if _load().get("moved_to"):
        return {"error": "this controller has moved already; nothing more leaves here"}
    token = new_token()
    key = key_of(token)
    made_at = int(time.time())
    # The record first, so the bundle carries it: the new home answers the
    # nodes' knocks from the key kept here, under the state that moved.
    with _lock:
        d = _load()
        for old in (STATE / "move").glob("*"):
            if old.suffix not in BUNDLE_SUFFIXES:
                continue
            old.unlink(missing_ok=True)
        d = {k: v for k, v in d.items() if k in ("moved_to", "moved_at")}
        d.update(made_at=made_at, to=to, bundle="", size=0, used=False, repos=bool(repos), carries_key=bool(carry_key),
                 stores=sorted(str(k) for k in stores) if stores is not None else None,
                 token_hash=token_hash(token), key_b64=base64.b64encode(key).decode(), by=str(principal)[:80])
        _save(d)
    r = pack_bundle()
    if r.get("error"):
        return r
    return {"ok": True, "token": token, "bundle": r["bundle"], "size": r["size"], "counts": r["counts"], "to": to, "made_at": made_at}


def far_nodes(to, nodes):
    """The nodes that cannot follow a move to `to`: a new home named by an
    address of the local network, and a node that dials in from outside it
    (the operator, 10 Nov: a node on a server elsewhere stayed quiet after a
    move to a LAN address), unless it dials a public hostname, which it is
    told to keep (node_url). `nodes` is [(name, address, hostname)]; the
    names."""
    import ipaddress
    host = urllib.parse.urlsplit(str(to or "")).hostname or ""
    try:
        here = ipaddress.ip_address(host)
    except ValueError:
        return []
    if not (here.is_private or here.is_loopback or here.is_link_local):
        return []
    out = []
    for name, addr, *host in nodes:
        if host and host[0]:
            continue
        try:
            a = ipaddress.ip_address(str(addr or "").split("%")[0])
        except ValueError:
            continue
        if a.is_global:
            out.append(str(name))
    return out


def far_said(far, to):
    one = len(far) == 1
    return (f"{', '.join(far)} {'dials' if one else 'dial'} in from outside this network at no public hostname of this controller's, so {to}, "
            f"an address of the local network, cannot be reached from {'it' if one else 'them'}: Forget this move and prepare it again with an "
            f"address {'it reaches' if one else 'they reach'}, or set Reach from outside on the Network page and enroll {'it' if one else 'them'} "
            f"again at that hostname with the Enroll script on {'its' if one else 'each'} row before you move")


def pack_bundle():
    """The bundle packed fresh under the armed move's key, written under
    STATE/move in place of the one before (R175: what moves is the state
    at the moment of moving, not at Prepare). {ok, bundle, size, counts}
    or {error}."""
    d = _load()
    key = _key()
    if not d.get("made_at") or not key or d.get("restored_at"):
        return {"error": "no move is prepared"}
    out_dir = STATE / "move"
    out_dir.mkdir(parents=True, exist_ok=True)
    # Named to the millisecond: two packs in one second are two bundles.
    stamp = time.strftime("%Y%m%d-%H%M%S") + f"-{int(time.time() * 1000) % 1000:03d}"
    # .aeriemove since the name moved; a .bbmove an older install packed
    # still lands (only its contents are read), and is cleaned up as one.
    name = f"aerieos-move-{stamp}.aeriemove"
    tmp = out_dir / (name + ".partial")

    def manifest_of(counts):
        return {"version": build_version(), "state_version": int(state_version() or 0), "made_at": int(d["made_at"]),
                "packed_at": int(time.time()), "from": page_url(), "to": d.get("to", ""), "repos": bool(d.get("repos")),
                "carries_key": bool(d.get("carries_key") and counts.get("install_key")),
                "nodes": list(node_ids()), "bare_metal": bool(bare_metal()), "counts": counts, "token_hash": d.get("token_hash", "")}
    # The bundle before goes first: it is the state as it was then, never
    # what moves, and kept while the new one was packed it took its room
    # twice over on a disk the bundle may only just fit.
    for old in out_dir.glob("*"):
        if old.suffix in BUNDLE_SUFFIXES or old.name.endswith((".partial", ".body")):
            old.unlink(missing_ok=True)
    try:
        manifest, counts = write_bundle(tmp, HEADER, manifest_of, key, repos=bool(d.get("repos")), carry_key=bool(d.get("carries_key")),
                                        stores=set(d["stores"]) if isinstance(d.get("stores"), list) else None)
        os.replace(tmp, out_dir / name)
        with _lock:
            d = _load()
            d.update(bundle=name, size=(out_dir / name).stat().st_size, packed_at=manifest["packed_at"], carries_key=manifest["carries_key"])
            _save(d)
    except OSError as e:
        tmp.unlink(missing_ok=True)
        (out_dir / name).unlink(missing_ok=True)
        return {"error": f"the bundle could not be written: {_no_room_said(e, out_dir, bool(d.get('repos')))}"}
    return {"ok": True, "bundle": name, "size": d["size"], "counts": counts}


def _no_room_said(e, where, repos):
    """An error packing a bundle as a sentence; a full disk said with
    where it is and what to do about it."""
    if getattr(e, "errno", None) != errno.ENOSPC:
        return str(e.strerror or e)
    try:
        free = f"{shutil.disk_usage(str(where)).free / 1e9:.1f} GB"
    except OSError:
        free = "too little"
    return (f"the disk holding this controller's state ({where}) filled up: {free} free once the unfinished bundle was removed. "
            + ("Free room there, or prepare the move again without the repositories, which then move by naming their folder on the new home"
               if repos else "Free room there and try again"))


# A backup of the controller under a token of its own (the operator, 6 Nov):
# kept here under a name never packed, the newest alone.
BACKUP_DIR = ".move-backup"
BACKUP_NAME = re.compile(r"aerieos-backup-[0-9-]+\.aeriemove")


def backup_bundle(principal, repos=False, carry_key=False, stores=None):
    """A copy of the controller to keep (the operator, 6 Nov): the state,
    the stores ticked, the spaces' repositories and the install key when
    ticked, packed as a move's bundle under a new token returned once and
    never kept, landed later on a controller being set up as a move is. No
    move is armed and no node told; landed, it never tells this controller,
    and nodes still there follow by the line the new Nodes page gives.
    {ok, token, bundle, size, counts} or {error}."""
    if _load().get("moved_to"):
        return {"error": "this controller has moved already; nothing more leaves here"}
    token = new_token()
    key = key_of(token)
    out_dir = STATE / BACKUP_DIR
    out_dir.mkdir(parents=True, exist_ok=True, mode=0o700)
    stamp = time.strftime("%Y%m%d-%H%M%S") + f"-{int(time.time() * 1000) % 1000:03d}"
    name = f"aerieos-backup-{stamp}.aeriemove"
    tmp = out_dir / (name + ".partial")
    now = int(time.time())

    def manifest_of(counts):
        return {"kind": "token-backup", "version": build_version(), "state_version": int(state_version() or 0), "made_at": now,
                "packed_at": now, "from": page_url(), "to": "", "repos": bool(repos),
                "carries_key": bool(carry_key and counts.get("install_key")), "nodes": list(node_ids()),
                "bare_metal": bool(bare_metal()), "counts": counts, "token_hash": token_hash(token), "by": str(principal)[:80]}
    try:
        manifest, counts = write_bundle(tmp, HEADER, manifest_of, key, repos=bool(repos), carry_key=bool(carry_key),
                                        stores=set(stores) if stores is not None else None)
        os.replace(tmp, out_dir / name)
    except OSError as e:
        tmp.unlink(missing_ok=True)
        return {"error": f"the backup could not be written: {_no_room_said(e, out_dir, bool(repos))}"}
    for old in out_dir.glob("*"):
        if old.name != name:
            old.unlink(missing_ok=True)
    return {"ok": True, "token": token, "bundle": name, "size": (out_dir / name).stat().st_size, "counts": counts}


def backup_path(name):
    """The backup's file by its name, or None."""
    p = STATE / BACKUP_DIR / str(name or "")
    return p if BACKUP_NAME.fullmatch(str(name or "")) and p.is_file() else None


def forget(principal):
    """The armed move withdrawn: the bundle gone, the nodes told nothing more."""
    with _lock:
        d = _load()
        if not d.get("made_at") or d.get("restored_at"):
            return {"error": "no move is prepared"}
        if d.get("moved_to"):
            return {"error": "this controller has moved; the move is not withdrawn after it landed"}
        for old in (STATE / "move").glob("*"):
            if old.suffix not in BUNDLE_SUFFIXES:
                continue
            old.unlink(missing_ok=True)
        d = {k: v for k, v in d.items() if k in ("moved_to", "moved_at")}
        _save(d)
    return {"ok": True}


# The public hostname a node dials the controller at through the home tunnel
# (nodes.tunnel_host), "" for one on the network: handed in by the server.
tunnel_host = lambda nid: ""  # noqa: E731


def node_url(nid, here):
    """Where a node reaches the controller after a move: the public hostname
    it was enrolled at, which the tunnel's settings carry to the new home,
    else `here` (the operator, 10 Nov: a node on a server elsewhere could
    never follow a move to a local address)."""
    h = tunnel_host(nid)
    return f"https://{h}" if h else here


def for_node(nid):
    """What a node's hello carries while a move is armed, and what the old
    controller's "moved" answer carries after (R175: a node that never
    heard the move hears it then and knocks): the new address and that
    node's challenge; {} with no move armed, and {} on the controller the
    move landed on, whose record came with the bundle."""
    d = _load()
    if not d.get("made_at") or not d.get("to") or d.get("restored_at"):
        return {}
    key = _key()
    if not key:
        return {}
    if nid not in (d.get("told") or []):
        # Which nodes have heard it, for the section's count: written once
        # per node, not on every hello.
        with _lock:
            d = _load()
            told = [x for x in (d.get("told") or []) if isinstance(x, str)]
            if nid not in told and d.get("made_at"):
                d["told"] = told + [str(nid)]
                _save(d)
    return {"url": node_url(nid, d.get("moved_to") or d["to"]), "expect": challenge(key, nid)}


def answer_for(nid):
    """The new controller's answer to a node's knock, once the bundle is
    restored here (the record came with it): the challenge the old
    controller told that node to expect, which only a holder of the move
    key can say back; "" when no move landed here."""
    d = _load()
    if not d.get("key_b64") or not d.get("restored_at"):
        return ""
    try:
        key = base64.b64decode(d["key_b64"])
    except ValueError:
        return ""
    return challenge(key, nid)


def mark_moved(to, how="pressed", landed_at=0):
    """The old controller, once the new one is up: read-only, saying where,
    and how it learned (pressed, told by the new controller, or asked)."""
    with _lock:
        d = _load()
        d.update(moved_to=str(to or "")[:200], moved_at=int(time.time()), used=True, moved_how=how,
                 landed_at=int(landed_at or d.get("landed_at") or 0))
        _save(d)
    return {"ok": True, "to": d["moved_to"], "how": how}


def moved_to():
    return str(_load().get("moved_to") or "")


# ---- the landing, told both ways (R175 step 4) --------------------------------

def take_landing(req):
    """POST /api/v1/move/landed on the old controller: the new controller's
    word that the bundle landed, {hash, at, proof, here}. The hash names
    the armed move, the proof is HMAC(key, landed\0at); right, this
    controller marks itself moved to the address it was prepared for (or
    the one the new controller says it is at, when none was named).
    (payload, status)."""
    d = _load()
    if not armed():
        return {"error": "no move is prepared here"}, 404
    if d.get("moved_to"):
        return {"ok": True, "moved": True, "to": d["moved_to"]}, 200
    if str(req.get("hash") or "") != str(d.get("token_hash") or ""):
        return {"error": "not this controller's move"}, 403
    try:
        at = int(req.get("at") or 0)
    except (TypeError, ValueError):
        at = 0
    want = landed_proof(_key(), at)
    if not at or not hmac.compare_digest(str(req.get("proof") or ""), want):
        return {"error": "the proof does not verify"}, 403
    to = d.get("to") or str(req.get("here") or "").strip().rstrip("/")[:200]
    r = mark_moved(to, how="told", landed_at=at)
    audit("controller", "moved-by-landing", {"to": to, "landed_at": at})
    return {"ok": True, "moved": True, "to": r["to"]}, 200


def answer_asked(q):
    """GET /api/v1/move/landed?hash=..&nonce=..&proof=.. on the new
    controller: the old controller asking whether its bundle landed here.
    The proof is HMAC(key, asked\0nonce) under the key that came with the
    bundle. (payload, status)."""
    d = _load()
    if not d.get("restored_at") or not d.get("key_b64"):
        return {"error": "no move landed here"}, 404
    if str(q.get("hash") or "") != str(d.get("token_hash") or ""):
        return {"error": "not this controller's move"}, 403
    nonce = str(q.get("nonce") or "")[:64]
    if not nonce or not hmac.compare_digest(str(q.get("proof") or ""), asked_proof(_key(), nonce)):
        return {"error": "the proof does not verify"}, 403
    return {"ok": True, "landed_at": int(d["restored_at"]), "here": page_url() or d.get("to", "")}, 200


def _peer_ctx():
    """TLS to the other controller: not verified, since neither knows the
    other's certificate; what is said either way is an HMAC under the move
    key, which a listener can neither forge nor use, and the bundle is
    sealed. Said in docs/install.md."""
    ctx = ssl.create_default_context()
    ctx.check_hostname = False
    ctx.verify_mode = ssl.CERT_NONE
    return ctx


def _peer_json(url, body=None, timeout=None):
    """One call to the other controller: (status, dict)."""
    req = urllib.request.Request(url, data=json.dumps(body).encode() if body is not None else None,
                                 method="POST" if body is not None else "GET",
                                 headers={"User-Agent": "AerieOS", **({"Content-Type": "application/json"} if body is not None else {})})
    try:
        with urllib.request.urlopen(req, timeout=timeout or PEER_TIMEOUT, context=_peer_ctx()) as r:
            raw = r.read()
            st = r.status
    except urllib.error.HTTPError as e:
        raw, st = e.read(), e.code
    except (OSError, ValueError) as e:
        return 0, {"error": f"{type(e).__name__}: {e}"}
    try:
        j = json.loads(raw) if raw else {}
    except ValueError:
        j = {"error": raw[:200].decode("utf-8", "replace")}
    return st, j if isinstance(j, dict) else {}


def ask_new(force=False):
    """The old controller, armed and not yet marked moved, asking the new
    address whether the bundle landed there; marked moved on a verified
    yes. Once per TICK_S unless forced. True when it learned so."""
    d = _load()
    if not armed() or d.get("moved_to") or not d.get("to"):
        return False
    now = int(time.time())
    if not force and now - int(d.get("asked_at") or 0) < TICK_S:
        return False
    nonce = secrets.token_hex(16)
    q = urllib.parse.urlencode({"hash": d.get("token_hash", ""), "nonce": nonce, "proof": asked_proof(_key(), nonce)})
    st, r = _peer_json(f"{d['to'].rstrip('/')}/api/v1/move/landed?{q}")
    with _lock:
        d = _load()
        d.update(asked_at=now, asked_error="" if st == 200 or st == 404 else (r.get("error") or f"answered {st}"))
        _save(d)
    if st == 200 and r.get("ok") and r.get("landed_at"):
        mark_moved(d.get("to") or r.get("here", ""), how="asked", landed_at=r["landed_at"])
        audit("controller", "moved-by-asking", {"to": d.get("to", ""), "landed_at": r["landed_at"]})
        return True
    return False


def tell_old(force=False):
    """The new controller, once the bundle landed here, telling the old
    address so until it answers (200: taken; 404: no move armed there any
    more, which is an answer too). Once per TICK_S unless forced. True
    once it has been told."""
    d = _load()
    if not d.get("restored_at") or d.get("told_at") or not d.get("came_from"):
        return bool(d.get("told_at"))
    now = int(time.time())
    if not force and now - int(d.get("tell_tried_at") or 0) < TICK_S:
        return False
    body = {"hash": d.get("token_hash", ""), "at": int(d["restored_at"]), "proof": landed_proof(_key(), int(d["restored_at"])),
            "here": page_url() or d.get("to", "")}
    st, r = _peer_json(f"{str(d['came_from']).rstrip('/')}/api/v1/move/landed", body)
    with _lock:
        d = _load()
        d["tell_tried_at"] = now
        if st in (200, 404):
            d["told_at"] = now
            d["told_how"] = "taken" if st == 200 else "no move armed there"
        else:
            d["tell_error"] = r.get("error") or (f"answered {st}" if st else "no answer")
        _save(d)
    return st in (200, 404)


def tick():
    """The loop's pass (server._move_loop): the old side asks, the new side
    tells, whichever this controller is."""
    ask_new()
    tell_old()


# ---- the pull (R175 step 5) ------------------------------------------------------

def serve_fetch(q):
    """GET /api/v1/move/bundle?hash=..&nonce=..&proof=.. on the old
    controller: the new install pulling the bundle with a proof derived
    from the token (HMAC(key, fetch\0nonce)), the bundle packed fresh for
    it; a nonce is good once and for NONCE_LIFE. (path, "") or ("", why,
    status)."""
    d = _load()
    if not armed():
        return "", "no move is prepared here", 404
    if d.get("moved_to"):
        return "", "this controller has moved already", 410
    if str(q.get("hash") or "") != str(d.get("token_hash") or ""):
        return "", "not this controller's move", 403
    nonce = str(q.get("nonce") or "")[:64]
    if not nonce or not hmac.compare_digest(str(q.get("proof") or ""), fetch_proof(_key(), nonce)):
        return "", "the proof does not verify", 403
    now = int(time.time())
    with _lock:
        d = _load()
        used = {k: v for k, v in (d.get("fetch_nonces") or {}).items() if now - int(v) < NONCE_LIFE}
        if nonce in used:
            return "", "that proof was used already", 403
        used[nonce] = now
        d["fetch_nonces"] = used
        _save(d)
    r = pack_bundle()
    if r.get("error"):
        return "", r["error"], 500
    audit("controller", "move-bundle-pulled", {"bundle": r["bundle"], "size": r["size"]})
    return str(STATE / "move" / r["bundle"]), "", 200


def room_for(size, where):
    """"" when `where` has room for a bundle of `size` bytes and what it
    unpacks to (twice it, and a little), or why not (B588: a stick before a
    system pool lands on its own small partition)."""
    try:
        free = shutil.disk_usage(str(where)).free
    except OSError:
        return ""
    need = 2 * int(size or 0) + (256 << 20)
    if free >= need:
        return ""
    gb = lambda n: f"{n / 1e9:.1f} GB"  # noqa: E731
    return (f"this machine has {gb(free)} free where a move lands, and the bundle needs about {gb(need)} (it, and what it unpacks to): "
            "a stick keeps that on itself until a system pool is named. Make the bundle without the repositories, land it, then name "
            "the folder they are in as the spaces folder on the Nodes page")


def fetch_bundle(old_url, token, dest):
    """The new install pulling the bundle from the old controller into
    `dest`, under the proof the token derives. "" or why."""
    old_url = str(old_url or "").strip().rstrip("/")
    if not old_url.startswith(("http://", "https://")):
        return "the old controller's address is where its page is reached, as http:// or https://"
    key = key_of(token)
    nonce = secrets.token_hex(16)
    q = urllib.parse.urlencode({"hash": token_hash(token), "nonce": nonce, "proof": fetch_proof(key, nonce)})
    req = urllib.request.Request(f"{old_url}/api/v1/move/bundle?{q}", headers={"User-Agent": "AerieOS"})
    try:
        with urllib.request.urlopen(req, timeout=3600, context=_peer_ctx()) as r:
            why = room_for(int(r.headers.get("Content-Length") or 0), Path(dest).parent)
            if why:
                return why
            # Never past what an upload may be, nor what room there is: an
            # answer with no length was read without end (B720).
            most = 16 << 30
            got = 0
            with open(dest, "wb") as f:
                while True:
                    chunk = r.read(1 << 20)
                    if not chunk:
                        break
                    got += len(chunk)
                    if got > most:
                        return "the old controller's answer ran past 16 GB, more than any bundle: stopped"
                    if got % (256 << 20) < len(chunk) and room_for(1 << 30, Path(dest).parent):
                        return "the disk here is filling up with the old controller's answer: stopped"
                    f.write(chunk)
    except urllib.error.HTTPError as e:
        try:
            why = json.loads(e.read()).get("error") or f"answered {e.code}"
        except (ValueError, AttributeError):
            why = f"answered {e.code}"
        return f"the old controller did not hand the bundle over: {why}"
    except (OSError, ValueError) as e:
        return f"the old controller at {old_url} did not answer: {type(e).__name__}: {e}"
    return ""


# ---- the nodes not yet here (R175 step 3) ------------------------------------------

def follow_line(nid):
    """The one line to run on a node that outlived the old controller: the
    agent's follow verb with this address and the challenge this
    controller holds the key for."""
    d = _load()
    key = _key()
    if not d.get("restored_at") or not key:
        return ""
    return f"aerieos-agent follow {node_url(nid, page_url() or d.get('to', ''))} {challenge(key, nid)}"


def node_here(nid):
    """A node's hello on the controller a move landed on (nodes.hello): the
    node is here now, written once; nothing elsewhere."""
    d = _load()
    if not d.get("restored_at") or nid not in (d.get("nodes") or []) or nid in (d.get("here") or []):
        return
    with _lock:
        d = _load()
        here = [x for x in (d.get("here") or []) if isinstance(x, str)]
        if nid not in here:
            d["here"] = here + [str(nid)]
            _save(d)


def not_yet_here():
    """On the controller a move landed on: the nodes the bundle named that
    have not said hello here since (node_here), each with its follow line;
    [] elsewhere."""
    d = _load()
    if not d.get("restored_at"):
        return []
    here = set(d.get("here") or [])
    return [{"id": nid, "name": node_name(nid), "line": follow_line(nid)} for nid in d.get("nodes") or [] if nid not in here]


def read_manifest(path):
    """The bundle's manifest, or (None, why)."""
    try:
        with open(path, "rb") as f:
            head = f.readline()
            if head not in (HEADER, BACKUP_HEADER):
                return None, "not an AerieOS move bundle or backup"
            line = f.readline()
        m = json.loads(line)
        if isinstance(m, dict) and head == BACKUP_HEADER:
            m["kind"] = "backup"
        return (m, "") if isinstance(m, dict) and m.get("format") in (1, FORMAT) else (None, "a bundle of a format this build does not read")
    except (OSError, ValueError) as e:
        return None, f"could not read the bundle: {e}"


def _set_aside_clashes(carried, workspace_dir, stamp, state_dir):
    """A space folder this controller has, of the same name as one the
    bundle carries (or a deleted one in its trash), moved into the trash
    under a name of its own before the copy, never merged with the bundle's
    (B707): two repositories' files mixed in one folder, and this one's
    space gone from the records the landing replaces. A landing cut midway
    and landed again (B622) finishes its own copy. What was set aside, said."""
    if cut_landing(state_dir):
        return []
    bin_ = workspace_dir / ".trash"
    said = []

    def aside(here, name):
        bin_.mkdir(exist_ok=True)
        dest, n = bin_ / f"{name}-before-move-{stamp}", 1
        while dest.exists():
            n += 1
            dest = bin_ / f"{name}-before-move-{stamp}-{n}"
        here.rename(dest)
        return dest.name

    for top in sorted(carried.iterdir()):
        here = workspace_dir / top.name
        if top.name == ".trash" and top.is_dir() and bin_.is_dir():
            for t in sorted(top.iterdir()):
                if (bin_ / t.name).exists():
                    said.append(f"{t.name}: a deleted space of that name was in this controller's trash; it is there now as {aside(bin_ / t.name, t.name)}")
            continue
        if top.name.startswith(".") or not (here.exists() or here.is_symlink()):
            continue
        if here.is_dir() and not here.is_symlink() and not any(here.iterdir()):
            continue
        said.append(f"{top.name}: this controller had a space folder of that name; it is in the workspace's trash as {aside(here, top.name)}, and the moved one in its place")
    return said


def _carry_share_people(aside, state_dir):
    """The accounts this controller made from an old system's share users
    (users.adopt: no password of their own, an SMB password's hash) carried
    into the landed accounts under the same id, so the shares already served
    to them keep their people (B716); a name or an id the landed accounts
    already have is left and said. What was carried or left, said."""
    try:
        was = json.loads((aside / "users.json").read_text())
        now = json.loads((state_dir / "users.json").read_text())
    except (OSError, ValueError):
        return []
    if not isinstance(was, dict) or not isinstance(now, dict):
        return []
    old, new = was.get("users") or {}, now.setdefault("users", {})
    if not isinstance(old, dict) or not isinstance(new, dict):
        return []
    uids = {str((u or {}).get("uid") or "") for u in new.values() if isinstance(u, dict)}
    carried, left = [], []
    for name, u in sorted(old.items()):
        if not isinstance(u, dict) or u.get("password") or not u.get("smb_nt") or u.get("role") == "owner":
            continue
        if name in new or str(u.get("uid") or "") in uids:
            left.append(name)
            continue
        new[name] = u
        carried.append(name)
    said = []
    if carried:
        tmp = state_dir / ".users.json.carry"
        try:
            fd = os.open(str(tmp), os.O_WRONLY | os.O_CREAT | os.O_TRUNC, 0o600)
            with os.fdopen(fd, "w") as f:
                json.dump(now, f, indent=1)
                f.flush()
                os.fsync(f.fileno())
            os.replace(tmp, state_dir / "users.json")
        except OSError as e:
            with contextlib.suppress(OSError):
                tmp.unlink()
            return [f"the share users made here ({', '.join(carried)}) could not be kept ({e}): make them again on the Users page"]
        said.append(f"the share users made here are kept as accounts with their SMB passwords: {', '.join(carried)}")
    if left:
        said.append(f"share users made here whose name the moved controller already has are its accounts now: {', '.join(left)}")
    return said


def restore(path, token="", state_dir=None, workspace_dir=None, secrets_dir=None, build_state_version=None, here_bare_metal=None, key=None,
            work_root=None):
    """The bundle unsealed under the token and put in place of the state here
    (the state as it is moved aside, as a reset does), its stores where the
    records name them, the repositories into the workspace, the secrets into
    theirs, the install key where it is read; held to the version gate first:
    never onto a build whose state version is older than the bundle's.
    Returns {ok, moved_aside, counts} or {error}."""
    state_dir = Path(state_dir or STATE)
    state_dir.mkdir(parents=True, exist_ok=True)
    workspace_dir = Path(workspace_dir or WORKSPACE)
    secrets_dir = Path(secrets_dir) if secrets_dir else (Path(SECRETS) if SECRETS else None)
    here_ver = int(build_state_version if build_state_version is not None else state_version() or 0)
    m, why = read_manifest(path)
    if not m:
        return {"error": why}
    if int(m.get("state_version") or 0) > here_ver:
        return {"error": f"the bundle's state is at version {m.get('state_version')} and this build reads up to {here_ver}: "
                         "a move never lands on an older build; update this install first"}
    # ...nor a state this build no longer upgrades from: it would land, and the
    # next start refuse it (B600).
    if m.get("state_version") and int(m["state_version"]) < stateversion.SUPPORTED_FROM:
        return {"error": f"the bundle's state is at version {m['state_version']}, and this build upgrades from "
                         f"{stateversion.SUPPORTED_FROM} on: move it through a release between them first"}
    # A backup opens under the key its password derives (backup.py); a
    # move under its token's.
    if key is None:
        if m.get("kind") == "backup":
            return {"error": "a backup opens under its password, not a move token"}
        if token_hash(token) != m.get("token_hash"):
            return {"error": "that is not this bundle's move token"}
        key = key_of(token)
    wrong = "the bundle did not open under that " + ("password" if m.get("kind") == "backup" else "token")
    fh = open(path, "rb")
    fh.readline(); fh.readline()
    if m.get("format") == 1:
        # The format before was opened whole in memory; a bundle that big
        # was never one of them (B724: the format is read from the plain line).
        if os.path.getsize(path) > (2 << 30):
            fh.close()
            return {"error": "the bundle says it is of the format before, which was never this big: not opened"}
        try:
            src, mode = io.BytesIO(open_with(key, fh.read())), "r:gz"
        except Exception:                                          # noqa: BLE001 (any failure to open is one answer)
            fh.close()
            return {"error": wrong}
        fh.close()
    else:
        # A piece at a time; the first opened here, so a wrong token is said
        # as one before anything is unpacked.
        src, mode = _Opener(fh, key), "r|gz"
        try:
            src._next()
        except ValueError:
            fh.close()
            return {"error": wrong}
    # Unpacked inside the state, or where the caller says (`work_root`: on a
    # stick, the projects folder on the machine's disks, never the stick).
    work = Path(tempfile.mkdtemp(prefix=".move-", dir=str(work_root or state_dir)))
    counts = {}
    said = []   # what the landing could not do as asked, said in its result (B623)
    try:
        try:
            unpacked = _unpack(src, mode, work, counts)
        except (ValueError, EOFError, tarfile.TarError, zlib.error) as e:
            unpacked = f"the bundle is damaged or cut short ({e}); nothing here was changed"
        if unpacked:
            return {"error": unpacked}
        counts.pop(MANIFEST_MARK, None)
        changed = _manifest_held(path, key, work)
        if changed:
            return {"error": changed}
        stamp = time.strftime("%Y%m%d-%H%M%S")
        aside = state_dir / f".moved-{stamp}"
        # A landing within the same second as one before (a retry after a
        # cut one, B622) takes a name of its own rather than failing on it.
        n = 1
        while aside.exists():
            n += 1
            stamp = f"{time.strftime('%Y%m%d-%H%M%S')}-{n}"
            aside = state_dir / f".moved-{stamp}"
        # The workspace and the secrets first, which do not need the state;
        # the state swapped after, and anything failing from there on puts
        # what was here back (B557): an error copying the workspace after
        # the swap left the new state half restored, the old one aside and
        # not said where.
        if (work / "workspace").is_dir():
            set_aside = []
            try:
                workspace_dir.mkdir(parents=True, exist_ok=True)
                set_aside = _set_aside_clashes(work / "workspace", workspace_dir, stamp, state_dir)
                said += set_aside
                shutil.copytree(str(work / "workspace"), str(workspace_dir), symlinks=True, dirs_exist_ok=True)
            except (OSError, shutil.Error) as e:
                # Said, with what was set aside and where, rather than
                # escaping the landing with those lines lost (B725).
                return {"error": f"the spaces could not be copied into {workspace_dir} ({str(e)[:300]}); the state here was not changed"
                                 + (". Set aside before the copy: " + "; ".join(set_aside) if set_aside else "")}
        if (work / "secrets").is_dir() and secrets_dir:
            try:
                secrets_dir.mkdir(parents=True, exist_ok=True, mode=0o700)
                shutil.copytree(str(work / "secrets"), str(secrets_dir), symlinks=True, dirs_exist_ok=True)
            except (OSError, shutil.Error) as e:
                # A secrets folder that is root's takes nothing the dashboard
                # writes (and root never reads what the dashboard's account
                # left for it): the rest lands, and this is said (B728).
                said.append(f"the old controller's secrets were not written into {secrets_dir} ({str(e)[:200]}): "
                            "copy its *.env files and ssh/ there as root, then restart the controller")
        swapped = False
        # The landing marked while the state is half old and half new, so a
        # power loss midway leaves a word of it for the next start (B622):
        # the bell says what is where and that the same bundle lands again.
        marker = state_dir / LANDING_MARK
        try:
            # The state swapped inside its folder, never by renaming the folder:
            # its parent is root's on an installed machine and a container's
            # /config is a mount point (B594). A mountpoint under it (a stick's
            # logs on a RAM disk) stays where it is, the bundle's merged in.
            aside.mkdir(mode=0o700)
            with contextlib.suppress(OSError):
                marker.write_text(json.dumps({"at": int(time.time()), "stamp": stamp, "aside": str(aside),
                                              "from": m.get("from", ""), "kind": m.get("kind", "")}))
            swapped = True
            for p in sorted(state_dir.iterdir()):
                if p.name.startswith(NEVER_PACKED) or p == work:
                    continue
                with contextlib.suppress(OSError):
                    os.rename(p, aside / p.name)
            _into(work / "state", state_dir)
            # The stores, where the restored records name them; one whose path
            # cannot be made on this machine lands under the state, and the
            # record says so for the Storage page (B598).
            for kind_dir in (work / "stores").iterdir() if (work / "stores").is_dir() else []:
                dest = Path((store_paths() or {}).get(kind_dir.name) or (state_dir / kind_dir.name))
                try:
                    dest.parent.mkdir(parents=True, exist_ok=True)
                    _into(kind_dir, dest)
                except OSError:
                    _store_here(state_dir, kind_dir.name)
                    _into(kind_dir, state_dir / kind_dir.name)
            said += _carry_share_people(aside, state_dir)
            if (work / "install-key").is_file():
                # A key the landing could not take is said in the result
                # and kept on the record (B623), never swallowed.
                why = install_landed_key((work / "install-key").read_bytes(), state_dir)
                if why:
                    said.append(str(why))
        except (OSError, shutil.Error) as e:
            with contextlib.suppress(OSError):
                marker.unlink()
            if swapped:
                for p in list(state_dir.iterdir()):
                    # A mount point stayed where it was through the swap (its
                    # rename refused): what it holds is this controller's, and
                    # is never deleted on the way back (B725).
                    if p.name.startswith(NEVER_PACKED) or p == work or os.path.ismount(p):
                        continue
                    if p.is_dir() and not p.is_symlink():
                        shutil.rmtree(p, ignore_errors=True)
                    else:
                        with contextlib.suppress(OSError):
                            p.unlink()
                _into(aside, state_dir)
                shutil.rmtree(aside, ignore_errors=True)
            return {"error": f"the restore stopped ({e}); "
                             + ("the state that was here is back as it was" if swapped else "nothing of the state was changed")}
        # The move's own record, carried with the state: now the new home's,
        # which answers the nodes' knocks and knows where it came from.
        rec_path = state_dir / "move.json"
        try:
            with open(rec_path) as f:
                rec = json.load(f)
        except (OSError, ValueError):
            rec = {}
        backup = m.get("kind") in ("backup", "token-backup")
        rec.update(restored_at=int(time.time()), used=True, came_from=m.get("from", "") if not backup else "",
                   source_bare_metal=bool(m.get("bare_metal")),
                   here_bare_metal=bool(here_bare_metal if here_bare_metal is not None else bare_metal()),
                   nodes=list(m.get("nodes") or []))
        if backup:
            rec["came_from_backup"] = True
        # A backup under a token (no move armed where it came from): its key
        # is the one nodes still there follow by, with the Nodes page's line.
        if m.get("kind") == "token-backup":
            rec.update(key_b64=base64.b64encode(key).decode(), token_hash=m.get("token_hash", ""), made_at=int(m.get("made_at") or 0))
        rec["said"] = list(said)
        for k in ("moved_to", "moved_at", "moved_how", "landed_at", "asked_at", "asked_error", "fetch_nonces", "told_at", "tell_tried_at",
                  "tell_error", "told_how", "told", "here"):
            rec.pop(k, None)
        # The record whole before the mark comes off (B720): a stop between
        # the two left a swapped state with the old controller's record, or
        # an empty one, and no word that the landing had not ended.
        tmp = rec_path.with_name(rec_path.name + ".new")
        with open(tmp, "w") as f:
            json.dump(rec, f)
            f.flush()
            os.fsync(f.fileno())
        os.chmod(tmp, 0o600)
        os.replace(tmp, rec_path)
        with contextlib.suppress(OSError):
            marker.unlink()
        # A bare-metal home keeps its own node and its stick's plan (above).
        here = carry_here(aside, state_dir, source_bare_metal=rec["source_bare_metal"]) if swapped and rec["here_bare_metal"] else []
        return {"ok": True, "moved_aside": str(aside), "counts": counts, "from": m.get("from", ""),
                "nodes": list(m.get("nodes") or []), "kept_here": here, "said": said}
    finally:
        shutil.rmtree(work, ignore_errors=True)
        src.close()


def _into(src, dest):
    """What `src` holds moved into the folder `dest`, made if missing: a name
    there already is merged (a mountpoint stays a mountpoint)."""
    src, dest = Path(src), Path(dest)
    dest.mkdir(parents=True, exist_ok=True)
    for p in sorted(src.iterdir()):
        to = dest / p.name
        if to.is_dir() and not to.is_symlink() and p.is_dir() and not p.is_symlink():
            _into(p, to)
        else:
            shutil.move(str(p), str(to))


def _store_here(state_dir, kind):
    """A store's record back to its default, under the state (paths.json)."""
    f = Path(state_dir) / "paths.json"
    with contextlib.suppress(OSError, ValueError):
        d = json.loads(f.read_text())
        if isinstance(d, dict) and d.pop(kind, None) is not None:
            f.write_text(json.dumps(d))


def _unpack(src, mode, work, counts):
    """The bundle's tar unpacked into `work`, counting each top folder's
    files: a file, or a link where the data filter can hold it inside what
    is restored. "" when done."""
    with tarfile.open(fileobj=src, mode=mode) as tar:
        safe_links = hasattr(tarfile, "data_filter")
        for info in tar:
            if info.name.startswith("/") or ".." in Path(info.name).parts:
                continue
            # A link only where the data filter can check it: it refuses
            # one that is absolute or leads out of what is restored.
            if not (info.isfile() or (info.issym() and safe_links)):
                continue
            try:
                tar.extract(info, path=str(work), filter="data") if safe_links else tar.extract(info, path=str(work))
            except tarfile.FilterError:
                continue
            top = Path(info.name).parts[0]
            counts[top] = counts.get(top, 0) + 1
    return ""


def carry_here(aside, state_dir, source_bare_metal=True):
    """What belongs to this machine rather than to the controller that moved
    in, carried from the state set aside into the one put in place (the
    operator, 1 Nov: a stick that came with a plan and a node of its own,
    then a controller moved onto it): the machine's own node, enrolled at
    its first boot, with its tokens, so its agent is known to the controller
    that moved here; and the stick's prepared configuration (firstboot.json),
    so what it names to adopt is still offered. Nothing the moved state has
    of its own is replaced. The lines said."""
    import sqlite3
    said = []
    old_db, new_db = Path(aside) / "builderbot.db", Path(state_dir) / "builderbot.db"
    if old_db.is_file() and new_db.is_file():
        try:
            src, dst = sqlite3.connect(str(old_db)), sqlite3.connect(str(new_db))
            try:
                cols = lambda c, t: [r[1] for r in c.execute(f"PRAGMA table_info({t})")]  # noqa: E731
                ncols = [x for x in cols(src, "nodes") if x in cols(dst, "nodes")]
                tcols = [x for x in cols(src, "tokens") if x in cols(dst, "tokens")]
                own = [r for r in src.execute(f"SELECT {', '.join(ncols)} FROM nodes WHERE state != 'retired'")
                       if (json.loads(r[ncols.index("config")] or "{}") or {}).get("own")] if "config" in ncols else []
                for r in own:
                    nid = r[ncols.index("id")]
                    if dst.execute("SELECT 1 FROM nodes WHERE id = ?", (nid,)).fetchone():
                        continue
                    # The old home's own machine, where it was bare metal, is
                    # that machine's, not this one: retired here (step 5 of
                    # Moving a controller in docs/install.md).
                    # Only where the old home was bare metal: a container
                    # install has no machine of its own, and a node it
                    # holds is a node of its own to follow, never retired
                    # and its spaces handed to this machine (the operator,
                    # 10 Nov: a space's container listed here after a move).
                    for oid, ocfg in (dst.execute("SELECT id, config FROM nodes WHERE state != 'retired'").fetchall() if source_bare_metal else []):
                        if (json.loads(ocfg or "{}") or {}).get("own"):
                            dst.execute("UPDATE nodes SET state = 'retired' WHERE id = ?", (oid,))
                            said += _own_node_handed_on(state_dir, oid, nid)
                    dst.execute(f"INSERT INTO nodes ({', '.join(ncols)}) VALUES ({', '.join('?' * len(ncols))})", r)
                    for t in src.execute(f"SELECT {', '.join(tcols)} FROM tokens WHERE node_id = ? AND kind = 'node'", (nid,)):
                        dst.execute(f"INSERT OR IGNORE INTO tokens ({', '.join(tcols)}) VALUES ({', '.join('?' * len(tcols))})", t)
                    said.append(f"this machine's own node ({r[ncols.index('name')]}) is the moved controller's too")
                dst.commit()
            finally:
                src.close()
                dst.close()
        except (sqlite3.Error, ValueError) as e:
            said.append(f"this machine's own node was not carried over ({e}): enroll it again from the Nodes page")
    fb_old, fb_new = Path(aside) / "firstboot.json", Path(state_dir) / "firstboot.json"
    if fb_old.is_file() and not fb_new.exists():
        shutil.copyfile(str(fb_old), str(fb_new))
        said.append("the stick's plan (its disks, shares, containers and VMs) is still offered on the Nodes page")
    return said


def _own_node_handed_on(state_dir, old, new):
    """The moved controller's own machine is retired for this one's: the
    projects that ran there run here now, their folder having come with the
    controller, and it is not a node to wait for. The lines said."""
    said = []
    f = Path(state_dir) / "claude-prefs.json"
    try:
        d = json.loads(f.read_text())
        moved = 0
        for p in (d.get("projects") or {}).values():
            if not isinstance(p, dict):
                continue
            was = (p.get("node"), list(p.get("nodes") or []))
            if p.get("node") == old:
                p["node"] = new
            if old in (p.get("nodes") or []):
                p["nodes"] = list(dict.fromkeys(new if x == old else x for x in p["nodes"]))
            moved += was != (p.get("node"), list(p.get("nodes") or []))
        if moved:
            tmp = f.with_name(f.name + ".new")
            tmp.write_text(json.dumps(d))
            os.replace(tmp, f)
            said.append(f"{moved} space{'' if moved == 1 else 's'} that ran on the old controller's machine run on this one now")
    except (OSError, ValueError):
        pass
    f = Path(state_dir) / "move.json"
    try:
        d = json.loads(f.read_text())
        if old in (d.get("nodes") or []):
            d["nodes"] = [x for x in d["nodes"] if x != old]
            tmp = f.with_name(f.name + ".new")
            tmp.write_text(json.dumps(d))
            os.replace(tmp, f)
    except (OSError, ValueError):
        pass
    return said


def restored():
    """Whether this state arrived by a move, and from where: for the first
    run's page and the Nodes page's "checking back in"."""
    d = _load()
    return {"restored_at": int(d.get("restored_at") or 0), "from": d.get("came_from", "") or ("a backup" if d.get("came_from_backup") else ""),
            "source_bare_metal": bool(d.get("source_bare_metal")), "told_at": int(d.get("told_at") or 0),
            "told_how": d.get("told_how", ""), "tell_error": d.get("tell_error", "")} if d.get("restored_at") else {}
