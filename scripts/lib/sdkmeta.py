#!/usr/bin/env python3
"""Read config/toolchains.json on bb's behalf.

The recipes are data now: every URL, branch, flag, archive layout and
environment variable a toolchain needs lives in that file, and this is the part
that reads them out: fields, argument vectors with their placeholders filled
in, and the version each upstream currently offers.

It sits beside bb rather than inside it because the reading is JSON work and
the resolvers are not alike. Each upstream announces its current release in a
different shape (a bare line of text, a redirect to a tag, a JSON index of
every build it has ever made), and that is a paragraph of python apiece
against a page of shell.

Placeholders, substituted into url templates and argv:

    {dir}      where the toolchain is being installed
    {version}  whatever the version resolver returned
    {script}   the installer this recipe downloaded, for kind "script"

Usage (all output is plain, and empty means "not set"):

    sdkmeta.py names
    sdkmeta.py field  NAME source.strip
    sdkmeta.py argv   NAME source.run  dir=/sdk/go version=go1.27.0
    sdkmeta.py resolve NAME                 -> version <TAB> url
    sdkmeta.py offer   NAME                 -> version <TAB> sha256, for a pinned row
    sdkmeta.py size    NAME                 -> bytes of the download, if knowable
    sdkmeta.py files   NAME DIR             -> writes the files the row carries into DIR
"""
import glob
import hashlib
import json
import os
import re
import subprocess
import sys
import time
import urllib.parse
import urllib.request

# Semgrep flags this import (use-defused-xml) and it is a fair thing to ask
# about, so the answer lives here rather than being re-derived every scan: the
# only XML parsed is Google's SDK repository index, fetched over TLS from
# dl.google.com. ElementTree does not resolve external entities at all, so XXE
# is not reachable; what remains is entity-expansion blowup, which requires
# Google's own CDN to serve a hostile index. Adding defusedxml would put a
# dependency in an otherwise stdlib-only tree to defend against that. If this
# ever parses XML from a source the catalog does not control, revisit it.
# The index comes from Google's CDN over TLS, and ElementTree resolves no
# external entities (see above). The rule's full id, which is what a
# suppression has to name to be honored.
import xml.etree.ElementTree as ET  # nosemgrep: python.lang.security.use-defused-xml.use-defused-xml

HERE = os.path.dirname(os.path.abspath(__file__))
# The file a node's bundle may carry beside the shipped catalog: the shipped
# rows with the vetted catalog's newer ones in their places, which the
# controller adds as a member of its own (workspace.CATALOG_ROWS).
CATALOG_ROWS = "toolchains.catalog.json"


def catalog_file(shipped):
    """The catalog to read where `shipped` is config/toolchains.json: the
    file beside it with the vetted catalog's newer rows where a bundle
    carries one, the shipped file otherwise. The shipped file is never
    rewritten for those rows: a release signs it as it is."""
    newer = os.path.join(os.path.dirname(shipped), CATALOG_ROWS)
    return newer if os.path.isfile(newer) else shipped


# BB_TOOLCHAINS_JSON points this at another catalog. It exists so the install
# machinery can be exercised against a fake one: five recipes fetched from
# file:// URLs prove the fetching, unpacking, environment and verify steps
# without spending gigabytes or touching the real toolchain store root.
CATALOG = os.environ.get("BB_TOOLCHAINS_JSON") or catalog_file(os.path.join(
    HERE, "..", "..", "config", "toolchains.json"))
TIMEOUT = 30
# Some of these hosts hand a bare urllib a different answer, or none: go.dev
# serves the plain version file happily, github's release redirect does not
# mind, but it costs nothing to look like something that reads web pages.
UA = {"User-Agent": "builderbot-sdk/1 (+https://github.com/aquilaelabs/aerieos)"}


def die(msg):
    print(f"sdkmeta: {msg}", file=sys.stderr)
    raise SystemExit(2)


def _catalog():
    """The whole file. Toolchains are most of it, but not all: see
    android_images, which is data about a thing that is not a toolchain."""
    try:
        with open(CATALOG) as f:
            return json.load(f)
    except (OSError, ValueError) as e:
        die(f"cannot read {CATALOG}: {e}")


def packs_at(path):
    """The tool packs a person added (R77), the rows of the toolpacks.json
    beside the catalog at `path`: the controller writes it into the bundle,
    so a node installs a pack by name exactly as it does a shipped toolchain.
    [] when none were added."""
    here = os.path.dirname(os.path.abspath(path))
    try:
        with open(os.path.join(here, "toolpacks.json")) as f:
            rows = json.load(f).get("toolchains") or []
    except (OSError, ValueError, AttributeError):
        return []
    rows = [p for p in rows if isinstance(p, dict) and p.get("name")]
    # A pack made on the controller travels as a git bundle beside this file
    # (config/toolpacks/NAME.bundle): its address made whole here, so the
    # pinned fetch reads it like any repository.
    for p in rows:
        src = p.get("source") if isinstance(p.get("source"), dict) else {}
        url = str(src.get("url") or "")
        if url.startswith("bundle:"):
            rel = url[len("bundle:"):]
            ok = rel.startswith("toolpacks/") and rel.endswith(".bundle") and "/" not in rel[len("toolpacks/"):] \
                and ".." not in rel
            src["url"] = os.path.join(here, rel) if ok else ""
    return rows


def catalog_at(path):
    """Every toolchain the catalog at `path` lists, the packs beside it
    after the shipped ones under names of their own; [] when it cannot be
    read. What bb's readers in sdk.sh take, so none of them reads the file
    alone and misses the packs."""
    try:
        with open(path) as f:
            shipped = json.load(f)["toolchains"]
    except (OSError, ValueError, KeyError, TypeError):
        return []
    names = {p.get("name") for p in shipped if isinstance(p, dict)}
    return shipped + [p for p in packs_at(path) if p["name"] not in names]


def catalog():
    try:
        shipped = _catalog()["toolchains"]
    except KeyError as e:
        die(f"cannot read {CATALOG}: {e}")
    names = {p.get("name") for p in shipped}
    return shipped + [p for p in packs_at(CATALOG) if p["name"] not in names]


def toolchain(name):
    for p in catalog():
        if p.get("name") == name:
            return p
    die(f"no toolchain named {name!r} in the catalog")


def dig(obj, path):
    """A dotted path into nested dicts and lists, or None.

    A number walks into a list (source.then.0.run is the first follow-up
    step), which is not decoration: without it the .NET recipe's workload step
    resolved to nothing and quietly did not run, leaving a plain SDK behind
    where a MAUI one was asked for.
    """
    for part in path.split("."):
        if isinstance(obj, list):
            if not part.isdigit() or int(part) >= len(obj):
                return None
            obj = obj[int(part)]
        elif isinstance(obj, dict) and part in obj:
            obj = obj[part]
        else:
            return None
    return obj


def fill(text, subs):
    for k, v in subs.items():
        text = text.replace("{" + k + "}", v)
    return text


