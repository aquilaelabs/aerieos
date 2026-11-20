"""The Library (R170): everything an AerieOS installs or runs, as one
list of one shape, for one node. The toolchains the catalog offers with
what the node's store holds (toolchains.payload_for_node), the coding
agents with their version against the latest (agentcode.rows), the tool
packs a person added (among the toolchain rows, by their tier), the apps a
NAS runs (nasapps.catalog), the vetted catalog's entries not yet added
(catalogindex) and the companions a person downloads (apps.view), each a
row: kind, tier, name, label, about, platforms, where it stands on the
node (installed, version, latest, update due, a job in flight), and the
one verb the row takes. The page draws the rows; each verb goes to the
read's own endpoint, so nothing is installed two ways.
"""
import calendar
import contextlib
import re
import time

import agents
import packformat

KINDS = ("toolchain", "agent", "pack", "service", "app", "companion")
# Who stands behind a card, as a person reads it (the operator, 12 Nov):
# AerieOS's own shipped rows and the packs its maintainers wrote are both
# Packaged by Aerie, a verified vendor's own pack is Verified, anybody's pack
# the maintainers reviewed is Vetted, and what a person added themselves is
# Sideloaded. The row's `tier` is the first word of each.
TIER_WORDS = {"official": "Packaged by Aerie", "verified": "Verified", "vetted": "Vetted", "url": "Sideloaded", "here": "Sideloaded", "sideloaded": "Sideloaded"}


# Who a shipped coding agent is by where its row names no provider: OpenCode
# runs any provider's model and is Anomaly's.
AGENT_MAKERS = {"open": "Anomaly"}


def _an(w):
    """"a" or "an" before a word, by its sound (Any model, OpenCode, xAI)."""
    return ("an " if w[:1].upper() in "AEIOU" or (w[:1] == "x" and w[1:2].isupper()) else "a ") + w


def _agent_about(provider):
    """What an agent's card says it is: a Claude session's, a ChatGPT
    session's; Any model's is a session on any model, which "an Any model
    session" did not say."""
    if provider.lower().startswith("any "):
        return f"What a session on {provider.lower()} runs on the node."
    return f"What {_an(provider)} session runs on the node."


def service_values(fields, status):
    """A service's configuration as the page shows it, from its own status
    (the router's: a provider's key as whether it is set, the endpoints
    with their keys as set, Ollama on or off, the projects allowed)."""
    out = {}
    for f in fields:
        n = f["name"]
        if f["kind"] == "secret":
            out[n] = bool((status.get("providers") or {}).get(n))
        elif n == "custom" and f["kind"] == "list":
            out[n] = [{"name": c.get("name", ""), "base": c.get("base", ""), "key": bool(c.get("key"))} for c in status.get("custom") or []]
        elif n == "ollama" and f["kind"] == "switch":
            out[n] = bool((status.get("ollama") or {}).get("on"))
        elif f["kind"] == "projects":
            out[n] = list(status.get("projects") or [])
        else:
            out[n] = "" if f["kind"] in ("text", "choice") else False if f["kind"] == "switch" else []
    return out


def repo_of(catalog_url):
    """The catalog repository's page from its index address, for Submit to
    the catalog: a raw.githubusercontent.com address names its owner and
    repository; any other address is given as it is, without the file."""
    u = str(catalog_url or "").strip()
    m = re.match(r"https://raw\.githubusercontent\.com/([^/]+)/([^/]+)/", u)
    if m:
        return f"https://github.com/{m.group(1)}/{m.group(2)}"
    return u.rsplit("/", 1)[0] if u.endswith((".json", ".sig")) else u.rstrip("/")


def _tier(t):
    return "official" if t in ("official", "aerie", "") else t if t in ("verified", "vetted") else "sideloaded"


