// The Settings tab: controller-scoped settings, graduated out of the gear
// popup the moment there was more than a flyout's worth (docs/nodes.md §13).
// The gear keeps the per-browser items (theme, layout) and one entry that
// opens this; everything the CONTROLLER owns and can apply live belongs here,
// where it has room to say what it does and what it costs.
//
// Its own classic script beside index.html, per the new-surface rule. Chrome
// from docSurface(); conformance held by uniform.mjs.

// The tab repaints when what it shows has moved on the poll: a value saved
// here, or by another window, and not otherwise, so typing is not swept
// away by a poll that changed nothing. A string, compared whole by drawPanes.

"use strict";

// What the controller offers and holds of its companions (apps.view), for
// the Apps section here and the Library's Companions cards (the Apps page's
// read until R170).
let devApps = null, devAppsRev = 0;
async function loadApps(){
  // Switched off on this install (R81): the route refuses, so it is not asked.
  if (featureOff("apps")){ devAppsRev++; return; }
  try{
    const r = await bootFetch("/api/apps");
    const j = await r.json();
    if (!j.error) devApps = j;
  }catch(e){ /* the section says it could not read them */ }
  devAppsRev++;
  if (tabs.some(t => t.kind === "settings")) drawPanes();
}

// Revert on a section puts its fields back to what is saved: the draft for
// them dropped and the tab repainted, which the live key has to notice.
let settingsRev = 0;
function settingsLive(){
  return JSON.stringify([state?.settings?.settings, state?.settings?.tunnel, state?.idle, state?.logs, state?.paths, settingsRev, devAppsRev, state?.checks]);
}

// Typed and not yet applied, by control id, across the tab's redraws: one
// section's Apply repaints the whole tab from the poll, and must not throw
// away what was typed into another (docs/design-language.md, Settings).
const settingsDraft = {};
const sdVal = (id, value) => settingsDraft[id] ?? value;
// Each field's saved value, read when it is drawn with no draft over it,
// so an edit back to it is no change and its section's Apply and Revert
// sleep again (R218 step 32, as Profile's do).
const settingsSaved = {};
const SETTINGS_FIELDS = "input[data-set], select[data-set], #idleMin, #logDays, input[data-path]";
function settingsKeep(el){
  const val = i => i.type === "checkbox" ? i.checked : i.value;
  el.querySelectorAll(SETTINGS_FIELDS).forEach(i => {
    if (!(i.id in settingsDraft)) settingsSaved[i.id] = val(i);
    const on = () => {
      const v = val(i);
      if (i.id in settingsSaved && v === settingsSaved[i.id]) delete settingsDraft[i.id];
      else settingsDraft[i.id] = v;
      settingsWake(el);
    };
    i.oninput = on; i.onchange = on;
  });
  el.querySelectorAll("[data-clear]").forEach(i => { i.addEventListener("change", () => settingsWake(el)); });
  settingsWake(el);
}
// A section's Apply and Revert awake only while one of its fields differs
// from what is saved, or a stored secret is ticked to go: the Logs section's
// too (the operator, 26 Oct: every save bar asleep with nothing to save).
function settingsWake(el){
  el.querySelectorAll("details.sect").forEach(sec => {
    const dirty = [...sec.querySelectorAll(SETTINGS_FIELDS)].some(i => i.id in settingsDraft)
      || !!sec.querySelector("[data-clear]:checked");
    sec.querySelectorAll(".setApply, #logApply, #idleApply, #pathsApply, [data-srevert]").forEach(b => {
      if (!b.dataset.busy && b.disabled !== !dirty) b.disabled = !dirty;
    });
  });
}

function openSettingsTab(){
  // The name the button that opens it uses, and the one the tab's own first
    // line uses. "Settings" alone competes with a project's settings dialog
    // and with the gear, which is this browser's appearance.
    openTab({kind: "settings", arg: "__settings", label: "Controller settings"});
}

// Each section's line on the list beside it: what is in it.
const SETTINGS_SAYS = {
  logs: "days kept, following, downloads", reports: "what was reported about AerieOS, and the diagnostics",
  idle: "when an idle session is ended", paths: "the shares and disks this controller uses",
  tunnel: "a hostname that reaches it from outside",
  apps: "the apps your people install, kept current",
  mail: "the SMTP server the bell goes out through",
  move: "to another home, its nodes following",
  updates: "the release running, the newest, and Update",
  power: "restart the machine, or shut it down",
  updwin: "when a newer release is applied by itself",
  backup: "the password the copies are sealed under",
  copies: "the copies kept on the disks, and one now",
  reset: "start over at the setup page",
};

function renderSettingsInto(i){
  const d = docSurface(i, "settings");
  if (!d) return;
  // The build and the uptime live here now (R218 step 2, the top-bar rule):
  // facts in the facts voice, where the header carried them before.
  // ...and no sentence about the page beside them (the operator, 18 Oct).
  // The controller's build and how long it has been up, as a node's head
  // says what a machine is (the operator, 25 Oct: no loose words at the top).
  d.setBar("");
  const img = state?.image || {};
  const head = pageHead({title: "This controller", facts: [
    ["Version", img.version || "unstamped"],
    ["Commit", (img.rev || "").slice(0, 7)],
    ["Up", shortUptime(state?.uptime || 0)]]});
  // Sections, like every other tab's (the operator, 11 Oct): one fold per
  // group, its status on the heading, a jump bar over them, and each with
  // its own Apply and Revert. The groups' own markup is kept inside (the
  // suites and the keepers address it), the heading taking the h4's place.
  const idle = state?.idle?.minutes;
  const paths = state?.paths?.paths || [];
  const t = state?.settings?.tunnel;
  const sect = (key, title, status, html, opts = {}) =>
    docSection("settings", key, title, status, html.replace(/<h4>[^<]*<\/h4>\s*/, ""), opts);
  // Before the first poll lands, the page's own placeholder (B647): every
  // section it will have, shimmering, rather than the few that need no
  // state and then the rest. Drawn whole again when the settings arrive.
  if (!state?.settings){
    const titles = [["logs", "Logs"], ["reports", "AerieOS bug reports"], ["idle", "Idle sessions"], ["paths", "Storage on this controller"],
      ...SETTING_GROUPS.filter(g => !g.debug && !g.bare && !NETWORK_GROUPS.includes(g.key)).map(g => [g.key, g.title]),
      ["copies", "Backup copies"], ["move", "Move this controller"], ["reset", "Reset AerieOS"]];
    d.list.innerHTML = `${head}<div class="sectjump" data-sects></div>
      ${titles.map(([k, t]) => sect(k, t, "", `<div class="field loading">${skRows(2)}</div>`)).join("")}`;
    sectJump(d.list.querySelector("[data-sects]"));
    return;
  }
  // Reach from outside and Connection are the Network page's now (R165
  // step 4, tab-network.js), drawn from the same table.
  const groups = settingsSections().filter(g => !NETWORK_GROUPS.includes(g.key));
  // The logs are an administrator's: a poll that has landed without them
  // means this account has no Logs section, not one still on its way (B38).
  const logs = logSection();
  d.list.innerHTML = `${head}<div class="sectjump" data-sects></div>
    ${logs || !state ? sect("logs", "Logs", "", `<div class="row stack2" data-group="Logs"><div class="grow">${withRevert(logs, "logs")
        || `<div class="sub">log settings arrive with the first poll…</div>`}</div></div>`) : ""}
    ${sect("reports", "AerieOS bug reports", reportsCount() === null ? "" : reportsCount() ? `${reportsCount()} report${reportsCount() === 1 ? "" : "s"}` : "none", reportsSection())}
    ${sect("idle", "Idle sessions", idle === undefined ? "" : idle ? `${idle} min` : "never",
           `<div class="row stack2" data-group="Idle sessions"><div class="grow">${withRevert(idleSection(), "idle")}</div></div>`)}
    ${pathsSection() ? sect("paths", "Storage on this controller", `${paths.length} path${paths.length === 1 ? "" : "s"}`, withRevert(pathsSection(), "paths")) : ""}
    ${state?.release?.running !== undefined ? sect("updates", "Updates", state.release.newer ? `${state.release.newer} is out` : state.release.latest ? "up to date" : "", updatesSection()) : ""}
    ${groups.map(g => sect(g.key, g.title, g.status, withRevert(g.html, g.key), {cls: g.cls})
        // The copies made go right under the Backup group that makes them.
        + (g.key === "backup" ? sect("copies", "Backup copies", backupData?.made_at ? `last ${ago(backupData.made_at)}` : backupData?.on === false ? "off" : "", backupSection()) : "")).join("")}
    ${state?.can?.admin ? sect("move", "Move this controller", moveStatus(), moveSection()) : ""}
    ${
    // Last, apart from the settings (R218 step 32); the Nodes section that
    // only linked to the Nodes page is gone with it, the rail being the way.
    sect("reset", "Reset AerieOS", "", `<div class="field" data-group="Reset">
      <div class="hint">Start over at the setup page, un-enrolling the nodes first if you choose. Everything but space files is moved aside, not deleted.</div>
      <div class="actbar"><span class="sp"></span><button type="button" class="danger" id="setReset">Reset AerieOS</button></div>
    </div>`)}`;
  sectJump(d.list.querySelector("[data-sects]"));
  wireSections(d.el);
  // A page of settings (page-docs.js splitSects): the sections a list beside
  // the one picked, as a project's Settings are.
  splitSects(d.list, "settings", {says: SETTINGS_SAYS, back: "Controller settings"});
  d.el.querySelectorAll("[data-srevert]").forEach(b => b.onclick = () => {
    const sec = b.closest("details.sect");
    sec?.querySelectorAll("input, select").forEach(i => { if (i.id) delete settingsDraft[i.id]; });
    settingsRev++;
    drawPanes();
  });
  wireLogSection(d.el);
  wireIdleSection(d.el);
  wirePathsSection(d.el);
  wireSettingsSections(d.el);
  wireChecks(d.el);
  wireCatalogMirror(d.el);
  settingsKeep(d.el);
  if (reportsList === null) loadReports();
  const ac = d.el.querySelector("#setAppsCheck");
  if (ac) ac.onclick = async () => {
    busy(ac, "Looking");
    try{
      const j = await (await postJSON("/api/apps", {action: "check"})).json();
      if (j.error) notify(j.error, true);
    }catch(e){ notify("could not reach the controller: " + failWords(e), true); }
    // The look runs in the background; read again once it has had a moment.
    setTimeout(loadApps, 4000);
    await loadApps();
  };
  const rs = d.el.querySelector("#setReset");
  if (rs) rs.onclick = () => askReset();
  d.el.querySelectorAll("[data-repdel]").forEach(b => b.onclick = () => deleteReport(b));
  const rc = d.el.querySelector("#setReportsClear");
  if (rc) rc.onclick = () => clearReports(rc);
}

// A section's Revert beside its Apply: the first Apply button in the markup
// gets one after it, wearing the section's key.
function withRevert(html, key){
  if (!html) return html;
  const m = html.match(/<button[^>]*(id="(logApply|idleApply|pathsApply)"|class="setApply")[^>]*>Apply<\/button>/);
  if (!m) return html;
  return html.replace(m[0], `${m[0]}<button type="button" class="caution" data-srevert="${esc(key)}" title="put this section's fields back to what is saved">Revert</button>`);
}

