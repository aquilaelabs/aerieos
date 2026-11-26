# Kubernetes

A space ships its software to Kubernetes in environments of its own: a
cluster an administrator kept on the Clusters page (Machines; see
[machines.md](machines.md)), a namespace on it that AerieOS makes ready,
and when it deploys. Every credential stays on the controller: the
cluster's own is used only to make a namespace ready and to mint, for one
use at a time, a token for the namespace's deployer; a session never holds
a kubeconfig.

**A cluster to start with.** k3s, from the Library, is a one-node cluster on
a node, added to the Clusters page with one press (Add k3s on NODE). Traefik
and its load balancer are left off where the node has nginx, which keeps
the front door. A cluster from anywhere else is added from its kubeconfig;
one that signs in through a cloud provider's command-line tool is refused,
with the way out said: a ServiceAccount's token.

**A space's environments.** Once a cluster is kept, each space's settings
carry a **Deploy** section: its environments as records (staging,
production, any name), each a cluster, a namespace on it, the registry its
images are pushed to, and when it deploys (by hand, on a push to a branch,
on a release); one marked production always asks a person before a
session's deploy lands. An environment's Save makes its namespace ready
with the cluster's own credential first: the namespace, labeled with the
space's id (`aerieos.io/space`) and this install's mark
(`aerieos.io/install`), and in it a ServiceAccount, `aerie-deployer`, with a
Role and a RoleBinding confined to that namespace (its workloads, services,
configuration, secrets, jobs and ingresses; no RBAC of its own), so what
deploys for one space never reaches another's or the cluster's own. A
namespace anybody else made (another space, another install, a hand) is
refused, never taken over. Remove takes an environment off the space's list
and leaves its namespace and what runs in it on the cluster. Changing them
is Space settings Write on the space with Clusters Read on the cluster
picked; seeing them is Deploy Read.

**A deploy.** What a repository sends to an environment is its own: a Helm
chart in `deploy/chart` or manifests in `deploy/k8s`, as committed at the
branch, tag or commit picked (never a working tree's edits), with the image
built from the `Dockerfile` at its root and tagged with the tag or the
commit's first twelve characters. The Deploy section says, for each
repository of the space, which it has; one with neither but a compose file
offers **Draft from the compose**, which writes a chart into its tree,
uncommitted, to read and commit: each service a Deployment, a Service named
as the service where it has ports, a claim for each named volume, the one
built from the root on the deploy's image, and what has no counterpart in a
cluster (another build context, a bind of a host folder) said in a comment
where it stands. A deploy is one job on a node the repository builds on
that runs Docker: the image built and pushed to the environment's registry,
or, where none is named, to the git host's own (GitHub's `ghcr.io`, a
Gitea's or a Forgejo's address) with the deploying person's own token for
it; on a k3s cluster this install runs on a node the repository builds on,
with no registry named, the image is imported straight into the cluster.
Then `helm upgrade --install` with the image set as `image.repository` and
`image.tag` and `--wait`, or the manifests applied with the image they name
by the repository's name swapped for the one built, each rollout waited on.
The cluster's token is made for that one deploy, confined to the
environment's namespace, and travels with the registry's password beside
the job, never in what a reader of the job sees, and gone from the job's
record when it ends; on the node they are a file only the job reads. A
deploy is refused on a node whose sessions run as its jobs' account, on a
hosting-only node and on the controller's own machine. Each deploy is kept
on its environment (who, the ref, the commit, the tag, how it ended), and
Roll back deploys the last one that succeeded before the newest again.
Deploying is Deploy Write on the space; drafting a chart is the
repository's Write.

**The Kubernetes view.** A notebook's Ship group carries a **Kubernetes**
view: each of the space's environments a section, its status how many of
its workloads are ready, with **Deploy** (a branch, tag or commit, followed
as a job) and **Roll back** on its bar. Each workload (Deployment,
StatefulSet, DaemonSet) says ready of desired, the version its image is
tagged with and where it answers (an Ingress's address, a load balancer's,
a node port, or its Service's name inside the cluster), with **Restart**
and **Scale**; its pods say their state, restarts and node, and a pod's
**Logs** opens in the dock, its end read again every few seconds, and a
running pod's **Shell** opens there too, under a container's Shell's rule
(a person who may deploy there; an administrator alone where the space's
Run its container is Deny), the controller the cluster's client. Its last
deploys are listed under it. Everything the view reads and does goes
through the environment's own deployer, a token made for its namespace and
kept in memory for its life, so the view sees and touches that namespace
and nothing else. Reading it is Deploy Read on the space; its presses are
Deploy Write.

**From a session.** A session reaches its space's environments with `aerie
k8s`, relayed by the controller, which holds every credential: a session
never holds a kubeconfig. `aerie k8s status` and `aerie k8s logs ENV POD`
read at any setting; `aerie k8s deploy ENV [REF] --why "..."` and `aerie k8s
rollback ENV --why "..."` are under the space's **Agents may: Deploy to
Kubernetes**, deny by default: ask puts each to the space's owner (or any
administrator) on the bell, auto starts it, and an environment marked
production asks a person whatever it says. Handing a session that is Deploy
Write's.

**Testing from a session.** A session tests what it deploys in an
environment kept for it: one on a node's own k3s (a cluster added from a
node running it), named test or whatever the space likes, which `aerie k8s
deploy test` ships to and `aerie k8s status test` and `aerie k8s logs` read
back. A throwaway cluster of a session's own is not offered: kind needs a
Docker daemon, and a session has none of its own, so the Kubernetes tools'
kind is for a person whose Docker is theirs.

**When it deploys.** An environment that deploys on a push to a branch is
deployed at the commit a push leaves there, a push from the Git view or one
`aerie git push` relays; one that deploys on a release, at the release's
tag once it is pushed. A person's push or release starts it; a session's
follows Deploy to Kubernetes as `aerie k8s deploy` does, and production asks
a person either way. A push made outside AerieOS starts nothing.
