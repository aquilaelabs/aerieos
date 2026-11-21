"""Declared downloads for every kind of source (pack format 5). What an
entry fetches besides its own source is named in the entry (source.fetch, a
pack's install.fetch), each file held to its sha256 or to its publisher's
signature under a key the entry carries, one named for a platform fetched
on that platform alone; AerieOS fetches and checks them before anything of
the entry runs, and what runs then runs with no network, unless the entry
says in a sentence that its installer downloads the rest (source.online).
One code path in sdk.sh for a script, a tarball, a command and a
repository, proved here by whole installs from files on disk."""
import json
import os
import subprocess
import sys
import unittest

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))
import sdkstore  # noqa: E402
from sdkstore import OTHER, PLATFORM, sdkmeta  # noqa: E402

SENTENCE = "Its installer downloads the compiler's components from static.example.org."
# A machine with no unshare to cut the network with: the installer finds none.
NO_CUT = "sdk_sys_path() { [ \"$1\" != unshare ] && PATH=\"$SDK_SYS_PATH\" type -P \"$1\"; }\n"


def mock_die():
    """sdkmeta.die as a refusal a test can read: it ends the process."""
    from unittest import mock  # noqa: PLC0415
    return mock.patch.object(sdkmeta, "die", side_effect=SystemExit)


class Script(sdkstore.KitCase):
    def test_its_declared_download_is_fetched_and_checked_before_its_installer_runs(self):
        sha = self.kit()
        rc, out = self.s.sh("sdk_install kit", PATH=self.s.can_cut())
        self.assertEqual(rc, 0, out)
        self.assertIn("verified: sha256 matches what kit declares for dl/data.bin", out)
        self.assertIn("kit holds forty-two", out, "the installer found the file there, and the verify ran what it made")
        self.assertLess(out.index("verified: sha256 matches what kit declares"), out.index("kit declares its downloads: its steps run with no network"))
        # Everything of the entry that ran, ran behind the cut.
        self.assertEqual(self.s.read("kit", "ran-how").split(), ["run=yes", "then=yes", "verify=yes"])
        self.assertEqual(self.s.read("kit", ".bb-net"), "cut\n")
        # ...and what landed is written down, under the digest its installer was held to.
        head = self.receipt("kit")
        self.assertEqual((head[1], head[7]), (sha, "cut"))
        self.assertIn("its steps ran with no network", out)

    def test_one_that_answers_another_file_stops_before_anything_runs(self):
        self.kit(fetch=[{"url": self.data_url, "sha256": "0" * 64, "to": "dl/data.bin"}])
        rc, out = self.s.sh("sdk_install kit; echo went-on", PATH=self.s.can_cut())
        self.assertNotEqual(rc, 0)
        self.assertIn(f"answered a file whose sha256 is {self.data_sha}, and its manifest declares {'0' * 64}: nothing is installed", out)
        self.assertNotIn("went-on", out)
        self.assertFalse(os.path.exists(self.mark), "the installer never ran")
        self.assertFalse(os.path.exists(self.s.dir("kit")), "and nothing is left installed")

    def test_a_node_that_cannot_cut_says_so_and_the_receipt_does_too(self):
        self.kit()
        rc, out = self.s.sh(NO_CUT + "sdk_install kit")
        self.assertEqual(rc, 0, out)
        self.assertIn("this node cannot cut the network for a step", out)
        self.assertEqual(self.s.read("kit", "ran-how").split(), ["run=no", "then=no", "verify=no"])
        self.assertEqual((self.s.read("kit", ".bb-net"), self.receipt("kit")[7]), ("open\n", "open"))

    # A row whose installer is checked against nothing it carries, as most
    # shipped rows' are today.
    UNHELD = {"from": "none", "why": "its publisher states no checksum"}

    def test_a_row_that_declares_nothing_is_installed_as_it_always_was(self):
        self.kit(fetch=None, checksum=self.UNHELD, run=["sh", "-c", "mkdir -p {dir}/dl {dir}/bin; echo x > {dir}/dl/data.bin; sh {script} {dir}"])
        rc, out = self.s.sh("sdk_install kit", PATH=self.s.can_cut())
        self.assertEqual(rc, 0, out)
        self.assertEqual(self.s.read("kit", "ran-how").split(), ["run=no", "then=no", "verify=no"])
        self.assertFalse(os.path.exists(os.path.join(self.s.dir("kit"), ".bb-net")))
        self.assertFalse(os.path.exists(os.path.join(self.s.dir("kit"), ".bb-receipt")))

    def test_offline_alone_cuts_the_steps_of_a_row_that_downloads_nothing_more(self):
        self.kit(fetch=None, checksum=self.UNHELD, offline=True, run=["sh", "-c", "mkdir -p {dir}/dl; echo x > {dir}/dl/data.bin; sh {script} {dir}"])
        rc, out = self.s.sh("sdk_install kit", PATH=self.s.can_cut())
        self.assertEqual(rc, 0, out)
        self.assertEqual(self.s.read("kit", "ran-how").split(), ["run=yes", "then=yes", "verify=yes"])