_ARCH = {"x86_64": "amd64", "amd64": "amd64", "aarch64": "arm64", "arm64": "arm64"}


def this_platform():
    """"<os>/<arch>" for the machine running this, the way the catalog's
    `platforms` spells it: linux/amd64, darwin/arm64."""
    import platform as _p
    return f"{_p.system().lower()}/{_ARCH.get(_p.machine().lower(), _p.machine().lower())}"


# The platform to answer for in place of this machine's, as a row keys one
# ("linux/arm64", "linux-musl/amd64", "darwin/*"). Empty at every install:
# the tool that proposes pins (tools/pins.py) sets it to each platform a row
# names in turn, so one machine learns every platform's file.
AS_PLATFORM = ""


def for_platform(value):
    """A recipe field that may differ per platform: a plain value, or a
    dict keyed "<os>/<arch>" with "<os>/*" as a fallback. A recipe whose
    download is one URL on Linux and another on a Mac writes the dict;
    everything else stays a string."""
    if not isinstance(value, dict):
        return value
    plat = AS_PLATFORM.replace("linux-musl/", "linux/", 1) or this_platform()
    # A musl system (Alpine) cannot load a glibc build, so a recipe that
    # publishes a musl one says so under linux-musl/<arch>, tried first.
    musl = "linux-musl/" + plat.partition("/")[2]
    if musl in value and (AS_PLATFORM.startswith("linux-musl/") if AS_PLATFORM else glob.glob("/lib/ld-musl-*.so.1")):
        return value[musl]
    if plat in value:
        return value[plat]
    o = plat.partition("/")[0]
    if f"{o}/*" in value:
        return value[f"{o}/*"]
    return ""


def on_platform(plat):
    """Whether this machine is the platform a declared download names:
    "<os>/<arch>", or "<os>/*" for any architecture of a system, matched as
    for_platform matches a key. One that names none is for every machine."""
    return True if not plat else bool(for_platform({str(plat): True}))


def declared_mine(rows):
    """The rows of a declared list that are this machine's. A musl system
    takes its own build of a file where a row names one (linux-musl/<arch>),
    and the glibc row for the same `to` is then another machine's, as
    for_platform tries a musl key first: two such rows may share a `to`
    (packformat.platforms_meet), and only one of them is ever fetched."""
    def musl(f):
        return str(f.get("platform") or "").startswith("linux-musl/")
    mine = [f for f in rows if on_platform(f.get("platform"))]
    own = {f.get("to") for f in mine if musl(f)}
    return [f for f in mine if musl(f) or f.get("to") not in own]


def declared(tc):
    """The downloads an entry declares that are this machine's
    (source.fetch, a pack's install.fetch): each {url, to} with the sha256
    it is held to, or `signed` where its publisher's signature holds it."""
    rows = (tc.get("source") or {}).get("fetch")
    return declared_mine([f for f in rows if isinstance(f, dict) and f.get("url")]) if isinstance(rows, list) else []


def declared_address(f, key="url"):
    """A declared download's address as it is fetched, or with `key` "sig"
    its signature's: {version} filled with the version the entry itself
    says the download is, with nobody asked. How a newer one is found
    (`track`, `found`) is beside it for the tool that proposes a pin, and is
    not read here."""
    signed = f.get("signed") if isinstance(f.get("signed"), dict) else {}
    text = str((signed.get("sig") if key == "sig" else f.get("url")) or "")
    return fill(text, {"version": f["version"]}) if isinstance(f.get("version"), str) else text


# A file a row carries into its directory: a path inside it, never one of
# AerieOS's marks or of git's.
CARRIED = re.compile(r"^(?!/)(?!.*(?:^|/)\.\.?(?:/|$))[A-Za-z0-9._/-]{1,200}$")


def write_files(tc, d):
    """The small files a row carries (source.files: {path: text}), written
    into its directory `d` before anything of the row runs: what a package
    manager installs by, its requirements with their hashes or its lock,
    which a pack keeps in its repository and a shipped row has nowhere else
    to keep. Returns the paths written. A path that would land outside the
    directory, or on a mark of AerieOS's or git's, writes nothing."""
    files = (tc.get("source") or {}).get("files")
    if not isinstance(files, dict) or not files:
        return []
    root = os.path.realpath(d)
    todo = []
    for rel, text in files.items():
        ok = isinstance(rel, str) and isinstance(text, str) and CARRIED.fullmatch(rel) \
            and not any(part == ".git" or part.startswith(".bb-") for part in rel.split("/"))
        path = os.path.realpath(os.path.join(root, rel)) if ok else ""
        if not ok or not path.startswith(root + os.sep):
            die(f"{tc['name']}: {str(rel)[:80]!r} is no file inside its directory: nothing of source.files was written")
        todo.append((rel, path, text))
    for _rel, path, text in todo:
        os.makedirs(os.path.dirname(path), exist_ok=True)
        with open(path, "w", encoding="utf-8") as f:
            f.write(text)
    return [rel for rel, _path, _text in todo]


# What separates the fields of a line of declared_plan: a character no
# address, file name or sentence holds, and not white space, so the shell's
# read keeps a field that is empty.
PLAN_SEP = "\x1f"


def held_by_entry(tc):
    """Whether a row's own download is held to something its entry carries:
    a pin, or its publisher's signature under keys the entry names (the
    download's own, or the one over the checksum file it is read from).
    Such a row has said what arrives, so what it runs afterwards runs with
    no network unless it says online; a row whose download is checked
    against its own origin, or not at all, has said nothing of the kind."""
    src = tc.get("source") or {}
    ck = src.get("checksum") if isinstance(src.get("checksum"), dict) else {}
    signed = ck.get("signed") if isinstance(ck.get("signed"), dict) else {}
    how = ck.get("from")
    return src.get("kind") in ("tarball", "script") and (
        how == "pin" or (how == "signature" and bool(ck.get("sig") and ck.get("keys")))
        or (how == "file" and bool(signed.get("sig") and signed.get("keys"))))


def declared_plan(tc):
    """What an entry declares of its own install, as the lines sdk.sh reads
    in one call (sdk_declared), or [] for an entry that declares nothing:
    no download, neither offline nor online, and its own download held to
    nothing it carries (held_by_entry). The first line says what its steps
    run with, then a line a download, each field after a separator:

        net    cut | online, the entry's sentence
        fetch  url, sha256, to, signed.sig, signed.keys   (this machine's)
        skip   to, platform                               (another's)
    """
    src = tc.get("source") or {}
    rows = [f for f in src.get("fetch") or [] if isinstance(f, dict) and f.get("url")] if isinstance(src.get("fetch"), list) else []
    online = " ".join(str(src.get("online") or "").split())
    if not (rows or online or src.get("offline") or held_by_entry(tc)):
        return []

    def said(*fields):
        return PLAN_SEP.join(" ".join(str(v or "").replace(PLAN_SEP, "").split()) for v in fields)

    out = [said("net", "online" if online else "cut", online)]
    mine = {id(f) for f in declared_mine(rows)}
    for f in rows:
        signed = f.get("signed") if isinstance(f.get("signed"), dict) else {}
        if id(f) in mine:
            out.append(said("fetch", declared_address(f), f.get("sha256"), f.get("to"), declared_address(f, "sig"), signed.get("keys")))
        else:
            out.append(said("skip", f.get("to"), f.get("platform")))
    return out


