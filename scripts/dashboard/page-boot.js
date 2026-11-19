// What runs as the page loads (R9 step 5): the listeners the page keeps on
// the document and the window, the dialogs' wiring, the watches on the
// revisions poll and the first reads, each part a function of its own and
// called in order by boot(), which index.html runs once every script of the
// page is in. Every other script of the page is pure declarations.
//
// One classic script beside index.html (docs/design-language.md, Files):
// pure declarations, nothing runs at load; boot() is what does.

"use strict";

function boot(){
  // Said for the head's watch over a page whose scripts never came (B930).
  document.documentElement.dataset.booted = "1";
  bootMarkup();
  bootWaits();
  bootTabs();
  bootShell();
  bootMenuHeld();
  bootTermWindow();
  bootMotion();
  bootPickers();
  bootMoreMenus();
  bootPanes();
  bootDockDrag();
  bootWelcome();
  bootKeys();
  bootFindings();
  bootLogs();
  bootDoctor();
  bootNotebooks();
  bootFirstSession();
  bootNewProject();
  bootContainerDialogs();
  bootProjectSettings();
  bootCreating();
  bootNotices();
  bootWatches();
  bootAway();
  bootDocs();
  bootLast();
}

// ---- what a draw brings ----------------------------------------------------
function bootMarkup(){
  // Wired by the draw that writes one (drawn, page-paint.js), with the fields
  // a password manager leaves alone (B495), every title turned into words and
  // every data-style applied: the markup the page loads with, here, and what a
  // draw writes later, by that draw.
  drawn(document.documentElement);
}

// ---- what the page waits with ----------------------------------------------
function bootWaits(){
  // Its declarations are page-docs.js (skel); what runs at load is this: the
  // placeholders in the markup take their shapes (R218 step 15). A view's head
  // keeps its element and takes a bar; a .loading line becomes the shape. The
  // first pane, until the first snapshot lands, is shaped like the page the
  // address names: Home's tiles, the Projects page's cards, rows otherwise.
  // The notebook's markup is a template, so its views' heads are found there.
  // The first pane is the page the address names in its frame (bootPage): the
  // rail, its bar and its shape, a reload included (the operator, 17 Oct).
  // The templates' first, so the first pane can be drawn from a notebook
  // view's own template with its shapes in it (B865).
  [...[...document.querySelectorAll("template")].map(t => t.content), document].flatMap(r => [...r.querySelectorAll("[data-skel]")]).forEach(el => {
    const shape = el.dataset.skel;
    if (shape === "page"){
      const pg = bootPage(location.hash), rl = bootRail(pg.rail);
      const id = `skboot${Math.random().toString(36).slice(2)}`;
      // Reloaded by a restart a moment ago: the page as it was, until the
      // first read draws it again (restartKeep).
      const kept = restartKept();
      if (kept){
        el.outerHTML = `<div class="snapback" id="${id}" inert aria-busy="true">${kept.html}</div>`;
        restartScrollTo($(id));
      } else {
        el.outerHTML = `<div class="loading skel skboot" id="${id}"><span class="sk-said">${esc(el.textContent.trim() || "loading")}</span>${pg.bar}${pg.body}</div>`;
        drawn($(id));
        if (pg.tool) bootOwn($(id), pg.tool);
      }
      if (!$("rail").innerHTML.trim()) drawHTML($("rail"), rl.rail);
      if (!$("railbar").innerHTML.trim()) drawHTML($("railbar"), rl.bar);
      return;
    }
    if (el.classList.contains("loading")){ const up = el.parentElement; el.outerHTML = skel(shape); drawn(up); }
    else drawHTML(el, skel(shape));
  });
}

// ---- tabs ------------------------------------------------------------
function bootTabs(){
  // Its declarations are page-tabs.js.
  // A press on a ? opens its words in a tooltip, and a second press shuts it;
  // anything else, Escape or a scroll shuts it. Bound once on the document, so icons
  // drawn later count too.
  addEventListener("click", e => {
    const h = e.target.closest && e.target.closest(".help");
    if (!h){ if (helpAt && !e.target.closest?.("#helpPop")) helpHide(); return; }
    e.preventDefault();
    helpToggle(h);
  });
  addEventListener("keydown", e => {
    if ((e.key === "Enter" || e.key === " ") && e.target.classList?.contains("help")){
      e.preventDefault();
      helpToggle(e.target);
    } else if (e.key === "Escape" && helpAt) helpHide();
  });
  addEventListener("scroll", () => { if (helpAt) helpHide(); }, true);
}

