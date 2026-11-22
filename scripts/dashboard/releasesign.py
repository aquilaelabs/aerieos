"""A release's Android APK signed by AerieOS with the project's own
sideload key, not in CI (R106, the operator 22 Oct: four keystore secrets
set by hand on GitHub failed three ways, and one put a password in a public
log).

The project's workflow builds an UNSIGNED release APK and hands it over as a
workflow artifact named `bb-release-apk-TAG` (kept a few days, never on the
release). The controller, which made the release, watches for that artifact:
it fetches it with the project's GitHub token, hands each APK in it to a
sign-key job on the project's node, which signs it as `aerie sign` does
(signing.sign_release: zipalign, apksigner with the proof of a rotation,
verify, the certificate checked against the kept key) with the node's own
tools, and attaches what comes back to the release under its name less
`-unsigned`, with its sha256 file and a line in the notes giving the key and
its certificate's SHA-256 fingerprint. No keystore, alias or password is
ever a GitHub secret, and the key reaches only that job on that node.

The run that hands the APK over may be the one that makes the release, as
its last job (R206 step 1): the artifact is there long before the release
is, and the run is not over until the release has every file. So a run
still going is read too, its APK left alone until its release exists
(asked at every look, never a failure), and signed within one look of it.
A run that ended is read only when it passed.

Only the release's own run is signed from (the audit of 20 Nov: any run of
the repository that wrote an artifact of that name had its APK signed with
the project's key, a pull request's from a fork among them, and a later run
for a released tag replaced the published file). A run is a tag's own when
the tag itself started it (its push, or its release), it ran on that tag and
on the commit the tag names on GitHub, it is a run of a workflow in the
project's tree that hands an APK over, and its commit came from the
repository and not a fork (_own). And a release that carries its signed APK
is signed once: a later run for its tag is left alone until a person asks
for that tag again (check's `again`, aerie sign release --again TAG, the
owner's answer whatever the dial). Each run left alone is a line of what the
look says, with the reason.

A signed APK changes what the release carries, and a release whose files
are listed and signed (AerieOS's own SHA256SUMS, R199) can have that list
made only once the APK is on it. So after an attach the controller starts
the workflows in the project's tree that make it: each one that can be
started by hand and names `bb-release-seal-` outside a comment (its
concurrency group, in AerieOS's seal-release.yml), with the tag as its
`tag` input, on the tag's ref (sealing, _seal). A project with no such
workflow is left as it was and nothing is said. One that could not be
started is said on the look's row and on the bell, with what a person does
instead: start it by hand from the repository's Actions page, from the tag.
GitHub starts a workflow, by hand or asked, only when the default branch
carries it with its by-hand trigger (v0.9.0-dev.6049's seal was answered
404 for that), so a release whose sealing workflow is not there is refused
before its tag (unstartable, asked by version.verb), and a start refused for
it says so in place of the host's bare 404.

What would stop a release's signing is said on the bell before the release
(attention(): no sideload key, an app mapped to none of several, the
project's node offline or without the jdk and build-tools), and a signing
that failed after one is said there too, red,
until it succeeds or is put away. The Signing view names which key signs
the releases (status()).

    configure(state=, workspace=, write_json_fn=, projects=, dispatch=)
    wants(project)        whether its workflows hand over an unsigned APK
    handing(project)      which workflow files' runs can: the uploader, its callers
    sealing(project)      which workflow files are started once an APK is attached
    unstartable(project)  why GitHub would refuse to start them, or ""
    readiness(project)    {wanted, packages, keys, why}
    status(project)       readiness and the newest results, for the view
    expect(project, tag)  a release just made: look for its APK soon
    check(project, force, again)  look now; sign and attach what is waiting
    attention(projects)   the bell's rows
    start()               the loop

GitHub only: a Gitea or GitLab workflow's artifacts are asked for another
way, and nothing here asks them.
"""
import base64
import calendar
import hashlib
import json
import os
import re
import shutil
import tempfile
import threading
import time
import urllib.error
import urllib.parse
import urllib.request
import zipfile
from pathlib import Path

import cilogs
import forgerelease
import signing

STATE = Path("/config")
WORKSPACE = Path("/workspace")
write_json = None
projects_fn = None
# Starts a workflow on the project's forge with its token: (project, the
# workflow's file name, the ref, {input: value}) -> (payload, status), the
# request `aerie forge run dispatch` and aerie version rehearse make
# (forgeaccess.dispatch, handed over by the server).
dispatch_fn = None

