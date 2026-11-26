"""The coding agents a session may run, as one table (R95).

A session used to be Claude's by construction: bb-tty's `claude:` argument,
the `claude-` session name, the `claude` census key, the claude-login job,
the ~/.claude/projects transcripts. Each of those is a fact about one agent,
and this table is where each agent's facts are written, so a place that
used to say claude asks here which agent a name or an argument is, and
what that agent's command, job, sign-in or transcript folder is called.

Each row is an adapter: how the agent installs and reports its version
(`command`, `reported`, `version`, `update_job`, and where its newest is
asked, `latest_url` or `latest_file`), signs in and out
(`provider`, `login_job`, `logout_job`), is launched (`arg`, `session`),
takes the briefing (`briefing`), is guarded (`guards`), reports its state
(`state`) and keeps its transcripts (`transcripts`). A row with `live`
False is planned and not wired: nothing parses a session name or an
argument as one of its, and no Start offers it, so the table can carry
the agents a later step wires without anything behaving differently now.

No imports from the rest of the dashboard, like names.py, so bb-tty, the
node's bundle and the doctor can read it standalone. The page's copy is
page-agents.js, held to this one by unit/test_agents.py; the node agent's
prefixes (aerieos_agent/sessions.py AGENT_PREFIXES) by the same test.
"""
import json
import os
import re
from dataclasses import dataclass, field


@dataclass(frozen=True)
class Agent:
    id: str                 # the table's key, and the stem of its names
    name: str               # what a person reads: on Start, the dock, a section
    product: str            # the program, as its makers call it
    command: str            # the binary a session runs, on the session account's PATH
    provider: str           # whose account signs it in, "" when it has none of its own
    reported: str           # the census key a node reports its version under
    update_job: str         # the node job that installs, updates or removes it
    login_job: str          # the node job that signs an account in, "" for none
    logout_job: str         # ...and out
    briefing: str           # how it is handed the briefing (BRIEFING below)
    guards: str             # what holds its guards (GUARDS below)
    state: str              # where working, waiting and asking are read from
    transcripts: str        # its conversations, under the account's home
    live: bool = False      # wired end to end: parsed, offered, started
    tool: str = ""          # its row's name in the Library and on the Installed page, "" when it has none yet
    latest_url: str = ""    # where the newest release is asked (an npm registry `latest`, or a plain version)
    latest_file: str = ""   # ...or, for a row with no registry, the installer's own `latest` file on its maker's download service; no pack's field
    census_suffix: str = ""  # what its --version prints after the number, kept on the census value a finished job writes
    says: dict = field(default=None, compare=False, hash=False)  # its own wording of a sentence agentcode.py says of every agent (agentcode.SAYS, by key), None for none
    pack: dict = field(default=None, compare=False, hash=False)  # a pack agent's adapter (R169 step 9), None for the shipped
    allow: dict = field(default=None, compare=False, hash=False)  # how it is told a command needs no asking (ALLOW_HOW), None for no way
    install: dict = field(default=None, compare=False, hash=False)  # its install recipe (install_checked), None for one a pack installs
    signin: dict = field(default=None, compare=False, hash=False)  # how it signs in, as a pack's manifest says its own (agent.signin), None for none

    @property
    def arg(self):
        """bb-tty's argument prefix: `claude:PROJECT`."""
        return self.id + ":"

    @property
    def session(self):
        """The tmux session prefix, before the account's: `claude-PROJECT`."""
        return self.id + "-"


# What each was checked against when R95 began (22 Oct): Codex CLI 0.163.0,
# Copilot CLI 1.0.102 and OpenCode 1.19.4, their help and docs read. Codex
# and Copilot both carry hooks now (Codex's SessionStart, PreToolUse,
# PermissionRequest, UserPromptSubmit and Stop; Copilot's sessionStart,
# preToolUse, permissionRequest, userPromptSubmitted and agentStop), so
# their guards and their state are hooks as Claude's are; OpenCode's are a
# plugin's.
#
# How each takes the briefing: a system prompt file on its command line
# (Claude's --append-system-prompt-file), or an instructions file in the
# session's view that the agent reads the way it reads a project's own.
BRIEFING = {"system-prompt-file", "instructions-file"}


def _recipes():
    """Each shipped agent's install recipe (install_checked, below), by its
    id: kept as data beside this file (agent-recipes.json), since a recipe
    carries pins that move. The tool that proposes a newer pin
    (tools/pins.py) writes it there, the packs are written from it
    (tools/packs-export.py), and nothing holds a second copy. A reader
    with no such file beside it (the node's bundle carries this table
    alone, and is handed each recipe with its job) has none."""
    try:
        with open(os.path.join(os.path.dirname(os.path.abspath(__file__)), "agent-recipes.json"), encoding="utf-8") as f:
            got = json.load(f).get("recipes")
    except (OSError, ValueError, AttributeError):
        return {}
    return got if isinstance(got, dict) else {}


