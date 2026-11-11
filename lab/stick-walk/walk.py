#!/usr/bin/env python3
"""A stick booted in QEMU with blank disks, for walking a first run as a person.
  walk.py prep IMAGE.raw.xz    the stick (16 GB, sparse) and four blank disks
  walk.py boot | stop | status
  walk.py sh 'CMD'             root, through the debug shell on the second serial
"""
import os, socket, subprocess, sys, time
HERE = os.path.dirname(os.path.abspath(__file__))
VM = os.path.join(HERE, "run")
STICK = f"{VM}/stick.raw"
SOCK = "/tmp/vmwalk-root.sock"       # a unix socket's path has a short limit
DISKS = [("blank-a", "WD-AAA111", 30), ("blank-b", "WD-BBB222", 30), ("blank-c", "WD-CCC333", 30)]
NVME = ("blank-n", "NVME-NNN444", 20)
ARGS = b"console=ttyS0,115200"
ROOTSOCK = "/tmp/vmwalk-rootsh.sock"

def prep(img):
    os.makedirs(VM, exist_ok=True)
    if not os.path.exists(STICK):
        with open(STICK, "wb") as out:
            subprocess.run(["xz", "-dc", img], stdout=out, check=True)
        os.truncate(STICK, 16 << 30)
    # aerie_args in the ESP's grubenv, as CI's boot test sets it.
    with open(STICK, "r+b") as f:
        buf = f.read(1 << 30)
        i, at = -1, 0
        while True:
            at = buf.find(b"# GRUB Environment Block\n", at)
            assert at >= 0, "no grubenv in the first GB"
            if at % 512 == 0 and buf[at + 1023:at + 1024] == b"#":
                i = at
                break
            at += 1
        body = b"".join(l + b"\n" for l in buf[i:i + 1024].rstrip(b"#").split(b"\n") if l and not l.startswith(b"aerie_args="))
        body += b"aerie_args=" + ARGS + b"\n"
        f.seek(i); f.write(body + b"#" * (1024 - len(body)))
        print("grubenv at", i, body.decode().replace("\n", " | "))
    for name, _, gb in DISKS + [NVME]:
        p = f"{VM}/{name}.raw"
        if not os.path.exists(p):
            with open(p, "wb") as f:
                f.truncate(gb << 30)
    vars_ = f"{VM}/vars.fd"
    if not os.path.exists(vars_):
        subprocess.run(["cp", "/usr/share/OVMF/OVMF_VARS_4M.fd", vars_], check=True)

def boot():
    cmd = ["qemu-system-x86_64", "-enable-kvm", "-cpu", "host", "-m", "8192", "-smp", "4", "-machine", os.environ.get("WALK_MACHINE", "q35"),
           "-drive", "if=pflash,format=raw,readonly=on,file=/usr/share/OVMF/OVMF_CODE_4M.fd",
           "-drive", f"if=pflash,format=raw,file={VM}/vars.fd",
           "-drive", f"file={STICK},format=raw,if=none,id=stick", "-device", "qemu-xhci", "-device", "usb-storage,drive=stick,removable=on,bootindex=0",
           "-netdev", "user,id=n0,hostname=newserver,hostfwd=tcp:127.0.0.1:7690-:7680,hostfwd=tcp:127.0.0.1:1445-:445", "-device", "virtio-net-pci,netdev=n0",
           "-display", "none", "-chardev", f"socket,id=s0,path={SOCK},server=on,wait=off,logfile={VM}/serial.log,logappend=on", "-serial", "chardev:s0", "-chardev", f"socket,id=s1,path={ROOTSOCK},server=on,wait=off,logfile={VM}/root.log", "-serial", "chardev:s1",
           "-daemonize", "-pidfile", f"{VM}/qemu.pid"]
    # WALK_QEMU_EXTRA: more of QEMU's arguments, one string (an IOMMU, a spare card to hold for a VM).
    cmd += os.environ.get("WALK_QEMU_EXTRA", "").split()
    for name, serial, _ in DISKS:
        cmd += ["-drive", f"file={VM}/{name}.raw,format=raw,if=none,id={name}", "-device", f"virtio-blk-pci,drive={name},serial={serial}"]
    name, serial, _ = NVME
    cmd += ["-drive", f"file={VM}/{name}.raw,format=raw,if=none,id={name}", "-device", f"nvme,drive={name},serial={serial}"]
    r = subprocess.run(cmd, capture_output=True, text=True)
    if r.returncode:
        sys.exit("qemu: " + r.stderr[-800:])
    print("booted", open(f"{VM}/qemu.pid").read().strip())

def stop():
    try:
        pid = int(open(f"{VM}/qemu.pid").read())
        os.kill(pid, 15)
        print("stopped", pid)
    except (OSError, ValueError) as e:
        print("not running:", e)

def sh(cmd, timeout=120):
    mark = f"__END{int(time.time() * 1000)}__"
    s = socket.socket(socket.AF_UNIX)
    s.connect(ROOTSOCK)
    s.settimeout(1)
    # set +H first, on a line of its own: the shell at the other end is an
    # interactive bash, where a bang in the command would be read as history.
    s.sendall(f"\nset +H 2>/dev/null\n( {cmd} ) 2>&1; echo {mark} $?\n".encode())
    out, end = b"", time.time() + timeout
    while time.time() < end:
        try:
            d = s.recv(65536)
            if d:
                out += d
        except socket.timeout:
            pass
        if out.count(mark.encode()) >= 2:
            break
    text = out.decode("utf-8", "replace").replace("\r", "")
    i = text.find(mark, text.find(mark) + 1)
    first = text.find("\n", text.find(mark))
    print(text[first + 1:i + len(mark) + 4] if i > 0 else text[-2000:])

def login():
    """The console, as a person logs in at the screen: admin and the console password, then sudo."""
    s = socket.socket(socket.AF_UNIX); s.connect(SOCK); s.settimeout(1)
    def say(x, wait=3):
        s.sendall(x.encode() + b"\n")
        out, end = b"", time.time() + wait
        while time.time() < end:
            try:
                out += s.recv(65536)
            except socket.timeout:
                pass
        return out.decode("utf-8", "replace")
    print(say("", 3)[-300:])
    print(say("admin", 3)[-200:])
    print(say(sys.argv[2], 5)[-300:])
    print(say("sudo -i", 4)[-200:])
    print(say(sys.argv[2], 4)[-200:])
    print(say("export PS1='# '; stty -echo; id -u", 3)[-200:])

{"prep": lambda: prep(sys.argv[2]), "boot": boot, "stop": stop, "login": login, "sh": lambda: sh(" ".join(sys.argv[2:]))}[sys.argv[1]]()
