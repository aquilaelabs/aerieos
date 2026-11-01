"use strict";
// This machine (R90 step 8, R56 step 8): the controller's own machine on a
// bare-metal install, a page of its own in the Controller rail group and
// not a row among Machines' nodes. Its head says what the machine is (its
// name, system, cores and memory, the release this install runs and how
// long it has been up, its agent, the wall); under it the Updates section
// (Controller settings' own, R90 step 5) and the own node's row as the
// Nodes page draws any node's (tab-nodes.js ndRowHtml): its health, the
// projects on it, its sessions, GPU, USB, router, features, storage,
// network and the advanced verbs (reboot and power off among them). The
// container edition has no own machine and says so if the page is opened.
// Chrome from docSurface(); the hard rules are uniform.mjs's.

function openMachineTab(what){
  if (what) sectOpen["nodes:" + what] = true;
  openTab({kind: "machine", arg: "__machine", label: "This machine"});
  loadNodes();
}

// The own machine's row, or null before the node list lands.
function ownMachine(){
  return (nodesList || []).find(n => n.config?.own && n.state !== "retired") || null;
}

function machineHead(n){
  const r = n.reported || {};
  const img = state?.image || {};
  const mem = r.mem_mb ? `${Math.round(r.mem_mb / 1024)} GB` : "";
  const wall = r.session?.up ? "in force" : r.session?.why ? `down: ${r.session.why}` : n.live ? "not reported yet" : "";
  // A held start (R56 step 9): Start lifts it. Holding the next one is the
  // checkbox beside Reboot and Shut down (R161 step 11).
  const h = state?.held || {};
  const actions = h.held ? `<button type="button" class="primary" data-heldstart title="${esc((h.why || []).join("; "))}">Start</button>` : "";
  return pageHead({title: n.name, pills: `<span class="tag ndown">this machine</span> ${nodeStatePill(n)}${h.held ? ` <span class="pill bad">held</span>` : ""}`, actions, facts: [
    ["System", [r.os, r.hostname && r.hostname !== n.name ? r.hostname : ""].filter(Boolean).join(" · ")],
    ["Cores and memory", [r.cpu ? `${r.cpu} cpu` : "", mem].filter(Boolean).join(" · ")],
    ["Release", `${img.version || "unstamped"}${img.rev ? ` (${img.rev.slice(0, 7)})` : ""}`],
    // BuilderBot OS (R160 step 4): the image, the slot this boot came from
    // and the one that boots next when an update has been written.
    ...(r.os_image?.version ? [["Image", `BuilderBot OS ${r.os_image.version}, slot ${r.os_image.slot || "?"}${r.os_image.next && r.os_image.next !== r.os_image.slot ? `; slot ${r.os_image.next} boots next: restart to finish the update` : r.os_image.trial ? "; on trial until the health check marks it good" : ""}${r.os_image.fell_back ? `; ${r.os_image.fell_back}` : ""}`]] : []),
    ["Up", shortUptime(state?.uptime || 0)],
    ...(r.timezone ? [["Time zone", r.timezone]] : []),
    ["Agent", n.agent?.version || ""],
    ["Wall", wall]]});
}

function renderMachineInto(i){
  const d = docSurface(i, "machine");
  if (!d) return;
  d.setBar("");
  if (!state?.bare_metal){
    d.list.innerHTML = `<div class="empty">This machine is a bare-metal install's page: the machine the controller runs on, its system, its updates and what it runs as a node. This BuilderBot runs in a container, which has no machine of its own here; its nodes are on the Nodes page.</div>`;
    return;
  }
  if (nodesList === null){
    d.list.innerHTML = skTpl(`<div class="row stack2 ndrow"><div class="grow"><div class="name">${skv(7)}</div>${ndFacts(null)}</div>
      <div class="ndsections">${ND_SECTS.filter(([k]) => k !== "gpu" && k !== "usb").map(([k, t], j) => docSection("nodes", k, t, "", skRows(j ? 1 : 3))).join("")}</div></div>`);
    loadNodes();
    return;
  }
  const n = ownMachine();
  if (!n){
    d.list.innerHTML = `<div class="empty">This install's own machine is not enrolled as a node yet: the setup page shows it being set up, and the installer's --install does it (install-controller.sh --no-node leaves it out, and then there is nothing here).</div>`;
    return;
  }
  const inflight = t => (n.jobs || []).some(j => j.type === t || j.apply === t);
  d.list.innerHTML = machineHead(n)
    + (state?.release?.running !== undefined ? docSection("nodes", "updates", "Updates", state.release.newer ? `${state.release.newer} is out` : state.release.latest ? "up to date" : "", updatesSection()) : "")
    + olderVersionsSection(n)
    + stickSection(n)
    + machineConsoleSection(n)
    + firstbootSection()
    + adoptSection(n)
    + adoptAppsSection(n)
    + ndRowHtml(n);
  wireNodesTab(d.el);
  nodesReadOnly(d.el);
  wireUpdates(d.el);
  wireOlderVersions(d.el);
  wireHeld(d.el);
  void inflight;
}

