// The Installed page (R172, the operator, 28 Oct: a thing is configured
// where it is installed, not in the catalog): under Machines beside Nodes
// and Storage, one node picked, what is installed there by kind, each a
// row that opens on what the Library's card does not show: an agent's
// sign-in and what this person added to it, a toolchain's path, system
// packages and needs, the machine's own driver and toolkit, a pack's or a
// service's Configure from its config block, a job's error, and Remove.
// It reads the Library's read for the node (/api/library) and keeps only
// what is installed; the Library keeps Install.
//
// Chrome from docSurface(); the hard rules are uniform.mjs's. Loaded
// before the page's own script, so everything here is a declaration.

"use strict";

let inst = null, instNode = "";
let instWantAgent = "";        // the agent whose page a door asked for, until the rows land
const instDraft = {};          // what was typed into a Configure form and not saved yet, by row
const INST_KINDS = [["agent", "Coding agents"], ["toolchain", "Toolchains"], ["pack", "Tool packs"], ["service", "Services"]];

function openInstalledTab(){
  openTab({kind: "installed", arg: "__installed", label: "Installed"});
}
// ...on a node somebody named (a project's Sign in on NODE, the bell), the
// agent's row open on its sign-in once the rows land.
function openInstalledOn(id, agent = "", row = ""){
  // ...or any thing's own page by its key (service:model-router, R181: a
  // system container's Configure), at its Configure, on that node.
  if (row){ openThing(id, row, "configure"); return; }
  if (agent) instWantAgent = agent;
  openKindOn("installed", id);
}

// The node the page opens on: the one it showed last, else the Library's,
// else the first agent node.
function instPick(){
  const live = liveAgents(), want = keptNode("installed", {have: live, also: PAGE_KINDS.library.keep});
  instNode = want;
  // The toolchain job's verbs act on tcNode; the pack dialogs read its rows.
  if (want && want !== tcNode){ tcNode = want; toolchains = null; }
  return live.find(n => n.id === want) || null;
}

function loadInstalled(){
  return reading("installed", async () => {
    if (nodesList === null || nodesStale) await nodesKnown();
    if (!instPick()){ inst = {nonode: true}; return; }
    // A reply is kept while it is still about the node on show.
    const node = instNode;
    const got = await getJSON("/api/library?node=" + encodeURIComponent(node));
    if (instNode !== node) return;
    inst = got;
    let wantPage = "";
    if (!inst.error){
      toolchainsSeen(inst);
      if (instWantAgent){
        const r = (inst.rows || []).find(x => x.kind === "agent" && x.agent === instWantAgent);
        instWantAgent = "";
        // The agent's own page, at its sign-in (R181 step 2), once drawn.
        if (r) wantPage = `agent:${r.name}`;
      }
    }
    if (wantPage) setTimeout(() => openThing(instNode, wantPage, "signin"));
  });
}

// What is here: an installed row, the machine's own rows, a deployed
// service, and an agent whose card a person signs in on (Claude Code's,
// so a node without it still says where its sign-in would be).
function instHere(r){
  // A service that asks for settings first is here before it is deployed
  // (the router: configured, then installed); one that asks nothing (nginx,
  // the Scanners: R264) is here once the Library put it on the node.
  if (r.kind === "service") return r.installed || r.running || !!(r.config || []).length;
  if (r.machine) return true;
  if (r.kind === "agent") return r.installed || r.agent === "claude";
  return r.installed || r.unknown || r.running;
}

