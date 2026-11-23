#!/usr/bin/env bash
# A release's controller bundle, packed the one way a tag's run and the
# rehearsal both pack it (R190 step 2): the tree at REF as the release
# carries it, with the commit's hash where the installer reads it
# (tree_stamp's .release-rev), and the agent's signature this run made,
# which is in no commit, beside the agent's sources where the controller
# reads it (scripts/agent/agent.sig, where it is here and not empty).
#
#   tools/release-pack.sh REF VERSION
#
# Writes aerieos-controller-VERSION.tar.gz and its .sha256 in the current
# folder and prints the bundle's name. Exits 1 where the bundle carries no
# dashboard, which is what an install runs.
set -euo pipefail
ref="${1:-}" ver="${2:-}"
[ -n "$ref" ] && [ -n "$ver" ] || { echo "usage: tools/release-pack.sh REF VERSION" >&2; exit 2; }
name="aerieos-controller-${ver}.tar.gz"
top="builderbot-${ver}"
work="$(mktemp -d)"
trap 'rm -rf "$work"' EXIT
git archive --format=tar --prefix="${top}/" "$ref" > "$work/tree.tar"
mkdir -p "$work/$top"
git rev-parse "$ref^{commit}" > "$work/$top/.release-rev"
tar -rf "$work/tree.tar" -C "$work" "$top/.release-rev"
if [ -s scripts/agent/agent.sig ]; then
    mkdir -p "$work/$top/scripts/agent"
    cp scripts/agent/agent.sig "$work/$top/scripts/agent/"
    tar -rf "$work/tree.tar" -C "$work" "$top/scripts/agent/agent.sig"
fi
gzip -n -9 < "$work/tree.tar" > "$name"
# Listed to a file and read from it: grep stopping at its first match ended
# tar mid-list, and with pipefail that read as no match (14 Nov).
tar -tzf "$name" > "$work/names"
grep -qx "${top}/scripts/dashboard/server.py" "$work/names" \
    || { echo "::error::the bundle has no scripts/dashboard/server.py" >&2; exit 1; }
sha256sum "$name" > "$name.sha256"
printf '%s\n' "$name"
