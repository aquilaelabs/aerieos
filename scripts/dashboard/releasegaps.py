"""What a release's changelog still owes: the bugs fixed since the last
release that the last release carried, with no Fixed line said for them.

A published release is a release whatever its tag calls it (vX.Y.Z,
vX.Y.Z-dev.N, vX.Y.Z-rc.2): somebody running it met its bugs, so a fix to one
of them is a Fixed line in the next release's notes. A fix to something no
release carried is not, since nobody upgrading met it. This module answers
which is which from what every space already keeps: the tracker's stamps (the
version a bug was seen in and fixed in, each with its commit) and git.

A bug is carried by the last release when:

  - it was seen in a build of that release's commit or one before it; or
  - a commit since the release that names the bug, or the commit it was closed
    on, takes out a line the release's own copy of that file holds.

It is not when every file its fix touched is a test's or CI's (nobody using
the product meets those), or when the code its fix changed came after the
release. Anything else is unsure, and the person or session cutting the
release says which: a Fixed line, or why there is none.

A bug is answered when a changelog line names one of its fix commits, or when
its notes carry a line beginning `Changelog:` (written by `aerie changelog
add --bug` and `aerie changelog skip`).

Path-pure apart from git, which is asked through version._git.
"""
import os
import re
import subprocess
import threading

version = None
bugs = None
changelog = None


def configure(*, version_mod, bugs_mod, changelog_mod):
    globals().update(version=version_mod, bugs=bugs_mod, changelog=changelog_mod)


# A release tag: vX.Y.Z, or vX.Y.Z-LABEL[.N] for a pre-release of any name.
TAG = re.compile(r"^v(\d+)\.(\d+)\.(\d+)(?:-([A-Za-z][0-9A-Za-z]*)(?:\.(\d+))?)?$")
# The commit inside a stamp: 0.9.0-dev.4837+83dc447.dirty
_SHA = re.compile(r"\+([0-9a-f]{7,40})(\.dirty)?")
# A line in a bug's notes that answers the changelog's question.
ANSWER = re.compile(r"(?:^|\n)(?:\[[^\]\n]*\]\s*)?Changelog:\s*(.+)")
# Paths nobody using the product meets: a fix touching only these is no line.
_DEV_ONLY = re.compile(r"(^|/)(tests?|unit|spec|specs|__tests__|lab|\.github|\.gitlab|\.forgejo|\.gitea)(/|$)"
                       r"|(^|/)[^/]*(_test|\.test|\.spec)\.[A-Za-z]+$|(^|/)test_[^/]*$")


def _git(project, *args):
    return version._git(project, *args, timeout=30)


def _yes(project, *args):
    """Whether a git question answers yes (exit 0). Asked directly: _git tries
    a failed read again after a pause, and a no here is an answer, not a
    failure."""
    try:
        return subprocess.run(["git", "-C", str(version.root(project)), *args], capture_output=True,
                              timeout=30, check=False, env={**os.environ, "GIT_OPTIONAL_LOCKS": "0"}).returncode == 0
    except (OSError, subprocess.SubprocessError):
        return False


# What git said about history, kept for the length of one walk over the
# tracker: a tracker holds hundreds of fixed bugs, and asking git about each
# (does this commit resolve, is it ours, was it before the tag, which commits
# name the bug) was several processes a bug, minutes in all on a tree that
# answers slowly. One walk asks each question once and reads the answers.
_walk = threading.local()


class _together:
    """One walk: while it is open, a read of history is asked once. `memo`
    is a walk's own answers handed back in, for work it left for later."""
    def __init__(self, memo=None):
        self.memo = {} if memo is None else memo

    def __enter__(self):
        self.outer = getattr(_walk, "memo", None)
        if self.outer is None:
            _walk.memo = self.memo
        return self

    def __exit__(self, *exc):
        if self.outer is None:
            _walk.memo = None


def _once(key, make):
    memo = getattr(_walk, "memo", None)
    if memo is None:
        return make()
    if key not in memo:
        memo[key] = make()
    return memo[key]


def _history(project, ref):
    """Every commit in `ref`'s history, by its first seven characters, or
    None when git would not say."""
    def make():
        out = _git(project, "rev-list", ref)
        if out is None:
            return None
        idx = {}
        for full in out.split():
            idx.setdefault(full[:7], []).append(full)
        return idx
    return _once(("history", project, ref), make)


def _since(project, tag):
    """The commits since `tag`, newest first, each (short hash, message)."""
    def make():
        out = _git(project, "log", "--format=%h%x00%B%x01", f"{tag}..HEAD") or ""
        rows = []
        for rec in out.split("\x01"):
            h, _, msg = rec.strip("\n").partition("\x00")
            if h:
                rows.append((h, msg))
        return rows
    return _once(("since", project, tag), make)


def tag_prefix(comp=""):
    return f"{comp}-v" if comp else "v"


def is_release_tag(name, comp=""):
    pre = tag_prefix(comp)
    return name.startswith(pre) and bool(TAG.match("v" + name[len(pre):]))


