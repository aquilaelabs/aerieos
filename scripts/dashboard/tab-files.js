// The Files page (R224, the operator, 8 Nov): a machine's files under
// Machines, beside Nodes, Storage and Installed, one node picked in the
// group's header. What it reaches is the node's roots (its pools, its array,
// its shares, the old system's disks it adopted, the spaces folder a stick
// names) as a row of chips; a folder of one is a table, its rows opened
// (a folder) or previewed (a file), ticked for Download, Rename, Move and
// Delete, which puts them in the root's trash. Upload takes files picked or
// dropped on the page, streamed to the node. Administrators only.
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
    const r = await fetch("/api/files?" + flQuery());
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

const FL_COLS = [{label: "Name", w: "minmax(0,4fr)"}, {label: "Size", w: "6rem", num: true}, {label: "Modified", w: "8rem"},
                 {label: "Owner", w: "minmax(4rem,.8fr)"}, {act: true, w: "2.5rem"}];

function flSize(n){
  return n >= 1073741824 ? `${(n / 1073741824).toFixed(1)} GB` : n >= 1048576 ? `${(n / 1048576).toFixed(1)} MB`
    : n >= 1024 ? `${Math.round(n / 1024)} KB` : `${n} B`;
}

function flCrumbs(){
  const root = (fl.roots || []).find(x => x.path === flRoot);
  const parts = flPath ? flPath.split("/") : [];
  const at = (i) => parts.slice(0, i + 1).join("/");
  return `<nav class="fxcrumbs" aria-label="where in ${esc(root?.label || "the root")}">
    <button type="button" class="namelink" data-fxgo="">${esc(root?.label || flRoot)}</button>${
      parts.map((p, i) => `<span class="dim" aria-hidden="true">/</span>${i === parts.length - 1
        ? `<span class="fxhere" aria-current="page">${esc(p)}</span>`
        : `<button type="button" class="namelink" data-fxgo="${esc(at(i))}">${esc(p)}</button>`}`).join("")}</nav>`;
}

function flRows(){
  const want = flFilter.trim().toLowerCase();
  const rows = (fl.entries || []).filter(e => !want || e.name.toLowerCase().includes(want))
    .sort((a, b) => ((b.kind === "dir" || b.to_dir) - (a.kind === "dir" || a.to_dir)) || a.name.localeCompare(b.name, undefined, {numeric: true}));
  return rows;
}

function flLine(e){
  const dir = e.kind === "dir" || (e.kind === "link" && e.to_dir);
  const icon = dir ? "📁" : e.kind === "link" ? "↪" : "";
  const tick = `<input type="checkbox" class="fxtick" data-fxtick="${esc(e.name)}" aria-label="select ${esc(e.name)}"${flSel.has(e.name) ? " checked" : ""}>`;
  const name = `<span class="fxname">${tick}<button type="button" class="namelink" data-fxopen="${esc(e.name)}" data-fxdir="${dir ? 1 : ""}">${
    icon ? `<span aria-hidden="true">${icon}</span> ` : ""}${esc(e.name)}</button></span>${e.target ? `<div class="sub dim">to ${esc(e.target)}</div>` : ""}`;
  return tblLine(FL_COLS, [name, dir ? "" : esc(flSize(e.size || 0)), esc(fmtTime(e.mtime * 1000)), esc(e.owner || ""),
    dir ? "" : `<a class="btn icon" href="/api/files/read?${flQuery({path: (flPath ? flPath + "/" : "") + e.name, dl: "1"})}" download="${esc(e.name)}"
       title="Download ${esc(e.name)}" aria-label="Download ${esc(e.name)}">↓</a>`], "div", flSel.has(e.name) ? "on" : "", `data-fxrow="${esc(e.name)}"`);
}