// Hold the next start (R56 step 9, R161 step 11): a checkbox beside Restart
// and Shut down, ticked for the one restart that follows and shown ticked
// while it is armed; a bare-metal install's alone.
function holdNextBox(){
  if (!state?.bare_metal) return "";
  const armed = !!state?.held?.armed;
  return `<label class="ndcap holdnext" title="the restart after this one comes back with nothing running, for a look first"><input type="checkbox" data-holdnextbox${armed ? " checked" : ""}> hold the next start</label>`;
}
function wireHoldNext(root){
  root.querySelectorAll("[data-holdnextbox]").forEach(c => c.onchange = async () => {
    const on = c.checked;
    c.disabled = true;
    const j = await (await postJSON("/api/v1/nodes", {action: "hold-next", on})).json().catch(() => ({error: "no answer"}));
    notify(j.error || (on ? "the next start is held: nothing runs after the restart until Start is pressed on This machine" : "the next start runs as usual"), !!j.error);
    await refresh();
  });
}

// Older versions (R201, the operator, 1 Nov): what updates pushed out of
// their slots, each one on the boot menu. Boot this next is one visit: the
// boot after is the version it came from again.
function olderVersionsSection(n){
  const k = n?.reported?.os_kept;
  if (!k?.booted && !(k?.versions || []).length) return "";
  const admin = !!state?.can?.admin, busy = (n.jobs || []).some(j => j.apply === "os-kept"), dead = busy || !n.live;
  const rows = (k.versions || []).map(v => `<div class="row" data-oskept="${esc(v.version)}"><div class="grow"><span class="name">${esc(v.version)}</span>
      <div class="sub dim">${v.mb >= 1024 ? `${(v.mb / 1024).toFixed(1)} GB` : `${v.mb} MB`}, kept ${esc(ago(v.at))}${v.state ? ", with its configuration" : ""}</div></div>
      ${admin && k.booted !== v.version ? `<div class="acts"><button type="button" data-oskeptdo="next"${dead ? " disabled" : ""}>Boot this next</button><button type="button" class="danger" data-oskeptdo="remove"${dead ? " disabled" : ""}>Remove</button></div>` : ""}</div>`).join("");
  return docSection("nodes", "older", "Older versions", k.booted ? `visiting ${k.booted}` : String(k.versions.length), `<div class="field">
      ${k.booted ? `<div class="hint warn">This boot is a visit to ${esc(k.booted)}. Restart to go back to the version it came from; updates wait until then.</div>` : ""}
      ${rows}${busy ? `<div class="sub dim">Working on it now.</div>` : !n.live ? `<div class="sub dim">Its agent is not dialing in.</div>` : ""}
      <div class="hint">Each version an update replaced, also under Older versions on the boot menu. A visit lasts one boot. If the configuration has moved on further than that version reads, the copy from when it was left is used, and yours comes back when you restart. Your projects, shares and VMs are not part of it. How many are kept is under Update window.</div></div>`);
}
function wireOlderVersions(root){
  root.querySelectorAll("[data-oskeptdo]").forEach(b => b.onclick = () => pressing(b, async () => {
    const verb = b.dataset.oskeptdo, version = b.closest("[data-oskept]")?.dataset.oskept || "";
    if (!await askYes(verb === "next"
        ? `Boot ${version} next?\n\nOnce, at the next restart; the boot after is this version again. Nothing restarts until you do.`
        : `Remove ${version} from this machine?\n\nIt goes from the boot menu and its files are deleted. A release can be installed again by updating to it.`,
        {title: verb === "next" ? "Boot it next?" : "Remove it?", verb: verb === "next" ? "Boot it next" : "Remove", danger: verb !== "next"})) return;
    busy(b, verb === "next" ? "Setting" : "Removing");
    const j = await (await postJSON("/api/v1/nodes", {action: "os-kept", id: ownMachine()?.id || "", verb, version})).json().catch(() => ({error: "no answer"}));
    notify(j.error || (verb === "next" ? `${version} boots next, once: restart from Advanced` : `removing ${version}`), !!j.error);
    await loadNodes();
  }));
}

