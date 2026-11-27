// Report a bug in AerieOS from a project's row (the operator, 2 Oct): a
// person's way into the same diagnostics a session reaches with
// `aerie report`. The dialog asks for a category, what happened and how to make
// it happen; the project is the row's, and the server adds the node and the
// build it was seen on. One classic script beside index.html; the button is
// projectActions' (nb-core.js), its handler page-sidebar.js's and the markup
// #reportModal index.html's.

"use strict";

// What a report is about, in the words a person would pick. The words go
// into the report's area, which is what the diagnostics sort and read by.
const REPORT_CATS = [
  "The dashboard", "An agent's session", "Builds and tests", "The notebook",
  "Nodes and toolchains", "The emulator or a phone", "Containers", "Git and pushing",
  "Signing", "The companion app", "Something else",
];
let reportProject = "";

// ---- its form ----
// One form over the dialog's own foot (R301): which repository beside what
// kind of thing, where a space has several (with one, Category runs across);
// what happened and how to make it happen; and the latest conversation on the
// space, which is usually the bug (the operator, 2 Oct), off unless ticked
// with the line under it saying which one it is.
function reportDrawForm(){
  const at = document.querySelector('#reportModal [data-dlgform="report"]');
  if (!at) return;
  at.innerHTML = formBox({fields: [
    `<div class="fcell fwide"><div class="fgrid pair">${
      formField("reportRepo", "Repository", `<select id="reportRepo"></select>`, {hidden: true, attrs: `id="reportRepoField"`})}${
      formField("reportCat", "Category", `<select id="reportCat"></select>`)}</div></div>`,
    formField("reportText", "What happened", `<textarea id="reportText" maxlength="2000" placeholder="what you did, what you expected, and what happened instead"></textarea>`, {wide: true}),
    formField("reportRepro", "How to make it happen", `<textarea id="reportRepro" maxlength="2000" placeholder="the steps, if you know them"></textarea>
      <div class="hint" id="reportHint">It goes to the diagnostics with this space, its node and the build it was seen on, where whoever maintains AerieOS reads it.</div>`,
      {wide: true, tail: `<span class="dim">(optional)</span>`}),
    `<div class="fcell fwide" id="reportConvField" hidden><label class="ndcap"><input type="checkbox" id="reportConv"> Include my latest conversation on this space</label>
      <div class="sub" id="reportConvWhich"></div></div>`]});
}

// From a project's card, which of its repositories (R138: the first unless
// another is picked), each sending its own node and conversation.
function openReport(project, repos = []){
  reportProject = project;
  const m = $("reportModal");
  armModal(m);
  // From a project's row, or the header's about no project in particular.
  $("reportTitle").textContent = project ? `Report a bug, from ${projectName(project)}` : "Report a bug";
  const pick = $("reportRepo");
  drawHTML(pick, repos.map(r => `<option value="${esc(r)}">${esc(projLabel(r))}</option>`).join(""));
  pick.value = project;
  $("reportRepoField").hidden = repos.length < 2;
  pick.onchange = () => { reportProject = pick.value; reportConvFor(pick.value); };
  $("reportHint").textContent = project
    ? "It goes to the diagnostics with this space, its node and the build it was seen on, where whoever maintains AerieOS reads it."
    : "It goes to the diagnostics with the build it was seen on, where whoever maintains AerieOS reads it. A problem in one space is better sent from that space's row.";
  const cat = $("reportCat");
  if (!cat.options.length)
    drawHTML(cat, REPORT_CATS.map(c => `<option>${esc(c)}</option>`).join(""));
  $("reportText").value = "";
  $("reportRepro").value = "";
  $("reportErrWrap").hidden = true;
  reportConvFor(project);
  m.hidden = false;
  m.onclick = e => { if (e.target === m) m.hidden = true; };
  $("reportCancel").onclick = () => { m.hidden = true; };
  $("reportSend").onclick = sendReport;
  // Only while it is still open: put away inside the 50ms, the focus went
  // into the closing box and not back to what opened it.
  setTimeout(() => { if (!m.hidden) $("reportText").focus(); }, 50);
}

// The conversation a report could carry: this account's newest on the
// repository it is sent from.
function reportConvFor(project){
  $("reportConv").checked = false;
  $("reportConvField").hidden = true;
  if (project) getJSON("/api/transcripts?project=" + encodeURIComponent(project)).then(j => {
      const c = (j.rows || [])[0];
      if (!c || reportProject !== project) return;
      // Its first words when it has any; a conversation that opened with
      // nothing typed printed `just now: "".` (B453).
      const first = String(c.first || "").trim().slice(0, 90);
      $("reportConvWhich").textContent = `${ago(c.at)}${first ? `: "${first}"` : ""}. `
        + "Its last part goes with the report, with secrets taken out, to whoever reads the diagnostics.";
      $("reportConvField").hidden = false;
    }).catch(() => {});
}

async function sendReport(){
  const text = $("reportText").value.trim();
  const fail = msg => { $("reportErr").textContent = msg; $("reportErrWrap").hidden = false; };
  if (!text) return fail("say what happened: one sentence is enough");
  const btn = $("reportSend");
  busy(btn, "Sending");
  try{
    const j = await postJSON("/api/reports", {action: "add", project: reportProject, text,
      area: $("reportCat").value, repro: $("reportRepro").value.trim(),
      include_conversation: !!reportProject && $("reportConv").checked});
    if (j.error) return fail(j.error);
    $("reportModal").hidden = true;
    notify(`reported as #${j.id ?? j.report?.id ?? "?"}: it is in the diagnostics`);
  }catch(e){ fail("could not reach the controller: " + e); }
  finally{ if (btn.isConnected) unbusy(btn, "Send"); }
}
