"""The node's stores: where data, cache, artifacts and the toolchains live, the rules for a store's path, and node.json."""
import contextlib
import fcntl
import json
import os
import re
import subprocess
import tempfile
import threading
from . import names
from . import release
from .base import NODE_JSON, STORE_DENY_EXACT, STORE_DENY_UNDER, StatTimeout, _run, log, statvfs_within


def _can_chown(path):
    """Whether this filesystem lets root change a file's owner.

    The discriminator between a local disk and a squashed NFS export, asked
    rather than guessed from the mount type: squashing is the server's
    policy and does not show in fstab. A chown to root:root is the test
    because it is a no-op locally and refused wherever ownership is the
    export's to decide.
    """
    probe = os.path.join(path, f".bb-chown-probe.{os.getpid()}")
    try:
        with open(probe, "w"):
            pass
    except OSError:
        return True          # cannot even write: the copy will say so itself
    try:
        os.chown(probe, 0, 0)
        return True
    except OSError:
        return False
    finally:
        with contextlib.suppress(OSError):
            os.remove(probe)


# A store's path, the one shape a new one is taken in and the only one
# written where a shell reads it (/etc/profile.d): letters, digits and
# . _ / + @ -, with no .. part. Nothing a shell reads as more than a word.
STORE_PATH = re.compile(r"/[A-Za-z0-9._/+@-]+")


def path_plain(path):
    """Whether `path` is of a store's one shape (STORE_PATH)."""
    p = str(path or "")
    return bool(STORE_PATH.fullmatch(p)) and ".." not in p.split("/")


def store_path_ok(path, what="a store", shape=True):
    """"" if this is a safe place for a store, else why not. A bare
    top-level directory is refused as well as a system one: /mnt is where
    mounts live, not a store, and putting one there scatters directories
    across the mount root. A path is held to a store's one shape
    (path_plain) unless `shape` is off, which is for the path a node's own
    record already holds: a store enrolled before the shape was held stays
    where it is, and is only left out of what a shell reads."""
    p = str(path or "").rstrip("/") or "/"
    if not p.startswith("/"):
        return f"{path!r} is not an absolute path"
    if " " in p or ".." in p.split("/"):
        return f"{path!r} must be a plain absolute path, with no spaces or .."
    if shape and not path_plain(p):
        return f"{path!r} must be a plain absolute path: letters, digits and . _ / + @ - alone"
    if p in STORE_DENY_EXACT:
        return (f"{p} is a system directory (or the root of the mounts): "
                f"{what} is a directory of its own, like /var/lib/aerieos/x "
                "or /mnt/<share>/<dir>")
    for bad in STORE_DENY_UNDER:
        if (p + "/").startswith(bad):
            return f"{p} is inside {bad.rstrip('/')}, which this agent will not write to"
    # ...and where it really is, held to the same: a link on a share that
    # points at /etc passed as text, and root then copied a store's tree
    # into /etc. A link to somewhere a store may be (macOS's /tmp) is fine.
    real = os.path.realpath(p)
    if real != p and (why := store_path_ok(real, what, shape)):
        return f"{p} is a link to {real}, and {why}"
    return ""
def make_store(path):
    """Create a store directory, and say which directories that actually
    brought into being.

    The list is the whole point. A store at /mnt/tank/bb/toolchains may have
    made two directories or none, and there is no way to tell afterwards:
    an empty /mnt/tank/bb could be ours or could be the operator's. So it is
    recorded at the moment of creation, and nothing outside that record is
    ever removed.
    """
    p = os.path.abspath(str(path))
    made, probe = [], p
    while probe and probe != "/" and not os.path.exists(probe):
        made.append(probe)
        probe = os.path.dirname(probe)
    os.makedirs(p, exist_ok=True)
    made.reverse()                      # shallowest first: the order they appeared
    return made


