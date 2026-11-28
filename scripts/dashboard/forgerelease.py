"""The forge's release beside the tag: when Release
has pushed a version's tag and the project is on GitHub, Gitea or GitLab
with a token that can write there, the forge's release for that tag, titled
with the version, its notes the changelog's section for it, its builds
attached.

On GitHub it is read and written with the project's own token, else the
shared PAT (the same one cilogs.py reads runs with), and only
api.github.com and uploads.github.com are asked. On Gitea (Forgejo and
Codeberg answer the same API) and on GitLab it is the project's own
token alone, the one its link stored, asked of the API root forges.py
derives from the remote's host and scheme and nothing else: a Gitea on a
LAN is plain http on a port, and that is the address its token was stored
for. GitLab keeps no files on a release, so a build goes into the
project's generic package registry under the version and the release
links to it there.

A release that exists already is changed only by edit:
its notes replaced, files attached to it (one of the same
name replaced), never the release deleted or its tag moved, and only with
files from the project's dist/ or its committed tree, which edit_plan
checks before anybody is asked. A file comes off a release only by
remove, its own ask and never part of an edit.

A release that exists already for the tag is left as it is and pointed at:
a second press makes nothing twice. What was made, or why nothing was, is
kept per project and tag, so the version row can link to it or say the
reason.

Builds are matched on the released commit: a file in dist/ whose name
carries that commit's short id (every build is named so) and is not a
dirty one, or carries the id of another commit with the same tree. Work
lands through a pull request, so the tag goes on the merge commit while
the builds were made, and signed, from the branch tip it merged: the same
files under another id (one space's v0.5.4 was released with
nothing attached). Signed ones are what a release carries when there are any; an
unsigned or debug build only where nothing signed was built.
"""
import fnmatch
import json
import mimetypes
import os
import re
import subprocess
import time
import urllib.error
import urllib.parse
import urllib.request
from pathlib import Path

import changelog
import cilogs
import forges
import statefile

STATE = Path("/config")
WORKSPACE = Path("/workspace")
write_json = None

API = "https://api.github.com"
UPLOADS = "https://uploads.github.com"
ASSET_MAX = 1_900_000_000         # GitHub takes 2 GiB a file; this leaves room
SHIPS = re.compile(r"\.(apk|aab|zip|xpi|tar\.gz|tgz|exe|msi|dmg|deb|rpm|AppImage)$")


class Refused(Exception):
    """A release this module will not make, with the sentence to show."""


class NoRelease(Refused):
    """The git host has no release for the tag: never made, or taken away."""


def configure(*, state, workspace, write_json_fn):
    globals().update(STATE=Path(state), WORKSPACE=Path(workspace), write_json=write_json_fn)
    import gitcreds                                         # noqa: PLC0415
    gitcreds.configure(state=state)


def _file():
    return STATE / "forge-releases.json"


_store = statefile.Store(_file, write=lambda: write_json)


def kept(project):
    """{tag: {url, error}} of the releases made, or refused, for this project."""
    got = _store.load().get(project)
    return got if isinstance(got, dict) else {}


def _keep(project, tag, url, error="", forge="GitHub"):
    d = _store.load()
    d.setdefault(project, {})[tag] = {"url": url, "error": error, "forge": forge}
    if write_json:
        _store.save(d)


# ---- what goes in it ----------------------------------------------------------

def notes(where, version, tag="", repo=""):
    """The release's notes: the tree's docs/release-notes/VERSION.md when it
    has one (@TAG@, @VER@ and @REPO@ filled in, as CI fills them for a
    release it makes), else the changelog's section for `version`, as
    Markdown, or "" when the file has none: its categories as headings and
    its entries as a list. A version cut without a bump has its changes
    still under Unreleased, and those are what it releases (v0.5.0 went out
    with no notes)."""
    own = Path(where) / "docs" / "release-notes" / f"{version}.md"
    try:
        return (own.read_text().replace("@TAG@", tag or f"v{version}")
                .replace("@VER@", version).replace("@REPO@", repo)).strip()
    except OSError:
        pass
    text = changelog.read(where) or ""
    pending = None
    for sec in changelog.sections(text):
        title = sec.get("title") or ""
        if title == version or title.startswith(version + ":") or title.startswith(version + " "):
            return _listed(sec)
        if pending is None and title == "Unreleased":
            pending = sec
    return _listed(pending) if pending else ""


# ---- what each of a release's files is for -----------------------------
# Over the notes of every release AerieOS makes or publishes, unless the
# repository's Releases settings switch it off: a row for each file the
# release holds with what it is for, from the repository's list, the
# checksums and signatures folded into one row, a file nobody described
# listed by its name. A repository holding docs/release-notes/downloads.md
# has that file put over its notes instead, @TAG@, @VER@ and @REPO@ filled.
FILES_HEAD = "### Which download is for what"
# project -> (on, [{name, what}]): the repository's setting, the server's.
files_setting = None
_COMPANION = re.compile(r"\.(sha256|sha512|asc|sig|minisig|attestation\.jsonl|intoto\.jsonl)$")


def _cell(t):
    return " ".join(str(t or "").split()).replace("|", "\\|")


def _version_of(tag):
    m = re.search(r"v(\d+\.\d+\.\d+[^\s/]*)$", str(tag or ""))
    return m.group(1) if m else str(tag or "")


def files_table(project, names, version="", tag="", repo="", where=None):
    """The table, or "" when it is switched off or there is no file."""
    try:
        on, rows = files_setting(project) if files_setting else (True, [])
    except Exception:  # noqa: BLE001  (a setting that cannot be read is the default)
        on, rows = True, []
    if not on:
        return ""
    version = version or _version_of(tag)
    own = Path(where or (WORKSPACE / project)) / "docs" / "release-notes" / "downloads.md"
    try:
        return (own.read_text().replace("@TAG@", tag or f"v{version}").replace("@VER@", version)
                .replace("@REPO@", repo)).strip()
    except OSError:
        pass
    names = [str(n) for n in names or () if n]
    if not names:
        return ""

    def what(n):
        for r in rows or ():
            pat = str(r.get("name") or "").replace("@VER@", version).replace("@TAG@", tag)
            if pat and fnmatch.fnmatchcase(n, pat):
                return str(r.get("what") or "")
        return ""
    main = [n for n in names if not _COMPANION.search(n)]
    extra = [n for n in names if _COMPANION.search(n)]
    out = [FILES_HEAD, "", "| File | What it is for |", "|---|---|"]
    out += [f"| `{_cell(n)}` | {_cell(what(n))} |" for n in main]
    if extra:
        kinds = sorted({"*" + m.group(0) for n in extra if (m := _COMPANION.search(n))})
        said = next((w for n in extra if (w := what(n))), "") or \
            "The checksum or signature of the file of the same name, to check a download; nothing to install."
        out.append(f"| {', '.join(f'`{k}`' for k in kinds)} | {_cell(said)} |")
    return "\n".join(out)


def with_files_table(project, notes, names, version="", tag="", repo="", where=None):
    """`notes` with the table over them, once: notes that carry it already
    are left as they are."""
    if FILES_HEAD in (notes or ""):
        return notes
    t = files_table(project, names, version, tag, repo, where)
    return f"{t}\n\n{notes or ''}".strip() if t else notes


def undescribed(project, names, version="", tag=""):
    """The files of a release the repository's list says nothing about, the
    checksums aside: [] when the table is off or a downloads.md stands in."""
    try:
        on, rows = files_setting(project) if files_setting else (True, [])
    except Exception:  # noqa: BLE001
        return []
    if not on or (WORKSPACE / project / "docs" / "release-notes" / "downloads.md").is_file():
        return []
    version = version or _version_of(tag)
    pats = [str(r.get("name") or "").replace("@VER@", version).replace("@TAG@", tag) for r in rows or ()]
    return [n for n in names if not _COMPANION.search(n) and not any(p and fnmatch.fnmatchcase(n, p) for p in pats)]


