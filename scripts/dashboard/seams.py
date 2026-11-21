"""The seams into the controller that only a test or a tool of the tree's
own needs, read in this one place.

A few checks and programs have a stand-in for a test: a pack fetched from
a repository on disk where a controller only ever fetches one over https,
the services' images or the registry's digests read from a file, another
file of who may sign a release, a stub in docker's or cloudflared's place.
Each is a variable in the process's environment (SEAMS names every one,
with what it stands in for), and each is read only where this file is
AerieOS's own source tree's (IN_TREE): the tree's Dockerfile and its
tools/ beside it, which an image's /opt/aerieos does not hold (the
Dockerfile copies neither) and a bare-metal install's does not either (it
lays out what the Dockerfile copies, with the Dockerfile and none of
tools/). The browser suites' harness runs the server from a copy of the
tree, a unit test runs in the tree, and the tools that read a checkout of
the catalog in a pack's place load a release's source tree, so each is
read there. It is where the file is, which nothing in an environment says:
the harness's whole block of variables, pasted into an install's
environment, turns no check off and swaps no trust root. What an install
can set is what docs/reference.md lists. Stdlib only, and no import from
the rest of the dashboard.
"""
import os
import re

_HERE = os.path.dirname(os.path.realpath(__file__))
_TOP = os.path.join(_HERE, "..", "..")
IN_TREE = os.path.isfile(os.path.join(_TOP, "Dockerfile")) and os.path.isdir(os.path.join(_TOP, "tools"))

# Every seam, with what it stands in for.
SEAMS = {
    "BB_TOOLPACKS_FILE_URLS": "a pack fetched from a repository on disk (file://), where a controller fetches one over https alone",
    "BB_SERVICE_IMAGES_FILE": "the services' images read from another file than the shipped service-images.json",
    "BB_RELEASE_SIGNERS": "who may sign a release's files: another file than the shipped config/release-signers",
    "BB_APPS_RELEASES_URL": "where AerieOS's releases are asked for, GitHub's API in an install's place",
    "BB_IMAGE_DIGESTS_FILE": "the digests a registry would answer for an image, read from a file",
    "BB_DOCKER_BIN": "the docker program a dev instance and a container run with",
    "BB_CLOUDFLARED": "the cloudflared program the home tunnel runs",
    "BB_TUNNEL_ROUTE_BASE": "where a tunnel's name is asked whether it reaches this controller",
    "BB_BIN": "the aerie program the toolchain worker runs",
    "BB_AGENT_DIR": "the agent's sources a test world's controller ships, a copy of its own in the tree's place",
    "BB_ACME_DIRECTORY": "the ACME directory certificates are asked of (a staging one), Let's Encrypt's in an install's place",
    "BB_RELEASE_IMAGE": "AerieOS's own image as a registry names it, held to the signed release's digest",
    "BB_SECRETS_CARRY": "the root helper a move asks for root's secrets, run with no sudo and on any machine",
    "BB_CMDLINE": "the kernel's command line Safe mode is read from, /proc/cmdline's in an install's place",
}
# ...and one a coding agent: where its newest release is asked, a file://
# stand-in for its registry's answer (BB_CLAUDE_LATEST_URL and the like).
LATEST = re.compile(r"BB_[A-Z0-9_]+_LATEST_URL")


def get(name, default=""):
    """What the seam `name` is set to in the source tree, else `default`:
    never anything an install's environment says."""
    if name not in SEAMS and not LATEST.fullmatch(name):
        raise KeyError(name)
    return (os.environ.get(name) or default) if IN_TREE else default


def latest_url(agent_id):
    """A coding agent's stand-in for where its newest release is asked, or ""."""
    return get("BB_" + re.sub(r"[^A-Z0-9]", "_", str(agent_id).upper()) + "_LATEST_URL")
