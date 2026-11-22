"""Apps a NAS runs (R164 step 2, R238): ready containers (a media server,
photos, files, home automation, a download client, syncing), each a
compose file and the fields its panel asks for (where its data and media
live, who it runs as, the time zone, its port), filled from the New
container dialog and made through the Containers page as any container
is: on the node picked, reached on its port, and put behind a node's nginx
with a certificate from that node's nginx page.

None is shipped in this file. An app is offered because the vetted
catalog's signed index lists it (R169, R238 step 1): its folder is fetched
at the commit the index pins and kept here (add_catalog), and an app is
added, fixed or re-pinned by a commit to the catalog, with no release of
AerieOS (refresh). Beside those, the apps a person added (R170 step 3,
the Library's Add your own): a compose file of their own, checked before
it is kept, held at tier sideloaded. Both are kept in sideapps.json under
the state. From pack format 5 an app names every image by its digest; one
of an earlier format pins each to a tag, never latest.
"""
import json
import os
import re
import sys
import time
from pathlib import Path

_lib = os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "lib")
if os.path.isdir(_lib) and _lib not in sys.path:
    sys.path.insert(0, _lib)
import markup  # noqa: E402
import packformat  # noqa: E402

FILE = None
write_json = None
ID_RE = re.compile(r"[a-z][a-z0-9-]{1,31}")
BLANKS = ("DATA", "MEDIA", "PUID", "PGID", "TZ", "PORT")
COMPOSE_MAX = 64 * 1024

# An app's own fields (R238 step 2, pack format 4): in place of the six
# blanks every app shared, bbapp.json declares what its form asks for,
# each a variable its compose reads. AerieOS's own four stay its own, drawn
# in the same words for every app whose compose reads them: who it runs as,
# the time zone, and the port it answers on.
OWN = ("PUID", "PGID", "TZ", "PORT")
FIELD_KINDS = ("folder", "port", "text", "secret", "choice", "switch", "router")
# A router field's address may end in a path the app's client wants (/v1).
ROUTE_PATH = re.compile(r"(/[\w.-]{1,40}){0,4}")
FIELDS_MAX, FIELDS_FORMAT = 16, 4
VAR_RE = re.compile(r"[A-Z][A-Z0-9_]{0,40}")
SUB_RE = re.compile(r"[\w.+-]{1,60}(/[\w.+-]{1,60}){0,5}")
# What a manifest with no fields (format 1 to 3) asks for: the two folders
# of the six blanks, each where its compose reads it.
LEGACY = {"DATA": {"var": "DATA", "kind": "folder", "label": "Its data", "default": "", "required": True,
                   "help": "its own folder on a pool or a share, which it keeps its settings and its databases in"},
          "MEDIA": {"var": "MEDIA", "kind": "folder", "label": "Its media or files", "default": "", "required": True,
                    "help": "the share's folder it serves or syncs"}}

TZ_RE = re.compile(r"[A-Za-z0-9_+-]{1,32}(/[A-Za-z0-9_+-]{1,32}){0,2}")
PATH_RE = re.compile(r"/(mnt|srv)/[\w./ +-]{1,180}")
IDS_RE = re.compile(r"[0-9]{1,6}:[0-9]{1,6}")

answers_fn = None      # (node, port) -> True when something on the node already answers there


def configure(*, state, write_json, answers=None):
    globals().update(FILE=Path(state) / "sideapps.json", write_json=write_json, answers_fn=answers)


# What New container calls AerieOS's own fields, so a refusal names the one
# that sets a variable.
OWN_LABELS = {"PUID": "Runs as", "PGID": "Runs as", "TZ": "Time zone", "PORT": "Its port"}


def extra_env(a, text):
    """The other variables a person typed for an app (its Environment tab):
    (text, why). One the app's panel sets is refused by name, so a value is
    set in one place and never two (R238 step 3)."""
    mine, own = (a.get("fields"), a.get("own")) if "own" in a else app_fields(a)
    taken = {f["var"]: f["label"] for f in mine} | {f["key"]: f["label"] for f in mine if f.get("key")} | {v: OWN_LABELS[v] for v in own}
    lines = [ln for ln in str(text or "").splitlines() if ln.strip()]
    for ln in lines:
        k = ln.partition("=")[0].strip()
        if k in taken:
            return "", f"{k} is set in {a.get('name') or 'the app'}'s fields above, as {taken[k]}: change it there"
    return ("\n".join(lines) + "\n") if lines else "", ""


