"""k3s on a node: a one-node Kubernetes cluster run as one of
AerieOS's own services, for the spaces to deploy to.

The Library installs it on a node as it installs nginx or the model router
(services.py): one System container, the rancher/k3s image its entry names
by digest, written through containers.create_container and built by a
compose job there, so the Containers page lists it with Up, Down and its
log. Its state is a volume of its own, so Update keeps the cluster.

Traefik and k3s's own load balancer are left off on a node where AerieOS's
nginx runs, so one front door answers on 80 and 443;
on a node without it they are on, and the cluster answers there itself.

The controller's way in is made here, never read back off the node: a
bootstrap token (an id and a secret, kept sealed under the install key)
written as a manifest k3s applies as it starts, a Secret in kube-system and
a ClusterRoleBinding giving the token's group cluster-admin. The cluster's
certificate authority is public, read once from the container when the
cluster is added (its exec job forgotten as it answers). Add k3s on NODE,
on the Clusters page, is then clusters.add with a kubeconfig made from the
two, so a cluster from k3s is kept, tested and forgotten like any other.

  STATE/k3s.json   {nid: {"deployed": t, "token_id": "abc123",
                    "secret": sealed, "traefik": bool, "cluster": cluster id}}
"""
import base64
import json
import re
import secrets
import string
import threading
import time
from pathlib import Path

import services
import statefile
import syscontainer

STATE = None
write_json = None
seal = None
unseal = None
sealing = None
node_list = None
node_name = None
node_addr = None            # nid -> the node's address, as this controller reaches it
nginx_on = None             # nid -> whether AerieOS's nginx is deployed there
run_wait = None             # nodes.run_wait: one command on a node, waited for
clusters = None             # the clusters module
_lock = threading.Lock()
SEALED = "bbseal:"
PORT = 6443
PACK = "k3s"
GROUP = "system:bootstrappers:aerieos"
CA_PATH = "/var/lib/rancher/k3s/server/tls/server-ca.crt"
MANIFEST = "/var/lib/rancher/k3s/server/manifests/aerieos-controller.yaml"
_ALNUM = string.ascii_lowercase + string.digits


def configure(**deps):
    globals().update({k: v for k, v in deps.items() if k in globals()})
    if "state" in deps:
        globals()["STATE"] = Path(deps["state"])


def _file():
    return STATE / "k3s.json"


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


def seal_all(again=False):
    """Each node's token secret sealed under today's install key."""
    if not (seal and sealing and sealing()):
        return 0
    n = 0
    with _lock:
        d = _load()
        for rec in d.values():
            v = str(rec.get("secret") or "")
            if v and (again or not v.startswith(SEALED)):
                plain = _open(v)
                if plain:
                    rec["secret"] = _keep(plain)
                    n += 1
        if n:
            _save(d)
    return n


def record(nid):
    return dict(_load().get(str(nid)) or {})


def node_of_cluster(cid):
    """The node whose k3s is that cluster on the Clusters page, or ""."""
    return next((nid for nid, r in _load().items() if cid and isinstance(r, dict) and r.get("cluster") == cid), "")


def container_name(nid):
    return syscontainer.container_name("k3s", node_name(nid) or nid)


def _rand(n):
    return "".join(secrets.choice(_ALNUM) for _ in range(n))


def _token(rec):
    """The bearer token the controller signs in with: id.secret."""
    return f"{rec.get('token_id', '')}.{_open(rec.get('secret'))}"


# ---- the compose file -----------------------------------------------------------

