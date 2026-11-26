"""Draft from the compose (R281 step 4): each service a Deployment, a
Service named as the service where it has ports, a claim for each named
volume; the service built from the root takes the deploy's image; what has
no counterpart in a cluster is said in a comment; and the chart is written
into the tree uncommitted, never over a chart or manifests already there."""
import os
import shutil
import sys
import tempfile
import unittest
from pathlib import Path

sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)), ".."))
import chartdraft  # noqa: E402
import deploys  # noqa: E402

COMPOSE = """services:
  web:
    build: .
    ports: ["8080:80"]
    environment:
      DB_HOST: db
  db:
    image: postgres:17
    environment: ["POSTGRES_PASSWORD=example"]
    volumes: ["pgdata:/var/lib/postgresql/data", "./init:/docker-entrypoint-initdb.d"]
    expose: ["5432"]
  worker:
    build: ./worker
volumes:
  pgdata: {}
"""


class Draft(unittest.TestCase):
    def test_each_service(self):
        got = chartdraft.draft(COMPOSE, "Shop")
        self.assertEqual(got["app"], "web", "the service built from the root is the deploy's image")
        f = got["files"]
        self.assertEqual(sorted(f), ["Chart.yaml", "templates/db.yaml", "templates/web.yaml", "templates/worker.yaml",
                                     "values.yaml"])
        self.assertIn('image: "{{ .Values.image.repository }}:{{ .Values.image.tag }}"', f["templates/web.yaml"])
        self.assertIn("replicas: {{ .Values.web.replicas }}", f["templates/web.yaml"])
        self.assertIn("port: 8080", f["templates/web.yaml"])
        self.assertIn("targetPort: 80", f["templates/web.yaml"])
        self.assertIn("kind: Service\nmetadata:\n  name: db", f["templates/db.yaml"], "named as the service, so db:5432 answers")
        self.assertIn("claimName: pgdata", f["templates/db.yaml"])
        self.assertIn("kind: PersistentVolumeClaim", f["templates/db.yaml"])
        self.assertIn("# ./init at /docker-entrypoint-initdb.d is not carried over", f["templates/db.yaml"])
        self.assertIn("# worker is built from ./worker, which a deploy does not build", f["templates/worker.yaml"])
        self.assertNotIn("kind: Service", f["templates/worker.yaml"], "no ports, no Service")
        self.assertIn("name: shop", f["Chart.yaml"])
        self.assertIn("repository: shop", f["values.yaml"])

    def test_what_is_not_a_compose_file(self):
        self.assertIn("names no services", chartdraft.draft("version: '3'\n", "x")["error"])


class Written(unittest.TestCase):
    def setUp(self):
        self.tmp = Path(tempfile.mkdtemp())
        self.addCleanup(shutil.rmtree, self.tmp, True)
        self.tree = self.tmp / "shop"
        self.tree.mkdir()
        (self.tree / "docker-compose.yml").write_text(COMPOSE)
        deploys.configure(tree=lambda repo: self.tmp / repo,
                          compose_of=lambda repo: (self.tmp / repo / "docker-compose.yml")
                          if (self.tmp / repo / "docker-compose.yml").is_file() else None)

    def test_into_the_tree_once(self):
        self.assertEqual(deploys.repo_facts("shop"), {"name": "shop", "ships": "", "compose": True})
        got = deploys.draft("shop", "Shop")
        self.assertTrue(got.get("ok"), got)
        self.assertIn("deploy/chart/Chart.yaml", got["paths"])
        self.assertTrue((self.tree / "deploy" / "chart" / "templates" / "web.yaml").is_file())
        self.assertEqual(deploys.repo_facts("shop")["ships"], "chart")
        self.assertIn("already has deploy/chart", deploys.draft("shop")["error"])
        (self.tmp / "plain").mkdir()
        (self.tmp / "plain" / "deploy" / "k8s").mkdir(parents=True)
        (self.tmp / "plain" / "deploy" / "k8s" / "web.yaml").write_text("kind: Deployment\n")
        self.assertEqual(deploys.repo_facts("plain"), {"name": "plain", "ships": "k8s", "compose": False})
        self.assertIn("no compose file", deploys.draft("plain")["error"])


if __name__ == "__main__":
    unittest.main()
