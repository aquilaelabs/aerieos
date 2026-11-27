// The Docker manager: a project's dev instances on a node, and the container
// editor behind them. Its own classic script beside index.html, per the
// new-surface rule (docs/nodes.md §13): same page, same global scope, one
// file per surface (roadmap R55 step 4).
//
// Chrome comes from docSurface() and the hard rules are held by uniform.mjs;
// this file only fills slots. Every action is a JOB on the node that owns the
// daemon, so the row reports progress rather than blocking on a request.
//
// dmRowsHtml and dmWireRows stay PAGE-LEVEL names on purpose: the notebook's
// own Docker view (loadNbDocker, nb-core.js) draws its rows with
// them, and a classic script shares one global scope, which is what makes
// that work without an export.
//
// Loaded BEFORE the page's own script, so
// everything here is a declaration and nothing runs at load.

// The one answer, from the poll. `on` absent (a payload that has not landed
// yet) is not "off": a control the page has no opinion about
// should behave as it always did rather than switch itself off on a hunch.

"use strict";

const dockerWhy = () =>
  state?.docker && state.docker.on === false
    ? (state.docker.why || "no docker daemon is reachable from here") : "";

// The poll's verdict, but only where it is about the node being looked at:
// state.docker is the DEFAULT node's answer, and a picked node answers for
// itself through its own overview (B109).
//
// An answer that does not say which daemon it is about is applied to NONE of
// them. The first cut of this read `state.docker.node || dockerNode`, which
// reads as caution and is the opposite: with the field absent, which it was,
// because nothing set it: the comparison became "this node equals itself"
// and every node's rows were grayed by the default node's silence again, with
// the guard sitting right there looking like it worked. Failing open costs
// nothing: the tab's own overview reports its node's daemon, and that is what
// grays a row whose daemon is genuinely down.
const dmPollSays = () => {
  const about = state?.docker?.node;
  if (dockerNode && about !== dockerNode) return "";
  return dockerWhy();
};

// Whether this list knows what is actually running. One function because the
// rows' ghosting and Remove's confirmation are the same question asked twice,
// and two copies of it would drift.
// `stale` does NOT count: a listing kept from before the node's current job
// is the last thing the daemon said, not a silence, and treating it as one
// drew "the daemon is not answering" on every row through every build. The
// pill says "as last seen" for it instead, and the actions stay live: they
// go through the agent, which is not what is busy.
const dmBlind = () =>
  !!(dockerList?.blind || dockerList?.error || dmPollSays());

// Applied to the DOM after a list draws rather than woven into each renderer,
// four places render one of these controls, and one function that switches
// them off is the only shape that cannot drift between them. Disable only:
// every renderer here redraws from state, so a daemon coming back is picked up
// by the next ordinary draw and nothing has to remember what it switched off.
function gateDocker(root, why){
  // THE CALLER SAYS WHICH DAEMON, always. There used to be a fallback to the
  // poll's answer for a caller that passed nothing, and the poll's answer is
  // about the DEFAULT node, so a project whose own node was fine had its
  // controls switched off because a different machine was down, and a
  // healthy node picked in the manager was gated by the default one's
  // absence, which is the single wrong answer a picker can give (B109). Both
  // callers know which daemon they are about; the fallback existed only to
  // be wrong, so it is gone rather than defaulted.
  if (!why) return;
  (root || document).querySelectorAll(DOCKER_ACTS).forEach(b => {
    b.disabled = true;
    // Kept for a screen reader (untitle); what the page says is the
    // tab's own line that the daemon is not answering.
    setTitle(b, why);
  });
}

// ---- the docker manager -------------------------------------------------
// What is actually running on the daemon the dev instances use. All of it,
// not only what this dashboard started: a port taken by something else is
// exactly what you open a list like this to find out about, and a listing
// that showed half would be lying by omission.
let dockerList = null;                   // the picked node's last answer
                                         // showing the same tab still repaints
// Which node the manager is looking at ("" = the default), and
// the last-known answer per node id: switching back to an offline node shows
// what was seen there instantly, in the ghosted state the blind path already
// renders, instead of a spinner for a machine that will not answer.
let dockerNode = "";
const dockerSeen = {};

// The node the tab is on rides in its `arg`, which is the one part of a tab
// that is saved. `identity()` for a kind that is not `multi` is the kind
// alone, so the arg can change without splitting the tab in two, and a
// reload stops landing on whichever node is the DEFAULT, which is not the one
// anybody picked and was reliably the second entry in the picker.
function dockerTab(){ return tabs.find(t => t.kind === "docker"); }

// What this tab draws from the node list: the picker's rows. The list
// itself moves on every heartbeat (nodes.rev folds the agent's numbers in),
// and a tab keyed on the whole of it repainted for every one while a Nodes
// tab was open anywhere in the layout, though nothing it shows had changed
// (B210's second half). A node arriving, leaving, renamed or changing state
// still repaints, because that is what the picker is made of.
function dmNodesKey(){
  if (nodesList === null) return "?";
  return nodesList.filter(n => n.kind !== "local")
    .map(n => [n.id, n.name, n.kind, n.state].join(",")).join(";") + dmOldAppsKey();
}
// ...and, on the controller's own machine, what the old system's section
// draws from: the disks, what was read, the VMs defined, the containers'
// rows and the VM picks, so a read landing or a tick redraws it.
function dmOldAppsKey(){
  const own = ownMachine();
  if (!own || dockerNode !== own.id) return "";
  const ad = own.reported?.adopted || {};
  return "|" + JSON.stringify([(ad.mounts || []).length, ad.apps || null, own.reported?.vms_other || null, !!oldAppsFrom(own),
                               adoptPlan === null ? null : adoptPlan, adoptNets, [...adoptSkip]]);
}

function openDocker(){
  const t = dockerTab();
  if (!dockerNode && t?.arg && t.arg !== "__docker") dockerNode = t.arg;
  openTab({kind: "docker", arg: dockerNode || "__docker", label: "Docker"});
  // Opening is a look: a tab already on screen is read again. Not while an
  // answer is on its way, which is the case the tab's own open hook just
  // made when the list was empty.
  if (!readBusy("docker")) loadDocker();
}

// ...on one node: the one a container was just made on, or the one a bell
// line names (B62). Without this the page opened on whichever node it last
// showed, and the build that had just started was nowhere on it. Moving
// the node swaps in that node's last answer at once, as the picker does,
// and asks for it even with another node's answer still on its way, since
// that answer is dropped on landing (asked !== dockerNode).
function openDockerOn(node){
  const moved = !!node && node !== dockerNode;
  if (moved){
    dockerNode = node;
    dockerList = dockerSeen[node] || null;
    readMoved("docker");
  }
  openDocker();
  dockerNodeKeep();
  if (moved && readBusy("docker")) loadDocker();
}

// ...and remembered when it changes, which is the only moment it can be
// written: the picker is the only thing that moves it deliberately.
function dockerNodeKeep(){
  const t = dockerTab();
  if (!t) return;
  const want = dockerNode || "__docker";
  if (t.arg === want) return;
  t.arg = want;
  saveLayout();
}

// The read the page's head began for the node this browser last listed
// (index.html, preGets): that node is the one looked at, and its list is
// read on the read already on its way (the operator, 18 Oct: a reload sat
// on the placeholder until the status read had landed, seconds on a busy
// controller, before the list was even asked for).
function dmBootLoad(u){
  const n = new globalThis.URL(u, location.origin).searchParams.get("node") || "";
  if (!dockerNode && n) dockerNode = n;
  loadDocker();
}

// The node's list read ahead while a pointer rests on the rail's
// Containers, into the cache the page draws from while its own read is out
// (dockerSeen): the first open waited the node's whole answer (a second or
// so, through its agent) on the placeholder. Once a node, and not while
// the page is reading already.
let dockerWarmAt = 0;
function dockerWarm(){
  const node = dockerNode || "";
  if (dockerSeen[node] || readBusy("docker") || Date.now() - dockerWarmAt < 10000) return;
  dockerWarmAt = Date.now();
  getJSON("/api/docker" + (node ? "?node=" + encodeURIComponent(node) : ""))
    .then(got => { if (got && !got.error){ const k = got.node || node; if (!dockerSeen[k]) dockerSeen[k] = got; if (!node && !dockerSeen[""]) dockerSeen[""] = got; } })
    .catch(() => {});
}

// A read on its way is said only once it has been slow. A read here is one
// per revision while a job runs, which is one per log line, and a word that
// appeared for each of them blinked at the foot of the tab through every
// build. Under this long, nothing is said: an answer that arrives at once
// needs no announcing.
const DM_SLOW_MS = 600;
// What a chip or Cards and List redraws: the groups' cards, or the list.
const DM_PARTS = ".pane .doc.on .dmtab .dmcard, .pane .doc.on .dmtab > .tbl";
// ...and each container's own row, a card or a line, the same one in either
// view: what Full and Compact move between (morphThrough).
const DM_ROWS = ".pane .doc.on .dmtab .row[data-inst]";
let dmSlowTimer = null, dmSlow = false;
function loadDocker(){
  return reading("docker", async overtaken => {
    const asked = dockerNode;
    clearTimeout(dmSlowTimer);
    dmSlowTimer = setTimeout(() => {
      if (readBusy("docker")){ dmSlow = true; readMoved("docker"); drawPanes(); }
    }, DM_SLOW_MS);
    const got = await getJSON("/api/docker" + (asked ? "?node=" + encodeURIComponent(asked) : ""));
    if (got.error && !got.containers) got.containers = [];
    // Every answer is that node's in the cache, the page falling back to it
    // while it has no list; reading() lands them in the order asked, so an
    // older one cannot write over a newer one (B853).
    // ...unless a newer ask has overtaken it: one revision's reload under
    // another's, about an earlier moment, and a daemon that came back
    // between the two would be painted as gone again (B69).
    if (overtaken()) return false;
    dockerSeen[got.node || asked || ""] = got;
    dmSlow = false; clearTimeout(dmSlowTimer);
    // An answer for a node the person has already picked away from must not
    // repaint the view it no longer belongs to.
    if (asked !== dockerNode) return;
    // First answer resolves "" to the default node's real id, so the picker
    // and the cache speak one language.
    if (!dockerNode && got.node) dockerNode = got.node;
    // ...and kept in this browser for the next reload's early read (dmBootLoad).
    if (dockerNode && !got.error) try{ localStorage.setItem("bb.dmnode", dockerNode); }catch(e){ /* private */ }
    dockerList = got;
    // A press queued behind a job is said until that job is not at work.
    for (const [k, q] of dmQueued){
      const jb = got.job;
      if (!jb?.running || jb.id !== q.behind || `${jb.project}|${jb.instance}` !== k) dmQueued.delete(k);
    }
    // An Edit open on a row this read has down comes alive (cFollowRow).
    cFollowRow();
    loadDockerStats(got);
  });
}

// ---- the jump bar's containers ----
// Every node's containers, not only the node this page last showed: what
// each node last answered (dockerSeen), with the nodes not yet asked read
// once the bar is focused, at most once a minute. A refusal answers 200
// with its reason, so a node this account may not read adds nothing.
let dmJumpAsked = 0;
function dmJumpLoad(){
  if (!nodesList || Date.now() - dmJumpAsked < 60000) return Promise.resolve();
  dmJumpAsked = Date.now();
  const ids = nodesList.filter(n => n.kind !== "local" && n.state !== "retired" && !dockerSeen[n.id]).map(n => n.id);
  return Promise.all(ids.map(id => getJSON("/api/docker?node=" + encodeURIComponent(id))
    .then(got => { const k = got.node || id; if (!dockerSeen[k]) dockerSeen[k] = got; }).catch(() => {})));
}
// [{name, node, where}]: each container with the node it is on, by name.
function dmJumpRows(){
  const rows = [];
  for (const [nid, got] of Object.entries(dockerSeen)){
    if (!got || got.error) continue;
    const where = (nodesList || []).find(n => n.id === nid)?.name || got.node_name || nid || "its node";
    for (const d of got.instances || []) rows.push({name: d.name || d.instance, node: nid, where});
    for (const c of got.containers || []) rows.push({name: c.name || c.id, node: nid, where});
  }
  return rows.filter(r => r.name);
}
// Picked there: the page on that node, its search narrowed to the one.
function dmJumpTo(nid, name){
  if (nid && nid !== dockerNode){ dockerNode = nid; dockerList = dockerSeen[nid] || null; }
  dmSearch = name; dmChip = "";
  railGo("containers", "docker");
  dockerNodeKeep();
  readMoved("docker"); drawPanes();
}

// What each container is using now (R216): asked once the list has landed
// and never inside it, since a sample of the daemon takes a second or two
// and the list must not wait on it. Kept by node; a row draws its strip
// from whatever is here, and a daemon that did not answer draws none.
let dockerStats = {};
// ...and each container's last hour, where its node's agent samples it
// once a minute (R218 step 9): {name: [[at, cpu %, memory %], ...]}.
let dockerSpark = {};
function loadDockerStats(list){
  const node = list?.node || dockerNode || "";
  if (!list || list.blind || list.on === false || list.error || !(list.instances || []).some(d => d.running)) return Promise.resolve();
  return reading("docker.stats", () => dockerStatsRead(node));
}
async function dockerStatsRead(node){
  const got = await getJSON("/api/docker/stats" + (node ? "?node=" + encodeURIComponent(node) : ""));
  if (!got || got.error || !got.stats) return;
  dockerStats[node] = got.stats;
  dockerSpark[node] = got.spark || {};
  if ((dockerList?.node || dockerNode || "") !== node) return;
  dmStatsPatch();
}

// The strip of what an instance's containers use, summed: CPU, memory,
// network in and out, processes. Nothing when nothing was sampled.
// What the stats are on every drawing of the rows (the page and a
// notebook's Docker view), written in place (the operator, 26 Oct: a tick
// redrew the whole page every few seconds, its folds and menus with it).
function dmStatsPatch(){
  const all = dockerStats[dockerList?.node || dockerNode || ""] || {};
  for (const el of document.querySelectorAll("[data-dmstats]")){
    const d = (dockerList?.instances || []).find(x => `${x.project}|${x.instance}` === el.dataset.dmstats);
    if (!d) continue;
    const t = document.createElement("template");
    t.innerHTML = dmStatStrip(d);
    const fresh = t.content.firstElementChild;
    // Recorded as markup, so the page's next patch takes it for its own.
    if (fresh && fresh.outerHTML !== el.outerHTML){ patchRecord(fresh); el.replaceWith(fresh); drawn(fresh); }
  }
  for (const el of document.querySelectorAll("[data-dmcpu]")){
    const st = all[el.dataset.dmcpu];
    setText(el, st ? `${st.cpu.toFixed(1)}%` : "");
  }
  for (const el of document.querySelectorAll("[data-dmmem]")){
    const st = all[el.dataset.dmmem];
    setText(el, st ? humanBytes(st.mem) : "");
  }
}
function dmStatStrip(d){
  const all = dockerStats[dockerList?.node || dockerNode || ""] || {};
  const mine = (d.services || []).map(c => all[c.name]).filter(Boolean);
  // Addressed by its row, and drawn empty where nothing is measured yet, so
  // a stats tick writes into it alone rather than redrawing the page.
  const at = `data-dmstats="${esc(`${d.project}|${d.instance}`)}"`;
  if (!mine.length) return `<div class="dmstats" ${at} hidden></div>`;
  const sum = k => mine.reduce((n, x) => n + (x[k] || 0), 0);
  const kb = n => humanBytes(n);
  // The instance's last half hour under its CPU (R218 step 9): its
  // containers' samples summed minute by minute.
  const rings = (d.services || []).map(c => (dockerSpark[dockerList?.node || dockerNode || ""] || {})[c.name]).filter(Boolean);
  const series = col => {
    const by = new Map();
    for (const r of rings) for (const x of r.slice(-30)) by.set(x[0], (by.get(x[0]) || 0) + x[col]);
    return [...by.entries()].sort((a, b) => a[0] - b[0]).map(x => x[1]);
  };
  const cpuS = rings.length ? series(1) : [];
  const lim = Math.max(0, ...mine.map(x => x.mem_limit || 0));
  const pct = lim ? Math.min(100, sum("mem") / lim * 100) : 0;
  // One band of four (the operator's concept, 17 Oct): each its word over
  // its figure, CPU with its half hour, memory with how full it is.
  return `<div class="dmstats" ${at}>
    <div class="tile"><span class="tl">CPU</span><span class="tv">${esc(sum("cpu").toFixed(sum("cpu") < 10 ? 1 : 0))}<span class="tu">%</span></span>${
      sparkSvg(cpuS, 100, "CPU over the last half hour")}</div>
    <div class="tile"><span class="tl">Memory</span><span class="tv">${esc(kb(sum("mem")))}${
      lim ? `<span class="tu">/ ${esc(kb(lim))}</span>` : ""}</span>${
      lim ? `<span class="dmbar" role="img" aria-label="${Math.round(pct)}% of its limit"><i data-style="width:${pct.toFixed(1)}%"></i></span>` : ""}</div>
    <div class="tile"><span class="tl">Network</span><span class="tv">↓ ${esc(kb(sum("rx")))}</span><span class="ts">↑ ${esc(kb(sum("tx")))}</span></div>
    <div class="tile"><span class="tl">Process${sum("pids") === 1 ? "" : "es"}</span><span class="tv">${esc(String(sum("pids")))}</span></div>
  </div>`;
}

// A stack's services as a table (the tables rule, the operator's concept,
// 17 Oct): each its dot and name, its image, its ports, what it uses now,
// and Open where it publishes a port.
const DM_SVC_COLS = [{label: "Service"}, {label: "Image", w: "minmax(0,1.3fr)"}, {label: "Ports", w: "minmax(0,1.1fr)"},
                     {label: "CPU", w: "4.5rem", num: true}, {label: "Memory", w: "5.5rem", num: true}, {act: true, w: "4.5rem"}];
function dmServicesTable(d, finished){
  const all = dockerStats[dockerList?.node || dockerNode || ""] || {};
  const rows = (d.services || []).map(c => {
    const st = all[c.name] || null;
    const ports = (c.ports || []).map(p => /(?:^|:)(\d+)->(\d+)\/\w+/.exec(p)).filter(Boolean);
    const tone = c.state === "running" ? "ok" : finished(c) ? "" : "off";
    return tblLine(DM_SVC_COLS, [
      // ...and how one that is not running is: a one-shot that finished, or
      // what docker says of it.
      `<span class="dmdot ${tone}" aria-hidden="true"></span><span class="name" title="${esc(c.status || c.state || "")}">${esc(c.service || c.name)}</span>${
        c.state === "running" ? "" : ` <span class="dim dmsvcst">${finished(c) ? "finished" : esc(c.status || c.state || "")}</span>`}`,
      `<span class="mono">${dmImage(c.image)}</span>`,
      ports.map(m => `${dmPortLink(m[1])} → ${esc(m[2])}`).join(" · "),
      `<span data-dmcpu="${esc(c.name)}">${st ? `${esc(st.cpu.toFixed(1))}%` : ""}</span>`,
      `<span data-dmmem="${esc(c.name)}">${st ? esc(humanBytes(st.mem)) : ""}</span>`,
      ports.length && c.state === "running" ? `<a href="http://${esc(daemonHost())}:${esc(ports[0][1])}/" target="_blank" rel="noreferrer">Open</a>` : ""]);
  }).join("");
  return tblWrap(DM_SVC_COLS, rows, "dmsvctbl");
}

// How long it has been up, off docker's own status ("Up 11 hours
// (healthy)"): its newest container's, as "up 11h"; "" when none says.
function dmUpFor(status){
  const m = /^Up (?:(About an?|Less than an?)|(\d+)) (second|minute|hour|day|week|month|year)s?/.exec(status || "");
  if (!m) return null;
  const n = m[2] ? +m[2] : m[1].startsWith("Less") ? 0 : 1;
  return n * {second: 1, minute: 60, hour: 3600, day: 86400, week: 604800, month: 2592000, year: 31536000}[m[3]];
}
function dmUptime(cs){
  const ups = (cs || []).filter(c => c.state === "running").map(c => dmUpFor(c.status)).filter(x => x !== null);
  if (!ups.length) return "";
  const t = Math.min(...ups);
  return "up " + (t < 60 ? `${t}s` : t < 3600 ? `${Math.round(t / 60)}m` : t < 86400 ? `${Math.round(t / 3600)}h` : `${Math.round(t / 86400)}d`);
}

// Open, a running container's main action (the operator's concept, 17 Oct):
// a new tab at the address it is reached at, or its first published port on
// the daemon's host; nothing for a stack, whose services each have theirs.
const DM_OUT = `<svg viewBox="0 0 12 12" aria-hidden="true"><path d="M5 2H2v8h8V7M7 2h3v3M10 2 5.5 6.5" fill="none" stroke="currentColor" stroke-width="1.3"/></svg>`;
function dmOpenLink(d){
  if ((d.services || []).length > 1) return "";
  const port = dmPorts(d)[0]?.pub;
  const url = d.route?.url && d.route.ready ? d.route.url : port ? `http://${daemonHost()}:${port}/` : "";
  if (!url) return "";
  return `<a class="btn primary dmopenb" href="${esc(url)}" target="_blank" rel="noreferrer" title="${esc(url)}">Open${port ? ` :${esc(port)}` : ""}${DM_OUT}</a>`;
}

// What the Ports and mounts fold holds, said on its heading: each published
// port and where it goes, or how many for a stack.
function dmPortsSaid(d){
  const ps = dmPorts(d);
  if (!ps.length) return "";
  return (d.services || []).length > 1 || ps.length > 2
    ? `${ps.length} port${ps.length === 1 ? "" : "s"}`
    : ps.map(p => `${p.pub} → ${p.target}/${p.proto}`).join(" · ");
}

// Naming a container from a project. The name says WHICH of that project's
// containers this is; what it is built from is settled by the project, which
// is why there is nothing else to fill in here.
let dnFor = null;
// ...and which of its compose files, "" for the root's own (the Artifacts
// tab's row it was pressed on).
let dnCompose = "";

// Where a sent container goes: one of the nodes of the project it will
// belong to (the one under Project, its own by default), the primary picked,
// said under the field. A project with no node has nowhere to send, and
// Create is dead until it is given one (R82, R79: a container elsewhere is
// out of reach of the project's sessions). Not the node the manager happens
// to be looking at: this dialog opens from the Artifacts tab too. Filled
// again when the node list lands if this dialog is still the one open.
function dnNodeSay(){
  const project = dnFor;
  if (!project) return;
  const whose = $("dnUnder").value || project;
  const row = state?.projects?.find(p => p.name === whose);
  const set = (row?.prefs?.nodes || []).filter(Boolean);
  const say = $("dnNodeHint"), field = $("dnNodeField");
  if (!set.length){
    field.hidden = false; $("dnNode").innerHTML = ""; $("dnNode").disabled = true;
    say.textContent = projLabel(whose) + " has no node: set one in its settings first, and the container goes there.";
    say.classList.add("bad");
    $("dnGo").disabled = true;
    return;
  }
  // Every node is offered (R166): the project's own build and run it there;
  // any other gets the image built on the project's node and shipped, so the
  // codebase never reaches it. Said on the option and under the field.
  fillNodeSelect($("dnNode"), field, set[0],
                 () => { if (dnFor === project && !$("dnmodal").hidden) dnNodeSay(); });
  field.hidden = false;
  groupNodeOptions($("dnNode"), set, whose);
  const called = projLabel(whose);
  const says = () => {
    const ship = !set.includes($("dnNode").value);
    say.textContent = ship
      ? `Not one of ${called}'s nodes: the image is built on ${called}'s node and shipped there, so the codebase never goes to it; binds into the space's tree are refused, and ${called}'s sessions can rebuild it.`
      : set.length > 1
        ? `One of ${called}'s nodes, its primary unless picked; an instance stays where it was made.`
        : `${called}'s node, ${row?.node_name || ""}: where its sessions can reach it.`;
  };
  $("dnNode").onchange = says;
  says();
  say.classList.remove("bad");
  $("dnGo").disabled = false;
}

