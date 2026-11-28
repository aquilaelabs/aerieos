"""A recipe's system packages reach the machine whole: the agent read
the first 64 and dropped the rest without a word, and Playwright with
WebKit's libraries is past that on apt, so WebKit installed and could not
launch. Every package the shipped playwright recipe names is asked about,
and a list past the cap stops at the cap, not at 64.

What a recipe names is handed to root's package manager, so each name is
held to one shape before anything is asked of it or installed, the names
follow a `--`, and the catalog they are read from is root's own copy of the
bundle, never the copy in the store the jobs account writes."""
import json
import os
import tempfile
import types
import unittest
from unittest import mock

HERE = os.path.dirname(os.path.abspath(__file__))
import agentpkg  # noqa: E402
agent = agentpkg.load("aerieos_agent_sysdeps")
CATALOG = os.path.join(HERE, "..", "..", "..", "config", "toolchains.json")


class SysdepsTest(unittest.TestCase):
    def test_the_playwright_recipe_is_read_whole(self):
        cat = json.load(open(CATALOG))
        apt = next(p for p in cat["toolchains"] if p["name"] == "playwright")["system"]["apt"]
        self.assertGreater(len(apt), 64, "the recipe carries WebKit's libraries too")
        self.assertLessEqual(len(apt), agent.SYSDEPS_MAX)
        # A query that finds nothing installed: every entry comes back,
        # the first alternative of each where the repositories cannot say.
        agent.pkg_available = lambda fam, name: True
        missing, other = agent.sysdeps_missing(cat, "playwright", "apt", ["false"])
        self.assertIsNone(other)
        self.assertEqual(len(missing), len(apt))
        self.assertIn("libgtk-4-1", missing)
        self.assertIn("libx264-165", missing)

    def test_a_list_past_the_cap_stops_there(self):
        names = [f"pkg{i}" for i in range(agent.SYSDEPS_MAX + 20)]
        cat = {"toolchains": [{"name": "big", "system": {"apt": names}}]}
        missing, _ = agent.sysdeps_missing(cat, "big", "apt", ["false"])
        self.assertEqual(len(missing), agent.SYSDEPS_MAX)

    def test_apt_waits_for_the_lock(self):
        """Another apt holding the dpkg lock failed the install at
        once; apt is told to wait for it."""
        agent._have = lambda b: b == agent.DPKG_BIN
        fam, _, install = agent.pkg_backend()
        self.assertEqual(fam, "apt")
        self.assertIn("DPkg::Lock::Timeout=300", install)
        self.assertLess(install.index("DPkg::Lock::Timeout=300"), install.index("install"))


