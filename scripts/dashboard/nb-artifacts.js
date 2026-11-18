// The notebook's Artifacts view and the version block in its head: what the
// project built, the dev instance, the version, the changelog. One classic
// script beside index.html (docs/nodes.md §13): one file per notebook view
// (R60). A factory makeNotebook calls per notebook.

"use strict";
// The view's sections by the titles they are drawn under, read by the view
// and by its placeholders (page-docs.js SKTPLS: artifacts, version) alike
// (R218, the operator 18 Oct).
const ART_TITLES = {build: "Build", files: "Files", version: "Version"};
const artTitle = k => ART_TITLES[k] || k;

// A staged bump that moves the compatibility window: minor and major do,
// patch does not, and only where this project owns the window at all.
const windowMove = (part, cost) =>
  (part === "minor" || part === "major") && (cost?.projects || []).length > 0;

// The changelog's released text with each roadmap item and bug it names a
// link to that row (R254 step 4): escaped first, then R12 and B34 wrapped.
function clLinks(text){
  return esc(text).replace(/(^|[^\w-])([RB])(\d{1,5})(?![\w-])/g,
    (m, pre, k, n) => `${pre}<a href="#" data-clref="${k}${n}" title="open ${k === "R" ? "roadmap item" : "bug"} ${k}${n}">${k}${n}</a>`);
}

// The view: what makeNotebook hands it and its state (the artifacts read
// and its poll, the version read, what is staged on it) on one object,
// `av`, which each function below that reads or changes them takes first;
// the ones that only build markup take plain values. What it returns is
// what the notebook calls by name.
function nbArtifactsView({$, nb, project, root, sheet}){
  const av = {$, nb, project, root,
    // What this project has built. Fetched on open like Analysis, and polled
    // only while a push is live: the one time it changes on its own.
    art: null, artTimer: null,
    // The file rows opened to their provenance, by path, across redraws.
    artOpen: new Set(),
    ver: null,
    // A bump is staged, not written. Pressing Patch/Minor/Major only records
    // the intent: Save commits it, Revert and leaving the tab throw it away.
    // Everything else in this notebook works that way, and a bump is the one
    // control here that reaches outside the panel: a misclicked "Major → 1.0.0"
    // used to be a commit before the finger left the button.
    // {component -> part}, "" being the project's own.
    verPending: {},
    verPolicyPending: null};   // a picked policy, until Save writes it

  // This notebook's own filter state, so two notebooks in a split do not
  // share a search box's contents.

  return {loadArtifacts: kept => nbArtLoad(av, kept), loadVersion: () => nbArtLoadVersion(av),
          drawVersion: () => nbArtDrawVersion(av), postArtifacts: body => nbArtPost(av, body),
          postVersion: (body, quiet) => nbArtPostVersion(av, body, quiet)};
}

// ---- artifacts -----------------------------------------------------------

// Sizes as a person reads them; the bytes are nobody's unit.
function nbArtHuman(n){
  return n >= 1 << 30 ? (n / (1 << 30)).toFixed(1) + " GB"
       : n >= 1 << 20 ? (n / (1 << 20)).toFixed(1) + " MB"
       : n >= 1 << 10 ? Math.round(n / (1 << 10)) + " KB"
       : n + " B";
}

// `kept`: drawn again from the read in hand, which is what Show more
// asks (R228 step 13), rather than read again.
function nbArtLoad(av, kept){
  const {$, project} = av;
  return reading(`${project}:artifacts`, async () => {
    const hint = $("artHint"), list = $("artList");
    if (!(kept === true && av.art)) try{
      av.art = await getJSON("/api/artifacts?project=" + encodeURIComponent(project));
    }catch(e){ viewGlance(hint, [], esc("artifacts: " + e), "", "bad"); return; }
    const art = av.art;
    if (art.error){ viewGlance(hint, [], esc("artifacts: " + art.error), "", "bad"); return; }
    const rows = art.artifacts || [], job = art.push || {}, dev = art.phone;
    const groups = art.branches || [];
    // The code base itself, as a zip through the browser: a navigation, so
    // the browser's own download handles it, cookie and all.
    const src = $("artSource");
    if (src) src.onclick = () => { location.href = "/api/source?project=" + encodeURIComponent(project); };
    // Why Push and Install are ghosted, when they are: the phone is on the
    // project's node and belongs to whoever connected it there.
    const phoneWhy = !dev ? "no phone is connected on this space's node: connect one in the Phone page, on its node"
      : !art.mine ? `connected by ${art.owner?.name || "somebody else"}: only they can push to it or install on it`
      : "";
    const inst = art.install || {};
    const caps = art.captures || [], onBranches = groups.reduce((n, g) => n + (g.artifacts || []).length, 0);
    nbArtGlance(hint, art, rows, caps, onBranches);
    nbArtBuildSection(av, art);
    const cf = art.compose_files || {files: []};
    const cfFiles = cf.files || [];
    const devHtml = nbArtDockerRows(cf, cfFiles);
    const jobHtml = nbArtPushRow(project, job);
    const instHtml = nbArtInstallRow(inst);
    const devNote = nbArtDevNote(art, rows);
    // Sections like the rest of the view (the operator, 6 Oct): the files
    // were a band of their own under Version, the one part of the tab that
    // did not fold, and a long list pushed Captures off the screen. The dev
    // instance is its own; the files are the one a person opens this view
    // for, so the one left open when nobody has chosen.
    // A role that reads the project and does not write it (B101): no
    // Install, Push, Remove or pin on a file, no Sign without Releases and versions
    // Write; nothing says why (the operator, 21 Oct: what a role does not
    // give is not advertised).
    const ro = projWriteWhy(project), relWhy = projReleaseWhy(project);
    // Only the files on show are built, a page at a time (pageLimit, R228
    // step 13); each row is named by its place in `rows`, which a page from
    // the top keeps.
    const artLim = pageLimit(list, "artList", rows.length);
    const apks = !ro && rows.some(a => a.kind === "apk"), xpis = !ro && rows.some(a => a.kind === "xpi");
    const deadSaid = [
      (apks || xpis) && phoneWhy ? `${apks && xpis ? "Install and Push" : apks ? "Install" : "Push"} cannot go: ${phoneWhy}.` : "",
      xpis && !phoneWhy && !art.webext ? `Push cannot go: web-ext is not on ${art.node_name || "the node"}; install it there first.` : "",
    ].filter(Boolean).map(t => `<div class="hint artwhy">${esc(t)}</div>`).join("");
    const filesBody = !rows.length
      ? `<div class="hint">Nothing in <b>dist/</b> yet: a build copies what it keeps there.</div>`
      : devNote + deadSaid + jobHtml + instHtml + rows.slice(0, artLim).map((a, i) => nbArtFileRow(project, art, a, i, {ro, relWhy, inst, job, phoneWhy,
          open: av.artOpen.has(a.path)})).join("");
    // Patched (R244): a field or a fold in the list stays as the person left
    // it when a build lands or the dev instance moves.
    patch(list, (devHtml ? docSection("artifacts", "dev", "Docker",
                                            cf.available === false ? "unreachable"
                                            : `${cfFiles.length} compose file${cfFiles.length === 1 ? "" : "s"}`, devHtml) : "")
      + docSection("artifacts", "files", artTitle("files"), rows.length ? `${rows.length} in dist/` : "none yet", filesBody, {prime: true}));
    wireSections(list);
    paginate(list.querySelector('[data-sect="artifacts:files"] > .body'), ":scope > .artrow",
             {key: "artList", noun: "files", total: rows.length, more: () => nbArtLoad(av, true)});
    nbArtCaptures(av, art, caps);
    nbArtBranches(av, groups);
    if (!tcDotsTimer && list.querySelector(".dots"))
      tcDotsTimer = setInterval(tcTickDots, 400);
    nbArtWireList(av, list, rows, cf, cfFiles);
    nbArtPoll(av, job, inst);
  });
}

// The glance (R109): what this project ships, in dist/, and its size;
// what was built on a branch, in each account's worktree; and the
// captures sessions looked with, kept apart from both.
function nbArtGlance(hint, art, rows, caps, onBranches){
  viewGlance(hint, [
    {label: "in dist/", value: rows.length, sub: rows.length ? humanBytes(rows.reduce((n, a) => n + (a.size || 0), 0)) : ""},
    {label: "built on branches", value: onBranches, omit: !onBranches},
    {label: caps.length === 1 ? "capture" : "captures", value: caps.length, omit: !caps.length},
    // The room the last build used on its node, workspace and cache (R110
    // step 7), which the next one is checked against. Said as room: "last
    // build took 2kB" read as a time; a label short enough for a phone's
    // tile, the build it was under it.
    {label: "build room", value: humanBytes(art.build?.took?.workspace || 0),
     sub: art.build?.took?.cache ? `the last build's, cache ${humanBytes(art.build.took.cache)}` : "the last build's", omit: !art.build?.took?.workspace}],
    // Its status line, on the control row beside Download source (the
    // operator, 29 Oct: never a button alone on its line).
    "the code base as a zip, without build output");
}

// Where this project compiles, as a section rather than a loose band:
// this tab is three subjects stacked, where it builds, what it is
// called, and what it shipped, and on a phone they arrived as one
// scroll with nothing naming any of them. The status is the answer on
// its own, so a shut section still says which node.
function nbArtBuildSection(av, art){
  const {$} = av;
  const b = art.build || {};
  const el = $("artBuild");
  if (el){
    el.hidden = false;
    el.className = "";
    patch(el, docSection("artifacts", "build", artTitle("build"),
      b.node ? (b.gap ? "agent behind" : b.name) : "no node",
      b.node && b.gap
        ? `<div class="hint bad">Nothing runs on <b>${esc(b.name)}</b> until its agent is
                 updated: ${esc(b.gap)}</div>`
        : b.node
        ? `<div class="hint">Builds run on <b>${esc(b.name)}</b>${b.tools?.length
                  ? `; it carries ${b.tools.map(esc).join(", ")}`
                  : "; it reports no toolchains yet, so a compile will not find one"}.
                 ${railAllows("library") ? `Add to it from the ${pageLink("library", "Library")}.`
                   // Not offered a page their grants keep them from (B114).
                   : "An account that may open the Library adds to it there."}</div>`
        : `<div class="hint">No node: nothing can be compiled for this space here.
                 ${esc(b.why || "")}</div>`,
      {cls: b.node ? (b.gap ? "bad" : "") : "warn"}));
    wireSections(el);
  }
}

