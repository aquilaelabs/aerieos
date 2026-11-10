"""Whether new agent code is AerieOS's own release (R227 step 1).

A node took its agent's update on a digest the controller named, so whoever
held the controller could put any code on a node as root. A node that has
pinned AerieOS's release key takes an update only when a signature under
that key covers its digest: the key is in no controller's hands (the release
build signs with it), so a controller taken over cannot make one.

The key is pinned when the node is enrolled (`enroll --release-key HEX`, as
the Enroll script carries it) or at the machine's own console afterwards
(`aerieos-agent release-key HEX`), and is never taken from the
controller's word on a running node. A node with no key pinned updates as
before. A build from a branch carries no signature: a node its owner uses
for those says so at its console (`aerieos-agent unsigned on`), which is
kept in node.json like the key.

Ed25519, by the `cryptography` library the nodes are provisioned with
(tokenseal.py's): nothing here is hand-built, and a node that pinned a key
and lacks the library refuses the update rather than taking it unchecked.
"""
import re

from . import names

# What is signed: this line, then the agent zip's digest as hello names it
# ("sha256:" and 64 hex characters). The line keeps a signature made for
# anything else under the same key from passing here.
MESSAGE = b"aerieos agent v1\n"
KEY_RE = re.compile(r"[0-9a-f]{64}")
SIG_RE = re.compile(r"[0-9a-f]{128}")


def clean_key(text):
    """A release key as 64 hex characters, or "" when it is not one."""
    k = str(text or "").strip().lower()
    return k if KEY_RE.fullmatch(k) else ""


def pinned(state):
    return clean_key((state or {}).get("release_key"))


def unsigned_ok(state):
    return (state or {}).get("unsigned_ok") is True


def verify(key, digest, sig):
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
        Ed25519PublicKey.from_public_bytes(bytes.fromhex(key)).verify(bytes.fromhex(sig), MESSAGE + digest.encode())
    except InvalidSignature:
        return "its signature is not the pinned release key's"
    except ValueError as e:
        return f"the pinned key or the signature is not usable ({e})"
    return ""


def may_install(state, digest, sig):
    """(ok, words) for an update of `digest` carrying `sig`: taken with no
    key pinned (said so), taken when the signature holds, taken unsigned
    only where this node's console said so, refused otherwise."""
    key = pinned(state)
    if not key:
        return True, ""
    why = verify(key, digest, sig)
    if not why:
        return True, f"signed by the release key this node pinned ({key[:16]}…)"
    if unsigned_ok(state):
        return True, f"not checked ({why}): this node's console allows unsigned builds"
    return False, (f"refused: {why}. This node takes only updates signed by the release key it pinned ({key[:16]}…); "
                   "a controller built from a branch ships an unsigned agent. To allow those on this machine, at its "
                   f"own console: sudo {names.command()} unsigned on")
