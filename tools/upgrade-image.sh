#!/usr/bin/env bash
# The built image started on each release snapshot of /config, through its
# own entrypoint and startup hooks: what the upgrade suite cannot reach,
# since it starts server.py alone with stand-ins for everything outside it.
# A person's update is this: the new image, the /config the old one left.
#
#   tools/upgrade-image.sh IMAGE [SNAPSHOT...]
#
# IMAGE is a controller image docker can run (a tag or a digest). Each
# SNAPSHOT is a folder of scripts/dashboard/test/upgrade/ (all of them when
# none is named). For each: its config.tar.gz is unpacked into a scratch
# folder, the image is started on it as an install starts it, and it passes
# when the dashboard answers, /config's stamp is the image's own state, a
# copy was taken where the state moved, and the owner signs in with the
# password the manifest gives. A snapshot older than the image migrates from
# is said and skipped. Exits 1 when one fails, with the container's log.
set -u

image="${1:-}"
[ -n "$image" ] || { echo "usage: tools/upgrade-image.sh IMAGE [SNAPSHOT...]" >&2; exit 2; }
shift
root="$(cd "$(dirname "$0")/.." && pwd)"
snaps=("$@")
if [ "${#snaps[@]}" -eq 0 ]; then
    for d in "$root"/scripts/dashboard/test/upgrade/*/; do
        [ -f "$d/manifest.json" ] && snaps+=("${d%/}")
    done
fi
[ "${#snaps[@]}" -gt 0 ] || { echo "no snapshot to start on" >&2; exit 2; }

field() { python3 -c 'import json, sys
d = json.load(open(sys.argv[1]))
for k in sys.argv[2].split("."):
    d = d[k]
print(d)' "$1" "$2"; }

policy="$(docker run --rm --entrypoint python3 "$image" /opt/aerieos/scripts/dashboard/stateversion.py policy)" \
    || { echo "the image did not say which states it reads" >&2; exit 1; }
now="$(printf '%s' "$policy" | python3 -c 'import json, sys; print(json.load(sys.stdin)["current"])')"
from="$(printf '%s' "$policy" | python3 -c 'import json, sys; print(json.load(sys.stdin)["supported_from"])')"
echo "image $image is at state $now and migrates from $from"

failed=0
for snap in "${snaps[@]}"; do
    name="$(basename "$snap")"
    state="$(field "$snap/manifest.json" state)"
    if [ "$state" -lt "$from" ]; then
        echo "  $name (state $state) is older than this image migrates from: not started"
        continue
    fi
    work="$(mktemp -d)"
    ctr="aerie-upgrade-$$-${name//[^A-Za-z0-9]/-}"
    tar --no-same-owner -xzf "$snap/config.tar.gz" -C "$work"
    mkdir -p "$work/home" "$work/sdk"
    # /config is the account's the container works as, as an install's is:
    # this user's where it is an ordinary one (PUID and PGID say so), and
    # the image's own default where this is root, whose files that account
    # could not read. The first real run met exactly that: users.json was
    # root's, nobody could sign in.
    if [ "$(id -u)" -eq 0 ]; then
        puid=99; pgid=100
        chown -R "$puid:$pgid" "$work"
    else
        puid="$(id -u)"; pgid="$(id -g)"
    fi
    docker run -d -t --name "$ctr" -p 127.0.0.1::7680 -e DASHBOARD_PORT=7680 -e PUID="$puid" -e PGID="$pgid" \
        -v "$work/config:/config" -v "$work/workspace:/workspace" \
        -v "$work/home:/home/builder" -v "$work/sdk:/sdk" "$image" >/dev/null \
        || { echo "FAIL  $name: the image did not start"; failed=1; continue; }
    port="$(docker port "$ctr" 7680/tcp | head -1 | sed 's/.*://')"
    why=""
    code=""
    for _ in $(seq 1 90); do
        code="$(curl -s -o /dev/null -m 5 -w '%{http_code}' "http://127.0.0.1:$port/login" || true)"
        [ "$code" = "200" ] && break
        [ "$(docker inspect -f '{{.State.Running}}' "$ctr" 2>/dev/null)" = "true" ] || { why="the container stopped"; break; }
        sleep 2
    done
    [ -n "$why" ] || [ "$code" = "200" ] || why="the dashboard did not answer in three minutes (last: ${code:-nothing})"
    # Read through the container: /config is its account's by now.
    if [ -z "$why" ]; then
        got="$(docker exec "$ctr" python3 -c 'import json; print(json.load(open("/config/state.json"))["state"])' 2>/dev/null || true)"
        [ "$got" = "$now" ] || why="/config's stamp is ${got:-unreadable}, not the image's $now"
    fi
    if [ -z "$why" ] && [ "$state" -lt "$now" ]; then
        docker exec "$ctr" sh -c 'ls -d /config/backups/before-* >/dev/null 2>&1' \
            || why="the state moved from $state and no copy was taken first"
    fi
    if [ -z "$why" ]; then
        owner="$(field "$snap/manifest.json" owner.name)"
        pass="$(field "$snap/manifest.json" owner.password)"
        signed="$(curl -s -o /dev/null -m 20 -D - "http://127.0.0.1:$port/login" \
            --data-urlencode "username=$owner" --data-urlencode "password=$pass" --data-urlencode "next=/" \
            | tr -d '\r' | grep -ci '^set-cookie: bb_session=' || true)"
        [ "$signed" = "1" ] || why="the owner did not sign in with the snapshot's password"
    fi
    if [ -n "$why" ]; then
        echo "FAIL  $name (state $state): $why"
        docker logs --tail 60 "$ctr" 2>&1 | sed 's/^/      /'
        failed=1
    else
        echo "PASS  $name (state $state): the image starts on it, migrates it to $now and the owner signs in"
    fi
    docker rm -f "$ctr" >/dev/null 2>&1
    # What the container wrote is its accounts': removed from inside one.
    docker run --rm --entrypoint sh -v "$work:/gone" "$image" -c 'rm -rf /gone/* /gone/.[!.]* 2>/dev/null; true' >/dev/null 2>&1
    rm -rf "$work" 2>/dev/null || true
done
exit "$failed"
