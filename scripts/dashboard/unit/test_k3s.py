"""k3s on a node (R281 step 1): its compose file runs the image its entry
names, privileged, its state in a volume, its API on the node's address;
Traefik and the load balancer are off where the node has nginx; the
controller's bootstrap token is made once, kept sealed and written as the
manifest k3s applies; and Add to Clusters makes a kubeconfig of the node's
address, the authority read from the container and that token, kept by
clusters.add once the API answers it."""
import base64
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
import k3s  # noqa: E402
import markup  # noqa: E402

CA = "-----BEGIN CERTIFICATE-----\nMIIBdzCCAR2gAwIBAgIBADAKBggqhkjOPQQDAjAjMSEwHwYDVQQDDBhrM3Mtc2VydmVyLWNh\n-----END CERTIFICATE-----\n"


def write_json(p, d, mode=0o644):
    Path(p).write_text(json.dumps(d))
    os.chmod(p, mode)


class Api(BaseHTTPRequestHandler):
    token = ""

    def do_GET(self):
        ok = self.headers.get("Authorization") == "Bearer " + Api.token
        body = {"/version": {"gitVersion": "v1.37.2+k3s1"}, "/api/v1/nodes": {"items": []},
                "/api/v1/namespaces": {"items": []}}.get(self.path) if ok else {"message": "Unauthorized"}
        raw = json.dumps(body or {}).encode()
        self.send_response(200 if ok and body else 401 if not ok else 404)
        self.send_header("Content-Type", "application/json")
        self.send_header("Content-Length", str(len(raw)))
        self.end_headers()
        self.wfile.write(raw)

    def log_message(self, *a):
        pass


