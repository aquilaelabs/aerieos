// Motion: the one reduced-motion gate, the FLIP for both reorder surfaces,
// and every height tween on the page (a card, a <details>, a box under a
// row, a block that is shown and hidden). Height is real layout, so what is
// below rides along frame by frame instead of jumping, which is the whole
// vocabulary; docs/design-language.md, Motion.
// One classic script beside index.html (docs/design-language.md, Files): pure
// declarations, nothing runs at load. The modals are armed and the Tools
// icons put on from index.html, under the motion header.

"use strict";

// Less motion, asked for by the device or by the account in the gear's menu
// (the operator, 19 Oct): the one gate every moving thing asks.
const noMotion = () => document.documentElement.dataset.motion === "reduce"
  || matchMedia("(prefers-reduced-motion: reduce)").matches;

// The account's choice, as the scheme is kept: on <html> for the paint
// (index.html reads it before the stylesheet does), in this browser for the
// next load, and on the account for a browser that has never seen it.
let motionSaved = null;
function applyMotion(reduce, {save = true} = {}){
  const root = document.documentElement;
  if (reduce) root.dataset.motion = "reduce";
  else delete root.dataset.motion;
  if (!save) return;
  const use = reduce ? "reduce" : "system";
  try{ localStorage.setItem("bb.motion", use); localStorage.setItem("bb.motion.who", state?.me || ""); }catch(e){ /* private mode */ }
  motionSaved = use;
  postJSON("/api/users", { action: "prefs", prefs: { motion: use } }).catch(() => {});
}
// ...taken up only by a browser that has none of its own (adoptTheme's rule).
function adoptMotion(m, who){
  let had, whose;
  try{ had = localStorage.getItem("bb.motion"); whose = localStorage.getItem("bb.motion.who"); }catch(e){ return; }
  const same = !who || !had || (whose || "") === who;
  if (had && same) return;
  const use = m === "reduce" ? "reduce" : "system";
  if (same && (!m || use === motionSaved)) return;
  motionSaved = use;
  applyMotion(use === "reduce");
}

// Every modal leaves the way it arrived. Closing one is `hidden = true` at a
// dozen sites, and any dialog added later closes the same way, so the leaving
// lives on the property itself: `hidden` on a modal is its own accessor, and
// setting it plays the tween first and puts the attribute on when the tween
// ends. Nothing at a call site to remember, and nothing for a watcher to
// misread: a hide of a modal already hidden is a hide, a show mid-leave
// drops the tween and shows. (An observer on the attribute did this first,
// and re-showing the element to play the tween was what every other test
// on the page tripped over.)
function armModal(el){
  if (!el || el.__modalArmed) return;
  el.__modalArmed = true;
  Object.defineProperty(el, "hidden", {
    configurable: true,
    // Hidden the moment it is told to, to everything that asks: the poll
    // and the cards read a dialog's state to decide what to repaint, and a
    // dialog that read as open for the length of its tween had them draw
    // the page as if it were. Only the pixels linger.
    get(){ return this.hasAttribute("hidden") || this.classList.contains("leaving"); },
    set(v){
      if (!v){
        const was = this.hasAttribute("hidden") || this.classList.contains("leaving");
        this.getAnimations().forEach(a => a.cancel());
        this.querySelector(":scope > .box")?.getAnimations().forEach(a => a.cancel());
        this.classList.remove("leaving");
        this.removeAttribute("hidden");
        // A dialog opens at its top: the box kept where it was last scrolled
        // to, and a field focused on the way in scrolled it further, so one
        // opened on a phone could start halfway down (the operator, 30 Sep).
        // Again after the frame, for what the opener fills and focuses.
        if (was){ modalTop(this); modalOpened(this); requestAnimationFrame(() => { modalTop(this); scrollHints(this); }); }
        return;
      }
      if (this.hasAttribute("hidden") || this.classList.contains("leaving")) return;
      modalClosed(this);
      if (noMotion()){ this.setAttribute("hidden", ""); return; }
      this.classList.add("leaving");
      this.querySelector(":scope > .box")?.animate(
        [{opacity: 1, transform: "none"}, {opacity: 0, transform: "translateY(6px) scale(.985)"}],
        {duration: 150, easing: "ease"});
      this.animate([{opacity: 1}, {opacity: 0}], {duration: 150, easing: "ease"}).finished.then(
        () => { if (this.classList.contains("leaving")){ this.classList.remove("leaving"); this.setAttribute("hidden", ""); } },
        () => {});                        // canceled: it was shown again, and stays
    }});
  // A press on the dimmed page around it is its way out, as Escape is: its
  // own backdrop handler where it has one, else its foot's Cancel or Close.
  // One holding something shown once (data-keep-stray) keeps the press.
  el.addEventListener("click", e => {
    if (e.target !== el || el.dataset.keepStray !== undefined) return;
    setTimeout(() => { if (!el.hidden) modalWayOut(el)?.click(); }, 0);
  });
}
// A dialog's way out at its foot: the one marked data-way-out where its
// words are its own (Keep it), else its Cancel or Close.
function modalWayOut(m){
  const bs = [...m.querySelectorAll(":scope > .box .foot button")].filter(b => !b.disabled);
  return bs.find(b => b.dataset.wayOut !== undefined) || bs.find(b => /^(cancel|close)$/i.test(b.textContent.trim())) || null;
}