// `sendAs` is the name the server offers (send_name): the project's own
// while it has none, which is what Send means then, and after that one
// beside it, so pressing Send again makes another container rather than a
// refusal naming the first (the operator, 26 Sep). `have` is how many it
// has already, whose ports a second one must not take.
function openSendToDocker(project, sendAs, have, compose){
  dnFor = project;
  dnCompose = compose || "";
  $("dnTitle").textContent = "New container from " + projLabel(project);
  $("dnName").value = sendAs || project;
  $("dnErrWrap").hidden = true;
  $("dnPreview").hidden = true;
  unbusy($("dnGo"), "Create");
  const from = dnCompose ? `${dnCompose} in ${projLabel(project)}` : `${projLabel(project)}'s codebase`;
  $("dnHint").textContent = have
    ? `Built from ${from}, beside the ${have === 1 ? "one" : have} it already has: give it ports of its own.`
    : `Built from ${from}. Its own name makes its own container; another name makes a second one.`;
  $("dnEnvField").hidden = true;
  $("dnEnv").value = "";
  fillUnderSelect($("dnUnder"), project);
  dnNodeSay();
  // The branches the manager already knows about for this project; it lists
  // them per project on the answer the tab is drawn from, so the dialog costs
  // nothing to fill.
  const refs = dockerList?.refs?.[project] || [];
  $("dnRefField").hidden = !refs.length;
  drawHTML($("dnRef"), optionList([["", "whatever the space is on"], ...refs]));
  $("dnmodal").hidden = false;
  // Fetched per open, and only shown when the project actually declares an
  // example: a blank Environment box on a project with nothing to fill in is
  // a question with no answer.
  postJSON("/api/devapp", {project, action:"starter", compose: dnCompose}).then(j => {
      if (dnFor !== project || !(j.text || "").trim()) return;
      $("dnEnv").value = j.text;
      $("dnEnvHint").textContent =
        "Copied from " + projLabel(project) + "'s .env.example. Saved for this container when you press Create.";
      $("dnEnvField").hidden = false;
    }).catch(() => {});
}

// The compose slug, which is NOT the project-name rule: that one keeps dots,
// and a compose project name may not have them. Mirrors _slug() in devapp.py,
// and a test asserts the two agree on the fixture whose name has a dot in it.
const dockerSlug = (s) => (s || "").toLowerCase()
  .replace(/[^a-z0-9]+/g, "-").replace(/^-+|-+$/g, "");

// Fill a dialog's node select from the registry: shown only when there is
// an actual choice, because a select with one option is furniture. `prefer`
// is the project's own binding (its settings dialog), else the manager's
// current pick, else the default node.
// `prefer` is the node the caller wants picked: the project's primary, or
// the node the manager is looking at. `allow` narrows the list to the
// project's own node set (R82): a container lives on one of its project's
// nodes and nowhere else, since a session reaches only those (R79), so
// nothing outside the set is offered. With one node to offer the picker
// still shows, disabled, so the dialog says where the container goes.
// `again` is called once the node list lands when it was not here yet, so
// a dialog opened before the first Nodes fetch (the Artifacts tab's Send)
// gets its picker instead of hiding it and sending "".
function fillNodeSelect(sel, wrap, prefer, again, allow){
  // Every node when nothing narrows: a node does everything for the
  // projects bound to it (docs/nodes.md §13).
  const dnodes = (nodesList || []).filter(n =>
    n.kind !== "local" && n.state !== "retired" && n.state !== "disabled"
    && (!allow || allow.includes(n.id)));
  // ...and drawn again when they land: loadNodes repaints only a Nodes tab,
  // so a draw here during a node-list reload lost the picker until something
  // else moved the containers' revision (B69's nodes.mjs sibling).
  if (nodesList === null || nodesStale) nodesKnown().then(() => { readMoved("docker"); drawPanes(); if (again) again(); });
  const known = dnodes.some(n => n.id === prefer);
  wrap.hidden = allow ? dnodes.length < 1 : dnodes.length < 2;
  sel.disabled = dnodes.length < 2;
  const want = known ? prefer : (dnodes[0]?.id || "");
  // An agent node carries its heartbeat's numbers, and this is the picker
  // the design says they belong beside (docs/nodes.md §9): the choice of
  // where to run a container is made on how busy the machine is.
  drawHTML(sel, dnodes.map(n => {
    const s = n.kind === "agent" && n.live && n.reported?.sample;
    const nums = s ? ` · cpu ${s.cpu_pct}% · ${Math.round(s.mem_used_mb / 1024 * 10) / 10}/${
        Math.round(s.mem_mb / 1024)}GB` : n.kind === "agent" ? " · quiet" : "";
    return `<option value="${esc(n.id)}"${n.id === want ? " selected" : ""}>${
      esc(n.name)}: ${esc(n.state)}${nums}</option>`;
  }).join(""));
}

// The project's own nodes first and named as such, the rest after them
// (the operator, 10 Oct): a container may go to any node, and only the
// project's own carry its codebase, its development and its Claude
// sessions; on any other its image is shipped. Regroups the options
// fillNodeSelect drew, keeping the one picked.
function groupNodeOptions(sel, own, whose, skip){
  const picked = sel.value;
  const opts = [...sel.options].filter(o => o.value !== skip);
  const mk = (label, list) => {
    if (!list.length) return null;
    const g = document.createElement("optgroup");
    g.label = label;
    list.forEach(o => g.append(o));
    return g;
  };
  const a = mk(`${projLabel(whose)}'s nodes: development and sessions`, opts.filter(o => own.includes(o.value)));
  const b = mk("Other nodes: its image shipped, no codebase or sessions there", opts.filter(o => !own.includes(o.value)));
  sel.innerHTML = "";
  [a, b].forEach(g => g && sel.append(g));
  if ([...sel.options].some(o => o.value === picked)) sel.value = picked;
}

// ---- copy or move a container to another node ------------------------------
// Its data with it (relocate.py): a copy beside it under a new name, or the
// same container moved. Send to Docker is the fresh one. Its env is shown on
// the way, to change what the new node needs.
let rlFor = null;

function openRelocate(project, instance){
  const d = (dockerList?.instances || []).find(x => x.project === project && x.instance === instance) || {};
  const here = dockerList?.node || dockerNode || "";
  const whose = d.owner || project;
  rlFor = {project, instance, here, whose, name: d.name || instance};
  $("rlTitle").textContent = `Copy or move ${d.name || instance}`;
  $("rlName").value = `${d.name || instance}-copy`;
  $("rlErrWrap").hidden = true;
  $("rlGo").disabled = false;
  document.querySelector('input[name="rlMode"][value="copy"]').checked = true;
  document.querySelector('input[name="rlData"][value="unpack"]').checked = true;
  const own = (state?.projects?.find(p => p.name === whose)?.prefs?.nodes || []).filter(Boolean);
  const fill = () => {
    fillNodeSelect($("rlNode"), $("rlNodeField"), own.find(n => n !== here) || "",
                   () => { if (rlFor && !$("rlmodal").hidden) fill(); });
    $("rlNodeField").hidden = false;
    groupNodeOptions($("rlNode"), own, whose, here);
    rlSay();
  };
  fill();
  $("rlEnv").value = "";
  $("rlEnvHint").textContent = "reading its env…";
  $("rlmodal").hidden = false;
  postJSON("/api/devapp", {project, instance, action: "env-get"}).then(j => {
      if (!rlFor || rlFor.instance !== instance) return;
      $("rlEnv").value = j.text || "";
      rlFor.envWas = j.text || "";
      rlFor.seeded = !!j.seeded;
      $("rlEnvHint").textContent = j.seeded
        ? "It has no env of its own: this is its space's .env.example, written as its env only if you change it."
        : "Its env as it is now: change what the new node needs (a port, an address) before it starts there.";
    }).catch(() => { $("rlEnvHint").textContent = "its env could not be read: what is written here becomes it"; });
}

function rlSay(){
  if (!rlFor) return;
  const move = document.querySelector('input[name="rlMode"]:checked')?.value === "move";
  $("rlNameField").hidden = move;
  $("rlGo").textContent = move ? "Move" : "Copy";
  const where = $("rlNode").selectedOptions[0]?.textContent.split(":")[0] || "the node picked";
  // What goes of its data (the operator, 14 Oct): written into its volumes
  // on arrival, over anything a volume of that name holds there, which is
  // said before the press; kept as the archive for the row's Unpack later;
  // or nothing, the container alone.
  const data = document.querySelector('input[name="rlData"]:checked')?.value || "unpack";
  $("rlModeHint").textContent = move
    ? (data === "none" ? `It stops, and it is built and started on ${where} with empty volumes. `
        : `It stops, its volumes and data directory go with it, and it is built and started on ${where}. `)
      + "Once it is up there its containers here come down; this node keeps its volumes until you remove them. "
      + "If it does not come up there, it comes back up here."
    : data === "none" ? `Nothing here changes; the copy is built and started on ${where} with empty volumes.`
    : `If it is running it stops for as long as its data takes to copy, then starts again here; the copy is built and started on ${where} with that data.`;
  $("rlDataHint").className = data === "unpack" ? "hint warn" : "hint";
  $("rlDataHint").textContent = data === "archive"
    ? `The archive lands in its compose directory on ${where} and stays there; it starts on empty volumes, and its row there offers Unpack when you are ready.`
    : data === "none" ? "Its volumes and data directory stay on this node and nothing of them is sent; what it makes on the new node starts from nothing."
    : `Its volumes and data directory are filled on arrival. A volume of the same name already on ${where} with files in it is written over.`;
  const own = (state?.projects?.find(p => p.name === rlFor.whose)?.prefs?.nodes || []);
  const node = $("rlNode").value;
  $("rlNodeHint").textContent = !node ? "There is no other node to send it to."
    : own.includes(node)
      ? `One of ${projLabel(rlFor.whose)}'s nodes: built and run there, where its sessions can work on it.`
      : `Not one of ${projLabel(rlFor.whose)}'s nodes: its image is built on ${projLabel(rlFor.whose)}'s node and shipped, `
        + "so its codebase never goes there, and no development or session happens there.";
  $("rlGo").disabled = !node;
}

function closeRelocate(){ $("rlmodal").hidden = true; rlFor = null; }

async function rlSubmit(){
  if (!rlFor || $("rlGo").disabled) return;
  const fail = m => ($("rlErr").textContent = m, $("rlErrWrap").hidden = false);
  const mode = document.querySelector('input[name="rlMode"]:checked')?.value || "copy";
  const name = $("rlName").value.trim();
  if (mode === "copy" && !name) return fail("the copy needs a name");
  const {project, instance} = rlFor;
  busy($("rlGo"), mode === "move" ? "Moving" : "Copying");
  try{
    const j = await postJSON("/api/devapp", {project, instance, action: "relocate", mode, node: $("rlNode").value, name,
                            data: document.querySelector('input[name="rlData"]:checked')?.value || "unpack",
                            // Its env as it stands goes with it anyway; sent
                            // only when there is something of the person's in it.
                            ...(rlFor.envWas === undefined || (rlFor.seeded && $("rlEnv").value === rlFor.envWas)
                                ? {} : {text: $("rlEnv").value})});
    if (j.error){ unbusy($("rlGo"), $("rlGo").textContent); rlSay(); return fail(j.error); }
    closeRelocate();
    notify(mode === "move" ? `moving ${j.name}: its row says each step` : `copying it as ${j.name}: its row says each step`);
    dockerList = null; readMoved("docker");
    loadDocker();
  }catch(e){ unbusy($("rlGo"), $("rlGo").textContent); rlSay(); fail(String(e)); }
}

function dnShow(){
  const raw = $("dnName").value, clean = dockerSlug(raw);
  // Only when the name it makes differs from what was typed. A container is
  // called exactly what you called it, so most of the time there is nothing
  // to warn about and the line stays out of the way.
  $("dnPreview").hidden = !raw.trim() || clean === raw.trim();
  $("dnPreview").textContent = clean
    ? `Will be created as ${clean}`
    : "That leaves nothing to name a container after";
}

function closeSendToDocker(){ $("dnmodal").hidden = true; dnFor = null; }

async function dnSubmit(){
  const project = dnFor, name = $("dnName").value.trim();
  const fail = m => ($("dnErr").textContent = m, $("dnErrWrap").hidden = false);
  if (!name) return fail("a name is needed");
  if ($("dnGo").disabled) return;
  busy($("dnGo"), "Creating");
  try{
    const j = await postJSON("/api/devapp", {project, action:"new", instance:name,
                            owner: $("dnUnder").value,
                            node: $("dnNodeField").hidden ? "" : $("dnNode").value,
                            ship: !$("dnNodeField").hidden && !!$("dnNode").value
                              && !((state?.projects?.find(p => p.name === ($("dnUnder").value || project))?.prefs?.nodes) || []).includes($("dnNode").value),
                            ref: $("dnRefField").hidden ? "" : $("dnRef").value,
                            compose: dnCompose,
                            text: $("dnEnvField").hidden ? "" : $("dnEnv").value});
    if (j.error){ unbusy($("dnGo"), "Create");
                  return fail(j.error); }
    // Where it went: the node picked, else its project's primary, which is
    // what an instance with no node of its own follows (create_instance).
    const whose = $("dnUnder").value || project;
    const goes = ($("dnNodeField").hidden ? "" : $("dnNode").value)
      || (state?.projects?.find(p => p.name === whose)?.prefs?.nodes || []).filter(Boolean)[0] || "";
    closeSendToDocker();
    // ...and build it. The manager lists what exists, so a container that was
    // only registered would not appear there: "send to" has to produce
    // something, or it sends you to a page that does not mention it. The
    // build carries the same confirmations pressing Build there would.
    // On the node it goes to, not the one the page last showed (B62).
    openDockerOn(goes);
    await dmAction(project, j.instance, "rebuild");
  }catch(e){ unbusy($("dnGo"), "Create");
             return fail("could not create it: " + e); }
}

// The job, if one is running. It comes with the overview rather than off the
// status snapshot: this page redraws on the devapp revision, which is exactly
// what a build moves, so the two arrive together and cannot disagree.
// The env editor, at module scope because two places open it now: the manager,
// where the controls live, and nothing else; it used to close over the
// artifacts renderer's `project`, which is why it had to move rather than be
// called from there.
async function openDevEnv(project, instance){
  let j;
  try{
    j = await postJSON("/api/devapp", {project, instance, action: "env-get"});
  }catch(e){ j = {error: failWords(e)}; }
  if (j.error){ notify("env: " + j.error, true); return; }
  const m = document.getElementById("devEnvModal");
  m.querySelector("textarea").value = j.text || "";
  // Both halves: whether this is a draft off the example, and what the STORED
  // file is still missing: the second stays true while the box holds an
  // unsaved draft, which is exactly when it matters.
  m.querySelector(".hint").textContent =
    (j.seeded ? "started from .env.example; nothing saved yet. " : "")
    + ((j.missing || []).length
       ? "missing against .env.example: " + j.missing.join(", ")
       : "everything .env.example declares is set");
  m.hidden = false;
  m.querySelector(".primary").onclick = async () => {
    try{
      const k = await postJSON("/api/devapp", {project, instance, action: "env-set",
                              text: m.querySelector("textarea").value});
      if (k.error){ notify(k.error, true); return; }
      m.hidden = true;
      notify("env saved");
      dockerList = null; readMoved("docker"); loadDocker();
    }catch(e){ notify("env: " + failWords(e), true); }
  };
}

// The instance's route (docs/nodes.md §7): the URL it is reached at, and
// the picker for how: lan on a published port, or Tailscale Funnel when
// the node has tailscale. public is named as unbuilt rather than hidden, so
// the record's third mode is visible for what it is. Drawn only for an
// instance that publishes something or already has a route set.
// A route picked and not yet applied, per instance: the tab redraws when
// the daemon answers, and a pick a redraw put back could never be applied.
const dmRouteDraft = {};
const devTestMode = name => (state?.projects || []).find(p => p.name === name)?.prefs?.tests_in
                             || "node";

function dmRouteLine(d){
  const r = d.route;
  const draft = dmRouteDraft[`${d.project}|${d.instance}`] || {};
  const mode = draft.mode ?? r?.mode, port = String(draft.port ?? r?.port ?? "");
  if (!r || (!r.ports?.length && r.mode === "lan" && !r.url)) return "";
  // Whose each published port is, for the picker, when the instance is more
  // than one container (B252): a bare :3000 beside a bare :7680 said nothing.
  const whose = {};
  if ((d.services || []).length > 1)
    for (const c of d.services) for (const e of c.ports || [])
      whose[String(e).split("->")[0]] = c.service || c.name;
  const link = r.url
    ? `<a href="${esc(r.url)}" target="_blank" rel="noreferrer"${r.ready ? "" : ' class="dim"'}>${esc(r.url)}</a>`
    : `<span class="dim">no address</span>`;
  const modes = [["lan", "lan: the node's address"],
                 ["funnel", r.funnel_ok ? "public link (Tailscale Funnel)" : "public link: needs Tailscale on the node"],
                 ["public", "public (not available yet)"]];
  // A cell of the row's settings grid (R210): the address it answers at,
  // then how it is reached and, for a stack, through which port; the
  // grid's one Apply saves it.
  // The address beside the label, not a line of its own over the picker
  // (the operator, 17 Oct: the card read large).
  return `<div class="setcell dmroute"><span class="lbl dmreach">Reached at ${link}${r.why ? ` <span class="dim">· ${esc(r.why)}</span>` : ""}</span>
    <div class="ctl"><select data-route="mode" data-was="${esc(r.mode)}" aria-label="route" title="how this instance is reached">${
      modes.map(([v, l]) => `<option value="${v}"${v === mode ? " selected" : ""}${
        v === "public" || (v === "funnel" && !r.funnel_ok) ? " disabled" : ""}>${esc(l)}</option>`).join("")}</select>${
    r.ports?.length > 1 ? `<select data-route="port" data-was="${esc(String(r.port))}" aria-label="port" title="which published port">${
      r.ports.map(p => `<option value="${p}"${String(p) === port ? " selected" : ""}>:${p}${
        whose[p] ? ` ${esc(whose[p])}` : ""}</option>`).join("")}</select>` : ""}</div></div>`;
}

// Whose Rebuild it is: a line of the row's own text column, beside the route,
// rather than a control in its action bar. The bar was wrong for it twice: its
// sizing is written for buttons (`.actbar input` hands an input a 12em basis,
// which a 15px checkbox spends on nothing), so the label wrapped to three
// words on three lines; and a bar has nothing safe after `.danger`, which a
// checkbox sitting under Remove broke. The long half of the explanation rides
// the `?` rather than a native title, because a title cannot be tapped and
// this tab is read on a phone.
// Which branch this instance builds from. A project's tree is SHARED: every
// session and every person on it sees one checkout, so "build the other
// branch" cannot mean switching it: the Git view refuses that outright while
// somebody's session stands in the directory, and rightly. Pinned here, the
// build comes from a worktree of its own and the project's tree is not
// touched at all.
//
// Staged and applied like the route above it, because it is a setting.
const dmRefDraft = {};
// The nginx line's three controls as typed and picked, by row (B729): a
// redraw of the tab (a job ending, a container's state) drew the line from
// nothing and took the hostname with it, so the press after sent none.
const dmNginxDraft = {};

// A route to this container through the node's nginx, from its row (R209,
// the operator, 13 Oct): the certificate the route serves under (its
// domain is the hostname; none means any hostname on 80 alone) and one of
// the container's published ports. A port routed already is offered again
// for another hostname (the operator, 14 Oct: the site at its domain and
// at www); the same hostname and port again is what the server refuses.
function dmNginxLine(d){
  const ng = dockerList?.nginx;
  if (!ng?.deployed || d.owner === "System" || !mayDocker()) return "";
  const ports = [...new Set((d.ports || []).map(p => /:(\d+)->/.exec(p)?.[1] || /^(\d+)->/.exec(p)?.[1]).filter(Boolean).map(Number))];
  const routed = ng.routed || [];
  if (!ports.length) return "";
  const key = `${d.project}|${d.instance}`, dr = dmNginxDraft[key] || {};
  // Add route is an action, not a setting: it writes the route on the press.
  // The hostname box starts on the certificate's own domain and takes a
  // subdomain under it (the operator, 13 Oct); empty with no certificate
  // means any name on 80. What is typed and picked is drawn from the draft,
  // so a redraw in between leaves it.
  return `<div class="setcell dmnginxroute">${lbl("dmng-" + key, "Route through nginx",
      "A route on this node's nginx page to one of this container's published ports, at the hostname typed (a subdomain of the "
      + "certificate's domain), or at any hostname on 80 alone with no certificate. A port routed already takes another hostname; the rest of a route is changed on the nginx page.")}
    <div class="ctl"><select id="${esc("dmng-" + key)}" data-dmngcert="${esc(key)}" aria-label="which certificate the route serves under">
      ${optionList([["", "no certificate: any hostname, 80 alone"], ...(ng.certs || [])], dr.cert || "")}</select>
    <input data-dmnghost="${esc(key)}" value="${esc(dr.host || "")}" data-was="${esc(dr.was || "")}" placeholder="app.example.com" aria-label="the hostname the route serves" autocomplete="off" spellcheck="false">
    <select data-dmngport="${esc(key)}" aria-label="which port the route goes to">${
      optionList(ports.map(p => [p, `${p}${routed.includes(p) ? " (routed)" : ""}`]), dr.port)}</select>
    <button type="button" data-dmngadd="${esc(key)}" title="write the route on the nginx page and apply it">Add route</button></div></div>`;
}

function dmRefLine(d){
  if (d.source === "file" || !mayDocker()) return "";
  const refs = dockerList?.refs?.[d.project] || [];
  if (!refs.length) return "";
  const key = `${d.project}|${d.instance}`;
  const saved = d.ref || "";
  const pick = dmRefDraft[key] ?? saved;
  // The `?` rides the LABEL (docs/design-language.md, Controls), not the end
  // of the row: a row of controls wraps on a phone, and an icon last wrapped
  // onto a line of its own, where it read as a stray mark belonging to
  // nothing.
  return `<div class="setcell dmref">${lbl("dmr-" + key, "Branch",
      "The next build uses that branch. The space's checkout, env and data stay as they are.")}
    <select id="${esc("dmr-" + key)}" data-dmref="${esc(key)}" aria-label="which branch to build">
      ${optionList([["", "whatever the space is on"], ...refs], pick || "")}</select></div>`;
}

// The compose file laid over the instance's own (the operator, 17 Oct): any
// compose file in its tree but the one it is built from, or none; staged
// and written by the grid's Apply, taken by the next build.
const dmOvDraft = {};
function dmOverrideLine(d){
  if (d.source === "file" || !mayDocker()) return "";
  const key = `${d.project}|${d.instance}`;
  const files = (dockerList?.overrides?.[d.project] || []).filter(f => f !== (d.compose_path || "") && !(d.compose_path === "" && /^(docker-)?compose\.ya?ml$/.test(f)));
  const saved = d.override || "";
  if (!files.length && !saved) return "";
  const pick = dmOvDraft[key] ?? saved;
  return `<div class="setcell dmov">${lbl("dmv-" + key, "Override",
      "Another compose file from the tree, laid over this one for this container alone: its ports, env, volumes or an extra service. The next build takes it.")}
    <select id="${esc("dmv-" + key)}" data-dmov="${esc(key)}" aria-label="compose file laid over it">
      ${optionList([["", "none"], ...new Set([...files, ...(saved ? [saved] : [])])], pick || "")}</select></div>`;
}

// The machine's GPU given to the container (R207 step 4): NVIDIA through
// the container toolkit, AMD through its render devices; offered only on
// a node that reports a card, staged and written by the grid's Apply, and
// taken by the next build.
const dmGpuDraft = {};
function dmGpuLine(d){
  if (!mayDocker()) return "";
  const node = (nodesList || []).find(x => x.id === d.node);
  const r = node?.reported || {};
  if (!r.gpu_card && !r.gpu_amd && !d.gpu) return "";
  const key = `${d.project}|${d.instance}`;
  const saved = d.gpu || "";
  const pick = dmGpuDraft[key] ?? saved;
  const opts = [["", "none"],
    ...(r.gpu_card || saved === "nvidia" ? [["nvidia", `NVIDIA card${r.gpu_card ? ` (${r.gpu_card})` : ""}, through the container toolkit`]] : []),
    ...(r.gpu_amd || saved === "amd" ? [["amd", `AMD card or APU${r.gpu_amd ? ` (${r.gpu_amd})` : ""}, its render devices (/dev/dri)`]] : [])];
  const held = node?.reported?.features?.gpuvm?.installed ? `<div class="sub dim">The NVIDIA card is marked for a VM under its node's Features: a container does not get it while it is.</div>` : "";
  return `<div class="setcell dmgpu">${lbl("dmg-" + key, "GPU",
      "The machine's card, given to every service of this container from the next build: an NVIDIA card through the container toolkit, an AMD card or APU through /dev/dri, which is how a media server transcodes.")}
    <select id="${esc("dmg-" + key)}" data-dmgpu="${esc(key)}" aria-label="which GPU the container gets">${optionList(opts, pick || "")}</select>${held}</div>`;
}

