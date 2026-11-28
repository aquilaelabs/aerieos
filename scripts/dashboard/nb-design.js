// The notebook's Design view: what the project looks like, kept. One design
// language (colors as tokens, type, shape, space, motion and the operator's
// own rules) and pages laid out as labeled blocks on a phone or desktop
// frame, each named for what it is for and the platform it is built for.
// Two sections, the pages and the themes, open like every page's
// (they folded for no reason); each shows one at a time, chosen on a pulldown, and each entry, the
// language included, carries its rules as a section inside it, every rules
// list the Briefing's.
// Every edit is staged and its section's Save (Themes or Pages) writes it at
// once, the way the roadmap saves. Nothing here is a prompt: a session reads
// the design piece by piece with aerie design show (design.py), which is what
// docs/design-language.md is written from too. One classic script beside
// index.html (docs/design-language.md, Files): a factory makeNotebook calls
// per notebook, and below it the view's parts, each a function handed the
// view's ds.

"use strict";

function nbDesignView({$, nb, project, root}){
  // The server's last answer, the working copies, and whether they differ.
  nb.dsData = null;
  nb.dsLang = null;
  nb.dsPages = null;
  nb.dsDirty = false;
  // Which block is selected on each page's board, by the page's key: a saved
  // page is keyed by its id, an unsaved one by a number of this panel's own,
  // so two pages added before a Save do not share a board.
  nb.dsSel = {};
  // Which theme, rule and page each section shows: one at a time, chosen
  // on the section's pulldown (listing every page
  // and every theme at once was the whole view scrolled past). A theme and
  // a rule by index, a page by its key; what is added is shown.
  nb.dsShow = {theme: 0, page: null};
  // The rules lists' reading state, per list (the language's, a theme's,
  // a page's): which rows are open, which are being edited, and what an
  // edited row said before Edit, for Cancel. The Briefing's shape.
  nb.dsRuleUI = {};
  // What the functions below are handed as ds: the notebook's own lookup
  // ($), its state (nb), the project, the notebook's element (root), and
  // the count that keys a page added before a Save.
  const ds = {$, nb, project, root, tmpN: 0};
  // The page an address names (#/spaces/NAME/design/KEY), "" for the list:
  // before the design is read it is the page the read lands on.
  nb.designAt = key => { if ((key || null) === nb.dsShow.page) return; nb.dsShow.page = key || null; if (nb.dsData) nbDsDrawDesign(ds); };
  $("dsWrite").onclick = () => nbDsWriteFile(ds);
  nbDsStageSections(ds);
  return {loadDesign: () => nbDsLoadDesign(ds), drawDesign: () => nbDsDrawDesign(ds)};
}

// A function below that reads the view takes its ds first, and names the
// parts of it the body reads: in the parameter for a one-line function, on
// its first line otherwise.
function nbDsRuleUI({nb}, key){ return nb.dsRuleUI[key] || (nb.dsRuleUI[key] = {editing: new Set(), open: new Set(), was: new Map()}); }
function nbDsKeyOf(p){ return p.id > 0 ? `p${p.id}` : `t${p.tmp}`; }
function nbDsPresets({nb}){ return nb.dsData?.presets || {}; }
function nbDsByKey(rows, k){ return (rows || []).find(r => r.key === k); }
function nbDsPlatformOf(ds, p){ return nbDsByKey(nbDsPresets(ds).platforms, p.platform) || (nbDsPresets(ds).platforms || [])[0]; }
function nbDsClone(o){ return JSON.parse(JSON.stringify(o)); }
// The slug a holder's rule is named under, as design.py's _slug makes it.
function nbDsHolderSlug(name){ return (name || "").toLowerCase().replace(/[^a-z0-9]+/g, "-").replace(/^-+|-+$/g, "") || "color"; }

// Nothing here changes: a locked project's notebook, or a role that reads
// the project and does not write it.
function nbDsRo({root, project}){ return root.classList.contains("ro") || !!projWriteWhy(project); }

function nbDsLoadDesign(ds){
  const {$, nb, project} = ds;
  return reading(`${project}:design`, async () => {
    try{
      const j = await getJSON(`/api/design?project=${encodeURIComponent(project)}`);
      if (j.error){ glanceBad($("dsHint"), "design", j.error); return; }
      nb.dsData = j;
    }catch(e){ glanceBad($("dsHint"), "design", e); return; }
    // A re-read never takes what is being edited: the working copies stay
    // until Save or Revert, and only the file's state and the vocabulary
    // come in fresh.
    if (!nb.dsDirty || !nb.dsLang){
      nb.dsLang = nbDsClone(nb.dsData.language);
      nb.dsPages = nbDsClone(nb.dsData.pages);
      nb.dsDirty = false;
    }
    nbDsDrawDesign(ds);
  });
}

// ---- the glance and the add bar ---------------------------------------------
// Its pages and themes as tiles, and the file's state on the line
// under them, with no pages said there while there are none.
function nbDsDrawHint(ds){
  const {$, nb} = ds;
  const f = nb.dsData?.file || {};
  const n = (nb.dsPages || []).length, t = (nb.dsLang?.themes || []).length;
  const file = nb.dsDirty ? "unsaved changes: Save in their section"
    : !f.exists ? `${f.path || "docs/design-language.md"} not written yet`
    : f.current ? `${f.path} is written and current`
    : `${f.path} is behind what is saved${nbDsRo(ds) ? "" : ": Write the file"}`;
  viewGlance($("dsHint"), [{label: n === 1 ? "page" : "pages", value: n, omit: !n},
                           {label: t === 1 ? "theme" : "themes", value: t, omit: !t}],
             esc(`${n ? "" : "no pages yet · "}${file}`));
  const w = $("dsWrite");
  w.disabled = !!nb.dsDirty;
  w.hidden = nbDsRo(ds);
  setTitle(w, nb.dsDirty ? "Save first: the file is written from what is saved"
    : "write docs/design-language.md into the space from what is saved here; a session commits it with the work");
}

function nbDsDrawAdd(ds){
  const {$} = ds;
  const P = nbDsPresets(ds);
  const plat = $("dsPlatform"), tpl = $("dsTemplate");
  const was = plat.value;
  drawHTML(plat, (P.platforms || []).map(p => `<option value="${esc(p.key)}">${esc(p.label)}</option>`).join(""));
  if (was && nbDsByKey(P.platforms, was)) plat.value = was;
  nbDsFillTemplates(ds);
}
// The templates a platform's frames allow: a phone app is not offered a
// desktop layout.
function nbDsFillTemplates(ds){
  const {$} = ds;
  const P = nbDsPresets(ds);
  const frames = nbDsByKey(P.platforms, $("dsPlatform").value)?.frames || [];
  const tpl = $("dsTemplate"), was = tpl.value;
  const rows = (P.templates || []).filter(t => frames.includes(t.frame));
  drawHTML(tpl, rows.map(t => `<option value="${esc(t.key)}">${esc(t.label)}</option>`).join(""));
  if (was && rows.some(t => t.key === was)) tpl.value = was;
}
// The add bar is drawn at the top of the Pages section on every draw,
// so it is wired then rather than once.
function nbDsWireAdd(ds){
  const {$, nb, root} = ds;
  if (!$("dsAdd")) return;
  nbDsDrawAdd(ds);
  $("dsPlatform").onchange = () => nbDsFillTemplates(ds);
  $("dsAdd").onclick = () => {
    const src = nb.dsPages.find(x => nbDsKeyOf(x) === ($("dsPageFrom")?.value || ""));
    const t = nbDsByKey(nbDsPresets(ds).templates, $("dsTemplate").value);
    if (!t && !src) return;
    const p = src
      ? {...nbDsClone(src), id: 0, tmp: ++ds.tmpN, name: "", key: ""}
      : {id: 0, tmp: ++ds.tmpN, name: "", platform: $("dsPlatform").value, template: t.key,
         frame: t.frame, blocks: nbDsClone(t.blocks), notes: ""};
    nb.dsPages.push(p);
    navPush(() => { nb.dsShow.page = nbDsKeyOf(p); });
    // The section opens on what was just added, whatever its fold said.
    sectOpen["design:pages"] = true;
    nbDsTouched(ds);
    nbDsDrawDesign(ds);
    root.querySelector(`[data-dspage="${nbDsKeyOf(p)}"] [data-dsf="name"]`)?.focus();
  };
}
// The glance's Write the file: docs/design-language.md written into the
// space from what is saved.
async function nbDsWriteFile(ds){
  const {$, nb, project} = ds;
  const b = $("dsWrite");
  busy(b, "Writing");
  try{
    const j = await postJSON("/api/design", {project, action: "write"});
    if (j.error) notify(j.error, true);
    else{
      if (nb.dsData) nb.dsData.file = j.file;
      notify(`${j.path} written into ${projLabel(project)}: the Git view shows it until a session commits it`);
    }
  }catch(e){ notify("design: " + failWords(e), true); }
  unbusy(b, "Write the file");
  nbDsDrawHint(ds);
}

// Something changed: its section's Save wakes, and the prompts follow.
function nbDsTouched(ds){
  const {nb} = ds;
  nb.dsDirty = true;
  nb.syncSave();
  nbDsDrawHint(ds);
}

