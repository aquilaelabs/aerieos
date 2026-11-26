"""A space's Discord server (R293): built out and changed from a layout kept
as code, through the controller, which holds the bot's token.

Connected once in the space's settings: a Discord application's bot token,
checked as a bot's (a user account's token is refused, as Discord's terms
refuse it), sealed under the install key and never shown again or handed to
a session; the server is one the bot was invited to. The controller calls
Discord's REST API itself with the standard library: there is no bot
process to run for any of this.

The layout is a file in the space's repository, deploy/discord.yml: its
roles, its categories and channels with each one's permission overwrites,
its AutoMod keyword rules and the messages pinned in each channel. Pull
writes the server as it stands into it, so an existing server is adopted;
a plan says what applying the file would add, change and remove; apply
makes it so. Anything that removes, changes a permission or reaches
members asks a person whatever a session's dial says: `asks` on a change.

discord.json: {space key: {token (sealed), guild, guild_name, app, by, at,
plans: [the last few plans, who made and who applied each]}}, the space's
key as repos.key_of names it, so every repository of a space reads the same
connection. Nothing of the server itself is kept here.
"""
import base64
import json
import re
import threading
import time
import urllib.error
import urllib.parse
import urllib.request

import statefile

STATE = None
write_json = None
seal = None              # bytes -> bytes, signing.seal
unseal = None            # bytes -> bytes, or raises
sealing = None           # () -> whether an install key is loaded now
audit = None             # (principal, verb, target, detail)
API = "https://discord.com/api/v10"
SEALED = "bbseal:"
LAYOUT = "deploy/discord.yml"
KEEP_PLANS = 10
_lock = threading.Lock()

# Discord's permission bits by the names a layout uses (its API's own names,
# lower case).
PERMS = {n: 1 << i for i, n in enumerate((
    "create_instant_invite", "kick_members", "ban_members", "administrator", "manage_channels",
    "manage_guild", "add_reactions", "view_audit_log", "priority_speaker", "stream", "view_channel",
    "send_messages", "send_tts_messages", "manage_messages", "embed_links", "attach_files",
    "read_message_history", "mention_everyone", "use_external_emojis", "view_guild_insights", "connect",
    "speak", "mute_members", "deafen_members", "move_members", "use_vad", "change_nickname",
    "manage_nicknames", "manage_roles", "manage_webhooks", "manage_emojis_and_stickers",
    "use_application_commands", "request_to_speak", "manage_events", "manage_threads",
    "create_public_threads", "create_private_threads", "use_external_stickers",
    "send_messages_in_threads", "use_embedded_activities", "moderate_members"))}
# What the bot is invited with: what the layout's own verbs need, no more.
INVITE = ("view_channel", "manage_channels", "manage_roles", "manage_guild", "send_messages",
          "manage_messages", "read_message_history")
KINDS = {"text": 0, "voice": 2, "announcement": 5, "stage": 13, "forum": 15}
CATEGORY = 4
TOKEN_RE = re.compile(r"^[A-Za-z0-9_.-]{40,120}$")


class Refused(Exception):
    """Discord's answer in a person's words."""


def configure(*, state, write_json_fn, seal_fn=None, unseal_fn=None, sealing_fn=None, audit_fn=None, api=None):
    globals().update(STATE=state, write_json=write_json_fn, seal=seal_fn, unseal=unseal_fn,
                     sealing=sealing_fn, audit=audit_fn)
    if api:
        globals()["API"] = api.rstrip("/")


def _file():
    return STATE / "discord.json"


_store = statefile.Store(_file, write=lambda: write_json, mode=0o600, cached=True)


def _load():
    d = _store.load()
    return d if isinstance(d, dict) else {}


def _save(d):
    _store.save(d)


def rev():
    return _store.rev()


def _keep(v):
    if v and seal and sealing and sealing():
        return SEALED + base64.b64encode(seal(str(v).encode())).decode()
    return str(v or "")


def _open(v):
    v = str(v or "")
    if v.startswith(SEALED):
        try:
            return unseal(base64.b64decode(v[len(SEALED):])).decode() if unseal else ""
        except Exception:                                   # noqa: BLE001 (Locked, or damaged: no value)
            return ""
    return v