// What sessions and people reported about AerieOS (aerie report, the
// header's Report a bug), every one listed with its delete, and the
// diagnostics download under them, which carries what is left (the
// operator, 26 Oct): a report taken out before the download is not in it.
// Whoever reads Controller settings reads them; only a session reading them
// is debug's. Read when the page draws it and after a delete, not on the poll.
let reportsList = null;
async function loadReports(){
  try{
    const j = await (await postJSON("/api/reports", {action: "list"})).json();
    if (j.error) return;
    reportsList = j.reports || [];
  }catch{ return; }
  settingsRev++;
  drawPanes();
}
const reportsCount = () => reportsList === null ? null : reportsList.length;
// A bare-metal install's updates (R90 step 5): the release running, the
// newest published, and Update, which runs the installer through this
// machine's own node; the container edition has no such section.
function updatesSection(){
  const r = state?.release || {};
  const when = r.at ? `checked ${esc(ago(r.at))}` : "not checked yet";
  const os = r.os && r.os.version ? r.os : null;
  // AerieOS (R160 step 4): the image whole into the other slot, a
  // restart to finish; elsewhere the installer's bundle (R90 step 5).
  const runs = os ? `AerieOS ${esc(os.version)} from slot ${esc(os.slot || "?")}${os.next && os.next !== os.slot ? `, and slot ${esc(os.next)} boots next: restart to finish the update` : os.trial ? ", on trial until the health check marks it good" : ""}${os.fell_back ? `; ${esc(os.fell_back)}` : ""}`
    : esc(r.running || "an unstamped build");
  const how = os ? `Update checks the release is genuine and writes it to the slot not in use. Restart to boot it; the slot running now stays to fall back to. An offline machine takes the same files from a folder here.`
    : `Update checks the release is genuine, switches to it, and comes back by itself if it does not answer.`;
  // The machine's own packages (R164 step 3), on a bare-metal install
  // that is not AerieOS: how many wait, the security ones among
  // them, and Apply updates, with a restart after when ticked.
  const h = r.host && typeof r.host.pending === "number" ? r.host : null;
  const host = !h ? "" : `<div class="sub">The system's own packages: ${h.pending ? `${h.pending} update${h.pending === 1 ? "" : "s"} waiting${h.security ? `, ${h.security} of them security` : ""}` : "up to date"}${h.checked ? ` (checked ${esc(ago(h.checked))})` : ""}${h.reboot ? `; <span class="warn">a restart is needed</span> to run the new kernel or libraries` : ""}.</div>
      <div class="field"><label class="ndcap"><input type="checkbox" id="hostReboot"> restart after, if the update asks for it</label></div>
      <div class="actbar"><span class="sp"></span>
        ${h.reboot ? `<button type="button" data-hostreboot="${esc(r.node || "")}">Restart now</button>` : ""}
        <button type="button" data-hostupdate="${esc(r.node || "")}"${r.node && h.pending ? "" : " disabled"}>Apply updates</button></div>`;
  // The release channel, on any install (the operator, 2 Nov).
  const channel = `<div class="field"><label class="pick"><span class="pickw">Channel</span><select id="relChannel" data-relchannel aria-label="release channel">
        <option value="normal"${r.channel !== "dev" ? " selected" : ""}>Releases</option><option value="dev"${r.channel === "dev" ? " selected" : ""}>Dev builds</option></select></label>
      <div class="sub dim">${r.channel === "dev" ? `The dev channel takes every pre-release CI publishes${r.dev_latest ? `; the newest is ${esc(r.dev_latest)}${r.dev_draft ? " (a draft, seen with this controller's token)" : ""}` : ""}${
        r.draft_fetch?.tag ? `. ${r.draft_fetch.error ? `The draft ${esc(r.draft_fetch.tag)}: ${esc(r.draft_fetch.error)}` : r.draft_fetch.done ? `The draft ${esc(r.draft_fetch.tag)}'s files are here; Update runs from them` : `Fetching the draft ${esc(r.draft_fetch.tag)}'s files`}` : ""}${
        helpIcon("A dev build is not a release: it may not come up, and on AerieOS the other slot's fallback is what brings the machine back. A draft not published yet is seen with this controller's token for AerieOS's repository, under Unpublished builds.")}`
        : `Published releases alone${helpIcon("The dev channel takes every dev build as it is published, which may not come up.")}`}</div></div>`;
  // Debug mode alone: any version, the unpublished ones with the token
  // (the operator, 2 Nov), older ones too, since a test goes both ways.
  const pick = r.pick?.length ? `<div class="field"><label class="pick"><span class="pickw">Version</span><select id="relPick" aria-label="the version to install">${
      r.pick.map(v => `<option value="${esc(v.tag)}">${esc(v.tag)}${v.draft ? " (not published)" : ""}</option>`).join("")}</select></label>
      <div class="actbar"><span class="sp"></span><button type="button" data-relpick="${esc(r.node || "")}" data-os="${os ? "1" : ""}"${r.node ? "" : " disabled"}>Install this version</button></div></div>` : "";
  return `<div class="row stack2" data-group="Updates"><div class="grow">
      <div class="sub">This install runs ${runs}; the newest ${r.channel === "dev" ? "on the dev channel" : "release"} is ${(r.channel === "dev" ? r.newer || r.dev_latest || r.latest : r.latest) ? esc(r.channel === "dev" ? r.newer || r.dev_latest || r.latest : r.latest) : "not known yet"} (${when}${r.error ? `; ${esc(r.error)}` : ""}).</div>
      <div class="sub dim">${how}</div>
      ${channel}
      ${pick}
      ${host}
      ${os ? `<div class="field"><label class="pick"><span class="pickw">From a folder here</span><input type="text" id="osFrom" placeholder="/mnt/stick/aerieos-os" autocomplete="off" spellcheck="false"></label></div>` : ""}
      <div class="actbar"><span class="sp"></span>
        <button type="button" data-relcheck>Check for updates</button>
        ${os ? `<button type="button" data-osfrom="${esc(r.node || "")}"${r.node ? "" : " disabled"}>Update from the folder</button>` : ""}
        <button type="button" class="primary" data-relupdate="${esc(r.node || "")}" data-os="${os ? "1" : ""}"${r.newer && r.node ? "" : " disabled"}>${r.newer ? `Update to ${esc(r.newer)}` : "Update"}</button></div>
    </div></div>`;
}
// ---- the copies kept (R161 step 4) ----
// Back up now writes a copy to every folder where they go; the list is what
// is there, newest first, each under the state downloadable (sealed).
let backupData = null, backupAsked = false;
async function loadBackup(){
  backupAsked = true;
  try{ backupData = await (await fetch("/api/backup")).json(); }
  catch(e){ backupData = {error: "backup: " + failWords(e)}; }
  settingsRev++; drawPanes();
}
function backupSection(){
  if (backupData === null){ if (!backupAsked) loadBackup(); return `<div class="field">${skRows(2)}</div>`; }
  const b = backupData;
  if (b.error) return `<div class="hint bad">${esc(b.error)}</div>`;
  const owner = !!b.owner;
  const rows = (b.copies || []).map(c => `<div class="row"><div class="grow"><div class="name">${esc(c.name)}</div>
      <div class="sub">${esc(c.where)} · ${esc(humanBytes(c.size || 0))} · ${c.made_at ? esc(ago(c.made_at)) : ""}${c.version ? ` · ${esc(c.version)}` : ""}</div></div>
      ${owner && !/\.builderbot\/backup$/.test(c.where) ? `<span class="acts"><a class="btn" href="/api/backup-file?name=${encodeURIComponent(c.name)}" download>Download</a></span>` : ""}</div>`).join("");
  return `<div class="row stack2" data-group="Backup copies"><div class="grow">
      <div class="sub">${b.on ? `Copies go to ${(b.where || []).map(esc).join(", ")}${b.made_at ? `; the last was written ${esc(ago(b.made_at))} (${esc(humanBytes(b.size || 0))})` : "; none written yet"}.` : "No backup password set: nothing is copied until one is, under Backup."}${(b.failed || []).length ? ` <span class="bad">Not written: ${esc(b.failed.join("; "))}.</span>` : ""}</div>
      ${(b.other || []).length ? `<div class="field">${lbl("", "Also copied to", "a disk or share under Other disks and shares on the Storage page, so a copy is off this machine; one mounted read-only cannot take one")}
        ${(b.other || []).map(o => `<label class="ndcap"><input type="checkbox" data-backupalso="${esc(o.id)}"${o.on ? " checked" : ""}${o.ro || !owner ? " disabled" : ""}> ${esc(o.name)} <span class="sub">${esc(o.kind === "smb" ? "SMB share" : o.kind === "nfs" ? "NFS export" : "disk")}${o.ro ? ", read-only" : ""}</span></label>`).join("")}
        <div class="actbar"><span class="sp"></span><button type="button" data-backupalsosave${owner ? "" : " disabled"}>Save</button></div></div>` : ""}
      <div class="hint">These copies are the controller: its accounts, the spaces' notebooks and settings, its nodes and keys. The files on your pools are not in them; the Storage page's snapshots and Backups keep those.</div>
      ${rows ? `<div class="rows">${rows}</div>` : ""}
      <div class="actbar"><span class="sp"></span><button type="button" class="primary" data-backupnow${b.on && owner ? "" : " disabled"}>Back up now</button></div>
    </div></div>`;
}
function wireBackup(root){
  root.querySelectorAll("[data-backupalsosave]").forEach(b => b.onclick = () => pressing(b, async () => {
    const ids = [...root.querySelectorAll("[data-backupalso]:checked")].map(x => x.dataset.backupalso);
    busy(b, "Saving");
    const j = await (await postJSON("/api/settings", {set: {backup_also: ids.join(" ")}})).json().catch(() => ({error: "no answer"}));
    notify(j.error || (ids.length ? `the next copy also goes to ${ids.length} disk${ids.length === 1 ? "" : "s"} or share${ids.length === 1 ? "" : "s"} off this machine` : "copies stay on this machine's pools"), !!j.error);
    await loadBackup();
  }));
  root.querySelectorAll("[data-backupnow]").forEach(b => b.onclick = () => pressing(b, async () => {
    busy(b, "Writing");
    const j = await (await postJSON("/api/backup", {action: "now"})).json().catch(() => ({error: "no answer"}));
    notify(j.error || `written: ${j.name} to ${(j.where || []).length} place${(j.where || []).length === 1 ? "" : "s"}`, !!j.error);
    await loadBackup();
  }));
}
// ---- moving this controller (R90 step 12) ----
// Prepare to move arms the move and shows the token once (R175: no life on
// it, and the nodes hear it on every hello from then on); Download the
// bundle packs it fresh under that key at that moment; Forget it withdraws
// the move (the key gone here, the nodes told nothing more); Mark as moved,
// pressed once the new home is up, makes this one read-only, saying where
// it went, and the controller marks itself so when the new one tells it or
// answers its asking. The moved band is page-shell.js's (drawMovedBand).
let moveData = null, moveAsked = false, moveToken = null;
async function loadMove(){
  moveAsked = true;
  const was = JSON.stringify(moveData);
  try{ moveData = await (await fetch("/api/move?pieces=1")).json(); }
  catch(e){ moveData = {error: "move: " + failWords(e)}; }
  // Drawn once it has landed, as the backup copies are (B645: the section
  // stayed its two shimmer rows after a reload, and Forget it drew nothing).
  if (JSON.stringify(moveData) !== was){ settingsRev++; if (tabs.some(t => t.kind === "settings")) drawPanes(); }
  // ...and read again every poll while a move is armed (B646): how many
  // nodes have heard it, the last packing and the ask's answer move on
  // their own, while the page is open and only then.
  clearTimeout(moveTimer); moveTimer = null;
  if (moveData?.prepared && tabs.some(t => t.kind === "settings")) moveTimer = setTimeout(loadMove, 15000);
}
let moveTimer = null;
function moveStatus(){
  const m = moveData || {};
  return m.moved ? "moved" : m.prepared ? "armed" : m.arrived?.restored_at ? "arrived" : "";
}
function moveSize(n){ return n >= 1073741824 ? `${(n / 1073741824).toFixed(1)} GB` : n >= 1048576 ? `${(n / 1048576).toFixed(1)} MB` : n >= 1024 ? `${Math.round(n / 1024)} KB` : `${n} B`; }
function moveSection(){
  if (moveData === null){ if (!moveAsked) loadMove(); return `<div class="field">${skRows(2)}</div>`; }
  const m = moveData;
  if (m.error) return `<div class="hint bad">${esc(m.error)}</div>`;
  const howWord = {pressed: "marked so here", told: "told by the new controller", asked: "learned by asking the new controller"}[m.how] || "";
  if (m.moved) return `<div class="row stack2" data-group="Move"><div class="grow">
      ${factGrid([["Moved to", m.to], ["When", m.at ? ago(m.at) : ""], ["How", howWord], ["Bundle landed", m.landed_at ? ago(m.landed_at) : ""]])}
      <div class="sub bad">This controller is read-only now; its nodes have followed, and one that comes back late is told where to knock.</div></div></div>`;
  // The state arrived by a move: what the old controller was told, as facts.
  const ar = m.arrived || {};
  const arrived = ar.restored_at ? `${factGrid([["Arrived by a move", ago(ar.restored_at)], ["From", ar.from || "no address named"],
      ["Old controller told", ar.told_at ? `${ago(ar.told_at)}${ar.told_how && ar.told_how !== "taken" ? ` (${ar.told_how})` : ""}`
        : ar.from ? `not yet${ar.tell_error ? `: ${ar.tell_error}` : ""}` : "it learns by asking here"],
      ["Nodes not back since", (m.not_here || []).length ? `${m.not_here.length}: the Nodes page gives each its line` : ""]])}` : "";
  const sizeMb = m.size ? moveSize(m.size) : "";
  const token = moveToken ? `<div class="field"><div class="hint warn">The move token, shown once and never kept here: <code>${esc(moveToken)}</code>. Give it on the new install's first page with this controller's address, or with the bundle.</div></div>` : "";
  // Each piece: its name on the tick's line, its size and what it holds
  // under it (the operator, 3 Nov: the name wrapped into a narrow column
  // beside the words).
  const pieces = (m.pieces || []).map(pc => `<div class="field"><label class="ndcap"><input type="checkbox" data-movepiece="${esc(pc.key)}"${pc.on ? " checked" : ""}${pc.fixed ? " disabled" : ""}> ${esc(pc.label)}</label>
      <div class="sub">${pc.over ? "at least " : ""}${moveSize(pc.size || 0)}${pc.about ? `: ${esc(pc.about)}` : ""}</div></div>`).join("");
  const stores = Array.isArray(m.stores) ? m.stores : [];
  // A move landed here instead (the operator, 1 Nov): on a fresh controller,
  // by its owner, from Controller settings, which on a stick is the only way
  // in, once its disks hold the projects.
  const ld = m.land || {};
  // A landing cut midway carried the old controller's record in with it,
  // so it reads as armed and landed: landing again is still what ends it.
  const land = ld.fresh && ld.owner && (ld.cut || (!m.prepared && !ar.restored_at)) ? moveLandBox(ld) : "";
  // What is in the bundle, as the record says it: the state always, then
  // what was ticked.
  const inside = ["the state", ...stores, ...(m.repos ? ["the repositories"] : []), ...(m.carries_key ? ["the install key"] : [])].join(", ");
  // Armed: the facts of the move (the operator, 3 Nov: a paragraph of them
  // said nothing at a glance), then the one line on what happens next.
  const armed = m.prepared ? `${factGrid([["New home", m.to || "not named yet"], ["Armed", ago(m.made_at)],
      ["Nodes that heard it", `${m.heard} of ${m.nodes}`], ["Last packed", m.packed_at ? `${ago(m.packed_at)}, ${sizeMb}` : "not yet: Download packs it"],
      ["In the bundle", inside], ["Asked whether it landed", m.asked_at ? `${ago(m.asked_at)}: ${m.asked_error || "not yet"}` : ""]])}
      <div class="sub">Every node follows by itself once the new home answers, however long that takes; Mark as moved makes this controller read-only now.</div>
      ${m.far ? `<div class="sub warn">${esc(m.far)}.</div>` : ""}` : "";
  return `<div class="row stack2" data-group="Move"><div class="grow">
      ${land}
      ${arrived}
      ${m.prepared ? armed : `<div class="sub">Prepare to move arms a move to another container, a machine of its own, or back, and shows a move token once; Download a backup packs what is ticked under a token of its own and arms nothing${
        helpIcon("From then on every node hears where the controller is going and follows by itself once the new home answers. The bundle (the state, the stores ticked, the deploy key, and the repositories and the install key when ticked) is packed fresh each time it is downloaded, or pulled by the new install from here with the token.")}</div>`}
      ${token}
      ${m.prepared ? "" : `<div class="field"><label class="pick"><span class="pickw">New home</span><input type="text" id="moveTo" placeholder="https://aerieos.new.example" autocomplete="off" spellcheck="false"></label></div>
      ${pieces}`}
      <div class="actbar"><span class="sp"></span>
        ${m.prepared ? `<button type="button" data-movebundle>Download the bundle</button>${m.to ? `<button type="button" data-moveask>Ask the new home</button>` : ""}<button type="button" data-moveforget>Forget it</button><button type="button" class="danger" data-movedone>Mark as moved</button>`
                     : `<button type="button" data-movebackup title="a copy of what is ticked, under a token of its own; no move is armed and no node told">Download a backup</button><button type="button" class="primary" data-moveprep>Prepare to move</button>`}</div>
    </div></div>`;
}
// The form that lands a move here: Controller settings' on a fresh controller,
// and the first-run walk's last step.
// In the walk the card around it says what it is, and says it waits while the
// step before is not done: only a hold the walk has not explained is said here.
function moveLandBox(ld, inWalk = false, heldSaid = false, bundleOnly = false){
  const off = ld.held ? " disabled" : "";
  // The token given on the first page is kept for this (the operator, 10 Nov:
  // asked twice), and where the old controller ran on this machine its
  // address cannot answer, so the bundle is the one way.
  const tok = ld.token_kept ? "" : `<label class="pick"><span class="pickw">Move token</span><input type="text" id="landTok" autocomplete="off" spellcheck="false"${off}></label>`;
  const from = bundleOnly ? "" : `<label class="pick"><span class="pickw">${ld.token_kept ? "Old controller, while it runs" : "Old controller"}</span><input type="text" id="landFrom" placeholder="https://aerieos.old.example" autocomplete="off" spellcheck="false"${off}></label>`;
  const file = `<label class="pick fwide"><span class="pickw">${bundleOnly ? "The bundle" : "Or the bundle"}</span><input type="file" id="landFile" accept=".aeriemove,.bbmove"${off}></label>`;
  return `<div class="field" data-movelandbox${ld.token_kept ? " data-tokkept" : ""}>
      ${inWalk ? "" : `<div class="sub">Moving a controller here instead: its token with its address, or its bundle, and its state takes this one's place${
        helpIcon(`This setup account goes with the old state, set aside and not deleted; you sign in with an account the moved controller had.${
          ld.stick ? " On this stick the bundle lands on the machine's disks, in the spaces' folder, never on the stick." : ""}`)}</div>
