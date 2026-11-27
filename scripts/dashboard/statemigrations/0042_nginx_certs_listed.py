"""State 41 to 42: every node's nginx certificate is a listed pair.

Before R188 (11 Oct) a node kept one default pair, `cert` in nginx.json with
its files in the node's own directory, and nginxproxy.py moved it into the
list under the domain its names say each time the node's record was read,
so a node not read since could still hold it. Moved here once as
nginxproxy._migrate moved it on 27 Nov (its helpers copied in, since a
migration never reads a module, which moves on), and the move on read goes
(R205).

Idempotent. Never edited once shipped (stateversion.py).
"""
import contextlib
import json
import os
import re
from pathlib import Path

# nginxproxy.HOST_RE on 27 Nov 2026.
HOST_RE = re.compile(r"^[a-z0-9]([a-z0-9-]{0,62}[a-z0-9])?(\.[a-z0-9]([a-z0-9-]{0,62}[a-z0-9])?)*$")


def _cert_dir(state, nid, host=""):
    d = state / "nginx" / re.sub(r"[^A-Za-z0-9_-]", "_", str(nid))
    return d / "certs" / re.sub(r"[^a-z0-9.-]", "_", host.lower()) if host else d


def _domain_of(names):
    first = str(names or "").split(",")[0].strip().lower()
    if first.startswith("*."):
        first = first[2:]
    return first if HOST_RE.match(first) else ""


def run(ctx):
    state = Path(ctx["state"])
    f = state / "nginx.json"
    try:
        st = json.loads(f.read_text())
    except (OSError, ValueError):
        return
    if not isinstance(st, dict):
        return
    moved = False
    for nid, rec in st.items():
        if not isinstance(rec, dict) or "cert" not in rec:
            continue
        cur = rec.get("cert")
        if isinstance(cur, dict) and cur.get("set"):
            key = _domain_of(cur.get("names") or cur.get("subject") or "") or "default"
            src, dst = _cert_dir(state, nid), _cert_dir(state, nid, key)
            dst.mkdir(parents=True, exist_ok=True, mode=0o700)
            for name in ("cert.pem", "key.pem"):
                with contextlib.suppress(OSError):
                    (src / name).replace(dst / name)
            rec.setdefault("certs", {}).setdefault(key, cur)
        rec.pop("cert", None)
        moved = True
    if not moved:
        return
    tmp = f.with_name(f.name + ".tmp")
    tmp.write_text(json.dumps(st, indent=1))
    os.chmod(tmp, f.stat().st_mode & 0o777)
    os.replace(tmp, f)
