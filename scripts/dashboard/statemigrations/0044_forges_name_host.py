"""State 43 to 44: every forge token an account keeps names its host.

An entry in account-secrets.json written before entries had ids (27 Oct)
was keyed by its host and had no `host` of its own, and one written before
hosts were kept unquoted (31 Oct) could carry a port's colon as git's credential
lines write it (%3a); accountkeys._entries mended both each time it read
one, taking the id for a missing host and unquoting and lowering it.
Written here once as _entries read them on 27 Nov, and the mending goes
(R205). The token stays sealed as it is: the host beside it is plain.

Idempotent. Never edited once shipped (stateversion.py).
"""
import json
import os
import urllib.parse
from pathlib import Path


def _bare(host):
    # accountkeys._bare on 27 Nov 2026.
    return urllib.parse.unquote(str(host or "")).lower()


def run(ctx):
    f = Path(ctx["state"]) / "account-secrets.json"
    try:
        d = json.loads(f.read_text())
    except (OSError, ValueError):
        return
    if not isinstance(d, dict):
        return
    moved = False
    for e in d.values():
        fs = e.get("forges") if isinstance(e, dict) else None
        for fid, ent in (fs.items() if isinstance(fs, dict) else ()):
            if not isinstance(ent, dict):
                continue
            host = _bare(ent.get("host") or fid)
            if ent.get("host") != host:
                ent["host"] = host
                moved = True
    if not moved:
        return
    tmp = f.with_name(f.name + ".tmp")
    tmp.write_text(json.dumps(d))
    os.chmod(tmp, f.stat().st_mode & 0o777)
    os.replace(tmp, f)
