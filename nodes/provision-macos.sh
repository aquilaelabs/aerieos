#!/bin/bash
#
# Enroll a Mac as an AerieOS node, a GUEST node (roadmap R23): one
# directory and one launchd agent, and nothing outside them. The Mac stays
# its owner's machine: no accounts made, no daemon, no root, nothing in
# /etc, and --remove takes exactly what this put there back out again.
#
# What a Mac node is for: building what only a Mac builds (iOS, macOS, the
# Apple half of a Flutter app) with Xcode, and a toolchain store of its own
# scope (darwin-arm64 or darwin-x86_64) under the same share the Linux
# nodes use, so nothing lands on top of theirs (roadmap R19).
#
# Run it as yourself, once:
#
#   bash provision-macos.sh --controller https://builderbot.example --token bbe_…
#
# Written for the bash macOS ships (3.2): no associative arrays, no mapfile,
# nothing newer than 2007. Its own file rather than a branch of
# nodes/provision-linux.sh for that reason and one more: that script provisions a
# machine, and this one only adds a footprint to somebody's.
#
set -eu

FOOT="${BUILDERBOT_HOME:-$HOME/.builderbot}"
PLIST="$HOME/Library/LaunchAgents/dev.builderbot.agent.plist"
LABEL="dev.builderbot.agent"
CONTROLLER=""; TOKEN=""; TOOLCHAINS=""; REMOVE=0; CHECK_ONLY=0
# AerieOS's release key, and what the agent that arrives is held to before
# any of it runs (agent_proved, below), as the Nodes page's command carries
# them: the digest of the agent the controller shipped when the command was
# made, and the release's signature over it where its build has one.
RELEASE_KEY=""; AGENT_DIGEST=""; AGENT_SIG=""
# What an https controller is held to, as the command carries it: the pin of
# the controller's own key (sha256// and base64, curl's --pinnedpubkey form),
# or `ca` for a hostname the system's authorities vouch for. CTL_KEY is the
# first kind alone: each fetch from the controller is made under it, and the
# agent pins the same.
CONTROLLER_PIN=""; CTL_KEY=""
CONTROLLER_PIN_RE='^sha256//[A-Za-z0-9+/]{43}=$'
# A release key, or the key and its spare after a comma: in a variable, since
# the bash a Mac ships reads a pattern with parentheses only from one.
RELEASE_KEYS_RE='^[0-9a-f]{64}(,[0-9a-f]{64})?$'

usage() {
    cat <<'EOF'
usage: bash provision-macos.sh --controller URL --token bbe_… [--toolchains PATH]
            [--release-key KEY[,SPARE]] [--agent-digest sha256:…] [--agent-sig HEX]
            [--controller-pin PIN]
       bash provision-macos.sh --check
       bash provision-macos.sh --remove

With no arguments this prints the help and changes nothing. The command to
run is the one the dashboard's Nodes page gives you: Enroll node mints a
token and prints this line with the address and the token in it.

  --controller URL     the dashboard's address, as you open it in a browser
  --token bbe_…        an enrollment token from the Nodes page (good once, for a day)
  --toolchains PATH      where this Mac's toolchain store is. Point it at the same
                       share the Linux nodes use, mounted over SMB (say
                       /Volumes/SDK): this machine's toolchains land under
                       <path>/darwin-<arch> and nobody else's are touched.
                       Default: ~/.builderbot/toolchains, on this disk.
  --release-key KEY[,SPARE]   AerieOS's release key, and its spare after a
                       comma: the agent pins them as it enrolls, and from then
                       on takes only an update a release signed, or as its own
                       console allows.
  --agent-digest sha256:…   what the agent that arrives is held to before any
  --agent-sig HEX      of it runs: the digest of the agent the controller
                       shipped when the command was made, and the release's
                       signature over it, checked under --release-key. The
                       Nodes page puts all three in the command; without them
                       the agent is held to the digest the controller sends
                       with it, and this says what was not checked.
  --controller-pin PIN   what an https controller is held to: the pin of its
                       own key (sha256// and base64, as the Nodes page gives
                       it), under which the agent is fetched and which it
                       pins as it enrolls; or `ca`, for a hostname the
                       system's authorities vouch for.
  --check              only the pre-flight: say whether this Mac can be a
                       node, change nothing, exit 0 or 1.
  --remove             take the footprint away: the launchd agent, the
                       directory (stores included; say so if that is not
                       what you want), and nothing else, because nothing
                       else was put there.

The footprint is ~/.builderbot (BUILDERBOT_HOME to move it) and one launchd
agent, ~/Library/LaunchAgents/dev.builderbot.agent.plist, that runs as you
at login. No root is used or asked for.
EOF
}