// Where it stands, in a few words at the row's right.
function instState(r){
  const w = packState;
  if (r.running) return w(`${esc(r.doing === "remove" ? "removing" : r.doing === "check" ? "checking" : r.doing === "deploy" ? "deploying" : r.installed ? "updating" : "installing")}<span class="dots"></span>`);
  if (r.kind === "service") return r.installed ? w("deployed", "ok") : r.ready ? w(esc(r.ready), "warn") : w("configured, not deployed", "warn");
  if (r.machine) return packMachineState(r, "not installed");
  if (r.kind === "agent" && !r.installed) return w("not installed: the Library installs it", "warn");
  // Kept here and not fitting this AerieOS: switched off until one that
  // does is kept, which its Library card offers when the catalog has one.
  if (r.pack?.disabled) return w(esc(r.pack.disabled) + ": the Library offers a version that fits when there is one", "warn");
  // The version that is out is the row's pill ("2.1.314 is out"), so the
  // state says only that, as the Library's card does.
  return packHeldState(r);
}

// The row's verbs: Update where its state says one is available, as the
// Library's card has it (a row saying so with nothing to press was out of
// step with it), Remove where it is here (a pack's Remove is the dialog's
// own, which asks where it is still installed), and a service's Install
// once something is behind it.
// While its own job runs they are drawn dead, never taken away (the
// operator, 22 Nov), and its state line says what runs.
function instActs(r, may){
  const off = r.running ? " disabled" : "";
  const a = (act, words, cls = "") => `<button type="button"${cls ? ` class="${cls}"` : ""} data-instact="${act}" data-instkind="${esc(r.kind)}" data-instname="${esc(r.name)}"${off}>${esc(words)}</button>`;
  if (r.kind === "service") return !may.configure ? "" : r.installed ? a("remove", "Remove", "danger")
    : `<button type="button" class="primary" data-instact="install" data-instkind="service" data-instname="${esc(r.name)}"${r.ready || r.running ? " disabled" : ""}${r.ready ? ` title="${esc(r.ready)}"` : ""}>Install</button>`;
  if (r.machine) return r.machine.managed && !r.machine.imaged && r.installed && may.install ? a("remove", "Remove", "danger") : "";
  if (!may.install) return "";
  // Software update, as the Library's card says it (the operator, 13 Nov).
  // ...and Install again on a copy an earlier manifest made, which takes what
  // the one kept now installs (B799): the same job, removing it first.
  const upd = r.installed && r.update ? a("update", "Software update", "primary")
    : r.installed && r.receipt?.stale ? a("update", "Install again", "primary") : "";
  // Edit on a pack a person added themselves, as on the Library's card: one
  // kept from the catalog is the catalog's, its kept copy reached from its
  // Details page there.
  if (r.kind === "pack" && r.pack) return `${upd}${r.tier === "sideloaded" ? a("edit", "Edit") : ""}${r.installed ? a("remove", "Remove", "danger") : ""}`;
  return r.installed ? `${upd}${a("remove", "Remove", "danger")}` : "";
}

// The open row: what the node knows of it, and what a person sets here.
let agYours = {plugins: [], mcp: {}};   // this account's plugins and MCP servers on the node, as the read last said

// What this account added to an agent on the node (R95 step 15, moved here
// from Profile; the Agents page's until R170): Claude Code's plugins, and
// each agent's MCP servers, by name, as the node last said. Read here;
// changed in a session.
function agExtras(a){
  const pl = a.id === "claude" ? (agYours.plugins || []) : [];
  const mcp = (agYours.mcp || {})[a.id] || [];
  const one = p => `<code>${esc(p.id.replace(/@claude-plugins-official$/, ""))}</code>${p.version ? ` ${esc(p.version)}` : ""}${
    p.scope === "project" ? ` (${esc(p.project ? projLabel(p.project) : "a space")})` : ""}${p.enabled === false ? ` <span class="dim">off</span>` : ""}`;
  const rows = [
    a.id === "claude" ? ["your plugins", pl.length ? pl.map(one).join(", ") : "none", {html: true}] : null,
    ["your MCP servers", mcp.length ? mcp.map(x => `<code>${esc(x)}</code>`).join(", ") : "none", {html: true}],
  ].filter(Boolean);
  return `<div class="field agpart"><div class="fsub">Yours</div>${factGrid(rows, "agextras")}<div class="hint">${
    a.id === "claude" ? "Changed with <code>/plugin</code> and <code>/mcp</code> in a Claude session, for you alone."
      : `Set up in ${esc(a.product)}'s own configuration, for you alone.`}</div></div>`;
}

