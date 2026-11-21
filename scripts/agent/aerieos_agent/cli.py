"""The commands: enroll, run, status, sample."""
import json
import sys
import time
from . import AGENT_VERSION
from .base import DEFAULT_STORES, NODE_JSON, harden, log, own_digest
from .controller import KEY_PIN, Controller
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
                and out.get(role) == DEFAULT_STORES[role] and not store_path_ok(path, shape=False):
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
            # Held to a store's one shape, unless it is where this node's
            # record already has that store: a script run again with the
            # flags it was first run with does not refuse the node its own.
            mine = (had_state().get("stores") or {}).get(role) == path
            why = store_path_ok(path, shape=not mine)
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
    if opts["--release-key"] and not release.clean_keys(opts["--release-key"]):
        raise SystemExit("--release-key takes the release key as 64 hex characters, and its spare after a comma")
    pins = release.clean_keys(opts["--release-key"]) or release.keys(was)
    unsigned = release.unsigned_ok(was)
    added = release.also(was)
    unpinned = release.unpinned(was)
    root_off = was.get("root_off") is True
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
        elif pin.startswith(KEY_PIN):
            print("pinned the controller's key, as the enrollment carried it: every connection must present a "
                  "certificate over that key, so the controller's renewed certificates are taken and no other is")
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
    # ...set here, at the save that is the console's, and not before:
    # nothing between could then write the record without them.
    state.pop("release_key", None)
    state.pop("release_spare", None)
    state.pop("release_also", None)
    state.pop("release_unpinned", None)
    state.pop("unsigned_ok", None)
    state.pop("root_off", None)
    if root_off:
        # What the console said of root commands outlives an enrollment, as
        # the pin does: enrolling again is the controller's script.
        state["root_off"] = True
    if added:
        # ...and so do the keys a person added here: the script names the
        # release key and its spare, and knows nothing of these.
        state["release_also"] = added
    if pins:
        state["release_key"] = pins[0]
        if len(pins) > 1:
            state["release_spare"] = pins[1]
        print(f"pinned AerieOS's release key {pins[0][:16]}…" + (f" and its spare {pins[1][:16]}…" if len(pins) > 1 else "")
              + ": this node takes only agent updates signed by " + ("one of them" if len(pins) > 1 else "it"))
    elif unpinned:
        # A person chose here to pin no key (release-key none): a script
        # that names none leaves that standing, as it leaves a pin.
        state["release_unpinned"] = True
    if unsigned:
        state["unsigned_ok"] = True
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


