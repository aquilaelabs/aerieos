#!/usr/bin/env python3
"""The official packs (R169 step 1): every shipped toolchain
(config/toolchains.json) and every coding agent (agents.py's table) written
as a pack in bbtool.json's format under packs/, tagged official and
bundled with the release for an install with no network. One manifest
for everything: the installer and the agents' adapters still read their
own tables; the packs are those tables in the one format, and this
script's --check holds the two to each other in aerie lint.

    tools/packs-export.py --write     write packs/official/*/bbtool.json and packs/agents/*/bbtool.json
    tools/packs-export.py --check     fail when what is written is not what the tables say
    tools/packs-export.py --catalog DIR          write the same folders under DIR/packs/ (the catalog's checkout)
    tools/packs-export.py --catalog DIR --index  rewrite DIR/index.json's official entries from DIR's HEAD commit
    tools/packs-export.py --catalog DIR --entry FOLDER... [--commit REF] [--tier TIER] [--topics T,T]
                                                 write the index entry of any folder under DIR/packs from its own
                                                 manifest at REF (DIR's HEAD when none is named): a pack's bbtool.json or
                                                 an app's bbapp.json and compose. TIER for a folder with no entry yet;
                                                 T,T what the entries named are about, one to three of the catalog's topics.
    tools/packs-export.py --catalog DIR --drop-older N
                                                 drop every older pin written in pack format N; with --index or
                                                 --entry too, after they wrote
The catalog (R170 step 6, the operator: the shipped toolchains and agents live
in the catalog repository): every official pack is a folder of that repository,
and its index entry pins the catalog's own commit, the folder as `path`, and
the sha256 of `git archive --format=tar COMMIT PATH`. Two commits, since an
index cannot pin the commit that holds it: --catalog writes the folders to
commit first, --index then pins that commit; the maintainer signs the index.

No entry is typed: what an entry repeats of its manifest (its pack format, the
framework's version, its platforms, its label, the release lines it works with,
what its downloads are held to, a recipe's rev) is read from the folder at the
commit, fetched and held as an install would, and what is the entry's own (its
tier, its topics, the day it was added, whether it is withdrawn) is kept from
the entry the index has. A folder that is as one of its entry's pins has it
keeps that pin, whatever commit is asked for.

A pin is placed by its pack format. One in a format past the entry's newest
becomes its newest, and the pin that was there is kept under `older`, for the
releases that read only its format (packformat.pin_for); one in the newest's
format takes its place; one in an earlier format (--commit, a commit where the
folder holds the earlier manifest) takes the place of that format's older pin.
An older pin is dropped only by --drop-older, once no listed release takes it.
"""
import json
import os
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.dirname(HERE)
sys.path.insert(0, os.path.join(ROOT, "scripts", "dashboard"))
import agents    # noqa: E402
import catalogrows  # noqa: E402
import library  # noqa: E402
import packformat  # noqa: E402
import toolpacks  # noqa: E402

PACKS = os.path.join(ROOT, "packs")


def toolchain_packs():
    """[(path, manifest)] for every shipped toolchain."""
    with open(os.path.join(ROOT, "config", "toolchains.json"), encoding="utf-8") as f:
        rows = json.load(f)["toolchains"]
    out = []
    for r in rows:
        # The row as its manifest, by the one writer the controller reads
        # it back with (catalogrows.row_of) when the catalog's is newer.
        m = catalogrows.manifest_of(r)
        # The folder is the name with its colon as a hyphen (android:emulator
        # under android-emulator), a folder name every system takes.
        out.append((os.path.join(PACKS, "official", r["name"].replace(":", "-"), "bbtool.json"), m))
    return out


def agent_packs():
    """[(path, manifest)] for every coding agent the table lists."""
    out = []
    for a in agents.TABLE:
        m = {"name": a.id, "label": a.name, "about": f"{a.product}, run by sessions as {a.command}", "tier": "official",
             # Who the agent is by: its provider, or its maker where it runs
             # any provider's model.
             "maker": library.AGENT_MAKERS.get(a.id) or a.provider, "framework": "2.1",
             "platforms": ["linux/*"], "terms": [],
             # ...with how it is told a command needs no asking, where the
             # table says a way (agents.allow_plan).
             "agent": {k: getattr(a, k) for k in toolpacks.AGENT_FIELDS} | ({"allow": a.allow} if a.allow else {})
                      # ...and how it is installed (R169 step 13): the recipe
                      # the controller hands a node, which the catalog's copy
                      # replaces when its rev is higher.
                      | ({"install": a.install} if a.install else {})
                      # ...and how it signs in (R234 step 6), in the words a
                      # pack's agent says its own: the one driver runs both.
                      | ({"signin": a.signin} if a.signin else {})}
        # A recipe that holds what it fetches (its downloads declared, its
        # steps run from them) is pack format 5's, and the manifest says so.
        if (a.install or {}).get("steps"):
            m["format"] = packformat.HELD_FORMAT
        # The framework version it needs: the least that holds what it uses.
        m["framework"] = packformat.least(m, toolpacks._agent_uses({"signin": a.signin or {}})) or m["framework"]
        out.append((os.path.join(PACKS, "agents", a.id, "bbtool.json"), m))
    return out


