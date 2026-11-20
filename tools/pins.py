#!/usr/bin/env python3
"""Moves the pins of the toolchains AerieOS ships (config/toolchains.json).

Whatever a row fetches from somewhere else is held to something the row
itself carries: the sha256 of the exact file, or, for a repository, a
commit. An install takes the pin and asks nobody what is newest, so a newer
version arrives as a change to the row, and this is what proposes it. How a
newer version is found and how its digest is learned are the row's own data
(source.version, checksum.found, a declared download's track and found,
source.track), read with the resolvers of scripts/lib/sdkmeta.py: nothing
here knows a vendor.

What a package manager installs is held the same way. A row says what it
asks pip or npm for (source.lock), the manager's own resolver says which
exact files that is (uv for pip, npm for npm: both must be on the PATH),
and each file becomes a declared download of the row under the lock's
directory, with the requirements or the lock an install reads written into
source.files. check says when a lock's resolution would change, and move
replaces the lock's set whole, leaving the row's other downloads alone.

    tools/pins.py check [NAME...]     what each pinned row is pinned to, what its own resolver finds
                                      now, and whether a pinned file that has no resolver still
                                      answers the pinned bytes. Reads the network, writes nothing.
                                      Exit 0 when nothing would move, 3 when something would, 1 on
                                      an error. A newer release that is not out for every platform
                                      a row names holds the row where it is: said, and not a move.
    tools/pins.py move [NAME...]      writes the new version and digests into the table for the rows
                                      named (every pinned row with none named), every platform a row
                                      names or none of them, raises the row's rev by one, and runs
                                      tools/packs-export.py --write. Prints what moved, old to new.
    tools/pins.py pin NAME            a row not pinned yet: its origin-checked download becomes a pin
                                      at the version its resolver finds now, the old checksum kept as
                                      found; a repository's commit is pinned by its source.track; and
                                      each download it declares with no digest yet (a row written with
                                      its address, its track and no sha256) is given the version its
                                      track finds now and its digest; and each lock with no downloads
                                      yet is resolved to its first set.
    tools/pins.py verify [NAME...]    downloads each pinned file and holds it to its pin, for this
                                      machine's platform; --platform P for another, --all for every
                                      one. A file is streamed and hashed, never kept. Exit 1 naming
                                      each file that is not its pin.

    --file PATH     another table than config/toolchains.json. The official packs are written only
                    for the shipped one.
    --version V     with pin or move and one NAME: that version, not the one the resolver finds (a
                    release whose files for every platform are not out yet).

Where a publisher states a sha256 the tool takes it, and says from where.
Where it states another digest (a sha1, a sha512) or none, the tool
downloads the file, hashes it, and holds it to what the publisher does
state. A row moves whole: one platform's file that cannot be learned leaves
the row as it was, said by name.
"""
import base64
import copy
import hashlib
import json
import os
import re
import shutil
import subprocess
import sys
import tempfile
import tomllib
import urllib.error
import urllib.request

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.dirname(HERE)
sys.path.insert(0, os.path.join(ROOT, "scripts", "lib"))
sys.path.insert(0, os.path.join(ROOT, "scripts", "dashboard"))
import catalogrows  # noqa: E402
import packformat  # noqa: E402
import sdkmeta  # noqa: E402

TABLE = os.path.join(ROOT, "config", "toolchains.json")
# A digest its publisher states that is no sha256 is checked while the file
# is hashed, by these.
ALSO = ("sha1", "sha512")


class Refused(Exception):
    """Why something of a row could not be learned."""


def _die(msg):
    raise Refused(str(msg))


class As:
    """sdkmeta answering for the platform `plat` names, as a row keys one
    ("" is this machine's own), and answering what it cannot read with a
    Refused: it ends its own process on that, and here it is one row's
    answer, with the next row still asked. Everything asked of sdkmeta is
    asked inside one."""

    def __init__(self, plat=""):
        self.plat = plat

    def __enter__(self):
        self.was = (sdkmeta.AS_PLATFORM, sdkmeta.die)
        sdkmeta.AS_PLATFORM, sdkmeta.die = self.plat, _die

    def __exit__(self, *exc):
        sdkmeta.AS_PLATFORM, sdkmeta.die = self.was


def hashed(url, also=""):
    """{"sha256": ..., also: ..., "bytes": n} for what `url` answers,
    streamed: nothing is kept. `also` is a second digest to work out on the
    way, for a publisher that states that one."""
    req = urllib.request.Request(sdkmeta._web(url), headers=sdkmeta.UA)
    sums = {"sha256": hashlib.sha256(), **({also: hashlib.new(also)} if also in ALSO else {})}
    n = 0
    with urllib.request.urlopen(req, timeout=120) as r:  # nosemgrep: python.lang.security.audit.dynamic-urllib-use-detected.dynamic-urllib-use-detected
        for chunk in iter(lambda: r.read(1 << 20), b""):
            n += len(chunk)
            for h in sums.values():
                h.update(chunk)
    return {**{k: h.hexdigest() for k, h in sums.items()}, "bytes": n}


def said(e):
    """An error as one line."""
    if isinstance(e, urllib.error.HTTPError):
        return f"{e.url} answered {e.code}"
    if isinstance(e, urllib.error.URLError):
        return f"it could not be reached: {e.reason}"
    if isinstance(e, subprocess.TimeoutExpired):
        return f"{os.path.basename(str(e.cmd[0] if isinstance(e.cmd, (list, tuple)) and e.cmd else e.cmd))} did not answer in time"
    if isinstance(e, StopIteration):
        return "its resolver found no version"
    if isinstance(e, KeyError):
        return f"its resolver names no {e}"
    return " ".join(str(e).split()) or type(e).__name__


ERRORS = (Refused, OSError, ValueError, KeyError, StopIteration, subprocess.TimeoutExpired)


