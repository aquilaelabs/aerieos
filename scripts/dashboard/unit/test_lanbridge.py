"""The LAN card in a bridge on AerieOS (R219): what is written, when it is
done at all, and VMs given a port on it, which reaches the host where
macvtap did not."""
import os
import sys
import tempfile
import unittest
from unittest import mock

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)
import agentpkg  # noqa: E402
agent = agentpkg.load("lanbridge")


def _mod(name):
    pkg = agent.__name__.rsplit(".", 1)[0]
    import importlib
    return importlib.import_module(f"{pkg}.{name}")


class Bridge(unittest.TestCase):
    def setUp(self):
        self.lb = _mod("lanbridge")
        self.net = tempfile.mkdtemp()
        os.makedirs(f"{self.net}/enp3s0/device")
        os.makedirs(f"{self.net}/wlan0/device")
        os.makedirs(f"{self.net}/wlan0/wireless")
        os.makedirs(f"{self.net}/br0/bridge")

    def test_the_plan(self):
        files = self.lb.plan("enp3s0", mac="52:54:00:12:34:56")
        netdev = files[self.lb.netdev_path()]
        self.assertIn("Kind=bridge", netdev)
        # The card's own MAC, written: left to itself the bridge took one of
        # its own and a new lease (the 4951 stick, .16 for the card's .15).
        self.assertIn("MACAddress=52:54:00:12:34:56", netdev)
        self.assertIn("Bridge=br0", files[self.lb.port_path("enp3s0")])
        self.assertIn("ClientIdentifier=mac", files[self.lb.bridge_path()])
        # The port's file sorts ahead of the image's DHCP and the page's own.
        names = sorted(os.path.basename(p) for p in (self.lb.port_path("enp3s0"), "80-dhcp.network",
                                                     "00-builderbot-enp3s0.network"))
        self.assertEqual(names[0], "00-aerieos-port-enp3s0.network")
        # ...and the page's file for br0 sorts ahead of the bridge's own.
        self.assertLess("00-builderbot-br0.network", os.path.basename(self.lb.bridge_path()))

    def test_the_cards_mac_is_read(self):
        with open(f"{self.net}/enp3s0/address", "w") as f:
            f.write("52:54:00:AA:bb:cc\n")
        self.assertEqual(self.lb.mac_of("enp3s0", self.net), "52:54:00:aa:bb:cc")
        self.assertEqual(self.lb.mac_of("eno9", self.net), "")

    def test_a_static_address_moves_to_the_bridge(self):
        page = "[Match]\nName=enp3s0\n\n[Network]\nAddress=192.168.1.15/24\nGateway=192.168.1.1\n"
        files = self.lb.plan("enp3s0", page)
        self.assertIn("Name=br0\n", files[self.lb.page_path("br0")])
        self.assertIn("Address=192.168.1.15/24", files[self.lb.page_path("br0")])
        self.assertIsNone(files[self.lb.page_path("enp3s0")])

    def test_when(self):
        w = lambda iface, img=True, boot=True: self.lb.wanted(iface, img, boot, self.net)  # noqa: E731
        self.assertEqual(w("enp3s0"), "")
        self.assertIn("AerieOS", w("enp3s0", img=False))
        self.assertIn("next boot", w("enp3s0", boot=False))
        self.assertIn("already", w("br0"))
        self.assertIn("not a wired card", w("wlan0"))
        with mock.patch.dict(os.environ, {"BUILDERBOT_NO_LAN_BRIDGE": "1"}):
            self.assertIn("switched off", w("enp3s0"))

    def test_macvtap_vms_move_to_the_bridge(self):
        xml = ("<domain><name>n</name><devices><interface type='direct'><mac address='52:54:00:aa:bb:cc'/>"
               "<source dev='enp3s0' mode='bridge'/><model type='virtio'/></interface></devices></domain>")
        new, changed = self.lb.to_bridge(xml, "enp3s0")
        self.assertTrue(changed)
        self.assertIn('type="bridge"', new)
        self.assertIn('bridge="br0"', new)
        self.assertIn("52:54:00:aa:bb:cc", new)
        self.assertFalse(self.lb.to_bridge(xml, "eno1")[1])

    def test_a_new_vm_on_the_lan_is_a_bridge_port_where_there_is_one(self):
        with mock.patch.object(self.lb, "SYS_NET", self.net):
            self.assertIn("<interface type='bridge'>", self.lb.nic_xml("br0"))
            self.assertIn('<source bridge="br0"/>', self.lb.nic_xml("br0"))
            self.assertIn("<interface type='direct'>", self.lb.nic_xml("enp3s0"))


