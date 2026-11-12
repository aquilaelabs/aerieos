"""Behind `aerie login --flow --agent ID` and `--out --agent ID` for a coding
agent a tool pack brings (R233 step 6): its sign-in run for the page.

A shipped agent's sign-in is a command that prints a link and waits; a
pack's agent may sign in on a screen of its own (Antigravity CLI opens on a
menu, then draws the link and a field for the code). This runs that program
under a terminal of its own, wide enough that a long link stays on one row,
and works its screens from what the pack says of them (agent.signin.flow,
held to plain words by toolpacks.py):

  answers      what it asks before the link: the words a screen shows, and
               the key or short word typed there, Enter after it
  url          how the link it prints starts
  prompt       the words it waits at for the code the provider's page hands
               back, which is read from this flow's own terminal and typed
  code_after   or the words a one-time code follows, for a flow where the
               person types the code on the provider's page
  kept         the file under the account's home whose arrival says the
               account is signed in, which ends the flow
  logout       its own sign-out command; left out, a sign-out removes `kept`

What goes up the job's log is this driver's lines and never the program's
screen: the link on one line, a one-time code on another, and the words the
controller's sign-in card waits for (signin.py PACK_FLOW). The code that
comes down is typed into the program and not echoed, so the log never holds
it. The program is ended once its sign-in is kept: what it asks after that
(a color scheme, terms, a folder's trust) is the person's own to answer, in
their first session.

    login-flow.py has AGENT    exit 0 when this bundle's packs bring AGENT
                               with a sign-in flow
    login-flow.py in AGENT     run the flow in HOME
    login-flow.py out AGENT    sign out in HOME
"""
import contextlib
import fcntl
import importlib.util
import os
import re
import select
import shutil
import signal
import struct
import subprocess
import sys
import termios
import time

HERE = os.path.dirname(os.path.abspath(__file__))
# The terminal the program draws on: wide, so a link is one row of it.
ROWS, COLS = 50, 2000
# Escape sequences taken out of what a screen says: a title or a link's
# target (OSC), a color or a move (CSI), and the short ones.
OSC = re.compile(r"\x1b\][^\x07\x1b]*(?:\x07|\x1b\\)")
CSI = re.compile(r"\x1b\[[0-?]*[ -/]*[@-~]")
SHORT = re.compile(r"\x1b[()][0-9A-Za-z]|\x1b[@-Z\\^_=>]")
# How long the screen is quiet before a link on it is taken as whole, how
# long the program has after a code to keep the sign-in, and the flow's own
# limit (the job's is a little longer). BB_FLOW_KEEP_S is the suite's seam.
QUIET_S, KEEP_S, LIMIT_S = 0.6, float(os.environ.get("BB_FLOW_KEEP_S") or 120), 880
# How much of its screen's bytes is kept to read: a link and the screens
# around it many times over, and no more however long it draws.
KEEP_CHARS = 120000


def say(msg):
    sys.stdout.write(f"[aerieos] {msg}\n")
    sys.stdout.flush()


def flows():
    """{agent: its adapter} for the packs' agents in this bundle that
    describe a sign-in's flow: login-list.py holds the one reading."""
    spec = importlib.util.spec_from_file_location("login_list", os.path.join(HERE, "login-list.py"))
    ll = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(ll)
    return ll.pack_flows()


def visible(raw):
    """What a screen's bytes say, the escapes out of them."""
    return SHORT.sub("", CSI.sub("", OSC.sub("", raw)))


def squash(text):
    """Words as they are compared: no spaces (a screen may draw a gap as a
    move, not a space) and no case."""
    return re.sub(r"\s+", "", text).lower()


def link_in(raw, prefix):
    """The longest link in `raw` that starts as the pack says, or "": the
    one a terminal link carries whole, or the one drawn on one wide row."""
    got = re.findall(re.escape(prefix) + r"[^\s\x1b\x07\"'<>]*", raw)
    return max(got, key=len) if got else ""


