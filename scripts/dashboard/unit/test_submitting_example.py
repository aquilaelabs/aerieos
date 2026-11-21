"""The submitting guide's worked tool pack (docs/submitting.md) is a manifest
an install takes as it is written there: the validator finds nothing to
fix, it is of the format and framework the catalog entry beside it says,
and its downloads read pinned, as the catalog asks of every pack it lists."""
import json
import os
import re
import sys
import unittest

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, os.path.join(HERE, ".."))
import packformat  # noqa: E402
import toolpacks  # noqa: E402

DOC = os.path.join(HERE, "..", "..", "..", "docs", "submitting.md")


class Example(unittest.TestCase):
    def test_the_worked_pack_validates_and_reads_pinned_as_its_entry_says(self):
        with open(DOC, encoding="utf-8") as f:
            text = f.read()
        blocks = [json.loads(b) for b in re.findall(r"```json\n(.*?)```", text, re.S) if b.lstrip().startswith("{")]
        pack = next(b for b in blocks if b.get("name") == "hexkit" and "install" in b)
        entry = next(json.loads(b) for b in re.findall(r"```json\n(.*?)```", re.sub(r"\n   ", "\n", text), re.S)
                     if '"commit"' in b and '"hexkit"' in b)
        clean, errors = toolpacks.validate(pack)
        self.assertEqual(errors, [])
        self.assertEqual((clean["format"], clean["framework"]), (entry["format"], entry["framework"]))
        self.assertEqual(packformat.held(clean)[0], entry["held"])
        self.assertEqual(entry["held"], "pinned")


if __name__ == "__main__":
    unittest.main()
