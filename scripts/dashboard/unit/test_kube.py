"""A space's Kubernetes environments (R281 step 3): an environment saved
makes its namespace ready on its cluster (the namespace, a ServiceAccount
and a Role and RoleBinding confined to it), a namespace somebody else made
is refused and never taken over, what is typed is checked, and removing one
leaves the cluster as it was."""
import json
import os
import sys
import tempfile
import threading
import unittest
from http.server import BaseHTTPRequestHandler, HTTPServer
from pathlib import Path

sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)), ".."))
import clusters  # noqa: E402
import kube  # noqa: E402


class Api(BaseHTTPRequestHandler):
    """A Kubernetes API that keeps what it is sent: path -> object."""
    objs = {}
    calls = []
    forbid = set()

    def _send(self, code, body):
        raw = json.dumps(body).encode()
        self.send_response(code)
        self.send_header("Content-Type", "application/json")
        self.send_header("Content-Length", str(len(raw)))
        self.end_headers()
        self.wfile.write(raw)

    def _body(self):
        return json.loads(self.rfile.read(int(self.headers.get("Content-Length") or 0)) or b"{}")

    def do_GET(self):
        Api.calls.append(("GET", self.path))
        if self.path == "/version":
            return self._send(200, {"gitVersion": "v1.37.3"})
        if self.path == "/api/v1/nodes":
            return self._send(200, {"items": []})
        if self.path == "/api/v1/namespaces":
            return self._send(200, {"items": [o for p, o in Api.objs.items() if p.startswith("/api/v1/namespaces/") and p.count("/") == 4]})
        o = Api.objs.get(self.path)
        return self._send(200, o) if o else self._send(404, {"message": "not found"})

    def do_POST(self):
        b = self._body()
        Api.calls.append(("POST", self.path))
        if self.path in Api.forbid:
            return self._send(403, {"message": "namespaces is forbidden"})
        if self.path.endswith("/serviceaccounts/aerie-deployer/token"):
            if self.path.replace("/token", "") not in Api.objs:
                return self._send(404, {"message": "serviceaccounts not found"})
            return self._send(201, {"status": {"token": f"minted-{b['spec']['expirationSeconds']}", "expirationTimestamp": "2026-11-26T12:00:00Z"}})
        p = f"{self.path}/{b['metadata']['name']}"
        if p in Api.objs:
            return self._send(409, {"message": "already exists"})
        Api.objs[p] = b
        return self._send(201, b)

    def do_PUT(self):
        b = self._body()
        Api.calls.append(("PUT", self.path))
        if self.path not in Api.objs:
            return self._send(404, {"message": "not found"})
        Api.objs[self.path] = b
        return self._send(200, b)

    def log_message(self, *a):
        pass


def write_json(p, d, mode=0o644):
    Path(p).write_text(json.dumps(d))
    os.chmod(p, mode)


KUBECONFIG = """apiVersion: v1
kind: Config
clusters:
- cluster:
    server: {url}
  name: lab
contexts:
- context:
    cluster: lab
    user: me
  name: lab
current-context: lab
users:
- name: me
  user:
    token: good
"""


