// The notebook's Roadmap view: the list and its steps, the send box, the
// refusal when two writers meet, and the staged changes Save replays. One
// classic script beside index.html (docs/nodes.md §13): one file per notebook
// view. nbRoadmapView is the factory makeNotebook calls per notebook;
// everything it draws and does is a function of its own below it.

"use strict";

// ---- the view -------------------------------------------------------------
// Once per notebook: the state this view keeps on nb, set in the order it
// always was, and the controls in the markup wired to the functions below.
// Each of those is handed what it reaches: `$`, the notebook's own lookup
// (every id inside a notebook is the template's, so the page's $ would find
// the first notebook's), and `nb`, the notebook's state, which holds all of
// this view's state too. What it hands back goes onto nb for the others.
function nbRoadmapView({$, nb}){
  // What a session can be switched to on the way in. Tables, not free text:
  // these become part of a command typed into a terminal, and the server keeps
  // its own copy of both lists rather than trusting the one that arrives.
  // Remembered outside the box, because the box is rebuilt from scratch every
  // time its list is redrawn: a half-typed note that vanished whenever
  // something else on the panel moved would be worse than useless.
  nb.sendNoteText = "";

  nb.roadmapItems = [];
  nb.roadmapSession = null;
  nb.roadmapUnsaved = {};  // {roadmap, memory}: what a session has not been told
  nb.roadmapSel = null;  // {id, step}: the arrow that is armed, if any
  // Which arrow's box has already unrolled. The box is rebuilt on every draw
  // (see nbRmDrawSendBox), so without this a poll landing while it is open would
  // replay the arrival two or three times a minute: the animation belongs to
  // the arrow being pressed, not to the box being drawn.
  nb.sendShownFor = "";
  nb.roadmapOrdering = false;  // the rows are showing move controls instead
  nb.roadmapOpen = new Set();  // the rows open to their workings and actions, as id:step
  // Reordering is the one edit held back. Everything else here is a decision:
  // ticked, crossed, dropped, and is written the moment it is made; arranging
  // is a draft you are in the middle of, and closing the panel on a half-done
  // shuffle should leave the order alone. So the moves live here until Save,
  // and the snapshot is what Cancel puts back.
  nb.roadmapPending = [];  // staged changes, in the order they were made
  nb.roadmapWas = null;  // the list as it was before the first staged change
  // A session's open batch, and whether one has closed since this copy of the
  // list was read. Both block Save: while it is open the list is moving, and
  // once it has closed what is on screen is out of date.
  nb.roadmapBatch = null;
  nb.roadmapStale = false;

  nb.clash = null;  // {op, item, rev, by, at}
  nb.clashResume = null;  // what to carry on with once it is settled

  $("roadmapAdd").onclick = () => nbRmAdd($, nb);
  nb.roadmapForm = on => nbRmForm($, on);
  $("roadmapShow").onclick = () => nbRmForm($, true);
  $("roadmapCancel").onclick = () => { $("roadmapText").value = ""; nbRmForm($, false); };
  $("roadmapOrder").onclick = () => {
    // Entering the mode throws nothing away either: whatever is already staged
    // stays staged, and the moves join it.
    nb.roadmapOrdering = !nb.roadmapOrdering;
    if (nb.roadmapOrdering) nbRmCancelSend($, nb);
    nbRmRedraw($, nb);
  };

  nb.tmpId = 0;  // ids for items the server has never heard of
  // Moves on every staged change, and never goes back. nbRmLoad reads it before
  // asking and again before drawing, which is how a reply that left before the
  // operator typed is told from one that left after; see the guard there.
  nb.roadmapStaged = 0;

  $("roadmapText").onkeydown = e => {
    if (e.key === "Enter"){ e.preventDefault(); nbRmAdd($, nb); }
    // Escape in a field with something in it clears the field, not the
    // panel; in an empty one it rolls the band back up.
    if (e.key === "Escape" && e.target.value){
      e.preventDefault(); e.stopPropagation(); e.target.value = "";
    } else if (e.key === "Escape"){
      e.preventDefault(); e.stopPropagation(); nb.roadmapForm(false);
    }
  };

  // The Finished section is shut until opened, and fetched the first time it
  // is; the search narrows it as it does the list.
  $("roadmapDoneSect").addEventListener("toggle", () => {
    if ($("roadmapDoneSect").open && nb.roadmapDone === null) nbRmLoadFinished($, nb);
    else nbRmDrawFinished($, nb);
  });
  wireSections($("roadmapDoneSect").parentElement);
  onTyping($("roadmapFind"), () => {
    nb.roadmapFind = $("roadmapFind").value;
    nbRmRedraw($, nb);
    nbRmDrawFinished($, nb);
  });
  nb.drawFinished = () => nbRmDrawFinished($, nb);

  // What makeNotebook and the other views call, bound to this notebook.
  return {
    cancelSend: () => nbRmCancelSend($, nb),
    drawSendBox: live => nbRmDrawSendBox($, nb, live),
    flushPending: () => nbRmFlushPending($, nb),
    loadRoadmap: gen => nbRmLoad($, nb, gen),
    postRoadmap: (body, quiet) => nbRmPost($, nb, body, quiet),
    redrawRoadmap: force => nbRmRedraw($, nb, force),
    revertPending: () => nbRmRevertPending(nb),
    sendBoxEl: opts => nbRmSendBoxEl(nb, opts),
    shutSendBoxes: () => nbRmShutSendBoxes($),
  };
}

// ---- the shared to-do list ---------------------------------------------
// Both sides write it: the operator here, a session through `aerie roadmap`. Its
// open items are appended to every Claude session bb-tty starts, which is why
// something noticed mid-task and left undone survives the conversation.

function nbRmLoad($, nb, gen){
  return reading(`${nb.memProj}:roadmap`, async () => {
    // What the staging counter was when we asked. See the guard below.
    const staged = nb.roadmapStaged;
    let j;
    try{
      j = await getJSON("/api/roadmap?project=" + encodeURIComponent(nb.memProj));
    }catch(e){ j = {error: String(e)}; }
    if (gen !== nb.memGen) return;
    // ...and never over something staged WHILE this was in flight. The guard
    // above catches a reply meant for a different project; this catches one for
    // this project that left before the operator typed and came back after.
    //
    // Every path that reloads does ask first: rereadRoadmap confirms, noteBatch
    // checks that nothing is staged, but they ask BEFORE the fetch, and the
    // answer stops being true while it is in flight. The list then came back
    // from the server and quietly took what had been typed since.
    //
    // The test is "did anything stage since we asked", not "is anything staged
    // now": an explicit re-read with work already staged is a request to
    // replace it, and rereadRoadmap has confirmed that. Only the typing that
    // happened DURING the round trip is unanswerable, because nobody was asked
    // about it.
    //
    // Measured rather than reasoned: three concurrent runs of roadmap.mjs, two of
    // them with #roadmapList empty and the hint back to "Nothing yet" a moment
    // after a row was staged. Filed as a test race for weeks (bug #13) because
    // it only showed under load, which is exactly when a fetch is slow enough
    // to land on the wrong side of the typing.
    //
    // The batch marker still gets through: a session opening or closing one is
    // news whether or not this list can be replaced.
    if (nb.roadmapStaged !== staged){
      if (j.batch !== undefined) nb.noteBatch(j.batch);
      return;
    }
    nbRmDraw($, nb, j);
    reposAlso($("roadmapRepos"), nb.memProj, "roadmap");
  });
}

// The send arrow. Crossing something out here does not mean "done"; it means
// "handed to the session", which is the thing the operator actually needs to
// see, because a step can be sent and then not carried out.

const NB_RM_UP = `<svg viewBox="0 0 16 16" aria-hidden="true">
  <path d="M8 12.6V3.7"/><path d="M4.4 7.3 8 3.7l3.6 3.6"/></svg>`;
const NB_RM_DOWN = `<svg viewBox="0 0 16 16" aria-hidden="true">
  <path d="M8 3.4v8.9"/><path d="M11.6 8.7 8 12.3 4.4 8.7"/></svg>`;

// A tray with something going into it: put aside, not thrown away. The state
// between "do this" and "we are not doing this", and the only one of the
// three that can be undone, which is why it is a toggle and the bin is not.
const NB_RM_SHELF = `<svg viewBox="0 0 16 16" aria-hidden="true">
  <path d="M2.2 9.4h3l.9 1.6h3.8l.9-1.6h3"/>
  <path d="M2.2 9.4v3.2h11.6V9.4"/>
  <path d="M8 2.2v5"/><path d="M5.9 5.1 8 7.2l2.1-2.1"/></svg>`;

// Which step a group would hand over next: the first that has not gone. The
// order is the whole point of a group: send the third before the second and
// it lands on a tree the second was supposed to have made, so only that one,
// and any already sent, can be sent at all.
// Whether a row can be handed to a session: asked by the arrow that offers
// it and by the redraw that decides whether an armed one is still valid.
//
// One function because it used to be two, and they disagreed: the arrow on a
// sent row was live (that is the whole "it did not take, do it again" case)
// while the redraw dropped the selection the moment it was made, so picking
// one armed nothing and the send controls never came up.
function nbRmCanSend(nb, r, idx, live){
  // Nothing goes out while the panel is holding unsaved work. The line about
  // to be typed into a session is one of the things that might be unsaved, so
  // sending against a list the server has not been told about would hand over
  // a step that does not exist there, and the session would then go and read
  // a roadmap that says something else. Save first, or throw it away first;
  // either way the list a step comes from is the list on disk.
  if (nb.nbUnsaved()) return false;
  if (!live || r.shelved) return false;
  const steps = r.steps || [];
  if (idx < 0) return steps.length ? nextStep(r) !== null : true;
  const st = steps[idx];
  // The frontier, or one that has already gone. Never a later one: send the
  // third before the second and it lands on a tree the second was to make.
  return !!st && (idx === nextStep(r) || stepGone(st));
}