def rows(node_payload, agent_rows, apps, catalog_index, companions, services=(), pack_values=None, pack_mine=None):
    """The one list, in the page's order: agents, toolchains, packs, the
    services (R172: a deployed thing of AerieOS's, its configuration on
    the card), apps, the catalog's offers, the companions. `services` is
    [{manifest, status, ready, all_projects}] and `pack_values` {pack name:
    its answers on this node} for the packs with a config block."""
    out = []
    pack_values = pack_values or {}
    # Who each tool is by (the operator, 12 Nov), for its card to name beside
    # the tier: a shipped row's own word, a coding agent's provider, and for
    # what the signed catalog lists, the entry's. Never a sideloaded pack's
    # own claim: what nobody vetted does not get to say whose it is.
    said = {e["name"]: e.get("maker", "") for e in (catalog_index or {}).get("packs") or []}
    # ...and this person's own answers, for the fields a pack scopes to a
    # person (R172 step 5): None where it asks none of them, or they may not.
    pack_mine = pack_mine or {}
    tc = node_payload or {}
    plat = str(tc.get("platform") or "")
    job = tc.get("job") or {}
    busy_on = job.get("current") if job.get("running") and job.get("action") != "check" else ""
    # What is queued behind it (a press while it ran): each such card says so.
    waiting = {str(x) for w in job.get("waiting") or [] if w.get("action") != "check" for x in w.get("names") or []}
    # ...and the job's own names it has not reached: until its agent says
    # which it is on, the first is the one it works on and the rest wait. A
    # card pressed read as not pressed until then, its Software update still
    # offered while the Jobs page said it ran (the operator, 17 Nov).
    if job.get("running") and job.get("action") != "check":
        ahead = [str(x) for x in job.get("queue") or []]
        if not busy_on and ahead:
            busy_on = ahead[0]
        waiting |= set(ahead) - {busy_on}
    for r in agent_rows or []:
        out.append({"kind": "agent", "tier": "official", "name": r["name"], "label": r.get("label") or r["name"], "agent": r.get("agent", ""),
                    "maker": AGENT_MAKERS.get(r.get("agent", "")) or getattr(agents.get(r.get("agent", "")), "provider", "") or "",
                    "about": _agent_about(r.get("for") or r.get("label") or ""), "platforms": [],
                    "installed": bool(r.get("installed")), "version": r.get("installed") or "", "latest": r.get("latest") or "",
                    "update": r.get("state") == "update", "running": bool(r.get("running")), "doing": r.get("action") or "",
                    "error": r.get("error") or "",
                    "verb": "update" if r.get("state") == "update" else ("" if r.get("installed") else "install")})
    # What is the machine's own rather than the store's (R102, step 5): the
    # NVIDIA driver and the container toolkit where the node has the card,
    # as toolchain rows carrying their machine record for the card's lines
    # and the driver's version pick.
    for m in tc.get("machine") or []:
        here = bool(m.get("here"))
        ver = m.get("installed") or m.get("loaded") or ""
        out.append({"kind": "toolchain", "tier": "official", "name": m["name"], "label": m.get("label") or m["name"], "maker": "NVIDIA",
                    "about": ("For " + (f"this machine's {m.get('gpu') or m.get('card')}" if m.get("card") else "an NVIDIA card")
                              + ": CUDA, the hardware video encoder and the emulator's GPU rendering need it. It is this machine's own, not a copy on the store.")
                    if m["name"] == "nvidia-driver" else
                    "Lets a container on this machine use the card. From NVIDIA's own package source, which installing adds and removing takes away. Running containers keep running.",
                    "platforms": [], "terms": [], "installed": here, "unknown": False, "version": ver.split("-")[0] if m["name"] != "nvidia-driver" else ver,
                    "latest": (m.get("newer") or "").split("-")[0], "update": bool(m.get("newer")), "updatable": True,
                    "running": busy_on == m["name"], "doing": job.get("action") or "" if busy_on == m["name"] else "",
                    "queued": m["name"] in waiting and busy_on != m["name"],
                    "size": "", "wrong_platform": "", "pinned": [], "pack": None, "machine": m,
                    "verb": "" if not m.get("managed") else "update" if m.get("newer") else ("" if here else "install")})
    packs_here = set()
    # The index's pin of each pack it offers: one kept from it at another
    # commit is offered the new pin on its row (R169 step 4).
    # A pin written in a format past this build's is no update to offer.
    pins = {e["name"]: e for e in (catalog_index or {}).get("packs") or []
            if e.get("kind", "pack") == "pack" and not e.get("withdrawn") and not _too_new(e, catalog_index)}
    for i in tc.get("items") or []:
        pack = i.get("pack")
        if pack:
            packs_here.add(i["name"])
        t = _tier(pack.get("tier", "url") if pack else "official")
        out.append({"kind": "pack" if pack else "toolchain", "tier": t, "name": i["name"], "label": i.get("label") or i["name"],
                    "maker": "" if t == "sideloaded" else i.get("maker") or said.get(i["name"].replace(":", "-"), ""),
                    "credits": [] if t == "sideloaded" else i.get("credits") or [],
                    "about": i.get("about") or "", "platforms": i.get("platforms") or [], "terms": i.get("terms") or [],
                    "installed": bool(i.get("installed")), "unknown": bool(i.get("unknown")), "version": i.get("version") or "",
                    "latest": i.get("latest") or "", "update": i.get("state") == "update", "updatable": bool(i.get("updatable")),
                    "running": busy_on == i["name"], "doing": job.get("action") or "" if busy_on == i["name"] else "",
                    "queued": i["name"] in waiting and busy_on != i["name"],
                    "size": i.get("size") or "", "wrong_platform": i.get("wrong_platform") or "", "pinned": i.get("pinned_by") or i.get("pinned") or [],
                    # The open row's lines, as the Toolchains page draws them (step 2).
                    "tool": i.get("tool") or "", "system": i.get("system"), "needs": i.get("needs") or [], "needed_by": i.get("needed_by") or [],
                    "needs_missing": i.get("needs_missing") or [], "path": i.get("path") or "", "verified": i.get("verified"), "receipt": i.get("receipt"), "reopen": i.get("reopen") or 0,
                    # What its downloads are held to (pack format 5): {word, why}, word one of pinned, installer and open.
                    "held": i.get("held"),
                    "pack": {k: pack.get(k) for k in ("url", "commit", "path", "by", "at", "tier", "verbs", "here", "disabled")} if pack else None,
                    # What it asks for per node, and what it has been given here (R172).
                    "config": i.get("config") or [], "values": pack_values.get(i["name"]) if i.get("config") else None,
                    "mine": pack_mine.get(i["name"]),
                    "repin": _repin(pack, pins.get(i["name"])) if pack else None,
                    # A pack that brings a coding agent is its card under Coding
                    # agents (R169 step 9), installed and updated as a pack.
                    **({"group": "agent"} if pack and pack.get("agent") else {}),
                    # Its own icon's address, the pin in it so an update is a new one (R182).
                    "icon": f"/api/pack-icon?name={i['name']}&v={str(pack.get('commit') or '')[:12]}" if pack and pack.get("icon") else "",
                    "verb": "update" if i.get("state") == "update" else ("" if i.get("installed") else "install")})
    for s in services or []:
        m, st = s.get("manifest") or {}, s.get("status") or {}
        deployed = bool(st.get("deployed"))
        out.append({"kind": "service", "tier": "official", "name": m.get("name", ""), "label": m.get("label") or m.get("name", ""),
                    "maker": packformat.maker_of(m) or said.get(m.get("name", ""), ""), "credits": packformat.credits_of(m),
                    "about": m.get("about") or "", "platforms": m.get("platforms") or [], "terms": [],
                    "installed": deployed, "unknown": False, "version": "", "latest": "", "update": False,
                    "running": bool(st.get("job")), "doing": "deploy" if st.get("job") else "",
                    "service": (m.get("service") or {}).get("kind", ""), "config": m.get("config") or [],
                    "values": service_values(m.get("config") or [], st), "ready": s.get("ready", ""), "all_projects": s.get("all_projects") or [],
                    "status": {k: st.get(k) for k in ("url", "port", "models", "models_at", "spend", "ollama", "projects")},
                    # What Remove takes and what it leaves, in the service's own words.
                    "removes": s.get("removes", ""),
                    "verb": "" if deployed else "install"})
    for a in apps or []:
        out.append({"kind": "app", "tier": _tier(a.get("tier", "official")), "name": a["id"], "label": a["name"], "about": a.get("what") or "", "platforms": ["linux/*"],
                    "maker": "" if _tier(a.get("tier", "official")) == "sideloaded" else a.get("maker") or said.get(a["id"], ""),
                    "credits": [] if _tier(a.get("tier", "official")) == "sideloaded" else a.get("credits") or [],
                    "by": a.get("by") or "", "at": a.get("at") or 0,
                    "port": a.get("port"), "media": bool(a.get("media")), "secrets": a.get("secrets") or [],
                    # Its compose file as the catalog holds it, and the blanks New container fills (step 2).
                    "compose": a.get("compose") or "", "blanks": sorted(set(re.findall(r"\$\{([A-Z_]+)\}", a.get("compose") or ""))),
                    # ...what its panel asks for, its network and whether it is going (R238).
                    "fields": a.get("fields") or [], "own": a.get("own") or [], "network": a.get("network") or "", "going": a.get("going") or "",
                    "icon": a.get("icon") or "",
                    "installed": False, "version": "", "latest": "", "update": False, "running": False, "verb": "install"})
    # The shipped rows by the names the catalog gives them (a toolchain's
    # colon as a hyphen, an agent by its id): an official entry naming one is
    # that row, listed once (R170 step 6).
    shipped = {i["name"].replace(":", "-") for i in tc.get("items") or []} | {r.get("agent", "") for r in agent_rows or []}
    app_ids = {a["id"] for a in apps or []}
    for e in (catalog_index or {}).get("packs") or []:
        # One added already is among the items with its pack; one the catalog
        # withdrew is not offered (the bell says so to an install that holds it).
        if e["name"] in packs_here or e.get("withdrawn") or (e.get("tier") == "official" and e["name"] in shipped):
            continue
        # A Docker app in the catalog (R170 step 7): an Apps card until it is
        # kept here, its Install keeping it and opening New container; a
        # service is its own row (R172).
        if e.get("kind") == "app":
            if e["name"] not in app_ids:
                out.append({"kind": "app", "tier": _tier(e.get("tier")), "name": e["name"], "label": e.get("label") or e["name"], "about": e.get("about") or "",
                            "maker": e.get("maker", ""),
                            "platforms": e.get("platforms") or [], "installed": False, "version": "", "latest": e.get("commit", "")[:12],
                            "update": False, "running": False, "compose": "", "blanks": [],
                            "catalog": {"url": e["url"], "commit": e["commit"], "sha256": e["sha256"], "path": e.get("path", "")}, "verb": "install",
                            **_past(e, catalog_index)})
            continue
        if e.get("kind") == "service":
            continue
        out.append({"kind": "pack", **({"group": "agent"} if e.get("agent") is True else {}), "tier": _tier(e.get("tier")), "name": e["name"], "label": e.get("label") or e["name"], "about": e.get("about") or "",
                    "maker": e.get("maker", ""), "framework": e.get("framework", ""),
                    "platforms": e.get("platforms") or [], "installed": False, "version": "", "latest": e.get("commit", "")[:12], "update": False,
                    "running": False, "catalog": {"url": e["url"], "commit": e["commit"], "sha256": e["sha256"], "path": e.get("path", "")}, "verb": "add",
                    **_past(e, catalog_index)})
    for c in (companions or {}).get("apps") or []:
        if not c.get("offered"):
            continue
        first = (c.get("files") or [None])[0]
        out.append({"kind": "companion", "tier": "official", "name": c["name"], "label": c.get("title") or c["name"], "about": c.get("does") or "", "maker": "AerieOS",
                    "platforms": [], "installed": False, "version": c.get("version") or "", "latest": "", "update": False, "running": False,
                    "dev": bool(c.get("dev")), "download": first, "files": c.get("files") or [], "absent": c.get("absent") or "",
                    "verb": "download" if first else ""})
    # A card not for this node (R170 step 9, the operator, 28 Oct: Xcode on
    # a Linux node): judged here for every row with a platforms list, the
    # toolchains' own verdict kept; the page leaves it out and counts it.
    # What each is about and when the catalog added it (R256), where its
    # index entry says: a shipped toolchain's and a kept pack's as well as
    # an offer's, by name.
    told = {e["name"]: e for e in (catalog_index or {}).get("packs") or []}
    for r in out:
        e = told.get(r["name"]) if r["kind"] != "agent" and r["kind"] != "companion" else None
        if e and e.get("topics"):
            r["topics"] = list(e["topics"])
        if e and e.get("added"):
            with contextlib.suppress(ValueError):
                r["added_at"] = int(calendar.timegm(time.strptime(e["added"], "%Y-%m-%d")))
    for r in out:
        r.setdefault("wrong_platform", "")
        if not r["wrong_platform"] and plat and r.get("platforms") and not _supports(r["platforms"], plat):
            r["wrong_platform"] = f"not for this node ({plat}): {', '.join(r['platforms'])}"
        # The toolchains' own verdict names the platforms alone: said as
        # the rest are, now a card for another system can be shown (R256).
        elif r["wrong_platform"] and not r["wrong_platform"].startswith("not for"):
            r["wrong_platform"] = f"not for this node{f' ({plat})' if plat else ''}: {r['wrong_platform']}"
    return out


