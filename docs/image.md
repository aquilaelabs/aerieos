# AerieOS: the appliance image

The installed editions of AerieOS (the installable OS, its VM disk, and
the USB edition) are made from one image: Debian stable, built by
[mkosi](https://mkosi.systemd.io/) from the definition in `image/`, sealed as
a read-only root and laid into a disk with two root slots. An update is a
whole new root written into the slot not in use, and a bad one falls back
to the one that was. This page says what the image is, what persists on it,
how it boots, and how it is built. The decisions behind it are in
[decisions.md](decisions.md), "The appliance image".

## What it is

- **Debian 13 (trixie), x86-64**, every package pinned to one dated
  [snapshot.debian.org](https://snapshot.debian.org) archive, named in
  `image/SNAPSHOT`, so a build from the same inputs is the same image.
- **The kernel Debian ships, with ZFS built against it** in the image
  (`zfs-dkms` at build time), so the two never part.
- **The controller staged in**, exactly as a bare-metal install lays it out
  (`nodes/install-controller.sh --stage`, run inside the tree by
  `image/mkosi.postinst`): the account, `/opt/aerieos`, the env file,
  `aerie`, the sudo rule and the service, enabled for the first boot. Its
  packages come from the one list the container image and a bare-metal
  install read, `config/controller-packages.tsv`.
- **Everything the node half needs**: what `nodes/provision-linux.sh`
  installs on a Debian node (python, tmux, git, the reel's X tools,
  WireGuard, nftables), Debian's own docker, the VM host's qemu and
  libvirt, Samba and NFS, NUT for a UPS, and the disk tools the Storage
  page uses (smartmontools, ZFS, mergerfs, SnapRAID).
- **No apt.** `apt` and `apt-get` are diverted to a stub that says why: the
  root forgets at the next boot, and a package installed into it would be
  gone without a word. A tool a space needs is a toolchain, from the
  Library; a package the node needs is added to
  `image/mkosi.conf` and comes with the next image.

## The disk

`image/build.sh` lays the image into one GPT disk, `aerieos-os-VERSION.raw`
(compressed with xz), and the same disk with the slot loaded into memory at boot as `aerieos-os-VERSION.stick.raw.xz`, the USB edition's. Every partition has a fixed UUID, the same on every
disk AerieOS makes, held in `image/partitions.sh` and read by the build,
the initramfs, `fstab` and GRUB alike:

| Partition | Size | What |
|---|---|---|
| `bios` | 1 MiB | GRUB's core for a BIOS boot |
| `esp` | 512 MiB | the ESP: GRUB for UEFI and BIOS, one menu, its environment, each slot's kernel and initrd under `/aerieos/a` and `/aerieos/b` |
| `bbroot-a` | 4 GiB | root slot A: a squashfs, read-only |
| `bbroot-b` | 4 GiB | root slot B: empty until an update writes it |
| `bbdata` | 2 GiB in the image, the rest of the disk when installed | `/var`, and under it the changes to `/etc` |

Beside the disk, the build leaves the slot's squashfs (`.root.squashfs`),
its kernel and initrd, and the release stamp, each with a `.sha256`; the ISO
carries the same four under `live/`, which is where an update takes them
from.

## On a stick, run from memory

The same disk written to a USB stick is the USB edition's base (R161): with
`aerie_toram=1` in GRUB's environment (`slot ram on`; the stick maker sets
it) the initramfs copies the slot's squashfs into memory, exactly its
bytes, and the root is that copy, so the stick is read once at boot and the
system runs from memory; `/var` and `/etc`'s changes stay
on the stick's data partition, apart from both slots, and an update writes
the other slot as on a disk. `slot status` says when the root is in memory.
A machine needs the slot's size in memory beside what it runs (about 2 GB).

A machine's own kernel arguments (the IOMMU, CPUs kept for VMs) are
`aerie_args` in the same environment, which every boot entry ends with:
`slot args NAME=VALUE...` sets them, each in place of one of that name,
`slot args-off NAME...` takes them off, and plain `slot args` prints them;
each counts from the next boot. The IOMMU switch on the Nodes page's
Features sets its arguments this way.

**The stick is written rarely.** Flash wears with every write, and many
small synced writes are what make a stick slow, so on a stick boot it keeps
the configuration and little else. Its data partition is flushed once a
minute rather than every five seconds. The system's logs (`/var/log`), the
controller's own logs and the journal are kept in memory, so they start
again at each boot; the controller's logs go to a pool when Controller
settings' paths put them there. What writes all day, docker's images and
containers, the VMs, the toolchains and the spaces, lives on a **system
pool**, and so does the secrets folder with the install key, so the stick
alone opens nothing the controller sealed: picked on the Nodes page under **Pool and spaces** from the pools and the
array the machine has, it is where those folders are bound at every boot,
and picking it moves what the stick held of them there. Until one is
picked, docker and the VMs wait, and the spaces are held (the secrets stay
on the stick until a pool is picked; once one is, a boot where it is not
mounted holds the secrets folder empty, makes no key, and restarts the
controller when the pool mounts): the spaces
folder is an empty read-only mount of its own, no space is made, cloned
or moved in, and they are never written to the stick. **Pool and spaces**
also says what still lives on the stick and how much has been written to it,
in its life and since this boot. An installed disk has none of this: its
data partition is the machine's disk.

**The spaces where they already are.** Under **Pool and spaces**, the
**Spaces folder** names a folder already on the machine's disks as the
spaces folder: a share of the disks the machine adopted, a pool or the
array, never the stick, and never a disk adopted read only. It is bound
over the spaces folder at every boot in place of the system pool's, with
no pool needed, and the controller restarts on it. Its files are handed to
the controller's own account and the folder closed to other accounts, as a
spaces folder it made is: their owner changes and nothing in them does, since
git refuses a tree another account owns, the controller could not write it, and
sessions on this machine are refused while anybody can walk into the spaces.
A share of that folder stops serving other people. The job says which of the
controller's spaces the folder holds and which it does not, and what the
spaces folder held before stays underneath, unseen, until **Let it go**
binds the pool's again.

The system that had the folder cannot read it after that, so it is given back
before going back. Who had it is written down first: a copy the machine keeps
for itself, which **Let it go** runs, and `.aerieos-give-back.sh` in the folder,
which stays with the disks, so from the old system, as root, the same is
`bash FOLDER/.aerieos-give-back.sh`. The folder's copy belongs to the
controller's account with the rest of the folder, so read it before running
it; **Let it go** never runs that one.

**A move onto a stick lands last,** since it would otherwise land on the stick.
The first page asks whether you are moving a controller here. Say yes and give
the move token, with no account to make, and the next page is **Moving here**, a walk of the steps in
the order they have to happen, each done on that page: what to have with you
(the move token and the bundle), the disks, where the spaces and containers
go, landing the controller, what comes after it, and the way back. Every install
takes the same walk with the steps it has: a stick made from another system's
backup adopts that system's disks in it and says what going back costs, any
other stick makes its own, and an install with no stick goes straight to
landing. The steps it cannot go on without come in order: each waits, with a
line saying which step it waits for, until the ones before it are done, and
while the machine runs a job (adopting the disks, moving to a pool) every step
that would start another waits for it, the page saying what runs. **Walk me
through it** and **Set up a new one instead** go between the walk and a new
start. The stick's own partition is small (a few gigabytes until a system
pool takes docker, the spaces and the secrets off it), and the Nodes page says
how much room it has left, as the bell does when it runs low: the
controller stops when it is full. A
pool the machine adopted can be the system pool whatever its filesystem; a
data disk cannot, since it carries the old system's parity. **Read only**
writes nothing to the data disks, so with no writable pool nothing new has
anywhere to go: moving for good takes **Writable**, or a spare disk made into
a pool. The move is the same one Controller settings lands, under **Move a
controller here** (the token with the old controller's address, or the
bundle). An old controller that ran on this machine is off by now, so its
address does not answer and the bundle is the only way. It is spooled and
unpacked in the spaces folder on the disks, and its state takes the setup
account's place.
A controller whose spaces already sit on these disks needs no repositories
in its bundle: name their folder first, and they are found where they are.

