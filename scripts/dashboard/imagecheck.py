"""Registry images kept up to date (R195, the operator, 11 Oct).

A container's services that run an image from a registry (`image:` and no
`build:`) have no other way to move: Rebuild builds what the project's code
makes, and pulls nothing that is already there. So once a week, and on Check
for updates on the Containers page, each instance's registry images are compared
on its node: the digest the node pulled (`docker inspect`'s
RepoDigests) against the one the registry serves for that tag now. One that
differs is behind: its row says so with Update (pull, then up), and the bell
carries a note per node.

What is not asked: a service whose image is pinned by digest (nginx's,
which its own tab moves, nginxproxy.py), a service built from code, and an
image the node has never pulled (Up pulls it; there is nothing to compare).

AerieOS's own image is held to more than its registry (R199): a registry's
tag is whatever was last pushed under it, and each AerieOS release names the
image its tag pushed by digest, in the release's signed list of its files.
So for a container that follows `:dev` or `:latest` of AerieOS's image, the
digest the tag serves is compared with the one the newest signed release
names (releasecheck.signed_image). Where they agree, the update is said by
that digest and whose release it is; where the tag serves another image,
that is said plainly on the row, and no update is offered from the tag.
Where no release says (none signed, none naming its image yet), the row is
as any other image's.

The registry is asked over its v2 API with an anonymous token
(imageregistry.py, the one client for that protocol), which is what a
public image answers on any host that speaks it; a private one says it
could not be read, on the row, rather than guessing. The harness points
BB_IMAGE_DIGESTS_FILE at {ref: digest} instead.
"""
import hashlib
import json
import os
import threading
import time
from pathlib import Path

import imageregistry
import releasecheck

STATE = None
write_json = None
devapp = None
_lock = threading.Lock()
_checking = {"on": False}

CHECK_DELAY = float(os.environ.get("BB_IMAGE_CHECK_DELAY") or 300)
AUTOCHECK = os.environ.get("BB_IMAGE_AUTOCHECK", "1") != "0"
DIGESTS_FILE = os.environ.get("BB_IMAGE_DIGESTS_FILE") or ""


def configure(*, state, write_json, devapp_module):
    globals().update(STATE=Path(state), write_json=write_json, devapp=devapp_module)


def _file():
    return STATE / "imagecheck.json"


def _load():
    try:
        d = json.loads(_file().read_text())
        return d if isinstance(d, dict) else {}
    except (OSError, ValueError, AttributeError):
        return {}


def parse_ref(ref):
    """(registry, repository, tag) of an image reference, or None for one
    pinned by digest. `mariadb:11` is Docker Hub's library/mariadb."""
    parts = imageregistry.parse(ref)
    return None if not parts or parts[3] else parts[:3]


def _stub(ref):
    try:
        return str(json.loads(Path(DIGESTS_FILE).read_text()).get(ref) or "")
    except (OSError, ValueError, AttributeError):
        return ""


def remote_digest(ref):
    """(digest, error): what the registry serves for this tag now
    (imageregistry.digest_of); ("", "") for a reference with no tag to ask
    about."""
    if DIGESTS_FILE:
        got = _stub(ref)
        return (got, "") if got else ("", f"the registry has no {ref}")
    if not parse_ref(ref):
        return "", ""
    return imageregistry.digest_of(ref)


def registry_images(project, instance):
    """[(service, image)] of an instance's services that run a registry
    image by tag: not built, not pinned by digest."""
    cfg = devapp._config(project, instance)
    if cfg is None:
        return []
    return sorted((name, str(sv["image"])) for name, sv in devapp._services(cfg).items()
                  if sv.get("image") and not sv.get("build") and parse_ref(sv["image"]))


def local_digests(image):
    """The digests the node has for an image it pulled, or None for one it
    has not (nothing to compare: Up pulls it)."""
    # `docker inspect --type image`, not `docker image inspect`: the bare
    # inspect is the read _run sends to an agent node as it is.
    r = devapp._run([devapp.DOCKER, "inspect", "--type", "image", "--format", "{{json .RepoDigests}}", image], timeout=30)
    if r.get("code") != 0:
        return None
    try:
        got = json.loads((r.get("out") or "").strip().splitlines()[-1])
    except (ValueError, IndexError):
        return None
    return {d.partition("@")[2] for d in got or [] if "@" in d}


def release_image(image, memo=None):
    """What the newest signed release names for `image`, when it is AerieOS's
    own followed by a tag a publication moves (:dev, :latest):
    releasecheck.signed_image's answer, asked once a check (`memo`). {} for
    any other image, and where the release names another repository's."""
    parts = parse_ref(image)
    if not parts or f"{parts[0]}/{parts[1]}" != releasecheck.IMAGE or parts[2] not in releasecheck.FOLLOWED:
        return {}
    memo = memo if memo is not None else {}
    if parts[2] not in memo:
        try:
            memo[parts[2]] = releasecheck.signed_image(parts[2])
        except Exception as e:   # noqa: BLE001 (what the release says is an extra; the registry's answer stands)
            memo[parts[2]] = {"why": f"{type(e).__name__}: {e}"}
    own = memo[parts[2]]
    return own if own.get("image") == releasecheck.IMAGE else {}


