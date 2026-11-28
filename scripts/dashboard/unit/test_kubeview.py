"""The Kubernetes view: the version an image names, a pod's
state as a person reads it (a container waiting says why), where a
workload answers (an Ingress, a load balancer, a node port, or its
Service inside the cluster), and Scale held to what can be scaled."""
import os
import sys
import unittest

sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)), ".."))
import kubeexec  # noqa: E402
import kubeview  # noqa: E402
import termws  # noqa: E402


class View(unittest.TestCase):
    def test_the_version_an_image_names(self):
        self.assertEqual(kubeview._tag("ghcr.io/ada/shop:v1.2"), "v1.2")
        self.assertEqual(kubeview._tag("localhost:5000/shop"), "latest", "a registry's port is no tag")
        self.assertEqual(kubeview._tag("nginx@sha256:" + "ab" * 32), "abababababab")

    def test_a_pods_state(self):
        p = {"metadata": {"name": "web-1"}, "spec": {"nodeName": "lab", "containers": [{"name": "web"}]},
             "status": {"phase": "Running", "containerStatuses": [
                 {"name": "web", "ready": False, "restartCount": 4, "state": {"waiting": {"reason": "CrashLoopBackOff"}}}]}}
        got = kubeview._pod(p)
        self.assertEqual((got["state"], got["ready"], got["of"], got["restarts"], got["node"]), ("CrashLoopBackOff", 0, 1, 4, "lab"))
        p["metadata"]["deletionTimestamp"] = "2026-11-26T00:00:00Z"
        self.assertEqual(kubeview._pod(p)["state"], "Terminating")

    def test_where_a_workload_answers(self):
        labels = {"app": "web"}
        svc = {"metadata": {"name": "web"}, "spec": {"selector": {"app": "web"}, "ports": [{"port": 8080}]}}
        other = {"metadata": {"name": "db"}, "spec": {"selector": {"app": "db"}, "ports": [{"port": 5432}]}}
        ing = {"spec": {"tls": [{}], "rules": [{"host": "shop.lan", "http": {"paths": [
            {"path": "/", "backend": {"service": {"name": "web"}}}]}}]}}
        self.assertEqual(kubeview._addresses(labels, [svc, other], []), ["web:8080 inside the cluster"])
        self.assertEqual(kubeview._addresses(labels, [svc], [ing])[0], "https://shop.lan/")
        lb = dict(svc, status={"loadBalancer": {"ingress": [{"ip": "10.0.0.9"}]}})
        self.assertEqual(kubeview._addresses(labels, [lb], []), ["10.0.0.9:8080"])
        np = {"metadata": {"name": "web"}, "spec": {"type": "NodePort", "selector": {"app": "web"}, "ports": [{"port": 80, "nodePort": 30080}]}}
        self.assertEqual(kubeview._addresses(labels, [np], []), ["port 30080 on each node"])

    def test_scale_held_to_what_scales(self):
        self.assertIn("not scaled", kubeview.scale("s", "staging", "daemonset", "agent", 2)["error"])
        self.assertIn("from 0 to", kubeview.scale("s", "staging", "deployment", "web", 51)["error"])
        self.assertIn("whole number", kubeview.scale("s", "staging", "deployment", "web", "two")["error"])
        self.assertIn("deployment, a statefulset", kubeview.restart("s", "staging", "pod", "web")["error"])
        self.assertIn("name a pod", kubeview.logs("s", "staging", "../etc")["error"])


class Watch(unittest.TestCase):
    """The bell's rows: a pod stuck at once, a workload short only once it
    has been short longer than a rollout takes, gone when it recovers."""

    def test_stuck_short_and_recovered(self):
        crash = {"workloads": [{"name": "web", "desired": 2, "ready": 1, "pods": [{"state": "CrashLoopBackOff"}, {"state": "Running"}]}]}
        self.assertEqual(kubeview.judge(crash, 0, 1000)[0], ["web: CrashLoopBackOff"])
        short = {"workloads": [{"name": "web", "desired": 2, "ready": 1, "pods": [{"state": "Running"}]}]}
        bad, since = kubeview.judge(short, 0, 1000)
        self.assertEqual((bad, since), ([], 1000), "short, but not yet longer than a rollout takes")
        self.assertEqual(kubeview.judge(short, since, 1000 + kubeview.SETTLE_S)[0], ["web: 1 of 2 ready"])
        well = {"workloads": [{"name": "web", "desired": 2, "ready": 2, "pods": []}]}
        self.assertEqual(kubeview.judge(well, since, 5000), ([], 0))

    def test_rows_for_who_may_read(self):
        kubeview._health.clear()
        self.addCleanup(kubeview._health.clear)
        kubeview._health[("shop", "staging")] = {"bad": ["web: CrashLoopBackOff"], "since": 10, "repo": "shop-api"}
        kubeview._health[("other", "prod")] = {"bad": ["db: 0 of 1 ready"], "since": 20}
        rows = kubeview.attention(lambda space: space == "shop")
        self.assertEqual([(r["space"], r["env"], r["repo"], r["active"]) for r in rows], [("shop", "staging", "shop-api", True)])


class Quantities(unittest.TestCase):
    def test_cores_and_bytes(self):
        import kubeclient
        self.assertEqual([kubeclient.quantity(q) for q in ("250m", "2", "1500000n", "8Gi", "512Mi", "1024k", "x", "")],
                         [0.25, 2.0, 0.0015, 8 * 1024 ** 3, 512 * 1024 ** 2, 1024000.0, 0, 0])


class Exec(unittest.TestCase):
    """A pod's shell (kubeexec.py): a client's frames masked, as the API
    requires, and read back whole by the reader the server's frames go
    through; and the exec's end said in words."""

    def test_a_clients_frames_read_back(self):
        for body in (b"", bytes([0]) + b"ls\r", bytes([4]) + b'{"Width":80,"Height":24}', bytes([0]) + b"x" * 70000):
            raw = kubeexec.masked(body)
            self.assertTrue(raw[1] & 0x80, "masked")
            self.assertEqual(termws.Frames().feed(raw), [(2, body)])

    def test_its_end_in_words(self):
        self.assertEqual(kubeexec._ended(b'{"status":"Success"}'), "the shell ended")
        self.assertIn("command terminated with non-zero exit code",
                      kubeexec._ended(b'{"status":"Failure","message":"command terminated with non-zero exit code"}'))


if __name__ == "__main__":
    unittest.main()