function dmClaudeSaid(d, other = false){
  // What a Claude session may do with it, in a pill's few words: the
  // setting of the PROJECT it belongs to (Agents may: Run its container),
  // the words linking there. `other` is a container AerieOS did not
  // start, which is started and stopped rather than rebuilt.
  if (!d.owner || !mayDocker() || d.owner === "System") return "";
  const mode = devClaudeMode(d.owner);
  const own = !other && d.owner === d.project && d.source !== "file";
  const says = other ? {auto: "start · stop", ask: "asks first", deny: "reads its log"}
    : own ? {auto: "rebuild · env · create", ask: "asks first", deny: "may not rebuild"}
    : {auto: "rebuild · env", ask: "asks first", deny: "may not rebuild"};
  return `<a href="#" data-dmtestgo="${esc(d.owner)}" title="the space's settings, where Agents may: Run its container is set">${esc(says[mode] || says.deny)}</a>`;
}

// The row's settings as one grid with one Apply at its foot (R210, the
// settings rule): `cells` are the setting lines above, and the foot is
// drawn only when one of them is a setting rather than a read-only line.
// `key` names the row for the Apply (`inst:project|instance` or
// `ctr:name`), and dmRowDirty says whether anything is staged.
function dmSetGrid(cells, key, {cancel = false, bare = false} = {}){
  const body = cells.filter(Boolean).join("");
  if (!body) return "";
  // ...or the grid alone, for a dialog whose foot carries the buttons.
  if (bare) return `<div class="setgrid dmsettings">${body.replace("<!--APPLY-->", "")}</div>`;
  const settable = DM_STAGED.some(s => body.includes(`data-${s.attr}=`));
  // ...with Cancel before it where Edit settings opened them: it drops what
  // was staged and puts the fields away (rows-you-open).
  const apply = `${cancel ? `<button type="button" class="stop" data-dmcancel="${esc(key)}">Cancel</button>` : ""}<button type="button" class="primary" data-dmapply="${esc(key)}"${
        dmRowDirty(key) ? "" : " disabled"} title="save what was changed above">Apply</button>`;
  // Beside the On boot tick where the row has one (its cell marks the
  // place), so a disabled Apply never takes a line of its own (the operator,
  // 17 Oct: the card read large); at the grid's foot otherwise.
  // Opened by Edit settings, Cancel and Apply are the grid's foot, at its
  // right, where a form's end is looked for.
  if (settable && body.includes("<!--APPLY-->") && !cancel) return `<div class="setgrid dmsettings">${body.replace("<!--APPLY-->", `<span class="dmapplyset">${apply}</span>`)}</div>`;
  return `<div class="setgrid dmsettings">${body.replace("<!--APPLY-->", "")}${settable
    ? `<div class="setfoot${cancel ? " dmeditfoot" : ""}">${apply}</div>` : ""}</div>`;
}
// A row's settings in a dialog (the operator, 17 Oct): a native dialog in
// the page's top layer, drawn inside its row so the row's wiring reaches its
// controls, shown by dmWireRows after each draw; its title, the settings
// grid, and the one filled Apply and Cancel at its foot. Escape is Cancel.
function dmSetDialog(name, key, cells){
  const grid = dmSetGrid(cells, key, {bare: true});
  if (!grid) return "";
  return `<dialog class="modal dmsetdlg" data-dmdlg="${esc(key)}" aria-label="Settings of ${esc(name)}">
    <div class="box wide"><h3>Settings: ${esc(name)}</h3>
      <div class="field">${grid}</div>
      <div class="foot"><span class="sp"></span>
        <button type="button" class="primary" data-dmapply="${esc(key)}"${dmRowDirty(key) ? "" : " disabled"}
          title="save what was changed">Apply</button>
        <button type="button" class="stop" data-dmcancel="${esc(key)}">Cancel</button></div>
    </div></dialog>`;
}

// The three keys a row's drafts are kept under, from the key its Apply
// carries: that key itself (`inst:project|instance` or `ctr:name`), the
// instance's `project|instance`, empty for a container AerieOS did not
// start, and the container's name, which for an instance is read from
// `list` and is none while the listing does not hold it.
function dmRowKeys(key, list = dockerList){
  const inst = key.startsWith("inst:") ? key.slice(5) : "";
  const name = inst ? (list?.instances || []).find(x => `${x.project}|${x.instance}` === inst)?.name : key.slice(4);
  return {row: key, inst, name};
}
// What a row has staged, dropped (Cancel): every draft its key names, and
// with them what was typed on its nginx line, which is no setting of the
// Apply's (Add route writes it) and so is not in DM_STAGED.
function dmDropDrafts(key){
  const keys = dmRowKeys(key);
  for (const s of DM_STAGED) if (keys[s.key]) delete s.draft[keys[s.key]];
  if (keys.inst) delete dmNginxDraft[keys.inst];
}
// Whether a row has a setting staged and not yet applied: the drafts each
// setting keeps, read by the row's key.
function dmRowDirty(key){
  const keys = dmRowKeys(key);
  return DM_STAGED.some(s => keys[s.key] && s.draft[keys[s.key]] !== undefined);
}
// Which project a row belongs to: its group on this tab, the notebook that
// lists it, and whose Claude sessions may see it and work on it (the
// operator, 24 Sep). Staged and applied like the branch above, because it
// is a setting. Keyed `inst:project|instance` or `ctr:name`.
const dmOwnDraft = {};

function dmOwnerLine(r, key){
  if (!mayDocker()) return "";
  const saved = r.owner || "";
  // System's is the deployment's to set (R180): said, with nothing to pick.
  if (saved === "System")
    return `<div class="setcell ro dmowner">${lbl("", "Space",
      "AerieOS deployed this itself, so it is System's: no space's session sees it, "
      + "and the network lets it reach every container on this node.")}<div class="val">System</div></div>`;
  const pick = dmOwnDraft[key] ?? saved;
  // A project since deleted is still what the row says until it is changed.
  const names = myProjectNames(saved);
  const shown = n => n === saved && r.owner_gone ? `${r.owner_label || n} (deleted)` : dmOwnerSaid(n);
  const id = "dmo-" + key;
  return `<div class="setcell dmowner">${lbl(id, "Space",
      "Its space's sessions can see it and, as that space's Run its container setting allows, "
      + "work on it. No space keeps it from every session.")}
    <select id="${esc(id)}" data-dmown="${esc(key)}" aria-label="which space it belongs to">
      ${optionList([["", "no space"], ...names.map(n => [n, shown(n)])], pick || "")}</select></div>`;
}

// Which project a project's own instance is built from, and Move to put it
// under another (the operator, 8 Oct: MediaReducer-Dev's to MediaReducer).
// Its containers, env and data stay as they are; a written container has no
// project behind it and moves with the Project line above.
const dmMoveDraft = {};
function dmMoveLine(d, busy = false){
  if (!mayDocker() || d.source === "file") return "";
  const key = `${d.project}|${d.instance}`, pick = dmMoveDraft[key] ?? d.project;
  // Built from a project since deleted: it is still that one's until moved.
  const gone = !(state?.projects || []).some(p => p.name === d.project);
  const names = myProjectNames(d.project);
  const id = "dmm-" + key;
  return `<div class="setcell dmmove">${lbl(id, "Built from",
      "The repository whose compose file and tree it is built from. Another one, applied, moves it "
      + "there, keeping its name, env and data; it then builds from that repository's tree.")}
    <select id="${esc(id)}" data-dmmove="${esc(key)}" aria-label="the space it is built from"${busy ? " disabled" : ""}>${
      optionList(names.map(n => [n, gone && n === d.project ? `${n} (deleted)` : projLabel(n)]), pick)}</select>${
      // Refused while a job builds it, since the job names the old space:
      // dead until it ends, and why said under it.
      busy ? `<div class="hint">A job is running on it: it moves once that has ended.</div>` : ""}</div>`;
}

function dmTestSaid(d){
  // Where the project's tests run, the project's setting (R68 step 6),
  // linking to where it is changed.
  if (d.source === "file") return "";
  const mode = devTestMode(d.project);
  return `<a href="#" data-dmtestgo="${esc(d.project)}" title="the space's settings, where its node and its test command are">${
    mode === "only" ? "in its container only" : mode === "up" ? "in its container when up" : "on the node"}</a>`;
}

// Which rows have their settings open (the operator's concept, 17 Oct): read
// as pills until Edit settings swaps the fields in; Apply and Cancel put them
// away; a row with a setting staged stays open whatever this says.
const dmEditing = new Set();
// A container's settings hold Back as every dialog does (backHold): Back
// puts them away as Cancel does.
const dmBack = new Map();
function dmBackHold(key){
  if (dmBack.has(key)) return;
  dmBack.set(key, backHold(() => { dmBack.delete(key); dmDropDrafts(key); dmEditing.delete(key); readMoved("docker"); drawPanes(); }));
}
function dmBackLet(key){
  const t = dmBack.get(key);
  dmBack.delete(key);
  if (t) backRelease(t);
}
// Edit settings is the first thing behind the row's ⋯ (the operator, 17
// Oct): the pills say every setting, so the press that changes them can
// wait in the menu.
const dmEditBtn = key => mayDocker() && !dmEditing.has(key) && !dmRowDirty(key)
  ? `<button type="button" data-dmedit="${esc(key)}">Edit settings</button>` : "";
function dmSetPills(pills){
  return factPills(pills, "dmsetpills");
}
// An instance's settings as pills: whose it is, what it is built from when
// that is another project, its branch, where it is reached, whether it
// starts on boot, what an agent may do and where tests run.
function dmInstPills(d, managed){
  const r = d.route;
  const mode = {lan: "LAN", funnel: "public link", public: "public"}[r?.mode] || "";
  const url = r?.url ? `<a href="${esc(r.url)}" target="_blank" rel="noreferrer"${r.ready ? "" : ' class="dim"'}>${esc(r.url.replace(/^https?:\/\//, "").replace(/\/$/, ""))}</a>` : "";
  const refs = dockerList?.refs?.[d.project] || [];
  return [
    ["Space", esc(dmOwnerSaid(d.owner))],
    d.source !== "file" && d.owner && d.project !== d.owner ? ["Built from", esc(projLabel(d.project))] : null,
    d.source !== "file" && refs.length ? ["Branch", d.ref ? esc(d.ref) : "follows space"] : null,
    d.override ? ["Override", esc(d.override)] : null,
    d.gpu ? ["GPU", d.gpu === "nvidia" ? "NVIDIA card" : "AMD card or APU"] : null,
    r && (mode || url) ? ["Reached via", [esc(mode), url].filter(Boolean).join(" · ")] : null,
    dmRoutesOf(d).length ? ["nginx", dmRoutesOf(d).map(dmRouteLink).join(" · ")] : null,
    d.exists && !managed ? ["", d.boot ? "✓ Starts on boot" : "not on boot", d.boot ? "ok" : ""] : null,
    ["Agent", dmClaudeSaid(d)],
    ["Tests", dmTestSaid(d)],
  ];
}

function dockerJob(){
  const j = dockerList?.job;
  // While it runs, and while it has something to say about how it ended. The
  // running-only rule meant a build that failed, or one stopped on purpose,
  // which ends a job with no other trace: vanished the instant it finished,
  // leaving the row showing whatever state it happened to be in. The server
  // stops sending it when the next job starts, which is when it stops being
  // the answer to "what just happened here".
  return j && (j.running || j.error) ? j : null;
}

// A job that has just ended, said on its row the moment the queue says so
// (B65): the row kept "stopping..." and Abort for the seconds the whole
// listing took to read again after its build had failed. Asked of the one
// job when the devapp revision moves, and written into the answer on
// screen, which the fresh listing then replaces. Read synchronously up to
// its fetch, so the caller may drop dockerList right after calling it.
async function dmJobSettle(){
  const j = dockerList?.job;
  if (!j?.running || !j.id) return;
  let got;
  try{ got = await getJSON(`/api/v1/jobs?id=${encodeURIComponent(j.id)}`); }catch(e){ return; }
  if (!got || got.id !== j.id || !j.running || !["succeeded", "failed", "canceled"].includes(got.state)) return;
  Object.assign(j, {running: false, state: got.state, step: "", aborting: false,
                    error: got.state === "succeeded" ? "" : (got.error || got.state)});
  readMoved("docker"); drawPanes();
}

// What a confirm or a notice calls a container: the name its row shows,
// else its project's shown name and the instance, never the project's
// directory, which a name reused after a delete has numbered (B64).
function dmCalled(project, instance){
  const d = (dockerList?.instances || []).find(i => i.project === project && i.instance === instance);
  return d?.name || `${projLabel(project)}/${instance}`;
}

// What the artifact row's buttons used to do, moved here with them. The
// confirmations come with it: taking something down and handing a compose
// file more than its own directory are both decisions, and moving a button
// is not a reason to stop asking.
async function dmAction(project, instance, act, btn){
  if (act === "env"){ openDevEnv(project, instance); return; }

  if (act === "edit"){
    // Which kind, off the button the row drew: the list it came from may be
    // reloading, and a written container opened as a project's came up empty.
    if (btn?.dataset.src === "file") openEditContainer(project); else openEditInstance(project, instance);
    return;
  }
  // Abort asks nothing: the confirmation for a destructive verb is worth its
  // interruption, and stopping a build you are watching is not destructive:
  // what is already built is kept, and pressing it again is the only way to
  // undo an accidental press, which costs a rebuild rather than data.
  // It reads Stopping on the click, held until the read after the answer,
  // and Abort again with the reason if the server refuses.
  if (act === "abort"){
    if (btn) btn.disabled = true;
    await dmGo(project, instance, "abort", () => postJSON("/api/devapp", {project, instance, action: "abort"}));
    return;
  }
  // A node's nginx behind the newest line (R192): the nginx tab's verb,
  // from the row it is about.
  if (act === "nginx-update"){
    const d = (dockerList?.instances || []).find(i => i.project === project && i.instance === instance);
    if (!await askYes(`Update nginx on this node to ${d?.nginx_to || "the newest line"}?\n\nIt is rebuilt with the new image, so its sites are down while the node pulls it.`)) return;
    if (btn) busy(btn, "Updating");
    try{
      const j = await postJSON("/api/nginx", {action: "update", node: dockerList?.node || dockerNode});
      if (j.error) notify(j.error, true);
      else if (j.note) notify(j.note, true);
      else notify(`updating nginx to ${j.to}: this row has the build`);
    }
    catch(e){ notify("could not update it: " + failWords(e), true); }
    readMoved("docker"); drawPanes(); loadDocker();
    return;
  }
  // Up, Down, Rebuild and an image's update lose nothing and ask nothing
  // (R265, the operator, 19 Nov): the row says what the press started.
  // nginx's update above keeps its question, since every space's sites on
  // the node are down while it pulls.
  if (act === "remove" && !await askYes(
      `Remove ${dmCalled(project, instance)}?\n\n`
      // Which of the two halves is actually going to happen. A row whose
      // daemon is not answering loses the down, and somebody removing one
      // should be told that before they press it rather than read it
      // afterwards.
      + (dmBlind()
          ? `Docker is not answering, so it is not taken down; only the row goes. `
          : `It is taken down first. `)
      + `Its env file and data stay for a remake.`)) return;
  let ack = "", beside = "";
  if (act === "up" || act === "rebuild"){
    // The full state for this one instance, asked now rather than computed
    // for every instance on every paint: risks and problems cost a compose
    // config parse each, and the manager lists them all.
    let st;
    try{
      const j = await postJSON("/api/devapp", {project, instance, action:"state"});
      if (j.error) throw new Error(j.error);
      st = j.state || {};
    }catch(e){ notify("could not read its state: " + failWords(e), true); return; }
    if ((st.problems || []).length){
      notify(`${dmCalled(project, instance)} will not work as written: `
             + st.problems.join("; "), true);
      return;
    }
    // A port something else holds: here, where Up is, that is a start that
    // would fail, and the way out is this instance's own env. (The Artifacts
    // view says the same fact as a note, since its Send opens that env.)
    if (act === "up" && (st.port_clash || []).length){
      notify(`port ${st.port_clash.join(", ")} ${st.port_clash.length === 1 ? "is" : "are"} `
             + `published already on this node: set another in this instance's env (Env), then Up`, true);
      return;
    }
    if ((st.missing_env || []).length && act === "up"){
      notify(`the env is missing ${st.missing_env.join(", ")}: press Env`, true);
      return;
    }
    // What this press needs a person's yes for, found now and asked once
    // (R265: it was a question for the rebuild itself, another for what the
    // compose reaches and a third for what it ships new, each a screen):
    // what the compose file asks for past its own directory, until that
    // list is acknowledged, and what it would run beside the app that its
    // last build did not ship (the operator, 17 Oct: the person knows what
    // is actually being shipped). With neither, the press runs; a no leaves
    // it as it was.
    const reach = st.risks_ack ? [] : st.risks || [], fresh = st.beside_new || [];
    if (reach.length || fresh.length){
      const verb = act === "up" ? "Start" : st.built_rev ? "Rebuild" : "Build";
      if (!await askYes(fresh.length ? "If a new one is not part of the app, cancel and give it a container of its own with New container." : "", {
        title: `${verb} ${dmCalled(project, instance)}?`, verb,
        parts: [{head: "Its compose file asks for more than its own directory", lines: reach},
                {head: "New beside the app, which its last build did not ship", lines: fresh}]})) return;
      if (reach.length) ack = st.risks_digest || "";
      if (fresh.length) beside = st.beside_digest || "";
    }
  }
  if (btn) btn.disabled = true;
  // A press while a job is at work on it is queued behind that one, never
  // refused (nodes.job_waits): said on the press and on its row.
  const ahead = dmAhead(project, instance);
  const j = await dmGo(project, instance, act, () => postJSON("/api/devapp", {project, instance, action:act, ack, beside}), ahead);
  // What was done instead of what was asked: a remove whose daemon could
  // not be reached took the record and nothing else. Said, because the row
  // vanishing looks identical either way.
  if (!j.error && j.note) notify(j.note);
  else if (!j.error && ahead && j.job !== ahead.id)
    notify(queuedSaid(`${DM_VERB[act] || act} on ${dmCalled(project, instance)}${j.already ? ", already" : ""}`, `${DM_JOB_NOUN[ahead.action] || "the job"} running on it`));
}

// The job at work on an instance, as the list has it, or null.
function dmAhead(project, instance){
  const jb = dockerJob();
  return jb?.running && jb.project === project && jb.instance === instance ? jb : null;
}
// What a press is called, and what a job is, in the queued line.
const DM_VERB = {up: "Up", down: "Down", rebuild: "Rebuild", update: "Update", remove: "Remove"};
const DM_JOB_NOUN = {rebuild: "the rebuild", up: "the Up", down: "the Down", update: "the update", remove: "the removal",
                     rename: "the rename", "relocate-out": "the move", "relocate-in": "the move", "relocate-unpack": "the unpack"};

// A row's press drawn on the click (the operator, 22 Nov: Down read as
// nothing for the 11 s its job took to reach the row): its state is the
// press's word, by "project|instance", until the server has answered and the
// read after it has the job, which says it from there. A refusal puts the
// row back and says why (drawNow). The answer comes back.
// One pressed behind a job at work (`ahead`) is said on the row as queued
// behind it from the click until that job has ended (dmQueued), which a read
// of the list says.
const dmGoing = new Map(), dmQueued = new Map();
async function dmGo(project, instance, act, send, ahead = null){
  const key = `${project}|${instance}`;
  const redraw = () => { readMoved("docker"); drawPanes(); };
  const j = await drawNow(() => {
    dmGoing.set(key, act);
    if (ahead && DM_VERB[act]) dmQueued.set(key, {act, behind: ahead.id});
    redraw();
    return () => { dmGoing.delete(key); dmQueued.delete(key); redraw(); };
  }, send);
  dockerList = null; readMoved("docker");
  try{ await loadDocker(); }catch(e){ /* the read says its own failure */ }
  if (dmGoing.get(key) === act){ dmGoing.delete(key); redraw(); }
  return j;
}