# Documents fetched while resolving, kept briefly on disk.
#
# A check asks about thirteen toolchains in thirteen separate processes, and
# several of them want the same file: sdkmanager's package index answers for
# the emulator, the NDK and CMake alike, which is four hundred kilobytes
# fetched three times over. Anything upstream publishes as a catalog changes
# on the order of days, so a few minutes of reuse costs nothing in accuracy
# and takes a check from 2.7MB to about half that.
#
# It is a cache and not a store: /tmp is cleared on every container start, and
# a missing or stale entry simply means fetching again.
#
# /tmp is every account's, and what is read back from here is taken as what
# an upstream published (an index a version is resolved from, a checksum
# document). So the directory is this account's own: made 0700, and used
# only while it is a real directory this account owns that nobody else may
# read or write (cache_dir). One that is anything else, made first by
# another account, is not used at all, and every document is fetched.
CACHE_DIR = os.path.join(os.environ.get("TMPDIR", "/tmp"), f"bb-sdk-cache-{os.getuid()}")
CACHE_TTL = int(os.environ.get("BB_SDK_CACHE_TTL", "900"))


def cache_dir():
    """CACHE_DIR where it is this account's own (made 0700 when it is not
    there; a real directory, its owner this process, no bit for anybody
    else), or "" where it is not: then nothing is kept and nothing read."""
    import stat  # noqa: PLC0415
    try:
        try:
            os.mkdir(CACHE_DIR, 0o700)
        except FileExistsError:
            pass
        st = os.lstat(CACHE_DIR)
    except OSError:
        return ""
    if not stat.S_ISDIR(st.st_mode) or st.st_uid != os.geteuid() or st.st_mode & 0o077:
        return ""
    return CACHE_DIR


def _cached(key, produce):
    """produce()'s bytes, remembered for CACHE_TTL by key in this account's
    own directory (cache_dir), or produced every time where it has none."""
    kept = cache_dir() if CACHE_TTL > 0 else ""
    if not kept:
        return produce()
    path = os.path.join(kept, hashlib.sha256(key.encode()).hexdigest()[:32])
    try:
        if time.time() - os.path.getmtime(path) < CACHE_TTL:
            with open(path, "rb") as f:
                return f.read()
    except OSError:
        pass
    body = produce()
    try:
        # Written aside and moved, so a reader never sees half a document.
        tmp = f"{path}.{os.getpid()}"
        with open(tmp, "wb") as f:
            f.write(body)
        os.replace(tmp, path)
    except OSError:
        pass
    return body


def _web(url):
    """`url`, or a ValueError for any scheme but http(s). Every URL here
    comes from the shipped catalog or from a release API answering for one,
    so this never fires in practice; it is what makes that a fact urlopen can
    rely on rather than one a reader has to trace, since urlopen would as
    happily open file:// and hand back a file on this machine."""
    if not str(url).lower().startswith(("https://", "http://")):
        raise ValueError(f"not a web address: {str(url)[:60]}")
    return url


def get(url, decode=True):
    def fetch():
        req = urllib.request.Request(_web(url), headers=UA)
        with urllib.request.urlopen(req, timeout=TIMEOUT) as r:  # nosemgrep: python.lang.security.audit.dynamic-urllib-use-detected.dynamic-urllib-use-detected
            return r.read()

    body = _cached("GET " + url, fetch)
    return body.decode("utf-8", "replace") if decode else body


def final_url(url):
    """Where a redirect lands, without fetching the body.

    Used for the /releases/latest trick: the tag is in the URL, and asking the
    API for it instead would be rate-limited by IP for anonymous callers.
    """
    req = urllib.request.Request(_web(url), headers=UA, method="HEAD")
    with urllib.request.urlopen(req, timeout=TIMEOUT) as r:  # nosemgrep: python.lang.security.audit.dynamic-urllib-use-detected.dynamic-urllib-use-detected
        return r.url


# What a pinned download is said to have been held to: in the install's log,
# in .bb-verified and on the Installed page.
PIN_SAID = "the pin its entry carries"


def pin_of(tc):
    """The pin a row's source.checksum carries, or None for a row with none:
    {"from": "pin", "version": the version it is, "sha256": the digest of
    the exact file, or one per platform keyed as source.url is}. The row is
    held by the signed catalog or the signed release, so the file is held to
    something its own origin cannot change."""
    spec = (tc.get("source") or {}).get("checksum")
    return spec if isinstance(spec, dict) and spec.get("from") == "pin" else None


def pinned_digest(tc):
    """The sha256 a row's pin names for this machine, or "" where it names
    none for it or the row has no pin."""
    pin = pin_of(tc)
    got = for_platform(pin.get("sha256")) if pin else ""
    got = got.strip().lower() if isinstance(got, str) else ""
    return got if re.fullmatch(r"[0-9a-f]{64}", got) else ""


def offered(tc):
    """What a row its entry pins has on offer, (version, sha256 for this
    machine), or None for a row whose version is whatever its vendor offers
    at the moment: the pinned version and digest, or a git source's commit.
    `aerie toolchains check` compares an installed copy with this, so a
    pinned row is never measured against a vendor's latest."""
    pin = pin_of(tc)
    if pin is not None:
        return str(pin.get("version") or ""), pinned_digest(tc)
    src = tc.get("source") or {}
    if src.get("kind") == "git" and src.get("commit"):
        return str(src["commit"])[:8], ""
    return None


def resolve(tc):
    """(version, url) for a toolchain: what its pin names where its entry
    carries one, with nobody asked; otherwise what upstream currently
    offers.

    Either may come back empty: a recipe that needs no version does not have a
    resolver, and one whose resolver supplies the download URL itself has no
    template to fill in.
    """
    src = tc.get("source") or {}
    version, url = "", ""

    pin = pin_of(tc)
    if pin is not None:
        # Pinned: the version its entry carries and the address made from
        # it. The resolver stays in the row as how a newer version is
        # found, which is not an install's question.
        version = str(pin.get("version") or "")
        if not pinned_digest(tc):
            die(f"{tc['name']}: the row offers no pinned download for {this_platform()}")
    else:
        version, url = newest(tc)

    if src.get("url"):
        url = fill(for_platform(src["url"]) or "", {"version": version})
        if not url:
            die(f"{tc['name']}: no download for {this_platform()}; the recipe names "
                f"{', '.join(sorted(src['url']))}")
    return version, url


def _vkey(text):
    """A version as something to order by: its runs of digits as numbers,
    what is between them as text."""
    return [(0, int(p)) if p.isdigit() else (1, p) for p in re.findall(r"\d+|\D+", str(text))]


