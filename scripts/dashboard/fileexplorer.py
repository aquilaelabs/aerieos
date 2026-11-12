"""The file explorer (R224): a machine's files, browsed, previewed,
uploaded, downloaded, renamed and put in the trash, through its agent.

Administrators only (the operator, 8 Nov), every change audited. What it
reaches is the machine's roots, read from its census: its pools, its
array, its shares, the old system's merged view where disks were adopted,
the disks and network shares it mounts, and the spaces folder a stick names; never the system's own folders, which
the agent refuses whatever is asked. Each request goes to the agent's
screen relay port signed for that request and this minute, as a terminal
is (files.py on the agent), and its answer is streamed through.
"""
import base64
import hashlib
import hmac
import json
import re
import socket
import time

node_fn = None          # nodes.node
host_fn = None          # nodes.route_host
key_fn = None           # nodes.screen_key
audit_fn = None         # db.audit(principal, what, detail, params)
SCREEN_PORT = 7684
OPS = ("list", "read", "write", "mkdir", "rename", "delete")


def configure(*, node, host, key, audit, screen_port=7684):
    globals().update(node_fn=node, host_fn=host, key_fn=key, audit_fn=audit, SCREEN_PORT=screen_port)


def roots(n):
    """The machine's roots from its census: [{path, label, kind}], each
    path once, in the order a person looks for them."""
    rep = (n or {}).get("reported") or {}
    out, seen = [], set()

    def add(path, label, kind):
        path = str(path or "").rstrip("/") or ""
        if not path.startswith("/") or path in seen or ".." in path.split("/"):
            return
        seen.add(path)
        out.append({"path": path, "label": label, "kind": kind})
    stick = rep.get("os_stick") or {}
    if stick.get("projects"):
        add(stick["projects"], "Spaces folder", "spaces")
    for p in rep.get("pools") or []:
        if isinstance(p, dict) and p.get("mount"):
            add(p["mount"], p.get("name") or p["mount"], "pool")
    ar = rep.get("array") or {}
    if ar.get("mount") and ar.get("mounted"):
        add(ar["mount"], "Array", "array")
    ad = rep.get("adopted") or {}
    for where, on in (ad.get("merged") or {}).items():
        if on:
            add(where, f"{where.rsplit('/', 1)[-1]} (adopted)", "adopted")
    for m in ad.get("mounts") or []:
        if isinstance(m, dict) and m.get("mounted"):
            add(m.get("where"), f"{str(m.get('where') or '').rsplit('/', 1)[-1]} (adopted{', read only' if m.get('ro') else ''})", "adopted")
    for sh in rep.get("shares") or []:
        if isinstance(sh, dict) and sh.get("path"):
            add(sh["path"], f"{sh.get('name')} (share)", "share")
    # The disks and network shares it mounts (its Storage section's mounts,
    # and the other disks under /mnt/other), on any node, not only a NAS.
    for m in rep.get("mounts") or []:
        if isinstance(m, dict) and m.get("mounted") and not m.get("stale"):
            add(m.get("path"), f"{str(m.get('path') or '').rstrip('/').rsplit('/', 1)[-1] or m.get('path')} (mount{', read only' if m.get('ro') else ''})", "mount")
    for m in rep.get("ext_mounts") or []:
        if isinstance(m, dict) and m.get("mounted") and m.get("name"):
            add(f"/mnt/other/{m['name']}", f"{m['name']} (other disk)", "mount")
    return out


def _target(principal_ok, node_id, root):
    """(node, host, port, key) for a request on `root`, or an error dict."""
    if not principal_ok:
        return {"error": "the file explorer is an administrator's"}
    n = node_fn(node_id) if node_fn else None
    if not n or n.get("kind") != "agent" or n.get("state") == "retired":
        return {"error": "no such node"}
    if not any(r["path"] == str(root or "").rstrip("/") for r in roots(n)):
        return {"error": f"{root or 'that'} is not one of {n.get('name') or node_id}'s disks, pools or shares"}
    if n.get("live") is False:
        return {"error": f"{n.get('name') or node_id}'s agent is not dialing in"}
    fs = (n.get("reported") or {}).get("files") or {}
    if not fs.get("port"):
        return {"error": f"{n.get('name') or node_id}'s agent does not serve files yet: update it from the Nodes page"}
    host, key = host_fn(node_id), key_fn(node_id)
    if not host or not key:
        return {"error": f"{n.get('name') or node_id} cannot be reached from here"}
    return {"node": n, "host": host, "port": int(fs["port"]), "key": key}


