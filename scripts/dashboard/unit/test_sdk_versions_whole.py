"""`aerie toolchains versions` lists every row, whatever one probe says.

It is what a node's agent reports as the versions installed there (the
agent's toolchains.sdk_versions). On a machine with no Android SDK the
first versioned Android row's probe (a find on a folder that is not there,
under pipefail) ended the list after two rows, and every other version on
that node's Library came from the census's summary instead: Go as its whole
banner, Rust as "present", Swift as the first 40 characters of its own,
bracket open."""
import os
import subprocess
import tempfile
import sys
import unittest

HERE = os.path.dirname(os.path.abspath(__file__))
REPO = os.path.normpath(os.path.join(HERE, "..", "..", ".."))
sys.path.insert(0, os.path.join(HERE, ".."))
import toolchains  # noqa: E402


class Whole(unittest.TestCase):
    def test_a_machine_with_no_android_sdk_lists_every_row(self):
        with tempfile.TemporaryDirectory() as store:
            env = dict(os.environ, SDK_ROOT=store, ANDROID_HOME=os.path.join(store, "none"),
                       ANDROID_SDK_ROOT=os.path.join(store, "none"))
            p = subprocess.run(["bash", os.path.join(REPO, "scripts", "aerie"), "toolchains", "versions"],
                               capture_output=True, text=True, timeout=120, check=False, env=env, cwd="/")
        self.assertEqual(p.returncode, 0, p.stderr[-600:])
        names = [line.split("\t")[0] for line in p.stdout.splitlines() if line.strip()]
        for want in ("jdk", "android-tools", "android:cmake", "go", "node", "rust", "swift", "zig"):
            self.assertIn(want, names, f"every row is listed, {want} among them: {names}")
        self.assertGreater(names.index("swift"), names.index("android:cmake"))

    def test_the_census_summary_where_the_list_has_none_is_a_version_and_no_banner(self):
        for said, want in (("Swift version 6.4.2 (swift-6.4.2-RELEASE", "6.4.2"),
                           ("go version go1.27.4 linux/amd64", "1.27.4"),
                           ("v26.13.1", "v26.13.1"), ("21.0.13", "21.0.13"),
                           ("present", "present"), ("", ""), (None, "")):
            self.assertEqual(toolchains._summary_version(said), want, said)


if __name__ == "__main__":
    unittest.main()
