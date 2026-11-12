// The notebook's Sessions view: your own conversations on this project,
// newest first, each to go on with, read here, or keep as a text file (the
// operator, 22 Oct: out of Profile and into the project they were had on,
// and any one of them resumed, where the Claude button resumes the last). Beside
// Overview in the Overview group. Only the signed-in account's: the
// controller lists them (transcripts.mine), never another account's.
// One classic script beside index.html, the shape tab-*.js has (docs/nodes.md
// §13): same page, same global scope, one file per notebook view (R60).
//
// A factory rather than a script that runs: makeNotebook calls it per
// notebook with the notebook's element lookup, its state object and its
// project, and takes back the one function the rest of the notebook calls.

"use strict";

// One conversation's row, the Artifacts view's shape so the two lists read
// the same: when, its size, the first thing you said, Resume, Read and
// Download, and behind its ⋯ Make visible (to every session on the project)
// and Delete. An anchor for the download, since a download is a link the
// browser saves. Its time is said once, as how long ago, the date and time
// on its title (the sweep, 7 Nov: both read as the same fact twice). Another
// account's, made visible, is read and downloaded
// only, with whose it is.
//
// A conversation is named by the label its person gave it (R236, the
// operator, 12 Nov), its first words under that, and by its first words
// alone where it has none; its note is a line under them, and one kept past
// its agent's own cleanup says so. Edit on the row swaps its label, its
// note and Keep in, as a row that opens does (rows-you-open); `editing` is
// the id of the one whose fields are in.
function convForm(r){
  return `<div class="memadd cvform ctlrow" data-cvform="${esc(r.id)}">
      ${lbl("cvLabel", "Label", "the name this conversation is listed and picked by, in place of its first words")}
      <input id="cvLabel" class="cvLabel" maxlength="60" autocomplete="off" value="${esc(r.label || "")}" placeholder="${esc((r.first || "what it was about").slice(0, 60))}">
      ${lbl("cvNote", "Note", "anything to remember about it: where it left off, what to do next")}
      <textarea id="cvNote" class="cvNote" maxlength="500" rows="3" spellcheck="true">${esc(r.note || "")}</textarea>
      <label class="ndcap"><input type="checkbox" class="cvKeep"${r.kept ? " checked" : ""}${r.gone ? " disabled" : ""}> Keep a copy on the controller, past its agent's own cleanup</label>
      ${r.gone ? `<div class="sub">The kept copy is the only one left of it: Delete removes it.</div>` : ""}
      <div class="actbar">
        <button type="button" class="stop" data-cvcancel>Cancel</button>
        <button type="button" class="primary" data-cvsave="${esc(r.id)}">Save</button></div>
    </div>`;
}

function convRows(project, rows, theirs = false, editing = ""){
  const size = b => b >= 1048576 ? `${(b / 1048576).toFixed(1)} MB` : `${Math.max(1, Math.round(b / 1024))} KB`;
  // The stamps in the text are written in this browser's zone, the one the
  // times on this page are in, so the log and the page agree.
  const tz = userTZ() || Intl.DateTimeFormat().resolvedOptions().timeZone || "";
  return `<div class="cvlogs">${rows.map(r => !theirs && editing === r.id ? `
    <div class="artrow cvediting" data-cvrow="${esc(r.id)}"><div class="grow">${convForm(r)}</div></div>` : `
    <div class="artrow" data-cvrow="${esc(r.id)}">
      <div class="grow">
        <div class="top">${r.label ? `<b class="cvlabel">${esc(r.label)}</b> <span class="dim" title="${esc(fmtTime(r.at * 1000))}">${esc(ago(r.at))}</span>`
            : `<b title="${esc(fmtTime(r.at * 1000))}">${esc(ago(r.at))}</b>`} <span class="pill cvagent" title="the coding agent this conversation is with">${esc(agentById(r.agent)?.name || "Claude")}</span> <span class="dim">${esc(size(r.bytes))}${
          theirs ? ` · ${esc(r.by || "")}'s` : ""}</span>${r.kept ? ` <span class="pill" title="${r.gone ? "its agent no longer has it: this is the copy kept on the controller" : "a copy is kept on the controller, past its agent's own cleanup"}">${r.gone ? "kept copy" : "kept"}</span>` : ""}${
          r.shared ? ` <span class="pill">visible to every session</span>` : ""}</div>
        ${r.first ? `<div class="dim first">${esc(r.first)}</div>` : ""}
        ${r.note ? `<div class="sub cvnote">${esc(r.note)}</div>` : ""}</div>
      <div class="acts actbar">${theirs ? "" : `<button type="button" data-cvresume="${esc(r.id)}" data-cvat="${esc(String(r.at))}" data-cvagent="${esc(r.agent || "claude")}">Resume</button>`}<button type="button" data-cvread="${esc(r.id)}">Read</button>${
        theirs ? "" : `<button type="button" data-cvedit="${esc(r.id)}" title="its label, its note, and whether a copy is kept">Edit</button>`}<a class="btn" href="/api/transcript?project=${encodeURIComponent(project)}&id=${encodeURIComponent(r.id)}&tz=${encodeURIComponent(tz)}" download>Download</a>${
        theirs ? "" : actMore([
          `<button type="button" data-cvshare="${esc(r.id)}" data-on="${r.shared ? "" : "1"}">${r.shared ? "Make private" : "Make visible"}</button>`,
          `<button type="button" class="danger" data-cvdel="${esc(r.id)}">Delete</button>`], true)}</div>
    </div>`).join("")}</div>`;
}

