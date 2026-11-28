"""Which account's terminals this controller opened on each node, for which
space: {node id: {"uid/space": when}}, in /config.

A terminal opened on a node is stamped with a session token for its
account and space (server._scoped_arg), and a session idle past that
token's life is handed a fresh one on its node's heartbeat
(server.session_tokens_for). The heartbeat's list of sessions is the node's
own word, so a stolen node token could name a session of any account that
may work on a space there and be handed its token. A fresh one goes only
where this controller opened that account's terminal on that space on that
node itself, so the node is never handed a pair it was not given already.

A pair is kept while its session runs, and a month after it was last seen.
"""
import threading
import time

import statefile

KEEP_S = 30 * 86400
# A pair's time written again at most this often, so a heartbeat is not a write.
FRESH_S = 86400
STATE = None
write_json = None
_lock = threading.Lock()


def configure(*, state, write_json_fn):
    globals().update(STATE=state, write_json=write_json_fn)


_store = statefile.Store(lambda: STATE / "sessions-asked.json", write=lambda: write_json, mode=0o600, cached=True)


def _load():
    d = _store.load()
    return d if isinstance(d, dict) else {}


def _key(uid, project):
    return f"{uid}/{project}"


def note(nid, uid, project, now=None):
    """A terminal of `uid`'s on `project` opened on node `nid`."""
    if not (nid and uid and project):
        return
    now = int(time.time() if now is None else now)
    with _lock:
        d = _load()
        held = d.setdefault(str(nid), {})
        was = int(held.get(_key(uid, project)) or 0)
        if was and now - was < FRESH_S:
            return
        held[_key(uid, project)] = now
        for n in list(d):
            d[n] = {k: at for k, at in (d[n] or {}).items() if now - int(at or 0) < KEEP_S}
            if not d[n]:
                d.pop(n)
        _store.save(d)


def asked(nid, uid, project, now=None):
    """Whether this controller opened `uid`'s terminal on `project` on `nid`
    within the month; one asked about while it runs stays kept."""
    now = int(time.time() if now is None else now)
    at = int((_load().get(str(nid)) or {}).get(_key(uid, project)) or 0)
    if not at or now - at >= KEEP_S:
        return False
    if now - at >= FRESH_S:
        with _lock:
            d = _load()
            d.setdefault(str(nid), {})[_key(uid, project)] = now
            _store.save(d)
    return True
