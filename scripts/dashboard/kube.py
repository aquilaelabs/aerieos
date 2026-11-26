"""A space's Kubernetes environments (R281 step 3): where its software goes.

An environment is a name (staging, production, any), one of the clusters an
administrator added on the Clusters page (clusters.py), a namespace on it,
the image registry its builds are pushed to, and when it deploys: by hand,
on every push to a branch, or on a release. One marked production always
asks a person before a session's deploy lands there (step 6).

Saving one prepares its namespace on the cluster with the cluster's own
credential: the namespace made where it is missing, and in it a
ServiceAccount, aerie-deployer, with a Role and a RoleBinding confined to
that namespace alone, so what deploys for a space never reaches another
space's workloads or the cluster's own. A namespace is this space's when it
carries the space's id and this install's mark as labels; one that is
anybody else's (another space, another install, made by hand) is refused,
never taken over. Removing an environment leaves its namespace and what runs
in it on the cluster: this install only stops deploying there.

environments.json: {"mark": hex, "spaces": {space key: [env, ...]}}, the
space's key as repos.key_of names it, so every repository of a space reads
the same list. No credential is kept here.
"""
import re
import secrets
import threading
import time
from pathlib import Path

import kubeclient
import statefile

STATE = None
write_json = None
clusters = None          # the clusters module: client_of, listing
space_id = None          # (space key) -> "P39", the id that never changes
space_of_id = None       # ("P39") -> the space's key, or ""

NAME_RE = re.compile(r"^[a-z0-9]([a-z0-9-]{0,22}[a-z0-9])?$")
NS_RE = re.compile(r"^[a-z0-9]([-a-z0-9]{0,61}[a-z0-9])?$")
REGISTRY_RE = re.compile(r"^[A-Za-z0-9.-]+(:[0-9]{1,5})?(/[a-z0-9._-]+)*$")
BRANCH_RE = re.compile(r"^(?!.*\.\.)(?!/)(?!.*//)[A-Za-z0-9._/-]{1,100}(?<!/)(?<!\.lock)$")
WHEN = ("hand", "push", "release")
DEPLOYER = "aerie-deployer"
KEEP_DEPLOYS = 20        # the deploys an environment keeps, newest first: its history and what a rollback picks from
LABEL_SPACE, LABEL_INSTALL, LABEL_ENV = "aerieos.io/space", "aerieos.io/install", "aerieos.io/env"
# What the deployer may do in its namespace and nowhere else: the workloads,
# their services, configuration and secrets (Helm keeps its releases in
# secrets), jobs, autoscalers, ingresses and disruption budgets, with every
# subresource (logs, exec, scale). No RBAC of its own, so nothing it deploys
# can grant itself more.
RULES = [
    {"apiGroups": ["", "apps", "batch", "autoscaling", "networking.k8s.io", "policy"], "resources": ["*"], "verbs": ["*"]},
    {"apiGroups": ["events.k8s.io"], "resources": ["events"], "verbs": ["get", "list", "watch"]},
]
_lock = threading.Lock()


def configure(**deps):
    globals().update({k: v for k, v in deps.items() if k in globals()})
    if "state" in deps:
        globals()["STATE"] = Path(deps["state"])


def _file():
    return STATE / "environments.json"


_store = statefile.Store(_file, write=lambda: write_json, mode=0o600, cached=True)


def _load():
    d = _store.load()
    d = d if isinstance(d, dict) else {}
    if not isinstance(d.get("spaces"), dict):
        d["spaces"] = {}
    return d


def rev():
    return _store.rev()


def _mark():
    """This install's mark, made and kept the first time it is asked for:
    what tells a namespace it made from one another install made for a
    space of the same id. Called under _lock."""
    d = _load()
    if not re.fullmatch(r"[0-9a-f]{16}", str(d.get("mark") or "")):
        d["mark"] = secrets.token_hex(8)
        _store.save(d)
    return d["mark"]


def _cluster_names():
    return {c["id"]: c["name"] for c in (clusters.listing().get("clusters") or [])} if clusters else {}


def envs(space):
    """A space's environments as the page reads them, each with its
    cluster's name ("" for one no longer kept)."""
    names = _cluster_names()
    return [dict(e, cluster_name=names.get(e.get("cluster"), "")) for e in _load()["spaces"].get(str(space), [])]


def using(cid):
    """The spaces with an environment on this cluster, as keys."""
    return sorted(k for k, rows in _load()["spaces"].items() if any(e.get("cluster") == cid for e in rows))


