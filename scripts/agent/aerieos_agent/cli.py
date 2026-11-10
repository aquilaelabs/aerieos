"""The commands: enroll, run, status, sample."""
import json
import sys
import time
from . import AGENT_VERSION
from .base import DEFAULT_STORES, NODE_JSON, harden, log, own_digest
from .controller import Controller
from .stores import load_state, make_store, save_state, store_path_ok
from .census import Sampler, census
from .agent import Agent


# ---------------------------------------------------------------------------
# commands

def had_state():
    """The record this node already has, or {} on a machine enrolling for
    the first time (load_state ends the command when it is missing)."""
    try:
        with open(NODE_JSON) as f:
            d = json.load(f)
        return d if isinstance(d, dict) else {}
    except (OSError, ValueError):
        return {}


def stores_kept(stores, given, had):
    """The stores an enrollment lands with (B658): a role the flags left
    at its default keeps the path the node's record already has, so a
    script run again on an enrolled node (which hands the provisioner
    nothing for a store it did not name) does not move the toolchains,
    the data and the rest back onto the defaults, with the runner's JDK,
    bb-ftpd and every toolchain gone from where the node looks."""
    kept = dict(had.get("stores") or {}) if isinstance(had, dict) else {}
    out = dict(stores)
    for role, path in kept.items():
        if role in DEFAULT_STORES and role not in given and isinstance(path, str) and path.startswith("/") \
                and out.get(role) == DEFAULT_STORES[role] and not store_path_ok(path):
            out[role] = path
    return out


