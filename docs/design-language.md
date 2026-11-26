# The design language

What this space looks like, in one place. Written by AerieOS's Design view from the notebook, so edit it there, or edit here and say so in the notebook. Every surface follows it; a change to the look is a change to this file first.

It governs the dashboard (scripts/dashboard: index.html and the scripts beside it), which the companion app mirrors.

## Color

Color comes only from these tokens, named once in the stylesheet. The app starts on Default; a theme picker, where the app has one, offers the themes by name, and every theme names the same tokens:

### Default (dark, the default)

| token | value | for |
|---|---|---|
| `--bg` | `#172136` | the page |
| `--panel` | `#24314b` | a raised box: a card, a pane, a modal |
| `--ink` | `#edf4ff` | the text, and text on a filled accent |
| `--dim` | `#b2c2db` | secondary text and field labels |
| `--line` | `#455e89` | hairlines and borders, 1px |
| `--accent` | `#00c1fd` | the one color that means this is the one: the active tab, the primary button, a link |
| `--warn` | `#d29922` | a warning, the amber marks, and the reason under a control a feature switched off for the install holds dead |
| `--bad` | `#f07178` | an error, a destructive verb |
| `--note` | `#37a5fb` | the second color: a link in words, the chosen view in a group's row, an info note; a hue apart from the accent |

Its light half, the same tokens under the mode switch:

| token | value |
|---|---|
| `--bg` | `#dde5f2` |
| `--panel` | `#fbfdff` |
| `--ink` | `#18212e` |
| `--dim` | `#4c596d` |
| `--line` | `#adbfd9` |
| `--accent` | `#005ed2` |
| `--warn` | `#996200` |
| `--bad` | `#c3131b` |
| `--note` | `#0065be` |

### Abyss (dark)

| token | value | for |
|---|---|---|
| `--bg` | `#152428` | the page |
| `--panel` | `#22353a` | a raised box: a card, a pane, a modal |
| `--ink` | `#e7f7f9` | the text, and text on a filled accent |
| `--dim` | `#adc6ca` | secondary text and field labels |
| `--line` | `#3f646e` | hairlines and borders, 1px |
| `--accent` | `#00d3e4` | the one color that means this is the one: the active tab, the primary button, a link |
| `--warn` | `#d7ab4c` | a warning, the amber marks, and the reason under a control a feature switched off for the install holds dead |
| `--bad` | `#ef6a63` | an error, a destructive verb |
| `--note` | `#eb69df` | the second color: a link in words, the chosen view in a group's row, an info note; a hue apart from the accent |

Its light half, the same tokens under the mode switch:

| token | value |
|---|---|
| `--bg` | `#dde7e8` |
| `--panel` | `#fafdfe` |
| `--ink` | `#1b2223` |
| `--dim` | `#4e5b5c` |
| `--line` | `#abc3c8` |
| `--accent` | `#00717c` |
| `--warn` | `#906700` |
| `--bad` | `#b53433` |
| `--note` | `#b804a7` |

### Carbon (dark)

| token | value | for |
|---|---|---|
| `--bg` | `#212127` | the page |
| `--panel` | `#313138` | a raised box: a card, a pane, a modal |
| `--ink` | `#f3f3f5` | the text, and text on a filled accent |
| `--dim` | `#c0c0c8` | secondary text and field labels |
| `--line` | `#5c5c69` | hairlines and borders, 1px |
| `--accent` | `#ff6a6b` | the one color that means this is the one: the active tab, the primary button, a link |
| `--warn` | `#d9a441` | a warning, the amber marks, and the reason under a control a feature switched off for the install holds dead |
| `--bad` | `#ff6b6b` | an error, a destructive verb |
| `--note` | `#00e2cd` | the second color: a link in words, the chosen view in a group's row, an info note; a hue apart from the accent |

Its light half, the same tokens under the mode switch:

| token | value |
|---|---|
| `--bg` | `#e4e4eb` |
| `--panel` | `#fdfdfe` |
| `--ink` | `#202021` |
| `--dim` | `#57575c` |
| `--line` | `#bdbcc7` |
| `--accent` | `#ca002b` |
| `--warn` | `#905e00` |
| `--bad` | `#bb2933` |
| `--note` | `#007368` |

### Ember (dark)

| token | value | for |
|---|---|---|
| `--bg` | `#281f1a` | the page |
| `--panel` | `#3a2f28` | a raised box: a card, a pane, a modal |
| `--ink` | `#fdf1e5` | the text, and text on a filled accent |
| `--dim` | `#d0bdac` | secondary text and field labels |
| `--line` | `#705940` | hairlines and borders, 1px |
| `--accent` | `#ff7f08` | the one color that means this is the one: the active tab, the primary button, a link |
| `--warn` | `#e8bb50` | a warning, the amber marks, and the reason under a control a feature switched off for the install holds dead |
| `--bad` | `#ef5f52` | an error, a destructive verb |
| `--note` | `#00dee8` | the second color: a link in words, the chosen view in a group's row, an info note; a hue apart from the accent |

Its light half, the same tokens under the mode switch:

| token | value |
|---|---|
| `--bg` | `#eae3de` |
| `--panel` | `#fefcfa` |
| `--ink` | `#251f1a` |
| `--dim` | `#60564d` |
| `--line` | `#cabbab` |
| `--accent` | `#ab4500` |
| `--warn` | `#8b6100` |
| `--bad` | `#ba2c25` |
| `--note` | `#007177` |

### Ice (dark)

| token | value | for |
|---|---|---|
| `--bg` | `#1a2329` | the page |
| `--panel` | `#27333c` | a raised box: a card, a pane, a modal |
| `--ink` | `#ebf5fd` | the text, and text on a filled accent |
| `--dim` | `#b4c4cb` | secondary text and field labels |
| `--line` | `#486175` | hairlines and borders, 1px |
| `--accent` | `#00cffb` | the one color that means this is the one: the active tab, the primary button, a link |
| `--warn` | `#d3ab52` | a warning, the amber marks, and the reason under a control a feature switched off for the install holds dead |
| `--bad` | `#ee6a68` | an error, a destructive verb |
| `--note` | `#a685ff` | the second color: a link in words, the chosen view in a group's row, an info note; a hue apart from the accent |

Its light half, the same tokens under the mode switch:

| token | value |
|---|---|
| `--bg` | `#dee6ea` |
| `--panel` | `#fafdfe` |
| `--ink` | `#1d2125` |
| `--dim` | `#515a5d` |
| `--line` | `#b1c0cd` |
| `--accent` | `#006e8c` |
| `--warn` | `#886200` |
| `--bad` | `#b43439` |
| `--note` | `#6538e5` |

### Moss (dark)

| token | value | for |
|---|---|---|
| `--bg` | `#192520` | the page |
| `--panel` | `#26362a` | a raised box: a card, a pane, a modal |
| `--ink` | `#edf7ed` | the text, and text on a filled accent |
| `--dim` | `#b6c6b9` | secondary text and field labels |
| `--line` | `#496552` | hairlines and borders, 1px |
| `--accent` | `#00de7e` | the one color that means this is the one: the active tab, the primary button, a link |
| `--warn` | `#d6ad4e` | a warning, the amber marks, and the reason under a control a feature switched off for the install holds dead |
| `--bad` | `#e8695f` | an error, a destructive verb |
| `--note` | `#ad87ff` | the second color: a link in words, the chosen view in a group's row, an info note; a hue apart from the accent |

Its light half, the same tokens under the mode switch:

| token | value |
|---|---|
| `--bg` | `#dee7e3` |
| `--panel` | `#fbfefc` |
| `--ink` | `#1d221d` |
| `--dim` | `#525b54` |
| `--line` | `#b2c3b6` |
| `--accent` | `#00743d` |
| `--warn` | `#8e6800` |
| `--bad` | `#b33833` |
| `--note` | `#7137e4` |

### Nocturne (dark)

| token | value | for |
|---|---|---|
| `--bg` | `#202030` | the page |
| `--panel` | `#2f2f45` | a raised box: a card, a pane, a modal |
| `--ink` | `#f3f2ff` | the text, and text on a filled accent |
| `--dim` | `#bfbce0` | secondary text and field labels |
| `--line` | `#585886` | hairlines and borders, 1px |
| `--accent` | `#a386ff` | the one color that means this is the one: the active tab, the primary button, a link |
| `--warn` | `#e0b24d` | a warning, the amber marks, and the reason under a control a feature switched off for the install holds dead |
| `--bad` | `#f2637b` | an error, a destructive verb |
| `--note` | `#00e5b2` | the second color: a link in words, the chosen view in a group's row, an info note; a hue apart from the accent |

Its light half, the same tokens under the mode switch:

| token | value |
|---|---|
| `--bg` | `#e2e4ed` |
| `--panel` | `#fcfcfe` |
| `--ink` | `#201f28` |
| `--dim` | `#575669` |
| `--line` | `#babbd8` |
| `--accent` | `#7339e0` |
| `--warn` | `#916600` |
| `--bad` | `#b72b4c` |
| `--note` | `#007253` |

### Nostromo (dark)

| token | value | for |
|---|---|---|
| `--bg` | `#1d2228` | the page |
| `--panel` | `#29333c` | a raised box: a card, a pane, a modal |
| `--ink` | `#ecf5fd` | the text, and text on a filled accent |
| `--dim` | `#b4c3d2` | secondary text and field labels |
| `--line` | `#50606e` | hairlines and borders, 1px |
| `--accent` | `#f6a900` | the one color that means this is the one: the active tab, the primary button, a link |
| `--warn` | `#e0913a` | a warning, the amber marks, and the reason under a control a feature switched off for the install holds dead |
| `--bad` | `#ff5f45` | an error, a destructive verb |
| `--note` | `#3da5f9` | the second color: a link in words, the chosen view in a group's row, an info note; a hue apart from the accent |

Its light half, the same tokens under the mode switch:

| token | value |
|---|---|
| `--bg` | `#e3e6de` |
| `--panel` | `#fdfdfa` |
| `--ink` | `#1e2123` |
| `--dim` | `#54595c` |
| `--line` | `#bbbfb5` |
| `--accent` | `#ba3900` |
| `--warn` | `#8b6100` |
| `--bad` | `#a8002a` |
| `--note` | `#327500` |

Nostromo differs from the default in:

- Shape, as the rule corners says:
-   This scheme squares all three corner tokens in its dark half; its light half is rounded like every other scheme (the operator, 16 Oct). The pills and the dots stay round, as everywhere.
- Motion: as the design's own rules say.

#### Rules of Nostromo's own

##### nostromo/textures

Applies to: scripts/dashboard/static/nostromo, scripts/dashboard/index.html; texture, hull, svg, decal

This scheme is the ship itself, a half for each of its interiors (the operator, 16 Oct), and the only one with drawn graphics: hand-written SVG under `static/nostromo`, served by the page's allow-list, each one's opacity baked into its file.

The dark half is the metal hallways: cold blue-black steel and silver, the lamps' amber as the accent, copper-rust for a warning and cold blue for a note. Behind the page, on body::before, the deck grating (`grate.svg`), a bulkhead's chamfered octagon frame at the foot (`bulkhead.svg`), two amber lamp glows up in the ceiling, a cold blue haze down the corridor and the dark closing in at the edges. The header is a steel ceiling with a sheen, the pipe runs and their amber lamp across its middle at a desk (`pipes.svg`), between the search and the controls and never under the brand or the search, and a steel rail along its foot. The rail is a steel column lit as the ceiling is, with a steel rail down its edge, and the group on show is a lamp: its bar glowing amber over a wash of the same; on a phone the bar along the foot is the same steel with its rail along its top, the group on show in amber. Buttons are brushed metal with a cold top highlight, the rail's items excepted, which are one surface; the title is stencil in amber; the tab in front glows like a lamp. The search is a recessed readout with a terminal's scanlines, lit amber when it has the keys; the tiles are readouts on the same glass, each figure glowing faintly in its own color as a phosphor does; the cards' heads are steel plates lit along their tops. The dock is a hatch: its edge is a hazard stripe, amber and black. The panes' bars and a document's ground are smoked glass at seven tenths, so the deck shows through them; a terminal keeps its own solid ground.

The light half is the white corridors: cool gray-white walls and panels, the hazard marking's red-orange as the accent and filled as itself, rounded corners, large chamfered wall panels behind the page (`panels.svg`), one wall panel's nested-octagon relief at the page's foot (`relief.svg`), the ceiling's vent grilles and light panels across the header's middle between the search and the controls (`vents.svg`) and buttons with a lit top edge. The rail is a white wall panel with a pressed seam down its edge, its items one surface and the group on show tinted with the accent; the search is pressed into the wall; the tiles and the cards' heads are pale panels lit along their tops; and the dock's edge is the door's red and white hazard stripe.

Each half's swatch shows its interior: the dark one a strip of silver pipe with an amber lamp over the deck grating, the light one a pale panel with the door's red and white stripe along its top. No pattern is ever drawn across a tall scrolling surface's own box (bug #57): the textures are on the page's layer, one viewport, and the scanlines only on the search and the tiles, each a few lines tall.

##### nostromo/corners

Applies to: scripts/dashboard/index.html; corner, radius, square

This scheme squares all three corner tokens in its dark half; its light half is rounded like every other scheme (the operator, 16 Oct). The pills and the dots stay round, as everywhere.

### Plum (dark)

| token | value | for |
|---|---|---|
| `--bg` | `#271d2e` | the page |
| `--panel` | `#382c41` | a raised box: a card, a pane, a modal |
| `--ink` | `#fbefff` | the text, and text on a filled accent |
| `--dim` | `#cdb8d7` | secondary text and field labels |
| `--line` | `#6d507d` | hairlines and borders, 1px |
| `--accent` | `#da6cef` | the one color that means this is the one: the active tab, the primary button, a link |
| `--warn` | `#dfae52` | a warning, the amber marks, and the reason under a control a feature switched off for the install holds dead |
| `--bad` | `#ee6183` | an error, a destructive verb |
| `--note` | `#2de78d` | the second color: a link in words, the chosen view in a group's row, an info note; a hue apart from the accent |

Its light half, the same tokens under the mode switch:

| token | value |
|---|---|
| `--bg` | `#e8e2eb` |
| `--panel` | `#fffcff` |
| `--ink` | `#241e26` |
| `--dim` | `#5e5364` |
| `--line` | `#c8b6d2` |
| `--accent` | `#9f31b2` |
| `--warn` | `#936500` |
| `--bad` | `#b62b55` |
| `--note` | `#007439` |

### Rust (dark)

| token | value | for |
|---|---|---|
| `--bg` | `#291f1c` | the page |
| `--panel` | `#3a2e2a` | a raised box: a card, a pane, a modal |
| `--ink` | `#fef0ed` | the text, and text on a filled accent |
| `--dim` | `#cfbcb7` | secondary text and field labels |
| `--line` | `#755450` | hairlines and borders, 1px |
| `--accent` | `#ff6738` | the one color that means this is the one: the active tab, the primary button, a link |
| `--warn` | `#d9a441` | a warning, the amber marks, and the reason under a control a feature switched off for the install holds dead |
| `--bad` | `#e8544a` | an error, a destructive verb |
| `--note` | `#35e3b9` | the second color: a link in words, the chosen view in a group's row, an info note; a hue apart from the accent |

Its light half, the same tokens under the mode switch:

| token | value |
|---|---|
| `--bg` | `#ebe2e0` |
| `--panel` | `#fefcfb` |
| `--ink` | `#251f1d` |
| `--dim` | `#5f5653` |
| `--line` | `#cdb8b5` |
| `--accent` | `#b53806` |
| `--warn` | `#905e00` |
| `--bad` | `#bc2825` |
| `--note` | `#007256` |

### Sepia (dark)

| token | value | for |
|---|---|---|
| `--bg` | `#262118` | the page |
| `--panel` | `#373125` | a raised box: a card, a pane, a modal |
| `--ink` | `#fef2dd` | the text, and text on a filled accent |
| `--dim` | `#cebfa6` | secondary text and field labels |
| `--line` | `#6b5b3f` | hairlines and borders, 1px |
| `--accent` | `#ebb000` | the one color that means this is the one: the active tab, the primary button, a link |
| `--warn` | `#e3c069` | a warning, the amber marks, and the reason under a control a feature switched off for the install holds dead |
| `--bad` | `#e0705f` | an error, a destructive verb |
| `--note` | `#00e2ce` | the second color: a link in words, the chosen view in a group's row, an info note; a hue apart from the accent |

Its light half, the same tokens under the mode switch:

| token | value |
|---|---|
| `--bg` | `#e8e4dd` |
| `--panel` | `#fefcfa` |
| `--ink` | `#252016` |
| `--dim` | `#5f574a` |
| `--line` | `#c6bdac` |
| `--accent` | `#865e00` |
| `--warn` | `#8a6900` |
| `--bad` | `#ac4133` |
| `--note` | `#007064` |

### Slate (dark)

| token | value | for |
|---|---|---|
| `--bg` | `#1d222b` | the page |
| `--panel` | `#2b323e` | a raised box: a card, a pane, a modal |
| `--ink` | `#eef4fb` | the text, and text on a filled accent |
| `--dim` | `#bac2cb` | secondary text and field labels |
| `--line` | `#525f6f` | hairlines and borders, 1px |
| `--accent` | `#569aff` | the one color that means this is the one: the active tab, the primary button, a link |
| `--warn` | `#d9a441` | a warning, the amber marks, and the reason under a control a feature switched off for the install holds dead |
| `--bad` | `#ef6f6c` | an error, a destructive verb |
| `--note` | `#97dd24` | the second color: a link in words, the chosen view in a group's row, an info note; a hue apart from the accent |

Its light half, the same tokens under the mode switch:

| token | value |
|---|---|
| `--bg` | `#e1e5eb` |
| `--panel` | `#fcfdff` |
| `--ink` | `#1e2124` |
| `--dim` | `#54595d` |
| `--line` | `#b6bfc9` |
| `--accent` | `#1461c7` |
| `--warn` | `#905e00` |
| `--bad` | `#b2373a` |
| `--note` | `#467200` |

## Type

The platform's own sans-serif: system-ui on Web, Roboto on Android, SF Pro on iOS, the desktop's own on Linux, SF Pro on macOS, Segoe UI Variable on Windows, set as system-ui for the page; a monospace stack (--mono) for data: names, paths, versions, anything a terminal could print; --f-note, --f-ui and --f-tag for the three secondary voices.

## Shape

Small radii: 6px on controls, 8px on boxes, 4px on tags.

## Space

An ordinary rhythm: 11px by 14px bands, 10px between fields.

## Motion

Short eases on state changes, nothing decorative, and none under prefers-reduced-motion.

## Rules

Each is one rule of the design, by name; a session is handed one on the turn it edits a file or is asked about a word the rule names, and `aerie design show NAME` reads one.

### design-language

The page's visual rules, in one place. The design has a name, Perch (the operator, 13 Nov): the shell
every page shares (the rail, the top bar, pages with their addresses, the dock) and the rules here. A
theme colors Perch and is not it, and the name carries no number: it is not a version of AerieOS.
Read this before adding or restyling
any surface, and extend the group selectors named here rather than restyling
locally. `test/uniform.mjs` measures most of what follows on every tab and
fails by name; the house rule `design` points here and runs it.

### color

Applies to: scripts/dashboard/index.html, scripts/dashboard/static; color, scheme, theme, palette, hex, contrast

Color comes only from the tokens in `:root`: surfaces `--bg` / `--panel` /
`--sunk` / `--flyout` (page, raised box, set-into-the-panel, and what the
terminal's bottom bar opens: tinted towards the accent, with an accent edge
and a shadow, so it never reads as part of the bar or the page), edge `--line`, text `--ink`
and `--dim`, status `--accent` / `--warn` / `--bad` / `--note`, buttons
`--btn` / `--btn-hi`. Twelve schemes repaint the page by swapping the rest of
them, so a hardcoded hex is a spot the schemes cannot reach. **Good, warning and error are not a scheme's** (`--pass`, `--warn`, `--bad`): one set for every dark scheme and one for every light one, each shade chosen for its half's contrast, so a warning reads the same on any theme. The warning is a warm gold, `#fbbf24` in the dark half (the operator, 23 Nov: warmer than the lemon yellow it was) and a darker gold, `#7d6608`, in the light, AA against the page in both. **A surface tinted with one of the three is mixed over `--ground`**, a neutral no scheme and no space's color moves, with `--ground-ink` on it: mixed over a space's panel, the warning's band read as a dirty olive. A warning's own surface (a band, a banner, the new build's bar) is `--warn-wash` with `--warn-wash-ink` and a `--warn-edge`: in the dark half a faint yellow over `--ground` that the page shows through, the yellow carried by its words and its edge (the operator, 17 Nov: see-through, after a solid yellow had replaced a tint over the space's color that read dirty), and a pale wash in the light half. `test/uniform.mjs` holds the three the same on every scheme in each half and a band's words at AA on its wash, a space's color under it.

**A filled lit surface is `--accent-deep` (mixed from the second color, `--lit`, since 16 Oct), and what sits on it is `--ink`,
never `--dim`.** The active tab, a primary button, a button that is on, a
view bar's current tab, an open select's chosen row, the text selection: all
one token, so all one answer. `--accent-deep` carries a lightness cap for
exactly this reason: the accents range from `#2fb8c6` to `#ffb000`, and
forty percent of black is not enough darkening under the bright ones. Five
schemes had text on that fill under AA before the cap, nostromo worst at
3.56:1. `test/uniform.mjs` measures the rendered pixels on every scheme.
A scheme that carries drawn textures says so in its own rules (Nostromo does).

Watch the class the words wear. A tab's name is a `.lbl`, which is also the
field-label helper, so it arrived wearing the quiet color meant for "Your
email" above a text box, on an accent fill, at 2.51:1.

The edge of a filled accent surface, and the tick of a checkbox, is `--accent-mid`: the accent darkened by 14%, between the accent and `--accent-deep`.

**Every scheme has a light half (R216).** The same nine tokens, hue for hue, with the page near white, the ink dark and the accent and the marks pulled down to AA against the page; `html[data-mode="light"]` is the switch, set by the gear's Dark / Light / System beside the swatches, before first paint from localStorage and on the account. What the dark half derives by lightening the light half derives by darkening (`--btn`, `--sunk`), the purple family and its edges flip with it, and a filled accent carries `--on-fill` (the ink in the dark half, white in the light) rather than the ink itself. Never a hex in a component in either half.

**A Claude session's dot is yellow while it works and green once it is idle** (`--warn`, breathing, then the accent: the operator, 16 Oct), as the phone app has it.

**What is live glows (R218 step 7).** A session dot working or waiting and a pill marking something running (`.pill.live`: a running job, a running container) carry a soft glow in their own color: a 2px ring at a fifth of it and an 8 to 10px blur at about half. One glow, small, so it reads as lit; nothing that is merely fine glows.

**Every scheme has two hues (the operator, 16 Oct).** The accent is where one is and what is live: the rail's bar, the session and status dots, the notebook's group row, a pill that runs. The second color, `--note`, is what is lit and what one follows: every filled control (`--lit`, from which `--accent-deep` and `--accent-mid` are mixed: the selected tab, a primary button, a button that is on, an open select's chosen row, the text selection, a checkbox's tick), a button under the pointer (a tint of it in its fill and its edge; a resting button is the plain control), the logo, a link in words, a space's branch, a Home tile with no news, the second of two charts side by side, the view chosen in a group's row and an info note. It sits apart from the accent on the wheel and from `--warn` and `--bad`, so it never reads as a warning: green and blue, amber and steel, blue and lime, red and teal, violet and mint, green and lavender, orange and turquoise, teal and orchid, purple and mint, rust and sage, ice and lavender, gold and teal. Both halves hold it at AA on the page and the panel, and text on its fill at AA too. A swatch shows both, as two dots.

**The default scheme fills what is pressed in copper (the operator, 1 Nov: not blue on blue).** Its `--lit` is #ff8f4a, #b8470f in the light half, apart from `--note`, so words, links and information stay blue and never read as a warning; every other scheme's `--lit` is its second color. The mark keeps cerulean wings, in the header too.

**A pass is one green in every scheme (the operator, 16 Oct).** The doctor's dot and its passing checks wear `--pass`, which no scheme swaps (#3fb950, #1a7f37 in the light half), as a warning stays `--warn` and a failure `--bad`: an accent can be orange or purple, and a verdict must not change color with the scheme.

**In the light half a lit control is a tint, not a block (the operator, 16 Oct: too dark).** `--accent-deep` there is the panel with 16% of the second color, `--accent-mid` (its edge) the color itself and `--on-fill` the ink, which clears AA on the tint in every scheme; the second color as text is the lightest of its hue that holds AA on the page and the panel. **A state that can be good or bad never wears the accent (the operator, 17 Oct: a healthy container read red in a scheme whose accent is red).** Healthy, running, passed, on, a meter with room: `--pass`, the same green in every scheme (darkened in a light half), as the doctor's checks are; a warning `--warn` and a failure `--bad`. The accent and the second color are for what is chosen and what is pressed, never for how a thing is.

**What floats over the page wears `--float` (the operator, 18 Nov: a tour's card read as part of the page).** The tour, the header's pop-outs (the bell's, the doctor's, the gear's), a row's ⋯ menu, a help pop, the phone's More sheet and a toast: the panel a step brighter with a breath of the second color in the dark half, so each scheme keeps its own, and white in the light half, each with `--float-edge`, a firmer edge than `--line`. What sits on it is re-pointed with it (`--btn`, `--btn-hi`, `--sunk` and `--panel` inside it are the float's), so a button still stands off the surface it is on. A dialog is not a float: it has its backdrop, and on a phone it is the whole screen. `test/uniform.mjs` holds it brighter than the panel (white in the light half), the ink and the quiet words on it at AA, and a button on it its own color, on every scheme.

### shape

Applies to: scripts/dashboard/index.html; corner, radius, rounded, hairline, border

Three corners, as tokens: `--r-surface` (6px, R218 step 7) for boxes (cards, panes,
modals), `--r-control` (6px) for controls (buttons, fields, tabs), `--r-small`
(4px) for tags. Never the number: a scheme may square all three, and nostromo
does. 99px for pills and 50% for dots are not corners and stay round
everywhere. Hairlines are `var(--hair) solid var(--line)`: `--hair` is one device pixel on a screen of two or more to the CSS pixel (0.5px there) and 1px elsewhere, so a border is a line and not a stroke (R218 step 7).

A color is a token too, including the ones that look like a one-off: a
danger edge is `--red2-edge`, a warn edge `--gold-edge`, text on a filled
accent is `--bg`, and a hover shade is `color-mix()` of the scheme's own.
A hex outside the scheme blocks is the default scheme leaking into the
other eleven, and the check counts them.

### type

Applies to: scripts/dashboard/index.html; font, mono, typography, text, size

`--mono` for data: names, paths, versions, anything a terminal could print.
Three secondary voices: `--f-note` (a quiet explainer, in `var(--dim)`),
`--f-ui` (secondary UI), `--f-tag` (pills and badges). Severity and level
colors agree everywhere: error and high are red, warning and medium yellow,
note and low blue.

A section's heading is `--f-sect` (600 14px system sans, 13px for a section
inside a section), the one voice above a row's. What a row says is `--f-row` (13px system sans), what is typed into is `--f-field` (mono, a step below the text beside it, because mono at the same size reads larger), and a pill is `--f-tag`. Code and logs read as prose in mono (a diff, a commit message, a log, a command) are `--f-code`, and a short mono fact `--f-data`: never a pixel size by hand, which stayed put when every voice grew a pixel at a desk.

**One step up at a desk (R210).** The sizes above are the phone's, set against a thumb's width; at a desk, `@media(min-width:901px)`, every voice is one pixel larger (`--f-note` 12, `--f-ui` 13, `--f-row` 14, `--f-field` 12 mono, `--f-sect` 15) so the ladder between them is the same ladder at both sizes. A row's mono facts are `--f-data` (12px, 13 at a desk) and a pill's text `--f-pill`; a button speaks in `--f-ui`, never the browser's default (B711). Nothing retypes a size: a voice is named once on `:root` and once in the desk block.

**A big number is in the display face (R218 step 7).** A tile's figure is `--f-stat`, 24px at a phone and 30px at a desk, in `--display` (the platform's display cut where it has one, Segoe UI Variable Display or SF Pro Display, Inter where installed, the system sans otherwise) at 650 with tabular figures and -0.02em tracking, so a row of figures lines up and reads as one set.

### space

Applies to: scripts/dashboard/index.html; padding, spacing, gap, inset, margin

A band of a document surface is inset `var(--row-y) var(--row-x)`, 12px 16px on the page's 8px rhythm (R218 step 7),
and `.field` applies it, so a band is a `.field` rather than a local padding.
A field inside a field does not inset again. Four
different left edges in one tab is what retyped padding produces.

**Down a dialog there are two gaps and no others**: `var(--field-gap)` (8px)
between the things in a band, and `var(--label-gap)` (4px) between a label
and the control it heads, because those two are one thing. The band owns
both: it is a flex column, and its children carry no margins of their own.
This is not a style preference. It was margin arithmetic between bare
siblings, which collapses between two blocks and adds around an input, so one
form measured 0, 10, 15, 16 and 22 down its length and read as several forms
stacked together. `uniform.mjs` measures every gap in every dialog against
the two tokens, so a dialog that invents a third fails rather than shipping.

### controls

Applies to: scripts/dashboard/index.html, scripts/dashboard/tab-*.js, scripts/dashboard/nb-*.js, scripts/dashboard/page-*.js; control, field, input, select, button, listbox, label, placeholder, textarea, picker

The field skin (ground, edge, radius) is applied to the elements globally,
so a new surface's controls match by existing. What a surface adds is
sizing: full-width mono controls at `--f-field` (11px, a step below the
text beside them, because mono at the same size reads larger) mean joining
the `.modal input, …` sizing group, its iOS rule and its `:focus` group. **The 16px is iOS's
alone**: Safari there zooms the page into a typed field smaller than that
and this layout cannot zoom back, so fields you type into are 16px under
`@supports (-webkit-touch-callout: none)`, a property only iOS has, and the
field size everywhere else. A one-line field there takes 3px above and below its 24px line in place of the field's 6px, so it is still `--tap` high beside a button. A browser without `appearance: base-select` (Firefox, Safari) draws the closed picker the page's way too, the same dim triangle and end padding (the operator, 18 Oct: match Chrome); its open list stays the browser's. A `<select>` never zooms, so it keeps the field
size at every width: a 16px mono picker beside an 11px label is the loudest
thing on the tab, and it was on every tab. Tap targets are `min-height: var(--tap)`. A row of filters
is `<div class="field histbar">`. A control stops short of its surface (`min(--ctl-w, 88%)`), the cap on its row where it has one: every row of controls (a field and its label, a filter row, a picker row, an add row) wears `.ctlrow`, the one class the cap and the bottom line-up read, a line of controls each in its own grid cell `.ctlline`, a box that sizes its own `.ctlown`; no page is named in those rules (R218 step 64); a floating menu is a surface of its own, and a field in it runs the menu's width as its buttons do (the operator, 19 Oct).

