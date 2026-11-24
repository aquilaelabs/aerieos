// The shell (R218 step 2): a rail of groups down the left edge, each one a
// page with an address, the page on show in the pane; the tool tabs that
// filled the strip are these pages now, and the strip keeps the documents
// (terminals, notebooks, the profile is a page under Settings). On a phone
// the rail is a bar of five across the bottom, with More for the rest.
// The top bar carries a search that jumps to a page, a project, a container
// or a node.
//
// One classic script beside index.html (docs/design-language.md, Files):
// pure declarations, nothing runs at load. What runs at load is
// page-boot.js's, under the section's header.

"use strict";

// ---- the rail ----------------------------------------------------------------

// One stroke voice with TOOL_ICONS (page-tabs.js), 16px, for the groups
// that have no tool icon of their own.
const RAIL_ICONS = {
  home: `<svg viewBox="0 0 16 16" aria-hidden="true"><path d="M2.5 8.2 8 3.2l5.5 5"/><path d="M4 7v6h8V7"/><path d="M6.6 13V9.6h2.8V13"/></svg>`,
  projects: `<svg viewBox="0 0 16 16" aria-hidden="true"><path d="M2.5 4.5h4l1.2 1.4h5.8v7.1H2.5z"/><path d="M2.5 7.4h11"/></svg>`,
  sessions: `<svg viewBox="0 0 16 16" aria-hidden="true"><rect x="2.4" y="3" width="11.2" height="8.6" rx="1.2"/><path d="M4.6 6.2l1.8 1.4-1.8 1.4"/><path d="M7.6 9h3"/><path d="M5.5 13.5h5"/></svg>`,
  people: `<svg viewBox="0 0 16 16" aria-hidden="true"><circle cx="6.2" cy="5.6" r="2.3"/><path d="M2.4 13c.3-2.6 1.9-4 3.8-4s3.5 1.4 3.8 4"/><circle cx="11.2" cy="6.2" r="1.8"/><path d="M10.4 9.6c1.9 0 3 1.3 3.2 3.4"/></svg>`,
  settings: `<svg viewBox="0 0 16 16" aria-hidden="true"><path d="M6.6 1.9h2.8l.35 1.72 1.2.7 1.66-.57 1.4 2.42-1.3 1.16v1.4l1.3 1.16-1.4 2.42-1.66-.57-1.2.7-.35 1.72H6.6l-.35-1.72-1.2-.7-1.66.57-1.4-2.42 1.3-1.16v-1.4L1.99 6.17l1.4-2.42 1.66.57 1.2-.7z"/><circle cx="8" cy="8" r="2.1"/></svg>`,
  more: `<svg viewBox="0 0 16 16" aria-hidden="true"><circle cx="3.5" cy="8" r="1.3"/><circle cx="8" cy="8" r="1.3"/><circle cx="12.5" cy="8" r="1.3"/></svg>`,
  // A server: two units in a rack, each with its light.
  controller: `<svg viewBox="0 0 16 16" aria-hidden="true"><rect x="2.5" y="2.8" width="11" height="4.4" rx="1"/><rect x="2.5" y="8.8" width="11" height="4.4" rx="1"/><circle cx="5" cy="5" r=".6"/><circle cx="5" cy="11" r=".6"/><path d="M8 5h3.5M8 11h3.5"/></svg>`,
  help: `<svg viewBox="0 0 16 16" aria-hidden="true"><circle cx="8" cy="8" r="5.8"/><path d="M6.3 6.4a1.75 1.75 0 1 1 2.5 1.6c-.55.27-.8.66-.8 1.2v.3"/><path d="M8 11.3v.1"/></svg>`,
};

// The eleven groups, in the rail's order (the design's rail rule); Help, the
// docs, last (R258).
const RAIL_GROUPS = [
  {key: "home", label: "Home", icon: "home"},
  {key: "projects", label: "Spaces", icon: "projects"},
  {key: "build", label: "Build", icon: "toolchains"},
  {key: "containers", label: "Containers", icon: "docker"},
  // The controller, a group of its own (the operator, 22 Oct): how this
  // AerieOS behaves, with room for the pages a bare-metal install and
  // the USB edition add beside Settings (R90, R56). After Containers, so a
  // phone's bar keeps its four.
  {key: "controller", label: "Controller", icon: "controller"},
  {key: "machines", label: "Machines", icon: "nodes"},
  {key: "sessions", label: "Sessions", icon: "sessions"},
  {key: "jobs", label: "Jobs", icon: "jobs"},
  {key: "people", label: "People", icon: "people"},
  {key: "settings", label: "Settings", icon: "settings"},
  {key: "help", label: "Help", icon: "help"},
];

// Every page kind, one record each: the one place a page's facts are
// written, and the tables under it are read off it, so a new page is one
// record here. A group's pages are its records in the order they stand in,
// the first the one its button opens. What a record says:
//   group, label   the group it is a page of, and its name on the sub-nav
//   open           what opens it from the rail, the sub-nav and its address;
//                  a page with a key of its own in its address (an installed
//                  thing, a Library entry) has none, the address opening it
//   may            whether the areas this account's grants read draw it
//                  (state.areas, "" for no Read; R152 step 3); without one
//                  everybody is drawn it. Asked only once the areas are
//                  known, unless the record says early
//   node, setNode  the last part of its address, read and set: the node it
//                  is on (R256 step 3). A page that keeps what it read for
//                  one node forgets it when the node changes, or the other
//                  node's list showed under this one until the read
//   keep           the key this browser keeps that node under
//   kept           what else a pick in the group's header keeps
//   load           what the page on show reads again after a pick; a page
//                  without one redraws from what setNode left it
//   moved          the read whose revision a pick moves (readMoved)
//   back           it is opened by a press, off its group's sub-nav (R181),
//                  and this is the page Back goes to when it was opened by
//                  its address alone
//   own: false     not built for the controller's own machine, whose docker
//                  is root over the controller (nodes.own_machine)
//   off            why its feature is not on a node (the node, its id), or ""
const PAGE_KINDS = {
  home: {group: "home", label: "Home", open: () => openHome()},

  projects: {group: "projects", label: "Spaces", open: () => openProjectsTab()},
  findings: {group: "projects", label: "Analysis", open: () => openFindingsTab()},

  // The Library (R170): the toolchains and the coding agents as one, so
  // either area draws it; what each row offers is the server's to gate.
  // Every door to the Toolchains, Agents and Apps pages it replaced lands
  // here, and their addresses open the group.
  library: {group: "build", label: "Library", open: () => openLibrary(),
    may: a => !!a.install || !!a.curate || !!a.nodes,
    node: () => libNode, setNode: v => { if (v !== libNode){ libNode = v; lib = null; } },
    keep: "bb.libnode", load: () => loadLibrary(), moved: "library"},
  // The Emulator's images are the toolchain store's, so the same area.
  emulator: {group: "build", label: "Emulator", open: () => openEmulator(),
    may: a => !!a.install,
    node: () => emuNode, setNode: v => { if (v !== emuNode){ emuNode = v; emu = null; emuTicked.clear(); } },
    keep: "bb.emunode", load: () => loadEmulator(), moved: "emulator",
    off: n => {
      const tc = n.reported?.toolchains || {};
      return Object.keys(tc).length && !tc.emulator && !tc["android-sdk"] ? "no Android tools on this node: install them from the Library" : "";
    }},
  phone: {group: "build", label: "Phone", open: () => openPhoneTab(),
    node: () => phNode, setNode: v => { if (v !== phNode){ phNode = v; phIp = ""; } },
    load: () => phFetch(null, true),
    off: (n, nid) => {
      const ns = typeof ph !== "undefined" && ph?.nodes;
      return Array.isArray(ns) && ns.length && !ns.some(x => x.id === nid) ? "no adb on this node: install Android platform tools from the Library" : "";
    }},
  // CI runner is offered by grant too (R137 step 3). Its page is drawn from
  // the nodes' read.
  runner: {group: "build", label: "CI runner", open: () => openRunnerTab(),
    // ...drawn for CI runner Read, which reads the runners it may (R277).
    may: a => state?.can?.["runner-read"] !== false && a.runner !== "",
    node: () => runnerNode, setNode: v => { runnerNode = v; }, moved: "nodes",
    off: n => {
      const has = (n.reported?.services?.runners || []).length || Object.keys(n.services?.runners || {}).length;
      return has ? "" : "no CI runner on this node yet: Add runner is on its page";
    }},
  // A Library entry's own page (R183), the Library's areas.
  entry: {group: "build", label: "Library", may: a => PAGE_KINDS.library.may(a), back: "library"},

  // The Containers page's node is its tab's own argument too, kept with
  // the layout.
  docker: {group: "containers", label: "Containers", open: () => openDocker(),
    node: () => dockerNode, setNode: v => { if (v !== dockerNode){ dockerNode = v; dockerList = dockerSeen[v] || null; } },
    kept: () => dockerNodeKeep(), load: () => loadDocker(), moved: "docker",
    off: (n, nid) => {
      const ns = typeof dockerList !== "undefined" && dockerList?.nodes;
      return Array.isArray(ns) && ns.length && !ns.some(x => x.id === nid) ? "this node does not run Docker" : "";
    }},
  vms: {group: "containers", label: "VMs", open: () => openVmsTab()},

  // This machine (R90 step 8): a bare-metal install's own, drawn only
  // where the install has one; the container edition shows Settings first.
  machine: {group: "controller", label: "This controller", open: () => openMachineTab(), may: a => !!a.controller && !!state?.own_node},
  settings: {group: "controller", label: "Settings", open: () => openSettingsTab(), may: a => !!a.controller},
  network: {group: "controller", label: "Network", open: () => openNetworkTab(), may: a => !!a.controller},
  keys: {group: "controller", label: "Keys", open: () => openKeysTab(), may: a => !!a.controller},
  audit: {group: "controller", label: "Audit", open: () => openAuditTab(), may: a => !!a.controller},
  // The Debug page (R147) only where DEBUG_MODE=1 started the controller,
  // and for an account with the debug grant, whatever its areas say.
  debug: {group: "controller", label: "Debug", open: () => openDebugTab(), early: true,
    may: () => !!state?.settings?.debug_available && state?.can?.debug !== false},

  nodes: {group: "machines", label: "Nodes", open: () => openNodesTab(), may: a => !!a.nodes,
    node: () => nodesPick, setNode: v => { nodesPick = v; }, moved: "nodes"},
  // Storage has an area of its own (R169).
  storage: {group: "machines", label: "Storage", open: () => openStorageTab(), may: a => !!a.storage,
    node: () => storageNode, setNode: v => { storageNode = v; }, keep: "bb.stnode", moved: "storage"},
  // What is installed on a node (R172): the same areas as the Library.
  installed: {group: "machines", label: "Installed", open: () => openInstalledTab(),
    may: a => !!a.install || !!a.configure || !!a.nodes,
    node: () => instNode, setNode: v => { if (v !== instNode){ instNode = v; inst = null; } },
    keep: "bb.instnode", load: () => loadInstalled(), moved: "installed"},
  // An installed thing's own page (R181 step 2), Installed's areas.
  thing: {group: "machines", label: "Installed", may: a => PAGE_KINDS.installed.may(a), back: "installed"},
  // nginx and the Scanners are services a node has installed (R264, the
  // operator, 19 Nov): their pages are opened from their rows on Installed,
  // and from Configure on their containers, kept off the sub-nav. Their
  // addresses from when they were the Containers group's still open
  // (openRoute: a page that moved group keeps its old address), and an
  // address with no opener lands on its group's first page (B410), so each
  // has one. Theirs is the Nodes page's area (R171).
  nginx: {group: "machines", label: "nginx", open: () => openNginxTab(), may: a => !!a.nodes,
    node: () => nginxNode, setNode: v => { nginxNode = v; }, keep: "bb.ngnode", moved: "nginx",
    back: "installed", own: false,
    off: (n, nid) => {
      const row = (typeof nginxList !== "undefined" && nginxList || []).find(x => x.node === nid);
      return row && !row.deployed ? "nginx is not deployed on this node: Deploy is on its page" : "";
    }},
  scanners: {group: "machines", label: "Scanners", open: () => openScannersTab(), may: a => !!a.nodes, back: "installed", own: false},
  // A machine's files (R224): an administrator's alone.
  files: {group: "machines", label: "Files", open: () => openFilesTab(), may: () => !!state?.admin,
    node: () => flNode, setNode: v => { if (v !== flNode){ flNode = v; fl = null; flRoot = ""; flPath = ""; flSel.clear(); } },
    keep: "bb.filenode", load: () => loadFiles()},

  sessions: {group: "sessions", label: "Sessions", open: () => openSessionsTab()},

  // The Jobs page has no node; the last part of its address is the chip it
  // is narrowed to (#/jobs/failed-today, which Home's "failed today" opens,
  // B74).
  jobs: {group: "jobs", label: "Jobs", open: () => openJobsTab(), may: a => !!a.jobs,
    node: () => jobsShow, setNode: v => jobsShowSet(v)},
  // An administrator's own cron (R117), its own area.
  schedules: {group: "jobs", label: "Schedules", open: () => openSchedulesTab(), may: a => !!a.schedules},

  users: {group: "people", label: "Users", open: () => openUsersTab(), may: a => !!a.accounts},
  roles: {group: "people", label: "Roles", open: () => openRolesTab(), may: a => !!a.accounts},

  profile: {group: "settings", label: "Profile", open: () => openProfileTab()},

  help: {group: "help", label: "Help", open: () => openHelp()},
};
// One fact of every kind that states it, by kind.
const kindFacts = fact => Object.fromEntries(Object.entries(PAGE_KINDS).filter(([, k]) => k[fact] !== undefined).map(([kind, k]) => [kind, k[fact]]));

