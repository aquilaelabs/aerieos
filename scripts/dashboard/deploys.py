"""A repository's build sent to one of its space's Kubernetes environments
(R281 step 4).

A deploy is one exec job on a node that holds the repository and runs
Docker: the tree as committed at the branch, tag or commit picked
(workspace.snapshot_at, never a working tree's edits), the image built from
its Dockerfile and tagged with the tag or the commit, sent where the cluster
can pull it, and the repository's own description of what runs applied in
the environment's namespace:

  * deploy/chart, a Helm chart: helm upgrade --install, the image set as
    image.repository and image.tag (the values `helm create` writes), and
    --wait, so the job ends when the rollout has;
  * deploy/k8s, plain manifests or a kustomization: applied with the image
    the manifests name by the repository's own name swapped for the one
    built, each Deployment, StatefulSet and DaemonSet then waited on.

Where the image goes. An environment that names a registry is pushed to it;
one that names none is pushed to the repository's git host's (GitHub's
ghcr.io, a Gitea's or a Forgejo's own address), logged in with the deploying
person's own token for that host. An environment on a k3s cluster this
install runs, with no registry named, needs none: the job runs on that k3s
node and imports the image straight into the cluster's containerd.

Nothing secret rides the spec's env or an argv: the cluster token is made
for this one deploy (kube.mint, a TokenRequest for the environment's
deployer, confined to its namespace) and travels with the registry password
in the job's secret_env, which no reader of the job is handed and which the
row forgets when the job ends (nodes.forget_secrets). On the node the script
writes the kubeconfig into a directory only the job reads and removes it.

Refused on a node where a session could read the job's environment: one
whose sessions run as the account its jobs run as, the controller's own
machine (where Docker is root's, not the jobs account's), and a hosting-only
node, which builds nothing.

Each deploy is kept on its environment (kube.note_deploy): the job, who, the
ref, the commit, the image tag and how it ended. Roll back is a deploy of the
last one that succeeded before the newest, built from its own commit.
"""
import re
import tarfile
import time
import urllib.parse

import forges
import kube

# Handed by the server (configure): every one a function, so the module is
# testable with stand-ins.
remote_url = None         # (repo) -> origin's address, or ""
key_of = None             # (repo) -> the space's key
nodes_of = None           # (repo) -> the node ids it builds on, its primary first
node = None               # (nid) -> the node's row, or None
host_only = None          # (row) -> whether it hosts containers and nothing else
own_machine = None        # (row) -> whether it is the controller's own machine
k3s_node_of = None        # (cluster id) -> the node a k3s cluster of this install runs on, or ""
k3s_container = None      # (nid) -> the k3s container's name on that node
access = None             # (cluster id) -> {server, ca, insecure} or None
snapshot_at = None        # (repo, ref) -> {digest, commit, files, bytes} or {error}
snapshot_path = None      # (digest) -> the snapshot's tar, or None
token_line = None         # (repo, uid) -> "https://user:token@host" for the person's git host token, or ""
job_add = None            # nodes.job_add
job = None                # nodes.job
tree = None               # (repo) -> its working tree, a Path
compose_of = None         # (repo) -> the compose file its containers are made from, a Path, or None

SINCE_LIMIT = 3600        # the longest a deploy may run, and its token's life
IMPORT_PREFIX = "aerieos.local"