function nbSessionsView({$, nb, project, root}){
  const view = () => root.querySelector('.nbview[data-view="sessions"]');
  let rows = null;
  // The one row whose fields are in, and what the list is narrowed to.
  let editing = "", find = "";
  const matches = r => !find || [r.label, r.note, r.first, agentById(r.agent)?.name].some(x => String(x || "").toLowerCase().includes(find.toLowerCase()));
  async function loadSessions(){
    try{
      const j = await (await fetch("/api/transcripts?project=" + encodeURIComponent(project))).json();
      rows = j.error ? {error: j.error} : {rows: j.rows || [], visible: j.visible || []};
    }catch(e){ rows = {error: "could not reach the controller: " + e}; }
    drawSessions();
  }
  function drawSessions(){
    const v = view(), list = v?.querySelector(".sesslist"), hint = v?.querySelector(".nbglance");
    if (!list) return;
    if (rows === null){ glanceWaiting(hint); list.innerHTML = skel("rows"); return; }
    if (rows.error){ viewGlance(hint, []); list.innerHTML = `<div class="field"><div class="notice bad">${esc(rows.error)}</div></div>`; return; }
    const mine = rows.rows, theirs = rows.visible;
    const week = mine.filter(r => r.at * 1000 > Date.now() - 7 * 86400000).length;
    const open = mine.filter(r => r.shared).length;
    const kept = mine.filter(r => r.kept).length;
    viewGlance(hint, mine.length ? [
      {label: mine.length === 1 ? "conversation" : "conversations", value: mine.length},
      {label: "this week", value: week, omit: !week},
      {label: "kept", value: kept, omit: !kept},
      {label: "visible to every session", value: open, omit: !open}] : [],
      mine.length ? "yours alone unless you make one visible: each is the whole exchange" : "");
    // Found by label, note, first words or agent, once there are enough to
    // look through; the field keeps its caret across the redraw it causes.
    const shown = mine.filter(matches);
    const finder = mine.length > 5 ? `<div class="field cvfindrow"><input type="search" class="cvfind" maxlength="80" autocomplete="off" spellcheck="false"
      aria-label="find a conversation" placeholder="find by label, note or first words" value="${esc(find)}"></div>` : "";
    const had = document.activeElement?.classList?.contains("cvfind") ? document.activeElement.selectionStart : null;
    // What the view is for is its empty state (the a-notebook/views rule).
    list.innerHTML = (mine.length ? finder + `<div class="field mineconv">${shown.length ? convRows(project, shown, false, editing)
        : `<div class="hint">None of your conversations here matches that.</div>`}</div>`
      : `<div class="field"><div class="hint nbempty">Your sessions on this space, once you have had one: each is listed here for you alone, to resume, read, download or make visible to every session here.</div></div>`)
      // ...and others' they made visible, which any session here reads too.
      + (theirs.length ? docSection("sessions", "visible", "Made visible by others", String(theirs.length),
          `<div class="field theirconv">${convRows(project, theirs, true)}</div>`) : "");
    wireSections(list);
    const f = list.querySelector(".cvfind");
    if (f){
      f.oninput = () => { find = f.value; drawSessions(); };
      if (had !== null){ f.focus(); f.setSelectionRange(had, had); }
    }
    // Edit swaps a row's label, note and Keep in; Cancel puts them away.
    list.querySelectorAll("[data-cvedit]").forEach(b => b.onclick = () => { editing = b.dataset.cvedit; drawSessions(); list.querySelector(".cvLabel")?.focus(); });
    list.querySelectorAll("[data-cvcancel]").forEach(b => b.onclick = () => { editing = ""; drawSessions(); });
    list.querySelectorAll("[data-cvsave]").forEach(b => b.onclick = () => save(b));
    list.querySelector(".cvLabel")?.addEventListener("keydown", e => { if (e.key === "Enter"){ e.preventDefault(); save(list.querySelector("[data-cvsave]")); } });
    list.querySelectorAll(".cvlogs").forEach((l, i) => paginate(l, ":scope > .artrow", {key: `nbSess${i}:` + project, noun: "conversations"}));
    // The ⋯ of a row, as an action bar's (wireMore), its menu over the page.
    list.querySelectorAll(".acts .more > button").forEach(b => b.onclick = () => {
      const m = b.nextElementSibling, shut = m.hidden;
      closeMore();
      if (shut){ m.hidden = false; b.setAttribute("aria-expanded", "true"); floatAt(m, b); }
    });
    list.querySelectorAll("[data-cvshare]").forEach(b => b.onclick = () => act(b, b.dataset.cvshare, b.dataset.on ? "share" : "unshare"));
    list.querySelectorAll("[data-cvdel]").forEach(b => b.onclick = async () => {
      const r = mine.find(x => x.id === b.dataset.cvdel);
      if (!await askYes(`Delete your conversation of ${r ? fmtTime(r.at * 1000) : "this session"}?\n\n`
          + "It is gone for good: nothing can resume, read or download it again.")) return;
      act(b, b.dataset.cvdel, "delete");
    });
    list.querySelectorAll("[data-cvread]").forEach(b => b.onclick = () => openConversation(project, b.dataset.cvread));
    // Go on with this one: the project's chooser opens on it (resumeConversation).
    list.querySelectorAll("[data-cvresume]").forEach(b => b.onclick = ev => resumeConversation(project, b.dataset.cvresume, +b.dataset.cvat, ev, b.dataset.cvagent));
  }
  // A row's label, note and Keep saved: each that changed, said to the
  // controller in its own word, and the row read again as it is kept.
  async function save(b){
    const id = b.dataset.cvsave, form = b.closest("[data-cvform]"), r = (rows?.rows || []).find(x => x.id === id);
    if (!form || !r) return;
    const want = {label: form.querySelector(".cvLabel").value.trim().replace(/\s+/g, " "), note: form.querySelector(".cvNote").value.trim(),
                  kept: form.querySelector(".cvKeep").checked};
    const steps = [];
    if (want.label !== (r.label || "")) steps.push({action: "label", text: want.label});
    if (want.note !== (r.note || "")) steps.push({action: "note", text: want.note});
    if (want.kept !== !!r.kept) steps.push({action: want.kept ? "keep" : "unkeep"});
    busy(b, "Saving");
    try{
      for (const s of steps){
        const j = await (await postJSON("/api/transcripts", {project, id, ...s})).json();
        if (j.error){ notify(j.error, true); unbusy(b, "Save"); return; }
      }
    }catch(e){ notify("could not reach the controller: " + failWords(e), true); unbusy(b, "Save"); return; }
    editing = "";
    await loadSessions();
  }
  // Delete, Make visible and Make private: a person's, on the press.
  async function act(b, id, action){
    closeMore();
    busy(b, {delete: "Deleting", share: "Making visible", unshare: "Making private"}[action]);
    try{
      const j = await (await postJSON("/api/transcripts", {project, id, action})).json();
      if (j.error) notify(j.error, true);
      else notify({delete: "deleted", share: "visible to every session on this space", unshare: "yours alone again"}[action]);
    }catch(e){ notify("could not reach the controller: " + failWords(e), true); }
    await loadSessions();
  }
  return {loadSessions};
}