# No arguments: the help, and nothing changed.
if [ $# -eq 0 ]; then
    usage
    exit 0
fi
while [ $# -gt 0 ]; do
    case "$1" in
        --controller) CONTROLLER="$2"; shift 2 ;;
        --token) TOKEN="$2"; shift 2 ;;
        --toolchains) TOOLCHAINS="$2"; shift 2 ;;
        --release-key) RELEASE_KEY="$2"; shift 2 ;;
        --agent-digest) AGENT_DIGEST="$2"; shift 2 ;;
        --agent-sig) AGENT_SIG="$2"; shift 2 ;;
        --controller-pin) CONTROLLER_PIN="$2"; shift 2 ;;
        --check) CHECK_ONLY=1; shift ;;
        --remove) REMOVE=1; shift ;;
        -h|--help) usage; exit 0 ;;
        *) echo "unknown option: $1" >&2; usage >&2; exit 1 ;;
    esac
done

# What the agent is held to, when given at all: a digest or a signature cut
# short by a paste is said now.
if [ -n "$AGENT_DIGEST" ] && ! [[ "$AGENT_DIGEST" =~ ^sha256:[0-9a-f]{64}$ ]]; then
    echo "--agent-digest takes sha256: and 64 hex characters, as the Nodes page gives it" >&2; exit 1
fi
if [ -n "$AGENT_SIG" ] && ! [[ "$AGENT_SIG" =~ ^[0-9a-f]{128}$ ]]; then
    echo "--agent-sig takes 128 hex characters, as the Nodes page gives it" >&2; exit 1
fi
if [ -n "$RELEASE_KEY" ] && ! [[ "$RELEASE_KEY" =~ $RELEASE_KEYS_RE ]]; then
    echo "--release-key takes the release key as 64 hex characters, and its spare after a comma" >&2; exit 1
fi
if [ -n "$CONTROLLER_PIN" ]; then
    case "$CONTROLLER" in https://*) ;; *) echo "--controller-pin is what an https controller is held to, and --controller is ${CONTROLLER:-not given}" >&2; exit 1 ;; esac
    if [[ "$CONTROLLER_PIN" =~ $CONTROLLER_PIN_RE ]]; then CTL_KEY="$CONTROLLER_PIN"
    elif [ "$CONTROLLER_PIN" != ca ]; then
        echo "--controller-pin takes the controller's key as sha256// and 44 base64 characters, as the Nodes page gives it, or ca" >&2; exit 1
    fi
fi

say()  { printf '\n== %s\n' "$1"; }
warn() { printf '\n!! %s\n' "$1" >&2; }

# ---- the agent, checked before it runs --------------------------------------
#
# The agent is fetched from the controller and run as you. What it is held to
# comes with the command the Nodes page gave, which a person signed in to
# the dashboard read there, and never from the answer that carries the
# agent: --agent-digest is the agent the controller shipped when the command
# was made, --agent-sig the release's signature over that digest, and
# --release-key the key the signature is checked under, which the agent then
# pins. A digest read from the same answer as the file says only that the
# file arrived whole. The same checks nodes/provision-linux.sh makes, in the
# bash a Mac ships.
#
# The signature is Ed25519 over the line "aerieos agent v1" and the digest
# as sha256: and 64 hex characters (the agent's release.py, tools/
# sign-agent.py). Three things can check one here, tried in this order:
# Python's cryptography library, which the agent's own check of its updates
# uses, where this Mac's python3 has it (the system's does not, unless
# somebody put it there); openssl, where the one on PATH is OpenSSL 3 (the
# system's is LibreSSL, which may not take the question); and Swift's
# CryptoKit, which is the certain one: it comes with the command line tools
# the pre-flight asks for, on macOS 10.15 and later. A signature none of
# them can check is a refusal, never a pass.

