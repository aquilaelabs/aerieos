"""A space's Discord server from a layout kept as code (R293), against a
stand-in for Discord's API: a bot's token taken and a user's refused, the
server pulled into the layout's shape, a plan that says what applying a
file adds, changes and removes and which of those a person allows, and an
apply that does the rest and leaves those until it is allowed."""
import json
import os
import shutil
import sys
import tempfile
import threading
import unittest
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))
sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "..", "lib"))
import discord  # noqa: E402

BOT = "MTI" + "x" * 60
GUILD = "900"


class World:
    def __init__(self):
        self.calls = []
        self.bot = True
        self.guilds = [{"id": GUILD, "name": "Shop community"}]
        self.roles = {GUILD: {"id": GUILD, "name": "@everyone", "permissions": str(discord.PERMS["view_channel"] | discord.PERMS["send_messages"]),
                              "position": 0, "color": 0},
                      "901": {"id": "901", "name": "Moderators", "permissions": str(discord.PERMS["manage_messages"]),
                              "position": 2, "color": 0xe67e22, "hoist": True},
                      "902": {"id": "902", "name": "Shop bot", "managed": True, "permissions": "0", "position": 3}}
        self.chans = {"910": {"id": "910", "name": "Welcome", "type": 4, "position": 0, "permission_overwrites": []},
                      "911": {"id": "911", "name": "rules", "type": 0, "parent_id": "910", "topic": "read first", "position": 1,
                              "permission_overwrites": [{"id": GUILD, "type": 0, "allow": "0", "deny": str(discord.PERMS["send_messages"])}]},
                      "912": {"id": "912", "name": "old-chat", "type": 0, "position": 2, "permission_overwrites": []}}
        self.automod = {}
        # Pinned by a person: not the layout's, which are the bot's own.
        self.pins = {"911": [{"id": "990", "content": "Be kind.", "author": {"id": "777"}}]}
        self.n = 1000
        self.features = []
        self.onboarding = {"prompts": [], "default_channel_ids": [], "enabled": False}


class Discord(BaseHTTPRequestHandler):
    world = None

    def log_message(self, *a):
        pass

    def _send(self, code, body=None):
        raw = json.dumps(body if body is not None else {}).encode()
        self.send_response(code)
        self.send_header("Content-Type", "application/json")
        self.send_header("Content-Length", str(len(raw)))
        self.end_headers()
        self.wfile.write(raw)

    def _body(self):
        n = int(self.headers.get("Content-Length") or 0)
        return json.loads(self.rfile.read(n) or b"{}") if n else {}

    def _go(self, method):
        w, p = self.world, self.path.split("?")[0]
        body = self._body() if method in ("POST", "PATCH", "PUT") else None
        w.calls.append((method, p, body))
        if self.headers.get("Authorization") != f"Bot {BOT}":
            return self._send(401, {"message": "401: Unauthorized"})
        if p == "/users/@me":
            return self._send(200, {"id": "800", "bot": w.bot, "username": "shopbot"})
        if p == "/users/@me/guilds":
            return self._send(200, w.guilds)
        g = f"/guilds/{GUILD}"
        if p == g and method == "GET":
            return self._send(200, {"id": GUILD, "name": "Shop community", "features": w.features})
        if p == g + "/onboarding":
            if "COMMUNITY" not in w.features:
                return self._send(403, {"message": "Missing Access"})
            if method == "PUT":
                w.onboarding = {k: body.get(k) for k in ("prompts", "default_channel_ids", "enabled")}
            return self._send(200, {"guild_id": GUILD, **w.onboarding})
        if p == g + "/roles":
            if method == "POST":
                w.n += 1
                w.roles[str(w.n)] = {**body, "id": str(w.n), "position": 1}
                return self._send(200, w.roles[str(w.n)])
            return self._send(200, list(w.roles.values()))
        if p.startswith(g + "/roles/"):
            rid = p.rsplit("/", 1)[1]
            if method == "DELETE":
                w.roles.pop(rid, None)
            else:
                w.roles[rid].update(body)
            return self._send(200, w.roles.get(rid, {}))
        if p == g + "/channels":
            if method == "POST":
                w.n += 1
                w.chans[str(w.n)] = {**body, "id": str(w.n), "position": 9}
                return self._send(200, w.chans[str(w.n)])
            return self._send(200, list(w.chans.values()))
        if p == g + "/auto-moderation/rules":
            if method == "POST":
                w.n += 1
                w.automod[str(w.n)] = {**body, "id": str(w.n)}
                return self._send(200, w.automod[str(w.n)])
            return self._send(200, list(w.automod.values()))
        if p.startswith("/channels/"):
            parts = p.split("/")
            cid = parts[2]
            if len(parts) == 3:
                if method == "DELETE":
                    w.chans.pop(cid, None)
                else:
                    w.chans[cid].update(body)
                return self._send(200, w.chans.get(cid, {}))
            if parts[3] == "pins" and method == "GET":
                return self._send(200, w.pins.get(cid, []))
            if parts[3] == "messages" and method == "POST":
                w.n += 1
                w.pins.setdefault("pending", []).append({"id": str(w.n), "content": body["content"], "author": {"id": "800"}, "cid": cid})
                return self._send(200, {"id": str(w.n)})
            if parts[3] == "pins" and method == "PUT":
                m = next(x for x in w.pins["pending"] if x["id"] == parts[4])
                w.pins.setdefault(cid, []).insert(0, m)
                return self._send(204)
            if parts[3] == "messages" and method == "DELETE":
                w.pins[cid] = [m for m in w.pins.get(cid, []) if m["id"] != parts[4]]
                return self._send(204)
        return self._send(404, {"message": "Unknown"})

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


