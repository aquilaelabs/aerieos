"""Tool packs (R77): toolchains a person adds from a git repository of their
own choosing, which AerieOS neither ships nor lists anywhere.

A pack is a repository with a bbtool.json at its root. The manifest says how
the toolchain installs (the catalog's own recipe machinery, its source being
the pack's repository at the commit that was approved), the verbs a session
calls through `aerie tool PACK VERB`, and a guidance file a session reads before it
uses them. An administrator adds a pack by its URL: the controller fetches the
repository at its current commit, shows the manifest, and keeps it pinned to
that commit until somebody approves another. The record lives here, in
/config/toolpacks.json, and never in AerieOS's repository.

What a pack becomes is one catalog row (recipe()), shipped to the nodes in the
bundle beside config/toolchains.json, so it installs, checks and removes the
way every toolchain does, into the store, read-only to sessions.

A pack may also be made here, with no repository of its own: a pasted
bbtool.json, or an uploaded zip or tarball of the pack's files. The
controller keeps it as a repository of its own (/config/toolpacks/NAME.git),
each approved version a commit there, so it is pinned, compared and approved
the same way; the nodes take it as a git bundle that travels in the bundle
beside config/toolpacks.json, and install it with the same pinned fetch.

    configure(state=, write_json=, unpack=)
    validate(manifest)          (clean, [errors])
    fetch(url, commit="")       the repository at a commit: {commit, manifest, guidance} or {error}
    stage(text=, archive=)      a pack made here, checked and held for Add: {staged, manifest, ...}
    add(url, commit, by) / add_staged(staged, by) / remove(name) / source(name)
    packs() / recipes() / hosted_files()
"""
import json
import os
import re
import secrets
import shutil
import subprocess
import tempfile
import threading
import time
from pathlib import Path

import packformat

FILE = None
write_json = None
_lock = threading.RLock()

MANIFEST = "bbtool.json"
NAME = re.compile(r"^[a-z][a-z0-9-]{1,39}$")
# aerie tool's own words (scripts/aerie cmd_tool): a pack of somebody's named one
# would never be reached, so none may be (R169 step 5 added search and
# install); the official packs behind graphics, diagrams and office are the
# toolchains those words run.
BB_TOOL_WORDS = frozenset({"graphics", "diagrams", "docs", "office", "sound", "search", "install"})
NAME_OFFICIAL = re.compile(r"^[a-z][a-z0-9:-]{1,39}$")
# A shipped layout may name the pack's own root ("") or a place under the
# store's root (root:android/...), which a person's pack may not.
REL_OFFICIAL = re.compile(r"^(|root:[A-Za-z0-9._/-]{1,200}|(?!/)(?!.*(?:^|/)\.\.?(?:/|$))[A-Za-z0-9._/-]{1,200})$")
VERB = re.compile(r"^[a-z][a-z0-9-]{0,39}$")
# A path inside the pack: no way out of its directory, nothing hidden.
REL = re.compile(r"^(?!/)(?!.*(?:^|/)\.\.?(?:/|$))[A-Za-z0-9._/-]{1,200}$")
PLATFORM = re.compile(r"^(linux|darwin)/(amd64|arm64|\*)$")
# What a verb's words may name besides plain text: the pack's directory, the
# project's dist/, the project's name, and the words the caller gave.
PLACEHOLDERS = ("{dir}", "{dist}", "{project}", "{args}")
GUIDANCE_MAX = 16 * 1024
MANIFEST_MAX = 64 * 1024
# A pack's own icon on its Library card (R182): a file in the pack, PNG, WebP
# or SVG, kept under the state and served as an image alone (server.py's
# /api/pack-icon), never drawn into the page as markup.
ICON_MAX = 64 * 1024
ICON_TYPES = {"png": "image/png", "webp": "image/webp", "svg": "image/svg+xml"}
# http too, for a git host on the LAN: what is installed is the commit an
# administrator approved, and git checks every object against its hash, so a
# fetch altered on the way is refused rather than installed.
URL = re.compile(r"^(https://|http://|git@|ssh://)[A-Za-z0-9._~:/@+-]{3,300}$")
FETCH_TIMEOUT = 120
# A pack made here: its address in the record, and where it is kept. It
# travels to every node in the bundle, so it is held small: a pack made
# here carries scripts and a manifest, and fetches anything big as it
# installs.
HERE = "here:"
HOSTED = None
unpack = None                 # projects.unpack_archive, handed over by configure()
HOSTED_MAX = 8 << 20
HOSTED_FILES = 2000
STAGE_TTL = 30 * 60
STAGE_ID = re.compile(r"^[0-9a-f]{16}$")
AUTHOR = ("-c", "user.name=AerieOS", "-c", "user.email=builderbot@localhost")


def configure(*, state, write_json, unpack=None):
    globals().update(FILE=Path(state) / "toolpacks.json", write_json=write_json,
                     HOSTED=Path(state) / "toolpacks", unpack=unpack)


def _load():
    try:
        d = json.loads(FILE.read_text())
    except (OSError, ValueError, AttributeError):
        d = {}
    packs = d.get("packs") if isinstance(d, dict) and isinstance(d.get("packs"), dict) else {}
    return {"packs": {k: v for k, v in packs.items() if isinstance(v, dict)}}


def _words(v, what, errors, placeholders=PLACEHOLDERS):
    """A command as a list of words, never a string a shell would read."""
    if not isinstance(v, list) or not v or not all(isinstance(w, str) and w for w in v):
        errors.append(f"{what} is a list of words, e.g. [\"{{dir}}/bin/tool\", \"{{args}}\"]")
        return None
    for w in v:
        for m in re.findall(r"\{[a-z]+\}", w):
            if m not in placeholders:
                errors.append(f"{what} names {m}, which is not one of {', '.join(placeholders)}")
    if v.count("{args}") > 1:
        errors.append(f"{what} names {{args}} more than once")
    if any("{args}" in w and w != "{args}" for w in v):
        errors.append(f"{what}: {{args}} is a word of its own, the caller's words in its place")
    return [str(w) for w in v]


# One manifest for everything (R169 step 1): a pack's tier, and the two
# blocks the official packs carry beyond a person's pack. `shipped` is a
# toolchain's recipe as config/toolchains.json has it (its source, probe,
# system packages and the rest), which the installer runs; `agent` is a
# coding agent's adapter as agents.py's table has it. Either stands in for
# install steps and verbs, since what they install is the tool itself.
TIERS = ("official", "vetted", "url")
# What a pack asks for per node (R172): each field's kind, drawn by the
# Library as Configure on the card, the answers kept sealed on the
# controller and handed to the node. A `list` field is rows of `fields`.
CONFIG_KINDS = ("secret", "text", "choice", "list", "switch", "projects")
CONFIG_NAME = re.compile(r"^[a-z][a-z0-9_-]{0,39}$")
ENV_NAME = re.compile(r"^[A-Z][A-Z0-9_]{0,40}$")
# A deployed thing an official pack stands for (R172): the model router.
SERVICES = ("router",)
AGENT_FIELDS = ("product", "command", "provider", "reported", "update_job", "login_job", "logout_job",
                "briefing", "guards", "state", "transcripts", "latest_url", "tool")
AGENT_BRIEFING = ("system-prompt-file", "instructions-file")
AGENT_GUARDS = ("hooks", "plugin", "approval")
AGENT_STATES = ("hooks", "plugin", "session-log")


def _agent(a, errors):
    """The agent block checked: an agent that cannot take the guards is
    not listed (R169 step 1)."""
    if not isinstance(a, dict):
        errors.append("agent is an object: product, command, provider, reported, the jobs, briefing, guards, state, transcripts")
        return None
    out = {}
    for k in AGENT_FIELDS:
        v = a.get(k, "")
        if not isinstance(v, str) or len(v) > 200:
            errors.append(f"agent.{k} is a string")
            return None
        out[k] = v
    for k in ("product", "command", "reported", "update_job", "transcripts"):
        if not out[k]:
            errors.append(f"agent.{k} is required")
    if not re.fullmatch(r"[a-z][a-z0-9-]{0,39}", out["command"] or "x"):
        errors.append("agent.command is the program's name on PATH")
    if out["briefing"] not in AGENT_BRIEFING:
        errors.append(f"agent.briefing is one of {', '.join(AGENT_BRIEFING)}")
    if out["guards"] not in AGENT_GUARDS:
        errors.append(f"agent.guards is one of {', '.join(AGENT_GUARDS)}: an agent that cannot take AerieOS's guards is not listed")
    if out["state"] not in AGENT_STATES:
        errors.append(f"agent.state is one of {', '.join(AGENT_STATES)}")
    if out["transcripts"] and not REL.fullmatch(out["transcripts"]):
        errors.append("agent.transcripts is a path under the account's home")
    if out["latest_url"] and not re.fullmatch(r"https://[A-Za-z0-9._~:/@+?=&%-]{3,300}", out["latest_url"]):
        errors.append("agent.latest_url is an https address")
    _agent_allow(a, out, errors)
    # How it is installed (R169 step 13): a shipped agent's alone, since a
    # pack agent is installed by its pack's own steps.
    import agents                                               # noqa: PLC0415 (beside this file)
    recipe, why = agents.install_checked(a.get("install"))
    if why:
        errors.append(why)
    elif recipe:
        out["install"] = recipe
    return out


def _agent_allow(a, out, errors):
    """An agent's `allow` (R231): how it is told the aerie verbs the
    controller decides need no asking, checked by agents.allow_checked and
    kept only where it says a way."""
    import agents                                               # noqa: PLC0415 (beside this file)
    spec, why = agents.allow_checked(a.get("allow"))
    if why:
        errors.append(why)
    elif spec:
        out["allow"] = spec


