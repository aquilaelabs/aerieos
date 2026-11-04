"use strict";
// ---- first run: the setup page (R199, R267) ---------------------------------
//
// After the owner is made, the page is this until Finish: the four things a
// new owner has to do, each a card with its state and its own action, at the
// page's reading width with nothing beside it (the operator, 18 Oct: the
// panel over half a Nodes page, six storage paths and an idle timeout ahead
// of the one step that blocks, read as anything but a start). A node first,
// which cannot wait: nothing runs without one (the operator, 12 Oct), and
// Finish is refused by the server too until one is enrolled and answering.
// Then the owner's name and email, which every commit carries; Claude Code
// on that node; and a first project. Those three can wait: Home keeps them
// in its Getting started card until they are done. Where what grows is kept
// and when an idle session ends have working defaults, under Controller
// settings, and are not asked here.

let setupSig = "", setupNodesAt = 0;

function setupNeeded(){
  return state?.settings?.settings?.setup_done?.value === false;
}

// A node enrolled, answering and running sessions, from the Nodes tab's
// list. Not a hosting-only one: it holds no code and runs no sessions, so a
// project has nowhere to work or to build its container (the operator,
// 12 Oct). That is also why the first node reaches the controller over the
// LAN or WireGuard, never only through a public hostname.
function setupNode(){
  const own = setupOwn();
  return (nodesList || []).find(n => n.kind === "agent" && n.state === "online" && n.live !== false
                                     && !n.config?.host_only && (!own || n === own)) || null;
}

// On a controller installed bare metal (R90), its own machine, which the
// installer enrolled: the first node is that one, and Finish waits for it
// rather than for one the person enrolls. Told by the install's own marker
// (the status read's bare_metal), never guessed; where the installer made
// no node of it (--no-node), the step is the container's.
function setupOwn(){
  return state?.bare_metal ? (nodesList || []).find(n => n.config?.own && n.state !== "retired") || null : null;
}

// Where each of the four stands, read from what the page already holds: the
// nodes list, the status read's git_ready and projects. Home's Getting
// started card reads the same, so the two never disagree.
function setupSteps(){
  const node = setupNode(), own = setupOwn();
  const waiting = !node && (own || (nodesList || []).find(n => n.kind === "agent" && n.state !== "retired" && !n.config?.host_only));
  const claude = node?.reported?.session?.claude || "";
  return {
    node, waiting, own,
    git: state?.git_ready !== false,
    claude,
    project: (state?.projects || []).length > 0,
  };
}

