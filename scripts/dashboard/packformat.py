"""The catalog's format number (R234).

Everything a catalog entry can be (a tool pack's bbtool.json, a Docker
app's bbapp.json, a coding agent's adapter) is written in one format, and
the format has a number. The promise the number keeps:

  - The format only grows. A manifest that is valid at one number is valid
    at every later one, and means what it meant: nothing already in the
    catalog is ever rewritten for something added beside it.
  - A manifest says the number it needs (`format`, 1 when it says none) and
    its entry in the signed index repeats it, so an install knows before it
    fetches anything whether an entry is one it reads.
  - An install too old for an entry says so on the card and adds nothing;
    it never guesses at a format it has not met.
  - An entry whose pack moved to a newer format keeps the pin of the
    manifest written in each earlier one a listed release still reads
    (`older`), and an install is offered the newest pin it reads (pin_for,
    below), with nothing said of the ones past it.
  - What a manifest can name but not describe (a source kind, a version
    resolver, a named hook shape, an app's blanks, a service's kind) is a
    primitive, written down in docs/tool-packs.md. A new primitive is a new
    number, never a change to an old one.

The framework's version is two numbers (the operator, 12 Nov: a version of
the catalog's own, moved whenever the framework changes), written X.Y:

  - X is the format above: it moves when an install that does not read it
    could not run the entry at all, and such an install hides the entry
    with what it needs.
  - Y moves when something is added that an install from before it simply
    leaves out, the rest meaning what it meant (a sign-in's flow, without
    which the agent signs in in its terminal; who a tool is by). An entry
    that uses it is still taken by every install that took it before. Y
    never goes back: 2.1 is followed by 2.2, or by 3.2 when X moves.

A manifest says both: `format`, the least X an install must read to run it
(a whole number, which is all a release from before the second number
takes there), and `framework`, the version it is written for ("2.1"), in
a key of its own beside it. What a manifest uses must be in the version it
says (needs, below), so the number an author reads off a manifest is what
an install has to know to do all of it.

What an entry's downloads are held to is the format's too, one mechanism
for a row AerieOS ships and for anybody's pack (pin_refused to held,
below): the shapes of a pin, a declared download, the keys an entry
carries and the sentence of an installer that keeps the network, and the
one word a card says of the whole, worked out from the entry alone.

unit/test_packformat.py holds the kept manifests of every number
(unit/packformat/N/) to this build, and `aerie lint` holds the ones a
release shipped unchanged, as it holds a shipped migration.

No imports from the rest of the dashboard: the catalog's own check loads
this beside toolpacks.py from a checkout of any release.
"""
import re

# The number this build reads, and every one before it.
FORMAT = 5
# ...and the framework's second number, which this build reads up to: what
# was added since that an earlier build leaves out. It never resets.
MINOR = 2
VERSION = f"{FORMAT}.{MINOR}"
# What each second number added, by the version that brought it.
ADDED = {
    (2, 1): "a coding agent's sign-in described as data (signin.flow), so the page runs it; who a tool is by (maker), "
            "and each maker's tool where a pack carries several (credits)",
    (2, 2): "a sign-in whose program ends by itself once signed in (signin.flow.ends exit), whose link may start in "
            "more than one way (signin.flow.url as a list), that says where who is signed in is read (signin.flow.who), "
            "and whose sign-out takes keys out of a settings file (signin.flow.forget)",
}
# What each number added, for the docs and for a person reading a refusal.
FORMATS = {
    1: "tool packs (install steps, layout, verbs, config), Docker apps, and a coding agent whose hooks are one of the named shapes "
       "(grouped or flat, snake or camel): what 0.9.0's first releases read",
    2: "a coding agent that describes its own hook protocol (hooks.document, hooks.payload as paths, hooks.answers), "
       "prompt_fires, the start event, and the briefing and the allow list handed over by hook",
    3: "declared downloads (install.fetch): every file an install takes from somewhere else, each with its address and "
       "its sha256, fetched and checked by AerieOS before the install steps run, which then run with no network",
    4: "a Docker app that declares its own fields (fields: each the variable it fills, its label, its kind, a default, a line "
       "of help and whether it is required) in place of the six blanks every app shared, one that runs on the machine's own "
       "network (network: host), and one marked as going (going: what to install in its place)",
    5: "every download held to something its entry carries: a shipped toolchain's download pinned (checksum pin: the version "
       "and the sha256 of the exact file), declared downloads for every kind of source, one named for a platform (platform) "
       "or held by its publisher's signature (signed) under a key the entry carries (keyring), an installer that keeps "
       "the network, with the sentence that says what it downloads by itself (online), and a pack's word that it "
       "downloads nothing (an empty install.fetch), which cuts its steps from the network; and how a newer pin is found, "
       "read by the tool that proposes one and by no install: a pin's found, a declared download's version, track and found, "
       "a repository's track and the tag its commit is fetched under, and the resolvers match, git-tag and git-branch; "
       "and what a package manager installs held the same way: what the entry asks pip or npm for (lock), resolved by that "
       "tool to exact files that are each a declared download, with the small files an install of them reads carried by a "
       "shipped row itself (files); and a coding agent's install held the same way (agent.install's fetch, keyring, online and "
       "steps in the place of script): its downloads declared, and its steps run from them, never a line a shell reads; "
       "and a container image held the same way: every image a Docker app's compose names carrying the digest of what is "
       "pulled (name:tag@sha256:...), and the images one of AerieOS's own services runs named so in its entry (images)",
}


# Who stands behind a catalog entry, as the signed index says it (`tier`)
# and as a person reads it (the operator, 12 Nov: Packaged by Aerie,
# Verified and Vetted, in place of official and vetted, which did not say
# who made what; Packaged, not Built, since the tool itself is somebody
# else's and the card names them: maker_of below):
#   official  one of AerieOS's own shipped rows, as a pack   Packaged by Aerie
#   aerie     a pack AerieOS's maintainers wrote             Packaged by Aerie
#   verified  a verified vendor's own pack, a shorter list   Verified
#   vetted    anybody's pack the maintainers reviewed        Vetted
# The words in a manifest and an index are stored ones and stay; a word this
# build has not met is read as vetted, the least any signed entry is, which
# is how a release from before `aerie` and `verified` reads them too.
TIERS = ("official", "aerie", "verified", "vetted")
TIER_WORDS = {"official": "Packaged by Aerie", "aerie": "Packaged by Aerie", "verified": "Verified", "vetted": "Vetted"}


def tier_of(word):
    """A signed entry's tier as this build keeps it."""
    return word if word in TIERS else "vetted"


# Who a tool is by (the operator, 12 Nov): the organization or the person
# that makes it, as its manifest, its index entry or its shipped row says in
# `maker`, a short line of plain words drawn on its card beside the tier. A
# pack of several makers' tools is by AerieOS and names each under
# `credits`, [{name, maker}], which its Details page lists. An extra: a
# build from before it leaves both out.
MAKER_MAX, CREDITS_MAX = 60, 24


def _line(v):
    """A name as a card draws it: one line of printable words, or ""."""
    s = " ".join(str(v).split()) if isinstance(v, str) else ""
    return s if s and len(s) <= MAKER_MAX and s.isprintable() and not any(c in s for c in "<>{}\\") else ""


def maker_of(doc):
    """Who the tool is by, as `doc` says it, or "" where it says nobody or
    says it in a way a card would not draw."""
    return _line(doc.get("maker")) if isinstance(doc, dict) else ""