def seal_all():
    """Every token sealed again under the install key in force (installkey's
    passes): one kept plain before a key existed, or under the one before."""
    with _lock:
        d = _load()
        n = 0
        for rec in d.values():
            if isinstance(rec, dict) and rec.get("token"):
                plain = _open(rec["token"])
                if plain:
                    rec["token"] = _keep(plain)
                    n += 1
        if n:
            _save(d)
    return n


# ---- Discord's API ------------------------------------------------------------

def _call(token, method, path, body=None, tries=3):
    """One call to Discord as the bot, its JSON answered ({} for none). A
    rate limit is waited out (its retry_after, a few seconds at most) and
    asked again; anything else refused raises Refused in a sentence."""
    url = API + path
    for _ in range(tries):
        data = json.dumps(body).encode() if body is not None else None
        req = urllib.request.Request(url, data=data, method=method, headers={
            "Authorization": f"Bot {token}", "User-Agent": "DiscordBot (https://aerieos.org, 1)",
            **({"Content-Type": "application/json"} if data is not None else {})})
        try:
            with urllib.request.urlopen(req, timeout=20) as r:   # noqa: S310 (Discord's own address)
                raw = r.read()
                return json.loads(raw) if raw.strip() else {}
        except urllib.error.HTTPError as e:
            try:
                j = json.loads(e.read(20000) or b"{}")
            except ValueError:
                j = {}
            if e.code == 429:
                time.sleep(min(5.0, float((j or {}).get("retry_after") or 1)))
                continue
            said = (j or {}).get("message") or e.reason
            if e.code == 401:
                raise Refused("Discord refused the bot's token: it was reset or is not a bot's") from e
            if e.code == 403:
                raise Refused(f"Discord refused it ({said}): the bot's role needs the permission, and sits "
                              "above the roles it changes") from e
            if e.code == 404:
                raise Refused(f"Discord has no such thing any more ({said})") from e
            raise Refused(f"Discord answered {e.code}: {said}") from e
        except (urllib.error.URLError, OSError) as e:
            raise Refused(f"Discord did not answer: {getattr(e, 'reason', None) or e}") from e
    raise Refused("Discord kept asking to slow down: try again in a minute")


def invite_url(app):
    """Where a person invites the bot, with the permissions its verbs need."""
    perms = sum(PERMS[p] for p in INVITE)
    return f"https://discord.com/oauth2/authorize?client_id={app}&scope=bot&permissions={perms}"


# ---- the connection -------------------------------------------------------------

def status(space):
    """What the space's settings and Discord view show: no token, ever."""
    rec = _load().get(space) or {}
    if not rec.get("token"):
        return {"connected": False}
    return {"connected": True, "guild": rec.get("guild", ""), "guild_name": rec.get("guild_name", ""),
            "app": rec.get("app", ""), "by": rec.get("by", ""), "at": rec.get("at", 0),
            "invite": invite_url(rec["app"]) if rec.get("app") else "",
            "plans": list(rec.get("plans") or [])[:KEEP_PLANS]}


def connect(space, token, guild="", by=""):
    """The bot's token kept for the space, once it reads as a bot's and the
    bot is in the server named (or in one alone). {ok, guild, guild_name}
    or {error, invite?}."""
    token = str(token or "").strip()
    if token.lower().startswith("bot "):
        token = token[4:].strip()
    if not TOKEN_RE.match(token):
        return {"error": "that does not read as a Discord bot token: its application's Bot page shows one (Reset Token)"}
    try:
        me = _call(token, "GET", "/users/@me")
        if not me.get("bot"):
            return {"error": "a user account's token is refused, as Discord's terms refuse it: make an application "
                             "and its bot on Discord's developer portal, and give its token"}
        guilds = _call(token, "GET", "/users/@me/guilds") or []
    except Refused as e:
        return {"error": str(e)}
    app = str(me.get("id") or "")
    pick = [g for g in guilds if not guild or str(g.get("id")) == str(guild)]
    if not pick:
        return {"error": "the bot is in no server yet: invite it with the link, then connect again"
                if not guilds else f"the bot is not in server {guild}", "invite": invite_url(app)}
    if len(pick) > 1:
        return {"error": "the bot is in several servers: name the one this space builds",
                "guilds": [{"id": str(g.get("id")), "name": g.get("name", "")} for g in pick]}
    g = pick[0]
    with _lock:
        d = _load()
        was = d.get(space) or {}
        d[space] = {"token": _keep(token), "guild": str(g.get("id")), "guild_name": str(g.get("name") or ""),
                    "app": app, "by": by, "at": int(time.time()), "plans": was.get("plans") or []}
        _save(d)
    if audit:
        audit(by, "discord-connect", space, {"guild": str(g.get("id")), "name": g.get("name", "")})
    return {"ok": True, "guild": str(g.get("id")), "guild_name": str(g.get("name") or "")}


