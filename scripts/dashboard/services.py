"""AerieOS's own services on a node, as one table (R172, R264).

A service is a deployed thing of AerieOS's that the Library lists as an
official pack: the model router (router.py), nginx (nginxproxy.py) and the
Scanners (scanners.py). Each is named here once, what differs between them
as plain data, and every list of them reads this table: the kinds a pack's
service block may name (toolpacks.SERVICES), the packs written under
packs/services (tools/packs-export.py), which of a node's System containers
is whose (containers.manager_view), and the Library's rows with its Install
and Remove (server.py). None asks a registry what is newest: each runs the
images its entry names by digest (images, below), and a newer one arrives
as a change to that entry.

A service's module answers by the same names as the others, which is all
this file asks of it:

  pack()                     its Library entry, a manifest, with the
                             images it runs (entry, below)
  container_name(nid)        the name its containers go by on that node
  service_deployed(nid)      whether it is on that node
  service_install(nid, by)   Install on its card: {ok, ...} or {error}
  service_remove(nid, by)    Remove on its card, the same
  REMOVES                    what Remove takes and what it leaves, said
                             before the press is confirmed; "" leaves the
                             page's own words
  service_row(nid)           where it has more to say on its row than
                             whether it is deployed: the keys it sets
  service_update(nid, by)    where its Update is its Containers row's:
                             its compose file written again with the images
                             its entry names now, and rebuilt

The modules are imported when first asked for and never as this one loads:
toolpacks reads the table while it loads, and each service's module reads
its images from here.
"""
import importlib
import json
import os

import packformat
import seams

# kind (a pack's service.kind) -> the module that is the service; the grant
# on a node that its Library row comes to (the server's Install and Remove
# name the same one in their own gates); and whether its settings are a
# page of its own, so the Library only installs and removes it. The order
# is the one every list of them keeps.
TABLE = {
    "router": {"module": "router", "grant": "configure", "page": False},
    "nginx": {"module": "nginxproxy", "grant": "docker-write", "page": True},
    "scanners": {"module": "scanners", "grant": "docker-write", "page": True},
}
KINDS = tuple(TABLE)

# The images each service runs, by its pack's name: the one copy, a file
# beside this one that tools/pins.py moves. Each is named by its tag and
# the digest of what is pulled, and a service's module reads its own by
# the names the file gives them: nothing of an image is a constant in code.
# The seam BB_SERVICE_IMAGES_FILE names another file, for the harness alone
# (seams.py: honored beside its marker), and the file is read again when it
# changes.
IMAGES_FILE = seams.get("BB_SERVICE_IMAGES_FILE") or os.path.join(os.path.dirname(os.path.abspath(__file__)), "service-images.json")
_images = {"at": None, "rows": {}}


def images(name):
    """{key: reference} for the images the service whose pack is `name`
    runs, each name:tag@sha256:...; {} for a name the file has no row for,
    or a row that is not what the format takes."""
    try:
        at = os.stat(IMAGES_FILE).st_mtime_ns
    except OSError:
        at = 0
    if _images["at"] != at:
        try:
            with open(IMAGES_FILE, encoding="utf-8") as f:
                rows = json.load(f)["services"]
        except (OSError, ValueError, KeyError, TypeError):
            rows = []
        _images.update(at=at, rows={r["name"]: packformat.images_checked(r.get("images"))[0] for r in (rows if isinstance(rows, list) else [])
                                    if isinstance(r, dict) and isinstance(r.get("name"), str)})
    return dict(_images["rows"].get(name) or {})


def entry(m):
    """A service's Library entry `m` with the images it runs, as its row
    of the file names them: pack format 5's, which the entry then says."""
    refs = images(m.get("name", ""))
    if not refs:
        return m
    m = {**m, "format": packformat.HELD_FORMAT, "images": refs}
    return {**m, "framework": packformat.least(m) or f"{packformat.HELD_FORMAT}.0"}


def module(kind):
    """The service's module, read by name at each call, so what a test
    replaces on it is what runs."""
    return importlib.import_module(TABLE[kind]["module"])


def packs():
    """Every service's Library entry, in the table's order."""
    return [module(k).pack() for k in KINDS]


def of_pack(name):
    """The kind whose pack goes by `name` (model-router is the router's),
    or "" for a name that is no service's."""
    return next((k for k in KINDS if module(k).pack().get("name") == name), "")


def grant(kind):
    return TABLE[kind]["grant"]


def paged(kind):
    return TABLE[kind]["page"]


# ---- a service on a node ---------------------------------------------------------

def deployed(kind, nid):
    return bool(module(kind).service_deployed(nid))


def install(kind, nid, by=""):
    return module(kind).service_install(nid, by)


def remove(kind, nid, by=""):
    return module(kind).service_remove(nid, by)


def updates(kind):
    """Whether a service's Update is the Containers row's own (its compose
    file written again from its entry and rebuilt, service_update), which
    it is where its module has no pin and no Update of its own."""
    return callable(getattr(module(kind), "service_update", None))


def update(kind, nid, by=""):
    return module(kind).service_update(nid, by) if kind in TABLE and updates(kind) else {"error": "it has no update of its own here"}


def container_names(nid):
    """{container name: kind} for a node: the name each service's
    containers go by there, whether or not it is deployed."""
    return {module(k).container_name(nid): k for k in KINDS}


def rows(nid, may=None):
    """The services' rows for a node's Library and Installed pages
    (library.rows' `services`): each one's entry as its pack, whether it is
    deployed there, and what its Remove says. `may` is asked each one's
    grant and leaves out a service it refuses; a pack that does not
    validate is left out too."""
    import toolpacks                                        # noqa: PLC0415 (it reads this table as it loads)
    out = []
    for kind in KINDS:
        if may is not None and not may(grant(kind)):
            continue
        m = module(kind)
        # Official by this table's word: the pack is the service module's own.
        manifest, errors = toolpacks.validate(m.pack(), shipped=(), official=True)
        if errors:
            continue
        row = {"manifest": manifest, "status": {"deployed": deployed(kind, nid)}, "ready": "", "removes": m.REMOVES}
        more = getattr(m, "service_row", None)
        if more:
            row.update(more(nid))
        out.append(row)
    return out
