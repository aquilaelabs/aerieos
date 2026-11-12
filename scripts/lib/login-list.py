"""Behind `aerie login --list` (cmd_login in bb): every account this machine is
signed in to Claude as, as JSON, changing nothing. The agent asks for it
and carries the answer up on its heartbeat (B104). Read from the files
rather than from `claude auth status`, for every account on the box at
once.

BB_USERS_DIR is the directory the accounts' homes are under.

Each row carries the other coding agents' sign-ins too (R95 step 3), under
`agents`, every one read the same way from what its row in the agents'
table or its pack's manifest says of its sign-in (who_of, R234 step 6):
Codex CLI's from its auth.json (the account the id token names, never the
token), Copilot CLI's from its config (the GitHub login it last signed in
as), and so on. `forget` is the sign-out of a program with none of its own.
"""
import base64
import json
import os
import re
import sys


def _claims(jwt):
    """The claims of a JSON web token, read and never checked: what it says
    about whose it is, for a row to name. {} when it is not one."""
    try:
        part = str(jwt).split(".")[1]
        return json.loads(base64.urlsafe_b64decode(part + "=" * (-len(part) % 4))) or {}
    except (IndexError, ValueError, TypeError):
        return {}


# Where a node keeps the coding agents' sign-ins sealed (R126, the agent's
# tokens.py): a seal there is a sign-in, its header saying whose, though the
# home's own file is a link to a copy that is only open while the account
# works here. Read as root, as this runs on a node.
# Under AerieOS's own name where the node has it (R204), else the one before.
SEAL_DIR = ("/var/lib/aerieos" if os.path.isdir("/var/lib/aerieos") else "/var/lib/builderbot") + "/tokens"


def sealed_of(home, agent):
    """{email, plan} from the seal of `agent` for the account whose home this
    is, or None: the header alone, never the sealed sign-in."""
    try:
        with open(os.path.join(SEAL_DIR, os.path.basename(home.rstrip("/")), agent + ".seal"), "rb") as f:
            blob = f.read(8192)
    except OSError:
        return None
    # Either format (B407): BBTOK2 since 0.9 (X25519, R158 step 3), BBTOK1
    # from a node before; the header line is the same shape in both.
    magic = next((m for m in (b"BBTOK2\n", b"BBTOK1\n") if blob.startswith(m)), None)
    if magic is None:
        return None
    try:
        h = json.loads(blob[len(magic):blob.index(b"\n", len(magic))])
    except ValueError:
        return None
    return {"email": str(h.get("email") or "")[:120], "plan": str(h.get("plan") or "")[:40]}


def _jwt_email(d, depth=0):
    """The email a JSON Web Token anywhere in this record says it is for,
    read from its claims without checking its signature (a name to show,
    never a credential to trust), or ""."""
    if depth > 4:
        return ""
    vals = d.values() if isinstance(d, dict) else d if isinstance(d, list) else [d]
    for v in vals:
        if isinstance(v, (dict, list)):
            got = _jwt_email(v, depth + 1)
            if got:
                return got
        elif isinstance(v, str) and v.count(".") == 2 and len(v) < 8192:
            try:
                part = v.split(".")[1]
                claims = json.loads(base64.urlsafe_b64decode(part + "=" * (-len(part) % 4)))
            except (ValueError, TypeError):
                continue
            mail = claims.get("email") if isinstance(claims, dict) else None
            if isinstance(mail, str) and "@" in mail:
                return mail[:120]
    return ""


def packs_file():
    """The tool packs this bundle carries, beside its catalog: where a pack
    that brings a coding agent says how it signs in."""
    return os.environ.get("BB_TOOLPACKS_JSON") or os.path.join(
        os.path.dirname(os.path.abspath(__file__)), "..", "..", "config", "toolpacks.json")


def pack_flows():
    """{agent: its adapter} for the packs' coding agents that describe a
    sign-in's flow (R233 step 6): the link, what its screens ask, and the
    file under the home its sign-in is kept in. A shipped agent's name is
    never a pack's, and a kept file that is not a plain path under the home
    is no row."""
    try:
        with open(packs_file(), encoding="utf-8") as f:
            rows = json.load(f).get("toolchains") or []
    except (OSError, ValueError, AttributeError):
        return {}
    out = {}
    for r in rows if isinstance(rows, list) else []:
        a = r.get("agent") if isinstance(r, dict) else None
        name = str(r.get("name") or "") if isinstance(r, dict) else ""
        si = a.get("signin") if isinstance(a, dict) else None
        flow = si.get("flow") if isinstance(si, dict) else None
        if not (isinstance(flow, dict) and re.fullmatch(r"[a-z][a-z0-9]{1,15}", name)
                and name not in ("claude", "codex", "copilot", "grok", "open")):
            continue
        kept, url = flow.get("kept"), flow.get("url")
        if not (isinstance(kept, str) and re.fullmatch(r"[A-Za-z0-9._/-]{1,200}", kept) and not kept.startswith("/")
                and not any(p in ("", ".", "..") for p in kept.split("/"))
                # How its link starts, one way or a few: each a web address.
                and (urls := url if isinstance(url, list) else [url]) and all(isinstance(u, str) and u.startswith("https://") for u in urls)):
            continue
        out[name] = a
    return out