// What a row knows: an item's when-added and by whom, how
// far its plan has got and when it was last sent; a step's when-done and
// when-sent. Drawn in the row's fold, with its details and its actions.
function nbRmRowFacts(nb, r, idx){
  const st = idx < 0 ? r : (r.steps || [])[idx] || {};
  // A step from another item says which, by the number it answers to
  // there: the one a session knows it by.
  const from = idx >= 0 && Array.isArray(st.sid) && st.sid.length === 2 && String(st.sid[0]) !== String(r.id)
    ? (st.sid[1] ? `R${st.sid[0]} step ${st.sid[1]}` : `R${st.sid[0]}, folded in`) : "";
  if (idx >= 0) return factGrid([["Done", st.done ? rmDay(st.done) : ""], ["Sent", st.sent ? rmDay(st.sent) : ""], ["Was", from]]);
  const steps = r.steps || [];
  return factGrid([["Added", r.added ? `${rmDay(r.added)}, by ${byWho(r.by || "you", r)}` : ""],
                   ["Target", r.target || ""],
                   ["Plan", steps.length ? `${steps.filter(x => x.done).length} of ${steps.length} steps done` : ""],
                   ["Sent", r.sent ? rmDay(r.sent) : ""],
                   ["Changelog", clRefs((nb.roadmapChangelog || {})["R" + r.id]), {html: true}]]);
}

function nbRmStepRow(nb, r, idx, live){
  const steps = r.steps || [];
  const nxt = nextStep(r);
  const st = idx < 0 ? r : steps[idx];
  // Shelving is an item's business, never a step's: parking one step of a
  // plan and leaving the rest live is not a state a plan can be in: the
  // thing you have decided not to do now is the whole plan. So the shelf
  // button sits on the item row, and a group is shelved entire.
  //
  // The bin is on every row. It used to be on the head of the queue only:
  // things come off a plan from the front, which meant a stale step three
  // cost you steps one and two to reach, and left the list describing work
  // nobody was going to do. That guardrail was aimed at the wrong risk: the
  // order that matters is the order things are *sent* in, and the frontier
  // rule below is what protects it. A deletion cannot send anything out of
  // order; it can only make a plan shorter, and it now says why it did and
  // keeps the words in the log.
  const shelf = idx < 0;
  // Sent ones stay live so they can go again; "it did not take, do it again"
  // is the reason they are still on screen at all.
  // A crossed line cannot be sent. Un-cross it first; that is one tap, and
  // it makes the struck-through state mean one thing instead of two.
  //
  // A group's own arrow is its next step's arrow: the plan is the item, and
  // reaching for the title to send "the next bit of this" is what a hand
  // does. Picking either highlights both, because they are one choice.
  const can = nbRmCanSend(nb, r, idx, live);
  const why = nb.nbUnsaved() ? `save or revert first: ${nb.nbUnsaved()} not on disk yet`
            : r.shelved ? "shelved: take it off the shelf to send it"
            : !live ? "no session is running here"
            : st.done ? "a session finished this: sending it again says it did not"
            : st.sent ? "this one has gone already: pick it to send it again"
            : idx < 0 && steps.length
              ? (nxt === null ? "every step of this has gone"
                              : `pick step ${nxt + 1}, the next one in line`)
            : idx < 0 ? "pick this to send"
            : idx === nxt ? "pick this to send"
            : `step ${nxt + 1} comes first`;
  // The row open (rows-you-open): the number, the words and Send
  // closed; the workings and what can be done to the line (shelve, reword,
  // drop) on the open row. Which rows are open survives a redraw.
  const isOpen = nb.roadmapOpen.has(`${r.id}:${idx}`);
  // Both halves of a group light up together.
  const on = nb.roadmapSel && String(nb.roadmapSel.id) === String(r.id)
             && (idx < 0 ? (steps.length ? true : nb.roadmapSel.step === null)
                         : nb.roadmapSel.step === idx);
  // The tags sit above the line rather than beside it: they are labels on the
  // whole item, and on a phone a pill sharing the first line pushed the words
  // into a column two thirds as wide as the ones under it.
  // ...and the release it is meant for, where one is set.
  // A step meant for a release of its own says so; one with none
  // goes with its item and carries no tag. An item an agent put here
  // names that agent.
  const tags = idx >= 0 ? (st.target ? `<span class="tag ver" title="this step is meant to ship in ${esc(st.target)}">for ${esc(st.target)}</span>` : "")
    : (r.target ? `<span class="tag ver" title="meant to ship in ${esc(r.target)}">for ${esc(r.target)}</span>` : "")
    + (r.by === "claude" ? `<span class="tag who" title="${esc(agentAsker(r))} put this here">${esc(agentAsker(r).toLowerCase())}</span>` : "");
  // In reorder mode the row's three controls are replaced rather than joined:
  // five buttons and a number do not fit a phone, and moving things about is
  // not something anybody does at the same time as sending them.
  // A step that has gone does not move, and by mark rather than by prefix:
  // a session can finish step three with one and two still to send.
  const fixed = idx >= 0 && (stepGone(st)
    || (steps[idx - 1] && stepGone(steps[idx - 1]))
    || (steps[idx + 1] && stepGone(steps[idx + 1])));
  const moves = `<button class="eye mv" type="button" data-dir="-1"${
      fixed ? " disabled" : ""} aria-label="up"
      title="${fixed ? "a step that has gone stays where it is" : "move it up"}"
      >${NB_RM_UP}</button>
    <button class="eye mv" type="button" data-dir="1"${fixed ? " disabled" : ""}
      aria-label="down"
      title="${fixed ? "a step that has gone stays where it is" : "move it down"}"
      >${NB_RM_DOWN}</button>`;
  // The send is the Claude mark, first of the row's own buttons on the
  // right; the fold's caret takes the arrow's old
  // place on a group's row, level with the first line of its words.
  // A role that reads the project and does not write it: the row
  // carries nothing that changes the list or sends from it.
  const ro = projWriteWhy(nb.memProj);
  const send = nb.roadmapOrdering || ro ? "" : `<button class="eye go${on ? " sel" : ""}" type="button"${can ? "" : ` aria-disabled="true"`}
      title="${esc(why)}" aria-label="send to ${esc(sendAgent(nb.memProj).name)}"
      aria-pressed="${on ? "true" : "false"}">${SPARK}</button>`;
  // In reorder mode a step can be dragged onto another item's row:
  // the same move as Move to, by hand.
  return `<div class="roadmap${st.sent ? " sent" : ""}${st.done ? " done" : ""}${
       idx >= 0 ? " step" : ""}${r.shelved ? " shelved" : ""}"
       data-id="${r.id}" data-step="${idx}"${nb.roadmapOrdering && idx >= 0 && !ro ? ' draggable="true"' : ""}>
    ${idx < 0 ? `<span class="eye fold" aria-hidden="true"></span>` : ""}
    ${idx >= 0 ? (st.done
        ? `<span class="n tick" title="step ${idx + 1}: a session finished this ${nb.stamp(st.done)}">✓</span>`
        : `<span class="n">${idx + 1}</span>`)
               : r.id < 0
                 ? `<span class="n id new" title="not saved yet; it gets its number when you press Save">new</span>`
                 : `<span class="n id" title="item R${r.id}: a session knows it by that number">R${r.id}</span>`}
    <span class="body">
      ${tags ? `<span class="tags">${tags}</span>` : ""}
      <span class="txt" role="textbox" tabindex="0">${esc(st.text)}</span>
      ${nb.roadmapOrdering ? "" : `<button type="button" class="dtog" aria-expanded="${isOpen}"
        title="${st.info ? "the technical half: files, functions, approach, and what can be done to this line" : "what can be done to this line"}">${
      isOpen ? "▾" : "▸"} ${st.info ? "details" : "more"}</button>
      ${(() => { const f = nbRmRowFacts(nb, r, idx); return f ? `<div class="dfacts"${isOpen ? "" : " hidden"}>${f}</div>` : ""; })()}
      ${st.info ? `<div class="dinfo"${isOpen ? "" : " hidden"}>${esc(st.info)}</div>` : ""}
      ${ro ? "" : `<div class="rowacts actbar"${isOpen ? "" : " hidden"}>${idx < 0 ? `<button class="dn" type="button"
        title="tick it off: it moves to Finished with its plan, and Reopen there puts it back until a release ships it">Done</button>` : ""}${shelf ? `<button class="x${r.shelved ? " on" : ""}" type="button"
        aria-label="${r.shelved ? "take it off the shelf" : "shelve it"}"
        title="${r.shelved
          ? "take it off the shelf: back among the live ones"
          : "shelve it: kept at the bottom"
            + (steps.length ? " with its steps" : "") + ", not for now"}"
        >${r.shelved ? "Unshelve" : "Shelve"}</button>` : ""}
      <button class="ed" type="button" aria-label="reword" title="reword this line">Reword</button>${
      idx >= 0 ? `<button class="mvto" type="button" title="move this step to another item, whole: its details, its marks and its number">Move to</button>`
      : steps.length ? `<button class="split" type="button" title="move some of its steps to a new item, which points back here">Split</button>` : ""}${
      idx < 0 ? `<button class="foldin" type="button" title="make this item a step of another, its steps following; Put back under History undoes it">Fold into</button>` : ""}
      <button class="rm danger" type="button" aria-label="drop it"
        title="${idx < 0 ? "take it off the list, with a note saying why"
                         : "drop this step; the one behind it takes its place"}"
        >Drop</button></div>`}`}
    </span>
    ${nb.roadmapOrdering ? moves : send}
  </div>`;
}

