"""A project's git token, as the controller keeps it: one line, the
URL git's credential store would write (scheme, user, token, host), in
/config/gitcreds/<project>, 0600, sealed under the install key where there
is one, so a copy of /config pushes nowhere.

git is handed the token by git-credential-bb, a credential helper beside this
file that opens the line for the host git asks about; git's own store,
which reads only plain lines, is not used. Readers in the dashboard ask
read_line. Sealing is the server's: seal, unseal and sealing are set by it
from signing's, as for the signing keys and two-factor secrets.

A token a person gives a project is kept in their own key store
(accountkeys.py, sealed under their key), and the
project's file then says `account:UID:ID`, nothing secret, one line per
person who gave one (every git action is a person's, with their own
token). A person's own git work (their session's aerie git, their presses in
the Git view, the release they cut, the wiki they sync) is handed their own
token, while they hold a live sign-in anywhere (logins.live); signed out
everywhere, their sessions' aerie git waits for them. Work that is nobody's
in the moment (watching CI) takes the token of any giver signed in now and
pauses while none is. A project keeps no token of its own; a line kept as
the project's (an install with no key to seal a store with) is read as it
is until a person gives theirs.
"""
import base64
import contextlib
import contextvars
import os
import shlex
import threading
from pathlib import Path

import unlocks            # the opened tokens and their handouts

STATE = None
# Whose work a git command is: the server sets it for a person's
# request, so a call that names no account (version.release, the wiki's
# push, the address check) is handed theirs.
ACTING = contextvars.ContextVar("gitcreds_acting", default="")
seal = None               # bytes -> bytes
unseal = None             # bytes -> bytes, or raises
sealing = None            # () -> whether an install key is loaded now
SEALED = "bbseal:"
LINKED = "account:"
# The space's own token as a connection (connections.py): told
# when one is written or forgotten, and when git work is handed it. Set by
# the server; None in a process with no ledger.
on_added = None           # (project) -> None
on_gone = None            # (project) -> None
on_used = None            # (project) -> None
HELPER = Path(__file__).resolve().with_name("git-credential-bb")


_KEEP = object()


def configure(*, state, seal_fn=_KEEP, unseal_fn=_KEEP, sealing_fn=_KEEP):
    """Where the tokens are, and (from the server) the install key's seal;
    a hook not passed is left as it was, so a module that only knows the
    state (projects, cilogs, forgerelease) never takes the seal away."""
    globals()["STATE"] = Path(state)
    for name, fn in (("seal", seal_fn), ("unseal", unseal_fn), ("sealing", sealing_fn)):
        if fn is not _KEEP:
            globals()[name] = fn


def path(project):
    return STATE / "gitcreds" / project


def open_text(text):
    """A file's content as its plain line: opened if sealed, "" when it
    cannot be (another install key, or none)."""
    # The project's own line is the first that is not a giver's (a
    # token moved to the project sits beside the `account:` lines).
    lines = [ln for ln in (text or "").splitlines() if ln.strip() and not ln.startswith(LINKED)]
    text = lines[0].strip() if lines else ""
    if text.startswith(SEALED):
        try:
            text = unseal(base64.b64decode(text[len(SEALED):])).decode() if unseal else ""
        except Exception:                                   # noqa: BLE001 (Locked, or damaged: no token)
            return ""
    return text.splitlines()[0] if text else ""


def _accounts():
    import accountkeys                                      # noqa: PLC0415
    if accountkeys.STATE is None and STATE is not None:
        accountkeys.configure(state=STATE)
    return accountkeys


def _live(uid):
    """Whether this person holds a live sign-in now (logins.live); a store
    with no logins module beside it (a test, bb's own python) reads every
    account as signed in."""
    try:
        import logins                                       # noqa: PLC0415
        if logins.STATE is None and STATE is not None:
            logins.configure(state=STATE)
        return logins.live(uid)
    except ImportError:
        return True


def givers(project):
    """Who has given this project a token: [(uid, entry id)], in the order
    they gave, from the project's `account:` lines; an entry from before
    ids is named by its host."""
    try:
        text = path(project).read_text()
    except OSError:
        return []
    out = []
    for ln in text.splitlines():
        ln = ln.strip()
        if ln.startswith(LINKED):
            uid, _, fid = ln[len(LINKED):].partition(":")
            if uid and (uid, fid) not in out:
                out.append((uid, fid))
    return out


def linked_to(project):
    """(uid, entry id) of the first account that gave the project a token
    (its owner's, from the move off a project's own), or ("", "")."""
    g = givers(project)
    return g[0] if g else ("", "")


