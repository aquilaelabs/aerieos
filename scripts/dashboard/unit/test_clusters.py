"""The Kubernetes clusters (R281 step 2): a kubeconfig's current context
read, a cloud CLI's sign-in refused with the way out (the operator, 25 Nov),
paths where data belongs refused, and a cluster added, asked again, renamed
and forgotten against a stub API server, its credential never in what the
page reads."""
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
import kubeclient  # noqa: E402

B64 = lambda s: base64.b64encode(s.encode()).decode()  # noqa: E731


def kubeconfig(server, user, cluster_extra=""):
    return f"""apiVersion: v1
kind: Config
clusters:
- cluster:
    server: {server}
{cluster_extra}  name: lab
contexts:
- context:
    cluster: lab
    user: me
  name: lab
current-context: lab
users:
- name: me
  user:
{user}"""


class Parse(unittest.TestCase):
    def test_a_token_and_a_client_certificate(self):
        k = clusters.parse(kubeconfig("https://10.0.0.5:6443", "    token: abc.def\n",
                                      f"    certificate-authority-data: {B64('-----CA-----')}\n"))
        self.assertEqual((k["server"], k["token"], k["ca"], k["context"]), ("https://10.0.0.5:6443", "abc.def", "-----CA-----", "lab"))
        k = clusters.parse(kubeconfig("https://k.example:443",
                                      f"    client-certificate-data: {B64('CERT')}\n    client-key-data: {B64('KEY')}\n"))
        self.assertEqual((k["cert"], k["key"], k["token"]), ("CERT", "KEY", ""))

    def test_a_cloud_cli_sign_in_is_refused_with_the_way_out(self):
        for user in ("    exec:\n      command: aws\n", "    auth-provider:\n      name: gcp\n"):
            with self.assertRaises(ValueError) as e:
                clusters.parse(kubeconfig("https://eks.example", user))
            self.assertIn("cloud CLI", str(e.exception))
            self.assertIn("ServiceAccount's token", str(e.exception))
            self.assertNotIn("`", str(e.exception), "one sentence, no command in it")

    def test_paths_where_data_belongs_and_nothing_to_sign_in_with(self):
        cases = [(kubeconfig("https://x", "    token: t\n", "    certificate-authority: /home/me/ca.crt\n"), "flatten"),
                 (kubeconfig("https://x", "    client-certificate: /home/me/c.crt\n    client-key: /home/me/c.key\n"), "flatten"),
                 (kubeconfig("https://x", "    username: me\n"), "neither a token"),
                 (kubeconfig("https://x", f"    client-certificate-data: {B64('C')}\n"), "half"),
                 ("kind: Pod\n", "kind: Config"),
                 ("", "paste")]
        for text, said in cases:
            with self.assertRaises(ValueError) as e:
                clusters.parse(text)
            self.assertIn(said, str(e.exception), text[:40])


class Stub(BaseHTTPRequestHandler):
    token = "good"
    answers = {
        "/version": {"gitVersion": "v1.37.3+k3s1"},
        "/api/v1/nodes": {"items": [
            {"status": {"conditions": [{"type": "Ready", "status": "True"}]}},
            {"status": {"conditions": [{"type": "Ready", "status": "False"}]}}]},
        "/api/v1/namespaces": {"items": [{"metadata": {"name": "default"}},
                                         {"metadata": {"name": "shop-staging", "labels": {"aerieos.io/space": "P7", "aerieos.io/install": "ours"}}},
                                         {"metadata": {"name": "theirs", "labels": {"aerieos.io/space": "P7", "aerieos.io/install": "another"}}}]},
    }

    def do_GET(self):
        if self.headers.get("Authorization") != "Bearer " + Stub.token:
            body, code = {"message": "Unauthorized"}, 401
        else:
            body, code = Stub.answers.get(self.path, {"message": "not found"}), 200 if self.path in Stub.answers else 404
        raw = json.dumps(body).encode()
        self.send_response(code)
        self.send_header("Content-Type", "application/json")
        self.send_header("Content-Length", str(len(raw)))
        self.end_headers()
        self.wfile.write(raw)

    def log_message(self, *a):
        pass