def cmd_selfcheck():
    """This agent loaded as `run` loads it, every module of it compiled, and
    this node's state read, said in one line: what a self-update asks of the
    file it is about to install, before that file replaces the running one
    (R241). It dials nothing and changes nothing. Reaching here is the first
    half: the entry imported this module, and with it everything `run`
    imports. The rest are compiled and not run, so a module that is only
    loaded when its work comes up, and may want a library this machine does
    not have, cannot refuse an update it would never have broken."""
    import pkgutil
    pkg = sys.modules[__package__]
    for m in pkgutil.iter_modules(pkg.__path__):
        name = f"{__package__}.{m.name}"
        src = m.module_finder.find_spec(name).loader.get_source(name)
        compile(src or "", name, "exec")
    state = load_state()
    # Whether this machine holds file work as an account (base.acting_as):
    # tried here as root, so an update's job says it before anything on the
    # node relies on it. It never fails the check: the agent does that work
    # as root, as before, where it does not hold.
    from .base import fs_probe
    who = None
    if state.get("user") and state.get("user") != "root":
        import pwd
        try:
            pw = pwd.getpwnam(state["user"])
            who = (pw.pw_uid, pw.pw_gid)
        except KeyError:
            who = None
    ok, why = fs_probe(who)
    fs = "holds" if ok else f"not tried ({why})" if ok is None else f"DOES NOT HOLD ({why})"
    print(f"selfcheck ok {AGENT_VERSION} {own_digest()[:19]}; file work as the account: {fs}")


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
    """release-key [HEX[,HEX]|none]: show, pin or drop AerieOS's release
    key here, with its spare after a comma. Dropping it is a choice this
    machine keeps (release_unpinned): it pins no key by itself afterwards,
    until one is pinned here again. release-key add HEX and
    release-key drop HEX: trust, or stop trusting, one more key beside
    them, the one a controller somebody built themselves is signed with."""
    from . import release
    state = load_state()
    if not args:
        key, spare, added = release.pinned(state), release.spare(state), release.also(state)
        chose = ", by this console's choice" if release.unpinned(state) else ""
        print(f"release key: {key}" if key else f"release key: none pinned{chose}"
              + ("" if added else "; agent updates are taken on the controller's word, "
                 + ("checked against nothing, and this node pins no key by itself" if chose else
                    "and the first one signed by a release key it names pins that key")))
        if spare:
            print(f"spare key:   {spare}")
        for k in added:
            print(f"added here:  {k}")
        print("unsigned builds: " + ("allowed here" if release.unsigned_ok(state) else "refused" if release.trusted(state)
                                     else "not asked, with no key pinned"))
        print("older agents:    " + ("allowed here" if release.older_ok(state) else "refused" if release.trusted(state)
                                     else "not asked, with no key pinned"))
        return
    if args[0] in ("add", "drop"):
        _release_also(state, args[0], args[1:])
        return
    _at_console("pinning a release key")
    if args[0] == "none":
        state.pop("release_key", None)
        state.pop("release_spare", None)
        # A person's choice, kept: the first signed update pins no key on
        # a node that was told to have none (release.first_pin).
        state["release_unpinned"] = True
        save_state(state, console=True)
        added = release.also(state)
        print(("no release key pinned: this node takes what its controller sends, checked against nothing" if not added else
               "no release key pinned: this node still takes only agent updates signed by "
               + ("the key" if len(added) == 1 else f"one of the {len(added)} keys") + " added here")
              + ", and will not pin a release key by itself until one is pinned here again")
        return
    pins = release.clean_keys(",".join(args))
    if not pins:
        raise SystemExit("the release key is 64 hex characters, as config/aerieos-release.pub and the Enroll script carry it, "
                         "and its spare after a comma")
    state["release_key"] = pins[0]
    state.pop("release_spare", None)
    state.pop("release_unpinned", None)
    if len(pins) > 1:
        state["release_spare"] = pins[1]
    save_state(state, console=True)
    print(f"pinned {pins[0][:16]}…" + (f" and its spare {pins[1][:16]}…" if len(pins) > 1 else "")
          + ": this node takes only agent updates signed by " + ("one of them" if len(pins) > 1 else "it"))


def _release_also(state, verb, args):
    """release-key add HEX, release-key drop HEX: the keys this machine
    trusts beside the release key and its spare (release.also). A person's
    at the machine, like the pin: no job reaches here."""
    from . import names, release
    _at_console("adding a key this machine trusts" if verb == "add" else "dropping a key this machine trusts")
    key = release.clean_key(args[0]) if len(args) == 1 else ""
    if not key:
        raise SystemExit(f"release-key {verb} takes one key as 64 hex characters: the public half of the key a build is signed with")
    added = release.also(state)
    if verb == "drop":
        if key not in added:
            raise SystemExit(f"{key[:16]}… is not a key added here: {names.command()} release-key shows them")
        added.remove(key)
        state.pop("release_also", None)
        if added:
            state["release_also"] = added
        save_state(state, console=True)
        print(f"dropped {key[:16]}…: this node takes nothing more on its signature")
        return
    if key in release.keys(state):
        print(f"{key[:16]}… is pinned here as the release key or its spare already: nothing added")
        return
    if key in added:
        print(f"{key[:16]}… was added here already")
        return
    if len(added) >= release.ALSO_MAX:
        raise SystemExit(f"this node holds {release.ALSO_MAX} added keys, the most it keeps: drop one first "
                         f"({names.command()} release-key drop HEX)")
    state["release_also"] = added + [key]
    save_state(state, console=True)
    print(f"added {key[:16]}…: this node takes "
          + ("agent updates, root's tools and the bundle's files signed by it, beside what the release key signs"
             if release.keys(state)
             else "only agent updates, root's tools and the bundle's files signed by a key added here"))


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
           else ("this machine refuses agent updates no key it trusts signed" if release.also(state)
                 else "this machine refuses agent updates the pinned release key did not sign")
           + ("" if release.trusted(state) else "; none is pinned yet, so that applies once one is")))


def cmd_older(args):
    """older on|off: whether this machine takes a signed agent older than
    the one it runs (release.may_install): a person's word that they mean
    to go back, kept until they say off."""
    if not args or args[0] not in ("on", "off"):
        raise SystemExit("older takes on or off")
    _at_console("letting an older agent be put back")
    state = load_state()
    if args[0] == "on":
        state["older_ok"] = True
    else:
        state.pop("older_ok", None)
    save_state(state, console=True)
    print("this machine takes a signed agent older than the one it runs, until older off" if args[0] == "on"
          else "this machine refuses a signed agent older than the one it runs")