def given_by(project, uid):
    """The entry id of the token `uid` gave this project, or ""."""
    return next((fid for u, fid in givers(project) if u == uid), "")


def acting():
    return ACTING.get() or ""


def read_line(project, uid=None, live_only=True, why="read"):
    """The credential line git work on this project is handed, plain, or
    "" for none: a person's work (`uid`, else ACTING) is handed their own
    alone, when they gave one and are signed in; work that is nobody's
    (uid "") any giver's who is signed in now; then a line kept as the
    project's own from before. Each opening is a use the person reads on
    their Profile (`why` says what for)."""
    uid = acting() if uid is None else uid
    g = givers(project)
    # Each person's own token, with their own rights, never another's:
    # a person who gave none is handed none.
    if uid:
        if any(u == uid for u, _ in g) and (not live_only or _live(uid)):
            line = _accounts().forge_line(uid, given_by(project, uid), why=why, project=project, by=uid)
            if line or _locked(uid):
                return line
    else:
        for u, fid in g:
            if (not live_only or _live(u)) and not _locked(u):
                line = _accounts().forge_line(u, fid, why=why, project=project, by="")
                if line:
                    return line
    try:
        line = open_text(path(project).read_text())
    except OSError:
        return ""
    if line and on_used and why != "read":
        on_used(project)
    return line


def own_line(project):
    """Whether the project keeps a line of its own (from before accounts,
    or moved to it when its giver took their key)."""
    try:
        return bool(open_text(path(project).read_text()))
    except OSError:
        return False


def keep_as_own(project, line):
    """`line` kept as the project's own, sealed, before its givers' lines:
    what a project's background work runs with when the person whose token
    it was holds their own key."""
    if not line or "\n" in line:
        return False
    _settled(project)
    d = STATE / "gitcreds"
    d.mkdir(parents=True, exist_ok=True)
    os.chmod(d, 0o700)
    with _glock:
        rows = givers(project)
        fd = os.open(path(project), os.O_WRONLY | os.O_CREAT | os.O_TRUNC, 0o600)
        with os.fdopen(fd, "w") as fh:
            fh.write(_kept(line) + "\n" + "".join(f"{LINKED}{u}:{f}\n" for u, f in rows))
    return True


def _locked(uid):
    """Whether the account's store is under a key of its own and shut
    (unlocks), so its tokens open for nobody now."""
    try:
        return bool(unlocks.locked(uid))
    except Exception:                                       # noqa: BLE001
        return False


def usable(project, uid):
    """What git work by `uid` on this project would run with:
    {"by": uid or "", "mine": bool, "live": bool, "given": bool, "why": ""}.
    `why` says, in a sentence, what stops a push when nothing would run."""
    uid = uid or acting()
    g = givers(project)
    mine = given_by(project, uid) if uid else ""
    if mine:
        if _locked(uid):
            return {"by": uid, "mine": True, "live": _live(uid), "given": True, "locked": True,
                    "why": "your key store is locked: unlock it on your Profile (Your key store), and your "
                           "pushes and pulls run with your token"}
        if _live(uid):
            return {"by": uid, "mine": True, "live": True, "given": True, "why": ""}
        return {"by": uid, "mine": True, "live": False, "given": True,
                "why": "your token for this space is used only while you are signed in, and you are "
                       "signed out everywhere: aerie git waits for you to sign in to the dashboard"}
    # Nobody's work (no person) runs with any signed-in giver's; a person's
    # with their own alone.
    other = "" if uid else next((u for u, _ in g if _live(u) and not _locked(u)), "")
    if other:
        return {"by": other, "mine": False, "live": True, "given": False, "why": ""}
    if uid and not own_line(project):
        return {"by": "", "mine": False, "live": False, "given": False,
                "why": "you have not given this space a token: your pushes and pulls run with your own, "
                       "given under Repository in its notebook's Settings"}
    if g and not own_line(project):
        shut = [u for u, _ in g if _live(u) and _locked(u)]
        return {"by": "", "mine": False, "live": False, "given": False,
                "why": ("everyone signed in who gave this space a token has their key store locked: one of them "
                        "unlocks it on their Profile, or give yours in the space's settings") if shut else
                       "nobody who gave this space a token is signed in: give yours in the space's "
                       "settings, or wait for one of them"}
    if own_line(project):
        return {"by": "", "mine": False, "live": True, "given": False, "why": ""}
    return {"by": "", "mine": False, "live": False, "given": False,
            "why": "this space has no git token: give yours in the space's settings"}