# The one script a deploy runs, from the snapshot's root, with what it needs
# in its environment (plan() says each). sh, not bash: any node has it.
SCRIPT = r"""set -eu
umask 077
w="$(mktemp -d)"
trap 'rm -rf "$w"' EXIT INT TERM
if [ -n "${KUBE_CA:-}" ]; then
  printf '%s\n' "$KUBE_CA" > "$w/ca.crt"
  tls="certificate-authority: $w/ca.crt"
else
  tls="insecure-skip-tls-verify: true"
fi
cat > "$w/kubeconfig" <<EOF
apiVersion: v1
kind: Config
clusters:
- name: cluster
  cluster:
    server: "$KUBE_SERVER"
    $tls
users:
- name: deployer
  user:
    token: "$KUBE_TOKEN"
contexts:
- name: env
  context: {cluster: cluster, user: deployer, namespace: "$KUBE_NAMESPACE"}
current-context: env
EOF
unset KUBE_TOKEN KUBE_CA
export KUBECONFIG="$w/kubeconfig"
image="$IMAGE:$TAG"
if [ "$BUILD" = 1 ]; then
  echo "building $image"
  docker build -t "$image" .
  if [ "$SHIP" = import ]; then
    echo "importing $image into the cluster on this node"
    docker save "$image" | docker exec -i "$K3S_CONTAINER" ctr -n k8s.io images import -
  else
    export DOCKER_CONFIG="$w/docker"
    mkdir -p "$DOCKER_CONFIG"
    if [ -n "${REGISTRY_PASSWORD:-}" ]; then
      printf '%s' "$REGISTRY_PASSWORD" | docker login "$REGISTRY_HOST" -u "$REGISTRY_USER" --password-stdin
    fi
    unset REGISTRY_PASSWORD
    echo "pushing $image"
    docker push "$image"
  fi
fi
unset REGISTRY_PASSWORD
if [ "$WHAT" = chart ]; then
  set -- helm upgrade --install "$RELEASE" deploy/chart --namespace "$KUBE_NAMESPACE" \
    --wait --timeout 15m --history-max 10
  if [ "$BUILD" = 1 ]; then
    set -- "$@" --set-string "image.repository=$IMAGE" --set-string "image.tag=$TAG"
    if [ "$SHIP" = import ]; then set -- "$@" --set-string image.pullPolicy=IfNotPresent; fi
  fi
  echo "helm upgrade --install $RELEASE"
  "$@"
else
  if [ -f deploy/k8s/kustomization.yaml ] || [ -f deploy/k8s/kustomization.yml ]; then
    k=deploy/.aerieos-deploy
    mkdir -p "$k"
    echo "resources: [../k8s]" > "$k/kustomization.yaml"
  else
    k=deploy/k8s
    { echo "resources:"; for f in deploy/k8s/*.yaml deploy/k8s/*.yml; do
        [ -f "$f" ] && echo "- ${f#deploy/k8s/}"; done; } > "$k/kustomization.yaml"
  fi
  if [ "$BUILD" = 1 ]; then
    { echo "images:"; echo "- name: \"$IMAGE_NAME\""; echo "  newName: \"$IMAGE\""; echo "  newTag: \"$TAG\""
      if [ "$IMAGE_NAME" != "$IMAGE" ]; then echo "- name: \"$IMAGE\""; echo "  newTag: \"$TAG\""; fi
    } >> "$k/kustomization.yaml"
  fi
  echo "kubectl apply"
  kubectl apply -k "$k" -o name > "$w/applied"
  cat "$w/applied"
  grep -E '^(deployment|statefulset|daemonset)\.apps/' "$w/applied" | while read -r r; do
    kubectl rollout status "$r" --timeout 15m
  done
fi
echo "deployed $image to $KUBE_NAMESPACE"
"""


def configure(**deps):
    globals().update({k: v for k, v in deps.items() if k in globals()})


def _slug(repo):
    return re.sub(r"[^a-z0-9._-]+", "-", str(repo).lower()).strip("-._") or "app"


def what_ships(digest_path):
    """What a snapshot holds to deploy, read from its tar: {build, what} or
    {error}. `build` is whether a Dockerfile is at its root; `what` is chart
    or k8s."""
    names = set()
    try:
        with tarfile.open(digest_path) as t:
            names = {m.name.lstrip("./") for m in t if m.isfile()}
    except (OSError, tarfile.TarError) as e:
        return {"error": f"the snapshot could not be read: {e}"}
    if "deploy/chart/Chart.yaml" in names:
        what = "chart"
    elif any(re.fullmatch(r"deploy/k8s/[^/]+\.ya?ml", n) for n in names):
        what = "k8s"
    else:
        return {"error": "it has neither a Helm chart in deploy/chart nor manifests in deploy/k8s"}
    return {"build": "Dockerfile" in names, "what": what}