// `force` is "the person just did this", and only a redraw somebody asked
// for may take the list apart while a box is open in it.
//
// The reword box, the drop box, the send note and the + step field are
// imperative DOM under a row, so the innerHTML below takes them and every
// word typed into them. The poll's own guard upstream watches for STAGED
// changes, and typing is not staged until the box's Save, so a session
// running `aerie roadmap add` in the background deleted a half-written
// rewording under the finger holding it. Bugs has skipped its redraw while
// a form is open since it was built; this is the same rule on the one view
// that did not have it. `nb.roadmapItems` is still updated underneath, so
// the next deliberate action draws with whatever arrived meanwhile.
// Is there a box in the list that a redraw would take something from?
//
// The reword box, the drop confirmation and the send note are deliberate
// states a person leaves by Save or Cancel, so they are protected whenever
// they are open, the way the Bugs form is. The `+ step` field is not: it
// STAYS open after each step so several can be typed in a row, and
// protecting an open one unconditionally would mean an empty box nobody
// closed freezes this panel for the rest of the day. So that one is
// protected while it holds words or holds the cursor, and is fair game
// otherwise, which is the state it spends most of its life in.
function nbRmBoxHolding($){
  const list = $("roadmapList");
  if (list.querySelector(".editbox, .dropbox, .sendbox")) return true;
  return [...list.querySelectorAll(".addstep textarea")].some(
    t => t.value.trim() !== "" || document.activeElement === t);
}

function nbRmDraw($, nb, j, force){
  if (j.error){ drawHTML($("roadmapList"), `<div class="hint bad">${esc(j.error)}</div>`); return; }
  if (!force && nbRmBoxHolding($)) return;
  // Every read and every write hands back where the list has got to, so the
  // poll below can tell this panel's own change from somebody else's. Without
  // it every write is followed by a redraw a second later, which detaches
  // whatever inline box was open (a send box, a drop confirmation) under
  // the finger that opened it.
  if (j.rev !== undefined) nb.roadmapRev = j.rev;
  // Whether there is a session to send into, from the answer OR from the
  // page's own session list, which is what lights the Claude button on
  // the project row. The two are the same fact read from the same place
  // on the server, and reading it here from one source only is what let
  // the row say running while every arrow here said no session:
  // an answer drawn before the list caught up stood until something else
  // redrew, and nothing said which of the two to believe.
  const sess = j.session || (nb.memProj
                             ? myLiveSession(nb.memProj) : null);
  j = Object.assign({}, j, {session: sess});
  const rows = j.items || [], live = !!sess;
  // Whatever was armed may have been crossed off, dropped, or overtaken by a
  // step in front of it since the last draw.
  if (nb.roadmapSel){
    const r = rows.find(x => String(x.id) === String(nb.roadmapSel.id));
    const ok = r && (nb.roadmapSel.step === null
      ? !(r.steps || []).length && nbRmCanSend(nb, r, -1, live)
      : nbRmCanSend(nb, r, nb.roadmapSel.step, live));
    if (!ok) nb.roadmapSel = null;
  }
  nb.roadmapSession = j.session || null;
  // Shelved ones are not counted, here or on the project row: "still to send"
  // is a question about live work, and a parked item is not asking.
  const left = rows.reduce((n, r) =>
    n + (r.shelved || nextStep(r) === null ? 0 : 1), 0);
  const parked = rows.filter(r => r.shelved).length;
  // What the list is for is its empty state.
  $("roadmapEmpty").hidden = !!rows.length;
  // The finished count rides a read; a redraw from the page's own state
  // (the search, a chip) keeps the last one.
  if (j.finished_n !== undefined) nb.roadmapFinishedN = j.finished_n;
  if (j.releases !== undefined) nb.roadmapReleases = j.releases;
  if (j.changelog !== undefined) nb.roadmapChangelog = j.changelog;
  const finishedN = nb.roadmapFinishedN || 0;
  // The glance (the Containers page's top): what is left to send,
  // shelved and finished as tiles, none while the list is empty, whose
  // empty state is the hint where it would be...
  viewGlance($("roadmapHint"), !rows.length && !finishedN ? [] : [
    {label: "to send", value: left},
    {label: "shelved", value: parked, omit: !parked},
    {label: "finished", value: finishedN, omit: !finishedN}]);
  // ...and its status line: whether a step can be sent, after what is
  // staged (the bar's own words, syncSave's). No session holds the arrows,
  // a running one lights them.
  // The session by its agent, not its tmux name.
  setText($("roadmapSess"), live ? `${agentOfSession(tmuxBase(j.session))?.agent.name || "A session"} running` : "no session running");
  $("roadmapField").hidden = !rows.length && !finishedN;
  // The band that narrows it: All, Open and Shelved, and the search on
  // the control row.
  nb.roadmapChip = ["", "open", "shelved"].includes(nb.roadmapChip) ? nb.roadmapChip : "";
  const chips = chipButtons([{key: "open", label: "Open", count: rows.length - parked},
                             {key: "shelved", label: "Shelved", count: parked}], nb.roadmapChip, "data-rmchip");
  const view = () => $("roadmapList")?.closest(".nbview");
  chipBand($("roadmapChips"), chips, "data-rmchip", view, "#roadmapList > details.grp",
           k => { nb.roadmapChip = k; nbRmRedraw($, nb, false); });
  setHidden($("roadmapFind"), rows.length + finishedN < 2 && !nb.roadmapFind);
  // ...and by the release an item is meant for: a
  // chip per target, oldest first, and No target; the Finished section
  // narrows by it too, so what went into a release can be read back.
  const vers = versionChips(rows, rmVers, "No target");
  if (nb.roadmapVer && !vers.some(v => v.key === nb.roadmapVer)) nb.roadmapVer = "";
  const verChips = chipButtons(vers, nb.roadmapVer, "data-rmver", undefined, "Any version");
  // One band for every group, drawn while any group has two.
  setHidden($("roadmapFilter"), !chips && !verChips);
  chipBand($("roadmapVers"), verChips, "data-rmver", view, "#roadmapList > details.grp, #roadmapDoneList > details.grp",
           k => { nb.roadmapVer = k; nbRmRedraw($, nb, false); if (nb.roadmapDone) nb.drawFinished(); });
  const q = (nb.roadmapFind || "").trim().toLowerCase();
  const shown = r => (!nb.roadmapChip || (nb.roadmapChip === "shelved") === !!r.shelved) && rmVer(r, nb.roadmapVer) && rmMatch(r, q);
  setHidden($("roadmapDoneSect"), !finishedN);
  setText($("roadmapDoneN"), finishedN ? String(finishedN) : "");
  // An open section fetches again when what it holds is not what the
  // count says: forgotten by a reload, or an item finished or reopened
  // since (a session ticking one off while it is open).
  if ($("roadmapDoneSect").open && !nb.roadmapDoneAsking
      && (nb.roadmapDone === null || nb.roadmapDone.length !== finishedN)) nbRmLoadFinished($, nb);
  if (nb.roadmapLogOn) nb.drawHistory();
  // A role that reads the project and does not write it.
  const ro = projWriteWhy(nb.memProj);
  // Only the items the band shows are built, a page at a time (pageLimit):
  // every item was built, those the band left out hidden,
  // and all but 25 of the rest.
  const vis = rows.filter(shown);
  {
  // A group is a fold, like a bug's row: its own
  // row is the summary, its steps open under it on a tap. Which were
  // open before this redraw stay open, so acting on one does not fold
  // it, and a group whose step is armed is open to show it.
  const held = new Set([...$("roadmapList").querySelectorAll("details.grp[open]")].map(d => d.dataset.id));
  const lim = pageLimit($("roadmapList"), "roadmapList", vis.length);
  drawHTML($("roadmapList"), vis.slice(0, lim).map(r =>
    // The group's own row gets the same `live` as its steps now: its arrow
    // stands for the next one, so it is as clickable as that one is.
    `<details class="grp${r.shelved ? " shelved" : ""}" data-id="${r.id}"${
      held.has(String(r.id)) || (nb.roadmapSel && String(nb.roadmapSel.id) === String(r.id)) ? " open" : ""}>
        <summary>${nbRmStepRow(nb, r, -1, live)}</summary>${
      (r.steps || []).map((_, i) => nbRmStepRow(nb, r, i, live)).join("")}${
      // How a plain item becomes a plan: give it a step. Hidden while
      // reordering, where the question is only where things sit.
      nb.roadmapOrdering || ro ? "" : `<div class="addstep" data-id="${r.id}"><button
        type="button" class="link">Add a step</button></div>`}</details>`).join(""));
  // The row's ground and its words open and shut the fold, on the same
  // tween a bug's row uses; a control on the row acts and does not fold.
  // Bound on the summary rather than the toggle event, because toggle
  // fires after the browser has already snapped it open.
  $("roadmapList").querySelectorAll("details.grp > summary").forEach(sm => {
    sm.onclick = e => {
      e.preventDefault();
      if (e.target.closest("button, a, input, textarea, select, .dtog, .dinfo")) return;
      slideDetails(sm.parentElement, !foldOpen(sm.parentElement));
    };
  });
  $("roadmapList").querySelectorAll(".addstep").forEach(box => {
    box.querySelector("button").onclick = () => nbRmOpenStepInput($, nb, box);
  });
  $("roadmapList").querySelectorAll(".roadmap").forEach(row => {
    const id = Number(row.dataset.id), step = Number(row.dataset.step);
    row.querySelectorAll(".mv").forEach(b => b.onclick = () =>
      nbRmMoveLocally($, nb, id, step < 0 ? null : step, Number(b.dataset.dir)));
    const go = row.querySelector(".go");
    // A group's title arrow stands for its next step, so both resolve to the
    // same choice and light up together.
    if (go) go.onclick = () => {
      // A dead arrow says why when pressed. It is aria-disabled
      // rather than disabled because a disabled button swallows the press
      // and the reason was only in its hover title, which a finger never
      // sees, and in the line under the whole list.
      if (go.getAttribute("aria-disabled") === "true") return notify(saidOf(go), true);
      const r = (nb.roadmapItems || []).find(x2 => String(x2.id) === String(id));
      const steps = r?.steps || [];
      nbRmPick($, nb, id, step >= 0 ? step : (steps.length ? nextStep(r) : null));
    };
    // Shelving never asks: nothing is lost and the same tap undoes it. That
    // is the whole difference between it and the bin beside it.
    const x = row.querySelector(".x");
    if (x) x.onclick = () =>
      nbRmStageShelve($, nb, id, !row.classList.contains("shelved"));
    // Deleting always asks. Nothing here is recoverable, and the strike beside
    // it is the reversible answer for anyone who only meant "not this one".
    const rm = row.querySelector(".rm");
    if (rm) rm.onclick = () => nbRmOpenDrop($, nb, row, id, step);
    // Ticking off acts on the press: Reopen under Finished
    // undoes it, so it does not ask. The row goes to Finished at once and
    // comes back saying why if the server refuses (nbRmDrawDone).
    const dn = row.querySelector(".dn");
    if (dn) dn.onclick = async () => {
      const j = await nbRmPost($, nb, {action: "done", id}, false, () => nbRmDrawDone($, nb, id));
      if (!j) return;
      notify(`R${id} finished: it is under Finished, and Reopen there puts it back`);
      if ($("roadmapDoneSect").open) nbRmLoadFinished($, nb);
      else nb.roadmapDone = null;
    };
    // A pencil, and the words themselves. The pencil because a tap target you
    // can see is the only one a thumb finds; the words because that is where
    // the hand goes anyway. Steps too: a plan is written before it is right,
    // and the line that needed changing was always the one inside a group.
    const reword = () => nbRmOpenReword($, nb, row, id, step);
    // The details fold: closed by default because the row's words are the
    // decision and this is the workings, wanted when the work starts.
    const dt = row.querySelector(".dtog");
    if (dt) dt.onclick = () => {
      const info = row.querySelector(".dinfo"), acts = row.querySelector(".rowacts"), fx = row.querySelector(".dfacts");
      const show = dt.getAttribute("aria-expanded") !== "true", key = `${id}:${step}`;
      if (show) nb.roadmapOpen.add(key); else nb.roadmapOpen.delete(key);
      // The caret turns with the slide rather than after it, so the row reads
      // as one movement instead of a glyph flicking ahead of the content.
      dt.textContent = `${show ? "▾" : "▸"} ${info ? "details" : "more"}`;
      dt.setAttribute("aria-expanded", String(show));
      if (info) slideHidden(info, show);
      if (fx) slideHidden(fx, show);
      if (acts) slideHidden(acts, show);
    };
    // Guarded like every other control on this row: reordering replaces all
    // three of them, so in that mode there is no pencil to bind and an
    // unguarded one took the whole redraw down with it.
    const ed = row.querySelector(".ed");
    if (ed) ed.onclick = reword;
    // A step's words reword it; a group's words open its fold,
    // and the pencil is what rewords those.
    if (step >= 0 && !ro) row.querySelector(".txt").onclick = reword;
    // Between items: a step moved to another, an item split into
    // new ones, or folded into another. Each lands at once, not staged:
    // what moves is on two items, and the page's staging is per row. Each
    // is drawn on the press, and put back if the server refuses it.
    const mvto = row.querySelector(".mvto");
    if (mvto) mvto.onclick = () => nbRmPickItem(nb, row, `Move step ${step + 1} to`, "Move", id, to =>
      nbRmPost($, nb, {action: "step-mv", id, step, to}, false, () => nbRmDrawStepMv($, nb, id, step, to))
        .then(j => j && notify(`step ${step + 1} of R${id} is R${to} step ${j.step + 1} now`)));
    const sp = row.querySelector(".split");
    if (sp) sp.onclick = () => nbRmOpenSplit($, nb, row, id);
    const fi = row.querySelector(".foldin");
    if (fi) fi.onclick = () => nbRmPickItem(nb, row, `Fold R${id} into`, "Fold", id, into =>
      nbRmPost($, nb, {action: "fold", id, into}, false, () => nbRmDrawFold($, nb, id, into))
        .then(j => j && notify(`R${id} is R${into} step ${j.folded[1]} now; Put back under History undoes it`)));
    if (row.getAttribute("draggable") === "true"){
      row.ondragstart = e => { e.dataTransfer.setData("text/plain", `${id}:${step}`); e.dataTransfer.effectAllowed = "move"; row.classList.add("dragging"); };
      row.ondragend = () => row.classList.remove("dragging");
    }
    if (nb.roadmapOrdering && step < 0 && !ro){
      row.ondragover = e => { e.preventDefault(); row.classList.add("dropat"); };
      row.ondragleave = () => row.classList.remove("dropat");
      row.ondrop = e => {
        e.preventDefault(); row.classList.remove("dropat");
        const [fid, fstep] = String(e.dataTransfer.getData("text/plain") || "").split(":").map(Number);
        if (!fid || isNaN(fstep) || fstep < 0 || fid === id) return;
        nbRmPost($, nb, {action: "step-mv", id: fid, step: fstep, to: id}, false, () => nbRmDrawStepMv($, nb, fid, fstep, id))
          .then(j => j && notify(`step ${fstep + 1} of R${fid} is R${id} step ${j.step + 1} now`));
      };
    }
  });
  }
  nb.roadmapItems = rows;
  nb.roadmapUnsaved = j.unsaved || {};
  if (j.batch !== undefined) nb.noteBatch(j.batch);
  nb.drawBatchNote();
  nb.syncSave();
  $("roadmapOrder").hidden = !rows.length || !!ro;
  // No Add to roadmap for a role that only reads
  // (what a role does not give is not drawn), and its box shut.
  if (ro && !$("roadmapForm").hidden) nbRmForm($, false);
  $("roadmapShow").hidden = !!ro;
  $("roadmapOrder").classList.toggle("on", nb.roadmapOrdering);
  $("roadmapLog").classList.toggle("on", nb.roadmapLogOn);
  nbRmDrawSendBox($, nb, live);
  // Groups, not steps: a plan cut in half by a page boundary is a plan
  // nobody can read.
  paginate($("roadmapList"), ":scope > .grp", {key: "roadmapList", noun: "items", total: vis.length,
                                               more: () => nbRmRedraw($, nb, false)});
}

