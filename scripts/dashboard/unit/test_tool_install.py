"""A session's `aerie tool install NAME` installs the tool on the node that
session runs on (toolchains.session_install, session_do; phone's ask):
Allow queues the install there as the person who allowed it, where it used
to keep a pack and install it nowhere (B1040). A name AerieOS ships is the
toolchain and never a pack; one the node holds whole is said at once; a
folder with no tool in it still asks; auto asks nobody; deny keeps its
words; an agreement is accepted for nobody; a pack that needs root stays an
administrator's; and the node is the one the session is on. Held without a
server: the node store, the kept packs and the catalog's entry are
stand-ins, the bell and the queue's rules are the modules' own."""
import os
import sys
import unittest

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))
import names  # noqa: E402
import phone  # noqa: E402
import toolchains  # noqa: E402

PIN = {"name": "hexkit", "kind": "pack", "tier": "vetted", "url": "https://example.com/hex", "commit": "a" * 40,
       "sha256": "b" * 64, "path": "packs/hexkit", "platforms": ["linux/amd64"], "about": "Looks inside binaries."}
ROW = {"name": "hexkit", "label": "Hex kit", "probe": "hexkit", "about": "Looks inside binaries.",
       "platforms": ["linux/amd64"], "layout": {"bin": ["bin"], "tool": "bin/hexkit"},
       "pack": {"url": PIN["url"], "commit": PIN["commit"]}, "verbs": {}}
DENIED = ("alpha's settings say an agent may not add a tool pack (Install a tool pack is deny): "
          "a person adds one from the Library, or changes that in the space's settings")
UID = "u_0a1b2c3d"


def node(nid, name, top=(), incomplete=(), sessions=(), arch="x86_64"):
    return {"id": nid, "name": name, "kind": "agent", "state": "online", "live": True, "os": "linux", "arch": arch,
            "reported": {"stores": {"toolchains": {"path": "/s", "scope": nid}}, "sessions": [{"name": s} for s in sessions],
                         "store_dirs": {"top": list(top), "android": [], "incomplete": list(incomplete)}}}