# The artifact's name, a tag after it: what a workflow writes to be signed.
MARK = "bb-release-apk-"
# What a workflow that signs a release's list of files names, a tag after
# it (its concurrency group): started once that release's APK is attached.
SEAL = "bb-release-seal-"
BY_HAND = re.compile(r"^\s*workflow_dispatch\s*:", re.M)
TAG = re.compile(r"[A-Za-z0-9][A-Za-z0-9._+-]{0,79}")
# What starts a release's own run: the push of its tag, or its release
# published (a workflow `on: release`). Neither can be started from a fork,
# and a run by hand, a pull request's and a schedule's are nobody's release.
EVENTS = ("push", "release")
# A workflow called as a job of another: `uses: ./.github/workflows/NAME`.
CALLS = re.compile(r"""^\s*(?:-\s*)?uses:\s*["']?\./(\.github/workflows/[A-Za-z0-9._-]+\.ya?ml)\b""", re.M)
APK = re.compile(r"[A-Za-z0-9][A-Za-z0-9._+-]{0,150}\.apk")
# How long an expected release is looked for every few minutes, and how
# often otherwise: the artifact is kept three days, so a run older than that
# has nothing left to fetch.
EXPECT_S = 12 * 3600
SCAN_S = 3600
TICK_S = int(os.environ.get("BB_RELEASESIGN_TICK", "120"))
RUN_AGE_S = 3 * 86400
MAX_ZIP = 400 << 20
NOTE = "Signed by AerieOS:"
_lock = threading.Lock()
_busy = set()
_cache = {}
_bare = set()        # (project, run id): finished runs that handed over no APK
_rev = [0]           # moved when a look starts or ends: the revisions poll's "releasesign"


def configure(*, state, workspace, write_json_fn, projects=None, dispatch=None):
    globals().update(STATE=Path(state), WORKSPACE=Path(workspace), write_json=write_json_fn,
                     projects_fn=projects, dispatch_fn=dispatch)
    _cache.clear()
    _bare.clear()


def _file():
    return STATE / "release-signing.json"


def _load():
    try:
        d = json.loads(_file().read_text())
        return d if isinstance(d, dict) else {}
    except (OSError, ValueError):
        return {}


def _mine(d, project):
    rec = d.setdefault(project, {})
    for k in ("expect", "signed", "failed", "runs"):
        if not isinstance(rec.get(k), dict):
            rec[k] = {}
    return rec


def _save(d):
    if write_json:
        write_json(_file(), d)
    _cache.clear()
    _rev[0] += 1


def rev():
    """The token a Signing view and the bell re-read on: a look started, or
    one ended and wrote what it found."""
    return _rev[0]


def looking(project):
    """Whether a look at the project's runs is going now."""
    return project in _busy


# ---- what the project asks for ----------------------------------------------

def _workflows(project):
    """{path in the tree: text} of the project's workflow files."""
    d = WORKSPACE / project / ".github" / "workflows"
    try:
        flows = [f for f in d.iterdir() if f.is_file() and f.suffix in (".yml", ".yaml")]
    except OSError:
        return {}
    out = {}
    for f in flows:
        try:
            out[f".github/workflows/{f.name}"] = f.read_text(errors="replace")
        except OSError:
            continue
    return out


def wants(project):
    """Whether any of the project's workflows hands over an unsigned APK for
    the controller to sign (writes an artifact named bb-release-apk-...)."""
    return any(MARK in text for text in _workflows(project).values())


def handing(project):
    """The workflow files, by their path in the tree, whose run can hand an
    unsigned APK over: one that writes the artifact itself, and one that
    calls such a workflow as a job, however deep (a tag's run is the
    caller's: GitHub names the run by the workflow the tag started, not by
    the one that uploaded)."""
    flows = _workflows(project)
    out = {p for p, text in flows.items() if MARK in text}
    calls = {p: set(CALLS.findall("\n".join(ln for ln in text.splitlines() if not ln.lstrip().startswith("#"))))
             for p, text in flows.items()}
    while True:
        more = {p for p, to in calls.items() if p not in out and to & out}
        if not more:
            return out
        out |= more


def sealing(project):
    """The workflow files, by name, that sign a release's list of its files
    and are started once its signed APK is attached: each one that names
    SEAL and can be started by hand, both outside a comment, so a workflow
    that only mentions the name starts nothing."""
    out = []
    for path, text in sorted(_workflows(project).items()):
        live = _live(text)
        if SEAL in live and BY_HAND.search(live):
            out.append(path.rsplit("/", 1)[1])
    return out


def _live(text):
    """A workflow's text less its comment lines."""
    return "\n".join(ln for ln in text.splitlines() if not ln.lstrip().startswith("#"))


def unstartable(project, flows=None):
    """Why GitHub would refuse to start the project's sealing workflows (or
    `flows`, by file name) for a release, as a clause, or "". GitHub starts
    a workflow, by hand or through its API, only when the default branch
    carries it with its by-hand trigger, whichever ref it then runs on. ""
    too where nothing would be started (no sealing workflow, or none of the
    project's runs hands over an APK to sign) and where GitHub could not be
    asked, since the look after the tag says what came of the start."""
    flows = sealing(project) if flows is None else flows
    if not flows or not wants(project):
        return ""
    repo = cilogs.repo_of(project)
    token = cilogs._token(project) if repo else ""
    if not repo or not token:
        return ""
    base = f"{forgerelease.API}/repos/{repo}"
    missing = []
    try:
        main = str((forgerelease._req("GET", base, token) or {}).get("default_branch") or "")
        if not main:
            return ""
        for wf in flows:
            got = forgerelease._req("GET", f"{base}/contents/.github/workflows/{urllib.parse.quote(wf)}"
                                           f"?ref={urllib.parse.quote(main, safe='')}", token)
            try:
                text = base64.b64decode((got or {}).get("content") or "").decode(errors="replace") \
                    if isinstance(got, dict) else ""
            except ValueError:
                text = ""
            if not BY_HAND.search(_live(text)):
                missing.append(wf)
    except forgerelease.Refused:
        return ""
    if not missing:
        return ""
    return f"GitHub starts a workflow only from the default branch, and {main} has no {' or '.join(missing)} it can start"


