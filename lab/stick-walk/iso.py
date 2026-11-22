#!/usr/bin/env python3
"""The installer ISO in a VM, as a person installs it: a machine with one
blank disk boots the ISO, the console installer is worked by its keys, and
the installed disk is booted after. No root: QEMU with KVM, OVMF, a monitor
socket for the keys and the screen.

  iso.py boot ISO     a blank disk and the ISO; the disk boots first once it holds a system
  iso.py key K...     keys to the console, in order (ret, tab, spc, left, down, esc, a..z)
  iso.py shot NAME    the console's screen as run/iso/NAME.png
  iso.py say LINE [S] a line at the serial console (where the installed system logs in), and its answer
  iso.py off          the power button
  iso.py stop

ISO_NOVIRT=1 hides the CPU's virtualization from the guest (the usual VM:
no nested virtualization, so no /dev/kvm inside). ISO_DISK=sata gives the
disk as SATA with a serial; the default is virtio with none. ISO_DISKS=N
adds N more blank disks. The dashboard answers at 127.0.0.1:7690.
"""
import os
import socket
import subprocess
import sys
import time

HERE = os.path.dirname(os.path.abspath(__file__))
VM = os.path.join(HERE, "run", "iso")
MON = os.path.join(VM, "mon.sock")
PID = os.path.join(VM, "qemu.pid")
SER = os.path.join(VM, "serial.sock")


def hmp(*lines, wait=0.4):
    s = socket.socket(socket.AF_UNIX)
    s.connect(MON)
    s.settimeout(1)
    out = b""
    for line in lines:
        s.sendall(line.encode() + b"\n")
        time.sleep(wait)
    try:
        while True:
            d = s.recv(65536)
            if not d:
                break
            out += d
    except socket.timeout:
        pass
    s.close()
    return out.decode("utf-8", "replace")


def boot(iso):
    os.makedirs(VM, exist_ok=True)
    disk = os.path.join(VM, "disk.qcow2")
    if not os.path.exists(disk):
        subprocess.run(["qemu-img", "create", "-q", "-f", "qcow2", disk, "48G"], check=True)
    vars_ = os.path.join(VM, "vars.fd")
    if not os.path.exists(vars_):
        subprocess.run(["cp", "/usr/share/OVMF/OVMF_VARS_4M.fd", vars_], check=True)
    cpu = "host,vmx=off,svm=off" if os.environ.get("ISO_NOVIRT") == "1" else "host"
    cmd = ["qemu-system-x86_64", "-enable-kvm", "-cpu", cpu, "-m", "6144", "-smp", "4", "-machine", "q35",
           "-drive", "if=pflash,format=raw,readonly=on,file=/usr/share/OVMF/OVMF_CODE_4M.fd",
           "-drive", f"if=pflash,format=raw,file={vars_}",
           "-drive", f"file={disk},format=qcow2,if=none,id=sys"]
    if os.environ.get("ISO_DISK") == "sata":
        cmd += ["-device", "ide-hd,drive=sys,serial=WALKSYS0001,bootindex=0"]
    else:
        cmd += ["-device", "virtio-blk-pci,drive=sys,bootindex=0"]
    for i in range(int(os.environ.get("ISO_DISKS") or 0)):
        more = os.path.join(VM, f"more{i}.qcow2")
        if not os.path.exists(more):
            subprocess.run(["qemu-img", "create", "-q", "-f", "qcow2", more, "8G"], check=True)
        cmd += ["-drive", f"file={more},format=qcow2,if=none,id=more{i}", "-device", f"virtio-blk-pci,drive=more{i}"]
    cmd += ["-drive", f"file={iso},format=raw,if=none,id=cd,media=cdrom,readonly=on",
            "-device", "ide-cd,drive=cd,bootindex=1",
            "-netdev", "user,id=n0,hostname=vmguest,hostfwd=tcp:127.0.0.1:7690-:7680", "-device", "virtio-net-pci,netdev=n0",
            "-vga", "std", "-display", "none",
            "-monitor", f"unix:{MON},server=on,wait=off",
            "-chardev", f"socket,id=s0,path={SER},server=on,wait=off,logfile={VM}/serial.log,logappend=on",
            "-serial", "chardev:s0",
            "-daemonize", "-pidfile", PID]
    r = subprocess.run(cmd, capture_output=True, text=True)
    if r.returncode:
        sys.exit("qemu: " + r.stderr[-800:])
    print("booted", open(PID).read().strip(), "cpu", cpu)


def say(line, wait=3.0):
    """A line typed at the machine's serial console, and what it printed."""
    s = socket.socket(socket.AF_UNIX)
    s.connect(SER)
    s.settimeout(0.5)
    s.sendall(line.encode() + b"\n")
    out, end = b"", time.time() + wait
    while time.time() < end:
        try:
            out += s.recv(65536)
        except socket.timeout:
            pass
    s.close()
    print(out.decode("utf-8", "replace").replace("\r", ""))


def shot(name):
    ppm = os.path.join(VM, name + ".ppm")
    png = os.path.join(VM, name + ".png")
    hmp(f"screendump {ppm}", wait=1.0)
    subprocess.run(["ffmpeg", "-loglevel", "error", "-y", "-i", ppm, png], check=True)
    os.remove(ppm)
    print(png)


def stop():
    try:
        pid = int(open(PID).read())
        os.kill(pid, 15)
        print("stopped", pid)
    except (OSError, ValueError) as e:
        print("not running:", e)


if __name__ == "__main__":
    verb, args = sys.argv[1], sys.argv[2:]
    if verb == "boot":
        boot(args[0])
    elif verb == "key":
        hmp(*[f"sendkey {k}" for k in args], wait=0.5)
    elif verb == "type":
        # A line typed at the console, then Enter.
        names = {" ": "spc", "/": "slash", "-": "minus", ".": "dot", "=": "equal", "_": "shift-minus",
                 "|": "shift-backslash", ":": "shift-semicolon", ";": "semicolon", "*": "shift-8", "\"": "shift-apostrophe",
                 ">": "shift-dot", "<": "shift-comma", "&": "shift-7", "'": "apostrophe", ",": "comma", "$": "shift-4",
                 "(": "shift-9", ")": "shift-0", "+": "shift-equal", "?": "shift-slash", "#": "shift-3", "!": "shift-1",
                 "\\": "backslash", "[": "bracket_left", "]": "bracket_right", "{": "shift-bracket_left",
                 "}": "shift-bracket_right", "~": "shift-grave_accent", "%": "shift-5", "@": "shift-2", "^": "shift-6"}
        keys = [names.get(ch) or (f"shift-{ch.lower()}" if ch.isupper() else ch) for ch in " ".join(args)]
        hmp(*[f"sendkey {k}" for k in keys], "sendkey ret", wait=0.12)
    elif verb == "say":
        say(args[0], float(args[1]) if len(args) > 1 else 3.0)
    elif verb == "off":
        hmp("system_powerdown")
    elif verb == "reset":
        hmp("system_reset")
    elif verb == "eject":
        hmp("eject -f cd")
    elif verb == "shot":
        shot(args[0])
    elif verb == "stop":
        stop()
    else:
        sys.exit(__doc__)