def git_refs(url, *refs):
    """What `git ls-remote` says of a repository's refs, as text: one
    "<commit>\\t<ref>" a line. No object is fetched."""
    if not str(url).lower().startswith("https://"):
        raise ValueError(f"not a repository's https address: {str(url)[:60]}")
    p = subprocess.run(["git", "ls-remote", url, *refs], capture_output=True, text=True, timeout=120, check=False,
                       env=dict(os.environ, GIT_TERMINAL_PROMPT="0"))
    if p.returncode:
        raise ValueError(f"git could not list {url}: {(p.stderr or '').strip()[-200:]}")
    return p.stdout


def git_newest(tc, spec=None):
    """(name, commit) for a repository: the tag or the branch its
    source.track names and the commit it is at now, read with ls-remote.

        git-tag     the newest tag `match` matches, by version order
        git-branch  the head of `branch`
    """
    src = tc.get("source") or {}
    spec = src.get("track") if spec is None else spec
    kind = (spec or {}).get("resolver")
    if kind == "git-branch":
        ref = f"refs/heads/{spec['branch']}"
        for line in git_refs(src["url"], ref).splitlines():
            commit, _, name = line.partition("\t")
            if name == ref:
                return spec["branch"], commit
        die(f"{tc['name']}: {src['url']} has no branch {spec['branch']}")
    if kind == "git-tag":
        tags = {}
        for line in git_refs(src["url"], "refs/tags/*").splitlines():
            commit, _, name = line.partition("\t")
            name = name.removeprefix("refs/tags/")
            # An annotated tag is listed twice: the tag itself, and under
            # ^{} the commit it names, which is the one to pin.
            if name.endswith("^{}"):
                tags[name[:-3]] = commit
            else:
                tags.setdefault(name, commit)
        want = [t for t in tags if re.search(spec.get("match") or "", t)]
        if not want:
            die(f"{tc['name']}: {src['url']} has no tag matching {spec.get('match')!r}")
        tag = max(want, key=_vkey)
        return tag, tags[tag]
    die(f"{tc['name']}: unknown resolver for a repository {kind!r}")


def _github_release(tc, spec):
    """(tag, url) from a repository's releases as GitHub's API lists them,
    newest first, for a resolver that says more than the repository: the
    first whose tag `tag` matches and that has been out `settled` days (a
    publisher that keeps only some of its builds for good), and, with
    `asset`, the address of the file whose name that pattern matches, one
    pattern per platform. With `asset` alone the release is the one GitHub
    calls latest, asked for by itself: a publisher with a thousand files a
    release has a list of releases too large to ask for."""
    import calendar  # noqa: PLC0415
    repo = spec["repo"]
    before = time.time() - 86400 * float(spec.get("settled") or 0)
    if spec.get("tag") or spec.get("settled"):
        listed = json.loads(get(f"https://api.github.com/repos/{repo}/releases?per_page=100"))
    else:
        listed = [json.loads(get(f"https://api.github.com/repos/{repo}/releases/latest"))]
    for rel in listed:
        tag = str(rel.get("tag_name") or "")
        if rel.get("draft") or rel.get("prerelease") or (spec.get("tag") and not re.search(spec["tag"], tag)):
            continue
        if spec.get("settled"):
            try:
                out = calendar.timegm(time.strptime(str(rel.get("published_at")), "%Y-%m-%dT%H:%M:%SZ"))
            except ValueError:
                continue
            if out > before:
                continue
        if not spec.get("asset"):
            return tag, ""
        want = for_platform(spec["asset"])
        if not want:
            die(f"{tc['name']}: its resolver names no asset for {AS_PLATFORM or this_platform()}")
        for a in rel.get("assets") or []:
            if re.search(want, str(a.get("name") or "")):
                return tag, str(a.get("browser_download_url") or "")
        die(f"{tc['name']}: {repo}'s release {tag} has no asset matching {want!r}")
    die(f"{tc['name']}: {repo} lists no release its resolver takes")


def trimmed(tag, spec):
    """A tag as the version it names: with the resolver's `trim_prefix`
    and `trim_suffix` taken off (v1.2.3 for the 1.2.3 in a file's name)."""
    for k, cut in (("trim_prefix", str.removeprefix), ("trim_suffix", str.removesuffix)):
        if spec.get(k):
            tag = cut(tag, spec[k])
    return tag


def newest(tc, spec=None):
    """(version, url) as a version resolver finds them now: what upstream
    currently offers. `spec` is the row's source.version when left out (a
    declared download's track otherwise); url is the address where the
    resolver supplies it itself, and "" where the entry's own template is
    filled. Asked by an install of a row that pins nothing, and by the tool
    that proposes a newer pin; never by an install of a pinned row."""
    spec = ((tc.get("source") or {}).get("version") or {}) if spec is None else spec
    kind = spec.get("resolver")
    version, url = "", ""

    if kind == "text":
        # A file whose whole content is the current version. go.dev serves one.
        version = get(spec["url"]).strip().splitlines()[0].strip()
        want = spec.get("expect_prefix")
        if want and not version.startswith(want):
            die(f"{tc['name']}: expected a version starting {want!r}, got {version!r}")

    elif kind == "github-release":
        if any(spec.get(k) for k in ("tag", "settled", "asset")):
            tag, url = _github_release(tc, spec)
        else:
            # The release GitHub calls latest, read off where its page
            # redirects to: a tag may be written with a slash, of which
            # the last part is taken, and with a plus sign.
            tag = final_url(f"https://github.com/{spec['repo']}/releases/latest").rstrip("/")
            tag = urllib.parse.unquote(tag.rsplit("/", 1)[-1])
        version = trimmed(tag, spec)
        if spec.get("numeric") and not version.replace(".", "").isdigit():
            die(f"{tc['name']}: could not read a version out of the tag {tag!r}")

    elif kind == "zig-index":
        # An index of every build, newest release first and "master" among
        # them: the nightly is not what anybody asked to install.
        index = json.loads(get(spec["url"]))
        version = next(k for k in index if k != "master")
        name = for_platform(spec["asset"])
        asset = index[version].get(name) or {}
        url = asset.get("tarball") or ""
        if not url:
            die(f"{tc['name']}: the index offers no {name or 'build for this platform'} build for {version}")

    elif kind == "node-index":
        # nodejs.org's own index, newest release first. LTS only: a node
        # building somebody's project should be on the line upstream still
        # supports, not on the current release that moves under it. The
        # entry's version already carries its "v", which the download path
        # and the filename both want.
        index = json.loads(get(spec["url"]))
        version = next((r["version"] for r in index if r.get("lts")), "")
        if not version:
            die(f"{tc['name']}: the index offers no LTS release")

    elif kind == "match":
        # A document its publisher serves and a pattern: the version is
        # what the pattern's first group matches first (a release file's
        # `version = '1.2.3'` line, the newest release an API names).
        m = re.search(spec["match"], get(spec["url"]), re.M)
        if not m:
            die(f"{tc['name']}: {spec['url']} holds nothing its resolver's pattern matches")
        version = m.group(1) if m.groups() else m.group(0)

    elif kind:
        die(f"{tc['name']}: unknown version resolver {kind!r}")

    return version, url


