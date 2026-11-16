"""aerie lint sorts every tracked file by its first line in one process
(embedded.py shebangs, R228 step 22), where it read each file's first line
twice, three processes a read: the same lists, a shell or python named on a
first line within its first 64 bytes, as `head -c 64 | head -1 | grep -E`
read it."""
import os
import shutil
import subprocess
import sys
import tempfile
import unittest

LIB = os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "..", "lib")


class Shebangs(unittest.TestCase):
    def test_a_shell_or_python_first_line_is_named_and_nothing_else(self):
        d = tempfile.mkdtemp()
        self.addCleanup(shutil.rmtree, d, True)
        files = {
            "a": "#!/usr/bin/env bash\necho\n",
            "b": "#!/bin/sh\n",
            "c": "#!/usr/bin/env python3\nprint()\n",
            "d": "#!/usr/bin/python\n",
            "e": "# not a shebang: bash\n",
            "f": "x\n#!/bin/sh\n",
            # Past the first 64 bytes the line is not read, as head -c 64 did not.
            "g": "#!" + "/x" * 40 + "/bash\n",
            "h": "#!/usr/bin/env zsh\n",
            "sp ace": "#!/bin/bash\n",
        }
        for name, text in files.items():
            with open(os.path.join(d, name), "w") as f:
                f.write(text)
        names = [os.path.join(d, n) for n in files] + [os.path.join(d, "missing")]
        out = subprocess.run([sys.executable, os.path.join(LIB, "embedded.py"), "shebangs"],
                             input="\0".join(names).encode(), capture_output=True, check=True).stdout
        parts = out.split(b"\0")[:-1]
        got = {os.path.basename(p.decode()): k.decode() for k, p in zip(parts[::2], parts[1::2])}
        self.assertEqual(got, {"a": "sh", "b": "sh", "c": "py", "d": "py", "sp ace": "sh"})


if __name__ == "__main__":
    unittest.main()
