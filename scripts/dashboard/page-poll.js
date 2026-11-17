// The two polls: refresh() fetches /api/status and draws from it, the one
// source of state, and pollRevs() asks every second and a half which
// revision tokens moved, onRev() being how a view says what to fetch when
// one does.
//
// One classic script beside index.html (docs/design-language.md, Files):
// pure declarations, nothing runs at load. What runs at load is
// page-boot.js's, under the section's header.

"use strict";

// ---- the status poll ----------------------------------------------------

let bootSeen = null;                      // which run of the container this page saw
let preStatusUsed = false;                // the head's early fetch: once only

// A read the head began for the page the address names (preGets), shared
// by whoever asks for it, each with a copy of its answer: the page's loader
// at load and its open on the first draw are one read, taken beside the
// status read. Taken after that draw, it is dropped once it has landed
// (the page has opened on it; whoever asks while it is still on its way
// shares it), or five seconds after the draw when nothing took it, so
// nothing read at load is handed out after the page moved on.
let bootDrawn = false;
function bootFetch(url){
  const p = preGets[url];
  if (!p) return fetch(url);
  if (bootDrawn) p.finally(() => { if (preGets[url] === p) delete preGets[url]; });
  return p.then(r => r.clone());
}
function bootReadsDone(){
  bootDrawn = true;
  setTimeout(() => { for (const k of Object.keys(preGets)) delete preGets[k]; }, 5000);
}

// ---- what a page reads (R9 step 2) ----------------------------------------
// Every read a page or a notebook view makes for what it draws goes through
// reading(), so each has the same sequence guard: one read of a kind at a
// time, and a read asked for while one is out made once more when it lands
// (the newest ask's), never stacked beside it: a token can move several
// times a second while a job runs, and every move asked again. Each answer
// lands and is drawn in the order asked, so a page whose reads are asked for
// faster than they answer still draws each (B154). Landing moves the kind's
// revision, which a page's live key reads with readRev() in place of a
// counter of its own; readMoved() moves it for a change the page draws
// that no read brought (a pick, a draft, a fold).
const readings = new Map();
function readingOf(key){
  let r = readings.get(key);
  if (!r){ r = {rev: 0, seq: 0, busy: null, again: null, waiting: []}; readings.set(key, r); }
  return r;
}
// `join`, a number of milliseconds, lets an ask about the same thing (`about`)
// within that long of the read's start share it rather than read again: the
// Library's open, its node's census and the revisions poll each asked at
// once, and the page waited on three reads where one would do.
// Each ask is answered by its own read: the one it started, the one out when
// it joined, or, asked while one was out, the next to start, which is made
// once however many asked meanwhile. Never by the reads asked after it: a
// kind asked again before each slow read is in (the nodes on a controller
// that takes seconds, polled every few) kept every caller waiting on a chain
// that did not end, and the pages behind it on their shapes.
function reading(key, fn, {join = 0, about = ""} = {}){
  const r = readingOf(key);
  if (r.busy){
    if (join && r.about === about && Date.now() - r.at < join) return readFor(r, r.seq);
    r.again = fn; r.againAbout = about;
    return readFor(r, r.seq + 1);
  }
  r.at = Date.now(); r.about = about;
  // A read that throws still lets the one asked meanwhile be made, and its
  // failure is its own asker's, said where nobody catches it (sayUnheard).
  // A read may leave its answer unlanded when a newer ask is already
  // waiting (overtaken(): its answer is about an earlier moment, and a page
  // that builds a draft from what it reads would build it from that), but
  // never two in a row, so a page asked faster than it answers still lands
  // one answer in two (B154). It says so by returning false, and whoever it
  // was for is answered by the read after it.
  r.busy = (async () => {
    try{
      for (let f = fn; f; f = r.again){
        if (f !== fn){ r.at = Date.now(); r.about = r.againAbout; }
        r.again = null;
        const seq = ++r.seq;
        const overtaken = () => !!r.again && !r.skipped;
        let landed = true, failed = null;
        try{ landed = (await f(overtaken)) !== false; }
        catch(e){ failed = e; }
        r.skipped = !landed;
        if (landed){ r.rev++; drawPanes(); }
        readSettle(r, seq, landed, failed);
      }
    }finally{ r.busy = null; readSettle(r, Infinity, true, null); }
  })();
  return readFor(r, r.seq);
}
// The promise an ask holds: settled when read number `seq` is in.
function readFor(r, seq){
  return new Promise((res, rej) => (r.waiting || (r.waiting = [])).push({seq, res, rej}));
}
function readSettle(r, seq, landed, failed){
  r.waiting = (r.waiting || []).filter(w => {
    if (w.seq > seq) return true;
    if (!landed){ w.seq = seq + 1; return true; }     // left unlanded: the next read is its
    if (failed && w.seq === seq) w.rej(failed); else w.res();
    return false;
  });
}
const readRev = key => readings.get(key)?.rev || 0;
// Whether a read of this kind is out now (a page that says it is reading).
const readBusy = key => !!readings.get(key)?.busy;
function readMoved(key){ readingOf(key).rev++; }

