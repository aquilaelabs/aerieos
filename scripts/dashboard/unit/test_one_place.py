"""Every setting at one scope and on one page (R294 step 3, the design's
placement rule): an install setting is declared as a field on one page's
table or drawn by one page's own code, named here, and never on two; a
space's settings and a repository's own are apart, the dials a repository
may set apart being the space's defaults. A new setting that lands in two
places, or nowhere, fails here by name."""
import re
import sys
import unittest
from pathlib import Path

DASH = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(DASH))
import prefs  # noqa: E402
import settings  # noqa: E402

# Drawn by a page's own code rather than a field table, each on the one page
# named; or never drawn, a mark of the install's own rather than a choice.
DRAWN_BY_CODE = {"offer_unvetted": "tab-debug.js", "backup_also": "tab-settings.js", "release_channel": "tab-settings.js",
                 "check_release": "tab-settings.js", "check_images": "tab-settings.js", "check_catalog": "tab-settings.js"}
NOT_DRAWN = {"debug_mode", "setup_done"}


class OnePlace(unittest.TestCase):
    def pages(self):
        return {f.name: f.read_text() for f in sorted(DASH.glob("*.js"))}

    def test_each_install_setting_is_drawn_on_one_page(self):
        pages = self.pages()
        wrong = []
        for k in settings.KEYS:
            tables = [(name, len(re.findall(r'\{key: "%s"' % re.escape(k), text))) for name, text in pages.items()]
            tables = [(n, c) for n, c in tables if c]
            if k in NOT_DRAWN:
                if tables:
                    wrong.append(f"{k}: a mark of the install's own, drawn on {tables}")
                continue
            if k in DRAWN_BY_CODE:
                page = DRAWN_BY_CODE[k]
                if tables or (k not in pages[page] and not (k.startswith("check_") and "check_${k}" in pages[page])):
                    wrong.append(f"{k}: said to be drawn by {page}'s own code, found {tables or 'not there'}")
                continue
            if len(tables) != 1 or tables[0][1] != 1:
                wrong.append(f"{k}: declared {sum(c for _, c in tables)} times, on {[n for n, _ in tables] or 'no page'}")
        self.assertEqual(wrong, [])

    def test_a_space_s_settings_and_a_repository_s_own_are_apart(self):
        group = set(prefs.GROUP_FIELDS)
        # The dials a repository may set apart are the space's defaults.
        self.assertTrue(set(prefs.OVERRIDABLE) <= group, set(prefs.OVERRIDABLE) - group)
        for d in prefs._dict_dials():
            self.assertTrue(d in group or d == "gate", d)
        # Each part of a dial made of parts is overridable by name.
        self.assertTrue({"gitpol.main", "forgepol.workflows", "gate.roadmap"} <= prefs._dial_parts())


if __name__ == "__main__":
    unittest.main()
