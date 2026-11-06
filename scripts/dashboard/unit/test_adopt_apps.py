"""The containers and VMs another system ran, taken again here (R163 steps
10 and 11): the compose each container becomes (adoptapps.compose_for:
the exact image by digest, its network of fixed addresses, started with
the machine where it was, its paths said where the adopted disks do not
hold them or may not write them), and the agent's reading of the old
Docker and libvirt folders and its rewrite of a VM for this machine."""
import json
import os
import sys
import tempfile
import unittest

sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)), ".."))
import adoptapps  # noqa: E402
import agentpkg  # noqa: E402

adopt = agentpkg.load("aerieos_agent_adopt_apps").module("adopt")

APP = {"name": "Plex-Media-Server", "compose": {"services": {"plex-media-server": {
    "image": "plexinc/pms-docker:latest", "restart": "unless-stopped", "ports": ["32400:32400/tcp"],
    "volumes": ["/mnt/user/appdata/plex:/config:rw", "/mnt/user/media:/data:ro", "/mnt/disks/usb/x:/x:rw"],
    "x-fixed-network": {"name": "br0", "ip": "192.168.1.50"}}}}}
READ = {"autostart": ["Plex-Media-Server"], "digests": {"Plex-Media-Server": "plexinc/pms-docker@sha256:" + "a" * 64}}


class Compose(unittest.TestCase):
    def test_the_exact_image_its_network_and_autostart(self):
        comp, notes, auto = adoptapps.compose_for(APP, READ, pools=["cache"], writable=True,
                                                  shares={"appdata": {"cache": "prefer"}})
        svc = comp["services"]["plex-media-server"]
        self.assertEqual(svc["image"], READ["digests"]["Plex-Media-Server"])
        self.assertEqual(svc["restart"], "unless-stopped")
        self.assertTrue(auto)
        self.assertEqual(comp["networks"], {"br0": {"external": True}})
        self.assertEqual(svc["networks"], {"br0": {"ipv4_address": "192.168.1.50"}})
        self.assertNotIn("ports", svc, "a container at its own address publishes no ports")
        self.assertNotIn("x-fixed-network", svc)
        self.assertTrue(any("/mnt/disks/usb/x" in n for n in notes), notes)

    def test_not_started_with_the_machine_and_no_digest_said(self):
        comp, notes, auto = adoptapps.compose_for(APP, {"autostart": [], "digests": {}})
        self.assertFalse(auto)
        self.assertEqual(comp["services"]["plex-media-server"]["restart"], "no")
        self.assertTrue(any("no exact image" in n for n in notes))

    def test_a_writable_path_that_may_be_on_a_read_only_disk_is_said(self):
        _comp, notes, _auto = adoptapps.compose_for(APP, READ, writable=False, shares={"appdata": {"cache": "yes"}})
        self.assertTrue(any("/mnt/user/appdata/plex may be on a data disk" in n for n in notes), notes)
        self.assertFalse(any("/mnt/user/media" in n and "data disk" in n for n in notes), "a read-only path is fine")


class Read(unittest.TestCase):
    def test_a_docker_folder_says_what_ran_and_the_digest(self):
        root = tempfile.mkdtemp()
        os.makedirs(f"{root}/containers/abc")
        json.dump({"Name": "/Plex-Media-Server", "Image": "sha256:111", "Config": {"Image": "plexinc/pms-docker:latest"}},
                  open(f"{root}/containers/abc/config.v2.json", "w"))
        os.makedirs(f"{root}/image/btrfs")
        json.dump({"Repositories": {"plexinc/pms-docker": {"plexinc/pms-docker:latest": "sha256:111",
                                                           "plexinc/pms-docker@sha256:abc": "sha256:111"}}},
                  open(f"{root}/image/btrfs/repositories.json", "w"))
        open(f"{root}/autostart-list", "w").write("Plex-Media-Server wait\nOther\n")
        got = adopt.read_docker_root(root, "autostart-list")
        self.assertEqual(got["autostart"], ["Plex-Media-Server", "Other"])
        self.assertEqual(got["containers"]["Plex-Media-Server"], {"image": "plexinc/pms-docker:latest", "digest": "plexinc/pms-docker@sha256:abc"})

    def test_a_libvirt_folder_says_each_vm_and_whether_it_started(self):
        root = tempfile.mkdtemp()
        os.makedirs(f"{root}/qemu/autostart")
        os.makedirs(f"{root}/qemu/nvram")
        open(f"{root}/qemu/Windows 11.xml", "w").write(
            "<domain type='kvm'><name>Windows 11</name><os><loader>/x/OVMF_CODE.fd</loader><nvram>/etc/libvirt/qemu/nvram/u_VARS.fd</nvram></os><devices/></domain>")
        open(f"{root}/qemu/nvram/u_VARS.fd", "wb").write(b"\0" * 16)
        open(f"{root}/qemu/autostart/Windows 11.xml", "w").write("")
        got = adopt.read_libvirt_root(root)
        self.assertEqual([(x["name"], x["autostart"], bool(x["nvram"])) for x in got], [("Windows 11", True, True)])