def digest_of(row, url, version, found):
    """(sha256, how it was learned) for the file `url` answers: its
    publisher's own sha256 where `found` reads one, with nothing
    downloaded; otherwise the file downloaded and hashed here, held to
    whatever other digest the publisher states."""
    kind = (found or {}).get("from")
    if kind and kind not in ("none", "signature"):
        algo, want, where = sdkmeta.checksum(row, url, version, found)
        if algo == "sha256":
            return want, f"stated by {where}"
        if algo in ALSO:
            got = hashed(url, algo)
            if got[algo] != want:
                raise Refused(f"{url} answers a file whose {algo} is {got[algo]}, and {where} states {want}")
            return got["sha256"], f"downloaded and hashed here ({got['bytes']} bytes), its {algo} matching {where}"
    got = hashed(url)
    return got["sha256"], f"downloaded and hashed here ({got['bytes']} bytes): its publisher states no digest for it"


# ---- a row's own download -----------------------------------------------------
def platforms(row):
    """The platforms a row's own download differs by, as the row keys
    them: its address's, its pin's digests', its resolver's assets'. [""]
    for a row whose one file serves every platform."""
    src = row.get("source") or {}
    pin = sdkmeta.pin_of(row) or {}
    for v in (src.get("url"), pin.get("sha256"), (src.get("version") or {}).get("asset")):
        if isinstance(v, dict) and v:
            return list(v)
    return [""]


def address(row, version, plat):
    """The address of a row's download at `version` for `plat`: its own
    template filled in."""
    src = row.get("source") or {}
    with As(plat):
        url = sdkmeta.fill(sdkmeta.for_platform(src.get("url")) or "", {"version": version}) if src.get("url") else ""
    if not url:
        raise Refused(f"it names no address for {plat or 'its download'}")
    return url


def learned(row, version=""):
    """What a row's pin would be now: {"version", "supplied" (whether its
    resolver gives the address itself), "files": {platform: {"url",
    "sha256", "how"}}}. Every platform the row names, or a Refused that
    says which could not be learned. `version` in the resolver's place
    where one is named."""
    src = row.get("source") or {}
    found = (src.get("checksum") or {}).get("found") if sdkmeta.pin_of(row) else src.get("checksum")
    out = {"version": None, "supplied": False, "files": {}}
    for plat in platforms(row):
        try:
            with As(plat):
                v, url = (version, "") if version else sdkmeta.newest(row)
            if out["version"] not in (None, v):
                raise Refused(f"its resolver finds {v} where it found {out['version']} for another platform: a pin is one version")
            out["version"] = v
            if url:
                out["supplied"] = True
            else:
                url = address(row, v, plat)
            with As(plat):
                digest, how = digest_of(row, url, v, found)
        except ERRORS as e:
            raise Refused(f"{plat or 'its download'} could not be learned ({said(e)})") from e
        out["files"][plat] = {"url": url, "sha256": digest, "how": how}
    return out


def pinned_files(row, plats=None):
    """{platform: (address, sha256)} as a row's pin has them now."""
    pin = sdkmeta.pin_of(row)
    out = {}
    for plat in platforms(row) if plats is None else plats:
        with As(plat):
            digest = sdkmeta.pinned_digest(row)
        if not digest:
            raise Refused(f"its pin names no digest for {plat or 'this machine'}")
        out[plat] = (address(row, str(pin.get("version") or ""), plat), digest)
    return out


def write_pin(row, got, found):
    """The pin `got` (learned) written into `row`: the version, a digest a
    platform in the shape its address has, the address too where the
    resolver supplies it, and `found` as how the next one is learned."""
    src = row["source"]
    files = got["files"]
    one = list(files) == [""]
    pin = {"from": "pin"}
    if got["version"]:
        pin["version"] = got["version"]
    pin["sha256"] = files[""]["sha256"] if one else {p: f["sha256"] for p, f in files.items()}
    if isinstance(found, dict) and found.get("from") not in (None, "none", "pin"):
        pin["found"] = found
    src["checksum"] = pin
    if got["supplied"]:
        src["url"] = files[""]["url"] if one else {p: f["url"] for p, f in files.items()}


# ---- a repository -------------------------------------------------------------
def git_learned(row):
    """{"name", "commit", "tag"} for a repository's commit to pin, by its
    source.track: the tag it is at where the track is by tag."""
    src = row.get("source") or {}
    if not isinstance(src.get("track"), dict):
        raise Refused("it says no source.track: how the commit to pin is found")
    try:
        with As():
            name, commit = sdkmeta.git_newest(row)
    except ERRORS as e:
        raise Refused(f"its commit could not be learned ({said(e)})") from e
    if not packformat.COMMIT.fullmatch(commit):
        raise Refused(f"its repository answered {commit[:60]!r}, which is no commit")
    return {"name": name, "commit": commit, "tag": name if src["track"].get("resolver") == "git-tag" else ""}


# ---- declared downloads --------------------------------------------------------
def fetch_rows(row):
    rows = (row.get("source") or {}).get("fetch")
    return [f for f in rows if isinstance(f, dict) and f.get("url")] if isinstance(rows, list) else []


def fetch_said(f):
    """A declared download as a line names it: the file it is kept as, and
    the platform it is for."""
    return f"{f.get('to')}{' for ' + f['platform'] if f.get('platform') else ''}"


def fetch_held(f):
    """Whether a declared download is held to something yet: a sha256, or
    its publisher's signature. One written with neither is waiting for its
    first pin."""
    return bool(f.get("sha256")) or isinstance(f.get("signed"), dict)


def unheld(row):
    """The downloads a row declares that are held to nothing yet."""
    return [f for f in fetch_rows(row) if not fetch_held(f)]


def fetch_of(row, to, plat):
    """The declared download of `row` kept as `to` for `plat`: a part is
    written into a copy of the row by what it is, not by where it stands in
    the list, since the rows beside it may have moved."""
    return next(f for f in fetch_rows(row) if f.get("to") == to and str(f.get("platform") or "") == plat)


