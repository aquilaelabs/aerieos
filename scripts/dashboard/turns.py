"""How many Claude sessions on one node are working on a prompt at once, and
the limit an administrator may set on that.

Why a node and not a project: what a working session costs is the machine's.
Claude Code itself is about half a gigabyte, and what it runs while it works
(a build, the suite, the emulator) is the real load. Several projects share a
node, so a limit per project would count the wrong thing. Claude's own usage
limits are per login, so one person's sessions never eat another's, and the
notebook, the hooks and the relay are proven under many writers at once
(test/concurrent.mjs): the node is what runs out.

WHAT COUNTS AS WORKING. Two sources, because neither is enough alone:

  * The heartbeat. Every node reports its tmux panes' titles, and a Claude
    pane's title carries a spinner while it works (server.claude_state).
    Exact, and as old as the last heartbeat, which is up to one poll.
  * The claims. A session's UserPromptSubmit hook asks here before a prompt
    starts (bb-gate --turn), and its Stop hook says when the turn is over.
    Immediate, and only as reliable as a hook: a session killed mid-turn
    never says it stopped.

So a session is working when it holds a claim the heartbeat has not yet had
time to contradict, or the heartbeat says so and it has not said it stopped
since that heartbeat was taken. A claim the heartbeat has seen through (a
sample taken well after it, with no spinner) is dropped: that is the session
that was killed, or interrupted, or whose Stop never came.

WAITING, NOT REFUSING. A prompt over the limit waits for a turn rather than
being thrown away, since a refused prompt is gone from the box it was typed
in. Waiters are served in the order they asked. A waiter that stops asking
(its hook was canceled) drops out of the queue after WAIT_STALE seconds.

In memory and nowhere else. Every fact here is about processes running now,
the heartbeat rebuilds the working half within one poll of a restart, and a
file of claims would only be a second copy that could go stale.
"""
import threading
import time

# A claim stands on its own this long, before the heartbeat has had a chance
# to see the turn it names: a poll is 25 seconds, and the title changes a
# moment after the prompt is sent.
CLAIM_GRACE = 45
# ...and never longer than this, whatever the heartbeat says.
CLAIM_MAX = 12 * 3600
# A waiter that has not asked again for this long has gone.
WAIT_STALE = 20
# The largest limit an administrator may set; past it the number means
# nothing a machine this project runs on could honor.
LIMIT_MAX = 64

# A hook that spoke this long before a session was first seen working
# belongs to that stretch of work: the prompt's hooks run a moment before
# the spinner shows, and a heartbeat is up to a poll old.
STRETCH_GRACE = 120
# ...and a stop's word is waited for this long after the session is seen
# idle: over a heartbeat, so the stop's hook has had a poll to be heard in.
END_GRACE = 30

_lock = threading.Lock()
_claims = {}       # (node, key) -> when its turn began
_ended = {}        # (node, key) -> when it said it stopped
_waiting = {}      # (node, key) -> [first asked, last asked]
_heard = {}        # key -> when a hook of that session last spoke
_watch = {}        # (node, key) -> {"idle": seen idle, "began": t, "ended": t, "quiet": t}


def _working(node, heart, at, now):
    """The keys working on `node`: `heart` is the set the last heartbeat
    showed working and `at` when that heartbeat was taken. Drops the claims
    the heartbeat has seen through. Called with the lock held."""
    out = {k for k in heart if _ended.get((node, k), 0) <= at}
    for (n, k), t in list(_claims.items()):
        if n != node:
            continue
        seen_through = at > t + CLAIM_GRACE and k not in heart
        if now - t > CLAIM_MAX or seen_through:
            del _claims[(n, k)]
            continue
        out.add(k)
    return out


def _tidy(now):
    for key, (_, last) in list(_waiting.items()):
        if now - last > WAIT_STALE:
            del _waiting[key]
    for key, t in list(_ended.items()):
        if now - t > CLAIM_MAX:
            del _ended[key]