def _clean(env):
    """An environment as typed, checked: (env, None) or (None, why)."""
    e = env if isinstance(env, dict) else {}
    name = str(e.get("name") or "").strip().lower()
    if not NAME_RE.match(name):
        return None, "name it in lowercase letters, digits and dashes, up to 24"
    ns = str(e.get("namespace") or "").strip().lower()
    if not NS_RE.match(ns):
        return None, "its namespace is lowercase letters, digits and dashes, up to 63"
    if ns.startswith("kube-") or ns in ("default", "kube-system", "kube-public", "kube-node-lease"):
        return None, f"{ns} is the cluster's own namespace: pick one for this space"
    reg = str(e.get("registry") or "").strip().rstrip("/")
    if reg and (not REGISTRY_RE.match(reg) or "." not in reg.split("/")[0] and ":" not in reg.split("/")[0] and reg.split("/")[0] != "localhost"):
        return None, "its registry is a host and a path, such as ghcr.io/owner: each repository's image goes under it by its name"
    when = str(e.get("when") or "hand")
    if when not in WHEN:
        return None, "it deploys by hand, on a push to a branch, or on a release"
    branch = str(e.get("branch") or "").strip()
    if when == "push" and not BRANCH_RE.match(branch):
        return None, "name the branch whose pushes it deploys"
    return {"name": name, "cluster": str(e.get("cluster") or ""), "namespace": ns, "registry": reg, "when": when,
            "branch": branch if when == "push" else "", "production": e.get("production") is True}, None


def _ensure(client, path, body):
    """The object at `path` there, made from `body` where it is missing."""
    try:
        return client.get(f"{path}/{body['metadata']['name']}")
    except kubeclient.KubeError as e:
        if e.status != 404:
            raise
    return client.call("POST", path, body)


def prepare(client, ns, sid, mark, env):
    """The namespace made or found this space's, and its deployer with a
    Role confined to it. Raises KubeError, or ValueError for a namespace
    that is somebody else's."""
    labels = {LABEL_SPACE: sid, LABEL_INSTALL: mark}
    try:
        got = client.get(f"/api/v1/namespaces/{ns}")
    except kubeclient.KubeError as e:
        if e.status != 404:
            raise
        got = client.call("POST", "/api/v1/namespaces", {"apiVersion": "v1", "kind": "Namespace",
                                                          "metadata": {"name": ns, "labels": dict(labels, **{LABEL_ENV: env})}})
    have = (got.get("metadata") or {}).get("labels") or {}
    if have.get(LABEL_SPACE) != sid or have.get(LABEL_INSTALL) != mark:
        raise ValueError(f"the namespace {ns} is already there and is not this space's: pick another")
    meta = {"name": DEPLOYER, "namespace": ns, "labels": labels}
    _ensure(client, f"/api/v1/namespaces/{ns}/serviceaccounts", {"apiVersion": "v1", "kind": "ServiceAccount", "metadata": meta})
    rbac = f"/apis/rbac.authorization.k8s.io/v1/namespaces/{ns}"
    role = {"apiVersion": "rbac.authorization.k8s.io/v1", "kind": "Role", "metadata": meta, "rules": RULES}
    try:
        client.call("PUT", f"{rbac}/roles/{DEPLOYER}", role)
    except kubeclient.KubeError as e:
        if e.status != 404:
            raise
        client.call("POST", f"{rbac}/roles", role)
    _ensure(client, f"{rbac}/rolebindings", {
        "apiVersion": "rbac.authorization.k8s.io/v1", "kind": "RoleBinding", "metadata": meta,
        "roleRef": {"apiGroup": "rbac.authorization.k8s.io", "kind": "Role", "name": DEPLOYER},
        "subjects": [{"kind": "ServiceAccount", "name": DEPLOYER, "namespace": ns}]})


