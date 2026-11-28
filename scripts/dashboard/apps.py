"""The apps a person installs, shipped with every controller and kept current
by it: the Android app, the VS Code extension and the
Windows companion, each built for every release and attached to it with its
sha256 (the android app and companion app workflows).

Which of them this controller offers is chosen on the Settings page (the
apps_* switches, settings.py), or by the seed file a generator writes beside
a compose file, read once on the first boot and then put aside. At boot and
once a day the controller fetches each offered app from the release that
matches its own version (the newest release when none does, and says so),
holds it to the release's signed list of its files and to its sha256
file, keeps it under /config/apps, and serves it at /apps/NAME/FILE to
anybody signed in and to a device's app, which is how the companion keeps
itself current. Nothing here runs a file it fetched.

The signed list is what makes a file AerieOS's: the sha256 beside a file is
the release's word for itself, and whoever can replace a file on a release
can replace that too. The release's SHA256SUMS is fetched once a look, its
signature verified with ssh-keygen against this install's own
config/release-signers, and each file's bytes held to the digest the list
gives its name. The tag says who may have signed: the namespace a signer is
named for is the channel, a pre-release takes a list signed in either, and a
stable release takes aerieos-release alone, so the key the release build
holds can never sign one. A release whose list is unsigned, signed by
nobody this install names or by somebody its tag may not have, is refused
and said, and so is every release on an install that names no signer at
all: no app is taken from it. The rule the OS updater (osimage.py), the installer and the stick
maker follow; test_release_signing.py holds the four to one table of cases.

    configure(state=, version=, setting=, write_json=, audit=)
    view                     the Settings section's and the Library's reading
    check_now                look again, in the background
    path(name, file)           a held file's path, or None
    start                    the boot look and the daily one
    seed                     apply /config/seed.json once
"""
import base64
import hashlib
import json
import os
import re
import shutil
import subprocess
import tempfile
import threading
import time
import urllib.parse
import urllib.request
from pathlib import Path

import releasecheck
import seams

# The releases are AerieOS's own on GitHub; a test in the source tree
# points this at a file (seams.py).
RELEASES_URL = (seams.get("BB_APPS_RELEASES_URL")
                or "https://api.github.com/repos/aquilaelabs/aerieos/releases")
BOOT_DELAY = float(os.environ.get("BB_APPS_BOOT_DELAY") or 30)
EVERY = 24 * 3600
TIMEOUT = 60
MAX_BYTES = 200 << 20

# name -> what the pages say of it, and the files a release carries for it
# (a prefix and a suffix around the version). The first file is the one a
# person downloads; the rest go beside it.
APPS = {
    "android": {"title": "Android app", "setting": "apps_android",
                "does": "The notebook, the bell and your sessions on a phone, and the phone lent to a space.",
                "files": [("aerieos-app-", ".apk")]},
    # dev: offered only with Offer dev features on, until walked on a real
    # Windows PC and a real VS Code.
    "vscode": {"title": "VS Code extension", "setting": "apps_vscode", "dev": True,
               "does": "A space's files and its terminal in VS Code, opened from the controller.",
               "files": [("aerieos-vscode-", ".vsix")]},
    "companion": {"title": "Windows companion", "setting": "apps_companion", "dev": True,
                  "does": "A folder on a Windows PC kept in step with a space both ways, for a tool that only runs there.",
                  "files": [("aerieos-companion-", ".exe"), ("aerieos-companion-", ".pyz")]},
}
SAFE = re.compile(r"^[A-Za-z0-9][A-Za-z0-9._+-]{0,120}$")
# Who may sign a release: this build's own copy of config/release-signers,
# so a key is trusted because the install held it, never because a release
# names it. A test in the source tree names another file (seams.py).
SIGNERS = seams.get("BB_RELEASE_SIGNERS") or os.path.join(
    os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "..", "config", "release-signers")