// Terminal tabs whose session we have actually watched running.
//
// The transition is what closes a tab, not the absence: "no session" is also
// true of a tab restored from a saved layout before anything has started, and
// of every tab for a moment if a poll ever comes back empty. Seen-then-gone
// happens exactly once, when the thing at the other end ended.
const seenLive = new Set();

// Close a terminal tab when its session has gone.
//
// bb-tty execs claude, so the pane's process IS the conversation: exit it:
// Ctrl+C twice, /exit, Ctrl+D, or a crash, and the pane dies, the tmux
// session goes with it, and the tab was left holding a dead terminal until
// somebody pressed ✕ on it. Nothing is lost by closing it: the transcript is
// on disk and the project's Claude button offers to resume it, which is a
// better way back than a corpse in a tab, because the row knows the id.
//
// Shells too, and for the same reason: a shell you typed `exit` in is just as
// dead, and one rule for terminal tabs is simpler than a carve-out.
function reapDeadTerminals(){
  const live = liveSessions();
  const gone = [];
  for (const t of tabs){
    if (t.kind !== "term") continue;
    const s = sessionOf(t.arg);
    if (live.has(s)) seenLive.add(s);
    else if (seenLive.has(s)){ seenLive.delete(s); gone.push(t.id); }
  }
  // Collected first: dropTab re-renders and repairs the panes, and doing that
  // while walking the list it edits is how one of two dying tabs gets missed.
  gone.forEach(dropTab);
  vmConsolesChecked();
}

let refreshBusy = false;     // a poll is out
let refreshAgain = false;    // ...and somebody asked for another while it was
// ...and who is waiting on that other one: an `await refresh()` asked while a
// poll was out resolved at once, on the state from before, so a project's
// settings Save read "what is saved now" from a poll sent before somebody
// else's save and wrote over it unseen (B100). It resolves when the read
// asked for has landed.
let refreshWaiters = [];
// How many action answers applyNow has adopted: a poll sent before the last
// of them was read before that action, so its reply is older than the rows
// on screen (B294).
let adoptSeq = 0;