// ---- drawing --------------------------------------------------------------------
function nbDsOpt(rows, cur, keyed = "key", labeled = "label"){ return optionList((rows || []).map(r => [r[keyed], r[labeled]]), cur); }
// Its editors are forms like every other: each
// field formField, its label over it.

// What each section shows, kept in range: a removed theme leaves the
// pulldown on the first one, and a page that is not there the list.
function nbDsShown(ds){
  const {nb} = ds;
  const L = nb.dsLang, S = nb.dsShow;
  S.theme = Math.min(Math.max(0, S.theme), Math.max(0, (L.themes || []).length - 1));
  if (!nb.dsPages.some(p => nbDsKeyOf(p) === S.page)) S.page = null;
  return {theme: (L.themes || [])[S.theme], page: nb.dsPages.find(p => nbDsKeyOf(p) === S.page)};
}

function nbDsDrawDesign(ds){
  const {$, nb} = ds;
  const body = $("dsBody");
  if (!nb.dsData){ drawHTML(body, skel("design")); return; }
  const sh = nbDsShown(ds);
  nb.dsRuleLists = {};
  // Patched: an edit draws the view again, and the control it was
  // made in keeps its focus, a field its caret, a fold its state. Every
  // handler below is set rather than added, the patch keeping the element.
  patch(body, nbDsPagesSection(ds, sh.page) + nbDsThemesSection(ds, sh.theme));
  wireSections(body);
  nbDsWireAdd(ds);
  nbDsWireLanguage(ds, body);
  nbDsWireThemes(ds, body, sh.theme);
  if (sh.page) nbDsWirePage(ds, body.querySelector(`[data-dspage="${nbDsKeyOf(sh.page)}"]`), sh.page);
  body.querySelectorAll("[data-dsrules]").forEach(host => {
    nbDsWireRulesList(ds, host);
    // A page of rules at a time, the one being edited always among them.
    const key = "dsrules:" + host.dataset.dsrules;
    pageReach(host, key, Math.max(0, ...[...nbDsRuleUI(ds, host.dataset.dsrules).editing].map(i => i + 1)));
    paginate(host, ":scope > details.rulerow", {key, noun: "rules"});
  });
  // A project read-only to you reads its design: what a role does not give
  // is not drawn, so every press that would change
  // it is gone, a fold's own toggle kept, and the fields stay to read,
  // dead, the pulldowns that pick what is shown live.
  // Taken away, so a project that is yours to change again gives them back.
  giveBack(body);
  if (nbDsRo(ds)){
    body.querySelectorAll("input,select:not([data-dspick]),textarea").forEach(e => takeAway(e));
    body.querySelectorAll("button").forEach(b => { if (!b.closest("summary") && !b.hasAttribute("aria-expanded")){ takeAway(b, true); b.disabled = true; } });
  }
  nbDsDrawHint(ds);
}

// A section's pulldown: which of its things is shown below it.
function nbDsPick(id, text, rows, cur, help = ""){
  return formField(id, text, `<select id="${id}" data-dspick>${nbDsOpt(rows, cur)}</select>`, {help: help});
}

// One of the language's four choices. Its first line is no choice at
// all, which is where a design starts: each
// choice carries a sentence a session holds the work to, so one that
// nobody made must say nothing.
function nbDsChoice(rows, cur){ return `<option value=""${cur ? "" : " selected"}>not chosen</option>` + nbDsOpt(rows, cur); }

// A choice that is custom is said by one of the theme's own rules, and
// names which: its text is what a session reads in the choice's place.
const DS_CUSTOM = [["font", "Type"], ["corners", "Corners"], ["density", "Space"], ["motion", "Motion"]];
function nbDsCustomCells(t, i){
  const mine = DS_CUSTOM.filter(([k]) => t[k] === "custom");
  const rules = (t.rules || []).filter(r => r.name);
  const pickRule = k => optionList([["", "no rule named"], ...rules.map(r => r.name)], (t.custom || {})[k] || "");
  return mine.map(([k, word]) =>
      formField(`dst-${i}-custom-${k}`, `${word}, by the rule`, `<select id="dst-${i}-custom-${k}" data-dstcustom="${k}">${pickRule(k)}</select>`, {help: "which of this theme's rules says it: a session reads that rule where the choice would be"}));
}

// The themes: the add bar (blank, a preset, or a copy of a theme here),
// a pulldown of them, what the language governs, and the chosen theme
// whole: its colors, its choices (type, corners, space, motion), its
// families and its rules. The first theme is the default: the app starts
// on it, and its choices and rules are the design's (the operator, 29
// Sep, folding the Design language section into the themes).
function nbDsThemesSection(ds, t){
  const {nb} = ds;
  const L = nb.dsLang, P = nbDsPresets(ds), C = P.choices || {};
  const themes = L.themes || [];
  const rows = themes.map((x, i) => ({key: String(i), label: `${x.name || "unnamed theme"} (${x.mode})${i === 0 ? ", the default" : ""}`}));
  const first = themes[0];
  const status = first ? [nbDsByKey(C.font, first.font)?.label, nbDsByKey(C.corners, first.corners)?.label].filter(Boolean).join(" · ") : "";
  const from = `<option value="" selected>blank</option><optgroup label="a preset">${nbDsOpt(P.schemes, "")}</optgroup>`
    + (themes.length ? `<optgroup label="a copy of">${themes.map((x, i) => `<option value="copy:${i}">${esc(x.name || "unnamed theme")}</option>`).join("")}</optgroup>` : "");
  const body = `
      <div class="field">${formBox({fields: [
        formField("dsThemeFrom", "Add one from", `<select id="dsThemeFrom">${from}</select>`, {help: "blank, a preset's ten colors, or a copy of a theme here, choices and rules included"})],
        foot: [`<button type="button" id="dsThemeAdd" ${themes.length >= (P.themes_max || 8) ? "disabled" : ""}>Add theme</button>`]})}</div>
      <div class="field">${formBox({fields: [
        formField("dsScope", "Governs", `<textarea id="dsScope" class="proseline" rows="1" maxlength="120">${esc(L.scope || "")}</textarea>`, {help: "what the language covers when the space is more than one product: the web app in site/", wide: true})]})}</div>
      ${themes.length ? `<div class="field">${formBox({fields: [
        nbDsPick("dsThemePick", "Theme", rows, String(nb.dsShow.theme), "each a named set of colors, dark or light, with its own type, corners, space, motion and rules; the first is the default, whose choices and rules are the design's")]})}</div>` : ""}
      ${t ? nbDsThemeBand(ds, t, nb.dsShow.theme, themes.length) : `<div class="field"><div class="hint">No theme yet. Add one, or leave it: a session that builds the space chooses the colors, the type, corners, space and motion, and puts them here.</div></div>`}`;
  return docSection("design", "themes", "Themes", `${themes.length} theme${themes.length === 1 ? "" : "s"}${status ? " · " + status : ""}`,
                    body + nb.sectBar("design:themes"));
}