# hex_bytes HEX: those bytes, on stdout. printf's own \xHH, since xxd is
# vim's and a fresh machine may not have it.
hex_bytes() {
    # shellcheck disable=SC2059
    printf "$(printf '%s' "$1" | sed 's/../\\x&/g')"
}

# The check with Python's library, as release.verify makes it: KEYS (one, or
# two after a comma), SIG and DIGEST are its arguments, and it prints ok and
# the key that signed, bad, or nolib where the library is not there.
RELEASE_VERIFY_PY='import sys
try:
    from cryptography.exceptions import InvalidSignature
    from cryptography.hazmat.primitives.asymmetric.ed25519 import Ed25519PublicKey
except ImportError:
    print("nolib")
    sys.exit(0)
keys, sig, digest = sys.argv[1:4]
for key in keys.split(","):
    try:
        Ed25519PublicKey.from_public_bytes(bytes.fromhex(key)).verify(bytes.fromhex(sig), b"aerieos agent v1\n" + digest.encode())
    except (InvalidSignature, ValueError):
        continue
    print("ok " + key)
    break
else:
    print("bad")
'

# The same check in Swift, for CryptoKit: the same three arguments, and ok
# and the key that signed, or bad, on its one line.
RELEASE_VERIFY_SWIFT='import CryptoKit
import Foundation

func bytes(_ hex: String) -> Data? {
    var out = Data()
    var i = hex.startIndex
    while i < hex.endIndex {
        guard let j = hex.index(i, offsetBy: 2, limitedBy: hex.endIndex), let b = UInt8(hex[i..<j], radix: 16) else { return nil }
        out.append(b)
        i = j
    }
    return out
}

let a = CommandLine.arguments
var said = "bad"
if a.count == 4, let sig = bytes(a[2]) {
    let message = Data(("aerieos agent v1\n" + a[3]).utf8)
    for k in a[1].split(separator: ",") {
        if let raw = bytes(String(k)), let key = try? Curve25519.Signing.PublicKey(rawRepresentation: raw),
           key.isValidSignature(sig, for: message) {
            said = "ok \(k)"
            break
        }
    }
}
print(said)
'

