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
       "downloads nothing (an empty install.fetch), which cuts its steps from the network",
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
PIN_KEYS = frozenset(("from", "version", "sha256"))
PIN_PLATFORMS = 8


def pin_refused(ck):
    """Why a row's source.checksum is not a pin as the format writes one,
    or "": {"from": "pin", "version": the version the file is (left out for
    a download with none in its address), "sha256": the digest of the exact
    file, 64 hex digits, or one per platform}."""
    if not isinstance(ck, dict) or ck.get("from") != "pin":
        return "its checksum is no pin"
    if set(ck) - PIN_KEYS:
        return f"its pin names {', '.join(sorted(set(ck) - PIN_KEYS))}: a pin is from, version and sha256"
    v = ck.get("version")
    if v is not None and not (isinstance(v, str) and PIN_VERSION.fullmatch(v)):
        return "its pin's version is not a version: up to 64 of letters, digits, dot, dash, plus and underscore"
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
# it is kept as.
FETCH_MAX = 32
HTTPS = re.compile(r"^https://[A-Za-z0-9.-]{1,253}(:\d{1,5})?/[\x21-\x7e]{0,1900}$")
REL = re.compile(r"^(?!/)(?!.*(?:^|/)\.\.?(?:/|$))[A-Za-z0-9._/-]{1,200}$")
FETCH_KEYS = frozenset(("url", "sha256", "to", "platform", "signed"))
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
    `reserved` are file names an entry may not write over."""
    if not isinstance(raw, list) or len(raw) > FETCH_MAX:
        return [], [f"{what} lists up to {FETCH_MAX} downloads, each {{url, sha256, to}}"], set()
    clean, errors, new = [], [], set()
    for i, f in enumerate(raw):
        said = (f"{what} {i + 1} is {{url, sha256, to}}: an https address, the sha256 of what it answers (64 hex digits), "
                "and the file inside the pack it is kept as, each named once; from pack format 5 it may name the platform it is for, "
                "and signed ({sig, keys}: its publisher's signature and the keys it is checked with) in the sha256's place")
        if not isinstance(f, dict) or set(f) - FETCH_KEYS:
            errors.append(said)
            continue
        url, to, plat = f.get("url"), f.get("to"), f.get("platform")
        sha, signed = f.get("sha256") or None, f.get("signed")
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
        row = {"url": url, "sha256": sha or "", "to": to}
        if plat:
            row["platform"] = plat
            new.add("platform")
        if signed:
            row["signed"] = {"sig": signed["sig"], "keys": signed["keys"]}
            new.add("signed")
        clean.append(row)
    return clean, errors, new


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
    downloads that machine fetches alone."""
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
        out.append({"to": str(f.get("to") or "")[:200], "url": str(f["url"])[:2000], "held": how, "sha256": sha,
                    "keys": str(signed.get("keys") or "")[:64] if how == "signed" else "",
                    "sig": str(signed.get("sig") or "")[:2000] if how == "signed" else "", "platform": plat[:40]})
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


def source_refused(src):
    """Why a row's source says something of its downloads that the format
    does not write, or "": its pin, its declared downloads, the keys it
    carries, and whether its steps keep the network."""
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
    return errors[0] if errors else ""


def source_format(src):
    """The least pack format a row's source needs for what it says of its
    downloads: 5 where it pins its download, declares downloads, carries
    keys, says its steps run with no network or keep it, or follows a
    tarball with steps; 1 otherwise."""
    if not isinstance(src, dict):
        return 1
    ck = src.get("checksum")
    new = (isinstance(ck, dict) and ck.get("from") == "pin") or any(src.get(k) for k in ("fetch", "keyring", "online", "offline")) \
        or (src.get("kind") == "tarball" and src.get("then"))
    return HELD_FORMAT if new else 1


# ---- the three words ---------------------------------------------------------
# What an entry's downloads are held to, in one word a person reads on its
# card, worked out from the entry alone (held, below):
#   pinned     every download it makes is a pin, a publisher's signature
#              under a key it carries, or a git commit, and its steps run
#              with no network;
#   installer  the same for everything it declares, and it says its pinned
#              installer downloads the rest from its vendor (online);
#   open       anything else: a download checked only against its own
#              origin or against nothing, a repository at a branch, steps
#              that run with the network and no declared reason.
HELD_WORDS = ("pinned", "installer", "open")
PINNED_SAID = ("every download it makes is held to a pin, a publisher's signature or a commit its entry carries, "
               "and its steps run with no network")


def _entry_source(doc):
    """(source, pack) for a toolchain row, an official pack's manifest (its
    recipe under `shipped`) or a pack's manifest, raw or as the validator
    keeps it; None for an entry whose install its entry does not describe
    (a shipped agent, a service). A pack is fetched at the commit its
    record or the signed index pins, which is its source here."""
    if isinstance(doc.get("source"), dict):
        return doc["source"], isinstance(doc.get("pack"), dict)
    sh = doc.get("shipped")
    if isinstance(sh, dict) and isinstance(sh.get("source"), dict):
        return sh["source"], False
    if doc.get("service") is not None or (doc.get("agent") is not None and doc.get("tier") == "official"):
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
    if got is None:
        return "open", "how it is installed is not in its entry"
    src, pack = got
    kind = src.get("kind")
    ck = src.get("checksum") if isinstance(src.get("checksum"), dict) else {}
    how = ck.get("from")
    # Its own source.
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
