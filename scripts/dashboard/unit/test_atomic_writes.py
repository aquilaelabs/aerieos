"""Three files that two writers can reach at once (the update checks' stamps,
a space's compose file saved from the Containers page, the move token kept
from the first page) are written through statefile's atomic writers: a
reader always meets one writer's whole content, both writers succeed, and
no temporary file is left beside the file."""
import contextlib
import os
import shutil
import subprocess
import sys
import tempfile
import threading
import unittest
from pathlib import Path
from unittest import mock

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, os.path.join(HERE, ".."))
import devactions  # noqa: E402
import devapp  # noqa: E402
import move  # noqa: E402
import statefile  # noqa: E402

ROUNDS = 40

# One process stamping the same check over and over. checks.stamp's own lock
# orders the threads of one process, so the two writers of its test are two
# processes, which nothing orders.
STAMPER = """
import os, sys
os.umask(int(sys.argv[5], 8))
sys.path.insert(0, sys.argv[1])
from pathlib import Path
import checks
checks.STATE = Path(sys.argv[2])
sys.stdin.read(1)
for _ in range(int(sys.argv[4])):
    checks.stamp("release", int(sys.argv[3]))
"""


class Watcher:
    """A reader of one file for as long as its block runs: every read is one
    of the contents allowed, or the file not there yet."""

    def __init__(self, path, allowed, binary=False):
        self.path, self.allowed, self.binary = Path(path), set(allowed), binary
        self.bad, self.reads, self._stop = [], 0, threading.Event()
        self._thread = threading.Thread(target=self._run, daemon=True)

    def _run(self):
        while not self._stop.is_set():
            try:
                got = self.path.read_bytes() if self.binary else self.path.read_text(encoding="utf-8")
            except FileNotFoundError:
                continue
            self.reads += 1
            if got not in self.allowed and len(self.bad) < 3:
                self.bad.append(got[:80])

    def __enter__(self):
        self._thread.start()
        return self

    def __exit__(self, *exc):
        self._stop.set()
        self._thread.join()


def both(first, second):
    """Two calls started together, each on its own thread: their answers."""
    gate, out = threading.Barrier(2), [None, None]

    def go(n, fn):
        gate.wait()
        out[n] = fn()
    threads = [threading.Thread(target=go, args=(n, fn)) for n, fn in enumerate((first, second))]
    for t in threads:
        t.start()
    for t in threads:
        t.join()
    return out


class AtomicWrites(unittest.TestCase):
    def setUp(self):
        self.tmp = Path(tempfile.mkdtemp())
        self.addCleanup(shutil.rmtree, self.tmp, True)

    def only(self, name):
        self.assertEqual(sorted(p.name for p in self.tmp.iterdir()), [name], "nothing is left beside the file")

    def test_the_update_checks_stamps(self):
        f = self.tmp / "checks.json"
        allowed = {'{"release": 111}', '{"release": 222}'}
        # The file's mode is what its writer's umask gives a new file: 0644
        # in the container, 0600 on a machine of the controller's own.
        for umask, mode in (("022", 0o644), ("077", 0o600)):
            with self.subTest(umask=umask), Watcher(f, allowed) as seen:
                procs = [subprocess.Popen([sys.executable, "-c", STAMPER, os.path.join(HERE, ".."), str(self.tmp), at,
                                           str(ROUNDS * 3), umask], stdin=subprocess.PIPE, stderr=subprocess.PIPE)
                         for at in ("111", "222")]
                for p in procs:
                    p.stdin.write(b"g")
                    p.stdin.flush()
                ends = [(p.wait(), p.stderr.read().decode()[-400:]) for p in procs]
                for p in procs:
                    p.stdin.close()
                    p.stderr.close()
                self.assertEqual([code for code, _ in ends], [0, 0], ends)
                self.assertIn(f.read_text(), allowed)
                self.assertEqual(f.stat().st_mode & 0o7777, mode)
                self.only("checks.json")
            self.assertEqual(seen.bad, [])

    def test_a_compose_file_saved_from_the_page(self):
        cf = self.tmp / "docker-compose.yml"
        texts = [f"services:\n  app:\n    image: {name}\n" + f"# {name}\n" * 20000 for name in ("one", "two")]
        cf.write_text("services: {}\n", encoding="utf-8")
        os.chmod(cf, 0o640)
        allowed = {"services: {}\n", *texts}
        with mock.patch.object(devapp, "compose_file", lambda p, i: cf), \
                mock.patch.object(devapp, "is_file_source", lambda p, i: False), \
                mock.patch.object(devapp, "_instance_node", lambda p, i: ""), \
                mock.patch.object(devapp, "on_node", lambda nid: contextlib.nullcontext()), \
                mock.patch.object(devapp, "_compose", lambda *a: ["true"]), \
                mock.patch.object(devapp, "_run", lambda *a, **k: {"code": 0, "out": ""}), \
                mock.patch.object(devapp, "_bump", lambda: None), \
                Watcher(cf, allowed) as seen:
            for _ in range(ROUNDS):
                got = both(lambda: devactions.set_compose("alpha", devapp.MAIN, texts[0]),
                           lambda: devactions.set_compose("alpha", devapp.MAIN, texts[1]))
                self.assertEqual([r.get("error") for r in got], [None, None])
                self.assertIn(cf.read_text(encoding="utf-8"), texts)
                self.assertEqual(cf.stat().st_mode & 0o7777, 0o640, "the file keeps its mode")
                self.only("docker-compose.yml")
        self.assertEqual(seen.bad, [])

    def test_the_move_token_kept_from_the_first_page(self):
        tokens = ["A" * 43, "B" * 43]
        blobs = [b"sealed:" + t.encode() * 2000 for t in tokens]
        f = self.tmp / move.SETUP_TOKEN_FILE
        with mock.patch.object(move, "STATE", self.tmp), \
                mock.patch.object(move, "seal", lambda b: b"sealed:" + b * 2000), \
                Watcher(f, blobs, binary=True) as seen:
            self.addCleanup(move._setup_token.update, tok="")
            for _ in range(ROUNDS):
                both(lambda: move.keep_setup_token(tokens[0]), lambda: move.keep_setup_token(tokens[1]))
                self.assertIn(f.read_bytes(), blobs)
                self.assertEqual(f.stat().st_mode & 0o7777, 0o600)
                self.only(move.SETUP_TOKEN_FILE)
        self.assertEqual(seen.bad, [])


class WriteBytes(unittest.TestCase):
    def test_bytes_land_whole_with_their_mode(self):
        tmp = Path(tempfile.mkdtemp())
        self.addCleanup(shutil.rmtree, tmp, True)
        f = tmp / "sub" / "blob.bin"
        statefile.write_bytes(f, b"\x00\xff one", mode=0o600)
        self.assertEqual(f.read_bytes(), b"\x00\xff one")
        self.assertEqual(f.stat().st_mode & 0o7777, 0o600)
        statefile.write_bytes(f, b"two")
        self.assertEqual(f.read_bytes(), b"two")
        self.assertEqual(f.stat().st_mode & 0o7777, 0o644)
        self.assertEqual([p.name for p in f.parent.iterdir()], ["blob.bin"])


if __name__ == "__main__":
    unittest.main()
