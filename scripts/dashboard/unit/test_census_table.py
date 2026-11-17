"""The census as a table (nodes.CENSUS): what a node says about itself is
whitelisted field by field, one cleaner per field, each with its caps.

Three things are held here. The table keeps what the one long function
kept, to the byte: a census that touches every field, with good and bad
values, oversized strings and lists and wrong types, and one wrong value
of each type under each key and under each field's own keys, against what
_census answered before it was a table, frozen below as JSON so the key
order is held too. Each row names the census keys its cleaner reads, so
the table knows every key it keeps and says once, on stderr, which it does
not. And every key the node agent can put in its census is one the table
reads, unless the allowlist below says why the controller leaves it.

A change made on purpose to what a field keeps changes its frozen answers:
`python3 test_census_table.py freeze` prints them as this checkout's
_census gives them, to put in place of the block at the end, and the diff
of that block is the change as a node's record sees it."""
import ast
import contextlib
import functools
import hashlib
import io
import json
import os
import sys
import unittest
from unittest import mock

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, os.path.join(HERE, ".."))
import nodes  # noqa: E402

AGENT = os.path.normpath(os.path.join(HERE, "..", "..", "agent", "aerieos_agent"))

# Longer than any cap the census has (the array's status, 400).
L = "L" * 500


def rich():
    """Every field the controller reads, each with good values, bad ones
    beside them, strings past their caps and lists past theirs (the item a
    cap drops is a valid one, so dropping it shows), and one key nothing
    reads."""
    return {
        "cpu": 8, "mem_mb": "16384",
        "os": "linux x86_64 " + L, "docker": "27.3.1", "docker_id": "ABCD:EFGH", "gpu": "", "hostname": "node-1",
        "git": "git version 2.43.0",
        "machine": "0123456789abcdef0123456789abcdef",
        "system": "Linux!", "arch": "x86_64;rm",
        "sshd": 1,
        "stores": {
            "toolchains": {"path": "/srv/tc/" + L, "id": "id-" + L, "free_mb": 1000, "total_mb": "2000", "used_mb": None,
                           "scope": "linux-x86_64;rm -rf"},
            "data": {"path": "/srv/data", "id": "abc", "free_mb": float("inf"), "total_mb": -5, "used_mb": "x", "scope": ""},
            "cache": "not a store",
            "r" + L: {"path": "/r"},
            "s5": {}, "s6": {}, "s7": {}, "s8": {}, "s9": {"path": "/past the cap"}},
        "tunnel": {"kind": "wireguard-1", "addr": "10.0.0.2", "up": 1},
        "toolchain_versions": {"jdk": "21.0.2", "k" + L: "v" + L, "n": 5, **{f"t{i}": "1" for i in range(40)}},
        "toolchain_verified": {"jdk": {"algo": "sha256", "where": "https://example.com/" + L}, "md": {"algo": "md5"},
                               "s": "not a dict", "g": {"algo": "gpg", "where": None}, "n" + L: {"algo": "none"},
                               **{f"w{i}": {"algo": "md5"} for i in range(75)}, "late": {"algo": "sha1"}},
        "toolchain_receipts": {"jdk": {"commit": "abc;X" + "0" * 70, "tree": "a" * 64, "files": "12", "bytes": -5, "at": 5,
                                       "before": "b" * 64, "net": "cut"},
                               "short": {"tree": "a" * 63}, "s": "not a dict", "words": {"tree": "c" * 64, "files": "x"},
                               "listed": {"tree": "c" * 64, "bytes": [1]},
                               "k" + L: {"tree": "e" * 64, "before": "not hex", "net": "open"},
                               **{f"w{i}": {"tree": "no"} for i in range(74)}, "late": {"tree": "f" * 64}},
        "tokseal": {"E": "ab12", "sealed": {
            "u_0123abcd": {"claude": {"R": "ff00", "K": "zz12ab" + "0" * 30, "email": "e" + L, "plan": "p" + L},
                           "codex": {"R": "XYZ"}, "gemini": {"R": "aa"}, "x": "y"},
            "u_bad": {"claude": {"R": "aa"}},
            "u_89abcdef": "not a dict",
            "u_fedcba98": {"codex": {"R": "1", "K": None}},
            **{f"x{i}": {} for i in range(496)},
            "u_11111111": {"claude": {"R": "aa"}}}},
        "store_dirs": {"top": ["a" + L, "b"] + ["c"] * 70, "android": ["platforms", "system-images"], "incomplete": None,
                       "roots": "ab",
                       "versions": {"platforms": ["android-34", "android-35"], "p" + L: ["x"], "bad": "not a list",
                                    **{f"v{i}": [] for i in range(8)}}},
        "images": [{"id": "system-images;android-34;google_apis;x86_64<script>", "api": "34", "kind": "google_apis",
                    "abi": "x86_64", "avds": ["Pixel_" + L, "b"]},
                   {"id": "not-an-image"}, "not a dict", {"id": "system-images;" + L, "avds": None}]
        + [{"id": "x"}] * 60 + [{"id": "system-images;late"}],
        "toolchains": {"jdk": "/opt/jdk", "none": "", "z": 0, "l" + L: "v" + L, **{f"t{i}": "x" for i in range(14)}},
        "docker_ip": "127.0.0.1" + L,
        "docker_gid": 998,
        "internet": True,
        "store_ro": True,
        "store_noexec": 1,
        "features": {"vmhost": {"installed": True, "kvm": 1, "libvirt": "10.0.0-ubuntu", "nokvm": "kernel", "virtiofs": True},
                     "firewall": {"installed": True},
                     "iommu": {"installed": True, "on": False},
                     "storage": {"installed": True, "zfs": True, "mergerfs": "yes", "snapraid": False, "smart": True},
                     "shares": {"installed": True, "smb": True, "nfs": True},
                     "ups": {"installed": True, "nut": True},
                     "gpuvm": {"installed": True, "bound": True, "cards": "2", "ids": "10de:2204,10de:1aef;rm"}},
        "disks": [{"name": "sda", "model": "WD <b>Red</b> " + L, "serial": "X1", "size_mb": 1000, "ssd": True, "tran": "sata",
                   "removable": False, "by_id": "ata-WD;x", "system": True, "holds": "ZFS pool tank",
                   "parts": [{"name": "sda1", "size_mb": 9, "holds": "tank"}, "x", {"name": "sda2", "size_mb": "9"}],
                   "smart": {"health": "ok", "temp_c": 40, "hours": 12}},
                  {"name": "sdb", "smart": {"health": "meh", "temp_c": "40"}, "size_mb": "5"},
                  {"name": "bad name"}, "junk"] + [{"name": "bad name"}] * 28 + [{"name": "sdz"}],
        "shares": [{"name": "media", "path": "/mnt/pool/media<" + L,
                    "smb": {"on": True, "guest": True, "ro": False, "tm": True, "users": ["alice", 5, "b<o>b"], "readers": ["carol"]},
                    "nfs": {"on": True, "ro": True, "clients": ["10.0.0.0/24(rw)", 7]}},
                   {"name": "-bad"}, {"name": "Two Words", "smb": "x", "nfs": None}, "junk"]
        + [{"name": "-bad"}] * 60 + [{"name": "late"}],
        "pools": [{"name": "tank", "size_mb": 1000, "alloc_mb": "5", "free_mb": 995, "health": "ONLINE<", "mount": "/tank",
                   "encrypted": True, "locked": False, "scrub": "scrub repaired 0B " + L, "errors": "No known data errors",
                   "vdevs": [{"type": "mirror", "state": "ONLINE", "disks": [{"id": "ata-1", "state": "ONLINE"}, "x"]}, "y"]},
                  {"name": "Bad"}, "junk"] + [{"name": "Bad"}] * 29 + [{"name": "late"}],
        "pools_importable": [{"name": "old", "id": "1234567890123456789012345678", "state": "ONLINE!", "said": "x" + L},
                             {"name": "o2", "id": "abc"}, {"name": "Bad"}, "x"] + [{"name": "Bad"}] * 12 + [{"name": "late"}],
        "snapshots": {"tank": {"count": 5, "used_mb": 10, "kinds": {"hourly": 3, "daily": "2"},
                               "newest": [{"name": "bb-hourly-20261117-1200", "at": 5}, {"name": "other"}, "x",
                                          {"name": "bb-manual-20261117-1201", "at": "5"}]},
                      "Bad": {}, "data": "not a dict", "p2": {"kinds": "x"}, **{f"z{i}": "x" for i in range(28)}, "late": {}},
        "array": {"data": [{"slot": 1, "id": "ata-a", "fs": "xfs", "size_mb": 100, "used_mb": 50, "mounted": True}, {"slot": 0},
                           {"slot": True}, "x", {"slot": 100}, {"slot": 2, "id": "b" + L}],
                  "parity": [{"slot": 1, "id": "ata-p"}, {"slot": 2}, {"slot": 3}],
                  "policy": "mfs<b>", "mount": "/mnt/array", "mounted": True, "last_sync": 5, "last_scrub": "x", "last_check": True,
                  "status": "ok " + L, "running": "sync", "progress": "50%", "adopted": True, "last_move": 7,
                  "moves": [{"share": "media", "land": "disk1", "from": "disk2", "to": "disk3"}, "x"],
                  "verify": {"at": 5, "found": 1, "fixed": 1, "unfixed": 0, "ok": True, "corrected": False}},
        "console": {"os": True, "set": 1, "open": True},
        "adopted": {"from": "pool<", "writable": True, "taken": False, "at": 5,
                    "mounts": [{"where": "/mnt/disk1", "fs": "xfs", "ro": True, "mounted": True}, "x"],
                    "merged": {"/mnt/user": True, "/mnt/user0": 1},
                    "parity": ["sdb", "sdc", "sdd"],
                    "folders": ["media", "-bad", 5, "Two Words"],
                    "apps": {"docker": {"autostart": ["plex", "sonarr<"], "digests": {"plex": "sha256:abc;rm"}},
                             "vms": [{"name": "win", "autostart": True, "nvram": True}, "x"],
                             "said": ["a" + L], "at": 5}},
        "timezone": "America/New_York;rm",
        "store_backups": [{"id": "b_1!", "name": "nightly", "last_at": 5, "ok": True, "error": "", "size_mb": -1, "runs": 3,
                           "took_s": True}, {"name": "Bad"}, "x"],
        "ext_mounts": [{"id": "m1", "name": "usb-disk", "kind": "usbdisk", "mounted": True, "present": True, "size_mb": 5,
                        "used_mb": "5", "error": "e<"}, {"name": "Bad"}],
        "ups": {"model": "APC <Back-UPS>", "status": "OL chrg", "words": "on line, Charging", "answers": True, "charge": 100,
                "runtime_s": 10 ** 8, "load": True},
        "host_updates": {"pending": 5, "security": -1, "checked": True, "reboot": True},
        "spindown": 30,
        "os_image": {"version": "0.9.1+x;rm", "snapshot": "20261117T1200Z", "built": "2026-11-17T12:00Z", "slot": "a", "next": "c",
                     "trial": True, "fell_back": "fell back <x>"},
        "os_kept": {"booted": "0.9.0;x", "versions": [{"version": "0.9.0", "mb": 2048, "at": 5, "state": True, "evil": 1},
                                                      {"version": ""}, "no", {"version": "0.8", "mb": -1, "at": True}]},
        "os_stick": {"stick": True, "pool": "/mnt/sys", "ready": True, "on_stick": ["docker", "evil", "projects"], "written_kb": 5,
                     "boot_written_kb": -1, "projects": "/mnt/proj", "projects_bound": True, "projects_home": "pool",
                     "others": ["/a", "b", 5], "var_total_mb": 100, "var_free_mb": True},
        "vms_other": [{"name": "win10", "state": "running!", "vcpus": 2, "mem_mb": "x", "autostart": True}, {"name": "-bad"}, "x"],
        "vms": [{"name": "bbvm-dev", "state": "running", "ip": "10.0.0.9", "vcpus": 2, "mem_mb": 2048,
                 "snapshots": ["s1", "-bad", "s" * 50], "screen": True, "autostart": True,
                 "hw": {"cpuset": [0, 1, "x"], "net": "br:br0", "model": "virtio", "mac": "52:54:00:AA:BB:CC", "mem_max_mb": 4096,
                        "share": {"path": "/workspace/p", "tag": "p!", "ro": True}, "tpm": True,
                        "devices": [{"type": "pci", "addr": "0000:01:00.0"}, {"type": "usb", "vendor": "0x1234", "product": "0x5678"},
                                    {"type": "x"}]},
                 "usb": [{"vendor": "0x1234", "product": "0x5678", "serial": "S;1", "port": "1-2.3", "name": "Key<board>"},
                         {"vendor": "bad"}],
                 "guest": {"hostname": "dev", "os": "Ubuntu", "kernel": "6.8", "ips": ["10.0.0.9", "zz"], "users": 1,
                           "fs": [["/", 5, 10], ["/x", -1, 2]]},
                 "iso": "ubuntu-24.04.iso"},
                {"name": "bbvm-x", "ip": "bad", "iso": "../evil", "hw": "not a dict", "guest": "not a dict"}, {"name": "notbb"}, "x"],
        "vm_pool": {"free_mb": 5, "total_mb": "10"},
        "vm_host": {"cpus": [[0, 1, "x", 3, 4], "not a list"],
                    "usb": [{"vendor": "0x1234", "product": "0x5678", "name": "Key", "serial": "S1", "port": "1-2", "bus": 3,
                             "speed": "480M", "driver": "usbhid;x", "ctl": "0000:00:14.0", "use": ["keyboard", 5]},
                            {"bus": 5000, "ctl": "bad", "port": "bad"}, "x"],
                    "pci": [{"addr": "0000:01:00.0", "class": "0x030000", "vendor": "0x10de", "device": "0x2204", "group": "12a",
                             "driver": "nvidia", "host": "the display"}, {"addr": "bad"}],
                    "iommu": True,
                    "bridges": ["br0", "docker0", "br-0123456789ab", "bbvm-x", "-bad"],
                    "vnets": ["default", "-bad"],
                    "tpm": True},
        "vm_isos": [{"name": "ubuntu.iso", "mb": 5}, {"name": "x.iso", "mb": "5"}, {"name": "../x.iso"}],
        "sandbox": "yes",
        "release_key": "ABCDEF0123456789abcdef0123456789;x", "release_spare": "f" * 40, "unsigned_ok": True, "root_off": 1,
        "gpu_card": "10de:2204 " + L, "gpu_display": "active", "gpu_amd": "",
        "gpu_driver": {"installed": "550.1;rm", "loaded": "550.1", "bound": "nvidia", "package": "nvidia-driver-550",
                       "pkg_version": "550", "candidate": "560", "recommended": "nvidia-driver-560-open",
                       "options": [{"pkg": "nvidia-driver-560-open", "version": "560.35" + L, "open": 1}, {"pkg": "evil"}, "x"]},
        "gpu_container": {"installed": "1.16", "candidate": "1.17", "runtime": 1},
        "sound": {"cards": ["HDA Intel<", "USB"], "virtual": ["Loopback"], "server": "pipewire"},
        "administers": 0,
        "isolation": {"sessions": 1, "why": "w" + L},
        "session_net": {"can": True, "why": "", "wanted": True, "active": 1, "sessions": "3", "error": "e" + L,
                        "ctr": {"wanted": True, "can": True, "why": "", "active": True, "error": "", "bridges": "x"}},
        "sysdeps": {"family": "debian!", "unmet": {"jdk:21": ["libfoo", "", "lib+x;rm"], "empty": [], "bad": "x"}},
        "storage": {"at": 5, "took_s": 2,
                    "filesystems": [{"path": "/", "source": "/dev/sda1", "type": "ext4", "ro": False, "total_mb": 10, "free_mb": "x",
                                     "used_mb": None, "also": ["/a"]}, "x"],
                    "stores": {"data": {"path": "/d", "fs": "/", "used_mb": 5, "slow": True}, "x": "not a dict"},
                    "projects": {"p1": {"data": 5, "cache": "x"}, "p2": "not a dict"},
                    "workspace": {"path": "/workspace", "fs": "/"},
                    "homes": {"path": "/home", "mb": 5, "fs": "/"},
                    "docker": {"kinds": [{"kind": "images", "count": 3, "mb": 100, "reclaimable_mb": None}, "x"],
                               "root": "/var/lib/docker", "fs": "/"},
                    "slow": ["/mnt/slow"],
                    "phones": [{"project": "p1", "uid": "u1", "name": "Pixel", "mb": 5, "running": True, "ran": None, "snap_mb": 3},
                               "x"]},
        "mounts": [{"path": "/mnt/a", "source": "nas:/a", "type": "nfs", "ro": True, "mounted": True, "real": "/mnt/a",
                    "stale": False, "error": "e"}, {"path": "relative"}, "x"],
        "door": {"kind": "tailscale", "host": "Node.Example.TS.net;x", "installed": True, "active": 1},
        "services": {"runners": [{"installed": True, "active": True, "busy": False, "name": "r1", "url": "https://github.com/x",
                                  "slot": "s1;x", "forge": "github!", "unit": "actions.runner@x", "labels": ["self-hosted", "", "x;y"]},
                                 "x"],
                     "tailscale": {"installed": True, "dns": "node.ts.net;x", "funnel": {"443": 8080, "8443": "x", "10000000": None}}},
        "files": {"port": 7684},
        "relay": {"tls": "sha256:" + "a" * 64, "once": True},
        "session": {"up": True, "screen": 7684, "ctr": True, "ctr_why": "", "term": True, "user": "bb;x", "workspace": True,
                    "writable": False, "claude": "2.0.1", "codex": "0.5", "copilot": "1.0", "grok": "0.1", "opencode": "0.2",
                    "bundle": "b1", "why": "", "boot": "123.456x",
                    "accounts": {"users": 3, "moved": 2, "waiting": 1, "error": "e"}, "up_s": 12.7},
        "network": {"interface": "eth0", "addresses": ["10.0.0.5/24"], "gateway": "10.0.0.1", "dns": ["1.1.1.1"],
                    "routes": [{"to": "10.1.0.0/24", "via": "10.0.0.2"}, "x"]},
        "distro": {"id": "ubuntu", "family": "debian", "pretty": "Ubuntu 24.04<", "pkg": "apt", "network": "netplan"},
        "evil": {"a": 1},
    }


