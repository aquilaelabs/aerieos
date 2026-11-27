"""State 42 to 43: everything sealed under the install key is sealed once
more, so nothing is left in the seal format from before 27 Oct (BBSEAL1).

Migration 0014 moved the seal to ChaCha20-Poly1305 and left the rewriting
to the passes the start runs, but only the signing keys' pass rewrote the
old format: a git token, a setting's secret, a two-factor secret or any
other seal from before stayed as it was, opened only through the reader of
the old format, which therefore could not go (B1190). Sealing needs the
install key, which a migration is not handed, so this one asks for it: the
file `seal-again` in the state, which the start reads once the migrations
have run (installkey.settle) and answers with one round of every pass
under today's key, each sealing what it opens in the format of today and
leaving what it cannot open as it is, then removing the file.

Idempotent: asked twice, the round runs twice and seals the same things.
Never edited once shipped (stateversion.py).
"""
from pathlib import Path


def run(ctx):
    (Path(ctx["state"]) / "seal-again").write_text("written by migration 0043: every seal once more in today's format\n")