# ---- what a download should be (R137) ---------------------------------------
# A row's source.checksum says where its publisher states what the file is:
#   github-asset   GitHub's own digest of a release asset (the release API)
#   file           a checksum file beside it (url: a template; {url}, {name}, {version})
#   go-json        go.dev's download index
#   zig-index      ziglang.org's index, the tarball's shasum
#   json           a JSON answer and a path into it (adoptium's API)
#   android-repo   Google's repository listing, the archive's sha1
#   zsync          an AppImage's .zsync, its SHA-1 line
#   none           nothing to check against, and why (said on the install)
# Each of those is read from the file's own origin at the moment of the
# install, so it holds nothing against that origin. One is the row's own
# (pack format 5):
#   pin            the sha256 of the exact file, and the version it is
# Each answers (algorithm, hex digest, where it came from).
HEX = re.compile(r"^[0-9a-fA-F]{40}$|^[0-9a-fA-F]{64}$|^[0-9a-fA-F]{128}$")
ALGOS = {40: "sha1", 64: "sha256", 128: "sha512"}


def _algo(hexd):
    hexd = str(hexd or "").strip().lower().removeprefix("sha256:")
    if not HEX.match(hexd):
        die(f"what the publisher gave is no checksum: {hexd[:80]!r}")
    return ALGOS[len(hexd)], hexd


def _name_of(url):
    return urllib.parse.unquote(urllib.parse.urlsplit(url).path.rsplit("/", 1)[-1])


KEYS_DIR = os.path.join(HERE, "..", "..", "config", "release-keys")


KEY_NAME = re.compile(r"^[A-Za-z0-9][A-Za-z0-9._-]{0,63}$")


def keyring(name, tc=None, into=None):
    """The publisher's keys `name`, as a keyring file gpgv reads: dearmored
    every time it is asked for, into `into`, the caller's own directory for
    this one check (one made here, 0700, when none is given, which the
    caller removes). Never a file kept from another run: a keyring found
    lying at a known name is whoever made it first's, and a signature would
    verify under it. One rule for every entry: the armored key the entry
    `tc` carries under that name (source.keyring, a pack's install.keyring)
    where it carries one, which wins, so a publisher's key that changes is
    a catalog commit; otherwise the file of that name AerieOS ships
    (config/release-keys). Never the machine's own keyring, which anybody
    with a shell may have added to."""
    name = os.path.basename(str(name or ""))
    carried = ((tc or {}).get("source") or {}).get("keyring")
    armored = carried.get(name) if isinstance(carried, dict) else None
    if isinstance(armored, str) and armored.strip():
        if not KEY_NAME.fullmatch(name):
            die(f"{name!r} is no name for a publisher's keys")
        armored = armored.encode()
    else:
        src = os.path.join(KEYS_DIR, name)
        if not KEY_NAME.fullmatch(name) or not os.path.isfile(src):
            die(f"no release keys named {name!r} beside the catalog" + (", and its entry carries none" if tc else ""))
        with open(src, "rb") as f:
            armored = f.read()
    import tempfile  # noqa: PLC0415
    p = subprocess.run(["gpg", "--batch", "--dearmor"], input=armored, capture_output=True, check=False)
    if p.returncode or not p.stdout:
        die(f"gpg could not read the release keys {name}: {p.stderr.decode(errors='replace')[:200]}")
    if into is None:
        into = tempfile.mkdtemp(prefix="bb-keys.")
    # A file of its own in the directory, made here and nowhere before.
    fd, out = tempfile.mkstemp(prefix="keys-", suffix=".gpg", dir=into)
    with os.fdopen(fd, "wb") as f:
        f.write(p.stdout)
    return out


def signed_by(data, sig, keys, tc=None):
    """Who of the publisher's keys `keys` signed `data` (bytes) with the
    detached signature `sig` (bytes), or a refusal. `tc` is the entry the
    keys are resolved for (keyring)."""
    import tempfile  # noqa: PLC0415
    with tempfile.TemporaryDirectory() as d:
        dp, sp = os.path.join(d, "data"), os.path.join(d, "data.sig")
        with open(dp, "wb") as f:
            f.write(data)
        with open(sp, "wb") as f:
            f.write(sig)
        try:
            p = subprocess.run(["gpgv", "--keyring", keyring(keys, tc, d), sp, dp], capture_output=True, text=True,
                               timeout=60, check=False)
        except FileNotFoundError:
            die("there is no gpgv here to check the publisher's signature with")
    if p.returncode:
        die(f"the publisher's signature does not hold: {(p.stderr or p.stdout).strip()[:300]}")
    m = re.search(r'Good signature from "([^"]+)"', p.stderr)
    return m.group(1) if m else "a key of the publisher's"