def credits_of(doc):
    """[{name, maker}] for the tools a pack of several makers' carries, each
    a line; a row that names no tool is left out."""
    rows = doc.get("credits") if isinstance(doc, dict) else None
    out = []
    for c in rows if isinstance(rows, list) else []:
        name = _line(c.get("name")) if isinstance(c, dict) else ""
        if name:
            out.append({"name": name, "maker": _line(c.get("maker"))})
    return out[:CREDITS_MAX]


# What a catalog entry is about, beyond its kind (R256, the operator, 18 Nov:
# a fixed list the catalog keeps, not tags anybody writes): each index entry
# names one to three of these keys in `topics`, the catalog's check refuses
# any other word, and the Library's Topic pulldown offers them in this order.
# A key is never renamed or taken back, only added to: an install reads the
# ones it knows and leaves out the rest, as a build from before topics does.
TOPICS = {
    "languages": "Languages and SDKs", "mobile": "Mobile", "web": "Web", "databases": "Databases",
    "ai": "AI and models", "media": "Media", "home": "Home and IoT", "files": "Files and backup",
    "network": "Networking", "security": "Security", "devtools": "Dev tools", "monitoring": "Monitoring",
    "productivity": "Productivity", "documents": "Documents",
}
TOPICS_MOST = 3


def topics_of(doc):
    """The topics an index entry names that this build knows, in its own
    order, three at most; [] where it names none."""
    got = doc.get("topics") if isinstance(doc, dict) else None
    out = []
    for t in got if isinstance(got, list) else []:
        if isinstance(t, str) and t in TOPICS and t not in out:
            out.append(t)
    return out[:TOPICS_MOST]


def topics_refused(doc):
    """Why an index entry's topics are not the catalog's, or "": a list of
    one to three keys of TOPICS, none twice. An entry with none is let
    through, so the catalog's older entries pass until they are tagged."""
    got = doc.get("topics") if isinstance(doc, dict) else None
    if got is None:
        return ""
    if not isinstance(got, list) or not 1 <= len(got) <= TOPICS_MOST:
        return f"topics names one to {TOPICS_MOST} of: {', '.join(TOPICS)}"
    bad = [str(t) for t in got if t not in TOPICS]
    if bad:
        return f"topics has {', '.join(bad[:3])}, not one of the catalog's: {', '.join(TOPICS)}"
    if len(set(got)) != len(got):
        return "topics names one twice"
    return ""


# ---- what a download is held to ---------------------------------------------
# Whatever an entry fetches from somewhere else is held to something the
# entry itself carries, the entry being held by the signed catalog or the
# signed release: the sha256 of the exact file (a pin), its publisher's
# signature under a key the entry carries, or a git commit. The shapes
# below are the format's, the same for a row AerieOS ships and for anybody's
# pack, and nothing here knows a vendor: a pin that moves is moved in the
# entry.
#
# A platform as an entry keys what differs by machine: the keys source.url
# takes, "<os>/<arch>" with "<os>/*" for any architecture of a system, and
# linux-musl for a build that is not glibc's.
PLATFORM_KEY = re.compile(r"^(linux|linux-musl|darwin)/(amd64|arm64|\*)$")
SHA256 = re.compile(r"^[0-9a-f]{64}$")
PIN_VERSION = re.compile(r"^[A-Za-z0-9][A-Za-z0-9._+-]{0,63}$")
PIN_KEYS = frozenset(("from", "version", "sha256", "found"))
PIN_PLATFORMS = 8

# How a newer pin is found is the entry's own too, written for the tool
# that proposes one (tools/pins.py) and read by nothing at install time: an
# install takes the pin and asks nobody. Two parts, each a primitive by its
# name:
#   how the newest version is found (a row's source.version, a declared
#   download's track, a repository's source.track), by one of these
#   resolvers;
TRACK_RESOLVERS = ("text", "github-release", "node-index", "zig-index", "match", "git-tag", "git-branch")
#   and how the new file's digest is learned from its publisher's own
#   statement without downloading it (`found`), written as a checksum that
#   asks the origin is. Where the publisher states no sha256, the tool
#   downloads the file and hashes it itself.
FOUND_FROM = ("json", "android-repo", "go-json", "none", "file", "github-asset", "zsync", "signature", "zig-index")
# A repository's commit, the tag it may be fetched under, and the
# resolvers that find a commit to pin.
COMMIT = re.compile(r"^[0-9a-f]{40}$|^[0-9a-f]{64}$")
GIT_REF = re.compile(r"^(?!.*\.\.)[A-Za-z0-9][A-Za-z0-9._+/-]{0,99}$")
GIT_RESOLVERS = ("git-tag", "git-branch")


def found_refused(spec, what="its pin's found"):
    """Why `spec` is not how a digest is learned from a publisher's own
    statement, or "": an object written as a checksum that asks the origin
    is, its `from` one of FOUND_FROM."""
    if not isinstance(spec, dict) or spec.get("from") not in FOUND_FROM:
        return f"{what} is how a newer file's digest is learned from its publisher, from one of: {', '.join(FOUND_FROM)}"
    return ""


def track_refused(spec, what="track", among=TRACK_RESOLVERS):
    """Why `spec` is not how a newer version is found, or "": an object
    naming one of the resolvers, written as a row's source.version is."""
    if not isinstance(spec, dict) or spec.get("resolver") not in among:
        return f"{what} is how a newer version is found, by one of: {', '.join(among)}"
    return ""


def pin_refused(ck):
    """Why a row's source.checksum is not a pin as the format writes one,
    or "": {"from": "pin", "version": the version the file is (left out for
    a download with none in its address), "sha256": the digest of the exact
    file, 64 hex digits, or one per platform}. It may say how a newer
    file's digest is learned (`found`), which no install reads."""
    if not isinstance(ck, dict) or ck.get("from") != "pin":
        return "its checksum is no pin"
    if set(ck) - PIN_KEYS:
        return f"its pin names {', '.join(sorted(set(ck) - PIN_KEYS))}: a pin is from, version and sha256, and may say found"
    v = ck.get("version")
    if v is not None and not (isinstance(v, str) and PIN_VERSION.fullmatch(v)):
        return "its pin's version is not a version: up to 64 of letters, digits, dot, dash, plus and underscore"
    if ck.get("found") is not None and found_refused(ck["found"]):
        return found_refused(ck["found"])
    sha = ck.get("sha256")
    if isinstance(sha, str):
        return "" if SHA256.fullmatch(sha) else "its pin's sha256 is not 64 hex digits, in lower case"
    if not isinstance(sha, dict) or not 1 <= len(sha) <= PIN_PLATFORMS:
        return "its pin's sha256 is the digest of the file, or one per platform"
    for plat, digest in sha.items():
        if not (isinstance(plat, str) and PLATFORM_KEY.fullmatch(plat)):
            return f"its pin names a digest for {str(plat)[:40]}, which is no platform AerieOS names"
        if not (isinstance(digest, str) and SHA256.fullmatch(digest)):
            return f"its pin's sha256 for {plat} is not 64 hex digits, in lower case"
    return ""


