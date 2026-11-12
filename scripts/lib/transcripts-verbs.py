"""Behind `aerie transcripts` (cmd_transcripts in bb): the account's own
conversations with Claude on a project, through the controller's API as
the caller (transcripts.py on the dashboard's side, the Profile page's
list and download). `list` prints them newest first with the first thing
typed; `show ID [--tz ZONE]` prints one as the Profile's download reads,
stamped in ZONE (the controller's own when none), the newest 16 MB of a
longer one unless --all; `fetch ID` copies the
file itself into this machine's folder for it, which is how a synced node
resumes a conversation it does not have (B613). A session reads its
account's conversations on its own project and on one its project reads
(`bb -p NAME transcripts`), and nobody else's: the controller looks under
the account's transcripts and nowhere else. `audit [DAYS]` is `aerie rules
audit`: the same conversations counted against the rules that refuse
commands (R200). `label ID WORDS`, `note ID WORDS`, `keep ID` and `unkeep
ID` say something of one of the account's own (R236): the name and the note
its person reads it by, and whether a copy of it is kept past its agent's
own cleanup. BB_TRANSCRIPTS_AUTH is the
auth header and BB_TRANSCRIPTS_PROJECT the project.
"""
import os
import sys
import time
import urllib.parse

import bbapi

argv = sys.argv[1:]
verb = argv[0] if argv else "list"
auth = os.environ["BB_TRANSCRIPTS_AUTH"]
proj = os.environ["BB_TRANSCRIPTS_PROJECT"]


def fail(msg):
    sys.exit(f"[builderbot] ERROR: {msg}")


# How much of a long conversation `show` prints, from its end, without --all.
SHOW_TAIL_MB = 16


def size(n):
    return f"{n / 1024 / 1024:.1f} MB" if n >= 1024 * 1024 else f"{max(1, n // 1024)} KB"


if verb == "list":
    r = bbapi.call(f"/api/transcripts?project={urllib.parse.quote(proj)}", auth=auth)
    if not isinstance(r, dict) or r.get("error"):
        fail(r.get("error") if isinstance(r, dict) else "the controller answered something that is not a list")
    rows, seen = r.get("rows") or [], r.get("visible") or []
    if not rows and not seen:
        print(f"no conversations of yours on {proj} yet")
        raise SystemExit(0)
    # Each row marked with its agent (R95), in both lists.
    names = {"claude": "Claude", "codex": "ChatGPT", "copilot": "Copilot", "grok": "Grok", "open": "Any model"}

    def line(row, who=""):
        when = time.strftime("%d %b %H:%M", time.localtime(int(row.get("at") or 0)))
        agent = names.get(row.get("agent") or "claude", row.get("agent") or "")
        # Under its label where its person gave it one, its first words
        # otherwise; a kept one says so.
        says = row.get("label") or row.get("first") or ""
        kept = "kept  " if row.get("kept") else ""
        print(f"  {row['id']}  {agent:<9} {when}  {size(int(row.get('bytes') or 0)):>7}  {kept}{who}{says}")
        if row.get("note"):
            print(f"      note: {' '.join(str(row['note']).split())}")
    if rows:
        print(f"your conversations on {proj}, every agent's, newest first:")
        for row in rows:
            line(row)
    # Others' that their person made visible to every session here (the
    # Sessions view's Make visible), each with whose it is.
    if seen:
        print(f"made visible to every session on {proj} by their person:")
        for row in seen:
            line(row, f"({row.get('by') or '?'}) ")
    print("aerie transcripts show ID prints one: what was said, every command it ran and what it answered")
    raise SystemExit(0)

if verb in ("label", "note", "keep", "unkeep"):
    words = verb in ("label", "note")
    if len(argv) < 2 or (not words and len(argv) != 2):
        fail(f"aerie transcripts {verb} ID" + (" WORDS (no words takes it off)" if words else ""))
    body = {"project": proj, "id": argv[1], "action": verb}
    if words:
        body["text"] = " ".join(argv[2:])
    r = bbapi.call("/api/transcripts", body, auth=auth)
    if not isinstance(r, dict) or r.get("error"):
        fail(r.get("error") if isinstance(r, dict) else "the controller did not answer")
    if verb == "label":
        print(f"{argv[1]} is labeled: {r.get('label')}" if r.get("label") else f"{argv[1]} has no label now: it is listed by its first words")
    elif verb == "note":
        print(f"noted on {argv[1]}" if r.get("note") else f"{argv[1]} has no note now")
    else:
        print(f"{argv[1]} is kept: a copy stays on the controller past its agent's own cleanup" if r.get("kept")
              else f"{argv[1]} is no longer kept: it lasts as long as its agent keeps it")
    raise SystemExit(0)