def _listed(sec):
    out, cat = [], None
    for e in sec.get("entries") or []:
        if e.get("cat") != cat:
            cat = e.get("cat")
            if cat:
                out.append(f"\n### {cat}\n")
        out.append(f"- {e.get('text', '')}")
    return "\n".join(out).strip()


def _shown(project):
    """The name the project is shown under, not its folder (a release
    read "builderbot-2 0.5.0")."""
    import roles
    return roles.shown(project)


def assets(project, sha, version=""):
    """The builds of commit `sha` in the project's dist/, signed ones when
    there are any: [Path], newest first. A signed build whose name carries
    no commit id (one signed from a build named by its version alone, as
    aerie sign names what it makes after what it was given) is the
    release's when its name carries `version` and it was made after the
    commit was: report #133, where the debug build of the pull request's
    head went out alone beside two such signed copies passed over."""
    d = WORKSPACE / project / "dist"
    if not sha or not d.is_dir():
        return []
    # An unsigned APK installs nowhere and is the controller's to sign
    # (releasesign.py): never one of a release's files.
    ships = [f for f in d.iterdir() if f.is_file() and "-dirty" not in f.name and "-unsigned" not in f.name
             and SHIPS.search(f.name)]
    files = [f for f in ships if sha in f.name]
    if not files:
        same = _same_tree(project, sha, {m.group(1) for f in ships for m in [BUILD_SHA.search(f.name)] if m})
        files = [f for f in ships if (m := BUILD_SHA.search(f.name)) and m.group(1) in same]
    signed = [f for f in files if "-signed" in f.name]
    if version and (when := _commit_time(project, sha)):
        # The version itself, not a pre-release of it (0.6.8 is not 0.6.8-dev.3).
        named = re.compile(rf"(?<![0-9A-Za-z.]){re.escape(version)}(?![0-9A-Za-z]|[-.+](?:dev|rc|alpha|beta|pre)\b)")
        signed += [f for f in ships if "-signed" in f.name and f not in signed and not BUILD_SHA.search(f.name)
                   and named.search(f.name) and f.stat().st_mtime >= when]
    if signed:
        files = signed
    else:
        real = [f for f in files if "-debug" not in f.name]
        files = real or files
    return sorted(files, key=lambda f: f.stat().st_mtime, reverse=True)


BUILD_SHA = re.compile(r"-([0-9a-f]{7,12})(?=[-.])")


def _commit_time(project, sha):
    """When commit `sha` was made (its committer's time), 0 when unknown."""
    try:
        r = subprocess.run(["git", "-C", str(WORKSPACE / project), "show", "-s", "--format=%ct", sha],
                           capture_output=True, text=True, timeout=10)
        return int(r.stdout.strip() or 0) if r.returncode == 0 else 0
    except (OSError, subprocess.SubprocessError, ValueError):
        return 0


def _same_tree(project, sha, others):
    """Those of `others` (short commit ids from build names) whose commit
    holds the same tree as `sha`: the same files, built before a merge."""
    def tree(c):
        try:
            r = subprocess.run(["git", "-C", str(WORKSPACE / project), "rev-parse", "--verify", "--quiet",
                                f"{c}^{{tree}}"], capture_output=True, text=True, timeout=10)
        except (OSError, subprocess.SubprocessError):
            return ""
        return r.stdout.strip() if r.returncode == 0 else ""
    want = tree(sha)
    return {c for c in others if want and tree(c) == want} if want else set()


# ---- asking GitHub ------------------------------------------------------------

# A release asked for by its tag, for _req's draft fallback.
_BY_TAG = re.compile(re.escape(API) + r"/repos/([^/?#]+/[^/?#]+)/releases/tags/([^/?#]+)")

def _draft_by_tag(repo, tag, token, pages=3):
    """The release (a draft among them) whose tag is `tag`, from the listed
    releases, newest first, or None. A draft GitHub moved to a name of its
    own (untagged-ID: a PATCH that left out tag_name) is found by its
    title, the tag, and every PATCH here sends the tag back with it."""
    for page in range(1, pages + 1):
        rows = _req("GET", f"{API}/repos/{repo}/releases?per_page=50&page={page}", token) or []
        for r in rows if isinstance(rows, list) else []:
            if isinstance(r, dict) and (r.get("tag_name") == tag or (
                    r.get("draft") and r.get("name") == tag and str(r.get("tag_name") or "").startswith("untagged-"))):
                return r
        if not isinstance(rows, list) or len(rows) < 50:
            return None
    return None


# What a token must be allowed for a release, by the kind of forge: the words
# its refusal is answered with.
_NEEDS = {"github": "contents write", "gitlab": "the api scope", "gitea": "the repository scope with write"}


def _request(method, url, accept, auth, body, data, ctype):
    """The request for one call: `data` as it is, else `body` as JSON."""
    payload = data if data is not None else (json.dumps(body).encode() if body is not None else None)
    return urllib.request.Request(url, data=payload, method=method,
                                  headers={"User-Agent": "AerieOS", "Accept": accept, **auth,
                                           **({"Content-Type": ctype} if payload is not None else {})})


def _send(opener, req, name, kind, upload, reasons, gone=None):
    """One request sent to the forge called `name`, and its JSON answered, {}
    for an empty body. A GET the forge has nothing at answers gone(), or None
    without one. Any other refusal raises Refused with the forge's name and
    its own reason, the first of the `reasons` keys its answer carries."""
    try:
        # Ten minutes for an upload, thirty seconds for anything else: a
        # host that stopped answering held a page's lookup that long.
        with opener(req, timeout=600 if upload else 30) as r:
            raw = r.read(2_000_000)
            return json.loads(raw) if raw.strip() else {}
    except urllib.error.HTTPError as e:
        if e.code == 404 and req.get_method() == "GET":
            return gone() if gone else None
        try:
            j = json.loads(e.read(20000)) or {}
            why = str(next((j[k] for k in reasons if j.get(k)), "")) if isinstance(j, dict) else ""
        except (ValueError, OSError):
            why = ""
        if e.code in (401, 403):
            raise Refused(f"{name} refused the token for releases: it needs {_NEEDS[kind]} "
                          "on this repository" + (f" ({why})" if why else "")) from e
        raise Refused(f"{name} answered {e.code}" + (f": {why}" if why else "")) from e
    except (urllib.error.URLError, OSError) as e:
        raise Refused(f"could not reach {name}: {e}") from e


# The container packages of a repository's owner, an organization's or the
# signed-in account's: what a withdrawn release's build pushed.
_PACKAGES = re.compile(re.escape(API) + r"/(?:(?:orgs|users)/[A-Za-z0-9-]+|user)/packages(?:[/?].*)?")
# Tags an image keeps beside its release's version and is still that
# release's alone: the commit's, as docker/metadata-action writes it.
_OWN_IMAGE_TAG = re.compile(r"sha-[0-9a-f]{7,40}")


def _gh_images_drop(repo, token, tag):
    """The container images the build of `tag` pushed, deleted with its
    release: the version of each container package GitHub links to
    `repo` whose tags are the release's version (the tag, or the tag without
    its v) and nothing but commit tags beside it. One that also carries a
    tag people follow (dev, latest, main) is left, said. {images: [the
    image:version deleted], images_left: why} with only what applies."""
    owner = repo.split("/", 1)[0]
    version = tag[1:] if tag[:1] == "v" and tag[1:2].isdigit() else tag
    out, left = [], []
    try:
        base = f"{API}/orgs/{owner}"
        pkgs = _req("GET", f"{base}/packages?package_type=container&per_page=100", token)
        if pkgs is None:
            base = f"{API}/users/{owner}"
            pkgs = _req("GET", f"{base}/packages?package_type=container&per_page=100", token)
        for pkg in pkgs if isinstance(pkgs, list) else []:
            if str((pkg.get("repository") or {}).get("full_name") or "").lower() != repo.lower():
                continue
            name = str(pkg.get("name") or "")
            at = f"{base}/packages/container/{urllib.parse.quote(name, safe='')}"
            vers = _req("GET", f"{at}/versions?per_page=100", token)
            for v in vers if isinstance(vers, list) else []:
                tags = list(((v.get("metadata") or {}).get("container") or {}).get("tags") or [])
                if version not in tags and tag not in tags:
                    continue
                more = [t for t in tags if t not in (version, tag) and not _OWN_IMAGE_TAG.fullmatch(t)]
                if more:
                    left.append(f"{name} is also tagged {', '.join(more)}")
                    continue
                # An owner that is a person deletes through its own path.
                gone = at if base.startswith(f"{API}/orgs/") else \
                    f"{API}/user/packages/container/{urllib.parse.quote(name, safe='')}"
                _req("DELETE", f"{gone}/versions/{int(v['id'])}", token)
                out.append(f"ghcr.io/{owner.lower()}/{name}:{version}")
    except Refused:
        left.append("the token may not delete packages")
    return {**({"images": out} if out else {}), **({"images_left": "; ".join(left)} if left else {})}