// What an installed thing is on this node, for its page's first section
// (R181 step 2): the machine's own driver and toolkit, a toolchain's or a
// pack's lines, an agent's.
function instAboutLines(r){
  const lines = [];
  if (r.machine){
    lines.push(r.name === TC_DRIVER ? tcDriverLine(r.machine) : tcToolkitLine(r.machine));
    if (!r.machine.managed) lines.push(`<span class="sub warn">This machine is its owner's, not an AerieOS sandbox: ${r.name === TC_DRIVER ? "its driver" : "the toolkit"} is installed there by hand.</span>`);
    if (r.machine.settling) lines.push(`<span class="sub">The node is reporting what the last job left<span class="dots"></span></span>`);
    return lines.filter(Boolean).join("");
  }
  if (r.about) lines.push(`<span class="sub">${esc(r.about)}</span>`);
  // Who it is by, as its Library card's Details say (makerLine).
  if (makerLine(r)) lines.push(makerLine(r));
  if (r.kind === "toolchain" || r.kind === "pack"){
    if (r.tool) lines.push(`<span class="sub">Adds <code>aerie tool ${esc(r.tool)}</code> to a session.</span>`);
    if (r.needs?.length) lines.push(`<span class="sub">Needs ${esc(r.needs.join(", "))}, installed with it.${r.needed_by?.length ? ` Needed by ${esc(r.needed_by.join(", "))}.` : ""}</span>`);
    else if (r.needed_by?.length) lines.push(`<span class="sub">Needed by ${esc(r.needed_by.join(", "))}.</span>`);
    lines.push(tcSystemLine(r, !!inst?.managed));
    lines.push(tcNeedsLine(r));
    if (r.path) lines.push(`<span class="sub">At ${esc(r.path)}.</span>`);
    lines.push(tcVerifiedLine(r));
    lines.push(tcReceiptLines(r));
    if (r.reopen) lines.push(`<span class="sub warn">${r.reopen === 1 ? "1 session" : `${r.reopen} sessions`} open here started before this was installed: reopen ${r.reopen === 1 ? "it" : "them"} to use it.</span>`);
    if (r.pinned?.length) lines.push(`<span class="sub">Pinned by ${esc(r.pinned.map(projLabel).join(", "))}.</span>`);
    if (r.pack) lines.push(`<span class="sub">${r.pack.here ? "Made here" : `From <code>${esc(r.pack.url)}</code> at ${esc((r.pack.commit || "").slice(0, 12))}`}${r.pack.by ? `, added by ${esc(r.pack.by)}` : ""}.</span>`);
  }
  if (r.kind === "agent"){
    const a = agentById(r.agent);
    lines.push(`<span class="sub">${a?.product ? `${esc(a.product)}, installed` : "Installed"} for the node's session account; ${r.latest ? `the latest is ${esc(r.latest)}` : "its latest is not known yet"}.${
      a?.provider ? ` Signs in with ${/^(?:[AEIOU]|x(?=[A-Z]))/.test(a.provider) ? "an" : "a"} ${esc(a.provider)} account.` : ""}</span>`);
    if (r.error) lines.push(`<span class="sub bad">${esc(r.error)}</span>`);
    if (r.agent === "open"){
      const rt = (inst?.rows || []).find(x => x.kind === "service" && x.service === "router");
      lines.push(rt?.installed ? `<span class="sub">Runs through the model router on this node${(rt.status?.models || []).length ? `, ${rt.status.models.filter(m => !m.wild).length} models known` : ""}.</span>`
        : `<span class="sub warn">Needs the model router on this node: under Services on the Installed page.</span>`);
    }
  }
  return lines.filter(Boolean).join("");
}

