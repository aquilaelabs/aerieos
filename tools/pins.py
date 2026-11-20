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
                                      track finds now and its digest.
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
import copy
import hashlib
import json
import os
import re
import subprocess
import sys
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
        return "git did not answer in time"
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


def fetch_learned(row, f, cache):
    """What a declared download would be now: {"version", "url", "sha256",
    "how"}. One that says track is asked for its newest version, once for
    every download that says the same track; one that says none has
    nothing to track, and its address is asked for the bytes it answers
    today."""
    track = f.get("track") if isinstance(f.get("track"), dict) else None
    plat = str(f.get("platform") or "")
    version, url = str(f.get("version") or ""), ""
    with As(plat):
        if track:
            key = json.dumps(track, sort_keys=True) + "\0" + plat
            if key not in cache:
                if track.get("resolver") in packformat.GIT_RESOLVERS:
                    # A repository's tag as the version in a file's name.
                    cache[key] = (sdkmeta.trimmed(sdkmeta.git_newest({**row, "source": {"url": track.get("url")}}, track)[0], track), "")
                else:
                    cache[key] = sdkmeta.newest(row, track)
            version, url = cache[key]
        url = url or sdkmeta.declared_address({**f, "version": version})
        if isinstance(f.get("signed"), dict):
            return {"version": version, "url": url, "sha256": "", "how": "held by its publisher's signature"}
        digest, how = digest_of(row, url, version, f.get("found"))
    return {"version": version, "url": url, "sha256": digest, "how": how}


# ---- what a row is, and what would move ---------------------------------------
def is_pinned(row):
    """Whether a row has anything pinned for check and move to ask about. A
    row with a download still waiting for its first pin is `pin`'s."""
    src = row.get("source") or {}
    held = bool(sdkmeta.pin_of(row) or (src.get("kind") == "git" and src.get("commit")) or any(fetch_held(f) for f in fetch_rows(row)))
    return held and not unheld(row)


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
    return parts + declared_parts(row)


def declared_parts(row, waiting=False):
    """plan's parts for what a row declares, a part a download. Each is
    asked by its own track, so a row of several tools moves the ones that
    have a newer release and leaves the others, and downloads that say one
    track move together. With `waiting`, only the downloads held to
    nothing yet: what a first pin fills in."""
    parts, cache = [], {}
    for f in fetch_rows(row):
        if waiting and fetch_held(f):
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
            part["apply"] = lambda r, key=key, changed=changed: fetch_of(r, *key).update(changed)
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
    waiting = unheld(row)
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
    # What it declares and holds to nothing yet: every one of them, or the
    # row is left as it was.
    if waiting:
        parts = declared_parts(row, waiting=True)
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
