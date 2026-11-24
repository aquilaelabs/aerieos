"""AerieOS on this machine (R160 step 4): what the image says of
itself for the census, and the update that writes the next image into the
slot not in use. The disk is image/partitions.sh's: two root slots found by
fixed partition UUIDs, each slot's kernel and initrd under /aerieos/SLOT
on the ESP, and GRUB booting the slot its environment names (the slot
tool). An update reads the release's list of its files, signed by a key
this install holds, fetches the release's ISO, checks it against the sha256
the release carries, against its build attestation and against that list,
takes the slot, its kernel, its initrd and its release stamp out of the
ISO's live/ folder, writes the other slot, puts its kernel beside it, names
it for the next boot, and asks for a restart; nothing running changes until
then, and the slot that runs now is the one to fall back to.
"""
import contextlib
import hashlib
import json
import os
import re
import shutil
import subprocess
import tempfile
import urllib.request
from .base import env_or, write_atomic
from .stores import path_plain

# Every BB_* read here (env_or) is the agent's own seam: a test's stand-in in
# the agent's environment, its unit's and root's alone, read wherever it runs.

RELEASE_FILE = "/usr/lib/aerieos-os/release"
SLOT_TOOL = "/usr/lib/aerieos-os/slot"
POOL_TOOL = "/usr/lib/aerieos-os/system-pool"
ESP = "/boot/efi"
# image/partitions.sh's, held to it by test_osimage.py.
SLOT_DEV = {"a": "/dev/disk/by-partuuid/6a5c2f3e-0b7d-4b2a-9c1e-b0b1de5b0e0a",
            "b": "/dev/disk/by-partuuid/6a5c2f3e-0b7d-4b2a-9c1e-b0b1de5b0e0b"}
SLOT_MIB = 4096
RELEASE_URL = "https://github.com/aquilaelabs/aerieos/releases/download"
REPO = "aquilaelabs/aerieos"
# A build's attestation, read from GitHub's public API with no token, and
# verified by gh with --bundle, which asks for no sign-in: a machine has
# none. An update from a folder takes the bundle the release carries
# beside the ISO and verifies it against the trusted root this image was
# built with, with no network.
ATTEST_URL = "https://api.github.com/repos/{repo}/attestations/sha256:{digest}"
# Who may have built an image an update takes (B729): the release workflow,
# build-image.yml, run on a version's tag, as a published release's
# attestation names it (read off v0.9.0-dev.5341's ISO, 16 Nov: its
# certificate's identity is .../build-image.yml@refs/tags/v0.9.0-dev.5341).
# The repository alone passed any workflow on any branch that attested one.


def signer_identity(repo):
    return rf"^https://github\.com/{re.escape(repo)}/\.github/workflows/build-image\.yml@refs/tags/v"


TRUSTED_ROOT = "/usr/lib/aerieos-os/trusted-root.jsonl"
# Who may sign a release (R199): the running controller's own copy of
# config/release-signers, so a key is trusted because this install already
# held it, never because the release names it.
SIGNERS = "/opt/aerieos/config/release-signers"
# The namespace a signer is named for says the channel, and a release's tag
# says which it may be signed in: a pre-release (vX.Y.Z-dev.N, -rc.N, any
# name) in either, a stable release (vX.Y.Z) in aerieos-release alone, so
# the key the release build holds, which signs dev builds as they publish
# themselves, can never sign a stable release. The same rule, in its own
# words, in the installer (nodes/install-controller.sh), the stick maker
# (tools/aerieos-stick.py) and the Library's downloads (apps.py);
# test_release_signing.py holds the four to one table of cases.
SIG_RELEASE, SIG_DEV = "aerieos-release", "aerieos-dev"
STABLE_TAG = re.compile(r"v\d+\.\d+\.\d+")
PRE_TAG = re.compile(r"v\d+\.\d+\.\d+-[a-z][a-z0-9]*\.\d+")
SIGNED_BY = {SIG_RELEASE: "AerieOS's release key", SIG_DEV: "the key AerieOS's dev builds are signed with"}


def signers():
    try:
        with open(env_or("BB_RELEASE_SIGNERS", SIGNERS), encoding="utf-8") as f:
            return [ln.strip() for ln in f if ln.strip() and not ln.lstrip().startswith("#")]
    except OSError:
        return []


def tag_namespaces(tag):
    """The namespaces the list of release `tag` may be signed in, by the
    tag's shape; none for what is no release's tag."""
    if STABLE_TAG.fullmatch(tag):
        return (SIG_RELEASE,)
    if PRE_TAG.fullmatch(tag):
        return (SIG_RELEASE, SIG_DEV)
    return ()


def unsignable(tag, keys):
    """Why no signature would have release `tag` taken by an install that
    names `keys`, or "": asked before anything is fetched."""
    may = tag_namespaces(tag)
    if not may:
        return f"{tag} is not a release's tag (vX.Y.Z, or vX.Y.Z-dev.N for a pre-release), so who may sign it cannot be told"
    if SIG_DEV not in may and not any(k.split(None, 1)[0] == SIG_RELEASE for k in keys):
        return (f"{tag} is a stable release and no stable signer is named yet: this install names only the key dev builds "
                "are signed with, and a stable release is signed by its own key's holder")
    return ""


def sig_namespace(sums, sig, keys, run=subprocess.run):
    """The namespace in which the signature `sig` over the file `sums`
    verifies against `keys`, or "": each signer is asked for in the one
    namespace it is named for."""
    with tempfile.TemporaryDirectory() as d:
        allowed = os.path.join(d, "signers")
        with open(allowed, "w", encoding="utf-8") as f:
            f.write("\n".join(keys) + "\n")
        for ns in (SIG_RELEASE, SIG_DEV):
            with open(sums, "rb") as fh:
                r = run(["ssh-keygen", "-Y", "verify", "-f", allowed, "-I", ns, "-n", ns, "-s", sig],
                        stdin=fh, capture_output=True, check=False)
            if r.returncode == 0:
                return ns
    return ""