// What a toolchain or a pack asks for here: this node's answers for whoever
// may Configure here, and each person's own for whoever works on this node's
// projects (R172 step 5).
function instConfigLines(r){
  const lines = [];
  if (r.config?.length && r.values && inst?.may?.configure) lines.push(instConfigForm(r, "node"));
  if (r.config?.length && r.mine && inst?.may?.yours) lines.push(instConfigForm(r, "person"));
  return lines.join("");
}
// Whether a row has a Configure of its own on its page.
function instConfigurable(r){
  return r.kind === "service" ? !!inst?.may?.configure : !!instConfigLines(r);
}

// What a pack or a service asks for on this node (R172): its config block
// as a form, the answers as the page may see them (a secret only as set:
// typed to replace, "clear" to take it out), Save to the card's own route.
function instConfigField(f, v, key){
  const id = `ic-${key}-${f.name}`.replace(/[^A-Za-z0-9_-]/g, "_");
  const at = `data-icf="${esc(f.name)}"`;
  const help = f.help || "";
  // Each a cell of the form (R301): its label over it, a list's rows and a
  // space's ticks across it.
  switch (f.kind){
    case "secret": return formField(id, f.label, `<input id="${id}" type="password" ${at} autocomplete="off" spellcheck="false" placeholder="${v ? "set: type to replace, or 'clear'" : f.required ? "required" : ""}">`, {help});
    case "text": return formField(id, f.label, `<input id="${id}" type="text" ${at} autocomplete="off" spellcheck="false" value="${esc(v || "")}">`, {help});
    case "switch": return `<div class="fcell fwide"><label class="ndcap"><input id="${id}" type="checkbox" ${at}${v ? " checked" : ""}> ${esc(f.label)}${f.help ? helpIcon(f.help) : ""}</label></div>`;
    case "choice": return formField(id, f.label, `<select id="${id}" ${at}>${(f.choices || []).map(c => `<option value="${esc(c.value)}"${c.value === v ? " selected" : ""}>${esc(c.label)}</option>`).join("")}</select>`, {help});
    case "projects": {
      const all = (inst?.rows || []).find(x => x.kind === "service" && x.service === "router")?.all_projects || [];
      return formField(id, f.label, `<div class="fticks" id="${id}">${all.length ? all.map(p => `<label class="ndcap"><input type="checkbox" data-icproj="${esc(f.name)}" value="${esc(p)}"${(v || []).includes(p) ? " checked" : ""}> ${esc(p)}</label>`).join("") : `<span class="dim">no spaces yet</span>`}</div>`, {help, wide: true});
    }
    case "list": {
      const rows = (v || []).map((row, j) => `<div class="ctlrow icrow" data-iclist="${esc(f.name)}" data-icrow="${j}">${
        (f.fields || []).map(sf => sf.kind === "secret"
          ? `<input type="password" data-icsub="${esc(sf.name)}" placeholder="${row[sf.name] ? "set: type to replace" : esc(sf.label)}" autocomplete="off" spellcheck="false" aria-label="${esc(sf.label)}">`
          : `<input type="text" data-icsub="${esc(sf.name)}" placeholder="${esc(sf.help || sf.label)}" value="${esc(row[sf.name] || "")}" autocomplete="off" spellcheck="false" aria-label="${esc(sf.label)}">`).join("")}
        <button type="button" data-icrm="${esc(f.name)}" data-icrow="${j}">Remove</button></div>`).join("");
      return formField(id, f.label, `<div class="iclist" id="${id}">${rows}<div class="addbar ctlrow"><button type="button" data-icadd="${esc(f.name)}">Add a row</button></div></div>`, {help, wide: true});
    }
    default: return "";
  }
}
// The fields of one scope: the node's (one answer for everybody there) or
// a person's own (R172 step 5).
const instScoped = (r, scope) => (r.config || []).filter(f => (f.scope || "node") === scope);
function instConfigForm(r, scope = "node"){
  const fields = instScoped(r, scope);
  if (!fields.length) return "";
  const key = `${r.kind}:${r.name}`, dk = `${key}|${scope}`, v = instDraft[dk] || (scope === "person" ? r.mine : r.values) || {};
  const both = instScoped(r, "node").length && instScoped(r, "person").length;
  const title = scope === "person" ? `Yours on ${inst?.name || "this node"}` : both ? `This node: ${inst?.name || ""}` : `Configure on ${inst?.name || "this node"}`;
  return `<div class="field agpart icform" data-icform="${esc(key)}" data-icscope="${scope}"><div class="fsub">${esc(title)}</div>
    ${scope === "person" ? `<div class="hint">Yours alone: your sessions' verbs here read these over the node's.</div>` : ""}
    ${formBox({fields: fields.map(f => instConfigField(f, v[f.name], `${key}-${scope}`)),
      state: `<span class="state">${r.kind === "service" && r.installed ? "saving rebuilds it with the change" : ""}</span>`,
      foot: [`<button type="button" class="primary" data-icsave="${esc(key)}">Save</button>`]})}</div>`;
}
function instConfigRead(form, r, scope = "node"){
  const v = {};
  for (const f of instScoped(r, scope)){
    if (f.kind === "secret" || f.kind === "text" || f.kind === "choice") v[f.name] = form.querySelector(`[data-icf="${CSS.escape(f.name)}"]`)?.value ?? "";
    else if (f.kind === "switch") v[f.name] = !!form.querySelector(`[data-icf="${CSS.escape(f.name)}"]`)?.checked;
    else if (f.kind === "projects") v[f.name] = [...form.querySelectorAll(`[data-icproj="${CSS.escape(f.name)}"]:checked`)].map(i => i.value);
    else if (f.kind === "list") v[f.name] = [...form.querySelectorAll(`.icrow[data-iclist="${CSS.escape(f.name)}"]`)].map(row =>
      Object.fromEntries((f.fields || []).map(sf => [sf.name, row.querySelector(`[data-icsub="${CSS.escape(sf.name)}"]`)?.value ?? ""])));
  }
  return v;
}
// What a service says of itself here: the router's address, the models
// known and the spend with the presses that read them again, and Ollama's
// models pulled and removed.
function instServiceLines(r){
  const st = r.status || {};
  if (r.service !== "router") return "";
  // What it is was said above the row (the catalog's line, B431): only what
  // Install does is said here.
  if (!r.installed) return `<span class="sub">Install deploys it as a written container once something is behind it: a provider key, an endpoint of your own, or Ollama.</span>`;
  const models = (st.models || []).filter(m => !m.wild);
  const pulled = (st.ollama?.models || []).map(m => `<div class="row"><span class="grow">${esc(m)}</span><button type="button" data-instsvc="ollama-remove" data-instmodel="${esc(m)}">Remove</button></div>`).join("");
  return `<span class="sub">LiteLLM answers at <code>${esc(st.url || "")}/v1</code> for the spaces allowed, each with a key of its own.</span>
    <div class="actbar"><span class="state">${models.length ? `${models.length} model${models.length === 1 ? "" : "s"} known${st.models_at ? `, read ${esc(ago(st.models_at))}` : ""}` : "no models read yet"}${
      Object.keys(st.spend || {}).length ? ` · spent ${Object.entries(st.spend).map(([p, s]) => `${esc(p)} $${Number(s).toFixed(2)}`).join(", ")}` : ""}</span>
      <button type="button" data-instsvc="models">Read the models</button><button type="button" data-instsvc="spend">Read the spend</button></div>
    ${st.ollama?.on ? `<div class="field"><div class="ctlrow"><input type="text" data-instpull placeholder="a model Ollama lists, such as qwen2.5-coder:7b" data-ph-short="model name" autocomplete="off" spellcheck="false">
      <button type="button" data-instsvc="ollama-pull">Pull</button></div>${pulled ? `<div class="rows">${pulled}</div>` : `<div class="sub dim">Nothing pulled yet.</div>`}</div>` : ""}`;
}

