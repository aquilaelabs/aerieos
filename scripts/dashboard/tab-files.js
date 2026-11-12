// The Files page (R224, the operator, 8 Nov): a machine's files under
// Machines, beside Nodes, Storage and Installed, one node picked in the
// group's header. Laid out as a file explorer is (the operator, 12 Nov):
// the places it reaches down the left (the node's roots: its pools, its
// array, its shares, the old system's disks it adopted, the spaces folder a
// stick names; each by its name and its kind in words, Trash last), and
// beside them one bar (where you are as a breadcrumb, a filter, New folder
// and Upload) over the folder's listing. A row is opened (a folder) or
// previewed (a file), ticked for Download, Rename, Move and Delete, which
// puts it in the place's trash. Upload takes files picked or dropped on
// the page, streamed to the node. Administrators only.
//
// Chrome from docSurface(); the hard rules are uniform.mjs's. Loaded
// before the page's own script, so everything here is a declaration.

"use strict";

let fl = null, flNode = "", flRoot = "", flPath = "", flRev = 0, flSeq = 0, flFilter = "";
const flSel = new Set();          // the names ticked in the folder on show
let flUp = null;                  // {name, done, size, i, n} while files go up

function openFilesTab(){
  openTab({kind: "files", arg: "__files", label: "Files"});
}

// The node the page opens on: the one it showed last, else the first.
function flPick(){
  const live = (nodesList || []).filter(n => n.kind === "agent" && n.state !== "retired");
  let want = flNode;
  if (!live.some(n => n.id === want)){
    try{ want = localStorage.getItem("bb.filenode") || ""; }catch(e){ want = ""; }
  }
  if (!live.some(n => n.id === want)) want = live[0]?.id || "";
  if (want !== flNode){ flNode = want; flRoot = ""; flPath = ""; flSel.clear(); }
  return live.find(n => n.id === want) || null;
}

function flQuery(extra = {}){
  return new URLSearchParams({node: flNode, root: flRoot, path: flPath, ...extra}).toString();
}

async function loadFiles(){
  const asked = ++flSeq;
  if (nodesList === null || nodesStale) await loadNodes();
  if (asked !== flSeq) return;
  if (!flPick()){
    fl = {nonode: true};
    flRev++; drawPanes();
    return;
  }
  const node = flNode, root = flRoot, path = flPath;
  try{
    const r = await fetch("/api/node-files?" + flQuery());
    const got = await r.json();
    if (asked !== flSeq) return;
    if (!r.ok) throw new Error(got.error || "HTTP " + r.status);
    // A root no longer there (a pool exported) gives way to the first one.
    if (!root && got.roots?.length){ flRoot = got.roots[0].path; flPath = ""; return loadFiles(); }
    if (root && !(got.roots || []).some(x => x.path === root)){ flRoot = ""; flPath = ""; return loadFiles(); }
    fl = {...got, at: {node, root, path}};
  }catch(e){
    if (asked !== flSeq) return;
    fl = {error: failWords(e)};
  }
  flRev++;
  drawPanes();
}

function flGo(root, path){
  flRoot = root; flPath = path.replace(/^\/+|\/+$/g, ""); flSel.clear(); flFilter = "";
  loadFiles();
}

const FL_COLS = [{label: "Name", w: "minmax(0,1fr)"}, {label: "Size", w: "6rem", num: true}, {label: "Modified", w: "8.5rem"},
                 {act: true, w: "2.5rem"}];
// A place's trash folder, which its listing leaves out and Trash opens.
const FL_TRASH = ".aerieos-trash";
// The page's own pictures, in the stroke every icon here is drawn in.
const FL_ICON = {
  dir: `<svg class="fxic" viewBox="0 0 16 16" aria-hidden="true"><path d="M1.8 4h4.2l1.4 1.7h6.8v7H1.8z"/></svg>`,
  file: `<svg class="fxic" viewBox="0 0 16 16" aria-hidden="true"><path d="M4 1.8h5.1l2.9 3v9.4H4z"/><path d="M9.1 1.8v3h2.9"/></svg>`,
  link: `<svg class="fxic" viewBox="0 0 16 16" aria-hidden="true"><path d="M4 12 12 4"/><path d="M6.6 4H12v5.4"/></svg>`,
  place: `<svg class="fxic" viewBox="0 0 16 16" aria-hidden="true"><rect x="2" y="3.6" width="12" height="8.8" rx="1.4"/><path d="M2 8.9h12"/><path d="M11 10.7h.9"/></svg>`,
  trash: `<svg class="fxic" viewBox="0 0 16 16" aria-hidden="true"><path d="M2.8 4.6h10.4"/><path d="M6.3 4.6V3h3.4v1.6"/><path d="M4.2 4.6l.6 8.6h6.4l.6-8.6"/></svg>`,
};