# Whether a manifest's works_with names this build's release line: the
# server sets it to toolpacks.fits; a standalone reader takes every entry.
fits = lambda manifest: True    # noqa: E731


def _too_new(e, index):
    """Why this build does not take a catalog entry, or "": its format is
    past the one this build reads (R234), named with the first AerieOS that
    reads it where the index says; or it says the AerieOS release lines it
    works with and this build's is not one of them. Such an entry is not
    listed on the Library at all (the operator, 12 Nov): the page counts
    them in its head, so a person knows another AerieOS would show more."""
    fmt = packformat.of(e) or 1
    why = packformat.too_new(fmt, ((index or {}).get("formats") or {}).get(str(fmt), ""))
    if why:
        return why
    ww = e.get("works_with") or []
    return f"works with AerieOS {', '.join(ww)}, and this is another" if ww and not fits({"works_with": ww}) else ""


def _past(e, index):
    """A row's `too_new` for such an entry, with no verb to press; and for
    one this build takes though it is written for a later framework than it
    reads, `ahead`: what it leaves out, said on the card's Details."""
    why = _too_new(e, index)
    if why:
        return {"too_new": why, "verb": ""}
    return {"ahead": packformat.ahead(e)} if packformat.ahead(e) else {}


def _repin(pack, e):
    """The index's newer pin of a pack kept from it: the same address and
    folder at another commit, or None."""
    if not e or e["url"] != pack.get("url") or (e.get("path") or "") != (pack.get("path") or "") or e["commit"] == pack.get("commit"):
        return None
    return {"url": e["url"], "commit": e["commit"], "sha256": e["sha256"], "path": e.get("path", ""), "tier": _tier(e.get("tier"))}