# A coding agent from a vetted pack (R169 step 8): an adapter of data, never
# code. Its hooks file is one of the two shapes bb-tty writes for the shipped
# agents (grouped: {hooks: {EVENT: [{hooks: [{type, command, timeout}]}]}} as
# Claude's, Codex's and Grok's; flat: {version: 1, hooks: {EVENT: [{type,
# bash, timeoutSec}]}} as Copilot's), and its payload one of the two field
# shapes they send (Claude's snake_case, or the camelCase of Grok and
# Copilot), so bb-agent-hook holds it to the same guards with no code of its
# own. Before a tool, a prompt and the stop are required: an agent that
# cannot take the guards is not listed.
#
# An agent whose hooks are none of those says its own as data (R234 step 3),
# so a protocol nobody has met is a manifest and no release of AerieOS:
# hooks.document lays its hooks file out, hooks.payload is the paths its
# payload keeps each thing at, hooks.answers the JSON it reads back for a
# refusal, a pass, words for the model and an approval. The named shapes are
# those descriptions under a name (bb-agent-hook DOCUMENTS, PAYLOADS) and
# stay what they are: a manifest written with them is valid for good.
PACK_AGENT = re.compile(r"^[a-z][a-z0-9]{1,15}$")
PACK_AGENT_SHAPES = ("grouped", "flat")
PACK_AGENT_PAYLOADS = ("snake", "camel")
# `start` is a conversation's start, for an agent handed the briefing by its
# hooks (briefing.how hook); the rest are AerieOS's guards.
PACK_AGENT_EVENTS = ("pre", "prompt", "stop", "recall", "asking", "start")
PACK_AGENT_NEEDS = ("pre", "prompt", "stop")
PACK_AGENT_BRIEFING = ("flag-text", "flag-file", "env-file", "hook", "none")
# When its prompt event is raised: once for each thing a person sends, or
# before every call to its model, where the hooks of a prompt run on the
# first of a turn alone.
PACK_AGENT_PROMPT_FIRES = ("once", "each-call")
# What a payload's paths may name, and a tool's arguments under `args`.
PACK_AGENT_PATHS = ("session", "cwd", "tool", "input", "prompt", "stop_active", "transcript", "call")
PACK_AGENT_ARGS = ("command", "file", "pattern")
PACK_AGENT_ANSWERS = ("refuse", "pass", "say", "approve")
DOTTED = re.compile(r"^[A-Za-z_][A-Za-z0-9_]{0,40}(\.[A-Za-z_][A-Za-z0-9_]{0,40}){0,5}$")
# A template is JSON an agent reads, so what it may hold is narrow: keys
# that are names, numbers, true and false, and strings that are either one
# placeholder, whole, or a single plain word (command, allow, deny, *). No
# string in one can carry a command line, a path or an address: the one
# command a hooks file runs is AerieOS's own, in {command}'s place.
TEMPLATE_KEY = re.compile(r"^[A-Za-z_][A-Za-z0-9_]{0,40}$")
TEMPLATE_WORD = re.compile(r"^[A-Za-z0-9_.*-]{0,40}$")


def _template(v, holes, what, errors, depth=0, count=None):
    """A template held to its shape, or an error said once: `holes` are the
    placeholders it may carry."""
    count = count if count is not None else [0]
    count[0] += 1
    bad = None
    if depth > 6 or count[0] > 60:
        bad = "is deeper or larger than a hook's answer is"
    elif isinstance(v, bool) or v is None:
        bad = None if isinstance(v, bool) else "holds a null"
    elif isinstance(v, int):
        bad = None if -1 <= v <= 86400 else "holds a number no hook is given"
    elif isinstance(v, str):
        bad = None if v in holes or TEMPLATE_WORD.fullmatch(v) else \
            f"holds {v[:30]!r}: a string is one of {', '.join(holes)}, whole, or one plain word"
    elif isinstance(v, list):
        if len(v) > 8:
            bad = "holds a list of more than 8"
        else:
            return all([_template(x, holes, what, errors, depth + 1, count) for x in v])
    elif isinstance(v, dict):
        if not all(isinstance(k, str) and TEMPLATE_KEY.fullmatch(k) for k in v):
            bad = "has a key that is not a name"
        else:
            return all([_template(x, holes, what, errors, depth + 1, count) for x in v.values()])
    else:
        bad = "holds something that is not JSON's"
    if bad:
        errors.append(f"{what} {bad}")
    return not bad


def _paths(v):
    """One path or a short list of them, or None."""
    if isinstance(v, str):
        v = [v]
    return list(v) if isinstance(v, list) and 1 <= len(v) <= 4 and all(isinstance(x, str) and DOTTED.fullmatch(x) for x in v) else None


def _hooks_data(h, errors):
    """What an adapter says of its own protocol, checked: (document,
    payload, answers), each None where it names a shape or gives none."""
    doc = h.get("document")
    if doc is not None:
        ok = isinstance(doc, dict) and set(doc) <= {"under", "with", "keep", "handler", "entry", "entries"}
        under = doc.get("under") if ok else None
        if not (ok and isinstance(under, list) and 1 <= len(under) <= 4 and all(isinstance(k, str) and TEMPLATE_KEY.fullmatch(k) for k in under)):
            errors.append("agent.hooks.document is an object: under (the keys down to its events), handler, entry, and optionally with, keep and entries")
            doc = None
        else:
            ok = _template(doc.get("handler"), ("{command}", "{seconds}"), "agent.hooks.document.handler", errors) and isinstance(doc.get("handler"), dict)
            if ok and "{command}" not in json.dumps(doc["handler"]):
                errors.append("agent.hooks.document.handler names no {command}: a hook that does not call AerieOS holds nothing")
                ok = False
            ok = _template(doc.get("entry", ["{handler}"]), ("{handler}",), "agent.hooks.document.entry", errors) and ok
            entries = doc.get("entries") if doc.get("entries") is not None else {}
            if not (isinstance(entries, dict) and all(k in PACK_AGENT_EVENTS for k in entries)):
                errors.append(f"agent.hooks.document.entries gives one of AerieOS's events its own entry: {', '.join(PACK_AGENT_EVENTS)}")
                ok = False
            else:
                ok = all([_template(v, ("{handler}",), f"agent.hooks.document.entries.{k}", errors) for k, v in entries.items()]) and ok
            for k, v in [("entry", doc.get("entry", ["{handler}"])), *entries.items()] if ok else []:
                if "{handler}" not in json.dumps(v):
                    errors.append(f"agent.hooks.document.{k} names no {{handler}}: an event with no hook holds nothing")
                    ok = False
            ok = _template(doc.get("with", {}), (), "agent.hooks.document.with", errors) and isinstance(doc.get("with", {}), dict) and ok
            doc = {"under": list(under), "with": dict(doc.get("with") or {}), "keep": doc.get("keep") is True,
                   "handler": doc["handler"], "entry": doc.get("entry", ["{handler}"]), "entries": dict(entries)} if ok else None
    pay = h.get("payload")
    if isinstance(pay, dict):
        args = pay.get("args") if pay.get("args") is not None else {}
        ok = set(pay) <= {*PACK_AGENT_PATHS, "args"} and all(_paths(pay[k]) for k in pay if k != "args") \
            and isinstance(args, dict) and set(args) <= set(PACK_AGENT_ARGS) and all(_paths(v) for v in args.values())
        if not ok or not all(k in pay for k in ("session", "tool", "input")):
            errors.append("agent.hooks.payload as paths names where the session, the tool and its input are (session, tool, input), and optionally "
                          "cwd, prompt, stop_active, transcript, call and args (command, file, pattern): each a dotted path or up to 4 of them")
            pay = None
        else:
            pay = {**{k: _paths(pay[k]) for k in pay if k != "args"}, "args": {k: _paths(v) for k, v in args.items()}}
    else:
        pay = None
    ans = h.get("answers")
    if ans is not None:
        ok = isinstance(ans, dict) and all(k in PACK_AGENT_EVENTS and isinstance(v, dict) and set(v) <= set(PACK_AGENT_ANSWERS) for k, v in ans.items())
        if not ok:
            errors.append(f"agent.hooks.answers gives an event ({', '.join(PACK_AGENT_EVENTS)}) what it is answered: {', '.join(PACK_AGENT_ANSWERS)}")
            ans = None
        else:
            holes = {"refuse": ("{reason}",), "pass": (), "say": ("{text}",), "approve": ()}
            ok = all([_template(t, holes[kind], f"agent.hooks.answers.{ev}.{kind}", errors) and isinstance(t, dict)
                      for ev, kinds in ans.items() for kind, t in kinds.items()])
            if ok and not all((ans.get(ev) or {}).get("refuse") for ev in PACK_AGENT_NEEDS):
                errors.append("agent.hooks.answers says how a refusal is written before a tool, on a prompt and at the stop (pre, prompt and stop each a refuse): "
                              "an agent that cannot be refused cannot take AerieOS's guards")
                ok = False
            ans = {ev: dict(kinds) for ev, kinds in ans.items()} if ok else None
    return doc, pay, ans


PACK_AGENT_FIRST = ("after-dashdash", "flag", "none")
SHIPPED_AGENTS = ("claude", "codex", "copilot", "grok", "open")
FLAG = re.compile(r"^-{1,2}[A-Za-z0-9][A-Za-z0-9-]{0,40}$")
ENV_NAME = re.compile(r"^[A-Z][A-Z0-9_]{0,40}$")
ARG = re.compile(r"^[A-Za-z0-9][A-Za-z0-9._=:,/-]{0,80}$|^-{1,2}[A-Za-z0-9][A-Za-z0-9._=:,/-]{0,80}$")
EVENT_NAME = re.compile(r"^[A-Za-z][A-Za-z0-9._]{0,40}$")
TOOL_NAME = re.compile(r"^[A-Za-z][A-Za-z0-9_.-]{0,60}$")


