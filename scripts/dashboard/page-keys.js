// The on-screen keys: the table a phone's hot bar draws a shell's line of
// keys from, and the band at a terminal's foot that holds it.
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

// A shell's tab, and not a coding agent's. Both are terminals, but a shell's
// keys are for driving a shell: over an agent they type into a conversation
// that has its own idea of what a keystroke means.
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
  // On a phone the band is the hot bar (the operator, 12 Nov): the keys of
  // the terminal in front, whichever kind it is, in a line that scrolls (a
  // shell's carrying the rest of the key table past its hot ones), then
  // Links. A desk's keys float over the
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
  // what is about the terminal in front, its keys and Links, on a phone,
  // and is not drawn with nothing in it. (Commands, a panel of things to
  // type into a shell, went on 12 Nov: the operator.)
  setHidden($("mobar"), !own);
}