// Sending to Docker: a row a compose file in the repository, each with
// its own Send, which makes a new container from that file on the Docker
// tab, as many as are wanted under as many names (the operator, 10 Oct).
// Nothing here follows a container once it is made: whether it is up,
// built, or answering is the Docker tab's, and a row here that said
// "down" read as a second place to run it. What a row says is about the
// FILE: what will not work as written, what reaches beyond its folder,
// a port already taken on the node.
function nbArtDockerRows(cf, cfFiles){
  const devLines = (label, items, cls) => !items?.length ? "" :
    `<div class="dim ${cls}">${label}</div>`
    + items.map(x => `<div class="dim ${cls} li">${esc(x)}</div>`).join("");
  const rowFor = (c, i) => `
        <div class="artrow"${i ? ` data-devrow="${i}"` : ' id="devRow"'}>
          <div class="grow">
            <div class="top"><span class="pill">docker</span>
              <b>${esc(c.path)}</b></div>
            ${devLines("will not work as written", c.problems, "bad")}${
            // Variables the file requires: its env's to set once it is sent
            // (the Docker tab's Env), not a fault, so the quiet voice.
            c.needs?.length ? `<div class="dim li">needs ${esc(c.needs.join(", "))} set in its env before it starts</div>` : ""}
            ${devLines("asks for more than its own directory", c.risks, "risk")}${
            // A port another container holds is not a fault in the file: the
            // container Send makes gets an env of its own, and the port goes in
            // it. So a note, in the quiet voice, not a verdict in red.
            c.port_clash?.length ? `<div class="dim li">port ${esc(c.port_clash.join(", "))} ${
              c.port_clash.length === 1 ? "is" : "are"} already published on this node</div>` : ""}
          </div>
          <span class="acts">
            <button type="button" data-devsend="${i}"${i ? "" : ' id="devSend"'} class="primary"
              title="make a new container from ${esc(c.path)} and manage it on the Containers page"
              >Send to Docker manager</button>
          </span>
        </div>`;
  return !cfFiles.length ? "" : !cf.available ? `
        <div class="artrow job"><span class="pill">docker</span>
          <span class="grow">${esc(cf.why || "docker is not reachable")}${
            // The machine it asked: a project's containers live on its own
            // node, and the refusal is about that one.
            cf.daemon || cf.where ? ` <span class="dim">(${esc(cf.daemon || cf.where)})</span>` : ""}</span>
        </div>` + cfFiles.map(rowFor).join("") : cfFiles.map(rowFor).join("");
}

// The push session, as a row: live once web-ext says the add-on is on
// the phone, with Stop, which is how the session ends.
function nbArtPushRow(project, job){
  return job.running || (job.state === "stopped" && job.error) ? `
        <div class="artrow job">
          <span class="pill ${job.state === "running" ? "ok" : job.error ? "bad" : "go"}">${
            job.state === "running" ? "live" : job.error ? "stopped" : "starting"}${
            job.running && job.state !== "running" ? `<span class="dots"></span>` : ""}</span>
          <span class="grow">${esc(job.what)}${job.error ? `: ${esc(job.error)}`
            : `: temporary, gone when Firefox restarts; changes do <b>not</b>
            push themselves, so rebuild the .xpi and push again.`}</span>
          ${job.running && !projWriteWhy(project) ? `<button type="button" id="artStop">Stop</button>` : ""}
        </div>` : "";
}

// An install is one shot rather than a session, so it reports its own
// line: what it is doing, and what went wrong in words when it does.
function nbArtInstallRow(inst){
  return inst.running || inst.state === "failed" ? `
        <div class="artrow job">
          <span class="pill ${inst.state === "failed" ? "bad" : "go"}">${
            inst.state === "failed" ? "failed" : "installing"}${
            inst.running ? `<span class="dots"></span>` : ""}</span>
          <span class="grow">${esc(inst.what)}${
            inst.error ? `: ${esc(inst.error)}` : ""}</span>
        </div>` : "";
}

// Dev builds go on their own past the newest few of each (R105): said
// once, over the list, where there are any.
function nbArtDevNote(art, rows){
  const keep = art.dev_keep ?? 3;
  return rows.some(a => /\d+\.\d+\.\d+-dev\.\d+-[0-9a-f]{7}/.test(a.name))
    ? `<div class="hint dim">${keep
            ? `Each product keeps its newest ${keep} builds; a release and anything pinned stay${
                helpIcon("The space's settings say how many (Dev builds kept). A signed build counts by its signed copy alone, and older ones are removed as new ones arrive.")}`
            : "Every dev build is kept: this space's settings say so (Dev builds kept)."}</div>` : "";
}

// One file in dist/ as its row: what it is, what built and signed it, and
// what this account may do with it.
// One line closed: what it is, its size and age, and the two presses it is
// most often for (Download, and Install, Push or View), the rest behind its
// More. A press on the line opens it to what is long and read now and then:
// where it sits, who pinned it, what built it and what signed it, with its
// certificate's fingerprint. What is acted on stays on the line: a build
// named with no version. Why Install or Push cannot go is the same for
// every row, so it is said once over them (nbArtLoad).
function nbArtFileRow(project, art, a, i, {ro, relWhy, inst, job, phoneWhy, open}){
  const install = a.kind === "apk" && !ro ? `<button type="button" data-artinstall="${i}"${
      inst.running || phoneWhy ? " disabled" : ""} title="${
      phoneWhy ? esc(phoneWhy)
      : inst.running ? "one install at a time"
      : "install it on the phone, replacing any copy already there"
      }">Install</button>` : "";
  const push = a.kind === "xpi" && !ro ? `<button type="button" data-artpush="${i}"${
      job.running || phoneWhy || !art.webext ? " disabled" : ""} title="${
      phoneWhy ? esc(phoneWhy)
      : !art.webext ? `web-ext is not on ${esc(art.node_name || "the node")}: install it there first`
      : job.running ? "one push at a time"
      : "install it on the phone, temporarily"}">Push</button>` : "";
  const view = a.view ? `<button type="button" data-artview="${i}"
      title="read it here, without downloading it">View</button>` : "";
  const signs = (a.kind === "apk" || a.kind === "aab") && !relWhy && !/-signed\.(apk|aab)$/.test(a.name)
    ? (art.sign_routes || []).map(r => `<button type="button" data-artsign="${i}" data-route="${r}"
      title="sign it on the space's node with its ${r === "play" ? "Play upload key" : "sideload signing key"}; it arrives beside it as -signed">Sign${
        (art.sign_routes || []).length > 1 ? (r === "play" ? " for Play" : " to sideload") : ""}</button>`) : [];
  const remove = a.unversioned && !ro ? `<button type="button" class="danger" data-artunnamed="${i}"
      title="remove it from dist/ now, for everybody">Remove</button>` : "";
  const first = install || push || view;
  const rest = [install, push, view].filter(b => b && b !== first).concat(signs, remove ? [remove] : []);
  // What it opens to: each line said once, under the closed one.
  const prov = [
    a.path !== a.name ? `<span class="dim">in ${esc(a.path)}</span>` : "",
    a.pinned && a.pinned_by ? `<span class="dim">pinned by ${esc(a.pinned_by)}</span>` : "",
    // What built it, when a job did: the job, the node, the snapshot. A
    // file somebody copied in says nothing.
    a.prov ? `<span class="dim">built by ${esc(a.prov.job)} on ${
      esc((nodesList || []).find(n => n.id === a.prov.node)?.name || a.prov.node || "?")}${
      a.prov.source?.digest ? ` from snapshot ${esc(a.prov.source.digest.slice(7, 19))}` : ""}${
      a.prov.sha256 ? ` · sha256 ${esc(a.prov.sha256.slice(0, 12))}` : ""}</span>` : "",
    // What signed it: the key, what verified, and the certificate's whole
    // fingerprint, which a store's metadata asks for (F-Droid's
    // AllowedAPKSigningKeys) and a person compares.
    a.prov?.signed ? `<span class="dim">signed with the ${
      a.prov.signed.key && a.prov.signed.key !== "default" ? `${esc(a.prov.signed.key)} key's ` : ""}${
      a.prov.signed.route === "play" ? "Play upload key" : "sideload signing key"}${
      a.prov.signed.from ? ` from ${esc(a.prov.signed.from)}` : ""}${
      a.prov.signed.schemes?.length ? `, verified ${esc(a.prov.signed.schemes.join(", "))}` : ""}${
      a.prov.signed.rotated_from ? `, rotated from ${esc(a.prov.signed.rotated_from)}: Android 8.1 and older still see ${esc(a.prov.signed.rotated_from)}` : ""}</span>
      <span class="artfp">SHA-256 ${esc(a.prov.signed.cert.match(/../g).join(":"))}
        <button type="button" class="link" data-artfp="${i}" title="the fingerprint as F-Droid's AllowedAPKSigningKeys takes it: lowercase, no colons">Copy for F-Droid</button></span>` : "",
  ].filter(Boolean).join("");
  return `
          <div class="artrow artfile${prov ? " opens" : ""}${prov && open ? " open" : ""}" data-artpath="${esc(a.path)}"${
            prov ? ` aria-expanded="${!!open}"` : ""}>
            <span class="grow">
              <span class="top">${prov ? `<span class="artcaret" aria-hidden="true">${open ? "\u25BE" : "\u25B8"}</span>` : ""}<span class="pill">${esc(a.kind)}</span>
                <b>${esc(a.name)}</b>${a.pinned ? ` <span class="pill on">pinned</span>` : ""}${
                a.prov?.signed ? ` <span class="pill ok">signed</span>` : ""}
                <span class="dim">${esc(nbArtHuman(a.size))} · ${esc(ago(a.at))}</span></span>${
              // A build named with no version (the operator, 6 Oct): the
              // sweep cannot tell when it is out of date, so it says so, in
              // the warning color, and offers Remove.
              a.unversioned ? `<span class="vermark">named with no version, so nothing can tell when it is out of date: name builds with aerie version --file</span>` : ""}${
              prov ? `<span class="artprov"${open ? "" : " hidden"}>${prov}</span>` : ""}</span>
            <span class="acts">
              ${first}
              <a class="btn" href="/api/artifact?project=${encodeURIComponent(project)
                }&path=${encodeURIComponent(a.path)}" download>Download</a>
              ${actMore(rest, true)}${ro ? "" : `
              <button type="button" class="eye pin${a.pinned ? " on" : ""}" data-artpin="${i}"
                aria-label="${a.pinned ? "unpin" : "pin"}" title="${a.pinned
                  ? "unpin: it goes like any other build when newer ones arrive"
                  : "pin: keep it, whatever builds come after it"}">${TACK}</button>`}
            </span>
          </div>`;
}

// What a session looked with (R96): a reel's sheet, an emulator shot.
// One fold apart from the files, since they are not what ships, each
// row saying whose it is and when. They go by age (the project's
// "captures kept" days, swept by the server on this read) or by Remove
// here: never by need, because nothing can tell whether another
// session is still reading one. Hidden when there are none: nothing to
// act on.
function nbArtCaptures(av, art, caps){
  const {$, project} = av;
  const capBox = $("artCaptures");
  if (capBox){
    capBox.hidden = !caps.length;
    const days = art.capture_days ?? 7;
    patch(capBox, !caps.length ? "" : docSection("artifacts", "captures", "Captures",
      `${caps.length}, kept ${days ? `${days} day${days === 1 ? "" : "s"}` : "until removed"}`,
      `<div class="hint">What a session looked with: a reel's sheet (<b>aerie capture reel</b>) or an
             emulator shot, not what the space ships. ${days
               ? `Each is removed ${days} day${days === 1 ? "" : "s"} after it was taken`
               : "Kept until somebody removes one"}; the space's settings say how long.</div>`
      + caps.map((c, i) => `
          <div class="artrow">
            <span class="grow">
              <span class="top"><span class="pill">${esc(c.kind)}</span> <b>${esc(c.name)}</b></span>
              <span class="dim">${esc(c.by ? `by ${c.by}` : "by nobody known")} · ${esc(ago(c.at))} · ${esc(nbArtHuman(c.size))}${
                c.kind === "reel" ? ` · ${c.frames} frame${c.frames === 1 ? "" : "s"}` : ""}</span></span>
            <span class="acts">
              <a class="btn" href="/api/artifact?project=${encodeURIComponent(project)
                }&path=${encodeURIComponent(c.path)}" download>Download</a>
              ${projWriteWhy(project) ? "" : `<button type="button" class="danger" data-artcap="${i}" title="remove it from dist/ now, for everybody">Remove</button>`}
            </span>
          </div>`).join("")));
    wireSections(capBox);
    capBox.querySelectorAll("[data-artcap]").forEach(b => b.onclick = async () => {
      const c = caps[+b.dataset.artcap];
      if (!c) return;
      busy(b, "Removing");
      try{
        const j = await postJSON("/api/artifacts", {project, action: "forget-capture", name: c.name});
        if (j.error) return notify(j.error, true);
      }catch(e){ return notify(String(e), true); }
      nbArtLoad(av);
    });
  }
}