// The stick (R161 step 10, the operator, 29 Oct: read once and written
// rarely): the system runs from RAM, the stick keeps the configuration, and
// what writes all day (docker, the VMs, the toolchains, the projects) is on
// the system pool picked here, or waits for one. What still lives on the
// stick and what it has written, in the facts voice.
const STICK_WORDS = {docker: "docker's images", containerd: "containers' layers", libvirt: "the VMs", toolchains: "the toolchains", projects: "the projects"};
function stickSection(n){
  const s = n?.reported?.os_stick;
  if (!s?.stick) return "";
  const gb = kb => kb === null || kb === undefined ? "" : kb >= 1048576 ? `${(kb / 1048576).toFixed(1)} GB` : `${Math.round(kb / 1024)} MB`;
  const mounts = [...(n.reported?.pools || []).filter(p => p.mount).map(p => [p.mount, `${p.name} (${p.mount})`]),
                  ...(n.reported?.array?.mount ? [[n.reported.array.mount, `the array (${n.reported.array.mount})`]] : [])];
  const busy = (n.jobs || []).some(j => j.apply === "system-pool");
  const admin = !!state?.can?.admin;
  const rows = [
    ["Runs from", "memory: the stick is read at boot"],
    ["On the stick", (s.on_stick || []).length ? `the configuration, and ${s.on_stick.map(k => STICK_WORDS[k] || k).join(", ")}` : "the configuration alone"],
    ["Docker and the VMs", s.ready ? `on ${s.pool}` : s.pool ? `waiting for ${s.pool} to mount` : "waiting for a system pool", {cls: s.ready ? "ok" : "warn"}],
    ["The projects", s.projects ? (s.projects_bound ? `in ${s.projects}` : `${s.projects}, waiting for its disks`) : s.ready ? `on ${s.pool}` : "held until a pool or a folder on the disks is named: none is made on the stick",
     {cls: s.projects ? (s.projects_bound ? "ok" : "warn") : s.ready ? "" : "warn"}],
    ["Written to the stick", [gb(s.written_kb) && `${gb(s.written_kb)} in its life`, gb(s.boot_written_kb) && `${gb(s.boot_written_kb)} since this boot`].filter(Boolean).join(", ")],
  ];
  const why = !mounts.length ? "No pool or array here yet: make one on the Storage page, then pick it here."
    : !n.live ? "Its agent is not dialing in." : busy ? "Moving to the pool now: docker and the VMs are stopped until it ends." : "";
  const pick = admin ? `<div class="actbar"><label class="pick"><span class="pickw">System pool</span><select id="stickPool" aria-label="system pool"${why ? " disabled" : ""}>${
      optionList([...(s.pool ? [] : [["", "pick a pool"]]), ...mounts], s.pool || "")}</select></label><span class="sp"></span>
      <button type="button" class="primary" data-stickpool${why ? " disabled" : ""}>${s.pool ? "Move to this pool" : "Use this pool"}</button></div>
      ${why ? `<div class="sub dim">${esc(why)}</div>` : ""}` : "";
  return docSection("nodes", "stick", "The stick", s.ready ? "written rarely" : (s.on_stick || []).length ? "writes on the stick" : "waiting for a pool",
    `<div class="field">${factGrid(rows, "stickfacts")}${pick}<div class="hint">Docker, the VMs, the toolchains and the projects write all day, so they live on a pool, never on the stick; until one is picked, docker and the VMs wait, no project can be made, and the logs and the journal are kept in memory.</div></div>${projectsFolderField(n, s, admin)}`,
    {cls: s.ready ? "" : "warn"});
}

