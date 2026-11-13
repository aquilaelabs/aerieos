"""What every part of the agent shares: the constants naming the node's paths and tools, the log, and the small runners of a command."""
import contextlib
import json
import hashlib
import os
import re
import shutil
import subprocess
import sys
import threading
import time
from . import names
from .names import ETC, VAR


# Where the enrollment lands. Overridable for tests, which run a throwaway
# agent against a throwaway controller and must not touch /etc.
NODE_JSON = os.environ.get("BUILDERBOT_NODE_JSON", ETC + "/node.json")
DEFAULT_STORES = {"data": VAR + "/data",
                  "toolchains": VAR + "/toolchains",
                  "cache": VAR + "/cache",
                  # What this node keeps of a project's built artifacts, so
                  # an emulator or a container here starts from a local copy
                  # rather than pulling one over the link every time, which
                  # is free on a LAN and is not on a node in somebody's
                  # cloud. Per project underneath (artifact_dir), because a
                  # VM may be several projects' node.
                  "artifacts": VAR + "/artifacts",
                  # What a dev instance KEEPS: the databases, the uploads, the
                  # caches its containers write, under <appdata>/<project>/
                  # <instance>. A store like the other four (R17 step 2), so
                  # the node reports its path and its headroom and the config
                  # plane edits it there. It used to be BB_DEV_DATA_DIR on the
                  # CONTROLLER, which is a fact about a node kept on the wrong
                  # machine, and an optional /devdata mount to go with it.
                  "appdata": VAR + "/appdata"}

# The session half (roadmap #24): the screen relay's port, the one a
# terminal (R133) and a VM's screen (R99) come in on, and the address it
# binds. The bind address defaults to the address the default route leaves
# by (the LAN one the controller reaches), not the loopback: the controller
# dials in from another machine, and the firewall keeps the port to it. The
# port is a seam for the suite alone, which runs several agents on one box;
# the census says it, so the controller dials what the node listens on.
SCREEN_PORT = int(os.environ.get("BUILDERBOT_SCREEN_PORT") or 7684)
SESSION_BIND = os.environ.get("BUILDERBOT_SESSION_BIND", "")
# What the census reports about it, kept by the Agent and read by census():
# the census is a function of the machine, and the session's state is the
# one part of the machine this process itself is holding.
SESSION = {}
# What the screen relay says of itself in the hello (census, R243): its
# certificate's sha256 once it has one, which the controller pins, and that
# it takes a signed request once. Set by screen.py.
RELAY = {"tls": "", "once": True}
# How often a node whose loop is held by a census says it is still there
# (census_beating): well inside the controller's three missed polls.
BEAT_S = 20

# Where a store may NOT be put. The stores are directories this agent
# creates, fills, and (for the cache) empties on request, so a store
# pointed at a system tree is a delete waiting to happen: `--cache /etc`
# would make Clear cache remove every directory under /etc. Refused here and
# again on the controller, deliberately twice: the tab should say no before
# anybody presses, and the node should refuse whatever it is told, which is
# the same reasoning as the capability check (docs/nodes.md §15 door 7).
STORE_DENY_EXACT = {"/", "/bin", "/boot", "/dev", "/etc", "/home", "/lib",
                    "/lib32", "/lib64", "/libx32", "/media", "/mnt", "/opt",
                    "/proc", "/root", "/run", "/sbin", "/srv", "/sys", "/tmp",
                    "/usr", "/var", "/var/lib", "/var/log"}
STORE_DENY_UNDER = ("/bin/", "/boot/", "/dev/", "/etc/", "/lib/", "/lib32/",
                    "/lib64/", "/libx32/", "/proc/", "/root/", "/run/",
                    "/sbin/", "/sys/", "/usr/", "/var/run/",
                    "/var/lock/", "/var/spool/", "/var/cache/")
# ...and a folder of its own under /var/log is a place for one (the operator,
# 23 Oct), though /var/log itself is not. Held equal on both sides by
# unit/test_store_paths.py.


