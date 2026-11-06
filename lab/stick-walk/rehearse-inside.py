#!/usr/bin/env python3
"""The move off another NAS rehearsed inside the walked stick, as root, with
the branch's own agent (R163 step 4): three blank disks and the NVMe laid out
as the old system left them (an XFS and a btrfs data disk with files, a
parity disk with an empty partition, a btrfs cache pool), its Docker and
libvirt image files on the array (a container that started with the
machine; a UEFI VM with a TPM's state, its disk under /mnt/user/domains and
its NIC on the old NAT network), then every step a person takes, each
checked: adopt read-only, read what ran, define the VM, clone it into a
space, take the array over, check the parity, run the mover, Release
refused, destroy, Release; every file's checksum the same at each stage.
Prints PASS or FAIL per check and ends with the count. Run by rehearse.py.
"""
import hashlib
import json
import os
import shutil
import subprocess
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
os.environ.setdefault("BUILDERBOT_VM_DIR", "/root/vmdir")
from aerieos_agent import adopt, array, vms, workspace  # noqa: E402

FAILS = []
U = "0f3a1b2c-1111-2222-3333-444455556666"


def ok(cond, what):
    print(("PASS  " if cond else "FAIL  ") + what, flush=True)
    if not cond:
        FAILS.append(what)


def sh(cmd):
    return subprocess.run(cmd, shell=True, capture_output=True, text=True)


class Job:
    def __init__(self):
        self.t = []

    def say(self, x):
        self.t.append(x)

    def text(self):
        return "".join(self.t)


class A(array.ArrayMixin, adopt.AdoptMixin, vms.VmsMixin, workspace.WorkspaceMixin):
    def _sh(self, job, argv, timeout=0, **k):
        r = subprocess.run(argv, capture_output=True, text=True, timeout=timeout or None)
        job.say(f"$ {' '.join(argv)[:160]} -> {r.returncode}\n{(r.stdout + r.stderr)[-800:]}")
        return r.returncode

    def hello_again(self, why):
        pass

    def drop_privileges(self, env):
        return {}


def run(fn, *a):
    job = Job()
    st = fn(job, *a)
    return st, job.text()


def sums(root):
    out = {}
    for here, dirs, names in os.walk(root):
        dirs[:] = [d for d in dirs if d != "system"]
        for n in names:
            if n.startswith(".snapraid"):
                continue
            p = os.path.join(here, n)
            with open(p, "rb") as f:
                out[os.path.relpath(p, root)] = hashlib.sha256(f.read()).hexdigest()[:16]
    return out


