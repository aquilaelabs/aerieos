"""What the roadmap and the bug tracker share: the file, its log and a batch.

Each of the two keeps one JSON file of the same shape:

    {"projects": {name: [row, ...]},     the rows as they stand
     "history":  {name: [event, ...]},   every change, capped
     "batch":    {name: {...}},          a session's open batch, if any
     "reserved": {name: n}}              the highest number ever handed out

and each reads it, logs to it, opens, commits and reverts a batch on it and
numbers its rows the same way. That half is here, once. What a row is, what
its verbs are, how a batch's events fold down and how a line reaches a
session stay in roadmap.py and bugs.py, which are different about all four.

A module makes one Tracker and keeps its own functions under the names its
callers know (begin, commit, history, _log and the rest), each a call into
it. Nothing is configured here: what differs between the two is handed to
the Tracker as it is made, and what the server or `aerie` injects into a
module later (its file, its writer, who is asking) is handed over as a call
that looks the module's name up when it runs.
"""
import json
import os
import sys
import time

# Beside this file, whichever way the module that imports it was loaded: see
# roadmap.py for why its neighbors come through sys.path.
_here = os.path.dirname(os.path.abspath(__file__))
if _here not in sys.path:
    sys.path.insert(0, _here)
import agents  # noqa: E402
import pending  # noqa: E402
import statefile  # noqa: E402


def _view(b):
    """An open batch as the status poll reads it."""
    return {"at": b.get("at", 0), "by": b.get("by", ""),
            "changes": len(b.get("events") or [])}


