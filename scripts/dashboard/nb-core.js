// The notebook itself: one per project, each a clone of #nbTpl with its
// state on one object (nb, written down above makeNotebook), so two open in
// a split share nothing. The views are the nb-*.js files beside this one;
// this is the frame they draw into, with its own strip, its presence line
// and its save.
//
// One classic script beside index.html (docs/design-language.md, Files):
// pure declarations, nothing runs at load. What runs at load is
// page-boot.js's, under the section's header.

"use strict";

// ---- notebooks -----------------------------------------------------------

// One notebook per project, and as many open as there are projects: each is a
// clone of #nbTpl with its state held on its own state object, so two of them
// in a split do not share so much as a variable. The local `$` shadows the
// global one on purpose: every lookup inside the notebook's code resolves
// within its own clone, which is what makes the ids in the template safe to
// repeat.
const notebooks = new Map();
// For the tests: the held state of one project's notebook, from outside.
const nbHeldFor = name => !!notebooks.get(name)?.held();

// Which view a project's notebook is on, kept per browser so a reload comes
// back to it: the strip and the active pane come back from the saved layout,
// and this is the one "where was I" that lives inside a tab rather than on
// the strip. Closing the notebook forgets it (destroy), so a tab opened
// fresh starts on the strip's first view as it always has.
const nbViewMemo = {
  read(){ try{ return JSON.parse(localStorage.getItem("bb.nbview") || "{}"); }catch(e){ return {}; } },
  keep(project, v){
    try{
      const m = this.read();
      if (v) m[project] = v; else delete m[project];
      localStorage.setItem("bb.nbview", JSON.stringify(m));
    }catch(e){ /* no storage */ }
  },
};

function getNotebook(project){
  let nb = notebooks.get(project);
  if (!nb){ nb = makeNotebook(project); notebooks.set(project, nb); }
  return nb;
}

function openNotebook(name, view){
  // A project with no repository (R208) has no notebook: what there is to
  // open is its settings, as its card's Settings opens them.
  if ((state?.projects || []).find(x => x.name === name)?.work) return renameProject(name, "project");
  openTab({kind: "notebook", arg: name, label: "Notebook: " + projLabel(name)});
  // Overview is the Briefing view under the name it is shown by, as the
  // address has it; a view the notebook has no pane for opens on its first
  // rather than on nothing (seen 29 Oct: a blank notebook).
  if (view === "overview") view = "briefing";
  const nb = getNotebook(name);
  if (view && !nb.root?.querySelector(`.nbview[data-view="${CSS.escape(view)}"]`)) view = "briefing";
  if (view) nb.view(view);
}

// ---- a project's notebook ------------------------------------------------

// The notebook's state object, nb. makeNotebook makes it and hands it to
// every function in this file and to every view factory (nb-*.js), which
// read and write it by name. Each property below says what it is and who
// sets it: a function in this file by name, a view by its file. "Reset on
// open" means nbCoreOpenMemory sets it again each time the notebook opens.
//
// The frame, and this file's own state
//   root                this notebook's clone of #nbTpl; makeNotebook
//   $                   an element by id inside root, since every clone repeats the ids; makeNotebook
//   project             the space this notebook is for; makeNotebook
//   sheet               the reading room's backdrop inside root; nbCoreReadingRoom
//   groupLast           each view group's last view, which its button returns to; makeNotebook, nbCoreSetView
//   loaded              whether the first show has loaded the notebook; nbCoreBag, nbCoreShown
//   sheetHome           each element lent to the reading room, with where it goes back to; nbCoreReadingRoom,
//                       nbCoreOpenSheet, nbCoreCloseSheet
//   sheetClosed         what to call when the reading room closes; nbCoreReadingRoom, nbCoreOpenSheet,
//                       nbCoreCloseSheet
//   memProj             the space nbCoreOpenMemory opened, null once closed; nbCoreOpenState, nbCoreOpenMemory,
//                       nbCoreLeaving
//   memGen              counts opens and closes, so a slow load cannot repaint; nbCoreOpenState,
//                       nbCoreOpenMemory, nbCoreLeaving
//   movedUnder          another writer moved a half this panel holds edits to; nbCoreOpenState,
//                       nbCoreSyncSave, nbCoreWatchHalves
//   nbWhere             the view this window is on, sent with the heartbeat; nbCorePresenceState,
//                       nbCoreOpenMemory, nbCoreSetView
//   nbRead              when a session last read the list, from the heartbeat's answer; nbCorePresenceState,
//                       nbCoreOpenMemory, nbCoreBeat
//   away                another page is on show and the heartbeat has said so; nbCoreShown, nbCorePoll
//   nbWriting           how many of this panel's own writes are still out; nbCoreWatchState, nbCoreWriting
//   unwatch             the way to stop each watch taken, for destroy; nbCoreWatchState, nbCoreWatch
//   halves              the six halves: the token, whether its move is news, what to re-read; makeNotebook
//   staleHalves         the halves that moved while another page was on show; nbCoreWatchHalves, nbCoreShown
//   dkGot               the Docker view's last /api/docker answer, its own node's; nbCoreWireDocker, nbCoreLoadDocker
//   dkMore              the answers of the other nodes its containers may be on; nbCoreLoadDocker
//   dkNode              the node the Docker view's chips narrow it to, "" for all; nbCoreDrawDocker
//   nvNode              the node the VMs view's chips narrow it to, "" for all; nbCoreDrawVms
//
// This file's functions, for the views to call
//   openSheet           opens the reading room on some elements; nbCorePublish
//   closeSheet          closes the reading room and puts its elements back; nbCorePublish
//   setNbView           shows a view; nbCorePublish
//   drawBatchNote       draws the band that says a session is changing the notebook; nbCorePublish
//   nbHeld              whether a session's batch holds the notebook's saves; nbCorePublish
//   nbUnsaved           what is unsaved here, in words, or ""; nbCorePublish
//   noteBatch           takes the batch the poll reports; nbCorePublish
//   syncSave            brings every section's Save and Revert up to date; nbCorePublish
//   stagers             what is staged, by key: each section's stager (count, what, save, revert) and each
//                       kind of unsaved work's (count, revert), which the leave and close questions
//                       read (NB_UNSAVED); nbCoreViews, nbCoreStage
//   sectBar             a section's Save and Revert bar, as markup; nbCoreViews
//   stage               registers a stager; nbCoreViews
//   watch               takes a watch on a revision token that destroy puts down; nbCoreWatchState
//   writing             runs one of this panel's writes so the poll does not take it for news; makeNotebook
//
// The views' functions, handed back by each factory and put on nb by
// nbCoreViews unless a file is named
//   loadGit             reads and draws the Git view; nbGitView
//   gitPage             the branch whose comparison is on show; nb-git.js
//   gitAt               shows a branch's comparison, from an address; nb-git.js
//   designAt            shows a design page, or the list of them, from an address; nb-design.js
//   loadPerms           reads and draws the Permissions view; nbPermsView
//   leavePerms          hands the settings dials back when Permissions is left; nbPermsView
//   drawPush            redraws the push policy and the view's glance; nbPermsView
//   loadSessions        reads and draws the Sessions view; nbSessionsView
//   loadArtifacts       reads and draws the Artifacts view; nbArtifactsView
//   loadVersion         reads and draws the version block; nbArtifactsView
//   drawVersion         redraws the version block from what is in hand; nbArtifactsView
//   postArtifacts       posts to /api/artifacts; nbArtifactsView
//   postVersion         posts to the version route; nbArtifactsView
//   loadSigning         reads and draws the Signing view; nbSigningView
//   loadAnalysis        reads and draws the Analysis view; nbAnalysisView
//   loadCodebase        reads the code base's numbers, one read for everyone asking; nbAnalysisView
//   codebaseSection     the Briefing's code base section, as markup; nbAnalysisView
//   loadPreamble        reads the block a session is handed; nbAnalysisView
//   preambleSection     the Briefing's section showing that block, as markup; nbAnalysisView
//   loadBrief           reads the brief the space was made with; nbAnalysisView
//   briefSection        the Briefing's section showing the brief, as markup; nbAnalysisView
//   loadDesign          reads and draws the Design view; nbDesignView
//   drawDesign          redraws the Design view from what is in hand; nbDesignView
//   loadWiki            reads and draws the Wiki view; nbWikiView
//   wikiNews            whether a wiki token's move is worth a re-read; nbWikiView
//   wikiAt              opens the wiki page an address names; nb-wiki.js
//   loadRules           reads and draws the rules; nbRulesView
//   drawRules           redraws the rules from what is in hand; nbRulesView
//   saveRules           saves the staged rules; nbRulesView
//   ruleDirty           whether the rules hold staged edits; nbRulesView
//   loadTests           reads and draws the Tests view; nbTestsView
//   loadBugs            reads and draws the Bugs view; nbBugsView
//   drawBugs            redraws the bugs from what is in hand; nbBugsView
//   postBug             posts a bug change as one of this panel's writes; nbBugsView
//   loadPending         reads and draws the approval queue; nbPendingView
//   drawPending         redraws the approval queue; nbPendingView
//   loadRoadmap         reads and draws the roadmap; nbRoadmapView
//   redrawRoadmap       redraws the roadmap from what is in hand; nbRoadmapView
//   postRoadmap         posts a roadmap change as one of this panel's writes; nbRoadmapView
//   flushPending        writes the staged roadmap changes in order; nbRoadmapView
//   revertPending       drops the staged roadmap changes; nbRoadmapView
//   cancelSend          puts down the armed send box; nbRoadmapView
//   drawSendBox         draws the send box under the armed step; nbRoadmapView
//   sendBoxEl           builds a send box; nbRoadmapView
//   shutSendBoxes       shuts every send box in this notebook; nbRoadmapView
//   drawFinished        draws the finished items; nb-roadmap.js
//   roadmapForm         opens or shuts the roadmap's add form; nb-roadmap.js
//   briefingHead        draws the Briefing's head from both halves; nbMemoryView
//   loadMemory          reads and draws the memories; nbMemoryView
//   memDirty            whether a memory holds unsaved edits; nbMemoryView
//   postMemory          posts a memory change as one of this panel's writes; nbMemoryView
//   saveMemory          saves the edited memories; nbMemoryView
//   drawHistory         draws a history log; nbHistoryView
//   stamp               a time in this browser's time zone; nbHistoryView
//
// The Roadmap view
//   roadmapItems        the list as last read; nb-roadmap.js
//   roadmapRev          the roadmap's revision as of this panel's last read; nbCoreOpenState, reset on open,
//                       nb-roadmap.js
//   roadmapPending      the staged changes, in the order they were made; reset on open, nb-roadmap.js
//   roadmapWas          the list before the first staged change, for Cancel; reset on open, nbCoreWireSections,
//                       nb-roadmap.js
//   roadmapStaged       moves on every staged change, so a read can tell it raced one; nb-roadmap.js
//   roadmapOrdering     the rows show move controls; reset on open, nbCoreRereadRoadmap, nbCoreLeaving,
//                       nbCoreWireSections, nb-roadmap.js, nb-history.js
//   roadmapOpen         the rows open to their workings and actions, as id:step; nb-roadmap.js
//   roadmapSel          the step whose send box is armed; reset on open, nb-roadmap.js, nb-bugs.js
//   sendNoteText        the note typed in the open send box; nb-roadmap.js, nb-bugs.js
//   sendShownFor        the step whose send box has unrolled, so a redraw does not replay it; nb-roadmap.js
//   roadmapSession      the live session beside the list; nbCorePoll, nb-roadmap.js
//   roadmapBatch        a session's open batch on this notebook; reset on open, nbCoreNoteBatch, nb-roadmap.js
//   roadmapStale        a batch closed since the list was read; reset on open, nbCoreNoteBatch,
//                       nbCoreRereadRoadmap, nb-roadmap.js
//   roadmapUnsaved      what no session has been told yet, {roadmap, memory}; nb-roadmap.js
//   roadmapChip         the chip narrowing the list; reset on open, nbCoreFind, nb-roadmap.js
//   roadmapVer          the release narrowing the list; reset on open, nbCoreFind, nb-roadmap.js
//   roadmapFind         the search narrowing the list; reset on open, nbCoreFind, nb-roadmap.js
//   roadmapFinishedN    how many items are finished, from the last read; reset on open, nb-roadmap.js
//   roadmapDone         the finished items, null until read; reset on open, nb-roadmap.js
//   roadmapDoneAsking   a read of the finished items is out; reset on open, nb-roadmap.js
//   roadmapDoneSeq      the newest read of the finished items, so an older answer is dropped; nb-roadmap.js
//   roadmapReleases     the releases, from the last read; nb-roadmap.js
//   roadmapChangelog    the changelog's lines by item, from the last read; nb-roadmap.js
//   roadmapLogOn        the panel shows the log instead of the list; reset on open, nb-history.js
//   roadmapLog          the log on show, null while it loads; reset on open, nb-history.js
//   tmpId               ids for items the server has not heard of yet; nb-roadmap.js
//   clash               a refused roadmap change waiting on which version wins; reset on open, nb-roadmap.js
//   clashResume         what settling the clash goes on to; reset on open, nbCoreWireSections, nb-roadmap.js
//
// The memories
//   memRev              the memories' revision as of the last read; nbCoreOpenState, reset on open, nb-memory.js
//   memN                how many memories the last read found, null until read; nbCoreBag, reset on open,
//                       nb-memory.js
//   memLast             the last answer drawn, for a redraw with nothing fetched; nb-memory.js
//   memTypes            the kinds a memory can be; nb-memory.js
//   memEditing          which memories have their fields out; nb-memory.js
//   memIndexRev         the digest of the index as read, for the write that rebuilds it; nb-memory.js
//   memClash            a refused memory write, with what is stored; reset on open, nb-memory.js
//
// The rules
//   ruleData            the rules as last read; nbCoreBag, nb-rules.js
//   rulePending         the staged copy of the rules; nbCoreBag, nb-rules.js
//   rulesRev            the rules' revision as of the last read; nbCoreBag, nb-rules.js
//   globalOffPending    the global rules switched off here, staged; nbCoreBag, nb-rules.js
//   globalEditing       the global rule an administrator is editing; nbCoreBag, nb-rules.js
//   ruleEditing         which rows are open for editing; nbCoreBag, nb-rules.js
//   ruleOpen            which rows are unfolded; nbCoreBag, nb-rules.js
//   ruleWas             what each row read when its Edit was pressed, for Cancel; nbCoreBag, nb-rules.js
//   ruleClash           what is stored, after a save was refused; nb-rules.js
//   rulesInFlight       the read of the rules still out, for anyone else asking; nb-rules.js
//
// The bugs
//   bugs                the tracker as last read, null until read; nb-bugs.js
//   bugRev              the tracker's revision as of the last read; nb-bugs.js
//   bugChip             the chip narrowing the list; reset on open, nbCoreFind, nb-bugs.js
//   bugVer              the release narrowing the list; reset on open, nbCoreFind, nb-bugs.js
//   bugFind             the search narrowing the list; reset on open, nbCoreFind, nbCoreWireBugs
//   bugRepr             how often a bug must reproduce to be listed; nb-bugs.js
//   bugReleases         the releases, from the last read; nb-bugs.js
//
// The tests
//   tests               the registry as last read, null until read; reset on open, nb-tests.js
//   testsRev            the registry's revision as of the last read; reset on open, nb-tests.js
//   tstSuite            the suite the list is narrowed to; reset on open, nb-tests.js
//   tstFlagged          only the flagged tests are listed; reset on open, nb-tests.js
//   tstUndoc            only the undocumented tests are listed; reset on open, nb-tests.js
//
// The approval queue
//   pendData            the queue as last read; nbCoreBag, nb-pending.js
//   pendRev             the queue's revision as of the last read; nbCoreBag, nb-pending.js
//
// The Analysis and Briefing views
//   anaStamp            the scan the Analysis view last drew; nb-analysis.js
//   preData             the block a session is handed, as last read; nb-analysis.js
//   briefData           the brief the space was made with, as last read; nb-analysis.js
//
// The Design view
//   dsData              the design as last read; nb-design.js
//   dsLang              the working copy of the language; nb-design.js
//   dsPages             the working copy of the pages; nb-design.js
//   dsDirty             whether the working copies differ from what was read; nb-design.js
//   dsSel               the block selected on each page's board; nb-design.js
//   dsShow              the theme and the page each section shows; nb-design.js
//   dsRuleUI            each rules list's open, editing and before-Edit rows; nb-design.js
//   dsRuleLists         each rules list's rows as drawn; nb-design.js
//
// The Wiki view
//   wkData              the wiki as last read; nb-wiki.js
//   wkRev               the wiki's revision as of the last read; nb-wiki.js
//   wkPages             each page as last read, by name; nb-wiki.js
//   wkCur               the page on show; nb-wiki.js
//   wkEdit              the page whose editor is open, with its text; nb-wiki.js
//   wkAdding            the page New page is adding, with its text; nb-wiki.js
//   wkLog               the page's history is on show; nb-wiki.js
//
// The history logs
//   histTimer           the history search's wait before it reads; nb-history.js
function makeNotebook(project){
  const root = nbCoreClone(project);
  const $ = id => root.querySelector('[id="' + CSS.escape(id) + '"]');
  // The notebook's state, one object rather than sixty closure variables,
  // so a view can live in its own file and reach it by name (R60).
  const nb = {};
  Object.assign(nb, {root, $, project});
  nb.groupLast = {};                 // a view group's last view, so its button returns there (R259)
  nbCorePublish(nb);
  nbCoreBag(nb);
  nbCoreReadingRoom(nb);
  nbCoreViews(nb);
  nbCoreWireSheet(nb);
  nbCoreOpenState(nb);
  nbCorePresenceState(nb);
  nbCoreWireSections(nb);
  nbCoreWireStrip(nb);
  nbCoreWireBugs(nb);
  nbCoreWatchState(nb);
  nbCoreWatchViews(nb);
  nb.halves = nbCoreHalves(nb);
  nbCoreWatchHalves(nb);
  nbCoreWireDocker(nb);
  nb.writing = fn => nbCoreWriting(nb, fn);
  return nbCoreHandle(nb);
}