def manifest_text(rec):
    """What k3s applies as it starts: the controller's bootstrap token and
    the binding that makes its group cluster-admin."""
    tid, secret = rec["token_id"], _open(rec.get("secret"))
    return "\n".join([
        "# Written by AerieOS (k3s.py): the controller's way into this cluster.",
        "apiVersion: v1",
        "kind: Secret",
        "metadata:",
        f"  name: bootstrap-token-{tid}",
        "  namespace: kube-system",
        "type: bootstrap.kubernetes.io/token",
        "stringData:",
        f"  token-id: {json.dumps(tid)}",
        f"  token-secret: {json.dumps(secret)}",
        "  usage-bootstrap-authentication: \"true\"",
        f"  auth-extra-groups: {json.dumps(GROUP)}",
        "---",
        "apiVersion: rbac.authorization.k8s.io/v1",
        "kind: ClusterRoleBinding",
        "metadata:",
        "  name: aerieos-controller",
        "roleRef:",
        "  apiGroup: rbac.authorization.k8s.io",
        "  kind: ClusterRole",
        "  name: cluster-admin",
        "subjects:",
        "  - apiGroup: rbac.authorization.k8s.io",
        "    kind: Group",
        f"    name: {json.dumps(GROUP)}",
        ""])


def compose_text(nid, rec):
    """k3s's compose file: the server, privileged as k3s in a container is,
    its state in a volume, its API on the node's address, the controller's
    manifest beside its own, Traefik and the load balancer off where nginx
    is the node's front door."""
    addr = node_addr(nid) if node_addr else ""
    image = services.images(PACK)
    cmd = ["server", "--tls-san", addr or "127.0.0.1", "--kube-apiserver-arg", "enable-bootstrap-token-auth=true",
           "--write-kubeconfig-mode", "600"]
    if not rec.get("traefik"):
        cmd += ["--disable", "traefik", "--disable", "servicelb"]
    at = f"{addr}:" if addr else ""
    ports = [f"      - \"{at}{PORT}:{PORT}\""]
    if rec.get("traefik"):
        ports += [f"      - \"{at}80:80\"", f"      - \"{at}443:443\""]
    return "\n".join([
        "# Written by AerieOS from the Library's k3s (k3s.py); Install and Update rewrite it.",
        "services:",
        "  k3s:",
        f"    image: {image['k3s']}",
        f"    container_name: {container_name(nid)}",
        "    restart: unless-stopped",
        "    privileged: true",
        f"    command: {json.dumps(cmd)}",
        "    tmpfs:",
        "      - /run",
        "      - /var/run",
        "    ulimits:",
        "      nproc: 65535",
        "      nofile:",
        "        soft: 65535",
        "        hard: 65535",
        "    ports:", *ports,
        "    volumes:",
        "      - k3s_data:/var/lib/rancher/k3s",
        "    configs:",
        "      - source: aerieos_controller",
        f"        target: {MANIFEST}",
        "volumes:",
        "  k3s_data:",
        "configs:",
        "  aerieos_controller:",
        "    content: |",
        syscontainer.indent(manifest_text(rec).replace("$", "$$"), 6),
        ""])


# ---- install, update, remove ---------------------------------------------------

def _fresh(nid):
    """A node's record with a token of its own, made the first time and kept
    after, and Traefik as the node has nginx or not, decided at install."""
    with _lock:
        d = _load()
        rec = dict(d.get(str(nid)) or {})
        if not re.fullmatch(r"[a-z0-9]{6}", str(rec.get("token_id") or "")) or not _open(rec.get("secret")):
            rec["token_id"], rec["secret"] = _rand(6), _keep(_rand(16))
        if "traefik" not in rec:
            rec["traefik"] = not (nginx_on(nid) if nginx_on else False)
        d[str(nid)] = rec
        _save(d)
    return rec


def deploy(nid, containers, devactions, devapp):
    if not (node_addr(nid) if node_addr else ""):
        return {"error": "this node has no address the controller knows, so the cluster's API could not be reached"}
    _fresh(nid)

    def made():
        with _lock:
            d = _load()
            d.setdefault(str(nid), {})["deployed"] = int(time.time())
            _save(d)
    return syscontainer.deploy(nid, container_name(nid), lambda: compose_text(nid, record(nid)),
                               containers, devactions, devapp, node_list, made=made)


def apply(nid, containers, devactions, devapp):
    return syscontainer.apply(container_name(nid), lambda: compose_text(nid, record(nid)), containers, devactions, devapp)


