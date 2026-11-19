// The notebook's Bugs view: the tracker, its form, its sorts and Send to
// Claude. One classic script beside index.html (docs/nodes.md §13): one file
// per notebook view (R60). A factory makeNotebook calls per notebook.

"use strict";

// A press handler set, not added (R244): a row drawn again is kept, and a
// listener added on every draw would answer each press once per draw.
function onPress(root, sel, fn){ const b = root.querySelector(sel); if (b) b.onclick = fn; }

// Whether a report answers a search (R254 step 1): its number (B12 or 12)
// or any of its words, case aside. An empty search is all.
function bugMatch(b, q){
  if (!q) return true;
  if (q === "b" + b.id || q === String(b.id)) return true;
  return ["title", "area", "repro", "expected", "actual", "notes", "status_note"]
    .some(k => String(b[k] || "").toLowerCase().includes(q));
}

// What a report knows (R254 step 3), as facts in place of a dotted line:
// who reported it and when, the build it was seen in and on, when and how
// it was closed, the build that closed it and the release that shipped
// the fix (shippedIn, from the CHANGELOG's dated headings).
function bugFacts(b, rel, words, refs, untie = false){
  const who = x => x === "claude" ? "Claude" : x === "you" ? "you" : x || "";
  const closed = b.status !== "open";
  const shipped = closed && b.status === "fixed" ? shippedIn(b.closed_at, rel) : "";
  return factGrid([
    ["Reported", `${b.at ? rmDay(b.at) : ""}${b.by ? `, by ${who(b.by)}` : ""}`],
    ["Seen in", b.seen_in || ""], ["Seen on", b.seen_on || ""],
    // Whether its steps show it (R124), from "not tried" up.
    ["Happens", REPRO_WORDS[b.reproduces || "untried"] || ""],
    ["Closed", closed ? `${words[b.status] || b.status}${b.closed_at ? ", " + rmDay(b.closed_at) : ""}${
      b.status_by ? `, by ${who(b.status_by)}` : ""}${b.status_note ? `: ${b.status_note}` : ""}` : ""],
    // The commits that fixed it (R255), or the build it was closed in
    // where none is named.
    ["Fixed in", closed ? (b.commits || []).join(", ") || b.fixed_in || "" : ""],
    ["Shipped in", shipped === null ? "not yet: planned for the next release" : shipped || ""],
    ["Changelog", clRefs(refs, untie), {html: true}]]);
}

// A fixed bug's answer for the release check (R255): a tied line, a line
// naming its fix commit, or its notes saying why it needs none.
const BUG_ANSWER = /(?:^|\n)(?:\[[^\]\n]*\]\s*)?Changelog:\s*(.+)/;
const bugOwed = (b, refs) => b.status === "fixed" && !(refs || []).length && !BUG_ANSWER.test(b.notes || "");

// Whether a report's steps reproduce it (R124), in the order a reader
// weighs them: every time first, the ones nobody has tried last.
const REPRO_ORDER = ["always", "sometimes", "once", "untried"];
const REPRO_WORDS = {always: "always", sometimes: "sometimes", once: "once", untried: "not tried"};
const REPRO_LABELS = {always: "Always", sometimes: "Sometimes", once: "Once", untried: "Not tried"};

