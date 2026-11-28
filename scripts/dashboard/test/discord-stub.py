"""A stand-in for Discord's REST API, for the browser suites, as
agent-stub.py stands in for a node: the server the harness's controller
calls through BB_DISCORD_API. One server, "Shop community", with a role, a
category and two channels; a bot's token is the one in TOKEN. Its world is
kept in a file under the fixture (DISCORD_STUB_STATE), so every suite
starts from the same server when the world is put back.

  DISCORD_STUB_PORT   the port it answers on
  DISCORD_STUB_STATE  the file its server is kept in
"""
import json
import os
import threading
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer

TOKEN = "MTI" + "s" * 60
GUILD = "900"
STATE = os.environ.get("DISCORD_STUB_STATE", "discord-world.json")
_lock = threading.Lock()


def _bits(*names):
    order = ("create_instant_invite", "kick_members", "ban_members", "administrator", "manage_channels",
             "manage_guild", "add_reactions", "view_audit_log", "priority_speaker", "stream", "view_channel",
             "send_messages", "send_tts_messages", "manage_messages")
    return str(sum(1 << order.index(n) for n in names))


def fresh():
    return {"n": 1000, "guilds": [{"id": GUILD, "name": "Shop community"}],
            "roles": {GUILD: {"id": GUILD, "name": "@everyone", "permissions": _bits("view_channel", "send_messages"), "position": 0, "color": 0},
                      "901": {"id": "901", "name": "Moderators", "permissions": _bits("manage_messages"), "position": 2, "color": 0xe67e22, "hoist": True}},
            "chans": {"910": {"id": "910", "name": "Welcome", "type": 4, "position": 0, "permission_overwrites": []},
                      "911": {"id": "911", "name": "rules", "type": 0, "parent_id": "910", "topic": "read first", "position": 1,
                              "permission_overwrites": []},
                      "912": {"id": "912", "name": "general", "type": 0, "position": 2, "permission_overwrites": []}},
            "automod": {}, "pins": {}, "features": [], "onboarding": {"prompts": [], "default_channel_ids": [], "enabled": False}}


def load():
    try:
        with open(STATE) as f:
            return json.load(f)
    except (OSError, ValueError):
        return fresh()


def save(w):
    with open(STATE, "w") as f:
        json.dump(w, f)


class Discord(BaseHTTPRequestHandler):
    def log_message(self, *a):
        pass

    def _send(self, code, body=None):
        raw = json.dumps(body if body is not None else {}).encode()
        self.send_response(code)
        self.send_header("Content-Type", "application/json")
        self.send_header("Content-Length", str(len(raw)))
        self.end_headers()
        self.wfile.write(raw)

    def _go(self, method):
        n = int(self.headers.get("Content-Length") or 0)
        body = json.loads(self.rfile.read(n) or b"{}") if n else {}
        if self.headers.get("Authorization") != f"Bot {TOKEN}":
            return self._send(401, {"message": "401: Unauthorized"})
        with _lock:
            w = load()
            code, out = self._answer(w, method, self.path.split("?")[0], body)
            save(w)
        self._send(code, out)

    def _answer(self, w, method, p, body):
        if p == "/users/@me":
            return 200, {"id": "800", "bot": True, "username": "shopbot"}
        if p == "/users/@me/guilds":
            return 200, w["guilds"]
        g = f"/guilds/{GUILD}"
        if p == g and method == "GET":
            return 200, {"id": GUILD, "name": w["guilds"][0]["name"], "features": w.get("features") or []}
        if p == g + "/onboarding":
            if "COMMUNITY" not in (w.get("features") or []):
                return 403, {"message": "Missing Access", "code": 50001}
            if method == "PUT":
                w["onboarding"] = {"prompts": body.get("prompts") or [], "default_channel_ids": body.get("default_channel_ids") or [],
                                   "enabled": bool(body.get("enabled"))}
            return 200, {"guild_id": GUILD, **(w.get("onboarding") or {})}

        def made(table):
            w["n"] += 1
            table[str(w["n"])] = {**body, "id": str(w["n"]), "position": 9}
            return table[str(w["n"])]
        if p == g + "/roles":
            return (200, made(w["roles"])) if method == "POST" else (200, list(w["roles"].values()))
        if p.startswith(g + "/roles/"):
            rid = p.rsplit("/", 1)[1]
            if method == "DELETE":
                w["roles"].pop(rid, None)
                return 204, {}
            w["roles"][rid].update(body)
            return 200, w["roles"][rid]
        if p == g + "/channels":
            return (200, made(w["chans"])) if method == "POST" else (200, list(w["chans"].values()))
        if p == g + "/auto-moderation/rules":
            return (200, made(w["automod"])) if method == "POST" else (200, list(w["automod"].values()))
        if p.startswith(g + "/auto-moderation/rules/"):
            aid = p.rsplit("/", 1)[1]
            if method == "DELETE":
                w["automod"].pop(aid, None)
                return 204, {}
            w["automod"][aid].update(body)
            return 200, w["automod"][aid]
        if p.startswith("/channels/"):
            parts = p.split("/")
            cid = parts[2]
            if len(parts) == 3:
                if method == "DELETE":
                    w["chans"].pop(cid, None)
                    return 204, {}
                w["chans"][cid].update(body)
                return 200, w["chans"][cid]
            if parts[3] == "pins" and method == "GET":
                return 200, w["pins"].get(cid, [])
            if parts[3] == "messages" and method == "POST":
                w["n"] += 1
                w["pins"].setdefault("pending", []).append({"id": str(w["n"]), "content": body.get("content", ""), "author": {"id": "800"}})
                return 200, {"id": str(w["n"])}
            if parts[3] == "pins" and method == "PUT":
                m = next(x for x in w["pins"].get("pending", []) if x["id"] == parts[4])
                w["pins"].setdefault(cid, []).insert(0, m)
                return 204, {}
            if parts[3] == "messages" and method == "DELETE":
                w["pins"][cid] = [m for m in w["pins"].get(cid, []) if m["id"] != parts[4]]
                return 204, {}
        return 404, {"message": "Unknown"}

    def do_GET(self):
        self._go("GET")

    def do_POST(self):
        self._go("POST")

    def do_PATCH(self):
        self._go("PATCH")

    def do_PUT(self):
        self._go("PUT")

    def do_DELETE(self):
        self._go("DELETE")


if __name__ == "__main__":
    ThreadingHTTPServer(("127.0.0.1", int(os.environ.get("DISCORD_STUB_PORT") or 0)), Discord).serve_forever()
