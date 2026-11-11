"""A shipped toolchain's recipe, read from the catalog when the catalog's is
newer (R234 step 4).

Every toolchain AerieOS ships is a row of config/toolchains.json, and each
is also an official pack in the catalog, written from that row
(manifest_of; tools/packs-export.py). A row's recipe is mostly other
people's facts: where a release is downloaded from, how its version is
found, which system packages it needs. When one of those moves upstream the
fix used to wait for a release of AerieOS. Now a row has a `rev`, its
catalog entry repeats it (`shipped_rev`), and an install that reads a signed
index whose rev is higher than its own row's fetches that pack at its pin,
under its sha256, holds the row to its shape, and keeps it under the state:
the controller's own table and the bundle every node installs from then
carry the newer row in the shipped one's place. The image's copy is what
runs with no network, at first boot, and whenever the catalog's is no newer.

What a row may say is the format's, not the catalog's: its source kind, its
version resolvers and its checksum kinds are a closed set this build
carries the code for (the primitives below, docs/tool-packs.md), and its
probe is the shipped row's, since what reads a toolchain's version is this
build's own. A row that names anything else is one this build is too old
for: refused, and the shipped row stays.

A toolchain nobody ships is not a row here: it is a pack, with its own
install steps, which the catalog adds with no release at all.
"""
import json
import re
import threading
import time

FILE = None            # the state's catalog-toolchains.json
write_json = None
_lock = threading.RLock()
_trying = {}           # {(name, commit): when it was last tried}, so a pack that fails is asked again in an hour, not on every read

# The format's primitives a recipe names (docs/tool-packs.md): each is code
# in scripts/lib (sdk.sh's five install shapes, sdkmeta.py's resolvers and
# checksum readers). A new one is a new pack format, never a new meaning
# for one of these.
KINDS = ("tarball", "script", "git", "command", "sdkmanager")
RESOLVERS = ("approximate", "android-repo", "command-urls", "zig-index", "url-matches", "text", "node-index", "github-release")
CHECKSUMS = ("json", "android-repo", "go-json", "none", "file", "github-asset", "zsync", "signature", "zig-index")
SHIPPED_KEYS = ("probe", "source", "system", "requires", "updatable", "tool")
PLATFORM = re.compile(r"^(linux|darwin)/(amd64|arm64|\*)$")
MAX_BYTES = 64 * 1024
RETRY_S = 3600


def configure(*, state, write_json):
    globals().update(FILE=f"{state}/catalog-toolchains.json", write_json=write_json)


def rev_of(row):
    """A row's rev: a whole number from 1, 1 when it says none."""
    v = (row or {}).get("rev", 1)
    return v if isinstance(v, int) and not isinstance(v, bool) and 1 <= v <= 9999 else 1


def manifest_of(row):
    """A shipped row as its official pack's manifest: the one format's own
    keys at the top, the rest of the recipe under `shipped`. row_of is its
    inverse, to the key."""
    lay = row.get("layout") or {}
    shipped = {k: row[k] for k in SHIPPED_KEYS if k in row}
    for k in ("reports", "needs"):
        if lay.get(k):
            shipped[k] = lay[k]
    if rev_of(row) > 1:
        shipped["rev"] = rev_of(row)
    return {"name": row["name"], "label": row["label"], "about": row.get("about", ""), "tier": "official",
            "platforms": row.get("platforms") or ["linux/amd64"], "terms": row.get("terms") or [],
            "layout": {k: v for k, v in lay.items() if k in ("bin", "env", "tool")},
            "shipped": shipped}


def row_of(m):
    """An official pack's manifest as the row it was written from."""
    sh = m.get("shipped") or {}
    lay = dict(m.get("layout") or {})
    for k in ("reports", "needs"):
        if sh.get(k):
            lay[k] = sh[k]
    row = {"name": m.get("name"), "label": m.get("label"), "about": m.get("about", ""),
           "platforms": m.get("platforms") or [], "terms": m.get("terms") or [], "layout": lay}
    row.update({k: sh[k] for k in SHIPPED_KEYS if k in sh})
    if rev_of(sh) > 1:
        row["rev"] = rev_of(sh)
    return row


def _named(v, key):
    """Every value a recipe gives `key`, however deep."""
    if isinstance(v, dict):
        for k, x in v.items():
            if k == key and isinstance(x, str):
                yield x
            yield from _named(x, key)
    elif isinstance(v, list):
        for x in v:
            yield from _named(x, key)


