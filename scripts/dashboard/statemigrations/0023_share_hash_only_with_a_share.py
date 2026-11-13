"""State 22 to 23: a share password kept only for an account a share names
(the operator, 13 Nov).

On a controller installed on its own machine every sign-in kept the NT hash
of the account's password (MD4, what Samba asks for) beside the password's
own hash, so a share could be opened with the same password, whether or not
any share named the account. That hash is far weaker than the password's
own and went wherever a copy of users.json went. It is kept now for an
account a share names and for nobody else.

Each account whose share password followed its sign-in (smb_follows) and
that no SMB share on the controller's own machine names, as a user or a
reader, has it taken away here. One a person set apart on Profile is theirs
and stays, and so does one that came with a move. Who is named is read from
what the own machine last reported, kept in the database; where no own
machine has reported, no share is served and every followed one goes. An
account named later has its share password made again at its next sign-in.
Idempotent. Never edited once shipped (stateversion.py).
"""
import json
import re
import sqlite3
import sys
from pathlib import Path


def _named(state):
    """The Unix users the own machine's SMB shares name."""
    out = set()
    db = Path(state) / "builderbot.db"
    if not db.is_file():
        return out
    try:
        con = sqlite3.connect(f"file:{db}?mode=ro", uri=True)
        try:
            rows = con.execute("SELECT config, reported FROM nodes WHERE kind = 'agent'").fetchall()
        finally:
            con.close()
    except sqlite3.Error:
        return out
    for config, reported in rows:
        try:
            cfg, rep = json.loads(config or "{}"), json.loads(reported or "{}")
        except ValueError:
            continue
        if not (isinstance(cfg, dict) and cfg.get("own") and isinstance(rep, dict)):
            continue
        for sh in rep.get("shares") or []:
            sm = sh.get("smb") if isinstance(sh, dict) else None
            if isinstance(sm, dict) and sm.get("on"):
                out.update(str(u) for u in [*(sm.get("users") or []), *(sm.get("readers") or [])])
    return out


def run(ctx):
    f = Path(ctx["state"]) / "users.json"
    try:
        d = json.loads(f.read_text())
    except (OSError, ValueError):
        return
    users = d.get("users") if isinstance(d, dict) else None
    if not isinstance(users, dict):
        return
    named = _named(ctx["state"])
    changed = False
    for u in users.values():
        if not (isinstance(u, dict) and u.get("smb_follows") and u.get("smb_nt")):
            continue
        uid = str(u.get("uid") or "")
        user = "bbu-" + uid[2:] if re.fullmatch(r"u_[0-9a-f]{8}", uid) else ""
        if user and user in named:
            continue
        for k in ("smb_nt", "smb_at", "smb_follows"):
            u.pop(k, None)
        changed = True
    if not changed:
        return
    sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
    import statefile
    statefile.write_json(f, d, mode=f.stat().st_mode & 0o777)
