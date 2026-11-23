"""A CI runner's download is held to a pin: the controller reads the pin
from the one table that carries it and hands it to the node with the job
that installs a runner, and the agent fetches that address and unpacks or
makes executable nothing unless the file is the pinned bytes. It was the
newest release's asset, as the publisher's API named it that day, taken
with no digest. No network: the addresses are stood in for."""
import hashlib
import io
import json
import os
import shutil
import sys
import tarfile
import tempfile
import unittest
from unittest import mock

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, os.path.join(HERE, ".."))
import agentpkg  # noqa: E402
import nodes  # noqa: E402
import runners as store  # noqa: E402

agent = agentpkg.load("runner_held")
runners = agent.module("runners")

NODE = {"id": "n1", "name": "box", "kind": "agent", "state": "online", "arch": "x86_64",
        "services": {"runners": {"github.com-acme": {"url": "https://github.com/acme", "forge": "github"},
                                 "git.example.org-acme": {"url": "https://git.example.org/acme", "forge": "gitea"}}}}


def sha(data):
    return hashlib.sha256(data).hexdigest()


def archive():
    """A runner's archive, as small as one can be: config.sh and the service's script."""
    buf = io.BytesIO()
    with tarfile.open(fileobj=buf, mode="w:gz") as tar:
        for name, text in (("config.sh", b"#!/bin/sh\nexit 0\n"), ("bin/runsvc.sh", b"#!/bin/sh\n")):
            info = tarfile.TarInfo(name)
            info.size, info.mode = len(text), 0o755
            tar.addfile(info, io.BytesIO(text))
    return buf.getvalue()


class TheTable(unittest.TestCase):
    """runners.pins: the table as a node is handed a row of it."""

    def write(self, doc):
        d = tempfile.mkdtemp()
        self.addCleanup(shutil.rmtree, d, True)
        path = os.path.join(d, "runner-pins.json")
        with open(path, "w", encoding="utf-8") as f:
            f.write(doc if isinstance(doc, str) else json.dumps(doc))
        return path

    def row(self, name="ci", **checksum):
        return {"name": name, "source": {"kind": "tarball", "url": {"linux/amd64": "https://ci.example.org/v{version}/r-{version}.tgz",
                                                                     "linux/arm64": "https://ci.example.org/v{version}/r-arm-{version}.tgz"},
                                         "checksum": {"from": "pin", "version": "3.1.0", "sha256": {"linux/amd64": "a" * 64, "linux/arm64": "b" * 64},
                                                      **checksum}}}

    def test_a_row_is_its_version_and_each_platforms_address_and_digest(self):
        got = store.pins(self.write({"runners": [self.row()]}))
        self.assertEqual(got, {"ci": {"version": "3.1.0", "files": {
            "linux/amd64": {"url": "https://ci.example.org/v3.1.0/r-3.1.0.tgz", "sha256": "a" * 64},
            "linux/arm64": {"url": "https://ci.example.org/v3.1.0/r-arm-3.1.0.tgz", "sha256": "b" * 64}}}})

    def test_the_shipped_table_answers_for_both_kinds_of_git_host(self):
        got = store.pins()
        self.assertEqual(sorted(got), ["gitea", "github"])
        for forge, pin in got.items():
            self.assertRegex(pin["version"], r"^[0-9][0-9.]*$", forge)
            self.assertIn("linux/amd64", pin["files"], forge)
            for plat, f in pin["files"].items():
                self.assertRegex(f["sha256"], r"^[0-9a-f]{64}$", f"{forge} {plat}")
                self.assertTrue(f["url"].startswith("https://") and pin["version"] in f["url"] and "{" not in f["url"], f"{forge} {plat}: {f['url']}")

    def test_a_row_that_is_no_whole_pin_answers_nothing(self):
        cases = {"checked against its origin": self.row(**{"from": "github-asset"}),
                 "no version": self.row(version=""),
                 "a digest that is not one": self.row(sha256={"linux/amd64": "abc"}),
                 "no digests": self.row(sha256="a" * 64)}
        for what, row in cases.items():
            self.assertEqual(store.pins(self.write({"runners": [row]})), {}, what)
        # A platform whose digest is missing, or whose address is no https one, is left out of a row that has others.
        row = self.row(sha256={"linux/amd64": "a" * 64})
        self.assertEqual(sorted(store.pins(self.write({"runners": [row]}))["ci"]["files"]), ["linux/amd64"])
        row = self.row()
        row["source"]["url"]["linux/arm64"] = "http://ci.example.org/v{version}/r.tgz"
        self.assertEqual(sorted(store.pins(self.write({"runners": [row]}))["ci"]["files"]), ["linux/amd64"])

    def test_a_table_that_cannot_be_read_answers_nothing(self):
        self.assertEqual(store.pins(os.path.join(tempfile.gettempdir(), "no-such-runner-pins.json")), {})
        self.assertEqual(store.pins(self.write("{not json")), {})
        self.assertEqual(store.pins(self.write({"toolchains": []})), {})
        self.assertEqual(store.pins(self.write([1, 2])), {})