def fetch_write(f, changed):
    """What moved written into a declared download, its keys left in the
    order a row writes them: the address, the version, the digest, then
    where it is kept and how the next one is found."""
    f.update(changed)
    for k in ("to", "platform", "signed", "track", "found"):
        if k in f:
            f[k] = f.pop(k)


def fetch_learned(row, f, cache):
    """What a declared download would be now: {"version", "url", "sha256",
    "how"}. One that says track is asked for its newest version, once for
    every download that says the same track; one that says none has
    nothing to track, and its address is asked for the bytes it answers
    today. A file in a repository is tracked by the repository: its
    version is the newest tag (with the track's trims off), or the commit a
    branch is at. A tracked download that is at the version found already
    is as its entry pins it, and is not asked for again."""
    track = f.get("track") if isinstance(f.get("track"), dict) else None
    plat = str(f.get("platform") or "")
    version, url = str(f.get("version") or ""), ""
    with As(plat):
        if track:
            key = json.dumps(track, sort_keys=True) + "\0" + plat
            if key not in cache:
                if track.get("resolver") in packformat.GIT_RESOLVERS:
                    name, commit = sdkmeta.git_newest({**row, "source": {"url": track.get("url")}}, track)
                    cache[key] = (commit if track["resolver"] == "git-branch" else sdkmeta.trimmed(name, track), "")
                else:
                    cache[key] = sdkmeta.newest(row, track)
            version, url = cache[key]
        url = url or sdkmeta.declared_address({**f, "version": version})
        if isinstance(f.get("signed"), dict):
            return {"version": version, "url": url, "sha256": "", "how": "held by its publisher's signature"}
        if track and f.get("sha256") and version == f.get("version") and url == sdkmeta.declared_address(f):
            return {"version": version, "url": url, "sha256": f["sha256"], "how": "its track finds the version it is pinned to"}
        digest, how = digest_of(row, url, version, f.get("found"))
    return {"version": version, "url": url, "sha256": digest, "how": how}


# ---- what a package manager installs -------------------------------------------
# A row says what it asks a package manager for (source.lock), and the
# manager's own resolver says which exact files that is today. Each file
# becomes a declared download of the row, kept under the lock's directory,
# and the small files the manager installs by (its requirements with their
# hashes, its lock) go into source.files beside them. The install step
# then installs from that directory with no index and no network.
#
# One function a manager turns what its resolver says into those rows
# (pip_locked, npm_locked), and one asks the resolver (pip_resolved,
# npm_resolved), which is the only part that runs a program and reaches
# the network: a test stands in for it. A lock's set is replaced whole
# when it moves, and the row's other downloads are left alone.
def locks(row):
    got = (row.get("source") or {}).get("lock")
    return [lk for lk in got if isinstance(lk, dict) and lk.get("to")] if isinstance(got, list) else []


def lock_rows(row, lk):
    """The declared downloads of `row` a lock owns: the ones kept under
    its directory."""
    return [f for f in fetch_rows(row) if str(f.get("to") or "").startswith(lk["to"] + "/")]


def lock_files(row, lk):
    """The files `row` carries that a lock owns, {path: text}."""
    files = (row.get("source") or {}).get("files")
    return {p: t for p, t in files.items() if p.startswith(lk["to"] + "/")} if isinstance(files, dict) else {}


def unlocked(row):
    """The locks of a row with no downloads yet: waiting for a first pin."""
    return [lk for lk in locks(row) if not lock_rows(row, lk)]


def _tool(name, what):
    path = shutil.which(name)
    if not path:
        raise Refused(f"there is no {name} here to resolve {what} with")
    return path


def _ran(argv, cwd, what):
    """Run a resolver, or a Refused with the end of what it said."""
    p = subprocess.run(argv, cwd=cwd, capture_output=True, text=True, timeout=900, check=False)
    if p.returncode:
        raise Refused(f"{what}: {' '.join((p.stderr or p.stdout).split())[-400:] or 'it failed'}")


def pip_resolved(requirements, python, target):
    """What `requirements` resolve to for a Python and a platform, as the
    packages of the pylock.toml uv writes: each {name, version, wheels:
    [{url, hashes: {sha256}}]}, the wheels the ones that fit the platform.
    The index states each file's sha256, so nothing is downloaded to learn
    one, and nothing is built: a source distribution's own code does not
    run here either."""
    uv = _tool("uv", "what pip is asked for")
    with tempfile.TemporaryDirectory() as d:
        with open(os.path.join(d, "requirements.in"), "w", encoding="utf-8") as f:
            f.write("".join(r + "\n" for r in requirements))
        _ran([uv, "pip", "compile", "requirements.in", "--python-version", python, "--python-platform", target, "--no-build",
              "--format", "pylock.toml", "-o", "pylock.toml", "--no-header", "-q"], d, f"uv could not resolve {', '.join(requirements)} for {target}")
        with open(os.path.join(d, "pylock.toml"), "rb") as f:
            return tomllib.load(f).get("packages") or []


def wheel_rank(name):
    """How closely a wheel is built for a machine, to pick one among those
    a resolver says fit it: one built for the interpreter before one for
    the stable ABI before a pure one, the newest interpreter it names, and
    the newest baseline of the system."""
    stem = name.removesuffix(".whl").split("-")
    py, abi, plat = stem[-3:] if len(stem) >= 5 else ("", "", "")

    def baseline(tag):
        """The system baseline a platform tag names, as numbers: a glibc
        or a musl version, a macOS release; the three old names by theirs."""
        for old, was in (("manylinux1_", [2, 5]), ("manylinux2010_", [2, 12]), ("manylinux2014_", [2, 17])):
            if tag.startswith(old):
                return was
        m = re.match(r"(?:manylinux|musllinux|macosx)_(\d+)_(\d+)_", tag)
        return [int(m.group(1)), int(m.group(2))] if m else [0, 0]

    newest = max(([int(n) for n in re.findall(r"\d+", tag)] for tag in py.split(".")), default=[])
    return (abi not in ("abi3", "none"), abi == "abi3", newest, plat != "any", max(baseline(tag) for tag in plat.split(".")), name)