# The pack format that brought the parts below (and the pin above): an
# install that does not read it could not run an entry that uses them.
HELD_FORMAT = 5
# A declared download: how many an entry may name, the address it is fetched
# from (https and nothing else) and the file inside the entry's directory
# it is kept as. The number is what a package manager's set asks for (lock,
# below): a tool with a few hundred packages under it declares each one.
FETCH_MAX = 256
HTTPS = re.compile(r"^https://[A-Za-z0-9.-]{1,253}(:\d{1,5})?/[\x21-\x7e]{0,1900}$")
REL = re.compile(r"^(?!/)(?!.*(?:^|/)\.\.?(?:/|$))[A-Za-z0-9._/-]{1,200}$")
FETCH_KEYS = frozenset(("url", "sha256", "to", "platform", "signed", "version", "track", "found"))
# A publisher's keys an entry carries: a few, each an armored public key
# under a plain file name, which a signature's `keys` names.
KEY_NAME = re.compile(r"^[A-Za-z0-9][A-Za-z0-9._-]{0,63}$")
KEYRING_MOST, KEY_MAX = 4, 32 * 1024
ARMOR = ("-----BEGIN PGP PUBLIC KEY BLOCK-----", "-----END PGP PUBLIC KEY BLOCK-----")
# The sentence an installer that keeps the network says of itself.
ONLINE_MAX = 300


def platforms_meet(a, b):
    """Whether two downloads, each for the platform it names (none: every
    one), can both be for one machine."""
    if not a or not b:
        return True
    (ao, _, aa), (bo, _, ba) = a.partition("/"), b.partition("/")
    return ao == bo and (aa == ba or "*" in (aa, ba))


def fetch_checked(raw, what="install.fetch", reserved=()):
    """An entry's declared downloads held to their shape: (clean, errors,
    new). Each is {url, to} with exactly one of sha256 (the digest of what
    the address answers) and signed ({sig, keys}: its publisher's detached
    signature and the name of the keys it is checked with), and may name
    the platform it is for. A file is kept once for a machine: two for
    platforms that cannot meet may share a name. `clean` keeps sha256 as ""
    on a signed one, so every row has the three keys format 3 gave it;
    `new` names what of format 5 they use, for the manifest's number.
    `reserved` are file names an entry may not write over.

    From format 5 a download may say the version it is (`version`), which
    fills {version} in its address and its signature's, never in the name
    it is kept as: the steps read one path whatever the version, so a pin
    that moves changes the version and the digest and nothing else. Beside
    it, for the tool that proposes a newer pin and for no install, how a
    newer version is found (`track`) and how its digest is learned
    (`found`)."""
    if not isinstance(raw, list) or len(raw) > FETCH_MAX:
        return [], [f"{what} lists up to {FETCH_MAX} downloads, each {{url, sha256, to}}"], set()
    clean, errors, new = [], [], set()
    for i, f in enumerate(raw):
        # One sentence: what each key is, and what format 5 adds, is the
        # doc's to say (docs/tool-packs.md, Declared downloads).
        said = f"{what} {i + 1} is {{url, sha256, to}}, each named once, as Declared downloads in docs/tool-packs.md writes one"
        if not isinstance(f, dict) or set(f) - FETCH_KEYS:
            errors.append(said)
            continue
        url, to, plat = f.get("url"), f.get("to"), f.get("platform")
        sha, signed = f.get("sha256") or None, f.get("signed")
        version, track, found = f.get("version"), f.get("track"), f.get("found")
        ok = isinstance(url, str) and HTTPS.fullmatch(url) and isinstance(to, str) and REL.fullmatch(to) and to not in reserved
        ok = ok and (sha is None) != (signed is None)
        ok = ok and (sha is None or (isinstance(sha, str) and SHA256.fullmatch(sha)))
        ok = ok and (signed is None or (isinstance(signed, dict) and set(signed) == {"sig", "keys"}
                                        and isinstance(signed["sig"], str) and HTTPS.fullmatch(signed["sig"])
                                        and isinstance(signed["keys"], str) and KEY_NAME.fullmatch(signed["keys"])))
        ok = ok and (plat is None or (isinstance(plat, str) and PLATFORM_KEY.fullmatch(plat)))
        ok = ok and not any(c["to"] == to and platforms_meet(c.get("platform"), plat) for c in clean)
        if not ok:
            errors.append(said)
            continue
        # The version it is, and how a newer one is found.
        named = "{version}" in url or (isinstance(signed, dict) and "{version}" in signed["sig"])
        if version is not None and not (isinstance(version, str) and PIN_VERSION.fullmatch(version)):
            errors.append(f"{what} {i + 1}'s version is not a version: up to 64 of letters, digits, dot, dash, plus and underscore")
            continue
        if named and version is None:
            errors.append(f"{what} {i + 1} has {{version}} in its address and says no version to fill it with")
            continue
        if track is not None and (track_refused(track, f"{what} {i + 1}'s track") or version is None):
            errors.append(track_refused(track, f"{what} {i + 1}'s track")
                          or f"{what} {i + 1} says track and no version: a download with no version has nothing to track")
            continue
        if found is not None and (found_refused(found, f"{what} {i + 1}'s found") or signed is not None):
            errors.append(found_refused(found, f"{what} {i + 1}'s found")
                          or f"{what} {i + 1} says found and is held by a signature: there is no digest to learn")
            continue
        row = {"url": url, "sha256": sha or "", "to": to}
        if plat:
            row["platform"] = plat
            new.add("platform")
        if signed:
            row["signed"] = {"sig": signed["sig"], "keys": signed["keys"]}
            new.add("signed")
        for key, v in (("version", version), ("track", track), ("found", found)):
            if v is not None:
                row[key] = v
                new.add(key)
        clean.append(row)
    return clean, errors, new


def download_address(f, key="url"):
    """A declared download's address as it is fetched: {version} filled
    with the version the entry says it is. `key` "sig" answers its
    signature's the same way."""
    signed = f.get("signed") if isinstance(f.get("signed"), dict) else {}
    text = str((signed.get("sig") if key == "sig" else f.get("url")) or "")
    return text.replace("{version}", f["version"]) if isinstance(f.get("version"), str) else text


def fits_machine(plat, machine):
    """Whether a download named for `plat` is one a machine that is
    `machine` ("<os>/<arch>") fetches: one that names none is everybody's,
    and a machine that has not said what it is is not judged."""
    return not plat or not machine or plat == machine or plat == machine.partition("/")[0] + "/*"


def downloads_said(fetch, machine=""):
    """An entry's declared downloads as a page reads them, each the same
    seven keys, all strings: `to` (the file it is kept as), `url`, `held`
    (how it is held: "sha256" or "signed"), `sha256` (the digest, "" on a
    signed one), `keys` and `sig` (the name of the keys a signed one is
    checked with and its signature's address, "" otherwise) and `platform`
    (the one it is for, "" for every one). `fetch` is the list as a
    manifest, the validator or a row's source has it; with `machine`, the
    downloads that machine fetches alone. An address is the one fetched,
    its {version} filled with the version the entry says (download_address)."""
    out = []
    for f in fetch if isinstance(fetch, list) else []:
        if not isinstance(f, dict) or not f.get("url"):
            continue
        signed = f.get("signed") if isinstance(f.get("signed"), dict) else {}
        sha = f["sha256"] if isinstance(f.get("sha256"), str) and SHA256.fullmatch(f["sha256"]) else ""
        plat = f["platform"] if isinstance(f.get("platform"), str) else ""
        if not fits_machine(plat, machine):
            continue
        how = "sha256" if sha else "signed" if signed.get("keys") else ""
        out.append({"to": str(f.get("to") or "")[:200], "url": download_address(f)[:2000], "held": how, "sha256": sha,
                    "keys": str(signed.get("keys") or "")[:64] if how == "signed" else "",
                    "sig": download_address(f, "sig")[:2000] if how == "signed" else "", "platform": plat[:40]})
    return out[:FETCH_MAX]


