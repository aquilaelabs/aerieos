"""The files a release must carry, checked on the forge when its CI ends
(R190 step 4, R206 step 6): a project lists them in `.release-files` at its
root, one name a line with @VER@ for the release's version, and a release
whose page is short of one is a red row on the bell naming the file and
why; one that has them all is said complete. The 0.9.0 dev release went out
with no APK and nothing said so until somebody looked (the operator, 30 Oct).

The list is read at the release's own tag, so a later commit changing it
does not change what an older release is held to. `*` matches as a shell
pattern does. A release is checked as the runs its tag started end (asked
of GitHub every TICK_S; while one is still going nothing is said, however
long it takes), where it was checked three hours after its tag whatever CI
was doing: too late for a build that had failed in ten minutes, too early
for one still running. Where the runs cannot be read (another git host, no
token, a tag that started none) the three hours stand (WAIT_S). Then every
TICK_S until it is whole or GIVE_UP_S has passed; a row stays until it is
whole or put away, or until a release that was read is deleted on the git
host, which ends its watch.

    configure(state=, workspace=, write_json_fn=)
    wanted(project, tag)   the names the release must carry, or []
    expect(project, tag)   a release's tag just pushed: check it as CI ends
    check(project)         check the expected releases that are due
    attention(projects)    the bell's rows
    start()                the loop
"""
import fnmatch
import hashlib
import json
import os
import subprocess
import threading
import time
from pathlib import Path

import cilogs
import forgerelease
import releasesign

STATE = Path("/config")
WORKSPACE = Path("/workspace")
write_json = None

MANIFEST = ".release-files"
WAIT_S = int(os.environ.get("BB_RELEASEFILES_WAIT", str(3 * 3600)))
GIVE_UP_S = 3 * 86400
# How often a release past GIVE_UP_S whose row still stands is asked after.
GONE_S = 86400
TICK_S = int(os.environ.get("BB_RELEASEFILES_TICK", "180"))
# The signed Android app is the controller's own to attach, within a look or
# two of the release being made: missing alone, and not failed, it is waited
# for this long after the runs end before it is said.
SIGN_GRACE_S = 1800
_lock = threading.Lock()
said = None      # said(project, tag, files, draft): a release that is complete, told to whoever the space is


def configure(*, state, workspace, write_json_fn, said_fn=None):
    globals().update(STATE=Path(state), WORKSPACE=Path(workspace), write_json=write_json_fn, said=said_fn)


def _file():
    return STATE / "release-files.json"


def _load():
    try:
        d = json.loads(_file().read_text())
        return d if isinstance(d, dict) else {}
    except (OSError, ValueError):
        return {}


def _save(d):
    if write_json:
        write_json(_file(), d)


def wanted(project, tag):
    """The names `tag`'s release must carry, from the list at that tag (at
    HEAD when the tag is not here yet), @VER@ filled in; [] with no list."""
    root = WORKSPACE / project
    text = ""
    for ref in (tag, "HEAD"):
        try:
            r = subprocess.run(["git", "-C", str(root), "show", f"{ref}:{MANIFEST}"],
                               capture_output=True, text=True, timeout=20, check=False)
        except (OSError, subprocess.SubprocessError):
            return []
        if r.returncode == 0:
            text = r.stdout
            break
    ver = tag.rsplit("-v", 1)[-1] if "-v" in tag and not tag.startswith("v") else tag.removeprefix("v")
    return [ln.strip().replace("@VER@", ver) for ln in text.splitlines()
            if ln.strip() and not ln.lstrip().startswith("#")][:100]


def expect(project, tag):
    """A release's tag was pushed: its files are checked once CI has had
    WAIT_S to build and attach them."""
    if not wanted(project, tag):
        return
    with _lock:
        d = _load()
        d.setdefault(project, {})[tag] = {"at": int(time.time())}
        _save(d)


