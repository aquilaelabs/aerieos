#!/usr/bin/env bash
# Where a release may be cut from (the operator, 14 Nov): a dev build
# (vX.Y.Z-dev.N) is tagged on the branch it was built on; a stable release
# (vX.Y.Z) or a release candidate (vX.Y.Z-rc.N, any other name after the
# version) only on a commit that is on main. Nothing checked it: the six
# newest tags sat on the working branch, and a stable one could have.
#
#   tools/release-place.sh TAG [COMMIT] [MAIN]
#
# COMMIT is the tag's commit (HEAD when not given), MAIN the ref that main
# is here (origin/main when not given; the caller fetches it). Exit 0 and
# one line saying what the tag is and why it may go on; exit 1 and why not;
# exit 2 for a name that is no release's.
set -u

tag="${1:-}"
commit="${2:-HEAD}"
main="${3:-origin/main}"
case "$tag" in
    v[0-9]*.[0-9]*.[0-9]*) ;;
    *) echo "not a release's tag: ${tag:-nothing} (vX.Y.Z, vX.Y.Z-dev.N or vX.Y.Z-rc.N)" >&2; exit 2 ;;
esac
ver="${tag#v}"
base="${ver%%-*}"
printf '%s' "$base" | grep -Eq '^[0-9]+\.[0-9]+\.[0-9]+$' \
    || { echo "not a release's tag: $tag (its version is not MAJOR.MINOR.PATCH)" >&2; exit 2; }
kind=stable
case "$ver" in
    "$base") ;;
    "$base"-dev.[0-9]*) kind=dev ;;
    "$base"-[a-z]*.[0-9]*) kind="a ${ver#"$base"-}"; kind="${kind%%.*} pre-release" ;;
    *) echo "not a release's tag: $tag (after the version comes -dev.N or -NAME.N)" >&2; exit 2 ;;
esac
sha="$(git rev-parse --verify --quiet "$commit^{commit}")" \
    || { echo "$tag: no commit called $commit here" >&2; exit 1; }
if [ "$kind" = dev ]; then
    echo "$tag is a dev build: tagged on the branch it was built on (${sha:0:7})"
    exit 0
fi
tip="$(git rev-parse --verify --quiet "$main^{commit}")" \
    || { echo "$tag is ${kind/stable/a stable release}, which is cut from main, and $main is not known here (fetch it first)" >&2; exit 1; }
if git merge-base --is-ancestor "$sha" "$tip"; then
    echo "$tag is ${kind/stable/a stable release}, and its commit ${sha:0:7} is on main"
    exit 0
fi
echo "$tag is ${kind/stable/a stable release}, which is cut from main, and its commit ${sha:0:7} is not on main (${tip:0:7}): merge the branch into main and tag there, or cut a dev build (vX.Y.Z-dev.N) from the branch" >&2
exit 1