def _pack_agent(name, a, errors, newer=False):
    """The adapter of a coding agent a vetted pack brings, checked and cut
    down to what bb-tty and bb-agent-hook read, or None."""
    if not isinstance(a, dict):
        errors.append("agent is an object: name, product, command, briefing, hooks, signin, transcripts")
        return None
    bad = len(errors)
    if not PACK_AGENT.fullmatch(name):
        errors.append("a pack that brings a coding agent is named 2 to 16 of a-z and 0-9, starting with a letter: its sessions are named after it")
    elif name in SHIPPED_AGENTS:
        errors.append(f"{name} is a coding agent AerieOS ships; a pack's agent takes a name of its own")
    out = {}
    for k, cap in (("name", 30), ("product", 60), ("provider", 60)):
        v = a.get(k, "")
        if not isinstance(v, str) or len(v) > cap or (k != "provider" and not v.strip()):
            errors.append(f"agent.{k} is a short string" + ("" if k == "provider" else ", required"))
        out[k] = str(v or "").strip()[:cap]
    cmd = a.get("command")
    if not (isinstance(cmd, str) and re.fullmatch(r"[a-z][a-z0-9._-]{0,39}", cmd)):
        errors.append("agent.command is the program's name, which the pack's layout.bin puts on PATH")
    out["command"] = str(cmd or "")
    b = a.get("briefing") if isinstance(a.get("briefing"), dict) else {"how": a.get("briefing") or "none"}
    how = b.get("how")
    if how not in PACK_AGENT_BRIEFING:
        errors.append(f"agent.briefing.how is one of {', '.join(PACK_AGENT_BRIEFING)}")
    out["briefing"] = {"how": how}
    if how in ("flag-text", "flag-file"):
        if not (isinstance(b.get("flag"), str) and FLAG.fullmatch(b["flag"])):
            errors.append(f"agent.briefing.flag is the option {how} hands the briefing with, e.g. --rules")
        out["briefing"]["flag"] = str(b.get("flag") or "")
    elif how == "env-file":
        if not (isinstance(b.get("env"), str) and ENV_NAME.fullmatch(b["env"])):
            errors.append("agent.briefing.env is the variable that names the briefing's file")
        out["briefing"]["env"] = str(b.get("env") or "")
    h = a.get("hooks")
    if not isinstance(h, dict):
        errors.append("agent.hooks is an object: file, shape, payload and events (pre, prompt and stop at least): an agent that cannot take AerieOS's guards is not listed")
        h = {}
    if not (isinstance(h.get("file"), str) and REL.fullmatch(h["file"])):
        errors.append("agent.hooks.file is its hooks file's path under the account's home, e.g. .foo/hooks/builderbot.json")
    document, paths, answers = _hooks_data(h, errors)
    if h.get("document") is None and h.get("shape") not in PACK_AGENT_SHAPES:
        errors.append(f"agent.hooks.shape is one of {', '.join(PACK_AGENT_SHAPES)}, or agent.hooks.document lays the file out")
    elif h.get("document") is not None and h.get("shape") not in (None, ""):
        errors.append("agent.hooks names a shape or lays its file out as document, not both")
    if not isinstance(h.get("payload"), dict) and h.get("payload") not in PACK_AGENT_PAYLOADS:
        errors.append(f"agent.hooks.payload is one of {', '.join(PACK_AGENT_PAYLOADS)}, or the paths its payload keeps each thing at")
    evs = h.get("events") if isinstance(h.get("events"), dict) else {}
    for k in evs:
        if k not in PACK_AGENT_EVENTS:
            errors.append(f"agent.hooks.events.{k} is not one of AerieOS's: {', '.join(PACK_AGENT_EVENTS)}")
        elif not (isinstance(evs[k], str) and EVENT_NAME.fullmatch(evs[k])):
            errors.append(f"agent.hooks.events.{k} is the agent's own name for that event")
    missing = [k for k in PACK_AGENT_NEEDS if k not in evs]
    if missing:
        errors.append(f"agent.hooks.events names no {', '.join(missing)}: an agent that cannot take AerieOS's guards is not listed")
    tools = h.get("tools") if isinstance(h.get("tools"), dict) else {}
    for k, v in tools.items():
        if k not in ("shell", "edit", "grep") or not (isinstance(v, list) and len(v) <= 8 and all(isinstance(t, str) and TOOL_NAME.fullmatch(t) for t in v)):
            errors.append("agent.hooks.tools maps shell, edit and grep to the agent's own tool names")
    fires = h.get("prompt_fires", "once")
    if fires not in PACK_AGENT_PROMPT_FIRES:
        errors.append(f"agent.hooks.prompt_fires is one of {', '.join(PACK_AGENT_PROMPT_FIRES)}")
    elif fires == "each-call" and not answers:
        errors.append("agent.hooks.prompt_fires each-call is for an agent answered from hooks.answers")
    # What only an answer can do is asked of an adapter that says the answer.
    if how == "hook" and not any((answers or {}).get(ev, {}).get("say") for ev in ("start", "prompt")):
        errors.append("agent.briefing.how hook needs hooks.answers to say how words reach the model at a start or on a prompt (a say)")
    out["hooks"] = {"file": str(h.get("file") or ""), "shape": h.get("shape") or "", "payload": paths or h.get("payload"),
                    "events": {k: v for k, v in evs.items() if k in PACK_AGENT_EVENTS},
                    "tools": {k: list(v) for k, v in tools.items() if k in ("shell", "edit", "grep") and isinstance(v, list)}}
    if document:
        out["hooks"]["document"] = document
    if answers:
        out["hooks"]["answers"] = answers
    if fires == "each-call":
        out["hooks"]["prompt_fires"] = fires
    env = a.get("env") if a.get("env") is not None else {}
    if not (isinstance(env, dict) and len(env) <= 8 and all(ENV_NAME.fullmatch(str(k)) and isinstance(v, str) and re.fullmatch(r"[A-Za-z0-9._:,-]{0,80}", v)
                                                          for k, v in env.items())):
        errors.append("agent.env maps up to 8 NAME to plain words (an updater off, a telemetry switch), never a path or a secret")
        env = {}
    if any(k.startswith("BB_") or k in ("PATH", "HOME", "LD_PRELOAD", "LD_LIBRARY_PATH") for k in env):
        errors.append("agent.env sets none of PATH, HOME, LD_* or AerieOS's own BB_ names")
    out["env"] = dict(env)
    si = a.get("signin") if isinstance(a.get("signin"), dict) else {}
    for k, v in (("respawn", a.get("respawn")), ("signin.login", si.get("login"))):
        v = v if v is not None else []
        if not (isinstance(v, list) and len(v) <= 6 and all(isinstance(x, str) and ARG.fullmatch(x) for x in v)):
            errors.append(f"agent.{k} lists up to 6 plain words")
            v = []
        out[k.split(".")[-1]] = list(v)
    if out["login"] and out["login"][0] != out["command"]:
        errors.append("agent.signin.login runs the agent's own command, e.g. [\"foo\", \"login\"]")
    fp = a.get("first_prompt") if isinstance(a.get("first_prompt"), dict) else {"how": a.get("first_prompt") or "none"}
    if fp.get("how") not in PACK_AGENT_FIRST:
        errors.append(f"agent.first_prompt.how is one of {', '.join(PACK_AGENT_FIRST)}")
    out["first_prompt"] = {"how": fp.get("how")}
    if fp.get("how") == "flag":
        if not (isinstance(fp.get("flag"), str) and FLAG.fullmatch(fp["flag"])):
            errors.append("agent.first_prompt.flag is the option a first prompt goes after, e.g. -i")
        out["first_prompt"]["flag"] = str(fp.get("flag") or "")
    sf, se = si.get("file", ""), si.get("env", "")
    if sf and not (isinstance(sf, str) and REL.fullmatch(sf)):
        errors.append("agent.signin.file is where its sign-in is kept, under the account's home")
    if se and not (isinstance(se, str) and ENV_NAME.fullmatch(se)):
        errors.append("agent.signin.env is a variable whose presence signs it in (an API key)")
    out["signin"] = {"file": str(sf or ""), "env": str(se or "")}
    if si.get("flow") is not None:
        before = len(errors)
        flow = _signin_flow(si["flow"], out, errors)
        if flow:
            out["signin"]["flow"] = flow
        elif newer:
            # Written for a later second number of the framework than this
            # build reads (R234 step 7): a flow said in a way it does not
            # know is left out, and the agent signs in in its terminal;
            # the manifest is not refused for it.
            del errors[before:]
    _agent_allow(a, out, errors)
    if (out.get("allow") or {}).get("how") == "hook" and not ((answers or {}).get("pre") or {}).get("approve"):
        errors.append("agent.allow.how hook needs hooks.answers.pre to say how a tool is approved (an approve)")
    tr = a.get("transcripts") if isinstance(a.get("transcripts"), dict) else {}
    td, tf = tr.get("dir", ""), tr.get("file", "")
    if td and not (isinstance(td, str) and REL.fullmatch(td)):
        errors.append("agent.transcripts.dir is the folder its conversations are kept in, under the account's home")
    if tf and not (isinstance(tf, str) and re.fullmatch(r"[A-Za-z0-9._/{}-]{1,120}", tf) and "{session}" in tf and ".." not in tf):
        errors.append("agent.transcripts.file is a conversation's file under that folder, with {session} for its id")
    sk = tr.get("session_key", "") or ""
    if sk and not (isinstance(sk, str) and re.fullmatch(r"[a-z_A-Z]{1,40}", sk)):
        errors.append("agent.transcripts.session_key is the payload's field the session's id is in")
    out["transcripts"] = {"dir": str(td or ""), "file": str(tf or ""), "session_key": str(sk)}
    models = a.get("models") if a.get("models") is not None else []
    if not (isinstance(models, list) and len(models) <= 24 and all(isinstance(x, str) and re.fullmatch(r"[A-Za-z0-9._:/-]{1,60}", x) for x in models)):
        errors.append("agent.models lists up to 24 model names Start offers")
        models = []
    out["models"] = list(models)
    if models and not (isinstance(a.get("model_flag"), str) and FLAG.fullmatch(a["model_flag"])):
        errors.append("agent.model_flag is the option a model is picked with, e.g. --model")
    out["model_flag"] = str(a.get("model_flag") or "") if models else ""
    return out if len(errors) == bad else None


