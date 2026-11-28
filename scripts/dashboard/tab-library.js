// The Library (one place for everything a
// AerieOS installs or runs, not a page each for toolchains, agents and
// apps): one list, read whole from /api/library for one node, of the
// toolchains the catalog offers and what the node's store holds, the coding
// agents with their versions, the tool packs a person added, the apps a NAS
// runs as containers, the vetted catalog's offers and the companions a
// person downloads; each a row of one shape (its kind, its tier, what it is,
// where it stands on the node) with one verb, and opening on its whole
// description. The node picker in the bar, a search box and chips by kind
// and tier under the head; the rows under a section per kind.
//
// Nothing here installs a second way: a toolchain's Install is the
// Toolchains job (tcAct), an agent's the /api/agents verb, a pack's the Add
// tool pack dialog (tpOpen, tpOpenCatalog) and an app's the New container
// dialog with the app picked, so what each did yesterday it does today.
// Chrome from docSurface; the hard rules are uniform.mjs's. Loaded before
// the page's own script, so everything here is a declaration.

"use strict";

let lib = null, libNode = "";
// The narrowing the list is waiting on (libQuery()), "" when none: while a
// press's read is out its list is its placeholder, drawn by the page's own
// render so the patcher's record is what is on screen.
let libWaitFor = "";
let libQ = "", libKind = "", libTier = "";
// The rest of what narrows it: a topic, the order, and whether what
// runs on other systems is shown too; all in the address, none saved.
let libTopic = "", libSort = "", libAll = false;
// Cards or rows, this browser's (the Spaces page's Full and Compact): a list
// on a phone opens in rows until somebody picks.
let libView = (() => { try{ return localStorage.getItem("bb.libview") || ""; }catch(e){ return ""; } })();
// How many a list asks for at a time.
const LIB_PAGE = 30;
// Whether the source chips drew the last time the page did: a library whose
// cards all come from one source draws none, and its waiting template then
// holds no row for them (it stood a row lower than the page it waited for
// once every catalog entry was Packaged by Aerie).
let libHadTiers = false;
const libSeen = {};            // what a pack's Look brought back, by row key ("looking" while it is asked)
let libWantAgent = "";         // the agent whose card a door asked to open, until the rows land
// The sections, in the page's order: what a session runs first, then what
// it builds with, then what a person adds, then what the box hosts, then
// what the person takes to their own machines.
const LIB_KINDS = [["agent", "Coding agents"], ["toolchain", "Toolchains"], ["pack", "Tool packs"], ["service", "Services"], ["app", "Apps"], ["companion", "For you"]];
// The chips after All that pick cards by where they stand rather than by
// kind, each across every kind's section (Installed,
// then Updates).
// An update is a newer version of what is installed, or a newer pin of a
// pack kept from the catalog. Both wear the accent and both count under
// Updates, and each says which it is: Software
// update puts a newer program on the node, Manifest update keeps the
// catalog's newer definition of a pack, and two presses reading Update for
// two different things were confusing.
const LIB_STANDS = {installed: r => r.installed, update: r => r.update || !!r.repin};
// The section a card sits in: its kind, or the group it names (a
// pack that brings a coding agent is a pack's card under Coding agents).
function libGroup(r){ return r.group || r.kind; }
// Who stands behind a card: what AerieOS ships or
// its maintainers wrote, a verified vendor's own pack, anybody's pack the
// maintainers reviewed, and what a person added themselves.
const LIB_TIERS = [["official", "Packaged by Aerie"], ["verified", "Verified"], ["vetted", "Vetted"], ["sideloaded", "Sideloaded"]];
function libTierWord(t){ return (LIB_TIERS.find(([k]) => k === t) || [t, t])[1]; }
// Every row the page holds now: a list's page so far, or the front page's
// shelves and what is on the node, and the entry page's own.
function libKnown(){
  return [...(lib?.rows || []), ...(lib?.here || []), ...(lib?.shelves || []).flatMap(s => s.rows || []), ...(entryLib?.rows || [])];
}
function libFind(f){ return libKnown().find(f) || null; }
// What the page asks for: the server narrows, counts and pages, so
// the page never holds the whole catalog.
function libQuery(offset = 0){
  const p = new URLSearchParams({node: libNode, view: "browse", limit: String(LIB_PAGE), offset: String(offset)});
  for (const [k, v] of [["q", libQ.trim()], ["kind", libKind], ["topic", libTopic], ["tier", libTier], ["sort", libSort]]) if (v) p.set(k, v);
  if (libAll) p.set("all", "1");
  return "/api/library?" + p;
}
// The narrowing as the address carries it (?kind=app&topic=media&q=...).
function libAddr(){
  const p = new URLSearchParams();
  for (const [k, v] of [["q", libQ.trim()], ["kind", libKind], ["topic", libTopic], ["tier", libTier], ["sort", libSort]]) if (v) p.set(k, v);
  if (libAll) p.set("all", "1");
  const s = p.toString();
  return s ? "?" + s : "";
}
// ...and read back from one, as the page opens on it.
function libFromAddr(query){
  const p = new URLSearchParams(query || "");
  libQ = p.get("q") || ""; libKind = p.get("kind") || ""; libTopic = p.get("topic") || "";
  libTier = p.get("tier") || ""; libSort = p.get("sort") || ""; libAll = p.get("all") === "1";
}

function openLibrary(){
  openTab({kind: "library", arg: "__library", label: "Library"});
}
// ...on a node somebody named (the bell's rows, a node's page): read for
// first when the page has not listed it yet.
function openLibraryOn(id, agent = ""){
  // A door that names a coding agent (a project's Sign in on NODE, the
  // bell's row) opens that agent's card on its sign-in once the rows land.
  if (agent) libWantAgent = agent;
  openKindOn("library", id);
}

// The node the page opens on: the one it showed last, else the first agent
// node, as the Toolchains page picked. The toolchain and pack verbs act on
// tcNode, so the pick is theirs too.
function libPick(){
  // ...and where this browser kept none, the one a node's toolchains were
  // last read for (tcPick's key).
  const live = liveAgents(), want = keptNode("library", {have: live});
  libNode = want;
  if (want && want !== tcNode){ tcNode = want; toolchains = null; tcDriverPick = ""; }
  return live.find(n => n.id === want) || null;
}