RECIPES = _recipes()
# What holds the guards: the agent's own hooks (Claude's seven), or its
# approval policy and sandbox with the bb-session view and the bb wrapper
# holding what it has no hook for.
GUARDS = {"hooks", "plugin", "approval"}
STATES = {"hooks", "plugin", "session-log"}

TABLE = (
    Agent(id="claude", name="Claude", product="Claude Code", command="claude",
          provider="Anthropic", reported="claude", update_job="claude-update",
          login_job="claude-login", logout_job="claude-logout",
          briefing="system-prompt-file", guards="hooks", state="hooks",
          transcripts=".claude/projects", live=True, tool="claude-code",
          latest_file="https://downloads.claude.ai/claude-code-releases/latest",
          census_suffix=" (Claude Code)",
          says={"no_account": "{node} runs no session account, so there is no {product} there to update",
                "hold": "{product} is updating on {node}: press {name} on {project} again when its row comes back"},
          allow={"how": "settings", "rule": "Bash({cmd} *)"},
          # Its sign-in as a pack's agent says its own (R234 step 6): a link
          # at one of three hosts, a code pasted back, the program ending
          # itself once signed in; who is signed in is the address its own
          # record names, while the credential beside it is there.
          signin={"login": ["claude", "auth", "login"],
                  "flow": {"url": ["https://claude.com/", "https://console.anthropic.com/", "https://platform.claude.com/"],
                           "prompt": "Paste code", "refused": "Invalid code", "ends": "exit", "kept": ".claude/.credentials.json",
                           "logout": ["claude", "auth", "logout"],
                           "who": {"file": ".claude.json", "email": ["oauthAccount", "emailAddress"]}}},
          # Its vendor's installer, held to its sha256 and run from the file:
          # it has no version in its address, so the day its vendor edits
          # it an install is refused until the pin moves. It is handed no
          # version: the one asked for is read from the versions folder it
          # leaves (fresh).
          install=RECIPES.get("claude")),
    Agent(id="codex", name="ChatGPT", product="Codex CLI", command="codex",
          provider="OpenAI", reported="codex", update_job="codex-update",
          login_job="codex-login", logout_job="codex-logout",
          briefing="instructions-file", guards="hooks", state="hooks",
          transcripts=".codex/sessions", tool="codex-cli", live=True,
          latest_url="https://registry.npmjs.org/@openai/codex/latest",
          allow={"how": "rules-file", "file": ".codex/rules/aerieos.rules",
                 "rule": 'prefix_rule(pattern={argv}, decision="allow")'},
          # A device login (0.164.0): a link, a one-time code under it,
          # the program ending itself once the person has entered the code
          # on OpenAI's page; who is signed in is the address its id token
          # names, or that it is an API key.
          signin={"login": ["codex", "login", "--device-auth"],
                  "flow": {"url": "https://auth.openai.com/", "code_after": "Enter this one-time code", "ends": "exit",
                           "kept": ".codex/auth.json", "logout": ["codex", "logout"],
                           "who": {"email": ["tokens", "id_token", "email"],
                                   "plan": ["tokens", "id_token", "https://api.openai.com/auth", "chatgpt_plan_type"],
                                   "key": ["OPENAI_API_KEY"], "key_named": "an OpenAI API key"}}},
          # Its vendor's installer as each release carries it, held to the
          # sha256 GitHub states for it: it lays a package out under
          # ~/.codex with links into it, which no step here could stand in
          # for, and downloads that package by itself.
          install=RECIPES.get("codex")),
    Agent(id="copilot", name="Copilot", product="Copilot CLI", command="copilot",
          provider="GitHub", reported="copilot", update_job="copilot-update",
          login_job="copilot-login", logout_job="copilot-logout",
          briefing="instructions-file", guards="hooks", state="hooks",
          transcripts=".copilot/session-state", tool="copilot-cli", live=True,
          latest_url="https://registry.npmjs.org/@github/copilot/latest",
          allow={"how": "flag", "flag": "--allow-tool", "rule": "shell({cmd}:*)"},
          # A device login (1.0.102). With no keyring on the machine it
          # asks, once GitHub has the code, whether to keep its token in
          # its config file: answered yes, the file being the account's
          # own. It has no sign-out of its own outside a session, so the
          # logins its config remembers are forgotten from it, and the
          # token with them where it was kept there.
          signin={"login": ["copilot", "login", "--device-code"], "env": {"COPILOT_AUTO_UPDATE": "false"},
                  "flow": {"url": "https://github.com/login/device", "code_after": "enter code", "ends": "exit",
                           "answers": [{"when": "plaintext config file", "send": "y"}],
                           "kept": ".copilot/config.json",
                           "forget": {"keys": ["lastLoggedInUser", "loggedInUsers"], "like": "token"},
                           "who": {"email": ["lastLoggedInUser", "login"]}}},
          # The program itself, pinned: its release's tarball for each
          # platform, held to the sha256 GitHub states and unpacked into
          # ~/.local/bin, which is all its vendor's installer does with it.
          install=RECIPES.get("copilot")),
    # Grok Build (R95 step 21): xAI's coding agent, checked against its user
    # guide on 25 Oct (xai-org/grok-build, Apache-2.0). Its hooks are
    # Claude's events (PreToolUse, UserPromptSubmit, Stop), its sign-in a
    # device code into ~/.grok/auth.json, its sessions under ~/.grok/sessions.
    Agent(id="grok", name="Grok", product="Grok Build", command="grok",
          provider="xAI", reported="grok", update_job="grok-update",
          login_job="grok-login", logout_job="grok-logout",
          briefing="system-prompt-file", guards="hooks", state="hooks",
          transcripts=".grok/sessions", tool="grok-build", live=True,
          latest_url="https://x.ai/cli/stable",
          allow={"how": "flag", "flag": "--allow", "rule": "Bash({cmd}:*)"},
          # A device code: a link at one of its hosts, the code under it,
          # the program ending itself once confirmed; who is signed in is
          # the address a token of its session names, where one does.
          signin={"login": ["grok", "login", "--device-auth"], "env": {"GROK_DISABLE_AUTOUPDATER": "1"},
                  "flow": {"url": ["https://accounts.x.ai/", "https://auth.x.ai/", "https://x.ai/", "https://grok.com/"],
                           "code_after": "Confirm this code in your browser", "ends": "exit", "kept": ".grok/auth.json",
                           "logout": ["grok", "logout"], "who": {"named": "an xAI account"}}},
          # The program itself, pinned: its vendor publishes one binary a
          # platform at each version and states no digest for it, and its
          # installer checks none, so the pin is the sha256 of the file as
          # it was when the pin was made. Put where the installer keeps it
          # (~/.grok/downloads) with the command a link to it.
          install=RECIPES.get("grok")),
    # Any model (R144 step 2): OpenCode, the open agent, pointed at a node's
    # model router (router.py) rather than signed in to anybody: its keys
    # are the router's, handed to a session at its start with the models
    # the router offers; its briefing an instructions file in its config,
    # its guards and its state a plugin of AerieOS's (bb-tty writes it)
    # calling bb-agent-hook as the others' hooks do, its conversations
    # exported by that plugin at each turn's end. Checked against OpenCode
    # 1.x's docs on 28 Oct.
    Agent(id="open", name="Any model", product="OpenCode", command="opencode",
          provider="", reported="opencode", update_job="opencode-update",
          login_job="", logout_job="",
          briefing="instructions-file", guards="plugin", state="plugin",
          transcripts=".local/share/opencode", tool="opencode", live=True,
          latest_url="https://registry.npmjs.org/opencode-ai/latest",
          # Its vendor's installer as its repository has it at each release's
          # tag, held to its sha256. It picks the build for the machine (one
          # for a processor without AVX2, which a platform's name cannot
          # say), puts the program in ~/.opencode/bin whatever it is told
          # (read off the script on 11 Nov), and is asked not to write the
          # account's shell files; the old place goes with a removal.
          install=RECIPES.get("open")),
)