class Inside(sdkstore.KitCase):
    """A declared download lands inside the pack by where it really is: a
    link the pack's repository carries at a folder's name is not written
    through, whatever `to` spells."""

    def fetch(self, to, prepare):
        d = os.path.join(self.root, "pack")
        self.outside = os.path.join(self.root, "outside")
        os.makedirs(d)
        os.makedirs(self.outside)
        prepare(d)
        plan = "\x1f".join(("fetch", self.data_url, self.data_sha, to, "", ""))
        return self.s.sh(f"sdk_fetch_declared kit {d!r} $'{plan}'\necho went-on"), d

    def test_a_link_at_a_folder_s_name_is_not_written_through(self):
        for to, prepare in (("dl/data.bin", lambda d: os.symlink(self.outside, os.path.join(d, "dl"))),
                            ("a/b/data.bin", lambda d: (os.makedirs(os.path.join(d, "a")),
                                                        os.symlink(self.outside, os.path.join(d, "a", "b")))),
                            ("dl/new/data.bin", lambda d: os.symlink("../outside", os.path.join(d, "dl"))),
                            ("gone/data.bin", lambda d: os.symlink(os.path.join(self.root, "nowhere"), os.path.join(d, "gone")))):
            with self.subTest(to=to):
                (rc, out), d = self.fetch(to, prepare)
                self.assertNotEqual(rc, 0, out)
                self.assertIn(f"kit: a declared download is kept inside the pack, and {to} is not", out)
                self.assertNotIn("went-on", out)
                self.assertEqual(os.listdir(self.outside), [], "nothing landed where the link points")
                self.assertFalse(os.path.exists(os.path.join(self.root, "nowhere")))
                self.assertEqual([n for n in os.listdir(d) if n.startswith(".bb-fetch")], [], "and nothing of it is left")
            import shutil  # noqa: PLC0415
            shutil.rmtree(os.path.join(self.root, "pack"))
            shutil.rmtree(self.outside)

    def test_a_link_or_a_folder_at_the_file_s_own_name_is_not_followed(self):
        target = os.path.join(self.root, "target")

        def a_link(d):
            os.makedirs(os.path.join(d, "dl"))
            with open(target, "w") as f:
                f.write("as it was")
            os.symlink(target, os.path.join(d, "dl", "data.bin"))
        (rc, out), d = self.fetch("dl/data.bin", a_link)
        self.assertEqual(rc, 0, out)
        with open(target) as f:
            self.assertEqual(f.read(), "as it was")
        self.assertFalse(os.path.islink(os.path.join(d, "dl", "data.bin")))
        with open(os.path.join(d, "dl", "data.bin")) as f:
            self.assertEqual(f.read(), "forty-two")

    def test_a_link_that_stays_inside_the_pack_is_taken(self):
        def inside(d):
            os.makedirs(os.path.join(d, "real"))
            os.symlink("real", os.path.join(d, "dl"))
        (rc, out), d = self.fetch("dl/data.bin", inside)
        self.assertEqual(rc, 0, out)
        self.assertTrue(os.path.isfile(os.path.join(d, "real", "data.bin")))