// A projects folder of the machine's own (R163, the operator, 1 Nov): a
// controller moved here without its repositories takes the folder its
// projects already sit in on the adopted disks, nothing copied. Offered
// where those disks are: the plan's shares, then the merged views.
function projectsFolderField(n, s, admin){
  if (!admin) return "";
  const ad = n.reported?.adopted || {};
  const roots = Object.keys(ad.merged || {}).filter(k => ad.merged[k]);
  const pools = [...(n.reported?.pools || []).map(p => p.mount), n.reported?.array?.mount].filter(Boolean);
  if (!roots.length && !pools.length) return "";
  const shares = (state.firstboot?.shares?.rows || []).map(r => r.path).filter(p => typeof p === "string" && p.startsWith("/"));
  const offer = [...new Set([...shares, ...roots.map(r => `${r}/projects`)])];
  const busy = (n.jobs || []).some(j => j.apply === "projects-folder");
  const why = !n.live ? "Its agent is not dialing in." : busy ? "Taking the folder now: the controller restarts on it when it ends." : "";
  return `<div class="field"><div class="fx"><label class="pick grow"><span class="pickw">Projects folder</span><input id="projFolder" list="projFolderOffer" spellcheck="false"
      value="${esc(s.projects || "")}" placeholder="${esc(offer[0] || (roots[0] || pools[0]) + "/projects")}" aria-label="the projects folder"${why ? " disabled" : ""}></label>
      <datalist id="projFolderOffer">${offer.map(p => `<option value="${esc(p)}">`).join("")}</datalist></div>
    <div class="actbar"><span class="sp"></span>${s.projects ? `<button type="button" data-projfolder="release"${why ? " disabled" : ""}>Let it go</button>` : ""}
      <button type="button" class="primary" data-projfolder="use"${why ? " disabled" : ""}>Use this folder</button></div>
    ${why ? `<div class="sub dim">${esc(why)}</div>` : ""}
    <div class="hint">Where the projects already are on these disks, as another system kept them (its share for the projects): the controller works in that folder in place, nothing copied, so a move here can leave its repositories out. Its files become BuilderBot's own; nothing in them changes.</div></div>`;
}
function wireStick(root){
  root.querySelectorAll("[data-projfolder]").forEach(pb => pb.onclick = () => pressing(pb, async () => {
    const release = pb.dataset.projfolder === "release", path = (root.querySelector("#projFolder")?.value || "").trim();
    if (!release && !path) return notify("name the folder the projects are in first", true);
    if (!await askYes(release
        ? "Let the projects folder go?\n\nThe controller restarts on the pool's projects folder (or the stick's). The folder and its files stay where they are."
        : `Take ${path} as the projects folder?\n\nThe controller restarts and works in it from then on, every boot. Its files are handed to BuilderBot's own account, so git and the controller can write them: their owner changes, nothing in them does. What the projects folder held before stays underneath, unseen.`,
        {title: release ? "Let it go?" : "Use this folder?", verb: release ? "Let it go" : "Use it"})) return;
    busy(pb, release ? "Letting go" : "Taking it");
    const j = await (await postJSON("/api/v1/nodes", {action: "projects-folder", id: ownMachine()?.id || "", path, release})).json().catch(() => ({error: "no answer"}));
    notify(j.error || "taking the folder: the job says which projects it found, and the controller restarts on it", !!j.error);
    await loadNodes();
  }));
  const b = root.querySelector("[data-stickpool]"), sel = root.querySelector("#stickPool");
  if (!b || !sel) return;
  b.onclick = () => pressing(b, async () => {
    const path = sel.value;
    if (!path) return notify("pick a pool first", true);
    if (!await askYes(`Put docker, the VMs, the toolchains and the projects on ${path}?\n\nDocker and the VMs stop while what the stick holds of theirs is moved there, and start again on the pool. From then on they write there, and the stick keeps the configuration alone.`,
        {title: "Use this pool?", verb: "Move"})) return;
    busy(b, "Moving");
    const j = await (await postJSON("/api/v1/nodes", {action: "system-pool", id: ownMachine()?.id || "", path})).json().catch(() => ({error: "no answer"}));
    notify(j.error || "moving to the pool: This machine says when it is done", !!j.error);
    await loadNodes();
  });
}

// A way in at the screen (R194): BuilderBot OS's console takes a password
// set here, logging in as admin with sudo for root; the boot menu's Rescue
// entry is the way in when nothing else answers. Only on BuilderBot OS.
function machineConsoleSection(n){
  const c = n.reported?.console;
  if (!c?.os) return "";
  return docSection("nodes", "console", "Console", c.set ? "password set" : "no password", `<div class="field">
      <div class="hint">At this machine's screen or a KVM, log in as <code>admin</code> with the console password; <code>sudo</code> gives root. It is not your dashboard password, and it is kept on the machine, not here. When nothing else answers, the boot menu's Rescue entry opens a root shell at the screen.</div>
      <div class="fx"><label class="pick"><span class="pickw">Password</span><input type="password" id="conPw" autocomplete="new-password" placeholder="ten characters at least" aria-label="the console password"></label>
        <label class="pick"><span class="pickw">Again</span><input type="password" id="conPw2" autocomplete="new-password" aria-label="the console password again"></label></div>
      <div class="actbar">${c.set ? `<button type="button" class="danger" data-console="clear">Take it away</button>` : ""}<button type="button" class="primary" data-console="set">${c.set ? "Change it" : "Set it"}</button></div></div>`);
}

function wireMachineConsole(root){
  root.querySelectorAll("[data-console]").forEach(b => b.onclick = () => pressing(b, async () => {
    const clear = b.dataset.console === "clear", n = ownMachine();
    const pw = $("conPw")?.value || "", pw2 = $("conPw2")?.value || "";
    if (!clear && pw !== pw2) return notify("the two passwords differ", true);
    if (clear && !await askYes("Take the console password away?\n\nNobody can log in at the screen as admin until one is set again; the boot menu's Rescue entry still opens a root shell there.",
        {title: "Take it away?", verb: "Take it away", danger: true})) return;
    busy(b, clear ? "Taking it away" : "Setting");
    const j = await (await postJSON("/api/v1/nodes", {action: "console", id: n?.id || "", ...(clear ? {clear: true} : {password: pw})})).json().catch(() => ({error: "no answer"}));
    notify(j.error || (clear ? "taking the console password away" : "setting it: log in at the screen as admin"), !!j.error);
    await loadNodes();
  }));
}

