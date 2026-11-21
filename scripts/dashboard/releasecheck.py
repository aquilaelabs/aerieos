"""A newer AerieOS release, for a controller installed bare metal (R90
step 5): the newest published release asked of GitHub a while after the
start and then daily, kept in memory, said on the bell and under Controller
settings when it is newer than the build running, and applied when pressed
as a system job on the controller's own node (its root agent runs the
installer's --update; the controller's account never does).

The container edition has its own path (the image, pulled by the host), so
nothing here is drawn for it: `attention` and `status` answer nothing when
the install is not bare metal.

What a release says its container image is (R199) is read here too, for
whoever compares an image with a registry's tag (imagecheck.py): each
release carries one line naming the image its tag pushed by digest
(aerieos-image-VER.digest), in the release's signed list of its files, so a
registry's `:dev` or `:latest` can be held to what the newest signed
release names (signed_image).
"""
import contextlib
import hashlib
import json
import os
import re
import shutil
import threading
import time
import urllib.request

import seams

RELEASES_URL = (seams.get("BB_APPS_RELEASES_URL")
                or "https://api.github.com/repos/aquilaelabs/aerieos/releases")
BOOT_DELAY = float(os.environ.get("BB_RELEASE_BOOT_DELAY") or 120)
EVERY = 24 * 3600
TIMEOUT = 30
VER = re.compile(r"^v?(\d+)\.(\d+)\.(\d+)$")
# A dev build's tag (R179): the release it heads for and its ordinal.
# A pre-release of any name (R218): vX.Y.Z-dev.N, -rc.N, -beta.N, N the
# commit's ordinal whatever the name, so one number orders them all.
DEV = re.compile(r"^v?(\d+)\.(\d+)\.(\d+)-[a-z][a-z0-9]*\.(\d+)(?:\+[0-9a-f]+)?$")
# A release's tag by its shape, which is what says which release it is: a
# stable one is vX.Y.Z, a pre-release has a name and the commit's ordinal
# after it. The channel a release is offered on and who may have signed its
# list of files (R199) both follow the tag, never the flag the git host
# keeps beside it, which whoever can edit a release can flip.
STABLE_TAG = re.compile(r"v\d+\.\d+\.\d+")
PRE_TAG = re.compile(r"v\d+\.\d+\.\d+-[a-z][a-z0-9]*\.\d+")
# AerieOS's own container image, as a registry names it, and the tags of it
# people follow: publishing a release moves :dev onto it, and a stable
# release :latest too (publish-release.yml).
IMAGE = os.environ.get("BB_RELEASE_IMAGE") or "ghcr.io/aquilaelabs/aerieos"
FOLLOWED = ("dev", "latest")
# The one line of a release's aerieos-image-VER.digest: the image by digest.
IMAGE_LINE = re.compile(r"([a-z0-9][a-z0-9._/:-]{0,200})@(sha256:[0-9a-f]{64})")
# How many of the newest releases are asked for one that names its image.
IMAGE_LOOK = 3

_lock = threading.Lock()
_latest = {"version": "", "tag": "", "at": 0, "error": "", "checking": False, "url": "", "dev": {"version": "", "tag": "", "url": ""}}
_version = lambda: ""       # noqa: E731 (configured)
_bare = lambda: False       # noqa: E731
_channel = lambda: "normal"  # noqa: E731 (configured: the release channel picked)
_debug = lambda: False      # noqa: E731 (configured: a controller in debug mode)
_window = lambda: ("", 4)   # noqa: E731 (the update window: day, hour)
_apply = lambda v: None     # noqa: E731 (queue the update to version v)
_applied = {"version": ""}  # the version the window last queued, so one window queues once
# Drafts (the operator, 1 and 2 Nov): a controller in debug mode on the dev channel
# holding a token for AerieOS's repository sees its draft releases too,
# and updates from one by fetching its files with that token.
_draft_token = lambda: ""   # noqa: E731 (configured)
_drafts = {}                # tag: its assets, from the last check that saw drafts
_fetch = {"tag": "", "at": 0, "error": "", "done": False}
_versions = []              # {tag, draft}, newest first, from the last check
DAYS = ("mon", "tue", "wed", "thu", "fri", "sat", "sun")


def configure(*, version, bare_metal, window=None, apply=None, channel=None, debug=None, draft_token=None):
    globals().update(_version=version, _bare=bare_metal, _window=window or _window, _apply=apply or _apply,
                     _channel=channel or (lambda: "normal"), _debug=debug or (lambda: False),
                     _draft_token=draft_token or (lambda: ""))