async function refresh(){
  // One at a time, and never dropped.
  //
  // /api/status runs git for every project, so it is seconds rather than
  // milliseconds on a cold share, and refreshSoon deliberately fires three
  // of these within four seconds while the fifteen-second poll carries on.
  // Without a guard they stack, and because each one costs the same git walk,
  // stacking makes every one of them slower: the load feeds itself. That is
  // the shape bug #44 was reported in: cards still on "loading…" minutes
  // after a restart, while the PHONE card, which fetches on its own, had
  // drawn fine.
  //
  // Asked while one is out, the request is remembered rather than dropped:
  // an explicit refresh after an action has to land, or the page shows the
  // state from before the thing the operator just did.
  if (refreshBusy){ refreshAgain = true; return new Promise(r => refreshWaiters.push(r)); }
  refreshBusy = true;
  const adoptedBefore = adoptSeq;
  let fetched = false;     // the container answered; what failed is this page
  let answered = false;    // the controller itself answered, if only with an error
  try{
    const r = preStatusUsed ? await fetch("/api/status")
                            : (preStatusUsed = true, await preStatus);
    // A proxy in front answers for a controller that is not there.
    answered = ![502, 503, 504].includes(r.status);
    // Signed out (the cookie expired, or the secret rotated): go to the
    // login page rather than showing a dead dashboard with a red dot.
    if (r.status === 401){ location.href = "/login?next=%2F"; return; }
    // A role of this account requires a second factor it has not set up
    // (R127): the setup page before anything else.
    if (r.status === 403 && (await r.clone().json().catch(() => ({}))).two_factor_setup){ location.href = "/login/setup"; return; }
    if (!r.ok) throw new Error("HTTP " + r.status);
    const got = await r.json();
    // An action's own answer was adopted while this poll was out: this
    // reply was read before that action, and drawing it put the row back
    // the way it was until the next poll, a locked padlock after an unlock
    // (B294). Dropped, and a fresh one asked for.
    if (adoptSeq !== adoptedBefore){ refreshAgain = true; return; }
    state = got;
    agentsAdopt(state.pack_agents);
    // A new run of the container under this page, noticed here or by the
    // revs poll, whichever answers first: its code is what that run serves,
    // so the page starts again rather than carrying on with the old code.
    // Ahead of everything below, the changelog above all: opened by this
    // page, it announced a build the page was not running, which is how the
    // operator met an old Global rules dialog under a new version's notes.
    // The reloaded page opens the changelog itself, and its tabs come from
    // the layout the server pruned of this container's dead sessions at boot.
    if (state.boot && bootSeen && state.boot !== bootSeen){ restartSeen(); return; }
    welcomeOnce();
    fetched = true;
    dropGoneNotebooks();
    // The bell reads what sessions have waiting for approval off this
    // payload (roadmap #27), so it is drawn from here as well as from the
    // phone and the page's own notes: a row that appeared with the poll
    // would otherwise wait for something else to happen to be seen.
    drawBell();
    drawMaintBand();
    drawHeldBand();
    drawMovedBand();
    // The account's scheme, on a browser that has never seen this account
    // (roadmap #25). localStorage is the PAINT path: the scheme is applied
    // at the top of this file before the stylesheet parses, and a value
    // fetched over the network would be a flash of the default followed by a
    // jump, so this only speaks when local has nothing to say. A pick made
    // HERE outranks the record, or picking a scheme on a phone would be
    // undone by the desktop's next poll.
    adoptTheme(state.theme, state.me);
    adoptMode(state.mode, state.me);
    adoptMotion(state.motion, state.me);
    // An account with no shell must not be sitting in one. The page opens on
    // a workspace terminal and the saved strip may carry more, both of which
    // predate knowing who is asking, so the first payload that says so is
    // where they go. Claude tabs stay: those are the console (roadmap #27).
    if (!mayShell()){
      const shells = tabs.filter(t => t.kind === "term" && !isClaude(t));
      if (shells.length) shells.forEach(t => dropTab(t.id));
    }
    if (state.boot) bootSeen = state.boot;
    // After the boot check above, which drops every Claude tab on a restart:
    // this would otherwise be reaping tabs that have already gone.
    reapDeadTerminals();
    if ($("dot").classList.contains("off")) $("dot").classList.remove("off");
    setAttr($("dot"), "aria-label", null);
    // The container's hostname, which answers "which AerieOS am I looking
    // at", and on the ordinary box, where the container is called builderbot,
    // answers it with the word already three inches to its left. Two of the
    // same word reads as a rendering fault rather than as information, so it
    // is shown only when it says something the title does not.
    const host = state.host || "";
    setText($("host"), host.toLowerCase() === "builderbot" ? "" : host);
    // The word that tells two dashboards apart: on when dev features, the
    // ones not yet vetted, are offered here, which production never has.
    setHidden($("devtag"), !state.settings?.settings?.offer_unvetted?.value);
    drawSetup();
    setText($("uptime"), "up " + shortUptime(state.uptime));
    settingsPaintFacts();
    drawBuild(state.image);
    adoptLayout(state.layout);
    // Every part draws on its own from here (bug #44). They used to run as
    // one straight line, so a draw that threw on the payload took every
    // draw after it down with it, and the page kept the fact to itself. Now
    // the part that failed says so in its own body and the rest draw.
    // A page opened (or reloaded) while a clone is running starts watching
    // it here. Not through pJobSeen: that redraws the card itself and would
    // recurse into refresh() on a finish, so only the poll is started; the
    // job itself is already in state, where the card reads it.
    if (state.project_job?.running && !pJobTimer) pJobTimer = setTimeout(pJobPoll, 1000);
    drawCard("projects", () => drawProjects(state.projects));
    // An open notebook learns from the poll that a session has started or
    // finished a batch, without the operator having to touch anything.
    drawCard(null, () => notebooks.forEach(nb => {
      const p = (state.projects || []).find(x => x.name === nb.project);
      if (p) nb.poll(p);
    }));
    drawCard("doctor", drawDoctor);
    drawCard(null, watchSignin);
    // A scan re-ran on the host: drop the cache, and any notebook showing
    // its Analysis view re-reads on its poll below.
    const agesKey = (state.reports_ages || [])
      .map(r => r.name + (r.stale ? "!" : "")).join(",");
    if (findings && !findings.loading
        && ((findingsMtime !== null && state.reports_mtime !== findingsMtime)
            || (findings.agesKey !== undefined && findings.agesKey !== agesKey)))
      findings = null;
    if (findings && !findings.loading && findings.agesKey === undefined)
      findings.agesKey = agesKey;
    // The first draw opens the page the address named: a read begun at load
    // that it takes from here is its last (bootFetch).
    if (!bootDrawn) bootReadsDone();
    render();
    restartScrollBack();
    // Cleared at the END, not where the fetch landed: a poll that arrives
    // and then fails on this page is still a failed poll, and resetting the
    // count on arrival read every one of those as the first.
    pollFails = 0;
    const pw = $("pollWhy");
    if (pw && !pw.hidden){ pw.hidden = true; pw.textContent = ""; }
    awayEnd();
    lastOkAt = Date.now();
  }catch(e){
    pollFails++;
    // Away for a restart: said calmly, and asked again soon (awayCalm).
    if (!answered && awayCalm()) return;
    // The light goes red either way; the console says whether the box was
    // unreachable or this page tripped over its own data.
    console.error("refresh:", e);
    $("dot").classList.add("off");
    // ...and the light says so in words, because red on its own does not.
    // A poll that keeps failing leaves every card that had not drawn yet
    // sitting at "loading…" forever, which reads as a hung page rather than
    // as an error: the operator described exactly that and had no way to
    // tell the two apart. The count is the useful half: one failure is a
    // blip, a rising number is the box or this page, and the reason names
    // which.
    //
    // Two different failures end up here, and they want different words: a
    // fetch that never landed is the box or the network, a payload that
    // arrived and then broke this page is a bug in this file. Calling the
    // second "not reaching the container" sends whoever reads it to check
    // the wrong machine.
    const n = `${pollFails} poll${pollFails === 1 ? "" : "s"} failed in a row`;
    const why = `Last reason: ${e && e.message ? e.message : e}`;
    // Said under the header from the second failure on (the light alone was
    // a tooltip, 11 Oct): one failed poll is a blip, two is a state.
    const said = fetched
      ? `the container answers, but this page fails on its answer: ${n}. ${why}`
      : `not talking to the container: ${n}. ${why}`;
    $("dot").setAttribute("aria-label", said);
    const pw = $("pollWhy");
    if (pw && pollFails > 1){ pw.textContent = said; pw.hidden = false; }
    if (pollFails > 1)
      // Every placeholder still waiting: the page's and the panels' own.
      document.querySelectorAll("main .loading").forEach(el => {
        el.textContent = fetched
          ? "not drawn: the page could not read the server's answer (the line under the header says why)"
          : "not loaded: the page is not reaching the container";
        el.classList.add("warn");
      });
  }finally{
    refreshBusy = false;
    if (refreshAgain){
      refreshAgain = false;
      const waiting = refreshWaiters;
      refreshWaiters = [];
      Promise.resolve(refresh()).finally(() => waiting.forEach(r => r()));
    }
    else statusLater();
  }
}