def prune_made(made):
    """Remove the directories in `made` that are now empty, deepest first.

    rmdir rather than a check-then-delete: it fails with ENOTEMPTY by
    itself, so there is no window between deciding a directory is empty and
    removing it. The first one that will not go stops the walk (a parent of
    something that is still there cannot be empty either), and a mountpoint
    is never touched, because removing the directory a share is mounted on
    is how you delete the thing you meant to detach.

    Returns (removed, [(path, why)]).
    """
    removed, kept = [], []
    for d in reversed(list(made or [])):
        if os.path.ismount(d):
            kept.append((d, "it is a mountpoint"))
            break
        try:
            os.rmdir(d)
            removed.append(d)
        except OSError as e:
            kept.append((d, e.strerror or "it would not go"))
            break
    return removed, kept


def mount_covering(path, mounts):
    """The bb-sandbox mount this path would live inside, or None.

    The deepest match wins, so /mnt/tank/builderbot/toolchains is answered by
    /mnt/tank rather than by /mnt if both are configured. This is what makes
    an unmounted share detectable: the mount is in fstab, the directory
    under it is not, and mkdir would quietly make a local one.
    """
    p = str(path or "").rstrip("/")
    best = None
    for m in mounts or []:
        mp = str(m.get("path") or "").rstrip("/")
        if not mp:
            continue
        if p == mp or p.startswith(mp + "/"):
            if best is None or len(mp) > len(str(best.get("path") or "").rstrip("/")):
                best = m
    return best


def dir_bytes(path):
    """What is in there, in bytes, or None if it cannot be told quickly.
    `du` rather than a walk: one C process instead of a stat per file, which
    matters on the far end of an NFS link."""
    try:
        out = subprocess.run(["du", "-sb", path], stdout=subprocess.PIPE,
                             stderr=subprocess.DEVNULL, timeout=180, check=False)
        return int(out.stdout.split()[0]) if out.returncode == 0 else None
    except (OSError, ValueError, IndexError, subprocess.SubprocessError):
        return None


STORE_ID_FILE = ".bb-store-id"


# ---------------------------------------------------------------------------
# the toolchain store, a directory per node (R196)
#
# One share can serve any number of machines only if their binaries do not
# land on top of each other: a node's root is therefore <store>/<node id>,
# and everything else (the layout, the probes, the census, the bundle) is
# relative to that. The operator's setting stays the share. What is the same
# bytes on every host (the Android system images, tens of gigabytes) lives
# once under <store>/shared and each node's android tree links to it,
# because sdkmanager and Gradle want one ANDROID_HOME and would otherwise
# fetch a second copy per node.


# This node's own directory under the toolchain store (R196, the operator, 12
# Oct): its node id, so no two machines share a directory of toolchains,
# whatever distro each runs, and an id is never renamed or reused. Set by the
# agent from its state at start and on every hello (use_scope). An agent that
# has no id has no toolchain directory: tc_root is "" and every toolchain
# job says the node has no store.
_SCOPE = {"name": ""}
_ID = re.compile(r"n_[0-9a-f]{4,32}")


def tc_scope():
    """This node's directory name under the toolchain store, its node id,
    or "" before it has one."""
    return _SCOPE["name"]


def use_scope(store, node_id):
    """Make <store>/<node id> this node's directory. Returns the name in use."""
    node_id = str(node_id or "")
    if not _ID.fullmatch(node_id):
        return tc_scope()
    if store and os.path.isdir(store):
        try:
            os.makedirs(os.path.join(store, node_id), exist_ok=True)
        except OSError as e:
            log(f"toolchains: could not make {os.path.join(store, node_id)} ({e})")
            return tc_scope()
    _SCOPE["name"] = node_id
    return node_id


def noexec(path):
    """True when `path` is on a filesystem mounted noexec: nothing in it can
    run, the bb bundle and its terminals included (a tmpfs Docker made is
    noexec unless told otherwise)."""
    try:
        return bool(os.statvfs(path).f_flag & os.ST_NOEXEC)
    except (OSError, AttributeError):
        return False


