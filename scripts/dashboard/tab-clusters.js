// The Clusters page (R281 step 2), under Machines beside Nodes: the
// Kubernetes clusters a space may deploy to, each added once from a
// kubeconfig, its credential kept sealed on the controller and never shown
// again. Each cluster a section of its own that folds open (rows you open):
// its facts as its API last said, its namespaces and the space that owns
// each, and Test, Rename and Forget on its action bar. Add cluster is the
// form under them, or the page itself while there is none.
//
// Chrome from docSurface(); data from GET /api/clusters, read when the page
// opens and after each change.

"use strict";

let clustersData = null;         // {clusters: [...]}, or null before the first read
let clustersErr = "";
let clAdding = false;            // the Add form shown with clusters already kept
let clDraft = {name: "", text: ""};

function openClustersTab(){
  openTab({kind: "clusters", arg: "__clusters", label: "Clusters"});   // its kind's open reads the list
}

function loadClusters(){
  return reading("clusters", async () => {
    const j = await getJSON("/api/clusters");
    clustersErr = j.error || "";
    if (!j.error) clustersData = j;
  });
}

// A cluster's line on its heading: its version and nodes ready of all, or
// why its API did not answer the last time it was asked.
function clStatus(c){
  const f = c.facts || {};
  if (f.error) return "not answering";
  return f.version ? `${f.version} · ${f.ready} of ${f.nodes} ready` : "";
}

function clBody(c){
  const f = c.facts || {}, may = !!c.may;
  const ns = (f.namespaces || []).filter(n => !/^kube-/.test(n.name));
  const facts = factGrid([["API server", c.server], ["Signs in with", c.auth === "token" ? "a token" : "a client certificate"],
    ["Added", c.added_at ? `${ago(c.added_at)}${c.added_by ? ` by ${c.added_by}` : ""}` : ""],
    ["Asked", f.at ? ago(f.at) : "never"]].filter(([, v]) => v), "clfacts");
  const nsList = ns.length
    ? `<div class="field"><label>Namespaces</label><div class="sub">${ns.map(n => `${esc(n.name)}${n.space ? ` <span class="dim">(${esc(projLabel(n.space))})</span>` : ""}`).join(", ")}</div></div>`
    : "";
  return `<div class="field">${facts}</div>
    ${f.error ? `<div class="field"><div class="notice warn">${esc(f.error)}</div></div>` : ""}
    ${c.insecure ? `<div class="field"><div class="hint warn">Its certificate is not checked: the kubeconfig says insecure-skip-tls-verify.</div></div>` : ""}
    ${nsList}
    ${may ? `<div class="field"><div class="actbar"><span class="sp"></span>
      <button type="button" data-clact="test" data-cl="${esc(c.id)}">Test</button>
      <button type="button" data-clact="rename" data-cl="${esc(c.id)}">Rename</button>
      <button type="button" class="caution" data-clact="forget" data-cl="${esc(c.id)}">Forget</button></div></div>` : ""}`;
}

function clAddBody(canCancel){
  return `<div class="field"><div class="hint">A kubeconfig whose user carries a token or a client certificate; its current context is the cluster added. One that signs in through a cloud CLI (EKS, GKE, AKS, kubelogin) is refused: a ServiceAccount's token works, from <code>kubectl create token NAME --duration=8760h</code>. One that names files is flattened first: <code>kubectl config view --raw --flatten --minify</code>.</div></div>
    <div class="field">
      <div class="setrow col ctlrow">${lbl("clName", "Name", "what this cluster is called here, as spaces and the bell name it")}
        <input id="clName" type="text" autocomplete="off" spellcheck="false" value="${esc(clDraft.name)}" placeholder="production"></div>
      <div class="setrow col ctlrow">${lbl("clText", "Kubeconfig", "pasted, or read from its file; kept sealed on the controller and never shown again")}
        <textarea id="clText" rows="8" spellcheck="false" autocomplete="off" placeholder="apiVersion: v1&#10;kind: Config&#10;...">${esc(clDraft.text)}</textarea></div>
      <div class="actbar"><input type="file" id="clFile" hidden accept=".yaml,.yml,.json,.conf,.config,text/plain">
        <button type="button" id="clPick">Read its file</button><span class="sp"></span>${canCancel ? `<button type="button" class="stop" id="clCancel">Cancel</button>` : ""}
        <button type="button" class="primary" id="clAdd"${clDraft.name.trim() && clDraft.text.trim() ? "" : " disabled"}>Add cluster</button></div>
    </div>`;
}