// The box itself, built once and used by both lists.
//
// The roadmap hands a step to a session and the tracker hands it a bug; the
// question either asks is the same one (anything to add, go or don't), so it
// is one box rather than two that drift apart. Model and effort are not asked
// here and are no longer applied here either: they are the project's own
// setting, in its settings dialog, and bb-tty passes them as launch flags, so
// a session that is up is already on them and a send is just the send. What
// used to sit here typed /model ahead of the step, which stopped working the
// day claude put a confirmation behind that command.
function nbRmSendBoxEl(nb, {label, sub, placeholder, onSend, onCancel}){
  const box = document.createElement("div");
  box.className = "sendbox ctlown";
  drawHTML(box, `<div class="q">${esc(label)}${
      sub ? ` <span>· ${esc(sub)}</span>` : ""}</div>
    <textarea id="sendMore" rows="2" maxlength="4000"
      placeholder="${esc(placeholder)}"></textarea>
    <div class="actbar">
      <button type="button" class="stop">Cancel</button>
      <button type="button" class="primary" id="roadmapGo">Send</button></div>`);
  const more = box.querySelector("#sendMore");
  more.value = nb.sendNoteText;
  // Kept on every keystroke rather than read at the end: a redraw between the
  // typing and the Send would otherwise take the words with it.
  more.oninput = () => { nb.sendNoteText = more.value; };
  more.onkeydown = e => {
    if (e.key === "Escape"){ e.preventDefault(); e.stopPropagation(); onCancel(); }
  };
  box.querySelector(".stop").onclick = onCancel;
  box.querySelector("#roadmapGo").onclick = onSend;
  return box;
}

// Only ever one open, anywhere in THIS notebook: two half-written notes
// with one Send between them is a message going to the wrong place, and
// the Bugs view shares this one with the Roadmap, which is why it is not
// scoped to the list.
//
// This notebook and not the page: two projects can be open side by side,
// and their notes go to two different sessions, so neither is the other's
// ambiguity. Swept page-wide, opening a note in one project deleted a
// half-written one in the other.
function nbRmShutSendBoxes($){
  // The clone this view lives in: makeNotebook puts the project on its
  // root, and every id inside it is the template's, so there is no id to
  // reach it by. The state object holds no element.
  const here = $("roadmapList")?.closest("[data-project]");
  (here || document).querySelectorAll(".sendbox").forEach(b => b.remove());
}

// The roadmap's, under the step it would send.
//
// Rebuilt on every draw rather than parked somewhere and moved: the rows are
// replaced wholesale by the redraw above, so a box held over would be sitting
// under whatever row happened to take that place. Cheap, and it cannot end up
// pointing at the wrong line.
function nbRmDrawSendBox($, nb, live){
  const list = $("roadmapList");
  list.querySelectorAll(".sendbox").forEach(b => b.remove());
  if (!nb.roadmapSel || !live || nb.roadmapOrdering || nb.roadmapLogOn){ nb.sendShownFor = ""; return; }
  const step = nb.roadmapSel.step === null ? -1 : nb.roadmapSel.step;
  const row = list.querySelector(
    `.roadmap[data-id="${CSS.escape(String(nb.roadmapSel.id))}"][data-step="${step}"]`);
  if (!row){ nb.sendShownFor = ""; return; }
  const box = nbRmSendBoxEl(nb, {
    label: "Send this one?",
    sub: step >= 0 ? `step ${step + 1}` : "",
    placeholder: "anything to send with it (optional)",
    onSend: () => nbRmReallySend($, nb),
    onCancel: () => nbRmPick($, nb, nb.roadmapSel.id, nb.roadmapSel.step),
  });
  row.after(box);
  // Only the first time this arrow arms, never again while it stays armed:
  // the box is rebuilt on every draw, and a poll landing while it is open
  // would otherwise replay the arrival two or three times a minute.
  const key = `${nb.roadmapSel.id}:${step}`;
  if (key !== nb.sendShownFor) arriveBox(box);
  nb.sendShownFor = key;
}

// Picking one arms the Send button; picking it again puts it down. The
// highlight is the whole confirmation: the line it would send is the line the
// arrow is sitting next to, and a sentence repeating it back was noise.
function nbRmPick($, nb, id, step){
  nb.roadmapSel = (nb.roadmapSel && String(nb.roadmapSel.id) === String(id) && nb.roadmapSel.step === step)
    ? null : {id, step};
  // A new target starts with an empty note. The text survives a *redraw* of
  // the box it was typed into, which is what the variable is for, but it
  // must not follow you to another step, or to a bug on the other tab, where
  // it would arrive pre-filled with words written about something else.
  nb.sendNoteText = "";
  nbRmDraw($, nb, {items: nb.roadmapItems, session: nb.roadmapSession, unsaved: nb.roadmapUnsaved}, true);
}