// One read at a time (reading), an ask about the same node within half a
// second of a read's start sharing it: the page's open, its node's census
// and the revisions poll each asked at once, and the page waited on three
// reads where one would do. A call later than that reads again, so nothing
// it was asked about is missed.
function loadLibrary(){
  return reading("library", async () => {
    if (nodesList === null || nodesStale) await nodesKnown();
    if (!libPick()){ lib = {nonode: true}; return; }
    // A reply is kept while it is still about the node on show.
    const node = libNode, asked = libQuery();
    let got;
    try{ got = await getJSON(asked); }
    catch(e){ if (libWaitFor === asked) libWaitFor = ""; throw e; }
    // An answer about another node, or to words since changed, is not drawn,
    // and what the page wants now is asked for: a read sent before the
    // address's narrowing was applied (a reload of a list) answered the
    // front page, and dropped with nothing asked after it, the list never
    // came.
    if (libNode !== node || libQuery() !== asked){ if (libNode) setTimeout(loadLibrary); return; }
    lib = got;
    if (libWaitFor === asked) libWaitFor = "";
    if (libWantAgent && !lib.error){
      const want = libWantAgent;
      libWantAgent = "";
      // An agent's card may be past the shelf's eight: asked for by kind.
      const found = libFind(x => x.kind === "agent" && x.agent === want)
        || ((await getJSON(`/api/library?node=${encodeURIComponent(node)}&view=browse&kind=agent&limit=60`)).rows || []).find(x => x.kind === "agent" && x.agent === want);
      // The agent's own entry page, once the card is drawn.
      if (found) setTimeout(() => openEntry(libNode, `agent:${found.name}`));
    }
    // What the store's own lines and tcAct read off this page's read.
    if (!lib.error) toolchainsSeen(lib);
  }, {join: 500, about: libQuery()});
}

// After a press: the list, and the entry's page where it is on show.
function libReload(){ return Promise.all([loadLibrary(), entryKey && typeof shown === "function" && shown("entry") ? loadEntry() : null]); }

// A list narrowed anew starts from its first page.
function libPagesFrom(){ if (typeof pageState === "object") delete pageState.liblist; }

// A list's next page, put under the rows it has: one already there (the
// list moved under it) is not drawn twice.
async function libMore(){
  if (!lib?.rows || lib.moreAsked) return;
  lib.moreAsked = true;
  const node = libNode, asked = libQuery(lib.rows.length), was = lib;
  try{
    const got = await getJSON(asked);
    if (lib !== was || libNode !== node || got.error) return;
    const have = new Set(lib.rows.map(r => `${r.kind}:${r.name}`));
    lib.rows = [...lib.rows, ...(got.rows || []).filter(r => !have.has(`${r.kind}:${r.name}`))];
    lib.total = got.total;
  } finally {
    if (lib === was) lib.moreAsked = false;
  }
  readMoved("library"); drawPanes();
}

// The pills a row wears: its tier (the three read on every row), what is
// installed, and what an update would move it to, which alone is news.
// Who a tool is by, in a sentence for its Details:
// its maker, or, where a pack carries several makers' tools and is
// AerieOS's own putting together, each tool with who it is by.
function makerLine(r){
  if (!r.maker) return "";
  const cs = (r.credits || []).filter(c => c.name);
  if (!cs.length) return `<span class="sub lcmaker">By ${esc(r.maker)}.</span>`;
  return `<span class="sub lcmaker">Put together by ${esc(r.maker)} from other people's work: ${cs.map(c => `${esc(c.name)}${c.maker ? ` (${esc(c.maker)})` : ""}`).join(", ")}.</span>`;
}

// A card's line under its name: who the tool is by, in the quiet voice at
// the left, then who stands behind the pack (the tier), its version and
// what is out. The maker is the tool's, the tier the pack's: Google's
// program, packaged by Aerie.
function libPills(r){
  const by = r.maker ? `<span class="lcby" title="who ${esc(r.label)} is by">${esc(r.maker)}</span>` : "";
  const tier = `${by}<span class="pill${r.tier === "vetted" || r.tier === "verified" ? " ok" : ""}">${esc(libTierWord(r.tier).toLowerCase())}</span>`;
  const pill = packVersionPill(r), ver = pill && ` ${pill}`;
  const dev = r.dev ? devMark() : "";
  return `${tier}${ver}${packOutPill(r)}${dev}`;
}