// ---- a dialog and the keyboard ------------------------------------------
// One place for what every dialog does with the keyboard (R88), rather than
// an Escape listener per dialog, which seven of the sixteen had: it takes
// the focus as it opens, so a screen reader starts in it and Tab starts
// from it; Tab and Shift+Tab go round inside it rather than out to the page
// behind; Escape closes it, as the design says every dialog's foot does;
// and the focus goes back to what opened it. The stack is the order they
// opened in, so Escape closes the one on top.
const openModals = [];

function topModal(){
  for (let i = openModals.length - 1; i >= 0; i--){
    const m = openModals[i];
    if (!m.isConnected || m.hidden){ openModals.splice(i, 1); continue; }
    // A notebook's reading room in a tab that is not showing is open but
    // not on screen, and not the one a key is meant for.
    if (m.getClientRects().length) return m;
  }
  return null;
}

function modalOpened(el){
  const i = openModals.indexOf(el);
  if (i >= 0) openModals.splice(i, 1);
  openModals.push(el);
  if (el.dataset.keepStray === undefined && !el.__backTok)
    el.__backTok = backHold(() => { el.__backTok = 0; dismissModal(el); });
  const a = document.activeElement;
  el.__opener = a && a !== document.body && !el.contains(a) ? a : null;
  // A dialog is named by its title for a screen reader, which the markup
  // says by aria-labelledby; one made in a script gets its h3 named here.
  const h = el.querySelector(":scope > .box h3");
  if (h && !el.hasAttribute("aria-labelledby")){
    if (!h.id) h.id = (el.id || "dlg") + "Title";
    el.setAttribute("aria-labelledby", h.id);
  }
  // After the frame, as modalTop's second pass: the opener fills the
  // dialog then, and may focus a field of its own, which is left alone. The
  // box itself otherwise, not its first field: a phone would raise its
  // keyboard over a dialog the person came to read.
  requestAnimationFrame(() => {
    toastPlace();
    if (el.hidden || el.contains(document.activeElement)) return;
    const box = el.querySelector(":scope > .box") || el;
    if (!box.hasAttribute("tabindex")) box.setAttribute("tabindex", "-1");
    box.focus({preventScroll: true});
  });
}

function modalClosed(el){
  const i = openModals.indexOf(el);
  if (i >= 0) openModals.splice(i, 1);
  toastPlace();
  if (el.__backTok){ backRelease(el.__backTok); el.__backTok = 0; }
  const back = el.__opener, a = document.activeElement;
  el.__opener = null;
  // Only when the focus was still in the dialog: a Save that opened a tab
  // or a dialog that opened another has put it somewhere on purpose.
  if (a && a !== document.body && !el.contains(a)) return;
  if (!back || !back.isConnected || back.disabled || !back.getClientRects().length){ a?.blur?.(); return; }
  // Never into a text field: on a phone that raises the keyboard for nothing.
  if (back.matches("textarea, [contenteditable], input:not([type=checkbox]):not([type=radio]):not([type=button])")){
    a?.blur?.(); return;
  }
  back.focus({preventScroll: true});
}

// ---- a dialog and Back ----------------------------------------------------
// Back puts the dialog on show away and leaves the page under it where it
// was, as a phone's own apps do. A dialog opened holds an entry in the
// history: the page's own address, its number in the entry's state. Back
// leaving that entry puts away everything held after the entry it lands
// on, each as Escape would. Put away any other way, a dialog gives its entry
// back, unless the page has moved on from it. One holding something shown
// once (data-keep-stray) holds none, and Back passes it by.
let backHolds = [], backSeq = 0, backGiving = false, backAfter = null;

// Hold an entry for something Back puts away with `shut`; its number.
function backHold(shut){
  const tok = ++backSeq, cur = history.state?.dlg;
  const st = {...(history.state || {}), dlg: tok};
  // An entry a dialog just put away has not given back yet is this one's.
  if (cur && !backHolds.some(h => h.tok === cur)) history.replaceState(st, "", location.href);
  else history.pushState(st, "", location.href);
  backHolds.push({tok, shut});
  return tok;
}

// Let a hold go when what it held was put away some other way.
function backRelease(tok){
  const i = backHolds.findIndex(h => h.tok === tok);
  if (i < 0) return;
  backHolds.splice(i, 1);
  setTimeout(() => {
    if (history.state?.dlg !== tok) return;        // the page moved on, or another dialog took it
    backGiving = true;
    history.back();
  }, 0);
}

// The page's popstate: Back (or Forward) moved between entries.
function backPressed(){
  const at = history.state?.dlg || 0;
  if (backGiving){
    backGiving = false;
    // A page opened while the entry was being given back is put in the
    // history now that it has gone: pushed before, the give-back landed
    // after it and took the page back with it (shellPush, shellSync).
    if (backAfter){ const to = backAfter; backAfter = null; history.pushState(null, "", to); shellSeen = to; }
    else shellSync();
    // One opened while its entry was being given back holds one again.
    const top = backHolds.at(-1);
    if (top && at < top.tok) history.pushState({...(history.state || {}), dlg: top.tok}, "", location.href);
    return;
  }
  const gone = backHolds.filter(h => h.tok > at);
  backHolds = backHolds.filter(h => h.tok <= at);
  gone.reverse().forEach(h => h.shut());
}

// Go to a page from a dialog: the dialog's entry becomes the page's, so
// Back from there comes to the page the dialog was opened on.
function hashGo(to){
  if (history.state?.dlg) location.replace(to);
  else location.hash = to;
}

