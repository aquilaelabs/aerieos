#!/usr/bin/env python3
"""Writing a state file, and holding it while you read-modify-write one.

Two things that were each implemented several times, and one of them was
implemented wrong.

**The write.** Every state file goes to a temp file in the same directory and
is then renamed over the real one, so a reader (including bb-tty, which parses
the lock list on every session launch) never sees half a file. The temp name
is unique per call, from mkstemp. It used to be a fixed `<name>.json.tmp`, and
the dashboard is a threading server: two saves landing together each opened the
SAME temp file, the second truncating what the first was writing, and whichever
renamed first published a torn file. That was fixed in the server and NOT in
the five copies inside `aerie`, which is the ordinary fate of a function that
exists six times.

**The lock.** roadmap.py and bugs.py already wrap every read-modify-write in
`with _lock:`, which was a threading.Lock. A threading lock guards the
threads of ONE process. The notebook has two writers: the dashboard, and a
`aerie roadmap`/`aerie bug` invocation, which is a separate short-lived process. Both
would load the file, both mutate their own copy, both write; os.replace makes
each write atomic and does nothing whatever about the second one landing on top
of the first. An item added from a terminal while the panel was saving simply
was not there afterwards, and nothing anywhere said so.

So the lock is on the FILE, taken with flock, and held across the load and the
save rather than around the save alone: locking the write is locking the wrong
half, because the read that produced the stale copy already happened.

Re-entrant on purpose. flock is per open file description, so a second
`open()` in the same process blocks against the first: a mutator that called
another through the front door would deadlock on itself. The depth count makes
the outermost `with` the one that takes and releases it.

One lock per path, and each module locks only its own file, so there is no
order in which two of them can be taken, and therefore no order to get wrong.
"""
import contextlib
import errno
import fcntl
import json
import os
import tempfile
import threading
import time

# path -> [reentrant lock, depth, fd]. The RLock makes the depth and the fd
# safe to touch: only the thread holding it ever does.
_locks = {}
_guard = threading.Lock()


# Held by every write of a state file for the moment it lands, and by
# frozen() for as long as a copy of the state is being taken: a backup or a
# move's bundle read the files one by one while the server went on writing
# them, so it could hold an account without its secrets, or a link to a
# token the copy of the other file had already dropped.
_gate = threading.RLock()


@contextlib.contextmanager
def frozen():
    """No state file of this process's lands while the block runs; writers
    wait, and go on when it ends. For reading the state as one moment (a
    bundle's walk of /config), so kept short: nothing slow that could wait
    on a writer belongs inside. The CLI's own writes, another process's,
    are not held."""
    with _gate:
        yield


class Landing(OSError):
    """A write refused because the state it was for is being replaced."""


# The folder a landing is replacing and the thread doing it, or nothing.
_landing = []


def landing_begins(folder):
    """The state under `folder` is being replaced whole (a move's bundle or
    a backup landing, R227 step 8): from here every state file another
    thread of this process would write there is refused, at once and
    without waiting, since what that thread holds is the state that is
    going. A writer already renaming its file finishes first. Refused, never
    held: a writer made to wait while it holds its module's lock would stop
    the landing, which takes those locks. The landing's own thread writes as
    before. It stays so until landing_over(), or until the process ends,
    which is how a landing that worked ends."""
    with _gate:
        _landing[:] = [os.path.realpath(str(folder)), threading.get_ident()]


def landing_over():
    """The state that was there is back as it was: writers go on."""
    with _gate:
        _landing[:] = []


def _not_landing(path):
    if _landing and _landing[1] != threading.get_ident():
        folder, into = _landing[0], os.path.realpath(os.path.dirname(path) or ".")
        if into == folder or into.startswith(folder.rstrip("/") + "/"):
            raise Landing(errno.EBUSY, "this controller's state is being replaced by the one that just landed: "
                                       "nothing more is written to it until the controller has restarted", path)