LAYOUT = """
roles:
  - name: "@everyone"
    permissions: [view_channel, send_messages]
  - name: Moderators
    color: "#e67e22"
    hoist: true
    permissions: [manage_messages, kick_members]
  - name: Regulars
    color: "#3498db"
categories:
  - name: Welcome
    channels:
      - name: rules
        topic: read first
        overwrites:
          - role: "@everyone"
            deny: [send_messages]
      - name: Introductions
        topic: say hello
automod:
  - name: No invites
    keywords: ["discord.gg/*"]
pins:
  rules:
    - Be kind.
    - No spam.
"""


class Base(unittest.TestCase):
    def setUp(self):
        self.tmp = Path(tempfile.mkdtemp())
        self.addCleanup(shutil.rmtree, self.tmp, True)
        self.w = World()
        Discord.world = self.w
        self.srv = ThreadingHTTPServer(("127.0.0.1", 0), Discord)
        threading.Thread(target=self.srv.serve_forever, daemon=True).start()
        self.addCleanup(self.srv.server_close)
        self.addCleanup(self.srv.shutdown)
        self.audits = []
        discord.configure(state=self.tmp, write_json_fn=lambda p, d, mode=None: Path(p).write_text(json.dumps(d)),
                          audit_fn=lambda *a: self.audits.append(a), api=f"http://127.0.0.1:{self.srv.server_port}")

    def connect(self):
        r = discord.connect("shop", BOT, by="user:ann")
        self.assertTrue(r.get("ok"), r)


class Connect(Base):
    def test_a_users_token_is_refused_and_a_bots_kept_unread(self):
        self.w.bot = False
        self.assertIn("user account's token is refused", discord.connect("shop", BOT)["error"])
        self.w.bot = True
        self.assertIn("does not read as a Discord bot token", discord.connect("shop", "short")["error"])
        self.connect()
        st = discord.status("shop")
        self.assertEqual((st["connected"], st["guild_name"]), (True, "Shop community"))
        self.assertNotIn(BOT, json.dumps(st), "never shown again")
        self.assertIn("permissions=", st["invite"])
        self.assertEqual(self.audits[-1][1], "discord-connect")

    def test_a_bot_in_no_server_is_given_its_invite(self):
        self.w.guilds = []
        r = discord.connect("shop", BOT)
        self.assertIn("in no server yet", r["error"])
        self.assertIn("client_id=800", r["invite"])

    def test_forget(self):
        self.connect()
        self.assertTrue(discord.forget("shop")["ok"])
        self.assertFalse(discord.status("shop")["connected"])