function modalFocusables(m){
  return [...m.querySelectorAll(`a[href], button, input, select, textarea, [contenteditable="true"],
                                 [tabindex]:not([tabindex="-1"])`)]
    .filter(x => !x.disabled && x.type !== "hidden" && x.getClientRects().length);
}

// Escape closes the dialog the way it closes itself: its backdrop's "never
// mind" where it has one (which may tidy up, as closeEditor and closeRename
// do), else its foot's way out (modalWayOut), else simply hidden.
function dismissModal(m){
  m.dispatchEvent(new MouseEvent("click", {bubbles: true}));
  if (m.hidden) return;
  modalWayOut(m)?.click();
  if (!m.hidden) m.hidden = true;
}

// The page's one keydown listener for dialogs, wired at load by page-boot.js
// ahead of the page's other Escape listeners: a dialog's Escape is its own,
// and the menus and armed arrows under it are not closed with it. A field
// that does something with Escape itself (a filter clearing its search)
// stops the event first and keeps the dialog open.
function modalKeys(e){
  if (e.key !== "Escape" && e.key !== "Tab") return;
  const m = topModal();
  if (!m) return;
  if (e.key === "Escape"){
    e.preventDefault(); e.stopImmediatePropagation();
    dismissModal(m);
    return;
  }
  const all = modalFocusables(m), a = document.activeElement;
  if (!all.length){ e.preventDefault(); return; }
  const first = all[0], last = all[all.length - 1];
  if (!m.contains(a)){ e.preventDefault(); (e.shiftKey ? last : first).focus(); }
  else if (e.shiftKey && (a === first || !all.includes(a))){ e.preventDefault(); last.focus(); }
  else if (!e.shiftKey && a === last){ e.preventDefault(); first.focus(); }
}

// Every scroller in a dialog back at its top, the dialog's own included.
function modalTop(el){
  el.scrollTop = 0;
  el.querySelectorAll(".box, .box *").forEach(x => { if (x.scrollTop) x.scrollTop = 0; });
}

// ---- scroll hints -------------------------------------------------------
// A box that scrolls says so: a soft shadow on each edge with more past it,
// gone at the end (the operator, 30 Sep). A phone hides its scrollbars until
// a finger moves, and a dialog cut off at a field boundary read as the whole
// dialog. An inset shadow rather than a painted gradient, since several
// themes put their own texture on these grounds; the classes are set here,
// from the box's own numbers, on scroll and on a slow clock for content that
// grows while nobody scrolls.
// ...and the lists and logs that scroll inside a surface: a project's Reads
// and nodes in its settings, the notebook's lists, a job's log, the chat
// (the operator, 30 Sep).
const SCROLL_HINTED = ".modal:not([hidden]):not(.inline) > .box, .modal:not([hidden]):not(.inline) .sheetslot, .pane .doc.on, "
  + ".lbox, #roadmapList, #memList, #pendList, .dllog, .dmlog, .chatlog, .mpanel.show, .abpage, .dsboardwrap";
function scrollHint(el){
  const more = el.scrollHeight - el.clientHeight > 2;
  el.classList.toggle("scrollup", more && el.scrollTop > 2);
  el.classList.toggle("scrolldown", more && el.scrollTop + el.clientHeight < el.scrollHeight - 2);
}
// Without a root, the parts on show alone: a pane's page, an open dialog, an
// open menu (R228 step 14). A box in a page left behind the one on show is
// one content-visibility spares laying out, and measuring it laid it out
// again, every look.
const HINT_ROOTS = ".pane .doc.on, .modal:not([hidden]), .mpanel.show";
function scrollHints(root){
  if (!root){ document.querySelectorAll(HINT_ROOTS).forEach(scrollHints); return; }
  root.querySelectorAll(SCROLL_HINTED).forEach(scrollHint);
  if (root.matches?.(SCROLL_HINTED)) scrollHint(root);
}
// ...and once a frame after a draw, however many parts it drew (drawHTML
// and patch ask), so a box a draw made long says so at once rather than at
// the clock's next look. The clock stays for what grows without a draw of
// either (a notebook moved into its pane, a fold's last frame, a log).
let hintFrame = 0;
function hintSoon(){
  if (hintFrame) return;
  hintFrame = requestAnimationFrame(() => { hintFrame = 0; if (!document.hidden) scrollHints(); });
}

// Things that move to a new place slide there from the old one: their
// places read before a change (`els`, each known by `key`), and the returned
// function, called once it is drawn, plays each from its old place to its
// new over `ms`.
function flip(els, key, ms = 140){
  if (noMotion()) return () => {};
  const before = new Map([...els()].map(el => [key(el), el.getBoundingClientRect()]));
  return () => [...els()].forEach(el => {
    const a = before.get(key(el));
    if (!a || !a.width) return;                // not on screen before: nothing to slide from
    const b = el.getBoundingClientRect();
    if (!b.width) return;
    const dx = a.left - b.left, dy = a.top - b.top;
    if (dx || dy)
      el.animate([{transform: `translate(${dx}px,${dy}px)`}, {transform: "none"}],
                 {duration: ms, easing: ms > 200 ? "cubic-bezier(.2,.8,.2,1)" : "ease"});
  });
}