def ask(node, key, limit, heart, at):
    """May `key`'s prompt on `node` start now?

    {"go": True} and the turn is claimed, or {"go": False, "working": [...],
    "ahead": n}, and `key` keeps its place in the queue for as long as it goes
    on asking. `limit` 0 is no limit, and nothing is queued.
    """
    now = time.time()
    with _lock:
        _tidy(now)
        busy = _working(node, heart, at, now) - {key}
        me = (node, key)
        if limit and len(busy) >= limit:
            first = _waiting.get(me, [now, now])[0]
            _waiting[me] = [first, now]
            ahead = sum(1 for (n, _), (f, _) in _waiting.items() if n == node and f < first)
            return {"go": False, "working": sorted(busy), "ahead": ahead, "limit": limit}
        # A free slot goes to whoever has waited longest: a prompt that has
        # just arrived does not jump the ones already in line.
        if limit:
            first = _waiting.get(me, [now, now])[0]
            free = limit - len(busy)
            ahead = sum(1 for (n, _), (f, _) in _waiting.items() if n == node and f < first)
            if ahead >= free:
                _waiting[me] = [first, now]
                return {"go": False, "working": sorted(busy), "ahead": ahead, "limit": limit}
        _waiting.pop(me, None)
        _claims[me] = now
        _ended.pop(me, None)
        return {"go": True, "working": sorted(busy | {key}), "limit": limit}


def done(node, key):
    """`key`'s turn on `node` is over, or its wait was given up."""
    now = time.time()
    with _lock:
        _claims.pop((node, key), None)
        _waiting.pop((node, key), None)
        _ended[(node, key)] = now


def state(node, heart, at):
    """{"working": [...], "waiting": n} on `node`, for its row."""
    now = time.time()
    with _lock:
        _tidy(now)
        return {"working": sorted(_working(node, heart, at, now)),
                "waiting": sum(1 for (n, _) in _waiting if n == node)}


def heard(key):
    """A hook of the session `key` (its tmux name) spoke to the controller:
    any of them, a prompt's, a tool's or a stop's."""
    now = time.time()
    with _lock:
        _heard[key] = now
        for (_n, k), w in _watch.items():
            if k == key:
                w["quiet"] = 0


def watch(node, present, heart, now=None):
    """A heartbeat of `node`: `present` the coding agents' sessions there (by
    tmux name), `heart` the ones working.

    THE GUARD THAT WENT QUIET. A session's hooks speak to the
    controller at every turn: the prompt's before it starts, a stop's when it
    ends, and several between. A coding agent passes over a hook that cannot
    be run, so a session whose hooks are gone works on with no gate and says
    nothing; the heartbeat still shows it working, which is the other source
    this module has. So a stretch of work that began and ended under this
    watch, with no hook of that session heard from STRETCH_GRACE before it
    began to END_GRACE after it ended, is a session working unguarded. It is
    marked until one of its hooks speaks again or the session is gone. A
    stretch already under way when the controller started is never judged:
    its beginning was not seen."""
    now = time.time() if now is None else now
    with _lock:
        for (n, k) in [x for x in _watch if x[0] == node and x[1] not in present]:
            del _watch[(n, k)]
        for k in list(_heard):
            if now - _heard[k] > CLAIM_MAX:
                del _heard[k]
        for k in present:
            w = _watch.setdefault((node, k), {"idle": False, "began": 0, "ended": 0, "quiet": 0})
            if k in heart:
                if w["began"]:
                    w["ended"] = 0                     # at work again before the last stretch was judged: one stretch
                elif w["idle"]:
                    w["began"] = now
                continue
            if w["began"] and not w["ended"]:
                w["ended"] = now
            if w["began"] and w["ended"] and now - w["ended"] >= END_GRACE:
                if _heard.get(k, 0) < w["began"] - STRETCH_GRACE and not w["quiet"]:
                    w["quiet"] = w["began"]
                w["began"] = w["ended"] = 0
            w["idle"] = True


def unguarded():
    """[(node, key, since)]: the sessions whose last stretch of work passed
    with no hook heard (watch), oldest first."""
    with _lock:
        return sorted(((n, k, w["quiet"]) for (n, k), w in _watch.items() if w["quiet"]), key=lambda x: x[2])


def limit_of(value):
    """A limit as stored, from whatever was sent: 0 (none) to LIMIT_MAX, or
    None when it is not a number."""
    try:
        n = int(value)
    except (TypeError, ValueError):
        return None
    return n if 0 <= n <= LIMIT_MAX else None