def keyring_checked(raw, what="install.keyring"):
    """The publisher's keys an entry carries, held to their shape: (clean,
    errors). {name: an armored public key}: a few, each under a plain file
    name and no larger than a key is."""
    said = (f"{what} maps up to {KEYRING_MOST} plain file names to a publisher's armored public key "
            f"({ARMOR[0]} ...), each at most {KEY_MAX // 1024} KB")
    if not isinstance(raw, dict) or not 1 <= len(raw) <= KEYRING_MOST:
        return {}, [said]
    for name, key in raw.items():
        text = key.strip() if isinstance(key, str) else ""
        if not (isinstance(name, str) and KEY_NAME.fullmatch(name) and len(text) <= KEY_MAX and text.startswith(ARMOR[0])
                and text.endswith(ARMOR[1]) and all(c.isprintable() or c in "\r\n" for c in text) and text.isascii()):
            return {}, [said]
    return {name: key.strip() + "\n" for name, key in raw.items()}, []


def online_checked(raw, what="install.online"):
    """The sentence an installer that keeps the network says, held to its
    shape: (sentence, errors). One line of plain words: what it downloads
    by itself, and from where."""
    text = " ".join(raw.split()) if isinstance(raw, str) else ""
    if not (8 <= len(text) <= ONLINE_MAX and text.isprintable() and not any(c in text for c in "<>{}\\")):
        return "", [f"{what} is one sentence of up to {ONLINE_MAX} plain characters: what its installer downloads by itself, and from where"]
    return text, []


# ---- an image a container runs ------------------------------------------------
# A container image is held as a download is, by the digest of what is
# pulled: `name[:tag][@sha256:<64 hex>]`. With a digest, that manifest is
# what a node pulls and runs (a list's digest covers every platform the
# list names), and the tag beside it is what a person reads and what the
# tool that proposes a newer pin asks the registry about. With none, the
# tag is all there is, and the registry may serve another image under it
# tomorrow. From format 5 a Docker app names every image by digest
# (nasapps.check_app), and each of AerieOS's own services does in its
# entry's `images` (images_checked).
IMAGE_REF = re.compile(r"(?P<name>[\w./-]+)(?::(?P<tag>[\w.-]+))?(?:@(?P<digest>sha256:[0-9a-f]{64}))?")
IMAGE_KEY = re.compile(r"^[a-z][a-z0-9-]{0,31}$")
IMAGES_MOST = 12


def image_parts(ref):
    """{name, tag, digest} of an image reference, "" for the part it does
    not say, or None for what is no reference."""
    m = IMAGE_REF.fullmatch(ref) if isinstance(ref, str) else None
    return {k: m.group(k) or "" for k in ("name", "tag", "digest")} if m else None


def image_digest(ref):
    """The digest an image reference carries, or ""."""
    return (image_parts(ref) or {}).get("digest", "")


def image_refused(ref):
    """Why an image reference is held to nothing, or "": it carries the
    digest of what is pulled, or names a tag that is not latest, which is
    what an app from before format 5 and a person's own compose file are
    held to."""
    parts = image_parts(ref)
    if not parts:
        return "is no image reference: name:tag, with @sha256: and the 64 hex digits of its digest where it is held by one"
    if not parts["digest"] and parts["tag"] in ("", "latest"):
        return "is not pinned to a tag (never latest), so an update could change it under you"
    return ""


def image_said(ref):
    """An image reference as a person reads it: its name and tag, and the
    first twelve digits of the digest it is held by."""
    parts = image_parts(ref)
    if not parts:
        return str(ref or "")[:200]
    return parts["name"] + (f":{parts['tag']}" if parts["tag"] else "") + (f" ({parts['digest'][7:19]})" if parts["digest"] else "")


def images_checked(raw, what="images"):
    """The images an entry of AerieOS's own runs, held to their shape:
    (clean, errors). {key: reference}: each under the name its entry's
    module reads it by, and each with its tag and its digest."""
    said_ = (f"{what} maps up to {IMAGES_MOST} names to the image each is, as name:tag@sha256: and the 64 hex digits "
             "of its digest: the tag is what a person reads, the digest what is pulled")
    if not isinstance(raw, dict) or not 1 <= len(raw) <= IMAGES_MOST:
        return {}, [said_]
    for key, ref in raw.items():
        parts = image_parts(ref)
        if not (isinstance(key, str) and IMAGE_KEY.fullmatch(key) and parts and parts["tag"] and parts["digest"]):
            return {}, [said_]
    return dict(raw), []


IMAGES_SAID = "every image it runs is named by the digest its entry carries"


def images_held(refs):
    """(word, why) for the images an entry runs, as held() answers: pinned
    only when every one carries its digest, open with the first that does
    not."""
    refs = list(refs) if isinstance(refs, (list, tuple)) else []
    if not refs:
        return "open", "its entry names no image"
    for ref in refs:
        if not image_digest(ref):
            return "open", f"{str(ref)[:120]} is named by its tag alone: the registry may serve another image under it"
    return "pinned", IMAGES_SAID


# A compose file's image lines, read and written as text so the file keeps
# its layout and its comments: each `image:` line's value, bare or quoted.
COMPOSE_IMAGE = re.compile(r"^(?P<head>[ \t]+image:[ \t]*)(?P<q>[\"']?)(?P<ref>[^\s\"'#]+)(?P=q)(?P<tail>[ \t]*(?:#.*)?)$", re.M)


def compose_images(text):
    """The image references a compose file's `image:` lines name, in the
    file's order, each once."""
    out = []
    for m in COMPOSE_IMAGE.finditer(str(text or "")):
        if m.group("ref") not in out:
            out.append(m.group("ref"))
    return out


def compose_repinned(text, moved):
    """A compose file with each image reference in `moved` ({old: new})
    written as its new one, on its own line and nowhere else."""
    return COMPOSE_IMAGE.sub(lambda m: m.group("head") + m.group("q") + moved.get(m.group("ref"), m.group("ref")) + m.group("q") + m.group("tail"),
                             str(text or ""))


# ---- what a package manager installs ----------------------------------------
# An install step that runs `pip install` or `npm install` downloads what
# the manager resolves that day, which is held to nothing. So an entry says
# what it asks its manager for as data (`lock`), the tool that proposes a
# pin resolves that to exact files (tools/pins.py, by the manager's own
# resolver), and each file is a declared download of the entry like any
# other: fetched and held to its sha256 by AerieOS before a step runs. The
# step then installs from the directory they landed in, with no index and
# no network. Nothing here is read by an install: a lock is how the set is
# found again, as a download's track is.
#
# A lock owns a directory inside the entry (`to`): every declared download
# kept under it is the lock's, written by the tool and replaced whole when
# the lock moves, and the entry's other downloads are left alone. Beside
# them go the small files the manager installs by (pip's requirements with
# their hashes, npm's package.json and its lock), which a pack keeps in its
# repository and a shipped row carries itself (`files`, below).
#
#   pip   requirements (what pip is asked for, as a requirements file
#         writes each), python (the version it installs for) and `for`: the
#         platforms it is resolved for, each with the resolver's own name
#         for it. Wheels only: a source distribution runs its own code at
#         install, so a package with no wheel for a platform is refused.
#   npm   requirements (what npm is asked for: a name, or name@range).
#         Every package's tarball is a download, one named for a system or
#         a processor for that platform alone.
LOCK_KINDS = ("pip", "npm")
LOCK_KEYS = {"pip": frozenset(("kind", "to", "requirements", "python", "for")), "npm": frozenset(("kind", "to", "requirements"))}
LOCK_MOST, LOCK_REQS = 4, 64
# What a manager is asked for: one line that starts with a name, so it can
# never be read as an option of the resolver's.
REQUIREMENT = re.compile(r"^[A-Za-z0-9@][\x20-\x7e]{0,199}$")
PYTHON = re.compile(r"^3\.\d{1,2}$")
LOCK_TARGET = re.compile(r"^[A-Za-z0-9][A-Za-z0-9_.-]{0,63}$")
# The small files a shipped row carries into its directory: a few, text,
# and small together. A pack's files are its repository.
FILES_MOST, FILES_MAX = 8, 96 * 1024