_BY_ID = {a.id: a for a in TABLE}

# ---- what an agent need not ask about (R231) ----------------------------------
# Every coding agent has a permission check of its own (Claude Code's rules
# and its classifier, Codex's execpolicy, Copilot's and Grok's allow lists),
# and none of them knows the space's Agents may. Left alone, each judges an
# `aerie` command by itself: the same release that ran one day was refused
# the next, with the space's dial on auto both times (the operator, 11 Nov).
# AerieOS is what decides these verbs: each is checked on the controller
# against the space's dials, its pushing rules and its git host's permit, or
# waits for a person's answer on the bell. So an agent is told, in its own
# words, that these need no asking, and the answer is the controller's alone.
#
# Only the verbs the controller decides. What runs a command of the
# session's own (`aerie run`, `build`, `test`, `emu`, `gpu run`) is left to
# the agent's check, as that command would be if it were typed bare.
OWN_VERBS = ("version", "changelog", "roadmap", "bug", "rules", "design", "wiki", "memory", "report",
             "git", "forge", "devapp", "container", "vm", "k8s", "tool", "sign", "pc", "root", "phone",
             "settings", "tidy")
OWN_NAMES = ("aerie",)
# How an agent takes the list, which its row here or its pack's manifest
# says (agent.allow): a rule in the settings file its session starts with
# (Claude Code), an option repeated on its command line (Grok, Copilot), a
# rules file under its home (Codex), its own hook's answer before a tool
# (Antigravity CLI, whose rules are in the person's own settings file: R233),
# or no way at all.
ALLOW_HOW = ("none", "settings", "flag", "rules-file", "hook")
_ALLOW_FLAG = re.compile(r"--[a-z][a-z0-9-]{1,30}")
_ALLOW_RULE = re.compile(r"[A-Za-z0-9_ ()\[\]{}=,:.*\"'-]{3,120}")
_ALLOW_FILE = re.compile(r"\.?[A-Za-z0-9_-]{1,40}(/[A-Za-z0-9._-]{1,60}){0,5}")


