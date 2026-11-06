"""Behind `aerie changelog` (cmd_changelog in bb): this project's CHANGELOG.md
as dashboard/changelog.py reads it, the same module the notebook's
Changelog view and a version bump use.

Arguments: version.py's path, the project, then the words (--for DIR and
the verb). BB_WORKSPACE says where the projects are, DASHBOARD_STATE
where the dashboard's files are, and BB_VERSION_TREE names a worktree
when the question is asked from one.
"""
import os
import sys

import dash

_here = dash.beside(sys.argv[1])
version = dash.load("version", _here)
statefile = dash.statefile(_here)
changelog = dash.load("changelog", _here)
_state = os.environ.get("DASHBOARD_STATE", "/config")
# The tracker, for what a release owes the changelog (R217): which bugs fixed
# since the last release it carried, and the answer a bug's notes keep.
bugs = dash.load("bugs", _here)
bugs.configure(write_json=statefile.write_json, state=_state)
version.configure(workspace=os.environ.get("BB_WORKSPACE", "/workspace"),
                  state=_state, write_json=lambda *a: None, bugs_mod=bugs, changelog_mod=changelog)
releasegaps = dash.load("releasegaps", _here)
releasegaps.configure(version_mod=version, bugs_mod=bugs, changelog_mod=changelog)

proj, argv = sys.argv[2], sys.argv[3:]
comp = ""
if "--for" in argv:
    i = argv.index("--for")
    if i + 1 >= len(argv):
        print("--for needs a component directory", file=sys.stderr)
        raise SystemExit(1)
    comp = argv[i + 1]
    argv = argv[:i] + argv[i + 2:]

d = version._sub(proj, comp)
if d is None:
    print(f"no such component here: {comp}", file=sys.stderr)
    raise SystemExit(1)

# --cat NAME files the entry under a category, the `### Name` subsections a
# reader knows from Keep a Changelog. A new one lands at the END: where a
# category sits in what a reader meets is an arrangement, and arrangements
# are the operator's, on the Changelog editor.
cat, moving = "", False
if "--cat" in argv:
    i = argv.index("--cat")
    if i + 1 >= len(argv):
        print("--cat needs a category name", file=sys.stderr)
        raise SystemExit(1)
    cat, moving = argv[i + 1], True
    argv = argv[:i] + argv[i + 2:]

# A line corrected rather than changed. An edit normally names the commit
# that made the change, which is the point of the stamp; a pass over the
# wording, or a move between categories, is not a change and must not claim
# one. 22 entries all naming the commit that reworded them is a record of
# nothing.
stamp = True
if "--no-stamp" in argv:
    stamp = False
    argv = [a for a in argv if a != "--no-stamp"]

# --bug N says which bug a Fixed line is about: kept in the bug's notes, so
# the release check (aerie changelog missing) and a stable release's
# gathering know the line answers it.
bug_n = None
if "--bug" in argv:
    i = argv.index("--bug")
    if i + 1 >= len(argv):
        print("--bug needs the bug's number", file=sys.stderr)
        raise SystemExit(1)
    bug_n, argv = argv[i + 1], argv[:i] + argv[i + 2:]


def _bug_of(word):
    import ids
    n, why = ids.parse("bugs", word)
    if n is None:
        print(why or f"not a bug's number: {word}", file=sys.stderr)
        raise SystemExit(1)
    with bugs._lock:
        b = next((x for x in (bugs.load()["projects"].get(proj) or []) if x.get("id") == n), None)
    if b is None:
        print(f"no bug {ids.label('bugs', n)} here", file=sys.stderr)
        raise SystemExit(1)
    return b


def _answer(b, words):
    """The bug's notes gain the changelog's answer, stamped as aerie bug note stamps."""
    import time
    body = (b.get("notes", "") + f"\n\n[{time.strftime('%d %b', time.localtime())}] Changelog: {words}").strip()
    r = bugs.edit(proj, b["id"], by="claude", act="noted", notes=body)
    if r.get("error"):
        print(r["error"], file=sys.stderr)
        raise SystemExit(1)