def _jsonc(data):
    """(its leading comment lines, its JSON) of a file's text: Copilot's
    config.json opens with `//` lines saying it is managed since 1.0.103,
    which a plain json.loads refused, so a sign-in there never reached the
    card."""
    lines = data.splitlines(keepends=True)
    n = 0
    while n < len(lines) and (not lines[n].strip() or lines[n].lstrip().startswith("//")):
        n += 1
    return "".join(lines[:n]), json.loads("".join(lines[n:]))


def _at(d, path):
    """The value the keys of `path` lead to in `d`, or None. A token met on
    the way (a JSON web token as text) is opened to what it says of its
    holder, read and never checked."""
    for k in path:
        if isinstance(d, str):
            d = _claims(d)
        if not isinstance(d, dict):
            return None
        d = d.get(k)
    return d


def who_of(home, agent, a):
    """Who this account is signed in to a coding agent as here, {email,
    plan}, or None: one reading for every agent, from what its row or its
    pack says of its sign-in (signin.flow, R234 step 6). The file the
    sign-in is kept in, or the one `who.file` names beside it; the address
    and the plan at the keys `who` gives, a token on the way opened to its
    claims; with no keys given, the address any token in it names. A file
    that names nobody is the account `who.named` says, or its provider's.
    None only when there is no sign-in: a file that could not be read is
    {"error": why}, which nobody reads as a sign-out (B236)."""
    flow = a["signin"]["flow"]
    who = flow.get("who") or {}
    whose = who.get("named") or f"{str(a.get('provider') or '').strip()[:60] or agent} account"
    apart = bool(who.get("file")) and who["file"] != flow["kept"]
    try:
        with open(os.path.join(home, who.get("file") or flow["kept"]), "rb") as f:
            data = f.read(1 << 20)
    except FileNotFoundError:
        # Sealed, its copy not open now (R126): still a sign-in.
        got = sealed_of(home, agent)
        return got if got and got["email"] else None
    except OSError as e:
        return {"error": f"{type(e).__name__}: {e}"[:200]}
    # Where another file says who, the sign-in itself is what makes it one
    # rather than a leftover name: a signed-out home keeps the first and
    # loses the second.
    if apart and not os.path.exists(os.path.join(home, flow["kept"])) and not sealed_of(home, agent):
        return None
    if not data.strip():
        return None
    try:
        d = _jsonc(data.decode("utf-8", "replace"))[1]
    except (ValueError, TypeError) as e:
        # A JSON file that does not read is unread; a token kept as plain
        # text is a sign-in that names nobody.
        if who.get("email") or who.get("key") or (who.get("file") or flow["kept"]).endswith(".json"):
            return {"error": f"{type(e).__name__}: {e}"[:200]}
        return {"email": whose[:120], "plan": ""}
    email = _at(d, who["email"]) if who.get("email") else _jwt_email(d)
    if isinstance(email, str) and email:
        plan = _at(d, who["plan"]) if who.get("plan") else ""
        return {"email": email[:120], "plan": (plan if isinstance(plan, str) else "")[:40]}
    if who.get("key") and _at(d, who["key"]):
        return {"email": (who.get("key_named") or f"{str(a.get('provider') or agent)} API key")[:120], "plan": "API"}
    if who.get("email") or not d:
        return None
    return {"email": whose[:120], "plan": ""}


def forget(home, flow):
    """A sign-out for a program with none of its own (Copilot CLI outside a
    session): the keys its flow names taken out of the file its sign-in is
    kept in, and any key that carries the word it gives; everything else,
    and the file's leading comment lines, left as they were."""
    g = flow.get("forget") or {}
    p = os.path.join(home, g.get("file") or flow["kept"])
    try:
        with open(p, encoding="utf-8") as f:
            head, d = _jsonc(f.read())
    except FileNotFoundError:
        return 0
    except (OSError, ValueError):
        return 1
    if not isinstance(d, dict):
        return 1
    like = str(g.get("like") or "").lower()
    for k in [k for k in d if k in (g.get("keys") or []) or (like and like in k.lower())]:
        d.pop(k, None)
    tmp = p + ".new"
    with open(tmp, "w", encoding="utf-8") as f:
        f.write(head)
        json.dump(d, f, indent=2)
    os.chmod(tmp, 0o600)
    os.replace(tmp, p)
    return 0


