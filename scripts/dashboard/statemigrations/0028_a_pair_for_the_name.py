"""State 27 to 28: the certificate for the dashboard's name is kept in files
of its own.

The dashboard kept one certificate and key (tls/cert.pem, tls/key.pem), of
whichever kind its Connection setting asked for: the install's own, or the
one issued for its name. It keeps both now, since a node pins the key of the
install's own and has to meet it whatever the setting says: cert.pem and
key.pem are the install's own, acme-cert.pem and acme-key.pem the name's.
Where the pair kept was the name's (tls/meta.json says kind acme), it moves
to the name's two files here, the key as it is sealed, and the record says
whose it is; the install's own pair is then made at the start that follows.
An install that kept its own pair, or none, is left as it is.

The files move before the record is rewritten, so a start cut short between
the two finds the record as it was and finishes. Idempotent. Never edited
once shipped (stateversion.py).
"""
import json
import os
from pathlib import Path

MOVES = (("cert.pem", "acme-cert.pem"), ("key.pem", "acme-key.pem"))


def run(ctx):
    d = Path(ctx["state"]) / "tls"
    f = d / "meta.json"
    try:
        m = json.loads(f.read_text())
    except (OSError, ValueError):
        return
    if not isinstance(m, dict) or m.get("kind") != "acme":
        return
    for was, now in MOVES:
        if (d / was).exists():
            os.replace(d / was, d / now)
    made = m.get("made")
    m["acme"] = {"names": [n for n in m.get("names") or [] if isinstance(n, str)] if isinstance(m.get("names"), list) else [],
                 "made": made if isinstance(made, int) and not isinstance(made, bool) else 0}
    m.update({"kind": "self", "names": [], "made": 0})
    tmp = d / "meta.json.tmp"
    tmp.write_text(json.dumps(m))
    os.replace(tmp, f)
