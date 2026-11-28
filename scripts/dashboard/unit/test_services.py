"""AerieOS's own services as one table (services.py): the kinds every
list of them reads in one order, each module answering by the same names,
the Library's rows as it drew them when the three were spelled out (the
router's with its status whole, nginx's and the Scanners' with what Remove
says), Install and Remove reaching each module's own verbs, and the update
checks two of them have."""
import json
import os
import shutil
import sys
import tempfile
import unittest
from pathlib import Path
from unittest import mock

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))
import checks      # noqa: E402
import containers  # noqa: E402
import devactions  # noqa: E402
import devapp      # noqa: E402
import k3s         # noqa: E402
import library     # noqa: E402
import nginxproxy  # noqa: E402
import router      # noqa: E402
import scanners    # noqa: E402
import schedules   # noqa: E402
import services    # noqa: E402
import settings    # noqa: E402
import statefile   # noqa: E402
import toolpacks   # noqa: E402

NGINX_REMOVES = "Its routes and certificates are kept here; the hostnames it answers for stop answering."
SCANNERS_REMOVES = "What they found is kept; nothing scans the spaces on this node until they are installed again."
K3S_REMOVES = "The cluster and everything deployed to it go with it, and it leaves the Clusters page."


def write_json(path, d, mode=0o644):
    with open(path, "w") as f:
        json.dump(d, f)


class Table(unittest.TestCase):
    def test_every_list_reads_the_table_in_its_order(self):
        self.assertEqual(services.KINDS, ("router", "nginx", "scanners", "k3s"))
        # Read from the one table, said in toolpacks' own source: the same
        # object only while no other test of the tier has reloaded services
        # (test_seams, test_features_off and test_auto_update do), which
        # made an identity check fail in a whole run.
        self.assertEqual(toolpacks.SERVICES, services.KINDS)
        with open(toolpacks.__file__, encoding="utf-8") as f:
            self.assertIn("\nSERVICES = services.KINDS\n", f.read())
        self.assertEqual(checks.KINDS, ("release", "images", "catalog"), "no service asks what is newest: each runs the images its entry names")
        self.assertEqual([k for k in settings.KEYS if k.startswith("check_")], [f"check_{k}" for k in checks.KINDS])

    def test_each_pack_names_its_kind_and_is_found_by_its_name(self):
        self.assertEqual([m["name"] for m in services.packs()], ["model-router", "nginx", "scanners", "k3s"])
        for kind, m in zip(services.KINDS, services.packs(), strict=True):
            clean, errors = toolpacks.validate(m, shipped=(), official=True)
            self.assertEqual(errors, [], kind)
            self.assertEqual(clean["service"], {"kind": kind})
            self.assertEqual(services.of_pack(m["name"]), kind)
        self.assertEqual(services.of_pack("router"), "", "a kind is not a pack's name")
        self.assertEqual(services.of_pack(""), "")

    def test_each_entry_names_every_image_it_runs_by_digest(self):
        import packformat
        for m in services.packs():
            clean, errors = toolpacks.validate(m, shipped=(), official=True)
            self.assertEqual(errors, [], m["name"])
            self.assertEqual((m["format"], clean["images"]), (packformat.HELD_FORMAT, services.images(m["name"])), m["name"])
            self.assertTrue(clean["images"], m["name"])
            for ref in clean["images"].values():
                parts = packformat.image_parts(ref)
                self.assertTrue(parts["tag"] and parts["digest"], f"{m['name']}: {ref} is a tag a person reads and the digest that is pulled")
            self.assertEqual(packformat.held(m), ("pinned", packformat.IMAGES_SAID), m["name"])
        one = services.packs()[1]
        self.assertTrue(any("names no" in e or "images maps" in e for e in toolpacks.validate({**one, "images": {"nginx": "nginx:1.31-alpine"}}, official=True)[1]),
                        "an image named by its tag alone is refused")
        self.assertTrue(any("pack format 5" in e for e in toolpacks.validate({**one, "format": 4, "framework": "4.1"}, official=True)[1]))
        plain = {"name": "mine", "label": "Mine", "platforms": ["linux/*"], "install": {"steps": []}, "format": 5, "images": one["images"]}
        self.assertTrue(any("official service pack's alone" in e for e in toolpacks.validate(plain)[1]))

    def test_each_module_answers_by_the_same_names(self):
        for kind in services.KINDS:
            m = services.module(kind)
            for name in ("pack", "container_name", "service_deployed", "service_install", "service_remove"):
                self.assertTrue(callable(getattr(m, name, None)), f"{kind}: {name}")
            self.assertIsInstance(m.REMOVES, str, kind)

    def test_the_grants_differ_and_only_the_router_is_set_on_its_card(self):
        self.assertEqual({k: services.grant(k) for k in services.KINDS},
                         {"router": "configure", "nginx": "configure", "scanners": "configure", "k3s": "configure"})
        self.assertEqual([k for k in services.KINDS if services.paged(k)], ["nginx", "scanners"])