def forget(space, by=""):
    """The space's token gone from here; the bot stays in the server until a
    person kicks it there."""
    with _lock:
        d = _load()
        if space not in d:
            return {"error": "this space has no Discord server connected"}
        d.pop(space)
        _save(d)
    if audit:
        audit(by, "discord-forget", space, {})
    return {"ok": True}


def _conn(space):
    rec = _load().get(space) or {}
    token = _open(rec.get("token"))
    if not token or not rec.get("guild"):
        raise Refused("this space has no Discord server connected: a person connects one in its settings")
    return token, rec["guild"]


def spaces():
    """[(space, guild name)] of every space connected: the Connected services list."""
    return [(k, v.get("guild_name") or v.get("guild") or "") for k, v in _load().items() if isinstance(v, dict) and v.get("token")]


def connected(space):
    """{by, at, guild_name} of a space's connection, for Connected services."""
    return _load().get(space) or {}


# ---- the layout and the server, in one shape ---------------------------------------

def _perm_names(bits):
    bits = int(bits or 0)
    return sorted(n for n, b in PERMS.items() if bits & b)


def _perm_bits(names):
    bad = [n for n in names or [] if n not in PERMS]
    if bad:
        raise ValueError(f"no Discord permission called {', '.join(bad)}")
    return sum(PERMS[n] for n in names or [])


def _color(v):
    if isinstance(v, int):
        return f"#{v:06x}" if v else ""
    v = str(v or "").strip()
    if not v:
        return ""
    if not re.fullmatch(r"#?[0-9a-fA-F]{6}", v):
        raise ValueError(f"a color is #rrggbb, not {v}")
    return "#" + v.lstrip("#").lower()


def _chan_name(name, kind):
    """As Discord keeps it: a text channel's name in lower case with dashes."""
    n = str(name or "").strip()
    return re.sub(r"\s+", "-", n.lower()) if kind in ("text", "announcement", "forum") else n


def _ow(rows, roles_by_id=None):
    out = []
    for o in rows or []:
        if roles_by_id is not None:
            if int(o.get("type", 0)) != 0 or str(o.get("id")) not in roles_by_id:
                continue                        # a member's own overwrite is not a layout's
            role = roles_by_id[str(o["id"])]
            allow, deny = _perm_names(o.get("allow")), _perm_names(o.get("deny"))
        else:
            role = str(o.get("role") or "")
            allow, deny = sorted(o.get("allow") or []), sorted(o.get("deny") or [])
            _perm_bits(allow + deny)
        if allow or deny:
            out.append({"role": role, "allow": allow, "deny": deny})
    return sorted(out, key=lambda x: x["role"])


def normalize(layout):
    """A layout file's value in the one shape a plan compares, or raises
    ValueError in a sentence."""
    if not isinstance(layout, dict):
        raise ValueError(f"{LAYOUT} is a mapping of roles, categories, channels, automod and pins")
    roles = []
    for r in layout.get("roles") or []:
        if not isinstance(r, dict) or not str(r.get("name") or "").strip():
            raise ValueError("every role has a name")
        perms = sorted(r.get("permissions") or [])
        _perm_bits(perms)
        roles.append({"name": str(r["name"]).strip(), "color": _color(r.get("color")), "hoist": bool(r.get("hoist")),
                      "mentionable": bool(r.get("mentionable")), "permissions": perms})

    def chans(rows, where):
        out = []
        for c in rows or []:
            if not isinstance(c, dict) or not str(c.get("name") or "").strip():
                raise ValueError(f"every channel {where} has a name")
            kind = str(c.get("kind") or "text")
            if kind not in KINDS:
                raise ValueError(f"a channel's kind is one of {', '.join(KINDS)}, not {kind}")
            out.append({"name": _chan_name(c["name"], kind), "kind": kind, "topic": str(c.get("topic") or ""),
                        "overwrites": _ow(c.get("overwrites"))})
        return out
    cats = []
    for c in layout.get("categories") or []:
        if not isinstance(c, dict) or not str(c.get("name") or "").strip():
            raise ValueError("every category has a name")
        cats.append({"name": str(c["name"]).strip(), "overwrites": _ow(c.get("overwrites")),
                     "channels": chans(c.get("channels"), f"in {c['name']}")})
    automod = []
    for a in layout.get("automod") or []:
        if not isinstance(a, dict) or not str(a.get("name") or "").strip():
            raise ValueError("every AutoMod rule has a name")
        automod.append({"name": str(a["name"]).strip(), "keywords": sorted(str(k) for k in a.get("keywords") or []),
                        "enabled": a.get("enabled", True) is not False})
    pins = {}
    for ch, msgs in (layout.get("pins") or {}).items():
        pins[_chan_name(ch, "text")] = [str(m).strip() for m in msgs or [] if str(m).strip()]
    return {"roles": roles, "categories": cats, "channels": chans(layout.get("channels"), "outside a category"),
            "automod": automod, "pins": pins}