# Where the configuration plane's tools are (docs/nodes.md §12, phase 5).
# bb-sandbox is the one copy of the mount logic, installed by the provisioner:
# its presence is what says this node was set up as a sandbox, and a
# `system` job is refused without it. The netplan seams exist so the tests
# can stand in for both without a root shell.
SANDBOX_BIN = os.environ.get("BUILDERBOT_SANDBOX_BIN", names.sandbox_bin())
# Where the agent's own unit is kept through a restart it did not ask for
# (B538): a systemd drop-in, and needrestart's configuration directory.
UNIT_DROPIN = f"/etc/systemd/system/{names.unit()}.service.d/builderbot.conf"
NEEDRESTART_DIR = "/etc/needrestart"
# What the GPU display's unit last said (bb-sandbox gpu-display, R20): one
# line, read into the census so the row says it.
GPU_DISPLAY_STATE = os.environ.get("BUILDERBOT_GPU_DISPLAY_STATE", "/run/builderbot-gpu-display")
# The machine's sysfs, where the card and its driver are read from. The
# suite's is a tree of its own with a card in it, so what it checks does
# not depend on the box it runs on; lspci is not asked then.
SYS_ROOT = os.environ.get("BUILDERBOT_SYS_ROOT", "/sys")
# The NVIDIA driver's name in a toolchain job: alone, or with the package
# apt is to install after a colon (nvidia-driver:nvidia-driver-610-open).
DRIVER = "nvidia-driver"
# ...and the container toolkit, the second of the machine's own rows there.
TOOLKIT = "nvidia-container-toolkit"
# The session's view (R35): the root helper that builds it, the file that
# tells it this machine's layout, and the sudo rule that is the session
# account's only way to it. Installed and kept by this agent from the bundle,
# on a node set up as a sandbox; the seams are for the suite.
SESSION_BIN = os.environ.get("BUILDERBOT_SESSION_BIN", "/usr/local/sbin/bb-session")
# Where root keeps its own copy of the two tools it installs from a bundle
# (bb-sandbox out of the provisioner, and bb-session): root-owned, 0700,
# written from the tar as it is unpacked and never from the toolchain store,
# which belongs to the job account. Reading them from the store let any job,
# and so any session through aerie run, plant root code that landed on the
# next hello (the review of 26 Sep).
TOOLS_DIR = os.environ.get("BUILDERBOT_TOOLS_DIR", VAR + "/agent/tools")
# The bundle a terminal runs where accounts are their own users (R125): a
# root-owned copy on the node's own disk, unpacked from the checked tar, so
# nothing outside a view can change what every account's terminal runs (the
# toolchain store is a share squashed to one uid).
ROOT_BUNDLE_DIR = os.environ.get("BUILDERBOT_ROOT_BUNDLE", "/usr/local/lib/builderbot/bundle")
# Where a signing job works with a key (B315): this machine's own memory,
# never a store. A data store may be a share squashed to one uid, the session
# account's on the documented one, and a key written there was a session's to
# read while the job ran. Root's, 0711, each job's folder its account's, 0700.
SIGN_WORK = os.environ.get("BUILDERBOT_SIGN_WORK", "/run/builderbot/sign")
ROOT_TOOLS = ("nodes/provision-linux.sh", "nodes/bb-session", "nodes/bb-netcut")
# Where an updated Claude Code is pinned, root-owned, for the sessions (claude_update).
CLAUDE_DIR = "/usr/local/lib/builderbot/claude"
# ...and the other coding agents (R95 step 2), each in a folder of its own
# under this one: AGENTS_DIR/codex/codex, AGENTS_DIR/copilot/copilot.
AGENTS_DIR = os.environ.get("BUILDERBOT_AGENTS_DIR", "/usr/local/lib/builderbot/agents")
# How each is installed, by the job the controller's agent table names for
# it (scripts/dashboard/agents.py update_job). Which agent is a lookup
# here; how is the recipe the controller hands over with the job (its
# table's, or its signed catalog's where that is newer: R169 step 13), held
# to one shape by recipe_checked below, and these rows' own for a
# controller that sends none. Each vendor's own installer, run as the
# session account into its home: `script` fetched fresh each time, the
# version asked for in `pin` (formatted with the version), `env` formatted
# with the home, and the binary it leaves at `bin` under the home. A test
# stands its own script in with BUILDERBOT_<ID>_INSTALLER. Checked against
# Codex CLI 0.163.0 and Copilot CLI 1.0.102 (22 Oct).
# Each coding agent's sign-in and sign-out jobs, by the controller's agent
# table (agents.py login_job, logout_job), to the agent `aerie login --flow` and
# `aerie login --out` are run for. Claude's are the claude-login and
# claude-logout of old, which name no agent.
# How each shipped agent's sign-in is kept and whom it names, as the
# controller's table says it (agents.py signin.flow: kept, who), copied
# rather than imported since the agent carries no dashboard module;
# unit/test_shipped_signin.py holds the two to each other. A pack's agent's
# comes from its manifest the same way (pack_signins below), so the seal,
# the watch and a seal's header read every agent's from data (R234 step 6).
SIGNINS = {
    "claude": {"kept": ".claude/.credentials.json", "provider": "Anthropic",
               "who": {"file": ".claude.json", "email": ["oauthAccount", "emailAddress"]}},
    "codex": {"kept": ".codex/auth.json", "provider": "OpenAI",
              "who": {"email": ["tokens", "id_token", "email"],
                      "plan": ["tokens", "id_token", "https://api.openai.com/auth", "chatgpt_plan_type"],
                      "key": ["OPENAI_API_KEY"], "key_named": "an OpenAI API key"}},
    "grok": {"kept": ".grok/auth.json", "provider": "xAI", "who": {"named": "an xAI account"}},
    "copilot": {"kept": ".copilot/config.json", "provider": "GitHub", "who": {"email": ["lastLoggedInUser", "login"]}},
}
AGENT_LOGINS = {"codex-login": "codex", "copilot-login": "copilot", "grok-login": "grok"}
AGENT_LOGOUTS = {"codex-logout": "codex", "copilot-logout": "copilot", "grok-logout": "grok"}
AGENT_INSTALLS = {
    "codex-update": {"id": "codex", "command": "codex", "product": "Codex CLI", "reported": "codex",
                     "script": "curl -fsSL https://chatgpt.com/codex/install.sh | sh",
                     "pin": ("CODEX_RELEASE", "{v}"), "env": {"CODEX_INSTALL_DIR": "{home}/.local/bin"},
                     "bin": ".local/bin/codex"},
    "copilot-update": {"id": "copilot", "command": "copilot", "product": "Copilot CLI", "reported": "copilot",
                       "script": "curl -fsSL https://gh.io/copilot-install | bash",
                       "pin": ("VERSION", "v{v}"), "env": {"PREFIX": "{home}/.local"},
                       "bin": ".local/bin/copilot"},
    # Grok Build's installer takes the version as its argument, not from its
    # environment: handed over through BB_PIN, empty for the newest. It does
    # not check its download against anything published (25 Oct).
    "grok-update": {"id": "grok", "command": "grok", "product": "Grok Build", "reported": "grok",
                    "script": 'curl -fsSL https://x.ai/cli/install.sh | bash -s -- ${BB_PIN:-}',
                    "pin": ("BB_PIN", "{v}"), "env": {"GROK_BIN_DIR": "{home}/.local/bin"},
                    "bin": ".local/bin/grok"},
    # OpenCode (R144 step 2), the open agent any model runs through: its
    # install script takes the version as VERSION and puts the program in
    # ~/.opencode/bin, whatever it is told (read off the script on 11 Nov:
    # it took OPENCODE_INSTALL_DIR on 28 Oct and no longer does, so an
    # update installed and then found nothing at ~/.local/bin). Asked not to
    # write the account's shell files: a session runs the pinned copy. The
    # old place is still taken away with it on a removal.
    "opencode-update": {"id": "open", "command": "opencode", "product": "OpenCode", "reported": "opencode",
                        "script": "curl -fsSL https://opencode.ai/install | bash -s -- --no-modify-path",
                        "pin": ("VERSION", "{v}"), "env": {},
                        "bin": ".opencode/bin/opencode", "also": (".local/bin/opencode",)},
}
# Claude Code's row in the same shape, for the claude-update job: kept out of
# AGENT_INSTALLS, which the census and the session PATH read for the agents
# beside Claude. Its copy is pinned in CLAUDE_DIR, its installer is handed no
# version (the one asked for is read from the versions folder it leaves),
# and a removal takes that folder too.
CLAUDE_INSTALL = {"id": "claude", "command": "claude", "product": "Claude Code", "reported": "claude",
                  "script": "curl -fsSL https://claude.ai/install.sh | bash",
                  "pin": None, "env": {}, "bin": ".local/bin/claude", "pin_dir": CLAUDE_DIR,
                  "fresh": ".local/share/claude/versions/{v}", "also": (".local/share/claude",)}
# The recipe the controller hands over with an install, an update or a
# removal (its agent table's `install`, or its catalog's where that is
# newer): what a row here says of the installer, in its place. The rows
# above are what runs when a controller from before this sends none. Held to
# the shape the controller holds a manifest's to (agents.py install_checked):
# one installer over https piped to sh or bash with plain arguments, an
# environment that names neither PATH nor the account, and paths of two or
# more parts under the account's home.
_RECIPE_SCRIPT = re.compile(r"curl -fsSL https://[A-Za-z0-9._~/@+%-]{3,200} \| (?:ba)?sh(?: -s --(?: [A-Za-z0-9_${}:=.,/-]{1,60}){1,6})?")
_RECIPE_NAME = re.compile(r"[A-Z][A-Z0-9_]{1,40}")
_RECIPE_VALUE = re.compile(r"[A-Za-z0-9._/{}:=-]{0,200}")
_RECIPE_PATH = re.compile(r"\.?[A-Za-z0-9_-]{1,40}(/[A-Za-z0-9._{}-]{1,60}){1,5}")
_RECIPE_ENV_KEPT = ("PATH", "HOME", "USER", "LOGNAME", "SHELL", "IFS", "ENV", "BASH_ENV")