def _nearest(project, tags):
    """Of `tags` (newest made first), the one nearest HEAD by commits: two
    made in the same second sort either way by date, and the last release is
    the one the history last passed."""
    best, at = "", None
    for t in tags[:30]:
        n = _git(project, "rev-list", "--count", f"{t}..HEAD")
        n = int(n) if (n or "").isdigit() else None
        # On one commit, the higher version is the later release (an rc,
        # then the stable it became).
        if n is not None and (at is None or n < at or (n == at and _vkey(t) > _vkey(best))):
            best, at = t, n
    return best


def _vkey(tag):
    m = TAG.match("v" + tag.rpartition("v")[2]) if tag else None
    if not m:
        return (-1,)
    a, b, c, label, num = m.groups()
    return (int(a), int(b), int(c), 0 if label else 1, label or "", int(num or 0))


def last_release(project, comp=""):
    """The newest release tag in HEAD's history, of any name, or ""."""
    out = _git(project, "tag", "--merged", "HEAD", "--list", f"{tag_prefix(comp)}*", "--sort=-creatordate") or ""
    return _nearest(project, [t for t in out.split() if is_release_tag(t, comp)])


def _stamp_sha(stamp):
    m = _SHA.search(stamp or "")
    return (m.group(1), bool(m.group(2))) if m else ("", False)


def _at_or_before(project, sha, tag):
    """Whether the commit `sha` (seven characters of it or more) is in
    `tag`'s history."""
    if not sha:
        return False
    idx = _history(project, tag)
    if idx is None or len(sha) < 7:
        return _yes(project, "merge-base", "--is-ancestor", sha, tag)
    return any(full.startswith(sha) for full in idx.get(sha[:7], ()))


def _ours(project, sha):
    """A stamp's commit that this branch's history holds: one a rewrite left
    on no branch still resolves, and is in no tag's history either, which read
    as after every release (B700)."""
    return bool(sha) and _at_or_before(project, sha, "HEAD")


def _closed_after(project, bug, tag, tag_time):
    sha, dirty = _stamp_sha(bug.get("fixed_in"))
    if _ours(project, sha):
        if not _at_or_before(project, sha, tag):
            return True
        # Closed with the fix not yet committed, on the release's own commit:
        # the fix landed after it.
        tagged = _once(("short", project, tag),
                       lambda: _git(project, "rev-parse", "--short=7", f"{tag}^{{commit}}") or "")
        return dirty and tagged and (sha.startswith(tagged) or tagged.startswith(sha))
    return int(bug.get("closed_at") or 0) > tag_time


def fix_commits(project, bug, tag):
    """The commits since `tag` that fixed `bug`: the ones whose message names
    it, and the one it was closed on when that came after the tag."""
    names = re.compile(re.escape(_label(bug)) + r"([^0-9]|$)", re.M)
    shas = [h for h, msg in _since(project, tag) if names.search(msg)]
    sha, dirty = _stamp_sha(bug.get("fixed_in"))
    if not dirty and _ours(project, sha) and not _at_or_before(project, sha, tag):
        short = _git(project, "rev-parse", "--short=7", sha) or sha[:7]
        if not any(s.startswith(short) or short.startswith(s) for s in shas):
            shas.append(short)
    return shas


def _label(bug):
    try:
        import ids  # noqa: PLC0415  (beside this file)
        return ids.label("bugs", bug.get("id"))
    except Exception:  # noqa: BLE001
        return f"B{bug.get('id')}"


def carried(project, bug, tag, shas=None):
    """("yes" | "no" | "unsure", why): whether the release `tag` had `bug`."""
    shas = fix_commits(project, bug, tag) if shas is None else shas
    if shas and all(_DEV_ONLY.search(p) for p in _files(project, shas)):
        return "no", "its fix touched only tests and CI"
    seen, _ = _stamp_sha(bug.get("seen_in"))
    if _ours(project, seen) and _at_or_before(project, seen, tag):
        return "yes", f"seen in {bug.get('seen_in')}, a build {tag} carries"
    if not shas:
        return "unsure", "no commit since the release names it"
    files, touched_old = set(), False
    for c in shas:
        diff = _git(project, "show", "--format=", "-U0", "--no-color", "--no-renames", c) or ""
        path = ""
        for ln in diff.splitlines():
            if ln.startswith("--- "):
                continue
            if ln.startswith("+++ "):
                path = ln[6:] if ln.startswith("+++ b/") else ""
                if path:
                    files.add(path)
                continue
            if not path or _DEV_ONLY.search(path):
                continue
            if ln.startswith("-"):
                gone = ln[1:].strip()
                if len(gone) < 12:
                    continue
                old = _old(project, tag, path)
                if old is not None:
                    touched_old = True
                    if gone in old:
                        return "yes", f"{c} changes code {tag} has ({path})"
        # A file the fix changed with additions only, there at the release.
        for p in files:
            if not _DEV_ONLY.search(p) and _old(project, tag, p) is not None:
                touched_old = True
    if files and all(_DEV_ONLY.search(p) for p in files):
        return "no", "its fix touched only tests and CI"
    if not touched_old:
        return "no", f"the code its fix changed came after {tag}"
    return "unsure", f"its fix adds to files {tag} has, and changes none of their lines"