SIG_RELEASE, SIG_DEV = "aerieos-release", "aerieos-dev"
SIGNED_BY = {SIG_RELEASE: "AerieOS's release key", SIG_DEV: "the key AerieOS's dev builds are signed with"}
NO_SIGNER = "this install names no release signer, so the release's signature cannot be checked"

# Each set by configure(); the defaults are the container's own paths.
DIR = Path("/config") / "apps"
SEED = Path("/config") / "seed.json"
INDEX = DIR / "index.json"


def _version():
    return ""


def _setting(key):
    return True


def write_json(path, data):
    raise RuntimeError("apps.configure() was not called")


audit = None
_lock = threading.Lock()
_state = {"checking": False}


def configure(*, state, version, setting, write_json, audit=None, container=None, registry_digest=None):
    globals().update(DIR=Path(state) / "apps", SEED=Path(state) / "seed.json", _version=version,
                     _setting=setting, write_json=write_json, audit=audit,
                     _container=container or (lambda: False), _registry_digest=registry_digest or (lambda ref: ("", "")))
    globals()["INDEX"] = DIR / "index.json"


_container = lambda: False                      # noqa: E731 (configure: the container edition)
_registry_digest = lambda ref: ("", "")         # noqa: E731 (configure: imagecheck.remote_digest)
IMAGE_REF = re.compile(r"[a-z0-9][a-z0-9.-]*(?::[0-9]+)?/[a-z0-9._/-]+@sha256:[0-9a-f]{64}")


def own_image(releases):
    """The container edition's image held to its signed release:
    the release for this very build, its signed
    list verified, the image reference its aerieos-image-VERSION.digest
    names, and what the registry serves under this version's tag now.
    {version, signed, registry, ok} where it could be told, {said} where
    the release cannot be read for it, {} on another edition or a build
    no release is for. A container cannot read its own image's digest, so
    what is held is the tag a person pulls this version by."""
    ver = str(_version() or "").split("+")[0]
    if not _container() or not ver:
        return {}
    tag = f"v{ver}"
    rel = next((r for r in releases if isinstance(r, dict) and r.get("tag_name") == tag and not r.get("draft")), None)
    if not rel:
        return {}
    listed, _sig, refused = _signed_list(rel)
    if refused:
        return {"version": ver, "said": refused}
    name = f"aerieos-image-{ver}.digest"
    asset = next((a for a in rel.get("assets") or [] if isinstance(a, dict) and a.get("name") == name), None)
    if not asset or name not in listed:
        return {"version": ver, "said": f"{tag} names no image in its signed list"}
    try:
        body = _get(_where(asset), 4096)
    except (OSError, ValueError, KeyError) as e:
        return {"version": ver, "said": f"{name} could not be read: {e}"}
    if hashlib.sha256(body).hexdigest() != listed[name]:
        return {"version": ver, "said": f"{name} is not the file {tag}'s signed list names"}
    ref = body.decode("ascii", "replace").strip()
    if not IMAGE_REF.fullmatch(ref):
        return {"version": ver, "said": f"{name} does not name an image by its digest"}
    repo, digest = ref.split("@", 1)
    have, why = _registry_digest(f"{repo}:{ver}")
    if not have:
        return {"version": ver, "signed": ref, "said": why or "the registry did not say"}
    return {"version": ver, "signed": ref, "registry": have, "ok": have == digest}


def image_attention(own_node_id):
    """The bell's row (kind image-signed) where the registry serves another
    image under this build's version than its signed release names."""
    im = _index().get("image") or {}
    if im.get("ok") is not False:
        return []
    return [{"kind": "image-signed", "id": own_node_id or "controller", "version": im.get("version", ""),
             "key": f"image-signed:{im.get('version')}:{str(im.get('registry') or '')[7:19]}"}]


# Whether dev features are offered (settings' offer_unvetted), set by server.py.
unvetted_ok = lambda: False  # noqa: E731