def _recipe_path(v, braces=""):
    if not (isinstance(v, str) and _RECIPE_PATH.fullmatch(v)) or ".." in v.split("/"):
        return False
    rest = v.replace(braces, "") if braces else v
    return "{" not in rest and "}" not in rest


def _recipe_name(k):
    return isinstance(k, str) and bool(_RECIPE_NAME.fullmatch(k)) and k not in _RECIPE_ENV_KEPT and not k.startswith("LD_")


def recipe_checked(r):
    """(recipe, why): an install recipe as agent_install reads it (script,
    pin, env, bin, also, fresh, rev), or why what was sent is not one."""
    if not isinstance(r, dict):
        return None, "it is not an object"
    script = r.get("script")
    if not (isinstance(script, str) and len(script) <= 400 and _RECIPE_SCRIPT.fullmatch(script)):
        return None, "its script is not one installer over https handed to a shell"
    pin = r.get("pin")
    if pin is not None and not (isinstance(pin, (list, tuple)) and len(pin) == 2 and _recipe_name(pin[0]) and isinstance(pin[1], str)
                                and re.fullmatch(r"[A-Za-z0-9._-]{0,12}\{v\}[A-Za-z0-9._-]{0,12}", pin[1])):
        return None, "its pin is not a variable and how a version is written"
    env = r.get("env") or {}
    if not (isinstance(env, dict) and len(env) <= 8 and all(
            _recipe_name(k) and isinstance(v, str) and _RECIPE_VALUE.fullmatch(v) and ".." not in v
            and "{" not in v.replace("{home}", "") and "}" not in v.replace("{home}", "") for k, v in env.items())):
        return None, "its env names something an installer is not handed"
    if not _recipe_path(r.get("bin")):
        return None, "its bin is not a path under the account's home"
    also = r.get("also") or []
    if not (isinstance(also, (list, tuple)) and len(also) <= 6 and all(_recipe_path(x) for x in also)):
        return None, "its also is not paths under the account's home"
    fresh = r.get("fresh") or ""
    if fresh and not (_recipe_path(fresh, "{v}") and "{v}" in fresh):
        return None, "its fresh is not a versions folder under the account's home"
    rev = r.get("rev")
    return {"script": script, "pin": tuple(pin) if pin is not None else None, "env": dict(env), "bin": r["bin"],
            "also": tuple(also), "fresh": fresh,
            "rev": rev if isinstance(rev, int) and not isinstance(rev, bool) else 0}, ""


SESSION_CONF = os.environ.get("BUILDERBOT_SESSION_CONF", "/etc/bb-session.conf")
SESSION_SUDOERS = os.environ.get("BUILDERBOT_SESSION_SUDOERS", "/etc/sudoers.d/builderbot-session")
# The root helper that cuts the network for a declared pack's install steps
# where the job account cannot make a network namespace itself (R234), and
# the one sudo rule that lets that account run it.
NETCUT_BIN = os.environ.get("BUILDERBOT_NETCUT_BIN", "/usr/local/sbin/bb-netcut")
NETCUT_SUDOERS = os.environ.get("BUILDERBOT_NETCUT_SUDOERS", "/etc/sudoers.d/builderbot-netcut")
# The wall the installer writes on a controller's own machine (docs/decisions.md),
# and where the root agent keeps that machine's compose files: under /var/lib
# and root's alone, since the job account owns the data store and could swap
# anything kept under it between the write and the run.
SESSION_WALL = os.environ.get("BUILDERBOT_SESSION_WALL", "/etc/bb-session.wall")
OWN_COMPOSE = os.environ.get("BUILDERBOT_OWN_COMPOSE", "/var/lib/aerieos-docker/compose")


def root_docker_env():
    """The environment docker runs with when the root agent runs it: the
    system's programs alone. A job's PATH leads into the toolchain store,
    which the job account writes, and a docker found there would run as root."""
    return {"PATH": "/usr/local/sbin:/usr/local/bin:/usr/sbin:/usr/bin:/sbin:/bin", "LANG": "C.UTF-8",
            "HOME": "/root", "USER": "root", "LOGNAME": "root"}


# Each session kept to its own project's network (R79): the folder this agent
# shares with bb-session (its resolver file for sessions, its mark that the
# table is in place, and a file per session saying which project an address
# is), the table it keeps, the range sessions are addressed from, and the mark
# the table puts on what it let through, which is all Docker's forwarding is
# told to let past: a table that is gone lets nothing through, not everything.
SESSNET_DIR = os.environ.get("BUILDERBOT_SESSNET_DIR", "/run/bb-session-net")
SESSNET_TABLE = "builderbot_sessnet"
SESSNET_CIDR = "10.231.0.0/16"
SESSNET_MARK = 0x10000000
IPTABLES_BIN = os.environ.get("BUILDERBOT_IPTABLES_BIN", "iptables")
DOCKER_BIN = os.environ.get("BUILDERBOT_DOCKER_BIN", "docker")
RESOLV_UPSTREAM = ("/run/systemd/resolve/resolv.conf", "/etc/resolv.conf")
# What is not the internet: every private, shared, loopback, link-local and
# multicast range. A session reaches none of it but what the sets name.
SESSNET_LOCAL = ("0.0.0.0/8", "10.0.0.0/8", "100.64.0.0/10", "127.0.0.0/8", "169.254.0.0/16",
                 "172.16.0.0/12", "192.168.0.0/16", "198.18.0.0/15", "224.0.0.0/3")
# Where the node's synced copy of its projects is (R162), which is what a
# session works in. The seam is for the suite: it runs its agent as a session account, and inside a
# session's view /workspace is the view's own read-only root.
SHARE = os.environ.get("BUILDERBOT_SHARE", "/workspace")
# The live coding agents (R95), each its id, its command and its session's
# prefix at once: the live rows of the controller's agent table
# (scripts/dashboard/agents.py), copied rather than imported since the agent
# carries no dashboard module; unit/test_agents.py holds the two to each
# other. The session prefixes, the launchers a respawn may run and the
# process kinds a busy machine is read by are all made from it.
AGENT_IDS = ("claude", "codex", "copilot", "grok", "open")
# The pane a respawn may run again: bb-tty's launcher of a coding agent
# (claude-run.sh, codex-run.sh, copilot-run.sh, grok-run.sh; a second slot's
# claude-2-run.sh, R143), in the project's cache
# folder and started inside the project's view when the node builds one.
_PATHCH = r"[A-Za-z0-9._/@+-]"
RESPAWNABLE = (rf"(?:sudo -n {re.escape(SESSION_BIN)} enter(?: --[a-z]+ {_PATHCH}+)* -- )?"
               rf"{_PATHCH}*/builderbot/(?:u/u_[0-9a-f]{{8}}/)?"
               rf"project/[A-Za-z0-9._-]+/(?:{'|'.join(AGENT_IDS)})(?:-[2-9])?-run\.sh")