def ports_taken(a, values, node, keep=None, held=()):
    """Of the ports an app would publish on `node` (its port and each port
    field), the ones something there already answers on, asked from here,
    or another container made there holds (`held`); a port the container
    already had (`keep`) is its own and not asked. Two of its own fields on
    one port are one taken too."""
    keep = keep if isinstance(keep, dict) else {}
    held = {int(p) for p in held}
    mine, own = (a.get("fields"), a.get("own")) if "own" in a else app_fields(a)
    want = [v for v in [*(f["var"] for f in mine if f["kind"] == "port"), *(["PORT"] if "PORT" in own else [])] if values.get(v)]
    seen, out = set(), []
    for v in want:
        p = str(values[v])
        if p in seen:
            out.append(int(p))
        seen.add(p)
        if keep.get(v) != p and (int(p) in held or answers_fn and answers_fn(node, int(p))):
            out.append(int(p))
    return sorted(set(out))


def snapshot(a):
    """What a container made from an app keeps of it beside its compose
    file (R238 step 3): which app, at which pin, and the fields it was made
    with, so Configure opens on them whatever the Library holds later."""
    keys = ("id", "name", "maker", "tier", "fields", "own", "network", "port", "commit", "at")
    return {k: a.get(k) for k in keys if k in a}


def _load():
    """{id: record} of the apps a person added; {} with no file."""
    try:
        d = json.loads(FILE.read_text()) if FILE else {}
    except (OSError, ValueError):
        return {}
    apps = d.get("apps") if isinstance(d, dict) else None
    return {k: v for k, v in (apps or {}).items() if isinstance(v, dict) and v.get("compose")}


def _save(apps):
    write_json(FILE, {"apps": apps})


def _all():
    """Every app kept here, each with its tier: a person's own as
    sideloaded, one taken from the catalog at the tier its entry said."""
    return {k: {**v, "tier": v["tier"] if v.get("pin") and v.get("tier") in packformat.TIERS else "sideloaded"} for k, v in _load().items()}


def catalog():
    """The list the dialog and the Library show: [{id, name, what, port,
    media, secrets, tier, by, at, icon, fields, own, network, going,
    commit, compose, held}], `icon` the address of its own picture when it has
    one (R182), `fields` what its panel asks for and `own` which of
    AerieOS's own it asks for too (R238)."""
    out = []
    for k, v in _all().items():
        mine, own = app_fields({**v, "id": k})
        out.append({"id": k, "name": v["name"], "what": v["what"], "port": v["port"], "media": v.get("media", False),
                    "secrets": v.get("secrets", []) or [f["var"] for f in mine if f["kind"] == "secret"],
                    "tier": v["tier"], "by": v.get("by", ""), "at": v.get("at", 0),
                    # Who the app itself is by (the operator, 12 Nov), where it says.
                    "maker": str(v.get("maker") or ""), "credits": list(v.get("credits") or []),
                    "icon": f"/api/pack-icon?app={k}&v={v.get('at', 0)}" if icon_of(k) else "",
                    "fields": mine, "own": own, "network": v.get("network", ""), "going": v.get("going", ""),
                    "commit": str((v.get("pin") or {}).get("commit") or ""), "compose": v["compose"],
                    # What its images are held to: pinned when every one has its digest.
                    "held": held_of(v)})
    return out


# An app's own icon (R182): the file bbapp.json names in the catalog's
# folder, checked as a pack's is (toolpacks.icon_refused), kept under the
# state by the app's id and served as an image alone.
def _icon_dir():
    return Path(FILE).parent / "app-icons" if FILE else None


def keep_icon(app, raw=None, ext=""):
    """The app's icon kept, or taken away with no bytes: its type, or ""."""
    import toolpacks  # noqa: PLC0415
    d = _icon_dir()
    if not d or not ID_RE.fullmatch(str(app or "")):
        return ""
    for e in toolpacks.ICON_TYPES:
        (d / f"{app}.{e}").unlink(missing_ok=True)
    if not raw or ext not in toolpacks.ICON_TYPES or toolpacks.icon_refused(raw, ext):
        return ""
    d.mkdir(parents=True, exist_ok=True)
    tmp = d / f".{app}.{ext}.new"
    tmp.write_bytes(raw)
    tmp.replace(d / f"{app}.{ext}")
    return ext


def icon_of(app):
    """(bytes, content type) of an app's kept icon, or None."""
    import toolpacks  # noqa: PLC0415
    d = _icon_dir()
    if not d or not ID_RE.fullmatch(str(app or "")):
        return None
    for e, ct in toolpacks.ICON_TYPES.items():
        f = d / f"{app}.{e}"
        if f.is_file():
            try:
                return f.read_bytes(), ct
            except OSError:
                return None
    return None


def source(app):
    """One added app as kept, for Edit: {id, name, what, port, media, compose} or {error}."""
    a = _load().get(str(app or ""))
    if not a:
        return {"error": f"no app called {app or 'nothing'} was added here"}
    return {"id": app, "name": a["name"], "what": a["what"], "port": a["port"], "media": bool(a.get("media")), "compose": a["compose"]}


