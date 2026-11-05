"""The map reads what the repository holds, not what git ignores: a copy of a
file left in an ignored folder answered ahead of the file itself."""
import os
import subprocess
import sys
import tempfile
import unittest

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "..", "lib"))
import codemap  # noqa: E402


class Ignored(unittest.TestCase):
    def names(self, root):
        return sorted(str(s[0] if isinstance(s, tuple) else s).replace(root + os.sep, "") for s in codemap.sources(root))

    def tree(self, d):
        os.makedirs(os.path.join(d, "lab", "run"))
        for f in ("page.js", os.path.join("lab", "walk.js"), os.path.join("lab", "run", "page.js")):
            with open(os.path.join(d, f), "w") as out:
                out.write("function a(){}\n")
        with open(os.path.join(d, "lab", ".gitignore"), "w") as out:
            out.write("run/\n")

    def test_an_ignored_folder_is_not_read(self):
        with tempfile.TemporaryDirectory() as d:
            self.tree(d)
            subprocess.run(["git", "-C", d, "init", "-q"], check=True)
            self.assertEqual(self.names(d), [os.path.join("lab", "walk.js"), "page.js"])

    def test_outside_a_repository_everything_is(self):
        with tempfile.TemporaryDirectory() as d:
            self.tree(d)
            self.assertEqual(len(self.names(d)), 3)


if __name__ == "__main__":
    unittest.main()