NETPLAN_DIR = os.environ.get("BUILDERBOT_NETPLAN_DIR", "/etc/netplan")
NETPLAN_BIN = os.environ.get("BUILDERBOT_NETPLAN_BIN", "netplan")
NETPLAN_FILE = "90-builderbot.yaml"
# How long a network change has to dial back in before it is reverted.
DIAL_BACK_S = 180
# The Actions runner as a per-node service (docs/nodes.md §14, phase 7):
# where it lives, and, for the tests, a tarball to unpack instead of the
# GitHub release download.
RUNNER_DIR = os.environ.get("BUILDERBOT_RUNNER_DIR", VAR + "/runner")
# The machine's package manager, for a recipe's `system` packages. Seams for
# the suite, which must not touch the box it runs on.
APT_BIN = os.environ.get("BUILDERBOT_APT_BIN", "apt-get")
# Seconds per "minute" of the idle rule; the suite sets 1.
IDLE_UNIT = float(os.environ.get("BUILDERBOT_IDLE_UNIT", "60"))
# The session names a coding agent runs under (claude-<project>).
AGENT_PREFIXES = tuple(f"{a}-" for a in AGENT_IDS)
_pack_ids = {"stamp": None, "ids": ()}


def pack_agent_ids():
    """The coding agents vetted packs bring (R169 step 10), by the rows of
    the root bundle's config/toolpacks.json that carry an adapter: read
    again only when the file changes. Never a shipped agent's id."""
    path = os.path.join(ROOT_BUNDLE_DIR, "current", "config", "toolpacks.json")
    try:
        st = os.stat(path)
        stamp = (st.st_mtime_ns, st.st_size)
    except OSError:
        return ()
    if stamp != _pack_ids["stamp"]:
        ids = ()
        try:
            with open(path, encoding="utf-8") as f:
                rows = json.load(f).get("toolchains") or []
            ids = tuple(sorted(r["name"] for r in rows if isinstance(r, dict) and isinstance(r.get("agent"), dict)
                               and re.fullmatch(r"[a-z][a-z0-9]{1,15}", str(r.get("name") or "")) and r["name"] not in AGENT_IDS))
        except (OSError, ValueError, AttributeError, TypeError):
            pass
        _pack_ids.update(stamp=stamp, ids=ids)
    return _pack_ids["ids"]


_pack_kept = {"stamp": None, "rows": {}}


def _who(w):
    """A flow's `who` as this agent reads it, or None: the keys to follow
    are plain words, the file a plain path under the home (the controller
    holds a manifest's to the same, toolpacks._flow_who)."""
    if not isinstance(w, dict):
        return None
    out = {}
    f = w.get("file")
    if isinstance(f, str) and re.fullmatch(r"[A-Za-z0-9._/-]{1,200}", f) and not f.startswith("/") and not any(p in ("", ".", "..") for p in f.split("/")):
        out["file"] = f
    for k in ("email", "plan", "key"):
        v = w.get(k)
        if isinstance(v, list) and 1 <= len(v) <= 6 and all(isinstance(x, str) and re.fullmatch(r"[A-Za-z0-9_][A-Za-z0-9_.:/@-]{0,79}", x) for x in v):
            out[k] = list(v)
    for k in ("named", "key_named"):
        v = w.get(k)
        if isinstance(v, str) and re.fullmatch(r"[A-Za-z0-9][A-Za-z0-9 .,:;'()/&-]{1,79}", v):
            out[k] = v
    return out or None


def pack_signins(bundle=""):
    """{agent: {"kept": file under the home, "provider": whose account}} for
    the packs' coding agents whose pack describes a sign-in's flow (R233
    step 6): the file each keeps its sign-in in, which is sealed and watched
    as a shipped agent's is. From the root bundle's config/toolpacks.json
    (or the bundle named, for a job that runs from one on the store), read
    again only when the file changes; a path that is not a plain one under
    the home is no row."""
    path = os.path.join(bundle or os.path.join(ROOT_BUNDLE_DIR, "current"), "config", "toolpacks.json")
    try:
        st = os.stat(path)
        stamp = (path, st.st_mtime_ns, st.st_size)
    except OSError:
        return {}
    if stamp != _pack_kept["stamp"]:
        got = {}
        try:
            with open(path, encoding="utf-8") as f:
                rows = json.load(f).get("toolchains") or []
            for r in rows if isinstance(rows, list) else []:
                a = r.get("agent") if isinstance(r, dict) else None
                name = str(r.get("name") or "") if isinstance(r, dict) else ""
                flow = ((a.get("signin") or {}).get("flow") or {}) if isinstance(a, dict) and isinstance(a.get("signin"), dict) else {}
                kept = flow.get("kept") if isinstance(flow, dict) else None
                if not (re.fullmatch(r"[a-z][a-z0-9]{1,15}", name) and name not in AGENT_IDS and isinstance(kept, str)
                        and re.fullmatch(r"[A-Za-z0-9._/-]{1,200}", kept) and not kept.startswith("/")
                        and not any(p in ("", ".", "..") for p in kept.split("/"))):
                    continue
                got[name] = {"kept": kept, "provider": str(a.get("provider") or "")[:60]}
                who = _who(flow.get("who"))
                if who:
                    got[name]["who"] = who
        except (OSError, ValueError, AttributeError, TypeError):
            got = {}
        _pack_kept.update(stamp=stamp, rows=got)
    return dict(_pack_kept["rows"])


def agent_prefixes():
    """Every coding agent's session prefix, the shipped and the packs'."""
    return AGENT_PREFIXES + tuple(f"{a}-" for a in pack_agent_ids())


def respawnable(cmd):
    """Whether a pane's start command is a coding agent's launcher bb-tty
    wrote, the shipped agents' or a pack's (R169 step 10)."""
    if re.fullmatch(RESPAWNABLE, cmd):
        return True
    ids = pack_agent_ids()
    return bool(ids) and bool(re.fullmatch(RESPAWNABLE.replace("|".join(AGENT_IDS), "|".join(AGENT_IDS + ids)), cmd))


def harden():
    """What this process does about the keys it holds (R158 step 6): the
    boot secret a terminal's seal keys travel under and every opened
    sign-in pass through here. Core dumps off and the process not dumpable
    (so a process of the same user cannot read it through ptrace or
    /proc/PID/mem either), its pages kept from swap where the memlock limit
    allows (the unit sets it), and what held a key zeroed (wipe) once it is
    let go. Never fails the agent: what it could not do is logged once."""
    out = {"core": False, "dumpable": False, "mlock": False}
    try:
        import resource
        resource.setrlimit(resource.RLIMIT_CORE, (0, 0))
        out["core"] = True
    except (ImportError, ValueError, OSError):
        pass
    try:
        import ctypes
        import ctypes.util
        import resource
        libc = ctypes.CDLL(ctypes.util.find_library("c") or "libc.so.6", use_errno=True)
        out["dumpable"] = libc.prctl(4, 0, 0, 0, 0) == 0
        # Only with no memlock limit (the unit lifts it): under one,
        # MCL_FUTURE makes every allocation past the limit fail.
        if resource.getrlimit(resource.RLIMIT_MEMLOCK)[0] == resource.RLIM_INFINITY:
            out["mlock"] = libc.mlockall(2 | 4) == 0 or libc.mlockall(2) == 0
    except (OSError, AttributeError, ImportError, ValueError):
        pass
    missed = [k for k, v in out.items() if not v]
    if missed:
        log("hardening: could not " + ", ".join({"core": "turn core dumps off", "dumpable": "make the process undumpable",
                                                 "mlock": "lock memory from swap (the memlock limit)"}[k] for k in missed))
    return out