class Rewrite(unittest.TestCase):
    def test_a_vm_runs_on_this_machines_qemu_firmware_and_lan(self):
        xml = ("<domain type='kvm'><name>vm</name><os><loader readonly='yes' type='pflash'>/usr/share/qemu/ovmf-x64/OVMF_CODE-pure-efi.fd</loader>"
               "<nvram>/etc/libvirt/qemu/nvram/u_VARS-pure-efi.fd</nvram></os><devices><emulator>/usr/local/sbin/qemu</emulator>"
               "<disk type='file'><source file='/mnt/user/domains/vm/vdisk1.img'/></disk>"
               "<interface type='bridge'><mac address='52:54:00:aa:bb:cc'/><source bridge='br0'/><model type='virtio'/></interface></devices></domain>")
        out, said = adopt.rewrite_domain(xml, "/usr/bin/qemu-system-x86_64", ("/usr/share/OVMF/OVMF_CODE_4M.fd", "/usr/share/OVMF/OVMF_VARS_4M.fd"),
                                         "/var/lib/libvirt/qemu/nvram/vm_VARS.fd", "enp3s0")
        self.assertIn("<emulator>/usr/bin/qemu-system-x86_64</emulator>", out)
        self.assertIn(">/usr/share/OVMF/OVMF_CODE_4M.fd</loader>", out)
        self.assertIn('template="/usr/share/OVMF/OVMF_VARS_4M.fd">/var/lib/libvirt/qemu/nvram/vm_VARS.fd</nvram>', out)
        self.assertIn('<interface type="direct"><mac address="52:54:00:aa:bb:cc" /><source dev="enp3s0" mode="bridge" />', out)
        self.assertIn("/mnt/user/domains/vm/vdisk1.img", out, "its disk where it was")
        self.assertEqual(len(said), 3)


U = "0f3a1b2c-1111-2222-3333-444455556666"
WIN = (f"<domain type='kvm'><name>Windows 11</name><uuid>{U}</uuid><os><loader>/x/OVMF_CODE.fd</loader></os>"
       "<devices><interface type='bridge'><mac address='52:54:00:aa:bb:cc'/><source bridge='virbr0'/></interface>"
       "<tpm model='tpm-tis'><backend type='emulator' version='2.0'/></tpm></devices></domain>")