**A field's label sits above it**, as `.lbl` (`lbl(id, text, help)`), two
or three words and no more: a field that is filled in still says what it
is, which a placeholder cannot. Where there is something the label cannot
say (a password's rules, what blank means, what a rename costs) it rides
the `?` beside it: `helpIcon(text)`, a circle whose press opens its words as a
line on the page under the label, and a second press folds them away, at
every width. Most fields need none: "Your
email" explains itself, and a `?` saying so is noise. Never a dash and a
clause on the label, never a line of small print under the field. A
checkbox keeps its sentence beside it. A placeholder, where there is one,
is an example, not a name. The two exceptions are a search box in a bar and
a one-line add box that is empty until it is sent: those carry their prompt
inside, because there is nothing to mistake them for once typed in. A text
field is wide enough for what goes in it: a name, an email, a password take
the row up to the cap, and only a number field is a few characters wide.

**Every control on a row is one height, the finger's (`--ctl`, which is
`--tap`).** A field, a pulldown, a one-line prose box and a button beside
each other were 35, 35, 38 and 30px (the operator, 29 Sep): now every
input, select, proseline and button in a document, a notebook or a dialog
takes `min-height: var(--ctl)`, the color swatches alone keeping their
circle, and `test/uniform.mjs` fails a line of controls that are not one
height. `--tap` is 32px (the operator, 13 Nov: every button the size the
group header's New VM and Enroll node were alone in; it was 38px), and
nothing sets a height of its own beside it: a button anywhere, the header's
picture buttons (one width too, the control's), a tab on the dock's line and
a key of the phone's hot bar are all that height, so a row of mixed controls
is one line. A page's sub-nav row keeps 4px above and below its buttons, the
dock line's own spacing.

**A button has a little depth** (the operator, 13 Nov: a subtle gradient):
`--sheen`, a faint light at its top edge falling to a faint shade at its
foot, laid as the background image over whatever color the button wears, so
the accent, the danger tone and a space's own color keep theirs and every
theme gets it without a line of its own. It is on `button`, `a.btn` and a
dock tab, and only on a press that has a ground: a rule that draws a button
with none (a link, a picture alone, a row you open, a tab of a strip) says
`--sheen:none` beside its `background:none`. Nothing else carries a
gradient: a card, a band and a field stay flat.

**Controls on a row line up at their bottom edge.** A row mixes fields that
carry a label above them with bare controls (a select, a button, a remove)
and a centered line floats the bare one between its neighbor's label and its
field. The bottom is the line the eye reads, whatever is stacked above it and
whatever each control's own height is, so a row of controls sets
`align-items: flex-end` and a row whose text column holds a field does the
same with its action cluster. `test/uniform.mjs` groups every visible control
into lines by vertical overlap and fails when one on a line ends at a
different height.

**A set of things to pick from is a listbox.** Several nodes a space
works on, several spaces it reads: a `.lbox`, a bordered box of checkbox
rows (`label.lrow`: the box, the name, a quiet note at the right), each a
thumb high, scrolling past four so it stays small, under a label like any
field. It is the one thing besides a text box that may scroll inside a
dialog: the dialog still scrolls in one place around it, since a box of
forty spaces that did not scroll would be the dialog. Never a
`select multiple`, whose list is the platform's and whose picks are
invisible once it closes, and never a loose column of checkboxes, which has
no edge to say where the choice ends. The space settings dialog draws
both of its sets this way (`lrow` in `page-projsettings.js`).

**A file field is a button of ours and the name of what was picked.** The
browser's own chooser stays hidden: its button wears the browser's skin,
not the page's, and there is no styling it. A `.filepick`: a button that
opens the chooser, and the picked name beside it: is the shape.

**An open `<select>` is the page's own menu, not the platform's.** The list
a select opens is drawn by the browser, so page CSS cannot reach it: on
Android it comes back as a system dialog with the OS accent on its radio
buttons, on iOS as a wheel, on each desktop as that platform's menu. Twelve
schemes and none of them apply. `appearance: base-select` moves the list into
the page, where the tokens do: the picker is `.pinmenu`'s box and `menuIn`,
its rows are `--tap` high and take `--accent-deep` when chosen, and the
element stays a `<select>` so its keyboard handling, its typeahead and its
screen-reader semantics are still the browser's. It is all inside `@supports`,
so a browser without it renders the native picker rather than nothing. The one
thing to know when placing one: a base select wraps a label that will not fit
where a native select truncated it, and `test/uniform.mjs` measures every
select as one line high at phone width. The arrow owns the end padding of
every base select (`padding-inline-end: 0` on the select, the padding on
`::picker-icon`), or a long choice slides under the arrow and shows again in
the strip beyond it.

**A button says what it does and stops.** No ellipsis on a label: "Enroll
node", not "Enroll node…": whether a dialog follows is not the reader's
problem, and the dots are not a word.

**A list of choices is in ALPHABETICAL order unless something says
otherwise, and what says otherwise says why in place.** The color schemes,
the git hosts, the hypervisors and the toolchain catalog were each in the order
somebody happened to write them in; this box's own hypervisor first, then
whatever was added next, which is an order only that person can predict, and
a reader ends up scanning the whole list twice. Alphabetical is the default
because it needs no explanation and a new entry has one place to go. Three
exceptions exist and each is a sentence in the code: `Default` leads the
schemes because it is what you get having made no choice, *Another git host*
trails the hosts because it is not a host, and the toolchain list puts what is
installed first because that is the half you came to act on.

**A value that is one line of PROSE is a `textarea.proseline`, never an
`<input>`.** An input shows about thirty characters at phone width, and a
roadmap item, a bug's title, a changelog entry or the reason something was
dropped runs to three hundred: on a phone every one of those was a field you
could not read what you were editing in. A proseline wraps, grows to its
content and never scrolls inside itself. It is still one line: Enter does
not make a newline in one, and the surface's own Enter handler still runs.
`proseline()` does the growing, and the draw that writes one wires it
(`drawn`, which `patch()` and `drawHTML()` call), so there is nothing for a
new surface to remember, and it is fitted in the same tick it is drawn. The rule the suite enforces: no `<input>` on a document tab
carries a `maxlength` over 120, because that is a sentence and a sentence is
a proseline.

**What the width test measures:** on every document tab, at desktop and at
phone width, the union of each control row's controls and each lone control
against the smaller of `--ctl-w` and nine tenths of the tab's box. A prose
editor in the notebook (a memory's body, a rule, a bug's repro) is a page
rather than a control and keeps the reading width.

**Every group of settings ends with one action bar**: the state line and
its Apply or Save at the right, and nothing else in the group carries a
button. One place to look for the press, on every section of every tab.

**A control never spans its container.** A button, a select, a text field,
or a row of them side by side, is at most `var(--ctl-w)` wide and never the
full width of the tab, card or band it sits in: it stops short, with the
band's own inset and room beside it, at every width. Full-width controls
read as a form pretending to be a page. The one exception is a control
whose whole point is the width: a terminal, a log. `test/uniform.mjs`
measures every control and control row on every tab against the surface
holding it.

**No tooltips** (the operator, 11 Oct). A hover box was clipped by the
pane it sat in and a phone never had one. A dead control is ghosted and
says nothing; a warning or an error is a line on the page, in `warn` or
`bad`, where the row's other facts sit, whole (what is wrong and what to
do), because a dead button with no visible reason is what somebody stares
at (three spaces with no node read as broken after an update, 23 Sep).
A `title` written anyway is never drawn: `untitle()` keeps its words for a
screen reader (`aria-label` on a control with no text, `aria-description`
otherwise), and `saidOf(el)` reads them back for a suite. A destructive button (`.danger`) is filled, never an outline alone (the operator, 27 Oct): its scheme's own red as its words, a 22% tint of that red over the panel as its ground and a 50% mix as its edge, a little more of the tint under the pointer; the same on every surface.

**Red is for what is dangerous; what interrupts and loses nothing is amber** (the operator, 19 Nov, on Restart's red button). A verb that destroys or cannot be taken back wears `.danger`, in red: Delete, Remove, Uninstall, Discard, Reset, Forget, Purge, Wipe, Revoke, Overwrite, Replace, Rotate, Destroy, Erase, a forced stop, leaving over unsaved changes. A verb that stops something which starts again wears `.caution`, in the scheme's amber (`--warn`), filled as the red one is: Restart, End a session, Stop, Reboot, Shut down, a job's Cancel, Sign out, Disconnect, Take back. A question's yes follows its verb the same way (`ASK_DANGER`, `ASK_CAUTION` in page-ask.js): a red yes comes after Cancel, which takes the focus; an amber one is the first button as any yes is.

**A field's words fit the field.** A placeholder that would be cut off where its field is narrow says its short words instead (`data-ph-short`, swapped by width as the field resizes, `phFit` in page-paint.js), as a bar button's words do (`barSaid`); and on a phone, text that would be cut off or ellipsized where it could wrap wraps instead (the operator, 22 Nov).

**On a phone a line is filled, never cut** (the operator, 22 Nov: "those pull down menus could fit flush with the compact buttons", and make it fit site wide). Pulldowns that share a line with a row's compact buttons wear `.pickshare` (page-overrides.css): on a phone they take the line between them in equal shares, each filling its share flush to the buttons, their answers clipped with an ellipsis and the list opening whole; a row that wraps names the least a pulldown takes before it starts a line of its own (`--share`, the Design view's new-page row) and every line it makes is filled the same way. It is the one place a pulldown grows past its longest answer (the pulldowns rule), and only on a phone; uniform.mjs holds each to filling its share or reaching its line's end. A group's tabs keep their line whole on a phone and the row its one height: a group's actions that would cut them short fold into one press whose menu holds them, a + where they make something new (Machines' New VM and Enroll node; actMore's face), and a tab drawn unavailable keeps its dimmed name and its reason as its title without the word not here, which the page it opens says. A press that ends a sentence (a hint's or a notice's `button.link`) is the link's words underlined in that sentence, never a box on a line of its own.

### forms

Applies to: scripts/dashboard/index.html, scripts/dashboard/tab-*.js, scripts/dashboard/nb-*.js, scripts/dashboard/page-*.js; form, field, label, pulldown, select, input

One way to lay out fields, on every page, measured by uniform.mjs's forms check (the operator, 4 Nov: fields crammed together, each page its own way).

**A label sits over its field**, 4px above it, never beside it: `.lbl` or `.pickw`. A picker in a band or an action bar sits beside what it filters and is not a form's field (`.docbarrow`, `.histbar`, `.actbar`, `.phead`).

**Fields go in `.fgrid`**: two equal columns at a desk, one on a phone, 14px down and 20px across, each filling its cell. `.fwide` spans both, for a path or an address. `.fshort` is a number's width. Fields never touch, and a form never sizes one field by hand.

**A long form is `.fgroup`s**, one concern each: a head in the UI voice with a line of dim words under it (`.fgrouphead`), a hairline and 16px between groups, and the same 16px under the last hairline before the action bar. A tick is a line of its own. A hint goes under what it explains. Save is at the foot on the right, as everywhere.

**The control fits the answer.** A known set of answers is a pulldown, never typed: a time zone, a pool, a security level, a person's access. A choice of two to four short answers that should all stay in view is the segmented control (`.pseg`). Yes or no is a tick. An answer with likely values that may be something else is a field with suggestions (a `datalist`): a path, a store. Only what nobody can list is a plain text field: a name, an address, a token. What depends on another answer stays hidden until that answer asks for it.

### settings

Applies to: scripts/dashboard/tab-settings.js, scripts/dashboard/page-projsettings.js; setting, apply, save, checkbox, switch, toggle

Nothing on a tab takes effect until Save or Apply is pressed. A select that
saves the moment it is changed, a checkbox that writes on the click, is a
control that cannot be reconsidered, and the same section's Save then means
two different things. So every group of settings, on the Settings, Users,
Nodes and Artifacts tabs and in the space dialogs: has one Save or Apply
at its foot, and reads its fields when that is pressed. The one exception
is the color scheme in the gear: a theme is looked at, not decided, and a
swatch that needed a second press to be seen would be answering a question
nobody asked. Buttons that *do* something (install, build, connect, end)
are actions, not settings, and act on the press.

**A row's settings are a grid with one Apply (R210).** `.setgrid` holds a `.setcell` per setting, the label above its control as every field is (`lbl`), in columns where there is room and one column on a phone; a read-only cell (`.ro`) says a setting kept elsewhere with the way there; an action that belongs beside a setting (Add route) sits in the cell's `.ctl` and acts on the press. The one Apply is in `.setfoot`, asleep until a control differs from what is saved, and writes every staged setting in turn. A container row was five settings each with its own Apply or Move (the operator, 13 Oct). **On a card the settings are read first (the operator, 17 Oct):** `factPills([[label, value]])`, one wrapping line of pills, each its label in the quiet voice and its value (a pill with no label is a state on its own, Starts on boot), so every setting is on show at a glance; Edit settings, the first thing behind the card's ⋯, opens the grid in a dialog titled with the card's name, Cancel and the one filled Apply at its foot, Escape its Cancel; a card with a setting staged keeps it open. A Containers card is this.

### files

Applies to: scripts/dashboard/index.html, scripts/dashboard/page-*.css, scripts/dashboard/page-boot.js; script, module, file, load, stylesheet, layer

The page is `index.html` (the markup, and the head's one script, which reads
the theme before the first paint), its stylesheet, and classic scripts
beside it.

The stylesheet is four files, a cascade layer each, linked in their order:
`page-skin.css` (the tokens, the twelve schemes and what a bare element
looks like), `page-components.css` (what more than one page draws: rows,
sections and their bars, tiles, facts, chips, pills, menus, dialogs,
toasts), `page-surfaces.css` (what one page or one part of the page draws:
the header, the rail, the dock, a page, a notebook view) and
`page-overrides.css` (what must win whatever else says: hidden is hidden,
less motion is none, a theme's crossfade while it runs). A later layer
wins over every rule of an earlier one, whatever either's specificity or
place in its file, so a rule goes in the layer of what it styles and is
written as plainly as that allows: never lengthened, and never moved down
the file, to win. Where a shared rule has to keep winning over a page's own on one
property (a dialog field's margins for its children, the look a disabled
button keeps under the pointer, the nostromo schemes' raised edge on a
button), the page's declarations of that property sit in the components
layer beside the shared rules, under a note naming what outranks them,
and the rest of the page's rule stays in surfaces. xterm's own stylesheet stays outside the layers, so its
rules for its own parts win over the page's for bare elements.

The scripts: `tab-*.js` for a document tab, `nb-*.js` for a notebook view
(`nb-core.js` is the notebook itself, the frame the views draw into),
`page-*.js` for a part of the page that is neither (the state and the
helpers everything reaches for, the tabs, the panes and the dock, a
space's rows, a space's settings, the doctor, the polls, the bell, and so
on), and `page-boot.js`, what runs at load: a function a part, under the
part's `// ---- name ----` header, called in order by `boot()`, which the
page's last line runs once every script is in. Every other file is pure
declarations and starts with `"use strict"`; a declaration whose
initializer reads the page at load (the favicon's element) is
`page-boot.js`'s, at its top level. The server serves a script or a
stylesheet only by name: the lists are the page's own tags (`page_scripts`
and `page_styles` in `server.py`), so a new file is added once, as a tag in
`index.html`. `aerie map sections FILE` reads a file by its headers, with
each section's outside callers, what runs at load and what the suite
covers.

### sections-and-action-bars

Applies to: scripts/dashboard/tab-*.js, scripts/dashboard/nb-*.js; section, fold, action, bar, actbar, hidden

A long surface is sections: `docSection(kind, id, title, status, body)`, one
fold per concern with its status on the heading in `--f-sect`. Every section is open by
default at a desk and several stand open there (the operator, 8 Oct: too much was hidden
in folds); a person may shut one, and it stays shut for the page's life. On a phone one
section is open at a time on every folded surface, as the notebook's views do: opening
one shuts the others (the operator, 11 Oct), so the page is never a stack of open folds
to scroll. A surface of more
than one section carries a jump bar (sectJump; the operator, 23 Oct): their names in a line at the top, each
scrolling to its own. Sections alone: what a page's chips pick (the Containers page's spaces) is not on it. A status is a word or a number, never a sentence.

**Nothing stands between sections, and pills stand at the top (the operator, 25 Oct).** A line about a section is inside it, first in its body, never a loose band between two sections (the coding agents' line stood between Toolchains and Tool packs). A page's pills, its chips and its jump bar, sit at its top, before its first section of any kind, never mid-page under sections its chips pick (Storage's jump bar stood under its disks). `test/uniform.mjs` fails a page with either.

`hidden` means hidden. `[hidden]{display:none !important}` is global,
because any class that sets `display` otherwise beats the attribute: a fold
that never closed and a Select all with nothing to select were both that. To
show something, take the attribute off; never give a hidden thing a display.

Every set of two or more text buttons is an action bar (`.actbar`): the
status on its own `.state` line, the buttons after it at the right, their
own size at every width: a phone gives them the finger height, never the
row. The destructive verb wears `.danger` and comes last, so nothing safe
sits after something that cannot be undone. A button that started something
wears `busy(btn, verb)` until the repaint replaces it. Icon clusters with no
text are exempt.

**At most five buttons on a bar, and the rest behind ⋯ (R210).** A row's bar holds its primary verbs (Open, Shell, the build, Down, an Update that is due) and `actMore([...])` draws the rest behind one ⋯ press (named More for a screen reader, the same ⋯ a space's header has), whose menu opens under it as the gear's does, anything else closes it, Escape too; a single leftover is drawn inline, since a menu of one is a detour. The destructive verb is last in the menu as it was last on the bar. Seven buttons wrapped to two lines on a phone with Remove alone on the second (the operator, 13 Oct); `test/uniform.mjs` counts a bar's buttons at phone width.

A segmented switch (`.pseg`: Deploy key / Access token, Dark / Light / System, Cards / List) is one choice of two or three, not a set of verbs, so it is not an action bar and sits where the choice is read: in a dialog's field, the gear, a tab's bar (R216). A press that navigates (a download, a container's Open) is a link in the button suit, `a.btn`, and `a.btn.primary` where it is the row's main action. Every page's last card has 16px under it, the list's own spacer (`.doclist::after`), never a last child's margin, which a scrolling box drops.

### rows-you-open

Applies to: scripts/dashboard/nb-*.js, scripts/dashboard/tab-profile.js, scripts/dashboard/nb-artifacts.js; row, fold, edit, cancel, download

A row with detail behind it is a fold, the shape a bug report has: the name
on the line with its pills, the fields under labels when opened, its action
bar at the foot, and a line divider between rows rather than a box. Rules
and memories on the Briefing tab and the tests on the Tests tab are this
shape too.

A row opens to be read, never as a form. Edit on its action bar swaps the
fields in; Cancel (`.stop`) puts them away and drops what was typed, and
Save puts them away having written it. A row Add made has nothing to go
back to, so canceling it removes it.

A list of things to download or open is the Artifacts tab's rows
(`.artrow`) wherever it appears: the name in bold with its facts in the
small mono beside it, a hairline between rows, and the download or the
action at the row's right, wrapping under it on a phone. A notebook's
Sessions are those rows, not a list of their own.

### nothing-acted-on-in-a-fold

Applies to: scripts/dashboard/tab-*.js, scripts/dashboard/nb-*.js, scripts/dashboard/page-*.js, scripts/dashboard/index.html; fold, details, collapse, hidden, row, summary

What a person acts on or decides by is on the row, at every width, and never only behind a fold: a row's settings (its space, where it is built from, its ports), its state and its buttons. A fold holds what is long and read now and then: a log, a list of mounts, raw output, a full compose file. A surface too long with everything shown is too long, and the fix is less on it, not a fold over part of it (the operator, 8 Oct: the Docker tab's Space picker sat in a closed Details fold on a phone and could not be found).

### long-lists

Applies to: scripts/dashboard/nb-*.js, scripts/dashboard/tab-*.js; list, page, paginate, pagination

A list that can outgrow a screen shows its first page and brings in more as the reader gets to its foot, through `paginate` and nothing else: one helper applied to the DOM after a list draws, rather than each renderer growing its own (the operator, 16 Oct: in place of Previous and Next). While more is to come it draws a quiet `.pagemore` foot saying how much is on screen of the whole ("50 of 80 bugs") with a Show more for a keyboard or a reader who would rather press, and the next page arrives by itself as that foot scrolls into view; with all of it shown there is no foot. It is a bar the framework owns, so it is exempt from the action-bar rule and its shape is the same on every list.

The rows already on screen never move as more arrive under them, and a redraw keeps what had been shown rather than cutting back to the first page. The order still means something (bugs by severity, the roadmap in the order the work has to happen in).

Two judgements are yours. A list that only just crosses the line is left whole, which `paginate` does for you. And a list somebody SCANS for a name rather than reads in order (the toolchain catalog) is not cut at all, because hiding half of it behind a control is worse than a long page.

The Library is no longer that list (R256, the operator, 18 Nov): a catalog that can grow without end is paged by the server like any other long list, and a name is found with its search rather than by scanning.

### motion

Applies to: scripts/dashboard/index.html, scripts/dashboard/page-motion.js; motion, animation, animate, fade, transition, tween

Everything that appears, leaves, opens or changes state moves: a panel or
menu arrives the way it opened (the operator, 18 Oct): one below what was pressed drops into place (`menuIn`, 8px over .22s) and one above it rises (`menuRise`, the same 8px and .22s upward), every context menu at its button at a desk and on a phone alike, never a sheet; the bottom bar's More, which opens upward from the bar, rises further (`menuUp`, 16px over .32s); all on one ease-out cubic, a document brought to the front fades in over its
own ground (`docIn`, contentIn's frames under a name of its own, so a
document that already wears contentIn from its first paint still fades when
it comes forward) while the page it replaces fades out first (`docOut`, gone by .09s) and holds still where it sat, a fade through rather than a double exposure (the operator, 16 Oct); every page's bar is one height, its sub-nav's segment (one button for a page that stands alone), so a switch moves nothing; the dock slides up out of its line when it opens (`dockUp`) and back down into it when it shuts (`dockDown`), laid over the page, a section folds over its height
(`slideBody`, the section tween), a button or tab eases its color, a
toast
slides, a modal leaves the way it arrived (caught off the `hidden` attribute
by one observer, so no close site has to remember), and a row folding its
controls out on a phone slides over the height that takes. A change that
snaps is a change the eye has to find. Every one of them is off under
`prefers-reduced-motion`.

**What fades is what is drawn, never the ground under it.** A document's
ground (the page color, the panel color, nostromo's glass and deck)
is painted by the pane's stack while that document is the one on show, and
the document box itself paints none, so the fade on it carries only its
content. When the box painted its own ground, the ground faded in with the
rest over the pane's black, and every switch to a notebook opened on a black
pane (27 Sep). `uniform.mjs` photographs the first frame of a switch, every
kind and every scheme, and holds it to the settled tab's own ground.

**The page waits on its own ground.** Nothing can be drawn in a pane until
the first snapshot lands, and an empty one used to be black and wearing the
active pane's outline: the loudest element on the page, showing nothing, for
as long as that took. Until then `body.booting` gives the pane the page's
ground and a placeholder shaped like the page its address names (Home's
tiles, the Spaces page's cards, rows otherwise), and the first draw that had
state to draw takes the class off.

**What is coming is drawn by its shape.** A list, a grid or a view waiting on
a fetch shows `skel(shape)` (page-docs.js): bars where its words will be,
rows, cards or tiles where those will stand, a light passing over them left to
right, in the ink at a whisper so every scheme tints them its own way (the
operator, 16 Oct). It is still a `.loading`, so what replaces it fades in
and a failed poll writes its words over it; the word stays for a screen
reader, and the light stands still under `prefers-reduced-motion`. A
page that knows its own shape waits as itself (the operator, 16 Oct): what
never changes on it (its headings, a tile's label, a table's head, a form's
labels, its bar's controls) is drawn for real and only the values on their
way shimmer: `skTpl()` around the page's own markup, `skv()` for a value
inline (`ctl` for a field's control), `skRows()` and `skTable()` for the
rows to come. It is inert while it
waits, its actions there and dead, so nothing is typed into a form the real
one replaces. A `loading…` line is left only where no shape is known.

**A row that goes leaves.** A row a press takes away (a bell row dismissed, a notice deleted) fades as its height folds to nothing, on the fold's 180ms tween, the rows under it riding up rather than jumping (`leaveBox`, the counterpart of `arriveBox`; the operator, 22 Nov). Every copy of it on show leaves together, and the page draws without it once it has gone; a refusal puts it back whole at once.

### progress

Applies to: scripts/dashboard/page-docs.js; progress, busy, spinner, percentage

Something that is running says so with a word and an animated ellipsis, `busy(btn, verb)`, and no bar or percentage of the page's own guessing: nothing here can honestly measure how far along a build or a pull is, and a bar that guesses is a lie with a scale on it. Where the thing running reports an honest measure of its own (the operator, 8 Nov: SnapRAID's percentage on a sync, scrub or parity check; the bytes of a bundle sent from the browser), a bar is drawn under the word with `pctBar`: a thin track in the line color, the accent as far as it has come, capped at a control's width, the word still saying what runs. Never a bar for a job whose only measure is time.

**A press still waiting wears a ring, where a ring has room.** A press whose work is not done after 200ms shows a small spinning ring in place of its word, or of its picture on a button that is a picture alone, the word kept unpainted so the button is exactly its size, so it reads as taken rather than missed (the operator, 8 Nov; in place of the word since 22 Nov: a wheel only where it fits without making the button bigger). Its work is what it asked for: a request sent while its click is handled (`postJSON`, `getJSON`, `postFile`) and the promise its handler returns, the questions it asks on the way included, the ring waiting while a dialog the button is not in is open; never a request that only started near it, so a poll on a slow link holds no button (`pressTie`, `pressHold`, page-motion.js). Never where it would disrupt a small space (the operator, 13 Nov: like the rail's icons): a group on the rail or the phone's bar, a page of a sub-nav or any segmented control, a notebook's view tab, a tab on the dock, a chip and a button of the header wear none, the page arriving being the answer there; and anywhere else the ring is tried and taken back off if it made its button wider or taller, or its row taller or wider than its box (`pressRing`, page-motion.js). A new strip of presses packed side by side joins `PRESS_TIGHT`.

**A press never looks ignored (the operator, 22 Nov).** On the click a press changes its own state: a chip in its band or a segment of a segmented control is lit before its handler's work (`pressPick`). A result the page knows before the server answers is drawn at once (`drawNow`): a row dismissed or deleted is gone, a narrowing of the rows in hand is narrowed; a refusal puts it back and says why in one sentence. A result it cannot know shows where it will land: the section under it becomes its placeholder, and a chip's count becomes the ring in the count's own room (`pressCount`), the chip neither wider nor taller. While any write the page sent is unanswered, leaving or reloading the page asks first, in the browser's own words (`writeOut`); the page's own writes on a timer (presence, the layout) say `{background: true}` and hold nothing.

**What waits is dead, what queues says so.** While an operation runs, a press it blocks (one the server would refuse) is drawn dead, its reason on its row in the muted voice, and live again when the operation ends; a press the server queues behind it stays live, and its press says in one sentence that it is queued and behind what, in a toast and on its row's own state where it has one (the operator, 22 Nov).

### meters

Applies to: scripts/dashboard/tab-nodes.js; meter, gauge, bar, track

A bar that measures something real (a disk, memory, a load) is a meter:
a label, a track, a value. Meters come in stacks, and a stack is read as
one set of gauges, so every track in it is the same width and the values
sit in one right-aligned column. The value column has a fixed width sized
to the widest value the stack can show; it is never `auto`, because then
each row sizes its bar to whatever its own number leaves it, the long
values shorten their bars, and the stack reads as a ragged edge instead of
a comparison. `uniform.mjs` measures every stack on every tab for this.

### when-a-view-re-reads

Applies to: scripts/dashboard/page-poll.js, scripts/dashboard/nb-*.js, scripts/dashboard/tab-*.js; poll, refresh, revision, redraw, re-read, timer

Three ways a view changes, and each has one answer.

**Something the person just pressed** is redrawn by the handler that sent it,
from the answer it got back. Nobody waits on a clock for a button they are
looking at. An answer that never comes is said: `postJSON` answers a
request that never landed with `{error: "the controller did not answer"}`,
so the handler's own `if (j.error)` says it, and what nothing caught is
said by the page (`sayUnheard`) rather than lost.

**A read is one at a time.** Every read a page or a view makes for what it
draws goes through `reading(key, fn)`: one read of a kind at a time, a
read asked for while one is out made once more when it lands rather than
stacked beside it (a token moves with every step of a job), and every
answer drawn in the order asked, so a page whose reads are asked for faster
than they answer still draws each. Its landing moves the kind's revision,
which the page's live key reads (`readRev`); a change no read brought (a
pick, a draft) moves it with `readMoved`. No page keeps a counter of its
own, and a press's own request never goes through it, since an ask asked
again would take its place.

**Something that arrived from elsewhere** is the revisions poll:
`/api/revs`, which is stats and in-memory counters and nothing that shells
out, every second and a half while something moved in the last minute,
every five seconds after that and every thirty while the page is hidden. A
token only one page draws (a node's heartbeat numbers, `nodes.sample`)
counts toward "something moved" only while that page is on show, and moves
apart from the token every other page watches, so one node's heartbeat is
not a re-read on every page (R218 step 10). A view says what it depends on with
`onRev(key, fn)` and never decides when to re-read; the server publishes a
token for everything a view watches, and every token it publishes is
watched. `test/revs.mjs` holds those two sets equal, in both directions,
because the failure is silent: a page that waits is not wrong, only late,
so nothing else goes red. The keys a notebook watches are per space and
the page asks for its open ones by name, so a space nobody has open costs
nothing.

**A token is a counter where a panel can lose work, and an mtime otherwise.**
A panel that stages (the roadmap, the memory editor, a test's description)
holds the number it last read and compares, so it can tell somebody else's
write from the echo of its own; an mtime cannot make that distinction, and a
redraw a panel did not need detaches the send box or the half-typed row under
the finger that opened it. The same panel ignores the poll while a write of
its own is out, and asks again when it lands: the token moves when the server
takes the write and the panel's number moves when the answer gets back, so a
poll arriving in between would read the panel's own words as somebody
else's.

**Everything else is `/api/status`**, and it carries only what nothing
cheaper can answer: the branch, the sessions, the image, the doctor. A
revision does not belong on it. Its clock is a chain, not an interval: the
next read is due fifteen seconds after the last one, whoever asked for that
one (an action's read resets it), none is due while the page is hidden, and
the page coming back reads at once.

**A draw writes only what changed.** The page draws as often as anything
asks it to, and a draw that finds nothing new touches nothing: a page's
skeleton (`docSurface`) outlives its draws, every list, bar, foot and the
rail go through `patch()`, and the frame's small writes through `setText`,
`setAttr`, `setClass`, `setHidden` and `setDisabled`, each a no-op when the
value is already there. What a draw brings is the draw's own, at once: a
data-style applied, a proseline wired, a field kept from password managers,
a title turned into words, a chip row's scroll put back (`drawn`), never an
observer's after it. Written unconditionally, a status read rewrote two
hundred nodes of the frame and faded the Home page in again each time, the
pointer losing its hover on whatever it rested on. `uniform.mjs` reads every
kind through a status read that brings nothing new and fails any write.

**A timer of a view's own is for watching something in flight, never for
noticing a change.** Noticing is the revisions poll's job, always. The
Toolchains and Emulator tabs are the ones that keep a timer, and only while a job is running:
an install of a small toolchain starts and finishes inside one revision poll,
so the tab would go from idle to done having never said "installing". It
stops when the job does. Anything else with a clock of its own is a tab that
notices things sooner than the tab beside it for no reason anybody chose,
which is what this whole section is against.

**A redraw nobody asked for never takes what a person has open.** Two things
on a surface are open rather than typed: a menu and a fold. Neither is a
tab's to look after, because a rule one tab keeps is a rule the next forgets.

A `<select>` whose list is showing holds the redraw. `menuHolds(root)` is
asked at the two places a redraw that did not come from a press starts: the
revisions poll, which is skipped whole so the news is still news on the next
tick, and `renderDoc`, which draws every document tab. The draw that was
skipped happens when the list shuts. A draw that came from a press is not
held, since the press is what shut the list. A patch keeps an open menu in
the surface it draws, so it needs no holding of its own.

A fold stays the way it was left. One with a `data-sect` key is recorded by
the page's one `toggle` listener, and only when somebody pressed it, so a
default never turns into a choice. `docSection` writes the key for a
section; `sectAttr(key, dflt)` writes it for a fold that is not one, such as
a row's Details or one file of a diff. A list row that carries its own
identity (a memory, a bug, a test, a rule) keeps its open set in its view
instead. `uniform.mjs` fails any `<details>` on any tab or notebook view that
has neither.

A surface keeps the rest a person has (R244). `patch(el, html)` writes a
new draw into what is there rather than over it: every element the new markup can be matched to is kept and brought
up to date, so a field being typed in keeps its value, its caret and an IME
composition, and a dialog open in the surface stays open. A list's rows
carry `data-key`, so a row added, taken away or moved takes nothing of its
neighbors'; rows that share a key are matched in their order, and a key
says which row it is (a file's fold is its path, not only its state). A
form control or a button is matched only to one with the same type, name
and `data-*`, so typing is never handed to another field and a press never
writes to another action's button. It changes only what the markup changed
since it last drew: what the page puts on an element itself (the password
managers' ignore marks, a title moved to `aria-description`, a class it
added, a card turned over by a press) and what a person changed (a value
typed, a box ticked, a fold turned) stay, while a press's own state
(`disabled`, `aria-busy`, a button's label) is the markup's again at the
next draw, and `pressBack()` and `unbusy()` give a press's button back as
its markup has it then, never the label kept from before the press. A
pulldown that is an action rather than a setting (fill a theme from a
preset) puts itself back on its first line when it has acted, since its
markup always draws that line and the person's pick would otherwise stay.
An element's `style` is never the markup's (the content policy draws none;
`data-style` is, applied through the CSSOM), so a part a press drew by its
own hand keeps its place and color when the surface around it is patched. A
patch keeps an open menu where it is with what is typed in it. What the
page's code puts into a drawn surface carries `data-own` and is left where
it is: a jump bar, a slide marker, a status it fills into a summary, a box
asking for a name (`askInline`), a card's color swatches, and a copy of a
part fading out (`.fghost`), which a patch landing while it fades never
takes for the part it copies. The record of a draw steps over them too, so
a jump bar put before a surface's first section is not another writer's
and the next draw is still a patch. On an element the markup draws,
`data-own` says its children are its code's (a fold read when it is opened,
a commit's detail read when it is picked). A handler on an element a patch
keeps is set (`onclick =`), never added, or a second draw would run it
twice; `uniform.mjs` draws every page and view twice over and names any
listener a draw adds to what the last one kept. Every page's bar and foot, the rail, the dock's line, a space's
header, a view's glance, the Spaces grid, the Containers, Nodes, VMs,
Files, nginx, Library, Home, Sessions and Installed pages, the first-run
page, every notebook view and every other list draw through it, none keeping
a caret or a focus by hand. A find box acts once a word is whole
(`onTyping`): never in the middle of an input method's composition, and once
at its end. `patch.mjs` holds every rule.

### words-on-the-screen

Applies to: scripts/dashboard; hint, wording, text, copy, sentence, empty, state, line

One sentence that tells the person what they need to know to act, in their
words: what the control does, and the one consequence they could not guess.
Not what they can intuit, not how it came to be, not the reasoning; a
paragraph on a control is one nobody reads, and a page of them turns the
reader off (the operator, 23 Sep, after R28 swept them). A hint, a state
line or an empty state is a line, about 25 words. The why goes in a code
comment, the README or Help, never inline. A stacked row
is `flex-wrap: nowrap`; a long token in it wraps or scrolls inside its own
box, and nothing scrolls the page or the pane sideways on a phone. One name for each thing (the words pass, R287, 26 Nov): a person reads space and repository, never project or repo, which stay the code's and the API's names; a toast is one sentence, a colon or a semicolon joining what a second one would say; a refusal every module meets is said once, in refusals.py (not a space, not an account). unit/test_words.py and unit/test_refusals.py hold these.

### badges

Applies to: scripts/dashboard/index.html, scripts/dashboard/nb-*.js; badge, pill, tag, severity, sev

A tag that says who or what (a memory's type, a bug's severity and state, who wrote a history line) wears one of five badge colors, the same on every scheme, named once on `:root`, each with an edge for the pill's border: `--purple` `#b79ae0` (edge `--purple-edge` `#38294a`) for who did it, a reference and a state that does not apply; `--green2` `#7fc08a` (`--green2-edge` `#1f3f28`) for what is new, a space's own and fixed; `--blue2` `#77b7e8` (`--blue2-edge` `#1e3a4a`) for the user's, low and open; `--gold` `#d8b25c` (`--gold-edge` `#4a3c1e`) for a note, feedback, medium and a toggle that is on; `--red2` `#e0796f` (`--red2-edge` `#94423d`) for what is gone and high. Never a hex at the site: the day one shade drifts is the day two tags of one family stop looking like it. The pill's text is `--f-tag`. A dev feature (offered only while Offer dev features is on, not yet walked on a real machine) says so wherever it is offered, the same way everywhere (R102, the operator, 22 Oct): a `dev` pill (`.pill.devmark`, gold, from `devMark()`) beside a row's name, a setting's label or a section's title, and ` (dev)` after its name in a pulldown's option (`devOpt()`), since an option holds no pill.

### project-color

Applies to: scripts/dashboard/index.html, scripts/dashboard/page-panes.js, scripts/dashboard/page-projsettings.js, scripts/dashboard/tab-docker.js; project color, stripe, swatch, tone

A space may carry a color, one of the nine swatches, each person's own and picked from Color in its card's menu, the swatches unrolling under its name (the operator, 18 Oct: not the space's, and nobody else sees it; a dot beside the name read as a checkbox), and the page says whose a thing is with it in four places and no others: its terminals' tabs in the dock, a Claude session's and a shell's whose label names it by the directory it is in (a 3px stripe on the left, the whole tab tinted 20% at rest and 36% when it is the one in front, its edge in the color), its card on the Spaces page and on Home and its row in the phone's space list (the stripe, the whole box tinted 16%, 14% for the phone's row, its edge in the color: the operator, 18 Oct, the whole box and not only the stripe; the card's own buttons tinted with it too, 22% and 50% for the green Open, so the card reads as one color and the running session still stands out on it), a space's page header as its card is (the stripe, the 16% tint over the panel, its edge and its buttons in the color: the operator, 19 Oct), the bar of any other page showing it (the stripe only), and the heading of its group in the Docker manager (a 4px stripe and a 16% tint, as `--gc`, the line color for containers that belong to no space). A tint is mixed over the panel, never over a bar's see-through ground, which turned a notebook's bar black (the operator, 29 Sep). The color arrives as `--pc` on the element; the swatches are circles of their own size, never the control height.

### node-switcher

Applies to: scripts/dashboard/tab-*.js, scripts/dashboard/page-docs.js; node, picker, switcher, select

A tab about one node at a time (Toolchains, the Emulator, the Phone, the CI runner, the Docker manager) picks it with `nodePick()` (page-docs.js): one `label.pick` reading **Node**, at the left of the tab's bar (`.docbarrow`) with its buttons at the right in the page-head order (no Refresh: the page follows its revisions), listing the agent nodes by name; a node that cannot be picked for this tab is in the list, disabled, its reason after its name (`sandbox: no adb`), and a quiet one says so. A tip in that bar opens under it, anchored to its right edge, so the rightmost one never hangs past a phone's pane.

What is installed on the node is a list of rows (`.tc`): an installed thing with its bin at the right, a thing to add with its own **Install** at the right, which acts on the press (Perch: an action acts on the press, only a setting stages); several at once are the action bar's **Select several**, which gives the rows ticks (`label.tc`) and **Install selected** for the ticked set in one job, with Cancel beside it. The Emulator is this, its rows to add narrowed to one flavor picked above them; the Library's cards act on the press the same way. A thing the node runs (the Phone, the CI runner) opens on a state row, `.row.toolstate`: "Phone on sandbox" or "CI runners on sandbox" with its state as a pill and one sentence under it; then its controls and its add band (inset in a `.field`), and at the foot a `.field.toolfoot` hint saying how a session or a workflow reaches it. A new node-scoped tab starts from one of these two shapes, never from a picker or a layout of its own (R121, the operator 4 Oct).

### voices

Applies to: scripts/dashboard/index.html, scripts/dashboard/tab-*.js, scripts/dashboard/nb-*.js; notice, notices, state, pill, facts, voice, voices, warning

Three things live under a row's name, and each has a voice of its own (R210; the operator, 13 Oct: facts, warnings and settings all wore the same dim mono and read as one gray block). **Facts** are one line of `--f-data` mono in `var(--dim)`: where it came from, its ports, a path, a revision, separated by ` · `. **A notice** is what is wrong or what to know, one sentence, in `--f-ui` sans in the level's color behind a 3px bar of that color, no wider than a paragraph: `.sub.warn`, `.sub.bad`, `.sub.note` under a row, `.notice` where there is no row; a problem the page can fix is a link in the same color. **A state** is a pill on the name line, `.pill.stat` (`.state` is the action bar's status line, `.st` the session dot), a word in `--f-tag` caps: `.ok` (running) in the accent, `.warn` (partly up) in gold, `.off` (stopped, down) in purple, and no class for one nobody asked (state unknown); never a parenthesis in the facts' mono. Settings are the grid the settings rule describes. `test/uniform.mjs` measures a notice's font and bar.

### tiles

Applies to: scripts/dashboard/page-docs.js, scripts/dashboard/tab-*.js, scripts/dashboard/index.html; tile, tiles, stat, count, number, summary, glance

**What a page is about now is one status line (R274, the operator 23 Nov: the tiles and the facts made pages busier than they are, and often said nothing to act on).** Under a page's head, or a notebook view's control row, one quiet line in the UI voice says what the page is about at this moment: `statusLine([{value, label, sub, tone} | {text, tone}])` in page-docs.js, short phrases joined by a dot, a number in ink with its words dim ("5 updates due · versions checked 37 h ago"). A phrase wears `--warn` or `--bad` only when it wants doing; nothing else is colored. A count a filter chip already shows is not said again on the line (the Library's Installed and Updates are its chips'). A phrase for a number that is always the same is not drawn. A page draws its line through `pageHead({line})`, in its head, a card at a desk, on every page alike (the operator, 24 Nov: a line bare on some pages and in a card on others was all over the place); a node's head card carries it over its facts, and `uniform.mjs` fails a page whose line stands as a band of its own. `statTiles` draws the same line for a notebook view's glance, on the view's own row. **Home is the one row of tiles left** (the-dashboard/home): the summary of everything, each tile a link to the page that holds its number. A page's top runs in one order (the page-head rule): a notice, its head (its name, its pills, its status line), its control row with the search and its buttons, its big chips, and only then the boxes that are its own.

### facts

Applies to: scripts/dashboard/page-docs.js, scripts/dashboard/tab-*.js, scripts/dashboard/nb-*.js, scripts/dashboard/index.html; fact, facts, grid, label, value, key, pairs

**What a row knows is a facts grid, not a sentence of dots (R216).** A row with more than two facts about one thing (image, ports, where it was built from, the compose file it came from, its containers) lays them out as `factGrid([[label, value], ...])`: a `dl.facts` of `dt` labels in `--f-note` dim and `dd` values in `--f-data` mono, two columns at a desk and one on a phone, each value wrapping on its own line. The ` · ` run-on line stays for two facts or fewer, and for the one line under a name that says where a thing came from. A value that is a path or an id is mono; a value that is a sentence is not a fact and goes in a notice (the voices rule).

### tables

Applies to: scripts/dashboard/page-docs.js, scripts/dashboard/tab-*.js, scripts/dashboard/nb-*.js, scripts/dashboard/index.html; table, tables, column, columns, header, thead, tline, tblwrap, tblline

**A list whose rows are all the same shape is a table (R218 step 8).** Jobs, the people on Users and the roles, the pinned toolchains, images and volumes and the Docker list view: a header line naming the columns in `--f-note` dim over rows whose first line holds the same columns, so a value is found by looking down a column, not by reading every row. `tblWrap(cols, rows)` draws the table and its header, `tblLine(cols, cells)` one row's line (in page-docs.js); a column is a share or a fixed width and never auto, since each line is its own grid and only shares and widths line up across lines. The lead cell is the thing's name in `--f-ui` 600 and may wrap; every other cell is one line in `--f-data` dim ending in an ellipsis, numbers right-aligned in tabular figures. A value in a column (a version, a size) is plain text in that voice, never a pill, so a column reads alike down its length; a pill is for a state (succeeded, running, in use). A row is still a row (rows-you-open): its buttons are the line's last column, at its right end; a reason is under the line; what is long (a log, a container's card) is behind its fold, opened from the line. Where rows differ in what they hold, they stay cards. On a phone (under 900px) the header goes, the lead cell takes the first line and the others follow it, each wearing its column's name, an empty cell not drawn, and the buttons at the right of the last line they fit on. A grouped list (containers by space) is a table per group under the group's heading.

### charts

Applies to: scripts/dashboard/page-docs.js, scripts/dashboard/tab-*.js, scripts/dashboard/nb-*.js, scripts/dashboard/index.html; chart, charts, sparkline, spark, crosshair, hourchart, sparksvg, trend

**Where a number moves, it is charted (R218 step 9).** A node's page charts its last hour of CPU and memory; a running container's CPU and memory tiles carry its last half hour. Drawn inline by `hourChart(id, title, points)` and `sparkSvg(values, max, label)` in page-docs.js, the crosshair wired by `wireCharts(root)`, with no library. One series to a chart: two measures are two small charts side by side (stacked on a phone), never two lines or two axes on one, so no chart needs a legend or a second hue; its caption names it. The line is 2px in `--accent` over a wash of the accent at a tenth, the grid three hairlines in `--line` (the top, the middle, zero), and every word (the caption, the axis, the readout) in text tokens, never the series color. Under the caption the latest value and the hour's low, average and high are written out, so nothing depends on a hover. The crosshair finds the nearest sample to the pointer and says its value and time; focused, the arrow keys walk it. The plot stretches to its box and its strokes do not (`vector-effect: non-scaling-stroke`); the axis labels and the end dot are HTML, so text keeps its size at every width. A gap longer than three samples' spacing breaks the line: a quiet node is a gap, not a slope. A sparkline is 96 by 24, its line in the quiet voice and its latest point a dot in the accent, under the tile's number; it is not drawn with fewer than two points. A longer span is the same chart (R164 step 4, This machine's Reporting): `hourChart` takes a sixth argument naming it (6h, day, week, month) and writes the span's own words on the axis and in the caption (a day ago, 12 h, now), the crosshair reading the span off the plot; one point is a five-minute or an hourly mean, so its tip says the weekday beyond a day. The hour's chart is unchanged.

### chips

Applies to: scripts/dashboard/page-docs.js, scripts/dashboard/tab-*.js, scripts/dashboard/index.html; chip, chips, filter, narrow, group, groups

**A long list is narrowed by chips, not by a second list (R216).** Where a list is grouped (containers and VMs by space, jobs by node, toolchains by kind) a row of `.chip` buttons under the bar narrows it: All first with the whole count, then one chip per group with its count in a small pill, the one in force wearing `.on` in the accent. One chip at a time; All puts everything back; a chip for an empty group is not drawn. Chips are a view, never a setting: nothing is saved, and the list is whole again on the next open. Where a list is narrowed more than one way (a state and a release, R109), every group shares one band (`.lfilter`), side by side and wrapping group by group where the width runs out, never a row per group; a group scrolls sideways on a phone rather than wrapping into a block. Containers and VMs are grouped by the space their repository is in, never by the repository (the operator, 24 Nov): a space of several repositories is one group and one chip, each row naming its repository beside the space.

### pages-of-settings

Applies to: settings, profile, roles, users

**A page of settings is a list beside the one picked (the operator, 16 Oct).** A space's Settings, Controller settings and Profile draw their sections through `splitSects` (page-docs.js): a list of the sections, each its name and a line of what is in it, `unsaved` on it when it holds a change, beside the section picked, whose heading is a heading and not a fold, with its own Save and Revert. The Users and Roles pages are the same shape by hand (the operator, 17 Oct): Users lists the accounts beside the picked one's settings (its name, its roles and spaces, its profile and a new password, saved together), Roles lists the roles as one list, with no heading or field halfway down it and the spaces' owner roles folded into one row at its end, beside the picked role's kind and areas. Each page's add (Add user, New role) is the main action at the right of its bar and opens a dialog; Remove sits at the foot of the picked one's settings, under Save and apart from it. The picked row is lit (`--lit`). On a phone it is one column: the list, then the section or detail over it, its head the way back (a chevron before its name, the whole head the press; the operator, 19 Oct: a Back button of its own was a row spent over a head that never folds), sliding in from the right (`splitIn`, 32px over .26s on the menus' ease-out) and the list sliding back from the left (`splitBack`); no row stays lit on the list, since none is open there. Off under reduced motion. A section this account may not see is not listed. `uniform.mjs` measures the column beside the list at one x of its own.

### floating-cards

Applies to: card, section, band

**At a desk, content floats as cards; no line runs to the page's edge (R262, the operator, 17 Oct).** As Home and Spaces already were: a page-level section (on a page, the Docker manager, a notebook's view) is a card on the page's margin, the panel color, a hairline edge, the surface's radius and 12px between cards, its heading over a hairline inside it; a table straight on a page is a card; a run of rows straight on a page is one card, its rows divided inside it; a notebook's lists (bugs, roadmap, memory, tests, history) are cards; a page of settings and the Roles page are a list card beside a detail card; the Docker manager's group is a card headed by its space. A section inside a section, or inside a row (a node's card), stays a band in its card. The frame keeps its lines: the page's bar band, a notebook's header and its view strips. A band that only labels (a view's head row, a jump bar, Toolchains' store line) draws no line under it. A phone keeps the full-width bands (the operator: mobile is fine). `uniform.mjs` names any visible top or bottom border spanning a page from side to side at a desk.

### page-head

Applies to: bar, tiles, head, header

**Every page's top is one order (the operator, 17 Oct), each layer there only when the page has it.** First what the page says over everything, a notice, then the page's head with its status line, and then the control row (the operator, 29 Oct: the numbers first, then the search and the buttons over the list they act on; this order is the surface's own, set once in the stylesheet for every page and its placeholder, never in a page's markup): what the page is looking at that is not the group header's at the left (its search, a picker of its own), then at the right, in this order, its view switch (a .pseg), its upkeep buttons (Check for updates, Measure now, Check now, the trash), and last its main action, the one button that wears the accent fill (New container, Enroll node, Deploy, Add runner, New space, Add user); a destructive verb, where the row has one (the Library's Remove), comes after it, as on every action bar. The buttons sit inside an .actbar. The row is one control high on every page, everything in it centered on that line and a picker's word to its left rather than above it, and on a phone a search takes its first line whole with the switch and the buttons on the line under it. A page with nothing for that row has none, and a page whose only buttons are about its head puts them on the head's action row instead (Storage's Measure now, the CI runner's Add runner, a node's Test and Enroll script), never in a row of their own over a gap. A switch, an upkeep button and the main action never look alike: the switch is one joined control with its pick lifted and underlined, the upkeep button is the plain button, and the accent fill is the main action's alone. One wording for one verb across pages: a check of what is newer is Check for updates wherever it is, a new VM is New VM. No page has a Refresh: a page follows its revision tokens (a node's containers by the fingerprint each heartbeat carries, a disk walk by the census), so what a Refresh would fetch arrives by itself. The page's head (page-docs.js pageHead; the operator, 25 Oct: "if you're going to give info on a page, it should be in an organized and consistent way across all pages like how machines does it"), never loose words at the page's top: what the page is about as its name (the machine, the controller, the account), its state as pills beside the name, and its status line (the tiles rule: what is news, on one line). A fact that is not news is not in a page's head: it is said beside what it describes (a store's path at the foot of what is kept there, what Remove takes in Remove's own question), or not at all (R274, the operator 23 Nov: a head that listed every fact made the page read busier than it was, and a Details fold was one more kind of heading on pages that each have their own). A page about one thing (a machine, the install key, how the controller is reached) draws its facts as its body's grid under its head. A head with neither a name nor a line is not drawn. At a desk the head is a card of its own, as a node's head is on the Nodes page (the operator, 26 Oct): the cards' panel, hairline and corners, on the page's margin with the cards' gap above it. On a page of settings it runs over the list and the section both, the whole page's head with the list starting under it (the operator, 26 Oct), and on a phone over the list, unboxed as a node's head is there, gone once a section opens. A page's error is said in the notice voice (viewSaid), not as a head. Two kinds of chips, never alike and never swapped (the operator, 29 Oct): the filter chips, the big ones with counts that narrow a list (All, Installed, Updates, a space's), sit with the control row, under the search; the jump chips, the small ones that scroll to a section and filter nothing (a node's Health, Storage, Network), sit directly over the sections they lead to. Then the content's cards. A page's own card heading (Phone's connection, a node's card) is a card's, not the page's head, and keeps its card and its buttons. Every page's bar is the height of a space's header, --pbar-h (45px: its 32px controls and 6px above and below), so moving from a page to a space's notebook does not move the page under the bar (the operator, 17 Oct). A notebook's view strip runs the pane's whole width, as the header above it does; every band under it keeps the reading width. Under the strip each view's top is this order too (a-notebook/views, R109): its glance (tiles and status line), its control row, its chips.

### record-lists

Applies to: scripts/dashboard/tab-nginx.js, scripts/dashboard/tab-nodes.js, scripts/dashboard/tab-runner.js, scripts/dashboard/page-projsettings.js, scripts/dashboard/index.html; record, records, edit a row, add record, list of settings, routes, hostnames, mounts

A list of things a person keeps (nginx's routes, hostnames and certificates, a node's mounts and path mapping, a CI runner's runners, a space's reaches and extra nodes, and any list like them) is a list of records, the way Cloudflare's DNS page lists its records (the operator, 19 Oct): a table, a row a record, each row read-only in the table's columns with Edit at its right end. Edit opens that one row in place into its form under it, the fields the row's columns are, Delete at the form's left and Cancel and Save at its right; Save writes that record and folds the row back, Cancel folds it back unchanged, and one row is open at a time. Add (named for what it adds: Add route, Add hostname) is the band over the table and opens the same form at the table's top. A record list has no Save at its foot: each record is saved on its own. On a phone the row's columns stack under its first and Edit stays at the right of the first line. Not pills with Edit behind a menu, and not a column of always-editable fields.

As built (Perch step 43, the operator 17 Nov): a record's Save writes that one record at once, its list sent with it changed, and a section's own Save is for its other fields alone (a node's stores; Also sees); a node's mounts are still put on the node by Apply storage. A record with nothing on it to edit (a hostname, a node a space also works on, a certificate) has its bin on its row and no Edit. A CI runner's Edit opens its token and labels with its actions: Remove at the form's left, Forget token, Cancel, and Install or Reinstall as its primary. In order: nginx's Routes, Hostnames and Certificates; a node's mounts, path mapping and runners; a space's Also reaches and Also works on.

### pulldowns

Applies to: scripts/dashboard/page-*.css, scripts/dashboard/tab-*.js, scripts/dashboard/nb-*.js, scripts/dashboard/page-*.js; pulldown, select, picker, dropdown

A pulldown in a bar or a row of controls (a page's bar, a band over a list, a picker row, an add row, a grid cell of controls) is as wide as its longest answer and no wider (the operator, 18 Nov): it never grows into the room around it and a grid cell does not stretch it. Where its row runs short it shrinks, to a thumb's width (--tap) at least, its words clipped with an ellipsis; the controls rule's cap holds where a rule sets one. A form's field fills its cell (forms), and a group header's or a notebook's head sizes its own picker. A base select is as wide as the answer chosen, so fitPickers (page-docs.js) sets each one's width from itself with its longest answer chosen, as the page draws it; a rule in page-overrides.css keeps it from growing, and uniform.mjs measures every such pulldown against its longest answer on every page.

**A group header's node picker is as wide as the name it shows, in every browser** (the operator, 19 Nov: bb-sand… on a phone with room beside it). It is measured (`fitHeadPickers`): the name's ink at the header's face, its padding, and 52px for the closed picker's arrow, which each engine draws at a different width; left to the browser, Firefox on a phone and WebKit cut the name short. The header's own max-width still lets it give way to the pill beside it on a screen too narrow for both.

### connections

Applies to: scripts/dashboard/tab-settings.js, scripts/dashboard/page-projsettings.js, scripts/dashboard/tab-profile.js, scripts/dashboard/page-shell.js; connection, connect, integration, credential, cluster, discord, webhook, registry

Where a connection lives (the operator, 25 Nov: future-proof, and never convoluted in settings). A connection is a credential AerieOS holds for an outside service: a git host, a Kubernetes cluster, a Discord server, a registry, a cloud account, a chat or notification service. It is placed by whose it is and what it is for, and never gathered into a Connect or Integrations page of its own:

- **Shared by spaces** (a cluster, a registry, a runner's host): a page of the Machines group beside Nodes, an administrator's to add, granted instance by instance on the Roles page.
- **One space's** (its git host and remote, its Discord server, its deploy environments): a section of that space's settings, beside its repository's.
- **One person's** (their git token, their coding agents' sign-ins, their own notification channels): their Profile.
- **The install's own** (the bell's webhooks and email, the update channel): Controller settings.

Controller settings also holds the one list of every connection, **Connected services**: who added each, when it was last used and its expiry, so what the install can reach and with what is one list, each row linking to where the connection lives. It is read on Controller Read. Its one verb is Forget, an administrator's, for a credential that must go at once (a leak, a person gone); adding one and changing one happen only where it lives.

**Who may**, by the same table, so a new kind needs no new rule of its own: a connection spaces share is an administrator's to add and forget, and its use is granted instance by instance on the Roles page in an area of its kind (Clusters, as Nodes are); a space's own is connected and changed on Space settings Write on that space, and seen on Space settings Read, unless what it does is a daily verb of its own, which then has its own space area (Deploy for Kubernetes: Read sees its environments and logs, Write deploys, rolls back, restarts and scales); a person's own is theirs alone, never granted and never seen by another, administrators included; the install's own is Controller Write. A session never connects, changes or forgets one: it operates one only through relayed aerie verbs under its space's dial for that kind, and anything that removes, changes who may do what, or reaches people asks a person on the bell whatever the dial.

Every kind shares one mechanism underneath: the credential sealed and never shown again or handed to a session, Test and Forget, the Doctor's warning near expiry or on failure, a session reaching it only through relayed aerie verbs under a dial with anything destructive asked on the bell, and an audit row a call. A new kind of connection is a new row in the table above and a new place where its owner already looks, never a new page of settings.

### placement

Applies to: scripts/dashboard/tab-settings.js, scripts/dashboard/page-projsettings.js, scripts/dashboard/tab-profile.js, scripts/dashboard/tab-nodes.js, scripts/dashboard/tab-machine.js, scripts/dashboard/settings.py, scripts/dashboard/prefs.py; setting, settings, scope, scoped, default, override, placement

Where a setting lives (R294, the operator, 25 Nov: what is controller scoped, node scoped and space scoped each where it should be). A setting is placed by whose it is and what it is for, stored at that one scope and drawn on that one page, as a connection is (the connections rule):

- **The install's**: Controller settings, but for how the install is reached (the Network page) and, on an install with a machine of its own, everything about updating that machine (This controller: Updates, the update window, the older versions kept).
- **A node's**: its own Nodes page, each section's settings saved with that section; where the install sets a default every node goes by (Room), the node's own field is blank for the install's and says the install's value.
- **A space's**: the space's settings dialog, from its card; what every repository of the space shares is the space's, drawn on a repository's view dead with Open the space's settings.
- **A repository's**: its notebook's Settings and Permissions views; a dial (Agents may, Pushing, On the git host) is the space's default with "as the space (word)" first, and a repository's own where set.
- **A person's**: their Profile (You on the rail): who they are, their time zone, their terminal, their coding agents' sign-ins, where the bell reaches them; what is one browser's alone (its scheme, its own time zone) is the gear's.
- **A role's**: the Roles page.

A list of a scope's things on another page (a node's Spaces, a space's model router, Connected services) reads them and opens where each is set, and never sets it there. A setting moved to its place leaves a line where it was for one release saying where it went, and the changelog's Upgrading note says the same; a stored value whose scope changes is carried by a numbered migration. unit/test_one_place.py holds an install setting to one page and a space's settings apart from a repository's own.

## Pages

Each page is a layout of labeled blocks on a frame, named for what it is for, on the platform it is built for.

### the dashboard (Web app)

Platform: a responsive web app: the layout holds at phone and desktop widths, and every tap target is at least 44px on a coarse pointer.
Layout of the dashboard on a desktop frame (12 columns by 8 rows), from the App shell template, numbered in drawing order (a later block draws over an earlier one where they overlap):
  1. Sidebar (a side column): the rail: nine groups, an icon each, labels on a wide screen; the one on show lit, down the left, full height, column 1 of 12
  2. Header (the band at the top): the top bar: search, the bell, the doctor dot, the version, the gear, on the right, columns 2 to 12 of 12, row 1 of 8
  3. Content (the main reading or working area): the page on show: one of the nine groups or a space, each with its own address, on the right, columns 2 to 12 of 12, rows 2 to 7 of 8
  4. Footer (the band at the foot): the dock: the open terminals and the Claude chat as tabs, one line when shut, half the screen when pulled up, on the right, columns 2 to 12 of 12, row 8 of 8
Notes:
  The page is an app shell (R218, the operator, 14 Oct): one rail of groups, one page on show, one dock. What was a strip of tool tabs is the rail; what was a strip of document tabs is a page (a space) and the dock (terminals, chat); what was two panes side by side is a page with the dock pulled up. Every page is the same reading surface a document tab was (docSurface: a bar band, the band list, a quiet footer), with an address, so a reload and a shared link land on it. The page an account was on is remembered per account, as the strip was (R131). Home (R218 step 5): Home is the landing page and the one single-screen view: lead with the big numbers, five or six tiles, white space, and paths into every page (R218 step 5). It is a glance, not a place to act: a tile is a link, a row opens its page. Nothing on Home is a setting. As built (step 4, 14 Oct): the dock is the second pane at the page's foot (page-dock.js): a terminal goes to it and anything else is the page (dockPlace); dockSettle repairs a layout the strip saved; its bar is the line (.dockline: each terminal a .dtab with its session dot and −, Chat with its unread mark, +, the pop-out and the chevron); up is the grid row --dock-h (half the area to begin with, kept per browser as bb.dock and bb.dock.h, a drag on the line sets it); on a phone up is a sheet over the page and opening a page puts it down; on a phone the foot band is the hot bar of the terminal in front, its keys and Links, and is not drawn without one (the Keys panel and the Commands panel went on 12 Nov: the operator); the strip, its picker and the split are gone (page-tabstrip.js went; paint and newShell are page-paint.js).
This page's own rules:
  the-dashboard/document-tabs: scripts/dashboard/tab-*.js; tab, document, docsurface, bar (`aerie design show the-dashboard/document-tabs` reads it)
  the-dashboard/rail: Eleven groups, in this order (the operator, 19 and 22 Oct), each one press: Home, Spaces, Build (Library: everything a AerieOS installs or runs on a node as one page, the Toolchains, Agents and Apps pages as one, R170, the operator 28 Oct; Emulator, Phone), Containers (Containers, VMs: the operator, 18 Oct), Controller (Settings, a group of its own after Containers so a phone's four stay as they are, with room for the pages a bare-metal install and the USB edition add: the operator, 22 Oct), Machines (Nodes, Storage, Installed: what the Library put on one node and how each is set there, R172, the operator 28 Oct; nginx and Scanners, services a node has installed as the model router is, are its pages opened from their rows on Installed and from their containers' Configure, off its sub-nav: R264, the operator, 19 Nov, where they were the Containers group's, R181; CI runner, a node's service kept on the node's own row rather than Installed, so on the sub-nav after Installed: R294, the operator 25 Nov, where it was Build's; Files), Sessions, Jobs (Jobs, Schedules: an administrator's own cron, R117), People (Users, Roles), You (Profile, its last section the devices signed in as them: the operator, 19 Oct; named You on 25 Nov, R294, so Controller's Settings is the one thing called Settings and its icon a person's head), Help (AerieOS's own docs in the wiki's reader, with a search across them: R258, the operator 16 Oct). A group with several tools opens on the first and carries the rest as its page's sub-nav. The rail is one column of icons at the left edge, 56px wide, labels under the icons from 1280px up; the group on show wears the accent as a bar on its left edge and the label in --ink, the rest in --dim. A group a grant forbids is not drawn (the Nodes tab's rule, kept). Hovering shows the label on a narrow screen as a tooltip, never as the only way to read it: the labels are drawn at a desk. On a phone (under 900px) the rail is a bottom bar of five, the rail's first four, Home, Spaces, Build and Containers, and More, in the desk's order (the operator, 19 Oct: one order at both widths), sharing the width, More opening a sheet of the other seven in that order; the bar sits above the safe area and the dock's shut line sits above the bar.

As built (R218 step 2, on claude/design-2-0, 14 Oct): Home opens the Spaces page until Home is built (step 5); Sessions opens the panel the pane's Sessions button opens until the dock (step 4); Analysis sits under Spaces. A group a grant forbids is read off the account's areas (railAllows), since the sidebar went with step 3.
  the-dashboard/top-bar: One row over the page, 48px: the brand at the left, then search, then at the right the bell, the doctor dot, the version as plain text and the gear. Search is a field that jumps: a page by its name, a space, a container, a node, each a row with its icon and where it lives, the first on Enter; it does not search inside notebooks (later, its own item). The bell, the doctor dot and the gear are the ones the page has (the bell's drawer, the doctor's panel, the gear's menu). The build stamp and uptime that stood in the header go to Settings: the top bar carries what is pressed or watched.

As built (R218 step 3, 14 Oct): the doctor dot (#bDocDot) sits after the bell in the bell's manners, its color the worst check's (accent, --warn, --bad; --line before a verdict), and opens #docPanel shaped like the bell's: Doctor, when it last ran and ↻ on one line, the problems as lines in their level's color, each saying what is wrong up to its first aside (a semicolon, a bracket), and the passing checks counted in a quiet line (the operator, 17 Nov: the panel compact, the full checks, with what each said, its fix and the passing ones as chips, being Controller settings' Controller section, which Controller settings at the panel's foot opens; an account that cannot open that page has the full checks in the panel). Anything else closes it, Escape closes it. Under 600px Report a bug and Sign out move into the gear's menu, below Profile: six buttons a thumb wide left the search a sliver at 344px (B744), and the search keeps at least 80px at every phone width. The three pop-outs under the top bar, the bell's, the doctor's and the gear's, are one shape (the operator, 22 Oct): one width (400px at most), anchored under the header, a title band on top (.popbar: Notifications with See all, Doctor with when it ran and its run, Preferences), banded section heads in the tag voice (.bgroup, the gear's h4), a height that scrolls inside with the band held, and on a phone each runs to the same 8px edges over the page, which is not dimmed under it (the operator, 23 Oct: it read as a dialog, which none of the three is); its shadow and its edge say where it ends.
  the-dashboard/pages: A page is what a document tab was: a reading surface built by docSurface (the bar band, the band list, the quiet footer), capped at --doc-w and centered in the content area, with the bar's rule kept (what the page is about at the left, the action on it at the right). Each page has an address under #/ (#/containers, #/projects/web/roadmap, #/machines/nodes/n_12ab) and the address is the page: a reload, a shared link and the back button all land on it, and openDocker() and its siblings route to it. A page subscribes to its own revision tokens on the one revisions poll (when-a-view-re-reads) and fetches what it draws from the status read split by page, nothing for the pages not on show; the poll backs off to five seconds after a minute with nothing moved and to thirty while the page is hidden. There is no strip and no second pane: two things side by side are a page and the dock.

As built (step 2): a page is still a tab in the page's tab model, kept out of the strip (isToolKind), so the panes, the per-account layout and every opener work as before; its bar is the group's sub-nav (a .pseg of the tools), one button in the accent for a page that stands alone (the operator, 16 Oct: a bare word read as a different kind of page), with no close. The address is #/group, #/group/tool or #/projects/NAME, replaced on each draw and pushed on a rail press; the status read's split waits for step 3.
  the-dashboard/dock: The dock is the foot of every page: one line when shut, naming the chat and the open terminals as tabs with their session dots, the line fading at either edge with more tabs past it (the operator, 16 Oct), Chat first since it is always there while terminals come and go (the operator, 15 Oct), and the page keeps its full height; pulled up it takes half the screen (a drag on its edge or a press on a tab) and the page scrolls above it. Its tabs are what the tab strip's terminals and the Sessions and Chat buttons were: a Claude session, a shell, the chat, each closed from its tab the way a terminal tab closed, and a session's end closes its tab as before. A Shell on a container's row opens docker exec in a dock tab, gated by the space's Run its container dial. On a phone the dock is a sheet from the bottom edge, the full width of the screen and the whole height between the header and the bottom bar when open (over the page and its sub-nav), its line on the bottom bar when shut (the operator, 16 Oct). On a phone the page's box itself runs to both edges of the screen and meets the header and the bottom bar with no gap, so what scrolls goes under them; at a desk it keeps its gutter and its border. Which tabs are open is the account's, as the strip was; which is in front and whether the dock is up are the browser's.

As built (step 4, cut 2, 14 Oct): a running instance's row on the Containers page carries Shell for its first running container and Shell in SERVICE for the rest under More; each opens a terminal tab in the dock (argument ctr:NAME:INSTANCE:CONTAINER, label "in CONTAINER"). Who may: a person who may start and stop that container with a shell, an administrator alone when its space's Run its container is Deny (the operator, 14 Oct). Dead, with the reason under the row, on a hosting-only node (no terminal there; there and on the controller's own machine no Shell is drawn, and the Containers page's head says so once under Shells) and under Deny for anybody else. On a node the shell is the agent's container terminal, on its screen relay's port (7684, the controller's only), as the docker account, since the session account is kept off docker (the operator, 14 Oct).
  the-dashboard/home: Five or six tiles across the top (the tiles rule), each a number across the whole install with its label under it, a tone when the number itself is news (failed jobs in --bad when any, updates due in --warn), and each a link into the page that holds the number: nodes online of enrolled, containers running of all, jobs running and failed today, sessions open, updates due (toolchains, images, nginx, the agent), CI red. Under them two cards side by side at a desk, stacked on a phone: Attention (the bell's rows, put away there as on the bell) and Last jobs (ten rows, state pill, when, the Jobs page's row on press). Under those, Favorites: a small card per space this person has starred (the operator, 17 Nov: favorites, each person's, where pins were) with its session dot, its branch and the one notice a space's card carries (no node, restart to use what changed), the full card on the space's page. Home reads on open and on the tokens the tiles depend on; nothing on it polls on its own.

As built (R218 step 5, 14 Oct): page-home.js and /api/home (home.py). The tiles: nodes online of enrolled and containers running of all (only for an account that reads the Nodes area; a node that does not answer within eight seconds counts as unknown and the tile says "as last seen"), jobs running with the ones failed today (bad) or waiting under it, sessions open (claude_where), updates due (the attention rows, each toolchain behind counted), CI red. A tile opens its page (CI red, the first red space's Git view). Attention is the bell's own rows (needsRows) with Dismiss and Show again; Last jobs opens a job's row on the Jobs page with its log open and marked (openJob). Favorites is this person's favorite spaces, each its name (opening its page), branch, session state and one notice. It reads /api/home whole on open and light (the queue and the node counts, the containers kept) on the jobs token; not on the nodes token, which moves with every check-in and would make Home a poll. It redraws from the poll, painted only when it changed. A fresh browser with no page on show lands on Home.
  the-dashboard/notifications: scripts/dashboard/page-bell.js, scripts/dashboard/page-notices.js; toast, toasts, notification, notifications, bell, notice, notices (`aerie design show the-dashboard/notifications` reads it)
  the-dashboard/library: scripts/dashboard/tab-library.js, scripts/dashboard/library.py, scripts/dashboard/test/library.mjs; library, card, cards, store, sideload, sideloaded, add your own, tier (`aerie design show the-dashboard/library` reads it)
  the-dashboard/installed: scripts/dashboard/tab-installed.js, scripts/dashboard/test/installed.mjs; installed, configure, sign-in, remove, machines (`aerie design show the-dashboard/installed` reads it)
  the-dashboard/group-header: scripts/dashboard/page-shell.js, scripts/dashboard/tab-nodes.js, scripts/dashboard/tab-storage.js, scripts/dashboard/tab-installed.js, scripts/dashboard/tab-library.js, scripts/dashboard/tab-emulator.js, scripts/dashboard/tab-phone.js, scripts/dashboard/tab-docker.js, scripts/dashboard/tab-nginx.js; group header, machines header, node picker, ndpick, unavailable, not here (`aerie design show the-dashboard/group-header` reads it)
  the-dashboard/pages-a-press-opens: scripts/dashboard/page-shell.js, scripts/dashboard/tab-docker.js, scripts/dashboard/tab-installed.js, scripts/dashboard/tab-thing.js; back, configure, system section (`aerie design show the-dashboard/pages-a-press-opens` reads it)
  the-dashboard/restart-and-update: scripts/dashboard/page-poll.js, scripts/dashboard/page-welcome.js, scripts/dashboard/page-boot.js; restart, restarting, updated, what changed, away (`aerie design show the-dashboard/restart-and-update` reads it)

#### Rules of the dashboard's own

##### the-dashboard/document-tabs

Applies to: scripts/dashboard/tab-*.js; tab, document, docsurface, bar

What a page's surface is, kept from the document tabs: Reading surfaces, not terminals. A new kind does not write its own chrome: it
calls `docSurface(i, kind)`, which builds the standard skeleton (a
`.doctab.<kind>tab` box capped at `var(--doc-w)`: a filter/actions bar slot,
the band list, a quiet `.fnote` footer) and returns the slots to fill. The footer carries what the page knows and the bands do not (when its reports were read, what was counted aside), never an explanation of the page: how a page works is the docs' to say (the operator, 16 Oct), so a page with nothing of that kind has no footer. States
are `.loading` (a `skel()` in the shape of the rows to come) / `.empty` /
`.hint.bad` inside the list.

**The bar is a band, not a row of controls.** What the tab is about goes at
its left (a node picker, the filters, a one-line count) and the action on
it at the right, where a row's buttons and a section's status already sit, so
every tab's buttons are in one place and line up with the column of actions
under it. The band spans the tab; the controls in it are capped one by one
like any other. A tab that builds its own chrome instead misses all of this:
the Toolchains tab kept its picker in a band of its own and its buttons landed
somewhere no other tab's does.

A new tab lands as: its own classic script file beside `index.html`, an entry
in `TABKINDS` there and `TAB_KINDS` in `server.py`, its top-level names in
`test/surface.mjs`, a driver in `test/uniform.mjs`, and a content test beside
its siblings. Renderers run inside `renderGuarded`, so a throwing renderer is
an error band in its own tab, never a dead dashboard.

**Which tabs are open is the account's; what is in front is the browser's.** Which
tabs are open is saved on the server per account, so a phone and a desk
have the same strip; which tab is in front, and which tab each pane
holds, are each browser's own, kept on the device the way a phone's
folded cards are, so switching tabs on the phone leaves the desk where it
was (R131).

##### the-dashboard/rail

Eleven groups, in this order (the operator, 19 and 22 Oct), each one press: Home, Spaces, Build (Library: everything a AerieOS installs or runs on a node as one page, the Toolchains, Agents and Apps pages as one, R170, the operator 28 Oct; Emulator, Phone), Containers (Containers, VMs: the operator, 18 Oct), Controller (Settings, a group of its own after Containers so a phone's four stay as they are, with room for the pages a bare-metal install and the USB edition add: the operator, 22 Oct), Machines (Nodes, Storage, Installed: what the Library put on one node and how each is set there, R172, the operator 28 Oct; nginx and Scanners, services a node has installed as the model router is, are its pages opened from their rows on Installed and from their containers' Configure, off its sub-nav: R264, the operator, 19 Nov, where they were the Containers group's, R181; CI runner, a node's service kept on the node's own row rather than Installed, so on the sub-nav after Installed: R294, the operator 25 Nov, where it was Build's; Files), Sessions, Jobs (Jobs, Schedules: an administrator's own cron, R117), People (Users, Roles), You (Profile, its last section the devices signed in as them: the operator, 19 Oct; named You on 25 Nov, R294, so Controller's Settings is the one thing called Settings and its icon a person's head), Help (AerieOS's own docs in the wiki's reader, with a search across them: R258, the operator 16 Oct). A group with several tools opens on the first and carries the rest as its page's sub-nav. The rail is one column of icons at the left edge, 56px wide, labels under the icons from 1280px up; the group on show wears the accent as a bar on its left edge and the label in --ink, the rest in --dim. A group a grant forbids is not drawn (the Nodes tab's rule, kept). Hovering shows the label on a narrow screen as a tooltip, never as the only way to read it: the labels are drawn at a desk. On a phone (under 900px) the rail is a bottom bar of five, the rail's first four, Home, Spaces, Build and Containers, and More, in the desk's order (the operator, 19 Oct: one order at both widths), sharing the width, More opening a sheet of the other seven in that order; the bar sits above the safe area and the dock's shut line sits above the bar.

As built (R218 step 2, on claude/design-2-0, 14 Oct): Home opens the Spaces page until Home is built (step 5); Sessions opens the panel the pane's Sessions button opens until the dock (step 4); Analysis sits under Spaces. A group a grant forbids is read off the account's areas (railAllows), since the sidebar went with step 3.

##### the-dashboard/top-bar

One row over the page, 48px: the brand at the left, then search, then at the right the bell, the doctor dot, the version as plain text and the gear. Search is a field that jumps: a page by its name, a space, a container, a node, each a row with its icon and where it lives, the first on Enter; it does not search inside notebooks (later, its own item). The bell, the doctor dot and the gear are the ones the page has (the bell's drawer, the doctor's panel, the gear's menu). The build stamp and uptime that stood in the header go to Settings: the top bar carries what is pressed or watched.

As built (R218 step 3, 14 Oct): the doctor dot (#bDocDot) sits after the bell in the bell's manners, its color the worst check's (accent, --warn, --bad; --line before a verdict), and opens #docPanel shaped like the bell's: Doctor, when it last ran and ↻ on one line, the problems as lines in their level's color, each saying what is wrong up to its first aside (a semicolon, a bracket), and the passing checks counted in a quiet line (the operator, 17 Nov: the panel compact, the full checks, with what each said, its fix and the passing ones as chips, being Controller settings' Controller section, which Controller settings at the panel's foot opens; an account that cannot open that page has the full checks in the panel). Anything else closes it, Escape closes it. Under 600px Report a bug and Sign out move into the gear's menu, below Profile: six buttons a thumb wide left the search a sliver at 344px (B744), and the search keeps at least 80px at every phone width. The three pop-outs under the top bar, the bell's, the doctor's and the gear's, are one shape (the operator, 22 Oct): one width (400px at most), anchored under the header, a title band on top (.popbar: Notifications with See all, Doctor with when it ran and its run, Preferences), banded section heads in the tag voice (.bgroup, the gear's h4), a height that scrolls inside with the band held, and on a phone each runs to the same 8px edges over the page, which is not dimmed under it (the operator, 23 Oct: it read as a dialog, which none of the three is); its shadow and its edge say where it ends.

##### the-dashboard/pages

A page is what a document tab was: a reading surface built by docSurface (the bar band, the band list, the quiet footer), capped at --doc-w and centered in the content area, with the bar's rule kept (what the page is about at the left, the action on it at the right). Each page has an address under #/ (#/containers, #/projects/web/roadmap, #/machines/nodes/n_12ab) and the address is the page: a reload, a shared link and the back button all land on it, and openDocker() and its siblings route to it. A page subscribes to its own revision tokens on the one revisions poll (when-a-view-re-reads) and fetches what it draws from the status read split by page, nothing for the pages not on show; the poll backs off to five seconds after a minute with nothing moved and to thirty while the page is hidden. There is no strip and no second pane: two things side by side are a page and the dock.

As built (step 2): a page is still a tab in the page's tab model, kept out of the strip (isToolKind), so the panes, the per-account layout and every opener work as before; its bar is the group's sub-nav (a .pseg of the tools), one button in the accent for a page that stands alone (the operator, 16 Oct: a bare word read as a different kind of page), with no close. The address is #/group, #/group/tool or #/projects/NAME, replaced on each draw and pushed on a rail press; the status read's split waits for step 3.

##### the-dashboard/dock

The dock is the foot of every page: one line when shut, naming the chat and the open terminals as tabs with their session dots, the line fading at either edge with more tabs past it (the operator, 16 Oct), Chat first since it is always there while terminals come and go (the operator, 15 Oct), and the page keeps its full height; pulled up it takes half the screen (a drag on its edge or a press on a tab) and the page scrolls above it. Its tabs are what the tab strip's terminals and the Sessions and Chat buttons were: a Claude session, a shell, the chat, each closed from its tab the way a terminal tab closed, and a session's end closes its tab as before. A Shell on a container's row opens docker exec in a dock tab, gated by the space's Run its container dial. On a phone the dock is a sheet from the bottom edge, the full width of the screen and the whole height between the header and the bottom bar when open (over the page and its sub-nav), its line on the bottom bar when shut (the operator, 16 Oct). On a phone the page's box itself runs to both edges of the screen and meets the header and the bottom bar with no gap, so what scrolls goes under them; at a desk it keeps its gutter and its border. Which tabs are open is the account's, as the strip was; which is in front and whether the dock is up are the browser's.

As built (step 4, cut 2, 14 Oct): a running instance's row on the Containers page carries Shell for its first running container and Shell in SERVICE for the rest under More; each opens a terminal tab in the dock (argument ctr:NAME:INSTANCE:CONTAINER, label "in CONTAINER"). Who may: a person who may start and stop that container with a shell, an administrator alone when its space's Run its container is Deny (the operator, 14 Oct). Dead, with the reason under the row, on a hosting-only node (no terminal there; there and on the controller's own machine no Shell is drawn, and the Containers page's head says so once under Shells) and under Deny for anybody else. On a node the shell is the agent's container terminal, on its screen relay's port (7684, the controller's only), as the docker account, since the session account is kept off docker (the operator, 14 Oct).

##### the-dashboard/home

Five or six tiles across the top (the tiles rule), each a number across the whole install with its label under it, a tone when the number itself is news (failed jobs in --bad when any, updates due in --warn), and each a link into the page that holds the number: nodes online of enrolled, containers running of all, jobs running and failed today, sessions open, updates due (toolchains, images, nginx, the agent), CI red. Under them two cards side by side at a desk, stacked on a phone: Attention (the bell's rows, put away there as on the bell) and Last jobs (ten rows, state pill, when, the Jobs page's row on press). Under those, Favorites: a small card per space this person has starred (the operator, 17 Nov: favorites, each person's, where pins were) with its session dot, its branch and the one notice a space's card carries (no node, restart to use what changed), the full card on the space's page. Home reads on open and on the tokens the tiles depend on; nothing on it polls on its own.

As built (R218 step 5, 14 Oct): page-home.js and /api/home (home.py). The tiles: nodes online of enrolled and containers running of all (only for an account that reads the Nodes area; a node that does not answer within eight seconds counts as unknown and the tile says "as last seen"), jobs running with the ones failed today (bad) or waiting under it, sessions open (claude_where), updates due (the attention rows, each toolchain behind counted), CI red. A tile opens its page (CI red, the first red space's Git view). Attention is the bell's own rows (needsRows) with Dismiss and Show again; Last jobs opens a job's row on the Jobs page with its log open and marked (openJob). Favorites is this person's favorite spaces, each its name (opening its page), branch, session state and one notice. It reads /api/home whole on open and light (the queue and the node counts, the containers kept) on the jobs token; not on the nodes token, which moves with every check-in and would make Home a poll. It redraws from the poll, painted only when it changed. A fresh browser with no page on show lands on Home.

##### the-dashboard/notifications

Applies to: scripts/dashboard/page-bell.js, scripts/dashboard/page-notices.js; toast, toasts, notification, notifications, bell, notice, notices

What the page says to a person is a system, not a box that flashes (R218 step 6, the operator, 14 Oct). A toast is one of a stack at the bottom left of the page, beside the rail and above the dock's line (on a phone, the width of the screen above the dock's line), the newest at the foot and at most four: the corner with the fewest controls on a page, since a row's actions are at its right and a view's and a page bar's at their right ends. It stays there while a dialog is open (the operator, 24 Oct: a stack that moved with a dialog read as a jump), above the dialog's backdrop, and a toast in the way of a press is put away by its own ×. On a touch screen a toast lets a tap through but for its ×, each with its kind's icon (information, a warning, a failure), its words and its own ×; it goes after four seconds, seven for a warning or a failure, and its clock stops while the pointer is over the stack, so nothing leaves mid-read. A job started from the page has a toast of its own that stays while the job runs, its line the job's state and step, and takes the outcome's tone when it ends; newer toasts push out the oldest of the others, not it. Every toast is also on the record: the bell's latest for the page, and the account's notices on the server (notices.py), kept across reloads and browsers, newest first, the latest 300.

The bell's panel is two sections (R280, the operator, 24 Nov). **Active**: what waits on an answer pinned at its top in gold, every ask queued listed, then invitations and held changes, then what blocks work now (a failing CI run, a session an outage held or whose hooks went quiet, a disk failing or a pool down, a UPS low or on battery, an agent out of its window, a second factor required); none of it has a Dismiss, and each leaves when it is answered or stops being true. **Earlier**: an ask answered or expired, plain and no longer gold, saying how it went and when; what can be put away (an update waiting, a release missing a file) with its Dismiss, its bar in the line's color and not the gold, since nothing under Earlier waits on you; and the five latest of what the page said, Clear at the section's head clearing those. Each section is headed with its count, and See all is at the panel's head.

The Notifications page is at #/notifications, on no group of the rail; See all opens it. Active comes first, drawn only while something is in it (and then, on a phone, the one section open): every ask, invitation and held change, each a row whose Approve and Deny (Accept and Decline, Review) are on the row, at every width, and whose long part (a compose file, the lines a push flagged, a release's notes) is whole in a box that scrolls inside itself behind a fold (the nothing-acted-on-in-a-fold rule); then what blocks work now, the bell's own rows. Nothing in Active has a ×. History follows: the account's notices, each a row with its kind's icon, its words, its kind and when, its own × to delete it, and a Job button when it is about one; chips narrow it (Said, Answers, Jobs, Failures), and Clear history empties it, or Clear with the chip in force, asked first: it is the page bar's action and names History, since Active is never cleared. An answer to an ask, from the bell or the page, is kept as an answer.

**On a phone a toast sits just above an open dialog's buttons.** A dialog there is the whole screen and covers the dock's line the stack sits above, so the stack moves to just above the dialog's foot while one is open, and back when it goes (the operator, 18 Nov: it floated over the dialog's words half way up). At a desk, where a dialog is a box over the page, the stack stays where it was.

##### the-dashboard/library

Applies to: scripts/dashboard/tab-library.js, scripts/dashboard/library.py, scripts/dashboard/test/library.mjs; library, card, cards, store, sideload, sideloaded, add your own, tier

For the dashboard. The Library (R170, the operator, 28 Oct: one place for everything a AerieOS installs or runs, not a page each for toolchains, agents and apps, and it should look nice) browses as a store: one node picked in the bar, Check for updates and Add your own (the accent) at the bar's right, the node's head (installed of offered, the store and its free space), then one band with the search (by name, maker or what it does) and the kind chips (Installed and Updates first after All, each drawn while it has cards, then Coding agents, Toolchains, Tool packs, Services, Apps, For you, Tool packs left out while there are no packs) and the tier chips (Packaged by Aerie, Verified, Vetted, Sideloaded, the words for who stands behind a card's pack; Packaged, not Built, since the tool is somebody else's (the operator, 12 Nov): what AerieOS ships or its maintainers wrote the pack for, a verified vendor's own pack, anybody's pack the maintainers reviewed, and what a person added themselves, the operator, 12 Nov, in place of official and vetted; the same words lowercase on a card's tier pill, Verified and Vetted in --ok; drawn only when two tiers are present),, and on a line under the search the Topic pulldown (the catalog's fixed list, each with its count, a topic with nothing under the rest left out), the order (By name, or Best match while something is typed, and Recently added) and Cards or Rows at its right. **However big the catalog grows the page stays navigable (R256, the operator, 18 Nov)**: the server narrows, counts and pages it, and the page never holds the whole catalog. With nothing typed and no chip or topic on, the page is shelves: On this node first (what is installed, updates first), then a shelf per kind, each a heading in the section voice with its count in --f-note and All N › at its right where it holds more than it shows, over at most eight cards (Packaged by Aerie first, then the newest, then by name). A chip, a topic or the search is one sorted list instead, through paginate a page of 30 at a time ('60 of 340 apps'), the whole narrowing in the page's address (#/build/library/NODE?kind=app&topic=media&q=...) so Back, a reload and a link land on it. Every count is the server's under the other narrowings. What runs only on other systems is left out of a list and said in one line over it (N more run only on other systems than NODE's, Show them); shown, each such card says not for this node in its state with its Install dead. Cards are the Spaces page's grid (270px columns, 12px apart, one column on a phone); Rows put each card on one line (its name and pills, what it is cut to one line, where it stands and its verb), the default for a list on a phone until somebody picks; on a phone a row is two lines (the operator, 19 Nov), the name and Details across the card, then who made it and its pills beside the verb, faded where they run out, what it is and where it stands left to its page. Anything else a card carries (the driver's version, a failed job's words) is a line of its own under a row, never a column beside the name. A card is its kind's glyph in a 36px rounded square tinted with the accent at the top left, the name beside it in the card's name size with its pills under the name (the tier on every card; the installed version; an update as a --warn pill naming what is out; dev where it is), what it is in two lines ellipsized, and a foot in the action-bar's shape: where it stands at the left in --f-note (installed in --ok, update available in --warn, the job's word with the dots while one writes it, nothing when there is nothing to say), Details as a plain underlined link, then the one verb (Install in the accent on every card, as Update is (the operator, 1 Nov: one look for every Install, Claude Code's no longer apart), Update in the accent, New container in the accent on an app since an app is made as a container and each press makes another, Edit on a pack or an app a person added themselves, the sideloaded ones, and never on one kept from the catalog (the operator, 12 Nov: no Edit on Gemini's card), whose kept copy is reached from the source line of its Details page as a plain link, Look for a newer pin, or remove it; Download on a companion; never Remove, which is the Installed page's). Details opens the entry's own page (R183, the operator, 29 Oct; the pages-a-press-opens rule: its small top header's Back, its address #/build/library/NODE/KIND:NAME, its head the card's glyph or icon, its name, its pills and its one verb) on the catalog's entry alone, the card no longer opening in place (the operator, 28 Oct: the Library is the catalog, what is installed is managed on Installed under Machines): what it is in full, platforms, terms, size and source, what it asks for per node, a pack's Look drawn in place, an app's compose file in a scrolling mono block with its blanks named, a companion's files; never a sign-in, a node's lines or a Configure. A failed job's words sit under the card's description in --bad. The catalog's trouble is said over the Tool packs, never in the node's head; over them too the link to submit a pack to the vetted catalog. No jump bar: the kind chips are the page's groups.

##### the-dashboard/installed

Applies to: scripts/dashboard/tab-installed.js, scripts/dashboard/test/installed.mjs; installed, configure, sign-in, remove, machines

For the dashboard. The Installed page (R172, the operator, 28 Oct: a thing is configured where it is installed, not in the catalog) is under Machines beside Nodes and Storage: the node picker alone in its bar, the node's head (installed, updates due, the store), then a section per kind with anything on the node (Coding agents, Toolchains, Tool packs, Services; never apps or companions; a pack that brings a coding agent is a row under Coding agents, as the Library files its card: the operator, 12 Nov), each a list of rows in the rows-you-open shape: the name with the installed version as a pill and an update as a --warn pill, Open as a plain underlined link beside the name, what it is in one ellipsized line, and at the right where it stands in --f-note (installed in --ok, update available or a state that needs a restart in --warn, the job's word with the dots while one writes it) and the verbs the Library does not carry: Remove in the danger tone, Edit on a pack, Install on a configured service. Open, and Configure where it asks for anything, opens the thing's own page on the node's side of it (R181 step 2, the operator, 29 Oct; the pages-a-press-opens rule), whose sections hold: an agent's facts, this person's sign-in block and what they added to the agent (a pack's agent, which signs in in its own session's terminal, says so there in the note voice), a toolchain's path, system packages with Install them now, needs, how its download was checked and who started before it landed, the machine's own driver and toolkit in the census's words, and Configure, the fields the manifest's config block names drawn as a form (a secret as a password field reading set: type to replace, or clear; a list as rows with Add a row; spaces as chips) with Save at its foot, which rebuilds a deployed service. A job's error sits under the row in --bad. Over the rows, the system packages the node lacks with the one press that installs them. No jump bar.

##### the-dashboard/group-header

Applies to: scripts/dashboard/page-shell.js, scripts/dashboard/tab-nodes.js, scripts/dashboard/tab-storage.js, scripts/dashboard/tab-installed.js, scripts/dashboard/tab-library.js, scripts/dashboard/tab-emulator.js, scripts/dashboard/tab-phone.js, scripts/dashboard/tab-docker.js, scripts/dashboard/tab-nginx.js; group header, machines header, node picker, ndpick, unavailable, not here

For the dashboard. The Machines, Build and Containers groups each wear one header over their sub-nav (R177, R178, the operator, 28 Oct: a header like a space's, with the node pulldown there instead of on each sub-tab). The pane's bar for every page of such a group is one band in the space header's shape (.bar.page.grouped .phead, page-shell.js groupHeader): the node picker (nodePick, id ndPick) where a space's name is and in its type (600, 1.15rem), drawn plain with its chevron and boxed only when hovered or focused, its word Node kept for a reader of the page alone (the operator, 29 Oct: drawn as a notebook's header), No node yet in the name's place when none is enrolled, and beside it the node's state as one pill (online, not answering, draining or disabled, waiting for enrollment: nodeState), a press that opens the node's own page on Machines' Nodes from any page of the group (the operator, 17 Nov: the facts line it replaced, seen, dials in from and its agent's version, took a phone's second and third lines, and they are on the node's page), the picker giving up width before the pill, the head one row of --ghead-h (44px), a little taller than the tab row under it, at a desk and on a phone; and under it, in a band of its own under a rule the pane's whole width, in the notebook view strip's type (600 12px), one height on every page with an action in it or not (--tabrow-h, 40px, the height a page standing alone such as Home and Spaces has too), the group's sub-nav strip at the left and the group's own actions at the right (Machines: New VM and Enroll node, dead with the enroll feature off, the reason on the Nodes page; Build and Containers carry none there: each page's actions are its own, under its head and tiles in the page-head rule's order: the Library's Check for updates, Add your own and Remove on the search's line, the Containers page's search with its cards-or-list segment, Check for updates and New container, the CI runner's Add runner and Storage's Measure now on their head's action row, the Phone's Check now on its phone's row; no page's bar carries a button over a gap, and no sub-tab says the node's name again under the header that names it). A page of such a group about no one node (Clusters, R281) wears the group's name where the picker stands, in the same type, with no pill: there is no node to pick for it. One pick drives every page of the group, which keeps one node (the operator, 29 Oct: GROUP_CUR, kept in the browser per group): groupPick sets each page's node through NODE_SET and redraws, a page whose own node differs is moved to the group's as it is drawn, and a page an opener sent to a node of its own takes the group with it; a pick is a history entry, so no page carries a picker of its own. A sub-tab whose feature the picked node lacks is drawn unavailable (toolOff): its label in --dim with the word not here after it in --f-note and the reason as its title, still a press; the page says the same and offers the one thing that makes it available (nginx not deployed: Deploy; no Docker on the node; no Android tools or adb: the Library; no CI runner yet: Add runner). A list not read yet marks nothing. The boot template (bootPage) draws each group's band with the picker's placeholder and, for Machines, the two actions dead. The address stays #/GROUP/VIEW/NODE.

##### the-dashboard/pages-a-press-opens

Applies to: scripts/dashboard/page-shell.js, scripts/dashboard/tab-docker.js, scripts/dashboard/tab-installed.js, scripts/dashboard/tab-thing.js; back, configure, system section

A page reached by a press rather than by its tab (R181, the operator, 29 Oct: nginx and Scanners, from Configure on their containers' rows) is off its group's sub-nav and wears a small top header in its place: Back, a quiet button with a chevron naming the page it was opened from, then a slash and the page's own name in --ink. Back opens the address it was opened from, as a press would, whatever the browser's own history holds, and a page opened by its address alone goes back to its group's first page. Its address, its grant and its node picker are as they were. On the Containers page, the containers AerieOS deploys itself are the System section pinned above every space's, each row exactly any container's row with one press more, Configure, where it has a page of its own; its env and compose file are that curated page's, never the row's. An installed thing's own page is one of these (R181 step 2, the operator, 29 Oct: every installed tool, pack, plugin and agent): Open on its Installed row, and Configure where it asks for anything, open it at #/machines/installed/NODE/KIND:NAME, its head the thing's name with where it stands as its pill, the node and the version as facts and its verbs at the right, then its sections from one table per kind (What it is; an agent's Your sign-in and Yours; a pack's or a service's Configure with Save), each open; the Installed row stays a row and opens nothing in place. That table is where a later plugin system would add a pack's own sections. A Library entry's page is another (R183): Details on its card opens it, the catalog's entry alone, never a sign-in or a node's lines.

**nginx and the Scanners are services** (R264, the operator, 19 Nov): each has a card under Services in the Library, where Install puts it on the node picked, and a row under Services on that node's Installed page once it is there, where Open leads to its own page (the nginx page, the Scanners page) and Remove takes it off, said in the service's own words for what is kept. Those pages are pages of the Machines group at #/machines/nginx and #/machines/scanners, their addresses under Containers still opening them; Back on one opened by its address alone is to Installed. Configure on their containers' rows in the System section opens the same pages.

##### the-dashboard/restart-and-update

Applies to: scripts/dashboard/page-poll.js, scripts/dashboard/page-welcome.js, scripts/dashboard/page-boot.js; restart, restarting, updated, what changed, away

The page across a controller restart is one calm state, said on purpose (Perch, the operator 13 Nov). Reads that stop landing after the page had been reading are a restart for 90 seconds: the page stays drawn as it was, one band under the header in the note voice (#awayBand: AerieOS is restarting, N seconds so far) with a 3px bar of --note, the brand in --dim and the doctor's dot in --line, the presses of the page and the dock dead (pointer-events none at .55), and the status asked for every two seconds. Past the grace, for a page that never read, and for a page failing on an answer, it is the red light and the red line with its reason, as before. A new run reloads the page, which paints its kept copy of the first pane (inert, no ids) where the placeholder's shapes went until the first read draws it, its scroll put back. A build the account has not seen is one line under the header (#updatedBand, --panel, --ink): Updated to VERSION and What changed, which opens the changelog; the next press elsewhere puts it away and acknowledges it. The changelog never opens by itself.

### a notebook (Web app)

Platform: a responsive web app: the layout holds at phone and desktop widths, and every tap target is at least 44px on a coarse pointer.
Layout of a notebook on a desktop frame (12 columns by 8 rows), from the Blank template, numbered in drawing order (a later block draws over an earlier one where they overlap):
  1. Tabs (a strip of tabs switching one area): the views: Briefing, Design, Roadmap, Bugs, Git, Artifacts, Docker, Tests, Analysis, across the top, row 1 of 8
  2. Content (the main reading or working area): the view, across the middle, rows 2 to 7 of 8
  3. Header (the band at the top): the head row: its one-line summary on the left, its controls and History on the right, at one height on every view, across the middle, row 2 of 8, inside block 2 (Content: the view)
  4. Form (fields a person fills in): the add bar: the first band under the head row, a button named for what it adds, its form unrolling in its place, across the middle, row 3 of 8, inside block 2 (Content: the view)
  5. List (rows of like things): the sections: folds with their count on the title, each remembered open or shut; rows that open on a slide, across the middle, rows 4 to 7 of 8, inside block 2 (Content: the view)
Notes:
  A space is a page (R218 step 3): the notebook's views are its sub-nav and the space's card is its header. Until R218 step 3 lands, the notebook is a document tab with the views as its strip; after it, this page is 'a space'. The Spaces page is the grid: a card per space with its session dot, branch, node and the one notice that matters, searchable, by name, a Favorites chip beside All and the groups narrowing it to this person's favorites (the operator, 17 Nov: no order by favorite); Full and Compact beside the search, as Containers' Cards and List are and with their pictures (the operator, 17 Nov): Compact folds every card to its name line with its star, archive and lock, a press on the name or the folded card opens it, and opening another folds the one open, one open at a time; this browser's choice (bb.pjview), opening folded; New space and Link a space are its bar's actions. Before: One notebook per space, a clone of one template. Every view opens with the same head row at one height. A row with detail behind it is a fold that opens to be read, never as a form. As built (step 3, 14 Oct): the pane's bar is the header (projectHeader in nb-core.js: .phead with .pname, .pfacts, .pstate, the .sp spacer, Start agent (Open and the agent's name in green while yours runs), Shell and the .more menu; the one notice as .pnote under it); the agent chooser is the house dialog at every width (the operator, 17 Nov): the page dimmed behind it, centered as every dialog is, each step its .box with the h3 Agents on the space, its lines .field bands headed by a label and its presses the box's .foot; a step keeps the taller one's height so the box never moves between them (syncResumeMenu, #rmModal); the view strip is the sub-nav: five groups with Overview first, a group's views in a row under it (R259); the address names the view (#/projects/NAME/VIEW, overview for the Briefing view). A roadmap line opens by its caret to its workings and Shelve, Reword and Drop (R223); the Roadmap's Save and Revert appear only with something staged (R224, the one section whose buttons are absent rather than dead); the Roadmap's status line carries when a session last read it (R222); every view's top is the Containers page's, a control row, tiles, a status line and one band of chips (R109); the Tests view's output button comes with the first run (R225); a finding's rule is a row that opens (R234); the wiki's narrow layout follows the pane's own width under 620px (B728).
  The Settings view (the operator, 16 Oct): a page of settings (the pages-of-settings rule). Each row the section's name and what is in it, unsaved on it when it holds a change; the picked section alone on the right, its heading a heading, not a fold, with its own Save and Revert. In this order: General, People, Agents may, Just for you, Repository, Nodes, Build and test, What sessions reach, File access, Snapshots, Running sessions (the Android signing keys are the Signing view, R103); a section this account may not see is not listed. On a phone the list, then the section over it, its head the way back. Asked for again it keeps the section picked and what is typed. The dialog (the Git view's remote door) keeps the sections open under a jump bar.
This page's own rules:
  a-notebook/views: scripts/dashboard/nb-*.js; notebook, view, head, row, strip (`aerie design show a-notebook/views` reads it)
  a-notebook/project-page: The header is one band: the name large, the branch and the node in --f-data beside it, the session's state as the dot and a word, and at the right the actions a space's card carries: Start agent, which turns green and reads Manage agent only while your session runs, the press opening the chooser with its Open, Restart and End (the operator, 22 Oct: one word for every agent; 23 Oct: Manage agent) (the operator, 16 Oct: green on every card read as running everywhere), with the chooser it opens (the house dialog over the dimmed page, titled Agents on the space, each band a field headed by a label, Close at its foot, the operator, 17 Nov; R143: three bands under the node it shows, Yours here with each of your sessions on the space, each agent's each slot, its state and Open, Restart and End; Start, a line per agent installed there with New, which takes the lowest slot free, and under it the Model and Effort that agent starts on, this person's kept picks for the space saved as they change, so New and Resume start at once and only Restart turns the chooser to a step of its own (the operator, 26 Nov, R284 step 4: the step of its own was a fourth press for two picks already kept); and Resume, your conversations here as one pulldown and one press (R236, the operator, 12 Nov: a list of rows with a button each was the longest thing on the card), each said by its label, or its first words where it has none, its agent and when, a kept one marked; under them the picked one's note, or its first words where it has a label, then a link to all of them in the notebook's Sessions view; one running in a session of yours says so in the press's place and is not offered; each band headed by a dialog's label), Shell, and the … menu (link, phone, report, lock, Add to favorites, settings). The sub-nav under it is the notebook's view strip under its own rule (views): five groups, a group's views in a row under it; Overview is the Briefing view under its new name and first, Settings beside it in its row, and the … menu's Settings opens it too. The view below opens with its head row as every notebook view does. The address names the view (#/projects/web/bugs), so a link to a bug's list lands on it. On a phone the name, the repository pulldown and the actions keep one row (the operator, 11 Nov): the buttons keep their width, the name is as wide as its words while there is room, and the pulldown takes what is left, never under a thumb's width; the branch, the node and the session's state go on the lines under them.
  a-notebook/roadmap-and-bugs: scripts/dashboard/nb-roadmap.js, scripts/dashboard/nb-bugs.js, scripts/dashboard/nb-history.js; roadmap, bug, bugs, finished, history, chips, facts, release, changelog (`aerie design show a-notebook/roadmap-and-bugs` reads it)
  a-notebook/restart-band: scripts/dashboard/nb-core.js; restart your session, pnote, band, put away (`aerie design show a-notebook/restart-band` reads it)
  a-notebook/permissions-inherit: For a notebook. The Permissions view's dials are a repository's overrides of its space's (R208 step 6, the operator, 3 Nov): each select's first choice reads 'as the space (word)', the word being what the space's own door (the card's Settings) sets, and a new repository starts on it on every dial; picking a value sets that repository apart, picking 'as the space' gives it back, and the glance counts an inherited dial as the word it inherits. The space's door draws the dials without that choice: what it sets is the default for every repository in the space.

#### Rules of a notebook's own

##### a-notebook/views

Applies to: scripts/dashboard/nb-*.js; notebook, view, head, row, strip

Every view's top is the Containers page's (R109, the operator, 22 Oct: the Docker view's head looked good, and the heads of Roadmap, Bugs, the Wiki and most views left a lot to be desired), in the page-head rule's order, each layer there only when the view has it (the operator, 29 Oct: the numbers first). First the glance, then the control row (`.nbhead`, a `.docbarrow`): one control high and at one height on every view. Its search sits at the left where the view has one (the Git view's branch picker in its place), then the view's own toggles (History, Cards or List), then at the right its actions in an `.actbar`, upkeep first and the primary last, which on a view that adds is its Add (Add to roadmap, Report a bug, New page, New key) in the accent fill. No words sit on it: no count line, no summary, and a view with nothing for it (Settings, Permissions) has none. Over it, the glance (the view's `#...Hint`, drawn by page-docs.js `viewGlance`): the numbers the view is about as tiles (`statTiles`), and under them its status line (`headLine`), words alone for what is not a number, with the upkeep buttons those words are about at its right. The tiles: the Roadmap's to send, shelved and finished; Bugs' open, each severity among the open and closed; Git's not committed, branches, to push and to pull; Tests' passing, failing, the time in tests, flagged and undescribed; Analysis by level; Artifacts' in dist/ and built on branches; Docker's running and updates due; VMs' running; Signing's keys and apps; the Wiki's pages; the Design's pages and themes; the Overview's rules and memories. The status line: the session and when it last read the list (Roadmap), a run going (Tests), the remote and what to push or pull with Fetch, Pull and Push (Git), where the wiki goes with Export, Pull and Push (Wiki), the file's state (Design), the node and when the images were checked (Docker). Then the chips, every group of them in one band (`.lfilter`) that wraps group by group, a view's Sort at its end, never a row per group. Then the content. What a view is for is its empty state: one dim hint line (`.hint.nbempty`, in a `.field` band) where the list would be, never in the head (R119 step 4), and an empty view draws no tiles of zeros. Settings and Permissions, pages of settings, keep one line of what each is on its control row, the views with words there.

The view strip is five groups in one row, at a desk and on a phone (the operator, 16 Oct: eleven tabs were too many): Overview, Plan (Roadmap, Bugs), Code (Git, Tests, Analysis), Ship (Artifacts, Docker, VMs, Signing) and Docs (Wiki, Design). A group of several opens its views in a row of their own under it, on the sunk ground, the way a rail group's page carries its tools; a group's button returns to the view it was last on. On a phone each row shares the width, so every view is one press from the group it is in and nothing hides behind an edge. Overview's row is Overview, Sessions, Permissions and Settings (the operator, 16 and 22 Oct), and the header's … menu opens Settings too. Sessions is your own conversations on the space, newest first (out of Profile), each a row read by the label its person gave it (R236, the operator, 12 Nov), with when, its agent, its size, the first thing said and its note under it, and by when alone where it has no label; one kept past its agent's own cleanup wears a pill saying so. A row has Resume, Read, Edit and Download, and behind its ⋯ Make visible (to every session on the space, a pill saying so) and Delete, asked first; Edit swaps the row's Label, Note and Keep a copy in, with Cancel and Save, as a row that opens does; Resume opens the Start chooser on that conversation. Past five conversations a find field over the list narrows it by label, note, first words or agent. Others' made visible follow in their own section, Read and Download only, each with whose it is. Permissions is everything a session may do on the space in one place: the settings form's Agents may section, lent to it while it is on screen and handed back to the form after (the Settings view does not list it), and Pushing, the push policy that was the Git view's, staged until its Apply. Docker is the Containers page scoped to the space (the operator, 19 Oct): its tiles (running and updates due, no spaces), when the images were checked, and the space's own card, in the cards or the list this browser keeps, with Check for updates and the Containers page on its control row. VMs is the VMs page scoped to the space (R96): its running of all a tile, the VMs page and New VM, the primary, on its control row, and the space's own VMs, each the row the VMs page draws. Signing is the space's Android keys (R103, the operator, 22 Oct: out of the Settings view's sections): its keys and apps as tiles (none over one hint line while it has no key), Import a backup and New key, the primary, on its control row, the form either opens unrolling under it (a backup the zip Download backup gave, its password and alias read from it), then the Backup password, a section per named key, Default key first, each a row per route (Play upload key, sideload signing key) with the alias and fingerprint, Upload one or Replace opening its file and password fields, Generate on an empty slot, Download backup and Remove, and on a sideload row a key picker with Rotate to it, and Apps, each package with the key it signs with; a key's uploads and removals and the apps' mappings staged behind their own section's Save and Revert. A sideload key never backed up says so in red under its row; an account whose roles do not give the keys reads them, the controls left out and why said once under the head. A group carries the approval counts of its views. The
view a notebook is on comes back with a reload, the way the tab strip and
the active pane do; closing the notebook's tab forgets it.

Adding goes at the top. The control that adds to a view is the last button on its control row, the primary, named for what it adds (`data-add`), and the form it opens unrolls as the first band under the control row, above the glance, the button staying where it is while the form is open. Never at the foot: a phone should not scroll past the list to add to it. Reorder sits beside Add to roadmap, the other thing done TO the list. An add that belongs to one section (a rule, a memory, a Design page or theme) is the first band inside that section instead.

Every section that stages something carries its own Save and Revert at
its foot (`.sectbar`, an action bar: its status, then Save, then Revert),
and they write or throw away that section's changes and no other's, each
dead while its section holds nothing (the operator, 5 Oct): one pair at the
notebook's foot was a long scroll on a phone from the change it saved. The
Roadmap's changes are on its rows, and its bar is its status line, under its
tiles: what is staged said first ("changed, not told to the session yet"),
then the session's state, Save and Revert at the line's right, never a loose
row of their own; the Memories, Your rules, each Version and the Design's Themes
and Pages carry theirs at their own foot. A view that writes through or
only reads (Bugs, Wiki, Tests, Analysis, Git) has none, and the notebook
has no foot.

A notebook view opens on its first section (the operator, 7 Oct). On a
phone one section is open at a time: opening one closes its siblings, a
section's own folds (a page's rules inside Pages) taking turns among
themselves without closing it, and a draw that finds several open keeps the
one last opened in this visit; a view or a page opened anew opens on its first. On a desktop no section at a page's level folds (the operator, 18 Oct): each stands open, its head with no triangle and nothing to press, but for a fold on purpose (data-fold: the Spaces page's Archived, a read made when opened, what a session is sent). Every section's head is one height and shade: 46px, on --head-bg, the ink a step into the panel, as Home's cards and the Containers space band are.

The Design view is two sections under its head row: Pages and Themes, in that order, each standing open like every other section (the operator, 19 Oct), and each showing one entry at a time, chosen on a pulldown at the section's top: every
page and every theme at once was the whole view scrolled past (the
operator, 28 Sep). The one shown is fields like any tab's, never a box of
its own. Adding is inside the section it adds to (the operator, 30 Sep): Add
page, with its platform, its template and a page here to copy, is the first
band inside Pages; Add theme, from blank, a preset or a copy of a theme, the
first inside Themes; blank is the default of both, and what is added is
what is shown. The design language is each theme's (the operator, 30 Sep):
the first theme is the default, and its type, corners, space, motion,
families and rules are the design's; another theme's are its own. Rules
live inside the entry they hold for and nowhere else (the operator, 29
Sep): a Rules section inside each theme above its colors and one inside
each page under its board, each following the pulldown; a rules fold below
everything read as the rules. Every rules list here is the Briefing's
(nb-rules.js): Add a rule first, a folded row a rule with its name and when
it reaches a session, Edit turning the row into its form. A new space's
design is empty, no theme and no page: the session that builds it chooses
the look and puts it here after. The view is passive: nothing on it reaches
into a session and nothing on it is a prompt; a session reads the design
piece by piece, through its rules and `aerie design show`, never as one dump.
A session meets a theme's or a page's own rule as HOLDER/RULE, and the
default theme's bare.

**The Design view's board is the one surface here whose colors are data.**
A page's blocks are painted in the space's own language (`nb-design.js`,
`blockStyle`), inline from the saved hex, because the board is a picture of
that space and not chrome of this page; everything around the board (the
frame's edge, the selection outline, the sizing corner) is the page's
tokens, and the corner shows on the selected block only, since a tap
selects a block before anything drags it. Its controls are the framework's:
choices in labeled selects on a `.dsrow` that lines up at the bottom, the
row's prose field growing only to the width the other tabs give a field so
what follows it stays beside it, colors as a chip beside a seven-character
field, prose in a proseline.

The Wiki view reads like an encyclopedia (the operator, 2 Oct), not as rows: the pages listed in a
narrow column (the wiki's own _Sidebar when it has one) beside one article at a time, its title large in
the serif over a hairline, its sections headed the same way, a Contents box for three or more, and the
prose in --serif at a reading width, the one place the dashboard sets text to be read at length. Read and
Edit are tabs over the article, with Rename and Remove at their right. Its control row carries History and New page, the primary; its status line, under the pages tile, says where the wiki goes and holds Export, with Pull and Push when the space has
a remote, so the control row fits a phone, where the column gives way to a picker above the article. Why
Push is dead (no push rights) is said in red under that line, never only in a tooltip. New page's form
unrolls under the control row, the first page offered as Home. Under Agents may: Write the wiki hidden the view is unchanged for a person; only a session is kept out.

The Briefing's rules section lists the global rules under the space's own, each a row that
opens to read with an On for this space switch, staged behind the section's own Save like the
rules above it. An administrator's rows also carry Edit and Remove, or Off everywhere for a
shipped one, each written at once for every space, and Add a global rule is the band over
them; nowhere else on the dashboard edits a global rule.

The Roadmap's exception (R224): its Save and Revert are absent, not dead, while nothing is staged; they appear on its status line with a reorder or an edit and go with the Save. Every other section's bar stays dead rather than absent, so it does not move under a thumb.

**The notebook's Docker and VMs views narrow by node** (the operator, 19 Nov): where the space's containers, or its VMs, are on more than one node, one band of chips under the glance, All and a chip a node with its count (the chips rule), the pick kept for the page's life as the Roadmap's is; with everything on one node there is no band. The Docker view reads every node the space's containers may be on, and with All each node's card says which node it is in its heading.

##### a-notebook/project-page

The header is one band: the name large, the branch and the node in --f-data beside it, the session's state as the dot and a word, and at the right the actions a space's card carries: Start agent, which turns green and reads Manage agent only while your session runs, the press opening the chooser with its Open, Restart and End (the operator, 22 Oct: one word for every agent; 23 Oct: Manage agent) (the operator, 16 Oct: green on every card read as running everywhere), with the chooser it opens (the house dialog over the dimmed page, titled Agents on the space, each band a field headed by a label, Close at its foot, the operator, 17 Nov; R143: three bands under the node it shows, Yours here with each of your sessions on the space, each agent's each slot, its state and Open, Restart and End; Start, a line per agent installed there with New, which takes the lowest slot free, and under it the Model and Effort that agent starts on, this person's kept picks for the space saved as they change, so New and Resume start at once and only Restart turns the chooser to a step of its own (the operator, 26 Nov, R284 step 4: the step of its own was a fourth press for two picks already kept); and Resume, your conversations here as one pulldown and one press (R236, the operator, 12 Nov: a list of rows with a button each was the longest thing on the card), each said by its label, or its first words where it has none, its agent and when, a kept one marked; under them the picked one's note, or its first words where it has a label, then a link to all of them in the notebook's Sessions view; one running in a session of yours says so in the press's place and is not offered; each band headed by a dialog's label), Shell, and the … menu (link, phone, report, lock, Add to favorites, settings). The sub-nav under it is the notebook's view strip under its own rule (views): five groups, a group's views in a row under it; Overview is the Briefing view under its new name and first, Settings beside it in its row, and the … menu's Settings opens it too. The view below opens with its head row as every notebook view does. The address names the view (#/projects/web/bugs), so a link to a bug's list lands on it. On a phone the name, the repository pulldown and the actions keep one row (the operator, 11 Nov): the buttons keep their width, the name is as wide as its words while there is room, and the pulldown takes what is left, never under a thumb's width; the branch, the node and the session's state go on the lines under them.

##### a-notebook/roadmap-and-bugs

Applies to: scripts/dashboard/nb-roadmap.js, scripts/dashboard/nb-bugs.js, scripts/dashboard/nb-history.js; roadmap, bug, bugs, finished, history, chips, facts, release, changelog

The Roadmap and Bugs views are read to find what is left and what happened to it (R254, the operator, 15 Oct). Under the glance, one band narrows the list: chips (All, Open, Shelved and the release an item is for on the Roadmap; All, Open, Closed and the release a report was seen in on Bugs), the groups side by side in that one band, Bugs' Sort at its end; the search, by words or by number (R12, B34), is the control row's, at its left; a row the band leaves out is not drawn and paging counts only what is shown. The Roadmap's numbers are tiles (to send, shelved, finished) and its status line says the session's state and when one last read the list ('claude-alpha running · read by a session just now'); a Save lit with nothing staged says on that line that a change has not been told to the session. Finished items are a section under the list, shut until opened and fetched then, each the same fold as an open item, with Reopen where no release has shipped it and the reason where one has. An opened row says what it knows as facts (factGrid), never a dotted line: an item's Added, Plan and Sent, a step's Done and Sent, a finished item's Finished and Shipped in, a bug's Reported, Seen in, Seen on, Closed (when, by, the note), Fixed in and Shipped in, and the changelog entries that name it with their release. What shipped a thing is read off the CHANGELOG's dated headings, never typed: the first release dated after it, the next release for one done since. A question a row asks (a close note, a drop) unrolls in the row, never the browser's prompt, and a bug's bar holds five at most with the rest behind More, Remove last. A History reads by day, each day's first line headed with the day and the release that day's work went out in; its verbs are words, a reorder is one line from place to place, every R and B id is a link that opens its row, and it pages with paginate alone.

##### a-notebook/restart-band

Applies to: scripts/dashboard/nb-core.js; restart your session, pnote, band, put away

For a notebook. The one notice a space's header carries about your own running session, Restart your session to use what changed, is a band between the header and the view strip (the operator, 28 Oct): .pnote.pband in the bar's second row, on the warning's own wash (--warn-wash, its words --warn-wash-ink, its hairline --warn-edge), never mixed over the panel, which carries the space's color, the words at the left and an x at the right that puts it away for as long as it says the same and for this visit to the notebook alone (the operator, 29 Oct: it comes back once you fully leave the notebook and return; another of its views is the same visit, another page, another space or a reload is not); what changes next brings it back. The space's card on the Spaces page keeps the plain one-line note. Every note the header carries is such a band (the operator, 29 Oct: a node removed from under the space, why Start agent is dead, a hold), each put away the same way; tests running stays a line, since it says what is happening rather than what to do. A band is a warning, tinted --warn, where it passes or asks a step of you (the restart, a node reconnecting, a hold, why Start agent is dead), and an error, tinted --bad with the same hairline in its tone, where no session can run there and nothing passes by itself (a node removed, disabled, off or hosting only); its words stay in --ink either way (the operator, 29 Oct: warnings yellow, errors red).

##### a-notebook/permissions-inherit

For a notebook. The Permissions view's dials are a repository's overrides of its space's (R208 step 6, the operator, 3 Nov): each select's first choice reads 'as the space (word)', the word being what the space's own door (the card's Settings) sets, and a new repository starts on it on every dial; picking a value sets that repository apart, picking 'as the space' gives it back, and the glance counts an inherited dial as the word it inherits. The space's door draws the dials without that choice: what it sets is the default for every repository in the space.

### the dashboard on a phone (Web app)

Platform: a responsive web app: the layout holds at phone and desktop widths, and every tap target is at least 44px on a coarse pointer.
Layout of the dashboard on a phone on a phone frame (6 columns by 12 rows), from the Blank template, numbered in drawing order (a later block draws over an earlier one where they overlap):
  1. Header (the band at the top): the brand, the uptime, the bell, the gear and sign out, across the top, row 1 of 12
  2. Tabs (a strip of tabs switching one area): Dashboard or Terminal: the two panels take turns, across the middle, row 2 of 12
  3. Content (the main reading or working area): the panel on show, across the middle, rows 3 to 11 of 12
  4. Card (a box holding one thing): Dashboard: the sidebar's cards, Spaces open and the rest folded, as the device last left them, across the middle, rows 3 to 7 of 12, inside block 3 (Content: the panel on show)
  5. List (rows of like things): a space row: name, dot, Claude, notebook, and … for shell, link, phone, report, lock, favorite, across the middle, row 4 of 12, inside block 4 (Card: Dashboard)
  6. Content (the main reading or working area): Terminal: the tab strip wrapping into rows, and the pane, across the middle, rows 8 to 11 of 12, inside block 3 (Content: the panel on show)
  7. Footer (the band at the foot): the hot bar of the terminal in front: its keys in a line that scrolls, and Links, across the bottom, row 12 of 12
Notes:
  From R218 step 2: the rail is a bottom bar of five (Home, Spaces, Build, Containers, More) sharing the width, More a sheet of the other seven (Controller, Machines, Sessions, Jobs, People, Settings, Help); the dock a sheet from the bottom edge; a space's sub-nav wrapped into rows of equal tabs; Home's tiles two across. Until then: Sections open on a desktop and shut on a phone, and a card opened here stays open after a reload. The notebook's strip wraps into rows of equal tabs. A bar of buttons shares the width so the last is never cut off, down to a 344px fold cover. A row's more button slides the row over the height its controls take, whether or not the card grows (30 Sep).
This page's own rules:
  the-dashboard-on-a-phone/both-sizes: scripts/dashboard/index.html; phone, mobile, touch, tap, width, responsive, fold, cover (`aerie design show the-dashboard-on-a-phone/both-sizes` reads it)

#### Rules of the dashboard on a phone's own

##### the-dashboard-on-a-phone/both-sizes

Applies to: scripts/dashboard/index.html; phone, mobile, touch, tap, width, responsive, fold, cover

The phone and the desktop are both first-class. A surface is not done until
it has been looked at at both widths: sections open on a desktop and one at a
time on a phone, no control spans the screen at either, and a typed field is 16px
on iOS alone, so Safari does not zoom.

A finger is not a pointer. On a coarse pointer (`@media(pointer:coarse)`)
every button in a dialog and in the notebook is `--tap` high, and the small
controls a thumb meets (a tab's close and minimize, the new-tab button, the
color swatches) are at least 30px; a desktop keeps its tighter strip. A bar
of buttons that spans a phone shares its width (`flex: 1 1 0; min-width: 0`)
rather than each taking its text's, so the last one is never cut off: at
344px, a folding phone's cover screen, four did not fit. A page's bar is one line on a phone, its node picker and its buttons (the operator, 18 Oct): the picker drops its word and gives up width last, the buttons take their short words (`barSaid`: Re-check, Install; New VM, Enroll; Check, New), and what else the bar holds is on that line too (the operator, 18 Oct, reversing the second line it had): Containers' search takes what is left from a 4em floor and its Cards and List are their pictures, the node's name read whole up to 11em; under 440px, where the search would be a sliver, it takes a line of its own under the rest. "Both widths" means
a small phone (360 to 375), the fold cover (344), an unfolded fold (690 to
840, still the phone layout) and a desktop.

On a phone the tab strip is a picker (`#tabPick`, R119 step 5): one button naming the tab on show, with a count of the open ones, and a list under it of every tab, each with its close or a terminal's minimize, and New terminal last; Escape or a tap elsewhere closes it. There is no strip to swipe and no paging arrows, and the pane's own caption, which only repeated the picker's name, is not drawn. A desktop keeps the strip, which wraps.

From R218 step 2 the strip's picker goes with the strip: the bottom bar is the rail (five groups and More), the dock is a sheet, and a page's own sub-nav (a group's tools, a notebook's groups and its views) shares the row's width while its tabs fit, and when there are more than fit each keeps its words and the row scrolls under a finger, its edges faded where more lies past them as the dock's line and a row of chips do, with the arrow at an edge with more past it, a small round press that pages the row, on a phone as on a desk (a thumb's 30px there), and the drag a mouse alone has (the operator, 29 Oct).

### a dialog (Web app)

Platform: a responsive web app: the layout holds at phone and desktop widths, and every tap target is at least 44px on a coarse pointer.
Layout of a dialog on a desktop frame (12 columns by 8 rows), from the Blank template, numbered in drawing order (a later block draws over an earlier one where they overlap):
  1. Overlay (a dialog, sheet, drawer, popover or toast over the page): a modal over the page, in the middle, columns 4 to 9 of 12, rows 2 to 7 of 8
  2. Header (the band at the top): its h3: what the dialog is, in a few words, in the middle, columns 4 to 9 of 12, row 2 of 8, inside block 1 (Overlay: a modal over the page)
  3. Form (fields a person fills in): every line a field band; groups headed by a label; the two gaps and no others, in the middle, columns 4 to 9 of 12, rows 3 to 6 of 8, inside block 1 (Overlay: a modal over the page)
  4. Footer (the band at the foot): the foot: the state on the left, Cancel and the one filled button on the right; Escape closes it, in the middle, columns 4 to 9 of 12, row 7 of 8, inside block 1 (Overlay: a modal over the page)
Notes:
  Two gaps down a dialog and no others: the field gap between the things in a band, the label gap between a label and its control. It scrolls in one place; a text box and a listbox are the only things that scroll inside it. A dialog opens at its top every time, whatever was scrolled or focused last. One taller than the screen scrolls inside its box between its title and its buttons, which stay in place with the hairlines they always had while the content passes under them; nothing is shaded (the operator, 16 Oct: the black fades read as dirt). A document pane fades what it holds into its own ground at the edge with more past it; a list or a log that scrolls inside a surface (a space's Reads, the notebook's lists, a job's log, the chat, the changelog) draws a hairline at that edge. It takes the focus as it opens (its own field when the opener focuses one, else its box, so a phone raises no keyboard), Tab and Shift+Tab go round inside it and never out to the page behind, Escape closes the one on top the way its backdrop or Cancel would, and the focus goes back to what opened it. Its title names it to a screen reader by aria-labelledby.
This page's own rules:
  a-dialog/layout: scripts/dashboard/index.html, scripts/dashboard/page-*.js; dialog, modal, popup, pop-up, foot (`aerie design show a-dialog/layout` reads it)

#### Rules of a dialog's own

##### a-dialog/layout

Applies to: scripts/dashboard/index.html, scripts/dashboard/page-*.js; dialog, modal, popup, pop-up, foot

A dialog is `.modal > .box` (`.wide` for a list or an editor), titled by its
`h3`. Every line of its body is a `.field` band, which is where the inset
lives: a hint, a control, a list, never text at box level, which draws flush
against the edge. A group of fields inside it is headed by a `label`, the dim
small heading every dialog uses, never an `h4`; a dialog that is prose to
read rather than fields to fill (About) says so with `.box.prose` and may use
headings. A dialog long enough to scroll through its groups (the space
settings) makes each group a section instead: a `details.sect` fold titled
by its summary, the box marked `data-sects` so its sections behave as a
tab's do, and the first that a door shows open when it opens.
The buttons are the `.foot`: a
`.state` first when there is one, then `.sp`, then the verbs, the primary
first and anything destructive last. A switch is a checkbox inside its label,
beside the thing it names, the way the Settings tab draws them
(`.logdays.setrow` holding a `label.ndcap`). What has nothing to act on is
hidden rather than disabled: a dialog with an empty list says so in one
sentence and offers Close.

A dialog is put away by its way out: Escape, a press on the dimmed page
around it and Back each press it, as the person would. The way out is the
foot's Cancel or Close, or the button marked `data-way-out` where its words
are its own (Reset's Keep it), and it is never the primary: Apply then
Cancel, Download then Close. Back puts the dialog away and leaves the page
under it where it was (the operator, 17 Nov): each dialog opened holds an
entry in the history (`backHold`), given back when it is put away some
other way, and a link in it takes that entry over, so Back from where it
led comes to the page it was opened on. On the way out the focus goes back
to what opened it. A dialog holding something shown once (Enroll's
one-time token) is marked `data-keep-stray`: a press around it and Back
pass it by, and Escape or its own Done puts it away.

At a desk a dialog is the size of what it holds: a reader's full height
(About's guide, a conversation) is for something to read, and the same box
with one line in it (a conversation with nothing said) is that line's size.
On a phone every dialog is the whole screen, as a log's sheet is (the
operator, 18 Nov): the box runs to the screen's edges with no page round
it, its title at the top and its foot at the bottom under the thumb
however little it holds, and what is between scrolls; the overlay keeps
the safe areas (a notch, the home bar) in the box's color. With no page
showing round it, its way out there is its foot, Escape and Back.
Its title shows wherever the dialog sits, a notebook's sheet included;
uniform holds a title that stands first and shows, and the dialog walk
(every dialog at 393 and 1440, on contact sheets) is how a pass over them
is read.

**A question is asked once, and only where its yes costs something** (R265, the operator, 19 Nov: Rebuild on a container raised three whole-screen questions in a row on a phone). A press asks when its yes deletes or overwrites something, cuts off somebody's work (sessions end, a machine restarts, a node's sites go down) or grants more reach, and at no other time: Rebuild, Up, Down, Stop and an image's update on a person's own containers run, and the row or the job's toast says what the press started. One press raises one question at most. What it needs a yes for is gathered before anything is asked and listed in that one question, each kind under a short heading with its lines as points (`ask`'s `parts`), under one button; with nothing to list the press runs. A choice that is not a yes or a no (bring the data across or start empty, check or check and correct) is still its own question. On a phone a question is the one dialog that is not the whole screen: a sheet at the foot, as tall as its words, the buttons under the thumb, the page dimmed above it and a press there Cancel; one too long for the screen scrolls inside itself with a strip of the page showing, and one that asks for a line of text sits at the top, clear of the keyboard. A toast sits above the sheet. At a desk it is the box every dialog is.

**A dialog's title is a band, as a pop-out's is** (Perch, the operator 23 Nov: dialogs had not had Perch's pass). Its `h3` says what the dialog is in the section voice (`--f-sect`), sentence case, in a band as tall as the bell's and the doctor's, with its hairline under it; never capitals in the tag voice, which made a dialog look older than the page under it and rewrote what a title quotes (a file's name). A question's title is the same band. **The page behind is veiled, not blacked out:** `--veil`, the theme's own page most of the way in the dark half and the ink at about a third in the light, with a 3px blur, so what is behind keeps its color and reads as set back; the box's shadow is a soft one. On a phone, where a dialog is the whole screen, nothing of the page shows; the question's sheet at the foot wears the same veil above it.

### signing in (Web app)

Platform: a responsive web app: the layout holds at phone and desktop widths, and every tap target is at least 44px on a coarse pointer.
Layout of signing in on a desktop frame (12 columns by 8 rows), from the Blank template, numbered in drawing order (a later block draws over an earlier one where they overlap):
  1. Card (a box holding one thing): one panel in the middle of the page: the mark and the name, then the form, in the middle, columns 5 to 8 of 12, rows 3 to 6 of 8
  2. Form (fields a person fills in): Username, Password and Sign in, the one filled button; a refusal is said under it, in the middle, columns 5 to 8 of 12, rows 4 to 6 of 8, inside block 1 (Card: one panel in the middle of the page)
Notes:
  The only page with nothing around it but its ground, and always in the Default scheme's dark half: nobody is signed in, so no scheme a person picked is worn here, whatever the browser kept (the operator, 17 Oct). The ground is a drafting grid in the line color, a fine one under a coarse one, fading out from the middle, under two slow glows, the accent's behind the panel and the second color's below it (still under reduced motion). One panel, 360px wide, centered both ways, a little glass over the grid, its top edge a hairline running from the accent to the second color; it rises into place once. In it, centered: the mark in the accent on a tile of its own, the name in the display face, and one dim line saying what the page is for (Sign in to continue, or Make the first account). Then the form: Username and Password, labels above, 42px fields in 16px so a phone does not zoom, and Sign in, the one filled button, the deep fill with the ink on it as every filled surface is; a refusal is a red-tinted band above the fields. Nothing else is reachable before it.

### first run (Web app)

Platform: a responsive web app: the layout holds at phone and desktop widths, and every tap target is at least 44px on a coarse pointer.
Layout of first run on a desktop frame (12 columns by 8 rows), from the Blank template, numbered in drawing order (a later block draws over an earlier one where they overlap):
  1. Card (a box holding one thing): The head: Set up AerieOS, and one line saying a node is all it needs to start, in the middle, columns 4 to 9 of 12, row 1 of 8
  2. Card (a box holding one thing): Four step cards, one under another: a node, your name and email, Claude Code on the node, a first space, in the middle, columns 4 to 9 of 12, rows 2 to 7 of 8
  3. Card (a box holding one thing): Finish, under them at the right, with what can wait, in the middle, columns 4 to 9 of 12, row 8 of 8
Notes:
  After the owner is made, the page is this until Finish (the operator, 18 Oct, R267): the content area's whole height with nothing beside it, no rail, no bell, no doctor, no search and no panes, so no dock; its steps at the reading width (--doc-w), centered. Each step is a card on the page's ground: its number in a circle, its title in the section face and its state as a pill at the right (to do, waiting, done, the number and the pill in the pass color when done), what it is in one dim line, and its own action at the card's foot on the right. 1, your first node: New VM and Enroll node open the Nodes page's own dialogs (ndDialogs), and the card says when a machine is waiting to dial in and when it is answering, by itself. 2, your name and email: two labeled fields side by side at a desk, stacked on a phone, Save waking once both are filled. 3, Claude Code on your node: Install, the Agents page's install as a job, dead until the node answers with the reason under it. 4, a first space: New space, the Spaces page's own dialog. Finish waits for the node, as the server does, and says steps 2 to 4 can wait; storage and the idle timeout are not asked, their defaults being under Controller settings. After Finish the page is Home, whose Getting started card keeps what is left of the four, for an administrator, until done or put away; the About guide no longer opens by itself for them. Moving here is the page's second shape (R214, the operator, 4 Nov: a person switching a machine over met a page that spoke only of a new start): the same page, the same cards, the steps a move takes in the order they have to happen, each done in place with This machine's and Controller settings' own controls and wiring and each state read from the machine. Have these with you (the move token and the bundle), This machine, The old system's disks, Where the spaces and containers go, Land the controller, After it lands, If you go back. A card with no state to read wears a word of its own in the note color (read first, then, any time). The first page asks whether a controller is moving here, and its answer opens this page on one shape or the other; a stick whose plan names disks has answered it already. Under the head one line and one button lead between the two (Walk me through it, Set up a new one instead), which one is showing being the browser's. Every install takes the walk with the steps it has, and an install with no old system's disks hears no word of one. Finish stays at the foot, plain beside the walk's primary actions. Nothing on this page links to a page, since none can show behind it: what lives on another page says after Finish, or is drawn here. The needed steps are taken in order, and a system job in flight holds the rest (8 Nov). Taking the array over is not a step of the walk (the operator, 8 Nov: the first parity sync is hours, and it held every step after it): the walk adopts the disks, read only or writable, and says the parity comes after, from Adopted disks on the Nodes page; the bell carries a row (The array has no parity yet, with the Nodes page on it) until the array is taken over or released. The sync runs in the background with its progress as a bar on the Storage page. On a machine that is its own controller the head's title line carries two presses at its right, on both shapes of the page (the operator, 9 Nov): Generate console login (New console login once one is set), which makes a password a person can read off and type at a KVM, shown once in a dialog, and Shut down in the danger tone. They are no step: nothing numbers them and no step waits for them; a job in flight makes them dead, the job's band saying why. The first page's yes to moving asks for the move token and no account: the accounts arrive with the move, and until it lands the name setup with that token is the way back in.

### a terminal tab (Web app)

Platform: a responsive web app: the layout holds at phone and desktop widths, and every tap target is at least 44px on a coarse pointer.
Layout of a terminal tab on a desktop frame (12 columns by 8 rows), from the Blank template, numbered in drawing order (a later block draws over an earlier one where they overlap):
  1. Header (the band at the top): the pane bar: which session this is, by its kind and its space, across the top, row 1 of 8
  2. Content (the main reading or working area): the terminal itself, the session as tmux has it: Claude or a shell, across the middle, rows 2 to 7 of 8
  3. Footer (the band at the foot): on a phone alone, the hot bar: the terminal's keys in a line that scrolls, and Links; a desk's floats over the terminal, across the bottom, row 8 of 8
Notes:
  A terminal is the one surface here that is not the dashboard's to draw: the frame shows the session and the chrome stays out of it, but for one piece (the operator, 12 Nov): the hot bar, the keys it is most reached for (an agent's Esc, Shift+Tab, arrows, Enter and Ctrl+C; a shell's Esc, Tab, arrows, Ctrl+C and Ctrl+D; PgUp and PgDn on every one) and Links, one press with the chain's picture that is always there and lists the terminal's links to open or copy over the bar, or says it shows none. At a desk it is a floating card over the terminal's bottom right corner, slightly translucent until the pointer or the focus is on it, each key the control's height, folding to its handle, the browser's own choice. On a phone nothing floats over the terminal: the bar is the band at its foot and reads as the dock's line of tabs does, its keys in a line that scrolls with the line's faded ends and round arrows, each key a tab's height, a shell's line carrying the rest of the key table past its hot ones (there is no Keys panel), and Links standing still to the right of the arrow. The bar wears the space's color as a stripe. There is no Commands panel (the operator, 12 Nov): a shell is typed into; Sessions is a page and Chat the dock's tab.

### the Library (Web app)

Platform: a responsive web app: the layout holds at phone and desktop widths, and every tap target is at least 44px on a coarse pointer.
Layout of the Library on a desktop frame (12 columns by 8 rows), from the Blank template, numbered in drawing order (a later block draws over an earlier one where they overlap):
  1. Header (the band at the top): the Build group's header: the node picked once; Check for updates and Add your own at the right, across the top, row 1 of 8
  2. Text (a block of prose): the node's head: installed of offered, updates due, the store, versions checked, not for this node, Remove takes, across the middle, row 2 of 8
  3. Text (a block of prose): notices over the cards: a node not reporting, a read-only store, system packages lacked with one press, across the middle, row 3 of 8
  4. Search (a search box): one band: the search, then the kind chips and the tier chips, across the middle, row 4 of 8
  5. List (rows of like things): a group of cards per kind: coding agents, toolchains, tool packs, services, apps, companions, across the bottom, rows 5 to 8 of 8
  6. Card (a box holding one thing): a card: glyph, name with Details, tier and version pills, two lines, the driver's version pick, state and one verb, across the middle, rows 6 to 7 of 8, inside block 5 (List: a group of cards per kind)
Notes:
  The Library (R170; the operator, 28 Oct) is one page under Build for everything a AerieOS installs or runs on a node, in the Spaces page's shape: a store browses as cards. Its chrome is a document tab's (docSurface) under the Build group's header, where the node is picked once (R178). The head is the node's: installed of offered, updates due, the store's path and room, when versions were last checked, how many cards are not for this node (the server marks a row the node's platform cannot have, and it is not drawn: a card nobody can press is not a fold, R170 step 9), and what Remove in the bar would take off the store (a retired node's directory, R196). The bar's verbs are the store's: Check for updates (Checking for updates with the ellipsis while the job runs), Add your own (one dialog for a tool pack or an app's compose file, looked at before it is kept), Remove for what no node runs from, and Abort while a job runs. Under the head, one band narrows the list more than one way (the chips rule): the search, the kind chips and the tier chips (Packaged by Aerie, Verified, Vetted, Sideloaded). Then a group of cards per kind, always drawn, headed with installed of offered. Under a card's name, at the left of its pills and in the quiet voice with no pill of its own, is who the tool itself is by (the operator, 12 Nov: Google, Eclipse Adoptium; AerieOS for a toolchain of several makers' tools, each credited on its Details page), then the tier's pill, its version and what is out; a sideloaded card names nobody. A card is the catalog's entry and nothing of the node (the operator, 28 Oct: what is installed is the Installed page's, under Machines): its kind's glyph, its name with Details beside it, the tier and the versions as pills, two lines of what it is, and at its foot the state (installed, update available, installing or removing with the ellipsis, the driver's installed and in use) and one verb: Install or Update on a toolchain, a pack or a coding agent, Install on a catalog pack (which opens the Add tool pack dialog at the catalog's commit), New container on an app (the Containers page's dialog with the app picked, each press another container), Edit on a sideloaded entry, Download on a companion. Open, a card runs the grid's width with the whole description: platforms, terms, what it adds to a session, its source and a pack's Look, an app's compose with its blanks, a companion's other files. The NVIDIA driver's card carries its version pick (the branches apt offers there, the recommended one first, dead once a driver is installed: another version means removing this one first, R102); its state and Remove are the Installed page's. What a job said failed is under the card it failed on. The Toolchains, Agents and Apps pages this replaced are gone (R170 step 5): an address naming one opens the Build group.

### the Installed page (Web app)

Platform: a responsive web app: the layout holds at phone and desktop widths, and every tap target is at least 44px on a coarse pointer.
Layout of the Installed page on a desktop frame (12 columns by 8 rows), from the Blank template, numbered in drawing order (a later block draws over an earlier one where they overlap):
  1. Header (the band at the top): the Machines group's header: the node picked once, with when it was seen and its agent, across the top, row 1 of 8
  2. Text (a block of prose): the node's head: how many of each kind it holds, its store, its session account, across the middle, row 2 of 8
  3. List (rows of like things): a section per kind with anything on the node: coding agents, toolchains, tool packs, services, across the bottom, rows 3 to 8 of 8
  4. Card (a box holding one thing): a row: name with Details, version pills, its state, Remove; a configured service's Install deploys it, across the middle, row 4 of 8, inside block 3 (List: a section per kind with anything on the )
  5. Card (a box holding one thing): the open row: an agent's sign-in and what is yours; a toolchain's path and packages; a service's Configure, across the middle, rows 5 to 7 of 8, inside block 3 (List: a section per kind with anything on the )
Notes:
  The Installed page (R172; the operator, 28 Oct) is what a node holds from the Library: under Machines beside Nodes and Storage, the node picked once in the group's header (R177), a section per kind with anything on the node (coding agents, toolchains, tool packs, services; never apps, which are containers on the Containers page, nor companions, which are a person's own machines'). A row is its name with Details beside it, the versions as pills, its state (installed, update available, not installed for Claude Code, which is always a row so a sign-in has a place; the driver's installed and in use or waiting for a restart; a service's deployed or what it still needs) and Remove, the toolchain job's; nothing installs from here but a configured service, whose Install deploys it as a written container. The open row is what the catalog's card does not show (rows-you-open). A coding agent's row: its facts (the program, installed, latest, whose account signs it in), the person's own sign-in on that node as one action bar (what is so on the state line, the press after it, the reason a press is dead on a line under it; while a sign-in runs the bar gives way to its link, a labeled field for the code where the flow asks for one, and Cancel, Start over and Send; a Start with no sign-in on its node lands here with the agent's row open), and under it what the person added to that agent on the node as a facts grid: Claude Code's plugins and each agent's MCP servers by name, as the node last said (R95, the operator 22 Oct). A toolchain's row: where it lives, its system packages (which are missing, with Install them now on a sandbox node, or whose to install on a guest machine), what it needs that is not here with that row's own install, how its download was checked when it was installed (R137), and the sessions to reopen that started before it landed. The NVIDIA driver's row says where it stands (not installed, installed and waiting for a restart, installed and in use, removed but still loaded, no card now) and the container toolkit's whether a container there can reserve the card. A service's row: its Configure form drawn from the pack's config block (keys sealed and shown as set, lists of endpoints, switches, the spaces allowed), Save keeping the answers on the service's own record, and Remove.

### the Emulator tab (Web app)

Platform: a responsive web app: the layout holds at phone and desktop widths, and every tap target is at least 44px on a coarse pointer.
Layout of the Emulator tab on a desktop frame (12 columns by 8 rows), from the Blank template, numbered in drawing order (a later block draws over an earlier one where they overlap):
  1. Header (the band at the top): the bar: which node, across the top, row 1 of 8
  2. Text (a block of prose): the store the images live in, across the middle, row 2 of 8
  3. Form (fields a person fills in): add an image: the API level, the flavor, and Add, across the middle, row 3 of 8
  4. List (rows of like things): the images held, across the middle, rows 4 to 7 of 8
  5. Card (a box holding one thing): an image: what it is and can do in a sentence, its size, its package and the AVD made from it, across the middle, row 5 of 8, inside block 4 (List: the images held)
  6. Footer (the band at the foot): the terms the images come under, across the bottom, row 8 of 8
Notes:
  A document tab: the bar band, the list of bands, a quiet footer (docSurface). The flavors say what they are for in a sentence (Play services or not, rootable or not), since the package name says it to nobody.

### the Docker tab (Web app)

Platform: a responsive web app: the layout holds at phone and desktop widths, and every tap target is at least 44px on a coarse pointer.
Layout of the Docker tab on a desktop frame (12 columns by 8 rows), from the Blank template, numbered in drawing order (a later block draws over an earlier one where they overlap):
  1. Header (the band at the top): the bar: which node's daemon, and how it is reached, across the top, row 1 of 8
  2. List (rows of like things): containers grouped by the space that owns them, the group headed in the space's color; no space last, across the middle, rows 2 to 7 of 8
  3. Card (a box holding one thing): one container: running as a pill, where it came from, Details, Ports and mounts; why a control is dead, under it, in the middle, columns 2 to 11 of 12, rows 3 to 6 of 8, inside block 2 (List: containers grouped by the space that own)
  4. Button (an action to press): the container's own action bar: Up, Down, Env or Edit, Rebuild (no cache, pull), Remove, in the middle, columns 2 to 11 of 12, row 6 of 8, inside block 3 (Card: one container)
  5. Footer (the band at the foot): New container, across the bottom, row 8 of 8
Notes:
  A document tab: the bar band, the list of bands, a quiet footer (docSurface). A group is headed by its space in the space's color. A container's row says whether it runs as a pill, never as colored words alone. Why a control is dead is written under the row, since a tooltip is nothing on a phone: in yellow, never in red, which is for what failed; a control the account's roles do not give is not drawn at all (the operator, 21 Oct). A session's request to rebuild is answered here.
  The nginx tab (R171) is a node-scoped tab of the Toolchains shape (the node-switcher rule): one node at a time, picked in the bar, a state row first (nginx on NAME, its pill not deployed, deployed or deployed, down, and under it the container's name and route count); then the form, route rows (hostname, path, port, 443 too, remove) with Add route on their action bar, the certificates' lines (each name and when it ends; a key is never shown back), the hostname picker, the certificate and the key each a full-width PEM box under its label (the operator, 11 Oct: side by side on desktop read as broken), the clash in red since nginx holds 80 and 443 on the host, and Save, Revert then Deploy or Remove on the action bar at the foot, the destructive one last.
  2.0 (R216, the operator, 13 Oct): under the bar, a row of tiles (containers running of all, updates due, spaces) and a row of chips narrowing the list to one space. A container's row is its name and a state pill with a dot (running, stopped, partly up, down), a facts grid (image, ports, built from, compose file, containers), its notices, then the settings grid with one Apply, then its action bar. Nothing a person acts on moves into a fold. The bar carries a search box (name, image, port or space) and a Cards or List switch: in the list a container is one line, its name and state pill then its facts in the data voice (whose, its ports as links, where nginx routes it, its image), that opens into its card (rows-you-open); this browser's choice, kept. A published port is a link to where it answers; a port nginx routes to shows the address as a fact; Docker's health (healthy, unhealthy, starting) is said on the state pill.

### the Nodes tab (Web app)

Platform: a responsive web app: the layout holds at phone and desktop widths, and every tap target is at least 44px on a coarse pointer.
Layout of the Nodes tab on a desktop frame (12 columns by 8 rows), from the Blank template, numbered in drawing order (a later block draws over an earlier one where they overlap):
  1. Header (the band at the top): the bar: which node, New VM and Enroll node, across the top, row 1 of 8
  2. Card (a box holding one thing): the node: where it dials in from, its agent, Update, and Test, across the middle, rows 2 to 3 of 8
  3. List (rows of like things): its sections, across the middle, rows 4 to 7 of 8
  4. Card (a box holding one thing): a section, a fold with its own Apply: Health, Sessions, GPU, Coding agents, Storage, Network, Runner, or why not, across the middle, rows 5 to 6 of 8, inside block 3 (List: its sections)
  5. Footer (the band at the foot): what a node is for, in a sentence, across the bottom, row 8 of 8
  6. Form (fields a person fills in): Coding agents: one line, which are installed and which you are signed in to here, and Agents, in the middle, columns 2 to 11 of 12, row 6 of 8, inside block 4 (Card: a section)
Notes:
  A document tab: the bar band, the list of bands, a quiet footer (docSurface). A node's state is one pill (the operator, 17 Nov: online and live side by side read as one word twice): online in --ok when it takes new work and its agent answers; not answering in --bad when it is set to take work and its agent has gone quiet; draining or disabled in --warn as set, with not answering after it only when that is true too; waiting for enrollment before it is enrolled. It is said once, beside the group header's picker (the operator, 17 Nov): the node's section under it carries no state pill, and its Health section's status says only why a node that does not answer was turned away. When it was last heard is its facts' seen. Health draws meters: a track with a fill, the number beside it; a node whose NVIDIA driver answers adds two, gpu (how busy the card is) and vram (its own memory), under cpu and memory. A section the node cannot offer says why in its place rather than being missing. A node with an NVIDIA card has a GPU section among its folds: two switches, render the Android emulator on the card and let sessions and jobs compute on it, and one Apply, as every section here. The GPU line under Health is a status: it names the card, and with no NVIDIA driver on the machine it offers Install the driver, which opens that node's Toolchains tab. Its coding agents are in its Sessions section (the operator, 23 Oct: a section of their own said less, and apart): a fact naming each installed there with its version, and one line saying which of them the person looking is signed in to, with Agents, the way to that node's Agents page, where each is installed, updated and signed in to. An account that does not administer sees the tab for the nodes its own spaces are on: every control on it is ghosted but the picker, and one line on the node's row says why.
  The Storage tab (R169) beside it, a node-scoped tab of the same shape: one node at a time, picked in the bar, a state row first (Storage on NAME, the walk's age as its pill): the filesystems as one meter stack (every track one width, the values one right-aligned column), the stores and Docker's share as rows, then the spaces as rows with their numbers in fixed right-aligned columns, largest first, the spaces a person cannot see as one dim line, and Measure now on the action bar at the foot. Every tab about settings on nodes picks its node this way (the operator, 11 Oct), never a section per node. The jump bar over a long surface draws its names as chips (the operator, 11 Oct: bare links blended with the text), in a row even inside a dialog's band.

### the Jobs tab (Web app)

Platform: a responsive web app: the layout holds at phone and desktop widths, and every tap target is at least 44px on a coarse pointer.
Layout of the Jobs tab on a desktop frame (12 columns by 8 rows), from the Blank template, numbered in drawing order (a later block draws over an earlier one where they overlap):
  1. Header (the band at the top): the bar: a filter for the ones still running, across the top, row 1 of 8
  2. List (rows of like things): jobs, newest first; a long list pages rather than scrolling forever, across the bottom, rows 2 to 8 of 8
  3. Card (a box holding one thing): a job: state as a pill, its kind, where, when, how long, who asked, and Log, across the middle, row 3 of 8, inside block 2 (List: jobs)
Notes:
  A document tab: the bar band, the list of bands, a quiet footer (docSurface). A long list pages rather than scrolling forever. Log opens the job's output in a dialog.

### a node's Phone section (Web app)

Platform: a responsive web app: the layout holds at phone and desktop widths, and every tap target is at least 44px on a coarse pointer.
Layout of a node's Phone section on a desktop frame (12 columns by 8 rows), from the Blank template, numbered in drawing order (a later block draws over an earlier one where they overlap):
  1. Header (the band at the top): the bar: which node the phone is plugged into or paired with, and Check now, across the top, row 1 of 8
  2. Card (a box holding one thing): whether a phone is connected, as a pill, and Connect, the filled button, across the middle, rows 2 to 3 of 8
  3. Form (fields a person fills in): pairing: the code from the phone, and Pair, with the steps to get one, across the middle, rows 4 to 6 of 8
  4. Card (a box holding one thing): lent to a space: for how long, the newest screenshot, the newest recording's reel and its video; Take back, across the middle, row 4 of 8
  5. List (rows of like things): what sessions have asked of the phone, across the middle, row 7 of 8
  6. Card (a box holding one thing): an ask: its reason, its command, Allow and Deny, across the middle, row 7 of 8, inside block 5 (List: what sessions have asked of the phone)
  7. Footer (the band at the foot): a session reaches the phone only by asking, across the bottom, row 8 of 8
Notes:
  A fold of a node's page on the Nodes tab (the operator, 2 Oct: each node with adb holds its own phone), shown on a node whose census carries adb, shut until opened: the phone and who connected it, Connect by IP, Pair, the phones the node remembers, and the asks waiting on its owner. Live for any account whatever the node's other settings allow, since a phone is its owner's. Under the connected phone, its owner's Lend to a space row: a space picker (only spaces on the phone's node), For (1 hour, 4 hours, until taken back) and Lend, with why it cannot be lent under it when no space fits. Once lent, a row says Lent to PROJECT with the time left as a pill, which apps its sessions drive, and the newest screenshot a session took at a phone's proportions (updated on the next poll), with Check now and Take back on the owner's action bar; the section's last band says the lease's terms beside Check now. Another account's phone is a phone, not a name and an address: connected, and whose, with no model, serial or address, and no remembered rows but the account's own (B490); an administrator keeps both, since they may disconnect anyone's.

### Controller settings (Web app)

Platform: a responsive web app: the layout holds at phone and desktop widths, and every tap target is at least 44px on a coarse pointer.
Layout of Controller settings on a desktop frame (12 columns by 8 rows), from the Blank template, numbered in drawing order (a later block draws over an earlier one where they overlap):
  1. Header (the band at the top): the bar: what this tab is, and where appearance lives instead, across the top, row 1 of 8
  2. List (rows of like things): seven sections, across the middle, rows 2 to 7 of 8
  3. Form (fields a person fills in): a section: a group of fields, a draft until its own Apply at its foot, across the middle, rows 3 to 4 of 8, inside block 2 (List: seven sections)
  4. Footer (the band at the foot): when a change takes effect: at once, or at the next start, across the bottom, row 8 of 8
Notes:
  A document tab: the bar band, the list of bands, a quiet footer (docSurface). Nothing here takes effect on the change: each section is a draft until its Apply. The color scheme is not here; it is in the gear, since a theme is looked at and not decided.
  Sections like every other tab's (the operator, 11 Oct): a fold per group (Logs, Claude sessions, Storage on this controller, Reach from outside, Debugging, Reset, Nodes), its status on the heading (the idle minutes, the number of paths, connected or off, on or off), a jump bar of chips over them, and each with its own Apply and Revert on its action bar; Revert puts that section's fields back to what is saved. The Reach from outside section carries its own setup steps as a numbered list, the controller's port in them.
This page's own rules:
  controller-settings/controller-card: scripts/dashboard/tab-settings.js, scripts/dashboard/page-doctor.js; controller card, doctor, run again (`aerie design show controller-settings/controller-card` reads it)

#### Rules of Controller settings's own

##### controller-settings/controller-card

Applies to: scripts/dashboard/tab-settings.js, scripts/dashboard/page-doctor.js; controller card, doctor, run again

The page's first section is Controller (Perch, the operator 18 Oct: a Controller card at the top), picked first in the list, its heading's status the doctor's verdict (all N ok, or N to look at in its level's color): the facts that would stop a controller if they ran out (the free space under /config and on the spaces' share, a disk under a tenth free in the warning's color, the database with its log, the nodes online of enrolled in the warning's color when any is not, the sessions open), with no hardware graphs, those being a node's; then the doctor's checks as its panel draws them (doctorChecks): the problems first, each in its level's color with what the check said under it and the way to fix it, the passing ones as chips; then when the doctor ran and Run again in the section's bar. The page redraws on the facts as they read, never on a byte of free space. The doctor's panel has Controller settings across its foot, as the gear has Profile, for an account that may open it, and it opens the page on this section.

### the Users tab (Web app)

Platform: a responsive web app: the layout holds at phone and desktop widths, and every tap target is at least 44px on a coarse pointer.
Layout of the Users tab on a desktop frame (12 columns by 8 rows), from the Blank template, numbered in drawing order (a later block draws over an earlier one where they overlap):
  1. Header (the band at the top): the bar: who may sign in here, and which spaces they see, across the top, row 1 of 8
  2. List (rows of like things): accounts, across the middle, rows 2 to 4 of 8
  3. Card (a box holding one thing): an account: admin or owner as a pill, its roles as pills, the spaces it is on, its Claude sign-in, Edit and Remove, across the middle, row 3 of 8, inside block 2 (List: accounts)
  4. Form (fields a person fills in): Add somebody: a name, the password twice, a name and an email (optional), and Add; no role, across the middle, rows 5 to 6 of 8
  5. Footer (the band at the foot): how a password is set from a shell, across the middle, row 7 of 8
Notes:
  A document tab: the bar band, the list of bands, a quiet footer (docSurface). The owner's row says it cannot be deleted, under the row, where a dead button would otherwise be the first you heard of it. The add form takes no git identity: that is the person's own, on their Profile (R134). Edit ticks the roles of your own an account carries beside its built-in one (R137). Its roles and spaces are set on the Roles tab (R152): the edit dialog says what it holds, with a Roles button that opens the tab on it.

### the Profile tab (Web app)

Platform: a responsive web app: the layout holds at phone and desktop widths, and every tap target is at least 44px on a coarse pointer.
Layout of the Profile tab on a desktop frame (12 columns by 8 rows), from the Blank template, numbered in drawing order (a later block draws over an earlier one where they overlap):
  1. Header (the band at the top): the bar: who you are here, your role, and your Claude sign-in, across the top, row 1 of 8
  2. List (rows of like things): five sections: Who you are, Password, Claude, Plugins and Conversations, each with its own Save, across the middle, rows 2 to 7 of 8
  3. List (rows of like things): Conversations: your sessions with Claude here, newest first, divided by hairlines, each a download, across the middle, rows 6 to 7 of 8, inside block 2 (List: five sections)
  4. Footer (the band at the foot): your commits carry the git name and email above, across the bottom, row 8 of 8
Notes:
  A document tab: the bar band, the list of bands, a quiet footer (docSurface). Conversations lists the account's own sessions with Claude, newest first, divided by hairlines as the Artifacts list is, each a download.

### the Analysis tab (Web app)

Platform: a responsive web app: the layout holds at phone and desktop widths, and every tap target is at least 44px on a coarse pointer.
Layout of the Analysis tab on a desktop frame (12 columns by 8 rows), from the Blank template, numbered in drawing order (a later block draws over an earlier one where they overlap):
  1. Header (the band at the top): the bar: the scanners' reports, by space, across the top, row 1 of 8
  2. List (rows of like things): findings grouped by space and scanner, across the bottom, rows 2 to 8 of 8
  3. Card (a box holding one thing): a finding: severity as a badge, its title; opens to its detail, across the middle, row 3 of 8, inside block 2 (List: findings grouped by space and scanner)
Notes:
  A document tab: the bar band, the list of bands, a quiet footer (docSurface). With no reports folder connected the tab says so in one line and where to read how.

### the Spaces tab (Web app)

Platform: a responsive web app: the layout holds at phone and desktop widths, and every tap target is at least 44px on a coarse pointer.
Layout of the Spaces tab on a desktop frame (12 columns by 8 rows), from the Blank template, numbered in drawing order (a later block draws over an earlier one where they overlap):
  1. Header (the band at the top): the bar: search, the trash, and New space (a name alone), across the top, row 1 of 8
  2. List (rows of like things): every space the account may see, across the bottom, rows 2 to 8 of 8
  3. Card (a box holding one thing): a space: its name with its star and archive, its repositories, who is working there; Start agent, Add repository, Edit, across the middle, row 3 of 8, inside block 2 (List: every space the account may see)
Notes:
  A document tab: the bar band, the list of bands, a quiet footer (docSurface). Lock warns which sessions are running and ends them all; a user's account cannot lock or unlock. As built (R138, 25 Oct): a space is made first, with a name alone (spaces and punctuation kept), and repositories are added to it; every repository is in one space. A card per space (.pcard.pflip in tab-projects.js), two faces in one grid cell so the card keeps its size. No rule divides anything inside a card: space groups its parts (the operator, 25 Oct), and its buttons share its width, wrapping on the back. The front: the space's color down its edge, its name with its star (a favorite, filled) and Archive as icons by it (pressed in, in the accent, where set; both each person's own: an archived space works as any other, its card in the Archived fold shut at the page's foot, star, group and every control kept, a favorite still on Home; the operator, 17 Nov) and the lock mark, its id and node in --f-data with who has a session there (the dot, a word and the agent each) on the same line, each repository a row whose name opens its notebook with its branch beside it, the one notice, and Start agent (on the first repository), Add repository and Edit. A press on the card itself opens nothing. Edit turns the card over (rotateY over .42s on the page's ease-out; the faces swap without it under reduced motion) to its back, the same size as the front: the name with its pencil (rename), each repository with its icons (a shell in it, its git host, lending your phone where it is connected on its node, rename, move to another space, delete to the trash, in --bad), and along the foot one line of icon buttons named for a hover and a screen reader: Color (filled with the space's color), Group, Lock (in the accent while locked; its owner's or an administrator's), Report bug (which repository, the first picked) and Settings, Delete space (in --bad) only for one with nothing in it; The star and Archive are by the name on the front. Back turns it back, saving nothing: each control on the back saves its own (the operator, 26 Oct), and wears the card's color as the front's buttons do. Each face's buttons are one line (the operator, 25 Oct), the front's as words sharing the card's width. No menu on the card. Add repository opens the create dialog into that space without the node and the dials, which are the space's. The trash says the space a repository was deleted from; Put back returns it there, or asks which space when that one is gone. A repository's page header keeps Start agent, Shell and its menu (link, phone, report, archive, lock, Add to favorites, settings), names its space, and switches between the space's repositories when it has several.
This page's own rules:
  the-spaces-tab/no-repository-card: For the Spaces tab. A space with no repository (R208, the operator, 3 Nov) is a place to run an agent that builds containers and VMs: its card lists no repository and says so in the note voice (no repository: a session here builds containers and VMs; Add repository makes it a coding space), Start agent is live on it as on any card, its back carries no Report bug (there is no tracker) and Delete space (its folder goes with it), and nothing on it opens a notebook: a press that would (Home's glance, a search) opens its settings dialog instead.

#### Rules of the Spaces tab's own

##### the-spaces-tab/no-repository-card

For the Spaces tab. A space with no repository (R208, the operator, 3 Nov) is a place to run an agent that builds containers and VMs: its card lists no repository and says so in the note voice (no repository: a session here builds containers and VMs; Add repository makes it a coding space), Start agent is live on it as on any card, its back carries no Report bug (there is no tracker) and Delete space (its folder goes with it), and nothing on it opens a notebook: a press that would (Home's glance, a search) opens its settings dialog instead.

### a notebook: Briefing (Web app)

Platform: a responsive web app: the layout holds at phone and desktop widths, and every tap target is at least 44px on a coarse pointer.
Layout of a notebook: Briefing on a desktop frame (12 columns by 8 rows), from the Blank template, numbered in drawing order (a later block draws over an earlier one where they overlap):
  1. Tabs (a strip of tabs switching one area): the views: Briefing, Design, Roadmap, Bugs, Git, Artifacts, Docker, Tests, Analysis, across the top, row 1 of 8
  2. Header (the band at the top): the head row: what every session here starts with, and History, across the middle, row 2 of 8
  3. Chart (a chart or a meter): Code base: open by default; the languages as one bar, counted from what git tracks, across the middle, row 3 of 8
  4. List (rows of like things): Your rules: standing ones in full, named ones with what calls for each, across the middle, rows 4 to 5 of 8
  5. Text (a block of prose): What a session is sent: the exact text, its size, and each part against its share, across the middle, row 6 of 8
  6. List (rows of like things): Memories: a fold, shut by default, its count on the title; Write a memory inside, across the middle, row 7 of 8
  7. Footer (the band at the foot): Save and Revert: what was changed is a draft until Save, across the bottom, row 8 of 8
Notes:
  What a session is sent is shut by default: a thing to check, not to read every time. It turns amber when a part is over its share of a session's prompt, and says what that part left out. Memories fold shut by default and Code base stays open (30 Sep): the languages are one glance, the memories a list to open when wanted.

### a notebook: Design (Web app)

Platform: a responsive web app: the layout holds at phone and desktop widths, and every tap target is at least 44px on a coarse pointer.
Layout of a notebook: Design on a desktop frame (12 columns by 14 rows: the frame shows 8 of them, and the page scrolls), from the Blank template, numbered in drawing order (a later block draws over an earlier one where they overlap):
  1. Tabs (a strip of tabs switching one area): the views: Briefing, Design, Roadmap, Bugs, Git, Artifacts, Docker, Tests, Analysis, across the top, row 1 of 14
  2. Header (the band at the top): the head row: how many pages, whether docs/design-language.md is written and current, and Write the file, across the middle, row 2 of 14
  3. Content (the main reading or working area): Pages: a fold, closed on a new tab, its count on the fold; one page shown at a time, across the middle, rows 3 to 9 of 14
  4. Form (fields a person fills in): Add page: the platform, the template it starts from, or a copy of a page here (blank by default), across the middle, row 3 of 14, inside block 3 (Content: Pages)
  5. Form (fields a person fills in): the page pulldown, then the page's For, Key, Platform, Frame and Rows, across the middle, row 4 of 14, inside block 3 (Content: Pages)
  6. Content (the main reading or working area): the board: the blocks on the frame in the space's colors; drag to move, a corner to size; a child stays in its parent, on the left, columns 1 to 8 of 12, rows 5 to 7 of 14, inside block 3 (Content: Pages)
  7. List (rows of like things): the layers, top first: each block's name; tap to select, up and down to reorder, on the right, columns 9 to 12 of 12, rows 5 to 7 of 14, inside block 3 (Content: Pages)
  8. Form (fields a person fills in): the selected block: Kind, what it's for, Inside (the block it is part of), Remove block; Add block above it, across the middle, row 8 of 14, inside block 3 (Content: Pages)
  9. Card (a box holding one thing): Rules: what holds for this page alone, as PAGE/RULE, the Briefing's list; then Notes and Remove page, across the middle, row 9 of 14, inside block 3 (Content: Pages)
  10. List (rows of like things): Themes: a fold, closed on a new tab; the count and the default's type and corners on the fold; one shown at a time, across the middle, rows 10 to 13 of 14
  11. Form (fields a person fills in): Add theme from blank, a preset's ten colors or a copy of a theme here; Governs; Theme pulldown, the first the default, across the middle, row 10 of 14, inside block 10 (List: Themes)
  12. Form (fields a person fills in): the theme: Name, Mode, Fill from; its Type, Corners, Space and Motion, custom naming a rule of its own; Families, across the middle, row 11 of 14, inside block 10 (List: Themes)
  13. Card (a box holding one thing): Rules: the default theme's are the design's, another's hold for it alone as THEME/RULE; the Briefing's list, across the middle, row 12 of 14, inside block 10 (List: Themes)
  14. List (rows of like things): Colors: each a name, a hex chip and what it is for, added and cut one by one, across the middle, row 13 of 14, inside block 10 (List: Themes)
  15. Footer (the band at the foot): Save and Revert: what was changed is a draft until Save, across the bottom, row 14 of 14
Notes:
  Two sections, Pages and Themes, each standing open like every other section, each showing one entry on its pulldown. The design language is each theme's: the first theme is the default and its type, corners, space, motion, families and rules are the design's; another theme's hold for it alone. A page keeps rules of its own under its board. Adding is inside the section it adds to: a new page from a platform and a template (Blank, App shell, Dashboard, Landing page, List and detail, Settings for a desktop frame; Mobile app and Mobile feed for a phone's), or a copy of a page here (blocks, layouts, rules and notes), and a new theme blank, from a preset or as a copy of a theme (colors, choices and rules); blank is the default. The board is the width of the view with the layers list beside it, top layer first; a later layer draws over an earlier one, and a block can be inside another, drawn over it and kept within it however either moves, so a card sits in a list and a pill in a bar. The view is passive: no prompt, no Copy, nothing sent to a session; a session reads the design through aerie design show and the rules that reach it.

### a notebook: Roadmap (Web app)

Platform: a responsive web app: the layout holds at phone and desktop widths, and every tap target is at least 44px on a coarse pointer.
Layout of a notebook: Roadmap on a desktop frame (12 columns by 8 rows), from the Blank template, numbered in drawing order (a later block draws over an earlier one where they overlap):
  1. Tabs (a strip of tabs switching one area): the views: Briefing, Design, Roadmap, Bugs, Git, Artifacts, Docker, Tests, Analysis, across the top, row 1 of 8
  2. Header (the band at the top): the head row: what is on the list, and History, across the middle, row 2 of 8
  3. Form (fields a person fills in): Add an item, and Reorder, across the middle, row 3 of 8
  4. List (rows of like things): the items, each a fold like a bug's row, across the middle, rows 4 to 7 of 8
  5. Card (a box holding one thing): an item's row: the caret level with the words, its number, the words, which open it on a slide; the pencil edits, across the middle, row 4 of 8, inside block 4 (List: the items)
  6. Button (an action to press): the right button group: edit, shelve, done, and Send to Claude with the Claude mark, last, on the right, columns 10 to 12 of 12, row 4 of 8, inside block 5 (Card: an item's row)
  7. List (rows of like things): behind the fold: its steps, a done one struck with a tick where its number was; the next step sends, across the middle, rows 5 to 7 of 8, inside block 4 (List: the items)
  8. Footer (the band at the foot): Save and Revert: what was changed is a draft until Save, across the bottom, row 8 of 8
Notes:
  An item folds like a bug's row (30 Sep): its words open it on the same slide, its buttons act on it, the send button wears the Claude mark and sits last in the right group. A parked item is dim and carries no steps. Finished items are behind their own view, not at the foot of this one.

### a notebook: Bugs (Web app)

Platform: a responsive web app: the layout holds at phone and desktop widths, and every tap target is at least 44px on a coarse pointer.
Layout of a notebook: Bugs on a desktop frame (12 columns by 8 rows), from the Blank template, numbered in drawing order (a later block draws over an earlier one where they overlap):
  1. Tabs (a strip of tabs switching one area): the views: Briefing, Design, Roadmap, Bugs, Git, Artifacts, Docker, Tests, Analysis, across the top, row 1 of 8
  2. Header (the band at the top): the head row: how many are open, and History, across the middle, row 2 of 8
  3. Form (fields a person fills in): Report a bug: the title, where it lives, how to reproduce it, the severity, across the middle, row 3 of 8
  4. Search (a search box): the sort bar: by severity, newest, oldest, recently changed or title, across the middle, row 4 of 8
  5. List (rows of like things): the bugs, open first, across the bottom, rows 5 to 8 of 8
  6. Card (a box holding one thing): a bug's row: number, severity as a badge, title; opens on a slide to its fields, notes and what fixed it, across the middle, row 5 of 8, inside block 5 (List: the bugs)
Notes:
  Severity wears the badge palette: the same colors on every scheme.

### a notebook: Git (Web app)

Platform: a responsive web app: the layout holds at phone and desktop widths, and every tap target is at least 44px on a coarse pointer.
Layout of a notebook: Git on a desktop frame (12 columns by 8 rows), from the Blank template, numbered in drawing order (a later block draws over an earlier one where they overlap):
  1. Tabs (a strip of tabs switching one area): the views: Briefing, Design, Roadmap, Bugs, Git, Artifacts, Docker, Tests, Analysis, across the top, row 1 of 8
  2. Header (the band at the top): the head row: the branch and how it stands with its host, and Refresh, across the middle, row 2 of 8
  3. Button (an action to press): the network bar: Fetch, Pull and Push, as the space's push rights allow, across the middle, row 3 of 8
  4. List (rows of like things): Changes: what is not committed, each file opening to its diff, and Commit all, across the middle, rows 4 to 5 of 8
  5. List (rows of like things): Branches, and Commits drawn as a graph in lanes, across the bottom, rows 6 to 8 of 8
  6. List (rows of like things): CI: what the daily look found, a row each; a moving label or an action behind carries Fix, written uncommitted, across the bottom, row 8 of 8
Notes:
  Reads to a beginner and stays exact for a developer: the host is named (GitHub, Gitea), never 'origin'. Whose working tree it is is said to anybody else, who is offered nothing that changes it. Fix commits nothing and pushes nothing (R117): the change shows in Changes, to commit or send to Claude, and a commit pin is never offered one.

### a notebook: Artifacts (Web app)

Platform: a responsive web app: the layout holds at phone and desktop widths, and every tap target is at least 44px on a coarse pointer.
Layout of a notebook: Artifacts on a desktop frame (12 columns by 8 rows), from the Blank template, numbered in drawing order (a later block draws over an earlier one where they overlap):
  1. Tabs (a strip of tabs switching one area): the views: Briefing, Design, Roadmap, Bugs, Git, Artifacts, Docker, Tests, Analysis, across the top, row 1 of 8
  2. Header (the band at the top): the head row: what the space ships, and Download source, across the middle, row 2 of 8
  3. Card (a box holding one thing): Build: the node it builds on. Version: where the tree is, and the buttons that move it, across the middle, rows 3 to 4 of 8
  4. Text (a block of prose): the dev instance: what it was built from, and whether the tree has moved past it, across the middle, row 5 of 8
  5. List (rows of like things): what is in dist/, divided by hairlines, each a download, across the bottom, rows 6 to 8 of 8
  6. List (rows of like things): Captures apart: each with whose it is and its age, and how long they are kept, across the bottom, row 8 of 8, inside block 5 (List: what is in dist/)
Notes:
  Captures are not what the space ships, so they are listed apart, each saying whose it is, and go by age. Each artifact row ends with a pin, the space row's own tack: lit when pinned, with a pinned tag beside the name and who pinned it on the line under. Dev builds past the newest few of each (the space's Dev builds kept, 3 unless changed, 0 for all) go when the tab draws, and a line over the list says so; a pinned one stays. An .apk or .aab row offers Sign for each key its space has. A signed build wears a signed tag beside its name and, under its provenance, which key signed it, from which build and what verified, then the whole certificate fingerprint, wrapping on a phone, with Copy for F-Droid as a link beside it.

### a notebook: Docker (Web app)

Platform: a responsive web app: the layout holds at phone and desktop widths, and every tap target is at least 44px on a coarse pointer.
Layout of a notebook: Docker on a desktop frame (12 columns by 8 rows), from the Blank template, numbered in drawing order (a later block draws over an earlier one where they overlap):
  1. Tabs (a strip of tabs switching one area): the views: Briefing, Design, Roadmap, Bugs, Git, Artifacts, Docker, Tests, Analysis, across the top, row 1 of 8
  2. Header (the band at the top): the head row: this space's containers, and a way to the Docker tab, across the middle, row 2 of 8
  3. List (rows of like things): the space's own containers, each as the Docker tab draws one, across the bottom, rows 3 to 8 of 8
Notes:
  The same rows as the Docker tab, for one space: a second drawing of them would be a second place to be wrong.

### a notebook: Tests (Web app)

Platform: a responsive web app: the layout holds at phone and desktop widths, and every tap target is at least 44px on a coarse pointer.
Layout of a notebook: Tests on a desktop frame (12 columns by 8 rows), from the Blank template, numbered in drawing order (a later block draws over an earlier one where they overlap):
  1. Tabs (a strip of tabs switching one area): the views: Briefing, Design, Roadmap, Bugs, Git, Artifacts, Docker, Tests, Analysis, across the top, row 1 of 8
  2. Header (the band at the top): the head row: the last run, and Open the run's output, across the middle, row 2 of 8
  3. Search (a search box): sort and filter: by suite, by what is slow, by what is flagged, across the middle, row 3 of 8
  4. Table (columns of data): the tests, across the bottom, rows 4 to 8 of 8
  5. Card (a box holding one thing): a test's row: suite, name, what it protects, how long it took, whether it is suspect; opens to describe it, across the middle, row 5 of 8, inside block 4 (Table: the tests)
Notes:
  With no run on record the view says how one is made, in one line.

### a notebook: Analysis (Web app)

Platform: a responsive web app: the layout holds at phone and desktop widths, and every tap target is at least 44px on a coarse pointer.
Layout of a notebook: Analysis on a desktop frame (12 columns by 8 rows), from the Blank template, numbered in drawing order (a later block draws over an earlier one where they overlap):
  1. Tabs (a strip of tabs switching one area): the views: Briefing, Design, Roadmap, Bugs, Git, Artifacts, Docker, Tests, Analysis, across the top, row 1 of 8
  2. Header (the band at the top): the head row: the scanners' findings for this space, and History, across the middle, row 2 of 8
  3. List (rows of like things): findings by scanner, severity as a badge; one can be sent to the session or dismissed with a reason, across the bottom, rows 3 to 8 of 8
Notes:
  The space's share of the Analysis tab.

### a space's settings (Web app)

Platform: a responsive web app: the layout holds at phone and desktop widths, and every tap target is at least 44px on a coarse pointer.
Layout of a space's settings on a desktop frame (12 columns by 8 rows), from the Blank template, numbered in drawing order (a later block draws over an earlier one where they overlap):
  1. Overlay (a dialog, sheet, drawer, popover or toast over the page): Space settings, the longest dialog, so the one that proves the layout, down the middle, full height, columns 4 to 9 of 12
  2. Header (the band at the top): Space settings: the space's name, in the middle, columns 4 to 9 of 12, row 1 of 8, inside block 1 (Overlay: Space settings)
  3. Form (fields a person fills in): groups headed by a label: name and color, the remote, the node and Also sees, build and test, Agents may, yours here, in the middle, columns 4 to 9 of 12, rows 2 to 7 of 8, inside block 1 (Overlay: Space settings)
  4. Footer (the band at the foot): the foot: Unlink and Delete apart from Save; Save lists what takes a restart and asks: end the session now, or keep it, in the middle, columns 4 to 9 of 12, row 8 of 8, inside block 1 (Overlay: Space settings)
Notes:
  In sections, each headed by a label band drawn as a divide (small, dim, uppercase, a rule under it), and a section with no field showing hidden with its heading: The space (name, color, People), the remote (its own door, no heading), Where it runs (node, other nodes, the node's GPU, where tests run), File access (a tick to serve the space's files over FTPS, the port with the nine after it said beside it, a row per account that sees the space with its access picker: No access, Read, Read and write; under them where it runs or, in red, why it is not; an account without the ftp grant is shown only that it is on, and where), What a session sees (Reads, Also sees, Also reaches: a row per address, an address field with, when the space is on more than one node, a tick per node beside it and its bin, then Add an address, and a line saying whether the space's nodes filter at all), Build and test (commands, outputs, captures kept, dev builds kept), Agents may (a change asked for while a test runs, then the permissions: the notebook's four and the wiki, build and test and the container, the two signing ones, reports), Yours on this space, Sessions on this space. Groups headed by a label, every line a field band, one foot. Agents may is ten dials (Write the wiki the newest), each auto, ask or deny, and Write the wiki may also be hidden, which keeps the wiki from a session, reading included. Also sees names the shares on the node a session may see, an allow-list since 29 Sep. During a test run says what a new ask does to a run going: wait for it, or interrupt it. Yours on this space is the person's own: model, effort, replies, questions. A saved change that takes a session restart (the model, the node, what it sees, the test setting) is listed at Save, which asks whether to end the running session now or keep it going (30 Sep). Unlink and Delete space are apart from Save, and each asks once, saying what goes and what stays. The node's GPU, with the Claude settings, says whether the space may compute on its node's NVIDIA card; off runs it as if the machine had none. People names the owner (a picker for the owner and AerieOS's owner; the owner's pick is an offer, said under the picker, that waits for acceptance and shows with Withdraw) and Invite only, both staged until Save, who is on it, each invitation waiting with Withdraw, and Invite with its account picker, which acts on the press.
This page's own rules:
  a-space-s-settings/a-card-door: For a space's settings. A card's Settings opens the space's settings as a dialog (R208, the operator, 3 Nov): what is the space's as a whole, General without the name field (the card's back renames it), People, Agents may, Just for you, Nodes, Deploy, What sessions reach, Toolchains and Running sessions, with Repository, Build and test, File access and Snapshots left out and one line at its foot saying they are each repository's, in its notebook's Settings view, which keeps every section as it was, as the notebook's Permissions view does. Each setting is edited where it lives (R223, the operator, 7 Nov): what every repository of the space shares (People, Deploy, What sessions reach, Toolchains, its coding agents, its node and Also works on, the GPU dial) is the space's, drawn on a repository's notebook Settings view as the space's, its controls dead, with one line in the note voice and Open the space's settings, and never sent from there; a repository may narrow the space's hosting nodes for its containers (Its containers may go to, under Nodes) and set its test node apart as a dial is; under each dial of the space's dialog a line names each repository that sets it apart and its value. Tests run is one choice under a repository's Build and test (a node of the space's, or its dev instance first or only); there is no daily snapshot switch (0 days kept is none) and no per-space terminal colors (Profile's are every space's); Move the version is set on the Permissions view, the Artifacts view saying it with Change on Permissions; Its VMs may hold shows only where Make VMs is not deny. On a space with no repository the dialog is the space's only settings, and the dials, the test-run pick and the commit identity that need code are not drawn: Agents may holds Run its container, Make VMs, Install a tool pack, Report AerieOS bugs and Use a lent PC alone. Deploy (R281 step 3, 26 Nov) is the space's Kubernetes environments as a list of records (Environment with a production pill, Where as cluster / namespace, Deploys), drawn once a cluster is kept or the space has an environment and never on a space with no repository; a record's Save rings Making it ready while its namespace is made ready on the cluster, a refusal leaving the record open as typed, and the section has no Save of its own.

#### Rules of a space's settings's own

##### a-space-s-settings/a-card-door

For a space's settings. A card's Settings opens the space's settings as a dialog (R208, the operator, 3 Nov): what is the space's as a whole, General without the name field (the card's back renames it), People, Agents may, Just for you, Nodes, Deploy, What sessions reach, Toolchains and Running sessions, with Repository, Build and test, File access and Snapshots left out and one line at its foot saying they are each repository's, in its notebook's Settings view, which keeps every section as it was, as the notebook's Permissions view does. Each setting is edited where it lives (R223, the operator, 7 Nov): what every repository of the space shares (People, Deploy, What sessions reach, Toolchains, its coding agents, its node and Also works on, the GPU dial) is the space's, drawn on a repository's notebook Settings view as the space's, its controls dead, with one line in the note voice and Open the space's settings, and never sent from there; a repository may narrow the space's hosting nodes for its containers (Its containers may go to, under Nodes) and set its test node apart as a dial is; under each dial of the space's dialog a line names each repository that sets it apart and its value. Tests run is one choice under a repository's Build and test (a node of the space's, or its dev instance first or only); there is no daily snapshot switch (0 days kept is none) and no per-space terminal colors (Profile's are every space's); Move the version is set on the Permissions view, the Artifacts view saying it with Change on Permissions; Its VMs may hold shows only where Make VMs is not deny. On a space with no repository the dialog is the space's only settings, and the dials, the test-run pick and the commit identity that need code are not drawn: Agents may holds Run its container, Make VMs, Install a tool pack, Report AerieOS bugs and Use a lent PC alone. Deploy (R281 step 3, 26 Nov) is the space's Kubernetes environments as a list of records (Environment with a production pill, Where as cluster / namespace, Deploys), drawn once a cluster is kept or the space has an environment and never on a space with no repository; a record's Save rings Making it ready while its namespace is made ready on the cluster, a refusal leaving the record open as typed, and the section has no Save of its own.

### a new space (Web app)

Platform: a responsive web app: the layout holds at phone and desktop widths, and every tap target is at least 44px on a coarse pointer.
Layout of a new space on a desktop frame (12 columns by 10 rows: the frame shows 8 of them, and the page scrolls), from the Blank template, numbered in drawing order (a later block draws over an earlier one where they overlap):
  1. Overlay (a dialog, sheet, drawer, popover or toast over the page): New space, in the middle, columns 4 to 9 of 12, rows 2 to 7 of 10
  2. Button (an action to press): the source as one row of buttons: a new repository, a clone, an archive, in the middle, columns 4 to 9 of 12, row 3 of 10, inside block 1 (Overlay: New space)
  3. Form (fields a person fills in): the fields under them, changing with the pick: its name, its node, what an agent may do, in the middle, columns 4 to 9 of 12, rows 4 to 6 of 10, inside block 1 (Overlay: New space)
  4. Footer (the band at the foot): Cancel and Create, the filled button, in the middle, columns 4 to 9 of 12, row 7 of 10, inside block 1 (Overlay: New space)
  5. Overlay (a dialog, sheet, drawer, popover or toast over the page): First session: the brief typed when the space was made, the model and effort, Build it or Start without it, in the middle, columns 4 to 9 of 12, rows 9 to 10 of 10
Notes:
  The three sources are one row of buttons and the fields under them change with the pick. A clone or a link runs as a job the Spaces card reports; the dialog does not wait on the network. Then, on the first start of Claude, the brief's dialog: Shown the first time Claude is started on a space that has a brief. Either button takes the brief out of the tree.

### a new container (Web app)

Platform: a responsive web app: the layout holds at phone and desktop widths, and every tap target is at least 44px on a coarse pointer.
Layout of a new container on a desktop frame (12 columns by 8 rows), from the Blank template, numbered in drawing order (a later block draws over an earlier one where they overlap):
  1. Overlay (a dialog, sheet, drawer, popover or toast over the page): New container: its name, its node and space, and its definition from an image or a compose file, in the middle, columns 4 to 9 of 12, rows 2 to 7 of 8
Notes:
  The env file's values are never shown back, only its keys.
This page's own rules:
  a-new-container/app-panel: For New container from the Library (R238, the operator, 13 and 18 Nov). An app's part of the dialog is a panel of its own, the first band, set apart from the name, the node and the definition under it: an inset box (`.apppanel`: the page's ground under the box's, a hairline edge, a card's corners, 12px inside) headed as the app's Library card is, its icon in its square, its name in the UI voice and under it who it is by in the quiet voice beside its tier's pill. Its fields are inside as a form's are (`.fgrid`, a label over each): the ones its bbapp.json declares, in their order, then AerieOS's own its compose reads (Runs as, a uid:gid; Time zone, a pulldown; Its port, a number's width). Each kind is drawn as the forms rule says its answer is: a folder a path with suggestions (each of the node's pools and shares with the app's own folder under it, the first filled in where the app names a folder of its own, and left to the person where it is a share's, a library or a set of files), a port a number, a choice a pulldown, a switch a tick, a secret a masked field made for it when left empty and never made again, a line of text a field with the app's own example. A field's help is its label's ?, as every form's is. An app on the machine's own network says so in a line under its head (it answers on its own port, which is not picked), and one that is going says what to install in its place in the warn voice.

The panel owns what it declares (the operator, 18 Nov): the Compose tab shows the app's file as the catalog wrote it, read-only, with Edit the definition by hand under it, and the Environment tab holds only the other variables, a declared one typed there refused by name. There is no From an image tab and no Fill the definition in. Edit the definition by hand asks first, once, and then folds the panel to one line in the note voice (Edited by hand: APP's fields no longer apply; Start over from the Library puts them back) with the compose file and the environment plain text, the values as they stood. Configure on a container made from an app opens this dialog on the same panel, each value read back from the container's environment; a field a newer definition added shows with its default.

#### Rules of a new container's own

##### a-new-container/app-panel

For New container from the Library (R238, the operator, 13 and 18 Nov). An app's part of the dialog is a panel of its own, the first band, set apart from the name, the node and the definition under it: an inset box (`.apppanel`: the page's ground under the box's, a hairline edge, a card's corners, 12px inside) headed as the app's Library card is, its icon in its square, its name in the UI voice and under it who it is by in the quiet voice beside its tier's pill. Its fields are inside as a form's are (`.fgrid`, a label over each): the ones its bbapp.json declares, in their order, then AerieOS's own its compose reads (Runs as, a uid:gid; Time zone, a pulldown; Its port, a number's width). Each kind is drawn as the forms rule says its answer is: a folder a path with suggestions (each of the node's pools and shares with the app's own folder under it, the first filled in where the app names a folder of its own, and left to the person where it is a share's, a library or a set of files), a port a number, a choice a pulldown, a switch a tick, a secret a masked field made for it when left empty and never made again, a line of text a field with the app's own example. A field's help is its label's ?, as every form's is. An app on the machine's own network says so in a line under its head (it answers on its own port, which is not picked), and one that is going says what to install in its place in the warn voice.

The panel owns what it declares (the operator, 18 Nov): the Compose tab shows the app's file as the catalog wrote it, read-only, with Edit the definition by hand under it, and the Environment tab holds only the other variables, a declared one typed there refused by name. There is no From an image tab and no Fill the definition in. Edit the definition by hand asks first, once, and then folds the panel to one line in the note voice (Edited by hand: APP's fields no longer apply; Start over from the Library puts them back) with the compose file and the environment plain text, the values as they stood. Configure on a container made from an app opens this dialog on the same panel, each value read back from the container's environment; a field a newer definition added shows with its default.

### waiting for your approval (Web app)

Platform: a responsive web app: the layout holds at phone and desktop widths, and every tap target is at least 44px on a coarse pointer.
Layout of waiting for your approval on a desktop frame (12 columns by 8 rows), from the Blank template, numbered in drawing order (a later block draws over an earlier one where they overlap):
  1. Overlay (a dialog, sheet, drawer, popover or toast over the page): What a session added under an ask dial: each with Approve and Deny, in the middle, columns 4 to 9 of 12, rows 2 to 7 of 8
Notes:
  Reached from the bell. A thing approved lands as if the session had been allowed it; a thing denied is said to the session.

### the gear (Web app)

Platform: a responsive web app: the layout holds at phone and desktop widths, and every tap target is at least 44px on a coarse pointer.
Layout of the gear on a desktop frame (12 columns by 8 rows), from the Blank template, numbered in drawing order (a later block draws over an earlier one where they overlap):
  1. Overlay (a dialog, sheet, drawer, popover or toast over the page): Layout (reset the sidebar's cards), Color scheme (twelve swatches), Account (Profile), in the middle, columns 4 to 9 of 12, rows 2 to 7 of 8
Notes:
  A menu under the gear, not a modal. A swatch applies on the press, the one setting that does: a theme is looked at, not decided. Each swatch is drawn in its own scheme.

### about (Web app)

Platform: a responsive web app: the layout holds at phone and desktop widths, and every tap target is at least 44px on a coarse pointer.
Layout of about on a desktop frame (12 columns by 8 rows), from the Blank template, numbered in drawing order (a later block draws over an earlier one where they overlap):
  1. Overlay (a dialog, sheet, drawer, popover or toast over the page): About: the build, the license, Getting started and Changelog, in the middle, columns 4 to 9 of 12, rows 2 to 7 of 8
Notes:
  The changelog is the same text the welcome panel shows after an update.

### the app: signing in (Android app)

Platform: an Android app: Material's shapes and elevation, 48dp touch targets, the app's sections as a bottom bar, and the system's back gesture respected.
Layout of the app: signing in on a phone frame (6 columns by 12 rows), from the Mobile app template, numbered in drawing order (a later block draws over an earlier one where they overlap):
  1. Header (the band at the top): AerieOS, and what to sign in with, across the middle, rows 4 to 5 of 12
  2. Form (fields a person fills in): the dashboard's address, the account, the password, and Sign in, across the middle, rows 6 to 9 of 12
  3. Text (a block of prose): over http, said before the sign-in: it travels in the clear, across the middle, row 10 of 12
Notes:
  The app wears the dashboard's schemes by the same names and hexes, chosen under More and kept on the device. Text buttons are the accent; a filled button is the deep accent with ink.

### the app: spaces (Android app)

Platform: an Android app: Material's shapes and elevation, 48dp touch targets, the app's sections as a bottom bar, and the system's back gesture respected.
Layout of the app: spaces on a phone frame (6 columns by 12 rows), from the Mobile app template, numbered in drawing order (a later block draws over an earlier one where they overlap):
  1. Header (the band at the top): the mark, the account, the build and the host, and Refresh; with two AerieOS installs, the title switches between them, across the top, row 1 of 12
  2. Card (a box holding one thing): the bell's row: questions waiting and nodes that need attention, a bar down its side, across the middle, rows 2 to 3 of 12
  3. Card (a box holding one thing): the doctor's problems, for an administrator, only when there are any, across the middle, row 4 of 12
  4. Search (a search box): a box to find a space in, once the list is longer than a screen, across the middle, row 5 of 12
  5. List (rows of like things): spaces, across the middle, rows 6 to 11 of 12
  6. Card (a box holding one thing): a space: the color down the side, the session as working or waiting on you, what is waiting, across the middle, row 7 of 12, inside block 5 (List: spaces)
  7. Navigation (the way around: tabs or a menu): the bottom bar: Spaces, Approvals, Nodes (an administrator), More, across the bottom, row 12 of 12
Notes:
  The question a phone is picked up to ask is whether it is done, so the list answers it before anything is opened. Pull down to read again, on every list.

### the app: a space (Android app)

Platform: an Android app: Material's shapes and elevation, 48dp touch targets, the app's sections as a bottom bar, and the system's back gesture respected.
Layout of the app: a space on a phone frame (6 columns by 12 rows), from the Mobile app template, numbered in drawing order (a later block draws over an earlier one where they overlap):
  1. Header (the band at the top): the space, its color, and its session as a pill: working, or waiting on you, across the top, row 1 of 12
  2. Tabs (a strip of tabs switching one area): the view strip, scrolling sideways: Claude first, then the notebook's views, Git, Settings, across the middle, row 2 of 12
  3. Form (fields a person fills in): Claude: what the session is doing, and a box to say a line to it, across the middle, rows 3 to 5 of 12
  4. List (rows of like things): your conversations here, each with Read the end and Share, across the middle, rows 6 to 11 of 12
  5. Navigation (the way around: tabs or a menu): the bottom bar: Spaces, Approvals, Nodes (an administrator), More, across the bottom, row 12 of 12
Notes:
  A space opens on Claude. The terminals stay the browser's; a line said here goes into the account's own session and nowhere else. Design is read here, not edited. Docker's Start, Stop and Rebuild each ask before they act. Settings are a draft until Save.

### the app: approvals (Android app)

Platform: an Android app: Material's shapes and elevation, 48dp touch targets, the app's sections as a bottom bar, and the system's back gesture respected.
Layout of the app: approvals on a phone frame (6 columns by 12 rows), from the Mobile app template, numbered in drawing order (a later block draws over an earlier one where they overlap):
  1. Header (the band at the top): Approvals, and Refresh, across the top, row 1 of 12
  2. List (rows of like things): what waits on your answer: the ask, its reason, its command, Deny and Allow, across the middle, rows 2 to 6 of 12
  3. List (rows of like things): changes a session has waiting, by space, each with Deny and Approve, across the middle, rows 7 to 11 of 12
  4. Navigation (the way around: tabs or a menu): the bottom bar: Spaces, Approvals, Nodes (an administrator), More, across the bottom, row 12 of 12
Notes:
  Root on a node wears red down its side and everything else amber. The same asks arrive as notifications with Approve and Deny on them, which need the phone unlocked.

### the app: nodes (Android app)

Platform: an Android app: Material's shapes and elevation, 48dp touch targets, the app's sections as a bottom bar, and the system's back gesture respected.
Layout of the app: nodes on a phone frame (6 columns by 12 rows), from the Mobile app template, numbered in drawing order (a later block draws over an earlier one where they overlap):
  1. Header (the band at the top): Nodes, and Refresh, across the top, row 1 of 12
  2. List (rows of like things): nodes: live or not down the side, what the machine is, Lock system changes and Drain, across the middle, rows 2 to 11 of 12
  3. Navigation (the way around: tabs or a menu): the bottom bar: Spaces, Approvals, Nodes (an administrator), More, across the bottom, row 12 of 12
Notes:
  An administrator's. Enrolling and the node's sections stay the dashboard's.

### the app: more (Android app)

Platform: an Android app: Material's shapes and elevation, 48dp touch targets, the app's sections as a bottom bar, and the system's back gesture respected.
Layout of the app: more on a phone frame (6 columns by 12 rows), from the Mobile app template, numbered in drawing order (a later block draws over an earlier one where they overlap):
  1. Header (the band at the top): More, across the top, row 1 of 12
  2. Card (a box holding one thing): whether the app and the dashboard are on the same API, and Install it when the app is behind, across the middle, rows 2 to 3 of 12
  3. List (rows of like things): the other pages as rows: Profile, Tools, Jobs, Users, What's new, across the middle, rows 4 to 6 of 12
  4. Form (fields a person fills in): The watch: questions, Tell me when Claude can take a message, how often to ask; one Save, across the middle, rows 7 to 9 of 12
  5. Form (fields a person fills in): Lock: Lock the app when it opens, refused with a sentence where the phone has no screen lock, across the middle, row 6 of 12
  6. List (rows of like things): AerieOS installs: each pairing by name, the one in front ticked; Add another, and Forget, across the middle, row 7 of 12
  7. List (rows of like things): Colors: the twelve schemes, each drawn in its own; About; Sign out, across the middle, rows 10 to 11 of 12
  8. Navigation (the way around: tabs or a menu): the bottom bar: Spaces, Approvals, Nodes (an administrator), More, across the bottom, row 12 of 12
Notes:
  The watch's settings are a draft until Save. The note that Claude is waiting on you names the space first and follows the space's During a test run setting: at once where a new ask interrupts a run, and when the tests finish where it waits for them (30 Sep). The scheme applies on the press, as it does on the dashboard. The lock is the phone's own (fingerprint, face or PIN), asked every time the app comes to the front; nothing of the app's own is stored for it (R133).

### the app: tools (Android app)

Platform: an Android app: Material's shapes and elevation, 48dp touch targets, the app's sections as a bottom bar, and the system's back gesture respected.
Layout of the app: tools on a phone frame (6 columns by 12 rows), from the Mobile app template, numbered in drawing order (a later block draws over an earlier one where they overlap):
  1. Header (the band at the top): Tools, and Refresh, across the top, row 1 of 12
  2. Tabs (a strip of tabs switching one area): the nodes, as chips; never the controller, across the middle, row 2 of 12
  3. Text (a block of prose): the store's path on that node, across the middle, row 3 of 12
  4. List (rows of like things): toolchains: what each is, its version or not installed, Install or Remove for an administrator, across the middle, rows 4 to 11 of 12
  5. Navigation (the way around: tabs or a menu): the bottom bar: Spaces, Approvals, Nodes (an administrator), More, across the bottom, row 12 of 12
Notes:
  Install and Remove ask first, saying the size. Android system images are not here: choosing one wants the room the dashboard's tab has.

### the Roles tab (Web app)

Platform: a responsive web app: the layout holds at phone and desktop widths, and every tap target is at least 44px on a coarse pointer.
Layout of the Roles tab on a desktop frame (12 columns by 8 rows), from the Blank template, numbered in drawing order (a later block draws over an earlier one where they overlap):
  1. Header (the band at the top): the bar: what each account may do: roles given to people, and what each role reads and writes, across the top, row 1 of 8
  2. Form (fields a person fills in): People: accounts as a list beside the picked one: Everywhere roles, its spaces, Add to space, a grid, across the middle, rows 2 to 4 of 8
  3. Form (fields a person fills in): Roles: roles as a list (kind, holders) beside the picked one: Kind, Read and Write per area, across the middle, rows 5 to 7 of 8
Notes:
  Under People on the rail, beside Users, and from the People field of a space's settings for its owner (R152, the operator, 7 Oct). owner and admin are built in and read as every area, with nothing to change and no Save; the owner's account reads as fixed in People. A space's owner who is not an administrator sees only the spaces they own and the roles on the user's spaces. In Roles, Write waits for Read, and the global areas are off for a role on the user's spaces; Remove comes last. In People, a space's roles show only once its tick is on, and Global roles are an administrator's to give. An Everywhere role this account may change opens an instance area's row on its instances (R260, the operator, 16 Oct): beside the area's name a quiet link in the second color, each node or each runner, or N of M nodes when it is held on some, opens a line per node (Nodes, Toolchains, Jobs, New spaces, Storage) or per runner (CI runner) under the area, indented, its Read and Write boxes in the area's columns. The area's own boxes tick or clear every instance and show partly ticked when some are held; every instance at one level is the area held on every one, those added later included. No other area opens. R255 step 9 (the operator, 16 Oct: every space listed for an account on none of them, and half the desk empty): each section a list beside the one picked, the list a column of rows, the picked row in the accent's tint; an account's spaces are only those it is on, Add to space puts it on another; on a phone the list, then the detail over it, its head the way back.

### the Scanners page (Web app)

Platform: a responsive web app: the layout holds at phone and desktop widths, and every tap target is at least 44px on a coarse pointer.
Layout of the Scanners page on a desktop frame (12 columns by 10 rows: the frame shows 8 of them, and the page scrolls), from the Blank template, numbered in drawing order (a later block draws over an earlier one where they overlap):
  1. Header (the band at the top): the bar: Check versions, and Deploy on N nodes while any node holding spaces has none, across the top, row 1 of 10
  2. Content (the main reading or working area): the page head: the newest versions known, when checked, how many nodes scan, across the middle, row 2 of 10
  3. Card (a box holding one thing): Schedule: one timetable for every node (daily, weekly, monthly, Custom), Run now on every node, Turn on or off, across the middle, rows 3 to 4 of 10
  4. List (rows of like things): a section per node: deployed with its versions, not deployed, deploying or update out in its head, across the middle, rows 5 to 8 of 10
  5. Card (a box holding one thing): one node: Runs, Scans, Last run (state pill, when, its log), Reports; then Run now, Update when behind, Remove last, in the middle, columns 2 to 11 of 12, rows 6 to 7 of 10, inside block 4 (List: a section per node)
  6. Table (columns of data): Not covered: each space no scanner reaches, with why (no node, hosts containers only, no scanners on NODE), across the bottom, rows 9 to 10 of 10
Notes:
  A page of the Machines group, off its sub-nav, opened from the Scanners' row under Services on Installed and from their containers' Configure, as the nginx page is (R145, the operator, 26 Oct; R264, 19 Nov, where it was the Containers group's). Every node at once rather than one picked in the bar: the question the page answers is whether every space is covered, which one node's view cannot. Each node is a section whose head says its state as a word (not deployed, deployed, deploying, update out) with the section tinted warn when an update is out, as the nginx page's Image section is. The schedule is one for all nodes, a section of its own first, its timetable in words in its head. Not covered closes the page: a table, never a hint, since each row is a space somebody may act on. A failed run and versions behind are the bell's (kind scan), each with a link to the page and a failed run's log. The SARIF a node sends up lands on the Analysis page as a host scanner's report did, so that page changes nothing.
This page's own rules:
  scanners/every-node: scripts/dashboard/tab-scanners.js, scripts/dashboard/scanners.py; scanners (`aerie design show scanners/every-node` reads it)

#### Rules of the Scanners page's own

##### scanners/every-node

Applies to: scripts/dashboard/tab-scanners.js, scripts/dashboard/scanners.py; scanners

The Scanners page lists every node as a section rather than picking one in the bar: its question is coverage across nodes. A node's state is a word in its section's head, never a colored word alone; Deploy is the one action on a node without scanners, and Remove is last on one with them.

### This controller (Web app)

Platform: a responsive web app: the layout holds at phone and desktop widths, and every tap target is at least 44px on a coarse pointer.
Layout of This controller on a desktop frame (12 columns by 10 rows: the frame shows 8 of them, and the page scrolls), from the Blank template, numbered in drawing order (a later block draws over an earlier one where they overlap):
  1. Content (the main reading or working area): the head, in the facts voice: System, Release, Image, Up, Wall, As a node; a held start's Start, across the top, rows 1 to 2 of 10
  2. Card (a box holding one thing): Updates: the release running against the newest, when checked, Check now, Update to X (dead until newer), across the middle, row 3 of 10
  3. Card (a box holding one thing): Older versions: each one kept, Boot this next, Remove, across the middle, rows 4 to 5 of 10
Notes:
  First in the rail's Controller group on a controller installed bare metal (R90 step 8, R56 step 8; the operator, 27 Oct), and not drawn in the container edition, which has no machine of its own: the page opened there says so in one empty note. What is the controller's and not the node's (split the operator, 9 Nov): the head in the facts voice (system, release, image, up, the wall, and As a node, a link to the machine's row), a held start's Start, the Updates section (Controller settings' own, drawn here too) and Older versions. The machine as a node is a row on the Nodes page like any node's, tagged this machine, with the sections only it carries (The stick, Console, what a stick prepared, the old system's disks and apps); it is in the picker of every page about a node, named NAME (this machine), but the containers' (Containers, nginx, Scanners), since it hosts none: docker there is root over the controller. A Library app on it says so on its card and New container picks another node. A space still picks it as its node, named This machine in every space's node picker.
This page's own rules:
  machine/one-node-one-way: scripts/dashboard/tab-machine.js, scripts/dashboard/tab-nodes.js; this machine, own node (`aerie design show machine/one-node-one-way` reads it)

#### Rules of This controller's own

##### machine/one-node-one-way

Applies to: scripts/dashboard/tab-machine.js, scripts/dashboard/tab-nodes.js; this machine, own node

This controller adds only what is the controller's: its head, its updates, its older versions. The machine as a node is drawn by the Nodes page's own row builder on the Nodes page; a section about a node is written once, in tab-nodes.js or the sections tab-machine.js gives that row, and never on This controller.

### the Network page (Web app)

Platform: a responsive web app: the layout holds at phone and desktop widths, and every tap target is at least 44px on a coarse pointer.
Layout of the Network page on a desktop frame (12 columns by 10 rows: the frame shows 8 of them, and the page scrolls), from the Blank template, numbered in drawing order (a later block draws over an earlier one where they overlap):
  1. Content (the main reading or working area): the head, in the facts voice: Reached at, Port, Served over, Hostname, Nodes, across the top, rows 1 to 2 of 10
  2. List (rows of like things): the sections beside the one picked: Reached at, Nodes dial in, Connection, Reach from outside, on the left, columns 1 to 3 of 12, rows 3 to 10 of 10
  3. Table (columns of data): Nodes dial in: each node, where it dials in from, when seen, how it reaches the controller, on the right, columns 4 to 12 of 12, rows 3 to 5 of 10
  4. Card (a box holding one thing): Connection and Reach from outside: Settings' own groups drawn here, each with Apply and Revert, on the right, columns 4 to 12 of 12, rows 6 to 10 of 10
Notes:
  A page of the Controller group in every edition (R165 step 4; the operator, 22 Oct): how this AerieOS is reached, and the two groups that were about reaching it moved out of Controller settings, Connection (http or https and its certificate) and Reach from outside (the home tunnel), drawn by Settings' own table so a field saves the way it always did (pages-of-settings). The bare-metal install's own ports, bridge, bonds and VLANs are This machine's Network section, not this page's.
This page's own rules:
  network/one-table-two-pages: scripts/dashboard/tab-network.js, scripts/dashboard/tab-settings.js; network page, reach from outside (`aerie design show network/one-table-two-pages` reads it)

#### Rules of the Network page's own

##### network/one-table-two-pages

Applies to: scripts/dashboard/tab-network.js, scripts/dashboard/tab-settings.js; network page, reach from outside

Connection and Reach from outside are one table (tab-settings.js SETTING_GROUPS) drawn on the Network page and nowhere else; a group about reaching the controller goes there, never back under Controller settings.

### the Files page (Web app)

Platform: a responsive web app: the layout holds at phone and desktop widths, and every tap target is at least 44px on a coarse pointer.
Layout of the Files page on a desktop frame (12 columns by 8 rows), from the Blank template, numbered in drawing order (a later block draws over an earlier one where they overlap):
  1. Header (the band at the top): the Machines group's header: the node picked once, its own machine among them on a machine install, across the top, row 1 of 8
  2. Text (a block of prose): the page head: the root and how many folders and files are here, across the middle, row 2 of 8
  3. Tabs (a strip of tabs switching one area): the roots as chips: the spaces folder, pools, the array, adopted disks, shares, across the middle, row 3 of 8
  4. Navigation (the way around: tabs or a menu): where in the root: the root's name then each folder, the last one plain, across the middle, row 4 of 8
  5. Search (a search box): the filter, New folder and Upload; with rows ticked: Rename, Move, Download, Delete, Clear, across the middle, row 5 of 8
  6. Table (columns of data): the folder: a tick and the name, size, modified, owner, a download at the row's end; folders first, across the bottom, rows 6 to 8 of 8
  7. Overlay (a dialog, sheet, drawer, popover or toast over the page): a file shown over the page: picture, video, sound or PDF as itself, else its first 256 KB as text; Download and Close, in the middle, columns 3 to 10 of 12, rows 3 to 7 of 8
Notes:
  R224, the operator 8 Nov: administrators only, every change audited; the roots alone, never the system's folders; a delete goes to the root's .aerieos-trash. Preview and download first; editing a text file in place is a later step.
This page's own rules:
  files/roots-only: files page, file explorer (`aerie design show files/roots-only` reads it)

#### Rules of the Files page's own

##### files/roots-only

Applies to: files page, file explorer

The Files page reaches a node's roots and nothing else: the system's own folders are never offered, and a root's chip says its kind in words (share, adopted), never a path alone; the path is the chip's title.