class Platform(sdkstore.KitCase):
    def test_one_for_another_machine_is_left_out(self):
        gone = "file://" + os.path.join(self.s.files, "not-built-for-this-machine.bin")
        self.kit(fetch=[{"url": self.data_url, "sha256": self.data_sha, "to": "dl/data.bin", "platform": PLATFORM.split("/")[0] + "/*"},
                        {"url": gone, "sha256": "1" * 64, "to": "dl/theirs.bin", "platform": OTHER}])
        rc, out = self.s.sh("sdk_install kit", PATH=self.s.can_cut())
        self.assertEqual(rc, 0, out)
        self.assertIn(f"leaving out dl/theirs.bin: it is for {OTHER}", out)
        self.assertEqual(sorted(os.listdir(os.path.join(self.s.dir("kit"), "dl"))), ["data.bin"])

    def test_a_musl_machine_takes_its_own_build_of_a_shared_file_and_not_the_glibc_one(self):
        # Two rows may share a `to` where one is glibc's and one musl's
        # (packformat.platforms_meet): a musl machine fetches its own alone,
        # and a file with no musl build is still the glibc row's.
        rows = [{"url": "https://example.com/g", "to": "tool.tgz", "platform": "linux/amd64"},
                {"url": "https://example.com/m", "to": "tool.tgz", "platform": "linux-musl/amd64"},
                {"url": "https://example.com/d", "to": "data.bin", "platform": "linux/amd64"},
                {"url": "https://example.com/a", "to": "tool.tgz", "platform": "linux/arm64"}]
        row = {"source": {"fetch": rows}}
        was = sdkmeta.AS_PLATFORM
        self.addCleanup(setattr, sdkmeta, "AS_PLATFORM", was)
        sdkmeta.AS_PLATFORM = "linux-musl/amd64"
        self.assertEqual([f["url"][-1] for f in sdkmeta.declared(row)], ["m", "d"])
        plan = [ln.split(sdkmeta.PLAN_SEP) for ln in sdkmeta.declared_plan(row)]
        self.assertEqual([(ln[0], ln[1][-1] if ln[0] == "fetch" else ln[2]) for ln in plan[1:]],
                         [("skip", "linux/amd64"), ("fetch", "m"), ("fetch", "d"), ("skip", "linux/arm64")])
        sdkmeta.AS_PLATFORM = "linux/amd64"
        self.assertEqual([f["url"][-1] for f in sdkmeta.declared(row)], ["g", "d"])

    def test_the_lookup_is_the_one_a_row_s_address_takes(self):
        system, arch = PLATFORM.split("/")
        self.assertTrue(sdkmeta.on_platform(PLATFORM) and sdkmeta.on_platform(f"{system}/*") and sdkmeta.on_platform(""))
        self.assertFalse(sdkmeta.on_platform(OTHER) or sdkmeta.on_platform(f"{system}/{'arm64' if arch == 'amd64' else 'amd64'}"))
        row = {"source": {"fetch": [{"url": "https://example.com/a", "to": "a", "platform": OTHER}, {"url": "https://example.com/b", "to": "b"},
                                    {"url": "https://example.com/c", "to": "c", "platform": PLATFORM}, "junk"]}}
        self.assertEqual([f["to"] for f in sdkmeta.declared(row)], ["b", "c"])
        # What the shell reads in one call: how the steps run, then a line a
        # download, this machine's to fetch and another's to leave out.
        self.assertEqual(sdkmeta.declared_plan({"source": {"kind": "tarball"}}), [], "an entry that declares nothing says nothing")
        self.assertEqual(sdkmeta.declared_plan({"source": {"offline": True}}), ["net\x1fcut\x1f"])
        plan = sdkmeta.declared_plan({"source": {"online": " It fetches\n the rest. ", "fetch": [
            {"url": "https://example.com/a", "sha256": "ab" * 32, "to": "a", "platform": OTHER},
            {"url": "https://example.com/b", "to": "b", "signed": {"sig": "https://example.com/b.sig", "keys": "b.asc"}}]}})
        self.assertEqual([ln.split("\x1f") for ln in plan], [["net", "online", "It fetches the rest."], ["skip", "a", OTHER],
                                                             ["fetch", "https://example.com/b", "", "b", "https://example.com/b.sig", "b.asc"]])
        # What an install would download counts this machine's alone.
        self.assertEqual(sdkmeta.download_urls({"name": "x", "source": {"kind": "git", "download": {"resolver": "approximate"}, **row["source"]}}),
                         ["https://example.com/b", "https://example.com/c"])