def offered(name):
    """On in Settings, and for a dev app, dev features on too: neither
    fetched, listed nor served otherwise."""
    a = APPS[name]
    return bool(_setting(a["setting"])) and (not a.get("dev") or bool(unvetted_ok()))


def _index():
    try:
        with open(INDEX) as f:
            d = json.load(f)
        return d if isinstance(d, dict) else {}
    except (OSError, ValueError):
        return {}


def base_version(v):
    """The release a build belongs to: 0.7.0 of 0.7.0-dev.3160+43218c1."""
    m = re.match(r"v?(\d+\.\d+\.\d+)", str(v or ""))
    return m.group(1) if m else ""


def view():
    """{apps: [...], checked, problem, release, matched, checking, version}:
    each app with whether it is offered, the files held of it and their
    sha256, for the Settings section and the Library's companion cards."""
    idx = _index()
    held = idx.get("apps") or {}
    out = []
    for name, a in APPS.items():
        h = held.get(name) or {}
        if a.get("dev") and not unvetted_ok():
            continue
        out.append({"name": name, "title": a["title"], "does": a["does"], "offered": offered(name), "dev": bool(a.get("dev")),
                    "version": h.get("version", ""), "absent": (idx.get("absent") or {}).get(name, ""),
                    "files": [{"file": f["file"], "sha256": f["sha256"], "size": f["size"],
                               "url": f"/apps/{name}/{f['file']}"}
                              for f in h.get("files") or []]})
    return {"apps": out, "checked": idx.get("checked", 0), "problem": idx.get("problem", ""),
            "release": idx.get("release", ""), "matched": bool(idx.get("matched")),
            # Who signed the release's list of files, or that nothing was checked.
            "signature": idx.get("signature", ""),
            # ...and the list and its signature, for a client that checks them
            # itself: {sums, sig (base64)} or None.
            "proof": idx.get("proof"),
            "checking": _state["checking"], "version": _version()}


def path(name, file):
    """A held file's path, or None: only a name the index holds, so a
    request can never name anything else under /config."""
    if name not in APPS or not SAFE.match(str(file or "")) or not offered(name):
        return None
    for f in ((_index().get("apps") or {}).get(name) or {}).get("files") or []:
        if f.get("file") == file:
            p = DIR / name / file
            return p if p.is_file() else None
    return None


def _get(url, limit=MAX_BYTES, accept="application/octet-stream, application/json"):
    # No credential: the apps come from AerieOS's public releases alone,
    # so a controller holds no GitHub token for them.
    req = urllib.request.Request(url, headers={"Accept": accept, "User-Agent": "builderbot-apps"})
    with urllib.request.urlopen(req, timeout=TIMEOUT) as r:                   # noqa: S310 (our releases, or a test's file)  # nosemgrep: python.lang.security.audit.dynamic-urllib-use-detected.dynamic-urllib-use-detected
        body = r.read(limit + 1)
    if len(body) > limit:
        raise ValueError(f"more than {limit >> 20} MB")
    return body


def _pick(releases, want):
    """The release for version `want`, else the newest that is published;
    (release, whether it matched)."""
    live = [r for r in releases if isinstance(r, dict) and not r.get("draft")]
    for r in live:
        if base_version(r.get("tag_name")) == want and want:
            return r, True
    return (live[0], False) if live else (None, False)


def _named(rel, prefix, suffix):
    """The name release `rel`'s build gives a file: PREFIX VERSION SUFFIX."""
    tag = str(rel.get("tag_name") or "")
    return f"{prefix}{tag[1:] if tag.startswith('v') else tag}{suffix}"


def _asset(rel, prefix, suffix):
    """Release `rel`'s file named for its version (_named): never another
    file with the prefix, which may be an older release's attached to this
    one with that release's own list."""
    want = _named(rel, prefix, suffix)
    if not SAFE.match(want):
        return None
    return next((a for a in rel.get("assets") or [] if isinstance(a, dict) and a.get("name") == want), None)