// Builds made on a branch, in each account's worktree (B237): Download
// and View, carrying the tree. Install and Push stay with dist/, whose
// files the phone's node is sent by their path in the project.
function nbArtBranches(av, groups){
  const {$, nb, project} = av;
  const brList = $("artBranches");
  const brRows = groups.flatMap(g => g.artifacts.map(a => ({...a, tree: g.uid})));
  if (brList){
    brList.hidden = !brRows.length;
    let at = 0;
    // A page at a time too, numbered across the groups (R228 step 13): a
    // group with nothing on the page leaves its heading out.
    const brLim = pageLimit(brList, "artBranches", brRows.length);
    patch(brList, !brRows.length ? "" : docSection("artifacts", "branches", "Branch builds", String(brRows.length),
      `<div class="hint">Built on a branch. Merge it to main to put its build in dist/.</div>`
      + groups.map(g => at >= brLim ? "" : `<div class="sub dim ggroup">${esc(g.who === state?.me ? "your" : `${g.who}'s`)} branch builds${
              g.branch ? `, on ${esc(g.branch)}` : ""}</div>` + g.artifacts.map(a => { const i = at++; if (i >= brLim) return ""; return `
            <div class="artrow">
              <span class="grow">
                <span class="top"><span class="pill">${esc(a.kind)}</span> <b>${esc(a.name)}</b></span>
                <span class="dim">${esc(nbArtHuman(a.size))} · ${esc(ago(a.at))}</span></span>
              <span class="acts">
                ${a.view ? `<button type="button" data-artbview="${i}"
                    title="read it here, without downloading it">View</button>` : ""}
                <a class="btn" href="/api/artifact?project=${encodeURIComponent(project)
                  }&path=${encodeURIComponent(a.path)}&tree=${encodeURIComponent(g.uid)}" download>Download</a>
              </span>
            </div>`; }).join("")).join("")));
    if (brRows.length){
      wireSections(brList);
      paginate(brList.querySelector('[data-sect="artifacts:branches"] > .body'), ":scope > .artrow",
               {key: "artBranches", noun: "files", total: brRows.length, more: () => nbArtLoad(av, true)});
    }
    brList.querySelectorAll("[data-artbview]").forEach(b => b.onclick = async () => {
      const a = brRows[Number(b.dataset.artbview)];
      const pane = document.createElement("div");
      pane.className = "verlogpane";
      nb.openSheet(a.name, [pane]);
      drawHTML(pane, `${skel("rows", 4)}`);
      try{
        const r = await fetch(`/api/artifact?project=${encodeURIComponent(project)
                                  }&path=${encodeURIComponent(a.path)}&tree=${encodeURIComponent(a.tree)}`);
        pane.textContent = r.ok ? await r.text() : `could not read ${a.name}`;
      }catch(e){ pane.textContent = String(e); }
    });
  }
}

// The buttons on the list's rows, each bound to the row it was drawn for,
// and Stop on the push row.
function nbArtWireList(av, list, rows, cf, cfFiles){
  const {$, nb, project} = av;
  list.querySelectorAll(".artfile.opens").forEach(r => r.onclick = e => {
    if (e.target.closest("button, a, input, select, .more, .artfp")) return;
    const path = r.dataset.artpath, open = !av.artOpen.has(path);
    if (open) av.artOpen.add(path); else av.artOpen.delete(path);
    r.classList.toggle("open", open);
    r.setAttribute("aria-expanded", String(open));
    setText(r.querySelector(".artcaret"), open ? "\u25BE" : "\u25B8");
    setHidden(r.querySelector(".artprov"), !open);
  });
  wireMore(list);
  list.querySelectorAll("[data-devsend]").forEach(b => b.onclick = () => {
    const c = cfFiles[+b.dataset.devsend] || {};
    openSendToDocker(project, c.send_as || av.art.send_as, av.art.containers || 0, c.path || "");
  });
  // THIS project's daemon, which is its node's and need not be the default
  // one the poll asked about. The row above already draws the reason when
  // there is one, so what is passed here is the same answer the row is
  // wearing rather than a second opinion about another machine.
  gateDocker(list, !cfFiles.length || cf.available ? "" : (cf.why || "docker is not reachable"));
  list.querySelectorAll("[data-artpush]").forEach(b => b.onclick = async () => {
    const a = rows[Number(b.dataset.artpush)];
    busy(b, "Pushing");
    await nbArtPost(av, {action: "push", path: a.path,
                         apk: (av.art.apks || [])[0] || ""});
  });
  list.querySelectorAll("[data-artinstall]").forEach(b => b.onclick = async () => {
    const a = rows[Number(b.dataset.artinstall)];
    busy(b, "Installing");
    await nbArtPost(av, {action: "install", path: a.path});
  });
  // A shipped script is a thing people read before they run it, and on a
  // phone a download is the end of that. Over the panel like a History, the
  // text as it is; nothing here runs it, and the tab has no way to.
  // Sign (R106): a job on the project's node with the project's key,
  // which never comes near the page either; the signed build arrives in
  // dist/ beside this one, and the list picks it up when it lands.
  list.querySelectorAll("[data-artsign]").forEach(b => b.onclick = async () => {
    const a = rows[+b.dataset.artsign];
    if (!a) return;
    b.disabled = true;
    const j = await postJSON("/api/signing", {action: "sign", project, file: a.path,
                                                     route: b.dataset.route});
    if (j.error){ b.disabled = false; return notify(j.error, true); }
    notify(`signing ${a.name} on the node: it arrives here as ${a.name.replace(/(-unsigned)?\.(apk|aab)$/, "-signed.$2")}`);
  });
  list.querySelectorAll("[data-artfp]").forEach(b => b.onclick = async () => {
    const a = rows[+b.dataset.artfp];
    const fp = String(a?.prov?.signed?.cert || "").toLowerCase();
    try{ await navigator.clipboard.writeText(fp); notify(`copied ${a.name}'s signing fingerprint`); }
    catch(e){ notify(`copy it by hand: ${fp}`, "warn"); }
  });
  list.querySelectorAll("[data-artunnamed]").forEach(b => b.onclick = async () => {
    const a = rows[+b.dataset.artunnamed];
    if (!a || !await askYes(`Remove ${a.name} from dist/?\n\nIt is gone for everybody.`)) return;
    b.disabled = true;
    try{
      const j = await postJSON("/api/artifacts", {project, action: "forget-unnamed", path: a.path});
      if (j.error){ b.disabled = false; return notify(j.error, true); }
      notify(`removed ${a.name}`);
    }catch(e){ b.disabled = false; return notify(String(e), true); }
    nbArtLoad(av);
  });
  list.querySelectorAll("[data-artpin]").forEach(b => b.onclick = async () => {
    const a = rows[+b.dataset.artpin];
    if (!a) return;
    b.disabled = true;
    try{
      const j = await postJSON("/api/artifacts", {project, action: a.pinned ? "unpin" : "pin", path: a.path});
      if (j.error){ b.disabled = false; return notify(j.error, true); }
      notify(j.pinned ? `pinned ${a.name}: it stays` : `unpinned ${a.name}`);
    }catch(e){ b.disabled = false; return notify(String(e), true); }
    nbArtLoad(av);
  });
  list.querySelectorAll("[data-artview]").forEach(b => b.onclick = async () => {
    const a = rows[Number(b.dataset.artview)];
    const pane = document.createElement("div");
    pane.className = "verlogpane";
    nb.openSheet(a.name, [pane]);
    drawHTML(pane, `${skel("rows", 4)}`);
    try{
      const r = await fetch(`/api/artifact?project=${encodeURIComponent(project)
                                }&path=${encodeURIComponent(a.path)}`);
      pane.textContent = r.ok ? await r.text() : `could not read ${a.name}`;
    }catch(e){ pane.textContent = String(e); }
  });
  const stop = $("artStop");
  if (stop) stop.onclick = () => nbArtPost(av, {action: "stop"});
}