class Online(sdkstore.KitCase):
    def test_an_installer_that_downloads_the_rest_keeps_the_network_and_says_why(self):
        sha = self.kit(online=SENTENCE)
        rc, out = self.s.sh("sdk_install kit", PATH=self.s.can_cut())
        self.assertEqual(rc, 0, out)
        # What it declares is fetched and checked all the same, before it runs.
        self.assertIn("verified: sha256 matches what kit declares for dl/data.bin", out)
        self.assertIn("kit keeps the network for its steps, as its entry says: " + SENTENCE, out)
        self.assertNotIn("its steps run with no network", out)
        self.assertEqual(self.s.read("kit", "ran-how").split(), ["run=no", "then=no", "verify=no"], "nothing was cut, though this node could")
        self.assertEqual(self.s.read("kit", ".bb-net"), f"online\n{SENTENCE}\n")
        head = self.receipt("kit")
        self.assertEqual((head[1], head[7], head[8]), (sha, "online", SENTENCE))
        self.assertIn("its steps kept the network, as its entry says: " + SENTENCE, out, "the receipt's own words say it")


class Files(sdkstore.KitCase):
    """The small files a row carries (source.files): what a package manager
    installs by, written into the row's directory before anything of the
    row runs."""

    REQS = "kit==1.0 --hash=sha256:" + "ab" * 32 + "\n"

    def test_they_are_there_before_its_steps_run_beside_what_it_declares(self):
        self.s.row("cmd", {"kind": "command", "run": ["sh", "-c", "cat {dir}/dl/pip/requirements.txt {dir}/dl/data.bin > {dir}/read; echo run=${CUT:-no} > {dir}/ran-how"],
                           "fetch": [{"url": self.data_url, "sha256": self.data_sha, "to": "dl/data.bin"}],
                           "files": {"dl/pip/requirements.txt": self.REQS, "package.json": "{}\n"}})
        rc, out = self.s.sh("sdk_install cmd", PATH=self.s.can_cut())
        self.assertEqual(rc, 0, out)
        self.assertIn("wrote from its entry: dl/pip/requirements.txt, package.json", out)
        self.assertEqual((self.s.read("cmd", "read"), self.s.read("cmd", "package.json"), self.s.read("cmd", "ran-how")), (self.REQS + "forty-two", "{}\n", "run=yes\n"))
        # A row that carries files and says nothing of its downloads has declared nothing: it is installed as it always was.
        self.s.row("plain", {"kind": "command", "run": ["sh", "-c", "cp {dir}/notes.txt {dir}/copied; echo run=${CUT:-no} > {dir}/ran-how"], "files": {"notes.txt": "kept\n"}})
        rc, out = self.s.sh("sdk_install plain", PATH=self.s.can_cut())
        self.assertEqual((rc, self.s.read("plain", "copied"), self.s.read("plain", "ran-how")), (0, "kept\n", "run=no\n"), out)
        self.assertFalse(os.path.exists(os.path.join(self.s.dir("plain"), ".bb-net")))

    def test_a_path_outside_the_directory_or_on_a_mark_writes_nothing_and_installs_nothing(self):
        for bad in ("../escaped.txt", "/tmp/escaped.txt", ".bb-receipt", "dl/.bb-net", ".git/config"):
            self.s.row("cmd", {"kind": "command", "run": ["sh", "-c", "touch {dir}/ran"], "files": {"ok.txt": "fine\n", bad: "no\n"}})
            rc, out = self.s.sh("sdk_install cmd; echo went-on", PATH=self.s.can_cut())
            self.assertNotEqual(rc, 0, bad)
            self.assertIn("is no file inside its directory: nothing of source.files was written", out, bad)
            self.assertIn("cmd: the files its entry carries could not be written: nothing is installed", out, bad)
            self.assertNotIn("went-on", out, bad)
            self.assertFalse(os.path.exists(os.path.join(self.s.dir("cmd"), "ran")) or os.path.exists(os.path.join(self.s.dir("cmd"), "ok.txt")), bad)
        self.assertFalse(os.path.exists(os.path.join(self.s.store, "here", "escaped.txt")))

    def test_a_link_out_of_the_directory_is_not_written_through(self):
        d = os.path.join(self.root, "tree")
        os.makedirs(d)
        os.symlink(self.root, os.path.join(d, "out"))
        with mock_die() as die, self.assertRaises(SystemExit):
            sdkmeta.write_files({"name": "x", "source": {"files": {"out/escaped.txt": "no\n"}}}, d)
        self.assertIn("is no file inside its directory", die.call_args[0][0])
        self.assertFalse(os.path.exists(os.path.join(self.root, "escaped.txt")))
        self.assertEqual(sdkmeta.write_files({"name": "x", "source": {}}, d), [])