def _sig_given(text):
    """The signature check-update was handed: its 128 hex characters, or a
    file that holds them, bare or as the build's own agent.sig holds them
    (a JSON object's "sig"). "" for none; what is neither is passed on as
    it is, and read as no signature."""
    from . import release
    text = str(text or "").strip()
    if not text or release.SIG_RE.fullmatch(text.lower()):
        return text.lower()
    try:
        with open(text, encoding="utf-8") as f:
            held = f.read(8192).strip()
    except (OSError, ValueError):
        return text
    try:
        d = json.loads(held)
    except ValueError:
        return held
    return str(d.get("sig") or "") if isinstance(d, dict) else held


def cmd_check_update(args):
    """check-update FILE [SIG]: whether this node would take FILE as its
    agent, by the rule its own update goes by (release.may_install), with
    the signature that came with it. For the provisioner, which swaps an
    agent in itself and so passed the node's own check by: it asks before
    the swap. One line is said, and the exit is 0 when the file may be
    installed and 77 when it is refused, the code the update's own job ends
    with. It reads the file and node.json and writes nothing: no key is
    pinned here, whatever the signature is under."""
    import hashlib
    from . import release
    if not 1 <= len(args) <= 2 or not args[0]:
        print("check-update takes the agent file, and after it the signature that came with it", file=sys.stderr)
        sys.exit(64)
    try:
        with open(args[0], "rb") as f:
            body = f.read()
        digest = "sha256:" + hashlib.sha256(body).hexdigest()
    except OSError as e:
        print(f"refused: {args[0]} could not be read ({e.strerror or e})")
        sys.exit(77)
    # The record as it is on the disk, which the console writes. A machine
    # with none has pinned nothing; one whose record cannot be read may
    # have, so nothing is taken on that.
    try:
        with open(NODE_JSON) as f:
            state = json.load(f)
    except FileNotFoundError:
        state = {}
    except ValueError:
        state = None
    except OSError as e:
        print(f"refused: {NODE_JSON} could not be read ({e.strerror or e}), so what this node pinned is not known; "
              "check-update is root's")
        sys.exit(77)
    if not isinstance(state, dict):
        # No agent starts on such a record either: enrolling again writes a new one.
        print(f"not checked: {NODE_JSON} is not a node's record, so no key pinned here can be read from it")
        return
    ok, said = release.may_install(state, digest, _sig_given(args[1] if len(args) > 1 else ""), body=body)
    print(said)
    if not ok:
        sys.exit(77)


def cmd_root_asks(args):
    """root-asks [on|off]: whether this machine runs a root command the
    controller sends (R227 step 2)."""
    state = load_state()
    if not args:
        print("root commands from the controller: "
              + ("refused here" if state.get("root_off") is True else "run once a person there allowed them"))
        return
    if args[0] not in ("on", "off"):
        raise SystemExit("root-asks takes on or off")
    _at_console("deciding whether root commands are run here")
    if args[0] == "off":
        state["root_off"] = True
    else:
        state.pop("root_off", None)
    save_state(state, console=True)
    print("this machine refuses every root command the controller sends (aerie root run, a schedule as root), whoever "
          "allowed it there; what AerieOS does as root by name (storage, updates, its own tools) goes on, and where this "
          "machine runs containers, Docker here is still root's"
          if args[0] == "off" else
          "this machine runs a root command the controller sends once a person there allowed it")


def main(argv):
    cmd = argv[0] if argv else ""
    if cmd == "enroll":
        cmd_enroll(argv[1:])
    elif cmd == "release-key":
        cmd_release_key(argv[1:])
    elif cmd == "unsigned":
        cmd_unsigned(argv[1:])
    elif cmd == "older":
        cmd_older(argv[1:])
    elif cmd == "check-update":
        cmd_check_update(argv[1:])
    elif cmd == "root-asks":
        cmd_root_asks(argv[1:])
    elif cmd == "follow":
        cmd_follow(argv[1:])
    elif cmd == "run":
        cmd_run()
    elif cmd == "selfcheck":
        cmd_selfcheck()
    elif cmd == "status":
        cmd_status()
    elif cmd == "sample":
        print(json.dumps(Sampler().sample(load_state(), 0), indent=2))
    else:
        print("Runs anywhere" + sys.modules[__package__].__doc__.split("Runs anywhere")[-1].rstrip() if cmd in ("", "-h", "--help")
              else f"unknown command {cmd}", file=sys.stderr)
        sys.exit(0 if cmd in ("", "-h", "--help") else 64)
