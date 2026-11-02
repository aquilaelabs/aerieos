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
#   tools/release-attach.sh TAG [--notes FILE] [--title TITLE] [FILE...]
#
# Needs GH_TOKEN (what gh reads) and GITHUB_REPOSITORY. Prints the release's
# id, then each file as it lands. --notes and --title are used only when the
# release is made here; a release that exists keeps its own.
set -euo pipefail

tag="${1:?tag}"; shift
notes="" title="$tag"
files=()
while [ $# -gt 0 ]; do
    case "$1" in
        --notes) notes="$2"; shift 2 ;;
        --title) title="$2"; shift 2 ;;
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

id="$(find_release || true)"
if [ -z "$id" ]; then
    pre=(--draft)
    case "$tag" in *-dev.*) pre+=(--prerelease --latest=false) ;; esac
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
