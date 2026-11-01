"""A way in at the console of AerieOS (R194, the operator, 1 Nov): a
password set on This machine logs in at the screen as admin, with sudo for
root. Root itself stays without one. The image's root is read-only and
forgets at every boot, so the password's hash is kept on the data partition
(/var) and the account is made again from it at each start of the agent.
Only on AerieOS: on a Linux of the person's own, its accounts are
theirs and none is made here.
"""
import os
import re
import subprocess
from typing import Callable

HASH_FILE = "/var/lib/builderbot/console-hash"
OS_RELEASE = "/usr/lib/builderbot-os/release"
USER = "admin"
# A SHA-512 crypt hash, as openssl passwd -6 writes one.
HASH_RE = re.compile(r"\$6\$[A-Za-z0-9./]{1,16}\$[A-Za-z0-9./]{86}")


def _env(k, d):
    return os.environ.get(k) or d


def on_os():
    return os.path.isfile(_env("BB_OS_RELEASE", OS_RELEASE))


def kept():
    try:
        with open(_env("BB_CONSOLE_HASH", HASH_FILE), encoding="utf-8") as f:
            h = f.read().strip()
        return h if HASH_RE.fullmatch(h) else ""
    except OSError:
        return ""


def console_now():
    """For the census: whether this is AerieOS and whether a console
    password is set."""
    return {"os": on_os(), "set": bool(kept())} if on_os() else {}


def apply(run=subprocess.run):
    """The admin account as the kept hash says: made with sudo if missing,
    given the hash, or locked where none is kept. The rc, 0 for nothing to
    do."""
    if not on_os() or os.geteuid() != 0:
        return 0
    h = kept()
    have = run(["getent", "passwd", USER], capture_output=True, timeout=10, check=False).returncode == 0
    if not h:
        return run(["usermod", "-L", USER], capture_output=True, timeout=10, check=False).returncode if have else 0
    if not have:
        rc = run(["useradd", "-m", "-s", "/bin/bash", "-G", "sudo", USER], capture_output=True, timeout=30, check=False).returncode
        if rc != 0:
            return rc
    return run(["usermod", "-p", h, "-U", USER], capture_output=True, timeout=10, check=False).returncode


class ConsoleMixin:
    hello_again: "Callable[..., None]"

    def _apply_console(self, job, cfg):
        """Set the console password from the hash the controller made, or
        take it away; applied at once and at every start after."""
        if not on_os():
            job.say("refused: a console password is AerieOS's; on a Linux of your own, log in with its own accounts\n")
            return "failed", 65
        h = str(cfg.get("hash") or "")
        path = _env("BB_CONSOLE_HASH", HASH_FILE)
        if cfg.get("clear") is True:
            try:
                os.unlink(path)
            except OSError:
                pass
            apply()
            job.say("the console password is taken away: admin cannot log in at the screen\n")
            self.hello_again("the console password was taken away")
            return "succeeded", 0
        if not HASH_RE.fullmatch(h):
            job.say("refused: not a password hash this takes\n")
            return "failed", 64
        os.makedirs(os.path.dirname(path), exist_ok=True)
        fd = os.open(path + ".new", os.O_WRONLY | os.O_CREAT | os.O_TRUNC, 0o600)
        with os.fdopen(fd, "w") as f:
            f.write(h + "\n")
        os.replace(path + ".new", path)
        rc = apply()
        if rc != 0:
            job.say("the password is kept, but the admin account did not take it (it is tried again at the next start)\n")
            return "failed", rc
        job.say("set: log in at the screen as admin with it; sudo gives root\n")
        self.hello_again("the console password was set")
        return "succeeded", 0