def cmd_enroll(args):
    opts = {"--controller": "", "--token": "", "--user": "bb", "--pin": "",
            "--session-user": "", "--reach": "", "--door": "", "--door-host": "",
            "--release-key": ""}
    stores = dict(DEFAULT_STORES)
    given = set()
    it = iter(args)
    for a in it:
        if a == "--store":
            role, _, path = next(it, "").partition("=")
            if role not in DEFAULT_STORES:
                raise SystemExit("--store takes " + ", ".join(f"{r}=/path" for r in DEFAULT_STORES))
            why = store_path_ok(path)
            if why:
                raise SystemExit(f"--store {role}: {why}")
            stores[role] = path
            given.add(role)
        elif a in opts:
            opts[a] = next(it, "")
        else:
            raise SystemExit(f"unknown option {a}")
    stores = stores_kept(stores, given, had_state())
    if not opts["--controller"] or not opts["--token"]:
        raise SystemExit("enroll needs --controller URL and --token bbe_…")
    if not opts["--token"].startswith("bbe_"):
        raise SystemExit("that is not an enrollment token (they start bbe_); "
                         "mint one on the controller's Nodes page")
    marks = {}
    for role, path in stores.items():
        # A store that cannot be made is reported, not fatal: its free space
        # reads as zero on the row, which is the true answer. What each one
        # DID create is kept, so that if the store is moved later the
        # directories this put there can be taken back and nothing else.
        try:
            marks[role] = make_store(path)
        except OSError as e:
            print(f"note: {role} store {path} could not be created ({e.strerror}); "
                  "it will report no space until it exists")
    if opts["--reach"] not in ("", "public"):
        raise SystemExit("--reach takes public: the controller published at a hostname by a tunnel "
                         "from home, verified by the system's CAs")
    # Through a public hostname (R170) the controller's own certificate is
    # never seen, only the name's public one: verified by CA, never pinned.
    if opts["--reach"] == "public":
        opts["--pin"] = Controller.CA
    ctl = Controller(opts["--controller"], opts["--token"], opts["--pin"])
    if opts["--reach"] == "public" and ctl.scheme != "https":
        raise SystemExit("through a public hostname the controller is an https hostname")
    state = {"controller": ctl.url, "user": opts["--user"], "stores": stores,
             "store_made": marks}
    if opts["--reach"]:
        state["reach"] = opts["--reach"]
        state["tunnel"] = {"kind": opts["--reach"], "host": ctl.host}
    # The door in for SSH (R174): which client the provisioner installed,
    # and its name, so the census says so and the row's switch finds it.
    if opts["--door"]:
        if opts["--door"] not in ("cloudflared", "tailscale"):
            raise SystemExit("--door takes cloudflared or tailscale")
        state["door"] = {"kind": opts["--door"], "host": opts["--door-host"][:253]}
    # AerieOS's release key, pinned here and now (release.py): the one the
    # Enroll script carries, else the one this machine pinned before, with
    # what its console said about unsigned builds. Never from a running
    # controller's word.
    from . import release
    was = {}
    try:
        was = load_state()
    except SystemExit:
        was = {}
    if opts["--release-key"] and not release.clean_key(opts["--release-key"]):
        raise SystemExit("--release-key takes the release key as 64 hex characters")
    key = release.clean_key(opts["--release-key"]) or release.pinned(was)
    if key:
        state["release_key"] = key
        print(f"pinned AerieOS's release key {key[:16]}…: this node takes only agent updates signed by it")
    if release.unsigned_ok(was):
        state["unsigned_ok"] = True
    # The account sessions run as (roadmap #24), when this agent runs as
    # root. Recorded even when empty, so `status` shows the decision.
    state["session_user"] = opts["--session-user"]
    st, r = ctl.call("enroll", {"census": census(state), "version": AGENT_VERSION,
                                "digest": own_digest(), "user": opts["--user"]},
                     timeout=30)
    if st != 200:
        raise SystemExit(f"enrollment refused ({st}): {r.get('error', 'no answer')}")
    if ctl.scheme == "https":
        pin = opts["--pin"] or getattr(ctl, "seen_pin", "")
        state["pin"] = pin
        if pin == Controller.CA:
            print(f"the controller is {ctl.host}, verified by the system's certificate authorities "
                  "on every call (a hostname behind a tunnel, whose own certificate this node never sees)")
        elif not opts["--pin"]:
            print(f"pinned the controller's certificate on first use: {pin}\n"
                  f"  check it against the controller; a different one next "
                  f"time is refused")
    else:
        print("note: plain http. The node token travels unencrypted on this "
              "network, as the dashboard's own credential does. Put TLS in "
              "front of the controller and re-enroll to pin it.")
    state.update({"node_id": r["node_id"], "token": r["token"],
                  "name": r.get("name", ""), "capabilities": r.get("capabilities", []),
                  "enrolled": int(time.time()), "scheme": ctl.scheme})
    save_state(state, console=True)
    print(f"enrolled as node {r['node_id']} ({r.get('name')}); "
          f"capabilities: {', '.join(r.get('capabilities') or []) or 'none'}")
    print(f"  credential in {NODE_JSON} (0600); jobs run as {opts['--user']}"
          + (f", sessions as {opts['--session-user']}" if opts["--session-user"] else ""))


def cmd_run():
    harden()
    # The new names made to answer where this machine has only the old ones
    # (names.py): added, never moved, before anything here reads a path.
    from . import names
    from .base import own_path
    names.ensure(own_path(), log)
    state = load_state()
    log(f"node {state.get('node_id')} → {state.get('controller')}, agent "
        f"{AGENT_VERSION} {own_digest()[:19]}…")
    Agent(state).loop()


def cmd_status():
    state = load_state()
    shown = {k: v for k, v in state.items() if k != "token"}
    print(json.dumps(shown, indent=2))
    ctl = Controller(state["controller"], state["token"], state.get("pin", ""))
    st, r = ctl.call("hello", {"census": census(state), "version": AGENT_VERSION,
                               "digest": own_digest()}, timeout=20)
    if st == 200:
        n = r.get("node") or {}
        cur = (r.get("agent") or {}).get("digest") == own_digest()
        print(f"controller answers: this is node {n.get('id')} ({n.get('name')}), "
              f"state {n.get('state')}; agent {'current' if cur else 'differs from the controller’s'}")
    else:
        print(f"controller: {st} {r.get('error', 'no answer')}")
        sys.exit(1)