class TheJob(unittest.TestCase):
    """nodes.node_runner: the pin goes with the job, and an install of a runner nothing pins is refused."""

    PINS = {"github": {"version": "2.1.0", "files": {"linux/amd64": {"url": "https://github.com/x/r-2.1.0.tgz", "sha256": "c" * 64}}},
            "gitea": {"version": "6.0.1", "files": {"linux/amd64": {"url": "https://gitea.com/x/r-6.0.1", "sha256": "d" * 64}}}}

    def ask(self, slot, want=True, pins=PINS, token=True):
        sent = []
        with mock.patch.object(nodes, "node", return_value=json.loads(json.dumps(NODE))), mock.patch.object(nodes, "_exec"), \
             mock.patch.object(nodes, "_touch"), mock.patch.object(nodes, "job_add", side_effect=lambda *a: sent.append(a) or {"id": "j1"}):
            r = nodes.node_runner({"name": "ada"}, "n1", slot, want, token=token, pins=pins)
        return r, sent

    def test_an_install_is_handed_the_pin_of_its_kind_of_git_host(self):
        for slot, forge in (("github.com-acme", "github"), ("git.example.org-acme", "gitea")):
            r, sent = self.ask(slot)
            self.assertEqual(r, {"id": "j1"})
            spec = sent[0][3]
            self.assertEqual(spec["apply"], "runner")
            self.assertEqual(spec["config"]["pin"], self.PINS[forge])
            self.assertEqual((spec["config"]["forge"], spec["config"]["slot"], spec["config"]["want"]), (forge, slot, True))

    def test_an_install_nothing_pins_is_refused_before_a_job_is_made(self):
        for pins in (None, {}, {"gitea": self.PINS["gitea"]}):
            r, sent = self.ask("github.com-acme", pins=pins)
            self.assertEqual(sent, [])
            self.assertIn("pins no download for that git host's runner", r["error"])
            self.assertNotIn("scripts/", r["error"], "no source path in a row a person reads")
            self.assertIn("none is fetched", r["error"])

    def test_a_removal_needs_no_pin_and_carries_none(self):
        r, sent = self.ask("github.com-acme", want=False, pins=None, token=False)
        self.assertEqual(r, {"id": "j1"})
        self.assertNotIn("pin", sent[0][3]["config"])


class Job:
    def __init__(self):
        self.said = []

    def say(self, text):
        self.said.append(text)

    def flush(self):
        pass

    @property
    def text(self):
        return "".join(self.said)


class Ctl:
    """A controller that mints no token: an install ends there, after its download."""

    def __init__(self):
        self.calls = []

    def call(self, verb, body, timeout=0):
        self.calls.append((verb, body))
        return 503, {"error": "the test's controller mints none"}


class Node(runners.RunnersMixin):
    def __init__(self):
        self.state = {"user": ""}
        self.ctl = Ctl()
        self.runner_procs, self.runner_tried = {}, {}

    def drop_privileges(self, env):
        return {}

    def own_dir(self, d, who):
        pass

    def hello(self):
        pass