// ---- the shell (R218 step 2) ---------------------------------------------
function bootShell(){
  // Its declarations are page-shell.js; what runs at load is this: the
  // address bar's back and forward open what they name, the search is wired,
  // and the phone's More sheet closes on a tap elsewhere.
  addEventListener("popstate", backPressed);
  // A link in a dialog goes the way hashGo does.
  document.addEventListener("click", e => {
    const a = e.target.closest?.('a[href^="#/"]');
    if (!a || e.defaultPrevented || e.button || e.ctrlKey || e.metaKey || e.shiftKey || !a.closest(".modal") || !history.state?.dlg) return;
    e.preventDefault();
    hashGo(a.getAttribute("href"));
  });
  addEventListener("hashchange", () => { sectNewVisit(); shellCame(shellSeen, location.hash); shellSeen = location.hash; if (!openRoute(location.hash)) shellSync(); });
  // The page the address names reads its own data now, on the read the head
  // began (preGets), so it is usually in hand when the first status read
  // draws the page, which then opens as itself rather than as a second
  // placeholder (the operator, 18 Oct).
  {
    const BOOT_LOADS = {"/api/home?light=1": homeOpen, "/api/users": loadUsers, "/api/roles": loadRoles, "/api/profile": loadProfile,
                        "/api/v1/nodes": loadNodes, "/api/storage": loadStorage, "/api/nginx": loadNginx, "/api/v1/jobs?n=100": loadJobs};
    for (const u of Object.keys(preGets)) (BOOT_LOADS[u] || (u.startsWith("/api/docker") ? () => dmBootLoad(u) : null))?.();
  }
  wireJump();
  document.addEventListener("click", e => {
    if (railMoreOpen && !e.target.closest("#railmore, [data-railmore]")) railMoreShow(false);
  });
}

// ---- a menu somebody has open ---------------------------------------------
// Its declarations are page-tabs.js.
// A redraw replaces the markup, and a <select> replaced while its list is
// showing takes the list with it. The Docker manager repaints on every step
// of a job, so picking a branch during a build was a race against the next
// step, and every other tab had the same race at a slower beat. Held at the
// three places a redraw nobody asked for starts from: the revisions poll
// (skipped whole, with the tokens not advanced, so the news is still news on
// the tick after), a document tab's draw, and paint(). A draw that came from
// a press is never held, because the press is what closed the menu.
//
// Nothing listens for the menu closing: there is no event for every way it
// can (a second click on it fires none). A short timer asks instead, and only
// while a redraw is owed.
const OPEN_KNOWN = (() => {
  try { document.documentElement.matches(":open"); return true; }
  catch(e){ return false; }
})();
function bootMenuHeld(){
  if (!OPEN_KNOWN){
    addEventListener("pointerdown", e => {
      selPressed = e.target.closest ? e.target.closest("select") : null;
      selPressedAt = Date.now();
    }, true);
    addEventListener("change", () => { selPressed = null; }, true);
    addEventListener("blur", e => { if (e.target === selPressed) selPressed = null; }, true);
    addEventListener("keydown", e => { if (e.key === "Escape") selPressed = null; }, true);
  }
}

// ---- a terminal in its own window (R8) ------------------------------------
function bootTermWindow(){
  // Its declarations are page-tabs.js.

  // The window closing is the tab coming back: polled, because a window on the
  // terminal's own URL runs none of this page's script to say so.
  setInterval(() => {
    let back = false;
    for (const [id, w] of popWins){
      if (!w.closed) continue;
      popWins.delete(id);
      const t = tabOf(id);
      if (t?.popped){ t.popped = false; back = true; }
    }
    if (back) render();
  }, 1500);
}

// ---- motion ----------------------------------------------------------
function bootPickers(){
  // A pulldown in a bar or a row is as wide as its longest answer, where a
  // base select is as wide as its chosen one (fitPickers, page-docs.js):
  // measured as the page draws one, or shows one it had hidden. Not where
  // the browser draws its own select, which is that wide already. Its own
  // writes are its style and a data attribute, which nothing here watches.
  if (!CSS.supports("appearance", "base-select")) return;
  new MutationObserver(fitPickersSoon).observe(document.body,
    {childList: true, subtree: true, characterData: true, attributes: true, attributeFilter: ["hidden", "class", "open"]});
  fitPickersSoon();
}
function bootMotion(){
  // FLIP, for both reorder surfaces: measure where the keyed elements sit,
  // let the caller do the (instant) DOM reorder, then play each element from
  // its old spot to its new one. The transform tween is what the eye follows.
  // Its functions are page-motion.js, with every height tween on the page.
  document.querySelectorAll(".modal:not(.inline)").forEach(armModal);
  // Focus in, Tab kept inside, Escape and focus back, for every dialog at
  // once (page-motion.js). Before the page's other keydown listeners, so a
  // dialog's Escape is not also a menu's or an armed arrow's.
  document.addEventListener("keydown", modalKeys);
  // A press that is taken (pressHook, page-motion.js): every click handler runs
  // as its button's press, which its requests and its promise hold.
  pressHook();
  // ...and what a press or a draw dropped unheard is said (sayUnheard, page-bell.js).
  addEventListener("unhandledrejection", sayUnheard);
  // A big chip already on is no change, so its press is none (B317, the
  // operator 24 Oct): no list drawn again, no fade, as the rail does nothing
  // for the group already on. Taken before any chip's own handler.
  document.addEventListener("click", e => {
    if (e.target.closest?.(".chip.on[aria-pressed='true']")){ e.stopPropagation(); e.preventDefault(); }
  }, true);
  // Scroll hints (scrollHints): on any scroll, which does not bubble but is
  // seen on its way down, after any draw (hintSoon), and on a slow clock for
  // content that grows under a box nobody is scrolling. Only the few hinted
  // boxes on show are measured.
  addEventListener("scroll", e => { if (e.target?.matches?.(SCROLL_HINTED)) scrollHint(e.target); }, true);
  setInterval(() => { if (!document.hidden) scrollHints(); }, 700);
}

