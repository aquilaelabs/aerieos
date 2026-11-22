"""A toolchain's folder with no tool in it is an install that did not finish,
and the two status views say so where they listed it as installed (a JDK left
as lib/ alone by an update that stopped, java missing a line above it)."""
import os
import shutil
import subprocess
import tempfile
import unittest

REPO = os.path.normpath(os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "..", ".."))


class Unfinished(unittest.TestCase):
    def setUp(self):
        self.root = tempfile.mkdtemp()
        self.addCleanup(shutil.rmtree, self.root, True)

    def sh(self, script):
        return subprocess.run(["bash", "-c", f'. "{REPO}/scripts/lib/common.sh"; . "{REPO}/scripts/lib/sdk.sh"; {script}'],
                              capture_output=True, text=True,
                              env={**os.environ, "PATH": "/usr/bin:/bin", "SDK_ROOT": self.root, "BB_SCRIPTS": f"{REPO}/scripts",
                                   "BB_LIB": f"{REPO}/scripts/lib", "BB_TOOLCHAINS_OFF": ""})

    def put(self, *parts):
        p = os.path.join(self.root, *parts)
        os.makedirs(os.path.dirname(p), exist_ok=True)
        with open(p, "w") as f:
            f.write("x")

    def test_a_folder_without_its_tool_is_named_with_the_tool_it_lacks(self):
        self.put("jdk", "lib", "modules")                      # what the stopped update left
        self.put("go", "bin", "go")                            # whole
        self.put("flutter", "bin", "internal", "x")            # half of it
        os.makedirs(os.path.join(self.root, "zig"))            # empty: not installed at all, and not this
        got = dict(line.split("\t") for line in self.sh(f'sdk_unfinished "{self.root}"').stdout.split("\n") if line)
        self.assertEqual(got, {"jdk": "bin/java", "flutter": "bin/flutter"})

    def test_a_layout_its_recipe_fills_in_is_not_this_ones_to_judge(self):
        # playwright's layout names `needs`, not a tool: its recipe fills the
        # folder in, so a folder without the module is not called unfinished.
        self.put("playwright", "browsers", "x")
        self.assertEqual(self.sh(f'sdk_unfinished "{self.root}"').stdout.strip(), "")

    def test_the_status_says_it_and_how_to_clear_it(self):
        # The status reads this machine's scope under the store, so the
        # folders go where it looks.
        scope = os.path.relpath(self.sh("sdk_root").stdout.strip(), self.root)
        self.put(scope, "jdk", "lib", "modules")
        self.put(scope, "go", "bin", "go")
        out = self.sh("sdk_status").stdout
        jdk = next((line for line in out.split("\n") if line.strip().startswith("jdk ")), "")
        self.assertIn("not installed", jdk)
        self.assertIn("holds no bin/java", jdk)
        self.assertIn("aerie toolchains install jdk", jdk)
        go = next((line for line in out.split("\n") if line.strip().startswith("go ")), "")
        self.assertIn(os.path.join(self.root, scope, "go"), go)
        self.assertNotIn("not installed", go)


if __name__ == "__main__":
    unittest.main()
