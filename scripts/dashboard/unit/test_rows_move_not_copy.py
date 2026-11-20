"""A shipped recipe moves what it downloaded into place; it does not copy it
inside the store.

A declared download lands in the entry's own directory on the node's
toolchain store, which is often a network share. On an NFS 4.2 export, cp
from one file of the share to another is done by the file server itself,
which then keeps both files open for a while: lint-tools' last step, which
removes its downloads, ended on "Directory not empty" on such a node (20
Nov), and the partial install could not be taken off either. A move within
the directory is a rename and copies nothing, and unpacking writes new
files as anything else does.
"""
import json
import os
import re
import unittest

TABLE = os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "..", "..", "config", "toolchains.json")
# cp or install naming a file under the entry's downloads as what it reads:
# "$dl/x", "$d"/dl/x, "$dst"/dl/x, {dir}/dl/x. A copy out to a scratch
# directory elsewhere (mktemp's) crosses filesystems and is an ordinary copy.
INSIDE = re.compile(r'(?:^|[;&|(]\s*)(?:cp|install)\s+(?:-\S+(?:\s+[0-7]{3,4})?\s+)*("?\$dl"?/|"?\$d(?:st)?"?/dl/|\{dir\}/dl/)\S+\s+("?\$d(?:st)?\b|\{dir\})')


def runs(row):
    src = row.get("source") or {}
    yield " ".join(str(w) for w in src.get("run") or [])
    for step in src.get("then") or []:
        yield " ".join(str(w) for w in step.get("run") or [])


class MoveNotCopy(unittest.TestCase):
    def test_no_shipped_recipe_copies_a_download_to_another_place_in_the_store(self):
        with open(TABLE, encoding="utf-8") as f:
            rows = json.load(f)["toolchains"]
        found = [(r["name"], m.group(0).strip()[:80]) for r in rows for text in runs(r) for m in INSIDE.finditer(text)]
        self.assertEqual(found, [], "moved (mv) or unpacked, never copied from the entry's downloads to the entry's directory")

    def test_the_pattern_reads_the_shapes_it_is_for(self):
        for bad in ('cp "$dl/yq" "$dst/yq"', 'x; cp "$d"/dl/npm/package.json "$d"/', 'cp {dir}/dl/a {dir}/bin/a',
                    'a && install -m 755 "$dst"/dl/tool "$dst"/bin/tool'):
            self.assertTrue(INSIDE.search(bad), bad)
        for fine in ('mv "$dl/yq" "$dst/yq"', 'cp "$dl/magick.AppImage" "$im"', 'cp "$1" "$dst/hadolint"',
                     'tar -xzf "$dl/ruff.tar.gz" -C "$t"', '"$d/node_modules/.bin/playwright" install chromium'):
            self.assertFalse(INSIDE.search(fine), fine)


if __name__ == "__main__":
    unittest.main()