class Kinds(sdkstore.KitCase):
    """The same call in each of the other shapes."""

    def test_a_tarball_s_follow_up_steps_and_verify_run_behind_the_cut(self):
        url, sha = self.s.tarball("tool-1.0.tar.gz", {"tool-1.0/bin/tool": "#!/bin/sh\necho \"tool $(cat \"$(dirname \"$0\")/../dl/data.bin\")\"\n"})
        self.s.row("tool", {"kind": "tarball", "url": url, "strip": 1, "checksum": {"from": "pin", "version": "1.0", "sha256": sha},
                            "fetch": [{"url": self.data_url, "sha256": self.data_sha, "to": "dl/data.bin"}],
                            "then": [{"run": ["sh", "-c", "echo then=${CUT:-no} >> {dir}/ran-how"]}],
                            "verify": ["sh", "-c", "echo verify=${CUT:-no} >> {dir}/ran-how; {dir}/bin/tool"]})
        rc, out = self.s.sh("sdk_install tool", PATH=self.s.can_cut())
        self.assertEqual(rc, 0, out)
        self.assertIn("tool forty-two", out)
        self.assertEqual(self.s.read("tool", "ran-how").split(), ["then=yes", "verify=yes"])
        self.assertEqual(self.receipt("tool")[1], sha)

    def test_a_command_runs_behind_it(self):
        self.s.row("cmd", {"kind": "command", "run": ["sh", "-c", "cp {dir}/dl/data.bin {dir}/copied; echo run=${CUT:-no} > {dir}/ran-how"],
                           "fetch": [{"url": self.data_url, "sha256": self.data_sha, "to": "dl/data.bin"}]})
        rc, out = self.s.sh("sdk_install cmd", PATH=self.s.can_cut())
        self.assertEqual(rc, 0, out)
        self.assertEqual((self.s.read("cmd", "copied"), self.s.read("cmd", "ran-how")), ("forty-two", "run=yes\n"))
        self.assertEqual(self.receipt("cmd")[7], "cut")
        # One that fails behind the cut says where to look.
        self.s.sh("sdk_remove cmd")
        self.s.row("cmd", {"kind": "command", "run": ["false"], "offline": True})
        rc, out = self.s.sh("sdk_install cmd", PATH=self.s.can_cut())
        self.assertTrue(rc != 0 and "it ran with no network: what it fetches is declared in its entry" in out, out)

    def repo(self):
        """A repository on disk with one commit: (its address, the commit)."""
        d = os.path.join(self.root, "repo")
        os.makedirs(d)
        with open(os.path.join(d, "install.sh"), "w") as f:
            f.write("#!/bin/sh\nmkdir -p \"$1/bin\"\ncp \"$1/dl/data.bin\" \"$1/bin/payload\"\necho then=${CUT:-no} >> \"$1/ran-how\"\n")
        git = ["git", "-C", d, "-c", "user.name=t", "-c", "user.email=t@example.com", "-c", "init.defaultBranch=main"]
        for args in (["init", "-q"], ["add", "-A"], ["commit", "-q", "-m", "one"]):
            subprocess.run([*git, *args], check=True, capture_output=True)
        return d, subprocess.run([*git, "rev-parse", "HEAD"], check=True, capture_output=True, text=True).stdout.strip()

    def test_a_pinned_repository_s_warm_up_steps_and_verify_run_behind_it(self):
        url, commit = self.repo()
        src = {"kind": "git", "url": url, "commit": commit, "fresh_only": True, "offline": True,
               "fetch": [{"url": self.data_url, "sha256": self.data_sha, "to": "dl/data.bin"}],
               "warm": ["sh", "-c", "echo warm=${CUT:-no} >> {dir}/ran-how"], "warm_note": "warming",
               "then": [{"run": ["sh", "{dir}/install.sh", "{dir}"]}],
               "verify": ["sh", "-c", "echo verify=${CUT:-no} >> {dir}/ran-how; cat {dir}/bin/payload"]}
        self.s.row("pack", src)
        rc, out = self.s.sh("sdk_install pack", PATH=self.s.can_cut())
        self.assertEqual(rc, 0, out)
        self.assertEqual(self.s.read("pack", "ran-how").split(), ["warm=yes", "then=yes", "verify=yes"])
        head = self.receipt("pack")
        self.assertEqual((head[1], head[7]), (commit, "cut"))
        # The same repository saying its installer downloads the rest.
        self.s.sh("sdk_remove pack")
        self.s.row("pack", {**{k: v for k, v in src.items() if k != "offline"}, "online": SENTENCE})
        rc, out = self.s.sh("sdk_install pack", PATH=self.s.can_cut())
        self.assertEqual(rc, 0, out)
        self.assertEqual(self.s.read("pack", "ran-how").split(), ["warm=no", "then=no", "verify=no"])
        self.assertEqual(self.receipt("pack")[7:], ["online", SENTENCE])
        self.assertIn("its steps kept the network, as its entry says: " + SENTENCE, out)


