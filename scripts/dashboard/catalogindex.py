"""The vetted catalog's index (R169 step 2): index.json and index.sig
fetched from the catalog's address, the signature checked against the
maintainers' public key this install ships (config/catalog.pub) before a
single entry is read, so a tampered index is refused and the one before
kept; an index made before the one kept is refused the same way, signed as
it is, so an old one served again brings back nothing the catalog withdrew
(older, below); each entry pins a pack to an exact commit and its archive's
sha256, never latest, and may keep the pins of the earlier pack formats it
still serves, one entry read out of the index at the pin this build takes
(named, pinning, official; packformat.pin_for); a withdrawn entry puts a
line on the bell for every install that holds the pack. Read on demand with the copy kept an hour under
the state, and fetched again on a press.
"""
import calendar
import json
import os
import re
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
# An index as big as a catalog of tens of thousands of entries gets (R256):
# past either, what it lists beyond is said, never dropped unsaid (B975).
MAX_BYTES = 16 << 20
ENTRIES_MOST = 20000
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


def _pin(p, own=True):
    """What moves with a pin (packformat.ENTRY_PIN) as `p` says it, each
    part held to its shape: `p` is an entry, whose own fields are its newest
    pin, or one of its `older` pins. None where its commit, its sha256 or
    its format is none. An entry's own format is kept where it is past 1,
    as it always was; an older pin's is always said."""
    if not re.fullmatch(r"[0-9a-f]{40}", str(p.get("commit") or "")) or not re.fullmatch(r"[0-9a-f]{64}", str(p.get("sha256") or "")):
        return None
    # The format its manifest is written in (R234), which the entry
    # repeats: one past this build's is listed and says so, and is not
    # fetched. An entry whose format is no number is no entry.
    fmt = packformat.of(p)
    if fmt is None:
        return None
    out = {"commit": str(p["commit"]), "sha256": str(p["sha256"]),
           "platforms": [str(x)[:20] for x in (p.get("platforms") or []) if isinstance(x, str)][:8]}
    # A shipped coding agent's entry says its install recipe's rev (R169
    # step 13), so an install fetches the pack only when that is higher
    # than the recipe its release carries.
    rev = p.get("install_rev")
    if isinstance(rev, int) and not isinstance(rev, bool) and 1 <= rev <= 9999:
        out["install_rev"] = rev
    # Its name as a person reads it, where the entry says: a card shows
    # it before the pack is fetched, as it does once it is kept.
    if isinstance(p.get("label"), str) and p["label"].strip():
        out["label"] = p["label"].strip()[:60]
    # A shipped toolchain's entry says its recipe's rev (R234 step 4), so
    # an install fetches the pack only when that is past its own row's.
    rev = p.get("shipped_rev")
    if isinstance(rev, int) and not isinstance(rev, bool) and 2 <= rev <= 9999:
        out["shipped_rev"] = rev
    if fmt > 1 or not own:
        out["format"] = fmt
    # ...and the framework's version it is written for, where it says
    # one past its format alone (packformat.framework_of): what a card
    # says of an entry this build takes and leaves part of out.
    fw = packformat.framework_of(p)
    if fw is not None and fw[1]:
        out["framework"] = packformat.said(fw)
    # The AerieOS release lines its manifest says it works with, where
    # the entry repeats them: an install on another line does not list
    # the entry at all (the operator, 12 Nov), which it could only learn
    # after fetching the pack before.
    ww = p.get("works_with")
    if isinstance(ww, list) and 0 < len(ww) <= 12 and all(isinstance(x, str) and re.fullmatch(r"\d{1,3}\.\d{1,3}", x) for x in ww):
        out["works_with"] = list(ww)
    # What its downloads are held to, in the word its manifest reads
    # (packformat.held_entry), so a card says it before anything is
    # fetched; and an installer's own sentence with it. A word this build
    # has not met is left out, and the card says none.
    if p.get("held") in packformat.HELD_WORDS:
        out["held"] = p["held"]
        sentence = packformat.online_checked(p.get("online"))[0] if out["held"] == "installer" else ""
        if sentence:
            out["online"] = sentence
    return out