// Where a container's published port actually answers.
//
// NOT location.hostname, which is the machine serving this page. The daemon
// runs on the sandbox VM: a different machine, which is the entire point of
// the arrangement, and a container publishing 8989 publishes it there. Using
// the page's own host pointed every port label and every Open link at the
// NAS box, where either nothing answers or, worse, something else does.
//
// Taken from the address the manager is already told about, with the scheme,
// the account and any port stripped: ssh://bb@10.0.0.9 is the machine 10.0.0.9.
// Falls back to this page's host, which is right for the case where there is
// no daemon and therefore no container to open.
function daemonHost(){
  const w = (state?.docker?.where || "").trim();
  const h = w.replace(/^[a-z][a-z0-9+.-]*:\/\//i, "")
             .replace(/^[^@/]*@/, "")
             .replace(/[:/].*$/, "");
  return h || location.hostname;
}

// The wiring itself, fetched on the first open. It arrives after the fold has
// already animated to the height of "reading…", so the panel is grown a second
// time when the real lines land: measured either side of the swap, which is
// what keeps the rows below from jumping.
// What each instance's Ports and mounts last said, by "project|instance",
// drawn at once into a fold a redraw brought back open (B827).
const dmWireSeen = {};
function loadWire(d){
  d.dataset.done = "1";
  const inst = d.closest("[data-inst]")?.dataset.inst || "";
  return reading("docker.wire:" + inst, () => wireRead(d));
}
async function wireRead(d){
  const [project, instance] = d.closest("[data-inst]").dataset.inst.split("|");
  const box = d.querySelector(".wire");
  let html;
  const key = `${project}|${instance}`;
  try{
    const j = await postJSON("/api/devapp", {project, instance, action:"state"});
    if (j.error) throw new Error(j.error);
    const st = j.state || {};
    // An answer that could not read the compose (the daemon or compose not
    // answering in time, as under a loaded gate) says nothing about the
    // wiring: what was read before stays, and with nothing read before it
    // says it could not (B12), never "publishes nothing".
    if (!st.wired) throw new Error(dmWireSeen[key] ? "kept" : st.wired_why ? `compose says: ${st.wired_why}` : "the compose file could not be read just now");
    const ports = st.ports || [], mounts = st.mounts || [];
    const portLine = p => {
      const at = `${daemonHost()}:${p.published || ""}`;
      // A link only where there is something to open: a port with no
      // published side is picked at start and has no address yet, and a
      // link to a udp port is a link to nothing.
      const body = p.published && /tcp/i.test(p.proto || "tcp")
        ? `<a href="http://${esc(at)}/" target="_blank" rel="noreferrer">${esc(at)}</a>`
        : esc(p.published ? at : "picked at start");
      return `<div class="dim li wport"><span class="wt">${esc(p.target)}:${
        esc(p.proto)}</span> <span class="wa">←</span> ${body}</div>`;
    };
    const mountLine = m => `<div class="dim li wmount"><span class="wt">${
      esc(m.target)}</span> <span class="wa">${m.ro ? "←" : "↔"}</span> ${
      esc(m.source)}</div>`;
    // Which container each line is, when the compose has more than one: a
    // stack's ports in one list could not be told apart (B252, the operator,
    // 24 Sep). A group per service, headed by its name, in the same columns.
    const svcs = [...new Set([...ports, ...mounts].map(x => x.service || ""))].sort();
    const lines = svcs.length > 1
      ? svcs.map(sv => `<div class="wgrp"><div class="lbl wsvc">${esc(sv)}</div>${
          ports.filter(p => (p.service || "") === sv).map(portLine).join("")}${
          mounts.filter(m => (m.service || "") === sv).map(mountLine).join("")}</div>`).join("")
      : ports.map(portLine).join("") + mounts.map(mountLine).join("");
    html = lines || `<div class="dim li">it publishes nothing and mounts nothing</div>`;
  }catch(e){
    html = dmWireSeen[key] && e.message === "kept" ? dmWireSeen[key]
      : `<div class="dim li bad">could not read it: ${esc(e.message || String(e))}</div>`;
  }
  dmWireSeen[key] = html;
  if (!d.isConnected){
    // The manager repainted under it, because every step of a job does that now,
    // and the fold the operator opened is a fresh, closed one with nothing in
    // it. Carry the answer over rather than drop it: the same instance's new
    // fold gets the lines and stays open, so a build in progress does not
    // snap the wiring shut every half second.
    const inst = d.closest("[data-inst]")?.dataset.inst || `${project}|${instance}`;
    const nd = document.querySelector(
      `:is(.dmtab, .dkview) .row[data-inst="${CSS.escape(inst)}"] details.sect`);
    if (!nd || nd.dataset.done) return;
    nd.dataset.done = "1";
    drawHTML(nd.querySelector(".wire"), html);
    if (d.open) nd.open = true;
    return;
  }
  const before = d.offsetHeight;
  drawHTML(box, html);
  const after = d.offsetHeight;
  if (d.open && before !== after && !noMotion()) foldHeight(d, before, after, () => {});
}

// A starting point rather than an empty box. Somebody opening this is about
let cEditing = null;              // the container being edited, or null for new

// While the container runs, the dialog is for reading (the operator, 11 Oct):
// Save ghosted and both boxes read-only, still scrollable and selectable.
// Down it to change anything here.
function cLock(running){
  $("cYml").readOnly = $("cEnv").readOnly = running;
  $("cGo").disabled = running;
}

// What the editor says of a container AerieOS deploys itself.
const C_MANAGED = "AerieOS manages this one: its name, compose file and env are written where it was deployed from (the nginx page).";
const C_RUNNING = "It is running, so this is for reading: Down it to change its name, compose file or env.";
// A written container's name line, off its row as the list has it now.
// The name changes only while it is down (the operator, 11 Oct): it is
// the compose project, the data directory and the volumes' prefix, and
// the node carries those under the new name before the next Up.
function cNameSay(name){
  const row = (dockerList?.instances || []).find(d => d.project === name && d.instance === "main");
  // Not known to be running is down for the dialog: opened while the list
  // reloads, it found no row and locked itself; the server still refuses a
  // rename of one that is up.
  const down = !row?.running;
  // AerieOS's own (System) is managed: for reading, whatever its state
  // (the operator, 11 Oct).
  const managed = row?.owner === "System";
  // ...nor while a job runs on it: its name is the job's compose project.
  const jb = dockerJob(), jobOn = !!(jb?.running && jb.project === name && jb.instance === "main");
  $("cName").disabled = !down || managed || jobOn;
  $("cNameHint").textContent = managed
    ? C_MANAGED
    : jobOn && down
    ? "A job is running on it: its name can change once that has ended."
    : down
    ? "Change the name while it is down: its volumes and data directory follow it on the node, then Build it again."
    : C_RUNNING;
  return {down, managed, jobOn};
}
// ...and a space's instance's, whose name is its own: not renamed while a
// job is on it either (the server refuses it, the job naming the old one).
function cInstanceSay(project, running, jobOn = false){
  return running ? C_RUNNING
    : jobOn ? "A job is running on it: its name can change once that has ended."
    : `Its name is its own: its volumes and data directory follow a new one on the node. The compose file is ${projLabel(project)}'s, in its folder: `
      + "saving it is an uncommitted change there, which the Git view shows. The env is this container's.";
}

// An Edit opened while its container ran follows its row (the operator, 22
// Nov: it stayed for reading after Down until the page was reloaded): once
// a read has the row down, the dialog is what opening it then would draw,
// its boxes and Save live, and its name once no job is on it. Only that way:
// one brought up under an open dialog keeps what was typed, and the server
// refuses its Save. Called as each read of the list lands.
let cUpHeld = false;
function cFollowRow(){
  if (!cUpHeld || cEditing === null || $("cmodal").hidden || $("cGo").getAttribute("aria-busy") === "true") return;
  const at = typeof cEditing === "object" ? cEditing : {project: cEditing, instance: "main"};
  const row = (dockerList?.instances || []).find(d => d.project === at.project && d.instance === at.instance);
  if (!row || row.running) return;
  if (typeof cEditing === "object"){
    const jobOn = !!dmAhead(at.project, at.instance);
    $("cName").disabled = !cEditing.name || jobOn;
    $("cNameHint").textContent = cInstanceSay(at.project, false, jobOn);
    // Held on while a job is on it, as a written container's is below.
    cUpHeld = jobOn;
  }else{
    const {managed, jobOn} = cNameSay(cEditing);
    if (managed){ cUpHeld = false; return; }
    // Held on while a job is on it, so its name comes alive with the read
    // that has the job ended.
    cUpHeld = jobOn;
  }
  cLock(false);
  // An app's panel: its fields live, its file still the catalog's.
  if (!$("cByHandBar").hidden){
    $("cYml").readOnly = true;
    $("cAppFields").querySelectorAll("input,select").forEach(e => { e.disabled = false; });
    $("cByHand").disabled = false;
  }
}

async function openEditContainer(name){
  cEditing = name;
  cAppCur = null; cAppHand = false;
  $("cAppField").hidden = true;
  cAppOwns(false);
  $("cTabForm").hidden = false;
  $("cEnvHint").hidden = true;
  $("cTitle").textContent = "Edit " + name;
  $("cName").value = name;
  const {down, managed} = cNameSay(name);
  cUpHeld = !down && !managed;
  $("cNodeField").hidden = true;   // where it runs is not an edit either
  $("cUnderField").hidden = true;  // its project is changed on its row
  $("cYml").value = $("cEnv").value = "";
  $("cErrWrap").hidden = true;
  unbusy($("cGo"), "Save");
  cLock(!down || managed);
  cSeg("yml");
  $("cmodal").hidden = false;
  cHold();
  try{
    const j = await postJSON("/api/container", {action:"read", name}, {read: true});
    if (cEditing !== name) return;          // reopened on another one meanwhile
    $("cYml").value = j.compose || "";
    $("cEnv").value = j.env || "";
    // Made from an app (R238 step 3): Configure on its panel, each value
    // read back from its environment, the other variables alone below.
    if (j.app && !j.managed && !managed){
      $("cTitle").textContent = "Configure " + name;
      await loadNasApps();
      if (cEditing !== name) return;
      cAppDraw({...j.app, env: j.env || ""}, j.app.values || {});
      $("cTabForm").hidden = true;
      $("cEnv").value = j.app.extra || "";
      cAppOwns(true);
      cAppNewerSay(j.app);
      const locked = $("cGo").disabled;
      $("cAppFields").querySelectorAll("input,select").forEach(e => { e.disabled = locked; });
      $("cByHand").disabled = locked;
      cHold();
    }
    // Opened while the list was put away, it had no row to say AerieOS
    // manages it: the read says so (B810), and it is for reading.
    if (j.managed && !managed){
      $("cName").disabled = true;
      $("cNameHint").textContent = C_MANAGED;
      cLock(true);
      cUpHeld = false;
    }
  }catch(e){ $("cErr").textContent = "could not read it: " + e;
             $("cErrWrap").hidden = false; }
}

// A project's instance in the same dialog (the operator, 9 Oct: one Edit for
// the compose file and the env): the compose file is the project's own, in
// its tree, so saving it is an uncommitted change there; the env is the
// instance's. No form tab: the form writes a container from an image.
async function openEditInstance(project, instance){
  const key = {project, instance};
  cEditing = key;
  cAppCur = null; cAppHand = false;
  $("cAppField").hidden = true;
  cAppOwns(false);
  $("cTitle").textContent = "Edit " + projLabel(project) + (instance === "main" ? "" : ` (${instance})`);
  // Its own name, whatever its owner calls it (the operator, 11 Oct: not
  // tied to the project, since a project sends several), changed while it
  // is down like a written container's.
  const row = (dockerList?.instances || []).find(d => d.project === project && d.instance === instance);
  const running = !!row?.running;
  key.name = row?.name || "";
  $("cName").value = key.name;
  const jobOn = !!dmAhead(project, instance);
  $("cName").disabled = running || !key.name || jobOn;
  $("cNameHint").textContent = cInstanceSay(project, running, jobOn);
  cUpHeld = running || jobOn;
  $("cNodeField").hidden = true;
  $("cUnderField").hidden = true;
  $("cTabForm").hidden = true;
  $("cYml").value = $("cEnv").value = "";
  $("cErrWrap").hidden = true;
  unbusy($("cGo"), "Save");
  cLock(running);
  cSeg("yml");
  $("cmodal").hidden = false;
  cHold();
  try{
    const [c, e] = await Promise.all([
      postJSON("/api/devapp", {project, instance, action: "compose-get"}),
      postJSON("/api/devapp", {project, instance, action: "env-get"})]);
    if (cEditing !== key) return;           // reopened on another one meanwhile
    if (c.error || e.error) throw new Error(c.error || e.error);
    $("cYml").value = c.text || "";
    $("cEnv").value = e.text || "";
    // ...and what the Env button's dialog said: a box opened on the example
    // is a draft, and which keys the example declares that are not set.
    $("cEnvHint").textContent = (e.seeded ? "started from .env.example; nothing saved yet. " : "")
      + ((e.missing || []).length ? "missing against .env.example: " + e.missing.join(", ")
                                  : "everything .env.example declares is set");
    $("cEnvHint").hidden = false;
    // A seeded env is unsaved, so it is sent on Save even untouched.
    key.was = {compose: c.text || "", env: e.seeded ? null : (e.text || "")};
  }catch(err){ $("cErr").textContent = "could not read it: " + (err.message || err);
               $("cErrWrap").hidden = false; }
}

async function cSaveInstance(key){
  const fail = m => ($("cErr").textContent = m, $("cErrWrap").hidden = false);
  const {project, instance} = key, compose = $("cYml").value, env = $("cEnv").value;
  busy($("cGo"), "Saving");
  const send = body => postJSON("/api/devapp", {project, instance, ...body});
  try{
    // The compose file first: compose reads it before it is kept, and a file
    // it refuses stops here with its words, before the env is touched.
    const c = compose !== key.was?.compose ? await send({action: "compose-set", text: compose}) : {};
    if (c.error){ unbusy($("cGo"), "Save"); cSeg("yml"); return fail(c.error); }
    const e = env !== key.was?.env ? await send({action: "env-set", text: env}) : {};
    if (e.error){ unbusy($("cGo"), "Save"); cSeg("env"); return fail(e.error); }
    // ...and the name last, since the node carries the data under it.
    const typed = $("cName").value.trim();
    const n = typed && key.name && dockerSlug(typed) !== key.name ? await send({action: "rename", name: typed}) : {};
    if (n.error){ unbusy($("cGo"), "Save"); return fail(n.error); }
    $("cmodal").hidden = true;
    notify(n.job ? `renaming ${key.name} to ${n.name}: its row says when it is done`
           : c.ok || e.ok ? "saved: rebuild it to bring the change up" : "nothing changed");
    dockerList = null; readMoved("docker"); loadDocker();
  }catch(err){ unbusy($("cGo"), "Save"); fail("could not save: " + err); }
}

// Which project a new container belongs to: every project this account
// sees, no project first.
// The projects a container may be put under, sent from or moved to: the ones
// on this account's own list, for an administrator and the owner as for a
// user (the operator, 10 Oct). An administrator could add any project to
// their list first; offering the rest here is how a container lands under
// the wrong one by accident. `keep` is a row's current project, shown
// whatever it is so the picker does not misstate where the row is.
function myProjectNames(keep){
  const names = (state?.projects || []).filter(p => p.mine).map(p => p.name);
  if (keep && !names.includes(keep)) names.push(keep);
  return names.sort((a, b) => projLabel(a).localeCompare(projLabel(b), undefined, {sensitivity: "base"}));
}

function fillUnderSelect(sel, picked){
  const names = myProjectNames(picked);
  drawHTML(sel, optionList([["", "no space"], ...names.map(n => [n, projLabel(n)])], picked));
}

// The node follows the project picked: a container of a project belongs on
// the node that project's work runs on, and a person picking the project is
// not also asked to know which machine that is. A project with no node
// leaves the pick where it was.
function cUnderPicked(){
  const whose = $("cUnder").value;
  const row = state?.projects?.find(p => p.name === whose);
  const set = whose ? (row?.prefs?.nodes || []).filter(Boolean) : null;
  const hint = $("cNodeHint");
  if (whose && !set.length){
    $("cNodeField").hidden = false; $("cNode").innerHTML = ""; $("cNode").disabled = true;
    hint.hidden = false; hint.classList.add("bad");
    hint.textContent = projLabel(whose) + " has no node: set one in its settings first, and the container goes there.";
    $("cGo").disabled = true;
    return;
  }
  // No project: any node, the one the manager is looking at first. A
  // project: its nodes only, its primary first (R82).
  fillNodeSelect($("cNode"), $("cNodeField"), set ? set[0] : dockerNode, null, set);
  hint.hidden = !set; hint.classList.remove("bad");
  if (set) hint.textContent = set.length > 1 ? `One of ${projLabel(whose)}'s nodes.` : `${projLabel(whose)}'s node, where its sessions can reach it.`;
  $("cGo").disabled = false;
}

// Apps a NAS runs (R164 step 2, R238): the apps the Library holds, read
// once an open, and the panel New container draws for the one picked (the
// design's app-panel rule). The panel owns what the app declares: the
// Compose tab is its file as the catalog wrote it, read-only, and the
// Environment tab holds only the other variables.
let cApps = null;
let cAppRoots = [];       // the node's pools and shares a folder field suggests
let cAppRootsAt = null;   // ...read for this node
let cAppRouters = [];     // the model routers a router field can be given a key at (R238 step 7)
let cAppWant = "";        // the app the Library asked New container to open on (R170)
let cAppCur = null;       // the app on the panel: the Library's, or a container's own copy on Configure
let cAppHand = false;     // its definition was edited by hand, so its panel no longer applies
let cAppTaken = {names: [], ports: [], apps: []};  // every container's name, and the ports and apps those made from an app hold on the node read
// The Library's Install on an app (R170): New container with that app on
// its panel, as if the person had chosen it in a list.
function openNewContainerApp(id, node = ""){
  cAppWant = id;
  // ...on the Library's node when it runs Docker (R170 step 7).
  if (node) dockerNode = node;
  openNewContainer();
}
// `fresh` reads it again on the same node: a container made since holds a
// name and ports the next one is not offered.
async function loadNasApps(node = "", fresh = false){
  if (fresh || !cApps || cAppRootsAt !== node) await reading("nasapps", async () => {
    const j = await getJSON("/api/nasapps" + (node ? "?node=" + encodeURIComponent(node) : ""));
    cApps = j.apps || []; cAppRoots = j.roots || []; cAppRootsAt = node; cAppRouters = j.routers || [];
    cAppTaken = j.taken || {names: [], ports: [], apps: []};
  });
  return cApps;
}
// Another of the same app is a container of its own (the Library's rule:
// each press makes another): the app's id as its name, or id-2, id-3, the
// first no container has.
function cAppFreeName(id){
  const taken = new Set(cAppTaken.names || []);
  for (let n = 1; ; n++){ const x = n === 1 ? id : `${id}-${n}`; if (!taken.has(x)) return x; }
}
// ...and ports of its own: each the app's, or the first after it that no
// container made from an app on the node holds and no other field here
// was given. `given` is the ports handed out on this panel so far.
function cAppFreePort(p, given){
  let n = Number(p) || 0;
  if (!n) return "";
  const taken = new Set((cAppTaken.ports || []).map(Number));
  while ((taken.has(n) || given.has(n)) && n < 65535) n++;
  given.add(n);
  return String(n);
}

// Where a folder field suggests putting it: each of the node's places with
// the app's own folder under it (apps/immich), as the forms rule draws a
// path, a field with suggestions.
// The app's own folder is named for the container, so another of the same
// app has its own (apps/immich-2): the segment of the default that is the
// app's id is the container's name, as the name field holds it.
const cAppUnder = () => ($("cName").value || "").toLowerCase().replace(/[^a-z0-9]+/g, "-").replace(/^-+|-+$/g, "") || cAppCur?.id || "";
const cAppFolders = (f, as = cAppUnder()) => [...new Set(cAppRoots.map(r => {
  const d = (f.default || "").split("/").map(x => x === cAppCur?.id ? as : x).join("/");
  return d ? `${r.path}/${d}` : r.path;
}))];

// One field of the panel, as its kind's answer is drawn (the forms rule): a
// folder a path with suggestions, a port a number, a choice a pulldown, a
// switch a tick, a secret a masked field made for it when left empty.
function cAppFieldHtml(f, v, i){
  const id = `cAppF${i}`, at = `data-avar="${esc(f.var)}"`;
  const plain = `autocomplete="off" spellcheck="false"`;
  if (f.kind === "switch") return `<div class="fcell fwide"><label class="ndcap"><input type="checkbox" id="${id}" ${at}${
    String(v) === "true" ? " checked" : ""}> ${esc(f.label)}${helpIcon(f.help)}</label></div>`;
  // A model router (R238 step 7): the node whose router it uses, a key of
  // the container's own made there; dead, with why, where none is deployed.
  if (f.kind === "router"){
    const none = !cAppRouters.length;
    return formField(id, f.label, `<select id="${id}" ${at}${none ? " disabled" : ""}>${optionList(
      [...(f.required && !none ? [] : [["", "none"]]), ...cAppRouters.map(r => [r.node, `the router on ${r.name}`])], String(v))}</select>`,
      {help: f.help, hint: none ? "No model router is deployed: deploy one from a node's Installed page, and this app gets a key of its own there." : ""});
  }
  const o = {help: f.help, short: f.kind === "port"};
  return f.kind === "folder" ? formField(id, f.label, `<input id="${id}" ${at} ${plain} list="${id}L" value="${esc(v)}" placeholder="${esc(f.example || "/mnt/…/" + (f.default || ""))}"><datalist id="${id}L">${
        cAppFolders(f).map(x => `<option value="${esc(x)}"></option>`).join("")}</datalist>`, o)
    : f.kind === "port" ? formField(id, f.label, `<input id="${id}" ${at} type="number" min="1" max="65535" value="${esc(v)}">`, o)
    : f.kind === "choice" ? formField(id, f.label, `<select id="${id}" ${at}>${optionList((f.choices || []).map(c => [c.value, c.label]), String(v))}</select>`, o)
    : f.kind === "secret" ? formField(id, f.label, `<input id="${id}" ${at} type="password" autocomplete="new-password" value="${esc(v)}" placeholder="made for it when left empty" data-ph-short="made if empty">`, o)
    : formField(id, f.label, `<input id="${id}" ${at} ${plain} value="${esc(v)}" placeholder="${esc(f.example || "")}">`, o);
}

// The panel for app `a`: its head as its Library card's, its own fields in
// its manifest's order, then AerieOS's own its compose reads. `vals` are a
// container's values on Configure; a new one starts each field at its
// default and a folder at the first place the node offers.
function cAppDraw(a, vals = null){
  cAppCur = a; cAppHand = false;
  const v = vals || {}, own = a.own || [];
  const fresh = !vals;
  const row = {...a, kind: "app", label: a.name};
  drawHTML($("cAppHead"), `${libIcon(row)}<div class="aptitle"><b>${esc(a.name)}</b><span class="apby">${libPills(row)}</span></div>`);
  wireLibrary($("cAppHead"));
  $("cAppWhat").textContent = a.what || "";
  cAppNetSay(a, fresh);
  $("cAppGoing").hidden = !a.going;
  $("cAppGoing").textContent = a.going || "";
  // A folder with a default of its own (apps/immich) starts at the first
  // place the node offers; one with none (a library, a share's files) is
  // the person's to pick from the suggestions.
  // A port starts at the app's own, or the next free one where another
  // container holds it.
  const given = new Set();
  const start = f => !fresh ? (v[f.var] ?? (f.kind === "folder" ? "" : f.default ?? ""))
    : f.kind === "folder" ? (f.default && cAppFolders(f)[0] || "") : f.kind === "router" ? (cAppRouters[0]?.node || "")
    : f.kind === "port" ? cAppFreePort(f.default, given) : f.default ?? "";
  const ids = v.PUID !== undefined ? `${v.PUID}:${v.PGID ?? v.PUID}` : "1000:1000";
  const tz = v.TZ || Intl.DateTimeFormat().resolvedOptions().timeZone || "UTC";
  drawHTML($("cAppFields"), (a.fields || []).map((f, i) => cAppFieldHtml(f, start(f), i)).join("")
    + (own.includes("PUID") || own.includes("PGID") ? formField("cAppIds", "Runs as", `<input id="cAppIds" value="${esc(ids)}" autocomplete="off" spellcheck="false">`,
      {help: "uid:gid, the user that owns its folders: a share's files are written as it"}) : "")
    + (own.includes("TZ") ? formField("cAppTz", "Time zone", `<select id="cAppTz">${tzOptions(tz)}</select>`) : "")
    + (own.includes("PORT") ? formField("cAppPort", "Its port", `<input id="cAppPort" type="number" min="1" max="65535" value="${esc(v.PORT || (fresh ? cAppFreePort(a.port, given) : a.port))}">`,
      {help: "what it answers on, on the node; a hostname and a certificate for it are the node's nginx page", short: true}) : ""));
  // What a new one was offered, so a node or a name picked after moves
  // only what the person has not changed.
  if (fresh) $("cAppFields").querySelectorAll('input[data-avar], #cAppPort').forEach(e => { e.dataset.auto = e.value; });
  $("cAppField").hidden = false;
  $("cAppPanel").hidden = false;
  $("cAppLeft").hidden = true;
  $("cAppNewer").hidden = true;
}

// Another node picked for a new one: its places suggested in each folder
// field, and a folder still at the first place the last node offered moved
// to the first this one offers.
async function cAppNodePicked(){
  if (!cAppCur || cEditing !== null || cAppHand) return;
  await loadNasApps($("cNode").value);
  cAppFollow();
  cAppNetSay(cAppCur, true);
}
// An app on the machine's own network answers on its own port, not picked
// here; a new one where another of it already runs has nothing to answer
// on, which is said before Create refuses it.
function cAppNetSay(a, fresh){
  const host = a.network === "host";
  $("cAppNet").hidden = !host;
  $("cAppNet").textContent = !host ? "" : `On the machine's own network: it answers on port ${a.port} there, which is not picked here.${
    fresh && (cAppTaken.apps || []).includes(a.id) ? ` Another ${a.name} on this node already does, so make this one on another node.` : ""}`;
}
// The name typed on a new one: its folders follow it.
function cAppNameTyped(){
  if (cAppCur && cEditing === null && !cAppHand) cAppFollow();
}
// What a new one was offered and the person has not changed, offered again
// for the node and the name as they are now: each folder at the first place
// under the name, each port the first free one there.
function cAppFollow(){
  const given = new Set();
  (cAppCur.fields || []).forEach((f, i) => {
    const inp = $(`cAppF${i}`), list = $(`cAppF${i}L`);
    if (!inp) return;
    const mine = inp.dataset.auto !== undefined && inp.value === inp.dataset.auto;
    if (f.kind === "folder" && list){
      drawHTML(list, cAppFolders(f).map(x => `<option value="${esc(x)}"></option>`).join(""));
      if (mine && f.default) inp.value = inp.dataset.auto = cAppFolders(f)[0] || "";
    } else if (f.kind === "port" && mine) inp.value = inp.dataset.auto = cAppFreePort(f.default, given);
  });
  const p = $("cAppPort");
  if (p && p.dataset.auto !== undefined && p.value === p.dataset.auto) p.value = p.dataset.auto = cAppFreePort(cAppCur.port, given);
}

// A newer definition of the app in the Library than the one a container
// was made with (a Manifest update kept since): said on the panel, with the
// press that takes it on Save, any field it adds shown at its default.
function cAppNewerSay(a){
  const n = a.newer, box = $("cAppNewer");
  box.hidden = !n;
  if (!n) return;
  drawHTML(box, `The Library holds a newer ${esc(a.name)}${n.commit ? ` (${esc(n.commit.slice(0, 12))})` : ""} than this container was made with.
    <button type="button" class="link" id="cAppTake">Take it on Save</button>`);
  $("cAppTake").onclick = () => {
    const vals = {...(a.values || {}), ...cAppSent().values};
    cAppDraw({...a, fields: n.fields, own: n.own, take: true, newer: null}, vals);
    $("cYml").value = n.compose || $("cYml").value;
    cAppOwns(true);
    $("cAppNewer").hidden = false;
    drawHTML($("cAppNewer"), `Save moves it to ${esc(a.name)}'s newer definition; a field it adds starts at its default.`);
  };
}

// What the panel holds: {values, ids, tz, port}, as /api/container takes it.
function cAppSent(){
  const values = {};
  $("cAppFields").querySelectorAll("[data-avar]").forEach(e => { values[e.dataset.avar] = e.type === "checkbox" ? e.checked : e.value.trim(); });
  return {values, ids: $("cAppIds")?.value.trim() || "", tz: $("cAppTz")?.value || "", port: $("cAppPort") ? parseInt($("cAppPort").value, 10) || "" : ""};
}

// The Compose and Environment tabs while an app owns them: its file
// read-only with the one press that leaves it, and only the other
// variables to type.
function cAppOwns(on){
  const name = cAppCur?.name || "the app";
  $("cYml").readOnly = on || $("cGo").disabled;
  $("cByHandBar").hidden = !on;
  $("cImport").closest(".actbar").hidden = on;
  $("cByHandSaid").textContent = on ? `${name}'s file as the catalog wrote it. Its fields above fill it in.` : "";
  // Never a variable of its own as the example (the operator, 22 Nov: a
  // static site's empty box showed PUID and TZ, which it reads nothing of,
  // and the gray example was taken for its env): what a line is, in words.
  $("cEnv").placeholder = on ? "OTHER=value, one a line: what its fields above do not set" : "NAME=value, one a line: what the compose file reads as ${NAME}";
  $("cEnvHint").hidden = !on;
  if (on) $("cEnvHint").textContent = `The other variables for ${name}. Its fields above set the rest, and one of theirs typed here is refused by name.`;
}

// Edit the definition by hand (R238 step 3): one way, said first. The
// panel folds to a line and the compose file and environment become plain
// text with the values as they stood.
async function cAppByHand(){
  const a = cAppCur;
  if (!a) return;
  if (!await askYes(`Edit ${a.name}'s definition by hand? Its fields no longer apply: the compose file and the environment become plain text with the values as they stand now, and only Start over from the Library puts the fields back.`)) return;
  const sent = cAppSent();
  // A router field's address and key are the container's own as it has
  // them (Configure), or empty to fill by hand on a new one.
  const was = Object.fromEntries((a.env || "").split("\n").filter(l => l.includes("=")).map(l => [l.slice(0, l.indexOf("=")), l.slice(l.indexOf("=") + 1)]));
  const lines = [...(a.fields || []).flatMap(f => f.kind === "router" ? [`${f.var}=${was[f.var] ?? ""}`, `${f.key}=${was[f.key] ?? ""}`]
    : [`${f.var}=${sent.values[f.var] === true ? "true" : sent.values[f.var] === false ? "false" : sent.values[f.var] ?? ""}`]),
    ...(a.own || []).includes("PUID") ? [`PUID=${sent.ids.split(":")[0] || ""}`, `PGID=${sent.ids.split(":")[1] || ""}`] : [],
    ...(a.own || []).includes("TZ") ? [`TZ=${sent.tz}`] : [], ...(a.own || []).includes("PORT") ? [`PORT=${sent.port}`] : []];
  // A secret left empty on a new one is made here, so the text holds a value.
  const made = (a.fields || []).filter(f => f.kind === "secret" && !sent.values[f.var]).map(f => f.var);
  const env = lines.map(ln => made.includes(ln.split("=")[0]) ? `${ln}${cMakeSecret()}` : ln).join("\n") + "\n" + $("cEnv").value.trim();
  cAppHand = true;
  $("cEnv").value = env.trim() + "\n";
  $("cAppPanel").hidden = true;
  $("cAppLeft").hidden = false;
  drawHTML($("cAppLeft"), `Edited by hand: ${esc(a.name)}'s fields no longer apply. Start over from the Library puts them back.`);
  cAppOwns(false);
  $("cEnvHint").hidden = true;
  cSwitch("yml");
}
function cMakeSecret(){
  const b = new Uint8Array(18);
  crypto.getRandomValues(b);
  return btoa(String.fromCharCode(...b)).replace(/\+/g, "-").replace(/\//g, "_").replace(/=+$/, "");
}

function openNewContainer(){
  cLock(false);
  cEditing = null;
  cAppCur = null; cAppHand = false;
  $("cAppField").hidden = true;
  cAppOwns(false);
  // Only the app the Library opened this on: the catalog is browsed there.
  const want = cAppWant;
  cAppWant = "";
  if (want) loadNasApps(dockerNode, true).then(apps => {
    const a = apps.find(x => x.id === want);
    if ($("cmodal").hidden || !a || cEditing !== null) return;
    // Its name first: its folders are named for it.
    if (!$("cName").value) $("cName").value = cAppFreeName(a.id);
    cAppDraw(a);
    // Its file is the catalog's and its fields are above: no From an image.
    $("cTabForm").hidden = true;
    $("cYml").value = a.compose || "";
    cYmlTouched = true;
    cAppOwns(true);
    cSeg("yml");
    cHold();
  });
  $("cTabForm").hidden = false;
  $("cEnvHint").hidden = true;
  $("cName").disabled = false;
  $("cName").value = "";
  fillUnderSelect($("cUnder"), "");
  $("cUnderField").hidden = false;
  // Left EMPTY, both of them. The shape each wants is on the field as a
  // placeholder, which shows the same thing and cannot be submitted: seeded
  // as values, an example compose for a radarr nobody asked for was one
  // unread click from being created under whatever name was typed.
  $("cYml").value = $("cEnv").value = "";
  // Created on the node the manager is looking at, unless picked otherwise,
  // or a project is: cUnderPicked moves it to that project's node.
  const fillC = () => fillNodeSelect($("cNode"), $("cNodeField"), dockerNode,
    () => { if (cEditing === null && !$("cmodal").hidden) cUnderPicked(); });
  fillC();
  $("cNodeHint").hidden = true;
  $("cErrWrap").hidden = true;
  unbusy($("cGo"), "Create");
  for (const id of ["cImage", "cPorts", "cVols", "cEnvLines"]) $(id).value = "";
  $("cRestart").value = "unless-stopped";
  cYmlTouched = false;
  // The form first: an image and a port is what most of these are, and the
  // compose file it writes is one tab away for everything else.
  cSeg("form");
  $("cNameHint").textContent =
    "A name no other container has.";
  $("cmodal").hidden = false;
  cHold();
}

// A compose file from the person's disk (the operator, 10 Nov: the old
// system's containers come as a zip of them): its text in the Compose pane,
// and the name its file has when none is typed.
async function cImportPicked(){
  const inp = $("cImportFile"), f = inp.files?.[0];
  inp.value = "";
  if (!f) return;
  const fail = m => { $("cErr").textContent = m; $("cErrWrap").hidden = false; };
  if (/\.zip$/i.test(f.name)) return fail(`${f.name} is a zip: unzip it and import one of its files`);
  if (f.size > 200000) return fail(`${f.name} is over 200 kB, more than a compose file holds`);
  const text = await f.text().catch(() => null);
  if (text === null) return fail(`${f.name} could not be read`);
  $("cErrWrap").hidden = true;
  $("cYml").value = text;
  cYmlTouched = true;
  const base = f.name.replace(/\.(ya?ml|json|txt)$/i, "");
  if (!$("cName").disabled && !$("cName").value.trim() && !/^(docker-)?compose([.-]override)?$/i.test(base)) $("cName").value = base.slice(0, 60);
  cSwitch("yml");
}

let cTab = "yml";                 // which pane the segment is showing

function cSeg(which){
  cTab = which;
  segPick(["cTabForm", "cTabYml", "cTabEnv"], {form: "cTabForm", yml: "cTabYml", env: "cTabEnv"}[which]);
  $("cFormField").hidden = which !== "form";
  $("cYmlField").hidden = which !== "yml";
  $("cEnvField").hidden = which !== "env";
}

// Once the compose file has been edited by hand the form stops writing it:
// a generator that overwrites what somebody typed is a generator that eats
// work. Reset on every open.
let cYmlTouched = false;

// The form's answer, as the compose file it stands for. Written here rather
// than on the server because what is about to be created should be readable
// before it is: the Compose tab shows exactly the text that will be saved,
// and the server still checks it with compose itself before writing it.
function cFormYaml(){
  const lines = l => l.split("\n").map(x => x.trim()).filter(Boolean);
  const image = $("cImage").value.trim();
  const ports = lines($("cPorts").value), vols = lines($("cVols").value);
  const env = lines($("cEnvLines").value), restart = $("cRestart").value;
  if (!image) return "";
  // Quoted, every one of them: a port reads as a base-60 number in YAML
  // ("7878:7878" is a sexagesimal literal to a YAML 1.1 parser), and a value
  // with a colon or a space in it needs quoting anyway. Double quotes with
  // the two escapes that matter inside them.
  const q = v => `"${String(v).replace(/\\/g, "\\\\").replace(/"/g, '\\"')}"`;
  const block = (key, xs) => xs.length
    ? `\n    ${key}:\n` + xs.map(x => `      - ${q(x)}`).join("\n") : "";
  return `services:\n  app:\n    image: ${q(image)}\n    restart: ${restart}`
    + block("ports", ports) + block("volumes", vols) + block("environment", env) + "\n";
}

function cFormWrote(){
  if (cYmlTouched) return;
  $("cYml").value = cFormYaml();
}

// Switching between them moves the way the New project dialog's source picker
// does: the incoming pane slides in from its own tab's side (Compose is the
// left tab, Environment the right), same 220ms ease, same reduced-motion gate.
// One vocabulary for every two-tab switch on the page; see pSlide, which is
// this in the other dialog. Not called from cSeg: an open draws its first pane
// rather than switching to it, and sliding on arrival would animate a dialog
// that is already animating itself in.
function cSlide(which){
  if (noMotion()) return;
  $({form: "cFormField", yml: "cYmlField", env: "cEnvField"}[which]).animate(
    [{transform: `translateX(${
        {form: -18, yml: 0, env: 18}[which] >= 0 ? "18px" : "-18px"})`, opacity: 0},
     {transform: "none", opacity: 1}],
    {duration: 220, easing: "ease"});
}

const cSwitch = w => { if (cTab === w) return; cSeg(w); cSlide(w); };
// One size whichever pane is on show (holdPanes): the ones this open offers.
function cHold(){
  const keys = [["form", "cTabForm"], ["yml", "cTabYml"], ["env", "cTabEnv"]].filter(([, id]) => !$(id).hidden).map(([k]) => k);
  holdPanes($("cmodal").querySelector(".box"), keys, cSeg, cTab);
}

async function cSubmit(){
  if (cEditing && typeof cEditing === "object") return cSaveInstance(cEditing);
  const fail = m => ($("cErr").textContent = m, $("cErrWrap").hidden = false);
  const editing = cEditing, verb = editing ? "Save" : "Create";
  if (!$("cName").value.trim()) return fail("a name is needed");
  busy($("cGo"), editing ? "Saving" : "Creating");
  try{
    // An app's panel sends its values, and its file stays the catalog's
    // (R238 step 3); edited by hand, what was typed is the container.
    const app = cAppCur && !cAppHand ? {app: cAppCur.id, ...cAppSent(), ...(cAppCur.take ? {newer: true} : {})}
      : cAppCur && editing ? {by_hand: true} : {};
    const j = await postJSON("/api/container", {action: editing ? "save" : "create",
                            name: editing || $("cName").value,
                            ...(editing && $("cName").value.trim() && $("cName").value.trim() !== editing
                                ? {rename: $("cName").value.trim()} : {}),
                            node: editing ? "" : ($("cNodeField").hidden
                              ? (dockerNode || "") : $("cNode").value),
                            owner: editing ? "" : $("cUnder").value,
                            compose: $("cYml").value, env: $("cEnv").value, ...app});
    if (j.error){
      unbusy($("cGo"), verb);
      // Compose's own complaint, which names the line: shown on the tab the
      // text is on, since that is where it has to be fixed. An app's panel
      // says its own above, where its fields are.
      if (!app.app) cSeg("yml");
      return fail(j.error);
    }
    $("cmodal").hidden = true;
    if (!editing){
      notify(`${j.name} is in the manager: press Build to bring it up`);
      // Shown on the node it was made on, which the picker may have moved
      // off the one on screen (B62).
      const made = $("cNodeField").hidden ? "" : $("cNode").value;
      if (made && made !== dockerNode){ openDockerOn(made); return; }
      dockerList = null; readMoved("docker"); loadDocker();
      return;
    }
    if (j.job && j.name && j.name !== editing){
      notify(`renaming ${editing} to ${j.name}: its row says each step, then Build it`);
      dockerList = null; readMoved("docker"); loadDocker();
      return;
    }
    // Saved. If it has been built, the change is on disk and not in the
    // running container: a state worth resolving now rather than leaving for
    // the row to hint at, because the gap between "I edited it" and "it is
    // running what I edited" is where the confusion lives. Asked rather than
    // done: a rebuild takes it down and brings it up, which is not something
    // to start on somebody's behalf because they pressed Save.
    const row = (dockerList?.instances || []).find(
      d => d.project === editing && d.instance === "main");
    dockerList = null; readMoved("docker"); loadDocker();
    if (row?.built_rev && await askYes(
          `${editing} is saved. Rebuild it now so the change takes effect?\n\n`
          + `Cancel keeps the change on disk for a later Rebuild.`)){
      dmAction(editing, "main", "rebuild", null);
      return;
    }
    notify(`${editing} saved: ${j.note || "rebuild it to bring the change up"}`);
  }catch(e){ unbusy($("cGo"), verb);
             return fail("could not create it: " + e); }
}

// How a job ENDED, in one line: the LAST non-empty line of its error, not the
// first.
//
// These errors are "<what failed>:\n<the tool's own output>", kept from the
// END (devapp's `("up failed:\n" + out)[-500:]`), so the first line is the
// LABEL and the row showed "up failed:" with docker's actual reason dropped.
// That is the same mistake the agent made printing a dead toolchain's first
// line: ".NET said: Process terminated." and nothing of the sentence after
// it that named the missing library. Where an error is one line, the first
// and the last are the same line and nothing changes.
function jobWhy(err){
  const lines = String(err || "").split("\n").map(l => l.trim()).filter(Boolean);
  return lines.length ? lines[lines.length - 1] : "";
}

// What a build was made FROM, in the row's own words.
//
// The ref here is the one stamped AT BUILD TIME, never the Ref line's value.
// That line is the setting for the next build, and repointing an instance does
// not rebuild it, so reading the setting to describe what is already built
// says "built from rack-drift 244e38d" about a branch that may never have been
// built here at all. The commit is the truth; the branch is the setting, and
// the moment the two disagree is the moment this line is worth reading.
function dmBuilt(d){
  return `built from ${d.built_ref ? esc(d.built_ref) + " " : ""}${
    esc(d.built_rev)}`;
}

// What one dev instance is doing, in a line: the action bar's status.
function dmState(d, job, mine, busy, blind){
  // A job in flight on this row is known whatever the listing says: its
  // phase comes from the job, not from the daemon.
  if (busy) return esc(job.step || "working") + '<span class="dots"></span>';
  // Nothing was asked, so nothing is claimed. What it was built from is still
  // true (that is a record on this side) and it is the one fact worth
  // carrying into a listing nobody can act on.
  if (blind)
    return d.built_rev
      ? `${dmBuilt(d)}: the daemon is not answering, so whether it is up is
         unknown`
      : "never built: the daemon is not answering";
  // How a job ENDED, which this row never said. A build that failed or was
  // stopped left the row showing the state it happened to be in, so the only
  // account of what went wrong was in the tail below it, and an abort, which
  // ends a job on purpose, said nothing at all.
  if (mine && job.error) return esc(jobWhy(job.error));
  if (d.interrupted && !d.running)
    return `a build was interrupted: AerieOS restarted while it was running${
      d.built_rev ? `; still on ${esc(d.built_rev)}` : ", and nothing was built"}`;
  // The pill on the name says it is running; this says how many, worded.
  if (d.running) return `${d.containers} container${d.containers === 1 ? "" : "s"} up`;
  if (d.exists) return "stopped: its containers are still there";
  if (d.built_rev) return `${dmBuilt(d)}, not running`;
  return "never built";
}

// A port only this node's nginx reaches (127.0.0.1 on a node whose ports
// stay on it) and no nginx route points at: the container answers nowhere
// until one does, which is the step a first move to a VPS missed (the
// operator, 11 Oct). Said under the row, with the way to the nginx tab.
function dmUnrouted(d){
  if (!dockerList?.ports_local || d.owner === "System" || !d.running) return "";
  const routed = new Set(dockerList.nginx_ports || []);
  const loop = (d.ports || []).map(p => /^127\.0\.0\.1:(\d+)->/.exec(p)?.[1]).filter(Boolean).map(Number)
    .filter(p => !routed.has(p));
  if (!loop.length) return "";
  return `<div class="sub dmunrouted">${loop.join(", ")} ${loop.length === 1 ? "is" : "are"} reachable only through this node's nginx, and no route points ${
    loop.length === 1 ? "at it" : "at them"} yet: <a href="#" data-dmnginx="${esc(dockerList.node || "")}">add a route on the nginx page</a></div>`;
}

// A hosting-only node runs no terminal, so its containers draw no Shell, and
// the page says so once on its status line rather than under every row: it
// is the node's policy, not a fault (the operator, 22 Oct). The controller's
// own machine is the same, its container terminal being the job account's.
function dmHostOnly(){
  const n = (nodesList || []).find(x => x.id === (dockerList?.node || dockerNode));
  return n?.config?.host_only || n?.config?.own ? n : null;
}
// A shell inside one of the instance's running containers, in the dock
// (R218 step 4): why it cannot open here, or "" when it can, said under the
// row as a setting switched off (warn), never red; the server asks the same
// questions again, and of the daemon, before anything runs (_ctr_refused).
function dmShellWhy(d){
  const owner = d.owner || d.project;
  if (!state?.admin && (state?.projects || []).find(p => p.name === owner)?.prefs?.devbuild === "deny")
    return `${projLabel(owner)}'s Agents may: Run its container is Deny, so a shell in its containers is an administrator's`;
  return "";
}
function dmShell(project, instance, ctr){
  openTab({kind: "term", arg: `ctr:${project}:${instance}:${ctr}`, label: `in ${ctr}`});
}

// What a row's pill says while its job runs, by the job's action.
const DM_JOB_WORD = {rebuild: "rebuilding", up: "starting", down: "stopping", update: "updating", remove: "removing",
                     rename: "renaming", unpack: "unpacking", "relocate-unpack": "unpacking",
                     "relocate-out": "sending", "relocate-in": "arriving"};

function dmRowsHtml(ins, job, blind){
  return ins.map(d => {
    // Explicitly running: dockerJob() keeps a finished job around now so the
    // row can say how it ended, and "busy" must not follow it there: a
    // stopped build would otherwise keep its Abort and its ghosted buttons
    // forever.
    const mine = job && job.project === d.project && job.instance === d.instance;
    const busy = !!(mine && job.running);
    // A press on it not yet answered (dmGo): its word until the job says
    // its own, and an Abort pressed reads Stopping at once.
    const pend = dmGoing.get(`${d.project}|${d.instance}`) || "";
    const going = !busy && pend !== "abort" ? pend : "";
    // ...and the button it came from stays dead till then, drawn so: a
    // redraw gives back what a press did to a button by hand.
    const held = a => going === a ? " disabled" : "";
    // AerieOS's own nginx (System's, R180): what a person changes about
    // it is the nginx tab's, and Deploy there makes it again, so its row
    // keeps Up, Down, Remove and the image update and loses Edit, Rebuild
    // and Copy or move (the operator, 13 Oct; R207).
    const managed = d.owner === "System";
    // A one-shot that ran and exited 0 (a seed, a migration) has done its
    // job: it is neither up nor down, and counting it as down said an
    // instance was partly up when nothing was wrong (B147).
    const finished = c => c.state === "exited" && /^Exited \(0\)/.test(c.status || "");
    const live = (d.services || []).filter(c => !finished(c));
    // The state is a pill on the name line (R210): a word in the level's
    // color, not a parenthesis in the dim mono the facts under it wear.
    const partly = !blind && d.running && live.some(c => c.state !== "running");
    // Docker's own health, read off the status it prints (R216): one
    // container unhealthy and the row says so; all of them healthy and it
    // says that rather than running; one still starting is said too.
    const hl = live.map(dmHealth).filter(Boolean);
    // A row whose job is running knows what it is doing whatever the
    // daemon said: a Rebuild read "state unknown" over its own "stopping"
    // while its node was busy with it (B65). So does one whose press is on
    // its way, from the click (the operator, 22 Nov), and the job's word
    // goes on from there rather than the daemon's "running" coming back
    // for the seconds a Down takes.
    const st = busy ? [DM_JOB_WORD[job.action] || "working", "warn"]
      : going ? [DM_JOB_WORD[going] || "working", "warn"]
      : blind ? ["state unknown", ""]
      : partly ? [`partly up: ${live.filter(c => c.state === "running").length} of ${live.length}`, "warn"]
      : d.running && hl.includes("unhealthy") ? ["unhealthy", "bad"]
      : d.running && hl.includes("starting") ? ["starting", "warn"]
      : d.running && hl.length && hl.every(h => h === "healthy") ? ["healthy", "ok"]
      : d.running ? ["running", "ok"] : d.exists ? ["stopped", "off"] : ["down", "off"];
    // Its running containers, for the Shell (R218 step 4), and why one
    // cannot open, said under the row.
    const shellAt = !blind && mayShell() && mayDocker() && !dmHostOnly() && (d.services || []).filter(c => c.state === "running").length
      ? (d.services || []).filter(c => c.state === "running") : null;
    const shellWhy = shellAt ? dmShellWhy(d) : "";
    const key = `inst:${d.project}|${d.instance}`;
    const many = (d.services || []).length > 1;
    // The head (the operator's concept, 17 Oct): the name, its pill and how
    // long it has been up, one mono line of what it is (its image, the
    // commit it was built from, its compose file), and at the right its
    // buttons, Open the main one where it answers somewhere.
    const meta = !blind && d.running && !busy && !going && !(mine && job.error)
      ? [dmUptime(d.services), `${d.containers ?? (d.services || []).length} container${(d.containers ?? (d.services || []).length) === 1 ? "" : "s"}`].filter(Boolean).join(" · ")
      : "";
    // ...and one queued behind its job, said after that job's step.
    const q = busy ? dmQueued.get(`${d.project}|${d.instance}`) : null;
    const queued = q && q.behind === job.id ? `<span class="dim"> · ${esc(DM_VERB[q.act] || q.act)} queued behind it</span>` : "";
    const said = meta ? "" : going ? `${esc(DM_JOB_WORD[going] || "working")}<span class="dots"></span>` : dmState(d, job, mine, busy, blind) + queued;
    const origin = [
      !many && d.services?.[0]?.image ? dmImage(d.services[0].image) : "",
      d.built_rev ? `@ ${esc(String(d.built_rev).slice(0, 7))}` : "",
      d.compose_path ? esc(d.compose_path) : d.source === "file" ? "written here" : "",
    ].filter(Boolean).join(`<span class="sep"></span>`);
    const open = !blind && d.running ? dmOpenLink(d) : "";
    const inner = `
      <div class="grow">
        <div class="dmhead">
        <div class="dmid">
        <div class="name">${esc(d.name)}<span class="pill stat dmpill${st[1] ? " " + st[1] : ""}${
            !blind && d.running && st[1] === "ok" ? " live" : ""}">${
            esc(st[0])}${dockerList?.stale && !blind ? ", as last seen" : ""}</span>${
            meta ? `<span class="dmmeta state">${esc(meta)}</span>` : ""}</div>
        ${origin ? `<div class="sub data dmorigin">${origin}</div>` : ""}
        ${said ? `<div class="sub dmstate state${
          // A job that failed is said in the bad tone even while the old
          // container still runs (B96: a failed Rebuild read in green).
          mine && job.error && !busy ? " bad" : !blind && d.running ? " ok" : ""}">${said}</div>` : ""}
        </div>
        <div class="actbar dmacts">
        ${open}
        ${dmConfigureBtn(d)}
        ${!mayDocker() ? "" : `${d.running ? "" : `<button type="button" class="primary" data-dm="up" ${
          (d.missing_env || []).length || going === "up" ? "disabled" : ""}
          title="${(d.missing_env || []).length
            ? "the env is missing " + esc(d.missing_env.join(", "))
            : !d.built_rev
              ? "Start it: docker compose up -d, which builds the image first, as compose does"
              : "Start it: docker compose up -d"}">Up</button>`}
        ${shellAt ? `<button type="button" data-dmshell="${esc(shellAt[0].name)}"${shellWhy ? " disabled" : ""}
          title="a shell inside ${esc(shellAt[0].service || shellAt[0].name)}, in the dock">Shell</button>` : ""}
        ${(d.images_behind || []).length ? `<button type="button" data-dm="update"${held("update")}
          title="pull the newer images and start it again: docker compose pull, then up -d">Update</button>` : ""}
        ${d.nginx_to ? `<button type="button" data-dm="nginx-update"
          title="pin the image's digest on the nginx page's record and rebuild with it">Update</button>` : ""}
        `}
        ${busy ? abortBtn('data-dm="abort"', job.aborting || pend === "abort", "stop this build; what is already built is kept") : ""}
        ${managed || !mayDocker() ? "" : `<button type="button" data-dm="rebuild" ${
          // A button that refuses is not information: a rebuild when nothing
          // moved is a cached build and a restart, behind a confirm that
          // says so; one pressed while a job runs queues behind it.
          held("rebuild")}
          title="${!d.built_rev
            ? "build the first image, then bring it up"
            : d.changed
              ? "build from " + esc(d.ref || d.project) + "'s codebase, then down and up"
              : (mine && job.error)
                ? "run it again: the last attempt did not finish"
                : "the last build is current; this builds it again anyway"}">${
          d.built_rev ? "Rebuild" : "Build"}</button>`}
        ${!mayDocker() ? "" : `<button type="button" data-dm="down" ${!d.exists || going === "down" ? "disabled" : ""}
          title="Stop it and remove its containers: docker compose down">Down</button>`}
        ${
        // Open, Shell, the build and Down are what a row is for; the rest
        // goes behind ⋯ (R210), Remove last in there as it was last on the bar.
        actMore([
          dmEditBtn(key),
          // Its log in a tab of the dock (the operator, 26 Oct: every log
          // opens there), one per container of a stack.
          ...(d.exists && !blind && mayDocker() ? (d.services || []).filter(c => c.name).map(c => `<button type="button" data-dmlog="${esc(c.name)}"
            data-running="${c.state === "running" ? 1 : 0}" title="what ${esc(c.service || c.name)} prints, in a tab of the dock, read again as it goes on">${
              many ? `Log of ${esc(c.service || c.name)}` : "Log"}</button>`) : []),
          ...(shellAt && !shellWhy ? shellAt.slice(1).map(c => `<button type="button" data-dmshell="${esc(c.name)}"
            title="a shell inside ${esc(c.service || c.name)}, in the dock">Shell in ${esc(c.service || c.name)}</button>`) : []),
          // One made from an app is configured on that app's panel (R238).
          managed || !mayDocker() ? "" : `<button type="button" data-dm="edit" data-src="${d.source === "file" ? "file" : "project"}"
            title="${d.app ? `${esc(d.app)}'s fields, as its panel asks for them, with its compose file and env`
                    : d.source === "file" ? "edit this container's compose file and env"
                    : "edit the space's compose file and this container's env"}">${d.app ? "Configure" : "Compose and env"}</button>`,
          !mayDocker() || managed ? "" : `<button type="button" data-dmrel ${busy || d.relocating?.busy ? "disabled" : ""}
            title="to another node, its data with it: a copy beside it, or this one moved">Copy or move…</button>`,
          // Live while a job runs: the server queues it behind that one.
          !mayDocker() ? "" : `<button type="button" class="danger" data-dm="remove" ${
            going === "remove" ? "disabled" : ""}
            title="take it down and drop it from this list; its env and data stay for a remake">Remove</button>`])}
        </div>
        </div>
        ${
        // What it uses: one band of four for a container, a table of its
        // services for a stack (the tables rule), each with its own use.
        blind ? "" : many ? dmServicesTable(d, finished) : dmStatStrip(d)}
        ${d.relocating ? `<div class="sub ${d.relocating.busy ? "" : d.relocating.archive ? "note" : "bad"} dmreloc">${esc(d.relocating.line)}${
          d.relocating.busy ? '<span class="dots"></span>'
          : d.relocating.archive && mayDocker() && !busy && !going ? ` <a href="#" data-dmunpack>unpack it now</a>`
          : d.relocating.archive && mayDocker() && busy ? `<span class="dim">: unpack it once this job has ended</span>` : ""}</div>` : ""}
        ${
        // The notices, each a line (the words rule): what is wrong and the
        // one thing to do about it.
        d.astray ? `<div class="sub warn dmastray">Out of reach: ${esc(projLabel(d.owner || d.project))}'s sessions run on ${
          esc(d.astray)}, which does not host its containers. Tick this node under the space's Also works on, or Remove it and send it again.</div>` : ""}
        ${
        // What a job at work holds back, said where the row is (a dead
        // control says why on its row): the server refuses a copy or move
        // until it has ended, where Up, Down and the rest queue behind it.
        busy && mayDocker() && !managed && !d.relocating?.busy ? `<div class="sub dim dmwait">Copy or move waits for this job to end.</div>` : ""}
        ${d.await_env ? `<div class="sub warn">built: fill in the env, then Up</div>`
          : (d.missing_env || []).length ? `<div class="sub warn dmenv">the env is missing ${esc(d.missing_env.join(", "))}: press Env</div>` : ""}
        ${d.nginx_to ? `<div class="sub warn dmnginx">${esc(d.nginx_to)} is out: Update pins it and rebuilds</div>` : ""}
        ${shellWhy ? `<div class="sub warn dmshellwhy">No shell here: ${esc(shellWhy)}</div>` : ""}
        ${dockerList?.ports_local && (d.open_ports || []).length ? `<div class="sub bad dmopen">${esc(d.open_ports.join(", "))} ${
          d.open_ports.length === 1 ? "is" : "are"} published on every address of this node, so the internet reaches ${
          d.open_ports.length === 1 ? "it" : "them"} past nginx: ${dmOpenWhy(d, d.open_ports.length === 1 ? "it" : "them")}</div>`
          : dockerList?.ports_local && d.open_from && !d.exists ? `<div class="sub warn dmopen">${dmOpenSoon(d)}</div>` : ""}
        ${dmUnrouted(d)}
        ${(d.images_behind || []).length ? `<div class="sub warn dmimages">a newer ${esc(d.images_behind.join(", "))} is out: Update pulls it and starts it again</div>` : ""}
        ${(d.images_said || []).map(s => `<div class="sub warn" data-imagesaid>${esc(s)}</div>`).join("")}
        ${
        // Its settings, read as pills; Edit settings, behind ⋯, opens them
        // in a dialog with Cancel and Apply (the operator, 17 Oct); a row
        // with a setting staged keeps it open.
        dmSetPills(dmInstPills(d, managed))}
        ${dmEditing.has(key) || dmRowDirty(key)
          ? dmSetDialog(d.name, key, [dmOwnerLine(d, key), dmMoveLine(d, busy), dmRefLine(d), dmOverrideLine(d), dmGpuLine(d), dmRouteLine(d),
                       dmNginxLine(d), d.exists ? dmBootLine(d.name, !!d.boot) : "", d.exists ? dmLanLine(d.name, !!d.lan) : ""]) : ""}
      </div>
      ${docSection("docker", `wire:${d.project}|${d.instance}`,
                   "Ports and mounts", dmPortsSaid(d),
                   `<div class="wire" data-own>${skel("rows", 2, "reading…")}</div>`, {open: false})}