def _write_givers(project, rows, keep_own=True):
    _settled(project)
    d = STATE / "gitcreds"
    d.mkdir(parents=True, exist_ok=True)
    os.chmod(d, 0o700)
    if not rows and not (keep_own and own_line(project)):
        forget(project)
        return
    try:
        own = [ln for ln in path(project).read_text().splitlines() if ln.strip() and not ln.startswith(LINKED)][:1] if keep_own else []
    except OSError:
        own = []
    fd = os.open(path(project), os.O_WRONLY | os.O_CREAT | os.O_TRUNC, 0o600)
    with os.fdopen(fd, "w") as fh:
        fh.write("".join(x + "\n" for x in own) + "".join(f"{LINKED}{u}:{f}\n" for u, f in rows))


# Each read of a project's givers and the write after it, as one: two
# people giving a project a token at once each read the givers, and one
# rewrite lost the other's line. Re-entrant, so a writer may call
# another.
_glock = threading.RLock()


def link_account(project, uid, fid):
    """The project given `uid`'s token: their line added, or theirs
    replaced when they had given one; the other givers stay."""
    with _glock:
        rows = [(u, f) for u, f in givers(project) if u != uid] + [(uid, fid)]
        _write_givers(project, rows)


def unlink_person(project, uid):
    """`uid`'s token no longer given to this project; the others stay."""
    with _glock:
        rows = [(u, f) for u, f in givers(project) if u != uid]
        if len(rows) == len(givers(project)):
            return False
        _write_givers(project, rows)
        return True


def linked_projects(uid, fid=None):
    """The projects this account gave a token, or one entry of it."""
    d = STATE / "gitcreds"
    return [f.name for f in (sorted(d.iterdir()) if d.is_dir() else [])
            if any(u == uid and (fid is None or x == fid) for u, x in givers(f.name))]


def keep_for(project, uid, line, login):
    """A token a person gave the project, into their own store and the
    project linked to it. The helper line, or "" when the install has no
    key to seal their store with (then kept as the project's own)."""
    got, _code = _accounts().link_forge(uid, line.rsplit("@", 1)[-1], line, login) if uid else ({"error": "no one"}, 400)
    if got.get("error"):
        write_line(project, line)
    else:
        link_account(project, uid, got["id"])
        # The entries it replaced: every project linked to one now uses the
        # one kept, so no project is left on a token that is gone.
        if got.get("replaced"):
            remap(uid, got["replaced"], got["id"])
    return helper(project)


def remap(uid, olds, new):
    """Each project linked to one of `uid`'s entries `olds` linked to `new`
    instead: the replaced token's projects keep a token, the current one."""
    olds = {str(o) for o in olds}
    d = STATE / "gitcreds"
    for f in sorted(d.iterdir()) if d.is_dir() else []:
        with _glock:
            rows = givers(f.name)
            if any(u == uid and x in olds for u, x in rows):
                moved = [(u, new if u == uid and x in olds else x) for u, x in rows]
                _write_givers(f.name, list(dict.fromkeys(moved)))


def _gone_file():
    return STATE / "gitcreds-gone.json"


def _gone():
    try:
        import json                                         # noqa: PLC0415
        d = json.loads(_gone_file().read_text())
    except (OSError, ValueError):
        d = {}
    return d if isinstance(d, dict) else {}


def _gone_save(d):
    import statefile                                        # noqa: PLC0415
    statefile.write_json(_gone_file(), d, mode=0o600)


def unlink_account(uid, name):
    """An account's key store gone (purged, or the account deleted): its
    line goes from every project it gave a token, and a project left with
    nobody's says so (gone_rows) until somebody gives theirs. Returns the
    projects that lost their last."""
    hit = linked_projects(uid)
    if not hit:
        return []
    import time                                             # noqa: PLC0415
    d = _gone()
    lost = []
    for p in hit:
        unlink_person(p, uid)
        if not givers(p):
            lost.append(p)
            d[p] = {"name": name, "at": int(time.time())}
    _gone_save(d)
    return lost


def gone_projects():
    """The projects whose git access went with an account."""
    return list(_gone())


def gone_rows(projects):
    """The bell's rows, kind git-unlinked, for these projects."""
    d = _gone()
    return [{"kind": "git-unlinked", "id": p, "project": p, "name": str(d[p].get("name") or ""),
             "at": int(d[p].get("at") or 0), "bad": True, "key": f"gitgone:{p}@{int(d[p].get('at') or 0)}",
             "why": f"its git access was linked to {d[p].get('name') or 'an account'}'s token, which is gone: "
                    "give it a token of its own, or link another account's, in its settings"}
            for p in projects if isinstance(d.get(p), dict)]