function drawSetup(){
  const on = setupNeeded();
  document.body.classList.toggle("firstrun", on);
  const el = $("setupPanel");
  if (!on){
    if (!el.hidden){ el.hidden = true; el.innerHTML = ""; setupSig = ""; }
    return;
  }
  el.hidden = false;
  // The nodes list is the node step's whole state, and no page that reads it
  // is open while this is: asked again every few seconds, so a machine that
  // dials in turns its card to done without a reload.
  if (Date.now() - setupNodesAt > 5000){
    setupNodesAt = Date.now();
    loadNodes().then(() => drawSetup());
    if (setupWalking()) setupLandLoad();
  }
  const s = setupSteps();
  // On a machine that is its own controller, its disks are a step (R161
  // step 3), read again every few seconds until they are made.
  if (s.own && !setupDisksDone(setupDisks.own) && Date.now() - setupDisks.at > 5000) setupDisksLoad();
  const dk = setupDisks.own;
  // Drawn again only when what it shows has moved: a poll landing mid-type
  // would otherwise take what was typed with it.
  const sig = JSON.stringify([setupWalkSig(s), s.node?.name || "", s.waiting?.name || "", s.waiting?.state || "", s.waiting?.live,
                              s.git, s.claude, s.project, !!s.own && [JSON.stringify(dk?.disks || []), (dk?.pools || []).length, dk?.array?.mount || "", (dk?.shares || []).length]]);
  if (sig === setupSig) return;
  setupSig = sig;
  if (setupWalking()){
    el.innerHTML = setupWalkHtml(s);
    wireSetup(el, s);
    return;
  }
  const card = setupCard;
  const nodeName = s.node ? esc(s.node.name) : "";
  el.innerHTML = `<div class="setuppage">
    <div class="setuphead">
      <h2>Set up AerieOS</h2>
      <p>AerieOS works on nodes: machines you enroll, where projects are kept, built and worked on. One is all it needs to start.</p>
      <div class="setwalkask"><span class="grow">Moving a controller or an old system here?</span><button type="button" data-setwalk="move">Walk me through it</button></div>
    </div>
    ${s.own ? card(1, "This machine", !!s.node, !s.node, s.node
      ? `<p><b>${nodeName}</b>, the machine this controller runs on, is enrolled and answering: it is your first node${
          s.node.agent?.addr ? `, at ${esc(s.node.agent.addr)}` : ""}${s.node.reported?.timezone ? `, its clock on ${esc(s.node.reported.timezone)}` : ""}. Its name and time zone are set on This machine, after Finish.</p>`
      : `<p>The machine this controller runs on is its first node, set up by the installer: ${
          s.own.state === "pending" ? "its agent is being installed and enrolled"
          : s.own.live === false ? "enrolled, and waiting for it to answer"
          : "enrolled, and setting up its sessions"}. This turns to done by itself.</p>`,
      `<button type="button" data-setenroll${featureOff("enroll") ? " disabled" : ""}>Enroll another machine</button>`)
    : card(1, "Your first node", !!s.node, !!s.waiting, s.node
      ? `<p><b>${nodeName}</b> is enrolled and answering.</p>`
      : s.waiting
      ? `<p>Waiting for <b>${esc(s.waiting.name)}</b> to dial in: run its enroll script on the machine. This turns to done by itself.</p>`
      : `<p>A sandbox VM made for it, or a machine you already have, on this network or reached over the internet.</p>${deadWhy(featureOff("enroll"))}`,
      s.node ? "" : `<button type="button" data-setvm${featureOff("enroll") ? " disabled" : ""}>New VM</button><button type="button" class="primary" data-setenroll${featureOff("enroll") ? " disabled" : ""}>Enroll node</button>`)}
    ${s.own ? setupDisksCard(2) : ""}
    ${card(s.own ? 3 : 2, "Your name and email", s.git, false, s.git
      ? `<p>Your commits carry them. Your profile, in the gear, changes them.</p>`
      : `<p>Every commit carries an author, and no Claude session starts without one.</p>
         <div class="setfields"><div class="setrow col ctlrow">${lbl("setName", "Your name")}<input id="setName" type="text" autocomplete="name" placeholder="Ada Lovelace"></div>
           <div class="setrow col ctlrow">${lbl("setEmail", "Your email")}<input id="setEmail" type="email" autocomplete="email" placeholder="ada@example.com"></div></div>`,
      s.git ? "" : `<button type="button" class="primary" data-setgit disabled>Save</button>`)}
    ${card(s.own ? 4 : 3, "Claude Code on your node", !!s.claude, false, s.claude
      ? `<p>${esc(s.claude)} on ${nodeName}. A project's Start agent signs you in there the first time.</p>`
      : s.node
      ? `<p>What a Claude session on ${nodeName} runs. It installs as a job on the node, a minute or two.</p>`
      : `<p>What a Claude session runs, installed on the node.</p><div class="sub bad setwhy">Once your node answers.</div>`,
      s.claude ? "" : `<button type="button" class="primary" data-setclaude${s.node ? "" : " disabled"}>Install</button>`)}
    ${card(s.own ? 5 : 4, "A first project", s.project, false, s.project
      ? `<p>The Projects page holds it, and every one after it.</p>`
      : `<p>A repository to work on: a new one, or one cloned from GitHub or Gitea.</p>`,
      s.project ? "" : `<button type="button" data-setproject>New project</button>`)}
    <div class="setfinish">
      <p class="dim">${s.node ? `Steps 2 to ${s.own ? 5 : 4} can wait: Home keeps them until they are done.` : "Finish opens once your node answers."}
        Storage and the idle timeout have working defaults, under Controller settings.</p>
      <div class="actbar"><button type="button" class="primary" id="setupFinish"${s.node ? "" : " disabled"}>Finish</button></div>
      <div class="hint bad" id="setupWhy" hidden></div>
    </div>
  </div>`;
  wireSetup(el, s);
}

function wireSetup(el, s){
  el.querySelectorAll("[data-setwalk]").forEach(b => b.onclick = () => setupWalkPick(b.dataset.setwalk));
  // The walk's steps are This machine's and Controller settings' own, so
  // their own wiring serves them; nothing here sends anything else.
  if (setupWalking()){ wireHeld(el); wireMove(el); }
  const vm = el.querySelector("[data-setvm]"), en = el.querySelector("[data-setenroll]");
  if (vm) vm.onclick = () => ndDialogs().openVm();
  if (en) en.onclick = () => ndDialogs().openEnroll();
  const name = el.querySelector("#setName"), email = el.querySelector("#setEmail"), git = el.querySelector("[data-setgit]");
  // Save wakes once there is a name and an email that reads as one.
  const ready = () => { if (git) git.disabled = !(name.value.trim() && email.value.trim() && email.checkValidity()); };
  if (name && email){ name.oninput = ready; email.oninput = ready; }
  if (git) git.onclick = async () => {
    busy(git, "Saving");
    const j = await (await postJSON("/api/profile", {action: "save", profile: {full_name: name.value.trim(), email: email.value.trim()}}))
      .json().catch(() => ({error: "no answer from the dashboard"}));
    if (j.error){ unbusy(git, "Save"); return notify(j.error, true); }
    refresh();
  };
  const cl = el.querySelector("[data-setclaude]");
  if (cl) cl.onclick = async () => {
    busy(cl, "Starting");
    const r = await postJSON("/api/agents", {action: "install", agent: "claude", node: s.node.id});
    const j = await r.json().catch(() => ({}));
    if (!r.ok){ unbusy(cl, "Install"); return notify(j.error || `could not start (HTTP ${r.status})`, true); }
    notifyJob(j.job, `installing Claude Code on ${s.node.name}`);
    // It turns to done when the node's census reports the version.
    busy(cl, "Installing");
  };
  wireSetupDisks(el);
  const np = el.querySelector("[data-setproject]");
  if (np) np.onclick = () => openNewProject();
  $("setupFinish").onclick = setupFinish;
}

async function setupFinish(){
  const btn = $("setupFinish"), why = $("setupWhy");
  busy(btn, "Finishing");
  let j;
  try{
    j = await (await postJSON("/api/settings", {set: {setup_done: true}})).json();
  }catch{ j = {error: "no answer from the dashboard"}; }
  if (j.error){
    unbusy(btn, "Finish");
    why.textContent = j.error;
    why.hidden = false;
    return;
  }
  setupSig = "";
  // Home, where what is left of the four waits in its Getting started card.
  location.hash = "#/home";
  refresh();
}

// A step of the setup page: its number, its title and its state as a pill, what
// it is, and its own action at the card's foot. `said` is a pill's word where
// a step has no state to read.
function setupCard(n, title, done, wait, body, acts = "", said = ""){
  const pill = said ? `<span class="pill note">${esc(said)}</span>`
    : done ? `<span class="pill ok">done</span>` : wait ? `<span class="pill note">waiting</span>` : `<span class="pill">to do</span>`;
  return `<section class="setstep${done ? " done" : ""}">
      <div class="setstephead"><span class="setnum">${n}</span><h3>${esc(title)}</h3>${pill}</div>
      <div class="setstepbody">${body}</div>${acts ? `<div class="actbar">${acts}</div>` : ""}</section>`;
}

// ---- moving here: the walk (R214, the operator, 4 Nov) -----------------------
//
// A person switching a machine over met a page that spoke only of a new start,
// a door that named three pages it hid, and the order of things nowhere. So
// the first-run page has a second shape: what moving here takes, step by step,
// in the order it has to happen, each done in place with the same controls and
// the same wiring This machine and Controller settings have, each one's state
// read from the machine. On by itself where the stick's plan names disks;
// otherwise a press away. Which one is showing is this browser's.
let setupWalk = (() => { try{ return localStorage.getItem("bb.setupWalk") || ""; }catch(e){ return ""; } })();
let setupLand = null;
function setupWalking(){
  return setupWalk ? setupWalk === "move" : !!state?.firstboot?.adopt;
}
function setupWalkPick(to){
  setupWalk = to;
  try{ localStorage.setItem("bb.setupWalk", to); }catch(e){ /* a private window: this page's memory is enough */ }
  if (to === "move") setupLandLoad();
  setupSig = ""; drawSetup();
}
async function setupLandLoad(){
  try{ setupLand = (await (await fetch("/api/move")).json()).land || null; }
  catch(e){ /* the step says it is waiting */ }
  drawSetup();
}
// What the walk's steps show, for the page's own redraw test: a poll that moved
// none of it leaves what was typed alone.
function setupWalkSig(s){
  if (!setupWalking()) return "";
  const r = (s.node || s.own)?.reported || {}, st = r.os_stick || {};
  return JSON.stringify([setupWalk, setupLand, r.adopted?.writable, (r.adopted?.mounts || []).map(m => [m.where, m.mounted, m.ro]), r.pools?.length, r.array?.mount,
                         st.pool, st.ready, st.projects, st.projects_bound, state?.held?.held, (r.disks || []).length, ((s.node || s.own)?.jobs || []).map(j => j.apply),
                         state?.firstboot?.adopt ? 1 : 0, (s.node || s.own)?.live]);
}
function setupBootBack(had){
  return `Shut this machine down and boot the old system's stick. ${had?.writable
    ? "These disks were adopted writable, so the old system then takes a parity sync, which leaves its array unprotected until it ends."
    : "Its disks are as they were."}`;
}
function setupWalkHtml(s){
  const n = s.node || s.own, rep = n?.reported || {}, stick = rep.os_stick?.stick ? rep.os_stick : null;
  const had = rep.adopted, plan = state?.firstboot?.adopt;
  const adopted = (had?.mounts || []).length > 0 && had.mounts.every(m => m.mounted);
  const placed = !stick || stick.ready || !!stick.projects_bound;
  const ld = setupLand;
  let i = 0;
  const cards = [];
  cards.push(setupCard(++i, "Have these with you", false, false,
    `<p>A controller moves with two things from the old one, both under Controller settings, Move this controller.</p>
     ${factGrid([["Move token", "shown once, when you press Prepare to move"],
                 ["The bundle", "Download the bundle, kept on the computer you are using now"]], "stickfacts")}
     <p>If the old controller ran on this machine it is off now: its address does not answer, and the bundle is the only way.</p>
     <p>Missing either one? ${esc(setupBootBack(had))} Make them there, then come back.</p>
     <p>Not moving a controller, only the disks? Leave the controller step and press Finish at the foot of this page.</p>`,
    "", "read first"));
  if (s.own) cards.push(setupCard(++i, "This machine", !!s.node, !s.node, s.node
    ? `<p><b>${esc(s.node.name)}</b> is answering${s.node.agent?.addr ? `, at ${esc(s.node.agent.addr)}` : ""}.</p>`
    : `<p>Its agent is coming up. The steps below need it, and this turns to done by itself.</p>`));
  const parts = n && (plan || had?.mounts?.length) ? adoptParts(n) : null;
  if (parts) cards.push(setupCard(++i, "The old system's disks", adopted, !s.node,
    `${adopted ? "" : `<p>Read only suits a trial: nothing is written to the data disks, so what is new needs a writable pool. Moving for good, or with no pool, adopt Writable.</p>`}${parts.body}`));
  else if (s.own && !plan) cards.push(setupDisksCard(++i));
  if (n && stick){
    const pick = stickPoolPick(n, stick, adopted || setupDisksDone(setupDisks.own) ? "None of these disks can hold them: a data disk carries the old parity. Name a folder below, or add a disk." : "Nothing to pick yet: the step before gives this one its disks.");
    const roOnly = adopted && !had.writable && !(had.mounts || []).some(m => !m.ro);
    cards.push(setupCard(++i, "Where the projects and containers go", placed, false,
      `<p>They write all day, so they live on the disks and never on the stick. The move lands there too.</p>
       ${factGrid([["Docker and the VMs", stick.ready ? `on ${stick.pool}` : stick.pool ? `waiting for ${stick.pool} to mount` : "waiting for a system pool", {cls: stick.ready ? "ok" : "warn"}],
                   ["The projects", stick.projects ? (stick.projects_bound ? `in ${stick.projects}` : `${stick.projects}, waiting for its disks`) : stick.ready ? `on ${stick.pool}` : "waiting for a pool or a folder",
                    {cls: stick.projects_bound || stick.ready ? "ok" : "warn"}]], "stickfacts")}
       ${roOnly ? `<div class="sub warn">These disks were adopted read only, with no writable pool, so nothing can go on them. Release them in the step before and adopt Writable, or add a disk.</div>` : ""}
       ${pick}${projectsFolderField(n, stick, !!state?.can?.admin)}`));
  }
  const landing = !ld ? skRows(1)
    : !ld.fresh ? `<div class="sub warn">A move lands only on a fresh controller, and this one has other accounts or nodes already. Take those away first, or install again.</div>`
    : state?.owner !== true ? `<div class="sub warn">A move here is the owner's to land.</div>`
    : `<p>The moved controller's accounts, nodes, projects and settings take this one's place, and this setup account goes with what was here, set aside and not deleted.${placed ? "" : " It waits for the step before."}</p>${moveLandBox(ld)}`;
  cards.push(setupCard(++i, "Land the controller", false, !placed, landing));
  cards.push(setupCard(++i, "After it lands", false, false,
    `${factGrid([["Sign in", "with an account the old controller had"],
                 ["Your nodes", "follow by themselves. Any that does not is listed on the Nodes page, with the one line to run on it"],
                 ...(state?.firstboot?.apps_from ? [["Containers and VMs", "This machine reads what the old system ran, and brings back what you tick. Home keeps this until it is done"]] : []),
                 ...(state?.held?.held ? [["Start", "nothing runs until it is pressed: sessions, shares, containers. Press it once the disks are as they should be"]] : [])], "stickfacts")}`,
    state?.held?.held ? `<button type="button" data-heldstart>Start</button>` : "", "then"));
  cards.push(setupCard(++i, "If you go back", false, false, `<p>${esc(setupBootBack(had))}</p><p>If you pressed Prepare to move on the old controller, press Forget it there, so its nodes stop expecting a new home.</p>`, "", "any time"));
  return `<div class="setuppage">
    <div class="setuphead">
      <h2>Moving here</h2>
      <p>The steps in the order they have to happen, each done on this page. Nothing on the old system's disks changes until a step says so.</p>
      <div class="setwalkask"><span class="grow">Starting new, with nothing to bring?</span><button type="button" data-setwalk="fresh">Set up a new one instead</button></div>
    </div>
    ${cards.join("")}
    <div class="setfinish">
      <p class="dim">${s.node ? "Not landing a controller: Finish keeps this setup account as the owner and opens Home. This machine holds all of the above." : "Finish opens once this machine answers."}</p>
      <div class="actbar"><button type="button" id="setupFinish"${s.node ? "" : " disabled"}>Finish</button></div>
      <div class="hint bad" id="setupWhy" hidden></div>
    </div>
  </div>`;
}