def _sign_failed(project, tag):
    """Why the controller could not sign the release's APK, or ""."""
    f = ((releasesign._load().get(project) or {}).get("failed") or {}).get(tag)
    return str(f.get("why") or "") if isinstance(f, dict) else ""


def _why(project, tag, name, failed=()):
    """Why one file is not there, as far as the controller can tell;
    `failed` the tag's runs that ended any way but passed."""
    if name.endswith((".apk", ".apk.sha256")):
        if why := _sign_failed(project, tag):
            return f"the controller could not sign it: {why}"
        # Said to a person on the bell: where they look, not a session's verb.
        return "the controller has not signed it yet: the space's Signing view says why and looks again"
    if failed:
        return f"CI did not attach it: {failed[0]['name']} {failed[0]['how']} ({failed[0]['url']})"
    return "CI did not attach it: the release's run on the git host says why"


def runs(project, tag):
    """The runs `tag` started on GitHub: [{name, going, how, url}], [] when
    it started none, None where they cannot be read (another git host, no
    token, GitHub not answering). `how` is the run's end in a word a person
    reads: passed, failed, was canceled."""
    repo = cilogs.repo_of(project)
    token = cilogs._token(project) if repo else ""
    if not repo or not token:
        return None
    try:
        j = cilogs._get(f"/repos/{repo}/actions/runs?branch={tag}&per_page=50", token)
    except cilogs.Refused:
        return None
    out = []
    for r in (j.get("workflow_runs") or [])[:50] if isinstance(j, dict) else []:
        if str(r.get("head_branch") or "") != tag:
            continue
        going = str(r.get("status") or "completed") != "completed"
        end = str(r.get("conclusion") or "")
        how = "passed" if end in ("success", "neutral", "skipped") else "was canceled" if end.startswith("cancel") else "failed"
        out.append({"name": str(r.get("name") or "a run"), "going": going, "how": "" if going else how,
                    "url": str(r.get("html_url") or "")})
    return out


def _is_draft(project, tag):
    """Whether the release for `tag` is still a draft on GitHub; None where
    that cannot be read."""
    try:
        kind, _name, ctx = forgerelease._handle(project)
        if kind != "github" or not ctx:
            return None
        rel = forgerelease._req("GET", f"{forgerelease.API}/repos/{ctx[0]}/releases/tags/{tag}", ctx[1])
    except forgerelease.Refused:
        return None
    return rel.get("draft") is True if rel else None


def missing(project, tag):
    """(names missing, release url) of `tag` on the forge, or raises
    forgerelease.Refused."""
    kind, name, ctx = forgerelease._handle(project)
    url, have = forgerelease._files_on(kind, name, ctx, tag)
    return [w for w in wanted(project, tag) if not fnmatch.filter(have, w)], url


