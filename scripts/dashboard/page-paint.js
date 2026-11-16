// patch(): a surface's new markup brought into what is there, the one way
// every list on this page is drawn again; and newShell(), a terminal opened
// in the dock. What was the tab strip around them (its drag, its picker, its
// arrows and pin menu) went with R218 step 4: terminals are the dock's line
// (page-dock.js) and every other tab is a page on the rail.
//
// One classic script beside index.html (docs/design-language.md, Files):
// pure declarations, nothing runs at load.

"use strict";

// What each surface was last drawn with, by the markup it was given. The
// poll is every fifteen seconds and nearly always says the same thing;
// writing identical markup anyway dropped :hover under a resting pointer,
// reset a link mid-"updating…", and made every card blink for nothing.
// Markup is compared as a string (cheap, since it was just built) and only
// a difference touches the DOM.
const painted = new WeakMap();

// The same rule for the frame's small writes (R218 step 10): a text, an
// attribute, a whole class list or a hidden flag set only when it differs.
// Written unconditionally, each status poll rewrote the header's words, the
// doctor's dot, the dock's and the panes' classes and the phone bar's flags
// with what they already said, two hundred changes a poll that were none.
function setText(el, s){ if (el && el.textContent !== String(s)) el.textContent = String(s); }
function setAttr(el, name, v){
  if (!el) return;
  if (v === null || v === undefined || v === false){ if (el.hasAttribute(name)) el.removeAttribute(name); }
  else if (el.getAttribute(name) !== String(v)) el.setAttribute(name, String(v));
}
function setClass(el, cls){ if (el && el.className !== cls) el.className = cls; }
function setHidden(el, off){ if (el && el.hidden !== !!off) el.hidden = !!off; }
function setDisabled(el, off){ if (el && el.disabled !== !!off) el.disabled = !!off; }
// A title is taken off by untitle() and kept for a screen reader as the
// element's description or name, so it is compared against what was kept.
function setTitle(el, s){ if (el && saidOf(el) !== String(s)) el.title = String(s); }
// The FIRST real content fades in: nothing drawn here yet, or what was here
// a placeholder saying it had not arrived. First only, deliberately: fading
// on every change would flicker a list every time a poll moved one word in
// it, which is worse than not animating at all.
const WAITING = /class="(loading|empty)[ "]|loading…/;
// What a draw wrote into a surface, as its record knows it: its children
// but the page's own (patchOwn: a slide marker, a section's jump bar put
// before its first section), which the page's code puts in beside them and
// which make the markup no staler. Counted with them, the Git view's jump
// bar at the top of its list read as another writer's every time, and the
// list was written whole, a commit message being typed with it (R244).
const paintedKids = el => { let n = 0;
  for (const c of el.childNodes) if (!patchOwn(c)) n++;
  return n; };
const paintedFirst = el => { let c = el.firstChild;
  while (patchOwn(c)) c = c.nextSibling;
  return c; };

// The new markup patched into what is there rather than written over it
// (R244): every element the new markup can be matched to is kept and brought
// up to date, so a redraw from the poll leaves a person's typing, its caret
// and an open IME composition, a fold they turned, a menu and a dialog they
// have open where they were. Measured on the Containers and Nodes pages
// before it was chosen (R244 step 1): replacing lost all of those, lifting a
// form region out and back still ended the composition and shut the folds,
// and this kept every one for about twice replace's time, four milliseconds
// at today's sizes, paid only when the markup changed. Returns whether it
// wrote anything, for the callers that wire or animate only on a change.
// `quiet` is the frame's own (the rail, a page's bar and foot): chrome is
// there, it does not arrive.
function patch(el, html, quiet = false){
  const rec = painted.get(el);
  // What it left there is what is there: a renderer that wrote the element
  // directly in between (a "loading…", an error) replaced its children, and
  // the same markup drawn again is then a change, written whole, since there
  // is nothing of the last draw's to keep. A fold opened or a box ticked
  // since replaces nothing and still reads as unchanged.
  const was = rec && rec.first === paintedFirst(el) && rec.n === paintedKids(el) ? rec.html : undefined;
  // ...unless a button in it was marked busy since (busy(): "Asking..."):
  // the press rewrote it in place, and the same markup drawn again is what
  // takes the mark off. Skipped, Measure now said Asking until a reload (the
  // operator, 23 Oct). A mark the markup carries itself (Abort's Stopping)
  // is not a press's.
  if (rec && was === html && (html.includes('aria-busy="true"') || !el.querySelector('[aria-busy="true"]'))) return false;
  const arriving = !rec || WAITING.test(rec.html);
  if (was !== undefined) patchInto(el, html);
  else {
    el.innerHTML = html;
    // What the markup gave each element, for the first patch after it.
    for (const c of el.children) patchRecord(c);
  }
  painted.set(el, {html, first: paintedFirst(el), n: paintedKids(el)});
  // ...but never fading while the card around it is folding. contentIn
  // starts at opacity 0 and takes 180ms, which is exactly the fold's
  // duration, so a draw landing on a collapsing card blanked its body at
  // full height and faded it back in as the card shut. Suppressed rather
  // than delayed: content arriving into something on its way shut has
  // nowhere to arrive, and the fold is the motion that matters.
  const folding = el.closest(".card")?.getAnimations().length > 0;
  if (arriving && !quiet && !folding && !WAITING.test(html) && !noMotion()){
    // Restarted rather than added-once: an element can arrive more than once
    // in a session, and a class already on it would not replay.
    el.classList.remove("justpainted");
    void el.offsetWidth;
    el.classList.add("justpainted");
  }
  return true;
}