// ---- the disks step (R161 step 3) -------------------------------------------
//
// What the disks are for and how many may fail, never RAID levels up front
// (the operator, 29 Oct: what is best across NAS software, not the
// traditional Linux way of partitioning by hand). The layout is picked from
// the disks there and said with why; Advanced overrides it. Made with the
// Storage page's own calls (storage-pool, storage-array, storage-share), so
// there is one way to make storage, and offered again there for later.

// A disk this step may use: not the one the system runs from, not a stick.
const setupDiskFree = d => !d.system && !d.removable;
// The disks a stick's plan adopts (R163 step 9): the old system's array,
// its parity and its pools, taken as they are on This machine under Disks
// from the stick and never offered here to erase (B637: a person moving
// off their NAS saw every disk of it listed under Make it). A plan's id is
// the old system's name for the disk (MODEL_SERIAL), met by the serial or
// the by-id name.
function setupPlanned(){
  const w = state?.firstboot?.adopt?.want || {};
  return [...(w.data || []).map(x => ({...x, what: "data"})), ...(w.parity || []).map(x => ({...x, what: "parity"})),
          ...(w.pools || []).map(x => ({...x, what: "pool"}))].filter(x => x.id);
}
const setupDiskPlanned = (d, rows) => rows.find(x => x.id === d.serial || (d.serial && x.id.endsWith("_" + d.serial)) || (d.by_id && d.by_id.includes(x.id))) || null;
// The machine's free disks split: theirs (the plan's, each with its row of
// the plan) and mine (this step's to make something of).
function setupDiskSplit(n){
  const free = (n.disks || []).filter(setupDiskFree), planned = setupPlanned();
  const theirs = free.map(d => [d, setupDiskPlanned(d, planned)]).filter(([, p]) => p);
  return {theirs, mine: free.filter(d => !theirs.some(([x]) => x === d))};
}
// One that holds something now (a filesystem, a partition with one).
const setupDiskHeld = d => !!(d.holds || (d.parts || []).some(p => p.holds));

