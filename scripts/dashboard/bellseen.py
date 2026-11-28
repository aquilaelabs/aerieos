"""What each account has dismissed from its bell
(the drawer was a wall of amber). Kept on the server, per account, so a note
put away on the phone is put away on the desktop too.

A dismissal is a key naming the thing AND its version: a toolchain's update
to one version (tc:NODE:NAME@VERSION), an agent's update to one version
(agent:NODE@VERSION). The next newer version is a new key, so it notes
again; a row whose every key is dismissed is not sent. What stops work (an
agent out of window, a failing CI run, an ask) has no key and cannot be put
away: it leaves when it stops being true.
"""
import threading
import time
from pathlib import Path

import statefile

FILE = None                  # <state>/bell-dismissed.json, set by configure()
write_json = None
_lock = threading.Lock()
# A key nobody has met for this long is forgotten, so the file does not grow
# a line per version for ever: by then that version is long installed.
KEEP_S = 90 * 86400
MAX_KEYS = 400


def configure(*, state, write_json):
    globals().update(FILE=Path(state) / "bell-dismissed.json", write_json=write_json)


def _load():
    d = statefile.read_json(FILE) if FILE else None   # read once while the same file
    return d if isinstance(d, dict) else {}


def dismissed(uid):
    """{key: when} for one account."""
    mine = _load().get(str(uid or "")) if uid else None
    return mine if isinstance(mine, dict) else {}


def dismiss(uid, keys):
    """Put these keys away for this account. ({ok, dismissed: n}, status)."""
    if not uid:
        return {"error": "no account to keep it for"}, 400
    keys = [str(k)[:200] for k in (keys if isinstance(keys, list) else []) if str(k).strip()][:64]
    if not keys:
        return {"error": "nothing named to dismiss"}, 400
    now = int(time.time())
    with _lock:
        d = _load()
        mine = {k: v for k, v in (d.get(str(uid)) or {}).items()
                if isinstance(v, int) and now - v < KEEP_S}
        mine.update({k: now for k in keys})
        if len(mine) > MAX_KEYS:
            mine = dict(sorted(mine.items(), key=lambda kv: kv[1])[-MAX_KEYS:])
        d[str(uid)] = mine
        write_json(FILE, d)
    return {"ok": True, "dismissed": len(keys)}, 200


def restore(uid):
    """Everything this account put away comes back."""
    if not uid:
        return {"error": "no account to keep it for"}, 400
    with _lock:
        d = _load()
        n = len(d.pop(str(uid), None) or {})
        write_json(FILE, d)
    return {"ok": True, "restored": n}, 200


def blocks_work(r):
    """Whether a bell row is about something that blocks work now:
    it stands in the bell's Active section, under what
    waits on an answer, with no Dismiss, and leaves when it stops being
    true. A failing CI run, a session an outage held, a session whose hooks
    went quiet, a disk failing or a pool or array down, a UPS low or on
    battery, and every row nothing could put away (an agent out of window, a
    second factor required). An update waiting, a release missing a file and
    the rest are Earlier, each with its Dismiss."""
    k = r.get("kind")
    if k in ("ci", "held", "unguarded"):
        return True
    if k in ("disk", "power"):
        return bool(r.get("bad"))
    if k in ("toolchain", "agents"):
        return False                    # updates, put away tool by tool
    return not r.get("key")


def filter_rows(uid, rows):
    """The bell's node rows with this account's dismissals taken out, and how
    many were. A toolchain row loses the tools put away and goes when none is
    left; an agent row goes when its key is put away. Each row and tool that
    may be put away is handed its key."""
    gone = dismissed(uid)
    out, hidden = [], 0
    for r in rows:
        r = dict(r)
        if r.get("kind") in ("toolchain", "agents"):
            tools = []
            for t in r.get("tools") or []:
                t = dict(t, key=f"tc:{r['id']}:{t['name']}@{t.get('to') or ''}")
                if t["key"] in gone:
                    hidden += 1
                else:
                    tools.append(t)
            if not tools:
                continue
            r["tools"] = tools
        elif r.get("kind") == "relocate":
            # To when it failed: put away until another one fails.
            r["key"] = f"relocate:{r['id']}@{r.get('at') or 0}"
        elif r.get("kind") == "image":
            # To the digests it would move to: put away until one moves.
            r["key"] = f"image:{r['id']}@{r.get('digest') or ''}"
        elif r.get("kind") == "token-read":
            # To the newest read: put away until another one.
            r["key"] = f"tokenread:{r['id']}@{r.get('at') or 0}"
        elif r.get("kind") == "node-refused":
            # To when it began: put away until a new refusal begins.
            r["key"] = f"noderefused:{r['id']}@{r.get('since') or 0}"
        elif r.get("kind") == "token-reuse":
            # To when it was found: put away until it happens again.
            r["key"] = f"tokenreuse:{r['id']}@{r.get('at') or 0}"
        elif r.get("kind") == "nginx":
            # To the digest it would move to: put away until the
            # registry moves the line again.
            r["key"] = f"nginx:{r['id']}@{r.get('digest') or ''}"
        elif not r.get("window") and r.get("id") and r.get("to"):
            r["key"] = f"agent:{r['id']}@{r['to']}"
        # Every row that carries a key, whether its maker gave it one (a
        # signing that failed, keyed on what it says; a failed CI run; a
        # bundle a node refused; a held session; a release short of a file,
        # keyed on what is missing; a space's git access gone) or the lines
        # above did, goes while that key is put away, and comes back when
        # the key moves. A row its maker keyed and no line here named was
        # drawn with Dismiss and came back on the next read.
        # ...and marked active or not (active above), an active row never
        # hidden, whatever was put away before it was one.
        r["active"] = blocks_work(r)
        if r.get("key") and r["key"] in gone and not r["active"]:
            hidden += 1
            continue
        out.append(r)
    return out, hidden