**The data partition takes the stick's room.** The image's data partition
is 2 GB; at each boot it is grown to the end of the stick (the filesystem
with it, while mounted) and never shrunk. `BB_DATA_MAX` in `aerieos.env`
caps it (`64G`, `512M`, `2T`; a bare number is GiB), to leave the rest of a
big stick unused.

## The configuration backed up, and a new stick

With a backup password set under Controller settings, Backup, the
controller keeps a sealed copy of its configuration (the same bundle a move
carries: the state without its logs, the stores, the secrets; never the
repositories) after every change, once the state has been quiet for a
quarter of an hour: under the state, and on every pool of the machine at
`/mnt/POOL/.builderbot/backup`, the five newest in each; Back up now writes
one at once, and each copy under the state is downloadable. Backup copies'
**Also copied to** sends each copy as well to a disk or share ticked under
Other disks and shares (`/mnt/other/NAME/.builderbot/backup`), so one is off
the machine. The key is the password's (scrypt), so a copy carried off is a
sealed file. These copies are the controller, not the files on the pools:
the Storage page's snapshots and Backups keep those.

A stick that dies is replaced by one written from the release's image with
no configuration: its first page offers *Restoring a saved configuration*,
lists the copies found on the machine's pools (newest first, with the
machine and the version each came from) and takes the password, or takes a
copy you kept; held to the same gate as a move (never onto an older build),
restored and restarted, the machine is the controller as it was, its nodes
checking back in. A node whose token rotated since the copy was made is
taken back by itself: it keeps the tokens it held over the last month and
offers them, newest first, and the one the restored record knows earns it a
fresh one. A node that is gone is simply never back.