def remove(nid, devactions, devapp):
    """The container taken off the node, and the cluster added from it
    forgotten here: its token meant nothing once the cluster is gone."""
    def gone():
        with _lock:
            d = _load()
            rec = d.pop(str(nid), None) or {}
            _save(d)
        if rec.get("cluster") and clusters:
            clusters.forget(rec["cluster"])
    return syscontainer.remove(container_name(nid), devactions, devapp, gone=gone)


# ---- Add to Clusters -----------------------------------------------------------

def kubeconfig(nid, ca):
    """A kubeconfig for this node's k3s: its address, its authority, the
    controller's token. Made in memory and handed to clusters.add."""
    rec = record(nid)
    server = f"https://{node_addr(nid)}:{PORT}"
    return json.dumps({"apiVersion": "v1", "kind": "Config", "current-context": "k3s",
                       "clusters": [{"name": "k3s", "cluster": {"server": server,
                                                               "certificate-authority-data": base64.b64encode(ca.encode()).decode()}}],
                       "users": [{"name": "aerieos", "user": {"token": _token(rec)}}],
                       "contexts": [{"name": "k3s", "context": {"cluster": "k3s", "user": "aerieos"}}]})


def add_cluster(nid, name, by=""):
    """The k3s on this node added to Clusters under `name`: its authority
    read from the container, then clusters.add, which keeps it once its
    API answers. {ok, cluster} or {error}."""
    rec = record(nid)
    if not rec.get("deployed"):
        return {"error": "k3s is not installed on this node"}
    if rec.get("cluster") and clusters and clusters.listing_one(rec["cluster"]):
        return {"error": "this node's k3s is already on the Clusters page"}
    r = run_wait("k3s:page", nid, ["docker", "exec", container_name(nid), "cat", CA_PATH], timeout=30,
                 forget=True, title="k3s: its certificate authority", docker=True)
    ca = str(r.get("out") or "")
    if r.get("error") or r.get("code") != 0 or "BEGIN CERTIFICATE" not in ca:
        return {"error": "k3s did not say its certificate authority: it may still be starting, so try again in a minute"}
    ca = ca[ca.index("-----BEGIN CERTIFICATE-----"):].strip() + "\n"
    got = clusters.add(kubeconfig(nid, ca), name, by)
    if got.get("ok"):
        with _lock:
            d = _load()
            d.setdefault(str(nid), {})["cluster"] = got["cluster"]["id"]
            _save(d)
    return got


# ---- the Library's service (services.py) ----------------------------------------

REMOVES = "The cluster and everything deployed to it go with it, and it leaves the Clusters page."


def pack():
    """k3s as an official pack: a service a node runs from its Library card."""
    return services.entry({"name": PACK, "label": "k3s", "tier": "official", "platforms": ["linux/amd64", "linux/arm64"], "terms": [],
                           "maker": "SUSE", "credits": [{"name": "k3s", "maker": "SUSE"}], "framework": "2.1",
                           "about": "A one-node Kubernetes cluster on this node for your spaces to deploy to. Once it is up, "
                                    "the Clusters page under Machines adds it with one press. Where this node runs "
                                    "AerieOS's nginx, the cluster's own Traefik is left off so nginx stays the front door.",
                           "service": {"kind": "k3s"}, "config": []})


def service_deployed(nid):
    return bool(record(nid).get("deployed"))


def service_install(nid, by=""):
    containers, devactions, devapp = syscontainer.hands()
    return deploy(nid, containers, devactions, devapp)


def service_remove(nid, by=""):
    _containers, devactions, devapp = syscontainer.hands()
    return remove(nid, devactions, devapp)


def service_update(nid, by=""):
    containers, devactions, devapp = syscontainer.hands()
    return apply(nid, containers, devactions, devapp)


def service_row(nid):
    """Whether this node's k3s is on the Clusters page yet, for its card."""
    rec = record(nid)
    return {"cluster": rec.get("cluster", "") if rec.get("cluster") and clusters and clusters.listing_one(rec["cluster"]) else ""}