def _node_why(n):
    """Why a deploy may not run on this node, or ""."""
    name = n.get("name") or n.get("id")
    if n.get("kind") != "agent":
        return f"{name} runs no agent"
    if host_only and host_only(n):
        return f"{name} only hosts containers and builds nothing"
    if own_machine and own_machine(n):
        return f"{name} is the controller's own machine, whose Docker is root's alone"
    if "docker-host" not in (n.get("capabilities") or []):
        return f"{name} does not run Docker for jobs"
    se = (n.get("reported") or {}).get("session") or {}
    jobs_as = (n.get("config") or {}).get("user") or "bb"
    if se.get("user") and se.get("user") == jobs_as:
        return f"{name} runs its sessions as the account its jobs run as, so a session could read a deploy's token"
    tc = (n.get("reported") or {}).get("toolchains")
    if isinstance(tc, dict) and tc and not tc.get("kubernetes"):
        return f"{name} has no Kubernetes tools: install them from the Library with {name} picked"
    return ""


def _where(repo, env):
    """Where the job runs and where its image goes: {node, ship, image,
    registry} or {error}."""
    mine = [x for x in (nodes_of(repo) or []) if x]
    k3s_on = k3s_node_of(env.get("cluster")) if k3s_node_of else ""
    if k3s_on and not env.get("registry"):
        # No registry and the cluster is a k3s of this install: built where
        # it runs and imported, which needs that node to be one the
        # repository builds on.
        n = node(k3s_on)
        if not n:
            return {"error": "the k3s node of that cluster is no longer enrolled"}
        if k3s_on not in mine:
            return {"error": f"{env['name']} runs on k3s on {n.get('name')}, where {repo} does not build: "
                             "name a registry for it, or add k3s on one of the repository's nodes"}
        why = _node_why(n)
        return {"error": why} if why else {"node": k3s_on, "ship": "import", "registry": "",
                                           "image": f"{IMPORT_PREFIX}/{_slug(repo)}"}
    if env.get("registry"):
        reg = env["registry"]
        image, host = f"{reg}/{_slug(repo)}", reg.split("/")[0]
    else:
        host, image = forges.image_of(remote_url(repo) if remote_url else "")
        if not image:
            return {"error": f"{repo}'s git host keeps no images this knows of: name a registry for {env['name']}"}
    whys = []
    for nid in mine:
        n = node(nid)
        why = _node_why(n) if n else f"{nid} is no longer enrolled"
        if not why:
            return {"node": nid, "ship": "push", "registry": host, "image": image}
        whys.append(why)
    return {"error": whys[0] if whys else f"{repo} has no node to build on: set one in its settings"}


def plan(repo, env_name, ref, uid):
    """Everything a deploy needs before it is queued, checked: {spec, source,
    node, rec} or {error}. Asks the cluster for the deployer's token last,
    once everything else holds."""
    space = key_of(repo)
    env = kube.env_of(space, env_name)
    if not env:
        return {"error": f"{repo}'s space has no environment called {env_name}"}
    acc = access(env.get("cluster")) if access else None
    if not acc:
        return {"error": f"{env_name}'s cluster is no longer kept"}
    where = _where(repo, env)
    if where.get("error"):
        return where
    snap = snapshot_at(repo, ref)
    if snap.get("error"):
        return snap
    got = what_ships(snapshot_path(snap["digest"]))
    if got.get("error"):
        return {"error": f"{repo} at {ref}: {got['error']}"}
    tag = snap.get("tag") or snap["commit"][:12]
    env_vars = {"KUBE_SERVER": acc["server"], "KUBE_NAMESPACE": env["namespace"], "RELEASE": _slug(repo),
                "WHAT": got["what"], "BUILD": "1" if got["build"] else "0", "SHIP": where["ship"],
                "IMAGE": where["image"], "IMAGE_NAME": _slug(repo), "TAG": tag,
                "REGISTRY_HOST": where["registry"], "REGISTRY_USER": "",
                "K3S_CONTAINER": k3s_container(where["node"]) if where["ship"] == "import" and k3s_container else ""}
    secret = {}
    if acc.get("ca"):
        env_vars["KUBE_CA"] = acc["ca"]
    if got["build"] and where["ship"] == "push" and not env.get("registry"):
        # The git host's own registry, with the person's own token for it.
        line = token_line(repo, uid) if token_line else ""
        u = urllib.parse.urlsplit(line) if line else None
        if not u or not u.password:
            return {"error": f"give {repo} your own token for its git host in its settings: "
                             f"its image is pushed to {where['registry']} with it"}
        env_vars["REGISTRY_USER"] = urllib.parse.unquote(u.username or "")
        secret["REGISTRY_PASSWORD"] = urllib.parse.unquote(u.password)
    tok = kube.mint(space, env_name, SINCE_LIMIT)
    if tok.get("error"):
        return tok
    secret["KUBE_TOKEN"] = tok["token"]
    rec = {"at": int(time.time()), "ref": str(ref), "commit": snap["commit"], "tag": tag, "state": "queued",
           "image": f"{where['image']}:{tag}" if got["build"] else "", "repo": repo}
    spec = {"argv": ["sh", "-c", SCRIPT], "timeout": SINCE_LIMIT, "project": repo, "requires": ["docker-host"],
            "env": env_vars, "secret_env": secret, "done": "deploy",
            "deploy": {"space": space, "env": env_name, "ref": str(ref), "commit": snap["commit"], "tag": tag}}
    source = {"digest": snap["digest"], "project": repo, "files": snap["files"], "bytes": snap["bytes"]}
    return {"spec": spec, "source": source, "node": where["node"], "rec": rec}