// A place as a person reads it: its name, and its kind in words (the
// design's files rule: never a path alone; the path is its title).
function flPlace(r){
  const m = String(r.label || "").match(/^(.*?)\s*\(([^)]*)\)$/);
  return {name: m ? m[1] : r.label || r.path, kind: m ? m[2] : {pool: "pool", array: "array", spaces: "spaces", share: "share", mount: "mount", adopted: "adopted"}[r.kind] || ""};
}
// When a file was changed, short: the day and the time this year, the day
// and the year before it.
function flWhen(sec){
  const t = new Date(sec * 1000), now = new Date();
  return fmtTime(t.getTime(), t.getFullYear() === now.getFullYear() ? {day: "numeric", month: "short", hour: "2-digit", minute: "2-digit"}
                                                                : {day: "numeric", month: "short", year: "numeric"});
}
const flInTrash = () => flPath === FL_TRASH || flPath.startsWith(FL_TRASH + "/");
// A place's trash keeps each thing under a stamped name (the day and time
// it was deleted, then its own name) beside a note of where it was: the
// page shows the name it had and when it went, and never the notes.
const FL_NOTE = ".aerieos-from", FL_STAMP = /^(\d{4})(\d{2})(\d{2})-(\d{2})(\d{2})(\d{2})-/;
const flTrashTop = () => flPath === FL_TRASH;
function flShown(name){ return flTrashTop() ? name.replace(FL_STAMP, "") : name; }
function flDeleted(name){
  const m = flTrashTop() && name.match(FL_STAMP);
  return m ? Date.UTC(+m[1], +m[2] - 1, +m[3], +m[4], +m[5], +m[6]) / 1000 : 0;
}

function flSize(n){
  return n >= 1073741824 ? `${(n / 1073741824).toFixed(1)} GB` : n >= 1048576 ? `${(n / 1048576).toFixed(1)} MB`
    : n >= 1024 ? `${Math.round(n / 1024)} KB` : `${n} B`;
}

function flCrumbs(){
  const root = (fl.roots || []).find(x => x.path === flRoot);
  const parts = flPath ? flPath.split("/") : [];
  const at = (i) => parts.slice(0, i + 1).join("/");
  const said = (p, i) => i === 0 && p === FL_TRASH ? "Trash" : p;
  const here = root ? flPlace(root).name : flRoot;
  return `<nav class="fxcrumbs" aria-label="where in ${esc(here)}">${parts.length
    ? `<button type="button" class="namelink" data-fxgo="">${esc(here)}</button>` : `<span class="fxhere" aria-current="page">${esc(here)}</span>`}${
      parts.map((p, i) => `<span class="fxsep" aria-hidden="true">›</span>${i === parts.length - 1
        ? `<span class="fxhere" aria-current="page">${esc(said(p, i))}</span>`
        : `<button type="button" class="namelink" data-fxgo="${esc(at(i))}">${esc(said(p, i))}</button>`}`).join("")}</nav>`;
}

function flRows(){
  const want = flFilter.trim().toLowerCase();
  // A place's trash is reached from Trash, never listed among its folders.
  const rows = (fl.entries || []).filter(e => !(flPath === "" && e.name === FL_TRASH) && !(flTrashTop() && e.name.endsWith(FL_NOTE))
                                              && (!want || flShown(e.name).toLowerCase().includes(want)))
    .sort((a, b) => ((b.kind === "dir" || b.to_dir) - (a.kind === "dir" || a.to_dir)) || a.name.localeCompare(b.name, undefined, {numeric: true}));
  return rows;
}

