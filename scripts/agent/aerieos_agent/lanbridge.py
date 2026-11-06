"""The host's wired LAN interface in a bridge on AerieOS (R219).

A VM on macvtap cannot talk to its own host, so a VM made a node on the
controller's own machine never reached its controller, and one a move
brought back could not knock. AerieOS puts the interface its default route
leaves by in a Linux bridge, br0, as the system it replaces did: the bridge
takes the interface's own MAC (MACAddress=none: the kernel gives a bridge its
first port's), so the router's reservation for that card still answers, and
the host's address moves to br0. A VM's port on br0 reaches the LAN and the
host alike.

Applied once, at a boot, by the own node's root agent: an update reboots
into the new image, so an existing machine takes it at the boot after its
update and a new install at its first. Committed and confirmed as the
Network page's change is: the files written, networkd reloaded, and br0 must
hold an address and the default route within CONFIRM_S, or the files go
back and the machine is as it was, said in the log and the census.

The Network page keeps working: its own file for br0 (00-builderbot-br0)
sorts ahead of this module's (10-aerieos-br0), and a static setting it had
written for the card itself moves to br0 here, since an address on a bridge
port is not an address the machine answers on.

Docker's forwarding drops what it does not know, and frames bridged
between a VM and the LAN pass through it once br_netfilter is loaded (Docker
loads it), so keep_forward() holds one rule in DOCKER-USER for br0.
"""
import contextlib
import os
import re
import subprocess
import time
import xml.etree.ElementTree as ET  # nosemgrep: python.lang.security.use-defused-xml.use-defused-xml (libvirt's own XML for this host's domains)

from .backends import _have
from .base import IPTABLES_BIN, NETWORKCTL_BIN, NETWORKD_DIR, _run, log

BRIDGE = "br0"
CONFIRM_S = 60
SYS_NET = os.environ.get("BUILDERBOT_SYS_NET", "/sys/class/net")


def _env(k, d):
    return os.environ.get(k, d)


def netdev_path():
    return os.path.join(NETWORKD_DIR, "00-aerieos-br0.netdev")


def port_path(iface):
    # Ahead of the image's 80-dhcp and of a 00-builderbot- file the Network
    # page wrote for the card (a < b): the first match is the one networkd reads.
    return os.path.join(NETWORKD_DIR, f"00-aerieos-port-{iface}.network")


def bridge_path():
    # Behind the Network page's 00-builderbot-br0, which is the person's say.
    return os.path.join(NETWORKD_DIR, "10-aerieos-br0.network")


def page_path(iface):
    return os.path.join(NETWORKD_DIR, f"00-builderbot-{iface}.network")


def is_bridge(iface, sys_net=None):
    return bool(iface) and os.path.isdir(os.path.join(sys_net or SYS_NET, iface, "bridge"))


def wired(iface, sys_net=None):
    """A physical wired interface: a device behind it, no wireless, not a bridge."""
    base = os.path.join(sys_net or SYS_NET, iface)
    return (bool(re.fullmatch(r"(en|eth)[A-Za-z0-9_.-]{0,13}", iface or "")) and os.path.exists(os.path.join(base, "device"))
            and not os.path.isdir(os.path.join(base, "wireless")) and not os.path.isdir(os.path.join(base, "bridge")))


def plan(iface, page_text=None):
    """{path: text or None} that puts `iface` in br0: the bridge, the card as
    its port, br0 on DHCP, and a Network page file for the card moved to br0
    (None removes a path). Pure, for the tests."""
    out: dict = {
        netdev_path(): "[NetDev]\nName=br0\nKind=bridge\n# The card's own MAC, so its DHCP reservation answers.\nMACAddress=none\n\n"
                       "[Bridge]\nSTP=no\n",
        port_path(iface): f"[Match]\nName={iface}\n\n[Network]\nBridge={BRIDGE}\n",
        bridge_path(): "[Match]\nName=br0\n\n[Network]\nDHCP=yes\n\n[DHCPv4]\n# By the MAC, as a router's reservation is.\nClientIdentifier=mac\n",
    }
    if page_text:
        out[page_path(BRIDGE)] = re.sub(r"(?m)^Name=.*$", f"Name={BRIDGE}", page_text)
        out[page_path(iface)] = None
    return out


def _snapshot(paths):
    got = {}
    for p in paths:
        try:
            with open(p, encoding="utf-8") as f:
                got[p] = f.read()
        except OSError:
            got[p] = None
    return got


def _write(files):
    for p, text in files.items():
        if text is None:
            with contextlib.suppress(OSError):
                os.remove(p)
            continue
        os.makedirs(os.path.dirname(p), exist_ok=True)
        with open(p + ".new", "w", encoding="utf-8") as f:
            os.fchmod(f.fileno(), 0o644)
            f.write(text)
        os.replace(p + ".new", p)


def _reload(iface):
    _run([NETWORKCTL_BIN, "reload"], timeout=30)
    _run([NETWORKCTL_BIN, "reconfigure", iface], timeout=30)
    _run([NETWORKCTL_BIN, "reconfigure", BRIDGE], timeout=30)


def _route_iface():
    for line in (_run(["ip", "route", "show", "default"]) or "").splitlines():
        m = re.search(r"\bdev (\S+)", line)
        if m:
            return m.group(1)
    return ""


def _has_v4(iface):
    return "inet " in (_run(["ip", "-4", "addr", "show", "dev", iface]) or "")