def checksum(tc, url, version, spec=None):
    """(algorithm, hex digest, where it came from) for the file `url`
    downloads, or ("none", "", why) for a row whose publisher states nothing
    to check it against. A row that names no source is refused. `spec` is
    the row's source.checksum when left out; the tool that proposes a pin
    hands it the pin's `found`, how the publisher states the digest."""
    spec = (tc.get("source") or {}).get("checksum") if spec is None else spec
    if not isinstance(spec, dict) or not spec.get("from"):
        die(f"{tc['name']}: the catalog says nowhere to check its download against")
    how, name = spec["from"], _name_of(url)
    subs = {"version": version, "url": url, "name": name, "base": url.rsplit("/", 1)[0]}
    if how == "none":
        return "none", "", spec.get("why") or "its publisher states no checksum"
    if how == "pin":
        digest = pinned_digest(tc)
        if not digest:
            die(f"{tc['name']}: the row offers no pinned download for {this_platform()}")
        return "sha256", digest, PIN_SAID
    if how == "github-asset":
        m = re.match(r"https://github\.com/([^/]+/[^/]+)/releases/(?:latest/download|download/([^/]+))/([^/?#]+)$", url)
        if not m:
            die(f"{tc['name']}: {url} is not a GitHub release asset's address")
        repo, tag, asset = m.groups()
        rel = json.loads(get(f"https://api.github.com/repos/{repo}/releases/" + (f"tags/{tag}" if tag else "latest")))
        for a in rel.get("assets") or []:
            if str(a.get("name", "")).lower() == asset.lower():
                if not str(a.get("digest") or "").startswith("sha256:"):
                    die(f"{tc['name']}: GitHub states no digest for {asset} in {repo} {rel.get('tag_name', '')}")
                return (*_algo(a["digest"]), f"GitHub's digest for {asset} in {repo} {rel.get('tag_name', '')}")
        die(f"{tc['name']}: {repo}'s release {rel.get('tag_name', '')} has no asset {asset}")
    if how == "signature":
        # The publisher signs the download itself (Swift): the shell checks
        # it once the file is here, with this signature and these keys.
        return "gpg", fill(spec["sig"], subs), os.path.basename(spec["keys"])
    if how == "file":
        src = fill(for_platform(spec["url"]) or "", subs)
        raw = get(src, decode=False)
        text = raw.decode("utf-8", "replace")
        signed = spec.get("signed")
        if signed:
            # The checksum file believed only once the publisher's signature
            # over its exact bytes holds (Node's SHASUMS256.txt), so a mirror
            # cannot hand out a file and a list that agree with each other.
            who = signed_by(raw, get(fill(signed["sig"], subs), decode=False), signed["keys"], tc)
            src = f"{src}, signed by {who}"
        lines = [ln.split() for ln in text.splitlines() if ln.strip()]
        for parts in lines:
            if len(parts) >= 2 and parts[-1].lstrip("*").removeprefix("./") == name:
                return (*_algo(parts[0]), src)
        if len(lines) == 1 and len(lines[0]) in (1, 2):
            return (*_algo(lines[0][0]), src)
        die(f"{tc['name']}: {src} names no checksum for {name}")
    if how == "go-json":
        for rel in json.loads(get("https://go.dev/dl/?mode=json&include=all")):
            for f in rel.get("files") or []:
                if f.get("filename") == name:
                    return (*_algo(f.get("sha256")), "go.dev's download index")
        die(f"{tc['name']}: go.dev's index lists no {name}")
    if how == "zig-index":
        for ver, builds in json.loads(get(spec.get("url") or "https://ziglang.org/download/index.json")).items():
            for b in (builds.values() if isinstance(builds, dict) else []):
                if isinstance(b, dict) and b.get("tarball") == url:
                    return (*_algo(b.get("shasum")), f"ziglang.org's index ({ver})")
        die(f"{tc['name']}: ziglang.org's index lists no {url}")
    if how == "json":
        src = fill(for_platform(spec["url"]) or "", subs)
        return (*_algo(dig(json.loads(get(src)), spec["path"])), src)
    if how == "android-repo":
        xml = get(spec.get("url") or "https://dl.google.com/android/repository/repository2-3.xml")
        for arch in re.findall(r"<archive>.*?</archive>", xml, re.S):
            if re.search(rf"<url>{re.escape(name)}</url>", arch):
                m = re.search(r'<checksum type="sha1">([0-9a-f]{40})</checksum>', arch)
                if m:
                    return (*_algo(m.group(1)), "Google's Android repository listing")
        die(f"{tc['name']}: Google's repository lists no {name}")
    if how == "zsync":
        head = get(url + ".zsync", decode=False)[:4096].decode("latin-1")
        m = re.search(r"^SHA-1: ([0-9a-f]{40})$", head, re.M)
        if not m:
            die(f"{tc['name']}: {url}.zsync states no SHA-1")
        return (*_algo(m.group(1)), url + ".zsync")
    die(f"{tc['name']}: unknown checksum source {how!r}")


def content_length(url):
    req = urllib.request.Request(_web(url), headers=UA, method="HEAD")
    with urllib.request.urlopen(req, timeout=TIMEOUT) as r:  # nosemgrep: python.lang.security.audit.dynamic-urllib-use-detected.dynamic-urllib-use-detected
        n = r.headers.get("Content-Length")
    return int(n) if n and n.isdigit() else 0


def download_urls(tc):
    """Every URL an install of this toolchain would fetch, or none: what
    its source names or can be asked for (_source_urls), and each download
    it declares for this machine."""
    return _source_urls(tc) + [declared_address(f) for f in declared(tc)]


def _source_urls(tc):
    """The URLs a toolchain's own source would fetch, or none.

    Two ways to know. A recipe whose own source.url is the payload (a tarball)
    is its own answer. Everything else has to ask the installer, and most of
    them will say: playwright's dry run names the five bundles it would pull,
    the .NET installer names the SDK archive it would pull. That is a command
    to run and a pattern to match, both of which are catalog entries rather
    than code here, so a toolchain that can be asked the same way needs no
    python at all.

    Some cannot be asked: a git clone has no content length, rustup fetches
    components it decides on as it goes, and sdkmanager keeps its sizes in a
    repository index this does not read. Those report nothing, which is the
    honest answer and is what the row then shows.
    """
    src = tc.get("source") or {}
    spec = src.get("download")
    if pin_of(tc) is not None and not src.get("online"):
        # Pinned, with nothing fetched behind it: the pinned file is the
        # download, whatever a dry run of the vendor's would name today.
        _, url = resolve(tc)
        return [url] if url and src.get("kind") in ("tarball", "script") else []
    if spec is None:
        _, url = resolve(tc)
        return [url] if url and src.get("kind") == "tarball" else []
    kind = spec.get("resolver")
    if kind in ("android-repo", "approximate"):
        return []                     # size_of answers these without a URL
    if kind == "url-matches":
        # The URLs are listed in a file upstream publishes rather than by a
        # command: rust's channel manifest names an archive per component, and
        # the three a minimal profile installs are the honest answer to what
        # `rustup` is about to fetch.
        if not spec.get("url") or not spec.get("match"):
            die(f"{tc['name']}: a url-matches download needs both url and match")
        try:
            return re.findall(spec["match"], get(spec["url"]))
        except Exception:  # noqa: BLE001
            return []
    if kind != "command-urls":
        die(f"{tc['name']}: unknown download resolver {kind!r}")
    if not spec.get("run") or not spec.get("match"):
        die(f"{tc['name']}: a command-urls download needs both run and match")
    env = dict(os.environ, **{k: str(v) for k, v in (spec.get("env") or {}).items()})
    # Cached like a fetched document, and for the same reason: the .NET dry run
    # downloads and executes a vendor script, and it was being run twice per
    # check: once to learn the version, once to learn the size.
    def dry_run():
        try:
            return subprocess.run(spec["run"], capture_output=True,
                                  timeout=120, env=env).stdout
        except (OSError, subprocess.SubprocessError):
            return b""

    out = _cached("RUN " + "\x00".join(spec["run"]), dry_run).decode("utf-8", "replace")
    return re.findall(spec["match"], out)


def _revision(pkg_el):
    rev = pkg_el.find("revision")
    if rev is None:
        return ()
    return tuple(int(x.text) if (x.text or "").isdigit() else 0 for x in rev)


def android_size(spec, pkg_id):
    """The size sdkmanager's own repository index gives for exactly this id.

    sdkmanager will not say what a package weighs, but the index it reads
    does, and that index is the only place an android download size exists
    before the download. Looked up by the id bb resolved rather than by
    picking the newest entry: the index's newest playstore image is an
    android-CANARY build nobody is installing, and the emulator appears twice,
    once stable and once on the dev channel, sixteen megabytes apart.
    """
    best = None
    for url in spec.get("xml") or []:
        try:
            root = ET.fromstring(get(url, decode=False))
        except Exception:  # noqa: BLE001 - one index missing is not fatal
            continue
        channels = {c.get("id"): (c.text or "") for c in root if c.tag.endswith("channel")}
        for el in root:
            if not el.tag.endswith("remotePackage") or el.get("path") != pkg_id:
                continue
            ref = el.find("channelRef")
            channel = channels.get(ref.get("ref"), "") if ref is not None else "stable"
            if channel and channel != "stable":
                continue
            for a in el.iter():
                if not a.tag.endswith("archive"):
                    continue
                host, arch = a.findtext("host-os"), a.findtext("host-arch")
                if host not in (None, "linux") or arch not in (None, "x64", "x86_64"):
                    continue
                size = a.findtext("complete/size") or ""
                if size.isdigit():
                    here = (_revision(el), int(size))
                    if best is None or here[0] > best[0]:
                        best = here
    return best[1] if best else 0


