// The document-tab scaffold: a document tab's surface, its sections (folds
// that stay the way they were left), the lanes and diffs the Git view
// draws, and the busy state a button wears while its request runs.
//
// One classic script beside index.html (docs/design-language.md, Files):
// pure declarations, nothing runs at load. What runs at load is
// page-boot.js's, under the section's header.

"use strict";

// ---- the document-tab scaffold ------------------------------------------

// Every document tab is the same five slots in the same order, and every tab
// that wrote its own copy of them drifted: a bar with no inset, rows on a
// tighter padding, an error state flush against the edge. Three of
// those shipped and were fixed by inverting a mechanism each time; this is
// the last inversion: the chrome is built HERE, once, and a renderer fills
// slots instead of writing chrome. The conformance suite (test/uniform.mjs)
// holds every kind to the result, so a new tab that skips this reads as a
// failure, not as a style.
//
//   const d = docSurface(i, "nodes");
//   d.bar.innerHTML  = ...   // filters/actions: a .field docbarrow, pre-made
//   d.list.innerHTML = ...   // the bands: .row / .rule / .empty / .loading
//   d.foot.innerHTML = ...   // the quiet footer line (.fnote), or leave empty
//
// Returns null when the pane is gone (a tab closed under a slow fetch), so
// callers bail with `if (!d) return;` instead of drawing into nothing.
// The node switcher every node-scoped tab wears:
// the same label, the same place (the bar's left, verbs at its right) and the
// same list on Toolchains, the Emulator, the Phone and the CI runner. A node
// that cannot be picked for this tab says why in its option, and a quiet one
// says so. `why(n)` is "" for one that can. `stated`: the page says the
// node's state beside the picker (a group header's pill), so the node on
// show is its name alone there, where "draconis (qui..." was cut off beside
// a pill already saying NOT ANSWERING; the others in
// the list still say so, which is where it helps the choice.
// `nodes` null is the page's placeholder (a
// placeholder drawn by the page's own code, so it cannot drift from it):
// the same label and word, the picker's box shimmering.
function nodePick(id, nodes, cur, why = () => "", {stated = false} = {}){
  if (nodes === null) return `<label class="pick nodepick"><span class="pickw">Node</span> ${skv(7, "ctl")}</label>`;
  if (!nodes.length) return "";
  return `<label class="pick nodepick"><span class="pickw">Node</span> <select id="${esc(id)}" aria-label="node">${nodes.map(n => {
    const w = why(n);
    return `<option value="${esc(n.id)}"${n.id === cur ? " selected" : ""}${w ? " disabled" : ""}>${esc(n.name)}${
      w ? `: ${esc(w)}` : n.live === false && !(stated && n.id === cur) ? " (quiet)" : ""}</option>`;
  }).join("")}</select></label>`;
}

// What a list, a grid or a page is waiting with:
// shapes laid out the way its content will land, shimmering, where
// a "loading…" line said the same in words. Still a .loading, so everything
// that knew a placeholder knows this one: a draw fades in what replaces it,
// the poll's failure notice writes its words over it, a suite waits for it
// to go. The words stay for a screen reader. A shape: rows (a list), cards
// (a grid of cards), tiles (a row of numbers), home (Home's tiles and two
// cards), lines (a page of text, a log, a diff), chips (a row of buttons),
// word (inline, a view's head while its count is coming).
const SKW = [62, 48, 71, 55, 66, 43, 58, 51];
function skel(shape = "rows", n = 0, said = "loading…"){
  if (SKTPLS[shape]) return SKTPLS[shape]();
  const b = (cls, w) => `<i class="sk-b${cls ? " " + cls : ""}"${w ? ` data-style="width:${w}%"` : ""}></i>`;
  const times = (k, f) => Array.from({length: k}, (_, j) => f(j)).join("");
  const rows = k => times(k, j => `<div class="sk-row">${b("", SKW[j % 8])}${b("sub", SKW[(j + 3) % 8] / 2)}</div>`);
  const tiles = k => `<div class="sk-tiles">${times(k, j => `<div class="sk-tile">${b("big", 30 + SKW[j % 8] / 4)}${b("sub", SKW[(j + 2) % 8])}</div>`)}</div>`;
  const card = j => `<div class="sk-card">${b("", 35 + SKW[j % 8] / 3)}${b("sub", 80)}${b("sub", SKW[(j + 1) % 8])}</div>`;
  const inner = {
    rows: () => rows(n || 5),
    cards: () => `<div class="sk-cards">${times(n || 6, card)}</div>`,
    tiles: () => tiles(n || 6),
    home: () => tiles(6) + `<div class="sk-cards halves">${times(2, j => `<div class="sk-card">${b("", 30)}${rows(4 - j)}</div>`)}</div>`,
    lines: () => times(n || 7, j => b("line", j % 4 === 3 ? 30 : 40 + SKW[j % 8] * .7)),
    chips: () => times(n || 6, j => b("chip", 0)),
    word: () => b("", 0),
  }[shape] || (() => rows(n || 5));
  const tag = shape === "word" ? "span" : "div";
  return `<${tag} class="loading skel sk-${esc(shape)}"><span class="sk-said">${esc(said)}</span>${inner()}</${tag}>`;
}

// ...and a page that knows its own shape better than that:
// what never changes on it (its headings, a tile's label,
// a table's head, a form's labels) drawn for real, and only the values on
// their way shimmering. skTpl keeps it a .loading, with the word for a
// screen reader; skv is one value inline, as wide as a typical one in em
// ("ctl" for a field's control, the height of one);
// skRows rows inside a real section or card.
function skv(em = 5, cls = ""){ return `<i class="skv${cls ? " " + esc(cls) : ""}" data-style="width:${Number(em) || 5}em"></i>`; }
// A question asked in a box under a row (consistency pass J3: a bug's
// close or delete, a roadmap item's drop): the question and what follows
// from it, a line for why, Cancel and the verb; Enter is the verb and
// Escape Cancel. Not focused: a phone's keyboard would rise over the row.
// `go(why)` runs on the verb, `cancel()` on Cancel; `place` "after" puts the
// box after `at` rather than in it. `sub` is said after the question as is.
function dropBox(at, {q, sub = "", placeholder = "", max = 1000, verb, tone = "primary", place = "append", go, cancel}){
  const box = document.createElement("div");
  box.className = "dropbox ctlown";
  drawHTML(box, `<div class="q">${esc(q)}${sub ? `<span>${esc(sub)}</span>` : ""}</div>
    <textarea class="proseline" rows="1" maxlength="${Number(max) || 1000}" placeholder="${esc(placeholder)}"></textarea>
    <div class="actbar">
      <button type="button" class="stop">Cancel</button>
      <button type="button" class="${esc(tone)}" data-dropgo>${esc(verb)}</button></div>`);
  if (place === "after") at.after(box); else at.appendChild(box);
  arriveBox(box);
  const ta = box.querySelector("textarea");
  const shut = () => { box.remove(); cancel?.(); };
  const ok = () => { const why = ta.value; box.remove(); go?.(why); };
  box.querySelector(".stop").onclick = shut;
  box.querySelector("[data-dropgo]").onclick = ok;
  ta.onkeydown = e => {
    if (e.key === "Enter" && !e.shiftKey){ e.preventDefault(); ok(); }
    if (e.key === "Escape"){ e.preventDefault(); e.stopPropagation(); shut(); }
  };
  return box;
}

// A running job's Abort, the same on every page that has one (consistency
// pass J11): while its stop is on the way it is dead and wears the ring in
// its word's place, its size kept, saying Stopping to a screen reader
// (a word that changed grew the button). `attrs` is the
// page's own data key, `title` what stopping keeps.
function abortBtn(attrs, aborting, title = ""){
  return `<button type="button" ${attrs}${title ? ` title="${esc(title)}"` : ""}${runAttr(aborting, "Stopping")}>Abort</button>`;
}
// A press the server queued behind what is running, said one way on every
// page (a press that can be queued says so): `what`
// the press set going, `behind` what it waits for.
function queuedSaid(what, behind){
  return `${what}: queued behind ${behind}, and starts once that has ended`;
}
// A button whose work runs, drawn so (a running word
// grew its button): its own word kept, so its size is, dead, the ring in
// the word's place, and `saying` (Installing, Checking for updates) what a
// screen reader hears of it while it runs. drawn applies it (runShow).
// "" where nothing runs, for a button drawn the same way either way.
function runAttr(running, saying){
  return running ? ` disabled data-running="${esc(saying)}"` : "";
}

// A field on its way: its real label over a control's box shimmering, as
// wide as a typical value in em (consistency pass J5: four pages wrote it).
function skField(label, em = 16, cls = ""){
  return `<div class="${cls ? esc(cls) + " " : ""}setrow col ctlrow"><span class="lbl">${esc(label)}</span>${skv(em, "ctl")}</div>`;
}
function skRows(n = 4){
  return Array.from({length: n}, (_, j) => `<div class="sk-row"><i class="sk-b" data-style="width:${SKW[j % 8]}%"></i><i class="sk-b sub" data-style="width:${SKW[(j + 3) % 8] / 2}%"></i></div>`).join("");
}
// Inert unless its caller wired what it drew (`live`): a form drawn before
// its wiring would take typing the real one, landing, throws away.
// Its sections lose their keys: drawn open or shut as the real ones will
// be, but never found by a selector, a wiring or a suite asking for those.
function skTpl(html, {said = "loading…", live = false} = {}){
  return `<div class="loading skel skt"${live ? "" : " inert"}><span class="sk-said">${esc(said)}</span>${
    skOpen(html).replace(/ data-sect="[^"]*"/g, "")}</div>`;
}
// A placeholder's sections open as the page will open them once it is drawn
// (oneOpen): at a desk every section of the page stands open, a fold on
// purpose shut as given; on a phone one does, the one this visit of the page
// last opened, else the first that is not a fold on purpose
// (a phone's placeholder stood every section open, and all but one
// folded away as the page came).
function skOpen(html){
  if (!html.includes("<details")) return html;
  const t = document.createElement("template");
  t.innerHTML = html;
  const top = [...t.content.querySelectorAll("details.sect")]
    .filter(d => !d.parentElement?.closest("details.sect") && !d.closest(".row:not(.ndrow), .modal"));
  if (!top.length) return html;
  if (!isPhone()) top.forEach(d => { if (!d.hasAttribute("data-fold")) d.setAttribute("open", ""); });
  else if (top.length > 1){
    const name = (top[0].dataset.sect || "").split(":")[0];
    const had = name ? sectLastByName.get(name) : undefined;
    const last = had && had[0] === sectVisit ? had[1] : "";
    const keep = top.find(d => last && d.dataset.sect === last) || top.find(d => !d.hasAttribute("data-fold")) || top[0];
    top.forEach(d => d.toggleAttribute("open", d === keep));
  }
  return t.innerHTML;
}