// The design's rules, the Briefing's shape (nb-rules.js, drawRules): Add a
// rule first, then a row a rule, folded, its name and whether it stands
// in every briefing or arrives on its triggers, opening to be read, and
// Edit turning the row into its form. The same list serves the language's
// rules, a theme's own and a page's own: a rules
// section inside the page and the theme, following the pulldown.
function nbDsRulesList(ds, key, rules){
  const {nb} = ds;
  nb.dsRuleLists[key] = rules;
  const ui = nbDsRuleUI(ds, key);
  return `<div class="addbar ctlrow" data-add="rule"><button type="button" data-dsruleadd ${rules.length >= (nbDsPresets(ds).rules_max || 60) ? "disabled" : ""}>Add a rule</button></div>
      <div class="field" data-dsrules="${key}">${rules.map((r, i) => `
        <details class="bug chev rulerow${ui.editing.has(i) ? " editing" : ""}" data-i="${i}"${ui.editing.has(i) || ui.open.has(i) ? " open" : ""}>
          <summary>
            <span class="btitle rlNameRO">${esc(r.name || "(unnamed)")}</span>
            <span class="rlkind ${ruleCond(r) ? "cond" : ""}">${ruleCond(r) ? "on its triggers" : "every session"}</span>
          </summary>
          <div class="body">${ui.editing.has(i) ? formBox({fields: [
            formField("", "Name", `<input class="rlName" maxlength="40" autocomplete="off" spellcheck="false" placeholder="dialogs" value="${esc(r.name || "")}" aria-label="rule name">`,
              {help: "a short name the rule is known by: dialogs, tap-targets"}),
            formField("", "The rule", `<textarea class="rlText" spellcheck="false" maxlength="20000" aria-label="the rule">${esc(r.text || "")}</textarea>`, {wide: true}),
            formField("", "Files it covers", `<input class="rlPaths" autocomplete="off" spellcheck="false" placeholder="src/ui, *.css" value="${esc((r.paths || []).join(", "))}" aria-label="paths">`,
              {help: "paths or globs, comma-separated; the rule arrives when a session edits one"}),
            formField("", "Words that raise it", `<input class="rlWords" autocomplete="off" spellcheck="false" placeholder="dialog, modal" value="${esc((r.words || []).join(", "))}" aria-label="words">`,
              {help: "comma-separated; the rule arrives when a session is asked about one"})],
            state: `<span class="state">${ruleWhen(r)} · the section's Save writes it</span>`,
            foot: [`<button type="button" class="danger lead rlRm">Remove</button>`, `<button type="button" class="stop rlCancel" title="discard what was typed">Cancel</button>`]}) : `
            <div class="bfield"><label>rule</label><div class="bval rlBody">${esc(r.text || "")}</div></div>
            ${(r.paths || []).length ? `<div class="bfield rltrig"><label>files</label><div class="bval">${esc((r.paths || []).join(", "))}</div></div>` : ""}
            ${(r.words || []).length ? `<div class="bfield rltrig"><label>words</label><div class="bval">${esc((r.words || []).join(", "))}</div></div>` : ""}
            <div class="actbar macts">
              <span class="state">${ruleWhen(r)}</span>
              <button type="button" class="rlEdit">Edit</button>
              <button type="button" class="danger rlRm">Remove</button>
            </div>`}
          </div>
        </details>`).join("")}${rules.length ? "" : `<div class="fnote">No rules here yet.</div>`}</div>`;
}
// Typed into rather than redrawn, as the Briefing's are: the model changes
// under the caret and only the row's word follows; Add, Edit, Cancel and
// Remove redraw.
function nbDsWireRulesList(ds, host){
  const {nb, root} = ds;
  const key = host.dataset.dsrules, rules = nb.dsRuleLists[key], ui = nbDsRuleUI(ds, key);
  if (!rules) return;
  const split = v => v.split(/[,\s]+/).map(x => x.trim()).filter(Boolean);
  const add = host.previousElementSibling?.querySelector("[data-dsruleadd]");
  if (add) add.onclick = () => {
    ui.editing.add(rules.length);
    rules.push({name: "", text: "", words: [], paths: []});
    nbDsTouched(ds); nbDsDrawDesign(ds);
    root.querySelector(`[data-dsrules="${key}"] .rulerow[data-i="${rules.length - 1}"] .rlName`)?.focus();
  };
  host.querySelectorAll(".rulerow").forEach(row => {
    const i = +row.dataset.i, r = rules[i];
    if (!r) return;
    const typed = () => {
      const kind = row.querySelector(".rlkind");
      kind.textContent = ruleCond(r) ? "on its triggers" : "every session";
      kind.classList.toggle("cond", !!ruleCond(r));
      row.querySelector(".actbar .state").textContent = `${ruleWhen(r)} · the section's Save writes it`;
      nbDsTouched(ds);
    };
    const put = (sel, fn) => { const el = row.querySelector(sel); if (el) el.oninput = () => { fn(el.value); typed(); }; };
    put(".rlName", v => { r.name = v; row.querySelector(".rlNameRO").textContent = v.trim() || "(unnamed)"; });
    put(".rlText", v => { r.text = v; });
    put(".rlPaths", v => { r.paths = split(v); });
    put(".rlWords", v => { r.words = split(v); });
    const shift = set => new Set([...set].filter(j => j !== i).map(j => (j > i ? j - 1 : j)));
    row.querySelector(".rlRm").onclick = () => {
      rules.splice(i, 1);
      ui.editing = shift(ui.editing); ui.open = shift(ui.open);
      ui.was = new Map([...ui.was].filter(([j]) => j !== i).map(([j, v]) => [j > i ? j - 1 : j, v]));
      nbDsTouched(ds); nbDsDrawDesign(ds);
    };
    const ed = row.querySelector(".rlEdit");
    if (ed) ed.onclick = () => {
      ui.was.set(i, {...r, paths: [...(r.paths || [])], words: [...(r.words || [])]});
      ui.editing.add(i); ui.open.add(i); nbDsDrawDesign(ds);
    };
    // Back to reading it as it read before Edit; a row that never had
    // words leaves.
    const cn = row.querySelector(".rlCancel");
    if (cn) cn.onclick = () => {
      const was = ui.was.get(i); ui.was.delete(i);
      if (was) Object.assign(r, was);
      else { rules.splice(i, 1); ui.editing = shift(ui.editing); ui.open = shift(ui.open); }
      ui.editing.delete(i);
      nbDsTouched(ds); nbDsDrawDesign(ds);
    };
    const sum = row.querySelector("summary");
    if (sum) sum.onclick = e => {
      e.preventDefault();
      if (row.open) ui.open.delete(i); else ui.open.add(i);
      slideDetails(row, !foldOpen(row));
    };
  });
}

// One theme: its name and mode, its colors as rows (a name, a hex and
// what it is for), and what can be done to it. Make default moves
// another theme up to first.
function nbDsThemeBand(ds, t, i, n){
  const P = nbDsPresets(ds), C = P.choices || {};
  const modes = (P.modes || ["dark", "light"]).map(m => ({key: m, label: m[0].toUpperCase() + m.slice(1)}));
  // Its own fields, choices and families one form, Make default and Remove
  // theme at its foot; its rules; its colors one form, a group a color.
  return `<div class="dstheme" data-dstheme="${i}">
      <div class="field">${formBox({fields: [
        formField(`dst-name-${i}`, "Name", `<textarea id="dst-name-${i}" class="proseline" rows="1" maxlength="40" data-dst="name">${esc(t.name)}</textarea>`, {wide: true}),
        formField(`dst-mode-${i}`, "Mode", `<select id="dst-mode-${i}" data-dst="mode">${nbDsOpt(modes, t.mode)}</select>`),
        formField(`dst-from-${i}`, "Fill from", `<select id="dst-from-${i}" data-dst="from"><option value="">keep as they are</option>${nbDsOpt(P.schemes, "")}</select>`, {help: "replace this theme's colors with a preset's ten"}),
        formField(`dst-${i}-font`, "Type", `<select id="dst-${i}-font" data-dstchoice="font">${nbDsChoice(C.font, t.font)}</select>`),
        formField(`dst-${i}-corners`, "Corners", `<select id="dst-${i}-corners" data-dstchoice="corners">${nbDsChoice(C.corners, t.corners)}</select>`),
        formField(`dst-${i}-density`, "Space", `<select id="dst-${i}-density" data-dstchoice="density">${nbDsChoice(C.density, t.density)}</select>`),
        formField(`dst-${i}-motion`, "Motion", `<select id="dst-${i}-motion" data-dstchoice="motion">${nbDsChoice(C.motion, t.motion)}</select>`),
        ...nbDsCustomCells(t, i),
        formField(`dst-${i}-fonts`, "Families", `<textarea id="dst-${i}-fonts" class="proseline" rows="1" maxlength="200" data-dst="fonts">${esc(t.fonts || "")}</textarea>`, {help: "the exact font stacks when the choice above is not enough: Inter for text, JetBrains Mono for code", wide: true})],
        state: `<span class="state">${i === 0 ? "the default: the app starts on it" : ""}</span>`,
        foot: [`<button type="button" class="danger lead" data-dstrm title="take this theme out">Remove theme</button>`,
          i === 0 ? "" : `<button type="button" data-dstdefault title="the app starts on this theme">Make default</button>`]})}</div>
      ${docSection("design", `rules:t${i}`, "Rules", (t.rules || []).length ? `${t.rules.length}` : "none",
        `<div class="hint">${i === 0
          ? "The design's rules: what holds for the whole design and the settings cannot say. A session gets one on the turn it edits a file or is asked about a word the rule names; aerie design show NAME reads one."
          : `What holds for ${esc(t.name.trim() || "this theme")} alone. A session meets one as ${esc(nbDsHolderSlug(t.name))}/NAME.`}</div>` + nbDsRulesList(ds, `t${i}`, t.rules || (t.rules = [])), {open: true})}
      <div class="field">${lbl("", "Colors", "each a name, a hex and what it is for; a session names them the same in the code")}${formBox({cls: "dscolors",
        groups: (t.colors || []).map((c, j) => ({attrs: `data-dstc="${j}"`, fields: [
          formField(`dst-${i}-name-${j}`, "Name", `<input id="dst-${i}-name-${j}" data-dsm="name" maxlength="40" autocomplete="off" value="${esc(c.name)}">`),
          formField(`dst-${i}-hex-${j}`, "Hex", `<div class="dsc"><span class="dschip" data-style="background:${esc(c.hex)}"></span><input id="dst-${i}-hex-${j}" data-dsm="hex" maxlength="7" spellcheck="false" autocomplete="off" value="${esc(c.hex)}"></div>`),
          formField(`dst-${i}-for-${j}`, "For", `<textarea id="dst-${i}-for-${j}" class="proseline" rows="1" maxlength="120" data-dsm="means">${esc(c.means)}</textarea>`),
          `<div class="fcell fcellbtn"><button type="button" class="danger" data-dstcrm="${j}" title="take this color out">Remove</button></div>`]})),
        foot: [`<button type="button" data-dstcadd ${(t.colors || []).length >= (P.colors_max || 40) ? "disabled" : ""}>Add color</button>`]})}</div>
      ${nbDsLightHalf(t, i)}
    </div>`;
}