def image_flavors():
    """The android_images section of the catalog: flavor -> {label, about, xml}."""
    sec = _catalog().get("android_images") or {}
    return sec.get("abi") or "x86_64", sec.get("flavors") or {}


IMAGE_ID = re.compile(r"^system-images;android-([A-Za-z0-9.-]+);([A-Za-z0-9_-]+);(.+)$")


def available_images():
    """Every system image the catalog's flavors offer, from sdkmanager's index.

    One line per image (id, API level, flavor, bytes), which is what makes an
    API level offerable at all: sdkmanager cannot be asked what exists without
    a network round trip that prints a thousand rows, and cannot be asked what
    anything weighs at any price. The index answers both.

    Stable channel only, and only the archive this host could run: the index
    carries CANARY builds and other ABIs beside the ones anybody wants.
    """
    abi, flavors = image_flavors()
    rows = {}
    for flavor, spec in flavors.items():
        url = spec.get("xml")
        if not url:
            continue
        try:
            root = ET.fromstring(get(url, decode=False))
        except Exception:  # noqa: BLE001 - one index missing is not fatal
            continue
        channels = {c.get("id"): (c.text or "") for c in root if c.tag.endswith("channel")}
        for el in root:
            if not el.tag.endswith("remotePackage"):
                continue
            m = IMAGE_ID.match(el.get("path") or "")
            if not m or m.group(2) != flavor or m.group(3) != abi:
                continue
            ref = el.find("channelRef")
            channel = channels.get(ref.get("ref"), "") if ref is not None else "stable"
            if channel and channel != "stable":
                continue
            for a in el.iter():
                if not a.tag.endswith("archive"):
                    continue
                host, arch = a.findtext("host-os"), a.findtext("host-arch")
                if host not in (None, "linux") or arch not in (None, "x64", "x86_64"):
                    continue
                size = a.findtext("complete/size") or ""
                if not size.isdigit():
                    continue
                key = el.get("path")
                # The newest revision of an image that ships more than one.
                here = (_revision(el), int(size))
                if key not in rows or here[0] > rows[key][0]:
                    rows[key] = here
    out = []
    for key, (_, size) in rows.items():
        m = IMAGE_ID.match(key)
        out.append((key, m.group(1), m.group(2), size))
    # Newest level first, and a plain level ahead of the extension builds that
    # share its number: android-34 is what somebody picking "34" means, and
    # android-34-ext11 is a thing they would have to have gone looking for.
    # The index itself is in no order worth relying on.
    def key(row):
        m = re.match(r"(\d+)(.*)", row[1])
        return (-int(m.group(1)) if m else 0, bool(m and m.group(2)),
                m.group(2) if m else row[1], row[2])
    return sorted(out, key=key)


def size_of(tc, pkg_id=""):
    """What an install would download, in bytes, or empty when unknowable."""
    spec = (tc.get("source") or {}).get("download") or {}
    if spec.get("resolver") == "android-repo":
        return str(android_size(spec, pkg_id)) if pkg_id else ""
    if spec.get("resolver") == "approximate":
        # A number somebody wrote down, for the one recipe whose download
        # cannot be measured before it happens. Marked with a tilde all the
        # way to the row, so it is never mistaken for a measurement.
        n = spec.get("bytes")
        return f"~{n}" if isinstance(n, int) and n > 0 else ""
    total = 0
    for url in download_urls(tc):
        try:
            total += content_length(url)
        except Exception:  # noqa: BLE001
            # One unreachable mirror and the total is a lie, so say nothing.
            return ""
    return str(total) if total else ""


# Where a source kind with no url of its own downloads from: sdkmanager's
# packages are Google's.
KIND_HOST = {"sdkmanager": "dl.google.com"}


def source_host(tc):
    """The host an install of `tc` downloads from first, or "" where the
    catalog does not say (a command run through another tool)."""
    src = tc.get("source") or {}
    url = for_platform(src.get("url")) if src.get("url") else ""
    if isinstance(url, str) and "://" in url:
        return urllib.parse.urlsplit(url).hostname or ""
    return KIND_HOST.get(str(src.get("kind") or ""), "")


def unreachable(host, timeout=6):
    """Why `host` cannot be reached from here on 443 (its name not found, or
    no answer), or "" when it can (R82): asked before an install starts, so a
    machine with no internet is told in one sentence, not a traceback."""
    import socket
    try:
        socket.getaddrinfo(host, 443)
    except OSError:
        return f"{host} could not be looked up: this machine has no internet, or no name server that answers"
    try:
        socket.create_connection((host, 443), timeout=timeout).close()
    except OSError as e:
        return f"{host} did not answer ({e.strerror or e}): this machine cannot reach the internet"
    return ""


