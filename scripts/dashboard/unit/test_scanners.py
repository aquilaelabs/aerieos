"""AerieOS's own scanners on each node (scanners.py): the record
and the compose file with each scanner the image its entry names by
digest, Deploy and Update as compose jobs, a run as a scan job over the
projects whose node it is, the schedule firing from the timer, a report
taken from a node and read by findings beside the host folder, a node
behind when the entry names another image, and the bell's rows."""
import io
import json
import os
import shutil
import sys
import tempfile
import time
import unittest
from pathlib import Path

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))
import findings    # noqa: E402
import packformat  # noqa: E402
import scanners    # noqa: E402
import schedules   # noqa: E402
import services    # noqa: E402

IMAGES = {"semgrep": "semgrep/semgrep:1.2.3@sha256:" + "a" * 64, "trivy": "aquasec/trivy:0.9.9@sha256:" + "b" * 64,
          "mobsfscan": "opensecurity/mobsfscan:0.4.5@sha256:" + "c" * 64}


def write_json(path, d):
    with open(path, "w") as f:
        json.dump(d, f)


class Scanners(unittest.TestCase):
    def setUp(self):
        self.tmp = Path(tempfile.mkdtemp())
        self.addCleanup(shutil.rmtree, self.tmp, True)
        self.jobs = []
        self.states = {}
        self.nodes = [{"id": "n1", "name": "Build Box", "kind": "agent", "state": "online", "live": True, "config": {}},
                      {"id": "n2", "name": "host", "kind": "agent", "state": "online", "live": True, "config": {"host_only": True}},
                      {"id": "n3", "name": "spare", "kind": "agent", "state": "online", "live": True, "config": {}}]
        self.bound = {"web": "n1", "app": "n1", "api": "n3", "lone": ""}

        def job_add(principal, placement, typ, spec):
            jid = f"j{len(self.jobs) + 1}"
            self.jobs.append({"id": jid, "principal": principal, "node": placement.get("node"), "type": typ, "spec": spec})
            return {"job": jid}
        scanners.configure(state=self.tmp, write_json=write_json, node_list=lambda: self.nodes,
                           node_name=lambda nid: {n["id"]: n["name"] for n in self.nodes}.get(nid, nid),
                           project_nodes=lambda: dict(self.bound), project_names=lambda: sorted(self.bound),
                           job_add=job_add, job_state=lambda jid: self.states.get(jid, ""),
                           next_after=schedules.next_after, cron_words=schedules.words)
        self.addCleanup(setattr, services, "IMAGES_FILE", services.IMAGES_FILE)
        services.IMAGES_FILE = str(self.tmp / "service-images.json")
        self.entry()

    def entry(self, **moved):
        """The scanners' entry naming those images, `moved` in their place."""
        write_json(services.IMAGES_FILE, {"services": [{"name": "scanners", "images": {**IMAGES, **moved}}]})

    def test_the_compose_file_names_each_scanner_by_digest_as_one_shot_services(self):
        text = scanners.compose_text("n1", {})
        self.assertEqual(packformat.compose_images(text), list(IMAGES.values()), "each the image its entry names, by its digest")
        self.assertNotIn("pip install", text, "nothing is installed at a scan: the tool is in its image")
        self.assertNotIn("python:", text)
        self.assertIn('entrypoint: ["sh", "-c"]', text)
        self.assertIn("mobsfscan --sarif -o /reports/mobsfscan.sarif /src; s=$$?; [ $$s -le 1 ]", text, "its exit 1 is a finding, not a failed scan")
        self.assertEqual(text.count("profiles: [scan]"), 3, "nothing starts at an up: a run is compose run per service")
        self.assertIn("./reports:/reports", text)
        self.assertEqual(scanners.container_name("n1"), "scanners-build-box")
        pinned = {"images": {**IMAGES, "trivy": "aquasec/trivy:0.9.0@sha256:" + "d" * 64}}
        self.assertIn("image: aquasec/trivy:0.9.0@sha256:" + "d" * 64, scanners.compose_text("n1", pinned), "a node runs what its record is pinned to")
        with open(services.IMAGES_FILE.replace(str(self.tmp), os.path.dirname(os.path.abspath(scanners.__file__))), encoding="utf-8") as f:
            shipped = next(r for r in json.load(f)["services"] if r["name"] == "scanners")["images"]
        self.assertEqual(sorted(shipped), sorted(scanners.SCANNERS), "the shipped entry names an image for each scanner")

    def test_deploy_and_update_are_compose_jobs_and_remove_takes_it_off(self):
        self.assertIn("hosts containers only", scanners.deploy("n2")["error"])
        r = scanners.deploy("n1", "ann")
        self.assertEqual(r["job"], "j1")
        j = self.jobs[0]
        self.assertEqual((j["type"], j["node"], j["spec"]["name"], j["principal"]), ("compose", "n1", "scanners-build-box", "scanners:ann"))
        self.assertEqual(j["spec"]["plan"][0]["name"], "pull")
        self.assertIn("compose.yml", j["spec"]["files"])
        rec = scanners.record("n1")
        self.assertTrue(rec["deployed"])
        self.assertEqual(rec["images"], IMAGES, "pinned to the images the entry names")
        self.assertEqual(rec["versions"], {"semgrep": "1.2.3", "trivy": "0.9.9", "mobsfscan": "0.4.5"})
        self.assertEqual(scanners.update("n1")["same"], True, "the entry names what it runs")
        # The entry names another image: the node is behind, Update pins and pulls.
        newer = "aquasec/trivy:9.9.9@sha256:" + "e" * 64
        self.entry(trivy=newer)
        self.assertEqual(scanners.behind(scanners.record("n1")), {"trivy": "9.9.9"}, "said with the tag it would move to")
        self.assertIn("image: " + IMAGES["trivy"], scanners.compose_text("n1", scanners.record("n1")), "and it still runs what it is pinned to")
        self.assertEqual(scanners.update("n1")["versions"]["trivy"], "9.9.9")
        self.assertIn("image: " + newer, self.jobs[-1]["spec"]["files"]["compose.yml"])
        self.assertEqual(scanners.behind(scanners.record("n1")), {})
        # The same tag under another digest is an Update too.
        self.entry(trivy="aquasec/trivy:9.9.9@sha256:" + "f" * 64)
        self.assertEqual(scanners.behind(scanners.record("n1")), {"trivy": "9.9.9"})
        self.entry(trivy=newer)
        self.assertIn("not deployed", scanners.update("n3")["error"])
        r = scanners.remove("n1")
        self.assertEqual(self.jobs[-1]["spec"]["plan"][0]["name"], "down")
        self.assertFalse(scanners.record("n1").get("deployed"))

    def test_a_run_is_a_scan_job_over_the_projects_whose_node_it_is(self):
        scanners.deploy("n1")
        r = scanners.run_now("ann")
        self.assertEqual(r["nodes"]["n1"]["job"], "j2")
        j = self.jobs[-1]
        self.assertEqual((j["type"], j["spec"]["projects"], j["spec"]["scanners"]), ("scan", ["app", "web"], list(scanners.SCANNERS)))
        self.assertIn("compose.yml", j["spec"]["files"])
        # A run still going is skipped, and a node with nothing bound said.
        self.states["j2"] = "running"
        self.assertIn("still going", scanners.run_now("ann")["nodes"]["n1"]["error"])
        scanners.deploy("n3")
        self.bound["api"] = ""
        self.assertIn("no space", scanners.run_now("ann", "n3")["nodes"]["n3"]["error"])
        # Who is not covered, and why.
        un = {u["project"]: u["why"] for u in scanners.uncovered()}
        self.assertEqual(un["lone"], "no node")
        self.assertNotIn("web", un)
        scanners.remove("n1")
        un = {u["project"]: u["why"] for u in scanners.uncovered()}
        self.assertEqual(un["web"], "no scanners on Build Box")

    def test_the_schedule_fires_from_the_timer_and_a_missed_one_runs_late(self):
        scanners.deploy("n1")
        base = time.mktime((2026, 10, 25, 3, 59, 10, 0, 0, -1))
        self.assertIn("names no minute", scanners.set_schedule(cron="61 4 * * *")["error"])
        s = scanners.set_schedule(on=True, cron="0 4 * * *")
        self.assertEqual((s["on"], s["words"]), (True, "daily at 4:00"))
        self.assertFalse(scanners.tick(base), "the first tick sets when it is due")
        self.assertFalse(scanners.tick(base + 30))
        self.assertTrue(scanners.tick(base + 60), "4:00: fired")
        self.assertEqual(self.jobs[-1]["type"], "scan")
        self.assertEqual(scanners.record("n1")["last"]["by"], "schedule")
        self.assertFalse(scanners.tick(base + 120), "once")
        # A whole day missed: run once, said late, due tomorrow.
        self.assertTrue(scanners.tick(base + 60 + 86400 + 1800))
        self.assertIn("late", scanners.record("n1")["last"]["by"])
        self.assertFalse(scanners.tick(base + 60 + 86400 + 1860))
        scanners.set_schedule(on=False)
        self.assertFalse(scanners.tick(base + 60 + 2 * 86400))

    def test_a_report_taken_from_a_node_is_read_beside_the_host_folder(self):
        findings.STATE_REPORTS = scanners.report_files
        self.addCleanup(setattr, findings, "STATE_REPORTS", None)
        was = findings.REPORTS
        findings.REPORTS = self.tmp / "no-such-host-folder"
        self.addCleanup(setattr, findings, "REPORTS", was)
        self.assertFalse(findings.mounted())
        self.assertIsNone(findings.report_files())
        doc = {"version": "2.1.0", "runs": [{"tool": {"driver": {"name": "semgrep"}}, "results": [
            {"ruleId": "x.y", "level": "warning", "message": {"text": "hm"},
             "locations": [{"physicalLocation": {"artifactLocation": {"uri": "/src/web/a.py"}, "region": {"startLine": 3}}}]}]}]}
        body = json.dumps(doc).encode()
        self.assertEqual(scanners.take_report("n1", "nope", io.BytesIO(body), len(body))[1], 400)
        self.assertEqual(scanners.take_report("n1", "semgrep", io.BytesIO(b"not json"), 8)[1], 400)
        self.assertEqual(scanners.take_report("n1", "semgrep", io.BytesIO(body), len(body), "web,app")[1], 200)
        self.assertTrue(findings.mounted())
        self.assertEqual([f.name for f in findings.report_files()], ["semgrep.sarif"])
        self.assertEqual(scanners.record("n1")["reports"]["semgrep"]["projects"], "web,app")
        got = findings.payload([{"name": "web", "issues": []}, {"name": "app", "issues": []}])
        self.assertTrue(got["available"])
        self.assertEqual([(f["project"], f["path"]) for f in got["reports"][0]["findings"]], [("web", "a.py")])
        self.assertGreater(findings.reports_mtime(), 0)
        self.assertEqual(findings.reports_ages()[0]["name"], "n1/semgrep.sarif")
        # A node retired takes its record and its reports with it:
        # the findings no longer read a node nobody has.
        scanners.forget_node("n1")
        self.assertEqual(scanners.record("n1"), {})
        self.assertIsNone(findings.report_files())

    def test_a_node_whose_record_names_no_images_is_pinned_at_its_next_run(self):
        with scanners._lock:
            d = scanners._load()
            d["nodes"]["n1"] = {"deployed": 5, "versions": {"semgrep": "1.0.0", "trivy": "0.1.0", "mobsfscan": "0.4.0"}}
            scanners._save(d)
        self.assertEqual(scanners.behind(scanners.record("n1")), {})
        scanners.run_now("ann", "n1")
        self.assertEqual(packformat.compose_images(self.jobs[-1]["spec"]["files"]["compose.yml"]), list(IMAGES.values()))
        self.assertEqual(scanners.record("n1")["images"], IMAGES)
        self.entry(semgrep="semgrep/semgrep:1.3.0@sha256:" + "e" * 64)
        self.assertEqual(list(scanners.behind(scanners.record("n1"))), ["semgrep"], "and from then on the entry moving is an Update")

    def test_the_bell_says_behind_and_failed_and_nothing_asks_what_is_newest(self):
        scanners.deploy("n1")
        self.assertEqual(scanners.behind(scanners.record("n1")), {}, "deployed from the entry: nothing to move to")
        self.entry(trivy="aquasec/trivy:1.200.1@sha256:" + "e" * 64)
        with scanners._lock:
            d = scanners._load()
            d["nodes"]["n1"]["last"] = {"at": 5, "job": "j9", "error": ""}
            scanners._save(d)
        self.states["j9"] = "failed"
        rows = scanners.attention()
        self.assertEqual(sorted(r["what"] for r in rows), ["behind", "failed"])
        self.assertEqual(next(r for r in rows if r["what"] == "behind")["said"], "trivy 1.200.1")
        v = scanners.view()
        self.assertEqual(v["nodes"][0]["name"], "Build Box")
        self.assertEqual(v["nodes"][0]["behind"], {"trivy": "1.200.1"})
        self.assertEqual(v["nodes"][0]["versions"]["trivy"], "0.9.9")
        self.assertEqual(v["latest"], {"versions": {"semgrep": "1.2.3", "trivy": "1.200.1", "mobsfscan": "0.4.5"}})
        self.assertEqual(v["nodes"][1]["host_only"], True)
        self.assertFalse(hasattr(scanners, "check_versions"), "nothing reads a registry or an index for what is newest")


if __name__ == "__main__":
    unittest.main()