def rich_alt():
    """The other side of the branches the rich census takes: fields left
    out, a driver kept without a card, an array without its moves, a stick
    that is not one, an infinite uptime."""
    return {
        "cpu": "x", "mem_mb": [1], "machine": "XYZ", "system": None, "arch": 5, "sshd": [],
        "stores": [], "tunnel": {"addr": "not.an.addr"}, "toolchain_versions": [],
        "tokseal": {"E": "not hex", "sealed": {}},
        "toolchain_verified": "x",
        "toolchain_receipts": [],
        "store_dirs": {"top": ["a"]},
        "images": "not a list",
        "toolchains": None,
        "docker_ip": None, "docker_gid": 2 ** 31, "internet": "yes", "store_ro": 1, "store_noexec": True,
        "features": {"vmhost": {"virtiofs": 1, "nokvm": "other"}, "ups": "x", "gpuvm": {"cards": "x"}},
        "disks": "x", "shares": {}, "pools": None, "pools_importable": "x", "snapshots": [],
        "array": {"data": [{"slot": 1}], "moves": "x", "verify": {}},
        "console": {},
        "adopted": {"from": "x", "merged": "x", "apps": {"at": True}},
        "timezone": 5, "store_backups": {}, "ext_mounts": None,
        "ups": {"charge": 5}, "host_updates": {"pending": "x"},
        "spindown": 7,
        "os_image": {"version": ""},
        "os_kept": {"booted": "0.9.0"},
        "os_stick": {"stick": 1},
        "vms_other": "x", "vms": {}, "vm_pool": {}, "vm_host": {"usb": None}, "vm_isos": None,
        "sandbox": 0,
        "release_key": None, "release_spare": 5, "unsigned_ok": 1, "root_off": True,
        "gpu_card": "", "gpu_display": None, "gpu_amd": "Radeon",
        "gpu_driver": {"installed": "550", "nocard": True, "options": None},
        "gpu_container": {"installed": "1.16", "nocard": 1},
        "sound": {"cards": None, "server": "alsa"},
        "administers": True,
        "isolation": "x",
        "session_net": {"can": 1, "ctr": {}},
        "sysdeps": [],
        "storage": {"at": 0},
        "mounts": {},
        "door": {"kind": "ssh"},
        "services": {"runners": "x", "tailscale": {"funnel": "x"}},
        "files": {"port": "x"},
        "relay": {"tls": "sha256:short", "once": 1},
        "session": {"up": 1, "up_s": float("inf"), "accounts": "x"},
        "network": [],
        "distro": "x",
    }


# One of each JSON type, and the empty ones, each put under every key on
# its own and under all of them at once.
WRONG = (None, False, True, 0, 7, -1, 2.5, "", "text", [], ["x", 1], {}, {"x": 1})
NOT_A_DICT = (None, [], "census", 5, True, [{"cpu": 4}])


def keys_of_rich():
    return [k for k in rich() if k != "evil"]


def answer(c):
    """_census's answer, or the kind of exception it raised: a census that
    raises is a hello refused, and the table must refuse the same ones."""
    try:
        with contextlib.redirect_stderr(io.StringIO()):
            return nodes._census(c)
    except Exception as e:  # noqa: BLE001 (the exception is the answer)
        return {"raises": type(e).__name__}


def delta(out, base):
    """What `out` changed from `base`, as JSON says it, so True and 1 are
    not one value; the fields it left out under "gone"."""
    if "raises" in out:
        return out
    d = {"set": {k: v for k, v in out.items() if k not in base or json.dumps(v) != json.dumps(base[k])},
         "gone": [k for k in base if k not in out]}
    return d if d["set"] or d["gone"] else None


def matrix():
    """Every variant against the empty census's answer, kept where it differs."""
    base = answer({})
    cases = {}
    for i, v in enumerate(NOT_A_DICT):
        cases[f"not a dict {i}"] = v
    for k in keys_of_rich():
        for i, v in enumerate(WRONG):
            cases[f"{k} {i}"] = {k: v}
    for i, v in enumerate(WRONG):
        cases[f"all {i}"] = {k: v for k in keys_of_rich()}
    got = {}
    for name, c in cases.items():
        d = delta(answer(c), base)
        if d is not None:
            got[name] = d
    return got


def deep():
    """The rich census with each of a field's own keys (the first entry's,
    for a list) put to each wrong value in turn, up to 24 keys a field: a
    digest of every answer per field, and the variants that raise, by key
    and the wrong value's place in WRONG. Without the sealed accounts past
    the cap, which only the rich case needs and which slow every call."""
    def light():
        c = rich()
        c["tokseal"]["sealed"] = {a: s for a, s in c["tokseal"]["sealed"].items() if a.startswith("u_")}
        return c
    got = {}
    for k, v in light().items():
        c = light()
        if isinstance(v, dict):
            at = c[k]
        elif isinstance(v, list) and v and isinstance(v[0], dict):
            at = c[k][0]
        else:
            continue
        h, raises = hashlib.sha256(), []
        for s in list(at)[:24]:
            was = at[s]
            for i, w in enumerate(WRONG):
                at[s] = w
                a = answer(c)
                h.update(json.dumps(a).encode())
                if "raises" in a:
                    raises.append(f"{s} {i} {a['raises']}")
            at[s] = was
        got[k] = {"answers": h.hexdigest()[:16], "raises": raises}
    return got


def frozen():
    """The frozen block at the end of this file, as this checkout's _census
    answers it."""
    parts = {"FROZEN_RICH": text(answer(rich())), "FROZEN_ALT": text(answer(rich_alt())),
             "FROZEN_EMPTY": text(answer({})), "FROZEN_MATRIX": text(matrix()), "FROZEN_DEEP": text(deep())}
    return "\n".join(f"{name} = r'''{v}'''\n" for name, v in parts.items())