def receipt(d, commit, name=""):
    """An install's receipt (R234): every file that landed in DIR with its
    sha256, one hash over the whole list, and the commit it was installed
    from (for an entry that is no repository, the sha256 its download was
    held to, or nothing). A pack's pin covers its own files, and what its
    install steps fetch from somewhere else left no trail (the operator,
    13 Nov): this is it. Written to DIR/.bb-receipt, whose first line is
    the summary the node's census reads (format, commit, tree, files,
    bytes, when, the tree the same commit made here before where that was
    another, and whether its steps ran with the network cut, for an entry
    that declares its downloads: cut, open, online with the entry's
    sentence in a field after it, or nothing for one that declares none),
    and added as a line to the store's own log (.bb-receipts beside DIR),
    which a remove and a reinstall leave alone. Returns the summary as
    words.

    Left out: git's own directory, AerieOS's marks (.bb-*) and compiled
    python, which carries the moment it was compiled."""
    import hashlib
    import time
    d = os.path.abspath(d)
    lines, total = [], 0
    for top, dirs, files in os.walk(d):
        dirs[:] = sorted(x for x in dirs if x not in (".git", "__pycache__"))
        for dn in list(dirs):
            full = os.path.join(top, dn)
            if os.path.islink(full):
                lines.append((os.path.relpath(full, d), "link  " + os.readlink(full)))
                dirs.remove(dn)
        for fn in files:
            if fn.startswith(".bb-") or fn.endswith(".pyc"):
                continue
            full = os.path.join(top, fn)
            rel = os.path.relpath(full, d)
            if os.path.islink(full):
                lines.append((rel, "link  " + os.readlink(full)))
                continue
            if not os.path.isfile(full):
                continue
            h = hashlib.sha256()
            try:
                with open(full, "rb") as f:
                    for chunk in iter(lambda: f.read(1 << 20), b""):
                        h.update(chunk)
                        total += len(chunk)
            except OSError as e:
                lines.append((rel, f"unread  {e.strerror or 'could not be read'}"))
                continue
            lines.append((rel, h.hexdigest() + ("  x" if os.access(full, os.X_OK) else "  -")))
    lines.sort(key=lambda r: r[0].encode("utf-8", "surrogateescape"))
    body = "".join(f"{what}  {rel}\n" for rel, what in lines)
    tree = hashlib.sha256(body.encode("utf-8", "surrogateescape")).hexdigest()
    now = int(time.time())
    name = name or os.path.basename(d)
    # What the same commit made here the last time, where that was another.
    log, before = os.path.join(os.path.dirname(d), ".bb-receipts"), ""
    try:
        with open(log, encoding="utf-8", errors="replace") as f:
            for ln in f:
                r = ln.rstrip("\n").split("\t")
                if commit and len(r) >= 4 and r[1] == name and r[2] == commit:
                    before = r[3] if r[3] != tree else ""
    except OSError:
        pass
    # Whether its steps ran with the network cut (sdk.sh sdk_declared), or
    # kept it because its entry says its installer downloads the rest, with
    # the entry's own sentence on the line after.
    net, why = "", ""
    try:
        with open(os.path.join(d, ".bb-net"), encoding="utf-8") as f:
            net = f.readline().strip()
            why = " ".join(f.readline().split())[:300]
    except OSError:
        pass
    net = net if net in ("cut", "open", "online") else ""
    why = why if net == "online" else ""
    with open(os.path.join(d, ".bb-receipt"), "w", encoding="utf-8", errors="surrogateescape") as f:
        f.write(f"1\t{commit}\t{tree}\t{len(lines)}\t{total}\t{now}\t{before}\t{net}" + (f"\t{why}" if why else "") + f"\n{body}")
    try:
        with open(log, "a", encoding="utf-8") as f:
            f.write(f"{now}\t{name}\t{commit}\t{tree}\t{len(lines)}\t{total}\n")
    except OSError:
        pass
    # Filed under the commit it was fetched at or the sha256 its download
    # was held to; a download its publisher's signature held has neither.
    said = f"receipt: {len(lines)} files, {total} bytes, " + (f"from {commit[:12]}, " if commit else "") + f"{tree[:12]} over them all"
    said += {"cut": "; its steps ran with no network", "open": "; its steps ran with the network, which this node cannot cut",
             "online": f"; its steps kept the network, as its entry says: {why or 'its installer downloads the rest'}"}.get(net, "")
    return said + (f"; the same commit made {before[:12]} here before" if before else "")


def main(argv):
    if not argv:
        die("usage: sdkmeta.py names|flavors|images|field|argv|resolve|size ...")
    op = argv[0]

    if op == "receipt":
        # receipt DIR COMMIT [NAME]: what an install left, written beside it.
        if len(argv) < 3 or not os.path.isdir(argv[1]):
            die("receipt needs the installed directory and the commit it came from")
        print(receipt(argv[1], argv[2], argv[3] if len(argv) > 3 else ""))
        return

    if op == "names":
        print("\n".join(p["name"] for p in catalog()))
        return

    if op == "flavors":
        abi, flavors = image_flavors()
        for name, spec in flavors.items():
            print(f"{name}\t{abi}\t{spec.get('label', name)}\t{spec.get('about', '')}")
        return

    if op == "keyring":
        # keyring KEYS [NAME [DIR]]: the keyring file gpgv reads for one
        # publisher's keys (R137), the ones the entry NAME carries where it
        # carries them, made in DIR, the caller's own directory for this
        # one check.
        print(keyring(argv[1] if len(argv) > 1 else "", toolchain(argv[2]) if len(argv) > 2 and argv[2] else None,
                      argv[3] if len(argv) > 3 else None))
        return


    if op == "images":
        for pid, api, flavor, size in available_images():
            print(f"{pid}\t{api}\t{flavor}\t{size}")
        return

    if len(argv) < 2:
        die(f"{op} needs a toolchain name")
    tc = toolchain(argv[1])

    if op == "field":
        # A per-platform value (a dict keyed "<os>/<arch>") answers for the
        # machine running this: a tarball's strip count, a script's url.
        v = for_platform(dig(tc, argv[2])) if len(argv) > 2 else None
        if isinstance(v, bool):
            v = "1" if v else ""
        print("" if v is None else v)

    elif op == "argv":
        subs = dict(a.split("=", 1) for a in argv[3:] if "=" in a)
        items = dig(tc, argv[2]) or []
        if not isinstance(items, list):
            die(f"{argv[2]} is not a list")
        # NUL-separated, because an argument may hold anything a JSON string
        # can and the caller reads it into a bash array.
        sys.stdout.write("".join(fill(str(i), subs) + "\0" for i in items))

    elif op == "env":
        # KEY=VALUE per line, NUL-terminated for the same reason.
        subs = dict(a.split("=", 1) for a in argv[3:] if "=" in a)
        for k, v in (dig(tc, argv[2]) or {}).items():
            sys.stdout.write(f"{k}={fill(str(v), subs)}\0")

    elif op == "reach":
        # Exit 0 quietly when the source's host answers, or when the catalog
        # names none; else the sentence, and 1.
        host = source_host(tc)
        why = unreachable(host) if host else ""
        if why:
            print(why)
            raise SystemExit(1)

    elif op == "resolve":
        version, url = resolve(tc)
        print(f"{version}\t{url}")

    elif op == "declared":
        # What the entry declares of its own install, for sdk.sh's
        # sdk_declared: nothing at all for one that declares nothing.
        for line in declared_plan(tc):
            print(line)

    elif op == "files":
        # files NAME DIR: the small files the row carries, written into
        # DIR; a line a file written, nothing for a row that carries none.
        if len(argv) < 3 or not os.path.isdir(argv[2]):
            die("files needs the directory the row is installed in")
        for rel in write_files(tc, argv[2]):
            print(rel)

    elif op == "offer":
        # The version and the digest a pinned row has on offer, or nothing
        # for a row whose version is its vendor's latest.
        got = offered(tc)
        if got:
            print(f"{got[0]}\t{got[1]}")

    elif op == "checksum":
        # The algorithm, the digest and where it came from, tab-separated:
        # what sdk.sh holds a download to before it is unpacked or run.
        url = argv[2] if len(argv) > 2 else ""
        version = argv[3] if len(argv) > 3 else ""
        algo, digest, where = checksum(tc, url, version)
        print(f"{algo}\t{digest}\t{where}")

    elif op == "size":
        # An optional package id, for the recipes whose size lives in an index
        # keyed by one: bb resolves it, so that the id asked about here is
        # exactly the id that would be installed.
        print(size_of(tc, argv[2] if len(argv) > 2 else ""))

    else:
        die(f"unknown operation {op!r}")


if __name__ == "__main__":
    main(sys.argv[1:])