function renderClustersInto(i){
  const d = docSurface(i, "clusters");
  if (!d) return;
  d.setBar("");
  if (clustersData === null){
    drawHTML(d.list, clustersErr ? `<div class="field"><div class="notice bad">${esc(clustersErr)}</div></div>`
      : skTpl(pageHead({title: "Clusters", line: [{value: GHOST, label: ""}]}) + docSection("clusters", "add", "Add cluster", "", skRows(2))));
    if (!clustersErr && !readBusy("clusters")) loadClusters();
    return;
  }
  const rows = clustersData.clusters || [], may = !!clustersData.may_add;
  const down = rows.filter(c => c.facts?.error).length;
  const head = pageHead({title: "Clusters", line: [{text: rows.length ? `${rows.length} cluster${rows.length === 1 ? "" : "s"}` : "none yet"},
    down ? {text: `${down} not answering`, tone: "warn"} : null]});
  const items = rows.map(c => docSection("clusters", `c:${c.id}`, c.name, clStatus(c), clBody(c),
    {item: true, cls: c.facts?.error ? "warn" : "", open: false})).join("");
  const add = !may ? (rows.length ? "" : `<div class="empty">No cluster is kept yet. Adding one is Clusters Write on every cluster.</div>`)
    : !rows.length || clAdding ? docSection("clusters", "add", "Add cluster", "", clAddBody(rows.length > 0))
    : `<div class="field addbar"><button type="button" id="clAddOpen">Add cluster</button></div>`;
  patch(d.list, head + items + add);
  wireSections(d.el);
  wireClusters(d.el);
}

function wireClusters(root){
  const name = root.querySelector("#clName"), text = root.querySelector("#clText"), add = root.querySelector("#clAdd");
  const wake = () => { if (add) add.disabled = !(clDraft.name.trim() && clDraft.text.trim()); };
  if (name) name.oninput = () => { clDraft.name = name.value; wake(); };
  if (text) text.oninput = () => { clDraft.text = text.value; wake(); };
  const file = root.querySelector("#clFile"), pick = root.querySelector("#clPick");
  if (pick && file) pick.onclick = () => file.click();
  if (file) file.onchange = async () => {
    const f = file.files?.[0];
    if (!f) return;
    if (f.size > 65536) return notify("that file is larger than a kubeconfig is", true);
    clDraft.text = await f.text();
    if (text) text.value = clDraft.text;
    wake();
  };
  const open = root.querySelector("#clAddOpen");
  if (open) open.onclick = () => { clAdding = true; readMoved("clusters"); drawPanes(); };
  const cancel = root.querySelector("#clCancel");
  if (cancel) cancel.onclick = () => { clAdding = false; clDraft = {name: "", text: ""}; readMoved("clusters"); drawPanes(); };
  if (add) add.onclick = async () => {
    busy(add, "Asking the cluster");
    const j = await postJSON("/api/clusters", {action: "add", name: clDraft.name.trim(), kubeconfig: clDraft.text});
    // Drawn again from the draft: the press given back as its markup was
    // drawn, before anything was typed, would come back dead.
    if (j.error){ notify(j.error, true); if (add.isConnected) unbusy(add, "Add cluster"); readMoved("clusters"); drawPanes(); return; }
    notify(`${j.cluster.name} added: ${clStatus(j.cluster)}`);
    clAdding = false; clDraft = {name: "", text: ""};
    await loadClusters();
  };
  root.querySelectorAll("[data-clact]").forEach(b => b.onclick = async () => {
    const id = b.dataset.cl, c = (clustersData?.clusters || []).find(x => x.id === id);
    if (!c) return;
    const act = b.dataset.clact;
    if (act === "forget"){
      const sp = c.spaces || [];
      if (!await askYes(`Forget ${c.name}? Its credential leaves this controller${sp.length ? `, and ${sp.join(", ")} deploy${sp.length === 1 ? "s" : ""} to it no more` : ""}. Nothing on the cluster changes.`)) return;
    }
    let body = {action: act, id};
    if (act === "rename"){
      const to = await askText(`Rename ${c.name}`, {verb: "Rename", value: c.name, label: "its name here"});
      if (!to || to === c.name) return;
      body.name = to;
    }
    busy(b, act === "test" ? "Asking" : act === "forget" ? "Forgetting" : "Renaming");
    const j = await postJSON("/api/clusters", body);
    if (j.error) notify(`${c.name}: ${j.error}`, true);
    else notify(act === "test" ? `${c.name}: ${clStatus(j.cluster)}` : act === "forget" ? `${c.name} forgotten` : "renamed");
    await loadClusters();
  });
}
