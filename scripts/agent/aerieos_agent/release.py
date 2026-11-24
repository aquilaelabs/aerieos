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
sign with can be replaced by the spare with no node cut off. A build from a
branch carries no signature: a node its owner uses for those says so at its
console (`aerieos-agent unsigned on`), which is kept in node.json like the
key.

A node with no key takes what its controller sends, and says in the update's
job that nothing was checked. It pins at one more moment: its controller
names the release keys its own build carries beside every update
(`release_keys`), and the first update whose signature is under one of them
pins that one key here as the update is installed (first_pin): the key the
signature held under, and no other the controller named with it. That is
trust on first use, of a controller this node already took everything from; an
update with no signature, or one under another key, pins nothing, and a node
that has any key is never offered one this way. Nor is a node whose console
dropped the release key (`aerieos-agent release-key none`, kept in node.json
as release_unpinned): that is a person's choice, and it stands until a
person pins a key there again.

Ed25519, by the `cryptography` library the nodes are provisioned with
(tokenseal.py's): nothing here is hand-built, and a node that pinned a key
and lacks the library refuses the update rather than taking it unchecked.

The tools root installs from the bundle are held by the bundle's list below
(R267 step 28): the provisioner with the machine's own helper in it, the
helper that builds a session's view, the one that cuts a pack's install off
the network and the provisioner's family files are files a release ships
in it, and root keeps its copy of them only from a tar that list passed.

So is everything else a release ships in the bundle (R267 step 6): aerie,
its library, the shipped catalog, the publishers' keys a download is checked
against, the terminal's launcher and the hooks. The bundle carries the list
of those files, a line each with its sha256 (nodes/bundle.list, the form of
a SHA256SUMS file), and the release's signature over that list's digest
under a third line (nodes/bundle.sig). A pinned node unpacks a bundle only
when the signature is under a key it trusts and every file in the tar is
the one the list names: none changed, none missing, and none beside them
but what a controller adds of its own (BUNDLE_ADDS: a person's tool packs,
the vetted catalog's newer rows, the signatures and the list). A bundle
that fails this is unpacked nowhere, not in the job account's store and not
in root's copies, and the node goes on with the one it has
(may_keep_bundle). What a controller adds is still its word: a tool pack
and a catalog row are a person's and the catalog's, and no release signs
them.

A controller somebody builds on their own machine is not a release, and its
builder signs it with a key of their own. A node trusts such a key beside
the release key and its spare once a person adds it at the node's console
(`aerieos-agent release-key add HEX`, up to ALSO_MAX of them, kept in
node.json as release_also): an update signed by an added key, or a bundle
whose list one signed (root's tools among its files), is taken as one the
release signed, and said as what it is. Nothing a controller sends adds, changes or
drops one.

A signature says who made an agent, not when: every agent the release key
ever signed carries a good one, and an old agent put back on a node reopens
what the ones after it closed. So a node that trusts a key takes a signed
update only when the agent in it is not older than the one running: the
zip's own version is under the signature (AGENT_VERSION in the package it
holds, whose last number only ever goes up), read from the bytes that were
checked, and one whose number is below this agent's, or that names none, is
refused. A person who means to go back says so at the node's console
(`aerieos-agent older on`, kept in node.json like the word for unsigned
builds, and `older off` again afterwards). The agent a failed update puts
back by itself is the file it kept beside it, which no controller sends.
The same holds for a bundle, and with it root's tools, which come out of
the same checked tar: it ships the agent package's __init__.py of the tree
it was built from (BUNDLE_BUILD), listed and signed with the rest, and a
signed bundle whose build is below this agent's is refused the same way.
A bundle from before it names no build and has no floor under it yet.

A node enrolled before the release named a spare holds the first key alone.
It pins the spare on the release key's own word: a release's build signs,
with the first key, a statement that names the spare, under a line of its
own (tools/sign-agent.py writes it into agent.sig, and the controller hands
it on with its hello and with an update). A node that holds the first key
and no spare, on a statement whose signature holds under the key it pinned,
pins the spare named (spare_pin). The statement is the pinned key's and not
the controller's: one under any other key pins nothing, a key added at the
console among them, and so does one on a node that has a spare already or
whose console chose to pin no key. The statement signs the build that
made it, and one below this agent's names nothing: a release after it may
have retired that spare. One that names no build names nothing either, so
no statement can be passed off as one with its build taken away.
"""
import hashlib
import io
import re
import zipfile

from . import AGENT_VERSION, names
from .bundle import PACKAGE

# What is signed: this line, then the agent zip's digest as hello names it
# ("sha256:" and 64 hex characters). The line keeps a signature made for
# anything else under the same key from passing here.
MESSAGE = b"aerieos agent v1\n"
# ...and for the list of every file a release ships in the bundle: this
# line, then the digest of that list as the bundle carries it. Another
# line, so neither signature passes as the other.
BUNDLE_MESSAGE = b"aerieos bundle v1\n"
# ...and for the release key's word that another key is its spare, with the
# build that said it: this line, the spare, a line break and the build
# (spare_built). A third line, so a signature over an agent or a bundle's
# list never names a spare. (The first form of that word named no build
# and was taken nowhere; its line is not used again.)
SPARE_BUILT_MESSAGE = b"aerieos release spare v2\n"
# What a controller adds to the bundle beside the files a release ships, so
# what a release's list never names and a pinned node lets ride: a person's
# tool packs and the packs made on that install, which are theirs and differ
# on every install; the vetted catalog's newer rows, which are the catalog's
# and newer than any release; and the two members that carry the list and
# its signature themselves. Under any other name, a file the list does not
# name is refused.
BUNDLE_ADDS = re.compile(r"config/toolpacks\.json|config/toolpacks/[A-Za-z0-9][A-Za-z0-9._-]{0,79}\.bundle"
                         r"|config/toolchains\.catalog\.json|nodes/bundle\.list|nodes/bundle\.sig")
# One line of the list: a file's sha256, two spaces, its name in the bundle.
LIST_LINE = re.compile(r"([0-9a-f]{64})  ([^\n]+)")
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


def older_ok(state):
    """Whether this node's console said an older agent may be put back
    (`older on`)."""
    return (state or {}).get("older_ok") is True


# The agent's version as its package says it, and the line that says it.
VERSION_LINE = re.compile(r'^AGENT_VERSION = "(\d+)\.(\d+)\.(\d+)"[ \t]*$', re.M)
# What a page says of an update refused for its age.
OLDER = "older than the agent this node runs"
# ...and of a bundle refused for its age.
BUNDLE_OLDER = "its files are older than the agent this node runs"
BUNDLE_UNDATED = "its files name no build, so how old they are cannot be told"
# The member of the bundle that says which build its files are: the agent
# package's __init__.py of the tree the release was built from, a file its
# list names and its signature covers like any other (scripts/lib/
# bundleparts.py ships it). A bundle from before it carries none, and has
# no floor under it.
BUNDLE_BUILD = "scripts/agent/aerieos_agent/__init__.py"


def version_of(text):
    """(BUILD, version) the AGENT_VERSION line in `text` names, or (None,
    "") where it names none."""
    m = VERSION_LINE.search(str(text or ""))
    return (int(m.group(3)), ".".join(m.groups())) if m else (None, "")


def agent_build(body):
    """(BUILD, version) of the agent the zip `body` holds, as the package
    in it says them (AGENT_VERSION, whose last number is the BUILD), or
    (None, "") where the bytes are no agent's zip or its package names no
    version. Read from the very bytes a signature was checked over."""
    try:
        with zipfile.ZipFile(io.BytesIO(body)) as z:
            text = z.read(f"{PACKAGE}/__init__.py").decode("utf-8", "replace")
    except (KeyError, OSError, ValueError, zipfile.BadZipFile, TypeError):
        return None, ""
    return version_of(text)


def own_build():
    """This agent's BUILD: the last number of its AGENT_VERSION."""
    return int(AGENT_VERSION.rsplit(".", 1)[-1])


def unpinned(state):
    """Whether this node's console chose to pin no release key (release-key
    none): such a node pins none by itself, whatever its controller names."""
    return (state or {}).get("release_unpinned") is True


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




def bundle_list(text):
    """{name: sha256} as the bundle's list of its files says them, or None
    for a text that is not such a list: a line that is not a sha256, two
    spaces and a name, a name there twice, or a last line cut short."""
    lines = str(text or "").split("\n")
    if lines.pop() != "":
        return None
    held = {}
    for line in lines:
        m = LIST_LINE.fullmatch(line)
        if not m or m.group(2) in held:
            return None
        held[m.group(2)] = m.group(1)
    return held


def bundle_wrong(text, members):
    """Why a bundle's files are not the ones its list names, said of the
    first one that is wrong by name, or "". `members` is {name in the tar:
    the sha256 of its bytes}. A file the list names is there with the bytes
    listed; one it does not name is one a controller adds (BUNDLE_ADDS)."""
    listed = bundle_list(text)
    if listed is None:
        return "its list of files is not one a release makes"
    for name in sorted(set(listed) | set(members)):
        if name not in members:
            return f"{name} is missing: the release's list names it and the bundle does not hold it"
        if name in listed:
            if members[name] != listed[name]:
                return f"{name} is changed: its bytes are not the ones the release signed"
        elif not BUNDLE_ADDS.fullmatch(name):
            return f"{name} is not one a release ships: the release's list does not name it"
    return ""


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


def spare_built(spare_key, build):
    """What a release signs to name `spare_key` its spare as of `build`
    (the BUILD of the agent its tree holds): SPARE_BUILT_MESSAGE, the spare
    and the build, so a statement a later build retired cannot be passed off
    as one a node has not outgrown."""
    return SPARE_BUILT_MESSAGE + f"{spare_key}\n{int(build)}".encode()


def spare_said(key, said, floor=0):
    """The spare `said` names, where it is `key`'s own word for it: `said`
    is {"key": the spare, "build": the build that said it, "build_sig": the
    signature} as a release's build writes it (tools/sign-agent.py), signed
    by `key` over spare_built, and a build below `floor` names nothing,
    since a release after it may have retired that spare. "" for anything
    else: no statement, one in another shape, one that names no build (a
    statement from before builds said theirs, or one with its build taken
    away), one that names `key` itself, one whose signature is not `key`'s,
    and any where this node has no library to check it with. A "sig" beside
    the build, the word without it, is not read."""
    if not isinstance(said, dict) or not isinstance(said.get("key"), str):
        return ""
    key, second = clean_key(key), clean_key(said["key"])
    build, sig = said.get("build"), str(said.get("build_sig") or "").strip().lower()
    if not key or not second or second == key or not SIG_RE.fullmatch(sig):
        return ""
    if not isinstance(build, int) or isinstance(build, bool) or build < 0 or build < floor:
        return ""
    try:
        from cryptography.exceptions import InvalidSignature
        from cryptography.hazmat.primitives.asymmetric.ed25519 import Ed25519PublicKey
    except ImportError:
        return ""
    try:
        Ed25519PublicKey.from_public_bytes(bytes.fromhex(key)).verify(bytes.fromhex(sig), spare_built(second, build))
    except (InvalidSignature, ValueError):
        return ""
    return second


def spare_pin(state, said):
    """The spare a node pins by itself on the statement `said`, or "": the
    key the statement names, for a node that holds the release key and no
    spare, when the statement is signed by the release key it pinned
    (spare_said). Always "" for a node that has a spare (the one there is
    kept, whatever is named), for one that pinned no release key, and for
    one whose console chose to pin none. A key added at the console signs
    for a build and never for this: a statement under one names nothing."""
    if unpinned(state) or spare(state) or not pinned(state):
        return ""
    # A statement made by a build older than this agent may name a spare a
    # release since retired: under the floor that this agent is.
    return spare_said(pinned(state), said, own_build())


def named_keys(named):
    """The release keys a controller names beside an update, the ones its
    own build carries: a list of one or two keys, [] for anything else."""
    if not isinstance(named, (list, tuple)) or not all(isinstance(k, str) for k in named):
        return []
    return clean_keys(",".join(named))


def first_pin(state, digest, sig, named):
    """The key a node that trusts none pins on this update: the one of the
    keys its controller named that the update's signature is under, as a
    list of that one key. A second key the controller named beside it is
    the controller's bare word and pins nothing: a spare is pinned on the
    pinned key's own signed statement (spare_pin), the one way a node
    takes one by itself. [] where the signature is under none of them, and
    always [] for a node that trusts a key already (what a controller
    names never replaces or joins a key that is here) and for one whose
    console chose to pin none."""
    if trusted(state) or unpinned(state):
        return []
    return [k for k in named_keys(named) if not verify(k, digest, sig)][:1]


def _no_key(state, digest, sig, named):
    """What a node with no key says of the update it takes: that its console
    chose to pin none, or which named release key signed it, or that
    nothing was checked and why not."""
    if unpinned(state):
        return "not checked: this node's console chose to pin no release key"
    cand, why = named_keys(named), ""
    for key in cand:
        said = verify(key, digest, sig)
        if not said:
            return f"signed by a release key this node's controller names ({key[:16]}…), with none pinned here yet"
        why = why or said
    if not cand:
        why = ("no release key was named to check its signature against" if SIG_RE.fullmatch(str(sig or "").strip().lower())
               else "the controller sent no signature with it")
    why = why.replace("its signature is not the pinned release key's", "its signature is not under a release key the controller named")
    return f"not checked: no release key is pinned here, and {why}"


class Refusal(str):
    """A refusal's words as a job's log and this node's own log say them,
    whole: what was wrong, which keys this node takes and what its console
    can do. `cause` is the first of those alone, a phrase: what a page says
    of it, where the rest is a paragraph nobody reads on a bell."""
    cause = ""


def _refusal(cause, words):
    said = Refusal(words)
    said.cause = cause
    return said


def may_install(state, digest, sig, named=None, body=None):
    """(ok, words) for an update of `digest` carrying `sig`: taken with no
    key trusted here and said as unchecked (for want of a signature, or
    because the console chose to pin no key), or as signed by a release key
    the controller named with it (`named`, which first_pin then pins);
    taken when the signature is under a key this node trusts (the release
    key, its spare, or one added at its console, said as which), taken
    unsigned only where this node's console said so, refused otherwise.
    `named` is read only by a node that trusts no key.

    `body` is the update itself, the bytes `digest` is of. With it, a
    signed update is taken only when the agent in it is not older than
    this one (agent_build against own_build), unless this node's console
    said an older one may be put back (older_ok).

    A refusal's words are a Refusal: the whole of it for a log (which keys
    this node takes, what its console can do), and its cause alone, one
    phrase, for the job's error and the row a page draws from it: OLDER for
    its age, else what was wrong with its signature."""
    if not trusted(state):
        return True, _no_key(state, digest, sig, named)
    who, why = _signer(state, digest, sig, MESSAGE)
    if who:
        if body is not None and not older_ok(state):
            build, version = agent_build(body)
            if build is None or build < own_build():
                return False, _refusal(OLDER, f"refused: this agent ({version or 'which names no version'}) is {OLDER} "
                                              f"({AGENT_VERSION}). At this machine's own console: sudo {names.command()} "
                                              "older on lets an older agent be put back")
        return True, f"signed by {who}"
    if unsigned_ok(state):
        return True, f"not checked ({why}): this node's console allows unsigned builds"
    return False, _refusal(why, f"refused: {why}. This node takes only updates signed by {_named(state)}. {_console_can()}")




def may_keep_bundle(state, text, sig, members, build=None):
    """(ok, words) for a bundle the controller sent, before any of it is
    unpacked: `text` is the list of its files the tar carries (bytes, or ""
    with none), `sig` the signature that came with it, and `members` every
    member of the tar that is not a folder, {name: the sha256 of its bytes},
    or for one that is no plain file the words for what it is (a link, a
    device, a name there twice). `build` is the bytes of its BUNDLE_BUILD
    member, None where it has none.

    A signature says who made a bundle, not when, as of an agent: so a
    signed bundle whose BUNDLE_BUILD names a build below this agent's is
    refused unless this node's console said an older one may be put back
    (older_ok), and with it root's tools, which come out of the same
    checked tar. One that names no build is refused the same way: every
    release's bundle names its build, so one that names none is from
    before that, and how old cannot be told.

    Kept with nothing said by a node that trusts no key. Otherwise kept
    when the signature over the list's digest is under a key this node
    trusts (as may_install decides an update) and every file is the one the
    list names (bundle_wrong); kept unsigned or not matching only where
    this node's console allows unsigned builds, and said; refused otherwise,
    with the first file that is wrong named. A member that is no plain file
    is refused on any node that trusts a key, whatever its console allows:
    no controller packs one. A refusal's words are a Refusal: the whole of
    it for a log, and its cause alone for what is told to the controller."""
    if not trusted(state):
        return True, ""
    tail = (f"so this node keeps the bundle it has. This node takes only what is signed by {_named(state)}. "
            f"{_console_can()}")
    # A plain file is here by its sha256; anything else by what it is.
    odd = next((name for name in sorted(members) if not re.fullmatch(r"[0-9a-f]{64}", str(members[name]))), None)
    if odd is not None:
        return False, _refusal(f"it holds {odd}, which is {members[odd]}",
                               f"refused: this bundle holds {odd}, which is {members[odd]}, and a bundle carries plain files alone, {tail}")
    raw = text if isinstance(text, bytes) else str(text or "").encode("utf-8")
    digest = "sha256:" + hashlib.sha256(raw).hexdigest() if raw else ""
    who, why = _signer(state, digest, sig, BUNDLE_MESSAGE)
    if who:
        why = bundle_wrong(raw.decode("utf-8", "replace"), members)
        if not why:
            # Its build, from the member the signed list held to its bytes.
            at, version = version_of(build.decode("utf-8", "replace") if isinstance(build, bytes) else build)
            back = f"At this machine's own console: sudo {names.command()} older on lets an older one be put back"
            if at is None and not older_ok(state):
                return False, _refusal(BUNDLE_UNDATED, f"refused: this bundle's files name no build, so how old they are "
                                                       f"cannot be told, and this node keeps the bundle it has. {back}")
            if at is not None and at < own_build() and not older_ok(state):
                return False, _refusal(BUNDLE_OLDER, f"refused: this bundle's files are from agent {version}, "
                                                     f"{OLDER} ({AGENT_VERSION}), so this node keeps the bundle it has. {back}")
            return True, f"the bundle's files are signed by {who}"
    why = why.replace("the update names no digest to check", "the bundle carries no list of its files")
    if unsigned_ok(state):
        return True, f"the bundle's files not checked ({why}): this node's console allows unsigned builds"
    return False, _refusal(why, f"refused: this bundle's files are not ones signed by a key this node trusts ({why}), {tail}")
