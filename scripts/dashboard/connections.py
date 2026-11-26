"""Connected services (R294 step 9, the connections rule in
docs/design-language.md): the one list of every credential this install
holds for an outside service, but a person's own, which is theirs alone and
listed on their Profile. Each row says what it is, whose it is (the
install's, a space's, or shared by spaces), who added it and when, when it
was last used, when it expires where its service says, and where it lives,
which is where it is added and changed; Forget is the list's one verb, an
administrator's, for a credential that must go at once.

The credential itself never comes here: each kind keeps its own where it
always has (gitcreds, the router's record, settings), and registers how its
rows are listed and how one is forgotten (`kind`). What the kinds do not keep,
who and when, is this module's ledger, STATE/connections.json, written as
each is added (`added`), used (`used`, at most once a minute) or measured
(`expires`). A row the ledger has nothing on was added before it kept any.

A new kind of connection (a cluster, a Discord server) is one `kind` call and
its own page; this list and its Forget come with it.
"""
import json
import threading
import time
from pathlib import Path

STATE = None
write_json = None
audit = None        # db.audit(principal, verb, target, detail)

# kind -> {"label", "whose", "list": () -> [{ref, name, uses, sealed, go}],
#          "forget": (ref, by) -> {ok}|{error}, or None}
_KINDS = {}
_lock = threading.Lock()
USED_EVERY_S = 60   # a use is written at most this often per connection
WHOSE = ("install", "space", "shared")


def configure(*, state, write_json_fn, audit_fn=None):
    globals().update(STATE=Path(state), write_json=write_json_fn, audit=audit_fn)


def kind(name, label, whose, lister, forget=None):
    """Register a kind of connection: `whose` is install, space or shared;
    `lister` gives its rows as they stand, each {ref, name, uses, sealed,
    go: [page, arg]}; `forget(ref, by)` removes one, or None where only its
    own page may."""
    assert whose in WHOSE, whose
    _KINDS[name] = {"label": label, "whose": whose, "list": lister, "forget": forget}


def _file():
    return STATE / "connections.json"


def _load():
    try:
        d = json.loads(_file().read_text())
    except (OSError, ValueError, TypeError):
        return {}
    return d if isinstance(d, dict) else {}


def _save(d):
    write_json(_file(), d, mode=0o600)


def _key(k, ref):
    return f"{k}:{ref}"


def added(k, ref, by=""):
    """A connection added or replaced: who and when, its last use and its
    expiry starting over, since they were the old credential's."""
    if not STATE:
        return
    with _lock:
        d = _load()
        d[_key(k, ref)] = {"by": str(by or "")[:80], "at": int(time.time())}
        _save(d)


def used(k, ref, at=None):
    """A connection used just now; written at most once a minute."""
    if not STATE:
        return
    now = int(at or time.time())
    with _lock:
        d = _load()
        rec = d.setdefault(_key(k, ref), {})
        if now - int(rec.get("used") or 0) < USED_EVERY_S:
            return
        rec["used"] = now
        _save(d)


def expires(k, ref, when):
    """When its service says the credential expires ("" for never or not
    said), as last measured."""
    if not STATE:
        return
    with _lock:
        d = _load()
        rec = d.setdefault(_key(k, ref), {})
        if rec.get("expires", "") == str(when or ""):
            return
        rec["expires"] = str(when or "")[:40]
        _save(d)


def gone(k, ref):
    """A connection that left by its own page: its ledger row with it."""
    if not STATE:
        return
    with _lock:
        d = _load()
        if d.pop(_key(k, ref), None) is not None:
            _save(d)


def listing():
    """{rows: [...]}: every kind's rows as they stand with what the ledger
    knows of each, the install's first, then the spaces', then shared."""
    led = _load()
    rows = []
    for k, spec in _KINDS.items():
        try:
            got = spec["list"]() or []
        except Exception as e:                 # noqa: BLE001 (one kind failing to list is said, not the list's end)
            rows.append({"kind": k, "label": spec["label"], "whose": spec["whose"], "ref": "", "name": spec["label"],
                         "error": f"could not be listed: {type(e).__name__}"})
            continue
        for r in got:
            rec = led.get(_key(k, r["ref"])) or {}
            rows.append({"kind": k, "label": spec["label"], "whose": spec["whose"], "ref": r["ref"],
                         "name": r.get("name") or r["ref"], "uses": r.get("uses", ""), "sealed": bool(r.get("sealed")),
                         "go": r.get("go") or [], "by": rec.get("by", ""), "at": rec.get("at", 0),
                         "used": rec.get("used", 0), "expires": rec.get("expires", ""),
                         "forget": spec["forget"] is not None})
    order = {w: i for i, w in enumerate(WHOSE)}
    rows.sort(key=lambda r: (order.get(r["whose"], 9), r["label"].lower(), r["name"].lower()))
    return {"rows": rows}


def forget(k, ref, by):
    """Forget one at once (a leak, a person gone): the kind removes its
    credential where it keeps it, and the ledger row goes. (payload, status)."""
    spec = _KINDS.get(str(k or ""))
    if not spec:
        return {"error": f"not a kind of connection: {k}"}, 400
    if not spec["forget"]:
        return {"error": f"{spec['label']} is forgotten where it lives, on its own page"}, 400
    try:
        kept = any(r["ref"] == ref for r in (spec["list"]() or []))
    except Exception as e:                     # noqa: BLE001 (said, as listing says it)
        return {"error": f"{spec['label']} could not be listed: {type(e).__name__}"}, 409
    if not kept:
        return {"error": f"no {spec['label']} {ref} is kept"}, 404
    got = spec["forget"](ref, by) or {}
    if got.get("error"):
        return {"error": got["error"]}, 409
    gone(k, ref)
    if audit:
        audit(by, "connection-forget", f"{k}:{ref}", {})
    return {"ok": True, **listing()}, 200
