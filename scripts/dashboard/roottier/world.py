"""What every module of the root tier stands on: an ordinary account of the
machine it runs on, a temporary folder with a file and a folder that are
root's alone, the agent as a test loads it, and a controller that answers
over a real connection from a thread that was there first (a thread started
inside base.acting_as is the account for good, so none is)."""
import http.server
import json
import os
import pwd
import shutil
import sys
import tempfile
import threading

HERE = os.path.dirname(os.path.abspath(__file__))
DASH = os.path.normpath(os.path.join(HERE, ".."))
UNIT = os.path.join(DASH, "unit")
ROOT = os.path.normpath(os.path.join(DASH, "..", ".."))
for _p in (DASH, UNIT):
    if _p not in sys.path:
        sys.path.insert(0, _p)

SECRET = "root's own, as it was\n"


def account(*but):
    """An ordinary account here, the image's own first: (name, uid, gid)."""
    for name in ("builder", "nobody", "daemon", "bin"):
        if name in but:
            continue
        try:
            pw = pwd.getpwnam(name)
        except KeyError:
            continue
        if pw.pw_uid:
            return name, pw.pw_uid, pw.pw_gid
    raise RuntimeError("this machine has no ordinary account to act as")


class World:
    """A temporary folder anybody may pass through, holding what is root's:
    `secret`, a file only root reads, and `vault`, a folder only root makes
    files in (as /etc is). intact() says both are as they were."""

    def __init__(self, case):
        self.top = tempfile.mkdtemp(prefix="aerie-root-tier.")
        os.chmod(self.top, 0o755)
        case.addCleanup(shutil.rmtree, self.top, True)
        self.secret = os.path.join(self.top, "roots-own")
        with open(self.secret, "w") as f:
            f.write(SECRET)
        os.chmod(self.secret, 0o600)
        self.vault = os.path.join(self.top, "roots-folder")
        os.mkdir(self.vault, 0o755)

    def folder(self, name, who=None, mode=0o755):
        """A folder here, `who`'s (a (uid, gid)) or root's."""
        d = os.path.join(self.top, name)
        os.makedirs(d, exist_ok=True)
        os.chmod(d, mode)
        if who:
            os.chown(d, *who)
        return d

    def intact(self):
        """"" when what is root's is as it was, else what moved."""
        said = []
        try:
            with open(self.secret) as f:
                if f.read() != SECRET:
                    said.append("root's own file was written")
            st = os.lstat(self.secret)
            if (st.st_uid, st.st_gid, st.st_mode & 0o7777) != (0, 0, 0o600):
                said.append(f"root's own file is {st.st_uid}:{st.st_gid} {st.st_mode & 0o7777:o} now")
        except OSError as e:
            said.append(f"root's own file: {e}")
        left = sorted(os.listdir(self.vault))
        if left:
            said.append(f"root's folder holds {', '.join(left)}")
        return "; ".join(said)


class Served:
    """A controller on this machine's loopback, answering a GET with `body`
    and keeping what a POST sent: the agent's own Controller speaks to it,
    so a download and an upload are the real ones. An upload that stopped
    short of the length it announced (the agent says the size, then is
    refused the file) is kept apart, in `cut`, and answered nothing."""

    def __init__(self, case, body=b"from the controller\n"):
        served = self
        self.body, self.posts, self.gets, self.cut = body, [], [], []

        class H(http.server.BaseHTTPRequestHandler):
            def log_message(self, *a):
                pass

            def do_GET(self):
                served.gets.append(self.path)
                self.send_response(200)
                self.send_header("Content-Length", str(len(served.body)))
                self.end_headers()
                self.wfile.write(served.body)

            def do_POST(self):
                n = int(self.headers.get("Content-Length") or 0)
                got = self.rfile.read(n)
                if len(got) != n:
                    served.cut.append(self.path)
                    self.close_connection = True
                    return
                served.posts.append((self.path, got))
                out = json.dumps({"path": "dist/" + self.path.rpartition("name=")[2], "size": len(got), "sha256": "s"}).encode()
                self.send_response(200)
                self.send_header("Content-Length", str(len(out)))
                self.end_headers()
                self.wfile.write(out)

        self.http = http.server.ThreadingHTTPServer(("127.0.0.1", 0), H)
        self.http.handle_error = lambda *a: None       # a connection the agent dropped is not this test's news
        self.url = f"http://127.0.0.1:{self.http.server_address[1]}"
        self.thread = threading.Thread(target=self.http.serve_forever, daemon=True)
        self.thread.start()
        case.addCleanup(self.stop)

    def stop(self):
        self.http.shutdown()
        self.http.server_close()


def agent(tag):
    """The agent's package under a name of this module's own, its log quiet."""
    import agentpkg
    a = agentpkg.load(tag)
    a.log = lambda *x, **k: None
    a.log_once = lambda *x, **k: None
    return a


def as_account(who, argv, **kw):
    """A command run as the account `who` (a (uid, gid)), with none of
    root's groups: what a session or a job of that account is."""
    import subprocess
    return subprocess.run(argv, user=who[0], group=who[1], extra_groups=[], capture_output=True, text=True,
                          check=False, **kw)
