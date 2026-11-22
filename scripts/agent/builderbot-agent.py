#!/usr/bin/env python3
"""AerieOS's node agent, the entry: the agent itself is the aerieos_agent
package beside this file (its __init__ says what it is and how it runs).

The controller ships the two as one zip with this file as its __main__.py
(aerieos_agent/bundle.py), and python runs that zip as it runs this file,
so a node still keeps one file at one path. From a checkout, this runs the
package beside it.

The way back from a bad update is here too, and for that reason this file
uses the standard library alone and nothing of the package: it has to work
when the package does not. A self-update keeps the file it replaces beside
the new one (FILE.prev) and leaves a note that the new one is on trial
(FILE.trial), which the agent takes away at its first answer from the
controller. Until then this entry counts each start of `run`. A package that
cannot be loaded, or a fourth start with the note still there, puts the old
file back and starts it, leaving why beside it (FILE.back) for the agent to
tell its controller. A node whose update would not start is back on the
agent it had, with nobody at its console.
"""
import json
import os
import sys
import time

# The starts a new agent gets to reach its controller before the old one is
# put back: a crash, the service's restart, twice more.
TRIAL_STARTS = 3


def _me():
    """The file a node runs: the zip this is the __main__ of, or this file."""
    here = os.path.dirname(os.path.abspath(__file__))
    return here if os.path.isfile(here) else os.path.abspath(__file__)


def _read(path):
    try:
        with open(path, encoding="utf-8") as f:
            d = json.load(f)
        return d if isinstance(d, dict) else None
    except (OSError, ValueError):
        return None


def _write(path, d):
    tmp = path + ".w"
    with open(tmp, "w", encoding="utf-8") as f:
        json.dump(d, f)
    os.replace(tmp, path)


def _back(me, why):
    """The file the update replaced put back and started in this one's place.
    Returns only when there is none to put back, or it could not be."""
    prev = me + ".prev"
    if not os.path.isfile(prev):
        return
    trial = _read(me + ".trial") or {}
    try:
        _write(me + ".back", {"digest": str(trial.get("digest") or ""), "at": int(time.time()),
                              "why": str(why)[:300]})
        os.replace(prev, me)
    except OSError as e:
        sys.stderr.write(f"aerieos-agent: could not put the agent before this one back: {e}\n")
        return
    try:
        os.unlink(me + ".trial")
    except OSError:
        pass
    sys.stderr.write(f"aerieos-agent: the updated agent {why}; the one before it is back and starting\n")
    sys.stderr.flush()
    os.execv(sys.executable, [sys.executable, me] + sys.argv[1:])


def _on_trial(me):
    """One more start of an agent on trial counted, or the old one put back
    when it has had its starts, or was told by itself to give way."""
    trial = _read(me + ".trial")
    if trial is None:
        return
    try:
        starts = int(trial.get("starts") or 0) + 1
    except (TypeError, ValueError):
        starts = 1
    if trial.get("why") or starts > TRIAL_STARTS:
        _back(me, str(trial.get("why") or f"started {starts - 1} times and never reached its controller"))
        return                          # nothing to go back to: carry on as it is
    trial["starts"] = starts
    try:
        _write(me + ".trial", trial)
    except OSError:
        pass


if __name__ == "__main__":
    # Inside the zip this is the zip itself, already on the path.
    here = os.path.dirname(os.path.abspath(__file__))
    if here not in sys.path:
        sys.path.insert(0, here)
    running = sys.argv[1:2] == ["run"]
    if running:
        _on_trial(_me())
    try:
        from aerieos_agent.cli import main
    except BaseException as e:          # noqa: BLE001 (whatever a broken package raises at import)
        if running and _read(_me() + ".trial") is not None:
            _back(_me(), f"could not be loaded ({type(e).__name__}: {e})")
        raise
    main(sys.argv[1:])