// A row: what it is in a line, where it stands and its verbs; Open, and
// Configure where it asks for anything, open its own page (R181 step 2).
function instRow(r, may){
  const key = `${r.kind}:${r.name}`;
  const pill = packVersionPill(r), ver = pill && ` ${pill}`;
  const err = packJobErr(r, inst?.job);
  const conf = instConfigurable(r) ? `<button type="button" data-instopen="${esc(key)}" data-instat="configure">Configure</button>` : "";
  return `<div class="row irow" data-irow="${esc(key)}"><div class="grow">
      <div class="name">${esc(r.label)}${ver}${r.update && r.latest ? ` <span class="pill warn">${esc(r.latest)} is out</span>` : ""} <button type="button" class="link imore" data-instopen="${esc(key)}">Open</button></div>
      <div class="sub iabout">${esc(r.about)}</div>${err}
    </div><div class="acts">${instState(r)}<span class="actbar">${conf}${instActs(r, may)}</span></div></div>`;
}

function renderInstalledInto(i){
  const d = docSurface(i, "installed");
  if (!d) return;
  if (inst === null){
    d.setBar("");    // the node is the Machines header's (R177)
    drawHTML(d.list, skTpl(pageHead({line: [{value: GHOST, label: "installed"}]})
      + INST_KINDS.map(([k, title]) => docSection("installed", k, title, "", skRows(2))).join("")));
    if (!readRev("installed") && !readBusy("installed")) loadInstalled();
    return;
  }
  if (inst.nonode){
    d.setBar("");
    drawHTML(d.list, noNodeYet("toolchains and coding agents install on a node", "instnone"));
    return;
  }
  const may = inst.may || {};
  d.setBar("");    // the node is picked in the Machines group's header (R177)
  if (inst.error){
    patch(d.list, readFailed("could not read what is installed: " + inst.error));
    wireReadAgain(d.list, () => loadInstalled());
    return;
  }
  const rows = (inst.rows || []).filter(instHere);
  const due = rows.filter(r => r.update).length;
  const unmet = Object.entries(inst.sysdeps?.unmet || {});
  const notes = unmet.length ? `<div class="field"><div class="notice warn instsys">System packages ${esc(inst.name || "this node")} lacks for what its store holds (${esc(inst.sysdeps.family || "")}): ${
      unmet.map(([r, ps]) => `${esc(r)}: ${esc(ps.join(" "))}`).join("; ")}. ${inst.sandbox && may.install
        ? `<button type="button" data-instsysdeps title="install these on ${esc(inst.name || "the node")} without reinstalling the toolchains">Install system packages</button>`
        : "This node's owner installs them: the agent does not administer the machine."}</div></div>` : "";
  // One line (R274): what is installed, and what wants updating.
  const head = pageHead({line: [
    {value: rows.filter(r => r.installed).length, label: "installed"},
    due ? {value: due, label: due === 1 ? "update due" : "updates due", tone: "warn"} : null,
  ]});
  // Where it is all kept, at the foot of what is kept there (R274).
  const where = inst.store?.root ? `<div class="field"><div class="hint">Kept in <code>${esc(inst.store.root)}</code>${
    inst.store.free_mb ? `, ${esc(humanBytes(inst.store.free_mb * 1048576))} free` : ""}.</div></div>` : "";
  const sects = INST_KINDS.map(([k, title]) => {
    // By its group, as the Library sorts it: a pack that brings a coding
    // agent sits with the coding agents (the operator, 12 Nov).
    const here = rows.filter(r => libGroup(r) === k);
    if (!here.length) return "";
    const body = `<div class="rows">${here.map(r => instRow(r, may)).join("")}</div>`;
    return docSection("installed", k, title, k === "agent" ? `${here.filter(r => r.installed).length} of ${here.length}` : String(here.length), body);
  }).join("") || `<div class="empty">Nothing installed on ${esc(inst.name || "this node")} yet: ${inst.host_only
      ? "it hosts containers only, and the Library deploys its services there" : "the Library installs toolchains, coding agents and packs there"}.</div>`;
  // Rows the redraw puts elsewhere (one arriving on top, one whose state
  // sorts it anew) slide there, and a new one fades in (reflow).
  reflow(d.list, ".irow[data-irow]", e => e.dataset.irow, () => patch(d.list, `<div data-instnode="${esc(instNode)}">${notes}${head}${sects}${where}</div>`));
  wireInstalled(d.el);
}