def lay():
    """The old system's disks, as it left them."""
    for d in ("vda", "vdb", "vdc", "nvme0n1"):
        sh(f"wipefs -a -q /dev/{d}?* /dev/{d}p?* 2>/dev/null; wipefs -a -q /dev/{d}; echo 'label: gpt\nstart=2048, type=0FC63DAF-8483-4772-8E79-3D69D8477DE4' | sfdisk -q /dev/{d}")
    # A partition made again where one was finds its old signature: the
    # parity partition holds none, as the old system's parity disk does not.
    sh("udevadm settle; wipefs -a -q /dev/vda1 /dev/vdb1 /dev/vdc1 /dev/nvme0n1p1")
    sh("mkfs.xfs -q -f /dev/vda1; mkfs.btrfs -q -f /dev/vdb1; mkfs.btrfs -q -f -L cache /dev/nvme0n1p1")
    m = "/root/lay"
    os.makedirs(m, exist_ok=True)
    sh(f"mount /dev/vda1 {m}")
    os.makedirs(f"{m}/TV Shows/s1")
    os.makedirs(f"{m}/domains/vm1")
    os.makedirs(f"{m}/system/libvirt")
    os.makedirs(f"{m}/system/docker")
    sh(f"head -c 5000000 /dev/urandom > '{m}/TV Shows/s1/e1.mkv'")
    sh(f"qemu-img create -q -f raw {m}/domains/vm1/vdisk1.img 64M; printf 'the guest disk' | dd of={m}/domains/vm1/vdisk1.img conv=notrunc 2>/dev/null")
    # libvirt's folder, in an image file of its own as the old system kept it.
    lv = "/root/lvroot"
    os.makedirs(f"{lv}/qemu/nvram", exist_ok=True)
    os.makedirs(f"{lv}/qemu/autostart", exist_ok=True)
    os.makedirs(f"{lv}/qemu/networks/autostart", exist_ok=True)
    os.makedirs(f"{lv}/swtpm/{U}/tpm2", exist_ok=True)
    with open(f"{lv}/swtpm/{U}/tpm2/tpm2-00.permall", "wb") as f:
        f.write(b"tpm state")
    shutil.copyfile("/usr/share/OVMF/OVMF_VARS_4M.fd", f"{lv}/qemu/nvram/{U}_VARS-pure-efi.fd")
    with open(f"{lv}/qemu/nvram/{U}_VARS-pure-efi.fd", "ab") as f:
        f.write(b"\0" * 4096)   # another firmware's size
    with open(f"{lv}/qemu/vm1.xml", "w") as f:
        f.write(f"""<domain type='kvm'><name>vm1</name><uuid>{U}</uuid><memory unit='KiB'>262144</memory><vcpu>1</vcpu>
<features><acpi/><apic/></features>
<os><type arch='x86_64' machine='q35'>hvm</type><loader readonly='yes' type='pflash'>/usr/share/qemu/ovmf-x64/OVMF_CODE-pure-efi-tpm.fd</loader>
<nvram>/etc/libvirt/qemu/nvram/{U}_VARS-pure-efi.fd</nvram></os><devices><emulator>/usr/local/sbin/qemu</emulator>
<disk type='file' device='disk'><driver name='qemu' type='raw'/><source file='/mnt/user/domains/vm1/vdisk1.img'/><target dev='vda' bus='virtio'/></disk>
<interface type='bridge'><mac address='52:54:00:aa:bb:cc'/><source bridge='virbr0'/><model type='virtio'/></interface>
<tpm model='tpm-tis'><backend type='emulator' version='2.0'/></tpm></devices></domain>""")
    open(f"{lv}/qemu/autostart/vm1.xml", "w").close()
    with open(f"{lv}/qemu/networks/default.xml", "w") as f:
        f.write("<network><name>default</name><forward mode='nat'/><bridge name='virbr0'/>"
                "<ip address='192.168.122.1' netmask='255.255.255.0'><dhcp><range start='192.168.122.2' end='192.168.122.254'/></dhcp></ip></network>")
    open(f"{lv}/qemu/networks/autostart/default.xml", "w").close()
    sh(f"truncate -s 300M {m}/system/libvirt/libvirt.img; mkfs.btrfs -q -f --rootdir {lv} {m}/system/libvirt/libvirt.img")
    # Docker's folder: one container, started with the machine.
    dk = "/root/dkroot"
    cid = "a" * 64
    os.makedirs(f"{dk}/containers/{cid}", exist_ok=True)
    os.makedirs(f"{dk}/image/btrfs", exist_ok=True)
    with open(f"{dk}/containers/{cid}/config.v2.json", "w") as f:
        json.dump({"Name": "/whoami", "Image": "sha256:" + "b" * 64, "Config": {"Image": "traefik/whoami:latest"}}, f)
    with open(f"{dk}/image/btrfs/repositories.json", "w") as f:
        json.dump({"Repositories": {"traefik/whoami": {"traefik/whoami@sha256:" + "c" * 64: "sha256:" + "b" * 64}}}, f)
    with open(f"{dk}/autostart", "w") as f:
        f.write("whoami\n")
    sh(f"truncate -s 300M {m}/system/docker/docker.img; mkfs.btrfs -q -f --rootdir {dk} {m}/system/docker/docker.img")
    sh(f"umount {m}; mount /dev/vdb1 {m}")
    os.makedirs(f"{m}/photos")
    sh(f"head -c 4000000 /dev/urandom > {m}/photos/p1.jpg")
    sh(f"umount {m}; mount /dev/nvme0n1p1 {m}")
    os.makedirs(f"{m}/appdata/whoami")
    os.makedirs(f"{m}/photos")   # an empty folder the old system left on its cache
    os.makedirs(f"{m}/TV Shows/s2")
    sh(f"head -c 100000 /dev/urandom > {m}/appdata/whoami/db; head -c 2000000 /dev/urandom > '{m}/TV Shows/s2/e2.mkv'; touch -d '2 hours ago' '{m}/TV Shows/s2/e2.mkv'")
    sh(f"umount {m}")


