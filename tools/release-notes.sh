#!/usr/bin/env bash
# A release's notes, written the one way a tag's run and the rehearsal both
# write them, on stdout. At the top, which download is for
# what (docs/release-notes/downloads.md: the files
# alone did not say). Then the tree's own notes for this version where it
# has them (docs/release-notes/X.Y.Z.md, or X.Y.Z-dev.md for a dev build),
# else the changelog's: for a pre-release what is new since the release
# before (tools/release-notes.py), for a release its section. @TAG@, @VER@
# and @REPO@ are filled in, so the release is made with them rather than
# edited after.
#
#   tools/release-notes.sh TAG REPO
#
# TAG names a commit here: a tag's run is on it, and a rehearsal tags its
# own commit in its checkout alone, pushing nothing.
set -euo pipefail
tag="${1:-}" repo="${2:-}"
[ -n "$tag" ] && [ -n "$repo" ] || { echo "usage: tools/release-notes.sh TAG REPO" >&2; exit 2; }
ver="${tag#v}"
base="${ver%%-*}"
notes="docs/release-notes/$base.md"
case "$tag" in v*-*) notes="docs/release-notes/$base-dev.md" ;; esac
fill() { sed -e "s|@TAG@|$tag|g" -e "s|@VER@|$ver|g" -e "s|@REPO@|$repo|g" "$1"; }
if [ -f docs/release-notes/downloads.md ]; then
    fill docs/release-notes/downloads.md
fi
if [ -f "$notes" ]; then
    fill "$notes"
elif [ "$ver" != "$base" ]; then
    python3 tools/release-notes.py "$tag"
else
    said="$(awk -v h="## $base:" 'index($0, h) == 1 {on = 1; next} on && /^## / {exit} on' CHANGELOG.md)"
    if printf '%s' "$said" | grep -q '[^[:space:]]'; then
        printf '%s\n' "$said"
    else
        echo "AerieOS $ver: see CHANGELOG.md."
    fi
fi