// A clone of #nbTpl for the project, parked and drawn.
function nbCoreClone(project){
  const root = document.getElementById("nbTpl").content.firstElementChild.cloneNode(true);
  // Whose notebook this clone is, on the element. Every id inside it is the
  // template's, so two open notebooks carry two of each; anything keyed on an
  // id alone is therefore keyed on BOTH of them, which is what paginate was.
  root.dataset.project = project;
  document.getElementById("nbPark").appendChild(root);
  drawn(root);
  return root;
}

// This file's own functions a view reaches through the state object,
// late-bound: a view file calls nb.syncSave(), and which function that is
// does not depend on the order the files loaded in.
function nbCorePublish(nb){
  Object.assign(nb, {openSheet: (title, els, onClose) => nbCoreOpenSheet(nb, title, els, onClose),
                     closeSheet: () => nbCoreCloseSheet(nb), setNbView: v => nbCoreSetView(nb, v),
                     drawBatchNote: () => nbCoreDrawBatchNote(nb), nbHeld: () => nbCoreHeld(nb),
                     nbUnsaved: () => nbCoreUnsaved(nb), noteBatch: b => nbCoreNoteBatch(nb, b),
                     syncSave: () => nbCoreSyncSave(nb)});
}

// What the views find on the state object when they are made.
function nbCoreBag(nb){
  nb.loaded = false;
  nb.ruleData = null; nb.rulePending = null; nb.rulesRev = null;
  // Global rules switched off for this project, staged (nb-rules.js), and
  // the one an administrator is editing.
  nb.globalOffPending = null; nb.globalEditing = null;
  // Which rules are open for editing, by row. A rule is READ by default:
  // its name, its text, its triggers, and shows its fields only after Edit,
  // the way a bug report does; every row opening as a form read as a tab
  // full of half-finished edits. A row just added starts open, since it is
  // nothing but a form until it has words.
  nb.ruleEditing = new Set();
  // ...and which are unfolded. A rule is a fold like a bug report: its name
  // on the line, the words behind a click: a tab that showed every rule in
  // full was a wall. Kept across redraws so a reword does not shut the fold.
  nb.ruleOpen = new Set();
  // What each row read when its Edit was pressed, so Cancel has somewhere
  // to go back to. A row with no entry here is one Add made: canceling
  // that is removing it.
  nb.ruleWas = new Map();
  // How many memories the tab found (null until read), for the glance that
  // sums both halves of the briefing: set by drawMemory, read by both draws.
  nb.memN = null;
  // The approval queue (roadmap #27): what the band and the tab counts draw
  // from, and the revision the poll compares to know when to re-read it.
  nb.pendData = null; nb.pendRev = null;
}

