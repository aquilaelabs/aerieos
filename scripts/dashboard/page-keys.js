// The on-screen keys, and the phone's panels: the key bar a touch device
// types with, and the panels (keys, macros, sessions, chat) that slide up
// from the phone's own bar.
//
// One classic script beside index.html (docs/design-language.md, Files):
// pure declarations, nothing runs at load. What runs at load stays in
// index.html under the section's header.

"use strict";

// ---- keys ------------------------------------------------------------

const KEYS = [
  [["escape","Esc"],["tab","Tab"],["left","←"],["down","↓"],["up","↑"],["right","→"],
   ["home","Home"],["end","End"],["pgup","PgUp"],["pgdn","PgDn"]],
  [["ctrl-c","^C"],["ctrl-d","^D"],["ctrl-z","^Z"],["ctrl-l","^L"],["ctrl-r","^R"],
   ["ctrl-a","^A"],["ctrl-e","^E"],["ctrl-u","^U"],["ctrl-w","^W"],["enter","⏎"]],
  [["pipe","|"],["tilde","~"],["slash","/"],["backslash","\\"],["dash","-"],
   ["under","_"],["dollar","$"],["star","*"],["lt","<"],["gt",">"]],
];

// The phone's second panel. Keys and macros are exclusive there; see the
// toggles below, and the macro lists are the dashboard's own #commands and
// The lists live here at every width: one DOM, one set of handlers, and no
// breakpoint to be on the wrong side of.
let showMacros = false;

// The phone's one panel, Commands: a press opens it and the next shuts it.
// (Keys was the other, until the hot bar's line took its keys: the
// operator, 12 Nov.)
function mobPanel(which){
  if (which !== "macros") return;
  showMacros = !showMacros;
  render();
}

// Slide a bottom flyout open or shut on a phone instead of popping it.
//
// The slide happens as an OVERLAY: for its duration the panel is taken out
// of the flow and pinned above the bottom bar, growing (or shrinking) over
// the terminal, and only when it lands is it put back into the flow, so the
// terminal resizes once, in a single step, instead of the iframe reflowing
// and refitting on every frame of the tween underneath it. Opening: overlay,
// slide up, then snap the terminal shorter. Closing: overlay (the terminal
// snaps taller at once), slide down, then hide. State is tracked on the
// element, not read from the class: the class stays on while a close is
// still tweening, and every render passes through here.
//
// Returns a promise for the moment the slide lands (null when there was no
// slide). `swap` is that promise from another panel opening in the same
// render: a panel closing to make way for it does not slide down at all;
// it stays put, in the flow, under the new one growing over it, and is
// simply gone when the new one lands. Two slides at once looked like a
// collision, and closing first would have resized the terminal twice.
function slidePanel(el, show, swap){
  const was = el.dataset.shown === "1";
  setAttr(el, "data-shown", show ? "1" : "0");
  if (was === show) return null;
  // Interrupted mid-slide, the next slide starts from the height the panel
  // is at, not from one end: the second tap on a flyout reverses it.
  const running = el.getAnimations();
  const mid = running.length ? el.getBoundingClientRect().height : null;
  running.forEach(a => a.cancel());
  // Where it ends up is the difference between the two screens. On a phone it
  // lands IN the flow and the terminal gives up the height, because there is
  // not enough screen to cover one thing with another. On a desktop it never
  // lands: it stays an overlay, and the terminal keeps its size, which is
  // what a terminal wants, since a resize costs it a refit and a reflow of
  // everything on screen. The TWEEN is an overlay either way, or the iframe
  // would reflow on every frame of it.
  const overlay = !isPhone();
  if (show && overlay) el.classList.add("over");
  const pin = () => { el.style.bottom = $("mobar").offsetHeight + "px"; };
  const settle = () => {
    el.style.overflow = "";
    el.classList.remove("sliding");
    if (!overlay) el.style.bottom = "";        // an overlay stays pinned
  };
  const done = () => { if (!show) el.classList.remove("show", "over"); };
  if (noMotion()){
    if (overlay) pin();
    settle(); el.classList.toggle("show", show); done();
    return null;
  }
  // The one being replaced holds still at full height and is dropped when the
  // opener lands over it: cheaper than two tweens, and nothing shows through
  // between them. Only in the flow: two overlays would have to agree about
  // which is on top, which the z-index above already settles.
  if (!show && swap && !overlay){
    settle();                                   // full height, in the flow
    swap.then(() => { if (el.dataset.shown === "0") el.classList.remove("show"); });
    return null;
  }
  el.classList.add("show", "sliding");
  pin();                                        // pinned just above the bar
  const h = el.offsetHeight;
  el.style.overflow = "hidden";
  const anim = el.animate(show ? [{height: (mid ?? 0) + "px"}, {height: h + "px"}]
                               : [{height: (mid ?? h) + "px"}, {height: "0px"}],
                          {duration: 200, easing: "ease"});
  return new Promise(res => {
    anim.onfinish = () => {
      settle();                                 // into the flow, or staying put
      done();
      res();
    };
    // Canceled by a newer slide: whoever is waiting must not wait forever,
    // and must not act either: the newer slide owns the panel now.
    anim.oncancel = () => res();
  });
}