class Tracker:
    """One module's file, read, logged and batched.

    file()          where the file is, asked at each read
    lock            the lock every read-modify-write of it holds
    save(d)         the module's own write of the whole file
    number(v)       the module's reader of an id: a whole number or None,
                    its own tab's letter accepted
    actor()         the callable that names the account writing, or None
    limit()         how many events a project's history keeps
    keep(event)     whether the trim keeps this event whatever its age
    coalesce(evs)   a batch's events folded to what happened, on commit
    noun            what a sentence calls the list: "this list"
    already_open    the refusal when a batch is opened over an open one
    find_keys       the fields of an event that history's `find` reads
    sections        other top-level keys the file always has, each a dict
    counts_revn     whether every logged change also moves a counter per
                    project, `revn`, that outlives the history's cap
    on_revert       called with (d, project) as a revert puts the rows
                    back, before the save
    view            an open batch as the status poll reads it
    """

    def __init__(self, *, file, lock, save, number, actor, limit, keep,
                 coalesce, noun, already_open, find_keys, sections=(),
                 counts_revn=False, on_revert=None, view=None):
        self.file, self.lock, self.save = file, lock, save
        self.number, self.actor = number, actor
        self.limit, self.keep, self.coalesce = limit, keep, coalesce
        self.noun, self.already_open = noun, already_open
        self.find_keys, self.sections = tuple(find_keys), tuple(sections)
        self.counts_revn, self.on_revert = counts_revn, on_revert
        self.view = view or _view

    # ---- the file ----------------------------------------------------------

    def load(self):
        """The file, or an empty one of its shape when it is missing, cut
        short, or not what this wrote."""
        try:
            with open(self.file()) as f:
                d = json.load(f)
            if isinstance(d, dict) and isinstance(d.get("projects"), dict):
                for k in self.sections:
                    d.setdefault(k, {})
                return d
            # There and not what this wrote: kept, as one that is not JSON
            # is, before the next save writes the empty one over it.
            statefile.keep_unreadable(self.file(), f"not a {self.noun} file")
        except OSError:
            pass
        except ValueError as e:
            statefile.keep_unreadable(self.file(), str(e)[:160])
        return {"projects": {}, **{k: {} for k in self.sections}}

    # ---- the log -----------------------------------------------------------

    def by_whom(self):
        """{"who": name} for the account behind this change, or {}.

        "you" and "claude" say a person or a session and stop there; with two
        people on a project that answers nothing about which of them it was.
        The name is asked at the moment an event is logged, and behind a
        session it is the person the session was minted for.
        """
        actor = self.actor()
        name = str((actor() if actor else "") or "")[:60]
        return {"who": name} if name else {}

    def trim(self, h):
        """A project's log cut to its last limit() events, in place, less the
        older ones keep() holds on to."""
        limit = self.limit()
        if len(h) <= limit:
            return
        cut = len(h) - limit
        h[:cut] = [e for e in h[:cut] if self.keep(e)]

    def log(self, d, project, by, ev):
        """Record one event, in the history or in an open batch.

        Called inside the lock, before the save that commits the change it
        describes, so the record and the change land together or neither
        does.

        While a batch is open its owner's events go into it instead. A
        session working something out rewords the same line three times
        before it is happy, and three entries saying so is a log nobody can
        read to find the one change that mattered. The batch is coalesced on
        commit into what actually happened.
        """
        if self.counts_revn:
            # Counted here because every write comes through here, batched or
            # not, and a history's length stops moving at its cap.
            d.setdefault("revn", {})[project] = int(d.get("revn", {}).get(project) or 0) + 1
        ev = {"at": int(time.time()),
              "by": "claude" if by == "claude" else "you", **agents.asker(by),
              **self.by_whom(),
              # A replay of something the operator approved: said on the event,
              # so the log reads "claude, approved" rather than "claude".
              **({"approved": True} if pending.replaying() else {}), **ev}
        b = d.get("batch", {}).get(project)
        if b is not None and ev["by"] == b.get("by", "claude"):
            b.setdefault("events", []).append(ev)
            return
        # Anyone else's change goes straight to the history, which is also what
        # makes revert's guard work: it looks there for the operator's hand.
        h = d.setdefault("history", {}).setdefault(project, [])
        h.append(ev)
        self.trim(h)

    def history(self, project, limit=None, since=None, find=None):
        """What has happened here, newest first, optionally narrowed: to the
        events at or after `since`, to those with `find` in one of
        find_keys, to the first `limit`."""
        with self.lock:
            h = self.load().get("history", {}).get(project) or []
        # Sorted, not merely reversed: a batch's events are written at commit,
        # so the order they sit in the file is not the order they happened in.
        out = sorted(h, key=lambda e: -e.get("at", 0))
        if since is not None:
            cut = self.number(since)
            if cut is not None:
                out = [e for e in out if e.get("at", 0) >= cut]
        if find:
            needle = str(find).lower()
            out = [e for e in out
                   if any(needle in str(e.get(k, "")).lower()
                          for k in self.find_keys)]
        n = self.number(limit)
        if n is not None and n > 0:
            out = out[:n]
        return out

    def moved_by(self, d, project, row_id):
        """Who last changed this row and when, out of the log, for a refusal
        that is worth nothing without a name and a time on it.

        An open batch is searched first: its events are newer than anything
        in the history, and a session working something out is the likeliest
        other writer.
        """
        b = (d.get("batch", {}).get(project) or {}).get("events") or []
        h = d.get("history", {}).get(project) or []
        for e in reversed(list(h) + list(b)):
            if self.number(e.get("id")) == row_id:
                return {"by": e.get("by", ""), "at": e.get("at", 0)}
        return {}

    # ---- a batch -----------------------------------------------------------
    # `begin` takes a copy of the rows, the work happens normally on top of
    # it, and `commit` writes what changed rather than every step of getting
    # there. `revert` puts the copy back.

    def begin(self, project, by="claude"):
        with self.lock:
            d = self.load()
            if d.get("batch", {}).get(project):
                return {"error": self.already_open}
            # How many of the operator's changes the log already held. Counted,
            # not timed: `at` has one-second resolution, so "later than the
            # batch opened" caught anything that happened in the same second
            # as it, which made revert refuse for a change that came before
            # the work it was asked to undo.
            h = d.get("history", {}).get(project) or []
            d.setdefault("batch", {})[project] = {
                "at": int(time.time()), "by": by, "events": [],
                "yours": sum(1 for e in h if e.get("by") == "you"),
                "rows": json.loads(json.dumps(d["projects"].get(project) or []))}
            self.save(d)
        return {"ok": True}

    def batches(self):
        """Every project with a batch open, for the status poll.

        One read of the file for all of them: this runs on every poll, and
        asking per project would be a load and a lock each.
        """
        with self.lock:
            d = self.load().get("batch", {})
        return {p: self.view(b) for p, b in d.items() if b}

    def batch(self, project):
        """The open batch here, or None."""
        with self.lock:
            b = self.load().get("batch", {}).get(project)
        return None if not b else self.view(b)

    def commit(self, project):
        with self.lock:
            d = self.load()
            b = d.get("batch", {}).get(project)
            if not b:
                return {"error": "nothing is open here"}
            kept = self.coalesce(b.get("events") or [])
            h = d.setdefault("history", {}).setdefault(project, [])
            h.extend(kept)
            self.trim(h)
            del d["batch"][project]
            self.save(d)
        return {"ok": True, "written": len(kept),
                "folded": len(b.get("events") or []) - len(kept)}

    def revert_blocked(self, project):
        """Why a revert would refuse, or None. Asked before anything is undone.

        Only the session's own work goes back. If the operator changed
        something while the batch was open, restoring a copy taken before it
        would quietly undo their change too, so it is refused and said.

        Its own call because a notebook batch spans two files: both guards
        have to answer before either is put back, or a refusal from the
        second would leave the first already reverted.
        """
        with self.lock:
            d = self.load()
            b = d.get("batch", {}).get(project)
            if not b:
                return "nothing is open here"
            h = d.get("history", {}).get(project) or []
            if sum(1 for e in h if e.get("by") == "you") > b.get("yours", 0):
                return (f"the operator has changed {self.noun} since the batch "
                        "opened; reverting would undo their work too. "
                        "Commit it and correct what is wrong.")
        return None

    def revert(self, project):
        why = self.revert_blocked(project)
        if why:
            return {"error": why}
        with self.lock:
            d = self.load()
            b = d.get("batch", {}).get(project)
            if not b:
                return {"error": "nothing is open here"}
            d["projects"][project] = b.get("rows") or []
            del d["batch"][project]
            if self.on_revert:
                self.on_revert(d, project)
            self.save(d)
        return {"ok": True, "dropped": len(b.get("events") or [])}

    # ---- numbers -----------------------------------------------------------

    def next_id(self, rows, d=None, project=None):
        """One above the highest number ever handed out here.

        Among `rows`, and, where the file and the project are given, held for
        approval (pending.py) or finished and gone as well: the file keeps
        the high-water mark under `reserved`, and it never comes down. A
        number is the row's own, and "a gap means something was removed"
        only holds if nothing is ever numbered twice.
        """
        top = max((int(r.get("id", 0)) for r in rows), default=0)
        if d is not None and project is not None:
            top = max(top, self.number((d.get("reserved") or {}).get(project)) or 0)
        return top + 1

    def took(self, d, project, n):
        """Record that `n` has been handed out, so it never is again."""
        r = d.setdefault("reserved", {})
        r[project] = max(self.number(r.get(project)) or 0, int(n))