def allow_checked(spec):
    """(spec, why): an agent's `allow` as it is kept, or why it is refused.
    A manifest's words reach a command line and a file under the account's
    home, so each is held to a shape: the option's name, a rule that carries
    {cmd} or {argv}, a file by its path under the home."""
    if spec in (None, "", {}):
        return None, ""
    if not isinstance(spec, dict) or spec.get("how") not in ALLOW_HOW:
        return None, f"agent.allow.how is one of {', '.join(ALLOW_HOW)}"
    how = spec["how"]
    if how == "none":
        return None, ""
    if how == "hook":
        # No rule of its own: bb-agent-hook answers for each verb (own_verb).
        return {"how": "hook"}, ""
    rule = spec.get("rule")
    if not (isinstance(rule, str) and _ALLOW_RULE.fullmatch(rule) and ("{cmd}" in rule or "{argv}" in rule)):
        return None, "agent.allow.rule is the agent's own rule for one command, with {cmd} (aerie version) or {argv} ([\"aerie\", \"version\"]) where the command goes"
    out = {"how": how, "rule": rule}
    if how == "flag":
        if not (isinstance(spec.get("flag"), str) and _ALLOW_FLAG.fullmatch(spec["flag"])):
            return None, "agent.allow.flag is the option that takes one rule, e.g. --allow"
        out["flag"] = spec["flag"]
    if how == "rules-file":
        f = spec.get("file")
        if not (isinstance(f, str) and _ALLOW_FILE.fullmatch(f) and ".." not in f):
            return None, "agent.allow.file is the rules file's path under the account's home, e.g. .codex/rules/aerieos.rules"
        out["file"] = f
    return out, ""


def allow_plan(agent_id, spec=None):
    """What starting this agent's session does so it need not ask about the
    verbs AerieOS decides: {"settings": [rule...], "args": [option, rule,
    ...], "file": {"path", "text"} or None}. Empty for an agent with no way
    of being told, and for one its hook answers for, which a start does
    nothing toward. `spec` is a pack agent's own, where the caller holds its
    adapter (a node's bb-tty, which has no table of packs)."""
    a = get(agent_id)
    spec, _why = allow_checked(spec or (a.allow if a else None) or ((a.pack or {}).get("allow") if a else None))
    plan = {"settings": [], "args": [], "file": None}
    if not spec or spec["how"] == "hook":
        return plan
    rules = []
    for name in OWN_NAMES:
        for verb in OWN_VERBS:
            rules.append(spec["rule"].replace("{cmd}", f"{name} {verb}").replace("{argv}", json.dumps([name, verb])))
    if spec["how"] == "settings":
        plan["settings"] = rules
    elif spec["how"] == "flag":
        plan["args"] = [x for r in rules for x in (spec["flag"], r)]
    elif spec["how"] == "rules-file":
        head = "# Written by AerieOS at each session's start: the aerie verbs its controller decides need no asking here.\n"
        plan["file"] = {"path": spec["file"], "text": head + "\n".join(rules) + "\n"}
    return plan