def _seal(project, tag):
    """Start each of the project's sealing workflows for `tag`, on the tag,
    with the tag as its input: ([the ones started], "" or what to say of the
    ones that were not, with what a person does instead, in one sentence).
    Nothing of either for a project with no such workflow."""
    started, not_started = [], []
    for wf in sealing(project):
        try:
            body, code = (dispatch_fn(project, wf, tag, {"tag": tag}) if dispatch_fn
                          else ({"error": "this controller was given no way to start a workflow"}, 400))
        except Exception as e:                                      # noqa: BLE001 (said on the row, never the look's end)
            body, code = {"error": f"{type(e).__name__}: {e}"}, 500
        if code == 200:
            started.append(wf)
        else:
            not_started.append((wf, str((body or {}).get("error") or "no reason given")[:300]))
    if not not_started:
        return started, ""
    # The host's bare 404 for a workflow the default branch lacks, said as
    # what it is, with the one thing that lets anybody start it.
    if why := unstartable(project, [wf for wf, _ in not_started]):
        return started, (f"{tag}'s list of files is not signed: {why}, so put it there and start it from the tag "
                         "on the repository's Actions page")
    said = " or ".join(f"{wf} ({reason})" for wf, reason in not_started)
    return started, (f"{tag}'s list of files is not signed: GitHub would not start {said}, so start it from the tag "
                     "on the repository's Actions page")


APP_ID = re.compile(r"""applicationId\s*(?:=\s*)?["']([A-Za-z][A-Za-z0-9_]*(?:\.[A-Za-z][A-Za-z0-9_]*)+)["']""")


def packages(project):
    """The applicationIds the tree's Gradle files declare, which is what a
    release's APK will say it is: [package]."""
    root = WORKSPACE / project
    found = []
    for pat in ("build.gradle*", "*/build.gradle*", "*/*/build.gradle*"):
        for f in sorted(root.glob(pat)):
            if ".git" in f.parts or "node_modules" in f.parts:
                continue
            try:
                found += APP_ID.findall(f.read_text(errors="replace")[:400_000])
            except OSError:
                continue
    return sorted(set(found))


def _stamp(project):
    """What a readiness depends on that changes by a file coming or going:
    the workflows directory and the project's signing directories."""
    out = []
    for d in [WORKSPACE / project / ".github" / "workflows", signing.STATE / "signing" / project]:
        try:
            out.append(d.stat().st_mtime_ns)
            if d.name == project:
                out += sorted(x.stat().st_mtime_ns for x in d.iterdir() if x.is_dir())
        except (OSError, TypeError):
            out.append(0)
    return tuple(out)


def readiness(project, fresh=False):
    """{wanted, packages, keys: [{package, key, sha256}], node, why}: which
    key signs each app's release and on which node, or what keeps one from
    being signed. Kept for the bell's poll half a minute, or until a
    workflow or a key comes or goes; `fresh` asks again."""
    stamp = _stamp(project)
    hit = _cache.get(("ready", project))
    if not fresh and hit and hit[2] == stamp and time.time() - hit[0] < 30:
        return hit[1]
    out = {"wanted": wants(project), "packages": [], "keys": [], "why": "", "node": ""}
    if out["wanted"]:
        out["packages"] = packages(project)
        out["node"] = signing.signer_name(project)
        for pkg in out["packages"] or [""]:
            key, rec, why = signing.release_key(project, pkg)
            if why:
                out["why"] = why
                break
            out["keys"].append({"package": pkg, "key": key, "sha256": rec.get("sha256") or "",
                                "rotated_from": rec.get("rotated_from") or ""})
        if not out["why"]:
            # The node the APK is signed on: online, current, and holding
            # the jdk and build-tools (signing.signer).
            out["why"] = signing.signer(project, build_tools=True)[1]
        if not out["why"] and not cilogs.repo_of(project):
            out["why"] = (f"{project} is not on GitHub, which is the one forge whose workflow "
                          "artifacts the controller fetches to sign")
    _cache[("ready", project)] = (time.time(), out, stamp)
    return out