def fields_of(raw, errors):
    """An app's own fields as bbapp.json declares them (pack format 4),
    checked and cut to what New container reads: [{var, kind, label, help,
    default, example, required, choices}], the errors said in `errors`.
    A folder's default is a folder under the pool or share picked (as
    apps/immich), a port's a number, a switch's true or false, a choice's
    one of its values; a secret has none, being made for it once."""
    if not isinstance(raw, list) or not 1 <= len(raw) <= FIELDS_MAX:
        errors.append(f"fields is a list of 1 to {FIELDS_MAX} fields, each {{var, label, kind}}")
        return []
    out, seen = [], set()
    for f in raw:
        if not isinstance(f, dict):
            errors.append("a field is an object: {var, label, kind}")
            continue
        var, kind = str(f.get("var") or ""), str(f.get("kind") or "")
        if not VAR_RE.fullmatch(var) or var in seen:
            errors.append(f"field {var or '(unnamed)'}: var is the variable it fills, of A-Z, 0-9 and _, starting with a letter, and once")
            continue
        seen.add(var)
        if var in OWN:
            errors.append(f"field {var}: {var} is one of AerieOS's own ({', '.join(OWN)}), which New container asks for in the same words for every app")
            continue
        if kind not in FIELD_KINDS:
            errors.append(f"field {var}: kind is one of {', '.join(FIELD_KINDS)}")
            continue
        label = " ".join(str(f.get("label") or "").split())
        if not 1 <= len(label) <= 60 or not label.isprintable():
            errors.append(f"field {var}: label is what the form calls it, one line of 1 to 60 characters")
            continue
        out_f = {"var": var, "kind": kind, "label": label, "help": " ".join(str(f.get("help") or "").split())[:200],
                 "required": kind in ("folder", "port") or f.get("required") is True}
        d = f.get("default")
        if kind == "folder":
            d = str(d or "").strip("/")
            if d and (not SUB_RE.fullmatch(d) or ".." in d.split("/")):
                errors.append(f"field {var}: a folder's default is a folder under the pool or share picked, as apps/{var.lower()}")
                continue
        elif kind == "port":
            if not (isinstance(d, int) and not isinstance(d, bool) and 1 <= d <= 65535):
                errors.append(f"field {var}: a port's default is the number it answers on, 1 to 65535")
                continue
        elif kind == "switch":
            d = d is True
        elif kind == "choice":
            ch = f.get("choices")
            if not isinstance(ch, list) or not 2 <= len(ch) <= 24 or not all(isinstance(x, dict) and VALUE_RE.fullmatch(str(x.get("value") or "")) for x in ch):
                errors.append(f"field {var}: choices lists 2 to 24 of {{value, label}}, each value one line")
                continue
            out_f["choices"] = [{"value": str(x["value"]), "label": " ".join(str(x.get("label") or x["value"]).split())[:60]} for x in ch]
            d = str(d) if str(d or "") in [c["value"] for c in out_f["choices"]] else out_f["choices"][0]["value"]
        elif kind == "secret":
            d = ""
        elif kind == "router":
            # The model router (R238 step 7): its address in `var`, a key of
            # the container's own in `key`, the router picked on the panel.
            key, path = str(f.get("key") or ""), str(f.get("path") or "")
            if not VAR_RE.fullmatch(key) or key in OWN or key == var or key in seen:
                errors.append(f"field {var}: a router field names the variable its key fills in key, another of A-Z, 0-9 and _")
                continue
            if not ROUTE_PATH.fullmatch(path):
                errors.append(f"field {var}: path is what the app's client adds to the router's address, as /v1")
                continue
            seen.add(key)
            out_f.update(key=key, **({"path": path} if path else {}))
            d = ""
        else:
            d = str(d or "")
            if not VALUE_RE.fullmatch(d) and d:
                errors.append(f"field {var}: a default is one line of up to 200 characters")
                continue
        out_f["default"] = d
        ex = " ".join(str(f.get("example") or "").split())[:120]
        if ex and kind in ("folder", "text"):
            out_f["example"] = ex
        out.append(out_f)
    return out


# A value a field holds in the environment: one line, nothing compose would
# read as another variable.
VALUE_RE = re.compile(r"[^\n\r$]{1,200}")


def app_fields(a, blanks=None):
    """What New container asks for one app, as a record or a check kept it:
    (its own fields, AerieOS's own its compose reads). A record from before
    format 4 asks for the folders of the six blanks its compose reads."""
    used = set(blanks if blanks is not None else re.findall(r"\$\{([A-Za-z_][A-Za-z0-9_]*)\}", str(a.get("compose") or "")))
    if isinstance(a.get("fields"), list):
        mine = [dict(f) for f in a["fields"]]
    else:
        mine = [dict(LEGACY[v], default=f"apps/{a.get('id') or ''}".rstrip("/") if v == "DATA" else "") for v in ("DATA", "MEDIA") if v in used]
    return mine, [v for v in OWN if v in used]


