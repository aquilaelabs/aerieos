"""What is not for this AerieOS is not offered, and what was kept and no
longer fits is switched off (the operator, 12 Nov): a catalog entry written
in a format past this build's, or for other release lines than this one, is
left out of the Library's cards and counted; a pack an install holds whose
manifest stops naming the running line after an upgrade stays where it is
installed, offers no agent and reaches no session, until a version that
names this line is kept."""
import json
import os
import subprocess
import sys
import tempfile
import unittest

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))
import catalogindex  # noqa: E402
import library  # noqa: E402
import packformat  # noqa: E402
import toolpacks  # noqa: E402

VERBS = os.path.join(os.path.dirname(__file__), "..", "..", "lib", "settings-verbs.py")


def entry(name, **more):
    return {"name": name, "url": f"https://example.com/{name}", "commit": "a" * 40, "sha256": "c" * 64, "tier": "vetted", "about": name,
            "platforms": ["linux/*"], **more}


class On(unittest.TestCase):
    """This build is on the 0.9 line."""

    def setUp(self):
        saved = (toolpacks.running_version, library.fits)
        self.addCleanup(lambda: (setattr(toolpacks, "running_version", saved[0]), setattr(library, "fits", saved[1])))
        toolpacks.running_version = lambda: "0.9.0-dev.5400+abc1234"
        library.fits = toolpacks.fits


class TheIndex(On):
    def test_an_entry_repeats_the_lines_its_manifest_works_with(self):
        raw = json.dumps({"version": 1, "packs": [entry("fits", works_with=["0.9", "0.10"]), entry("plain"),
                                                  entry("odd", works_with=["latest"]), entry("many", works_with=["0.9"] * 13)]}).encode()
        got, why = catalogindex.parse(raw)
        self.assertEqual(why, "")
        by = {p["name"]: p for p in got["packs"]}
        self.assertEqual(by["fits"]["works_with"], ["0.9", "0.10"])
        for name in ("plain", "odd", "many"):
            self.assertNotIn("works_with", by[name], name)


class TheLibrary(On):
    TC = {"name": "box", "live": True, "root": "/mnt/SDK", "platform": "linux/amd64", "items": [
        {"name": "kept", "label": "Kept", "about": "k", "installed": True, "version": "1", "state": "current",
         "pack": {"url": "https://example.com/kept", "commit": "b" * 40, "tier": "vetted", "disabled": "switched off: it works with AerieOS 0.8, and this is 0.9"}}]}

    def rows(self, *entries, formats=None):
        return {r["name"]: r for r in library.rows(self.TC, [], [], {"packs": list(entries), "formats": formats or {}}, None)}

    def test_an_entry_for_this_line_or_for_any_is_offered(self):
        by = self.rows(entry("here", works_with=["0.9"]), entry("any"))
        self.assertEqual((by["here"]["verb"], by["any"]["verb"]), ("add", "add"))
        self.assertNotIn("too_new", by["here"])

    def test_an_entry_for_other_lines_is_marked_and_has_nothing_to_press(self):
        by = self.rows(entry("later", works_with=["0.10", "0.11"]), entry("earlier", works_with=["0.8"]),
                       entry("app", kind="app", works_with=["0.10"]))
        for name in ("later", "earlier", "app"):
            self.assertTrue(by[name]["too_new"], name)
            self.assertEqual(by[name]["verb"], "", name)
        self.assertIn("works with AerieOS 0.10, 0.11", by["later"]["too_new"])

    def test_an_entry_in_a_format_past_this_builds_is_marked_the_same_way(self):
        by = self.rows(entry("next", format=packformat.FORMAT + 1), formats={str(packformat.FORMAT + 1): "0.10.0"})
        self.assertIn("0.10.0", by["next"]["too_new"])
        self.assertEqual(by["next"]["verb"], "")

    def test_a_newer_pin_that_does_not_fit_is_no_update_to_offer(self):
        by = self.rows(entry("kept", commit="d" * 40, works_with=["0.10"]))
        self.assertIsNone(by["kept"]["repin"])
        by = self.rows(entry("kept", commit="d" * 40, works_with=["0.9", "0.10"]))
        self.assertEqual(by["kept"]["repin"]["commit"], "d" * 40, "one that fits is the way back")
        self.assertIn("switched off", by["kept"]["pack"]["disabled"])