// The poll: stopped, and started again while a push or an install is in
// flight.
function nbArtPoll(av, job, inst){
  const {root} = av;
  clearInterval(av.artTimer); av.artTimer = null;
  // Polled while either thing is in flight. An install is the slower of the
  // two (a 24MB APK over wifi) and is the reason this exists at all.
  if ((job.running || inst.running)
      && !root.querySelector('[data-view="artifacts"]').hidden)
    av.artTimer = setTimeout(() => nbArtLoad(av), 2000);
}

// An action on this space's artifacts, its error said, and the view read
// again.
async function nbArtPost(av, body){
  const {project} = av;
  try{
    const j = await postJSON("/api/artifacts", {project, ...body});
    if (j.error){ notify(j.error, true); }
  }catch(e){ notify("artifacts: " + failWords(e), true); }
  await nbArtLoad(av);
}

// ---- the version, in the head of the tab whose files carry it ----------
// Two jobs, and they are not the same job. The display answers "what is
// this at", which needs no decision and is on all the time. The buttons
// answer "what should it be next", which is rare, and is hard here for a
// specific reason the operator named: most of the coding happens through
// prompts, so by bump time nobody remembers what the last three weeks
// contained. Hence the evidence line; that is the half that makes the
// decision two seconds instead of a scroll through git log.
function nbArtLoadVersion(av){
  const {$, project} = av;
  return reading(`${project}:version`, async () => {
    const box = $("verBox");
    try{
      av.ver = await getJSON("/api/version?project=" + encodeURIComponent(project));
    }catch(e){ box.textContent = "version: " + e; return; }
    const ver = av.ver;
    if (ver.error && !ver.target){
      // A malformed VERSION is worth saying out loud: everything downstream
      // assumes the shape, so this is the one place it can be reported, in
      // the section the number itself lives in, or it would be the one band
      // on this tab with nothing naming it. "unavailable" rather than a
      // guess at which, because this branch is both a malformed VERSION and
      // a project with no git behind it; the body says which.
      patch(box, docSection("artifacts", "version", artTitle("version"), "unavailable",
        `<div class="verln"><span>version</span><code>${esc(ver.error)}</code></div>`,
        {cls: "warn"}));
      wireSections(box);
      return;
    }
    nbArtDrawVersion(av);
  });
}

// A repo can ship two products, and then one number is a lie: an extension
// at 2.1 beside an app at 0.3 do not share a maturity. So the block is one
// section per VERSION file the project carries: almost always just the
// one, because a component exists only where somebody put a file.
function nbArtDrawVersion(av){
  const {$, nb, project, root, ver} = av;
  const box = $("verBox");
  const all = [ver, ...(ver.versions || [])];
  // One section per VERSION file, which is almost always one, and the
  // number is its status, so a shut section still answers the question the
  // tab is opened with. They used to be bands separated by a rule, with a
  // wall of bump buttons under each and nothing naming either.
  nbArtVerStages(av, all);
  // Patched (R244): a starting version or a bump being typed stays when a
  // build lands or the version is read again.
  patch(box, all.map(v => docSection("artifacts",
    `version${v.component ? ":" + v.component : ""}`,
    all.length > 1 ? (v.component || `${projLabel(v.project)} (the space)`) : artTitle("version"),
    v.target || "no VERSION file",
    nbArtVerSection(av, v) + nb.sectBar(`artifacts:version${v.component ? ":" + v.component : ""}`),
    {cls: v.target ? "" : "warn"})).join(""));
  wireSections(box);
  nbArtLoadDrafts(av);
  nbArtVerByRole(av, box);
  nbArtWireRelease(av, box, all);
  nbArtWireUnbump(av, box, all);
  nbArtVerBridges(av);
  nbArtWireChangelog(av, box);
  nbArtWireBump(av, box, all);
  nbArtWireInit(av, box);
  nbArtWireAsk(av, box);
  // Staged like a bump, written by the foot's Save (docs/design-language.md,
  // Settings): picking the saved value back clears the stage.
  root.querySelectorAll("[data-verpolgo]").forEach(b => { b.onclick = () => openNotebook(project, "permissions"); });
}

// Each VERSION file's section saves and reverts its own staged bump, the
// project's also its Claude access (the operator, 5 Oct).
function nbArtVerStages(av, all){
  const {nb} = av;
  all.forEach(v => {
    const comp = v.component || "";
    nb.stage(`artifacts:version${comp ? ":" + comp : ""}`, {
      count: () => (comp in av.verPending ? 1 : 0) + (!comp && av.verPolicyPending != null ? 1 : 0),
      what: () => comp ? `the staged bump of ${comp}` : "the staged version change",
      save: () => nb.verCommitStaged(comp),
      revert: () => nb.verClearStaged(comp)});
  });
}