function nbBugsView({$, nb, project}){
  // ---- bugs ----------------------------------------------------------------
  // Write-through, unlike the roadmap: a bug report is a form submitted once,
  // not a list curated in place, and a session finding one mid-task must not
  // depend on somebody pressing Save later.
  nb.bugs = null;
  nb.bugRev = null;      // the tracker's revision as of the last read

  // The tracker's read (nbRevRead): a read that failed is an empty tracker
  // carrying the error, which drawBugs says.
  function loadBugs(again = false){
    return nbRevRead(nb, {
      key: "bugs", token: "bug", url: "/api/bugs",
      rev: [() => nb.bugRev, v => nb.bugRev = v],
      put: (j, threw) => nb.bugs = threw || j.error ? {bugs: [], error: j.error} : j,
      draw: () => { drawBugs(); reposAlso($("bugRepos"), project, "bugs"); },
    }, again);
  }

  // The tracker's write (nbPoster). The batch guard reaches here too: a
  // report would survive a session's commit untouched (different file), but
  // the hold is the notebook's.
  const postBug = nbPoster(nb, "/api/bugs", {
    holdExcept: "history",
    // Somebody else edited this report first (roadmap #26). The tracker
    // that came back with the refusal is drawn; it is what the report now
    // says, but the FORM is left alone, holding what was typed, and the
    // caller keeps the new revision so pressing Save again writes over
    // theirs deliberately rather than by accident.
    conflict: j => {
      notify(j.error + ": what was typed is still in the form; "
             + "Save again to write it over theirs", true);
      if (j.bugs){ nb.bugs = j; if (nb.bugRev !== null) nb.bugRev += 1; }
      return j;
    },
    // `keepOpen`: the first of two writes from one form, which stays drawn.
    ok: (j, {keepOpen = false} = {}) => {
      nb.bugs = j;
      // This panel's own write moved the revision. Left unmarked, the next
      // poll reads it as somebody else's and reloads on top of the answer
      // just received.
      if (nb.bugRev !== null) nb.bugRev += 1;
      if (!keepOpen) drawBugs(true);
    },
  });

  const SEVS = ["low", "medium", "high", "critical"];

  // Ordered worst-first for sorting; the picker's own list runs the other way
  // because that is how somebody reads a severity scale when choosing one.
  const SEV_RANK = {critical: 0, high: 1, medium: 2, low: 3};
  const STATUS_WORDS = {open: "open", fixed: "fixed", wontfix: "won't fix",
                        na: "not applicable"};

  // Open before closed, always: a tracker is read to find what is left, and
  // a fixed critical topping the list is not that. The choice orders within.
  //
  // ...and severity is the one choice that means nothing once a bug is closed.
  // "How bad is it" is a question about work outstanding; a critical fixed in
  // June above a medium fixed yesterday answers nothing anybody asked. So the
  // closed half falls back to most recently closed, which is the only thing
  // that half is read for. The other four sorts already mean the same in both
  // halves (a date is a date and a title is a title), so they are left alone.
  const BUG_SORTS = {
    // The tie-break matters here and nowhere else: `updated` has one-second
    // resolution, and closing two bugs in the same second is ordinary. Falling
    // back to the id keeps the rows from swapping places between draws.
    severity: (a, b) => a.status !== "open"
                        ? (b.updated || b.at || 0) - (a.updated || a.at || 0)
                          || (b.id || 0) - (a.id || 0)
                        : (SEV_RANK[a.severity] ?? 9) - (SEV_RANK[b.severity] ?? 9)
                          || (b.at || 0) - (a.at || 0),
    newest:   (a, b) => (b.at || 0) - (a.at || 0),
    oldest:   (a, b) => (a.at || 0) - (b.at || 0),
    updated:  (a, b) => (b.updated || b.at || 0) - (a.updated || a.at || 0),
    reproduces: (a, b) => REPRO_ORDER.indexOf(a.reproduces || "untried") - REPRO_ORDER.indexOf(b.reproduces || "untried")
                          || (SEV_RANK[a.severity] ?? 9) - (SEV_RANK[b.severity] ?? 9) || (b.at || 0) - (a.at || 0),
    title:    (a, b) => String(a.title).localeCompare(String(b.title)),
  };

  function sortedBugs(){
    const how = BUG_SORTS[$("bugSort").value] || BUG_SORTS.severity;
    return (nb.bugs?.bugs || []).slice().sort((a, b) =>
      (a.status !== "open") - (b.status !== "open") || how(a, b));
  }

  // The report form, used for a new bug and for editing one. The fields are
  // the ones a session needs to act on a report without a conversation: where
  // it lives, how to make it happen, and the gap between should and does.
  function bugForm(b){
    const v = k => esc(b?.[k] || "");
    return `<div class="memadd bugform ctlrow">
      <label>Title</label>
      <textarea class="bfTitle proseline" rows="1" maxlength="1000"
        placeholder="the picker loses its selection on rotate">${v("title")}</textarea>
      <div class="two">
        <div><label>Severity</label>
          <select class="bfSev">${optionList(SEVS, b?.severity || "medium")}</select></div>
        <div><label>Where<span class="help" data-help="files, component, screen" tabindex="0">?</span></label>
          <textarea class="bfArea proseline" rows="1" maxlength="1000"
            placeholder="scripts/dashboard/index.html, the picker">${v("area")}</textarea></div>
      </div>
      <label>How to reproduce</label>
      <textarea class="bfRepro" spellcheck="false"
        placeholder="1. open the picker on a phone&#10;2. rotate">${v("repro")}</textarea>
      <label>Do those steps show it?</label>
      <div class="pseg bfRepr" role="radiogroup" aria-label="whether the steps reproduce it">${REPRO_ORDER.map(k => `
        <button type="button" data-repr="${k}" role="radio" class="${(b?.reproduces || "untried") === k ? "on" : ""}"
          aria-checked="${(b?.reproduces || "untried") === k}">${REPRO_LABELS[k]}</button>`).join("")}</div>
      <div class="two">
        <div><label>Expected</label>
          <textarea class="bfExpected proseline" rows="1" maxlength="1000"
            >${v("expected")}</textarea></div>
        <div><label>Actual</label>
          <textarea class="bfActual proseline" rows="1" maxlength="1000"
            >${v("actual")}</textarea></div>
      </div>
      ${b?.status === "fixed" ? `<label>Fixed in<span class="help" data-help="the commits that fixed it, by their hash; one commit may fix several bugs" tabindex="0">?</span></label>
      <input class="bfCommits" spellcheck="false" autocomplete="off" value="${esc((b.commits || []).join(", "))}"
        placeholder="2d591be, 0d90688">` : ""}
      <label>Notes<span class="help" data-help="cause, analysis, fix plan" tabindex="0">?</span></label>
      <textarea class="bfNotes" spellcheck="false"
        placeholder="what is known about why; mostly the agent's half">${v("notes")}</textarea>
      <div class="actbar">
        <button type="button" class="stop bfCancel">Cancel</button>
        <button type="button" class="primary bfGo">${b ? "Save the bug" : "Report it"}</button></div>
    </div>`;
  }

  // The form's one-of-four (R124): a press moves the pick.
  function reprPick(box){
    box.querySelectorAll(".bfRepr [data-repr]").forEach(b => b.onclick = () =>
      box.querySelectorAll(".bfRepr [data-repr]").forEach(x => {
        x.classList.toggle("on", x === b); x.setAttribute("aria-checked", String(x === b)); }));
  }

  function readBugForm(box){
    return {title: box.querySelector(".bfTitle").value,
            severity: box.querySelector(".bfSev").value,
            area: box.querySelector(".bfArea").value,
            repro: box.querySelector(".bfRepro").value,
            reproduces: box.querySelector(".bfRepr .on")?.dataset.repr || "untried",
            expected: box.querySelector(".bfExpected").value,
            actual: box.querySelector(".bfActual").value,
            notes: box.querySelector(".bfNotes").value};
  }

  // Report a bug, the control row's primary (R109): its form unrolls under
  // the row, as every view's add does, and rolls back on Cancel or a send.
  // Not drawn for a role that only reads the project (the operator, 21 Oct:
  // what a role does not give is not advertised), and its form shut.
  function drawBugAdd(){
    const box = $("bugAdd"), btn = $("bugNew");
    const shut = () => swapBox(box, () => {
      box.innerHTML = ""; box.hidden = true; btn.setAttribute("aria-expanded", "false"); });
    btn.hidden = !!projWriteWhy(project);
    if (btn.hidden){ if (!box.hidden) shut(); return; }
    // The same fold the memory writer opens with: the two are the same control
    // on two views of one notebook, and one of them appearing whole while the
    // other unrolled was the kind of difference you cannot unsee.
    btn.onclick = () => {
      if (!box.hidden) return box.querySelector(".bfTitle")?.focus();
      btn.setAttribute("aria-expanded", "true");
      swapBox(box, () => {
        box.hidden = false;
        drawHTML(box, bugForm(null));
        reprPick(box);
        box.querySelector(".bfCancel").onclick = shut;
        box.querySelector(".bfGo").onclick = async () => {
          const j = await postBug({action: "add", ...readBugForm(box)});
          if (j) shut();
        };
      });
    };
  }

  // `force` is what a deliberate action passes. Without it, a redraw is
  // skipped while a row has something typed into it.
  //
  // The list is rebuilt with innerHTML, which carries each row's open state
  // across but nothing else, and the delete box and the edit form are
  // imperative DOM put into a row AFTER the render, so a repaint took them
  // and whatever the operator had written in them. Any bug_rev change did
  // it: another session filing something, or this one closing a bug in a
  // terminal. The same family as the changelog pane (bug #13), and the same
  // answer the rest of the notebook already gives: Memory stages behind
  // Save, the node editor keeps its draft across a repaint. An editor beats
  // freshness; the next deliberate action redraws with whatever arrived
  // meanwhile, because `bugs` is still updated underneath.
  function drawBugs(force){
    const list = $("bugList"), hint = $("bugHint");
    if (!nb.bugs){
      // Waiting as it lands: Report a bug above the list, which needs no list.
      glanceWaiting(hint); drawHTML(list, skel("rows"));
      drawBugAdd();
      return;
    }
    if (nb.bugs.error){ viewGlance(hint, [], esc("bugs: " + nb.bugs.error), "", "bad"); return; }
    if (!force && list.querySelector(".dropbox, .bugform")) return;
    if (nb.bugs.releases !== undefined) nb.bugReleases = nb.bugs.releases;
    const rows = sortedBugs();
    const open = rows.filter(b => b.status === "open").length;
    // The glance (R109): what is open, each severity among the open ones
    // from the worst, and what is closed, as tiles; the worst two in their
    // colors while any is open. What the tracker is for is its empty state
    // (R119 step 4), so an empty one draws none.
    const sevN = s => rows.filter(b => b.status === "open" && b.severity === s).length;
    viewGlance(hint, !rows.length ? [] : [
      {label: "open", value: open},
      ...["critical", "high", "medium", "low"].map(s => ({label: s, value: sevN(s), omit: !sevN(s),
        tone: s === "critical" ? "bad" : s === "high" ? "warn" : ""})),
      {label: "closed", value: rows.length - open, omit: rows.length === open}]);
    // A sort over nothing is a control that does nothing: it arrives with
    // the second bug, when there is an order to choose, and the search with it.
    const sortBar = $("bugSortBar");
    if (sortBar) sortBar.hidden = rows.length < 2;
    setHidden($("bugFind"), rows.length < 2 && !nb.bugFind);
    // Narrowed by a chip (All, Open, Closed) and the search (R254 step 1).
    nb.bugChip = ["", "open", "closed"].includes(nb.bugChip) ? nb.bugChip : "";
    if (patch($("bugChips"), chipButtons([{key: "open", label: "Open", count: open},
                                          {key: "closed", label: "Closed", count: rows.length - open}], nb.bugChip, "data-bgchip"), true))
      $("bugChips").querySelectorAll("[data-bgchip]").forEach(b => b.onclick = () => chipMove(() => $("bugList")?.closest(".nbview"), "#bugList details.bug", () => { nb.bugChip = b.dataset.bgchip; drawBugs(true); }));
    const q = (nb.bugFind || "").trim().toLowerCase();
    // ...and by the release a report was seen in (the operator, 21 Oct).
    const vers = versionChips(rows, b => b.seen_in, "Unknown");
    if (nb.bugVer && !vers.some(v => v.key === nb.bugVer)) nb.bugVer = "";
    if (patch($("bugVers"), chipButtons(vers, nb.bugVer, "data-bgver", undefined, "Any version"), true))
      $("bugVers").querySelectorAll("[data-bgver]").forEach(b => b.onclick = () => chipMove(() => $("bugList")?.closest(".nbview"), "#bugList details.bug", () => { nb.bugVer = b.dataset.bgver; drawBugs(true); }));
    // ...and by whether it reproduces (R124).
    const reprN = k => rows.filter(b => (b.reproduces || "untried") === k).length;
    if (!REPRO_ORDER.includes(nb.bugRepr)) nb.bugRepr = "";
    if (patch($("bugRepro"), chipButtons(REPRO_ORDER.map(k => ({key: k, label: REPRO_LABELS[k], count: reprN(k)})),
                                         nb.bugRepr, "data-bgrepr", undefined, "However often"), true))
      $("bugRepro").querySelectorAll("[data-bgrepr]").forEach(b => b.onclick = () => chipMove(() => $("bugList")?.closest(".nbview"), "#bugList details.bug", () => { nb.bugRepr = b.dataset.bgrepr; drawBugs(true); }));
    const shown = b => (!nb.bugChip || (nb.bugChip === "open") === (b.status === "open"))
      && inRelease(b.seen_in, nb.bugVer) && (!nb.bugRepr || (b.reproduces || "untried") === nb.bugRepr) && bugMatch(b, q);
    // Which were open before this redraw, so acting on one does not fold it.
    const held = new Set([...list.querySelectorAll(".bug[open]")].map(d => d.dataset.id));
    // Only the rows on show are built, a page at a time (pageLimit): every
    // one of 795 built and all but 25 hidden was three seconds on a phone
    // for each press of a chip (the operator, 17 Oct).
    const vis = rows.filter(shown);
    const lim = pageLimit(list, "bugList", vis.length);
    // A role that reads the project and does not write it (B86): a report
    // carries no verbs, and Report a bug says why above the list.
    const ro = projWriteWhy(project);
    drawHTML(list, vis.slice(0, lim).map(b => `
      <details class="bug chev" data-id="${b.id}"${held.has(String(b.id)) ? " open" : ""}>
        <summary>
          <span class="tag sev ${esc(b.severity)}">${esc(b.severity)}</span>
          <span class="n id" title="bug B${b.id}: a session knows it by that number">B${b.id}</span>
          <span class="btitle${b.status !== "open" ? " done" : ""}">${esc(b.title)}</span>
          <span class="tag bstat ${esc(b.status)}">${esc(
            b.status === "na" ? "n/a" : b.status === "wontfix" ? "won't fix" : b.status)}</span>
        </summary>
        <div class="body">
          ${["area", "repro", "expected", "actual", "notes"].map(k => b[k]
            ? `<div class="bfield"><label>${k}</label><div class="bval">${esc(b[k])}</div></div>` : "").join("")}
          ${bugFacts(b, nb.bugReleases, STATUS_WORDS, (nb.bugs.changelog || {})["B" + b.id], !ro)}
          ${bugOwed(b, (nb.bugs.changelog || {})["B" + b.id]) ? `<div class="hint bowed">No changelog line answers this fix yet:
            tie it to one, write one, or say why it needs none, from ⋯ below. A release waits for it.</div>` : ""}
          ${ro ? "" : `<div class="actbar macts">
            <span class="sp"></span>
            <button type="button" class="bSend"${b.status === "open" ? "" : " disabled"}
              title="${b.status === "open"
                ? `send this bug to the running session`
                : `closed: reopen it first to send it`}"
              >Send to ${esc(sendAgent(project).name)}</button>
            <button type="button" class="bEdit">Edit</button>
            ${b.status === "open"
              // Five at most on a bar, the rest behind More (R210): six
              // were cut short at 344px (R254 step 7). Mark fixed stays on
              // the bar, the other closes and Remove go under it, Remove
              // last as the one that cannot be undone.
              ? `<button type="button" class="bFix">Mark fixed</button>
                 ${actMore([`<button type="button" class="bWont">Won't fix</button>`,
                   `<button type="button" class="bNa" title="it was real and stopped applying: the feature went away">Not applicable</button>`,
                   `<button type="button" class="danger bRm" title="for a report that should not exist: mis-filed, a duplicate, the wrong space">Remove</button>`])}`
              : b.status === "fixed"
              // What the changelog says of it (R255) under More, Remove last.
              ? `<button type="button" class="bReopen">Reopen</button>
                 ${actMore([`<button type="button" class="bTie"${(nb.bugs.lines || []).length ? "" : ` disabled title="nothing is unreleased to tie it to"`}>Tie to a line</button>`,
                   `<button type="button" class="bLine">Write a line</button>`,
                   `<button type="button" class="bNoLine" title="a release never had it, or nobody using it meets it">Needs no line</button>`,
                   `<button type="button" class="danger bRm" title="for a report that should not exist: mis-filed, a duplicate, the wrong space">Remove</button>`])}`
              : `<button type="button" class="bReopen">Reopen</button>
                 <!-- Last, because it is the one that cannot be undone. -->
                 <button type="button" class="danger bRm"
                   title="for a report that should not exist: mis-filed, a duplicate, the wrong space">Remove</button>`}
          </div>`}
        </div>
      </details>`).join("")
      // What the tracker is for, as its empty state (R119 step 4).
      || (rows.length ? "" : `<div class="hint nbempty">What goes here reaches every session in this space.</div>`));
    paginate(list, ":scope > .bug", {key: "bugList", noun: "reports", total: vis.length, more: () => drawBugs()});
    wireMore(list);
    list.querySelectorAll(".bug").forEach(d => {
      const id = Number(d.dataset.id);
      // Opened with the same tween the cards and the memories use. Bound on
      // the summary rather than the details' toggle event, because toggle
      // fires after the browser has already snapped it open.
      const sum = d.querySelector("summary");
      if (sum) sum.onclick = e => { e.preventDefault(); slideDetails(d, !foldOpen(d)); };
      // The closing note typed in the row (R254 step 6), the box the Delete
      // below and the roadmap's drop open, not the browser's prompt: one
      // shape for every question this view asks, and one a phone lays out.
      const ask = (status, q, verb) => {
        closeMore();
        const body = d.querySelector(".body");
        if (body.querySelector(".dropbox")) return;
        dropBox(body, {q, sub: ": kept on the bug", placeholder: "a commit, a word", verb,
                       go: note => postBug({action: "status", id, status, note}), cancel: () => drawBugs(true)});
      };
      onPress(d, ".bFix",
        () => ask("fixed", "What fixed it?", "Close as fixed"));
      onPress(d, ".bWont",
        () => ask("wontfix", "Why not?", "Close: won't fix"));
      onPress(d, ".bNa",
        () => ask("na", "What stopped it applying?", "Close: not applicable"));
      onPress(d, ".bReopen",
        () => postBug({action: "status", id, status: "open", note: ""}));
      // The changelog's half of a fixed bug (R255): kept in the notebook,
      // the public line naming its commits alone.
      d.querySelectorAll("[data-untie]").forEach(x => x.onclick = () =>
        postBug({action: "untie", id, line: x.dataset.untie}));
      onPress(d, ".bTie", () => {
        closeMore();
        const body = d.querySelector(".body");
        if (body.querySelector(".tiebox")) return;
        const lines = nb.bugs.lines || [];
        const cats = [...new Set(lines.map(l => l.cat))];
        const box = document.createElement("div");
        box.className = "dropbox ctlown tiebox";
        drawHTML(box, `<div class="q">Which line says this was fixed?<span>: kept in the notebook; the public line names its commits</span></div>
          <select aria-label="an unreleased changelog line">${cats.map(c => `<optgroup label="${esc(c || "no category")}">${
            lines.filter(l => l.cat === c).map(l => `<option value="${esc(l.words)}">${esc(l.words.length > 110 ? l.words.slice(0, 108) + "…" : l.words)}</option>`).join("")
          }</optgroup>`).join("")}</select>
          <div class="actbar"><button type="button" class="stop">Cancel</button>
            <button type="button" class="primary" data-tiego>Tie it</button></div>`);
        body.appendChild(box);
        arriveBox(box);
        box.querySelector(".stop").onclick = () => { box.remove(); drawBugs(true); };
        box.querySelector("[data-tiego]").onclick = () => {
          const line = box.querySelector("select").value;
          box.remove();
          if (line) postBug({action: "tie", id, line});
        };
      });
      onPress(d, ".bLine", () => {
        closeMore();
        const body = d.querySelector(".body");
        if (body.querySelector(".dropbox")) return;
        const b = (nb.bugs.bugs || []).find(x => x.id === id);
        const box = dropBox(body, {q: "The changelog's line for this fix", sub: ": what a person upgrading now finds right, filed under Fixed with its commits",
                                   placeholder: "A move lands on a stick that keeps deploy keys", verb: "Add the line", max: 300,
                                   cancel: () => drawBugs(true),
                                   go: async text => {
                                     const j = await postJSON("/api/changelog", {project, action: "line", text, cat: "Fixed",
                                                                                 shas: b?.commits || [], bugs: [id]});
                                     if (j?.error){ notify(j.error, true); drawBugs(true); return; }
                                     loadBugs(true);
                                   }});
        const ta = box.querySelector("textarea");
        ta.value = b?.title || "";
        ta.dispatchEvent(new Event("input"));
      });
      onPress(d, ".bNoLine", () => {
        closeMore();
        const body = d.querySelector(".body");
        if (body.querySelector(".dropbox")) return;
        dropBox(body, {q: "Why does it need no line?", sub: ": kept in its notes, which the release check reads",
                       placeholder: "no release had it; nobody using it meets it", verb: "Needs no line",
                       cancel: () => drawBugs(true), go: why => postBug({action: "noline", id, why})});
      });
      // Handing a bug over. Same box the roadmap opens under a step, opened
      // under the report instead; it asks the same question and the pickers
      // behind it are the same two.
      onPress(d, ".bSend", () => {
        const body = d.querySelector(".body");
        if (body.querySelector(".sendbox")) { nb.shutSendBoxes(); return; }
        nb.shutSendBoxes();
        nb.sendNoteText = "";            // see nbRmPick: a note is not carried over
        nb.roadmapSel = null;               // and only one thing is armed at a time
        nb.drawSendBox(!!nb.roadmapSession);
        // Same session the roadmap sends into, and the same reason it has to
        // exist first: there is no door into a session that is not running.
        if (!nb.roadmapSession){
          notify("no session is running here: start one with Start agent first", true);
          return;
        }
        const box = nb.sendBoxEl({
          label: `Send B${id} to ${agentOfSession(tmuxBase(nb.roadmapSession))?.agent.name || "the session"}?`,
          sub: "the session looks it up by number",
          placeholder: "anything to send with it (optional)",
          onCancel: nb.shutSendBoxes,
          onSend: async () => {
            const go = box.querySelector("#roadmapGo");
            busy(go, "Sending");
            const to = await pickSend(project);
            if (to === null){ unbusy(go, "Send"); return; }
            const j = await postBug({action: "send", id, note: nb.sendNoteText, session: to});
            unbusy(go, "Send");
            if (!j) return;
            if (!j.sent){
              notify(j.switching
                ? `Not sent: the session is busy with the /${j.switching} line. `
                  + "Clear its tab and send the bug again."
                : "Not sent: the session is busy. Press Enter in its tab when it is free.",
                true);
              return;
            }
            nb.sendNoteText = "";
            nb.shutSendBoxes();
            openSentTo(project, j.session);   // land in the tab it went to
          },
        });
        body.appendChild(box);
        arriveBox(box);   // appended by the click; nothing redraws it under us
      });
      // Same box the roadmap's bin opens, for the same reason: nothing here
      // can be undone, so the only thing between a deleted report and its
      // being filed again is a note saying why it went.
      onPress(d, ".bRm", () => {
        closeMore();
        const body = d.querySelector(".body");
        if (body.querySelector(".dropbox")) return;
        // Removed first, then redrawn: the box is what defers the redraw,
        // so anything that arrived while it was open lands now.
        dropBox(body, {q: "Delete this report?", sub: ": it is gone for good; to keep a record, close it instead",
                       placeholder: "why it should not have been filed (optional, kept in the log)",
                       verb: "Remove it", tone: "danger", cancel: () => drawBugs(true),
                       go: why => postBug({action: "remove", id, why})});
      });
      onPress(d, ".bEdit", () => {
        const body = d.querySelector(".body");
        const b = (nb.bugs.bugs || []).find(x => x.id === id);
        drawHTML(body, bugForm(b));
        reprPick(body);
        // The revision this form was opened over, so a write that would go
        // over somebody else's is refused rather than applied. On the form
        // rather than in a closure, the same way the memory editor carries
        // its digest: a refusal moves it on, and the second press is then a
        // decision made knowing what it replaces.
        const form = body.querySelector(".bugform");
        form.dataset.rev = b?.rev ?? "";
        // Forced: this IS the deliberate close, and the form it is putting
        // away is the thing that would otherwise hold the redraw off.
        body.querySelector(".bfCancel").onclick = () => drawBugs(true);
        body.querySelector(".bfGo").onclick = async () => {
          // Fixed in (R255): the commits added and taken off, written first
          // so a refused hash leaves the form open to put right.
          const field = body.querySelector(".bfCommits");
          if (field){
            const was = b?.commits || [], now = field.value.split(/[\s,]+/).map(x => x.trim().toLowerCase()).filter(Boolean);
            const add = now.filter(x => !was.some(w => w.startsWith(x) || x.startsWith(w)));
            const drop = was.filter(w => !now.some(x => w.startsWith(x) || x.startsWith(w)));
            if (add.length || drop.length){
              const c = await postBug({action: "commits", id, add, drop}, {keepOpen: true});
              if (!c || c.error) return;
              // ...which moved the report's revision: the edit is over that.
              form.dataset.rev = (c.bugs || []).find(x => x.id === id)?.rev ?? form.dataset.rev;
            }
          }
          const j = await postBug({action: "edit", id, rev: form.dataset.rev || undefined,
                                   ...readBugForm(body)});
          if (j?.conflict) form.dataset.rev = j.conflict.rev;
        };
      });
    });
    drawBugAdd();
  }

  return {loadBugs, drawBugs, postBug};
}