def signers():
    """The signer lines this install holds; none when the file is not there."""
    try:
        with open(SIGNERS, encoding="utf-8") as f:
            return [ln.strip() for ln in f if ln.strip() and not ln.lstrip().startswith("#")]
    except OSError:
        return []


# The signed list itself and its signature, by tag, as the last look read
# them: handed to the companion with the files, so it checks the signature
# with keys of its own and not on this controller's word.
_proof = {}


def _signed_list(rel):
    """({file: sha256}, what to say of it, "") for release `rel`'s SHA256SUMS
    when its signature is one the tag may carry, by a key this install
    names; (None, "", why) when the release is refused, as it is when this
    install names no signer: every build ships the file that names them,
    so an install without one has lost it."""
    keys = signers()
    tag = str(rel.get("tag_name") or "")
    if not keys:
        return None, "", NO_SIGNER
    kind = releasecheck.tag_kind(tag)
    if not kind:
        return None, "", f"{tag} is not a release's tag (vX.Y.Z, or vX.Y.Z-dev.N for a pre-release), so who may sign it cannot be told"
    if kind == "stable" and not any(k.split(None, 1)[0] == SIG_RELEASE for k in keys):
        return None, "", (f"{tag} is a stable release and no stable signer is named yet: this install names only the key "
                          "dev builds are signed with, and a stable release is signed by its own key's holder")
    assets = {str(a.get("name")): a for a in rel.get("assets") or [] if isinstance(a, dict)}
    try:
        sums = _get(_where(assets["SHA256SUMS"]), 1 << 20)
        sig = _get(_where(assets["SHA256SUMS.sig"]), 1 << 16)
    except (OSError, ValueError, KeyError) as e:
        # A release that does not carry the two files is said as that, with
        # no word of the lookup that missed; one that could not be read says why.
        why = "" if isinstance(e, KeyError) else f": {e}"
        return None, "", (f"{tag} carries no signed list of its files (SHA256SUMS and SHA256SUMS.sig{why}): it was made "
                          "before releases were signed, or its key's holder has not signed it yet")
    ns = ""
    try:
        with tempfile.TemporaryDirectory() as d:
            allowed, sigf = os.path.join(d, "signers"), os.path.join(d, "SHA256SUMS.sig")
            with open(allowed, "w", encoding="utf-8") as f:
                f.write("\n".join(keys) + "\n")
            with open(sigf, "wb") as f:
                f.write(sig)
            # Each signer is asked for in the one namespace it is named for.
            for want in (SIG_RELEASE, SIG_DEV):
                r = subprocess.run(["ssh-keygen", "-Y", "verify", "-f", allowed, "-I", want, "-n", want, "-s", sigf],
                                   input=sums, capture_output=True, check=False, timeout=TIMEOUT)
                if r.returncode == 0:
                    ns = want
                    break
    except (OSError, subprocess.SubprocessError) as e:
        return None, "", f"ssh-keygen is not here to check {tag}'s signature with ({e})"
    if not ns:
        return None, "", f"{tag}'s list of files is signed by no key this install names"
    if kind == "stable" and ns != SIG_RELEASE:
        return None, "", (f"{tag} is a stable release and its list is signed by the key dev builds are signed with: "
                          "a stable release takes its own key's signature alone")
    _proof[tag] = {"sums": sums.decode("utf-8", "replace"), "sig": base64.b64encode(sig).decode()}
    listed = {}
    for line in sums.decode("utf-8", "replace").splitlines():
        parts = line.split()
        if len(parts) == 2 and re.fullmatch(r"[0-9a-f]{64}", parts[0].lower()):
            listed[parts[1].lstrip("*")] = parts[0].lower()
    return listed, f"signed by {SIGNED_BY[ns]}", ""