// What a stick's prepared configuration did at the first boot (R161 step 8,
// firstboot.py): each piece applied, waiting for disks to be adopted, or not
// applied with why, in the facts voice. Nothing on an install that had none.
function firstbootSection(){
  const f = state?.firstboot;
  if (!f) return "";
  const line = (x, cls) => [x.what, `${x.said}${x.count ? ` (${x.count})` : ""}`, {cls}];
  const rows = [...(f.done || []).map(x => line(x, "ok")), ...(f.waiting || []).map(x => line(x, "")), ...(f.failed || []).map(x => line(x, "warn"))];
  const status = (f.failed || []).length ? `${f.failed.length} not applied` : (f.waiting || []).length ? `${f.waiting.length} waiting` : "applied";
  return docSection("nodes", "firstboot", "From the stick", status,
    `<div class="field">${factGrid(rows, "fbfacts")}<div class="hint">Taken off the stick at the first boot ${esc(ago(f.at))} and blanked there; what waits is applied once its disks are adopted.</div></div>`);
}

// The disks and pools the stick's plan names, adopted as they are (R163
// steps 8 and 9): each found here by its serial or not, the parity disk
// left alone, read only or writable said in what each costs, Check for the
// dry run and Adopt; once adopted, what is mounted where and Release.
let adoptWritable = false;
function adoptFound(n, id){
  const disks = n.reported?.disks || [];
  return disks.find(d => { const link = String(d.by_id || "").split("/").pop();
    return link === id || link.endsWith("-" + id) || link.endsWith("_" + id) || (d.serial && String(d.serial).length >= 4 && (id === d.serial || id.endsWith("_" + d.serial))); });
}
function adoptSection(n){
  const had = n.reported?.adopted;
  if (had && (had.mounts || []).length){
    const rows = [...had.mounts.map(m => [m.where, `${m.fs}, ${m.ro ? "read-only" : "writable"}${m.mounted ? "" : ", not mounted yet"}`, {cls: m.mounted ? "" : "warn"}]),
      ...Object.entries(had.merged || {}).map(([w, up]) => [w, up ? "merged" : "merged, not mounted yet", {cls: up ? "" : "warn"}]),
      ...(had.parity || []).map(p => ["parity", `${p}, left alone`])];
    return docSection("nodes", "adopted", "Adopted disks", had.writable ? "writable" : "read-only",
      `<div class="field">${factGrid(rows, "adfacts")}<div class="hint">${had.writable
        ? "Writable: going back to the old system takes a parity sync, which leaves its array unprotected until it ends."
        : "Read-only: nothing on a data disk is written, so the old system's parity stays good. New files land on a pool."}</div>
        ${adoptSharesLine()}
        <div class="actbar"><button type="button" class="danger" data-adopt="release">Release</button>${
          (state?.firstboot?.shares?.rows || []).length ? `<button type="button" class="primary" data-adoptshares>Serve the shares</button>` : ""}</div></div>`);
  }
  const a = state?.firstboot?.adopt;
  if (!a) return "";
  const w = a.want || {};
  const found = id => adoptFound(n, id);
  const rows = [
    ...(w.data || []).map(x => { const d = found(x.id);
      return [x.slot, `${x.fs} · ${x.id}${d ? ` · here as ${d.name}` : " · not on this machine"}`, {cls: d ? "" : "warn"}]; }),
    ...(w.parity || []).map(x => { const d = found(x.id);
      return [x.slot, `${x.id}${d ? ` · here as ${d.name}, left alone` : " · not on this machine"}`]; }),
    ...(w.pools || []).map(p => [p.name, `${p.fs} pool, writable`]),
    ...(a.skipped || []).map(x => [x.slot || "disk", `${x.id} · ${x.why}`, {cls: "warn"}])];
  const missing = (w.data || []).filter(x => !found(x.id)).length;
  return docSection("nodes", "adopt", "Disks from the stick", missing ? `${missing} not here` : `${(w.data || []).length} disks, ${(w.pools || []).length} pools`,
    `<div class="field">${factGrid(rows, "adfacts")}
      <div class="adpick">
        <label class="ndcap"><input type="radio" name="adoptMode" value="ro"${adoptWritable ? "" : " checked"}> Read only: the old system's parity stays good, and new files land on a pool</label>
        <label class="ndcap"><input type="radio" name="adoptMode" value="rw"${adoptWritable ? " checked" : ""}> Writable: going back to the old system then takes a parity sync</label>
      </div>
      <div class="hint">Each disk is mounted as it is, never formatted or partitioned, at the path it had, and the merged folders are made again, so what pointed at them finds its files.</div>
      <div class="actbar"><button type="button" data-adopt="dry">Check</button><button type="button" class="primary" data-adopt="adopt">Adopt</button></div></div>`, {open: true});
}