def sums_read(sums):
    """{file: sha256} of a SHA256SUMS."""
    out = {}
    with open(sums, encoding="utf-8", errors="replace") as f:
        for line in f:
            parts = line.split()
            if len(parts) == 2 and re.fullmatch(r"[0-9a-f]{64}", parts[0].lower()):
                out[parts[1].lstrip("*")] = parts[0].lower()
    return out


def signed_list(tag, sums, sig, keys, run=subprocess.run):
    """({file: sha256}, who signed it, "") for release `tag`'s SHA256SUMS
    when its signature is one the tag may carry, by a key in `keys`; else
    (None, "", why not)."""
    why = unsignable(tag, keys)
    if why:
        return None, "", why
    try:
        ns = sig_namespace(sums, sig, keys, run)
    except OSError as e:
        return None, "", f"ssh-keygen is not here to check {tag}'s signature with ({e})"
    if not ns:
        return None, "", f"{tag}'s list of files is signed by no key this install names"
    if ns not in tag_namespaces(tag):
        return None, "", (f"{tag} is a stable release and its list is signed by the key dev builds are signed with: "
                          "a stable release takes its own key's signature alone")
    return sums_read(sums), SIGNED_BY[ns], ""


def unlisted(listed, name, digest, tag):
    """Why the file `name` with sha256 `digest` is not release `tag`'s by its
    signed list, or "": the list is what the key signed, where the sha256
    beside a file is the release's word for itself."""
    if name not in listed:
        return f"{name} is not in the list of files {tag} signed"
    if listed[name] != digest:
        return f"{name} is not the file {tag} signed: its bytes are not the ones the signed list names"
    return ""


# Each piece of a slot, and where image/build.sh puts it on the ISO.
PIECES = {"root.squashfs": "live/filesystem.squashfs", "vmlinuz": "live/vmlinuz",
          "initrd": "live/initrd", "release": "live/release"}
# A release's version by its tag, the v left out or not: a stable one, or a
# pre-release in PRE_TAG's shape (-dev.N, -rc.N), as the controller and the
# signature's check take them.
VER_RE = re.compile(r"v?(\d+\.\d+\.\d+(?:-[a-z][a-z0-9]*\.\d+)?)")


def os_work():
    """The folder AerieOS keeps its own in on the data partition: the
    configuration copied before each update, the older versions kept, an
    update's download, /etc's overlay."""
    return env_or("BB_OS_WORK", "/var/lib/aerieos-os")


def version_key(v):
    """A version to order by: X.Y.Z, then a pre-release (-dev.N) before the
    release it leads to. None for one that is not a version."""
    m = re.fullmatch(r"(\d+)\.(\d+)\.(\d+)(?:-[a-z][a-z0-9]*\.(\d+))?", v or "")
    if not m:
        return None
    return (int(m[1]), int(m[2]), int(m[3]), 0 if m[4] else 1, int(m[4] or 0))


def release_version(path):
    """The BUILDERBOT_OS_VERSION an image's release file names, or ""."""
    try:
        with open(path, encoding="utf-8", errors="replace") as f:
            for line in f:
                k, _, v = line.strip().partition("=")
                if k == "BUILDERBOT_OS_VERSION":
                    return v[:40]
    except OSError:
        pass
    return ""


def os_release():
    """{version, snapshot, built, slot, next} on an AerieOS disk, {}
    anywhere else: the release file the image carries, and the slot tool's
    reading of this boot and the next."""
    path = env_or("BB_OS_RELEASE", RELEASE_FILE)
    if not os.path.isfile(path):
        return {}
    out = {}
    try:
        with open(path, encoding="utf-8", errors="replace") as f:
            for line in f:
                k, _, v = line.strip().partition("=")
                if k == "BUILDERBOT_OS_VERSION":
                    out["version"] = v[:40]
                elif k == "DEBIAN_SNAPSHOT":
                    out["snapshot"] = v[:20]
                elif k == "BUILT":
                    out["built"] = v[:24]
    except OSError:
        return {}
    tool = env_or("BB_OS_SLOT", SLOT_TOOL)
    for key, verb in (("slot", "current"), ("next", "next")):
        try:
            r = subprocess.run(["bash", tool, verb], capture_output=True, text=True, timeout=10, check=False)
            got = r.stdout.strip()
            out[key] = got if got in ("a", "b") else ""
        except (OSError, subprocess.SubprocessError):
            out[key] = ""
    # On trial (R161 step 2): the slot an update wrote, booted and not yet
    # marked good; and a fallback the health check recorded, said until the
    # next update.
    try:
        st = subprocess.run(["bash", tool, "status"], capture_output=True, text=True, timeout=10, check=False).stdout
        out["trial"] = "\ntrial:" in "\n" + st
    except (OSError, subprocess.SubprocessError):
        out["trial"] = False
    fb = os.path.join(os_work(), "fell-back")
    try:
        with open(fb, encoding="utf-8", errors="replace") as f:
            out["fell_back"] = f.read().strip()[:200]
    except OSError:
        out["fell_back"] = ""
    return out


def keep_state_before(say, running):
    """The controller's configuration as it is before an update (R160 step
    4, R161 step 2): a copy beside the old slot, so going back to that slot
    boots the configuration it had, and the two newest copies kept."""
    src = env_or("BB_OS_STATE", "/var/lib/aerieos-controller/config")
    if not os.path.isdir(src):
        say("no controller configuration here to copy before the update\n")
        return True
    keep = os.path.join(os_work(), "before")
    os.makedirs(keep, mode=0o700, exist_ok=True)
    dest = os.path.join(keep, f"{running or 'unknown'}.tar.gz")
    r = subprocess.run(["tar", "-czf", dest + ".new", "-C", os.path.dirname(src), "--exclude=logs", "--exclude=jobs", "--exclude=os-draft", "--exclude=.moved-*", "--exclude=.move-*",
                        os.path.basename(src)], capture_output=True, text=True, check=False)
    # 1 is GNU tar's word for a file that changed as it was read (a log,
    # the database between its writes): the copy is whole. 2 is a failure.
    if r.returncode not in (0, 1):
        with contextlib.suppress(OSError):
            os.unlink(dest + ".new")
        say(f"the configuration's copy before the update did not take, so nothing was written: {r.stderr.strip()[-300:]}\n")
        return False
    os.replace(dest + ".new", dest)
    say(f"the configuration as it is, kept at {dest}\n")
    olds = sorted((os.path.join(keep, f) for f in os.listdir(keep) if f.endswith(".tar.gz")), key=os.path.getmtime)
    for old in olds[:-2]:
        os.unlink(old)
    return True