def _request_line(key, spec):
    blob = base64.urlsafe_b64encode(json.dumps(spec, separators=(",", ":")).encode()).decode().rstrip("=")
    t = int(time.time())
    sig = hmac.new(key.encode(), f"files.{blob}.{t}".encode(), hashlib.sha256).hexdigest()
    return f"/files?a={blob}&t={t}&s={sig}"


def open_request(tg, spec, method="GET", length=None):
    """A connection to the agent with the request's head sent: the socket."""
    up = socket.create_connection((tg["host"], tg["port"]), timeout=15)
    head = [f"{method} {_request_line(tg['key'], spec)} HTTP/1.1", f"Host: {tg['host']}:{tg['port']}", "Connection: close"]
    if length is not None:
        head.append(f"Content-Length: {int(length)}")
    up.sendall(("\r\n".join(head) + "\r\n\r\n").encode())
    return up


def read_head(up):
    """(status, headers, the body's start) of the agent's answer."""
    buf = b""
    while b"\r\n\r\n" not in buf:
        got = up.recv(65536)
        if not got:
            break
        buf += got
        if len(buf) > 65536:
            break
    head, _, rest = buf.partition(b"\r\n\r\n")
    lines = head.decode("latin-1").split("\r\n")
    try:
        status = int(lines[0].split(" ")[1])
    except (IndexError, ValueError):
        status = 502
    hdr = {k.strip().lower(): v.strip() for k, _, v in (ln.partition(":") for ln in lines[1:])}
    return status, hdr, rest


def read_json(up, hdr, rest):
    n = int(hdr.get("content-length") or 0)
    while len(rest) < n:
        got = up.recv(65536)
        if not got:
            break
        rest += got
    try:
        return json.loads(rest[:n] or b"{}")
    except ValueError:
        return {"error": "the agent's answer was not one"}


def call(tg, spec):
    """A small request answered with JSON: (payload, status)."""
    try:
        up = open_request(tg, spec)
        try:
            status, hdr, rest = read_head(up)
            return read_json(up, hdr, rest), status
        finally:
            up.close()
    except OSError as e:
        return {"error": f"{(tg.get('node') or {}).get('name')} did not answer on {tg['host']}:{tg['port']}: {e}"}, 502


NAME = re.compile(r"[^/\0]{1,255}")
# What a file is shown in the page as: an image, a video, a PDF as itself;
# anything else as text, so a page or a script on a disk never runs here.
SHOWN = {".png": "image/png", ".jpg": "image/jpeg", ".jpeg": "image/jpeg", ".gif": "image/gif", ".webp": "image/webp",
         ".avif": "image/avif", ".bmp": "image/bmp", ".ico": "image/x-icon", ".mp4": "video/mp4", ".webm": "video/webm",
         ".mov": "video/quicktime", ".m4v": "video/mp4", ".mp3": "audio/mpeg", ".m4a": "audio/mp4", ".ogg": "audio/ogg",
         ".wav": "audio/wav", ".flac": "audio/flac", ".pdf": "application/pdf"}


def shown_as(name):
    dot = name.rfind(".")
    return SHOWN.get(name[dot:].lower() if dot > 0 else "", "text/plain; charset=utf-8")


def act(principal, admin, node_id, root, op, path="", name="", dest=""):
    """A list or a change: (payload, status). A change is audited."""
    if op not in ("list", "mkdir", "rename", "delete"):
        return {"error": "not a file action"}, 400
    tg = _target(admin, node_id, root)
    if tg.get("error"):
        return tg, 403 if "administrator" in str(tg["error"]) else 400
    if op in ("mkdir",) and not NAME.fullmatch(name or ""):
        return {"error": "a name is needed, without a slash"}, 400
    spec = {"op": op, "root": str(root).rstrip("/"), "path": str(path or ""), "name": str(name or ""), "dest": str(dest or "")}
    out, status = call(tg, spec)
    if op != "list" and status == 200 and audit_fn:
        audit_fn(principal, f"files-{op}", f"{(tg.get('node') or {}).get('name')}:{root}/{str(path).lstrip('/')}"[:120],
                 {"name": name, "dest": dest})
    return out, status