`;
    return dmRowWrap(d, st, inner, blind);
  }).join("");
}

// Docker's health for one container, off the status it prints ("Up 3
// weeks (healthy)"): healthy, unhealthy, starting, or "" for none.
function dmHealth(c){
  const t = c.status || "";
  return /\(healthy\)/.test(t) ? "healthy" : /\(unhealthy\)/.test(t) ? "unhealthy" : /health: starting/.test(t) ? "starting" : "";
}

// Cards or a list (R216, the operator's second set of examples): the same
// card either way, drawn whole as a row, or behind one line that opens
// into it (rows-you-open). Which, is this browser's, kept in localStorage.
let dmView = (() => { try{ return localStorage.getItem("bb.dmview") === "list" ? "list" : "cards"; }catch(e){ return "cards"; } })();
// In list view each project's group is a table (R218 step 8, the tables
// rule): the container, its state, whose it is, where it answers (its
// published ports as links, the address nginx routes to it) and its image,
// each line opening into the card.
const DM_COLS = [{label: "Container"}, {label: "State", w: "8.5rem"}, {label: "Space", w: "minmax(0,.7fr)"},
                 {label: "Ports", w: "minmax(0,.6fr)"}, {label: "Address", w: "minmax(0,.9fr)"},
                 {label: "Image", w: "minmax(0,1.2fr)"}];
function dmLineWrap(key, cls, cells, inner){
  return `<details class="row stack2 dmline${cls}" ${key}${sectAttr(`docker:line:${key.replace(/^data-\w+="|"$/g, "")}`)}>
    ${tblLine(DM_COLS, cells, "summary", "dmsum")}
    <div class="dmbody">${inner}</div></details>`;
}
function dmRowWrap(d, st, inner, blind){
  const key = `${d.project}|${d.instance}`;
  if (dmView !== "list")
    return `<div class="row stack2${blind ? " off" : ""}" data-inst="${esc(key)}">${inner}</div>`;
  return dmLineWrap(`data-inst="${esc(key)}"`, blind ? " off" : "", dmLineCells(d, st), inner);
}

// The line's cells: whose it is, where it answers and its image.
function dmLineCells(d, st){
  const who = d.owner || d.project;
  const imgs = [...new Set((d.services || []).map(c => (c.image || "").replace(/@sha256:.*$/, "")).filter(Boolean))];
  return [`<span class="name">${esc(d.name)}</span>`,
          `<span class="pill stat dmpill${st[1] ? " " + st[1] : ""}">${esc(st[0])}</span>`,
          who ? esc(dmOwnerSaid(who)) : "",
          dmPorts(d).map(p => dmPortLink(p.pub)).join(" "),
          dmRoutesOf(d).map(dmRouteLink).join(" "),
          imgs.map(dmImage).join(", ")];
}

// The published ports of an instance: [{pub, target, proto, svc}].
function dmPorts(d){
  const out = [];
  const take = (text, svc) => {
    const m = /(?:^|:)(\d+)->(\d+)\/(\w+)/.exec(text || "");
    if (m && !out.some(p => p.pub === m[1])) out.push({pub: m[1], target: m[2], proto: m[3], svc});
  };
  if ((d.services || []).length > 1) d.services.forEach(c => (c.ports || []).forEach(p => take(p, c.service || c.name)));
  else (d.ports || []).forEach(p => take(p, ""));
  return out;
}

// A published port as the address it answers at (R216): the daemon's
// host, which the row's Reached at line already names.
const dmPortLink = pub => `<a href="http://${esc(daemonHost())}:${esc(pub)}/" target="_blank" rel="noreferrer">${esc(pub)}</a>`;

// Why a row publishes on every address of a node whose ports stay on it
// (R217), and what puts it right: its compose file names 0.0.0.0, by a
// variable defaulting to it (set in the env) or written in; or nothing in
// the file says so, and the container was made before the node's setting.
function dmOpenWhy(d, them){
  const f = d.open_from;
  if (f?.vars?.length)
    return `${esc(f.vars.join(", "))} default${f.vars.length === 1 ? "s" : ""} to 0.0.0.0 in its compose file, which wins over this node's setting; set ${
      f.vars.length === 1 ? "it" : "them"} to 127.0.0.1 under Env, then Down and Up`;
  if (f?.literal)
    return `0.0.0.0 is written into its compose file, which wins over this node's setting; change it there to 127.0.0.1, or leave the address out, then Down and Up`;
  return `Down and Up binds ${them} to 127.0.0.1`;
}
function dmOpenSoon(d){
  const f = d.open_from;
  return f.vars?.length
    ? `when it comes up, ${esc(f.vars.join(", "))} default${f.vars.length === 1 ? "s" : ""} to 0.0.0.0 in its compose file and its ports publish on every address of this node past nginx: set ${
        f.vars.length === 1 ? "it" : "them"} to 127.0.0.1 under Env first`
    : `when it comes up, 0.0.0.0 in its compose file publishes its ports on every address of this node past nginx: change it there to 127.0.0.1 first`;
}

