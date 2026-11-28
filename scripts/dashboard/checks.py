"""Update checks on one clock, adjustable.

Each check AerieOS makes by itself has a cadence under Controller
settings, Update checks: the release (a newer AerieOS), the container
images, and the catalog (the toolchains, the coding
agents and the vetted index this controller offers), each daily, weekly
(the default), monthly or off, with Check now beside it. A node's own
version check (what its store holds against what is out) is that node's
setting on its page, read by toolchains.node_checks_due. Each loop asks
due in place of the constant it had; an environment switch that turns a
check off (BB_IMAGE_AUTOCHECK=0 and the like) still does, for the suite.

What a check last ran at is its own module's to say (last); the release's
and the catalog's, which kept theirs in memory, are stamped here in
STATE/checks.json so a restart is not a reason to ask again.
"""
import contextlib
import json
import threading
import time
from pathlib import Path

import statefile

CADENCE = {"daily": 86400, "weekly": 7 * 86400, "monthly": 30 * 86400, "off": None}
# Every check, in the order Controller settings lists them. AerieOS's own
# services have none: each runs the images its entry names by digest.
KINDS = ("release", "images", "catalog")
STATE = Path("/config")
settings = None
_last = {}       # kind -> fn returning the epoch it last ran, or 0
_run = {}        # kind -> fn running it now
_lock = threading.Lock()


def configure(*, state, settings_mod, last=None, run=None):
    globals().update(STATE=Path(state), settings=settings_mod)
    _last.update(last or {})
    _run.update(run or {})


def cadence(kind):
    v = settings.get(f"check_{kind}") if settings else "weekly"
    return v if v in CADENCE else "weekly"


def every(kind):
    """Seconds between checks of `kind`, or None when it is off."""
    return CADENCE[cadence(kind)]


def due(kind, last_at, now=None):
    e = every(kind)
    return e is not None and (time.time() if now is None else now) >= int(last_at or 0) + e


def guarded(lock, record, fetch, keep=None, flag=None):
    """One check of what is newest at a time, and its record stamped.

    record() answers the record, a dict, under `lock`. Its "checking" says a
    check is in flight, or `flag`'s does, a dict of the caller's own where
    the record is a file's and does not carry it; a second asker is answered
    the record as it stands. fetch() runs outside the lock and answers
    (found, error): the fields it read, {} when it read none so the last
    answer stays, and why it read none. The record then takes when it was
    asked (at) and the error, then what was found, and goes to keep() where
    it is kept in a file. The answer is a copy of the record."""
    with lock:
        on = record() if flag is None else flag
        if on["checking"]:
            return dict(record())
        on["checking"] = True
    # Whatever the fetch raises is its answer's error, and the flag comes
    # down however the record's keeping goes (a TypeError from a
    # null body left it up, and every later ask answered the stale record
    # until the controller restarted).
    try:
        found, error = fetch()
    except Exception as e:                                             # noqa: BLE001 (any of a fetch's reasons)
        found, error = {}, f"the check failed: {str(e)[:200] or type(e).__name__}"
    with lock:
        rec = record()
        try:
            rec.update(at=int(time.time()), error=error)
            rec.update(found)
            if keep:
                keep(rec)
        finally:
            (rec if flag is None else flag)["checking"] = False
        return dict(rec)


def loop(kind, last_at, run, delay, nap, on=None):
    """A check's own loop, a thread's target: after `delay` seconds, and
    every `nap` seconds from then, run() when the cadence of `kind` says it
    is due, counted from last_at(), so a restart is not a reason to ask
    again. One bad run is not the loop's end. `on`, where a check has a
    switch of its own, is read on every pass: off, nothing is looked at."""
    time.sleep(delay)
    while True:
        if (on is None or on()) and due(kind, last_at()):
            with contextlib.suppress(Exception):
                run()
        time.sleep(nap)


def _file():
    return STATE / "checks.json"


def _own_mode():
    """The mode a file this process makes is given, 0666 less its umask: 0644
    in the container, and 0600 on a machine of its own, where what the
    controller writes is its account's alone (host-boot.sh)."""
    try:
        with open("/proc/self/status") as f:
            for line in f:
                if line.startswith("Umask:"):
                    return 0o666 & ~int(line.split()[1], 8)
    except (OSError, ValueError, IndexError):
        pass
    return 0o644


def stamped(kind):
    try:
        return int(json.loads(_file().read_text()).get(kind) or 0)
    except (OSError, ValueError, AttributeError):
        return 0


def stamp(kind, at=None):
    with _lock:
        try:
            d = json.loads(_file().read_text())
        except (OSError, ValueError):
            d = {}
        d[kind] = int(at or time.time())
        statefile.write_text(_file(), json.dumps(d), mode=_own_mode())


def view():
    """What Controller settings draws: each check's cadence and when it last
    ran, those this install has."""
    out = {}
    for k in KINDS:
        if k not in _run:
            continue
        try:
            at = int(_last[k]() or 0) if k in _last else stamped(k)
        except Exception:                                   # noqa: BLE001 (a reading, never the page's failure)
            at = 0
        out[k] = {"cadence": cadence(k), "at": at}
    return out


def run_now(kind):
    """Check now: the check on a thread of its own, the answer on the page's
    next poll. {ok} or {error}."""
    fn = _run.get(kind)
    if not fn:
        return {"error": f"no {kind} check on this install"}
    threading.Thread(target=fn, name=f"check-{kind}", daemon=True).start()
    return {"ok": True}
