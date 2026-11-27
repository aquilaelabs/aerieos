"""State 38 to 39: every finished roadmap item's "done" event holds its row.

An item finished by its last step before 15 Oct (B767) was logged with its
words alone, or with an empty row a build before the rebuild wrote, and
roadmap.py put its row back together from the log each time the Finished
section or a reopen read it, and never wrote it. Each is put together here
once as roadmap.py did on 27 Nov (its rules copied in, since a migration
never reads a module, which moves on) and written into its event, and the
rebuilding goes (R205).

Idempotent. Never edited once shipped (stateversion.py).
"""
import json
import os
from pathlib import Path


def _int(v):
    if isinstance(v, bool):
        return None
    if isinstance(v, int):
        return v
    s = str(v or "").strip()
    s = s[1:] if s[:1] in ("R", "r") else s
    return int(s) if s.isdigit() else None


def _oldest_first(events):
    return [e for _, e in sorted(enumerate(events), key=lambda p: (p[1].get("at", 0), p[0]))]


def _rebuilt_row(events, item_id, text):
    row = {"id": item_id, "text": text, "steps": []}
    steps = row["steps"]
    for e in events:
        if _int(e.get("id")) != item_id:
            continue
        act, i = e.get("act"), _int(e.get("step"))
        if act == "add":
            row["text"] = e.get("text") or row["text"]
            steps[:] = [{"text": f"step {k + 1} (its words were not kept)", "sent": 0}
                        for k in range(_int(e.get("steps")) or 0)]
        elif act == "add-step" and i is not None:
            while len(steps) < i:
                steps.append({"text": f"step {len(steps) + 1} (its words were not kept)", "sent": 0})
            steps[i:i + 1] = [{"text": e.get("text", ""), "sent": 0}]
        elif i is not None and 0 <= i < len(steps):
            if act == "edit-step":
                steps[i]["text"] = e.get("text", steps[i]["text"])
            elif act == "info-step":
                steps[i]["info"] = e.get("text", "")
            elif act == "done-step":
                steps[i]["done"] = e.get("at", 0)
            elif act == "undone-step":
                steps[i].pop("done", None)
            elif act == "target-step":
                if e.get("target"):
                    steps[i]["target"] = e["target"]
                else:
                    steps[i].pop("target", None)
        elif act == "edit" and i is None:
            row["text"] = e.get("text") or row["text"]
        elif act == "info" and i is None:
            row["info"] = e.get("text", "")
        if act in ("add", "target") and i is None and "target" in e:
            row["target"] = e["target"]
    if not row.get("target"):
        row.pop("target", None)
    return row


def run(ctx):
    f = Path(ctx["state"]) / "roadmap.json"
    try:
        d = json.loads(f.read_text())
    except (OSError, ValueError):
        return
    history = d.get("history") if isinstance(d, dict) else None
    if not isinstance(history, dict):
        return
    moved = False
    for log in history.values():
        if not isinstance(log, list):
            continue
        ordered = None
        for e in log:
            if not isinstance(e, dict) or e.get("act") != "done" or e.get("step") is not None:
                continue
            row = e.get("row") if isinstance(e.get("row"), dict) else {}
            if row.get("steps"):
                continue
            i = _int(e.get("id"))
            if i is None:
                continue
            ordered = ordered if ordered is not None else _oldest_first([x for x in log if isinstance(x, dict)])
            got = _rebuilt_row(ordered, i, e.get("text", ""))
            new = {**got, **row, "steps": got["steps"]}
            if new != e.get("row"):
                e["row"] = new
                moved = True
    if not moved:
        return
    tmp = f.with_name(f.name + ".tmp")
    tmp.write_text(json.dumps(d, indent=1))
    os.chmod(tmp, f.stat().st_mode & 0o777)
    os.replace(tmp, f)