def _req(method, url, token, body=None, data=None, ctype="application/json"):
    """One call to GitHub, at its API or its upload host and nowhere else.
    The token goes in a header a redirect does not carry on, since an
    asset's download is answered with one to another host."""
    if not (url.startswith(API + "/repos/") or url.startswith(UPLOADS + "/repos/") or _PACKAGES.fullmatch(url)):
        raise Refused("not an address this asks GitHub at")
    req = _request(method, url, "application/vnd.github+json", {}, body, data, ctype)
    req.add_unredirected_header("Authorization", f"Bearer {token}")

    def gone():
        # A draft release is never found by its tag (GitHub's rule), and
        # every release starts a draft: looked for
        # among the listed ones, which a token that may see drafts lists.
        m = _BY_TAG.fullmatch(url)
        return _draft_by_tag(m.group(1), urllib.parse.unquote(m.group(2)), token) if m else None
    # The host is one of the two literals above, checked; the path is the repo's.
    return _send(urllib.request.urlopen, req, "GitHub", "github", data is not None, ("message",), gone)  # nosemgrep: python.lang.security.audit.dynamic-urllib-use-detected.dynamic-urllib-use-detected


def publish(project, tag, version, sha, comp="", pre=False):
    """The forge's release for `tag`, made if it is not there:
    {url, made, assets, skipped, forge} or {error, forge}. A project whose CI
    makes its releases says so with .release-files: its release is CI's draft,
    which a person publishes, so nothing is published here ahead of it.
    `pre` marks it a pre-release, never the latest: its notes are its
    own changelog section, which notes finds by its version."""
    if not comp and (WORKSPACE / project / ".release-files").is_file():
        return {"url": "", "made": False, "assets": [], "skipped": [], "forge": "CI",
                "note": "CI makes this release as a draft: read it and publish it from the Artifacts view's Drafts"}
    try:
        h = _find(project)
    except _NoForge as e:
        if e.token:
            why = f"the controller has no {e.name} token for this space, so the tag is its release"
            _keep(project, tag, "", why, e.name)
        else:
            why = (f"{project} is on {e.name}, which has no release this can make, so the tag is its release"
                   if e.name else f"{project} is not on GitHub, Gitea or GitLab, so the tag is its release")
        return {"error": why, "forge": e.name}
    where = WORKSPACE / project / comp if comp else WORKSPACE / project
    try:
        made = h.publish(project, tag, version, sha, where, f"{comp + ' ' if comp else ''}{version}", pre)
    except Refused as e:
        _keep(project, tag, "", str(e), h.name)
        return {"error": str(e), "forge": h.name}
    _keep(project, tag, made["url"], "", h.name)
    return made | {"forge": h.name}


def _body(project, where, version, tag, repo, names):
    """A new release's notes, the project's name and the version where it
    has written none, with the table of the files called `names` over them."""
    body = notes(where, version, tag, repo) or f"{_shown(project)} {version}"
    return with_files_table(project, body, names, version, tag, repo, where)


def _github(repo, token, project, tag, version, sha, where, title, pre=False):
    """GitHub's release by its tag, made if it is not there, and each build
    uploaded to it. The table names the builds GitHub will take."""
    base = f"{API}/repos/{repo}/releases"
    have = _req("GET", f"{base}/tags/{urllib.parse.quote(tag, safe="")}", token)
    if have:
        return {"url": have.get("html_url") or "", "made": False, "assets": [], "skipped": []}
    body = _body(project, where, version, tag, repo,
                 [f.name for f in assets(project, sha, version) if f.stat().st_size <= ASSET_MAX])
    rel = _req("POST", base, token, {"tag_name": tag, "name": title,
                                     "body": body, "draft": False, "prerelease": bool(pre),
                                     **({"make_latest": "false"} if pre else {})})
    up, skipped = [], []
    for f in assets(project, sha, version):
        size = f.stat().st_size
        if size > ASSET_MAX:
            skipped.append(f"{f.name} is {size // 1_000_000} MB, over GitHub's limit")
            continue
        url = f"{UPLOADS}/repos/{repo}/releases/{int(rel['id'])}/assets?name={urllib.parse.quote(f.name)}"
        try:
            _req("POST", url, token, data=f.read_bytes(), ctype="application/octet-stream")
            up.append(f.name)
        except Refused as e:
            skipped.append(f"{f.name}: {e}")
    return {"url": rel.get("html_url") or "", "made": True, "assets": up, "skipped": skipped}


# ---- Gitea and GitLab ---------------------------------------------------

def _remote(project):
    """{scheme, host, path} of the project's forge: the push record its link
    wrote, else the tree's origin. None when it has neither."""
    rec = cilogs.push_record(project) if cilogs.push_record else None
    if isinstance(rec, dict) and rec.get("repo") and rec.get("host"):
        return {"scheme": "", "host": str(rec["host"]), "path": str(rec["repo"]).removesuffix(".git")}
    try:
        cfg = cilogs.read_config(WORKSPACE / project / ".git") if cilogs.read_config else {}
    except Exception:  # noqa: BLE001 (an unreadable config is no remote)
        cfg = {}
    url = ((cfg.get("remote.origin.url") or [""])[-1]) if isinstance(cfg, dict) else ""
    got = forges.parse(url) if url else None
    return got if got and got.get("path") else None


def _own_token(project, host):
    """(token, scheme) from the project's stored credential line when it was
    written for this host, else ("", ""). The scheme is the line's: a token
    stored for http://host:3000 is the address that host answers on."""
    import gitcreds                                         # noqa: PLC0415
    line = gitcreds.read_line(project) if gitcreds.STATE else ""
    m = re.match(r"(https?)://[^:@/]*:([^@/]+)@([A-Za-z0-9.:%-]+)$", line)
    if not m:
        return "", ""
    stored = urllib.parse.unquote(m.group(3)).lower()
    want = host.lower()
    if stored != want and stored.split(":")[0] != want.split(":")[0]:
        return "", ""
    return urllib.parse.unquote(m.group(2)), m.group(1)


class _Forge:
    """One forge's API root and token. Asks nothing outside that root, and
    keeps the token home on a redirect (forges._OPENER)."""

    def __init__(self, base, entry, token):
        self.base, self.entry, self.token = base, entry, token

    def ask(self, method, path, body=None, data=None, ctype="application/json"):
        url = self.base + path
        name, kind = self.entry["name"], self.entry["kind"]
        if not path.startswith("/") or not url.lower().startswith(("https://", "http://")):
            raise Refused(f"not an address this asks {name} at")
        req = _request(method, url, "application/json", forges._auth(kind, self.token), body, data, ctype)
        # The root is forges.api_base()'s, from a host its URL pattern
        # matched and a scheme of http or https, checked above.
        return _send(forges._OPENER.open, req, name, kind, data is not None, ("message", "error"))  # nosemgrep: python.lang.security.audit.dynamic-urllib-use-detected.dynamic-urllib-use-detected


# ---- the forge at hand ---------------------------------------------------------
# One driver a kind of forge: what publish, edit, remove and withdraw ask of
# it, each in that forge's own addresses. A driver is made from the forge's
# name and a ctx, the two _handle() answers after the kind.