class OnANode(unittest.TestCase):
    def setUp(self):
        self.tmp = Path(tempfile.mkdtemp())
        self.addCleanup(shutil.rmtree, self.tmp, True)
        nodes = [{"id": "n1", "name": "GPU Box", "kind": "agent", "state": "online", "live": True, "config": {}}]
        self.jobs = []

        def job_add(principal, placement, typ, spec):
            self.jobs.append((principal, typ))
            return {"job": f"j{len(self.jobs)}"}
        router.configure(state=self.tmp, write_json=statefile.write_json, seal=None, unseal=None, sealing=lambda: False,
                         node_list=lambda: nodes, node_name=lambda nid: "GPU Box", node_addr=lambda nid: "10.0.0.5",
                         project_names=lambda: ["web", "app"], job_add=job_add, job_get=lambda jid: None)
        nginxproxy.configure(state=self.tmp, write_json=write_json, node_list=lambda: nodes,
                             node_name=lambda nid: "GPU Box", taken_ports=lambda *a: [])
        scanners.configure(state=self.tmp, write_json=write_json, node_list=lambda: nodes, node_name=lambda nid: "GPU Box",
                           project_nodes=lambda: {"web": "n1"}, project_names=lambda: ["web", "app"],
                           job_add=job_add, job_state=lambda jid: "", next_after=schedules.next_after, cron_words=schedules.words)
        k3s.configure(state=self.tmp, write_json=write_json, seal=None, unseal=None, sealing=lambda: False, node_list=lambda: nodes,
                      node_name=lambda nid: "GPU Box", node_addr=lambda nid: "10.0.0.5", nginx_on=lambda nid: True,
                      run_wait=None, clusters=None)
        # The node's nginx is on the Containers page; nothing else written is.
        for name, fn in (("is_file_source", lambda name: name == "nginx-gpu-box"), ("_read_rec", lambda name, inst: {"node": "n1"})):
            p = mock.patch.object(devapp, name, fn)
            p.start()
            self.addCleanup(p.stop)

    def spelled_out(self, nid):
        """The rows as the server made them with each spelled out."""
        return ([{"manifest": toolpacks.validate(router.pack(), shipped=(), official=True)[0], "status": router.status(nid),
                  "ready": router._ready(nid), "all_projects": sorted(["web", "app"])}],
                [{"manifest": toolpacks.validate(nginxproxy.pack(), shipped=(), official=True)[0],
                  "status": {"deployed": bool(nginxproxy.deployed(devapp, nid))}, "ready": "", "removes": NGINX_REMOVES},
                 {"manifest": toolpacks.validate(scanners.pack(), shipped=(), official=True)[0],
                  "status": {"deployed": bool(scanners.record(nid).get("deployed"))}, "ready": "", "removes": SCANNERS_REMOVES},
                 {"manifest": toolpacks.validate(k3s.pack(), shipped=(), official=True)[0],
                  "status": {"deployed": False}, "ready": "", "removes": K3S_REMOVES, "cluster": ""}])

    def drawn(self, rows):
        return json.dumps(library.rows({"items": []}, [], [], None, None, services=rows), sort_keys=False)

    def test_the_library_s_rows_are_the_rows_it_drew_before(self):
        for step in ("nothing set", "a key and the scanners"):
            if step != "nothing set":
                self.assertTrue(router.set_keys("n1", {"providers": {"anthropic": "sk-ant-1"}, "ollama": True})["ok"])
                self.assertTrue(scanners.deploy("n1", "ann")["ok"])
            the_router, the_paged = self.spelled_out("n1")
            got = services.rows("n1")
            self.assertEqual([r["manifest"]["name"] for r in got], ["model-router", "nginx", "scanners", "k3s"], step)
            self.assertEqual(self.drawn(got), self.drawn(the_router + the_paged), step)
            # The router's row keeps its own keys, each as it was.
            for k in ("manifest", "status", "ready", "all_projects"):
                self.assertEqual(json.dumps(got[0][k]), json.dumps(the_router[0][k]), f"{step}: {k}")
            self.assertEqual(got[1:], the_paged, step)
            # Each comes to whoever holds Configure on the node, a node's
            # services all being its, and none to Containers Write.
            self.assertEqual(self.drawn(services.rows("n1", lambda g: g == "configure")),
                             self.drawn(the_router + the_paged), step)
            self.assertEqual(services.rows("n1", lambda g: g == "docker-write"), [], step)
            self.assertEqual(services.rows("n1", lambda g: False), [], step)
        self.assertEqual((got[1]["status"], got[2]["status"]), ({"deployed": True}, {"deployed": True}))
        self.assertEqual(got[0]["ready"], "")

    def test_a_pack_that_does_not_validate_is_left_out(self):
        with mock.patch.object(nginxproxy, "pack", lambda: {"name": "nginx"}):
            self.assertEqual([r["manifest"]["name"] for r in services.rows("n1")], ["model-router", "scanners", "k3s"])

    def test_the_containers_of_each_are_known_by_name(self):
        self.assertEqual(services.container_names("n1"),
                         {"router-gpu-box": "router", "nginx-gpu-box": "nginx", "scanners-gpu-box": "scanners", "k3s-gpu-box": "k3s"})

    def test_install_and_remove_are_each_module_s_own_verbs(self):
        said = []

        def verb(name):
            return lambda *a: said.append((name, a)) or {"ok": True, "name": name}
        with mock.patch.object(nginxproxy, "deploy", verb("nginx deploy")), mock.patch.object(nginxproxy, "remove", verb("nginx remove")), \
                mock.patch.object(router, "deploy", verb("router deploy")), mock.patch.object(router, "remove", verb("router remove")), \
                mock.patch.object(router, "node_gpu", lambda nid: nid == "n1"), \
                mock.patch.object(scanners, "deploy", verb("scanners deploy")), mock.patch.object(scanners, "remove", verb("scanners remove")), \
                mock.patch.object(k3s, "deploy", verb("k3s deploy")), mock.patch.object(k3s, "remove", verb("k3s remove")):
            for kind in services.KINDS:
                self.assertEqual(services.install(kind, "n1", "ann")["name"], f"{kind} deploy")
                self.assertEqual(services.remove(kind, "n1", "ann")["name"], f"{kind} remove")
            services.install("router", "n2", "ann")
        self.assertEqual(said, [("router deploy", ("n1", containers, devactions, devapp, True)), ("router remove", ("n1", devactions, devapp)),
                                ("nginx deploy", ("n1", containers, devactions, devapp)), ("nginx remove", ("n1", devactions, devapp)),
                                ("scanners deploy", ("n1", "ann")), ("scanners remove", ("n1", "ann")),
                                ("k3s deploy", ("n1", containers, devactions, devapp)), ("k3s remove", ("n1", devactions, devapp)),
                                ("router deploy", ("n2", containers, devactions, devapp, False))])

    def test_deployed_is_each_one_s_own_answer(self):
        self.assertEqual([services.deployed(k, "n1") for k in services.KINDS], [False, True, False, False])
        self.assertFalse(services.deployed("nginx", "n2"), "the written container is another node's")
        scanners.deploy("n1")
        self.assertTrue(services.deployed("scanners", "n1"))

    def test_no_service_has_a_check_of_its_own(self):
        for kind in services.KINDS:
            m = services.module(kind)
            self.assertNotIn("check", services.TABLE[kind], kind)
            for name in ("checked_at", "check_loop", "check_image", "check_versions"):
                self.assertFalse(hasattr(m, name), f"{kind}: {name}: what it runs is its entry's, and a newer image is a change to the entry")


if __name__ == "__main__":
    unittest.main()
