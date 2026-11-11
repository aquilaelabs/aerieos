#!/usr/bin/env bash
# One release per tag, a draft until its owner publishes it, and every file
# on that one release. GitHub's release-by-tag endpoint does not answer for
# a draft, and `gh release view TAG` fell back to the drafts inconsistently:
# v0.9.0-dev.4797 ended with two drafts, the apps on one and the OS image on
# the other (2 Nov). So the release is looked up among every release, drafts
# included, by its tag; created as a draft when there is none (a dev tag a
# pre-release and never the latest); and each file is uploaded to it by its
# id, an asset of the same name replaced. Every job that attaches a file
# calls this, so they cannot disagree about which release is the tag's.
#
#   tools/release-attach.sh TAG [--notes FILE] [--title TITLE] [--publish-when-whole LIST] [FILE...]
#
# Needs GH_TOKEN (what gh reads) and GITHUB_REPOSITORY. Prints the release's
# id, then each file as it lands. --notes and --title are used only when the
# release is made here; a release that exists keeps its own.
#
# --publish-when-whole LIST is the last job's (the operator, 11 Nov): a dev
# build's release goes out by itself, and only once every file LIST names
# (.release-files, @VER@ the version, * a pattern) is on it. Two dev builds
# were published by hand from the git host's own page minutes after their
# tags, which checks nothing, and one of them never got its image. Whole,
# the draft is published and the line says so; a file still missing after
# RELEASE_WAIT_S (the signed app is attached by a controller, on its own
# clock) is named, the release stays a draft and this exits 3. A release
# that is not a dev build is never published here: its owner reads it first.
set -euo pipefail

tag="${1:?tag}"; shift
notes="" title="$tag" whole=""
files=()
while [ $# -gt 0 ]; do
    case "$1" in
        --notes) notes="$2"; shift 2 ;;
        --title) title="$2"; shift 2 ;;
        --publish-when-whole) whole="$2"; shift 2 ;;
        *) files+=("$1"); shift ;;
    esac
done
repo="${GITHUB_REPOSITORY:?GITHUB_REPOSITORY}"

# The release with this tag, drafts included: every release listed, since
# GET /releases/tags/TAG does not see a draft.
find_release() {
    gh api "repos/$repo/releases?per_page=100" --paginate \
        --jq ".[] | select(.tag_name == \"$tag\") | .id" 2>/dev/null | head -1
}

# A draft published from GitHub's form with its tag field lost goes out
# under a name GitHub invents (untagged-ID) and a git tag of that name on the
# default branch (2 Nov, v0.9.0-dev.4818): nothing that reads releases by
# tag sees it, and the next job here would make a second release. One
# titled for this tag under such a name gets the tag back and the invented
# tag taken off, if the token may; its files and notes stay.
mend_untagged() {
    local row rid stray
    row="$(gh api "repos/$repo/releases?per_page=100" --paginate \
        --jq ".[] | select(.name == \"$tag\" and (.tag_name | startswith(\"untagged-\"))) | \"\\(.id) \\(.tag_name)\"" 2>/dev/null | head -1)"
    [ -n "$row" ] || return 1
    rid="${row%% *}"; stray="${row#* }"
    gh api --method PATCH "repos/$repo/releases/$rid" -f tag_name="$tag" >/dev/null || return 1
    gh api --method DELETE "repos/$repo/git/refs/tags/$stray" >/dev/null 2>&1 || true
    echo "release $rid was published as $stray: its tag set back to $tag" >&2
    echo "$rid"
}

id="$(find_release || true)"
[ -n "$id" ] || id="$(mend_untagged || true)"
if [ -z "$id" ]; then
    pre=(--draft)
    # Any name after the version is a pre-release: -dev.N, -rc.N (R218).
    case "$tag" in v*-*) pre+=(--prerelease --latest=false) ;; esac
    if [ -n "$notes" ]; then
        gh release create "$tag" --repo "$repo" --verify-tag "${pre[@]}" --title "$title" --notes-file "$notes" >/dev/null
    else
        gh release create "$tag" --repo "$repo" --verify-tag "${pre[@]}" --title "$title" --notes "AerieOS ${tag#v}: see CHANGELOG.md." >/dev/null
    fi
    # Created a moment ago, which the list may not show at once.
    for _ in 1 2 3 4 5 6; do
        id="$(find_release || true)"
        [ -n "$id" ] && break
        sleep 5
    done
    [ -n "$id" ] || { echo "release-attach: made the release for $tag and cannot find it" >&2; exit 1; }
    echo "release $id made for $tag (a draft)"
else
    echo "release $id is $tag's"
fi

for f in "${files[@]}"; do
    name="$(basename "$f")"
    # An asset of the same name goes first: the uploads API refuses a duplicate.
    for aid in $(gh api "repos/$repo/releases/$id/assets?per_page=100" --paginate \
                   --jq ".[] | select(.name == \"$name\") | .id"); do
        gh api --method DELETE "repos/$repo/releases/assets/$aid" >/dev/null
    done
    gh api --method POST -H "Content-Type: application/octet-stream" \
        "https://uploads.github.com/repos/$repo/releases/$id/assets?name=$name" --input "$f" >/dev/null
    echo "  $name"
done

[ -n "$whole" ] || exit 0
case "$tag" in
    v*-dev.*) ;;
    *) echo "release $id is not a dev build's: it stays a draft for its owner to read and publish"; exit 0 ;;
esac
[ -f "$whole" ] || { echo "release-attach: no list of the release's files at $whole" >&2; exit 2; }
ver="${tag#v}"
mapfile -t want < <(sed -e 's/[[:space:]]*$//' -e '/^[[:space:]]*#/d' -e '/^$/d' -e "s|@VER@|$ver|g" "$whole")
[ "${#want[@]}" -gt 0 ] || { echo "release-attach: $whole names no file" >&2; exit 2; }
missing=()
end=$(( $(date +%s) + ${RELEASE_WAIT_S:-900} ))
while :; do
    mapfile -t have < <(gh api "repos/$repo/releases/$id/assets?per_page=100" --paginate --jq '.[].name')
    missing=()
    for w in "${want[@]}"; do
        found=""
        for h in "${have[@]}"; do
            # shellcheck disable=SC2053  # the list's names are patterns
            [[ "$h" == $w ]] && { found=1; break; }
        done
        [ -n "$found" ] || missing+=("$w")
    done
    [ "${#missing[@]}" -eq 0 ] && break
    [ "$(date +%s)" -lt "$end" ] || break
    sleep "${RELEASE_POLL_S:-30}"
done
if [ "${#missing[@]}" -gt 0 ]; then
    echo "release $id is not whole: ${missing[*]} still missing, so it stays a draft" >&2
    exit 3
fi
if [ "$(gh api "repos/$repo/releases/$id" --jq '.draft')" != "true" ]; then
    echo "release $id was published already, whole now (${#want[@]} files)"
    exit 0
fi
# The tag goes with it: GitHub drops a draft's tag patched without one.
gh api --method PATCH "repos/$repo/releases/$id" -F draft=false -F prerelease=true -f make_latest=false -f tag_name="$tag" >/dev/null
echo "release $id published: whole (${#want[@]} files)"