# A sign-in's flow as its pack describes it (R233 step 6), so the page signs
# an account in to a pack's agent as it does to a shipped one: the words a
# screen shows are plain ones, the link is named by how it starts, and what
# is typed back is a key or a short word. No pattern comes from a manifest.
FLOW_WORDS = re.compile(r"^[A-Za-z0-9][A-Za-z0-9 .,:;'()/&-]{1,79}$")
FLOW_URL = re.compile(r"^https://[a-z0-9][a-z0-9-]{0,62}(?:\.[a-z0-9][a-z0-9-]{0,62}){1,6}(?:/[A-Za-z0-9._~/-]{0,120})?$")
FLOW_SEND = re.compile(r"^[A-Za-z0-9]{0,8}$")


def _signin_flow(f, out, errors):
    """A pack agent's sign-in flow checked and cut down to what the node's
    driver reads (scripts/lib/login-flow.py), or None: `url` is how the link
    it prints starts; `prompt` the words it waits at for the code the
    provider's page hands back, or `code_after` the words a one-time code
    follows, for one typed on the provider's page; `refused` the words it
    shows when it does not take a code; `answers` what it asks
    before the link, each the words it shows and what is typed (Enter
    follows); `kept` the file under the account's home whose arrival says
    it is signed in, which is sealed where a node seals sign-ins and removed
    on a sign-out unless `logout` names its own command."""
    if not isinstance(f, dict):
        errors.append("agent.signin.flow is an object: url, prompt or code_after, answers, kept")
        return None
    bad = len(errors)
    if not out.get("login"):
        errors.append("agent.signin.flow is run by agent.signin.login, the command that starts its sign-in")
    # How its link starts, or the few ways it may (a program that signs in
    # at one of several hosts): each https and its host.
    url = f.get("url")
    urls = url if isinstance(url, list) else [url]
    if not (1 <= len(urls) <= 4 and all(isinstance(u, str) and FLOW_URL.fullmatch(u) for u in urls)):
        errors.append("agent.signin.flow.url is how the link it prints starts: https and its host, e.g. https://auth.example.com/, or up to 4 of them")
    # How the flow ends: by the kept file's arrival, for a program that stays
    # up once signed in (its first-run screens are the person's own), or by
    # the program ending itself, signed in when it says so by its exit.
    ends = f.get("ends", "kept")
    if ends not in ("kept", "exit"):
        errors.append("agent.signin.flow.ends is kept (the kept file's arrival ends it) or exit (the program ends itself once signed in)")
    words = {}
    for k in ("prompt", "code_after", "refused"):
        v = f.get(k, "")
        if v and not (isinstance(v, str) and FLOW_WORDS.fullmatch(v)):
            errors.append(f"agent.signin.flow.{k} is the plain words its screen shows there, 2 to 80 of them")
            v = ""
        words[k] = str(v or "")
    if bool(words["prompt"]) == bool(words["code_after"]):
        errors.append("agent.signin.flow names prompt (where a code is pasted back) or code_after (a code typed on the provider's page), one of them")
    answers = f.get("answers") if f.get("answers") is not None else []
    if not (isinstance(answers, list) and len(answers) <= 4 and all(
            isinstance(a, dict) and isinstance(a.get("when"), str) and FLOW_WORDS.fullmatch(a["when"])
            and isinstance(a.get("send", ""), str) and FLOW_SEND.fullmatch(a.get("send", "")) for a in answers)):
        errors.append("agent.signin.flow.answers lists up to 4 of {when, send}: the words a screen shows and the key or short word typed there, Enter after it")
        answers = []
    kept = f.get("kept")
    if not (isinstance(kept, str) and REL.fullmatch(kept)):
        errors.append("agent.signin.flow.kept is the file its sign-in is kept in, under the account's home")
        kept = ""
    logout = f.get("logout") if f.get("logout") is not None else []
    if not (isinstance(logout, list) and len(logout) <= 6 and all(isinstance(x, str) and ARG.fullmatch(x) for x in logout)) \
            or (logout and logout[0] != out.get("command")):
        errors.append("agent.signin.flow.logout runs the agent's own command, e.g. [\"foo\", \"logout\"]; left out, a sign-out removes the kept file")
        logout = []
    if len(errors) != bad:
        return None
    return {"url": url, "prompt": words["prompt"], "code_after": words["code_after"], "refused": words["refused"],
            "answers": [{"when": a["when"], "send": a.get("send", "")} for a in answers], "kept": kept, "logout": list(logout),
            **({"ends": "exit"} if ends == "exit" else {})}


def _agent_uses(a):
    """What a cleaned adapter uses that a second number of the framework
    brought, each (version, what it is)."""
    flow = ((a or {}).get("signin") or {}).get("flow")
    if not flow:
        return []
    out = [((2, 1), "its agent's signin.flow")]
    if flow.get("ends") == "exit":
        out.append(((2, 2), "signin.flow.ends"))
    if isinstance(flow.get("url"), list):
        out.append(((2, 2), "signin.flow.url as a list"))
    return out


def _agent_format(a):
    """The pack format a cleaned adapter needs: 2 when it describes its own
    protocol or uses what came with that (R234 step 3), else 1."""
    h = a.get("hooks") or {}
    two = h.get("document") or isinstance(h.get("payload"), dict) or h.get("answers") or h.get("prompt_fires") \
        or "start" in (h.get("events") or {}) or (a.get("briefing") or {}).get("how") == "hook" or (a.get("allow") or {}).get("how") == "hook"
    return 2 if two else 1


def _config(c, errors, depth=0):
    """The config block checked: a list of fields, each {name, label, kind,
    help, required, env, choices (choice), fields (list)}; [] with the
    errors said."""
    if not isinstance(c, list) or len(c) > 24:
        errors.append("config is a list of up to 24 fields, each {name, label, kind, help, required}")
        return []
    out, seen = [], set()
    for f in c:
        if not isinstance(f, dict):
            errors.append("a config field is an object")
            continue
        name, kind = str(f.get("name") or ""), str(f.get("kind") or "text")
        if not CONFIG_NAME.fullmatch(name) or name in seen:
            errors.append(f"config field {name or '(unnamed)'}: name is 1 to 40 of a-z, 0-9, - and _, starting with a letter, and once")
            continue
        seen.add(name)
        if kind not in CONFIG_KINDS or (kind in ("list", "projects") and depth):
            errors.append(f"config field {name}: kind is one of {', '.join(CONFIG_KINDS)}" + (" (not inside a list)" if depth else ""))
            continue
        field = {"name": name, "kind": kind, "label": str(f.get("label") or name)[:60], "help": str(f.get("help") or "")[:200],
                 "required": f.get("required") is True}
        # Whose the value is (R172 step 5): the node's (one for everybody
        # there), or each person's own on that node, kept under their key.
        scope = str(f.get("scope") or "node")
        if scope not in ("node", "person") or (depth and scope != "node"):
            errors.append(f"config field {name}: scope is node or person" + (" (a list's rows are the list's)" if depth else ""))
            continue
        if scope == "person":
            field["scope"] = "person"
        env = str(f.get("env") or "")
        if env and not ENV_NAME.fullmatch(env):
            errors.append(f"config field {name}: env is a NAME a verb reads it as")
        elif env:
            field["env"] = env
        if kind == "choice":
            ch = f.get("choices")
            if not isinstance(ch, list) or not ch or not all(isinstance(x, dict) and str(x.get("value") or "") for x in ch):
                errors.append(f"config field {name}: choices lists {{value, label}}")
                continue
            field["choices"] = [{"value": str(x["value"])[:60], "label": str(x.get("label") or x["value"])[:60]} for x in ch[:24]]
        if kind == "list":
            sub_errors = []
            field["fields"] = _config(f.get("fields"), sub_errors, depth + 1)
            if sub_errors or not field["fields"]:
                errors.append(f"config field {name}: a list names the fields of each row: " + "; ".join(sub_errors or ["none"]))
                continue
        out.append(field)
    return out