# release_sig_ok KEYS SIG DIGEST: 0 when SIG is the signature of one of KEYS
# (the release key, its spare after a comma) over the agent whose digest is
# DIGEST, and SIG_SAID is the key that signed; 1 when it is not; 2 when
# nothing on this machine can check one, and SIG_SAID is why.
SIG_SAID=""
release_sig_ok() {
    local keys="$1" sig="$2" digest="$3" out="" key said d
    SIG_SAID=""
    [[ "$keys" =~ $RELEASE_KEYS_RE ]] \
        || { SIG_SAID="the release key is not 64 hex characters, with its spare after a comma"; return 2; }
    [[ "$digest" =~ ^sha256:[0-9a-f]{64}$ ]] || { SIG_SAID="there is no digest to check it over"; return 2; }
    [[ "$sig" =~ ^[0-9a-f]{128}$ ]] || return 1
    if command -v python3 >/dev/null 2>&1; then
        # From /, so that nothing in the folder this was run from is imported
        # in the library's place.
        out="$(cd / && python3 -c "$RELEASE_VERIFY_PY" "$keys" "$sig" "$digest" 2>/dev/null || true)"
        case "$out" in
            "ok "*) SIG_SAID="${out#ok }"; return 0 ;;
            bad) return 1 ;;
        esac
    fi
    if command -v openssl >/dev/null 2>&1 && command -v base64 >/dev/null 2>&1; then
        d="$(mktemp -d)"
        printf 'aerieos agent v1\n%s' "$digest" > "$d/msg"
        hex_bytes "$sig" > "$d/sig"
        out=""
        for key in ${keys//,/ }; do
            # The key as OpenSSL reads one: Ed25519's fixed twelve bytes of
            # SubjectPublicKeyInfo, then the key's own thirty-two.
            { printf -- '-----BEGIN PUBLIC KEY-----\n'
              hex_bytes "302a300506032b6570032100${key}" | base64
              printf -- '-----END PUBLIC KEY-----\n'; } > "$d/pub"
            said="$(openssl pkeyutl -verify -pubin -inkey "$d/pub" -rawin -in "$d/msg" -sigfile "$d/sig" 2>&1 || true)"
            case "$said" in
                *"Signature Verified Successfully"*) out="ok $key"; break ;;
                *"Signature Verification Failure"*) out=bad ;;
            esac
        done
        rm -rf "$d"
        case "$out" in
            "ok "*) SIG_SAID="${out#ok }"; return 0 ;;
            bad) return 1 ;;
        esac
    fi
    if command -v swift >/dev/null 2>&1; then
        d="$(mktemp -d)"
        printf '%s\n' "$RELEASE_VERIFY_SWIFT" > "$d/verify.swift"
        out="$(swift "$d/verify.swift" "$keys" "$sig" "$digest" 2>/dev/null || true)"
        rm -rf "$d"
        case "$out" in
            "ok "*) SIG_SAID="${out#ok }"; return 0 ;;
            bad) return 1 ;;
        esac
    fi
    SIG_SAID="its python3 has no cryptography library, its openssl is not OpenSSL 3, and swift (the command line tools) did not run the check either"
    return 2
}

# agent_sent HEADERS NAME: what the controller's answer says under NAME
# (x-agent-digest, x-agent-sig), from the headers curl kept; nothing for none.
agent_sent() {
    tr -d '\r' < "$1" | awk -v n="$2:" 'tolower($1) == n { v = $2 } END { print v }'
}