def shipped():
    """{agent: its adapter} for the shipped agents that say how they sign
    in: the controller's own table (agents.py), which rides in this bundle
    beside the hook. {} where the bundle carries none."""
    here = os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "dashboard")
    if here not in sys.path:
        sys.path.insert(0, here)
    try:
        import agents                                           # noqa: PLC0415 (the bundle's, beside the dashboard)
        return agents.signs_in()
    except (ImportError, AttributeError):
        return {}


def signins():
    """Every coding agent that describes its sign-in, the shipped and the
    packs': what `aerie login` runs and what each row's reader reads."""
    return {**pack_flows(), **shipped()}


def mcp_of(home):
    """The MCP servers each coding agent of this account's is set up with
    here (R95 step 15), by name only: a server's settings can carry its own
    keys, and nothing here reads them. Claude Code's from ~/.claude.json,
    Codex's from its config.toml ([mcp_servers.NAME]), Copilot's from its
    mcp-config.json. {agent: [names]}, an agent with none left out."""
    out = {}
    try:
        with open(os.path.join(home, ".claude.json")) as f:
            got = (json.load(f) or {}).get("mcpServers")
        if isinstance(got, dict) and got:
            out["claude"] = sorted(str(k)[:80] for k in got)[:32]
    except (OSError, ValueError, AttributeError):
        pass
    try:
        with open(os.path.join(home, ".codex", "config.toml")) as f:
            names = sorted({m.group(1).strip('"')[:80] for m in re.finditer(r'^\[mcp_servers\.("?[^\]."]+"?)\]', f.read(), re.M)})
        if names:
            out["codex"] = names[:32]
    except OSError:
        pass
    try:
        with open(os.path.join(home, ".copilot", "mcp-config.json"), encoding="utf-8") as f:
            got = (_jsonc(f.read())[1] or {}).get("mcpServers")
        if isinstance(got, dict) and got:
            out["copilot"] = sorted(str(k)[:80] for k in got)[:32]
    except (OSError, ValueError, AttributeError):
        pass
    return out


def plugins_of(home):
    """The Claude Code plugins this account installed here: what `claude
    plugin list --json` prints, read from the same two files it reads, so a
    person's plugins can be seen on their Profile and in aerie diag. Only the
    names, versions and scope: a plugin's settings can hold its own secrets,
    and nothing here reads them. None when the account never installed one."""
    try:
        got = json.load(open(os.path.join(home, ".claude", "plugins", "installed_plugins.json")))
    except (OSError, ValueError):
        return None
    try:
        on = json.load(open(os.path.join(home, ".claude", "settings.json"))).get("enabledPlugins") or {}
    except (OSError, ValueError, AttributeError):
        on = {}
    rows = []
    for pid, installs in list(((got or {}).get("plugins") or {}).items())[:64]:
        for i in (installs if isinstance(installs, list) else [])[:4]:
            if not isinstance(i, dict):
                continue
            scope = str(i.get("scope") or "")[:12]
            rows.append({"id": str(pid)[:120], "version": str(i.get("version") or "")[:40],
                         "scope": scope,
                         # Where a project-scoped one lives says which project;
                         # the rest of its path is this machine's business.
                         "project": os.path.basename(str(i.get("projectPath") or ""))[:80],
                         # Enabled is the account's own setting for a user-scoped
                         # one; a project's lives in that project and is unknown here.
                         "enabled": bool(on.get(pid, True)) if scope == "user" else None})
    return rows


# Every account's home on this machine. The owner has no bare directory here:
# on a node every account is prefixed and homed under users/ (common.sh's
# owner_uid says why), so the uid is simply the directory's name.
def main():
    out = []
    root = os.environ.get("BB_USERS_DIR") or ""
    try:
        names = sorted(os.listdir(root))
    except OSError:
        names = []
    all_ = signins()
    for name in names[:64]:
        if not re.fullmatch(r"u_[0-9a-f]{8}", name):
            continue
        home = os.path.join(root, name)
        got = {k: who_of(home, k, a) for k, a in all_.items()}
        # Claude's is the row's own address, as it was before the others had
        # one; the rest are under `agents`.
        email = str((got.pop("claude", None) or {}).get("email") or "")
        agents = {k: v for k, v in got.items() if v}
        out.append({"uid": name, "email": email, "plugins": plugins_of(home), "agents": agents, "mcp": mcp_of(home)})
    print(json.dumps(out))


# Imported by login-check.py for the agents' readers, run by `aerie login --list`.
if __name__ == "__main__":
    main()