// The nginx routes on this node that point at one of the row's published
// ports (manager_view's nginx.routes), and each as a link.
function dmRoutesOf(d){
  const mine = new Set(dmPorts(d).map(p => +p.pub));
  return (dockerList?.nginx?.routes || []).filter(r => mine.has(+r.port));
}
const dmRouteLink = r => {
  const host = r.host && r.host !== "*" ? r.host : daemonHost();
  const url = `${r.tls ? "https" : "http"}://${host}${r.path || "/"}`;
  return `<a href="${esc(url)}" target="_blank" rel="noreferrer">${esc(host + (r.path && r.path !== "/" ? r.path : ""))}</a>`;
};

// The Images and volumes section: tiles of what the daemon holds and
// what a prune would give back, then each image (in use or not, its size
// and age) and each volume, and the two prunes on the action bar.
// A fold's loader fills whichever element holds its key when the answer
// lands: the list redraws on every revision, and the fold a read was
// started in is often not the fold on the page by the time it ends.
const DM_IMG_COLS = [{label: "Image"}, {label: "State", w: "6.5rem"}, {label: "ID", w: "8rem"},
                     {label: "Size", w: "6rem", num: true}, {label: "Created", w: "minmax(0,.6fr)"}];
const DM_VOL_COLS = [{label: "Volume"}, {label: "Driver", w: "8rem"}];
const dmFoldNow = key => document.querySelector(`:is(.dmtab, .dkview) details[data-sect="${CSS.escape(key)}"]`);
function loadDockerImages(det){
  const key = det.dataset.sect;
  if (!key) return Promise.resolve();
  return reading("docker.images:" + key, () => dockerImagesRead(key));
}
async function dockerImagesRead(key){
  const node = dockerList?.node || dockerNode || "";
  const j = await getJSON("/api/docker/images" + (node ? "?node=" + encodeURIComponent(node) : ""));
  const det = dmFoldNow(key);
  const box = det?.querySelector(".dmimgbox");
  if (!det || !box) return;
  if (j.error){ drawHTML(box, `<div class="hint bad">${esc(j.error)}</div>`); return; }
  const df = k => (j.df || []).find(x => x.kind === k) || {};
  const unused = (j.images || []).filter(i => !i.used).length;
  const dang = (j.images || []).filter(i => i.dangling).length;
  // The section's status, once there is one: docSection draws none for "".
  let st = det.querySelector(":scope > summary .sst");
  if (!st){ st = document.createElement("span"); st.className = "sst"; st.setAttribute("data-own", ""); det.querySelector(":scope > summary")?.appendChild(st); }
  st.textContent = `${(j.images || []).length} image${(j.images || []).length === 1 ? "" : "s"}, ${(j.volumes || []).length} volume${(j.volumes || []).length === 1 ? "" : "s"}`;
  drawHTML(box, statTiles([
    {label: (j.images || []).length === 1 ? "image" : "images", value: (j.images || []).length, sub: humanBytes(df("Images").size || (j.images || []).reduce((n, i) => n + i.size, 0))},
    {label: "not in use", value: unused, sub: `${dang} dangling`, tone: dang ? "warn" : ""},
    {label: (j.volumes || []).length === 1 ? "volume" : "volumes", value: (j.volumes || []).length, sub: df("Local Volumes").size ? humanBytes(df("Local Volumes").size) : ""},
    // Docker's reclaimable is what no container uses: unused images and
    // volumes, which only the two red prunes take (the operator, 23 Oct: 18
    // GB said reclaimable did not move after the two safe ones). Said by
    // name, and the build cache beside it, which the safe prune takes.
    {label: "reclaimable", value: humanBytes((df("Images").reclaimable || 0) + (df("Local Volumes").reclaimable || 0)),
     sub: "unused images and volumes: the red prunes", omit: !(j.df || []).length},
    {label: "build cache", value: humanBytes(df("Build Cache").size || 0),
     sub: df("Build Cache").reclaimable ? `${humanBytes(df("Build Cache").reclaimable)} reclaimable` : "",
     omit: !(j.df || []).some(r => r.kind === "Build Cache")},
  ]).replace(/^<div class="field">|<\/div>$/g, "")
  // The prunes under the numbers they act on, before the lists (the
  // operator, 23 Oct: at the foot they were a long scroll away).
  // Red only where something is lost (the operator, 23 Oct): dangling
  // layers and an old build cache are nobody's, and come back by building;
  // an unused image may be one to start from later (one built here is gone
  // until it is built again), and a volume is data. Safe first.
  + (mayDocker() ? `<div class="actbar dmprunes"><span class="state">a prune removes only what no container uses</span>
      <button type="button" data-dmprune="images" title="docker image prune: dangling images, the layers left by rebuilds">Prune images</button>
      <button type="button" data-dmprune="cache" title="docker builder prune: the build cache, a week old; the next build rebuilds what it needs">Prune build cache</button>
      <button type="button" class="danger" data-dmprune="unused" title="docker image prune -a: images no container uses, two weeks old; one built here is gone until it is built again">Prune unused images</button>
      <button type="button" class="danger" data-dmprune="volumes" title="docker volume prune: volumes no container uses, and the data in them">Prune volumes</button></div>` : "")
  // Two tables (R218 step 8): each image with its state, id, size and age,
  // then each volume with its driver.
  + ((j.images || []).length ? tblWrap(DM_IMG_COLS, j.images.map(i => `
      <div class="row dmimg${i.used ? "" : " off"}">${tblLine(DM_IMG_COLS, [
        esc(i.dangling ? "(dangling)" : `${i.repo}:${i.tag}`),
        `<span class="pill stat${i.used ? " ok" : " off"}">${i.used ? "in use" : "unused"}</span>`,
        esc(i.id), esc(humanBytes(i.size)), esc(i.created)])}</div>`).join(""), "dmimgs")
      : `<div class="hint">no images on this daemon</div>`)
  + ((j.volumes || []).length ? tblWrap(DM_VOL_COLS, j.volumes.map(v => `
      <div class="row dmvol">${tblLine(DM_VOL_COLS, [esc(v.name), esc(v.driver)])}</div>`).join(""), "dmvols")
      : `<div class="hint">no volumes on this daemon</div>`)
);
  box.querySelectorAll("[data-dmprune]").forEach(b => b.onclick = async () => {
    if (await dockerPrune(b.dataset.dmprune, node, dockerList?.name, b)) loadDockerImages(det);
  });
}

// One of the four prunes on a node, asked first in words, from the
// Containers page or the Storage page's Docker row (R123 step 3): true once
// it ran. Red where something is lost (an unused image, a volume's data).
const DOCKER_PRUNE_SAID = {images: "Dangling images go; images a container uses stay.",
                           volumes: "Volumes no container uses go, with their data.",
                           unused: "Images no container uses and two weeks old go; a rebuild pulls or builds them again.",
                           cache: "The build cache a week old goes; the next build of what used it is slower."};
async function dockerPrune(kind, node, nodeName, b){
  if (!await askYes(`Prune ${kind === "cache" ? "the build cache" : kind === "unused" ? "unused images" : kind} on ${nodeName || "this node"}?\n\n${DOCKER_PRUNE_SAID[kind]}`,
                    {verb: "Prune", danger: kind === "unused" || kind === "volumes"})) return false;
  busy(b, "Pruning");
  const r = await postJSON("/api/dockerctl", {action: "prune", container: kind, node});
  if (r.error) notify(r.error, true);
  else notify(`pruned ${kind}: ${(r.out || "").split("\n").filter(l => /reclaimed/i.test(l)).join(" ") || "nothing to remove"}`);
  return !r.error;
}

// ...and the handlers those rows need, wired onto whichever element holds
// them. `list` is the answer the rows were drawn from, for the saved values
// a pick is compared against.
// A row's settings dialog shown where its drawing is on show, and only
// one per row (B852), after every draw and after a draw skipped for having
// nothing new: a dialog closed while its page was out of sight is shown
// again when the page comes back. Escape is its Cancel.
function dmSyncDialogs(el){
  const onShow = !!el.offsetParent || (el.checkVisibility?.() ?? false);
  // Out of sight with a dialog waiting (a phone's pane behind another): shown
  // once the page comes into sight, which no redraw may bring now that one
  // with nothing new is skipped and the stats write in place.
  if (!onShow && el.querySelector("dialog.dmsetdlg") && typeof ResizeObserver === "function" && !el.__dmWatch){
    el.__dmWatch = new ResizeObserver(() => {
      if (!(el.offsetParent || el.checkVisibility?.())) return;
      el.__dmWatch.disconnect(); el.__dmWatch = null;
      dmSyncDialogs(el);
    });
    el.__dmWatch.observe(el);
  }
  el.querySelectorAll("dialog.dmsetdlg").forEach(dlg => {
    const twin = [...document.querySelectorAll("dialog.dmsetdlg[open]")]
      .some(o => o !== dlg && o.dataset.dmdlg === dlg.dataset.dmdlg);
    if (!onShow || twin){ if (dlg.open) dlg.close(); }
    else if (!dlg.open) try{
      dlg.classList.toggle("still", dmWasOpen.has(dlg.dataset.dmdlg));
      dlg.showModal();
    }catch(e){ /* detached mid-draw */ }
    dlg.oncancel = e => {
      e.preventDefault();
      dmBackLet(dlg.dataset.dmdlg); dmDropDrafts(dlg.dataset.dmdlg); dmEditing.delete(dlg.dataset.dmdlg); readMoved("docker"); drawPanes();
    };
  });
}

