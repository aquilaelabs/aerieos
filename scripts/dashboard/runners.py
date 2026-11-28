"""A node's CI runners as the controller holds them: the root-only helper that
keeps each runner's token and mints from it, and the list the Runner card draws.

The helper is the builder account's one sudo rule (Dockerfile). Nothing here
ever sees a token: store hands one in on stdin, every other verb prints a
derived answer, and --list says only which runners have one.
"""
import json
import os
import re
import subprocess
import threading
import time
import urllib.error
import urllib.request

# Injected by configure(): the server's subprocess runner, and the nodes
# module, or None when the node store would not open.
run = None
nodes = None

HELPER = "/opt/aerieos/scripts/mint-runner-token"


def configure(*, run, nodes):
    globals().update(run=run, nodes=nodes)


# What each runner's download is held to: the one table that pins them,
# which tools/pins.py --file moves (docs/toolchains.md, Moving a pin).
PINS = os.path.join(os.path.dirname(os.path.abspath(__file__)), "runner-pins.json")
_SHA256 = re.compile(r"[0-9a-f]{64}")


def pins(path=None):
    """The runners' pins as a node is handed one, by the kind of git host a
    runner registers with: {forge: {"version", "files": {platform: {"url",
    "sha256"}}}}, each address the table's own with the version filled in.
    A node gets its row with the job that installs a runner and takes a
    file only where it is those bytes. A row that is not a whole pin, or a
    table that cannot be read, answers nothing for that runner, so its
    install is refused by name here and is never sent off to fetch what
    nothing holds."""
    try:
        with open(path or PINS, encoding="utf-8") as f:
            rows = json.load(f).get("runners")
    except (OSError, ValueError, AttributeError):
        return {}
    out = {}
    for row in rows if isinstance(rows, list) else []:
        src = row.get("source") if isinstance(row, dict) else None
        ck = src.get("checksum") if isinstance(src, dict) else None
        if not isinstance(ck, dict) or ck.get("from") != "pin":
            continue
        version, urls, sums = ck.get("version"), src.get("url"), ck.get("sha256")
        if not (isinstance(version, str) and version and isinstance(urls, dict) and isinstance(sums, dict)):
            continue
        files = {plat: {"url": url.replace("{version}", version), "sha256": sums[plat]} for plat, url in urls.items()
                 if isinstance(url, str) and url.startswith("https://") and isinstance(sums.get(plat), str) and _SHA256.fullmatch(sums[plat])}
        if files and isinstance(row.get("name"), str):
            out[row["name"]] = {"version": version, "files": files}
    return out


def _why(r):
    why = (r["out"].strip().splitlines() or ["the helper printed nothing"])[-1]
    return re.sub(r"^\[builderbot\] ERROR: ", "", why)[:200]


def mint(kind, node_id, slot, runner_id=""):
    """A registration or removal token for one of a node's runners, minted
    from the token stored for it. `runner_id` is the runner's id on a
    Gitea, where removal is a deletion there rather than a token."""
    argv = ["sudo", "-n", HELPER, kind, node_id, slot]
    if re.fullmatch(r"[0-9]{1,12}", str(runner_id or "")):
        argv.append(str(runner_id))
    r = run(argv, timeout=60)
    if r["code"] == 0 and r["out"].strip():
        return {"token": r["out"].strip().splitlines()[-1]}
    return {"error": f"the controller cannot mint a runner token: {_why(r)}"}


# What --list said, kept TOKENS_KEEP_S: the Nodes listing
# asked on every read, a sudo and a process each. A store, a forget or a
# reset here forgets it; one made outside the dashboard shows within the time.
TOKENS_KEEP_S = 60.0
_tokens_kept = {"at": 0.0, "out": None}
_tokens_lock = threading.Lock()


def _tokens_forget():
    with _tokens_lock:
        _tokens_kept.update(at=0.0, out=None)


def tokens():
    """{node id: {slot, ...}} for every runner token stored, from one call
    to the helper's --list. Which runners have a token, and nothing else."""
    with _tokens_lock:
        if _tokens_kept["out"] is not None and time.monotonic() - _tokens_kept["at"] < TOKENS_KEEP_S:
            return {k: set(v) for k, v in _tokens_kept["out"].items()}
    r = run(["sudo", "-n", HELPER, "--list"], timeout=20)
    out = {}
    if r["code"] == 0:
        for line in r["out"].splitlines():
            parts = line.split()
            if len(parts) == 2:
                out.setdefault(parts[0], set()).add(parts[1])
        with _tokens_lock:
            _tokens_kept.update(at=time.monotonic(), out={k: set(v) for k, v in out.items()})
    return out