def cmd_follow(args):
    """follow URL EXPECT (R175 step 3): the line the new controller's Nodes
    page gives for a node that outlived the old controller, so it was never
    told the move. Knocks there at once with this node's own token, checks
    the answer against EXPECT, and on the right answer writes the new
    address and pin into node.json; the running agent re-reads node.json
    once the controller it had has stayed quiet for three hellos, or at
    once when its service is restarted. Nothing is enrolled again: the
    node keeps its id, its token, its containers and its synced copies."""
    if len(args) != 2 or not args[0].startswith(("http://", "https://")):
        raise SystemExit("follow takes the new controller's address and this node's challenge, as its Nodes page shows them")
    state = load_state()
    from .agent import follow
    ok, why = follow(state, args[0], args[1])
    if not ok:
        raise SystemExit(why or "nothing to knock on")
    print(f"this node follows the controller to {state['controller']}: the running agent takes it once the old "
          "address has stayed quiet for three hellos, or now if its service is restarted")


def _at_console(what):
    """A choice about what this machine trusts is made by a person at it:
    root, on a terminal. A job the controller sends has neither a terminal
    nor a reason to ask."""
    import os
    if os.geteuid() != 0:
        raise SystemExit(f"{what} is root's on this machine: run it with sudo")
    if not sys.stdin.isatty():
        raise SystemExit(f"{what} is said at this machine's own console or over ssh, by a person: "
                         "it takes a terminal, which a job does not have")


def cmd_release_key(args):
    """release-key [HEX|none]: show, pin or drop AerieOS's release key here."""
    from . import release
    state = load_state()
    if not args:
        key = release.pinned(state)
        print(f"release key: {key}" if key else "release key: none pinned; agent updates are taken on the controller's word")
        print("unsigned builds: " + ("allowed here" if release.unsigned_ok(state) else "refused" if key else "not asked, with no key pinned"))
        return
    _at_console("pinning a release key")
    if args[0] == "none":
        state.pop("release_key", None)
        save_state(state, console=True)
        print("no release key pinned: agent updates are taken on the controller's word again")
        return
    key = release.clean_key(args[0])
    if not key:
        raise SystemExit("the release key is 64 hex characters, as config/aerieos-release.pub and the Enroll script carry it")
    state["release_key"] = key
    save_state(state, console=True)
    print(f"pinned {key[:16]}…: this node takes only agent updates signed by it")


def cmd_unsigned(args):
    """unsigned on|off: whether this machine takes an agent no release signed."""
    from . import release
    if not args or args[0] not in ("on", "off"):
        raise SystemExit("unsigned takes on or off")
    _at_console("allowing unsigned builds")
    state = load_state()
    if args[0] == "on":
        state["unsigned_ok"] = True
    else:
        state.pop("unsigned_ok", None)
    save_state(state, console=True)
    print(("this machine takes agent updates no release signed (a controller built from a branch)" if args[0] == "on"
           else "this machine refuses agent updates the pinned release key did not sign"
           + ("" if release.pinned(state) else "; none is pinned yet, so that applies once one is")))


def main(argv):
    cmd = argv[0] if argv else ""
    if cmd == "enroll":
        cmd_enroll(argv[1:])
    elif cmd == "release-key":
        cmd_release_key(argv[1:])
    elif cmd == "unsigned":
        cmd_unsigned(argv[1:])
    elif cmd == "follow":
        cmd_follow(argv[1:])
    elif cmd == "run":
        cmd_run()
    elif cmd == "status":
        cmd_status()
    elif cmd == "sample":
        print(json.dumps(Sampler().sample(load_state(), 0), indent=2))
    else:
        print("Runs anywhere" + sys.modules[__package__].__doc__.split("Runs anywhere")[-1].rstrip() if cmd in ("", "-h", "--help")
              else f"unknown command {cmd}", file=sys.stderr)
        sys.exit(0 if cmd in ("", "-h", "--help") else 64)