// The same fold, on a <details> and on a plain hidden block: the memories,
// the bug reports, and a roadmap row's details. A <details> snaps open by
// construction and a [hidden] block appears with no in-between, so both are
// driven here instead: measure, flip the state, measure again, and tween
// between the two real heights. Height is real layout, so everything below
// rides along frame by frame rather than jumping.
function foldHeight(el, from, to, done){
  // Only its own kind: another animation on the element is not this fold's.
  el.getAnimations().forEach(a => { if (a.id === "fold") a.cancel(); });
  el.style.overflow = "hidden";
  const anim = el.animate([{height: from + "px"}, {height: to + "px"}],
                          {duration: 180, easing: "ease"});
  anim.id = "fold";
  const settle = () => { el.style.overflow = ""; el.style.height = ""; };
  anim.onfinish = () => { done(); settle(); };
  // Canceled by a newer fold: that one owns the element now, and it measured
  // its own starting height from wherever this one had got to.
  anim.oncancel = settle;
}

// A <details>, which has to be open while it shrinks or there is nothing to
// see moving, so the flag is set true for the tween and written for real at
// the end, whichever direction it went.
function slideDetails(el, willOpen){
  const sum = el.querySelector("summary");
  // A slide still running is this one's to replace, from where it has got
  // to: left to finish, its end wrote its own open or shut over this press
  // (a fold opened while its closing slide ran shut again a moment later).
  const running = el.getAnimations().filter(a => a.id === "fold");
  if (!sum || noMotion()){ running.forEach(a => a.cancel()); el.open = willOpen; delete el.dataset.slideTo; return; }
  const from = el.offsetHeight;
  running.forEach(a => a.cancel());
  el.open = true;
  const to = willOpen ? el.offsetHeight : sum.offsetHeight;
  if (from === to){ el.open = willOpen; delete el.dataset.slideTo; return; }
  el.dataset.slideTo = willOpen ? "1" : "0";
  foldHeight(el, from, to, () => { el.open = willOpen; delete el.dataset.slideTo; });
}
// Whether a fold reads as open to a press: where its slide is headed while
// one runs, since it is held open for the tween, else its own flag. Read as
// open mid-slide, a second press to open a fold sliding shut shut it (B838).
function foldOpen(el){
  return el.dataset.slideTo && el.getAnimations().some(a => a.id === "fold" && a.playState === "running")
    ? el.dataset.slideTo === "1" : el.open;
}

// A plain block that is shown and hidden. Same tween, collapsed height zero.
// One arrival for every box that opens under a row: the send box, a reword,
// a delete confirm, the bug tracker's two. They unroll from nothing on the
// same height tween the folds use, so the lines below ride down instead of
// jumping out of the way. Height rather than opacity, because those lines
// have to move either way and moving them smoothly is the whole point.
function arriveBox(el){
  proselines(el);
  if (noMotion() || !el) return;
  foldHeight(el, 0, el.offsetHeight, () => {});
}

// ...and a row that goes leaves the way a box arrives, backwards: it fades as
// its height folds to nothing, the rows under it riding up rather than
// jumping (the operator, 22 Nov: a dismissed row just disappeared). `done`
// runs once it has gone, where the page then draws without it; a newer
// draw meanwhile may take it first, which is the same end. Canceled (a
// refusal putting the row back), it is whole again at once.
function leaveBox(el, done){
  if (!el || noMotion()){ done?.(); return; }
  el.getAnimations().forEach(a => { if (a.id === "leave" || a.id === "fold") a.cancel(); });
  const cs = getComputedStyle(el), px = v => parseFloat(v) || 0;
  const was = {height: el.offsetHeight + "px", opacity: 1, paddingTop: cs.paddingTop, paddingBottom: cs.paddingBottom,
               marginTop: cs.marginTop, marginBottom: cs.marginBottom};
  el.style.overflow = "hidden";
  const anim = el.animate([was, {height: "0px", opacity: 0, paddingTop: "0px", paddingBottom: "0px",
                                 marginTop: px(cs.marginTop) < 0 ? cs.marginTop : "0px", marginBottom: "0px"}],
                          {duration: 180, easing: "ease", fill: "forwards"});
  anim.id = "leave";
  // Held at nothing until the page has drawn without it, then let go: an
  // element a patched draw kept for another row must not stay folded.
  anim.onfinish = () => { done?.(); anim.cancel(); };
  anim.oncancel = () => { el.style.overflow = ""; };
}

// A box whose CONTENTS are replaced: the memory writer and the bug reporter,
// each a one-line link that becomes a form and goes back to a link. Not
// arriveBox: that unrolls from nothing, and these start at the height of the
// link they are replacing, so the tween runs between the two real sizes the
// same way every other fold here does. Paint first, measure after: the form
// has no height until it is in the document.
function swapBox(el, paint){
  if (!el){ paint(); return; }
  if (noMotion()){ paint(); return; }
  // Where it is NOW, which mid-tween is a pinned px height rather than the
  // natural one: measured before the cancel below, exactly as the card fold
  // does it. Reopening a box while it was still rolling up otherwise measured
  // that pinned height twice, read from === to, and swapped with no motion at
  // all: the second click in a row was the one that looked broken.
  const from = el.offsetHeight;
  el.getAnimations().forEach(a => { if (a.id === "fold") a.cancel(); });
  paint();
  const to = el.offsetHeight;
  if (from === to) return;
  foldHeight(el, from, to, () => {});
}

// What a press just redrew in place (a chip narrowing a list, Cards or a
// List, a group picked) fades in as a rail page does: the in-half of the
// fade through, on the parts that changed (the operator, 17 Oct). Only for
// a press: a redraw the poll makes is not a change of page and never fades.
function fadeIn(els){
  if (noMotion()) return;
  for (const el of (els instanceof Element ? [els] : [...(els || [])])){
    el.getAnimations().forEach(a => { if (a.id === "fadein") a.cancel(); });
    // docIn's frames and timing, so a part arrives as a rail page does.
    el.animate([{opacity: 0}, {opacity: 1}], {duration: 220, delay: 60, fill: "backwards",
                                                easing: "cubic-bezier(.33,1,.68,1)", id: "fadein"});
  }
}

