"""A Kubernetes API server asked over HTTPS with the standard library alone:
the dashboard is dependency-free, and what it asks a cluster
is a handful of reads and writes on its REST API.

A client is made from what clusters.py keeps of a kubeconfig: the server's
address, its certificate authority (PEM), and one way in, a bearer token or
a client certificate and its key. A client certificate is handed to ssl
through a file of its own (load_cert_chain reads only paths), written 0600
in a private folder for the one call and removed after it. Nothing here
keeps anything.
"""
import contextlib
import json
import re
import os
import ssl
import tempfile
import urllib.error
import urllib.request

TIMEOUT = 10
LOG_MAX = 512 * 1024       # the most of a pod's log one read carries


class KubeError(Exception):
    """What the cluster answered instead, said in a person's words."""

    def __init__(self, words, status=0):
        super().__init__(words)
        self.status = status


class Client:
    def __init__(self, server, ca="", token="", cert="", key="", insecure=False):
        self.server = str(server or "").rstrip("/")
        self.ca, self.token, self.cert, self.key, self.insecure = ca, token, cert, key, insecure

    @contextlib.contextmanager
    def _context(self):
        if self.server.startswith("http://"):
            yield None
            return
        ctx = ssl.create_default_context(cadata=self.ca or None) if self.ca else ssl.create_default_context()
        if self.insecure:
            ctx.check_hostname = False
            ctx.verify_mode = ssl.CERT_NONE
        if not (self.cert and self.key):
            yield ctx
            return
        with tempfile.TemporaryDirectory(prefix="bb-kube-") as d:
            os.chmod(d, 0o700)
            cp, kp = os.path.join(d, "c.pem"), os.path.join(d, "k.pem")
            for p, text in ((cp, self.cert), (kp, self.key)):
                fd = os.open(p, os.O_WRONLY | os.O_CREAT | os.O_EXCL, 0o600)
                with os.fdopen(fd, "w") as fh:
                    fh.write(text)
            ctx.load_cert_chain(cp, kp)
            yield ctx

    def call(self, method, path, body=None, content_type="application/json", raw=False):
        """The JSON the API answers (its text, with `raw`: a pod's log), or a
        KubeError saying why not."""
        data = None if body is None else (body if isinstance(body, bytes) else json.dumps(body).encode())
        req = urllib.request.Request(self.server + path, data=data, method=method)
        req.add_header("Accept", "*/*" if raw else "application/json")
        if data is not None:
            req.add_header("Content-Type", content_type)
        if self.token:
            req.add_header("Authorization", "Bearer " + self.token)
        try:
            with self._context() as ctx, urllib.request.urlopen(req, timeout=TIMEOUT, context=ctx) as r:
                # Whole unless it is a log, which is read to LOG_MAX.
                body_bytes = r.read(LOG_MAX + 1) if raw else r.read()
                kind = r.headers.get("Content-Type") or "no content type"
        except urllib.error.HTTPError as e:
            with e:
                words = _said(e)
            raise KubeError(words, e.code) from None
        except ssl.SSLCertVerificationError as e:
            raise KubeError(f"its certificate is not the one the kubeconfig's authority signs ({e.verify_message or 'not verified'})") from None
        except (urllib.error.URLError, OSError, ssl.SSLError) as e:
            raise KubeError(f"it does not answer at {self.server}: {getattr(e, 'reason', e)}") from None
        if raw:
            return body_bytes.decode("utf-8", "replace")
        try:
            return json.loads(body_bytes or b"{}")
        except ValueError:
            # What it was, never what it said: a body can carry anything.
            raise KubeError(f"it answered {kind.split(';')[0]} ({len(body_bytes)} bytes) to {method} {path.split('?')[0]}, "
                            "not the API's JSON") from None

    def get(self, path):
        return self.call("GET", path)


def _said(e):
    """An API error in a person's words: the status's own message where the
    server gave one."""
    msg = ""
    with contextlib.suppress(Exception):
        msg = json.loads(e.read() or b"{}").get("message") or ""
    if e.code == 401:
        return "it does not know this credential (401): the token or certificate is wrong or has expired"
    if e.code == 403:
        return f"this credential may not do that (403){': ' + msg if msg else ''}"
    if e.code == 404:
        return f"not on this cluster (404){': ' + msg if msg else ''}"
    return f"{e.code}{': ' + msg if msg else ''}"


_UNITS = {"n": 1e-9, "u": 1e-6, "m": 1e-3, "": 1, "k": 1e3, "M": 1e6, "G": 1e9, "T": 1e12, "P": 1e15, "E": 1e18,
          "Ki": 1024, "Mi": 1024 ** 2, "Gi": 1024 ** 3, "Ti": 1024 ** 4, "Pi": 1024 ** 5, "Ei": 1024 ** 6}


def quantity(q):
    """A Kubernetes quantity as a number: cores for CPU ("250m" 0.25,
    "2" 2, "1500000n" 0.0015), bytes for memory ("8Gi", "512Mi",
    "1024k"); 0 for what is not one."""
    m = re.fullmatch(r"\s*([0-9.]+(?:[eE][-+]?[0-9]+)?)\s*([a-zA-Z]*)\s*", str(q or ""))
    if not m or m.group(2) not in _UNITS:
        return 0
    try:
        return float(m.group(1)) * _UNITS[m.group(2)]
    except ValueError:
        return 0


def facts(client):
    """What a cluster is, as its own API says: {version, nodes, ready,
    namespaces: [{name, labels}]}, each namespace's AerieOS labels alone
    (kube.owner_of reads whose it is). Raises KubeError."""
    v = client.get("/version")
    nodes = client.get("/api/v1/nodes").get("items") or []
    ready = sum(1 for n in nodes if any(c.get("type") == "Ready" and c.get("status") == "True"
                                       for c in (n.get("status") or {}).get("conditions") or []))
    ns = client.get("/api/v1/namespaces").get("items") or []
    # What its nodes hold and, where the cluster runs metrics-server (k3s
    # does), what is in use now; a cluster without one says nothing of use.
    cap = {"cpu": sum(quantity((n.get("status") or {}).get("allocatable", {}).get("cpu")) for n in nodes),
           "mem": sum(quantity((n.get("status") or {}).get("allocatable", {}).get("memory")) for n in nodes)}
    use = None
    try:
        items = client.get("/apis/metrics.k8s.io/v1beta1/nodes").get("items") or []
        use = {"cpu": sum(quantity((m.get("usage") or {}).get("cpu")) for m in items),
               "mem": sum(quantity((m.get("usage") or {}).get("memory")) for m in items)}
    except KubeError:
        pass
    return {"version": str(v.get("gitVersion") or ""), "nodes": len(nodes), "ready": ready,
            "cpu": round(cap["cpu"], 2), "mem": int(cap["mem"]),
            **({"cpu_used": round(use["cpu"], 2), "mem_used": int(use["mem"])} if use else {}),
            "namespaces": [{"name": (x.get("metadata") or {}).get("name", ""),
                            "labels": {k: str(v)[:80] for k, v in ((x.get("metadata") or {}).get("labels") or {}).items()
                                       if str(k).startswith("aerieos.io/")}}
                           for x in ns]}