// The plan for these disks: {main, fast, notes}. `main` is where the shares
// live, {kind: "zfs"|"array", layout, disks, parity, usable_mb, may_fail,
// grows}; `fast` the SSDs' pool by purpose (R162 step 6) beside hard disks,
// or null. `lose` is how many disks may fail (0, 1 or 2); `layout` an
// Advanced override ("", "mirror", "raidz1", "raidz2", "single", "array").
function setupDiskPlan(disks, {lose = 1, layout = ""} = {}){
  const free = (disks || []).filter(setupDiskFree);
  const hdd = free.filter(d => !d.ssd), ssd = free.filter(d => d.ssd);
  // Hard disks hold the shares where there are any; SSDs alone otherwise.
  const main = hdd.length ? hdd : ssd, fastSrc = hdd.length ? ssd : [];
  const sizes = main.map(d => d.size_mb || 0), min = Math.min(...sizes), max = Math.max(...sizes);
  const same = main.length > 0 && max <= min * 1.05;
  const n = main.length, notes = [];
  let kind = "zfs", lay = layout && layout !== "array" ? layout : "", parity = [];
  if (layout === "array" || (!layout && !same && n >= 2)) kind = "array";
  if (kind === "zfs" && !lay){
    lay = n === 1 ? "single" : n === 2 || lose === 0 ? (lose === 0 ? "single" : "mirror")
      : lose >= 2 && n >= 4 ? "raidz2" : "raidz1";
    if (lose >= 2 && n < 4 && n > 1) notes.push(`Two disks failing needs four or more of the same size; with ${n}, any one may fail.`);
  }
  if (kind === "array"){
    // The largest disks are parity, as parity must be at least as large as
    // any data disk; the rest hold data.
    const by = [...main].sort((a, b) => (b.size_mb || 0) - (a.size_mb || 0));
    const p = Math.max(1, Math.min(lose || 1, n - 1));
    parity = by.slice(0, p).map(d => d.name);
  }
  const data = main.filter(d => !parity.includes(d.name));
  const usable = kind === "array" ? data.reduce((a, d) => a + (d.size_mb || 0), 0)
    : lay === "mirror" ? min : lay === "raidz1" ? (n - 1) * min : lay === "raidz2" ? (n - 2) * min : sizes.reduce((a, b) => a + b, 0);
  const mayFail = kind === "array" ? parity.length : lay === "mirror" ? n - 1 : lay === "raidz1" ? 1 : lay === "raidz2" ? 2 : 0;
  if (n === 1) notes.push("One disk keeps no copy: if it fails, what is on it is lost. Backups to another machine are on the Storage page.");
  const out = {main: n ? {kind, layout: kind === "zfs" ? lay : "", disks: main.map(d => d.name), parity, usable_mb: usable, may_fail: mayFail,
                          why: kind === "array" ? "Your disks are different sizes: an array uses every one, its largest as parity, and grows a disk at a time."
                            : lay === "single" ? "One disk, used as it is." : "Your disks are the same size: ZFS checks every block and repairs one that rots from its copy.",
                          grows: kind === "array" ? "Add a disk of any size up to the parity disk's, one at a time."
                            : lay === "mirror" ? "Replace both disks with larger ones, or add another pair." : "Add another set of disks like these as a second group."} : null,
               fast: null, notes};
  if (fastSrc.length){
    const fsame = Math.max(...fastSrc.map(d => d.size_mb || 0)) <= Math.min(...fastSrc.map(d => d.size_mb || 0)) * 1.05;
    const flay = fastSrc.length >= 2 && fsame ? "mirror" : "single";
    out.fast = {kind: "zfs", layout: flay, disks: fastSrc.map(d => d.name), usable_mb: flay === "mirror" ? Math.min(...fastSrc.map(d => d.size_mb || 0)) : fastSrc.reduce((a, d) => a + (d.size_mb || 0), 0),
                may_fail: flay === "mirror" ? fastSrc.length - 1 : 0,
                why: "Your SSDs are a fast pool of their own for apps, VMs and projects, never a cache"
                  + (flay === "single" ? ": with one SSD it is backed up to the main pool nightly." : ".")};
  }
  return out;
}

