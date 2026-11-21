#!/usr/bin/env bash
# Where a release may be cut from (the operator, 14 Nov): a dev build
# (vX.Y.Z-dev.N) on a commit that is on one of the branches a release is
# cut from (tools/release-branches: main, and a release's working branch);
# a stable release (vX.Y.Z) or a release candidate (vX.Y.Z-rc.N, any other
# name after the version) only on a commit that is on main. So a tag on a
# commit no such branch holds (a stray branch, a commit pushed nowhere but
# under the tag) is refused before anything is signed for it.
#
#   tools/release-place.sh TAG [COMMIT] [MAIN] [BRANCHES]
#
# COMMIT is the tag's commit (HEAD when not given), MAIN the ref that main
# is here (origin/main when not given), BRANCHES the list of branches (the
# file beside this script when not given). The caller fetches the remote's
# branch heads first: a branch is read as MAIN's remote holds it. Exit 0
# and one line saying what the tag is and why it may go on; exit 1 and why
# not; exit 2 for a name that is no release's.
#
# Every pattern here and in the list is an extended regular expression a
# name matches whole, never a shell glob: a glob's * matches a slash and
# any text after it, so claude/[0-9]*.[0-9]*.[0-9]* took claude/1.2.3/x and
# claude/1x.2.3-anything, names anybody who may push a branch can make.
set -u

tag="${1:-}"
commit="${2:-HEAD}"
main="${3:-origin/main}"
branches="${4:-$(dirname "$0")/release-branches}"
[[ "$tag" =~ ^v[0-9] ]] \
    || { echo "not a release's tag: ${tag:-nothing} (vX.Y.Z, vX.Y.Z-dev.N or vX.Y.Z-rc.N)" >&2; exit 2; }
ver="${tag#v}"
base="${ver%%-*}"
[[ "$base" =~ ^[0-9]+\.[0-9]+\.[0-9]+$ ]] \
    || { echo "not a release's tag: $tag (its version is not MAJOR.MINOR.PATCH)" >&2; exit 2; }
kind=stable
if [ "$ver" = "$base" ]; then
    :
elif [[ "${ver#"$base"}" =~ ^-dev\.[0-9]+$ ]]; then
    kind=dev
elif [[ "${ver#"$base"}" =~ ^-([a-z]+)\.[0-9]+$ ]]; then
    kind="a ${BASH_REMATCH[1]} pre-release"
else
    echo "not a release's tag: $tag (after the version comes -dev.N or -NAME.N)" >&2; exit 2
fi
sha="$(git rev-parse --verify --quiet "$commit^{commit}")" \
    || { echo "$tag: no commit called $commit here" >&2; exit 1; }
if [ "$kind" = dev ]; then
    [ -r "$branches" ] || { echo "$tag is a dev build, and the list of branches a release is cut from is not here ($branches)" >&2; exit 1; }
    remote="${main%%/*}"
    listed=""
    while IFS= read -r pat; do
        case "$pat" in ''|'#'*) continue ;; esac
        listed="${listed:+$listed, }$pat"
        while IFS= read -r ref; do
            name="${ref#"$remote"/}"
            # The whole name, by the line read as an extended regular expression.
            if [[ "$name" =~ ^(${pat})$ ]] && git merge-base --is-ancestor "$sha" "$ref" 2>/dev/null; then
                echo "$tag is a dev build, and its commit ${sha:0:7} is on $name"
                exit 0
            fi
        done < <(git for-each-ref --format='%(refname:short)' "refs/remotes/$remote/")
    done < "$branches"
    echo "$tag is a dev build, and its commit ${sha:0:7} is on no branch a release is cut from as $remote holds them ($listed): push the branch first, or tag a commit that is on one" >&2
    exit 1
fi
tip="$(git rev-parse --verify --quiet "$main^{commit}")" \
    || { echo "$tag is ${kind/stable/a stable release}, which is cut from main, and $main is not known here (fetch it first)" >&2; exit 1; }
if git merge-base --is-ancestor "$sha" "$tip"; then
    echo "$tag is ${kind/stable/a stable release}, and its commit ${sha:0:7} is on main"
    exit 0
fi
echo "$tag is ${kind/stable/a stable release}, which is cut from main, and its commit ${sha:0:7} is not on main (${tip:0:7}): merge the branch into main and tag there, or cut a dev build (vX.Y.Z-dev.N) from the branch" >&2
exit 1