// A bar button's words at both widths (the node
// picker and a page's buttons on one line on a phone). On a phone the short
// form shows; where it is the start of the long one the rest is a span a
// phone hides, so the button's text is still the whole label everywhere.
function barSaid(full, short){
  return full.startsWith(short) ? `${esc(short)}<span class="lng">${esc(full.slice(short.length))}</span>`
    : `<span class="lng">${esc(full)}</span><span class="shrt">${esc(short)}</span>`;
}
// ---- the first paint, shaped like the page the address names ----------------
// What a reload shows until the first snapshot lands
// (a refresh on Projects showed full-width rows, no rail and no bar). The
// rail's groups, inert until drawRail replaces them; the pane's bar as the
// page will wear it (its group's tools, or a project's header and its view
// strip); and the page's own shape in a document's frame. Its own class
// names, not the pane's .stack, so the first real draw builds the pane
// afresh rather than inside it.
function bootPage(hash){
  const parts = routeIn(hash).replace(/^#\/?/, "").split("/").filter(Boolean).map(decodeURIComponent);
  const key = parts[0] || "home", g = RAIL.find(x => x.key === key) || RAIL[0];
  const tool = g.tools.some(([k]) => k === parts[1]) ? parts[1] : g.tools[0][0];
  const seg = (tools, on) => `<span class="subnav pseg hscroll">${tools.filter(([k]) => !PRESSED.has(k)).map(([k, label]) =>
      `<button type="button" disabled class="${k === on ? "on" : ""}">${esc(label)}</button>`).join("")}</span>`;
  const doc = (barHtml, body) => `<div class="doc on flush"><div class="doctab">${barHtml
    ? `<div class="field docbarrow">${barHtml}</div>` : ""}<div class="doclist">${body}</div></div></div>`;
  let bar, body;
  if (key === "projects" && parts[1] && !g.tools.some(([k]) => k === parts[1])){
    // A project's notebook: its header, its view strip under it the
    // pane's width with the view's group open, then rows.
    // The notebook's own groups and views (NB_VIEWS), each view by its
    // name in an address, so this strip is the one the notebook then draws.
    const GROUPS = NB_GROUPS.map(([k, w]) => [k, w, NB_VIEWS.filter(x => x.group === k).map(x => [x.addr || x.key, x.label])]);
    const view = parts[2] || "overview", grp = GROUPS.find(x => x[2].some(([v]) => v === view)) || GROUPS[0];
    const btn = (on, w) => `<button type="button" disabled class="${on ? "on" : ""}">${w}</button>`;
    bar = `<span class="phead"><span class="pname">${skv(6)}</span><span class="pfacts">${skv(14)}</span><span class="sp"></span>
      <button type="button" disabled>Start agent</button><button type="button" disabled>Shell</button></span>`;
    body = `<div class="doc on nbhost"><div class="nb"><div class="nbtabs"><div class="nbgroups hscroll">${GROUPS.map(([k, w]) => btn(k === grp[0], w)).join("")}</div>
      <div class="nbsub hscroll">${grp[2].map(([v, w]) => btn(v === view, w)).join("")}</div></div>
      ${bootView(view) || `<div class="nbview"><div class="field">${skRows(5)}</div></div>`}</div></div>`;
    return {rail: key, bar: `<div class="bar proj">${bar}</div>`, body: `<div class="skstack">${body}</div>`};
  }
  // A group's header over its sub-nav: the picker's
  // placeholder, the state pill's shimmer, the Machines group's two
  // actions dead.
  bar = ["machines", "build", "containers"].includes(key)
    ? `<div class="bar page grouped${key === "machines" ? " machines" : ""}"><span class="phead mchead">${nodePick("", null)}${skv(5, "ndstatesk")}<span class="sp"></span></span>
        <span class="subrow">${seg(g.tools, tool)}<span class="sp"></span>${key === "machines" ? `<span class="actbar"><button type="button" disabled>${"New VM"}</button><button type="button" class="primary" disabled>${barSaid("Enroll node", "Enroll")}</button></span>` : ""}</span></div>`
    : `<div class="bar page">${seg(g.tools, tool)}</div>`;
  if (key === "home")
    // Home's own order: the tiles, Attention and Last jobs, the projects at
    // a glance, each heading drawn and what fills it shimmering.
    body = doc("", `<div class="field"><div class="tiles hometiles">${["nodes online", "containers running", "jobs running",
        "sessions open", "updates due", "CI red"].map(l => `<span class="tile"><span class="tv">${skv(1.4)}</span><span class="tl">${l}</span></span>`).join("")}</div></div>
      <div class="field"><div class="homegrid"><section class="hcard"><h3>Attention</h3>${skRows(2)}</section>
        <section class="hcard"><h3>Last jobs</h3>${skRows(3)}</section></div></div>
      <div class="field"><section class="hsect"><h3>Favorites</h3>${skRows(2)}</section></div>`);
  else if (key === "projects" && tool === "projects")
    body = doc(`<input type="search" disabled placeholder="name, branch or node"><span class="sp"></span>
      <span class="actbar"><button type="button" class="ic" disabled>${BIN}</button><button type="button" class="primary" disabled>New space</button></span>`,
      `<div class="field pgridband"><div class="pgrid">${Array.from({length: 6}, (_, j) => skProjectCard(j)).join("")}</div></div>`);
  // The rest: their rows in a floating card, as the pages draw them at a
  // desk.
  else body = doc("", `<div class="field"><div class="sk-card skrows">${skRows(6)}</div></div>`);
  return {rail: key, bar, body: `<div class="skstack">${body}</div>`, tool};
}

// A project's card on its way, in the card's own parts: its
// name, its id and node, a repository or two by name and branch, and its
// actions at the foot as the card draws them, dead until it lands.
function skProjectCard(j = 0){
  const repo = k => `<div class="pcrepo">${skv(4 + (SKW[(j + k) % 8] % 5))}${skv(5)}</div>`;
  const mark = icon => `<button type="button" class="eye bare pcmark" disabled>${icon}</button>`;
  return `<div class="pcard skpcard"><div class="pcname">${skv(5 + (SKW[j % 8] % 6), "name")}<span class="sp"></span>${mark(STAR)}${mark(ARCHIVE)}</div>
    <div class="pcmeta"><span class="pcfacts">${skv(7)}</span></div>
    <div class="pcrepos">${repo(0)}${j % 3 === 1 ? repo(3) : ""}</div>
    <div class="pcacts actbar"><button type="button" disabled>Start agent</button><button type="button" disabled>Add repository</button><button type="button" disabled>Edit</button></div></div>`;
}

// A notebook view at the first paint is its own markup from the notebook's
// template, its shapes in it as a press shows them (a reload on the
// Roadmap drew five plain rows, then the view's head and list): inert, and
// without its ids, which belong to the notebook the page builds. A view
// whose markup is drawn by its loader (Settings) keeps the rows.
function bootView(view){
  const v = view === "overview" ? "briefing" : view;
  const src = [...document.querySelectorAll("template")]
    .map(t => t.content.querySelector(`.nbview[data-view="${CSS.escape(v)}"]`)).find(Boolean);
  if (!src?.querySelector(".skel")) return "";
  const c = src.cloneNode(true);
  c.removeAttribute("hidden");
  [c, ...c.querySelectorAll("[id]")].forEach(e => e.removeAttribute("id"));
  c.querySelectorAll("label[for]").forEach(e => e.removeAttribute("for"));
  c.querySelectorAll("input, select, textarea, button").forEach(e => { e.disabled = true; });
  return skOpen(c.outerHTML);
}

// ...and in it, the page's own placeholder where it has one: the page drawn
// by its own render into the boot's frame (doc "boot") with nothing loaded
// yet, which is what a page opened by a press shows while it waits
// (a reload showed a placeholder of its own and then the
// page's). A page that cannot draw before the first status read keeps the
// boot's shape.
function bootOwn(root, tool){
  const doc = root?.querySelector(".skstack > .doc");
  const spec = TABKINDS[tool];
  if (!doc || !spec?.render || tool === "projects") return;
  const was = doc.innerHTML;
  doc.id = "docboot";
  doc.innerHTML = "";
  try{ spec.render("boot"); }catch(e){ drawHTML(doc, was); }
  if (!doc.querySelector(".doclist > *")) drawHTML(doc, was);
  doc.removeAttribute("id");
}

// A page of settings on its way, in splitSects' shape: its sections' names
// and what each holds in the list, the first one picked, its heading and
// body beside the list (the template a page of settings waits as).
function skSplit(items, title, body, head = ""){
  return `<div class="ssplit"><div class="rlist snav">${items.map(([t, says], j) =>
      `<button type="button" class="rrow${j ? "" : " on"}" disabled><span class="name">${esc(t)}</span><span class="rtags"><span class="dim">${esc(says)}</span></span></button>`).join("")}</div>
    ${head}<details class="sect scur" open><summary><span class="t">${esc(title)}</span></summary><div class="body"><div class="field">${body}</div></div></details></div>`;
}

// The rail's groups at the first paint: every group, inert, the one the
// address names lit; drawRail puts what this account may open in their place.
function bootRail(on){
  const item = g => `<button type="button" class="ritem${g.key === on ? " on" : ""}" disabled>${
    RAIL_ICONS[g.icon] || TOOL_ICONS[g.icon] || ""}<span class="rlbl">${esc(g.label)}</span></button>`;
  return {rail: RAIL.map(item).join(""), bar: RAIL.filter(g => RAIL_PHONE.includes(g.key)).map(item).join("")
    + `<button type="button" class="ritem" disabled>${RAIL_ICONS.more || ""}<span class="rlbl">More</span></button>`};
}

// The notebook views whose sections are always the same, by name, so the
// markup's placeholders (data-skel) and the views' own waits draw them.
const SKTPLS = {
  // As the view lands, from the view's own table (nb-git.js GIT_SECTS): its
  // sections' chips, then each steady section; CI and a README come with
  // what the repository holds, so the placeholder promises neither.
  // ...its jump bar from two sections, as sectJump draws it.
  git: () => skTpl((GIT_SECTS.length >= 2 ? `<nav class="sectjump">${GIT_SECTS.map(([, t]) => `<a href="#">${esc(t)}</a>`).join("")}</nav>` : "")
    + GIT_SECTS.map(([k, t]) => docSection("git", k, t, "", k === "branches" ? skTable(gitBranchCols("main"), 3, "gbranches", "row gbranch") : skRows(2))).join("")),
  design: () => skTpl(`<nav class="sectjump"><a href="#">Pages</a><a href="#">Themes</a></nav>`
    + docSection("design", "pages", "Pages", "", skRows(2))
    + docSection("design", "themes", "Themes", "", skRows(2))),
  // Its sections by the view's own titles (nb-artifacts.js ART_TITLES), in
  // the order it lands them: Build first, in its own box above the Version
  // (nbArtBuildSection), under the jump bar the view draws over the three
  // (sectJump), so the page does not move down as it lands; then Files
  // under the Version.
  artbuild: () => skTpl(`<nav class="sectjump">${["build", "version", "files"].map(k => `<a href="#">${esc(artTitle(k))}</a>`).join("")}</nav>`
    + docSection("artifacts", "build", artTitle("build"), "", skRows(1))),
  artifacts: () => skTpl(docSection("artifacts", "files", artTitle("files"), "", skRows(2))),
  // The Overview's box of sections (nb-rules.js BRIEF_SECTS) as drawRules
  // lands it, the Brief left out, with the jump bar over them and the
  // Memories under them that the markup holds.
  briefing: () => {
    const sects = BRIEF_SECTS.filter(([k]) => k !== "brief");
    return skTpl(`<nav class="sectjump">${[...sects.map(([, t]) => t), "Memories"].map(t => `<a href="#">${esc(t)}</a>`).join("")}</nav>`
      + sects.map(([k, t, open], j) => docSection("briefing", k, t, "", skRows(j ? 1 : 3), {open})).join(""));
  },
  // The Signing view as a project with its one key lands (nb-signing.js
  // drawSigning) on a node that signs: the jump bar over its sections, the
  // backup password, the default key, the apps and the releases. A node
  // without the tools heads the view with why, which is not the common case.
  signing: () => {
    const sects = [["lock", "Backup password", 1], ["key:default", "Default key", 2], ["apps", "Apps", 1], ["releases", "Releases", 2]];
    return skTpl(`<nav class="sectjump">${sects.map(([, t]) => `<a href="#">${esc(t)}</a>`).join("")}</nav>`
      + sects.map(([k, t, n]) => docSection("signing", k, t, "", skRows(n))).join(""));
  },
  // ...and the Version box above it, which the view fills on its own.
  version: () => skTpl(docSection("artifacts", "version", artTitle("version"), "", skRows(1))),
};
// A select's options from strings or [value, label] pairs, the current one
// selected, every value and label escaped (consistency pass J20: fifty-odd
// written by hand, a few of them unescaped).
function optionList(items, cur){
  return (items || []).map(it => {
    const [v, l] = Array.isArray(it) ? it : [it, it];
    return `<option value="${esc(v)}"${String(v) === String(cur ?? "") ? " selected" : ""}>${esc(l)}</option>`;
  }).join("");
}
// A word the page needs, asked in a box in the row where
// window.prompt was: its label, the field, Cancel and OK, under the control
// that asked; Enter is OK and Escape is Cancel. Resolves with what was typed,
// trimmed, or null. One at a time: a second ask takes the first one's place,
// and the same ask again where it is open closes it as a Cancel would, so
// the control that opened the box shuts it.
// `options` are offered as the box is typed in; `allowEmpty` lets OK answer
// "" (a group taken away), where otherwise an empty box is a Cancel. `also`,
// {key, label}, is a destructive verb last on the box's bar, answering
// {also: key} (a group's Delete group).
function askInline(after, {label, value = "", ok = "OK", options = [], allowEmpty = false, also = null} = {}){
  return new Promise(resolve => {
    const was = after.nextElementSibling;
    document.querySelectorAll(".askline").forEach(x => x.__done?.(null));
    if (was?.classList.contains("askline") && was.__label === label){ resolve(null); return; }
    const box = document.createElement("div");
    box.className = "field askline";
    // The page's own while it is open: a redraw of the surface it is in
    // (a card's back, a group's head) leaves it where it is, with what is
    // typed in it.
    box.setAttribute("data-own", "");
    // With options, the field is one to type in and a pulldown of every
    // option at once (a datalist hinted only once
    // something was typed): its chevron opens the whole list, typing narrows
    // it, and a press on one fills the field.
    const list = options.length ? `askopts${++seq}` : "";
    const field = `<input type="text" autocomplete="off" spellcheck="false" aria-label="${esc(label)}"${
        list ? ` role="combobox" aria-expanded="false" aria-controls="${list}" aria-autocomplete="list"` : ""}>`;
    drawHTML(box, `<label class="lbl">${esc(label)}</label><div class="askrow actbar ctlrow">${list
        ? `<span class="combo">${field}<button type="button" class="combobtn" tabindex="-1" aria-label="every ${esc(label.toLowerCase())}">${CHEVRON_DOWN}</button>
            <span class="combolist" id="${list}" role="listbox" hidden></span></span>` : field}
      <button type="button" data-askno>Cancel</button><button type="button" class="primary" data-askok>${esc(ok)}</button>${
        also ? `<button type="button" class="danger" data-askalso>${esc(also.label)}</button>` : ""}</div>`);
    // On a card's back the box takes the repositories' place, and the back
    // keeps its height while it is open: the card never changes size.
    const back = after.closest(".pcback");
    if (back) back.style.minHeight = back.getBoundingClientRect().height + "px";
    faceFade(after, () => after.insertAdjacentElement("afterend", box));
    const inp = box.querySelector("input");
    inp.value = value;
    inp.focus(); inp.select();
    const done = v => { faceFade(box, () => { box.remove(); if (back && !back.querySelector(".askline, .pcpop")) back.style.minHeight = ""; }); resolve(v); };
    box.__done = done;
    box.__label = label;
    const answer = () => done(inp.value.trim() || (allowEmpty ? "" : null));
    box.querySelector("[data-askok]").onclick = answer;
    box.querySelector("[data-askno]").onclick = () => done(null);
    const al = box.querySelector("[data-askalso]");
    if (al) al.onclick = () => done({also: also.key});
    const combo = list ? comboWire(box, inp, options) : null;
    inp.onkeydown = e => {
      if (combo?.key(e)) return;
      if (e.key === "Enter"){ e.preventDefault(); answer(); }
      else if (e.key === "Escape"){ e.preventDefault(); e.stopPropagation(); done(null); }
    };
  });
}

// A field that is also a pulldown of `options` (askInline's): the list under
// it, every option when it is opened by its chevron or an arrow key, the ones
// containing what is typed as it is typed; Up and Down move the pick, Enter
// takes it, Escape shuts the list before anything else. Returns {key(e)},
// true when the list took the key.
function comboWire(box, inp, options){
  const ul = box.querySelector(".combolist"), btn = box.querySelector(".combobtn");
  let shown = [], at = -1;
  const draw = all => {
    const q = inp.value.trim().toLowerCase();
    shown = all || !q ? options.slice() : options.filter(o => o.toLowerCase().includes(q));
    at = Math.min(at, shown.length - 1);
    drawHTML(ul, shown.length ? shown.map((o, i) => `<button type="button" role="option" data-combo="${i}" aria-selected="${i === at}"${
        i === at ? ' class="on"' : ""} tabindex="-1">${esc(o)}</button>`).join("")
      : `<span class="combonone">none yet: what is typed is a new one</span>`);
    // Taken on the click, a press and its release on the one option, so a
    // press that holds to scroll the list takes nothing; the press
    // itself only keeps the field's focus, whose blur would shut the list.
    ul.querySelectorAll("[data-combo]").forEach(b => {
      b.onpointerdown = e => e.preventDefault();
      b.onclick = e => { e.preventDefault(); pick(shown[+b.dataset.combo]); };
    });
  };
  const open = all => { draw(all); ul.hidden = false; inp.setAttribute("aria-expanded", "true"); };
  const shut = () => { ul.hidden = true; at = -1; inp.setAttribute("aria-expanded", "false"); };
  const pick = o => { inp.value = o; shut(); inp.focus(); };
  btn.onpointerdown = e => { e.preventDefault(); if (ul.hidden){ at = -1; open(true); inp.focus(); } else shut(); };
  // ...and a key's press on it (Enter or Space), which brings a click with
  // no pointer before it: the pointer's own click is already answered.
  btn.onclick = e => { e.preventDefault(); if (e.detail) return; if (ul.hidden){ at = -1; open(true); inp.focus(); } else shut(); };
  inp.addEventListener("input", () => { at = -1; open(false); });
  inp.addEventListener("blur", () => setTimeout(shut, 0));
  return {key(e){
    if (e.key === "ArrowDown" || e.key === "ArrowUp"){
      e.preventDefault();
      if (ul.hidden){ at = -1; open(!inp.value.trim()); }
      const n = shown.length;
      if (n) at = e.key === "ArrowDown" ? (at + 1) % n : (at - 1 + n) % n;
      draw(!inp.value.trim());
      ul.querySelector(".on")?.scrollIntoView({block: "nearest"});
      return true;
    }
    if (e.key === "Enter" && !ul.hidden && at >= 0){ e.preventDefault(); pick(shown[at]); return true; }
    if (e.key === "Escape" && !ul.hidden){ e.preventDefault(); e.stopPropagation(); shut(); return true; }
    return false;
  }};
}

// A pointer to another page is a link to it: the address that
// page answers at, so a press goes there as the rail does and Back returns.
const PAGE_AT = {nodes: "#/machines/nodes", installed: "#/machines/installed", storage: "#/machines/storage", docker: "#/containers", jobs: "#/jobs",
  library: "#/build/library", users: "#/people/users", roles: "#/people/roles", machine: "#/controller/machine",
  clusters: "#/machines/clusters"};
// A page this account may not open is its words and no link: the
// address of one a grant forbids landed on the group's first page instead.
function pageLink(page, words, hash = PAGE_AT[page]){
  if (!railAllows(page)) return esc(words);
  return `<a href="${esc(hash || "#")}" class="pagelink">${esc(words)}</a>`;
}
// A table on its way: its real head over rows whose cells shimmer, each as
// wide as its column's values tend to be.
function skTable(cols, n = 5, cls = "", rowCls = "row stack2"){
  return tblWrap(cols, Array.from({length: n}, (_, j) => `<div class="${rowCls}">${tblLine(cols, cols.map((c, i) =>
    c.act ? "" : skv(i === 0 ? 7 + (SKW[j % 8] % 5) : 2.5 + ((i + j) % 3))))}</div>`).join(""), cls);
}

function docSurface(i, kind){
  const el = $("doc" + i);
  if (!el) return null;
  if (!el.classList.contains("flush")) el.classList.add("flush");
  // Kept when this page is already drawn here: built afresh on
  // every draw, a page drawn by the poll was born again each time, its list
  // fading in as if it had just arrived, its scroll and whatever was under
  // the pointer lost, though nothing in it had changed. A draw that changes
  // nothing now writes nothing: the list goes through patch,
  // and the bar and the foot are patched only where what they say moved, a
  // picker or a search in the bar kept as it is.
  let box = el.firstElementChild;
  if (!box || el.children.length !== 1 || !box.classList.contains("doctab") || !box.classList.contains(`${kind}tab`)
      || !box.querySelector(":scope > .doclist")){
    drawHTML(el, `<div class="doctab ${esc(kind)}tab">
      <div class="field docbarrow" hidden></div>
      <div class="doclist"></div>
      <div class="fnote" hidden></div>
    </div>`);
    box = el.firstElementChild;
  }
  const bar = box.querySelector(":scope > .docbarrow");
  const foot = box.querySelector(":scope > .fnote");
  const slot = (node, html) => {
    const s = String(html);
    patch(node, s, true);
    const off = !s.trim();
    if (node.hidden !== off) node.hidden = off;
  };
  // Plain nodes and two explicit setters: a slot written to becomes visible,
  // one left alone costs no empty band. (A Proxy did this implicitly at first
  // and threw Illegal invocation the moment a DOM accessor ran through it;
  // the error boundary caught it, which is the one nice thing it did.)
  return { root: box, el, bar, foot, list: box.querySelector(":scope > .doclist"),
           setBar(html){ slot(bar, html); },
           setFoot(html){ slot(foot, html); } };
}

// ---- a form ----------------------------------------------------------
// Every form is this one part, as every page is docSurface
// (a form's buttons touched the field above them and hung past its edge,
// pointed out many times; a site builder's form block owns its own insides).
// The part owns what a page used to arrange for itself: the fields on the
// grid (.fgrid), their room, and the foot, 16px under the last field with the
// primary at the right. The box is what is capped, never a field alone, so the
// foot ends where the fields end at every width. A page hands it fields
// (formField) and verbs, never layout; lint refuses a field written outside it.
//   fields: formField strings, or groups: [{head, says, fields, attrs, grid}], each a
//     .fgroup, grid "three" for three short numbers across
//   foot: the verbs' button strings, the primary last, a .lead one at the left;
//   state: a .state on a line of its own over them
function formBox({fields = [], groups = null, foot = [], state = "", cls = "", attrs = ""} = {}){
  const grid = (fs, cls = "") => `<div class="fgrid${cls ? ` ${cls}` : ""}">${fs.filter(Boolean).join("")}</div>`;
  const body = groups
    ? groups.map(g => `<div class="fgroup"${g.attrs ? ` ${g.attrs}` : ""}>${g.head ? `<div class="fgrouphead">${esc(g.head)}${
        g.says ? `<span class="sub dim">${esc(g.says)}</span>` : ""}</div>` : ""}${grid(g.fields || [], g.grid)}</div>`).join("")
    : grid(fields);
  const verbs = foot.filter(Boolean);
  return `<div class="fbox${cls ? ` ${cls}` : ""}"${attrs ? ` ${attrs}` : ""}>${body}${verbs.length || state
    ? `<div class="actbar ffoot">${state}${verbs.join("")}</div>` : ""}</div>`;
}
// One field of a form: its label over it, a hint under it. `wide` spans the
// grid's two columns (a path, an address, a file's text), `short` is a
// number's width; `control` is the input, select or textarea itself, and
// `tail` what the label carries after its words (a pill saying where the
// value comes from).
function formField(id, label, control, {help = "", hint = "", wide = false, short = false, hidden = false, attrs = "", tail = "", cls = ""} = {}){
  const head = tail ? lbl(id, label, help).replace(/<\/label>$/, ` ${tail}</label>`) : lbl(id, label, help);
  return `<div class="fcell${wide ? " fwide" : ""}${short ? " fshort" : ""}${cls ? ` ${cls}` : ""}"${hidden ? " hidden" : ""}${attrs ? ` ${attrs}` : ""}>${
    head}${control}${hint ? `<div class="hint">${hint}</div>` : ""}</div>`;
}

// A section of a document tab (see "sections and action bars" in the
// stylesheet): a fold with a title, a one-line status on the right, and the
// controls inside. `kind:id` is what its open state is kept under, for this
// page's life: a fold you opened stays open across every repaint, and a
// reload starts every fold from its default: open on a desktop and shut on
// a phone, so a phone shows headings. Not stored, on purpose: a page that
// came back with last week's folds read as a page somebody else had left.
// Pass `open` to override, which is for a section that IS
// the answer rather than a place to go and look for it.
const sectOpen = {};
// The attributes of a fold that remembers: its key, and `open` when it was
// left open (or, never touched, when `dflt` says so). docSection writes its
// own; this is for a fold that is not a section, a row's Details or a diff's
// file, which a redraw otherwise puts back the way it was first drawn.
function sectAttr(key, dflt = false){
  return ` data-sect="${esc(key)}"${(key in sectOpen ? sectOpen[key] : dflt) ? " open" : ""}`;
}
// Lanes for a commit graph: commits newest first, each with its parents.
// The classic walk: a commit takes the lane that was waiting for it (the
// leftmost, when several were), its first parent inherits that lane, and
// every other parent gets a lane of its own, and the edges between rows,
// for the page to draw as curves. Writes `lane` onto each commit.
function gitLanes(commits){
  const rowOf = new Map(commits.map((c, i) => [c.sha, i]));
  const lanes = [];                       // the sha each lane is waiting for
  const edges = [];
  const slot = () => { const i = lanes.indexOf(null); return i < 0 ? lanes.push(null) - 1 : i; };
  commits.forEach((c, row) => {
    const mine = lanes.map((x, i) => x === c.sha ? i : -1).filter(i => i >= 0);
    const lane = mine.length ? mine[0] : slot();
    for (const i of mine.slice(1)) lanes[i] = null;
    c.lane = lane;
    const [first, ...rest] = c.parents;
    lanes[lane] = first || null;
    for (const p of rest) if (!lanes.includes(p)) lanes[slot()] = p;
  });
  commits.forEach((c, row) => {
    for (const p of c.parents){
      const pr = rowOf.get(p);
      if (pr === undefined) continue;     // beyond what was fetched
      edges.push({from: {lane: c.lane, row}, to: {lane: commits[pr].lane, row: pr}});
    }
  });
  return {edges};
}

// A unified diff as markup: one fold per file, each line marked as added,
// removed, context or hunk head. Text only ever lands through esc().
function renderDiff(text){
  if (!text || !text.trim()) return `<div class="empty">no textual change</div>`;
  const files = [];
  let cur = null;
  for (const line of text.split("\n")){
    if (line.startsWith("diff --git ")){
      const m = /^diff --git a\/(.*) b\/(.*)$/.exec(line);
      cur = {name: m ? m[2] : line.slice(11), lines: []};
      files.push(cur);
      continue;
    }
    if (!cur){ cur = {name: "", lines: []}; files.push(cur); }
    cur.lines.push(line);
  }
  const pre = f => `<pre class="diff">${f.lines.filter(l => !/^(index |--- |\+\+\+ |new file mode|deleted file mode|similarity index|rename from|rename to|old mode|new mode)/.test(l) || !f.name)
      .map(l => `<span class="${l.startsWith("@@") ? "d-hunk" : l.startsWith("+") ? "d-add" : l.startsWith("-") ? "d-del" : "d-ctx"}">${esc(l)}\n</span>`).join("")}</pre>`;
  // A diff with no file header (a single file's, asked by path) is the
  // text alone; a fold with nothing to name would wear the browser's word.
  return files.map(f => f.name
    ? `<details class="dfile chev"${sectAttr("diff:" + f.name, true)}><summary><code>${esc(f.name)}</code></summary>${pre(f)}</details>`
    : pre(f)).join("");
}

// A section that has just become news (CI on main gone red) opens by itself
// once, at the moment it turns, and is the one open in its view; closed
// after that, it stays closed for as long as it stays the same news.
const sectLoud = {};
// `fold`: a fold on purpose, shut until opened at every width (the Projects
// page's Archived, a read made only when it is opened); every other section
// at a page's level stands open at a desk and does not fold there.
function docSection(kind, id, title, status, body, {cls = "", open, loud = false, prime = false, fold = false, item = false, sectCls = ""} = {}){
  const key = `${kind}:${id}`;
  const turned = loud && !sectLoud[key];
  sectLoud[key] = loud;
  // Open unless somebody shut it, at every width (too
  // much was hidden in folds).
  const isOpen = turned || (key in sectOpen ? sectOpen[key] : (open !== undefined ? open : true));
  // `prime`: the section a view is opened for (Artifacts' Files), open by
  // default beside the first on a desktop. `data-set`: its caller said open
  // or shut, which a default never overrules.
  // `cls` is the status's tone; `sectCls` the section's own (svcro: read
  // without the grant that changes it).
  return `<details class="sect${sectCls ? " " + sectCls : ""}" data-sect="${esc(key)}"${isOpen ? " open" : ""}${turned ? " data-lead" : ""}${prime ? " data-prime" : ""}${open !== undefined ? " data-set" : ""}${fold ? " data-fold" : ""}${item ? " data-item" : ""}>
    <summary><span class="t">${esc(title)}</span>${
      status ? `<span class="sst${cls ? " " + cls : ""}">${esc(status)}</span>` : ""}</summary>
    <div class="body">${body}</div>
  </details>`;
}
// ---- a page of settings: its sections a list beside the one picked ----
// A page that is a run of settings sections (a
// project's Settings, Controller settings, Profile) reads as a list of them,
// each with what is in it, beside the one picked, the Roles page's shape;
// on a phone the list, then the section sliding in over it, its head the
// way back (a chevron before its name: a Back button
// of its own was a row spent over a head that never folds), and the list
// sliding back. `root` holds the sections (details.sect) as
// children; `key` keeps which is picked; `says` is each section's line
// under its name, by its data-sect id; `marks(id)` says whether one holds
// something unsaved. Drawn again on every call, so a page that repaints
// calls it after each paint. splitOff puts the sections back one under
// another (the project's settings dialog).
const SPLIT = {};
function splitSects(root, key, {says = {}, sel = ":scope > details.sect", marks = null, back = "Back"} = {}){
  if (!root) return;
  const st = SPLIT[key] || (SPLIT[key] = {pick: "", open: false});
  root._split = {key, says, sel, marks};
  root.classList.add("ssplit");
  let nav = root.querySelector(":scope > .snav");
  if (!nav){
    nav = document.createElement("div");
    nav.className = "rlist snav";
    nav.setAttribute("data-own", "");
    nav.setAttribute("role", "tablist");
    root.insertBefore(nav, root.firstChild);
    // A press on the open section's head, on a phone, goes back to the list.
    root.addEventListener("click", e => {
      const s = e.target.closest("summary"), d = s?.parentElement;
      if (!d || d.parentElement !== root || !d.classList.contains("scur") || !root.classList.contains("sopen")
          || !isPhone()) return;
      e.preventDefault();
      SPLIT[root._split.key].open = false; splitMove(root, "back"); splitDraw(root);
    });
    root.addEventListener("input", () => splitMarks(root));
    root.addEventListener("change", () => splitMarks(root));
  }
  root._split.back = back;
  // A section shows or hides itself as what it holds arrives (People after
  // its read): the list follows.
  root._splitObs?.disconnect();
  root._splitObs = new MutationObserver(() => splitDraw(root));
  root.querySelectorAll(sel).forEach(d => root._splitObs.observe(d, {attributes: true, attributeFilter: ["hidden"], subtree: true}));
  splitDraw(root);
}

const splitId = d => (d.dataset.sect || "").replace(/^[^:]*:/, "");

function splitDraw(root){
  const o = root._split;
  if (!o || !root.classList.contains("ssplit")) return;
  const st = SPLIT[o.key];
  // ...and not one with nothing in it to show: a settings group none of
  // whose fields is on show is drawn as nothing (.rngroup's own rule), and
  // listed it opened on an empty pane.
  const empty = d => d.matches(".rngroup") && !d.querySelector(RN_SHOWN);
  const all = [...root.querySelectorAll(o.sel)].filter(d => !d.classList.contains("fghost")), shown = all.filter(d => !d.hidden && !empty(d));
  // The one picked, or the first shown while it is hidden (its list being
  // read again), without forgetting it: it comes back when it shows.
  let pick = st.pick;
  if (!shown.some(d => splitId(d) === pick)) pick = shown[0] ? splitId(shown[0]) : "";
  const nav = root.querySelector(":scope > .snav");
  const html = shown.map(d => { const k = splitId(d), on = k === pick;
    const say = o.says[k] ?? d.querySelector(":scope > summary .sst")?.textContent ?? "";
    return `<button type="button" class="rrow${on ? " on" : ""}" role="tab" aria-selected="${on}" data-spick="${esc(k)}">
      <span class="name">${esc(d.querySelector(":scope > summary .t")?.textContent || k)}</span>
      <span class="rtags">${say ? `<span class="dim">${esc(say)}</span>` : ""}<span class="sunsaved" hidden>unsaved</span></span></button>`; }).join("");
  if (nav.dataset.drawn !== html){
    drawHTML(nav, html); nav.dataset.drawn = html;
    nav.querySelectorAll("[data-spick]").forEach(b => b.onclick = () => {
      // The section on show pressed again at a desk is no change: nothing
      // drawn again, no fade. On a phone the list stands in its place,
      // so a press there still opens it.
      // It is still the one open, which a narrower window shows in place of
      // the list.
      if (b.classList.contains("on") && !isPhone()){ st.open = true; return; }
      st.pick = b.dataset.spick; st.open = true;
      // At a desk the section fades through, as a rail page does; on a
      // phone it slides in over the list.
      splitAway(() => [...root.querySelectorAll(o.sel)].filter(d => d.classList.contains("scur")),
                () => { splitMove(root, "in"); splitDraw(root); });
      if (isPhone()) root.scrollIntoView?.({block: "start"});
    });
  }
  all.forEach(d => { const on = splitId(d) === pick;
    const s = d.querySelector(":scope > summary");
    // Code's own (data-own), so a patch of the page steps over it rather
    // than matching it to the title span the markup starts the head with.
    if (s && !s.querySelector(":scope > .shback"))
      s.insertAdjacentHTML("afterbegin", `<span class="shback" role="img" aria-label="Back to ${esc(o.back)}" data-own>\u2039</span>`);
    if (d.classList.contains("scur") !== on) d.classList.toggle("scur", on);
    if (on && !d.open) d.open = true; });
  root.classList.toggle("sopen", st.open);
  splitMarks(root);
}

// A pick on a list beside its detail: a fade through at a desk (fadeThrough),
// and on a phone the redraw alone, which plays its slide (splitMove).
function splitAway(parts, swap){
  return isPhone() ? swap() : fadeThrough(parts, swap);
}

// The phone's slide: in from the right to a section, back from the left to
// the list, restarted on each press.
function splitMove(root, how){
  delete root.dataset.move;
  void root.offsetWidth;
  root.dataset.move = how;
  // Taken off once it has run: a page that repaints (Controller settings on
  // the poll) would play it again on every paint.
  clearTimeout(root._splitT);
  root._splitT = setTimeout(() => { delete root.dataset.move; }, 320);
}

function splitMarks(root){
  const o = root._split;
  if (!o?.marks) return;
  root.querySelectorAll(":scope > .snav [data-spick]").forEach(b => {
    let dirty = false;
    try { dirty = !!o.marks(b.dataset.spick); } catch { /* a form not drawn yet */ }
    const m = b.querySelector(".sunsaved");
    if (m && m.hidden === dirty) m.hidden = !dirty;
  });
}

function splitOff(root){
  if (!root?.classList.contains("ssplit")) return;
  root.classList.remove("ssplit", "sopen");
  root.querySelectorAll(":scope > details.sect").forEach(d => d.classList.remove("scur"));
}

function wireSections(root){
  root.querySelectorAll("details.sect").forEach(d => {
    // Its state is recorded by the page's one toggle listener, beside
    // sectAttr, and only for a fold that has a key: one without keeps its
    // own (the Git view's file and branch folds do, by path and by name).
    // Driven, not the browser's instant snap: the same helper the memories,
    // the bug reports, the version tab's fold and the Docker manager's wiring
    // fold already use. A <details> opens at full height by construction, so
    // a fold on this page only moves if something moves it, and sections
    // shipped without it: the one kind of fold that jumped.
    //
    // `:scope > summary` because a section can contain folds of its own, and
    // the section must not answer for theirs.
    const sum = d.querySelector(":scope > summary");
    if (sum) sum.onclick = e => { e.preventDefault(); if (sectFixed(d)) return; const will = !foldOpen(d); if (will) soleOpen(d); else soleShut(d); slideDetails(d, will); };
  });
  const view = root.closest?.(".nbview, .doctab") || root.querySelector?.(".doctab");
  if (view){
    oneOpen(view);
    root.querySelectorAll("details.sect").forEach(oneOpen);
    sectJump(view);
  }
}
// A jump bar over a surface of more than one part (the operator, 8 and 23
// Oct): its sections' names in a line at the top, each scrolling to its own
// and opening it if somebody shut it.
function sectJump(g){
  // A surface's own sections, which each have a title of their own: a fold
  // repeated once per row of a list (the Docker tab's Ports and mounts, one
  // per container) is the row's, and seventeen of them made a bar of
  // seventeen links all called the same.
  // Sections alone: a page's chips pick its groups
  // (the Containers page's projects), and the jump bar is for its sections.
  // A section drawn per item (`item`: a disk, a key) is picked by the page's
  // chips instead, and is not one to jump to (big
  // chips for what changes, small pills for what does not).
  const titleOf = o => o.querySelector(":scope > summary .t")?.textContent || "";
  // Drawn again when one of its sections shows or goes: a section that
  // shows once its read lands (a space's People, Nodes, Discord, Running
  // sessions) had no chip, the bar having been drawn at the door's opening.
  // A draw that changes nothing writes nothing, so this is quiet.
  if (!g._jumpObs && window.MutationObserver){
    let soon = false;
    g._jumpObs = new MutationObserver(() => { if (soon) return; soon = true;
      requestAnimationFrame(() => { soon = false; if (g.isConnected) sectJump(g); }); });
    g._jumpObs.observe(g, {attributes: true, attributeFilter: ["hidden"], subtree: true});
  }
  const all = sectsOf(g).filter(o => !o.hasAttribute("data-item")), seen = {};
  all.forEach(o => { seen[titleOf(o)] = (seen[titleOf(o)] || 0) + 1; });
  const mine = all.filter(o => seen[titleOf(o)] === 1);
  const have = g.querySelector(":scope .sectjump");
  // Two or more (every page with more than one). One
  // the page's markup drew (Settings') is hidden rather than taken out: its
  // markup still has it, and a list missing a child the markup drew reads
  // as another writer's at the next draw, which is then written whole.
  if (mine.length < 2){
    if (have && have.__markup && !patchOwn(have)){ if (!have.hidden) have.hidden = true; }
    else have?.remove();
    return;
  }
  const bar = have || document.createElement("nav");
  if (bar.hidden) bar.hidden = false;
  // The code's own, which a patched surface leaves where it is.
  if (!have) bar.setAttribute("data-own", "");
  // In a dialog every line is a .field band (the design's dialog layout).
  // Written only where it moved: this runs after every draw, and a poll that
  // brought nothing new must write nothing (when-a-view-re-reads).
  const cls = g.matches("[data-sects]") ? "field sectjump" : "sectjump";
  if (bar.className !== cls) bar.className = cls;
  if (bar.getAttribute("aria-label") !== "sections") bar.setAttribute("aria-label", "sections");
  const html = mine.map((o, i) => `<a href="#" data-jump="${i}">${esc(titleOf(o))}</a>`).join("");
  if (bar.innerHTML !== html) drawHTML(bar, html);
  // At the top, before the surface's first section of any kind
  // (pills at the top of a page and nowhere else); before
  // its first jump target it stood mid-page under the sections its chips
  // pick (Storage's disks).
  const top = sectsOf(g)[0] || mine[0];
  if (!have) top.before(bar);
  else if (bar.nextElementSibling !== top) top.before(bar);
  bar.querySelectorAll("[data-jump]").forEach(a => a.onclick = e => {
    e.preventDefault();
    sectGoTo(mine[+a.dataset.jump]);
  });
}
// A section gone to from outside it (its jump bar's link, a door that names
// it) opens as a press on its summary does: sliding, and on a phone the one
// open before sliding shut as it opens (soleOpen); a jump only opened it, so
// a phone stood two open. Brought to the top once the
// folds have moved, since a scroll at once aimed where it stood before the
// one above it shut.
function sectGoTo(d, {smooth = true} = {}){
  if (!d) return;
  soleOpen(d);
  if (!foldOpen(d)) slideDetails(d, true);
  const g = sectGroup(d);
  const moving = (g ? sectsOf(g) : [d]).flatMap(o => o.getAnimations().filter(a => a.id === "fold"));
  const go = () => d.scrollIntoView({block: "start", behavior: smooth && !noMotion() ? "smooth" : "auto"});
  if (!moving.length) go();
  else Promise.all(moving.map(a => a.finished.catch(() => {}))).then(go);
}
// Every section is open by default at a desk and several stand open there
// (too much was hidden in folds); a long surface has a
// jump bar (sectJump). On a phone one section is open at a time on every
// folded surface, as the notebook's views do: opening one shuts the others,
// so the page is never a stack of open folds
// to scroll. Among siblings only: a section's own folds (a page's rules
// inside Pages) take turns among themselves and never close the section
// holding them.
const sectLast = new WeakMap();     // a group -> the key of the section last opened in it
// ...and the same by the group's NAME (the sections' key prefix, "nodes" for
// nodes:health and the rest): a redraw between a press and the next draw
// replaces the group's element, and a WeakMap keyed on the old one forgot
// the press, so the draw opened the prime section instead.
const sectLastByName = new Map();
const sectGroupName = g => (sectsOf(g)[0]?.dataset.sect || "").split(":")[0] || "";
function sectRemember(g, key){
  sectLast.set(g, [sectVisit, key]);
  const n = sectGroupName(g);
  if (n) sectLastByName.set(n, [sectVisit, key]);
}
function sectRecall(g){
  const n = sectGroupName(g);
  const have = sectLast.get(g) || (n ? sectLastByName.get(n) : undefined);
  return have && have[0] === sectVisit ? have[1] : undefined;
}
// A group is a view, a tab, a fold holding folds, or a dialog box that says
// it holds sections (`data-sects`: the project settings).
function sectGroup(d){ return d.parentElement?.closest("details.sect, .nbview, .doctab, [data-sects]") || null; }
const sectRuled = g => !!g?.closest?.(".nb, .doctab, [data-sects]");
// Its sections in the order drawn, those a person can see: a settings group
// with nothing in it is display:none and is no group's first.
const sectsOf = g => [...g.querySelectorAll("details.sect")]
  .filter(o => sectGroup(o) === g && getComputedStyle(o).display !== "none");
// A section at a page's level on a desk: it stands open and does not fold
// (no section collapses on a desktop; on a phone they
// take turns, one open, the page opening on its first). Not a fold on
// purpose (data-fold), one inside a row (a container's Log) or inside
// another section, nor a dialog's.
function sectFixed(d){
  return !isPhone() && !d.hasAttribute("data-fold") && !d.closest(".row:not(.ndrow), .modal")
    && !d.parentElement?.closest("details.sect") && !!d.closest(".doctab, .nbview");
}
// Which visit of a page the remembered pick belongs to: a page opened anew
// opens on its first section on a phone, a redraw within the visit keeps
// the one somebody opened (always starting with the
// top section).
let sectVisit = 0;
function sectNewVisit(){ sectVisit++; }
// Nobody has opened or shut it, and its caller left it to the default.
const sectDefault = o => !(o.dataset.sect && o.dataset.sect in sectOpen) && !o.hasAttribute("data-set");
// What a group remembers when a hand shut the one that stood open on a
// phone: none, for the rest of this visit of the page. The next draw's oneOpen
// opened the top one again with no motion, so a section shut by a press
// sprang open a moment later (smooth everywhere).
const SECT_NONE = "\u0000none";
function soleShut(d){
  const g = sectGroup(d);
  if (!sectRuled(g) || !isPhone()) return;
  if (sectsOf(g).some(o => o !== d && o.open)) return;
  sectRemember(g, SECT_NONE);
  if (d.dataset.sect) sectOpen[d.dataset.sect] = false;
}
function soleOpen(d){
  const g = sectGroup(d);
  if (!sectRuled(g)) return;
  sectRemember(g, d.dataset.sect || "");
  // Recorded now, not when the slide ends: a repaint landing mid-slide read
  // the one sliding shut as still open and kept it over the one just opened.
  if (d.dataset.sect) sectOpen[d.dataset.sect] = true;
  // On a phone the others shut as this one opens; a desk keeps them.
  // Shut by the rule, not by a hand: nothing is recorded for them, so a desk
  // this page is widened to shows them open again as it always did, and the
  // press mark comes off so the toggle their slide fires records nothing.
  if (!isPhone()) return;
  for (const o of sectsOf(g)){
    if (o === d || !o.open) continue;
    delete o.dataset.pressed;
    slideDetails(o, false);
  }
  // One not on show yet (a settings group whose read lands after the press)
  // comes up shut when it does: left as it was, it stood open beside the one
  // just opened. Nothing to slide, since nothing of it is drawn.
  for (const o of g.querySelectorAll("details.sect")){
    if (o === d || !o.open || sectGroup(o) !== g || getComputedStyle(o).display !== "none") continue;
    delete o.dataset.pressed;
    o.open = false;
  }
}
// A section opened by a draw rather than by a hand (Memories, remembered
// open): it is the one that stays, and on a phone the others shut at once,
// since a slide here overlapped two sections for its length (uniform, 6 Oct).
function keepOpen(d){
  const g = sectGroup(d);
  if (!sectRuled(g)) return;
  sectRemember(g, d.dataset.sect || "");
  oneOpen(g);
}
// After a draw. At a desk nothing anybody chose is moved: every section
// stands open unless somebody shut it. On a phone one stands open: the one
// last opened by a hand or a draw, else the one the view is for (prime),
// else the first; the rest are shut without a slide, since a draw is not a
// press.
function oneOpen(g){
  if (!sectRuled(g)) return;
  const mine = sectsOf(g);
  for (const o of mine){
    if (o.hasAttribute("data-lead")){ o.removeAttribute("data-lead"); sectRemember(g, o.dataset.sect || ""); continue; }
    // At a desk a page's sections stand open, whoever shut one before
    // (sectFixed); a fold on purpose keeps what it was given.
    if (sectFixed(o) || sectDefault(o)) o.open = true;
  }
  if (!isPhone() || mine.length < 2) return;
  // On a phone one stands open: the one opened by a hand or a draw in this
  // visit of the page, else the first that is not a fold on purpose, the
  // top of the page. A fold on purpose is one of the one at a time too: it
  // is never what a phone opens on, but opening it shuts the rest.
  const last = sectRecall(g);
  // A hand shut the last one open in this visit: all of them stay shut.
  if (last === SECT_NONE){ for (const o of mine) if (o.open && !o.dataset.slideTo) o.open = false; return; }
  const keep = mine.find(o => last && (o.dataset.sect || "") === last)
    || mine.find(o => !o.hasAttribute("data-fold")) || mine[0];
  for (const o of mine) o.open = o === keep;
}
// A button that is doing something says so until the repaint replaces it:
// grayed, and wearing the verb with an animated ellipsis. Pair with
// pressing: that disables for the round trip, this says what for.
// An action bar's More: the primary verbs stay on the bar and the
// rest go behind one button, whose menu opens under it. `items` are the
// bar's own button strings in their order, destructive last; an empty one is
// skipped, a single leftover is drawn inline (a menu of one is a detour),
// and two or more make the menu; `always` makes the menu of one too, for a
// table's buttons column, whose width is the ⋯'s whatever the row offers.
// `face` names another press for it where the verbs are of one kind (a +
// for what makes something new), and `dead` draws it so when they all are.
// wireMore wires the button; the page's one click listener (page-boot.js)
// shuts every open menu.
function actMore(items, always = false, {glyph = DOTS, said = "More", title = "the rest of what can be done to it", dead = false} = {}){
  const have = items.filter(Boolean);
  if (have.length < (always ? 1 : 2)) return have.join("");
  // ⋯, as a project's header has it: the rest of a
  // row's verbs behind one small press, named for a screen reader.
  return `<span class="more"><button type="button" class="moreb" aria-haspopup="menu" aria-expanded="false" aria-label="${esc(said)}"
      title="${esc(title)}"${dead ? " disabled" : ""}>${glyph}</button>
    <div class="actmenu" hidden role="menu">${have.join("")}</div></span>`;
}
function wireMore(root){
  root.querySelectorAll(".actbar .more > button, .acts .more > button").forEach(b => b.onclick = () => {
    const m = b.nextElementSibling;
    const open = m.hidden;
    closeMore();
    if (open){ m.hidden = false; b.setAttribute("aria-expanded", "true"); floatAt(m, b); }
  });
}
// A menu over the page, never inside what holds its button
// (a card's ⋯ in Archived was cut off at the fold's foot): at a desk
// under its button and lined up with it, above it when it would pass
// the screen's foot, at every width: the page's menus. Fixed to the screen, measured
// against whatever box holds it as its frame (a scheme's glass makes one),
// its entrance played from the start where it lands.
function floatAt(m, anchor){
  m._anchor = anchor;
  // ...and placed again when the pane it is over changes size: a press that
  // brings up the dock's line shrinks the page's pane under a menu placed
  // a moment before, which then reached under the line.
  const pn = anchor?.closest?.(".pane");
  if (pn && !pn._floatSeen && typeof ResizeObserver === "function"){
    pn._floatSeen = new ResizeObserver(() => floatSoon());
    pn._floatSeen.observe(pn);
  }
  floatPlace(m, anchor);
  m.getAnimations().forEach(a => a.cancel());
  m.style.animation = "none"; void m.offsetWidth; m.style.animation = "";
  // A box around it moving on a transform (a page fading in when the press
  // came that soon) is its frame until the move ends, and the frame then
  // goes back to the screen: placed again when the moves end, or it jumps.
  const moving = document.getAnimations().filter(a => a.playState === "running"
    && a.effect?.target instanceof Element && a.effect.target !== m && a.effect.target.contains(m));
  if (moving.length) Promise.all(moving.map(a => a.finished.catch(() => {}))).then(() => {
    if (m.isConnected && !m.hidden && m.classList.contains("floatm")) floatPlace(m, anchor);
  });
}
function floatPlace(m, anchor){
  const phone = isPhone();
  m.classList.add("floatm");
  m.classList.remove("up");
  Object.assign(m.style, {right: "auto", bottom: "auto", maxHeight: "", maxWidth: ""});
  // The frame's origin, read off a probe beside it rather than the menu
  // itself, whose own entrance may be moving it.
  const probe = document.createElement("i");
  probe.style.cssText = "position:fixed;left:0;top:0;width:0;height:0";
  m.parentElement.append(probe);
  const o = probe.getBoundingClientRect();
  probe.remove();
  // The foot is the bottom of the pane its button is in, never past the
  // bottom bar on a phone: what lies under a page's pane (the dock, its shut
  // line, a phone's keys) is drawn over the page, so a menu reaching under
  // it had its last items covered. One opened in the dock has the dock's.
  const bar = document.querySelector(".railbar")?.getBoundingClientRect();
  let foot = bar?.height ? bar.top : innerHeight;
  const pane = anchor?.closest?.(".pane")?.getBoundingClientRect();
  if (pane?.height && pane.bottom < foot) foot = pane.bottom;
  // ...and its ceiling the top of the page area its button is in, under the
  // header and the page's own bar: a menu that rose over either was under
  // it, both being drawn over the page.
  const head = document.querySelector("body > header")?.getBoundingClientRect();
  const area = anchor?.closest?.(".doc")?.getBoundingClientRect();
  const ceil = Math.max(head?.height ? head.bottom : 0, area?.height ? area.top : 0);
  // At its button on a phone too (a bottom sheet was
  // the bottom bar's More's, not a menu's), as wide as the screen allows.
  // A button under the dock or over the page's bar (the row scrolled past
  // the pane's edge) is brought into the pane first, or the menu was a
  // 40px strip with its items out of reach.
  let a = anchor.getBoundingClientRect();
  if (a.bottom > foot || a.top < ceil){
    anchor.scrollIntoView({block: "center", inline: "nearest"});
    a = anchor.getBoundingClientRect();
  }
  const w = Math.min(m.offsetWidth, innerWidth - 16), h = m.offsetHeight;
  if (phone) m.style.maxWidth = `${innerWidth - 16}px`;
  // (a button the dock covers still opens its menu above the dock)
  const aTop = Math.min(a.top, foot), aBottom = Math.min(a.bottom, foot);
  const below = foot - aBottom - 12, above = aTop - ceil - 12;
  const up = h > below && above > below;
  const room = Math.max(40, up ? above : below);
  m.style.maxHeight = room + "px";
  // Lined up with its button on the side it opens from: Start agent at a
  // card's left opens rightward from its left edge, a ⋯ at its right
  // leftward from its right edge.
  const left = Math.max(8, Math.min((a.left + a.right) / 2 < innerWidth / 2 ? a.left : a.right - w, innerWidth - w - 8));
  const top = up ? Math.max(ceil + 8, aTop - 4 - Math.min(h, room)) : aBottom + 4;
  // Its entrance moves the way it opened: up into place above its button,
  // down into place below it.
  m.classList.toggle("up", up);
  m.style.left = (left - o.left) + "px";
  m.style.top = (top - o.top) + "px";
}
// An open floating menu follows its button as the page scrolls or the window
// changes size, and a ⋯ menu closes once its button is off the screen or
// gone (closing on any scroll shut menus a redraw's own scroll had moved
// nothing under).
function floatFollow(){
  document.querySelectorAll(".floatm").forEach(m => {
    if (m.hidden || !m.isConnected) return;
    const a = m._anchor;
    const r = a?.isConnected ? a.getBoundingClientRect() : null;
    if (!r || !r.width || r.bottom < 0 || r.top > innerHeight){
      if (m.classList.contains("actmenu")) closeMore();
      return;
    }
    floatPlace(m, a);
  });
}
// A press on a card that opens its project's page
// (the whole card, not only its name): anywhere but one of its controls,
// its menu, its swatches or its chooser, and not the end of selecting text.
function cardPress(e){
  if (e.target.closest("button, a, input, select, textarea, label, .actmenu, .pcpop, .resumemenu")) return false;
  return !String(getSelection?.() || "");
}
function closeMore(){
  document.querySelectorAll(".actmenu:not([hidden])").forEach(m => {
    m.hidden = true;
    m.previousElementSibling?.setAttribute("aria-expanded", "false");
  });
}

// A bar where the thing running reports an honest measure of its own
// (SnapRAID's percentage, an upload's bytes sent), under the
// word that says what runs; "" for anything that reports none, since a bar
// that guesses is a lie with a scale on it (the progress rule). `said` is
// "45%, 120 MB/s" or a number 0..100.
function pctBar(said, label = "progress"){
  const m = typeof said === "number" ? said : parseInt(String(said || "").match(/(\d{1,3})%/)?.[1] ?? "", 10);
  if (!Number.isFinite(m)) return "";
  return `<progress class="pbar" max="100" value="${Math.max(0, Math.min(100, m))}" aria-label="${esc(label)}"></progress>`;
}

// ---- tiles, facts, tables, charts and chips (the 2.0 language)
// Three shapes every document tab draws the same way, held by the design's
// rules tiles, facts and chips and measured by uniform.mjs.

// One button of a segmented control pressed and the rest not, said to a
// screen reader as well as drawn (consistency pass J18: four of the six
// toggled the class alone). `on` is the id of the one pressed.
function segPick(ids, on){
  for (const id of ids){
    const b = $(id);
    if (!b) continue;
    b.classList.toggle("on", id === on);
    b.setAttribute("aria-pressed", String(id === on));
  }
}


// A page's head: what the page is
// about with its state as pills, then one status line of what is news
// (statusLine), and the buttons about it on an action bar. Each part only
// when the page has it. A fact that is not news is not in a page's head: it
// is said beside what it describes, or not at all (a
// Details fold was one more kind of heading on pages that each have their
// own). A page about one thing (a machine, the install key, how this
// controller is reached) says `about` and its facts are its body's grid.
// `pills` is markup (pill spans); `line` statusLine's parts; `facts`
// factGrid's pairs, drawn only with `about`.
function pageHead({title = "", pills = "", line = [], facts = [], about = false, actions = "", cls = ""} = {}){
  const grid = about ? factGrid(facts, "pghfacts") : "";
  const said = statusLine(line, true);
  if (!title && !pills && !said && !grid && !actions) return "";
  return `<div class="field pghead${about ? " about" : ""}${cls ? " " + esc(cls) : ""}">${
    title || pills ? `<div class="name">${title === GHOST ? skv(10) : title ? esc(title) : ""}${pills ? `${title ? " " : ""}${pills}` : ""}</div>` : ""}${said}${grid}${
    actions ? `<div class="actbar">${actions}</div>` : ""}</div>`;
}

// A page's status line (the tiles and the facts
// made pages busier than they are): what the page is about now, as short
// phrases on one line joined by a dot, quiet but for a phrase that wants
// doing, which wears --warn or --bad. A part is {text} or {value, label,
// sub, tone}: a number and what it counts ("5 updates due"), the number in
// ink. `bare` draws the line without its band, for a head that holds it.
function statusLine(parts, bare = false){
  const ps = (parts || []).filter(p => p && !p.omit && (p.text || p.value != null || p.label));
  if (!ps.length) return "";
  const one = p => {
    const v = p.value === GHOST ? skv(1.4) : p.value != null && p.value !== "" ? `<b>${esc(String(p.value))}${p.unit ? " " + esc(p.unit) : ""}</b> ` : "";
    const words = p.text != null ? esc(p.text) : `${esc(p.label || "")}${p.sub === GHOST ? " " + skv(4) : p.sub ? " " + esc(p.sub) : ""}`;
    return `<span class="pgl${p.tone ? " " + esc(p.tone) : ""}"${p.title ? ` title="${esc(p.title)}"` : ""}>${v}${words}</span>`;
  };
  const line = `<div class="pgline">${ps.map(one).join('<span class="sep" aria-hidden="true"> · </span>')}</div>`;
  return bare ? line : `<div class="field">${line}</div>`;
}
// What a surface's numbers were, a row of tiles, are its status line now:
// each tile a phrase, its number first and what it counts after it.
// Kept by its name for the pages and the notebook's glance that call it; a
// tile flagged `omit`, a number that is always the same, is still left out.
function statTiles(tiles){
  return statusLine((tiles || []).map(t => t && !t.omit ? {...t} : null));
}
// What a placeholder passes where a value will go (statTiles, a page's own
// builders): drawn as a shimmer in the real markup.
const GHOST = Object.freeze({ghost: true});
// A notebook view's glance (the a-notebook/views rule): the band under
// its control row, in the Containers page's order: the numbers the view is
// about as tiles, then its status line, words alone (`said`, markup) with the
// buttons those words are about at its right. Painted only when it changed,
// so a poll's redraw leaves it still; an empty view passes no tiles, its
// empty state being the hint where its list would be.
// `tiles` may be a page's own drawing of them (the Docker view's, dmTiles).
// The same glance while a view's data is on its way: the shape that view's
// glance had the last time it was drawn (in any notebook: flipping between
// projects, each settles as the last one did), else what its markup
// declares on its .nbglance (data-tiles, data-said) for a first open. The
// markup is the one place a view's waiting shape is written, so it cannot
// drift from a view's own code; templates.mjs holds
// both. A glance a view has drawn for real, empty included, is never
// overdrawn: an empty roadmap kept placeholder tiles over its empty state.
const glanceSeen = {};
function glanceWaiting(el){
  if (!el || el.dataset.drawn) return false;
  const was = glanceSeen[el.id];
  const n = was ? was.tiles : +el.dataset.tiles || 0;
  const said = was ? was.said : "said" in el.dataset;
  const tiles = statTiles(Array.from({length: n}, () => ({value: GHOST, label: "\u00a0"})));
  // ...its words where the view will say them: on the control row's slot
  // where it has one, as viewGlance does, so the row's buttons wait beside
  // the words under the tiles. With the slot empty a row of a button or two
  // shares the tiles' line, and the buttons rode up beside the tiles while
  // the view waited, dropping under them as it landed.
  const slot = el.closest(".nbview")?.querySelector(":scope > .nbhead > .nbsaidslot");
  if (slot){
    const wrote = patch(el, tiles);
    return patch(slot, said ? `<div class="notice note">${skel("word")}</div>` : "") || wrote;
  }
  return patch(el, tiles + (said ? viewSaid(skel("word")) : ""));
}
// What a view has to say beside its tiles, in the notice voice
// (no loose words at a page's top): an error in red, a warning in
// gold, a state in the note's color, its buttons on the notice's own bar. A
// bare .notice is gold, so a state passed with no tone is a note: the
// Artifacts view's "the code base as a zip" read as a warning.
function viewSaid(said, actions = "", tone = ""){
  if (!said && !actions) return "";
  return `<div class="field nbsaid"><div class="notice ${esc(tone || "note")}">${said}${
    actions ? `<div class="actbar">${actions}</div>` : ""}</div></div>`;
}
function viewGlance(el, tiles = [], said = "", actions = "", tone = ""){
  if (!el) return false;
  const html = Array.isArray(tiles) ? statTiles(tiles) : tiles || "";
  // A view whose control row holds only buttons keeps its status line on
  // that row, the words at its left and the buttons at its right
  // (a button never on a line of its own), in the row's
  // own slot, which this paints and nothing else does.
  const slot = el.closest(".nbview")?.querySelector(":scope > .nbhead > .nbsaidslot");
  let wrote;
  if (slot){
    wrote = patch(el, html);
    wrote = patch(slot, said || actions ? `<div class="notice ${esc(tone || "note")}">${said}${actions ? `<div class="actbar">${actions}</div>` : ""}</div>` : "") || wrote;
  } else wrote = patch(el, html + viewSaid(said, actions, tone));
  // Marked once: a poll that brings nothing new writes nothing (uniform).
  if (!el.dataset.drawn) el.dataset.drawn = "1";
  glanceSeen[el.id] = {tiles: el.querySelectorAll(".pgl").length, said: !!(said || actions)};
  return wrote;
}
// A view's glance when its read failed: no tiles, and what was being read
// with the error's words, in red.
function glanceBad(el, what, err){ return viewGlance(el, [], esc(what + ": " + err), "", "bad"); }

// What a card's settings are, read: one
// wrapping line of pills, each its label in the quiet voice and its value,
// a pill with no label a state on its own (Starts on boot).
function factPills(pairs, cls = ""){
  const rows = (pairs || []).filter(p => p && String(p[1] ?? "").trim() !== "");
  if (!rows.length) return "";
  return `<div class="fpills${cls ? " " + esc(cls) : ""}"><div class="fpl">${rows.map(([k, v, tone]) =>
    `<span class="fpill${tone ? " " + esc(tone) : ""}">${k ? `<span class="k">${esc(k)}</span>` : ""}<span class="v">${v}</span></span>`).join("")}</div></div>`;
}

// What a row knows, as labels and values: two columns at a desk, one on a
// phone. A pair whose value is empty is left out, so a caller lists what
// it has and the grid says what there is. `html` on a pair means the value
// is already markup (a code span, a link); otherwise it is escaped, and
// `cls` names the value's element for a suite that reads one.
function factGrid(pairs, cls = ""){
  const rows = (pairs || []).filter(p => p && p[1] !== undefined && p[1] !== null && String(p[1]).trim() !== "");
  if (!rows.length) return "";
  return `<dl class="facts${cls ? " " + esc(cls) : ""}">${rows.map(([k, v, opt]) => `
    <div class="fact"><dt>${esc(k)}</dt><dd${opt && opt.cls ? ` class="${esc(opt.cls)}"` : ""}>${
      v === GHOST ? skv(8) : opt && opt.html ? v : esc(String(v))}</dd></div>`).join("")}</dl>`;
}

// ---- tables (the design's tables rule) -----------------------
// A list whose rows are all the same shape is a table: a header line naming
// the columns over rows whose first line holds the same columns, so a value
// is found by looking down a column rather than by reading every row. Each
// row is still a row: a reason under its line in red, its buttons at the
// line's right end, what is long (a log, a card) behind its fold. On a phone
// the header goes and each cell after the first wears its column's name.
//
// `cols` is [{label, w, num, act}]: `w` a grid track, a share (the default,
// minmax(0,1fr)) or a fixed width and never auto, since each line is its own
// grid and only shares and widths line up across them; `num` right-aligns
// tabular figures; `act` is the buttons' column, unlabeled.
function tblTracks(cols){
  return cols.map(c => c.w || "minmax(0,1fr)").join(" ");
}
// The table around its rows, the header line first.
// Cards or a list, as their pictures at every width:
// four tiles, and lines; the word is the
// button's name and its title says what each shows. `attr` is the data-
// attribute the page's wiring reads (data-dmview, data-vmview).
const VIEW_ICON_CARDS = `<svg viewBox="0 0 16 16" width="16" height="16" aria-hidden="true" fill="none" stroke="currentColor" stroke-width="1.5"><rect x="2" y="2" width="5" height="5" rx="1"/><rect x="9" y="2" width="5" height="5" rx="1"/><rect x="2" y="9" width="5" height="5" rx="1"/><rect x="9" y="9" width="5" height="5" rx="1"/></svg>`;
const VIEW_ICON_LIST = `<svg viewBox="0 0 16 16" width="16" height="16" aria-hidden="true" fill="none" stroke="currentColor" stroke-width="1.5" stroke-linecap="round"><path d="M2 4h12M2 8h12M2 12h12"/></svg>`;
// A pulldown in a bar or a row is as wide as its longest answer
// (page-overrides.css keeps it from stretching). A base
// select (page-skin.css) is as wide as the answer chosen, so the width is
// set here from what it measures: itself with its longest answer chosen
// and nothing sizing it, then put back as it was, its choice and its style.
// The canvas only says which answer is longest. Kept by its answers' words,
// so it is measured again only when they change; one not on show waits for
// its turn. A browser without base-select sizes a select by its longest
// answer itself.
const PICKERS = ":is(.docbarrow,.histbar,.actbar,.ctlrow,.ctlline,.lfilter,.rninvitebar,label.wkpick) select:not([multiple],[size]):not(:is(.fgrid,.setrow.col,.prefrow,.phead) select)";
let pickFitDue = 0;
let pickInk = null;
// A group header's node picker is as wide as the name it shows, measured
// here in every browser: left to size itself it was cut short with room
// beside it (bb-sand… on a phone in Firefox; in
// WebKit too), each engine keeping a different room for the closed
// picker's arrow at the header's larger face. The name's ink, its own
// padding, and room for the arrow whatever draws it; the header's own
// max-width still lets it give way to the pill beside it.
const HEAD_PICKERS = ".pane .bar.page.grouped .phead > label.pick > select";
const HEAD_ARROW = 52;
function fitHeadPickers(){
  pickInk = pickInk || document.createElement("canvas").getContext("2d");
  for (const s of document.querySelectorAll(HEAD_PICKERS)){
    const word = s.selectedOptions[0]?.label || s.selectedOptions[0]?.textContent || "";
    if (!word || !s.checkVisibility()) continue;
    const cs = getComputedStyle(s), font = `${cs.fontStyle} ${cs.fontWeight} ${cs.fontSize} ${cs.fontFamily}`;
    const key = `${font}\n${word}`;
    if (s.dataset.fitFor === key) continue;
    pickInk.font = font;
    const px = v => parseFloat(v) || 0;
    // ...and what its own negative margin takes back: its label is as wide
    // as it is less that margin, and the header's max-width holds it to that.
    s.style.width = `${Math.ceil(pickInk.measureText(word).width + px(cs.paddingLeft) + Math.max(px(cs.paddingRight), HEAD_ARROW)
      + px(cs.borderLeftWidth) + px(cs.borderRightWidth) + Math.max(0, -px(cs.marginLeft)))}px`;
    s.dataset.fitFor = key;
  }
}
function fitPickers(){
  pickFitDue = 0;
  fitHeadPickers();
  // The rest is a base select's alone: a browser that draws its own select
  // sizes one in a bar by its longest answer itself.
  if (!CSS.supports("appearance", "base-select")) return;
  pickInk = pickInk || document.createElement("canvas").getContext("2d");
  for (const s of document.querySelectorAll(PICKERS)){
    const words = [...s.options].map(o => o.label || o.textContent || "");
    const key = words.join("\n");
    if (!words.length || s.dataset.fitFor === key || !s.checkVisibility()) continue;
    const cs = getComputedStyle(s);
    pickInk.font = cs.font || `${cs.fontWeight} ${cs.fontSize} ${cs.fontFamily}`;
    const ink = words.map(w => pickInk.measureText(w).width);
    const longest = ink.indexOf(Math.max(...ink)), at = s.selectedIndex;
    const was = s.getAttribute("style") || "";
    s.style.cssText = `${was};width:auto;flex:none;max-width:none;min-width:0`;
    s.selectedIndex = longest;
    const w = s.getBoundingClientRect().width;
    s.selectedIndex = at;
    s.setAttribute("style", was);
    s.style.width = `${Math.ceil(w)}px`;
    s.dataset.fitFor = key;
  }
}
// ...asked for on a draw, once a frame however many draws there were.
function fitPickersSoon(){
  if (!pickFitDue) pickFitDue = requestAnimationFrame(fitPickers);
}
function viewSeg(attr, cur, cardsSay, listSay, dead = "", words = ["Cards", "List"]){
  const b = (v, word, say, icon) => `<button type="button" data-${attr}="${v}" class="${cur === v ? "on" : ""}" aria-pressed="${cur === v}" title="${esc(word)}: ${esc(say)}" aria-label="${word}"${dead}>${icon}</button>`;
  return `<div class="pseg dmviewseg" role="group" aria-label="${esc(`${words[0]} or ${words[1]}`.toLowerCase())}">${
    b("cards", words[0], cardsSay, VIEW_ICON_CARDS)}${b("list", words[1], listSay, VIEW_ICON_LIST)}</div>`;
}
function tblWrap(cols, rows, cls = ""){
  return `<div class="tbl${cls ? " " + esc(cls) : ""}" data-style="--tcols:${tblTracks(cols)}">
    <div class="thead">${cols.map(c => `<span class="th${c.num ? " num" : ""}${c.act ? " act" : ""}">${
      c.act ? "" : esc(c.label || "")}</span>`).join("")}</div>${rows}</div>`;
}
// One row's line: a cell per column, in order; a cell is markup already.
// `tag` is "summary" for a row whose line opens its fold, `cls` its own
// class, `attrs` its own attributes (a data- key a wiring reads).
function tblLine(cols, cells, tag = "div", cls = "", attrs = ""){
  return `<${tag} class="tline${cls ? " " + esc(cls) : ""}"${attrs ? " " + attrs : ""}>${cols.map((c, i) => `<span class="td${i === 0 ? " lead" : ""}${
    c.num ? " num" : ""}${c.act ? " act" : ""}"${i && !c.act && c.label ? ` data-th="${esc(c.label)}"` : ""}>${cells[i] ?? ""}</span>`).join("")}</${tag}>`;
}