def validate(m, shipped=()):
    """A manifest checked and cut down to what AerieOS reads: (clean,
    errors). Nothing in it is run here; the errors say what to fix. An
    official pack (tier official, R169 step 1) may carry a shipped
    toolchain's recipe or an agent's adapter in place of install steps and
    verbs, and may take a shipped name, being the shipped thing itself."""
    errors = []
    if not isinstance(m, dict):
        return None, [f"{MANIFEST} is a JSON object"]
    # The format it needs (R234), said before anything else is read: a
    # manifest of a format this build has not met is not judged by rules
    # written before it, so it is refused in one sentence, never a list.
    fmt = packformat.of(m)
    if fmt is None:
        return None, ["format is the pack format the manifest needs, a whole number from 1 (left out, it is 1)"]
    if fmt > packformat.FORMAT:
        return None, [f"{str(m.get('name') or 'this pack')} {packformat.too_new(fmt)}"]
    tier = str(m.get("tier") or "url")
    if tier not in TIERS:
        errors.append(f"tier is one of {', '.join(TIERS)}")
    official = tier == "official"
    name = str(m.get("name") or "")
    # A shipped toolchain's name may carry a colon (android:emulator), the
    # store's own family form; a person's pack never does.
    if not (NAME_OFFICIAL if official else NAME).fullmatch(name):
        errors.append("name is 2 to 40 of a-z, 0-9 and -, starting with a letter")
    elif name in shipped and not official:
        errors.append(f"{name} is a toolchain AerieOS ships; a pack takes a name of its own")
    elif name in BB_TOOL_WORDS and not official:
        errors.append(f"{name} is one of aerie tool's own words; a pack takes a name of its own")
    out: dict = {"name": name, "tier": tier, "format": fmt,
           "label": str(m.get("label") or name)[:80],
           "about": str(m.get("about") or "")[:400]}
    if official and isinstance(m.get("shipped"), dict):
        out["shipped"] = m["shipped"]
    elif m.get("shipped") is not None:
        errors.append("shipped (a toolchain's recipe) is an official pack's alone")
    if m.get("agent") is not None:
        if not official:
            a = _pack_agent(name, m["agent"], errors, newer=(packformat.framework_of(m) or (0, 0))[1] > packformat.MINOR)
            if a:
                out["pack_agent"] = a
                # What it uses says the format it needs, and the manifest
                # says that number: an install that reads only an earlier
                # one then knows the entry is past it without fetching it.
                needs = _agent_format(a)
                if needs > fmt:
                    errors.append(f"what its agent says of its own hooks is pack format {needs}'s: the manifest says \"format\": {needs}")
        else:
            a = _agent(m["agent"], errors)
            if a:
                out["agent"] = a
    # A deployed thing (R172): the model router, deployed and configured
    # from its card; an official pack's alone, like an agent's adapter.
    if m.get("service") is not None:
        sv = m["service"] if isinstance(m["service"], dict) else {}
        if not official:
            errors.append("service (a deployed thing of AerieOS's) is an official pack's alone")
        elif str(sv.get("kind") or "") not in SERVICES:
            errors.append(f"service.kind is one of {', '.join(SERVICES)}")
        else:
            out["service"] = {"kind": str(sv["kind"])}
    if m.get("config") is not None:
        out["config"] = _config(m["config"], errors)
    stands_in = "shipped" in out or "agent" in out or "service" in out or "pack_agent" in out
    plats = m.get("platforms") or []
    if not isinstance(plats, list) or not plats or not all(isinstance(p, str) and PLATFORM.fullmatch(p) for p in plats):
        # The wildcard named too, in the form the rule takes (B111): a bare
        # "*" is refused, since a platform is matched as os/arch on a node.
        errors.append("platforms lists where it works as os/arch, e.g. [\"linux/amd64\", \"linux/arm64\"], "
                      "or linux/* or darwin/* for any architecture of that system")
    out["platforms"] = [p for p in plats if isinstance(p, str)] if isinstance(plats, list) else []
    terms = m.get("terms") or []
    if not isinstance(terms, list) or not all(isinstance(t, dict) and t.get("label") for t in terms):
        errors.append("terms lists what it is under, each {label, url}")
        terms = []
    out["terms"] = [{"label": str(t["label"])[:120], "url": str(t.get("url") or "")[:300]} for t in terms]
    # Who the tool is by, and each of them where it carries several makers'
    # (packformat.maker_of): said wrong is said, not dropped in silence.
    if m.get("maker") is not None and not packformat.maker_of(m):
        errors.append(f"maker is who the tool is by, an organization or a person: one line of up to {packformat.MAKER_MAX} plain characters")
    if m.get("credits") is not None and (not isinstance(m["credits"], list) or len(packformat.credits_of(m)) != len(m["credits"])):
        errors.append(f"credits lists up to {packformat.CREDITS_MAX} of {{name, maker}}: each tool the pack carries and who it is by")
    out["maker"], out["credits"] = packformat.maker_of(m), packformat.credits_of(m)
    # The framework's version it is written for (packformat): what it uses
    # must be in the version it says. A coding agent's part is added to this
    # once its adapter is read, below.
    out["framework"] = packformat.said(packformat.framework_of(m) or (fmt, 0))
    # What it touches (R169 step 4): the hosts its install fetches from and
    # whether it needs root on the node, said on Look before it is added; a
    # pack that needs root is an administrator's to add.
    tch = m.get("touches") if m.get("touches") is not None else {}
    if not isinstance(tch, dict):
        errors.append("touches is an object: hosts (the names its install fetches from) and root (true or false)")
        tch = {}
    hosts = tch.get("hosts") or []
    if not isinstance(hosts, list) or len(hosts) > 16 or not all(isinstance(h, str) and re.fullmatch(r"[a-z0-9]([a-z0-9.-]{0,251}[a-z0-9])?", h) for h in hosts):
        errors.append("touches.hosts lists up to 16 host names an install fetches from, e.g. [\"github.com\"]")
        hosts = []
    if tch.get("root") not in (None, True, False):
        errors.append("touches.root is true or false")
    out["touches"] = {"hosts": hosts, "root": tch.get("root") is True}
    # The AerieOS versions it works with (R169 step 6), by release line
    # ("0.9", "0.10"); none named, every one. Checked before it is added and
    # said on the bell when this install moves to a line it does not name.
    ww = m.get("works_with") if m.get("works_with") is not None else []
    if not isinstance(ww, list) or len(ww) > 16 or not all(isinstance(x, str) and re.fullmatch(r"\d{1,3}\.\d{1,3}", x) for x in ww):
        errors.append("works_with lists the AerieOS release lines it works with, e.g. [\"0.9\", \"0.10\"]")
        ww = []
    out["works_with"] = ww
    inst = m.get("install") or {}
    if not isinstance(inst, dict):
        errors.append("install is an object: steps (each a list of words) and verify")
        inst = {}
    steps = []
    for i, s in enumerate(inst.get("steps") or []):
        w = _words(s, f"install step {i + 1}", errors, ("{dir}",))
        if w:
            steps.append(w)
    out["steps"] = steps
    out["verify"] = _words(inst["verify"], "install verify", errors, ("{dir}",)) if inst.get("verify") else None
    lay = m.get("layout") or {}
    if not isinstance(lay, dict):
        errors.append("layout is an object: bin, env and tool")
        lay = {}
    rel = REL_OFFICIAL if official else REL
    bins = lay.get("bin") or []
    if not isinstance(bins, list) or not all(isinstance(b, str) and rel.fullmatch(b) for b in bins):
        errors.append("layout.bin lists directories inside the pack to put on PATH")
        bins = []
    tool = lay.get("tool") or ""
    if tool and not (isinstance(tool, str) and rel.fullmatch(tool)):
        errors.append("layout.tool is a file inside the pack whose presence says it is installed")
        tool = ""
    env = lay.get("env") or {}
    if not isinstance(env, dict) or not all(re.fullmatch(r"[A-Z][A-Z0-9_]{0,40}", k) and isinstance(v, str)
                                            for k, v in env.items()):
        errors.append("layout.env maps NAME to a path inside the pack (\"\" for the pack itself) or =VALUE")
        env = {}
    out["layout"] = {"bin": bins, "env": env, "tool": tool or MANIFEST}
    # System packages per package manager (R171), as the shipped recipes
    # carry them: the node's family script installs its own manager's list,
    # and a node whose manager the pack names none for is not offered it.
    sysd = m.get("system") if isinstance(m.get("system"), dict) else {}
    keep = {}
    for mgr, shape in SYSTEM_NAMES.items():
        names = sysd.get(mgr)
        if names is None:
            continue
        if not (isinstance(names, list) and len(names) <= 60 and all(isinstance(a, str) and shape.fullmatch(a) for a in names)):
            errors.append(f"system.{mgr} lists {SYSTEM_WORDS[mgr]} package names")
            continue
        if names:
            keep[mgr] = names
    for mgr in sysd:
        if mgr not in SYSTEM_NAMES:
            errors.append(f"system.{mgr} is not a package manager a node runs: {', '.join(SYSTEM_NAMES)}")
    if keep:
        out["system"] = keep
    verbs = m.get("verbs") or {}
    if not isinstance(verbs, dict) or (not verbs and not stands_in):
        errors.append("verbs names at least one command a session calls, each {about, usage, run}")
        verbs = {}
    out["verbs"] = {}
    for v, spec in verbs.items():
        if not VERB.fullmatch(str(v)):
            errors.append(f"verb {v!r}: a-z, 0-9 and -, starting with a letter")
            continue
        if not isinstance(spec, dict):
            errors.append(f"verb {v} is an object: about, usage and run")
            continue
        w = _words(spec.get("run"), f"verb {v}'s run", errors)
        if not w:
            continue
        first = w[0]
        # The program a verb runs is the pack's own: a file inside its
        # directory, or a script the pack carries run by sh or python3.
        inside = first.startswith("{dir}/") and REL.fullmatch(first[6:])
        script = first in ("sh", "bash", "python3") and len(w) > 1 and w[1].startswith("{dir}/") \
            and REL.fullmatch(w[1][6:])
        if not (inside or script):
            errors.append(f"verb {v} runs {first}: a verb runs a file inside the pack ({{dir}}/...), "
                          "or sh, bash or python3 on a script inside it")
            continue
        out["verbs"][v] = {"about": str(spec.get("about") or "")[:300],
                           "usage": str(spec.get("usage") or "")[:200], "run": w}
    g = m.get("guidance") or ""
    if g and not (isinstance(g, str) and REL.fullmatch(g)):
        errors.append("guidance names a Markdown file inside the pack")
        g = ""
    out["guidance_file"] = g
    ic = m.get("icon") or ""
    if ic and not (isinstance(ic, str) and REL.fullmatch(ic) and ic.rsplit(".", 1)[-1].lower() in ICON_TYPES):
        errors.append("icon names a PNG, WebP or SVG file inside the pack")
        ic = ""
    out["icon"] = ic
    # What it uses is in the framework version it says (R234 step 7): the
    # number on a manifest is what an install has to know to do all of it.
    errors.extend(packformat.needs(m, [*packformat.uses_of(m), *_agent_uses(out.get("pack_agent"))]))
    return (out if not errors else None), errors


def _git(args, cwd=None, timeout=FETCH_TIMEOUT):
    env = dict(os.environ, GIT_TERMINAL_PROMPT="0")
    return subprocess.run(["git", *args], cwd=cwd, capture_output=True, text=True,
                          timeout=timeout, env=env, check=False)


PATH_IN = re.compile(r"[a-z0-9][\w./-]{0,120}")