// Where the row stands on the node, in a few words at its right.
function libState(r){
  const w = packState;
  if (r.running) return w(`${packDoing(r)}<span class="dots"></span>`);
  // Pressed while another job ran: it goes when that one ends, and says
  // which job that is.
  if (r.queued) return w(esc(`queued behind ${tcBehind(lib?.job) || tcBehind(entryLib?.job) || tcBehind() || "the job running now"}`));
  // One this AerieOS is too old for: said plainly, in the muted voice, since
  // nothing is wrong with the card or the machine.
  if (r.too_new) return w(esc(r.too_new.charAt(0).toUpperCase() + r.too_new.slice(1).replace(/ \(.*$/, "")));
  // An app runs where Docker does: said when this node has none.
  if (r.kind === "app") return lib && !lib.docker ? w("this node runs no Docker: New container picks another", "warn") : w("");
  if (r.kind === "service") return r.installed ? w("deployed", "ok") : r.ready ? w(esc(r.ready), "warn") : w("");
  if (r.kind === "companion") return r.download ? w(esc(r.version ? `held, ${r.version}` : "held")) : w(esc(r.absent ? `not in ${r.absent}` : "not fetched yet"), "warn");
  if (r.wrong_platform) return w(esc(r.wrong_platform), "warn");
  if (r.machine){
    const m = r.machine;
    // A newer version of what is here is the news, whatever runs the card
    // now: the card is where it is installed from, so it says that first.
    if (m.managed && m.here && m.newer && m.state !== "nocard" && m.state !== "leaving") return w("software update available", "warn");
    return packMachineState(r);
  }
  // A pack kept here that does not fit this AerieOS is switched off until
  // one that does is kept: said in the warning
  // voice, since it was working before the update.
  if (r.pack?.disabled) return w(esc(r.pack.disabled) + (r.repin ? ": Manifest update keeps one that fits" : r.tier === "sideloaded" ? ": Edit keeps a version that names this one" : ""), "warn");
  // The catalog pins a newer commit of a pack kept from it: said as what
  // it is, the pack's manifest and not the program on the node.
  if (r.repin) return w("manifest update available", "warn");
  return packHeldState(r);
}

// The one verb a row takes, and Remove where it is installed (the
// Toolchains page's Remove and the Agents page's, moved here).
// Why the store's verbs are held on every card, or "": a node not reporting,
// a store it cannot write. A job running there holds nothing: a press queues
// behind it (toolchains.store_gate).
// Set by the draw; the notice over the cards says the last two in full.
let libHold = "";
function libActs(r, may){
  const n = libNode, a = (act, words, cls = "", held = "") =>
    `<button type="button"${cls ? ` class="${cls}"` : ""} data-libact="${act}" data-libkind="${esc(r.kind)}" data-libname="${esc(r.name)}"${
      held ? ` disabled title="${esc(held)}"` : ""}>${esc(words)}</button>`;
  if (r.running || r.queued) return "";
  // Written in a format this AerieOS has not met: nothing to press,
  // and the card's state says which AerieOS takes it.
  if (r.too_new) return "";
  if (r.kind === "companion") return r.download
    ? `<a class="btn primary" href="${esc(r.download.url)}" download title="${esc(r.download.file)} · sha256 ${esc((r.download.sha256 || "").slice(0, 12))}…">Download</a>`
    : `<button type="button" class="primary" disabled>Download</button>`;
  // An app is not installed on the node from here:
  // its press sends it to the Containers page's New container with the app
  // picked, and each press makes another container under its own name.
  if (r.kind === "app") return `${may.apps ? a("install", "New container", "primary") : ""}${r.tier === "sideloaded" && may.packs ? a("edit", "Edit") : ""}`;
  // A service deploys as a written container does (Configure on the node), once
  // something is behind it, set on the Installed page.
  if (r.kind === "service") return !may.configure || r.installed ? "" : `<button type="button" class="primary" data-libact="install" data-libkind="service" data-libname="${esc(r.name)}"${r.ready ? " disabled" : ""}${r.ready ? ` title="${esc(r.ready)}: set on the Installed page"` : ""}>Install</button>`;
  if (!may.install || !n) return "";
  // One for other systems, shown when somebody asked to see them:
  // its Install dead, the card's state saying why.
  if (r.wrong_platform && !r.installed) return a(r.kind === "pack" && r.catalog ? "add" : "install", "Install", "primary", r.wrong_platform);
  if (r.kind === "pack" && !r.installed && r.catalog) return a("add", "Install", "primary", libHold);
  if (r.machine && (!r.machine.managed || r.machine.imaged)) return "";
  // The container toolkit installed but unknown to Docker is put right by
  // installing it again, which its line on the Installed page says.
  const again = r.machine?.state === "unconfigured"
    // ...and a pack whose copy here an earlier manifest made.
    || !!(r.installed && r.receipt?.stale);
  // One switched off for not fitting this AerieOS is not installed anywhere
  // new: its way back is the catalog's newer pin, below.
  const verb = r.pack?.disabled ? "" : r.update ? a("install", "Software update", "primary", libHold) : again ? a("install", "Install again", "primary", libHold)
    : r.installed ? "" : a("install", "Install", "primary", libHold);
  // Edit on what a person added themselves, as on an app: a pack kept from
  // the catalog is not theirs to edit (no Edit on
  // Gemini's card), and its kept copy is reached from its Details page.
  const edit = r.kind === "pack" && r.pack && r.tier === "sideloaded" ? a("edit", "Edit") : "";
  // The catalog pins a newer commit of a pack kept from it:
  // Manifest update, in the accent as every update is and named apart from
  // a program's Software update, opens the dialog on that
  // pin, its changes marked, before anything is kept. It is the card's one
  // verb while it stands. A pack has no version of its own to compare, so
  // its card never carries a Software update: the manifest is what moves.
  // Keeping one changes what the controller and its sessions read at once
  // and reinstalls nothing: a node's copy made by the earlier manifest's
  // install steps stays, and its card then offers Install again.
  if (r.repin && may.packs) return `${a("repin", "Manifest update", "primary")}${edit}`;
  return `${verb}${edit}`;
}

// The whole description, on the open row (rows-you-open): what it fetches
// and runs, its terms, its platforms, the verbs it gives a session, an
// agent's sign-in on this node, a pack's source, a companion's other files.
// How a companion is connected once it is installed:
// the controller's address is the one thing each asks for,
// written where it is typed.
function devHow(name){
  const at = `<code>${esc(location.origin)}</code>`;
  return {
    android: `Install it, open it and sign in at ${at} with your name and password.`,
    vscode: `In VS Code: Extensions, the ⋯ menu, Install from VSIX; then AerieOS: Connect, at ${at}.`,
    companion: `Run it, sign in at ${at} with your name and password, and pick a space and a folder.`,
  }[name] || "";
}

function libDetail(r){
  // The entry's metadata alone (the Library is the
  // catalog; what is installed is managed on the Installed page under
  // Machines): what it is in full, its platforms, terms, size and source, a
  // pack's Look, an app's compose with its blanks, a companion's files.
  const key = `${r.kind}:${r.name}`;
  const lines = [];
  if (makerLine(r)) lines.push(makerLine(r));
  // Written for a later framework than this AerieOS reads: taken, with what
  // is newer left out, said so nobody wonders where a part of it is.
  if (r.ahead) lines.push(`<span class="sub warn">It is ${esc(r.ahead)}.</span>`);
  if (r.platforms?.length) lines.push(`<span class="sub">Platforms: ${esc(r.platforms.join(", "))}</span>`);
  if (r.kind === "toolchain" || r.kind === "pack"){
    if (r.tool) lines.push(`<span class="sub">Adds <code>aerie tool ${esc(r.tool)}</code> to a session.</span>`);
    if (r.needs?.length) lines.push(`<span class="sub">Needs ${esc(r.needs.join(", "))}, installed with it.</span>`);
    lines.push(tcTermsLine(r));
    if (tcHeldLine(r)) lines.push(tcHeldLine(r));
    if (r.size) lines.push(`<span class="sub">About ${esc(r.size)} on the store.</span>`);
    if (r.machine) lines.push(`<span class="sub">${r.name === TC_DRIVER ? "Built for the machine's kernel, installed as root, taking the card at the next restart." : "From NVIDIA's own package source, which installing adds and removing takes away."} Its state and Remove are on the Installed page.</span>`);
    if (r.pack) lines.push(`<span class="sub">${r.pack.here ? "Made here" : `From <code>${esc(r.pack.url)}</code>${r.pack.path ? ` (${esc(r.pack.path)})` : ""} at ${esc((r.pack.commit || "").slice(0, 12))}`}${r.pack.by ? `, added by ${esc(r.pack.by)}` : ""}. A session has <code>aerie tool ${esc(r.name)}</code>.${
      r.tier !== "sideloaded" && lib?.may?.install && !r.running ? ` <button type="button" class="link" data-libact="edit" data-libkind="pack" data-libname="${esc(r.name)}">Look for a newer pin, or remove it</button>` : ""}</span>`);
    if (r.catalog) lines.push(`<span class="sub">From <code>${esc(r.catalog.url)}</code>${r.catalog.path ? ` (${esc(r.catalog.path)})` : ""} at ${esc((r.catalog.commit || "").slice(0, 12))}, its archive's sha256 checked on the way in. Install opens the Add tool pack dialog on that commit, and Add keeps exactly that.</span>`);
    if (r.repin) lines.push(`<span class="sub warn">The vetted catalog pins a newer commit, ${esc(r.repin.commit.slice(0, 12))}: Manifest update shows what it changes before it is kept.</span>`);
    if (r.config?.length) lines.push(`<span class="sub">Asks for ${esc(r.config.map(f => f.label).join(", "))} on each node, set on the Installed page once it is there.</span>`);
    if (r.wrong_platform) lines.push(`<span class="sub warn">${esc(r.wrong_platform)}</span>`);
    if (r.pack?.disabled) lines.push(`<span class="sub warn">It is ${esc(r.pack.disabled)}. No session uses it, and it offers no agent, until a version that names this AerieOS is kept; where it is installed it stays.</span>`);
    if (r.too_new) lines.push(`<span class="sub">This one ${esc(r.too_new)}. Nothing is fetched or added until then.</span>`);
    if (r.pack && !r.pack.here || r.catalog){
      const seen = libSeen[key];
      lines.push(seen === "looking" ? `<span class="sub">Looking at the repository<span class="dots"></span></span>`
        : seen?.error ? `<span class="sub bad">${esc(seen.error)}</span>`
        : seen ? tpSeen(seen, null, false)
        : `<span class="sub"><button type="button" class="link" data-liblook="${esc(key)}">Look</button> at what it fetches and runs, before anything is installed.</span>`);
    }
  }
  if (r.kind === "service"){
    lines.push(`<span class="sub">Deployed on the node as a written container; configured, read and removed on the Installed page under Machines.</span>`);
    if (r.repin) lines.push(`<span class="sub warn">The vetted catalog pins a newer commit, ${esc(r.repin.commit.slice(0, 12))}: Manifest update shows what it changes before it is kept.</span>`);
    if (r.config?.length) lines.push(`<span class="sub">Asks for ${esc(r.config.map(f => f.label).join(", "))}.</span>`);
  }
  if (r.kind === "agent"){
    const a = agentById(r.agent);
    lines.push(`<span class="sub">${a?.product ? `${esc(a.product)}, installed` : "Installed"} once per node for its session account${a?.provider ? `; each person signs in with ${/^(?:[AEIOU]|x(?=[A-Z]))/.test(a.provider) ? "an" : "a"} ${esc(a.provider)} account on the Installed page` : ""}.${r.latest ? ` The latest is ${esc(r.latest)}.` : ""}</span>`);
  }
  if (r.kind === "app"){
    // Whether every image it runs is named by its digest (pack format 5),
    // in one line, as a toolchain's Details says of its downloads.
    if (r.held?.word) lines.push(`<span class="sub tcheld">${r.held.word === "pinned"
      ? "Every image it runs is named by its digest."
      : "Its images are named by tag alone: a tag is whatever was last pushed under it."}</span>`);
    if (r.tier === "sideloaded") lines.push(`<span class="sub">Added${r.by ? ` by ${esc(r.by)}` : ""}${r.at ? ` ${ago(r.at)}` : ""}, kept as sideloaded: Edit changes it, and Remove in there takes it off the catalog.</span>`);
    if (r.going) lines.push(`<span class="sub warn">${esc(r.going)}</span>`);
    lines.push(`<span class="sub">New container opens the Containers page's dialog on ${esc(r.label)}'s panel, and Create makes it a container there${
      r.network === "host" ? `, on the machine's own network, answering on ${esc(String(r.port))}` : r.port ? `, on port ${esc(String(r.port))} unless you pick another` : ""}. Each press makes another, under its own name.</span>`);
    // What its panel asks for: its own fields, then AerieOS's.
    const asks = [...(r.fields || []).map(f => f.kind === "secret" ? `${f.label} (made for it)` : f.label),
      ...(r.own || []).includes("PUID") ? ["who it runs as"] : [], ...(r.own || []).includes("TZ") ? ["the time zone"] : []];
    if (asks.length) lines.push(`<span class="sub">Asks for ${esc(asks.join(", "))}.</span>`);
    if (r.compose) lines.push(`<pre class="libcompose mono">${esc(r.compose.trim())}</pre>`);
  }
  if (r.kind === "companion"){
    lines.push(`<span class="sub">${devHow(r.name)}</span>`);
    if ((r.files || []).length > 1) lines.push(`<span class="sub">Also: ${r.files.slice(1).map(f => `<a href="${esc(f.url)}" download>${esc(f.file)}</a>`).join(", ")}</span>`);
  }
  return lines.filter(Boolean).join("");
}

// The glyph a card wears for its kind: the rail's and the tabs' own where
// one exists, a box with a tag for a pack and a screen for a companion.
const LIB_ICONS = {
  agent: () => TOOL_ICONS.agents, toolchain: () => TOOL_ICONS.toolchains, app: () => TOOL_ICONS.docker,
  pack: () => `<svg viewBox="0 0 16 16" aria-hidden="true"><path d="M2.5 5.2 8 2.6l5.5 2.6v5.6L8 13.4l-5.5-2.6z"/><path d="M2.5 5.2 8 7.8l5.5-2.6"/><path d="M8 7.8v5.6"/><path d="M5.2 3.9l5.6 2.7"/></svg>`,
  companion: () => `<svg viewBox="0 0 16 16" aria-hidden="true"><rect x="2.2" y="3" width="11.6" height="7.6" rx="1.2"/><path d="M6 13.4h4M8 10.6v2.8"/></svg>`,
  // A service: what a node runs for the others, as a box with a plug.
  service: () => `<svg viewBox="0 0 16 16" aria-hidden="true"><rect x="2.4" y="4.2" width="11.2" height="7.6" rx="1.2"/><path d="M5.2 8h5.6M5.2 4.2V2.6M10.8 4.2V2.6"/></svg>`,
};

// One card (the Projects page's shape: a store browses as cards):
// its kind's glyph, its name with the tier and the versions as quiet pills,
// what it is in two lines, and at its foot where it stands, Details, and
// the verb. Open, it runs the grid's width with the whole description.
// A pack's Look on its row: the manifest fetched at the commit it is pinned
// to (an added pack at its own, a catalog offer at the catalog's, its archive
// checked against the catalog's sha256), drawn as the dialog draws it.
async function libLook(key){
  const r = libFind(x => `${x.kind}:${x.name}` === key);
  if (!r || libSeen[key] === "looking") return;
  libSeen[key] = "looking"; readMoved("library"); drawPanes();
  const body = r.catalog ? {action: "preview", url: r.catalog.url, commit: r.catalog.commit, sha256: r.catalog.sha256, path: r.catalog.path || ""}
    : {action: "preview", url: r.pack.url, commit: r.pack.commit, path: r.pack.path || ""};
  const j = await postJSON("/api/toolpacks", body);
  libSeen[key] = j;
  readMoved("library"); drawPanes();
}

// The driver's version on its card (the branch
// is picked before Install), as the Toolchains page's row had it: the
// recommended one first, the rest by version, dead once one is installed.
function libDriverPick(m){
  const opts = m.options || [];
  if (!opts.length || m.state === "nocard" || !m.managed) return "";
  const picked = m.here ? m.package : (opts.some(o => o.pkg === tcDriverPick) ? tcDriverPick : "");
  return `<label class="pick libdrvpick">Version <select id="libDrvSel" aria-label="driver version"${m.here || !lib?.may?.install ? " disabled" : ""}${
      m.here ? ` title="installed: remove it first to install another version"` : ""}>
      ${m.here ? "" : `<option value=""${picked ? "" : " selected"}>${esc(m.recommended
          ? tcDriverOption(opts.find(o => o.pkg === m.recommended) || {pkg: m.recommended, version: "recommended"}, m)
          : "the one recommended for this card")}</option>`}
      ${opts.filter(o => m.here || o.pkg !== m.recommended).map(o => `<option value="${esc(o.pkg)}"${o.pkg === picked ? " selected" : ""}>${esc(tcDriverOption(o, m))}</option>`).join("")}
    </select></label>`;
}

// ...Details opening the entry's own page, never the card in place.
function libRow(r, may){
  const key = `${r.kind}:${r.name}`;
  const err = packJobErr(r, lib?.job);
  return `<div class="lcard${r.running ? " busy" : ""}" data-lrow="${esc(key)}">
    <div class="lchead">${libIcon(r)}
      <div class="lctitle"><div class="name"><span class="lcname">${esc(r.label)}</span> <button type="button" class="link lmore" data-libmore="${esc(key)}">Details</button></div><div class="lcmeta">${libPills(r)}</div></div></div>
    <div class="lcabout">${esc(r.about)}</div>
    ${r.machine && r.name === TC_DRIVER ? libDriverPick(r.machine) : ""}${err}
    <div class="pcacts actbar">${libState(r)}${libActs(r, may)}</div>
  </div>`;
}

// The band under the head: the search, then the kind chips and the tier
// chips side by side (the chips rule: one band where a list is narrowed
// more than one way).
// The search on a line of its own with the page's buttons at its right
// (under the head, where the bar left a gap), then
// the chips under it.
// The sources count within the kind picked (a kind
// picked says how many of it each source has); the kinds, the first row,
// count the whole library, so a source picked never empties that row.
function libFilterBand(acts = ""){
  const c = lib.counts || {kind: {}, tier: {}, topic: {}, all: 0};
  // Installed, then Updates, first after All, each
  // drawn while it has cards; the counts are the server's, under the other
  // narrowings.
  const kinds = [{key: "installed", label: "Installed", count: c.kind.installed || 0},
                 {key: "update", label: "Updates", count: c.kind.update || 0},
                 ...LIB_KINDS.map(([k, l]) => ({key: k, label: l, count: c.kind[k] || 0}))];
  // A source picked keeps its chip while it narrows to nothing, so it can
  // be let go; the chips draw only where two sources are present.
  const tiers = LIB_TIERS.map(([k, l]) => ({key: k, label: l, count: c.tier[k] || (k === libTier ? 0.5 : 0)}));
  const tierChips = tiers.filter(t => t.count).length > 1 || libTier ? chipButtons(tiers.map(t => ({...t, count: Math.floor(t.count)})).filter(t => t.count || t.key === libTier), libTier, "data-libtier", undefined, "Any source") : "";
  libHadTiers = !!tierChips;
  // A topic (the catalog's fixed list) and the order, each a pulldown
  // beside the search; a topic with nothing under the rest is left out.
  const topics = (lib.topics || []).filter(([k]) => c.topic[k] || k === libTopic);
  const topicSel = topics.length ? `<label class="pick libtopic"><select id="libTopic" aria-label="topic">
      <option value="">Any topic</option>${topics.map(([k, l]) => `<option value="${esc(k)}"${k === libTopic ? " selected" : ""}>${esc(l)}${c.topic[k] ? ` (${c.topic[k]})` : ""}</option>`).join("")}</select></label>` : "";
  const sortSel = `<label class="pick libsort"><select id="libSort" aria-label="order">${[["", libQ.trim() ? "Best match" : "By name"], ...(libQ.trim() ? [["name", "By name"]] : []), ["added", "Recently added"]]
      .map(([k, l]) => `<option value="${k}"${k === libSort ? " selected" : ""}>${l}</option>`).join("")}</select></label>`;
  const view = viewSeg("libview", libViewNow(), "each a card with what it is", "each a row, more to a screen", "", ["Cards", "Rows"]);
  return `<div class="field lfilter libfilter">
    <div class="libsearchrow"><input id="libFind" type="search" maxlength="80" autocomplete="off" spellcheck="false" aria-label="search the library"
      placeholder="search by name, maker or what it does" data-ph-short="search" value="${esc(libQ)}"><span class="libnarrow pickshare">${topicSel}${sortSel}${view}</span>${acts ? `<span class="actbar">${acts}</span>` : ""}</div>
    <div class="chips" data-chips="libkind">${chipButtons(kinds, libKind, "data-libkind", c.all)}</div>
    <div class="chips" data-chips="libtier">${tierChips}</div>
  </div>`;
}

// Cards or rows: the browser's pick, else rows for a list on a phone and
// cards everywhere else.
function libViewNow(){
  if (libView === "cards" || libView === "list") return libView;
  return innerWidth < 600 && libNarrowed() ? "list" : "cards";
}
function libNarrowed(){ return !!(libQ.trim() || libKind || libTopic || libTier); }

// What a group says over its cards: the catalog's trouble and the way to
// submit a pack, over the Tool packs (never in the node's head).
function libPackNote(may){
  const submit = lib.catalog_repo && may.packs
    ? `<div class="hint">Made a pack worth sharing? <a href="${esc(lib.catalog_repo)}" target="_blank" rel="noopener">Submit it to the vetted catalog ↗</a>: a pull request there, reviewed and signed by the maintainers.</div>` : "";
  const past = lib.catalog_past ? `<div class="hint warn">The catalog lists ${lib.catalog_past.toLocaleString()} more than this AerieOS reads; a newer AerieOS reads them all.</div>` : "";
  return (lib.catalog_error ? `<div class="hint warn">${esc(lib.catalog_error)}</div>` : "") + past + submit;
}

// A hosting-only node: its Library offers the
// services and apps it runs, and says once where the rest goes.
function libHostNote(){
  return lib.host_only ? `<div class="hint libhost">${esc(lib.name || "This node")} hosts containers only, so it is offered services and apps: toolchains, coding agents and tool packs go on the nodes where spaces build (<a href="#/machines/nodes">Nodes</a>).</div>` : "";
}

function libCards(rows, may){
  return `<div class="lgrid${libViewNow() === "list" ? " lrows" : ""}">${rows.map(r => libRow(r, may)).join("")}</div>`;
}

// The front page (shelves, never the whole
// catalog): what is on this node, then a shelf per kind of at most eight
// cards, Packaged by Aerie first, each with All N opening that kind's list.
function libShelves(may){
  const shelf = (key, title, total, rows, note = "") => `<div class="libgroup" data-libgroup="${esc(key)}">
    <h3 class="libgname">${esc(title)} <span class="dim">${esc(String(total))}</span>${
      total > rows.length ? `<button type="button" class="link libshelfall" data-libshelf="${esc(key)}">All ${esc(String(total))} ›</button>` : ""}</h3>${note}${libCards(rows, may)}</div>`;
  const here = lib.here || [];
  const mine = here.length ? shelf("installed", "On this node", here.length, here.slice(0, 8)) : "";
  const kinds = (lib.shelves || []).map(sh => {
    const title = (LIB_KINDS.find(([k]) => k === sh.kind) || [sh.kind, sh.kind])[1];
    if (sh.kind === "companion" && featureOff("apps")) return "";
    return shelf(sh.kind, title, sh.total, sh.rows, sh.kind === "pack" ? libPackNote(may) : "");
  }).join("");
  // No packs at all is no shelf, but what the
  // catalog has to say over them is still said.
  const packsSaid = !(lib.shelves || []).some(sh => sh.kind === "pack") && libPackNote(may)
    ? `<div class="libgroup" data-libgroup="pack"><h3 class="libgname">Tool packs</h3>${libPackNote(may)}</div>` : "";
  // No app at all is no shelf either (none is shipped), and an
  // install that read no catalog and keeps none says so in a line.
  const appsSaid = !(lib.shelves || []).some(sh => sh.kind === "app") && lib.apps_note
    ? `<div class="libgroup" data-libgroup="app"><h3 class="libgname">Apps</h3><div class="hint warn">${esc(lib.apps_note)}</div></div>` : "";
  return libHostNote() + (mine + kinds + packsSaid + appsSaid || `<div class="empty">Nothing here yet.</div>`);
}

// A card in the page's placeholder, as a card is laid out.
function libSkCard(){
  return `<div class="lcard skcard"><div class="lchead"><span class="lcicon"></span><div class="lctitle">${skv(7, "name")}${skv(4)}</div></div>${skRows(1)}</div>`;
}
// The list a narrowing is reading, as its placeholder: drawn on the press,
// under the chip already lit and its count turned to the ring, and replaced
// by the server's page when it lands.
function libListSkel(){
  return skTpl(`<div class="libgroup libone"><div class="lgrid">${Array.from({length: 6}, libSkCard).join("")}</div></div>`);
}

// A list (a chip, a topic or the search): one sorted list, a page at a time.
function libList(may){
  const rows = lib.rows || [];
  const kindWord = LIB_STANDS[libKind] ? (libKind === "update" ? "with an update" : "installed") : "";
  const noun = libKind && !LIB_STANDS[libKind] ? (LIB_KINDS.find(([k]) => k === libKind) || ["", "entries"])[1].toLowerCase() : "entries";
  const hidden = lib.hidden ? `<div class="hint libhidden">${lib.hidden} more ${lib.hidden === 1 ? "runs" : "run"} only on other systems than ${esc(lib.name || "this node")}'s. <button type="button" class="link" data-liball="1">Show ${lib.hidden === 1 ? "it" : "them"}</button></div>`
    : libAll ? `<div class="hint libhidden">Showing what runs on other systems too, each marked. <button type="button" class="link" data-liball="0">Hide them</button></div>` : "";
  const note = libKind === "pack" ? libPackNote(may) : libKind === "app" && lib.apps_note ? `<div class="hint warn">${esc(lib.apps_note)}</div>` : "";
  const body = rows.length ? libCards(rows, may)
    : `<div class="empty">${libQ.trim() ? `Nothing ${kindWord ? kindWord + " " : ""}matches ${esc(libQ.trim())}.` : "Nothing here matches."}</div>`;
  return `${libHostNote()}<div class="libgroup libone" data-libgroup="list">${note}${hidden}${body}</div>`;
}

function renderLibraryInto(i){
  const d = docSurface(i, "library");
  if (!d) return;
  if (lib === null){
    d.setBar("");
    const skcard = libSkCard;
    drawHTML(d.list, skTpl(pageHead({line: [{value: GHOST, label: "updates due"}]})
      + `<div class="field lfilter libfilter"><div class="libsearchrow"><input type="search" disabled placeholder="search by name, maker or what it does" data-ph-short="search"><span class="libnarrow pickshare"><label class="pick libsort"><select disabled aria-label="order"><option>By name</option></select></label>${viewSeg("libviewsk", libViewNow(), "", "", " disabled", ["Cards", "Rows"])}</span><span class="actbar"><button type="button" disabled>${barSaid("Check for updates", "Check")}</button><button type="button" class="primary" disabled>${barSaid("Add your own", "Add")}</button></span></div><div class="chips">${skel("chips", 5)}</div>${libHadTiers ? `<div class="chips">${skel("chips", 3)}</div>` : ""}</div>`
      + `<div class="field libgroups">${[["installed", "On this node"], ...LIB_KINDS].map(([k, title]) => `<div class="libgroup"><h3 class="libgname">${esc(title)}<button type="button" class="link libshelfall" disabled>All ›</button></h3><div class="lgrid">${skcard()}${skcard()}${skcard()}</div></div>`).join("")}</div>`));
    if (!readRev("library") && !readBusy("library")) loadLibrary();
    return;
  }
  if (lib.nonode){
    d.setBar("");
    drawHTML(d.list, noNodeYet("toolchains and coding agents install on a node", "libnone"));
    return;
  }
  const may = lib.may || {};
  const job = lib.job || {}, busy = !!job.running;
  // The node's whole record: whether its agent is behind and its store
  // read-only are read off it.
  const node = (nodesList || []).find(x => x.id === libNode) || {};
  const stale = nodeStale(node), pro = node.reported?.store_ro === true;
  const clean = may.install && !pro ? (lib.cleanable || []) : [];
  // The node is the Build group's header's, and the buttons sit on
  // the search's line under the head, so the bar carries nothing.
  d.setBar("");
  // No Abort beside them: a check is short, and a job
  // the page cannot stop here is the Jobs page's. While a check runs, Check
  // is dead and wears the ring in its word's place, its size kept; while
  // another job runs it is live, and its press queues behind that job.
  const checking = busy && job.action === "check";
  const acts = may.install
    ? `<button type="button" data-libcheck${stale && !checking ? " disabled" : ""}${runAttr(checking, "Checking for updates")} title="ask each upstream what it has now">${
         barSaid("Check for updates", "Check")}</button>${
        may.packs ? `<button type="button" class="primary" data-libadd>${barSaid("Add your own", "Add")}</button>` : ""}${
        clean.length ? `<button type="button" class="danger" data-libclean>Remove</button>` : ""}` : "";
  if (lib.error){
    patch(d.list, readFailed("could not read the library: " + lib.error));
    wireReadAgain(d.list, () => loadLibrary());
    return;
  }
  // What the head says is about the whole Library on the node, whatever is
  // narrowed: the server counts it. A card not for this node is left
  // out of a list and counted, and an entry this AerieOS does
  // not take is never shown.
  const f = lib.facts || {};
  // The last update installed takes the Updates chip with it, the last
  // thing removed the Installed chip: back to All.
  if (LIB_STANDS[libKind] && !(lib.counts?.kind?.[libKind]) && !(lib.rows || []).length && !libQ.trim()){ libKind = ""; setTimeout(loadLibrary); }
  const inst = f.installed || 0, due = f.updates || 0;
  // One line of what is news: updates due, and how fresh that is;
  // what is installed is the Installed chip's count, said once.
  const head = pageHead({line: [
    due ? {value: due, label: due === 1 ? "update due" : "updates due", tone: "warn"} : {text: `${inst} of ${f.offered || 0} installed, all up to date`},
    lib.store?.checked ? {text: `versions checked ${ago(lib.store.checked)}`} : null,
  ]});
  // What the Toolchains page said over its rows (step 5): a node that has
  // not reported, a store it cannot write, and the system packages its
  // held recipes lack, with the one press that installs them.
  const unmet = Object.entries(lib.sysdeps?.unmet || {});
  const notes = `${stale ? `<div class="field"><div class="notice warn libstale">${esc(staleWhy(node))}. Nothing installs here until it is.</div></div>` : ""}${
    pro ? `<div class="field"><div class="notice warn libro">${esc(lib.name || "This node")}'s toolchain store is read-only to it, so nothing installs here: what is in it is what it has. Make it writable on the machine to install.</div></div>` : ""}${
    unmet.length ? `<div class="field"><div class="notice warn libsys">System packages ${esc(lib.name || "this node")} lacks for what its store holds (${esc(lib.sysdeps.family || "")}): ${
      unmet.map(([r, ps]) => `${esc(r)}: ${esc(ps.join(" "))}`).join("; ")}. ${lib.sandbox && may.install
        ? `<button type="button" data-libsysdeps${stale ? " disabled" : ""} title="install these on ${esc(lib.name || "the node")} without reinstalling the toolchains">Install system packages</button>`
        : "This node's owner installs them: the agent does not administer the machine."}</div></div>` : ""}`;
  libHold = stale ? "this node is not reporting" : pro ? "this node's store is read-only to it" : "";
  // Patched into what is there: the search being typed in keeps its
  // focus and its caret through the redraw its own key brings. A narrowing
  // whose read is out is its placeholder.
  const waiting = !!libWaitFor && libWaitFor === libQuery();
  // ...each card that the redraw puts elsewhere (an update done sorts it
  // anew, one installed joins On this node) sliding there (reflow), named
  // by its shelf and its entry, since one entry stands on two shelves.
  reflow(d.list, ".lcard[data-lrow]", e => `${e.closest("[data-libgroup]")?.dataset.libgroup || ""}:${e.dataset.lrow}`,
    () => patch(d.list, `<div data-libnode="${esc(libNode)}">${notes}${head}${libFilterBand(acts)}<div class="field libgroups">${
      waiting ? libListSkel() : libNarrowed() || !lib.shelves ? libList(may) : libShelves(may)}</div></div>`));
  // A list a page at a time (the long-lists rule): its foot says how much
  // of how many, and the next page comes as the foot scrolls into view. The
  // placeholder a narrowing draws on its press has no foot: the total is
  // still the list's before, and "6 of 61 coding agents" stood under six
  // placeholder cards, then inside the first card that took its place.
  const one = d.list.querySelector(".libone .lgrid");
  if (one) paginate(one, ":scope > .lcard", {key: "liblist", total: waiting ? 0 : lib.total || 0, more: libMore,
    noun: libKind && !LIB_STANDS[libKind] ? (LIB_KINDS.find(([k]) => k === libKind) || ["", "entries"])[1].toLowerCase() : "entries"});
  // The ellipsis on a card whose job runs is ticked by the one timer every
  // page shares (tcTickDots), so a redraw does not restart it.
  if (!tcDotsTimer && d.list.querySelector(".dots")) tcDotsTimer = setInterval(tcTickDots, 400);
  // The order's answers change with the search (Best match comes and goes):
  // each pulldown is held to its longest answer again.
  fitPickersSoon();
  wireLibrary(d.el);
}

// A card's glyph, or the pack's or app's own icon in its square, drawn
// as an image alone; one that does not load shows the kind's glyph instead.
function libIcon(r){
  const glyph = (LIB_ICONS[libGroup(r)] || LIB_ICONS.toolchain)();
  return r.icon && /^\/api\/pack-icon\?/.test(r.icon)
    ? `<span class="lcicon own"><img src="${esc(r.icon)}" alt="" loading="lazy" decoding="async" width="36" height="36">${glyph}</span>`
    : `<span class="lcicon">${glyph}</span>`;
}

function wireLibrary(root){
  root.querySelectorAll(".lcicon.own img").forEach(i => {
    const broke = () => i.parentElement.classList.add("broken");
    if (i.complete && !i.naturalWidth) broke(); else i.onerror = broke;
  });
  wireSections(root);
  wireSignin(root);
  // Each narrowing asks the server again, the address following it,
  // and a list starts from its first page.
  // The list under it becomes its placeholder on the press, and the read is
  // the press's own, so a chip's count is the ring until it lands.
  // Drawn by the page's render, never written in under it: a placeholder put
  // straight into the list was taken by the patcher for its last draw, and a
  // search cleared while the read for its words was out left that list on
  // the screen.
  const ask = set => {
    set(); if (lib) lib.moreAsked = false; libPagesFrom(); shellSync();
    libWaitFor = libQuery();
    readMoved("library"); drawPanes();
    return loadLibrary();
  };
  const q = root.querySelector("#libFind");
  if (q){
    onTyping(q, () => { if (q.value === libQ) return; ask(() => { libQ = q.value; if (!libQ.trim() && libSort === "") libSort = ""; }); });
  }
  root.querySelectorAll("[data-libkind]").forEach(b => b.onclick = () => ask(() => { libKind = b.dataset.libkind; }));
  root.querySelectorAll("[data-libtier]").forEach(b => b.onclick = () => ask(() => { libTier = b.dataset.libtier; }));
  root.querySelectorAll("[data-libshelf]").forEach(b => b.onclick = () => ask(() => { libKind = b.dataset.libshelf; }));
  root.querySelectorAll("[data-liball]").forEach(b => b.onclick = () => ask(() => { libAll = b.dataset.liball === "1"; }));
  const tsel = root.querySelector("#libTopic");
  if (tsel) tsel.onchange = () => ask(() => { libTopic = tsel.value; });
  const ssel = root.querySelector("#libSort");
  if (ssel) ssel.onchange = () => ask(() => { libSort = ssel.value; });
  root.querySelectorAll("[data-libview]").forEach(b => b.onclick = () => {
    libView = b.dataset.libview;
    try{ localStorage.setItem("bb.libview", libView); }catch(e){ /* private */ }
    // Each entry's box moving and tweening to its new size as its drawing
    // fades through (the boxes popped to their size).
    morphThrough(".pane .doc.on .librarytab .lcard[data-lrow]", () => { readMoved("library"); drawPanes(); }, e => e.dataset.lrow);
  });
  root.querySelectorAll("[data-libmore]").forEach(b => b.onclick = () => openEntry(libNode, b.dataset.libmore));
  const chk = root.querySelector("[data-libcheck]");
  // ...and the vetted catalog read again with it: its index is kept for an
  // hour, so a newer pin showed up to an hour after Check.
  if (chk) chk.onclick = () => pressing(chk, async () => { busy(chk, "Checking"); await tcOn(libNode);
    await Promise.all([tcAct("check"), fetch("/api/catalog?fresh=1").catch(() => null)]); await loadLibrary(); });
  const sd = root.querySelector("[data-libsysdeps]");
  // ...its word Queuing while a job runs, which it waits behind (tcAct says
  // which).
  if (sd) sd.onclick = () => pressing(sd, async () => { await tcOn(libNode); busy(sd, tcBehind() ? "Queuing" : "Installing"); await tcAct("sysdeps"); await loadLibrary(); });
  const cl = root.querySelector("[data-libclean]");
  if (cl) cl.onclick = async () => {
    // What each one was, said here, where the head said it as a fact.
    const dirs = (lib?.cleanable || []).map(c => c.dir), named = (lib?.cleanable || []).map(c => c.what ? `${c.dir} (${c.what})` : c.dir);
    if (!dirs.length || !await askYes(`Take ${named.join(", ")} off the store?\n\nNo node runs from ${dirs.length === 1 ? "it" : "them"}; what is in ${dirs.length === 1 ? "it" : "them"} is gone for good.`, {verb: "Remove", danger: true})) return;
    // While a job writes the store it waits behind it, and says so.
    const ahead = tcBehind();
    busy(cl, ahead ? "Queuing" : "Removing");
    const j = await postJSON("/api/toolchains", {action: "clean", node: libNode, names: dirs});
    if (j.error) notify(j.error, true);
    else if (ahead || j.waits) notify(queuedSaid(`taking ${dirs.join(", ")} off the store`, ahead || "the job writing it"));
    loadLibrary();
  };
  const dsel = root.querySelector("#libDrvSel");
  if (dsel) dsel.onchange = () => { tcDriverPick = dsel.value; };
  const add = root.querySelector("[data-libadd]");
  if (add) add.onclick = () => libWithToolchains(() => tpOpen(""));
  root.querySelectorAll("[data-libact]").forEach(b => b.onclick = () => libAct(b, b.dataset.libact, b.dataset.libkind, b.dataset.libname));
  root.querySelectorAll("[data-liblook]").forEach(b => b.onclick = () => libLook(b.dataset.liblook));
}

// The pack dialogs read the store's rows (tpOpen's Edit finds the pack
// there), so they are read for this node first where they are not yet.
async function libWithToolchains(f){
  await toolchainsFor(libNode);
  f();
}

async function libAct(b, act, kind, name){
  const r = libFind(x => x.kind === kind && x.name === name);
  if (!r) return;
  if (kind === "app"){
    if (act === "edit"){ tpOpenApp(name); return; }
    // One the vetted catalog offers is kept first, from its pin in the
    // signed index; then New container, on this node when it
    // runs Docker.
    if (r.catalog){
      busy(b, "Taking");
      const j = await postJSON("/api/nasapps", {action: "add-catalog", app: name});
      if (j.error){ notify(j.error, true); await libReload(); return; }
      if (typeof cApps !== "undefined") cApps = null;
      await libReload();
    }
    openNewContainerApp(name, lib?.docker ? libNode : "");
    return;
  }
  if (kind === "service"){ await packDeploy(b, libNode, r, "install", libReload); return; }
  if (kind === "agent"){ await agentUpdate(b, libNode, r, libReload); return; }
  // Add, Edit and Update a pin open the pack's dialog once the store's rows
  // are read, which is a round trip where they are not held: awaited, so
  // the press wears its ring until the dialog is up (pressHold).
  if (act === "add"){ await libWithToolchains(() => tpOpenCatalog({...r.catalog, name: r.name, tier: r.tier, about: r.about, platforms: r.platforms})); return; }
  if (act === "edit"){ await libWithToolchains(() => tpOpen(r.name)); return; }
  if (act === "repin"){ await libWithToolchains(() => tpOpen(r.name, r.repin)); return; }
  // Install or update a toolchain or an added pack: the Toolchains job,
  // with its agreements asked the way that page asks them. While another
  // job runs on the node it is queued behind it, never refused:
  // the card says so once its questions are answered,
  // behind what, and its toast says it too (tcAct).
  await tcOn(libNode);
  if (tcBehind()){
    await tcAct("install", [r.name], {now: () => libQueuedNow(kind, name)});
  } else {
    busy(b, r.installed ? "Updating" : "Installing");
    await tcAct("install", [r.name]);
  }
  await libReload();
}

// A card pressed while a job runs, drawn queued behind it at once, every
// copy of it the page holds (a shelf, the list, its entry page); what this
// gives back takes the mark off again, for a press refused or not sent.
// The read after the answer says the same from the server's queue.
function libQueuedNow(kind, name){
  const rows = libKnown().filter(x => x.kind === kind && x.name === name && !x.queued && !x.running);
  rows.forEach(x => { x.queued = true; });
  readMoved("library"); drawPanes();
  return () => { rows.forEach(x => { x.queued = false; }); readMoved("library"); drawPanes(); };
}