class Shipped(sdkstore.KitCase):
    """What the implied cut does to the rows AerieOS ships. A row whose
    own download is held by a pin or by its publisher's signature runs what
    it runs with no network; the rest are installed as they were."""

    def shipped(self):
        with open(os.path.join(sdkstore.REPO, "config", "toolchains.json")) as f:
            return {r["name"]: r for r in json.load(f)["toolchains"]}

    # The shipped rows whose own download is a tarball held by a pin or by
    # its publisher's signature, with nothing run after it but its verify.
    UNPACKED = {"node": ["{dir}/bin/node", "--version"], "swift": ["{dir}/usr/bin/swift", "--version"], "go": ["{dir}/bin/go", "version"],
                "jdk": ["{dir}/bin/java", "-version"], "zig": ["{dir}/zig", "version"], "ffmpeg": ["{dir}/bin/ffmpeg", "-version"]}

    def test_the_rows_held_by_a_pin_or_a_signature_are_cut_and_each_runs_its_verify_alone(self):
        rows = self.shipped()
        for name, verify in self.UNPACKED.items():
            src = rows[name]["source"]
            self.assertEqual(sdkmeta.declared_plan(rows[name]), ["net\x1fcut\x1f"], name)
            self.assertTrue(sdkmeta.held_by_entry(rows[name]), name)
            # Nothing of it runs after its download but a look at what was unpacked.
            self.assertEqual((src["kind"], src["verify"], [k for k in ("run", "then", "warm", "fetch", "online") if k in src]),
                             ("tarball", verify, []), name)
        # A row that says online keeps the network, in its own sentence; any
        # other whose own download its entry holds, or that declares
        # downloads, is cut by that alone, its installer's run included,
        # with a line for each download it declares; and one that declares
        # nothing is installed as it always was.
        for name, r in rows.items():
            plan, online = sdkmeta.declared_plan(r), " ".join(str(r["source"].get("online") or "").split())
            declares = r["source"].get("fetch") or []
            if online:
                self.assertEqual(plan[0], f"net\x1fonline\x1f{online}", name)
            else:
                self.assertEqual(plan[:1], ["net\x1fcut\x1f"] if sdkmeta.held_by_entry(r) or declares else [], name)
            self.assertEqual([ln.split("\x1f")[0] for ln in plan[1:]], [("fetch" if sdkmeta.on_platform(f.get("platform")) else "skip") for f in declares], name)
        # A command has no download of its own to hold: what it declares is what cuts it, or its sentence keeps the network.
        self.assertEqual((sdkmeta.declared_plan(rows["language-servers"])[0], sdkmeta.held_by_entry(rows["language-servers"])), ("net\x1fcut\x1f", False))
        self.assertEqual((sdkmeta.declared_plan(rows["playwright"])[0].split("\x1f")[:2], sdkmeta.held_by_entry(rows["playwright"])), (["net", "online"], False))
        tools = rows["android-tools"]
        self.assertEqual((sdkmeta.held_by_entry(tools), tools["source"]["kind"], "online" in tools["source"]), (True, "script", False),
                         "the program that installs every Android package is itself a pinned file, unpacked with no network")

    def test_node_s_recipe_runs_its_verify_behind_the_cut(self):
        # The shipped row's own source, its address a file on disk and its
        # version not asked for; its checksum list is nodejs.org's to
        # serve, so the check of the download is stood in for.
        src = {k: v for k, v in self.shipped()["node"]["source"].items() if k != "version"}
        url, sha = self.s.tarball("node-v9.9.9-linux-x64.tar.gz", {"node-v9.9.9-linux-x64/bin/node": "#!/bin/sh\necho \"v9.9.9 cut=${CUT:-no}\"\n"})
        self.s.row("node", {**src, "url": url})
        stand_in = ("sdk_verify_download() { printf 'sha256\\t%s\\tSHASUMS256.txt, signed by its release team\\n' "
                    "\"$(sha256sum \"$2\" | cut -d' ' -f1)\" > \"$5/.bb-verified\"; }\n")
        rc, out = self.s.sh(stand_in + "sdk_install node", PATH=self.s.can_cut())
        self.assertEqual(rc, 0, out)
        self.assertIn("v9.9.9 cut=yes", out, "node --version runs with no network, and runs")
        self.assertEqual(self.s.read("node", ".bb-net"), "cut\n")
        head = self.receipt("node")
        self.assertEqual((head[1], head[7]), (sha, "cut"), "an install of it now leaves a receipt, under the digest it was held to")
        # ...and on a node that cannot cut, it installs as it did, and says so.
        self.s.sh("sdk_remove node")
        rc, out = self.s.sh(stand_in + NO_CUT + "sdk_install node")
        self.assertEqual(rc, 0, out)
        self.assertIn("v9.9.9 cut=no", out)
        self.assertEqual(self.s.read("node", ".bb-net"), "open\n")


if __name__ == "__main__":
    unittest.main()
