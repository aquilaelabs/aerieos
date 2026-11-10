"""The containers another system ran, as compose files to import (the
operator, 10 Nov: a zip of their compose files, each imported from New
container, rather than containers made here on a press).

Each is written from what the old Docker's image file says it ran: its
settings, handed over by the read (the agent's adopt.container_spec), are
its image, its environment beyond its image's own, its ports, its paths as
they were (under the adopted disks' old paths, so it finds its files where
they were), its fixed address on a network of the LAN, and how it was run;
it restarts with the machine where it started with it there. A stick made
with a plan has each template's compose too, used for one the read did not
hand over. What will not work as written (a path the adopted disks do not
hold, a writable path that may sit on a read-only data disk, another
container's network) is said at the top of its file and on its row.

The settings are kept in the state folder, readable by the controller
alone, since an environment holds passwords; the next read replaces them.
"""
import io
import json
import os
import re
import time
import zipfile
from pathlib import Path

STATE: Path = Path("/config")
FILE = "old-apps.json"
MAX = 4 * 1024 * 1024

NAME_RE = re.compile(r"[A-Za-z0-9][A-Za-z0-9 ._-]{0,63}")
# The old paths the adopted disks hold.
HELD = re.compile(r"^/mnt/(user|user0|disk[1-9][0-9]?|[a-z][a-z0-9_-]{0,31})(/|$)")
NOT_HELD = ("/mnt/disks/", "/mnt/remotes/", "/mnt/addons/", "/mnt/rootshare/")
# What a container's settings carry over to its service as they are.
AS_IS = ("command", "entrypoint", "user", "working_dir", "hostname", "tty", "stdin_open", "privileged", "init",
         "cap_add", "cap_drop", "devices", "extra_hosts", "dns", "security_opt", "group_add", "tmpfs", "sysctls",
         "shm_size", "mem_limit", "cpus", "cpuset", "pid", "ipc", "runtime", "mac_address", "logging", "labels",
         "volumes")


def configure(*, state):
    globals().update(STATE=Path(state))


def slug_of(name):
    return re.sub(r"[^a-z0-9-]+", "-", str(name).lower()).strip("-")[:40] or "app"


# ---- the settings the read handed over ----

def take(stream, length):
    """The read's upload: {"specs": {name: settings}, "autostart": [names]},
    kept whole in place of the last. (answer, status)."""
    if length <= 0 or length > MAX:
        return {"error": f"the settings are over {MAX >> 20} MB or empty: not taken"}, 413
    body = stream.read(length)
    if len(body) != length:
        return {"error": "short body"}, 400
    try:
        got = json.loads(body)
    except ValueError:
        return {"error": "not JSON"}, 400
    specs = got.get("specs") if isinstance(got, dict) else None
    if not isinstance(specs, dict):
        return {"error": "the settings are {specs: {name: settings}, autostart: [names]}"}, 400
    keep = {"at": int(time.time()),
            "specs": {str(k): v for k, v in list(specs.items())[:256] if NAME_RE.fullmatch(str(k)) and isinstance(v, dict)},
            "autostart": [str(x) for x in (got.get("autostart") or [])[:256] if isinstance(x, str)]}
    f = STATE / FILE
    tmp = f.with_name(f".{FILE}.new")
    fd = os.open(tmp, os.O_WRONLY | os.O_CREAT | os.O_TRUNC, 0o600)
    with os.fdopen(fd, "w", encoding="utf-8") as fh:
        json.dump(keep, fh)
    os.replace(tmp, f)
    return {"ok": True, "containers": len(keep["specs"])}, 200


def kept():
    try:
        got = json.loads((STATE / FILE).read_text(encoding="utf-8"))
        return got if isinstance(got, dict) else {}
    except (OSError, ValueError, TypeError):
        return {}


# ---- one container's compose ----

