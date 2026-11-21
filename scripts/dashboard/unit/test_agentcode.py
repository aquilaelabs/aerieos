"""The coding agents as a node's rows in the Library and on the
Installed page (R95 step 2): the census's version against the registry's latest, each install its
own job, Claude Code one of them in its own words, and the node agent's
half run against a stub installer, never a vendor's."""
import contextlib
import hashlib
import io
import json
import os
import subprocess
import sys
import tempfile
import time
import unittest
from unittest import mock

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, os.path.join(HERE, ".."))
import agentcode  # noqa: E402
import agents  # noqa: E402
import packformat  # noqa: E402
import toolchains  # noqa: E402
sys.path.insert(0, HERE)
import agentpkg  # noqa: E402


def node(codex="codex-cli 0.160.0", copilot="", up=True, **kw):
    return {"id": "n1", "name": "box", "kind": "agent", "live": True,
            "reported": {"sandbox": True, "session": {"up": up, "codex": codex, "copilot": copilot}}} | kw


class Nodes:
    def __init__(self, n):
        self.n, self.added, self.reported = n, [], []

    def node_list(self):
        return [self.n]

    def node(self, nid):
        return self.n

    def jobs_for(self, *a, **k):
        return []

    def job_add(self, principal, where, type_, spec):
        self.added.append((type_, spec))
        return {"ok": True, "job": "j_1"}

    def job(self, jid, with_log=False):
        return {"log": self.log}

    def reported_set(self, nid, half, key, value):
        self.reported.append((nid, half, key, value))


# A recipe both halves take, and what neither does: the controller holds a
# manifest's to this shape (agents.install_checked) and the node what it is
# handed (the agent's recipe_checked).
GOOD = {"rev": 1, "script": "curl -fsSL https://x.example/install | bash", "pin": ["VERSION", "v{v}"],
        "env": {"PREFIX": "{home}/.local"}, "bin": ".local/bin/x", "also": [], "fresh": ""}
BAD_RECIPES = (
    {"script": "curl -fsSL https://x.example/i | bash; rm -rf ~"},
    {"script": "curl -fsSL https://x.example/i | bash -s -- $(id)"},
    {"script": "curl -fsSL https://x.example/i | bash -s -- `id`"},
    {"script": "curl -fsSL http://x.example/i | bash"},
    {"script": "wget -qO- https://x.example/i | bash"},
    {"script": "curl -fsSL https://x.example/i | bash && curl https://y.example"},
    {"bin": "../x/y"}, {"bin": "/usr/bin/x"}, {"bin": ".ssh"}, {"bin": ".local/bin/{v}"},
    {"also": ["/etc/passwd"]}, {"also": [".local/../../etc"]}, {"also": [".config"]},
    {"env": {"PATH": "/tmp"}}, {"env": {"LD_PRELOAD": "/tmp/x.so"}}, {"env": {"HOME": "/root"}},
    {"env": {"X_DIR": "{home}/../other"}}, {"env": {"X_DIR": "$(id)"}},
    {"pin": ["VERSION", "{v}; id"]}, {"pin": ["PATH", "{v}"]}, {"pin": ["VERSION"]},
    {"fresh": ".local/share/x/versions"}, {"fresh": "/opt/x/{v}"},
)