def check_app(meta, compose):
    """An app's folder as the catalog holds it, bbapp.json and its compose,
    checked as an install keeps it: check()'s answer with the app's own
    fields, `network` and `going`, or {error}. What came with pack format
    4 (fields, network, going) is refused in a manifest that says an
    earlier one, since an install that reads only that would not run it."""
    meta = meta if isinstance(meta, dict) else {}
    fmt = packformat.of(meta) or 1
    errors, fields = [], None
    for key in ("fields", "network", "going"):
        if meta.get(key) is not None and fmt < FIELDS_FORMAT:
            return {"error": f'{key} is pack format {FIELDS_FORMAT}\'s: the manifest says "format": {FIELDS_FORMAT}'}
    if meta.get("fields") is not None:
        fields = fields_of(meta["fields"], errors)
    network = meta.get("network") or ""
    if network not in ("", "host"):
        errors.append('network is "host", the machine\'s own network, or left out')
    # The card and New container keep 200 characters of it, as a person's
    # own app is held to; said here, where the catalog's check hears it,
    # rather than cut mid-word on the card (B932).
    if len(" ".join(str(meta.get("about") or "").split())) > 200:
        errors.append("about says what the app is in a line of up to 200 characters")
    going = " ".join(str(meta.get("going") or "").split())
    if meta.get("going") is not None and not 1 <= len(going) <= 200:
        errors.append("going says, in a line of up to 200 characters, that the app is going and what to install in its place")
    if errors:
        return {"error": errors[0]}
    seen = check(compose, fields, network)
    if seen.get("error"):
        return seen
    # From format 5 an app names every image by its digest: what a node
    # pulls is then what its entry carries, whatever the tag serves later.
    # An app of an earlier format means what it meant, held to its tags.
    if fmt >= packformat.HELD_FORMAT:
        loose = next((s for s in seen["services"] if not packformat.image_digest(s["image"])), None)
        if loose:
            return {"error": f"service {loose['name']}: {loose['image']} names no digest: a pack format {packformat.HELD_FORMAT} app names every image "
                             "as name:tag@sha256: and the 64 hex digits of its digest"}
    return {**seen, **({"fields": fields} if fields is not None else {}), **({"network": network} if network else {}),
            **({"going": going} if going else {})}


def held_of(a):
    """What an app's images are held to, as an API answers it: {word,
    why}, pinned only when every image its compose names carries its
    digest (packformat.images_held)."""
    word, why = packformat.images_held(packformat.compose_images(a.get("compose") if isinstance(a, dict) else ""))
    return {"word": word, "why": why}


# What a compose file here does not use, since each lets a file say one thing
# to the reader this check and Look read it with and another to Docker: an
# anchor or an alias (&name, *name), a merge key (<<), a tag (!name), and a
# mapping written in braces. A value that begins with one of those marks and
# is not quoted is the mark; ${NAME} is a blank, not a mapping.
COMPOSE_MARK = re.compile(r"""(?mx)
    (?: ^[ \t]* | :[ \t]+ | -[ \t]+ | [\[,][ \t]* )     # where a key or a value begins
    (?: [&*][A-Za-z0-9_.-] | ![A-Za-z!<] | \{ | <<[ \t]*: )""")


def compose_marked(text):
    """Why a compose file is not written plainly enough to be held to what
    Look shows, or "": the first line that uses one of COMPOSE_MARK's forms
    outside a comment."""
    for n, line in enumerate(str(text).splitlines(), 1):
        if COMPOSE_MARK.search(re.sub(r"(^|[ \t])#.*$", "", line)):
            return f"line {n} uses an anchor, an alias, a merge key, a tag or a mapping in braces: write it out plainly"
    return ""


def compose_plain(text, services):
    """...and why its images are not, or "": every image its services name
    is on an `image:` line of its own, so the images this check read are
    the ones an Update moves and the card's word is read from
    (packformat.compose_images)."""
    named = sorted({str(svc.get("image") or "") for svc in services.values() if isinstance(svc, dict)})
    if named != sorted(packformat.compose_images(text)):
        return "every service names its image on a line of its own (image: name:tag@sha256:...)"
    return ""


# The keys an app's compose may use, each one that reaches nothing of the
# host past what Look shows (its image, ports and volumes): a key Docker
# reads that is not here is refused rather than passed unread, since a
# check that knows `privileged` and not `cap_add`, `devices`, `extends` or
# `include` holds nothing. What service_reach reads on a key that is here
# (a network or a profile that reaches out) is refused by its own words.
SERVICE_KEYS = frozenset((
    "image", "command", "entrypoint", "environment", "ports", "expose", "volumes", "tmpfs", "restart", "user",
    "working_dir", "depends_on", "healthcheck", "init", "network_mode", "networks", "hostname", "domainname",
    "dns", "dns_search", "extra_hosts", "labels", "container_name", "stop_signal", "stop_grace_period", "tty",
    "stdin_open", "read_only", "shm_size", "mem_limit", "mem_reservation", "memswap_limit", "cpus", "cpu_shares",
    "pids_limit", "ulimits", "cap_drop", "security_opt", "platform", "pull_policy"))