def _settled(project):
    """A project given git access again says no more that it lost it."""
    d = _gone()
    if d.pop(project, None) is not None:
        with contextlib.suppress(OSError):
            _gone_save(d)


def helpers(project, uid=None, why="git"):
    """The credential helpers for git work on this project, in the order
    git asks them: a handout of the acting person's own token, when
    they gave this project one and are signed in with their store open,
    and never another person's; for work that is
    nobody's (uid "", watching CI) a handout of any signed-in giver's whose
    store is open; then the project's helper for a line kept as the
    project's own from before. A handout (unlocks.handout) is the opened
    line in a file of its own for the window, so the helper opens nothing
    itself and each opening is a use on the person's Profile."""
    uid = acting() if uid is None else uid
    out = []
    g = givers(project)
    handed = ""
    for u, fid in ([(uid, given_by(project, uid))] if given_by(project, uid) else []) if uid else g:
        if not _live(u) or _locked(u):
            continue
        e = _accounts().entry_for(u, fid)
        if not e:
            continue
        handed = unlocks.handout(u, project, fid, why=why, by=uid or "", host=e["host"], login=e["login"])
        if handed:
            break
    if handed:
        out.append(f"!{shlex.quote(str(HELPER))} {shlex.quote(handed)}")
    if not g or own_line(project):
        h = helper(project)
        if h:
            out.append(h)
            # Handed to git work that reaches the remote: a use of the
            # space's own token (connections.py's last used).
            if on_used:
                on_used(project)
    return out


def git_c(project, uid=None, why="git"):
    """git's -c arguments that hand a command AerieOS's credential for this
    project, wherever it is kept (the account's own store, the project's),
    whatever the tree's own config names: every git that reaches a remote
    for AerieOS goes through these or through helpers written into a
    config of its own. [] where there is none."""
    hs = helpers(project, uid, why)
    return ["-c", "credential.helper=", *[x for h in hs for x in ("-c", f"credential.helper={h}")]] if hs else []


def _kept(line):
    if seal and sealing and sealing():
        return SEALED + base64.b64encode(seal(line.encode())).decode()
    return line


def write_line(project, line):
    _settled(project)
    d = STATE / "gitcreds"
    d.mkdir(parents=True, exist_ok=True)
    os.chmod(d, 0o700)
    fd = os.open(path(project), os.O_WRONLY | os.O_CREAT | os.O_TRUNC, 0o600)
    with os.fdopen(fd, "w") as fh:
        fh.write(_kept(line) + "\n")
    if on_added:
        on_added(project)


def helper(project):
    """The credential.helper value for a project that has a token, or ""."""
    f = path(project)
    return f"!{shlex.quote(str(HELPER))} {shlex.quote(str(f))}" if f.is_file() else ""


def names_helper(value, project):
    """Whether a repository's credential.helper value is this project's:
    git-credential-bb on its token file (projects.scoped_to_token). The
    helper is known by its name, not by the directory it was written from:
    a repository linked before the install moved to /opt/aerieos names it
    at /opt/builderbot, a link to the same file, and asked for the resolved
    path it read as no credential at all, its pushes refused."""
    f = str(path(project))
    for line in value.splitlines():
        try:
            words = shlex.split(line.strip().lstrip("!"))
        except ValueError:
            continue
        if words and Path(words[0]).name == HELPER.name and f in words[1:]:
            return True
    return False


def forget(project):
    with contextlib.suppress(OSError):
        path(project).unlink()
    if on_gone:
        on_gone(project)


def seal_all(again=False):
    """Every line kept open sealed, once the install has a key: at start.
    `again`, after the install key changed: every sealed one sealed
    once more, under today's key. Returns how many."""
    if not (seal and sealing and sealing()):
        return 0
    d = STATE / "gitcreds"
    n = 0
    for f in (sorted(d.iterdir()) if d.is_dir() else []):
        try:
            text = f.read_text().strip()
        except OSError:
            continue
        if text.startswith(LINKED):
            continue
        # Through keep_as_own, which writes the line with the givers' lines
        # after it: write_line kept the one line and every person who had
        # given the project a token was gone from it.
        if text and not text.startswith(SEALED):
            keep_as_own(f.name, text.splitlines()[0])
            n += 1
        elif again and text and (line := open_text(text)):
            keep_as_own(f.name, line)
            n += 1
    return n