class Controller(unittest.TestCase):
    def setUp(self):
        self.was = (agentcode.nodes, agentcode.node_sessions, agentcode.tmux_base,
                    toolchains.agentcode, json.dumps(agentcode._latest))
        self.addCleanup(self.restore)
        agentcode._latest.clear()
        agentcode._latest["codex"] = {"version": "0.163.0", "at": 1, "error": "", "checking": False}

    def restore(self):
        agentcode.nodes, agentcode.node_sessions, agentcode.tmux_base, toolchains.agentcode, latest = self.was
        agentcode._latest.clear()
        agentcode._latest.update(json.loads(latest))

    def use(self, n):
        agentcode.nodes = Nodes(n)
        agentcode.node_sessions = lambda: []
        agentcode.tmux_base = lambda s: s
        return agentcode.nodes

    def test_every_agent_the_library_installs_is_tracked_claude_first(self):
        self.assertEqual([a.id for a in agentcode.tracked()], ["claude", "codex", "copilot", "grok", "open"])

    def test_the_version_is_read_out_of_what_each_prints(self):
        n = node(codex="codex-cli 0.163.0", copilot="GitHub Copilot CLI 1.0.102.")
        self.assertEqual(agentcode.installed(n, "codex"), "0.163.0")
        self.assertEqual(agentcode.installed(n, "copilot"), "1.0.102")

    def test_a_node_behind_has_a_row_offering_the_update(self):
        self.use(node())
        r = agentcode.row(node(), "codex")
        self.assertEqual((r["name"], r["label"], r["installed"], r["latest"], r["state"]),
                         ("codex-cli", "Codex CLI", "0.160.0", "0.163.0", "update"))
        self.assertEqual(agentcode.row(node(), "copilot")["state"], "absent")

    def test_a_row_says_what_its_recipe_is_held_to_and_what_an_install_brings(self):
        # The word and the downloads are the recipe's own (packformat.held,
        # downloads_said). A recipe whose program is its download pins a
        # version: that is what an install brings, so that is what a node
        # is behind of and what the job asks for, whatever the vendor's
        # newest is; an installer that keeps the network brings the newest.
        ns = self.use(node(codex="codex-cli 0.170.0"))
        agentcode._latest["codex"]["version"] = "0.171.0"
        with mock.patch.object(agentcode, "recipe", lambda aid, ask=True: (PLACED, "release")):
            r = agentcode.row(node(codex="codex-cli 0.170.0"), "codex")
            self.assertEqual((r["held"]["word"], r["pinned"], r["latest"], r["vendor_latest"], r["state"]),
                             ("pinned", "0.170.0", "0.170.0", "0.171.0", "current"))
            self.assertEqual([(d["to"], d["platform"], d["held"], d["url"]) for d in r["downloads"]],
                             [("dl/codex.tar.gz", "linux/amd64", "sha256", "https://x.example/0.170.0/codex-x64.tar.gz"),
                              ("dl/codex.tar.gz", "linux/arm64", "sha256", "https://x.example/0.170.0/codex-arm64.tar.gz")])
            self.assertEqual((agentcode.pinned("codex"), agentcode.offered("codex")), ("0.170.0", "0.170.0"))
            self.assertFalse(agentcode.behind(node(codex="codex-cli 0.170.0"), "codex"))
            self.assertTrue(agentcode.behind(node(codex="codex-cli 0.169.0"), "codex"))
            self.assertTrue(agentcode.update("user:admin", "n1", "codex")["ok"])
            self.assertEqual(ns.added[-1][1]["to"], "0.170.0")
        with mock.patch.object(agentcode, "recipe", lambda aid, ask=True: (HELD, "catalog")):
            r = agentcode.row(node(codex="codex-cli 0.170.0"), "codex")
            self.assertEqual((r["held"], r["pinned"], r["latest"], r["state"]),
                             ({"word": "installer", "why": SENTENCE}, "", "0.171.0", "update"))
            self.assertTrue(agentcode.update("user:admin", "n1", "codex")["ok"])
            self.assertEqual(ns.added[-1][1]["to"], "0.171.0")
        with mock.patch.object(agentcode, "recipe", lambda aid, ask=True: (OLD["codex-update"], "release")):
            r = agentcode.row(node(), "codex")
            self.assertEqual((r["held"]["word"], r["downloads"], r["pinned"]), ("open", [], ""))

    def test_no_session_account_no_row(self):
        self.use(node(up=False))
        self.assertIsNone(agentcode.row(node(up=False), "codex"))

    def test_the_latest_is_the_registry_s_version(self):
        with tempfile.NamedTemporaryFile("w", suffix=".json", delete=False) as f:
            json.dump({"name": "@openai/codex", "version": "0.170.1"}, f)
        self.addCleanup(os.unlink, f.name)
        with mock.patch.dict(os.environ, {"BB_CODEX_LATEST_URL": "file://" + f.name}):
            self.assertEqual(agentcode.check("codex")["version"], "0.170.1")

    def test_an_install_queues_the_table_s_job_for_the_latest(self):
        ns = self.use(node())
        r = agentcode.update("user:admin", "n1", "codex")
        self.assertTrue(r["ok"])
        # ...with how it is installed, the table's own where no catalog says otherwise (R169 step 13).
        self.assertEqual(ns.added, [("codex-update", {"timeout": 900, "to": "0.163.0", "ended": [],
                                                      "recipe": agents.get("codex").install, "recipe_from": "release"})])

    def catalog(self, recipe, error="", says=None):
        """A catalog whose signed index pins codex's pack at one commit and
        says its recipe's rev (`says`, the recipe's own unless given), and
        whose pack there carries `recipe`; the fetches are counted."""
        was = (agentcode.catalog_entry, agentcode.fetch_pack, dict(agentcode._recipes))
        self.addCleanup(lambda: (setattr(agentcode, "catalog_entry", was[0]), setattr(agentcode, "fetch_pack", was[1]),
                                 agentcode._recipes.clear(), agentcode._recipes.update(was[2])))
        agentcode._recipes.clear()
        asked = []
        rev = says if says is not None else (recipe or {}).get("rev")
        agentcode.catalog_entry = lambda name: {"name": name, "url": "https://example.test/catalog", "commit": "c" * 40,
                                                "sha256": "5" * 64, "path": "packs/agents/" + name,
                                                **({"install_rev": rev} if rev else {})} if name == "codex" else None

        def fetch(url, commit, shipped, sha256, path, official=False):
            # The pin is the signed index's official entry, and the fetch
            # is told so: the manifest's own word would not be taken.
            self.assertTrue(official and sha256)
            asked.append((url, commit, sha256, path))
            return {"error": error} if error else {"manifest": {"agent": {"install": recipe}}}
        agentcode.fetch_pack = fetch
        return asked

    def test_a_newer_recipe_in_the_catalog_is_the_one_sent(self):
        # The point of it: an installer that changed upstream is answered
        # by the catalog, with no release of AerieOS.
        theirs = agents.get("codex").install | {"rev": 3, "bin": ".codex/bin/codex", "also": [".local/bin/codex"]}
        asked = self.catalog(theirs)
        ns = self.use(node())
        agentcode.update("user:admin", "n1", "codex")
        agentcode.remove("user:admin", "n1", "codex")
        self.assertEqual([(t, sp["recipe"], sp["recipe_from"]) for t, sp in ns.added],
                         [("codex-update", theirs, "catalog")] * 2)
        # Fetched at the commit the index pins with its sha256, once.
        self.assertEqual(asked, [("https://example.test/catalog", "c" * 40, "5" * 64, "packs/agents/codex")])
        # Another agent, which that catalog does not pin, keeps the table's.
        self.assertEqual(agentcode.recipe("grok"), (agents.get("grok").install, "release"))

    def test_the_catalog_s_pack_is_read_at_its_pin_as_any_pack_is(self):
        # Through the real fetch: a repository holding the pack as the
        # export writes it, with a newer recipe; the commit and the folder's
        # sha256 are the index's, and a folder that differs is refused.
        import hashlib  # noqa: PLC0415
        import shutil  # noqa: PLC0415
        import subprocess  # noqa: PLC0415
        import toolpacks  # noqa: PLC0415
        root = os.path.dirname(os.path.dirname(os.path.dirname(HERE)))
        with open(os.path.join(root, "packs", "agents", "open", "bbtool.json"), encoding="utf-8") as f:
            m = json.load(f)
        self.assertEqual(m["agent"]["install"], agents.get("open").install, "the bundled pack carries the table's recipe")
        m["agent"]["install"] = m["agent"]["install"] | {"rev": 7, "bin": ".opencode/v2/opencode"}
        tmp = tempfile.mkdtemp()
        self.addCleanup(shutil.rmtree, tmp, True)
        folder = os.path.join(tmp, "packs", "agents", "open")
        os.makedirs(folder)
        with open(os.path.join(folder, "bbtool.json"), "w", encoding="utf-8") as f:
            json.dump(m, f)

        def git(*a):
            return subprocess.run(["git", "-C", tmp, "-c", "user.name=t", "-c", "user.email=t@example.test", *a],
                                  capture_output=True, check=True).stdout
        git("init", "-q")
        git("add", "-A")
        git("commit", "-qm", "pack")
        entry = {"name": "open", "url": "file://" + tmp, "commit": git("rev-parse", "HEAD").decode().strip(), "path": "packs/agents/open", "install_rev": 7,
                 "sha256": hashlib.sha256(git("archive", "--format=tar", "HEAD", "packs/agents/open")).hexdigest()}
        was = (agentcode.catalog_entry, agentcode.fetch_pack, dict(agentcode._recipes))
        self.addCleanup(lambda: (setattr(agentcode, "catalog_entry", was[0]), setattr(agentcode, "fetch_pack", was[1]),
                                 agentcode._recipes.clear(), agentcode._recipes.update(was[2])))
        agentcode._recipes.clear()
        agentcode.fetch_pack = toolpacks.fetch
        with mock.patch.dict(os.environ, {"BB_TOOLPACKS_FILE_URLS": "1"}):
            agentcode.catalog_entry = lambda name: entry if name == "open" else None
            got, where = agentcode.recipe("open")
            self.assertEqual((where, got["rev"], got["bin"]), ("catalog", 7, ".opencode/v2/opencode"))
            # The same pin looked at as a pack to add is no shipped agent's:
            # official is this caller's word, from the signed index, and a
            # manifest that says it of itself is refused.
            looked = toolpacks.fetch(entry["url"], entry["commit"], (), entry["sha256"], entry["path"])
            self.assertIn("tier official is said by AerieOS of the packs it ships", looked.get("error", ""))
            agentcode._recipes.clear()
            agentcode.catalog_entry = lambda name: dict(entry, sha256="0" * 64) if name == "open" else None
            self.assertEqual(agentcode.recipe("open"), (agents.get("open").install, "release"))

    def test_a_catalog_no_newer_than_the_release_changes_nothing(self):
        # A catalog left behind never undoes what a release fixed, and is
        # not even fetched: the index says its rev, so a press waits for
        # nothing (a press that waited ended no session: the node had
        # stopped counting as live by the time it looked).
        asked = self.catalog(agents.get("codex").install | {"bin": ".codex/old/codex"})
        self.assertEqual(agentcode.recipe("codex"), (agents.get("codex").install, "release"))
        agentcode.warm()
        self.assertEqual(asked, [])
        # An index from before it said a rev is the same: nothing newer is known.
        asked = self.catalog(agents.get("codex").install | {"rev": 9}, says=0)
        self.assertEqual(agentcode.recipe("codex"), (agents.get("codex").install, "release"))
        self.assertEqual(asked, [])
        # ...and an index that says more than its pack holds changes nothing.
        self.catalog(agents.get("codex").install, says=5)
        self.assertEqual(agentcode.recipe("codex"), (agents.get("codex").install, "release"))

    def test_a_pack_that_cannot_be_read_leaves_the_table_s(self):
        asked = self.catalog(None, error="its archive's sha256 differs, so it is refused", says=3)
        self.assertEqual(agentcode.recipe("codex"), (agents.get("codex").install, "release"))
        self.assertEqual(agentcode.recipe("codex"), (agents.get("codex").install, "release"))
        self.assertEqual(len(asked), 1)          # asked again only after RECIPE_MISS_S

    def test_the_library_s_read_fetches_a_newer_recipe_ahead_of_the_press(self):
        theirs = agents.get("codex").install | {"rev": 3, "bin": ".codex/bin/codex"}
        asked = self.catalog(theirs)
        agentcode.warm()
        for _ in range(200):
            if not agentcode._warming.is_set() and asked:
                break
            time.sleep(0.01)
        self.assertEqual(len(asked), 1)
        self.assertEqual(agentcode.recipe("codex"), (theirs, "catalog"))
        agentcode.warm()
        self.assertEqual(len(asked), 1, "read once per commit")

    def test_a_recipe_is_held_to_its_shape(self):
        for a in agents.TABLE:
            self.assertEqual(agents.install_checked(a.install), (a.install, ""), a.id)
        for bad in BAD_RECIPES:
            self.assertTrue(agents.install_checked(HELD | bad)[1], bad)
        self.assertTrue(agents.install_checked(HELD | {"rev": True})[1])
        self.assertEqual(agents.install_checked(HELD)[1], "")
        # A vendor's installer handed to a shell as it arrives is no recipe,
        # however plain its one line is: refused as a shape, alone or beside
        # a held recipe's parts.
        for piped in (GOOD, OLD["codex-update"], HELD | {"script": GOOD["script"]}):
            got, why = agents.install_checked(piped)
            self.assertEqual((got, why[:33]), (None, "agent.install.script is no recipe"), piped)

    def test_a_newer_recipe_held_to_less_than_the_table_s_is_refused(self):
        # A higher rev is the catalog's word alone and never buys a weaker
        # hold (packformat.replaces_refused): grok's recipe is pinned, so
        # an installer that keeps the network does not replace it; codex's
        # is an installer's, which a pinned one and another installer's do.
        said = []
        was = (agentcode.catalog_entry, agentcode.fetch_pack, dict(agentcode._recipes), agentcode.audit)
        self.addCleanup(lambda: (setattr(agentcode, "catalog_entry", was[0]), setattr(agentcode, "fetch_pack", was[1]),
                                 agentcode._recipes.clear(), agentcode._recipes.update(was[2]), setattr(agentcode, "audit", was[3])))
        agentcode.audit = lambda who, action, target, params: said.append((who, action, target))
        asked = []

        def offer(recipe):
            agentcode._recipes.clear()
            said.clear()
            asked.clear()
            agentcode.catalog_entry = lambda name: {"name": name, "url": "https://example.test/catalog", "commit": "c" * 40, "sha256": "5" * 64,
                                                    "path": "packs/agents/" + name, "install_rev": recipe["rev"]}
            agentcode.fetch_pack = lambda *a, **kw: asked.append(a) or {"manifest": {"agent": {"install": recipe}}}
        grok, codex = agents.get("grok").install, agents.get("codex").install
        self.assertEqual((packformat.agent_held(grok)["word"], packformat.agent_held(codex)["word"]), ("pinned", "installer"))
        # Pinned, and a pinned one newer: taken, and said once in the audit.
        offer(grok | {"rev": grok["rev"] + 2})
        self.assertEqual(agentcode.recipe("grok")[1], "catalog")
        self.assertEqual(agentcode.recipe("grok")[1], "catalog")
        self.assertEqual(said, [("catalog", "agent-recipe-taken", f"grok rev {grok['rev']} to {grok['rev'] + 2}")])
        # Pinned, and an installer that keeps the network newer: refused, the table's stays, read once.
        with contextlib.redirect_stdout(io.StringIO()) as out:
            offer(HELD | {"rev": grok["rev"] + 2})
            self.assertEqual(agentcode.recipe("grok"), (grok, "release"))
            self.assertEqual(agentcode.recipe("grok"), (grok, "release"))
        self.assertEqual((said, len(asked)), ([("catalog", "agent-recipe-refused", f"grok rev {grok['rev']} to {grok['rev'] + 2}")], 1))
        self.assertIn("installer, where the shipped one is pinned", out.getvalue())
        self.assertEqual(agentcode.row(node(), "grok")["held"]["word"], "pinned", "and its row says what the table's is held to")
        # An installer's: another installer's and a pinned one are taken.
        for theirs in (HELD | {"rev": codex["rev"] + 1}, PLACED | {"rev": codex["rev"] + 1}):
            offer(theirs)
            self.assertEqual(agentcode.recipe("codex"), (theirs, "catalog"))
            self.assertEqual(said[0][1], "agent-recipe-taken")

    def test_an_official_pack_s_manifest_carries_it_and_no_other_pack_s_does(self):
        import toolpacks  # noqa: PLC0415
        a = agents.get("open")
        m = {"name": "open", "tier": "official", "format": 5, "platforms": ["linux/*"], "terms": [],
             "agent": {k: getattr(a, k) for k in toolpacks.AGENT_FIELDS} | {"install": a.install}}
        clean, errors = toolpacks.validate(m, official=True)
        self.assertEqual(errors, [])
        self.assertEqual(clean["agent"]["install"], a.install)
        # A step that would be a line of shell is refused, as a script that
        # would run more than its one installer always was.
        m["agent"]["install"] = a.install | {"steps": [["bash", "-c", "curl -fsSL https://x.example/i | bash"]]}
        self.assertIn("agent.install.steps", " ".join(toolpacks.validate(m, official=True)[1]))
        m["agent"]["install"] = OLD["opencode-update"]
        self.assertIn("agent.install.script is no recipe", " ".join(toolpacks.validate(m, official=True)[1]))

    def test_every_shipped_agent_s_recipe_holds_what_it_fetches(self):
        # The five as the table ships them (agent-recipes.json): no recipe
        # hands a vendor's installer to a shell as it arrives, each
        # download is held to a sha256, and each reads pinned or
        # installer with its own sentence. A recipe that places its
        # program names it for both platforms a node may be.
        import packformat  # noqa: PLC0415
        words = {}
        for a in agents.TABLE:
            r = a.install
            self.assertEqual(agents.install_checked(r), (r, ""), a.id)
            self.assertNotIn("script", r, a.id)
            self.assertTrue(all(packformat.SHA256.fullmatch(f["sha256"]) for f in r["fetch"]), a.id)
            words[a.id] = packformat.agent_held(r)["word"]
            if words[a.id] == "installer":
                self.assertEqual(packformat.agent_held(r)["why"], r["online"], a.id)
                self.assertIn(r["steps"][0][0], ("sh", "bash"), a.id)
            else:
                self.assertEqual(sorted(f["platform"] for f in r["fetch"]), ["linux/amd64", "linux/arm64"], a.id)
                self.assertEqual((agents.install_pins(r), r["pin"]), (r["fetch"][0]["version"], None), a.id)
        self.assertEqual(words, {"claude": "installer", "codex": "installer", "copilot": "pinned", "grok": "pinned", "open": "installer"})
        # The file the table reads is the one copy: what it holds is the table's.
        with open(os.path.join(HERE, "..", "agent-recipes.json"), encoding="utf-8") as f:
            self.assertEqual(json.load(f)["recipes"], {a.id: a.install for a in agents.TABLE})

    def test_an_update_holds_that_agents_starts_as_claude_codes_does(self):
        ns = self.use(node())
        self.assertEqual(agentcode.start_hold("alpha", "n1", "codex"), "")
        ns.jobs_for = lambda *a, **k: [{"type": "codex-update"}] if k.get("type") == "codex-update" else []
        self.assertIn("is updating", agentcode.start_hold("alpha", "n1", "codex"))
        self.assertEqual(agentcode.start_hold("alpha", "n1", "copilot"), "")

    def test_a_removal_needs_it_installed(self):
        self.use(node(codex=""))
        self.assertIn("not installed", agentcode.remove("user:admin", "n1", "codex")["error"])

    def test_claude_code_is_one_of_them_in_its_own_wording(self):
        ns = self.use(node())
        agentcode._latest["claude"] = {"version": "2.1.306", "at": 1, "error": "", "checking": False}
        self.assertTrue(agentcode.update("user:admin", "n1", "claude")["ok"])
        self.assertEqual(ns.added, [("claude-update", {"timeout": 900, "to": "2.1.306", "ended": [],
                                                       "recipe": agents.get("claude").install, "recipe_from": "release"})])
        # Its own wording of a hold and of a refusal, beside the common one.
        ns.jobs_for = lambda *a, **k: [{"type": k.get("type")}]
        self.assertEqual(agentcode.start_hold("alpha", "n1", "claude"),
                         "Claude Code is updating on box: press Claude on alpha again when its row comes back")
        self.assertEqual(agentcode.start_hold("alpha", "n1", "codex"),
                         "Codex CLI is updating on box: start ChatGPT on alpha again when its row on the Installed page comes back")
        self.use(node(up=False))
        self.assertEqual(agentcode.update("user:admin", "n1", "claude")["error"],
                         "box runs no session account, so there is no Claude Code there to update")
        self.assertEqual(agentcode.update("user:admin", "n1", "codex")["error"],
                         "box runs no session account, so there is nowhere for Codex CLI to go")

    def test_the_latest_of_claude_code_is_its_installer_s_plain_file(self):
        with mock.patch.dict(os.environ):
            os.environ.pop("BB_CLAUDE_LATEST_URL", None)
            self.assertEqual(agentcode.latest_url(agents.get("claude")), "https://downloads.claude.ai/claude-code-releases/latest")
        with tempfile.NamedTemporaryFile("w", suffix=".txt", delete=False) as f:
            f.write("2.1.306\n")
        self.addCleanup(os.unlink, f.name)
        with mock.patch.dict(os.environ, {"BB_CLAUDE_LATEST_URL": "file://" + f.name}):
            self.assertEqual(agentcode.check("claude")["version"], "2.1.306")
        # What could not be asked is named by where each agent's answer comes from.
        with mock.patch.dict(os.environ, {"BB_CLAUDE_LATEST_URL": "file:///nonexistent", "BB_CODEX_LATEST_URL": "file:///nonexistent"}):
            self.assertTrue(agentcode.check("claude")["error"].startswith("could not reach the download service: "))
            self.assertTrue(agentcode.check("codex")["error"].startswith("could not reach the registry: "))

    def test_the_census_catches_up_when_the_job_ends(self):
        ns = self.use(node())
        ns.log = "installing\nCodex CLI 0.163.0 is what a session here runs now\n"
        agentcode.update_done({"id": "j_1", "type": "codex-update", "node": "n1", "spec": {}}, "succeeded")
        self.assertEqual(ns.reported, [("n1", "session", "codex", "0.163.0")])

    def test_the_toolchains_page_draws_each_with_claude_s_first(self):
        self.use(node())
        toolchains.agentcode = agentcode
        names = [r["name"] for r in agentcode.rows(node())]
        self.assertEqual(names, [a.tool for a in agents.installable()])
        self.assertEqual(names[0], "claude-code")


