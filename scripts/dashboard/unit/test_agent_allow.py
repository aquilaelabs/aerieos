"""What a coding agent need not ask about (R231): the aerie verbs the
controller decides, said to each agent the way its manifest says it is told,
and nothing that runs a command of the session's own."""
import json
import os
import sys
import unittest

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))
import agents  # noqa: E402
import toolpacks  # noqa: E402


class Allow(unittest.TestCase):
    def test_each_shipped_agent_is_told_in_its_own_words(self):
        claude = agents.allow_plan("claude")
        self.assertIn("Bash(aerie version *)", claude["settings"])
        self.assertIn("Bash(bb bug *)", claude["settings"])
        self.assertEqual((claude["args"], claude["file"]), ([], None))
        grok = agents.allow_plan("grok")["args"]
        self.assertEqual(grok[:2], ["--allow", "Bash(aerie version:*)"])
        copilot = agents.allow_plan("copilot")["args"]
        self.assertEqual(copilot[:2], ["--allow-tool", "shell(aerie version:*)"])
        codex = agents.allow_plan("codex")["file"]
        self.assertEqual(codex["path"], ".codex/rules/aerieos.rules")
        self.assertIn('prefix_rule(pattern=["aerie", "version"], decision="allow")', codex["text"])
        # OpenCode is started with every command allowed already, and an
        # agent nobody knows is told nothing.
        for nobody in ("open", "nosuch"):
            self.assertEqual(agents.allow_plan(nobody), {"settings": [], "args": [], "file": None})

    def test_only_the_verbs_the_controller_decides(self):
        said = json.dumps([agents.allow_plan(a) for a in ("claude", "codex", "copilot", "grok")])
        for verb in ("run", "build", "test", "emu", "gpu", "shell", "capture", "dashboard"):
            self.assertNotIn(f"aerie {verb}", said, verb)
            self.assertNotIn(json.dumps(["aerie", verb]), said, verb)
        # Never the whole command: that would hand `aerie run -- anything` past the agent's check.
        self.assertNotIn("Bash(aerie *)", said)
        self.assertNotIn("shell(aerie:*)", said)
        for verb in ("version", "roadmap", "bug", "git", "forge", "devapp", "sign"):
            self.assertIn(f"aerie {verb}", said)

    def test_a_manifest_s_words_are_held_to_a_shape(self):
        ok = {"how": "flag", "flag": "--allow", "rule": "Bash({cmd}:*)"}
        self.assertEqual(agents.allow_checked(ok), (ok, ""))
        self.assertEqual(agents.allow_checked(None), (None, ""))
        self.assertEqual(agents.allow_checked({"how": "none"}), (None, ""))
        for bad in ({"how": "magic", "rule": "x {cmd}"}, {"how": "flag", "flag": "allow", "rule": "x({cmd})"},
                    {"how": "flag", "flag": "--allow", "rule": "no place for the command"},
                    {"how": "flag", "flag": "--allow", "rule": "x({cmd}); rm -rf $HOME"},
                    {"how": "rules-file", "file": "../etc/x", "rule": "r({argv})"},
                    {"how": "rules-file", "file": "/etc/x", "rule": "r({argv})"}):
            spec, why = agents.allow_checked(bad)
            self.assertIsNone(spec, bad)
            self.assertTrue(why, bad)

    def test_a_pack_s_agent_says_its_own(self):
        plan = agents.allow_plan("zed", {"how": "flag", "flag": "--auto-approve", "rule": "{cmd}"})
        self.assertEqual(plan["args"][:2], ["--auto-approve", "aerie version"])
        errors, out = [], {}
        toolpacks._agent_allow({"allow": {"how": "flag", "flag": "--auto-approve", "rule": "{cmd}"}}, out, errors)
        self.assertEqual((errors, out["allow"]["flag"]), ([], "--auto-approve"))
        errors, out = [], {}
        toolpacks._agent_allow({"allow": {"how": "flag", "flag": "nope", "rule": "{cmd}"}}, out, errors)
        self.assertTrue(errors)
        self.assertNotIn("allow", out)


if __name__ == "__main__":
    unittest.main()