# The one security option an app may set: the one that takes privileges away.
OWN_SECURITY = ("no-new-privileges", "no-new-privileges:true", "no-new-privileges=true")
# A file's own top level: its services, the named volumes and networks
# they use, and the x- blocks Docker leaves unread (`version` too, which
# it reads as nothing). A named volume or network is the app's own: one
# that is another's (external, a name of its own) or a host path by
# another name (a driver's options) is refused.
TOP_KEYS = frozenset(("services", "volumes", "networks", "version"))
VOLUME_KEYS, NETWORK_KEYS = frozenset(("labels",)), frozenset(("labels", "internal", "enable_ipv6"))
OWN_DRIVERS = {"volumes": ("local",), "networks": ("bridge",)}


def compose_keys_refused(doc):
    """Why a compose file's top level, or a named volume or network it
    declares, reaches past the app, or ""."""
    for key in doc:
        if str(key) not in TOP_KEYS and not str(key).startswith("x-"):
            return f"{key} is not a key an app's compose uses here"
    for kind, keys in (("volumes", VOLUME_KEYS), ("networks", NETWORK_KEYS)):
        named = doc.get(kind)
        if named is None:
            continue
        if not isinstance(named, dict):
            return f"{kind} is a mapping of the app's own named {kind}"
        for name, item in named.items():
            item = item if item is not None else {}
            if not isinstance(item, dict):
                return f"{kind[:-1]} {name} is declared as a mapping"
            odd = next((k for k in item if k not in keys and k != "driver"), None)
            if odd:
                return f"{kind[:-1]} {name}: {odd} is not a key an app's compose uses here"
            if str(item.get("driver") or OWN_DRIVERS[kind][0]) not in OWN_DRIVERS[kind]:
                return f"{kind[:-1]} {name}: its driver is {OWN_DRIVERS[kind][0]}, the app's own"
    return ""


def check(compose, fields=None, network=""):
    """What a compose file of a person's own would run, before it is kept
    (the Look): {services: [{name, image, ports, volumes}], blanks, media}
    or {error}. Held to what the catalog's are held to: a services
    mapping, every image held by its digest or pinned to a tag that is not
    latest, and no blank
    but the ones New container fills: the six every app shared, or, for an
    app that declares its own `fields` (pack format 4), those and AerieOS's
    own, each declared one read. `network` "host" is an app on the
    machine's own network: every service says so, publishes nothing, and
    answers on its own port, so no ${PORT}."""
    text = str(compose or "")
    if not text.strip():
        return {"error": "paste the app's compose file"}
    if len(text.encode("utf-8")) > COMPOSE_MAX:
        return {"error": f"a compose file is {COMPOSE_MAX // 1024} KB at most"}
    why = compose_marked(text)
    if why:
        return {"error": why}
    try:
        doc = markup.yaml_load(text)
    except Exception as e:  # noqa: BLE001 (the reader's own word is the reason)
        return {"error": f"not a compose file: {e}"}
    services = doc.get("services") if isinstance(doc, dict) else None
    if not isinstance(services, dict) or not services:
        return {"error": "a compose file has a services mapping with at least one service"}
    why = compose_keys_refused(doc)
    if why:
        return {"error": why}
    out = []
    for name, svc in services.items():
        svc = svc if isinstance(svc, dict) else {}
        image = str(svc.get("image") or "")
        if not image:
            return {"error": f"service {name} names an image"}
        # Held by its digest (name:tag@sha256:...), which is then what is
        # pulled and run, or by a tag that is not latest.
        why = packformat.image_refused(image)
        if why:
            return {"error": f"service {name}: {image} {why}"}
        if "build" in svc:
            return {"error": f"service {name}: an app from the catalog is a pulled image, never built here"}
        # What it asks of the host, by the reader a dev instance's warnings
        # use; the machine's own network alone is the app's to say (below).
        reach = [phrase for key, phrase in packformat.service_reach(str(name), svc)
                 if not (key == "network_mode" and str(svc.get(key)) == "host")]
        if reach:
            return {"error": f"service {reach[0]}"}
        odd = sorted(str(k) for k in svc if str(k) not in SERVICE_KEYS and not str(k).startswith("x-"))
        if odd:
            return {"error": f"service {name}: {odd[0]} is not a key an app's compose uses here"}
        opts = svc.get("security_opt") if isinstance(svc.get("security_opt"), list) else [svc.get("security_opt")] if "security_opt" in svc else []
        if any(str(o) not in OWN_SECURITY for o in opts):
            return {"error": f"service {name}: no-new-privileges is the one security option an app sets"}
        # Its own network, none, or the machine's: never another's by its name.
        if "network_mode" in svc and str(svc.get("network_mode")) not in ("host", "bridge", "none"):
            return {"error": f"service {name}: network_mode is host, bridge or none, and its own networks are named under networks"}
        ports = svc.get("ports") if isinstance(svc.get("ports"), list) else []
        vols = svc.get("volumes") if isinstance(svc.get("volumes"), list) else []
        if network == "host" and (svc.get("network_mode") != "host" or ports):
            return {"error": f"service {name}: an app on the machine's own network (network: host) says network_mode: host on every service and publishes no ports"}
        if fields is not None and network != "host" and svc.get("network_mode") == "host":
            return {"error": f"service {name}: network_mode: host is said in bbapp.json too (\"network\": \"host\"), so its card says it"}
        out.append({"name": str(name), "image": image, "ports": [str(p) for p in ports], "volumes": [str(v) for v in vols]})
    why = compose_plain(text, services)
    if why:
        return {"error": why}
    blanks = sorted(set(re.findall(r"\$\{([A-Za-z_][A-Za-z0-9_]*)\}", text)))
    if fields is None:
        odd = [b for b in blanks if b not in BLANKS]
        if odd:
            return {"error": f"unknown blank {', '.join(odd)}: the blanks New container fills are {', '.join(BLANKS)}"}
    else:
        mine = [v for f in fields for v in (f["var"], f.get("key")) if v]
        odd = [b for b in blanks if b not in mine and b not in OWN]
        if odd:
            return {"error": f"unknown blank {', '.join(odd)}: a blank is one of the app's own fields ({', '.join(mine) or 'none'}) "
                             f"or AerieOS's own ({', '.join(OWN)})"}
        unread = [v for v in mine if v not in blanks]
        if unread:
            return {"error": f"field {', '.join(unread)} is declared and compose.yml never reads it"}
    if network == "host":
        if "PORT" in blanks:
            return {"error": "an app on the machine's own network answers on its own port, so ${PORT} is not filled: name that port in bbapp.json's port"}
    elif "PORT" not in blanks:
        return {"error": "the app answers on ${PORT}: New container fills it with the port you pick"}
    return {"services": out, "blanks": blanks, "media": "MEDIA" in blanks}


