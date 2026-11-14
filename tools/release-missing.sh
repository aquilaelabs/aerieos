#!/usr/bin/env bash
# What a release still lacks: each file the list names that is not among
# the names given, one a line; nothing when it is whole.
#
#   tools/release-missing.sh LIST VERSION [NAME...]
#
# LIST is .release-files: one file a line, @VER@ the release's version
# (0.9.0, 0.9.0-dev.4501) and * a shell pattern, # a comment. One reading
# of it for the job that publishes a dev build once it is whole
# (tools/release-attach.sh) and for the rehearsal, which says the same of
# the files a branch built (release-rehearsal.yml). Exits 2 when the list
# cannot be read or names nothing.
set -euo pipefail

list="${1:?list}"; ver="${2:?version}"; shift 2
[ -f "$list" ] || { echo "release-missing: no list of the release's files at $list" >&2; exit 2; }
mapfile -t want < <(sed -e 's/[[:space:]]*$//' -e '/^[[:space:]]*#/d' -e '/^$/d' -e "s|@VER@|$ver|g" "$list")
[ "${#want[@]}" -gt 0 ] || { echo "release-missing: $list names no file" >&2; exit 2; }
for w in "${want[@]}"; do
    found=""
    for h in "$@"; do
        # shellcheck disable=SC2053  # the list's names are patterns
        [[ "$h" == $w ]] && { found=1; break; }
    done
    [ -n "$found" ] || printf '%s\n' "$w"
done
exit 0
