"""What runs in a space's Kubernetes environment, and the presses on it
(R281 step 5): the notebook's Kubernetes view.

Every read and press goes through the environment's own deployer, a token
kube.mint makes for its ServiceAccount, kept in memory for its life less a
minute and never written anywhere; never the cluster's own credential. So
Kubernetes itself holds the view to the environment's namespace: a workload
in another space's namespace, or the cluster's own, is not this view's to
see or touch, whatever a bug here would ask for.

  status(space, env)    each workload (Deployment, StatefulSet, DaemonSet)
                        with ready of desired, the version its image is
                        tagged with, its pods (state, restarts, node) and
                        the address its Service or Ingress answers at
  restart(...)          a rollout restart, as kubectl rollout restart does
  scale(...)            a Deployment's or a StatefulSet's replicas
  logs(...)             the end of a pod's log
"""
import re
import threading
import time
import urllib.parse

import kube
import kubeclient

clusters = None           # the clusters module: access
_tokens = {}              # (space, env) -> (token, good until)
_lock = threading.Lock()
KINDS = {"deployment": "deployments", "statefulset": "statefulsets", "daemonset": "daemonsets"}
SCALES = ("deployment", "statefulset")
REPLICAS_MAX = 50
NAME_RE = re.compile(r"^[a-z0-9]([-a-z0-9.]{0,251}[a-z0-9])?$")


def configure(**deps):
    globals().update({k: v for k, v in deps.items() if k in globals()})


def _client(space, env_name):
    """(client, env) signed in as the environment's deployer, or (None, why)."""
    env = kube.env_of(space, env_name)
    if not env:
        return None, f"no environment called {env_name}"
    acc = clusters.access(env.get("cluster")) if clusters else None
    if not acc:
        return None, f"{env_name}'s cluster is no longer kept"
    key = (str(space), str(env_name))
    with _lock:
        tok, until = _tokens.get(key, ("", 0))
    if not tok or until < time.time():
        got = kube.mint(space, env_name, 600)
        if got.get("error"):
            return None, got["error"]
        tok = got["token"]
        with _lock:
            _tokens[key] = (tok, time.time() + 540)
    return kubeclient.Client(acc["server"], ca=acc.get("ca", ""), token=tok, insecure=acc.get("insecure")), env


def forget(space=None):
    """The tokens kept for a space's environments (all of them, with none
    named) let go: an environment removed or changed reads afresh."""
    with _lock:
        for k in [k for k in _tokens if space is None or k[0] == str(space)]:
            _tokens.pop(k, None)


def _matches(selector, labels):
    sel = (selector or {}).get("matchLabels") or {}
    return bool(sel) and all((labels or {}).get(k) == v for k, v in sel.items())


def _tag(image):
    """The version an image reference names: its tag, else its digest's head."""
    image = str(image or "")
    if "@" in image:
        return image.split("@", 1)[1].split(":")[-1][:12]
    last = image.rsplit("/", 1)[-1]
    return last.split(":", 1)[1] if ":" in last else "latest"


def _pod(p):
    st = p.get("status") or {}
    cs = st.get("containerStatuses") or []
    waiting = next((c["state"]["waiting"].get("reason") for c in cs if (c.get("state") or {}).get("waiting")), "")
    gone = (p.get("metadata") or {}).get("deletionTimestamp")
    return {"name": (p.get("metadata") or {}).get("name", ""), "state": "Terminating" if gone else waiting or st.get("phase") or "Unknown",
            "ready": sum(1 for c in cs if c.get("ready")), "of": len(cs) or len((p.get("spec") or {}).get("containers") or []),
            "restarts": sum(int(c.get("restartCount") or 0) for c in cs), "node": (p.get("spec") or {}).get("nodeName") or "",
            "containers": [c.get("name") for c in (p.get("spec") or {}).get("containers") or []],
            "started": st.get("startTime") or ""}


def _addresses(labels, services, ingresses):
    """Where a workload answers: an Ingress's host and path for a Service that
    selects its pods, a load balancer's address, a node port, or the
    Service's own name inside the cluster."""
    out = []
    for s in services:
        sel, spec = (s.get("spec") or {}).get("selector") or {}, s.get("spec") or {}
        if not sel or not all(labels.get(k) == v for k, v in sel.items()):
            continue
        name = (s.get("metadata") or {}).get("name", "")
        for ing in ingresses:
            tls = bool((ing.get("spec") or {}).get("tls"))
            for rule in (ing.get("spec") or {}).get("rules") or []:
                for path in ((rule.get("http") or {}).get("paths") or []):
                    if ((path.get("backend") or {}).get("service") or {}).get("name") == name:
                        out.append(f"{'https' if tls else 'http'}://{rule.get('host') or '*'}{path.get('path') or '/'}")
        lb = ((s.get("status") or {}).get("loadBalancer") or {}).get("ingress") or []
        for port in spec.get("ports") or []:
            if lb:
                out.append(f"{lb[0].get('ip') or lb[0].get('hostname')}:{port.get('port')}")
            elif spec.get("type") == "NodePort" and port.get("nodePort"):
                out.append(f"port {port['nodePort']} on each node")
            else:
                out.append(f"{name}:{port.get('port')} inside the cluster")
    return list(dict.fromkeys(out))