# ---- older versions kept (R201, the operator, 1 Nov) ---------------------------
# A version an update pushes out of its slot is kept as files on the data
# partition, its root, kernel, initrd and release, with the configuration's
# copy from when it was left, and is a boot menu entry of its own. Only an
# image that says it can boot that way (BUILDERBOT_OS_BOOTS_KEPT): an older
# initramfs does not know aeriekept=. Keeping never stops an update.
KEPT_VER = re.compile(r"[0-9A-Za-z][0-9A-Za-z.+-]{0,59}")
KEEP_DEFAULT = 3


def kept_dir():
    return os.path.join(os_work(), "kept")


def kept_boot():
    """The kept version this boot came from, or ""."""
    try:
        with open(env_or("BB_CMDLINE", "/proc/cmdline"), encoding="utf-8", errors="replace") as f:
            for w in f.read().split():
                if w.startswith("aeriekept="):
                    return w[len("aeriekept="):][:60]
    except OSError:
        pass
    return ""


def kept_list():
    """The versions kept, newest first: [{version, mb, at, state}]."""
    out = []
    try:
        names = os.listdir(kept_dir())
    except OSError:
        return out
    for v in names:
        d = os.path.join(kept_dir(), v)
        root = os.path.join(d, "root.squashfs")
        if KEPT_VER.fullmatch(v) and not v.endswith(".new") and os.path.isfile(root):
            st = os.stat(root)
            size = sum(os.path.getsize(os.path.join(d, f)) for f in os.listdir(d))
            out.append({"version": v, "mb": size >> 20, "at": int(st.st_mtime), "state": os.path.isfile(os.path.join(d, "state.tar.gz"))})
    return sorted(out, key=lambda x: x["at"], reverse=True)


def write_kept_menu(esp=None):
    """GRUB's Older versions, from what is kept: grub.cfg sources this file
    (nothing kept, an empty one). The root is on the same disk's data
    partition, the fifth, never another AerieOS disk's."""
    grub = os.path.join(esp or env_or("BB_OS_ESP", ESP), "grub")
    if not os.path.isdir(grub):
        return
    rows = kept_list()
    text = ""
    if rows:
        text = ("insmod regexp\ninsmod part_gpt\ninsmod ext2\n"
                'regexp --set=1:aerie_disk \'^([^,]+),\' "$root"\n'
                'set aerie_data="($aerie_disk,gpt5)"\n'
                'if [ "$aerie_toram" = 1 ]; then set aerie_keptram="aerietoram=1"; else set aerie_keptram=""; fi\n'
                "export aerie_data\nexport aerie_keptram\nexport aerie_slot\nexport aerie_args\n"
                'submenu "Older versions" --id older {\n')
        for r in rows:
            v = r["version"]
            at = f"$aerie_data/lib/aerieos-os/kept/{v}"
            text += (f'    menuentry "AerieOS {v}" --id kept-{v} {{\n'
                     f"        linux {at}/vmlinuz root=/dev/loop0 aeriekept={v} $aerie_keptram rootfstype=squashfs overlayroot=tmpfs "
                     "aerieslot=$aerie_slot panic=15 console=ttyS0,115200 console=tty0 quiet systemd.show_status=auto $aerie_args\n"
                     f"        initrd {at}/initrd\n    }}\n")
        text += "}\n"
    with open(os.path.join(grub, "kept.cfg.new"), "w", encoding="utf-8") as f:
        f.write(text)
        f.flush()
        os.fsync(f.fileno())
    os.replace(os.path.join(grub, "kept.cfg.new"), os.path.join(grub, "kept.cfg"))


def _unname_kept(ver, say):
    """A version no longer kept, taken off the next boot where Boot this next
    named it (slot kept-next, aerie_kept_next in grubenv): GRUB with a default
    its menu no longer has boots its first entry, slot A, whichever slot is in
    use (B620). Read from the environment block itself, cleared by the tool."""
    envf = os.path.join(env_or("BB_OS_ESP", ESP), "grub", "grubenv")
    try:
        with open(envf, encoding="utf-8", errors="replace") as f:
            named = f"aerie_kept_next={ver}" in (ln.strip() for ln in f)
    except OSError:
        return
    if not named:
        return
    try:
        subprocess.run(["bash", env_or("BB_OS_SLOT", SLOT_TOOL), "kept-next"], capture_output=True, timeout=30, check=False)
    except (OSError, subprocess.SubprocessError):
        return
    say(f"{ver} was to boot next, once; it is not kept any more, so the next boot is this version's slot\n")


def _drop_kept(ver, say):
    """One kept version removed, and unnamed for the next boot."""
    shutil.rmtree(os.path.join(kept_dir(), ver), ignore_errors=True)
    _unname_kept(ver, say)


def _prune_kept(keep, say, spare=""):
    """Down to `keep` versions, oldest first, never `spare`."""
    for r in reversed(kept_list()):
        if len(kept_list()) <= keep:
            break
        if r["version"] != spare:
            _drop_kept(r["version"], say)
            say(f"{r['version']} is no longer kept\n")


