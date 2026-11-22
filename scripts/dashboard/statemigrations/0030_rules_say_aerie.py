"""State 29 to 30: the house rules call the command by its name.

The command was called bb before it was aerie, and no PATH carries the old
name now. Rules written before then still say bb VERB in their words, their
reasons, their checks and the commands they refuse, and every session is
handed them in its briefing: a session told to run bb tests run meets a
command that is not there, and a check that runs one fails. Each is said
with aerie where the word after bb is one of aerie's own verbs (as they are
at this migration); anything else (a host called bb-sandbox, a function
called bb_setting, a word that only follows bb) is left as it is.

Idempotent. Never edited once shipped (stateversion.py).
"""
import json
import os
import re
from pathlib import Path

VERBS = ("brief", "browser", "bug", "build", "capture", "catchup", "changelog", "ci-labels",
         "ci-log", "container", "dashboard", "design", "devapp", "diag", "doctor", "drift", "emu",
         "findings", "forge", "git", "gpu", "help", "history", "jobs", "lint", "login", "logs", "map",
         "memory", "node", "nodes", "pc", "phone", "preamble", "proc", "projects", "report", "roadmap",
         "root", "router-key", "rules", "run", "settings", "shell", "sign", "status", "test", "tests",
         "tidy", "token", "tool", "toolchains", "transcripts", "users", "version", "vm", "wiki",
         "work", "-p")
OLD = re.compile(r"(?<![\w./-])bb (?=(?:" + "|".join(re.escape(v) for v in VERBS) + r")(?![\w-]))")
FIELDS = ("text", "why", "check", "refuse")


def said(v):
    if isinstance(v, str):
        return OLD.sub("aerie ", v)
    if isinstance(v, list):
        return [said(x) for x in v]
    return v


def run(ctx):
    f = Path(ctx["state"]) / "rules.json"
    try:
        d = json.loads(f.read_text())
    except (OSError, ValueError):
        return
    projects = d.get("projects") if isinstance(d, dict) else None
    if not isinstance(projects, dict):
        return
    moved = False
    for p in projects.values():
        for r in (p.get("rules") if isinstance(p, dict) else None) or []:
            if not isinstance(r, dict):
                continue
            for k in FIELDS:
                if k in r:
                    now = said(r[k])
                    if now != r[k]:
                        r[k], moved = now, True
    if not moved:
        return
    tmp = f.with_name(f.name + ".tmp")
    tmp.write_text(json.dumps(d, indent=1))
    os.chmod(tmp, f.stat().st_mode & 0o777)
    os.replace(tmp, f)