// ---- the reading room --------------------------------------------------
// What goes in is the real element, MOVED: every handler bound to a filter
// bar keeps working and there is no second copy to drift out of step with
// the first. They go home on close, to the exact place they left: parent
// AND next sibling, because "append it back" is how an element ends up
// under the wrong heading.
function nbCoreReadingRoom(nb){
  const {root} = nb;
  const sheet = root.querySelector(".nbsheet");
  armModal(sheet);                        // a clone: the page-load pass did not see it
  nb.sheet = sheet;
  nb.sheetHome = []; nb.sheetClosed = null;
}

function nbCoreOpenSheet(nb, title, els, onClose){
  const {$, sheet} = nb;
  nbCoreCloseSheet(nb);                    // one at a time, like the env editor
  $("sheetTitle").textContent = title;
  const slot = $("sheetSlot");
  nb.sheetHome = els.map(el => [el, el.parentElement, el.nextSibling, el.hidden]);
  els.forEach(el => { el.hidden = false; slot.appendChild(el); });
  nb.sheetClosed = onClose || null;
  sheet.hidden = false;   // the fade is the stylesheet's, for every modal
}

function nbCoreCloseSheet(nb){
  const {sheet} = nb;
  if (sheet.hidden) return;
  sheet.hidden = true;
  for (const [el, parent, next, wasHidden] of nb.sheetHome){
    el.hidden = wasHidden;
    // No parent means it was built for the sheet and has nowhere to go back
    // to. next is null for "it was last".
    if (!parent){ el.remove(); continue; }
    // The reference node is only good while its parent still holds it, and
    // one of these parents does not: the changelog pane lives in #verBox,
    // whose children drawVersion() replaces wholesale, which happens on a
    // commit, a version poll or a dist change while the sheet is still open
    // over the top. insertBefore then throws on a node that is no longer a
    // child, mid-loop, so nb.sheetHome was never cleared and nb.sheetClosed never
    // ran: the button stayed lit and the pane sat orphaned in the slot,
    // reappearing inside the next sheet opened.
    try{
      parent.insertBefore(el, next && next.parentNode === parent ? next : null);
    }catch(e){
      // Parent gone from the document entirely; put it back where it can
      // do no harm rather than leaving it in the sheet.
      el.remove();
    }
  }
  nb.sheetHome = [];
  const done = nb.sheetClosed; nb.sheetClosed = null;
  done?.();
}

// The reading room's close button and its backdrop.
function nbCoreWireSheet(nb){
  const {$, sheet} = nb;
  $("sheetClose").onclick = () => nbCoreCloseSheet(nb);
  // The backdrop, and not the box on it: a click landing inside is aimed at
  // something in there.
  sheet.onclick = e => { if (e.target === sheet) nbCoreCloseSheet(nb); };
  // Escape is modalKeys' (page-motion.js), which reaches the backdrop's
  // nbCoreCloseSheet above. A filter field holding a search clears the field
  // on Escape and stops the event, so the sheet stays open for that one.
}

// ---- the views, one file each (nb-*.js) --------------------------------
// Made here, before anything after them runs: a view is a factory that only
// defines functions, and the names it hands back go on the state object,
// where this file's functions and the other views call them.
function nbCoreViews(nb){
  const {$, project, root, sheet} = nb;
  // Each section's Save and Revert (see sectBar): published before the views
  // are made, since they register their sections as they are.
  nb.stagers = {}; nb.sectBar = key => nbCoreSectBar(nb, key); nb.stage = (key, st) => nbCoreStage(nb, key, st);
  Object.assign(nb, nbGitView({$, nb, project}));
  Object.assign(nb, nbPermsView({$, nb, project, root}));
  Object.assign(nb, nbSessionsView({$, nb, project, root}));
  Object.assign(nb, nbArtifactsView({$, nb, project, root, sheet}));
  Object.assign(nb, nbSigningView({$, nb, project}));
  Object.assign(nb, nbAnalysisView({$, nb, project}));
  Object.assign(nb, nbDesignView({$, nb, project, root}));
  Object.assign(nb, nbWikiView({$, nb, project}));
  Object.assign(nb, nbRulesView({$, nb, project}));
  Object.assign(nb, nbTestsView({$, nb, project}));
  Object.assign(nb, nbBugsView({$, nb, project}));
  Object.assign(nb, nbPendingView({$, nb, project, root}));
  Object.assign(nb, nbRoadmapView({$, nb}));
  Object.assign(nb, nbMemoryView({$, nb}));
  Object.assign(nb, nbHistoryView({$, nb, project}));
}

// ---- opening, and a session's batch --------------------------------------
// What an open resets and the watches compare against, set once the views
// are made.
function nbCoreOpenState(nb){
  nb.memProj = null;  // set by openMemory; always this project
  nb.memGen  = 0;  // bumped on close, so a slow load cannot repaint it
  // What each half of the notebook was on at the last read, so the poll can see
  // somebody else writing (roadmap #26). Until this, the Bugs tab was the only
  // one of the four that noticed: the Roadmap and Memory views loaded once when
  // the tab opened and then held that drawing until it was closed and reopened,
  // which is a long time to be looking at a list a session has moved on from.
  nb.roadmapRev = null; nb.memRev = null;
  nb.movedUnder = false;        // another writer moved a half this panel is holding edits to (B199)
}

async function nbCoreOpenMemory(nb, name){
  const {$} = nb;
  nb.memProj = name;
  const gen = ++nb.memGen;
  $("memTitle").textContent = "Notebook: " + projLabel(name);
  nb.memN = null; nb.briefingHead();
  drawHTML($("memDrift"), $("memList").innerHTML = $("memAdd").innerHTML = "");
  nb.roadmapSel = null;                 // the send box lives on the row, and the
  nb.roadmapOrdering = false;           // rows are about to be replaced wholesale
  nb.roadmapPending = []; nb.roadmapWas = null;
  nb.roadmapBatch = null; nb.roadmapStale = false;
  nb.roadmapRev = nb.memRev = null;
  nb.clash = nb.memClash = null; nb.clashResume = null;
  nb.nbRead = 0; nb.nbWhere = "briefing"; nbCoreDrawHere(nb);
  nb.tests = null; nb.testsRev = null;
  nb.tstSuite = ""; nb.tstFlagged = nb.tstUndoc = false;
  nb.roadmapLogOn = false;
  nb.roadmapLog = null;
  nb.roadmapDone = null; nb.roadmapChip = ""; nb.roadmapVer = ""; nb.roadmapFind = ""; nb.roadmapFinishedN = 0;
  nb.roadmapDoneAsking = false;
  nb.bugChip = ""; nb.bugVer = ""; nb.bugFind = "";
  $("roadmapFind").value = ""; $("bugFind").value = "";
  $("histFind").value = "";
  nb.cancelSend();
  $("roadmapText").value = "";
  $("roadmapForm").hidden = true; $("roadmapAddBar").hidden = true; $("roadmapShow").setAttribute("aria-expanded", "false");
  drawHTML($("roadmapList"), `${skel("rows")}`);
  // Opening it is a re-read: both halves come off disk again, and the card
  // gets the same treatment so the number on the row you just pressed is not
  // the one from the last poll.
  await Promise.all([nb.loadRoadmap(gen), nb.loadMemory(gen), refresh()]);
}

// A batch opening is news; a batch closing is news of a different kind: the
// list on screen is now a copy of something that has changed, so it is marked
// stale and stays that way until it is re-read.
function nbCoreNoteBatch(nb, b){
  if (nb.roadmapBatch && !b){
    nb.roadmapStale = true;
    // Nothing staged and nothing half-typed: the fresh list can simply be
    // taken, and the banner never has to ask for a click it does not need.
    if (!nb.roadmapPending.length && !nb.memDirty()){
      nb.roadmapStale = false;
      nb.roadmapBatch = null;
      nbCoreReloadViews(nb);
      return;
    }
  }
  nb.roadmapBatch = b || null;
}

// Is the notebook held against operator writes? While a session's batch is
// open, and again until the roadmap is re-read after one closes. It holds
// everything: the Saves, and the write-through controls on the memory and
// bug views, because "a session is mid-change here" is a fact about the
// notebook, not about one of its tabs.
// A batch open past BATCH_STALE holds nothing (B198): its session is gone,
// and a hold nobody can lift is a notebook nobody can save.
function nbCoreHeld(nb){ return (!!nb.roadmapBatch && !nb.roadmapBatch.stale) || nb.roadmapStale; }

function nbCoreDrawBatchNote(nb){
  const {$, project, root} = nb;
  const el = $("roadmapBatch");
  if (!el) return;
  root.classList.toggle("held", nbCoreHeld(nb));
  setHidden(el, !nb.roadmapBatch && !nb.roadmapStale);
  if (el.hidden){ if (el.firstChild) el.innerHTML = ""; return; }
  const n = nb.roadmapBatch?.changes || 0;
  const mins = nb.roadmapBatch?.at ? Math.max(1, Math.round((Date.now() / 1000 - nb.roadmapBatch.at) / 60)) : 0;
  patch(el, nb.roadmapBatch?.stale
    ? `<div>A session started changing this notebook ${mins} min ago and never closed it.
       Nothing is held: your saves go through.${
       state?.can?.admin ? ` <button type="button" id="roadmapBatchClose">Close it</button>` : ""}</div>`
    : nb.roadmapBatch
    ? `<div>${esc(nb.roadmapBatch.by || "a session")} is changing this
       notebook${n ? `: ${n} change${n === 1 ? "" : "s"} so far` : ""}. Saving
       waits until it finishes; your edits stay where they are.
       <button type="button" id="roadmapRecheck">Check now</button></div>`
    : `<div>A session finished changing this notebook. What is on screen was
       read before that, so saving over it would undo the change.
       <button type="button" id="roadmapReread">Reload the list</button></div>`, true);
  const bc = $("roadmapBatchClose");
  if (bc) bc.onclick = async () => {
    busy(bc, "Closing");
    try{
      const j = await postJSON("/api/roadmap", {project, action: "batch-close"});
      if (j.error) notify(j.error, true);
    }catch(e){ notify("could not reach the server: " + failWords(e), true); }
    await refresh();
  };
  const rr = $("roadmapReread");
  if (rr) rr.onclick = () => nbCoreRereadRoadmap(nb);
  const rc = $("roadmapRecheck");
  // The link is the answer to "is it done yet?" without waiting for the next
  // poll. If it is, and nothing local is at stake, the reload happens by
  // itself: the guard should only demand a click when a click would cost.
  if (rc) rc.onclick = async () => {
    busy(rc, "Checking");
    // The batch state, which is the question the button asks, not a reload
    // of one view, which is what it used to do and why the roadmap refreshed
    // while the other three tabs did not. If the batch has closed and nothing
    // local is staged, noteBatch re-reads the whole notebook by itself.
    await refresh();
    if (nbCoreHeld(nb)) notify("still at it: the guard stays until it commits");
  };
}