def add(app, name, what, port, compose, by="", replace=False):
    """Keep an app of a person's own, looked at first (check): {app} or
    {error}. `replace` takes a new version of one added before."""
    app = str(app or "").strip().lower()
    if not ID_RE.fullmatch(app):
        return {"error": "an app's id is 2 to 32 lower-case letters, digits and dashes, starting with a letter"}
    name, what = str(name or "").strip(), str(what or "").strip()
    if not 1 <= len(name) <= 60:
        return {"error": "its name is 1 to 60 characters"}
    if not 1 <= len(what) <= 200:
        return {"error": "what it is, in a line of 200 characters at most"}
    try:
        port = int(port)
    except (TypeError, ValueError):
        return {"error": "a port is a number"}
    if not 1 <= port <= 65535:
        return {"error": "a port is 1 to 65535"}
    seen = check(compose)
    if seen.get("error"):
        return seen
    apps = _load()
    if app in apps and not replace:
        return {"error": f"{app} was added already: open it from its row to change it"}
    apps[app] = {"name": name, "what": what, "port": port, "media": seen["media"], "compose": str(compose), "secrets": [],
                 "by": str(by or ""), "at": int(time.time())}
    _save(apps)
    return {"app": app, "replaced": app in apps and replace, **{k: v for k, v in seen.items()}}


