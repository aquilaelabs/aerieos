"""Removing a toolchain whose file a running program still holds open sets
what is left aside and frees the name: on a share the server keeps such a
file under a hidden name, rm ended on a directory that was not empty, and an
update that began with the remove left the toolchain gone and not installed."""
import os
import shutil
import subprocess
import tempfile
import unittest

REPO = os.path.normpath(os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "..", ".."))

# rm as a share behaves: a file named .fuse_hidden* or stuck* is held and
# does not go, so its directories do not either.
RM = r"""#!/bin/bash
rc=0
for a in "$@"; do
    case "$a" in -*) continue ;; esac
    [ -e "$a" ] || continue
    if [ -d "$a" ]; then
        find "$a" -depth \( -type f -o -type l \) ! -name '.fuse_hidden*' ! -name 'stuck*' -delete
        find "$a" -depth -type d -empty -delete
        [ ! -e "$a" ] || { echo "rm: cannot remove '$a/lib': Directory not empty" >&2; rc=1; }
    else
        /bin/rm -f "$a"
    fi
done
exit $rc
"""


class Held(unittest.TestCase):
    def setUp(self):
        self.root = tempfile.mkdtemp()
        self.addCleanup(shutil.rmtree, self.root, True)
        self.bin = os.path.join(self.root, "bin")
        os.makedirs(self.bin)
        with open(os.path.join(self.bin, "rm"), "w") as f:
            f.write(RM)
        os.chmod(os.path.join(self.bin, "rm"), 0o755)
        self.store = os.path.join(self.root, "store")
        self.jdk = os.path.join(self.store, "jdk")
        os.makedirs(os.path.join(self.jdk, "lib"))
        os.makedirs(os.path.join(self.jdk, "bin"))
        for rel in ("bin/java", "lib/libjvm.so", "release"):
            open(os.path.join(self.jdk, rel), "w").close()

    def sh(self, script, share=True):
        path = (self.bin + ":" if share else "") + "/usr/bin:/bin"
        return subprocess.run(["bash", "-c", f'. "{REPO}/scripts/lib/common.sh"; . "{REPO}/scripts/lib/sdk.sh"; {script}'],
                              capture_output=True, text=True, env={**os.environ, "PATH": path})

    def test_a_file_still_held_open_is_set_aside_and_the_name_is_free(self):
        open(os.path.join(self.jdk, "lib", ".fuse_hidden00253706000302b9"), "w").close()
        r = self.sh(f'sdk_rm_tree "{self.jdk}"')
        self.assertEqual(r.returncode, 0, r.stderr)
        self.assertFalse(os.path.exists(self.jdk), "the name is free for the install")
        aside = os.listdir(os.path.join(self.store, ".gone"))
        self.assertEqual(len(aside), 1)
        self.assertTrue(aside[0].startswith("jdk."))
        self.assertTrue(os.path.exists(os.path.join(self.store, ".gone", aside[0], "lib", ".fuse_hidden00253706000302b9")))
        self.assertIn("still running has a file of it open", r.stdout + r.stderr)

    def test_anything_else_left_is_a_failure_as_before(self):
        open(os.path.join(self.jdk, "lib", "stuck.jar"), "w").close()
        r = self.sh(f'sdk_rm_tree "{self.jdk}"')
        self.assertNotEqual(r.returncode, 0)
        self.assertIn("could not remove", r.stderr + r.stdout)
        self.assertTrue(os.path.isdir(self.jdk))
        self.assertFalse(os.path.exists(os.path.join(self.store, ".gone")))

    def test_an_ordinary_remove_goes_whole_and_clears_what_was_set_aside(self):
        os.makedirs(os.path.join(self.store, ".gone", "jdk.1795100000", "lib"))
        r = self.sh(f'sdk_rm_tree "{self.jdk}"', share=False)
        self.assertEqual(r.returncode, 0, r.stderr)
        self.assertEqual(os.listdir(self.store), [], "the toolchain and what an earlier remove set aside are gone")


if __name__ == "__main__":
    unittest.main()