# The older form of a recipe, as a controller from before pack format 5
# hands it: a node still runs it as it was.
OLD = {"codex-update": {"rev": 1, "script": "curl -fsSL https://x.example/codex/install.sh | sh", "pin": ["CODEX_RELEASE", "{v}"],
                        "env": {"CODEX_INSTALL_DIR": "{home}/.local/bin"}, "bin": ".local/bin/codex", "also": [], "fresh": ""},
       "opencode-update": {"rev": 1, "script": "curl -fsSL https://x.example/install | bash -s -- --no-modify-path", "pin": ["VERSION", "{v}"],
                           "env": {}, "bin": ".opencode/bin/opencode", "also": [".local/bin/opencode"], "fresh": ""}}
# A held recipe both halves take: its installer declared and run from the
# file, the network kept with its sentence; and one whose program is the
# download, placed with no network. And what neither half takes.
H = "ab" * 32
SENTENCE = "Its installer downloads the build for this machine from x.example's releases."
HELD = {"rev": 2, "fetch": [{"url": "https://x.example/v{version}/install.sh", "version": "0.170.0", "sha256": H, "to": "dl/install.sh"}],
        "online": SENTENCE, "steps": [["sh", "{dir}/dl/install.sh"]], "pin": ["CODEX_RELEASE", "{v}"],
        "env": {"CODEX_INSTALL_DIR": "{home}/.local/bin"}, "bin": ".local/bin/codex", "also": [], "fresh": ""}