function flLine(e){
  const dir = e.kind === "dir" || (e.kind === "link" && e.to_dir);
  const tick = `<input type="checkbox" class="fxtick" data-fxtick="${esc(e.name)}" aria-label="select ${esc(e.name)}"${flSel.has(e.name) ? " checked" : ""}>`;
  const name = `<span class="fxname">${tick}<button type="button" class="namelink" data-fxopen="${esc(e.name)}" data-fxdir="${dir ? 1 : ""}">${
    FL_ICON[e.kind === "link" ? "link" : dir ? "dir" : "file"]}<span class="fxn">${esc(flShown(e.name))}</span></button></span>${
    e.target ? `<div class="sub dim">to ${esc(e.target)}</div>` : ""}`;
  const when = esc(flWhen(flDeleted(e.name) || e.mtime));
  // On a phone a row is one line: its name, and at its right a file's size
  // or a folder's day (.fxphone, which a desk does not draw).
  return tblLine(FL_COLS, [name, dir ? `<span class="fxphone">${when}</span>` : esc(flSize(e.size || 0)), when,
    dir ? "" : `<a class="btn icon" href="/api/node-files/read?${flQuery({path: (flPath ? flPath + "/" : "") + e.name, dl: "1"})}" download="${esc(e.name)}"
       title="Download ${esc(e.name)}" aria-label="Download ${esc(e.name)}">↓</a>`], "div", flSel.has(e.name) ? "on" : "",
    `data-fxrow="${esc(e.name)}"${e.owner ? ` title="owned by ${esc(e.owner)}"` : ""}`);
}

// The places column: every root by its name and kind, the one on show
// marked, and its trash last.
function flPlaces(roots){
  return `<nav class="fxplaces" aria-label="places on ${esc(fl.name || "this node")}"><div class="fxphead">Places</div>${roots.map(r => {
    const p = flPlace(r), on = r.path === flRoot && !flInTrash();
    return `<button type="button" class="fxplace${on ? " on" : ""}" data-fxroot="${esc(r.path)}" aria-pressed="${on}" title="${esc(r.path)}">${
      FL_ICON.place}<span class="fxpname">${esc(p.name)}</span>${p.kind ? `<span class="fxpkind">${esc(p.kind)}</span>` : ""}</button>`; }).join("")}
    <button type="button" class="fxplace fxtrash${flInTrash() ? " on" : ""}" data-fxgo="${FL_TRASH}" aria-pressed="${flInTrash()}"
      title="what was deleted from ${esc(flPlace((roots.find(r => r.path === flRoot)) || {label: flRoot}).name)}">${FL_ICON.trash}<span class="fxpname">Trash</span></button></nav>`;
}

