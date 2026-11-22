#!/bin/sh
# The agent's version is the one number in this tree a person moves by hand,
# and a node compares the FILE while the Nodes tab names the NUMBER: when the
# file moved without it, three tabs said "runs 0.6.92 and ships 0.6.92" and
# refused work (B221). So the agent (scripts/agent: the entry and the
# aerieos_agent package, which a node gets as one zip) may not change
# against the branch's base without AGENT_VERSION's patch moving.
#
# The base is the last commit that moved the number, so every change to the
# agent after one bump needs the next: measured from origin/main's merge
# point, one bump early on a long branch passed every change after it (the
# audit of 13 Nov: fe36377 changed the agent with no bump, 226 commits into
# a branch). Where history does not hold that commit (a shallow checkout),
# the previous commit; a tree with no base to compare is said, not passed.
# Run by `aerie lint` and by the lint workflow, so the two agree.
# Exit 0 clean, 1 on a finding, 0 with [skip] when it cannot compare.
set -eu
f=scripts/agent
v=scripts/agent/aerieos_agent/__init__.py
if [ ! -f "$v" ] || ! git rev-parse --is-inside-work-tree >/dev/null 2>&1; then
    echo "  [skip] no agent here, or not a git tree"; exit 0
fi
base="$(git log -1 --format=%H -G'^AGENT_VERSION = ' -- "$v" 2>/dev/null || true)"
if [ -z "$base" ] && git rev-parse --verify -q HEAD~1 >/dev/null 2>&1; then
    base="HEAD~1"
fi
if [ -z "$base" ]; then
    echo "  [skip] no base to compare the agent against (a shallow checkout with one commit)"; exit 0
fi
short="$(git rev-parse --short "$base" 2>/dev/null || echo "$base")"
# What a node runs: the entry and the package (not the ruff pin beside them).
if git diff --quiet "$base" -- "$f/builderbot-agent.py" "$f/aerieos_agent" 2>/dev/null; then
    echo "  [ok]   the agent is as it was when its version last moved ($short)"; exit 0
fi
now="$(grep '^AGENT_VERSION = ' "$v" | head -n 1)"
# grep reads the whole stream: an early close under git show is SIGPIPE, and
# a pipefail shell then ends the caller without a word.
# (before the split the number was in the one file, so the base may have it there)
then_="$( { git show "$base:$v" 2>/dev/null || git show "$base:$f/builderbot-agent.py" 2>/dev/null; } \
         | grep '^AGENT_VERSION = ' || true)"
then_="$(printf '%s\n' "$then_" | head -n 1)"
if [ -n "$now" ] && [ "$now" != "$then_" ]; then
    echo "  [ok]   the agent changed and its version moved with it (${now#AGENT_VERSION = }, was ${then_#AGENT_VERSION = })"; exit 0
fi
echo "  [FAIL] the agent ($f) changed since $short and AGENT_VERSION (${now#AGENT_VERSION = }) did not: a node compares the file and the row names the number, so bump the patch (measured from the commit that last moved it)"
exit 1