`}
      ${ld.held && !heldSaid ? `<div class="hint warn">${esc(ld.held)}.</div>` : ""}
      ${ld.token_kept ? `<div class="sub dim">The move token is the one you gave on the first page.</div>` : ""}
      <div class="fgrid">${tok}${from}${file}</div>
      <div class="actbar"><span class="sp"></span><button type="button" class="primary" data-moveland${off}>Land it here</button></div></div>`;
}
function wireMove(root){
  root.querySelectorAll("[data-moveland]").forEach(b => b.onclick = () => pressing(b, async () => {
    const tok = ($("landTok")?.value || "").trim(), from = ($("landFrom")?.value || "").trim(), file = $("landFile")?.files?.[0];
    const kept = !!b.closest("[data-movelandbox]")?.hasAttribute("data-tokkept");
    if (!tok && !kept) return notify("the move token is needed, with the old controller's address or the bundle", true);
    if (!(file || from)) return notify($("landFrom") ? "pick the bundle, or give the old controller's address" : "pick the bundle first", true);
    if (!await askYes(`Land the move here?\n\nThe moved controller's state takes this one's place: this setup account goes with it (set aside, not deleted), and you sign in with an account it had. ${file ? `The bundle (${moveSize(file.size)}) is sent from this browser.` : `The bundle is pulled from ${from}.`}`,
        {title: "Land the move?", verb: "Land it", danger: true})) return;
    busy(b, file ? "Sending" : "Landing");
    const fd = new FormData();
    fd.append("token", tok);
    fd.append("from", file ? "" : from);
    if (file) fd.append("bundle", file, file.name);
    // The bundle's bytes as they go, a bar under the button (the operator,
    // 8 Nov: a large bundle sat for minutes with nothing moving); once sent,
    // the landing itself (unpacking, the swap) with the word alone.
    const box = b.closest("[data-movelandbox]"), prog = document.createElement("div");
    prog.className = "field landprog";
    if (box) box.append(prog);
    const draw = (sent, total) => { prog.innerHTML = `<div class="sub">Sending the bundle: ${moveSize(sent)} of ${moveSize(total)}</div>${pctBar(total ? sent / total * 100 : 0, "bundle sent")}`; };
    const j = await new Promise(resolve => {
      const x = new XMLHttpRequest();
      x.open("POST", "/api/move-land");
      if (file) x.upload.onprogress = e => { if (e.lengthComputable) draw(e.loaded, e.total); };
      x.upload.onload = () => { prog.innerHTML = `<div class="sub">Sent. Landing it: unpacking, then the swap<span class="dots"></span></div>`; busy(b, "Landing"); };
      x.onload = () => { let r = {}; try{ r = JSON.parse(x.responseText); }catch(e){ r = {error: x.status === 200 ? "no answer" : `HTTP ${x.status}`}; } resolve(r); };
      x.onerror = () => resolve({error: "the landing stopped: the connection dropped"});
      x.send(fd);
    });
    prog.remove();
    if (j.error){ notify(j.error, true); unbusy(b, "Land it here"); return; }
    notify(`landed${j.from ? ` from ${j.from}` : ""}: the dashboard restarts on it, then sign in with an account it had${
      (j.said || []).length ? `. ${j.said.join(". ")}` : ""}`, (j.said || []).length > 0);
    setTimeout(() => location.assign("/"), 6000);
  }));
  root.querySelectorAll("[data-moveprep]").forEach(b => b.onclick = () => pressing(b, async () => {
    busy(b, "Preparing");
    const on = k => !!root.querySelector(`[data-movepiece="${k}"]`)?.checked;
    const stores = [...root.querySelectorAll('[data-movepiece^="store:"]')].filter(x => x.checked).map(x => x.dataset.movepiece.slice(6));
    const j = await (await postJSON("/api/move", {action: "prepare", to: $("moveTo")?.value || "", repos: on("repos"), carry_key: on("install_key"), stores})).json().catch(() => ({error: "no answer"}));
    if (j.error){ notify(j.error, true); unbusy(b, "Prepare to move"); return; }
    if ((j.said || []).length) notify(j.said.join(". "), true);
    moveToken = j.token;
    await loadMove();
  }));
  // A backup of the controller to keep (the operator, 6 Nov): what is ticked,
  // under a token of its own that the person records, no move armed.
  root.querySelectorAll("[data-movebackup]").forEach(b => b.onclick = () => pressing(b, async () => {
    const on = k => !!root.querySelector(`[data-movepiece="${k}"]`)?.checked;
    const stores = [...root.querySelectorAll('[data-movepiece^="store:"]')].filter(x => x.checked).map(x => x.dataset.movepiece.slice(6));
    busy(b, "Packing");
    const j = await (await postJSON("/api/move", {action: "backup", repos: on("repos"), carry_key: on("install_key"), stores})).json().catch(() => ({error: "no answer"}));
    unbusy(b, "Download a backup");
    if (j.error){ notify(j.error, true); return; }
    const typed = await askText(`The backup's token, shown once and never kept here:\n\n${j.token}\n\nRecord it: the backup opens only under it, on a new controller's first setup, and whoever holds the file and the token holds this controller's data${on("install_key") ? " and its install key" : ""}. Nothing is armed, so no node hears of it. It is the controller and what was ticked, not the files on your pools: the Storage page's snapshots and Backups keep those.\n\nType the token's last four characters to download the file.`,
                                {title: "Record the backup's token", verb: "Download", label: "The token's last four characters"});
    if (typed === null || typed === undefined){ notify("not downloaded: press Download a backup again for a new one under a new token", true); return; }
    if (String(typed).trim() !== j.token.slice(-4)){ notify("those are not the token's last four characters: press Download a backup again", true); return; }
    const a = document.createElement("a");
    a.href = `/api/move-backup?name=${encodeURIComponent(j.bundle)}`; a.download = j.bundle;
    document.body.appendChild(a); a.click(); a.remove();
    notify(`downloading ${j.bundle} (${moveSize(j.size || 0)}); keep it with its token`);
  }));
  // Packed while the button says so, then downloaded by name (the operator,
  // 8 Nov: a plain link said nothing while a large bundle was packed, and a
  // failure came back as a page of JSON).
  root.querySelectorAll("[data-movebundle]").forEach(b => b.onclick = () => pressing(b, async () => {
    busy(b, "Packing");
    const j = await (await postJSON("/api/move", {action: "pack"})).json().catch(() => ({error: "no answer"}));
    unbusy(b, "Download the bundle");
    if (j.error){ notify(j.error, true); return; }
    const a = document.createElement("a");
    a.href = `/api/move-bundle?name=${encodeURIComponent(j.bundle)}`; a.download = j.bundle;
    document.body.appendChild(a); a.click(); a.remove();
    notify(`downloading ${j.bundle} (${moveSize(j.size || 0)})`);
  }));
  root.querySelectorAll("[data-moveforget]").forEach(b => b.onclick = () => pressing(b, async () => {
    if (!await askYes("Forget this move?\n\nThe key is gone from here, so no node will follow a controller restored from its bundle, and the nodes hear of it no more. A bundle already downloaded still opens under its token, as a backup does.", {title: "Forget the move?", verb: "Forget it", danger: true})) return;
    const j = await (await postJSON("/api/move", {action: "forget"})).json().catch(() => ({error: "no answer"}));
    if (j.error) notify(j.error, true);
    moveToken = null;
    await loadMove();
  }));
  root.querySelectorAll("[data-moveask]").forEach(b => b.onclick = () => pressing(b, async () => {
    busy(b, "Asking");
    const j = await (await postJSON("/api/move", {action: "ask"})).json().catch(() => ({error: "no answer"}));
    if (j.error) notify(j.error, true);
    else notify(j.moved ? "it landed: this controller is marked moved" : `not landed there yet${j.asked_error ? `: ${j.asked_error}` : ""}`);
    await loadMove();
    if (j.moved) await refresh();
  }));
  root.querySelectorAll("[data-movedone]").forEach(b => b.onclick = () => pressing(b, async () => {
    if (!await askYes("Mark this controller as moved?\n\nFrom now on it is read-only and tells its nodes where it went; press this once the new home is up and answering, or let it learn so by itself.", {title: "Moved?", verb: "Mark as moved", danger: true})) return;
    const j = await (await postJSON("/api/move", {action: "moved"})).json().catch(() => ({error: "no answer"}));
    if (j.error) notify(j.error, true);
    await loadMove();
    await refresh();
  }));
}