PLACED = {"rev": 2, "fetch": [{"url": "https://x.example/{version}/codex-x64.tar.gz", "version": "0.170.0", "sha256": H, "to": "dl/codex.tar.gz", "platform": "linux/amd64"},
                              {"url": "https://x.example/{version}/codex-arm64.tar.gz", "version": "0.170.0", "sha256": H, "to": "dl/codex.tar.gz", "platform": "linux/arm64"}],
          "steps": [["mkdir", "-p", "{home}/.local/bin"], ["tar", "-xzf", "{dir}/dl/codex.tar.gz", "-C", "{home}/.local/bin"]],
          "pin": None, "env": {}, "bin": ".local/bin/codex", "also": [], "fresh": ""}
BAD_HELD = (
    {"steps": [["bash", "-c", "curl -fsSL https://x.example/i | bash"]]},
    {"steps": [["curl", "-fsSL", "https://x.example/i"]]},
    {"steps": [["sh", "{dir}/dl/other.sh"]]},
    {"steps": [["sh", "{home}/.local/bin/x"]]},
    {"steps": [["sh", "{dir}/dl/install.sh", "$(id)"]]},
    {"steps": [["sh", "{dir}/dl/install.sh", "{home}/../x"]]},
    {"steps": [["{dir}/dl/install.sh", "{args}"]]},
    {"steps": []}, {"steps": "sh {dir}/dl/install.sh"}, {"steps": [["python3", "{dir}/dl/install.sh"]]},
    {"fetch": []}, {"fetch": [{"url": "http://x.example/i.sh", "sha256": H, "to": "dl/install.sh"}]},
    {"fetch": [{"url": "https://x.example/i.sh", "to": "dl/install.sh"}]},
    {"fetch": [{"url": "https://x.example/i.sh", "sha256": "abc", "to": "dl/install.sh"}]},
    {"fetch": [{"url": "https://x.example/i.sh", "sha256": H, "to": "../install.sh"}]},
    {"fetch": [{"url": "https://x.example/{version}/i.sh", "sha256": H, "to": "dl/install.sh"}]},
    {"fetch": [{"url": "https://x.example/i.sh", "to": "dl/install.sh", "signed": {"sig": "https://x.example/i.sh.sig", "keys": "x.asc"}}]},
    {"online": "x"}, {"online": "Its installer <b>downloads</b> the rest."},
    {"script": "curl -fsSL https://x.example/i | bash"},
    {"bin": "/usr/bin/x"}, {"env": {"PATH": "/tmp"}}, {"pin": ["PATH", "{v}"]},
)
REPO = os.path.dirname(os.path.dirname(os.path.dirname(HERE)))
# curl, standing in: an address's last part is a file of the test's own.
FAKE_CURL = '''#!/bin/sh
out=""; url=""
while [ "$#" -gt 0 ]; do
    case "$1" in
        -o) out="$2"; shift ;;
        --proto|--proto-redir|--connect-timeout|--speed-limit|--speed-time|--retry|--retry-delay|--max-time) shift ;;
        -*) ;;
        *) url="$1" ;;
    esac
    shift
done
f="$FAKE_WEB/${url##*/}"
[ -f "$f" ] || exit 22
if [ -n "$out" ]; then cp "$f" "$out"; else cat "$f"; fi
'''