// Re-read, which is the only way out of stale. It costs whatever is staged,
// so it says so first.
// Every view, not just the roadmap. The banner says a session changed *this
// notebook*, and it holds all four tabs, so the re-read that lifts it has to
// cover what it held. Reloading only the list is how the Bugs tab could sit
// there showing what a session had already changed.
async function nbCoreReloadViews(nb){
  const {root} = nb;
  await nb.loadRoadmap(nb.memGen);
  if (nb.bugs) await nb.loadBugs();
  await nb.loadMemory(nb.memGen);
  if (!root.querySelector('[data-view="analysis"]').hidden) await nb.loadAnalysis();
}

async function nbCoreRereadRoadmap(nb){
  if (nb.roadmapPending.length
      && !await askYes(`Reload? ${nb.roadmapPending.length} unsaved change`
                  + `${nb.roadmapPending.length === 1 ? "" : "s"} of yours would go: `
                  + "the notebook is being replaced with what is on disk."))
    return;
  nb.revertPending();
  nb.roadmapOrdering = false;
  nb.roadmapStale = false;
  await nbCoreReloadViews(nb);
}

// ---- a section's own Save and Revert (the operator, 5 Oct) ------------------
// Every section that stages anything carries its own Save and Revert at its
// foot, and they write or throw away that section's changes and nothing
// else. There was one pair at the bottom of the tab, and on a phone a
// change made near the top was a long scroll from the button that saved it,
// past sections that had nothing to do with it. A stager is what a section
// registers: how many changes it holds, what they are in words, how to
// write them (a message, or null when a clash stopped it part-way) and how
// to throw them away.
//
// The same registry holds each kind of unsaved work the leave and close
// questions name (NB_UNSAVED), under the kind's own key: where that is not
// one section's stager already, a view registers how many changes the kind
// holds and how to throw them all away, with no bar and so no words or save.
function nbCoreStage(nb, key, st){ nb.stagers[key] = st; }
// The bar, drawn by whichever view draws the section; dead rather than
// absent while there is nothing to save, so it does not move under a thumb.
function nbCoreSectBar(nb, key){
  // Drawn as syncSave would leave it, its words and its dead buttons with
  // it (B2): a view whose draw did not call syncSave after (the rules')
  // left the bar untitled until whatever synced next, and that wrote two
  // titles into a status read that brought nothing.
  const b = nbCoreBarSays(nb, key);
  // In a field band, as every line of a section's body is (a-dialog/layout):
  // bare, it sat beside the last row it followed rather than under it.
  return `<div class="field"${key === "roadmap" && b.hide ? " hidden" : ""}>${saveBar({
    save: `data-ssave="${esc(key)}" title="${esc(b.saveTitle)}"${b.saveDead ? " disabled" : ""}`,
    revert: `data-srevert="${esc(key)}" title="${esc(b.rvTitle)}"${b.rvDead ? " disabled" : ""}`,
    state: esc(b.state), cls: "sectbar", attrs: `data-bar="${esc(key)}"`})}</div>`;
}
// What a section's bar says and which of its buttons are dead, the one
// answer sectBar draws and syncSave keeps.
function nbCoreBarSays(nb, key){
  const st = nb.stagers[key], n = st?.count() || 0, held = nbCoreHeld(nb);
  return {
    hide: !(n > 0 || nbCoreSectDirty(nb, key) || nb.roadmapOrdering),
    saveDead: !nbCoreSectDirty(nb, key) || (key === "roadmap" && held),
    rvDead: !n,
    rvTitle: n ? `throw away ${st.what()}: it goes back to what is on disk` : "nothing unsaved here to throw away",
    saveTitle: key === "roadmap" && held
      ? (nb.roadmapBatch ? "a session is part-way through changing this list"
                         : "a session changed this list: reload it before saving over it")
      : "save this section; a session running here hears about it on its next prompt",
    // A panel holding unsaved work stops re-reading, since a redraw would
    // eat the typing (B199); said where the Save is, once something here
    // has moved under it. A Save lit with nothing staged is the change no
    // session has been told about yet, which says so rather than sitting
    // there unexplained.
    state: n && nb.movedUnder ? "this has changed since you loaded it: Save will ask which version wins"
      : n ? `${n} unsaved` : nbCoreSectDirty(nb, key) ? "changed, not told to the session yet" : ""};
}
// A section holding unsaved work, or a change no session has been told
// about yet, which the roadmap's and the memories' Saves settle.
function nbCoreSectDirty(nb, key){
  const st = nb.stagers[key];
  if (!st) return false;
  return st.count() > 0 || (key === "roadmap" && !!nb.roadmapUnsaved.roadmap)
    || (key === "briefing:memories" && !!nb.roadmapUnsaved.memory);
}
function nbCoreSyncSave(nb){
  const {root} = nb;
  // Held while a session is mid-batch, and again until the list is re-read
  // after one finishes; that is the list's own business, so it holds only
  // the roadmap's Save. Reverting is allowed either way: throwing away your
  // own unsaved work never depends on what anybody else is doing.
  // Nothing has moved under anybody once no bar's Save has anything to
  // write: a stager with no save has no bar to say it on.
  if (![...Object.keys(nb.stagers)].some(k => nb.stagers[k].save && nb.stagers[k].count() > 0)) nb.movedUnder = false;
  root.querySelectorAll(".sectbar[data-bar]").forEach(bar => {
    const key = bar.dataset.bar, st = nb.stagers[key];
    const save = bar.querySelector("[data-ssave]"), rv = bar.querySelector("[data-srevert]");
    if (!st || !save || !rv || save.getAttribute("aria-busy")) return;
    const b = nbCoreBarSays(nb, key);
    // The Roadmap's bar is its status line (R109), and its Save and Revert
    // are the ones that sat dead most of the time (R224): they appear with
    // a reorder or an edit staged, and go with the Save. The rest stay,
    // dead, so they do not move under a thumb.
    if (key === "roadmap"){ setHidden(save, b.hide); setHidden(rv, b.hide); }
    setDisabled(save, b.saveDead);
    setDisabled(rv, b.rvDead);
    setTitle(rv, b.rvTitle);
    setTitle(save, b.saveTitle);
    // ...its words what is staged, before the session's (.stg).
    setText(bar.querySelector(".state .stg") || bar.querySelector(".state"), b.state);
  });
}

// One section's Save: its own changes written, then the marker settled, so
// a session running here hears about it on its next prompt (roadmap #27).
async function nbCoreSaveSection(nb, key, b){
  const st = nb.stagers[key];
  if (!st) return;
  const was = b.textContent;
  busy(b, "Saving");
  const msg = await st.save();
  // A refused roadmap change stops the replay with the op still queued and
  // the band asking which version wins; settling it calls this again.
  if (msg === null){ unbusy(b, was); nbCoreSyncSave(nb); return; }
  const j = await nb.postRoadmap({action: "save"});
  b.removeAttribute("aria-busy");
  b.textContent = was;
  nbCoreSyncSave(nb);
  if (j) notify([msg, "saved: the session reads it on its next prompt"].filter(Boolean).join(" · "));
}
async function nbCoreRevertSection(nb, key){
  const st = nb.stagers[key];
  if (!st || !st.count()) return;
  if (!await askYes(`Revert ${st.what()}?\n\nIt goes back to what is on disk.`)) return;
  await st.revert();
  nbCoreSyncSave(nb);
}
// The bars' presses, and the stagers of the two halves this file holds.
function nbCoreWireSections(nb){
  const {root} = nb;
  root.addEventListener("click", e => {
    const sv = e.target.closest("[data-ssave]"), rv = e.target.closest("[data-srevert]");
    if (sv && !sv.disabled){ e.preventDefault(); nbCoreSaveSection(nb, sv.dataset.ssave, sv); }
    if (rv && !rv.disabled){ e.preventDefault(); nbCoreRevertSection(nb, rv.dataset.srevert); }
  });
  // The two halves this file holds: the roadmap's list and the memories.
  nbCoreStage(nb, "roadmap", {
    count: () => nb.roadmapPending.length,
    what: () => `${nb.roadmapPending.length} change${nb.roadmapPending.length === 1 ? "" : "s"} to the list`,
    save: async () => {
      nb.clashResume = () => nbCoreSaveSection(nb, "roadmap", root.querySelector('[data-ssave="roadmap"]'));
      await nb.flushPending();
      if (nb.roadmapPending.length) return null;
      nb.clashResume = null;
      nb.roadmapWas = null;     // committed: nothing left for a Cancel to go back to
      return "";
    },
    revert: () => { nb.revertPending(); nb.roadmapOrdering = false; nb.redrawRoadmap(); }});
  // The Memories section is markup rather than a draw: wired here, once.
  wireSections(root.querySelector('.nbview[data-view="briefing"]'));
  nbCoreStage(nb, "briefing:memories", {
    count: () => nb.memDirty() ? 1 : 0,
    what: () => "the edited memories",
    save: async () => { if (nb.memDirty()) await nb.saveMemory(true); await nb.loadMemory(nb.memGen); return ""; },
    revert: async () => { nb.memEditing.clear(); await nb.loadMemory(nb.memGen); }});
  // The space's settings, while their form is in this notebook's Settings
  // view: another view picked, the form went back to the dialog and was
  // filled again from what is saved, without a word (the audit of 13 Nov).
  // The dialog's own door asks the same. Leaving the view is what throws
  // them away (nbCoreSetView), so there is nothing for a revert to do.
  nbCoreStage(nb, "settings", {count: () => nbCoreSettingsEdited(nb) ? 1 : 0, revert: () => {}});
}

// ---- who else is in here ---------------------------------------------------
// Roadmap #26's other half. A refusal makes a collision safe; this is what
// stops most of them happening: the line says who else has this notebook
// open before the typing starts, rather than after it.
//
// Ridden on the poll rather than on a timer of its own: the panel is already
// asking the server something every fifteen seconds, and a second clock would
// be a second thing to get wrong. The request is not awaited: presence is
// the least important thing on this page, and nothing else waits for it.
function nbCorePresenceState(nb){
  nb.nbWhere = "briefing"; nb.nbRead = 0;
}

// This notebook is the page on show, not one left behind another page.
function nbCoreOnShow(nb){ const t = tabOf(panes[0]); return t?.kind === "notebook" && t.arg === nb.project; }