// ---- an action bar's More menu ----------------------------------------
// A floating menu (floatAt) follows its button as the page scrolls or the
// window changes size, a frame at a time; a scroll inside the menu moves
// nothing under it.
let floatFrame = 0;
const floatSoon = e => { if (e?.target?.closest?.(".floatm") || floatFrame) return;
  floatFrame = requestAnimationFrame(() => { floatFrame = 0; floatFollow(); }); };
function bootMoreMenus(){
  // An action bar's More menu: a press anywhere but on its button shuts it,
  // its own items included, since each has done its work by then; Escape too.
  // A menu with a box to type in (the Git view's branch picker) keeps a press
  // in its box, and its opener ([data-menuopen]) opens and shuts it itself.
  document.addEventListener("click", e => {
    if (!e.target.closest(".actbar .more > button, [data-menuopen], .actmenu input")) closeMore();
  });
  document.addEventListener("keydown", e => { if (e.key === "Escape") closeMore(); });
  document.addEventListener("scroll", floatSoon, {capture: true, passive: true});
  // A chip row's scroll, kept as it moves and put back when it is drawn again
  // (page-docs.js chipsBack, from drawn()).
  document.addEventListener("scroll", chipsScrolled, {capture: true, passive: true});
  // A row of chips on a desk: its ends' arrows and a mouse drag (page-docs.js
  // chipsEdge), kept right as the window changes width.
  document.addEventListener("click", chipsArrow);
  document.addEventListener("click", chipsClickGuard, {capture: true});
  document.addEventListener("pointerdown", chipsDown);
  document.addEventListener("pointermove", chipsMove, {passive: true});
  document.addEventListener("pointerup", chipsUp);
  window.addEventListener("resize", () => chipsEdges());
  addEventListener("resize", floatSoon);
}

// ---- panes -----------------------------------------------------------
function bootPanes(){
  // Its declarations are page-panes.js.
  document.addEventListener("visibilitychange", () => {
    if (document.hidden){ hiddenAt = Date.now(); return; }
    // Only after long enough that the socket was really dropped: a quick glance
    // away keeps it, and reloading then would flash the terminal for nothing.
    // Gated to touch devices: a desktop page is throttled, not frozen, so its
    // sockets live through it, and a desktop reload on every alt-tab is noise.
    if (isPhone() && hiddenAt && Date.now() - hiddenAt > 3000) reattachTerminals();
    nudgeTerminals();
  });
  // A back/forward-cache restore always resumes with a dead socket, phone or not.
  window.addEventListener("pageshow", e => { if (e.persisted) reattachTerminals(); });
  window.addEventListener("focus", nudgeTerminals);
}

// ---- the dock's tabs, held and dragged ------------------------------------
function bootDockDrag(){
  // Its declarations are page-dock.js.
  // Before the hold the browser owns a moving finger and scrolls the dock's
  // line; after it, the finger's movement IS the drag. Registered once, here
  // and non-passive: the browser asks at a touch's start whether anything may
  // refuse its pan, so a listener added mid-gesture was asked too late and the
  // line scrolled under the lifted tab. The same half-second is the platform's
  // long-press menu, refused while a tab is held.
  window.addEventListener("touchmove", dockNoScroll, {passive: false});
  document.addEventListener("contextmenu", e => { if (ddrag) e.preventDefault(); });
}

// ---- the welcome panel: the guide, and the changelog ----------------------
// Which pane of a split is active decides where the keys and the commands
// go, and clicking into a terminal is the natural way to say "this one":
// focus landing in a pane says it, a terminal's own keyboard included. A
// VM's screen is a frame, and a click inside it never reaches this page;
// what does is the window losing focus to it, the frame then the active
// element: that is the click, one step removed.
const paneFocused = el => {
  // Its content, not its bar: a button there has its own press to make.
  const p = el?.closest?.(".stack")?.closest(".pane");
  if (!isSplit() || !p) return;
  const i = p.id === "pane1" ? 1 : 0;
  if (i !== active){ active = i; render(); }
};
function bootWelcome(){
  // Its declarations are page-welcome.js.
  // Two guides, because an administrator and a user see different rails:
  // the user's is what a person with projects and no machinery needs; the
  // administrator's adds the nodes, the tools, the accounts. Written here
  // rather than fetched, so the panel works on a first sign-in before anything
  // else has loaded.
  $("bAbout").onclick = () => openAbout();
  $("aboutClose").onclick = closeAbout;
  $("aboutTours").onclick = () => pressing($("aboutTours"), () => tourReset());
  // Escape and the backdrop mean what Close means (B229): the popup opens
  // itself after an update, over whatever the person came to do, and every
  // other dialog on the page lets them out either way. Escape is modalKeys'.
  document.querySelectorAll(".abswitch button").forEach(b => b.onclick = () => abShow(b.dataset.ab));
  $("aboutModal").onclick = e => {
    if (e.target.id === "aboutModal") closeAbout();
  };
  document.addEventListener("focusin", e => paneFocused(e.target));
  window.addEventListener("blur", () => {
    if (document.activeElement?.tagName === "IFRAME") paneFocused(document.activeElement);
  });
}