class Install(unittest.TestCase):
    def setUp(self):
        test = self
        self.nodes_ = {"n1": node("n1", "sandbox"), "n2": node("n2", "bench")}
        self.jobs, self.adds, self.packs, self.entries = [], [], {}, {"hexkit": dict(PIN)}
        self.root_pack = False

        class Nodes:
            LOCAL = "local"

            @staticmethod
            def node(nid):
                return test.nodes_.get(nid)

            @staticmethod
            def node_list(all=False):
                return list(test.nodes_.values())

            @staticmethod
            def node_sessions():
                return {i: (n["name"], n["reported"]["sessions"]) for i, n in test.nodes_.items()}

            @staticmethod
            def jobs_for(**k):
                return []

            @staticmethod
            def job_add(principal, placement, type, spec, project="", source=None):
                test.jobs.append({"by": principal, "node": placement.get("node"), "type": type, "spec": spec})
                return {"ok": True, "job": f"j_{len(test.jobs):08x}"}

        def add(entry, by, may_root=False):
            test.adds.append((entry["name"], entry.get("commit"), by, may_root))
            if test.root_pack and not may_root:
                return {"error": f"{entry['name']}: it needs root on the node (its touches say so): an administrator adds it"}
            test.packs[entry["name"]] = {"name": entry["name"], "manifest": {"touches": {"root": test.root_pack}}}
            return {"ok": True}

        was = {k: getattr(toolchains, k) for k in ("nodes", "pack_entry", "pack_have", "pack_add", "pack_ask", "packs_rows", "CATALOG_DIGEST")}
        rows = list(toolchains.TOOLCHAINS)
        runner, reqs = phone.pack_runner, list(phone._reqs)

        def back():
            for k, v in was.items():
                setattr(toolchains, k, v)
            toolchains.TOOLCHAINS[:] = rows
            phone.pack_runner = runner
            phone._reqs[:] = reqs
        self.addCleanup(back)
        toolchains.nodes = Nodes()
        toolchains.pack_entry = lambda name: self.entries.get(name)
        toolchains.pack_have = lambda: self.packs
        toolchains.pack_add = add
        toolchains.pack_ask = phone.ask_pack
        # The kept packs' rows, as toolpacks.recipes hands them over.
        toolchains.packs_rows = lambda: [dict(ROW, **self.row_extra)] if "hexkit" in self.packs else []
        self.row_extra = {}
        # The server's own wiring of an allowed ask.
        phone.pack_runner = lambda project, held, by: toolchains.session_do(
            held, f"user:{by} (for session:{project})", pack_by=f"session:{project} (allowed by {by})", may_root=True)
        phone._reqs[:] = []

    def ask(self, name, mode="ask", mine=("n1",), said="", why="to build the app", uid=UID):
        return toolchains.session_install("alpha", {"action": "install", "name": name, "why": why, "node": said},
                                          mine=list(mine), uid=uid, mode=mode, asker="session:alpha", shown="Alpha")

    def allow(self, rid):
        return phone.decide(rid, True, "u_admin000", "ann", admin=True)

    def test_allow_installs_a_shipped_toolchain_on_the_session_s_node_and_adds_no_pack(self):
        r, st = self.ask("jdk")
        self.assertEqual((st, r.get("to"), r.get("node"), r.get("name")), (200, "the administrators", "sandbox", "jdk"), r)
        held = phone._find(r["id"])
        self.assertEqual((held["kind"], held["cmd"], held["node"], held["node_name"], held["project"]),
                         ("pack", ["tool", "install", "jdk"], "n1", "sandbox", "alpha"))
        self.assertEqual(held["pack"], {"name": "jdk", "toolchain": True}, "a shipped name holds no pin: it is no pack")
        row = phone._req_public(held)
        self.assertEqual((row["name"], row["node_name"], row["kind"]), ("jdk", "sandbox", "pack"), "the row names the tool and the node")
        self.assertNotIn("pack", row, "an address and a pin stay off the row")
        self.assertEqual((self.jobs, self.adds), ([], []), "nothing happens before a person answers")
        got = self.allow(r["id"])
        self.assertEqual((got.get("ok"), got.get("job"), got.get("said")), (True, "j_00000001", "installing jdk on sandbox"), got)
        self.assertEqual(self.jobs, [{"by": "user:ann (for session:alpha)", "node": "n1", "type": "toolchain",
                                      "spec": {"action": "install", "names": ["jdk"], "step_timeout": toolchains.TC_STEP_S,
                                               "timeout": toolchains.TC_STEP_S + 600}}])
        self.assertEqual((self.adds, self.packs), ([], {}), "and no pack is kept under the toolchain's name")
        out = phone.outcome(r["id"], project="alpha")
        self.assertEqual((out["state"], out["code"], out["out"], out["job"]),
                         ("done", 0, "installing jdk on sandbox: job j_00000001", "j_00000001"), "the asker's verb is told the job")
        self.assertIn("error", phone.outcome(r["id"], project="beta"), "and no other space's")

    def test_the_catalog_s_word_for_an_android_part_is_its_shipped_row(self):
        self.assertEqual((toolchains.shipped_name("jdk"), toolchains.shipped_name("android-ndk"), toolchains.shipped_name("android:ndk"),
                          toolchains.shipped_name("android-tools"), toolchains.shipped_name("hexkit"), toolchains.shipped_name("")),
                         ("jdk", "android:ndk", "android:ndk", "android-tools", "", ""))
        self.packs["hexkit"] = {"manifest": {}}
        toolchains.refresh_packs()
        self.assertNotIn("hexkit", toolchains.shipped_names(), "a pack kept here is not a shipped name")
        self.assertIn("jdk", toolchains.shipped_names())

    def test_allow_adds_a_catalog_pack_and_installs_it_there(self):
        r, st = self.ask("hexkit")
        self.assertEqual(st, 200, r)
        held = phone._find(r["id"])
        self.assertEqual((held["pack"]["commit"], held["pack"]["sha256"], held["pack"]["path"], held["pack"]["tier"], held["pack"].get("toolchain")),
                         ("a" * 40, "b" * 64, "packs/hexkit", "vetted", False), "held with the pin the signed index names")
        got = self.allow(r["id"])
        self.assertEqual(got.get("said"), "hexkit is added to the catalog here, and installing it on sandbox", got)
        self.assertEqual(self.adds, [("hexkit", "a" * 40, "session:alpha (allowed by ann)", True)])
        self.assertEqual([(j["by"], j["node"], j["spec"]["names"]) for j in self.jobs], [("user:ann (for session:alpha)", "n1", ["hexkit"])])
        # Kept here already and not on the node: the ask is for the install
        # alone, where the verb used to answer that it was added already.
        self.jobs.clear()
        self.adds.clear()
        r, st = self.ask("hexkit")
        self.assertEqual((st, bool(r.get("id"))), (200, True), r)
        self.assertEqual(self.allow(r["id"]).get("said"), "installing hexkit on sandbox")
        self.assertEqual((self.adds, len(self.jobs)), ([], 1))

    def test_one_the_node_holds_is_said_at_once_and_nobody_is_asked(self):
        self.nodes_["n1"] = node("n1", "sandbox", top=["jdk", "hexkit"])
        for mode in ("ask", "auto", "deny"):
            r, st = self.ask("jdk", mode=mode)
            self.assertEqual((st, r.get("installed"), r.get("note")), (200, True, "jdk is installed on sandbox already"), mode)
        # A folder of a pack's name is the pack's only once the pack is kept here.
        r, st = self.ask("hexkit")
        self.assertTrue(r.get("id"), r)
        phone._reqs[:] = []
        self.packs["hexkit"] = {"manifest": {}}
        toolchains.refresh_packs()
        r, st = self.ask("hexkit")
        self.assertTrue(r.get("note", "").startswith("hexkit is installed on sandbox already"), r)
        self.assertEqual((phone._reqs, self.jobs), ([], []))

    def test_a_folder_with_no_tool_in_it_is_not_installed(self):
        # What an install that stopped leaves: the node lists the folder
        # and names it incomplete. The ask goes ahead (the installer clears
        # the folder itself), and so does an Allow that finds it so.
        self.nodes_["n1"] = node("n1", "sandbox", top=["jdk"], incomplete=["jdk"])
        self.assertIn("jdk", toolchains.node_has(self.nodes_["n1"]))
        self.assertNotIn("jdk", toolchains.node_whole(self.nodes_["n1"]))
        r, st = self.ask("jdk")
        self.assertEqual((st, bool(r.get("id")), r.get("note")), (200, True, None), r)
        self.assertEqual(self.allow(r["id"]).get("job"), "j_00000001")
        # ...and it is not a requirement met: what needs it installs it first.
        need = next(p for p in toolchains.TOOLCHAINS if "jdk" in (p.get("requires") or []) and not toolchains.agreements([p["name"]]))
        self.nodes_["n1"] = node("n1", "sandbox", top=["jdk", *[x for x in need["requires"] if x != "jdk"]], incomplete=["jdk"])
        self.jobs.clear()
        r, st = self.ask(need["name"], mode="auto")
        self.assertEqual(self.jobs[0]["spec"]["names"], ["jdk", need["name"]], r)
        self.assertEqual(r["said"], f"installing {need['name']} on sandbox, with jdk which it needs")

    def test_an_install_that_landed_while_the_ask_waited_is_said_not_queued_twice(self):
        r, _ = self.ask("jdk")
        self.nodes_["n1"] = node("n1", "sandbox", top=["jdk"])
        got = self.allow(r["id"])
        self.assertEqual((got.get("ok"), got.get("said"), got.get("job")), (True, "jdk is installed on sandbox already", None))
        self.assertEqual(self.jobs, [])
        self.assertEqual(phone.outcome(r["id"], project="alpha")["out"], "jdk is installed on sandbox already")

    def test_auto_installs_with_no_ask_as_the_session_s_own(self):
        r, st = self.ask("jdk", mode="auto")
        self.assertEqual((st, r.get("job"), r.get("said"), r.get("node_name")), (200, "j_00000001", "installing jdk on sandbox", "sandbox"), r)
        self.assertEqual([(j["by"], j["node"], j["spec"]["names"]) for j in self.jobs], [("session:alpha", "n1", ["jdk"])])
        self.assertEqual(phone._reqs, [], "nobody is asked")
        r, st = self.ask("hexkit", mode="auto")
        self.assertEqual((st, r.get("said"), r.get("added")), (200, "hexkit is added to the catalog here, and installing it on sandbox", True), r)
        self.assertEqual(self.adds, [("hexkit", "a" * 40, "session:alpha", False)])
        self.assertEqual(self.jobs[-1]["spec"]["names"], ["hexkit"])

    def test_deny_refuses_in_the_words_it_had(self):
        for name in ("jdk", "hexkit"):
            r, st = self.ask(name, mode="deny")
            self.assertEqual((st, r), (403, {"error": DENIED}), name)
        self.assertEqual((phone._reqs, self.jobs, self.adds), ([], [], []))

    def test_an_agreement_is_accepted_for_nobody(self):
        # Google's Android SDK terms, as the Library asks a person to accept
        # them by name: never a session's reason and never an Allow.
        need = toolchains.agreements(["android-tools"])
        self.assertTrue(need, "the row that proves this accepts an agreement")
        for name, row in (("android-tools", "android-tools"), ("android-ndk", "android:ndk")):
            for mode in ("ask", "auto"):
                r, st = self.ask(name, mode=mode)
                self.assertEqual(st, 409, (name, mode, r))
                self.assertEqual(r["error"], f"installing {row} accepts {need[0]['label']}, which only a person accepts: "
                                             f"a person installs {row} on sandbox from the Library, where they accept it")
                self.assertEqual(r["accept"], toolchains.agreements([row]))
        self.assertEqual((phone._reqs, self.jobs), ([], []), "nobody is asked to allow what Allow could not do")
        # A pack whose terms are read only once it is kept: an Allow keeps
        # it and installs nothing, and says which of the two happened.
        self.row_extra = {"terms": [{"label": "The vendor's license", "url": "https://example.com/terms", "accept": True}]}
        r, _ = self.ask("hexkit")
        got = self.allow(r["id"])
        self.assertEqual(got, {"error": "hexkit is added to the catalog here, and installing hexkit accepts The vendor's license, "
                                        "which only a person accepts: a person installs hexkit on sandbox from the Library, where they accept it"})
        self.assertEqual(self.jobs, [])
        self.assertEqual(phone.outcome(r["id"], project="alpha")["code"], 1)

    def test_a_pack_that_needs_root_stays_an_administrator_s(self):
        self.root_pack = True
        r, st = self.ask("hexkit", mode="auto")
        self.assertEqual((st, r), (400, {"error": "hexkit: it needs root on the node (its touches say so): an administrator adds it"}))
        self.assertEqual((self.adds, self.jobs, self.packs), ([("hexkit", "a" * 40, "session:alpha", False)], [], {}))
        # An administrator's Allow keeps it and installs it.
        r, _ = self.ask("hexkit")
        self.assertEqual(self.allow(r["id"]).get("job"), "j_00000001")
        self.assertEqual(self.adds[-1], ("hexkit", "a" * 40, "session:alpha (allowed by ann)", True))
        # Kept by an administrator, it is still theirs to put on a node: at
        # auto a session's name queues nothing.
        self.jobs.clear()
        r, st = self.ask("hexkit", mode="auto")
        self.assertEqual((st, r), (400, {"error": "hexkit: it needs root on the node (its touches say so): "
                                                 "an administrator installs it on sandbox from the Library"}))
        self.assertEqual(self.jobs, [])

    def test_the_node_is_the_one_the_session_runs_on(self):
        both = ("n1", "n2")
        # A space on several nodes: the node the session's terminal was
        # told, believed only among the space's own.
        r, _ = self.ask("jdk", mine=both, said="n2")
        self.assertEqual((r.get("node"), phone._find(r["id"])["node"]), ("bench", "n2"))
        r, st = self.ask("jdk", mine=("n1",), said="n2")
        self.assertEqual(phone._find(r["id"])["node"], "n1", "a node that is not the space's is not taken on the session's word")
        # None said: the heartbeats say it, when one node alone reports
        # this account's session on this space.
        mine = f"{UID}~{names.agent_sessions('alpha')[0]}"
        self.nodes_["n2"] = node("n2", "bench", sessions=[mine, f"u_ffffffff~{names.agent_sessions('alpha')[0]}"])
        self.nodes_["n1"] = node("n1", "sandbox", sessions=[f"u_ffffffff~{names.agent_sessions('alpha')[0]}",
                                                           f"{UID}~{names.agent_sessions('beta')[0]}"])
        r, _ = self.ask("jdk", mine=both)
        self.assertEqual(phone._find(r["id"])["node"], "n2")
        # It cannot be told: on both, or on neither. Nobody is asked.
        before = len(phone._reqs)
        self.nodes_["n1"] = node("n1", "sandbox", sessions=[mine])
        for case in ("both", "neither"):
            if case == "neither":
                self.nodes_["n1"], self.nodes_["n2"] = node("n1", "sandbox"), node("n2", "bench")
            for mode in ("ask", "auto"):
                r, st = self.ask("jdk", mine=both, mode=mode)
                self.assertEqual((st, r), (400, {"error": "Alpha works on several nodes (sandbox, bench) and which one this session runs on "
                                                          "could not be told: start the session again from the dashboard, or have a person "
                                                          "install jdk on its node from the Library"}), (case, mode))
        r, st = self.ask("jdk", mine=())
        self.assertEqual((st, r), (400, {"error": "Alpha runs on no node, so there is no machine to install jdk on: "
                                                  "a node is picked in the space's settings"}))
        self.assertEqual((len(phone._reqs), self.jobs), (before, []))
        # Deny is said before a node that cannot be told.
        self.assertEqual(self.ask("jdk", mine=(), mode="deny")[0], {"error": DENIED})

    def test_what_is_no_pack_to_add_is_refused_by_name(self):
        r, st = self.ask("nothere")
        self.assertEqual((st, r), (400, {"error": "no tool pack called nothere in the vetted catalog: aerie tool search WORDS lists them"}))
        # A coding agent AerieOS ships is in the index as an official pack.
        self.entries["claude"] = dict(PIN, name="claude", tier="official")
        r, st = self.ask("claude", mode="auto")
        self.assertEqual((st, r), (400, {"error": "claude is part of AerieOS itself, not a tool pack to add: "
                                                  "a person installs or updates it from the Library"}))
        self.assertEqual((phone._reqs, self.jobs, self.adds), ([], [], []))

    def test_a_node_it_is_not_packaged_for_is_refused_before_anybody_is_asked(self):
        self.nodes_["n1"] = node("n1", "sandbox", arch="aarch64")
        r, st = self.ask("hexkit")
        self.assertEqual((st, r), (400, {"error": "sandbox is linux/arm64, and hexkit is packaged for linux/amd64"}))
        only = next((p for p in toolchains.TOOLCHAINS if not toolchains.supports(p, "linux/arm64") and not toolchains.agreements([p["name"]])
                     and not p.get("requires")), None)
        if only:
            r, st = self.ask(only["name"])
            self.assertEqual(st, 400)
            self.assertIn(f"sandbox is linux/arm64, and {only['name']} is packaged for", r["error"])
        self.assertEqual((phone._reqs, self.jobs, self.adds), ([], [], []))

    def test_an_ask_needs_a_reason_and_a_refused_install_reaches_both(self):
        self.assertIn("say what the tool is for", phone.ask_pack("", "alpha", {"name": "jdk", "node": "n1"}).get("error", ""))
        r, st = self.ask("jdk", why="")
        self.assertEqual(phone._find(r["id"])["why"], "install jdk on sandbox", "the verb's own words stand in for none")
        # The node went away while the ask waited: Allow says so to the
        # person, and the outcome says so to the session.
        self.nodes_.pop("n1")
        got = self.allow(r["id"])
        self.assertIn("is gone", got.get("error", ""))
        out = phone.outcome(r["id"], project="alpha")
        self.assertEqual((out["code"], out["out"]), (1, got["error"]))


if __name__ == "__main__":
    unittest.main()