# ---- how an agent is installed (R169 step 13) ---------------------------------
# A shipped agent's install recipe is its row's `install`, which its pack's
# manifest in the catalog carries as agent.install. The controller hands the
# recipe to the node with each install, update and removal, the catalog's
# where the signed index pins a pack whose `rev` is higher than this table's
# (agentcode.recipe), so a pin that moves is answered by a catalog commit and
# a maintainer's signature, with no release of AerieOS. `rev` moves by one
# with any change to a recipe here, or a catalog still holding the old one
# wins.
#
# A recipe is held like any entry's install (pack format 5): what it fetches
# is declared (`fetch`, each download with its sha256 or its publisher's
# signature under a key in `keyring`), the node fetches and holds each before
# anything runs, and `steps` then run from what was fetched, each a list of
# words and never a line a shell reads. Without `online` the steps run with
# no network; with it the recipe says in one sentence what its pinned
# installer downloads by itself. Beside them, what is the agent's own: the
# variable a version is handed to an installer through (`pin`), the
# installer's environment (`env`), where the program lands under the
# account's home (`bin`), older places a removal clears (`also`), and the
# folder a named version is read from (`fresh`).
#
# A vendor's installer fetched over https and handed to a shell as it
# arrives (`script`, in the place of fetch and steps) is no recipe: nothing
# in it holds what arrives, so it is refused as a shape, whoever signed the
# index that names it.
_INSTALL_NAME = re.compile(r"[A-Z][A-Z0-9_]{1,40}")
_INSTALL_VALUE = re.compile(r"[A-Za-z0-9._/{}:=-]{0,200}")
_INSTALL_PATH = re.compile(r"\.?[A-Za-z0-9_-]{1,40}(/[A-Za-z0-9._{}-]{1,60}){1,5}")
# What an installer's environment never sets is the format's one rule for
# a variable an entry may set (packformat.env_name_ok).
# A step of a held recipe: a few plain words. What it runs is a file the
# recipe fetched ({dir}/...), sh or bash on one, or one of the tools that
# only put files in place; so a step is never a line of shell, and nothing
# reaches a shell from the network but a file held to its entry.
INSTALL_STEPS_MOST, INSTALL_WORDS_MOST = 8, 16
INSTALL_HOLES = ("{dir}", "{home}", "{version}")
INSTALL_TOOLS = ("mkdir", "tar", "unzip", "install", "ln", "chmod")
INSTALL_SHELLS = ("sh", "bash")
_INSTALL_WORD = re.compile(r"[A-Za-z0-9_@%+=:,./{}-]{1,200}")
INSTALL_KEYS = frozenset(("rev", "fetch", "keyring", "online", "steps", "pin", "env", "bin", "also", "fresh"))


def _install_path(v, braces=""):
    """Whether `v` is a path of two or more parts under the account's home,
    with no braces but `braces` ({v} for the versions folder)."""
    if not (isinstance(v, str) and _INSTALL_PATH.fullmatch(v)) or ".." in v.split("/"):
        return False
    rest = v.replace(braces, "") if braces else v
    return "{" not in rest and "}" not in rest


def install_version(spec):
    """The version a held recipe's downloads say they are, or "": the one
    version every download that says one says. It fills {version} in the
    recipe's steps, and is what an install brings where the program itself
    is among the downloads and the steps run with no network."""
    fetch = spec.get("fetch") if isinstance(spec, dict) else None
    said = {f.get("version") for f in fetch if isinstance(f, dict) and f.get("version")} if isinstance(fetch, list) else set()
    return said.pop() if len(said) == 1 else ""


def install_pins(spec):
    """The version an install of this recipe brings whatever its vendor's
    newest is, or "": a held recipe whose steps run with no network installs
    the program it declares, at the version that says (install_version). An
    installer that keeps the network brings whichever version it is asked
    for."""
    return install_version(spec) if isinstance(spec, dict) and spec.get("steps") and not spec.get("online") else ""


def _install_steps(steps, fetch):
    """Why a held recipe's steps are not ones, or ""."""
    said = (f"agent.install.steps lists up to {INSTALL_STEPS_MOST} commands, each a list of plain words: a file the recipe fetched "
            f"({{dir}}/...), sh or bash on one, or one of {', '.join(INSTALL_TOOLS)}, with {', '.join(INSTALL_HOLES)} where a path goes")
    if not (isinstance(steps, list) and 1 <= len(steps) <= INSTALL_STEPS_MOST):
        return said
    kept = {"{dir}/" + f["to"] for f in fetch}
    for step in steps:
        if not (isinstance(step, list) and 1 <= len(step) <= INSTALL_WORDS_MOST
                and all(isinstance(w, str) and _INSTALL_WORD.fullmatch(w) and ".." not in w.split("/") for w in step)):
            return said
        for w in step:
            rest = w
            for hole in INSTALL_HOLES:
                rest = rest.replace(hole, "")
            if "{" in rest or "}" in rest:
                return said
            # A fetched file is named as its download is kept.
            if w.startswith("{dir}/") and w not in kept:
                return (f"agent.install.steps names {w}, which is no download agent.install.fetch keeps: "
                        "a step runs and reads what the recipe declares")
        run = step[1] if step[0] in INSTALL_SHELLS and len(step) > 1 else step[0]
        if step[0] in INSTALL_SHELLS and not run.startswith("{dir}/"):
            return said
        if not (run.startswith("{dir}/") or step[0] in INSTALL_TOOLS):
            return said
    if any("{version}" in w for step in steps for w in step) and not install_version({"fetch": fetch}):
        return "agent.install.steps names {version}, and its downloads do not say one version to fill it with"
    return ""