function renderFilesInto(i){
  const d = docSurface(i, "files");
  if (!d) return;
  d.setBar("");    // the node is picked in the Machines group's header (R177)
  if (fl === null){
    // As it waits, the page it will be: the places, the bar and the rows.
    d.list.innerHTML = skTpl(`<div class="fxpage"><div class="fxcols"><nav class="fxplaces"><div class="fxphead">Places</div>${
      [GHOST, GHOST, GHOST].map(g => `<span class="fxplace">${FL_ICON.place}<span class="fxpname">${g}</span></span>`).join("")}</nav>
      <div class="fxmain"><div class="fxbar"><nav class="fxcrumbs"><span class="fxhere">${GHOST}</span></nav></div>${skRows(6)}</div></div></div>`);
    if (!flSeq) loadFiles();
    return;
  }
  if (fl.nonode){
    d.list.innerHTML = noNodeYet("a node's disks, pools and shares are browsed here", "fxnone");
    return;
  }
  if (fl.error && !fl.roots){
    paint(d.list, `<div class="field"><div class="notice bad">${esc("could not read the files: " + fl.error)}</div></div>`);
    return;
  }
  const roots = fl.roots || [];
  if (!roots.length){
    paint(d.list, `<div class="empty">${esc(fl.name || "This node")} has no pool, array or share to browse. Make one on the Storage page, and its files show here.</div>`);
    return;
  }
  const rows = fl.error ? [] : flRows();
  const ticked = [...flSel], trash = flInTrash();
  // One bar over the listing: where you are at its left, and at its right
  // the filter and the folder's two actions, or what the ticked rows take.
  const right = ticked.length
    ? `<div class="actbar fxselbar"><span class="said">${ticked.length} selected</span>
        ${ticked.length === 1 && !trash ? `<button type="button" data-fxact="rename">Rename</button>` : ""}
        <button type="button" data-fxact="move">${flTrashTop() ? "Put back" : "Move"}</button>
        <button type="button" data-fxact="download"${ticked.some(n => (fl.entries || []).find(e => e.name === n && e.kind === "dir")) ? " disabled title=\"a folder downloads one file at a time\"" : ""}>Download</button>
        ${trash ? "" : `<button type="button" class="danger" data-fxact="delete">Delete</button>`}
        <button type="button" data-fxact="none">Clear</button></div>`
    : `<input type="search" id="flFilter" class="flfilter" placeholder="Filter" aria-label="filter this folder" value="${esc(flFilter)}" spellcheck="false" autocomplete="off">
        ${trash ? "" : `<div class="actbar"><button type="button" data-fxact="mkdir">New folder</button>
        <button type="button" class="primary" data-fxact="upload"${fl.serves ? "" : " disabled"}>Upload</button>
        <input type="file" id="flPick" multiple hidden></div>`}`;
  const bar = `<div class="fxbar">${flCrumbs()}<div class="fxbarend">${right}</div></div>`;
  const up = flUp ? `<div class="fxnote"><div class="sub">Uploading ${esc(flUp.name)} (${flUp.i} of ${flUp.n}): ${flSize(flUp.done)} of ${flSize(flUp.size)}</div>
      <progress max="${flUp.size || 1}" value="${flUp.done}" aria-label="upload progress"></progress></div>` : "";
  const why = !fl.serves ? `<div class="field"><div class="notice warn">${esc(fl.name)}'s agent does not serve files yet: update it from the Nodes page.</div></div>`
    : fl.live === false ? `<div class="field"><div class="notice warn">${esc(fl.name)}'s agent is not dialing in, so its files cannot be read now.</div></div>` : "";
  const shown = (fl.entries || []).filter(e => !(flPath === "" && e.name === FL_TRASH) && !(flTrashTop() && e.name.endsWith(FL_NOTE)));
  const nd = shown.filter(e => e.kind === "dir").length, nf = shown.length - nd;
  const count = `${nd} folder${nd === 1 ? "" : "s"}, ${nf} file${nf === 1 ? "" : "s"}`;
  const body = fl.error ? `<div class="fxnote"><div class="notice bad">${esc(fl.error)}</div></div>`
    : rows.length ? tblWrap(flTrashTop() ? FL_COLS.map(c => c.label === "Modified" ? {...c, label: "Deleted"} : c) : FL_COLS, rows.map(flLine).join(""), "fxtbl")
    : `<div class="fxempty">${flFilter ? "Nothing here matches the filter." : trash ? "Nothing has been deleted from this place." : "This folder is empty."}</div>`;
  const foot = fl.error ? "" : `<div class="fxfoot">${flTrashTop() ? "What was deleted from this place. Put back returns what is ticked to where it was. " : ""}${
    count}${fl.truncated ? `; the first ${(fl.entries || []).length} are shown, and this folder holds more` : ""}</div>`;
  paint(d.list, `<div class="fxpage" data-fxnode="${esc(flNode)}">${why}<div class="fxcols">${flPlaces(roots)}<div class="fxmain">${bar}${up}${body}${foot}</div></div></div>`);
  wireFiles(d.el);
  if (rows.length > 120) paginate(d.el.querySelector(".fxtbl"), ".tline", {key: `fx:${flNode}:${flRoot}:${flPath}`, noun: "items"});
}

function flFull(name){ return (flPath ? flPath + "/" : "") + name; }

async function flPost(body){
  const j = await (await postJSON("/api/node-files", {node: flNode, root: flRoot, ...body})).json().catch(() => ({error: "no answer"}));
  if (j.error) notify(j.error, true);
  return !j.error;
}

function wireFiles(root){
  wireSections(root);
  root.querySelectorAll("[data-fxroot]").forEach(b => b.onclick = () => flGo(b.dataset.fxroot, ""));
  root.querySelectorAll("[data-fxgo]").forEach(b => b.onclick = () => flGo(flRoot, b.dataset.fxgo));
  root.querySelectorAll("[data-fxopen]").forEach(b => b.onclick = () => b.dataset.fxdir ? flGo(flRoot, flFull(b.dataset.fxopen)) : flPreview(b.dataset.fxopen));
  root.querySelectorAll("[data-fxtick]").forEach(c => c.onchange = () => {
    c.checked ? flSel.add(c.dataset.fxtick) : flSel.delete(c.dataset.fxtick);
    flRev++; drawPanes();
  });
  const f = root.querySelector("#flFilter");
  if (f) f.oninput = () => { flFilter = f.value; flRev++; drawPanes(); requestAnimationFrame(() => {
    const g = document.querySelector("#flFilter"); if (g){ g.focus(); g.setSelectionRange(g.value.length, g.value.length); } }); };
  const pick = root.querySelector("#flPick");
  if (pick) pick.onchange = () => { flUpload([...pick.files]); pick.value = ""; };
  root.querySelectorAll("[data-fxact]").forEach(b => b.onclick = () => pressing(b, () => flAct(b.dataset.fxact, root)));
  const page = root.querySelector(".fxpage");
  if (page && !page.__drop){
    page.__drop = true;
    page.addEventListener("dragover", e => { if (e.dataTransfer?.types?.includes("Files")){ e.preventDefault(); page.classList.add("drop"); } });
    page.addEventListener("dragleave", e => { if (e.target === page) page.classList.remove("drop"); });
    page.addEventListener("drop", e => { e.preventDefault(); page.classList.remove("drop"); flUpload([...(e.dataTransfer?.files || [])]); });
  }
}