def check_instance(project, instance, memo=None):
    """{"at", "behind": [{service, image, to}], "said": [sentence], "error"}
    for one instance, asked on its node. A behind row of AerieOS's own image
    carries `signed`, the image by the digest its release names and whose
    release it is; `said` is what a person must be told that is no update:
    a tag that serves another image than the newest signed release names."""
    behind, errors, said = [], [], []
    with devapp.on_node(devapp._instance_node(project, instance)):
        for service, image in registry_images(project, instance):
            have = local_digests(image)
            if not have:
                continue
            want, err = remote_digest(image)
            own = {} if err else release_image(image, memo)
            if err:
                errors.append(f"{image}: {err}")
            elif own and want != own["digest"]:
                said.append(f"{image} serves {want} now, which is not the image the newest signed release names "
                            f"({own['tag']}: {own['ref']}, {own['signed']}). The registry's tag was moved by something "
                            "other than that release's publication, or a newer release is not signed yet, so no update "
                            "is offered from the tag; the signed image is pulled by its digest")
            elif want and want not in have:
                behind.append({"service": service, "image": image, "to": want}
                              | ({"signed": f"{own['ref']}, {own['tag']}'s own image, {own['signed']}"} if own else {}))
    return {"at": int(time.time()), "behind": behind, "said": said, "error": "; ".join(errors)[:400]}


def check(node=None):
    """Every instance's registry images (on one node, or all), now. The
    answers, keyed by container name. One asked for while another runs
    waits for it and then runs, since it may be about another node."""
    while True:
        with _lock:
            if not _checking["on"]:
                _checking["on"] = True
                break
        time.sleep(0.5)
    out = {}
    # What the newest signed release names, asked once a check.
    memo = {}
    try:
        for project, insts in devapp._load().items():
            for inst in insts:
                if devapp.owner_of(project, inst) == devapp.SYSTEM:
                    continue
                if node and (devapp._instance_node(project, inst) or "") != node:
                    continue
                try:
                    out[devapp._pname(project, inst)] = check_instance(project, inst, memo) | {
                        "node": devapp._instance_node(project, inst) or "",
                        "project": devapp.owner_of(project, inst) or project}
                except Exception as e:   # noqa: BLE001 (one container's trouble is not the check's)
                    print(f"[imagecheck] {project}/{inst}: {type(e).__name__}: {e}", flush=True)
        with _lock:
            d = _load()
            if not node:
                d = {k: v for k, v in d.items() if k.startswith("_")}
            d.update(out)
            d["_at"] = int(time.time())
            write_json(_file(), d)
    finally:
        with _lock:
            _checking["on"] = False
    return {"ok": True, "checked": len(out), "behind": sum(1 for v in out.values() if v["behind"])}


def of(name):
    """What the last check said of the container called `name`, or {}."""
    return dict(_load().get(name) or {})


def last_at():
    return int(_load().get("_at") or 0)


def forget(name):
    """An update that pulled what was behind: nothing is behind until the
    next check says so."""
    with _lock:
        d = _load()
        if name in d:
            d[name] = dict(d[name], behind=[])
            write_json(_file(), d)


def _project_of(name, v):
    """The project a checked container is one of: as the check recorded it,
    or, for an answer from before it did, found by the container's name."""
    if (v or {}).get("project"):
        return v["project"]
    for project, insts in devapp._load().items():
        for inst in insts:
            if devapp._pname(project, inst) == name:
                return devapp.owner_of(project, inst) or project
    return ""


def attention(node_name, allowed=None):
    """The bell's rows: one per node with a container behind, kind image,
    keyed by bellseen on the digests it would move to. `allowed(project)`
    keeps the containers of the projects this account may act on: a row of
    another project's updates is news about containers it cannot touch, and
    names what it may not see (the operator, 16 Oct)."""
    by = {}
    for name, v in _load().items():
        if name.startswith("_") or not (v or {}).get("behind"):
            continue
        if allowed is not None and not allowed(_project_of(name, v)):
            continue
        by.setdefault(v.get("node") or "", []).append((name, v["behind"]))
    out = []
    for nid, rows in sorted(by.items()):
        rows.sort()
        digest = hashlib.sha256(json.dumps(rows, sort_keys=True).encode()).hexdigest()[:16]
        out.append({"kind": "image", "id": nid, "node": node_name(nid) if nid else "the default node",
                    "containers": [{"name": n, "images": [b["image"] for b in bs]} for n, bs in rows],
                    "digest": digest})
    return out


import checks  # noqa: E402 (the cadence, R176)


def check_loop():
    """The weekly check, from when the last one ran rather than from the
    start, beside the toolchains' and nginx's."""
    checks.loop("images", last_at, check, CHECK_DELAY, 600)
