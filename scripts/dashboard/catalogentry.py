"""An index entry, written from the folder it pins.

An entry of the catalog's signed index is never typed. What it repeats of
its manifest (the pack format, the framework's version, the platforms, the
label, the release lines it works with, what its downloads are held to, a
recipe's rev: packformat.ENTRY_PIN) is read from the folder's own manifest
at the commit the entry pins, fetched and held as the install that takes
the entry fetches it, so an entry written here is one an install takes.
What is the entry's own (its tier, its topics, the day it was added,
whether it is withdrawn) is kept from the entry the index has.

    said_at     what a folder says at a commit: the pin, and what of its
                manifest an entry says once
    entry_with  an entry with that pin placed by its pack format, the pin
                it had kept as an older one where the format went up
    drop_older  an index's entries without the older pins of one format
    differs     what an entry says that its folder at its pin does not

tools/packs-export.py writes the catalog's index with these, and the
catalog's own check, which loads this beside toolpacks.py from a checkout,
holds every entry to the same reading (differs).
"""
import json
import time

import catalogrows
import nasapps
import packformat
import toolpacks

# An entry's keys in the order the index writes them: what it is, its
# newest pin, what else it says, and its older pins last.
ORDER = ("name", "kind", "agent", "url", "commit", "path", "sha256", "tier", "withdrawn", "about", "platforms", "format", "label", "maker",
         "framework", "works_with", "held", "online", "install_rev", "shipped_rev", "topics", "added", "older")


def said_at(url, commit, sha256, folder, kind="pack", official=False):
    """(pin, own, why): what the folder `folder` of the repository at `url`
    says at `commit`, its archive held to `sha256`, read from its own
    manifest as an install reads it. `pin` is what moves with a pin
    (packformat.ENTRY_PIN); `own` what the manifest says that an entry says
    once (its name, its kind, whether it brings a coding agent, what it is
    about, who it is by). `kind` "app" reads a Docker app's bbapp.json and
    compose; `official` says the entry is one of AerieOS's own, as the
    signed index's tier says it to an install."""
    pin, own = {"commit": commit, "sha256": sha256}, {}
    if kind == "app":
        # A Docker app, held as an install keeps one (nasapps.add_catalog).
        got = toolpacks.fetch_folder(url, commit, sha256, folder, ("bbapp.json", "compose.yml"))
        if got.get("error"):
            return None, None, got["error"]
        try:
            meta = json.loads(got["files"]["bbapp.json"].decode("utf-8"))
            compose = got["files"]["compose.yml"].decode("utf-8")
        except (ValueError, UnicodeDecodeError):
            return None, None, "its bbapp.json is not JSON"
        fmt = packformat.of(meta) if isinstance(meta, dict) else None
        if fmt is None or packformat.too_new(fmt):
            return None, None, "its bbapp.json says a format that is no number" if fmt is None else packformat.too_new(fmt)
        late = packformat.needs(meta, packformat.uses_of(meta))
        seen = {"error": late[0]} if late else nasapps.check_app(meta, compose)
        if seen.get("error"):
            return None, None, seen["error"]
        m = {"name": str(meta.get("name") or ""), "format": fmt, "framework": packformat.said(packformat.framework_of(meta)),
             "label": " ".join(str(meta.get("label") or "").split()), "works_with": [],
             "platforms": [x for x in meta.get("platforms") or [] if isinstance(x, str)], "about": " ".join(str(meta.get("about") or "").split()),
             "maker": packformat.maker_of(meta)}
        held = nasapps.held_of({"compose": compose})
        own["kind"] = "app"
    else:
        if official:
            # One of AerieOS's own: its manifest alone, as large as a shipped
            # row's recipe is, read as a newer recipe is (catalogrows.refresh);
            # an agent's or a service's is held to a pack's own size, as the
            # fetch that reads those holds it.
            got = toolpacks.fetch_folder(url, commit, sha256, folder, (toolpacks.MANIFEST,))
            if got.get("error"):
                return None, None, got["error"]
            raw = got["files"][toolpacks.MANIFEST]
            try:
                doc = json.loads(raw.decode("utf-8"))
            except (ValueError, UnicodeDecodeError):
                return None, None, f"its {toolpacks.MANIFEST} is not JSON"
            if not (isinstance(doc, dict) and isinstance(doc.get("shipped"), dict)) and len(raw) > toolpacks.MANIFEST_MAX:
                return None, None, f"{toolpacks.MANIFEST} is over {toolpacks.MANIFEST_MAX // 1024} KB"
            m, errors = toolpacks.validate(doc, (), official=True)
            if errors:
                return None, None, f"{toolpacks.MANIFEST} needs fixing: " + "; ".join(errors)
            held = packformat.held_of(m)
        else:
            got = toolpacks.fetch(url, commit, (), sha256, folder)
            if got.get("error"):
                return None, None, got["error"]
            m, held = got["manifest"], got["held"]
        if m.get("service"):
            own["kind"] = "service"
        # A pack that brings a coding agent says so, and the Library files
        # its card with the agents before it is added.
        if m.get("pack_agent"):
            own["agent"] = True
        # A shipped coding agent's recipe's rev, and a shipped toolchain's
        # past the first, so an install fetches the pack only for a newer one.
        rev = ((m.get("agent") or {}).get("install") or {}).get("rev")
        if rev:
            pin["install_rev"] = rev
        if catalogrows.rev_of(m.get("shipped")) > 1:
            pin["shipped_rev"] = catalogrows.rev_of(m["shipped"])
    # An index names a shipped toolchain with its colon as a hyphen.
    own.update(name=m["name"].replace(":", "-"), about=m["about"] or m["label"], **({"maker": m["maker"]} if m.get("maker") else {}))
    pin["platforms"] = list(m["platforms"])
    if m["format"] > 1:
        pin["format"] = m["format"]
    if m["label"] and m["label"] != m["name"]:
        pin["label"] = m["label"][:60]
    # The framework's version it is written for, where that is past its format alone.
    if not m["framework"].endswith(".0"):
        pin["framework"] = m["framework"]
    if m.get("works_with"):
        pin["works_with"] = list(m["works_with"])
    # What its downloads are held to, for its card before it is added.
    pin.update(packformat.held_entry(held))
    return pin, own, ""