def status(space, env_name):
    """The environment's workloads as the view draws them: {namespace,
    workloads} or {error}."""
    c, env = _client(space, env_name)
    if c is None:
        return {"error": env}
    ns = env["namespace"]
    try:
        pods = c.get(f"/api/v1/namespaces/{ns}/pods").get("items") or []
        services = c.get(f"/api/v1/namespaces/{ns}/services").get("items") or []
        try:
            ingresses = c.get(f"/apis/networking.k8s.io/v1/namespaces/{ns}/ingresses").get("items") or []
        except kubeclient.KubeError:
            ingresses = []
        rows = []
        for kind, plural in KINDS.items():
            for w in c.get(f"/apis/apps/v1/namespaces/{ns}/{plural}").get("items") or []:
                meta, spec, st = w.get("metadata") or {}, w.get("spec") or {}, w.get("status") or {}
                tpl = ((spec.get("template") or {}).get("metadata") or {}).get("labels") or {}
                ctrs = ((spec.get("template") or {}).get("spec") or {}).get("containers") or []
                if kind == "daemonset":
                    ready, want = st.get("numberReady") or 0, st.get("desiredNumberScheduled") or 0
                else:
                    ready, want = st.get("readyReplicas") or 0, spec.get("replicas") if spec.get("replicas") is not None else 1
                rows.append({"kind": kind, "name": meta.get("name", ""), "ready": ready, "desired": want,
                             "version": _tag(ctrs[0].get("image")) if ctrs else "", "image": ctrs[0].get("image", "") if ctrs else "",
                             "pods": [_pod(p) for p in pods if _matches(spec.get("selector"), (p.get("metadata") or {}).get("labels"))],
                             "addresses": _addresses(tpl, services, ingresses), "scales": kind in SCALES})
    except kubeclient.KubeError as e:
        return {"error": f"{env_name}'s cluster did not answer: {e}"}
    rows.sort(key=lambda r: (r["kind"] != "deployment", r["name"]))
    return {"namespace": ns, "workloads": rows}


def _workload(kind, name):
    if kind not in KINDS:
        return "", "a workload is a deployment, a statefulset or a daemonset"
    if not NAME_RE.match(str(name or "")):
        return "", "name a workload in the environment"
    return KINDS[kind], ""


def restart(space, env_name, kind, name):
    """Its pods made again one by one, as kubectl rollout restart does:
    {ok} or {error}."""
    plural, why = _workload(kind, name)
    if why:
        return {"error": why}
    c, env = _client(space, env_name)
    if c is None:
        return {"error": env}
    at = time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime())
    try:
        c.call("PATCH", f"/apis/apps/v1/namespaces/{env['namespace']}/{plural}/{name}",
               {"spec": {"template": {"metadata": {"annotations": {"kubectl.kubernetes.io/restartedAt": at}}}}},
               content_type="application/merge-patch+json")
    except kubeclient.KubeError as e:
        return {"error": f"{name} was not restarted: {e}"}
    return {"ok": True}


def scale(space, env_name, kind, name, replicas):
    """A Deployment's or a StatefulSet's replicas set: {ok} or {error}."""
    plural, why = _workload(kind, name)
    if why:
        return {"error": why}
    if kind not in SCALES:
        return {"error": "a daemonset runs one pod on each node and is not scaled"}
    try:
        n = int(replicas)
    except (TypeError, ValueError):
        return {"error": "replicas is a whole number"}
    if not 0 <= n <= REPLICAS_MAX:
        return {"error": f"replicas is from 0 to {REPLICAS_MAX}"}
    c, env = _client(space, env_name)
    if c is None:
        return {"error": env}
    try:
        c.call("PATCH", f"/apis/apps/v1/namespaces/{env['namespace']}/{plural}/{name}/scale",
               {"spec": {"replicas": n}}, content_type="application/merge-patch+json")
    except kubeclient.KubeError as e:
        return {"error": f"{name} was not scaled: {e}"}
    return {"ok": True, "replicas": n}


def logs(space, env_name, pod, container="", tail=500):
    """The end of a pod's log: {text} or {error}."""
    if not NAME_RE.match(str(pod or "")) or (container and not NAME_RE.match(str(container))):
        return {"error": "name a pod in the environment"}
    c, env = _client(space, env_name)
    if c is None:
        return {"error": env}
    q = {"tailLines": str(max(10, min(int(tail or 500), 5000))), "timestamps": "true"}
    if container:
        q["container"] = container
    try:
        text = c.call("GET", f"/api/v1/namespaces/{env['namespace']}/pods/{pod}/log?{urllib.parse.urlencode(q)}", raw=True)
    except kubeclient.KubeError as e:
        return {"error": f"{pod}'s log was not read: {e}"}
    return {"text": text[-kubeclient.LOG_MAX:]}
