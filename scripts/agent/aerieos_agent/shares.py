"""SMB and NFS shares on the controller's own machine (R162 step 1): each
share as AerieOS's own two files say it (/etc/samba/smb.conf.d/
builderbot.conf, included by smb.conf; /etc/exports.d/builderbot.exports),
read whole for the census and written whole by the storage-share job, which
checks the name, the path (a folder under /mnt or /srv that is there) and
the users and clients named before Samba and NFS are told to read again.
Who may reach a share is a Unix user the machine has (an account's own,
R125, or one named) or everybody as a guest. The SMB passwords the accounts
set on Profile (R164 step 1) come with the hello as Samba keeps them (the
NT hash per Unix user) and are imported into Samba's own database here,
the users made where they are missing and the ones gone removed; a share
may be a Mac's Time Machine target.
"""
import hashlib
import json
import os
import re
import shutil
import subprocess
import time

from .base import log
from .stores import save_state
from .names import ETC

SMB_FILE = "/etc/samba/smb.conf.d/builderbot.conf"
# The shares nothing serves: a folder that is a share, kept here since neither
# Samba's file nor NFS's says it (the operator, 4 Nov).
INTERNAL_FILE = ETC + "/shares-internal.json"
SMB_MAIN = "/etc/samba/smb.conf"
SMB_MAP = "/etc/samba/aerieos-users.map"
NFS_FILE = "/etc/exports.d/builderbot.exports"
# The accounts' SMB passwords as handed over, written for pdbedit to import
# (smbpasswd's line format) and removed once read.
SMB_USERS_FILE = "/run/builderbot/smbusers"
# A share's name and its folder's path may hold single spaces between words
# (TV Shows, as another NAS names one), never a leading, trailing or doubled
# one, nor a character Samba's or NFS's file would read as its own.
NAME_RE = re.compile(r"(?=.{1,63}$)[A-Za-z0-9][A-Za-z0-9_.-]*(?: [A-Za-z0-9_.-]+)*")
PATH_RE = re.compile(r"(?:/[A-Za-z0-9._+@-]+(?: [A-Za-z0-9._+@-]+)*)+/?")
USER_RE = re.compile(r"[a-z_][a-z0-9_-]{0,31}")
CLIENT_RE = re.compile(r"[A-Za-z0-9*][A-Za-z0-9*./:_-]{0,80}")
ROOTS = ("/mnt/", "/srv/")


def _env(name, default):
    return os.environ.get(name) or default


def _read(path):
    try:
        with open(path, encoding="utf-8", errors="replace") as f:
            return f.read()
    except OSError:
        return ""


