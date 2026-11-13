"""Everything the bundle a node fetches is made of is in the image (R246;
the audit of 13 Nov): the bundle is built from the install's own files, a
part that is not there was left out without a word, and the Dockerfile
copies nodes/ one file at a time, so a new root helper reached no node
until its own COPY line was written. Held here for every part, and said by
name at run time."""
import io
import os
import pathlib
import re
import sys
import unittest
from contextlib import redirect_stdout
from unittest import mock

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, os.path.join(HERE, ".."))
import workspace  # noqa: E402

ROOT = pathlib.Path(HERE).parents[2]


def copies():
    """(source in the tree, destination in the image) of every COPY line."""
    out = []
    for ln in (ROOT / "Dockerfile").read_text().splitlines():
        m = re.fullmatch(r"COPY (\S+) (\S+)", ln.strip())
        if m:
            out.append((m.group(1), m.group(2)))
    return out


def image_has(part):
    """Whether some COPY puts `part` at /opt/aerieos/<part>: the part
    itself, or a folder above it copied whole."""
    for src, dst in copies():
        s, d = src.rstrip("/"), dst.rstrip("/")
        if (part == s or part.startswith(s + "/")) and d + part[len(s):] == "/opt/aerieos/" + part:
            return True
    return False


class Parts(unittest.TestCase):
    def test_every_part_is_in_the_tree(self):
        for part in workspace.BUNDLE_PARTS:
            self.assertTrue((ROOT / part).exists(), f"{part} is named in BUNDLE_PARTS and is not in the tree")

    def test_every_part_is_copied_into_the_image_where_the_bundle_reads_it(self):
        self.assertTrue(image_has("scripts/lib/sdk.sh") and not image_has("nodes/not-copied"), "the check itself")
        missing = [p for p in workspace.BUNDLE_PARTS if not image_has(p)]
        self.assertEqual(missing, [], "the Dockerfile copies none of these to /opt/aerieos: a node would be sent a bundle without them")

    def test_a_part_the_install_lacks_is_said_by_name(self):
        said = io.StringIO()
        with mock.patch.object(workspace, "BUNDLE_PARTS", (*workspace.BUNDLE_PARTS, "nodes/not-in-this-image")), \
                mock.patch.object(workspace, "_bundle", {}), mock.patch.object(workspace, "_bundle_missing", set()), \
                mock.patch.object(workspace, "REPO", ROOT), redirect_stdout(said):
            first = workspace.bundle()
            workspace._bundle.clear()
            workspace.bundle()
        self.assertTrue(first.get("digest"))
        self.assertEqual(said.getvalue().count("the bundle a node fetches is missing nodes/not-in-this-image"), 1)


if __name__ == "__main__":
    unittest.main()
