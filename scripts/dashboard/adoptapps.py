"""The containers another system ran, made again here (R163 step 10): each
from the compose file its template became, as the Containers page makes any
container, with the exact image it ran (the digest read from the old Docker's
image file), its fixed address on a network of the LAN kept, and started
with the machine where it was. Its paths are the template's, under the
adopted disks' old paths, so it finds its files where they were; a path the
adopted disks do not hold is said, and so is a writable path that may sit on
a read-only data disk.

What it asks for beyond its own folder (those paths, devices, privileges)
is shown once on the Nodes page, and the press that starts the containers
acknowledges it for each, as Build on the Containers page does for one.
"""
import json
import re

import containers
import devactions
import devapp

NAME_RE = re.compile(r"[A-Za-z0-9][A-Za-z0-9 ._-]{0,63}")
# The old paths the adopted disks hold.
HELD = re.compile(r"^/mnt/(user|user0|disk[1-9][0-9]?|[a-z][a-z0-9_-]{0,31})(/|$)")
NOT_HELD = ("/mnt/disks/", "/mnt/remotes/", "/mnt/addons/", "/mnt/rootshare/")


def slug_of(name):
    return re.sub(r"[^a-z0-9-]+", "-", str(name).lower()).strip("-")[:40] or "app"


def compose_for(app, read, pools=(), writable=False, shares=None):
    """One app's compose as it runs here: (compose dict, [notes], autostart).
    `read` is what the old Docker's image file said (autostart, digests),
    `pools` the adopted pools' names, `shares` the plan's shares by name."""
    comp = app.get("compose")
    if isinstance(comp, str):
        try:
            comp = json.loads(comp)
        except ValueError:
            return None, ["its compose file is not one this can read"], False
    if not isinstance(comp, dict) or not isinstance(comp.get("services"), dict) or len(comp["services"]) != 1:
        return None, ["its compose file is not one service"], False
    comp = json.loads(json.dumps(comp))
    (key, svc), = comp["services"].items()
    name = str(app.get("name") or key)
    notes = []
    auto = name in (read.get("autostart") or [])
    digest = (read.get("digests") or {}).get(name, "")
    if digest and "@sha256:" in digest:
        svc["image"] = digest
    else:
        notes.append(f"no exact image was read for it: {svc.get('image') or 'its image'} is pulled as the template names it")
    svc["restart"] = "unless-stopped" if auto else "no"
    fixed = svc.pop("x-fixed-network", None)
    if isinstance(fixed, dict) and fixed.get("name"):
        net = str(fixed["name"])
        comp["networks"] = {net: {"external": True}}
        svc["networks"] = {net: ({"ipv4_address": fixed["ip"]} if fixed.get("ip") else {})}
        svc.pop("ports", None)
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
    return comp, notes, auto


def plan(cfg, adopted):
    """Each app of the stick's plan as it would be made: [{name, slug,
    autostart, notes, network}]."""
    read = ((adopted or {}).get("apps") or {}).get("docker") or {}
    pools = [str(p.get("name")) for p in (cfg or {}).get("pools") or [] if isinstance(p, dict)]
    shares = {str(s.get("name")): s for s in (cfg or {}).get("shares") or [] if isinstance(s, dict)}
    writable = (adopted or {}).get("writable") is True
    out = []
    for app in (cfg or {}).get("apps") or []:
        if not isinstance(app, dict) or not NAME_RE.fullmatch(str(app.get("name") or "")):
            continue
        comp, notes, auto = compose_for(app, read, pools, writable, shares)
        net = ""
        if comp:
            svc = next(iter(comp["services"].values()))
            net = next(iter(svc.get("networks") or {}), "") or ("host" if svc.get("network_mode") == "host" else "bridge")
        out.append({"name": app["name"], "slug": slug_of(app["name"]), "autostart": auto, "notes": notes, "network": net, "ok": comp is not None})
    return out


def make(cfg, adopted, names, node):
    """The named apps made as containers on `node`, not started:
    {"made": [{name, slug, autostart, risks, ack}], "skipped": [{name, why}]}."""
    read = ((adopted or {}).get("apps") or {}).get("docker") or {}
    pools = [str(p.get("name")) for p in (cfg or {}).get("pools") or [] if isinstance(p, dict)]
    shares = {str(s.get("name")): s for s in (cfg or {}).get("shares") or [] if isinstance(s, dict)}
    writable = (adopted or {}).get("writable") is True
    want = set(names or [])
    made, skipped = [], []
    for app in (cfg or {}).get("apps") or []:
        if not isinstance(app, dict) or app.get("name") not in want:
            continue
        comp, notes, auto = compose_for(app, read, pools, writable, shares)
        if not comp:
            skipped.append({"name": app["name"], "why": "; ".join(notes)})
            continue
        slug = slug_of(app["name"])
        r = containers.create_container(slug, json.dumps(comp, indent=2) + "\n", node=node)
        if r.get("error"):
            skipped.append({"name": app["name"], "why": r["error"]})
            continue
        rs = devapp.risks(r["project"], devapp._config(r["project"], devapp.MAIN))
        made.append({"name": app["name"], "slug": r["project"], "autostart": auto, "notes": notes,
                     "risks": rs[:12], "ack": devapp.risk_digest(rs) if rs else ""})
    return {"made": made, "skipped": skipped}


def start(rows):
    """Each container named started, its risks acknowledged by the press that
    showed them: {"started": [slug], "failed": [{slug, why}]}."""
    started, failed = [], []
    for row in rows or []:
        if not isinstance(row, dict):
            continue
        slug = str(row.get("slug") or "")
        if not re.fullmatch(r"[a-z0-9][a-z0-9-]{0,39}", slug):
            continue
        r = devactions.up(slug, ack=str(row.get("ack") or ""))
        (failed.append({"slug": slug, "why": r["error"]}) if r.get("error") else started.append(slug))
    return {"started": started, "failed": failed}