if argv and argv[0] == "add":
    if len(argv) < 2 or not argv[1].strip():
        print('aerie changelog add "what changed, for the person using it" '
              '--cat NAME [--for DIR]\n' + changelog.rules(), file=sys.stderr)
        raise SystemExit(1)
    # A category is asked for rather than assumed. Filed under none, an entry
    # lands in a heap above the headings, and a changelog that is mostly heap
    # is what this repository's own had become: the refusal is where a session
    # learns which categories there are, since nothing else ever told it.
    if not cat.strip():
        print(changelog.rules(), file=sys.stderr)
        raise SystemExit(1)
    if not changelog.standard(changelog.canonical(cat)):
        print(f"filed under {cat!r}, which is this space's own category rather than one "
              "of the six; kept as typed", file=sys.stderr)
    # Stamped with HEAD: the instruction in the template is to log after
    # committing, so the sha names the commit the entry describes.
    sha = version._git(proj, "rev-parse", "--short=7", "HEAD") or ""
    b = _bug_of(bug_n) if bug_n is not None else None
    r = changelog.add(d, argv[1], sha=sha, cat=cat)
    if r.get("error"):
        print(r["error"], file=sys.stderr)
        raise SystemExit(1)
    if b is not None:
        _answer(b, f"{changelog.canonical(cat) or cat} line: {argv[1]}")
    n = len(changelog.unreleased(d))
    print(f"logged{' (new ' + changelog.FILE + ')' if r.get('created') else ''}: "
          f"{n} unreleased entr{'y' if n == 1 else 'ies'} now waiting for a bump")
    # ...and that the file is now modified. An entry is stamped with the commit
    # it describes, so it is written AFTER that commit and lands in the next
    # one: every entry but a session's last gets swept up by the commit that
    # follows it, and the last one sits in a dirty tree that Pull, Switch and
    # Merge all refuse on (B162). Said rather than committed here, because the
    # wording belongs with whatever commit the author is making next.
    print(f"{changelog.FILE} is modified now: commit it with your next commit",
          file=sys.stderr)
    raise SystemExit(0)

if argv and argv[0] == "missing":
    # What the next release owes (R217): a bug fixed since the last release
    # that it carried, or may have, with no Fixed line and no answer. A
    # release is refused while this lists anything.
    since = argv[1] if len(argv) > 1 else ""
    g = releasegaps.gaps(proj, comp, since=since)
    if not g["since"]:
        print("no release here yet: nothing is owed")
        raise SystemExit(0)
    if not g["owed"]:
        print(f"nothing owed since {g['since']}: every bug fixed since it that it carried has a line or an answer")
        raise SystemExit(0)
    print(f"since {g['since']}, {len(g['owed'])} fixed bug(s) need a Fixed line or an answer:")
    for r in g["owed"]:
        print(f"  {r['label']}  {'carried' if r['carried'] == 'yes' else 'unsure'}: {r['why']}"
              + (f"  ({', '.join(r['commits'])})" if r["commits"] else ""))
        print(f"        {r['title']}")
    print('each: aerie changelog add "..." --cat Fixed --bug N, or aerie changelog skip N "why it needs none"')
    raise SystemExit(1)

if argv and argv[0] == "skip":
    if len(argv) < 3 or not " ".join(argv[2:]).strip():
        print('aerie changelog skip N "why"   a fixed bug that needs no Fixed line, and why: the last\n'
              "    release did not have it, or nobody using the product meets it", file=sys.stderr)
        raise SystemExit(1)
    b = _bug_of(argv[1])
    _answer(b, "no line: " + " ".join(argv[2:]))
    print(f"noted: {b.get('title', '')[:80]} needs no Fixed line")
    raise SystemExit(0)