function wireUpdates(root){
  // The channel's pick (R179): saved, then the newest asked for again.
  root.querySelectorAll("[data-relchannel]").forEach(s => s.onchange = async () => {
    const j = await (await postJSON("/api/settings", {set: {release_channel: s.value}})).json().catch(() => ({error: "no answer"}));
    if (j.error){ notify(j.error, true); return; }
    await postJSON("/api/v1/nodes", {action: "release-check"}).catch(() => {});
    await refresh();
  });
  root.querySelectorAll("[data-hostupdate]").forEach(b => b.onclick = () => pressing(b, async () => {
    const reboot = !!$("hostReboot")?.checked;
    if (!await askYes(`Update the system's own packages?\n\napt brings every package to its newest with the configuration files kept as they are${reboot ? ", and the machine restarts after if the update asks for it" : "; a restart, if one is needed, is yours to press after"}. The log is on the Jobs page.`, {title: "Apply updates?", verb: "Update"})) return;
    busy(b, "Updating");
    const j = await (await postJSON("/api/v1/nodes", {action: "host-update", id: b.dataset.hostupdate, reboot})).json().catch(() => ({error: "no answer"}));
    notify(j.error || "updating: the job runs on this machine; its log is on the Jobs page", !!j.error);
  }));
  root.querySelectorAll("[data-hostreboot]").forEach(b => b.onclick = () => pressing(b, async () => {
    if (!await askYes("Restart this machine now? Every session and container on it stops until it is back.", {title: "Restart?", verb: "Restart", danger: true})) return;
    busy(b, "Restarting");
    const j = await (await postJSON("/api/v1/nodes", {action: "reboot", id: b.dataset.hostreboot})).json().catch(() => ({error: "no answer"}));
    notify(j.error || "restarting: the page comes back when the machine does", !!j.error);
  }));
  root.querySelectorAll("[data-relcheck]").forEach(b => b.onclick = () => pressing(b, async () => {
    busy(b, "Checking");
    const j = await (await postJSON("/api/v1/nodes", {action: "release-check"})).json().catch(() => ({error: "no answer"}));
    if (j.error) notify(j.error, true);
    await refresh();
  }));
  root.querySelectorAll("[data-osfrom]").forEach(b => b.onclick = () => pressing(b, async () => {
    const from = ($("osFrom")?.value || "").trim();
    if (!from){ notify("name the folder on this machine that holds the release's ISO with its .sha256 and .attestation.jsonl", true); return; }
    if (!await askYes(`Write the ISO in ${from} into the other slot?\n\nThe ISO is checked against the sha256 beside it; the slot not in use takes it and boots next; nothing running changes until you restart.`, {title: "Update from a folder?", verb: "Write the slot"})) return;
    busy(b, "Updating");
    const j = await (await postJSON("/api/v1/nodes", {action: "os-update", id: b.dataset.osfrom, from})).json().catch(() => ({error: "no answer"}));
    notify(j.error || "updating: the job writes the other slot; restart from the Nodes page when it is done", !!j.error);
  }));
  root.querySelectorAll("[data-relpick]").forEach(b => b.onclick = () => pressing(b, async () => {
    const tag = $("relPick")?.value;
    if (!tag || !await askYes(`Install ${tag} on this machine?\n\nIt is fetched and checked as any update is. An older build may refuse this machine's state, and a dev build may not come up.`, {title: "Install this version?", verb: "Install"})) return;
    busy(b, "Installing");
    const j = await (await postJSON("/api/v1/nodes", {action: b.dataset.os ? "os-update" : "controller-update", id: b.dataset.relpick, release: tag})).json().catch(() => ({error: "no answer"}));
    notify(j.error || j.said || `installing ${tag}: its job is on the Jobs page`, !!j.error);
    unbusy(b, "Install this version");
  }));
  root.querySelectorAll("[data-relupdate]").forEach(b => b.onclick = () => pressing(b, async () => {
    if (b.dataset.os){
      if (!await askYes(`Update this machine to AerieOS ${state?.release?.newer}?\n\nThe release's image is fetched and checked (sha256, build attestation), written into the slot not in use and named for the next boot; nothing running changes until you restart from the Nodes page, and the slot running now stays to fall back to.`, {title: "Update the image?", verb: "Write the slot"})) return;
      busy(b, "Updating");
      const j = await (await postJSON("/api/v1/nodes", {action: "os-update", id: b.dataset.relupdate, release: "v" + state.release.newer})).json().catch(() => ({error: "no answer"}));
      notify(j.error || j.said || "updating: the job writes the other slot; restart from the Nodes page when it is done", !!j.error);
      return;
    }
    if (!await askYes(`Update this install to ${state?.release?.newer}?\n\nThe installer runs on this machine's node: the bundle is fetched and checked, the state copied aside, the service switched to the new release and started. The page comes back on it; if it does not answer, the install goes back by itself.`)) return;
    busy(b, "Updating");
    const j = await (await postJSON("/api/v1/nodes", {action: "controller-update", id: b.dataset.relupdate})).json().catch(() => ({error: "no answer"}));
    notify(j.error || "updating: the job runs on this machine's node; the page comes back on the new release", !!j.error);
  }));
}
function reportsSection(){
  const rows = reportsList || [];
  const mayDelete = state?.can?.controller !== false;
  const list = reportsList === null ? `<div class="row stack2"><div class="grow"><div class="sub dim">reading the reports…</div></div></div>`
    : !rows.length ? `<div class="empty">No reports. A session's <code>aerie report</code> and Report a bug in the header land here.</div>`
    : rows.map(r => `<div class="row repline" data-report="${r.id}"><div class="grow">
        <div class="name">#${r.id} ${esc(r.project || "no space")}<span class="dim"> · ${esc(ago(r.at))} · ${esc(r.by || "")}${r.area ? ` · ${esc(r.area)}` : ""}</span></div>
        <div class="sub reptext">${esc(r.text || "")}</div></div>
        ${mayDelete ? rmIcon(`data-repdel="${r.id}"`, `Delete report ${r.id}`, {title: "take it out: it is not in the diagnostics downloaded after"}) : ""}
      </div>`).join("");
  return `<div class="field"><div class="hint">What sessions and people reported about AerieOS. Delete any you do not want in the diagnostics before downloading them.</div></div>
    <div class="replist">${list}</div>
    <div class="field"><div class="actbar"><span class="sp"></span>
      <a class="btnish" href="/logs/download?what=diag" download title="the controller's diagnostics as one file, with the reports listed here">Download diagnostics</a>
      ${mayDelete && rows.length ? `<button type="button" class="danger" id="setReportsClear">Clear reports</button>` : ""}</div></div>`;
}