// Putting the selection down, and the box with it. It redraws rather than
// only clearing the variable: the box and the lit arrow are both drawn from
// nb.roadmapSel, and a sent row stays selectable now (that is the point of being
// able to send it again), so nothing else is going to take them off screen.
function nbRmCancelSend($, nb){
  nb.roadmapSel = null;
  nbRmDraw($, nb, {items: nb.roadmapItems, session: nb.roadmapSession, unsaved: nb.roadmapUnsaved}, true);
}

async function nbRmReallySend($, nb){
  if (!nb.roadmapSel) return;
  let {id, step} = nb.roadmapSel;
  // Always told, where this used to be a checkbox. The question the checkbox
  // asked ("shall I mention the list moved?") cannot have a useful "no" any
  // more: nothing can be sent until the panel is saved, so by the time a step
  // goes there IS no unsaved work to keep quiet about, and a session about to
  // act on a step is exactly who wants to know the plan around it changed.
  // It costs nothing when nothing moved: the note is empty and rides as "".
  const proj = nb.memProj;
  // Held in locals: the box is rebuilt by every redraw between here and the
  // end of this function, so the button read back at the end is not
  // necessarily the one that was pressed, but a switch that was asked for
  // still has to be the one that gets sent.
  const note = nb.sendNoteText;
  const go = $("roadmapGo");
  busy(go, "Sending");
  // Staged changes go first, always, not only when "also save" is ticked.
  // The line about to be typed into a session is one of them, and sending it
  // against a list the server has not been told about would hand over a step
  // that does not exist there. An item added in this panel has a negative id
  // until that flush; the real one comes back from it.
  if (nb.roadmapPending.length){
    nb.clashResume = null;                 // settled by hand, then Send again
    const map = await nbRmFlushPending($, nb);
    if (map.has(String(id))) id = map.get(String(id));
    // Refused: the step about to be typed into a session is described by a
    // list the server has not accepted, so it must not go.
    if (nb.roadmapPending.length){
      unbusy(go, "Send");
      return;
    }
  }
  // The note rides on the same line as the step rather than chasing it: two
  // messages into one input box is how the second ends up glued to the first.
  const to = await pickSend(nb.memProj);
  if (to === null){ unbusy(go, "Send"); return; }
  const j = await nbRmPost($, nb, {action: "send", id, step, tell: true, note, session: to});
  unbusy(go, "Send");
  if (!j) { nbRmDrawSendBox($, nb, !!nb.roadmapSession); return; }
  if (!sendOutcome(j)){
    nbRmDrawSendBox($, nb, !!nb.roadmapSession);
    return;
  }
  // Cleared only once it has gone. The pickers are a standing preference and
  // stay; a note belongs to the one thing it was written for, and finding it
  // still sitting there on the next step is how it ends up sent twice.
  nb.sendNoteText = "";
  nbRmCancelSend($, nb);
  // The notebook stays open behind it now. Sending used to close the panel
  // because a modal was in the way of the tab you were being sent to; a tab
  // is not in the way of anything, and coming back to the plan to send its
  // next step is the ordinary next thing.
  openSentTo(proj);             // opens the tab, or goes to the one that is there
}

// The roadmap's write (nbPoster), for the space that is open. No hold is
// asked about here: a session's batch holds the staged changes at their
// Save (nbCoreBarSays), and a send or a step marked done goes through.
// `now` draws what the write will do on the press, and gives back how to
// put it back (nbPoster's opts.now).
function nbRmPost($, nb, body, quiet, now){
  return nbPoster(nb, "/api/roadmap", {
    proj: () => nb.memProj, hold: false,
    // Somebody else wrote this item first (roadmap #26). Not a toast: the op
    // stays at the head of the queue and the band asks which version wins,
    // because the alternative (applying it) is how one of the two writers
    // silently loses their words.
    conflict: j => { nbRmShowClash($, nb, body, j); return null; },
    // quiet: one of a run of moves being flushed, where redrawing between
    // each would flicker the list through every intermediate arrangement.
    ok: j => { if (!quiet){ nbRmDraw($, nb, j, true); refresh(); } },
  })(body, {now});
}

// ---- drawn on the press ----------------------------------------------------
// What a write between items will do, done to the page's own copy and drawn
// before the server answers (a press must never look
// as if nothing happened). Each answers how to put it back, which nbPoster
// calls when the write is refused; one that landed is drawn again from the
// answer, so the guess stands only for the round trip.

// An item ticked off: off the list and into Finished, its count with it.
function nbRmDrawDone($, nb, id){
  const i = nb.roadmapItems.findIndex(r => String(r.id) === String(id));
  if (i < 0) return null;
  const [r] = nb.roadmapItems.splice(i, 1);
  const went = {...r, done_at: Math.floor(Date.now() / 1000), reopenable: true};
  if (nb.roadmapDone) nb.roadmapDone.unshift(went);
  nb.roadmapFinishedN = (nb.roadmapFinishedN || 0) + 1;
  nbRmRedraw($, nb); nbRmDrawFinished($, nb);
  return () => {
    if (!nbRmFindRow(nb, id)) nb.roadmapItems.splice(Math.min(i, nb.roadmapItems.length), 0, r);
    if (nb.roadmapDone) nb.roadmapDone = nb.roadmapDone.filter(x => x !== went);
    nb.roadmapFinishedN = Math.max(0, (nb.roadmapFinishedN || 0) - 1);
    nbRmRedraw($, nb); nbRmDrawFinished($, nb);
  };
}

// ...and one reopened: out of Finished and back among the live ones, as it
// was when it went.
function nbRmDrawReopen($, nb, id){
  const i = (nb.roadmapDone || []).findIndex(r => String(r.id) === String(id));
  if (i < 0) return null;
  const [r] = nb.roadmapDone.splice(i, 1);
  const {done_at, done_by, reopenable, ...row} = r;
  nb.roadmapItems.splice(nb.roadmapItems.filter(x => !x.shelved).length, 0, row);
  nb.roadmapFinishedN = Math.max(0, (nb.roadmapFinishedN || 0) - 1);
  nbRmRedraw($, nb); nbRmDrawFinished($, nb);
  return () => {
    nb.roadmapItems = nb.roadmapItems.filter(x => x !== row);
    if (nb.roadmapDone && !nb.roadmapDone.includes(r)) nb.roadmapDone.splice(Math.min(i, nb.roadmapDone.length), 0, r);
    nb.roadmapFinishedN = (nb.roadmapFinishedN || 0) + 1;
    nbRmRedraw($, nb); nbRmDrawFinished($, nb);
  };
}

// A step moved to another item (Move to, or dragged onto its row): out of
// this one's plan and onto the end of that one's, saying the item and number
// it was, as the server marks it.
function nbRmDrawStepMv($, nb, id, step, to){
  const r = nbRmFindRow(nb, id), t = nbRmFindRow(nb, to);
  const st = r?.steps?.[step];
  if (!st || !t) return null;
  const went = {...st, sid: Array.isArray(st.sid) ? st.sid : [Number(id), step + 1]};
  r.steps.splice(step, 1);
  (t.steps = t.steps || []).push(went);
  nbRmRedraw($, nb);
  return () => {
    const at = (t.steps || []).indexOf(went);
    if (at >= 0) t.steps.splice(at, 1);
    if (!(r.steps || []).includes(st)) (r.steps = r.steps || []).splice(Math.min(step, r.steps.length), 0, st);
    nbRmRedraw($, nb);
  };
}

// An item folded into another: its line a step at the end of that one's
// plan, its own steps after it.
function nbRmDrawFold($, nb, id, into){
  const i = nb.roadmapItems.findIndex(r => String(r.id) === String(id)), t = nbRmFindRow(nb, into);
  if (i < 0 || !t) return null;
  const [r] = nb.roadmapItems.splice(i, 1);
  const came = [{text: r.text, ...(r.info ? {info: r.info} : {}), sent: r.sent || 0}, ...(r.steps || [])];
  const had = (t.steps || []).slice();
  t.steps = [...had, ...came];
  nbRmRedraw($, nb);
  return () => {
    t.steps = had;
    if (!nbRmFindRow(nb, id)) nb.roadmapItems.splice(Math.min(i, nb.roadmapItems.length), 0, r);
    nbRmRedraw($, nb);
  };
}

// An item split: the ticked steps leave it for a new item under the title
// typed, which wears "new" until the answer brings its number.
function nbRmDrawSplit($, nb, id, picked, text){
  const r = nbRmFindRow(nb, id);
  if (!r) return null;
  const had = (r.steps || []).slice();
  const made = {id: --nb.tmpId, text, by: "you", sent: 0, shelved: 0,
                steps: had.filter((_, i) => picked.includes(i + 1))};
  r.steps = had.filter((_, i) => !picked.includes(i + 1));
  nb.roadmapItems.splice(nb.roadmapItems.filter(x => !x.shelved).length, 0, made);
  nbRmRedraw($, nb);
  return () => {
    r.steps = had;
    nb.roadmapItems = nb.roadmapItems.filter(x => x !== made);
    nbRmRedraw($, nb);
  };
}

// ---- two writers, one item ------------------------------------------------
// The optimistic half of roadmap #26. The writes here are tiny and per-field,
// so they are not serialized behind a lock somebody has to remember to
// release: each one carries the revision it was read at, and the server
// refuses it if that is no longer what is stored.
//
// This is the refusal made useful. A message saying "somebody got there
// first" leaves the words that were typed with nowhere to go, which is worse
// than the overwrite it prevented: the op stays at the head of the queue, the
// stored version is shown beside the typed one, and one of two buttons
// decides it. Nothing is applied until it does.

function nbRmShowClash($, nb, op, j){ nb.clash = {op, ...j.conflict}; nbRmDrawClash($, nb); }