// The containers and VMs the old system ran (R163 steps 10 and 11): read
// from its Docker and libvirt image files once the disks are adopted, the
// containers made again here as Containers page containers with the exact
// image each ran, the VMs defined in this machine's libvirt, each started
// with the machine where it was. The list of what would be made is the
// controller's (adopt-apps plan), fetched once a read lands.
let adoptPlan = null, adoptPlanFor = "";
// What the person unticked, kept across redraws: "c:NAME" a container, "v:NAME"
// a VM (the operator, 1 Nov: pick which to bring back, not all of them).
const adoptSkip = new Set();
function adoptAppsSection(n){
  const had = n.reported?.adopted, from = state?.firstboot?.apps_from;
  if (!had || !(had.mounts || []).length || !from) return "";
  const apps = had.apps;
  const btn = (attr, word, cls = "") => `<button type="button"${cls ? ` class="${cls}"` : ""} ${attr}>${word}</button>`;
  if (!apps){
    return docSection("nodes", "adoptapps", "Containers and VMs from the old system", "not read yet",
      `<div class="field"><div class="hint">Its Docker and VMs keep what ran in two image files on the adopted disks (${esc(from.docker?.image || "no Docker image")}; ${esc(from.vms?.image || "no VM image")}). Reading opens each read-only: nothing in them changes, and neither is run.</div>
        <div class="actbar">${btn('data-adoptapp="read"', "Read what ran", "primary")}</div></div>`);
  }
  const key = JSON.stringify(apps.docker?.digests || {}) + (had.writable ? "w" : "r");
  if (adoptPlanFor !== key){ adoptPlanFor = key; adoptPlan = null; loadAdoptPlan(); }
  // Each a tick, ticked unless the person took it off; what cannot be made
  // is said and has none.
  const pick = (key, label, said, on, warn = false) => `<label class="ndcap adrow"><input type="checkbox" data-adpick="${esc(key)}"${on ? " checked" : ""}${on === null ? " disabled" : ""}>
      <b>${esc(label)}</b> <span class="sub${warn ? " warn" : ""}">${esc(said)}</span></label>`;
  const rows = (adoptPlan || []).map(a => pick(`c:${a.name}`, a.name,
    `${a.network}${a.autostart ? " · starts with the machine" : ""}${a.notes.length ? " · " + a.notes.join("; ") : ""}`,
    a.ok ? !adoptSkip.has(`c:${a.name}`) : null, a.notes.length > 0)).join("");
  const other = Object.fromEntries((n.reported?.vms_other || []).map(v => [v.name, v]));
  const vms = (apps.vms || []).map(v => { const here = other[v.name];
    return here ? `<div class="ndcap adrow"><b>${esc(v.name)}</b> <span class="sub">${esc(`${here.state}${here.autostart ? " · starts with the machine" : ""}`)}</span></div>`
      : pick(`v:${v.name}`, v.name, `not defined here yet${v.autostart ? " · started with the machine there" : ""}`, !adoptSkip.has(`v:${v.name}`)); }).join("");
  const nC = (adoptPlan || []).filter(a => a.ok && !adoptSkip.has(`c:${a.name}`)).length;
  const nV = (apps.vms || []).filter(v => !other[v.name] && !adoptSkip.has(`v:${v.name}`)).length;
  const nets = Object.entries(from.networks || {});
  const vmActs = (apps.vms || []).filter(v => other[v.name]).map(v => { const s = other[v.name];
    return `<div class="actbar"><span class="grow">${esc(v.name)}</span>${s.state === "running"
      ? btn(`data-adoptvm="shutdown" data-vmname="${esc(v.name)}"`, "Shut down") : btn(`data-adoptvm="start" data-vmname="${esc(v.name)}"`, "Start")}${
      btn(`data-adoptvm="${s.autostart ? "autostart-off" : "autostart-on"}" data-vmname="${esc(v.name)}"`, s.autostart ? "Don't start with the machine" : "Start with the machine")}</div>`; }).join("");
  return docSection("nodes", "adoptapps", "Containers and VMs from the old system",
    `${(adoptPlan || []).length} containers, ${(apps.vms || []).length} VMs`,
    `<div class="field">${(apps.said || []).map(x => `<div class="sub">${esc(x)}</div>`).join("")}
      ${adoptPlan === null ? skRows(2) : `<div class="adpick">${rows}</div>`}
      <div class="hint">Each is made with the exact image it ran and its paths as they were, so it finds its files where they were. A container or VM made new here goes where BuilderBot keeps its own.</div>
      <div class="actbar">${nets.map(([k, v]) => btn(`data-adoptnet="${esc(k)}" data-subnet="${esc(v.subnet)}" data-gateway="${esc(v.gateway)}"`, `Make the ${esc(k)} network`)).join("")}
        ${btn(`data-adoptapp="make"${nC ? "" : " disabled"}`, `Make and start ${nC === (adoptPlan || []).filter(a => a.ok).length ? "the containers" : nC ? `the ${nC} ticked` : "the ticked"}`, "primary")}</div>
      ${(apps.vms || []).length ? `<div class="sub">The VMs</div><div class="adpick">${vms}</div>${vmActs}
        <div class="actbar">${(apps.vms || []).some(v => !other[v.name]) ? btn(`data-adoptapp="define"${nV ? "" : " disabled"}`, nV === (apps.vms || []).filter(v => !other[v.name]).length ? "Define the VMs" : nV ? `Define the ${nV} ticked` : "Define the ticked", "primary") : ""}</div>` : ""}
    </div>`);
}