def wipe(b):
    """A bytes or bytearray value overwritten with zeros in place, for a key
    or an opened sign-in let go (R158 step 6); CPython's layout alone."""
    if isinstance(b, bytearray):
        for i in range(len(b)):
            b[i] = 0
        return True
    if isinstance(b, bytes) and b and sys.implementation.name == "cpython":
        try:
            import ctypes
            ctypes.memset(id(b) + bytes.__basicsize__ - 1, 0, len(b))
            return True
        except (ValueError, OSError):
            return False
    return False


def has_systemd():
    """Whether the runner can be a service here. A VM has systemd; a
    container (this image in the node role) and a guest machine without it
    run the runner in the foreground under the agent instead. The suite
    pins the answer with BUILDERBOT_SYSTEMD so both paths are exercised
    whichever box runs it."""
    pin = os.environ.get("BUILDERBOT_SYSTEMD", "")
    if pin in ("0", "1"):
        return pin == "1"
    return os.path.isdir("/run/systemd/system")
DPKG_BIN = os.environ.get("BUILDERBOT_DPKG_BIN", "dpkg")
# ...and the RHEL family's pair, for a node provisioned on Rocky (nodes/provision-linux.sh
# takes either): a recipe names its packages per family under `system.apt`
# and `system.dnf`, and the agent uses the list for the manager it has.
DNF_BIN = os.environ.get("BUILDERBOT_DNF_BIN", "dnf")
RPM_BIN = os.environ.get("BUILDERBOT_RPM_BIN", "rpm")
# NetworkManager's CLI, the network backend where there is no netplan (the
# RHEL family). Settable for the same reason as netplan's: the suite stubs it.
NMCLI_BIN = os.environ.get("BUILDERBOT_NMCLI_BIN", "nmcli")
# The other package managers and network backends this agent can drive:
# one pair per family, detected on the machine, never told by the
# controller. Each settable so the suite can point one at a stub or at a
# path that does not exist.
PACMAN_BIN = os.environ.get("BUILDERBOT_PACMAN_BIN", "pacman")
ZYPPER_BIN = os.environ.get("BUILDERBOT_ZYPPER_BIN", "zypper")
APK_BIN = os.environ.get("BUILDERBOT_APK_BIN", "apk")
XBPS_QUERY_BIN = os.environ.get("BUILDERBOT_XBPS_QUERY_BIN", "xbps-query")
# What apt's repositories carry, as opposed to what dpkg has installed: asked
# only to pick among a recipe's alternatives ("libasound2t64|libasound2").
APT_CACHE_BIN = os.environ.get("BUILDERBOT_APT_CACHE_BIN", "apt-cache")
XBPS_INSTALL_BIN = os.environ.get("BUILDERBOT_XBPS_INSTALL_BIN", "xbps-install")
EMERGE_BIN = os.environ.get("BUILDERBOT_EMERGE_BIN", "emerge")
BREW_BIN = os.environ.get("BUILDERBOT_BREW_BIN", "brew")
# The session ports' firewall rule the provisioner wrote, which names the
# controller's address: the agent keeps it true when that address moves.
NFT_BIN = os.environ.get("BUILDERBOT_NFT_BIN", "nft")
FIREWALL_CMD = os.environ.get("BUILDERBOT_FIREWALL_CMD", "firewall-cmd")
SESSION_NFT = os.environ.get("BUILDERBOT_SESSION_NFT", ETC + "/session-ports.nft")
FIREWALL_EVERY_S = 60
NETWORKD_DIR = os.environ.get("BUILDERBOT_NETWORKD_DIR", "/etc/systemd/network")
NETWORKCTL_BIN = os.environ.get("BUILDERBOT_NETWORKCTL_BIN", "networkctl")
INTERFACES_FILE = os.environ.get("BUILDERBOT_INTERFACES_FILE", "/etc/network/interfaces")
IFUP_BIN = os.environ.get("BUILDERBOT_IFUP_BIN", "ifup")
IFDOWN_BIN = os.environ.get("BUILDERBOT_IFDOWN_BIN", "ifdown")
WICKED_BIN = os.environ.get("BUILDERBOT_WICKED_BIN", "wicked")
SYSCONFIG_NET_DIR = os.environ.get("BUILDERBOT_SYSCONFIG_NET_DIR", "/etc/sysconfig/network")
DHCPCD_CONF = os.environ.get("BUILDERBOT_DHCPCD_CONF", "/etc/dhcpcd.conf")
OS_RELEASE = os.environ.get("BUILDERBOT_OS_RELEASE", "/etc/os-release")
RUNNER_TARBALL = os.environ.get("BUILDERBOT_RUNNER_TARBALL", "")
RUNNER_RELEASES = "https://api.github.com/repos/actions/runner/releases/latest"
# Gitea's runner: one static binary, fetched from gitea.com's releases, or a
# prebuilt one named here for the suite.
ACT_RUNNER_BIN = os.environ.get("BUILDERBOT_ACT_RUNNER_BIN", "")
# gitea/act_runner became gitea/runner upstream (the old address answers
# 301, the assets are gitea-runner-<ver>-<os>-<arch>); the binary keeps the
# act_runner command set, and keeps its name here.
ACT_RUNNER_RELEASES = "https://gitea.com/api/v1/repos/gitea/runner/releases/latest"


# Tailscale, for Funnel (docs/nodes.md §7, phase 8): a seam so the tests can
# stand in for it, like the rest of the tools the agent drives.
TAILSCALE_BIN = os.environ.get("BUILDERBOT_TAILSCALE_BIN", "tailscale")


def log(msg):
    # journald stamps its own time; a bare line reads best in `journalctl -u`.
    print(f"[builderbot-agent] {msg}", file=sys.stderr, flush=True)


_said = {}


def log_once(key, msg, every=3600):
    """log(), but the same `msg` under `key` at most once per `every`
    seconds, with how many times it came up meanwhile. For a loop that
    meets the same fault on every tick: a sync step failing every five
    seconds was 17,000 identical journal lines a day (the operator, 12 Oct)."""
    now = time.monotonic()
    last, n, was = _said.get(key, (-1e9, 0, None))
    if msg == was and now - last < every:
        _said[key] = (last, n + 1, was)
        return
    log(msg + (f" (and {n} more times since)" if n and msg == was else ""))
    _said[key] = (now, 0, msg)


def hello_again(agent, why):
    """Ask the agent for a fresh hello with its reason in the journal
    (Agent.hello_again); a stand-in driven in a test has only the clock."""
    fn = getattr(agent, "hello_again", None)
    if fn:
        fn(why)
    else:
        agent.hello_at = 0