// The block for one VERSION file. Its NAME is not in here: the section
// heading around it carries that, along with the number as its status.
function nbArtVerSection(av, v){
  const {project, ver, verPending, art} = av;
  const f = v.forms || {};
  const staged = verPending[v.component || ""];
  // What a window move costs, when this project is the one that owns the
  // window (the server decides that, from the files that move it). A
  // COMPONENT's version is its own and carries none of it.
  const cost = v.component ? null : ver?.window_cost;
  // Where the number here lives against the branch builds come from, and
  // where a staged bump would land: the server's sentences (version.lands),
  // so the row and aerie version say the same thing. A bump on a branch
  // already merged, unpushed, read as the project's version here while
  // main still had the old one, and nothing on the row said so (B338).
  const lands = v.lands || {};
  const mark = (text, bad) => text ? `<div class="verln"><span></span><span class="vermark${
      bad ? " bad" : ""}">${esc(text)}</span></div>` : "";
  const line = (label, value, cls = "") => value
    ? `<div class="verln ${cls}"><span>${label}</span><code>${esc(value)}</code></div>`
    : "";
  // "running here" only where it is a comparison rather than a coincidence:
  // BB_VERSION is the image's, and the image is built from one repo. It is
  // also the line that catches "merged, therefore running", which has cost
  // this project an afternoon before.
  const stale = v.running && f.semver && v.running !== f.semver;
  // Which way round, because the two directions mean opposite things and
  // guessing gets it wrong half the time. The ordinal is the only orderable
  // part, which is the entire reason it exists.
  const ordOf = str => { const m = /-dev\.(\d+)/.exec(str || ""); return m ? +m[1] : null; };
  const mine = v.ordinal, theirs = ordOf(v.running);
  const which = !stale ? ""
    : (theirs != null && mine != null && theirs > mine)
      ? "the running build is newer than this checkout: pull"
    : (theirs != null && mine != null && theirs < mine)
      ? "this checkout is newer than the running build: it is not deployed yet"
      : "the running build and this checkout are different builds";
  const newest = (art?.artifacts || [])[0];
  const s = v.since || {};
  // Counts, no verdict. Roadmap items finished reads as a minor and fixes
  // alone read as a patch, but that judgment is the operator's: a
  // recommendation this side cannot justify is worse than none.
  const bits = [];
  if (s.commits != null) bits.push(`${s.commits} commit${s.commits === 1 ? "" : "s"}`);
  if (s.done) bits.push(`${s.done} roadmap item${s.done === 1 ? "" : "s"} done`);
  if (s.fixed) bits.push(`${s.fixed} bug${s.fixed === 1 ? "" : "s"} fixed`);
  if (v.unreleased) bits.push(`${v.unreleased} change${v.unreleased === 1 ? "" : "s"} logged`);
  // "building towards" until the tag exists, "released as" after: the two
  // gestures said in the label somebody reads first, because which of them
  // has happened is the question this block kept failing to answer.
  return (v.target
            ? line(v.released ? "released as" : "building towards", v.target)
            : line("version", "none yet: no VERSION file; Set one below"))
    + (v.released ? line("tag", v.tag) : "")
    // The forge's release Release made for this tag (R123, R124).
    + (v.released && nbArtRelUrl(ver, v.tag) ? `<div class="verln"><span>on ${esc(nbArtRelOf(ver, v.tag).forge || "GitHub")}</span><a href="${
           esc(nbArtRelUrl(ver, v.tag))}" target="_blank" rel="noopener noreferrer">the ${esc(v.tag)} release</a></div>`
       // ...or why there is none, the tag left pushed.
       : v.released && nbArtRelOf(ver, v.tag).error ? mark(`no release on ${nbArtRelOf(ver, v.tag).forge || "the forge"}: ${nbArtRelOf(ver, v.tag).error}`, true) : "")
    + mark(lands.now, lands.bad)
    + (staged ? `<div class="verln"><span></span><span class="vermark">
           staged: ${esc(v.next[staged] || "")} on Save: ${esc(staged)}${
             v.unreleased ? `, dating ${v.unreleased} changelog entr${
               v.unreleased === 1 ? "y" : "ies"}`
             : `, with no changelog entries to date`}</span></div>` : "")
    + (staged ? mark(lands.staged, lands.staged_bad) : "")
    // What a MINOR bump costs everything else, said BEFORE Save rather than
    // discovered after it (B92): the minor is the compatibility window, so
    // moving it ends the Claude sessions on every project whose block is
    // from the old one and holds them until each is updated. The count is
    // the server's, from the blocks that actually exist.
    + (windowMove(staged, cost) ? `<div class="verln"><span></span>
           <span class="vermark bad">this moves the compatibility window from ${
             esc(cost.window)} to ${esc((v.next[staged] || "").split(".").slice(0, 2).join("."))
             }: sessions on ${cost.projects.length} space${cost.projects.length === 1 ? "" : "s"
             } end until each is updated from the bell</span></div>` : "")
    + line("a build now", f.semver)
    + (v.running ? line("running here", v.running, stale ? "" : "off") : "")
    + (stale ? `<div class="verln"><span></span><span class="vermark">${
           esc(which)}</span></div>` : "")
    + (newest ? line("last shipped", newest.name, "off") : "")
    + (v.warn ? `<div class="verln"><span></span><span class="vermark">${
           esc(v.warn)}</span></div>` : "")
    + (v.target ? `
        <p class="verwhy">${bits.length
          ? "since " + esc(v.target) + ": " + bits.join(" · ")
          : "nothing has landed since " + esc(v.target)}</p>
        <div class="actbar verbtns">
          ${["patch", "minor", "major"].map(pt => `
            <button type="button" data-verbump="${pt}" data-vercomp="${esc(v.component || "")}"
              class="${staged === pt ? "on" : ""}"
              title="${staged === pt
                ? "staged: Save writes VERSION and commits it; press again to unstage"
                : `stage ${esc(v.next[pt] || "")}; nothing is written until Save`}">
              ${pt[0].toUpperCase() + pt.slice(1)} → ${esc(v.next[pt] || "")}</button>`).join("")}
          <button type="button" data-verask="${esc(v.component || "")}"
            title="ask the session whether ${esc(v.target)} should move; it proposes and asks first">Send to ${esc(sendAgent(project).name)}</button>
          ${v.prev && !v.sealed ? `
          <button type="button" data-verunbump="${esc(v.component || "")}"
            title="take the version back to ${esc(v.prev)}; ${esc(v.target)}'s changelog lines return to Unreleased">↩ ${esc(v.prev)}</button>` : ""}
          ${v.released ? "" : `
          <button type="button" data-verrelease="${esc(v.component || "")}"
            title="${`tag the pushed commit ${esc(v.component ? v.component + "-v" + v.target : "v" + v.target)} and push the tag: `
                + "that is what releases " + esc(v.target)}"
            >Release ${esc(v.target)}</button>`}
          <button type="button" class="verlogbtn" data-verlog="${esc(v.component || "")}"
            title="what changed, for the people using it; a bump dates the lines so far">Changelog${
            v.unreleased ? ` (${v.unreleased} new)` : ""}</button>
        </div>
        ${v.component ? "" : nbArtVerPolicyPicker(v)}
        <p class="verwhy">${v.released
          ? `Released: <code>${esc(v.tag)}</code> is on this commit, so a build of it
             is <code>${esc(v.target)}</code> exactly. Bump to start the next one.`
          : `<b>Bump</b> decides the number and closes the changelog under it;
             <b>Release</b> tags and pushes it. ${helpIcon(`Two steps. Until the release, a build reads ${
               v.target}-dev.${v.ordinal ?? "n"} rather than ${v.target}: the tag on the commit, pushed, is what says it happened.`)}`}</p>
        ${v.component ? "" : `<p class="verwhy">A bump is staged until Save, and is never pushed. ${
          helpIcon("Save writes and commits VERSION. Agent access limits what a session may change.")}</p>
        ${nbArtVerAddFold(project, v)}`}` : `
        ${v.component ? "" : nbArtVerPolicyPicker(v)}
        <div class="verln"><span>start at</span>
          <span class="verinit">
            <input class="vstart" value="0.1.0" size="8" maxlength="20"
              inputmode="decimal" aria-label="starting version"
              pattern="[0-9]+\.[0-9]+\.[0-9]+">
            <button type="button" data-verinit="${esc(v.component || "")}"${state?.can?.version === false ? " disabled" : ""}
              title="${state?.can?.version === false ? "moving a space's version is not one of your roles' grants" : "write a VERSION file at this number and commit it"}">Set</button>
          </span></div>
        <div class="actbar verbtns">
          <button type="button" data-verask="${esc(v.component || "")}"
            title="ask the session what the version should be; it proposes and asks first">Send to ${esc(sendAgent(project).name)}</button>
          <button type="button" data-verlog="${esc(v.component || "")}"
            title="entries logged before the first version wait here">Changelog${
            v.unreleased ? ` (${v.unreleased} new)` : ""}</button>
        </div>
        <p class="verwhy">No version yet. Setting one writes a
          <code>VERSION</code> file and commits it${v.unreleased
            ? `, dating the ${v.unreleased} logged change${
                v.unreleased === 1 ? "" : "s"} as its first section` : ""}.</p>
        ${nbArtVerAddFold(project, v)}`);

}

// What the forge holds for a tag's release: its address, or why there is
// none.
function nbArtRelOf(ver, tag){
  return (ver?.forge_releases || {})[tag] || {};
}
function nbArtRelUrl(ver, tag){
  // A web address and nothing else (never javascript:); plain http too,
  // which a Gitea on a LAN serves its releases on (B505).
  const u = nbArtRelOf(ver, tag).url || "";
  return /^https?:\/\//.test(u) ? u : "";
}

// "Ships something else from here?": the door to a component's own
// number. Offered wherever candidate directories exist, INCLUDING on a
// project with no version of its own yet: two products with different
// maturities is exactly the state a fresh project can already be in, and
// the two inits work in either order.
function nbArtVerAddFold(project, v){
  if (v.component || !(v.candidates || []).length) return "";
  return `
      <details class="veradd chev"${sectAttr("artifacts:veradd:" + project)}><summary>ships something else from here?</summary>
        <p class="verwhy">A directory with its own <code>VERSION</code> file is
          versioned on its own, like an extension beside an app.</p>
        <div class="verinit">
          <select class="vdir" aria-label="which directory">${
            v.candidates.map(c => `<option>${esc(c)}</option>`).join("")}</select>
          <input class="vstart" value="0.1.0" size="8" maxlength="20"
            inputmode="decimal" aria-label="starting version"
            pattern="[0-9]+\.[0-9]+\.[0-9]+">
          <button type="button" data-veradd>Give it its own version</button>
          <button type="button" data-verask="@fold"
            title="put the question to this space's session, for
this directory">Send to ${esc(sendAgent(project).name)}</button>
        </div>
      </details>`;
}

// The one picker, drawn in both states of this tab. It used to be written
// only into the has-a-version branch, so a project with no version had no
// way to say who may give it one, which is the setting that matters most
// at exactly that moment.
function nbArtVerPolicyPicker(v){
  // Said here, set on the Permissions view beside every other dial (R223,
  // the operator, 7 Nov: one place for what an agent may do).
  return `<span class="verpol">
      <span>Agent access</span> <b>${esc(POLICY_LABEL[v.policy] || v.policy || "")}</b>
      <button type="button" data-verpolgo>Change on Permissions</button>
    </span>`;
}