class AHeldPack(On):
    def rec(self, ww, agent=True):
        m = {"name": "heron", "label": "Heron", "about": "h", "platforms": ["linux/*"], "terms": [], "steps": [], "verbs": {}, "layout": {},
             "works_with": ww}
        if agent:
            m["pack_agent"] = {"name": "Heron", "command": "heron"}
        return {"url": "https://example.com/heron", "commit": "a" * 40, "tier": "vetted", "manifest": m}

    def test_one_that_names_this_line_or_none_is_on(self):
        for ww in (["0.9"], ["0.8", "0.9"], []):
            self.assertEqual(toolpacks.disabled(self.rec(ww)), "", ww)
            self.assertTrue(toolpacks.offers_agent(self.rec(ww)), ww)

    def test_one_that_stops_fitting_is_switched_off_and_offers_no_agent(self):
        rec = self.rec(["0.8"])
        self.assertEqual(toolpacks.disabled(rec), "switched off: it works with AerieOS 0.8, and this is 0.9")
        self.assertIsNone(toolpacks.offers_agent(rec))
        self.assertEqual(toolpacks.recipe(rec)["pack"]["disabled"], toolpacks.disabled(rec))
        self.assertTrue(toolpacks.recipe(rec)["pack"]["agent"], "its card stays with the agents, switched off")

    def test_a_build_with_no_version_switches_nothing_off(self):
        toolpacks.running_version = lambda: ""
        self.assertEqual(toolpacks.disabled(self.rec(["0.8"])), "")


class ASideloadedAgent(On):
    """A pack a person added themselves offers its agent only where the
    install says so: for trying an agent of your own before submitting it."""

    def setUp(self):
        super().setUp()
        saved = toolpacks.sideload_agents
        self.addCleanup(setattr, toolpacks, "sideload_agents", saved)

    def rec(self, tier):
        return {"url": "https://example.com/heron", "commit": "a" * 40, "tier": tier,
                "manifest": {"name": "heron", "label": "Heron", "about": "h", "platforms": ["linux/*"], "terms": [], "steps": [], "verbs": {},
                             "layout": {}, "works_with": [], "pack_agent": {"name": "Heron", "command": "heron"}}}

    def test_off_it_installs_and_offers_no_agent(self):
        toolpacks.sideload_agents = lambda: False
        for tier in ("url", "here"):
            self.assertIsNone(toolpacks.offers_agent(self.rec(tier)), tier)
            self.assertFalse(toolpacks.recipe(self.rec(tier))["pack"]["agent"])
            self.assertNotIn("agent", toolpacks.recipe(self.rec(tier)))
        self.assertTrue(toolpacks.offers_agent(self.rec("vetted")), "one the catalog pinned is offered either way")

    def test_on_it_is_offered_and_its_adapter_rides_to_the_nodes(self):
        toolpacks.sideload_agents = lambda: True
        for tier in ("url", "here"):
            self.assertEqual(toolpacks.offers_agent(self.rec(tier))["command"], "heron", tier)
            row = toolpacks.recipe(self.rec(tier))
            self.assertTrue(row["pack"]["agent"])
            self.assertEqual(row["agent"]["name"], "Heron")

    def test_the_setting_is_off_until_somebody_turns_it_on(self):
        import settings
        self.assertIs(settings.KEYS["sideload_agents"]["default"], False)


class ASpacesSessions(unittest.TestCase):
    """aerie settings, which a session's launcher reads: a pack switched off
    is off for every space, ticked there or not."""

    def show(self, version):
        d = tempfile.mkdtemp()
        self.addCleanup(__import__("shutil").rmtree, d, True)
        with open(os.path.join(d, "toolpacks.json"), "w") as f:
            json.dump({"packs": {"old": {"manifest": {"name": "old", "works_with": ["0.8"]}},
                                 "new": {"manifest": {"name": "new", "works_with": ["0.9"]}},
                                 "any": {"manifest": {"name": "any"}}, "unticked": {"manifest": {"name": "unticked"}}}}, f)
        p = subprocess.run([sys.executable, VERBS, "show", os.path.join(os.path.dirname(VERBS), "..", "dashboard"), "alpha"],
                           env={**os.environ, "DASHBOARD_STATE": d, "BB_VERSION": version, "WORKSPACE": d, "BB_SETTINGS_JSON": "1"},
                           capture_output=True, text=True)
        return p

    def test_the_off_list_holds_the_pack_that_does_not_fit(self):
        p = self.show("0.9.0-dev.5400+abc1234")
        self.assertEqual(p.returncode, 0, p.stderr)
        rec = json.loads(p.stdout)
        self.assertEqual(rec["packs_disabled"], ["old"])
        self.assertIn("old", rec["toolchains_off"])
        rec = json.loads(self.show("0.8.3").stdout)
        self.assertEqual(rec["packs_disabled"], ["new"], "judged against the build that is running")
        self.assertEqual(json.loads(self.show("").stdout)["packs_disabled"], [], "a build with no version switches nothing off")

if __name__ == "__main__":
    unittest.main()
