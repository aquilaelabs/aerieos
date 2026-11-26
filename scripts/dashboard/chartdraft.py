"""Draft from the compose (R281 step 4): a Helm chart written from a
repository's compose file, for a person or a session to read, change and
commit; a deploy uses deploy/chart once it is committed.

Each compose service becomes a Deployment, a Service where it has ports
(named as the service is, so `db:5432` in the app's own settings still
answers), and a PersistentVolumeClaim for each named volume it mounts. The
one service built from the repository's root is the image a deploy builds:
its image is .Values.image, which a deploy sets to the build's. A service
built from anywhere else, or a bind of a host folder, has no counterpart in
a cluster; the draft says so where it stands, in a comment, rather than
guessing. Replicas are values, so Scale and a redeploy agree.

A pure function of the compose file's text: draft(text, name) gives the
files as {path under deploy/chart: text} or {error}. write(root, files)
puts them in the tree, refusing where deploy/chart or deploy/k8s is there.
"""
import os
import re
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "lib"))
import markup  # noqa: E402

NAME_RE = re.compile(r"[^a-z0-9-]+")


def _dns(name):
    """A name Kubernetes takes for an object: lowercase, digits and dashes."""
    return NAME_RE.sub("-", str(name).lower()).strip("-")[:50] or "app"


def _ports(sv):
    """(containerPort, service port) of each port a service publishes or
    exposes, in its order, once each."""
    out = []
    for p in list(sv.get("ports") or []) + list(sv.get("expose") or []):
        if isinstance(p, dict):
            tgt, pub = p.get("target"), p.get("published") or p.get("target")
        else:
            bits = str(p).split("/")[0].split(":")
            tgt, pub = bits[-1], bits[-2] if len(bits) > 1 else bits[-1]
        try:
            tgt, pub = int(str(tgt).split("-")[0]), int(str(pub).split("-")[0])
        except ValueError:
            continue
        if (tgt, pub) not in out:
            out.append((tgt, pub))
    return out


def _env(sv):
    env = sv.get("environment") or {}
    if isinstance(env, list):
        env = {str(x).partition("=")[0]: str(x).partition("=")[2] for x in env}
    return [{"name": str(k), "value": "" if v is None else str(v)} for k, v in env.items()]


def _volumes(sv, named):
    """(mounts, claims, notes): a named volume a claim, a bind a note."""
    mounts, claims, notes = [], [], []
    for v in sv.get("volumes") or []:
        if isinstance(v, dict):
            src, tgt, kind = v.get("source") or "", v.get("target") or "", v.get("type") or "volume"
        else:
            bits = str(v).split(":")
            src, tgt = (bits[0], bits[1]) if len(bits) > 1 else ("", bits[0])
            kind = "bind" if src.startswith((".", "/", "~")) else "volume"
        if not tgt:
            continue
        if kind == "volume" and src in named:
            claims.append(src)
            mounts.append({"name": _dns(src), "mountPath": tgt})
        else:
            notes.append(f"{src or 'an anonymous volume'} at {tgt} is not carried over: give it a volume here")
    return mounts, claims, notes