// Drafts (the operator, 1 Nov): every release CI makes waits as a draft,
// seen by the repository's own people alone, its notes read and corrected
// here, then published. A role that may not release reads them.
function nbArtLoadDrafts(av, force){
  const {$, project} = av;
  return reading(`${project}:drafts`, async () => {
    const box = $("verDrafts");
    if (!box) return;
    // Notes being corrected are never redrawn under the person typing them.
    if (!force && box.querySelector("textarea[data-dirty]")) return;
    const j = await postJSON("/api/version", {project, action: "release-drafts"});
    const ds = j.drafts || [];
    if (!ds.length){ box.innerHTML = ""; return; }
    const may = !projReleaseWhy(project);
    patch(box, docSection("artifacts", "drafts", "Drafts", `${ds.length} waiting`, ds.map(d => {
      const miss = d.missing || [];
      // What keeps it from being published, each said on its row (R206 step
      // 3): a tag that is not on the git host stops the press; placeholder
      // notes are put right in the box, so the press stays and is checked.
      const holds = d.holds || [], stop = miss.length || holds.some(h => h.what !== "notes");
      return `<div class="field verdraft" data-draft="${esc(d.tag)}" data-key="${esc(d.tag)}">
          <div class="verln"><span>${d.prerelease ? "dev build" : "release"}</span><a href="${esc(d.url)}" target="_blank" rel="noopener noreferrer">${esc(d.tag)}</a></div>
          ${miss.length ? `<div class="hint warn">Not whole yet: ${esc(miss.join(", "))} still missing; CI may still be building it.</div>` : ""}
          ${holds.map(h => `<div class="hint warn" data-drafthold="${esc(h.what)}">Not published yet: ${esc(h.why)}.</div>`).join("")}
          ${(d.undescribed || []).length ? `<div class="hint" data-draftundesc>Publish puts a table of its files over the notes; ${
            esc(d.undescribed.join(", "))} ${d.undescribed.length === 1 ? "is" : "are"} listed by name alone, with nothing said of what ${
            d.undescribed.length === 1 ? "it is" : "they are"} for. Describe them in Settings, Releases.</div>` : ""}
          <textarea rows="12" aria-label="${esc(d.tag)}'s notes"${may ? "" : " readonly"}>${esc(d.notes)}</textarea>
          ${may ? `<div class="actbar"><span class="sp"></span><button type="button" data-draftsave>Save the notes</button><button type="button" class="primary" data-draftpub${stop ? " disabled" : ""}>Publish</button></div>` : ""}
        </div>`;
    }).join("") + `<div class="hint">Only this repository's own people see a draft. Read its notes and correct them, then Publish: the release goes public, the dev channel and the containers following :dev take it, and a stable one becomes :latest. Publish it here: the git host's own form checks none of this, and one published there with its tag field emptied went out under a name nothing reads.</div>`, {cls: "warn"}));
    wireSections(box);
    box.querySelectorAll("[data-draft]").forEach(row => {
      const tag = row.dataset.draft, ta = row.querySelector("textarea");
      const save = row.querySelector("[data-draftsave]"), pub = row.querySelector("[data-draftpub]");
      ta.oninput = () => { ta.dataset.dirty = "1"; };
      if (save) save.onclick = () => pressing(save, async () => {
        const r = await postJSON("/api/version", {project, action: "release-draft-notes", tag, notes: ta.value});
        notify(r.error || `${tag}'s notes saved; it is still a draft`, !!r.error);
        if (!r.error) delete ta.dataset.dirty;
      });
      if (pub) pub.onclick = () => pressing(pub, async () => {
        if (!await askYes(`Publish ${tag}?\n\nIts notes as they stand in the box go out with it, and everybody can see and take it from then on: ${
              tag.includes("-dev.") ? "the dev channel and the containers following :dev" : "every install following releases, and :latest"}. A published release is taken back with Withdraw.`,
            {title: "Publish it?", verb: "Publish"})) return;
        busy(pub, "Publishing");
        const r = await postJSON("/api/version", {project, action: "release-publish", tag, notes: ta.value});
        notify(r.error || `${tag} is published`, !!r.error);
        if (!r.error) await nbArtLoadDrafts(av, true);
      });
    });
  });
}

// A role without Releases and versions Write on the project (B101):
// every button that moves or releases the version left out, and the
// fields that say it read-only; without Projects Write, Send to Claude
// too. Nothing says why (the operator, 21 Oct).
function nbArtVerByRole(av, box){
  const {project} = av;
  const relWhy = projReleaseWhy(project), ro = projWriteWhy(project);
  giveBack(box);
  if (relWhy){
    box.querySelectorAll("[data-verbump],[data-verrelease],[data-verunbump],[data-verinit],[data-veradd]").forEach(x => takeAway(x, true));
    box.querySelectorAll("#verPolicy,.vstart,.vdir").forEach(x => takeAway(x));
  }
  if (ro) box.querySelectorAll("[data-verask]").forEach(x => takeAway(x, true));
}

// Releasing: outward-facing, and the one thing on this tab other people
// fetch. Confirmed by name, because a pushed tag is not taken back from
// here, or anywhere, without thinking about who has it.
function nbArtWireRelease(av, box, all){
  box.querySelectorAll("[data-verrelease]").forEach(b => b.onclick = async () => {
    const comp = b.dataset.verrelease || "";
    const blk = all.find(x => (x.component || "") === comp);
    const tag = comp ? `${comp}-v${blk?.target}` : `v${blk?.target}`;
    // What would keep its Android APK from being signed, said before the
    // tag rather than found after it (R134 step 4).
    if (!await askYes(`Release ${blk?.target}?\n\n`
                 + `Tags this branch's pushed commit as ${tag} and pushes the tag; a pushed tag is not moved or deleted from here. `
                 + "A change not committed here is not in it, and a commit not pushed is asked for first."
                 + (av.ver?.release_sign ? `\n\nIts Android APK will not be signed: ${av.ver.release_sign}. `
                    + "The Signing view's Look for unsigned APKs now signs it once that is put right, within three days." : ""))) return;
    busy(b, "Releasing");
    box.querySelectorAll("button,select").forEach(x => x.disabled = true);
    const j = await nbArtPostVersion(av, {action: "release", component: comp});
    // The forge's release beside the tag (R123; Gitea and GitLab since
    // R124), or why there is none: the tag is pushed either way, so a
    // forge's no is a note, not a failure.
    const fg = j?.released?.forge, on = fg?.forge || "the forge";
    if (j?.released?.tag)
      notify(j.released.note
             || (fg?.url ? `${j.released.tag} tagged and pushed, and ${fg.made ? "released" : "already released"} on ${on}${
                     fg.assets?.length ? ` with ${fg.assets.length} build${fg.assets.length === 1 ? "" : "s"}` : ""}`
                 : `${j.released.tag} tagged and pushed` + (fg?.error ? `; no release on ${on}: ${fg.error}` : "")),
             !!fg?.error);
  });
}

// Taking a version back to the one before it, asked first: the code stays,
// and its changelog lines return to Unreleased.
function nbArtWireUnbump(av, box, all){
  box.querySelectorAll("[data-verunbump]").forEach(b => b.onclick = async () => {
    const comp = b.dataset.verunbump || "";
    const blk = all.find(x => (x.component || "") === comp);
    if (!await askYes(`Take ${comp ? comp + "'s" : "this space's"} version back `
                 + `from ${blk?.target} to ${blk?.prev}?\n\n`
                 + `The code stays; ${blk?.target}'s changelog lines return to Unreleased.`)) return;
    box.querySelectorAll("button,select").forEach(x => x.disabled = true);
    await nbArtPostVersion(av, {action: "unbump", component: comp});
  });
}

// Published to the panel-level Save/Revert, which live outside this
// closure. Rebound on every draw so they always close over this
// notebook's own state rather than whichever one drew last.
function nbArtVerBridges(av){
  const {nb} = av;
  nb.verStagedCount = () => Object.keys(av.verPending).length + (av.verPolicyPending != null ? 1 : 0);
  // With a component, that section's alone (its bump, and for the
  // project's own section its Claude access too); without, all of them.
  nb.verClearStaged = only => {
    if (only === undefined){ av.verPending = {}; av.verPolicyPending = null; }
    else { delete av.verPending[only]; if (!only) av.verPolicyPending = null; }
    nbArtDrawVersion(av);
  };
  nb.verCommitStaged = async only => {
    const parts = Object.entries(av.verPending).filter(([comp]) => only === undefined || comp === only);
    const policy = only === undefined || only === "" ? av.verPolicyPending : null;
    if (!parts.length && policy == null) return "";
    // A window move is the one thing on this tab that reaches other
    // projects: it ends their sessions. Asked here as well as said on the
    // staged line, because the line can be scrolled past and this cannot
    // (B92). Anything else saves without a question, as it always has.
    const cost = av.ver?.window_cost;
    const moves = parts.find(([comp, part]) => !comp && windowMove(part, cost));
    if (moves && !await askYes(
          `Bump the ${moves[1]}? This moves the compatibility window.\n\n`
          + `Sessions on ${cost.projects.length} space${cost.projects.length === 1 ? "" : "s"} `
          + `(${cost.projects.join(", ")}) end until each node's agent is updated on the Nodes page.`)) return null;
    for (const [comp] of parts) delete av.verPending[comp];
    if (policy != null) av.verPolicyPending = null;
    const done = [];
    if (policy != null){
      const j = await nbArtPostVersion(av, {action: "policy", policy}, true);
      if (j && !j.error) done.push(`Agent access: ${POLICY_LABEL[policy] || policy}`);
    }
    for (const [comp, part] of parts){
      const j = await nbArtPostVersion(av, {action: "bump", part, component: comp},
                                       true);
      if (j?.bumped) done.push(`${comp || "version"} ${j.bumped.was} → ${j.bumped.target}`);
    }
    return done.join(" · ");
  };
}

// Patch, Minor and Major stage a bump for Save; the staged one pressed
// again clears it.
function nbArtWireBump(av, box, all){
  const {nb} = av;
  box.querySelectorAll("[data-verbump]").forEach(b => b.onclick = async () => {
    const part = b.dataset.verbump, comp = b.dataset.vercomp || "";
    const blk = all.find(x => (x.component || "") === comp);
    const to = blk?.next?.[part];
    // Staged, not done: no confirm here, because nothing has happened yet
    // and Save is the question. Pressing the same part again clears it,
    // which is how a misclick is undone without a dialog.
    av.verPending[comp] = av.verPending[comp] === part ? undefined : part;
    if (av.verPending[comp] === undefined) delete av.verPending[comp];
    nbArtDrawVersion(av);
    nb.syncSave();
  });
}

// The starting version typed beside the button, or null, said and focused,
// when it is not MAJOR.MINOR.PATCH.
function nbArtVerStart(el){
  const f = el.closest(".verinit").querySelector(".vstart");
  const val = (f.value || "").trim();
  if (!/^\d+\.\d+\.\d+$/.test(val)){
    notify("a version is MAJOR.MINOR.PATCH, like 0.1.0", true);
    f.focus();
    return null;
  }
  return val;
}

