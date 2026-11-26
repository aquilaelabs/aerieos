"""Every time the page shows goes through fmtTime (page-state.js), so a
person's own time zone, or the one their browser picked, reaches all of them
(R294 step 8): ten places formatted a date themselves and showed it in the
device's zone whatever was picked."""
import re
import unittest
from pathlib import Path

DASH = Path(__file__).resolve().parent.parent
# fmtTime itself, and the one stamp written into a note's text, which names
# the zone it was written in explicitly.
OWN = {"page-state.js"}
STAMP = re.compile(r"toLocaleDateString\(\"en-GB\", \{[^}]*timeZone: z")
DATE_FORMAT = re.compile(r"\.toLocale(?:Date|Time)String\(|new Date\([^()]*(?:\([^()]*\))?[^()]*\)\.toLocaleString\(")


class OneWay(unittest.TestCase):
    def test_no_page_script_formats_a_time_itself(self):
        found = []
        for f in sorted(DASH.glob("*.js")):
            if f.name in OWN:
                continue
            for n, line in enumerate(f.read_text().splitlines(), 1):
                if DATE_FORMAT.search(line) and not STAMP.search(line):
                    found.append(f"{f.name}:{n}: {line.strip()[:100]}")
        self.assertEqual(found, [], "a time shown goes through fmtTime(ms, opts)")


if __name__ == "__main__":
    unittest.main()
