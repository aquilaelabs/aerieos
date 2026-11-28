"""The app kept current by its controller: a person's device,
not a machine of the controller's, so nothing pushes to it; the app asks.

At start and once a day it asks its controller's door what the controller
holds of it (the apps verb), and when that is newer than itself it
fetches the file it runs as (the .exe, or the .pyz), checks it against the
controller's sha256 and, where this copy is signed, that the new one is
signed too, and leaves it beside itself. The next start swaps it in
(apply_pending) and starts again from it. Run from a checkout, it is never
replaced: the checkout is somebody's working tree.
"""
import hashlib
import os
import pkgutil
import re
import subprocess
import sys
import urllib.parse

DOOR = 1                # the device door this app speaks (devices.DOOR)
NEEDS_DOOR = 1          # the oldest controller door this app works with


def headers():
    """What this app says on every call: the door it speaks and which app
    and release it is, so a controller can refuse it by name."""
    return {"X-BB-Door": str(DOOR), "X-BB-App": f"companion/{version()}"}


def controller_too_old(answer):
    """The plain sentence for a controller older than this app, from the
    door it said in a projects or apps answer, or "". One that says none
    predates the handshake and speaks door 1."""
    said = (answer or {}).get("door") if isinstance(answer, dict) else None
    try:
        theirs = 1 if said is None else int(said)
    except (TypeError, ValueError):
        theirs = 0
    if theirs >= NEEDS_DOOR:
        return ""
    return (f"the controller speaks door {theirs} and this companion needs {NEEDS_DOOR} or newer: "
            "update AerieOS on the controller, or use the companion it offers")


def version():
    """The release this copy was built for (its VERSION, written by the
    build), or 0.0.0 for a checkout."""
    try:
        return (pkgutil.get_data("bbcompanion", "VERSION") or b"").decode().strip() or "0.0.0"
    except OSError:
        return "0.0.0"


def _parts(v):
    """Where a version stands: X.Y.Z, then a dev build (-dev.N) before the
    release it leads to and by its number, so one dev build is newer than
    the last (-dev.N was ignored, and a dev companion never moved)."""
    m = re.match(r"v?(\d+)\.(\d+)\.(\d+)(?:-[a-z][a-z0-9]*\.(\d+))?", str(v or ""))
    if not m:
        return (0, 0, 0, 0, 0)
    return (int(m[1]), int(m[2]), int(m[3]), 0 if m[4] else 1, int(m[4] or 0))


def newer(theirs, mine):
    return _parts(theirs) > _parts(mine)


def running_as():
    """("exe" | "pyz", the file) for a packaged copy; ("", "") from a
    checkout, which is never replaced."""
    if getattr(sys, "frozen", False):
        return "exe", os.path.abspath(sys.executable)
    me = os.path.abspath(sys.argv[0] if sys.argv else "")
    if me.endswith(".pyz") and os.path.isfile(me):
        return "pyz", me
    return "", ""


def _sha256(path):
    h = hashlib.sha256()
    with open(path, "rb") as f:
        for chunk in iter(lambda: f.read(1 << 20), b""):
            h.update(chunk)
    return h.hexdigest()


def signed(path):
    """Whether Windows trusts the file's Authenticode signature; None off
    Windows, where there is none to ask about."""
    if os.name != "nt":
        return None
    import ctypes
    from ctypes import wintypes

    class FileInfo(ctypes.Structure):
        _fields_ = [("cbStruct", wintypes.DWORD), ("pcwszFilePath", wintypes.LPCWSTR),
                    ("hFile", wintypes.HANDLE), ("pgKnownSubject", ctypes.c_void_p)]

    class TrustData(ctypes.Structure):
        _fields_ = [("cbStruct", wintypes.DWORD), ("pPolicyCallbackData", ctypes.c_void_p),
                    ("pSIPClientData", ctypes.c_void_p), ("dwUIChoice", wintypes.DWORD),
                    ("fdwRevocationChecks", wintypes.DWORD), ("dwUnionChoice", wintypes.DWORD),
                    ("pFile", ctypes.POINTER(FileInfo)), ("dwStateAction", wintypes.DWORD),
                    ("hWVTStateData", wintypes.HANDLE), ("pwszURLReference", wintypes.LPCWSTR),
                    ("dwProvFlags", wintypes.DWORD), ("dwUIContext", wintypes.DWORD)]

    class Guid(ctypes.Structure):
        _fields_ = [("a", wintypes.DWORD), ("b", wintypes.WORD), ("c", wintypes.WORD), ("d", ctypes.c_ubyte * 8)]

    # WINTRUST_ACTION_GENERIC_VERIFY_V2
    action = Guid(0xAAC56B, 0xCD44, 0x11D0, (ctypes.c_ubyte * 8)(0x8C, 0xC2, 0x00, 0xC0, 0x4F, 0xC2, 0x95, 0xEE))
    fi = FileInfo(ctypes.sizeof(FileInfo), path, None, None)
    td = TrustData(ctypes.sizeof(TrustData), None, None, 2, 0, 1, ctypes.pointer(fi), 0, None, None, 0, 0)
    return ctypes.windll.wintrust.WinVerifyTrust(None, ctypes.byref(action), ctypes.byref(td)) == 0


# Who may sign a release, as AerieOS's own config/release-signers names them,
# carried in this copy (the build puts the file beside VERSION), and the
# namespace each signs in (apps.py's SIG_RELEASE and SIG_DEV).
NAMESPACES = ("aerieos-release", "aerieos-dev")