async function nbCoreBeat(nb, leave, keepalive){
  if (!nb.memProj) return;
  // Not for a project this account no longer has (deleted, or taken off
  // it): the server answers that with a 400 on every poll (B65), and
  // there is no one there to say anything to.
  if (state && !(state.projects || []).some(p => p.name === nb.memProj)) return;
  try{
    // A leave sent as the page goes away (pagehide) has to outlive the
    // page: keepalive is what lets it arrive after the page has gone.
    const j = await postJSON("/api/presence", {project: nb.memProj, client: nbClient,
                                               where: nb.nbWhere, ...(leave ? {leave: 1} : {})},
                             {keepalive: !!keepalive, background: true});
    if (leave || !j.ok) return;
    nb.nbRead = j.read || 0;
    nbCoreDrawHere(nb);
  }catch(e){ /* the least important thing on the page */ }
}

// Who else has the notebook open is no longer said (the operator, 17 Oct:
// not necessary): two windows writing one item are caught at the save,
// which refuses the second and shows both. The heartbeat stays for what a
// session has read, said on the Roadmap's status line.
function nbCoreDrawHere(nb){
  const {$} = nb;
  // A session that has gone and read the list, which is a different claim
  // from having been told: being told rides in on its next prompt (#27), and
  // what the operator wants to know after changing something is whether it
  // has actually looked. The Roadmap's fact, on its status line (R222): it
  // stood over every view.
  const rd = $("roadmapRead");
  if (rd) rd.textContent = nb.nbRead ? ` · read by a session ${ago(nb.nbRead)}` : "";
}

// What is unsaved here, in the words the buttons use. Both halves, because
// both Saves write both and a Revert that left one behind would be a trap.
// Every kind of unsaved work, by the key its stager is registered under,
// with its words from how many changes it holds, in the order a sentence
// names them. A view that stages something registers it (nb.stage) and has
// its line here; nothing else asks a view what it holds.
const NB_UNSAVED = [
  ["roadmap", n => `${n} change${n === 1 ? "" : "s"} to the list`],
  ["briefing:memories", () => "an edited memory"],
  ["briefing:rules", () => "an edited rule"],
  ["design", () => "an unsaved design"],
  ["wiki", () => "a wiki page being edited"],
  ["settings", () => "settings being edited"],
  ["signing", () => "a staged signing key change"],
  ["artifacts", n => `${n} staged version bump${n === 1 ? "" : "s"}`],
  ["permissions:githost", () => "a staged git host permission"],
];
function nbCoreSettingsEdited(nb){
  const {root} = nb;
  if (!rnHost || !root.contains(rnHost)) return false;
  try { return rnDirty().length > 0; } catch { return false; }
}
function nbCoreUnsaved(nb){
  return NB_UNSAVED.map(([key, says]) => { const n = nb.stagers[key]?.count() || 0; return n ? says(n) : ""; })
    .filter(Boolean).join(" and ");
}

// A notebook tab going away takes whatever is unsaved in it with it, so it is
// the one tab close that asks. Answered here rather than in hideTab, which is
// shared by every kind and should not learn about any of them.
async function nbCoreLeaving(nb){
  const what = nbCoreUnsaved(nb);
  // The seat would time out on its own in under a minute; saying so is what
  // stops the other window claiming somebody is here who has just left.
  if (!what){ nbCoreBeat(nb, true); return true; }
  if (!await askYes(`Close without saving?\n\n${what} would be dropped.`, {verb: "Close without saving", danger: true})) return false;
  nb.revertPending();
  nb.roadmapOrdering = false;
  nbCoreBeat(nb, true);
  nb.memGen++; nb.memProj = null;
  return true;
}

// ---- the notebook's views --------------------------------------------------
// The strip's five groups, in the order a space is worked, by key and by
// the word on the button.
const NB_GROUPS = [["overview", "Overview"], ["plan", "Plan"], ["code", "Code"], ["ship", "Ship"], ["docs", "Docs"]];
// Every view, in the strip's order, a group's views together as the row
// under it draws them. The one list of them: the strip in #nbTpl is static
// markup held to it by test/surface.mjs, and the first paint's strip
// (bootPage), what showing a view loads (nbCoreSetView) and what it watches
// while it is on screen (nbCoreWatchViews) are read from it.
//
//   key     the view's name in the markup (data-v, data-view), in the
//           address and in what a browser remembers; never changed
//   label   the word on its button
//   group   the group whose row it is in
//   addr    its name in an address, where that is not its key
//   show    what it does as it comes on, before it is marked as waiting:
//           Permissions draws itself from what the page holds, and a mark
//           put on first would flash under it
//   read    what it asks for once marked, so it waits as its markup
//           declares (R109)
//   watch   what it reads again while it is on screen, by the revision
//           token that moves; a token ending in a colon is the space's own.
//           Only ever acted on while the view is the one showing: a token
//           moving for a view nobody is looking at is not worth a fetch.
const NB_VIEWS = [
  // The rules once; the code base every time the view is shown, since a
  // commit moves it and the server answers from its cache when not.
  {key: "briefing", label: "Overview", group: "overview", addr: "overview", read: nb => {
    if (!nb.ruleData) nb.loadRules(); else nb.loadCodebase().then(() => nb.drawRules());
    // Once, on the first show. It is re-read when one of the three stores
    // behind it moves, and only while this view is the one on screen.
    if (!nb.preData) nb.loadPreamble();
    // Every show: the brief leaves the tree when the first session starts,
    // which can be while this notebook sits open.
    nb.loadBrief();
  }},
  {key: "sessions", label: "Sessions", group: "overview", show: nb => nb.loadSessions()},
  {key: "permissions", label: "Permissions", group: "overview", show: nb => nb.loadPerms()},
  {key: "settings", label: "Settings", group: "overview"},
  {key: "roadmap", label: "Roadmap", group: "plan"},
  {key: "bugs", label: "Bugs", group: "plan", read: nb => { if (!nb.bugs) nb.loadBugs(); }},
  {key: "git", label: "Git", group: "code", read: nb => nb.loadGit(), watch: {"git:": nb => nb.loadGit()}},
  {key: "tests", label: "Tests", group: "code", read: nb => { if (!nb.tests) nb.loadTests(); }},
  {key: "analysis", label: "Analysis", group: "code", read: nb => nb.loadAnalysis(),
   watch: {reports: nb => nb.loadAnalysis(), findings: nb => nb.loadAnalysis()}},
  {key: "artifacts", label: "Artifacts", group: "ship", read: nb => { nb.loadArtifacts(); nb.loadVersion(); }, watch: {
    "dist:": nb => { nb.loadArtifacts(); nb.loadVersion(); },
    // A session bumping while this tab is open, and the policy changing from
    // anywhere else. Both are file mtimes on the server: neither costs a git
    // call to notice.
    "ver:": nb => nb.loadVersion(),
    vpolicy: nb => nb.loadVersion(),
    devapp: nb => nb.loadArtifacts(),
    // A commit changes what the dev row says about the build being current,
    // and what the version block computes since the target last moved.
    "git:": nb => { nb.loadArtifacts(); nb.loadVersion(); },
    "phone.dev": nb => nb.loadArtifacts()}},
  // The Docker view re-reads on the manager's token, as the Docker tab
  // does: a job queued, taken or finished, an instance written. Not on the
  // status poll (B727): a read of an agent node's docker is a round trip
  // through its agent, whose heartbeat moves the nodes token, whose watch
  // runs the status poll, which re-read docker again, 134 requests in 30 s.
  {key: "docker", label: "Docker", group: "ship", read: nb => nbCoreLoadDocker(nb), watch: {devapp: nb => nbCoreLoadDocker(nb)}},
  {key: "vms", label: "VMs", group: "ship", read: nb => nbCoreLoadVms(nb), watch: {vms: nb => nbCoreLoadVms(nb)}},
  // A release's APK looked for and signed (R106), by the press or the
  // hourly look: the Releases section follows it to its end.
  {key: "signing", label: "Signing", group: "ship", read: nb => nb.loadSigning(), watch: {releasesign: nb => nb.loadSigning()}},
  {key: "wiki", label: "Wiki", group: "docs", read: nb => nb.loadWiki(),
   watch: {"wiki:": (nb, k) => { if (nb.wikiNews(k)) nb.loadWiki(); }}},
  {key: "design", label: "Design", group: "docs", read: nb => nb.loadDesign()},
];