async function deleteReport(btn){
  const id = Number(btn.dataset.repdel);
  busy(btn, "");
  try{
    const j = await (await postJSON("/api/reports", {action: "delete", id})).json();
    if (j.error){ notify(j.error, true); unbusy(btn, ""); return; }
    notify(`report #${id} deleted`);
  }catch{ notify("could not delete the report", true); unbusy(btn, ""); return; }
  await loadReports();
}

async function clearReports(btn){
  // Read again first: a report may have come in, or gone, since the draw.
  await loadReports();
  const n = reportsList?.length || 0;
  if (!n) return notify("there are no reports to clear");
  const s = n === 1 ? "" : "s";
  if (!await askYes(`Delete all ${n} report${s} about AerieOS?`)) return;
  busy(btn, "Clearing");
  try{
    const j = await (await postJSON("/api/reports", {action: "clear"})).json();
    if (j.error) notify(j.error, true);
    else notify(`cleared ${j.cleared} report${j.cleared === 1 ? "" : "s"}`);
  }catch{ notify("could not clear the reports", true); }
  unbusy(btn, "Clear reports");
  loadReports();
}

// The settings that used to be environment variables (roadmap R29): what is
// left of them after the operator asked which needed to exist at all. Each
// group is one section with one Apply, a field that has never been saved
// says so beside it, and the bar says whether a change applies at once or at the
// next start. Drawn from the poll's copy, so a save shows on the next poll.
// The checks, in the order Controller settings lists them, with what each asks.
const CHECK_KINDS = [
  ["release", "A newer AerieOS", "Asks the releases for a newer version than this install runs, on a bare-metal install; the Update window applies it."],
  ["images", "Container images", "Asks each space container's registry for a newer image."],
  ["nginx", "nginx", "Asks the registry for a newer nginx image for the nodes that serve hostnames."],
  ["scanners", "Scanners", "Asks for newer versions of the scanners the nodes run over spaces."],
  ["catalog", "Library", "Asks upstream for the toolchains' and coding agents' newest versions, and the vetted catalog for its index. A node's own check of what it holds is on its page."]];
const SETTING_GROUPS = [
  // The apps this controller offers its people (R272 step 3, apps.py): each
  // one on is fetched from the release matching this controller, checked
  // against its sha256 and offered on its card in the Library (under Build); Check for updates asks the
  // release again rather than waiting for the daily look.
  // Update checks on one clock (R176, checks.py): each check AerieOS
  // makes by itself, how often, when it last ran, and Check for updates. A node's
  // own version check is its page's.
  {key: "checks", title: "Update checks", intro: checksIntro, status: checksStatus,
   heading: () => { const c = state?.checks || {}; const off = Object.values(c).filter(x => x.cadence === "off").length;
     return off ? `${off} off` : Object.keys(c).length ? "on" : ""; },
   // The release check is an install that updates itself (B648): not
   // offered on the container edition.
   fields: CHECK_KINDS.map(([k, label, hint]) => ({key: `check_${k}`, label, type: "select", hint, when: k === "release" ? () => !!state?.bare_metal : undefined,
     options: [["daily", "Daily"], ["weekly", "Weekly"], ["monthly", "Monthly"], ["off", "Off: only Check for updates"]]}))},
  // The vetted catalog (R169): where its signed index is read, and a mirror
  // of it imported for a controller that cannot reach it (step 6).
  {key: "catalog", title: "Vetted catalog", intro: catalogIntro, status: catalogStatus,
   heading: s => `${/aquilaelabs\/(aerieos|builderbot)-catalog\//.test(s?.settings?.catalog_url?.value || "") ? "the public catalog" : "another catalog"}${s?.catalog_mirror ? ", a mirror held" : ""}`,
   fields: [{key: "catalog_url", label: "Address", type: "text", placeholder: "https://raw.githubusercontent.com/aquilaelabs/aerieos-catalog/main/",
     hint: "where the Library reads the catalog's index.json and index.sig, checked against the maintainers' key this install ships"},
    {key: "sideload_agents", label: "Offer coding agents from packs added here", type: "bool",
     hint: "A pack you added yourself may bring a coding agent. Off, its program installs and its agent is not offered: an agent's adapter decides what runs in every session of it, and nobody vetted this one. On, for trying an agent of your own before you submit it to the catalog."}]},
  {key: "apps", title: "Apps", off: "apps", intro: appsIntro, status: appsStatus,
   heading: s => `${["apps_android", ...(s?.settings?.offer_unvetted?.value ? ["apps_vscode", "apps_companion"] : [])]
     .filter(k => s?.settings?.[k]?.value).length} offered`,
   fields: [
    {key: "apps_android", label: "Android app", type: "bool",
     hint: "The notebook, the bell and your sessions on a phone, and the phone lent to a space."},
    {key: "apps_vscode", label: "VS Code extension", type: "bool", dev: true,
     hint: "A space's files and terminal in VS Code."},
    {key: "apps_companion", label: "Windows companion", type: "bool", dev: true,
     hint: "A folder on a Windows PC kept in step with a space, for a tool that only runs there."}]},
  // The home tunnel the controller runs itself (R176): the public hostname
  // a node off the LAN dials, the tunnel's token, and an API token that
  // writes the hostname's record and the tunnel's rules rather than having
  // them clicked. The two tokens are secrets: never shown back.
  // Named for what it is for, not for its field (the operator, 13 Oct):
  // "Public hostname" read as a node's or a route's, and those are on the
  // node's row and the nginx tab.
  {key: "tunnel", title: "Reach from outside", off: "tunnel", status: tunnelStatus, intro: tunnelSteps,
   heading: s => !s?.tunnel ? "" : s.tunnel.connected ? "connected" : s.tunnel.configured ? (s.tunnel.running ? "starting" : "stopped") : "off",
   headingCls: s => s?.tunnel?.connected ? "ok" : "",
   fields: [
    {key: "tunnel_host", label: "Hostname", type: "text", placeholder: "bb.example.com",
     hint: "The name a node off your network dials the controller at, published by a tunnel from home. Enroll node offers it as the controller's address."},
    {key: "tunnel_token", label: "Tunnel token", type: "secret",
     hint: "From Zero Trust: Networks, Tunnels, Create a tunnel (Cloudflared), the long eyJ… string in its install command. The controller runs the tunnel itself with it."},
    {key: "cf_api_token", label: "Cloudflare API token (optional)", type: "secret",
     hint: "With Zone DNS Edit and Account Cloudflare Tunnel Edit: the hostname's record and the tunnel's two rules (the agent's API to the controller, everything else 404) are written on Apply rather than clicked."}]},
  // The dashboard's own connection (R158 step 2, tls.py): http, the
  // install's own certificate, or Let's Encrypt for the controller's own
  // hostname; its line says what is in force, with the fingerprint a phone
  // or the companion pins and Download for the certificate itself.
  {key: "connection", title: "Connection", status: connectionStatus, intro: connectionIntro,
   heading: s => !s?.tls ? "" : s.tls.on ? (s.tls.kind === "acme" ? "https, Let's Encrypt" : "https, own certificate") : "http",
   headingCls: s => s?.tls?.on ? "ok" : "warn",
   fields: [
    {key: "tls_mode", label: "Served over", type: "select",
     options: [["", "as set below: https with the install's own certificate where a hostname is set, else http"],
               ["http", "http: nothing encrypted, for a LAN with no CA"],
               ["self", "https with the install's own certificate"],
               ["acme", "https with a Let's Encrypt certificate for the hostname (DNS-01, Cloudflare)"]],
     hint: "One port serves both: a browser gets https and a node keeps dialing http. The install's own certificate is made here and remade a month before it ends; a browser warns once until it is pinned. Let's Encrypt needs the hostname below on a domain the Cloudflare API token (Reach from outside) can write a record in; port 80 is not asked for."},
    {key: "tls_host", label: "Hostname", type: "text", placeholder: "bb.example.com",
     hint: "The controller's own public name, which the certificate is for. Leave it empty on a LAN with no name: the install's own certificate then names the addresses the page is reached at."},
    {key: "tls_email", label: "Email (Let's Encrypt)", type: "text", placeholder: "you@example.com",
     hint: "Where Let's Encrypt writes about the certificate. Optional."}]},
  // The mail server the bell's rows go out through (R149, reach.py): each
  // person picks where the bell reaches them on their Profile; email needs
  // this server.
  {key: "mail", title: "Mail", status: s => s?.settings?.smtp_host?.value ? "set" : "no server yet",
   heading: s => s?.settings?.smtp_host?.value ? "set" : "",
   headingCls: s => s?.settings?.smtp_host?.value ? "ok" : "",
   fields: [
    {key: "smtp_host", label: "SMTP server", type: "text", placeholder: "smtp.example.com",
     hint: "The server AerieOS sends mail through, for a person who asked for the bell by email on their Profile. Nothing is sent until one is set."},
    {key: "smtp_port", label: "Port", type: "text", placeholder: "587",
     hint: "Empty takes 587 with STARTTLS and 465 with TLS."},
    {key: "smtp_security", label: "Security", type: "select",
     options: [["starttls", "STARTTLS (port 587)"], ["tls", "TLS from the start (port 465)"], ["none", "none: a server on this network only"]],
     hint: "What the connection to the server is: STARTTLS and TLS encrypt it; none sends in the clear."},
    {key: "smtp_user", label: "Sign-in name", type: "text", placeholder: "you@example.com",
     hint: "Empty sends without signing in, which a server on this network may allow."},
    {key: "smtp_password", label: "Password", type: "secret",
     hint: "Kept sealed under the install key, as the tokens are."},
    {key: "smtp_from", label: "From", type: "text", placeholder: "AerieOS <builderbot@example.com>",
     hint: "The address the mail is from; the sign-in name when empty."}]},
  // The room a node keeps for itself (R110): the numbers the bell, the
  // build gate, a rebuild's check and the hourly prune go by, and a memory
  // limit for a container whose compose file sets none.
  {key: "room", title: "Room on the nodes", status: () => "applies at once; a container's limit at its next start",
   heading: s => `${s?.settings?.room_floor_gb?.value ?? 10} GB kept`,
   fields: [
    {key: "room_floor_gb", label: "Disk kept free (GB)", type: "number",
     hint: "A node under this much free on a disk or a store is on the bell, and a build, a test or a container rebuild there is refused until room is made. A disk smaller than ten times this keeps a tenth of itself instead."},
    {key: "room_mem_pct", label: "Memory warning (% in use)", type: "number",
     hint: "A node or a VM using more than this share of its memory over ten minutes is on the bell, before the system starts killing processes."},
    {key: "container_mem_gb", label: "Default container memory (GB, 0 for none)", type: "number",
     hint: "A container whose compose file sets no memory limit gets this one when it starts, so one runaway app cannot take the node's memory. A limit the compose file sets is kept."}]},
  // Maintenance mode, the owner's alone (state.can.maintenance): every
  // other account is told why and kept out until it is off, and a band on
  // every page reminds the owner it is on.
  // The backup password (R161 step 4): the copies of the state on the
  // machine's pools and under the state are sealed under its key; the
  // copies themselves are the Backup copies section's.
  {key: "backup", title: "Backup",
   heading: s => s?.settings?.backup_password?.set ? "on" : "off",
   fields: [
    {key: "backup_password", label: "Backup password", type: "secret",
     hint: "Eight characters at least. With one set, a sealed copy of the configuration (accounts, nodes, spaces, settings, the stores) is written after every change onto every pool of this machine and under the state, the five newest kept; a fresh install's first page restores one with this password. Keep the password where you keep the owner's: a copy without it is a sealed file."}]},
  // Unpublished builds (the operator, 1 Nov): in debug mode alone, a GitHub
  // token that may read AerieOS's repository, with which the dev channel and
  // the version picker see the drafts not published yet.
  {key: "drafts", title: "Unpublished builds", debug: true,
   heading: s => s?.settings?.release_token?.set ? "token set" : "no token",
   fields: [
    {key: "release_token", label: "GitHub token", type: "secret",
     hint: "A personal access token that may read AerieOS's repository (contents, read). With it, and the dev channel picked under Updates, this controller also sees the builds not published yet, and Update on AerieOS fetches one's files with it and takes the update from them, checked as a folder's are. Kept sealed here, never shown again, and cleared at any start out of debug mode."}]},
  // The update window (R160 step 4): a newer release applied by itself at
  // the hour named, daily or one weekday; off by default, so nothing moves
  // the install without a press or this choice.
  // An install that updates itself alone (B648): the container is pulled
  // by whatever runs it, so the window is not offered there, and the boot
  // menu's older versions are AerieOS's own.
  {key: "updwin", title: "Update window", bare: true,
   heading: s => s?.settings?.update_window?.value ? `${s.settings.update_window.value} at ${String(s.settings.update_hour?.value ?? 4).padStart(2, "0")}:00` : "off",
   fields: [
    {key: "update_window", label: "Apply a newer release", type: "select",
     options: [["", "never by itself: Update under Updates is the press"], ["daily", "daily, at the hour below"],
               ["mon", "Mondays"], ["tue", "Tuesdays"], ["wed", "Wednesdays"], ["thu", "Thursdays"], ["fri", "Fridays"], ["sat", "Saturdays"], ["sun", "Sundays"]],
     hint: "In the window the newest release is applied the way Update does it: the image into the other slot on AerieOS (a restart still waits for you), the installer's bundle elsewhere. One window applies one release once."},
    {key: "update_hour", label: "At (hour, 0 to 23, this controller's time)", type: "number"},
    {key: "os_keep", label: "Older versions kept on the boot menu", type: "number", when: () => !!state?.release?.os?.version,
     hint: "AerieOS: each version an update replaces stays on the machine, about 2 GB each, bootable from the menu's Older versions. 0 keeps none."}]},
  {key: "maint", title: "Maintenance", can: "maintenance",
   heading: s => s?.settings?.maintenance_mode?.value ? "on" : "off",
   headingCls: s => s?.settings?.maintenance_mode?.value ? "warn" : "",
   fields: [
    {key: "maintenance_mode", label: "Maintenance mode", type: "bool",
     hint: "Only you can sign in and use AerieOS, from the page, a phone or a session. Everybody else is told it is down for maintenance and stays signed in for after; their sessions and terminals are ended when it goes on, which it asks about first. Nodes keep running."}]},
];

