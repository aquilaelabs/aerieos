"""Whether new agent code is AerieOS's own release (R227 step 1).

A node took its agent's update on a digest the controller named, so whoever
held the controller could put any code on a node as root. A node that has
pinned AerieOS's release key takes an update only when a signature under
that key covers its digest: the key is in no controller's hands (the release
build signs with it), so a controller taken over cannot make one.

The key is pinned when the node is enrolled (`enroll --release-key HEX`, as
the Enroll script carries it) or at the machine's own console afterwards
(`aerieos-agent release-key HEX`), and is never taken from the
controller's word on a running node. A spare may be pinned with it, after a
comma (R232): an update signed by either is taken, so the key the builds
sign with can be replaced by the spare with no node cut off. A node with no key pinned updates as
before. A build from a branch carries no signature: a node its owner uses
for those says so at its console (`aerieos-agent unsigned on`), which is
kept in node.json like the key.

Ed25519, by the `cryptography` library the nodes are provisioned with
(tokenseal.py's): nothing here is hand-built, and a node that pinned a key
and lacks the library refuses the update rather than taking it unchecked.

The tools root installs from the bundle are held the same way (the rest of
step 1): the provisioner with the machine's own helper in it, the helper
that builds a session's view, the one that cuts a pack's install off the
network, and the provisioner's family files. The bundle's own digest moves
with a person's tool packs, so no release can sign it; what a release signs
is the list of those files, each with its digest (tools_digest), under a
line of its own, and a pinned node keeps a copy of them for root only when
that signature covers the files it was sent.

A controller somebody builds on their own machine is not a release, and its
builder signs it with a key of their own. A node trusts such a key beside
the release key and its spare once a person adds it at the node's console
(`aerieos-agent release-key add HEX`, up to ALSO_MAX of them, kept in
node.json as release_also): an update or a list of root's tools signed by an
added key is taken as one the release signed, and said as what it is.
Nothing a controller sends adds, changes or drops one.
"""
import hashlib
import re

from . import names

# What is signed: this line, then the agent zip's digest as hello names it
# ("sha256:" and 64 hex characters). The line keeps a signature made for
# anything else under the same key from passing here.
MESSAGE = b"aerieos agent v1\n"
# ...and for the tools root installs from the bundle: this line, then
# tools_digest() of them. Another line, so neither signature passes as the
# other.
TOOLS_MESSAGE = b"aerieos root tools v1\n"
KEY_RE = re.compile(r"[0-9a-f]{64}")
SIG_RE = re.compile(r"[0-9a-f]{128}")
# How many keys a console may add beside the release key and its spare.
ALSO_MAX = 4


def clean_key(text):
    """A release key as 64 hex characters, or "" when it is not one."""
    k = str(text or "").strip().lower()
    return k if KEY_RE.fullmatch(k) else ""


def clean_keys(text):
    """A release key, or a key and its spare after a comma, as a list of one
    or two; [] when any part is not a key."""
    parts = [clean_key(x) for x in str(text or "").replace(" ", ",").split(",") if x.strip()]
    return list(dict.fromkeys(parts)) if parts and all(parts) and len(parts) <= 2 else []


def pinned(state):
    return clean_key((state or {}).get("release_key"))


def spare(state):
    """The spare release key pinned beside the first (R232): a pair whose
    private half is kept apart from the release build's, so the key a build
    signs with can be lost or replaced without a visit to every node."""
    return clean_key((state or {}).get("release_spare"))


def keys(state):
    """Every release key pinned here, the first one first: [] for none."""
    return list(dict.fromkeys(k for k in (pinned(state), spare(state)) if k))


def also(state):
    """The keys added at this node's console (release-key add), in the order
    they were added: whoever builds a controller of their own signs it with
    one. [] for none; what is not a key is passed over, and no more than
    ALSO_MAX are read."""
    got = (state or {}).get("release_also")
    if not isinstance(got, list):
        return []
    return list(dict.fromkeys(k for k in (clean_key(x) for x in got if isinstance(x, str)) if k))[:ALSO_MAX]


def trusted(state):
    """Every key this node trusts, the release key and its spare first and
    the ones added at its console after them: [] for a node that checks
    nothing."""
    return list(dict.fromkeys(keys(state) + also(state)))


def unsigned_ok(state):
    return (state or {}).get("unsigned_ok") is True


def _kind(state, key):
    """What a key trusted here is, in the words a job's log says it by."""
    pins = keys(state)
    if key in pins:
        return "the release key this node pinned" if key == pins[0] else "the spare release key this node pinned"
    return "a key added at this node's console"


