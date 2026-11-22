"""Backups off the machine (R162 step 5): a folder on the controller's own
machine (a pool's mount, the array, the controller's state) copied to
another place (the array, a disk or a share mounted under /mnt/other) by
rsync, each run its own dated folder hard-linked to the one before so a
run costs only what changed, the oldest pruned past what is kept, and
`latest` always the newest whole run; a run that fails leaves no half
folder behind. The record comes with the hello (the controller's
backups.py), the storage-backup job names one of its rows, and the state
file beside it says each row's last run for the census.
"""
import os
import re
import shutil
import stat
import subprocess
import time

from .base import env_or, log, read_json, write_json
from .stores import save_state
from .names import VAR

STATE_FILE = VAR + "/backups-state.json"
NAME_RE = re.compile(r"[a-z][a-z0-9-]{0,30}")
ROOTS = ("/mnt/", "/var/lib/aerieos-controller", "/srv/")
RUN_RE = re.compile(r"\d{8}-\d{6}")
# Whose the runs' folder must be: root's, the account rsync copies as.
OWNER = 0


def _state():
    return read_json(env_or("BB_BACKUPS_STATE", STATE_FILE), {})


def _state_set(name, **kw):
    s = _state()
    s[name] = {**(s.get(name) or {}), **kw}
    write_json(env_or("BB_BACKUPS_STATE", STATE_FILE), s, makedirs=True)


def backups_now(state):
    """[{id, name, last_at, ok, error, size_mb, runs, took_s}] for the
    census: the record the hello left, each with its last run."""
    out = []
    st = _state()
    for r in state.get("store_backups") or []:
        if not isinstance(r, dict) or not NAME_RE.fullmatch(str(r.get("name") or "")):
            continue
        s = st.get(r["name"]) or {}
        out.append({"id": str(r.get("id") or "")[:16], "name": r["name"], "last_at": int(s.get("last_at") or 0), "ok": s.get("ok") is True,
                    "error": str(s.get("error") or "")[:200], "size_mb": int(s.get("size_mb") or 0), "runs": int(s.get("runs") or 0),
                    "took_s": int(s.get("took_s") or 0)})
    return out


def _du_mb(fd):
    """The megabytes under the folder `fd` is a descriptor on."""
    out = subprocess.run(["du", "-sm", _held(fd) + "/."], capture_output=True, text=True, timeout=600, check=False, pass_fds=(fd,)).stdout
    try:
        return int(out.split()[0])
    except (ValueError, IndexError):
        return 0


def _held(fd, name=""):
    """The path that reaches the folder `fd` is a descriptor on (and `name`
    inside it), in this process and in a child handed `fd`, whatever is
    done to the folder's own name meanwhile."""
    return f"/proc/self/fd/{fd}" + (f"/{name}" if name else "")


def _open_as(real, fds):
    """A descriptor on the folder at `real`, a path with no link in it,
    added to `fds`; raised where what opened is not the folder at that path
    (a part of it swapped since it was resolved)."""
    fd = os.open(real, os.O_RDONLY | os.O_DIRECTORY | os.O_NOFOLLOW)
    fds.append(fd)
    if os.readlink(_held(fd)) != real:
        raise OSError(f"{real} is not where it was")
    return fd


def _roots_alone(fd):
    """Whether only root may write the folder `fd` is a descriptor on: root
    owns it, and neither others nor a group other than root's may write it
    (by its mode, or by an ACL, whose mask the group's bits then are). An
    SMB mount shows each folder as root's and writable by root's group."""
    st = os.fstat(fd)
    if not stat.S_ISDIR(st.st_mode) or st.st_uid != OWNER or st.st_mode & stat.S_IWOTH:
        return False
    if st.st_mode & stat.S_IWGRP:
        return st.st_gid == OWNER and not _acl(fd)
    return True


def _acl(fd):
    try:
        os.getxattr(fd, "system.posix_acl_access")
    except (OSError, AttributeError):
        return False
    return True


def _there(fd, name):
    try:
        os.lstat(name, dir_fd=fd)
        return True
    except FileNotFoundError:
        return False