// The rail: each group with its tools, the tab kinds it holds as [kind,
// label], the first the one its button opens; a group with several draws
// them as the page's sub-nav.
const RAIL = RAIL_GROUPS.map(g => ({...g, tools: Object.entries(PAGE_KINDS).filter(([, k]) => k.group === g.key).map(([kind, k]) => [kind, k.label])}));
// Where Back on a page a press opened goes when it was opened by its address
// alone: the page its press is on, which need not be its group's first.
const PRESSED_HOME = kindFacts("back");
// The pages a press opens rather than a tab (R181): off their group's
// sub-nav, each wearing a small top header with Back to the page it was
// opened from.
const PRESSED = new Set(Object.keys(PRESSED_HOME));
// What opens each page (railGo, openRoute).
const OPENERS = kindFacts("open");
// A node page's picked node, read and set by the address (R256 step 3): the
// node is the address's last part, so a reload, a link and Back land on it.
const NODE_PICKED = kindFacts("node"), NODE_SET = kindFacts("setNode");
// What a page keeps in this browser about its node, written on a pick.
const GROUP_KEEP = kindFacts("keep");
// What the page on show reads again after a pick; the rest redraw from
// what NODE_SET left them.
const GROUP_LOAD = kindFacts("load");
// The controller's own machine is a node like any (the operator, 9 Nov), on
// every page about a node but those not built for it.
const NOT_ON_OWN = new Set(Object.keys(PAGE_KINDS).filter(kind => PAGE_KINDS[kind].own === false));

// The five on a phone's bar: the rail's first four, so a phone and a desk
// keep one order (the operator, 19 Oct), and More for the rest in it.
const RAIL_PHONE = RAIL.slice(0, 4).map(g => g.key);

// A tool kind is a page: it leaves the strip and lives on the rail.
function isToolKind(kind){ return kind !== "term" && kind !== "notebook"; }

// The group a tab kind is a page of: the first group that lists it.
function groupOf(kind){
  return RAIL.find(g => (g.tools || []).some(([k]) => k === kind));
}

// Which tool kinds this account may open, from the areas its grants read
// (each record's may): a rail item for something a grant forbids is not
// drawn. Before the first poll everything is drawn, as the page always was,
// but a page whose answer no area gives.
function railAllows(kind){
  const k = PAGE_KINDS[kind], a = state?.areas;
  if (!k?.may || (!a && !k.early)) return true;
  return k.may(a);
}
function railGroups(){
  return RAIL.filter(g => (g.tools || []).some(([k]) => railAllows(k)));
}
// The page a group opens on: the one asked for when this account may open
// it, else the group's first that it may.
function railTool(g, want){
  const ok = (g.tools || []).filter(([k]) => railAllows(k)).map(([k]) => k);
  return want && ok.includes(want) ? want : ok[0] || "";
}

// What the rail lights: the group somebody pressed, while its page is the
// one on show; else the group of the page on show.
let railWant = "";
function railOn(){
  const t = tabOf(panes[0]);
  const kind = t?.kind || "";
  if (railWant){
    const g = RAIL.find(x => x.key === railWant);
    if (g && (g.tools || []).some(([k]) => k === kind)) return railWant;
    railWant = "";
  }
  // The pages the Library replaced (R170) are off the rail but keep their
  // addresses under Build until step 5 retires them.
  return groupOf(kind)?.key || (kind === "notebook" ? "projects" : "");
}

function railWarm(key){
  if (key === "containers") dockerWarm();
  else if (key === "build" && !lib) loadLibrary();
}

// Open a group: its first tool as a page. A press is a navigation, so the
// address is pushed.
function railGo(key, tool){
  const g = RAIL.find(x => x.key === key);
  if (!g) return;
  railWant = key;
  const kind = railTool(g, tool);
  if (!kind) return;
  // A page opened anew opens on its first section on a phone.
  sectNewVisit();
  const was = location.hash;
  OPENERS[kind]?.();
  const to = routeOf(tabOf(panes[0]));
  if (to && to !== was) shellPush(to, was);
}

// A history entry the page made itself, and shellSync told so: it leaves an
// address alone that differs from the one it last saw (a hand-typed one,
// B303), and an entry pushed here without saying so read as one, so the
// next page opened left the old page's address under it and Back went
// there (B313).
function shellPush(to, from = location.hash){
  shellCame(from, to);
  // While a dialog's entry is being given back the push waits for it to
  // have gone (backPressed), or the give-back would undo the page.
  if (backGiving){ backAfter = to; shellSeen = to; return; }
  // From a dialog's entry the page takes it over (hashGo's way).
  if (history.state?.dlg) history.replaceState(null, "", to);
  else history.pushState(null, "", to);
  shellSeen = to;
}

// A move inside a page (a notebook view, a wiki page) is a history entry,
// so Back returns to where it was (R256 step 3): the draw replaces the
// address as it always does, and the one before is put back and the new
// one pushed after it.
function navPush(fn){
  const was = location.hash;
  fn();
  const to = routeOf(tabOf(panes[0]));
  if (to && to !== was){ history.replaceState(null, "", was || location.pathname + location.search); shellPush(to); }
}

