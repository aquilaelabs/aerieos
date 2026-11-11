"""The vetted catalog's index (R169 step 2): index.json and index.sig
fetched from the catalog's address, the signature checked against the
maintainers' public key this install ships (config/catalog.pub) before a
single entry is read, so a tampered index is refused and the one before
kept; each entry pins a pack to an exact commit and its archive's sha256,
never latest; a withdrawn entry puts a line on the bell for every install
that holds the pack. Read on demand with the copy kept an hour under the
state, and fetched again on a press.
"""
import json
import os
import threading
import time
import urllib.request

import packformat

STATE = None
mirror_index = None      # catalogmirror.index: the imported mirror's index, for when the catalog does not answer
write_json = None
PUB_FILE = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "..", "config", "catalog.pub")
DEFAULT_URL = "https://raw.githubusercontent.com/aquilaelabs/aerieos-catalog/main/"
KEEP_S = 3600
MISS_S = 300
MAX_BYTES = 4 << 20
_lock = threading.RLock()
_cache = {"at": 0.0, "index": None, "error": ""}


def configure(**deps):
    globals().update({k: v for k, v in deps.items() if k in globals()})
    if "state" in deps:
        globals()["STATE"] = str(deps["state"])


def _pubkeys(path=None):
    """The maintainers' public keys as the install ships them: the key the
    index is signed with, and on a second line its spare (R232), whose
    private half is kept apart so the first can be lost or replaced with no
    install cut off. [] when the file is not that, and then nothing is
    trusted and the catalog says so."""
    try:
        with open(path or os.path.normpath(PUB_FILE), encoding="utf-8") as f:
            lines = [ln.split() for ln in f if ln.strip() and not ln.lstrip().startswith("#")]
        if not 1 <= len(lines) <= 2 or any(len(w) != 2 or w[0] != "builderbot-catalog-ed25519" for w in lines):
            return []
        keys = [bytes.fromhex(w[1]) for w in lines]
        return keys if all(len(k) == 32 for k in keys) else []
    except (OSError, ValueError):
        return []


def _pubkey(path=None):
    """The key the index is signed with, or None."""
    return (_pubkeys(path) or [None])[0]


def verify(index_bytes, sig_text, pub=None):
    """Whether the signature is the maintainers' over these bytes, under
    the key this install ships or its spare: "" or why not. Needs the
    cryptography library; without it nothing is trusted, which is said
    rather than skipped."""
    keys = ([pub] if isinstance(pub, bytes) else list(pub)) if pub is not None else _pubkeys()
    if not keys:
        return "this install ships no catalog key, so no index is trusted"
    words = str(sig_text or "").split()
    if len(words) != 2 or words[0] != "builderbot-catalog-ed25519-signature":
        return "index.sig is not a catalog signature"
    try:
        from cryptography.hazmat.primitives.asymmetric import ed25519  # noqa: PLC0415
    except ImportError:
        return "the cryptography library is missing, so the index's signature cannot be checked: nothing is trusted"
    for key in keys:
        try:
            ed25519.Ed25519PublicKey.from_public_bytes(key).verify(bytes.fromhex(words[1]), index_bytes)
            return ""
        except Exception:                                              # noqa: BLE001, PERF203 (any failure is one answer)
            continue
    return "the index's signature does not match: it was changed on the way or signed by another key, and is refused"


def parse(index_bytes):
    """The entries, each held to its shape, or (None, why)."""
    try:
        d = json.loads(index_bytes.decode("utf-8"))
    except (ValueError, UnicodeDecodeError):
        return None, "index.json is not JSON"
    if not isinstance(d, dict) or d.get("version") != 1 or not isinstance(d.get("packs"), list):
        return None, "index.json is not a version 1 catalog index"
    import re
    out = []
    for p in d["packs"][:2000]:
        if not isinstance(p, dict):
            continue
        name = str(p.get("name") or "")
        if not re.fullmatch(r"[a-z][a-z0-9-]{1,39}", name) or not re.fullmatch(r"[0-9a-f]{40}", str(p.get("commit") or "")) \
                or not re.fullmatch(r"[0-9a-f]{64}", str(p.get("sha256") or "")) or not str(p.get("url") or "").startswith("https://"):
            continue
        # A pack kept in a folder of one repository (R170 step 6: the shipped
        # packs live in the catalog's own): its path, held to a plain
        # relative folder; the sha256 is then of the archive of that folder.
        path = str(p.get("path") or "")
        if path and (not re.fullmatch(r"[a-z0-9][\w./-]{0,120}", path) or ".." in path.split("/")):
            continue
        # What the entry is (R170 step 7, R172): a tool pack, a Docker app or a service.
        kind = p.get("kind") if p.get("kind") in ("app", "service") else "pack"
        out.append({"name": name, "url": str(p["url"])[:300], "commit": str(p["commit"]), "sha256": str(p["sha256"]), "path": path, "kind": kind,
                    "tier": "official" if p.get("tier") == "official" else "vetted", "withdrawn": p.get("withdrawn") is True,
                    "about": str(p.get("about") or "")[:400],
                    "platforms": [str(x)[:20] for x in (p.get("platforms") or []) if isinstance(x, str)][:8]})
        # A shipped coding agent's entry says its install recipe's rev (R169
        # step 13), so an install fetches the pack only when that is higher
        # than the recipe its release carries.
        rev = p.get("install_rev")
        if isinstance(rev, int) and not isinstance(rev, bool) and 1 <= rev <= 9999:
            out[-1]["install_rev"] = rev
        # A pack that brings a coding agent says so, and the Library files
        # its card with the agents before it is installed as after.
        if p.get("agent") is True:
            out[-1]["agent"] = True
        # The format its manifest is written in (R234), which the entry
        # repeats: one past this build's is listed and says so, and is not
        # fetched. An entry whose format is no number is no entry.
        fmt = packformat.of(p)
        if fmt is None:
            out.pop()
            continue
        if fmt > 1:
            out[-1]["format"] = fmt
    # The first AerieOS that reads each format, where the index says, for a
    # card to name ({"3": "0.10.0"}).
    since = {str(k): str(v)[:40] for k, v in (d.get("formats") or {}).items()
             if re.fullmatch(r"[0-9]{1,4}", str(k)) and re.fullmatch(r"[0-9A-Za-z.+-]{1,40}", str(v))} if isinstance(d.get("formats"), dict) else {}
    return {"generated": str(d.get("generated") or "")[:40], "packs": out, **({"formats": since} if since else {})}, ""