def text(v):
    """JSON with one line per top-level key, so a failure's diff names the
    field (or the case) that moved."""
    if not isinstance(v, dict) or not v:
        return json.dumps(v)
    return "{\n" + ",\n".join(f" {json.dumps(k)}: {json.dumps(x)}" for k, x in v.items()) + "\n}"


class Frozen(unittest.TestCase):
    """The table answers what the long function answered, key order and all."""

    maxDiff = None

    def test_the_rich_census(self):
        self.assertEqual(text(answer(rich())), FROZEN_RICH)

    def test_the_other_branches(self):
        self.assertEqual(text(answer(rich_alt())), FROZEN_ALT)

    def test_the_empty_census(self):
        self.assertEqual(text(answer({})), FROZEN_EMPTY)

    def test_every_wrong_type_under_every_key(self):
        self.assertEqual(text(matrix()), FROZEN_MATRIX)

    def test_every_wrong_type_under_each_fields_own_keys(self):
        # Those that raise are a hello refused (a nested list that is a
        # number); kept as they were, since this is the table and not a fix.
        self.assertEqual(text(deep()), FROZEN_DEEP)


class RecordingDict(dict):
    """A census that notes which of its keys were asked for."""

    def __init__(self, *a, **kw):
        super().__init__(*a, **kw)
        self.asked = set()

    def get(self, k, default=None):
        self.asked.add(k)
        return super().get(k, default)

    def __getitem__(self, k):
        self.asked.add(k)
        return super().__getitem__(k)

    def __contains__(self, k):
        self.asked.add(k)
        return super().__contains__(k)


class Table(unittest.TestCase):
    def test_each_row_names_the_keys_its_cleaner_reads(self):
        # A row that reads a key it does not name would let that key be
        # said as unknown while it is kept; one that names a key it does
        # not read would hide a key that is dropped.
        for keys, clean in nodes.CENSUS:
            asked = set()
            for sample in (rich(), rich_alt(), {}):
                c = RecordingDict(sample)
                with contextlib.suppress(Exception):
                    clean(c, {})
                asked |= c.asked
            self.assertEqual(asked, set(keys), f"{clean.__name__} reads {sorted(asked)}, its row names {sorted(keys)}")

    def test_the_table_reads_every_key_the_rich_census_has(self):
        self.assertEqual(sorted(nodes.CENSUS_KEYS), sorted(keys_of_rich()),
                         "a new row's field goes into rich() and rich_alt(), and the frozen answers are made again")
        self.assertEqual(nodes.census_unknown(rich()), ["evil"])
        self.assertEqual(nodes.census_unknown({}), [])
        self.assertEqual(nodes.census_unknown(["cpu"]), [])

    def test_an_unknown_key_is_said_once_per_process(self):
        err = io.StringIO()
        with mock.patch.object(nodes, "_census_said", set()), contextlib.redirect_stderr(err):
            nodes._census({"cpu": 2, "foo": 1})
            nodes._census({"foo": 2, "bar": "x"})
            nodes._census({"foo": 3})
        self.assertEqual(err.getvalue().splitlines(), [
            "[nodes] a node's census carries \"foo\", which the controller does not keep: add it to nodes.CENSUS",
            "[nodes] a node's census carries \"bar\", which the controller does not keep: add it to nodes.CENSUS"])

    def test_what_is_said_is_bounded(self):
        # The keys come from a machine that could be lying: fresh ones on
        # every hello grow neither the set nor the log without end.
        err = io.StringIO()
        with mock.patch.object(nodes, "_census_said", set()), contextlib.redirect_stderr(err):
            nodes._census({"x" * 300: 1, "line\nbreak": 1})
            nodes._census({f"k{i}": 1 for i in range(nodes.CENSUS_SAID_MOST + 10)})
            self.assertEqual(len(nodes._census_said), nodes.CENSUS_SAID_MOST)
        lines = err.getvalue().splitlines()
        self.assertEqual(len(lines), nodes.CENSUS_SAID_MOST)
        self.assertIn(' "' + "x" * 80 + '", ', lines[0], "a long key is cut")
        self.assertIn(' "line\\nbreak", ', lines[1], "a key is one line however it is written")


# ---- the agent's side ----

@functools.cache
def _parse(name):
    with open(os.path.join(AGENT, name), encoding="utf-8") as f:
        return ast.parse(f.read(), name)


def _literal_keys(node, where):
    """The constant keys of a dict literal, through its ** spreads of dict
    literals (a conditional one's both sides). Anything else is refused,
    so a census assembled some other way fails here rather than reading as
    a census with fewer keys."""
    if isinstance(node, ast.IfExp):
        return _literal_keys(node.body, where) | _literal_keys(node.orelse, where)
    if not isinstance(node, ast.Dict):
        raise AssertionError(f"{where}: a census key comes from {ast.unparse(node)[:80]}, which this test cannot read")
    keys = set()
    for k, v in zip(node.keys, node.values, strict=True):
        if k is None:
            keys |= _literal_keys(v, where)
        elif isinstance(k, ast.Constant) and isinstance(k.value, str):
            keys.add(k.value)
        else:
            raise AssertionError(f"{where}: a census key is computed ({ast.unparse(k)[:80]}), which this test cannot read")
    return keys


FUNCS = (ast.FunctionDef, ast.AsyncFunctionDef, ast.Lambda)


def _functions(tree):
    return {n.name: n for n in ast.walk(tree) if isinstance(n, FUNCS[:2])}


def _own(fn):
    """The nodes of a function's own body, not those of a function inside it."""
    todo = list(ast.iter_child_nodes(fn))
    while todo:
        n = todo.pop()
        yield n
        if not isinstance(n, FUNCS):
            todo.extend(ast.iter_child_nodes(n))


def census_literal():
    """The keys of the dict census.census returns, its one return."""
    fn = _functions(_parse("census.py"))["census"]
    rets = [n for n in _own(fn) if isinstance(n, ast.Return)]
    assert len(rets) == 1, "census.census returns in one place"
    return _literal_keys(rets[0].value, "census.census")


def _sends():
    """Each place the agent hands the controller a census: a .call("hello"
    or "enroll", {...}) whose dict has "census", anywhere in the package,
    with the function it is in."""
    for name in sorted(os.listdir(AGENT)):
        if not name.endswith(".py"):
            continue
        tree = _parse(name)
        owner = {}
        for fn in ast.walk(tree):
            if isinstance(fn, FUNCS[:2]):
                owner.update((n, fn) for n in _own(fn))
        for call in ast.walk(tree):
            if not (isinstance(call, ast.Call) and isinstance(call.func, ast.Attribute) and call.func.attr == "call"
                    and len(call.args) >= 2 and isinstance(call.args[0], ast.Constant)
                    and call.args[0].value in ("hello", "enroll")):
                continue
            assert isinstance(call.args[1], ast.Dict), f"{name}:{call.lineno} says {call.args[0].value} with a body this test cannot read"
            for k, v in zip(call.args[1].keys, call.args[1].values, strict=True):
                if isinstance(k, ast.Constant) and k.value == "census":
                    assert call in owner, f"{name}:{call.lineno} sends a census outside a function: follow it here"
                    yield name, owner[call], v


def _methods():
    out = {}
    for name in sorted(os.listdir(AGENT)):
        if name.endswith(".py"):
            out.update(_functions(_parse(name)))
    return out


def _from_census(expr, fn, methods, seen=()):
    """Whether `expr` is census.census's answer: a call of census(), a
    method whose every return is one, a name assigned one, or a branch of
    either. A function's parameter (hello's `taken`) is its caller's to
    say and passes here."""
    if isinstance(expr, ast.IfExp):
        return _from_census(expr.body, fn, methods, seen) and _from_census(expr.orelse, fn, methods, seen)
    if isinstance(expr, ast.Call):
        f = expr.func
        if isinstance(f, ast.Name) and f.id == "census":
            return True
        if isinstance(f, ast.Attribute) and f.attr in methods and f.attr not in seen:
            m = methods[f.attr]
            rets = [r.value for r in _own(m) if isinstance(r, ast.Return) and r.value is not None]
            return bool(rets) and all(_from_census(r, m, methods, seen + (f.attr,)) for r in rets)
        return False
    if isinstance(expr, ast.Name):
        if expr.id in {a.arg for a in fn.args.args + fn.args.kwonlyargs}:
            return True
        sets = [n.value for n in _own(fn) if isinstance(n, ast.Assign)
                and any(isinstance(t, ast.Name) and t.id == expr.id for t in n.targets)]
        return bool(sets) and all(_from_census(v, fn, methods, seen) for v in sets)
    return False


def _added(expr, fn, where):
    """The keys a send site puts into the census it was handed, on the name
    it sends: c["k"] = ..., c |= {...}, c.update({...}), c.setdefault("k")."""
    if not isinstance(expr, ast.Name):
        return set()

    def key(k):
        if not (isinstance(k, ast.Constant) and isinstance(k.value, str)):
            raise AssertionError(f"{where}: a census key is computed ({ast.unparse(k)[:80]})")
        return k.value
    keys = set()
    for n in _own(fn):
        if isinstance(n, (ast.Assign, ast.AugAssign)):
            for t in (n.targets if isinstance(n, ast.Assign) else [n.target]):
                if isinstance(t, ast.Subscript) and isinstance(t.value, ast.Name) and t.value.id == expr.id:
                    keys.add(key(t.slice))
            if isinstance(n, ast.AugAssign) and isinstance(n.target, ast.Name) and n.target.id == expr.id:
                keys |= _literal_keys(n.value, where)
        if isinstance(n, ast.Call) and isinstance(n.func, ast.Attribute) and n.func.attr in ("update", "setdefault") \
                and isinstance(n.func.value, ast.Name) and n.func.value.id == expr.id:
            keys |= {key(n.args[0])} if n.func.attr == "setdefault" else _literal_keys(n.args[0], where)
    return keys


@functools.cache
def agent_census_keys():
    """Every top-level key the agent can put in the census it sends: what
    census.census returns, and what each send site adds to it."""
    methods = _methods()
    keys = census_literal()
    sites = 0
    for name, fn, expr in _sends():
        where = f"{name} {fn.name}"
        assert _from_census(expr, fn, methods), f"{where} sends a census that is not census.census's: follow it here"
        keys |= _added(expr, fn, where)
        sites += 1
    assert sites >= 3, f"found {sites} places the agent sends a census; enroll, status and the loop's hello were three"
    return frozenset(keys)


# Keys the agent sends that the controller leaves out on purpose, each with
# why. Empty: the controller keeps every key the agent sends.
CONTROLLER_LEAVES = {}


class AgentAndController(unittest.TestCase):
    def test_every_key_the_agent_sends_is_one_the_controller_reads(self):
        sent = agent_census_keys()
        self.assertGreater(len(sent), 50, "the census literal was read")
        dropped = sorted(sent - nodes.CENSUS_KEYS - set(CONTROLLER_LEAVES))
        self.assertEqual(dropped, [], "the agent sends these and nodes.CENSUS does not read them: add a row, "
                                      "or say in CONTROLLER_LEAVES why the controller leaves them")

    def test_the_allowlist_holds_only_what_is_sent_and_dropped(self):
        sent = agent_census_keys()
        for k in CONTROLLER_LEAVES:
            self.assertIn(k, sent, f"{k} is no longer sent: take it off CONTROLLER_LEAVES")
            self.assertNotIn(k, nodes.CENSUS_KEYS, f"{k} is read now: take it off CONTROLLER_LEAVES")

    def test_the_hello_adds_its_token_seals(self):
        # The one key a send site adds to census.census's answer; found, so
        # the extraction follows the census past the literal.
        self.assertIn("tokseal", agent_census_keys())
        self.assertNotIn("tokseal", census_literal())