def add_catalog(entry, by="", fetch=None):
    """Keep an app the vetted catalog offers (R170 step 7): its folder at the
    commit the signed index pins, bbapp.json and compose.yml read from it and
    the compose held to what a person's own is held to, kept with the
    entry's tier and pin so New container offers it. `entry` is the index's,
    never the page's. {app} or {error}."""
    if not entry or entry.get("kind") != "app":
        return {"error": "no app by that name in the catalog"}
    # One written in a format this build has not met is not fetched (R234).
    past = packformat.too_new(packformat.of(entry) or 1)
    if past:
        return {"error": f"{entry['name']} {past}"}
    got = fetch(entry["url"], entry["commit"], entry["sha256"], entry.get("path", ""), ("bbapp.json", "compose.yml"))
    if got.get("error"):
        return got
    try:
        meta = json.loads(got["files"]["bbapp.json"].decode("utf-8"))
        compose = got["files"]["compose.yml"].decode("utf-8")
    except (ValueError, UnicodeDecodeError, KeyError):
        return {"error": f"{entry['name']}'s bbapp.json is not JSON"}
    app = entry["name"]
    # The format the manifest itself says it needs, held as the entry's was.
    fmt = packformat.of(meta)
    if fmt is None or packformat.too_new(fmt):
        return {"error": f"{app}'s bbapp.json says a format that is no number" if fmt is None else f"{app} {packformat.too_new(fmt)}"}
    # ...and what it uses is in the framework version it says (R234 step 7).
    late = packformat.needs(meta, packformat.uses_of(meta))
    if late:
        return {"error": f"{app}'s bbapp.json: {late[0]}"}
    seen = check_app(meta, compose)
    if seen.get("error"):
        return {"error": f"{app}: {seen['error']}"}
    try:
        port = int(meta.get("port"))
    except (TypeError, ValueError):
        return {"error": f"{app}'s bbapp.json names no port"}
    # Its own icon, when bbapp.json names one in its folder (R182): read at
    # the same pin and under the same sha256, refused whole when it is not
    # the image its name says.
    import toolpacks  # noqa: PLC0415
    ic = str(meta.get("icon") or "")
    if ic:
        ext = ic.rsplit(".", 1)[-1].lower()
        if not (toolpacks.REL.fullmatch(ic) and ext in toolpacks.ICON_TYPES):
            return {"error": f"{app}'s bbapp.json names {ic} as its icon: a PNG, WebP or SVG file in its folder"}
        g = fetch(entry["url"], entry["commit"], entry["sha256"], entry.get("path", ""), (ic,), cap=toolpacks.ICON_MAX)
        if g.get("error"):
            return {"error": f"{app}'s icon: {g['error']}"}
        why = toolpacks.icon_refused(g["files"][ic], ext)
        if why:
            return {"error": f"{app}'s icon {ic}: {why}"}
        keep_icon(app, g["files"][ic], ext)
    else:
        keep_icon(app)
    apps = _load()
    apps[app] = {"name": str(meta.get("label") or app)[:60], "what": str(meta.get("about") or entry.get("about") or "")[:200], "port": port,
                 "media": seen["media"], "compose": compose, "secrets": [], "by": str(by or ""), "at": int(time.time()),
                 "tier": packformat.tier_of(entry.get("tier")),
                 # Who it is by, its own fields, the network it runs on and
                 # whether it is going (R238), as its manifest says them.
                 "maker": packformat.maker_of(meta), "credits": packformat.credits_of(meta),
                 **{k: seen[k] for k in ("fields", "network", "going") if k in seen},
                 "pin": {k: entry[k] for k in ("url", "commit", "sha256")} | {"path": entry.get("path", "")}}
    _save(apps)
    return {"app": app, **seen}


# A kept app's newer definition (R238): an app is fixed or re-pinned by a
# commit to the catalog, and the signed index then pins that commit. One
# kept here from the same repository and folder takes it, fetched and held
# as its first keep was, so a container made from it is offered the images
# its entry names now (containers.entry_moved).
RETRY_S = 3600
_trying = {}           # {(app, commit): when it was last tried}, so one that fails is asked again in an hour, not on every read


def wanted(index):
    """[(app, entry)] for the kept apps the signed index pins another
    commit of: an app entry of the same repository and folder, not
    withdrawn, in a format this build reads. The pin compared is the one
    this build takes (packformat.taken): an app kept from an entry's older
    pin is as its entry pins it for as long as this build reads no newer."""
    mine, out = _load(), []
    for e in packformat.taken(index):
        pin = (mine.get(e.get("name")) or {}).get("pin") or {}
        if e.get("kind") != "app" or e.get("withdrawn") or not pin or pin.get("commit") == e.get("commit"):
            continue
        if (pin.get("url"), pin.get("path", "")) != (e.get("url"), e.get("path", "")) or packformat.too_new(packformat.of(e) or 1):
            continue
        out.append((e["name"], e))
    return out


def refresh(index, fetch):
    """Take the catalog's newer definition of each kept app the index pins
    another commit of: [(app, "" or why it was not taken)], nothing when
    nothing was wanted. Who kept it stays who kept it."""
    said = []
    for app, e in wanted(index):
        key = (app, e["commit"])
        if time.time() - _trying.get(key, 0) < RETRY_S:
            continue
        _trying[key] = time.time()
        r = add_catalog(e, by=str((_load().get(app) or {}).get("by") or ""), fetch=fetch)
        said.append((app, r.get("error", "")))
    return said


def remove(app):
    """Drop an added app: {ok} or {error}. A container made from it stays
    what it is, its own compose file kept with it."""
    apps = _load()
    if app not in apps:
        return {"error": f"no app called {app or 'nothing'} was added here"}
    del apps[app]
    _save(apps)
    keep_icon(app)
    return {"ok": True}


def env_values(text):
    """{NAME: value} of an environment file's lines, the last of a name
    standing; a line that is no NAME=value is left out."""
    out = {}
    for ln in str(text or "").splitlines():
        k, eq, v = ln.partition("=")
        if eq and VAR_RE.fullmatch(k.strip()):
            out[k.strip()] = v
    return out