def shares_now():
    """[{name, path, smb: {on, guest, ro, users}, nfs: {on, ro, clients}}]
    from AerieOS's own two files; [] where neither is here."""
    smb, nfs = {}, {}
    cur = None
    for line in _read(_env("BB_SMB_FILE", SMB_FILE)).splitlines():
        line = line.strip()
        m = re.fullmatch(r"\[([^\]]+)\]", line)
        if m:
            cur = m.group(1).strip()
            smb[cur] = {"path": "", "guest": False, "ro": False, "tm": False, "users": [], "readers": [], "writers": []}
            continue
        if cur and "=" in line and not line.startswith((";", "#")):
            k, _, v = line.partition("=")
            k, v = k.strip().lower(), v.strip()
            if k == "path":
                smb[cur]["path"] = v[:200]
            elif k == "guest ok":
                smb[cur]["guest"] = v.lower() == "yes"
            elif k == "read only":
                smb[cur]["ro"] = v.lower() == "yes"
            elif k == "valid users":
                smb[cur]["users"] = [u for u in v.split() if USER_RE.fullmatch(u)][:64]
            elif k == "read list":
                smb[cur]["readers"] = [u for u in v.split() if USER_RE.fullmatch(u)][:64]
            elif k == "write list":
                smb[cur]["writers"] = [u for u in v.split() if USER_RE.fullmatch(u)][:64]
            elif k == "fruit:time machine":
                smb[cur]["tm"] = v.lower() == "yes"
    for line in _read(_env("BB_NFS_FILE", NFS_FILE)).splitlines():
        line = line.strip()
        if not line or line.startswith("#"):
            continue
        if line.startswith('"'):
            path, _, rest = line[1:].partition('"')
            parts = [path, *rest.split()]
        else:
            parts = line.split()
            path = parts[0]
        clients = []
        ro = False
        for c in parts[1:]:
            host, _, opts = c.partition("(")
            if CLIENT_RE.fullmatch(host):
                clients.append(host)
                ro = ro or "ro" in opts.rstrip(")").split(",")
        nfs[path] = {"ro": ro, "clients": clients[:64]}
    names = list(smb)
    out = []
    for name in names:
        s = smb[name]
        n = nfs.get(s["path"]) or {}
        # Private: valid users are everybody named, the read list those who only
        # read. Secure: a guest may read, and the write list names who writes.
        users = s["writers"] if s["guest"] else [u for u in s["users"] if u not in s["readers"]]
        out.append({"name": name, "path": s["path"], "smb": {"on": True, "guest": s["guest"], "ro": s["ro"] and not (s["guest"] and users), "tm": s["tm"], "users": users,
                                                             "readers": [] if s["guest"] else s["readers"]},
                    "nfs": {"on": bool(n), "ro": bool(n.get("ro")), "clients": n.get("clients") or []}})
    for path, n in nfs.items():
        if not any(o["path"] == path for o in out):
            out.append({"name": os.path.basename(path.rstrip("/")) or path, "path": path, "smb": {"on": False, "guest": False, "ro": False, "tm": False, "users": []},
                        "nfs": {"on": True, "ro": n["ro"], "clients": n["clients"]}})
    # The shares that are folders and nothing more.
    try:
        kept = json.loads(_read(_env("BB_SHARES_INTERNAL", INTERNAL_FILE)) or "[]")
    except ValueError:
        kept = []
    for k in kept if isinstance(kept, list) else []:
        if isinstance(k, dict) and k.get("name") and k.get("path") and not any(o["name"] == k["name"] or o["path"] == k["path"] for o in out):
            out.append({"name": str(k["name"])[:63], "path": str(k["path"])[:200],
                        "smb": {"on": False, "guest": False, "ro": False, "tm": False, "users": [], "readers": []},
                        "nfs": {"on": False, "ro": False, "clients": []}})
    return out[:64]


def _nobodys(path):
    """Whether a share's folder belongs to the nobody account."""
    try:
        import pwd
        return os.stat(path).st_uid == pwd.getpwnam("nobody").pw_uid
    except (OSError, KeyError):
        return False


def _make_folder(path):
    """A share's missing folder made where it is on a disk the machine has: one
    level under a mounted pool or array or deeper, never on the root's tmpfs.
    "" when it is there now, or why not. Closed to everybody but Samba's
    account, which everyone named on the share writes as."""
    if os.path.isdir(path):
        return ""
    probe = os.path.dirname(path)
    while probe not in ("", "/") and not os.path.exists(probe):
        probe = os.path.dirname(probe)
    at = probe
    while at not in ("", "/", "/mnt", "/srv") and not os.path.ismount(at):
        at = os.path.dirname(at)
    if at in ("", "/", "/mnt", "/srv"):
        return f"{path} is not on a disk this machine has mounted"
    try:
        import pwd
        import grp
        os.makedirs(path, exist_ok=True)
        os.chown(path, pwd.getpwnam("nobody").pw_uid, grp.getgrnam("nogroup").gr_gid)
        os.chmod(path, 0o770)
    except (OSError, KeyError) as e:
        return f"{path} could not be made: {e}"
    return ""