// ---- charts (the design's charts rule) -----------------------
// Where a number moves: an hour's line chart on a node's page and a
// sparkline beside a running container's number, drawn inline with no
// library. One series to a chart, so no legend: the caption names it. The
// plot is an SVG stretched to its box with strokes that do not scale; the
// axis labels and the end dot are HTML, so text keeps its size at every
// width. A gap longer than three samples' spacing breaks the line rather
// than drawing across a time nobody measured.

// A sparkline: the values in the quiet voice, the last one a dot in the
// accent, 96 by 24. `max` is the scale's top (100 for a percentage, more
// when a container's CPU spans cores).
function sparkSvg(vals, max = 100, label = ""){
  const v = (vals || []).filter(x => typeof x === "number");
  if (v.length < 2) return "";
  const top = Math.max(max, ...v), W = 96, H = 24, pad = 3;
  const pt = (x, i) => [pad + i * (W - 2 * pad) / (v.length - 1), H - pad - x / top * (H - 2 * pad)];
  const pts = v.map(pt), last = pts.at(-1);
  return `<svg class="spark" width="${W}" height="${H}" viewBox="0 0 ${W} ${H}" role="img" aria-label="${esc(label)}">
    <polyline points="${pts.map(p => p.map(n => n.toFixed(1)).join(",")).join(" ")}"/>
    <circle cx="${last[0].toFixed(1)}" cy="${last[1].toFixed(1)}" r="3"/></svg>`;
}