class _NoForge(Exception):
    """The project has no forge to ask a release of. `name` is the forge it
    is on, "" when that is none this knows; `token` says the forge is one of
    the three and only its token is missing."""

    def __init__(self, name, token=False):
        super().__init__(name)
        self.name, self.token = name, token


class _Driver:
    """What every forge answers alike unless its driver says otherwise."""

    def __init__(self, name, ctx):
        self.name, self.ctx = name, ctx

    def attached(self, rel):
        """The files a release as read holds."""
        return rel.get("assets") or []

    def swept(self, project, tag):
        """What a withdrawn release left behind and this took away, for
        withdraw's answer."""
        return {}


class _GitHub(_Driver):
    """GitHub, asked with _req: its ctx is (owner/name, token)."""
    kind = "github"

    def __init__(self, name, ctx):
        super().__init__(name, ctx)
        self.repo, self.token = ctx

    def call(self, method, url):
        return _req(method, url, self.token)

    def publish(self, project, tag, version, sha, where, title, pre):
        return _github(self.repo, self.token, project, tag, version, sha, where, title, pre)

    def raw(self, sha, rel):
        """The address of the committed file `rel` as commit `sha` has it."""
        return f"https://github.com/{self.repo}/raw/{sha}/{rel}"

    def edit(self, project, tag, notes, files):
        return _github_edit(project, self.repo, self.token, tag, notes, files)

    def files_on(self, tag):
        """(release url, {file name: (id, size, release id)}) of the release
        for `tag`."""
        rel = _req("GET", f"{API}/repos/{self.repo}/releases/tags/{urllib.parse.quote(tag, safe='')}", self.token)
        if not rel:
            raise NoRelease(f"there is no release for {tag} on GitHub")
        return rel.get("html_url") or "", {a.get("name"): (int(a["id"]), int(a.get("size") or 0), int(rel["id"]))
                                           for a in rel.get("assets") or []}

    def delete_asset(self, project, tag, name, got):
        """The file `name` off the release for `tag`: `got` is what
        files_on() said of it."""
        _req("DELETE", f"{API}/repos/{self.repo}/releases/assets/{got[0]}", self.token)

    def swept(self, project, tag):
        # The image the tag's build pushed, which deleting the release left
        # pullable by its version.
        return _gh_images_drop(self.repo, self.token, tag)

    def paths(self, tag):
        """The addresses call() takes for `tag`: {rel: the release by tag,
        ref: the tag read, unref: the tag deleted, by_id: a release by its
        id ("" where the tag names it)}."""
        t, base = urllib.parse.quote(tag, safe=""), f"{API}/repos/{self.repo}"
        # git/ref/ reads one ref exactly; git/refs/ would list every tag
        # the name begins (v0.9.0-dev.45 reading v0.9.0-dev.4500).
        return {"rel": f"{base}/releases/tags/{t}", "ref": f"{base}/git/ref/tags/{t}",
                "unref": f"{base}/git/refs/tags/{t}", "by_id": f"{base}/releases/"}


class _Gitea(_Driver):
    """Gitea, and the Forgejo and Codeberg that answer its API: its ctx is
    (the _Forge to ask, the remote)."""
    kind = "gitea"

    def __init__(self, name, ctx):
        super().__init__(name, ctx)
        self.f, self.at = ctx
        owner, _, repo = self.at["path"].partition("/")
        self.root = f"/repos/{urllib.parse.quote(owner)}/{urllib.parse.quote(repo)}"

    def call(self, method, path):
        return self.f.ask(method, path)

    def publish(self, project, tag, version, sha, where, title, pre):
        body = _body(project, where, version, tag, self.at["path"], [f.name for f in assets(project, sha, version)])
        return _gitea(self.f, self.at, project, tag, version, sha, title, body, pre)

    def raw(self, sha, rel):
        return f"{self.at['web']}/raw/commit/{sha}/{rel}"

    def edit(self, project, tag, notes, files):
        return _gitea_edit(self.f, self.at, project, tag, notes, files)

    def files_on(self, tag):
        rel = self.f.ask("GET", f"{self.root}/releases/tags/{urllib.parse.quote(tag, safe='')}")
        if not rel:
            raise NoRelease(f"there is no release for {tag} on {self.name}")
        return rel.get("html_url") or "", {a.get("name"): (int(a["id"]), int(a.get("size") or 0), int(rel["id"]))
                                           for a in rel.get("assets") or []}

    def delete_asset(self, project, tag, name, got):
        self.f.ask("DELETE", f"{self.root}/releases/{got[2]}/assets/{got[0]}")

    def paths(self, tag):
        t = urllib.parse.quote(tag, safe="")
        return {"rel": f"{self.root}/releases/tags/{t}", "ref": f"{self.root}/tags/{t}",
                "unref": f"{self.root}/tags/{t}", "by_id": f"{self.root}/releases/"}


class _GitLab(_Driver):
    """GitLab, which names a project by its whole path, holds links where
    the others hold files, and keeps the builds in its package registry: its
    ctx is (the _Forge to ask, the remote)."""
    kind = "gitlab"

    def __init__(self, name, ctx):
        super().__init__(name, ctx)
        self.f, self.at = ctx
        self.pid = urllib.parse.quote(self.at["path"], safe="")

    def call(self, method, path):
        return self.f.ask(method, path)

    def publish(self, project, tag, version, sha, where, title, pre):
        body = _body(project, where, version, tag, self.at["path"], [f.name for f in assets(project, sha, version)])
        return _gitlab(self.f, self.at, project, tag, version, sha, title, body)

    def raw(self, sha, rel):
        return f"{self.at['web']}/-/raw/{sha}/{rel}"

    def edit(self, project, tag, notes, files):
        return _gitlab_edit(self.f, self.at, project, tag, notes, files)

    def files_on(self, tag):
        rel = self.f.ask("GET", f"/projects/{self.pid}/releases/{urllib.parse.quote(tag, safe='')}")
        if not rel:
            raise NoRelease(f"there is no release for {tag} on GitLab")
        return ((rel.get("_links") or {}).get("self") or "",
                {x.get("name"): (int(x["id"]), 0, 0) for x in self.attached(rel)})

    def delete_asset(self, project, tag, name, got):
        self.f.ask("DELETE", f"/projects/{self.pid}/releases/{urllib.parse.quote(tag, safe='')}/assets/links/{got[0]}")
        # ...and the file the link served: the link gone, the
        # package registry still handed the build out.
        _gl_pkg_drop(self.f, self.pid, project, tag, name)

    def paths(self, tag):
        t = urllib.parse.quote(tag, safe="")
        return {"rel": f"/projects/{self.pid}/releases/{t}", "ref": f"/projects/{self.pid}/repository/tags/{t}",
                "unref": f"/projects/{self.pid}/repository/tags/{t}", "by_id": ""}

    def attached(self, rel):
        return (rel.get("assets") or {}).get("links") or []

    def swept(self, project, tag):
        # GitLab keeps a release's builds in its package registry, which
        # deleting the release leaves serving them.
        return {"packages": _gl_pkg_drop(self.f, self.pid, project, tag)}


_DRIVERS = {d.kind: d for d in (_GitHub, _Gitea, _GitLab)}


def _driver(kind, name, ctx):
    """The driver for what _handle() answered."""
    return _DRIVERS[kind](name, ctx)


def _find(project):
    """The driver for the project's forge, or raises _NoForge. GitHub is
    asked with the project's own token, else the shared one; Gitea and
    GitLab with the token the project's link stored, at the address it was
    stored for."""
    repo = cilogs.repo_of(project)
    if repo:
        token = cilogs._token(project)
        if not token:
            raise _NoForge("GitHub", token=True)
        return _driver("github", "GitHub", (repo, token))
    at = _remote(project)
    entry = forges.forge_of(at["host"]) if at else None
    if not at or not entry or entry["kind"] not in ("gitea", "gitlab"):
        raise _NoForge(entry["name"] if at and entry and entry["id"] != "git" else "")
    token, scheme = _own_token(project, at["host"])
    if not token:
        raise _NoForge(entry["name"], token=True)
    # The stored line's scheme is the one the host answers on; a remote that
    # is read without one is asked over https.
    api = forges.api_base(entry, at["host"], scheme or ("https" if at["scheme"] == "ssh" else at["scheme"]))
    web = f"{scheme or ('https' if at['scheme'] in ('ssh', '') else at['scheme'])}://{at['host']}/{at['path']}"
    return _driver(entry["kind"], entry["name"], (_Forge(api, entry, token), at | {"web": web}))