def parse(index_bytes):
    """The entries, each held to its shape, or (None, why)."""
    try:
        d = json.loads(index_bytes.decode("utf-8"))
    except (ValueError, UnicodeDecodeError):
        return None, "index.json is not JSON"
    if not isinstance(d, dict) or d.get("version") != 1 or not isinstance(d.get("packs"), list):
        return None, "index.json is not a version 1 catalog index"
    out = []
    for p in d["packs"][:ENTRIES_MOST]:
        if not isinstance(p, dict):
            continue
        name = str(p.get("name") or "")
        # Its newest pin, which the entry's own fields are (_pin): an entry
        # whose commit, sha256 or format is none is no entry.
        pin = _pin(p)
        if not re.fullmatch(r"[a-z][a-z0-9-]{1,39}", name) or pin is None or not str(p.get("url") or "").startswith("https://"):
            continue
        # A pack kept in a folder of one repository (R170 step 6: the shipped
        # packs live in the catalog's own): its path, held to a plain
        # relative folder; the sha256 is then of the archive of that folder.
        path = str(p.get("path") or "")
        if path and (not re.fullmatch(r"[a-z0-9][\w./-]{0,120}", path) or ".." in path.split("/")):
            continue
        # What the entry is (R170 step 7, R172): a tool pack, a Docker app or a service.
        kind = p.get("kind") if p.get("kind") in ("app", "service") else "pack"
        out.append({"name": name, "url": str(p["url"])[:300], "path": path, "kind": kind,
                    "tier": packformat.tier_of(p.get("tier")), "withdrawn": p.get("withdrawn") is True,
                    "about": str(p.get("about") or "")[:400], **pin})
        # Who the tool is by, where the entry says: a card names them
        # before the pack is fetched, as it does once it is kept.
        if packformat.maker_of(p):
            out[-1]["maker"] = packformat.maker_of(p)
        # A pack that brings a coding agent says so, and the Library files
        # its card with the agents before it is installed as after.
        if p.get("agent") is True:
            out[-1]["agent"] = True
        # What it is about (R256): the catalog's topics this build knows,
        # and the day it was added, for the Library's Topic and Recently
        # added. A build from before either leaves them out.
        topics = packformat.topics_of(p)
        if topics:
            out[-1]["topics"] = topics
        added = str(p.get("added") or "")
        if re.fullmatch(r"20\d\d-[01]\d-[0-3]\d", added):
            out[-1]["added"] = added
        # The pins of the earlier formats it still serves (packformat.pin_for),
        # each read as the entry's own pin is. An `older` that is not the
        # format's is dropped whole and the entry kept: its newest pin is as
        # good as it was, so a build that reads it loses nothing, a build
        # that does not is left with a card that says what it needs and
        # fetches nothing, and what the entry says of itself (that it is
        # withdrawn, above all) is never lost with it. Part of a list that
        # does not hold together is never guessed at.
        if p.get("older") is not None and not packformat.older_refused(p):
            older = [_pin(o, own=False) for o in p["older"]]
            if all(older):
                out[-1]["older"] = older
    # The first AerieOS that reads each format, where the index says, for a
    # card to name ({"3": "0.10.0"}).
    since = {str(k): str(v)[:40] for k, v in (d.get("formats") or {}).items()
             if re.fullmatch(r"[0-9]{1,4}(?:\.[0-9]{1,4})?", str(k)) and re.fullmatch(r"[0-9A-Za-z.+-]{1,40}", str(v))} if isinstance(d.get("formats"), dict) else {}
    # ...and how many it lists past what this build reads, for the Library to say.
    past = max(0, len(d["packs"]) - ENTRIES_MOST)
    return {"generated": str(d.get("generated") or "")[:40], "packs": out, **({"formats": since} if since else {}),
            **({"past": past} if past else {})}, ""


def too_new(entry, index=None):
    """Why this build does not take an entry, or "": its format is past
    the one this build reads (packformat), named with the first AerieOS
    that reads it where the index says."""
    fmt = packformat.of(entry) or 1
    return packformat.too_new(fmt, ((index or {}).get("formats") or {}).get(str(fmt), ""))


