"""Behind `aerie tool search` and `aerie tool install` (cmd_tool in bb, R169 step
5): the vetted catalog looked through, and one tool asked for by name, to be
installed on the node this session runs on: a toolchain AerieOS ships, or a
tool pack of the vetted catalog, which is added here first at the commit the
signed index pins. The project's Install a tool pack dial says what happens:
deny refuses, ask waits for a person on the bell and installs it on their
Allow, auto installs it now. One the node already has is said at once and
nobody is asked; one whose install accepts an agreement is a person's to
install from the Library, where they accept it. A session never installs
anything on a node itself: the controller queues the job, in the name of
whoever allowed it.

The words are argv: the verb, then its own. The auth header is bbapi's own
(BB_AUTH_HEADER, from aerie), and BB_NODE_ID is the node this session's
terminal was told it is on, which the controller believes only when it is one
of the project's own.
"""
import os
import sys

import bbapi
from say import die, need

USAGE = """usage: aerie tool search [WORDS...]
       aerie tool install NAME --why "what it is for\""""


def said(d):
    """What an install that was queued, or had nothing left to do, says:
    the controller's sentence, the job where there is one and how to read
    it."""
    job = d.get("job") or ""
    print(f"[builderbot] {d.get('said') or d.get('out') or 'done'}" + (f": job {job}" if job and d.get("said") else ""))
    if job:
        print(f"[builderbot] aerie jobs {job} shows its log; a session started after it lands has the tool on its PATH")


def main(argv):
    if not argv or argv[0] not in ("search", "install"):
        sys.exit(USAGE)
    if argv[0] == "search":
        import urllib.parse
        d = bbapi.call("/api/catalog/search?q=" + urllib.parse.quote(" ".join(argv[1:])))
        if d.get("error") and not d.get("packs"):
            sys.exit(f"[builderbot] ERROR: {d['error']}")
        rows = d.get("packs") or []
        if not rows:
            print("nothing in the vetted catalog matches" + (f" {' '.join(argv[1:])}" if argv[1:] else ""))
            return
        for r in rows:
            mark = " (added here)" if r.get("added") else ""
            print(f"{r['name']:<24} {r.get('kind', 'pack'):<6} {r.get('tier') or '':<9} {r.get('about') or ''}{mark}")
        if d.get("more"):
            print(f"... and {d['more']} more: add words to narrow it")
        print("\naerie tool install NAME --why \"what it is for\" installs one on this session's node, "
              "as this space's Install a tool pack setting says")
        return
    rest = argv[1:]
    why = ""
    if "--why" in rest:
        i = rest.index("--why")
        why = " ".join(rest[i + 1:i + 2])
        rest = rest[:i] + rest[i + 2:]
    if len(rest) != 1:
        sys.exit(USAGE)
    d = bbapi.call("/api/toolpacks", {"action": "install", "name": rest[0], "why": why,
                                      "node": os.environ.get("BB_NODE_ID", "")})
    need(d)
    name = d.get("name") or rest[0]
    if d.get("note"):
        # Installed there already: nobody was asked.
        print(f"[builderbot] {d['note']}")
    elif d.get("id") and not d.get("job"):
        import waits
        where = d.get("node") or "this session's node"
        print(f"[builderbot] asked {d.get('to') or 'the administrators'} (#{d['id']}): install {name} on {where} is on "
              "their bell, waiting up to 15 minutes for their answer (Install a tool pack is ask)", file=sys.stderr)
        o = waits.outcome("", d["id"], "denied on the bell: nothing was installed",
                          "nothing was installed; ask again when a person is there to answer")
        if o.get("code"):
            die(o.get("out") or "refused")
        said({"out": f"allowed: {o.get('out') or 'done'}", "job": o.get("job") or ""})
    else:
        said(d)


if __name__ == "__main__":
    main(sys.argv[1:])