def install_checked(spec):
    """(spec, why): an agent's install recipe as it is kept, or why it is
    refused. The node's agent holds the same shape to what it is handed
    (aerieos_agent/base.py recipe_checked; unit/test_agentcode.py holds the two
    to each other). A held recipe's downloads, keys and sentence are the
    format's own shapes (packformat), read here only where a recipe says
    them: a standalone reader of this table checks no recipe."""
    if spec in (None, "", {}):
        return None, ""
    if not isinstance(spec, dict):
        return None, "agent.install is an object: rev, fetch and steps, pin, env, bin, also, fresh"
    rev = spec.get("rev")
    if not (isinstance(rev, int) and not isinstance(rev, bool) and 1 <= rev <= 9999):
        return None, "agent.install.rev is a whole number from 1, one more with each change to the recipe"
    import packformat  # noqa: PLC0415 (the format's shapes, where a recipe is checked)
    if "script" in spec:
        return None, "agent.install.script is no recipe: an installer is a download the recipe declares and holds, run from the file (fetch and steps)"
    # A key the form does not have is said, not dropped: a recipe that
    # says `run` for steps would otherwise install nothing in silence.
    if set(spec) - INSTALL_KEYS:
        return None, (f"agent.install names {', '.join(sorted(str(k) for k in set(spec) - INSTALL_KEYS))}: "
                      "it is rev, fetch, keyring, online, steps, pin, env, bin, also and fresh")
    fetch, errors, _new = packformat.fetch_checked(spec.get("fetch"), "agent.install.fetch")
    if not errors and not fetch:
        errors = ["agent.install.fetch lists what its steps install from: a recipe declares at least one download"]
    keyring, online = {}, ""
    if not errors and spec.get("keyring") is not None:
        keyring, errors = packformat.keyring_checked(spec["keyring"], "agent.install.keyring")
    if not errors and spec.get("online") is not None:
        online, errors = packformat.online_checked(spec["online"], "agent.install.online")
    if not errors:
        errors = [f"agent.install.fetch's {f['to']} is signed under {f['signed']['keys']}, which agent.install.keyring does not carry"
                  for f in fetch if f.get("signed") and f["signed"]["keys"] not in keyring][:1]
    if errors:
        return None, errors[0]
    why = _install_steps(spec.get("steps"), fetch)
    if why:
        return None, why
    how = {"fetch": fetch, **({"keyring": keyring} if keyring else {}), **({"online": online} if online else {}),
           "steps": [list(s) for s in spec["steps"]]}
    pin = spec.get("pin")
    if pin is not None:
        if not (isinstance(pin, (list, tuple)) and len(pin) == 2 and all(isinstance(x, str) for x in pin)
                and _INSTALL_NAME.fullmatch(pin[0]) and packformat.env_name_ok(pin[0])
                and re.fullmatch(r"[A-Za-z0-9._-]{0,12}\{v\}[A-Za-z0-9._-]{0,12}", pin[1])):
            return None, "agent.install.pin is the variable a version is handed through and how it is written, e.g. [\"VERSION\", \"v{v}\"], or null"
        pin = [pin[0], pin[1]]
    env = spec.get("env") or {}
    if not (isinstance(env, dict) and len(env) <= 8 and all(
            isinstance(k, str) and _INSTALL_NAME.fullmatch(k) and packformat.env_name_ok(k)
            and isinstance(v, str) and _INSTALL_VALUE.fullmatch(v) and ".." not in v
            and "{" not in v.replace("{home}", "") and "}" not in v.replace("{home}", "") for k, v in env.items())):
        return None, "agent.install.env is the installer's own variables, each a plain value with {home} for the account's home"
    if not _install_path(spec.get("bin")):
        return None, "agent.install.bin is where the installer leaves the program, under the account's home, e.g. .local/bin/codex"
    also = spec.get("also") or []
    if not (isinstance(also, (list, tuple)) and len(also) <= 6 and all(_install_path(x) for x in also)):
        return None, "agent.install.also is the older places a removal clears, each under the account's home"
    fresh = spec.get("fresh") or ""
    if fresh and not (_install_path(fresh, "{v}") and "{v}" in fresh):
        return None, "agent.install.fresh is the folder a named version is read from, with {v} for the version"
    return {"rev": rev, **how, "pin": pin, "env": dict(sorted(env.items())), "bin": spec["bin"],
            "also": list(also), "fresh": fresh}, ""