def read(space):
    """The server as it stands, in the layout's shape, with Discord's ids
    beside it for apply: (layout, ids)."""
    token, guild = _conn(space)
    roles = _call(token, "GET", f"/guilds/{guild}/roles") or []
    chans = _call(token, "GET", f"/guilds/{guild}/channels") or []
    rules = _call(token, "GET", f"/guilds/{guild}/auto-moderation/rules") or []
    me = _call(token, "GET", "/users/@me")
    by_id = {str(r["id"]): ("@everyone" if str(r["id"]) == str(guild) else r["name"]) for r in roles}
    ids = {"guild": guild, "me": str(me.get("id") or ""), "roles": {v: k for k, v in by_id.items()},
           "channels": {}, "automod": {}, "pins": {}}
    out_roles = []
    for r in sorted(roles, key=lambda r: -int(r.get("position") or 0)):
        if r.get("managed"):
            continue                            # a bot's or an integration's own role
        name = by_id[str(r["id"])]
        out_roles.append({"name": name, "color": _color(int(r.get("color") or 0)), "hoist": bool(r.get("hoist")),
                          "mentionable": bool(r.get("mentionable")), "permissions": _perm_names(r.get("permissions"))})
    kind_of = {v: k for k, v in KINDS.items()}
    cats, top = {}, []
    for c in sorted(chans, key=lambda c: int(c.get("position") or 0)):
        if int(c.get("type") or 0) == CATEGORY:
            cats[str(c["id"])] = {"name": c["name"], "overwrites": _ow(c.get("permission_overwrites"), by_id), "channels": []}
            ids["channels"][("", c["name"], "category")] = str(c["id"])
    for c in sorted(chans, key=lambda c: int(c.get("position") or 0)):
        t = int(c.get("type") or 0)
        if t == CATEGORY or t not in kind_of:
            continue
        row = {"name": c["name"], "kind": kind_of[t], "topic": str(c.get("topic") or ""),
               "overwrites": _ow(c.get("permission_overwrites"), by_id)}
        parent = cats.get(str(c.get("parent_id") or ""))
        (parent["channels"] if parent else top).append(row)
        ids["channels"][(parent["name"] if parent else "", c["name"], "channel")] = str(c["id"])
    automod = []
    for a in rules:
        if int(a.get("trigger_type") or 0) != 1:
            continue                            # keyword rules alone are a layout's
        automod.append({"name": a["name"], "keywords": sorted((a.get("trigger_metadata") or {}).get("keyword_filter") or []),
                        "enabled": bool(a.get("enabled", True))})
        ids["automod"][a["name"]] = str(a["id"])
    pins = {}
    for (cat, name, what), cid in ids["channels"].items():
        if what != "channel":
            continue
        got = _call(token, "GET", f"/channels/{cid}/pins") or []
        mine = [m for m in got if str((m.get("author") or {}).get("id")) == ids["me"]]
        if mine:
            pins[name] = [str(m.get("content") or "") for m in reversed(mine)]
            ids["pins"][name] = {str(m.get("content") or ""): str(m["id"]) for m in mine}
    return {"roles": out_roles, "categories": list(cats.values()), "channels": top,
            "automod": automod, "pins": pins}, ids