mirror_bundle = None    # catalogmirror.bundle(url, commit): the imported mirror's bundle holding it, or None


def _source(url, commit):
    """Where a fetch reads `url` at `commit` (its head when none): the
    imported catalog mirror's bundle when it holds that commit (R169 step 6),
    nothing going to the network, else the repository itself, shallow."""
    b = mirror_bundle(url, commit) if mirror_bundle and commit else None
    if b:
        return [b, f"refs/pins/{commit}"]
    return ["--depth", "1", url, commit or "HEAD"]


def fetch(url, commit="", shipped=(), sha256="", path=""):
    """The repository at `commit` (its default branch's head when none):
    {commit, manifest, guidance} with the manifest validated, or {error}.
    Fetched into a scratch directory that is gone when this returns. With
    `sha256` (the catalog's, of the archive at that commit, R169 step 4)
    the archive is made and compared, and a difference refuses the pack:
    git's own hashes pin the commit, this pins what the maintainers saw."""
    url = str(url or "").strip()
    # A suite's pack is a repository on disk (BB_TOOLPACKS_FILE_URLS=1); a
    # controller only ever fetches one over the network.
    local = os.environ.get("BB_TOOLPACKS_FILE_URLS") == "1" and url.startswith("file:///")
    if not (URL.fullmatch(url) or local):
        return {"error": "a pack is a git repository's address: https://host/owner/repo"}
    if commit and not re.fullmatch(r"[0-9a-f]{40}", commit):
        return {"error": "a commit is its full 40-character hash"}
    # A pack in a folder of the repository (R170 step 6): the archive and
    # the manifest are that folder's.
    path = str(path or "").strip("/")
    if path and (not PATH_IN.fullmatch(path) or ".." in path.split("/")):
        return {"error": "a pack's folder is a plain relative path inside the repository"}
    at = f"{path}/" if path else ""
    tmp = tempfile.mkdtemp(prefix="toolpack-")
    try:
        for args in (["init", "-q", tmp], ["-C", tmp, "fetch", "-q", *_source(url, commit)]):
            try:
                r = _git(args)
            except subprocess.TimeoutExpired:
                return {"error": f"{url} did not answer within {FETCH_TIMEOUT}s"}
            if r.returncode != 0:
                said = (r.stderr or r.stdout).strip().splitlines()
                return {"error": f"could not fetch {url}: {said[-1] if said else 'git failed'}"}
        got = _git(["-C", tmp, "rev-parse", "FETCH_HEAD"]).stdout.strip()
        if commit and got != commit:
            return {"error": f"{url} answered {got[:12]} where {commit[:12]} was asked"}
        if sha256:
            if not re.fullmatch(r"[0-9a-f]{64}", sha256):
                return {"error": "the catalog's sha256 is 64 hex digits"}
            import hashlib  # noqa: PLC0415
            r = subprocess.run(["git", "-C", tmp, "archive", "--format=tar", "FETCH_HEAD", *([path] if path else [])], capture_output=True, timeout=120, check=False)
            if r.returncode != 0 or hashlib.sha256(r.stdout).hexdigest() != sha256:
                return {"error": f"{url} at {got[:12]} is not what the catalog vetted: its archive's sha256 differs, so it is refused"}

        def read(rel, cap):
            r = subprocess.run(["git", "-C", tmp, "show", f"FETCH_HEAD:{at}{rel}"], capture_output=True,
                               timeout=30, check=False)
            if r.returncode != 0:
                return None
            return r.stdout[:cap + 1]
        got_m = _examine(read, shipped, f"{url} has no {MANIFEST} at {('its ' + path) if path else 'its root'}")
        if got_m.get("error"):
            return {**got_m, "commit": got} if got_m.get("errors") else got_m
        return {"commit": got, **got_m, "plain": url.startswith("http://"), "path": path}
    finally:
        shutil.rmtree(tmp, ignore_errors=True)


def fetch_folder(url, commit, sha256, path, files, cap=256 << 10):
    """A catalog entry's folder at the commit it pins (R170 step 7: an app's
    bbapp.json and compose.yml), its archive's sha256 checked as a pack's
    is: {files: {name: bytes}} or {error}. Only the files named are read."""
    url = str(url or "").strip()
    local = os.environ.get("BB_TOOLPACKS_FILE_URLS") == "1" and url.startswith("file:///")
    if not (URL.fullmatch(url) or local):
        return {"error": "a catalog entry is a git repository's address: https://host/owner/repo"}
    if not re.fullmatch(r"[0-9a-f]{40}", str(commit or "")) or not re.fullmatch(r"[0-9a-f]{64}", str(sha256 or "")):
        return {"error": "a catalog entry pins a full commit and its archive's sha256"}
    path = str(path or "").strip("/")
    if not path or not PATH_IN.fullmatch(path) or ".." in path.split("/"):
        return {"error": "a catalog entry's folder is a plain relative path inside the repository"}
    tmp = tempfile.mkdtemp(prefix="catalog-")
    try:
        for args in (["init", "-q", tmp], ["-C", tmp, "fetch", "-q", *_source(url, commit)]):
            try:
                r = _git(args)
            except subprocess.TimeoutExpired:
                return {"error": f"{url} did not answer within {FETCH_TIMEOUT}s"}
            if r.returncode != 0:
                said = (r.stderr or r.stdout).strip().splitlines()
                return {"error": f"could not fetch {url}: {said[-1] if said else 'git failed'}"}
        if _git(["-C", tmp, "rev-parse", "FETCH_HEAD"]).stdout.strip() != commit:
            return {"error": f"{url} did not answer with {commit[:12]}"}
        import hashlib  # noqa: PLC0415
        r = subprocess.run(["git", "-C", tmp, "archive", "--format=tar", "FETCH_HEAD", path], capture_output=True, timeout=120, check=False)
        if r.returncode != 0 or hashlib.sha256(r.stdout).hexdigest() != sha256:
            return {"error": f"{url} at {commit[:12]} is not what the catalog vetted: its archive's sha256 differs, so it is refused"}
        out = {}
        for name in files:
            g = subprocess.run(["git", "-C", tmp, "show", f"FETCH_HEAD:{path}/{name}"], capture_output=True, timeout=30, check=False)
            if g.returncode != 0:
                return {"error": f"{url} has no {name} in {path}"}
            if len(g.stdout) > cap:
                return {"error": f"{path}/{name} is over {cap // 1024} KB"}
            out[name] = g.stdout
        return {"files": out}
    finally:
        shutil.rmtree(tmp, ignore_errors=True)


def _examine(read, shipped, missing):
    """The manifest and guidance a pack's files hold, read through `read(rel,
    cap)`: {manifest, guidance} validated, or {error}. One reading for a
    repository and a pack made here."""
    raw = read(MANIFEST, MANIFEST_MAX)
    if raw is None:
        return {"error": missing}
    if len(raw) > MANIFEST_MAX:
        return {"error": f"{MANIFEST} is over {MANIFEST_MAX // 1024} KB"}
    try:
        m = json.loads(raw.decode("utf-8"))
    except (ValueError, UnicodeDecodeError) as e:
        return {"error": f"{MANIFEST} is not JSON: {e}"}
    clean, errors = validate(m, shipped)
    if errors:
        return {"error": f"{MANIFEST} needs fixing: " + "; ".join(errors), "errors": errors}
    guidance = ""
    if clean["guidance_file"]:
        g = read(clean["guidance_file"], GUIDANCE_MAX)
        if g is None:
            return {"error": f"{MANIFEST} names {clean['guidance_file']} as its guidance, and it is not there"}
        guidance = g[:GUIDANCE_MAX].decode("utf-8", "replace")
    icon = None
    if clean.get("icon"):
        raw = read(clean["icon"], ICON_MAX)
        if raw is None:
            return {"error": f"{MANIFEST} names {clean['icon']} as its icon, and it is not there"}
        ext = clean["icon"].rsplit(".", 1)[-1].lower()
        why = icon_refused(raw, ext)
        if why:
            return {"error": f"{clean['icon']}: {why}"}
        icon = (raw, ext)
    return {"manifest": clean, "guidance": guidance, **({"icon_bytes": icon} if icon else {})}


def icon_refused(raw, ext):
    """Why an icon's bytes are not the image its name says, or "": a PNG's
    and a WebP's signature, an SVG that is a document with an svg element,
    and the size cap."""
    if len(raw) > ICON_MAX:
        return f"an icon is {ICON_MAX // 1024} KB at most"
    if ext == "png" and not raw.startswith(b"\x89PNG\r\n\x1a\n"):
        return "not a PNG image"
    if ext == "webp" and not (raw[:4] == b"RIFF" and raw[8:12] == b"WEBP"):
        return "not a WebP image"
    if ext == "svg":
        head = raw[:4096].decode("utf-8", "replace").lower()
        if "<svg" not in head:
            return "not an SVG image"
    return ""


def icon_dir():
    return Path(FILE).parent / "pack-icons" if FILE else None


def _keep_icon(name, got):
    """The icon a pack's files carry, kept under the state by the pack's name
    (one file, any older one of another type gone); its type, or "" for
    none."""
    d = icon_dir()
    if not d or not NAME.fullmatch(name):
        return ""
    for e in ICON_TYPES:
        (d / f"{name}.{e}").unlink(missing_ok=True)
    ic = got.get("icon_bytes")
    if not ic:
        return ""
    raw, ext = ic
    d.mkdir(parents=True, exist_ok=True)
    tmp = d / f".{name}.{ext}.new"
    tmp.write_bytes(raw)
    tmp.replace(d / f"{name}.{ext}")
    return ext


def icon_of(name):
    """(bytes, content type) of a kept pack's icon, or None."""
    d = icon_dir()
    if not d or not NAME.fullmatch(str(name or "")):
        return None
    for e, ct in ICON_TYPES.items():
        f = d / f"{name}.{e}"
        if f.is_file():
            try:
                return f.read_bytes(), ct
            except OSError:
                return None
    return None