# A platform as a requirements file's marker says it, for a lock resolved
# for several: a package only some of them need, or need another version of.
MARKERS = {"linux": "sys_platform == 'linux'", "linux-musl": "sys_platform == 'linux'", "darwin": "sys_platform == 'darwin'"}
MACHINES = {("linux", "amd64"): "x86_64", ("linux", "arm64"): "aarch64", ("linux-musl", "amd64"): "x86_64", ("linux-musl", "arm64"): "aarch64",
            ("darwin", "amd64"): "x86_64", ("darwin", "arm64"): "arm64"}


def marker(plat):
    system, _, arch = plat.partition("/")
    return MARKERS[system] + (f" and platform_machine == '{MACHINES[(system, arch)]}'" if arch != "*" else "")


def pip_locked(row, lk, have):
    """A pip lock as the row holds it: {"fetch", "files", "said"}. For each
    platform the lock names, what its requirements resolve to and the one
    wheel of each package that fits it best; every wheel a declared
    download, named for its platform where not every one takes it; and
    requirements.txt, each package at its version with the sha256 of each
    wheel, which the install step requires. A package with no wheel for a
    platform is refused by name."""
    plats, chosen = lk.get("for") or {}, {}
    for plat, target in plats.items():
        chosen[plat] = {}
        for pkg in pip_resolved(lk["requirements"], lk["python"], target):
            name, version = str(pkg.get("name") or ""), str(pkg.get("version") or "")
            wheels = [w for w in pkg.get("wheels") or [] if isinstance(w, dict) and w.get("url") and packformat.SHA256.fullmatch(str((w.get("hashes") or {}).get("sha256") or ""))]
            if not wheels:
                raise Refused(f"{name} {version} has no wheel for {plat}: a source distribution runs its own code at install, and is not taken")
            best = max(wheels, key=lambda w: wheel_rank(sdkmeta._name_of(w["url"])))
            chosen[plat][name] = {"version": version, "url": best["url"], "sha256": best["hashes"]["sha256"], "file": sdkmeta._name_of(best["url"])}
    # Each wheel once, for every platform or for the ones that take it.
    wheels = {}
    for plat in plats:
        for c in chosen[plat].values():
            wheels.setdefault(c["url"], (c, []))[1].append(plat)
    fetch = []
    for url, (c, takes) in wheels.items():
        base = {"url": url, "sha256": c["sha256"], "to": f"{lk['to']}/{c['file']}"}
        fetch += [base] if len(takes) == len(plats) else [{**base, "platform": p} for p in takes]
    # The requirements: a line a package and version, with the platforms
    # that take it where that is not every one.
    lines_, said_ = [], {}
    for name in sorted({n for p in plats for n in chosen[p]}):
        by_version = {}
        for plat in plats:
            if name in chosen[plat]:
                by_version.setdefault(chosen[plat][name]["version"], []).append(plat)
        said_[name] = ", ".join(by_version)
        for version, takes in by_version.items():
            sums = sorted({chosen[p][name]["sha256"] for p in takes})
            only = "" if len(takes) == len(plats) else " ; " + " or ".join(f"({marker(p)})" for p in takes)
            lines_.append(f"{name}=={version}{only}" + "".join(f" --hash=sha256:{s}" for s in sums))
    return {"fetch": sorted(fetch, key=lambda f: (f["to"], f.get("platform", ""))), "said": said_,
            "files": {f"{lk['to']}/requirements.txt": "".join(ln + "\n" for ln in lines_)}}


def pip_said(files, lk):
    """{package: version} as a pip lock's carried requirements say it."""
    out = {}
    for ln in str(files.get(f"{lk['to']}/requirements.txt") or "").splitlines():
        name, eq, rest = ln.partition("==")
        if eq:
            out[name] = ", ".join(v for v in (out.get(name), rest.split()[0]) if v)
    return out


def npm_resolved(requirements):
    """(package.json, package-lock.json) as npm writes them for a project
    that asks for `requirements`, both as objects, with nothing installed
    and nobody's script run: the lock names every package's tarball and its
    integrity."""
    npm = _tool("npm", "what npm is asked for")
    with tempfile.TemporaryDirectory() as t:
        # The lock is named for its directory, so the directory is always this one.
        d = os.path.join(t, "entry")
        os.mkdir(d)
        with open(os.path.join(d, "package.json"), "w", encoding="utf-8") as f:
            f.write('{"private": true}\n')
        _ran([npm, "install", "--package-lock-only", "--ignore-scripts", "--no-audit", "--no-fund", "--loglevel=error", "--", *requirements], d,
             f"npm could not resolve {', '.join(requirements)}")
        return load(os.path.join(d, "package.json")), load(os.path.join(d, "package-lock.json"))


def _allows(listed, value):
    """Whether a lock's `os`, `cpu` or `libc` list takes `value`: named, or
    not ruled out where the list only rules out (a leading !)."""
    listed = [str(x) for x in listed] if isinstance(listed, list) else []
    yes = [x for x in listed if not x.startswith("!")]
    return "!" + value not in listed and (not yes or value in yes)