def status(project):
    """What the Signing view says of releases: readiness, and the newest
    signed and failed, newest first."""
    rec = _load().get(project) or {}
    newest = lambda d: sorted(({"tag": t, **v} for t, v in (d or {}).items() if isinstance(v, dict)),
                              key=lambda x: -int(x.get("at") or 0))[:5]
    return readiness(project, fresh=True) | {"signed": newest(rec.get("signed")), "failed": newest(rec.get("failed")),
                                             "looking": looking(project), "last": rec.get("last") or {},
                                             "expect": sorted(rec.get("expect") or {})}


# ---- GitHub -----------------------------------------------------------------

def _download(repo, aid, token, into):
    """An artifact's zip into the file `into`. GitHub answers with a redirect
    to its storage host, which is never handed the token."""
    path = f"/repos/{repo}/actions/artifacts/{int(aid)}/zip"
    if not re.fullmatch(r"/repos/[A-Za-z0-9_.-]+/[A-Za-z0-9_.-]+/actions/artifacts/\d+/zip", path):
        raise cilogs.Refused("not a path this asks GitHub for")
    req = urllib.request.Request(cilogs.API + path, headers={"User-Agent": "AerieOS",
                                                             "Accept": "application/vnd.github+json"})
    req.add_unredirected_header("Authorization", f"Bearer {token}")
    try:
        # The host is cilogs' literal API and the path is checked above.
        with urllib.request.urlopen(req, timeout=600) as r, open(into, "wb") as f:  # nosemgrep: python.lang.security.audit.dynamic-urllib-use-detected.dynamic-urllib-use-detected
            n = 0
            while chunk := r.read(1 << 20):
                n += len(chunk)
                if n > MAX_ZIP:
                    raise cilogs.Refused("the artifact is larger than an APK's zip should be")
                f.write(chunk)
    except urllib.error.HTTPError as e:
        if e.code in (401, 403):
            raise cilogs.Refused("GitHub refused the token for the run's artifact: it needs Actions: read") from e
        if e.code == 410:
            raise cilogs.Refused("GitHub no longer keeps the run's artifact: run the workflow again") from e
        raise cilogs.Refused(f"GitHub answered {e.code} for the run's artifact") from e
    except (urllib.error.URLError, OSError) as e:
        raise cilogs.Refused(f"could not fetch the run's artifact: {e}") from e


def _waiting(project, repo, token, seen=None):
    """[(run, artifact id, tag, going, the run as GitHub lists it)] of the
    recent runs that handed over an unsigned APK: the ones that passed, and
    the ones still going (`going`), whose release may not be made yet;
    `seen`, when given, counts the runs asked about and the ones skipped as
    known to hand over nothing (what a look says, R190 step 5). Any run of
    the repository is listed here, a pull request's from a fork too: whether
    one is its tag's own is _own's to say, before anything is fetched."""
    j = cilogs._get(f"/repos/{repo}/actions/runs?per_page=50", token)
    out = []
    seen = seen if seen is not None else {}
    seen.update(asked=0, known_bare=0)
    for r in (j.get("workflow_runs") or [])[:50]:
        rid = int(r.get("id") or 0)
        # A run that ended any way but passed hands over nothing to sign.
        going = str(r.get("status") or "completed") != "completed"
        if not going and str(r.get("conclusion") or "success") != "success":
            continue
        at = str(r.get("created_at") or "")
        try:
            t = calendar.timegm(time.strptime(at[:19], "%Y-%m-%dT%H:%M:%S"))
        except ValueError:
            t = 0
        if not rid or (t and time.time() - t > RUN_AGE_S):
            continue
        if (project, rid) in _bare:
            seen["known_bare"] += 1
            continue
        seen["asked"] += 1
        arts = cilogs._get(f"/repos/{repo}/actions/runs/{rid}/artifacts?per_page=50", token)
        found = False
        for a in (arts.get("artifacts") or [])[:50]:
            name = str(a.get("name") or "")
            tag = name[len(MARK):]
            if name.startswith(MARK) and TAG.fullmatch(tag) and not a.get("expired"):
                out.append((rid, int(a.get("id") or 0), tag, going, r))
                found = True
        # A finished run's artifacts do not change: one that handed over
        # nothing is not asked about again (a look every few minutes for a
        # release's twelve hours would otherwise ask about thirty runs each).
        # GitHub can list a run as finished a little before it lists the
        # artifact it uploaded, so a run that ended in the last ten minutes
        # is asked about again (B467).
        try:
            ended = calendar.timegm(time.strptime(str(r.get("updated_at") or "")[:19], "%Y-%m-%dT%H:%M:%S"))
        except ValueError:
            ended = 0
        # ...and one still going may hand its APK over yet.
        if not found and not going and (not ended or time.time() - ended > 600):
            _bare.add((project, rid))
    return out


