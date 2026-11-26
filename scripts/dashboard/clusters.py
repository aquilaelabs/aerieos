"""The Kubernetes clusters this install may deploy to (R281 step 2): a
cluster an administrator adds once on the Clusters page, under Machines, from
a kubeconfig pasted or uploaded, kept here with its credential sealed under
the install key, never shown again and never handed to a session.

What is kept of a kubeconfig is its current context alone: the API server's
address, its certificate authority, and one way in, a bearer token or a
client certificate and its key. A kubeconfig that signs in through a cloud
CLI (an exec plugin or an auth-provider: EKS, GKE, AKS, kubelogin) is refused
with the way out, a token-based one (the operator, 25 Nov), since a command
run on the controller to sign in is a credential nobody here can hold to
anything. A path where data belongs (certificate-authority: /a/file) is
refused too: the file is on the machine the kubeconfig came from.

Each cluster is a connection (connections.py, kind "cluster", shared by
spaces): who added it and when, its last use, Forget. Its facts (the
version, nodes ready of all, its namespaces and which space owns each by
the aerieos.io/space label) are asked of its API on Add and Test and kept
with when, so the page reads them without a call.
"""
import base64
import json
import os
import re
import secrets
import sys
import threading
import time
from pathlib import Path

_lib = os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "lib")
if os.path.isdir(_lib) and _lib not in sys.path:
    sys.path.insert(0, _lib)
import kubeclient  # noqa: E402
import markup  # noqa: E402
import statefile  # noqa: E402

STATE = None
write_json = None
seal = None             # bytes -> bytes
unseal = None           # bytes -> bytes, or raises
sealing = None          # () -> whether an install key is loaded now
used = None             # (cluster id) -> None: a use, for Connected services
SEALED = "bbseal:"
NAME_RE = re.compile(r"^[A-Za-z0-9][A-Za-z0-9 ._-]{0,60}$")
TEXT_MAX = 64 * 1024
# Said in one sentence with no command in it (a failure line's rule); the
# commands are the page's, in the hint over the field.
TOKEN_WAY = "a kubeconfig with a ServiceAccount's token works"
FLATTEN_WAY = "flatten the kubeconfig so they are written in"
_lock = threading.Lock()


def configure(**deps):
    globals().update({k: v for k, v in deps.items() if k in globals()})
    if "state" in deps:
        globals()["STATE"] = Path(deps["state"])


def _file():
    return STATE / "clusters.json"


_store = statefile.Store(_file, write=lambda: write_json, mode=0o600, cached=True)


def _load():
    d = _store.load()
    return d if isinstance(d, dict) else {}


def _save(d):
    _store.save(d)


def rev():
    return _store.rev()


def _keep(v):
    if v and seal and sealing and sealing():
        return SEALED + base64.b64encode(seal(str(v).encode())).decode()
    return str(v or "")


def _open(v):
    v = str(v or "")
    if v.startswith(SEALED):
        try:
            return unseal(base64.b64decode(v[len(SEALED):])).decode() if unseal else ""
        except Exception:                                   # noqa: BLE001 (Locked, or damaged: no value)
            return ""
    return v


# ---- reading a kubeconfig ------------------------------------------------------

def _b64(v, what):
    try:
        return base64.b64decode(str(v), validate=True).decode()
    except (ValueError, UnicodeDecodeError):
        raise ValueError(f"its {what} is not base64 PEM") from None


def _named(rows, name, key):
    for r in rows or []:
        if isinstance(r, dict) and r.get("name") == name and isinstance(r.get(key), dict):
            return r[key]
    return None


def parse(text):
    """{server, ca, token, cert, key, insecure, context} from a kubeconfig's
    current context, or a ValueError saying what it does not give."""
    text = str(text or "")
    if not text.strip():
        raise ValueError("paste a kubeconfig, or pick its file")
    if len(text) > TEXT_MAX:
        raise ValueError("that is larger than a kubeconfig is")
    try:
        doc = json.loads(text) if text.lstrip().startswith("{") else markup.yaml_load(text)
    except (ValueError, markup.MarkupError) as e:
        raise ValueError(f"it does not read as a kubeconfig: {e}") from None
    if not isinstance(doc, dict) or doc.get("kind", "Config") != "Config":
        raise ValueError("it does not read as a kubeconfig (kind: Config)")
    ctxs = doc.get("contexts") or []
    cur = doc.get("current-context") or (ctxs[0].get("name") if len(ctxs) == 1 and isinstance(ctxs[0], dict) else "")
    ctx = _named(ctxs, cur, "context")
    if not ctx:
        raise ValueError("it names no current context: set current-context to the cluster to add")
    cl, us = _named(doc.get("clusters"), ctx.get("cluster"), "cluster"), _named(doc.get("users"), ctx.get("user"), "user")
    if not cl or not cl.get("server"):
        raise ValueError(f"its context {cur} names no cluster with a server")
    server = str(cl["server"]).strip()
    if not re.match(r"^https?://[A-Za-z0-9.\-\[\]:]+(/[A-Za-z0-9._~/-]*)?$", server):
        raise ValueError(f"its server is not an address: {server[:80]}")
    if cl.get("certificate-authority"):
        raise ValueError(f"its certificate authority is a file on the machine it came from: {FLATTEN_WAY}")
    if us is None:
        raise ValueError(f"its context {cur} names no user")
    if us.get("exec") or us.get("auth-provider"):
        raise ValueError(f"it signs in through a cloud CLI, which AerieOS does not run: {TOKEN_WAY}")
    if us.get("client-certificate") or us.get("client-key") or us.get("tokenFile"):
        raise ValueError(f"its user is files on the machine it came from: {FLATTEN_WAY}")
    out = {"server": server, "context": str(cur), "insecure": bool(cl.get("insecure-skip-tls-verify")),
           "ca": _b64(cl["certificate-authority-data"], "certificate authority") if cl.get("certificate-authority-data") else "",
           "token": str(us.get("token") or ""), "cert": "", "key": ""}
    if us.get("client-certificate-data") or us.get("client-key-data"):
        if not (us.get("client-certificate-data") and us.get("client-key-data")):
            raise ValueError("its user has half of a client certificate: both the certificate and its key are needed")
        out["cert"] = _b64(us["client-certificate-data"], "client certificate")
        out["key"] = _b64(us["client-key-data"], "client key")
    if not (out["token"] or out["cert"]):
        raise ValueError(f"its user carries neither a token nor a client certificate: {TOKEN_WAY}")
    return out