// The hour as a chart: `pts` is [[at, value], ...], `fmt` how a value is
// said, `max` the scale's top. Its id keeps the crosshair where it was
// across the redraw a new sample brings.
const CHART_SPAN = 3600;
// A longer span (This machine's Reporting): the same chart
// over six hours, a day, a week or a month, its axis and caption words
// for the span, the hour's chart unchanged.
const CHART_SPANS = {"6h": [6 * 3600, "the last six hours", ["6 h ago", "3 h", "now"]], day: [86400, "the last day", ["a day ago", "12 h", "now"]],
                     week: [7 * 86400, "the last week", ["a week ago", "3.5 days", "now"]], month: [30 * 86400, "the last month", ["a month ago", "15 days", "now"]]};
function hourChart(id, title, pts, fmt = v => `${Math.round(v)}%`, max = 100, span = ""){
  const p = (pts || []).filter(x => x && typeof x[1] === "number");
  const sp = CHART_SPANS[span] || [CHART_SPAN, "the last hour", ["an hour ago", "30 min", "now"]];
  if (!p.length) return `<figure class="chart" data-chart="${esc(id)}"><figcaption><span class="ct">${esc(title)}</span></figcaption>
    <div class="hint">no samples yet: the node sends one each poll</div></figure>`;
  const now = p.at(-1)[0], from = now - sp[0], vals = p.map(x => x[1]);
  const top = Math.max(max, ...vals);
  const X = at => Math.max(0, Math.min(1000, (at - from) / sp[0] * 1000)), Y = v => 100 - v / top * 100;
  // Runs split where the samples stop: a node that went quiet is a gap, not
  // a slope. Measured against the slow end of its spacing, not the middle:
  // a busy node reports in bursts seconds apart and an idle one at the
  // poll, so three of the median broke every idle stretch, which is where
  // the load sits low, into dots.
  const gaps = p.slice(1).map((x, i) => x[0] - p[i][0]).sort((a, b) => a - b);
  const slow = gaps.length ? gaps[Math.min(gaps.length - 1, Math.floor(gaps.length * 0.9))] : 60;
  const runs = [[p[0]]];
  for (let i = 1; i < p.length; i++){
    if (p[i][0] - p[i - 1][0] > Math.max(slow * 3, 90)) runs.push([]);
    runs.at(-1).push(p[i]);
  }
  const line = runs.map(r => r.map((x, i) => `${i ? "L" : "M"}${X(x[0]).toFixed(1)},${Y(x[1]).toFixed(1)}`).join("")).join("");
  const fill = runs.filter(r => r.length > 1).map(r => `M${X(r[0][0]).toFixed(1)},100${
    r.map(x => `L${X(x[0]).toFixed(1)},${Y(x[1]).toFixed(1)}`).join("")}L${X(r.at(-1)[0]).toFixed(1)},100Z`).join("");
  const avg = vals.reduce((a, b) => a + b, 0) / vals.length, last = p.at(-1);
  return `<figure class="chart" data-chart="${esc(id)}">
    <figcaption><span class="ct">${esc(title)}</span><span class="cv">${esc(fmt(last[1]))}</span>
      <span class="cs">${esc(sp[1])}: low ${esc(fmt(Math.min(...vals)))}, average ${esc(fmt(avg))}, high ${esc(fmt(Math.max(...vals)))}</span></figcaption>
    <div class="cplot">
      <div class="cy" aria-hidden="true"><span>${esc(fmt(top))}</span><span>${esc(fmt(top / 2))}</span><span>${esc(fmt(0))}</span></div>
      <div class="carea" tabindex="0" role="img" aria-label="${esc(`${title} over ${sp[1]}, now ${fmt(last[1])}`)}"
        data-pts="${esc(JSON.stringify(p.map(x => [x[0], x[1]])))}" data-from="${from}" data-span="${sp[0]}">
        <svg viewBox="0 0 1000 100" preserveAspectRatio="none" aria-hidden="true">
          <line class="cgrid" x1="0" x2="1000" y1="0" y2="0"/><line class="cgrid" x1="0" x2="1000" y1="50" y2="50"/>
          <line class="cgrid" x1="0" x2="1000" y1="100" y2="100"/>
          <path class="cfill" d="${fill}"/><path class="cline" d="${line}"/></svg>
        <span class="cdot" data-style="left:${(X(last[0]) / 10).toFixed(2)}%;top:${Y(last[1]).toFixed(2)}%"></span>
        <span class="chair" hidden></span><span class="ctip" hidden></span>
        <div class="cx" aria-hidden="true"><span>${esc(sp[2][0])}</span><span>${esc(sp[2][1])}</span><span>${esc(sp[2][2])}</span></div>
      </div>
    </div></figure>`;
}