def _tag_commit(repo, token, tag):
    """(the commit the tag `tag` names on GitHub, "") or ("", why not). An
    annotated tag's ref names a tag object, which names the commit (or
    another tag object): followed to the commit, a few deep at most."""
    base = f"{forgerelease.API}/repos/{repo}/git"
    try:
        # git/ref/ reads one ref exactly; git/refs/ would answer every tag
        # that starts with this one's name.
        ref = forgerelease._req("GET", f"{base}/ref/tags/{urllib.parse.quote(tag, safe='')}", token)
        if not isinstance(ref, dict) or ref.get("ref") != f"refs/tags/{tag}":
            return "", f"the tag {tag} is not on GitHub, so no run is its own: push the tag, then run its workflow again"
        obj = ref.get("object")
        for _ in range(5):
            obj = obj if isinstance(obj, dict) else {}
            sha = str(obj.get("sha") or "").lower()
            if not re.fullmatch(r"[0-9a-f]{40,64}", sha):
                break
            if obj.get("type") == "commit":
                return sha, ""
            if obj.get("type") != "tag":
                break
            obj = (forgerelease._req("GET", f"{base}/tags/{sha}", token) or {}).get("object")
    except forgerelease.Refused as e:
        return "", f"the commit the tag {tag} names could not be read, so its run could not be told from another's ({e})"
    return "", f"the tag {tag} names no commit on GitHub, so no run is its own"


def _own(r, repo, tag, flows, commit_of):
    """Why the run `r`, as GitHub lists it, is not the own run of the
    release `tag`, or "" when it is. Read from the run alone, in this order:
    where its commit came from (head_repository against the run's own
    repository: a pull request from a fork is listed among a repository's
    runs), what started it (event), what it ran on (head_branch, which for a
    tag's push and a release is the tag's name), which workflow file it is a
    run of (path, against the ones in the project's tree that hand over),
    and its commit (head_sha) against the one the tag names now, asked of
    GitHub last and only for a run that passed the rest. `commit_of` is
    _tag_commit, kept per look."""
    home = str((r.get("repository") or {}).get("full_name") or repo)
    head = str((r.get("head_repository") or {}).get("full_name") or "")
    if head.lower() != home.lower():
        return (f"its commit came from {head or 'a repository GitHub no longer names'}, not from {home}: "
                "a fork's run is never signed")
    event = str(r.get("event") or "")
    if event not in EVENTS:
        how = ("a pull request started it" if event.startswith("pull_request") else
               "it was started by hand" if event == "workflow_dispatch" else
               f"{event} started it" if event else "GitHub does not say what started it")
        return (f"{how}, and an APK is signed only from the run the tag {tag} itself started, by its push or "
                "its release: run that one again from its page on GitHub (Re-run all jobs)")
    ran_on = str(r.get("head_branch") or "")
    if ran_on != tag:
        return f"it ran on {ran_on or 'no branch or tag GitHub names'}, not on the tag {tag} its artifact is named for"
    # GitHub may say the ref the file was read at after an @.
    path = str(r.get("path") or "").split("@", 1)[0]
    if path not in flows:
        return (f"it is a run of {path or 'a workflow GitHub does not name'}, and "
                + (f"the workflows in this space's tree that hand over an unsigned APK are {', '.join(sorted(flows))}"
                   if flows else "no workflow in this space's tree hands over an unsigned APK"))
    commit, why = commit_of(tag)
    if why:
        return why
    sha = str(r.get("head_sha") or "").lower()
    if sha != commit:
        return (f"it ran on commit {sha[:12] or 'GitHub does not name'}, and the tag {tag} names {commit[:12]}: "
                "the tag moved after the run started, or the run is not the tag's")
    return ""


def _carried(rel, was):
    """What a release already carries of a signing, in words, or "": the
    files this controller attached to it (`was`, its record of the tag), or
    a line in its notes saying AerieOS signed one, which another controller
    on the same repository writes too. The notes' line is written last, so
    an attach that stopped half way reads as not carried and is finished."""
    names = {a.get("name") for a in rel.get("assets") or [] if isinstance(a, dict)}
    mine = [n for n in (was or {}).get("files") or [] if n in names]
    if mine:
        return ", ".join(mine)
    if any(ln.startswith(NOTE) for ln in str(rel.get("body") or "").splitlines()):
        return "an APK its notes say AerieOS signed"
    return ""


def _has_release(repo, token, tag):
    """Whether `tag` has a release on GitHub, a draft counted."""
    try:
        return bool(forgerelease._req("GET", f"{forgerelease.API}/repos/{repo}/releases/tags/{urllib.parse.quote(tag)}", token))
    except forgerelease.Refused:
        return False


def _release_gone(repo, token, tag):
    """Whether GitHub says `tag` has no release, a draft counted: True only on
    its own answer, never because it could not be asked, so a row is not
    lost to a passing outage."""
    try:
        return forgerelease._req("GET", f"{forgerelease.API}/repos/{repo}/releases/tags/{urllib.parse.quote(tag)}", token) is None
    except forgerelease.Refused:
        return False


