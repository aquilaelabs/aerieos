"""A session's bb on a node whose projects are a synced copy:
wait for the copy to be in step with the controller's before a relayed verb
reads or changes the controller's copy, and for the controller's changes to
be back here before the verb's answer is used.

The agent writes each project's state to .bbsync-state inside it (in .git
when there is one): the revision this copy has caught up to, how many
changes are still waiting to go up, and when the tick that measured that
began. No file, no synced copy: nothing to wait for.
"""
import json
import os
import sys
import time

UP_S = 60
DOWN_S = 60
# How long up goes on waiting while the copy is moving: each fall in what
# is left to send buys another UP_S, up to this (a node with
# thousands of changes on their way failed a push after a minute while they
# were still going, and the session tried again blindly four times).
MOVING_S = 600


def state_file(project):
    top = os.path.join(os.environ.get("WORKSPACE") or "/workspace", project)
    for f in (os.path.join(top, ".git", ".bbsync-state"), os.path.join(top, ".bbsync-state")):
        if os.path.isfile(f):
            return f
    return ""


def _read(f):
    try:
        with open(f) as fh:
            return json.load(fh)
    except (OSError, ValueError):
        return None


def up(project, why="the controller acts on this space's tree"):
    """Every change made here has reached the controller: a tick that began
    after this was asked saw nothing left to send. False, said, when it
    did not happen in time."""
    f = state_file(project)
    if not f:
        return True
    asked = time.time()
    end = asked + UP_S
    st, least = None, None
    while time.time() < end:
        st = _read(f)
        if st and float(st.get("started") or 0) > asked and not int(st.get("pending") or 0):
            return True
        # Moving: fewer left than ever seen buys another UP_S, within MOVING_S.
        left = int((st or {}).get("pending") or 0)
        if st and (least is None or left < least):
            if least is not None:
                end = min(max(end, time.time() + UP_S), asked + MOVING_S)
            least = left
        time.sleep(0.2)
    pending = int((st or {}).get("pending") or 0)
    print(f"[builderbot] WARN: {pending or 'some'} change(s) here have not reached the controller in "
          f"{round(time.time() - asked)}s{': ' + st['error'] if st and st.get('error') else ''}, and {why}", file=sys.stderr)
    return False


def down(project, rev):
    """This copy has caught up to the controller's revision `rev`."""
    f = state_file(project)
    if not f or not rev:
        return True
    end = time.time() + DOWN_S
    while time.time() < end:
        st = _read(f)
        if st and int(st.get("rev") or 0) >= int(rev):
            return True
        time.sleep(0.2)
    print(f"[builderbot] WARN: what the controller changed has not reached this copy in {DOWN_S}s; "
          "it arrives on its own when the node is back in step", file=sys.stderr)
    return False