def check(project, now=None):
    """Check each expected release of the project that is due: one whose
    runs have all ended, or, where its runs cannot be read or it started
    none, one whose tag is WAIT_S old."""
    now = int(now or time.time())
    with _lock:
        recs = dict(_load().get(project) or {})
    for tag, rec in recs.items():
        if not isinstance(rec, dict) or rec.get("done"):
            continue
        age = now - int(rec.get("at") or 0)
        late = age > GIVE_UP_S
        # Past giving up, a release whose row still stands is looked at once
        # a day, only to learn that it has been taken away.
        if late and (not rec.get("url") or now - int(rec.get("asked") or rec.get("checked") or 0) < GONE_S):
            continue
        ci = None if late else runs(project, tag)
        going = [r for r in ci or [] if r["going"]]
        ended = bool(ci) and not going
        if going:
            # Still building: nothing is said of it, however long it has been.
            if rec.get("ci") != "running":
                rec["ci"] = "running"
                _keep(project, tag, rec)
            continue
        if not ended and not late and age < WAIT_S:
            continue
        failed = [r for r in ci or [] if r["how"] and r["how"] != "passed"]
        if ended:
            rec.update(ci="ended")
            rec.setdefault("ended", now)
        try:
            gone, url = missing(project, tag)
            if late:
                # Still there: its row stands as it was last read.
                rec.update(asked=now)
            elif (ended and gone and all(n.endswith((".apk", ".apk.sha256")) for n in gone)
                  and not _sign_failed(project, tag) and now - int(rec["ended"]) < SIGN_GRACE_S):
                # Whole but for the app the controller signs, which is on
                # its way: looked at again at the next tick, said only if it
                # does not come.
                rec.update(checked=now, url=url)
                _keep(project, tag, rec)
                continue
            else:
                rec.update(checked=now, url=url, gone=[{"name": n, "why": _why(project, tag, n, failed)} for n in gone],
                           error="")
        except forgerelease.NoRelease as e:
            if rec.get("url"):
                # Read before, and not there now: deleted on the git host,
                # on purpose. Not a release short of a file: its watch ends,
                # and its row with it (B780).
                rec.update(checked=now, done=now, deleted=True, gone=[], error="")
            elif not late:
                # The run that makes the release failed before it did.
                rec.update(checked=now, error=(f"its build made no release: {failed[0]['name']} {failed[0]['how']} "
                                               f"({failed[0]['url']})" if failed else str(e)))
        except forgerelease.Refused as e:
            if not late:
                rec.update(checked=now, error=str(e))
        if not rec.get("gone") and not rec.get("error") and not rec.get("done"):
            rec["done"] = now
            # Complete, and said so once (R206 step 6): how many files, and
            # whether it is out or waits for its owner to read it.
            n = len(wanted(project, tag))
            draft = _is_draft(project, tag)
            rec["complete"] = {"files": n, "draft": draft}
            if said:
                try:
                    said(project, tag, n, draft)
                except Exception as e:                              # noqa: BLE001 (saying it must not stop the check)
                    print(f"dashboard: release files {project}: {e}", flush=True)
        _keep(project, tag, rec)


def complete_words(label, tag, files, draft):
    """A complete release, in a sentence: how many files it carries, and
    whether it is out or waits for its owner."""
    return (f"{tag} of {label} is complete: every file it must carry is on it ({files})"
            + (", and it is a draft until its notes are read and it is published from the Artifacts view's Drafts"
               if draft else ", and it is published" if draft is False else ""))


def _keep(project, tag, rec):
    with _lock:
        d = _load()
        if tag in (d.get(project) or {}):
            d[project][tag] = rec
            _save(d)


def attention(projects):
    """The bell's rows, kind release-files: a release short of a file it
    must carry, red, each keyed on what is missing so a row put away comes
    back only when that changes."""
    out, whole = [], _load()
    for p in projects:
        for tag, rec in (whole.get(p) or {}).items():
            if not isinstance(rec, dict) or rec.get("done") or not (rec.get("gone") or rec.get("error")):
                continue
            gone = rec.get("gone") or []
            why = "; ".join(f"{g['name']}: {g['why']}" for g in gone) or f"it could not be read: {rec['error']}"
            h = hashlib.sha256(why.encode()).hexdigest()[:10]
            out.append({"kind": "release-files", "id": f"{p}|{tag}", "project": p, "tag": tag, "bad": True,
                        "files": [g["name"] for g in gone], "why": why, "url": rec.get("url") or "",
                        "at": int(rec.get("checked") or 0), "key": f"rfiles:{p}|{tag}@{h}"})
    return out


def start():
    """Every TICK_S, each project with a release expected. A daemon thread."""
    def loop():
        while True:
            time.sleep(TICK_S)
            for p in list(_load()):
                try:
                    check(p)
                except Exception as e:                              # noqa: BLE001 (a loop must not die)
                    print(f"dashboard: release files {p}: {e}", flush=True)
    threading.Thread(target=loop, name="releasefiles", daemon=True).start()