// ---- the patch ----
// Each element keeps the attributes its markup gave it (__markup), recorded
// as it is written and before anything else on the page has touched it. A
// patch then changes only what the markup changed between the two: what the
// page puts on an element itself (a password manager's ignore marks, a title
// moved to aria-description) and what the person changed (a fold turned, a
// dialog opened, a value typed, a box ticked) are neither of the markups'
// and are left as they are. data-own says what is code's: on an element the
// markup draws, its children (a fold read when it is opened), and on one the
// code puts in, the element itself (patchOwn).
const PATCH_PRESS = ["disabled", "aria-busy"];
// ...never its style attribute, which no markup writes (the content policy
// draws none: data-style is the markup's, applied through the CSSOM). Read
// off an element the markup never recorded (a part a press drew by its own
// hand), it was taken for the markup's and removed, the block's place and
// color with it, while its data-style said nothing had changed.
function patchAttrs(n){ const o = {}; for (const at of n.attributes) if (at.name !== "style") o[at.name] = at.value; return o; }
function patchRecord(root){
  if (root.nodeType !== 1) return;
  root.__markup = patchAttrs(root);
  if (root.tagName === "BUTTON") root.__markupHtml = root.innerHTML;
  for (const e of root.querySelectorAll("*")){
    e.__markup = patchAttrs(e);
    // ...and a button's label, which a press gives back (unbusy) as the
    // markup has it then rather than as it was when the press began.
    if (e.tagName === "BUTTON") e.__markupHtml = e.innerHTML;
  }
}
function patchWas(n){ return n.__markup || patchAttrs(n); }
// What one element is called among its siblings: a row's data-key, which a
// list's rows carry so that one moved, added or taken away takes nothing of
// its neighbors' with it, else its id. "" is no name: matched by place.
function patchKey(n){
  if (n.nodeType !== 1) return "";
  // An option is its value: a pulldown whose list changed under a redraw
  // keeps the option the person picked, rather than its place being
  // rewritten into another value still picked (seen on nginx's host).
  if (n.tagName === "OPTION") return "opt:" + (n.getAttribute("value") ?? n.textContent);
  return n.getAttribute("data-key") || n.id || "";
}
// Whether `a` can be brought up to `b` rather than replaced: the same kind of
// node, the same tag, and for a form control or a button the same type, name
// and data-* (which field it edits, data-k="rootasks"; which action it is,
// data-nd="sync-clean"), so what a person typed is never handed to another
// field, and a press that still holds its button never writes to another.
function patchSame(a, b){
  if (a.nodeType !== b.nodeType) return false;
  if (a.nodeType !== 1) return true;
  if (a.tagName !== b.tagName || patchKey(a) !== patchKey(b)) return false;
  // One whose children are its code's is only ever itself: matched to
  // another element in its place, it would keep that one's old children.
  if (("data-own" in patchWas(a)) !== b.hasAttribute("data-own")) return false;
  if (a.tagName === "INPUT" || a.tagName === "SELECT" || a.tagName === "TEXTAREA" || a.tagName === "BUTTON")
    return patchFieldOf(patchWas(a)) === patchFieldOf(patchAttrs(b));
  return true;
}
function patchFieldOf(attrs){
  let s = (attrs.type || "") + "|" + (attrs.name || "") + "|";
  for (const name of Object.keys(attrs).sort()) if (name.startsWith("data-")) s += name + "=" + attrs[name] + ";";
  return s;
}
// What a person changes in a form control is a property its markup only
// starts: it follows the markup when the markup changed it (a Revert, a
// draft drawn, the server's new value), never when the markup says what it
// said before. Set only when it differs, so a caret is not moved for nothing.
function patchControl(a, was, now){
  if (a.tagName === "INPUT"){
    const t = (now.type || "text").toLowerCase();
    if (t === "checkbox" || t === "radio"){
      const want = "checked" in now;
      if (want !== ("checked" in was) && a.checked !== want) a.checked = want;
    } else if (t !== "file"){
      const want = now.value ?? "";
      if (want !== (was.value ?? "") && a.value !== want) a.value = want;
    }
  } else if (a.tagName === "OPTION"){
    const want = "selected" in now;
    if (want !== ("selected" in was) && a.selected !== want) a.selected = want;
  }
}
function patchNode(a, b){
  if (a.nodeType !== 1){ if (a.nodeValue !== b.nodeValue) a.nodeValue = b.nodeValue; return; }
  const was = patchWas(a), now = patchAttrs(b);
  patchControl(a, was, now);
  for (const name in was) if (!(name in now) && a.hasAttribute(name)) a.removeAttribute(name);
  for (const name in now){
    if (was[name] === now[name] || a.getAttribute(name) === now[name]) continue;
    // A class the page's code added (a fold's current one, a split list's
    // open one) outlives the markup changing its own: the markup's tokens
    // come and go, the others stay.
    if (name === "class" && was.class !== undefined){
      const gone = was.class.split(/\s+/).filter(Boolean), come = now.class.split(/\s+/).filter(Boolean);
      for (const t of gone) if (!come.includes(t)) a.classList.remove(t);
      for (const t of come) a.classList.add(t);
    } else {
      a.setAttribute(name, now[name]);
      // A style is written as data-style (the page's content policy draws
      // no style attribute) and applied through the CSSOM as an element
      // lands (index.html); one that stays and changes is applied here.
      if (name === "data-style") a.style.cssText = now[name];
    }
  }
  if ("data-style" in was && !("data-style" in now)) a.style.cssText = "";
  // A press's own state is the markup's again at the next draw, as it was
  // when a draw wrote everything: a button a press disabled or marked busy
  // (busy(): "Asking..." and its dots) is given back by the redraw after it.
  for (const name of PATCH_PRESS){
    const want = now[name];
    if (want === undefined){ if (a.hasAttribute(name)) a.removeAttribute(name); }
    else if (a.getAttribute(name) !== want) a.setAttribute(name, want);
  }
  a.__markup = now;
  if (a.tagName === "BUTTON"){
    if (a.innerHTML !== b.innerHTML){ a.innerHTML = b.innerHTML; for (const c of a.children) patchRecord(c); }
    a.__markupHtml = b.innerHTML;
  } else if (a.tagName === "TEXTAREA"){
    // Its text is its default value: a person's typing is its value, which
    // follows the markup's text only when that changed.
    const want = b.textContent;
    if (want !== a.defaultValue){ a.defaultValue = want; if (a.value !== want) a.value = want; }
  } else if (!("data-own" in now)) patchKids(a, b);
}
// The new children into `from` in order: a named one is found wherever it
// is among the old and moved into place; an unnamed one is matched to the
// old one in its place when it is the same kind; anything else is the new
// node itself, moved in from the new markup. What is left of the old is gone.
// An element the page's code put into a drawn surface and marked data-own
// (a split list's index row, a jump bar, a slide marker, a status filled into
// a summary) is stepped over and left where it is: its code keeps it or
// takes it away. Anything else no markup wrote (a part a press drew again by
// its own hand) follows the markup like the rest, so nothing stale stays.
function patchOwn(n){ return !!n && n.nodeType === 1 && !n.__markup && n.hasAttribute("data-own"); }
function patchKids(from, to){
  // A key two siblings share is matched in their order, the first old one to
  // the first new one, so neither is taken for the other.
  const named = new Map();
  for (const n of from.childNodes){
    const k = patchKey(n);
    if (!k || patchOwn(n)) continue;
    const id = n.tagName + "#" + k;
    if (named.has(id)) named.get(id).push(n); else named.set(id, [n]);
  }
  let cur = from.firstChild;
  for (const want of [...to.childNodes]){
    while (patchOwn(cur)) cur = cur.nextSibling;
    const k = patchKey(want);
    // One unnamed node gone from before its place is stepped over, so the
    // rest of an unnamed run is still matched rather than all remade.
    if (!k && cur && !patchKey(cur) && !patchSame(cur, want) && cur.nextSibling && !patchOwn(cur.nextSibling)
        && !patchKey(cur.nextSibling) && patchSame(cur.nextSibling, want)){
      const gone = cur; cur = cur.nextSibling; from.removeChild(gone);
    }
    const same = k ? named.get(want.tagName + "#" + k) : null;
    const old = k ? same?.[0] || null : cur && !patchKey(cur) ? cur : null;
    if (old && patchSame(old, want)){
      if (k) same.shift();
      if (old !== cur && patchHeld(old)){
        // Moving it would blur what has the focus and close an open
        // dialog, so the ones before it are moved past it instead, in
        // their order, still to be matched.
        const after = old.nextSibling;
        while (cur && cur !== old){ const next = cur.nextSibling; if (!patchOwn(cur)) from.insertBefore(cur, after); cur = next; }
      }
      if (old === cur) cur = cur.nextSibling;
      else from.insertBefore(old, cur);
      patchNode(old, want);
    } else {
      patchRecord(want);
      from.insertBefore(want, cur);
    }
  }
  while (cur){ const next = cur.nextSibling; if (!patchOwn(cur)) from.removeChild(cur); cur = next; }
}
// Whether moving `n` would lose what a person has in it: the focus, an open
// dialog (taken out of the top layer), a frame (loaded again).
function patchHeld(n){
  if (n.nodeType !== 1) return false;
  const a = document.activeElement;
  return (a && a !== document.body && n.contains(a)) || n.matches("dialog[open], iframe") || !!n.querySelector("dialog[open], iframe");
}
function patchInto(el, html){
  const t = document.createElement("template");
  t.innerHTML = html;
  patchKids(el, t.content);
}