// Creating the first VERSION, and creating a component's. Both exist
// because the file tools are denied on VERSION: without a sanctioned path
// the tab would be telling the operator to do something no part of this
// UI can do, which is how a guardrail turns into a thing people route
// around.
function nbArtWireInit(av, box){
  box.querySelectorAll("[data-verinit]").forEach(b => b.onclick = async () => {
    const val = nbArtVerStart(b);
    if (val === null) return;
    busy(b, "Setting");
    await nbArtPostVersion(av, {action: "init", value: val,
                                component: b.dataset.verinit || ""});
  });
  const add = box.querySelector("[data-veradd]");
  if (add) add.onclick = async () => {
    const val = nbArtVerStart(add);
    if (val === null) return;
    const dir = add.closest(".verinit").querySelector(".vdir").value;
    busy(add, "Adding");
    await nbArtPostVersion(av, {action: "init", value: val, component: dir});
  };
  // The fold opens the way every other fold on the page does: driven, not
  // the browser's instant snap. Same helper as a memory and a bug report.
  box.querySelectorAll("details.veradd > summary").forEach(sum => {
    sum.onclick = e => {
      e.preventDefault();
      slideDetails(sum.parentElement, !foldOpen(sum.parentElement));
    };
  });
}

// Asked of the session rather than answered here, and then the tab gets
// out of the way: the same shape as sending a step, because it is the
// same thing: a question that wants a conversation, not a field filled in
// behind the operator's back.
function nbArtWireAsk(av, box){
  const {project} = av;
  box.querySelectorAll("[data-verask]").forEach(b => b.onclick = async () => {
    const comp = b.dataset.verask === "@fold"
      ? b.closest(".verinit").querySelector(".vdir").value
      : (b.dataset.verask || "");
    if (!await sendSure(project, comp ? `the version question for ${comp}` : "the version question")) return;
    busy(b, "Sending");
    try{
      const j = await postJSON("/api/version", {project, action: "ask", component: comp});
      if (j.error){ notify(j.error, true); b.disabled = false; return; }
      if (!j.sent){
        notify("Not sent: the session is busy. Press Enter in its tab when it is free.",
               true);
      }
      openSentTo(project, j.session);   // opens the tab, or goes to the one there
    }catch(e){ notify("ask: " + failWords(e), true); }
    // finally, not after the try: an exception on the way to the session
    // used to leave this dead, and a button that will not fire twice is
    // indistinguishable from one that did nothing.
    finally { b.disabled = false; }
  });
}

// A version action, what came of it said in words, and the version read
// again whatever came back.
async function nbArtPostVersion(av, body, quiet){
  const {project} = av;
  try{
    const j = await postJSON("/api/version", {project, ...body});
    if (j.error){ notify(j.error, true); }
    else if (j.bumped){
      if (!quiet) notify(`version ${j.bumped.was} → ${j.bumped.target}`);
      if (j.bumped.note) notify(j.bumped.note, true);
    }
    else if (j.unbumped) notify(`version returned: ${j.unbumped.was} → ${
        j.unbumped.target}: its changelog is back in Unreleased`);
    else if (j.created) notify(`${j.created.component || "this space"} `
                               + `is now ${j.created.target}`);
    return j;
  }catch(e){ notify("version: " + failWords(e), true); }
  finally{ await nbArtLoadVersion(av); }
}