// ...and the out-half (the operator, 18 Oct: a section, a person, a chip
// and a view switched with a cut where the rail fades through). What is on
// show is copied before the press redraws it; the copy goes back where it
// stood, in the parent the redraw left (or drew again) there, so the page's
// rules still dress it, and fades out on docOut's .09s while the new part
// fades in. The copy is inert, has no ids and wears .fghost, which every
// reader of the parts skips, and is the page's own (data-own), which a
// patch landing while it fades steps over: matched by the key it was
// copied with, it would be taken for the part it copies (R244).
function ghostOf(el){
  if (!el || !el.offsetParent) return null;
  return { g: el.cloneNode(true), r: el.getBoundingClientRect(), home: el.parentNode };
}
function ghostOut(w, home){
  if (!w) return;
  const at = home?.isConnected ? home : w.home?.isConnected ? w.home : null;
  if (!at) return;
  const g = w.g;
  g.classList.add("fghost");
  g.removeAttribute("id");
  g.querySelectorAll("[id]").forEach(e => e.removeAttribute("id"));
  g.inert = true;
  g.setAttribute("aria-hidden", "true");
  g.setAttribute("data-own", "");
  Object.assign(g.style, { position: "absolute", left: "0", top: "0", margin: "0", boxSizing: "border-box",
                           width: `${w.r.width}px`, height: `${w.r.height}px`, pointerEvents: "none", zIndex: "1" });
  at.appendChild(g);
  const r = g.getBoundingClientRect();
  g.style.left = `${(w.r.left - r.left).toFixed(1)}px`;
  g.style.top = `${(w.r.top - r.top).toFixed(1)}px`;
  const gone = () => g.remove();
  g.animate([{opacity: 1}, {opacity: 0}], {duration: 90, easing: "ease-in", fill: "forwards"}).finished.then(gone, gone);
  setTimeout(gone, 400);
}
// A press's redraw as a fade through: `pick` names the parts that change
// (a selector, or a function giving them), `swap` redraws them.
function fadeThrough(pick, swap){
  const parts = () => [...(typeof pick === "function" ? pick() : document.querySelectorAll(pick))]
    .filter(e => !e.classList.contains("fghost") && e.offsetParent);
  if (noMotion()) return swap();
  const was = parts().map(ghostOf);
  swap();
  const now = parts();
  was.forEach((w, i) => ghostOut(w, (now[i] || now[0])?.parentNode));
  fadeIn(now);
}

// A chip's press as a move (R192, the operator, 31 Oct): what the list holds
// on both sides of the press slides from where it stood to where it stands
// now, what the chip leaves out fades away where it was, and what it brings
// in fades up in its place, so the eye follows the list rather than finding
// it again. `scope` gives the box the list lives in (it outlives the redraw,
// and a leaving copy is laid in it so the page's rules still dress it),
// `items` the selector of what moves, each known by moveKey; `swap` is the
// redraw. Only what is on screen on either side moves: a list of a hundred
// rows animates the ones a person can see.
function moveKey(el){
  // A group's heading is its group's (the Library's kinds).
  const g = el.parentNode?.dataset?.libgroup;
  if (g && el.matches(".libgname")) return `g:${g}`;
  for (const a of el.attributes)
    if (a.name.startsWith("data-") && a.value && !/^data-(state|kind|held|tail|skel|tiles)$/.test(a.name)) return `${a.name}=${a.value}`;
  return (el.querySelector(".name, summary, code")?.textContent || el.textContent || "").trim().slice(0, 80);
}
function onScreen(r){
  return r.width && r.bottom > -40 && r.top < innerHeight + 40;
}
function chipMove(scope, items, swap){
  const MOVE_EASE = "cubic-bezier(.2,.8,.2,1)";
  const list = () => [...(scope()?.querySelectorAll(items) || [])].filter(e => !e.classList.contains("fghost") && e.offsetParent);
  if (noMotion()) return swap();
  const before = new Map();
  for (const el of list()){
    const k = moveKey(el), r = el.getBoundingClientRect();
    if (k && !before.has(k)) before.set(k, {el, r});
  }
  const out = swap();
  const host = scope();
  // The list is not a page arriving: paint's fade on what it redrew went
  // under the move, the whole list blinking while its cards slid.
  if (host){
    host.classList.remove("justpainted");
    host.querySelectorAll(".justpainted").forEach(e => e.classList.remove("justpainted"));
  }
  const kept = new Set();
  let late = 0;
  // Every place read before anything is started or added, so the page is
  // laid out once (a read after each write laid out a big page per card,
  // and the screen stood still while it did).
  const now = list().map(el => [el, moveKey(el), el.getBoundingClientRect()]);
  for (const [el, k, r] of now){
    const was = before.get(k);
    if (was && !kept.has(k)){
      kept.add(k);
      const dx = was.r.left - r.left, dy = was.r.top - r.top;
      if ((dx || dy) && (onScreen(was.r) || onScreen(r)))
        el.animate([{transform: `translate(${dx}px,${dy}px)`}, {transform: "none"}], {duration: 320, easing: MOVE_EASE});
    } else if (onScreen(r)){
      // Arriving one after another, a beat apart, as a store's shelf fills.
      el.animate([{opacity: 0, transform: "scale(.96)"}, {opacity: 1, transform: "none"}],
                 {duration: 240, delay: 110 + Math.min(late++, 8) * 18, fill: "backwards", easing: MOVE_EASE});
    }
  }
  const ghosts = [];
  if (host) for (const [k, was] of before){
    if (kept.has(k) || !onScreen(was.r)) continue;
    const g = was.el.cloneNode(true);
    g.classList.add("fghost");
    g.removeAttribute("id");
    g.querySelectorAll("[id]").forEach(e => e.removeAttribute("id"));
    g.inert = true;
    g.setAttribute("aria-hidden", "true");
    g.setAttribute("data-own", "");
    Object.assign(g.style, {position: "absolute", left: "0", top: "0", margin: "0", boxSizing: "border-box",
                            width: `${was.r.width}px`, height: `${was.r.height}px`, pointerEvents: "none", zIndex: "1"});
    ghosts.push([g, was]);
  }
  // All laid in, then all measured, then all put in place: one layout.
  ghosts.forEach(([g]) => host.appendChild(g));
  const at = ghosts.map(([g]) => g.getBoundingClientRect());
  ghosts.forEach(([g, was], n) => {
    g.style.left = `${(was.r.left - at[n].left).toFixed(1)}px`;
    g.style.top = `${(was.r.top - at[n].top).toFixed(1)}px`;
    const gone = () => g.remove();
    g.animate([{opacity: 1, transform: "none"}, {opacity: 0, transform: "scale(.96)"}],
              {duration: 180, easing: "ease-in", fill: "forwards"}).finished.then(gone, gone);
    setTimeout(gone, 600);
  });
  return out;
}