def _files(project, shas):
    out = set()
    for c in shas:
        out |= set((_git(project, "show", "--format=", "--name-only", "--no-renames", c) or "").split())
    return out or {""}


_old_cache = {}


def _old(project, tag, path):
    k = (project, tag, path)
    if k not in _old_cache:
        _old_cache[k] = _git(project, "show", f"{tag}:{path}") if _yes(project, "cat-file", "-e", f"{tag}:{path}") else None
        if len(_old_cache) > 400:
            _old_cache.pop(next(iter(_old_cache)))
    return _old_cache[k]


def answer_of(bug):
    """What the bug's notes say for the changelog, or ""."""
    said = ANSWER.findall(bug.get("notes") or "")
    return said[-1].strip() if said else ""


def _named(where, shas):
    """Whether a changelog line names one of `shas`."""
    def make():
        text = changelog.read(where) or ""
        return {s for sec in changelog.sections(text) for e in sec["entries"] for s in e["shas"]}
    named = _once(("named", str(where)), make)
    return any(s.startswith(n) or n.startswith(s) for s in shas for n in named if len(n) >= 7)


def gaps(project, comp="", since=""):
    """{since, owed: [{id, label, title, carried, why, commits}]}: the bugs
    fixed since the last release (or the tag `since`) that it carried, or may
    have, with no Fixed line and no answer. {since: ""} for a tree with no
    release yet."""
    with _together():
        return _gaps(project, comp, since)


def _gaps(project, comp, since):
    tag = since or last_release(project, comp)
    if not tag or bugs is None:
        return {"since": tag, "owed": []}
    tag_time = int(_git(project, "log", "-1", "--format=%ct", tag) or 0)
    where = version._sub(project, comp)
    rows = []
    with bugs._lock:
        listed = list((bugs.load()["projects"].get(project) or []))
    for b in listed:
        if b.get("status") != "fixed" or answer_of(b):
            continue
        if not _closed_after(project, b, tag, tag_time):
            continue
        shas = fix_commits(project, b, tag)
        if shas and where is not None and _named(where, shas):
            continue
        how, why = carried(project, b, tag, shas)
        if how == "no":
            continue
        rows.append({"id": b.get("id"), "label": _label(b), "title": b.get("title", ""),
                     "carried": how, "why": why, "commits": shas})
    return {"since": tag, "owed": rows}


def refusal(g, limit=8):
    """The sentence a release is refused with while `g` owes lines, or ""."""
    owed = g.get("owed") or []
    if not owed:
        return ""
    shown = "; ".join(f"{r['label']} ({'carried' if r['carried'] == 'yes' else 'unsure'}: {r['why']}) {r['title']}"
                      for r in owed[:limit])
    more = f"; and {len(owed) - limit} more (aerie changelog missing)" if len(owed) > limit else ""
    return (f"{len(owed)} bug(s) fixed since {g['since']} that it carried, or may have, have no Fixed line: "
            f"{shown}{more}. Give each one: aerie changelog add \"...\" --cat Fixed --bug N, or say why "
            "it needs none: aerie changelog skip N \"why\"")


def last_stable(project, comp=""):
    """The newest stable release tag (no pre-release name) in HEAD's history, or ""."""
    pre = tag_prefix(comp)
    out = _git(project, "tag", "--merged", "HEAD", "--list", f"{pre}*", "--sort=-creatordate") or ""
    return _nearest(project, [t for t in out.split() if t.startswith(pre)
                              and (m := TAG.match("v" + t[len(pre):])) and not m.group(4)])


def stable_keep(project, comp=""):
    """keep(entry) for a stable release gathering its pre-releases: a Fixed
    line about a bug the last stable release did not have is left out, since
    nobody upgrading from it met that bug. A line no bug is found for stays.
    None with no stable release before (the first one keeps everything)."""
    prev = last_stable(project, comp)
    if not prev or bugs is None:
        return None
    prev_time = int(_git(project, "log", "-1", "--format=%ct", prev) or 0)
    with bugs._lock:
        listed = list((bugs.load()["projects"].get(project) or []))
    idx, memo = [], {}
    with _together(memo):
        for b in listed:
            if b.get("status") != "fixed" or not _closed_after(project, b, prev, prev_time):
                continue
            idx.append((b, fix_commits(project, b, prev), answer_of(b)))

    def keep(e):
        if e.get("cat") != "Fixed":
            return True
        hit = [(b, shas) for b, shas, ans in idx
               if any(s.startswith(n) or n.startswith(s) for s in shas for n in e["shas"] if len(n) >= 7)
               or (ans and e["text"] in ans)]
        if not hit:
            return True
        with _together(memo):
            return any(carried(project, b, prev, shas)[0] != "no" for b, shas in hit)
    return keep