function nbCoreSetView(nb, v){
  const {project, root} = nb;
  // Which view somebody is on is half of what the presence line says, so it
  // is reported on the switch rather than waiting for the next poll: the
  // other window would otherwise name the tab this one just left.
  if (nb.nbWhere !== v){ nb.nbWhere = v; nbCoreBeat(nb); }
  nbViewMemo.keep(project, v);
  shellSync();                    // the address names the view (R218 step 3)
  // Its group lit in the top row and the group's views in the row under it
  // with this one lit (R259), so the row is always there and every view's
  // head at one height; Settings sits beside Overview in its group. The
  // view is the group's to come back to.
  const me = root.querySelector(`.nbtabs button[data-v="${CSS.escape(v)}"]`);
  const g = me?.dataset.in || me?.dataset.g || "";
  if (g) nb.groupLast[g] = v;
  root.querySelectorAll(".nbtabs .nbgroups button").forEach(b => {
    const on = b.dataset.g === g;
    if (b.classList.contains("on") !== on) b.classList.toggle("on", on);
    b.setAttribute("aria-selected", String(on));
  });
  const sub = root.querySelector(".nbtabs .nbsub");
  sub?.querySelectorAll("button").forEach(b => {
    const mine = b.dataset.in === g, on = b.dataset.v === v;
    if (b.hidden === mine) b.hidden = !mine;
    if (b.classList.contains("on") !== on) b.classList.toggle("on", on);
    b.setAttribute("aria-selected", String(on));
  });
  // Each strip's line slides to the one pressed (slideMark): the groups'
  // per notebook, the views' per group, so a group's row never slides
  // from another group's.
  slideMark(root.querySelector(".nbtabs .nbgroups"), "nbg:" + project);
  slideMark(sub, "nbv:" + project + ":" + g);
  // A view switched fades through as a rail page does (the operator,
  // 18 Oct): the one going out as a still copy fading on docOut's time,
  // the incoming on docIn's (fadeThrough's halves), rather than a tab
  // switch being the one place on the page where something simply appears.
  let away = null;
  // A view opened anew opens on its first section on a phone.
  if (root.querySelector(`.nbview[data-view="${v}"]`)?.hidden) sectNewVisit();
  root.querySelectorAll(".nbview:not(.fghost)").forEach(x => {
    const show = x.dataset.view === v, wasHidden = x.hidden;
    if (!show && !wasHidden && !noMotion()) away = ghostOf(x);
    x.hidden = !show;
    if (show && wasHidden){ x.classList.remove("justpainted"); fadeIn(x); }
  });
  ghostOut(away);
  // The settings form comes into this view while it is on screen, and goes
  // back to the dialog when another view is picked (page-projsettings.js).
  // ...and its Agents may section into Permissions, which hands it back
  // first whenever another view is shown.
  if (v !== "permissions") nb.leavePerms();
  if (v === "settings") settingsInto(project, root.querySelector('.nbview[data-view="settings"] .nbsettings'));
  else if (rnHost && root.contains(rnHost)) settingsOut();
  // What the view itself does on show is its row's (NB_VIEWS); a name that
  // is no view's does nothing here.
  const view = NB_VIEWS.find(x => x.key === v);
  view?.show?.(nb);
  // A view still waiting on its data waits as its markup declares (R109).
  glanceWaiting(root.querySelector(`.nbview[data-view="${v}"] .nbglance`));
  view?.read?.(nb);
}
// Unsaved work does not follow you to another tab.
//
// It used to: the roadmap's staged changes and a half-edited memory both
// sat in variables that no tab switch touched, so you could leave an edit
// on Memory, do something on Bugs, and meet it again later with no memory
// of having made it, and Save, from over there, would write it. So leaving
// asks, and answering yes throws it away. Same question the tab close asks,
// for the same reason, in the one other place work can be walked away from.
//
// Only the operator's own click is guarded, never setNbView itself: the
// panel opens itself on a view sometimes (a findings row asks for Analysis),
// and nothing is unsaved a moment after opening.
async function nbCoreLeaveView(nb, v){
  const {root} = nb;
  const cur = root.querySelector(".nbview:not([hidden])")?.dataset.view;
  if (v === cur) return true;
  const what = nbCoreUnsaved(nb);
  if (!what) return true;
  if (!await askYes(`Leave this tab? ${what} would be thrown away.\n\n`
               + "Unsaved work does not carry across the tabs: Save it "
               + "first if you want to keep it.")) return false;
  // Every kind's revert in one turn, the last named first: the list's
  // redraw reads what else is unsaved (nbRmCanSend), so it follows the
  // rest, and the memories' read, which drops whatever the editors were
  // holding, is the one thing waited on.
  await Promise.all(NB_UNSAVED.map(([key]) => nb.stagers[key]).reverse().map(st => st?.revert()));
  return true;
}
// A view's own button opens it; a group's opens the view it was last on,
// else its first (R259).
// The line under the strip moves first and the view is drawn a frame
// after (the operator, 26 Oct: the slide lagged): drawn in the same task,
// a notebook's long view held the slide's first frame until it was done.
function nbCoreWireStrip(nb){
  const {root} = nb;
  root.querySelectorAll(".nbtabs button").forEach(b =>
    b.onclick = async () => {
      const v = b.dataset.v || nb.groupLast[b.dataset.g]
        || root.querySelector(`.nbtabs .nbsub button[data-in="${CSS.escape(b.dataset.g || "")}"]`)?.dataset.v;
      if (!v || !await nbCoreLeaveView(nb, v)) return;
      nbCoreLineTo(nb, v);
      await new Promise(r => requestAnimationFrame(() => setTimeout(r)));
      navPush(() => nbCoreSetView(nb, v));
    });
}
// The strips' lines to the view `v`, ahead of its draw: its group lit in
// the top row, and in the row under it the view, when it is the group on
// show already. setNbView lights them again the same, which moves nothing.
function nbCoreLineTo(nb, v){
  const {project, root} = nb;
  const me = root.querySelector(`.nbtabs button[data-v="${CSS.escape(v)}"]`);
  const g = me?.dataset.in || me?.dataset.g || "";
  if (!g) return;
  root.querySelectorAll(".nbtabs .nbgroups button").forEach(x => {
    if (x.classList.contains("on") !== (x.dataset.g === g)) x.classList.toggle("on", x.dataset.g === g); });
  slideMark(root.querySelector(".nbtabs .nbgroups"), "nbg:" + project);
  const sub = root.querySelector(".nbtabs .nbsub");
  if (!sub || [...sub.querySelectorAll("button:not([hidden])")].some(x => x.dataset.in !== g)) return;
  sub.querySelectorAll("button").forEach(x => { if (x.classList.contains("on") !== (x.dataset.v === v)) x.classList.toggle("on", x.dataset.v === v); });
  slideMark(sub, "nbv:" + project + ":" + g);
}
// The Bugs view's sort and search.
function nbCoreWireBugs(nb){
  const {$} = nb;
  $("bugSort").onchange = nb.drawBugs;
  onTyping($("bugFind"), () => { nb.bugFind = $("bugFind").value; nb.drawBugs(true); });
}

// ---- what this notebook watches ------------------------------------------
// Whether the view `v` is the one on screen in this notebook.
function nbCoreShowing(nb, v){ return !nb.root.querySelector(`[data-view="${v}"]`).hidden; }
// A write of this panel's own, still out on the wire.
//
// The token moves when the SERVER takes the write; the number this panel
// compares against moves when the ANSWER gets back. A poll landing between
// the two reads this panel's own write as somebody else's and re-reads the
// list, which detaches whatever inline box is open under the finger that
// opened it. The window is a few tens of milliseconds against a poll every
// second and a half, so it is about one edit in thirty: rare enough to look
// like a glitch and common enough to meet.
//
// Counted, because several can be out at once, and answered rather than
// dropped: when the last one lands the same questions are asked again, so
// a change somebody else made during the write is late by a moment instead
// of lost until the next one.
async function nbCoreWriting(nb, fn){
  nb.nbWriting++;
  try { return await fn(); }
  finally { if (!--nb.nbWriting) for (const [key, news, read] of nb.halves){
              const k = key(); if (news(k)) read(); } }
}
// One watch, kept so destroy() can put it down.
function nbCoreWatch(nb, k, fn){ return nb.unwatch.push(onRev(k, fn)); }
// The count of writes out, and every watch this notebook takes, so
// destroy() can put them all down again. A closed notebook that goes on
// watching goes on fetching: its root is detached, not gone, and
// nbCoreShowing reads .hidden off it happily.
function nbCoreWatchState(nb){
  nb.nbWriting = 0;
  nb.unwatch = [];
  nb.watch = (k, fn) => nbCoreWatch(nb, k, fn);
}
// What this notebook's views watch, each row's own (NB_VIEWS). Registered
// once per instance, and only ever acted on while the view in question is
// actually on screen.
function nbCoreWatchViews(nb){
  const {project} = nb;
  for (const view of NB_VIEWS)
    for (const [token, read] of Object.entries(view.watch || {}))
      nbCoreWatch(nb, token.endsWith(":") ? () => token + project : token,
                  k => { if (nbCoreShowing(nb, view.key)) read(nb, k); });
}

// ---- the notebook's own six halves ---------------------------------------
// All six on this poll, which is the whole of what a view is allowed to
// wait on. Five of them used to ride a per-project counter on /api/status
// instead, so the Bugs tab noticed a session's write in a second and a half
// and the Roadmap beside it took fifteen: one tab, two clocks, and nothing
// choosing between them.
//
// Each compares against the number the PANEL last read rather than
// reloading on any move, because the token moves for this panel's own write
// too, and a redraw it did not need detaches whatever inline box is open:
// a send box, a drop confirmation, a half-typed description, under the
// finger that opened it. That is also why these are counters on the server
// and not file mtimes: an mtime cannot tell the echo from the news.
//
// The guards are each half's own, and they are not decoration: the roadmap
// and the memory editor may be holding work the server has never seen, so
// they re-read only with nothing to lose. Bugs, tests and the queue write
// through and have nothing to lose by definition.
//
// Written once as a list: the token, whether a move of it is news for this
// panel, and what to re-read, because two things ask these questions: the
// poll, and the moment a write of this panel's own settles. They have to
// ask the same ones.
function nbCoreHalves(nb){
  const {project} = nb;
  return [
    [() => `roadmap:${project}`,
     k => nb.roadmapRev !== null && revs[k] > nb.roadmapRev
          && !nb.roadmapPending.length && !nb.clash && !nbCoreHeld(nb),
     () => nb.loadRoadmap(nb.memGen)],
    [() => `mem:${project}`,
     k => nb.memRev !== null && revs[k] && revs[k] !== nb.memRev
          && !nb.memDirty() && !nb.memClash && !nbCoreHeld(nb),
     () => nb.loadMemory(nb.memGen)],
    [() => `bug:${project}`,
     k => nb.bugs && nb.bugRev !== null && revs[k] !== nb.bugRev,
     () => nb.loadBugs()],
    [() => `tests:${project}`,
     k => nb.tests && nb.testsRev !== null && revs[k] !== nb.testsRev,
     () => nb.loadTests()],
    [() => `rules:${project}`,
     k => nb.ruleData && nb.rulesRev !== null && revs[k] !== nb.rulesRev && !nb.ruleDirty(),
     () => nb.loadRules()],
    [() => `pending:${project}`,
     k => nb.pendRev !== null && revs[k] !== nb.pendRev,
     () => nb.loadPending()],
  ];
}
// ...while this notebook is the page on show: one left behind another
// page marks the half and reads it when it is shown again, if it is still
// news then (R228 step 11).
function nbCoreWatchHalves(nb){
  const {project} = nb;
  nb.staleHalves = new Set();
  for (const [key, news, read] of nb.halves)
    nbCoreWatch(nb, key, k => {
      if (nb.nbWriting || !news(k)) return;
      if (nbCoreOnShow(nb)) read(); else nb.staleHalves.add(key);
    });
  // ...and the other half of each guard: the token moved and the panel did NOT
  // re-read, because it is holding work. That is the moment to say so (B199).
  const MOVED = [
    [() => `roadmap:${project}`, k => nb.roadmapRev !== null && revs[k] > nb.roadmapRev && nb.roadmapPending.length > 0],
    [() => `mem:${project}`, k => nb.memRev !== null && revs[k] && revs[k] !== nb.memRev && nb.memDirty()],
    [() => `rules:${project}`, k => nb.ruleData && nb.rulesRev !== null && revs[k] !== nb.rulesRev && nb.ruleDirty()],
  ];
  for (const [key, moved] of MOVED)
    nbCoreWatch(nb, key, k => { if (!nb.nbWriting && moved(k)){ nb.movedUnder = true; nbCoreSyncSave(nb); } });
  // The block a session is handed is the first, third and fifth of those
  // joined, so it is stale the moment any of them moves. Only re-read while
  // somebody is looking at it: it is a fold that is shut by default, and
  // fetching a few kilobytes for a closed fold on every roadmap edit is the
  // kind of cost nobody chooses.
  for (const half of ["rules", "roadmap", "bug"])
    nbCoreWatch(nb, () => `${half}:${project}`,
          () => { if (nbCoreShowing(nb, "briefing")) nb.loadPreamble(); });
}