def as_file(layout):
    """The layout as deploy/discord.yml's text."""
    import markup                                   # scripts/lib, on the path
    head = ("# This space's Discord server, as AerieOS builds it out: aerie discord plan says what\n"
            "# applying this would change, aerie discord apply makes it so. Permission names are Discord's own.\n")
    return head + markup.yaml_dump(_pruned(layout) or {})


def _pruned(v):
    """What a person writes: no empty topic, no empty list, no false switch;
    the layout's reader takes each missing as that."""
    if isinstance(v, dict):
        out = {k: _pruned(x) for k, x in v.items()}
        return {k: x for k, x in out.items() if x not in ("", [], {}, None, False)}
    if isinstance(v, list):
        return [_pruned(x) for x in v]
    return v


def pull(space):
    """The server as it stands, as a layout file's text: {text} or {error}."""
    try:
        layout, _ = read(space)
    except Refused as e:
        return {"error": str(e)}
    return {"text": as_file(layout)}


# ---- a plan -------------------------------------------------------------------------

def _change(op, kind, name, said, asks=False, **more):
    return {"op": op, "kind": kind, "name": name, "said": said, "asks": bool(asks), **more}


def diff(want, have):
    """What applying `want` to a server that is `have` changes, in order:
    [{op: add|edit|remove, kind, name, said, asks}]. `asks` is a change a
    person allows whatever a session's dial says: a removal, a permission
    granted or taken (a role's, an overwrite's)."""
    out = []
    hr = {r["name"]: r for r in have["roles"]}
    for r in want["roles"]:
        h = hr.get(r["name"])
        if not h:
            if r["name"] == "@everyone":
                continue
            out.append(_change("add", "role", r["name"], f"role {r['name']} added"
                               + (f" with {', '.join(r['permissions'])}" if r["permissions"] else ""),
                               asks=bool(r["permissions"]), want=r))
            continue
        moved = [k for k in ("color", "hoist", "mentionable") if r[k] != h[k]]
        perms = r["permissions"] != h["permissions"]
        if moved or perms:
            gained = sorted(set(r["permissions"]) - set(h["permissions"]))
            lost = sorted(set(h["permissions"]) - set(r["permissions"]))
            said = f"role {r['name']}: " + "; ".join(
                ([f"{', '.join(moved)} changed"] if moved else [])
                + ([f"gains {', '.join(gained)}"] if gained else []) + ([f"loses {', '.join(lost)}"] if lost else []))
            out.append(_change("edit", "role", r["name"], said, asks=perms, want=r))
    want_cats = {c["name"]: c for c in want["categories"]}
    have_cats = {c["name"]: c for c in have["categories"]}
    for c in want["categories"]:
        h = have_cats.get(c["name"])
        if not h:
            out.append(_change("add", "category", c["name"], f"category {c['name']} added", asks=bool(c["overwrites"]), want=c))
        elif c["overwrites"] != h["overwrites"]:
            out.append(_change("edit", "category", c["name"], f"category {c['name']}: its permissions changed", asks=True, want=c))

    def chans(cat, want_rows, have_rows):
        hc = {c["name"]: c for c in have_rows}
        where = f" in {cat}" if cat else ""
        for c in want_rows:
            h = hc.get(c["name"])
            if not h:
                out.append(_change("add", "channel", c["name"], f"#{c['name']} added{where} ({c['kind']})",
                                   asks=bool(c["overwrites"]), want=c, parent=cat))
                continue
            if h["kind"] != c["kind"]:
                out.append(_change("edit", "channel", c["name"], f"#{c['name']}{where} is {h['kind']} there and {c['kind']} "
                                   "here: Discord does not change a channel's kind, so remove it and add it again", asks=True,
                                   want=c, parent=cat, cannot=True))
                continue
            what = (["its topic"] if h["topic"] != c["topic"] else []) + (["its permissions"] if h["overwrites"] != c["overwrites"] else [])
            if what:
                out.append(_change("edit", "channel", c["name"], f"#{c['name']}{where}: {' and '.join(what)} changed",
                                   asks=h["overwrites"] != c["overwrites"], want=c, parent=cat))
    chans("", want["channels"], have["channels"])
    for c in want["categories"]:
        chans(c["name"], c["channels"], (have_cats.get(c["name"]) or {}).get("channels") or [])
    ha = {a["name"]: a for a in have["automod"]}
    for a in want["automod"]:
        h = ha.get(a["name"])
        if not h:
            n = len(a["keywords"])
            out.append(_change("add", "automod", a["name"], f"AutoMod rule {a['name']} added ({n} word{'s' if n != 1 else ''})", want=a))
        elif h != a:
            out.append(_change("edit", "automod", a["name"], f"AutoMod rule {a['name']} changed", want=a))
    for ch, msgs in want["pins"].items():
        for m in msgs:
            if m not in (have["pins"].get(ch) or []):
                out.append(_change("add", "pin", ch, f"a message pinned in #{ch}: {m[:60]}", text=m))
    # Removals last: what the file no longer names. Each asks a person.
    wr = {r["name"] for r in want["roles"]}
    for r in have["roles"]:
        if r["name"] not in wr and r["name"] != "@everyone":
            out.append(_change("remove", "role", r["name"], f"role {r['name']} removed", asks=True))
    wanted = {("", c["name"]) for c in want["channels"]} | {(cat["name"], c["name"]) for cat in want["categories"] for c in cat["channels"]}
    for c in have["channels"]:
        if ("", c["name"]) not in wanted:
            out.append(_change("remove", "channel", c["name"], f"#{c['name']} removed", asks=True, parent=""))
    for cat in have["categories"]:
        for c in cat["channels"]:
            if (cat["name"], c["name"]) not in wanted:
                out.append(_change("remove", "channel", c["name"], f"#{c['name']} in {cat['name']} removed", asks=True, parent=cat["name"]))
        if cat["name"] not in want_cats:
            out.append(_change("remove", "category", cat["name"], f"category {cat['name']} removed", asks=True))
    wa = {a["name"] for a in want["automod"]}
    for a in have["automod"]:
        if a["name"] not in wa:
            out.append(_change("remove", "automod", a["name"], f"AutoMod rule {a['name']} removed", asks=True))
    for ch, msgs in have["pins"].items():
        for m in msgs:
            if m not in (want["pins"].get(ch) or []):
                out.append(_change("remove", "pin", ch, f"a message unpinned and deleted in #{ch}: {m[:60]}", asks=True, text=m))
    return out