function dmWireRows(el, list = dockerList){
  // Another project's containers, for an administrator not on it (R274):
  // read, never acted on; the server refuses the same.
  el.querySelectorAll(".dmcard.notmine :is(button, input, select, textarea)").forEach(c => { c.disabled = true; });
  // The unrouted port's way to the nginx tab (dmUnrouted).
  el.querySelectorAll("[data-dmnginx]").forEach(a => a.onclick = e => { e.preventDefault(); openNginxTab(a.dataset.dmnginx); });
  wireSections(el);
  el.querySelectorAll("details.sect").forEach(d => {
    const sum = d.querySelector(":scope > summary");
    if (!sum) return;
    sum.onclick = (e) => {
      e.preventDefault();
      const willOpen = !foldOpen(d);
      slideDetails(d, willOpen);
      if (willOpen && d.querySelector(".dmimgbox")) loadDockerImages(d);
      // Read on every opening: the page keeps the fold across its redraws
      // (R244), so it shows what was read last while it reads again.
      else if (willOpen) loadWire(d);
    };
    // A fold left open across a redraw is drawn back as "reading…": its
    // read is started again, unless one is already on its way to it.
    if (d.open && d.querySelector(".dmimgbox") && /reading…/.test(d.querySelector(".dmimgbox").textContent)) loadDockerImages(d);
    // ...and Ports and mounts (B827): what was read last at once, read again
    // behind it, since the stats and every job step redraw the list.
    else if (d.open && d.querySelector(".wire") && !d.dataset.done){
      const inst = d.closest("[data-inst]")?.dataset.inst;
      if (inst && dmWireSeen[inst]) drawHTML(d.querySelector(".wire"), dmWireSeen[inst]);
      loadWire(d);
    }
  });
  // Returned, so the press's ring holds through its questions, its send and
  // the read after it.
  el.querySelectorAll("[data-dm]").forEach(btn => btn.onclick = () => {
    const [project, instance] = btn.closest("[data-inst]").dataset.inst.split("|");
    return dmAction(project, instance, btn.dataset.dm, btn);
  });
  el.querySelectorAll("[data-dmshell]").forEach(btn => btn.onclick = () => {
    const [project, instance] = btn.closest("[data-inst]").dataset.inst.split("|");
    dmShell(project, instance, btn.dataset.dmshell);
  });
  el.querySelectorAll("[data-dmrel]").forEach(btn => btn.onclick = () => {
    const [project, instance] = btn.closest("[data-inst]").dataset.inst.split("|");
    openRelocate(project, instance);
  });
  // Its archived data written into its volumes (relocate.unpack_start): it
  // stops, the archive goes in over whatever is there, and it starts again.
  // The row says unpacking once the question is answered (dmGo).
  el.querySelectorAll("[data-dmunpack]").forEach(a => a.onclick = async e => {
    e.preventDefault();
    const [project, instance] = a.closest("[data-inst]").dataset.inst.split("|");
    if (!await askYes("Unpack its data into its volumes? It stops, the archive is written in over anything already in them, and it starts again.")) return;
    const j = await dmGo(project, instance, "unpack", () => postJSON("/api/devapp", {project, instance, action: "unpack"}));
    if (!j.error) notify(`unpacking ${j.name}: its row says when it is done`);
  });
  // Whose Rebuild it is. Written at once, like the row's other controls, and
  // the answer redraws every row of that project; it is the project's
  // setting, not the instance's.
  // Staged on the pick, written by Apply: the same shape as the route line
  // above it, and as every other setting on the page.
  // The hostname box follows the certificate pick until it is typed in:
  // the pair's domain, which a subdomain is typed under.
  // ...and each of the three is kept in the row's draft as it changes, so
  // the line redrawn carries them (B729).
  const ngDraft = key => (dmNginxDraft[key] = dmNginxDraft[key] || {});
  el.querySelectorAll("[data-dmngcert]").forEach(sel => sel.onchange = () => {
    const key = sel.dataset.dmngcert, box = el.querySelector(`[data-dmnghost="${CSS.escape(key)}"]`);
    if (box && (!box.value || box.value === box.dataset.was)) box.value = box.dataset.was = sel.value;
    Object.assign(ngDraft(key), {cert: sel.value, host: box?.value || "", was: box?.dataset.was || ""});
  });
  el.querySelectorAll("[data-dmnghost]").forEach(box => box.oninput = () => {
    Object.assign(ngDraft(box.dataset.dmnghost), {host: box.value, was: box.dataset.was || ""});
  });
  el.querySelectorAll("[data-dmngport]").forEach(sel => sel.onchange = () => { ngDraft(sel.dataset.dmngport).port = sel.value; });
  el.querySelectorAll("[data-dmngadd]").forEach(b => b.onclick = async () => {
    const key = b.dataset.dmngadd;
    const cert = el.querySelector(`[data-dmngcert="${CSS.escape(key)}"]`)?.value || "";
    const host = el.querySelector(`[data-dmnghost="${CSS.escape(key)}"]`)?.value.trim() || "";
    const port = el.querySelector(`[data-dmngport="${CSS.escape(key)}"]`)?.value || "";
    busy(b, "Adding");
    const j = await postJSON("/api/nginx", {action: "route-add", node: dockerList?.node || dockerNode || "", cert, host, port});
    if (j.error) notify(j.error, true);
    else { delete dmNginxDraft[key]; notify(`routed ${j.route?.host || "*"} to ${port} on this node's nginx${j.deployed === false ? " (applied once it is deployed)" : ""}`); }
    dockerList = null; readMoved("docker"); loadDocker();
  });
  // Every setting on a row is staged by its control and written by the
  // grid's one Apply (R210): DM_STAGED says which, and how each is written.
  dmWireStaged(el, list);
  // Start, stop, restart and the log, on any container the daemon reported,
  // including the ones AerieOS did not create (R68 steps 1 and 2). The
  // name goes back to the server, which looks it up in a fresh listing
  // before it acts: the rule every executing surface here follows.
  // The node the LIST is about: the notebook reads its project's node, which
  // need not be the one picked on this tab.
  const node = list?.node || dockerNode;
  el.querySelectorAll("[data-ctl]").forEach(b => b.onclick = async () => {
    const what = b.dataset.ctl, ctr = b.dataset.ctr;
    busy(b, {start: "Starting", stop: "Stopping", restart: "Restarting"}[what]);
    try{
      const j = await postJSON("/api/dockerctl", {action: what, container: ctr, node});
      if (j.error) notify(j.error, true); else notify(j.out || `${what} sent`);
    }catch(e){ notify(`${what} ${ctr}: ` + e, true); }
    dockerList = null; loadDocker();
  });
  // A container's log opens in a tab of the dock: streamed from its node
  // while it runs in an instance (log:ctr:), else read by the controller
  // every few seconds (log:dm:), stopped, on the controller or nobody's.
  el.querySelectorAll("[data-dmconf]").forEach(b => b.onclick = () => DM_CONFIGURE[b.dataset.dmconf]?.go(dockerNode));
  el.querySelectorAll("[data-dmlog]").forEach(b => b.onclick = () => {
    const row = b.closest("[data-inst]"), name = b.dataset.dmlog;
    const [project, instance] = (row?.dataset.inst || "").split("|");
    openLogTab(row && b.dataset.running === "1" ? `log:ctr:${project}:${instance}:${name}`
                 : `log:dm:${list?.node || dockerNode || ""}:${name}`, `Log: ${name}`);
  });
  // The words on the row are a way in to where the setting lives now.
  el.querySelectorAll("[data-dmtestgo]").forEach(a => a.onclick = e => {
    e.preventDefault();
    // The project's settings are its notebook's Settings view (R119 step 3):
    // this clicked the row's settings button, which went with it.
    openProjectSettings(a.dataset.dmtestgo);
  });
  // The grid's one Apply: every staged setting on the row, in turn, then
  // one redraw. A setting that fails says so and the rest still go.
  // A row's settings dialog, drawn open: shown in the top layer, again after
  // each draw replaced it; Escape is its Cancel.
  // One dialog per row, in a drawing of it that is on show: the notebook's
  // Docker view draws the same rows in a page out of sight, and its dialog,
  // shown modal on top, left the one on screen inert, every keystroke typed
  // into it going nowhere (B852).
  dmSyncDialogs(el);
  el.querySelectorAll("[data-dmedit]").forEach(b => b.onclick = () => {
    closeMore(); dmEditing.add(b.dataset.dmedit); dmBackHold(b.dataset.dmedit); readMoved("docker"); drawPanes();
  });
  el.querySelectorAll("[data-dmcancel]").forEach(b => b.onclick = () => {
    dmBackLet(b.dataset.dmcancel); dmDropDrafts(b.dataset.dmcancel); dmEditing.delete(b.dataset.dmcancel); readMoved("docker"); drawPanes();
  });
  el.querySelectorAll("[data-dmapply]").forEach(btn => btn.onclick = async () => {
    const key = btn.dataset.dmapply, row = btn.closest(".row");
    dmBackLet(key); dmEditing.delete(key);
    busy(btn, "Applying");
    try{ await dmApplyStaged(key, row, {list, node}); }
    catch(e){ notify("apply: " + failWords(e), true); }
    finally{ if (btn.isConnected) unbusy(btn, "Apply"); }
    dockerList = null; readMoved("docker"); loadDocker();
  });
  wireMore(el);
}

// Grouped by the SPACE each row belongs to (the operator, 24 Sep; B1153: by
// the space its repository is in): a space's containers together under its
// name, the groups in alphabetical order, and what belongs to none last. In each, AerieOS's own
// containers first and then the others, by name. Where a row came from
// (built from a project, written here, or started by somebody else) is said
// on the row itself, since that is what decides what can be done to it.
// The search (R216): what was typed, where the caret was when the redraw
// took the box, and whether a redraw since was the search's own (only
// then is the focus put back, so a redraw for a revision does not steal it).
let dmSearch = "", dmSearchTimer = null;
function dmMatch(r){
  const q = dmSearch.trim().toLowerCase();
  if (!q) return true;
  const hay = [r.name, r.id, r.image, r.project, r.instance, r.owner, r.owner_label,
               r.owner ? projLabel(r.owner) : "", r.owner ? dmSpaceLabel(dmSpaceOf(r.owner)) : "", ...(r.ports || []),
               ...((r.services || []).flatMap(c => [c.name, c.image, c.service, ...(c.ports || [])]))]
    .filter(Boolean).join(" ").toLowerCase();
  return q.split(/\s+/).every(w => hay.includes(w));
}

// Which space's group the chips narrow the list to, for the page's life
// ("" is All, "none" the containers of no space): a view, never saved.
let dmChip = "";

// The space a row's owner is in (B1153): a container belongs to a
// repository, and a space of several (R208) holds all their containers in
// one group, named and colored as the space. System, an owner since deleted
// and no owner are each their own.
// The repository's own record, or the owner itself where it is a space (one
// a move left a container with) or gone.
const dmSpaceOf = o => !o || o === "System" ? (o || "")
  : (state?.projects || []).find(p => p.name === o && p.project)?.project || o;
const dmSpaceLabel = k => state?.repos?.[k]?.name || projLabel(k);
const dmKeyOf = r => dmSpaceOf(r.owner || "");
// What the groups are drawn from beside the list: each space's name, color
// and repositories, and each repository's label and space. In the Containers
// and VMs pages' live stamps, so a space renamed or a repository moved
// redraws them though no container or VM changed.
const dmSpacesKey = () => Object.entries(state?.repos || {}).map(([k, r]) => `${k}=${r.name}:${r.color}:${(r.members || []).join("+")}`).join(";")
  + "|" + (state?.projects || []).map(p => `${p.name}:${p.label}:${p.project}`).join(";");
// What a row says it belongs to: its space, and its repository beside it
// where the space has more than one.
function dmOwnerSaid(o){
  if (!o) return "none";
  if (o === "System") return "System";
  // Given to the space itself (a move that left it there), or kept by the
  // repository named as the space, the space alone: never one name twice.
  const k = dmSpaceOf(o), space = dmSpaceLabel(k), repo = projLabel(o);
  return k !== o && repo !== space && (state?.repos?.[k]?.members || []).length > 1 ? `${space} · ${repo}` : space;
}

// `on` is the node these are on, {id, name}, where a space's containers are
// drawn a node at a time (the notebook's Docker view): its card is marked
// with the node, and its heading says which when a name is given. `only`
// narrows to one group: a chip's space, "none", or a repository's own
// containers by its name (the notebook's).
function dmGroupsHtml(ins, cs, job, blind, only = "", on = null){
  // A space's heading wears its own color when it has one; `null` is
  // the No space heading, which wears none.
  const head = (t, sub, tone) => `<div class="field dmgroup${tone === null ? " none" : ""}"${
    tone ? ` data-style="--gc:${tone}"` : ""}><b>${esc(t)}</b>${
    sub ? `<span class="dim">${esc(sub)}</span>` : ""}</div>`;
  const byName = (a, b) => a.localeCompare(b, undefined, {sensitivity: "base"});
  const kept = r => !only || (only === "none" ? !r.owner : dmKeyOf(r) === only || r.owner === only);
  ins = ins.filter(kept); cs = cs.filter(kept);
  // A deleted repository's containers keep its name until it is restored
  // from the trash, or they are moved or given to another space (8 Oct).
  const gone = k => [...ins, ...cs].some(r => dmKeyOf(r) === k && r.owner_gone);
  const gonesName = k => [...ins, ...cs].find(r => dmKeyOf(r) === k)?.owner_label || k;
  // An administrator sees every space's containers and works on the ones
  // on their own list, as anybody does (R274, the operator 19 Oct): those
  // first, by name; another space's after them, dimmed, its controls dead
  // and the way onto it said under its heading.
  const notMine = k => !!state?.admin && k !== "System" && !gone(k)
    && (state?.projects || []).some(p => (p.name === k || p.project === k) && !p.mine);
  // ...AerieOS's own (System) pinned above them all (R181, the operator,
  // 29 Oct), then this account's, then another space's.
  const rank = k => k === "System" ? -1 : notMine(k) ? 2 : 0;
  const keys = [...new Set([...ins, ...cs].map(dmKeyOf))].filter(Boolean)
    .sort((a, b) => rank(a) - rank(b) || byName(dmSpaceLabel(a), dmSpaceLabel(b)));
  const rowsOf = k =>
    dmRowsHtml(ins.filter(d => dmKeyOf(d) === k).sort((a, b) => byName(a.name, b.name)), job, blind)
    + dmOtherRowsHtml(cs.filter(c => dmKeyOf(c) === k)
        .sort((a, b) => byName(a.name || a.id, b.name || b.id)));
  const group = k => dmView === "list" ? tblWrap(DM_COLS, rowsOf(k), "dmtbl") : rowsOf(k);
  const loose = [...ins, ...cs].some(r => !r.owner);
  // System is AerieOS's own (R180): what it deploys itself, the nginx
  // container today, set by that deployment and by no picker.
  // Each group a card at a desk (R262): its heading and its rows together.
  const card = (html, cls = "") => `<section class="dmcard${cls}"${on ? ` data-node="${esc(on.id)}"` : ""}>${html}</section>`;
  return keys.map(k => gone(k)
      ? card(head(`${gonesName(k)} (deleted)`, "restore it from the trash, or Move these to another space", null) + group(k))
      : k === "System"
        ? card(head("System", "AerieOS's own · no session sees these", null) + group(k))
        : notMine(k)
          ? card(head(dmSpaceLabel(k), "", colorTone(projectColor(k)))
              + `<div class="sub bad dmwhy">${esc(dmSpaceLabel(k))} is not on your list of spaces: add it to your own list on ${
                  pageLink("users", "the Users page")} to work on these</div>` + group(k), " notmine")
          : card(head(dmSpaceLabel(k), on?.name ? `on ${on.name}` : "", colorTone(projectColor(k))) + group(k))).join("")
    + (loose ? card(head("No space", "no session sees these", null) + group("")) : "");
}

// The groups the chips offer: each space with containers here, by its
// name, with how many, and "No space" for the loose ones.
function dmChipGroups(ins, cs){
  const all = [...ins, ...cs];
  const byName = (a, b) => a.localeCompare(b, undefined, {sensitivity: "base"});
  const keys = [...new Set(all.map(dmKeyOf))].filter(Boolean);
  const label = k => k === "System" ? "System"
    : all.some(r => dmKeyOf(r) === k && r.owner_gone) ? `${all.find(r => dmKeyOf(r) === k)?.owner_label || k} (deleted)` : dmSpaceLabel(k);
  const groups = keys.map(k => ({key: k, label: label(k), count: all.filter(r => dmKeyOf(r) === k).length}))
    .sort((a, b) => byName(a.label, b.label));
  const loose = all.filter(r => !r.owner).length;
  return loose ? [...groups, {key: "none", label: "No space", count: loose}] : groups;
}

// A container AerieOS did not start: what the daemon says about it,
// started, stopped and restarted by name, and put under a project on its row.
// Start on boot (R122): a switch on a row, a draft until its Apply, as every
// setting here is. `name` is what the server acts on (a container, or an
// instance meaning all its containers), `on` what the daemon says now.
const dmBootDraft = {};
function dmBootLine(name, on){
  if (!mayDocker()) return "";
  const want = name in dmBootDraft ? dmBootDraft[name] : on;
  // A cell of the settings grid: the tick is a draft, the grid's Apply
  // writes it (R122).
  return `<div class="setcell dmboot">${lbl("", "On boot", "")}<div class="ctl"><label class="ndcap"><input type="checkbox" data-dmboot="${esc(name)}"
      data-was="${on ? "1" : ""}"${want ? " checked" : ""}> Start on boot</label><!--APPLY--></div></div>`;
}

// Reaches the LAN (R178): each project's containers are kept off the
// private ranges, which a container that talks to a machine on the network
// (a controller to its nodes, an app to a device) cannot work behind. An
// administrator lets one through; what no role gives is not drawn.
const dmLanDraft = {};
function dmLanLine(name, on){
  if (!state?.can?.admin) return "";
  const want = name in dmLanDraft ? dmLanDraft[name] : on;
  return `<div class="setcell dmlan">${lbl("", "Network", "")}<div class="ctl"><label class="ndcap"><input type="checkbox" data-dmlan="${esc(name)}"
      data-was="${on ? "1" : ""}"${want ? " checked" : ""}> Reaches the LAN</label></div></div>`;
}

// What an instance has saved under one field of its listing, as the saved
// half of a setting kept under `project|instance`.
const dmInstSaved = field => (key, list) =>
  (list?.instances || []).find(x => `${x.project}|${x.instance}` === key)?.[field] || "";
// What a notice calls an instance: its row's name in the listing the row
// was drawn from, else its project.
const dmInstNamed = ({list, project, instance}) =>
  (list?.instances || []).find(x => x.project === project && x.instance === instance)?.name || project;

// The settings a row stages and its one Apply writes (R210), in the order
// the Apply writes them. Whether the grid has an Apply (dmSetGrid), what
// Cancel drops (dmDropDrafts), whether a row is dirty (dmRowDirty), the
// controls' wiring (dmWireStaged) and the Apply itself (dmApplyStaged) are
// all read from here, so a new setting is its draft, the line that draws
// its control and one entry. Declared after the last draft it names.
//   attr   the control's data attribute, whose value is the draft's key
//   key    which of the row's keys that is (dmRowKeys): row, inst or name
//   draft  what is staged, by that key; the setting's line reads the same
//          object by its own name to draw what was picked
//   tick   a checkbox, staged as true or false; the rest are selects
//   saved  what is saved now: a control put back to it stages nothing
//   skip   a staged value the Apply passes over, where that is not just
//          `undefined`
//   post   the path and the body that write it
//   said   the words once it is written, `j` being the server's answer
// `ctx` is the listing the rows were drawn from, its node, and the row's
// project and instance. An entry with `stage` and `apply` does both itself.
const DM_STAGED = [
  // Which space the row belongs to, on an instance's row and on a
  // container's alike: the one draft kept under the row's own key.
  {name: "owner", attr: "dmown", key: "row", draft: dmOwnDraft,
   saved: (key, list) => (key.startsWith("ctr:")
     ? (list?.containers || []).find(c => (c.name || c.id) === key.slice(4))
     : (list?.instances || []).find(x => `inst:${x.project}|${x.instance}` === key))?.owner || "",
   post: (key, owner, {node, project, instance}) => key.startsWith("ctr:")
     ? ["/api/dockerctl", {action: "owner", container: key.slice(4), owner, node}]
     : ["/api/devapp", {action: "owner", project, instance, owner}],
   said: (key, owner, j, ctx) => {
     const what = key.startsWith("ctr:") ? key.slice(4) : dmInstNamed(ctx);
     return owner ? `${what} belongs to ${projLabel(owner)} now` : `${what} belongs to no space now`;
   }},
  // Built from: the project in the key is what is saved, and an empty pick
  // moves nothing. The row's Apply is the only yes it takes.
  {name: "move", attr: "dmmove", key: "inst", draft: dmMoveDraft,
   saved: key => key.split("|")[0],
   skip: to => !to,
   post: (key, to, {project, instance}) => ["/api/devapp", {action: "move", project, instance, to}],
   said: (key, to, j, ctx) => `${dmInstNamed(ctx)} is ${projLabel(to)}'s now` + (j.dropped_ref
     ? `; it built from ${j.dropped_ref}, which was ${projLabel(ctx.project)}'s branch, and now builds from ${projLabel(to)}'s checkout` : "")},
  {name: "ref", attr: "dmref", key: "inst", draft: dmRefDraft,
   saved: dmInstSaved("ref"),
   post: (key, ref, {project, instance}) => ["/api/devapp", {project, instance, action: "ref", ref}],
   said: (key, ref, j, {project, instance}) => ref ? `${dmCalled(project, instance)} builds from ${ref} now`
     : `${dmCalled(project, instance)} builds from the space's own checkout again`},
  {name: "override", attr: "dmov", key: "inst", draft: dmOvDraft,
   saved: dmInstSaved("override"),
   post: (key, file, {project, instance}) => ["/api/devapp", {project, instance, action: "override", file}],
   said: (key, file, j, {project, instance}) => file ? `${dmCalled(project, instance)} lays ${file} over its compose file from the next build`
     : `${dmCalled(project, instance)} has no override from the next build`},
  {name: "gpu", attr: "dmgpu", key: "inst", draft: dmGpuDraft,
   saved: dmInstSaved("gpu"),
   post: (key, kind, {project, instance}) => ["/api/devapp", {project, instance, action: "gpu", kind}],
   said: (key, kind, j, {project, instance}) => kind
     ? `${dmCalled(project, instance)} gets the ${kind === "nvidia" ? "NVIDIA card" : "AMD card"} from the next build`
     : `${dmCalled(project, instance)} gets no GPU from the next build`},
  // The route does both itself: its draft is two controls' picks (how it is
  // reached, and through which port), dropped when both are back at what is
  // saved; the Apply reads the two from the row, and a public link is asked
  // about first, a no putting the controls back. Its redrawn line is what
  // says it was written.
  {name: "route", attr: "route", key: "inst", draft: dmRouteDraft,
   stage(sel){
     const row = sel.closest("[data-inst]");
     const d = dmRouteDraft[row.dataset.inst] || (dmRouteDraft[row.dataset.inst] = {});
     d[sel.dataset.route] = sel.value;
     const dirty = [...row.querySelectorAll("[data-route]")].some(x => x.value !== x.dataset.was);
     if (!dirty) delete dmRouteDraft[row.dataset.inst];
     return row;
   },
   async apply(row){
     if (!row?.dataset.inst) return;
     const [project, instance] = row.dataset.inst.split("|");
     if (!dmRouteDraft[row.dataset.inst]) return;
     const sel = row.querySelector('[data-route="mode"]');
     const mode = sel?.value || "lan";
     const port = row.querySelector('[data-route="port"]')?.value || "";
     if (mode === "funnel" && sel.dataset.was !== "funnel" && !await askYes(
         `Open ${dmCalled(project, instance)} to the internet?\n\nAnyone with the link can reach the port until the route goes back to lan.`)){
           row.querySelectorAll("[data-route]").forEach(x => { x.value = x.dataset.was; });
           delete dmRouteDraft[row.dataset.inst]; return; }
     delete dmRouteDraft[row.dataset.inst];
     const j = await postJSON("/api/devapp", {project, instance, action:"route", mode, port});
     if (j.error) notify(j.error, true);
   }},
  // Start on boot (R122) and Reaches the LAN (R178), an administrator's: a
  // tick each, kept under the container's name, saved as the tick was drawn.
  {name: "boot", attr: "dmboot", key: "name", draft: dmBootDraft, tick: true,
   saved: (name, list, box) => box.dataset.was === "1",
   post: (name, on, {node}) => ["/api/dockerctl", {action: on ? "boot-on" : "boot-off", container: name, node}],
   said: (name, on, j) => j.out || (on ? `${name} starts on boot` : `${name} no longer starts on boot`)},
  {name: "lan", attr: "dmlan", key: "name", draft: dmLanDraft, tick: true,
   saved: (name, list, box) => box.dataset.was === "1",
   post: (name, on, {node}) => ["/api/dockerctl", {action: on ? "lan-on" : "lan-off", container: name, node}],
   said: (name, on, j) => j.out || (on ? `${name} reaches the network around its node` : `${name} no longer reaches the network around its node`)},
];

// Each staged control wired: a pick or a tick that differs from what is
// saved is its draft, one put back is none, and either wakes the row's Apply
// while something is staged. `list` is the listing the rows were drawn from.
function dmWireStaged(el, list){
  const wake = row => {
    const b = row?.querySelector("[data-dmapply]");
    if (b && !b.getAttribute("aria-busy")) b.disabled = !dmRowDirty(b.dataset.dmapply);
  };
  for (const s of DM_STAGED)
    el.querySelectorAll(`[data-${s.attr}]`).forEach(c => c.onchange = () => {
      if (s.stage){ wake(s.stage(c)); return; }
      const key = c.dataset[s.attr], v = s.tick ? c.checked : c.value;
      if (v === s.saved(key, list, c)) delete s.draft[key];
      else s.draft[key] = v;
      wake(c.closest(".row"));
    });
}

// A row's Apply: every setting it has staged, written in the table's order.
// One the server refuses says why and keeps its draft, and the rest still
// go. `key` is the key the Apply carries, `row` its row, `list` the listing
// the row was drawn from and `node` that listing's node.
async function dmApplyStaged(key, row, {list, node}){
  const keys = dmRowKeys(key, list);
  const [project, instance] = keys.inst.split("|");
  const ctx = {list, node, project, instance};
  for (const s of DM_STAGED){
    const k = keys[s.key];
    if (!k) continue;
    if (s.apply){ await s.apply(row); continue; }
    const v = s.draft[k];
    if (s.skip ? s.skip(v) : v === undefined) continue;
    const [path, body] = s.post(k, v, ctx);
    const j = await postJSON(path, body);
    if (j.error){ notify(j.error, true); continue; }
    delete s.draft[k];
    notify(s.said(k, v, j, ctx));
  }
}

// A system container's own page (R181): nginx's routes and certificates,
// the scanners' schedule, the router's settings on the Installed page.
// Its row is any container's row with this one press more.
const DM_CONFIGURE = {
  // Each a service's own page, beside Installed (R264), in whichever group
  // the rail lists it.
  nginx: {page: "nginx", go: nid => { if (nid) NODE_SET.nginx(nid); railGo(groupOf("nginx").key, "nginx"); }},
  scanners: {page: "scanners", go: () => railGo(groupOf("scanners").key, "scanners")},
  router: {page: "installed", go: nid => openInstalledOn(nid, "", "service:model-router")},
};
function dmConfigureBtn(r){
  const c = DM_CONFIGURE[r?.system];
  return c && railAllows(c.page) ? `<button type="button" data-dmconf="${esc(r.system)}" title="its settings, on a page of their own">Configure</button>` : "";
}