def draft(text, name):
    """The chart's files from a compose file's text: {path: text} or {error}."""
    try:
        cfg = markup.yaml_load(text)
    except Exception as e:                                                # noqa: BLE001
        return {"error": f"the compose file does not read as YAML: {e}"}
    services = (cfg or {}).get("services") if isinstance(cfg, dict) else None
    if not isinstance(services, dict) or not services:
        return {"error": "the compose file names no services"}
    named = set((cfg.get("volumes") or {}).keys()) if isinstance(cfg.get("volumes"), dict) else set()
    chart = _dns(name)
    built = [n for n, sv in services.items() if isinstance(sv, dict) and sv.get("build") is not None
             and str((sv["build"] if not isinstance(sv["build"], dict) else sv["build"].get("context")) or ".").rstrip("/") in (".", "./", "")]
    app = built[0] if built else ""
    values: dict = {"image": {"repository": chart, "tag": "latest", "pullPolicy": "IfNotPresent"}}
    files = {}
    for sname, sv in services.items():
        if not isinstance(sv, dict):
            continue
        n = _dns(sname)
        key = re.sub(r"[^A-Za-z0-9]", "_", str(sname))
        values[key] = {"replicas": 1}
        notes = []
        if sname == app:
            image = "__IMAGE__"
        elif sv.get("image"):
            image = str(sv["image"])
        else:
            image = f"{n}:latest"
            notes.append(f"{sname} is built from {sv.get('build')}, which a deploy does not build: give it an image")
        labels = {"app.kubernetes.io/name": n, "app.kubernetes.io/instance": "__RELEASE__"}
        c: dict = {"name": n, "image": image}
        if sname == app:
            c["imagePullPolicy"] = "__PULL__"
        if sv.get("entrypoint"):
            c["command"] = sv["entrypoint"] if isinstance(sv["entrypoint"], list) else ["sh", "-c", str(sv["entrypoint"])]
        if sv.get("command"):
            c["args"] = sv["command"] if isinstance(sv["command"], list) else ["sh", "-c", str(sv["command"])]
        ports = _ports(sv)
        if ports:
            c["ports"] = [{"containerPort": t} for t, _ in ports]
        env = _env(sv)
        if env:
            c["env"] = env
        mounts, claims, vnotes = _volumes(sv, named)
        notes += vnotes
        if mounts:
            c["volumeMounts"] = mounts
        pod: dict = {"containers": [c]}
        if claims:
            pod["volumes"] = [{"name": _dns(v), "persistentVolumeClaim": {"claimName": _dns(v)}} for v in claims]
        dep = {"apiVersion": "apps/v1", "kind": "Deployment", "metadata": {"name": n, "labels": labels},
               "spec": {"replicas": f"__REPLICAS_{key}__", "selector": {"matchLabels": labels},
                        "template": {"metadata": {"labels": labels}, "spec": pod}}}
        docs: list = [dep]
        if ports:
            docs.append({"apiVersion": "v1", "kind": "Service", "metadata": {"name": n, "labels": labels},
                         "spec": {"selector": labels,
                                  "ports": [{"name": f"p{p}", "port": p, "targetPort": t} for t, p in ports]}})
        for v in claims:
            docs.append({"apiVersion": "v1", "kind": "PersistentVolumeClaim", "metadata": {"name": _dns(v)},
                         "spec": {"accessModes": ["ReadWriteOnce"], "resources": {"requests": {"storage": "1Gi"}}}})
        head = "".join(f"# {x}\n" for x in [f"From the compose file's {sname}."] + notes)
        body = "---\n".join(markup.yaml_dump(d) for d in docs)
        body = (body.replace('"__IMAGE__"', '"{{ .Values.image.repository }}:{{ .Values.image.tag }}"')
                .replace("__IMAGE__", '"{{ .Values.image.repository }}:{{ .Values.image.tag }}"')
                .replace('"__PULL__"', "{{ .Values.image.pullPolicy }}").replace("__PULL__", "{{ .Values.image.pullPolicy }}")
                .replace('"__RELEASE__"', "{{ .Release.Name }}").replace("__RELEASE__", "{{ .Release.Name }}"))
        body = re.sub(r'"?__REPLICAS_(\w+)__"?', lambda m: "{{ .Values." + m.group(1) + ".replicas }}", body)
        files[f"templates/{n}.yaml"] = head + body
    files["Chart.yaml"] = markup.yaml_dump({"apiVersion": "v2", "name": chart, "description": f"{name}, drafted from its compose file",
                                            "type": "application", "version": "0.1.0", "appVersion": "0.1.0"})
    files["values.yaml"] = ("# A deploy sets image.repository and image.tag to the image it built;\n"
                            "# each service's replicas are its own.\n" + markup.yaml_dump(values))
    return {"files": files, "app": app}


def write(root, files):
    """The chart into the tree at deploy/chart, uncommitted: {ok, paths} or
    {error} where the repository already has what a deploy reads."""
    root = Path(root)
    for have in ("deploy/chart", "deploy/k8s"):
        if (root / have).exists():
            return {"error": f"it already has {have}: a deploy uses that"}
    out = root / "deploy" / "chart"
    paths = []
    for rel, text in sorted(files.items()):
        p = out / rel
        if ".." in Path(rel).parts or not p.resolve().is_relative_to(out.resolve().parent.parent):
            return {"error": f"{rel} is no path in a chart"}
        p.parent.mkdir(parents=True, exist_ok=True)
        p.write_text(text)
        os.chmod(p, 0o644)
        paths.append(f"deploy/chart/{rel}")
    return {"ok": True, "paths": paths}