def check():
    """Fetch each offered app from the matching release, check it, keep it,
    and drop what is no longer offered. Writes the index; returns view()."""
    idx = _index()
    held = idx.get("apps") or {}
    err, rel, matched = "", None, False
    image = idx.get("image") or {}
    try:
        releases = json.loads(_get(RELEASES_URL, 8 << 20))
        rel, matched = _pick(releases if isinstance(releases, list) else [], base_version(_version()))
        image = own_image(releases if isinstance(releases, list) else [])
        if not rel:
            err = "no published release to take the apps from"
    except (OSError, ValueError) as e:
        err = f"the releases did not answer: {e}"
        if "404" in str(e):
            err += " (the apps come from AerieOS's public releases, and its repository is not public yet)"
    DIR.mkdir(parents=True, exist_ok=True)
    # The release's signed list of its files, once a look: a release it may
    # not be taken on is said, nothing is fetched from it, and what is held
    # stays as it is.
    listed, signature, refused = None, "", ""
    if rel:
        listed, signature, refused = _signed_list(rel)
        if refused:
            err = f"{refused}: no app is taken from it"
    # An app the release carries no file of at all is said on its own row,
    # not as a look that did not work: a release may go out without one.
    absent = {}
    for name, a in APPS.items():
        if not offered(name):
            shutil.rmtree(DIR / name, ignore_errors=True)
            held.pop(name, None)
            continue
        if not rel or refused:
            continue
        _unhold(name, held, rel, listed)
        files, missing = [], []
        for prefix, suffix in a["files"]:
            asset = _asset(rel, prefix, suffix)
            if not asset:
                missing.append(_named(rel, prefix, suffix))
                continue
            sums = {str(x.get("name")): x for x in rel.get("assets") or []}
            sha_asset = sums.get(asset["name"] + ".sha256")
            if not sha_asset:
                missing.append(f"{asset['name']}.sha256")
                continue
            got = _keep(name, asset, sha_asset, held.get(name) or {}, listed, str(rel.get("tag_name") or ""))
            if isinstance(got, str):
                missing.append(got)
            else:
                files.append(got)
        if files:
            keep = {f["file"] for f in files}
            for old in (DIR / name).iterdir() if (DIR / name).is_dir() else []:
                if old.name not in keep:
                    old.unlink(missing_ok=True)
            held[name] = {"version": base_version(rel.get("tag_name")) or str(rel.get("tag_name") or ""),
                          "files": files, "at": int(time.time())}
        if not any(_asset(rel, prefix, suffix) for prefix, suffix in a["files"]):
            absent[name] = str(rel.get("tag_name") or "")
        elif missing and not err:
            err = f"{a['title']}: {', '.join(missing)} not in {rel.get('tag_name')}"
    tag = str((rel or {}).get("tag_name") or "")
    idx = {"apps": held, "checked": int(time.time()), "problem": err, "absent": absent, "signature": signature,
           "release": tag or idx.get("release") or "", "matched": matched,
           # The signed list the held files were taken on, kept for the
           # companion's own check; the one before stays while
           # nothing new was taken.
           "proof": _proof.get(tag) if tag and not refused else idx.get("proof"),
           # The container edition's image against its signed release.
           "image": image}
    write_json(INDEX, idx)
    return view()


def _unhold(name, held, rel, listed):
    """A file held of app `name` under a name the release carries, whose
    sha256 is not the one the release's signed list gives that name, is
    held no longer: it was kept on the sha256 beside it, before the list
    was asked. A file of another release is left for its successor."""
    h = held.get(name) or {}
    carried = {str(a.get("name")) for a in rel.get("assets") or [] if isinstance(a, dict)}
    good = [f for f in h.get("files") or [] if f.get("file") not in carried or listed.get(f.get("file")) == f.get("sha256")]
    if len(good) == len(h.get("files") or []):
        return
    for f in h.get("files") or []:
        if f not in good and SAFE.match(str(f.get("file") or "")):
            (DIR / name / f["file"]).unlink(missing_ok=True)
    if good:
        held[name] = {**h, "files": good}
    else:
        held.pop(name, None)


