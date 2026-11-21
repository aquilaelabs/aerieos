#!/usr/bin/env bash
# held-run.sh [--fetch TOP | --run TOP] NAME [KEY=VALUE...]: one entry's
# steps, run from what the entry declares and from nothing else.
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
# The cut is the account's own to make where the machine lets it
# (sdk_net_cut). Where it does not, a caller that is root makes it instead,
# and the install is two runs of this, both as the account:
#
#   --fetch TOP   with the network: the entry is read, and what it declares
#                 is fetched and held into TOP, a directory this run makes
#                 and, where every download is held, leaves. Nothing runs.
#   --run TOP     started by root inside the cut it made, as the account
#                 again and with no way back: the entry is the one TOP
#                 holds, nothing is fetched, and the steps run. This run
#                 checks for itself that it has no network (sdk.sh
#                 SDK_CUT_MADE) and runs nothing where it has one. TOP is
#                 gone when it ends.
#
# TOP is a directory of the account's own, by name and by owner: this
# never reads an entry or runs a step from one that is somebody else's.
#
# What it exits with:
#   0   every step ran (--fetch: every download is held)
#   65  a declared download could not be fetched, or the entry could not be read: nothing ran
#   66  a declared download answered other bytes than its entry holds: nothing ran
#   1   a step failed, or --run was given no directory of this account's to run from
set -euo pipefail

BB_SCRIPTS="$(readlink -f "$0")"
BB_SCRIPTS="${BB_SCRIPTS%/lib/*}"
# shellcheck source=lib/common.sh
. "$BB_SCRIPTS/lib/common.sh"
# shellcheck source=lib/sdk.sh
. "$BB_SCRIPTS/lib/sdk.sh"

phase="" top=""
case "${1:-}" in
    --fetch|--run)
        phase="${1#--}" top="${2:-}"
        shift 2 || die "usage: held-run.sh [--fetch TOP | --run TOP] NAME [KEY=VALUE...]"
        case "$top" in
            /*/aerie-held.*) ;;
            *) die "held-run.sh: ${top:-no directory} is not a run's own directory (.../aerie-held.NAME)" ;;
        esac ;;
esac
[ "$#" -ge 1 ] || die "usage: held-run.sh [--fetch TOP | --run TOP] NAME [KEY=VALUE...] < the entry, a catalog of one row"
what="$1"; shift

# The run's own directory, under the account's home: an installer may be
# large, and /tmp is memory on many machines.
base="" made="" stage="read" keep=""
held_end() {
    local rc=$?
    # Left for the run that follows only by a fetch that held everything.
    if [ -z "$keep" ] || [ "$rc" != 0 ]; then rm -rf "$top"; fi
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
if [ "$phase" = run ]; then
    # What the first run left: this account's own directory, and no link to
    # one. Anything else is not run from, and not removed.
    stage="run"
    if [ ! -d "$top" ] || [ -L "$top" ] || [ ! -O "$top" ] || [ ! -f "$top/entry.json" ] || [ ! -d "$top/dir" ]; then
        die "${what}: ${top} is not a directory this account fetched into: nothing is run"
    fi
    trap held_end EXIT
    # Root started this from its own directory: the steps start where a
    # run started as the account does, in its home.
    cd "${HOME:-/}" 2>/dev/null || cd /
else
    if [ -n "$top" ]; then
        base="$(dirname "$top")"
        [ -d "$base" ] || made=1
        # Made here and new: one that is there already is not this run's.
        if ! mkdir -p "$base" || ! mkdir -m 700 "$top"; then
            die "${what}: no directory to fetch into at ${top}"
        fi
        keep=1
    else
        base="${HOME:-/tmp}/.cache"
        [ -d "$base" ] || made=1
        mkdir -p "$base" 2>/dev/null || { base="${TMPDIR:-/tmp}"; made=""; }
        top="$(mktemp -d "${base}/aerie-held.XXXXXX")" || die "${what}: no directory to fetch into"
    fi
    trap held_end EXIT
    mkdir -p "$top/dir" "$top/tmp"
    cat > "$top/entry.json"
fi
export TMPDIR="$top/tmp"
# The row this run was handed is the catalog it reads (sdk.sh SDK_CATALOG).
# shellcheck disable=SC2034  # sdk.sh's own, which sdk_meta reads
SDK_CATALOG="$top/entry.json"
exec < /dev/null
d="$top/dir"

# What the entry declares, fetched and held; SDK_CUT is then the words its
# steps run behind. In two runs: the first fetches and holds and ends
# there; the second fetches nothing, and says the cut is made around it.
# shellcheck disable=SC2034  # sdk.sh's own, which sdk_declared and sdk_net_cut read
if [ "$phase" = run ]; then
    SDK_PHASE="run" SDK_CUT_MADE=1
else
    stage="fetch"
    SDK_PHASE="$phase"
fi
sdk_declared "$what" "$d"
[ -n "$SDK_DECLARED" ] || die "${what}: its entry declares nothing of what it downloads: nothing is run"
[ "$phase" != fetch ] || exit 0

stage="run"
cut=""
if [ "$(head -n 1 "$d/.bb-net" 2>/dev/null)" = cut ]; then cut=1; fi
i=0
while :; do
    cmd=()
    sdk_meta_into cmd argv "$what" "source.steps.${i}" "dir=$d" "$@"
    [ "${#cmd[@]}" != 0 ] || break
    log "running ${cmd[*]//$d/\{dir\}}"
    "${SDK_CUT[@]}" "${cmd[@]}" \
        || die "${what}: a step failed${cut:+ (it ran with no network: what it installs from is declared in its entry)}"
    i=$((i + 1))
done
[ "$i" != 0 ] || die "${what}: its entry names no step to run"