WANT = {"data": [{"slot": "disk1", "id": "WD-AAA111", "fs": "xfs"}, {"slot": "disk2", "id": "WD-BBB222", "fs": "btrfs"}],
        "parity": [{"slot": "parity", "id": "WD-CCC333"}],
        "pools": [{"name": "cache", "fs": "btrfs", "uuid": "", "disk_id": "NVME-NNN444"}], "writable": False, "from": "rehearsal"}


def main():
    a = A()
    os.makedirs("/root/vmdir/disks", exist_ok=True)
    os.makedirs("/run/aerieos-os", exist_ok=True)
    open("/run/aerieos-os/system-pool-ready", "a").close()
    sh("systemctl start libvirtd")
    lay()
    (st, _c), text = run(a._apply_storage_adopt, {"adopt": "adopt", "want": WANT})
    ok(st == "succeeded", "the old system's disks adopted read-only")
    before = sums("/mnt/user")
    ok(len(before) == 5, f"every file read through /mnt/user ({len(before)} files)")
    ok("ro," in sh("findmnt -no OPTIONS /mnt/disk1").stdout, "a data disk is read-only")
    (st, _c), text = run(a._apply_apps, "read-apps", {"docker": {"image": "/mnt/user/system/docker/docker.img", "autostart_file": "autostart"},
                                                      "vms": {"image": "/mnt/user/system/libvirt/libvirt.img", "vfio": []}})
    apps = adopt.read_apps()
    ok(st == "succeeded" and apps["docker"]["autostart"] == ["whoami"]
       and apps["docker"]["containers"]["whoami"]["digest"].endswith("c" * 64), "what Docker ran read, with its exact image")
    vm1 = next((v for v in apps.get("vms") or [] if v["name"] == "vm1"), {})
    ok(vm1.get("autostart") and vm1.get("nvram") and vm1.get("tpm"), "the VM read, its start with the machine, its UEFI variables and its TPM's state kept")
    ok([n["name"] for n in apps.get("vm_networks") or []] == ["default"], "the old NAT network read")
    ok(sums("/mnt/user") == before, "nothing changed by reading what ran")
    (st, _c), text = run(a._apply_apps, "define-vms", {"names": ["vm1"]})
    ok(st == "succeeded", "the VM defined here" + ("" if st == "succeeded" else f": {text[-400:]}"))
    x = sh("virsh -c qemu:///system dumpxml vm1").stdout
    ok("<source network='default'" in x and "52:54:00:aa:bb:cc" in x, "on the NAT network still, its MAC kept")
    ok("/mnt/user/domains/vm1/vdisk1.img" in x, "its disk where it was")
    ok("network default" in text or "the network default" in text, "the NAT network defined as the old system had it")
    tpm_said = "TPM's state kept" in text or "without its TPM" in text
    ok(tpm_said, "its TPM said: kept, or this image has no swtpm")
    ok("UEFI variables" in text, "its UEFI variables said")
    (st, _c), text = run(a.vm, {"action": "clone", "domain": "bbvm-web-vm1", "project": "web", "from": "vm1"})
    ok(st == "succeeded", "cloned into a space" + ("" if st == "succeeded" else f": {text[-300:]}"))
    back = sh("qemu-img convert -O raw /root/vmdir/disks/bbvm-web-vm1.qcow2 /root/back.raw && head -c 14 /root/back.raw").stdout
    ok(back == "the guest disk", "the clone's disk holds the guest's bytes")
    ok(sums("/mnt/user") == before, "the original's disk untouched by the clone")
    (st, _c), text = run(a._apply_storage_array, {"array": "takeover", "dry": True})
    ok(st == "succeeded" and "dry run: nothing changed" in text, "the takeover checked first, changing nothing")
    (st, _c), text = run(a._apply_storage_array, {"array": "takeover", "moves": [
        {"share": "TV Shows", "land": "cache", "from": "cache", "to": "array"}, {"share": "appdata", "land": "cache", "from": "", "to": ""},
        {"share": "photos", "land": "array", "from": "", "to": ""}]})
    ok(st == "succeeded", "the array taken over, its first sync done" + ("" if st == "succeeded" else f": {text[-400:]}"))
    # Each share lands where its settings say: a new file through /mnt/user
    # on the pool for one, on a data disk for the other.
    ok(not os.path.exists("/mnt/cache/photos"), "a share landing on the array has its empty folder on the cache removed")
    for f in ("/mnt/user/TV Shows/new.txt", "/mnt/user/photos/new.txt"):
        with open(f, "w") as fh:
            fh.write("new")
    ok(os.path.isfile("/mnt/cache/TV Shows/new.txt") and os.path.isfile("/mnt/disk2/photos/new.txt"),
       "a new file lands on the cache for TV Shows and on a data disk for photos")
    for f in ("/mnt/user/TV Shows/new.txt", "/mnt/user/photos/new.txt"):
        os.unlink(f)
    ok("ro," not in sh("findmnt -no OPTIONS /mnt/disk1").stdout, "the data disks writable where they are")
    new_on = [p for d in ("/mnt/disk1", "/mnt/disk2") for p in os.listdir(d) if p.startswith(".snapraid")]
    ok(sorted(new_on) == [".snapraid.content", ".snapraid.content"], "SnapRAID's content files the only new thing on the data disks")
    ok(sums("/mnt/user") == before, "every checksum the same after the takeover")
    (st, _c), text = run(a._apply_storage_array, {"array": "verify"})
    v = array.array_now().get("verify") or {}
    ok(st == "succeeded" and v.get("ok") and v.get("found") == 0, "Check parity: every block good")
    (st, _c), text = run(a._apply_storage_adopt, {"adopt": "release"})
    ok(st == "failed" and "destroy the array" in text, "Release waits until the array is destroyed")
    (st, _c), text = run(a._apply_storage_array, {"array": "mover"})
    ok(st == "succeeded" and not os.listdir("/mnt/cache/TV Shows"), "the mover took the old file off the cache")
    ok(os.path.isdir("/mnt/cache/appdata/whoami"), "appdata stays on the pool")
    ok(sums("/mnt/user") == before, "every checksum the same after the mover")
    (st, _c), text = run(a._apply_storage_array, {"array": "destroy", "confirm": "array"})
    ok(st == "succeeded", "the array destroyed, the data disks kept")
    (st, _c), text = run(a._apply_storage_adopt, {"adopt": "release"})
    ok(st == "succeeded" and not sh("findmnt -n /mnt/disk1").stdout, "released: everything unmounted")
    sh("virsh -c qemu:///system undefine --nvram bbvm-web-vm1; virsh -c qemu:///system undefine --nvram vm1")
    print(f"{'all passed' if not FAILS else f'{len(FAILS)} failed'}")
    return 1 if FAILS else 0


if __name__ == "__main__":
    sys.exit(main())
