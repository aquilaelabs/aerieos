#!/usr/bin/env bash
# shellcheck disable=SC2034  # the FAMILY_* names are read by the core that sources this
# The Debian and Ubuntu family of nodes/provision-linux.sh: what differs by
# package manager, where docker comes from, and what the packages are
# called. The core sources this file from beside it (the enroll script
# puts the picked system's there) and calls nothing of a distribution's
# by name. Vetted: Ubuntu 24.04 and 26.04 sandboxes, in daily use.
FAMILY_PICKED=deb
FAMILY_NAME="Debian and Ubuntu"
# The os-release IDs (ID and ID_LIKE) this file is for.
FAMILY_IDS="debian ubuntu raspbian"
# The tools the family implies, checked before anything lands.
FAMILY_NEED="apt-get dpkg"

# apt_waiting CMD...: CMD, run again while another apt holds its lock (B320).
# A machine just booted from a cloud image runs its own apt-get (cloud-init,
# unattended-upgrades) for a few minutes, and an install started as soon as
# ssh answered failed at its first step on the lock. Up to ten minutes, said
# once; any other failure is CMD's own, at once.
apt_waiting() {
    local i out rc=0
    for i in $(seq 1 60); do
        out="$("$@" 2>&1)" && rc=0 || rc=$?
        if [ "$rc" -ne 0 ] && grep -qE 'Could not get lock|Unable to lock|is another process using it' <<<"$out"; then
            [ "$i" -gt 1 ] || echo "waiting for another apt (a machine's own first update) to let go of its lock" >&2
            sleep 10
            continue
        fi
        break
    done
    [ -z "$out" ] || printf '%s\n' "$out"
    return "$rc"
}
# pkg_refresh: the package index, once, before the first install.
# On an AerieOS disk (image/, R160 step 1) the packages are the image's,
# pinned when it was built, and its root forgets at the next boot: nothing is
# fetched, and a package the provisioner needs that the image lacks is a
# build of the image to fix, said here by name.
on_os_image() { [ -r "${BB_OS_RELEASE:-/usr/lib/aerieos-os/release}" ]; }
pkg_refresh() {
    on_os_image && return 0
    export DEBIAN_FRONTEND=noninteractive; apt_waiting apt-get update -qq
}
# pkg NAME...: install what is named, quietly.
pkg() {
    if on_os_image; then
        # The image removes its package database (CleanPackageMetadata), so
        # there is nothing to ask: what it carries was settled when it was built.
        [ -s "${BB_DPKG_STATUS:-/var/lib/dpkg/status}" ] || return 0
        local p alt have=0 miss=()
        for p in "$@"; do
            have=0
            for alt in ${p//|/ }; do
                dpkg-query -W -f='${db:Status-Status}' "$alt" 2>/dev/null | grep -qx installed && { have=1; break; }
            done
            [ "$have" = 1 ] || miss+=("$p")
        done
        [ "${#miss[@]}" -eq 0 ] && return 0
        echo "not in the AerieOS image: ${miss[*]} (image/mkosi.conf lists what it carries; a package the node needs is added there)" >&2
        return 1
    fi
    DEBIAN_FRONTEND=noninteractive NEEDRESTART_MODE=a \
                apt_waiting apt-get -o Dpkg::Use-Pty=0 -o DPkg::Lock::Timeout=600 install -y -qq "$@"
}
# pkg_names KEY: what a package is called here, for the handful the core
# installs itself. A recipe's system packages are the recipe's business,
# per family, in config/toolchains.json.
pkg_names() {
    case "$1" in
        base) echo "ca-certificates curl gnupg nfs-common" ;;
        guest) echo "qemu-guest-agent" ;;
        guestsvc) echo "qemu-guest-agent" ;;
        python) echo "python3" ;;
        pycrypto) echo "python3-cryptography" ;;
        session) echo "tmux jq git" ;;
        reel) echo "xvfb xdotool x11-utils" ;;
        wg) echo "wireguard-tools" ;;
        nft) echo "nftables" ;;
        docker) echo "docker-ce docker-ce-cli containerd.io docker-buildx-plugin docker-compose-plugin" ;;
    esac
}
# docker_install: docker, where this family gets it from.
docker_install() {
            # An image's packages were settled when it was built, and its root
            # takes no repository: a missing docker is a build of the image to fix.
            if on_os_image; then
                echo "not in the AerieOS image: docker (image/mkosi.conf lists what it carries)" >&2
                return 1
            fi

            # Which of Docker's two Debian-family repositories, and which
            # suite in it. A derivative uses its parent's: Mint and Pop!_OS
            # carry UBUNTU_CODENAME for exactly this; Kali's own codename
            # is nothing Docker publishes, and Raspberry Pi OS is Debian's
            # stable; both fall through docker_suite to it.
            case " ${ID} ${ID_LIKE:-} " in
                *" ubuntu "*) DOCKER_DEB=ubuntu; code="${UBUNTU_CODENAME:-${VERSION_CODENAME:-}}"; fall="noble jammy" ;;
                *)            DOCKER_DEB=debian; code="${VERSION_CODENAME:-}"; fall="bookworm bullseye" ;;
            esac
            # shellcheck disable=SC2086  # the fallbacks are meant to split
            suite="$(docker_suite "$code" $fall)" || true
            [ -n "${suite:-}" ] || {
                echo "docker publishes nothing this machine can use (tried ${code:-no codename}, ${fall})" >&2
                exit 1
            }
            [ "$suite" = "$code" ] \
                || echo "note: docker has no ${code:-$ID} suite; using ${suite}, which is the same build"
            install -m 0755 -d /etc/apt/keyrings
            curl -fsSL "https://download.docker.com/linux/${DOCKER_DEB}/gpg" \
                | gpg --dearmor -o /etc/apt/keyrings/docker.gpg
            chmod a+r /etc/apt/keyrings/docker.gpg
            echo "deb [arch=$(dpkg --print-architecture) signed-by=/etc/apt/keyrings/docker.gpg]" \
                 "https://download.docker.com/linux/${DOCKER_DEB} ${suite} stable" \
                > /etc/apt/sources.list.d/docker.list
            apt_waiting apt-get update -qq
            # shellcheck disable=SC2046
            pkg $(pkg_names docker)
}
# apt_suite BASE SUITE...: the first of the suites named that the apt
# repository at BASE publishes, for a vendor whose repository lags a new
# release or has never heard of a derivative's codename. It settles only
# which suite to ask for: what the suite holds is checked by apt against
# the key its source line names, whichever suite it is.
apt_suite() {
    local base="$1" try
    shift
    for try in "$@"; do
        [ -n "$try" ] || continue
        if curl -fs -o /dev/null --max-time 15 "${base}/dists/${try}/InRelease"; then
            printf '%s' "$try"
            return 0
        fi
    done
    return 1
}
# door_install NAME: a door's program (cloudflared, tailscale) from its
# vendor's own apt repository, whose index apt holds to the vendor's key
# and whose packages it holds to the index. The key is the copy the core
# carries (door_key), written where the source line's signed-by names it,
# and never one fetched here. 2 where this system has no verified source
# for it, DOOR_WHY saying why. DOOR_KEYS and DOOR_SOURCES are apt's own
# directories for a key and a source.
DOOR_KEYS=/etc/apt/keyrings
DOOR_SOURCES=/etc/apt/sources.list.d
door_install() {
    local arch dist code fall suite
    case "$1" in cloudflared|tailscale) ;; *) return 2 ;; esac
    if on_os_image; then
        DOOR_WHY="an AerieOS disk's packages are its image's, which carries no $1"
        return 2
    fi
    arch="$(dpkg --print-architecture)"
    install -m 0755 -d "$DOOR_KEYS" || return 1
    case "$1" in
        cloudflared)
            # One suite, any, serves every release of every distribution.
            door_key cloudflared > "$DOOR_KEYS/cloudflared.asc" || return 1
            echo "deb [arch=${arch} signed-by=${DOOR_KEYS}/cloudflared.asc] https://pkg.cloudflare.com/cloudflared any main" \
                > "$DOOR_SOURCES/cloudflared.list" ;;
        tailscale)
            # A repository a distribution and a suite a release, a
            # derivative asking for its parent's as it does of Docker's;
            # the packages are the same build under every suite.
            case " ${ID} ${ID_LIKE:-} " in
                *" ubuntu "*)   dist=ubuntu; code="${UBUNTU_CODENAME:-${VERSION_CODENAME:-}}"; fall="noble jammy" ;;
                " raspbian "*)  dist=raspbian; code="${VERSION_CODENAME:-}"; fall="bookworm" ;;
                *)              dist=debian; code="${DEBIAN_CODENAME:-${VERSION_CODENAME:-}}"; fall="trixie bookworm" ;;
            esac
            # shellcheck disable=SC2086  # the fallbacks are meant to split
            suite="$(apt_suite "https://pkgs.tailscale.com/stable/${dist}" "$code" $fall)" || true
            [ -n "${suite:-}" ] || {
                echo "Tailscale's repository answers for none of the suites tried (${code:-no codename}, ${fall})" >&2
                return 1
            }
            door_key tailscale > "$DOOR_KEYS/tailscale.asc" || return 1
            echo "deb [arch=${arch} signed-by=${DOOR_KEYS}/tailscale.asc] https://pkgs.tailscale.com/stable/${dist} ${suite} main" \
                > "$DOOR_SOURCES/tailscale.list" ;;
    esac
    chmod 0644 "$DOOR_KEYS/$1.asc" "$DOOR_SOURCES/$1.list"
    apt_waiting apt-get update -qq || return 1
    pkg "$1" || return 1
    # The package starts its own daemon where systemd runs: said again, a no-op.
    [ "$1" != tailscale ] || svc_enable tailscaled
}
