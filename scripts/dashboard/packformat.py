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
# and as a person reads it (the operator, 12 Nov: Built by Aerie, Verified
# and Vetted, in place of official and vetted, which did not say who made
# what):
#   official  one of AerieOS's own shipped rows, as a pack   Built by Aerie
#   aerie     a pack AerieOS's maintainers wrote             Built by Aerie
#   verified  a verified vendor's own pack, a shorter list   Verified
#   vetted    anybody's pack the maintainers reviewed        Vetted
# The words in a manifest and an index are stored ones and stay; a word this
# build has not met is read as vetted, the least any signed entry is, which
# is how a release from before `aerie` and `verified` reads them too.
TIERS = ("official", "aerie", "verified", "vetted")
TIER_WORDS = {"official": "Built by Aerie", "aerie": "Built by Aerie", "verified": "Verified", "vetted": "Vetted"}


def tier_of(word):
    """A signed entry's tier as this build keeps it."""
    return word if word in TIERS else "vetted"


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