def _attach(project, repo, token, tag, files, lines):
    """Each (name, path) onto the release for `tag` with its sha256 file, one
    of the same name replaced, and the notes' signing lines put in place of
    any earlier ones. The release's address."""
    base = f"{forgerelease.API}/repos/{repo}/releases"
    rel = forgerelease._req("GET", f"{base}/tags/{urllib.parse.quote(tag)}", token)
    if not rel:
        raise forgerelease.Refused(f"there is no release for {tag} on GitHub to attach the APK to")
    have = {a.get("name"): a for a in rel.get("assets") or []}
    for name, path in files:
        data = Path(path).read_bytes()
        sums = f"{hashlib.sha256(data).hexdigest()}  {name}\n".encode()
        for n, body, ctype in ((name, data, "application/vnd.android.package-archive"),
                               (f"{name}.sha256", sums, "text/plain")):
            if n in have:
                forgerelease._req("DELETE", f"{base}/assets/{int(have[n]['id'])}", token)
            forgerelease._req("POST", f"{forgerelease.UPLOADS}/repos/{repo}/releases/{int(rel['id'])}/assets"
                                      f"?name={urllib.parse.quote(n)}", token, data=body, ctype=ctype)
    kept = [ln for ln in str(rel.get("body") or "").rstrip().splitlines() if not ln.startswith(NOTE)]
    while kept and not kept[-1].strip():
        kept.pop()
    body = "\n".join([*kept, *([""] if kept else []), *lines])
    # The release's draft said back with the notes: a draft whose notes were
    # sent alone was published, unread, by the APK's attach (B590).
    # The tag goes with it: GitHub drops a draft's tag patched without one (B696).
    forgerelease._req("PATCH", f"{base}/{int(rel['id'])}", token, {"body": body, "draft": rel.get("draft") is True,
                                                                  "tag_name": tag})
    return rel.get("html_url") or ""


def _sign_run(project, repo, token, rid, aid, tag, was=None, replace=False):
    """Fetch one run's artifact, sign what it holds, attach it. {url, files,
    key, cert} or {error}; or {kept}, what the release already carries of an
    earlier signing (`was`, this controller's record of the tag), with
    nothing fetched or signed, unless `replace`."""
    d = tempfile.mkdtemp(prefix="bb-relsign-")
    try:
        os.chmod(d, 0o700)
        # The release is read before anything is fetched: one that is not
        # there fails here as it would at the attach, and one that carries
        # its signed APK is not signed again by a later run on its own.
        rel = forgerelease._req("GET", f"{forgerelease.API}/repos/{repo}/releases/tags/{urllib.parse.quote(tag)}", token)
        if not rel:
            return {"error": f"there is no release for {tag} on GitHub to attach the APK to"}
        if not replace and (kept := _carried(rel, was)):
            return {"kept": kept}
        z = os.path.join(d, "artifact.zip")
        _download(repo, aid, token, z)
        try:
            with zipfile.ZipFile(z) as zf:
                names = [n for n in zf.namelist() if APK.fullmatch(os.path.basename(n)) and not n.endswith("/")]
                apks = []
                for n in names[:8]:
                    p = os.path.join(d, "in-" + os.path.basename(n))
                    with zf.open(n) as src, open(p, "wb") as dst:
                        shutil.copyfileobj(src, dst)
                    apks.append((os.path.basename(n), p))
        except zipfile.BadZipFile:
            return {"error": "the run's artifact is not a zip"}
        if not apks:
            return {"error": f"the run's {MARK}{tag} artifact holds no .apk"}
        out, said, first = [], [], {}
        for name, path in apks:
            final = name.replace("-unsigned", "")
            dst = os.path.join(d, "out-" + final)
            r = signing.sign_release(project, path, dst)
            if r.get("error"):
                return {"error": f"{name}: {r['error']}"}
            first = first or r
            out.append((final, dst))
            said.append(f"{NOTE} {final} with the sideload key {r['key']}, certificate SHA-256 {r['cert']}"
                        + (f" (rotated from {r['rotated_from']}, with the proof)" if r.get("rotated_from") else ""))
        url = _attach(project, repo, token, tag, out, said)
        return {"url": url, "files": [n for n, _ in out], "key": first.get("key"), "cert": first.get("cert")}
    except (cilogs.Refused, forgerelease.Refused, OSError) as e:
        return {"error": str(e)}
    finally:
        shutil.rmtree(d, ignore_errors=True)


def expect(project, tag):
    """A release was just made for `tag`: its APK is looked for every few
    minutes for a while, and a release whose APK never comes is said."""
    if not TAG.fullmatch(tag or "") or not wants(project):
        return
    with _lock:
        d = _load()
        _mine(d, project)["expect"][tag] = int(time.time())
        _save(d)
    check_soon(project)