def _handle(project):
    """(kind, name, ctx) for the project's forge, or raises Refused: what a
    driver is made from, and what a caller outside this module holds."""
    try:
        h = _find(project)
    except _NoForge as e:
        raise Refused(f"the controller has no {e.name} token for this space" if e.token else
                      f"{project} is not on GitHub, Gitea or GitLab, so it has no release page") from e
    return h.kind, h.name, h.ctx


def _driver_of(project):
    """The driver for the project's forge, or raises Refused."""
    return _driver(*_handle(project))


def _gitea(f, at, project, tag, version, sha, title, body, pre=False):
    """Gitea's API is GitHub's shape: the release by its tag, made if it is
    not there, and each build attached to it as a multipart upload."""
    owner, _, repo = at["path"].partition("/")
    base = f"/repos/{urllib.parse.quote(owner)}/{urllib.parse.quote(repo)}/releases"
    have = f.ask("GET", f"{base}/tags/{urllib.parse.quote(tag, safe="")}")
    if have:
        return {"url": have.get("html_url") or "", "made": False, "assets": [], "skipped": []}
    # Gitea takes a pushed tag into its database on a queue, a moment after
    # the push: a release asked for at once is refused as "repo is empty"
    # or its tag not found (measured on 1.24, 5 Oct), so it is asked again
    # for a few seconds before that answer is believed.
    for wait in (1, 2, 3, 4, 0):
        try:
            rel = f.ask("POST", base, {"tag_name": tag, "name": title, "body": body,
                                       "draft": False, "prerelease": bool(pre)})
            break
        except Refused as e:
            if not wait or not re.search(r"answered (409|422|404)", str(e)):
                raise
            time.sleep(wait)
    up, skipped = [], []
    for p in assets(project, sha, version):
        size = p.stat().st_size
        if size > ASSET_MAX:
            skipped.append(f"{p.name} is {size // 1_000_000} MB, too big to attach")
            continue
        data, ctype = _multipart("attachment", p.name, p.read_bytes())
        try:
            f.ask("POST", f"{base}/{int(rel['id'])}/assets?name={urllib.parse.quote(p.name)}", data=data, ctype=ctype)
            up.append(p.name)
        except Refused as e:
            skipped.append(f"{p.name}: {e}")
    return {"url": rel.get("html_url") or "", "made": True, "assets": up, "skipped": skipped}


def _gitlab(f, at, project, tag, version, sha, title, body):
    """GitLab names a project by its whole path, encoded, and a release holds
    links rather than files: each build goes into the generic package
    registry under the version, and the release links to it there."""
    pid = urllib.parse.quote(at["path"], safe="")
    web = f"{f.base.split('/api/')[0]}/{at['path']}/-/releases/{urllib.parse.quote(tag, safe="")}"
    have = f.ask("GET", f"/projects/{pid}/releases/{urllib.parse.quote(tag, safe="")}")
    if have:
        return {"url": ((have.get("_links") or {}).get("self") or web), "made": False, "assets": [], "skipped": []}
    rel = f.ask("POST", f"/projects/{pid}/releases", {"tag_name": tag, "name": title, "description": body})
    # A package's name and version are GitLab's own charset; the project's
    # name and the version already are, and anything else becomes a dash.
    pkg = re.sub(r"[^A-Za-z0-9._-]", "-", project) or "builds"
    ver = re.sub(r"[^A-Za-z0-9._+-]", "-", version) or "0"
    up, skipped = [], []
    for p in assets(project, sha, version):
        size = p.stat().st_size
        if size > ASSET_MAX:
            skipped.append(f"{p.name} is {size // 1_000_000} MB, too big to attach")
            continue
        path = f"/projects/{pid}/packages/generic/{pkg}/{ver}/{urllib.parse.quote(p.name)}"
        try:
            f.ask("PUT", path, data=p.read_bytes(), ctype="application/octet-stream")
            f.ask("POST", f"/projects/{pid}/releases/{urllib.parse.quote(tag, safe="")}/assets/links",
                  {"name": p.name, "url": f.base + path, "link_type": "package"})
            up.append(p.name)
        except Refused as e:
            skipped.append(f"{p.name}: {e}")
    return {"url": ((rel.get("_links") or {}).get("self") or web), "made": True, "assets": up, "skipped": skipped}


def _multipart(field, name, data):
    """One file as multipart/form-data, which is how Gitea takes an asset."""
    boundary = "aerie" + os.urandom(12).hex()
    safe = name.replace('"', "_").replace("\r", "_").replace("\n", "_")
    head = (f"--{boundary}\r\nContent-Disposition: form-data; name=\"{field}\"; filename=\"{safe}\"\r\n"
            f"Content-Type: application/octet-stream\r\n\r\n").encode()
    return head + data + f"\r\n--{boundary}--\r\n".encode(), f"multipart/form-data; boundary={boundary}"


# ---- editing a published release ----------------------------------------

NOTES_MAX = 100_000
ATTACH_MAX = 20
ATTACHABLE = re.compile(r"\.(apk|aab|zip|xpi|tar\.gz|tgz|exe|msi|dmg|deb|rpm|AppImage|png|jpe?g|gif|webp|pdf|txt|sha256)$",
                        re.I)
TAG = re.compile(r"[A-Za-z0-9][A-Za-z0-9._/-]{0,99}")
ASSET_REF = re.compile(r"\(asset:([^)\s]+)\)")
FILE_REF = re.compile(r"\(file:([^)\s]+)\)")
SHOWABLE = re.compile(r"\.(png|jpe?g|gif|webp|svg)$", re.I)


def _tree_git(project, *args):
    try:
        return subprocess.run(["git", "-C", str(WORKSPACE / project), *args], capture_output=True,
                               text=True, timeout=10)
    except (OSError, subprocess.SubprocessError):
        return None


