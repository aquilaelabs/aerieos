"""The coding agents' sign-ins sealed on a node (R126).

With the node's switch on (token_seal, after R125's accounts as their own
users), an account's Claude Code, Codex CLI and Grok Build sign-ins are kept here
sealed, never in the clear on a disk: a copied disk, a backup, the share or
a snapshot carries nothing usable, and a root who arrives while the account
has no session running gets nothing for it. tokenseal.py says how.

  SEAL_DIR/u_X/AGENT.seal   the sealed sign-in, root's alone, outside every
                            home and every session's view
  OPEN_DIR/u_X/AGENT.json   the opened copy while the account works here: a
                            tmpfs, the account's user's alone; the home's
                            own file is a link to it, so the agent reads and
                            refreshes it where it always did

A seal is opened only when a person opens a terminal for their own account
(the key rides in the controller's signed /term open, token_open), and the
opened copy is wiped GRACE_S after the account's last session ends. A
refresh written into it is sealed again within a pass. A login writes into
the home as ever; the pass finds the plain file, seals it, and puts the
link in its place.

Which copy is the newest, for everything here that writes one (B1043): a
plain file in the home, then the opened copy, then the seal. An agent
refreshes its sign-in by writing a new file and renaming it over the name,
which takes the link's place, or by writing through the link into the
opened copy, and a refresh spends the token before it: the copy it left
behind is worth nothing. So a seal is opened only where neither of the
other two is, and neither is ever written from an older one.

Copilot CLI keeps its token inside its config.json with
its settings, so that file is sealed whole (R126 step 3): the settings in
it are the CLI's own, read where it reads them, and the Installed page names
who is signed in from the seal's header as for the others.
"""
import base64
import contextlib
import json
import os
import pwd
import subprocess
import threading
import time

from . import tokenseal
from .accounts import UID_RE, user_of
from .base import SIGNINS, log, pack_signins, wipe, write_atomic
from .names import VAR

SEAL_DIR = VAR + "/tokens"
OPEN_DIR = "/run/bb-tokens"
GRACE_S = 300
EVERY_S = 10
# The shipped agents' sign-ins, each the file its row says it is kept in
# (base.SIGNINS).
FILES = tuple((agent, os.path.join(*row["kept"].split("/"))) for agent, row in SIGNINS.items())


def files():
    """Every sign-in sealed here: the shipped agents', then the file each
    pack's agent keeps its own in, where its pack says (R233 step 6)."""
    return FILES + tuple((agent, row["kept"]) for agent, row in sorted(pack_signins().items()))


def _claims(jwt):
    try:
        part = str(jwt).split(".")[1]
        return json.loads(base64.urlsafe_b64decode(part + "=" * (-len(part) % 4))) or {}
    except (IndexError, ValueError, TypeError):
        return {}


def _jwt_email(d, depth=0):
    """The email a JSON Web Token anywhere in a record names, from its
    claims, unverified (a name to show, never a credential), or ""."""
    if depth > 4:
        return ""
    for v in (d.values() if isinstance(d, dict) else d if isinstance(d, list) else []):
        if isinstance(v, (dict, list)):
            got = _jwt_email(v, depth + 1)
            if got:
                return got
        elif isinstance(v, str) and v.count(".") == 2 and len(v) < 8192:
            got = str(_claims(v).get("email") or "")
            if got:
                return got
    return ""


def _at(d, path):
    """The value the keys of `path` lead to in `d`, or None; a token met on
    the way is opened to what it says of its holder."""
    for k in path:
        if isinstance(d, str):
            d = _claims(d)
        if not isinstance(d, dict):
            return None
        d = d.get(k)
    return d


def _jsonc(data):
    """A file's JSON, read past leading `//` lines (Copilot's config opens
    with them since 1.0.103, B282)."""
    lines = (data.decode("utf-8", "replace") if isinstance(data, bytes) else str(data)).splitlines()
    n = 0
    while n < len(lines) and (not lines[n].strip() or lines[n].lstrip().startswith("//")):
        n += 1
    return json.loads("\n".join(lines[n:]))