class FileLock:
    """`with lock:` over `locked(path)`, for a module that held a threading
    lock alone around a read, a change and a save of its file: the same
    block now holds the file against every other process too (the CLI's
    verbs, a relay's worker), which the threading lock never did. Reentrant
    in one thread, as `locked` is. `path` is asked each time, since a
    module is told where its file is after it is imported; with none yet,
    the threads of this process are what it holds."""

    def __init__(self, path):
        self._path = path
        self._here = threading.RLock()
        self._held = threading.local()

    def __enter__(self):
        p = self._path()
        cm = locked(p) if p else self._here
        cm.__enter__()
        stack = getattr(self._held, "stack", None)
        if stack is None:
            stack = self._held.stack = []
        stack.append(cm)
        return self

    def __exit__(self, *exc):
        return self._held.stack.pop().__exit__(*exc)


def _sync(f):
    """The file's bytes on the disk before it is renamed into place: without
    it a power cut after the rename could leave the name pointing at a file
    cut short, which every loader then read as empty and the next save wrote
    over (B763). Never fatal: a filesystem that cannot sync keeps the rename."""
    with contextlib.suppress(OSError, ValueError):
        f.flush()
        os.fsync(f.fileno())


def _sync_dir(path):
    """...and the rename itself, by syncing the folder that holds the name."""
    with contextlib.suppress(OSError):
        fd = os.open(os.path.dirname(path) or ".", os.O_RDONLY)
        try:
            os.fsync(fd)
        finally:
            os.close(fd)


def unreadable(folder):
    """The state files in `folder` that are there and cannot be read as JSON:
    [(name, why)]. Asked at start, before any of them is loaded: a loader
    reads one as empty, and a save after that writes the empty view over
    what a person could still have mended."""
    out = []
    try:
        names = sorted(os.listdir(_p(folder)))
    except OSError:
        return out
    for name in names:
        if not name.endswith(".json") or name.startswith("."):
            continue
        f = os.path.join(_p(folder), name)
        if not os.path.isfile(f):
            continue
        try:
            with open(f, encoding="utf-8") as fh:
                json.load(fh)
        except (OSError, ValueError) as e:
            out.append((name, str(e)[:160]))
    return out


def set_aside(folder, name):
    """A copy of an unreadable state file kept beside it, so what a save
    writes over it afterwards is not the only copy: NAME.unreadable-STAMP.
    The copy's name, or "" when it could not be made."""
    import shutil
    import time
    src = os.path.join(_p(folder), name)
    dst = f"{src}.unreadable-{time.strftime('%Y%m%d-%H%M%S')}"
    try:
        shutil.copy2(src, dst)
        os.chmod(dst, 0o600)
    except OSError:
        return ""
    return os.path.basename(dst)


# ---- a state file read once while it stays the same file (R228 step 1) ----
# The text of each state file read through here, kept by what the file is on
# disk (its inode, size and times): on a /config served over the network each
# open and read was a round trip, and one status read opened users.json
# seventy times. Every caller still parses its own copy, so nothing one
# changes reaches another; what is saved is the trip to the disk. A request
# (begin_request) looks at each file once: the first ask stats it, and the
# same answer serves the rest of that request, as a request is one moment.
# A write through write_json, write_text or write_bytes forgets the file at
# once.
_texts = {}
_texts_lock = threading.Lock()
_here = threading.local()


# How long a request's look at a file holds: a request is one moment, and
# one that lives on (a terminal's socket, a node's long-poll) looks again.
REQUEST_HOLD_S = 2.0


def begin_request():
    """A request begins on this thread: each file is looked at once in it."""
    _here.seen = {}
    _here.t0 = time.monotonic()


def end_request():
    """...and ends: the next one looks again."""
    _here.seen = None


def writes_here():
    """How many state files this thread has written: a request's own answer
    about itself (who is asking) is kept until it writes one."""
    return getattr(_here, "wrote", 0)


def _forget(path):
    with _texts_lock:
        _texts.pop(path, None)
    seen = getattr(_here, "seen", None)
    if seen is not None:
        seen.pop(path, None)
        seen.pop(("sig", path), None)
    _here.wrote = getattr(_here, "wrote", 0) + 1


def forget(path):
    """A state file written some other way than write_json or write_text
    (its own temporary and rename): read afresh from now on."""
    _forget(_p(path))