def _keep(name, asset, sha_asset, was, listed, tag=""):
    """One file of an app: kept as it is when the sha256 has not moved,
    else downloaded and checked, against the release's signed list
    (`listed`, {file: sha256}) and the sha256 beside it. Its index entry,
    or a sentence."""
    try:
        want = _get(_where(sha_asset), 4096).decode("ascii", "replace").split()[0].lower()
    except (OSError, ValueError, IndexError, KeyError) as e:
        return f"{sha_asset.get('name')} ({e})"
    if not re.fullmatch(r"[0-9a-f]{64}", want):
        return f"{sha_asset.get('name')} is not a sha256"
    if asset["name"] not in listed:
        return f"{asset['name']} is not in the list of files {tag} signed"
    dest = DIR / name / asset["name"]
    for f in was.get("files") or []:
        if (f.get("file") == asset["name"] and f.get("sha256") == want and dest.is_file()
                and listed[asset["name"]] == want):
            return f
    try:
        body = _get(_where(asset))
    except (OSError, ValueError, KeyError) as e:
        return f"{asset['name']} ({e})"
    have = hashlib.sha256(body).hexdigest()
    # The file's own bytes against the list, whatever the sha256 beside it says.
    if listed[asset["name"]] != have:
        return f"{asset['name']} is not the file {tag} signed: its bytes are not the ones the signed list names"
    if have != want:
        return f"{asset['name']} does not match its sha256"
    dest.parent.mkdir(parents=True, exist_ok=True)
    tmp = dest.with_name(dest.name + ".part")
    tmp.write_bytes(body)
    os.replace(tmp, dest)
    return {"file": asset["name"], "sha256": want, "size": len(body)}


def _where(asset):
    """Where a release's file is read from: its public download link."""
    return asset["browser_download_url"]


def check_now():
    """Look again in the background; False when a look is already going."""
    with _lock:
        if _state["checking"]:
            return False
        _state["checking"] = True

    def run():
        try:
            check()
        except Exception as e:              # noqa: BLE001 (said on the section)
            write_json(INDEX, {**_index(), "checked": int(time.time()), "problem": f"{type(e).__name__}: {e}"})
        finally:
            _state["checking"] = False
    threading.Thread(target=run, daemon=True, name="apps-check").start()
    return True


def start():
    """The look at boot, a while after it, and then once a day."""
    def loop():
        time.sleep(BOOT_DELAY)
        while True:
            check_now()
            time.sleep(EVERY)
    threading.Thread(target=loop, daemon=True, name="apps-loop").start()


# ---- the seed file -------------------------------------------
#
# /config/seed.json, written by a compose generator beside the compose file:
#
#     {"version": 1, "apps": ["android", "companion"]}
#
# Read once, on the first boot that finds it: each app named is offered and
# each one left out is not. It is then renamed seed.json.applied, so Settings
# owns the choice from there and a later edit of the file changes nothing.

def seed(set_many):
    """Apply the seed file once; what it set, or {} when there was none."""
    try:
        d = json.loads(SEED.read_text())
    except FileNotFoundError:
        return {}
    except (OSError, ValueError) as e:
        return {"error": f"seed.json not read: {e}"}
    if not isinstance(d, dict):
        return {"error": "seed.json is not an object"}
    changes = {}
    if isinstance(d.get("apps"), list):
        names = {str(x) for x in d["apps"]}
        changes = {a["setting"]: name in names for name, a in APPS.items()}
        set_many(changes)
    try:
        os.replace(SEED, SEED.with_name("seed.json.applied"))
    except OSError:
        pass
    if audit:
        audit("controller", "seed", "seed.json", changes)
    return changes
