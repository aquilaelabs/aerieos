"""The file explorer's verbs on a node (R224): a request the controller
signed, on the screen relay's port (screen.py), which the node's firewall
opens to the controller alone.

The controller signs what the request is (its op, its root, its path and
what else the op needs) and the minute, keyed with the hash of this node's
own token, as it signs a terminal. Every path is resolved and held inside
the root the request names, and a root is a folder on the machine's disks,
never the system's own (/, /etc, /usr and the like): a link is never
followed out of it. A delete is a move into the root's trash folder, with
a note of where it came from; nothing here deletes a file outright.

What it answers, one request each, the connection closed after:
  list    {entries: [{name, kind, size, mtime, mode, owner, target?}], truncated}
  read    the file's bytes from `from`, Content-Length its size
  write   the request's body to a new file in `path` named `name`
  mkdir   a folder `name` in `path`
  rename  `path` to `dest`, both inside the root
  delete  `path` into ROOT/.aerieos-trash
A file or folder made here takes the owner and group of the folder it is
made in, so a share's people can still write what an administrator put
there.
"""
import base64
import hashlib
import hmac
import json
import os
import pwd
import stat
import time
import urllib.parse

SKEW_S = 120
TRASH = ".aerieos-trash"
LIST_MAX = 5000
CHUNK = 1 << 20
# What is never a root: the system's own folders, and the ones the kernel makes.
SYSTEM = ("/", "/bin", "/boot", "/dev", "/etc", "/lib", "/lib64", "/proc", "/root", "/run", "/sbin", "/sys", "/usr", "/var")
OPS = ("list", "read", "write", "mkdir", "rename", "delete")


def sign(key, blob, when):
    return hmac.new(key.encode(), f"files.{blob}.{int(when)}".encode(), hashlib.sha256).hexdigest()


def signed(key, blob, when, sig, now=None):
    """Whether the controller signed this request, this minute. `key` may
    be several: the current and the one before a rotation."""
    try:
        when = int(when)
    except (TypeError, ValueError):
        return False
    now = time.time() if now is None else now
    keys = key if isinstance(key, list) else [key]
    return abs(now - when) <= SKEW_S and any(hmac.compare_digest(sign(k, blob, when), str(sig or "")) for k in keys)


def pack(spec):
    return base64.urlsafe_b64encode(json.dumps(spec, separators=(",", ":")).encode()).decode().rstrip("=")


def unpack(blob):
    """The request's spec, or None for anything that is not one."""
    try:
        d = json.loads(base64.urlsafe_b64decode(blob + "=" * (-len(blob) % 4)))
    except (ValueError, TypeError):
        return None
    if not isinstance(d, dict) or d.get("op") not in OPS:
        return None
    for k in ("root", "path", "dest", "name"):
        v = d.get(k, "")
        if not isinstance(v, str) or "\0" in v or len(v) > 4096:
            return None
    return d


def root_ok(root):
    """The root as a real folder, or "" when it is not one a request may name."""
    if not isinstance(root, str) or not root.startswith("/"):
        return ""
    real = os.path.realpath(root)
    if any(real == d or real.startswith(d + "/") for d in SYSTEM if d != "/") or real == "/":
        return ""
    return real if os.path.isdir(real) else ""


def inside(root, rel):
    """ROOT/REL resolved, or "" when it leaves the root (a `..`, a link out)."""
    rel = str(rel or "").lstrip("/")
    full = os.path.realpath(os.path.join(root, rel))
    return full if full == root or full.startswith(root + "/") else ""


def thing(root, rel):
    """ROOT/REL as the thing itself (a link not followed), its folder
    resolved and held inside the root; "" when it leaves it or is the root."""
    rel = str(rel or "").strip("/")
    if not rel:
        return ""
    parent = inside(root, os.path.dirname(rel))
    name = os.path.basename(rel)
    if not parent or not _name_ok(name):
        return ""
    return os.path.join(parent, name)


def _name_ok(name):
    return bool(name) and name not in (".", "..") and "/" not in name and "\0" not in name and len(name.encode()) <= 255


def _owner(uid):
    try:
        return pwd.getpwuid(uid).pw_name
    except KeyError:
        return str(uid)


def _like_parent(path):
    """A new file or folder takes its folder's owner and group (as root)."""
    if os.geteuid() != 0:
        return
    try:
        st = os.stat(os.path.dirname(path))
        os.lchown(path, st.st_uid, st.st_gid)
    except OSError:
        pass


def listing(full):
    out, truncated = [], False
    with os.scandir(full) as it:
        for e in it:
            if len(out) >= LIST_MAX:
                truncated = True
                break
            try:
                st = e.stat(follow_symlinks=False)
            except OSError:
                continue
            kind = "link" if stat.S_ISLNK(st.st_mode) else "dir" if stat.S_ISDIR(st.st_mode) else "file" if stat.S_ISREG(st.st_mode) else "other"
            row = {"name": e.name, "kind": kind, "size": st.st_size if kind == "file" else 0, "mtime": int(st.st_mtime),
                   "mode": stat.filemode(st.st_mode), "owner": _owner(st.st_uid)}
            if kind == "link":
                try:
                    row["target"] = os.readlink(e.path)[:500]
                    row["to_dir"] = os.path.isdir(e.path)
                except OSError:
                    pass
            out.append(row)
    return {"entries": out, "truncated": truncated}