class Names(unittest.TestCase):
    # A trailing + is apt's word for install, and the end of real names.
    GOOD = ["libgtk-4-1", "libstdc++6", "gcc-c++-12", "python3.12", "libc6:i386", "ca_certs", "0ad", "X11", "g++", "gcc-c++", "pkg+"]
    BAD = ["-y", "--allow-unauthenticated", "pkg-", "../x", "/tmp/x.deb", "./x.rpm", "https://x.example/x.rpm",
           "a b", "a;b", "$(id)", "", "+x", ".x", "a/b", "a=1.0", "a*", "a" * 81]

    def test_one_shape_for_a_package_s_name(self):
        for n in [*self.GOOD, "a" * 80]:
            self.assertTrue(agent.pkg_name_ok("apt", n), n)
        for n in self.BAD:
            self.assertFalse(agent.pkg_name_ok("apt", n), n)

    def test_portage_s_category_and_name_and_none_of_its_files(self):
        for n in ("dev-libs/icu", "media-fonts/dejavu", "icu"):
            self.assertTrue(agent.pkg_name_ok("emerge", n), n)
        for n in ("dev-libs/icu/x", "/dev-libs/icu", "dev-libs/-icu", "../icu", "dev-libs/..", "x/evil.ebuild", "evil.tbz2",
                  "x/evil.gpkg.tar", "-icu"):
            self.assertFalse(agent.pkg_name_ok("emerge", n), n)

    def cat(self, names):
        return {"toolchains": [{"name": "r", "system": {"apt": names}}]}

    def test_a_name_of_another_shape_is_asked_of_nothing(self):
        asked = []

        def run(argv, **kw):
            asked.append(argv)
            return types.SimpleNamespace(returncode=1, stdout="", stderr="")
        tc = agent.module("toolchains")
        cat = self.cat(["libgood", "--allow-unauthenticated", "libnew|-o", "liba|libb"])
        with mock.patch.object(tc.subprocess, "run", run), mock.patch.object(tc, "_have", lambda b: True):
            missing, _ = agent.sysdeps_missing(cat, "r", "apt", ["dpkg", "-s"])
        self.assertEqual(missing, ["libgood", "liba"])
        self.assertEqual(agent.sysdeps_refused(cat, "r", "apt"), ["--allow-unauthenticated", "libnew|-o"])
        for argv in asked:
            self.assertEqual(argv[-2], "--", argv)
            self.assertTrue(agent.pkg_name_ok("apt", argv[-1]), argv)

    def test_the_names_follow_two_dashes_and_one_bad_name_installs_none(self):
        work = agent.module("work")
        ran, said = [], []
        job = types.SimpleNamespace(say=said.append)

        def run(argv, **kw):
            ran.append(argv)
            return types.SimpleNamespace(returncode=0, stdout="", stderr="")
        a = object.__new__(agent.Agent)
        with mock.patch.object(work.subprocess, "run", run):
            self.assertTrue(a._install_system(job, "r", "apt", ["apt-get", "install", "-y"], ["liba", "libb"]))
            self.assertFalse(a._install_system(job, "r", "apt", ["apt-get", "install", "-y"], ["liba", "-o", "libb"]))
        self.assertEqual(ran, [["apt-get", "install", "-y", "--", "liba", "libb"]])
        self.assertIn("refused: r's recipe names a system package that is not a package's name", said[-1])
        self.assertEqual(said[-1].count("\n"), 1, "one line")

    def test_a_recipe_with_a_bad_name_has_none_of_its_packages_installed(self):
        work = agent.module("work")
        said = []
        job = types.SimpleNamespace(say=said.append)
        a = object.__new__(agent.Agent)
        a.administers = lambda: True
        a._install_system = mock.Mock(side_effect=AssertionError("installed something"))
        with mock.patch.object(work, "root_catalog", lambda into: self.cat(["libgood", "pkg-"])), \
                mock.patch.object(work, "pkg_backend", lambda: ("apt", ["false"], ["apt-get", "install"])):
            self.assertFalse(a._system_deps(job, "r", "/store/.bb/x"))
        self.assertIn("'pkg-'", said[-1])

    def test_root_reads_the_catalog_from_its_own_copy_of_the_bundle(self):
        tc = agent.module("toolchains")
        with tempfile.TemporaryDirectory() as tmp:
            store, rooted = os.path.join(tmp, "store"), os.path.join(tmp, "root", "current")
            for d, names in ((store, ["planted"]), (rooted, ["signed"])):
                os.makedirs(os.path.join(d, "config"))
                with open(os.path.join(d, "config", "toolchains.json"), "w") as f:
                    json.dump(self.cat(names), f)
            with mock.patch.object(tc, "ROOT_BUNDLE_DIR", os.path.join(tmp, "root")):
                with mock.patch.object(tc.os, "geteuid", lambda: 0):
                    self.assertEqual(tc.root_catalog(store), self.cat(["signed"]))
                with mock.patch.object(tc.os, "geteuid", lambda: 1000):
                    self.assertEqual(tc.root_catalog(store), self.cat(["planted"]))


if __name__ == "__main__":
    unittest.main()