# ---- a pack made here ------------------------------------------------------

def _staging():
    return HOSTED / "staging"


def _sweep_staging():
    now = time.time()
    for d in _staging().iterdir() if _staging().is_dir() else []:
        try:
            if now - d.stat().st_mtime > STAGE_TTL:
                shutil.rmtree(d, ignore_errors=True)
        except OSError:
            pass


def _files_in(d):
    """Every file under `d` as a relative path, .git left out."""
    return sorted(str(f.relative_to(d)) for f in d.rglob("*")
                  if f.is_file() and ".git" not in f.relative_to(d).parts)


def _read_in(d):
    def read(rel, cap):
        if not REL.fullmatch(rel):
            return None
        f = d / rel
        try:
            with open(f, "rb") as fh:
                return fh.read(cap + 1)
        except OSError:
            return None
    return read


def stage(text=None, archive="", shipped=()):
    """A pack made here, from a pasted manifest or an uploaded archive (the
    New project dialog's upload, spooled by projects.spool_archive): its
    files checked and held for Add, as {staged, manifest, guidance, files},
    or {error}. Nothing is kept as a pack until somebody presses Add."""
    _staging().mkdir(parents=True, exist_ok=True)
    _sweep_staging()
    tok = secrets.token_hex(8)
    d = _staging() / tok
    d.mkdir()
    out = _stage_into(d, text, archive, shipped)
    if out.get("error"):
        shutil.rmtree(d, ignore_errors=True)
        return out
    return {**out, "staged": tok}


def _stage_into(d, text, archive, shipped):
    """The files of a pack made here, put in `d` and checked."""
    if archive:
        if not unpack:
            return {"error": "uploads are not open here"}
        got = unpack(archive, d)
        if got.get("error"):
            return {"error": got["error"]}
        # A repository's own history is not the pack's: what is kept is
        # this version's files, as a commit made here.
        shutil.rmtree(d / ".git", ignore_errors=True)
        where = "the upload"
    else:
        raw = str(text or "")
        if not raw.strip():
            return {"error": f"paste a {MANIFEST}, or upload the pack's files"}
        if len(raw.encode("utf-8")) > MANIFEST_MAX:
            return {"error": f"{MANIFEST} is over {MANIFEST_MAX // 1024} KB"}
        (d / MANIFEST).write_text(raw, encoding="utf-8")
        where = "what was pasted"
    files = _files_in(d)
    size = sum((d / f).stat().st_size for f in files)
    if len(files) > HOSTED_FILES or size > HOSTED_MAX:
        return {"error": f"a pack made here is at most {HOSTED_MAX >> 20} MB in {HOSTED_FILES} files, "
                         "since every node carries it; fetch what is bigger in its install steps"}
    got = _examine(_read_in(d), shipped, f"{where} has no {MANIFEST} at its top")
    if got.get("error"):
        return got
    return {**got, "files": files[:200], "nfiles": len(files), "here": True}


def _git_here(name, *args, work=None):
    repo = HOSTED / f"{name}.git"
    pre = ["--git-dir", str(repo)] + (["--work-tree", str(work)] if work else [])
    return _git([*AUTHOR, *pre, *args])


def add_staged(staged, by, shipped=(), may_root=False):
    """Keep a pack made here, as the version that was looked at: committed
    to its repository on this controller, its bundle written for the nodes.
    A pack of the same name made here is updated; one from a repository is
    not replaced by it."""
    if not STAGE_ID.fullmatch(str(staged or "")) or not (_staging() / staged).is_dir():
        return {"error": "that upload has gone (they are kept for thirty minutes); paste or upload it again"}
    d = _staging() / staged
    try:
        got = _examine(_read_in(d), shipped, f"no {MANIFEST} at the top")
        if got.get("error"):
            return got
        m = got["manifest"]
        name = m["name"]
        if (m.get("touches") or {}).get("root") and not may_root:
            return {"error": f"{name}: {ROOT_REFUSED}"}
        if not fits(m):
            return {"error": _unfit_why(m)}
        with _lock:
            data = _load()
            was = data["packs"].get(name)
            if was and not was.get("hosted"):
                return {"error": f"a pack called {name} is already here from {was.get('url')}; remove it first"}
            repo = HOSTED / f"{name}.git"
            if not repo.is_dir():
                r = _git(["init", "-q", "--bare", "-b", "main", str(repo)])
                if r.returncode != 0:
                    return {"error": f"could not make {name}'s repository: {(r.stderr or '').strip()}"}
            had = _git_here(name, "rev-parse", "-q", "--verify", "refs/heads/main").stdout.strip()
            for args in (["read-tree", "--empty"], ["add", "-A", "."]):
                r = _git_here(name, *args, work=d)
                if r.returncode != 0:
                    return {"error": f"could not keep {name}: {(r.stderr or '').strip()}"}
            same = had and _git_here(name, "diff", "--cached", "--quiet", had, work=d).returncode == 0
            if not same:
                r = _git_here(name, "commit", "-q", "-m", f"{name}, as {by or 'an administrator'} approved it",
                              work=d)
                if r.returncode != 0:
                    return {"error": f"could not keep {name}: {(r.stderr or r.stdout or '').strip()}"}
            commit = _git_here(name, "rev-parse", "refs/heads/main").stdout.strip()
            r = _git_here(name, "bundle", "create", "-q", str(HOSTED / f"{name}.bundle"), "main")
            if r.returncode != 0:
                return {"error": f"could not write {name}'s bundle: {(r.stderr or '').strip()}"}
            rec = {"name": name, "url": HERE + name, "hosted": True, "commit": commit, "manifest": m,
                   "guidance": got["guidance"], "by": str(by or ""), "at": int(time.time()), "icon": _keep_icon(name, got)}
            data["packs"][name] = rec
            write_json(FILE, data)
        return {"ok": True, "pack": rec, "replaced": bool(was), "unchanged": bool(same)}
    finally:
        shutil.rmtree(d, ignore_errors=True)


def source(name):
    """A pack made here, as its bbtool.json reads at the kept version: what
    Edit puts in the paste field. {text} or {error}."""
    rec = packs().get(str(name or ""))
    if not rec or not rec.get("hosted"):
        return {"error": f"{name} is not a pack made here"}
    r = _git_here(rec["name"], "show", f"{rec['commit']}:{MANIFEST}")
    if r.returncode != 0:
        return {"error": f"{name}'s {MANIFEST} could not be read"}
    return {"text": r.stdout}


def hosted_files():
    """The packs made here as the bundle carries them, (path in the bundle,
    file here), beside config/toolpacks.json."""
    return [(f"config/toolpacks/{n}.bundle", HOSTED / f"{n}.bundle")
            for n, r in sorted(packs().items())
            if r.get("hosted") and (HOSTED / f"{n}.bundle").is_file()]


def packs():
    with _lock:
        return _load()["packs"]


# The package managers a node's family runs (provision-linux.sh's families),
# each with the shape of its package names.
SYSTEM_NAMES = {"apt": re.compile(r"[a-z0-9.+|-]{1,80}"), "dnf": re.compile(r"[A-Za-z0-9._+|-]{1,80}"),
                "pacman": re.compile(r"[a-z0-9@._+|-]{1,80}"), "zypper": re.compile(r"[A-Za-z0-9._+|-]{1,80}"),
                "apk": re.compile(r"[a-z0-9._+|-]{1,80}")}
SYSTEM_WORDS = {"apt": "Debian and Ubuntu", "dnf": "Fedora and Red Hat", "pacman": "Arch", "zypper": "openSUSE", "apk": "Alpine"}


ROOT_REFUSED = "it needs root on the node (its touches say so): an administrator adds it"
running_version = lambda: ""    # noqa: E731 (this build's version, set by the server)


def line_of(version):
    """A version's release line, "0.9" of "0.9.0-dev.4342+48b768b"; "" when it has none."""
    m = re.match(r"^v?(\d+)\.(\d+)", str(version or ""))
    return f"{m.group(1)}.{m.group(2)}" if m else ""


def fits(manifest, version=None):
    """Whether a pack's manifest names this build's release line (R169 step 6):
    True for one that names none, or a build with no version."""
    ww = (manifest or {}).get("works_with") or []
    line = line_of(running_version() if version is None else version)
    return not ww or not line or line in ww


def unfit():
    """The bell's rows (kind pack) for each pack this install holds whose
    works_with does not name the running release line."""
    line = line_of(running_version())
    out = []
    for n, r in packs().items():
        m = (r or {}).get("manifest") or {}
        if line and not fits(m):
            out.append({"kind": "pack", "name": n, "key": f"pack:unfit:{n}:{line}",
                        "said": f"the pack {n} says it works with AerieOS {', '.join(m.get('works_with') or [])}, and this is {line}: "
                                "update it from the Library, or remove it"})
    return out


def _unfit_why(m):
    line = line_of(running_version())
    return f"{m['name']} works with AerieOS {', '.join(m.get('works_with') or [])}, and this is {line}: a newer commit of it may name {line}"