# ---- the clusters ---------------------------------------------------------------

def client_of(cid):
    """A client for a kept cluster, or None."""
    c = _load().get(str(cid))
    if not c:
        return None
    if used:
        used(cid)
    return kubeclient.Client(c["server"], ca=c.get("ca", ""), token=_open(c.get("token")), cert=c.get("cert", ""),
                             key=_open(c.get("key")), insecure=bool(c.get("insecure")))


def _row(cid, c):
    """A cluster as the page reads it: never a credential."""
    return {"id": cid, "name": c.get("name", cid), "server": c.get("server", ""), "context": c.get("context", ""),
            "auth": "token" if c.get("token") else "certificate", "insecure": bool(c.get("insecure")),
            "added_by": c.get("added_by", ""), "added_at": c.get("added_at", 0), "facts": c.get("facts") or {}}


def listing():
    return {"clusters": sorted((_row(k, v) for k, v in _load().items()), key=lambda r: r["name"].lower())}


def _measure(client):
    try:
        return {**kubeclient.facts(client), "at": int(time.time()), "error": ""}
    except kubeclient.KubeError as e:
        return {"at": int(time.time()), "error": str(e)}


def add(text, name, by):
    """A cluster added from a kubeconfig, once its API answered with what the
    credential may read: {ok, cluster} or {error}."""
    name = str(name or "").strip()
    if not NAME_RE.match(name):
        return {"error": "name it: letters, digits, spaces, dots, dashes or underscores, up to 60"}
    try:
        k = parse(text)
    except ValueError as e:
        return {"error": str(e)}
    if any(c.get("name", "").lower() == name.lower() for c in _load().values()):
        return {"error": f"a cluster is already called {name}"}
    facts = _measure(kubeclient.Client(k["server"], ca=k["ca"], token=k["token"], cert=k["cert"], key=k["key"],
                                       insecure=k["insecure"]))
    if facts["error"]:
        return {"error": f"{name} was not added: {facts['error']}"}
    cid = "k_" + secrets.token_hex(4)
    with _lock:
        d = _load()
        d[cid] = {"name": name, "server": k["server"], "context": k["context"], "ca": k["ca"], "insecure": k["insecure"],
                  "token": _keep(k["token"]), "cert": k["cert"], "key": _keep(k["key"]),
                  "added_by": str(by or "")[:80], "added_at": int(time.time()), "facts": facts}
        _save(d)
    return {"ok": True, "cluster": _row(cid, d[cid])}


def test(cid):
    """Its API asked again now; its facts kept. {ok, cluster} or {error}."""
    cl = client_of(cid)
    if not cl:
        return {"error": "no such cluster"}
    facts = _measure(cl)
    with _lock:
        d = _load()
        if cid not in d:
            return {"error": "no such cluster"}
        d[cid]["facts"] = {**(d[cid].get("facts") or {}), **facts} if facts["error"] else facts
        _save(d)
    return {"ok": not facts["error"], "cluster": _row(cid, d[cid]), **({"error": facts["error"]} if facts["error"] else {})}


def rename(cid, name):
    name = str(name or "").strip()
    if not NAME_RE.match(name):
        return {"error": "name it: letters, digits, spaces, dots, dashes or underscores, up to 60"}
    with _lock:
        d = _load()
        if cid not in d:
            return {"error": "no such cluster"}
        if any(k != cid and c.get("name", "").lower() == name.lower() for k, c in d.items()):
            return {"error": f"a cluster is already called {name}"}
        d[cid]["name"] = name
        _save(d)
    return {"ok": True, "cluster": _row(cid, d[cid])}


def forget(cid):
    """The cluster and its credential gone from here; nothing on the cluster
    changes. {ok} or {error}."""
    with _lock:
        d = _load()
        if d.pop(str(cid), None) is None:
            return {"error": "no such cluster"}
        _save(d)
    return {"ok": True}


def seal_all(again=False):
    """Every credential sealed under today's install key: one kept plain once
    there is a key, and every one again after the key changed."""
    if not (seal and sealing and sealing()):
        return 0
    n = 0
    with _lock:
        d = _load()
        for c in d.values():
            for k in ("token", "key"):
                v = str(c.get(k) or "")
                if not v or (v.startswith(SEALED) and not again):
                    continue
                plain = _open(v)
                if plain:
                    c[k] = _keep(plain)
                    n += 1
        if n:
            _save(d)
    return n