// The address a tab is reached at: #/group, #/group/tool, #/spaces/NAME,
// with a node page's node and the open wiki page on the end. A terminal has
// none. A group's address is its key but for the spaces', whose key is
// projects as the code knows them; #/projects/... still opens (routeIn).
const ADDR_OF = {projects: "spaces"};
const routeIn = hash => String(hash || "").replace(/^#\/spaces(?=\/|$)/, "#/projects");
function routeOf(t){
  if (!t) return "";
  if (t.kind === "notebook"){
    // ...and the view it is on (R218 step 3): Overview is the Briefing
    // view's name on the page, so the address says overview.
    const n = notebooks.get(t.arg), v = n?.where?.() || "";
    // ...and a branch's comparison, its own page (R269 step 2).
    const page = v === "wiki" ? n?.wikiPage?.() || "" : v === "git" && n?.gitPage?.() ? "compare/" + encodeURIComponent(n.gitPage())
      : v === "design" ? n?.designPage?.() || "" : "";
    return "#/spaces/" + encodeURIComponent(t.arg) + (v ? "/" + (v === "briefing" ? "overview" : v) : "")
      + (page ? "/" + (v === "git" ? page : encodeURIComponent(page)) : "");
  }
  if (!isToolKind(t.kind)) return "";
  // The Notifications page is on no group: the bell's See all opens it.
  if (t.kind === "notices") return "#/notifications";
  // Help names the doc on show (R258), so a link to one lands on it.
  if (t.kind === "help") return "#/help" + (helpCur && helpCur !== helpIndex?.home ? "/" + encodeURIComponent(helpCur) : "");
  const g = groupOf(t.kind);
  if (!g) return "";
  // Home is #/home, the address everything links to, though its group
  // holds Controller settings too.
  if (t.kind === "home") return "#/home";
  // An installed thing's page names its node and itself under Installed's.
  if (t.kind === "thing") return `#/machines/installed/${encodeURIComponent(instNode || "")}/${encodeURIComponent(thingKey)}`;
  // ...and a Library entry's page its node and itself under the Library's (R183).
  if (t.kind === "entry") return `#/build/library/${encodeURIComponent(libNode || "")}/${encodeURIComponent(entryKey)}`;
  const node = NODE_PICKED[t.kind]?.() || "";
  // A page named as its group is (Jobs, beside Schedules since R117) keeps
  // the group's own address, #/jobs/failed as Home links it, never
  // #/jobs/jobs; the reader takes a segment that is no page's for its node.
  const at = ADDR_OF[g.key] || g.key;
  // ...and the Library's narrowing (R256), so Back, a reload and a link land
  // on the same list.
  return ((g.tools || []).length > 1 && t.kind !== g.key ? `#/${at}/${t.kind}` : `#/${at}`) + (node ? "/" + encodeURIComponent(node) : "")
    + (t.kind === "library" ? libAddr() : "");
}

// Open what an address names; nothing happens for one that names nothing.
function openRoute(hash){
  hash = routeIn(hash);
  // What follows a ? is a page's own narrowing (the Library's, R256).
  const qat = String(hash || "").indexOf("?");
  const query = qat >= 0 ? hash.slice(qat + 1) : "";
  if (qat >= 0) hash = hash.slice(0, qat);
  const m = /^#\/([a-z]+)(?:\/([^/]+))?(?:\/([^/]+))?(?:\/([^/]+))?(?:\/([^/]+))?/.exec(hash || "");
  if (!m) return false;
  const [, key, a, b, c, d] = m;
  if (key === "projects" && a && !RAIL[1].tools.some(([k]) => k === a)){
    const name = decodeURIComponent(a);
    if (!(state?.projects || []).some(p => p.name === name)) return false;
    railWant = "projects";
    const v = b ? decodeURIComponent(b) : "";
    // A comparison is set before the open as well as after it: the open
    // writes the address, and written without the comparison the entry for
    // it read /git, so Back from it went nowhere.
    const cmp = v === "git" ? (c === "compare" && d ? decodeURIComponent(d) : "") : null;
    if (cmp !== null) notebooks.get(name)?.gitAt?.(cmp);
    // ...and a design page, or the list, for the same reason.
    const dpage = v === "design" ? (c ? decodeURIComponent(c) : "") : null;
    if (dpage !== null) notebooks.get(name)?.designAt?.(dpage);
    openNotebook(name, v ? (v === "overview" ? "briefing" : v) : undefined);
    if (v === "wiki" && c) notebooks.get(name)?.wikiAt?.(decodeURIComponent(c));
    if (dpage !== null) notebooks.get(name)?.designAt?.(dpage);
    if (cmp !== null) notebooks.get(name)?.gitAt?.(cmp);
    return true;
  }
  if (key === "notifications"){ openNotices(); return true; }
  if (key === "help"){
    railWant = "help";
    // #/help/help is the page by its tool's name, as #/group/tool is for any
    // group: its front page, not a doc called help.
    const doc = a && a !== "help" ? decodeURIComponent(a) : helpIndex?.home || "";
    if (doc && doc !== helpCur){ helpCur = doc; helpQ = ""; helpHits = null; readMoved("help"); }
    // ...at a section of it when the address names one (#/help/reference/
    // the-install-key): the doctor's links land on the fix itself.
    if (b){ helpAnchor = decodeURIComponent(b); readMoved("help"); }
    openHelp();
    if (helpIndex && helpCur) helpRead(helpCur);
    return true;
  }
  let g = RAIL.find(x => x.key === key);
  if (!g) return false;
  // A page that moved group keeps its old address: #/machines/settings and
  // #/home/settings, bookmarks from before Controller settings had a group
  // of its own, open it there.
  if (a && !(g.tools || []).some(([k]) => k === a) && groupOf(a)) g = groupOf(a);
  // An installed thing's page (R181 step 2): #/machines/installed/NODE/KIND:NAME.
  if (g.key === "machines" && a === "installed" && b && c){ railWant = g.key; openThing(decodeURIComponent(b), decodeURIComponent(c)); return true; }
  // A Library entry's page (R183): #/build/library/NODE/KIND:NAME.
  if (g.key === "build" && a === "library" && b && c){ railWant = g.key; openEntry(decodeURIComponent(b), decodeURIComponent(c)); return true; }
  const multi = (g.tools || []).length > 1;
  // A group of one tool names its node second (#/group/NODE), as routeOf
  // writes it.
  const named = (g.tools || []).some(([k]) => k === a);
  const kind = railTool(g, named ? a : "");
  if (!kind) return false;
  railWant = g.key;
  // The node the address names, set before the page draws (R256 step 3).
  const node = multi && named ? b : a;
  if (node && NODE_SET[kind]) NODE_SET[kind](decodeURIComponent(node));
  if (kind === "library"){
    const was = libAddr();
    libFromAddr(query);
    if (libAddr() !== was && lib){ lib.moreAsked = false; libPagesFrom(); loadLibrary(); }
  }
  OPENERS[kind]?.();
  return true;
}

// The address follows the page on show (render calls this): replaced, not
// pushed, so a poll's redraw is not a history entry; a rail press pushes.
// The address it last left, or null before the first: one that has changed
// since, and is not the page on show, is a navigation whose hashchange has
// not run yet, and is left for it. Replacing it took the address back to the
// page being left, which the handler then opened (B303).
let shellSeen = null;
// Signing in after a deliberate Sign out opens on Home, never on the page
// the browser last showed, which on a shared browser was another person's
// (the operator, 22 Nov). Sign out leaves the note (signOutGo); the boot
// after it takes it once. A sign-in the page was sent to (its session ran
// out) leaves none and comes back to the page as a reload does.
const SIGNED_OUT_KEY = "bb.signedout";
function signOutGo(url){
  try{ localStorage.setItem(SIGNED_OUT_KEY, "1"); }catch(e){ /* private mode */ }
  location.href = url;
}
function signedOut(take = false){
  try{
    const was = localStorage.getItem(SIGNED_OUT_KEY) === "1";
    if (take) localStorage.removeItem(SIGNED_OUT_KEY);
    return was;
  }catch(e){ return false; }
}
// The address of the page in front, as this browser last showed it: what a
// load with no address of its own will open on (its saved front tab), so
// its first placeholder is shaped as that page and not as Home's.
const FRONT_KEY = "bb.front";
let frontKept = null;
function keepFront(to){
  if (to === frontKept) return;
  frontKept = to;
  try{ localStorage.setItem(FRONT_KEY, to); }catch(e){ /* private mode */ }
}
// ...read by the boot, before anything is drawn: the address the page will
// open on.
function bootFront(hash){
  if (hash && hash !== "#/") return hash;
  if (signedOut()) return "#/home";
  try{ return localStorage.getItem(FRONT_KEY) || ""; }catch(e){ return ""; }
}
function shellSync(){
  // Not while a dialog's entry is being given back: written over it, the
  // give-back went to the page before (backPressed syncs once it lands).
  if (backGiving) return;
  const to = routeOf(tabOf(panes[0]));
  if (shellSeen !== null && location.hash && location.hash !== shellSeen && location.hash !== to) return;
  shellSeen = to || "";
  if (shellBooted) keepFront(to || "");
  // A page that moved under a dialog takes its entry over, so the dialog
  // put away does not give back the page's address (backRelease).
  if (to && to !== location.hash) history.replaceState(null, "", to);
  // A document in front has no address: the page's goes, so a reload lands
  // on the document this browser had in front (R131), not on the last page.
  else if (!to && location.hash) history.replaceState(null, "", location.pathname + location.search);
}
// Once, on the first draw that had state: an address the page was opened on
// wins over the strip's remembered front tab, unless it names that very tab.
let shellBooted = false;
function shellBoot(){
  if (shellBooted || !state) return;
  shellBooted = true;
  const h = location.hash, out = signedOut(true);
  if (h && h !== "#/" && h !== routeOf(tabOf(panes[0]))) openRoute(h);
  else if (out && (!h || h === "#/") && routeOf(tabOf(panes[0])) !== "#/home") openRoute("#/home");
}

// A page on show in a visible pane: what a watch asks before fetching for it
// (the design's pages rule: nothing for the pages not on show).
function shown(kind){
  return panes.some((id, i) => (i === 0 || isSplit()) && tabOf(id)?.kind === kind);
}

// The rail, and on a phone the bar and its More sheet.
function drawRail(){
  const rail = $("rail"), bar = $("railbar");
  if (!rail || !bar || !state) return;
  const on = railOn(), groups = railGroups();
  const item = g => `<button type="button" class="ritem${g.key === on ? " on" : ""}" data-rail="${esc(g.key)}" aria-label="${esc(g.label)}"${
      g.key === on ? ' aria-current="page"' : ""}>${RAIL_ICONS[g.icon] || TOOL_ICONS[g.icon] || ""}<span class="rlbl">${esc(g.label)}</span></button>`;
  const html = groups.map(item).join("");
  // Through patch(), which remembers what it wrote: compared against
  // innerHTML, which the browser writes back its own way (an SVG's
  // attributes, an entity), it never matched, and the rail was rebuilt on
  // every draw with the pointer on it (R218 step 10); patched, a group
  // pressed keeps its button and the keyboard's focus on it (R244).
  if (patch(rail, html, true)){
    rail.querySelectorAll("[data-rail]").forEach(b => {
      b.onclick = () => railGo(b.dataset.rail);
      // A pointer resting on a group reads ahead what its page waits on
      // first, so the press opens on it (a mouse only: a touch is the press).
      b.onpointerenter = e => { if (e.pointerType === "mouse") railWarm(b.dataset.rail); };
    });
  }
  // ...and the bar beside the group on show slides to the one pressed.
  slideMark(rail, "rail", true);
  const five = groups.filter(g => RAIL_PHONE.includes(g.key));
  const rest = groups.filter(g => !RAIL_PHONE.includes(g.key));
  const moreOn = rest.some(g => g.key === on);
  const bhtml = five.map(item).join("") + (rest.length
    ? `<button type="button" class="ritem${moreOn ? " on" : ""}" data-railmore aria-haspopup="menu" aria-expanded="${railMoreOpen}" aria-label="More">${RAIL_ICONS.more}<span class="rlbl">More</span></button>` : "");
  if (patch(bar, bhtml, true)){
    bar.querySelectorAll("[data-rail]").forEach(b => b.onclick = () => { railMoreShow(false); railGo(b.dataset.rail); });
    // Set, not added: the patch keeps the button, and a second listener
    // would open More and shut it again in one press.
    const mb = bar.querySelector("[data-railmore]");
    if (mb) mb.onclick = () => railMoreShow(!railMoreOpen);
  }
  const more = $("railmore");
  if (more){
    const mhtml = rest.map(g => `<button type="button" class="ritem${g.key === on ? " on" : ""}" data-rail="${esc(g.key)}">${
        RAIL_ICONS[g.icon] || TOOL_ICONS[g.icon] || ""}<span class="rlbl">${esc(g.label)}</span></button>`).join("");
    if (patch(more, mhtml, true)){
      more.querySelectorAll("[data-rail]").forEach(b => b.onclick = () => { railMoreShow(false); railGo(b.dataset.rail); });
    }
  }
}
let railMoreOpen = false;
function railMoreShow(on){
  railMoreOpen = !!on;
  const m = $("railmore"), b = $("railbar")?.querySelector("[data-railmore]");
  if (m) m.hidden = !railMoreOpen;
  if (b) b.setAttribute("aria-expanded", String(railMoreOpen));
}

// The pane's bar for a page: the group's tools as a sub-nav, one button
// in the accent when the page stands alone (the operator, 16 Oct: a bare
// name beside the other pages' segments read as a different kind of page);
// a page has no close, the rail is how you leave it (a split pane keeps its
// own close).
function shellBar(t, i){
  const g = groupOf(t.kind);
  const tools = g ? g.tools.filter(([k]) => !PRESSED.has(k) && (railAllows(k) || k === t.kind)) : [[t.kind, tabLabel(t)]];
  // A page a press opened: its top header, Back and its name, in place of
  // the sub-nav it is not on.
  if (PRESSED.has(t.kind)) return backHead(t) + (g && GROUP_HEADS[g.key] && NODE_PICKED[t.kind] ? groupHeader(t, g) : "");
  const grouped = !!g && GROUP_HEADS[g.key];
  const nid = grouped ? groupNode(g, t.kind) : "";
  const nav = `<span class="subnav pseg hscroll" role="tablist" aria-label="${esc(g ? g.label : tabLabel(t))}">${tools.map(([k, label]) => {
    // A sub-tab whose feature the picked node lacks is drawn unavailable
    // (R178): muted, the reason on it, still a press, and the page says
    // the same and offers the one thing that makes it available.
    const off = grouped && nid ? toolOff(k, nid) : "";
    return `<button type="button" role="tab" aria-selected="${k === t.kind}" class="${k === t.kind ? "on" : ""}${off ? " off" : ""}"${g ? ` data-subnav="${esc(k)}"` : ""}${off ? ` title="${esc(off)}"` : ""}>${esc(label)}${off ? `<span class="navnote">not here</span>` : ""}</button>`;
  }).join("")}</span>`;
  // A group that wears one header over its sub-nav (R177, R178): the node
  // picked once for every page of the group, the group's actions on the
  // sub-nav's line at its right (the operator, 28 Oct).
  return grouped ? groupHeader(t, g) + `<span class="subrow">${nav}<span class="sp"></span>${GROUP_HEADS[g.key].actions ? GROUP_HEADS[g.key].actions() : ""}</span>` : nav;
}
// Where Back on a page a press opened goes (R181): the address it was
// opened from, kept as it opens, with what that page is called; none when it
// was opened by its own address (a reload, a link from outside), and Back
// then opens its group's first page.
let shellFrom = null;
function shellCame(from, to){
  const k = kindOfRoute(to);
  if (!PRESSED.has(k) || kindOfRoute(from) === k) return;
  const was = shellFrom?.hash;
  shellFrom = from ? {kind: k, hash: from, label: routeLabel(from)} : null;
  // A header drawn before this was known names it on the next draw.
  if ((shellFrom?.hash || null) !== (was || null)) setTimeout(drawPanes);
}
// The page kind an address names, or "".
function kindOfRoute(hash){
  hash = routeIn(hash);
  const m = /^#\/([a-z]+)(?:\/([^/]+))?(?:\/([^/]+))?(?:\/([^/]+))?/.exec(hash || "");
  if (!m) return "";
  if (m[1] === "machines" && m[2] === "installed" && m[4]) return "thing";
  if (m[1] === "build" && m[2] === "library" && m[4]) return "entry";
  if (m[1] === "projects" && m[2] && !RAIL[1].tools.some(([k]) => k === m[2])) return "notebook";
  const g = RAIL.find(x => x.key === m[1]);
  // A page that moved group is still named by its old address (openRoute).
  return g ? ((g.tools || []).some(([k]) => k === m[2]) || (m[2] && groupOf(m[2])) ? m[2] : g.tools[0][0]) : m[1];
}
// What a person calls the page at an address: its tool's name, or the project's.
function routeLabel(hash){
  const k = kindOfRoute(hash);
  if (k === "notebook") return projLabel(decodeURIComponent(/^#\/projects\/([^/]+)/.exec(routeIn(hash))[1]));
  if (k === "notifications") return "Notifications";
  for (const g of RAIL) for (const [key, label] of g.tools || []) if (key === k) return label;
  return "";
}
function backHead(t){
  const g = groupOf(t.kind);
  const from = shellFrom?.kind === t.kind ? shellFrom : null;
  const home = g ? g.tools.find(([k]) => k === PRESSED_HOME[t.kind]) || g.tools.find(([k]) => !PRESSED.has(k)) : null;
  const to = from?.label || (home || [])[1] || "back";
  return `<span class="backhead"><button type="button" class="bare backbtn" data-shellback title="back to ${esc(to)}">${ICON_BACK}<span>${esc(to)}</span></button>`
    + `<span class="backof">${esc(tabLabel(t))}</span></span>`;
}
const ICON_BACK = `<svg viewBox="0 0 16 16" width="14" height="14" aria-hidden="true"><path d="M10 3 5 8l5 5" fill="none" stroke="currentColor" stroke-width="1.8" stroke-linecap="round" stroke-linejoin="round"/></svg>`;
function shellBack(t){
  const from = shellFrom?.kind === t?.kind ? shellFrom : null;
  shellFrom = null;
  // The address it was opened from, opened as a press would: the browser's
  // own history need not hold it (a page opened without an entry of its own).
  if (from && from.hash && openRoute(from.hash)){
    const to = routeOf(tabOf(panes[0]));
    if (to) shellPush(to, location.hash);
    return;
  }
  const g = groupOf(t?.kind);
  if (g) railGo(g.key, PRESSED_HOME[t?.kind]);
}

function wireShellBar(bar){
  bar.querySelectorAll("[data-shellback]").forEach(b => b.onclick = () => shellBack(tabOf(panes[0])));
  // The line under the tab on show slides to the one pressed (slideMark),
  // kept per group so another group's sub-nav never slides from this one.
  const sub = bar.querySelector(".subnav");
  if (sub) slideMark(sub, "subnav:" + (groupOf(sub.querySelector(".on")?.dataset.subnav || "")?.key || sub.getAttribute("aria-label") || ""));
  bar.querySelectorAll("[data-subnav]").forEach(b => b.onclick = () => {
    const g = groupOf(b.dataset.subnav);
    if (g) railGo(g.key, b.dataset.subnav);
  });
  wireGroupHeader(bar);
}

// ---- a group's header (R177, R178) --------------------------------------------------
// The operator, 28 Oct: a header like a project's for the Machines group,
// the node pulldown there instead of on each of the three sub-tabs; then
// the same for Build and Containers. One band in the project header's
// shape: the node picker where the name is, the node's facts beside it in
// the data face (seen, reached from, its agent), the sub-nav strip under
// it with the group's own actions at its right. One pick drives every page
// of the group: each keeps its own node state for its openers (NODE_PICKED
// and NODE_SET name them), the header reads the page on show and sets them
// all on a press. A page's own bar keeps its actions and loses its picker.
const GROUP_HEADS = {
  machines: {actions: () => machinesActions()},
  build: {},
  containers: {},
};
// The nodes a page is offered: every machine there is but the controller's
// container, and not the controller's own machine on a page not built for
// one (NOT_ON_OWN).
function machinesLive(kind = ""){
  return (nodesList || []).filter(n => n.state !== "retired" && n.kind !== "local" && !(state?.bare_metal && n.config?.own && NOT_ON_OWN.has(kind)));
}
function machinesNode(kind){
  return NODE_PICKED[kind]?.() || "";
}
// Every node with an agent that is not retired: what a page about a node's
// own tools picks from and counts (the Library, Installed, Files, the
// Emulator, a CI runner, the nodes that dial in). One not yet enrolled,
// switched off, hosting only or quiet is among them, and says so where it
// is drawn.
function liveAgents(){
  return (nodesList || []).filter(n => n.kind === "agent" && n.state !== "retired");
}
// The node a page opens on: the one it shows now (`cur`) while that is among
// the nodes there are (`have`, each named by `idOf`), else the one this
// browser kept for it (its record's keep, then the key `also` names), else
// `fallback` where the page has one, else the first there is, else "".
// Asked on every load and draw, so a node retired under a page is not shown
// as if it were still there.
function keptNode(kind, {have = liveAgents(), idOf = n => n.id, cur = PAGE_KINDS[kind].node(), also = "", fallback} = {}){
  const there = id => have.some(n => idOf(n) === id);
  let want = cur;
  if (!there(want)){
    try{ want = localStorage.getItem(PAGE_KINDS[kind].keep) || (also && localStorage.getItem(also)) || ""; }catch(e){ want = ""; }
  }
  if (!there(want) && fallback !== undefined) want = fallback;
  if (!there(want)) want = (have.length && idOf(have[0])) || "";
  return want;
}
// A page opened on a node somebody named (the bell's rows, a node's page, a
// space's Sign in on NODE): the node set and kept, the page opened with its
// address pushed as a press pushes it, and read for that node. A node the
// list does not hold yet is read for first (B754's lesson).
function openKindOn(kind, id){
  const k = PAGE_KINDS[kind];
  if (id) k.setNode(id);
  if (!(nodesList || []).some(n => n.id === id)) nodesStale = true;
  try{ localStorage.setItem(k.keep, id); }catch(e){ /* private */ }
  const was = location.hash;
  k.open();
  readMoved(k.moved);
  const to = routeOf(tabOf(panes[0]));
  if (to && to !== was) shellPush(to);
  k.load();
}
// One node per group (the operator, 29 Oct: the header's pick is the node
// every sub-tab of the group shows). A page whose own node differs from the
// group's is moved to it when it is drawn, read again for it; a page an
// opener sent to a node of its own (a node's row, a Library entry) takes
// the group with it, which is how a node it last reported differs from
// what the page holds now. Kept in this browser per group.
const GROUP_CUR = {}, PAGE_SEEN = {};
function groupKept(g){ try{ return localStorage.getItem("bb.group." + g.key) || ""; }catch(e){ return ""; } }
function groupKeep(g, nid){
  GROUP_CUR[g.key] = nid;
  try{ localStorage.setItem("bb.group." + g.key, nid); }catch(e){ /* private */ }
}
function groupNode(g, kind){
  const live = machinesLive(kind);
  const ok = id => !!id && live.some(n => n.id === id);
  const page = machinesNode(kind);
  let cur = ok(GROUP_CUR[g.key]) ? GROUP_CUR[g.key] : groupKept(g);
  if (kind in PAGE_SEEN && ok(page) && page !== PAGE_SEEN[kind]) cur = page;
  if (!ok(cur)) cur = ok(page) ? page : live[0]?.id || "";
  if (cur !== GROUP_CUR[g.key]) groupKeep(g, cur);
  if (cur && page !== cur && NODE_SET[kind]){
    NODE_SET[kind](cur);
    // Read for its node after this draw, not inside it.
    if (GROUP_LOAD[kind]) setTimeout(() => { if (tabOf(panes[0])?.kind === kind) GROUP_LOAD[kind](); }, 0);
    else setTimeout(drawPanes, 0);
  }
  PAGE_SEEN[kind] = cur;
  return cur;
}
function groupPick(g, nid){
  groupKeep(g, nid);
  (g.tools || []).forEach(([k]) => {
    if (NODE_SET[k]) NODE_SET[k](nid);
    PAGE_SEEN[k] = nid;
    if (GROUP_KEEP[k]){ try{ localStorage.setItem(GROUP_KEEP[k], nid); }catch(e){ /* private */ } }
    PAGE_KINDS[k].kept?.();
  });
  new Set((g.tools || []).map(([k]) => PAGE_KINDS[k].moved).filter(Boolean)).forEach(key => readMoved(key));
  drawPanes();
  const on = tabOf(panes[0])?.kind;
  if (on && GROUP_LOAD[on]) GROUP_LOAD[on]();
}
// Why a page's feature is not on this node, or "" (nothing known counts as
// there: a list not read yet marks nothing).
function toolOff(kind, nid){
  const n = (nodesList || []).find(x => x.id === nid);
  return n && PAGE_KINDS[kind]?.off ? PAGE_KINDS[kind].off(n, nid) : "";
}
function groupHeader(t, g){
  if (nodesList === null){
    // Drawn on every paint until the list lands: the read out is shared, not
    // asked again behind on each.
    nodesKnown();
    // A page that has its nodes before the list lands (Storage, nginx) is
    // drawn from them, so its picker is there with its rows.
    const have = t.kind === "storage" ? (typeof storageList !== "undefined" && storageList || []).map(n => ({id: n.node, name: n.name, live: n.live}))
      : t.kind === "nginx" ? (typeof nginxList !== "undefined" && nginxList || []).map(n => ({id: n.node, name: n.name, live: n.live})) : [];
    if (!have.length) return `<span class="phead mchead">${nodePick("", null)}${skv(5, "ndstatesk")}<span class="sp"></span></span>`;
    return `<span class="phead mchead">${nodePick("ndPick", have, machinesNode(t.kind) || have[0].id)}${skv(5, "ndstatesk")}<span class="sp"></span></span>`;
  }
  const live = machinesLive(t.kind);
  const cur = groupNode(g, t.kind);
  const n = live.find(x => x.id === cur);
  // Beside the picker, the node's state as one pill and a press to its own
  // page from any page of the group. When it was seen, where it dials in
  // from and its agent are on that page, not a line under the picker, which
  // took a phone's second and third lines.
  const s = n ? nodeState(n) : null;
  const pill = !s ? "" : `<button type="button" class="pill stat ${s.cls} ndstate" data-ndgo="${esc(n.id)}"
      aria-label="${esc(n.name)} is ${esc(s.word)}: open its page" title="${esc(s.means ? `${s.means}: open its page` : "open its page")}">${esc(s.word)}</button>`;
  // The containers' pages leave the own machine out, so on a machine alone
  // there is no other node to show them for.
  const ownHere = state?.bare_metal && (nodesList || []).some(x => x.config?.own && x.state !== "retired");
  const pick = live.length ? nodePick("ndPick", live.map(x => ({id: x.id, name: x.config?.own ? `${x.name} (this machine)` : x.name, live: x.live})), cur,
    undefined, {stated: !!pill}) : `<span class="pname">${ownHere ? "No other node yet" : "No node yet"}</span>`;
  return `<span class="phead mchead">${pick}${pill}<span class="sp"></span></span>`;
}
// A node's own page from anywhere: Machines' Nodes on it, the group's
// picker following (a group header's state pill, the search's node rows).
function openNodePage(nid){
  railGo("machines", "nodes");
  openNodesTab(nid);
}
// The Machines group's actions, on the sub-nav's line: dead with the enroll
// feature off (the reason is on the Nodes page) and until the node list lands.
// At a desk the two buttons; on a phone, where they cut the tabs short behind
// the strip's arrow, one + whose menu holds them, so the tabs are whole and
// the row keeps its one height (the operator, 22 Nov; the group-header rule).
function machinesActions(){
  // Not drawn for an account whose roles do not give a new node (Nodes Write
  // on every node, R277): what a role does not give is not advertised.
  if (state?.can?.["nodes-new"] === false) return "";
  const dead = nodesList === null || featureOff("enroll") ? " disabled" : "";
  const fold = actMore([`<button type="button" data-ndvm${dead}>New VM</button>`, `<button type="button" data-ndenroll${dead}>Enroll node</button>`],
    true, {glyph: "+", said: "New VM or Enroll node", title: "a new VM, or a machine to enroll", dead: !!dead});
  return `<span class="actbar mcacts"><span class="mcwide"><button type="button" id="ndVm"${dead}>${"New VM"}</button>
    <button type="button" class="primary" id="ndEnroll"${dead}>${barSaid("Enroll node", "Enroll")}</button></span>${fold}</span>`;
}
function wireGroupHeader(bar){
  const go = bar.querySelector("[data-ndgo]");
  if (go) go.onclick = () => openNodePage(go.dataset.ndgo);
  const pick = bar.querySelector("#ndPick");
  // A pick is a history entry (B31), so Back returns to the node before.
  if (pick) pick.onchange = () => navPush(() => groupPick(groupOf(tabOf(panes[0])?.kind || "nodes") || groupOf("nodes"), pick.value));
  const vms = bar.querySelectorAll("#ndVm, [data-ndvm]"), ens = bar.querySelectorAll("#ndEnroll, [data-ndenroll]");
  if (vms.length || ens.length){
    const d = ndDialogs();
    vms.forEach(b => { b.onclick = () => { closeMore(); d.openVm(); }; });
    ens.forEach(b => { b.onclick = () => { closeMore(); d.openEnroll(); }; });
    wireMore(bar);
  }
}

// ---- maintenance mode's band ---------------------------------------------------
// Drawn under the header for the owner while maintenance mode is on: the
// server sends it hidden on every page, and the poll shows it, so switching
// it on or off shows without a reload.
function drawMaintBand(){
  const b = document.getElementById("maintband");
  const off = !(state?.can?.maintenance && state?.settings?.settings?.maintenance_mode?.value);
  // Written only when it changes: a poll that brings nothing new writes nothing.
  if (b && b.hidden !== off) b.hidden = off;
  // Its link opens Controller settings at Maintenance, where it is switched
  // off (the operator, 26 Oct).
  const go = b?.querySelector("[data-maintgo]");
  if (go && !go.onclick) go.onclick = e => { e.preventDefault(); SPLIT.settings = {pick: "maint", open: true}; openSettingsTab(); };
}

// ---- a held start's band (R56 step 9) ------------------------------------------
// Drawn under the header on a bare-metal install while its start is held:
// the server sends it hidden on every page, and the poll shows it with why.
function drawHeldBand(){
  const b = document.getElementById("heldband");
  if (!b) return;
  const h = state?.held || {};
  const off = !h.held;
  if (b.hidden !== off) b.hidden = off;
  const why = b.querySelector("[data-heldwhy]");
  const said = (h.why || []).length ? `Held because ${h.why.join("; ")}.` : "";
  if (why && why.textContent !== said) why.textContent = said;
  const go = b.querySelector("[data-heldgo]");
  // While the first-run page stands, no page shows behind it (B662): the
  // walk holds Start.
  if (go && !go.onclick) go.onclick = e => { e.preventDefault(); setupNeeded() ? setupWalkPick("move") : openMachineTab(); };
}

// ---- a moved controller's band (R90 step 12) ---------------------------------
function drawMovedBand(){
  const b = document.getElementById("movedband");
  if (!b) return;
  const to = state?.moved_to || "";
  const off = !to;
  if (b.hidden !== off) b.hidden = off;
  const a = b.querySelector("[data-movedto]");
  if (a && to && a.textContent !== to){ a.textContent = to; a.href = to; }
}

// ---- search: jump to a page, a project, a container or a node ---------------

// Rows: [label, where, go]. Pages by name, projects by the name they are
// shown under, nodes from the list once it has landed, containers from what
// every node last answered (dmJumpRows).
function jumpItems(q){
  const needle = (q || "").trim().toLowerCase();
  if (!needle) return [];
  const rows = [];
  for (const g of railGroups()){
    for (const [k, label] of g.tools) if (railAllows(k))
      rows.push([label, g.tools.length > 1 ? `${g.label} page` : "page", () => railGo(g.key, k)]);
  }
  for (const p of state?.projects || [])
    rows.push([projLabel(p.name), "space", () => { railWant = "projects"; openNotebook(p.name); }]);
  for (const n of nodesList || [])
    rows.push([n.name || n.id, "node", () => openNodePage(n.id)]);
  for (const c of dmJumpRows())
    rows.push([c.name, `container on ${c.where}`, () => dmJumpTo(c.node, c.name)]);
  const hit = rows.filter(([label]) => label.toLowerCase().includes(needle));
  hit.sort((a, b) => a[0].toLowerCase().indexOf(needle) - b[0].toLowerCase().indexOf(needle));
  return hit.slice(0, 8);
}
let jumpRows = [];
let jumpAt = 0;                  // the row the arrow keys have marked, Enter's
function drawJump(){
  const inp = $("jump"), list = $("jumpList");
  if (!inp || !list) return;
  jumpRows = jumpItems(inp.value);
  jumpAt = 0;
  // Something typed that matches nothing says so, rather than the list
  // staying shut as if the field had not heard (B72).
  const none = !jumpRows.length && !!inp.value.trim();
  list.hidden = !jumpRows.length && !none;
  patch(list, none ? `<div class="jnone" role="option" aria-disabled="true">nothing matches “${esc(inp.value.trim())}”</div>`
    : jumpRows.map(([label, where], i) =>
    `<button type="button" class="jrow${i === 0 ? " on" : ""}" id="jumpRow${i}" data-jump="${i}" role="option" aria-selected="${i === 0}"><span class="jl">${esc(label)}</span><span class="jw">${esc(where)}</span></button>`).join(""));
  list.querySelectorAll("[data-jump]").forEach(b => b.onclick = () => jumpGo(Number(b.dataset.jump)));
  if (jumpRows.length) inp.setAttribute("aria-activedescendant", "jumpRow0");
  else inp.removeAttribute("aria-activedescendant");
}
// ArrowDown and ArrowUp move the mark through the rows, round at the ends,
// so the second hit is a key away and not only the mouse's (B72).
function jumpMove(by){
  const list = $("jumpList");
  if (!jumpRows.length || !list) return;
  jumpAt = (jumpAt + by + jumpRows.length) % jumpRows.length;
  list.querySelectorAll("[data-jump]").forEach(b => {
    const on = Number(b.dataset.jump) === jumpAt;
    b.classList.toggle("on", on);
    b.setAttribute("aria-selected", String(on));
    if (on) b.scrollIntoView({block: "nearest"});
  });
  $("jump")?.setAttribute("aria-activedescendant", "jumpRow" + jumpAt);
}
function jumpGo(i){
  const row = jumpRows[i] || jumpRows[0];
  const inp = $("jump"), list = $("jumpList");
  if (inp){ inp.value = ""; inp.blur(); }
  if (list){ list.hidden = true; list.innerHTML = ""; }
  jumpRows = [];
  if (!row) return;
  row[2]();
}
function wireJump(){
  const inp = $("jump"), list = $("jumpList");
  if (!inp || !list) return;
  // Its hint is the whole where it fits, else a shorter one, else two words
  // (the operator, 18 Oct: cut off mid-word), as every field's is (phFit,
  // its data-ph-short); the aria-label keeps the whole of it either way.
  onTyping(inp, drawJump);
  inp.onfocus = () => { (nodesList === null ? nodesKnown() : Promise.resolve()).then(dmJumpLoad).then(drawJump); drawJump(); };
  inp.onkeydown = e => {
    if (e.key === "Enter"){ e.preventDefault(); jumpGo(jumpAt); }
    else if (e.key === "ArrowDown" || e.key === "ArrowUp"){ e.preventDefault(); jumpMove(e.key === "ArrowDown" ? 1 : -1); }
    else if (e.key === "Escape"){ inp.value = ""; list.hidden = true; inp.blur(); }
  };
  document.addEventListener("click", e => { if (!e.target.closest(".jump")) list.hidden = true; });
}

// ---- the project page's header (R218 step 3) -----------------------------

// A project is a page: its pane's bar is the header the design names (the
// a-notebook/project-page rule): the name large, the branch and the node in
// the data face, the session's state as the dot and a word, and at the
// right its actions: Start agent, or Open
// Claude in green while yours runs (the chooser under it), Shell, and the rest behind one menu (link, phone, report,
// lock, pin, settings). Drawn by paintBar on every pass like every bar; the
// chooser sits on the pane, not in the bar, so a repaint leaves it up.
// The session's state as the dot and a word: this account's session
// first, then whose else is here, then none. The dot is the one every
// session surface wears.
function projectState(p){
  // A space's one session runs on its first repository (R136), so every
  // repository's header says that one's state, as its agent button does:
  // the second repository of a space read "no session" beside a lit Manage
  // agent (the operator's screen, 19 Nov).
  const name = state?.repos?.[p.project]?.members?.[0] || p.name, sess = myLiveSession(name), mine = !!sess;
  // One entry per person per agent per slot (B344: a person's Claude and
  // Codex folded into one, one session's state masking the other's; R143:
  // and two of one agent's), from where each session is: its account, its
  // agent, its slot and its state, a session on two nodes once.
  const rows = (state?.claude_where || {})[tmuxName(name)] || (state?.claude_where || {})[name] || [];
  const seen = new Map();
  for (const r of rows){
    const k = `${r.who}|${r.agent}|${r.slot || 1}`, was = seen.get(k);
    seen.set(k, {who: r.who, agent: r.agent, slot: r.slot || 1, working: !!(r.working || was?.working), asking: !!(r.asking || was?.asking)});
  }
  const one = (st, word, cls, agent, slot = 1) => `<span class="pstate${cls}">${st ? `<span class="st ${st}"></span>` : ""}${esc(word)}${
    agent ? `<span class="pagent"> · ${esc(agentSlotName(agentById(agent) || {name: agent}, slot))}</span>` : ""}</span>`;
  // Yours first, then everybody else's, each with its own dot (the
  // operator, 16 Oct). On its permission prompt it is asking, in amber, as
  // the dock and Sessions say it (B98); another account's reads asking too
  // (B104), not "asking you": only that person's terminal answers it.
  const all = [...seen.values()];
  const me = all.filter(e => e.who === state?.me).map(e => e.asking ? one("asking", "asking you", "", e.agent, e.slot)
    : e.working ? one("working", "working", "", e.agent, e.slot) : one("waiting", "waiting for you", "", e.agent, e.slot)).join("")
    // A session of yours the poll has not placed on a node yet.
    || (mine ? (claudeOf(sess)?.state === "asking" ? one("asking", "asking you", "", agentOfSession(tmuxBase(sess))?.agent.id)
        : one("waiting", "waiting for you", "", agentOfSession(tmuxBase(sess))?.agent.id)) : "");
  const them = all.filter(e => e.who !== state?.me).map(e => e.asking ? one("asking", `${e.who} asking`, " other", e.agent, e.slot)
    : one(e.working ? "working" : "waiting", `${e.who}${e.working ? " working" : "'s session"}`, " other", e.agent, e.slot)).join("");
  return me || them ? `<span class="pstates">${me}${them}</span>` : one("", "no session", "", "");
}
// The one notice a project carries (why nobody can start here, the agent
// out of window), in the notice voice, or nothing.
function projectNote(p, band = false){
  const here = withMe(p.name).length > 0;
  // What holds it back is said ahead of a wait that would end by itself
  // (B826: a copy going up was said and the missing Claude Code that really
  // held it never was).
  const held = p.held && !state?.mapping?.[p.name]?.running ? p.held : "";
  // Not this account's to change: nothing is said and Start agent is not
  // drawn (the operator, 21 Oct: a role somebody lacks is not advertised to
  // them, and a reason a button is off is not an error, so no line is red).
  if (!p.locked_me && writeWhy(p)) return "";
  // Your session running here and behind what changed since it started (a
  // toolchain on its node, AerieOS updated, a repository added): said
  // ahead of the rest, which are about starting one.
  const behind = !here ? [] : [...new Set(((state?.claude_where || {})[tmuxName(p.name)] || (state?.claude_where || {})[p.name] || [])
    .filter(r => r.who === state?.me).flatMap(r => r.behind || []))];
  // A band between the header and the view strip, put away with its x for
  // as long as it says the same (the operator, 28 Oct); what changed next
  // brings it back, and so does leaving the notebook and coming back to it
  // (the operator, 29 Oct). Every note the header carries is one (pnoteBand).
  if (behind.length){
    const text = `Restart your session to use what changed: ${behind.join("; ")}.`;
    return band ? pnoteBand(p, text) : `<div class="pnote warn">${esc(text)}</div>`;
  }
  // The project's agent missing on its node, for an account that may install
  // it: the button says it (Install Claude, Install ChatGPT), so no line does.
  if (agentInstall(p, projectAgent(p))) return "";
  const said = held || p.session_why;
  // An error where no session can run there and nothing passes by itself
  // (a node removed, disabled, off or hosting only); a warning where it is a
  // wait or a hold (the operator, 29 Oct: warnings yellow, errors red).
  const tone = held || p.session_waiting ? "warn" : "bad";
  if (said && !p.locked_me && !here) return band ? pnoteBand(p, said, tone) : `<div class="pnote dim">${esc(said)}</div>`;
  // ...and otherwise why Start agent is dead, whatever made it so (B88):
  // a Profile with no commit author, somebody else's node. A locked one
  // says so by its mark, and is left out.
  const dead = p.locked_me ? "" : claudeDeadWhy(p);
  return !dead ? "" : band ? pnoteBand(p, dead) : `<div class="pnote dim">${esc(dead)}</div>`;
}
// A note in the project's header as a band with its x (the operator, 28 and
// 29 Oct: every one, the way the restart band is), or "" while it is put away.
function pnoteBand(p, text, tone = "warn"){
  if (pnotePutAway(p.name) === text) return "";
  return `<div class="pnote ${tone === "bad" ? "bad" : "warn"} pband" data-pnote="${esc(p.name)}"><span class="grow">${esc(text)}</span><button type="button" class="ic" data-pnote-x aria-label="put this away">×</button></div>`;
}
// The node to install Claude Code on in place of starting a session, or "":
// the project's node has none and this account may install toolchains there
// (the operator, 21 Oct: the button opens that node's Toolchains).
const claudeInstall = p => !p.locked_me && !myLiveSession(p.name) && p.claude_missing
  && mayToolchains(p.claude_missing) ? p.claude_missing : "";
// ...and the same for any agent (R95 step 18): another agent is missing where
// the project's node does not list it among the agents installed there, the
// list Start's chooser offers from.
function agentInstall(p, ag){
  if (ag.id === "claude") return claudeInstall(p);
  const n = (p.session_nodes || []).find(x => x.id === p.session_node);
  return !p.locked_me && !myLiveSession(p.name) && n && n.where === "node"
    && !(n.agents || []).includes(ag.id) && mayToolchains(n.id) ? n.id : "";
}
// The agent a project's Start agent opens first: this account's pick for it,
// else Claude.
const projectAgent = p => agentById(p.prefs?.agent_default) || AGENTS[0];
// Why Start agent is dead on this project, or "" when it is live: the one
// answer the button, its description and the line under it all read.
function claudeDeadWhy(p){
  const mine = !!myLiveSession(p.name);
  if (p.locked_me) return lockedWhy(p);
  if (notMine(p)) return NOT_MINE_WHY;
  // A Claude session is work on the project (B86): Projects Write.
  if (p.write_why) return p.write_why;
  if (heldWhy(p)) return heldWhy(p);
  if (!p.session_at && p.session_why && !mine) return p.session_why;
  if (p.node_removed && !mine) return p.session_why || "its node was removed: pick another in its settings";
  return "";
}
// Why a lock holds this account out, as the server says it (R119).
const lockedWhy = p => p.locked_admin
  ? "locked by an administrator: nobody starts a session or changes it until one unlocks it"
  : `locked by ${p.owner_name || "its owner"}, its owner: only they work in it until they unlock it`;
// The lock's press in a menu: an administrator's says it is one (the
// operator, 23 Oct), since it holds the project's owner out too.
const lockLabel = p => {
  const asAdmin = p.locked ? p.locked_admin : !p.owner_mine;
  return (asAdmin ? "Admin: " : "") + (p.locked ? "Unlock" : "Lock");
};
// The agent's button, on a project's card and a repository's header: Start
// agent, Manage agent while this account's session runs, or Install where
// the project's agent is missing on its node. A project's one session runs
// on its first repository (R136), so every repository's opens that.
function agentButton(p){
  // The agent the project's Start opens (R95 step 4): Claude's unless its
  // settings name another. Its own session running here makes it Open.
  const ag = projectAgent(p);
  const rk = state?.repos?.[p.project];
  const name = p.name, at = rk?.members?.[0] || name, sess = myLiveSession(at), mine = !!sess;
  const dead = claudeDeadWhy(p);
  // What this account's roles do not give is left out, not drawn dead.
  if (isBroken(p) || (!p.locked_me && !!writeWhy(p))) return "";
  // What a press does, or why it is dead, in the button's own words: a
  // screen reader hears it, and a press on a dead one is told.
  const live = liveSessions();
  // Named for the agent it opens, whatever it says: the button's own word is
  // Start agent for every one of them.
  const said = dead ? dead
    : p.session_why ? p.session_why
    : othersOn(name).length ? `${othersOn(name).join(", ")} also working here, in a checkout of their own: start yours`
    : p.session_node && !agentOn(ag.id, p.session_node) && !live.has(myAgentSession(ag.id, name))
      ? `${ag.name}: you are not signed in on ${p.session_at}, this space's node. Press for its sign-in`
    : p.session_at ? `${ag.name}: a session on ${p.session_at}, this space's node`
    : mine ? `${agentOfSession(tmuxBase(sess))?.agent.name || ag.name}: your session is running; open its tab, restart or end it`
    : p.last_claude ? `${ag.name}: no session running; resume or start one`
    : `${ag.name}: start a session here`;
  const say = said.startsWith(`${ag.name}:`) ? said : `${ag.name}: ${said}`;
  // Green only while your session runs, and then Manage agent, since the
  // press opens the chooser with the session's Open, Restart and End;
  // otherwise a plain Start agent, the chooser under it picking which (the
  // operator, 16 Oct: green on every card read as running everywhere; 22
  // Oct: one word for every agent; 23 Oct: Manage agent, not Open Claude).
  const inst = agentInstall(p, ag);
  return inst ? `<button type="button" data-tcinst="${esc(inst)}" data-agent="${esc(ag.id)}" title="${
        esc(`${ag.product} is not installed on ${p.node_name || "its node"}: the Library installs it there`)}">Install ${esc(ag.name)}</button>`
    : `<button type="button"${mine ? ' class="primary"' : ""} data-c="${esc(at)}"${dead ? " disabled" : ""} title="${esc(say)}">${
        mine ? "Manage agent" : "Start agent"}</button>`;
}
// A repository's header: the agent, a shell, and the rest behind one menu
// (R238: nine look-alike icons on a row were one too many). Its data-*
// names are wireProjectRows', which serves them; the marks act on its
// project.
function projectActions(p){
  const name = p.name, key = p.project || name, c = state?.repos?.[key] || p;
  const menu = [
    p.git_ok && !isBroken(p) && state?.can?.["git-auth"] !== false
      ? `<button type="button" data-l="${esc(name)}">${
          p.linked ? `${esc(p.forge_name || "Remote")} settings` : "Link to a git host"}</button>` : "",
    p.phone?.mine ? `<button type="button" data-ph="${esc(name)}"${phoneWhy(p) ? " disabled" : ""}>${
        p.phone?.lease?.project === name ? "Take your phone back" : "Lend your phone"}</button>` : "",
    p.mine === false ? "" : `<button type="button" data-bug="${esc(name)}">Report an AerieOS bug</button>`,
    // Archive is out of sight only (R119, the operator, 23 Oct): its card
    // folds away at the foot of the Projects page and leaves Home, and the
    // project works on. Its owner's or an administrator's.
    c.may_archive ? `<button type="button" data-k="${esc(key)}" data-on="${c.archived ? "0" : "1"}">${c.archived ? "Unarchive" : "Archive"}</button>` : "",
    // ...and Lock, which is: its owner's holds everybody else out, an
    // administrator's its owner too, and says so on the press.
    c.may_lock ? `<button type="button" data-lock="${esc(key)}" data-on="${c.locked ? "0" : "1"}">${lockLabel(c)}</button>` : "",
    `<button type="button" data-p="${esc(key)}" data-on="${c.pinned ? "0" : "1"}">${c.pinned ? "Remove from favorites" : "Add to favorites"}</button>`,
    `<button type="button" data-rn="${esc(name)}">Settings</button>`,
  ].filter(Boolean).join("");
  return `${agentButton(p)}
    ${mayShell() && !notMine(p) ? `<button type="button" data-s="${esc(name)}"${!gitReadyFor(p) ? " disabled" : ""}>Shell</button>` : ""}
    <span class="more"><button type="button" data-pmore aria-label="more" aria-expanded="false">${DOTS}</button><div class="actmenu" hidden>${menu}</div></span>`;
}
function projectHeader(t){
  const name = t.arg, p = (state?.projects || []).find(x => x.name === name);
  if (!p) return `<div class="phead"><span class="pname">${esc(projLabel(name))}</span></div>`;
  // A repository of a project of several (R136): the project's name, and
  // its repositories as a pulldown, this one picked, each opening its own
  // notebook (the operator, 27 Oct: a switch of buttons is no way to hold a
  // list that may be long), in the project's color as its buttons are.
  const rk = state?.repos?.[p.project];
  const repoSwitch = rk?.members.length > 1 ? `<select class="prepos" data-reposw aria-label="${esc(rk.name)}'s repositories: the one this notebook is">${
    optionList(rk.members.map(m => [m, projLabel(m)]), name)}</select>` : "";
  return `<div class="phead">
    <span class="pname">${esc(rk ? rk.name : p.label || name)}${lockMark(p)}</span>${repoSwitch}
    <span class="pfacts">${projFacts(p)}</span>
    ${projectState(p)}
    <span class="sp"></span>
    ${projectActions(p)}
  </div>${projNotes(p, true)}`;
}
// The row's handlers serve the header too (the same data-* names); the
// menu's own button is the one thing the row did differently.
// The header's band put away, by project: the text it had, for this visit
// to the notebook alone (the operator, 29 Oct: it comes back once you fully
// leave the notebook and return). A view of the same notebook is the same
// visit; another page, another project or a reload is not.
const pnoteAway = {};
let pnoteHere = "";
function pnotePutAway(name, text){
  if (text !== undefined) pnoteAway[name] = text;
  return pnoteAway[name] || "";
}
// The project the front pane is on, told on every draw of its bar: leaving
// one forgets what was put away there.
function pnoteOnShow(name){
  if (name === pnoteHere) return;
  if (pnoteHere) delete pnoteAway[pnoteHere];
  pnoteHere = name;
}
function wireProjectHeader(bar){
  wireProjectRows(bar);
  bar.querySelectorAll("[data-pnote-x]").forEach(b => b.onclick = () => {
    const band = b.closest("[data-pnote]");
    pnotePutAway(band.dataset.pnote, band.querySelector(".grow")?.textContent || "");
    band.remove();
  });
  bar.querySelectorAll("select[data-reposw]").forEach(s => s.onchange = () => openNotebook(s.value));
  // On the project's own page its menu's Settings is the notebook's Settings
  // view (R259: the view strip carries no tab for it), not the dialog. Only
  // there: a card on the Projects page keeps wireProjectRows' Settings, which
  // goes to the page (B82: this one turned the notebook in the background).
  bar.querySelectorAll("[data-rn]").forEach(b => b.onclick = () => {
    const n = getNotebook(b.dataset.rn);
    if (n) n.view("settings"); else openProjectSettings(b.dataset.rn);
  });
  wireProjectMenu(bar);
}
// The other repositories of a project of several (R136), under one
// repository's own list: their open roadmap items or open bugs, merged,
// each row naming its repository and opening its view there. Read-only
// here, as each repository's list is its own to change.
async function reposAlso(el, project, kind){
  if (!el) return;
  const r = state?.repos?.[(state?.projects || []).find(p => p.name === project)?.project];
  if (!r || r.members.length < 2){ el.hidden = true; el.innerHTML = ""; return; }
  const rows = [];
  for (const m of r.members.filter(m => m !== project)){
    try{
      const j = await getJSON(`/api/${kind}?project=${encodeURIComponent(m)}`);
      const list = kind === "bugs" ? (j.bugs || []).filter(b => b.status === "open") : (j.items || []);
      for (const x of list) rows.push({m, id: x.id, text: x.title || x.text || ""});
    }catch(e){ /* that repository's list answers on its own page */ }
  }
  const tag = kind === "bugs" ? "B" : "R", noun = kind === "bugs" ? "open bug" : "open item";
  const body = rows.length ? rows.map(x => `<div class="alsorow">
      <button type="button" class="namelink" data-also="${esc(x.m)}">${esc(projLabel(x.m))}</button>
      <span class="pid">${tag}${x.id}</span><span class="alsotext">${esc(x.text)}</span></div>`).join("")
    : `<div class="empty">nothing open in its other repositories</div>`;
  const html = docSection(kind, "also", `Also in ${r.name}`, `${rows.length} ${noun}${rows.length === 1 ? "" : "s"}`, body, {open: true});
  if (patch(el, html)){
    wireSections(el);
    el.querySelectorAll("[data-also]").forEach(b => b.onclick = () => openNotebook(b.dataset.also, kind === "bugs" ? "bugs" : "roadmap"));
  }
  el.hidden = false;
}

// A project's ⋯, on its header and on its card alike.
function wireProjectMenu(bar){
  bar.querySelectorAll("[data-pmore]").forEach(b => b.onclick = e => {
    e.stopPropagation();
    const m = b.nextElementSibling, open = m.hidden;
    closeMore();
    m.hidden = !open;
    b.setAttribute("aria-expanded", open ? "true" : "false");
    if (open) floatAt(m, b);
  });
}

// A project's lock, said one way on its card, its page's header and Home
// (consistency batch J: the header said locked where the card said
// archived): locked when its owner or an administrator locked it (R119),
// whomever it holds out, read-only when it is not this account's to change
// (not taken on, or a role that reads it alone). Archived is said by where
// the card sits, not by a mark.
function lockMark(p){
  const said = p.locked ? (p.locked_admin ? "locked by an administrator" : "locked") : writeWhy(p) ? "read-only" : "";
  return said ? ` <span class="lockmark" title="${esc(p.locked ? lockedWhy(p) : said)}">${LOCK}${said}</span>` : "";
}
// A project's facts line, the same parts wherever it is drawn: its id, its
// branch, that it may push, and the node it runs on.
function projFacts(p){
  return [pidMark(projId(p)), repoFacts(p), esc(p.node_name || p.session_at || "")].filter(Boolean).join(" · ");
}
