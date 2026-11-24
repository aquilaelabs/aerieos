"""Behind `aerie forge` (R188): the project's git host worked through the
controller, which holds the project's token and runs each verb with it
(dashboard/forgeaccess.py); the token never reaches here.

Arguments: the project, then the words after `aerie forge`: a verb (whoami,
measure, owed, or a group and an action: pr list, run log ...), its positional
arguments, and its flags (--title "...", --draft, -f NAME=VALUE ...).
The session's credential is bbapi's own header (BB_AUTH_HEADER, from api_py
in aerie).
"""
import json
import sys

import bbapi
from say import die

GROUPS = ("pr", "issue", "run", "release")
# Flags that take no value.
SWITCHES = {"draft", "approve", "request-changes", "failed", "job", "json"}
# Every flag some verb reads (dashboard/forgeaccess.py), --body-file read
# here into --body: anything else is refused by name, where it was sent and
# dropped, and a pull request made with no description said nothing (B1123,
# report #132).
FLAGS = SWITCHES | {"base", "body", "body-file", "branch", "field", "head", "label", "lines", "method",
                    "name", "ref", "size", "state", "title"}


proj, words = sys.argv[1], list(sys.argv[2:])
if not words or words[0] in ("-h", "--help", "help"):
    print(__doc__.split("\n\n")[0])
    raise SystemExit(0)
verb = words.pop(0)
if verb in GROUPS:
    if not words:
        die(f"aerie forge {verb} needs an action: list, view ...")
    verb = f"{verb} {words.pop(0)}"
pos, flags = [], {}
while words:
    w = words.pop(0)
    # --field is -f's long name, a list as -f's is (B1062: read as one plain
    # flag, its value was taken a character at a time).
    if w in ("-f", "--field") or w.startswith("--field="):
        if w.startswith("--field="):
            flags.setdefault("field", []).append(w[len("--field="):])
            continue
        if not words:
            die(f"{w} needs NAME=VALUE")
        flags.setdefault("field", []).append(words.pop(0))
    elif w.startswith("--"):
        k, eq, v = w[2:].partition("=")
        if eq:
            flags[k] = v
        elif k in SWITCHES:
            flags[k] = True
        elif words:
            flags[k] = words.pop(0)
        else:
            die(f"--{k} needs a value")
    else:
        pos.append(w)
for k in flags:
    if k not in FLAGS:
        die(f"aerie forge: --{k} is not an option any verb takes; "
            f"aerie help forge lists each verb's ({', '.join('--' + f for f in sorted(FLAGS - {'json'}))})")
# --body-file FILE is the body read from that file, - from standard input.
if "body-file" in flags:
    if "body" in flags:
        die("aerie forge: --body or --body-file, not both")
    src = flags.pop("body-file")
    try:
        flags["body"] = sys.stdin.read() if src == "-" else open(src, encoding="utf-8").read()
    except OSError as e:
        die(f"aerie forge: --body-file {src}: {e.strerror or e}")
as_json = bool(flags.pop("json", False))
r = bbapi.call("/api/forge", {"project": proj, "verb": verb, "args": {"pos": pos, "flags": flags}},
               timeout=120)
if isinstance(r, dict) and r.get("error"):
    die(r["error"])
if as_json:
    print(json.dumps(r, indent=1))
elif verb == "whoami":
    print(r.get("briefing") or json.dumps(r.get("measure"), indent=1))
elif verb == "owed":
    # What the git host owes this repository's workflows (R267 step 29).
    for row in r:
        mark = {"ok": "[ok]  ", "owed": "[owed]"}.get(row.get("state"), "[?]   ")
        print(f"  {mark} {row.get('what')}" + (f": {row['why']}" if row.get("why") else ""))
    if not r:
        print("(nothing: no workflow here asks the host for an environment, a tag or a pull request)")
elif verb == "run log":
    for j in r:
        print(f"== job {j.get('job')}")
        print(j.get("log") or j.get("error") or "")
elif isinstance(r, list):
    for row in r:
        num = row.get("number") or row.get("id") or row.get("tag")
        state = row.get("conclusion") or row.get("state") or row.get("status") or ""
        what = row.get("title") or row.get("workflow") or row.get("name") or ""
        where = row.get("head") or row.get("branch") or ""
        print(f"{num}\t{state}\t{what}" + (f"\t{where}" if where else "") + (f"\t{row['url']}" if row.get("url") else ""))
    if not r:
        print("(none)")
else:
    print(json.dumps(r, indent=1, ensure_ascii=False))
