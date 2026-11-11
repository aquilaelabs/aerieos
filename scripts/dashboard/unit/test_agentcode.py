"""Codex CLI and Copilot CLI as a node's rows in the Library and on the
Installed page (R95 step 2): the census's version against the registry's latest, each install its
own job, and the node agent's half run against a stub installer, never a
vendor's."""
import json
import os
import sys
import tempfile
import unittest
from unittest import mock

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, os.path.join(HERE, ".."))
import agentcode  # noqa: E402
import agents  # noqa: E402
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

    def test_codex_copilot_grok_and_open_are_tracked_and_claude_is_not(self):
        self.assertEqual([a.id for a in agentcode.tracked()], ["codex", "copilot", "grok", "open"])

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

    def catalog(self, recipe, error=""):
        """A catalog whose signed index pins codex's pack at one commit, and
        whose pack there carries `recipe`; the fetches are counted."""
        was = (agentcode.catalog_entry, agentcode.fetch_pack, dict(agentcode._recipes))
        self.addCleanup(lambda: (setattr(agentcode, "catalog_entry", was[0]), setattr(agentcode, "fetch_pack", was[1]),
                                 agentcode._recipes.clear(), agentcode._recipes.update(was[2])))
        agentcode._recipes.clear()
        asked = []
        agentcode.catalog_entry = lambda name: {"name": name, "url": "https://example.test/catalog", "commit": "c" * 40,
                                                "sha256": "5" * 64, "path": "packs/agents/" + name} if name == "codex" else None

        def fetch(url, commit, shipped, sha256, path):
            asked.append((url, commit, sha256, path))
            return {"error": error} if error else {"manifest": {"agent": {"install": recipe}}}
        agentcode.fetch_pack = fetch
        return asked

    def test_a_newer_recipe_in_the_catalog_is_the_one_sent(self):
        # The point of it: an installer that changed upstream is answered
        # by the catalog, with no release of AerieOS.
        theirs = agents.get("codex").install | {"rev": 2, "bin": ".codex/bin/codex", "also": [".local/bin/codex"]}
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
        entry = {"name": "open", "url": "file://" + tmp, "commit": git("rev-parse", "HEAD").decode().strip(), "path": "packs/agents/open",
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
            agentcode._recipes.clear()
            agentcode.catalog_entry = lambda name: dict(entry, sha256="0" * 64) if name == "open" else None
            self.assertEqual(agentcode.recipe("open"), (agents.get("open").install, "release"))

    def test_a_catalog_no_newer_than_the_release_changes_nothing(self):
        # A catalog left behind never undoes what a release fixed.
        self.catalog(agents.get("codex").install | {"script": "curl -fsSL https://old.example/install.sh | sh"})
        self.assertEqual(agentcode.recipe("codex"), (agents.get("codex").install, "release"))

    def test_a_pack_that_cannot_be_read_leaves_the_table_s(self):
        asked = self.catalog(None, error="its archive's sha256 differs, so it is refused")
        self.assertEqual(agentcode.recipe("codex"), (agents.get("codex").install, "release"))
        self.assertEqual(agentcode.recipe("codex"), (agents.get("codex").install, "release"))
        self.assertEqual(len(asked), 1)          # asked again only after RECIPE_MISS_S

    def test_a_recipe_is_held_to_its_shape(self):
        for a in agents.TABLE:
            self.assertEqual(agents.install_checked(a.install), (a.install, ""), a.id)
        for bad in BAD_RECIPES:
            self.assertTrue(agents.install_checked(GOOD | bad)[1], bad)
        self.assertTrue(agents.install_checked(GOOD | {"rev": True})[1])
        self.assertEqual(agents.install_checked(GOOD)[1], "")

    def test_an_official_pack_s_manifest_carries_it_and_no_other_pack_s_does(self):
        import toolpacks  # noqa: PLC0415
        a = agents.get("open")
        m = {"name": "open", "tier": "official", "platforms": ["linux/*"], "terms": [],
             "agent": {k: getattr(a, k) for k in toolpacks.AGENT_FIELDS} | {"install": a.install}}
        clean, errors = toolpacks.validate(m)
        self.assertEqual(errors, [])
        self.assertEqual(clean["agent"]["install"], a.install)
        m["agent"]["install"] = a.install | {"script": "curl -fsSL https://x.example/i | bash; rm -rf ~"}
        self.assertIn("agent.install.script", " ".join(toolpacks.validate(m)[1]))

    def test_an_update_holds_that_agents_starts_as_claude_codes_does(self):
        ns = self.use(node())
        self.assertEqual(agentcode.start_hold("alpha", "n1", "codex"), "")
        ns.jobs_for = lambda *a, **k: [{"type": "codex-update"}] if k.get("type") == "codex-update" else []
        self.assertIn("is updating", agentcode.start_hold("alpha", "n1", "codex"))
        self.assertEqual(agentcode.start_hold("alpha", "n1", "copilot"), "")

    def test_a_removal_needs_it_installed(self):
        self.use(node(codex=""))
        self.assertIn("not installed", agentcode.remove("user:admin", "n1", "codex")["error"])

    def test_claude_is_not_this_module_s(self):
        self.use(node())
        with self.assertRaises(KeyError):
            agentcode.update("user:admin", "n1", "claude")

    def test_the_census_catches_up_when_the_job_ends(self):
        ns = self.use(node())
        ns.log = "installing\nCodex CLI 0.163.0 is what a session here runs now\n"
        agentcode.update_done({"id": "j_1", "type": "codex-update", "node": "n1", "spec": {}}, "succeeded")
        self.assertEqual(ns.reported, [("n1", "session", "codex", "0.163.0")])

    def test_the_toolchains_page_draws_both_beside_claude(self):
        self.use(node())
        toolchains.agentcode = agentcode
        names = [agentcode.row(node(), a.id)["name"] for a in agentcode.tracked()]
        self.assertEqual(names, [a.tool for a in agents.installable() if a.id != "claude"])


class NodeAgent(unittest.TestCase):
    """The node's half: AGENT_INSTALLS's row for the job, the installer run
    with the version pinned, the binary's version read back."""

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

    def run_job(self, spec, type_="codex-update"):
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
        fake.as_user = lambda env, who: {}
        fake.session_renew = lambda: None
        fake.hello_again = lambda why: None
        # The one install path every agent's job goes through (R95 step 18).
        fake.agent_install = lambda job, spec, how: self.mod.Agent.agent_install(fake, job, spec, how)
        fake.agent_recipe = lambda job, spec, row: self.mod.Agent.agent_recipe(fake, job, spec, row)
        env = {"BUILDERBOT_CODEX_INSTALLER": self.stub, "HOME": self.home}
        with mock.patch.dict(os.environ, env), \
                mock.patch("os.path.expanduser", return_value=self.home), \
                mock.patch("os.geteuid", return_value=1000):
            for m in self.mod._mods:
                if "sdk_env" in vars(m):
                    vars(m)["sdk_env"] = lambda state: {"HOME": self.home, "PATH": "/usr/bin:/bin"}
            got = self.mod.Agent.agent_update(fake, job, spec)
        return got, "".join(said)

    def test_the_installer_runs_with_the_version_and_the_binary_is_read_back(self):
        got, log = self.run_job({"to": "0.163.0"})
        self.assertEqual(got, ("succeeded", 0), log)
        self.assertIn("stub installed 0.163.0", log)
        self.assertIn("Codex CLI 0.163.0 is what a session here runs now", log)

    def test_opencode_is_found_where_its_installer_puts_it(self):
        # B772: OpenCode's own script installs into ~/.opencode/bin whatever
        # it is told, so the update ran and then found no program at
        # ~/.local/bin. The stub does what the script does; the row names
        # that place, asks the script not to write the shell's files, and a
        # removal takes the old place away too.
        row = self.mod.AGENT_INSTALLS["opencode-update"]
        self.assertEqual(row["bin"], ".opencode/bin/opencode")
        self.assertIn("--no-modify-path", row["script"])
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
            # ...and its recipe, which is what runs for a controller that
            # sends none, is the one this controller's table would send.
            sent, why = self.mod.recipe_checked(a.install)
            self.assertEqual(why, "", a.id)
            self.assertEqual({k: sent[k] for k in ("script", "pin", "env", "bin", "also", "fresh")},
                             {"script": how["script"], "pin": tuple(how["pin"]) if how["pin"] else None, "env": how["env"],
                              "bin": how["bin"], "also": tuple(how.get("also", ())), "fresh": how.get("fresh", "")}, a.id)

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