# agent_proved FILE SENT: whether the agent that arrived in FILE is the one
# to run, said either way. SENT is the digest the controller's answer names.
# Held to the digest the script carries where it carries one, and to SENT
# otherwise, with that said: a command from an older controller, or one
# somebody saved, carries none. No digest at all, and nothing
# arriving, is a refusal: an answer with no digest was taken as it came
# here, and an empty file runs as an empty script that says nothing. Then the
# signature, where one came: under the release key, before any of the agent
# runs, and refused when it is not that key's or cannot be checked here.
agent_proved() {
    local file="$1" sent="$2" got want rc=0
    got="sha256:$(shasum -a 256 "$file" | cut -d' ' -f1)"
    want="${AGENT_DIGEST:-$sent}"
    if [ -z "$want" ] || [ ! -s "$file" ]; then
        warn "what ${CONTROLLER} sent for the agent is not AerieOS's ($(wc -c < "$file" 2>/dev/null | tr -d ' ') bytes, ${want:-no digest}): the address does not reach the controller's agent API"
        return 1
    fi
    if [ "$got" != "$want" ] && [ -n "$AGENT_DIGEST" ]; then
        warn "the agent that arrived (${got}) is not the one this enrollment was made for (${AGENT_DIGEST}), so none of it was run. Either the controller was updated after the script or the command was made, or something other than the controller answered: make a new one on the Nodes page (Enroll node)"
        return 1
    elif [ "$got" != "$want" ]; then
        warn "the agent that arrived does not match the digest the controller sent (${got} vs ${want})"
        return 1
    fi
    if [ -n "$AGENT_SIG" ]; then
        if [ -z "$RELEASE_KEY" ]; then
            warn "a signature for the agent came (--agent-sig) with no release key to check it under (--release-key), so none of the agent was run: use the script or the command as the Nodes page gave it"
            return 1
        fi
        release_sig_ok "$RELEASE_KEY" "$AGENT_SIG" "$got" || rc=$?
        case "$rc" in
            0) printf '   the agent is %s, the one this enrollment was made for, signed by %s (%s…)\n' "${got:7:12}" \
                   "$([ "$SIG_SAID" = "${RELEASE_KEY%%,*}" ] && echo "AerieOS's release key" || echo "the spare of AerieOS's release key")" "${SIG_SAID:0:16}" ;;
            1) warn "the signature that came for the agent is not the release key's (${RELEASE_KEY:0:16}…), so none of the agent was run: nothing says an AerieOS release built it. Make a new script on the Nodes page (Enroll node)"
               return 1 ;;
            *) warn "a release signature came for the agent and this machine cannot check one (${SIG_SAID}), so none of the agent was run"
               return 1 ;;
        esac
    elif [ -n "$AGENT_DIGEST" ]; then
        printf '   the agent is %s, the one this enrollment was made for. No release signature came with it: the build this controller runs carries none (one made outside the release build, from a branch), so nothing says an AerieOS release built this agent.\n' "${got:7:12}"
        [ -z "$RELEASE_KEY" ] || printf '   The node pins the release key all the same: it takes a later agent update only when a release signed it, or when its own console allows unsigned ones (the agent, with: unsigned on).\n'
    else
        printf '   the agent is %s, by the digest the controller sent with it and nothing else: this script or command carries no digest and no signature for it (an older controller made it, or it was saved from one). A new one from the Nodes page carries both.\n' "${got:7:12}"
    fi
    [ -n "$RELEASE_KEY" ] || printf '   No release key came with this enrollment, so the node pins none it did not hold already, and takes agent updates on the word of its controller.\n'
    return 0
}

# ---- taking it away --------------------------------------------------------
if [ "$REMOVE" = 1 ]; then
    say "removing the AerieOS footprint"
    if [ -f "$PLIST" ]; then
        launchctl bootout "gui/$(id -u)/$LABEL" 2>/dev/null || launchctl unload "$PLIST" 2>/dev/null || true
        rm -f "$PLIST" && printf '   removed %s\n' "$PLIST"
    fi
    if [ -d "$FOOT" ]; then
        rm -rf "$FOOT" && printf '   removed %s\n' "$FOOT"
    fi
    printf '   nothing else was here to remove. On the dashboard, Remove the node on its row.\n'
    exit 0
fi

# ---- pre-flight ------------------------------------------------------------
# Before anything is written: what this Mac has, and what it lacks. A FAIL
# stops with the whole list printed; a WARN is something to know.
say "checking this Mac"
FAILED=0
chk() {
    case "$1" in
        ok)   printf '   ok    %s\n' "$2" ;;
        warn) printf '   WARN  %s\n' "$2" ;;
        fail) printf '   FAIL  %s\n' "$2"; FAILED=1 ;;
    esac
}
if [ "$(uname -s)" = Darwin ]; then chk ok "macOS $(sw_vers -productVersion 2>/dev/null || echo '?') on $(uname -m)"
else chk fail "this is $(uname -s), and this script is for macOS; nodes/provision-linux.sh is the one for Linux"; fi
if [ "$(id -u)" = 0 ]; then chk fail "run this as yourself, not root: a guest node is one directory in your home and a launchd agent that runs as you"; fi
if xcode-select -p >/dev/null 2>&1; then chk ok "Xcode command line tools at $(xcode-select -p)"
else chk fail "no Xcode command line tools: run  xcode-select --install  and come back (git and clang live there)"; fi
if command -v python3 >/dev/null 2>&1; then chk ok "python3: $(python3 --version 2>&1)"
else chk fail "no python3: it comes with the command line tools above"; fi
# The library the agent checks a signed update with. A Mac's own python3 has
# none, and an agent that pinned the release key refuses an update it cannot
# check: said here, with the line that puts it there.
if [ -n "$RELEASE_KEY" ] && command -v python3 >/dev/null 2>&1; then
    if (cd / && python3 -c 'import cryptography') >/dev/null 2>&1; then chk ok "python3 has the cryptography library, which checks a signed agent update"
    else chk warn "python3 has no cryptography library: this Mac pins the release key, and its agent then refuses an update it cannot check; python3 -m pip install --user cryptography puts it there"; fi
