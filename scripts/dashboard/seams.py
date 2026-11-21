"""The seams into the controller that only a test or a tool of the tree's
own needs, honored in one place.

A few checks have a way around them: a pack fetched from a repository on
disk where a controller only ever fetches one over https
(BB_TOOLPACKS_FILE_URLS=1), the services' images read from another file
than the shipped one (BB_SERVICE_IMAGES_FILE). Each is a variable in the
process's environment, and each is honored only beside one marker,
BB_SEAMS=1, which says the process is not an install's: the browser
suites' harness sets it for the server it starts
(scripts/dashboard/test/run.sh), a unit test for itself, and the tools that
read a checkout of the catalog in a pack's place (tools/packs-export.py,
the catalog's own check). So a seam's variable alone, left or put in an
install's environment, turns no check off, and what an install can set is
what docs/reference.md lists. Stdlib only, and no import from the rest of
the dashboard.
"""
import os

MARK = "BB_SEAMS"
NAMES = ("BB_TOOLPACKS_FILE_URLS", "BB_SERVICE_IMAGES_FILE")


def on():
    """Whether this process said its seams are open."""
    return os.environ.get(MARK) == "1"


def get(name):
    """What the seam `name` is set to, "" where the marker is not beside it."""
    if name not in NAMES:
        raise KeyError(name)
    return os.environ.get(name, "") if on() else ""