// The status poll's own clock (R218 step 10): the next read is due fifteen
// seconds after the last one, whoever asked for that one, so an action's
// read is not followed a moment later by the timer's; none is due while the
// page is hidden, where a git walk per project buys nothing nobody sees; and
// coming back to the page reads at once (its visibilitychange listener,
// beside the revisions poll's). It was a fixed interval: on time whether or
// not a read had just landed, and on, hidden or not.
const STATUS_MS = 15000;
let statusTimer = null;
function statusLater(){
  clearTimeout(statusTimer);
  // Every two seconds while away for what reads as a restart.
  const soon = awaySince && Date.now() - awaySince <= AWAY_GRACE_MS;
  statusTimer = document.hidden ? null : setTimeout(() => refresh(), soon ? AWAY_POLL_MS : STATUS_MS);
}

// Consecutive failed polls. Zero is healthy; the header's light carries the
// count and the reason once it is not.
let pollFails = 0;

// The Analysis button, and any tab already open on it. Ghosting the
// button is the ordinary half; closing an open tab is only done ONCE, when the
// page first learns there is nothing to read: a layout restored from the last
// session can carry an Analysis tab for a scanner that has since been
// unmounted, and leaving it open to say "nothing here" is a tab the operator
// has to close by hand. After that first answer a tab stays put: taking one
// out from under somebody mid-read, because a report went stale while they
// were looking at it, would be worse than the empty state it would leave.
// A notebook on a project that is no longer there (deleted, or never this
// account's) is put away once the project list has said so (B40): restored
// from the saved layout, it opened on red "not a project" lines and seven
// refused requests on every load.
// One that was on show gives way to Projects, where the project was, not to
// whichever page the fallback found (B94: deleted from its Settings, the page
// landed on the Profile).
function dropGoneNotebooks(){
  const have = new Set((state?.projects || []).map(p => p.name));
  const front = tabOf(panes[0]);
  const gone = tabs.filter(t => t.kind === "notebook" && t.arg && !have.has(t.arg));
  gone.forEach(t => hideTab(t.id));
  if (front && gone.includes(front) && !tabOf(front.id)){ railWant = "projects"; openProjectsTab(); }
}