function renderFilesInto(i){
  const d = docSurface(i, "files");
  if (!d) return;
  d.setBar("");    // the node is picked in the Machines group's header (R177)
  if (fl === null){
    d.list.innerHTML = skTpl(pageHead({facts: [["Roots", GHOST], ["Here", GHOST]]}) + docSection("files", "list", "Files", "", skRows(6)));
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
  const chips = `<div class="field"><div class="chips" data-chips="data-fxroot">${roots.map(r => `<button type="button" class="chip${r.path === flRoot ? " on" : ""}"
      data-fxroot="${esc(r.path)}" aria-pressed="${r.path === flRoot}" title="${esc(r.path)}">${esc(r.label)}</button>`).join("")}</div></div>`;
  const rows = fl.error ? [] : flRows();
  const ticked = [...flSel];
  const bar = ticked.length
    ? `<div class="actbar fxselbar"><span class="said">${ticked.length} selected</span><span class="sp"></span>
        ${ticked.length === 1 ? `<button type="button" data-fxact="rename">Rename</button>` : ""}
        <button type="button" data-fxact="move">Move</button>
        <button type="button" data-fxact="download"${ticked.some(n => (fl.entries || []).find(e => e.name === n && e.kind === "dir")) ? " disabled title=\"a folder downloads one file at a time\"" : ""}>Download</button>
        <button type="button" class="danger" data-fxact="delete">Delete</button>
        <button type="button" data-fxact="none">Clear</button></div>`
    : `<div class="actbar"><input type="search" id="flFilter" placeholder="Filter this folder" aria-label="filter this folder" value="${esc(flFilter)}" spellcheck="false" autocomplete="off">
        <span class="sp"></span><button type="button" data-fxact="mkdir">New folder</button>
        <button type="button" class="primary" data-fxact="upload"${fl.serves ? "" : " disabled"}>Upload</button>
        <input type="file" id="flPick" multiple hidden></div>`;
  const up = flUp ? `<div class="field"><div class="sub">Uploading ${esc(flUp.name)} (${flUp.i} of ${flUp.n}): ${flSize(flUp.done)} of ${flSize(flUp.size)}</div>
      <progress max="${flUp.size || 1}" value="${flUp.done}" aria-label="upload progress"></progress></div>` : "";
  const why = !fl.serves ? `<div class="field"><div class="notice warn">${esc(fl.name)}'s agent does not serve files yet: update it from the Nodes page.</div></div>`
    : fl.live === false ? `<div class="field"><div class="notice warn">${esc(fl.name)}'s agent is not dialing in, so its files cannot be read now.</div></div>` : "";
  const body = fl.error ? `<div class="field"><div class="notice bad">${esc(fl.error)}</div></div>`
    : rows.length ? tblWrap(FL_COLS, rows.map(flLine).join(""), "fxtbl") + (fl.truncated ? `<div class="sub dim">The first ${(fl.entries || []).length} are shown: this folder holds more.</div>` : "")
    : `<div class="empty">${flFilter ? "Nothing here matches the filter." : "This folder is empty."}</div>`;
  const head = pageHead({facts: [["Root", flRoot], ["Here", `${(fl.entries || []).filter(e => e.kind === "dir").length} folders, ${(fl.entries || []).filter(e => e.kind !== "dir").length} files`]]});
  paint(d.list, `<div class="fxpage" data-fxnode="${esc(flNode)}">${why}${head}${chips}${docSection("files", "list", "Files", "", `${flCrumbs()}${bar}${up}${body}`)}</div>`);
  wireFiles(d.el);
  if (rows.length > 120) paginate(d.el.querySelector(".fxtbl"), ".tline", {key: `fx:${flNode}:${flRoot}:${flPath}`, noun: "items"});
}

function flFull(name){ return (flPath ? flPath + "/" : "") + name; }

async function flPost(body){
  const j = await (await postJSON("/api/files", {node: flNode, root: flRoot, ...body})).json().catch(() => ({error: "no answer"}));
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
      a.href = "/api/files/read?" + flQuery({path: flFull(n), dl: "1"}); a.download = n;
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
      x.open("POST", "/api/files/upload?" + new URLSearchParams({node, root, path, name: file.name, ...(replace ? {replace: "1"} : {})}));
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
  const src = "/api/files/read?" + flQuery({path: flFull(name)});
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
  m.innerHTML = `<div class="box"><h3>${esc(name)}</h3><div class="sub dim">${esc(flSize(e.size || 0))}, ${esc(fmtTime((e.mtime || 0) * 1000))}</div>
    <div class="fxbody">${body}</div>
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