// ---- what a view reads and writes ----------------------------------------
// The read of a view whose half carries a revision (the bugs, the tests, the
// rules, the approval queue): ask `url` for this space, hand the answer to
// `put`, note the revision it carried, `draw`.
//
// `put(j, threw)` keeps the answer in the view's own shape and gives back
// what it kept, or nothing to leave what was read before and end the read
// there; a read that threw comes to it as {error: its words} with `threw`
// set. `rev` is the pair that reads and writes the view's revision. The one
// noted is the ANSWER's, never the page's token as of now: a write landing
// between the read and that line moved the token, and recording that marked
// the write as seen, so the row it made never showed (B201). An answer that
// failed carries none, and the token stands in so the watch keeps asking
// rather than waiting on a number that never comes.
//
// Already behind: a write landed while this answer was on its way, and the
// poll fired for it BEFORE this landed, so it will not fire again. Read once
// more now rather than wait for the next write. Once (`again`): an answer
// and a token that disagree for good must not become a loop; and not while
// `hold` says the view is holding work.
//
// `key` names the read and, unless `token` does, the revision token; `start`
// is what else the read sets going as it begins.
function nbRevRead(nb, o, again = false){
  const {project} = nb;
  const {key, token = key, url, rev: [was, note], put, draw, start, hold} = o;
  return reading(`${project}:${key}`, async () => {
    start?.();
    let got;
    try{ got = put(await getJSON(`${url}?project=${encodeURIComponent(project)}`), false); }
    catch(e){ got = put({error: String(e)}, true); }
    if (got === undefined) return;
    const k = `${token}:${project}`;
    note(got.rev ?? revs[k] ?? was());
    draw();
    if (!again && got.rev !== undefined && revs[k] !== undefined
        && revs[k] !== got.rev && !hold?.()) nbRevRead(nb, o, true);
  });
}
// A view's write-through post to `url`, made once and called with each
// body: it answers the route's answer, or null when nothing was written,
// having said why. Wrapped so the poll can tell this panel's own write from
// somebody else's while it is still out (nbCoreWriting).
//
// A session's batch holds it, as it holds the Saves: "held" has to mean the
// notebook, or the banner is a lie about its other tabs. Reading is never
// held, so `holdExcept` names the one action that goes through all the same
// (a view's history), and `hold: false` is a post that asks nothing of it
// (the roadmap's, whose staged changes are held at their Save).
//
// `proj` gives the space, where it is not the notebook's own; `conflict(j,
// body)` takes a write the server refused because somebody else wrote
// first, and what it answers is the post's; `ok(j, opts)` takes a write
// that landed, with whatever the caller passed after the body.
//
// `opts.now`, where the page knows the result before the answer (a row
// ticked, moved or deleted), draws it on the press as drawNow does (the
// operator, 22 Nov): after the hold has had its say, so a held notebook
// draws nothing, and inside the write, so no poll reads the list back over
// it before the answer. What it gives back puts the page as it was when
// nothing was written: a refusal, a clash, or no answer at all.
function nbPoster(nb, url, {proj = () => nb.project, hold = true, holdExcept, conflict, ok} = {}){
  return async (body, opts) => nb.writing(async () => {
    if (hold && nb.nbHeld() && (holdExcept === undefined || body.action !== holdExcept)){
      notify("a session is part-way through changing this notebook: "
             + "check the banner at the top", true);
      return null;
    }
    let undo = null;
    try{ undo = opts?.now?.(); }catch(e){ console.error(e); }
    const back = () => { try{ if (typeof undo === "function") undo(); }catch(e){ console.error(e); } };
    try{
      const j = await postJSON(url, {project: proj(), ...body});
      if (conflict && j.conflict){ back(); return conflict(j, body); }
      if (j.error){ back(); notify(j.error, true); return null; }
      ok?.(j, opts);
      return j;
    }catch(e){ back(); notify("could not reach the server: " + failWords(e), true); return null; }
  });
}

// What a send to a session came to, said when it did not go: the line was
// typed into the session's input with Enter held back because it was busy,
// and the person is told what to do about that. Answers whether it went,
// so each view goes on to its own next thing. `noun` is what was sent
// ("step", "bug") where a /model line can go ahead of it: which line
// stalled matters then, since the one left in the box has the thing still
// to come and Enter would glue the two together. A send with no noun has
// no such line.
function sendOutcome(j, noun){
  if (j.sent) return true;
  notify(noun && j.switching
    ? `Not sent: the session is busy with the /${j.switching} line. `
      + `Clear its tab and send the ${noun} again.`
    : "Not sent: the session is busy. Press Enter in its tab when it is free.", true);
  return false;
}

// ---- this space's VMs and containers -------------------------------------
// This project's VMs as the VMs page draws them, scoped to it (R96): the
// page's own rows and their presses, the project's card alone.
function nbCoreLoadVms(nb){
  const {$, project} = nb;
  return reading(`${project}:vms`, async () => {
    try{
      vmsData = await getJSON("/api/vms");
    }catch(e){ glanceBad($("nvHint"), "VMs", e); return; }
    nbCoreDrawVms(nb);
  });
}
// A band of chips narrowing a notebook's list to one node (the operator,
// 19 Nov): drawn only where what the space has is on more than one, All and
// a chip a node with its count, the pick kept for the page's life as the
// Roadmap's is. `counts` is [[node id, name, how many]...]; answers the pick
// that stands.
function nbCoreNodeChips(nb, box, counts, picked, attr, items, pick){
  const groups = counts.length > 1 ? counts.map(([key, label, count]) => ({key, label, count}))
    .sort((a, b) => a.label.localeCompare(b.label, undefined, {sensitivity: "base"})) : [];
  const on = groups.some(g => g.key === picked) ? picked : "";
  const chips = chipButtons(groups, on, attr);
  chipBand(box, chips, attr, () => box.closest(".nbview"), items, pick);
  setHidden(box.parentElement, !chips);
  return on;
}
function nbCoreDrawVms(nb){
  const {$, project} = nb;
  const all = (vmsData?.vms || []).filter(v => v.project === project);
  const nodes = [...new Set(all.map(v => v.node || ""))];
  nb.nvNode = nbCoreNodeChips(nb, $("nvChips"), nodes.map(id => [id, all.find(v => (v.node || "") === id)?.node_name || id || "no node",
                                                               all.filter(v => (v.node || "") === id).length]),
                              nb.nvNode || "", "data-nvnode", ".dmcard .row, .tbl > .row, .tbl .rows > .row",
                              id => { nb.nvNode = id; nbCoreDrawVms(nb); });
  const rows = nb.nvNode ? all.filter(v => (v.node || "") === nb.nvNode) : all;
  const up = rows.filter(v => v.state === "running").length;
  // The glance (R109): what runs of how many, as the VMs page counts,
  // and on the row with VMs page and New VM what a session here may do
  // about VMs, so those two are never on a line of their own (the sweep,
  // 7 Nov, on a phone).
  const dial = (state?.projects || []).find(x => x.name === project)?.prefs?.makevms || "deny";
  viewGlance($("nvHint"), rows.length ? [{label: "running", value: up, sub: `of ${rows.length} VM${rows.length === 1 ? "" : "s"}`}] : [],
             dial === "auto" ? "a session here makes VMs on its own" : dial === "ask" ? "a session here asks before it makes a VM"
               : "a session here may not make VMs");
  const may = (vmsData.can || {})[project] === "write";
  const add = $("nvNew");
  add.hidden = !may;
  add.disabled = !(vmsData.hosts || []).length;
  add.onclick = () => openNewVm(project);
  $("nvOpen").onclick = () => openVmsTab();
  // What the view is for, as its empty state (R119 step 4).
  drawHTML($("nvList"), rows.length ? vmGroupsHtml(rows)
    : `<div class="field"><div class="hint nbempty">${!(vmsData.hosts || []).length
        ? `No node has VM host yet: a node's Features section on the ${pageLink("nodes", "Nodes page")} installs it.`
        : dial === "deny" ? "A session here may not make VMs (Make VMs is deny in this space's settings); a person makes one with New VM."
        : "A session makes one with aerie vm new NAME --os debian, or a person with New VM."}</div></div>`);
  wireVms($("nvList"));
}

// This project's containers as the Containers page draws them, scoped to
// it (the operator, 19 Oct): its tiles, when the images were checked, and
// its card in the page's cards or list, whichever this browser keeps.
function nbCoreWireDocker(nb){
  const {$} = nb;
  nb.dkGot = null; nb.dkMore = []; nb.dkNode = "";
  $("dkOpen").onclick = () => openDocker();
  // Cards and List wait on the control row where they land: a press before
  // the read keeps the choice for when it is drawn. A space with nothing
  // to show takes them away then.
  const seg = () => { patch($("dkSeg"), dmViewSeg()); dmViewWire($("dkSeg"), () => nb.dkGot ? nbCoreDrawDocker(nb) : seg()); };
  seg();
}
function nbCoreLoadDocker(nb){
  const {$, project} = nb;
  return reading(`${project}:docker`, async () => {
    const p = (state?.projects || []).find(x => x.name === project);
    const own = p?.prefs?.node || "";
    const node = own || dockerNode || "";
    // A space with a node reads it as the space's, and is told every node
    // its containers may be on (a hosting node, one it also works on): each
    // of the others is read the same way, on its own, since a row's presses
    // go to the node its read names.
    const url = n => "/api/docker" + (own ? `?project=${encodeURIComponent(project)}&node=${encodeURIComponent(n)}`
      : n ? "?node=" + encodeURIComponent(n) : "");
    try{
      nb.dkGot = await getJSON(url(node));
    }catch(e){ glanceBad($("dkHint"), "docker", e); return; }
    dockerSeen[nb.dkGot.node || node || ""] = nb.dkGot;
    const rest = (nb.dkGot.nodes || []).map(n => n.id).filter(id => id !== (nb.dkGot.node || node));
    // Its own node's rows are drawn as they land, the others' kept as last
    // read until theirs do: a hosting node slow to answer holds nothing.
    nb.dkMore = (nb.dkMore || []).filter(g => rest.includes(g.node));
    nbCoreDrawDocker(nb);
    if (!rest.length) return;
    const was = nb.dkMore;
    nb.dkMore = (await Promise.all(rest.map(id => getJSON(url(id)).catch(() => was.find(g => g.node === id) || null))))
      .filter(Boolean);
    nbCoreDrawDocker(nb);
  });
}
function nbCoreDrawDocker(nb){
  const {$, project} = nb;
  const called = id => (nodesList || []).find(n => n.id === id)?.name || (nb.dkGot.nodes || []).find(n => n.id === id)?.name || "its node";
  // What belongs to the project on each node read, which is the Containers
  // page's group for it there.
  const parts = [nb.dkGot, ...(nb.dkMore || [])].map(got => ({
    got, node: got.node || "",
    mine: (got.instances || []).filter(d => d.owner === project),
    others: (got.containers || []).filter(c => c.owner === project),
    job: got.job && (got.job.running || got.job.error) ? got.job : null,
    blind: !!(got.blind || got.error || got.on === false)}));
  const held = parts.filter(x => x.mine.length + x.others.length);
  // The band that narrows it to one node, where it is on more than one.
  nb.dkNode = nbCoreNodeChips(nb, $("dkChips"), held.map(x => [x.node, called(x.node), x.mine.length + x.others.length]),
                              nb.dkNode || "", "data-dknode", ".dmcard, .tbl > .row, .tbl .rows > .row",
                              id => { nb.dkNode = id; nbCoreDrawDocker(nb); });
  const shown = nb.dkNode ? held.filter(x => x.node === nb.dkNode) : held.length ? held : parts.slice(0, 1);
  const one = shown.length === 1 ? shown[0] : null;
  const got = (one || parts[0]).got, node = (one || parts[0]).node;
  const mine = shown.flatMap(x => x.mine), others = shown.flatMap(x => x.others);
  const dark = shown.filter(x => x.blind && x.mine.length + x.others.length);
  const blind = !!one && one.blind;
  const where = one ? called(node) : `${shown.length} nodes`;
  const n = mine.length + others.length;
  // The glance (R109): the Containers page's tiles for the project's own,
  // then its node and when the images were checked, or why the rows
  // cannot say what runs.
  const imgs = !mine.length || !mayDocker() || featureOff("image-updates") ? ""
    : got.images_at ? ` · images checked ${esc(ago(got.images_at))}` : " · images not checked yet";
  viewGlance($("dkHint"), blind || !n ? "" : dmTiles({running: mine.filter(d => d.running).length, all: mine.length,
    behind: mine.filter(d => (d.images_behind || []).length || d.nginx_to).length, checked: !!got.images_at}),
    blind && n ? `on ${esc(where)}: the daemon did not answer, so the rows cannot say what is running`
      // ...named while they are one or two; more are counted, each one's card saying so.
      : !one && dark.length ? `on ${esc(where)}: ${dark.length > 2 ? dark.length : esc(dark.map(x => called(x.node)).join(" and "))} did not answer, so ${dark.length === 1 ? "its" : "their"} rows cannot say what is running`
      : n ? `on ${esc(where)}${one ? imgs : ""}` : "no node runs this space's containers yet", "", (blind || (!one && dark.length)) && n ? "warn" : "");
  // Patched as the Containers page's rows are (R244): a row's settings
  // dialog open, a field typed in it and a fold stay as they are, and a
  // draw that brings nothing new writes nothing, which a key of its own
  // used to decide.
  patch($("dkSeg"), n ? dmViewSeg() : "");
  dmViewWire($("dkSeg"), () => nbCoreDrawDocker(nb));
  const ck = $("dkCheck");
  // Check asks each node on show that answers and has one of its instances.
  const checks = shown.filter(x => !x.blind && x.mine.length).map(x => x.node);
  ck.hidden = !checks.length || !mayDocker();
  ck.onclick = async () => {
    for (const id of checks.slice(0, -1)) await dmCheck(ck, id, () => {});
    dmCheck(ck, checks.at(-1), () => { unbusy(ck); nbCoreLoadDocker(nb); });
  };
  // What the view is for, as its empty state (R119 step 4).
  dmNoteOpen($("dkList"));
  patch($("dkList"), shown.map(x => dmGroupsHtml(x.mine, x.others, x.job, x.blind, project,
                                                 {id: x.node, name: one ? "" : called(x.node) + (x.blind ? ", which did not answer" : "")})).join("")
    || `<div class="field"><div class="hint nbempty">Send ${esc(projLabel(project))} from ${pageLink("", "Artifacts", `#/spaces/${encodeURIComponent(project)}/artifacts`)}, or pick it on a container's row on the ${pageLink("docker", "Containers page")}.</div></div>`);
  // Each node's card is wired with its own read: a press on a row goes to
  // the node that row is on.
  const cards = [...$("dkList").querySelectorAll(":scope > .dmcard[data-node]")];
  if (cards.length > 1) for (const c of cards) dmWireRows(c, shown.find(x => x.node === c.dataset.node)?.got || got);
  else dmWireRows($("dkList"), got);
}