def plan(space, text, by=""):
    """What applying `text` (deploy/discord.yml) would change: {changes,
    asks, said} or {error}. Kept with the space's last plans."""
    import markup
    try:
        want = normalize(markup.yaml_load(text or "") or {})
    except ValueError as e:
        return {"error": f"{LAYOUT}: {e}"}
    except Exception as e:                                  # noqa: BLE001 (the reader's own words)
        return {"error": f"{LAYOUT} does not read as YAML: {e}"}
    try:
        have, _ = read(space)
    except Refused as e:
        return {"error": str(e)}
    changes = diff(want, have)
    n_ask = sum(1 for c in changes if c["asks"])
    said = (f"{len(changes)} change{'s' if len(changes) != 1 else ''}" + (f", {n_ask} a person allows" if n_ask else "")
            if changes else "nothing to change: the server is as the file says")
    _note_plan(space, {"at": int(time.time()), "by": by, "said": said, "changes": [c["said"] for c in changes][:40]})
    return {"changes": changes, "asks": n_ask, "said": said}


def _note_plan(space, row):
    with _lock:
        d = _load()
        rec = d.get(space)
        if not isinstance(rec, dict):
            return
        rec["plans"] = ([row] + list(rec.get("plans") or []))[:KEEP_PLANS]
        _save(d)


# ---- apply ---------------------------------------------------------------------------

def apply(space, text, by="", allowed=False):
    """The layout made so: every change in the plan's order, the ones that
    ask a person only where `allowed` (a person applying, or a person's
    Allow on a session's ask). {ok, done: [said], left: [said]} or {error,
    done}; each call audited."""
    got = plan(space, text, by=by)
    if got.get("error"):
        return got
    try:
        token, guild = _conn(space)
        _, ids = read(space)
    except Refused as e:
        return {"error": str(e)}
    done, left = [], []
    for c in got["changes"]:
        if c.get("cannot") or (c["asks"] and not allowed):
            left.append(c["said"])
            continue
        try:
            _do(token, guild, ids, c)
        except (Refused, ValueError) as e:
            return {"error": f"{c['said']}: {e}", "done": done, "left": left}
        done.append(c["said"])
        if audit:
            audit(by, "discord-apply", space, {"change": c["said"][:200], "asked": c["asks"]})
    _note_plan(space, {"at": int(time.time()), "by": by, "said": f"applied {len(done)}" + (f", {len(left)} left" if left else ""),
                       "changes": done[:40], "applied": True})
    return {"ok": True, "done": done, "left": left}