def lock_checked(raw, what="install.lock"):
    """What an entry asks a package manager for, held to its shape:
    (clean, errors). A list of up to LOCK_MOST locks, each {kind, to,
    requirements} with what its kind adds, no two of them owning one
    directory or one inside the other."""
    said = (f"{what} lists up to {LOCK_MOST} of {{kind, to, requirements}}: the package manager ({', '.join(LOCK_KINDS)}), the directory inside "
            f"the entry its downloads are kept in, and up to {LOCK_REQS} things it is asked for, each one line that starts with a name; "
            'pip adds python ("3.12") and for ({platform: the resolver\'s name for it})')
    if not isinstance(raw, list) or not 1 <= len(raw) <= LOCK_MOST:
        return [], [said]
    clean = []
    for lk in raw:
        kind = lk.get("kind") if isinstance(lk, dict) else None
        if kind not in LOCK_KINDS or set(lk) - LOCK_KEYS[kind]:
            return [], [said]
        to, reqs = lk.get("to"), lk.get("requirements")
        ok = isinstance(to, str) and REL.fullmatch(to) and isinstance(reqs, list) and 1 <= len(reqs) <= LOCK_REQS
        ok = ok and all(isinstance(r, str) and REQUIREMENT.fullmatch(r) and r == r.strip() for r in reqs)
        ok = ok and not any(to == c["to"] or to.startswith(c["to"] + "/") or c["to"].startswith(to + "/") for c in clean)
        if kind == "pip":
            plats = lk.get("for")
            ok = ok and isinstance(lk.get("python"), str) and PYTHON.fullmatch(lk["python"])
            ok = ok and isinstance(plats, dict) and 1 <= len(plats) <= PIN_PLATFORMS
            ok = ok and all(isinstance(p, str) and PLATFORM_KEY.fullmatch(p) and isinstance(t, str) and LOCK_TARGET.fullmatch(t) for p, t in plats.items())
        if not ok:
            return [], [said]
        clean.append({k: lk[k] for k in ("kind", "to", "requirements", "python", "for") if k in lk})
    return clean, []


def lock_of(locks, to):
    """The lock that owns the file an entry keeps as `to`, or None: the
    one whose directory it is under."""
    for lk in locks if isinstance(locks, list) else []:
        if isinstance(lk, dict) and isinstance(lk.get("to"), str) and str(to).startswith(lk["to"] + "/"):
            return lk
    return None


def files_checked(raw, what="source.files"):
    """The small files a shipped row carries, held to their shape: (clean,
    errors). {path: text}: each a file inside the row's directory that
    AerieOS writes before anything of the row runs, never one of its own
    marks or of git's."""
    said = (f"{what} maps up to {FILES_MOST} files inside the row's directory to their text, {FILES_MAX // 1024} KB together: "
            "what a package manager installs by (its requirements, its lock), written before the steps run")
    if not isinstance(raw, dict) or not 1 <= len(raw) <= FILES_MOST:
        return {}, [said]
    for path, text in raw.items():
        ok = isinstance(path, str) and REL.fullmatch(path) and isinstance(text, str)
        ok = ok and not any(part == ".git" or part.startswith(".bb-") for part in path.split("/"))
        ok = ok and all(c.isprintable() or c in "\n\t" for c in text)
        if not ok:
            return {}, [said]
    if sum(len(t.encode()) for t in raw.values()) > FILES_MAX:
        return {}, [said]
    return dict(raw), []


# ---- a variable an entry may set, and a system package it may name ------------
# An entry sets variables in three places: a pack's or a row's layout.env,
# which reaches every job on the node; a row's source.env and an agent's
# install env, which an installer runs with; and an agent's env, which its
# sessions and its sign-in run with. One rule for all of them: a name of
# capitals, digits and underscores that is none of the ones a loader, a
# shell, an interpreter, git, ssh or AerieOS itself reads at its start to
# find code to run, or to know who and where the account is.
ENV_NAME = re.compile(r"[A-Z][A-Z0-9_]{0,40}")
ENV_KEPT = frozenset(("PATH", "HOME", "USER", "LOGNAME", "SHELL", "TMPDIR", "IFS", "ENV", "BASH_ENV", "PROMPT_COMMAND",
                      "PYTHONSTARTUP", "PYTHONPATH", "PERL5OPT", "RUBYOPT", "NODE_OPTIONS", "GIT_EXEC_PATH"))
ENV_KEPT_PREFIXES = ("LD_", "DYLD_", "GIT_SSH", "GIT_CONFIG", "SSH_", "BB_", "BUILDERBOT_", "AERIEOS_")
ENV_SAID = ("a name of capitals, digits and underscores, never one a loader, a shell, an interpreter, git, ssh or AerieOS "
            "reads at its start (PATH, HOME, LD_*, BASH_ENV, PYTHONPATH, NODE_OPTIONS, GIT_SSH*, SSH_*, BB_* and their like)")


def env_name_ok(name):
    """Whether an entry may set the variable `name` (ENV_NAME, ENV_KEPT,
    ENV_KEPT_PREFIXES): the one rule for every place an entry sets one."""
    return isinstance(name, str) and bool(ENV_NAME.fullmatch(name)) and name not in ENV_KEPT and not name.startswith(ENV_KEPT_PREFIXES)


# What a recipe may list for a node's package manager to install as root (a
# row's or a pack's `system`) is a package's name and nothing a package
# manager reads as anything else: it starts with a letter or a digit, never
# a dash (an option), and ends in neither `-` nor `+` (apt's suffixes for
# remove and install). An entry may give alternatives, NAME|NAME, of which
# a node installs the first its release carries, and a portage name is
# CATEGORY/NAME; each part is held to the shape.
SYSTEM_NAME = re.compile(r"[A-Za-z0-9][A-Za-z0-9.+:_-]*")
SYSTEM_NAME_MAX = 80
SYSTEM_SLASHED = ("emerge",)
SYSTEM_MANAGER = re.compile(r"[a-z]{2,12}")
SYSTEM_MOST = 120


def system_name_ok(name, manager=""):
    """Whether `name` is an entry of a `system` list for `manager`: one
    package name, or alternatives, each of SYSTEM_NAME's shape."""
    if not (isinstance(name, str) and 1 <= len(name) <= SYSTEM_NAME_MAX):
        return False
    for alt in name.split("|"):
        parts = alt.split("/") if manager in SYSTEM_SLASHED else [alt]
        if len(parts) > 2 or not all(SYSTEM_NAME.fullmatch(p) and p[-1] not in "-+" for p in parts):
            return False
    return True


def system_refused(sysd):
    """Why a row's `system` is not {package manager: [package names]}, or ""."""
    if sysd is None:
        return ""
    if not (isinstance(sysd, dict) and all(isinstance(k, str) and SYSTEM_MANAGER.fullmatch(k) and isinstance(v, list) and len(v) <= SYSTEM_MOST
                                           and all(system_name_ok(n, k) for n in v) for k, v in sysd.items())):
        return "its system packages are not package names: each starts with a letter or a digit and ends in neither - nor +"
    return ""