# ---- frozen: what _census answered before it was a table ----
FROZEN_RICH = r'''{
 "cpu": 8,
 "mem_mb": 16384,
 "os": "linux x86_64 LLLLLLLLLLLLLLLLLLLLLLLLLLLLLLLLLLLLLLLLLLLLLLLLLLLLLLLLLLLLLLLLLLLLLLLLLLLLLLLLLLLLLLLLLLLLLLLLLLLLLLLLLLL",
 "docker": "27.3.1",
 "docker_id": "ABCD:EFGH",
 "hostname": "node-1",
 "git": "git version 2.43.0",
 "machine": "0123456789abcdef0123456789abcdef",
 "system": "linux",
 "arch": "x86_64rm",
 "sshd": true,
 "stores": {"toolchains": {"path": "/srv/tc/LLLLLLLLLLLLLLLLLLLLLLLLLLLLLLLLLLLLLLLLLLLLLLLLLLLLLLLLLLLLLLLLLLLLLLLLLLLLLLLLLLLLLLLLLLLLLLLLLLLLLLLLLLLLLLLLLLLLLLLLLLLLLLLLLLLLLLLLLLLLLLLLLLLLLLLLLLLLLLLLLLLLLLLLLLLLLLLLLLLLLLLLLLLLLLLL", "id": "id-LLLLLLLLLLLLLLLLLLLLLLLLLLLLLLLLLLLLLLLLLLLLLLLLLLLLLLLLLLLLL", "free_mb": 1000, "total_mb": 2000, "used_mb": null, "scope": "linux-x86_64rm-rf"}, "data": {"path": "/srv/data", "id": "abc", "free_mb": 0, "total_mb": 0, "used_mb": 0, "scope": ""}, "rLLLLLLLLLLLLLLLLLLL": {"path": "/r", "id": "", "free_mb": null, "total_mb": null, "used_mb": null, "scope": ""}, "s5": {"path": "", "id": "", "free_mb": null, "total_mb": null, "used_mb": null, "scope": ""}, "s6": {"path": "", "id": "", "free_mb": null, "total_mb": null, "used_mb": null, "scope": ""}, "s7": {"path": "", "id": "", "free_mb": null, "total_mb": null, "used_mb": null, "scope": ""}, "s8": {"path": "", "id": "", "free_mb": null, "total_mb": null, "used_mb": null, "scope": ""}},
 "tunnel": {"kind": "wireguard", "addr": "10.0.0.2", "up": true},
 "toolchain_versions": {"jdk": "21.0.2", "kLLLLLLLLLLLLLLLLLLLLLLLLLLLLLLLLLLLLLLL": "vLLLLLLLLLLLLLLLLLLLLLLLLLLLLLLLLLLLLLLL", "n": "5", "t0": "1", "t1": "1", "t2": "1", "t3": "1", "t4": "1", "t5": "1", "t6": "1", "t7": "1", "t8": "1", "t9": "1", "t10": "1", "t11": "1", "t12": "1", "t13": "1", "t14": "1", "t15": "1", "t16": "1", "t17": "1", "t18": "1", "t19": "1", "t20": "1", "t21": "1", "t22": "1", "t23": "1", "t24": "1", "t25": "1", "t26": "1", "t27": "1", "t28": "1", "t29": "1", "t30": "1", "t31": "1", "t32": "1", "t33": "1", "t34": "1", "t35": "1", "t36": "1"},
 "tokseal": {"E": "ab12", "sealed": {"u_0123abcd": {"claude": {"R": "ff00", "K": "12ab00000000000000000000", "email": "eLLLLLLLLLLLLLLLLLLLLLLLLLLLLLLLLLLLLLLLLLLLLLLLLLLLLLLLLLLLLLLLLLLLLLLLLLLLLLLLLLLLLLLLLLLLLLLLLLLLLLLLLLLLLLLLLLLLLLLL", "plan": "pLLLLLLLLLLLLLLLLLLLLLLLLLLLLLLLLLLLLLLL"}}, "u_fedcba98": {"codex": {"R": "1", "K": "", "email": "", "plan": ""}}}},
 "toolchain_verified": {"jdk": {"algo": "sha256", "where": "https://example.com/LLLLLLLLLLLLLLLLLLLLLLLLLLLLLLLLLLLLLLLLLLLLLLLLLLLLLLLLLLLLLLLLLLLLLLLLLLLLLLLLLLLLLLLLLLLLLLLLLLLLLLLLLLLLLLLLLLLLLLLLLLLLLLLLLLLLLLLLLLLLLLLLLLLLLLLLLLLLLLLLLLLLLLLLLLLLLLLLLLLL"}, "g": {"algo": "gpg", "where": ""}, "nLLLLLLLLLLLLLLLLLLLLLLLLLLLLLLLLLLLLLLL": {"algo": "none", "where": ""}},
 "toolchain_receipts": {"jdk": {"commit": "abc0000000000000000000000000000000000000000000000000000000000000", "tree": "aaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaa", "files": 12, "bytes": 0, "at": 5, "before": "bbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbb", "net": "cut"}, "kLLLLLLLLLLLLLLLLLLLLLLLLLLLLLLLLLLLLLLL": {"commit": "", "tree": "eeeeeeeeeeeeeeeeeeeeeeeeeeeeeeeeeeeeeeeeeeeeeeeeeeeeeeeeeeeeeeee", "files": 0, "bytes": 0, "at": 0, "before": "", "net": "open"}},
 "store_dirs": {"top": ["aLLLLLLLLLLLLLLLLLLLLLLLLLLLLLLLLLLLLLLLLLLLLLLLLLLLLLLLLLLL", "b", "c", "c", "c", "c", "c", "c", "c", "c", "c", "c", "c", "c", "c", "c", "c", "c", "c", "c", "c", "c", "c", "c", "c", "c", "c", "c", "c", "c", "c", "c", "c", "c", "c", "c", "c", "c", "c", "c", "c", "c", "c", "c", "c", "c", "c", "c", "c", "c", "c", "c", "c", "c", "c", "c", "c", "c", "c", "c", "c", "c", "c", "c"], "android": ["platforms", "system-images"], "incomplete": [], "roots": ["a", "b"], "versions": {"platforms": ["android-34", "android-35"], "pLLLLLLLLLLLLLLLLLLL": ["x"], "v0": [], "v1": [], "v2": [], "v3": [], "v4": []}},
 "images": [{"id": "system-images;android-34;google_apis;x86_64script", "api": "34", "kind": "google_apis", "abi": "x86_64", "avds": ["Pixel_LLLLLLLLLLLLLLLLLLLLLLLLLLLLLLLLLLLLLLLLLLLLLLLLLLLLLL", "b"]}, {"id": "system-images;LLLLLLLLLLLLLLLLLLLLLLLLLLLLLLLLLLLLLLLLLLLLLLLLLLLLLLLLLLLLLLLLLLLLLLLLLLLLLLLLLLLLLLLLLLLLLLLLLLLLLLLLLL", "api": "", "kind": "", "abi": "", "avds": []}],
 "toolchains": {"jdk": "/opt/jdk", "none": null, "z": null, "lLLLLLLLLLLLLLLLLLLLLLLLLLLLLL": "vLLLLLLLLLLLLLLLLLLLLLLLLLLLLLLLLLLLLLLL", "t0": "x", "t1": "x", "t2": "x", "t3": "x", "t4": "x", "t5": "x", "t6": "x", "t7": "x", "t8": "x", "t9": "x", "t10": "x", "t11": "x"},
 "docker_ip": "127.0.0.1LLLLLLLLLLLLLLLLLLLLLLLLLLLLLLL",
 "docker_gid": 998,
 "internet": true,
 "store_ro": true,
 "store_noexec": false,
 "features": {"vmhost": {"installed": true, "kvm": false, "libvirt": "10.0.0", "nokvm": "kernel", "virtiofs": true}, "firewall": {"installed": true}, "iommu": {"installed": true, "on": false}, "storage": {"installed": true, "zfs": true, "mergerfs": false, "snapraid": false, "smart": true}, "shares": {"installed": true, "smb": true, "nfs": true}, "ups": {"installed": true, "nut": true}, "gpuvm": {"installed": true, "bound": true, "cards": 2, "ids": "10de:2204,10de:1aef"}},
 "disks": [{"name": "sda", "model": "WD bRed/b LLLLLLLLLLLLLLLLLLLLLLLLLLLLLLLLLLLLLLLLLLLLLLLLLLLLLL", "serial": "X1", "size_mb": 1000, "ssd": true, "tran": "sata", "removable": false, "by_id": "ata-WDx", "system": true, "holds": "ZFS pool tank", "parts": [{"name": "sda1", "size_mb": 9, "holds": "tank"}, {"name": "sda2", "size_mb": 0, "holds": ""}], "smart": {"health": "ok", "temp_c": 40, "hours": 12}}, {"name": "sdb", "model": "", "serial": "", "size_mb": 0, "ssd": false, "tran": "", "removable": false, "by_id": "", "system": false, "holds": "", "parts": [], "smart": {}}],
 "shares": [{"name": "media", "path": "/mnt/pool/mediaLLLLLLLLLLLLLLLLLLLLLLLLLLLLLLLLLLLLLLLLLLLLLLLLLLLLLLLLLLLLLLLLLLLLLLLLLLLLLLLLLLLLLLLLLLLLLLLLLLLLLLLLLLLLLLLLLLLLLLLLLLLLLLLLLLLLLLLLLLLLLLLLLLLLLLLLLLLLLLLLLLLLLLLLLLLLLLLLLLLLLLLLL", "smb": {"on": true, "guest": true, "ro": false, "tm": true, "users": ["alice", "bob"], "readers": ["carol"]}, "nfs": {"on": true, "ro": true, "clients": ["10.0.0.0/24(rw)"]}}, {"name": "Two Words", "path": "", "smb": {"on": false, "guest": false, "ro": false, "tm": false, "users": [], "readers": []}, "nfs": {"on": false, "ro": false, "clients": []}}],
 "pools": [{"name": "tank", "size_mb": 1000, "alloc_mb": 0, "free_mb": 995, "health": "ONLINE", "mount": "/tank", "encrypted": true, "locked": false, "scrub": "scrub repaired 0B LLLLLLLLLLLLLLLLLLLLLLLLLLLLLLLLLLLLLLLLLLLLLLLLLLLLLLLLLLLLLLLLLLLLLLLLLLLLLLLLLLLLLLLLLLLLLLLLLLLLLLLLLLLLLLLLLLLLLLLLLLLLLLLLLLLLLLLLLLLLLL", "errors": "No known data errors", "vdevs": [{"type": "mirror", "state": "ONLINE", "disks": [{"id": "ata-1", "state": "ONLINE"}]}]}],
 "pools_importable": [{"name": "old", "id": "123456789012345678901234", "state": "ONLINE", "said": "xLLLLLLLLLLLLLLLLLLLLLLLLLLLLLLLLLLLLLLLLLLLLLLLLLLLLLLLLLLLLLLLLLLLLLLLLLLLLLLLLLLLLLLLLLLLLLLLLLLLLLLLLLLLLLLLLLLLLLLLLLLLLLLLLLLLLLLLLLLLLLLLLLLLLLLLLLLLLLLLLLLLLLLLLLLLLLLLLLLLLLLLLLLLLLLLLLLLLLLL"}, {"name": "o2", "id": "", "state": "", "said": ""}],
 "snapshots": {"tank": {"count": 5, "used_mb": 10, "kinds": {"hourly": 3, "daily": 0, "weekly": 0, "manual": 0}, "newest": [{"name": "bb-hourly-20261117-1200", "at": 5}, {"name": "bb-manual-20261117-1201", "at": 0}]}, "p2": {"count": 0, "used_mb": 0, "kinds": {"hourly": 0, "daily": 0, "weekly": 0, "manual": 0}, "newest": []}},
 "array": {"policy": "mfsb", "mount": "/mnt/array", "mounted": true, "data": [{"slot": 1, "id": "ata-a", "fs": "xfs", "size_mb": 100, "used_mb": 50, "mounted": true}, {"slot": 2, "id": "bLLLLLLLLLLLLLLLLLLLLLLLLLLLLLLLLLLLLLLLLLLLLLLLLLLLLLLLLLLLLLLLLLLLLLLLLLLLLLLLLLLLLLLLLLLLLLLLLLLLLLLLLLLLLLLLLLLLLLLL", "fs": "", "size_mb": 0, "used_mb": 0, "mounted": false}], "parity": [{"slot": 1, "id": "ata-p", "fs": "", "size_mb": 0, "used_mb": 0, "mounted": false}, {"slot": 2, "id": "", "fs": "", "size_mb": 0, "used_mb": 0, "mounted": false}], "last_sync": 5, "last_scrub": 0, "last_check": 0, "status": "ok LLLLLLLLLLLLLLLLLLLLLLLLLLLLLLLLLLLLLLLLLLLLLLLLLLLLLLLLLLLLLLLLLLLLLLLLLLLLLLLLLLLLLLLLLLLLLLLLLLLLLLLLLLLLLLLLLLLLLLLLLLLLLLLLLLLLLLLLLLLLLLLLLLLLLLLLLLLLLLLLLLLLLLLLLLLLLLLLLLLLLLLLLLLLLLLLLLLLLLLLLLLLLLLLLLLLLLLLLLLLLLLLLLLLLLLLLLLLLLLLLLLLLLLLLLLLLLLLLLLLLLLLLLLLLLLLLLLLLLLLLLLLLLLLLLLLLLLLLLLLLLLLLLLLLLLLLLLLLLLLLLLLLLLLLLLLLLLLLLLLLLLLLLLLLLLLLLLLLLLLLLLLLLLLLLLLLLLLLLLLLLLLLLLLLLLLLLLLL", "running": "sync", "progress": "50%", "adopted": true, "last_move": 7, "moves": [{"share": "media", "land": "disk1", "from": "disk2", "to": "disk3"}], "verify": {"at": 5, "found": 1, "fixed": 1, "unfixed": 0, "ok": true, "corrected": false}},
 "console": {"os": true, "set": false, "open": true},
 "adopted": {"from": "pool", "writable": true, "taken": false, "at": 5, "mounts": [{"where": "/mnt/disk1", "fs": "xfs", "ro": true, "mounted": true}], "merged": {"/mnt/user": true, "/mnt/user0": false}, "parity": ["sdb", "sdc"], "folders": ["media", "Two Words"], "apps": {"docker": {"autostart": ["plex", "sonarr"], "digests": {"plex": "sha256:abcrm"}}, "vms": [{"name": "win", "autostart": true, "nvram": true}], "said": ["aLLLLLLLLLLLLLLLLLLLLLLLLLLLLLLLLLLLLLLLLLLLLLLLLLLLLLLLLLLLLLLLLLLLLLLLLLLLLLLLLLLLLLLLLLLLLLLLLLLLLLLLLLLLLLLLLLLLLLLLLLLLLLLLLLLLLLLLLLLLLLLLLLLLLLLLLLLLLLLLLLLLLLLLLLLLLLLLLLLLLLLLLLLLLLLLLLLLLLLLLLLLLLLLLLLLLLLLLLLLLLLLLLLLLLLLLLLLLLLLLLLLLLLLLLLLLLLLLLLLLLLLLLLLLLLLLLLLLLLLLLLLLLLLLLLLLLLLLLLL"], "at": 5}},
 "timezone": "America/New_Yorkrm",
 "store_backups": [{"id": "b_1", "name": "nightly", "last_at": 5, "ok": true, "error": "", "size_mb": 0, "runs": 3, "took_s": 0}],
 "ext_mounts": [{"id": "m1", "name": "usb-disk", "kind": "usbd", "mounted": true, "present": true, "size_mb": 5, "used_mb": 0, "error": "e"}],
 "ups": {"model": "APC Back-UPS", "status": "OL ", "words": "on line, harging", "answers": true, "charge": 100, "runtime_s": null, "load": null},
 "host_updates": {"pending": 5, "security": 0, "checked": 0, "reboot": true},
 "spindown": 30,
 "os_image": {"version": "0.9.1+xrm", "snapshot": "20261117T1200Z", "built": "2026-11-17T12:00Z", "slot": "a", "next": "", "trial": true, "fell_back": "fell back x"},
 "os_kept": {"booted": "0.9.0x", "versions": [{"version": "0.9.0", "mb": 2048, "at": 5, "state": true}, {"version": "0.8", "mb": 0, "at": 0, "state": false}]},
 "os_stick": {"stick": true, "pool": "/mnt/sys", "ready": true, "on_stick": ["docker", "projects"], "written_kb": 5, "boot_written_kb": null, "projects": "/mnt/proj", "projects_bound": true, "projects_home": "pool", "others": ["/a"], "var_total_mb": 100},
 "vms_other": [{"name": "win10", "state": "running", "vcpus": 2, "mem_mb": 0, "autostart": true}],
 "vms": [{"name": "bbvm-dev", "state": "running", "ip": "10.0.0.9", "vcpus": 2, "mem_mb": 2048, "snapshots": ["s1"], "screen": true, "autostart": true, "hw": {"cpuset": [0, 1], "net": "br:br0", "model": "virtio", "mac": "52:54:00:aa:bb:cc", "mem_max_mb": 4096, "share": {"path": "/workspace/p", "tag": "p", "ro": true}, "tpm": true, "devices": [{"type": "pci", "addr": "0000:01:00.0"}, {"type": "usb", "vendor": "0x1234", "product": "0x5678"}]}, "usb": [{"vendor": "0x1234", "product": "0x5678", "serial": "S1", "port": "1-2.3", "name": "Keyboard"}], "guest": {"hostname": "dev", "os": "Ubuntu", "kernel": "6.8", "ips": ["10.0.0.9"], "users": 1, "fs": [["/", 5, 10]]}, "iso": "ubuntu-24.04.iso"}, {"name": "bbvm-x", "state": "", "ip": "", "vcpus": 0, "mem_mb": 0, "snapshots": [], "screen": false, "autostart": false, "hw": {"cpuset": [], "net": "project", "devices": []}, "usb": [], "iso": ""}],
 "vm_pool": {"free_mb": 5},
 "vm_host": {"cpus": [[0, 1, 3]], "usb": [{"vendor": "0x1234", "product": "0x5678", "name": "Key", "serial": "S1", "port": "1-2", "bus": 3, "speed": "480", "driver": "usbhidx", "ctl": "0000:00:14.0", "use": ["keyboard"]}, {"vendor": "", "product": "", "name": "", "serial": "", "port": "", "bus": 0, "speed": "", "driver": "", "ctl": "", "use": []}], "pci": [{"addr": "0000:01:00.0", "class": "0x030000", "vendor": "0x10de", "device": "0x2204", "group": "12", "driver": "nvidia", "host": "the display"}], "iommu": true, "bridges": ["br0"], "vnets": ["default"], "tpm": true},
 "vm_isos": [{"name": "ubuntu.iso", "mb": 5}, {"name": "x.iso", "mb": 0}],
 "sandbox": true,
 "release_key": "0123456789abcdef",
 "release_spare": "ffffffffffffffff",
 "unsigned_ok": true,
 "root_off": false,
 "gpu_card": "10de:2204 LLLLLLLLLLLLLLLLLLLLLLLLLLLLLLLLLLLLLLLLLLLLLLLLLLLLLLLLLLLLLLLLLLLLLLLLLLLLLLLLLLLLLLLLLLLLLLLLLLLLLLLLLLLLLLLLLLLLLLLLLLLLLLLLLLLLLLLLLLLLLLLLLLLLLLLLLLLLLLLLLLLLLLLLLLLLLLLLLLLLLLLLLLLLLL",
 "gpu_display": "active",
 "gpu_driver": {"installed": "550.1rm", "loaded": "550.1", "bound": "nvidia", "package": "nvidia-driver-550", "pkg_version": "550", "candidate": "560", "recommended": "nvidia-driver-560-open", "options": [{"pkg": "nvidia-driver-560-open", "version": "560.35LLLLLLLLLLLLLLLLLLLLLLLL", "open": true}]},
 "gpu_container": {"installed": "1.16", "candidate": "1.17", "runtime": true},
 "sound": {"cards": ["HDA Intel", "USB"], "virtual": ["Loopback"], "server": "pipewire"},
 "administers": false,
 "isolation": {"sessions": true, "why": "wLLLLLLLLLLLLLLLLLLLLLLLLLLLLLLLLLLLLLLLLLLLLLLLLLLLLLLLLLLLLLLLLLLLLLLLLLLLLLLLLLLLLLLLLLLLLLLLLLLLLLLLLLLLLLLLLLLLLLLLLLLLLLLLLLLLLLLLLLLLLLLLLLLLLLLLLLLLLLLLLLLLLLLLLLLLLLLLLLLLLLLLLLLLLLLLLLLLLLLL"},
 "session_net": {"can": true, "why": "", "wanted": true, "active": true, "sessions": 3, "error": "eLLLLLLLLLLLLLLLLLLLLLLLLLLLLLLLLLLLLLLLLLLLLLLLLLLLLLLLLLLLLLLLLLLLLLLLLLLLLLLLLLLLLLLLLLLLLLLLLLLLLLLLLLLLLLLLLLLLLLLLLLLLLLLLLLLLLLLLLLLLLLLLLLLLLLLLLLLLLLLLLLLLLLLLLLLLLLLLLLLLLLLLLLLLLLLLLLLLLLLLLLLLLLLLLLLLLLLLLLLLLLLLLLLLLLLLLLLLLLLLLLLLLLLLLLLLLLLLLLLLLLLLLLLLLLLLLLLLLLLLLLLLLLLLLLLLLLLLLLLL", "ctr": {"wanted": true, "can": true, "why": "", "active": true, "error": "", "bridges": 0}},
 "sysdeps": {"family": "debian", "unmet": {"jdk:21": ["libfoo", "lib+xrm"]}},
 "storage": {"at": 5, "took_s": 2, "filesystems": [{"path": "/", "source": "/dev/sda1", "type": "ext4", "ro": false, "total_mb": 10, "free_mb": null, "used_mb": null, "also": ["/a"]}], "stores": {"data": {"path": "/d", "fs": "/", "used_mb": 5, "slow": true}}, "projects": {"p1": {"data": 5, "cache": null}}, "workspace": {"path": "/workspace", "fs": "/"}, "homes": {"path": "/home", "mb": 5, "fs": "/"}, "docker": {"kinds": [{"kind": "images", "count": 3, "mb": 100, "reclaimable_mb": 0}], "root": "/var/lib/docker", "fs": "/"}, "slow": ["/mnt/slow"], "phones": [{"project": "p1", "uid": "u1", "name": "Pixel", "mb": 5, "running": true, "ran": 0, "snap_mb": 3}]},
 "mounts": [{"path": "/mnt/a", "source": "nas:/a", "type": "nfs", "ro": true, "mounted": true, "real": "/mnt/a", "stale": false, "error": "e"}],
 "door": {"kind": "tailscale", "host": "node.example.ts.netx", "installed": true, "active": true},
 "services": {"runners": [{"installed": true, "active": true, "busy": false, "name": "r1", "url": "https://github.com/x", "slot": "s1x", "forge": "github", "unit": "actions.runner@x", "labels": ["self-hosted", "xy"]}], "tailscale": {"installed": true, "dns": "node.ts.netx", "funnel": {"443": 8080, "8443": 0, "100000": null}}},
 "files": {"port": 7684},
 "relay": {"tls": "sha256:aaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaa", "once": true},
 "session": {"up": true, "screen": 7684, "ctr": true, "ctr_why": "", "term": true, "user": "bbx", "workspace": true, "writable": false, "claude": "2.0.1", "codex": "0.5", "copilot": "1.0", "grok": "0.1", "opencode": "0.2", "bundle": "b1", "why": "", "boot": "123.456", "accounts": {"users": 3, "moved": 2, "waiting": 1, "error": "e"}, "up_s": 12},
 "network": {"interface": "eth0", "addresses": ["10.0.0.5/24"], "gateway": "10.0.0.1", "dns": ["1.1.1.1"], "routes": [{"to": "10.1.0.0/24", "via": "10.0.0.2"}]},
 "distro": {"id": "ubuntu", "family": "debian", "pretty": "Ubuntu 24.04", "pkg": "apt", "network": "netplan"}
}'''