# The coding agents installed packs bring (R169 step 9): the server sets this
# to toolpacks.offered_agents, [(name, label, adapter)]; a standalone reader
# (bb-tty, the doctor) has none. Each is an ordinary row, live, installed and
# updated as its pack is, so it has no update or sign-in job of its own.
pack_source = lambda: ()    # noqa: E731
# The node jobs that sign an account in to a pack's agent and out of it: one
# pair for all of them, the job's spec naming which (the agent's jobs.py).
PACK_LOGIN, PACK_LOGOUT = "agent-login", "agent-logout"
_packs = {"key": None, "rows": ()}


def _pack_rows():
    got = tuple(pack_source() or ())
    if got != _packs["key"]:
        rows = []
        for name, _label, a in got:
            if name in _BY_ID:
                continue
            signs_in = bool((a.get("signin") or {}).get("flow"))
            rows.append(Agent(id=name, name=a.get("name") or name, product=a.get("product") or name, command=a.get("command") or name,
                              provider=a.get("provider") or "", reported=name, update_job="",
                              # One that describes its sign-in's flow is signed in
                              # from the page as a shipped one is (R233 step 6),
                              # by one job for every pack's agent, told which.
                              login_job=PACK_LOGIN if signs_in else "", logout_job=PACK_LOGOUT if signs_in else "",
                              briefing="instructions-file" if (a.get("briefing") or {}).get("how") == "env-file" else "system-prompt-file",
                              guards="hooks", state="hooks", transcripts=(a.get("transcripts") or {}).get("dir") or "",
                              live=True, tool=name, pack=a, allow=allow_checked(a.get("allow"))[0]))
        _packs.update(key=got, rows=tuple(rows))
    return _packs["rows"]


def signs_in():
    """{id: adapter} for the shipped agents that say how they sign in, each
    in the shape a pack agent's cleaned adapter has (name, product, command,
    provider, env, login, signin.flow), so one driver on the node runs
    every agent's sign-in and one reader says who is signed in
    (scripts/lib/login-flow.py, login-list.py)."""
    out = {}
    for a in TABLE:
        if a.signin and a.signin.get("flow"):
            out[a.id] = {"name": a.name, "product": a.product, "command": a.command, "provider": a.provider,
                         "env": dict(a.signin.get("env") or {}), "login": list(a.signin.get("login") or []),
                         "signin": {"flow": dict(a.signin["flow"])}}
    return out


def flow_of(agent_id):
    """How this agent's sign-in goes, as its row or its pack's manifest
    says (signin.flow), or None for one that describes none."""
    a = get(agent_id)
    if a is None:
        return None
    return ((a.signin or {}).get("flow") if not a.pack else ((a.pack.get("signin") or {}).get("flow"))) or None


def rows():
    """Every agent: the table's, then the ones installed packs bring."""
    return TABLE + _pack_rows()


def page_rows():
    """The pack agents as the page's table holds an agent (page-agents.js
    AGENTS), with the models Start offers and what holds its guards."""
    out = []
    for a in _pack_rows():
        evs = (a.pack.get("hooks") or {}).get("events") or {}
        lacks = [w for k, w in (("recall", "the house rules' recall after a summary"), ("asking", "the asking mark")) if k not in evs]
        out.append({"id": a.id, "name": a.name, "product": a.product, "command": a.command, "provider": a.provider, "live": True, "pack": True,
                    # Signed in from the page where its pack says how; else in its session's terminal.
                    "signin": bool(a.login_job),
                    "models": list(a.pack.get("models") or []),
                    "guards": "the same guards through its own hooks, from its pack's adapter" + (f", but for {' and '.join(lacks)}, which it names no hook for" if lacks else "")})
    return out


# Each agent's own models and reasoning efforts, what Start's model and
# effort step offers for it (R95 step 9) and the only words bb-tty passes on
# (a table lookup, never a word from the URL): read off Codex CLI 0.163.0's
# `codex debug models` and Copilot CLI 1.0.102's `copilot help config` on
# 22 Oct. Claude's are the project dialog's (MODELS, EFFORTS) as before.
# page-agents.js and bb-tty carry the same lists, held to these by
# unit/test_agents.py.
MODELS = {
    "codex": ('gpt-6.1-sol', 'gpt-6-sol', 'gpt-6-astra', 'gpt-6-luna', 'gpt-5.6-sol', 'gpt-5.6-terra', 'gpt-5.6-luna', 'gpt-5.5'),
    "copilot": ('auto', 'claude-sonnet-5.5', 'claude-opus-5.5', 'claude-haiku-5.5', 'gpt-6.1-sol', 'gpt-6-sol', 'gpt-5.6-sol', 'gpt-5-mini', 'gemini-4-argon', 'gemini-3.8-flash', 'grok-4.7'),
}
EFFORTS = {
    "codex": ('low', 'medium', 'high', 'xhigh', 'max'),
    "copilot": ('low', 'medium', 'high', 'xhigh', 'max'),
}
# Any model's models are the router's (router.models_for), read per project
# rather than kept here; a pick is held to that list by prefs and bb-tty.
OPEN_MODEL = re.compile(r"^[A-Za-z0-9._:/-]{1,120}$")


