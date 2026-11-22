#!/usr/bin/env bash
# shellcheck disable=SC2034  # the FAMILY_* names are read by the core that sources this
# The openSUSE and SLES family of nodes/provision-linux.sh: what differs by
# package manager, where docker comes from, and what the packages are
# called. The core sources this file from beside it (the enroll script
# puts the picked system's there) and calls nothing of a distribution's
# by name. Written to the family's documentation and never run for real (dev).
FAMILY_PICKED=suse
FAMILY_NAME="openSUSE and SLES"
# The os-release IDs (ID and ID_LIKE) this file is for.
FAMILY_IDS="suse opensuse opensuse-leap opensuse-tumbleweed sles"
# The tools the family implies, checked before anything lands.
FAMILY_NEED="zypper rpm"

# pkg_refresh: the package index, once, before the first install.
pkg_refresh() {
    zypper -n -q refresh >/dev/null 2>&1 || true
}
# pkg NAME...: install what is named, quietly.
pkg() {
    zypper -n -q install -y "$@" >/dev/null
}
# pkg_names KEY: what a package is called here, for the handful the core
# installs itself. A recipe's system packages are the recipe's business,
# per family, in config/toolchains.json.
pkg_names() {
    case "$1" in
        base) echo "ca-certificates curl gpg2 nfs-client" ;;
        guest) echo "qemu-guest-agent" ;;
        guestsvc) echo "qemu-ga" ;;
        python) echo "python3" ;;
        pycrypto) echo "python3-cryptography" ;;
        session) echo "tmux jq git" ;;
        reel) echo "xorg-x11-server-Xvfb xdotool xdpyinfo" ;;
        wg) echo "wireguard-tools" ;;
        nft) echo "nftables" ;;
        docker) echo "docker docker-buildx docker-compose" ;;
    esac
}
# docker_install: docker, where this family gets it from.
docker_install() {

            # Arch, SUSE, Alpine, Void and Gentoo package a current Docker
            # themselves, which is the point of using theirs.
            # shellcheck disable=SC2046
            pkg $(pkg_names docker) \
                || warn "docker did not install from the distribution's packages, so this machine is not a Docker host until it does"
}
# zypp_carries NAME: whether a repository this machine has carries a
# package of that name.
zypp_carries() {
    zypper -n -q search --match-exact "$1" >/dev/null 2>&1
}
# door_install NAME: a door's program (cloudflared, tailscale) from the
# distribution's own repositories where they carry it, as Tumbleweed's do,
# and otherwise from its vendor's own rpm repository, each package held by
# rpm to the vendor's key. The key is the copy the core carries (door_key),
# imported into rpm's keyring from a file and never fetched here. 2 where
# this system has no verified source for it, DOOR_WHY saying why.
# DOOR_KEYS and DOOR_SOURCES are the directories the key's file and
# zypper's repositories are kept in.
DOOR_KEYS=/etc/pki/rpm-gpg
DOOR_SOURCES=/etc/zypp/repos.d
door_install() {
    local at base index
    case "$1" in cloudflared|tailscale) ;; *) return 2 ;; esac
    if ! zypp_carries "$1"; then
        case "$1" in
            cloudflared)
                # Its packages are signed with the key and its index is
                # not: Cloudflare signs the index with an older key than
                # the one it publishes (20 Nov 2026), so only the packages
                # are held (pkg_gpgcheck), and one the key did not sign is
                # refused.
                base="https://pkg.cloudflare.com/cloudflared/rpm"; index=0 ;;
            tailscale)
                # A repository a release, as Tailscale lays them out:
                # Tumbleweed's, or Leap's by its version, which SLES of the
                # same version takes too.
                case " ${ID:-} ${ID_LIKE:-} " in
                    *tumbleweed*|*slowroll*) at=tumbleweed ;;
                    *)                       at="leap/${VERSION_ID:-}" ;;
                esac
                base="https://pkgs.tailscale.com/stable/opensuse/${at}/\$basearch"; index=1 ;;
        esac
        install -d -m 0755 "$DOOR_KEYS" || return 1
        door_key "$1" > "$DOOR_KEYS/RPM-GPG-KEY-$1" || return 1
        rpm --import "$DOOR_KEYS/RPM-GPG-KEY-$1" || return 1
        printf '%s\n' "[$1-stable]" "name=$1 stable" "baseurl=${base}" "enabled=1" "autorefresh=1" "gpgcheck=1" \
            "repo_gpgcheck=${index}" "pkg_gpgcheck=1" "gpgkey=file://${DOOR_KEYS}/RPM-GPG-KEY-$1" > "$DOOR_SOURCES/$1.repo" || return 1
        chmod 0644 "$DOOR_KEYS/RPM-GPG-KEY-$1" "$DOOR_SOURCES/$1.repo"
        zypper -n -q refresh "$1-stable" >/dev/null || return 1
    fi
    pkg "$1" || return 1
    [ "$1" != tailscale ] || svc_enable tailscaled
}
