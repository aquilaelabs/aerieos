"""Behind `aerie k8s` (cmd_k8s in aerie): a space's Kubernetes environments
from a session (R281 step 6), relayed through the controller's /api/k8s,
which holds every credential; a session never holds a kubeconfig.

  aerie k8s [status] [ENV]          each environment's workloads: ready of
                                    desired, the version, the pods, where it
                                    answers
  aerie k8s logs ENV POD [--tail N] [--container NAME]
  aerie k8s deploy ENV [REF] --why "..."
  aerie k8s rollback ENV --why "..."

deploy and rollback are under the space's Deploy to Kubernetes dial: deny
refuses, ask waits for the space's owner on the bell, auto starts it; an
environment marked production waits for a person whatever the dial says.
Once started, the job's log is followed to its end.

BB_PROJECT is the space; the auth header is bbapi's own (BB_AUTH_HEADER).
"""
import os
import sys

import bbapi
import waits
from say import die

PROJECT = os.environ.get("BB_PROJECT", "")
USAGE = """usage: aerie k8s [status] [ENV]
       aerie k8s logs ENV POD [--tail N] [--container NAME]
       aerie k8s deploy ENV [BRANCH|TAG|COMMIT] --why "what it is for"
       aerie k8s rollback ENV --why "what it is for\""""


def post(body):
    return bbapi.call("/api/k8s", {"project": PROJECT, **body})


def opts(args, flags):
    """(positional words, {flag: value}) for flags that each take a value."""
    words, got = [], {}
    i = 0
    while i < len(args):
        a = args[i]
        if a in flags:
            if i + 1 >= len(args):
                die(f"{a} needs a value after it\n{USAGE}")
            got[a] = args[i + 1]
            i += 2
            continue
        if a.startswith("--"):
            die(f"no option {a}\n{USAGE}")
        words.append(a)
        i += 1
    return words, got


def cmd_status(args):
    r = post({"action": "status", "env": args[0] if args else ""})
    if r.get("error"):
        die(r["error"])
    envs = r.get("envs") or []
    if not envs:
        print("no environment yet: a person adds one in the space's settings, under Deploy")
        return
    for e in envs:
        if e.get("error"):
            print(f"{e['name']}: {e['error']}")
            continue
        wl = e.get("workloads") or []
        print(f"{e['name']} ({e.get('namespace', '')}): " + (f"{sum(1 for w in wl if w['desired'] and w['ready'] >= w['desired'])} "
                                                             f"of {len(wl)} ready" if wl else "nothing deployed"))
        for w in wl:
            print(f"  {w['kind']} {w['name']}: {w['ready']} of {w['desired']} ready, {w.get('version') or '?'}"
                  + (f", at {', '.join(w['addresses'])}" if w.get("addresses") else ""))
            for p in w.get("pods") or []:
                print(f"    {p['name']}: {p['state']} {p['ready']}/{p['of']}, {p['restarts']} restarts"
                      + (f", on {p['node']}" if p.get("node") else ""))


def cmd_logs(args):
    words, got = opts(args, ("--tail", "--container"))
    if len(words) != 2:
        die(USAGE)
    r = post({"action": "logs", "env": words[0], "pod": words[1], "container": got.get("--container", ""),
              "tail": got.get("--tail", "200")})
    if r.get("error"):
        die(r["error"])
    sys.stdout.write(r.get("text") or "")


def cmd_change(verb, args):
    words, got = opts(args, ("--why",))
    if not words or len(words) > (2 if verb == "deploy" else 1):
        die(USAGE)
    if not got.get("--why"):
        die(f"aerie k8s {verb} needs --why \"what it is for\"")
    r = post({"action": verb, "env": words[0], "ref": words[1] if len(words) > 1 else "", "why": got["--why"]})
    if r.get("error"):
        die(r["error"])
    jid = r.get("job")
    if r.get("id") and not jid:
        to = r.get("to") or "the space's owner"
        print(f"[builderbot] asked {to} (#{r['id']}): the {verb} of {words[0]} is on their bell, "
              "waiting up to 15 minutes for Allow", file=sys.stderr)
        o = waits.outcome("", r["id"], f"denied on the dashboard; nothing was {'deployed' if verb == 'deploy' else 'rolled back'}")
        if o.get("code"):
            die(o.get("out") or "refused")
        jid = o.get("out")
    if not jid:
        die("the controller started nothing")
    print(f"[builderbot] {verb} of {words[0]}: job {jid}" + (f", {r['tag']}" if r.get("tag") else ""), file=sys.stderr)
    _, state = waits.follow("", jid)
    if state != "succeeded":
        die(f"the {verb} {state}: the job's log above says where")


def main(argv):
    verb, rest = (argv[0], argv[1:]) if argv else ("status", [])
    if verb in ("-h", "--help", "help"):
        print(USAGE)
        return
    if verb == "status":
        return cmd_status(rest)
    if verb == "logs":
        return cmd_logs(rest)
    if verb in ("deploy", "rollback"):
        return cmd_change(verb, rest)
    # `aerie k8s staging` is the status of staging.
    return cmd_status([verb])


if __name__ == "__main__":
    main(sys.argv[1:])