async function flAct(what, root){
  const ticked = [...flSel];
  if (what === "none"){ flSel.clear(); flRev++; drawPanes(); return; }
  if (what === "upload"){ root.querySelector("#flPick")?.click(); return; }
  if (what === "mkdir"){
    const name = await askText("New folder", {verb: "Make folder", label: "Name"});
    if (name && await flPost({action: "mkdir", path: flPath, name: name.trim()})) loadFiles();
    return;
  }
  if (what === "download"){
    for (const n of ticked){
      const a = document.createElement("a");
      a.href = "/api/node-files/read?" + flQuery({path: flFull(n), dl: "1"}); a.download = n;
      document.body.appendChild(a); a.click(); a.remove();
      await new Promise(r => setTimeout(r, 300));
    }
    return;
  }
  if (what === "rename"){
    const was = ticked[0];
    const name = await askText(`Rename ${was}`, {value: was, verb: "Rename", label: "New name"});
    if (!name || name.trim() === was) return;
    if (await flPost({action: "rename", path: flFull(was), dest: flFull(name.trim())})){ flSel.clear(); loadFiles(); }
    return;
  }
  if (what === "move" && flTrashTop()){
    // Back to where each was, which its note says; one whose note is gone
    // is put at the place's top.
    for (const n of ticked){
      let was = "";
      try{
        const r = await fetch("/api/node-files/read?" + flQuery({path: flFull(n + FL_NOTE)}));
        if (r.ok) was = String((await r.json()).from || "");
      }catch(e){ was = ""; }
      const dest = (was && !was.startsWith("..") ? was : flShown(n)).replace(/^\/+|\/+$/g, "");
      if (!await flPost({action: "rename", path: flFull(n), dest})) break;
      notify(`${flShown(n)} is back at ${dest}`);
    }
    flSel.clear(); loadFiles();
    return;
  }
  if (what === "move"){
    const to = await askText(`Move ${ticked.length === 1 ? ticked[0] : ticked.length + " items"} to which folder?\n\nA folder of ${(fl.roots || []).find(x => x.path === flRoot)?.label || flRoot}, from its top, as a/b. Empty is its top.`,
      {value: flPath, verb: "Move", label: "Folder"});
    if (to === null) return;
    const dest = to.trim().replace(/^\/+|\/+$/g, "");
    for (const n of ticked){
      if (!await flPost({action: "rename", path: flFull(n), dest: (dest ? dest + "/" : "") + n})) break;
    }
    flSel.clear(); loadFiles();
    return;
  }
  if (what === "delete"){
    if (!await askYes(`Delete ${ticked.length === 1 ? ticked[0] : ticked.length + " items"}?\n\nThey go to this root's trash folder, .aerieos-trash, with a note of where each was, and stay there until somebody empties it.`,
        {verb: "Delete", danger: true})) return;
    for (const n of ticked){
      if (!await flPost({action: "delete", path: flFull(n)})) break;
    }
    flSel.clear(); loadFiles();
  }
}