// ---- the changelog, as something you can shape ------------------------
// It used to be the file as text, which is right for reading and useless
// for the thing it is actually for: a cycle's entries are written by
// sessions, one at a time, in the order the work happened, and what a
// person reads at a release wants an arrangement. Categories, their
// order, the order inside them, the words: all of it here.
//
// Unreleased only. Everything below it is a release somebody may have
// read, shown as the text it is; `aerie version unroll` is how one is
// reopened, which is a gesture that says what it is.
function nbArtDrawChangelog(av, pane, comp, j){
  const {nb, project} = av;
  let gs = JSON.parse(JSON.stringify(j.groups || []));
  // The tracker's half (R255): the bugs each saved line answers, by its
  // words as saved (`orig`); a line written here for a bug carries it as
  // `pend` until Save has put the line in the file, then it is tied.
  const norm = t => String(t || "").split(/\s+/).filter(Boolean).join(" ");
  let meta = {ties: j.ties || {}, fixed: j.fixed || [], owed: j.owed || []};
  const ro = !!projWriteWhy(project);
  const marked = () => gs.forEach(g => g.entries.forEach(e => { if (e.orig === undefined && !e.pend) e.orig = norm(e.text); }));
  marked();
  const tiedTo = e => [...(e.orig !== undefined ? meta.ties[e.orig] || [] : []), ...(e.pend || [])];
  const titleOf = n => meta.fixed.find(b => b.id === n)?.title || "";
  const owedNow = () => meta.owed.filter(o => !gs.some(g => g.entries.some(e => tiedTo(e).includes(o.id))));
  const clBugs = e => {
    const ids = tiedTo(e);
    if (ro && !ids.length) return "";
    return `<div class="clbugs">${ids.map(n => `<span class="pill clbug${(e.pend || []).includes(n) ? " pend" : ""}"
        title="${esc(`B${n} ${titleOf(n)}${(e.pend || []).includes(n) ? ": tied when the line is saved" : ""}`)}">B${n}${
        ro ? "" : `<button type="button" class="pillx" data-clun="${n}" aria-label="this line no longer answers B${n}">✕</button>`}</span>`).join("")}${
      ro ? "" : `<button type="button" class="ghost" data-cltie title="tie a fixed bug to this line: kept in the notebook, the file names its commits">+ Bug</button>`}</div>`;
  };
  const owedBand = () => {
    const rows = ro ? [] : owedNow();
    if (!rows.length) return "";
    return `<div class="clowed" role="group" aria-label="fixed bugs the next release owes a line">
      <div class="sub">${rows.length} fixed bug${rows.length === 1 ? "" : "s"} the next release owes a line: tie each to a line below with + Bug, write one, or say why it needs none. A release waits for them.</div>
      ${rows.map(o => `<div class="row clowe" data-ow="${o.id}">
        <div class="clowt"><span class="n id">B${o.id}</span> ${esc(titleOf(o.id))}</div>
        <div class="actbar"><button type="button" data-owline>Write a line</button>
          <button type="button" data-ownone title="a release never had it, or nobody using it meets it">Needs no line</button></div>
      </div>`).join("")}</div>`;
  };
  const dated = (j.text || "").split(/\n(?=## (?!Unreleased))/s).slice(1).join("\n");
  const names = () => [...new Set(gs.map(g => g.name))];
  const flat = () => gs.flatMap(g => g.entries.map(e => [g, e]));
  const swap = (a, i, k) => { const t = a[i]; a[i] = a[i + k]; a[i + k] = t; };

  // Where the reader was, across a redraw. Every gesture here rebuilds the
  // whole pane, which is fine for ten entries and not for sixty, where
  // one press of ↑ threw away the scroll position and the focus, so
  // moving a line three places meant finding its button three times.
  // `keep` is the ENTRY OBJECT rather than an index, because the indices
  // are what the move just changed.
  // The sheet's slot is what scrolls (`.box.sheet .sheetslot{overflow:auto}`),
  // and the pane is its child. Named rather than walked, because a guess
  // that finds the wrong element restores a scroll nobody moved.
  const scroller = () => pane.closest(".sheetslot") || pane.parentElement;
  const draw = (keep, sel) => {
    const opts = (cur) => optionList(["", ...names().filter(Boolean)].map(n => [n, n || "no category"]), cur)
      + `<option value="\u0000new">new category…</option>`;
    const box = scroller();
    const top = box ? box.scrollTop : null;
    drawHTML(pane,
      `<div class="clog">
             <div class="hint">Sessions add the lines; the order and the words are yours. Save writes CHANGELOG.md. The bugs a line answers are kept in the notebook, never in the file.</div>
             ${owedBand()}
             ${gs.length ? gs.map((g, gi) => `
               <div class="clgroup" data-g="${gi}">
                 ${g.name ? `<div class="clhead">
                   <input class="clname" value="${esc(g.name)}" maxlength="40"
                          aria-label="category name">
                   <button type="button" data-cmv="up" data-g="${gi}"
                     ${gi === 0 ? "disabled" : ""} title="move this category up">↑</button>
                   <button type="button" data-cmv="down" data-g="${gi}"
                     ${gi === gs.length - 1 ? "disabled" : ""} title="move this category down">↓</button>
                 </div>` : ""}
                 ${g.entries.map((e, ei) => `
                   <div class="clrow" data-g="${gi}" data-e="${ei}">
                     <textarea class="cltext proseline" rows="1" maxlength="300"
                       aria-label="what changed">${esc(e.text)}</textarea>
                     <div class="clmeta" title="${esc((e.shas || []).join(", "))}">
                       <select class="clcat" aria-label="category">${opts(g.name)}</select>
                       <span class="clsha">${esc((e.shas || []).join(", ")) || "none"}</span>
                       <span class="sp"></span>
                       <button type="button" data-emv="up" title="move up">↑</button>
                       <button type="button" data-emv="down" title="move down">↓</button>
                       <button type="button" class="danger" data-erm
                         title="drop this line: the commit is untouched">✕</button>
                     </div>
                     ${clBugs(e)}
                   </div>`).join("")}
               </div>`).join("")
             : `<div class="empty">nothing unreleased here yet</div>`}
             ${projWriteWhy(project) ? "" : `<div class="actbar"><span class="state" id="clState"></span>
               <button type="button" class="primary" id="clSave">Save</button></div>`}
           </div>
           ${dated ? `<div class="verlogpane">${clLinks(dated)}</div>` : ""}`);
    wire();
    if (top != null && box) box.scrollTop = top;
    if (keep){
      const at = flat().findIndex(([, x]) => x === keep);
      const row = at >= 0 ? pane.querySelectorAll(".clrow")[at] : null;
      row?.querySelector(sel || "textarea")?.focus();
    }
  };

  const wire = () => {
    const q = (sel, fn) => pane.querySelectorAll(sel).forEach(fn);
    // An id in the released text opens its row, the sheet put away.
    q("[data-clref]", a => a.onclick = e => {
      e.preventDefault();
      nb.closeSheet();
      getNotebook(project).find(a.dataset.clref);
    });
    q("[data-cmv]", b => b.onclick = () => {
      const gi = Number(b.dataset.g);
      swap(gs, gi, b.dataset.cmv === "up" ? -1 : 1);
      draw();
    });
    q(".clname", i => i.onchange = () => {
      gs[Number(i.closest(".clgroup").dataset.g)].name = i.value.trim();
      draw();
    });
    q(".clrow", row => {
      const g = gs[Number(row.dataset.g)], e = g.entries[Number(row.dataset.e)];
      // The growing is proseline()'s, wired by the draw that wrote the
      // row (drawHTML); this only has to hear the words change.
      row.querySelector(".cltext").onchange = ev => { e.text = ev.target.value; };
      row.querySelector("[data-erm]").onclick = () => {
        g.entries.splice(g.entries.indexOf(e), 1);
        gs = gs.filter(x => x.entries.length);
        draw();
      };
      row.querySelectorAll("[data-emv]").forEach(b => b.onclick = () => {
        // Across the whole section, not within the group: a line moved
        // off the end of one category lands in the next, which is what
        // "move it down" looks like to somebody dragging a list.
        const all = flat();
        const at = all.findIndex(([, x]) => x === e);
        const to = at + (b.dataset.emv === "up" ? -1 : 1);
        if (to < 0 || to >= all.length) return;
        const [tg] = all[to];
        g.entries.splice(g.entries.indexOf(e), 1);
        if (tg === g) g.entries.splice(g.entries.indexOf(all[to][1])
                                       + (b.dataset.emv === "up" ? 0 : 1), 0, e);
        else tg.entries.splice(b.dataset.emv === "up" ? tg.entries.length : 0, 0, e);
        gs = gs.filter(x => x.entries.length);
        // ...and the button that moved it is under the same finger, so a
        // line goes three places in three presses rather than three hunts.
        draw(e, `[data-emv="${b.dataset.emv}"]`);
      });
      row.querySelector(".clcat").onchange = async ev => {
        let to = ev.target.value;
        if (to === "\u0000new"){
          to = await askInline(row, {label: "The new category's name", ok: "Make it"});
          if (!to){ draw(); return; }
        }
        g.entries.splice(g.entries.indexOf(e), 1);
        let hit = gs.find(x => x.name === to);
        if (!hit){ hit = {name: to, entries: []}; gs.push(hit); }
        hit.entries.push(e);
        gs = gs.filter(x => x.entries.length);
        draw();
      };
    });
    // The tracker's half (R255): a tie to a saved line is written at once,
    // one to a line written here waits for Save.
    const tie = async (e, n, on) => {
      if (e.orig === undefined){
        e.pend = on ? [...new Set([...(e.pend || []), n])] : (e.pend || []).filter(x => x !== n);
        return draw(e, "[data-cltie]");
      }
      const r = await postJSON("/api/bugs", {project, action: on ? "tie" : "untie", id: n, line: e.orig});
      if (r?.error) return notify(r.error, true);
      const have = meta.ties[e.orig] || [];
      meta.ties[e.orig] = on ? [...new Set([...have, n])] : have.filter(x => x !== n);
      draw(e, "[data-cltie]");
    };
    q(".clrow", row => {
      const e = gs[Number(row.dataset.g)].entries[Number(row.dataset.e)];
      row.querySelectorAll("[data-clun]").forEach(x => x.onclick = () => tie(e, Number(x.dataset.clun), false));
      const plus = row.querySelector("[data-cltie]");
      if (plus) plus.onclick = () => {
        if (row.querySelector(".tiebox")) return;
        const have = tiedTo(e), owed = new Set(owedNow().map(o => o.id));
        const offer = meta.fixed.filter(b => !have.includes(b.id)).sort((a, b) => owed.has(b.id) - owed.has(a.id));
        if (!offer.length) return notify("no fixed bug is left to tie to this line", true);
        const box = document.createElement("div");
        box.className = "dropbox ctlown tiebox";
        drawHTML(box, `<div class="q">Which fixed bug does this line answer?<span>: kept in the notebook</span></div>
          <select aria-label="a fixed bug">${optionList(offer.map(b => [String(b.id),
            `B${b.id}${owed.has(b.id) ? " (owed)" : ""}: ${b.title.length > 90 ? b.title.slice(0, 88) + "…" : b.title}`]), "")}</select>
          <div class="actbar"><button type="button" class="stop">Cancel</button>
            <button type="button" class="primary" data-tiego>Tie it</button></div>`);
        row.appendChild(box);
        arriveBox(box);
        box.querySelector(".stop").onclick = () => box.remove();
        box.querySelector("[data-tiego]").onclick = () => tie(e, Number(box.querySelector("select").value), true);
      };
    });
    q("[data-ow]", r => {
      const n = Number(r.dataset.ow), b = meta.fixed.find(x => x.id === n);
      r.querySelector("[data-owline]").onclick = () => {
        // A line under Fixed holding the bug's title and its commits, to
        // reword before Save; the bug is tied once it is saved.
        let g = gs.find(x => x.name === "Fixed");
        if (!g){ g = {name: "Fixed", entries: []}; gs.push(g); }
        const e = {text: b?.title || "", shas: b?.commits || [], pend: [n]};
        g.entries.push(e);
        draw(e, "textarea");
      };
      r.querySelector("[data-ownone]").onclick = () => {
        if (r.querySelector(".dropbox")) return;
        dropBox(r, {q: "Why does it need no line?", sub: ": kept in its notes, which the release check reads",
                    placeholder: "no release had it; nobody using it meets it", verb: "Needs no line",
                    go: async why => {
                      const a = await postJSON("/api/bugs", {project, action: "noline", id: n, why});
                      if (a?.error) return notify(a.error, true);
                      meta.owed = meta.owed.filter(o => o.id !== n);
                      draw();
                    }});
      };
    });
    const save = pane.querySelector("#clSave");
    if (save) save.onclick = async () => {
      busy(save, "Saving");
      try{
        const pend = flat().filter(([, e]) => (e.pend || []).length).map(([, e]) => ({words: norm(e.text), ids: e.pend}));
        const a = await postJSON("/api/changelog", {project, component: comp, groups: gs});
        if (a.error){ notify(a.error, true); return; }
        // Drawn again from what the server kept, not what was sent: a
        // tidy-up on the way in shows (B820: it set the list and never
        // drew it).
        gs = a.groups || [];
        // ...the bugs a new line was written for are tied to its words as
        // saved, and the ties and what is owed read again: a reworded line
        // carried its bugs on the server.
        for (const p of pend)
          for (const n of p.ids){
            const t = await postJSON("/api/bugs", {project, action: "tie", id: n, line: p.words});
            if (t?.error) notify(`B${n}: ${t.error}`, true);
          }
        try{
          const f = await getJSON(`/api/changelog?project=${encodeURIComponent(project)}&component=${encodeURIComponent(comp)}`);
          if (!f.error){ meta = {ties: f.ties || {}, fixed: f.fixed || [], owed: f.owed || []}; gs = f.groups || gs; }
        }catch{ /* drawn from the save's own answer */ }
        marked();
        draw();
        const st = pane.querySelector("#clState");
        if (st) st.textContent = `saved: ${a.entries} line${a.entries === 1 ? "" : "s"}`;
        nbArtLoadVersion(av);
      }catch(e){ notify("changelog: " + failWords(e), true); }
      finally{ if (save.isConnected) unbusy(save, "Save"); }
    };
  };
  draw();
}

// Each Changelog button opens its file's changelog over the panel, and
// closes it when pressed again.
function nbArtWireChangelog(av, box){
  const {nb, project} = av;
  box.querySelectorAll("[data-verlog]").forEach(b => b.onclick = async () => {
    const comp = b.dataset.verlog || "";
    if (b.classList.contains("on")){ nb.closeSheet(); return; }
    // Built for the sheet rather than rendered into the box and moved there.
    // It used to live in #verBox, hidden, and nb.openSheet() moved it, so a
    // repaint of the box while the sheet was open (a version poll, a dist
    // change) put a second, empty .verlogpane back in the box, and anything
    // looking for "the changelog pane" found whichever came first in the
    // document. nb.openSheet takes a parentless element and drops it on close,
    // so there is now exactly one at a time, or none.
    const pane = document.createElement("div");
    pane.className = "verlogpane";
    pane.dataset.verlogpane = comp;
    // A changelog is prose someone wrote to be read, and it was opening as a
    // block wedged between the version's own controls. Over the panel, like
    // the four histories, with room for the lines it is made of.
    b.classList.add("on");
    nb.openSheet(`Changelog${comp ? ": " + comp : ""}`, [pane],
              () => b.classList.remove("on"));
    drawHTML(pane, `${skel("lines")}`);
    try{
      const j = await getJSON(`/api/changelog?project=${encodeURIComponent(project)}`
                            + `&component=${encodeURIComponent(comp)}`);
      if (j.error){ pane.textContent = `changelog: ${j.error}`; return; }
      if (j.text == null){
        // No file yet. The first line can be written here as well as by
        // a session's `aerie changelog add`: the editor used to sit dead
        // until Claude made the file.
        drawHTML(pane, `<div class="sub">no CHANGELOG.md yet: write the first line, or a session's first entry creates it</div>
            <div class="actbar"><input id="clFirst" maxlength="300" autocomplete="off"
              placeholder="what changed for the person using it, in their words">
              <button type="button" class="primary" id="clFirstGo">Create</button></div>`);
        pane.querySelector("#clFirstGo").onclick = async () => {
          const text = pane.querySelector("#clFirst").value.trim();
          if (!text) return notify("write the line first", true);
          const j2 = await postJSON("/api/changelog", {project, component: comp, action: "first", text});
          if (j2.error) return notify(j2.error, true);
          notify("CHANGELOG.md written; the next bump dates it");
          nbArtDrawChangelog(av, pane, comp, j2);
        };
        return;
      }
      nbArtDrawChangelog(av, pane, comp, j);
    }catch(e){ pane.textContent = "changelog: " + e; }
  });
}