// A change inside a project's card fades in what it brings to the face on
// show (the operator, 26 Oct: a box opening on the card appeared with a cut):
// the box opened, or the repositories coming back as it shuts. Only those,
// never the face through a copy of it: the copy went out before the face
// came in, and the card's own ground showed between them, a flicker. `el`
// is anything in the card, `swap` the change. Elsewhere it is the change
// alone.
function faceFade(el, swap){
  const face = el?.closest?.(".pcface");
  if (!face) return swap();
  const shown = () => [...face.children].filter(e => e.offsetParent && !e.classList.contains("fghost"));
  const was = new Set(shown());
  swap();
  if (face.isConnected) fadeIn(shown().filter(e => !was.has(e)));
}

// The marker on the item on show slides to the one pressed (the operator,
// 17 Oct): the line under a sub-nav's tab and a notebook strip's, the bar
// beside the rail's group. One element per strip, put back when a draw
// replaced the strip's contents, moved from where it last stood (kept by
// `key`, so a group's sub-nav never slides from another group's) to the
// item now on. The strip wears .slides, which puts its own static line away.
const SLIDE_MARKS = {};
function slideMark(box, key, vertical = false){
  if (!box) return;
  const on = [...box.children].find(e => e.classList.contains("on") && !e.hidden && e.offsetWidth);
  // The same element back when a repaint took it (the rail is painted two
  // or three times on one press), so a slide already under way goes on.
  let m = box.querySelector(":scope > .slmark") || SLIDE_MARKS[key]?.el;
  if (!on){ m?.remove(); if (box.classList.contains("slides")) box.classList.remove("slides"); return; }
  if (!m){ m = document.createElement("span"); m.className = "slmark"; m.setAttribute("aria-hidden", "true"); m.setAttribute("data-own", ""); }
  if (m.parentNode !== box) box.append(m);
  // Written only when it changes: a draw that moves nothing writes nothing.
  if (!box.classList.contains("slides")) box.classList.add("slides");
  const at = vertical ? on.offsetTop + 8 : on.offsetLeft;
  const size = vertical ? Math.max(0, on.offsetHeight - 16) : on.offsetWidth;
  const dim = vertical ? "height" : "width";
  const move = n => vertical ? `translateY(${n}px)` : `translateX(${n}px)`;
  if (m.style.transform !== move(at)) m.style.transform = move(at);
  if (m.style[dim] !== `${size}px`) m.style[dim] = `${size}px`;
  const was = SLIDE_MARKS[key];
  SLIDE_MARKS[key] = {at, size, el: m};
  // Transform alone, so the compositor runs it (the operator, 18 Oct: the
  // notebook's line stuttered): the marker takes its new size at once and
  // its old size is a scale that eases to 1, rather than a width animated
  // on the main thread, which the view drawn on the same press held up.
  const scale = n => vertical ? `scaleY(${n})` : `scaleX(${n})`;
  if (was && (was.at !== at || was.size !== size) && size > 0 && !noMotion())
    m.animate([{transform: `${move(was.at)} ${scale(was.size / size)}`}, {transform: `${move(at)} ${scale(1)}`}],
              {duration: 260, easing: "cubic-bezier(.33,1,.68,1)"});
}

function slideHidden(el, willShow, after){
  const done = () => { el.hidden = !willShow; after?.(); };
  if (noMotion()){ done(); return; }
  el.hidden = false;
  const full = el.offsetHeight;
  foldHeight(el, willShow ? 0 : full, willShow ? full : 0,
             () => { el.hidden = !willShow; after?.(); });
}


