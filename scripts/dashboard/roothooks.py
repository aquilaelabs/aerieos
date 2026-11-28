"""The root startup hooks an administrator approves: each
STATE/startup.d/*.root.sh, what it says, and whether the start will run it,
read and changed through the root-only helper scripts/root-hook, which keeps
the approvals where only root writes. Controller settings' Startup hooks
draws this; Controller Write approves and revokes.

Where the helper is the installed one (under /opt/aerieos) it is asked
through sudo, as deploy-key is; anywhere else (a checkout, the suites' copy)
the tree's own is run as this account against this state, its trust checks
held to this account instead of root."""
import os
import re
import subprocess
from pathlib import Path

HELPER = Path(__file__).resolve().parent.parent / "root-hook"
STATE = None
NAME_RE = re.compile(r"^[A-Za-z0-9][A-Za-z0-9._-]{0,80}\.root\.sh$")
TEXT_MAX = 64 * 1024


def configure(*, state):
    globals()["STATE"] = str(state)


def _run(argv):
    """(stdout, error) of the helper."""
    installed = str(HELPER).startswith("/opt/aerieos/") and os.geteuid() != 0
    cmd = (["sudo", "-n", str(HELPER)] if installed else ["bash", str(HELPER)]) + list(argv)
    env = None if installed else dict(os.environ, BB_ROOT_HOOK_STATE=STATE or "/config")
    try:
        p = subprocess.run(cmd, capture_output=True, text=True, timeout=30, check=False, env=env)
    except (OSError, subprocess.SubprocessError) as e:
        return "", f"the root-hook helper did not run: {e}"
    if p.returncode != 0:
        said = (p.stderr or p.stdout).strip().splitlines()
        return "", (said[-1] if said else f"exit {p.returncode}").replace("root-hook: ", "")[:200]
    return p.stdout, ""


def listing():
    """{hooks: [{name, sha, state, text}]}: every root hook in the state's
    startup.d, what it says (read here, as anything in /config is), and
    approved, changed (approved once, different now) or new."""
    out, why = _run(["list"])
    if why:
        return {"error": why, "hooks": []}
    hooks = []
    for line in out.splitlines():
        parts = line.split()
        if len(parts) != 3 or not NAME_RE.match(parts[0]):
            continue
        name, sha, state = parts
        try:
            text = (Path(STATE or "/config") / "startup.d" / name).read_text(errors="replace")[:TEXT_MAX]
        except OSError:
            text = ""
        hooks.append({"name": name, "sha": sha, "state": state, "text": text})
    return {"hooks": hooks}


def act(req):
    """approve NAME SHA (the sha the page was shown, so what is approved is
    what was read) or revoke NAME: (payload, status)."""
    action, name, sha = str(req.get("action") or ""), str(req.get("name") or ""), str(req.get("sha") or "")
    if not NAME_RE.match(name):
        return {"error": f"not a root hook's name: {name}"}, 400
    if action == "approve":
        if not re.fullmatch(r"[0-9a-f]{64}", sha):
            return {"error": "approve names the hook's sha256 as it was shown"}, 400
        _out, why = _run(["approve", name, sha])
    elif action == "revoke":
        _out, why = _run(["revoke", name])
    else:
        return {"error": "action is approve or revoke"}, 400
    return ({"error": why}, 409) if why else ({"ok": True, **listing()}, 200)
