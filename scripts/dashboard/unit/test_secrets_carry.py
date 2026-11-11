"""The controller's secrets carried across a move on a machine of its own
(B728): the folder is root's there, so the root helper packs it on the old
home and places it on the new, where every *.env line is held to a secret's
name and a value with no shell in it, since the controller's start reads
those files as root. Run here as the test's own account against folders of
its own; a stand-in helper names them for the move module."""
import io
import os
import re
import shutil
import stat
import subprocess
import sys
import tarfile
import tempfile
import unittest
from pathlib import Path

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE.parent))
import move  # noqa: E402

TOOL = HERE.parent.parent / "secrets-carry"


def run(verb, folder, data=None):
    return subprocess.run(["bash", str(TOOL), verb], input=data, capture_output=True, timeout=60, check=False,
                          env=dict(os.environ, BB_SECRETS_DIR=str(folder)))


def tar_of(files, links=()):
    buf = io.BytesIO()
    with tarfile.open(fileobj=buf, mode="w") as t:
        for name, body in files.items():
            info = tarfile.TarInfo(name)
            info.size = len(body)
            t.addfile(info, io.BytesIO(body))
        for name, target in links:
            info = tarfile.TarInfo(name)
            info.type, info.linkname = tarfile.SYMTYPE, target
            t.addfile(info)
    return buf.getvalue()


@unittest.skipIf(os.geteuid() == 0, "as root the helper serves the machine's own folder, never a test's")
class Helper(unittest.TestCase):
    def setUp(self):
        self.d = Path(tempfile.mkdtemp())
        self.addCleanup(shutil.rmtree, self.d, True)
        self.old, self.new = self.d / "old", self.d / "new"
        (self.old / "ssh").mkdir(parents=True)
        (self.old / "install-key").mkdir()
        self.new.mkdir()
        (self.old / "tokens.env").write_text("NPM_TOKEN=npm_abc123\nexport SIGNING_SECRET=\"a passphrase, with words\"\n# a note\n")
        (self.old / "ssh" / "id_ed25519").write_text("PRIVATE\n")
        (self.old / "install-key" / "key").write_text("k" * 64)
        (self.old / "notes.txt").write_text("not a secret file\n")
        os.symlink("/etc/passwd", self.old / "link.env")

    def test_the_names_it_takes_are_the_ones_the_start_reads(self):
        boot = (HERE.parent.parent / "lib" / "boot.sh").read_text()
        want = re.search(r"^SECRET_VARS=\(([^)]*)\)", boot, re.M).group(1).split()
        got = re.search(r"^SECRET_NAMES=\(([^)]*)\)", TOOL.read_text(), re.M).group(1).split()
        self.assertEqual(got, want)

    def test_a_pack_is_the_env_files_and_the_keys_and_never_the_install_key(self):
        r = run("--can", self.old)
        self.assertEqual(r.returncode, 0, r.stderr)
        self.assertRegex(r.stdout.decode(), r"^2 files, \d+ bytes")
        r = run("pack", self.old)
        self.assertEqual(r.returncode, 0, r.stderr)
        with tarfile.open(fileobj=io.BytesIO(r.stdout)) as t:
            self.assertEqual(sorted(m.name for m in t.getmembers()), ["ssh/id_ed25519", "tokens.env"])
        # A folder with nothing to carry says so, and is no error to a caller that asked.
        self.assertEqual(run("--can", self.new).returncode, 3)

    def test_a_landing_keeps_secrets_as_plain_words_and_leaves_the_rest_out(self):
        body = (b"NPM_TOKEN=npm_abc123   # a note after it\n"
                b"export SIGNING_SECRET=\"a passphrase, with words\"\n"
                b"INSTALL_KEY='abc def'\n"
                b"PATH=/tmp/evil\n"                       # not a secret the start reads
                b"UV_PUBLISH_TOKEN=$(id > /tmp/pwned)\n"  # shell in a value
                b"INSTALL_KEY_PREVIOUS=\"a$HOME\"\n"      # expands
                b"touch /tmp/pwned\n")                    # not a NAME=value line
        r = run("land", self.new, tar_of({"tokens.env": body, "ssh/id_ed25519": b"PRIVATE\n"}))
        self.assertEqual(r.returncode, 0, r.stdout.decode() + r.stderr.decode())
        said = r.stdout.decode()
        landed = (self.new / "tokens.env").read_text()
        kept = [ln for ln in landed.splitlines() if not ln.startswith("#")]
        self.assertEqual(kept, ["NPM_TOKEN='npm_abc123'", "SIGNING_SECRET='a passphrase, with words'", "INSTALL_KEY='abc def'"])
        for word in ("sets PATH, which is not a secret", "line 5 (UV_PUBLISH_TOKEN) has shell in its value",
                     "line 6 (INSTALL_KEY_PREVIOUS) has shell", "line 7 is not a NAME=value line", "placed ssh/id_ed25519"):
            self.assertIn(word, said)
        # What root reads at the start runs nothing: sourced, it sets three words.
        out = subprocess.run(["bash", "-c", f'set -a; . "{self.new / "tokens.env"}"; echo "$NPM_TOKEN|$SIGNING_SECRET|$INSTALL_KEY|${{PATH%%:*}}"'],
                             capture_output=True, text=True, check=True).stdout.strip()
        self.assertTrue(out.startswith("npm_abc123|a passphrase, with words|abc def|"), out)
        self.assertNotIn("/tmp/evil", out)
        self.assertEqual(stat.S_IMODE((self.new / "tokens.env").stat().st_mode), 0o600)
        self.assertEqual((self.new / "ssh" / "id_ed25519").read_text(), "PRIVATE\n")

    def test_anything_but_plain_files_of_its_own_names_refuses_it_all(self):
        for what, data in (("a link", tar_of({}, links=[("evil.env", "/etc/shadow")])),
                           ("a path out", tar_of({"../../etc/cron.d/x.env": b"NPM_TOKEN=a\n"})),
                           ("another folder", tar_of({"install-key/key": b"k"})),
                           ("a name with a space", tar_of({"a b.env": b"NPM_TOKEN=a\n"})),
                           ("ssh's own config", tar_of({"ssh/config/x": b"ProxyCommand evil\n"})),
                           ("not a tar", b"not a tar at all")):
            r = run("land", self.new, data)
            self.assertNotEqual(r.returncode, 0, what)
            self.assertIn("nothing placed", r.stderr.decode(), what)
            self.assertEqual(sorted(p.name for p in self.new.iterdir()), [], what)

    def test_a_file_already_there_is_kept_beside_the_new_one_and_the_folder_s_mode_stands(self):
        (self.new / "tokens.env").write_text("NPM_TOKEN=theirs\n")
        os.chmod(self.new, 0o710)
        r = run("land", self.new, tar_of({"tokens.env": b"NPM_TOKEN=ours\n"}))
        self.assertEqual(r.returncode, 0, r.stderr)
        self.assertEqual((self.new / "tokens.env.before-move").read_text(), "NPM_TOKEN=theirs\n")
        self.assertIn("NPM_TOKEN='ours'", (self.new / "tokens.env").read_text())
        self.assertEqual(stat.S_IMODE(self.new.stat().st_mode), 0o710, "the account's way to its key folder is left as it was")