def _booted_recently(limit=900):
    try:
        with open("/proc/uptime", encoding="utf-8") as f:
            return float(f.read().split()[0]) < limit
    except (OSError, ValueError, IndexError):
        return False


def wanted(iface, os_image, booted, sys_net=None):
    """Why not to bridge now, or "" to go ahead."""
    if _env("BUILDERBOT_NO_LAN_BRIDGE", ""):
        return "switched off for this agent"
    if not os_image:
        return "not an AerieOS machine"
    if is_bridge(iface, sys_net):
        return "already bridged"
    if not booted:
        return "applied at the next boot, not under a running machine"
    if not wired(iface, sys_net):
        return f"{iface or 'no interface'} is not a wired card a bridge can take"
    return ""


def ensure(os_image, confirm_s=CONFIRM_S):
    """Bridge the LAN card, once, at a boot: (done, why). Reverted when br0 has
    no address and route within `confirm_s`."""
    iface = _route_iface()
    why = wanted(iface, os_image, _booted_recently())
    if why:
        return False, why
    pg = _snapshot([page_path(iface)])[page_path(iface)]
    files = plan(iface, pg)
    before = _snapshot(list(files))
    _write(files)
    log(f"LAN bridge: {iface} goes into {BRIDGE}, which takes its MAC and its address")
    _reload(iface)
    deadline = time.time() + confirm_s
    while time.time() < deadline:
        if _route_iface() == BRIDGE and _has_v4(BRIDGE):
            log(f"LAN bridge: {BRIDGE} is up on {iface} with the host's address; VMs on it reach the host and the LAN")
            moved = move_domains(iface)
            if moved:
                log(f"LAN bridge: {', '.join(moved)} moved from macvtap on {iface} to {BRIDGE}, from their next start")
            return True, ""
        time.sleep(2)
    _write(before)
    _reload(iface)
    log(f"LAN bridge: {BRIDGE} had no address within {confirm_s}s; put back as it was, {iface} on its own")
    return False, f"{BRIDGE} had no address within {confirm_s}s, so the change was put back"


def nic_xml(lan, mac_el="", model="virtio"):
    """A VM's interface on the LAN: a port on the bridge where `lan` is one,
    macvtap on the card otherwise (a host with no bridge)."""
    from xml.sax.saxutils import quoteattr  # nosemgrep: python.lang.security.use-defused-xml.use-defused-xml (escaping only)
    if is_bridge(lan):
        return f"<interface type='bridge'>{mac_el}<source bridge={quoteattr(lan)}/><model type={quoteattr(model)}/></interface>"
    return f"<interface type='direct'>{mac_el}<source dev={quoteattr(lan)} mode='bridge'/><model type={quoteattr(model)}/></interface>"


def to_bridge(xml, iface, bridge=BRIDGE):
    """A domain's XML with each macvtap interface on `iface` made a port on
    `bridge`: (xml, changed)."""
    dom = ET.fromstring(xml)
    changed = False
    for nic in dom.findall("devices/interface"):
        src = nic.find("source")
        if nic.get("type") == "direct" and src is not None and src.get("dev") == iface:
            nic.set("type", "bridge")
            src.attrib.clear()
            src.set("bridge", bridge)
            changed = True
    return (ET.tostring(dom, encoding="unicode") if changed else xml), changed


def move_domains(iface):
    """Every domain here on macvtap over `iface` defined again on br0; the
    names moved. A running one takes it at its next start."""
    if not _have("virsh"):
        return []
    moved = []
    for name in (_run(["virsh", "-c", "qemu:///system", "list", "--all", "--name"], timeout=20) or "").split():
        xml = _run(["virsh", "-c", "qemu:///system", "dumpxml", "--inactive", name], timeout=20) or ""
        if not xml:
            continue
        try:
            new, changed = to_bridge(xml, iface)
        except ET.ParseError:
            continue
        if not changed:
            continue
        r = subprocess.run(["virsh", "-c", "qemu:///system", "define", "/dev/stdin"], input=new, text=True,
                           capture_output=True, timeout=30, check=False)
        if r.returncode == 0:
            moved.append(name)
        else:
            log(f"LAN bridge: {name} could not be defined on {BRIDGE}: {(r.stderr or r.stdout).strip()[:200]}")
    return moved


FORWARD_RULE = ["-i", BRIDGE, "-o", BRIDGE, "-j", "ACCEPT"]


def keep_forward():
    """The one DOCKER-USER rule that lets frames bridged on br0 past Docker's
    forwarding: "" kept or nothing to do, else what iptables said."""
    if not is_bridge(BRIDGE) or not _have(IPTABLES_BIN):
        return ""
    ipt = [IPTABLES_BIN, "-w", "5"]
    if subprocess.run(ipt + ["-S", "DOCKER-USER"], capture_output=True, timeout=15, check=False).returncode:
        return ""
    if subprocess.run(ipt + ["-C", "DOCKER-USER", *FORWARD_RULE], capture_output=True, timeout=15, check=False).returncode == 0:
        return ""
    r = subprocess.run(ipt + ["-I", "DOCKER-USER", "1", *FORWARD_RULE], capture_output=True, text=True, timeout=15, check=False)
    return "" if r.returncode == 0 else ((r.stderr or r.stdout).strip()[:200] or "iptables refused the rule")
