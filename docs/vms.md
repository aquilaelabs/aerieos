# VMs

A space's virtual machines, made, started, stopped, snapshotted and removed
on the nodes whose VM host feature is installed, by a person on the VMs page
or by a space's session with `aerie vm`, under the space's own
setting. The VMs page sits in the Containers group beside Containers, and
is built from the Containers page's pieces.

**The machine's own VMs** (R165): a VM may belong to the machine rather
than a space: Belongs to on New VM offers "This machine's own" to an
administrator, and such a VM is keyed under `machine`, grouped and chipped
as This machine's own on the VMs page, acted on by administrators alone
under the VMs area, and never a session's (a session sees its own
space's VMs and nothing else). It is for the NAS's own apps and
desktops (a Home Assistant VM, a Windows desktop) on any VM host, the
controller's own machine first where there is one; its network is its
own as a space's is, or the LAN from its Hardware dialog.

## Where a VM runs

A VM runs on a node with **VM host** installed: KVM through libvirt, put
there by Enroll node's tick or by the node's Features section on the Nodes
page (`bb-sandbox feature install vmhost`, the same install either way). It
needs `/dev/kvm`. A node that is itself a VM has that only when its host
passes virtualization through: CPU mode host-passthrough (a host's CPU mode
set to host passthrough, Proxmox's CPU type host) and nested KVM on in the host's
`kvm_intel` or `kvm_amd`. Without it the Features row says so, and offers no
Install: a VM in software emulation would be tens of times slower.

The VMs' images and disks are in `/var/lib/aerieos/vms` on the node,
owned by the jobs account, which is in the libvirt group; no session can
reach libvirt. Removing VM host is refused while any VM is there, and takes
off exactly the packages its install added.

On the controller's own machine (a bare-metal install, the appliance) VM
host installs too, with one difference: libvirt's group is root on that
machine, so the jobs account stays out of it and the VMs there run through
the node's root agent, each action still one of its table's. Domains the
machine's libvirt has that AerieOS did not make (made with virt-manager,
say, or another system's VMs taken over with its disks) are listed on the
VMs page for an administrator under **Not AerieOS's**, by name, state and
size; the page never changes one. **Clone into a space** on a shut-off one
makes a copy that is AerieOS's: each of its disk files copied into the
node's VM folder as qcow2 (the original untouched), its UEFI variables
copied, and the domain defined again with its own UUID, AerieOS's marker
and its hardware as it was (vCPUs, memory, firmware, MAC address and
passthrough; a disk passed through whole is shared, not copied, and said
so). The copy is then managed on the VMs page like any other, under the
space or as This machine's own; the original stays defined until it is
removed, and since the two share a MAC address, one runs at a time.

## What a VM is made from

An OS from `config/vm-images.json`, asked for by name in any of the ways a
person says it (`debian`, `Debian 12`, `ubuntu-24.04`, `noble`, `rocky`,
`leap 16`): Ubuntu 26.04 and 24.04, Debian 13 and 12, Fedora 44, Rocky Linux
10 and 9, AlmaLinux 9, CentOS Stream 9, Arch, openSUSE Leap 16 and
Tumbleweed, Gentoo, Alpine 3.24. Gentoo's image is a dated build, which the
catalog moves on by hand. Each is its publisher's cloud image, downloaded once per node
and checked against the checksum file the publisher posts beside it before
it is kept. cloud-init makes one account (`builder`, sudo without a password)
that lets in the ssh keys given and no password. `aerie vm os` lists them.

Windows and macOS are in the catalog only to be refused by name: each has a
license to accept or a key to enter, which a session never does for a
person, and AerieOS does not make them.

## The dial, the area and the limits

- **Make VMs**, under Agents may in the space's settings, reads as Run its
  container does: deny (the default) refuses a session's `aerie vm`, ask holds
  each for the administrators' bell with Allow and Deny, auto does it. A
  person may always do from the page what the dial holds a session to
  asking for. Changing it is the VMs area's.
- **VMs**, a space area in the roles: Read sees its VMs, Write makes,
  starts, stops, snapshots and removes them. Every role that held Containers
  was given VMs at the same level when this arrived (state migration 0002).
- **What its VMs may hold** in the space's settings: how many, and their
  vCPUs, memory and disk added up (4, 8, 16 GB and 200 GB by default). Each
  node keeps 2 GB of memory and 10 GB of disk for itself besides. A VM that
  would pass either is refused with the limit named.

## The network

Each space has a network of its own on each node, a /24 out of
10.232.0.0/16 kept for it, NAT'd to the internet. A table of AerieOS's
own (`builderbot_vmnet`) keeps a VM off other spaces' VMs, off the LAN
(unless the node's Features row lets its VMs onto it), and off the node
itself but for the DHCP and DNS libvirt serves; the controller's address and
port it reaches. Its space's sessions reach it, by ssh and anything else,
through the sessions' own table; no other space's session does.

The Hardware dialog picks a VM's network as a machine's VM settings do:
**Network source** is its space's network, the LAN (on AerieOS a port on
`br0`, below), any other bridge on the host by name, or a libvirt network
by name, grouped as Bridges and libvirt networks; **Network model** is
virtio, e1000e, e1000, rtl8139 or vmxnet3, for a guest with no virtio
driver; **Network MAC** keeps the address a router's reservation knows,
and Regenerate makes a new one. Anything but its space's network takes the
VM past the table above, so a session cannot pick it: a person does, in
the dialog.

## Snapshots

A VM's state saved under a name and gone back to, as in VMware: libvirt's
own, inside its qcow2 disk. A running VM's memory is kept too, so a revert
lands where it was, mid-program. Listed under its row with Revert and
Delete; `aerie vm snapshot NAME SNAP`, `aerie vm revert NAME SNAP` and `aerie vm
snapshot-rm NAME SNAP` from a session, under the same dial. A snapshot taken
before a session changes a VM is the undo.

## Made a node

New VM's **Make it a node** and `aerie vm new --node-agent` enroll the VM as a
node at its first boot: Enroll node's own script, for the OS's system, run by
cloud-init and removed once it has run. It appears on the Nodes page marked
as a VM on its host, and is retired with its credential revoked when the VM
is removed. A session's is always an administrator's to allow, whatever the
dial says: adding a node is theirs.

A VM made a node is not on its space's network, and its own account is
`admin`, not `builder`: `builder` is the account its sessions run as, which
has no sudo, where cloud-init gives the VM's own account sudo. It joins the LAN
and takes an address from the LAN's DHCP like any other machine, because the
controller reaches a node at its address (its sessions' terminals, its Docker
over SSH), which a space network behind the host's NAT does not give it. Its
firewall is the one the provisioner makes on every node, and the VMs page
shows the address its agent dials in from.

How it joins depends on the host. On AerieOS the wired card the machine's
default route leaves by is a port of a bridge, `br0`, which takes the card's
own MAC (so the router's reservation for the card still answers) and the
machine's address; a VM on the LAN is a port on `br0` too, and reaches the
LAN and its own host alike, so a node VM on the controller's own machine
dials in to it, and one a move brings back knocks there as any node does.
The bridge is made once, at a boot, and put back as it was when `br0` has no
address within a minute; a machine updated to it takes it at the boot after
its update, and its VMs on macvtap move to `br0` from their next start. The
Network page's settings for the machine are `br0`'s from then on. Elsewhere a
VM joins through the card itself (macvtap), which other machines reach but
its own host does not: there, put node VMs on another machine than the
controller's.

## Console and Screen

**Console** on a running VM's row opens its serial console in the dock,
`virsh console` as the jobs account on the node's container terminal
server, for a person with a shell and VMs Write on its space. Ctrl+]
leaves it.

**Screen** opens the VM's display in the dock: keyboard, mouse and all,
drawn by noVNC, which the image carries. Every VM has one, on its host's
loopback alone; the node's agent relays it on port 7684, the port its
terminals come in on too, which it opens to the controller alone, and only for a request the
controller signed for that VM within the last two minutes. It takes VMs
Write on the VM's space, since seeing a screen is driving the machine.
A screen password set at New VM is asked for when it opens.

A Screen is shared: several people can have it open at once, all on one
keyboard and mouse. A Console is one person's at a time, and opening it
takes it from whoever had it. The VM's row says who is on its Screen and who
has its Console. While somebody has the Console, anybody else is refused
it; the space's owner and the administrators may take it over, asked
first, and the person it is taken from is told who took it.

## From an installer

For a system the catalog does not carry (Windows, a BSD, an appliance, a
distribution of your own), New VM's **From** has **Add an ISO…**: an https
address and the SHA-256 its publisher gives, fetched onto the node and
kept only when it matches; or an .iso uploaded from your computer, sent
through the controller (up to 16 GB, held there only until the node has
taken it) and checked on the node against the hash taken as it arrived. The ISO is then offered under **From** on that
node. A VM made from it boots the installer with a blank disk of the size
given, UEFI or BIOS as picked, and nothing of AerieOS's inside it (no
account, no key, no cloud-init): its **Screen** is where you install it.
Once the system is on its disk, **Eject ISO** under More empties the drive
so it boots from the disk. Making one is a person's: a session has no screen
to install from, and is refused.