def _token():
    """The token drafts are asked with: on the dev channel alone, and only
    ever to GitHub's own API."""
    if channel() != "dev" or not RELEASES_URL.startswith("https://api.github.com/"):
        return ""
    try:
        return str(_draft_token() or "")
    except Exception:                                               # noqa: BLE001 (no token is the answer)
        return ""


def channel():
    """The channel in force."""
    return "dev" if _channel() == "dev" else "normal"


def in_window(now=None):
    """Whether this hour is the update window the person set (R160 step 4):
    daily or one weekday, at the hour named; "" is no window, the default,
    and nothing is applied by itself then."""
    day, hour = _window()
    if not day:
        return False
    t = time.localtime(now if now is not None else time.time())
    if day != "daily" and DAYS[t.tm_wday] != day:
        return False
    return t.tm_hour == int(hour)


def window_pass(now=None):
    """One look, every few minutes from the loop: in the window with a
    newer release not yet queued, the update is queued once (the own node's
    job: the image on AerieOS, the installer elsewhere), and said
    where the job's log and the bell say the rest. Returns what it queued."""
    v = newer() if _bare() else ""
    if not v or not in_window(now) or _applied["version"] == v:
        return ""
    _applied["version"] = v
    try:
        _apply(v)
    except Exception as e:                                          # noqa: BLE001 (said, and the next window tries again)
        print(f"[dashboard] update window: {type(e).__name__}: {e}", flush=True)
        _applied["version"] = ""
        return ""
    return v


def tag_kind(tag):
    """"stable" for a stable release's tag, "pre" for a pre-release's, ""
    for anything else."""
    t = str(tag or "")
    return "stable" if STABLE_TAG.fullmatch(t) else "pre" if PRE_TAG.fullmatch(t) else ""


def parse(v):
    """(major, minor, patch) of a released version, or None for anything
    else (a dev build, unstamped)."""
    m = VER.match(str(v or "").strip())
    return tuple(int(x) for x in m.groups()) if m else None


def parse_dev(v):
    """(major, minor, patch, ordinal) of a dev build or any pre-release, or its tag, or None."""
    m = DEV.match(str(v or "").strip())
    return tuple(int(x) for x in m.groups()) if m else None


def rank(v):
    """Where a version stands across both channels: a release above every
    dev build heading for it, a dev build by its ordinal; None for neither."""
    r = parse(v)
    if r:
        return (*r, 10 ** 9)
    return parse_dev(v)


def _read():
    """What the releases list says now, for the record: ({version, tag, url}
    of the newest release when there is one, with the dev channel's newest
    under dev when the list was read, why not). The versions debug mode
    picks from and the drafts' files are kept as it reads."""
    version, tag, url, error = "", "", "", ""
    token = _token()
    try:
        # A page long enough that dev builds never push the newest release off it.
        url_ = RELEASES_URL + ("?per_page=100" if RELEASES_URL.startswith("https://") else "")
        req = urllib.request.Request(url_, headers={"Accept": "application/json", "User-Agent": "aerieos-release"})
        if token:
            req.add_unredirected_header("Authorization", f"Bearer {token}")
        with urllib.request.urlopen(req, timeout=TIMEOUT) as r:   # noqa: S310 (our releases, or a test's file://)  # nosemgrep: python.lang.security.audit.dynamic-urllib-use-detected.dynamic-urllib-use-detected
            rows = json.loads(r.read(8 << 20) or b"[]")
        # The stable channel's: a release whose tag is a stable release's
        # (tag_kind), whatever the pre-release flag beside it says. The flag
        # is the git host's, flipped by whoever can edit a release; the tag
        # is what the release's files are signed for. A stable release's
        # draft too where asked with the token.
        live = [x for x in rows if isinstance(x, dict) and (token or not x.get("draft")) and tag_kind(x.get("tag_name")) == "stable"]
        live.sort(key=lambda x: parse(x.get("tag_name")), reverse=True)
        if live:
            tag = str(live[0].get("tag_name") or "")
            version = ".".join(str(n) for n in parse(tag))
            url = str(live[0].get("html_url") or "")
        else:
            error = "no published release"
        # The dev channel's newest (R179): a pre-release whose tag is a dev
        # build's, never taken on the normal channel; a draft only where
        # it was asked with the token (debug mode, the dev channel).
        dev = [x for x in rows if isinstance(x, dict) and (token or not x.get("draft")) and parse_dev(x.get("tag_name"))
               and (x.get("prerelease") or x.get("draft"))]
        dev.sort(key=lambda x: parse_dev(x.get("tag_name")), reverse=True)
        devrec = {"version": str(dev[0]["tag_name"]).lstrip("v"), "tag": str(dev[0]["tag_name"]), "url": str(dev[0].get("html_url") or ""),
                  "draft": dev[0].get("draft") is True} if dev else {"version": "", "tag": "", "url": "", "draft": False}
        # Every version there is, newest first, for debug mode's picker.
        picks = [x for x in rows if isinstance(x, dict) and rank(str(x.get("tag_name") or "").lstrip("v"))
                 and (token or not x.get("draft"))]
        picks.sort(key=lambda x: rank(str(x["tag_name"]).lstrip("v")), reverse=True)
        _versions[:] = [{"tag": str(x["tag_name"]), "draft": x.get("draft") is True} for x in picks[:40]]
        if token:
            _drafts.clear()
            _drafts.update({str(x["tag_name"]): [a for a in x.get("assets") or [] if isinstance(a, dict)]
                            for x in rows if isinstance(x, dict) and x.get("draft") and x.get("tag_name")})
    except (OSError, ValueError) as e:
        error = f"the releases did not answer: {e}"[:200]
        devrec = None
    return {**({"version": version, "tag": tag, "url": url} if version else {}),
            **({"dev": devrec} if devrec is not None else {})}, error


