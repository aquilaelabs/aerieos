#!/usr/bin/env bash
# held-run.sh NAME [KEY=VALUE...]: one entry's steps, run from what the entry
# declares and from nothing else.
#
# The entry is read from standard input, a catalog of one row: NAME's
# source with what it downloads (fetch, keyring), what its steps keep
# (online, or offline) and the steps themselves (steps, each a list of
# words). It is how a node installs a coding agent from the recipe its
# controller hands it (the agent's sessions.agent_install): a row that is in
# no catalog on disk, run as the session account into its home.
#
# One mechanism, sdk.sh's own (sdk_declared): each download is fetched over
# https into a directory made for this run and held to its sha256 or its
# publisher's signature before anything runs, and the steps then run with
# no network, or with it where the entry says online. {dir} in a step is
# that directory, and each KEY=VALUE fills {KEY} ({home}, {version}). The
# directory is gone when this ends, however it ends.
#
# What it exits with:
#   0   every step ran
#   65  a declared download could not be fetched, or the entry could not be read: nothing ran
#   66  a declared download answered other bytes than its entry holds: nothing ran
#   1   a step failed
set -euo pipefail

BB_SCRIPTS="$(readlink -f "$0")"
BB_SCRIPTS="${BB_SCRIPTS%/lib/*}"
# shellcheck source=lib/common.sh
. "$BB_SCRIPTS/lib/common.sh"
# shellcheck source=lib/sdk.sh
. "$BB_SCRIPTS/lib/sdk.sh"

[ "$#" -ge 1 ] || die "usage: held-run.sh NAME [KEY=VALUE...] < the entry, a catalog of one row"
what="$1"; shift

# The run's own directory, under the account's home: an installer may be
# large, and /tmp is memory on many machines.
base="${HOME:-/tmp}/.cache" made=""
[ -d "$base" ] || made=1
mkdir -p "$base" 2>/dev/null || { base="${TMPDIR:-/tmp}"; made=""; }
top="$(mktemp -d "${base}/aerie-held.XXXXXX")" || die "${what}: no directory to fetch into"
stage="read"
held_end() {
    local rc=$?
    rm -rf "$top"
    # ...and the folder it stood in, where this run made it and nothing else is in it.
    [ -z "$made" ] || rmdir "$base" 2>/dev/null || true
    # Before a step ran, the exit says which it was: a file that is not what
    # the entry holds, or anything else that kept the downloads from being had.
    if [ "$rc" != 0 ] && [ "$stage" != run ]; then
        if [ -n "${SDK_NOT_HELD:-}" ]; then exit 66; fi
        exit 65
    fi
    exit "$rc"
}
trap held_end EXIT
mkdir -p "$top/dir" "$top/tmp"
export TMPDIR="$top/tmp"
export BB_TOOLCHAINS_JSON="$top/entry.json"
cat > "$BB_TOOLCHAINS_JSON"
exec < /dev/null
d="$top/dir"

# What the entry declares, fetched and held; SDK_CUT is then the words its
# steps run behind.
stage="fetch"
sdk_declared "$what" "$d"
[ -n "$SDK_DECLARED" ] || die "${what}: its entry declares nothing of what it downloads: nothing is run"

stage="run"
i=0
while :; do
    cmd=()
    sdk_meta_into cmd argv "$what" "source.steps.${i}" "dir=$d" "$@"
    [ "${#cmd[@]}" != 0 ] || break
    log "running ${cmd[*]//$d/\{dir\}}"
    "${SDK_CUT[@]}" "${cmd[@]}" \
        || die "${what}: a step failed${SDK_CUT[*]:+ (it ran with no network: what it installs from is declared in its entry)}"
    i=$((i + 1))
done
[ "$i" != 0 ] || die "${what}: its entry names no step to run"