// The crosshair: it finds the nearest sample to the pointer (or, focused,
// the one the arrow keys move to) and says its value and its time. Kept by
// chart id across a redraw, until the pointer leaves.
let chartHover = {id: "", i: -1};
function wireCharts(root, fmtOf = () => v => `${Math.round(v)}%`){
  root.querySelectorAll(".chart .carea").forEach(a => {
    const fig = a.closest(".chart"), id = fig.dataset.chart, fmt = fmtOf(id);
    let pts;
    try{ pts = JSON.parse(a.dataset.pts || "[]"); }catch(e){ pts = []; }
    if (!pts.length) return;
    const from = Number(a.dataset.from), span = Number(a.dataset.span) || CHART_SPAN, hair = a.querySelector(".chair"), tip = a.querySelector(".ctip");
    const show = i => {
      if (i < 0){ hair.hidden = tip.hidden = true; return; }
      const x = Math.max(0, Math.min(100, (pts[i][0] - from) / span * 100));
      hair.style.left = tip.style.left = `${x}%`;
      tip.classList.toggle("flip", x > 70);
      tip.textContent = "";
      const b = document.createElement("b"); b.textContent = fmt(pts[i][1]);
      tip.append(b, " ", span > 86400 ? fmtTime(pts[i][0] * 1000, {weekday: "short", hour: "2-digit", minute: "2-digit"})
                       : fmtTime(pts[i][0] * 1000, {hour: "2-digit", minute: "2-digit"}));
      hair.hidden = tip.hidden = false;
      chartHover = {id, i};
    };
    const near = ev => {
      const r = a.getBoundingClientRect(), at = from + (ev.clientX - r.left) / r.width * span;
      let best = 0;
      pts.forEach((p, i) => { if (Math.abs(p[0] - at) < Math.abs(pts[best][0] - at)) best = i; });
      return best;
    };
    a.onpointermove = ev => show(near(ev));
    a.onpointerleave = () => { if (document.activeElement !== a){ show(-1); chartHover = {id: "", i: -1}; } };
    a.onfocus = () => show(chartHover.id === id && chartHover.i >= 0 ? Math.min(chartHover.i, pts.length - 1) : pts.length - 1);
    a.onblur = () => { show(-1); chartHover = {id: "", i: -1}; };
    a.onkeydown = ev => {
      if (ev.key !== "ArrowLeft" && ev.key !== "ArrowRight") return;
      ev.preventDefault();
      const i = chartHover.id === id ? chartHover.i : pts.length - 1;
      show(Math.max(0, Math.min(pts.length - 1, i + (ev.key === "ArrowLeft" ? -1 : 1))));
    };
    if (chartHover.id === id && chartHover.i >= 0) show(Math.min(chartHover.i, pts.length - 1));
  });
}