// Turning maintenance mode on: who is kept out, and the sessions and
// terminals of theirs it ends, each with what it is doing (the operator, 27
// Oct), so a working session is not ended unseen.
const MAINT_STATE = {working: "working", waiting: "waiting for its person", asking: "asking for permission", open: "open"};
async function maintAsk(rows){
  const line = r => `${r.who}: ${r.what}${r.project ? ` on ${r.project}` : ""}, ${MAINT_STATE[r.state] || "idle"}, on ${r.node}`;
  const busyN = rows.filter(r => r.state === "working").length;
  const text = rows.length
    ? `Everybody else is kept out until it is off, and these ${rows.length} session${rows.length === 1 ? "" : "s"} and terminal${
        rows.length === 1 ? "" : "s"} of theirs end now${busyN ? `, ${busyN} of them in the middle of work` : ""}:\n\n${rows.map(line).join("\n")}`
    : "Everybody else is kept out until it is off. Nobody else has a session or a terminal open.";
  return askYes(text, {title: "Turn maintenance mode on?", verb: rows.length ? "End them and turn it on" : "Turn it on", danger: rows.length > 0});
}

// The Connection section's lines (R158 step 2): what is in force, the
// certificate's fingerprint and expiry, Download, and an ACME request going.
function connectionIntro(s){
  const t = s?.tls || {};
  if (!t.on) return `<div class="hint">Served over http: what the page carries crosses the network in the clear. https is recommended wherever this is reached beyond one machine; behind the home tunnel, Cloudflare's edge is https already.</div>`;
  const when = t.expires ? new Date(t.expires * 1000).toLocaleDateString() : "";
  const p = t.pending || {};
  return `<div class="hint">https with ${t.kind === "acme" ? "a Let's Encrypt certificate" : "the install's own certificate"} for ${esc((t.names || []).join(", ") || "this install")}${when ? `, until ${esc(when)}` : ""}${
      t.kind === "self" ? "; a browser warns once until it is pinned, and the phone and the companion pin it by its fingerprint" : ""}.</div>
    <div class="field"><div class="sub mono">${esc(t.fingerprint || "")}</div></div>
    <div class="field"><div class="actbar"><span class="sp"></span><a class="btn" href="/api/tls?download=1" download="builderbot.pem">Download the certificate</a>${
      t.mode === "acme" ? `<button type="button" data-tlsissue${p.state && !["done", "failed"].includes(p.state) ? " disabled" : ""}>Ask Let's Encrypt now</button>` : ""}</div></div>${
    p.state ? `<div class="field"><div class="sub${p.state === "failed" ? " bad" : ""}">${p.state === "failed" ? `Let's Encrypt: ${esc(p.error || "it failed")}` : p.state === "done" ? "the Let's Encrypt certificate is in force" : `asking Let's Encrypt (${esc(p.state)})`}</div></div>` : ""}`;
}
function connectionStatus(s){
  const t = s?.tls || {};
  return t.on ? (t.key_sealed ? "applies at once; the private key is sealed under the install key" : "applies at once; the private key is kept open until the install has a key") : "applies at once";
}

// What the Apps section holds, over its switches, and Check for updates.
// The clocks alone (the operator, 3 Nov): Check for updates is on each
// thing's own page (Containers, nginx, Scanners, the Library, Updates), so
// this section says when each last looked and sets how often.
function checksIntro(){
  const c = state?.checks || {};
  const said = CHECK_KINDS.filter(([k]) => c[k]).map(([k, label]) =>
    `${esc(label)} ${c[k].at ? esc(ago(c[k].at)) : "never"}`);
  return said.length ? `<div class="sub">Last checked: ${said.join(" · ")}. Check for updates is on each one's own page.</div>` : "";
}
function checksStatus(){
  const c = state?.checks || {};
  const due = Object.values(c).filter(x => x.cadence !== "off").length;
  return `${due} of ${Object.keys(c).length} on their own clock · applies at once`;
}
function wireChecks(root){
  root.querySelectorAll("[data-checknow]").forEach(b => b.onclick = () => pressing(b, async () => {
    busy(b, "Checking");
    const j = await (await postJSON("/api/checks", {kind: b.dataset.checknow})).json().catch(() => ({error: "no answer"}));
    notify(j.error || "checking: the answer is here in a moment", !!j.error);
    setTimeout(() => refresh(), 4000);
  }));
}

// The mirror's line and its two presses: Import takes an archive that
// tools/catalog-mirror.py made on a machine with the network.
function catalogIntro(s){
  const m = s?.catalog_mirror;
  return `<div class="sub">The Library lists the packs and apps AerieOS's maintainers reviewed, from the signed index at this address${
    helpIcon("Another address can only mirror the same files: index.json and index.sig are checked against the maintainers' key this install ships, so no other catalog passes as vetted. A controller that cannot reach the address imports a mirror instead: tools/catalog-mirror.py makes one on a machine with the network, and the Library installs from it with nothing fetched.")}</div>
    <div class="field">${m
      ? `<div class="row stack2"><div class="grow"><span class="name">Mirror</span> <span class="sub">${m.packs} entr${m.packs === 1 ? "y" : "ies"} from ${m.repos} repositor${m.repos === 1 ? "y" : "ies"}, made ${esc(m.generated || "at an unknown time")}, imported ${esc(ago(m.imported_at))}</span></div>
          <button type="button" data-mirrorforget>Forget</button></div>`
      : `<div class="sub dim">No mirror imported.</div>`}</div>
    <div class="addbar ctlrow"><input id="mirrorFile" type="file" hidden accept=".tar,.tgz,.tar.gz,application/gzip,application/x-tar">
      <button type="button" data-mirrorimport>${m ? "Import a newer mirror" : "Import a mirror"}</button></div>`;
}
function catalogStatus(s){
  return s?.catalog_mirror ? `a mirror made ${s.catalog_mirror.generated || "earlier"} answers when the catalog does not · applies at once` : "applies at once";
}
function wireCatalogMirror(root){
  const file = root.querySelector("#mirrorFile");
  root.querySelector("[data-mirrorimport]")?.addEventListener("click", () => file?.click());
  if (file) file.onchange = async () => {
    const f = file.files[0];
    if (!f) return;
    const b = root.querySelector("[data-mirrorimport]");
    if (b) busy(b, "Importing");
    const u = await fetch("/api/upload-archive?name=" + encodeURIComponent(f.name), {method: "POST", body: f});
    const uj = await u.json().catch(() => ({}));
    const j = !u.ok || uj.error ? {error: uj.error || `the upload failed (HTTP ${u.status})`}
      : await (await postJSON("/api/catalog-mirror", {action: "import", archive: uj.id})).json().catch(() => ({error: "no answer"}));
    notify(j.error || `the mirror is imported: ${j.packs} entries, made ${j.generated}`, !!j.error);
    if (state && !j.error) state.catalog_mirror = j.mirror;
    settingsRev++; drawPanes(); refresh();
  };
  root.querySelector("[data-mirrorforget]")?.addEventListener("click", async e => {
    const b = e.currentTarget;
    if (!await askYes("Forget the catalog's mirror? The Library reads the catalog's address alone again; packs kept from the mirror stay.")) return;
    busy(b, "Forgetting");
    const j = await (await postJSON("/api/catalog-mirror", {action: "forget"})).json().catch(() => ({error: "no answer"}));
    notify(j.error || "the mirror is forgotten", !!j.error);
    if (state && !j.error) state.catalog_mirror = null;
    settingsRev++; drawPanes();
  });
}

function appsIntro(){
  return `<div class="sub">Each one on is fetched from the release that matches this controller, checked, and offered on the ${
    pageLink("library", "Library")}, under For you, for your people to download and keep current.</div>
    <div class="addbar ctlrow"><button type="button" id="setAppsCheck"${devApps?.checking ? " disabled" : ""}>${devApps?.checking ? "Checking…" : "Check for updates"}</button></div>`;
}
// ...and its line: what it holds, from which release, when it looked.
function appsStatus(){
  if (!devApps) return "applies at once";
  const held = (devApps.apps || []).filter(a => a.files.length);
  const when = devApps.checked ? `looked ${ago(devApps.checked)}` : "not looked yet";
  if (devApps.problem) return `${devApps.problem} · ${when}`;
  return held.length ? `holds ${held.map(a => a.title).join(", ")} from ${devApps.release}${devApps.matched ? "" : " (no release matches this controller: the newest)"} · ${when}` : when;
}