def check(project, force=False, again=""):
    """Look at the project's recent runs now; sign and attach each unsigned
    APK its tag's own run handed over and its release does not carry yet (a
    failed one again when `force` or an hour on). `again` is a tag a person
    named: its own run's APK is signed again and replaces the one on its
    release, which no run does by itself. {signed: [tag], failed: [tag],
    error}."""
    now = int(time.time())
    again = again if TAG.fullmatch(again or "") else ""
    done = {"signed": [], "failed": [], "error": ""}
    repo = cilogs.repo_of(project)
    token = cilogs._token(project) if repo else ""
    if not repo or not token:
        done["error"] = ("not on GitHub" if not repo else
                         "the controller has no GitHub token for this space, so it cannot fetch the APK to sign")
        return done
    seen = {}
    try:
        waiting = _waiting(project, repo, token, seen)
    except cilogs.Refused as e:
        done["error"] = str(e)
        waiting = []
    d = _load()
    rec = _mine(d, project)
    rec["scanned"] = now
    # What this look found, run by run, for aerie sign release to say (R190
    # step 5): "looking" alone left a missing APK unexplained.
    last = {"at": now, "error": done["error"], "asked": seen.get("asked", 0),
            "known_bare": seen.get("known_bare", 0), "runs": []}
    flows, commits = handing(project), {}

    def commit_of(tag):
        if tag not in commits:
            commits[tag] = _tag_commit(repo, token, tag)
        return commits[tag]
    # By tag: the newest run that handed an APK over and was refused, the
    # tags a run of their own was found for, and the ones whose release
    # was found to carry its signed APK already.
    refused, own, carried = {}, set(), set()
    redone = not again
    for rid, aid, tag, going, run in waiting:
        ran = rec["runs"].get(str(rid)) or {}
        redo = tag == again and not redone
        if ran.get("state") == "signed" and not redo:
            last["runs"].append({"run": rid, "tag": tag, "state": "signed before"})
            own.add(tag)
            continue
        # Whose run it is, before anything of it is fetched: said, and
        # asked again at the next look, since a tag can be pushed after.
        if why := _own(run, repo, tag, flows, commit_of):
            last["runs"].append({"run": rid, "tag": tag, "state": "refused", "why": why})
            refused.setdefault(tag, (rid, why))
            continue
        own.add(tag)
        # The run that makes the release has not made it yet: nothing is
        # fetched or signed, nothing has failed, and the next look asks again.
        if going and not _has_release(repo, token, tag):
            last["runs"].append({"run": rid, "tag": tag, "state": "its run has not made the release yet"})
            continue
        if ran.get("state") == "failed" and not force and not redo and now - int(ran.get("at") or 0) < SCAN_S:
            last["runs"].append({"run": rid, "tag": tag, "state": "failed within the hour, not tried again"})
            continue
        r = _sign_run(project, repo, token, rid, aid, tag, was=rec["signed"].get(tag), replace=redo)
        if r.get("kept"):
            # A release is signed once: what it carries stays until a
            # person asks for the tag again. Nothing has failed and nothing
            # is waited for, whichever controller signed it.
            rec["failed"].pop(tag, None)
            rec["expect"].pop(tag, None)
            carried.add(tag)
            last["runs"].append({"run": rid, "tag": tag, "state": "not signed again",
                                 "why": f"{tag}'s release already carries {r['kept']}, and a later run replaces it "
                                        f"only when a person asks: aerie sign release --again {tag} --why \"...\""})
            continue
        redone = redone or redo
        # The APK is on the release: the workflows that sign the release's
        # list of files are started for it, and one that could not be is
        # said with the signing.
        started, unsealed = ([], "") if r.get("error") else _seal(project, tag)
        last["runs"].append({"run": rid, "tag": tag, "state": "failed" if r.get("error") else "signed",
                             "why": r.get("error") or unsealed
                                    or (f"{' and '.join(started)} started to sign the release's list of files" if started else ""),
                             "url": r.get("url") or ""})
        if r.get("error"):
            rec["runs"][str(rid)] = {"state": "failed", "at": now, "tag": tag}
            rec["failed"][tag] = {"why": r["error"], "at": now, "run": rid}
            done["failed"].append(tag)
        else:
            rec["runs"][str(rid)] = {"state": "signed", "at": now, "tag": tag}
            rec["signed"][tag] = {"at": now, "run": rid, "url": r["url"], "files": r["files"],
                                  "key": r["key"], "cert": r["cert"]}
            rec["failed"].pop(tag, None)
            rec["expect"].pop(tag, None)
            done["signed"].append(tag)
            if unsealed:
                # Red on the bell and in the Signing view until it is put
                # away: the APK is signed, the release is not whole, and
                # nothing here tries again. `sealing` is what the bell
                # titles the row by.
                rec["failed"][tag] = {"why": unsealed, "at": now, "run": rid, "sealing": True}
    if not redone:
        # The tag a person named had no run to sign again: said, with the
        # runs above when one was refused.
        last["said"] = [f"{again} was not signed again: " + (
            "the runs above say why" if any(x["tag"] == again for x in last["runs"]) else
            f"no run of the last {RUN_AGE_S // 86400} days still holds an unsigned APK for it. Run the tag's own "
            "run again from its page on GitHub (Re-run all jobs), then ask again")]
    # A release made here whose APK never came: said once it is overdue,
    # with the run that was refused when one handed an APK over.
    for tag, at in list(rec["expect"].items()):
        if now - int(at or 0) > EXPECT_S:
            rec["expect"].pop(tag)
            if tag not in rec["signed"]:
                rec["failed"][tag] = {"why": (
                    f"no run of {tag}'s own handed over an unsigned APK within {EXPECT_S // 3600} hours: run "
                    f"{refused[tag][0]} did and was refused, since {refused[tag][1]}" if tag in refused else
                    f"no run that passed handed over an unsigned APK for {tag} within "
                    f"{EXPECT_S // 3600} hours: its build failed or never ran (aerie ci-log)"),
                                      "at": now, "run": 0}
                done["failed"].append(tag)
    # ...and one still waited for whose only APK came from a run that is
    # not its own: red on the bell and in the Signing view now, where the
    # wait says nothing for twelve hours. Written once for what it says, so
    # a row put away stays away.
    for tag, (rid, why) in refused.items():
        said = f"run {rid} handed over an unsigned APK for {tag} and was refused: {why}"
        if (tag in rec["expect"] and tag not in own and tag not in rec["signed"]
                and (rec["failed"].get(tag) or {}).get("why") != said):
            rec["failed"][tag] = {"why": said, "at": now, "run": rid}
            done["failed"].append(tag)
    # A release that is gone (deleted on GitHub, a draft included) has
    # nothing left to sign or seal: its red row goes with it. v0.9.0-dev.4885's
    # stayed on the bell for 17 days after the release was deleted.
    if repo and token:
        for tag in [t for t in rec["failed"] if t not in done["failed"]]:
            if _release_gone(repo, token, tag):
                rec["failed"].pop(tag, None)
                rec["signed"].pop(tag, None)
    rec["last"] = last
    # Old runs forgotten: their artifacts are gone by now.
    rec["runs"] = {k: v for k, v in rec["runs"].items() if now - int((v or {}).get("at") or 0) < 2 * RUN_AGE_S}
    with _lock:
        whole = _load()
        # A release expected while this look ran is kept for the next.
        was = (whole.get(project) or {}).get("expect") or {}
        rec["expect"].update({t: a for t, a in was.items()
                              if int(a or 0) >= now and t not in rec["signed"] and t not in carried})
        whole[project] = rec
        _save(whole)
    return done