def tc_root(state):
    """Where THIS machine's toolchains live: <store>/<node id>, or "" when
    the node has no toolchain store or no id yet."""
    store = (state.get("stores") or {}).get("toolchains") or ""
    return os.path.join(store, tc_scope()) if store and tc_scope() else ""


def store_id(path):
    """A stable id for a store, from a marker inside it: the same file the
    controller reads for its own (nodes.store_id).

    Two machines mounting one share cannot recognize each other by path: the
    controller reaches the toolchain store through the host's user-share layer while this
    node reaches the same bytes over NFS, and neither mount string can be
    derived from the other. The file answers exactly, whatever the transport.
    Read-only here: the controller creates it, so a node with a read-only
    store still reports the right id and never writes to one it should not.
    """
    try:
        with open(os.path.join(path, STORE_ID_FILE)) as f:
            return f.read().strip()[:64]
    except OSError:
        return ""


def store_here(path, role, node_id, made=()):
    """Why `path` already is a store, said before anything is copied into
    it (B661): "marked" when it carries the controller's marker, "mine"
    when it is a toolchain store holding this node's own folder, "own"
    when this agent made it for the store before (the folder the page nested
    for the node), and "" when none of those. The page asks the same of the
    controller's probe when a store is saved; the agent asks again at apply
    time, so an apply of a setting saved before the probe could answer is
    not refused for the files the store itself put there.
    """
    try:
        if store_id(path):
            return "marked"
        if role == "toolchains" and node_id and os.path.isdir(os.path.join(path, str(node_id))):
            return "mine"
    except (OSError, TypeError):
        return ""
    want = os.path.abspath(str(path)).rstrip("/")
    if any(os.path.abspath(str(d)).rstrip("/") == want for d in (made or ())):
        return "own"
    return ""