// Save and Revert under what they save, in one order on every page
// (consistency batch J: the notebook put Save first, Users and Roles Revert
// first with Save filled): the state, then Save, then Revert in caution, the
// undoing verb last. `save` and `revert` are each button's own attributes
// (an id, a data key), `state` the words on its line, `dead` keeps both
// asleep while there is nothing to save, so the bar does not move, and
// `cls` and `attrs` are the bar's own.
function saveBar({save, revert, state = "", dead = false, cls = "", attrs = ""}){
  return `<div class="actbar${cls ? " " + cls : ""}"${attrs ? " " + attrs : ""}><span class="state">${state}</span><span class="sp"></span>
    ${saveVerbs({save, revert, dead}).join("")}</div>`;
}
// ...the same two as a form's foot hands them to formBox.
function saveVerbs({save, revert, dead = false}){
  const off = dead ? " disabled" : "";
  return [`<button type="button" ${save}${off}>Save</button>`, `<button type="button" class="caution" ${revert}${off}>Revert</button>`];
}

// A dialog's foot in the design's order (a-dialog: the state on the left,
// Cancel and the one filled button on the right), one way on every dialog
// (consistency batch J: nine foots put the action before Cancel, two
// without type="button"). `cancel` is the Cancel or Done button, `acts`
// what follows it, the filled one last, and `lead` what sits at the left.
// A dialog that switches between panes keeps one size whichever is on show:
// each pane is drawn in turn before a frame is
// painted, and the box is held at the tallest, never past its own
// max-height; what fills in later (a node list, a file read) scrolls inside
// it rather than growing it. On a phone the box is the whole screen on
// every pane, so nothing is held. `show(key)` draws a pane; `cur` is the one
// to leave on show. Returns the height held.
function holdPanes(box, keys, show, cur){
  if (!box) return 0;
  box.style.height = "";
  box.classList.remove("held");
  if (keys.length < 2 || isPhone()) return 0;
  let h = 0;
  for (const k of keys){ show(k); h = Math.max(h, box.getBoundingClientRect().height); }
  show(cur);
  const held = Math.ceil(h);
  box.style.boxSizing = "border-box";
  box.style.height = held + "px";
  // ...its buttons at the held box's foot, as on a phone, rather than under
  // a shorter pane with the rest of the height empty below them.
  box.classList.add("held");
  return held;
}
// A dialog's foot in the dialog rule's one order: what it says (a .state
// in `lead`) first, the spacer, then the verbs, the primary first and the
// rest after it, the way out (`cancel`), and a verb that cannot be undone
// last. A button handed in `lead` is a verb like the rest.
function dlgFoot(cancel, acts, lead = ""){
  const BUTTON = /<button\b[\s\S]*?<\/button>/g;
  const btns = [...String(acts + lead).matchAll(BUTTON)].map(m => m[0]);
  const is = (b, c) => new RegExp(`class="[^"]*\\b${c}\\b`).test(b.slice(0, b.indexOf(">")));
  const verbs = [...btns.filter(b => is(b, "primary")), ...btns.filter(b => !is(b, "primary") && !is(b, "danger")),
                 cancel, ...btns.filter(b => is(b, "danger"))];
  return `<div class="foot">${String(lead).replace(BUTTON, "")}<span class="sp"></span>${verbs.join("")}</div>`;
}