def about(agent, data, home):
    """What a sign-in says of itself, kept readable in its seal's header so
    the Installed page can name who is signed in without opening it: read
    from what the agent's row or its pack says of its sign-in (`who`), as
    login-list.py who_of reads the open file, so a row names the same
    account sealed or open."""
    out = {"agent": agent}
    row = SIGNINS.get(agent) or pack_signins().get(agent)
    if not row:
        return out
    who = row.get("who") or {}
    whose = who.get("named") or f"{row.get('provider') or agent} account"
    with contextlib.suppress(OSError, ValueError, TypeError, AttributeError):
        if who.get("file") and who["file"] != row["kept"]:
            # Another file says who (Claude Code's own record beside its
            # credential): read from the home.
            with open(os.path.join(home, who["file"]), "rb") as f:
                data = f.read(1 << 20)
        try:
            d = _jsonc(data)
        except (ValueError, TypeError):
            # A JSON file that does not read names nobody; a token kept as
            # plain text is its provider's account.
            if who.get("email") or who.get("key") or (who.get("file") or row["kept"]).endswith(".json"):
                return out
            out["email"] = whose[:120]
            return out
        email = _at(d, who["email"]) if who.get("email") else _jwt_email(d)
        email = email if isinstance(email, str) else ""
        if who.get("plan"):
            plan = _at(d, who["plan"]) if email else ""
            out["plan"] = (plan if isinstance(plan, str) else "")[:40]
        if not email and who.get("key") and _at(d, who["key"]):
            email, out["plan"] = who.get("key_named") or f"{row.get('provider') or agent} API key", "API"
        out["email"] = (email or ("" if who.get("email") else whose))[:120]
    return out


def _shred(path):
    """A plain sign-in file overwritten and removed: what overwriting can do
    on the disk it is on (nothing on a copy-on-write one, or a snapshot)."""
    with contextlib.suppress(OSError):
        n = os.path.getsize(path)
        with open(path, "r+b") as f:
            f.write(b"\0" * n)
            f.flush()
            os.fsync(f.fileno())
    with contextlib.suppress(OSError):
        os.unlink(path)


def plain(home_file):
    """Whether the home's file is a sign-in in the clear: a file of its own
    with something in it, not the link to an opened copy. A login wrote it,
    or a refresh that renamed a new file over the link, so it is newer than
    the seal and than any copy open."""
    return os.path.isfile(home_file) and not os.path.islink(home_file) and os.path.getsize(home_file) > 0


def _stamp(st):
    """What tells a file from the one that was there before: a rename over
    it is another inode, a write in place another time or size."""
    return (st.st_ino, st.st_size, st.st_mtime_ns)


def link_left(home_file, opened, seal):
    """Whether the home's file is a link to an opened copy that is not there
    with no seal left to open it from: a sign-out, or a seal wiped, after
    the link was made."""
    return os.path.islink(home_file) and os.readlink(home_file) == opened \
        and not os.path.lexists(opened) and not os.path.exists(seal)