async function loadAdoptPlan(){
  const j = await (await postJSON("/api/v1/nodes", {action: "adopt-apps", op: "plan", id: ownMachine()?.id || ""})).json().catch(() => ({error: "no answer"}));
  adoptPlan = j.apps || [];
  nodesRev++; drawPanes();
}

function wireAdoptApps(root){
  const n = ownMachine();
  root.querySelectorAll("[data-adpick]").forEach(c => c.onchange = () => {
    if (c.checked) adoptSkip.delete(c.dataset.adpick); else adoptSkip.add(c.dataset.adpick);
    nodesRev++; drawPanes();
  });
  root.querySelectorAll("[data-adoptapp]").forEach(b => b.onclick = () => pressing(b, async () => {
    const act = b.dataset.adoptapp, from = state?.firstboot?.apps_from || {};
    if (act === "read"){
      busy(b, "Reading");
      const j = await (await postJSON("/api/v1/nodes", {action: "storage-adopt", id: n.id, adopt: "read-apps", docker: from.docker, vms: from.vms})).json().catch(() => ({error: "no answer"}));
      notify(j.error || "reading: the containers and VMs it ran are listed here when it is done", !!j.error);
    } else if (act === "define"){
      const other = new Set((n.reported?.vms_other || []).map(v => v.name));
      const names = (n.reported?.adopted?.apps?.vms || []).map(v => v.name).filter(x => !other.has(x) && !adoptSkip.has(`v:${x}`));
      if (!await askYes(`Define ${names.length} VM${names.length === 1 ? "" : "s"} in this machine's libvirt?\n\n${names.join(", ")}\n\nEach keeps its disks where they are; its network bridge becomes the LAN through this machine's interface, and those that started with the machine there do here.`,
          {title: "Define the VMs?", verb: "Define"})) return;
      busy(b, "Defining");
      const j = await (await postJSON("/api/v1/nodes", {action: "storage-adopt", id: n.id, adopt: "define-vms", names})).json().catch(() => ({error: "no answer"}));
      notify(j.error || "defining: its job says each VM's changes", !!j.error);
    } else {
      const names = (adoptPlan || []).filter(a => a.ok && !adoptSkip.has(`c:${a.name}`)).map(a => a.name);
      busy(b, "Making");
      const m = await (await postJSON("/api/v1/nodes", {action: "adopt-apps", op: "make", id: n.id, names})).json().catch(() => ({error: "no answer"}));
      if (m.error){ notify(m.error, true); return; }
      const go = (m.made || []).filter(x => x.autostart);
      const asks = go.filter(x => x.risks.length).map(x => `${x.name}: ${x.risks.slice(0, 4).join("; ")}`);
      if (go.length && (!asks.length || await askYes(`Start the ${go.length} that started with the machine there?\n\nWhat they ask for beyond their own folder, acknowledged by this press:\n${asks.join("\n")}`,
          {title: "Start them?", verb: "Start"}))){
        const s = await (await postJSON("/api/v1/nodes", {action: "adopt-apps", op: "start", id: n.id, rows: go.map(x => ({slug: x.slug, ack: x.ack}))})).json().catch(() => ({error: "no answer"}));
        notify(s.error || `made ${(m.made || []).length}, starting ${(s.started || []).length}${(s.failed || []).length ? `; not ${s.failed.map(x => x.slug).join(", ")}` : ""}${(m.skipped || []).length ? `; skipped ${m.skipped.map(x => x.name).join(", ")}` : ""}: the Containers page shows each`, !!(s.error || (s.failed || []).length));
      } else notify(`made ${(m.made || []).length}${(m.skipped || []).length ? `; skipped ${m.skipped.map(x => `${x.name} (${x.why})`).join(", ")}` : ""}: start each from the Containers page`);
    }
    await loadNodes();
  }));
  root.querySelectorAll("[data-adoptnet]").forEach(b => b.onclick = () => pressing(b, async () => {
    busy(b, "Making");
    const j = await (await postJSON("/api/v1/nodes", {action: "storage-adopt", id: n.id, adopt: "docker-network", name: b.dataset.adoptnet, subnet: b.dataset.subnet, gateway: b.dataset.gateway})).json().catch(() => ({error: "no answer"}));
    notify(j.error || `making the ${b.dataset.adoptnet} network`, !!j.error);
    await loadNodes();
  }));
  root.querySelectorAll("[data-adoptvm]").forEach(b => b.onclick = () => pressing(b, async () => {
    busy(b, "Asking");
    const j = await (await postJSON("/api/v1/nodes", {action: "storage-adopt", id: n.id, adopt: "vm", name: b.dataset.vmname, op: b.dataset.adoptvm})).json().catch(() => ({error: "no answer"}));
    notify(j.error || `${b.dataset.vmname}: ${b.dataset.adoptvm.replace("-", " ")}`, !!j.error);
    await loadNodes();
  }));
}