def _trash(root, full):
    """`full` moved into ROOT/.aerieos-trash under a name of its own, with a
    note of where it was; the trash's own path."""
    trash = os.path.join(root, TRASH)
    if not os.path.isdir(trash):
        os.mkdir(trash, 0o700)
    stamp = time.strftime("%Y%m%d-%H%M%S")
    base = f"{stamp}-{os.path.basename(full)}"[:240]
    to, n = os.path.join(trash, base), 1
    while os.path.lexists(to):
        n += 1
        to = os.path.join(trash, f"{base}-{n}")
    os.rename(full, to)
    with open(to + ".aerieos-from", "w") as f:
        json.dump({"from": os.path.relpath(full, root), "at": int(time.time())}, f)
    return os.path.relpath(to, root)


def _answer(conn, code, body, ctype="application/json"):
    data = json.dumps(body).encode() if ctype == "application/json" else body
    conn.sendall(f"HTTP/1.1 {code} OK\r\nContent-Type: {ctype}\r\nContent-Length: {len(data)}\r\nConnection: close\r\n\r\n".encode() + data)


def _err(conn, code, why):
    _answer(conn, code, {"error": why})


def serve(conn, key, hdr, q, rest):
    """One request: checked as the controller signed it, then done.
    `rest` is what of the body came with the head."""
    blob = (q.get("a") or [""])[0]
    if not signed(key, blob, (q.get("t") or [""])[0], (q.get("s") or [""])[0]):
        return _err(conn, 403, "not signed by this node's controller")
    spec = unpack(blob)
    if spec is None:
        return _err(conn, 400, "not a file request")
    root = root_ok(spec.get("root"))
    if not root:
        return _err(conn, 403, f"{spec.get('root') or 'that'} is not a folder the file explorer reaches here")
    op = spec["op"]
    # Followed through links for what is read or written in; a rename and a
    # delete act on the thing itself (thing()).
    full = inside(root, spec.get("path"))
    if not full and op not in ("rename", "delete"):
        return _err(conn, 403, "that path leaves its root")
    try:
        if op == "list":
            if not os.path.isdir(full):
                return _err(conn, 404, "no such folder")
            return _answer(conn, 200, listing(full))
        if op == "read":
            return _read(conn, full, spec)
        if op == "write":
            return _write(conn, full, spec, hdr, rest)
        if op == "mkdir":
            name = str(spec.get("name") or "")
            if not _name_ok(name) or not os.path.isdir(full):
                return _err(conn, 400, "a folder's name is one word of a path, in a folder that is there")
            to = os.path.join(full, name)
            os.mkdir(to, 0o775)
            _like_parent(to)
            return _answer(conn, 200, {"ok": True})
        if op == "rename":
            src, dest = thing(root, spec.get("path")), thing(root, spec.get("dest"))
            if not src or not dest:
                return _err(conn, 403, "a rename stays inside its root, and the root itself is not renamed")
            if os.path.lexists(dest):
                return _err(conn, 409, f"{os.path.basename(dest)} is there already")
            if not os.path.lexists(src):
                return _err(conn, 404, "no such file")
            if os.path.isdir(src) and not os.path.islink(src) and (dest + "/").startswith(src + "/"):
                return _err(conn, 400, "a folder does not go inside itself")
            os.rename(src, dest)
            return _answer(conn, 200, {"ok": True})
        if op == "delete":
            src = thing(root, spec.get("path"))
            if not src or src == os.path.join(root, TRASH):
                return _err(conn, 403, "the root and its trash are not deleted")
            if not os.path.lexists(src):
                return _err(conn, 404, "no such file")
            return _answer(conn, 200, {"ok": True, "trash": _trash(root, src)})
    except PermissionError as e:
        return _err(conn, 403, f"not allowed here: {e.strerror}")
    except FileNotFoundError:
        return _err(conn, 404, "no such file or folder")
    except OSError as e:
        return _err(conn, 500, f"{e.strerror or e}")
    return _err(conn, 400, "not a file request")


def _read(conn, full, spec):
    if not os.path.isfile(full):
        return _err(conn, 404, "no such file")
    size = os.path.getsize(full)
    try:
        start = max(0, min(int(spec.get("from") or 0), size))
    except (TypeError, ValueError):
        start = 0
    with open(full, "rb") as f:
        f.seek(start)
        conn.sendall(f"HTTP/1.1 200 OK\r\nContent-Type: application/octet-stream\r\nContent-Length: {size - start}\r\n"
                     f"X-Size: {size}\r\nX-Mtime: {int(os.path.getmtime(full))}\r\nConnection: close\r\n\r\n".encode())
        while True:
            b = f.read(CHUNK)
            if not b:
                return None
            conn.sendall(b)


def _write(conn, full, spec, hdr, rest):
    name = str(spec.get("name") or "")
    if not _name_ok(name) or not os.path.isdir(full):
        return _err(conn, 400, "a file's name is one word of a path, in a folder that is there")
    to = os.path.join(full, name)
    if os.path.lexists(to) and not spec.get("replace"):
        return _err(conn, 409, f"{name} is there already")
    try:
        left = int(hdr.get("content-length", "-1"))
    except ValueError:
        left = -1
    if left < 0:
        return _err(conn, 411, "the upload says no length")
    part = os.path.join(full, f".{name}.aerieos-part")
    conn.settimeout(120)
    try:
        with open(part, "wb") as f:
            if rest:
                f.write(rest[:left])
                left -= len(rest[:left])
            while left > 0:
                b = conn.recv(min(CHUNK, left))
                if not b:
                    raise OSError("the upload was cut short")
                f.write(b)
                left -= len(b)
        if os.path.isdir(to):
            raise IsADirectoryError(f"{name} is a folder here")
        os.replace(part, to)
    except BaseException:
        try:
            os.unlink(part)
        except OSError:
            pass
        raise
    _like_parent(to)
    return _answer(conn, 200, {"ok": True, "size": os.path.getsize(to)})


def route(path):
    return urllib.parse.urlsplit(path).path == "/files"