def npm_platforms(pkg, named):
    """The platforms of a row, as it keys them, that a package of an npm
    lock is for: None for one that is for every platform, [] for one that
    is for none the row names (it is left out), else the keys, a system's
    two processors as "<os>/*"."""
    if not any(pkg.get(k) for k in ("os", "cpu", "libc")):
        return None

    def covered(system, arch):
        """Whether the row names this machine: a musl one is a linux one."""
        system = system.replace("linux-musl", "linux")
        return any(str(n).replace("linux-musl/", "linux/") in (f"{system}/{arch}", f"{system}/*") for n in named)

    out = []
    for system, npm_os, libc in (("linux", "linux", "glibc"), ("linux-musl", "linux", "musl"), ("darwin", "darwin", "")):
        fits = [arch for cpu, arch in (("x64", "amd64"), ("arm64", "arm64"))
                if _allows(pkg.get("os"), npm_os) and _allows(pkg.get("cpu"), cpu) and (not libc or _allows(pkg.get("libc"), libc)) and covered(system, arch)]
        out += [f"{system}/*"] if len(fits) == 2 else [f"{system}/{a}" for a in fits]
    # A musl machine takes what is named for linux too: named once.
    return [k for k in out if not (k.startswith("linux-musl/") and (k.replace("linux-musl/", "linux/") in out or "linux/*" in out))]


def npm_hashed(url, integrity):
    """The sha256 of a package's tarball, downloaded and hashed here and
    held to the integrity its lock states (a sha512, or a sha1 on an old
    one): the registry states no sha256."""
    for one in str(integrity).split():
        algo, _, b64 = one.partition("-")
        if algo in ALSO:
            want = base64.b64decode(b64).hex()
            got = hashed(url, algo)
            if got[algo] != want:
                raise Refused(f"{url} answers a file whose {algo} is {got[algo]}, and its lock states {want}")
            return got["sha256"]
    raise Refused(f"{url} is held by {str(integrity)[:40]!r} in its lock, which is no digest read here")


def npm_locked(row, lk, have):
    """An npm lock as the row holds it: {"fetch", "files", "said"}. Every
    package of the lock npm writes a declared download, its tarball hashed
    here and held to the lock's integrity (`have` is the digests the row
    holds already, by address: a tarball is not fetched twice), one for a
    system or a processor named for that platform; and package.json with
    package-lock.json, which the install step installs by."""
    manifest, lock = npm_resolved(lk["requirements"])
    fetch, said_ = {}, {}
    for path, pkg in (lock.get("packages") or {}).items():
        if not path or not isinstance(pkg, dict) or pkg.get("link") or pkg.get("inBundle"):
            continue
        name = str(pkg.get("name") or path.rsplit("node_modules/", 1)[-1])
        said_[path.removeprefix("node_modules/")] = str(pkg.get("version") or "")
        url, integrity = str(pkg.get("resolved") or ""), pkg.get("integrity")
        if not url.startswith("https://") or not integrity:
            raise Refused(f"{name} is not a tarball its lock holds: it names {url[:80] or 'no address'}" + ("" if integrity else " and no integrity"))
        plats = npm_platforms(pkg, row.get("platforms") or [])
        if plats == []:
            continue
        to = f"{lk['to']}/{name.lstrip('@').replace('/', '-')}-{pkg.get('version')}.tgz"
        digest = have.get(url) or npm_hashed(url, integrity)
        for plat in plats or [""]:
            if fetch.get((to, plat), {"url": url})["url"] != url:
                raise Refused(f"two packages of its lock would be kept as {to}")
            fetch[(to, plat)] = {"url": url, "sha256": digest, "to": to, **({"platform": plat} if plat else {})}
    return {"fetch": [fetch[k] for k in sorted(fetch)], "said": said_,
            "files": {f"{lk['to']}/package.json": json.dumps(manifest, indent=2) + "\n",
                      f"{lk['to']}/package-lock.json": json.dumps(lock, separators=(",", ":")) + "\n"}}


def npm_said(files, lk):
    """{package: version} as an npm lock's carried package-lock.json says it."""
    try:
        packages = json.loads(files.get(f"{lk['to']}/package-lock.json") or "{}").get("packages") or {}
    except ValueError:
        return {}
    return {p.removeprefix("node_modules/"): str(v.get("version") or "") for p, v in packages.items() if p and isinstance(v, dict) and not v.get("link")}


# A package manager: what turns its resolver's answer into the row's
# downloads and files, and what reads the versions back out of the files.
LOCKS = {"pip": (pip_locked, pip_said), "npm": (npm_locked, npm_said)}


def write_lock(row, lk, got):
    """A lock's set written into `row` whole: its downloads in the place of
    the ones it owned, after the row's others, and its files likewise."""
    src = row["source"]
    under = lk["to"] + "/"
    src["fetch"] = [f for f in src.get("fetch") or [] if not (isinstance(f, dict) and str(f.get("to") or "").startswith(under))] + got["fetch"]
    src["files"] = {**{p: t for p, t in (src.get("files") or {}).items() if not p.startswith(under)}, **got["files"]}


def lock_parts(row, waiting=False):
    """plan's parts for what a row asks its package managers for, a part a
    lock: what its resolver finds now against the set the row holds. With
    `waiting`, only the locks with no downloads yet."""
    parts = []
    for lk in locks(row):
        mine, kind = lock_rows(row, lk), str(lk.get("kind"))
        if waiting and mine:
            continue
        if kind not in LOCKS:
            raise Refused(f"its lock for {lk['to']} is of kind {kind}, which is none of {', '.join(LOCKS)}")
        locked, said_of = LOCKS[kind]
        what = f"its {kind} lock ({lk['to']})"
        try:
            got = locked(row, lk, {sdkmeta.declared_address(f): f["sha256"] for f in mine if f.get("sha256")})
        except ERRORS as e:
            raise Refused(f"{what} could not be resolved ({said(e)})") from e
        key = lambda f: (f.get("to"), f.get("platform") or "", f.get("url"), f.get("sha256"))  # noqa: E731
        files = lock_files(row, lk)
        old = f"{len(mine)} file(s)" if mine else ""
        part = {"what": what, "old": old, "new": f"{len(got['fetch'])} file(s)"}
        if sorted(map(key, mine)) != sorted(map(key, got["fetch"])) or files != got["files"]:
            was = said_of(files, lk)
            moved_ = [f"{n} {was[n]} to {v}" if n in was else f"{n} {v} added" for n, v in got["said"].items() if was.get(n) != v]
            moved_ += [f"{n} {v} gone" for n, v in was.items() if n not in got["said"]]
            if mine and moved_:
                part["note"] = "; ".join(moved_[:8]) + (f"; and {len(moved_) - 8} more" if len(moved_) > 8 else "")
            part["apply"] = lambda r, lk=lk, got=got: write_lock(r, lk, got)
        else:
            part["new"], part["note"] = old, "its resolver finds the set it holds"
        parts.append(part)
    return parts


