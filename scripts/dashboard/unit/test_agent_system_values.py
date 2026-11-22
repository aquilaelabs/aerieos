"""A system job's values are held on the node: a network's, a backup's.

Root writes them into whichever file owns the machine's network (an
interfaces stanza that may carry commands, a file named for the interface)
and hands them to its tools. The controller sends each in one shape; the
node takes each in that shape alone, whoever sent the job, and renders
nothing for one that is not."""
import types
import unittest
from unittest import mock

import agentpkg  # noqa: E402

agent = agentpkg.load("aerieos_agent_system_values")
agent.log = lambda *a, **k: None
configplane = agent.module("configplane")


class Backend:
    name = "stub"

    def __init__(self):
        self.rendered = []

    def ready(self, iface):
        return ""

    def render(self, iface, mode, addr, gw, dns, routes):
        self.rendered.append((iface, mode, addr, gw, tuple(dns)))
        return "desired"

    def snapshot(self, iface):
        return "desired"

    def same(self, a, b):
        return a == b


class Held(unittest.TestCase):
    def apply(self, net):
        backend, said = Backend(), []
        a = object.__new__(agent.Agent)
        job = types.SimpleNamespace(say=said.append)
        with mock.patch.object(configplane, "net_backend", lambda: backend), \
                mock.patch.object(configplane, "network_now", lambda: {"interface": "eth0"}), \
                mock.patch.object(configplane, "export_gaps", lambda addr: []):
            got = a._apply_network(job, {"network": net})
        return got, backend.rendered, "".join(said)

    def test_what_a_controller_sends_is_taken(self):
        got, rendered, _ = self.apply({"mode": "static", "interface": "enp3s0.100", "address": "10.0.0.12/24",
                                       "gateway": "10.0.0.1", "dns": ["10.0.0.1", "1.1.1.1"]})
        self.assertEqual(got, ("succeeded", 0))
        self.assertEqual(rendered, [("enp3s0.100", "static", "10.0.0.12/24", "10.0.0.1", ("10.0.0.1", "1.1.1.1"))])
        self.assertEqual(self.apply({"mode": "dhcp"})[1], [("eth0", "dhcp", "", "", ())])

    def test_an_interface_that_is_not_a_name_renders_nothing(self):
        for iface in ("x/../../../../etc/cron.d/evil", "-a", "eth0\n    up /bin/sh -c id", "eth 0", "..", ".hidden", "a" * 33,
                      "eth0;id", "$(id)"):
            got, rendered, said = self.apply({"mode": "dhcp", "interface": iface})
            self.assertEqual((got, rendered), (("failed", 65), []), iface)
            self.assertEqual(said, "refused: that is not an interface's name\n")

    def test_an_address_that_is_not_one_renders_nothing(self):
        ok = {"mode": "static", "interface": "eth0", "address": "10.0.0.12/24", "gateway": "10.0.0.1", "dns": ["10.0.0.1"]}
        for field, bad in (("address", "10.0.0.5/24\n    up /bin/sh -c 'id >/root/x'"), ("address", "10.0.0.5"),
                           ("address", "10.0.0.5/24'\nFOO='x"), ("gateway", "10.0.0.1\n[Route]"), ("gateway", "-h"),
                           ("dns", ["10.0.0.1", "1.1.1.1\nnameserver 6.6.6.6"]), ("dns", ["host.example"])):
            got, rendered, said = self.apply(dict(ok, **{field: bad}))
            self.assertEqual((got, rendered), (("failed", 65), []), (field, bad))
            self.assertTrue(said.startswith("refused: "), said)
            self.assertEqual(said.count("\n"), 1)


class BackupPlaces(unittest.TestCase):
    """A backup's source and destination are folders under the machine's
    disks or the controller's state, by name and by where they really are."""

    def test_by_whole_names(self):
        backups = agent.module("backups")
        for p in ("/mnt/tank/share", "/srv/x", "/var/lib/aerieos-controller", "/var/lib/aerieos-controller/state"):
            self.assertTrue(backups.under_roots(p), p)
        for p in ("/mnt", "/mnt/", "/srv", "/var/lib/aerieos-controller-other", "/var/lib/aerieos-controllers/x", "/etc", "/"):
            self.assertFalse(backups.under_roots(p), p)

    def test_a_link_out_of_the_disks_is_refused_before_anything_is_copied(self):
        import os
        import tempfile
        backups = agent.module("backups")
        with tempfile.TemporaryDirectory() as d:
            share, outside = os.path.join(d, "mnt", "share"), os.path.join(d, "etc")
            os.makedirs(share)
            os.makedirs(outside)
            os.symlink(outside, os.path.join(share, "l"))
            a = object.__new__(agent.Agent)
            a.state = {"store_backups": [{"name": "nightly", "source": os.path.join(share, "l"), "dest": os.path.join(d, "mnt", "dest")}]}
            a._sh = mock.Mock(side_effect=AssertionError("copied something"))
            said = []
            with mock.patch.object(backups, "ROOTS", (os.path.join(d, "mnt") + "/",)), \
                    mock.patch.object(backups.os, "geteuid", lambda: 0), \
                    mock.patch.object(backups.shutil, "which", lambda n: "/usr/bin/rsync"):
                got = a._apply_storage_backup(types.SimpleNamespace(say=said.append), {"name": "nightly"})
            self.assertEqual(got, ("failed", 64), said)
            self.assertFalse(os.path.exists(os.path.join(d, "mnt", "dest")))


if __name__ == "__main__":
    unittest.main()