def _supports(platforms, plat):
    """toolchains.supports' rule for a list that is there: the platform
    itself, or its system with any machine (linux/*)."""
    o, _, _a = plat.partition("/")
    return any(x == plat or x == f"{o}/*" for x in platforms)


# ---- browsing it (R256) ----

# How many cards a shelf on the front page shows, and the most a list asks
# for at once.
SHELF = 8
PAGE_MOST = 60
SORTS = ("match", "name", "added")
STANDS = {"installed": lambda r: bool(r.get("installed")),
          "update": lambda r: bool(r.get("update") or r.get("repin"))}
TIER_ORDER = {"official": 0, "verified": 1, "vetted": 2, "sideloaded": 3}


def _group(r):
    return r.get("group") or r.get("kind")


def _words(q):
    return [w for w in str(q or "").lower().split() if w][:8]


def _score(r, words):
    """How well a row answers the words, 0 when one of them is nowhere in it:
    its name first, then its label and maker, then its topics, then what it
    is, so typing a tool's name puts that tool first."""
    if not words:
        return 1
    name, label = str(r.get("name") or "").lower(), str(r.get("label") or "").lower()
    maker = str(r.get("maker") or "").lower()
    topics = " ".join(r.get("topics") or []).lower()
    about = f"{r.get('about') or ''} {r.get('kind') or ''} {r.get('tier') or ''} {' '.join(r.get('platforms') or [])}".lower()
    total = 0
    for w in words:
        if w == name or w == label:
            total += 100
        elif name.startswith(w) or label.startswith(w):
            total += 60
        elif w in name or w in label:
            total += 40
        elif w in maker:
            total += 30
        elif w in topics:
            total += 20
        elif w in about:
            total += 10
        else:
            return 0
    return total