def code_in(text, after):
    """The one-time code that follows the words `after` on the screen."""
    flat = re.sub(r"\s+", " ", text)
    at = flat.lower().rfind(after.lower())
    if at < 0:
        return ""
    m = re.search(r"(?<![A-Za-z0-9-])([A-Z0-9]{4,12}(?:-[A-Z0-9]{3,12}){0,3})(?![A-Za-z0-9-])", flat[at + len(after):at + len(after) + 160])
    return m.group(1) if m else ""


def kept_now(path):
    try:
        return os.path.getsize(path) > 0
    except OSError:
        return False


def end(proc):
    """The program ended, its whole group: asked, then made to."""
    for sig, wait in ((signal.SIGTERM, 3), (signal.SIGKILL, 2)):
        if proc.poll() is not None:
            return
        with contextlib.suppress(OSError):
            os.killpg(proc.pid, sig)
        with contextlib.suppress(subprocess.TimeoutExpired):
            proc.wait(timeout=wait)


def sign_in(agent, a):
    flow = a["signin"]["flow"]
    home = os.environ.get("HOME") or ""
    name = a.get("name") or agent
    kept = os.path.join(home, flow["kept"])
    argv = [str(x) for x in a.get("login") or []]
    if not home or not argv:
        say(f"{name} has no sign-in to run here")
        return 1
    if kept_now(kept):
        say(f"already signed in to {name} here: sign out first to sign in as somebody else")
        return 0
    if not shutil.which(argv[0]):
        say(f"{a.get('product') or name} is not installed on this machine: Install on {name}'s card in the Library, with this node picked, puts it here")
        return 1
    # A folder of its own to start in, empty and the account's: a program
    # that asks about the folder it is in is asked about this one.
    where = os.path.join(home, ".cache", "aerieos", "signin")
    os.makedirs(where, mode=0o700, exist_ok=True)
    master, slave = os.openpty()
    fcntl.ioctl(slave, termios.TIOCSWINSZ, struct.pack("HHHH", ROWS, COLS, 0, 0))
    env = dict(os.environ, TERM="xterm-256color", COLUMNS=str(COLS), LINES=str(ROWS))
    env.update({str(k): str(v) for k, v in (a.get("env") or {}).items()})
    # What this flow tells the controller with afterwards is aerie's own to
    # hold: the program signing in has no use for it.
    for k in ("BB_TOKEN", "BB_LOGIN_AUTH"):
        env.pop(k, None)
    # The code is typed into the program, never said back up the log.
    with contextlib.suppress(termios.error, OSError):
        attrs = termios.tcgetattr(0)
        attrs[3] &= ~termios.ECHO
        termios.tcsetattr(0, termios.TCSANOW, attrs)
    try:
        proc = subprocess.Popen(argv, stdin=slave, stdout=slave, stderr=slave, cwd=where, env=env, close_fds=True,
                                start_new_session=True, preexec_fn=lambda: fcntl.ioctl(0, termios.TIOCSCTTY, 0))
    except OSError as e:
        os.close(master), os.close(slave)
        say(f"could not start {name}'s sign-in: {e}")
        return 1
    os.close(slave)
    signal.signal(signal.SIGTERM, lambda *_: (end(proc), sys.exit(1)))
    # `raw` is what its screen has said (the newest of it); `since`, what it
    # has said since the last thing typed into it, which is where the next
    # words to answer are looked for, so a screen drawn twice is answered once.
    raw = since = ""
    started = time.time()
    todo = [[squash(x["when"]), x.get("send", ""), 0.0] for x in flow.get("answers") or []]
    prompt, after = squash(flow.get("prompt") or ""), flow.get("code_after") or ""
    link = code = ""
    link_at = sent_at = 0.0
    asked = False
    watch = [master, 0]
    try:
        while True:
            try:
                ready, _, _ = select.select(watch, [], [], 0.2)
            except (OSError, ValueError):
                break
            now = time.time()
            if master in ready:
                try:
                    chunk = os.read(master, 65536)
                except OSError:
                    chunk = b""
                if chunk:
                    said = chunk.decode("utf-8", "replace")
                    raw, since = (raw + said)[-KEEP_CHARS:], (since + said)[-KEEP_CHARS:]
            if 0 in ready:
                try:
                    typed = os.read(0, 8192)
                except OSError:
                    typed = b""
                if not typed:
                    watch = [master]              # nobody is left to type a code
                elif asked and not sent_at:
                    got = "".join(c for c in typed.decode("utf-8", "replace") if "!" <= c <= "~")[:2048]
                    if got:
                        with contextlib.suppress(OSError):
                            os.write(master, got.encode())
                            time.sleep(0.4)
                            os.write(master, b"\r")
                        sent_at, since = now, ""
                        say(f"the code is with {name}; waiting for it to keep the sign-in")
            if kept_now(kept):
                say(f"signed in to {name} on {os.environ.get('BB_NODE') or 'this machine'}")
                return 0
            text = visible(raw)
            flat, fresh = squash(text), squash(visible(since))
            # What it asks before the link, each answered once: typed when
            # its words have stood on the screen for a moment, so the
            # program is reading by then.
            for row in todo:
                when, send, at = row
                if when and when in fresh:
                    if not at:
                        row[2] = now
                    elif now - at >= QUIET_S:
                        with contextlib.suppress(OSError):
                            os.write(master, send.encode() + b"\r")
                        since = ""
                        todo.remove(row)
                    break
            if not link:
                got = link_in(raw, flow["url"])
                if got:
                    link_at = link_at or now
                    if now - link_at >= QUIET_S or (prompt and prompt in flat) or (after and code_in(text, after)):
                        link = got
                        say(f"open this link to sign in: {link}")
            if link and after and not code:
                code = code_in(text, after)
                if code:
                    say(f"then enter this code there: {code}")
            if link and prompt and not asked and prompt in flat:
                asked = True
                say("Paste code: the one that page gives you once you have signed in there")
            if proc.poll() is not None:
                if kept_now(kept):
                    say(f"signed in to {name} on {os.environ.get('BB_NODE') or 'this machine'}")
                    return 0
                break
            if sent_at and now - sent_at > KEEP_S:
                break
            if now - started > LIMIT_S:
                say("the sign-in was not finished in time")
                return 1
    finally:
        end(proc)
        with contextlib.suppress(OSError):
            os.close(master)
    # Why, in the program's own words: what its screen said last (after the
    # code, where one was typed).
    words = re.sub(r"\s+", " ", visible(since if sent_at else raw)).strip()
    say(f"{name} did not keep a sign-in" + (" after the code" if sent_at else "")
        + (f"; its screen last said: {words[-240:]}" if words else ""))
    return 1