def store(node_id, slot, url, forge, token):
    """Hand a runner's token to the helper on stdin: it never rides an argv,
    where every account on the box could read it off ps."""
    _tokens_forget()
    try:
        p = subprocess.run(["sudo", "-n", HELPER, "store", node_id, slot],
                           input=f"RUNNER_URL={url}\nRUNNER_FORGE={forge}\nRUNNER_TOKEN={token}\n",
                           capture_output=True, text=True, timeout=30, check=False)
    except (OSError, subprocess.SubprocessError) as e:
        return {"error": f"could not store the token: {e}"}
    r = {"code": p.returncode, "out": ((p.stdout or "") + (p.stderr or "")).strip()}
    if r["code"]:
        return {"error": _why(r)}
    return {"ok": True}


def forget(node_id, slot):
    _tokens_forget()
    r = run(["sudo", "-n", HELPER, "forget", node_id, slot], timeout=20)
    return {"ok": True} if r["code"] == 0 else {"error": _why(r)}


def reset():
    """Forget every stored token, for a controller being reset: the nodes
    they were for are being forgotten too. True when the helper did."""
    _tokens_forget()
    return run(["sudo", "-n", HELPER, "--reset"], timeout=20)["code"] == 0


# Whether a runner's repository is public, asked of its host once an hour
# and never on the page's own read: {url: (when, True|False|None)}.
_public = {}
_public_lock = threading.Lock()
PUBLIC_EVERY_S = 3600
urlopen = urllib.request.urlopen     # the seam a test replaces


def _ask_public(url):
    """GitHub alone answers this without a token: a repository it shows to
    nobody signed in is public. None where it cannot be told."""
    m = re.fullmatch(r"https://github\.com/([A-Za-z0-9_.-]+)/([A-Za-z0-9_.-]+?)(?:\.git)?/?", url or "")
    if not m:
        return None
    try:
        req = urllib.request.Request(f"https://api.github.com/repos/{m.group(1)}/{m.group(2)}",
                                     headers={"Accept": "application/vnd.github+json", "User-Agent": "aerieos"})
        with urlopen(req, timeout=8) as r:
            return json.loads(r.read().decode(errors="replace") or "{}").get("private") is False
    except urllib.error.HTTPError as e:
        return False if e.code == 404 else None
    except (urllib.error.URLError, OSError, ValueError):
        return None


def is_public(url):
    """True, False or None (not known yet): read from what was last asked,
    and asked again on a thread when that is an hour old."""
    now = time.time()
    with _public_lock:
        at, got = _public.get(url, (0, None))
        due = now - at > PUBLIC_EVERY_S
        if due:
            _public[url] = (now, got)

    def go():
        ans = _ask_public(url)
        with _public_lock:
            _public[url] = (time.time(), ans if ans is not None else got)
    if due and url:
        threading.Thread(target=go, name="runner-public", daemon=True).start()
    return got


def exposed(url, node_name, docker):
    """What a runner on a public repository means, for its row: a
    pull request from a fork runs whatever workflow it carries on this
    machine, as its jobs account. "" for a repository that is not public."""
    if is_public(url) is not True:
        return ""
    return (f"This repository is public, so a pull request from anybody can run its own workflow on {node_name}, "
            "as the jobs account" + (", which reaches Docker there and through it the whole machine" if docker else "")
            + ". On GitHub: Settings, Actions, General, Approval for running fork pull request workflows, "
              "Require approval for all external contributors; and read what a pull request changes under "
              ".github/workflows before approving its run.")


def listing():
    """[{node, name, listening, busy, labels, url}] for every node whose
    census reports a runner, or that has been asked for one. Quiet nodes are
    included and marked: a runner nobody can hear from is a fact worth
    seeing, not a row to hide."""
    if not nodes:
        return []
    out = []
    for n in nodes.node_list():
        if n["kind"] != "agent":
            continue
        asked = nodes.runners_of(n)
        reported = {r.get("slot"): r for r in nodes.runners_reported(n)}
        ap = n.get("applying") or {}
        failed = n.get("runner_failed") or {}
        for slot in sorted(set(asked) | set(reported)):
            want = asked.get(slot) or {}
            rep = reported.get(slot) or {}
            # A runner job in flight keeps the row while it runs: a Remove
            # takes the ask off the record the moment it is pressed, and the
            # row went with it before the node had said a word.
            applying = ap.get("what") == "runner" and (ap.get("slot") or slot) == slot
            if not (rep.get("installed") or want.get("want") or applying):
                continue
            out.append({"node": n["name"], "id": n["id"], "slot": slot, "live": bool(n.get("live")),
                        "installed": bool(rep.get("installed")),
                        "listening": bool(rep.get("active")), "busy": bool(rep.get("busy")),
                        "name": rep.get("name") or "", "url": rep.get("url") or want.get("url") or "",
                        "labels": rep.get("labels") or want.get("labels") or [],
                        # A public repository's runner takes a stranger's pull request.
                        "exposed": exposed(rep.get("url") or want.get("url") or "", n["name"],
                                           bool((n.get("reported") or {}).get("docker"))),
                        # Why a runner that was asked for is not there, and
                        # whether the install that would put it there runs now.
                        "failed": failed if failed and (failed.get("slot") or slot) == slot else None,
                        "installing": applying and bool(want.get("want")),
                        "removing": applying and not want.get("want")})
    return out