// ---- a press that is taken -------------------------------------------------
// A press's own work holds its button until it is done, and a button still
// waiting after a moment wears the ring (the operator, 8 Nov: buttons that
// answered nothing for a while read as missed). Its work is what the press
// asked for, never what happened to start near it: a request sent while a
// click is being handled (postJSON, getJSON) asks for the clicked button's
// ring, and a click handler set on an element (every press's, since R244
// sets them as properties) holds it through the promise it returns, the
// questions it asks on the way included. A poll that starts just after a
// click on a slow link is the page's own and holds nothing.
//
// One mechanism for the three ways a press says it is taken: pressHold is
// the ring, pressing() is a press that is also kept from being pressed again
// while it runs, and busy() puts a word in the button's place, which the
// ring stands down for.
const PRESS_SHOW_MS = 200;
// ...unless the ring has no room (the operator, 13 Nov: where the wheel would
// disrupt a small space, like the rail's icons, none pops up). A strip of
// presses packed side by side, or one over another, is that by its shape: a
// group on the rail or the phone's bar grew a third line and pushed every
// group under it, a page of a sub-nav widened and slid its neighbors. There
// the page arriving is the answer. Anywhere else the ring is tried and
// taken back off if it made its button taller, or its row taller or wider
// than its box: a row of buttons that just fits a phone.
const PRESS_TIGHT = ".rail, .railbar, .railmore, .pseg, .nbtabs, .dockline, .chip, .lfilter, header";
function pressRing(b){
  if (b.closest(PRESS_TIGHT)) return false;
  const row = b.parentElement;
  const was = {w: b.offsetWidth, h: b.offsetHeight, rh: row ? row.offsetHeight : 0, over: row ? Math.max(0, row.scrollWidth - row.clientWidth) : 0};
  // The ring sits in the word's place, centered in the button: a button the
  // page has not positioned becomes its frame for as long as it wears it.
  if (getComputedStyle(b).position === "static") b.classList.add("ringrel");
  b.classList.add("working");
  // Never bigger: not wider, not taller, and its row not pushed (the
  // operator, 22 Nov); a button the ring would grow wears none.
  if (b.offsetWidth <= was.w && b.offsetHeight <= was.h
      && (!row || (row.offsetHeight <= was.rh && row.scrollWidth - row.clientWidth <= was.over))) return true;
  b.classList.remove("working", "ringrel");
  return false;
}
// The button a click is a press of: the button or a.btn it landed on. Not
// one that opens a panel (the bell, the doctor, the gear), which has
// answered when the panel shows, and not a question's answer, whose asker's
// press goes on holding its own button.
function pressOf(e, within){
  const b = e?.target?.closest?.("button, a.btn");
  if (!b || (within && !within.contains(b))) return null;
  if (b.hasAttribute("aria-haspopup") || b.closest(".askdlg")) return null;
  return b;
}
// The ring waits while something else has the person's attention: a word
// busy() put in the button's place, or a dialog the button is not in (a
// question the press asked, which is answered before anything is sent).
function pressQuiet(b){
  if (b.getAttribute("aria-busy") === "true" && !b.dataset.pressWorking) return true;
  for (const m of document.querySelectorAll(".modal:not([hidden]):not(.inline)")) if (!m.contains(b)) return true;
  return false;
}
// A pick shows on the click (the operator, 22 Nov: a press must never look
// as if nothing happened): a chip in its band, or a segment of a segmented
// control, wears `on` before its handler's work, and its siblings let go.
// One already on is left as it is, for a handler that lets it go itself.
// The draw that follows says the same, or puts it right.
function pressPick(b){
  const band = b?.classList?.contains("chip") ? b.parentElement : b?.parentElement?.closest?.(".pseg");
  if (!band || b.classList.contains("on") || b.disabled) return;
  const sibs = b.classList.contains("chip") ? band.querySelectorAll(":scope > .chip") : band.querySelectorAll("button");
  for (const s of sibs){
    const me = s === b;
    s.classList.toggle("on", me);
    if (s.hasAttribute("aria-pressed")) s.setAttribute("aria-pressed", String(me));
  }
}
// ...and a chip whose press waits (a narrowing the server reads) turns its
// count into the ring, where the count already has room: no ring grows a
// chip (pressRing), and a count is never taller than its chip.
function pressCount(b){
  const pill = b?.classList?.contains("chip") ? b.querySelector(":scope > .pill") : null;
  if (!pill) return false;
  if (!pill.classList.contains("counting")){
    pill.style.minWidth = pill.offsetWidth + "px";
    pill.classList.add("counting");
  }
  return true;
}
function pressCountDone(b){
  const pill = b?.querySelector?.(":scope > .pill.counting");
  if (!pill) return;
  pill.classList.remove("counting");
  pill.style.minWidth = "";
}
function pressHold(b, p){
  if (!b) return;
  b.__pending = (b.__pending || 0) + 1;
  // A chip's count is the ring at once: the list under it is its
  // placeholder at the same moment, so the two say it together.
  if (pressCount(b)){
    const done = () => { b.__pending -= 1; if (b.__pending <= 0){ b.__pending = 0; pressCountDone(b); } };
    Promise.resolve(p).then(done, done);
    return;
  }
  const t = setInterval(() => {
    if (!b.__pending || !b.isConnected || b.dataset.pressWorking || b.__noRing) return;
    if (pressQuiet(b)) return;
    if (pressRing(b)){ b.dataset.pressWorking = "1"; b.setAttribute("aria-busy", "true"); }
    else b.__noRing = true;
  }, PRESS_SHOW_MS);
  const done = () => {
    clearInterval(t);
    b.__pending -= 1;
    if (b.__pending > 0) return;
    delete b.__noRing;
    if (b.dataset.pressWorking){ b.classList.remove("working", "ringrel"); b.removeAttribute("aria-busy"); delete b.dataset.pressWorking; }
  };
  Promise.resolve(p).then(done, done);
}
// A request asks for the ring of the press it was sent from: the button
// whose handler is running, or the one the click being handled landed on
// (window.event is that click while its listeners and what they await at
// once run, and nothing after).
let pressNow = null;
function pressTie(p){
  const ev = window.event;
  const b = pressNow || (ev?.type === "click" ? pressOf(ev) : null);
  if (b?.isConnected) pressHold(b, p);
  return p;
}
// Every click handler set as a property runs as its press: requests it sends
// at once ask for its button's ring, and the promise it returns holds it.
// The handler read back is the one set, so a draw comparing it sees its own.
function pressHook(){
  const d = Object.getOwnPropertyDescriptor(HTMLElement.prototype, "onclick");
  if (!d?.set || HTMLElement.prototype.__pressHooked) return;
  const own = new WeakMap();
  Object.defineProperty(HTMLElement.prototype, "onclick", {
    configurable: true, enumerable: d.enumerable,
    get(){ return own.has(this) ? own.get(this) : d.get.call(this); },
    set(fn){
      if (typeof fn !== "function"){ own.delete(this); d.set.call(this, fn); return; }
      own.set(this, fn);
      d.set.call(this, function(e){ return pressRun(this, e, fn); });
    }});
  Object.defineProperty(HTMLElement.prototype, "__pressHooked", {value: true});
}
function pressRun(el, e, fn){
  const b = pressOf(e, el), was = pressNow;
  if (b) pressNow = b;
  if (b) pressPick(b);
  let out;
  try{ out = fn.call(el, e); }finally{ pressNow = was; }
  if (b && out && typeof out.then === "function") pressHold(b, out);
  return out;
}
// A press kept from being pressed again until it has done. Disabled at once:
// for the second or two of a round trip the control looked as it did before
// the click, and a second press queued a second job or met a refusal of
// "one at a time". The ring after a moment where it has room, and given back as
// its markup has it at the end (pressBack): a surface the page patches
// (R244) keeps the button the press began on, which a redraw during the
// press may have drawn disabled, or made another button in its place. Put
// an `await askYes()` BEFORE the call, so canceling leaves the button alive.
async function pressing(btn, fn){
  if (!btn || btn.disabled) return undefined;
  btn.disabled = true;
  const p = (async () => fn())();
  pressHold(btn, p);
  try{ return await p; }
  finally{ pressBack(btn); }
}