def check():
    """Ask what the newest published release is, now. The record."""
    import checks
    return checks.guarded(_lock, lambda: _latest, _read)


def latest():
    with _lock:
        return dict(_latest)


def newer():
    """The newest version on the channel in force when it is newer than
    the build running, else "". On the normal channel a released version
    alone; on the dev channel the newest of the releases and the dev
    pre-releases. Both by rank, so a dev build moves to a later dev build
    (dev channel) or to the release it was heading for (either channel: a
    build that picked Releases again is offered the release, B618)."""
    lt = latest()
    now = rank(_version()) or rank(str(_version() or "").split("+")[0]) or parse(str(_version() or "").split("-")[0])
    if now and len(now) == 3:
        now = (*now, 10 ** 9)
    if channel() == "dev":
        best = max((v for v in (lt.get("version", ""), (lt.get("dev") or {}).get("version", "")) if rank(v)), key=rank, default="")
        return best if best and now and rank(best) > now else ""
    want = rank(lt.get("version"))
    return lt["version"] if want and now and want > now else ""


def status():
    """What the page draws: nothing on a container install. The channel in
    force, the dev channel's newest, and in debug mode every version to pick."""
    if not _bare():
        return {}
    lt = latest()
    return {"running": _version(), "latest": lt.get("version", ""), "newer": newer(), "at": lt.get("at", 0),
            "error": lt.get("error", ""), "url": lt.get("url", ""),
            "channel": channel(), "pick": list(_versions) if _debug() else [], "dev_latest": (lt.get("dev") or {}).get("version", ""),
            "dev_draft": bool((lt.get("dev") or {}).get("draft")), "draft_fetch": dict(_fetch)}


def is_draft(tag):
    """Whether `tag` is a draft the last check saw (with the token)."""
    return bool(_token()) and str(tag) in _drafts


# What an AerieOS update takes from a release's folder (osimage).
def _os_files(tag):
    ver = str(tag).lstrip("v")
    return {f"aerieos-os-{ver}.iso", f"aerieos-os-{ver}.iso.sha256", f"aerieos-os-{ver}.attestation.jsonl",
            "SHA256SUMS", "SHA256SUMS.sig"}


def fetch_draft(tag, dest):
    """The draft's AerieOS files fetched into `dest` with the token, as
    a folder update reads them: "" or why. Said on the Updates section as it
    goes (status's draft_fetch)."""
    token = _token()
    assets = _drafts.get(str(tag)) or []
    want = _os_files(tag)
    got = [a for a in assets if a.get("name") in want and str(a.get("url") or "").startswith("https://api.github.com/")]
    need = 2 * sum(int(a.get("size") or 0) for a in got)
    with contextlib.suppress(OSError):
        os.makedirs(os.path.dirname(dest), exist_ok=True)
        if shutil.disk_usage(os.path.dirname(dest)).free < need:
            _fetch.update(tag=str(tag), at=int(time.time()), error=f"no room for the draft's {need >> 20} MB here", done=False)
            return _fetch["error"]
    _fetch.update(tag=str(tag), at=int(time.time()), error="", done=False)
    if not token or not any(str(a.get("name")).endswith(".iso") for a in got):
        _fetch["error"] = f"{tag} is not a draft this controller can see, or it carries no AerieOS image yet"
        return _fetch["error"]
    try:
        os.makedirs(dest, exist_ok=True)
        for a in got:
            req = urllib.request.Request(str(a["url"]), headers={"Accept": "application/octet-stream", "User-Agent": "aerieos-release"})
            req.add_unredirected_header("Authorization", f"Bearer {token}")
            with urllib.request.urlopen(req, timeout=600) as r, open(os.path.join(dest, str(a["name"])), "wb") as f:  # noqa: S310 (GitHub's API, checked above)  # nosemgrep: python.lang.security.audit.dynamic-urllib-use-detected.dynamic-urllib-use-detected
                shutil.copyfileobj(r, f, 1 << 20)
    except (OSError, ValueError) as e:
        _fetch["error"] = f"the draft's files did not come: {e}"[:200]
        return _fetch["error"]
    _fetch["done"] = True
    return ""