function wireInstalled(root){
  wireSections(root);
  wireSignin(root);
  root.querySelectorAll("[data-instopen]").forEach(b => b.onclick = () => instOpen(b.dataset.instopen, b.dataset.instat || ""));
  root.querySelectorAll("[data-tcsys]").forEach(b => b.onclick = async () => { await tcAct("sysdeps", [b.dataset.tcsys]); loadInstalled(); });
  root.querySelectorAll("[data-tcneed]").forEach(b => b.onclick = async () => { await tcAct("install", [b.dataset.tcneed]); loadInstalled(); });
  const sd = root.querySelector("[data-instsysdeps]");
  if (sd) sd.onclick = () => pressing(sd, async () => { busy(sd, "Installing"); await tcAct("sysdeps"); await loadInstalled(); });
  root.querySelectorAll(".icform").forEach(form => {
    const key = form.dataset.icform, scope = form.dataset.icscope || "node", dk = `${key}|${scope}`;
    const r = (inst?.rows || []).find(x => `${x.kind}:${x.name}` === key);
    if (!r) return;
    const read = () => { instDraft[dk] = instConfigRead(form, r, scope); return instDraft[dk]; };
    // A secret typed and not saved comes back after a redraw (a row added,
    // a poll): a password field is drawn empty, so the draft fills it.
    const dr = instDraft[dk];
    if (dr) for (const f of instScoped(r, scope)){
      if (f.kind === "secret" && typeof dr[f.name] === "string" && dr[f.name]){ const i = form.querySelector(`[data-icf="${CSS.escape(f.name)}"]`); if (i && !i.value) i.value = dr[f.name]; }
      if (f.kind === "list") form.querySelectorAll(`.icrow[data-iclist="${CSS.escape(f.name)}"]`).forEach((row, j) => {
        for (const sf of f.fields || []) if (sf.kind === "secret" && typeof dr[f.name]?.[j]?.[sf.name] === "string" && dr[f.name][j][sf.name]){
          const i = row.querySelector(`[data-icsub="${CSS.escape(sf.name)}"]`); if (i && !i.value) i.value = dr[f.name][j][sf.name]; }
      });
    }
    // Set, not added: a patched page keeps the form across its draws (R244).
    form.oninput = read;
    form.onchange = read;
    form.querySelectorAll("[data-icadd]").forEach(b => b.onclick = () => { const v = read(); v[b.dataset.icadd] = [...(v[b.dataset.icadd] || []), {}]; readMoved("installed"); drawPanes(); });
    form.querySelectorAll("[data-icrm]").forEach(b => b.onclick = () => { const v = read(); v[b.dataset.icrm].splice(Number(b.dataset.icrow), 1); readMoved("installed"); drawPanes(); });
    const save = form.querySelector("[data-icsave]");
    if (save) save.onclick = () => pressing(save, async () => {
      busy(save, "Saving");
      const j = await postJSON("/api/library", {action: "configure", node: instNode, pack: r.name, values: read(), ...(scope === "person" ? {scope} : {})});
      if (j.error){ notify(j.error, true); return; }
      delete instDraft[dk];
      // Saved, the form is drawn fresh: a key is shown as set and its field
      // empties to type a replacement into.
      drawFresh(form);
      notify(j.job ? "saved: the router is rebuilt with the change, its row on the Containers page has the build" : "saved");
      await loadInstalled();
    });
  });
  root.querySelectorAll("[data-instsvc]").forEach(b => b.onclick = () => pressing(b, async () => {
    const row = b.closest(".irow"), r = (inst?.rows || []).find(x => `${x.kind}:${x.name}` === row?.dataset.irow);
    if (!r) return;
    const act = b.dataset.instsvc;
    busy(b, act === "ollama-pull" ? "Pulling" : act === "ollama-remove" ? "Removing" : "Reading");
    const model = act === "ollama-pull" ? row.querySelector("[data-instpull]")?.value || "" : b.dataset.instmodel || "";
    const j = await postJSON("/api/library", {action: act, node: instNode, pack: r.name, model});
    if (j.error) notify(j.error, true); else if (act === "ollama-pull") notify(`pulling ${model}: a job on the Jobs page`);
    await loadInstalled();
  }));
  root.querySelectorAll("[data-instact]").forEach(b => b.onclick = () => instAct(b, b.dataset.instact, b.dataset.instkind, b.dataset.instname));
}