fi
if command -v brew >/dev/null 2>&1; then chk ok "Homebrew at $(command -v brew)"
else chk warn "no Homebrew: a recipe's system packages (tmux for sessions) cannot be installed by the agent; https://brew.sh"; fi
if command -v git >/dev/null 2>&1; then chk ok "git: $(git --version 2>&1)"
else chk fail "no git"; fi
xcode="$(find /Applications -maxdepth 1 -name 'Xcode*.app' 2>/dev/null | head -1)"
if [ -n "$xcode" ]; then chk ok "Xcode: $xcode"
else chk warn "no Xcode.app: iOS and macOS apps need it, from the App Store or the xcodes recipe from the Library once enrolled"; fi
if [ -n "$TOOLCHAINS" ]; then
    if [ -d "$TOOLCHAINS" ] && [ -w "$TOOLCHAINS" ]; then chk ok "toolchain store at $TOOLCHAINS (this Mac's scope: darwin-$(uname -m))"
    else chk fail "$TOOLCHAINS is not a writable directory: mount the share first (Finder: Go > Connect to Server, smb://…), or use a directory of this Mac's"; fi
fi
avail="$(df -Pk "$HOME" 2>/dev/null | awk 'NR==2{print int($4/1024/1024)}')"
if [ -n "$avail" ]; then
    if [ "$avail" -ge 20 ]; then chk ok "${avail}G free in $HOME"
    else chk warn "only ${avail}G free in $HOME; Xcode alone wants 15"; fi
fi
if [ -n "$CONTROLLER" ]; then
    if curl -fsk ${CTL_KEY:+--pinnedpubkey "$CTL_KEY"} --max-time 10 -o /dev/null "${CONTROLLER%/}/" 2>/dev/null; then chk ok "controller ${CONTROLLER} answers"
    else chk warn "${CONTROLLER} does not answer from here, so enrollment will fail until it does"; fi
fi
if [ "$FAILED" = 1 ]; then
    warn "this Mac is not ready to be a node, so nothing was changed"
    exit 1
fi
if [ "$CHECK_ONLY" = 1 ]; then printf '\n   this Mac can be a node.\n'; exit 0; fi
if [ -z "$CONTROLLER" ] || [ -z "$TOKEN" ]; then
    echo "--controller and --token go together, and enrolling needs both" >&2; exit 1
fi

# ---- the footprint ---------------------------------------------------------
say "the footprint: $FOOT"
mkdir -p "$FOOT/bin" "$FOOT/data" "$FOOT/cache" "$FOOT/artifacts" "$FOOT/log"
[ -n "$TOOLCHAINS" ] || { TOOLCHAINS="$FOOT/toolchains"; mkdir -p "$TOOLCHAINS"; }
AGENT="$FOOT/bin/builderbot-agent"
NODE_JSON="$FOOT/node.json"

say "the agent, from ${CONTROLLER}"
hdr="$(mktemp)"
curl -fsSL ${CTL_KEY:+-k --pinnedpubkey "$CTL_KEY"} -D "$hdr" -H "Authorization: Bearer ${TOKEN}" \
     "${CONTROLLER%/}/api/v1/agent/download" -o "${AGENT}.new" \
    || { warn "could not download the agent from ${CONTROLLER}. Is that the dashboard's address, and is the token unused?"; rm -f "$hdr" "${AGENT}.new"; exit 1; }