# The files a node writes itself, each kept to this and one earlier
# generation (cap_file): the terminal server's and the runners' were
# appended to for the life of the machine.
NODE_LOG_MAX = 16 * 1024 * 1024
RUNNER_DIAG_KEEP = 20       # newest files in a runner's _diag


def cap_file(path, limit=NODE_LOG_MAX):
    """Copy-truncate `path` into `path`.1 once it passes `limit`: the
    writers hold it open with O_APPEND, so they go on at the new end. True
    when it was cut."""
    try:
        if os.path.getsize(path) <= limit:
            return False
        shutil.copyfile(path, path + ".1")
        with open(path, "r+b") as f:
            f.truncate(0)
        return True
    except OSError:
        return False


def prune_dir(d, keep):
    """The newest `keep` files directly in `d`, the rest removed. How many."""
    try:
        files = sorted((e for e in os.scandir(d) if e.is_file()), key=lambda e: e.stat().st_mtime, reverse=True)
    except OSError:
        return 0
    gone = 0
    for e in files[keep:]:
        with contextlib.suppress(OSError):
            os.unlink(e.path)
            gone += 1
    return gone


# Docker's json-file logs on a node, per container: three files of 20 MB.
CONTAINER_LOG_OPTS = {"max-size": "20m", "max-file": "3"}

# The bridge driver's option for a network's default bind address.
HOST_BINDING = "com.docker.network.bridge.host_binding_ipv4"


def daemon_json_with_ip(text, on):
    """/etc/docker/daemon.json as it should read with published ports bound
    to 127.0.0.1 by default (`ip`, docker's own default bind address) or not
    (R190): the file's other keys kept, a file that is not JSON left alone.
    Returns the new text, or None when nothing has to change."""
    try:
        d = json.loads(text) if text.strip() else {}
    except ValueError:
        return None
    if not isinstance(d, dict):
        return None
    # Two keys: `ip` is the default bridge's, and every network compose makes
    # is a user-defined one, which takes its bind address from
    # default-network-opts instead (a hosting node, 11 Oct: with `ip` alone,
    # aquilaeLabs's 8380 and 8381 answered from the internet).
    want = "127.0.0.1" if on else None
    before = json.dumps(d, sort_keys=True)
    opts = d.get("default-network-opts") if isinstance(d.get("default-network-opts"), dict) else {}
    br = opts.get("bridge") if isinstance(opts.get("bridge"), dict) else {}
    if want is None:
        d.pop("ip", None)
        br.pop(HOST_BINDING, None)
    else:
        d["ip"] = want
        br[HOST_BINDING] = want
    if br:
        opts["bridge"] = br
    else:
        opts.pop("bridge", None)
    if opts:
        d["default-network-opts"] = opts
    else:
        d.pop("default-network-opts", None)
    # ...and every container's log bounded (the operator, 12 Oct): the
    # json-file driver keeps all of it by default, so a chatty container
    # filled the disk under /var/lib/docker. Only where nobody chose a
    # driver or its options: a node's own logging arrangement is kept.
    if d.get("log-driver", "json-file") == "json-file" and "log-opts" not in d:
        d["log-opts"] = dict(CONTAINER_LOG_OPTS)
    if json.dumps(d, sort_keys=True) == before:
        return None
    return json.dumps(d, indent=2) + "\n"


def own_path():
    """The file a node runs and a self-update writes over: the zip the
    controller shipped (this package inside it), or from a checkout the
    entry beside the package (bundle.py)."""
    outer = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
    return outer if os.path.isfile(outer) else os.path.join(outer, "builderbot-agent.py")


def own_digest():
    """The digest of what this process runs, as the controller names its own:
    the zip's bytes, or from a checkout the zip its sources make."""
    outer = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
    try:
        if os.path.isfile(outer):
            with open(outer, "rb") as f:
                body = f.read()
        else:
            from .bundle import build
            body = build(outer)
        return "sha256:" + hashlib.sha256(body).hexdigest()
    except OSError:
        return ""


# -- file work as the account whose folder it is ---------------------------------
#
# This agent is root, and much of what it writes and reads is inside folders
# an account owns: a job account's workspace and store, a space's tree, an
# account's home. Root opening a path there follows whatever the account put
# at that path, so a link planted where root was about to write, chmod or
# upload turned root's reach into the account's (the audit of 13 Nov). Inside
# acting_as(), this thread's file identity is the account's: the kernel
# checks every path it touches as that account, with none of root's file
# capabilities and none of its groups, so a planted link leads nowhere the
# account could not have gone itself. Files made there are the account's
# without a chown. Linux keeps this per thread (setfsuid, setfsgid and the
# groups of the calling thread), so the agent's other threads stay root. Two
# things started inside it are not what they look like: a child process is
# root again (an exec makes it whoever the process is), which is what
# Popen's user and group are for; and a new THREAD is the account for good
# (a thread is whoever started it), so none is started inside.
_FSLIBC = None
_ACTING = threading.local()
# setgroups, as the kernel takes it for the calling thread alone: libc's own
# applies to every thread. By machine; one not listed keeps root's groups
# inside acting_as, said once.
_SYS_SETGROUPS = {"x86_64": 116, "aarch64": 159, "riscv64": 159, "loongarch64": 159,
                  "armv7l": 206, "armv6l": 206, "i686": 206, "i386": 206, "ppc64le": 81, "s390x": 206}
_NOBODY = 0xFFFFFFFF


def _fs_libc():
    global _FSLIBC
    if _FSLIBC is None:
        import ctypes
        try:
            lib = ctypes.CDLL(None, use_errno=True)
            lib.setfsuid, lib.setfsgid       # noqa: B018 (Linux alone has them: an AttributeError elsewhere)
            _FSLIBC = lib
        except (OSError, AttributeError):
            _FSLIBC = False
    return _FSLIBC


def _fs_groups(lib, groups):
    """This thread's supplementary groups set to `groups`; False where this
    machine's call for it is not known."""
    import ctypes
    import platform
    nr = _SYS_SETGROUPS.get(platform.machine())
    if nr is None:
        return False
    arr = (ctypes.c_uint * max(1, len(groups)))(*groups)
    return lib.syscall(ctypes.c_long(nr), ctypes.c_size_t(len(groups)), arr) == 0


def _fs_become(lib, uid, gid, groups):
    """This thread's file identity made (uid, gid, groups), and seen to be."""
    import ctypes
    if uid == 0:
        # Back to root: the identity first, so the groups may be set again.
        lib.setfsuid(ctypes.c_uint(0))
        lib.setfsgid(ctypes.c_uint(0))
        _fs_groups(lib, groups)
    else:
        if not _fs_groups(lib, groups):
            log_once("fs-groups", "this machine's per-thread setgroups is not known: file work in an account's "
                                  "folder keeps root's groups (its file identity is still the account's)")
        lib.setfsgid(ctypes.c_uint(gid))
        lib.setfsuid(ctypes.c_uint(uid))
    return lib.setfsuid(ctypes.c_uint(_NOBODY)) == uid and lib.setfsgid(ctypes.c_uint(_NOBODY)) == gid