class Environments(unittest.TestCase):
    def setUp(self):
        Api.objs, Api.calls, Api.forbid = {}, [], set()
        self.srv = HTTPServer(("127.0.0.1", 0), Api)
        threading.Thread(target=self.srv.serve_forever, daemon=True).start()
        self.addCleanup(self.srv.server_close)
        self.addCleanup(self.srv.shutdown)
        self.d = tempfile.TemporaryDirectory()
        self.addCleanup(self.d.cleanup)
        clusters.configure(state=self.d.name, write_json=write_json, seal=None, unseal=None, sealing=lambda: False,
                           used=None, owner_of=kube.owner_of)
        kube.configure(state=self.d.name, write_json=write_json, clusters=clusters,
                       space_id=lambda k: {"shop": "P7", "lab": "P8"}.get(k, ""),
                       space_of_id=lambda i: {"P7": "shop", "P8": "lab"}.get(i, ""))
        r = clusters.add(KUBECONFIG.format(url=f"http://127.0.0.1:{self.srv.server_address[1]}"), "lab", "ada")
        self.assertTrue(r.get("ok"), r)
        self.cid = r["cluster"]["id"]

    def env(self, **kw):
        return {"name": "staging", "cluster": self.cid, "namespace": "shop-staging", "registry": "ghcr.io/ada/shop",
                "when": "hand", **kw}

    def test_a_saved_environment_has_its_namespace_ready(self):
        r = kube.save("shop", self.env(), by="ada")
        self.assertTrue(r.get("ok"), r)
        ns = Api.objs["/api/v1/namespaces/shop-staging"]
        mark = json.loads((Path(self.d.name) / "environments.json").read_text())["mark"]
        self.assertEqual(ns["metadata"]["labels"], {"aerieos.io/space": "P7", "aerieos.io/install": mark, "aerieos.io/env": "staging"})
        sa = "/api/v1/namespaces/shop-staging/serviceaccounts/aerie-deployer"
        role = "/apis/rbac.authorization.k8s.io/v1/namespaces/shop-staging/roles/aerie-deployer"
        bind = "/apis/rbac.authorization.k8s.io/v1/namespaces/shop-staging/rolebindings/aerie-deployer"
        self.assertIn(sa, Api.objs)
        self.assertEqual(Api.objs[role]["kind"], "Role", "a Role, never a ClusterRole")
        self.assertFalse(any("rbac.authorization.k8s.io" in g for rule in Api.objs[role]["rules"] for g in rule["apiGroups"]),
                         "the deployer may not grant itself more")
        self.assertEqual(Api.objs[bind]["subjects"], [{"kind": "ServiceAccount", "name": "aerie-deployer", "namespace": "shop-staging"}])
        self.assertFalse(any("clusterrole" in p for _, p in Api.calls), "nothing outside the namespace is touched")
        e = kube.envs("shop")[0]
        self.assertEqual((e["name"], e["cluster_name"], e["by"], e["when"]), ("staging", "lab", "ada", "hand"))
        self.assertTrue(e["ready_at"])
        self.assertEqual(kube.using(self.cid), ["shop"])
        # The Clusters page reads it as the space's, after its next Test.
        clusters.test(self.cid)
        got = {n["name"]: n["space"] for n in clusters.listing()["clusters"][0]["facts"]["namespaces"]}
        self.assertEqual(got["shop-staging"], "shop")

    def test_saved_again_it_is_made_ready_again_without_harm(self):
        kube.save("shop", self.env(), by="ada")
        n = len(Api.calls)
        r = kube.save("shop", self.env(when="push", branch="main"), was="staging", by="bea")
        self.assertTrue(r.get("ok"), r)
        self.assertEqual(len(Api.calls), n, "a change that keeps its namespace asks the cluster nothing")
        e = kube.envs("shop")[0]
        self.assertEqual((e["when"], e["branch"], e["by"]), ("push", "main", "ada"), "who added it is kept")
        # Its namespace moved: the new one is made ready, the Role put again.
        r = kube.save("shop", self.env(namespace="shop-stage"), was="staging")
        self.assertTrue(r.get("ok"), r)
        self.assertIn("/api/v1/namespaces/shop-stage", Api.objs)

    def test_a_namespace_somebody_else_made_is_refused(self):
        Api.objs["/api/v1/namespaces/web"] = {"metadata": {"name": "web", "labels": {}}}
        r = kube.save("shop", self.env(namespace="web"))
        self.assertIn("not this space's", r.get("error", ""))
        self.assertNotIn("/api/v1/namespaces/web/serviceaccounts/aerie-deployer", Api.objs, "never taken over")
        self.assertTrue(kube.save("lab", self.env(namespace="lab-staging")).get("ok"))
        r = kube.save("shop", self.env(namespace="lab-staging"))
        self.assertIn("not this space's", r.get("error", ""), "another space's namespace is refused")
        self.assertEqual(kube.envs("shop"), [])

    def test_what_is_typed_is_checked(self):
        bad = [({"name": "Staging!"}, "lowercase"), ({"namespace": "kube-system"}, "cluster's own"),
               ({"namespace": "default"}, "cluster's own"), ({"namespace": "A_B"}, "namespace is"),
               ({"registry": "not a registry"}, "registry"), ({"when": "nightly"}, "by hand"),
               ({"when": "push", "branch": ""}, "branch"), ({"when": "push", "branch": "a..b"}, "branch"),
               ({"cluster": "k_nothere"}, "Clusters page")]
        for kw, said in bad:
            self.assertIn(said, kube.save("shop", self.env(**kw)).get("error", ""), kw)
        self.assertEqual(Api.calls.count(("POST", "/api/v1/namespaces")), 0, "nothing reaches the cluster")
        kube.save("shop", self.env())
        self.assertIn("already called", kube.save("shop", self.env(namespace="other"))["error"])
        self.assertIn("already deploys", kube.save("shop", self.env(name="prod"))["error"])
        self.assertIn("no environment called", kube.save("shop", self.env(), was="nope")["error"])

    def test_a_credential_that_may_not_make_a_namespace_says_so(self):
        Api.forbid = {"/api/v1/namespaces"}
        r = kube.save("shop", self.env())
        self.assertIn("may not do that (403)", r.get("error", ""))
        self.assertEqual(kube.envs("shop"), [], "nothing is kept that is not ready")

    def test_removed_it_leaves_the_cluster_as_it_was(self):
        kube.save("shop", self.env())
        n = len(Api.calls)
        self.assertTrue(kube.remove("shop", "staging").get("ok"))
        self.assertEqual(len(Api.calls), n)
        self.assertIn("/api/v1/namespaces/shop-staging", Api.objs)
        self.assertEqual(kube.envs("shop"), [])
        self.assertIn("no environment", kube.remove("shop", "staging")["error"])

    def test_a_token_minted_for_one_use(self):
        self.assertIn("no environment", kube.mint("shop", "staging")["error"])
        kube.save("shop", self.env())
        self.assertEqual(kube.mint("shop", "staging", 2400)["token"], "minted-2400")
        self.assertEqual(kube.mint("shop", "staging", 5)["token"], "minted-600", "never shorter than a deploy needs")
        self.assertNotIn("minted", (Path(self.d.name) / "environments.json").read_text(), "never kept")
        self.assertEqual(clusters.access(self.cid)["server"], f"http://127.0.0.1:{self.srv.server_address[1]}")
        self.assertNotIn("token", clusters.access(self.cid))

    def test_a_namespace_from_another_install_is_nobodys(self):
        self.assertEqual(kube.owner_of({"aerieos.io/space": "P7", "aerieos.io/install": "0123456789abcdef"}), "")
        kube.save("shop", self.env())
        mark = json.loads((Path(self.d.name) / "environments.json").read_text())["mark"]
        self.assertEqual(kube.owner_of({"aerieos.io/space": "P7", "aerieos.io/install": mark}), "shop")
        self.assertEqual(oct(os.stat(Path(self.d.name) / "environments.json").st_mode & 0o777), "0o600")


if __name__ == "__main__":
    unittest.main()