def _request_seen():
    seen = getattr(_here, "seen", None)
    if seen is not None and time.monotonic() - getattr(_here, "t0", 0) > REQUEST_HOLD_S:
        seen.clear()
        _here.t0 = time.monotonic()
    return seen


# A file changed this recently is never taken as the same file: a
# filesystem's clock moves in ticks, and two writes of one size in place
# within a tick leave inode, size and times as they were (git's "racy"
# entries). Such a file is read again until it has been still this long.
RACY_NS = 2_000_000_000


def sig(path):
    """What the file is on disk, (inode, size, mtime, ctime, racy), or None
    when it is not there: looked at once a request, for a module that keeps
    its own parse of a file (registry, repos, roles) and checked it on every
    call. `racy` is 0 for a file still since RACY_NS, and a value no other
    look gives for one changed since, so it matches nothing kept."""
    path = _p(path)
    seen = _request_seen()
    key = ("sig", path)
    if seen is not None and key in seen:
        return seen[key]
    try:
        st = os.stat(path)
        racy = time.time_ns() - max(st.st_mtime_ns, st.st_ctime_ns) < RACY_NS
        got = (st.st_ino, st.st_size, st.st_mtime_ns, st.st_ctime_ns, time.monotonic_ns() if racy else 0)
    except OSError:
        got = None
    if seen is not None:
        seen[key] = got
    return got


def read_text(path):
    """The file's text, or None when it cannot be read (missing, a folder,
    not text): from what was kept while the file is the same one."""
    path = _p(path)
    seen = _request_seen()
    if seen is not None and path in seen:
        return seen[path]
    sig_ = sig(path)
    text = None
    if sig_ is not None:
        with _texts_lock:
            got = _texts.get(path)
        if got and got[0] == sig_:
            text = got[1]
        else:
            try:
                with open(path, encoding="utf-8") as f:
                    text = f.read()
            except (OSError, UnicodeDecodeError):
                text = None
            if text is not None:
                with _texts_lock:
                    if len(_texts) > 1024:
                        _texts.clear()
                    _texts[path] = (sig_, text)
    if seen is not None:
        seen[path] = text
    return text


def read_json(path, default=None):
    """The file's JSON, parsed for this caller alone, or `default` when the
    file is missing or is not JSON."""
    text = read_text(path)
    if text is None:
        return default
    try:
        return json.loads(text)
    except ValueError:
        return default


def write_json(path, obj, mode=0o644, sync=True):
    """Atomically replace `path` with `obj` as JSON. `mode` is the file's
    from the moment it is in place: a file of password hashes was 0644
    for the instant between the rename and the chmod that followed it.
    `sync=False` is for a store that is only notes of the moment (which
    session is editing which file, what a session last saw): still replaced
    whole, never half-written, but not waited onto the disk, which is tens
    of milliseconds a write and was paid on every edit a session made. A
    power cut can cost such a store its last minutes and nothing else."""
    path = _p(path)
    _not_landing(path)
    os.makedirs(os.path.dirname(path) or ".", exist_ok=True)
    fd, tmp = tempfile.mkstemp(dir=os.path.dirname(path) or ".",
                               prefix=os.path.basename(path) + ".",
                               suffix=".tmp")
    try:
        with os.fdopen(fd, "w") as f:
            f.write(json.dumps(obj, indent=2) + "\n")
            if sync:
                _sync(f)
        # mkstemp gives 600 and these were world-readable before.
        os.chmod(tmp, mode)
        with _gate:
            _not_landing(path)
            os.replace(tmp, path)
        _forget(path)
        if sync:
            _sync_dir(path)
    except BaseException:
        with contextlib.suppress(OSError):
            os.unlink(tmp)
        raise