def edit_plan(project, tag, notes=None, attach=()):
    """What an edit of the release for `tag` would do, checked before
    anybody is asked: {tag, notes, files: [{path, name, size, signed}]} or
    {error}. A file is the project's own: a build in dist/, or a file its
    git tree tracks (a screenshot under docs/), inside the project and of a
    kind a release carries."""
    if not tag or not TAG.fullmatch(tag) or ".." in tag:
        return {"error": f"not a tag: {tag or '(none)'}"}
    r = _tree_git(project, "rev-parse", "--verify", "--quiet", f"refs/tags/{tag}")
    if r is None or r.returncode:
        return {"error": f"{tag} is not a tag here, so it has no release to edit"}
    if notes is not None:
        notes = str(notes).rstrip()
        if not notes.strip():
            return {"error": "the notes are empty: a release's notes are replaced whole, so say them all"}
        if len(notes) > NOTES_MAX:
            return {"error": f"the notes are {len(notes)} characters; a release takes {NOTES_MAX} at most"}
    attach = [str(a) for a in (attach or [])]
    # `(file:PATH)` shows a committed picture from the repository at the
    # pushed commit that has it, so a screenshot is on the page without
    # being one of the release's downloads, which (asset:NAME) makes it.
    root = (WORKSPACE / project).resolve()
    pinned = {}
    for rel in sorted({m.group(1) for m in FILE_REF.finditer(notes or "")}):
        p = (root / rel).resolve()
        if rel.startswith("/") or not p.is_relative_to(root) or not p.is_file() or not SHOWABLE.search(p.name):
            return {"error": f"file:{rel} is not a picture in {project}"}
        r = _tree_git(project, "log", "-1", "--format=%H", "HEAD", "--", rel)
        sha = r.stdout.strip() if r is not None and not r.returncode else ""
        same = _tree_git(project, "diff", "--quiet", "HEAD", "--", rel)
        if not sha or same is None or same.returncode:
            return {"error": f"file:{rel} is not committed as it is now: commit it and push, so the page "
                             "shows what the history has"}
        on = _tree_git(project, "branch", "-r", "--contains", sha)
        if on is None or on.returncode or not on.stdout.strip():
            return {"error": f"file:{rel} is in commit {sha[:8]}, which is not pushed: push it first, or the "
                             "picture is a broken link on the release"}
        pinned[rel] = sha
    if notes is None and not attach:
        return {"error": "say what changes: --notes FILE, --attach FILE, or both"}
    if len(attach) > ATTACH_MAX:
        return {"error": f"{len(attach)} files; one edit attaches {ATTACH_MAX} at most"}
    files, names = [], set()
    for rel in attach:
        p = (root / rel).resolve()
        if rel.startswith("/") or not p.is_relative_to(root) or not p.is_file():
            return {"error": f"{rel} is not a file in {project}"}
        rel = str(p.relative_to(root))
        if not ATTACHABLE.search(p.name):
            return {"error": f"{p.name} is not a kind of file a release carries here: a build, an image, "
                             "a PDF, a text file or a checksum"}
        in_dist = rel.startswith("dist/")
        if in_dist and "-dirty" in p.name:
            return {"error": f"{p.name} was built from uncommitted changes, so it is not what any tag names"}
        if not in_dist:
            t = _tree_git(project, "ls-files", "--error-unmatch", "--", rel)
            if t is None or t.returncode:
                return {"error": f"{rel} is not committed: a release carries a build in dist/ or a file "
                                 "the space's history has, so what it shows can be found again"}
            # ...as the history has it: a tracked file changed since was
            # attached as it is now, which no commit holds.
            same = _tree_git(project, "diff", "--quiet", "HEAD", "--", rel)
            if same is None or same.returncode:
                return {"error": f"{rel} has changes not committed: commit them first, so what the release "
                                 "carries is what the history has"}
        size = p.stat().st_size
        if size > ASSET_MAX:
            return {"error": f"{p.name} is {size // 1_000_000} MB, too big to attach"}
        if p.name in names:
            return {"error": f"two files are named {p.name}; a release keeps one of each name"}
        names.add(p.name)
        files.append({"path": rel, "name": p.name, "size": size, "signed": "-signed" in p.name})
    return {"tag": tag, "notes": notes, "files": files, "pinned": pinned}


def _with_assets(notes, urls):
    """`(asset:NAME)` in the notes, the address of the file of that name on
    the release: how a screenshot attached by the same edit is shown."""
    return ASSET_REF.sub(lambda m: f"({urls[m.group(1)]})" if urls.get(m.group(1)) else m.group(0), notes)


def _with_files(notes, pinned, raw):
    """`(file:PATH)` in the notes, the forge's address of that committed
    file at the commit edit_plan() pinned it to."""
    return FILE_REF.sub(lambda m: f"({raw(pinned[m.group(1)], m.group(1))})" if m.group(1) in pinned else m.group(0),
                        notes)


def edit(project, plan):
    """Make the edit edit_plan() checked: {url, notes, attached, replaced,
    skipped, forge} or {error, forge}."""
    tag, notes, files = plan["tag"], plan.get("notes"), plan.get("files") or []
    pinned = plan.get("pinned") or {}
    try:
        h = _find(project)
    except _NoForge as e:
        if e.token:
            return {"error": f"the controller has no {e.name} token for this space", "forge": e.name}
        return {"error": f"{project} is not on GitHub, Gitea or GitLab, so it has no release page to edit",
                "forge": ""}
    if notes is not None:
        notes = _with_files(notes, pinned, h.raw)
    try:
        return h.edit(project, tag, notes, files) | {"forge": h.name}
    except Refused as e:
        return {"error": str(e), "forge": h.name}


def _said(rel, notes, urls, attached, replaced, skipped):
    if notes is not None:
        missing = sorted({m.group(1) for m in ASSET_REF.finditer(notes)} - {n for n, u in urls.items() if u})
        skipped += [f"the notes name asset:{n}, which is not on the release" for n in missing]
    return {"url": rel, "notes": notes is not None, "attached": attached, "replaced": replaced, "skipped": skipped}


# The name a replacing file is uploaded under before the one it replaces is
# taken off and it is named for it.
_TMP = "replacing-"


def _ctype(name):
    return mimetypes.guess_type(name)[0] or "application/octet-stream"


def _github_edit(project, repo, token, tag, notes, files):
    base = f"{API}/repos/{repo}/releases"
    rel = _req("GET", f"{base}/tags/{urllib.parse.quote(tag, safe="")}", token)
    if not rel:
        raise Refused(f"there is no release for {tag} on GitHub to edit: aerie version release makes one")
    have = {a.get("name"): a for a in rel.get("assets") or []}
    urls = {n: a.get("browser_download_url") or "" for n, a in have.items()}
    attached, replaced, skipped = [], [], []
    for x in files:
        p = WORKSPACE / project / x["path"]
        try:
            # The new file first, under a name of its own, and only then the
            # old one gone and the new one named for it: deleted
            # first, a failed upload left the release without the file.
            old = have.get(x["name"])
            got = _req("POST", f"{UPLOADS}/repos/{repo}/releases/{int(rel['id'])}/assets"
                               f"?name={urllib.parse.quote(_TMP + x['name'] if old else x['name'])}", token,
                       data=p.read_bytes(), ctype=_ctype(x["name"]))
            if old:
                _req("DELETE", f"{base}/assets/{int(old['id'])}", token)
                got = _req("PATCH", f"{base}/assets/{int(got['id'])}", token, {"name": x["name"]})
                replaced.append(x["name"])
            urls[x["name"]] = (got or {}).get("browser_download_url") or ""
            attached.append(x["name"])
        except (Refused, OSError, KeyError, TypeError, ValueError) as e:
            skipped.append(f"{x['name']}: {e}")
    if notes is not None:
        # Its draft said back with the notes, or a draft is published.
        _req("PATCH", f"{base}/{int(rel['id'])}", token, {"body": _with_assets(notes, urls), "draft": rel.get("draft") is True,
                                                          "tag_name": tag})
    return _said(rel.get("html_url") or "", notes, urls, attached, replaced, skipped)


def _gitea_edit(f, at, project, tag, notes, files):
    owner, _, repo = at["path"].partition("/")
    base = f"/repos/{urllib.parse.quote(owner)}/{urllib.parse.quote(repo)}/releases"
    rel = f.ask("GET", f"{base}/tags/{urllib.parse.quote(tag, safe="")}")
    if not rel:
        raise Refused(f"there is no release for {tag} on {f.entry['name']} to edit: aerie version release makes one")
    have = {a.get("name"): a for a in rel.get("assets") or []}
    urls = {n: a.get("browser_download_url") or "" for n, a in have.items()}
    attached, replaced, skipped = [], [], []
    for x in files:
        try:
            # As on GitHub: the new file in, then the old one out.
            old = have.get(x["name"])
            up = _TMP + x["name"] if old else x["name"]
            data, ctype = _multipart("attachment", up, (WORKSPACE / project / x["path"]).read_bytes())
            got = f.ask("POST", f"{base}/{int(rel['id'])}/assets?name={urllib.parse.quote(up)}",
                        data=data, ctype=ctype)
            if old:
                f.ask("DELETE", f"{base}/{int(rel['id'])}/assets/{int(old['id'])}")
                got = f.ask("PATCH", f"{base}/{int(rel['id'])}/assets/{int(got['id'])}", {"name": x["name"]})
                replaced.append(x["name"])
            urls[x["name"]] = (got or {}).get("browser_download_url") or ""
            attached.append(x["name"])
        except (Refused, OSError, KeyError, TypeError, ValueError) as e:
            skipped.append(f"{x['name']}: {e}")
    if notes is not None:
        f.ask("PATCH", f"{base}/{int(rel['id'])}", {"body": _with_assets(notes, urls)})
    return _said(rel.get("html_url") or "", notes, urls, attached, replaced, skipped)