// How the public hostname is set up, in the section itself (the operator,
// 11 Oct): the steps in order, with the controller's own port in them.
function tunnelSteps(s){
  const port = s?.tunnel?.port || 7680;
  return `<div class="sub">A name a node off your network dials to reach this controller, carried by a tunnel the controller runs itself. Nothing on your router changes, and the node never learns your address.</div>
    <ol class="setsteps dim">
      <li>In Cloudflare Zero Trust: Networks, Tunnels, Create a tunnel (Cloudflared), named for this controller. Copy the long <code>eyJ…</code> token from its install command into Tunnel token below. Do not run that command: the controller runs the tunnel.</li>
      <li>Pick the hostname, on a domain in your Cloudflare account (<code>bb.example.com</code>), and type it in Hostname.</li>
      <li>Either paste an API token with Zone DNS Edit on that domain and Account Cloudflare Tunnel Edit, and Apply writes the hostname's record and the tunnel's rules; or set them yourself on the tunnel's Public Hostname page: path <code>api/v1/agent/.*</code> to HTTP <code>localhost:${esc(String(port))}</code> (the controller's own port, inside its container), and the bare hostname to HTTP status 404, so the name serves no page.</li>
      <li>Apply. The line below says connected once the tunnel is up; Enroll node then fills the hostname in for a node reaching the controller through it.</li>
    </ol>`;
}

// The tunnel's line on its group's action bar (R176): whether cloudflared
// is here, running, registered, and at which name, as the server reads it.
function tunnelStatus(s){
  const t = s?.tunnel;
  if (!t) return "applies at once";
  if (t.error) return t.error;
  if (!t.installed) return "cloudflared is not in this image: the tunnel cannot run from here";
  if (!t.configured) return "off: paste a tunnel token and Apply to run the home tunnel here";
  if (!t.running) return "starting";
  if (!t.connected) return "running, not registered yet";
  // Registered is not routed (the operator, 11 Oct): the server asks the
  // name itself, and says so when the answer is somebody else's.
  if (t.route?.ok === false) return `connected, but ${t.route.said}`;
  if (t.route?.ok === true) return `connected: ${t.host || "the tunnel"} reaches this controller${tunnelNodes()}`;
  return `connected; checking that ${t.host || "the name"} reaches this controller`;
}

// Which nodes come in through the tunnel, on the same line: the route is
// each node's (chosen in Enroll node, kept on its record), and this is the
// one place the controller's side of it is set.
function tunnelNodes(){
  if (nodesList === null){ loadNodes(); return ""; }
  const via = (nodesList || []).filter(n => n.config?.tunnel?.kind === "public").map(n => n.name);
  return via.length ? `; ${via.join(", ")} come${via.length === 1 ? "s" : ""} in through it` : "; no node comes in through it yet";
}

// The reset's confirmation, the way a project's purge asks: the word typed
// in a box under the button, and the red verb asleep until it matches.
// What it moves aside is said once more here, since the thing a person
// regrets is the thing they did not read.
// Reset AerieOS (the operator, 12 Oct): a dialog that offers to
// un-enroll every node first, so each machine is clean to enroll again
// afterwards, then the typed word. The controller uninstalls each and waits
// for every one to report before anything is moved (server._reset_after),
// and this follows it to the end. A node with sessions or containers
// running cannot be ticked: un-enrolling would end them, and that is the
// person's to do first, as on the node's own Un-enroll.
function resetBusy(n){
  const rep = n.reported || {};
  const s = (rep.sessions || []).filter(x => /^u_[0-9a-f]{8}~/.test(String(x?.name || ""))).length;
  const c = Object.keys(rep.published || {}).length;
  return [s ? `${s} session${s === 1 ? "" : "s"} running` : "", c ? `${c} container${c === 1 ? "" : "s"} running` : ""]
    .filter(Boolean).join(" and ");
}

async function askReset(){
  const modal = $("resetmodal"), body = $("resetBody");
  if (!modal || !body) return;
  try { await loadNodes(); } catch {}
  const list = (nodesList || []).filter(n => n.kind === "agent" && n.state !== "retired");
  const shut = () => { modal.hidden = true; body.innerHTML = ""; };
  body.innerHTML = `<div class="field">
      <div class="hint bad">Accounts, nodes, space settings, tokens, the notebook, memories and logs move into a dated
        directory under the controller's config. Space files stay. The next page is the setup page.</div>
    </div>
    ${list.length ? `<div class="field">
      <label class="lbl">Un-enroll first</label>
      <div class="hint">So each machine can be enrolled again afterwards. One AerieOS set up is uninstalled from; any other is removed here only.</div>
      ${unenrollWhat(true)}
      ${list.map(n => { const busy = resetBusy(n), clean = !!(n.live && n.reported?.sandbox); return `
        <label class="ndcap"><input type="checkbox" data-rsnode="${esc(n.id)}"${busy ? " disabled" : " checked"}> ${esc(n.name)}: ${
          clean ? "uninstall AerieOS from it" : "remove it here; the machine keeps AerieOS until <code>sudo bb-sandbox uninstall</code> there"}${
          busy ? `<div class="hint bad">${esc(busy)}: end and bring them down first, or it stays enrolled</div>` : ""}</label>`; }).join("")}
      <label class="ndcap"><input type="checkbox" id="resetStores"> Also delete the stores on their disks: the toolchains, the caches, the artifacts</label>
    </div>` : ""}
    <div class="field">
      <label class="lbl" for="resetWord">Type reset to confirm</label>
      <input id="resetWord" autocomplete="off" placeholder="reset">
      <div class="hint bad" id="resetWhy" hidden></div>
    </div>
    <div class="foot"><span class="sp"></span>
      <button type="button" id="resetKeep">Keep it</button>
      <button type="button" class="danger" id="resetGo" disabled>Reset</button></div>`;
  modal.hidden = false;
  const word = $("resetWord"), go = $("resetGo"), why = $("resetWhy");
  word.oninput = () => { go.disabled = word.value.trim() !== "reset"; };
  $("resetKeep").onclick = shut;
  const send = async (ids) => {
    busy(go, ids.length ? "Un-enrolling" : "Resetting");
    why.hidden = true;
    let j;
    try{
      j = await (await postJSON("/api/reset", {confirm: word.value.trim(), unenroll: ids,
        stores: !!$("resetStores")?.checked})).json();
    }catch(e){ j = {error: "no answer from the dashboard: " + e}; }
    if (j.error){ unbusy(go, "Reset"); why.textContent = j.error; why.hidden = false; return; }
    if (j.unenrolling) return resetFollow(body, ids, send);
    resetGone(body, j.moved_to);
  };
  go.onclick = () => send([...body.querySelectorAll("[data-rsnode]:checked")].map(i => i.dataset.rsnode));
  word.focus();
}

// The un-enrolling, node by node, until the reset happens or something
// stops it; then Reset anyway, which leaves the rest enrolled.
function resetFollow(body, ids, send){
  const draw = j => {
    body.innerHTML = `<div class="field">
        <div class="hint">Un-enrolling, then the reset. A machine reports its uninstall when it is done; this can take a few minutes.</div>
        ${(j.nodes || []).map(x => `<div class="ndcap">${esc(x.name)}: ${
          x.error ? `<span class="bad">${esc(x.error)}</span>` : x.done ? "done" : x.how === "uninstall" ? "uninstalling…" : "removing…"}</div>`).join("")}
        <div class="hint bad" id="resetWhy"${j.error ? "" : " hidden"}>${esc(j.error || "")}</div>
      </div>
      <div class="foot"><span class="sp"></span>${j.error ? `
        <button type="button" id="resetShut">Close</button>
        <button type="button" class="danger" id="resetAnyway">Reset anyway</button>` : ""}</div>`;
    if (j.error){
      $("resetShut").onclick = () => { $("resetmodal").hidden = true; body.innerHTML = ""; };
      $("resetAnyway").onclick = async () => {
        let r;
        try{ r = await (await postJSON("/api/reset", {confirm: "reset"})).json(); }
        catch(e){ r = {error: "no answer from the dashboard: " + e}; }
        if (r.error){ $("resetWhy").textContent = r.error; $("resetWhy").hidden = false; return; }
        resetGone(body, r.moved_to);
      };
    }
  };
  const tick = async () => {
    let j;
    try{ j = await (await fetch("/api/reset")).json(); }
    catch{ return resetGone(body, ""); }       // the controller is starting over
    draw(j);
    if (j.moved_to) return resetGone(body, j.moved_to);
    if (j.running) setTimeout(tick, 3000);
  };
  tick();
}

function resetGone(body, moved){
  body.innerHTML = `<div class="field"><div class="hint">Reset: the dashboard is starting over${
    moved ? `; the old state is in ${esc(moved)}` : ""}. The setup page follows.</div></div>`;
  setTimeout(() => { location.href = "/login"; }, 2500);
}