# ---- what a row is, and what would move ---------------------------------------
def is_pinned(row):
    """Whether a row has anything pinned for check and move to ask about. A
    row with a download still waiting for its first pin is `pin`'s."""
    src = row.get("source") or {}
    held = bool(sdkmeta.pin_of(row) or (src.get("kind") == "git" and src.get("commit")) or any(fetch_held(f) for f in fetch_rows(row)))
    return held and not unheld(row) and not unlocked(row)


def plan(row, version=""):
    """What would move in a row, with nothing written: a list of
    {"what", "old", "new", "apply", "note"}, each one part of the row (its
    own download, its commit, a declared download). `apply` writes the part
    into a copy of the row. A part that is as its entry pins it is listed
    with old and new alike."""
    src = row.get("source") or {}
    parts = []
    pin = sdkmeta.pin_of(row)
    if pin is not None:
        tracked = bool(src.get("version")) or bool(version)
        old_v = str(pin.get("version") or "")
        if tracked:
            with As(platforms(row)[0]):
                new_v = version or sdkmeta.newest(row)[0]
            got, held = None, ""
            if new_v != old_v or version:
                try:
                    got = learned(row, version)
                except Refused as e:
                    # A version named by hand that cannot be learned is an
                    # error. One its resolver finds is a release that is not
                    # out for every platform the row names yet: the row
                    # stays where it is until it is, and says so.
                    if version:
                        raise
                    held = f"its resolver finds {new_v}, and {e}"
            if got and got["version"] == old_v:
                # The version it has, named again: a move only where its
                # publisher's file is no longer the pinned one.
                have = pinned_files(row)
                if all(have[p] == (f["url"], f["sha256"]) for p, f in got["files"].items()):
                    got = None
            if held:
                parts.append({"what": "its download", "old": old_v, "new": old_v, "held": held, "note": f"{held}: it stays where it is"})
            elif got is None:
                parts.append({"what": "its download", "old": old_v, "new": old_v, "note": "its resolver finds the version it is pinned to"})
            else:
                parts.append({"what": "its download", "old": old_v, "new": got["version"], "files": got["files"],
                              "apply": lambda r, got=got: write_pin(r, got, (r["source"]["checksum"] or {}).get("found"))})
        else:
            # Nothing says how a newer one is found: a file with no version
            # in its address, or one nobody tracks. Its address is asked for
            # the bytes it answers today.
            have = pinned_files(row)
            got = {"version": old_v, "supplied": False, "files": {}}
            for plat, (url, digest) in have.items():
                try:
                    now = hashed(url)["sha256"]
                except ERRORS as e:
                    raise Refused(f"{plat or 'its download'} could not be fetched ({said(e)})") from e
                got["files"][plat] = {"url": url, "sha256": now, "how": "downloaded and hashed here", "was": digest}
            moved = [p for p, f in got["files"].items() if f["sha256"] != f["was"]]
            if moved:
                parts.append({"what": "its download", "old": "the pinned bytes", "new": "other bytes", "files": got["files"],
                              "note": "its vendor changed the file at " + ", ".join(got["files"][p]["url"] for p in moved),
                              "apply": lambda r, got=got: write_pin(r, got, (r["source"]["checksum"] or {}).get("found"))})
            else:
                parts.append({"what": "its download", "old": old_v or "the pinned bytes", "new": old_v or "the pinned bytes",
                              "note": "its address still answers the pinned bytes"})
    if src.get("kind") == "git" and src.get("commit"):
        if isinstance(src.get("track"), dict):
            got = git_learned(row)
            old = f"{src.get('tag') or ''} {str(src['commit'])[:12]}".strip()
            new = f"{got['tag']} {got['commit'][:12]}".strip()
            part = {"what": "its commit", "old": old, "new": new}
            if got["commit"] != src["commit"] or (got["tag"] and got["tag"] != src.get("tag")):
                part["apply"] = lambda r, got=got: r["source"].update({"commit": got["commit"], **({"tag": got["tag"]} if got["tag"] else {})})
            else:
                part["new"] = old
            parts.append(part)
        else:
            parts.append({"what": "its commit", "old": str(src["commit"])[:12], "new": str(src["commit"])[:12], "note": "it says no source.track: nothing to ask"})
    return parts + declared_parts(row) + lock_parts(row)


def declared_parts(row, waiting=False):
    """plan's parts for what a row declares, a part a download. Each is
    asked by its own track, so a row of several tools moves the ones that
    have a newer release and leaves the others, and downloads that say one
    track move together. With `waiting`, only the downloads held to
    nothing yet: what a first pin fills in."""
    parts, cache = [], {}
    for f in fetch_rows(row):
        # A lock's downloads are its lock's to move, as one set (lock_parts).
        if (waiting and fetch_held(f)) or packformat.lock_of(locks(row), f.get("to")):
            continue
        what = fetch_said(f)
        try:
            got = fetch_learned(row, f, cache)
        except ERRORS as e:
            raise Refused(f"{what} could not be learned ({said(e)})") from e
        old = f"{f.get('version') or ''} {str(f.get('sha256') or '')[:12]}".strip() if fetch_held(f) else ""
        new = f"{got['version']} {got['sha256'][:12]}".strip()
        part = {"what": what, "old": old, "new": new, "note": got["how"]}
        changed = {k: got[k] for k in ("version", "sha256") if got[k] and got[k] != f.get(k)}
        if got["url"] != sdkmeta.declared_address({**f, "version": got["version"]}):
            changed["url"] = got["url"]
        if changed:
            key = (f.get("to"), str(f.get("platform") or ""))
            part["apply"] = lambda r, key=key, changed=changed: fetch_write(fetch_of(r, *key), changed)
        else:
            part["new"] = old
        parts.append(part)
    return parts