// ---- what changed, and who cares ------------------------------------------

// A view says what it depends on; it never decides when to re-read. That
// decision was the source of four bugs in a week, every one of them a view
// reasoning about something it could not see: the roadmap's arrows and a
// session starting, the Artifacts tab and a phone connecting, and the Phone
// card polling only when it already knew of a request, which meant it could
// never find the first one.
//
// The tokens come from /api/revs, which is deliberately tiny: file mtimes and
// counters, no git, no tmux, no adb. That is what makes it affordable to ask
// every second, where /api/status is affordable every fifteen.
const revWatch = [];
let revs = {};

// `key` may be a name or a function returning one, because half of these are
// per project and the project is not known when the watch is registered.
//
// Returns the way to stop watching, and a per-project view MUST use it: a
// notebook's thirteen watches closed over a root that had been removed from
// the document, and kept firing: `showing()` reads .hidden off a detached
// element, which is still false, so every closed notebook went on fetching
// its artifacts and its version forever, once per token that moved.
function onRev(key, fn){
  const w = {key, fn};
  revWatch.push(w);
  return () => { const i = revWatch.indexOf(w); if (i >= 0) revWatch.splice(i, 1); };
}

// One out at a time, as refresh() is (R88): the timer, a tab coming back
// into view and a menu let go all start one, and with no guard an older
// reply landing second set revs back to the past, every watch fired again
// and every view's fetch doubled. Asked while one is out, it is remembered
// and asked once more when that one lands.
let revsBusy = false, revsAgain = false;
// ---- the controller restarted under this page ------------------------------
// The page starts again, since what it holds is from a server that is gone.
// With work on it that is not saved it waits for a press instead (the
// operator, 13 Nov): a band under the header says the controller was updated
// and what would be lost, with Reload, and the page stays as it was left so
// the work can be saved or copied first. Until this it reloaded at once, and
// a staged roadmap edit, a wiki page being written or a half-typed message
// went with it.
let restartHeld = false;

// What this page holds that is not saved, in words, or "".
function unsavedHere(){
  const said = [];
  notebooks.forEach((nb, name) => {
    let w = "";
    try { w = nb.unsaved?.() || ""; } catch { w = ""; }
    if (w) said.push(`${w} in ${name}`);
  });
  // A space's settings open in the dialog (a notebook's own view counts them itself).
  try {
    if (!rnHost && !$("rnmodal")?.hidden && rnDirty().length) said.push("a space's settings being edited");
  } catch { /* no form filled yet */ }
  // A message half typed: to a session's console, in the chat, in a report.
  const typed = [...Object.values(consDraft), ...Object.values(chatDraft), $("reportText")?.value]
    .some(v => String(v || "").trim());
  if (typed) said.push("a message being typed");
  return said.join(", ");
}

function restartSeen(){
  awayEnd();
  const what = unsavedHere();
  if (!what){ restartKeep(); location.reload(); return; }
  restartHeld = true;
  const band = $("newBuild");
  if (!band){ return; }
  $("newBuildSay").textContent = `The controller was updated. Reload to use it: ${what} is not saved yet.`;
  band.hidden = false;
}

