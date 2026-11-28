"""A shell in a pod, in the dock: the dock's terminal socket spliced
to the Kubernetes API's exec, translated between the two.

The page speaks AerieOS's own terminal frames (termws): a binary frame from
the browser is one byte, 0 for keys or 1 for a resize as JSON {cols, rows},
then its body; a frame to it is the screen's bytes. The API speaks its
channel protocol over a websocket of its own (v4.channel.k8s.io): every
binary frame starts with its channel, 0 stdin, 1 stdout, 2 stderr, 3 the
exec's end as a Status, 4 a resize as JSON {Width, Height}. This end is the
API's client, so its frames are masked; the server's are read by
termws.Frames as the browser's are.

Signed in as the environment's deployer, whose Role covers pods/exec in its
namespace and nowhere else; the token is the one kubeview keeps, in the
Authorization header of the upgrade, never in a URL.
"""
import base64
import json
import os
import selectors
import socket
import ssl
import struct
import time
import urllib.parse

import termws

CHECK_S = 5
# What runs: bash where the image has it, sh otherwise.
SHELL = ["sh", "-c", "command -v bash >/dev/null 2>&1 && exec bash || exec sh"]


def masked(payload, opcode=2):
    """A frame from a client: masked, as RFC 6455 requires of one."""
    n, key = len(payload), os.urandom(4)
    head = bytes([0x80 | opcode])
    if n < 126:
        head += bytes([0x80 | n])
    elif n < 65536:
        head += bytes([0x80 | 126]) + struct.pack(">H", n)
    else:
        head += bytes([0x80 | 127]) + struct.pack(">Q", n)
    body = (int.from_bytes(payload, "big") ^ int.from_bytes((key * (n // 4 + 1))[:n], "big")).to_bytes(n, "big") if n else b""
    return head + key + body


def _connect(server, ca, insecure, timeout=10):
    u = urllib.parse.urlsplit(server)
    host, port = u.hostname or "", u.port or (443 if u.scheme == "https" else 80)
    raw = socket.create_connection((host, port), timeout=timeout)
    if u.scheme != "https":
        return raw, f"{host}:{port}"
    ctx = ssl.create_default_context(cadata=ca or None) if ca else ssl.create_default_context()
    if insecure:
        ctx.check_hostname = False
        ctx.verify_mode = ssl.CERT_NONE
    return ctx.wrap_socket(raw, server_hostname=host), f"{host}:{port}"


def open_exec(acc, token, ns, pod, container="", cols=80, rows=24):
    """The API's exec socket, upgraded: (socket, leftover bytes) or a
    ValueError saying why not."""
    q = [("command", c) for c in SHELL] + [("stdin", "true"), ("stdout", "true"), ("stderr", "true"), ("tty", "true")]
    if container:
        q.append(("container", container))
    try:
        up, hostport = _connect(acc["server"], acc.get("ca", ""), acc.get("insecure"))
    except (OSError, ssl.SSLError) as e:
        raise ValueError(f"the cluster did not answer: {getattr(e, 'reason', None) or e}") from None
    key = base64.b64encode(os.urandom(16)).decode()
    path = urllib.parse.urlsplit(acc["server"]).path.rstrip("/")
    up.sendall((f"GET {path}/api/v1/namespaces/{ns}/pods/{pod}/exec?{urllib.parse.urlencode(q)} HTTP/1.1\r\n"
                f"Host: {hostport}\r\nUpgrade: websocket\r\nConnection: Upgrade\r\nSec-WebSocket-Key: {key}\r\n"
                f"Sec-WebSocket-Version: 13\r\nSec-WebSocket-Protocol: v4.channel.k8s.io\r\n"
                f"Authorization: Bearer {token}\r\n\r\n").encode())
    head = b""
    up.settimeout(15)
    while b"\r\n\r\n" not in head and len(head) < 16384:
        got = up.recv(4096)
        if not got:
            break
        head += got
    line, _, rest = head.partition(b"\r\n\r\n")
    first = line.split(b"\r\n")[0].decode("latin-1")
    if " 101 " not in first + " ":
        said = ""
        try:
            said = json.loads(rest.decode("utf-8", "replace") or "{}").get("message") or ""
        except ValueError:
            said = rest.decode("utf-8", "replace").strip()[:160]
        up.close()
        raise ValueError(f"the cluster refused the shell: {said or first}"[:200])
    up.settimeout(None)
    up.sendall(masked(bytes([4]) + json.dumps({"Width": cols, "Height": rows}).encode()))
    return up, rest


def _ended(status):
    """The exec's end in words, from channel 3's Status."""
    try:
        st = json.loads(status.decode("utf-8", "replace") or "{}")
    except ValueError:
        return "the shell ended"
    if st.get("status") == "Success":
        return "the shell ended"
    return f"the shell ended: {st.get('message') or st.get('reason') or 'with an error'}"[:200]


def splice(conn, up, rest, alive=None):
    """The browser's socket and the API's spliced until either ends or
    `alive` says no more."""
    down, upf = termws.Frames(), termws.Frames()
    sel = selectors.DefaultSelector()
    sel.register(conn, selectors.EVENT_READ, "down")
    sel.register(up, selectors.EVENT_READ, "up")
    check = time.monotonic() + CHECK_S

    def from_api(data):
        for op, body in upf.feed(data):
            if op == 8:
                return termws.close(conn, "the shell ended") or "end"
            if op == 9:
                up.sendall(masked(body, 10))
            elif op in (1, 2) and body:
                ch, out = body[0], body[1:]
                if ch in (1, 2) and out:
                    conn.sendall(termws.frame(out))
                elif ch == 3:
                    return termws.close(conn, _ended(out)) or "end"
        return ""
    try:
        if rest and from_api(rest):
            return None
        while True:
            for k, _ in sel.select(timeout=CHECK_S):
                data = k.fileobj.recv(65536)
                if not data:
                    if k.data == "up":
                        termws.close(conn, "the shell ended")
                    return None
                if k.data == "up":
                    if from_api(data):
                        return None
                    continue
                for op, body in down.feed(data):
                    if op == 8:
                        return None
                    if op not in (1, 2) or not body:
                        continue
                    if body[0] == 0:
                        up.sendall(masked(bytes([0]) + body[1:]))
                    elif body[0] == 1:
                        try:
                            d = json.loads(body[1:].decode() or "{}")
                            up.sendall(masked(bytes([4]) + json.dumps({"Width": int(d["cols"]), "Height": int(d["rows"])}).encode()))
                        except (ValueError, KeyError, TypeError):
                            pass
            if time.monotonic() >= check:
                check = time.monotonic() + CHECK_S
                why = alive() if alive else ""
                if why:
                    return termws.close(conn, why)
    except OSError:
        return None
    finally:
        sel.close()
        try:
            up.sendall(masked(b"", 8))
        except OSError:
            pass
        up.close()