def _latest(fd):
    """The name of the newest run in the runs' folder `fd` is a descriptor
    on, where `latest` names one there that is a real folder; "" otherwise."""
    try:
        to = os.readlink("latest", dir_fd=fd)
        return to if RUN_RE.fullmatch(to) and stat.S_ISDIR(os.lstat(to, dir_fd=fd).st_mode) else ""
    except OSError:
        return ""


def under_roots(path):
    """Whether `path` is a folder under one of ROOTS, or the controller's
    state itself: by whole names, so a folder whose name only begins as a
    root's does is not one."""
    for root in ROOTS:
        r = root.rstrip("/")
        if path.startswith(r + "/") and path.rstrip("/") != r:
            return True
        if not root.endswith("/") and path.rstrip("/") == r:
            return True
    return False


class BackupsMixin:
    """Agent's backup jobs: one of the parts class Agent (agent.py) is made of."""

    def backups_want(self, rows):
        """The record as the hello hands it, kept in node.json for the job
        to look a name up in."""
        want = [{k: r.get(k) for k in ("id", "name", "source", "dest", "keep")} for r in rows
                if isinstance(r, dict) and NAME_RE.fullmatch(str(r.get("name") or ""))]
        if want != (self.state.get("store_backups") or []):
            self.state["store_backups"] = want
            save_state(self.state)

    def _apply_storage_backup(self, job, cfg):
        say = job.say
        rsync = shutil.which("rsync")
        if os.geteuid() != 0 or not rsync:
            say("refused: a backup is copied by rsync as root, and this agent is not root or has no rsync\n")
            return "failed", 77
        name = str(cfg.get("name") or "")
        rec = next((r for r in self.state.get("store_backups") or [] if r.get("name") == name), None)
        if not rec:
            say(f"refused: no backup called {name or 'nothing'} in the record this machine holds; the next hello brings it\n")
            return "failed", 66
        src, dest = str(rec.get("source") or ""), str(rec.get("dest") or "")
        keep = rec.get("keep") if isinstance(rec.get("keep"), int) and 1 <= rec.get("keep") <= 365 else 7
        for p in (src, dest):
            # By its name and by where it really is: a link under a share is
            # a share user's to make, and root copies what it points at.
            if not (os.path.isabs(p) and under_roots(p) and ".." not in p.split("/") and under_roots(os.path.realpath(p))):
                say(f"refused: {p or 'nothing'} is not a folder under /mnt, /srv or the controller's state\n")
                return "failed", 64
        if not os.path.isdir(src):
            say(f"refused: the source {src} is not here (a disk not plugged in, a pool not imported)\n")
            _state_set(name, ok=False, error="the source is not here", last_at=int(time.time()))
            return "failed", 65
        if dest.startswith(src.rstrip("/") + "/") or src.startswith(dest.rstrip("/") + "/") or src.rstrip("/") == dest.rstrip("/"):
            say("refused: a backup goes somewhere other than inside its source\n")
            return "failed", 64
        top = os.path.dirname(dest.rstrip("/")) if dest.count("/") > 2 else dest
        if dest.startswith("/mnt/") and not any(os.path.ismount(m) for m in (dest, top, "/".join(dest.split("/")[:3]))):
            say(f"refused: nothing is mounted at {dest}: the disk is not plugged in or the share is not mounted, and a copy would land on the system disk\n")
            _state_set(name, ok=False, error="the destination is not mounted", last_at=int(time.time()))
            return "failed", 65
        # rsync is handed the source and the runs' folder by descriptors held
        # here (_held), never by a name: a link left at any name on the way
        # (a share user's to make), or a folder swapped for one after these
        # checks, would take the copy, and its deletions, anywhere root may
        # write.
        fds = []
        try:
            return self._backup_held(job, rsync, name, src, dest, keep, fds)
        finally:
            for fd in fds:
                os.close(fd)

    def _backup_held(self, job, rsync, name, src, dest, keep, fds):
        say = job.say
        real_src, real_dest = os.path.realpath(src), os.path.realpath(dest)
        if real_dest.startswith(real_src.rstrip("/") + "/") or real_src.startswith(real_dest.rstrip("/") + "/") or real_src == real_dest:
            say("refused: a backup goes somewhere other than inside its source\n")
            return "failed", 64
        try:
            src_fd = _open_as(real_src, fds)
            dest_fd = _open_as(real_dest, fds)
        except OSError:
            say(f"refused: {src} or {dest} moved while the backup began\n")
            _state_set(name, ok=False, error="the source or the destination moved", last_at=int(time.time()))
            return "failed", 64
        try:
            os.mkdir(name, 0o755, dir_fd=dest_fd)
        except FileExistsError:
            pass
        except OSError as e:
            say(f"refused: the folder {name} could not be made in {dest}: {e.strerror}\n")
            _state_set(name, ok=False, error="the backup's folder could not be made", last_at=int(time.time()))
            return "failed", 73
        try:
            runs_fd = os.open(name, os.O_RDONLY | os.O_DIRECTORY | os.O_NOFOLLOW, dir_fd=dest_fd)
            fds.append(runs_fd)
        except OSError:
            say(f"refused: the folder {name} in {dest} leads somewhere else\n")
            _state_set(name, ok=False, error="the backup's folder leads somewhere else", last_at=int(time.time()))
            return "failed", 64
        # Root's alone, so nobody else may leave a name inside it for the
        # copy to follow; one made by hand over a share, or opened to others,
        # is refused rather than taken.
        if not _roots_alone(runs_fd):
            say(f"refused: the folder {name} in {dest} is not root's alone\n")
            _state_set(name, ok=False, error="the backup's folder is not root's alone", last_at=int(time.time()))
            return "failed", 64
        stamp = time.strftime("%Y%m%d-%H%M%S")
        new, part = os.path.join(real_dest, name, stamp), stamp + ".partial"
        try:
            if _there(runs_fd, stamp):
                raise FileExistsError(stamp)
            os.mkdir(part, 0o700, dir_fd=runs_fd)
        except OSError:
            say(f"refused: something is already at {name}/{part} in {dest}\n")
            _state_set(name, ok=False, error="something is already at the run's name", last_at=int(time.time()))
            return "failed", 64
        argv = [rsync, "-aHAX", "--numeric-ids", "--delete", "--delete-excluded", "--exclude", ".snapraid.content",
                "--exclude", "lost+found", "--exclude", ".zfs", "--info=stats1,progress0"]
        # The run before, only where it is one of these runs.
        before = _latest(runs_fd)
        if before:
            argv += ["--link-dest", _held(runs_fd, before)]
        argv += [_held(src_fd) + "/", _held(runs_fd, part) + "/"]
        say(f"backup {name}: {src} to {new}{' (hard-linked to the run before)' if before else ''}\n")
        t0 = time.time()
        _state_set(name, running=True)
        try:
            rc = self._sh(job, argv, timeout=86400, pass_fds=(src_fd, runs_fd))
        finally:
            _state_set(name, running=False)
        if rc not in (0, 24):                              # 24: a file vanished while it was read, the copy whole otherwise
            shutil.rmtree(_held(runs_fd, part), ignore_errors=True)
            _state_set(name, ok=False, error=f"rsync exit {rc}", last_at=int(time.time()), took_s=int(time.time() - t0))
            return "failed", rc
        os.rename(part, stamp, src_dir_fd=runs_fd, dst_dir_fd=runs_fd)
        try:
            os.unlink("latest.new", dir_fd=runs_fd)
        except OSError:
            pass
        os.symlink(stamp, "latest.new", dir_fd=runs_fd)
        os.replace("latest.new", "latest", src_dir_fd=runs_fd, dst_dir_fd=runs_fd)
        runs = sorted(d for d in os.listdir(runs_fd) if RUN_RE.fullmatch(d))
        for old in runs[:max(0, len(runs) - keep)]:
            say(f"pruned {old}: past the {keep} kept\n")
            shutil.rmtree(_held(runs_fd, old), ignore_errors=True)
        size = _du_mb(runs_fd)
        _state_set(name, ok=True, error="", last_at=int(time.time()), took_s=int(time.time() - t0), size_mb=size, runs=min(len(runs), keep))
        say(f"done: {name} at {new}, {len(runs[-keep:])} run(s) kept, {size} MB in all\n")
        log(f"backups: {name} done in {int(time.time() - t0)} s")
        self.hello_again(f"the backup {name} ran")
        return "succeeded", 0