// The page as it was, kept across the reload a restart brings (Perch): its
// first pane copied into the browser's session store just before, and drawn
// in the placeholder's place by the reloaded page (bootWaits) until its first
// read lands, so the page does not go blank and come back as shapes. The
// copy is inert and has no ids, so nothing draws into it; it is read once,
// for the same address and within two minutes. Where it was scrolled is
// kept too, and put back on the first draw.
const RESTART_KEEP = "aerie.restartKeep";
let restartScroll = null;
function restartKeep(){
  try{
    const pane = $("pane0");
    if (!pane) return;
    const copy = pane.cloneNode(true);
    // Only the page on show: what the stack keeps alive behind it, and any
    // frame, stays behind.
    copy.querySelectorAll(":scope > .stack > :not(.on)").forEach(e => e.remove());
    copy.querySelectorAll("iframe, video, audio, canvas, script").forEach(e => e.remove());
    copy.querySelectorAll("[id]").forEach(e => e.removeAttribute("id"));
    copy.querySelectorAll("[data-key]").forEach(e => e.removeAttribute("data-key"));
    const html = copy.innerHTML;
    if (html.length > 2000000) return;
    const at = [...pane.querySelectorAll("*")].find(e => e.scrollTop > 0);
    sessionStorage.setItem(RESTART_KEEP, JSON.stringify({hash: location.hash, at: Date.now(), html,
      scroll: at ? {cls: [...at.classList], top: at.scrollTop} : null}));
  }catch{ /* no store here: the page reloads as it always did */ }
}
// The kept page for this address, read once, or null.
function restartKept(){
  try{
    const k = JSON.parse(sessionStorage.getItem(RESTART_KEEP) || "null");
    sessionStorage.removeItem(RESTART_KEEP);
    if (!k || k.hash !== location.hash || !(Date.now() - k.at < 120000) || typeof k.html !== "string") return null;
    restartScroll = k.scroll || null;
    return k;
  }catch{ return null; }
}
// The scroller with the kept one's classes under `root`, scrolled where it was.
function restartScrollTo(root){
  const sc = restartScroll;
  if (!sc || !sc.cls?.length || !root) return;
  const el = [...root.querySelectorAll("." + sc.cls.map(c => CSS.escape(c)).join("."))][0];
  if (el) el.scrollTop = sc.top;
}
// ...on the first draw after the reload, once.
function restartScrollBack(){
  if (!restartScroll) return;
  restartScrollTo($("pane0"));
  restartScroll = null;
}

// ---- the controller away for a restart ---------------------------------------
// The page across a restart is one calm state (Perch): reads that stop
// landing after the page had been reading are a restart until they have
// been away longer than one takes. Meanwhile the page stays drawn as it
// was, one band in the note voice says AerieOS is restarting and for how
// long, the brand and the doctor's dot go quiet, the presses that would fail
// are dead, and the status is asked for every two seconds. The red line
// with its reason is kept for a controller away past the grace, for one
// that never answered this page, and for a page failing on an answer.
const AWAY_GRACE_MS = 90000, AWAY_POLL_MS = 2000;
let lastOkAt = 0;          // when a read last landed whole
let awaySince = 0;         // when the reads stopped landing
let awayTick = null;
function awayCalm(){
  if (!lastOkAt) return false;
  if (!awaySince) awaySince = Date.now();
  if (Date.now() - awaySince > AWAY_GRACE_MS){ awayQuiet(false); return false; }
  awayQuiet(true);
  awaySay();
  if (!awayTick) awayTick = setInterval(awaySay, 1000);
  return true;
}
function awaySay(){
  const band = $("awayBand");
  if (!band) return;
  const s = Math.max(0, Math.round((Date.now() - awaySince) / 1000));
  band.textContent = `AerieOS is restarting, ${s} second${s === 1 ? "" : "s"} so far: this page carries on where it is when it is back.`;
  band.hidden = false;
}
// The calm look on or off: the band, the body's class the dead presses and
// the quiet dots read, and the brand's light.
function awayQuiet(on){
  document.body.classList.toggle("away", on);
  $("dot")?.classList.toggle("away", on);
  if (on) $("dot")?.classList.remove("off");
  const pw = $("pollWhy");
  if (on && pw){ pw.hidden = true; pw.textContent = ""; }
  if (!on){
    clearInterval(awayTick); awayTick = null;
    const band = $("awayBand");
    if (band){ band.hidden = true; band.textContent = ""; }
  }
}
// Back: the reads land again, or the page starts over on a new run.
function awayEnd(){
  if (!awaySince && !document.body.classList.contains("away")) return;
  awaySince = 0;
  awayQuiet(false);
}