// The theme's other half: the same tokens for the opposite mode,
// so one name is one scheme with a dark half and a light one, and the
// app's mode switch picks the half. Started from the colors above, names
// and meanings kept, hexes to be set; removed whole.
function nbDsLightHalf(t, i){
  const other = t.mode === "light" ? "dark" : "light";
  if (!(t.light || []).length)
    return `<div class="field"><div class="actbar"><span class="state">one palette: the app has no ${other} half of ${esc(t.name.trim() || "this theme")} to switch to</span>
        <button type="button" data-dstladd ${(t.colors || []).length ? "" : "disabled"}>Add a ${other} half</button></div></div>`;
  return `<div class="field">${lbl("", `The ${other} half`, `the same tokens for ${other} mode; the app's Dark / Light switch picks the half`)}${formBox({
      groups: t.light.map((c, j) => ({attrs: `data-dstl="${j}"`, fields: [
        formField(`dstl-${i}-name-${j}`, "Name", `<input id="dstl-${i}-name-${j}" data-dslm="name" maxlength="40" autocomplete="off" value="${esc(c.name)}">`),
        formField(`dstl-${i}-hex-${j}`, "Hex", `<div class="dsc"><span class="dschip" data-style="background:${esc(c.hex)}"></span><input id="dstl-${i}-hex-${j}" data-dslm="hex" maxlength="7" spellcheck="false" autocomplete="off" value="${esc(c.hex)}"></div>`)]})),
      state: `<span class="state">${t.light.length} of ${(t.colors || []).length} tokens</span>`,
      foot: [`<button type="button" class="danger" data-dstlrm title="take the ${other} half out">Remove the ${other} half</button>`]})}</div>`;
}

// The pages: the add bar (a platform, a template, Add page), a pulldown
// of them, and the chosen one's board and fields. Shut on a new tab,
// like the language and the themes: the board is
// the big thing on this view, and it opens on what is added.
// A page's line: what it is for, its platform and how many blocks.
function nbDsPageSaid(ds, p){
  return `${p.name.trim() || "unnamed page"} · ${nbDsPlatformOf(ds, p)?.label || p.platform} · ${p.blocks.length} block${p.blocks.length === 1 ? "" : "s"}`;
}
const DS_PAGE_COLS = [{label: "Page"}, {label: "Platform", w: "minmax(0,.6fr)"}, {label: "Frame", w: "minmax(0,.6fr)"}, {label: "Blocks", w: "5rem", num: true}];
function nbDsPagesSection(ds, p){
  const {nb} = ds;
  const n = nb.dsPages.length;
  const P = nbDsPresets(ds);
  // A new page starts from a template, or as a copy of a page here (its
  // blocks, layouts, rules and notes), blank by default.
  const add = `<div class="field" data-add="design">${formBox({fields: [
        formField("dsPlatform", "Platform", `<select id="dsPlatform"></select>`, {help: "the platform the new page is for"}),
        formField("dsTemplate", "Template", `<select id="dsTemplate"></select>`, {help: "the layout the new page starts from"}),
        formField("dsPageFrom", "Or a copy of", `<select id="dsPageFrom"><option value="" selected>not a copy</option>${
          nb.dsPages.map(x => `<option value="${nbDsKeyOf(x)}">a copy of ${esc(x.name.trim() || "unnamed page")}</option>`).join("")}</select>`, {help: "a page here, its blocks, layouts, rules and notes"})],
        foot: [`<button id="dsAdd" class="primary" type="button">Add page</button>`]})}</div>`;
  // Every page a row, a press on it opening that page at an address of its
  // own; the page open, a line back to the rows over it and the page.
  const rows = nb.dsPages.map(x => `<div class="row dspagerow" data-dspagego="${nbDsKeyOf(x)}">${tblLine(DS_PAGE_COLS, [
      `<button type="button" class="namelink" title="open this page">${esc(x.name.trim() || "unnamed page")}</button>`,
      esc(nbDsPlatformOf(ds, x)?.label || x.platform), esc(P.frames?.[x.frame]?.label || x.frame || ""), String(x.blocks.length)])}</div>`).join("");
  const body = p ? `<div class="dspagehead">
        <button type="button" class="bare backbtn" data-dspageback title="back to every page">${ICON_BACK}<span>Pages</span></button>
        <span class="dim dspagesaid">${esc(nbDsPageSaid(ds, p))}</span></div>
      ${nbDsPageBody(ds, p)}`
    : add + (n ? tblWrap(DS_PAGE_COLS, rows, "dspages")
      : `<div class="field"><div class="hint">No pages yet: pick a platform and a template and press Add page.</div></div>`);
  return docSection("design", "pages", "Pages", n ? `${n} page${n === 1 ? "" : "s"}` : "none yet",
                    body + nb.sectBar("design:pages"));
}

function nbDsPageBody(ds, p){
  const {nb} = ds;
  const P = nbDsPresets(ds), key = nbDsKeyOf(p);
  const plat = nbDsPlatformOf(ds, p);
  const frames = (plat?.frames || Object.keys(P.frames || {})).map(f => ({key: f, label: P.frames?.[f]?.label || f}));
  const n = p.blocks.length;
  const sel = nb.dsSel[key];
  const b = sel != null ? p.blocks[sel] : null;
  return `<div data-dspage="${key}">
      <div class="field">${formBox({fields: [
        formField(`${key}-name`, "For", `<textarea id="${key}-name" class="proseline" rows="1" maxlength="120" data-dsf="name">${esc(p.name)}</textarea>`, {help: "what this page is for: the settings page. Applying it means applying the design there", wide: true}),
        formField(`${key}-key`, "Key", `<textarea id="${key}-key" class="proseline" rows="1" maxlength="24" data-dsf="key">${esc(p.key || "")}</textarea>`, {help: "optional: a short name of the page's own, which its rules are addressed under (settings/save). Without one they go by the whole name"}),
        formField(`${key}-plat`, "Platform", `<select id="${key}-plat" data-dsf="platform">${nbDsOpt(P.platforms, p.platform)}</select>`),
        formField(`${key}-frame`, "Frame", `<select id="${key}-frame" data-dsf="frame">${nbDsOpt(frames, p.frame)}</select>`),
        formField(`${key}-rows`, "Rows", `<input id="${key}-rows" type="number" inputmode="numeric" min="${nbDsFrameOf(ds, p.frame).rows}" max="${nbDsRowsMax(ds)}" value="${nbDsGridOf(ds, p).rows}" data-dsf="rows">`, {help: "how long the page is: the frame is one screen, and a page with more rows scrolls"})]})}</div>
      <div class="field">${nbDsBoardHtml(ds, p)}</div>
      <div class="field">${formBox({fields: [formField(`${key}-kind`, "Block", `<select id="${key}-kind" data-dsf="newkind">${nbDsOpt(P.kinds, "content")}</select>`)],
        foot: [`<button type="button" data-dsblockadd title="put a block of this kind on the board">Add block</button>`]})}</div>
      ${b ? `<div class="field" data-dsselected>${formBox({fields: [
        formField(`${key}-bkind`, "Kind", `<select id="${key}-bkind" data-dsb="kind">${nbDsOpt(P.kinds, b.kind)}</select>`),
        formField(`${key}-blabel`, "What it's for", `<textarea id="${key}-blabel" class="proseline" rows="1" maxlength="120" data-dsb="label">${esc(b.label)}</textarea>`, {help: "one line a session reads: the account menu, the list of orders", wide: true}),
        formField(`${key}-bin`, "Inside", `<select id="${key}-bin" data-dsb="in"><option value="">none</option>${p.blocks.map((o, j) => j === sel || nbDsDescends(p, j, sel) ? ""
                : `<option value="${j + 1}"${b.in === j + 1 ? " selected" : ""}>${j + 1}: ${esc(nbDsKindLabel(ds, o.kind))}${o.label ? ": " + esc(o.label.slice(0, 30)) : ""}</option>`).join("")}</select>`, {help: "the block this one is part of and stays within, drawn over it: a card in a list, a cover in a card, a pill in a bar; a block inside another can hold blocks of its own"}),
        `<div class="fcell fwide"><div class="hint">Drag a block to move it and its corner to size it; the arrow keys move a focused one, with Shift to size. A later layer draws over an earlier one.</div></div>`],
        foot: [`<button type="button" class="danger" data-dsblockrm>Remove block</button>`]})}</div>`
      : `<div class="field"><div class="hint">${n ? "Tap a block to name what it is for." : "Add a block, or start again from a template with Add page."}</div></div>`}
      ${docSection("design", `rules:${key}`, "Rules", (p.rules || []).length ? `${p.rules.length}` : "none",
        `<div class="hint">What holds for ${esc(p.name.trim() || "this page")} alone. A session meets one as ${esc(p.key || nbDsHolderSlug(p.name || `page-${p.id}`))}/NAME.</div>` + nbDsRulesList(ds, key, p.rules || (p.rules = [])), {open: true})}
      <div class="field">${formBox({fields: [formField(`${key}-notes`, "Notes", `<textarea id="${key}-notes" rows="3" maxlength="65536" data-dsf="notes">${esc(p.notes)}</textarea>`, {help: "what the blocks cannot say: what a tap does, where the data comes from", wide: true})]})}</div>
      <div class="field"><div class="actbar"><span class="state"></span>
          <button type="button" class="danger" data-dspagerm title="take this page out; Save makes it final, Revert brings it back">Remove page</button></div></div>
    </div>`;
}

// ---- the board --------------------------------------------------------------------
// What a block wears comes from the language: a bar is a surface, an action
// is the accent, the reading area is the page itself.
const DS_WEAR = {header: "panel", nav: "panel", tabs: "panel", sidebar: "panel", footer: "panel",
                 button: "accent", hero: "accent"};
// The default theme's colors by role, whatever the design calls them
// (presets.roles), falling back to the dashboard's own scheme: the board
// is painted in the language, and a theme with a "page" and a "surface"
// is still a page and a surface.
const DS_FALLBACK = {bg: "#172136", panel: "#24314b", ink: "#edf4ff", line: "#455e89", accent: "#00c1fd"};
function nbDsPaint(ds, role){
  const {nb} = ds;
  const t = (nb.dsLang.themes || [])[0];
  const names = nbDsPresets(ds).roles?.[role] || [role];
  const hit = (t?.colors || []).find(c => names.includes(c.name.toLowerCase()));
  return hit ? hit.hex : DS_FALLBACK[role];
}
function nbDsBlockStyle(ds, b){
  const wear = DS_WEAR[b.kind] || (["content", "text"].includes(b.kind) ? "bg" : "panel");
  const bg = nbDsPaint(ds, wear);
  const ink = wear === "accent" ? nbDsPaint(ds, "bg") : nbDsPaint(ds, "ink");
  return `grid-column:${b.x + 1} / span ${b.w};grid-row:${b.y + 1} / span ${b.h};`
    + `background:${bg};color:${ink};border-color:${wear === "accent" ? bg : nbDsPaint(ds, "line")}`;
}
// A frame is one screen and a page may be longer than one: its grid is
// the frame's columns by its own rows, and the board grows with them.
function nbDsRowsMax(ds){ return nbDsPresets(ds).rows_max || 60; }
function nbDsFrameOf(ds, f){ return nbDsPresets(ds).frames?.[f] || {cols: 12, rows: 8}; }
function nbDsReach(places){ return Math.max(0, ...(places || []).map(b => b.y + b.h)); }
function nbDsGridOf(ds, p){
  return {cols: nbDsFrameOf(ds, p.frame).cols,
          rows: Math.min(nbDsRowsMax(ds), Math.max(nbDsFrameOf(ds, p.frame).rows, p.rows || 0))};
}
const DS_SHAPE = {desktop: [16, 10], phone: [9, 16], landscape: [16, 9]};
function nbDsBoardHtml(ds, p){
  const {nb} = ds;
  const g = nbDsGridOf(ds, p);
  const [bw, bh] = DS_SHAPE[p.frame] || DS_SHAPE.desktop;
  const tall = g.rows > nbDsFrameOf(ds, p.frame).rows ? `aspect-ratio:${bw} / ${(bh * g.rows / nbDsFrameOf(ds, p.frame).rows).toFixed(2)};` : "";
  const key = nbDsKeyOf(p);
  // In the blocks' order, which is the drawing order: a later one draws
  // over an earlier one where they overlap, and the layers beside the
  // board are the way to one another covers.
  const inner = p.blocks.length
    ? p.blocks.map((b, i) => `<div class="dsblock${nb.dsSel[key] === i ? " on" : ""}" tabindex="0" role="button"
            data-i="${i}" data-style="${nbDsBlockStyle(ds, b)}" aria-label="${esc(nbDsKindLabel(ds, b.kind))}${b.label ? ": " + esc(b.label) : ""}">
            <b>${esc(nbDsKindLabel(ds, b.kind))}</b>${b.label ? `<span>${esc(b.label)}</span>` : ""}<i class="dsgrip" aria-hidden="true"></i></div>`).join("")
    : `<div class="dsempty">nothing on this ${esc(p.frame)} yet</div>`;
  // A page of many screens is looked at through a window of its own,
  // so the fields under the board stay in reach.
  return `<div class="dsboardrow"><div class="dsboardwrap"><div class="dsboard" data-frame="${esc(p.frame)}" role="group" aria-label="the layout of ${esc(p.name || "this page")}"
      data-style="${tall}grid-template-columns:repeat(${g.cols},1fr);grid-template-rows:repeat(${g.rows},1fr);background:${esc(nbDsPaint(ds, "bg"))};border-color:${esc(nbDsPaint(ds, "line"))}">${inner}</div></div>${nbDsLayersHtml(ds, p)}</div>`;
}
// Whether block j lies inside block i, however many parents up.
function nbDsDescends(p, j, i){
  const seen = new Set();
  for (let k = p.blocks[j]?.in; k && !seen.has(k); k = p.blocks[k - 1]?.in){
    if (k - 1 === i) return true;
    seen.add(k);
  }
  return false;
}
function nbDsDepthOf(p, i){ let d = 0; const seen = new Set(); for (let k = p.blocks[i]?.in; k && !seen.has(k); k = p.blocks[k - 1]?.in){ seen.add(k); d++; } return d; }
// The layers: one row per block, the top layer first, a child indented
// under its parent's depth, the selected one marked as its block is.
function nbDsLayersHtml(ds, p){
  const {nb} = ds;
  const key = nbDsKeyOf(p), sel = nb.dsSel[key], n = p.blocks.length;
  const rows = p.blocks.map((b, i) => [b, i]).reverse().map(([b, i]) => `<div class="dslayer${sel === i ? " on" : ""}" data-dsl="${i}" role="button" tabindex="0"
        data-style="padding-left:${10 + nbDsDepthOf(p, i) * 12}px" title="select this block${b.in ? `; inside block ${b.in}` : ""}">
        <span class="t"><b>${esc(nbDsKindLabel(ds, b.kind))}</b>${b.label ? ` <span>${esc(b.label)}</span>` : ""}</span>
        <button type="button" class="ic" data-dslup="${i}" aria-label="a layer up"${i === n - 1 ? " disabled" : ""} title="a layer up: over the one above it">▲</button>
        <button type="button" class="ic" data-dsldown="${i}" aria-label="a layer down"${i === 0 ? " disabled" : ""} title="a layer down: under the one below it">▼</button></div>`).join("");
  return `<div class="lbox dslayers" role="group" aria-label="the layers of ${esc(p.name || "this page")}, top first">${rows || `<div class="hint">no layers yet</div>`}</div>`;
}
// A layer moved up or down the stack: the block and its place on every
// frame swap with the neighbor's, and every parent number follows.
function nbDsMoveLayer(ds, p, i, dir){
  const j = i + dir;
  if (j < 0 || j >= p.blocks.length) return;
  // A child stays over its parent and a parent under its children.
  if (dir < 0 && p.blocks[i].in === j + 1) return;
  if (dir > 0 && p.blocks[j].in === i + 1) return;
  nbDsMoveTo(ds, p, i, j);
  nbDsTouched(ds); nbDsDrawDesign(ds);
}
// Block i taken out of the list and put at j: its place on every frame
// goes with it, and every parent number follows the move.
function nbDsMoveTo(ds, p, i, j){
  const {nb} = ds;
  if (i === j) return;
  const shift = arr => { const [x] = arr.splice(i, 1); arr.splice(j, 0, x); };
  shift(p.blocks);
  for (const rows of Object.values(p.layouts || {})) shift(rows);
  const at = k => k === i + 1 ? j + 1 : (i < j && k > i + 1 && k <= j + 1) ? k - 1 : (i > j && k >= j + 1 && k < i + 1) ? k + 1 : k;
  p.blocks.forEach(b => { if (b.in) b.in = at(b.in); });
  nb.dsSel[nbDsKeyOf(p)] = j;
}
function nbDsWireLayers(ds, el, p){
  const {nb} = ds;
  el.querySelectorAll("[data-dsl]").forEach(row => {
    const pick = () => { nb.dsSel[nbDsKeyOf(p)] = +row.dataset.dsl; nbDsDrawDesign(ds); };
    row.onclick = pick;
    row.onkeydown = e => { if (e.key === "Enter" || e.key === " "){ e.preventDefault(); pick(); } };
  });
  el.querySelectorAll("[data-dslup]").forEach(b => b.onclick = e => { e.stopPropagation(); if (!nbDsRo(ds)) nbDsMoveLayer(ds, p, +b.dataset.dslup, 1); });
  el.querySelectorAll("[data-dsldown]").forEach(b => b.onclick = e => { e.stopPropagation(); if (!nbDsRo(ds)) nbDsMoveLayer(ds, p, +b.dataset.dsldown, -1); });
}
function nbDsKindLabel(ds, k){ return nbDsByKey(nbDsPresets(ds).kinds, k)?.label || k; }
function nbDsRepaintBoard(ds, p){
  const {root} = ds;
  const row = root.querySelector(`[data-dspage="${nbDsKeyOf(p)}"] .dsboardrow`);
  if (row){
    row.outerHTML = nbDsBoardHtml(ds, p);
    const el = drawn(root.querySelector(`[data-dspage="${nbDsKeyOf(p)}"]`));
    nbDsWireBoard(ds, el.querySelector(".dsboard"), p);
    nbDsWireLayers(ds, el, p);
  }
  nbDsPageOption(ds, p);
}
// The page's line over it: its name, platform and count, as it is typed.
function nbDsPageOption(ds, p){
  setText(ds.root.querySelector(".dspagehead .dspagesaid"), nbDsPageSaid(ds, p));
}
// Inside the frame, two ways: a block being SIZED keeps its corner and is
// capped at the edge, a block being MOVED keeps its size and stops at the
// edge. One rule for both grew a block being sized past the bottom by
// sliding it up instead. A frame change does both, size first.
function nbDsClampBlock(b, g, sizing){
  b.x = Math.max(0, Math.min(b.x, g.cols - 1)); b.y = Math.max(0, Math.min(b.y, g.rows - 1));
  if (sizing !== false){ b.w = Math.max(1, Math.min(b.w, g.cols - b.x)); b.h = Math.max(1, Math.min(b.h, g.rows - b.y)); }
  if (!sizing){
    b.w = Math.max(1, Math.min(b.w, g.cols)); b.h = Math.max(1, Math.min(b.h, g.rows));
    b.x = Math.min(b.x, g.cols - b.w); b.y = Math.min(b.y, g.rows - b.h);
  }
}

// A block inside another stays within it: sized down to it where it is
// bigger, moved in where it reaches out.
function nbDsFitIn(b, par){
  b.w = Math.max(1, Math.min(b.w, par.w)); b.h = Math.max(1, Math.min(b.h, par.h));
  b.x = Math.max(par.x, Math.min(b.x, par.x + par.w - b.w));
  b.y = Math.max(par.y, Math.min(b.y, par.y + par.h - b.h));
}
function nbDsKidsOf(p, i){
  return p.blocks.map((b, j) => j).filter(j => j !== i && nbDsDescends(p, j, i))
    .sort((a, b) => nbDsDepthOf(p, a) - nbDsDepthOf(p, b));
}
// Block i was just moved or sized from `before`: held within its parent,
// its children carried by the move (not by a sizing) and held within
// it in turn, parents before children. Returns the indexes that moved.
function nbDsSettle(p, i, before, sizing){
  const b = p.blocks[i];
  if (b.in) nbDsFitIn(b, p.blocks[b.in - 1]);
  const dx = b.x - before.x, dy = b.y - before.y;
  const moved = [];
  for (const j of nbDsKidsOf(p, i)){
    const c = p.blocks[j];
    if (!sizing){ c.x += dx; c.y += dy; }
    nbDsFitIn(c, p.blocks[c.in - 1]);
    moved.push(j);
  }
  return moved;
}
// A page remembers where its blocks sat on each frame it has been on:
// to Phone and back to Desktop left them squeezed into the
// phone's six columns, because the clamp that fits them to the smaller
// frame was never undone. Leaving a frame keeps its layout; arriving on
// one that has a layout for these blocks takes it, and only a frame
// never visited is clamped into.
function nbDsGeometry(b){ return {x: b.x, y: b.y, w: b.w, h: b.h}; }
function nbDsToFrame(ds, p, frame){
  if (frame === p.frame) return;
  p.layouts = p.layouts || {};
  p.layouts[p.frame] = p.blocks.map(nbDsGeometry);
  p.frame = frame;
  const kept = p.layouts[frame];
  const had = Array.isArray(kept) && kept.length === p.blocks.length;
  if (had) p.blocks.forEach((b, i) => Object.assign(b, kept[i]));
  // As long as its layout there was; a frame never visited is one screen.
  p.rows = had ? Math.max(nbDsFrameOf(ds, frame).rows, nbDsReach(kept)) : nbDsFrameOf(ds, frame).rows;
  p.blocks.forEach(b => nbDsClampBlock(b, nbDsGridOf(ds, p), undefined));
  delete p.layouts[frame];
}
// A block added or taken away is added to or taken from every layout the
// page keeps, so the layouts stay about the same blocks.
function nbDsLayoutsAdd(ds, p, b){
  for (const [f, rows] of Object.entries(p.layouts || {})){
    const nb_ = nbDsGeometry(b);
    nbDsClampBlock(nb_, {cols: nbDsFrameOf(ds, f).cols, rows: Math.max(nbDsFrameOf(ds, f).rows, nbDsReach(rows))}, false);
    rows.push(nb_);
  }
}
function nbDsLayoutsRemove(p, i){
  for (const rows of Object.values(p.layouts || {})) rows.splice(i, 1);
}

function nbDsWirePage(ds, el, p){
  const {nb} = ds;
  if (!el) return;
  const key = nbDsKeyOf(p);
  const P = nbDsPresets(ds);
  // Rows are a draft like the rest: shortening a page brings its blocks
  // up into what is left, and never under the frame's one screen.
  el.querySelector('[data-dsf="rows"]').onchange = e => {
    const n = Math.round(Number(e.target.value)) || 0;
    p.rows = Math.min(nbDsRowsMax(ds), Math.max(nbDsFrameOf(ds, p.frame).rows, n));
    p.blocks.forEach(b => nbDsClampBlock(b, nbDsGridOf(ds, p), undefined));
    nbDsTouched(ds); nbDsDrawDesign(ds);
  };
  el.querySelector('[data-dsf="name"]').oninput = e => {
    p.name = e.target.value;
    nbDsPageOption(ds, p);
    nbDsTouched(ds);
  };
  el.querySelector('[data-dsf="notes"]').oninput = e => { p.notes = e.target.value; nbDsTouched(ds); };
  el.querySelector('[data-dsf="key"]').oninput = e => {
    p.key = e.target.value.toLowerCase().replace(/[^a-z0-9-]+/g, "-").replace(/^-+/, "").slice(0, 24);
    nbDsTouched(ds);
  };
  el.querySelector('[data-dsf="key"]').onchange = () => nbDsDrawDesign(ds);
  el.querySelector('[data-dsf="platform"]').onchange = e => {
    p.platform = e.target.value;
    const frames = nbDsPlatformOf(ds, p)?.frames || [];
    if (!frames.includes(p.frame)) nbDsToFrame(ds, p, frames[0] || p.frame);
    nbDsTouched(ds); nbDsDrawDesign(ds);
  };
  el.querySelector('[data-dsf="frame"]').onchange = e => {
    nbDsToFrame(ds, p, e.target.value);
    nbDsTouched(ds); nbDsDrawDesign(ds);
  };
  nbDsWireBlocks(ds, el, p, key);
  el.querySelector("[data-dspagerm]").onclick = () => {
    nb.dsPages = nb.dsPages.filter(x => x !== p);
    delete nb.dsSel[key];
    navPush(() => { nb.dsShow.page = null; });
    nbDsTouched(ds); nbDsDrawDesign(ds);
  };
  nbDsWireBoard(ds, el.querySelector(".dsboard"), p);
}

// A page's blocks: Add block, Remove block, the selected one's kind,
// parent and label, and the layers.
function nbDsWireBlocks(ds, el, p, key){
  const {nb, root} = ds;
  const grid = () => nbDsGridOf(ds, p);
  el.querySelector("[data-dsblockadd]").onclick = () => {
    const g = grid();
    const b = {kind: el.querySelector('[data-dsf="newkind"]').value, label: "",
               x: 0, y: 0, w: Math.min(4, g.cols), h: Math.min(2, g.rows)};
    // Under the last block rather than on top of the first, while there
    // is room; the finger moves it from there.
    const last = p.blocks[p.blocks.length - 1];
    if (last){ b.y = Math.min(last.y + last.h, g.rows - b.h); b.x = last.x; }
    nbDsClampBlock(b, g, false);
    p.blocks.push(b);
    nbDsLayoutsAdd(ds, p, b);
    nb.dsSel[key] = p.blocks.length - 1;
    nbDsTouched(ds); nbDsDrawDesign(ds);
    root.querySelector(`[data-dspage="${key}"] [data-dsb="label"]`)?.focus();
  };
  const set = (sel, kind, fn) => { const x = el.querySelector(sel); if (x) x["on" + kind] = fn; };
  set("[data-dsblockrm]", "click", () => nbDsRemoveBlock(ds, p));
  set('[data-dsb="kind"]', "change", e => {
    const b = p.blocks[nb.dsSel[key]]; if (!b) return;
    b.kind = e.target.value; nbDsTouched(ds); nbDsRepaintBoard(ds, p);
  });
  set('[data-dsb="in"]', "change", e => {
    const i = nb.dsSel[key], b = p.blocks[i]; if (!b) return;
    if (e.target.value) b.in = +e.target.value; else delete b.in;
    // Brought within its parent now, here and on every other frame's
    // layout, and drawn over it: a block that came before its parent in
    // the list moves to just after it.
    if (b.in){
      nbDsFitIn(b, p.blocks[b.in - 1]);
      for (const rows of Object.values(p.layouts || {})) nbDsFitIn(rows[i], rows[b.in - 1]);
      if (b.in - 1 > i) nbDsMoveTo(ds, p, i, b.in - 1);
    }
    nbDsTouched(ds); nbDsDrawDesign(ds);
  });
  nbDsWireLayers(ds, el, p);
  set('[data-dsb="label"]', "input", e => {
    const b = p.blocks[nb.dsSel[key]]; if (!b) return;
    b.label = e.target.value; nbDsTouched(ds);
    const on = el.querySelector(".dsblock.on");
    if (on){
      let s = on.querySelector("span");
      if (!s){ s = document.createElement("span"); on.insertBefore(s, on.querySelector(".dsgrip")); }
      s.textContent = b.label;
    }
  });
}

function nbDsRemoveBlock(ds, p){
  const {nb} = ds;
  const key = nbDsKeyOf(p);
  if (nb.dsSel[key] == null) return;
  const i = nb.dsSel[key];
  p.blocks.splice(i, 1);
  nbDsLayoutsRemove(p, i);
  // Its children are freed, keeping their place; the parent numbers
  // above it move down one.
  p.blocks.forEach(b => { if (b.in === i + 1) delete b.in; else if (b.in > i + 1) b.in -= 1; });
  delete nb.dsSel[key];
  nbDsTouched(ds); nbDsDrawDesign(ds);
}

// Pointer events on the board, delegated: a block moves under the finger,
// its corner sizes it, and either commits on release. Pointer rather
// than mouse events so a touch does the same thing, with touch-action
// off on the board so the page does not scroll instead.
function nbDsWireBoard(ds, board, p){
  const {nb, root} = ds;
  if (!board) return;
  const key = nbDsKeyOf(p);
  const P = nbDsPresets(ds);
  // Set rather than added, the board being kept from one draw to the next;
  // focusin has no property of its own, so its one listener calls the
  // handler this draw left on the board.
  board.onpointerdown = e => nbDsBoardPointerDown(ds, board, p, key, e);
  board.__focusIn = e => {
    const el = e.target.closest(".dsblock");
    if (el && nb.dsSel[key] !== +el.dataset.i){ nb.dsSel[key] = +el.dataset.i; nbDsDrawDesign(ds);
      root.querySelector(`[data-dspage="${key}"] .dsblock.on`)?.focus(); }
  };
  if (!board.__focusWired){ board.__focusWired = true; board.addEventListener("focusin", e => board.__focusIn?.(e)); }
  board.onkeydown = e => nbDsBoardKeyDown(ds, board, p, e);
}

// A press on the board: the first on a block selects it, and one on the
// selected block drags it, or sizes it from its corner, until release.
function nbDsBoardPointerDown(ds, board, p, key, e){
  const {nb} = ds;
  const el = e.target.closest(".dsblock");
  if (!el || nbDsRo(ds)) return;
  const i = +el.dataset.i, b = p.blocks[i];
  if (!b) return;
  if (nb.dsSel[key] !== i){ nb.dsSel[key] = i; nbDsDrawDesign(ds); return; }
  const g = nbDsGridOf(ds, p);
  const r = board.getBoundingClientRect();
  const cw = (r.width - 12) / g.cols, ch = (r.height - 12) / g.rows;
  const resize = e.target.classList.contains("dsgrip");
  const start = {x: e.clientX, y: e.clientY, bx: b.x, by: b.y, bw: b.w, bh: b.h};
  let moved = false;
  el.setPointerCapture(e.pointerId);
  el.classList.add("dragging");
  const move = ev => {
    const dx = Math.round((ev.clientX - start.x) / cw), dy = Math.round((ev.clientY - start.y) / ch);
    const before = nbDsGeometry(b);
    if (resize){ b.w = start.bw + dx; b.h = start.bh + dy; }
    else { b.x = start.bx + dx; b.y = start.by + dy; }
    nbDsClampBlock(b, g, resize);
    // Settled (held within its parent, its children carried) before it
    // is drawn, or the screen shows a place the block does not have.
    const carried = nbDsSettle(p, i, before, resize);
    el.style.cssText = nbDsBlockStyle(ds, b);
    for (const j of carried){
      const kid = board.querySelector(`.dsblock[data-i="${j}"]`);
      if (kid) kid.style.cssText = nbDsBlockStyle(ds, p.blocks[j]);
    }
    moved = moved || dx !== 0 || dy !== 0;
  };
  const up = () => {
    el.removeEventListener("pointermove", move);
    el.removeEventListener("pointerup", up);
    el.removeEventListener("pointercancel", up);
    el.classList.remove("dragging");
    if (moved){ nbDsTouched(ds); }
  };
  el.addEventListener("pointermove", move);
  el.addEventListener("pointerup", up);
  el.addEventListener("pointercancel", up);
  e.preventDefault();
}

// A key on a focused block: an arrow moves it, Shift with an arrow sizes
// it, and Delete or Backspace takes it out.
function nbDsBoardKeyDown(ds, board, p, e){
  const el = e.target.closest(".dsblock");
  if (!el || nbDsRo(ds)) return;
  const b = p.blocks[+el.dataset.i];
  if (!b) return;
  const d = {ArrowLeft: [-1, 0], ArrowRight: [1, 0], ArrowUp: [0, -1], ArrowDown: [0, 1]}[e.key];
  if (e.key === "Delete" || e.key === "Backspace"){ e.preventDefault(); nbDsRemoveBlock(ds, p); return; }
  if (!d) return;
  e.preventDefault();
  const before = nbDsGeometry(b);
  if (e.shiftKey){ b.w += d[0]; b.h += d[1]; } else { b.x += d[0]; b.y += d[1]; }
  nbDsClampBlock(b, nbDsGridOf(ds, p), e.shiftKey);
  const carried = nbDsSettle(p, +el.dataset.i, before, e.shiftKey);
  el.style.cssText = nbDsBlockStyle(ds, b);
  for (const j of carried){
    const kid = board.querySelector(`.dsblock[data-i="${j}"]`);
    if (kid) kid.style.cssText = nbDsBlockStyle(ds, p.blocks[j]);
  }
  nbDsTouched(ds);
}

// ---- the language's controls ------------------------------------------------------
function nbDsWireLanguage(ds, body){
  const {nb} = ds;
  const L = nb.dsLang;
  const sc = body.querySelector("#dsScope");
  if (sc) sc.oninput = e => { L.scope = e.target.value; nbDsTouched(ds); };
  // A page from its row, and back to the rows: each a step Back returns
  // from, the address naming the page.
  body.querySelectorAll("[data-dspagego]").forEach(r => r.onclick = () =>
    navPush(() => { nb.dsShow.page = r.dataset.dspagego; nbDsDrawDesign(ds); }));
  const back = body.querySelector("[data-dspageback]");
  if (back) back.onclick = () => navPush(() => { nb.dsShow.page = null; nbDsDrawDesign(ds); });
  paginate(body.querySelector(".tbl.dspages"), ":scope > .row", {key: "dspages", noun: "pages"});
}

// A theme from a preset is the ten colors in its hexes, named for it.
function nbDsFromScheme(P, key, name){
  const sc = nbDsByKey(P.schemes, key) || P.schemes[0];
  const light = (c => { const r = parseInt(c.slice(1, 3), 16), g = parseInt(c.slice(3, 5), 16), b = parseInt(c.slice(5, 7), 16);
    return (0.2126 * r + 0.7152 * g + 0.0722 * b) / 255 > 0.5; })(sc.colors.bg);
  return {name: name || sc.label.replace(" (light)", ""), mode: light ? "light" : "dark",
          colors: (P.tokens || []).map(x => ({name: x.key, hex: sc.colors[x.key], means: x.means}))};
}

// The themes: the pulldown that picks the one shown, Add theme, and the
// chosen one's band.
function nbDsWireThemes(ds, body, t){
  const {nb, root} = ds;
  const L = nb.dsLang, P = nbDsPresets(ds);
  const tp = body.querySelector("#dsThemePick");
  if (tp) tp.onchange = e => { nb.dsShow.theme = +e.target.value; nbDsDrawDesign(ds); };
  body.querySelector("#dsThemeAdd").onclick = () => {
    const key = body.querySelector("#dsThemeFrom").value;
    // Blank, a preset, or a copy of a theme here, choices and rules
    // included.
    let nt, base;
    if (key.startsWith("copy:")){
      const src = L.themes[+key.slice(5)];
      nt = nbDsClone(src); base = `${src.name} copy`; nt.name = base;
    } else if (key){ nt = nbDsFromScheme(P, key, ""); base = nbDsByKey(P.schemes, key)?.label || "Theme"; }
    else { nt = {name: "Theme", mode: "dark", colors: [], rules: []}; base = "Theme"; }
    const names = new Set(L.themes.map(x => x.name.toLowerCase()));
    for (let k = 2; names.has(nt.name.toLowerCase()); k++) nt.name = `${base} ${k}`;
    L.themes.push(nt);
    nb.dsShow.theme = L.themes.length - 1;
    nbDsTouched(ds); nbDsDrawDesign(ds);
    root.querySelector(`#dst-name-${L.themes.length - 1}`)?.focus();
  };
  nbDsWireThemeBand(ds, body, t);
}