FROZEN_ALT = r'''{
 "system": "",
 "arch": "5",
 "sshd": false,
 "stores": {},
 "toolchain_versions": {},
 "toolchain_verified": {},
 "toolchain_receipts": {},
 "store_dirs": {"top": ["a"], "android": [], "incomplete": [], "roots": []},
 "toolchains": {},
 "docker_ip": "",
 "docker_gid": null,
 "internet": null,
 "store_ro": false,
 "store_noexec": true,
 "features": {"vmhost": {"installed": false, "kvm": false, "libvirt": "", "virtiofs": false}, "firewall": {"installed": false}, "iommu": {"installed": false, "on": false}, "storage": {"installed": false, "zfs": false, "mergerfs": false, "snapraid": false, "smart": false}, "shares": {"installed": false, "smb": false, "nfs": false}, "ups": {}, "gpuvm": {"installed": false, "bound": false, "cards": 0, "ids": ""}},
 "array": {"policy": "", "mount": "", "mounted": false, "data": [{"slot": 1, "id": "", "fs": "", "size_mb": 0, "used_mb": 0, "mounted": false}], "parity": [], "last_sync": 0, "last_scrub": 0, "last_check": 0, "status": "", "running": "", "progress": "", "adopted": false, "last_move": 0, "verify": {}},
 "adopted": {"from": "x", "writable": false, "at": 0, "mounts": [], "merged": {}, "parity": [], "folders": [], "apps": {"docker": {"autostart": [], "digests": {}}, "vms": [], "said": [], "at": 0}},
 "ups": {"model": "", "status": "", "words": "", "answers": false, "charge": 5, "runtime_s": null, "load": null},
 "host_updates": {"pending": 0, "security": 0, "checked": 0, "reboot": false},
 "os_kept": {"booted": "0.9.0", "versions": []},
 "vm_host": {"cpus": [], "usb": [], "pci": [], "iommu": false, "bridges": [], "vnets": [], "tpm": false},
 "sandbox": false,
 "release_key": "",
 "release_spare": "5",
 "unsigned_ok": false,
 "root_off": true,
 "gpu_amd": "Radeon",
 "gpu_driver": {"installed": "550", "loaded": "", "bound": "", "package": "", "pkg_version": "", "candidate": "", "recommended": "", "options": [], "nocard": true},
 "gpu_container": {"installed": "1.16", "candidate": "", "runtime": false, "nocard": true},
 "sound": {"cards": [], "virtual": [], "server": ""},
 "administers": true,
 "session_net": {"can": true, "why": "", "wanted": false, "active": false, "sessions": 0, "error": ""},
 "sysdeps": {"family": "", "unmet": {}},
 "mounts": [],
 "services": {"runners": [], "tailscale": {"installed": false, "dns": "", "funnel": {}}},
 "files": {"port": 0},
 "relay": {"tls": "", "once": false},
 "session": {"up": true, "screen": 0, "ctr": false, "ctr_why": "", "term": false, "user": "", "workspace": false, "writable": null, "claude": "", "codex": "", "copilot": "", "grok": "", "opencode": "", "bundle": "", "why": "", "boot": "", "accounts": {}, "up_s": null},
 "network": {"interface": "", "addresses": [], "gateway": "", "dns": [], "routes": []}
}'''