def start(repo, env_name, ref, principal, uid, by=""):
    """A deploy queued: {ok, job, node} or {error}."""
    p = plan(repo, env_name, ref, uid)
    if p.get("error"):
        return p
    r = job_add(principal, {"node": p["node"]}, "exec", p["spec"], repo, source=p["source"])
    if r.get("error"):
        return r
    kube.note_deploy(key_of(repo), env_name, p["rec"] | {"job": r["job"], "by": str(by)[:80]})
    return {"ok": True, "job": r["job"], "node": p["node"], "tag": p["rec"]["tag"], "commit": p["rec"]["commit"]}


def rollback(repo, env_name, principal, uid, by=""):
    """The last deploy that succeeded before the newest, deployed again from
    its own commit: {ok, job, ...} or {error}."""
    env = kube.env_of(key_of(repo), env_name)
    if not env:
        return {"error": f"{repo}'s space has no environment called {env_name}"}
    rows = [d for d in env.get("deploys") or [] if d.get("repo", repo) == repo]
    good = [d for d in rows[1:] if d.get("state") == "succeeded"]
    if not good:
        return {"error": f"{env_name} has no earlier deploy of {repo} that succeeded to go back to"}
    return start(repo, env_name, good[0]["commit"], principal, uid, by)


def done(j, state):
    """A deploy's job ended (nodes.on_done): its row on the environment says
    how. A failure's line is the job's own."""
    d = ((j or {}).get("spec") or {}).get("deploy") or {}
    if d.get("space") and d.get("env"):
        kube.deploy_ended(d["space"], d["env"], (j or {}).get("id"), state)


def history(space, env_name):
    """An environment's deploys, newest first, each with its job's state
    where the row has not heard the end yet (a job canceled before it ran)."""
    env = kube.env_of(space, env_name) or {}
    out = []
    for d in env.get("deploys") or []:
        row = dict(d)
        if row.get("state") in ("queued", "running") and job:
            jj = job(row.get("job"), with_log=False) or {}
            row["state"] = jj.get("state") or row["state"]
        out.append(row)
    return out


def repo_facts(repo):
    """What a repository deploys, read off its working tree: {name, ships:
    chart, k8s or "", compose: whether it has a compose file to draft a
    chart from}."""
    root = tree(repo) if tree else None
    ships = ""
    if root is not None and (root / "deploy" / "chart" / "Chart.yaml").is_file():
        ships = "chart"
    elif root is not None and (root / "deploy" / "k8s").is_dir() and any(
            p.suffix in (".yaml", ".yml") for p in (root / "deploy" / "k8s").iterdir()):
        ships = "k8s"
    return {"name": repo, "ships": ships, "compose": bool(compose_of and compose_of(repo))}


def draft(repo, name=""):
    """Draft from the compose: a chart written into the tree at deploy/chart,
    uncommitted. {ok, paths, app} or {error}."""
    import chartdraft
    f = compose_of(repo) if compose_of else None
    if not f:
        return {"error": f"{repo} has no compose file to draft from"}
    try:
        text = f.read_text(encoding="utf-8")
    except OSError as e:
        return {"error": f"its compose file could not be read: {e.strerror or e}"}
    got = chartdraft.draft(text, name or repo)
    if got.get("error"):
        return got
    wrote = chartdraft.write(tree(repo), got["files"])
    return wrote if wrote.get("error") else wrote | {"app": got["app"]}