// What the step has been told, for this page's life: how many disks may
// fail, an Advanced layout, the disks holding something a person said to
// use, and the storage read it draws from (the own machine's row).
const setupDisks = {lose: 1, layout: "", use: new Set(), adv: false, own: null, at: 0, made: false};
async function setupDisksLoad(){
  setupDisks.at = Date.now();
  try{
    const j = await (await fetch("/api/storage")).json();
    setupDisks.own = (j.nodes || []).find(n => n.own) || null;
  }catch(e){ /* the card says it is waiting */ }
  setupSig = ""; drawSetup();
}
// Done once the machine holds a pool or an array, whoever made it.
const setupDisksDone = n => !!(n && ((n.pools || []).length || (n.array?.data || []).length || n.array?.mount));
const setupGB = mb => mb >= 1048576 ? `${(mb / 1048576).toFixed(1)} TB` : `${Math.round(mb / 1024)} GB`;

function setupDisksCard(num){
  const n = setupDisks.own;
  if (!n) return `<section class="setstep"><div class="setstephead"><span class="setnum">${num}</span><h3>Your disks</h3><span class="pill note">waiting</span></div>
    <div class="setstepbody"><p>Reading this machine's disks<span class="dots"></span></p></div></section>`;
  const head = (done, pill) => `<div class="setstephead"><span class="setnum">${num}</span><h3>Your disks</h3>${pill}</div>`;
  if (setupDisksDone(n)){
    const where = [...(n.pools || []).map(p => `the pool ${esc(p.name)}`), ...(n.array?.mount ? ["the array"] : [])].join(" and ");
    const shares = (n.shares || []).length;
    return `<section class="setstep done">${head(true, `<span class="pill ok">done</span>`)}<div class="setstepbody">
      <p>This machine stores on ${where}. ${shares ? `${shares} share${shares === 1 ? "" : "s"} made.` : "Make the shares your files go in:"}</p></div>
      ${shares ? "" : `<div class="actbar"><button type="button" class="primary" data-setshares>Make Media, Backups and Projects</button></div>`}</section>`;
  }
  const {theirs, mine: free} = setupDiskSplit(n);
  const facts = d => `<b>${esc(d.model || d.name)}</b> <span class="dim">${esc(setupGB(d.size_mb || 0))} · ${d.ssd ? "SSD" : "hard disk"} · serial ${esc(d.serial || "none")}</span>`;
  // The old system's disks: said whose they are, no box, nothing to press.
  const theirRow = ([d, p]) => `<div class="row setdisk theirs"><span class="grow">${facts(d)}
      <span class="sub note">the old system's ${esc(p.what === "pool" ? `pool ${p.name || ""}`.trim() : p.slot || p.what)}: adopted as it is, in the walk; nothing here touches it</span></span></div>`;
  if (theirs.length && !free.length){
    const nd = theirs.filter(([, p]) => p.what === "data").length, np = theirs.filter(([, p]) => p.what === "parity").length, npool = theirs.length - nd - np;
    const what = [nd ? `${nd} data disk${nd === 1 ? "" : "s"}` : "", np ? `${np === 1 ? "the parity disk" : `${np} parity disks`}` : "", npool ? `${npool} pool disk${npool === 1 ? "" : "s"}` : ""].filter(Boolean).join(", ");
    return `<section class="setstep">${head(false, `<span class="pill note">in the walk</span>`)}<div class="setstepbody">
    <p>Every disk here belongs to the system the stick's plan came from: ${esc(what)}. They are adopted as they are, nothing erased, and the walk does it. Nothing is made here.</p>
    <div class="rows">${theirs.map(theirRow).join("")}</div></div>
    <div class="actbar"><button type="button" class="primary" data-setwalk="move">Walk me through it</button></div></section>`;
  }
  if (!free.length) return `<section class="setstep">${head(false, `<span class="pill">later</span>`)}<div class="setstepbody">
    <p>No disk here but the one AerieOS runs from. Add disks and set them up on the Storage page, after Finish.</p></div></section>`;
  const use = d => !setupDiskHeld(d) || setupDisks.use.has(d.name);
  const plan = setupDiskPlan(free.filter(use), setupDisks);
  const row = d => `<div class="row setdisk"><label class="grow"><input type="checkbox" data-setdiskuse="${esc(d.name)}"${use(d) ? " checked" : ""}${setupDiskHeld(d) ? "" : " disabled"}>
      ${facts(d)}
      ${d.smart && d.smart.ok === false ? `<span class="pill bad">failing</span>` : ""}
      ${setupDiskHeld(d) ? `<span class="sub warn">holds ${esc(d.holds || "data")}: kept unless you tick it, which erases it</span>` : ""}</label></div>`;
  const says = p => !p ? "" : `<div class="setplan"><p><b>${p.kind === "array" ? "An array" : p.layout === "single" ? "One pool" : `A ZFS ${esc(p.layout)}`}</b> of ${p.disks.length} disk${p.disks.length === 1 ? "" : "s"}${
      p.parity?.length ? `, ${p.parity.length} for parity` : ""}: <b>${esc(setupGB(p.usable_mb))}</b> to use, ${p.may_fail ? `any ${p.may_fail === 1 ? "one disk" : `${p.may_fail} disks`} may fail` : "no disk may fail"}.</p>
      <p class="dim">${esc(p.why)}${p.grows ? ` ${esc(p.grows)}` : ""}</p></div>`;
  const lose = [[0, "No copy: all the space"], [1, "One disk may fail"], [2, "Two disks may fail"]];
  const lays = [["", "As recommended"], ["mirror", "ZFS mirror"], ["raidz1", "ZFS raidz1"], ["raidz2", "ZFS raidz2"], ["single", "ZFS, one group"], ["array", "Array with parity"]];
  return `<section class="setstep">${head(false, `<span class="pill">to do</span>`)}<div class="setstepbody">
    <p>Where your files and AerieOS's own data will live. Nothing is written until you press Make it, which names every disk it erases first.${
      theirs.length ? " The old system's disks are adopted in the walk, not made into anything here." : ""}</p>
    <div class="rows">${theirs.map(theirRow).join("")}${free.map(row).join("")}</div>
    <div class="setfields"><div class="setrow col ctlrow">${lbl("setLose", "How safe")}<select id="setLose">${optionList(lose.map(([v, w]) => [String(v), w]), String(setupDisks.lose))}</select></div>
      ${setupDisks.adv ? `<div class="setrow col ctlrow">${lbl("setLayout", "Layout")}<select id="setLayout">${optionList(lays, setupDisks.layout)}</select></div>` : ""}</div>
    ${says(plan.main)}${plan.fast ? says(plan.fast).replace("<b>A ZFS mirror</b>", "<b>A fast ZFS mirror</b>").replace("<b>One pool</b>", "<b>A fast pool</b>") : ""}
    ${plan.notes.map(t => `<div class="sub warn">${esc(t)}</div>`).join("")}
    <p class="dim">Encryption, snapshots and moving writes between pools are on the Storage page, after Finish.</p></div>
    <div class="actbar">${setupDisks.adv ? "" : `<button type="button" data-setdiskadv>Advanced</button>`}<button type="button" class="primary" data-setdisksmake${plan.main ? "" : " disabled"}>Make it</button></div></section>`;
}