FROZEN_EMPTY = r'''{
 "cpu": 0,
 "mem_mb": 0,
 "system": "",
 "arch": "",
 "sshd": false,
 "stores": {},
 "toolchain_versions": {},
 "toolchain_verified": {},
 "toolchain_receipts": {},
 "toolchains": {},
 "docker_ip": "",
 "docker_gid": null,
 "internet": null,
 "store_ro": false,
 "store_noexec": false,
 "features": {"vmhost": {"installed": false, "kvm": false, "libvirt": ""}, "firewall": {"installed": false}, "iommu": {"installed": false, "on": false}, "storage": {"installed": false, "zfs": false, "mergerfs": false, "snapraid": false, "smart": false}, "shares": {"installed": false, "smb": false, "nfs": false}, "ups": {}, "gpuvm": {}},
 "sandbox": false,
 "release_key": "",
 "release_spare": "",
 "unsigned_ok": false,
 "root_off": false,
 "administers": false,
 "sysdeps": {"family": "", "unmet": {}},
 "mounts": [],
 "services": {"runners": [], "tailscale": {"installed": false, "dns": "", "funnel": {}}},
 "network": {"interface": "", "addresses": [], "gateway": "", "dns": [], "routes": []}
}'''

FROZEN_MATRIX = r'''{
 "cpu 2": {"set": {"cpu": 1}, "gone": []},
 "cpu 4": {"set": {"cpu": 7}, "gone": []},
 "cpu 5": {"set": {"cpu": -1}, "gone": []},
 "cpu 6": {"set": {"cpu": 2}, "gone": []},
 "cpu 8": {"set": {}, "gone": ["cpu"]},
 "cpu 10": {"set": {}, "gone": ["cpu"]},
 "cpu 12": {"set": {}, "gone": ["cpu"]},
 "mem_mb 2": {"set": {"mem_mb": 1}, "gone": []},
 "mem_mb 4": {"set": {"mem_mb": 7}, "gone": []},
 "mem_mb 5": {"set": {"mem_mb": -1}, "gone": []},
 "mem_mb 6": {"set": {"mem_mb": 2}, "gone": []},
 "mem_mb 8": {"set": {}, "gone": ["mem_mb"]},
 "mem_mb 10": {"set": {}, "gone": ["mem_mb"]},
 "mem_mb 12": {"set": {}, "gone": ["mem_mb"]},
 "os 2": {"set": {"os": "True"}, "gone": []},
 "os 4": {"set": {"os": "7"}, "gone": []},
 "os 5": {"set": {"os": "-1"}, "gone": []},
 "os 6": {"set": {"os": "2.5"}, "gone": []},
 "os 8": {"set": {"os": "text"}, "gone": []},
 "os 10": {"set": {"os": "['x', 1]"}, "gone": []},
 "os 12": {"set": {"os": "{'x': 1}"}, "gone": []},
 "docker 2": {"set": {"docker": "True"}, "gone": []},
 "docker 4": {"set": {"docker": "7"}, "gone": []},
 "docker 5": {"set": {"docker": "-1"}, "gone": []},
 "docker 6": {"set": {"docker": "2.5"}, "gone": []},
 "docker 8": {"set": {"docker": "text"}, "gone": []},
 "docker 10": {"set": {"docker": "['x', 1]"}, "gone": []},
 "docker 12": {"set": {"docker": "{'x': 1}"}, "gone": []},
 "docker_id 2": {"set": {"docker_id": "True"}, "gone": []},
 "docker_id 4": {"set": {"docker_id": "7"}, "gone": []},
 "docker_id 5": {"set": {"docker_id": "-1"}, "gone": []},
 "docker_id 6": {"set": {"docker_id": "2.5"}, "gone": []},
 "docker_id 8": {"set": {"docker_id": "text"}, "gone": []},
 "docker_id 10": {"set": {"docker_id": "['x', 1]"}, "gone": []},
 "docker_id 12": {"set": {"docker_id": "{'x': 1}"}, "gone": []},
 "gpu 2": {"set": {"gpu": "True"}, "gone": []},
 "gpu 4": {"set": {"gpu": "7"}, "gone": []},
 "gpu 5": {"set": {"gpu": "-1"}, "gone": []},
 "gpu 6": {"set": {"gpu": "2.5"}, "gone": []},
 "gpu 8": {"set": {"gpu": "text"}, "gone": []},
 "gpu 10": {"set": {"gpu": "['x', 1]"}, "gone": []},
 "gpu 12": {"set": {"gpu": "{'x': 1}"}, "gone": []},
 "hostname 2": {"set": {"hostname": "True"}, "gone": []},
 "hostname 4": {"set": {"hostname": "7"}, "gone": []},
 "hostname 5": {"set": {"hostname": "-1"}, "gone": []},
 "hostname 6": {"set": {"hostname": "2.5"}, "gone": []},
 "hostname 8": {"set": {"hostname": "text"}, "gone": []},
 "hostname 10": {"set": {"hostname": "['x', 1]"}, "gone": []},
 "hostname 12": {"set": {"hostname": "{'x': 1}"}, "gone": []},
 "git 2": {"set": {"git": "True"}, "gone": []},
 "git 4": {"set": {"git": "7"}, "gone": []},
 "git 5": {"set": {"git": "-1"}, "gone": []},
 "git 6": {"set": {"git": "2.5"}, "gone": []},
 "git 8": {"set": {"git": "text"}, "gone": []},
 "git 10": {"set": {"git": "['x', 1]"}, "gone": []},
 "git 12": {"set": {"git": "{'x': 1}"}, "gone": []},
 "system 2": {"set": {"system": "true"}, "gone": []},
 "system 4": {"set": {"system": "7"}, "gone": []},
 "system 5": {"set": {"system": "1"}, "gone": []},
 "system 6": {"set": {"system": "25"}, "gone": []},
 "system 8": {"set": {"system": "text"}, "gone": []},
 "system 10": {"set": {"system": "x1"}, "gone": []},
 "system 12": {"set": {"system": "x1"}, "gone": []},
 "arch 2": {"set": {"arch": "True"}, "gone": []},
 "arch 4": {"set": {"arch": "7"}, "gone": []},
 "arch 5": {"set": {"arch": "1"}, "gone": []},
 "arch 6": {"set": {"arch": "25"}, "gone": []},
 "arch 8": {"set": {"arch": "text"}, "gone": []},
 "arch 10": {"set": {"arch": "x1"}, "gone": []},
 "arch 12": {"set": {"arch": "x1"}, "gone": []},
 "sshd 2": {"set": {"sshd": true}, "gone": []},
 "sshd 4": {"set": {"sshd": true}, "gone": []},
 "sshd 5": {"set": {"sshd": true}, "gone": []},
 "sshd 6": {"set": {"sshd": true}, "gone": []},
 "sshd 8": {"set": {"sshd": true}, "gone": []},
 "sshd 10": {"set": {"sshd": true}, "gone": []},
 "sshd 12": {"set": {"sshd": true}, "gone": []},
 "toolchain_versions 12": {"set": {"toolchain_versions": {"x": "1"}}, "gone": []},
 "store_dirs 11": {"set": {"store_dirs": {"top": [], "android": [], "incomplete": [], "roots": []}}, "gone": []},
 "store_dirs 12": {"set": {"store_dirs": {"top": [], "android": [], "incomplete": [], "roots": []}}, "gone": []},
 "images 9": {"set": {"images": []}, "gone": []},
 "images 10": {"set": {"images": []}, "gone": []},
 "toolchains 12": {"set": {"toolchains": {"x": "1"}}, "gone": []},
 "docker_ip 2": {"set": {"docker_ip": "True"}, "gone": []},
 "docker_ip 4": {"set": {"docker_ip": "7"}, "gone": []},
 "docker_ip 5": {"set": {"docker_ip": "-1"}, "gone": []},
 "docker_ip 6": {"set": {"docker_ip": "2.5"}, "gone": []},
 "docker_ip 8": {"set": {"docker_ip": "text"}, "gone": []},
 "docker_ip 10": {"set": {"docker_ip": "['x', 1]"}, "gone": []},
 "docker_ip 12": {"set": {"docker_ip": "{'x': 1}"}, "gone": []},
 "docker_gid 3": {"set": {"docker_gid": 0}, "gone": []},
 "docker_gid 4": {"set": {"docker_gid": 7}, "gone": []},
 "internet 1": {"set": {"internet": false}, "gone": []},
 "internet 2": {"set": {"internet": true}, "gone": []},
 "store_ro 2": {"set": {"store_ro": true}, "gone": []},
 "store_noexec 2": {"set": {"store_noexec": true}, "gone": []},
 "disks 9": {"set": {"disks": []}, "gone": []},
 "disks 10": {"set": {"disks": []}, "gone": []},
 "shares 9": {"set": {"shares": []}, "gone": []},
 "shares 10": {"set": {"shares": []}, "gone": []},
 "pools 9": {"set": {"pools": []}, "gone": []},
 "pools 10": {"set": {"pools": []}, "gone": []},
 "pools_importable 9": {"set": {"pools_importable": []}, "gone": []},
 "pools_importable 10": {"set": {"pools_importable": []}, "gone": []},
 "snapshots 11": {"set": {"snapshots": {}}, "gone": []},
 "snapshots 12": {"set": {"snapshots": {}}, "gone": []},
 "array 11": {"set": {"array": {}}, "gone": []},
 "array 12": {"set": {"array": {}}, "gone": []},
 "console 12": {"set": {"console": {"os": false, "set": false, "open": false}}, "gone": []},
 "adopted 12": {"set": {"adopted": {"from": "", "writable": false, "at": 0, "mounts": [], "merged": {}, "parity": [], "folders": []}}, "gone": []},
 "timezone 7": {"set": {"timezone": ""}, "gone": []},
 "timezone 8": {"set": {"timezone": "text"}, "gone": []},
 "store_backups 9": {"set": {"store_backups": []}, "gone": []},
 "store_backups 10": {"set": {"store_backups": []}, "gone": []},
 "ext_mounts 9": {"set": {"ext_mounts": []}, "gone": []},
 "ext_mounts 10": {"set": {"ext_mounts": []}, "gone": []},
 "ups 12": {"set": {"ups": {"model": "", "status": "", "words": "", "answers": false, "charge": null, "runtime_s": null, "load": null}}, "gone": []},
 "host_updates 12": {"set": {"host_updates": {"pending": 0, "security": 0, "checked": 0, "reboot": false}}, "gone": []},
 "spindown 3": {"set": {"spindown": 0}, "gone": []},
 "vms_other 9": {"set": {"vms_other": []}, "gone": []},
 "vms_other 10": {"set": {"vms_other": []}, "gone": []},
 "vms 9": {"set": {"vms": []}, "gone": []},
 "vms 10": {"set": {"vms": []}, "gone": []},
 "vm_pool 12": {"set": {"vm_pool": {}}, "gone": []},
 "vm_host 12": {"set": {"vm_host": {"cpus": [], "usb": [], "pci": [], "iommu": false, "bridges": [], "vnets": [], "tpm": false}}, "gone": []},
 "vm_isos 9": {"set": {"vm_isos": []}, "gone": []},
 "vm_isos 10": {"set": {"vm_isos": []}, "gone": []},
 "sandbox 2": {"set": {"sandbox": true}, "gone": []},
 "sandbox 4": {"set": {"sandbox": true}, "gone": []},
 "sandbox 5": {"set": {"sandbox": true}, "gone": []},
 "sandbox 6": {"set": {"sandbox": true}, "gone": []},
 "sandbox 8": {"set": {"sandbox": true}, "gone": []},
 "sandbox 10": {"set": {"sandbox": true}, "gone": []},
 "sandbox 12": {"set": {"sandbox": true}, "gone": []},
 "release_key 2": {"set": {"release_key": "e"}, "gone": []},
 "release_key 4": {"set": {"release_key": "7"}, "gone": []},
 "release_key 5": {"set": {"release_key": "1"}, "gone": []},
 "release_key 6": {"set": {"release_key": "25"}, "gone": []},
 "release_key 8": {"set": {"release_key": "e"}, "gone": []},
 "release_key 10": {"set": {"release_key": "1"}, "gone": []},
 "release_key 12": {"set": {"release_key": "1"}, "gone": []},
 "release_spare 2": {"set": {"release_spare": "e"}, "gone": []},
 "release_spare 4": {"set": {"release_spare": "7"}, "gone": []},
 "release_spare 5": {"set": {"release_spare": "1"}, "gone": []},
 "release_spare 6": {"set": {"release_spare": "25"}, "gone": []},
 "release_spare 8": {"set": {"release_spare": "e"}, "gone": []},
 "release_spare 10": {"set": {"release_spare": "1"}, "gone": []},
 "release_spare 12": {"set": {"release_spare": "1"}, "gone": []},
 "unsigned_ok 2": {"set": {"unsigned_ok": true}, "gone": []},
 "root_off 2": {"set": {"root_off": true}, "gone": []},
 "gpu_card 2": {"set": {"gpu_card": "True"}, "gone": []},
 "gpu_card 4": {"set": {"gpu_card": "7"}, "gone": []},
 "gpu_card 5": {"set": {"gpu_card": "-1"}, "gone": []},
 "gpu_card 6": {"set": {"gpu_card": "2.5"}, "gone": []},
 "gpu_card 8": {"set": {"gpu_card": "text"}, "gone": []},
 "gpu_card 10": {"set": {"gpu_card": "['x', 1]"}, "gone": []},
 "gpu_card 12": {"set": {"gpu_card": "{'x': 1}"}, "gone": []},
 "gpu_display 2": {"set": {"gpu_display": "True"}, "gone": []},
 "gpu_display 4": {"set": {"gpu_display": "7"}, "gone": []},
 "gpu_display 5": {"set": {"gpu_display": "-1"}, "gone": []},
 "gpu_display 6": {"set": {"gpu_display": "2.5"}, "gone": []},
 "gpu_display 8": {"set": {"gpu_display": "text"}, "gone": []},
 "gpu_display 10": {"set": {"gpu_display": "['x', 1]"}, "gone": []},
 "gpu_display 12": {"set": {"gpu_display": "{'x': 1}"}, "gone": []},
 "gpu_amd 2": {"set": {"gpu_amd": "True"}, "gone": []},
 "gpu_amd 4": {"set": {"gpu_amd": "7"}, "gone": []},
 "gpu_amd 5": {"set": {"gpu_amd": "-1"}, "gone": []},
 "gpu_amd 6": {"set": {"gpu_amd": "2.5"}, "gone": []},
 "gpu_amd 8": {"set": {"gpu_amd": "text"}, "gone": []},
 "gpu_amd 10": {"set": {"gpu_amd": "['x', 1]"}, "gone": []},
 "gpu_amd 12": {"set": {"gpu_amd": "{'x': 1}"}, "gone": []},
 "sound 11": {"set": {"sound": {"cards": [], "virtual": [], "server": ""}}, "gone": []},
 "sound 12": {"set": {"sound": {"cards": [], "virtual": [], "server": ""}}, "gone": []},
 "administers 2": {"set": {"administers": true}, "gone": []},
 "administers 4": {"set": {"administers": true}, "gone": []},
 "administers 5": {"set": {"administers": true}, "gone": []},
 "administers 6": {"set": {"administers": true}, "gone": []},
 "administers 8": {"set": {"administers": true}, "gone": []},
 "administers 10": {"set": {"administers": true}, "gone": []},
 "administers 12": {"set": {"administers": true}, "gone": []},
 "isolation 11": {"set": {"isolation": {"sessions": false, "why": ""}}, "gone": []},
 "isolation 12": {"set": {"isolation": {"sessions": false, "why": ""}}, "gone": []},
 "session_net 12": {"set": {"session_net": {"can": false, "why": "", "wanted": false, "active": false, "sessions": 0, "error": ""}}, "gone": []},
 "files 11": {"set": {"files": {"port": 0}}, "gone": []},
 "files 12": {"set": {"files": {"port": 0}}, "gone": []},
 "relay 11": {"set": {"relay": {"tls": "", "once": false}}, "gone": []},
 "relay 12": {"set": {"relay": {"tls": "", "once": false}}, "gone": []},
 "session 11": {"set": {"session": {"up": false, "screen": 0, "ctr": false, "ctr_why": "", "term": false, "user": "", "workspace": false, "writable": null, "claude": "", "codex": "", "copilot": "", "grok": "", "opencode": "", "bundle": "", "why": "", "boot": "", "accounts": {}, "up_s": null}}, "gone": []},
 "session 12": {"set": {"session": {"up": false, "screen": 0, "ctr": false, "ctr_why": "", "term": false, "user": "", "workspace": false, "writable": null, "claude": "", "codex": "", "copilot": "", "grok": "", "opencode": "", "bundle": "", "why": "", "boot": "", "accounts": {}, "up_s": null}}, "gone": []},
 "distro 11": {"set": {"distro": {"id": "", "family": "", "pretty": "", "pkg": "", "network": ""}}, "gone": []},
 "distro 12": {"set": {"distro": {"id": "", "family": "", "pretty": "", "pkg": "", "network": ""}}, "gone": []},
 "all 1": {"set": {"internet": false}, "gone": []},
 "all 2": {"set": {"cpu": 1, "mem_mb": 1, "os": "True", "docker": "True", "docker_id": "True", "gpu": "True", "hostname": "True", "git": "True", "system": "true", "arch": "True", "sshd": true, "docker_ip": "True", "internet": true, "store_ro": true, "store_noexec": true, "sandbox": true, "release_key": "e", "release_spare": "e", "unsigned_ok": true, "root_off": true, "gpu_card": "True", "gpu_display": "True", "gpu_amd": "True", "administers": true}, "gone": []},
 "all 3": {"set": {"docker_gid": 0, "spindown": 0}, "gone": []},
 "all 4": {"set": {"cpu": 7, "mem_mb": 7, "os": "7", "docker": "7", "docker_id": "7", "gpu": "7", "hostname": "7", "git": "7", "system": "7", "arch": "7", "sshd": true, "docker_ip": "7", "docker_gid": 7, "sandbox": true, "release_key": "7", "release_spare": "7", "gpu_card": "7", "gpu_display": "7", "gpu_amd": "7", "administers": true}, "gone": []},
 "all 5": {"set": {"cpu": -1, "mem_mb": -1, "os": "-1", "docker": "-1", "docker_id": "-1", "gpu": "-1", "hostname": "-1", "git": "-1", "system": "1", "arch": "1", "sshd": true, "docker_ip": "-1", "sandbox": true, "release_key": "1", "release_spare": "1", "gpu_card": "-1", "gpu_display": "-1", "gpu_amd": "-1", "administers": true}, "gone": []},
 "all 6": {"set": {"cpu": 2, "mem_mb": 2, "os": "2.5", "docker": "2.5", "docker_id": "2.5", "gpu": "2.5", "hostname": "2.5", "git": "2.5", "system": "25", "arch": "25", "sshd": true, "docker_ip": "2.5", "sandbox": true, "release_key": "25", "release_spare": "25", "gpu_card": "2.5", "gpu_display": "2.5", "gpu_amd": "2.5", "administers": true}, "gone": []},
 "all 7": {"set": {"timezone": ""}, "gone": []},
 "all 8": {"set": {"os": "text", "docker": "text", "docker_id": "text", "gpu": "text", "hostname": "text", "git": "text", "system": "text", "arch": "text", "sshd": true, "docker_ip": "text", "timezone": "text", "sandbox": true, "release_key": "e", "release_spare": "e", "gpu_card": "text", "gpu_display": "text", "gpu_amd": "text", "administers": true}, "gone": ["cpu", "mem_mb"]},
 "all 9": {"set": {"images": [], "disks": [], "shares": [], "pools": [], "pools_importable": [], "store_backups": [], "ext_mounts": [], "vms_other": [], "vms": [], "vm_isos": []}, "gone": []},
 "all 10": {"set": {"os": "['x', 1]", "docker": "['x', 1]", "docker_id": "['x', 1]", "gpu": "['x', 1]", "hostname": "['x', 1]", "git": "['x', 1]", "system": "x1", "arch": "x1", "sshd": true, "images": [], "docker_ip": "['x', 1]", "disks": [], "shares": [], "pools": [], "pools_importable": [], "store_backups": [], "ext_mounts": [], "vms_other": [], "vms": [], "vm_isos": [], "sandbox": true, "release_key": "1", "release_spare": "1", "gpu_card": "['x', 1]", "gpu_display": "['x', 1]", "gpu_amd": "['x', 1]", "administers": true}, "gone": ["cpu", "mem_mb"]},
 "all 11": {"set": {"store_dirs": {"top": [], "android": [], "incomplete": [], "roots": []}, "snapshots": {}, "array": {}, "sound": {"cards": [], "virtual": [], "server": ""}, "isolation": {"sessions": false, "why": ""}, "files": {"port": 0}, "relay": {"tls": "", "once": false}, "session": {"up": false, "screen": 0, "ctr": false, "ctr_why": "", "term": false, "user": "", "workspace": false, "writable": null, "claude": "", "codex": "", "copilot": "", "grok": "", "opencode": "", "bundle": "", "why": "", "boot": "", "accounts": {}, "up_s": null}, "distro": {"id": "", "family": "", "pretty": "", "pkg": "", "network": ""}}, "gone": []},
 "all 12": {"set": {"os": "{'x': 1}", "docker": "{'x': 1}", "docker_id": "{'x': 1}", "gpu": "{'x': 1}", "hostname": "{'x': 1}", "git": "{'x': 1}", "system": "x1", "arch": "x1", "sshd": true, "toolchain_versions": {"x": "1"}, "store_dirs": {"top": [], "android": [], "incomplete": [], "roots": []}, "toolchains": {"x": "1"}, "docker_ip": "{'x': 1}", "snapshots": {}, "array": {}, "console": {"os": false, "set": false, "open": false}, "adopted": {"from": "", "writable": false, "at": 0, "mounts": [], "merged": {}, "parity": [], "folders": []}, "ups": {"model": "", "status": "", "words": "", "answers": false, "charge": null, "runtime_s": null, "load": null}, "host_updates": {"pending": 0, "security": 0, "checked": 0, "reboot": false}, "vm_pool": {}, "vm_host": {"cpus": [], "usb": [], "pci": [], "iommu": false, "bridges": [], "vnets": [], "tpm": false}, "sandbox": true, "release_key": "1", "release_spare": "1", "gpu_card": "{'x': 1}", "gpu_display": "{'x': 1}", "gpu_amd": "{'x': 1}", "gpu_driver": {"installed": "", "loaded": "", "bound": "", "package": "", "pkg_version": "", "candidate": "", "recommended": "", "options": []}, "gpu_container": {"installed": "", "candidate": "", "runtime": false}, "sound": {"cards": [], "virtual": [], "server": ""}, "administers": true, "isolation": {"sessions": false, "why": ""}, "session_net": {"can": false, "why": "", "wanted": false, "active": false, "sessions": 0, "error": ""}, "files": {"port": 0}, "relay": {"tls": "", "once": false}, "session": {"up": false, "screen": 0, "ctr": false, "ctr_why": "", "term": false, "user": "", "workspace": false, "writable": null, "claude": "", "codex": "", "copilot": "", "grok": "", "opencode": "", "bundle": "", "why": "", "boot": "", "accounts": {}, "up_s": null}, "distro": {"id": "", "family": "", "pretty": "", "pkg": "", "network": ""}}, "gone": ["cpu", "mem_mb"]}
}'''