def named(index, name, kind="pack", tier=""):
    """The index's entry of this name and kind, as this build takes it
    (packformat.taken: at the newest pin whose pack format it reads, which
    for an entry that moved to a newer format is the older pin it keeps),
    withdrawn ones left out, or None. `tier` narrows it to that tier. The
    way a request reads one entry out of the index, so what is looked at,
    added and kept is that pin and never one past this build; an entry with
    no pin this build reads is answered too, for the caller to say what it
    needs (too_new)."""
    return next((e for e in packformat.taken(index)
                 if e["name"] == name and e.get("kind", "pack") == kind and not e.get("withdrawn") and (not tier or e.get("tier") == tier)), None)


def official(index, name):
    """The index's official pack entry of this name at a pin this build
    reads, or None: where a shipped coding agent's newer install recipe is
    read (R169 step 13). An entry whose every pin is in a format past this
    build's names no recipe it could run, and is not answered."""
    e = named(index, name, tier="official")
    return e if e and not too_new(e, index) else None


def pinning(index, url, commit, sha256, path=""):
    """The index's pack entry that pins exactly this address, commit,
    sha256 and folder at the pin this build takes, withdrawn ones left
    out, or None (B440): the tier of what a page asks to add is this
    entry's, never the request's."""
    return next((e for e in packformat.taken(index)
                 if e.get("kind", "pack") == "pack" and not e.get("withdrawn") and e["url"] == url and e["commit"] == commit
                 and e["sha256"] == sha256 and (e.get("path") or "") == (path or "")), None)


def made(index):
    """When an index was made, in seconds: its `generated`, the UTC stamp
    the catalog's tools write (2026-11-12T21:34:58Z), or None for one that
    says none or says it any other way. Read as a time, never compared as
    text, where a word would sort after every date."""
    said = (index or {}).get("generated")
    if not isinstance(said, str) or not re.fullmatch(r"\d{4}-\d\d-\d\dT\d\d:\d\d:\d\dZ", said):
        return None
    try:
        return calendar.timegm(time.strptime(said, "%Y-%m-%dT%H:%M:%SZ"))
    except ValueError:
        return None


STAMP = r"\d{4}-\d\d-\d\dT\d\d:\d\d:\d\dZ"


def floor():
    """(when, as said) of the oldest index this AerieOS takes, from the file
    beside the maintainers' key (config/catalog-floor: one line, a moment
    as an index says its own), or (None, "") where the install ships none
    or it is not that."""
    try:
        with open(os.path.join(os.path.dirname(os.path.normpath(PUB_FILE)), "catalog-floor"), encoding="utf-8") as f:
            lines = [ln.strip() for ln in f if ln.strip() and not ln.lstrip().startswith("#")]
        if len(lines) != 1 or not re.fullmatch(STAMP, lines[0]):
            return None, ""
        return calendar.timegm(time.strptime(lines[0], "%Y-%m-%dT%H:%M:%SZ")), lines[0]
    except (OSError, ValueError):
        return None, ""


def older(new, held, what="the index kept here"):
    """Why `new` is not taken in the place of `held` (`what`, in the
    refusal's words), or "": the one comparison of two signed indexes, for
    the catalog's answer, an imported mirror and the choice between them.

    A signature says who made an index, never that it is the newest, so
    whoever can answer at the catalog's address could serve an old one
    again: its withdrawn packs come back and its older pins read as
    updates. So one made before the one held is refused. One that does not
    say when it was made is refused too wherever the one held does, or
    leaving the date out would be the way round. One made at the same
    moment is taken: the catalog's signing stamps each index with the
    moment, so two signed ones that differ do not share one, and the
    indexes from before that stamp are older than any release's floor.

    An install that holds none yet has nothing to be older than, so the
    release says the oldest it takes (floor): one made before that, or one
    that does not say when it was made, is refused whatever is held."""
    now = made(new)
    least, least_said = floor()
    if least is not None:
        if now is None:
            return f"it does not say when it was made, and this AerieOS takes none made before {least_said}"
        if now < least:
            return f"it was made {new.get('generated')}, before the oldest this AerieOS takes ({least_said})"
    was = made(held)
    if was is None:
        return ""
    if now is None:
        return f"it does not say when it was made, and {what} was made {held.get('generated')}"
    if now < was:
        return f"it was made {new.get('generated')}, before {what} ({held.get('generated')})"
    return ""


def _path():
    return os.path.join(STATE, "catalog-index.json")