// ---- keys ------------------------------------------------------------
function bootKeys(){
  // Its declarations are page-keys.js.

  // Crossing the phone breakpoint (a rotation) draws again for the width.
  window.matchMedia("(max-width:900px)").addEventListener("change", () => render());
}

// ---- findings --------------------------------------------------------
function bootFindings(){
  // Its declarations are tab-findings.js; nothing of it runs at load.
  $("bOut").onclick = () => askSignOut();
}

// ---- logs --------------------------------------------------------------
// The log settings are the Controller page's Logs section; their functions
// (logSection) are page-gear.js's. The gear is wired here.

// One of the header's panels open at a time (the operator, 16 Oct: the
// doctor and the gear stood open together). Each button stops its click
// before the others' outside-click closers hear it, so each shuts the
// other two itself.
function headerOnly(keep){
  if (keep !== "gear" && uiMenuOpen) toggleUiMenu(false);
  if (keep !== "doctor" && docShown) toggleDoctor(false);
  if (keep !== "bell" && bellOpen) toggleBell(false);
}
function bootLogs(){
  $("bCards").onclick = e => { e.stopPropagation(); headerOnly("gear"); toggleUiMenu(); };
  document.addEventListener("click", e => {
    if (uiMenuOpen && !$("uiMenu").contains(e.target) && !$("bCards").contains(e.target))
      toggleUiMenu(false);
  });
  document.addEventListener("keydown", e => {
    if (e.key === "Escape" && uiMenuOpen) toggleUiMenu(false);
  });
}

// ---- doctor -----------------------------------------------------------
function bootDoctor(){
  // Its declarations are page-doctor.js; the dot, its panel's closing and ↻
  // are wired here.
  $("bDocDot").onclick = e => { e.stopPropagation(); headerOnly("doctor"); toggleDoctor(); };
  document.addEventListener("click", e => {
    if (docShown && e.target.isConnected
        && (!$("docPanel").contains(e.target) || e.target.closest("#docPanel a[href]"))
        && !$("bDocDot").contains(e.target))
      toggleDoctor(false);
  });
  document.addEventListener("keydown", e => {
    if (e.key === "Escape" && docShown) toggleDoctor(false);
  });
  $("bDoctor").onclick = () => runDoctor();
  // Controller settings on its Controller section, where the checks are.
  $("docSettings").onclick = () => {
    toggleDoctor(false);
    Object.assign(SPLIT.settings || (SPLIT.settings = {}), {pick: "controller", open: true});
    openSettingsTab();
  };
}

// ---- notebooks -----------------------------------------------------------
// Its declarations are nb-core.js.
// This browser tab, for as long as it is loaded. What makes "your other
// window" tellable from "you" in the presence line below (roadmap #26):
// the account is the same in both, so the account cannot be the answer.
const nbClient = Math.random().toString(36).slice(2) + Date.now().toString(36);
function bootNotebooks(){
  // A tab closed, reloaded or navigated away says so on its way out, so the
  // other windows stop naming it at once rather than for its seat's fifty
  // seconds: "your other window" about a window that is gone is the one line
  // presence exists to avoid (roadmap #26, B144).
  addEventListener("pagehide", () => notebooks.forEach(n => n.leave()));
}

// ---- a new project's first session ----------------------------------------
function bootFirstSession(){
  // Its declarations are page-claude.js.
  $("briefGo").onclick = () => briefGo(false);
  $("briefSkip").onclick = () => briefGo(true);
  $("briefCancel").onclick = closeBrief;
  $("briefModal").onclick = e => { if (e.target.id === "briefModal") closeBrief(); };
}