function nbRmSettleClash($, nb, mine){
  const c = nb.clash, go = nb.clashResume;
  nb.clash = null; nb.clashResume = null;
  if (!c) return;
  // Either way the head of the queue is what moves: mine goes again saying it
  // replaces what is there NOW, theirs wins by the op simply being dropped.
  if (mine && nb.roadmapPending[0]) nb.roadmapPending[0].was = c.current;
  else nb.roadmapPending.shift();
  nbRmDrawClash($, nb);
  // Read before the redraw above, which is what raised this the first time
  // round: nbRmDrawClash used to clear the resume itself, so settling a conflict
  // dropped the save it was part of and left the rest of the queue staged
  // with nothing to push it.
  if (go) go();
  else nb.syncSave();      // no save to carry on with: the rest stays staged
}

function nbRmDrawClash($, nb){
  const box = $("roadmapClash");
  if (!box) return;
  box.hidden = !nb.clash;
  if (!nb.clash){ box.innerHTML = ""; return; }
  const op = nb.clash.op;
  // "you" in the log means a person, and the person reading this is one, but
  // not the one who made that write, or the words would have matched. So it
  // is named as the other window rather than as them.
  const who = nb.clash.by === "claude" ? "a session" : "another window";
  const when = nb.clash.at ? " " + ago(nb.clash.at) : "";
  const theirs = String(nb.clash.current ?? "");
  const mine = op.action === "remove" ? "" : String(op.text || "");
  drawHTML(box, `
    <div class="hint bad">${who} changed this while you had it open${esc(when)}.
      Nothing has been written: pick one.</div>
    <div class="clashpair">
      <div><div class="clashwho">On the list now</div>
        <div class="clashtext">${esc(theirs) || "<em>nothing</em>"}</div></div>
      <div><div class="clashwho">Yours, not written</div>
        <div class="clashtext">${op.action === "remove"
          ? "<em>you dropped it</em>" : esc(mine) || "<em>nothing</em>"}</div></div>
    </div>
    <div class="actbar">
      <button type="button" id="clashTheirs">Keep theirs</button>
      <button type="button" id="clashMine" class="primary">Use mine</button>
    </div>`);
  $("clashTheirs").onclick = () => nbRmSettleClash($, nb, false);
  $("clashMine").onclick = () => nbRmSettleClash($, nb, true);
}

// Dropping something, with the reason it went. Inline rather than a await askYes()
// box, because a confirm cannot hold a field, and the field is the point:
// nothing here can be undone, so the only thing standing between a deleted
// line and somebody adding it straight back is a note saying why it went.
// Optional, deliberately. A reason demanded is a reason typed as "x".
function nbRmOpenDrop($, nb, row, id, step){
  if (row.nextElementSibling?.classList.contains("dropbox")) return;
  row.parentElement.querySelectorAll(".editbox,.dropbox").forEach(b => b.remove());
  const what = row.querySelector(".txt").textContent;
  const r = (nb.roadmapItems || []).find(x => String(x.id) === String(id));
  const also = step >= 0
    ? "the one behind it takes its place"
    : (r?.steps || []).length ? `its ${r.steps.length} steps go too` : "";
  dropBox(row, {q: "Drop this?", sub: also ? ` · ${also}` : "", max: 4000, place: "after",
                placeholder: "why it is going (optional, kept in the history)", verb: "Drop it", tone: "danger",
                go: why => nbRmStageRemove($, nb, id, step, why)});
}

// Which other item: a pick list of every open item but this one,
// under the row, as the other inline asks are; `go` gets its number.
function nbRmPickItem(nb, row, label, ok, id, go){
  const others = (nb.roadmapItems || []).filter(x => String(x.id) !== String(id) && x.id > 0);
  if (!others.length){ notify("there is no other item to move it to", true); return; }
  const opts = others.map(x => `R${x.id} ${x.text}`.slice(0, 80));
  askInline(row, {label, ok, options: opts}).then(got => {
    if (!got) return;
    const m = /^R(\d+)/.exec(got.trim());
    const hit = m ? others.find(x => String(x.id) === m[1])
      : others.find(x => x.text.toLowerCase().startsWith(got.trim().toLowerCase()));
    if (!hit){ notify(`${got} is not an item on this list`, true); return; }
    go(hit.id);
  });
}

// Splitting an item: tick the steps that go, name the new item,
// and Split moves them whole; the new item points back here.
function nbRmOpenSplit($, nb, row, id){
  if (row.nextElementSibling?.classList.contains("splitbox")) return;
  row.parentElement.querySelectorAll(".editbox,.dropbox").forEach(b => b.remove());
  const r = nbRmFindRow(nb, id), steps = r?.steps || [];
  const box = document.createElement("div");
  box.className = "dropbox editbox splitbox ctlown";
  // A form (a drop box that asks more than one
  // thing is a form): the steps to move, the new item's title, Cancel and
  // Split at its foot.
  drawHTML(box, formBox({fields: [
    `<div class="fcell fwide"><span class="lbl">Split R${id}: the ticked steps move to a new item, whole</span>
      <div class="splitsteps">${steps.map((st, i) => `<label><input type="checkbox" value="${i + 1}"> <span class="n">${i + 1}</span> ${esc(st.text.slice(0, 160))}</label>`).join("")}</div></div>`,
    formField(`rmSplit${id}`, "The new item's title", `<input id="rmSplit${id}" class="title" maxlength="4000" autocomplete="off" spellcheck="false">`, {wide: true})],
    foot: [`<button type="button" class="stop">Cancel</button>`, `<button type="button" class="primary">Split</button>`]}));
  row.after(box);
  arriveBox(box);
  const shut = () => box.remove();
  box.querySelector(".stop").onclick = shut;
  box.querySelector(".primary").onclick = async () => {
    const picked = [...box.querySelectorAll("input[type=checkbox]:checked")].map(c => Number(c.value));
    const text = box.querySelector(".title").value.trim();
    if (!picked.length){ notify("tick the steps that go", true); return; }
    if (!text){ notify("the new item needs a title", true); box.querySelector(".title").focus(); return; }
    shut();
    const j = await nbRmPost($, nb, {action: "split", id, groups: [{text, steps: picked}]}, false,
                             () => nbRmDrawSplit($, nb, id, picked, text));
    if (j?.held) notify("the split is held for approval on this notebook");
    else if (j) notify(`R${j.made[0].id} made with ${picked.length} step${picked.length === 1 ? "" : "s"} from R${id}`);
  };
  box.querySelector(".title").onkeydown = e => {
    if (e.key === "Enter"){ e.preventDefault(); box.querySelector(".primary").click(); }
    if (e.key === "Escape"){ e.preventDefault(); e.stopPropagation(); shut(); }
  };
}

// Rewording, in a box under the row rather than a prompt(). A prompt is one
// line by construction, and these are not any more: opening a three-line step
// in one would have flattened it on the way back, which is the kind of quiet
// data loss an edit box should never do.
function nbRmOpenReword($, nb, row, id, step){
  if (row.nextElementSibling?.classList.contains("editbox")) return;
  row.parentElement.querySelectorAll(".editbox,.dropbox").forEach(b => b.remove());
  const was = row.querySelector(".txt").textContent;
  const r0 = nbRmFindRow(nb, id);
  const wasInfo = (step < 0 ? r0?.info : r0?.steps?.[step]?.info) || "";
  const box = document.createElement("div");
  box.className = "dropbox editbox ctlown";
  // A form (a drop box that asks more than one
  // thing is a form): its words, its details and its target, Cancel and
  // Save at its foot.
  const k = `rmRw${id}${step < 0 ? "" : `s${step}`}`;
  drawHTML(box, formBox({fields: [
    formField(k, step < 0 ? "Reword it" : `Reword step ${step + 1}`, `<textarea id="${k}" maxlength="4000" spellcheck="false"></textarea>`,
      {wide: true, hint: "Enter saves, shift+Enter is a new line."}),
    formField(`${k}d`, "Details", `<textarea id="${k}d" class="dta" maxlength="20000" spellcheck="false" placeholder="mostly the agent's to write; empty is fine"></textarea>`,
      {wide: true, help: "the technical half: files, functions, approach"}),
    formField(`${k}t`, "Target", `<input id="${k}t" class="tgt" maxlength="24" autocomplete="off" spellcheck="false" inputmode="decimal" placeholder="${step < 0 ? "0.6.0" : esc(r0?.target || "0.6.0")}">`,
      {short: true, hint: step < 0 ? "The release it is meant to ship in; empty for none."
        : `The release this step ships in; empty goes with the item${r0?.target ? ` (${esc(r0.target)})` : ""}.`})],
    foot: [`<button type="button" class="stop">Cancel</button>`, `<button type="button" class="primary">Save</button>`]}));
  row.after(box);
  arriveBox(box);
  const ta = box.querySelector("textarea");
  ta.value = was;
  const dta = box.querySelector(".dta");
  dta.value = wasInfo;
  const tgt = box.querySelector(".tgt"), wasTarget = (step < 0 ? r0?.target : r0?.steps?.[step]?.target) || "";
  if (tgt) tgt.value = wasTarget;
  const shut = () => box.remove();
  box.querySelector(".stop").onclick = shut;
  box.querySelector(".primary").onclick = () => {
    const now = ta.value, nowInfo = dta.value, nowTarget = (tgt?.value || "").trim().replace(/^v/i, "");
    // The server's own check, said before Save rather than after it.
    if (tgt && nowTarget && !/^\d{1,4}\.\d{1,5}\.\d{1,6}$/.test(nowTarget)){
      notify(`${nowTarget} is not a version: a target is X.Y.Z, as 0.6.0`, true);
      tgt.focus();
      return;
    }
    shut();
    if (tgt && nowTarget !== wasTarget) nbRmStageTarget($, nb, id, nowTarget, step < 0 ? null : step);
    if (now.trim() && now !== was)
      nbRmStageEdit($, nb, id, step < 0 ? null : step, now);
    if (nowInfo !== wasInfo)
      nbRmStageInfo($, nb, id, step < 0 ? null : step, nowInfo);
  };
  ta.onkeydown = e => {
    if (e.key === "Enter" && !e.shiftKey){
      e.preventDefault(); box.querySelector(".primary").click();
    }
    if (e.key === "Escape"){ e.preventDefault(); e.stopPropagation(); shut(); }
  };
  // Focused, unlike a window opening: the finger that wants this field just
  // tapped the pencil, and the text it wants to change is already in it.
  ta.focus();
  ta.setSelectionRange(ta.value.length, ta.value.length);
}