class Settings(unittest.TestCase):
    """R163 step 16: what an adopted VM keeps that this machine can honor."""
    def test_its_tpm_state_is_found_wherever_the_old_system_kept_it(self):
        root = tempfile.mkdtemp()
        os.makedirs(f"{root}/qemu")
        os.makedirs(f"{root}/swtpm/{U}/tpm2")
        open(f"{root}/swtpm/{U}/tpm2/tpm2-00.permall", "wb").write(b"state")
        open(f"{root}/qemu/Windows 11.xml", "w").write(WIN)
        got = adopt.read_libvirt_root(root)
        self.assertEqual(got[0]["tpm"], f"{root}/swtpm/{U}")
        self.assertEqual(adopt.tpm_state(root, "not-a-uuid"), "")

    def test_a_nat_network_stays_a_network_and_its_mac_is_kept(self):
        root = tempfile.mkdtemp()
        os.makedirs(f"{root}/qemu/networks/autostart")
        open(f"{root}/qemu/networks/default.xml", "w").write(
            "<network><name>default</name><forward mode='nat'/><bridge name='virbr0'/><ip address='192.168.122.1' netmask='255.255.255.0'/></network>")
        open(f"{root}/qemu/networks/autostart/default.xml", "w").write("")
        nets = adopt.read_libvirt_networks(root)
        self.assertEqual([(n["name"], n["bridge"], n["autostart"]) for n in nets], [("default", "virbr0", True)])
        self.assertEqual(adopt.domain_networks(WIN, {"virbr0": "default"}, {"default"}), {"default"})
        out, said = adopt.rewrite_domain(WIN, "", None, "", "enp3s0", {"virbr0": "default"})
        out = out.replace('"', "'").replace(" />", "/>")
        self.assertIn("<interface type='network'><mac address='52:54:00:aa:bb:cc'/><source network='default'/>", out)
        self.assertNotIn("enp3s0", out, "not moved onto the LAN")

    def test_uefi_variables_carried_into_another_firmwares_store(self):
        d = tempfile.mkdtemp()
        tmpl, old, out = f"{d}/VARS_4M.fd", f"{d}/old.fd", f"{d}/new.fd"
        open(tmpl, "wb").write(b"T" * 64)
        open(old, "wb").write(b"O" * 32)
        calls = []

        def run(argv, **_k):
            calls.append(argv)
            if "-o" in argv:
                open(argv[argv.index("-o") + 1], "wb").write(b"N" * 64)
            return type("R", (), {"returncode": 0, "stdout": "", "stderr": ""})()
        from unittest import mock
        with mock.patch.object(adopt.shutil, "which", return_value="/usr/bin/virt-fw-vars"):
            said = adopt.carry_vars(old, tmpl, out, run=run)
        self.assertIn("carried", said)
        self.assertEqual(open(out, "rb").read(), b"N" * 64)
        self.assertEqual([c[1:3] for c in calls], [["-i", old], ["-i", tmpl]])
        with mock.patch.object(adopt.shutil, "which", return_value=None):
            self.assertIn("start fresh", adopt.carry_vars(old, tmpl, out, run=run))
        self.assertEqual(open(out, "rb").read(), b"T" * 64)
        open(old, "wb").write(b"O" * 64)
        self.assertEqual(adopt.carry_vars(old, tmpl, out, run=run), "", "the same size: the file itself")
        self.assertEqual(open(out, "rb").read(), b"O" * 64)

    def test_its_tpm_state_goes_where_libvirt_looks_for_it(self):
        d = tempfile.mkdtemp()
        os.makedirs(f"{d}/kept/tpm2")
        open(f"{d}/kept/tpm2/tpm2-00.permall", "wb").write(b"state")
        x = {"xml": WIN, "tpm": f"{d}/kept"}
        self.assertIn("without its TPM", adopt.carry_tpm(x, False, f"{d}/swtpm")[0])
        self.assertNotIn("<tpm", adopt.drop_tpm(WIN))
        self.assertIn("kept", adopt.carry_tpm(x, True, f"{d}/swtpm")[0])
        self.assertTrue(os.path.isfile(f"{d}/swtpm/{U}/tpm2/tpm2-00.permall"))
        self.assertIn("starts empty", adopt.carry_tpm({"xml": WIN, "tpm": ""}, True, f"{d}/swtpm")[0])
        self.assertEqual(adopt.carry_tpm({"xml": "<domain/>"}, True), [])

    def test_passthrough_held_from_boot_by_address_and_the_hosts_own_left(self):
        from unittest import mock
        vmhw = agentpkg.load("aerieos_agent_adopt_apps").module("vmhw")
        d = tempfile.mkdtemp()
        for a in ("0000:01:00.0", "0000:01:00.1", "0000:03:00.0"):
            os.makedirs(f"{d}/sys/bus/pci/devices/{a}")
        host = {"pci": [{"addr": "0000:03:00.0", "host": "the host's LAN interface"}]}
        with mock.patch.object(vmhw, "host_hw", return_value=host):
            held, why = vmhw.hold_for_vms(["0000:01:00.0", "0000:01:00.1", "0000:03:00.0", "0000:09:00.0", "x"],
                                          sys_root=f"{d}/sys", path=f"{d}/rules")
        self.assertEqual(held, ["0000:01:00.0", "0000:01:00.1"])
        self.assertEqual(len(why), 3)
        rules = open(f"{d}/rules").read()
        self.assertIn('KERNEL=="0000:01:00.1", ATTR{driver_override}="vfio-pci"', rules)
        self.assertNotIn("0000:03:00.0", rules)


if __name__ == "__main__":
    unittest.main()