def _front_order(r):
    # A shelf's order: the machine's own first (the NVIDIA driver, then its
    # container toolkit, as rows() lists them), then Packaged by Aerie, then
    # the newest in the catalog, then by name.
    return (not r.get("machine"), TIER_ORDER.get(r.get("tier"), 9), -int(r.get("added_at") or 0), str(r.get("label") or r.get("name") or "").lower())


def browse(rows, q="", kind="", topic="", tier="", here=True, sort="", offset=0, limit=30, kinds=()):
    """One look at the Library for the page (R256): the rows narrowed by the
    words, the kind (or Installed or Updates), the topic and the source,
    and, while `here`, to what runs on the node; the count for every chip
    and topic under the other narrowings; how many the node's platform hid;
    and either the front page's shelves (nothing narrowed) or one page of
    the one sorted list."""
    # An entry this AerieOS does not take is never shown (the operator, 12
    # Nov), counted for the page's head with the rest of what it says of
    # the node, which is about every row whatever is narrowed.
    later = [r for r in rows if r.get("too_new")]
    rows = [r for r in rows if not r.get("too_new")]
    facts = {"installed": sum(1 for r in rows if r.get("installed") and not r.get("wrong_platform")),
             "offered": sum(1 for r in rows if r["kind"] not in ("app", "companion") and not r.get("wrong_platform")),
             "updates": sum(1 for r in rows if STANDS["update"](r) and not r.get("wrong_platform")),
             "other_platform": sum(1 for r in rows if r.get("wrong_platform")), "not_this_build": len(later)}
    words = _words(q)
    offset = max(0, int(offset or 0))
    limit = max(1, min(PAGE_MOST, int(limit or 30)))
    sort = sort if sort in SORTS else ("match" if words else "name")
    scored = [(r, _score(r, words)) for r in rows]
    scored = [(r, s) for r, s in scored if s]

    def k_ok(r, k=None):
        k = kind if k is None else k
        return not k or (STANDS[k](r) if k in STANDS else _group(r) == k)

    def t_ok(r, t=None):
        t = topic if t is None else t
        return not t or t in (r.get("topics") or [])

    def s_ok(r, s=None):
        s = tier if s is None else s
        return not s or r.get("tier") == s

    def p_ok(r):
        return not here or not r.get("wrong_platform")

    def counted(f):
        return [r for r, _ in scored if f(r) and p_ok(r)]
    counts = {
        "kind": {k: len([r for r in counted(lambda r: t_ok(r) and s_ok(r)) if k_ok(r, k)]) for k in (*STANDS, *kinds)},
        "all": len(counted(lambda r: t_ok(r) and s_ok(r))),
        "tier": {}, "topic": {}}
    for r in counted(lambda r: k_ok(r) and t_ok(r)):
        counts["tier"][r.get("tier")] = counts["tier"].get(r.get("tier"), 0) + 1
    for r in counted(lambda r: k_ok(r) and s_ok(r)):
        for t in r.get("topics") or []:
            counts["topic"][t] = counts["topic"].get(t, 0) + 1
    matched = [(r, s) for r, s in scored if k_ok(r) and t_ok(r) and s_ok(r)]
    hidden = len([r for r, _ in matched if not p_ok(r)])
    matched = [(r, s) for r, s in matched if p_ok(r)]
    out = {"counts": counts, "hidden": hidden, "total": len(matched), "sort": sort, "facts": facts}
    if not (words or kind or topic or tier):
        mine = [r for r, _ in matched if STANDS["installed"](r) or STANDS["update"](r)]
        mine.sort(key=lambda r: (not STANDS["update"](r), str(r.get("label") or r.get("name")).lower()))
        out["here"] = mine
        out["shelves"] = []
        for k in kinds:
            of = sorted((r for r, _ in matched if _group(r) == k), key=_front_order)
            if of:
                out["shelves"].append({"kind": k, "total": len(of), "rows": of[:SHELF]})
        return out
    if sort == "match":
        matched.sort(key=lambda rs: (-rs[1], str(rs[0].get("label") or rs[0].get("name")).lower()))
    elif sort == "added":
        matched.sort(key=lambda rs: (-int(rs[0].get("added_at") or 0), str(rs[0].get("label") or rs[0].get("name")).lower()))
    else:
        # By name, the machine's own first in the order rows() gives them
        # (the driver before the toolkit that needs it).
        matched.sort(key=lambda rs: (not rs[0].get("machine"), "" if rs[0].get("machine") else str(rs[0].get("label") or rs[0].get("name")).lower()))
    out["rows"] = [r for r, _ in matched[offset:offset + limit]]
    out["offset"] = offset
    return out
