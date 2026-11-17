// The doctor: aerie doctor's verdict, run by the server on a slow loop and on
// the ↻ button, behind a dot in the top bar after the bell (R218 step 3).
// The dot wears the worst check's color; its panel lists failures and
// warnings as full lines (they are for reading) and passing checks as chips.
// One classic script beside index.html (docs/design-language.md, Files):
// pure declarations, nothing runs at load. The dot and ↻ are wired from
// index.html, under the doctor header.

"use strict";

let docShown = false;

function drawDoctor(){
  const el = $("doctor"), d = state?.doctor;
  const dot = $("docDot");
  setText($("docWhen"), d?.running ? "running…" : d?.when ? ago(d.when) : "");
  if (!d || !d.when){
    setClass(dot, "st");
    setAttr($("bDocDot"), "aria-label", "aerie doctor: no verdict yet");
    patch(el, `<div class="empty">${d?.running ? "running…" : "first run pending…"}</div>`);
    return;
  }
  const {level, probs, fine, html} = doctorChecks(d);
  setClass(dot, "st " + level);
  setAttr($("bDocDot"), "aria-label", level === "ok" ? `aerie doctor: all ${fine.length} ok`
    : `aerie doctor: ${probs.length} to look at`);
  patch(el, html);
  // Controller settings from here, for an account that may open it, as the
  // gear has Profile.
  const go = $("docSettings");
  if (go) go.hidden = !railAllows("settings");
}

// The doctor's checks as the panel and Controller settings' card draw them:
// the problems first, each its line in its level's color with what the
// check said under it and the way to fix it where the server knows one, then
// the passing checks as chips. {level, probs, fine, html}.
function doctorChecks(d){
  const tip = c => c.text + (c.detail ? "\n\n" + c.detail : "");
  // A plain user sees the lines that are theirs to act on: whether a node
  // can run their session. Runner tokens, ssh keys and the docker daemon
  // are the controller's, and in their panel they read as things to fix.
  const checks = state?.admin === false
    ? d.checks.filter(c => /can run a session/.test(c.text)) : d.checks;
  const probs = checks.filter(c => c.level === "FAIL" || c.level === "warn");
  const fine = checks.filter(c => c.level === "ok");
  const skip = checks.filter(c => c.level === "skip");
  const level = probs.some(c => c.level === "FAIL") ? "bad"
              : probs.length ? "warn" : "ok";
  const html =
    `<div class="probs">${probs.map(c =>
       `<div class="sub ${c.level === "FAIL" ? "bad" : "warn"}" title="${esc(tip(c))}">${esc(c.text)}${
          c.detail ? `<span class="why">${esc(c.detail)}</span>` : ""}${
          // Where the fix is, when the server knows (B71): a link, which
          // closes the panel as any press elsewhere does.
          c.href ? `<a class="pagelink" href="${esc(c.href)}">${esc(c.act || "Open")}</a>` : ""}</div>`
     ).join("")}</div>` +
    `<div class="chips">${
       fine.map(c => `<span class="pill ok" title="${esc(tip(c))}">${esc(c.text)}</span>`).join("") +
       skip.map(c => `<span class="pill" title="${esc(tip(c))}">${esc(c.text)}</span>`).join("")
     }</div>`;
  return {level, probs, fine, html};
}

// Run the doctor now, from the panel's ↻ or the card's Run again: both
// presses rest while it runs, and both places draw what it found.
async function runDoctor(){
  const bs = [$("bDoctor"), $("setDocRun")].filter(Boolean);
  if (bs.some(b => b.disabled)) return;
  bs.forEach(b => { b.disabled = true; });
  setText($("docWhen"), "running…");
  try{
    const j = await postJSON("/api/doctor", {});
    if (j.error) notify("doctor: " + j.error, true);
    else if (state) state.doctor = j;
  }catch(e){ notify("doctor: " + failWords(e), true); }
  [$("bDoctor"), $("setDocRun")].filter(Boolean).forEach(b => { b.disabled = false; });
  drawDoctor();
  if (shown("settings")) drawPanes();
}

// Open or shut the panel, with the bell's manners: anything else closes it,
// Escape closes it (wired by page-boot.js).
function toggleDoctor(open){
  docShown = open === undefined ? !docShown : open;
  $("bDocDot").setAttribute("aria-expanded", String(docShown));
  $("docPanel").hidden = !docShown;
  if (docShown) drawDoctor();
}