// ---- the handle the rest of the page holds ------------------------------
function nbCoreHandle(nb){
  const {root, project} = nb;
  return {
    root, project,
    // The state object, for a suite calling this file's functions with it.
    nb,
    // First show loads; later shows are just the pane coming back.
    shown(){ nbCoreShown(nb); },
    reloadPending: nb.loadPending,
    reload(){ return nb.loadRoadmap(nb.memGen); },
    reloadMemory(){ return nb.loadMemory(nb.memGen); },
    reloadBugs(){ return nb.loadBugs(); },
    // A roadmap item or a bug by its id (R12, B34), from a link elsewhere
    // (the changelog, R254 step 4): its view, its list narrowed to it.
    find(id){ nbCoreFind(nb, id); },
    reloadTests(){ return nb.loadTests(); },
    leaving: () => nbCoreLeaving(nb),
    held: () => nbCoreHeld(nb),
    unsaved: () => nbCoreUnsaved(nb),
    view: v => nbCoreSetView(nb, v),
    where: () => nb.nbWhere,
    // The wiki page on show, for the address, and set from one (R256 step 3).
    wikiPage: () => nb.wkCur,
    wikiAt: name => nb.wikiAt(name),
    // The branch whose comparison is on show, and set from an address (R269 step 2).
    gitPage: () => nb.gitPage?.() || "",
    gitAt: name => nb.gitAt?.(name),
    // The design page on show, and set from an address.
    designPage: () => nb.nbWhere === "design" ? (nb.dsShow?.page || "") : "",
    designAt: key => nb.designAt?.(key),
    poll(p){ nbCorePoll(nb, p); },
    escape(){ if (nb.roadmapSel){ nb.cancelSend(); nb.redrawRoadmap(); return true; } return false; },
    // Says this tab has left the notebook without taking the notebook down:
    // the page is going (see the pagehide listener by getNotebook).
    leave(){ return nbCoreBeat(nb, true, true); },
    destroy(){ nbCoreDestroy(nb); },
  };
}

function nbCoreShown(nb){
  const {project} = nb;
  if (!nb.loaded){ nb.loaded = true; nbCoreOpenMemory(nb, project); nb.loadPending(); }
  if (nb.away){ nb.away = false; nbCoreBeat(nb); }
  // What moved while another page was on show, read now that it is not
  // (staleHalves). Called on every draw of the page on show, so it asks
  // for nothing else: the poll names this notebook from its next tick,
  // and a token that comes back is news to the watches that compare it.
  if (nb.staleHalves.size){
    for (const [key, news, read] of nb.halves)
      if (nb.staleHalves.has(key) && news(key())) read();
    nb.staleHalves.clear();
  }
}

function nbCoreFind(nb, id){
  const {$} = nb;
  const bug = /^b/i.test(id);
  nbCoreSetView(nb, bug ? "bugs" : "roadmap");
  if (bug){ nb.bugChip = ""; nb.bugVer = ""; nb.bugFind = id; $("bugFind").value = id; nb.drawBugs(true); }
  else { nb.roadmapChip = ""; nb.roadmapVer = ""; nb.roadmapFind = id; $("roadmapFind").value = id; nb.redrawRoadmap(); }
}

function nbCorePoll(nb, p){
  const {project, root} = nb;
  nbCoreNoteBatch(nb, p.todo_batch); nbCoreDrawBatchNote(nb); nbCoreSyncSave(nb);
  // ...and who else is in here (roadmap #26), while this is the page on
  // show: a project page left for another stays in the page model, and
  // it went on saying this person was in its notebook (B765). Off show,
  // it says once that it has left; shown again, it says it is back.
  if (nbCoreOnShow(nb)){ nb.away = false; nbCoreBeat(nb); }
  else if (!nb.away){ nb.away = true; nbCoreBeat(nb, true); }
  // A session started (or ended) under an open notebook.
  //
  // Whether a step can be sent is a fact about the session running beside
  // it, and that fact arrived only with the list, which is fetched when
  // the notebook opens and then not again. So starting Claude while
  // looking at the Roadmap left every arrow gray, correctly describing
  // the world as it had been when the tab opened, until the tab was
  // closed and reopened. It is read off the poll now, like everything
  // else on this row.
  //
  // Redrawn from what is already in hand rather than re-fetched: the list
  // on screen may be carrying staged changes that are not on the server,
  // and a refetch here would quietly throw them away.
  const now = myLiveSession(project);
  if (now !== nb.roadmapSession){ nb.roadmapSession = now; nb.redrawRoadmap(false); }
  // The Docker view follows a job on the devapp token above, never here.
  // What this notebook re-reads and when is declared once, up where the
  // watches are taken; nothing here decides it. All six halves are on
  // the revisions poll; this poll carries only what /api/status alone
  // knows, which for a notebook is the batch note and who else is in here.
  // A scan re-ran while the Analysis view is up: re-read. The cache was
  // dropped by refresh() when the mtime moved, so this is one fetch.
  // What a person changed of the push policy elsewhere, on Permissions.
  if (!root.querySelector('[data-view="permissions"]').hidden) nb.drawPush();
  if (!root.querySelector('[data-view="analysis"]').hidden
      && nb.anaStamp !== (state?.reports_mtime ?? null))
    nb.loadAnalysis();
}

function nbCoreDestroy(nb){
  const {project, root} = nb;
  // The settings form is one element lent to whichever Settings view
  // shows it: handed back before this notebook's elements go, or it
  // goes with them and every later Settings view is empty.
  nb.leavePerms();
  if (typeof rnHost !== "undefined" && rnHost && root.contains(rnHost)) settingsOut();
  nbCoreBeat(nb, true);
  nb.unwatch.forEach(off => off());
  nbViewMemo.keep(project, null);
  notebooks.delete(project);
  root.remove();
}