def add(url, commit, by, shipped=(), sha256="", tier="url", path="", may_root=False):
    """Keep a pack pinned to `commit`, which the person approving it saw:
    the repository is fetched again at exactly that commit, so what is kept
    is what was shown. A pack of the same name is replaced (an update).
    From the vetted catalog (R169 step 4) it carries the index's sha256,
    checked on the way in, and its tier. A pack in a folder of the
    repository (`path`, R170 step 6) is kept as a pack made here: that
    folder's files at that commit, committed to its repository on this
    controller, so a node fetches the folder and nothing else."""
    got = fetch(url, commit, shipped, sha256, path)
    if got.get("error"):
        return got
    # One that needs root is an administrator's to add (R169 step 4).
    if (got.get("manifest") or {}).get("touches", {}).get("root") and not may_root:
        return {"error": f"{got['manifest']['name']}: {ROOT_REFUSED}"}
    # ...and one that does not name this release line is not added (step 6).
    if got.get("manifest") and not fits(got["manifest"]):
        return {"error": _unfit_why(got["manifest"])}
    # One from the mirror is kept hosted, its folder or its whole tree, so
    # the nodes take it from the controller and need no network either.
    if path or (mirror_bundle and mirror_bundle(url, got["commit"])):
        return _add_folder(url, got["commit"], path, by, shipped, sha256, tier)
    m = got["manifest"]
    with _lock:
        d = _load()
        rec = {"name": m["name"], "url": url, "commit": got["commit"], "manifest": m,
               "guidance": got["guidance"], "by": str(by or ""), "at": int(time.time()),
               "tier": tier if tier in packformat.TIERS and sha256 else "url", "sha256": sha256 or ""}
        was = d["packs"].get(m["name"])
        if was and was.get("url") != url:
            return {"error": f"a pack called {m['name']} is already here from {was.get('url')}; remove it first"}
        rec["icon"] = _keep_icon(m["name"], got)
        d["packs"][m["name"]] = rec
        write_json(FILE, d)
    return {"ok": True, "pack": rec, "replaced": bool(was)}


def _add_folder(url, commit, path, by, shipped, sha256, tier):
    """A folder of a repository at a commit, staged as a pack made here and
    kept, its record naming where it came from (R170 step 6)."""
    _staging().mkdir(parents=True, exist_ok=True)
    tok = secrets.token_hex(8)
    d = _staging() / tok
    d.mkdir()
    tmp = tempfile.mkdtemp(prefix="toolpack-")
    try:
        for args in (["init", "-q", tmp], ["-C", tmp, "fetch", "-q", *_source(url, commit)]):
            r = _git(args)
            if r.returncode != 0:
                return {"error": f"could not fetch {url}: {(r.stderr or r.stdout).strip().splitlines()[-1:] or 'git failed'}"}
        arc = subprocess.run(["git", "-C", tmp, "archive", "--format=tar", f"FETCH_HEAD:{path}"], capture_output=True, timeout=120, check=False)
        if arc.returncode != 0:
            return {"error": f"{url} at {commit[:12]} has no folder {path}"}
        import io  # noqa: PLC0415
        import tarfile  # noqa: PLC0415
        with tarfile.open(fileobj=io.BytesIO(arc.stdout), mode="r:") as tar:
            for ti in tar.getmembers():
                if not (ti.isfile() or ti.isdir()) or ti.name.startswith(("/", "..")) or ".." in ti.name.split("/"):
                    return {"error": f"{path} holds something a pack cannot: {ti.name}"}
            tar.extractall(d, filter="data")
    except (subprocess.TimeoutExpired, OSError, tarfile.TarError) as e:
        return {"error": f"could not take {path} from {url}: {e}"}
    finally:
        shutil.rmtree(tmp, ignore_errors=True)
    out = add_staged(tok, by, shipped)
    shutil.rmtree(d, ignore_errors=True)
    if out.get("error"):
        return out
    with _lock:
        data = _load()
        rec = data["packs"].get(out["pack"]["name"])
        if rec:
            # The record names where the folder came from and the commit the
            # catalog pins; the commit it is kept under in its repository
            # here is its own, and is what a node fetches from the bundle.
            rec.update({"url": url, "commit": commit, "path": path, "sha256": sha256 or "", "kept_at": rec.get("commit") or "",
                        "tier": tier if tier in packformat.TIERS and sha256 else "url"})
            write_json(FILE, data)
            out["pack"] = rec
    return out


def configs():
    """{pack name: its config fields} for every added pack that asks for
    any (R172), what packconfig.for_node reads the node's answers by."""
    with _lock:
        d = _load()
    return {n: r["manifest"]["config"] for n, r in d["packs"].items() if isinstance(r, dict) and (r.get("manifest") or {}).get("config")}


def where_said(name, where):
    """The refusal for removing a pack still installed (B84): its files
    would stay in those stores with no row left to uninstall them from, and
    a pack added back would read as installed with no install run."""
    return {"error": f"{name} is installed on {', '.join(where)}: uninstall it there first "
                     f"(pick that node in the Library and press Remove on its card), "
                     f"then remove the pack", "installed": list(where)}


def remove(name, where=()):
    """Take a pack out of the catalog; refused while `where` (the nodes that
    hold it) names any."""
    if where:
        return where_said(name, where)
    with _lock:
        d = _load()
        if name not in d["packs"]:
            return {"error": f"no tool pack called {name}"}
        rec = d["packs"].pop(name)
        write_json(FILE, d)
        _keep_icon(name, {})
        if rec.get("hosted") and HOSTED and NAME.fullmatch(name):
            shutil.rmtree(HOSTED / f"{name}.git", ignore_errors=True)
            (HOSTED / f"{name}.bundle").unlink(missing_ok=True)
    return {"ok": True}


def _bundle_commit(rec):
    """The commit a node fetches a pack at. One kept from a folder of a
    repository (R170 step 6) is in its repository here under a commit of
    its own, which is the one its bundle holds: the record's `kept_at`, or,
    for a record from before it said so, that repository's head. Any other
    pack's is the commit it is pinned to."""
    if rec.get("hosted") and rec.get("path"):
        if rec.get("kept_at"):
            return rec["kept_at"]
        if HOSTED and NAME.fullmatch(str(rec.get("name") or "")):
            r = _git_here(rec["name"], "rev-parse", "-q", "--verify", "refs/heads/main")
            if r.returncode == 0 and r.stdout.strip():
                return r.stdout.strip()
    return rec["commit"]


def recipe(rec):
    """A pack as one catalog row: the recipe machinery's own shape, its
    source the pack's repository cloned at the approved commit, then its
    install steps, then its verify. `pack` marks it as added, not shipped."""
    m = rec["manifest"]
    # A pack made here is fetched from the bundle beside the catalog on the
    # node (sdkmeta.packs_at makes the path whole there).
    url = f"bundle:toolpacks/{m['name']}.bundle" if rec.get("hosted") else rec["url"]
    src = {"kind": "git", "url": url, "commit": _bundle_commit(rec), "fresh_only": True}
    if m["steps"]:
        src["then"] = [{"run": s} for s in m["steps"]]
    if m.get("verify"):
        src["verify"] = m["verify"]
    # What the install marks executable (B83): a file committed through a
    # forge's web editor has no executable bit, and every run of it was
    # 'Permission denied'. The programs the verbs, the steps and verify run
    # by path, the layout's tool, and whatever is in its bin directories.
    progs = [w[0] for w in [*(v["run"] for v in m["verbs"].values()), *m["steps"], m.get("verify") or [""]]
             if w and w[0].startswith("{dir}/")]
    tool = m["layout"].get("tool")
    if tool and tool != MANIFEST:
        progs.append("{dir}/" + tool)
    src["exec"] = sorted(set(progs))
    src["exec_dirs"] = ["{dir}/" + b for b in m["layout"].get("bin") or []]
    # about is optional in a manifest, and a catalog row without one is not
    # drawn (B106): the label stands in for it.
    row = {"name": m["name"], "label": m["label"], "probe": m["name"], "about": m["about"] or m["label"],
           "platforms": m["platforms"], "layout": m["layout"], "source": src, "terms": m["terms"],
           "maker": m.get("maker") or "", "credits": m.get("credits") or [],
           "verbs": m["verbs"],
           "pack": {"url": rec["url"], "commit": rec["commit"], "path": rec.get("path", ""), "by": rec.get("by", ""), "at": rec.get("at", 0),
                    "tier": rec.get("tier") or ("here" if rec.get("hosted") else "url"),
                    "guidance": rec.get("guidance", ""),
                    # Made here: a person's own text or archive. A folder of
                    # a repository is kept hosted too, so the nodes take it
                    # from the controller, but it came from where its url
                    # says, and a page that called it made here (every pack
                    # of the catalog, each a folder of it) was wrong.
                    "here": bool(rec.get("hosted")) and str(rec.get("url") or "").startswith(HERE),
                    "agent": bool(offers_agent(rec)),
                    # Whether it carries an icon of its own (R182).
                    "icon": bool(rec.get("icon"))}}
    # A coding agent it offers, for bb-tty and bb-agent-hook on the node,
    # which read it from the bundle's config/toolpacks.json (R169 step 10).
    if offers_agent(rec):
        row["agent"] = offers_agent(rec)
    if m.get("system"):
        row["system"] = m["system"]
    if m.get("config"):
        row["config"] = m["config"]
    return row


def offers_agent(rec):
    """The coding agent an installed pack offers (R169 step 9), its adapter,
    or None: only one the vetted catalog pinned, or an official one, since
    the adapter decides what runs in every session of it."""
    m = (rec or {}).get("manifest") or {}
    return m.get("pack_agent") if m.get("pack_agent") and rec.get("tier") in packformat.TIERS else None


_offered = {"stamp": None, "rows": ()}


def offered_agents():
    """[(name, label, adapter)] for every installed pack that offers a coding
    agent, in name order; read again only when the packs' file changes, since
    every session name is asked of it."""
    try:
        st = FILE.stat() if FILE else None
        stamp = (str(FILE), st.st_mtime_ns, st.st_size) if st else None
    except OSError:
        stamp = None
    if stamp is None or stamp != _offered["stamp"]:
        rows = []
        for name, rec in sorted(packs().items()) if stamp is not None else ():
            a = offers_agent(rec)
            if a:
                rows.append((name, rec["manifest"].get("label") or name, a))
        _offered.update(stamp=stamp, rows=tuple(rows))
    return _offered["rows"]


def recipes():
    """Every pack as a catalog row, in name order."""
    return [recipe(r) for _, r in sorted(packs().items())]


def catalog_json():
    """What the bundle carries beside config/toolchains.json, for the nodes:
    "" when no pack was added, so the bundle carries no file for none."""
    rows = recipes()
    return json.dumps({"toolchains": rows}, indent=1, sort_keys=True) if rows else ""