// A press that says in a word what it set going (the progress rule: a word
// and an animated ellipsis, never a bar of the page's own guessing), dead
// while it runs; the ring stands down for it.
function busy(btn, word){
  if (!btn) return;
  btn.disabled = true;
  btn.setAttribute("aria-busy", "true");
  drawHTML(btn, `${esc(word)}<span class="dots"></span>`);
  // The one ticker every .dots on the page shares; it stops itself when
  // the last one is repainted away.
  if (!tcDotsTimer) tcDotsTimer = setInterval(tcTickDots, 400);
}

// ...and the other half, for a press that can fail without a repaint behind
// it. Most busy() calls need none: the round trip redraws the surface and
// the button with it, but the notebook's Send and Save both stay on screen
// when the server says no, and a button left wearing "Sending…" over a
// refusal is the worst of both.
function unbusy(btn, word){
  if (!btn) return;
  btn.removeAttribute("aria-busy");
  // A button a patched surface drew (R244) is given back as its markup has
  // it now: the redraw the press brought may have drawn it with another
  // label (a branch switched to) or disabled, and the word kept from before
  // the press would undo that.
  if (btn.__markupHtml !== undefined){
    if (btn.innerHTML !== btn.__markupHtml){ btn.innerHTML = btn.__markupHtml; for (const c of btn.children) patchRecord(c); drawn(btn); }
    pressBack(btn);
    return;
  }
  btn.disabled = false;
  btn.textContent = word;
}

// The word a press wears for its verb, where a page's buttons carry the verb
// as data (data-vm="stop", data-starray="sync"): one table for every page, so
// a verb is worded once. A verb the table has not got says Working.
const BUSY_WORDS = {
  start: "Starting", stop: "Stopping", restart: "Restarting", remove: "Removing", rename: "Renaming",
  set: "Saving", snapshot: "Saving", paths: "Saving", turns: "Saving", take: "Taking",
  revert: "Reverting", "snapshot-rm": "Deleting", eject: "Ejecting", "disk-grow": "Growing", "disk-add": "Adding",
  sync: "Syncing", scrub: "Scrubbing", check: "Checking", verify: "Checking", mover: "Moving", "to-sync": "Moving",
  on: "Mounting", off: "Unmounting", init: "Creating", clone: "Starting", link: "Starting",
  "update-agent": "Updating", test: "Asking", drain: "Draining", online: "Undraining", "cache-clear": "Clearing",
  retire: "Removing", discard: "Discarding", uninstall: "Uninstalling", lockdown: "Locking down",
  reboot: "Rebooting", poweroff: "Shutting down", "gpu-apply": "Applying",
  "sync-stop": "Stopping", "sync-resume": "Resuming", "sync-clean": "Cleaning",
};
// busy() by the verb. `extra` is the page's own words, looked at first: for a
// verb whose word depends on the press, or that means something else there.
function busyFor(btn, verb, extra = {}){
  busy(btn, extra[verb] ?? BUSY_WORDS[verb] ?? "Working");
}