function wireSetupDisks(el){
  const n = setupDisks.own;
  if (!n) return;
  el.querySelectorAll("[data-setdiskuse]").forEach(i => i.onchange = () => {
    if (i.checked) setupDisks.use.add(i.dataset.setdiskuse); else setupDisks.use.delete(i.dataset.setdiskuse);
    setupSig = ""; drawSetup();
  });
  const lose = el.querySelector("#setLose"), lay = el.querySelector("#setLayout"), adv = el.querySelector("[data-setdiskadv]");
  if (lose) lose.onchange = () => { setupDisks.lose = Number(lose.value); setupSig = ""; drawSetup(); };
  if (lay) lay.onchange = () => { setupDisks.layout = lay.value; setupSig = ""; drawSetup(); };
  if (adv) adv.onclick = () => { setupDisks.adv = true; setupSig = ""; drawSetup(); };
  const make = el.querySelector("[data-setdisksmake]");
  if (make) make.onclick = () => pressing(make, async () => {
    const free = setupDiskSplit(n).mine.filter(d => !setupDiskHeld(d) || setupDisks.use.has(d.name));
    const plan = setupDiskPlan(free, setupDisks);
    const said = names => names.map(x => { const d = (n.disks || []).find(y => y.name === x); return d ? `${x} (${d.model || "unnamed"}, ${setupGB(d.size_mb || 0)}, serial ${d.serial || "none"})` : x; });
    const all = [...plan.main.disks, ...(plan.fast?.disks || [])];
    if (!await askYes(`Make your storage on these disks?\n\n${said(all).join("\n")}\n\nEverything on them is erased.`, {title: "Make it?", verb: "Erase and make it", danger: true})) return;
    busy(make, "Making");
    const held = all.some(x => setupDiskHeld((n.disks || []).find(d => d.name === x) || {}));
    const m = plan.main;
    const body = m.kind === "array"
      ? {action: "storage-array", id: n.node, array: "create", data: m.disks.filter(x => !m.parity.includes(x)), parity: m.parity, fs: "xfs", policy: "mfs", wipe: held}
      : {action: "storage-pool", id: n.node, pool: "create", name: "tank", layout: m.layout, disks: m.disks, wipe: held};
    const calls = [body];
    if (plan.fast) calls.push({action: "storage-pool", id: n.node, pool: "create", name: "fast", layout: plan.fast.layout, disks: plan.fast.disks, wipe: held});
    for (const c of calls){
      const j = await (await postJSON("/api/v1/nodes", c)).json().catch(() => ({error: "no answer"}));
      if (j.error){ notify(j.error, true); unbusy(make, "Make it"); return; }
    }
    notify("the disks are being made: a job on this machine, a minute or two; this card turns to done when they are");
    setupDisks.made = true;
  });
  const sh = el.querySelector("[data-setshares]");
  if (sh) sh.onclick = () => pressing(sh, async () => {
    busy(sh, "Sharing");
    const base = n.array?.mount || ((n.pools || []).find(p => p.name !== "fast") || (n.pools || [])[0])?.mount || "";
    for (const name of ["Media", "Backups", "Projects"]){
      const j = await (await postJSON("/api/v1/nodes", {action: "storage-share", id: n.node, share: "set", name, path: `${base}/${name.toLowerCase()}`,
        smb: {on: true, guest: false, ro: false, tm: false, users: []}, nfs: {on: false, ro: false, clients: []}})).json().catch(() => ({error: "no answer"}));
      if (j.error){ notify(j.error, true); unbusy(sh, "Make Media, Backups and Projects"); return; }
    }
    notify("Media, Backups and Projects are being shared: who may use each is on the Storage page");
  });
}