class Answer(io.BytesIO):
    def __enter__(self):
        return self

    def __exit__(self, *exc):
        self.close()


class TheAgent(unittest.TestCase):
    """The agent's half: the file the pin names, and nothing kept of another."""

    def setUp(self):
        self.tmp = tempfile.mkdtemp()
        self.addCleanup(shutil.rmtree, self.tmp, True)
        self.root = os.path.join(self.tmp, "runner")
        os.mkdir(self.root)
        self.web, self.asked = {}, []
        for name, value in (("RUNNER_DIR", self.root), ("RUNNER_TARBALL", ""), ("ACT_RUNNER_BIN", "")):
            was = getattr(agent, name)
            setattr(agent, name, value)
            self.addCleanup(setattr, agent, name, was)
        for target, name, stand_in in ((runners.urllib.request, "urlopen", self.urlopen), (runners.platform, "system", lambda: "Linux"),
                                       (runners.platform, "machine", lambda: "x86_64")):
            p = mock.patch.object(target, name, stand_in)
            p.start()
            self.addCleanup(p.stop)
        self.node, self.job = Node(), Job()

    def urlopen(self, url, timeout=0):
        self.asked.append(url)
        if url not in self.web:
            raise OSError(f"HTTP Error 404: {url}")
        return Answer(self.web[url])

    def pin(self, data, url="https://dl.example.org/v3.1.0/runner-3.1.0", digest=None, plat="linux/amd64"):
        self.web[url] = data
        return {"version": "3.1.0", "files": {plat: {"url": url, "sha256": digest or sha(data)}}}

    def left(self):
        return sorted(os.path.relpath(os.path.join(d, f), self.root) for d, _dirs, files in os.walk(self.root) for f in files)

    # -- which file a pin names for this machine -------------------------------
    def test_a_machine_is_keyed_as_the_table_keys_a_platform(self):
        for system, machine, want in (("Linux", "x86_64", "linux/amd64"), ("Linux", "aarch64", "linux/arm64"), ("Darwin", "arm64", "darwin/arm64"),
                                      ("Darwin", "x86_64", "darwin/amd64"), ("Linux", "armv7l", "linux/armv7l")):
            with mock.patch.object(runners.platform, "system", lambda s=system: s), mock.patch.object(runners.platform, "machine", lambda m=machine: m):
                self.assertEqual(runners.pin_platform(), want)

    def test_no_pin_or_none_for_this_machine_names_no_file_and_says_why(self):
        for pin in (None, {}, {"version": "3.1.0"}, {"files": {}}, "3.1.0"):
            named, why = runners.pinned_file(pin)
            self.assertIsNone(named)
            self.assertIn("the controller handed no pin for the runner's download, and a file held to nothing is not fetched", why)
        named, why = runners.pinned_file({"files": {"darwin/arm64": {"url": "https://x.example/r", "sha256": "a" * 64}}})
        self.assertEqual((named, why), (None, "no runner is pinned for linux/amd64: the pin names darwin/arm64"))
        for f in ({"url": "http://x.example/r", "sha256": "a" * 64}, {"url": "file:///etc/passwd", "sha256": "a" * 64},
                  {"url": "https://x.example/r", "sha256": "A" * 64}, {"url": "https://x.example/r"}):
            named, why = runners.pinned_file({"files": {"linux/amd64": f}})
            self.assertEqual((named, why), (None, "the pin names no https address with a sha256 for linux/amd64"), f)
        self.assertEqual(runners.pinned_file({"files": {"linux/amd64": {"url": "https://x.example/r", "sha256": "a" * 64}}}),
                         (("https://x.example/r", "a" * 64), ""))

    # -- the fetch --------------------------------------------------------------
    def test_the_pinned_bytes_are_kept_and_others_leave_nothing(self):
        dest = os.path.join(self.root, "file")
        self.web["https://x.example/r"] = b"the runner"
        self.assertTrue(runners.fetch_pinned("https://x.example/r", sha(b"the runner"), dest, self.job.say))
        with open(dest, "rb") as f:
            self.assertEqual(f.read(), b"the runner")
        self.assertEqual(self.left(), ["file"])
        # Another file at that address: what was there stays, and nothing of the other is kept.
        self.web["https://x.example/r"] = b"something else"
        self.assertFalse(runners.fetch_pinned("https://x.example/r", sha(b"the runner"), dest, self.job.say))
        with open(dest, "rb") as f:
            self.assertEqual(f.read(), b"the runner")
        self.assertEqual(self.left(), ["file"])
        self.assertEqual(self.job.said[-3:], [f"sha256 of what https://x.example/r answered: {sha(b'something else')}\n", f"sha256 expected: {sha(b'the runner')}\n",
                                               "refused: the download is not the file its pin names: nothing of it was kept\n"])

    def test_an_address_that_does_not_answer_leaves_nothing(self):
        dest = os.path.join(self.root, "file")
        self.assertFalse(runners.fetch_pinned("https://x.example/gone", "a" * 64, dest, self.job.say))
        self.assertEqual(self.left(), [])
        self.assertIn("download failed: https://x.example/gone", self.job.said[-1])

    def test_what_a_ci_job_left_at_the_fetching_name_is_not_written_through(self):
        dest = os.path.join(self.root, "file")
        elsewhere = os.path.join(self.tmp, "elsewhere")
        os.symlink(elsewhere, dest + ".fetching")
        self.web["https://x.example/r"] = b"the runner"
        self.assertTrue(runners.fetch_pinned("https://x.example/r", sha(b"the runner"), dest, self.job.say))
        self.assertFalse(os.path.lexists(elsewhere))
        self.assertFalse(os.path.islink(dest))

    # -- GitHub's runner: an archive ----------------------------------------------
    def test_the_archive_is_unpacked_where_it_is_the_pinned_file(self):
        data = archive()
        cfg = {"want": True, "url": "https://github.com/acme", "forge": "github", "slot": "github.com-acme", "name": "box",
               "pin": self.pin(data, "https://github.com/x/releases/download/v3.1.0/r-3.1.0.tar.gz")}
        got = self.node._apply_runner(self.job, cfg)
        self.assertEqual(got, ("failed", 69), self.job.text)          # the token, after the download
        self.assertIn("could not get a registration token", self.job.said[-1])
        self.assertEqual(self.left(), ["github.com-acme/bin/runsvc.sh", "github.com-acme/config.sh"])
        self.assertIn("downloading GitHub's runner 3.1.0, pinned: https://github.com/x/releases/download/v3.1.0/r-3.1.0.tar.gz\n", self.job.said)
        self.assertIn(f"it is the pinned file (sha256 {sha(data)})\n", self.job.said)
        self.assertEqual(self.asked, ["https://github.com/x/releases/download/v3.1.0/r-3.1.0.tar.gz"], "the pinned address, and nobody asked what is newest")

    def test_an_archive_that_is_not_the_pinned_file_unpacks_nothing_and_says_both_digests(self):
        data = archive()
        cfg = {"want": True, "url": "https://github.com/acme", "forge": "github", "slot": "github.com-acme", "name": "box",
               "pin": self.pin(data, "https://github.com/x/r.tar.gz", digest="e" * 64)}
        self.assertEqual(self.node._apply_runner(self.job, cfg), ("failed", 69))
        self.assertEqual(self.job.said[-3:], [f"sha256 of what https://github.com/x/r.tar.gz answered: {sha(data)}\n", f"sha256 expected: {'e' * 64}\n",
                                               "refused: the download is not the file its pin names: nothing of it was kept\n"])
        self.assertEqual(os.listdir(self.root), [], "not the archive, not a file of it, not the folder made for it")
        self.assertEqual(self.node.ctl.calls, [], "and no token was asked for")

    # -- the slot ---------------------------------------------------------------
    def test_a_slot_is_one_an_address_maps_to_or_nothing_is_made(self):
        """A job's slot names the folder root makes and gives to the jobs
        account: an absolute path, a dotted one or any other shape is
        refused before anything is made or asked."""
        outside = os.path.join(self.tmp, "outside")
        for slot in (outside, "/etc/cron.d", "..", ".", "../outside", "a/b", ".hidden", "-x", "Git.Example", "a--b", "a b",
                     "ends-", "ends.", "x" * 61):
            cfg = {"want": True, "url": "https://github.com/acme", "forge": "github", "slot": slot, "name": "box",
                   "pin": self.pin(archive(), "https://github.com/x/r.tar.gz")}
            with self.subTest(slot=slot):
                self.assertEqual(self.node._apply_runner(self.job, cfg), ("failed", 64))
                self.assertEqual(self.job.said[-1], "refused: that is not a runner's slot\n")
                self.assertEqual(self.node._apply_runner(self.job, dict(cfg, want=False)), ("failed", 64))
        self.assertEqual((self.asked, os.listdir(self.root), self.node.ctl.calls), ([], [], []))
        self.assertFalse(os.path.lexists(outside))
        # No slot and no address to map one from is no slot either.
        self.assertEqual(self.node._apply_runner(self.job, {"want": False}), ("failed", 64))

    def test_every_slot_an_address_maps_to_is_taken(self):
        for url in ("https://github.com/acme", "https://github.com/Acme/Some_Repo.git", "https://git.example.org:3000/a/b/",
                    "https://github.com/" + "long-organization-name/" * 4, "https://h/x.git.git", "http://10.0.0.5/r"):
            slot = runners.runner_slot(url)
            self.assertTrue(runners.slot_ok(slot), (url, slot))
            self.assertEqual(slot, nodes.runner_slot(url), "the controller's maps it the same")
        # Cut at sixty on a dash: still the slot that address maps to.
        cut = runners.runner_slot("https://github.com/" + "a" * 48 + "-bcd")
        self.assertEqual((len(cut), cut[-1]), (60, "-"))
        self.assertTrue(runners.slot_ok(cut))

    def test_an_install_handed_no_pin_fetches_nothing(self):
        cfg = {"want": True, "url": "https://github.com/acme", "forge": "github", "slot": "github.com-acme", "name": "box"}
        self.assertEqual(self.node._apply_runner(self.job, cfg), ("failed", 65))
        self.assertTrue(self.job.said[-1].startswith("refused: the controller handed no pin for the runner's download"), self.job.said)
        self.assertEqual((self.asked, os.listdir(self.root)), ([], []))

    def test_a_machine_the_pin_does_not_name_is_refused_by_name(self):
        cfg = {"want": True, "url": "https://github.com/acme", "forge": "github", "slot": "github.com-acme", "name": "box",
               "pin": self.pin(archive(), plat="linux/arm64")}
        self.assertEqual(self.node._apply_runner(self.job, cfg), ("failed", 65))
        self.assertEqual(self.job.said[-1], "refused: no runner is pinned for linux/amd64: the pin names linux/arm64\n")
        self.assertEqual((self.asked, os.listdir(self.root)), ([], []))

    def test_the_suites_stand_in_is_taken_as_it_is(self):
        tarball = os.path.join(self.tmp, "runner.tar.gz")
        with open(tarball, "wb") as f:
            f.write(archive())
        agent.RUNNER_TARBALL = tarball
        cfg = {"want": True, "url": "https://github.com/acme", "forge": "github", "slot": "github.com-acme", "name": "box"}
        self.assertEqual(self.node._apply_runner(self.job, cfg), ("failed", 69))
        self.assertIn("config.sh", os.listdir(os.path.join(self.root, "github.com-acme")))
        self.assertEqual(self.asked, [])

    # -- Gitea's and Forgejo's runner: one program ------------------------------------
    def gitea(self, **more):
        return {"want": True, "url": "https://git.example.org/acme", "forge": "gitea", "slot": "git.example.org-acme", "name": "box", **more}

    def exe(self):
        return os.path.join(self.root, "git.example.org-acme", "act_runner")

    def test_the_program_is_made_executable_where_it_is_the_pinned_file(self):
        got = self.node._apply_runner(self.job, self.gitea(pin=self.pin(b"\x7fELF the runner")))
        self.assertEqual(got, ("failed", 69), self.job.text)
        self.assertIn("could not get a registration token", self.job.said[-1])
        self.assertEqual(self.left(), ["git.example.org-acme/act_runner"])
        self.assertTrue(os.access(self.exe(), os.X_OK))
        self.assertEqual(self.asked, ["https://dl.example.org/v3.1.0/runner-3.1.0"])

    def test_a_program_that_is_not_the_pinned_file_leaves_nothing_and_says_both_digests(self):
        cfg = self.gitea(pin=self.pin(b"another program", digest="f" * 64))
        self.assertEqual(self.node._apply_runner(self.job, cfg), ("failed", 69))
        self.assertEqual(self.job.said[-3:], [f"sha256 of what https://dl.example.org/v3.1.0/runner-3.1.0 answered: {sha(b'another program')}\n",
                                               f"sha256 expected: {'f' * 64}\n",
                                               "refused: the download is not the file its pin names: nothing of it was kept\n"])
        self.assertEqual(os.listdir(self.root), [])
        self.assertEqual(self.node.ctl.calls, [])

    def test_an_install_handed_no_pin_fetches_no_program(self):
        self.assertEqual(self.node._apply_runner(self.job, self.gitea()), ("failed", 65))
        self.assertTrue(self.job.said[-1].startswith("refused: the controller handed no pin for the runner's download"))
        self.assertEqual((self.asked, os.listdir(self.root)), ([], []))

    def test_a_program_already_here_that_is_the_pinned_one_is_not_fetched_again(self):
        os.makedirs(os.path.dirname(self.exe()))
        with open(self.exe(), "wb") as f:
            f.write(b"\x7fELF the runner")
        self.assertEqual(self.node._apply_runner(self.job, self.gitea(pin=self.pin(b"\x7fELF the runner"))), ("failed", 69))
        self.assertEqual(self.asked, [])

    def test_a_program_already_here_that_is_not_the_pinned_one_is_replaced_by_it(self):
        os.makedirs(os.path.dirname(self.exe()))
        with open(self.exe(), "wb") as f:
            f.write(b"what an earlier agent fetched")
        self.assertEqual(self.node._apply_runner(self.job, self.gitea(pin=self.pin(b"\x7fELF the runner"))), ("failed", 69))
        self.assertIn("the act_runner here is not the pinned file; fetching the pinned one in its place\n", self.job.said)
        with open(self.exe(), "rb") as f:
            self.assertEqual(f.read(), b"\x7fELF the runner")
        # ...and where the pinned one cannot be had, the one here is left as it was.
        with open(self.exe(), "wb") as f:
            f.write(b"what an earlier agent fetched")
        self.assertEqual(self.node._apply_runner(self.job, self.gitea(pin=self.pin(b"not it", digest="f" * 64))), ("failed", 69))
        with open(self.exe(), "rb") as f:
            self.assertEqual(f.read(), b"what an earlier agent fetched")

    def test_a_program_already_here_goes_on_where_no_pin_is_handed(self):
        os.makedirs(os.path.dirname(self.exe()))
        with open(self.exe(), "wb") as f:
            f.write(b"what an earlier agent fetched")
        self.assertEqual(self.node._apply_runner(self.job, self.gitea()), ("failed", 69))
        self.assertIn("could not get a registration token", self.job.said[-1])
        self.assertEqual(self.asked, [], "nothing is fetched, so nothing unchecked arrives")


class NobodyIsAskedWhatIsNewest(unittest.TestCase):
    def test_the_agent_names_no_release_api_and_no_latest(self):
        for name in ("runners.py", "base.py"):
            with open(os.path.join(agentpkg.PKG, name), encoding="utf-8") as f:
                text = f.read()
            self.assertNotIn("releases/latest", text, name)
            self.assertNotIn("browser_download_url", text, name)
        with open(os.path.join(agentpkg.PKG, "runners.py"), encoding="utf-8") as f:
            text = f.read()
        self.assertEqual(text.count("urlopen("), 1, "one place fetches, and it is the one that holds the file to its pin")
        for vendor in ("api.github.com", "gitea.com"):
            self.assertNotIn(vendor, text)


if __name__ == "__main__":
    unittest.main()