def keep_slot(say, dev, where, keep=KEEP_DEFAULT):
    """The version in the slot about to be written kept, from its partition
    and its kernel on the ESP (`where`). Says why it was not; never raises:
    an update does not stop for this. The menu follows what is kept however
    it ends."""
    try:
        _keep_slot(say, dev, where, keep)
    finally:
        with contextlib.suppress(OSError):
            write_kept_menu()


def _keep_slot(say, dev, where, keep):
    try:
        keep = int(keep)
    except (TypeError, ValueError):
        keep = KEEP_DEFAULT
    try:
        with open(os.path.join(where, "release"), encoding="utf-8", errors="replace") as f:
            rel = dict(ln.strip().partition("=")[::2] for ln in f if "=" in ln)
    except OSError:
        return                                          # an empty slot: nothing to keep
    ver = rel.get("BUILDERBOT_OS_VERSION", "")
    if not KEPT_VER.fullmatch(ver):
        return
    if keep <= 0:
        _prune_kept(0, say)
        return
    if rel.get("BUILDERBOT_OS_BOOTS_KEPT") != "1":
        say(f"{ver} is not kept as an older version: it was built before an older version could boot from its files\n")
        return
    d = os.path.join(kept_dir(), ver)
    new = d + ".new"
    # A copy kept already is the one taken from a whole slot: it is never
    # replaced by what the slot holds now.
    if os.path.isfile(os.path.join(d, "root.squashfs")):
        say(f"{ver} is kept already, on the boot menu\n")
        return
    try:
        with open(dev, "rb") as f:
            head = f.read(48)
            if head[:4] != b"hsqs":
                say(f"{ver} is not kept: its slot does not hold a squashfs\n")
                return
            used = int.from_bytes(head[40:48], "little")
            _prune_kept(keep - 1, say, spare=ver)
            st = os.statvfs(kept_dir() if os.path.isdir(kept_dir()) else os_work())
            if st.f_bavail * st.f_frsize < used + (1 << 30):
                say(f"{ver} is not kept: the data partition has too little room beside its {used >> 20} MB\n")
                return
            shutil.rmtree(new, ignore_errors=True)
            os.makedirs(new, mode=0o700)
            f.seek(0)
            left = used
            with open(os.path.join(new, "root.squashfs"), "wb") as out:
                while left > 0:
                    chunk = f.read(min(1 << 22, left))
                    if not chunk:
                        raise OSError("the slot ended early")
                    out.write(chunk)
                    left -= len(chunk)
        for piece in ("vmlinuz", "initrd", "release"):
            shutil.copyfile(os.path.join(where, piece), os.path.join(new, piece))
        state = os.path.join(os_work(), "before", f"{ver}.tar.gz")
        if os.path.isfile(state):
            shutil.copyfile(state, os.path.join(new, "state.tar.gz"))
        shutil.rmtree(d, ignore_errors=True)
        os.replace(new, d)
        say(f"{ver} is kept as an older version, on the boot menu\n")
    except OSError as e:
        shutil.rmtree(new, ignore_errors=True)
        say(f"{ver} was not kept as an older version: {e}\n")


def pin_hostid():
    """This machine's host id written through /etc's overlay, so it is kept on
    the data partition. Each image carries its own /etc/hostid, ZFS holds a
    pool to the host id that last had it, and every update otherwise looked
    to its own pools like another machine. Once only: the copy kept is what
    every later image shows."""
    kept = os.path.join(os_work(), "etc", "upper", "hostid")
    hostid = env_or("BB_HOSTID", "/etc/hostid")
    if not os.path.isdir(os.path.dirname(kept)) or os.path.exists(kept):
        return
    with contextlib.suppress(OSError):
        with open(hostid, "rb") as f:
            raw = f.read()
        if len(raw) == 4:
            write_atomic(hostid, raw)


def _sha256(path):
    h = hashlib.sha256()
    with open(path, "rb") as f:
        for chunk in iter(lambda: f.read(1 << 20), b""):
            h.update(chunk)
    return h.hexdigest()


# What an update holds at once on the data partition, against the ISO's
# size: the ISO, the root taken out of it, its kernel and initrd (R191
# step 4: a fetch that filled /var took the controller's database with it).
ROOM = 2.2


def _room(where, size):
    """Why `size` bytes of ISO do not fit beside the update's working files
    in `where`, or ""."""
    try:
        st = os.statvfs(where)
    except OSError:
        return ""
    free, need = st.f_bavail * st.f_frsize, int(size * ROOM)
    # Kept older versions give way, oldest first, before an update is refused.
    while size and free < need and kept_list():
        _drop_kept(kept_list()[-1]["version"], lambda s: None)
        write_kept_menu()
        st = os.statvfs(where)
        free = st.f_bavail * st.f_frsize
    if size and free < need:
        return (f"the data partition has {free >> 20} MB free and the update needs about {need >> 20} MB "
                f"for the image and what it takes out of it: free some, or grow the disk")
    return ""


def _fetch(url, dest, say):
    """One file by URL (https, or file:// for the tests) into dest, by
    chunks, saying each tenth of a large one; refused before a byte is
    written when it would not fit with what the update takes out of it."""
    with urllib.request.urlopen(url, timeout=60) as r:  # noqa: S310 (the release's address, or a test's file://)  # nosemgrep: python.lang.security.audit.dynamic-urllib-use-detected.dynamic-urllib-use-detected
        total = int(r.headers.get("Content-Length") or 0)
        if dest.endswith(".iso") and (why := _room(os.path.dirname(dest), total)):
            raise OSError(why)
        with open(dest, "wb") as f:
            _copy_from(r, f, dest, total, say)


def _copy_from(r, f, dest, total, say):
    """r into f by chunks, saying each tenth of a large one."""
    got, said = 0, 0
    while True:
        chunk = r.read(1 << 20)
        if not chunk:
            break
        f.write(chunk)
        got += len(chunk)
        if total > (64 << 20) and got * 10 // total > said:
            said = got * 10 // total
            say(f"{os.path.basename(dest)}: {said * 10}% of {total >> 20} MB\n")