function settingsSections(){
  const s = state?.settings;
  if (!s) return [{key: "wait", title: "Settings", status: "", html: `<div class="row stack2"><div class="grow"><div class="sub">the settings arrive with the first poll…</div></div></div>`}];
  const src = k => s.settings[k]?.source === "default" ? `<span class="pill">default</span>` : "";
  // What this install switched off from its environment (R81), listed first
  // when there is any: set where the container starts, so nothing here
  // turns it back on.
  const offs = Object.values(state?.off || {});
  const offSect = offs.length ? [{key: "off", title: "Switched off", status: String(offs.length), cls: "",
    html: `<div class="row stack2"><div class="grow"><div class="sub">Set where this container starts (FEATURES_OFF), so nothing here turns them back on.</div>${
      offs.map(w => `<div class="setrow">${esc(w)}</div>`).join("")}</div></div>`}] : [];
  return offSect.concat(SETTING_GROUPS.filter(g => (!g.can || state?.can?.[g.can]) && (!g.debug || state?.release?.dev_ok)
                                                && (!g.bare || state?.bare_metal)).map(g => {
    const field = f => {
            const v = s.settings[f.key]?.value;
            const id = "set_" + f.key;
            // A text is a field with its label over it; a secret the same,
            // typed blind, with "set" said beside it and never its value:
            // left empty it is left alone, and its own tick takes it off.
            if (f.type === "text" || f.type === "secret"){
              const isSet = f.type === "secret" ? !!s.settings[f.key]?.set : !!v;
              return `<div class="setrow col ctlrow"><label for="${id}">${esc(f.label)}${f.dev ? devMark() : ""}${helpIcon(f.hint)}${
                  f.type === "secret" ? (isSet ? ` <span class="pill ok">set</span>` : ` <span class="pill">not set</span>`) : src(f.key)}</label>
                <input id="${id}" type="${f.type === "secret" ? "password" : "text"}" data-set="${f.key}"${
                  f.type === "secret" ? ' data-secret="1"' : ""} value="${esc(f.type === "secret" ? "" : sdVal(id, v || ""))}"
                  placeholder="${esc(f.type === "secret" ? (isSet ? "set: paste a new one to replace it" : "paste it") : (f.placeholder || ""))}"
                  autocomplete="off" spellcheck="false">${
                  f.type === "secret" && isSet ? `<label class="ndcap"><input type="checkbox" data-clear="${f.key}"> take it off</label>` : ""}
              </div>`;
            }
            // A number is a short field beside its label, held to the
            // range the server keeps (settings.KEYS) by the browser too.
            // A pick among a few (R158 step 2: the connection's mode).
            if (f.type === "select"){
              return `<div class="setrow col ctlrow"><label for="${id}">${esc(f.label)}${helpIcon(f.hint)}${src(f.key)}</label>
                <select id="${id}" data-set="${f.key}">${(f.options || []).map(([val, lab]) =>
                  `<option value="${esc(val)}"${sdVal(id, v ?? "") === val ? " selected" : ""}>${esc(lab)}</option>`).join("")}</select>
              </div>`;
            }
            if (f.type === "number"){
              const m = s.meta?.[f.key] || {};
              return `<div class="setrow col ctlrow"><label for="${id}">${esc(f.label)}${helpIcon(f.hint)}${src(f.key)}</label>
                <input id="${id}" type="number" inputmode="numeric" data-set="${f.key}" data-num="1"
                  min="${esc(String(m.min ?? 0))}" max="${esc(String(m.max ?? ""))}" step="1"
                  value="${esc(String(sdVal(id, v ?? "")))}">
              </div>`;
            }
            // Every other setting is a switch: a checkbox inside its label,
            // the way the Tests bar's are, with what the label cannot say on
            // the ? (docs/design-language.md, Controls).
            return `<div class="logdays setrow ctlrow"><label class="ndcap">
                <input id="${id}" type="checkbox" data-set="${f.key}"${sdVal(id, !!v) ? " checked" : ""}> ${esc(f.label)}${f.dev ? devMark() : ""}${helpIcon(f.hint)}</label>${src(f.key)}
              </div>`;
    };
    // A group whose feature this install switched off (R81): its sentence
    // in place of its fields, which nothing could apply.
    if (g.off && featureOff(g.off)) return {key: g.key, title: g.title, status: "off", cls: "",
      html: `<div class="row stack2" data-group="${esc(g.title)}"><div class="grow">${deadWhy(featureOff(g.off))}</div></div>`};
    return {key: g.key, title: g.title, status: g.heading ? g.heading(s) : "", cls: g.headingCls ? g.headingCls(s) : "",
      html: `<div class="row stack2" data-group="${esc(g.title)}">
      <div class="grow">
        <div class="logset">
          ${g.intro ? g.intro(s) : ""}
          ${g.fields.filter(f => (!f.dev || s.settings.offer_unvetted?.value) && (!f.when || f.when(s))).map(field).join("")}
          <div class="actbar">
            <span class="state">${g.status ? g.status(s) : "applies at once"}</span>
            <button type="button" class="setApply" title="save">Apply</button>
          </div>
        </div>
      </div>
    </div>`};
  }));
}

function wireSettingsSections(el){
  wireUpdates(el);
  wireBackup(el);
  wireMove(el);
  // Ask Let's Encrypt now (R158 step 2): the Connection section's own press.
  el.querySelectorAll("[data-tlsissue]").forEach(b => b.onclick = async () => {
    busy(b, "Asking");
    try{
      const j = await (await postJSON("/api/tls", {action: "issue"})).json();
      if (j.error) notify(j.error, true);
      else notify("asking Let's Encrypt: the Connection section says how it goes");
    }catch(e){ notify("could not ask: " + failWords(e), true); }
    refresh();
  });
  el.querySelectorAll('[data-group]').forEach(box => {
    const btn = box.querySelector(".setApply");
    if (!btn) return;
    const apply = async () => {
      const set = {};
      box.querySelectorAll("[data-set]").forEach(i => {
        // A secret left empty is left as it is; its tick takes it off.
        if (i.dataset.secret && !i.value.trim()) return;
        set[i.dataset.set] = i.type === "checkbox" ? i.checked : i.dataset.num ? Number(i.value) : i.value.trim();
      });
      box.querySelectorAll("[data-clear]:checked").forEach(i => { set[i.dataset.clear] = ""; });
      busy(btn, "Applying");
      try{
        const post = extra => fetch("/api/settings", {method: "POST",
          headers: {"Content-Type": "application/json"}, body: JSON.stringify({set, ...extra})});
        let j = await (await post({})).json();
        // Maintenance mode asks first, with every other account's sessions
        // and what each is doing, since turning it on ends them.
        if (j.confirm === "maintenance"){
          if (!await maintAsk(j.sessions || [])) return;
          j = await (await post({confirmed: true})).json();
        }
        if (j.error) return notify(j.error, true);
        box.querySelectorAll("[data-set]").forEach(i => { delete settingsDraft[i.id]; });
        // What the tunnel did with it (R176): the record and rules written,
        // or why not, said here rather than only on the next poll's line.
        if (j.published?.error) notify(`saved; Cloudflare: ${j.published.error}`, true);
        else if (j.published?.did) notify(`saved; Cloudflare: ${j.published.did.join("; ")}`);
        else if (j.tunnel?.error) notify(`saved; the tunnel: ${j.tunnel.error}`, true);
        else notify("saved");
        refresh();
      }catch(e){ notify("settings: " + failWords(e), true); }
      finally{ if (btn.isConnected) unbusy(btn, "Apply"); }
    };
    btn.onclick = apply;
    box.querySelectorAll("input[type=text]").forEach(i => {
      i.onkeydown = e => { if (e.key === "Enter"){ e.preventDefault(); apply(); } };
    });
  });
}

// Ending Claude sessions nobody has used for a while. One rule for this
// container and every node, and a node enforces it itself: the value rides
// the agent's hello and lives in its node.json, so it holds while this
// controller is down. That is the point: a node's sessions outlive a
// controller restart on purpose, and the rule about when they end must not.
function idleSection(){
  const m = state?.idle?.minutes;
  if (m === undefined) return `<div class="sub">the idle rule arrives with the first poll…</div>`;
  // What 0 means is in the label, where a phone reads it (B459).
  return `<h4>Claude sessions</h4>
    <div class="logset">
      <div class="dim">A session idle this long is ended, on every node.</div>
      <div class="logdays setrow col ctlrow">
        ${lbl("idleMin", "Minutes idle before a session ends (0: never)", "shells are left alone")}
        <input id="idleMin" type="number" min="0" max="100000" step="1"
               value="${sdVal("idleMin", m)}" inputmode="numeric">
      </div>
      <div class="actbar">
        <span class="state">applies at once; a node hears on its next poll</span>
        <button type="button" id="idleApply" title="save it: a node hears on its next poll">Apply</button>
      </div>
    </div>`;
}

function wireIdleSection(el){
  const inp = el.querySelector("#idleMin");
  if (!inp) return;
  const apply = async () => {
    const minutes = parseInt(inp.value, 10);
    if (!(minutes >= 0)) return notify("minutes has to be 0 or more", true);
    const btn = el.querySelector("#idleApply");
    if (btn) busy(btn, "Applying");
    try{
      const r = await fetch("/api/idle", {method: "POST",
        headers: {"Content-Type": "application/json"},
        body: JSON.stringify({minutes})});
      const j = await r.json();
      if (j.error) return notify(j.error, true);
      delete settingsDraft.idleMin;
      notify(j.minutes ? `every agent's session ends after ${j.minutes} idle minute(s), here and on every node`
                       : "no session is ended for being idle");
      refresh();
    }catch(e){ notify("idle: " + failWords(e), true); }
    finally{ if (btn && btn.isConnected){ btn.disabled = false; btn.textContent = "Apply"; } }
  };
  el.querySelector("#idleApply").onclick = apply;
  inp.onkeydown = e => { if (e.key === "Enter"){ e.preventDefault(); apply(); } };
}

// Where the controller keeps what grows (paths.py): each kind on its own line,
// the path in use, and a move in flight or the last one's error. Applying a
// path moves what is there and switches once it has all arrived. The JSON
// records, the database, the signing keys and the git credentials stay in
// /config whatever is set here, and the section says so. An administrator's:
// the poll carries nothing for anybody else, and the section is absent.
function pathsSection(){
  const list = state?.paths?.paths;
  if (!list) return "";
  const line = p => {
    const id = "path_" + p.name;
    const note = p.pinned ? `<div class="dim">${esc(p.pinned)}</div>`
      : p.moving?.error ? `<div class="sub bad">moving to ${esc(p.moving.to)} stopped: ${esc(p.moving.error)}</div>`
      : p.moving ? `<div class="dim">moving to ${esc(p.moving.to)}; ${esc(p.path)} is in use until it is done</div>`
      : !p.set ? "" : `<div class="dim">default: ${esc(p.default)}</div>`;
    return `<div class="logdays setrow col ctlrow">
        ${lbl(id, p.name, p.what)}
        <input id="${id}" type="text" data-path="${esc(p.name)}" spellcheck="false" autocomplete="off"
               value="${esc(sdVal(id, p.path))}"${p.pinned || (p.moving && !p.moving.error) ? " disabled" : ""}>
        ${note}
      </div>`;
  };
  return `<div class="row stack2" data-group="Storage">
      <div class="grow">
        <h4>Storage on this controller</h4>
        <div class="logset">
          <div class="dim">Where what grows is kept. A new path must be empty or new; what is there is moved across.
            The records, the database, the signing keys and the git credentials stay in the state directory.</div>
          ${list.map(line).join("")}
          <div class="actbar">
            <span class="state">applies once what is there has moved</span>
            <button type="button" id="pathsApply" title="move each changed one to its new path">Apply</button>
          </div>
        </div>
      </div>
    </div>`;
}

function wirePathsSection(el){
  const btn = el.querySelector("#pathsApply");
  if (!btn) return;
  const apply = async () => {
    const list = state?.paths?.paths || [];
    const changed = [...el.querySelectorAll("input[data-path]")]
      .filter(i => !i.disabled && i.value.trim() !== (list.find(p => p.name === i.dataset.path)?.path || ""));
    if (!changed.length) return notify("nothing changed");
    busy(btn, "Applying");
    try{
      for (const i of changed){
        const r = await fetch("/api/paths", {method: "POST", headers: {"Content-Type": "application/json"},
          body: JSON.stringify({name: i.dataset.path, path: i.value.trim()})});
        const j = await r.json();
        if (j.error) return notify(`${i.dataset.path}: ${j.error}`, true);
        delete settingsDraft[i.id];
        notify(j.moving ? `${i.dataset.path}: moving what is there; it switches once it has arrived`
                        : `${i.dataset.path} is kept at ${i.value.trim() || "its default"}`);
      }
      refresh();
    }catch(e){ notify("storage: " + failWords(e), true); }
    finally{ if (btn.isConnected) unbusy(btn, "Apply"); }
  };
  btn.onclick = apply;
  el.querySelectorAll("input[data-path]").forEach(i => {
    i.onkeydown = e => { if (e.key === "Enter"){ e.preventDefault(); apply(); } };
  });
}

// The global rules (R63) are not on this tab: every project's notebook lists
// them under its own rules on the Briefing, with a switch for that project,
// and an administrator changes them there for every project (nb-rules.js).