// ---- the new-project dialog ---------------------------------------------
function bootNewProject(){
  // Its declarations are tab-projects.js.
  $("pArchivePick").onclick = () => $("pArchive").click();
  $("pArchive").onchange = pArchivePicked;
  $("pLocal").onclick = () => pSwitch("init");
  $("pClone").onclick = () => pSwitch("clone");
  $("pLinkKey").onclick = () => { pLinkAuth = "key"; pDraw(); };
  $("pLinkToken").onclick = () => { pLinkAuth = "token"; pDraw(); };
  $("pKey").onchange = pShowKey;
  $("pForge").onchange = () => { pForgeId = $("pForge").value; pDraw(); };
  $("pCopy").onclick = async () => {
    // clipboard API needs a secure context; plain-http access to the dashboard
    // falls back to the selection route, which works everywhere a click does.
    const pub = $("pPub").textContent;
    try { await navigator.clipboard.writeText(pub); }
    catch { getSelection().selectAllChildren($("pPub")); document.execCommand("copy"); }
    notify("public key copied: paste it under the repo's Settings → Deploy keys");
  };
  $("pCancel").onclick = closeNewProject;
  $("pmodal").onclick = e => { if (e.target.id === "pmodal") closeNewProject(); };
  for (const f of ["pName", "pUrl"])
    $(f).onkeydown = e => { if (e.key === "Enter"){ e.preventDefault(); $("pCreate").click(); } };
  $("pName").oninput = () => { pNameTyped = true; pNameShow(); };
  $("pUrl").oninput = () => {
    if (pMode !== "clone" || pNameTyped) return;
    const u = $("pUrl").value.trim().replace(/\/+$/, "");
    const last = u.split(/[/:]/).pop() || "";
    $("pName").value = last.endsWith(".git") ? last.slice(0, -4) : last;
    pNameShow();
  };
  // ...and when a name HAS been typed, the URL still decides nothing, but the
  // warning has to keep up with a URL edited afterwards. So does the Host row
  // under the address, which reads it back as it is typed, in both modes.
  $("pUrl").addEventListener("input", pNameShow);
  $("pUrl").addEventListener("input", () => { if (pMode !== "init") pDraw(); });
}

// ---- the container dialogs: New container, and Send to Docker -----------
function bootContainerDialogs(){
  $("cTabForm").onclick = () => cSwitch("form");
  $("cTabYml").onclick = () => cSwitch("yml");
  // The form writes the compose file as it is filled in, and stops the moment
  // somebody edits that file by hand.
  for (const id of ["cImage", "cPorts", "cVols", "cEnvLines", "cRestart"])
    $(id).oninput = $(id).onchange = () => cFormWrote();
  $("cYml").oninput = () => { cYmlTouched = true; };
  $("cTabEnv").onclick = () => cSwitch("env");
  $("cImport").onclick = () => $("cImportFile").click();
  $("cImportFile").onchange = cImportPicked;
  $("cUnder").onchange = cUnderPicked;
  // An app's panel (R238): its file left by hand, one way, and its folders
  // suggested from the node picked.
  $("cByHand").onclick = cAppByHand;
  $("cNode").onchange = cAppNodePicked;
  $("cName").addEventListener("input", cAppNameTyped);
  $("dnUnder").onchange = dnNodeSay;
  $("rnNode").onchange = () => {
    // Italic only while the removed node is the one shown (page-projsettings.js).
    $("rnNode").classList.toggle("removed", !!$("rnNode").selectedOptions[0]?.classList.contains("removed"));
    rnFillNodesMore();
  };
  // Each Also reaches row ticks among the nodes picked above, so it follows them.
  // ...and so do its records, which redraw them when they move.
  // Add an address opens its form at the table's top.
  $("rnReachAdd").onclick = () => { rnReachEdit = {i: -1, form: {addr: "", nodes: []}}; rnDrawReach(true); };
  $("cGo").onclick = cSubmit;
  // The controller restarted under unsaved work: the band's one press (page-poll.js).
  $("newBuildGo").onclick = () => location.reload();
  $("cCancel").onclick = () => { $("cmodal").hidden = true; };
  $("cmodal").onclick = e => { if (e.target === $("cmodal")) $("cmodal").hidden = true; };
  $("dnName").oninput = dnShow;
  $("dnGo").onclick = dnSubmit;
  $("dnCancel").onclick = closeSendToDocker;
  $("dnmodal").onclick = e => { if (e.target === $("dnmodal")) closeSendToDocker(); };
  $("rlGo").onclick = rlSubmit;
  $("rlCancel").onclick = closeRelocate;
  $("rlmodal").onclick = e => { if (e.target === $("rlmodal")) closeRelocate(); };
  document.querySelectorAll('input[name="rlMode"], input[name="rlData"]').forEach(r => r.onchange = rlSay);
  $("rlNode").onchange = rlSay;
}