def _stores(stores, used=False):
    out = {}
    for role, path in (stores or {}).items():
        try:
            # Within seconds or not at all: a store on a share that stopped
            # answering blocked statvfs, and with it every turn of the
            # agent's loop, which samples the stores (B980).
            st = statvfs_within(path)
            out[role] = {"path": path, "id": store_id(path),
                         "free_mb": st.f_bavail * st.f_frsize // (1024 * 1024),
                         "total_mb": st.f_blocks * st.f_frsize // (1024 * 1024)}
            if role == "toolchains":
                out[role]["scope"] = tc_scope()      # where THIS machine's toolchains are, under path
        except StatTimeout:
            # Not answering: null as missing is, and said so on the row.
            out[role] = {"path": path, "free_mb": None, "total_mb": None, "stuck": True}
            continue
        except OSError:
            # Not there is a different fact from full: reported as null so
            # the row says "missing" rather than "0MB free".
            out[role] = {"path": path, "free_mb": None, "total_mb": None}
            continue
        if used:
            # What the store itself holds; the cache's size is the number
            # the row shows beside its Clear (docs/nodes.md §6). du, at the
            # census only: a walk of a big cache is not a per-poll cost.
            n = _run(["du", "-sm", path], timeout=60).split()
            out[role]["used_mb"] = int(n[0]) if n and n[0].isdigit() else None
    return out


# Where a toolchain installed into the toolchain store keeps its command,
# relative to the store (aerie toolchains's layout), for the census to find without
# PATH knowing about it. `android` is a directory, not a command.
def _lay_path(store, entry, rel):
    """A layout path against the store. `root:` means the store itself;
    anything else is under the toolchain's own directory."""
    if rel.startswith("root:"):
        return os.path.join(store, rel[5:])
    return os.path.join(store, entry["dir"], rel) if rel else \
        os.path.join(store, entry["dir"])


def store_layout(state):
    """What the controller last told us about where toolchains land, or the
    built-in answer before it has said (the census a first hello carries)
    or when its catalog did not open.

    The controller's answer wins whenever there is one: a node follows it
    rather than a copy of its own that can drift.
    """
    got = state.get("layout")
    return got if isinstance(got, list) and got else BUILTIN_LAYOUT


# The answer this agent shipped with, used only when the controller has not
# sent one. Kept short and honest: it is a fallback, not a second authority.
BUILTIN_LAYOUT = [
    {"name": "jdk", "dir": "jdk", "bin": ["bin"], "env": {"JAVA_HOME": ""},
     "tool": "bin/java", "reports": "java"},
    {"name": "flutter", "dir": "flutter", "bin": ["bin"], "env": {},
     "tool": "bin/flutter", "reports": "flutter"},
    {"name": "dotnet", "dir": "dotnet", "bin": ["", "tools"],
     "env": {"DOTNET_ROOT": ""}, "tool": "dotnet", "reports": "dotnet"},
    {"name": "go", "dir": "go", "bin": ["bin"], "env": {}, "tool": "bin/go",
     "reports": "go"},
    {"name": "lint-tools", "dir": "lint-tools", "bin": ["bin"], "env": {},
     "tool": "bin/shellcheck", "reports": "shellcheck"},
    {"name": "node", "dir": "node", "bin": ["bin"], "env": {}, "tool": "bin/node",
     "reports": "node"},
    {"name": "swift", "dir": "swift", "bin": ["usr/bin"], "env": {},
     "tool": "usr/bin/swift", "reports": "swift"},
    {"name": "rust", "dir": "rust", "bin": ["cargo/bin"],
     "env": {"RUSTUP_HOME": "rustup", "CARGO_HOME": "cargo"},
     "tool": "cargo/bin/cargo", "reports": "rust"},
    {"name": "zig", "dir": "zig", "bin": [""], "env": {}, "tool": "zig", "reports": ""},
    {"name": "android-tools", "dir": "android-tools",
     "bin": ["root:android/cmdline-tools/latest/bin", "root:android/platform-tools"],
     "env": {}, "tool": "cmdline-tools/bin/sdkmanager", "reports": ""},
    {"name": "android:emulator", "dir": "android", "bin": ["root:android/emulator"],
     "env": {}, "tool": "root:android/emulator/emulator", "reports": "emulator"},
]

STORE_TOOLS = {"java": ("jdk/bin/java",), "flutter": ("flutter/bin/flutter",),
               "dotnet": ("dotnet/dotnet",), "go": ("go/bin/go",),
               "node": ("node/bin/node",), "swift": ("swift/usr/bin/swift",),
               "cargo": ("rust/cargo/bin/cargo",),
               # The BINARIES, not the directories they sit in. Checking the
               # directories called android-sdk present on a node whose
               # cmdline-tools was an empty folder and whose platform-tools
               # did not exist, so toolchain_gap admitted a job needing adb
               # and it failed there instead of being refused here.
               "android-sdk": ("android/platform-tools/adb",
                               "android/cmdline-tools/latest/bin/sdkmanager",
                               "android/cmdline-tools/bin/sdkmanager"),
               "emulator": ("android/emulator/emulator",),
               # adb on its own: a phone is driven from whichever node has
               # it, and the Phone tab's picker reads this.
               "adb": ("android/platform-tools/adb",),
               # web-ext beside it: pushing a Firefox extension to the phone
               # is web-ext driving that adb, on the same node.
               "web-ext": ("node/bin/web-ext",)}


def _own_tool(entry):
    """The layout's tool when it lives in the toolchain's own directory
    (`root:` names one elsewhere in the store)."""
    t = str(entry.get("tool") or "")
    return "" if t.startswith("root:") else t


def store_dirs(state):
    """What is actually IN the toolchain store, as directory names.

    The census's `toolchains` above is a placement summary (six names, so a
    job can select on them), and it was being read as an inventory of the
    whole catalog, which called four installed toolchains missing on a store
    the controller could see for itself. `aerie toolchains` puts each toolchain in
    <root>/<name>, and android's parts under <root>/android/, so the names
    ARE the inventory and this is one listdir.
    """
    store = tc_root(state)
    out = {"top": [], "android": []}
    if not store:
        return out
    # An empty directory is no toolchain: a delete that could not finish
    # (a file still open over NFS) or a mount point leaves one, and listed,
    # an empty android/platform-tools read as two Android rows installed on
    # a store wiped to start over (the operator, 12 Oct).
    def full(d):
        # ...nor one an install has not finished (its marker beside it,
        # sdk.sh sdk_mark_partial): half a toolchain left by an Abort read
        # as installed (the operator, 12 Oct).
        if os.path.exists(os.path.join(os.path.dirname(d), ".bb-installing." + os.path.basename(d))):
            return False
        with contextlib.suppress(OSError):
            if not os.path.isdir(d):
                return False
            with os.scandir(d) as entries:
                return any(True for _ in entries)
        return False
    with contextlib.suppress(OSError):
        out["top"] = sorted(x for x in os.listdir(store) if not x.startswith(".")
                            and full(os.path.join(store, x)))[:64]
    with contextlib.suppress(OSError):
        out["android"] = sorted(x for x in os.listdir(os.path.join(store, "android"))
                                if x.startswith(".") or full(os.path.join(store, "android", x)))[:64]
    # ...and the versions under android's versioned families (B712): what a
    # project pins (ndkVersion, buildToolsVersion, compileSdk) is a directory
    # here, one listdir each, and the controller says which pins this store
    # lacks. The key is sent even when empty: it is absent only where there
    # is no toolchain store, which the controller reads as "cannot say".
    vers = {}
    for sub in ("ndk", "build-tools", "platforms", "cmake"):
        d = os.path.join(store, "android", sub)
        with contextlib.suppress(OSError):
            vers[sub] = sorted(x for x in os.listdir(d)
                               if not x.startswith(".") and full(os.path.join(d, x)))[:64]
    out["versions"] = vers
    # A directory is not a toolchain: an install that stopped part-way leaves
    # one without the file that completes it (playwright's module beside its
    # browsers). A layout that names that file (`needs`) is checked here, and
    # the controller reads a name in this list as not installed.
    # Where none is named, the tool the layout runs is that file: a flutter
    # left with no bin/flutter (an install cut short before the marker
    # existed) was listed installed and `flutter` was not found (diagnostics
    # #124).
    for entry in store_layout(state):
        need = entry.get("needs") or _own_tool(entry)
        if not need or entry.get("dir", "").startswith("android"):
            continue
        d = os.path.join(store, entry["dir"])
        if os.path.isdir(d) and not os.path.exists(os.path.join(d, need)):
            out.setdefault("incomplete", []).append(entry["name"])
    # ...and the directories at the top of the store, whose names say whose
    # they are (a node's id, `shared`, the controller's own): a retired
    # node's is the controller's to offer for removal (R196).
    base = (state.get("stores") or {}).get("toolchains") or ""
    if base:
        with contextlib.suppress(OSError):
            out["roots"] = sorted(x for x in os.listdir(base)
                                  if not x.startswith(".") and os.path.isdir(os.path.join(base, x)))[:64]
    return out


# ---------------------------------------------------------------------------
# node.json

# The record in memory is changed by the agent's loop, its job threads and
# the configuration plane, and saved by each of them. Every change takes
# STATE_LOCK (State takes it for each of its own), and save_state holds it
# while it reads the console's keys into the record, dumps it and writes it:
# a dump never walks a record another thread is changing, and a change and
# the save that follows it are one step where the caller holds it around
# both. Reentrant for that. Taken before _save_lock, never after it.
STATE_LOCK = threading.RLock()


class State(dict):
    """node.json as the running agent holds it: a dict whose every change
    takes STATE_LOCK, and whose copy is taken under it."""

    def __setitem__(self, k, v):
        with STATE_LOCK:
            super().__setitem__(k, v)

    def __delitem__(self, k):
        with STATE_LOCK:
            super().__delitem__(k)

    def __ior__(self, other):
        with STATE_LOCK:
            return super().__ior__(other)

    def pop(self, *a):
        with STATE_LOCK:
            return super().pop(*a)

    def popitem(self):
        with STATE_LOCK:
            return super().popitem()

    def setdefault(self, *a):
        with STATE_LOCK:
            return super().setdefault(*a)

    def update(self, *a, **kw):
        with STATE_LOCK:
            super().update(*a, **kw)

    def clear(self):
        with STATE_LOCK:
            super().clear()

    def copy(self):
        with STATE_LOCK:
            return dict(self)


def load_state():
    try:
        with open(NODE_JSON) as f:
            got = json.load(f)
        return State(got) if isinstance(got, dict) else got
    except OSError as e:
        raise SystemExit(f"{NODE_JSON} is missing; enroll this node first: "
                         f"{names.command()} enroll --controller URL --token …") from e
    except ValueError as e:
        raise SystemExit(f"{NODE_JSON} is not JSON ({e}); enroll again") from e


# What this machine's console alone decides: the release key pinned here,
# the keys added beside it, whether an unsigned agent is taken, whether an
# older one may be put back and whether a person chose to pin no key
# (release.py), and whether a root
# command the controller sends is run at all (root_off, R227 step 2). A running agent holds
# node.json in memory and writes it whole at every token it is handed, so
# what the console wrote is read back from the file and kept, never the
# agent's older copy of it.
CONSOLE_KEYS = ("release_key", "release_spare", "release_also", "release_unpinned", "unsigned_ok", "older_ok", "root_off")


# What the provisioner writes into the record on a run after the enrollment
# (the session account it made, the tunnel it brought up), through
# record_set and the console's own lock. Like the console's keys, a running
# agent takes them from the file at every save and never from its own
# older copy, so a save between the provisioner's write and the restart it
# asks for does not take the change back.
RECORD_KEYS = ("session_user", "tunnel")


def record_set(key, value):
    """One of RECORD_KEYS set in node.json, or taken out with nothing, under
    the save's lock and through its whole-file write: read from the file,
    changed, and written as the console's own save writes. Whether it
    changed; an error where the record could not be read or written, which
    leaves it as it was."""
    if key not in RECORD_KEYS:
        raise ValueError(f"{key} is not the provisioner's to set")
    d = os.path.dirname(NODE_JSON)
    with _save_lock, open(os.path.join(d, ".node.json.lock"), "a") as held:
        fcntl.flock(held.fileno(), fcntl.LOCK_EX)
        with open(NODE_JSON) as f:
            cur = json.load(f)
        if not isinstance(cur, dict):
            raise ValueError(f"{NODE_JSON} does not hold a node's record")
        if (cur.get(key) or None) == (value or None):
            return False
        if value:
            cur[key] = value
        else:
            cur.pop(key, None)
        _save(cur, True, d)
    return True


def console_said():
    """The console's keys as node.json has them now, {} when it has none."""
    try:
        with open(NODE_JSON) as f:
            cur = json.load(f)
    except (OSError, ValueError):
        return {}
    return {k: cur[k] for k in CONSOLE_KEYS if isinstance(cur, dict) and k in cur}


# One save at a time (B982): node.json is saved by the agent's loop, its job
# threads and the configuration plane (a new token at every hello among
# them), and by the console's own commands in another process. Two saves
# through one fixed .tmp could interleave into a file that is not JSON,
# after which no start reads it and the node has to be enrolled again at its
# console. The thread lock orders this process's saves of a copy read from
# the file (record_set, pin_release, pin_spare); the file lock, on a file
# beside node.json, orders them against the console's.
_save_lock = threading.Lock()


def save_state(state, console=False):
    """node.json written whole, under STATE_LOCK: nothing changes `state`
    while the console's keys are read into it, it is dumped and it is
    written. `console` is a person at the machine saying what it trusts
    (enroll, release-key, unsigned): only then are the console's keys taken
    from `state`; otherwise the file's own are kept."""
    d = os.path.dirname(NODE_JSON)
    os.makedirs(d, mode=0o700, exist_ok=True)
    with STATE_LOCK, _save_lock, open(os.path.join(d, ".node.json.lock"), "a") as held:
        fcntl.flock(held.fileno(), fcntl.LOCK_EX)
        _save(state, console, d)


def pin_release(keys):
    """AerieOS's release key pinned by the agent itself, at the one moment
    it may (release.first_pin: a node that trusts no key, installing its
    first update a release signed): the key, set in
    node.json as the console's own save would write it, under the same
    lock and through the same whole-file write. The record is read here,
    under the lock, and not taken from the agent's copy: a key a person
    pinned or added at the console in the meantime stands, as does their
    choice to pin none (release-key none), and nothing is written. Whether
    these were pinned; an error where the record could not be read or
    written, which leaves it as it was."""
    keys = release.clean_keys(",".join(keys))
    d = os.path.dirname(NODE_JSON)
    with _save_lock, open(os.path.join(d, ".node.json.lock"), "a") as held:
        fcntl.flock(held.fileno(), fcntl.LOCK_EX)
        with open(NODE_JSON) as f:
            cur = json.load(f)
        if not isinstance(cur, dict):
            raise ValueError(f"{NODE_JSON} does not hold a node's record")
        if not keys or release.trusted(cur) or release.unpinned(cur):
            return False
        cur["release_key"] = keys[0]
        cur.pop("release_spare", None)
        if len(keys) > 1:
            cur["release_spare"] = keys[1]
        _save(cur, True, d)
    return True


def pin_spare(first, key):
    """The release key's spare pinned by the agent itself, on the release
    key's own signed word for it (release.spare_pin): set in node.json
    beside the key, under the lock and through the whole-file write the
    console's own save uses. The record is read here, under the lock: it is
    written only while it still holds `first` as its release key and no
    spare, and no choice to pin none, so what a person did at the console
    in the meantime stands. Whether the spare was pinned; an error where
    the record could not be read or written, which leaves it as it was."""
    first, key = release.clean_key(first), release.clean_key(key)
    d = os.path.dirname(NODE_JSON)
    with _save_lock, open(os.path.join(d, ".node.json.lock"), "a") as held:
        fcntl.flock(held.fileno(), fcntl.LOCK_EX)
        with open(NODE_JSON) as f:
            cur = json.load(f)
        if not isinstance(cur, dict):
            raise ValueError(f"{NODE_JSON} does not hold a node's record")
        if not first or not key or key == first or release.pinned(cur) != first or release.spare(cur) or release.unpinned(cur):
            return False
        cur["release_spare"] = key
        _save(cur, True, d)
    return True


def _save(state, console, d):
    if not console:
        try:
            with open(NODE_JSON) as f:
                cur = json.load(f)
        except (OSError, ValueError):
            cur = None
        if isinstance(cur, dict):
            for k in CONSOLE_KEYS + RECORD_KEYS:
                if k in cur:
                    state[k] = cur[k]
                else:
                    state.pop(k, None)
    text = json.dumps(state, indent=2)
    fd, tmp = tempfile.mkstemp(prefix=".node.json.", dir=d)
    try:
        with os.fdopen(fd, "w") as f:
            os.fchmod(f.fileno(), 0o600)
            f.write(text)
            # On the disk before its name points at it: a power cut after a
            # new token was used could bring back the one before, which the
            # controller had retired and reads as a stolen copy.
            try:
                f.flush()
                os.fsync(f.fileno())
            except OSError:
                pass
        os.replace(tmp, NODE_JSON)
    except BaseException:
        with contextlib.suppress(OSError):
            os.unlink(tmp)
        raise
    try:
        fd = os.open(d, os.O_RDONLY)
        try:
            os.fsync(fd)
        finally:
            os.close(fd)
    except OSError:
        pass