// A shell tab, and not a Claude one. Both are terminals, but the keys and the
// macros are for driving a shell: over Claude they type into a conversation
// that has its own idea of what a keystroke means, and over a document there
// is nothing to type into at all.
const isShellTab = t => t?.kind === "term" && !agentOfArg(t.arg);

// The terminal the phone's band is for: the one in front.
function mobHotRec(){
  const t = tabOf(panes[active]);
  return t ? [...TERMS.values()].find(r => r.t.id === t.id && r.el.isConnected) || null : null;
}
function mobLinksShut(){
  const box = $("mLinksBox");
  if (box && !box.hidden) box.hidden = true;
  // Written only when it changes: a status read that brings nothing new
  // writes nothing.
  const ml = $("mLinks");
  if (ml && ml.getAttribute("aria-expanded") !== "false") ml.setAttribute("aria-expanded", "false");
}
// A phone's line carries a shell's other keys past the hot ones, where the
// Keys panel was (the operator, 12 Nov: most of them were on the bar
// already): the rest of the table, in its order.
function mobMoreKeys(t){
  if (!isShellTab(t) || !mayShell()) return [];
  const have = new Set(termHotKeys(t).map(([k]) => k));
  return KEYS.flat().filter(([k]) => !have.has(k));
}

function drawKeys(){
  const t = tabOf(panes[active]);
  const term = isShellTab(t);
  // Commands, on a shell's tab: not there at all where there is no shell to
  // type into (B460).
  const mm = $("mMacros");
  mm.classList.toggle("on", showMacros);
  setHidden(mm, !term);
  // On a phone the band is the hot bar (the operator, 12 Nov): the keys of
  // the terminal in front, whichever kind it is, in a line that scrolls (a
  // shell's carrying the rest of the key table past its hot ones), then
  // Links, and Commands where it is a shell. A desk's keys float over the
  // terminal.
  const hot = $("mHot"), own = t?.kind === "term" && termOwn(t) && isPhone() ? t : null;
  if (paint(hot, own ? termHotButtons(own, mobMoreKeys(own)) : "")){
    hot.querySelectorAll("[data-hk]").forEach(b => b.onclick = () => { mobLinksShut(); sendKey(b.dataset.hk); });
    // A press on the band leaves the keyboard where it is.
    hot.onpointerdown = e => { if (e.target.closest("button")) e.preventDefault(); };
  }
  setHidden(hot, !own);
  // Links, always there beside the line: what the terminal in front shows,
  // listed over the band, or that it shows none.
  const ml = $("mLinks");
  setHidden(ml, !own);
  if (!own) mobLinksShut();
  ml.onpointerdown = e => e.preventDefault();
  ml.onclick = () => {
    const rec = mobHotRec(), box = $("mLinksBox");
    if (!rec || !box.hidden) return mobLinksShut();
    termLinksFill(rec, box, mobLinksShut);
    box.hidden = false;
    ml.setAttribute("aria-expanded", "true");
  };
  // Its ends, as the dock's line has them: faded, with the arrow, where
  // more keys lie past one (chipsEdge), measured once it is laid out.
  if (own) requestAnimationFrame(() => chipsEdge(hot));
  // Sessions is a page and Chat the dock's tab (R250): the foot bar keeps
  // what is about the terminal in front, its keys, Links and Commands, and
  // is not drawn with nothing in it.
  setHidden($("mobar"), mm.hidden && !own);
  // One panel at a time: whichever is opening slides, and any that is
  // closing in the same breath swaps out under it (see slidePanel).
  // Commands closes with the keys when the tab underneath is not a shell: a
  // flyout of things to type, over something that cannot be typed into.
  const want = [[$("macpanel"), showMacros && term]];
  const opener = want.find(([p, s]) => s && p.dataset.shown !== "1");
  const landed = opener ? slidePanel(opener[0], true) : null;
  for (const [p, s] of want) if (p !== opener?.[0]) slidePanel(p, s, landed);
}