def checked(row, shipped):
    """(row, why): a catalog's row as this build takes it in the shipped
    one's place, or why it does not."""
    if not isinstance(row, dict) or not isinstance(shipped, dict):
        return None, "it is not a toolchain this AerieOS ships"
    if len(json.dumps(row)) > MAX_BYTES:
        return None, "it is larger than a recipe is"
    if row.get("name") != shipped.get("name") or row.get("probe") != shipped.get("probe"):
        return None, "its name or its probe is not the shipped row's: what reads a toolchain's version is this AerieOS's own"
    if not all(isinstance(row.get(k), str) and row.get(k) for k in ("label", "about")):
        return None, "it has no label or no about"
    plats = row.get("platforms")
    if not (isinstance(plats, list) and plats and all(isinstance(p, str) and PLATFORM.fullmatch(p) for p in plats)):
        return None, "its platforms are not ones AerieOS names"
    src = row.get("source")
    if not isinstance(src, dict) or src.get("kind") not in KINDS:
        return None, f"its source is not one of {', '.join(KINDS)}: a newer AerieOS reads it"
    odd = sorted({r for r in _named(row, "resolver") if r not in RESOLVERS})
    if odd:
        return None, f"it finds a version with {', '.join(odd)}, which this AerieOS does not carry: a newer AerieOS reads it"
    ck = src.get("checksum")
    if isinstance(ck, dict) and ck.get("from") not in (None, *CHECKSUMS):
        return None, f"it checks a download by {ck.get('from')}, which this AerieOS does not carry: a newer AerieOS reads it"
    if not isinstance(row.get("layout"), dict):
        return None, "it has no layout"
    if rev_of(row) <= rev_of(shipped):
        return None, "it is no newer than the shipped row"
    return row, ""


def kept():
    """{name: {rev, commit, at, row}}: the rows taken from the catalog."""
    try:
        with open(FILE, encoding="utf-8") as f:
            d = json.load(f)
        rows = d.get("rows") if isinstance(d, dict) else None
        return {k: v for k, v in rows.items() if isinstance(v, dict) and isinstance(v.get("row"), dict)} if isinstance(rows, dict) else {}
    except (OSError, ValueError, TypeError):
        return {}


def merged(rows):
    """The shipped rows with the catalog's newer one in each one's place:
    every kept row is held to its shape again against the row it replaces,
    so one this build would no longer take (an upgrade caught up with it, a
    downgrade does not read it) is simply not used."""
    if not FILE or not isinstance(rows, list):
        return rows
    mine = kept()
    if not mine:
        return rows
    out = []
    for r in rows:
        rec = mine.get(r.get("name")) if isinstance(r, dict) else None
        row, _why = checked(rec["row"], r) if rec else (None, "")
        out.append(row or r)
    return out


def text(shipped_text):
    """config/toolchains.json as the bundle carries it: the shipped file
    with the catalog's newer rows in place, or "" when none applies and the
    file goes as it is."""
    try:
        doc = json.loads(shipped_text)
        rows = doc["toolchains"]
    except (ValueError, KeyError, TypeError):
        return ""
    new = merged(rows)
    if new == rows or new is rows:
        return ""
    return json.dumps({**doc, "toolchains": new}, indent=1) + "\n"


def wanted(index, shipped_rows):
    """The index's official entries whose shipped_rev is past the row this
    install would use today (its own, or one kept already)."""
    have = {r["name"]: rev_of(r) for r in merged(list(shipped_rows)) if isinstance(r, dict) and r.get("name")}
    out = []
    for e in (index or {}).get("packs") or []:
        # An index names a toolchain with its colon as a hyphen.
        name = next((n for n in have if n.replace(":", "-") == e.get("name")), None)
        rev = e.get("shipped_rev")
        if name and e.get("tier") == "official" and not e.get("withdrawn") and e.get("kind", "pack") == "pack" \
                and isinstance(rev, int) and not isinstance(rev, bool) and rev > have[name]:
            out.append((name, e))
    return out


def refresh(index, fetch, shipped_rows, validate=None):
    """Take the catalog's newer rows: each fetched at its pin under its
    sha256 (`fetch` is toolpacks.fetch_folder), its manifest held to the
    pack format (`validate`, toolpacks.validate) and its row to its shape.
    Rows an upgrade caught up with are dropped. [(name, "" or why)] for what
    was tried; nothing when nothing was wanted."""
    shipped = {r["name"]: r for r in shipped_rows if isinstance(r, dict) and r.get("name")}
    said = []
    with _lock:
        mine = kept()
        # What this build's own rows are as new as, or no longer ships.
        stale = [n for n, rec in mine.items() if n not in shipped or rev_of(rec["row"]) <= rev_of(shipped[n])]
        for name, e in wanted(index, shipped_rows):
            key = (name, e["commit"])
            if time.time() - _trying.get(key, 0) < RETRY_S:
                continue
            _trying[key] = time.time()
            got = fetch(e["url"], e["commit"], e["sha256"], e.get("path", ""), ("bbtool.json",))
            if got.get("error"):
                said.append((name, got["error"]))
                continue
            try:
                m = json.loads(got["files"]["bbtool.json"].decode("utf-8"))
            except (ValueError, UnicodeDecodeError, KeyError):
                said.append((name, "its bbtool.json is not JSON"))
                continue
            errors = validate(m)[1] if validate else []
            row, why = (None, "; ".join(errors)) if errors else checked(row_of(m), shipped[name])
            if not row:
                said.append((name, why))
                continue
            mine[name] = {"rev": rev_of(row), "commit": e["commit"], "at": int(time.time()), "row": row}
            said.append((name, ""))
        if stale or any(not why for _n, why in said):
            for n in stale:
                mine.pop(n, None)
            write_json(FILE, {"rows": mine})
    return said