def due(project, now=None):
    """Whether a project wants a look: a release expected, or the hourly one."""
    now = now or time.time()
    rec = _load().get(project) or {}
    if any(now - int(at or 0) <= EXPECT_S for at in (rec.get("expect") or {}).values()):
        return True
    return now - int(rec.get("scanned") or 0) >= SCAN_S and wants(project)


def _claim(project):
    with _lock:
        if project in _busy:
            return False
        _busy.add(project)
        _rev[0] += 1
        return True


def _release(project):
    with _lock:
        _busy.discard(project)
        _rev[0] += 1


def check_soon(project, force=False, again=""):
    """check() on its own thread, one per project at a time."""
    if not _claim(project):
        return False

    def go():
        try:
            said = check(project, force, again).get("error")
            if said:
                print(f"dashboard: release signing {project}: {said}", flush=True)
        except Exception as e:                                      # noqa: BLE001 (a look must not take the server)
            print(f"dashboard: release signing {project}: {e}", flush=True)
        finally:
            _release(project)
    threading.Thread(target=go, name=f"releasesign-{project}", daemon=True).start()
    return True


def start():
    """Every TICK_S, each project that is due. A daemon thread."""
    def loop():
        while True:
            time.sleep(TICK_S)
            for p in (projects_fn() if projects_fn else []):
                try:
                    if not due(p) or not _claim(p):
                        continue
                except Exception:                                   # noqa: BLE001 (a loop must not die)
                    continue
                try:
                    check(p)
                except Exception as e:                              # noqa: BLE001
                    print(f"dashboard: release signing {p}: {e}", flush=True)
                finally:
                    _release(p)
    threading.Thread(target=loop, name="releasesign", daemon=True).start()


# ---- the bell ---------------------------------------------------------------

def attention(projects):
    """The bell's rows, kind release-sign: what would keep a release's APK
    from being signed, said before the release (amber), and a signing that
    failed after one (red, `bad`), each keyed for bellseen on what it says.
    `sealing` marks the one whose APK is signed and whose list of files
    could not be started."""
    out, whole = [], _load()
    for p in projects:
        r = readiness(p)
        if r["wanted"] and r["why"]:
            h = hashlib.sha256(r["why"].encode()).hexdigest()[:10]
            out.append({"kind": "release-sign", "id": p, "project": p, "why": r["why"], "bad": False,
                        "key": f"rsign:{p}@{h}"})
        for tag, f in ((whole.get(p) or {}).get("failed") or {}).items():
            if isinstance(f, dict):
                out.append({"kind": "release-sign", "id": f"{p}|{tag}", "project": p, "tag": tag,
                            "why": str(f.get("why") or ""), "at": int(f.get("at") or 0), "bad": True,
                            "sealing": f.get("sealing") is True,
                            "key": f"rsign:{p}|{tag}@{int(f.get('at') or 0)}"})
    return out
