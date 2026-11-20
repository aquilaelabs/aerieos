"""A pinned download (pack format 5): a row's source.checksum may carry the
version and the sha256 of the exact file, so the row itself, held by the
signed catalog or the signed release, says what its download is. A pinned
row installs that version with nobody asked what is newest, its file is
held to the pin and refused with both digests when it is another, a machine
the pin names no digest for is told so, and what `aerie toolchains check`
and `update` have on offer for it is the pin."""
import os
import shutil
import sys
import tempfile
import unittest
from unittest import mock

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))
import catalogrows  # noqa: E402
import packformat  # noqa: E402
import sdkstore  # noqa: E402
from sdkstore import OTHER, PLATFORM, sdkmeta  # noqa: E402

NOWHERE = "https://nowhere.invalid/VERSION"
GO = "#!/bin/sh\necho \"go version {v} linux/amd64\"\n"


class Reads(unittest.TestCase):
    """sdkmeta's half: what a pinned row resolves to and is checked against."""

    def row(self, **pin):
        return {"name": "go", "source": {"kind": "tarball", "url": {PLATFORM: "https://example.com/dl/{version}.tar.gz"},
                                         "version": {"resolver": "text", "url": NOWHERE},
                                         "checksum": {"from": "pin", "version": "go1.99.0", "sha256": {PLATFORM: "ab" * 32}, **pin}}}

    def setUp(self):
        # A pinned row asks nobody: any fetch is a failure of the test.
        asked = mock.patch.multiple(sdkmeta, get=mock.Mock(side_effect=AssertionError("the network was asked")),
                                    final_url=mock.Mock(side_effect=AssertionError("the network was asked")))
        asked.start()
        self.addCleanup(asked.stop)

    def test_it_resolves_to_the_pinned_version_with_nobody_asked(self):
        self.assertEqual(sdkmeta.resolve(self.row()), ("go1.99.0", "https://example.com/dl/go1.99.0.tar.gz"))
        # One file for every platform, and a download with no version in its address.
        row = self.row(sha256="cd" * 32)
        del row["source"]["checksum"]["version"]
        row["source"]["url"] = "https://example.com/dl/tool.tar.gz"
        self.assertEqual(sdkmeta.resolve(row), ("", "https://example.com/dl/tool.tar.gz"))
        self.assertEqual(sdkmeta.checksum(row, "https://example.com/dl/tool.tar.gz", ""), ("sha256", "cd" * 32, "the pin its entry carries"))

    def test_its_download_is_held_to_the_digest_for_this_machine(self):
        self.assertEqual(sdkmeta.checksum(self.row(), "https://example.com/dl/go1.99.0.tar.gz", "go1.99.0"),
                         ("sha256", "ab" * 32, "the pin its entry carries"))
        # A wildcard names every architecture of a system, as source.url's does.
        wild = self.row(sha256={PLATFORM.split("/")[0] + "/*": "ef" * 32})
        self.assertEqual(sdkmeta.checksum(wild, "https://example.com/x", "")[1], "ef" * 32)

    def test_a_pin_with_no_digest_for_this_machine_is_refused_with_that_said(self):
        row = self.row(sha256={OTHER: "ab" * 32})
        for ask in (lambda: sdkmeta.resolve(row), lambda: sdkmeta.checksum(row, "https://example.com/x", "go1.99.0")):
            with mock.patch.object(sdkmeta, "die", side_effect=SystemExit) as die, self.assertRaises(SystemExit):
                ask()
            self.assertEqual(die.call_args[0][0], f"go: the row offers no pinned download for {PLATFORM}")

    def test_what_it_has_on_offer_is_the_pin_and_a_git_source_s_is_its_commit(self):
        self.assertEqual(sdkmeta.offered(self.row()), ("go1.99.0", "ab" * 32))
        self.assertEqual(sdkmeta.offered({"name": "kit", "source": {"kind": "git", "url": "https://example.com/kit", "commit": "c" * 40}}), ("c" * 8, ""))
        self.assertIsNone(sdkmeta.offered({"name": "go", "source": {"kind": "tarball", "checksum": {"from": "go-json"}}}))
        self.assertIsNone(sdkmeta.offered({"name": "flutter", "source": {"kind": "git", "url": "https://example.com/f", "branch": "stable"}}))

    def test_what_it_would_download_is_the_pinned_file(self):
        row = self.row()
        # A dry run of the vendor's would name today's release, not the pin's.
        row["source"]["download"] = {"resolver": "command-urls", "run": ["false"], "match": "x"}
        self.assertEqual(sdkmeta.download_urls(row), ["https://example.com/dl/go1.99.0.tar.gz"])


