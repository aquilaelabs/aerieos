#!/usr/bin/env bash
# What the supervisor asks about the dashboard, kept apart from its loop so
# it can be run by a test.

# dashboard_pid [STATE]: the pid of the server on STATE, printed, or nothing
# and a failure where none runs. By the pid the server leaves in
# STATE/.server.pid, held to a process that is there and is a server.py: the
# supervisor looked for 'dashboard/server.py' on any command line, which a
# test harness's copy and an editor on that file both answered to. Where no
# pid was ever left (a folder the server could not write), by that name, as
# before.
dashboard_pid() {
    local state="${1:-${DASHBOARD_STATE:-/config}}" pid
    if [ ! -e "$state/.server.pid" ]; then
        pid="$(pgrep -f 'dashboard/server\.py' 2>/dev/null | head -n 1 || true)"
        [ -n "$pid" ] || return 1
        printf '%s\n' "$pid"
        return 0
    fi
    pid="$(head -n 1 "$state/.server.pid" 2>/dev/null || true)"
    case "$pid" in ''|*[!0-9]*) return 1 ;; esac
    [ -r "/proc/$pid/cmdline" ] || return 1
    tr '\0' ' ' < "/proc/$pid/cmdline" 2>/dev/null | grep -q 'server\.py' || return 1
    printf '%s\n' "$pid"
}

# json_str TEXT: TEXT as the inside of a JSON string. A folder's name with a
# quote or a backslash in it spoiled the whole saved-sessions file, which was
# written with printf and nothing else.
json_str() {
    local s="$1"
    s="${s//\\/\\\\}"
    s="${s//\"/\\\"}"
    s="${s//$'\t'/\\t}"
    s="${s//$'\r'/\\r}"
    s="${s//$'\n'/\\n}"
    printf '%s' "$s" | tr -d '\000-\037'
}
