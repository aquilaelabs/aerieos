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

The number a manifest says is the one it needs. A key an earlier build
leaves out with the rest meaning what it meant (an extra: today a coding
agent's signin.flow, without which the agent signs in in its terminal)
does not move it, so a pack that gains one is still taken by every install
that took it before; docs/tool-packs.md lists the extras and who reads them.

unit/test_packformat.py holds the kept manifests of every number
(unit/packformat/N/) to this build, and `aerie lint` holds the ones a
release shipped unchanged, as it holds a shipped migration.

No imports from the rest of the dashboard: the catalog's own check loads
this beside toolpacks.py from a checkout of any release.
"""

# The number this build reads, and every one before it.
FORMAT = 2
# What each number added, for the docs and for a person reading a refusal.
FORMATS = {
    1: "tool packs (install steps, layout, verbs, config), Docker apps, and a coding agent whose hooks are one of the named shapes "
       "(grouped or flat, snake or camel): what 0.9.0's first releases read",
    2: "a coding agent that describes its own hook protocol (hooks.document, hooks.payload as paths, hooks.answers), "
       "prompt_fires, the start event, and the briefing and the allow list handed over by hook",
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


def too_new(fmt, since=""):
    """Why this build does not take something of format `fmt`, or "" when
    it does. `since` is the first AerieOS that reads it, where the index
    says (its `formats`)."""
    if not isinstance(fmt, int) or fmt <= FORMAT:
        return ""
    need = f"AerieOS {since} or newer" if since else "a newer AerieOS than this one"
    return f"needs {need} (it is written in pack format {fmt}, and this AerieOS reads up to {FORMAT})"