FROZEN_DEEP = r'''{
 "stores": {"answers": "272eb4d59720c22a", "raises": []},
 "tunnel": {"answers": "eeaabae11eeee403", "raises": []},
 "toolchain_versions": {"answers": "0ff3bf4b6259d135", "raises": []},
 "toolchain_verified": {"answers": "5794ac6fd77e11a0", "raises": []},
 "toolchain_receipts": {"answers": "a3b5a337095355f1", "raises": []},
 "tokseal": {"answers": "15326b88e3153231", "raises": []},
 "store_dirs": {"answers": "6af735f7b0a1a323", "raises": ["top 2 TypeError", "top 4 TypeError", "top 5 TypeError", "top 6 TypeError", "top 12 KeyError", "android 2 TypeError", "android 4 TypeError", "android 5 TypeError", "android 6 TypeError", "android 12 KeyError", "incomplete 2 TypeError", "incomplete 4 TypeError", "incomplete 5 TypeError", "incomplete 6 TypeError", "incomplete 12 KeyError", "roots 2 TypeError", "roots 4 TypeError", "roots 5 TypeError", "roots 6 TypeError", "roots 12 KeyError"]},
 "images": {"answers": "bd45578f3abbf62b", "raises": ["avds 2 TypeError", "avds 4 TypeError", "avds 5 TypeError", "avds 6 TypeError", "avds 12 KeyError"]},
 "toolchains": {"answers": "dd126078796d1bad", "raises": []},
 "features": {"answers": "3f8cf028358f4c5f", "raises": []},
 "disks": {"answers": "3a4ea5baa800189c", "raises": ["parts 2 TypeError", "parts 4 TypeError", "parts 5 TypeError", "parts 6 TypeError", "parts 12 KeyError"]},
 "shares": {"answers": "67850aadf8e45ad4", "raises": []},
 "pools": {"answers": "d07fc9e8d55e7ac2", "raises": ["vdevs 2 TypeError", "vdevs 4 TypeError", "vdevs 5 TypeError", "vdevs 6 TypeError", "vdevs 12 KeyError"]},
 "pools_importable": {"answers": "a8b3834163092821", "raises": []},
 "snapshots": {"answers": "67370e2d473d2360", "raises": []},
 "array": {"answers": "abe3b1d43346d495", "raises": ["data 2 TypeError", "data 4 TypeError", "data 5 TypeError", "data 6 TypeError", "data 12 KeyError", "parity 2 TypeError", "parity 4 TypeError", "parity 5 TypeError", "parity 6 TypeError", "parity 12 KeyError"]},
 "console": {"answers": "c71c2ff1ba839c19", "raises": []},
 "adopted": {"answers": "76d2f33a785fb0f5", "raises": ["mounts 2 TypeError", "mounts 4 TypeError", "mounts 5 TypeError", "mounts 6 TypeError", "mounts 12 KeyError", "parity 2 TypeError", "parity 4 TypeError", "parity 5 TypeError", "parity 6 TypeError", "parity 12 KeyError", "folders 2 TypeError", "folders 4 TypeError", "folders 5 TypeError", "folders 6 TypeError", "folders 12 KeyError"]},
 "store_backups": {"answers": "9bf39a66a105e0d9", "raises": []},
 "ext_mounts": {"answers": "c6fdd342db212a26", "raises": []},
 "ups": {"answers": "9fb8e5085f53455e", "raises": []},
 "host_updates": {"answers": "e114f76a50acb2da", "raises": []},
 "os_image": {"answers": "3806c0f45cd59384", "raises": []},
 "os_kept": {"answers": "fe084a43cb20df7d", "raises": []},
 "os_stick": {"answers": "05faf48072eb2960", "raises": ["on_stick 2 TypeError", "on_stick 4 TypeError", "on_stick 5 TypeError", "on_stick 6 TypeError", "others 2 TypeError", "others 4 TypeError", "others 5 TypeError", "others 6 TypeError"]},
 "vms_other": {"answers": "b3a26650b6198368", "raises": []},
 "vms": {"answers": "a2eb8f2f3686ff1b", "raises": ["snapshots 2 TypeError", "snapshots 4 TypeError", "snapshots 5 TypeError", "snapshots 6 TypeError", "snapshots 12 KeyError"]},
 "vm_pool": {"answers": "35c6e83ade6f8b87", "raises": []},
 "vm_host": {"answers": "103882f7d2c0e3f7", "raises": ["cpus 2 TypeError", "cpus 4 TypeError", "cpus 5 TypeError", "cpus 6 TypeError", "cpus 12 KeyError", "usb 2 TypeError", "usb 4 TypeError", "usb 5 TypeError", "usb 6 TypeError", "usb 12 KeyError", "pci 2 TypeError", "pci 4 TypeError", "pci 5 TypeError", "pci 6 TypeError", "pci 12 KeyError", "bridges 2 TypeError", "bridges 4 TypeError", "bridges 5 TypeError", "bridges 6 TypeError", "bridges 12 KeyError", "vnets 2 TypeError", "vnets 4 TypeError", "vnets 5 TypeError", "vnets 6 TypeError", "vnets 12 KeyError"]},
 "vm_isos": {"answers": "63bdce1fcd64c4cd", "raises": []},
 "gpu_driver": {"answers": "a0ad629a7fb9ebc2", "raises": ["options 2 TypeError", "options 4 TypeError", "options 5 TypeError", "options 6 TypeError", "options 12 KeyError"]},
 "gpu_container": {"answers": "ecebdc1bb6ee34e2", "raises": []},
 "sound": {"answers": "c4f8b8269ea44085", "raises": ["cards 2 TypeError", "cards 4 TypeError", "cards 5 TypeError", "cards 6 TypeError", "cards 12 KeyError", "virtual 2 TypeError", "virtual 4 TypeError", "virtual 5 TypeError", "virtual 6 TypeError", "virtual 12 KeyError"]},
 "isolation": {"answers": "783e7a1049a615ad", "raises": []},
 "session_net": {"answers": "e54c72c0372d9a25", "raises": []},
 "sysdeps": {"answers": "a1191891ae02e968", "raises": []},
 "storage": {"answers": "b7bac34de98952a5", "raises": ["at 8 ValueError", "at 10 TypeError", "at 12 TypeError", "took_s 8 ValueError", "took_s 10 TypeError", "took_s 12 TypeError", "filesystems 2 TypeError", "filesystems 4 TypeError", "filesystems 5 TypeError", "filesystems 6 TypeError", "filesystems 12 KeyError", "stores 2 AttributeError", "stores 4 AttributeError", "stores 5 AttributeError", "stores 6 AttributeError", "stores 8 AttributeError", "stores 10 AttributeError", "projects 2 AttributeError", "projects 4 AttributeError", "projects 5 AttributeError", "projects 6 AttributeError", "projects 8 AttributeError", "projects 10 AttributeError", "workspace 2 AttributeError", "workspace 4 AttributeError", "workspace 5 AttributeError", "workspace 6 AttributeError", "workspace 8 AttributeError", "workspace 10 AttributeError", "homes 2 AttributeError", "homes 4 AttributeError", "homes 5 AttributeError", "homes 6 AttributeError", "homes 8 AttributeError", "homes 10 AttributeError", "docker 2 AttributeError", "docker 4 AttributeError", "docker 5 AttributeError", "docker 6 AttributeError", "docker 8 AttributeError", "docker 10 AttributeError", "slow 2 TypeError", "slow 4 TypeError", "slow 5 TypeError", "slow 6 TypeError", "slow 12 KeyError", "phones 2 TypeError", "phones 4 TypeError", "phones 5 TypeError", "phones 6 TypeError", "phones 12 KeyError"]},
 "mounts": {"answers": "7c1daf62f7758a6c", "raises": []},
 "door": {"answers": "b9492a6e17204ec4", "raises": []},
 "services": {"answers": "4bb6bbc383dbc61b", "raises": []},
 "files": {"answers": "fbf9e523283e4421", "raises": []},
 "relay": {"answers": "391f34d7587db49f", "raises": []},
 "session": {"answers": "3716d64d69a09593", "raises": []},
 "network": {"answers": "0f9aea7e6a3239f5", "raises": ["addresses 2 TypeError", "addresses 4 TypeError", "addresses 5 TypeError", "addresses 6 TypeError", "addresses 12 KeyError", "dns 2 TypeError", "dns 4 TypeError", "dns 5 TypeError", "dns 6 TypeError", "dns 12 KeyError", "routes 2 TypeError", "routes 4 TypeError", "routes 5 TypeError", "routes 6 TypeError", "routes 12 KeyError"]},
 "distro": {"answers": "05fd2976216450ba", "raises": []},
 "evil": {"answers": "c117e4b316e61d85", "raises": []}
}'''


if __name__ == "__main__":
    if sys.argv[1:] == ["freeze"]:
        print(frozen())
    else:
        unittest.main()