def _overwrites(rows, ids):
    out = []
    for o in rows:
        rid = ids["roles"].get(o["role"])
        if not rid:
            raise ValueError(f"no role {o['role']} on the server yet")
        out.append({"id": rid, "type": 0, "allow": str(_perm_bits(o["allow"])), "deny": str(_perm_bits(o["deny"]))})
    return out


def _do(token, guild, ids, c):
    """One change made on the server, the ids kept up as it goes."""
    w, kind, op = c.get("want") or {}, c["kind"], c["op"]
    if kind == "role":
        body = {"name": w.get("name"), "permissions": str(_perm_bits(w.get("permissions"))),
                "color": int((w.get("color") or "#000000")[1:], 16), "hoist": w.get("hoist", False),
                "mentionable": w.get("mentionable", False)}
        if op == "add":
            r = _call(token, "POST", f"/guilds/{guild}/roles", body)
            ids["roles"][c["name"]] = str(r.get("id"))
        elif op == "edit":
            rid = ids["roles"][c["name"]]
            _call(token, "PATCH", f"/guilds/{guild}/roles/{rid}",
                  {"permissions": body["permissions"]} if c["name"] == "@everyone" else body)
        else:
            _call(token, "DELETE", f"/guilds/{guild}/roles/{ids['roles'][c['name']]}")
    elif kind == "category":
        key = ("", c["name"], "category")
        if op == "add":
            r = _call(token, "POST", f"/guilds/{guild}/channels",
                      {"name": c["name"], "type": CATEGORY, "permission_overwrites": _overwrites(w["overwrites"], ids)})
            ids["channels"][key] = str(r.get("id"))
        elif op == "edit":
            _call(token, "PATCH", f"/channels/{ids['channels'][key]}", {"permission_overwrites": _overwrites(w["overwrites"], ids)})
        else:
            _call(token, "DELETE", f"/channels/{ids['channels'][key]}")
    elif kind == "channel":
        key = (c.get("parent") or "", c["name"], "channel")
        parent = ids["channels"].get(("", c.get("parent") or "", "category")) if c.get("parent") else None
        if op == "add":
            r = _call(token, "POST", f"/guilds/{guild}/channels",
                      {"name": c["name"], "type": KINDS[w["kind"]], "topic": w.get("topic") or None,
                       "parent_id": parent, "permission_overwrites": _overwrites(w["overwrites"], ids)})
            ids["channels"][key] = str(r.get("id"))
        elif op == "edit":
            _call(token, "PATCH", f"/channels/{ids['channels'][key]}",
                  {"topic": w.get("topic") or None, "permission_overwrites": _overwrites(w["overwrites"], ids)})
        else:
            _call(token, "DELETE", f"/channels/{ids['channels'][key]}")
    elif kind == "automod":
        body = {"name": c["name"], "event_type": 1, "trigger_type": 1,
                "trigger_metadata": {"keyword_filter": w.get("keywords") or []},
                "actions": [{"type": 1}], "enabled": w.get("enabled", True)}
        if op == "add":
            r = _call(token, "POST", f"/guilds/{guild}/auto-moderation/rules", body)
            ids["automod"][c["name"]] = str(r.get("id"))
        elif op == "edit":
            _call(token, "PATCH", f"/guilds/{guild}/auto-moderation/rules/{ids['automod'][c['name']]}", body)
        else:
            _call(token, "DELETE", f"/guilds/{guild}/auto-moderation/rules/{ids['automod'][c['name']]}")
    elif kind == "pin":
        cid = next((v for (cat, name, what), v in ids["channels"].items() if what == "channel" and name == c["name"]), "")
        if not cid:
            raise ValueError(f"no channel #{c['name']} on the server")
        if op == "add":
            m = _call(token, "POST", f"/channels/{cid}/messages", {"content": c["text"][:2000]})
            _call(token, "PUT", f"/channels/{cid}/pins/{m.get('id')}")
        else:
            mid = (ids["pins"].get(c["name"]) or {}).get(c["text"])
            if mid:
                _call(token, "DELETE", f"/channels/{cid}/messages/{mid}")