def compose_of(name, spec, autostart=()):
    """A container's compose from what the read says it ran: (compose dict,
    [notes]). Its image as it named it, its digest said at the top of its
    file."""
    key = slug_of(name)
    svc: dict = {"image": str(spec.get("image") or "")}
    env = {}
    for e in spec.get("environment") or []:
        k, _, v = str(e).partition("=")
        if k:
            env[k] = v
    if env:
        svc["environment"] = env
    for k in AS_IS:
        if spec.get(k) not in (None, "", [], {}):
            svc[k] = spec[k]
    notes = []
    mode = str(spec.get("network_mode") or "bridge")
    nets = spec.get("networks") if isinstance(spec.get("networks"), dict) else {}
    comp: dict = {"services": {key: svc}}
    if mode in ("host", "none"):
        svc["network_mode"] = mode
    elif mode.startswith("container:"):
        svc["network_mode"] = mode
        notes.append(f"it used the network of {mode.partition(':')[2]}: once that runs here, put its container's name in network_mode")
    elif mode != "bridge":
        mine = {n: x for n, x in nets.items() if isinstance(x, dict)} or {mode: {}}
        svc["networks"] = {n: ({"ipv4_address": x["ipv4_address"]} if x.get("ipv4_address") else {}) for n, x in mine.items()}
        comp["networks"] = {n: {"external": True} for n in mine}
        notes.append(f"it joins {', '.join(mine)}, a network made once on the Containers page before it starts")
    if mode in ("host", "none") or mode.startswith("container:"):
        svc.pop("ports", None)
    elif spec.get("ports"):
        svc["ports"] = list(spec["ports"])
    gpus = spec.get("gpus")
    if gpus:
        dev: dict = {"driver": "nvidia", "capabilities": ["gpu"]}
        dev.update({"device_ids": gpus} if isinstance(gpus, list) else {"count": gpus})
        svc["deploy"] = {"resources": {"reservations": {"devices": [dev]}}}
    if spec.get("runtime") == "nvidia":
        notes.append("it ran with the NVIDIA runtime, which this machine has once its GPU's drivers are installed")
    svc["restart"] = str(spec.get("restart") or ("unless-stopped" if name in autostart else "no"))
    return comp, notes


def compose_for(app, read, pools=(), writable=False, shares=None):
    """A plan's app (its template's compose) as it runs here: (compose dict,
    [notes], autostart). `read` is what the old Docker's image file said
    (autostart, digests)."""
    comp = app.get("compose")
    if isinstance(comp, str):
        try:
            comp = json.loads(comp)
        except ValueError:
            return None, ["its compose file is not one this can read"], False
    if not isinstance(comp, dict) or not isinstance(comp.get("services"), dict) or len(comp["services"]) != 1:
        return None, ["its compose file is not one service"], False
    comp = json.loads(json.dumps(comp))
    (_key, svc), = comp["services"].items()
    name = str(app.get("name") or _key)
    auto = name in (read.get("autostart") or [])
    svc["restart"] = "unless-stopped" if auto else "no"
    fixed = svc.pop("x-fixed-network", None)
    notes = []
    if isinstance(fixed, dict) and fixed.get("name"):
        net = str(fixed["name"])
        comp["networks"] = {net: {"external": True}}
        svc["networks"] = {net: ({"ipv4_address": fixed["ip"]} if fixed.get("ip") else {})}
        svc.pop("ports", None)
        notes.append(f"it joins {net}, a network made once on the Containers page before it starts")
    return comp, notes + path_notes(comp, pools, writable, shares), auto


def path_notes(comp, pools=(), writable=False, shares=None):
    """What a compose's paths will not find here, or may not write."""
    notes = []
    for svc in (comp.get("services") or {}).values():
        for v in svc.get("volumes") or []:
            host, _, rest = str(v).partition(":")
            mode = rest.rsplit(":", 1)[1] if rest.count(":") else "rw"
            if host.startswith(NOT_HELD):
                notes.append(f"{host} is on a disk or share the old system mounted on its own, not one adopted here: mount it from Storage's other disks and shares (under /mnt/other) and point the container there")
            elif host.startswith("/mnt/") and not HELD.match(host):
                notes.append(f"{host} is not under a path the adopted disks hold")
            elif m := HELD.match(host):
                top = m.group(1)
                if top not in ("user", "user0") and not top.startswith("disk") and pools and top not in pools:
                    notes.append(f"{host} is on {top}, which is not a pool adopted here")
                share = host.split("/")[3] if host.count("/") >= 3 else ""
                cache = ((shares or {}).get(share) or {}).get("cache", "")
                if not writable and mode != "ro" and (top.startswith("disk") or top == "user0" or (top == "user" and cache in ("no", "yes"))):
                    notes.append(f"{host} may be on a data disk adopted read-only, where it cannot write")
    return notes


# ---- every container, for the page and the zip ----

def _all(cfg, adopted):
    """[(name, compose or None, notes, autostart, digest)]: the read's,
    then a plan's app the read did not hand over."""
    read = ((adopted or {}).get("apps") or {}).get("docker") or {}
    pools = [str(p.get("name")) for p in (cfg or {}).get("pools") or [] if isinstance(p, dict)]
    shares = {str(s.get("name")): s for s in (cfg or {}).get("shares") or [] if isinstance(s, dict)}
    writable = (adopted or {}).get("writable") is True
    k = kept()
    auto = set(k.get("autostart") or read.get("autostart") or [])
    out, seen = [], set()
    for name, spec in sorted((k.get("specs") or {}).items(), key=lambda x: x[0].lower()):
        comp, notes = compose_of(name, spec, auto)
        out.append((name, comp, notes + path_notes(comp, pools, writable, shares), name in auto, str(spec.get("digest") or "")))
        seen.add(name)
    for app in (cfg or {}).get("apps") or []:
        if not isinstance(app, dict) or not NAME_RE.fullmatch(str(app.get("name") or "")) or app["name"] in seen:
            continue
        comp, notes, a = compose_for(app, read, pools, writable, shares)
        out.append((app["name"], comp, notes, a, str((read.get("digests") or {}).get(app["name"]) or "")))
    return out