def sign_out(agent, a):
    flow = a["signin"]["flow"]
    home = os.environ.get("HOME") or ""
    name = a.get("name") or agent
    if not home:
        return 1
    argv = [str(x) for x in flow.get("logout") or []]
    if argv:
        if not shutil.which(argv[0]):
            say(f"{a.get('product') or name} is not installed on this machine, so there is no sign-in of its own to end")
            return 1
        try:
            got = subprocess.run(argv, cwd=home, timeout=90, check=False).returncode
        except (OSError, subprocess.SubprocessError) as e:
            say(f"{name}'s sign-out did not run: {e}")
            return 1
        if got != 0:
            return got
    # ...and the file its sign-in is kept in, which is the sign-in: a link to
    # a sealed copy goes the same way (the node's agent forgets the seal).
    with contextlib.suppress(FileNotFoundError):
        os.unlink(os.path.join(home, flow["kept"]))
    say(f"signed out of {name} on {os.environ.get('BB_NODE') or 'this machine'}")
    return 0


def main(argv):
    if len(argv) != 2 or argv[0] not in ("has", "in", "out"):
        sys.stderr.write("usage: login-flow.py has|in|out AGENT\n")
        return 2
    a = flows().get(argv[1])
    if not a:
        return 1
    if argv[0] == "has":
        return 0
    return sign_in(argv[1], a) if argv[0] == "in" else sign_out(argv[1], a)


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