class Ensure(unittest.TestCase):
    """Committed and confirmed: the bridge stays when br0 holds the address and
    the default route in time, and the files go back when it does not."""
    def setUp(self):
        self.lb = _mod("lanbridge")
        self.d = tempfile.mkdtemp()
        self.net = tempfile.mkdtemp()
        os.makedirs(f"{self.net}/enp3s0/device")
        with open(f"{self.net}/enp3s0/address", "w") as f:
            f.write("52:54:00:12:34:56\n")
        with open(f"{self.d}/80-dhcp.network", "w") as f:
            f.write("[Match]\nName=en*\n\n[Network]\nDHCP=yes\n")
        self.route = ["enp3s0"]
        self.v4 = False
        for k, v in (("NETWORKD_DIR", self.d), ("SYS_NET", self.net), ("_reload", lambda i: None),
                     ("_route_iface", lambda: self.route[0]), ("_has_v4", lambda i: self.v4),
                     ("_booted_recently", lambda: True), ("move_domains", lambda i: []),
                     ("log", lambda m: None)):
            p = mock.patch.object(self.lb, k, v)
            p.start()
            self.addCleanup(p.stop)
        p = mock.patch.object(self.lb.time, "sleep", lambda s: None)
        p.start()
        self.addCleanup(p.stop)

    def test_confirmed(self):
        def reload(_i):
            self.route[0], self.v4 = "br0", True
        with mock.patch.object(self.lb, "_reload", reload):
            self.assertEqual(self.lb.ensure(True, confirm_s=5), (True, ""))
        self.assertIn("MACAddress=52:54:00:12:34:56", open(f"{self.d}/00-aerieos-br0.netdev").read())

    def test_put_back_without_an_address(self):
        done, why = self.lb.ensure(True, confirm_s=0.01)
        self.assertFalse(done)
        self.assertIn("put back", why)
        self.assertEqual(sorted(os.listdir(self.d)), ["80-dhcp.network"])


class Picked(unittest.TestCase):
    """A VM's network source, model and MAC as the old system's form picks
    them (R219 step 4): written into the domain and read back."""
    XML = ("<domain><name>v</name><memory unit='KiB'>1048576</memory><currentMemory unit='KiB'>1048576</currentMemory>"
           "<vcpu>1</vcpu><devices><interface type='network'><mac address='52:54:00:01:02:03'/>"
           "<source network='bbvm-n1'/><model type='virtio'/></interface></devices></domain>")

    def setUp(self):
        self.hw = _mod("vmhw")

    def put(self, **hw):
        return self.hw.apply(self.XML, hw, 1, 1024, lan="br0", network="bbvm-n1")

    def test_a_bridge_by_name(self):
        x = self.put(net="br:virbr0", model="e1000")
        r = self.hw.read(x)
        self.assertEqual((r["net"], r["model"], r["mac"]), ("br:virbr0", "e1000", "52:54:00:01:02:03"))

    def test_a_libvirt_network_and_a_new_mac(self):
        r = self.hw.read(self.put(net="net:default", mac="52:54:00:aa:bb:cc"))
        self.assertEqual((r["net"], r["mac"], r["model"]), ("net:default", "52:54:00:aa:bb:cc", "virtio"))

    def test_the_space_network_reads_as_its_own(self):
        self.assertEqual(self.hw.read(self.XML)["net"], "project")

    def test_the_names_are_checked(self):
        for good in ("project", "lan", "br:br1", "net:default"):
            self.assertTrue(self.hw.net_ok(good), good)
        for bad in ("br:", "net:bbvm-n2", "br:a b", "host", "net:../x"):
            self.assertFalse(self.hw.net_ok(bad), bad)


class Adopted(unittest.TestCase):
    def test_an_adopted_vm_on_the_old_br0_is_a_port_on_this_one(self):
        adopt = _mod("adopt")
        xml = ("<domain><name>node</name><os><type>hvm</type></os><devices><emulator>/x</emulator>"
               "<interface type='bridge'><source bridge='br0'/><model type='virtio'/></interface></devices></domain>")
        real = os.path.isdir
        with mock.patch.object(adopt.os.path, "isdir", lambda p: p == "/sys/class/net/br0/bridge" or real(p)):
            out, said = adopt.rewrite_domain(xml, "", None, "", "br0")
        self.assertIn('type="bridge"', out)
        self.assertIn('bridge="br0"', out)
        self.assertNotIn("direct", out)


if __name__ == "__main__":
    unittest.main()