if argv and argv[0] == "unreleased":
    rows = changelog.numbered(d)
    if not rows:
        print("nothing unreleased here")
    seen = None
    for n, text, shas, group in rows:
        if group != seen:
            seen = group
            print(f"  {group or '(no category)'}")
        print(f"{n:3d}  {text}" + (f"  ({', '.join(shas)})" if shas else ""))
    raise SystemExit(0)

if argv and argv[0] == "edit":
    words = argv[2] if len(argv) > 2 else None
    if len(argv) < 2 or (words is None and not moving) or (words is not None and not words.strip()):
        print('aerie changelog edit N "the line as it should read now" [--cat NAME]\n'
              "aerie changelog edit N --cat NAME        move it, leaving the words alone",
              file=sys.stderr)
        raise SystemExit(1)
    # Nothing is claimed for a move on its own: the entry says what it said.
    sha = ""
    if stamp and words is not None:
        sha = version._git(proj, "rev-parse", "--short=7", "HEAD") or ""
    r = changelog.edit(d, argv[1], words, sha=sha, cat=cat if moving else None)
    if r.get("error"):
        print(r["error"], file=sys.stderr)
        raise SystemExit(1)
    print(("reworded" if words is not None else "moved") + f" unreleased entry {r['n']}")
    raise SystemExit(0)

if argv and argv[0] == "merge":
    if len(argv) < 4 or not argv[-1].strip():
        print('aerie changelog merge N M [...] "the one line for all of them" '
              '[--for DIR]', file=sys.stderr)
        raise SystemExit(1)
    r = changelog.merge(d, argv[1:-1], argv[-1], cat=cat or None)
    if r.get("error"):
        print(r["error"], file=sys.stderr)
        raise SystemExit(1)
    print(f"merged into one entry; {r['entries']} unreleased now")
    raise SystemExit(0)

if argv and argv[0] == "split":
    if len(argv) < 2:
        print("aerie changelog split N [--for DIR]", file=sys.stderr)
        raise SystemExit(1)
    r = changelog.split(d, argv[1])
    if r.get("error"):
        print(r["error"], file=sys.stderr)
        raise SystemExit(1)
    print(f"split into one entry per commit; {r['entries']} unreleased now. "
          f"Reword them, or drop the one that stopped being true.")
    raise SystemExit(0)

if argv and argv[0] == "rm":
    if len(argv) < 2:
        print("aerie changelog rm N [--for DIR]", file=sys.stderr)
        raise SystemExit(1)
    r = changelog.remove(d, argv[1])
    if r.get("error"):
        print(r["error"], file=sys.stderr)
        raise SystemExit(1)
    print(f"dropped it; {r['entries']} unreleased now")
    raise SystemExit(0)

if argv:
    print("aerie changelog [--for DIR]         read it\n"
          'aerie changelog add "..." [--cat NAME]  log a user-facing change\n'
          "aerie changelog unreleased          the entries waiting for a bump, numbered\n"
          'aerie changelog edit N "..."        reword one of them; --cat NAME moves it,\n'
          "                                 and on its own moves it without rewording\n"
          "                                 (--no-stamp: a correction, not a change)\n"
          'aerie changelog merge N M "..."     one line for several, carrying their commits\n'
          "aerie changelog split N             back into one line per commit\n"
          "aerie changelog rm N                drop one that stopped being true\n"
          "aerie changelog missing [TAG]       the fixed bugs the last release (or TAG) carried with\n"
          "                                 no Fixed line: a release is refused while there are any\n"
          'aerie changelog skip N "why"        a fixed bug that needs no line, and why\n'
          "  add ... --bug N                  the Fixed line is about bug N\n"
          "\nA category is a `### Name` subsection. Which ones exist and what\n"
          "order they and their lines sit in is the operator's, on the\n"
          "Changelog editor beside the version.",
          file=sys.stderr)
    raise SystemExit(1)

text = changelog.read(d)
if text is None:
    print(f"no {changelog.FILE} here yet; the first "
          f"`aerie changelog add` creates it")
    raise SystemExit(0)
print(text, end="")