// The plan's shares, served from the merged tree once the disks are here:
// how many, and what of theirs cannot be carried.
function adoptSharesLine(){
  const s = state?.firstboot?.shares;
  if (!s || !(s.rows || []).length) return "";
  return `<div class="hint">The stick's ${s.rows.length} share${s.rows.length === 1 ? "" : "s"} (${s.rows.map(r => esc(r.name)).join(", ")}) can be served from /mnt/user as they were.${
    (s.notes || []).map(x => ` ${esc(x.name)}: ${esc(x.said)}.`).join("")}</div>`;
}

function wireAdopt(root){
  root.querySelectorAll("[data-adoptshares]").forEach(b => b.onclick = () => pressing(b, async () => {
    const n = ownMachine(), rows = state?.firstboot?.shares?.rows || [];
    if (!n || !rows.length) return;
    busy(b, "Serving");
    const j = await (await postJSON("/api/v1/nodes", {action: "storage-share", id: n.id, share: "set-many", shares: rows})).json().catch(() => ({error: "no answer"}));
    notify(j.error || `serving ${rows.length - (j.skipped || []).length} shares${(j.skipped || []).length ? `; not ${j.skipped.map(x => `${x.name} (${x.why})`).join(", ")}` : ""}`, !!j.error);
    await loadNodes();
  }));
  root.querySelectorAll('input[name="adoptMode"]').forEach(r => r.onchange = () => { adoptWritable = r.value === "rw"; });
  root.querySelectorAll("[data-adopt]").forEach(b => b.onclick = () => pressing(b, async () => {
    const act = b.dataset.adopt, n = ownMachine();
    if (!n) return;
    if (act === "release" && !await askYes("Unmount every adopted disk and pool and forget them?\n\nEach disk is left as it is. Containers and VMs using them stop finding their files.",
        {title: "Release the disks?", verb: "Release", danger: true})) return;
    if (act === "adopt" && adoptWritable && !await askYes("Adopt the data disks writable?\n\nA file written to one is a write the old system's parity did not see: going back to it then takes a parity sync, which leaves its array unprotected until it ends.",
        {title: "Writable?", verb: "Adopt writable"})) return;
    busy(b, act === "dry" ? "Checking" : act === "adopt" ? "Adopting" : "Releasing");
    const want = act === "release" ? undefined : {...(state?.firstboot?.adopt?.want || {}), writable: adoptWritable};
    const j = await (await postJSON("/api/v1/nodes", {action: "storage-adopt", id: n.id, adopt: act, ...(want ? {want} : {})})).json().catch(() => ({error: "no answer"}));
    notify(j.error || (act === "dry" ? "checking: its job says each mount, on the node's Jobs" : act === "adopt" ? "adopting: This machine shows each mount as it lands" : "releasing"), !!j.error);
    await loadNodes();
  }));
}

function wireHeld(root){
  root.querySelectorAll("[data-heldstart]").forEach(b => b.onclick = () => pressing(b, async () => {
    busy(b, "Starting");
    const j = await (await postJSON("/api/v1/nodes", {action: "start-held"})).json().catch(() => ({error: "no answer"}));
    notify(j.error || "started: sessions run again", !!j.error);
    await refresh();
  }));
  wireHoldNext(root);
  wireStick(root);
  wireAdopt(root);
  wireAdoptApps(root);
  wireMachineConsole(root);
}