def signed_image(follow):
    """What the newest signed release says its container image is, for the
    tag of it somebody follows (`dev`: every published release; `latest`:
    the stable ones): {tag, image, digest, ref, signed}, ref the image by
    its digest and signed who signed the release's list of files. {why}
    where none says: no release published, or none whose list this install
    takes (the one check the Library's downloads make, apps._signed_list).
    A release whose list is not taken is passed over for the one before
    it, since what it names is nobody's word; one that is signed and names
    no image, or whose image file is not the one its list names, ends the
    look with that said, never an older release's image in its place.
    Published releases alone, asked without a token."""
    import apps
    kinds = ("stable",) if follow == "latest" else ("stable", "pre")
    try:
        rows = json.loads(apps._get(RELEASES_URL + ("?per_page=100" if RELEASES_URL.startswith("https://") else ""), 8 << 20))
    except (OSError, ValueError) as e:
        return {"why": f"the releases did not answer: {e}"[:200]}
    live = [r for r in rows if isinstance(r, dict) and not r.get("draft") and tag_kind(r.get("tag_name")) in kinds]
    live.sort(key=lambda r: rank(str(r["tag_name"]).lstrip("v")), reverse=True)
    why = "there is no published release"
    for rel in live[:IMAGE_LOOK]:
        tag = str(rel["tag_name"])
        listed, signature, refused = apps._signed_list(rel)
        if listed is None:
            # Not taken, or nothing here to check it with: said if no
            # release before it answers either.
            why = refused or signature
            continue
        name = f"aerieos-image-{tag.lstrip('v')}.digest"
        asset = next((a for a in rel.get("assets") or [] if isinstance(a, dict) and a.get("name") == name), None)
        if name not in listed or not asset:
            return {"tag": tag, "why": f"{tag} is signed and names no image: it was made before a release said which image is its own"}
        try:
            body = apps._get(apps._where(asset), 4096)
        except (OSError, ValueError) as e:
            return {"tag": tag, "why": f"{tag}'s {name} did not come: {e}"[:200]}
        m = IMAGE_LINE.fullmatch(body.decode("utf-8", "replace").strip())
        if hashlib.sha256(body).hexdigest() != listed[name] or not m:
            return {"tag": tag, "why": f"{tag}'s {name} is not the file its signed list names, so which image is {tag}'s cannot be told"}
        return {"tag": tag, "image": m.group(1), "digest": m.group(2), "ref": f"{m.group(1)}@{m.group(2)}", "signed": signature}
    return {"why": why}


def attention(own_node_id):
    """The bell's row (kind release), for a bare-metal install behind the
    newest release, keyed on the version it would move to, so a dismissal
    holds until the next one."""
    v = newer() if _bare() else ""
    if not v or not own_node_id:
        return []
    return [{"kind": "release", "id": own_node_id, "from": _version(), "to": v, "key": f"release:{v}"}]


def start():
    """The check on a thread, a while after the start, then on its cadence
    (checks.py: weekly unless set), and the window looked at every ten
    minutes between checks."""
    def loop():
        time.sleep(BOOT_DELAY)
        import checks
        while True:
            try:
                # On its cadence (R176, weekly unless set), from when it last
                # ran, which outlives a restart.
                if checks.due("release", checks.stamped("release")):
                    check()
                    checks.stamp("release")
                window_pass()
            except Exception as e:                                  # noqa: BLE001 (the loop outlives one bad pass)
                print(f"[dashboard] release check: {type(e).__name__}: {e}", flush=True)
            time.sleep(600)
    threading.Thread(target=loop, name="release-check", daemon=True).start()