**More** at New VM gives any VM up to three further disks (vdb to vdd), a
MAC address kept for good (so a DHCP reservation holds) and the screen's
password; every disk hands freed space back to the pool (discard) and has
a serial of its own, the same every boot, for `/dev/disk/by-id`. **Grow
disk** on a stopped VM makes one of its disks larger, never smaller; the
partition inside is the system's own to grow. **Add disk** gives a stopped
VM the next of vdb to vdd, there at its next start.

## Hardware

New VM's **More**, and **Hardware…** under a stopped VM's More, set what
a VM has beyond its size; a change lands at its next start, and the row
says what it was given.

- **CPU threads**: its vCPUs pinned to host threads, picked in each core's
  pair as the node reports them. A thread another VM on the node is pinned
  to is refused unless **Share them** is ticked.
- **Memory ceiling**: it starts with its memory and may balloon up to
  this, through a virtio balloon; empty for none.
- **Network**: its space's own network, or the LAN as a machine of its
  own through the node's wired interface (refused on Wi-Fi, which cannot
  carry it).
- **Shared folder**: a folder of the space, read-only if ticked, seen
  inside the VM through virtiofs: `mount -t virtiofs project /mnt`. It is
  always inside the space; a dot shares the whole of it. Inside, its files
  are the VM's own account's (uid 2000), and what anyone in the VM writes is
  the folder owner's on the node, so nothing in the space turns root's.
  A node whose VM host was installed before this asks for **Bring in shared
  folders** on its Features row.