@unittest.skipIf(os.geteuid() == 0, "as root nothing is closed to the test")
class Moved(unittest.TestCase):
    """The move module with a folder it cannot read, and a stand-in for the
    helper that reads another the test can."""

    def setUp(self):
        self.d = Path(tempfile.mkdtemp())
        self.addCleanup(lambda: (os.chmod(self.d / "closed", 0o700), shutil.rmtree(self.d, True)))
        (self.d / "closed").mkdir()
        os.chmod(self.d / "closed", 0)
        self.real = self.d / "real"
        (self.real / "ssh").mkdir(parents=True)
        (self.real / "tokens.env").write_text("NPM_TOKEN=npm_abc123\n")
        (self.real / "ssh" / "id_ed25519").write_text("PRIVATE\n")
        stand = self.d / "carry"
        stand.write_text(f'#!/bin/sh\nBB_SECRETS_DIR="{self.real}" exec bash "{TOOL}" "$@"\n')
        os.chmod(stand, 0o755)
        was = (move.SECRETS, move.CARRY, os.environ.get("BB_SECRETS_CARRY"))
        self.addCleanup(lambda: (setattr(move, "SECRETS", was[0]), setattr(move, "CARRY", was[1]),
                                 os.environ.pop("BB_SECRETS_CARRY", None) if was[2] is None else os.environ.__setitem__("BB_SECRETS_CARRY", was[2])))
        move.SECRETS, move.CARRY = str(self.d / "closed"), str(stand)
        os.environ["BB_SECRETS_CARRY"] = str(stand)

    def test_a_bundle_carries_what_root_packs_and_a_landing_hands_it_to_root(self):
        self.assertTrue(move._secrets_closed())
        buf = io.BytesIO()
        with tarfile.open(fileobj=buf, mode="w") as tar:
            self.assertEqual(move._tar_carried(tar), 2)
        with tarfile.open(fileobj=io.BytesIO(buf.getvalue())) as t:
            self.assertEqual(sorted(t.getnames()), ["secrets/ssh/id_ed25519", "secrets/tokens.env"])
            t.extractall(self.d / "work", filter="data")
        # The landing's half: the bundle's secrets go to the helper, which
        # places them where it serves and says what it did.
        shutil.rmtree(self.real)
        self.real.mkdir()
        said = move._land_carried(self.d / "work" / "secrets")
        self.assertEqual(len(said), 1)
        self.assertIn("placed tokens.env (1 secret(s))", said[0])
        self.assertIn("placed ssh/id_ed25519", said[0])
        self.assertIn("NPM_TOKEN='npm_abc123'", (self.real / "tokens.env").read_text())

    def test_with_no_helper_to_run_nothing_is_asked_of_root(self):
        os.environ.pop("BB_SECRETS_CARRY")
        self.assertEqual(move._carry("--can")[0], 127, "not a machine of its own here: sudo is never run")
        self.assertEqual(move._land_carried(self.d), [])


if __name__ == "__main__":
    unittest.main()