# Held to what the command carries before any of it runs (agent_proved); an
# answer with no digest was taken as it came here, and is refused.
want="$(agent_sent "$hdr" x-agent-digest)"
rm -f "$hdr"
agent_proved "${AGENT}.new" "$want" || { rm -f "${AGENT}.new"; exit 1; }
chmod 755 "${AGENT}.new"; mv -f "${AGENT}.new" "$AGENT"

# Enrolled as this account, with the stores under the footprint (the
# toolchain store wherever --toolchains said). The credential it keeps is this
# node's own row and nothing else. The release key is pinned as it enrolls,
# as on any node: from then on the agent takes only an update a release
# signed, or as its console allows.
say "enrolling as $(id -un)"
launchctl bootout "gui/$(id -u)/$LABEL" 2>/dev/null || true
BUILDERBOT_NODE_JSON="$NODE_JSON" "$AGENT" enroll --controller "$CONTROLLER" --token "$TOKEN" \
    --user "$(id -un)" ${RELEASE_KEY:+--release-key "$RELEASE_KEY"} ${CONTROLLER_PIN:+--pin "$CONTROLLER_PIN"} \
    --store "data=$FOOT/data" --store "toolchains=$TOOLCHAINS" \
    --store "cache=$FOOT/cache" --store "artifacts=$FOOT/artifacts"

# ---- the launchd agent -----------------------------------------------------
# Runs as you, at login, restarted if it stops; its log beside it. What a
# systemd unit is on the sandbox, in launchd's words.
say "the launchd agent: $LABEL"
mkdir -p "$(dirname "$PLIST")"
cat > "$PLIST" <<EOF
<?xml version="1.0" encoding="UTF-8"?>
<!DOCTYPE plist PUBLIC "-//Apple//DTD PLIST 1.0//EN" "http://www.apple.com/DTDs/PropertyList-1.0.dtd">
<plist version="1.0">
<dict>
  <key>Label</key><string>${LABEL}</string>
  <key>ProgramArguments</key>
  <array><string>$(command -v python3)</string><string>${AGENT}</string><string>run</string></array>
  <key>EnvironmentVariables</key>
  <dict>
    <key>BUILDERBOT_NODE_JSON</key><string>${NODE_JSON}</string>
    <key>BUILDERBOT_RUNNER_DIR</key><string>${FOOT}/runner</string>
    <key>PATH</key><string>/opt/homebrew/bin:/usr/local/bin:/usr/bin:/bin:/usr/sbin:/sbin</string>
    <key>HOME</key><string>${HOME}</string>
  </dict>
  <key>RunAtLoad</key><true/>
  <key>KeepAlive</key><true/>
  <key>ThrottleInterval</key><integer>5</integer>
  <key>StandardOutPath</key><string>${FOOT}/log/agent.log</string>
  <key>StandardErrorPath</key><string>${FOOT}/log/agent.log</string>
</dict>
</plist>
EOF
launchctl bootstrap "gui/$(id -u)" "$PLIST" 2>/dev/null || launchctl load "$PLIST"
sleep 2
if launchctl print "gui/$(id -u)/$LABEL" >/dev/null 2>&1; then
    printf '   running; log at %s/log/agent.log\n' "$FOOT"
else
    warn "the agent did not stay up; read $FOOT/log/agent.log"
fi

cat <<EOF

Done. This Mac is a GUEST node: the dashboard's Nodes page shows it live
within a minute, with Storage and Network not offered (they are yours), and
the Library installs into its own scope of the toolchain store,
$TOOLCHAINS/darwin-$(uname -m). Root is never asked for here.

  launchctl print gui/$(id -u)/$LABEL     is it running
  tail -f $FOOT/log/agent.log             what it is doing
  bash provision-macos.sh --remove        take it all away again

Sessions on this Mac (a Claude terminal here rather than on the controller)
need the spaces share mounted at /workspace (on macOS that is one line
in /etc/synthetic.conf and an SMB mount), and are not set up by this script.
EOF