## The stick maker

On Windows, **AerieOS USB Maker** (`aerieos-usb-maker-VERSION.exe`,
attached to every release) does it in a window: which release (the newest,
the newest dev build, one by name, or an image file you have), which stick
(the removable disks alone), a few settings for the first boot (the dev
channel, a name, a time zone, a fixed address), and a last page naming the
stick by model and size, with a box to tick, before it is erased; then the
progress and the read back. It asks for Administrator once at start, since
writing a disk needs it, and every step in it is the stick maker's own.

`tools/aerieos-stick.py` writes a release's stick image onto a USB
stick on Windows, a Mac or Linux with nothing but Python's own library: `list`
names the removable disks here (the system disk marked, and never written),
`write DISK` fetches the newest release's `aerieos-os-VERSION.stick.raw.xz`
(or `--release vX.Y.Z`'s, or writes `--image FILE`) with its sha256, checks
it, says what is on the stick is lost, writes the disk whole and reads it
back; `verify` reads a stick back against an image. `--set KEY=VALUE`, as
often as needed, writes a line into the stick's `aerieos.env`, the file on
the ESP each boot reads: `TZ` (`Europe/Berlin`) and `BB_RELEASE_LINE` (the
release line updates follow, `0.9`) for the controller, and the stick's
network settings. `BB_HOSTNAME` names the machine; `BB_NET_ADDRESS`
(`192.0.2.20`) gives the wired interfaces a static address instead of
DHCP, with `BB_NET_MASK` (`24` or `255.255.255.0`, `24` when left out),
`BB_NET_GATEWAY` and `BB_NET_DNS` (`1.1.1.1,9.9.9.9`). `BB_DATA_MAX` caps the
stick's data partition (below). A value that is not
an address is said in the boot's log and DHCP stands, so a mistyped stick
still comes up on the network. The file is 4 KiB laid by the image itself, and
the maker writes the lines into those same bytes as the image streams, so
nothing writes a FAT partition by hand on any system; with the stick in
another machine it is a plain file to edit, and `verify` takes the same
`--set` to read such a stick back.

`--mirror FILE` writes a mirror of the vetted catalog (the archive
`tools/catalog-mirror.py` makes, up to 64 MiB) into the stick's
`aerieos/catalog-mirror.bin`, laid and filled the same way. Each boot
hands it to the controller, which imports it as it starts, once per mirror,
so a machine with no network installs tool packs from the Library (Tool
packs' Without the network says how the mirror is used). The stick keeps
it; it holds nothing secret.

`--config FILE` writes a prepared configuration into the stick's
`aerieos/firstboot.json` (64 KiB, laid and filled the same way), which the
first boot applies before anyone signs in. It is a JSON object:

```json
{"format": 1, "first_run": "skip",
 "machine": {"hostname": "tower", "timezone": "Europe/Berlin",
             "network": {"address": "192.0.2.20", "netmask": "255.255.255.0",
                         "gateway": "192.0.2.1", "dns": ["1.1.1.1"]}},
 "owner": {"name": "ada", "password_hash": "pbkdf2_sha256$600000$SALT$HASH"},
 "people": [{"name": "sam", "role": "user", "smb_nt": "NTHASH"}],
 "shares": [], "pools": [], "array": {}, "apps": []}
```

`machine` may also carry `"kernel_args"`, a list of kernel arguments for
VMs given the machine's own devices and CPUs (`isolcpus`, `nohz_full`,
`rcu_nocbs`, `intel_iommu`, `amd_iommu`, `iommu`, `pcie_acs_override`,
`video`, `vfio-pci.ids`, the `kvm` and hugepage options; anything else is
left out and said), put on every boot entry from the next restart, and
`"features"`, any of `vmhost` and `iommu`, turned on with the machine's
own node as the installer's are.

Before the controller starts, the boot sets the hostname and the time zone,
writes a static address (`"network": "dhcp"` or leaving it out keeps DHCP)
into the stick's `aerieos.env` as the `BB_NET_` lines above, unless the
stick already names one, hands the rest to the controller and blanks the file on the stick, so the
password hash is never left there. The controller makes the owner from the
hash (the dashboard's own scheme, so a tool that writes the file hashes what
was typed) and each person by name and role, with their SMB password where
it came with them and no dashboard password until the owner sets one on the
Users page. `"first_run": "skip"` marks the setup page done unless the plan names disks, which that page walks through, and `"hold_first_start": true`
holds that first start, so the disks are on the Nodes page before anything
mounts; without an
owner's hash the first-run page makes the owner as on any stick. The shares,
pools, array and apps wait until their disks are adopted. The machine's row's
**First boot** section says what was applied, what waits and what could
not be, and nothing of a hash is kept on the controller beyond the accounts
themselves. It runs as root (sudo) on Linux and a
Mac and as an administrator on Windows, where it locks and dismounts the
stick's volumes first. A stick made this way boots the appliance with the
slot loaded into memory and keeps its configuration on the stick's data
partition. Its network settings are the `BB_NET_` lines in `aerieos.env`;
without them the stick takes DHCP.

## A graphics card

The image carries the NVIDIA driver (Debian's, its kernel module built
into the image) and NVIDIA's container toolkit, registered with Docker, so
a machine with an NVIDIA card has the driver on it from the first boot and
a container that asks for the card gets it; nouveau is kept off the card.
On a machine without a card the modules stay unloaded. An AMD card or APU
runs on the kernel's own amdgpu driver with the firmware the image carries.
Which way a card is used, by this machine and its containers or by one VM
through vfio, is a choice under Features on the Nodes page (R207).

## Its disks at the first run

A machine that is its own controller has a disks step in its first run,
after This machine. It lists every disk but the one it runs from, by model,
size, kind and serial; a disk that holds something is kept unless you tick
it. You say how safe the storage should be (no copy, one disk may fail, two
disks may fail) rather than pick a RAID level, and it picks the layout from
the disks and says why: disks of one size become a ZFS mirror, raidz1 or
raidz2, which checks every block and repairs one that rots; disks of mixed
sizes become an array with its largest disk as parity, which uses every
disk and grows one at a time; an SSD beside hard disks becomes a fast pool
of its own for apps, VMs and spaces, never a cache. As you choose it says
how much you can use, how many disks may fail and how it grows, and
Advanced picks another layout. **Make it** names every disk it erases by
serial before anything is written. On a stick the first pool made becomes the
system pool by itself, a fast one where there is one, and a later step says so.
A pool that holds an earlier AerieOS install's data (its containers, VMs,
spaces and the accounts' sign-ins) is never taken as the system pool: a
reinstall starts clean, and that controller is brought over only with a move
token from it.
**Shares** is the next step and is optional. A share is a folder on a pool, Media
and Backups to begin with, and stays on this machine until you export it; then
other computers open it over the network, signing in with the same name and
password as the dashboard. The Storage page does all of this too, later, the same
way, with each share's security and each person's access. On a stick made with a prepared configuration that
names disks to adopt, those disks are the old system's: each is listed as
such, with no box, and the step makes nothing of them; they are taken as
they are in the first-run page's walk, and later on the Nodes page under The old system's disks.

Once they are adopted, the Nodes page and the Storage page show them under
**Adopted disks**, with the folders at the top of `/mnt/user` that had no
share settings offered to serve as the old system did. **Take the array
over** (after **Check the takeover**, which says every step and changes
nothing) makes the data disks writable where they are, never formatting
one, gives the old parity disk's first partition a filesystem for
SnapRAID's parity, and starts the first sync, which builds the parity from
nothing. That sync runs in the background, hours for a large array, with
its progress on the Nodes page and the Storage page (a bar, since SnapRAID
says how far it is): the takeover's job ends at once, so the machine's
other jobs are not held behind it. The array is unprotected until the sync
ends. Taking the array over is not a step of the first-run walk: it is
done from here afterwards, and the bell carries a row saying the array
has no parity yet, with the Nodes page on it, until it is taken over or the
disks are released. SnapRAID's content files, its catalogue of every block
of the array, live on the data disks; on a stick none goes on the stick's
own partition, where one for a large array would fill it. The array then
appears on the Storage page with its sync, scrub and Check parity, each a
run in the background too. Each share keeps its places as the old
system had them: where its new files land (a pool, or the array) and what
the mover does with them, from what to what (a pool to the array, the
array to a pool, one pool to another, or nothing). They are set before the
takeover, starting from the old system's own settings, with when the mover
runs, and changed later from each share's Edit on the Storage page. A new
file lands on the first pool that holds its share's folder and on the data
disks where none does, so the agent keeps each share's folder where it
lands and removes its empty folders elsewhere; a folder with anything in it
is never touched.

The takeover finds the old parity disk by the serial the adoption read, never
by its device name, which a reboot or a stick plugged in can give another
disk, and stops before writing anything unless every data disk is mounted.
The mover moves a file only when both its places are mounted (an empty
mount point is the stick's memory), leaves one whose path is already on the
other side, one a program holds open and one written in the last ten
minutes for its next run, and never follows a share folder that is a link.
A sync, scrub or parity check is refused while any disk of the array is not
mounted.

**Going back to the old system** on the Nodes page says the way back for the
state the disks are in: nothing to do while they are read-only, a parity
check there once they were written to, and a new configuration with its
parity rebuilt once the array was taken over. Nothing here repartitions or
reformats a data disk, upgrades a ZFS pool or turns on a btrfs feature, and
the old system's stick is never written.

## At the console

A machine running AerieOS welcomes whoever is at its screen with
AerieOS's logo above the login prompt, the release and slot it runs, and
the address to open the dashboard at (this machine's address and the
dashboard's port), which the console fills in and redraws as the network
comes up. The installer opens on the same logo. Both are plain characters,
so a serial console or a server's remote screen draws them too.

To log in at the screen (a monitor or a KVM), set a console password on
the Console section of its row on the Nodes page: it logs in as `admin`, with `sudo` for
root, and it is separate from the dashboard's password. The image's root
forgets everything at each boot, so the password's hash is kept on the
data partition and the account is made from it at every start; until one
is set, the screen says where to set it. While a machine is first set up,
`admin` logs in with no password and `sudo` asks for none, so there is a way
in if the agent or the dashboard stops partway. **Generate console login** at the top
of the first-run page shows a password once; setup's end, or setting one, closes that login. It opens only on a
machine's first boot, so an update never opens it on an install already set
up, and it is a login at the screen or serial line only. Root itself has no
password. When
nothing else answers, the boot menu's **Rescue** entry, beside Safe mode,
starts nothing and opens a root shell at the screen: whoever is at the
keyboard can already take the disks out, so it opens nothing they do not
have, and it is never the default.

## Setting up a new machine

A new machine is set up from the USB edition: the stick's image, written
with the USB maker or `tools/aerieos-stick.py`, booted on the machine, and
the dashboard's first page at `http://ITS-ADDRESS:7680` on the LAN, which
makes the owner, names the machine and sets up its disks as a pool or an
array ([On a stick](#on-a-stick-run-from-memory), [The stick maker](#the-stick-maker)).

`aerieos-os-VERSION.iso` is not an installer. It is the file a machine
already running AerieOS updates from ([Updating](#updating)): the same root,
kernel and initrd under `live/`. Booted by itself (UEFI or BIOS) its menu
starts nothing on its own; its one entry runs AerieOS from the medium with
nothing installed and nothing kept, for a look or a rescue, and the other
says where a new machine starts. An installer on the machine's own screen,
which puts this system on a disk and sets up the machine's disks there, is
being built; until it is, no release offers one.

The console installer that the ISO used to open is still in the image, for
the build's check and for what replaces it: with `bbinstaller=1` on the
kernel's line it lists the machine's disks (the medium left out), asks which
to lay out and which features to turn on, and lays the disk out with the
script that made the image (`image/lay-disk`). With
`aerie_install_to=/dev/DISK` beside it the install asks nothing: that disk
is laid out with no feature turned on, each step is said on the kernel's
console, and the machine turns itself off at the end. That is how the build
checks that its ISO lays out a blank disk that then boots; no menu carries
either word.

## In a VM

A VM runs the USB edition as a machine does: the stick's image
(`aerieos-os-VERSION.stick.raw.xz`, unpacked) as its first disk, and at
least one more virtual disk for a pool, since the stick keeps the
configuration and the containers' data goes on a pool. The build also
converts the raw disk, never laid out again, into
`aerieos-os-VERSION.qcow2` and `aerieos-os-VERSION.ova` (a
stream-optimized VMDK with its OVF descriptor, `image/ovf.xml`, and a
manifest), which the boot test runs and the CI run keeps as its artifact;
a release does not carry them. Give the VM two processors and 4 GB at least, and
turn nested virtualization on for it where VMs are to run inside it (the
Features row says when `/dev/kvm` is missing); the data partition is grown
to the disk the hypervisor gives it at boot, so a disk made bigger later is
taken up at the next one.

## What persists

The root is read-only, with a tmpfs over it (`overlayroot`): anything
written anywhere in it lives until the next boot. What is made to last is on
the data partition and mounted by the initramfs
(`image/mkosi.extra/etc/initramfs-tools/scripts/init-bottom/aerieos-os`)
before the system starts, so PID 1 sees it from its first read:

- **`/var`**, the data partition itself: the controller's state and
  secrets' home, the spaces, docker, libvirt, the logs.
- **`/etc`**, as an overlay whose upper half is `/var/lib/aerieos-os/etc`:
  an account made, a hostname set, a unit enabled or a share written is kept
  across boots, and every file the next image brings still shows through
  unless a changed copy sits over it.
- **`/usr/local`**, an overlay the same way: the machine's own node, its agent,
  `bb-sandbox` and `bb-session`, which first boot installs there.
- **`/srv`, `/home` and `/workspace`**, bound from the data partition: the
  spaces, each account's home and sign-ins, and the node's workspace. A
  system pool takes them off a stick, with Docker and the VMs.

Nothing else persists, which is what makes an update a whole image.

## How it boots

GRUB on the ESP reads its environment (`grubenv`) for `aerie_slot`, the slot to
boot, and shows both slots in its menu for three seconds. The slot's kernel
and initrd are on the ESP; the kernel's command line names the slot's root
partition by its UUID and the slot by name (`aerieslot=a`). The initramfs mounts
the squashfs, puts the tmpfs over it, mounts `/var` and `/etc`'s overlay,
and the system starts.

The first boot of a disk runs `aerieos-os-firstboot.service` once: it
waits for the controller, which the image's own service started, puts up
the wall between the controller and the sessions, and enrolls the machine as
its controller's own node, as a bare-metal install's last step does. From
there the machine is what [install.md](install.md)'s bare-metal section
describes, and its row is on the Nodes page.

`/usr/lib/aerieos-os/slot` is the slot tool: `current` (the slot this
boot came from), `other`, `next [a|b]` (the one GRUB boots next time, which
is what an update sets once it has written the other slot) and `status`.
An updated slot's trial and Safe mode are under [Updating](#updating).

## Building it

CI builds the image on a hosted runner with a workflow of its own,
`.github/workflows/os-image.yml`, which builds it and then boots the VM
disk under QEMU until the dashboard answers (`appliance-boot`), and the ISO
installed onto a blank disk there, which is then booted to its dashboard. The image
build calls it on every release tag, from the Actions page's *Run
workflow* with its *appliance* box ticked, and weekly; a branch push that
touches the image runs it alone and publishes nothing, so a fix to the
image is proved on a push. A release carries two of its files, the ISO and
the stick's image, each with its sha256 and a build attestation, and only
after the boot (`appliance-publish`); the raw disk, the qcow2 and the OVA
stay the run's artifact.
The weekly run takes the day before's snapshot, builds, and says in its
summary which system packages moved since the last release (each image
carries its package list, `.packages`); a patch release from it is a press
on a tag, never the run's own doing.

By hand, on a Debian or Ubuntu machine with root (mkosi installs packages,
and the disk is assembled on a loop device):

```bash
pip install 'mkosi @ https://github.com/systemd/mkosi/archive/refs/tags/v25.3.tar.gz'   # the version build.sh pins; mkosi is not on PyPI
sudo apt install squashfs-tools dosfstools e2fsprogs fdisk grub-efi-amd64-bin grub-pc-bin grub-common xz-utils xorriso mtools qemu-utils
sudo image/build.sh --out image/out
```

`--tree-only` stops after mkosi, with the tree under `image/out/mkosi/tree`
to look at; `--from-tree DIR` assembles a disk from a tree built before.
Moving the pin is editing `image/SNAPSHOT` to a newer timestamp; the weekly
rebuild takes the day before's snapshot on its own.

## Updating

A newer release is found the way a bare-metal install's is (checked weekly
unless Controller settings' Update checks says otherwise, and on **Check
now** under Controller settings, Updates, and said on the bell). It follows
the release line the install is on (`BB_RELEASE_LINE`, which the stick
maker's `--set` writes) and the releases as published; the dev builds'
channel is in [versions.md](versions.md#two-channels). On AerieOS **Update** does not run the installer: the own
node's root agent fetches the release's ISO, checks it against the sha256
the release carries and against its build attestation (`gh attestation
verify`; an image that does not verify, or a machine without `gh`, writes
nothing), opens it read-only and takes the root, the kernel, the initrd and
the stamp out of its `live/` folder as plain files, points the next boot
back at the slot running now, writes the slot not in use, puts the kernel
beside it on the ESP, and only then names that slot for the next boot, on
trial, in one write. An update is refused while the slot running now is
itself on trial, since the other slot is then the only good one, and when
a second AerieOS disk or stick in the machine carries the same slot.
Nothing running changes until you restart
from This controller, and the slot running now stays to fall back to: at the
GRUB menu, or with `slot next a`. The Updates section says which slot runs
and which boots next.

An offline machine takes the same files from a folder on it (a stick, a
share): **Update from the folder** under Updates, the folder holding the
release's ISO with its `.sha256` and its `.attestation.jsonl` beside it,
all three from the release. The ISO is checked against both with no
network: the attestation against the trusted root the running image was
built with, so a folder on a share others can write cannot hand over an
image AerieOS's release workflow did not build. A release's attestation
is read from GitHub's public API, and neither way asks for a sign-in.

**The release key.** The sha256 and the attestation prove a file is the one
AerieOS's release workflow built, which is not enough when the workflow
or the repository itself is changed by someone else: they would build and
attest a release of their own. So a release also carries `SHA256SUMS` and
`SHA256SUMS.sig`, the list of its files' sha256 signed with an Ed25519 key
that lives offline on the release key holder's own machine
(`tools/release-sign.py sign TAG`), never in CI, the repository or a
controller. The keys a signature must verify against are the install's own
copy of `config/release-signers`, read from the image it is running, never
from the release: an update that no key this install already held signed
is refused, by the OS updater, the stick maker (`write` checks the image it
fetched against the list) and the installer alike. Each checks with
OpenSSH's `ssh-keygen -Y verify`. While `config/release-signers` holds no
key the check is skipped and said so, which is how a build before the first
key behaves; once it holds one, an unsigned release is refused. The key's
fingerprint is published on aerieos.org to check the file against.

**On trial.** The slot an update wrote boots on trial: GRUB counts each
boot of it in its environment, and the health check
(`aerieos-os-health.service`) marks it good once the controller's health
answer (`/api/v1/healthz`) says it is up, three times running, and the
node's agent runs. A trial boot that is not healthy
within ten minutes restarts, a kernel or initramfs that panics restarts
after fifteen seconds, and a kernel that will not load falls to the slot
before at once; a second boot without the health check's word goes back to
the slot before by itself, and This controller says so until the next update.
Picking the slot before from the menu during a trial ends the trial there,
and visiting an older version is refused while one runs. The new image's
own boot menu goes on the disk only once its slot is marked good, so a
release whose menu is broken cannot take away the way back.
Before an update the controller's configuration is copied to
`/var/lib/aerieos-os/before/` (the two newest kept), first, and an update
that cannot take that copy writes nothing. The other slot's old release is
taken off it before its root is written, so a write cut short leaves a slot
that reads as empty, never as the version it held. A boot that fell
back puts that copy back before the controller starts, when the newer slot
moved the configuration on further than the slot before reads, and so does
the slot before picked by hand from the boot menu, when a newer build wrote
the configuration; what it held is kept in
`/var/lib/aerieos-os/rolled-back-TIME/`. A patch carries no
configuration change, so falling back on one boots the same configuration
as it is.

**Older versions.** A slot holds a whole AerieOS, its controller and
agent with it. When an update is about to overwrite the slot not in use, the
version in it is kept instead of lost, as files under
`/var/lib/aerieos-os/kept/` with the configuration's copy from when it was
left: about 2 GB each, the three newest by default (Update window's **Older
versions kept on the boot menu**, 0 for none). Each is an entry under **Older
versions** on the boot menu and a row on This controller, whose **Boot this next**
visits it once. A visit loads its root into memory from the data partition, on
a disk as on a stick. It lasts one boot: the next restart is the version it came
from, and one that does not come up restarts into it by itself. If the
configuration has moved on further than that version reads, its copy is used and
yours is set aside, and comes back when the visit ends; what the visit changed
is set aside in `/var/lib/aerieos-os/rolled-back-TIME-visit/`. Updates wait
until a visit ends. An image built before this feature cannot boot from files,
so it is said and not kept, and a version kept already is never replaced by
what the slot holds later. The menu on the ESP follows the image running, so a
disk laid by an older image takes the entry with its first update.

**The short address.** On a controller's own machine the dashboard stays on its
port, and plain `http://THE-MACHINE/` finds it: a small redirect holds port 80
while nothing else wants it. It lets go as soon as the machine has an nginx
container, and for as long as containers are being started, so nothing that
publishes port 80 finds it taken by this. Once nginx holds the port the short
address stops: nginx closes a request that names none of your sites and never
points it at the dashboard, so use the address with its port, or give the
dashboard a route of its own on the nginx page.

**The boot menu.** Each slot is named with its version, the slot that
boots is the default after four seconds, and **Safe mode** boots the slot
that runs now with the start held: the dashboard and the shares come up
and nothing else starts (no container, VM or session) until Start is
pressed on This controller.

**Update window.** By default nothing is applied by itself. Under
Controller settings, *Update window* names a day (daily, or one weekday)
and an hour; in that hour a newer release is applied the way Update does
it, once per release, and the restart still waits for you.

## What is not here yet

The boot in CI does not yet try a ZFS pool and an array on virtual disks, a
share over SMB, a node enrolled and a container started, or the browser
suites against the booted system; those are proved by hand on a machine
for now.