def get(agent_id):
    """The adapter called this, or None."""
    k = str(agent_id or "")
    return _BY_ID.get(k) or next((a for a in _pack_rows() if a.id == k), None)


def live():
    """The agents a session may run today, Claude first."""
    return tuple(a for a in rows() if a.live)


def default():
    return TABLE[0]


# A second session of one agent on one project is a slot of its own (R143):
# `claude-alpha` is the first, as every session was named before, and
# `claude-alpha~2` the second. tmux keeps `~` as it is (names.tmux_name
# rewrites `.` and `:` alone), and no project's name carries one.
SLOT_SEP = "~"
_SLOT = re.compile(r"~([2-9])$")


def _split_slot(stem):
    m = _SLOT.search(stem)
    return (stem[:m.start()], int(m.group(1))) if m else (stem, 1)


def of_session(base):
    """(agent, stem) for a session name with its account prefix already off
    (`claude-alpha` -> (Claude, "alpha")), or (None, "") for a shell or
    anything else. Only a live agent's names are read as an agent's. The
    stem is the project's as tmux writes it, whichever slot the session is
    (`claude-alpha~2` -> (Claude, "alpha")): slot_of says which."""
    base = str(base or "")
    for a in live():
        if base.startswith(a.session) and len(base) > len(a.session):
            stem = _split_slot(base[len(a.session):])[0]
            return (a, stem) if stem else (None, "")
    return None, ""


def slot_of(base):
    """Which slot an agent's session name is (R143): 1 for `claude-alpha`,
    2 for `claude-alpha~2`; 0 for a name that is no agent's."""
    a, _stem = of_session(base)
    return _split_slot(str(base)[len(a.session):])[1] if a else 0


def is_session(base):
    """True when a session name (account prefix off) is an agent's."""
    return of_session(base)[0] is not None


def of_arg(arg):
    """(agent, rest) for a terminal argument (`claude:alpha:r:UUID` ->
    (Claude, "alpha:r:UUID")), or (None, "") for any other."""
    arg = str(arg or "")
    for a in live():
        if arg.startswith(a.arg):
            return a, arg[len(a.arg):]
    return None, ""


def slot_of_arg(arg):
    """The slot a terminal argument opens (R143): its `:s:N`, 1 when it
    names none, as every argument from before slots does."""
    a, rest = of_arg(arg)
    m = re.search(r":s:([0-9]{1,2})(?::|$)", rest) if a else None
    n = int(m.group(1)) if m else 1
    return n if 1 <= n <= MAX_SLOTS else 1


def project_of_arg(arg):
    """The project an agent's argument names, or ""."""
    a, rest = of_arg(arg)
    return rest.split(":")[0] if a else ""


# The most slots of one agent a person may have on one project, whatever a
# project's own cap says (R143): what the names can carry.
MAX_SLOTS = 9


def session_name(agent_id, project, slot=1):
    """The tmux session an agent's conversation on a project runs in,
    before the account prefix a node puts in front of it. tmux rewrites
    `.` and `:` to `_` (names.tmux_name). A slot past the first carries its
    number (R143)."""
    a = get(agent_id) or default()
    n = int(slot or 1) if str(slot or 1).isdigit() else 1
    return re.sub(r"[.:]", "_", a.session + str(project)) + (f"{SLOT_SEP}{n}" if 1 < n <= MAX_SLOTS else "")


def installable():
    """The agents the Library installs on a node, Claude first: every
    row with a toolchain row of its own, live or not yet, since an agent
    is installed before a session can start it. A pack's agent is not
    among them: it is installed and updated as its pack is."""
    return tuple(a for a in TABLE if a.tool)


def asked_by():
    """The agent whose session is asking, from BB_AGENT, which bb-tty's
    launcher sets for every agent and the relay carries from a node: its
    id, or "" when it is none of the table's. For what a record names as
    its asker, never for whether it may: every gate holds for every agent's
    session alike."""
    a = get(os.environ.get("BB_AGENT", ""))
    return a.id if a else ""


def asker(by):
    """{"agent": id} for a record made by a session ("claude", the stored
    word for any session's), {} otherwise: added beside `by`, which keeps
    its stored values."""
    a = asked_by() if by == "claude" else ""
    return {"agent": a} if a else {}


def by_tool(name):
    """The agent whose row in the Library is called this, or None."""
    return next((a for a in TABLE if a.tool and a.tool == str(name)), None)


def prefixes():
    """The live agents' session prefixes, for a reader that only needs to
    say whether a name is an agent's (the node agent, idle.py)."""
    return tuple(a.session for a in live())