def _ids(who):
    """(uid, gid) of an account given as that pair or as Popen's keywords
    (drop_privileges), or None for nobody to act as."""
    if not who:
        return None
    if isinstance(who, dict):
        uid, gid = who.get("user"), who.get("group")
    else:
        uid, gid = who
    if not isinstance(uid, int) or not isinstance(gid, int) or uid <= 0:
        return None
    return uid, gid


@contextlib.contextmanager
def acting_as(who):
    """File work in this thread done as the account `who`, a (uid, gid) or
    drop_privileges' keywords; as it already is where this process is not
    root, there is nobody to act as, or the machine is not Linux. Nests:
    as_root() inside it is root again for a file of the agent's own."""
    ids = _ids(who)
    lib = _fs_libc() if hasattr(os, "geteuid") and os.geteuid() == 0 and ids else None
    if not lib:
        yield
        return
    was = getattr(_ACTING, "now", (0, 0))
    groups = os.getgroups() if was[0] == 0 else getattr(_ACTING, "groups", [])
    if was[0] == 0:
        _ACTING.groups = groups
    if not _fs_become(lib, ids[0], ids[1], []):
        _fs_become(lib, was[0], was[1], [] if was[0] else groups)
        raise OSError(f"could not take the file identity of uid {ids[0]} for work in its folder")
    _ACTING.now = ids
    try:
        yield
    finally:
        back = _fs_become(lib, was[0], was[1], [] if was[0] else groups)
        _ACTING.now = was
        if not back:
            # A thread left as the account would do root's work as it from
            # here on, and fail in ways nobody could read: start again.
            log("could not take this thread's own file identity back after work in an account's folder: stopping")
            os._exit(70)


@contextlib.contextmanager
def as_root():
    """Root's own file identity again, inside acting_as(): for a file of the
    agent's own (a record, a download kept where only root writes) in the
    middle of work in an account's folder."""
    was = getattr(_ACTING, "now", (0, 0))
    lib = _fs_libc() if was[0] != 0 else None
    if not lib:
        yield
        return
    groups = getattr(_ACTING, "groups", [])
    if not _fs_become(lib, 0, 0, groups):
        raise OSError("could not take root's file identity back for the agent's own file")
    _ACTING.now = (0, 0)
    try:
        yield
    finally:
        ok = _fs_become(lib, was[0], was[1], [])
        _ACTING.now = was
        if not ok:
            log("could not return to an account's file identity: stopping")
            os._exit(70)


_FS_HOLDS = {}


def fs_probe(who):
    """Whether acting_as() holds on this machine, tried and not assumed:
    (True, "") when a thread acting as `who` is refused a file of root's
    behind a link in a folder of its own, makes files that are its own,
    carries none of root's groups, and is root again afterwards while
    another thread stayed root throughout; (False, why) otherwise; (None,
    why) where there is nothing to try (not root, no account, not Linux)."""
    import tempfile
    ids = _ids(who)
    if not hasattr(os, "geteuid") or os.geteuid() != 0:
        return None, "this agent is not root"
    if not ids:
        return None, "no account to act as"
    if not _fs_libc():
        return None, "this system has no per-thread file identity"
    d = tempfile.mkdtemp(prefix="aerie-fsprobe.")
    said = []
    try:
        os.chmod(d, 0o755)
        secret, acct = os.path.join(d, "roots-own"), os.path.join(d, "account")
        with open(secret, "w") as f:
            f.write("x")
        os.chmod(secret, 0o600)
        os.mkdir(acct, 0o700)
        os.chown(acct, *ids)
        os.symlink(secret, os.path.join(acct, "link"))
        other = {}
        go, went = threading.Event(), threading.Event()

        def beside():
            # A thread that was there before: it must stay root while another
            # acts as the account. (One STARTED inside acting_as would not:
            # a new thread is whoever started it.)
            go.wait(20)
            try:
                with open(secret) as f:
                    other["read"] = f.read() == "x"
            except OSError as e:
                other["read"] = False
                other["why"] = str(e)
            went.set()

        watcher = threading.Thread(target=beside)
        watcher.start()

        def work():
            try:
                with acting_as(ids):
                    go.set()
                    went.wait(10)
                    try:
                        with open(os.path.join(acct, "link")) as f:
                            f.read()
                        said.append("a link to root's own file was followed and read")
                    except PermissionError:
                        pass
                    try:
                        with open(os.path.join(acct, "link"), "w") as f:
                            f.write("y")
                        said.append("a link to root's own file was followed and written")
                    except PermissionError:
                        pass
                    with open(os.path.join(acct, "made"), "w") as f:
                        f.write("z")
                    if os.getgroups():
                        said.append(f"the thread kept groups {os.getgroups()}")
                    with as_root():
                        with open(secret) as f:
                            if f.read() != "x":
                                said.append("root's own file changed")
                made = os.lstat(os.path.join(acct, "made"))
                if (made.st_uid, made.st_gid) != ids:
                    said.append(f"a file made there is {made.st_uid}:{made.st_gid}'s, not the account's")
                with open(secret) as f:
                    if f.read() != "x":
                        said.append("root's own file changed")
            except OSError as e:
                said.append(f"{type(e).__name__}: {e}")

        t = threading.Thread(target=work)
        t.start()
        t.join(30)
        go.set()
        watcher.join(25)
        if t.is_alive():
            said.append("the probe did not finish")
        if other.get("read") is not True:
            said.append("another thread was not root meanwhile" + (f" ({other.get('why')})" if other.get("why") else ""))
    except OSError as e:
        said.append(f"{type(e).__name__}: {e}")
    finally:
        shutil.rmtree(d, ignore_errors=True)
    return (not said), "; ".join(said)


def fs_holds(who):
    """acting_as() for `who`, where this machine was seen to hold it (once a
    process, by fs_probe); else a block that changes nothing, said once: the
    file work is then root's as it was before, and the agent's log says why."""
    ids = _ids(who)
    if not ids or not hasattr(os, "geteuid") or os.geteuid() != 0:
        return acting_as(None)
    if "ok" not in _FS_HOLDS:
        ok, why = fs_probe(ids)
        _FS_HOLDS["ok"] = ok is True
        if ok is False:
            log(f"file work in an account's folder is done as root on this machine, as before: the check of "
                f"doing it as the account failed ({why})")
        elif ok is True:
            log("file work in an account's folder is done as that account")
    return acting_as(ids if _FS_HOLDS["ok"] else None)


# -- an update on trial ---------------------------------------------------------
#
# A self-update keeps the file it replaces (FILE.prev) and leaves a note that
# the new one is on trial (FILE.trial). The zip's entry, builderbot-agent.py,
# holds the way back, with the standard library alone since it has to work
# when this package does not: it counts each start of `run` while the note is
# there, and a package that cannot be loaded or a start past its count puts
# the old file back, leaving why in FILE.back. This side begins a trial, ends
# it at the first answer from the controller, gives way when none came in
# TRIAL_S, and says a way back taken to the controller (R241).
TRIAL_S = int(os.environ.get("BUILDERBOT_AGENT_TRIAL_S", "600") or 600)
SELFCHECK_S = 120