// The next draw of the surface holding `el` writes it all again rather than
// patching it: for a form a save is done with (a secret saved is drawn as
// set, its field empty to type a replacement into), where what the person
// typed is meant to go. Said by the save, never by a poll.
function drawFresh(el){
  for (let e = el; e; e = e.parentElement) if (painted.has(e)){ painted.delete(e); return; }
}

// A press's button given back when the press ends: as its markup has it,
// where a patch keeps it (the same element, perhaps drawn disabled since, or
// another button now in its place), and enabled where nothing recorded one.
function pressBack(btn){
  if (!btn?.isConnected) return;
  const want = !!btn.__markup && "disabled" in btn.__markup;
  if (btn.disabled !== want) btn.disabled = want;
}

// What the page's code takes from a drawn surface for whoever is looking (a
// press a role does not give, a field a locked space keeps): hidden or dead,
// and marked so that a draw for somebody it does give has it back. A patch
// keeps what code did to an element its markup does not mention, so giving
// it back is the code's as well (R244): giveBack first, then takeAway what
// this look takes, on every draw.
function takeAway(el, hide = false){
  if (!el) return;
  el.setAttribute("data-taken", "");
  if (hide) el.hidden = true; else el.disabled = true;
}
// What is typed into a find box acts once a word is whole: never in the
// middle of an input method's composition, whose keys are not letters yet,
// and once at its end (R244 step 4). Set, so a draw that keeps the box may
// set it again.
function onTyping(inp, fn){
  if (!inp) return;
  inp.oninput = e => { if (!e.isComposing) fn(); };
  inp.oncompositionend = () => fn();
}
// A Revert's fields as the markup draws them. A patch keeps what is typed
// wherever the markup says what it said before, and a field typed into with
// no draw since was drawn with the saved value then and now, so a Revert
// that only drops its drafts and draws again would leave the typing there
// (R244). Called after that draw.
function fieldsBack(root){
  root?.querySelectorAll("input, select, textarea").forEach(f => {
    if (f.type === "checkbox" || f.type === "radio"){ if (f.checked !== f.defaultChecked) f.checked = f.defaultChecked; }
    else if (f.tagName === "SELECT"){ for (const o of f.options) if (o.selected !== o.defaultSelected) o.selected = o.defaultSelected; }
    else if (f.type !== "file" && f.value !== f.defaultValue) f.value = f.defaultValue;
  });
}
function giveBack(root){
  root?.querySelectorAll("[data-taken]").forEach(e => {
    e.removeAttribute("data-taken");
    pressBack(e);
    const hid = !!e.__markup && "hidden" in e.__markup;
    if (e.hidden !== hid) e.hidden = hid;
  });
}

// A terminal at some directory, always a new one. "" is the workspace root.
function newShell(proj){
  if (!mayShell()){ notify("a shell is an administrator's", true); return; }
  const arg = nextShell(proj);
  if (!arg){ notify("Too many terminals open for that directory.", true); return; }
  // A shell on a project whose node cannot take one opens on this container
  // and says so: a shell is where the node gets looked at, and a JSON error
  // in the frame was what the operator got instead of one. Only when a NODE
  // refused, which is what session_at names: a project with no node has
  // always had its shell here, and announcing that would be news about
  // nothing.
  const pr = (state?.projects || []).find(p => p.name === proj);
  const here = !!(pr?.session_why && pr?.session_at);
  if (here) notify(`${projLabel(proj)}'s node cannot take a session now; this shell is on the controller`);
  openTab({kind:"term", arg, label: `sh: ${proj ? projLabel(proj) : "workspace"}${here ? " (here)" : ""}`, here});
}