def _samba_hooks(main=None):
    """smb.conf told about the shares file and the names' map, once, in its
    [global] section, where the image's own says nothing of them (B672). The
    file's kept in /etc, so a boot keeps it; False when it could not be written."""
    main = main or _env("BB_SMB_MAIN", SMB_MAIN)
    want = [f"   username map = {_env('BB_SMB_MAP', SMB_MAP)}", f"   include = {_env('BB_SMB_FILE', SMB_FILE)}"]
    try:
        with open(main, encoding="utf-8") as f:
            text = f.read()
    except OSError:
        return False
    missing = [w for w in want if w not in text.split("\n")]
    if not missing:
        return True
    # The map is [global]'s, right under its head; the include goes last, since
    # what it brings starts sections of its own.
    lines = text.rstrip("\n").split("\n")
    if want[0] in missing:
        at = next((i for i, x in enumerate(lines) if x.strip().lower() == "[global]"), None)
        if at is None:
            lines[:0] = ["[global]", want[0]]
        else:
            lines.insert(at + 1, want[0])
    if want[1] in missing:
        lines.append(want[1])
    try:
        with open(main + ".new", "w", encoding="utf-8") as f:
            f.write("\n".join(lines) + "\n")
        os.chmod(main + ".new", 0o644)
        os.replace(main + ".new", main)
    except OSError:
        return False
    return True


def render(shares):
    """The two files from the record: Samba's sections and NFS's lines."""
    smb = ["# Written by AerieOS (the Storage page): every share here is one it makes. Do not edit; the page writes it whole.\n"]
    nfs = ["# Written by AerieOS (the Storage page): do not edit; the page writes it whole.\n"]
    for s in shares:
        if s["smb"]["on"]:
            smb.append(f"[{s['name']}]\n    path = {s['path']}\n    browseable = yes\n    read only = {'yes' if s['smb']['ro'] or (s['smb']['guest'] and s['smb']['users']) else 'no'}\n")
            readers = list(s["smb"].get("readers") or [])
            if s["smb"]["guest"]:
                smb.append("    guest ok = yes\n    force user = nobody\n")
                # Secure: everybody reads as a guest, the people named write.
                if s["smb"]["users"]:
                    smb.append(f"    write list = {' '.join(s['smb']['users'])}\n")
            else:
                smb.append(f"    guest ok = no\n    valid users = {' '.join(s['smb']['users'] + readers)}\n")
                if readers:
                    smb.append(f"    read list = {' '.join(readers)}\n")
                # A folder made for the share is nobody's and each person named
                # on it writes as that, so two people see each other's files,
                # as a NAS's share is (B672). A folder that was somebody's
                # before keeps its owners.
                if _nobodys(s["path"]):
                    # Group-write too: without it a file written over the
                    # network cannot be saved over again (found by a real
                    # client: new files worked, overwriting them was denied).
                    smb.append("    force user = nobody\n    force group = nogroup\n    create mask = 0664\n    directory mask = 0775\n")
            # A Mac's Time Machine target (R164 step 1): fruit says so to the
            # Finder, catia keeps the names it writes; the Mac finds it by
            # mDNS, which Samba registers itself.
            smb.append("    vfs objects = catia fruit streams_xattr\n    fruit:metadata = stream\n"
                       + ("    fruit:time machine = yes\n" if s["smb"].get("tm") else "") + "\n")
        if s["nfs"]["on"]:
            opts = "ro" if s["nfs"]["ro"] else "rw"
            # A path with a space is quoted, as exportfs reads one.
            nfs.append((f'"{s["path"]}" ' if " " in s["path"] else f"{s['path']} ") + " ".join(f"{c}({opts},sync,no_subtree_check,root_squash)" for c in s["nfs"]["clients"]) + "\n")
    return "".join(smb), "".join(nfs)