// Open on a row: the thing's own page on this node. A service whose
// settings are a page of their own (nginx's routes and certificates, the
// Scanners' schedule and runs: R264) opens that page for the node.
function instOpen(key, at = ""){
  const pages = {nginx: node => openNginxTab(node), scanners: () => openScannersTab()};
  const r = (inst?.rows || []).find(x => `${x.kind}:${x.name}` === key);
  const page = r?.kind === "service" && r.installed ? pages[r.service] : null;
  if (page) return page(instNode);
  openThing(instNode, key, at);
}

async function instAct(b, act, kind, name){
  const r = (inst?.rows || []).find(x => x.kind === kind && x.name === name);
  if (!r) return;
  const where = (nodesList || []).find(x => x.id === instNode)?.name || "this node";
  if (kind === "service"){
    if (act === "remove" && !await askYes(`Remove ${r.label} from ${where}? ${r.removes || "Its keys stay here sealed; the spaces lose their way to it."}`, {verb: "Remove", danger: true})) return;
    await packDeploy(b, instNode, r, act, loadInstalled);
    return;
  }
  if (act === "update"){
    if (kind === "agent"){ await agentUpdate(b, instNode, r, loadInstalled); return; }
    busy(b, "Updating");
    // The job reads the store's record of this node, not its rows: the
    // stand-in the page's read keeps will do.
    if (!toolchains || toolchains.nonode || toolchains.error || tcNode !== instNode) await loadToolchains();
    await tcAct("install", [r.name]);
    await loadInstalled();
    return;
  }
  if (kind === "agent"){
    if (!await askYes(`Remove ${r.label} from ${where}? Its sessions end, and none starts there until it is installed again.`)) return;
    await sayPost(b, "Removing", "/api/agents", {action: "remove", node: instNode, agent: r.agent || ""}, "", loadInstalled);
    return;
  }
  if (act === "edit"){
    // The dialog finds the pack in the store's rows, read first where the
    // page holds only its stand-in for them.
    await toolchainsFor(instNode);
    tpOpen(r.name);
    return;
  }
  // The machine's own two say what removing them does to the machine (R102,
  // as the Toolchains page asked them); a store's toolchain, its files.
  // With no card there is nothing for nouveau to take back (B168).
  const ask = r.name === TC_DRIVER && r.machine?.state === "nocard"
    ? `Remove NVIDIA's driver from ${where}? It has no card to drive here, and its tries for one stop.`
    : r.name === TC_DRIVER
    ? `Remove NVIDIA's driver from ${where}? The emulator's GPU display goes with it, and nouveau takes the card back when the machine restarts.`
    : r.name === TC_TOOLKIT
    ? `Remove the NVIDIA container toolkit from ${where}? A container that reserves the card no longer starts; NVIDIA's package source goes with it.`
    : `Uninstall ${r.label} from ${where}? The files are deleted; installing it again re-downloads them.`;
  if (!await askYes(ask)) return;
  busy(b, "Removing");
  await tcAct("remove", [r.name]);
  await loadInstalled();
}
