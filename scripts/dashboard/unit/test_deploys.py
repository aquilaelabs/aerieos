"""A repository's deploy (R281 step 4): where its job runs and where its
image goes (imported into a k3s of this install on the node it builds on,
else pushed to the environment's registry or the git host's with the
person's own token); the nodes a deploy is refused on, and why; what ships
read from the commit's tree; nothing secret in the spec's env; a rollback
deploys the last good commit again; the job's end lands on its row; and the
script itself, run against stand-in docker, helm and kubectl, hands the
cluster its token in a kubeconfig file, never an argv."""
import os
import shutil
import stat
import subprocess
import sys
import tarfile
import tempfile
import unittest
from pathlib import Path

sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)), ".."))
import deploys  # noqa: E402

NODE = {"id": "n1", "name": "lab", "kind": "agent", "capabilities": ["docker-host"], "config": {"user": "bb"},
        "reported": {"session": {"user": "builder"}, "toolchains": {"kubernetes": "1.37"}}}


class Deploys(unittest.TestCase):
    def setUp(self):
        self.tmp = Path(tempfile.mkdtemp())
        self.addCleanup(shutil.rmtree, self.tmp, True)
        self.tar = self.tmp / "snap.tar"
        self.files = {"Dockerfile": b"FROM scratch\n", "deploy/chart/Chart.yaml": b"name: shop\n"}
        self.write_tar()
        self.env = {"name": "staging", "cluster": "c1", "namespace": "shop-staging", "registry": "", "deploys": []}
        self.nodes = {"n1": dict(NODE), "n2": dict(NODE, id="n2", name="far")}
        self.k3s_on = ""
        self.line = "https://ada:tok-gh@github.com"
        self.added, self.noted, self.ended = [], [], []
        deploys.configure(remote_url=lambda repo: "https://github.com/Ada/Shop.git", key_of=lambda repo: "shop",
                          nodes_of=lambda repo: ["n1"], node=lambda nid: self.nodes.get(nid),
                          host_only=lambda n: bool((n.get("config") or {}).get("host_only")),
                          own_machine=lambda n: bool((n.get("config") or {}).get("own")),
                          k3s_node_of=lambda cid: self.k3s_on, k3s_container=lambda nid: f"k3s-{self.nodes[nid]['name']}",
                          access=lambda cid: {"server": "https://10.0.0.5:6443", "ca": "CA PEM", "insecure": False},
                          snapshot_at=lambda repo, ref: {"digest": "sha256:" + "a" * 64, "commit": "c0ffee" * 7,
                                                         "tag": "v1.2" if ref == "v1.2" else "", "files": 2, "bytes": 30},
                          snapshot_path=lambda d: self.tar, token_line=lambda repo, uid: self.line,
                          job_add=self.job_add, job=lambda jid, with_log=False: None)
        k = deploys.kube
        was = (k.env_of, k.mint, k.note_deploy, k.deploy_ended)
        k.env_of = lambda space, name: self.env if name == "staging" else None
        k.mint = lambda space, name, seconds=600: {"token": "kube-tok", "expires": ""}
        k.note_deploy = lambda space, name, rec: self.noted.append(rec) or True
        k.deploy_ended = lambda space, name, job, state: self.ended.append((space, name, job, state)) or True
        self.addCleanup(lambda: setattr(k, "env_of", was[0]) or setattr(k, "mint", was[1])
                        or setattr(k, "note_deploy", was[2]) or setattr(k, "deploy_ended", was[3]))

    def write_tar(self):
        import io
        with tarfile.open(self.tar, "w") as t:
            for name, body in self.files.items():
                ti = tarfile.TarInfo(name)
                ti.size = len(body)
                t.addfile(ti, io.BytesIO(body))

    def job_add(self, principal, target, kind, spec, project, source=None):
        self.added.append((principal, target, kind, spec, project, source))
        return {"job": "j1"}

    def test_pushed_to_the_git_hosts_registry_with_the_persons_token(self):
        got = deploys.plan("shop", "staging", "main", "u1")
        self.assertNotIn("error", got, got)
        sp = got["spec"]
        self.assertEqual(got["node"], "n1")
        self.assertEqual(sp["env"]["IMAGE"], "ghcr.io/ada/shop")
        self.assertEqual(sp["env"]["TAG"], "c0ffeec0ffee", "the commit's first twelve")
        self.assertEqual((sp["env"]["SHIP"], sp["env"]["WHAT"], sp["env"]["BUILD"]), ("push", "chart", "1"))
        self.assertEqual((sp["env"]["REGISTRY_HOST"], sp["env"]["REGISTRY_USER"]), ("ghcr.io", "ada"))
        self.assertEqual(sp["secret_env"], {"REGISTRY_PASSWORD": "tok-gh", "KUBE_TOKEN": "kube-tok"})
        self.assertFalse(any("tok" in str(v) for v in sp["env"].values()), "nothing secret in the env a reader sees")
        self.assertEqual(sp["requires"], ["docker-host"])
        self.assertEqual(sp["done"], "deploy")
        self.assertEqual(got["source"]["digest"], "sha256:" + "a" * 64)
        self.line = ""
        self.assertIn("your own token for its git host", deploys.plan("shop", "staging", "main", "u1")["error"])

    def test_a_release_tag_names_the_image(self):
        self.assertEqual(deploys.plan("shop", "staging", "v1.2", "u1")["spec"]["env"]["TAG"], "v1.2")

    def test_a_registry_named_takes_no_git_token(self):
        self.env["registry"] = "registry.lan:5000/team"
        sp = deploys.plan("shop", "staging", "main", "u1")["spec"]
        self.assertEqual(sp["env"]["IMAGE"], "registry.lan:5000/team/shop")
        self.assertNotIn("REGISTRY_PASSWORD", sp["secret_env"])

    def test_k3s_of_this_install_imports_on_its_node(self):
        self.k3s_on = "n1"
        got = deploys.plan("shop", "staging", "main", "u1")
        sp = got["spec"]
        self.assertEqual((got["node"], sp["env"]["SHIP"], sp["env"]["K3S_CONTAINER"]), ("n1", "import", "k3s-lab"))
        self.assertEqual(sp["env"]["IMAGE"], "aerieos.local/shop")
        self.assertEqual(sp["secret_env"], {"KUBE_TOKEN": "kube-tok"}, "no registry, no registry password")
        self.k3s_on = "n2"
        self.assertIn("name a registry", deploys.plan("shop", "staging", "main", "u1")["error"])

    def test_the_nodes_a_deploy_refuses(self):
        for change, word in ((lambda n: n["config"].update(host_only=True), "only hosts"),
                             (lambda n: n["config"].update(own=True), "own machine"),
                             (lambda n: n.update(capabilities=[]), "Docker"),
                             (lambda n: n["reported"]["session"].update(user="bb"), "could read"),
                             (lambda n: n["reported"].update(toolchains={"node": "22"}), "Kubernetes tools")):
            self.nodes["n1"] = {**NODE, "config": dict(NODE["config"]), "reported": {
                "session": dict(NODE["reported"]["session"]), "toolchains": dict(NODE["reported"]["toolchains"])}}
            change(self.nodes["n1"])
            self.assertIn(word, deploys.plan("shop", "staging", "main", "u1").get("error", ""), word)

    def test_what_ships(self):
        self.files = {"deploy/k8s/web.yaml": b"kind: Deployment\n"}
        self.write_tar()
        self.assertEqual(deploys.what_ships(self.tar), {"build": False, "what": "k8s"})
        self.files = {"Dockerfile": b"FROM scratch\n", "README": b"x"}
        self.write_tar()
        self.assertIn("neither a Helm chart", deploys.plan("shop", "staging", "main", "u1")["error"])

    def test_started_noted_rolled_back_and_ended(self):
        got = deploys.start("shop", "staging", "main", "user:ada", "u1", "ada")
        self.assertTrue(got["ok"], got)
        (_, target, kind, spec, project, source), = self.added
        self.assertEqual((target, kind, project), ({"node": "n1"}, "exec", "shop"))
        self.assertEqual((self.noted[0]["job"], self.noted[0]["by"], self.noted[0]["state"]), ("j1", "ada", "queued"))
        self.env["deploys"] = [{"job": "j3", "commit": "new", "state": "failed"},
                               {"job": "j2", "commit": "good", "state": "succeeded"}]
        self.assertTrue(deploys.rollback("shop", "staging", "user:ada", "u1", "ada")["ok"])
        self.assertEqual(self.noted[-1]["ref"], "good", "the last good commit before the newest")
        self.env["deploys"] = [{"job": "j2", "commit": "good", "state": "succeeded"}]
        self.assertIn("no earlier deploy", deploys.rollback("shop", "staging", "user:ada", "u1")["error"])
        deploys.done({"id": "j1", "spec": spec}, "succeeded")
        self.assertEqual(self.ended, [("shop", "staging", "j1", "succeeded")])