// Files sent one after another, each streamed as the request's body with
// its progress; a name already there is asked about first.
async function flUpload(list){
  if (!list.length || flUp) return;
  const node = flNode, root = flRoot, path = flPath;
  const there = new Set((fl?.entries || []).map(e => e.name));
  for (const [i, file] of list.entries()){
    let replace = false;
    if (there.has(file.name)){
      if (!await askYes(`Replace ${file.name}?\n\nA file of that name is in this folder already.`, {verb: "Replace", danger: true})) continue;
      replace = true;
    }
    flUp = {name: file.name, done: 0, size: file.size, i: i + 1, n: list.length};
    flRev++; drawPanes();
    const err = await new Promise(resolve => {
      const x = new XMLHttpRequest();
      x.open("POST", "/api/node-files/upload?" + new URLSearchParams({node, root, path, name: file.name, ...(replace ? {replace: "1"} : {})}));
      x.upload.onprogress = e => { if (flUp){ flUp.done = e.loaded; flRev++; drawPanes(); } };
      x.onload = () => { let j = {}; try{ j = JSON.parse(x.responseText); }catch(e){ /* not JSON */ } resolve(x.status === 200 ? "" : j.error || "HTTP " + x.status); };
      x.onerror = () => resolve("the upload stopped");
      x.send(file);
    });
    if (err){ notify(`${file.name}: ${err}`, true); break; }
  }
  flUp = null;
  if (flNode === node && flRoot === root && flPath === path) loadFiles(); else { flRev++; drawPanes(); }
}

// A file shown over the page: an image, a video, a sound or a PDF as
// itself; anything else as its first 256 KB of text, and a Download.
const FL_SHOWN = {img: /\.(png|jpe?g|gif|webp|avif|bmp|ico)$/i, video: /\.(mp4|webm|mov|m4v)$/i, audio: /\.(mp3|m4a|ogg|wav|flac)$/i, pdf: /\.pdf$/i};
async function flPreview(name){
  const e = (fl?.entries || []).find(x => x.name === name) || {};
  const src = "/api/node-files/read?" + flQuery({path: flFull(name)});
  const kind = Object.keys(FL_SHOWN).find(k => FL_SHOWN[k].test(name)) || "text";
  const m = document.createElement("div");
  m.className = "modal fxview";
  m.setAttribute("role", "dialog");
  m.setAttribute("aria-modal", "true");
  m.setAttribute("aria-label", name);
  m.hidden = true;
  const body = kind === "img" ? `<img src="${esc(src)}" alt="${esc(name)}">`
    : kind === "video" ? `<video src="${esc(src)}" controls preload="metadata"></video>`
    : kind === "audio" ? `<audio src="${esc(src)}" controls preload="metadata"></audio>`
    : kind === "pdf" ? `<iframe src="${esc(src)}" title="${esc(name)}"></iframe>`
    : `<pre class="fxtext">${skRows(4)}</pre>`;
  m.innerHTML = `<div class="box"><h3>${esc(name)}</h3><div class="field"><div class="sub dim">${esc(flSize(e.size || 0))}, changed ${esc(fmtTime((e.mtime || 0) * 1000))}${e.owner ? `, owned by ${esc(e.owner)}` : ""}</div></div>
    <div class="field fxbody">${body}</div>
    <div class="foot"><span class="sp"></span><a class="btn" href="${esc(src)}&dl=1" download="${esc(name)}">Download</a><button type="button" class="primary" data-fxclose>Close</button></div></div>`;
  document.body.appendChild(m);
  armModal(m);
  const done = () => { m.hidden = true; setTimeout(() => m.remove(), 400); };
  m.onclick = ev => { if (ev.target === m) done(); };
  m.querySelector("[data-fxclose]").onclick = done;
  m.hidden = false;
  requestAnimationFrame(() => m.querySelector("[data-fxclose]")?.focus());
  if (kind !== "text") return;
  const pre = m.querySelector(".fxtext");
  try{
    const ctl = new AbortController();
    const r = await fetch(src, {signal: ctl.signal});
    if (!r.ok){ const j = await r.json().catch(() => ({})); throw new Error(j.error || "HTTP " + r.status); }
    const reader = r.body.getReader(), parts = [];
    let got = 0;
    while (got < 262144){
      const {done: end, value} = await reader.read();
      if (end) break;
      parts.push(value); got += value.length;
    }
    ctl.abort();
    const bytes = new Uint8Array(got);
    let at = 0;
    for (const p of parts){ bytes.set(p.subarray(0, Math.min(p.length, got - at)), at); at += p.length; if (at >= got) break; }
    const binary = bytes.subarray(0, 4096).some(b => b === 0);
    pre.textContent = binary ? "This file is not text: Download it to open it." : new TextDecoder().decode(bytes.subarray(0, 262144))
      + ((e.size || 0) > 262144 ? "\n\n(the first 256 KB of it: Download it for the whole)" : "");
  }catch(err){
    if (err.name !== "AbortError") pre.textContent = "Could not read it: " + failWords(err);
  }
}