// A row's remove, the bin, drawn one way on every page (consistency batch
// J: eight copies, some without type="button"): `attr` is the page's data
// key and its value, `label` what it removes for a screen reader, `title`
// what it does, and `why` the reason it is off when it is.
function rmIcon(attr, label, {title = "", why = ""} = {}){
  return `<button type="button" class="eye rm" ${attr} aria-label="${esc(label)}"${
    why ? ` disabled title="${esc(why)}"` : title ? ` title="${esc(title)}"` : ""}>${BIN}</button>`;
}

// A page that works on a node, with none enrolled: one sentence, the same
// on every such page, and the way to one (consistency batch J: nginx,
// storage, the emulator and toolchains each said it their own way, two
// with a link and two without). `what` says what needs the node.
function noNodeYet(what, cls = ""){
  return `<div class="empty${cls ? " " + cls : ""}">No node yet: ${what}; enroll one on the ${pageLink("nodes", "Nodes page")} under Machines.</div>`;
}

// A row of chips narrowing a list: All first, then one per group with its
// count, the one in force wearing `.on`. A chip is a view, never a setting:
// the caller keeps which is on for the page's life and nothing is saved.
// `groups` is [{key, label, count}], `on` the key in force ("" for All),
// `all` All's count where the groups overlap (chipButtons).
function chipBar(groups, on, attr, all){
  const chips = chipButtons(groups, on, attr, all);
  return chips ? `<div class="field"><div class="chips" data-chips="${esc(attr)}">${chips}</div></div>` : "";
}
// A row of chips keeps where it was scrolled across the redraws a press or
// a poll brings (pressing a chip far along the row
// sent it back to its start): its scroll kept by the row's attribute as it
// moves, and put back on the row drawn in its place.
const chipScroll = {};
function chipsScrolled(e){
  const c = e.target;
  if (c?.matches?.(".chips[data-chips]")) chipScroll[c.dataset.chips] = c.scrollLeft;
  if (c?.matches?.(".chips, .hscroll")) chipsEdge(c);
}
// Which ends of a row of chips have more past them (on
// a desk a row that ran off the edge had no way along but a trackpad): .chl
// and .chr, which draw the arrow at that end and fade it.
function chipsEdge(c){
  const max = c.scrollWidth - c.clientWidth;
  c.classList.toggle("chl", max > 1 && c.scrollLeft > 1);
  c.classList.toggle("chr", max > 1 && c.scrollLeft < max - 1);
}
function chipsEdges(root = document){
  // ...and a row of sub-tabs that may run off its edge.
  root.querySelectorAll?.(".chips, .hscroll").forEach(chipsEdge);
}
// A press on an end's arrow moves the row most of its width that way. The
// arrows are the row's own ::before and ::after, so the press lands on the
// row itself, at its edge, never on a chip.
const CHIP_ARROW = 32;
function chipsArrow(e){
  const c = e.target;
  if (!c?.matches?.(".chips.chl, .chips.chr, .dockline.chl, .dockline.chr, .hscroll.chl, .hscroll.chr") || chipDragged) return;
  const r = c.getBoundingClientRect(), by = Math.max(80, c.clientWidth * 0.7);
  if (c.classList.contains("chl") && e.clientX < r.left + CHIP_ARROW) c.scrollBy({left: -by, behavior: "smooth"});
  else if (c.classList.contains("chr") && e.clientX > r.right - CHIP_ARROW) c.scrollBy({left: by, behavior: "smooth"});
}
// ...and a mouse drags it: held and moved past a few pixels the row follows
// the pointer, and the click a drag ends on presses nothing. A touch keeps
// the browser's own swipe.
let chipDrag = null, chipDragged = false;
function chipsDown(e){
  const c = e.target?.closest?.(".chips, .dockline, .hscroll");
  if (!c || e.pointerType !== "mouse" || e.button !== 0 || c.scrollWidth <= c.clientWidth + 1) return;
  chipDrag = {c, x: e.clientX, left: c.scrollLeft, moved: false};
  chipDragged = false;
}
function chipsMove(e){
  if (!chipDrag) return;
  const dx = e.clientX - chipDrag.x;
  if (!chipDrag.moved && Math.abs(dx) < 5) return;
  chipDrag.moved = true;
  chipDrag.c.classList.add("dragging");
  chipDrag.c.scrollLeft = chipDrag.left - dx;
}
function chipsUp(){
  if (!chipDrag) return;
  chipDragged = chipDrag.moved;
  chipDrag.c.classList.remove("dragging");
  chipDrag = null;
  // The click this release makes is swallowed (chipsClickGuard), then the
  // next press is a press again.
  if (chipDragged) setTimeout(() => { chipDragged = false; }, 0);
}
function chipsClickGuard(e){
  if (chipDragged && e.target?.closest?.(".chips, .hscroll")){ e.stopPropagation(); e.preventDefault(); }
}
function chipsBack(root){
  // Its ends, once it is laid out.
  if (root.matches(".chips, .hscroll") || root.querySelector(".chips, .hscroll")) requestAnimationFrame(() => chipsEdges(root.parentNode || document));
  for (const c of root.matches(".chips[data-chips]") ? [root] : root.querySelectorAll(".chips[data-chips]")){
    const x = chipScroll[c.dataset.chips];
    if (x && c.scrollLeft !== x){
      c.scrollLeft = x;
      // ...and once more after layout, for a row not laid out yet when
      // it was added (inside a view fading in).
      requestAnimationFrame(() => { if (c.isConnected && c.scrollLeft !== x) c.scrollLeft = x; });
    }
  }
}
// Chips by release (the Roadmap's by an item's target,
// Bugs' by the version a report was seen in): [{key, label, count}], one per
// X.Y.Z that verOf gives, oldest first, then `none` with what has none.
const relOf = v => (String(v || "").match(/^v?(\d+\.\d+\.\d+)/) || [])[1] || "";
function versionChips(rows, verOf, none){
  const n = new Map();
  // `verOf` may give several (an item and its steps' own): the row
  // counts once under each.
  for (const r of rows)
    for (const k of new Set([].concat(verOf(r)).map(v => relOf(v) || "none"))) n.set(k, (n.get(k) || 0) + 1);
  const num = v => v.split(".").map(Number);
  const keys = [...n.keys()].filter(k => k !== "none")
    .sort((a, b) => { const x = num(a), y = num(b); return x[0] - y[0] || x[1] - y[1] || x[2] - y[2]; });
  return [...keys.map(k => ({key: k, label: k, count: n.get(k)})),
          ...(n.has("none") ? [{key: "none", label: none, count: n.get("none")}] : [])];
}
// Whether a row is under the release chip in force ("" is All).
const inRelease = (v, on) => !on || (on === "none" ? !relOf(v) : relOf(v) === on);
// The chips alone, for a band that holds more than them (a list's search
// beside them): "" when fewer than two groups have anything,
// but for one that holds less than the whole, which narrows all the same.
// `all` is All's count where the groups overlap (a branch both Active and
// Yours), the groups' sum otherwise. `allWord` names the first chip where a
// second row under another would say All again (the Library's sources,
// Bugs' and the Roadmap's versions).
function chipButtons(groups, on, attr, all, allWord = "All"){
  // A group with no count to give (a disk, a key: count null) is a chip
  // with its name alone; one whose count is 0 has nothing to show.
  const gs = (groups || []).filter(g => g && (g.count || g.count === null));
  if (!gs.length) return "";
  const total = all ?? (gs.some(g => g.count === null) ? null : gs.reduce((n, g) => n + g.count, 0));
  // One group alone is drawn only where it holds less than the whole (a
  // list's favorites): otherwise All says the same.
  if (gs.length < 2 && !(total !== null && gs[0].count !== null && gs[0].count < total)) return "";
  const chip = (key, label, count) => `<button type="button" class="chip${(on || "") === key ? " on" : ""}"
    ${attr}="${esc(key)}" aria-pressed="${(on || "") === key}">${esc(label)}${
      count === null || count === undefined ? "" : `<span class="pill">${count}</span>`}</button>`;
  return chip("", allWord, total) + gs.map(g => chip(g.key, g.label, g.count)).join("");
}
// A band of chips in a box of its own: the chips patched in and, when that
// wrote anything, each wired so its press is a move (chipMove) of the
// `items` in `scope` to what `pick` draws for the chip's key, which is its
// `attr`. The band is there, it does not arrive, so the patch is a quiet
// one. Answers whether it drew, as patch does.
function chipBand(box, html, attr, scope, items, pick){
  const drew = patch(box, html, true);
  if (drew) box.querySelectorAll(`[${attr}]`).forEach(b => b.onclick = () =>
    chipMove(scope, items, () => pick(b.getAttribute(attr))));
  return drew;
}
// Whether a row answers a list's search: its number, with its letter or
// bare (R12 or 12), or any of its words, case aside. An empty search
// is all. `q` comes trimmed and in lower case, `prefix` is the letter in
// lower case, and `words` gives the row's words only when a search asks.
function idOrWords(prefix, id, words, q){
  if (!q) return true;
  if (q === prefix + id || q === String(id)) return true;
  return words().some(t => String(t || "").toLowerCase().includes(q));
}