function dmOtherRowsHtml(cs){
  return cs.map(c => dmOtherWrap(c, `
      <div class="grow">
        <div class="dmhead">
        <div class="dmid">
        <div class="name">${esc(c.name || c.id)}<span class="pill stat${c.state === "running" ? " ok" : " off"}">${
          esc(c.state || "unknown")}</span> <span class="pill" title="not started by AerieOS">not ours</span></div>
        <div class="sub">${dmImage(c.image)} · ${esc(c.status || c.state)}${
          c.project ? ` · ${esc(c.project)}${c.service ? "/" + esc(c.service) : ""}` : ""}${
          c.ports.length ? ` · ${c.ports.map(esc).join(", ")}` : ""}</div>
        </div>
        <div class="actbar dmacts">
        ${dmConfigureBtn(c)}
        ${!mayDocker() ? "" : `<button type="button" data-ctl="${
          c.state === "running" ? "stop" : "start"}" data-ctr="${esc(c.name || c.id)}"
          title="${c.state === "running" ? "Stop" : "Start"} it: docker ${c.state === "running" ? "stop" : "start"} ${esc(c.name || c.id)}">${
          c.state === "running" ? "Stop" : "Start"}</button>
        <button type="button" data-ctl="restart" data-ctr="${esc(c.name || c.id)}"${
          c.state === "running" ? "" : " disabled"}
          title="Restart it: docker restart ${esc(c.name || c.id)}">Restart</button>`}
        ${actMore([dmEditBtn("ctr:" + (c.name || c.id)),
          mayDocker() ? `<button type="button" data-dmlog="${esc(c.name || c.id)}" data-running="0"
            title="what it prints, in a tab of the dock, read again as it goes on">Log</button>` : ""])}
        </div>
        </div>
        ${dmSetPills([["Space", esc(dmOwnerSaid(c.owner))],
                        ["", c.boot ? "✓ Starts on boot" : "not on boot", c.boot ? "ok" : ""],
                        ["Agent", dmClaudeSaid(c, true)]])}
        ${dmEditing.has("ctr:" + (c.name || c.id)) || dmRowDirty("ctr:" + (c.name || c.id))
          ? dmSetDialog(c.name || c.id, "ctr:" + (c.name || c.id),
                        [dmOwnerLine(c, "ctr:" + (c.name || c.id)), dmBootLine(c.name || c.id, !!c.boot),
                         dmLanLine(c.name || c.id, !!c.lan)]) : ""}
      </div>`)).join("");
}
// A container AerieOS did not start is a line in list view too, with
// what the daemon says in the same columns, so the table has one shape.
function dmOtherWrap(c, inner){
  const name = c.name || c.id;
  if (dmView !== "list") return `<div class="row stack2 off dmother" data-ctr="${esc(name)}">${inner}</div>`;
  return dmLineWrap(`data-ctr="${esc(name)}"`, " off dmother", [`<span class="name">${esc(name)}</span>`,
    `<span class="pill stat${c.state === "running" ? " ok" : " off"}">${esc(c.state || "unknown")}</span>`,
    c.owner ? esc(dmOwnerSaid(c.owner)) : "", esc((c.ports || []).join(", ")), "", dmImage(c.image)], inner);
}

// An image as a fact (R227 step 2): its tag, and a pinned digest's first
// twelve in code with the whole of it as its title, where the whole printed
// over three lines.
function dmImage(img){
  const s = String(img || ""), at = s.indexOf("@sha256:");
  // ...and an image named by its id alone, as a container made from an
  // untagged build is: its first twelve, as docker ps shows it.
  const id = /^sha256:([0-9a-f]{12,})$/.exec(s);
  if (id) return `<code class="dmdigest" title="${esc(s)}">${esc(id[1].slice(0, 12))}</code>`;
  if (at < 0) return esc(s);
  const dg = s.slice(at + 8);
  return `${esc(s.slice(0, at))} <code class="dmdigest" title="${esc(s.slice(at + 1))}">${esc(dg.slice(0, 12))}</code>`;
}

// The page's top, drawn by the page and by its placeholder alike (R218, the
// operator 18 Oct: a template written beside the page fell behind it), so
// a change to either is a change to both. Given null, each draws its
// placeholder: the same markup with a shimmer where a value goes and its
// controls dead.
// The bar: the one node switcher (page-docs.js nodePick, R121 step 5) at
// the left, the search beside it (R216: a name, an image, a port or a
// project, narrowing the rows as it is typed; a view, never saved), Cards
// and List, and the page's buttons at the right: Check for updates, the
// registry images against what their registries serve now (R195), not while
// the daemon is blind; and New container, the page's main action, where a
// phone finds it without scrolling past every container (R119 step 5).
function dmBar(b){
  const ghost = !b, dead = ghost ? " disabled" : "";
  // The node is the Containers group's header's (R178): the search takes
  // the picker's room.
  return `<div class="field docbarrow dmpick"><input${ghost ? "" : ` id="dmSearch"`} type="search"
        placeholder="name, image, port or space" data-ph-short="search" autocomplete="off" aria-label="narrow the containers: name, image, port or space" value="${esc(dmSearch)}"${dead}><span class="sp"></span>
      ${dmViewSeg(dead)}
      ${mayDocker() ? `<span class="actbar">${
      b?.blind ? "" : `<button type="button"${ghost ? "" : ` id="bDockerCheck"`}${dead || (featureOff("image-updates") ? " disabled" : "")}>${barSaid("Check for updates", "Check")}</button>`}${
      `<button type="button"${ghost ? "" : ` id="bDockerNew"`} class="primary"${dead}>${barSaid("New container", "New")}</button>`}</span>` : ""}</div>`;
}
// Cards or a list, this browser's choice: the page's and a notebook's
// Docker view's, which keep the one choice between them.
function dmViewSeg(dead = ""){
  return viewSeg("dmview", dmView, "each container as a card", "one line per container, opening into its card", dead);
}
// The press on it, then `redraw`; kept for the next open.
function dmViewWire(el, redraw){
  el.querySelectorAll("[data-dmview]").forEach(b => b.onclick = () => {
    dmView = b.dataset.dmview === "list" ? "list" : "cards";
    try{ localStorage.setItem("bb.dmview", dmView); }catch(e){ /* private mode */ }
    redraw();
  });
}
// Check for updates on `node`'s images, said as a notice, then `after`.
async function dmCheck(btn, node, after){
  busy(btn, "Checking");
  try{
    const j = await postJSON("/api/images", {action: "check", node});
    if (j.error) notify(j.error, true);
    else notify(j.behind ? `${j.behind} container${j.behind === 1 ? " has" : "s have"} a newer image: Update on ${j.behind === 1 ? "its row" : "their rows"}`
                         : `checked ${j.checked}: every registry image is current`);
  }catch(e){ notify("could not check: " + failWords(e), true); }
  after();
}
// The status line: what runs of how many, the updates due once images were
// checked, the projects, and what on this daemon nobody here started; a
// project's own Docker view counts its containers alone, with no projects.
// Its phrases: the page draws them in its head (dmHead), a notebook's
// Docker view in its glance (dmTiles).
function dmTiles(t){
  return statTiles(dmLine(t));
}
function dmHead(t){
  return pageHead({line: dmLine(t)});
}
function dmLine(t){
  const g = !t;
  return ([
    // "of 6" alone on a small phone, where the word wrapped the tile.
    {label: "running", value: g ? GHOST : t.running, sub: g ? GHOST
      : `of ${t.all}${matchMedia("(max-width:440px)").matches ? "" : ` container${t.all === 1 ? "" : "s"}`}`,
     tone: !g && t.all && !t.running ? "warn" : ""},
    {label: !g && t.behind === 1 ? "update due" : "updates due", value: g ? GHOST : t.behind, tone: !g && t.behind ? "warn" : "", omit: !g && !t.checked && !t.behind},
    {label: !g && t.projects === 1 ? "space" : "spaces", value: g ? GHOST : t.projects, omit: !g && t.projects === undefined},
    {label: "not ours", value: g ? 0 : t.notOurs, omit: g || !t.notOurs, title: "on this daemon, started by nobody here"},
    // ...and when its images were checked, and where a node only hosts
    // containers where a shell opens, on the same line (R274): one band, as
    // the page waits.
    {text: g || featureOff("image-updates") ? "" : t.images_at ? `images checked ${ago(t.images_at)}` : "images not checked yet", omit: g || !!featureOff("image-updates")},
    (h => ({text: h && mayShell() ? (h.config?.own ? "no shells on this machine: it is the controller's own" : `shells open from a node that runs sessions: ${h.name} hosts containers only`) : "",
            omit: g || !h || !mayShell()}))(dmHostOnly()),
  ]);
}
// The daemon's images and volumes (R216): a section at the foot, read when
// opened, for an administrator, with the two prunes that touch nothing a
// container uses.
function dmImagesSection(){
  return state?.can?.admin ? docSection("docker", "images", "Images and volumes", "",
    `<div class="dmimgbox" data-own>${skel("rows", 3, "reading…")}</div>`, {open: false, fold: true}) : "";
}
// ...and the page's head under them: when the images were checked.
function dmStatus(d){
  if (!mayDocker()) return "";
  // Image updates switched off on this install (R81): its sentence where
  // the line says when they were checked.
  if (featureOff("image-updates")) return `<div class="field">${deadWhy(featureOff("image-updates"))}</div>`;
  // When its images were checked and where a shell opens are the page's
  // line's (dmTiles, R274).
  return "";
}

// The old system's containers and VMs on the controller's own machine
// (tab-machine.js adoptAppsSection), above the rows: where a person looks for
// them after a move off another NAS.
function dmOldApps(){
  const own = ownMachine();
  return own && dockerNode === own.id && state?.can?.admin ? adoptAppsSection(own) : "";
}
// The rows' settings dialogs open before a redraw, by key: shown again after
// it without their opening animation (the operator, 26 Oct: each redraw
// played it again, a flicker under the pointer).
let dmWasOpen = new Set();
function dmNoteOpen(el){
  dmWasOpen = new Set([...(el?.querySelectorAll("dialog.dmsetdlg[open]") || [])].map(d => d.dataset.dmdlg));
}
function renderDockerInto(i){
  const el = $("doc" + i);
  if (!el) return;
  el.classList.add("flush");
  // An answer on its way is not a blank page: a build makes the daemon's
  // ps slow, and the operator watched the whole tab turn to "loading" for
  // the length of a build. The last answer for this node stays on screen
  // with a note, and the new one repaints when it lands (B125).
  if (!dockerList && dockerSeen[dockerNode || ""]) dockerList = dockerSeen[dockerNode || ""];
  if (!dockerList){
    // Its template (R218 step 16): the picker band with its search, the
    // view switch and its buttons, the add band and the tiles' words are the
    // page's own; the daemon's containers are on their way, as cards or as
    // lines, whichever view this browser keeps.
    // In the page's own order (the page tops' rule), drawn by the page's own
    // builders given nothing (the operator, 18 Oct: a template written
    // beside the page fell behind it): the bar, the tiles, the status line,
    // then the rows.
    // The old system's containers and VMs need nothing of the daemon's
    // answer, so they are drawn while it is on its way.
    const old = dmOldApps();
    drawHTML(el, `<div class="doctab dmtab">${skTpl(`${dmBar(null)}${dmHead(null)}${dmStatus(null)}`)}${old}${skTpl(`
      ${dmView === "list" ? skTable(DM_COLS, 4)
        // ...the rows in a project group's card, as they land (R262).
        : `<section class="dmcard"><div class="field dmgroup"><b>${skv(8)}</b></div>${skRows(3)}</section>`}
      ${dmImagesSection()}`)}</div>`);
    if (old) wireAdoptApps(el);
    return;
  }
  // The daemon did not answer; it is off, it is not a sandbox VM, or the VM
  // is not running. This used to end here, in one error line with no rows: the
  // page threw away everything it could still honestly say, which is most of
  // it. What an instance IS lives on this side (its name, its project, what it
  // was built from, what its env still wants); only whether it is RUNNING is
  // the daemon's to know. So the rows are drawn from the store, grayed, and
  // say nothing about their state: an unreachable daemon is not evidence that
  // anything stopped.
  // Three ways to be blind, and the poll's is the one that outlives a fetch:
  // a list read while the daemon was up is stale the moment the poll says it
  // is down, and going on showing "running" from it would be the page's own
  // memory presented as the daemon's answer.
  // The poll's verdict is about the DEFAULT node, so it speaks for this view
  // only while this view IS the default one. Computed once, because `blind`
  // and the gate below both used to ask and only one of them narrowed it.
  const pollSays = dmPollSays();
  const blind = dmBlind();
  const job = dockerJob();
  // The search narrows the rows and nothing else: the tiles and the chips
  // still count the whole, so what is hidden is still said.
  const ins = (dockerList.instances || []).filter(dmMatch);
  const cs = (dockerList.containers || []).filter(dmMatch);
  // A chip in force names a group that is still here; one for a group that
  // went (its last container removed) falls back to All.
  const chips = dmChipGroups(dockerList.instances || [], dockerList.containers || []);
  if (dmChip && !chips.some(g => g.key === dmChip)) dmChip = "";
  const rows = dmGroupsHtml(ins, cs, job, blind, dmChip);
  // Its own class rather than the projects tab's: the two look alike and a
  // selector that matched both would be a test passing on the wrong tab.
  // Said in words at the top: "why is everything grayed out" is answered by
  // looking, on a phone as at a desk.
  // Why everything is grayed, in words at the top. The poll's sentence when it
  // has one; otherwise the daemon's own words from the call this page just
  // made, which is the case the poll cannot see: a VM that went away inside
  // the availability memo.
  // The poll's verdict is about the DEFAULT node; a picked node answers for
  // itself through its own overview. Mixing them gated node B behind node
  // A's absence, which is the one wrong answer a picker can give.
  // WHAT SWITCHES THE BUTTONS OFF is whether this node can be ACTED on, which
  // is not whether this controller can see what is running there. On an agent
  // node compose goes to the agent and runs against that machine's own
  // socket, so a controller that cannot ssh in changes nothing about whether
  // Up works, and gating on the listing ghosted Up, Down, Rebuild and Send
  // on a node where all four would have worked (B111). A listing that failed
  // still grays the ROWS, because what they would claim about running and
  // stopped is exactly what nobody asked.
  const off = pollSays
    || (dockerList.on === false ? (dockerList.why || "the daemon did not answer") : "");
  // Said, not switched off: a listing that failed is worth a line, and the
  // line has to say that the buttons under it still work.
  const note = off || (dockerList.error
    // The error's own full stop comes off before the clause is joined on:
    // "...does not know.: the rows cannot say" was on a walk's screenshot.
    ? `Docker did not answer: ${String(dockerList.error).replace(/\.\s*$/, "")}. What is running `
      + `is unknown; the controls still work`
    : "");
  // Which daemon this is, stated rather than inferred: the node picked
  // above names it, and saying which machine the buttons below act on is
  // worth a line whatever the arrangement.
  // The PICKED node's own answer, not the poll's: the poll is about the
  // default node, so on any other one this line named a machine the tab was
  // not talking to, in an address, which reads as proof.
  const src = dockerList?.src || state?.docker || {};
  // Through its agent, the ordinary case, the picker has said already; a
  // daemon reached at an address, or a mapped path not mounted, is news.
  const srcLine = !note && src.kind && (!src.agent || (src.strays || []).length)
    ? `<div class="dmsrc">${src.agent ? `on ${esc(src.kind)}`
                                       : `on ${esc(src.kind)} at <code>${esc(src.where)}</code>`}${
        // A mapped path this container does not have. Not a fault: it can be a
        // share the daemon mounts and AerieOS has no business reading. It is
        // said because nothing else here will ever act on it, and a line of
        // configuration that does nothing should not look like it does.
        (src.strays || []).length
          ? `<br><span class="dim">${esc((src.strays || []).join(", "))} ${
              src.strays.length > 1 ? "are" : "is"} mapped but not mounted here</span>` : ""}</div>`
    : "";
  // Slow, not merely in flight: readBusy("docker") alone is true for the whole
  // of every fetch, and the timer in loadDocker is what decides it is worth
  // saying. A listing the server itself marked stale wears the same class
  // without the word: it is the last answer, and nothing is on its way that
  // the next revision will not bring.
  const slow = readBusy("docker") && dmSlow;
  // The picker: every node, online or not: an offline node's view is its
  // last-known list in the ghosted state the blind path draws.
  // One tab, re-rendered per pick (docs/nodes.md §13), never a tab per node.
  // The one node switcher (page-docs.js nodePick, R121 step 5), in the bar
  // the other node-scoped tabs wear: the picker at the left, the page's
  // buttons at the right, drawn whenever there is a node so the tab says
  // whose daemon it is. No Refresh: the page follows its node's containers
  // by the fingerprint each heartbeat carries (the operator, 17 Oct).
  const dnodes = (nodesList || []).filter(n => n.kind !== "local");
  if (nodesList === null || nodesStale) nodesKnown();
  const picker = dmBar({nodes: dnodes, blind});
  const status = blind ? "" : dmStatus(dockerList);
  // What a session is waiting on, above everything else: somebody is blocked
  // on these, and this is the tab whose dial sent them here. The bell carries
  // them too, the way root asks sit on the Nodes tab and in the bell.
  const asks = (typeof ph !== "undefined" && ph?.asks || [])
    .filter(a => a.kind === "rebuild");
  const askRows = asks.map(a => `<div class="row dmask">
      <div class="grow"><div class="name">${esc(askVerb(a))}: ${esc(a.why)}</div>
        <div class="phcmd">${askCmd(a)}</div>
        <div class="sub">${esc(askWho(a))} asks to ${esc(askVerb(a))} it · ${askLeft(a)}</div></div>
      <span class="acts">${askActs(a, {deny: "data-rdeny", allow: "data-rallow"})}</span></div>`).join("");
  // `dmstale` while the rows are the last answer and a new one is on its
  // way: what a reader waiting on a refresh looks at, and what the note
  // below says in words.
  // The tab at a glance (R216, the tiles rule): how many run of all that
  // are here, how many have an update due, how many projects, and what
  // is on the daemon that nobody here started. Blind, the daemon has not
  // answered, so nothing is counted.
  const allIns = dockerList.instances || [], allCs = dockerList.containers || [];
  const running = allIns.filter(d => d.running).length;
  const behind = allIns.filter(d => (d.images_behind || []).length || d.nginx_to).length;
  const notOurs = allCs.filter(c => !c.ours).length;
  const tiles = blind || !(allIns.length || allCs.length) ? "" : dmHead({running, all: allIns.length, behind,
    checked: !!dockerList?.images_at, images_at: dockerList?.images_at || 0, projects: chips.filter(g => g.key !== "none").length, notOurs});
  const html = `<div class="doctab dmtab${slow || dockerList?.stale ? " dmstale" : ""}">${picker}${tiles}${
    // The page's own boxes under the tiles and the chips, never between
    // them (the operator, 26 Oct): what every page has comes first.
    chipBar(chips, dmChip, "data-dmchip")}${status}${askRows}${dmOldApps()}${note
      ? `<div class="field"><div class="notice warn dmnote">${esc(note)}</div></div>` : srcLine}${
    // Blind, the list is what is on record here rather than what is on the
    // daemon, and "nothing on this daemon yet" would be a claim about a
    // machine nobody just asked.
    rows || `<div class="empty">${dmSearch ? `nothing here matches ${esc(dmSearch)}` : blind
      ? "nothing on record here: an instance appears once it has been sent"
      : dockerList?.unseen
      // Left out by the server, not absent (B89): what runs here belongs to
      // projects this account's roles give no Containers Read on.
      ? "nothing here is yours to see: what runs on this daemon belongs to spaces whose Containers your roles do not read"
      : "nothing on this daemon yet"}</div>`}
    ${
    // The daemon's images and volumes (R216): a section at the foot, read
    // when opened, for an administrator, with the two prunes that touch
    // nothing a container uses. Blind, there is no daemon to list.
    blind ? "" : dmImagesSection()}
    </div>`;
  // Written only when it says something new (the operator, 26 Oct: the page
  // was written again on every read, its open folds read again, the pointer's
  // place lost): a read that brings the same list leaves the page alone.
  // ...and one that does is patched into what is there (R244): a person's
  // typing in the search or a row's settings, an open fold and what was read
  // into it, and an open dialog all stay where they were.
  // Rows the redraw puts elsewhere (one arriving on top, one whose state
  // sorts it anew) slide there, and a new one fades in (reflow).
  if (!reflow(el, ".row[data-inst]", e => e.dataset.inst, () => patch(el, html)) && el.querySelector(":scope > .dmtab")){ dmSyncDialogs(el); return; }
  dmNoteOpen(el);
  gateDocker(el, off);
  wireAdoptApps(el);
  // The asks answer through the phone's endpoint, which holds the one list of
  // them; phFetch redraws this tab when the answer comes back.
  el.querySelectorAll("[data-rallow]").forEach(b => b.onclick = () => {
    b.disabled = true; b.textContent = "starting";
    phFetch({action: "allow", id: Number(b.dataset.rallow)});
  });
  el.querySelectorAll("[data-rdeny]").forEach(b => b.onclick = () =>
    phFetch({action: "deny", id: Number(b.dataset.rdeny)}));
  const ck = el.querySelector("#bDockerCheck");
  if (ck) ck.onclick = () => dmCheck(ck, dockerList?.node || dockerNode || "", () => { readMoved("docker"); loadDocker(); });
  const nb = el.querySelector("#bDockerNew");
  if (nb) nb.onclick = openNewContainer;
  // A chip narrows the list to one project's group (the chips rule): a
  // redraw from what is already here, nothing fetched and nothing saved.
  el.querySelectorAll("[data-dmchip]").forEach(c => c.onclick = () =>
    // ...the groups it leaves fading through, as a page does (fadeThrough).
    chipMove(() => document.querySelector(".pane .doc.on .dmtab"), ".dmcard, .tbl > .row, .tbl .rows > .row",
             () => { dmChip = c.dataset.dmchip; readMoved("docker"); drawPanes(); }));
  dmViewWire(el, () => morphThrough(DM_ROWS, () => { readMoved("docker"); drawPanes(); }, e => e.dataset.inst));
  // The search redraws as it is typed; the patch keeps the box, its focus
  // and its caret.
  const sb = el.querySelector("#dmSearch");
  if (sb){
    // A word an input method is still composing is filtered on once it is
    // chosen (R244 step 4).
    onTyping(sb, () => {
      dmSearch = sb.value;
      clearTimeout(dmSearchTimer);
      dmSearchTimer = setTimeout(() => { readMoved("docker"); drawPanes(); }, 120);
    });
  }
  // The wiring, fetched when the fold is opened and not before. It needs the
  // compose file parsed, which is the one thing overview() refuses to do for
  // every instance at once, and it is the thing you want occasionally, which
  // is what a fold is for. Rendered the same way the artifact row renders it:
  // the container's side on the left, the daemon's on the right, and an arrow
  // saying which way a mount goes.
  // The summary's own click, not the toggle: <details> opens instantly by
  // construction, so the flag has to be driven by slideDetails: the same
  // helper the notebook's folds already use, rather than watched afterwards.
  // wireSections first, for the remembered open state; then the click is
  // rebound, because this fold also has to fetch what it is about to show.
  dmWireRows(el, dockerList);
}

// ---- new project / link to a git host ----------------------------------
// One dialog, three modes, one table. `init` and `clone` feed /api/create;
// `link` points an existing repo at an empty one via /api/link. The
// table is the whole difference between the modes, which fields show, what
// the button says, where it posts, so a new mode is a row, not a hunt
// through branches. The server re-validates everything; this side only
// catches the obvious before a round-trip, and keeps the dialog open on
// failure so nothing typed is lost.

// ---- no daemon, no Docker buttons ---------------------------------------

// The controls that act on the daemon, in one list. Not the ones that only
// read or explain: a daemon wired up is read again when its node's
// fingerprint of its containers moves (there is no Refresh), Edit and Env
// open a compose file that is a file whether or not anything can run it, and
// the manager tab itself is where the reason is written in words: disabling
// the way to READ a diagnosis is how you get a dashboard that has gone quiet
// for no visible cause.
//
// REMOVE IS NOT ONE OF THEM, and that is the correction: removing is this
// side's own record, with a `down` in front of it as a courtesy. Gating it on
// the daemon left a row on a machine that had gone away removable by nobody:
// the one state a list must not have, since the row is the only control over
// the thing it names. It stays live, the server takes the record either way,
// and the confirmation says which of the two halves will happen.
// The new-project dialog that followed this list is tab-projects.js now; its fields and its submit are wired further down.
const DOCKER_ACTS = '[data-dm="up"],[data-dm="down"],'
                  + '[data-dm="rebuild"],'
                  + '[data-devsend],#bDockerNew';