class SharesMixin:
    """Agent's share jobs: one of the parts class Agent (agent.py) is made of."""

    def smb_users_want(self, rows):
        """The accounts' SMB passwords as the hello hands them (R164 step 1):
        [{user, nt}], applied once per change (its digest kept in node.json):
        each user made where it is missing (a system user, no login shell,
        the bbu group), the set imported into Samba's database whole, and
        every bbu- user Samba knows that is not in the set removed. Root,
        with Samba installed; nothing otherwise."""
        want = sorted(({"user": str(r.get("user") or ""), "nt": str(r.get("nt") or "").upper(), "name": str(r.get("name") or "")} for r in rows if isinstance(r, dict)),
                      key=lambda r: r["user"])
        want = [r for r in want if re.fullmatch(r"bbu-[0-9a-f]{8}", r["user"]) and re.fullmatch(r"[0-9A-F]{32}", r["nt"])]
        # The record's shape in the digest, so a machine that took a set in an
        # older shape takes it again.
        sig = hashlib.sha256(json.dumps(["2", want]).encode()).hexdigest()
        pdbedit = shutil.which("pdbedit")
        if sig == self.state.get("smb_users_sig") or not pdbedit or os.geteuid() != 0:
            return
        group = getattr(self, "_account_group", None)
        if group:
            group()
        import pwd
        for r in want:
            try:
                pwd.getpwnam(r["user"])
            except KeyError:
                p = subprocess.run(["useradd", "-r", "-M", "-U", "-d", "/nonexistent", "-s", "/usr/sbin/nologin", "-G", "bbu", r["user"]],
                                   capture_output=True, text=True, timeout=30, check=False)
                if p.returncode != 0:
                    log(f"shares: could not make {r['user']}: {(p.stderr or '').strip()[:160]}")
        have = set()
        for line in (self._out([pdbedit, "-L"]) or "").splitlines():
            u = line.split(":", 1)[0]
            if re.fullmatch(r"bbu-[0-9a-f]{8}", u):
                have.add(u)
        for u in sorted(have - {r["user"] for r in want}):
            subprocess.run([pdbedit, "-x", "-u", u], capture_output=True, timeout=30, check=False)
        lines = []
        for r in want:
            try:
                uid = pwd.getpwnam(r["user"]).pw_uid
            except KeyError:
                continue
            # X: the password does not expire, and a real time it last changed;
            # LCT-00000000 tells Samba it must change first, which no share
            # client can do (B672).
            lines.append(f"{r['user']}:{uid}:{'X' * 32}:{r['nt']}:[UX         ]:LCT-{int(time.time()):08X}:\n")
        path = _env("BB_SMB_USERS_FILE", SMB_USERS_FILE)
        try:
            os.makedirs(os.path.dirname(path), mode=0o700, exist_ok=True)
            fd = os.open(path, os.O_WRONLY | os.O_CREAT | os.O_TRUNC, 0o600)
            with os.fdopen(fd, "w") as f:
                f.write("".join(lines))
            if lines:
                p = subprocess.run([pdbedit, "-i", f"smbpasswd:{path}", "-e", "tdbsam"], capture_output=True, text=True, timeout=60, check=False)
                if p.returncode != 0:
                    log(f"shares: pdbedit did not take the passwords: {(p.stderr or p.stdout or '').strip()[:200]}")
                    return
        finally:
            try:
                os.unlink(path)
            except OSError:
                pass
        # The name a person signs in with, onto the Unix user Samba knows them
        # as (B672).
        try:
            mp = _env("BB_SMB_MAP", SMB_MAP)
            with open(mp + ".new", "w", encoding="utf-8") as f:
                f.write("".join(f'{r["user"]} = "{r["name"]}"\n' for r in want if re.fullmatch(r"[A-Za-z0-9._@+-]{1,64}", r["name"])))
            os.chmod(mp + ".new", 0o644)
            os.replace(mp + ".new", mp)
        except OSError as e:
            log(f"shares: the names' map did not write: {e}")
        _samba_hooks()
        self.state["smb_users_sig"] = sig
        save_state(self.state)
        log(f"shares: {len(lines)} SMB password(s) in Samba, {len(have - {r['user'] for r in want})} removed")

    def _out(self, argv, timeout=30):
        try:
            return subprocess.run(argv, capture_output=True, text=True, timeout=timeout, check=False).stdout
        except (OSError, subprocess.SubprocessError):
            return ""

    def _make_account_user(self, name):
        """An account's user made as smb_users_want makes one (a system
        user, no home, no login shell, the bbu group); "" or why not."""
        group = getattr(self, "_account_group", None)
        if group:
            group()
        p = subprocess.run(["useradd", "-r", "-M", "-U", "-d", "/nonexistent", "-s", "/usr/sbin/nologin", "-G", "bbu", name],
                           capture_output=True, text=True, timeout=30, check=False)
        if p.returncode != 0:
            why = (p.stderr or "").strip()[:160] or f"useradd exit {p.returncode}"
            log(f"shares: could not make {name}: {why}")
            return why
        return ""

    def _apply_storage_share(self, job, cfg):
        say = job.say
        if os.geteuid() != 0:
            say("refused: shares are written as root, and this agent is not root\n")
            return "failed", 77
        # Many at once (R163 step 9, an adopted system's shares): each the
        # same set as one alone, in turn, each said; one refused leaves the
        # others served.
        if cfg.get("share") == "set-many":
            rows = [x for x in (cfg.get("shares") or []) if isinstance(x, dict)][:64]
            bad = []
            for x in rows:
                st, _rc = self._apply_storage_share(job, {**x, "share": "set"})
                if st != "succeeded":
                    bad.append(str(x.get("name") or "?"))
            say(f"{len(rows) - len(bad)} of {len(rows)} shares served" + (f"; not {', '.join(bad)} (above)" if bad else "") + "\n")
            return ("succeeded", 0) if not bad else ("failed", 1)
        action = str(cfg.get("share") or "")
        name = str(cfg.get("name") or "").strip()
        if action not in ("set", "remove"):
            say(f"refused: {action or 'no action'} is not a share action (set, remove)\n")
            return "failed", 64
        if not NAME_RE.fullmatch(name):
            say(f"refused: {name or 'no name'} is not a share name (letters, digits, dots, hyphens and underscores, 63 at most)\n")
            return "failed", 64
        have = shares_now()
        rest = [s for s in have if s["name"] != name]
        if action == "set":
            path = str(cfg.get("path") or "").strip()
            smb = cfg.get("smb") if isinstance(cfg.get("smb"), dict) else {}
            nfs = cfg.get("nfs") if isinstance(cfg.get("nfs"), dict) else {}
            if not (path.startswith(ROOTS) and os.path.isabs(path) and ".." not in path.split("/")):
                say(f"refused: {path or 'no path'} is not a folder under /mnt or /srv\n")
                return "failed", 65
            if not os.path.isdir(path):
                if not PATH_RE.fullmatch(path):
                    say(f"refused: {path} has characters a share's path may not have (quotes, a doubled space and the like): name its folder plainly\n")
                    return "failed", 65
                why = _make_folder(path)
                if why:
                    say(f"refused: {why}\n")
                    return "failed", 65
                say(f"{path}: made for the share\n")
            # The folder as it really is, and a plain path: it is written into
            # /etc/exports.d and smb.conf, where a space or a newline in a name
            # a share's user made wrote options of its own (a world export
            # keeping root), and a link exported wherever it pointed.
            real = os.path.realpath(path)
            if not (real.startswith(ROOTS) and PATH_RE.fullmatch(real)):
                say(f"refused: {path} is a link out of /mnt or /srv, or has characters a share's path may not have "
                    "(quotes, a doubled space and the like): name its folder plainly\n")
                return "failed", 65
            path = real
            users = [str(u) for u in (smb.get("users") or []) if isinstance(u, str)]
            readers = [str(u) for u in (smb.get("readers") or []) if isinstance(u, str) and str(u) not in users]
            if smb.get("on") and (users or readers or not smb.get("guest")):
                if not smb.get("guest") and not users and not readers:
                    say("refused: an SMB share takes the users who may reach it, or everybody as a guest\n")
                    return "failed", 64
                for u in users + readers:
                    if not USER_RE.fullmatch(u):
                        say(f"refused: {u!r} is not a user name\n")
                        return "failed", 64
                    try:
                        import pwd
                        pwd.getpwnam(u)
                    except KeyError:
                        # An account's own user (bbu-ID, named by the
                        # controller for an account it has) is made here
                        # when the share names it, as it would be at the
                        # account's first sign-in: a share adopted from
                        # another system names people who have never signed
                        # in (B633, the VM walk of 2 Nov: 'backups' for two
                        # people refused). A name that is not an account's
                        # is still refused.
                        if not re.fullmatch(r"bbu-[0-9a-f]{8}", u):
                            say(f"refused: {u} is not a user this machine has (an account's own user is made when it first signs in here)\n")
                            return "failed", 66
                        why = self._make_account_user(u)
                        if why:
                            say(f"refused: {u} is not a user this machine has and could not be made: {why}\n")
                            return "failed", 66
                        say(f"{u} made here for the share: they reach it over SMB once their password is set on Profile\n")
            clients = [str(c) for c in (nfs.get("clients") or []) if isinstance(c, str)]
            if nfs.get("on"):
                if not clients:
                    say("refused: an NFS share takes the clients it is exported to (an address, a network, a name, or * for any)\n")
                    return "failed", 64
                for c in clients:
                    if not CLIENT_RE.fullmatch(c):
                        say(f"refused: {c!r} is not a client (an address, a network like 192.168.1.0/24, a name, or *)\n")
                        return "failed", 64
            if any(s["path"] == path and s["name"] != name for s in rest):
                say(f"refused: {path} is shared already under another name\n")
                return "failed", 66
            rest.append({"name": name, "path": path,
                         "smb": {"on": bool(smb.get("on")), "guest": bool(smb.get("guest")), "ro": bool(smb.get("ro")), "tm": smb.get("tm") is True, "users": users[:64], "readers": readers[:64]},
                         "nfs": {"on": bool(nfs.get("on")), "ro": bool(nfs.get("ro")), "clients": clients[:64]}})
            say(f"share {name}: {path}, {'SMB' if smb.get('on') else ''}{' and ' if smb.get('on') and nfs.get('on') else ''}{'NFS' if nfs.get('on') else ''}{'internal, not exported' if not smb.get('on') and not nfs.get('on') else ''}\n")
        else:
            if len(rest) == len(have):
                say(f"refused: no share called {name}\n")
                return "failed", 66
            say(f"share {name}: removed\n")
        if not _samba_hooks():
            say("smb.conf could not be told about the shares file: Samba will not serve them until it can\n")
        # What nothing serves is kept apart, and is still a share.
        try:
            ip = _env("BB_SHARES_INTERNAL", INTERNAL_FILE)
            os.makedirs(os.path.dirname(ip), exist_ok=True)
            with open(ip + ".new", "w", encoding="utf-8") as fh:
                json.dump([{"name": x["name"], "path": x["path"]} for x in rest if not x["smb"]["on"] and not x["nfs"]["on"]], fh)
            os.replace(ip + ".new", ip)
        except OSError as e:
            say(f"the list of internal shares did not write: {e}\n")
            return "failed", 67
        smb_text, nfs_text = render(rest)
        smb_file, nfs_file = _env("BB_SMB_FILE", SMB_FILE), _env("BB_NFS_FILE", NFS_FILE)
        try:
            for f, text in ((smb_file, smb_text), (nfs_file, nfs_text)):
                os.makedirs(os.path.dirname(f), exist_ok=True)
                with open(f + ".new", "w", encoding="utf-8") as fh:
                    fh.write(text)
                os.chmod(f + ".new", 0o644)
        except OSError as e:
            say(f"the share files did not write: {e}\n")
            return "failed", 67
        testparm = shutil.which("testparm")
        if testparm and subprocess.run([testparm, "-s", "--suppress-prompt", smb_file + ".new"], capture_output=True, text=True, check=False).returncode != 0:
            say("refused: Samba does not accept the share file as written (testparm); nothing changed\n")
            os.unlink(smb_file + ".new")
            os.unlink(nfs_file + ".new")
            return "failed", 68
        os.replace(smb_file + ".new", smb_file)
        os.replace(nfs_file + ".new", nfs_file)
        bad = 0
        if shutil.which("smbcontrol"):
            bad += self._sh(job, [shutil.which("smbcontrol"), "all", "reload-config"], timeout=30) != 0
        if shutil.which("exportfs"):
            bad += self._sh(job, [shutil.which("exportfs"), "-ra"], timeout=30) != 0
        self.hello_again(f"the share {name}: {action}")
        return ("succeeded", 0) if not bad else ("failed", 1)