async function pollRevs(){
  // A notebook view draws from its own fetch, straight into its own element,
  // so the only place to hold one is here, before the watch that starts it.
  if (menuHolds(null)) return;
  if (revsBusy){ revsAgain = true; return; }
  revsBusy = true;
  try{ await pollRevsOnce(); }
  finally{
    revsBusy = false;
    if (revsAgain){ revsAgain = false; pollRevs(); }
  }
}
async function pollRevsOnce(){
  let now;
  try{
    // Which projects this page has a notebook open on. The per-project
    // tokens are watched by notebooks and by nothing else, so asking for the
    // whole share's would be a directory walk per project per second and a
    // half for panes nobody has open. Always sent, empty included: an absent
    // `p` means "all of them", which is what `aerie` and the tests want.
    // ...and of those, the one on show and any holding work a person has not
    // saved, whose moved-under-you note still has to be said (R228 steps 10
    // and 11): every notebook visited stayed on this list, and each re-read
    // on every write to its space while another page was on show. One
    // shown again is asked for at once (its shown()), and a token that
    // appears is news.
    const front = tabOf(panes[0]);
    const ps = [...new Set(tabs.filter(t => t.kind === "notebook"
                                          && (t.id === front?.id || notebooks.get(t.arg)?.held?.()
                                              || notebooks.get(t.arg)?.unsaved?.()))
                               .map(t => t.arg))];
    const r = await fetch("/api/revs?p=" + encodeURIComponent(ps.join(",")));
    if (!r.ok) return;
    now = await r.json();
  }catch(e){ return; }
  // The container was replaced under this page. Everything it holds is from
  // a server that no longer exists, so the cheapest correct answer is to
  // start again rather than reconcile.
  if (revs.boot && now.boot && revs.boot !== now.boot){ restartSeen(); return; }
  const was = revs;
  revs = now;
  // The first poll of a page has nothing to compare against, so nothing is
  // news; after that a token APPEARING is, and a token going away is not.
  //
  // Both halves of that are cases, not theory. A per-project token appears
  // when its notebook opens and stops being asked for when it closes, so
  // treating a disappearance as a change fires a dead notebook's watches,
  // and treating an appearance as no change loses anything that happened
  // between the notebook opening and the first poll that named it. Each
  // watch compares against the number its own panel last read, so a fire it
  // did not need costs nothing.
  const first = !Object.keys(was).length;
  // Anything moved: what the back-off below reads. A token only one page
  // draws counts only while that page is on show: a node's heartbeat moves
  // its numbers every poll, and counted everywhere it kept every page at a
  // second and a half for good (R218 step 10).
  if (first || Object.keys(now).some(k => was[k] !== now[k] && (!REVS_PAGE_ONLY[k] || REVS_PAGE_ONLY[k]())))
    revsMovedAt = Date.now();
  for (const w of revWatch){
    const k = typeof w.key === "function" ? w.key() : w.key;
    if (!k) continue;
    if (!first && now[k] !== undefined && was[k] !== now[k]){
      try { w.fn(k); } catch(e){}
    }
  }
}

// Fast while the tab is being looked at, slow while it is not, and the tab
// being hidden must not mean "stop", which was the mistake in the first cut
// of the phone view. A hidden tab is exactly where a request lands while
// nobody is watching, and a browser throttles background timers hard anyway;
// what matters is that whenever the page does get to run, it catches up.
// ...and slow while nothing moves (R218 step 2, the pages rule): a second
// and a half while something changed in the last minute, five seconds
// after, thirty while hidden. A chain of timeouts rather than an interval,
// so the next wait is decided after each poll.
let revTimer = null, revsMovedAt = Date.now();
const REVS_PAGE_ONLY = {"nodes.sample": () => shown("nodes"), "containers": () => shown("docker")};
const REVS_IDLE_MS = 60000;
function revsDelay(){
  if (document.hidden) return 30000;
  return Date.now() - revsMovedAt > REVS_IDLE_MS ? 5000 : 1500;
}
function reschedRevs(){
  clearTimeout(revTimer);
  revTimer = setTimeout(() => { pollRevs().finally(reschedRevs); }, revsDelay());
}