class Plan(Base):
    def test_the_server_is_pulled_into_the_layouts_shape(self):
        self.connect()
        layout, _ = discord.read("shop")
        self.assertEqual([r["name"] for r in layout["roles"]], ["Moderators", "@everyone"], "a bot's own role left out")
        self.assertEqual(layout["categories"][0]["channels"][0]["overwrites"],
                         [{"role": "@everyone", "allow": [], "deny": ["send_messages"]}])
        self.assertEqual(layout["pins"], {})
        self.assertIn("old-chat", discord.pull("shop")["text"])

    def test_a_plan_says_what_changes_and_which_a_person_allows(self):
        self.connect()
        got = discord.plan("shop", LAYOUT, by="user:ann")
        said = {c["said"]: c["asks"] for c in got["changes"]}
        self.assertEqual(said["role Moderators: gains kick_members"], True, "a permission granted asks")
        self.assertEqual(said["role Regulars added"], False)
        self.assertEqual(said["#introductions added in Welcome (text)"], False, "named as Discord keeps it")
        self.assertEqual(said["AutoMod rule No invites added (1 word)"], False)
        self.assertEqual(said["#old-chat removed"], True, "a removal asks")
        self.assertIn("a message pinned in #rules: No spam.", said, "a person's pin is not the bot's")
        self.assertEqual(got["asks"], 2)
        self.assertEqual(discord.status("shop")["plans"][0]["by"], "user:ann")

    def test_a_layout_that_does_not_read_says_why(self):
        self.connect()
        self.assertIn("no Discord permission called fly", discord.plan("shop", "roles:\n  - name: A\n    permissions: [fly]\n")["error"])
        self.assertIn("kind is one of", discord.plan("shop", "channels:\n  - name: a\n    kind: blog\n")["error"])


class Apply(Base):
    def test_the_rest_is_done_and_what_asks_is_left_until_allowed(self):
        self.connect()
        # A pin the bot made is the layout's own: its own author id.
        self.w.pins["911"][0]["author"]["id"] = "800"
        got = discord.apply("shop", LAYOUT, by="session:shop")
        self.assertTrue(got["ok"], got)
        self.assertIn("role Regulars added", got["done"])
        self.assertIn("#old-chat removed", got["left"])
        self.assertIn("role Moderators: gains kick_members", got["left"])
        self.assertIn("912", self.w.chans, "nothing removed without an Allow")
        made = next(c for c in self.w.chans.values() if c["name"] == "introductions")
        self.assertEqual(made["parent_id"], "910")
        self.assertTrue(self.w.automod)
        self.assertEqual([m["content"] for m in self.w.pins["911"]], ["No spam.", "Be kind."])
        # Allowed: the rest, and then nothing is left to change.
        got = discord.apply("shop", LAYOUT, by="user:ann", allowed=True)
        self.assertTrue(got["ok"], got)
        self.assertNotIn("912", self.w.chans)
        mods = self.w.roles["901"]
        self.assertEqual(int(mods["permissions"]), discord.PERMS["manage_messages"] | discord.PERMS["kick_members"])
        self.assertEqual(discord.plan("shop", LAYOUT)["changes"], [])
        self.assertTrue(any(a[1] == "discord-apply" for a in self.audits))

    def test_onboarding_is_left_on_a_server_that_is_not_community_and_set_on_one(self):
        # The operator, 26 Nov: onboarding questions in the layout; nothing
        # turns Community on, and the plan says so where it is off.
        self.connect()
        self.w.pins["911"][0]["author"]["id"] = "800"
        layout = LAYOUT + """onboarding:
  default_channels: [rules]
  questions:
    - title: What brings you here?
      single: true
      options:
        - title: Helping out
          description: the moderators' corner
          roles: [Regulars]
          channels: [introductions]
"""
        plan = discord.plan("shop", layout)
        row = next(c for c in plan["changes"] if c["kind"] == "onboarding")
        self.assertTrue(row.get("cannot") and "not a Community server" in row["said"], row)
        got = discord.apply("shop", layout, by="user:ann", allowed=True)
        self.assertTrue(got["ok"], got)
        self.assertTrue(any("onboarding left" in x for x in got["left"]))
        self.w.features = ["COMMUNITY"]
        row = next(c for c in discord.plan("shop", layout)["changes"] if c["kind"] == "onboarding")
        self.assertTrue(row["asks"] and row["said"] == "onboarding set: 1 question, 1 default channel", row)
        self.assertTrue(discord.apply("shop", layout, by="session:shop")["left"], "what new members are asked waits on a person")
        got = discord.apply("shop", layout, by="user:ann", allowed=True)
        self.assertIn("onboarding set: 1 question, 1 default channel", got["done"])
        prompt = self.w.onboarding["prompts"][0]
        regulars = next(k for k, r in self.w.roles.items() if r["name"] == "Regulars")
        intro = next(k for k, c in self.w.chans.items() if c["name"] == "introductions")
        self.assertEqual((prompt["title"], prompt["single_select"], prompt["options"][0]["role_ids"], prompt["options"][0]["channel_ids"]),
                         ("What brings you here?", True, [regulars], [intro]))
        self.assertEqual(self.w.onboarding["default_channel_ids"], ["911"])
        self.assertEqual(discord.plan("shop", layout)["changes"], [], "read back as the file says")
        self.assertIn("What brings you here?", discord.pull("shop")["text"])


if __name__ == "__main__":
    unittest.main()