// ---- a project's settings dialog, wired ---------------------------------
// Each section's Save, Save, keep it running, Save and end it and Revert,
// and every change kept in step with its bar. On the form itself, which
// moves between the dialog and a notebook's Settings view.
// Wired on whatever holds a part of it: the dialog's box, and the
// Permissions view's, which Agents may is lent into (rnWireBox there): on
// the dialog's box alone, a dial changed on Permissions never lit its Save.
function rnWireBox(box){
  if (!box || box.dataset.rnwired) return;
  box.dataset.rnwired = "1";
  box.addEventListener("click", e => {
    const b = e.target.closest("[data-rnsave],[data-rnkeep],[data-rnend],[data-rnrevert]");
    if (b && !b.disabled){
      if (b.dataset.rnrevert){
        const said = rnSectChanges(b.dataset.rnrevert).said;
        if (said.length) askYes(`Revert ${said.join(", ")}?\n\nIt goes back to what is saved.`)
          .then(yes => { if (yes) rnRevertSect(b.dataset.rnrevert); });
      } else rnSubmit(b.dataset.rnsave || b.dataset.rnkeep || b.dataset.rnend, !!b.dataset.rnend);
      return;
    }
    setTimeout(rnBars, 0);
  });
  for (const ev of ["input", "change"]) box.addEventListener(ev, () => setTimeout(rnBars, 0));
}
function bootProjectSettings(){
  // Its declarations are page-projsettings.js.
  $("rnName").oninput = rnShow;
  rnWireBox($("rnmodal").querySelector(":scope > .box"));
  $("rnTokenClear").onclick = () => {
    rnClearToken = !rnClearToken;
    if (rnClearToken) $("rnToken").value = "";   // whatever was typed was for the
    rnDrawAuth();                                // token being thrown away
    if (rnClearToken) $("rnToken").focus();
  };
  $("rnAuthNone").onclick = () => rnAuthSet("none");
  $("rnAuthKey").onclick = () => rnAuthSet("ssh");
  $("rnAuthToken").onclick = () => rnAuthSet("https");
  // Typing a token can turn the disabled side on: setting one and switching to
  // it is a single intention, and the submit does them in that order.
  $("rnToken").addEventListener("input", rnDrawAuth);
  $("rnTest").onclick = rnTestAuth;
  $("rnKeyMake").onclick = () => rnKeyAct("key-make");
  $("rnKeyPasteBtn").onclick = () => {
    if ($("rnKeyPaste").hidden){ $("rnKeyPaste").hidden = false; $("rnKeyPaste").focus(); rnDrawKey(); return; }
    rnKeyAct("key-store");
  };
  $("rnKeyForget").onclick = () => rnKeyAct("key-forget");
  $("rnKeyCopy").onclick = async () => {
    const pub = $("rnKeyPub").textContent;
    try { await navigator.clipboard.writeText(pub); }
    catch { getSelection().selectAllChildren($("rnKeyPub")); document.execCommand("copy"); }
    notify("public key copied: add it on the host as a deploy key with write access");
  };
  $("rnUnlink").onclick = () => unlinkProject(rnFor);
  $("rnDelete").onclick = () => { const n = rnFor; closeRename(); deleteProject(n); };
  // Closing with a section unsaved asks, naming what would go.
  $("rnCancel").onclick = async () => {
    const d = rnDirty().map(x => document.querySelector(`details.rngroup[data-sect="rn:${x}"] .t`)?.textContent || x);
    const opening = rnOpens;
    if (d.length && !await askYes(`Close without saving?\n\n${d.join(", ")} would be dropped.`,
                                  {verb: "Close without saving", danger: true})) return;
    // The answer came after the dialog was opened again: that one stays.
    if (opening !== rnOpens) return;
    closeRename();
  };
  // The settings' sections take turns, one open at a time, as a tab's do.
  wireSections($("rnmodal"));
  $("rnmodal").onclick = e => { if (e.target === $("rnmodal")) $("rnCancel").click(); };
}

// ---- creating a project -------------------------------------------------
function bootCreating(){
  $("pCreate").onclick = createProject;
}

// ---- what the page has said, and what is waiting on you ----------------
function bootNotices(){
  // Its declarations are page-bell.js.
  $("bBell").onclick = e => { e.stopPropagation(); headerOnly("bell"); toggleBell(); };
  // A toast being read stays: the stack's clocks stop under the pointer.
  $("toast").addEventListener("pointerenter", () => toastHold(true));
  $("toast").addEventListener("pointerleave", () => toastHold(false));
  $("pendApprove").onclick = () => pendAct("approve");
  $("pendDeny").onclick = () => pendAct("deny");
  $("pendClose").onclick = () => { $("pendModal").hidden = true; pendFor = null; };
  $("pendModal").onclick = e => { if (e.target === $("pendModal")){ $("pendModal").hidden = true; pendFor = null; } };
  $("tClose").onclick = () => { $("tmodal").hidden = true; };
  $("tmodal").onclick = e => { if (e.target === $("tmodal")) $("tmodal").hidden = true; };
  // Anywhere else closes it, including the header around it: a panel you have
  // to aim at the bell again to shut is a panel in the way.
  //
  // Except a target that is no longer in the document. Every control in this
  // panel redraws the panel, which detaches the very button that was clicked
  // before the event finishes bubbling to here, so `panel.contains(target)`
  // answered false about a button that had been inside it a moment ago, and
  // Clear shut the whole panel as a side effect of clearing. Approve and Deny
  // did the same. isConnected is the honest question: a node that left the
  // document during its own handler was not a click somewhere else.
  document.addEventListener("click", e => {
    if (bellOpen && e.target.isConnected
        && !$("bellPanel").contains(e.target) && !$("bBell").contains(e.target))
      toggleBell(false);
  });
  document.addEventListener("keydown", e => {
    if (e.key === "Escape" && bellOpen) toggleBell(false);
  });
}