def source_refused(src):
    """Why a row's source says something of its downloads that the format
    does not write, or "": its pin, its declared downloads, the keys it
    carries, whether its steps keep the network, what it asks a package
    manager for and the small files it carries."""
    if not isinstance(src, dict):
        return "it has no source"
    ck = src.get("checksum")
    if isinstance(ck, dict) and ck.get("from") == "pin" and pin_refused(ck):
        return pin_refused(ck)
    errors = []
    if src.get("fetch") is not None:
        errors += fetch_checked(src["fetch"], "source.fetch")[1]
    if src.get("keyring") is not None:
        errors += keyring_checked(src["keyring"], "source.keyring")[1]
    if src.get("online") is not None:
        errors += online_checked(src["online"], "source.online")[1]
        if src.get("offline"):
            errors.append("source.online and source.offline are both said: its steps keep the network or run with none")
    if src.get("offline") not in (None, True, False):
        errors.append("source.offline is true or false")
    if src.get("lock") is not None:
        errors += lock_checked(src["lock"], "source.lock")[1]
    if src.get("files") is not None:
        errors += files_checked(src["files"], "source.files")[1]
    if src.get("env") is not None and not (isinstance(src["env"], dict) and all(env_name_ok(k) and isinstance(v, str) for k, v in src["env"].items())):
        errors.append(f"source.env maps the installer's own variables to their values, each {ENV_SAID}")
    # A repository's pin: the commit, the tag it is fetched under, and how
    # the commit to pin is found.
    git = src.get("kind") == "git"
    if src.get("commit") is not None and git and not (isinstance(src["commit"], str) and COMMIT.fullmatch(src["commit"])):
        errors.append("source.commit is a commit's whole hash, in lower case")
    if src.get("tag") is not None and not (git and src.get("commit") and isinstance(src["tag"], str) and GIT_REF.fullmatch(src["tag"])):
        errors.append("source.tag is the tag a repository's pinned commit is fetched under: a tag's name, beside source.commit")
    if src.get("track") is not None and (not git or track_refused(src["track"], "source.track", GIT_RESOLVERS)):
        errors.append(track_refused(src["track"], "source.track", GIT_RESOLVERS)
                      or "source.track is how a repository's commit to pin is found: a source of another kind says source.version")
    return errors[0] if errors else ""


def source_format(src):
    """The least pack format a row's source needs for what it says of its
    downloads: 5 where it pins its download, declares downloads, carries
    keys, says its steps run with no network or keep it, names the tag a
    repository's commit is fetched under or how its commit is found, says
    what it asks a package manager for, carries files, or follows a
    tarball with steps; 1 otherwise."""
    if not isinstance(src, dict):
        return 1
    ck = src.get("checksum")
    new = (isinstance(ck, dict) and ck.get("from") == "pin") \
        or any(src.get(k) for k in ("fetch", "keyring", "online", "offline", "tag", "track", "lock", "files")) \
        or (src.get("kind") == "tarball" and src.get("then"))
    return HELD_FORMAT if new else 1


# ---- the three words ---------------------------------------------------------
# What an entry's downloads are held to, in one word a person reads on its
# card, worked out from the entry alone (held, below):
#   pinned     every download it makes is a pin, a publisher's signature
#              under a key it carries, or a git commit, and its steps run
#              with no network;
#   installer  the same for everything it declares, and it says its pinned
#              installer downloads the rest from its vendor (online); a
#              package another row's program installs is that installer's
#              too, with the sentence;
#   open       anything else: a download checked only against its own
#              origin or against nothing, a repository at a branch, steps
#              that run with the network and no declared reason.
HELD_WORDS = ("pinned", "installer", "open")
PINNED_SAID = ("every download it makes is held to a pin, a publisher's signature or a commit its entry carries, "
               "and its steps run with no network")


def _entry_source(doc):
    """(source, pack) for a toolchain row, an official pack's manifest (its
    recipe under `shipped`, or a coding agent's under agent.install) or a
    pack's manifest, raw or as the validator keeps it; None for an entry
    whose install its entry does not describe (a service, an agent with no
    recipe). A pack is fetched at the commit its record or the signed index
    pins, which is its source here; `pack` says the entry carries the keys
    its signed downloads are checked with."""
    if isinstance(doc.get("source"), dict):
        return doc["source"], isinstance(doc.get("pack"), dict)
    sh = doc.get("shipped")
    if isinstance(sh, dict) and isinstance(sh.get("source"), dict):
        return sh["source"], False
    if doc.get("agent") is not None and doc.get("tier") == "official":
        # A shipped coding agent: its recipe (agent.install) is its install.
        inst = doc["agent"].get("install") if isinstance(doc["agent"], dict) else None
        return (agent_source(inst), True) if isinstance(inst, dict) else None
    if doc.get("service") is not None:
        return None
    raw = isinstance(doc.get("install"), dict)
    inst = doc["install"] if raw else doc
    fetch, online = inst.get("fetch") or [], inst.get("online") or ""
    # What it declares cuts its steps: a download, or, from format 5, that
    # it downloads nothing (declares_none; the validator keeps that as
    # `offline`).
    cut = bool(fetch) or (declares_none(doc) if raw else bool(doc.get("offline")))
    return {"kind": "git", "commit": "the commit it is kept at", "fetch": fetch, "keyring": inst.get("keyring") or {},
            "online": online, "offline": cut and not online, "then": inst.get("steps") or [],
            "verify": inst.get("verify")}, True


# A coding agent's install recipe (agent.install, agents.install_checked)
# is an install like any entry's, read as one: what it declares (fetch,
# keyring, online) and the steps that run from it. One that says no steps
# (a vendor's installer fetched and handed to a shell, which no recipe may
# be: install_checked refuses it) declares nothing and is read as that,
# under a kind of its own.
PIPED = "piped"
PIPED_SAID = ("its vendor's installer is fetched and handed to a shell as it arrives, and it downloads the rest: "
              "nothing in its entry holds either")


def agent_source(inst):
    """A coding agent's install recipe as the source held() reads: a held
    recipe's downloads, keys and sentence with its steps, which run with no
    network unless it says online; one with no steps as PIPED."""
    if not isinstance(inst.get("steps"), list):
        return {"kind": PIPED}
    online = inst.get("online") if isinstance(inst.get("online"), str) else ""
    return {"kind": "command", "fetch": inst.get("fetch") if isinstance(inst.get("fetch"), list) else [],
            "keyring": inst.get("keyring") if isinstance(inst.get("keyring"), dict) else {},
            "online": online, "offline": not online.strip(), "run": inst["steps"]}


def agent_held(inst):
    """held_of for a coding agent's install recipe alone, as the controller
    holds one (its table's, or the catalog's newer one)."""
    return held_of({"tier": "official", "agent": {"install": inst}})


def declares_none(doc):
    """Whether a pack's manifest declares that its install downloads
    nothing: `"fetch": []` under install, from pack format 5. Its steps
    then run with no network, as those of one that declares downloads do.
    Before format 5 an empty list declared nothing, and still does."""
    inst = doc.get("install") if isinstance(doc, dict) else None
    return isinstance(inst, dict) and isinstance(inst.get("fetch"), list) and not inst["fetch"] and (of(doc) or 1) >= HELD_FORMAT