def _gitlab_edit(f, at, project, tag, notes, files):
    pid = urllib.parse.quote(at["path"], safe="")
    t = urllib.parse.quote(tag, safe="")
    rel = f.ask("GET", f"/projects/{pid}/releases/{t}")
    if not rel:
        raise Refused(f"there is no release for {tag} on GitLab to edit: aerie version release makes one")
    links = {x.get("name"): x for x in ((rel.get("assets") or {}).get("links") or [])}
    urls = {n: x.get("url") or "" for n, x in links.items()}
    pkg, ver = _gl_pkg(project, tag)
    attached, replaced, skipped = [], [], []
    for x in files:
        path = f"/projects/{pid}/packages/generic/{pkg}/{ver}/{urllib.parse.quote(x['name'])}"
        try:
            # The package first: a failed upload leaves the link and
            # what it serves as they were. A link already at this address
            # serves the new file now and stays.
            f.ask("PUT", path, data=(WORKSPACE / project / x["path"]).read_bytes(), ctype="application/octet-stream")
            old = links.get(x["name"])
            if old and old.get("url") == f.base + path:
                replaced.append(x["name"])
            else:
                if old:
                    f.ask("DELETE", f"/projects/{pid}/releases/{t}/assets/links/{int(old['id'])}")
                    replaced.append(x["name"])
                f.ask("POST", f"/projects/{pid}/releases/{t}/assets/links",
                      {"name": x["name"], "url": f.base + path,
                       "link_type": "image" if re.search(r"\.(png|jpe?g|gif|webp)$", x["name"], re.I) else "package"})
            urls[x["name"]] = f.base + path
            attached.append(x["name"])
        except (Refused, OSError) as e:
            skipped.append(f"{x['name']}: {e}")
    if notes is not None:
        f.ask("PUT", f"/projects/{pid}/releases/{t}", {"description": _with_assets(notes, urls)})
    web = f"{f.base.split('/api/')[0]}/{at['path']}/-/releases/{t}"
    return _said(((rel.get("_links") or {}).get("self") or web), notes, urls, attached, replaced, skipped)


def edit_said(r):
    """One line for what an edit did, for the session and the outcome."""
    if r.get("error"):
        return f"no edit on {r.get('forge') or 'the forge'}: {r['error']}"
    parts = (["the notes replaced"] if r.get("notes") else []) + (
        [f"attached {', '.join(r['attached'])}"] if r.get("attached") else []) + (
        [f"replacing {', '.join(r['replaced'])}"] if r.get("replaced") else [])
    return (f"edited on {r.get('forge')}: {'; '.join(parts) or 'nothing changed'}"
            + (f"; not done: {'; '.join(r['skipped'])}" if r.get("skipped") else "") + f"; {r.get('url')}")


# ---- taking a file off a published release ---------------------------------------
# Its own ask, never part of an edit: a removal is the one change here that
# takes something away from the people downloading, so it is asked as itself.
# The release is read first, so the ask names files
# that are really there, with their sizes.

def _files_on(kind, name, ctx, tag):
    """(release url, {file name: (id, size, release id)}) of the release for
    `tag`, for a caller holding what _handle() answered."""
    return _driver(kind, name, ctx).files_on(tag)


def remove_plan(project, tag, names):
    """The files a removal would take off the release for `tag`, read from
    the forge before anybody is asked: {tag, forge, files: [{name, size}]}
    or {error}."""
    if not tag or not TAG.fullmatch(tag) or ".." in tag:
        return {"error": f"not a tag: {tag or '(none)'}"}
    names = [str(n) for n in names or []]
    if not names:
        return {"error": "say which files come off: --remove NAME, once for each"}
    if len(names) > ATTACH_MAX or len(set(names)) != len(names):
        return {"error": f"name each file once, {ATTACH_MAX} at most"}
    try:
        h = _driver_of(project)
        _url, have = h.files_on(tag)
    except Refused as e:
        return {"error": str(e)}
    missing = [n for n in names if n not in have]
    if missing:
        return {"error": f"the {tag} release on {h.name} has no {', '.join(missing)}; it has "
                         + (", ".join(sorted(have)) or "no files")}
    return {"tag": tag, "forge": h.name, "files": [{"name": n, "size": have[n][1]} for n in names]}


def remove(project, plan):
    """Take the planned files off the release, each looked up again by name
    (an id read at the ask may be stale by the Allow): {url, removed,
    skipped, forge} or {error, forge}."""
    try:
        h = _driver_of(project)
        url, have = h.files_on(plan["tag"])
    except Refused as e:
        return {"error": str(e), "forge": ""}
    removed, skipped = [], []
    for x in plan.get("files") or []:
        got = have.get(x["name"])
        if not got:
            skipped.append(f"{x['name']} was already gone")
            continue
        try:
            h.delete_asset(project, plan["tag"], x["name"], got)
            removed.append(x["name"])
        except Refused as e:
            skipped.append(f"{x['name']}: {e}")
    return {"url": url, "removed": removed, "skipped": skipped, "forge": h.name}


def remove_said(r):
    if r.get("error"):
        return f"nothing removed: {r['error']}"
    return (f"removed from the release on {r.get('forge')}: {', '.join(r.get('removed') or []) or 'nothing'}"
            + (f"; not done: {'; '.join(r['skipped'])}" if r.get("skipped") else "") + f"; {r.get('url')}")


def _gl_pkg(project, tag):
    """The generic package a release's builds are kept in on GitLab: the
    project's name and the tag's version, in GitLab's charset."""
    pkg = re.sub(r"[^A-Za-z0-9._-]", "-", project) or "builds"
    ver = re.sub(r"[^A-Za-z0-9._+-]", "-", re.sub(r"^(?:.*-)?v(?=\d)", "", tag)) or "0"
    return pkg, ver


def _gl_pkg_drop(f, pid, project, tag, name=None):
    """The release's package deleted, or its file called `name`; how many."""
    pkg, ver = _gl_pkg(project, tag)
    got = f.ask("GET", f"/projects/{pid}/packages?package_type=generic&package_name={urllib.parse.quote(pkg, safe='')}"
                       f"&package_version={urllib.parse.quote(ver, safe='')}")
    n = 0
    for pk in got if isinstance(got, list) else []:
        if pk.get("name") != pkg or pk.get("version") != ver:
            continue
        if name is None:
            f.ask("DELETE", f"/projects/{pid}/packages/{int(pk['id'])}")
            n += 1
            continue
        files = f.ask("GET", f"/projects/{pid}/packages/{int(pk['id'])}/package_files")
        for pf in files if isinstance(files, list) else []:
            if pf.get("file_name") == name:
                f.ask("DELETE", f"/projects/{pid}/packages/{int(pk['id'])}/package_files/{int(pf['id'])}")
                n += 1
    return n


# ---- withdrawing a release, its tag with it --------------------------------
# A release taken back takes its tag too: the forge keeps a
# tag while its release exists, a session may not push a deletion, and the
# 0.9.0 dev release left three to be deleted by hand, one of them a tag with
# no release. Always a person's answer, whatever the
# dial: it is the one change here nothing undoes.


# ---- drafts --------------------------------------------
# Every release CI makes starts a draft, seen by the repository's own people
# alone, so its notes are read before anybody else sees it. GitHub's alone:
# Gitea and GitLab releases made here are published as they are made.

def drafts(project):
    """The project's draft releases on GitHub, newest first: {drafts:
    [{tag, prerelease, notes, url}], forge} or {error}. [] on another forge."""
    try:
        kind, name, ctx = _handle(project)
    except Refused as e:
        return {"error": str(e)}
    if kind != "github":
        return {"drafts": [], "forge": name}
    repo, token = ctx
    try:
        rows = _req("GET", f"{API}/repos/{repo}/releases?per_page=30", token) or []
    except Refused as e:
        return {"error": str(e)}
    out = []
    for r in rows:
        if not (isinstance(r, dict) and r.get("draft")):
            continue
        # One GitHub moved to a name of its own (untagged-ID: its tag field
        # lost on the git host's form) is listed under the tag it is
        # titled for, which is the one it is published under from here.
        tag = str(r.get("tag_name") or "")
        if tag.startswith("untagged-") and TAG.fullmatch(str(r.get("name") or "")):
            tag = str(r["name"])
        if not TAG.fullmatch(tag):
            continue
        names = [str(a.get("name") or "") for a in r.get("assets") or [] if isinstance(a, dict)]
        out.append({"tag": tag, "prerelease": r.get("prerelease") is True, "notes": str(r.get("body") or ""),
                    "url": str(r.get("html_url") or ""), "holds": holds(repo, token, tag, str(r.get("body") or "")),
                    "undescribed": undescribed(project, names, tag=tag)})
    return {"forge": name, "drafts": out}


