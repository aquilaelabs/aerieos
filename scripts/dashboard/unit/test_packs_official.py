"""The official packs (R169 step 1): every shipped toolchain and every
agent as a pack in bbtool.json's format, validated as such (a shipped
recipe or an agent's adapter standing in for steps and verbs, a shipped
name allowed), an agent that cannot take the guards refused, and the
export's check holding packs/ to the tables."""
import json
import os
import subprocess
import sys
import unittest

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.dirname(os.path.dirname(os.path.dirname(HERE)))
sys.path.insert(0, os.path.join(HERE, ".."))
import toolpacks  # noqa: E402


class Official(unittest.TestCase):
    def test_a_config_block_is_checked_and_a_service_is_official_only(self):
        # R172: what a pack asks for per node, drawn by the Library as Configure.
        good = {"name": "hexkit", "label": "Hexkit", "platforms": ["linux/amd64"], "terms": [], "layout": {"bin": [], "env": {}},
                "verbs": {"dump": {"about": "dump", "usage": "FILE", "run": ["{dir}/bin/hexkit", "{args}"]}},
                "config": [{"name": "api_key", "label": "API key", "kind": "secret", "env": "HEXKIT_KEY", "required": True},
                           {"name": "region", "kind": "choice", "choices": [{"value": "eu"}, {"value": "us", "label": "US"}]},
                           {"name": "hosts", "kind": "list", "fields": [{"name": "name", "kind": "text"}, {"name": "key", "kind": "secret"}]},
                           {"name": "verbose", "kind": "switch"}]}
        clean, errors = toolpacks.validate(good)
        self.assertEqual(errors, [])
        self.assertEqual([f["kind"] for f in clean["config"]], ["secret", "choice", "list", "switch"])
        self.assertEqual((clean["config"][0]["env"], clean["config"][0]["required"], clean["config"][1]["choices"][1]["label"]), ("HEXKIT_KEY", True, "US"))
        self.assertEqual([f["name"] for f in clean["config"][2]["fields"]], ["name", "key"])
        for bad, said in (([{"name": "x", "kind": "magic"}], "kind is one of"), ([{"name": "A", "kind": "text"}], "name is"),
                          ([{"name": "a", "kind": "text"}, {"name": "a", "kind": "text"}], "once"),
                          ([{"name": "l", "kind": "list", "fields": [{"name": "p", "kind": "projects"}]}], "not inside a list"),
                          ([{"name": "c", "kind": "choice"}], "choices lists"), ("no", "config is a list")):
            _c, errors = toolpacks.validate(dict(good, config=bad))
            self.assertTrue(any(said in e for e in errors), (bad, errors))
        _c, errors = toolpacks.validate(dict(good, service={"kind": "router"}))
        self.assertTrue(any("official pack's alone" in e for e in errors))
        import router
        clean, errors = toolpacks.validate(router.pack(), official=True)
        self.assertEqual(errors, [])
        self.assertEqual((clean["service"], clean["verbs"], [f["name"] for f in clean["config"]][-3:]), ({"kind": "router"}, {}, ["custom", "ollama", "projects"]))
        _c, errors = toolpacks.validate(dict(router.pack(), service={"kind": "nope"}), official=True)
        self.assertTrue(any("service.kind is one of" in e for e in errors))

    def test_an_official_pack_stands_in_for_steps_and_verbs(self):
        m = {"name": "jdk", "label": "JDK", "tier": "official", "platforms": ["linux/amd64"], "terms": [],
             "layout": {"bin": ["bin"], "env": {"JAVA_HOME": ""}, "tool": "bin/java"}, "shipped": {"source": {"kind": "tarball"}}}
        clean, errors = toolpacks.validate(m, shipped=("jdk",), official=True)
        self.assertEqual(errors, [])
        self.assertEqual((clean["tier"], clean["shipped"]["source"]["kind"], clean["verbs"]), ("official", "tarball", {}))
        clean, errors = toolpacks.validate(dict(m, tier="url"), shipped=("jdk",))
        self.assertTrue(any("a name of its own" in e for e in errors) and any("official pack's alone" in e for e in errors))

    def test_official_is_the_caller_s_word_and_never_the_manifest_s(self):
        # What official unlocks is the shipped packs' alone: a shipped name
        # (a colon in it too), a shipped recipe, a service, a shipped
        # agent's table row and a layout under the store's root. A manifest
        # that says the tier of itself, as one added by address, pasted or
        # uploaded could, takes none of it.
        said = "tier official is said by AerieOS of the packs it ships, never by a manifest of itself: a pack leaves tier out"
        verbs = {"dump": {"about": "dump", "usage": "FILE", "run": ["{dir}/bin/hexkit", "{args}"]}}
        plain = {"name": "hexkit", "label": "Hexkit", "tier": "official", "platforms": ["linux/amd64"], "terms": [], "verbs": verbs}
        self.assertEqual(toolpacks.validate(plain)[1], [said], "the claim alone is refused, whatever else it asks for")
        self.assertEqual(toolpacks.validate(plain, official=False)[1], [said])
        self.assertEqual(toolpacks.validate(dict(plain, tier="url"))[1], [])
        import router
        a = {"product": "Claude Code", "command": "claude", "provider": "Anthropic", "reported": "claude", "update_job": "claude-update",
             "login_job": "claude-login", "logout_job": "claude-logout", "briefing": "system-prompt-file", "guards": "hooks", "state": "hooks",
             "transcripts": ".claude/projects", "latest_url": "", "tool": "claude-code"}
        for grab, refused in (
                ({"name": "jdk", "shipped": {"source": {"kind": "tarball"}}}, ("jdk is a toolchain AerieOS ships", "shipped (a toolchain's recipe) is an official pack's alone")),
                ({"name": "android:emulator", "verbs": verbs}, ("name is 2 to 40",)),
                ({"name": "graphics", "verbs": verbs}, ("graphics is one of aerie tool's own words",)),
                ({"name": "hexkit", "verbs": verbs, "layout": {"bin": ["root:android/bin"], "tool": "root:android/tool"}}, ("layout.bin lists directories inside the pack", "layout.tool is a file inside the pack")),
                ({k: v for k, v in router.pack().items() if k not in ("tier", "platforms", "terms", "label")}, ("service (a deployed thing of AerieOS's) is an official pack's alone",)),
                ({"name": "claude", "agent": a}, ("a coding agent AerieOS ships",))):
            m = {"label": "X", "tier": "official", "platforms": ["linux/amd64"], "terms": [], **grab}
            errors = toolpacks.validate(m, shipped=("jdk",))[1]
            self.assertIn(said, errors, grab["name"])
            for why in refused:
                self.assertTrue(any(why in e for e in errors), (grab["name"], why, errors))
            # ...and each is the shipped pack it is written as once the
            # caller says so.
            self.assertEqual(toolpacks.validate(m, shipped=("jdk",), official=True)[1], [], grab["name"])
        # The caller's word does not make a manifest official that is not
        # written as one.
        errors = toolpacks.validate({"name": "jdk", "label": "JDK", "platforms": ["linux/amd64"], "terms": [], "shipped": {"source": {"kind": "tarball"}}},
                                    shipped=("jdk",), official=True)[1]
        self.assertTrue(any("a name of its own" in e for e in errors) and any("official pack's alone" in e for e in errors), errors)

    def test_every_pack_this_tree_ships_is_official_by_the_tables_and_not_by_itself(self):
        # The files under packs/ say tier official, as the catalog's copies
        # do: read as a person's pack each is refused, and read as what the
        # tables wrote (tools/packs-export.py, the lint) each is whole.
        seen = 0
        for sub in ("official", "agents", "services"):
            for name in sorted(os.listdir(os.path.join(ROOT, "packs", sub))):
                with open(os.path.join(ROOT, "packs", sub, name, "bbtool.json"), encoding="utf-8") as f:
                    m = json.load(f)
                self.assertEqual(toolpacks.validate(m, official=True)[1], [], f"{sub}/{name}")
                self.assertTrue(any("tier official is said by AerieOS" in e for e in toolpacks.validate(m)[1]), f"{sub}/{name}")
                seen += 1
        self.assertGreater(seen, 30)
        import services
        import toolchains
        self.assertEqual(len(services.packs()), len(services.KINDS))
        for m in services.packs():
            self.assertEqual(toolpacks.validate(m, shipped={r["name"] for r in toolchains.load_toolchains()}, official=True)[1], [], m["name"])

    def test_an_agent_pack_is_checked_and_one_without_guards_is_refused(self):
        a = {"product": "Claude Code", "command": "claude", "provider": "Anthropic", "reported": "claude", "update_job": "claude-update",
             "login_job": "claude-login", "logout_job": "claude-logout", "briefing": "system-prompt-file", "guards": "hooks", "state": "hooks",
             "transcripts": ".claude/projects", "latest_url": "", "tool": "claude-code"}
        m = {"name": "claude", "label": "Claude", "tier": "official", "platforms": ["linux/*"], "terms": [], "agent": a}
        clean, errors = toolpacks.validate(m, official=True)
        self.assertEqual(errors, [])
        self.assertEqual(clean["agent"]["command"], "claude")
        clean, errors = toolpacks.validate({**m, "agent": {**a, "guards": "none"}}, official=True)
        self.assertTrue(any("cannot take AerieOS's guards" in e for e in errors))
        # Another pack's agent block is a pack agent's adapter (R169 step 8),
        # which never takes a shipped agent's name or its table's fields.
        clean, errors = toolpacks.validate({**m, "tier": "url"})
        self.assertTrue(any("a coding agent AerieOS ships" in e for e in errors), errors)

    def test_the_packs_written_match_the_tables(self):
        r = subprocess.run([sys.executable, os.path.join(ROOT, "tools", "packs-export.py"), "--check"], capture_output=True, text=True, check=False)
        self.assertEqual(r.returncode, 0, r.stdout + r.stderr)
        with open(os.path.join(ROOT, "packs", "agents", "claude", "bbtool.json"), encoding="utf-8") as f:
            m = json.load(f)
        self.assertEqual((m["tier"], m["agent"]["guards"]), ("official", "hooks"))
        with open(os.path.join(ROOT, "packs", "official", "jdk", "bbtool.json"), encoding="utf-8") as f:
            m = json.load(f)
        self.assertEqual(m["shipped"]["source"]["kind"], "tarball")


if __name__ == "__main__":
    unittest.main()