def _older(pin):
    """A pin as one of an entry's older pins is written: what moves with a
    pin, its format said first and always. `pin` is a pin, or an entry
    whose newest pin is meant."""
    return {"format": packformat.of(pin), **{k: pin[k] for k in packformat.ENTRY_PIN if k in pin and k != "format"}}


def entry_with(was, pin, own, tier, url, folder, topics=None):
    """(entry, said): the index's entry `was` (None for a new one) with
    `pin` placed by its pack format, and what that did to the pins it held,
    in a few words. `topics` says what it is about in the place of what
    the entry had. A pin in a format past the entry's newest becomes its
    newest, and the pin that was there is kept under `older` for the
    releases that read only its format; one in the newest's format takes
    its place; one in an earlier format takes the place of the older pin of
    that format, or stands among them where there was none. No pin is
    dropped here (drop_older)."""
    was = was or {}
    fmt, had = pin.get("format", 1), packformat.of(was) if was else None
    older = [dict(o) for o in was.get("older") or []] if not packformat.older_refused(was) else []
    said, newest = "", True
    if had is not None and fmt < had:
        # An earlier format's pin: the entry's newest stays where it is.
        newest, new = False, _older(pin)
        at = next((i for i, o in enumerate(older) if o["format"] == fmt), None)
        if at is None:
            older = sorted([*older, new], key=lambda o: -o["format"])
            said = f"its pack format {fmt} pin is kept beside its newest ({had})"
        elif older[at] != new:
            older[at] = new
            said = f"its pack format {fmt} pin moved, beside its newest ({had})"
    elif had is not None and fmt > had:
        older = [_older(was), *older]
        said = f"pack format {had} to {fmt}: its format {had} pin is kept as an older one"
    entry = {**{k: v for k, v in was.items() if k != "older" and (not newest or k not in (*packformat.ENTRY_PIN, "kind", "agent"))},
             # What the manifest gives an entry that it says once is its newest pin's manifest's.
             **({**pin, **own} if newest else {}),
             "name": own["name"], "url": was.get("url") or url, "path": folder, "tier": tier, "withdrawn": was.get("withdrawn") is True,
             **({} if was else {"added": time.strftime("%Y-%m-%d", time.gmtime())}), **({"topics": list(topics)} if topics else {}),
             **({"older": older} if older else {})}
    return {k: entry[k] for k in (*ORDER, *sorted(set(entry) - set(ORDER))) if k in entry}, said


def drop_older(packs, fmt):
    """(entries, how many went): the entries with every older pin written
    in pack format `fmt` dropped. What the maintainers ask for by number,
    once no listed release takes those pins: a pin is still taken while,
    for some listed release, packformat.pin_for answers the entry at it."""
    out, n = [], 0
    for e in packs:
        keep = [o for o in e.get("older") or [] if not (isinstance(o, dict) and o.get("format") == fmt)]
        n += len(e.get("older") or []) - len(keep)
        out.append({k: v for k, v in e.items() if k != "older"} | ({"older": keep} if keep else {}))
    return out, n


def differs(entry, url=""):
    """What an index entry says of its pin that its folder at that commit
    does not, a sentence each, [] when they agree. `entry` is the entry as
    a build takes it (packformat.pin_for), so the catalog's check holds
    each release to the pin that release reads; `url` is where its
    repository is read from, when that is not the entry's own address (a
    checkout on disk). An entry's label may be left out, and what it says
    of itself that its manifest does not (its maker, where the manifest
    names none) is left alone."""
    pin, own, why = said_at(url or entry["url"], entry["commit"], entry["sha256"], entry.get("path") or "", entry.get("kind", "pack"),
                            official=entry.get("tier") == "official")
    if why:
        return [why]
    bad = []
    for k in packformat.ENTRY_PIN:
        if k in ("commit", "sha256") or (k == "label" and k not in entry):
            continue
        want, got = pin.get(k, 1 if k == "format" else None), entry.get(k, 1 if k == "format" else None)
        if k in ("platforms", "works_with"):
            want, got = sorted(want or []), sorted(got or [])
        elif k == "framework":
            # Left out, it is the format's own first version.
            want, got = want or f"{pin.get('format', 1)}.0", got or f"{pin.get('format', 1)}.0"
        if want != got:
            bad.append(f"the entry says {k} {got if got is not None else '(nothing)'} and its manifest {want if want is not None else '(nothing)'}")
    for k in ("name", "kind", "agent", "maker"):
        want, got = own.get(k, "pack" if k == "kind" else None), entry.get(k, "pack" if k == "kind" else None)
        if want != got and not (k == "maker" and want is None):
            bad.append(f"the entry says {k} {got if got is not None else '(nothing)'} and its manifest {want if want is not None else '(nothing)'}")
    return bad