class Shape(unittest.TestCase):
    """What a pin may say, held where the catalog's row is taken."""

    def test_a_well_formed_pin_is_taken(self):
        for ck in ({"from": "pin", "version": "v22.11.0", "sha256": {"linux/amd64": "ab" * 32, "linux/arm64": "cd" * 32}},
                   {"from": "pin", "sha256": "ab" * 32},
                   {"from": "pin", "version": "1.2.3+build.4", "sha256": {"linux/*": "ab" * 32, "linux-musl/amd64": "cd" * 32, "darwin/arm64": "ef" * 32}}):
            self.assertEqual(packformat.pin_refused(ck), "", ck)

    def test_a_malformed_one_is_refused_and_says_which_part(self):
        good = {"from": "pin", "version": "1.2.3", "sha256": {"linux/amd64": "ab" * 32}}
        for change, said in (({"sha256": "abc"}, "not 64 hex digits"), ({"sha256": "AB" * 32}, "not 64 hex digits"),
                             ({"sha256": {"linux/amd64": "xyz"}}, "sha256 for linux/amd64 is not 64 hex digits"),
                             ({"sha256": {"plan9/amd64": "ab" * 32}}, "plan9/amd64, which is no platform"),
                             ({"sha256": {}}, "or one per platform"), ({"sha256": None}, "or one per platform"),
                             ({"sha256": ["ab" * 32]}, "or one per platform"),
                             ({"version": "1.2.3 beta"}, "is not a version"), ({"version": 7}, "is not a version"),
                             ({"version": "x" * 65}, "is not a version"), ({"url": "https://example.com/x"}, "its pin names url")):
            self.assertIn(said, packformat.pin_refused({**good, **change}), change)

    def test_the_catalog_s_row_is_held_to_it(self):
        self.assertIn("pin", catalogrows.CHECKSUMS)
        shipped = {"name": "go", "probe": "go", "label": "Go", "about": "The Go toolchain.", "platforms": ["linux/amd64"], "layout": {},
                   "source": {"kind": "tarball", "url": "https://example.com/{version}.tar.gz", "checksum": {"from": "go-json"}}}
        newer = {**shipped, "rev": 2, "source": {**shipped["source"], "checksum": {"from": "pin", "version": "go1.99.0", "sha256": {"linux/amd64": "ab" * 32}}}}
        self.assertEqual(catalogrows.checked(newer, shipped), (newer, ""))
        bad = {**newer, "source": {**newer["source"], "checksum": {"from": "pin", "version": "go1.99.0", "sha256": {"linux/amd64": "nope"}}}}
        got, why = catalogrows.checked(bad, shipped)
        self.assertIsNone(got)
        self.assertIn("its pin's sha256 for linux/amd64 is not 64 hex digits", why)