def moved(row, parts):
    """`row` with every part that moves applied and its rev raised by one,
    or None where nothing moves. Refused where the result is no row the
    format takes."""
    todo = [p for p in parts if p.get("apply")]
    if not todo:
        return None
    new = copy.deepcopy(row)
    for p in todo:
        p["apply"](new)
    new["rev"] = catalogrows.rev_of(row) + 1
    why = packformat.source_refused(new.get("source"))
    if why:
        raise Refused(f"what it would become is refused: {why}")
    return new


def lines(name, parts):
    """What a row's parts say, a line each, with a line a platform under a
    download that moves."""
    out = []
    for p in parts:
        same = not p.get("apply")
        now = p["new"] or "the bytes its address answers today"
        head = f"{name}: {p['what']} " + (f"is at {p['old'] or 'its pin'}" if same else f"{p['old']} to {now}" if p["old"] else f"pinned at {now}")
        out.append(head + (f" ({p['note']})" if p.get("note") else ""))
        for plat, f in (p.get("files") or {}).items() if not same else ():
            out.append(f"    {plat or 'every platform'}  sha256 {f['sha256']}  {f['how']}")
            out.append(f"    {' ' * len(plat or 'every platform')}  {f['url']}")
    return out


# ---- the verbs ----------------------------------------------------------------
def load(path):
    with open(path, encoding="utf-8") as f:
        return json.load(f)


def save(path, doc):
    """The table as it is laid out, so a move's diff is the lines that
    changed and no others."""
    with open(path, "w", encoding="utf-8") as f:
        f.write(json.dumps(doc, indent=2, ensure_ascii=False) + "\n")


def chosen(doc, names):
    """The rows named, in the table's order; every one with none named."""
    rows = doc["toolchains"]
    have = {r.get("name") for r in rows}
    missing = [n for n in names if n not in have]
    if missing:
        raise Refused(f"no toolchain named {', '.join(missing)} in the table")
    return [r for r in rows if not names or r.get("name") in names]


def cmd_check(doc, names, opts, out):
    would, failed, waiting = 0, 0, 0
    for row in chosen(doc, names):
        name = row["name"]
        if not is_pinned(row):
            if names:
                out(f"{name}: not pinned ({packformat.held(row)[1]})")
            continue
        try:
            parts = plan(row)
        except ERRORS as e:
            out(f"{name}: could not be asked: {said(e)}")
            failed += 1
            continue
        for line in lines(name, parts):
            out(line)
        # A release that is not out for every platform holds its row
        # whole: nothing of that row would move.
        if any(p.get("held") for p in parts):
            waiting += 1
        else:
            would += any(p.get("apply") for p in parts)
    out((f"{would} row(s) would move" if would else "nothing would move")
        + (f"; {waiting} row(s) wait for a release that is not out for every platform they name" if waiting else ""))
    return 1 if failed else 3 if would else 0


def cmd_move(doc, names, opts, out):
    changed, failed = 0, 0
    rows = doc["toolchains"]
    for row in chosen(doc, names):
        name = row["name"]
        if not is_pinned(row):
            if names:
                out(f"{name}: not pinned: tools/pins.py pin {name} pins it")
                failed += 1
            continue
        try:
            parts = plan(row, opts.get("version", ""))
            # A row moves whole: a part held back holds every part of it.
            held = next((p["held"] for p in parts if p.get("held")), "")
            if held:
                raise Refused(held)
            new = moved(row, parts)
        except ERRORS as e:
            out(f"{name}: left as it was: {said(e)}")
            failed += 1
            continue
        if new is None:
            out(f"{name}: nothing to move")
            continue
        for line in lines(name, [p for p in parts if p.get("apply")]):
            out(line)
        out(f"{name}: rev {catalogrows.rev_of(row)} to {new['rev']}")
        rows[rows.index(row)] = new
        changed += 1
    return finish(doc, opts, out, changed, failed)


def cmd_pin(doc, names, opts, out):
    if len(names) != 1:
        raise Refused("pin takes one NAME")
    row = chosen(doc, names)[0]
    try:
        return pin_row(doc, row, opts, out)
    except Refused as e:
        raise Refused(f"{row['name']} is left as it was: {e}") from e