// The chosen theme, its colors typed in place: its name, mode, choices
// and families, its colors and its other half, Make default and Remove
// theme.
function nbDsWireThemeBand(ds, body, t){
  const {nb, root} = ds;
  const L = nb.dsLang, P = nbDsPresets(ds);
  const band = body.querySelector("[data-dstheme]");
  if (!band || !t) return;
  const i = +band.dataset.dstheme;
  band.querySelector('[data-dst="name"]').oninput = e => {
    t.name = e.target.value; nbDsTouched(ds);
    const o = body.querySelector(`#dsThemePick option[value="${i}"]`);
    if (o) o.textContent = `${t.name || "unnamed theme"} (${t.mode})${i === 0 ? ", the default" : ""}`;
  };
  band.querySelector('[data-dst="mode"]').onchange = e => { t.mode = e.target.value; nbDsTouched(ds); nbDsDrawDesign(ds); };
  band.querySelectorAll("[data-dstchoice]").forEach(sel => sel.onchange = e => {
    const k = sel.dataset.dstchoice, was = t[k];
    t[k] = e.target.value;
    // The rule a custom choice named goes with the choice.
    if (t[k] !== "custom" && t.custom) delete t.custom[k];
    nbDsTouched(ds);
    if ((was === "custom") !== (t[k] === "custom") || i === 0) nbDsDrawDesign(ds);
  });
  band.querySelectorAll("[data-dstcustom]").forEach(sel => sel.onchange = e => {
    t.custom = t.custom || {};
    if (e.target.value) t.custom[sel.dataset.dstcustom] = e.target.value; else delete t.custom[sel.dataset.dstcustom];
    nbDsTouched(ds);
  });
  band.querySelector('[data-dst="fonts"]').oninput = e => { t.fonts = e.target.value; nbDsTouched(ds); };
  band.querySelector('[data-dst="from"]').onchange = e => {
    if (!e.target.value) return;
    const f = nbDsFromScheme(P, e.target.value, t.name);
    // An action, not a setting: the pulldown goes back to keeping the
    // colors once they are filled. Its markup always draws that first
    // line, so a patch alone would leave the pick showing.
    e.target.value = "";
    t.mode = f.mode; t.colors = f.colors; nbDsTouched(ds); nbDsDrawDesign(ds);
  };
  band.querySelectorAll("[data-dstc]").forEach(row => {
    const c = t.colors[+row.dataset.dstc]; if (!c) return;
    row.querySelector('[data-dsm="name"]').oninput = e => { c.name = e.target.value; nbDsTouched(ds); if (i === 0) nb.dsPages.forEach(p => nbDsRepaintBoard(ds, p)); };
    row.querySelector('[data-dsm="means"]').oninput = e => { c.means = e.target.value; nbDsTouched(ds); };
    row.querySelector('[data-dsm="hex"]').oninput = e => {
      const v = e.target.value.trim().toLowerCase();
      if (!/^#[0-9a-f]{6}$/.test(v)) return;
      c.hex = v; e.target.previousElementSibling.style.background = v;
      if (i === 0) nb.dsPages.forEach(p => nbDsRepaintBoard(ds, p));
      nbDsTouched(ds);
    };
    row.querySelector("[data-dstcrm]").onclick = () => { t.colors.splice(+row.dataset.dstc, 1); nbDsTouched(ds); nbDsDrawDesign(ds); };
  });
  band.querySelector("[data-dstcadd]").onclick = () => {
    t.colors.push({name: "", hex: nbDsPaint(ds, "accent"), means: ""}); nbDsTouched(ds); nbDsDrawDesign(ds);
    root.querySelector(`#dst-${i}-name-${t.colors.length - 1}`)?.focus();
  };
  const press = (sel, fn) => { const b = band.querySelector(sel); if (b) b.onclick = fn; };
  press("[data-dstladd]", () => {
    t.light = t.colors.map(c => ({name: c.name, hex: c.hex, means: c.means})); nbDsTouched(ds); nbDsDrawDesign(ds);
  });
  press("[data-dstlrm]", () => { t.light = []; nbDsTouched(ds); nbDsDrawDesign(ds); });
  band.querySelectorAll("[data-dstl]").forEach(row => {
    const c = (t.light || [])[+row.dataset.dstl]; if (!c) return;
    row.querySelector('[data-dslm="name"]').oninput = e => { c.name = e.target.value; nbDsTouched(ds); };
    row.querySelector('[data-dslm="hex"]').oninput = e => {
      const v = e.target.value.trim().toLowerCase();
      if (!/^#[0-9a-f]{6}$/.test(v)) return;
      c.hex = v; e.target.previousElementSibling.style.background = v; nbDsTouched(ds);
    };
  });
  press("[data-dstdefault]", () => {
    L.themes.splice(i, 1); L.themes.unshift(t); nb.dsShow.theme = 0; nbDsTouched(ds); nbDsDrawDesign(ds);
  });
  band.querySelector("[data-dstrm]").onclick = () => {
    L.themes.splice(i, 1); nb.dsShow.theme = 0; nbDsTouched(ds); nbDsDrawDesign(ds);
  };
}

// The view is passive by design: nothing here
// reaches into a session. A session meets the design on its own, through
// the rules the briefing names and aerie design show, and a person who wants
// it applied now copies the prompt into one.

// ---- each section's Save and Revert -------------------------
// The design is one record, but its two sections stage apart: Themes holds
// the language (its themes, choices, notes and rules), Pages the pages. A
// section's Save writes its half over what is saved of the other, and its
// Revert puts back only its own.
function nbDsSame(a, b){ return JSON.stringify(a) === JSON.stringify(b); }
function nbDsLangDirty({nb}){ return !!nb.dsData && !!nb.dsLang && !nbDsSame(nb.dsLang, nb.dsData.language); }
function nbDsPagesDirty({nb}){ return !!nb.dsData && !!nb.dsPages && !nbDsSame(nb.dsPages, nb.dsData.pages); }
// A section's Revert, or both sections' with no part named: the working
// copy back to what is saved.
function nbDsClearStaged(ds, part){
  const {nb, root} = ds;
  if (!nb.dsData) return;
  if (part !== "pages") nb.dsLang = nbDsClone(nb.dsData.language);
  if (part !== "themes"){ nb.dsPages = nbDsClone(nb.dsData.pages); nb.dsSel = {}; }
  nb.dsDirty = nbDsLangDirty(ds) || nbDsPagesDirty(ds);
  if (!root.querySelector('[data-view="design"]').hidden) nbDsDrawDesign(ds);
}
// A section's Save, or both sections' with no part named: what the notebook
// says once it is written, "" when there was nothing to write, null when
// it failed.
async function nbDsCommitStaged(ds, part){
  const {nb, project} = ds;
  const lang = part === "pages" ? nb.dsData.language : nb.dsLang;
  const pages = part === "themes" ? nb.dsData.pages : nb.dsPages;
  if (part === "themes" ? !nbDsLangDirty(ds) : part === "pages" ? !nbDsPagesDirty(ds) : !nb.dsDirty) return "";
  // The half not being saved keeps its edits only if it has any: the
  // server answers with the record normalized, and an untouched half
  // compared against that read as edited (5 Oct).
  const keepLang = part === "pages" && nbDsLangDirty(ds), keepPages = part === "themes" && nbDsPagesDirty(ds);
  let j;
  try{
    j = await postJSON("/api/design", {project, action: "save", language: lang,
                                                pages: pages.map(p => ({...p, id: p.id > 0 ? p.id : undefined}))});
  }catch(e){ notify("design: " + failWords(e), true); return null; }
  if (j.error){ notify("design: " + j.error, true); return null; }
  // The saved pages come back with their ids, and a board keyed by a
  // temporary number is keyed by its id from here.
  if (part !== "themes"){
    const sel = {};
    nb.dsPages.forEach((p, i) => {
      if (nb.dsSel[nbDsKeyOf(p)] != null && j.pages[i]) sel[`p${j.pages[i].id}`] = nb.dsSel[nbDsKeyOf(p)];
      if (nb.dsShow.page === nbDsKeyOf(p) && j.pages[i]) nb.dsShow.page = `p${j.pages[i].id}`;
    });
    nb.dsSel = sel;
  }
  nb.dsData = {...nb.dsData, language: j.language, pages: j.pages};
  if (!keepLang) nb.dsLang = nbDsClone(j.language);
  if (!keepPages) nb.dsPages = nbDsClone(j.pages);
  nb.dsDirty = nbDsLangDirty(ds) || nbDsPagesDirty(ds);
  // The file's state is a question for the server, now that what it would
  // write has changed.
  await nbDsLoadDesign(ds);
  return part === "themes" ? "the design's themes saved" : part === "pages" ? "the design's pages saved" : "design saved";
}
// What the notebook reads of the two sections: each one's stager, and the
// design's own for the leave and close questions, which counts the sections
// with edits and reverts both.
function nbDsStageSections(ds){
  const {nb} = ds;
  nb.stage("design:themes", {count: () => (nbDsLangDirty(ds) ? 1 : 0), what: () => "the edited themes",
                             save: () => nbDsCommitStaged(ds, "themes"), revert: () => nbDsClearStaged(ds, "themes")});
  nb.stage("design:pages", {count: () => (nbDsPagesDirty(ds) ? 1 : 0), what: () => "the edited pages",
                            save: () => nbDsCommitStaged(ds, "pages"), revert: () => nbDsClearStaged(ds, "pages")});
  nb.stage("design", {count: () => (nbDsLangDirty(ds) ? 1 : 0) + (nbDsPagesDirty(ds) ? 1 : 0),
                      revert: () => nbDsClearStaged(ds)});
}
