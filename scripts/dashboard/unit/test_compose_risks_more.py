"""What a compose file asks of the host past the binds, privileges and
namespaces the check read before (R227): the other host namespaces, another
container's, volumes_from, device rules, a loosened profile under any name,
a build that reaches the host, a named volume bound to a host path, and a
path in the tree that is a link out of it."""
import os
import sys
import tempfile
import unittest
from unittest import mock

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))
import devapp  # noqa: E402


class More(unittest.TestCase):
    def setUp(self):
        self.ws = tempfile.mkdtemp()
        p = mock.patch.object(devapp, "WORKSPACE", devapp.Path(self.ws))
        p.start()
        self.addCleanup(p.stop)

    def said(self, sv, **top):
        return " | ".join(devapp.risks("web", {"services": {"app": sv}, **top}))

    def test_a_plain_service_says_nothing(self):
        self.assertEqual(self.said({"image": "nginx", "volumes": ["data:/data"],
                                    "security_opt": ["no-new-privileges:true"]}, volumes={"data": {}}), "")

    def test_the_other_host_namespaces(self):
        got = self.said({"ipc": "host", "uts": "host", "cgroup": "host"})
        for what in ("inter-process memory", "hostname", "control groups"):
            self.assertIn(what, got)

    def test_another_containers_namespaces_and_volumes(self):
        got = self.said({"network_mode": "container:db", "pid": "service:db", "volumes_from": ["db"]})
        self.assertIn("joins the network of container:db", got)
        self.assertIn("joins the processes of service:db", got)
        self.assertIn("takes every volume of db", got)

    def test_devices_by_rule_and_kernel_parameters(self):
        got = self.said({"device_cgroup_rules": ["c 189:* rwm"], "sysctls": {"net.ipv4.ip_forward": 1}})
        self.assertIn("allowed host devices by rule", got)
        self.assertIn("sets kernel parameters: net.ipv4.ip_forward", got)

    def test_a_profile_loosened_under_any_name(self):
        for opt in ("label:disable", "label=disable", "seccomp:./mine.json", "apparmor=unconfined", "systempaths=unconfined"):
            self.assertIn("drops a security profile", self.said({"security_opt": [opt]}), opt)

    def test_a_build_that_reaches_the_host(self):
        got = self.said({"build": {"context": ".", "network": "host", "ssh": ["default"], "privileged": True}})
        self.assertIn("builds on the host's own network", got)
        self.assertIn("ssh agent", got)
        self.assertIn("build runs privileged", got)

    def test_a_named_volume_bound_to_a_host_path(self):
        vols = {"sneak": {"driver": "local", "driver_opts": {"type": "none", "o": "bind", "device": "/etc"}},
                "sock": {"driver_opts": {"o": "bind", "device": "/var/run/docker.sock"}},
                "fine": {"driver_opts": {"type": "nfs", "o": "addr=nas", "device": ":/export"}}}
        got = self.said({"volumes": ["sneak:/x", "sock:/s", "fine:/f"]}, volumes=vols)
        self.assertIn("the volume sneak is /etc", got)
        self.assertIn("the volume sock is /var/run/docker.sock", got)
        self.assertNotIn("fine", got)

    def test_a_link_in_the_tree_is_judged_by_where_it_leads(self):
        tree = os.path.join(self.ws, "web")
        os.makedirs(os.path.join(tree, "real"))
        os.symlink("/etc", os.path.join(tree, "data"))
        self.assertIn("a link to /etc", self.said({"volumes": [f"{tree}/data:/d"]}))
        self.assertEqual(self.said({"volumes": [f"{tree}/real:/d"]}), "")


if __name__ == "__main__":
    unittest.main()
