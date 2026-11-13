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

unit/test_packformat.py holds the kept manifests of every number
(unit/packformat/N/) to this build, and `aerie lint` holds the ones a
release shipped unchanged, as it holds a shipped migration.

No imports from the rest of the dashboard: the catalog's own check loads
this beside toolpacks.py from a checkout of any release.
"""

# The number this build reads, and every one before it.
FORMAT = 3
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