# The notes CI writes when the changelog has nothing for a version (the
# tag's workflow and tools/release-attach.sh), which say nothing a person
# reading the release can use: 4818 went out with them (2 Nov).
_PLACEHOLDER = re.compile(r".+: see CHANGELOG\.md\.?")


def placeholder_notes(notes):
    """Whether a release's notes say nothing of the release: empty, or
    ending in CI's placeholder line. The controller's own signing lines and
    the list of downloads at the top are not what a release carries."""
    lines = [ln.strip() for ln in str(notes or "").splitlines() if ln.strip() and not ln.startswith("Signed by AerieOS:")]
    return not lines or bool(_PLACEHOLDER.fullmatch(lines[-1]))


def is_pre(tag):
    """Whether a tag is a pre-release's: anything after its version."""
    return bool(re.search(r"(?:^|-)v\d+\.\d+\.\d+-[A-Za-z]", tag))


def holds(repo, token, tag, notes):
    """What keeps a draft from being published, each a sentence saying what
    puts it right; [] when nothing does. The files it must
    carry are the caller's to check (releasefiles), which reads the list.

    The tag: a release published while its tag is not on the git host is
    given one by GitHub, on the newest commit of the default branch, which
    is no commit the release was built from (as when the form's own tag
    field is emptied). The notes: CI's placeholder says nothing."""
    out = []
    try:
        ref = _req("GET", f"{API}/repos/{repo}/git/ref/tags/{urllib.parse.quote(tag, safe='')}", token)
    except Refused as e:
        ref = {"unknown": str(e)}
    if not ref:
        out.append({"what": "tag", "why": f"the tag {tag} is not on GitHub, and a release published without its tag is "
                                          "given one on the default branch's newest commit, which nothing was built from: "
                                          "push the tag first (releasing again finishes it), then publish"})
    elif ref.get("unknown"):
        out.append({"what": "tag", "why": f"whether the tag {tag} is on GitHub could not be read ({ref['unknown']})"})
    if placeholder_notes(notes):
        out.append({"what": "notes", "why": "the notes are the placeholder CI writes when the changelog has nothing for this "
                                            "version: write what the release carries in the box, then publish"})
    return out


def _draft(project, tag):
    """(repo, token, release) of the draft for `tag`, or raises Refused."""
    if not tag or not TAG.fullmatch(tag) or ".." in tag:
        raise Refused(f"not a tag: {tag or '(none)'}")
    kind, name, ctx = _handle(project)
    if kind != "github":
        raise Refused(f"{name} releases are published as they are made: there is no draft to publish")
    repo, token = ctx
    rel = _req("GET", f"{API}/repos/{repo}/releases/tags/{urllib.parse.quote(tag, safe='')}", token)
    if not rel:
        raise NoRelease(f"there is no release for {tag} on GitHub")
    if not rel.get("draft"):
        raise Refused(f"{tag} is published already")
    return repo, token, rel


def draft_notes(project, tag, notes):
    """A draft's notes replaced, as read and corrected before it is
    published: {ok, tag} or {error}."""
    try:
        repo, token, rel = _draft(project, tag)
        _req("PATCH", f"{API}/repos/{repo}/releases/{int(rel['id'])}", token,
             {"body": str(notes)[:120000], "draft": True, "tag_name": tag})
    except Refused as e:
        return {"error": str(e)}
    return {"ok": True, "tag": tag}


def publish_draft(project, tag, notes=None, missing=()):
    """A draft published, its notes first replaced when given: {ok, tag,
    url} or {error}. Refused while `missing` names a file the release must
    carry (releasefiles), so nothing goes out half built; while its tag is
    not on the git host; and while its notes, as they would go out, are
    CI's placeholder (holds). Published under its own tag, a pre-release as
    one and never the latest, whatever the draft was left marked as."""
    if missing:
        return {"error": f"{tag} is not whole yet: {', '.join(missing)} still missing. CI may still be building it"}
    try:
        repo, token, rel = _draft(project, tag)
        held = holds(repo, token, tag, str(notes) if notes is not None else str(rel.get("body") or ""))
        if held:
            return {"error": f"{tag} is not published: " + "; ".join(h["why"] for h in held), "holds": held}
        pre = is_pre(tag)
        said = str(notes) if notes is not None else str(rel.get("body") or "")
        names = [str(a.get("name") or "") for a in rel.get("assets") or [] if isinstance(a, dict)]
        told = with_files_table(project, said, names, tag=tag, repo=repo)
        body = {"draft": False, "tag_name": tag, "prerelease": pre, "make_latest": "false" if pre else "legacy",
                **({"body": told[:120000]} if notes is not None or told != said else {})}
        out = _req("PATCH", f"{API}/repos/{repo}/releases/{int(rel['id'])}", token, body) or {}
    except Refused as e:
        return {"error": str(e)}
    return {"ok": True, "tag": tag, "url": str(out.get("html_url") or rel.get("html_url") or "")}


def withdraw_plan(project, tag):
    """What withdrawing `tag` would take away, read from the forge before
    anybody is asked: {tag, forge, release, tagged, prerelease, files, url}
    or {error}. A tag whose release is already gone is withdrawn alone."""
    if not tag or not TAG.fullmatch(tag) or ".." in tag:
        return {"error": f"not a tag: {tag or '(none)'}"}
    try:
        h = _driver_of(project)
        p = h.paths(tag)
        rel, ref = h.call("GET", p["rel"]), h.call("GET", p["ref"])
    except Refused as e:
        return {"error": str(e)}
    if not rel and not ref:
        return {"error": f"{h.name} has neither a release nor a tag called {tag}"}
    rel = rel or {}
    return {"tag": tag, "forge": h.name, "release": bool(rel), "tagged": bool(ref),
            "prerelease": bool(rel.get("prerelease")), "files": len(h.attached(rel)),
            "url": rel.get("html_url") or (rel.get("_links") or {}).get("self") or ""}


def withdraw(project, tag):
    """Delete the release for `tag`, then the tag, each looked up again at
    the Allow: {forge, tag, release, tagged} saying what went, or
    {error, forge}."""
    try:
        h = _driver_of(project)
    except Refused as e:
        return {"error": str(e), "forge": ""}
    p, out = h.paths(tag), {"forge": h.name, "tag": tag, "release": False, "tagged": False}
    try:
        rel = h.call("GET", p["rel"])
        if rel:
            h.call("DELETE", p["by_id"] + str(int(rel["id"])) if p["by_id"] else p["rel"])
            out["release"] = True
        out.update(h.swept(project, tag))
        if h.call("GET", p["ref"]):
            h.call("DELETE", p["unref"])
            out["tagged"] = True
    except Refused as e:
        return {**out, "error": str(e)}
    return out


def withdraw_said(r):
    imgs = r.get("images") or []
    went = [w for w, on in (("its release", r.get("release")), ("its tag", r.get("tagged")),
                            ("its image" if len(imgs) == 1 else f"its {len(imgs)} images", imgs)) if on]
    if r.get("error"):
        return (f"{r.get('tag') or 'the release'} not withdrawn" + (" (" + " and ".join(went) + " already deleted)" if went else "")
                + f": {r['error']}")
    kept = f", its image kept since {r['images_left']}" if r.get("images_left") else ""
    return ((f"{r.get('tag')} withdrawn from {r.get('forge')}: " + ", ".join(went[:-1]) + (" and " if went[1:] else "")
             + went[-1] + " deleted") if went else f"{r.get('tag')} had nothing left on {r.get('forge')} to withdraw") + kept