def service_packs():
    """[(path, manifest)] for every deployed thing of AerieOS's that is a pack (R172)."""
    import services
    return [(os.path.join(PACKS, "services", m["name"], "bbtool.json"), m) for m in services.packs()]


def text(m):
    return json.dumps(m, indent=1, sort_keys=True) + "\n"


def catalog_dir_paths(root):
    """[(path under DIR, manifest, index name)] for every official pack."""
    out = []
    for path, m in toolchain_packs() + agent_packs() + service_packs():
        rel = os.path.relpath(path, PACKS)                     # official/NAME/bbtool.json
        out.append((os.path.join(root, "packs", rel), m, rel.split(os.sep)[1]))
    return out


def catalog_write(root):
    n = 0
    for path, m, _name in catalog_dir_paths(root):
        os.makedirs(os.path.dirname(path), exist_ok=True)
        with open(path, "w", encoding="utf-8") as f:
            f.write(text(m))
        n += 1
    print(f"  wrote {n} official pack(s) under {os.path.join(root, 'packs')}")


# ---- the catalog's index entries ------------------------------------------------
# An entry is written from the folder it pins, never typed
# (scripts/dashboard/catalogentry.py): this is the part that reads the
# catalog's checkout and writes its index.json.
OWN_FOLDERS = ("packs/official/", "packs/agents/", "packs/services/")
CATALOG_URL = "https://github.com/aquilaelabs/aerieos-catalog"


def _git(root, *args, text=True):
    import subprocess
    return subprocess.run(["git", "-C", root, *args], capture_output=True, text=text, check=False)


def catalog_url(root):
    """The address the catalog's own entries are pinned under: its origin's."""
    return (_git(root, "remote", "get-url", "origin").stdout.strip() or CATALOG_URL).removesuffix(".git")


def index_read(root):
    try:
        with open(os.path.join(root, "index.json"), encoding="utf-8") as f:
            idx = json.load(f)
    except (OSError, ValueError):
        idx = {}
    return idx if isinstance(idx, dict) and isinstance(idx.get("packs"), list) else {"version": 1, "packs": []}


def index_write(root, idx, packs):
    """The index with these entries, stamped now, and whether it was
    written: one whose entries are all as they were is left alone, its date
    with it. What it says beside its entries (the first AerieOS that reads
    each pack format) is kept as it was."""
    import time
    if packs == idx.get("packs") and idx.get("version") == 1:
        print(f"  {os.path.join(root, 'index.json')} is as it was: nothing to write")
        return False
    idx = {**{k: v for k, v in idx.items() if k not in ("version", "generated", "packs")},
           "version": 1, "generated": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()), "packs": packs}
    with open(os.path.join(root, "index.json"), "w", encoding="utf-8") as f:
        json.dump(idx, f, indent=1)
        f.write("\n")
    # A format an entry is written in and the index does not date is said:
    # the catalog's own check refuses to sign an index that leaves it out.
    since = idx.get("formats") if isinstance(idx.get("formats"), dict) else {}
    for fmt in sorted({p.get("format", 1) for e in packs for p in (e, *(e.get("older") or [])) if isinstance(p.get("format", 1), int)}):
        if fmt > 1 and str(fmt) not in since:
            print(f"  [note] the index's formats does not say which AerieOS first reads pack format {fmt}: add it before signing")
    return True