def write_text(path, text, mode=0o644, encoding="utf-8"):
    """Atomically replace `path` with `text`: a temporary of its own name
    beside it, renamed over it, so a reader never meets it half-written and
    two writers never share a temp file (B196). The one copy of this: git.py,
    gitrelay.py, changelog.py and memory.py each carried their own and each
    met the fixed-temp-file race on its own before this."""
    path = _p(path)
    _not_landing(path)
    os.makedirs(os.path.dirname(path) or ".", exist_ok=True)
    fd, tmp = tempfile.mkstemp(dir=os.path.dirname(path) or ".",
                               prefix="." + os.path.basename(path) + ".", suffix=".tmp")
    try:
        with os.fdopen(fd, "w", encoding=encoding) as f:
            f.write(text)
            _sync(f)
        os.chmod(tmp, mode)
        with _gate:
            _not_landing(path)
            os.replace(tmp, path)
        _forget(path)
        _sync_dir(path)
    except BaseException:
        with contextlib.suppress(OSError):
            os.unlink(tmp)
        raise


def write_bytes(path, data, mode=0o644):
    """Atomically replace `path` with `data`, as write_text does with text:
    for a file that is not text (a sealed blob), whose writer would
    otherwise carry a temporary and a rename of its own."""
    path = _p(path)
    _not_landing(path)
    os.makedirs(os.path.dirname(path) or ".", exist_ok=True)
    fd, tmp = tempfile.mkstemp(dir=os.path.dirname(path) or ".",
                               prefix="." + os.path.basename(path) + ".", suffix=".tmp")
    try:
        with os.fdopen(fd, "wb") as f:
            f.write(data)
            _sync(f)
        os.chmod(tmp, mode)
        with _gate:
            _not_landing(path)
            os.replace(tmp, path)
        _forget(path)
        _sync_dir(path)
    except BaseException:
        with contextlib.suppress(OSError):
            os.unlink(tmp)
        raise


@contextlib.contextmanager
def locked(path):
    """Hold `path` exclusively, against this process's threads and every other
    process, for as long as the block runs.

    Never fatal. A state directory that cannot hold a lock file (read-only,
    full, a filesystem with no flock) degrades to the threading lock alone,
    which is what there was before this existed. Refusing to let somebody read
    their roadmap because a lock could not be taken would be a worse failure
    than the one being prevented.
    """
    key = _p(path)
    with _guard:
        ent = _locks.setdefault(key, [threading.RLock(), 0, None])
    ent[0].acquire()
    try:
        if ent[1] == 0:
            ent[2] = _flock(key)
        ent[1] += 1
        yield
    finally:
        ent[1] -= 1
        if ent[1] == 0 and ent[2] is not None:
            with contextlib.suppress(OSError):
                fcntl.flock(ent[2], fcntl.LOCK_UN)
                os.close(ent[2])
            ent[2] = None
        ent[0].release()


class on:
    """A reusable `with` over whatever path a module has configured.

    Modules set their FILE in configure(), after import, so a lock built at
    import time would close over None. This reads the path when the block is
    entered, and it can be entered again, which a contextmanager object
    cannot: `with locked(p):` twice reuses a generator that is already
    finished. Its own stack is per-thread, so two threads entering the same
    handle do not pop each other's.
    """

    def __init__(self, get_path):
        self._get = get_path
        self._held = threading.local()

    def _stack(self):
        if not hasattr(self._held, "cms"):
            self._held.cms = []
        return self._held.cms

    def __enter__(self):
        cm = locked(self._get())
        cm.__enter__()
        self._stack().append(cm)
        return self

    def __exit__(self, *exc):
        return self._stack().pop().__exit__(*exc)


def _flock(key):
    """The open, locked fd for `key`, or None if this filesystem will not."""
    try:
        os.makedirs(os.path.dirname(key) or ".", exist_ok=True)
        fd = os.open(key + ".lock", os.O_CREAT | os.O_RDWR, 0o644)
    except OSError:
        return None
    try:
        fcntl.flock(fd, fcntl.LOCK_EX)
        return fd
    except OSError as e:
        # ENOLCK/EINVAL: a filesystem without locking. Anything else is worth
        # not swallowing silently, but not worth failing the operation over.
        if e.errno not in (errno.ENOLCK, errno.EINVAL, errno.ENOSYS):
            raise
        with contextlib.suppress(OSError):
            os.close(fd)
        return None


def _p(path):
    return os.fspath(path)