class NodeAgent(unittest.TestCase):
    """The node's half: AGENT_INSTALLS's row for the job, the recipe the
    controller handed over run with the version pinned, the binary's
    version read back."""

    def setUp(self):
        self.mod = agentpkg.load("agentinstall")
        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        self.home = os.path.join(self.tmp.name, "home")
        os.makedirs(self.home)
        # The node's own agents folder is read first: on a node that carries
        # a real Codex the census found that one and not the stub (B251).
        self.mod.AGENTS_DIR = os.path.join(self.tmp.name, "agents")
        self.stub = os.path.join(self.tmp.name, "installer.sh")
        with open(self.stub, "w") as f:
            f.write('mkdir -p "$CODEX_INSTALL_DIR"\n'
                    'printf "#!/bin/sh\\necho codex-cli ${CODEX_RELEASE:-0.0.0}\\n" > "$CODEX_INSTALL_DIR/codex"\n'
                    'chmod +x "$CODEX_INSTALL_DIR/codex"\necho "stub installed $CODEX_RELEASE"\n')
        # What a vendor serves, for a run with no stub: the installer above
        # under the name a recipe's address ends in, fetched by a curl that
        # reads this folder and asks no network.
        self.web = os.path.join(self.tmp.name, "web")
        self.bin = os.path.join(self.tmp.name, "bin")
        os.makedirs(self.web)
        os.makedirs(self.bin)
        with open(os.path.join(self.bin, "curl"), "w") as f:
            f.write(FAKE_CURL)
        os.chmod(os.path.join(self.bin, "curl"), 0o755)
        with open(self.stub) as f, open(os.path.join(self.web, "install.sh"), "w") as w:
            w.write(f.read())
        # bb-netcut, standing in: it writes down whom it was asked to run
        # as and the environment it was started with, makes no namespace,
        # and starts the command with a plain environment as the real one
        # does. And the kernel's list of a process's interfaces, as a run
        # inside a cut reads it and as one outside does.
        self.netcut = os.path.join(self.bin, "bb-netcut")
        self.cut_log = os.path.join(self.tmp.name, "netcut.log")
        with open(self.netcut, "w") as f:
            f.write(f'#!/bin/sh\nenv > "{self.cut_log}.env"\necho "$SUDO_UID $*" >> "{self.cut_log}"\nexec env -i PATH=/usr/bin:/bin "$@"\n')
        os.chmod(self.netcut, 0o755)
        head = "Inter-|   Receive  |  Transmit\n face |bytes    packets|bytes    packets\n"
        self.no_net, self.a_net = (os.path.join(self.tmp.name, n) for n in ("net-none", "net-eth"))
        with open(self.no_net, "w") as f:
            f.write(head + "    lo:       0       0    0    0\n")
        with open(self.a_net, "w") as f:
            f.write(head + "    lo:       0       0    0    0\n  eth0:   91234     812    0    0\n")

    def placed(self):
        """A recipe whose program is its download, with what its vendor
        serves for it: a tarball a platform, holding the program."""
        import tarfile  # noqa: PLC0415
        prog = os.path.join(self.tmp.name, "codex")
        with open(prog, "w") as f:
            f.write("#!/bin/sh\necho codex-cli 0.170.0\n")
        os.chmod(prog, 0o755)
        for name in ("codex-x64.tar.gz", "codex-arm64.tar.gz"):
            with tarfile.open(os.path.join(self.web, name), "w:gz") as tar:
                tar.add(prog, arcname="codex")
        return PLACED | {"fetch": [self.held(PLACED | {"fetch": [f]}, f["url"].rsplit("/", 1)[-1])["fetch"][0] for f in PLACED["fetch"]]}

    def held(self, recipe=HELD, name="install.sh"):
        """`recipe` with each download's sha256 that of the file the web
        folder serves under `name`."""
        with open(os.path.join(self.web, name), "rb") as f:
            digest = hashlib.sha256(f.read()).hexdigest()
        return recipe | {"fetch": [f | {"sha256": digest} for f in recipe["fetch"]]}

    def left(self):
        """What is under the account's home now."""
        return sorted(os.path.relpath(os.path.join(d, x), self.home) for d, dirs, files in os.walk(self.home) for x in dirs + files)

    def run_job(self, spec, type_="codex-update", stub=True, root=False, more=None):
        # The recipe a controller hands over with every job: the older form
        # unless the test names another, or none with None. With `root` the
        # agent is root, as on a managed node: it drops to the session
        # account (this test's own, which is all a test may become) and
        # cuts the network through its helper, stood in for (self.netcut).
        # `more` is added to what an install's environment starts from.
        spec = dict(spec)
        if "recipe" not in spec and type_ in OLD:
            spec["recipe"] = OLD[type_]
        elif spec.get("recipe", 0) is None:
            del spec["recipe"]
        said = []
        job = type("J", (), {})()
        job.job = {"type": type_}
        job.say = said.append
        job.pending = False
        job.proc = None
        job.flush = lambda: None
        job.cancel = lambda: None
        fake = type("A", (), {})()
        fake.state = {}
        fake.session_account = lambda: "builder"
        fake.as_user = lambda env, who: {"user": os.getuid(), "group": os.getgid()} if root else {}
        fake.held_cut = lambda who: self.netcut if root and who else self.mod.Agent.held_cut(fake, who)
        fake.held_cut_env = self.mod.Agent.held_cut_env
        fake.session_renew = lambda: None
        fake.hello_again = lambda why: None
        # The one install path every agent's job goes through (R95 step 18).
        fake.agent_install = lambda job, spec, how: self.mod.Agent.agent_install(fake, job, spec, how)
        fake.agent_recipe = lambda job, spec, row: self.mod.Agent.agent_recipe(fake, job, spec, row)
        # A held recipe is run by this checkout's held-run.sh, as a node
        # runs its bundle's.
        fake.held_install = lambda job, how, who, home: self.mod.Agent.held_install(fake, job, how, who, home)
        fake.bundle = lambda job, who: REPO
        env = {"HOME": self.home} | ({"BUILDERBOT_CODEX_INSTALLER": self.stub} if stub else {})
        with mock.patch.dict(os.environ, env), \
                mock.patch("os.path.expanduser", return_value=self.home), \
                mock.patch("os.geteuid", return_value=0 if root else 1000):
            if not stub:
                os.environ.pop("BUILDERBOT_CODEX_INSTALLER", None)
            for m in self.mod._mods:
                if "sdk_env" in vars(m):
                    vars(m)["sdk_env"] = lambda state: {"HOME": self.home, "PATH": f"{self.bin}:/usr/bin:/bin", "FAKE_WEB": self.web, **(more or {})}
                # Root's own copy of the bundle is this machine's, if it has one: the checkout's is what runs here.
                if "ROOT_BUNDLE_DIR" in vars(m):
                    vars(m)["ROOT_BUNDLE_DIR"] = os.path.join(self.tmp.name, "no-root-bundle")
                # A root agent probes a program as the account that owns
                # it, which only root can become: here it is run as it is.
                if root and "_probe" in vars(m):
                    vars(m)["_probe"] = lambda argv, timeout=20, **kw: (subprocess.run(argv, capture_output=True, text=True, timeout=timeout,
                                                                                       check=False).stdout.strip(), "")
            got = self.mod.Agent.agent_update(fake, job, spec)
        return got, "".join(said)

    def test_the_installer_runs_with_the_version_and_the_binary_is_read_back(self):
        got, log = self.run_job({"to": "0.163.0"})
        self.assertEqual(got, ("succeeded", 0), log)
        self.assertIn("stub installed 0.163.0", log)
        self.assertIn("Codex CLI 0.163.0 is what a session here runs now", log)

    def test_a_held_recipe_is_fetched_held_and_then_run_from_the_file(self):
        # What the recipe declares is fetched and held to its sha256 before
        # anything runs, and its step runs the file that was held. Its
        # installer keeps the network, and the job says the recipe's sentence.
        got, log = self.run_job({"to": "0.171.0", "recipe": self.held()}, stub=False)
        self.assertEqual(got, ("succeeded", 0), log)
        self.assertIn("fetching dl/install.sh from https://x.example/v0.170.0/install.sh", log)
        self.assertIn("verified: sha256 matches what Codex CLI declares for dl/install.sh", log)
        self.assertIn(f"Codex CLI keeps the network for its steps, as its entry says: {SENTENCE}", log)
        self.assertLess(log.index("verified: sha256"), log.index("stub installed"), "held before it ran")
        # The version asked for is still handed to an installer that takes one.
        self.assertIn("stub installed 0.171.0", log)
        self.assertIn("Codex CLI 0.171.0 is what a session here runs now", log)
        self.assertNotIn("nothing holds what this fetches", log)
        # Nothing of the fetch is left: the program, and the places it made.
        self.assertEqual(self.left(), [".local", ".local/bin", ".local/bin/codex"])

    def test_a_file_that_is_not_the_pinned_bytes_installs_nothing(self):
        # The vendor's file is one byte off the recipe's digest: nothing of
        # it runs, the job says both digests and that the vendor changed
        # its installer, and the home is as it was.
        good = self.held()
        want = good["fetch"][0]["sha256"]
        off = ("0" if want[0] != "0" else "1") + want[1:]
        got, log = self.run_job({"to": "0.171.0", "recipe": good | {"fetch": [good["fetch"][0] | {"sha256": off}]}}, stub=False)
        self.assertEqual(got, ("failed", self.mod.HELD_CHANGED), log)
        self.assertIn(f"answered a file whose sha256 is {want}, and its manifest declares {off}", log)
        self.assertIn("refused: Codex CLI's vendor changed its installer since AerieOS pinned it", log)
        self.assertIn("Nothing was run and nothing is installed", log)
        self.assertNotIn("stub installed", log)
        self.assertEqual(self.left(), [])
        # ...and one that cannot be fetched at all is said as that.
        os.unlink(os.path.join(self.web, "install.sh"))
        got, log = self.run_job({"to": "0.171.0", "recipe": good}, stub=False)
        self.assertEqual(got, ("failed", self.mod.HELD_UNFETCHED), log)
        self.assertIn("what its recipe declares could not be fetched", log)
        self.assertEqual(self.left(), [])

    def test_a_recipe_that_places_its_program_runs_with_no_network_and_installs_the_pinned_version(self):
        # The program itself is the download, for this machine's platform
        # alone, and the steps only put it in place: no sentence, so they
        # are cut from the network where this machine can cut, and the
        # version is the one the recipe pins, whatever the controller named.
        got, log = self.run_job({"to": "0.171.0", "recipe": self.placed()}, stub=False)
        self.assertEqual(got, ("succeeded", 0), log)
        self.assertIn("(0.170.0 is the version its recipe pins)", log)
        self.assertEqual(log.count("fetching dl/codex.tar.gz"), 1, "the one for this machine")
        self.assertIn("leaving out dl/codex.tar.gz: it is for linux/", log)
        self.assertTrue("its steps run with no network" in log or "this node cannot cut the network" in log, log)
        self.assertNotIn("keeps the network", log)
        self.assertIn("Codex CLI 0.170.0 is what a session here runs now", log)

    def test_a_root_agent_cuts_the_network_itself_for_the_session_account(self):
        # The session account has no rule for bb-netcut, and where it can
        # make no namespace it cut nothing: a recipe that reads pinned ran
        # its steps with the network. The agent is root, so it makes the
        # cut: what the recipe declares is fetched and held as the account
        # with the network, and the steps are then started through the
        # helper, as the account this node's sessions run as.
        got, log = self.run_job({"to": "0.171.0", "recipe": self.placed()}, stub=False, root=True, more={"BUILDERBOT_NET_DEV": self.no_net})
        self.assertEqual(got, ("succeeded", 0), log)
        self.assertIn("Codex CLI declares its downloads: its steps run with no network", log)
        self.assertNotIn("cannot cut the network", log)
        self.assertLess(log.index("verified: sha256"), log.index("its steps run with no network"), "held with the network, then cut")
        self.assertLess(log.index("its steps run with no network"), log.index("running mkdir -p"), "and every step behind it")
        self.assertIn("Codex CLI 0.170.0 is what a session here runs now", log)
        with open(self.cut_log) as f:
            asked = f.read().splitlines()
        self.assertEqual(len(asked), 1, "one run through the helper: the steps, never the fetch")
        self.assertTrue(asked[0].startswith(f"{os.getuid()} env "), asked[0][:80])
        self.assertIn(f" bash {REPO}/scripts/lib/held-run.sh --run {self.home}/.cache/aerie-held.", asked[0])
        # The helper is started with nothing of the install's environment
        # but whom to become: the install's own goes over as words.
        with open(self.cut_log + ".env") as f:
            started = dict(ln.split("=", 1) for ln in f.read().splitlines() if "=" in ln)
        self.assertEqual({k: v for k, v in started.items() if k not in ("PWD", "SHLVL", "_", "OLDPWD")},
                         {"PATH": "/usr/local/sbin:/usr/local/bin:/usr/sbin:/usr/bin:/sbin:/bin", "LANG": "C.UTF-8", "SUDO_UID": str(os.getuid())})
        # Nothing of the fetch is left: the program, and the places it made.
        self.assertEqual([x for x in self.left() if "aerie-held" in x], [])
        self.assertIn(".local/bin/codex", self.left())

    def test_a_root_agent_s_install_of_a_changed_file_never_reaches_the_helper(self):
        # The fetch is the first run, as the account: a file that is not
        # the pinned bytes ends there, with nothing started behind a cut
        # and nothing left.
        good = self.placed()
        off = [f | {"sha256": ("0" if f["sha256"][0] != "0" else "1") + f["sha256"][1:]} for f in good["fetch"]]
        got, log = self.run_job({"to": "0.171.0", "recipe": good | {"fetch": off}}, stub=False, root=True, more={"BUILDERBOT_NET_DEV": self.no_net})
        self.assertEqual(got, ("failed", self.mod.HELD_CHANGED), log)
        self.assertIn("refused: Codex CLI's vendor changed that file since AerieOS pinned it", log)
        self.assertFalse(os.path.exists(self.cut_log))
        self.assertEqual(self.left(), [])

    def test_nothing_a_job_says_names_the_account_the_steps_run_as(self):
        # The account is the one this node's own state names for sessions,
        # handed to the helper by the agent: a job that says another, in
        # any word, changes nothing.
        spec = {"to": "0.171.0", "recipe": self.placed(), "user": "root", "uid": 0, "account": "root", "session_user": "root", "as": "root",
                "env": {"SUDO_UID": "0"}, "SUDO_UID": "0"}
        got, log = self.run_job(spec, stub=False, root=True, more={"BUILDERBOT_NET_DEV": self.no_net})
        self.assertEqual(got, ("succeeded", 0), log)
        with open(self.cut_log) as f:
            self.assertEqual([ln.split(" ", 1)[0] for ln in f.read().splitlines()], [str(os.getuid())])
        # ...and a recipe cannot hand the helper one through its
        # environment: that is the install's, set once the helper has
        # become the account, and the helper was started with the agent's.
        got, log = self.run_job({"to": "0.171.0", "recipe": self.placed() | {"env": {"SUDO_UID": "0"}}}, stub=False, root=True,
                                more={"BUILDERBOT_NET_DEV": self.no_net})
        self.assertEqual(got, ("succeeded", 0), log)
        with open(self.cut_log + ".env") as f:
            self.assertIn(f"SUDO_UID={os.getuid()}\n", f.read())

    def test_which_helper_a_root_agent_cuts_with(self):
        # bb-netcut, where the agent is root and drops to an account that
        # is not: root's own file, which nobody else can write, or none.
        cut = self.mod.Agent.held_cut
        fake = type("A", (), {})()
        made = []
        fake.refresh_netcut_tool = lambda: made.append(1)
        fake.held_cut_env = self.mod.Agent.held_cut_env
        who = {"user": 1001, "group": 1001}
        asked = []

        def looks(uid=0, mode=0o100755):
            return mock.patch("os.lstat", return_value=type("S", (), {"st_uid": uid, "st_mode": mode})())

        def cuts(code=0):
            """The helper asked for nothing: what it was started with, and how it ended."""
            def run(argv, **kw):
                asked.append((argv, kw.get("env")))
                return type("P", (), {"returncode": code})()
            return mock.patch("subprocess.run", run)
        with mock.patch("os.geteuid", return_value=1000), looks(), cuts():
            self.assertEqual(cut(fake, who), "", "an agent that is not root cuts nothing for anybody")
        with mock.patch("os.geteuid", return_value=0):
            with looks(), cuts():
                self.assertEqual(cut(fake, who), self.mod.NETCUT_BIN)
                self.assertEqual(made, [1], "kept as root's copy of the bundle has it, as a toolchain's install keeps it")
                # Asked for nothing first, as the account, with a plain environment.
                self.assertEqual(asked, [([self.mod.NETCUT_BIN, "true"], {"PATH": "/usr/local/sbin:/usr/local/bin:/usr/sbin:/usr/bin:/sbin:/bin",
                                                                          "LANG": "C.UTF-8", "SUDO_UID": "1001"})])
                self.assertEqual((cut(fake, {}), cut(fake, {"user": 0})), ("", ""), "nobody to drop to, or root itself")
            for uid, mode in ((1001, 0o100755), (0, 0o100775), (0, 0o100757), (0, 0o100644), (0, 0o120777), (0, 0o040755)):
                with looks(uid, mode), cuts():
                    self.assertEqual(cut(fake, who), "", (uid, oct(mode)))
            self.assertEqual(len(asked), 1, "a file that is not root's own is never started")
            with mock.patch("os.lstat", side_effect=FileNotFoundError), cuts():
                self.assertEqual(cut(fake, who), "", "a node with no helper")
            # A machine that lets nobody make a namespace: the helper says so, and the install goes on as the account can.
            with looks(), cuts(71):
                self.assertEqual(cut(fake, who), "")

    def test_a_recipe_that_keeps_the_network_is_not_cut_by_a_root_agent_either(self):
        got, log = self.run_job({"to": "0.171.0", "recipe": self.held()}, stub=False, root=True, more={"BUILDERBOT_NET_DEV": self.no_net})
        self.assertEqual(got, ("succeeded", 0), log)
        self.assertIn(f"Codex CLI keeps the network for its steps, as its entry says: {SENTENCE}", log)
        self.assertNotIn("its steps run with no network", log)
        self.assertFalse(os.path.exists(self.cut_log), "the helper is not asked")

    def test_an_agent_that_is_not_root_cuts_as_the_account_can_and_says_when_it_cannot(self):
        # As before: the account makes its own namespace where the machine
        # lets it, and where it cannot (here: an unshare that refuses, and
        # no helper it may run) the steps run with the network, said.
        with open(os.path.join(self.bin, "unshare"), "w") as f:
            f.write("#!/bin/sh\nexit 1\n")
        os.chmod(os.path.join(self.bin, "unshare"), 0o755)
        got, log = self.run_job({"to": "0.171.0", "recipe": self.placed()}, stub=False,
                                more={"BUILDERBOT_NETCUT_BIN": os.path.join(self.tmp.name, "no-helper"), "BUILDERBOT_NET_DEV": self.no_net})
        self.assertEqual(got, ("succeeded", 0), log)
        self.assertIn("Codex CLI declares its downloads, but this node cannot cut the network for a step", log)
        self.assertNotIn("its steps run with no network", log)
        self.assertFalse(os.path.exists(self.cut_log))

    def test_said_to_be_cut_and_not_cut_runs_nothing(self):
        # The second run believes the cut only where it can see it: a
        # helper that made none (this stand-in, on a machine whose
        # interfaces are listed) has nothing run, and nothing left.
        got, log = self.run_job({"to": "0.171.0", "recipe": self.placed()}, stub=False, root=True, more={"BUILDERBOT_NET_DEV": self.a_net})
        self.assertEqual(got, ("failed", 1), log)
        self.assertIn("it was started as if the network had been cut for it, and this process still has one: nothing is run", log)
        self.assertNotIn("running mkdir", log)
        self.assertEqual(self.left(), [".cache"])

    def test_the_second_run_takes_only_a_directory_of_the_account_s_own(self):
        # held-run.sh --run by hand: it reads an entry and runs steps from
        # a directory this account fetched into, by name and by owner, and
        # from no other; and a word in its environment that the cut is
        # made, or that this is a second run, is not heard.
        helper = os.path.join(REPO, "scripts", "lib", "held-run.sh")
        env = {"HOME": self.home, "PATH": f"{self.bin}:/usr/bin:/bin", "BUILDERBOT_NET_DEV": self.no_net, "SDK_CUT_MADE": "1", "SDK_PHASE": "run"}
        elsewhere = os.path.join(self.tmp.name, "aerie-held.none")
        link = os.path.join(self.tmp.name, "aerie-held.link")
        real = os.path.join(self.tmp.name, "real")
        os.makedirs(os.path.join(real, "dir"))
        with open(os.path.join(real, "entry.json"), "w") as f:
            f.write("{}")
        os.symlink(real, link)
        for top, said in ((elsewhere, "is not a directory this account fetched into"), (link, "is not a directory this account fetched into"),
                          (real, "is not a run's own directory"), ("relative/aerie-held.x", "is not a run's own directory"), ("", "is not a run's own directory")):
            p = subprocess.run(["bash", helper, "--run", top, "X CLI"], env=env, capture_output=True, text=True, check=False)
            self.assertEqual(p.returncode, 1, (top, p.stderr))
            self.assertIn(said, p.stderr, top)
        self.assertTrue(os.path.isdir(real), "and what it does not run from it does not remove")
        # A fetch into a directory that is there already is not this run's to take.
        os.makedirs(elsewhere)
        p = subprocess.run(["bash", helper, "--fetch", elsewhere, "X CLI"], env=env, input="{}", capture_output=True, text=True, check=False)
        self.assertEqual((p.returncode, os.path.isdir(elsewhere)), (1, True), p.stderr)
        # One run by hand, with those words in its environment: it fetches
        # as ever and decides the cut for itself, as ever.
        with open(os.path.join(self.bin, "unshare"), "w") as f:
            f.write("#!/bin/sh\nexit 1\n")
        os.chmod(os.path.join(self.bin, "unshare"), 0o755)
        recipe = self.placed()
        row = {"name": "X CLI", "source": {"kind": "command", "fetch": recipe["fetch"], "keyring": {}, "steps": [["mkdir", "-p", "{home}/made"]], "offline": True}}
        p = subprocess.run(["bash", helper, "X CLI", f"home={self.home}"], input=json.dumps({"toolchains": [row]}), capture_output=True, text=True, check=False,
                           env=env | {"FAKE_WEB": self.web, "BUILDERBOT_NETCUT_BIN": os.path.join(self.tmp.name, "no-helper")})
        self.assertEqual(p.returncode, 0, p.stdout + p.stderr)
        self.assertIn("fetching dl/codex.tar.gz", p.stdout)
        self.assertIn("this node cannot cut the network for a step", p.stdout)

    def test_a_recipe_of_the_older_form_still_runs_and_says_nothing_held_it(self):
        # An older catalog's row: a vendor's installer handed to a shell as
        # it arrives. Run as it was, and said in one line.
        got, log = self.run_job({"to": "0.163.0"}, stub=False)
        self.assertEqual(got, ("succeeded", 0), log)
        self.assertEqual(log.count("nothing holds what this fetches"), 1)
        self.assertIn("stub installed 0.163.0", log)
        self.assertIn("Codex CLI 0.163.0 is what a session here runs now", log)

    def test_no_recipe_installs_nothing_and_still_takes_the_agent_off(self):
        # This agent keeps no installer of its own: a job with no recipe
        # is refused, with or without a stand-in, and a removal needs none.
        marker = os.path.join(self.tmp.name, "ran")
        with open(self.stub, "w") as f:
            f.write(f'touch "{marker}"\n')
        got, log = self.run_job({"to": "0.163.0", "recipe": None})
        self.assertEqual(got, ("failed", 78), log)
        self.assertIn("the controller sent no install recipe for Codex CLI", log)
        self.assertFalse(os.path.exists(marker))
        for row in (*self.mod.AGENT_INSTALLS.values(), self.mod.CLAUDE_INSTALL):
            self.assertEqual(sorted(set(row) - {"pin_dir"}), sorted({"id", "command", "product", "reported", "bin"} | ({"also"} if "also" in row else set())))
        os.makedirs(os.path.join(self.home, ".local", "bin"))
        with open(os.path.join(self.home, ".local", "bin", "codex"), "w") as f:
            f.write("#!/bin/sh\n")
        got, log = self.run_job({"action": "remove", "recipe": None})
        self.assertEqual(got, ("succeeded", 0), log)
        self.assertFalse(os.path.exists(os.path.join(self.home, ".local", "bin", "codex")))

    def test_opencode_is_found_where_its_installer_puts_it(self):
        # B772: OpenCode's own script installs into ~/.opencode/bin whatever
        # it is told, so the update ran and then found no program at
        # ~/.local/bin. The stub does what the script does; the row names
        # that place, asks the script not to write the shell's files, and a
        # removal takes the old place away too.
        row = self.mod.AGENT_INSTALLS["opencode-update"]
        self.assertEqual(row["bin"], ".opencode/bin/opencode")
        stub = os.path.join(self.tmp.name, "opencode-installer.sh")
        with open(stub, "w") as f:
            f.write('mkdir -p "$HOME/.opencode/bin"\n'
                    'printf "#!/bin/sh\\necho ${VERSION:-0.0.0}\\n" > "$HOME/.opencode/bin/opencode"\n'
                    'chmod +x "$HOME/.opencode/bin/opencode"\necho "stub installed opencode $VERSION"\n')
        os.makedirs(os.path.join(self.home, ".local", "bin"))
        old = os.path.join(self.home, ".local", "bin", "opencode")
        with open(old, "w") as f:
            f.write("#!/bin/sh\necho 1.0.0\n")
        os.chmod(old, 0o755)
        with mock.patch.dict(os.environ, {"BUILDERBOT_OPEN_INSTALLER": stub}):
            got, log = self.run_job({"to": "1.19.5"}, type_="opencode-update")
            self.assertEqual(got, ("succeeded", 0), log)
            self.assertIn("OpenCode 1.19.5 is what a session here runs now", log)
            # Where the agent is not root there is no pinned copy, and a
            # session's PATH carries ~/.local/bin, not ~/.opencode/bin: the
            # old copy there, which would have run, is a link to the new one.
            self.assertEqual(os.readlink(old), os.path.join(self.home, ".opencode", "bin", "opencode"))
            got, log = self.run_job({"action": "remove"}, type_="opencode-update")
        self.assertEqual(got, ("succeeded", 0), log)
        self.assertFalse(os.path.exists(os.path.join(self.home, ".opencode", "bin", "opencode")))
        self.assertFalse(os.path.exists(old))

    def test_a_job_the_table_does_not_name_is_refused(self):
        got, log = self.run_job({}, type_="exec")
        self.assertEqual(got, ("failed", 78))
        self.assertIn("no coding agent", log)

    def test_a_removal_takes_the_account_s_copy_off(self):
        self.run_job({"to": "0.163.0"})
        got, log = self.run_job({"action": "remove"})
        self.assertEqual(got, ("succeeded", 0))
        self.assertFalse(os.path.exists(os.path.join(self.home, ".local", "bin", "codex")))

    def test_the_census_reads_each_agent_under_its_key(self):
        self.run_job({"to": "0.163.0"})
        with mock.patch.dict(os.environ, {}):
            v = self.mod._agent_version(self.mod.AGENT_INSTALLS["codex-update"], self.home)
        self.assertEqual(v, "codex-cli 0.163.0")
        self.assertEqual(self.mod._agent_version(self.mod.AGENT_INSTALLS["copilot-update"], self.home), "")

    def test_the_node_s_table_matches_the_controller_s(self):
        for job, how in {**self.mod.AGENT_INSTALLS, "claude-update": self.mod.CLAUDE_INSTALL}.items():
            a = agents.get(how["id"])
            self.assertEqual((a.update_job, a.command, a.product, a.reported),
                             (job, how["command"], how["product"], how["reported"]))
            # ...and the recipe this controller's table would send is one
            # the node takes, whole: what it fetches, what holds each
            # download, its steps or its script, and where the program is,
            # which is where the node's row says a removal finds it.
            sent, why = self.mod.recipe_checked(a.install)
            self.assertEqual(why, "", a.id)
            self.assertEqual(sent["bin"], how["bin"], a.id)
            self.assertLessEqual(set(how.get("also", ())), set(sent["also"]), f"{a.id}: the recipe clears every place the row would")
            self.assertEqual({k: sent[k] for k in ("script", "steps", "online", "keyring", "pin", "env", "fresh")},
                             {"script": a.install.get("script", ""), "steps": a.install.get("steps", []), "online": a.install.get("online", ""),
                              "keyring": a.install.get("keyring", {}), "pin": tuple(a.install["pin"]) if a.install["pin"] else None,
                              "env": a.install["env"], "fresh": a.install["fresh"]}, a.id)
            self.assertEqual([{k: f[k] for k in f if k not in ("track", "found")} for f in a.install.get("fetch", [])], sent["fetch"], a.id)

    def test_both_halves_hold_a_held_recipe_to_one_shape(self):
        # What the controller keeps of a manifest's recipe the node takes,
        # and what one refuses the other does: a step is never a line of
        # shell, a download is never held to nothing.
        for good in (HELD, PLACED):
            self.assertEqual(agents.install_checked(good), (good, ""))
            sent, why = self.mod.recipe_checked(good)
            self.assertEqual((why, sent["steps"], sent["fetch"], sent["online"]), ("", good["steps"], good["fetch"], good.get("online", "")))
        for bad in BAD_HELD:
            self.assertTrue(agents.install_checked(HELD | bad)[1], bad)
            self.assertTrue(self.mod.recipe_checked(HELD | bad)[1], bad)
        # How a newer pin is found is the pin tool's, and no node reads it.
        tracked = HELD | {"fetch": [HELD["fetch"][0] | {"track": {"resolver": "github-release", "repo": "x/x", "trim_prefix": "v"}, "found": {"from": "github-asset"}}]}
        self.assertEqual(agents.install_checked(tracked), (tracked, ""))
        self.assertEqual(self.mod.recipe_checked(tracked)[0]["fetch"], HELD["fetch"])
        self.assertEqual((self.mod.recipe_version(HELD), agents.install_version(HELD), agents.install_pins(HELD), agents.install_pins(PLACED)),
                         ("0.170.0", "0.170.0", "", "0.170.0"))

    def test_the_recipe_the_controller_hands_over_is_what_runs(self):
        # R169 step 13: where the program lands is the recipe's word, not
        # the node's table's. The stub is an installer that moved its
        # program; the recipe sent says where, and the job finds it there.
        stub = os.path.join(self.tmp.name, "moved-installer.sh")
        with open(stub, "w") as f:
            f.write('mkdir -p "$HOME/.codex/bin"\n'
                    'printf "#!/bin/sh\\necho codex-cli ${CODEX_VERSION:-0.0.0}\\n" > "$HOME/.codex/bin/codex"\n'
                    'chmod +x "$HOME/.codex/bin/codex"\n')
        recipe = {"rev": 2, "script": "curl -fsSL https://x.example/install.sh | sh", "pin": ["CODEX_VERSION", "{v}"],
                  "env": {}, "bin": ".codex/bin/codex", "also": [".local/bin/codex"], "fresh": ""}
        with mock.patch.dict(os.environ, {"BUILDERBOT_CODEX_INSTALLER": stub}):
            self.stub = stub
            got, log = self.run_job({"to": "0.170.0", "recipe": recipe, "recipe_from": "catalog"})
            self.assertEqual(got, ("succeeded", 0), log)
            self.assertIn("by the catalog's recipe (rev 2)", log)
            self.assertIn("Codex CLI 0.170.0 is what a session here runs now", log)
            # The census finds it as a session would, through ~/.local/bin.
            self.assertEqual(self.mod._agent_version(self.mod.AGENT_INSTALLS["codex-update"], self.home), "codex-cli 0.170.0")
            got, log = self.run_job({"action": "remove", "recipe": recipe, "recipe_from": "catalog"})
        self.assertEqual(got, ("succeeded", 0), log)
        self.assertFalse(os.path.lexists(os.path.join(self.home, ".codex", "bin", "codex")))
        self.assertFalse(os.path.lexists(os.path.join(self.home, ".local", "bin", "codex")))

    def test_what_is_not_a_recipe_is_refused_and_nothing_runs(self):
        marker = os.path.join(self.tmp.name, "ran")
        with open(self.stub, "w") as f:
            f.write(f'touch "{marker}"\n')
        for bad in BAD_RECIPES:
            got, log = self.run_job({"to": "0.163.0", "recipe": GOOD | bad})
            self.assertEqual(got, ("failed", 78), bad)
            self.assertIn("the install recipe the controller sent for Codex CLI is not one", log)
        got, log = self.run_job({"to": "0.163.0", "recipe": "curl https://x.example | sh"})
        self.assertEqual(got, ("failed", 78))
        self.assertFalse(os.path.exists(marker))
        # ...and the same shape is the controller's: what one takes the other does.
        self.assertEqual(self.mod.recipe_checked(GOOD)[1], "")


if __name__ == "__main__":
    unittest.main()