def signers():
    """The release signers this copy carries, as ssh-keygen's allowed
    signers lines; a checkout reads the repository's own file."""
    try:
        text = (pkgutil.get_data("bbcompanion", "release-signers") or b"").decode()
    except OSError:
        text = ""
    if not text.strip():
        here = os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "..", "..", "config", "release-signers")
        try:
            with open(here, encoding="utf-8") as f:
                text = f.read()
        except OSError:
            text = ""
    return [ln for ln in text.splitlines() if ln.strip() and not ln.lstrip().startswith("#")]


def proven(proof, name, sha):
    """Why the file `name` with `sha` is not one the release's signed list
    names under a key this copy carries, or "" when it is: the list's
    signature checked here with Windows' own ssh-keygen (OpenSSH Client),
    never on the controller's word."""
    keys = signers()
    if not keys:
        return "this copy carries no release signer to check the update with"
    if not isinstance(proof, dict) or not proof.get("sums") or not proof.get("sig"):
        return "the controller sent no signed list of the release's files"
    import base64
    import tempfile
    try:
        with tempfile.TemporaryDirectory() as d:
            allowed, sigf = os.path.join(d, "signers"), os.path.join(d, "SHA256SUMS.sig")
            with open(allowed, "w", encoding="utf-8") as f:
                f.write("\n".join(keys) + "\n")
            with open(sigf, "wb") as f:
                f.write(base64.b64decode(proof["sig"]))
            ok = False
            for ns in NAMESPACES:
                r = subprocess.run(["ssh-keygen", "-Y", "verify", "-f", allowed, "-I", ns, "-n", ns, "-s", sigf],
                                   input=proof["sums"].encode(), capture_output=True, check=False, timeout=30,
                                   **({"creationflags": 0x08000000} if os.name == "nt" else {}))
                if r.returncode == 0:
                    ok = True
                    break
    except (OSError, ValueError, subprocess.SubprocessError):
        return "this PC has no ssh-keygen to check the update's signature with (Windows' OpenSSH Client)"
    if not ok:
        return "the release's list of files is signed by no key this copy carries"
    listed = {}
    for line in proof["sums"].splitlines():
        parts = line.split()
        if len(parts) == 2 and re.fullmatch(r"[0-9a-f]{64}", parts[0].lower()):
            listed[parts[1].lstrip("*")] = parts[0].lower()
    if listed.get(name) != str(sha or "").lower():
        return f"{name} is not in the release's signed list as it was fetched"
    return ""


def check(ctl):
    """Ask the controller what it holds of this app and fetch it when it is
    newer: {current | pending | said}. `ctl` is the door's connection."""
    kind, me = running_as()
    st, r = ctl.call("apps", {})
    if st != 200:
        return {"said": f"could not ask the controller for updates ({(r or {}).get('error') or st})"}
    app = next((a for a in r.get("apps") or [] if a.get("name") == "companion"), None)
    if not app:
        return {"said": "this controller does not offer the companion: it is not updated from here"}
    mine = version()
    if not newer(app.get("version"), mine):
        return {"current": mine}
    if not kind:
        return {"said": f"{app['version']} is out; this copy runs from a checkout, which is never replaced"}
    f = next((x for x in app.get("files") or [] if x.get("file", "").endswith("." + kind)), None)
    if not f:
        return {"said": f"{app['version']} is out, but not as a .{kind}"}
    dest = me + ".new"
    code, _ = ctl.fetch("app-file?app=companion&file=" + urllib.parse.quote(f["file"]), dest)
    if code != 200:
        return {"said": f"the update did not download ({code})"}
    if _sha256(dest) != f.get("sha256"):
        os.remove(dest)
        return {"said": "the update did not match the controller's sha256: not kept"}
    # ...and its sha256 one the release's signed list gives it, the list's
    # signature checked here with the keys this copy carries.
    if why := proven(r.get("proof"), f["file"], _sha256(dest)):
        os.remove(dest)
        return {"said": f"{why}: the update is not kept"}
    if signed(me) and not signed(dest):
        os.remove(dest)
        return {"said": "the update is not signed where this copy is: not kept"}
    with open(dest + ".sha256", "w") as w:
        w.write(f["sha256"] + "\n")
    return {"pending": app["version"]}


def apply_pending(argv=None):
    """At start: a fetched update swapped in for this copy and started in
    its place, or nothing. Returns only when nothing was swapped."""
    kind, me = running_as()
    if not kind:
        return
    old, new = me + ".old", me + ".new"
    try:
        os.remove(old)                    # the copy the last swap left
    except OSError:
        pass
    if not os.path.isfile(new):
        return
    try:
        with open(new + ".sha256") as f:
            want = f.read().split()[0]
    except (OSError, IndexError):
        want = ""
    if not want or _sha256(new) != want:
        for p in (new, new + ".sha256"):
            try:
                os.remove(p)
            except OSError:
                pass
        return
    # A running .exe may be renamed on Windows though not replaced, so this
    # copy steps aside and the new one takes its name.
    os.replace(me, old)
    os.replace(new, me)
    os.remove(new + ".sha256")
    args = list(sys.argv[1:] if argv is None else argv)
    cmd = [me] + args if kind == "exe" else [sys.executable, me] + args
    subprocess.Popen(cmd, close_fds=True)                     # noqa: S603 (itself, just checked)
    sys.exit(0)