def _signer(state, digest, sig, message):
    """(who, why): the key trusted here that signed `digest`, said as its
    kind with the key shortened, or "" and why none of them did."""
    why = ""
    for key in trusted(state):
        said = verify(key, digest, sig, message)
        if not said:
            return f"{_kind(state, key)} ({key[:16]}…)", ""
        why = why or said
    if also(state):
        # Among several kinds of key, "the pinned release key's" names one.
        why = why.replace("its signature is not the pinned release key's", "its signature is under no key this node trusts")
    return "", why


def _named(state):
    """The keys this node takes a signature under, as a refusal names them."""
    pins, added = keys(state), [k for k in also(state) if k not in keys(state)]
    said = []
    if pins:
        said.append(f"the release key it pinned ({pins[0][:16]}…)" + (f" or its spare ({pins[1][:16]}…)" if len(pins) > 1 else ""))
    if added:
        said.append(("a key" if len(added) == 1 else "one of the keys") + " added at its console ("
                    + ", ".join(f"{k[:16]}…" for k in added) + ")")
    return " or ".join(said)


def _console_can():
    """What a person at the machine can do about a refusal: the two verbs."""
    return ("A build made outside AerieOS's release builds is unsigned unless its builder signs it with a key of their "
            f"own. At this machine's own console: sudo {names.command()} release-key add HEX trusts that builder's key, "
            f"sudo {names.command()} unsigned on allows unsigned builds")


def tools_digest(files):
    """What a release signs for the tools root installs: {name in the bundle:
    bytes}, each said as its own digest and its name, in the names' order,
    and the digest of that list."""
    h = hashlib.sha256()
    for name in sorted(files):
        h.update(f"{hashlib.sha256(files[name]).hexdigest()}  {name}\n".encode())
    return "sha256:" + h.hexdigest()


def verify(key, digest, sig, message=MESSAGE):
    """Why `sig` is not the release key's signature over `digest`, or ""."""
    key, sig = clean_key(key), str(sig or "").strip().lower()
    if not key:
        return "no release key is pinned here"
    if not re.fullmatch(r"sha256:[0-9a-f]{64}", str(digest or "")):
        return "the update names no digest to check"
    if not SIG_RE.fullmatch(sig):
        return "the controller sent no signature with it"
    try:
        from cryptography.exceptions import InvalidSignature
        from cryptography.hazmat.primitives.asymmetric.ed25519 import Ed25519PublicKey
    except ImportError:
        return "this node has no cryptography library to check a signature with (the provisioner installs it)"
    try:
        Ed25519PublicKey.from_public_bytes(bytes.fromhex(key)).verify(bytes.fromhex(sig), message + digest.encode())
    except InvalidSignature:
        return "its signature is not the pinned release key's"
    except ValueError as e:
        return f"the pinned key or the signature is not usable ({e})"
    return ""


def may_install(state, digest, sig):
    """(ok, words) for an update of `digest` carrying `sig`: taken with no
    key trusted here, taken when the signature is under a key this node
    trusts (the release key, its spare, or one added at its console, said as
    which), taken unsigned only where this node's console said so, refused
    otherwise."""
    if not trusted(state):
        return True, ""
    who, why = _signer(state, digest, sig, MESSAGE)
    if who:
        return True, f"signed by {who}"
    if unsigned_ok(state):
        return True, f"not checked ({why}): this node's console allows unsigned builds"
    return False, f"refused: {why}. This node takes only updates signed by {_named(state)}. {_console_can()}"


def may_keep_tools(state, digest, sig):
    """(ok, words) for root's copy of the bundle's tools, whose list is
    `digest` and came with `sig`: as may_install decides an update. Kept
    with no key trusted here, kept when the signature is under a key this
    node trusts, kept unsigned only where this node's console said so, and
    otherwise not: root goes on with the copy it has."""
    if not trusted(state):
        return True, ""
    who, why = _signer(state, digest, sig, TOOLS_MESSAGE)
    if who:
        return True, f"root's tools are signed by {who}"
    why = why.replace("the update names no digest to check", "the bundle holds none of root's tools")
    if unsigned_ok(state):
        return True, f"root's tools not checked ({why}): this node's console allows unsigned builds"
    return False, (f"refused: the tools root installs from this bundle are not signed by a key this node trusts ({why}), so "
                   f"root keeps the copy it has. This node takes only what is signed by {_named(state)}. {_console_can()}")