def pin_row(doc, row, opts, out):
    name, src = row["name"], row.get("source") or {}
    new = copy.deepcopy(row)
    # Its own source, where that is not pinned yet: a repository's commit,
    # a tarball's or a script's file.
    kind = src.get("kind")
    own = (kind == "git" and not src.get("commit")) or (kind in ("tarball", "script") and not sdkmeta.pin_of(row))
    waiting = unheld(row) or unlocked(row)
    if not own and not waiting:
        if kind in ("git", "tarball", "script") or fetch_rows(row):
            raise Refused(f"it is pinned already: tools/pins.py move {name} moves it")
        raise Refused(f"it has no download of its own to pin, and declares none: its source is of kind {kind}")
    if own and kind == "git":
        got = git_learned(row)
        new["source"].update({"commit": got["commit"], **({"tag": got["tag"]} if got["tag"] else {})})
        out(f"{name}: its commit pinned at {got['tag']} {got['commit']}".replace("  ", " "))
    elif own:
        got = learned(row, opts.get("version", ""))
        write_pin(new, got, src.get("checksum"))
        for line in lines(name, [{"what": "its download", "old": "", "new": got["version"], "files": got["files"], "apply": True}]):
            out(line)
    # What it declares and holds to nothing yet, and what it asks a
    # package manager for and has no files for yet: every one of them, or
    # the row is left as it was.
    if waiting:
        parts = declared_parts(row, waiting=True) + lock_parts(row, waiting=True)
        for p in parts:
            p["apply"](new)
        for line in lines(name, parts):
            out(line)
    new["rev"] = catalogrows.rev_of(row) + 1
    why = packformat.source_refused(new["source"])
    if why:
        raise Refused(f"what it would become is refused: {why}")
    doc["toolchains"][doc["toolchains"].index(row)] = new
    word, why = packformat.held(new)
    out(f"{name}: rev {catalogrows.rev_of(row)} to {new['rev']}; it reads {word}" + (f" ({why})" if word == "open" else ""))
    return finish(doc, opts, out, 1, 0)


def finish(doc, opts, out, changed, failed):
    """Write the table where something changed, and the official packs
    from it where it is the shipped one."""
    if changed:
        save(opts["file"], doc)
        if os.path.abspath(opts["file"]) == os.path.abspath(TABLE):
            p = subprocess.run([sys.executable, os.path.join(HERE, "packs-export.py"), "--write"], capture_output=True, text=True, check=False)
            out((p.stdout + p.stderr).strip())
            failed += bool(p.returncode)
    return 1 if failed else 0


def cmd_verify(doc, names, opts, out):
    bad, seen = 0, 0
    for row in chosen(doc, names):
        name, src = row["name"], row.get("source") or {}
        if not is_pinned(row):
            continue
        files = []
        try:
            if sdkmeta.pin_of(row):
                plats = platforms(row) if opts.get("all") else [opts.get("platform", "")]
                with As(plats[0]):
                    there = sdkmeta.pinned_digest(row)
                if not there and not opts.get("all"):
                    out(f"{name}: it names no download for {plats[0] or sdkmeta.this_platform()}")
                    plats = []
                files += [(f"its download{' for ' + p if p else ''}", u, d) for p, (u, d) in pinned_files(row, plats).items()]
            for f in fetch_rows(row):
                plat = str(f.get("platform") or "")
                with As(opts.get("platform", "")):
                    mine = opts.get("all") or sdkmeta.on_platform(plat)
                if not mine:
                    continue
                if not f.get("sha256"):
                    out(f"{name}: {f.get('to')} is held by its publisher's signature, which an install checks: not hashed here")
                    continue
                files.append((f"{f.get('to')}{' for ' + plat if plat else ''}", sdkmeta.declared_address(f), f["sha256"]))
            if src.get("kind") == "git" and src.get("commit") and src.get("tag"):
                # A commit is held by its own hash at the fetch; what can
                # move under a row is the tag it names beside it.
                with As():
                    got = sdkmeta.git_newest(row, {"resolver": "git-tag", "match": "^" + re.escape(src["tag"]) + "$"})
                seen += 1
                if got[1] != src["commit"]:
                    out(f"{name}: NOT ITS PIN: the tag {src['tag']} of {src['url']} is at {got[1]}, and the row pins {src['commit']}")
                    bad += 1
                else:
                    out(f"{name}: the tag {src['tag']} is at the pinned commit {src['commit'][:12]}")
        except ERRORS as e:
            out(f"{name}: could not be verified: {said(e)}")
            bad += 1
            continue
        for what, url, want in files:
            seen += 1
            try:
                got = hashed(url)
            except ERRORS as e:
                out(f"{name}: NOT VERIFIED: {what}, {url}: {said(e)}")
                bad += 1
                continue
            if got["sha256"] != want:
                out(f"{name}: NOT ITS PIN: {what}, {url} answers sha256 {got['sha256']}, and the row pins {want}")
                bad += 1
            else:
                out(f"{name}: {what} is its pin ({got['bytes']} bytes, sha256 {want[:12]})")
    out(f"{bad} of {seen} pinned file(s) are not their pin" if bad else f"every one of the {seen} pinned file(s) asked for is its pin")
    return 1 if bad else 0


VERBS = {"check": cmd_check, "move": cmd_move, "pin": cmd_pin, "verify": cmd_verify}


def main(argv, out=print):
    opts, names = {"file": TABLE}, []
    args = list(argv)
    while args:
        a = args.pop(0)
        if a in ("--file", "--version", "--platform"):
            if not args:
                out(f"{a} takes a value")
                return 1
            opts[a[2:]] = args.pop(0)
        elif a == "--all":
            opts["all"] = True
        elif a.startswith("-"):
            out(__doc__.strip())
            return 0 if a in ("-h", "--help") else 1
        else:
            names.append(a)
    if not names or names[0] not in VERBS:
        out(__doc__.strip())
        return 1
    verb, names = names[0], names[1:]
    if opts.get("version") and (verb not in ("pin", "move") or len(names) != 1):
        out("--version goes with pin or move and one NAME")
        return 1
    if opts.get("platform") and not packformat.PLATFORM_KEY.fullmatch(opts["platform"]):
        out(f"{opts['platform']} is no platform a row names: linux/amd64, linux/arm64, linux-musl/amd64, darwin/arm64, ...")
        return 1
    try:
        doc = load(opts["file"])
        if not isinstance(doc.get("toolchains"), list):
            raise ValueError("it has no list of toolchains")
    except (OSError, ValueError, AttributeError) as e:
        out(f"pins: cannot read {opts['file']}: {said(e)}")
        return 1
    try:
        return VERBS[verb](doc, names, opts, out)
    except ERRORS as e:
        out(f"pins: {said(e)}")
        return 1


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
