"""The page's text is set in its voices' tokens (Perch step 70): a font or a
font size in pixels is a glyph's or a control's, named below, and a hairline
is --hair, never 1px. A control's height is --tap, never its 32px written
out, and a script asks whether it is on a phone with isPhone() (Perch step
69). A new rule with a pixel font, a 1px border or a 32px control fails here
by its selector, and a script with the phone's query of its own by name."""
import re
import unittest
from pathlib import Path

DASH = Path(__file__).resolve().parent.parent
SHEETS = ("page-components.css", "page-surfaces.css", "page-skin.css", "page-overrides.css")

# Glyphs drawn in a font (chevrons, the help mark, carets, counts), controls
# in their own sizes, the brand, the dialog and setup headings, the iOS rule
# that keeps a phone from zooming into a field, and the body's base.
KEPT = {
    ".help", ".modal h3", ".chev>summary::before", ".roadmap .fold", ".actbar .more>.moreb",
    ".nbtabs button", ".pane .bar.page.grouped>.subrow>.subnav.pseg>button",
    ":is(.chips,.dockline,.hscroll).chl::before,:is(.chips,.dockline,.hscroll).chr::after",
    "button.eye i", ".sect>summary::before", ".sect .sect>summary .t", ".pane .bar", ".pane .bar button",
    'html[data-theme="nostromo"]:not([data-mode="light"]) header h1',
    'html[data-mode="light"][data-theme="nostromo"] header h1', "header h1", ".setuphead h2",
    "#linux button,#git button",
    "input:not([type=checkbox]):not([type=radio]):not([type=range]):not([type=color]),textarea",
    ".clog .clhead input.clname", ".gbpickcaret", ".dsblock b", ".dsblock span",
    ":is(.dmtab,.dkview,.vmtab) details.dmline > summary.dmsum .td.lead::before",
    ".nbtabs .pcount", ".dockline .dspend", "body",
}


def rules():
    for name in SHEETS:
        text = (DASH / name).read_text()
        for m in re.finditer(r"([^{}]+)\{([^{}]*)\}", text):
            sel = " ".join(m.group(1).split()).split("*/")[-1].strip()
            yield name, sel, m.group(2)


class Tokens(unittest.TestCase):
    def test_a_pixel_font_is_a_glyphs_or_a_controls(self):
        loose = sorted({f"{n}: {sel}" for n, sel, body in rules()
                        if re.search(r"(?<![-\w])font(?:-size)?:[^;}]*\b[0-9.]+px", body) and sel not in KEPT})
        self.assertEqual(loose, [], "set these in a voice's token (--f-ui, --f-row, --f-data...), or name them in KEPT")

    def test_a_hairline_is_the_hair(self):
        ones = sorted({f"{n}: {sel}" for n, sel, body in rules()
                       if re.search(r"(?<![-\w])(?:border(?:-top|-bottom|-left|-right)?|outline):1px\b", body)})
        self.assertEqual(ones, [], "a 1px line is var(--hair)")

    def test_a_controls_height_is_the_tap(self):
        written = sorted({f"{n}: {sel}" for n, sel, body in rules()
                          if re.search(r"(?<![-\w])min-(?:height|width):32px\b", body)})
        self.assertEqual(written, [], "a control's height is var(--tap)")

    def test_a_script_asks_isphone(self):
        # The page's own listeners on the query's change are the one place
        # it is written besides isPhone itself.
        own = {"page-tabs.js", "page-boot.js"}
        asked = sorted(p.name for p in DASH.glob("*.js")
                       if p.name not in own and re.search(r"matchMedia\(\s*[\"']\(max-width:\s*900px\)", p.read_text()))
        self.assertEqual(asked, [], "ask isPhone(), never the 900px query written out")


if __name__ == "__main__":
    unittest.main()