def stick_status():
    """A stick boot's state (R161 step 10, the system-pool tool's status):
    {stick, pool, ready, on_stick, written_kb, boot_written_kb}, or {} where
    the tool is not here (no AerieOS)."""
    tool = env_or("BB_OS_POOL", POOL_TOOL)
    if not os.path.isfile(tool):
        return {}
    try:
        r = subprocess.run(["bash", tool, "status"], capture_output=True, text=True, timeout=15, check=False)
        d = json.loads(r.stdout.strip().splitlines()[-1]) if r.stdout.strip() else {}
    except (OSError, subprocess.SubprocessError, ValueError):
        return {}
    if not isinstance(d, dict) or not d.get("stick"):
        return {"stick": False}
    # The stick's own partition (/var): how much room it has, since what
    # fills it takes the controller down (the operator, 8 Nov).
    try:
        du = shutil.disk_usage(env_or("BB_SP_VAR", "/var"))
        room = {"var_total_mb": du.total >> 20, "var_free_mb": du.free >> 20}
    except OSError:
        room = {}
    return {"stick": True, "pool": str(d.get("pool") or "")[:200], "ready": d.get("ready") is True, **room,
            "on_stick": [str(x)[:20] for x in (d.get("on_stick") or [])][:8],
            "written_kb": d.get("written_kb") if isinstance(d.get("written_kb"), int) else None,
            "boot_written_kb": d.get("boot_written_kb") if isinstance(d.get("boot_written_kb"), int) else None,
            "projects": str(d.get("projects") or "")[:300], "projects_bound": d.get("projects_bound") is True,
            "projects_home": d.get("projects_home") if d.get("projects_home") in ("folder", "pool", "held") else "",
            # The pools holding another install's folder, which a pick there sets aside.
            "others": [str(x)[:200] for x in (d.get("others") or []) if isinstance(x, str)][:16],
            # The id its system pool is marked with, for the controller's
            # state to carry into a backup (B939).
            "install_id": str(d.get("install_id") or "") if re.fullmatch(r"[0-9a-f]{32,64}", str(d.get("install_id") or "")) else "",
            # ...and the id each other install's pool is marked with.
            "other_marks": {str(k)[:200]: str(v) for k, v in list((d.get("other_marks") or {}).items())[:16]
                            if isinstance(k, str) and k.startswith("/") and re.fullmatch(r"[0-9a-f]{32,64}", str(v))}
                           if isinstance(d.get("other_marks"), dict) else {}}


# Where this machine's pools, its array and the disks it adopted are mounted
# (pools.MOUNT_ROOT, array.MOUNT and its neighbors): the one place a system
# pool or a folder of spaces is named in.
DISKS_ROOT = "/mnt"


def on_disks(path):
    """Whether `path` names a place on this machine's disks: a plain path
    (stores.path_plain) whose real place is under DISKS_ROOT. What the tool
    is handed moves the machine's own folders there or gives the folder to
    the controller's account, so it is never a folder of the system's."""
    if not path_plain(path):
        return False
    real = os.path.realpath(path)
    return real.startswith(DISKS_ROOT + "/")