def _note(path):
    try:
        with open(path, encoding="utf-8") as f:
            d = json.load(f)
        return d if isinstance(d, dict) else None
    except (OSError, ValueError):
        return None


def _note_write(path, d):
    tmp = path + ".w"
    with open(tmp, "w", encoding="utf-8") as f:
        json.dump(d, f)
    os.replace(tmp, path)


def trial_note():
    """The note of an update on trial, or None."""
    return _note(own_path() + ".trial")


def trial_begin(digest, was):
    """The file about to replace this one is on trial from its first start."""
    _note_write(own_path() + ".trial", {"digest": digest, "from": was, "starts": 0, "at": int(time.time())})


def trial_passed():
    """The trial over, the new agent kept: its note taken away, and with it
    the word of a way back taken before. Whether there was a trial."""
    me = own_path()
    was = os.path.exists(me + ".trial")
    for x in (".trial", ".back"):
        with contextlib.suppress(OSError):
            os.unlink(me + x)
    return was


def trial_give_way(why):
    """The note marked so the entry puts the old file back at the next start,
    which the caller makes now. False where there is no trial or nothing to
    go back to."""
    me = own_path()
    t = _note(me + ".trial")
    if t is None or not os.path.isfile(me + ".prev"):
        return False
    t["why"] = str(why)[:300]
    try:
        _note_write(me + ".trial", t)
    except OSError:
        return False
    return True


def back_note():
    """A way back this node took, for its controller: the digest it would
    not run, when, and why; None where it took none."""
    b = _note(own_path() + ".back")
    if not b or not b.get("digest"):
        return None
    try:
        at = int(b.get("at") or 0)
    except (TypeError, ValueError):
        at = 0
    return {"digest": str(b["digest"])[:80], "at": at, "why": str(b.get("why") or "")[:300]}


def selfcheck(path):
    """The agent file at `path` asked to load itself, before it replaces the
    running one: (True, what it said) when it does, (False, why) when it
    does not, and (None, "") for a build from before the check, which has no
    such verb and is installed as every build was."""
    import zipfile
    try:
        with zipfile.ZipFile(path) as z:
            knows = b'"selfcheck"' in z.read("aerieos_agent/cli.py")
    except (OSError, KeyError, zipfile.BadZipFile):
        knows = False
    if not knows:
        return None, ""
    try:
        r = subprocess.run([sys.executable, path, "selfcheck"], capture_output=True, text=True,
                           timeout=SELFCHECK_S, check=False, stdin=subprocess.DEVNULL)
    except subprocess.TimeoutExpired:
        return False, f"it did not load within {SELFCHECK_S} seconds"
    except OSError as e:
        return False, f"it could not be run: {e}"
    said = (r.stdout + r.stderr).strip()
    if r.returncode == 0 and "selfcheck ok" in r.stdout:
        return True, r.stdout.strip().splitlines()[-1]
    return False, " | ".join(said.splitlines()[-4:])[:400] or f"it ended with {r.returncode} and said nothing"


# ---------------------------------------------------------------------------
# the census and the sample

def _run(argv, timeout=5):
    try:
        p = subprocess.run(argv, capture_output=True, text=True, timeout=timeout,
                           check=False)
        return (p.stdout or p.stderr).strip()
    except (OSError, subprocess.SubprocessError):
        return ""


_PROBE_SAID = set()


def _probe_as(exe):
    """Who a version probe runs as, from root: the account that owns the
    binary, or nobody where root owns it and another account may write it.
    The agent is root, and the binaries it asked for a version (a toolchain
    store's java, a session's own claude) are files a build or a session can
    replace, which root then ran (B523). As whom they answer changes nothing
    of what they print."""
    if os.geteuid() != 0:
        return {}
    import shutil
    import stat
    try:
        st = os.stat(shutil.which(exe) or exe)
    except OSError:
        return {}
    if st.st_uid != 0:
        return {"user": st.st_uid, "group": st.st_gid, "extra_groups": []}
    if st.st_mode & (stat.S_IWGRP | stat.S_IWOTH):
        return {"user": 65534, "group": 65534, "extra_groups": []}
    return {}


def _probe(argv, timeout=5):
    """Ask a tool for its version: what it said, and whether it ANSWERED.

    _run cannot tell those apart (it hands back stdout or stderr and drops
    the status), so a binary that ABORTS on startup read as a tool that
    printed something odd, and _clean_version called that "present". The node
    then advertised a toolchain it cannot run, and the controller placed work
    there that could only fail on arrival. Measured on bb-sandbox-redhat,
    where the toolchain store's dotnet dies every census while the row said
    the node had .NET.

    Death by SIGNAL, or a probe that never comes back, is the line. A
    non-zero EXIT is not: `flutter --version` as root and rustup with no
    default toolchain both exit non-zero with a sentence, and both mean the
    tool is installed and being awkward, which is what "present" is for.

    There is no attempt to stop a crashing probe dumping core, because there
    is no way to from here. This ran under `ulimit -c 0` for one build on the
    theory that a version probe has no business leaving a core file, and the
    kernel ignores RLIMIT_CORE when core_pattern is a PIPE, which is what
    both machines here have (apport on one, systemd-coredump on the other).
    Measured, not assumed: the limit reads back as 0 and the process is
    dumped anyway. The dumps stop when the tool does; what this can do is
    say which binary it was, which is the part nobody had.
    """
    try:
        p = subprocess.run(argv, capture_output=True, text=True, timeout=timeout,
                           check=False, **_probe_as(argv[0]))
    except subprocess.TimeoutExpired:
        return "", f"did not answer within {timeout}s"
    except (OSError, subprocess.SubprocessError) as e:
        return "", str(e)[:80]
    out = (p.stdout or p.stderr).strip()
    return out, (f"died on signal {-p.returncode}" if p.returncode < 0 else "")


def _probe_died(name, path, out, why):
    """Say it once, and leave the name out of the census.

    Out, because reporting a toolchain that cannot start is what lets the
    controller send work here that can only fail. Once per agent process,
    because the census runs every ten minutes and the interesting part (the
    tool's own first line, which is the whole diagnosis) does not change; a
    restart says it again, which is when somebody is looking anyway.
    """
    if name in _PROBE_SAID:
        return
    _PROBE_SAID.add(name)
    # The whole of what it said, newlines folded, not its first line, which
    # was the first cut of this and threw the answer away: .NET's startup
    # failures open with "Process terminated." on a line of their own and put
    # the reason on the next one, so the log carried the half that says
    # nothing and dropped the half somebody has to act on.
    said = " ".join((out or "").split())[:300]
    log(f"toolchain: {path} {why} when asked its version, so {name} is not in "
        f"this node's census" + (f". It said: {said}" if said else ""))


def _mem():
    tot = avail = 0
    try:
        with open("/proc/meminfo") as f:
            for line in f:
                if line.startswith("MemTotal:"):
                    tot = int(line.split()[1]) // 1024
                elif line.startswith("MemAvailable:"):
                    avail = int(line.split()[1]) // 1024
    except (OSError, ValueError):
        pass
    return tot, max(0, tot - avail)