class TokensMixin:
    tokens_at = 0.0
    _tok_e = None
    # One at a time over an account's sign-ins: the pass is the loop's, and
    # each terminal a person opens brings its keys on a thread of its own
    # (a page reconnecting opens several at once), which would otherwise
    # read a plain file the other is half way through shredding.
    _tok_lock = threading.RLock()

    def token_seal_on(self):
        return bool(self.state.get("token_seal")) and self.account_users_ready()

    def token_boot_public(self):
        """This run's public half, which the controller wraps a seal's key to."""
        if self._tok_e is None:
            self._tok_e = tokenseal.boot_secret()
        return tokenseal.public(self._tok_e)

    def _tok_state(self):
        if not hasattr(self, "_tok_seen"):
            self._tok_seen, self._tok_live = {}, {}
        return self._tok_seen, self._tok_live

    def token_census(self):
        """For the hello: this boot's public half and the R of every seal
        here, by account and agent (public, both), or None while off."""
        if not self.token_seal_on() and not os.path.isdir(SEAL_DIR):
            return None
        sealed = {}
        with contextlib.suppress(OSError):
            for acct in sorted(os.listdir(SEAL_DIR))[:500]:
                if not UID_RE.match(acct):
                    continue
                for agent, _ in files():
                    with contextlib.suppress(OSError, tokenseal.Refused):
                        with open(os.path.join(SEAL_DIR, acct, agent + ".seal"), "rb") as f:
                            h = tokenseal.header(f.read(8192))
                        sealed.setdefault(acct, {})[agent] = {"R": h.get("R", ""), "K": h.get("K", ""),
                                                             "email": h.get("email", ""), "plan": h.get("plan", "")}
        return {"E": self.token_boot_public(), "sealed": sealed}

    def _open_mounted(self):
        """OPEN_DIR a tmpfs of its own, mounted once: noswap where the kernel
        has it, so an opened sign-in is not written to swap either."""
        os.makedirs(OPEN_DIR, mode=0o711, exist_ok=True)
        with open("/proc/mounts", encoding="utf-8") as f:
            if any(ln.split()[1] == OPEN_DIR and ln.split()[2] == "tmpfs" for ln in f if len(ln.split()) > 2):
                return True
        for opts in ("mode=0711,size=4m,noswap", "mode=0711,size=4m"):
            if subprocess.run(["mount", "-t", "tmpfs", "-o", opts, "bb-tokens", OPEN_DIR],
                              capture_output=True, timeout=30, check=False).returncode == 0:
                return True
        log(f"tokens: could not mount a tmpfs at {OPEN_DIR}, so no sign-in is opened here")
        return False

    def _acct_open_dir(self, acct, pw):
        d = os.path.join(OPEN_DIR, acct)
        os.makedirs(d, mode=0o700, exist_ok=True)
        os.chown(d, pw.pw_uid, pw.pw_gid)
        os.chmod(d, 0o700)
        return d

    def _seal(self, acct, agent, data, home):
        # The X25519 public where this node has the library (R158 step 3),
        # else the public before, which seals the old way.
        pub = ((self.state.get("token_pubs2") or {}).get(acct) if tokenseal.HAVE else None) \
            or (self.state.get("token_pubs") or {}).get(acct)
        if not pub:
            return False
        d = os.path.join(SEAL_DIR, acct)
        os.makedirs(SEAL_DIR, mode=0o700, exist_ok=True)
        os.makedirs(d, mode=0o700, exist_ok=True)
        # K names the public key it was sealed under, so the controller can
        # tell a seal still under the install key before a rotation.
        write_atomic(os.path.join(d, agent + ".seal"), tokenseal.seal(pub, data, dict(about(agent, data, home), K=tokenseal.rid(pub))),
                     mode=0o600, uid=0, gid=0)
        # The controller hears the new seal's R at once: the next terminal
        # opened for this account must bring the key that opens this one.
        again = getattr(self, "hello_again", None)
        if again:
            again(f"{acct}'s {agent} sign-in was sealed")
        return True

    def _link(self, home_file, target, pw):
        """The home's file a link to the opened copy, the account's user's.
        Never in the place of a sign-in in the clear: one that landed since
        the caller looked is newer than what the link leads to, and stays
        for the next look to seal."""
        with contextlib.suppress(FileNotFoundError):
            if os.path.islink(home_file) and os.readlink(home_file) == target:
                return
            if plain(home_file):
                return
            os.unlink(home_file)
        os.makedirs(os.path.dirname(home_file), exist_ok=True)
        os.symlink(target, home_file)
        os.lchown(home_file, pw.pw_uid, pw.pw_gid)

    def _live(self, acct):
        user = user_of(acct)
        return bool((self._tmux_as(user, ["list-sessions", "-F", "#{session_name}"], quiet=True) or "").strip())

    def _seal_plain(self, acct, agent, hf, home, pw, opening=False):
        """A plain sign-in in the home (a login, a refresh renamed over the
        link, or one from before the switch) sealed, kept open while the
        account works here or, with `opening`, for the terminal about to
        start, and the plain file shredded with the link in its place. The
        one path the pass and a terminal's open both take (B1043): the file
        is newer than whatever is sealed or open, so both are written from
        it. False with no public key to seal it with yet, and the file then
        stays exactly as it is."""
        with open(hf, "rb") as f:
            was = _stamp(os.fstat(f.fileno()))
            data = f.read()
        if not self._seal(acct, agent, data, home):
            return False
        odir = os.path.join(OPEN_DIR, acct)
        of = os.path.join(odir, agent + ".json")
        if opening or os.path.isdir(odir) or self._live(acct):
            self._acct_open_dir(acct, pw)
            write_atomic(of, data, mode=0o600, uid=pw.pw_uid, gid=pw.pw_gid)
            self._tok_state()[0][(acct, agent)] = _stamp(os.stat(of))
        # Written again while this one was being sealed: that file is newer
        # still, and is left whole for the next look to take.
        with contextlib.suppress(FileNotFoundError):
            if _stamp(os.lstat(hf)) != was:
                return True
        _shred(hf)
        self._link(hf, of, pw)
        log(f"tokens: {acct}'s {agent} sign-in sealed")
        return True

    def _seal_changed(self, acct, agent, of, home, anyway=False):
        """An opened copy sealed again when it is not the one last sealed (a
        refresh written into it), or `anyway`. The stamp is kept only once
        it is sealed, so a copy that changed before its account had a
        public key here is sealed when the key comes."""
        seen = self._tok_state()[0]
        key = _stamp(os.stat(of))
        if seen.get((acct, agent)) == key and not anyway:
            return
        with open(of, "rb") as f:
            if self._seal(acct, agent, f.read(), home):
                seen[(acct, agent)] = key

    def token_pass_early(self):
        """The pass ahead of what waits on the controller, where node.json
        already says sign-ins are sealed here (B1043): as this process
        starts, and at the top of a turn before a hello. A process's first
        pass used to come after the bundle's fetch, the first hello with
        its census taken on the loop, and the passes ahead of it in the
        turn: 87 seconds on a node whose agent had just re-executed for its
        update, while the page was reconnecting that node's terminals.
        Nothing in a pass needs the controller's answer: the switch and
        the public keys are kept.
        With the switch off in what was kept, nothing is done here:
        putting sign-ins back as plain files waits for the controller's
        own word, in the turn's pass after the hello."""
        if time.time() - self.tokens_at >= EVERY_S and self.token_seal_on():
            self.token_pass()

    def token_pass(self):
        """Every few seconds, with the switch on: a plain sign-in sealed and
        made a link, a refreshed one sealed again, and an account's opened
        copies wiped GRACE_S after its last session."""
        if os.geteuid() != 0 or time.time() - self.tokens_at < EVERY_S:
            return
        if not self.token_seal_on():
            self.tokens_at = time.time()
            self._tokens_back()
            return
        self.tokens_at = time.time()
        if not self._open_mounted():
            return
        try:
            users_dir = os.path.join(pwd.getpwnam(self.session_account()).pw_dir, "users")
            accts = [a for a in sorted(os.listdir(users_dir))[:500] if UID_RE.match(a)]
        except (KeyError, OSError):
            return
        now = time.time()
        for acct in accts:
            with self._tok_lock:
                self._pass_account(acct, os.path.join(users_dir, acct), now)

    def _pass_account(self, acct, home, now):
        """One account's part of the pass."""
        seen, live = self._tok_state()
        try:
            pw = pwd.getpwnam(user_of(acct))
            if os.lstat(home).st_uid != pw.pw_uid:
                return                      # not moved to its user yet (R125)
        except (KeyError, OSError):
            return
        odir = os.path.join(OPEN_DIR, acct)
        for agent, rel in files():
            hf, of = os.path.join(home, rel), os.path.join(odir, agent + ".json")
            with contextlib.suppress(OSError):
                if plain(hf):
                    # A login, a refresh renamed over the link, or a
                    # sign-in from before the switch: sealed, kept open
                    # while the account works here, and the plain file gone.
                    self._seal_plain(acct, agent, hf, home, pw)
                elif os.path.isfile(of):
                    self._seal_changed(acct, agent, of, home)
                elif acct not in live and link_left(hf, of, os.path.join(SEAL_DIR, acct, agent + ".seal")):
                    # No seal behind the home's link and nothing open: the
                    # link goes, so a terminal here says to sign in rather
                    # than that a sign-in is waiting to be opened (B386).
                    os.unlink(hf)
        if not os.path.isdir(odir):
            return
        if self._live(acct):
            live[acct] = now
        elif now - live.setdefault(acct, now) > GRACE_S:
            for agent, _ in files():
                of = os.path.join(odir, agent + ".json")
                with contextlib.suppress(OSError):
                    os.unlink(of)
                seen.pop((acct, agent), None)
            with contextlib.suppress(OSError):
                os.rmdir(odir)
            live.pop(acct, None)

    def _tokens_back(self):
        """The switch off: each account's opened sign-ins put back as the
        plain files they were, and their seals gone. One with no copy open
        stays sealed until its next terminal opens it (the controller keeps
        sending its key while this node reports a seal), and then comes back."""
        if not os.path.isdir(SEAL_DIR) or not os.path.isdir(OPEN_DIR):
            return
        try:
            users_dir = os.path.join(pwd.getpwnam(self.session_account()).pw_dir, "users")
        except KeyError:
            return
        for acct in sorted(os.listdir(OPEN_DIR))[:500]:
            if not UID_RE.match(acct):
                continue
            with self._tok_lock, contextlib.suppress(KeyError, OSError):
                pw = pwd.getpwnam(user_of(acct))
                home = os.path.join(users_dir, acct)
                for agent, rel in files():
                    of = os.path.join(OPEN_DIR, acct, agent + ".json")
                    if not os.path.isfile(of):
                        continue
                    hf = os.path.join(home, rel)
                    # A plain file already in the home is a refresh renamed
                    # over the link since: newer than the copy, and already
                    # what this puts back, so it stays as it is (B1043).
                    if not plain(hf):
                        with open(of, "rb") as f:
                            data = f.read()
                        with contextlib.suppress(FileNotFoundError):
                            os.unlink(hf)
                        write_atomic(hf, data, mode=0o600, uid=pw.pw_uid, gid=pw.pw_gid)
                    self.token_forget(acct, agent)
                    log(f"tokens: {acct}'s {agent} sign-in is a plain file again")
                with contextlib.suppress(OSError):
                    os.rmdir(os.path.join(OPEN_DIR, acct))

    def _open_seal(self, blob, keys):
        """(what a seal holds, whether only the key from before opened it),
        with the keys a terminal brought: the account's own, or the one
        before it while a rotation keeps it (|prev). (None, False) when
        neither fits."""
        r = tokenseal.rid(tokenseal.header(blob).get("R", ""))
        for k, old in ((keys.get(r), False), (keys.get(r + "|prev"), True)):
            if not k:
                continue
            with contextlib.suppress(tokenseal.Refused):
                return tokenseal.open_with(k, blob), old
        return None, False

    def token_open(self, tk):
        """An account's sign-ins made ready for the terminal a person just
        opened for it (the controller's signed /term, R133), the newest copy
        of each kept. Every open used to write the opened copy from the
        seal, which put a spent token back over a refresh the pass had not
        sealed yet and signed the account out at its next start (B1043).

          a plain file in the home   newer than its seal: sealed, opened
                                     and made a link as the pass does, or
                                     left where it is with no public key
          a copy open already        the truth while it is there: linked,
                                     never written from the seal, and
                                     sealed again when it changed
          neither                    the seal opened into the tmpfs with
                                     the keys this terminal brought,
                                     unwrapped with this boot's secret,
                                     and the home's file a link to it

        Called by the terminal server before the program starts; the keys
        are forgotten when it returns."""
        acct = str(tk.get("acct") or "")
        # Opened with the switch off too: that is how a seal left from while
        # it was on comes back (_tokens_back).
        if not UID_RE.match(acct) or self._tok_e is None or not self.account_users_ready() \
                or not os.path.isdir(os.path.join(SEAL_DIR, acct)) or not self._open_mounted():
            return
        keys = tokenseal.unwrap(self._tok_e, tk["C"], base64.urlsafe_b64decode(tk["w"] + "=" * (-len(tk["w"]) % 4)))
        try:
            pw = pwd.getpwnam(user_of(acct))
            home = os.path.join(pwd.getpwnam(self.session_account()).pw_dir, "users", acct)
            with self._tok_lock:
                if self._open_account(acct, home, pw, keys):
                    self._tok_state()[1][acct] = time.time()
        finally:
            # The keys the terminal brought are let go, zeroed (R158 step 6).
            for k in keys.values():
                wipe(k)

    def _open_account(self, acct, home, pw, keys):
        """token_open's work, sign-in by sign-in; whether the account has a
        copy open after it."""
        on = self.token_seal_on()
        seen = self._tok_state()[0]
        odir = os.path.join(OPEN_DIR, acct)
        some = False
        for agent, rel in files():
            hf, of = os.path.join(home, rel), os.path.join(odir, agent + ".json")
            sealf = os.path.join(SEAL_DIR, acct, agent + ".seal")
            with contextlib.suppress(OSError, tokenseal.Refused):
                if plain(hf):
                    if not on:
                        # The switch off: the plain file is how the sign-in
                        # is kept now, and the seal left from while it was
                        # on is behind it, as _tokens_back would leave them.
                        self.token_forget(acct, agent)
                    elif self._seal_plain(acct, agent, hf, home, pw, opening=True):
                        some = True
                    continue
                if os.path.isfile(of):
                    self._link(hf, of, pw)
                    some = True
                    # A seal only the key from before opens is sealed again
                    # from the copy, so the rotation still completes.
                    old = False
                    with contextlib.suppress(OSError, tokenseal.Refused):
                        with open(sealf, "rb") as f:
                            was, old = self._open_seal(f.read(), keys)
                        wipe(was)
                    self._seal_changed(acct, agent, of, home, anyway=old)
                    continue
                with open(sealf, "rb") as f:
                    data, old = self._open_seal(f.read(), keys)
                if data is None:
                    continue
                # Opened with the key from before, it is sealed again under
                # the account's public key now.
                if old:
                    self._seal(acct, agent, data, home)
                self._acct_open_dir(acct, pw)
                write_atomic(of, data, mode=0o600, uid=pw.pw_uid, gid=pw.pw_gid)
                wipe(data)
                seen[(acct, agent)] = _stamp(os.stat(of))
                self._link(hf, of, pw)
                some = True
        return some

    def token_login_ready(self, acct):
        """Before a sign-in: the account's opened folder made, so a login
        writing through the home's link lands in the tmpfs, never on a disk."""
        if not UID_RE.match(acct or "") or not self.token_seal_on() or not self._open_mounted():
            return
        self._acct_open_dir(acct, pwd.getpwnam(user_of(acct)))
        self._tok_state()[1][acct] = time.time()

    def token_forget(self, acct, agent):
        """A sign-out: the seal and the opened copy gone."""
        with self._tok_lock:
            for p in (os.path.join(SEAL_DIR, acct, agent + ".seal"), os.path.join(OPEN_DIR, acct, agent + ".json")):
                with contextlib.suppress(OSError):
                    os.unlink(p)
            self._tok_state()[0].pop((acct, agent), None)