def held(doc):
    """(word, why): what a toolchain row's or a manifest's downloads are
    held to, one of HELD_WORDS, and the sentence that says why: for open,
    which part is held to nothing; for installer, the entry's own sentence."""
    got = _entry_source(doc) if isinstance(doc, dict) and doc else None
    # A deployed thing of AerieOS's installs nothing: what it runs is the
    # images its entry names.
    if got is None and isinstance(doc, dict) and doc.get("service") is not None and isinstance(doc.get("images"), dict):
        return images_held(list(doc["images"].values()))
    if got is None:
        return "open", "how it is installed is not in its entry"
    src, pack = got
    kind = src.get("kind")
    ck = src.get("checksum") if isinstance(src.get("checksum"), dict) else {}
    how = ck.get("from")
    # Its own source.
    if kind == PIPED:
        return "open", PIPED_SAID
    if kind == "git":
        if not src.get("commit"):
            return "open", "its repository is fetched at a branch, with no commit: what arrives is whatever the branch holds that day"
    elif kind in ("tarball", "script"):
        signed = ck.get("signed") if isinstance(ck.get("signed"), dict) else {}
        if how == "pin":
            if pin_refused(ck):
                return "open", pin_refused(ck)
        elif how == "none":
            return "open", f"its download is checked against nothing: {ck.get('why') or 'its publisher states no checksum'}"
        elif not how:
            return "open", "its entry says nothing to check its download against"
        elif not ((how == "signature" and ck.get("sig") and ck.get("keys")) or (how == "file" and signed.get("sig") and signed.get("keys"))):
            return "open", (f"its download is checked against what its own origin says at the moment of the install ({how}), "
                            "not against a pin or a signature its entry carries")
    elif kind == "sdkmanager":
        # A package of another row's program: it has no download of its
        # own, and the program that installs it (the row it requires)
        # downloads it by itself. With the sentence that says so it is that
        # installer's; without one, nothing in its entry says what holds
        # what arrives.
        if not (isinstance(src.get("online"), str) and src["online"].strip()):
            return "open", "its own package manager downloads it, and nothing in its entry holds what arrives"
    elif kind != "command":
        return "open", "its own package manager downloads it, and nothing in its entry holds what arrives"
    # What it declares besides.
    fetch = src.get("fetch") if isinstance(src.get("fetch"), list) else []
    keyring = src.get("keyring") if isinstance(src.get("keyring"), dict) else {}
    for f in fetch:
        f = f if isinstance(f, dict) else {}
        signed = f.get("signed") if isinstance(f.get("signed"), dict) else {}
        if isinstance(f.get("sha256"), str) and SHA256.fullmatch(f["sha256"]):
            continue
        # A pack carries the key itself; a row AerieOS ships may name one
        # of the release's own (config/release-keys).
        if signed.get("sig") and signed.get("keys") and (not pack or signed["keys"] in keyring):
            continue
        return "open", f"{f.get('to') or 'a download it declares'} is held to nothing its entry carries: no sha256, and no signature under a key in it"
    # What runs, and whether it can fetch.
    online = src.get("online")
    if isinstance(online, str) and online.strip():
        return "installer", " ".join(online.split())
    # A row whose own download is a pin or its publisher's signature (every
    # tarball and script that came this far) has its steps cut by that
    # alone; a repository or a command by what it declares, or by offline.
    runs = kind in ("script", "command") or any(src.get(k) for k in ("run", "then", "warm", "verify"))
    if runs and not (src.get("offline") or fetch or kind in ("tarball", "script")):
        return "open", "its install steps run with the network, and its entry does not say what they fetch"
    return "pinned", PINNED_SAID


def held_of(doc):
    """held(doc) as an API answers it: {word, why}."""
    word, why = held(doc)
    return {"word": word, "why": why}


def replaces_refused(theirs, shipped):
    """Why a recipe held to `theirs` may not take the place of a shipped
    one held to `shipped` (two of HELD_WORDS), or "": the catalog's newer
    recipe is taken only where it is held to as much as the one this build
    ships, pinned above installer above open, and one held to nothing takes
    no shipped recipe's place whatever that one is. A higher rev alone
    would let a recipe that fetches whatever its origin serves stand in
    the place of one that was pinned."""
    if theirs not in HELD_WORDS or theirs == "open":
        return "its downloads are held to nothing its entry carries, and such a recipe takes no shipped one's place"
    if HELD_WORDS.index(theirs) > (HELD_WORDS.index(shipped) if shipped in HELD_WORDS else len(HELD_WORDS)):
        return f"it is held to less than the shipped one: {theirs}, where the shipped one is {shipped}"
    return ""


def of(doc):
    """The format a manifest or an index entry says it needs: a whole
    number from 1, 1 when it says none, None when what it says is no number."""
    v = doc.get("format", 1) if isinstance(doc, dict) else 1
    return v if isinstance(v, int) and not isinstance(v, bool) and 1 <= v <= 9999 else None


def framework_of(doc):
    """The framework version a manifest or an index entry says it is written
    for, (X, Y): from `framework` ("2.1"), or its format and nought where it
    says none; None when what it says is no version."""
    fmt = of(doc)
    if fmt is None:
        return None
    v = doc.get("framework") if isinstance(doc, dict) else None
    if v is None:
        return (fmt, 0)
    if not isinstance(v, str):
        return None
    x, dot, y = v.partition(".")
    if not (dot and x.isdigit() and y.isdigit() and len(x) <= 4 and len(y) <= 4 and int(x) >= 1):
        return None
    return (int(x), int(y))


def said(version):
    """A version as it is written: 2.1."""
    return f"{version[0]}.{version[1]}"


def needs(doc, uses=()):
    """What is wrong with the framework version a manifest says, as a list
    of sentences, [] when nothing: a version that is none, one before its
    own format, or one before something it uses. `uses` is what the caller
    found in it, each (the version that brought it, what it is)."""
    fw = framework_of(doc)
    if fw is None:
        return ['framework is the catalog framework\'s version the manifest is written for, as "2.1"']
    if fw[0] < (of(doc) or 1):
        return [f'framework {said(fw)} is before the format the manifest says it needs ({of(doc)}): its first number is that format or a later one']
    # By the second number alone, which never resets: what 2.1 brought is in 3.1 and not in 3.0.
    late = [(v, what) for v, what in uses if v[1] > fw[1]]
    if late:
        v = max(v for v, _ in late)
        return [f'{", ".join(what for _, what in late)} {"is" if len(late) == 1 else "are"} catalog framework {said(v)}\'s: the manifest says "framework": "{said(v)}"']
    return []


def uses_of(doc):
    """What a manifest's top level uses that a second number brought, each
    (version, what it is): the keys any kind of entry can carry."""
    out = []
    if isinstance(doc, dict):
        if doc.get("maker") is not None:
            out.append(((2, 1), "maker"))
        if doc.get("credits") is not None:
            out.append(((2, 1), "credits"))
    return out


def least(doc, uses=()):
    """The framework version a manifest written from a table says: the
    least that holds what it uses, as "2.1", or "" where its format alone
    says it (nothing a second number brought)."""
    y = max((v[1] for v, _ in [*uses_of(doc), *uses]), default=0)
    return f"{max(of(doc) or 1, max((v[0] for v, _ in [*uses_of(doc), *uses] if v[1] == y), default=1))}.{y}" if y else ""