if verb == "audit":
    # `aerie rules audit [DAYS]` (R200): the account's conversations here over
    # the last DAYS, counted against the rules that refuse commands.
    days = argv[1] if len(argv) > 1 and argv[1].isdigit() else "7"
    q = urllib.parse.urlencode({"project": proj, "audit": days})
    r = bbapi.call(f"/api/transcripts?{q}", auth=auth, timeout=300)
    if not isinstance(r, dict) or r.get("error"):
        fail(r.get("error") if isinstance(r, dict) else "the controller answered something that is not an audit")
    a = r.get("audit") or {}
    print(f"your conversations on {proj} over the last {a.get('days')} days: "
          f"{a.get('conversations', 0)}, with {a.get('bash', 0)} shell commands"
          + (f" (the newest {48} MB of {a['partial']} long one{'s' if a['partial'] != 1 else ''})" if a.get("partial") else ""))
    g = a.get("guards") or {}
    if g:
        print("commands a rule refuses (refused since the guard, or would have been before it):")
        for name, n in sorted(g.items(), key=lambda kv: -kv[1]):
            print(f"  {n:>5}  {name}")
            for ex in (a.get("examples") or {}).get(name, []):
                print(f"         $ {ex[:120]}")
    else:
        print("no command a rule refuses")
    print(f"refused by the guard: {a.get('refused', 0)}")
    print(f"the code map asked: {a.get('map', 0)}, grep and Grep: {a.get('grep', 0)}")
    raise SystemExit(0)

if verb == "show":
    sid = argv[1] if len(argv) > 1 and not argv[1].startswith("--") else ""
    if not sid:
        fail("aerie transcripts show ID [--tz ZONE] [--all]: the id from aerie transcripts")
    tz = ""
    if "--tz" in argv:
        k = argv.index("--tz")
        tz = argv[k + 1] if k + 1 < len(argv) else ""
    # The newest part of a long one unless --all: a resumed session wants
    # where it stopped, and a whole day's conversation outran the wait.
    q = urllib.parse.urlencode({"project": proj, "id": sid, "tz": tz, "as": "json",
                                "tail": 0 if "--all" in argv else SHOW_TAIL_MB})
    r = bbapi.call(f"/api/transcript?{q}", auth=auth, timeout=600 if "--all" in argv else 120)
    if not isinstance(r, dict) or r.get("error"):
        fail(r.get("error") if isinstance(r, dict) else "the controller answered something that is not a transcript")
    sys.stdout.write(r.get("text") or "")
    raise SystemExit(0)

if verb == "fetch":
    # The conversation as Claude Code wrote it, into this machine's folder
    # for it, so a node holding its projects as a synced copy can resume one
    # it does not have (B613): bb-tty runs this before claude --resume. A
    # copy here that is as long is left alone.
    import re
    sid = argv[1] if len(argv) > 1 and not argv[1].startswith("--") else ""
    if not sid or not re.fullmatch(r"[0-9A-Za-z-]+", sid):
        fail("aerie transcripts fetch ID [--into DIR]: the id from aerie transcripts")
    into = ""
    if "--into" in argv:
        k = argv.index("--into")
        into = argv[k + 1] if k + 1 < len(argv) else ""
    if not into:
        into = os.path.join(os.path.expanduser("~/.claude/projects"), re.sub(r"[^A-Za-z0-9]", "-", os.getcwd()))
    dest = os.path.join(into, sid + ".jsonl")
    have = os.path.getsize(dest) if os.path.isfile(dest) else -1
    q = urllib.parse.urlencode({"project": proj, "id": sid, "as": "raw", "have": have})
    try:
        c, base = bbapi._conn(600)
        c.request("GET", f"{base}/api/transcript?{q}", None, {"Authorization": auth})
        r = c.getresponse()
        if r.status != 200 or r.getheader("Content-Type", "").startswith("application/json"):
            import json
            got = json.loads(r.read() or b"{}")
            c.close()
            if r.status != 200:
                fail(got.get("error") or f"HTTP {r.status}")
            print(f"{sid} is here already")
            raise SystemExit(0)
        os.makedirs(into, exist_ok=True)
        tmp = os.path.join(into, f".bbsync-{sid}.jsonl")
        n = 0
        with open(tmp, "wb") as f:
            for chunk in iter(lambda: r.read(1 << 20), b""):
                f.write(chunk)
                n += len(chunk)
        c.close()
        want = int(r.getheader("Content-Length") or n)
        if n != want:
            os.remove(tmp)
            fail(f"the download stopped at {size(n)} of {size(want)}")
        mt = int(r.getheader("X-Mtime-Ms") or 0)
        if mt:
            # The controller's time, so the node's mirror reads the two as
            # one file and sends nothing back.
            os.utime(tmp, ns=(mt * 1_000_000, mt * 1_000_000))
        os.chmod(tmp, 0o600)
        os.replace(tmp, dest)
    except OSError as e:
        fail(f"could not fetch {sid}: {e}")
    print(f"fetched {sid} ({size(n)}) from the controller")
    raise SystemExit(0)

fail("aerie transcripts [list | show ID [--tz ZONE] | fetch ID [--into DIR]]")
