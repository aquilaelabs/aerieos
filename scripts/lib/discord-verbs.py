"""Behind `aerie discord` (cmd_discord in aerie): a space's Discord server
from a session (R293), relayed through the controller's /api/discord,
which holds the bot's token; a session never holds it.

  aerie discord [status]          the server connected and the last plans
  aerie discord pull              the server as it stands, written into
                                  deploy/discord.yml here, uncommitted
  aerie discord plan              what applying deploy/discord.yml would
                                  change, each change a person allows marked
  aerie discord apply --why "..." the layout made so

apply is under the space's Manage Discord dial: deny refuses, ask waits for
the space's owner on the bell, auto makes what asks nobody and asks for the
rest; a change that removes, changes a permission or reaches members waits
for a person whatever the dial says. The layout sent is this tree's own.

BB_PROJECT is the space; the auth header is bbapi's own (BB_AUTH_HEADER).
"""
import os
import subprocess
import sys
from pathlib import Path

import bbapi
import waits
from say import die

PROJECT = os.environ.get("BB_PROJECT", "")
LAYOUT = "deploy/discord.yml"
USAGE = """usage: aerie discord [status]
       aerie discord pull
       aerie discord plan
       aerie discord apply --why "what it is for\""""


def post(body):
    return bbapi.call("/api/discord", {"project": PROJECT, **body})


def root():
    """This repository's top, where deploy/discord.yml lives."""
    try:
        top = subprocess.run(["git", "rev-parse", "--show-toplevel"], capture_output=True, text=True, timeout=10).stdout.strip()
    except (OSError, subprocess.TimeoutExpired):
        top = ""
    return Path(top or os.getcwd())


def layout():
    f = root() / LAYOUT
    try:
        return f.read_text(encoding="utf-8")
    except OSError:
        die(f"no {LAYOUT} here yet: aerie discord pull writes the server as it stands into it")


def cmd_status():
    r = post({"action": "status"})
    if r.get("error"):
        die(r["error"])
    if not r.get("connected"):
        print("no Discord server connected: a person connects one in the space's settings, under Discord")
        return
    print(f"connected to {r.get('guild_name') or r.get('guild')}" + (f", by {r['by']}" if r.get("by") else ""))
    print(f"{LAYOUT}: {'here' if (root() / LAYOUT).is_file() else 'not here yet (aerie discord pull)'}")
    for p in (r.get("plans") or [])[:5]:
        print(f"  {'applied' if p.get('applied') else 'planned'} by {p.get('by') or '?'}: {p.get('said')}")


def cmd_pull():
    r = post({"action": "pull"})
    if r.get("error"):
        die(r["error"])
    f = root() / LAYOUT
    f.parent.mkdir(parents=True, exist_ok=True)
    f.write_text(r["text"], encoding="utf-8")
    print(f"wrote {LAYOUT}: the server as it stands; commit it, then plan and apply your changes")


def cmd_plan():
    r = post({"action": "plan", "text": layout()})
    if r.get("error"):
        die(r["error"])
    print(r.get("said") or "")
    for c in r.get("changes") or []:
        print(f"  {'! ' if c.get('asks') else '  '}{c['said']}")
    if r.get("asks"):
        print("(! a person allows these on the bell, whatever the space's Manage Discord dial says)")


def cmd_apply(args):
    why = ""
    if "--why" in args:
        i = args.index("--why")
        why = args[i + 1] if i + 1 < len(args) else ""
    if not why:
        die('aerie discord apply needs --why "what it is for"')
    r = post({"action": "apply", "text": layout(), "why": why})
    if r.get("error"):
        die(r["error"])
    for s in r.get("done") or []:
        print(f"  done: {s}")
    ask = r.get("asked") or (r.get("id") if not r.get("done") and not r.get("ok") else "")
    if ask:
        print(f"[builderbot] asked {r.get('to') or 'the space owner'} (#{ask}): the changes left wait on their bell, "
              "up to 15 minutes for Allow", file=sys.stderr)
        o = waits.outcome("", ask, "denied on the dashboard; the changes that ask were not made")
        if o.get("code"):
            die(o.get("out") or "refused")
        print(f"[builderbot] allowed: {o.get('out') or 'applied'}")
    elif r.get("ask_error"):
        die(f"the changes left could not be asked for: {r['ask_error']}")
    elif not r.get("done"):
        print(r.get("said") or "nothing to change: the server is as the file says")


def main(argv):
    verb, rest = (argv[0], argv[1:]) if argv else ("status", [])
    if verb in ("-h", "--help", "help"):
        print(USAGE)
        return
    if verb == "status":
        return cmd_status()
    if verb == "pull":
        return cmd_pull()
    if verb == "plan":
        return cmd_plan()
    if verb == "apply":
        return cmd_apply(rest)
    die(USAGE)


if __name__ == "__main__":
    main(sys.argv[1:])