def entry_at(root, folder, commit, was=None, tier="", url="", topics=None):
    """(entry, said, why) for one folder under the catalog's packs/ at
    `commit`: its index entry written from its own manifest there
    (catalogentry.said_at, the folder fetched from the checkout as an
    install fetches it), over the entry the index holds for it (`was`).
    The tier is the entry's own: official for the folders AerieOS's own
    packs are kept in, else the one it has, else the one named."""
    import hashlib
    import catalogentry
    folder = folder.strip("/")
    tier = "official" if folder.startswith(OWN_FOLDERS) else tier or (was or {}).get("tier") or ""
    if tier not in packformat.TIERS or (tier == "official") != folder.startswith(OWN_FOLDERS):
        return None, "", f"it has no entry yet: name its tier with --tier ({', '.join(t for t in packformat.TIERS if t != 'official')})"
    tree = _git(root, "rev-parse", "--verify", "-q", f"{commit}:{folder}").stdout.strip()
    if not tree:
        return None, "", f"it is not in the catalog at {commit[:12]}"
    # A folder that is as one of the entry's pins has it (the same tree at
    # that pin's commit) keeps that pin: an archive names its commit, so a
    # new commit alone would read as a new pin, and everything kept from
    # the entry would be offered an update that changes nothing.
    for held in (was or {}), *((was or {}).get("older") or []):
        at = str(held.get("commit") or "") if isinstance(held, dict) else ""
        if at and at != commit and _git(root, "rev-parse", "--verify", "-q", f"{at}:{folder}").stdout.strip() == tree:
            commit = at
            break
    tar = _git(root, "archive", "--format=tar", commit, folder, text=False)
    if tar.returncode != 0:
        return None, "", f"it is not in the catalog at {commit[:12]}"
    # A Docker app is the folder with a bbapp.json; any other is a pack.
    kind = "app" if _git(root, "cat-file", "-e", f"{commit}:{folder}/bbapp.json").returncode == 0 else "pack"
    os.environ["BB_TOOLPACKS_FILE_URLS"] = "1"
    pin, own, why = catalogentry.said_at("file://" + os.path.abspath(root), commit, hashlib.sha256(tar.stdout).hexdigest(), folder, kind,
                                         official=tier == "official")
    if why:
        return None, "", why
    if was and was.get("name") != own["name"]:
        return None, "", f"its manifest names it {own['name']}, and its entry is {was.get('name')}"
    if not (own.get("maker") or (was or {}).get("maker")):
        return None, "", "its manifest names no maker: an entry says who its tool is by"
    if topics and packformat.topics_refused({"topics": topics}):
        return None, "", packformat.topics_refused({"topics": topics})
    entry, said = catalogentry.entry_with(was, pin, own, tier, url or catalog_url(root), folder, topics)
    return entry, said, ""


def dropped(packs, drop):
    """The entries with the older pins of each format named dropped, said."""
    import catalogentry
    for fmt in drop:
        packs, n = catalogentry.drop_older(packs, fmt)
        print(f"  dropped {n} older pin(s) written in pack format {fmt}")
    return packs


def catalog_head(root):
    """The catalog's HEAD commit, or "" with the reason said: packs/ must
    be committed, since an entry pins a commit that holds its folder."""
    head = _git(root, "rev-parse", "HEAD").stdout.strip()
    if not head or _git(root, "status", "--porcelain", "packs").stdout.strip():
        print("  [FAIL] packs/ in the catalog is not committed: commit the folders first, then the index pins that commit")
        return ""
    return head


def catalog_index(root, drop=()):
    """DIR/index.json with an official entry per pack exported from this
    tree, each written from its folder at DIR's HEAD (entry_at); other
    entries kept. An entry that moves to a newer pack format keeps the pin
    it had as an older one."""
    head = catalog_head(root)
    if not head:
        return 1
    idx, url = index_read(root), catalog_url(root)
    have = {p.get("name"): p for p in idx["packs"] if isinstance(p, dict) and p.get("tier") == "official"}
    kept = [p for p in idx["packs"] if isinstance(p, dict) and p.get("tier") != "official"]
    new, bad = [], 0
    for path, _m, name in catalog_dir_paths(root):
        folder = os.path.relpath(os.path.dirname(path), root)
        entry, said, why = entry_at(root, folder, head, have.get(name), "official", url)
        if why:
            print(f"  [FAIL] {name}: {why}")
            bad += 1
            continue
        if said:
            print(f"  {name}: {said}")
        new.append(entry)
    if bad:
        print("  nothing was written")
        return 1
    if index_write(root, idx, dropped(new + kept, drop)):
        moved = sum(1 for e in new if e != have.get(e["name"]))
        print(f"  wrote {len(new)} official entries from {head[:12]} ({moved} changed, {len(kept)} others kept) in {os.path.join(root, 'index.json')}; sign it")
    return 0