def _fallback(base):
    """What answers when the catalog does not: the index kept from this
    address, or the imported mirror's when it is as new or newer (R169
    step 6), or None."""
    k = _kept(base)
    m = mirror_index() if mirror_index else None
    if m and not older(m, k):
        return m
    return k


def _newest(idx):
    """The index a read answers: `idx`, the catalog's own, or the imported
    mirror's where that was made after it. Both carry the maintainers'
    signature, and a signature never says which is the newest, so a mirror
    a person imported is a floor under what the network answers: a catalog
    that answers an index from before it (an old copy served again, a cache
    behind the mirror) does not bring back what the mirror's had withdrawn.
    What is kept and compared for the address stays the catalog's own."""
    m = mirror_index() if mirror_index and idx else None
    return m if m and older(idx, m) else idx


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
    or {error, index: the one kept before, if any}. One made before the
    one kept is refused as a wrong signature is (older). `opener(url)`
    returns bytes, for a test to stand in for the network."""
    base = (url or DEFAULT_URL).rstrip("/") + "/"
    get = opener or (lambda u: urllib.request.urlopen(u, timeout=20).read(MAX_BYTES + 1))
    try:
        data = get(base + "index.json")
        sig = get(base + "index.sig").decode("utf-8", "replace")
    except Exception as e:                                             # noqa: BLE001 (the network's reasons are many)
        return {"error": f"the catalog did not answer: {str(e)[:200]}", "index": _fallback(base)}
    if len(data) > MAX_BYTES:
        return {"error": "the index is over 16 MB, which no catalog's is: refused", "index": _fallback(base)}
    why = verify(data, sig)
    if why:
        return {"error": why, "index": _fallback(base)}
    idx, why = parse(data)
    if why:
        return {"error": why, "index": _fallback(base)}
    idx["fetched_at"] = int(time.time())
    idx["url"] = base
    with _lock:
        # Signed, and still not taken when it was made before the one kept
        # from this address (older): the kept one stands and the reason is
        # said, as for a signature that does not match.
        held = (_kept(base) if STATE else None) or (_cache["index"] if (_cache["index"] or {}).get("url", base) == base else None)
        why = older(idx, held)
        if why:
            return {"error": f"the index the catalog answered is refused: {why}; the one kept stays in use", "index": _fallback(base)}
        if STATE:
            os.makedirs(STATE, exist_ok=True)
            (write_json or _write)(_path(), idx)
        _cache.update(at=time.time(), index=idx, error="")
    return {"index": _newest(idx)}


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
            return {"index": _newest(_cache["index"]), "error": ""}
        kept = _kept(base)
        if not fresh and kept and time.time() - int(kept.get("fetched_at") or 0) < KEEP_S:
            _cache.update(at=float(kept.get("fetched_at") or 0), index=kept)
            return {"index": _newest(kept), "error": ""}
        # A catalog that did not answer is asked again after five minutes,
        # not on every read: a box with no network reads its mirror at once.
        miss = _cache.get("missed") or {}
        if not fresh and miss.get("base") == base and time.time() - miss.get("at", 0) < MISS_S:
            return {"index": _fallback(base), "error": miss["error"]}
    r = fetch(url, opener)
    with _lock:
        _cache["missed"] = {"base": base, "at": time.time(), "error": r["error"]} if r.get("error") else {}
    return {"index": r.get("index"), "error": r.get("error", "")}


def said(url=None):
    """When the index in use was made and when it was read, for Controller
    settings' Vetted catalog group: {made, read}, or None with none yet.
    `made` is the index's own `generated` as it is written, "" where it
    says none; `read` when this install last took it from the address, 0
    for a mirror's. An index the address keeps answering is never replaced
    by a newer one, so its age is said where a person can see it: nothing
    here expires one, since a catalog may be quiet for weeks."""
    idx = known(url)
    if not idx:
        return None
    return {"made": idx.get("generated") if made(idx) is not None else "", "read": int(idx.get("fetched_at") or 0)}


def known(url=None):
    """The index as last read from this address (or the imported mirror's),
    never asked for now: what a press reads, which must not wait for the
    network. None when there is none yet."""
    base = (url or DEFAULT_URL).rstrip("/") + "/"
    with _lock:
        if _cache["index"] and _cache["index"].get("url", base) == base:
            return _newest(_cache["index"])
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