def write_json(p, d, mode=0o644):
    Path(p).write_text(json.dumps(d))
    os.chmod(p, mode)


class Kept(unittest.TestCase):
    def setUp(self):
        self.srv = HTTPServer(("127.0.0.1", 0), Stub)
        threading.Thread(target=self.srv.serve_forever, daemon=True).start()
        self.addCleanup(self.srv.server_close)
        self.addCleanup(self.srv.shutdown)
        self.url = f"http://127.0.0.1:{self.srv.server_address[1]}"
        self.d = tempfile.TemporaryDirectory()
        self.addCleanup(self.d.cleanup)
        self.uses = []
        clusters.configure(state=self.d.name, write_json=write_json, seal=lambda b: b[::-1], unseal=lambda b: b[::-1],
                           sealing=lambda: True, used=self.uses.append,
                           owner_of=lambda lb: "shop" if (lb or {}).get("aerieos.io/install") == "ours" else "")

    def test_added_asked_renamed_and_forgotten(self):
        r = clusters.add(kubeconfig(self.url, "    token: good\n"), "lab", "ada")
        self.assertTrue(r.get("ok"), r)
        c = r["cluster"]
        self.assertEqual((c["facts"]["version"], c["facts"]["ready"], c["facts"]["nodes"]), ("v1.37.3+k3s1", 1, 2))
        self.assertIn({"name": "shop-staging", "space": "shop"}, c["facts"]["namespaces"])
        self.assertIn({"name": "theirs", "space": ""}, c["facts"]["namespaces"],
                      "a namespace another install made for a space of the same id is nobody's here")
        kept = json.loads((Path(self.d.name) / "clusters.json").read_text())
        self.assertTrue(kept[c["id"]]["token"].startswith(clusters.SEALED), "the token is kept sealed")
        self.assertNotIn("good", json.dumps(clusters.listing()), "the page never reads the credential")
        self.assertEqual(oct(os.stat(Path(self.d.name) / "clusters.json").st_mode & 0o777), "0o600")
        self.assertIn("already called", clusters.add(kubeconfig(self.url, "    token: good\n"), "LAB", "ada")["error"])
        self.assertTrue(clusters.test(c["id"])["ok"])
        self.assertEqual(self.uses, [c["id"]], "a test is a use")
        self.assertEqual(clusters.rename(c["id"], "lab two")["cluster"]["name"], "lab two")
        self.assertTrue(clusters.forget(c["id"])["ok"])
        self.assertEqual(clusters.listing()["clusters"], [])

    def test_a_credential_the_cluster_refuses_is_not_kept(self):
        r = clusters.add(kubeconfig(self.url, "    token: wrong\n"), "lab", "ada")
        self.assertIn("401", r["error"])
        self.assertEqual(clusters.listing()["clusters"], [])

    def test_one_that_answers_no_longer_says_why(self):
        r = clusters.add(kubeconfig(self.url, "    token: good\n"), "lab", "ada")
        Stub.token = "rotated"
        self.addCleanup(setattr, Stub, "token", "good")
        t = clusters.test(r["cluster"]["id"])
        self.assertFalse(t["ok"])
        self.assertIn("401", t["cluster"]["facts"]["error"])
        self.assertEqual(t["cluster"]["facts"]["version"], "v1.37.3+k3s1", "what it said before is kept beside why it does not now")

    def test_nothing_answering_is_said(self):
        with self.assertRaises(kubeclient.KubeError) as e:
            kubeclient.Client("http://127.0.0.1:9", token="t").get("/version")
        self.assertIn("does not answer", str(e.exception))


if __name__ == "__main__":
    unittest.main()