def too_new(entry, index=None):
    """Why this build does not take an entry, or "": its format is past
    the one this build reads (packformat), named with the first AerieOS
    that reads it where the index says."""
    fmt = packformat.of(entry) or 1
    return packformat.too_new(fmt, ((index or {}).get("formats") or {}).get(str(fmt), ""))


def _path():
    return os.path.join(STATE, "catalog-index.json")


def _fallback(base):
    """What answers when the catalog does not: the index kept from this
    address, or the imported mirror's when it is as new or newer (R169
    step 6), or None."""
    k = _kept(base)
    m = mirror_index() if mirror_index else None
    if m and (not k or str(m.get("generated", "")) >= str(k.get("generated", ""))):
        return m
    return k


def _kept(base=None):
    """The index kept under the state, None when there is none or it was
    read from another address than `base` (B443)."""
    try:
        with open(_path(), encoding="utf-8") as f:
            d = json.load(f)
        if base and isinstance(d, dict) and d.get("url", base) != base:
            return None
        return d if isinstance(d, dict) and isinstance(d.get("packs"), list) else None
    except (OSError, ValueError):
        return None


def fetch(url=None, opener=None):
    """The index from the catalog, verified, kept and answered: {index}
    or {error, index: the one kept before, if any}. `opener(url)` returns
    bytes, for a test to stand in for the network."""
    base = (url or DEFAULT_URL).rstrip("/") + "/"
    get = opener or (lambda u: urllib.request.urlopen(u, timeout=20).read(MAX_BYTES + 1))
    try:
        data = get(base + "index.json")
        sig = get(base + "index.sig").decode("utf-8", "replace")
    except Exception as e:                                             # noqa: BLE001 (the network's reasons are many)
        return {"error": f"the catalog did not answer: {str(e)[:200]}", "index": _fallback(base)}
    if len(data) > MAX_BYTES:
        return {"error": "the index is over 4 MB, which no catalog's is: refused", "index": _fallback(base)}
    why = verify(data, sig)
    if why:
        return {"error": why, "index": _fallback(base)}
    idx, why = parse(data)
    if why:
        return {"error": why, "index": _fallback(base)}
    idx["fetched_at"] = int(time.time())
    idx["url"] = base
    with _lock:
        if STATE:
            os.makedirs(STATE, exist_ok=True)
            (write_json or _write)(_path(), idx)
        _cache.update(at=time.time(), index=idx, error="")
    return {"index": idx}


def _write(path, data):
    tmp = path + ".new"
    with open(tmp, "w", encoding="utf-8") as f:
        json.dump(data, f)
    os.replace(tmp, path)


def index(url=None, fresh=False, opener=None):
    """The index as kept, fetched when it is older than an hour or asked
    fresh: {index, error}."""
    # Each answer is the address asked's: a catalog moved under Controller
    # settings is read at once, not after the old one's hour (B443).
    base = (url or DEFAULT_URL).rstrip("/") + "/"
    with _lock:
        if not fresh and _cache["index"] and _cache["index"].get("url", base) == base and time.time() - _cache["at"] < KEEP_S:
            return {"index": _cache["index"], "error": ""}
        kept = _kept(base)
        if not fresh and kept and time.time() - int(kept.get("fetched_at") or 0) < KEEP_S:
            _cache.update(at=float(kept.get("fetched_at") or 0), index=kept)
            return {"index": kept, "error": ""}
        # A catalog that did not answer is asked again after five minutes,
        # not on every read: a box with no network reads its mirror at once.
        miss = _cache.get("missed") or {}
        if not fresh and miss.get("base") == base and time.time() - miss.get("at", 0) < MISS_S:
            return {"index": _fallback(base), "error": miss["error"]}
    r = fetch(url, opener)
    with _lock:
        _cache["missed"] = {"base": base, "at": time.time(), "error": r["error"]} if r.get("error") else {}
    return {"index": r.get("index"), "error": r.get("error", "")}


def known(url=None):
    """The index as last read from this address (or the imported mirror's),
    never asked for now: what a press reads, which must not wait for the
    network. None when there is none yet."""
    base = (url or DEFAULT_URL).rstrip("/") + "/"
    with _lock:
        if _cache["index"] and _cache["index"].get("url", base) == base:
            return _cache["index"]
    return _fallback(base)


def withdrawn(installed_names):
    """The names among `installed_names` the kept index marks withdrawn:
    what the bell says to remove."""
    idx = _cache["index"] or _kept()
    if not idx:
        return []
    gone = {p["name"] for p in idx.get("packs") or [] if p.get("withdrawn")}
    return sorted(n for n in installed_names if n in gone)


def attention(installed_names):
    """The bell's rows (kind pack) for a withdrawn pack this install holds."""
    return [{"kind": "pack", "name": n, "key": f"pack:withdrawn:{n}",
             "said": f"the catalog withdrew the pack {n}: remove it from the Library, and from every node that holds it"}
            for n in withdrawn(installed_names)]