// Adding steps one after another: the field stays open, so a plan is typed
// rather than assembled a dialog at a time.
function nbRmOpenStepInput($, nb, box){
  const id = box.dataset.id;
  drawHTML(box, `<textarea class="proseline" rows="1" maxlength="4000"
      placeholder="then…"></textarea><button type="button" class="primary">Add</button>
      <button type="button" class="stop">Cancel</button>`);
  const inp = box.querySelector("textarea"), btn = box.querySelector(".primary");
  // Escape closes it too, but a phone keyboard has no Escape, and a field
  // that only closes by being emptied first is a field you are stuck in.
  box.querySelector(".stop").onclick = () => nbRmCloseStepInput($, nb, box);
  const go = async () => {
    if (!inp.value.trim()) return nbRmCloseStepInput($, nb, box);
    if (nbRmStageAddStep($, nb, id, nbRmClean(inp.value))){
      // The redraw replaced this box; find the new one and carry on typing.
      const again = $("roadmapList").querySelector(`.addstep[data-id="${id}"]`);
      if (again) nbRmOpenStepInput($, nb, again);
    }
  };
  btn.onclick = go;
  inp.onkeydown = e => {
    if (e.key === "Enter"){ e.preventDefault(); go(); }
    // stopPropagation, or the document handler behind it reads the same
    // Escape as "close the panel" and the plan being typed goes with it.
    if (e.key === "Escape"){ e.preventDefault(); e.stopPropagation(); nbRmCloseStepInput($, nb, box); }
  };
  // Focused, unlike anything a window opens with: this field exists because
  // the finger that wants it just tapped "+ step", and making them tap twice
  // to type in the thing they asked for is not the same problem.
  inp.focus();
}

function nbRmCloseStepInput($, nb, box){
  drawHTML(box, `<button type="button" class="link">Add a step</button>`);
  box.querySelector("button").onclick = () => nbRmOpenStepInput($, nb, box);
}

async function nbRmAdd($, nb){
  const t = $("roadmapText");
  if (!t.value.trim()) return;
  if (nbRmStageAdd($, nb, nbRmClean(t.value))){
    t.value = "";
    // It lands at the end now, which on a phone is below the fold. Scrolled
    // to, because "did that work?" should not need a swipe to answer.
    $("roadmapList").lastElementChild?.scrollIntoView({block: "nearest"});
  }
  // Kept, not taken: the keyboard is already up because they just typed, and
  // a list is usually added to more than one line at a time.
  t.focus();
}

// Add to roadmap, the control row's primary, unrolls the box under that
// row, and Cancel (or Escape in an empty box) rolls it back; a line
// half typed keeps the box open. The button stays where it is, a press
// while the box is open taking the caret back to it.
function nbRmForm($, on){
  // Rolled back with the caret in it, the caret goes back to the press that
  // opened it (a keyboard's place was lost with the box).
  const back = !on && $("roadmapAddBar").contains(document.activeElement);
  // Unrolled and rolled back over its height, as it says (the motion rule).
  slideShow($("roadmapForm"), !!on);
  slideShow($("roadmapAddBar"), !!on);
  $("roadmapShow").setAttribute("aria-expanded", String(!!on));
  if (on) $("roadmapText").focus();
  else if (back) $("roadmapShow").focus();
}

// Put the list back the way it was found. The server never saw any of it, so
// this is only the page's own copy going back to the snapshot taken when the
// first change was staged.
function nbRmRevertPending(nb){
  if (nb.roadmapPending.length && nb.roadmapWas) nb.roadmapItems = nb.roadmapWas;
  nb.roadmapPending = []; nb.roadmapWas = null;
}

// A press on the list draws it whatever is open, since it is that press's
// own change; what moves under a person (the poll, the paging as they
// scroll, a chip pressed elsewhere on the band) passes force false and
// leaves an open Reword, Drop or Add step as it is, the list drawn
// once it closes.
const nbRmRedraw = ($, nb, force = true) =>
  nbRmDraw($, nb, {items: nb.roadmapItems, session: nb.roadmapSession, unsaved: nb.roadmapUnsaved}, force !== false);

// ---- staging -------------------------------------------------------------
// Nothing the panel does touches the list until Save. Reordering worked this
// way already; everything else used to write on the spot, which made Save mean
// two different things depending on which control you had pressed, and left
// no way to type three steps, look at them together, and change your mind.
//
// Each change is applied to the page's own copy and appended here. Save
// replays them in the order they were made, which is what makes the server
// arrive at what is on screen. Anything else (closing, Escape, the backdrop)
// asks, and puts the copy back.
//
// Sending is not staged and cannot be: it types into a live session, which no
// Save button can take back. It flushes whatever is pending first, so the line
// that goes carries the list as the operator has just arranged it.

function nbRmStage($, nb, op, apply){
  if (!nb.roadmapPending.length) nb.roadmapWas = structuredClone(nb.roadmapItems);
  const out = apply();
  if (out === false) return false;      // nothing actually changed
  nb.roadmapPending.push(op);
  nb.roadmapStaged++;
  nbRmRedraw($, nb);
  return true;
}

const nbRmFindRow = (nb, id) => nb.roadmapItems.find(r => String(r.id) === String(id));

// The same tidy roadmap.py's _clean does, so the row on screen before Save is
// the row that lands after it rather than one that quietly loses a space.
const nbRmClean = t => String(t ?? "").replace(/\r\n?/g, "\n").split("\n")
  .map(l => l.split(/\s+/).filter(Boolean).join(" "))
  .filter((l, i, a) => l || (i && a[i - 1])).slice(0, 12)
  .join("\n").replace(/\n+$/, "");

function nbRmStageAdd($, nb, text){
  const id = --nb.tmpId;                   // negative: not on the server yet
  return nbRmStage($, nb, {action: "add", text, tmp: id}, () => {
    nb.roadmapItems.splice(nb.roadmapItems.filter(r => !r.shelved).length, 0,
                     {id, text, by: "you", sent: 0, steps: [], shelved: 0});
    return true;
  });
}

function nbRmStageAddStep($, nb, id, text){
  return nbRmStage($, nb, {action: "add-step", id, text}, () => {
    const r = nbRmFindRow(nb, id);
    if (!r) return false;
    (r.steps = r.steps || []).push({text, sent: 0});
  });
}

// What a replacing op believes it is replacing, carried with it so the write
// can be refused rather than applied if that is no longer what is stored
// (roadmap #26). One FIELD's words, not a version for the row: a session
// attaching details to an item while the operator rewords its line is two
// people doing two things.
//
// The state flips beside them (shelve, cross, reorder) carry nothing:
// they lose nobody's words if they land after somebody else's change, and a
// dialog asking which of them wins would be a question with no wrong answer.
const nbRmWasOf = (nb, id, step, act) => {
  const r = nbRmFindRow(nb, id);
  if (!r) return undefined;
  const t = step !== undefined && step !== null && step >= 0
    ? (r.steps || [])[step] : r;
  if (!t) return undefined;
  return act === "info" ? (t.info || "") : (t.text || "");
};

function nbRmStageEdit($, nb, id, step, text){
  return nbRmStage($, nb, {action: "edit", id, step, text, was: nbRmWasOf(nb, id, step, "edit")}, () => {
    const r = nbRmFindRow(nb, id);
    if (!r) return false;
    if (step === null || step < 0) r.text = text;
    else if ((r.steps || [])[step]) r.steps[step].text = text;
    else return false;
  });
}

function nbRmStageInfo($, nb, id, step, text){
  return nbRmStage($, nb, {action: "info", id, ...(step !== null ? {step} : {}), text,
                was: nbRmWasOf(nb, id, step, "info")}, () => {
    const r = nbRmFindRow(nb, id);
    if (!r) return false;
    const t = step === null ? r : (r.steps || [])[step];
    if (!t) return false;
    if (text.trim()) t.info = text; else delete t.info;
  });
}

// The release an item is meant for: a state like a shelf, so it carries
// no was; "" clears it.
// A step's own rides the same action with its step.
function nbRmStageTarget($, nb, id, target, step = null){
  return nbRmStage($, nb, {action: "target", id, target, ...(step === null ? {} : {step})}, () => {
    const r = nbRmFindRow(nb, id);
    const at = step === null ? r : r?.steps?.[step];
    if (!at) return false;
    if (target) at.target = target; else delete at.target;
  });
}

function nbRmStageRemove($, nb, id, step, why){
  return nbRmStage($, nb, {action: "remove", id, ...(step >= 0 ? {step} : {}), why,
                was: nbRmWasOf(nb, id, step, "remove")}, () => {
    const i = nb.roadmapItems.findIndex(r => String(r.id) === String(id));
    if (i < 0) return false;
    if (step >= 0) nb.roadmapItems[i].steps.splice(step, 1);
    else nb.roadmapItems.splice(i, 1);
  });
}

function nbRmStageShelve($, nb, id, on){
  return nbRmStage($, nb, {action: "shelve", id, on}, () => {
    const i = nb.roadmapItems.findIndex(r => String(r.id) === String(id));
    if (i < 0) return false;
    const [r] = nb.roadmapItems.splice(i, 1);
    r.shelved = on ? Math.floor(Date.now() / 1000) : 0;
    // The same place the server would put it: the shelf is the bottom of the
    // list, and coming back off it means the end of the live ones.
    if (on) nb.roadmapItems.push(r);
    else nb.roadmapItems.splice(nb.roadmapItems.filter(x => !x.shelved).length, 0, r);
  });
}

