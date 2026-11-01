"""Plain http://THE-MACHINE/ on a controller's own machine finds the dashboard
(R202, the operator, 1 Nov): the dashboard stays on its port, and while nothing
else wants port 80 this answers there with a redirect to it.

It wants nothing for itself. It lets go the moment a nginx container exists
(AerieOS's own holds 80 and 443 on the machine, and closes a request naming
none of its sites: it never points a stranger at the dashboard, so from then on
the address with its port is the way in) and for as long as a compose job runs, so a container that
publishes 80 is never told the port is taken by this; it takes the port back
only when it is free. It reads one request line and a Host header, under a size
and a time limit, and answers a redirect: root, but nothing it reads goes
anywhere but that one line, held to a host's and a path's characters.
"""
import contextlib
import os
import re
import socket
import ssl
import subprocess
import threading
import time

MARK = "/etc/aerieos-controller/own-node"
ENV = "/etc/aerieos-controller/controller.env"
PORT = 80
CHECK_S = 5.0
HOLD_S = 120.0
HOST = re.compile(r"[A-Za-z0-9.-]{1,253}|\[[0-9A-Fa-f:.]{2,64}\]")
HOST_PORT = re.compile(r"(\[[^\]]*\]|[^:]*)(?::\d+)?")
PATH = re.compile(r"/[A-Za-z0-9._~!$&'()*+,;=:@%/?#\[\]-]{0,2000}")

_paused = 0
_lock = threading.Lock()


class paused:                                                   # noqa: N801 (a with-block's word)
    """Port 80 let go for a compose job's length."""

    def __enter__(self):
        global _paused
        with _lock:
            _paused += 1

    def __exit__(self, *exc):
        global _paused
        with _lock:
            _paused -= 1


def dashboard_port():
    port = 7680
    with contextlib.suppress(OSError, ValueError):
        with open(os.environ.get("BB_CONTROLLER_ENV", ENV), encoding="utf-8") as f:
            for line in f:
                if line.startswith("DASHBOARD_PORT="):
                    port = int(line.split("=", 1)[1].strip().strip('"'))
    return port


def scheme_of(port):
    """https where the dashboard answers a TLS handshake, else http."""
    ctx = ssl.create_default_context()
    ctx.check_hostname = False
    ctx.verify_mode = ssl.CERT_NONE
    try:
        with socket.create_connection(("127.0.0.1", port), timeout=1) as raw, ctx.wrap_socket(raw):
            return "https"
    except OSError:
        return "http"


def answer(head, port, scheme="http", here="localhost"):
    """The bytes to answer a request whose head is `head`: a redirect to the
    dashboard on the name it was asked by, at the path it asked for."""
    lines = head.decode("latin-1", "replace").split("\r\n")
    parts = lines[0].split(" ") if lines else []
    path = parts[1] if len(parts) == 3 and PATH.fullmatch(parts[1]) else "/"
    host = here
    for ln in lines[1:]:
        k, _, v = ln.partition(":")
        if k.strip().lower() == "host":
            m = HOST_PORT.fullmatch(v.strip())
            if m and HOST.fullmatch(m.group(1)):
                host = m.group(1)
            break
    to = f"{scheme}://{host}:{port}{path}"
    return (f"HTTP/1.1 302 Found\r\nLocation: {to}\r\nContent-Length: 0\r\nConnection: close\r\n"
            "Cache-Control: no-store\r\n\r\n").encode("latin-1", "replace")


def docker_look():
    """(whether docker runs, whether a container of AerieOS's nginx is on
    this machine, up or not: its restart policy then wants the port). A daemon
    that is held (a stick before its pool) is not asked: docker's socket would
    try to start it. Where docker answers oddly, nginx is taken to be there,
    since this is never worth being in the way."""
    with contextlib.suppress(OSError, subprocess.SubprocessError):
        r = subprocess.run(["systemctl", "is-active", "--quiet", "docker.service"], timeout=10, check=False)
        if r.returncode != 0:
            return False, False
    try:
        r = subprocess.run(["docker", "ps", "-a", "--format", "{{.Names}}"], capture_output=True, text=True, timeout=10, check=False)
    except (OSError, subprocess.SubprocessError):
        return False, False
    if r.returncode != 0:
        return False, "cannot connect" not in (r.stderr or "").lower()
    return True, any(n.startswith("nginx-") for n in r.stdout.split())


def _serve_one(conn, port, scheme):
    """One request, under a deadline as a whole: a slow client holds nothing."""
    conn.settimeout(1)
    until = time.monotonic() + 3
    with conn:
        head = b""
        with contextlib.suppress(OSError):
            while b"\r\n\r\n" not in head and len(head) < 8192 and time.monotonic() < until:
                chunk = conn.recv(2048)
                if not chunk:
                    break
                head += chunk
        with contextlib.suppress(OSError):
            conn.sendall(answer(head, port, scheme))


def _loop(listen_port):
    state = {"sock": None, "checked": 0.0, "nginx": False, "up": False, "hold": 0.0, "scheme": "http", "scheme_at": 0.0}
    while True:
        try:
            _turn(state, listen_port)
        except Exception as e:                                  # noqa: BLE001 (a redirect's fault takes nothing with it)
            print(f"http80: {type(e).__name__}: {e}", flush=True)
            time.sleep(CHECK_S)


def _turn(st, listen_port):
    now = time.monotonic()
    if now - st["checked"] >= CHECK_S:
        st["checked"] = now
        up, st["nginx"] = docker_look()
        # Docker come up: its containers that start with it take their ports
        # first, and it does not try one again that found its port taken.
        if up and not st["up"]:
            st["hold"] = now + HOLD_S
        st["up"] = up
    want = not st["nginx"] and not _paused and now >= st["hold"]
    if not want and st["sock"]:
        st["sock"].close()
        st["sock"] = None
    if want and not st["sock"]:
        s = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        try:
            s.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
            s.bind(("0.0.0.0", listen_port))                        # noqa: S104 (the LAN's way in is the point)
            s.listen(16)
            s.settimeout(1)
            st["sock"] = s
        except OSError:
            s.close()
            time.sleep(CHECK_S)
            return
    if not st["sock"]:
        time.sleep(1)
        return
    try:
        conn, _ = st["sock"].accept()
    except socket.timeout:                                      # TimeoutError from 3.10; the agent's python may be older
        return
    except OSError:
        st["sock"] = None
        return
    port = dashboard_port()
    if now - st["scheme_at"] > 60:
        st["scheme"], st["scheme_at"] = scheme_of(port), now
    _serve_one(conn, port, st["scheme"])


def start():
    """The redirect, on a controller's own machine alone."""
    if not os.path.isfile(os.environ.get("BB_OWN_NODE_MARK", MARK)):
        return False
    threading.Thread(target=_loop, args=(int(os.environ.get("BB_HTTP80_PORT", PORT)),), name="http80", daemon=True).start()
    return True
