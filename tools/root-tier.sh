#!/usr/bin/env bash
# The root tier (scripts/lib/roottier.py) as root in a throwaway container:
# what the root agent and the root helpers do in a folder an account
# controls, which only root sees for real and the browser harness refuses
# to be.
#
#   tools/root-tier.sh [--tree DIR] [IMAGE] [MODULE...]
#
# IMAGE is a controller image docker can run (the published dev build when
# none is named). By itself the tier is the image's own copy, which is what
# ships: a release's workflow runs it so on the image it just built. With
# --tree the tier is DIR's, copied into the container, and the image is
# only where it runs (python, git, tmux and an ordinary account): a pull
# request and a session's `aerie tests root` run it so. Nothing is mounted
# for writing and the container is removed; exits as the tier does.
set -u

tree=""
if [ "${1:-}" = --tree ]; then
    [ -n "${2:-}" ] || { echo "usage: tools/root-tier.sh [--tree DIR] [IMAGE] [MODULE...]" >&2; exit 2; }
    tree="$(cd "$2" && pwd)" || exit 2
    shift 2
fi
image="${1:-ghcr.io/aquilaelabs/aerieos:dev}"
[ $# -gt 0 ] && shift
command -v docker >/dev/null 2>&1 || { echo "the root tier runs in a container, and there is no docker here" >&2; exit 2; }

if [ -z "$tree" ]; then
    exec docker run --rm --user 0 --entrypoint python3 "$image" /opt/aerieos/scripts/lib/roottier.py "$@"
fi
[ -f "$tree/scripts/lib/roottier.py" ] || { echo "no root tier in $tree" >&2; exit 2; }
# A copy inside the container, readable by its accounts whatever the
# checkout's own modes are: the tree is laid out there as the image lays
# its own (scripts beside nodes).
# shellcheck disable=SC2016  # the container's shell expands these, not this one
exec docker run --rm --user 0 --entrypoint sh -v "$tree:/src:ro" "$image" -c '
    mkdir -p /tier/nodes && cp -r /src/scripts /tier/scripts && cp /src/nodes/bb-session /tier/nodes/bb-session \
        && chmod -R a+rX /tier || exit 2
    exec python3 /tier/scripts/lib/roottier.py "$@"' root-tier "$@"