def rows(cfg, adopted):
    """Each container as its row says it: {apps: [{name, file, autostart,
    notes, network, ok}], networks: {name: {subnet, gateway}}}, the
    networks being the ones its containers joined with a fixed address."""
    apps, nets = [], {}
    for name, comp, notes, auto, _digest in _all(cfg, adopted):
        net = ""
        if comp:
            svc = next(iter(comp["services"].values()))
            net = next(iter(svc.get("networks") or {}), "") or svc.get("network_mode") or "bridge"
        # Its network is said on the row with its Make button beside it,
        # so the file's line about joining it is not said twice.
        notes = [x for x in notes if not x.startswith("it joins ")]
        apps.append({"name": name, "file": f"{slug_of(name)}.yaml", "autostart": auto, "notes": notes,
                     "network": net, "ok": comp is not None})
    for spec in (kept().get("specs") or {}).values():
        for n, x in (spec.get("networks") or {}).items() if isinstance(spec.get("networks"), dict) else []:
            if isinstance(x, dict) and x.get("subnet") and n not in nets:
                nets[n] = {"subnet": str(x["subnet"]), "gateway": str(x.get("gateway") or "")}
    return {"apps": apps, "networks": nets}


# ---- the zip ----

PLAIN_KEY = re.compile(r"[A-Za-z_][A-Za-z0-9_.-]*")
RESERVED = {"y", "n", "yes", "no", "on", "off", "true", "false", "null"}


def _key(k):
    k = str(k)
    return k if PLAIN_KEY.fullmatch(k) and k.lower() not in RESERVED else json.dumps(k, ensure_ascii=False)


def _scalar(v):
    if v is True or v is False:
        return "true" if v else "false"
    if v is None:
        return "null"
    if isinstance(v, (int, float)):
        return str(v)
    # Double quoted, every string: a port reads as a number to YAML 1.1
    # otherwise, and compose reads $ as a variable, so a literal one is $$.
    return json.dumps(str(v).replace("$", "$$"), ensure_ascii=False)


def _lines(v, ind=0):
    pad, out = "  " * ind, []
    if isinstance(v, dict):
        for k, x in v.items():
            if isinstance(x, (dict, list)) and x:
                out.append(f"{pad}{_key(k)}:")
                out += _lines(x, ind + 1)
            else:
                out.append(f"{pad}{_key(k)}: {('{}' if isinstance(x, dict) else '[]') if isinstance(x, (dict, list)) else _scalar(x)}")
    else:
        for x in v:
            if isinstance(x, (dict, list)) and x:
                sub = _lines(x, ind + 1)
                out.append(f"{pad}- {sub[0].lstrip()}")
                out += sub[1:]
            else:
                out.append(f"{pad}- {_scalar(x)}")
    return out


def yaml_of(comp):
    """A compose dict as YAML, in the order it was built."""
    return "\n".join(_lines(comp)) + "\n"


def file_of(name, comp, notes, digest=""):
    head = [f"# {name}, as it ran on the old system: its image, settings, paths and network.",
            "# Import it on the Containers page: New container, Compose, Import a compose file."]
    if digest and "@sha256:" in digest:
        head.append(f"# It ran {digest}: put that as its image to run exactly what ran.")
    head += [f"# Note: {n}." for n in notes]
    return "\n".join(head) + "\n\n" + yaml_of(comp)


README = """These are the containers the old system ran, one compose file each.

Import each one on the Containers page: New container, then Compose, then
Import a compose file, then Create, then Build. Its paths are the ones it
had, under the adopted disks, so it finds its files where they were.

A file that says it joins a network needs that network made once first: on
the Containers page, under Containers and VMs from the old system, Make the
network. Anything else a file will not do as written is said at its top.
"""


def export_zip(cfg, adopted):
    """(file name, the zip's bytes), or None when there is nothing to write."""
    files = [(name, comp, notes, digest) for name, comp, notes, _a, digest in _all(cfg, adopted) if comp]
    if not files:
        return None
    buf, used = io.BytesIO(), set()
    with zipfile.ZipFile(buf, "w", zipfile.ZIP_DEFLATED) as z:
        z.writestr("old-system-compose/README.txt", README)
        for name, comp, notes, digest in files:
            base = slug_of(name)
            fname, i = f"{base}.yaml", 2
            while fname in used:
                fname, i = f"{base}-{i}.yaml", i + 1
            used.add(fname)
            z.writestr(f"old-system-compose/{fname}", file_of(name, comp, notes, digest))
    return "old-system-compose.zip", buf.getvalue()