class K3s(unittest.TestCase):
    def setUp(self):
        self.d = tempfile.TemporaryDirectory()
        self.addCleanup(self.d.cleanup)
        self.nginx = False
        self.asked = []
        clusters.configure(state=self.d.name, write_json=write_json, seal=lambda b: b[::-1], unseal=lambda b: b[::-1],
                           sealing=lambda: True, used=None, owner_of=None)
        k3s.configure(state=self.d.name, write_json=write_json, seal=lambda b: b[::-1], unseal=lambda b: b[::-1],
                      sealing=lambda: True, node_list=lambda: [{"id": "n1", "name": "lab"}], node_name=lambda nid: "lab",
                      node_addr=lambda nid: "127.0.0.1", nginx_on=lambda nid: self.nginx, run_wait=self.run_wait,
                      clusters=clusters)
        self.images = {"k3s": "rancher/k3s:v1.37.2-k3s1@sha256:" + "a" * 64}
        self._was = k3s.services.images
        k3s.services.images = lambda name: dict(self.images) if name == "k3s" else {}
        self.addCleanup(setattr, k3s.services, "images", self._was)

    def run_wait(self, principal, nid, argv, **kw):
        self.asked.append((nid, argv, kw))
        return {"code": 0, "out": "some line first\n" + CA}

    def test_the_compose_file(self):
        rec = k3s._fresh("n1")
        y = markup.yaml_load(k3s.compose_text("n1", rec))
        sv = y["services"]["k3s"]
        self.assertEqual(sv["image"], self.images["k3s"], "the image its entry names, by its digest")
        self.assertTrue(sv["privileged"])
        self.assertIn("k3s_data:/var/lib/rancher/k3s", sv["volumes"], "its state is a volume, kept across Update")
        self.assertIn("127.0.0.1:6443:6443", sv["ports"])
        self.assertIn("enable-bootstrap-token-auth=true", sv["command"])
        self.assertIn("127.0.0.1", sv["command"][sv["command"].index("--tls-san") + 1])
        self.assertNotIn("traefik", sv["command"], "no nginx on the node: Traefik answers")
        self.assertIn("127.0.0.1:80:80", sv["ports"])
        man = y["configs"]["aerieos_controller"]["content"]
        self.assertEqual(sv["configs"][0]["target"], k3s.MANIFEST)
        secret = k3s._open(json.loads((Path(self.d.name) / "k3s.json").read_text())["n1"]["secret"])
        self.assertIn(f"bootstrap-token-{rec['token_id']}", man)
        self.assertIn(json.dumps(secret), man)
        self.assertIn("cluster-admin", man)
        kept = json.loads((Path(self.d.name) / "k3s.json").read_text())["n1"]
        self.assertTrue(kept["secret"].startswith(k3s.SEALED), "the secret is kept sealed")
        self.assertEqual(oct(os.stat(Path(self.d.name) / "k3s.json").st_mode & 0o777), "0o600")
        self.assertEqual(k3s._fresh("n1")["token_id"], rec["token_id"], "made once, kept after")

    def test_nginx_on_the_node_keeps_the_front_door(self):
        self.nginx = True
        sv = markup.yaml_load(k3s.compose_text("n1", k3s._fresh("n1")))["services"]["k3s"]
        self.assertEqual([sv["command"][i + 1] for i, a in enumerate(sv["command"]) if a == "--disable"], ["traefik", "servicelb"])
        self.assertEqual(sv["ports"], ["127.0.0.1:6443:6443"], "80 and 443 are nginx's")

    def test_added_to_clusters_with_its_own_token(self):
        self.assertIn("not installed", k3s.add_cluster("n1", "lab k3s")["error"])
        rec = k3s._fresh("n1")
        with k3s._lock:
            d = k3s._load()
            d["n1"]["deployed"] = 1
            k3s._save(d)
        Api.token = f"{rec['token_id']}.{k3s._open(rec['secret'])}"
        srv = HTTPServer(("127.0.0.1", 0), Api)
        threading.Thread(target=srv.serve_forever, daemon=True).start()
        self.addCleanup(srv.server_close)
        self.addCleanup(srv.shutdown)
        # The stub answers over plain HTTP; the kubeconfig names https on 6443.
        made = json.loads(k3s.kubeconfig("n1", CA))
        self.assertEqual(made["clusters"][0]["cluster"]["server"], "https://127.0.0.1:6443")
        self.assertEqual(base64.b64decode(made["clusters"][0]["cluster"]["certificate-authority-data"]).decode(), CA)
        self.assertEqual(made["users"][0]["user"]["token"], Api.token)
        k3s.PORT, was = srv.server_address[1], k3s.PORT
        self.addCleanup(setattr, k3s, "PORT", was)
        real = k3s.kubeconfig
        k3s.kubeconfig = lambda nid, ca: real(nid, ca).replace("https://", "http://")
        self.addCleanup(setattr, k3s, "kubeconfig", real)
        got = k3s.add_cluster("n1", "lab k3s", "ada")
        self.assertTrue(got.get("ok"), got)
        (nid, argv, kw), = self.asked
        self.assertEqual(argv, ["docker", "exec", "k3s-lab", "cat", k3s.CA_PATH])
        self.assertTrue(kw.get("forget"), "the read of its authority leaves no job behind")
        self.assertEqual(k3s.record("n1")["cluster"], got["cluster"]["id"])
        self.assertIn("already on the Clusters page", k3s.add_cluster("n1", "again")["error"])
        self.assertEqual(k3s.service_row("n1"), {"cluster": got["cluster"]["id"]})

    def test_a_hosting_only_node_answers_its_authority_read_alone(self):
        import nodes
        self.assertEqual(tuple(nodes.K3S_CA_READ), ("cat", k3s.CA_PATH), "one path, said in both places")
        ok = ["docker", "exec", "k3s-lab", "cat", k3s.CA_PATH]
        self.assertTrue(nodes.host_exec_ok("exec", {"argv": ok}))
        for bad in (["docker", "exec", "k3s-lab", "cat", "/etc/shadow"], ["docker", "exec", "web-1", "cat", k3s.CA_PATH],
                    ["docker", "exec", "k3s-lab", "sh", "-c", "id"], ok + ["/etc/shadow"]):
            self.assertFalse(nodes.host_exec_ok("exec", {"argv": bad}), bad)

    def test_a_cluster_still_starting_says_so(self):
        k3s._fresh("n1")
        with k3s._lock:
            d = k3s._load()
            d["n1"]["deployed"] = 1
            k3s._save(d)
        k3s.configure(run_wait=lambda *a, **kw: {"code": 1, "out": "cat: no such file"})
        self.assertIn("still be starting", k3s.add_cluster("n1", "lab")["error"])


if __name__ == "__main__":
    unittest.main()