def save(space, env, was="", by=""):
    """An environment added, or the one called `was` changed, once its
    namespace is ready on its cluster: {ok, envs} or {error}."""
    space = str(space or "")
    e, why = _clean(env)
    if why:
        return {"error": why}
    if e["cluster"] not in _cluster_names():
        return {"error": "pick one of the clusters on the Clusters page"}
    with _lock:
        rows = list(_load()["spaces"].get(space, []))
        mark = _mark()
    was = str(was or "")
    i = next((j for j, r in enumerate(rows) if r.get("name") == was), -1) if was else -1
    if was and i < 0:
        return {"error": f"{space} has no environment called {was}"}
    if any(j != i and r.get("name") == e["name"] for j, r in enumerate(rows)):
        return {"error": f"an environment is already called {e['name']}"}
    if any(j != i and r.get("cluster") == e["cluster"] and r.get("namespace") == e["namespace"] for j, r in enumerate(rows)):
        return {"error": f"another environment already deploys to {e['namespace']} on that cluster"}
    old = rows[i] if i >= 0 else {}
    if (old.get("cluster"), old.get("namespace")) != (e["cluster"], e["namespace"]) or old.get("error"):
        client = clusters.client_of(e["cluster"])
        sid = (space_id(space) if space_id else "") or space
        try:
            prepare(client, e["namespace"], sid, mark, e["name"])
        except (kubeclient.KubeError, ValueError) as x:
            return {"error": f"{e['namespace']} was not made ready: {x}"}
        e["ready_at"] = int(time.time())
    else:
        e["ready_at"] = old.get("ready_at", 0)
    e.update(by=str(old.get("by") or by)[:80], at=old.get("at") or int(time.time()))
    if old.get("deploys"):
        e["deploys"] = old["deploys"]
    with _lock:
        d = _load()
        rows = list(d["spaces"].get(space, []))
        j = next((k for k, r in enumerate(rows) if r.get("name") == was), -1) if was else -1
        if j >= 0:
            rows[j] = e
        else:
            rows.append(e)
        d["spaces"][space] = rows
        _store.save(d)
    return {"ok": True, "envs": envs(space)}


def remove(space, name):
    """An environment taken off the space's list; its namespace and what
    runs in it stay on the cluster. {ok, envs} or {error}."""
    space, name = str(space or ""), str(name or "")
    with _lock:
        d = _load()
        rows = d["spaces"].get(space, [])
        if not any(r.get("name") == name for r in rows):
            return {"error": f"{space} has no environment called {name}"}
        d["spaces"][space] = [r for r in rows if r.get("name") != name]
        if not d["spaces"][space]:
            d["spaces"].pop(space)
        _store.save(d)
    return {"ok": True, "envs": envs(space)}


def env_of(space, name):
    """One of a space's environments as kept, or None."""
    return next((e for e in _load()["spaces"].get(str(space), []) if e.get("name") == str(name)), None)


def mint(space, name, seconds=600):
    """A token for the environment's deployer, made by its cluster for this
    one use (TokenRequest) and never kept: {token, expires} or {error}. A
    deploy asks for long enough to build, push and roll out."""
    e = env_of(space, name)
    if not e:
        return {"error": f"{space} has no environment called {name}"}
    client = clusters.client_of(e["cluster"]) if clusters else None
    if not client:
        return {"error": f"{name}'s cluster is no longer kept"}
    seconds = max(600, min(int(seconds), 3600))
    try:
        r = client.call("POST", f"/api/v1/namespaces/{e['namespace']}/serviceaccounts/{DEPLOYER}/token",
                        {"apiVersion": "authentication.k8s.io/v1", "kind": "TokenRequest", "spec": {"expirationSeconds": seconds}})
    except kubeclient.KubeError as x:
        return {"error": f"{name}'s cluster made no token for its deployer: {x}"}
    tok = str((r.get("status") or {}).get("token") or "")
    if not tok:
        return {"error": f"{name}'s cluster made no token for its deployer"}
    return {"token": tok, "expires": str((r.get("status") or {}).get("expirationTimestamp") or "")}


def note_deploy(space, name, rec):
    """A deploy started (deploys.py), kept first on its environment's list
    of the newest KEEP_DEPLOYS: {job, at, by, ref, commit, tag, state}.
    False where the environment is gone."""
    with _lock:
        d = _load()
        e = next((x for x in d["spaces"].get(str(space), []) if x.get("name") == str(name)), None)
        if e is None:
            return False
        e["deploys"] = ([dict(rec)] + [r for r in e.get("deploys") or [] if r.get("job") != rec.get("job")])[:KEEP_DEPLOYS]
        _store.save(d)
    return True


def deploy_ended(space, name, job, state):
    """A deploy's job ended: its row on the environment says how."""
    with _lock:
        d = _load()
        e = next((x for x in d["spaces"].get(str(space), []) if x.get("name") == str(name)), None)
        r = next((r for r in (e or {}).get("deploys") or [] if r.get("job") == job), None)
        if r is None:
            return False
        r.update(state=str(state), ended=int(time.time()))
        _store.save(d)
    return True


def owner_of(labels):
    """The space a namespace's labels name, as a key, where this install
    made it: "" for one that is not ours."""
    labels = labels if isinstance(labels, dict) else {}
    if labels.get(LABEL_INSTALL) != _load().get("mark"):
        return ""
    sid = str(labels.get(LABEL_SPACE) or "")
    return (space_of_id(sid) if space_of_id else "") or ""