def ahead(doc):
    """What this build leaves out of something written for a later version
    of the framework than it reads, in a sentence, or "": a later second
    number, which is what an entry it still takes can be ahead by."""
    fw = framework_of(doc)
    if fw is None or fw[1] <= MINOR:
        return ""
    return f"written for catalog framework {said(fw)}: this AerieOS reads {VERSION} and leaves out what was added after it"


def too_new(fmt, since=""):
    """Why this build does not take something of format `fmt`, or "" when
    it does. `since` is the first AerieOS that reads it, where the index
    says (its `formats`)."""
    if not isinstance(fmt, int) or fmt <= FORMAT:
        return ""
    need = f"AerieOS {since} or newer" if since else "a newer AerieOS than this one"
    return f"needs {need} (it is written in pack format {fmt}, and this AerieOS reads up to {FORMAT})"


# ---- the pins an index entry carries -------------------------------------------
# An entry of the signed index pins one manifest: the commit it is at, the
# sha256 of its archive there, and what the entry repeats of that manifest
# so an install knows it before it fetches anything (ENTRY_PIN). The entry's
# own fields are its newest pin, as they always were.
#
# A pack that moves to a newer format keeps serving the releases that read
# only the one before (the operator, 20 Nov): its older manifest is still
# there at its older commit, so nothing is copied, and the entry keeps that
# pin beside the newest under `older`, newest first:
#
#   {"name": ..., "url": ..., "path": ..., "tier": ..., "maker": ...,
#    "format": 6, "framework": "6.0", "commit": ..., "sha256": ...,
#    "older": [{"format": 5, "framework": "5.2", "commit": ..., "sha256": ...}]}
#
# A pin is whole: an older one says everything of ENTRY_PIN its manifest
# gave the entry when it was the newest, and takes nothing from the pins
# beside it. What is the entry's own (its name, where it is kept, its tier,
# who it is by, what it is about, whether it is withdrawn) is said once.
# One function answers the entry as a build takes it (pin_for), and every
# reader of an index goes through it (taken).
ENTRY_PIN = ("format", "framework", "commit", "sha256", "platforms", "label", "works_with", "held", "online", "install_rev", "shipped_rev")
ENTRY_OWN = ("name", "url", "path", "kind", "tier", "maker", "about", "topics", "added", "withdrawn", "agent", "older")
OLDER_MOST = 8
ENTRY_COMMIT = re.compile(r"^[0-9a-f]{40}$")


def older_refused(entry):
    """Why an entry's `older` is not its earlier pins as the format writes
    them, or "" (and "" for an entry with none): a list of up to OLDER_MOST,
    each with its format, its commit and its archive's sha256, the formats
    going down from below the entry's own with none twice, and nothing in
    a pin that is the entry's own to say. A key no build has met yet is
    left for the build that reads it."""
    older = entry.get("older") if isinstance(entry, dict) else None
    if older is None:
        return ""
    below = of(entry)
    if not isinstance(older, list) or not 1 <= len(older) <= OLDER_MOST or below is None:
        return f"older lists up to {OLDER_MOST} earlier pins of the entry, each {{format, commit, sha256}} with what the entry repeats of that manifest"
    for pin in older:
        fmt = pin.get("format") if isinstance(pin, dict) else None
        if not (isinstance(fmt, int) and not isinstance(fmt, bool) and fmt >= 1 and isinstance(pin.get("commit"), str)
                and ENTRY_COMMIT.fullmatch(pin["commit"]) and isinstance(pin.get("sha256"), str) and SHA256.fullmatch(pin["sha256"])):
            return "an older pin says its format (a whole number from 1), its commit (the full 40-character hash) and its archive's sha256"
        own = sorted(k for k in pin if k in ENTRY_OWN)
        if own:
            return f"an older pin says {', '.join(own)}, which the entry says once: a pin is {', '.join(ENTRY_PIN)}"
        if fmt >= below:
            return (f"older lists pack format {fmt} at or after {below}: earlier pins go from the newest format down, "
                    "each below the one before and all below the entry's own")
        below = fmt
    return ""


def pin_for(entry, reads=None):
    """An index entry as a build that reads pack format `reads` (this
    build's, when none is named) takes it: its newest pin where the build
    reads that format, else the newest of its older pins the build reads,
    laid over the entry's own fields, with no `older` left on it; None
    where no pin of it is readable. An `older` that is not the format's
    (older_refused) is read as none."""
    reads = FORMAT if reads is None else reads
    fmt = of(entry) if isinstance(entry, dict) else None
    if fmt is None:
        return None
    if fmt <= reads:
        return {k: v for k, v in entry.items() if k != "older"} if "older" in entry else entry
    pin = next((p for p in entry.get("older") or [] if p["format"] <= reads), None) if not older_refused(entry) else None
    return _at(entry, pin) if pin else None


def _at(entry, pin):
    """An entry at one of its older pins: the entry's own fields with the
    pin's in the place of its newest pin's, none of those carried over."""
    return {**{k: v for k, v in entry.items() if k not in ENTRY_PIN and k != "older"}, **{k: pin[k] for k in ENTRY_PIN if k in pin}}


def taken(index, reads=None):
    """An index's entries as a build takes them, in the index's order:
    each at the pin the build reads (pin_for). One with no readable pin is
    answered at the oldest pin it has, the one nearest the build: its format
    is past the build's, so every reader leaves it as it leaves any entry
    too new, and what its card says it needs is the least that would do."""
    out = []
    for e in (index.get("packs") if isinstance(index, dict) else None) or []:
        if not isinstance(e, dict) or of(e) is None:
            continue
        got = pin_for(e, reads)
        if got is None:
            last = e["older"][-1] if e.get("older") and not older_refused(e) else None
            got = _at(e, last) if last else {k: v for k, v in e.items() if k != "older"} if "older" in e else e
        out.append(got)
    return out


# What an entry says its downloads are held to, before anything of it is
# fetched: the word its manifest reads (held, above) under `held`, and for
# an installer the manifest's own sentence under `online`, both the pinned
# manifest's and so a pin's (ENTRY_PIN). The other two words' sentences are
# not the entry's to carry: pinned's is this build's own, and open's names
# a file or a step of the manifest, which a person reads once the entry is
# looked at or kept.
OFFER_INSTALLER = "its pinned installer downloads the rest from its vendor"
OFFER_OPEN = "a download or a step of it is held to nothing its entry carries"


def held_entry(held):
    """What an index entry says of a manifest whose downloads read `held`
    ({word, why} as held_of answers, or held's pair): {"held": the word},
    and {"online": the sentence} with it for an installer. What the tools
    write into an entry, and what the catalog's check holds an entry's to."""
    pair = (held.get("word"), held.get("why")) if isinstance(held, dict) else held
    word, why = pair if isinstance(pair, (tuple, list)) and len(pair) == 2 else (None, None)
    if word not in HELD_WORDS:
        return {}
    return {"held": word, **({"online": " ".join(str(why).split())[:ONLINE_MAX]} if word == "installer" and why else {})}


def held_offer(entry):
    """{word, why} for an entry not kept here yet, from what it says
    (held_entry), or None for one that says no word: the shape a kept
    pack's and a kept app's `held` has. An app's and a service's downloads
    are the images they run."""
    word = entry.get("held") if isinstance(entry, dict) else None
    if word not in HELD_WORDS:
        return None
    if word == "pinned":
        return {"word": word, "why": IMAGES_SAID if entry.get("kind") in ("app", "service") else PINNED_SAID}
    if word == "installer":
        return {"word": word, "why": online_checked(entry.get("online"))[0] or OFFER_INSTALLER}
    return {"word": word, "why": OFFER_OPEN}