// ---- what changed, and who cares ------------------------------------------
function bootWatches(){
  // Its declarations are page-poll.js.

  // The Docker manager follows the same revision every dev-instance control
  // already moved on. Without this it is a snapshot: correct when it loaded and
  // stale from the first Up, with a Refresh button as the only way back, which
  // is a page that tells you what used to be running.
  onRev("devapp", () => {
    if (shown("docker")){ dmJobSettle(); dockerList = null; readMoved("docker"); loadDocker(); }
    // ...and the nginx page, whose state line is its container's: a Save's
    // rebuild ending moves this and nothing of nginx's own, and the line
    // said "deployed, down" over a container long since up again (B65).
    if (shown("nginx")) loadNginx();
  });
  // ...and a node's containers changing outside AerieOS (one crashed, a
  // shell or a session ran docker): read again in place, the rows kept on
  // screen until the answer replaces them. This is why the page has no
  // Refresh (the operator, 17 Oct).
  onRev("containers", () => {
    if (shown("docker") && !readBusy("docker")) loadDocker();
  });
  // Coming back to the tab is the common case, so it is the one that must be
  // instant: read immediately, before any timer has a chance to fire.
  document.addEventListener("visibilitychange", () => {
    reschedRevs();
    if (!document.hidden){ pollRevs(); refresh(); }
    else statusLater();
  });
  reschedRevs();
  pollRevs();
}

// ---- saying so when nobody is looking at the page --------------------------
// Its declarations are page-badge.js.
const ICON = document.querySelector('link[rel="icon"][href^="data:"]');
// getAttribute, not .href: the property comes back through the URL parser and
// what goes into a data: URI should be the literal that was written.
const ICON_BASE = ICON ? ICON.getAttribute("href") : "";
function bootAway(){
  // A request arriving or being answered, and a phone connecting or going away.
  // Both are facts this card displays and neither is a fact it owns, which is
  // exactly the shape that used to go stale.
  onRev("prefs", () => refresh());
  // Pull to refresh on a touch screen (page-pull.js): the header's ↻ it replaced.
  wirePull();
  // A lent phone, live (R113): a session's screenshot reaches the Phone tab.
  onRev("phone.lease", () => { if (shown("phone")) phFetch(); });
  // Who has a session where, and whether it is working: the light fetch, so
  // the dot beside a name follows a session within seconds.
  onRev("live", () => liveRefresh());
  // The controller's own settings, which the tab draws out of `state`: another
  // window saved, or `aerie` wrote the file. The server has published this token
  // since the store was built and nothing watched it, so the tab that owns the
  // setting was the one place a change took fifteen seconds to show.
  onRev("settings", () => refresh());
  // The toolchain store: an install or an uninstall finishing, or the version
  // check. The Toolchains page used to keep a timer of its own for this (half
  // a second while a job ran, eight seconds otherwise) which is a third clock
  // for a fact the poll already carries. The Library (R170) and the Installed
  // page (R172) read on it.
  onRev("toolchains", () => {
    if (shown("library")) loadLibrary();
    if (shown("entry")) loadEntry();
    if (shown("installed")) loadInstalled();
  });
  // Google's image index landing, for the Emulator tab's picker.
  onRev("emulator", () => {
    if (shown("emulator")) loadEmulator();
  });
  // The node registry moved: a mutation here, or another browser's. Open
  // views refetch; node data deliberately never rides the status poll
  // (docs/nodes.md §13).
  // The nginx record moved: a route or certificate saved here, from a
  // container's row on the Docker tab (R209), by bb or by another browser
  // (B714). An open nginx tab re-reads around its draft; an open Docker tab
  // re-reads too, since its rows say which ports are routed.
  // The VMs page (R91): a record written, a job ended, or a node's hello
  // carrying what its VMs are doing now.
  // ...and read for a console tab too, which goes when its VM does (B172).
  onRev("vms", () => { if (shown("vms") || tabs.some(vmConsoleTab)) loadVms(); });
  onRev("nginx", () => {
    if (shown("nginx")) loadNginx();
    if (shown("docker")){ dockerList = null; readMoved("docker"); loadDocker(); }
  });
  onRev("nodes", () => {
    // The list is drawn by every page with a node picker, not the Nodes page
    // alone: re-read for the one on show, and when none is, marked stale, so
    // the next page to read it loads a fresh one rather than a list from
    // before a node enrolled or retired.
    if (NODE_READERS.some(shown)) loadNodes();
    else nodesStale = true;
    // A node's census carries its images: refetched only when they moved.
    if (shown("emulator")) emuOnNodes();
    // ...and Storage, whose walk lands with a node's census: the numbers a
    // Measure now asked for arrive with no Refresh (the operator, 17 Oct).
    if (shown("storage")) loadStorage();
    // ...and the Library and the Installed page, whose agents' versions ride
    // a node's census (R95); a page that said no node yet looks again.
    if (shown("library")) loadLibrary();
    if (shown("entry")) loadEntry();
    if (shown("installed") || shown("thing")) loadInstalled();
    if (shown("emulator") && emu?.nonode) loadEmulator();
    // ...and Home's Getting started, which says whether a node is online.
    if (shown("home") && homeStartReadsNodes()) loadNodes().then(() => drawPanes());
    // ...and what is drawn off the status poll (the bell, the doctor): a job
    // on a node moves this rev, so they say it inside a second or two instead
    // of at the next fifteen-second poll.
    refresh();
  });
  // A heartbeat's numbers alone (R218 step 10): the Nodes page draws them,
  // its meters and its hour's charts, and no other page does, so no other page
  // re-reads anything for them.
  onRev("nodes.sample", () => { if (shown("nodes")) loadNodes(); });
  // A message between accounts (R218 step 10): the chat open on a conversation
  // reads it, and nothing is read while it is shut.
  onRev("chat", () => { if (chatWith && tabOf(panes[1])?.kind === "chat") loadChat(); });
  // The queue moved: a job taken, a step, a result, a cancel. Same rule: an
  // open Jobs tab refetches, and nothing about jobs rides the status poll.
  onRev("jobs", () => {
    if (shown("jobs")) loadJobs();
    // ...and the Schedules page, whose last runs are jobs (R117).
    if (shown("schedules")) loadSchedules();
    // Home's queue and node counts, its containers kept (R218 step 5).
    if (shown("home")) loadHome(true);
    // ...and the jobs a toast is following (R218 step 6).
    if (jobToasts.size) jobToastsCheck();
    if (shown("emulator")) loadEmulator();
  });
  // The Phone tab's data (tab-phone.js): fetched here too, because the bell
  // carries the same asks whether or not the tab is open.
  onRev("phone.asks", () => phFetch());
  // The badge follows the count directly rather than waiting for the fetch, so
  // the tab strip is right even if the page is throttled too hard to redraw.
  onRev("phone.asks", k => setBadge(revs[k] || 0));
  onRev("phone.dev", () => { if (shown("phone")) phFetch(); });
  phFetch();
}