def catalog_entries(root, folders, commit="", tier="", drop=(), topics=None):
    """DIR/index.json with the entry of each folder named, any folder under
    DIR/packs, written from its own manifest at `commit` (DIR's HEAD when
    none is named): in the place of the entry the index has for it, or
    after the others where it has none. Nothing else of the index changes."""
    head = catalog_head(root)
    if not head:
        return 1
    if commit:
        got = _git(root, "rev-parse", "--verify", f"{commit}^{{commit}}").stdout.strip()
        if not got:
            print(f"  [FAIL] {commit} is no commit of the catalog")
            return 1
        commit = got
    idx, url = index_read(root), catalog_url(root)
    packs, bad = [p for p in idx["packs"] if isinstance(p, dict)], 0
    for folder in folders:
        folder = os.path.relpath(os.path.abspath(folder), os.path.abspath(root)) if os.path.isabs(folder) else folder.strip("/")
        if not folder.startswith("packs/") or ".." in folder.split("/"):
            print(f"  [FAIL] {folder}: an entry's folder is under the catalog's packs/")
            bad += 1
            continue
        at = next((i for i, p in enumerate(packs) if (p.get("path") or "").strip("/") == folder), None)
        entry, said, why = entry_at(root, folder, commit or head, packs[at] if at is not None else None, tier, url, topics)
        if why:
            print(f"  [FAIL] {folder}: {why}")
            bad += 1
            continue
        if at is None and any(p.get("name") == entry["name"] for p in packs):
            print(f"  [FAIL] {folder}: the index has another entry named {entry['name']}")
            bad += 1
            continue
        was = packs[at] if at is not None else None
        print(f"  {entry['name']}: " + ("as the index has it" if entry == was else (said or (f"pinned at {entry['commit'][:12]}" if was else f"added at {entry['commit'][:12]}"))))
        if at is None:
            packs.append(entry)
        else:
            packs[at] = entry
    if bad:
        print("  nothing was written")
        return 1
    if index_write(root, idx, dropped(packs, drop)):
        print(f"  wrote {os.path.join(root, 'index.json')}; sign it")
    return 0


def catalog_drop(root, drop):
    """DIR/index.json with the older pins of the formats named dropped,
    and nothing else changed."""
    idx = index_read(root)
    if index_write(root, idx, dropped([p for p in idx["packs"] if isinstance(p, dict)], drop)):
        print(f"  wrote {os.path.join(root, 'index.json')}; sign it")
    return 0


def _values(argv, flag):
    """The values after `flag` up to the next flag, for each time it is said."""
    out = []
    for i, a in enumerate(argv):
        if a == flag:
            for v in argv[i + 1:]:
                if v.startswith("--"):
                    break
                out.append(v)
    return out


def main(argv):
    want = toolchain_packs() + agent_packs() + service_packs()
    if "--catalog" in argv:
        root = (_values(argv, "--catalog") or [""])[0]
        if not os.path.isdir(os.path.join(root, "packs")):
            print("  [FAIL] --catalog names a checkout of the catalog, with its packs/")
            return 1
        drop = _values(argv, "--drop-older")
        if not all(d.isdigit() and int(d) >= 1 for d in drop) or ("--drop-older" in argv and not drop):
            print("  [FAIL] --drop-older names the pack format whose older pins go, a whole number")
            return 1
        drop = [int(d) for d in drop]
        if "--index" in argv:
            return catalog_index(root, drop)
        if "--entry" in argv:
            folders = _values(argv, "--entry")
            if not folders:
                print("  [FAIL] --entry names a folder under the catalog's packs/")
                return 1
            topics = [t for v in _values(argv, "--topics") for t in v.split(",") if t]
            return catalog_entries(root, folders, (_values(argv, "--commit") or [""])[0], (_values(argv, "--tier") or [""])[0], drop, topics)
        if drop:
            return catalog_drop(root, drop)
        bad = sum(1 for _p, m in want if toolpacks.validate(m, shipped=(), official=True)[1])
        if bad:
            return 1
        catalog_write(root)
        return 0
    bad = 0
    # Official by these tables' word: each manifest is written from a row
    # AerieOS ships (validate takes that from its caller, never the manifest).
    for path, m in want:
        clean, errors = toolpacks.validate(m, shipped=(), official=True)
        if errors:
            print(f"  [FAIL] {os.path.relpath(path, ROOT)}: " + "; ".join(errors))
            bad += 1
    if bad:
        return 1
    if "--write" in argv:
        for path, m in want:
            os.makedirs(os.path.dirname(path), exist_ok=True)
            with open(path, "w", encoding="utf-8") as f:
                f.write(text(m))
        print(f"  wrote {len(want)} pack(s) under packs/")
        return 0
    wanted = {os.path.relpath(p, ROOT) for p, _ in want}
    for path, m in want:
        try:
            with open(path, encoding="utf-8") as f:
                have = f.read()
        except OSError:
            have = ""
        if have != text(m):
            print(f"  [FAIL] {os.path.relpath(path, ROOT)} is not what the table says: tools/packs-export.py --write rewrites it")
            bad += 1
    for sub in ("official", "agents", "services"):
        d = os.path.join(PACKS, sub)
        for name in (os.listdir(d) if os.path.isdir(d) else []):
            rel = os.path.join("packs", sub, name, "bbtool.json")
            if rel not in wanted:
                print(f"  [FAIL] {rel} names nothing the tables ship any more: remove it")
                bad += 1
    if not bad:
        print(f"  [ok]   {len(want)} official pack(s) match the tables")
    return 1 if bad else 0


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