def render_with(a, values=None, ids="1000:1000", tz="UTC", port=None, keep=None, router=None):
    """The environment for one app's record `a` (as catalog() reads it, or
    a container's own copy of it) with its fields filled: {env, values} or
    {error}. `values` is {VAR: what the form holds}; `keep` the values the
    container already has, so a secret is made once and never again on an
    edit, and a field the panel left empty keeps what it had. The
    environment is where the choices live, so the file stays the catalog's.
    `router` is (node) -> {url, key} or {error}: the container's own key at
    that node's model router, for a router field."""
    import secrets as _secrets
    values = values if isinstance(values, dict) else {}
    keep = keep if isinstance(keep, dict) else {}
    mine, own = (a.get("fields"), a.get("own")) if "own" in a else app_fields(a)
    env, got = [], {}
    for f in mine:
        var, kind = f["var"], f["kind"]
        # What the panel sent; else what the container has; else, for a
        # field that is not a folder, its default (a field a newer
        # definition added, on an edit).
        v = values[var] if var in values else keep[var] if var in keep else f.get("default") if kind != "folder" else ""
        v = ("true" if v else "false") if isinstance(v, bool) else str(v if v is not None else "").strip()
        if kind == "secret":
            v = v or keep.get(var) or _secrets.token_urlsafe(18)
        elif kind == "folder":
            v = v.rstrip("/")
            if not PATH_RE.fullmatch(v) or ".." in v.split("/"):
                return {"error": f"{f['label']} is a folder under /mnt (a pool, the array, a share) or /srv"}
        elif kind == "port":
            try:
                p = int(v)
            except ValueError:
                return {"error": f"{f['label']} is a port, a number"}
            if not 1 <= p <= 65535:
                return {"error": f"{f['label']} is a port, 1 to 65535"}
            v = str(p)
        elif kind == "switch":
            v = "true" if v.lower() in ("true", "1", "on", "yes") else "false"
        elif kind == "router":
            # The node whose router it uses, or none: the address and a key
            # of its own filled in from that router.
            if not v:
                if f.get("required"):
                    return {"error": f"{f['label']} is needed: pick the model router it uses"}
                env += [f"{var}=", f"{f['key']}="]
                got.update({var: "", f["key"]: ""})
                continue
            r = router(v) if router else {"error": "no model router is reached from here"}
            if r.get("error"):
                return {"error": f"{f['label']}: {r['error']}"}
            env += [f"{var}={r['url']}{f.get('path', '')}", f"{f['key']}={r['key']}"]
            got.update({var: r["url"] + f.get("path", ""), f["key"]: r["key"]})
            continue
        elif kind == "choice":
            ch = [c for c in f.get("choices") or [] if isinstance(c, dict)]
            if v not in [c.get("value") for c in ch]:
                return {"error": f"{f['label']} is one of {', '.join(str(c.get('label')) for c in ch)}"}
        elif not v and f.get("required"):
            return {"error": f"{f['label']} is needed"}
        if v and not VALUE_RE.fullmatch(v):
            return {"error": f"{f['label']} is one line, 200 characters at most"}
        env.append(f"{var}={v}")
        got[var] = v
    if "PUID" in own or "PGID" in own:
        if not IDS_RE.fullmatch(str(ids or "")):
            return {"error": "the user it runs as is uid:gid, two numbers"}
        uid, gid = ids.split(":")
        env += [f"PUID={uid}", f"PGID={gid}"]
        got.update(PUID=uid, PGID=gid)
    if "TZ" in own:
        if not TZ_RE.fullmatch(str(tz or "")):
            return {"error": "a time zone is named as Region/City"}
        env.append(f"TZ={tz}")
        got["TZ"] = tz
    if "PORT" in own:
        try:
            port = int(port if port not in (None, "") else a["port"])
        except (TypeError, ValueError):
            return {"error": "a port is a number"}
        if not 1 <= port <= 65535:
            return {"error": "a port is 1 to 65535"}
        env.append(f"PORT={port}")
        got["PORT"] = str(port)
    # The secrets a record from before format 4 names, made as a secret field is.
    for k in a.get("secrets") or []:
        if k in got:
            continue
        v = str(values.get(k) or keep.get(k) or _secrets.token_urlsafe(18))
        if not VALUE_RE.fullmatch(v):
            return {"error": f"{k} is one line, 200 characters at most"}
        env.append(f"{k}={v}")
        got[k] = v
    return {"env": "\n".join(env) + "\n", "values": got}


def render(app, values=None, ids="1000:1000", tz="UTC", port=None, keep=None):
    """The compose and the environment for one app with its fields filled:
    {name, compose, env, values} or {error}; render_with's words."""
    a = next((x for x in catalog() if x["id"] == str(app or "")), None)
    if not a:
        return {"error": f"no app called {app or 'nothing'} in the catalog"}
    r = render_with(a, values, ids, tz, port, keep)
    return r if r.get("error") else {"name": app, "compose": a["compose"], **r}