class Script(unittest.TestCase):
    """SCRIPT, run by sh against stand-ins that log their argv and what the
    kubeconfig they were handed says."""

    def setUp(self):
        self.tmp = Path(tempfile.mkdtemp())
        self.addCleanup(shutil.rmtree, self.tmp, True)
        self.bin, self.work, self.log = self.tmp / "bin", self.tmp / "work", self.tmp / "log"
        self.bin.mkdir()
        (self.work / "deploy" / "chart").mkdir(parents=True)
        for tool in ("docker", "helm", "kubectl"):
            p = self.bin / tool
            p.write_text('#!/bin/sh\necho "' + tool + ' $*" >> "$LOG"\n'
                         'if [ -n "${KUBECONFIG:-}" ] && [ -f "$KUBECONFIG" ]; then grep -c "token: \\"kube-tok\\"" "$KUBECONFIG" >> "$LOG"; '
                         'stat -c "%a" "$KUBECONFIG" >> "$LOG"; fi\n'
                         'case "$1 $2" in "apply -k") echo deployment.apps/web;; esac\n'
                         'if [ "$1" = login ]; then cat > /dev/null; fi\n')
            p.chmod(p.stat().st_mode | stat.S_IXUSR)

    def run_script(self, **over):
        env = {"PATH": f"{self.bin}:/usr/bin:/bin", "LOG": str(self.log), "KUBE_SERVER": "https://10.0.0.5:6443",
               "KUBE_NAMESPACE": "shop-staging", "RELEASE": "shop", "WHAT": "chart", "BUILD": "1", "SHIP": "push",
               "IMAGE": "ghcr.io/ada/shop", "IMAGE_NAME": "shop", "TAG": "abc", "REGISTRY_HOST": "ghcr.io",
               "REGISTRY_USER": "ada", "K3S_CONTAINER": "", "KUBE_CA": "CA PEM", "KUBE_TOKEN": "kube-tok",
               "REGISTRY_PASSWORD": "tok-gh"} | over
        p = subprocess.run(["sh", "-c", deploys.SCRIPT], cwd=self.work, env=env, capture_output=True, text=True, timeout=60)
        return p, self.log.read_text() if self.log.exists() else ""

    def test_a_chart_pushed_and_upgraded(self):
        p, log = self.run_script()
        self.assertEqual(p.returncode, 0, p.stdout + p.stderr)
        self.assertNotIn("kube-tok", log.replace('"kube-tok"', ""), "the token is in no argv")
        self.assertNotIn("tok-gh", log, "nor the registry password")
        self.assertIn("docker build -t ghcr.io/ada/shop:abc .", log)
        self.assertIn("docker login ghcr.io -u ada --password-stdin", log)
        self.assertIn("docker push ghcr.io/ada/shop:abc", log)
        helm = next(line for line in log.splitlines() if line.startswith("helm "))
        self.assertIn("upgrade --install shop deploy/chart --namespace shop-staging", helm)
        self.assertIn("image.repository=ghcr.io/ada/shop", helm)
        self.assertIn("image.tag=abc", helm)
        lines = log.splitlines()
        i = lines.index(helm)
        self.assertEqual(lines[i + 1:i + 3], ["1", "600"], "helm was handed the token in a file only the job reads")

    def test_manifests_imported_and_waited_on(self):
        shutil.rmtree(self.work / "deploy" / "chart")
        (self.work / "deploy" / "k8s").mkdir()
        (self.work / "deploy" / "k8s" / "web.yaml").write_text("kind: Deployment\n")
        p, log = self.run_script(WHAT="k8s", SHIP="import", IMAGE="aerieos.local/shop", K3S_CONTAINER="k3s-lab")
        self.assertEqual(p.returncode, 0, p.stdout + p.stderr)
        self.assertIn("docker exec -i k3s-lab ctr -n k8s.io images import -", log)
        self.assertNotIn("docker push", log)
        self.assertIn("kubectl apply -k deploy/k8s -o name", log)
        self.assertIn("kubectl rollout status deployment.apps/web --timeout 15m", log)
        k = (self.work / "deploy" / "k8s" / "kustomization.yaml").read_text()
        self.assertIn("- web.yaml", k)
        self.assertIn('newName: "aerieos.local/shop"', k)
        self.assertIn('newTag: "abc"', k)


if __name__ == "__main__":
    unittest.main()