// ---- the document-tab scaffold ------------------------------------------
function bootDocs(){
  // Its declarations are page-docs.js.
  // Crossing the phone width re-judges every group's folds (oneOpen): a desk
  // this page is widened to shows them open again, and a phone it is
  // narrowed to keeps one; nothing else redraws a surface whose data has not
  // moved (B723's fix made the phone's one-open stick on the way back up).
  matchMedia("(max-width:900px)").addEventListener("change", () =>
    document.querySelectorAll(".doctab, .nbview, [data-sects]").forEach(g => oneOpen(g)));
  // Recorded for every keyed fold from one place. `toggle` does not bubble, but
  // it is captured, so a fold needs a key and nothing else to be remembered.
  // Only a fold somebody pressed: markup arriving with `open` on it fires the
  // same event, and recording that would turn a default into a choice, which
  // is how a desktop's open-by-default followed the page down to phone width.
  document.addEventListener("click", e => {
    const d = e.target.closest?.("summary")?.parentElement;
    if (!d?.dataset?.sect) return;
    d.dataset.pressed = "1";
    // Recorded at the press, not only at `toggle`: a section slides shut over
    // a third of a second, and a tab that repaints on a heartbeat (Nodes, on
    // every one) replaced the fold mid-slide, so the toggle fired on a
    // detached element nobody heard and the new fold drew open again. The
    // press is the choice; `toggle` below confirms it for the other ways a
    // fold can move.
    sectOpen[d.dataset.sect] = !foldOpen(d);
  }, true);
  document.addEventListener("toggle", e => {
    fxRemember(e);                        // a finding's rule, open or shut (tab-findings.js)
    const d = e.target;
    if (d?.dataset?.sect && d.dataset.pressed) sectOpen[d.dataset.sect] = d.open;
  }, true);
}

// ---- the last of the wiring: the popup menus, the command editor, Escape --

function bootLast(){
  // Both popup menus dismiss on a click that is neither in them nor on the
  // control that opened them.
  document.addEventListener("click", e => {
    if (resumeFor && !e.target.closest(".resumemenu, [data-c], .modal")){
      resumeFor = null;
      if (state) drawProjects(state.projects);
    }
  });
  document.addEventListener("keydown", e => {
    if (e.key !== "Escape") return;
    // A dialog's Escape is modalKeys' (page-motion.js), which stops the event
    // before it reaches here.
    // Escape puts an armed arrow down, in whichever notebook holds one. It
    // closes nothing: the notebook is a tab, and tabs are not dismissed by a
    // keystroke.
    let armed = false;
    notebooks.forEach(nb => { if (nb.escape()) armed = true; });
    if (armed) return;
    if (resumeFor){ resumeFor = null; if (state) drawProjects(state.projects); }
  });
  refresh();
  // Its next read is the status poll's own business now (page-poll.js,
  // statusLater): fifteen seconds after the last read, none while hidden. The
  // timer calls through the binding, not the function: the harness holds the
  // poll by replacing `refresh` (lib.mjs holdPoll), and a timer that captured
  // the original kept polling under a planted row (B265).
    // Two presses that were inline handlers (R158 step 4: no inline script).

  $("bReport").onclick = () => openReport("");
  $("devEnvCancel").onclick = () => { $("devEnvModal").hidden = true; };
}
