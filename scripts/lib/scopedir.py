"""Where an account keeps what it has for one space on this machine.

    scope_dir(project, *parts)

bb-tty writes a session's launcher, its scope and its token into that
folder, bbapi a renewed token and the word that the controller went quiet,
and the hooks their stamps and what they were told; each reader has to look
where the writer wrote, so the path is built here and nowhere else in
Python (bb_scope_dir in common.sh is the shell's). A file of its own, and
this small, because bb-gate asks for the path on every tool call of every
session: it loads nothing else to have it.
"""
import os


def scope_dir(project, *parts):
    """This account's AerieOS cache folder for `project`, or the path
    `parts` name under it. The account is in the path on purpose: on
    a node every account's ~/.cache is a link to the base home's, so the id
    is all that separates one account's files from another's. With no home
    to keep it under, a folder of this user's own in /tmp."""
    home = os.environ.get("HOME", "")
    base = os.environ.get("XDG_CACHE_HOME") or (home and os.path.join(home, ".cache")) \
        or f"/tmp/bb-scope-{os.getuid()}"
    return os.path.join(base, "builderbot", "u", os.environ.get("BB_ACCOUNT_UID") or "_none",
                        "project", project, *parts)
