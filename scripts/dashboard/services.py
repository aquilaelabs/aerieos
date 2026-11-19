"""AerieOS's own services on a node, as one table (R172, R264).

A service is a deployed thing of AerieOS's that the Library lists as an
official pack: the model router (router.py), nginx (nginxproxy.py) and the
Scanners (scanners.py). Each is named here once, what differs between them
as plain data, and every list of them reads this table: the kinds a pack's
service block may name (toolpacks.SERVICES), the packs written under
packs/services (tools/packs-export.py), which of a node's System containers
is whose (containers.manager_view), the Library's rows with its Install and
Remove (server.py), and the update checks two of them have (checks.KINDS,
the server's runners and loops).

A service's module answers by the same names as the others, which is all
this file asks of it:

  pack()                     its Library entry, a manifest
  container_name(nid)        the name its containers go by on that node
  service_deployed(nid)      whether it is on that node
  service_install(nid, by)   Install on its card: {ok, ...} or {error}
  service_remove(nid, by)    Remove on its card, the same
  REMOVES                    what Remove takes and what it leaves, said
                             before the press is confirmed; "" leaves the
                             page's own words
  service_row(nid)           where it has more to say on its row than
                             whether it is deployed: the keys it sets
  checked_at()               where it has a check: when that last ran
  check_loop()               ...and the loop that runs it on its cadence

The modules are imported when first asked for and never as this one loads:
toolpacks and checks read the table while they load, and nginxproxy and
scanners import checks themselves.
"""
import importlib

# kind (a pack's service.kind) -> the module that is the service; the grant
# on a node that its Library row comes to (the server's Install and Remove
# name the same one in their own gates); whether its settings are a page of
# its own, so the Library only installs and removes it; and the function of
# its module that runs its update check now, "" where it has none. The
# order is the one every list of them keeps.
TABLE = {
    "router": {"module": "router", "grant": "configure", "page": False, "check": ""},
    "nginx": {"module": "nginxproxy", "grant": "docker-write", "page": True, "check": "check_image"},
    "scanners": {"module": "scanners", "grant": "docker-write", "page": True, "check": "check_versions"},
}
KINDS = tuple(TABLE)
# The kinds with an update check of their own, each a cadence under
# Controller settings by its kind's name.
CHECKED = tuple(k for k, s in TABLE.items() if s["check"])


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
        manifest, errors = toolpacks.validate(m.pack(), shipped=())
        if errors:
            continue
        row = {"manifest": manifest, "status": {"deployed": deployed(kind, nid)}, "ready": "", "removes": m.REMOVES}
        more = getattr(m, "service_row", None)
        if more:
            row.update(more(nid))
        out.append(row)
    return out


# ---- the update checks (checks.py) -------------------------------------------------

def check_last():
    """{kind: () -> when its check last ran} for checks.configure."""
    return {k: (lambda k=k: module(k).checked_at()) for k in CHECKED}


def check_run():
    """{kind: () -> its check run now} for checks.configure."""
    return {k: (lambda k=k: getattr(module(k), TABLE[k]["check"])()) for k in CHECKED}


def check_loops():
    """{kind: the loop that runs its check when due}, each a thread's
    target at the server's start."""
    return {k: (lambda k=k: module(k).check_loop()) for k in CHECKED}
