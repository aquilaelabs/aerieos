"""State 23 to 24: the stamp alone, for the database's migration 0008.

A token's state moved to a column of its own and the revoked column went,
which db.py's own migration does as the store opens. Nothing is changed
here: the state moves so that a copy of /config is taken before it, and so
that a build from before this one refuses to start on a database it would
read wrongly, saying so, as for any other state it does not know.
Idempotent. Never edited once shipped (stateversion.py).
"""


def run(ctx):
    return
