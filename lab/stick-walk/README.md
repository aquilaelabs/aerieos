# Walking a first run on a real stick image

`go.sh IMAGE.stick.raw.xz` boots a stick image in QEMU with KVM, no root, with three blank hard disks and an NVMe, and does what a person does: the first page, the account, making the pools, shares, Claude Code, a project and Finish, in a real browser, then a reboot. The suites fake the job calls, so they cannot find what this finds; this found that blank disks could not be made into anything, that nothing could reach a share and that a machine lost its node at every reboot.

Needs `/dev/kvm`, OVMF, `xz` and Playwright. Port 7690 is the VM's dashboard and 1445 its SMB. Its files land in `run/`, which is not committed.

- `walk.py`: lay out the stick and disks, boot, stop, and `sh CMD` for root on the VM through its second serial port.
- `rescue.py`: pick the boot menu's Rescue over serial and run commands there.
- `person.mjs` and `steps.mjs`: one browser step per run, its sign-in kept: `node person.mjs jobs`, `node person.mjs look HASH NAME`.
- `rehearse.py`: the move off another NAS rehearsed on the booted stick with this branch's agent, as root: the three blank disks and the NVMe laid out as the old system left them (data disks with files, a parity disk, a cache pool, its Docker and libvirt image files), then adopted, its VM defined and cloned into a space, the array taken over, its parity checked, the mover run, destroyed and released, every file's checksum compared at each stage. It prints a PASS or FAIL line per check. The disks are laid out afresh each run; the stick's libvirt is started for it with its state in memory.

An image from a release carries that release's code. To walk a branch, copy its dashboard over the VM's after first boot, as root.

A real client over SMB takes Debian's `smbclient` unpacked in the VM to a temporary folder (`dpkg -x`), since `curl` speaks only SMB1, which Samba refuses.

## The installer ISO in a VM

`iso.py boot ISO` gives a VM one blank disk and the ISO in its drive, and the installer on its console is worked as a person works it: `iso.py key ret left ret`, `iso.py type "a line"`, `iso.py shot NAME` for the screen. `ISO_NOVIRT=1` hides the CPU's virtualization from the guest, which is what most VMs are (no `/dev/kvm` inside); `ISO_DISK=sata` and `ISO_DISKS=N` change the disks. Once it has installed, `iso.py eject` and Enter restart it into its disk, the dashboard answers at port 7690 for `person.mjs` (`look`, `words`, `press`, `api`), and `iso.py say LINE` types at the serial console, where the installed system logs in (set the console password from the Nodes page first).

First walked on 11 Nov 2026 with the published 0.9.0-dev.5173 ISO, which could not install on a blank machine at all.