class Installs(unittest.TestCase):
    """The whole install, from a catalog of made-up rows and files on disk."""

    def setUp(self):
        self.root = tempfile.mkdtemp()
        self.addCleanup(shutil.rmtree, self.root, True)
        self.s = sdkstore.Store(self.root)

    def go(self, version="go1.99.0", sha=None, plat=PLATFORM):
        url, real = self.s.tarball(f"{version}.tar.gz", {"go/bin/go": GO.format(v=version)})
        self.s.row("go", {"kind": "tarball", "strip": 1, "fresh_only": True, "url": "file://" + self.s.files + "/{version}.tar.gz",
                          "version": {"resolver": "text", "url": NOWHERE},
                          "checksum": {"from": "pin", "version": version, "sha256": {plat: sha or real}},
                          "verify": ["{dir}/bin/go", "version"]}, layout={"bin": ["bin"], "env": {}, "tool": "bin/go"})
        return url, real

    def test_a_pinned_tarball_installs_and_says_it_was_held_to_its_pin(self):
        _, sha = self.go()
        rc, out = self.s.sh("sdk_install go; sdk_status_local")
        self.assertEqual(rc, 0, out)
        self.assertIn("installing go go1.99.0 into", out)
        self.assertIn("verified: sha256 matches the pin its entry carries", out)
        self.assertIn("go version go1.99.0", out, "and its verify ran")
        # A row that declares nothing beside its own download is cut because
        # that download is held, and its job says that, not that it declares.
        self.assertIn("go's download is held to what its entry carries", out)
        self.assertNotIn("go declares its downloads", out)
        self.assertRegex(out, rf"receipt: \d+ files, \d+ bytes, from {sha[:12]}, [0-9a-f]{{12}} over them all")
        self.assertEqual(self.s.read("go", ".bb-verified"), f"sha256\t{sha}\tthe pin its entry carries\n")
        self.assertIn("; checked: sha256 matched the pin its entry carries", out, "the status line reads the same record")

    def test_a_file_that_is_not_the_pinned_one_is_refused_and_nothing_is_left(self):
        _, real = self.go(sha="0" * 64)
        rc, out = self.s.sh("sdk_install go; echo went-on")
        self.assertNotEqual(rc, 0)
        self.assertIn(f"go's download is not what the pin its entry carries says it is (sha256 {real}, expected {'0' * 64}): nothing was installed", out)
        self.assertNotIn("went-on", out)
        self.assertFalse(os.path.exists(self.s.dir("go")), "nothing is left installed")
        self.assertEqual([n for n in os.listdir(os.path.dirname(self.s.dir("go"))) if n.startswith(".bb-installing")], [])

    def test_a_machine_the_pin_names_no_digest_for_is_told_so(self):
        self.go(plat=OTHER)
        rc, out = self.s.sh("sdk_install go; echo went-on")
        self.assertNotEqual(rc, 0)
        self.assertIn(f"go: the row offers no pinned download for {PLATFORM}", out)
        self.assertNotIn("went-on", out)
        self.assertFalse(os.path.exists(self.s.dir("go")))

    def test_a_plan_names_the_pinned_version_and_asks_nobody(self):
        self.go()
        rc, out, err = self.s.meta("resolve", "go")
        self.assertEqual((rc, out), (0, f"go1.99.0\tfile://{self.s.files}/go1.99.0.tar.gz\n"), err)

    def curl_refused(self):
        """A curl ahead of the real one on PATH that says it was called."""
        d = os.path.join(self.root, "bin")
        os.makedirs(d, exist_ok=True)
        with open(os.path.join(d, "curl"), "w") as f:
            f.write(f"#!/bin/sh\necho called >> {self.root}/curl-called\nexit 22\n")
        os.chmod(os.path.join(d, "curl"), 0o755)
        return d + os.pathsep + os.environ.get("PATH", "/usr/bin:/bin")

    def test_a_check_offers_the_pin_and_never_the_vendor_s_latest(self):
        self.go()
        rc, out = self.s.sh("sdk_install go")
        self.assertEqual(rc, 0, out)
        rc, out = self.s.sh("sdk_check_one go", PATH=self.curl_refused())
        self.assertEqual(rc, 0, out)
        self.assertEqual(out.rstrip("\n").split("\t")[:4], ["go", "go1.99.0", "go1.99.0", "current"])
        self.assertFalse(os.path.exists(os.path.join(self.root, "curl-called")), "the vendor was not asked what is newest")
        # The pin moves in the entry: that is the update on offer.
        self.go("go1.100.0")
        rc, out = self.s.sh("sdk_check_one go", PATH=self.curl_refused())
        self.assertEqual(out.rstrip("\n").split("\t")[:4], ["go", "go1.99.0", "go1.100.0", "update"], out)
        # ...and a rebuilt file under the same version is one too, by its digest.
        self.go("go1.99.0", sha="1" * 64)
        rc, out = self.s.sh("sdk_check_one go", PATH=self.curl_refused())
        self.assertEqual(out.rstrip("\n").split("\t")[:4], ["go", "go1.99.0", "go1.99.0", "update"], out)
        self.assertFalse(os.path.exists(os.path.join(self.root, "curl-called")))
        # What is installed, with nobody asked, is as it was.
        rc, out = self.s.sh("sdk_versions go")
        self.assertEqual(out, "go\tgo1.99.0\t-\tlocal\n")

    def test_an_update_installs_what_the_entry_pins(self):
        self.go()
        rc, out = self.s.sh("sdk_install go")
        self.assertEqual(rc, 0, out)
        _, sha = self.go("go1.100.0")
        rc, out = self.s.sh("sdk_update go")
        self.assertEqual(rc, 0, out)
        self.assertIn("updating go to what its entry pins", out)
        self.assertIn("go version go1.100.0", out)
        self.assertEqual(self.s.read("go", ".bb-verified"), f"sha256\t{sha}\tthe pin its entry carries\n")
        # One not installed has nothing to update, as before.
        self.s.sh("sdk_remove go")
        rc, out = self.s.sh("sdk_update go")
        self.assertTrue(rc != 0 and "go is not installed" in out, out)

    def test_what_a_pinned_row_runs_is_cut_by_the_pin_alone_and_online_is_the_way_out(self):
        url, sha = self.s.tarball("tool-1.0.tar.gz", {"tool-1.0/bin/tool": "#!/bin/sh\necho tool one\n"})
        src = {"kind": "tarball", "url": url, "strip": 1, "checksum": {"from": "pin", "version": "1.0", "sha256": sha},
               "then": [{"run": ["sh", "-c", "echo then=${CUT:-no} >> {dir}/ran-how"]}],
               "verify": ["sh", "-c", "echo verify=${CUT:-no} >> {dir}/ran-how; {dir}/bin/tool"]}
        how = lambda: (self.s.read("tool", "ran-how").split(),  # noqa: E731
                       self.s.read("tool", ".bb-net") if os.path.exists(os.path.join(self.s.dir("tool"), ".bb-net")) else None)
        # No offline said: the pin is the declaration.
        self.s.row("tool", src)
        rc, out = self.s.sh("sdk_install tool", PATH=self.s.can_cut())
        self.assertEqual(rc, 0, out)
        self.assertEqual(how(), (["then=yes", "verify=yes"], "cut\n"))
        head = self.s.read("tool", ".bb-receipt").splitlines()[0].split("\t")
        self.assertEqual((head[1], head[7]), (sha, "cut"), "and what landed is written down under the pin's digest")
        # offline said as well means what it meant.
        self.s.sh("sdk_remove tool")
        self.s.row("tool", {**src, "offline": True})
        rc, out = self.s.sh("sdk_install tool", PATH=self.s.can_cut())
        self.assertEqual((rc, how()), (0, (["then=yes", "verify=yes"], "cut\n")), out)
        # Its installer downloads the rest: the one way to keep the network.
        self.s.sh("sdk_remove tool")
        self.s.row("tool", {**src, "online": "Its first run downloads its plugins from plugins.example.org."})
        rc, out = self.s.sh("sdk_install tool", PATH=self.s.can_cut())
        self.assertEqual((rc, how()), (0, (["then=no", "verify=no"], "online\nIts first run downloads its plugins from plugins.example.org.\n")), out)
        # A row checked against nothing its entry carries says nothing of
        # the kind, and is installed as it always was.
        self.s.sh("sdk_remove tool")
        self.s.row("tool", {**src, "checksum": {"from": "none", "why": "its publisher states no checksum"}})
        rc, out = self.s.sh("sdk_install tool", PATH=self.s.can_cut())
        self.assertEqual((rc, how()), (0, (["then=no", "verify=no"], None)), out)
        self.assertFalse(os.path.exists(os.path.join(self.s.dir("tool"), ".bb-receipt")))

    def test_a_pinned_installer_is_fetched_at_its_version_and_held_before_it_runs(self):
        text = "#!/bin/sh\nmkdir -p \"$1/bin\"\nprintf '#!/bin/sh\\necho kit %s\\n' \"$2\" > \"$1/bin/kit\"\nchmod +x \"$1/bin/kit\"\n"
        _, sha = self.s.file("kit-install-2.5.sh", text)
        src = {"kind": "script", "url": "file://" + self.s.files + "/kit-install-{version}.sh", "run": ["sh", "{script}", "{dir}", "{version}"],
               "checksum": {"from": "pin", "version": "2.5", "sha256": sha}, "verify": ["{dir}/bin/kit"]}
        self.s.row("kit", src)
        rc, out = self.s.sh("sdk_install kit")
        self.assertEqual(rc, 0, out)
        self.assertIn("kit 2.5", out)
        self.assertEqual(self.s.read("kit", ".bb-verified"), f"sha256\t{sha}\tthe pin its entry carries\n")
        # Another file at that address is never run.
        self.s.sh("sdk_remove kit")
        self.s.file("kit-install-2.5.sh", text + "touch \"$1/ran\"\n")
        rc, out = self.s.sh("sdk_install kit")
        self.assertNotEqual(rc, 0)
        self.assertIn("is not what the pin its entry carries says it is", out)
        self.assertFalse(os.path.exists(self.s.dir("kit")))


if __name__ == "__main__":
    unittest.main()