// One swap, on the page's copy. The same swap the server would do, so that
// replaying the list of them at Save arrives at what is on screen.
function nbRmMoveLocally($, nb, id, step, dir){
  nbRmStage($, nb, {action: "move", id, step, dir}, () => {
    const i = nb.roadmapItems.findIndex(r => String(r.id) === String(id));
    if (i < 0) return false;
    const seq = step === null ? nb.roadmapItems : (nb.roadmapItems[i].steps || []);
    const at = step === null ? i : step;
    const to = at + dir;
    if (to < 0 || to >= seq.length) return false;
    [seq[at], seq[to]] = [seq[to], seq[at]];
  });
}

// Replay, in order. An item added here has a negative id the server has never
// seen, so the id it comes back with is substituted into everything that was
// staged against it: a step typed onto an item that did not exist yet is the
// ordinary case, not the exotic one.
async function nbRmFlushPending($, nb){
  const map = new Map();
  const real = v => map.has(String(v)) ? map.get(String(v)) : v;
  // What each FIELD now holds, after the write before this one. Editing the
  // same line twice before pressing Save stages two ops both claiming to
  // replace the words that were on screen, and the second would then be
  // refused as a conflict with the first; this panel arguing with itself.
  // After a write, what is stored is what was just written.
  const now = new Map();
  const fkey = b => `${b.id}:${b.step ?? -1}:${b.action === "info" ? "i" : "t"}`;
  // Taken one at a time rather than emptied up front: a refusal half way down
  // used to discard everything behind it as well, which turned one rejected
  // edit into the loss of a whole panel's work. What is left stays staged, so
  // Save can be pressed again once whatever it was is dealt with.
  while (nb.roadmapPending.length){
    const op = nb.roadmapPending[0];
    const body = {...op};
    delete body.tmp;
    if (body.id !== undefined) body.id = real(body.id);
    if (body.was !== undefined && now.has(fkey(body)))
      body.was = now.get(fkey(body));
    const j = await nbRmPost($, nb, body, true);
    if (!j) return map;                 // nbRmPost has already said why
    nb.roadmapPending.shift();
    if (op.action === "add" && j.item) map.set(String(op.tmp), j.item.id);
    if (body.was !== undefined && op.action !== "remove")
      now.set(fkey(body), body.text);
  }
  nb.roadmapWas = null;
  return map;
}

// ---- the finished ones --------------------------------------------
// Ticked-off items leave the list (a list is read to find out what is
// left) and live in the history with their plans. The toggle at the top
// fetches them and draws them below the shelved ones, struck through,
// with no arrows: there is nothing left to send. Off by default, and off
// again when the notebook reopens.
// The newest ask wins: one still out from before a reload or a reopen
// would land a list from before it.
function nbRmLoadFinished($, nb){
  return reading(`${nb.memProj}:finished`, async () => {
    const seq = nb.roadmapDoneSeq = (nb.roadmapDoneSeq || 0) + 1;
    nb.roadmapDoneAsking = true;
    let j;
    try{
      j = await postJSON("/api/roadmap", {project: nb.memProj, action: "finished"});
    }catch(e){ j = {error: String(e)}; }
    if (seq !== nb.roadmapDoneSeq) return;
    nb.roadmapDoneAsking = false;
    nb.roadmapDone = j.finished || [];
    nbRmDrawFinished($, nb);
  });
}
function nbRmDrawFinished($, nb){
  const host = $("roadmapDoneList");
  if (!host) return;
  if (!$("roadmapDoneSect").open){ host.innerHTML = ""; return; }
  const q = (nb.roadmapFind || "").trim().toLowerCase();
  const rows = nb.roadmapDone;
  if (rows === null){ drawHTML(host, `${skel("rows")}`); return; }
  if (!rows.length){ drawHTML(host, `<div class="empty">nothing finished yet</div>`); return; }
  const when = t => t ? fmtTime(t * 1000, {day: "2-digit", month: "short"}) : "";
  // Each the same fold as an open item: its row, then its
  // details and its steps with when each was done, and Reopen where a
  // release has not shipped it yet.
  const held = new Set([...host.querySelectorAll("details.grp[open]")].map(d => d.dataset.done));
  // Only the matching rows, a page at a time (pageLimit):
  // built whole and hidden, a long finished list was slow to draw.
  const vis = rows.filter(r => rmVer(r, nb.roadmapVer) && rmMatch(r, q));
  if (!vis.length && nb.roadmapVer){
    drawHTML(host, `<div class="empty">nothing finished ${nb.roadmapVer === "none" ? "without a target" : `for ${esc(nb.roadmapVer)}`}</div>`);
    return;
  }
  const lim = pageLimit(host, "roadmapDone", vis.length);
  drawHTML(host, vis.slice(0, lim).map(r => `<details class="grp done" data-done="${r.id}"${
      held.has(String(r.id)) ? " open" : ""}>
      <summary><div class="roadmap"><span class="n id">R${r.id}</span> <span class="body"><span class="txt">${esc(r.text || "")}</span>
        <span class="sub data dim">done ${r.done_at ? esc(when(r.done_at)) : ""}${(() => { const v = shippedIn(r.done_at, nb.roadmapReleases);
        return v ? ` · in ${esc(v)}` : ""; })()}</span></span></div></summary>
      ${factGrid([["Added", r.added ? `${rmDay(r.added)}, by ${byWho(r.by || "you", r)}` : ""],
                ["Target", r.target || ""],
                // The agent an item names is the one that added it; which agent's
                // session finished it is not on the row, so that one reads as Claude.
                ["Finished", r.done_at ? `${rmDay(r.done_at)}${r.done_by ? `, by ${byWho(r.done_by)}` : ""}` : ""],
                ["Shipped in", (() => { const v = shippedIn(r.done_at, nb.roadmapReleases);
                  return v === null ? "not yet: planned for the next release" : v || ""; })()],
                ["Changelog", clRefs((nb.roadmapChangelog || {})["R" + r.id]), {html: true}]], "dfacts")}
      ${r.info ? `<div class="dinfo">${esc(r.info)}</div>` : ""}${
    (r.steps || []).map((st, i) => `<div class="roadmap step"><span class="n">${st.done ? "✓" : i + 1 + "."}</span>
        <span class="body"><span class="txt">${esc(st.text || "")}</span>${st.done ? `<span class="sub data dim">done ${esc(when(st.done))}</span>` : ""}${
        st.info ? `<div class="dinfo">${esc(st.info)}</div>` : ""}</span></div>`).join("")}
      <div class="actbar">${r.reopenable
      ? `<button type="button" data-reopen="${r.id}" title="put it back on the list as it was, for more work on the same goal">Reopen</button>`
      : `<span class="state">shipped in a release: more work on it is a new item</span>`}</div>
    </details>`).join(""));
  // Reopen puts it back on the list on the press (nbRmDrawReopen), and
  // Finished is read again once the server has it.
  host.querySelectorAll("[data-reopen]").forEach(b => b.onclick = async () => {
    const id = b.dataset.reopen;
    const j = await nbRmPost($, nb, {action: "reopen", id}, false, () => nbRmDrawReopen($, nb, id));
    if (!j) return;
    notify(`R${id} is back on the list`);
    nbRmLoadFinished($, nb);
  });
  paginate(host, ":scope > .grp", {key: "roadmapDone", noun: "finished", total: vis.length, more: () => nbRmDrawFinished($, nb)});
}

// ---- a step that needs no sending -----------------------------------------
// Handed over, or finished by a session. Two marks, one question: sent is
// the dashboard's and says a line went; done is a session's and says the
// work is finished, sent or not. Moved here from index.html: only this view
// asks.

// A step that needs no sending: handed over, or finished by a session.
// Two marks, one question: sent is the dashboard's and says a line went;
// done is a session's and says the work is finished, sent or not.
const stepGone = s => !!(s.sent || s.done);

// A day as the rows' facts say it ("15 Oct"), from epoch seconds.
function rmDay(t){ return t ? fmtTime(t * 1000, {day: "2-digit", month: "short"}) : ""; }

// The release a thing done at `at` shipped in, from the
// CHANGELOG's dated headings, newest first as [version, end of its day]: the
// oldest release whose day ends after it. null for one done after the newest
// release (planned for the next), "" where the project has no releases.
function shippedIn(at, rel){
  if (!at || !rel || !rel.length) return "";
  for (let i = rel.length - 1; i >= 0; i--) if (rel[i][1] >= at) return rel[i][0];
  return null;
}

// What the changelog says about an item or a bug, as a fact's
// value: each entry with the release it went out in, or Unreleased.
function clRefs(refs, untie = false){
  if (!refs || !refs.length) return "";
  // A bug's tied line carries its bin where the bug may be written:
  // the line stays, it only stops answering this bug. One found by the
  // bug's fix commit says so, and has nothing to untie.
  return `<ul class="clrefs">${refs.map(e => `<li><span class="clin">${esc(e.in)}</span><span class="cltx">${esc(e.text)}${
    e.by === "commit" ? ` <span class="dim">(names its fix commit)</span>` : ""}</span>${
    untie && e.tied ? rmIcon(`data-untie="${esc(e.words || "")}"`, "this line no longer answers it",
                             {title: "untie: the line stays, and no longer answers this bug"}) : ""}</li>`).join("")}</ul>`;
}

// Whether an item answers a search: its number (R12 or 12), its
// words, its steps' and their details, case aside. An empty search is all.
// Whether an item is under the target chip in force ("" is All).
// An item is under a release by its own target or by a step's: a
// step with none goes with its item.
const rmVers = r => [r.target || "", ...(r.steps || []).filter(st => st.target).map(st => st.target)];
const rmVer = (r, v) => rmVers(r).some(t => inRelease(t, v));

function rmMatch(r, q){
  return idOrWords("r", r.id, () => [r.text, r.info, r.target, ...(r.steps || []).flatMap(st => [st.text, st.info])], q);
}

function nextStep(r){
  const steps = r.steps || [];
  if (!steps.length) return stepGone(r) ? null : -1;
  const i = steps.findIndex(s => !stepGone(s));
  return i < 0 ? null : i;
}
