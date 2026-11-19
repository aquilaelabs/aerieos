"""Root's copy of a bundle is kept while a session entered under it still
runs: its coding agent runs every hook from that folder by its path. Kept by
count alone (the newest three), a session open across three updates of its
controller lost the folder, each hook then failed as a program that could
not be run, and the session went on with no gate and no refused commands."""
import os
import tempfile
import unittest
from unittest import mock
import agentpkg  # noqa: E402

agent = agentpkg.load("aerieos_agent")
ws = agent.module("workspace")


class Stale(unittest.TestCase):
    def setUp(self):
        self.root = tempfile.mkdtemp()

    def bundle(self, name, at):
        d = os.path.join(self.root, name)
        os.makedirs(os.path.join(d, "scripts"))
        os.utime(d, (at, at))
        return d

    def five(self):
        for i, name in enumerate(("a", "b", "c", "d", "e")):
            self.bundle(name, 1000 * (i + 1))           # a at 1000 ... e (current) at 5000
        os.symlink("e", os.path.join(self.root, "current"))

    def test_with_no_session_running_the_newest_three_stay(self):
        self.five()
        self.assertEqual(ws.stale_bundles(self.root, "e", None, ()), ["a", "b"])

    def test_a_bundle_a_running_session_was_entered_under_stays(self):
        self.five()
        # Entered at 1500: under a, which b replaced at 2000. Everything since stays.
        self.assertEqual(ws.stale_bundles(self.root, "e", 1500, ()), [])
        # Entered at 2900, under b: a went out at 2000, well before it.
        self.assertEqual(ws.stale_bundles(self.root, "e", 2900, ()), ["a"])
        # Entered a moment after b arrived: its hooks were written a moment
        # before that, perhaps under a, which stays.
        self.assertEqual(ws.stale_bundles(self.root, "e", 2000 + 60, ()), [])

    def test_a_bundle_a_process_names_stays(self):
        self.five()
        self.assertEqual(ws.stale_bundles(self.root, "e", None, {"a"}), ["b"])

    def test_no_more_than_the_most_are_kept_whatever_runs(self):
        for i in range(ws.BUNDLES_MOST + 5):
            self.bundle(f"b{i:03d}", 1000 + i)
        got = ws.stale_bundles(self.root, f"b{ws.BUNDLES_MOST + 4:03d}", 1, ())
        self.assertEqual(got, [f"b{i:03d}" for i in range(5)], "the oldest go first")


class Sessions(unittest.TestCase):
    def test_the_oldest_session_and_the_bundles_named_are_read_from_proc(self):
        proc = tempfile.mkdtemp()
        hz = os.sysconf("SC_CLK_TCK")
        with open(os.path.join(proc, "stat"), "w") as f:
            f.write("cpu 1 2 3\nbtime 1000000\n")

        def process(pid, argv, ticks):
            os.makedirs(os.path.join(proc, str(pid)))
            with open(os.path.join(proc, str(pid), "cmdline"), "w") as f:
                f.write("\0".join(argv) + "\0")
            with open(os.path.join(proc, str(pid), "stat"), "w") as f:
                f.write(f"{pid} (python3 (x)) S " + " ".join(["0"] * 18) + f" {ticks} 0 0\n")
        process(10, ["/usr/bin/python3", "-I", "/usr/local/sbin/bb-session", "enter", "--project", "hello"], 500 * hz)
        process(11, ["/usr/bin/python3", "-I", "/usr/local/sbin/bb-session", "enter", "--project", "web"], 200 * hz)
        process(12, ["/usr/bin/python3", "-I", "/usr/local/sbin/bb-session", "tty", "x"], 5 * hz)
        process(13, ["bash", "/usr/local/lib/builderbot/bundle/abc123/scripts/dashboard/bb-tty", "sh:1:hello"], 900 * hz)
        os.makedirs(os.path.join(proc, "self"))
        oldest, named = ws.sessions_from(proc, "/usr/local/lib/builderbot/bundle")
        self.assertEqual(oldest, 1000200)
        self.assertEqual(named, {"abc123"})

    def test_a_new_bundle_spares_the_one_a_running_session_uses(self):
        root = tempfile.mkdtemp()
        import io
        import tarfile
        tar_path = os.path.join(root, "b.tar")
        with tarfile.open(tar_path, "w") as tar:
            info = tarfile.TarInfo("scripts/aerie")
            info.size = 2
            tar.addfile(info, io.BytesIO(b"#!"))
        bundles = os.path.join(root, "bundle")
        for i, name in enumerate(("a", "b", "c")):
            os.makedirs(os.path.join(bundles, name, "scripts"))
            os.utime(os.path.join(bundles, name), (1000 * (i + 1), 1000 * (i + 1)))
        os.symlink("c", os.path.join(bundles, "current"))
        said = []
        with mock.patch.object(ws, "ROOT_BUNDLE_DIR", bundles), mock.patch.object(ws.os, "chown"), \
                mock.patch.object(ws, "sessions_from", return_value=(1500, set())):
            ws.WorkspaceMixin._keep_root_bundle(tar_path, "d", said.append)
        self.assertEqual(said, [])
        self.assertEqual(sorted(d for d in os.listdir(bundles) if d != "current"), ["a", "b", "c", "d"],
                         "a session entered under a still runs: a stays, where the count dropped it")
        self.assertEqual(os.readlink(os.path.join(bundles, "current")), "d")
        with mock.patch.object(ws, "ROOT_BUNDLE_DIR", bundles), mock.patch.object(ws.os, "chown"), \
                mock.patch.object(ws, "sessions_from", return_value=(None, set())):
            ws.WorkspaceMixin._keep_root_bundle(tar_path, "d", said.append)
        self.assertEqual(sorted(d for d in os.listdir(bundles) if d != "current"), ["b", "c", "d"],
                         "with no session running it goes")


if __name__ == "__main__":
    unittest.main()
