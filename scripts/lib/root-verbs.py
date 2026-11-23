"""Behind `aerie root` (cmd_root in bb): one command as root on the project's node
(roadmap R38), the phone's shape applied to root: the reason and the exact
command in front of a person, Allow runs it on the node, Deny says no.

The first argument is the verb (status or run); for run the rest are the
command. BB_PHONE_WHY is the sentence an administrator reads,
BB_PHONE_PROJECT the project asking. The auth header is bbapi's own
(BB_AUTH_HEADER, from api_py in aerie).
"""
import os
import sys

import bbapi
import waits
from say import need


def status():
    d = bbapi.call("/api/phone")
    if d.get("error"):
        sys.exit(f"[builderbot] ERROR: could not reach the dashboard at {bbapi.url()}: {d['error']}")
    asks = [a for a in (d.get("asks") or []) if a.get("kind") == "root"]
    if not asks:
        print("root:    nothing is waiting")
    for a in asks:
        print("waiting: #{} {} ({} on {}): {}".format(a.get("id"), a.get("why"), a.get("project") or "a session",
                                                     a.get("node_name"), " ".join(a.get("cmd") or [])))


def run():
    def post(body):
        # The ask itself: one nothing answered may still have been made, so
        # that is said, and where to look (B1070), rather than the bare error.
        st, got = bbapi.request("/api/phone", body)
        if st is None:
            sys.exit(f"[builderbot] ERROR: the controller did not answer the ask ({got.get('error') or 'no answer'}), "
                     "so it may or may not have been made: aerie root status says whether one is waiting")
        return got

    # A file under /tmp: on a sandbox node a session's /tmp is its own view
    # (bb-session), and the root command runs outside it, so the file is not
    # there and the command failed with a bare exit code (B253). Refused
    # before the ask, since an approval spent on it could only fail (B159).
    for a in sys.argv[2:]:
        if a.startswith(("/tmp/", "/var/tmp/", "/dev/shm/")) and os.path.exists(a):
            sys.exit(f"[builderbot] ERROR: {a} is under a directory that is this session's own view; "
                     "the root command runs outside it and would not find the file there, so nobody was "
                     "asked. A path under the space tree is seen by both.")
    r = post({"action": "ask", "kind": "root", "why": os.environ["BB_PHONE_WHY"], "cmd": sys.argv[2:],
              "project": os.environ.get("BB_PHONE_PROJECT", ""),
              # A node the project hosts containers on, when named (--node).
              **({"node": os.environ["BB_PHONE_NODE"]} if os.environ.get("BB_PHONE_NODE") else {})})
    need(r)
    rid = r["id"]
    print(f"[builderbot] asked {r.get('to') or 'the administrators'} (#{rid}) for root on {r.get('node') or 'the node'}, "
          "waiting up to 15 minutes for Approve on the dashboard's Nodes page or bell", file=sys.stderr)
    o = waits.outcome("", rid, "denied on the dashboard; nothing ran")
    sys.stdout.write(o.get("out") or "")
    sys.exit(o.get("code") or 0)


VERBS = {"status": status, "run": run}

if __name__ == "__main__":
    VERBS[sys.argv[1]]()