class OsImageMixin:
    def hostid_pass(self):
        """Once a minute, and nothing once it is done (pin_hostid)."""
        pin_hostid()

    """Agent's AerieOS update: one of the parts class Agent (agent.py)
    is made of."""

    def _apply_os_kept(self, job, cfg):
        """An older version kept (R201): `next` boots it once, `remove` takes
        it away; then a hello."""
        tool = env_or("BB_OS_SLOT", SLOT_TOOL)
        verb, ver = str(cfg.get("verb") or ""), str(cfg.get("version") or "")
        if not os.path.isfile(tool):
            job.say("refused: this machine does not run AerieOS\n")
            return "failed", 77
        if not KEPT_VER.fullmatch(ver) or not os.path.isdir(os.path.join(kept_dir(), ver)):
            job.say(f"refused: {ver or 'that version'} is not kept here\n")
            return "failed", 64
        if verb == "next" and os_release().get("trial"):
            # A visit now spends one of the trial's two boots, and a trial
            # not yet booted would end on the slot it came from.
            job.say("refused: an update is on trial and not marked good yet: let it boot and the health check mark it, then visit an older version\n")
            return "failed", 79
        if verb == "next":
            rc = self._sh(job, ["bash", tool, "kept-next", ver], timeout=30)
            if rc == 0:
                job.say(f"the next boot is {ver}, once: restart this machine to visit it, and the boot after is this version again\n")
        elif verb == "remove":
            if kept_boot() == ver:
                job.say("refused: this boot is running from it\n")
                return "failed", 65
            self._sh(job, ["bash", tool, "kept-next"], timeout=30)
            shutil.rmtree(os.path.join(kept_dir(), ver), ignore_errors=True)
            write_kept_menu()
            job.say(f"{ver} is no longer kept\n")
            rc = 0
        else:
            job.say("refused: next or remove\n")
            return "failed", 64
        self.hello_again("the older versions changed")
        return ("succeeded", 0) if rc == 0 else ("failed", rc)

    def _attested(self, job, iso, digest, name, src, work):
        """Whether the ISO verifies against its build attestation, said in
        the job either way: the bundle from the folder (and the trusted root
        this image carries) or from GitHub's public API, then gh attestation
        verify --bundle."""
        say = job.say
        gh = shutil.which("gh")
        if not gh:
            say("refused: no gh here to verify the image's build attestation with: nothing written\n")
            return False
        repo = env_or("BB_OS_REPO", REPO)
        bundle = os.path.join(work, "attestation.jsonl")
        extra = []
        if src:
            have = os.path.join(src, f"{name}.attestation.jsonl")
            root = env_or("BB_OS_TRUSTED_ROOT", TRUSTED_ROOT)
            if not os.path.isfile(have):
                say(f"refused: {src} holds no {name}.attestation.jsonl, the release's proof of who built the image; "
                    "bring it beside the ISO: nothing written\n")
                return False
            if not os.path.isfile(root):
                say("refused: this image carries no trusted root to verify an offline update with; update online: "
                    "nothing written\n")
                return False
            shutil.copyfile(have, bundle)
            extra = ["--custom-trusted-root", root]
        else:
            url = env_or("BB_OS_ATTEST_URL", ATTEST_URL).format(repo=repo, digest=digest)
            try:
                req = urllib.request.Request(url, headers={"Accept": "application/vnd.github+json",
                                                           "User-Agent": "AerieOS"})
                with urllib.request.urlopen(req, timeout=60) as r:  # noqa: S310 (GitHub's API, or a test's file://)  # nosemgrep: python.lang.security.audit.dynamic-urllib-use-detected.dynamic-urllib-use-detected
                    got = json.loads(r.read(4 << 20) or b"{}")
            except (OSError, ValueError) as e:
                say(f"the image's build attestation could not be fetched from GitHub ({e}): nothing written\n")
                return False
            lines = [json.dumps(a["bundle"]) for a in got.get("attestations") or []
                     if isinstance(a, dict) and isinstance(a.get("bundle"), dict)]
            if not lines:
                say("GitHub has no build attestation for this image: nothing written\n")
                return False
            with open(bundle, "w", encoding="utf-8") as f:
                f.write("\n".join(lines) + "\n")
        rc = self._sh(job, [gh, "attestation", "verify", iso, "--bundle", bundle, "--repo", repo,
                            "--cert-identity-regex", signer_identity(repo), *extra], timeout=120)
        if rc != 0:
            say("the image's build attestation did not verify: nothing written\n")
            return False
        say("the image's build attestation verifies: built by AerieOS's release workflow\n")
        return True

    def _iso_pieces(self, job, iso, work):
        """The slot's pieces copied out of the ISO's live/ folder into
        `work`, the ISO mounted read-only for it: {piece: path}, or {} with
        what went wrong said."""
        mnt = os.path.join(work, "iso")
        os.makedirs(mnt, exist_ok=True)
        if self._sh(job, ["mount", "-o", "loop,ro,nodev,nosuid,noexec", iso, mnt], timeout=60) != 0:
            job.say("the image would not open (mount -o loop): nothing written\n")
            return {}
        files = {}
        try:
            for piece, inside in PIECES.items():
                dest = os.path.join(work, piece)
                at = os.path.join(mnt, inside)
                # A piece is a plain file on the ISO itself, never a link
                # out of it (B470: one to /dev/zero filled the disk).
                if os.path.islink(at) or not os.path.isfile(at):
                    job.say(f"the image has no {inside} as a plain file: nothing written\n")
                    return {}
                try:
                    shutil.copyfile(at, dest, follow_symlinks=False)
                except OSError as e:
                    job.say(f"the image has no {inside}: {e}; nothing written\n")
                    return {}
                files[piece] = dest
        finally:
            if self._sh(job, ["umount", mnt], timeout=60) != 0:
                job.say(f"the image stayed mounted at {mnt}: umount it before the next update\n")
        return files

    def _apply_system_pool(self, job, cfg):
        """A stick's system pool named (R161 step 10): the tool stops docker,
        containerd and libvirt, moves what the stick holds of theirs, of the
        toolchains and of the projects to the pool, keeps the name and binds
        them there at every boot; then a hello says where things are."""
        tool = env_or("BB_OS_POOL", POOL_TOOL)
        path = str(cfg.get("path") or "")
        if not os.path.isfile(tool):
            job.say("refused: this machine does not run AerieOS, so it has no stick\n")
            return "failed", 77
        if not on_disks(path):
            job.say("refused: a pool is named by its mount point\n")
            return "failed", 64
        # Another install's folder there is set aside only when asked (the
        # operator, 8 Nov); the tool refuses it otherwise, but for the one
        # this controller's restored configuration names as its own (B939).
        adopt = str(cfg.get("adopt_id") or "")
        pre = ["env", f"BB_SP_ADOPT_ID={adopt}"] if re.fullmatch(r"[0-9a-f]{32,64}", adopt) else []
        rc = self._sh(job, [*pre, "bash", tool, "set", path, *(["--aside"] if cfg.get("aside") is True else [])], timeout=6 * 3600)
        self.hello_again("the system pool was set")
        return ("succeeded", 0) if rc == 0 else ("failed", rc)

    def _apply_projects_folder(self, job, cfg):
        """A folder already on the machine's disks taken as the projects
        folder (R163, the operator, 1 Nov: a moved controller adopts the
        projects where they are), or let go (`release`): the tool checks it,
        says which of `names` it holds, hands it to the controller's account,
        binds it and restarts the controller on it; then a hello."""
        tool = env_or("BB_OS_POOL", POOL_TOOL)
        if not os.path.isfile(tool):
            job.say("refused: this machine does not run AerieOS, so it has no stick\n")
            return "failed", 77
        if cfg.get("release"):
            rc = self._sh(job, ["bash", tool, "projects", "--release"], timeout=600)
        else:
            path = str(cfg.get("path") or "")
            if not on_disks(path):
                job.say("refused: a spaces folder is named by its path\n")
                return "failed", 64
            names = [str(n) for n in (cfg.get("names") or []) if isinstance(n, str) and n and "/" not in n and not n.startswith(".")][:500]
            rc = self._sh(job, ["bash", tool, "projects", path, *names], timeout=6 * 3600)
        self.hello_again("the spaces folder changed")
        return ("succeeded", 0) if rc == 0 else ("failed", rc)

    def _apply_os_update(self, job, cfg):
        """Write the next image into the slot not in use. `cfg` names a
        release by its tag, or a folder on this machine that holds the
        release's files (an offline machine, the files brought on a stick or
        over a share); the sha256 files beside them are read either way.
        What it fetched and took out of the ISO is gone again however it
        ends: a failed update left gigabytes on the data partition (B470)."""
        work = os.path.join(os_work(), "update")
        try:
            return self._os_update(job, cfg, work)
        finally:
            shutil.rmtree(work, ignore_errors=True)

    def _os_update(self, job, cfg, work):
        say = job.say
        rel = os_release()
        tool = env_or("BB_OS_SLOT", SLOT_TOOL)
        if not rel or not os.path.isfile(tool):
            say("refused: this machine does not run AerieOS (no image release here), so there is no slot to write\n")
            return "failed", 77
        cur, other = rel.get("slot") or "", ""
        if cur in ("a", "b"):
            other = "b" if cur == "a" else "a"
        if not other:
            say("refused: this boot named no slot, so the one to write cannot be told from the one running\n")
            return "failed", 78
        # The slot running now on trial is not proven: the other slot is the
        # only good one, and writing it would leave nothing to go back to
        # (B470).
        if rel.get("trial") and rel.get("next") == cur:
            say(f"refused: slot {cur} runs on trial and is not marked good yet, and slot {other} is the one to fall "
                "back to: wait for the health check (a few minutes after the dashboard is up), then update\n")
            return "failed", 79
        if kept_boot():
            say(f"refused: this boot is a visit to the older version {kept_boot()}: restart into the version it came from, then update\n")
            return "failed", 80
        tag = str(cfg.get("release") or "").strip()
        src = str(cfg.get("from") or "").strip()
        if not tag and not src:
            say("refused: an update names a release (vX.Y.Z) or a folder with its files\n")
            return "failed", 64
        if tag and not VER_RE.fullmatch(tag):
            say("refused: a release is named by its tag, vX.Y.Z or a pre-release's vX.Y.Z-dev.N\n")
            return "failed", 64
        if src and not (os.path.isabs(src) and os.path.isdir(src)):
            say(f"refused: {src or 'the folder'} is not a folder on this machine\n")
            return "failed", 64
        ver = VER_RE.fullmatch(tag).group(1) if tag else ""
        shutil.rmtree(work, ignore_errors=True)
        os.makedirs(work, mode=0o700)
        name = f"aerieos-os-{ver}" if ver else ""
        if src:
            # The folder's ISO names the version.
            found = sorted(f for f in os.listdir(src) if f.startswith("aerieos-os-") and f.endswith(".iso"))
            if len(found) != 1:
                say(f"refused: {src} holds {len(found)} images (aerieos-os-VERSION.iso); one, please\n")
                return "failed", 65
            name = found[0][:-len(".iso")]
            ver = name[len("aerieos-os-"):]
        say(f"os update: {name}, into slot {other} (slot {cur} runs now)\n")
        fn = f"{name}.iso"
        iso = os.path.join(work, fn)
        # The release's list of its files, signed by a key this install
        # already holds (R199), before the image is fetched: who changes the
        # repository or a release can build and attest an image and put a
        # sha256 beside it, not sign the list. The tag says who may have
        # signed (tag_namespaces); a list that is unsigned, or signed by
        # somebody the tag may not have, is refused, and so is every
        # release on an install that names no signer at all: every build
        # ships the file that names them, so one without it has lost it.
        rtag = (tag if tag.startswith("v") else "v" + tag) if tag else "v" + ver
        at = f"{env_or('BB_OS_RELEASE_URL', RELEASE_URL)}/{rtag}"
        keys, listed, who = signers(), None, ""
        if not keys:
            say("refused: this install names no release signer: nothing written\n")
            return "failed", 69
        if keys:
            if why := unsignable(rtag, keys):
                say(f"refused: {why}: nothing written\n")
                return "failed", 69
            sums, sig = os.path.join(work, "SHA256SUMS"), os.path.join(work, "SHA256SUMS.sig")
            try:
                if src:
                    shutil.copyfile(os.path.join(src, "SHA256SUMS"), sums)
                    shutil.copyfile(os.path.join(src, "SHA256SUMS.sig"), sig)
                else:
                    _fetch(f"{at}/SHA256SUMS", sums, say)
                    _fetch(f"{at}/SHA256SUMS.sig", sig, say)
            except OSError as e:
                say(f"refused: {rtag} carries no signed list of its files (SHA256SUMS and SHA256SUMS.sig: {e}): it was made "
                    "before releases were signed, or its key's holder has not signed it yet; nothing written\n")
                return "failed", 69
            listed, who, why = signed_list(rtag, sums, sig, keys)
            if listed is None:
                say(f"refused: {why}: nothing written\n")
                return "failed", 69
            if fn not in listed:
                say(f"refused: {unlisted(listed, fn, '', rtag)}: nothing written\n")
                return "failed", 69
        try:
            if src:
                if why := _room(work, os.path.getsize(os.path.join(src, fn))):
                    raise OSError(why)
                shutil.copyfile(os.path.join(src, fn), iso)
                shutil.copyfile(os.path.join(src, fn + ".sha256"), iso + ".sha256")
            else:
                job.step(f"fetching {fn}")
                _fetch(f"{at}/{fn}", iso, say)
                _fetch(f"{at}/{fn}.sha256", iso + ".sha256", say)
        except OSError as e:
            say(f"{fn}: not got: {e}\n")
            return "failed", 66
        with open(iso + ".sha256", encoding="utf-8", errors="replace") as f:
            want = (f.read().split() or [""])[0].lower()
        have = _sha256(iso)
        if not re.fullmatch(r"[0-9a-f]{64}", want) or want != have:
            say(f"{fn}: its sha256 does not match the one the release carries ({have[:12]} against {want[:12] or 'none'}): nothing written\n")
            return "failed", 67
        say(f"{fn} matches its sha256\n")
        # The build attestation (R160 step 4): keyless, from the workflow
        # that built the image, checked where gh is here to ask GitHub.
        # The build attestation, from a release or from a folder alike: a
        # sha256 from the same place as the image proves nothing about who
        # built it, and a folder may be on a share others write (B470, R191
        # step 1).
        if not self._attested(job, iso, have, name, src, work):
            return "failed", 68
        # ...and the image's own bytes are the ones the signed list names,
        # whatever the sha256 beside it says.
        if listed is not None:
            if why := unlisted(listed, fn, have, rtag):
                say(f"refused: {why}: nothing written\n")
                return "failed", 69
            say(f"{fn} is the image {rtag}'s list names, signed by {who}\n")
        job.step("reading the image")
        files = self._iso_pieces(job, iso, work)
        if not files:
            return "failed", 66
        os.unlink(iso)
        # The version is the image's own release file's, never only its
        # file's name, and an older one than this machine runs is not taken
        # (B847): going back is the boot menu's, which keeps the version
        # before.
        said = release_version(files["release"])
        if said != ver:
            say(f"refused: the image's own release says {said or 'no version'}, and its name says {ver}: nothing written\n")
            return "failed", 69
        now = rel.get("version") or ""
        if version_key(ver) is None or (version_key(now) is not None and version_key(ver) < version_key(now)):
            say(f"refused: {ver} is older than {now}, which this machine runs: an update only goes forward, and the "
                "version before is on the boot menu to go back to\n")
            return "failed", 69
        size = os.path.getsize(files["root.squashfs"])
        if size > SLOT_MIB * 1048576:
            say(f"the root image is {size >> 20} MB and a slot holds {SLOT_MIB}: nothing written\n")
            return "failed", 69
        dev = env_or(f"BB_OS_DEV_{other.upper()}", SLOT_DEV[other])
        if not os.path.exists(dev):
            say(f"slot {other}'s partition is not here ({dev}): nothing written\n")
            return "failed", 70
        # Every AerieOS disk shares its partitions' UUIDs, so with a second
        # one in the machine (a stick) the name could be either (B470).
        if not env_or(f"BB_OS_DEV_{other.upper()}", ""):
            uuid = os.path.basename(SLOT_DEV[other])
            r = subprocess.run(["blkid", "-t", f"PARTUUID={uuid}", "-o", "device"], capture_output=True, text=True,
                               timeout=30, check=False)
            if len(r.stdout.split()) > 1:
                say(f"refused: {len(r.stdout.split())} disks here carry slot {other} ({', '.join(r.stdout.split())}): "
                    "take out the other AerieOS disk or stick, then update\n")
                return "failed", 70
        # GRUB pointed back at this slot, trial off, before the other is
        # touched: a slot left half written by a lost power or a failed
        # write is never the next boot (B470).
        if self._sh(job, ["bash", tool, "hold"], timeout=30) != 0:
            say("GRUB's environment could not be set back to this slot: nothing written\n")
            return "failed", 73
        # The configuration as it is, first: going back to this slot needs
        # it, so an update that could not take it does not go ahead.
        if not keep_state_before(say, rel.get("version") or ""):
            return "failed", 74
        # What the slot holds goes on the boot menu before it is overwritten.
        job.step(f"keeping what slot {other} holds")
        keep_slot(say, dev, os.path.join(env_or("BB_OS_ESP", ESP), "aerieos", other), cfg.get("keep", KEEP_DEFAULT))
        # The slot's old release named off it before its root is written: a
        # write cut short leaves a slot that reads as empty, never as the
        # old version, which the next update's keep would have taken and
        # put in place of the good copy kept before it.
        try:
            stale = os.path.join(env_or("BB_OS_ESP", ESP), "aerieos", other, "release")
            if os.path.exists(stale):
                os.unlink(stale)
                fd = os.open(os.path.dirname(stale), os.O_RDONLY)
                try:
                    os.fsync(fd)
                finally:
                    os.close(fd)
        except OSError as e:
            say(f"slot {other}'s old release could not be taken off it before writing: {e}; nothing written\n")
            return "failed", 72
        job.step(f"writing slot {other}")
        try:
            with open(files["root.squashfs"], "rb") as f, open(dev, "r+b") as d:
                shutil.copyfileobj(f, d, 1 << 22)
                d.flush()
                os.fsync(d.fileno())
        except OSError as e:
            say(f"slot {other} did not take the image: {e}\n")
            return "failed", 71
        esp = env_or("BB_OS_ESP", ESP)
        where = os.path.join(esp, "aerieos", other)
        try:
            os.makedirs(where, exist_ok=True)
            for piece, target in (("vmlinuz", "vmlinuz"), ("initrd", "initrd"), ("release", "release")):
                shutil.copyfile(files[piece], os.path.join(where, target + ".new"))
                # On the ESP before GRUB is told: a kernel still in the
                # page cache when power goes is a slot that will not load.
                with open(os.path.join(where, target + ".new"), "rb+") as f:
                    os.fsync(f.fileno())
                os.replace(os.path.join(where, target + ".new"), os.path.join(where, target))
            os.sync()
        except OSError as e:
            say(f"the ESP did not take slot {other}'s kernel: {e}\n")
            return "failed", 72
        # Named for the next boot and put on trial (R161 step 2) in one
        # write: two boots without the health check's word go back to the
        # slot running now. Not set, it is said, and the next boot stays here
        # (B470: a next without its trial booted the new slot with no way
        # back, and was reported a success).
        pin_hostid()
        if self._sh(job, ["bash", tool, "switch", other, cur, ver], timeout=30) != 0:
            self._sh(job, ["bash", tool, "hold"], timeout=30)
            say(f"GRUB was not told to boot slot {other} on trial: the slot is written and the next boot stays on slot {cur}\n")
            return "failed", 73
        with contextlib.suppress(OSError):
            os.unlink(os.path.join(os_work(), "fell-back"))
        say(f"slot {other} holds AerieOS {ver}, and the next boot starts it: restart this machine to finish (Reboot under Advanced on the Nodes page). "
            f"Slot {cur} keeps {rel.get('version') or 'the image running now'} to fall back to.\n")
        self.hello_again(f"AerieOS {ver} written to slot {other}")
        return "succeeded", 0