- **Devices passed through**: a USB device by its vendor and product, or a
  PCI device (a GPU, its sound, a controller) by its address. These are an
  administrator's alone, and a PCI device needs the IOMMU on in the node's
  firmware and kernel (`intel_iommu=on` or `amd_iommu=on`, which the node's
  Features section turns on); the dialog says when it is off. A card the
  host's own driver holds is this machine's: the node's Features section
  marks it for a VM, which binds it to vfio-pci from the next boot, and only
  then is it offered. A card the
  node's own display runs on is refused, and so is a device that shares its
  IOMMU group with something the host needs (its LAN interface, the
  controller of a mounted disk), with what shares it. A USB device is
  simpler given from the node's page, below, which needs no stop.
- **Dump vBIOS**, beside a GPU: reads the card's ROM on the node as root
  and keeps it, so passing it through hands the VM a clean copy, which
  some cards need before a VM will start with them. A card that reads
  short is woken by a moment in a throwaway VM and read again. **Give a
  .rom…** keeps one from the card's maker, or from a collection of them,
  instead. libvirt hands a passed-through PCI device to vfio-pci when its VM
  starts and gives it back when it stops.

**Starts with its host**, on the row and at New VM, starts the VM whenever
its node boots; a VM made a node always does.

## USB devices

A node's page has a **USB** section once VM host is installed there: each
USB device the machine reports (its name, vendor and product, serial, bus
and port, speed and the driver holding it) with what holds it: **free**,
**the host** (with why: it boots from it, a partition is mounted, it is in
a pool) or the VM it was given to. **Give to a VM** picks one of that
node's VMs and queues the node's `usb-give` job: libvirt's hostdev for the
device, attached live to a running VM and written into its definition, so
a running VM has it now and at its next start and a stopped one from its
next start; **Take back** detaches it the same way. The device is named by
its vendor, product and serial, so it is found again after a replug or a
reboot wherever it is plugged in; two alike with no serial are told apart
by their port, and a VM given one of those is pointed at the right one each
time it starts. A device pulled out does not keep the VM from starting
(the hostdev is optional). The VM's row on the VMs page names the devices
it holds. Giving or taking is an administrator's, since a device can be a
disk or a key; the section draws no press for anyone else.

The section's **Controllers** list the machine's USB controllers with what
hangs off each and its IOMMU group: a controller goes to a VM whole, with
everything on it, through the VM's **Hardware…** dialog (VFIO, the VM
stopped), for a device that misbehaves over USB passthrough. One sharing
its group with something the host needs says so and stays. The IOMMU
itself is a feature on the node's Features section: **Install** puts
`intel_iommu=on` or `amd_iommu=on` with `iommu=pt` on the kernel's command
line (through grubby, GRUB, extlinux or systemd-boot, whichever boots the
machine) and the row asks for a restart; if the groups stay empty after
one, VT-d or AMD-Vi is off in the firmware.

## From a session

```
aerie vm                       this project's VMs: state, OS, node, address, size, snapshots
aerie vm os                    the operating systems there are
aerie vm new db --os debian --mem 4G --disk 30 --why "a database to test the migration on"
aerie vm ssh db                in, as builder, with the session's own key (made when there is none)
aerie vm snapshot db clean     before changing it
aerie vm revert db clean       and back
aerie vm stop db && aerie vm grow db 60          a larger disk; the system inside grows its partition
aerie vm hardware db --pin 2,3 --mem-max 8G --share data --ro
aerie vm autostart db on       it starts when its node boots
aerie vm devices               the USB devices on the project's VM hosts, each with what holds it
aerie vm usb db give 0781:5583:4C53   a device to the VM, held for a person on the bell
aerie vm usb db take 0781:5583:4C53   and back
aerie vm rm db
```

Each is under the same Make VMs setting as making one. A session's
hardware stops at its own space: it may pin, give a memory ceiling and
share a folder of the space, while putting a VM on the LAN and passing a
device through are a person's, from the VMs page; a USB device asked for
with `aerie vm usb` is held for an administrator on the bell whatever Make VMs
says, since a device can be a disk or a key.
