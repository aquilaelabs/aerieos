"use strict";
// ---- a space's Deploy section --------------------------------
// Where the space's software goes: its Kubernetes environments, each a
// cluster from the Clusters page, a namespace on it that AerieOS makes ready
// (the namespace, and a deployer confined to it), the registry its builds
// are pushed to, and when it deploys. The space's, for every repository in
// it (RN_SPACE_SECTS), in its settings dialog. A list of records (the
// record-lists rule): a row an environment with Edit at its right, Edit
// opening it in place, Add environment over the table; a record's Save
// writes it at once, its namespace made ready first, and the section has no
// Save of its own. Drawn once a cluster is kept or the space has an
// environment; a space with no repository has nothing to deploy and no
// section (page-surfaces.css, .rnwork).
//
// Data from GET /api/deploy?project=, read when the dialog opens.

let rnDeploy = null;              // {envs, clusters, kept, may, why}, or null before the read
let rnEnvEdit = null;             // {i, form}: the row open, i -1 for a new one

const ENV_COLS = [{label: "Environment"}, {label: "Where", w: "minmax(0,1fr)"}, {label: "Deploys"}, {act: true, w: "5rem"}];
const ENV_WHEN = [["hand", "By hand"], ["push", "On a push to a branch"], ["release", "On a release"]];
const SHIP_SAID = {chart: "deploys its Helm chart in <code>deploy/chart</code>", k8s: "deploys its manifests in <code>deploy/k8s</code>"};

function envWhenSaid(e){
  return e.when === "push" ? `on a push to ${e.branch}` : e.when === "release" ? "on a release" : "by hand";
}

// A namespace's name from the space's and the environment's: what a new
// record's field starts as, until the person types their own.
function envNamespaceFor(env){
  const base = String(projectName(rnFor) || rnFor || "").toLowerCase().replace(/[^a-z0-9-]+/g, "-").replace(/^-+|-+$/g, "");
  return `${base}-${env || "staging"}`.slice(0, 63).replace(/-+$/, "");
}

function rnLoadDeploy(name){
  rnDeploy = null; rnEnvEdit = null;
  rnDrawDeploy();
  // Not asked for where a role does not give Deploy Read here, and not
  // drawn: what a role does not give is not shown.
  if ((state?.projects || []).find(p => p.name === name)?.may_deploy === false) return;
  return getJSON(`/api/deploy?project=${encodeURIComponent(name)}`).then(j => {
    if (rnFor !== name) return;
    rnDeploy = j.error ? null : j;
    rnDrawDeploy();
  });
}

function rnDrawDeploy(focus){
  const sect = document.querySelector('details.rngroup[data-sect="rn:deploy"]');
  if (!sect) return;
  const d = rnDeploy;
  sect.hidden = !d || (!d.kept && !(d.envs || []).length);
  if (sect.hidden) return;
  const box = $("rnEnvRows"), ro = !d.may, ed = rnEnvEdit;
  const form = (f, i) => formBox({cls: "recform", attrs: `data-i="${i}"`, fields: [
      formField("envName", "Name", `<input id="envName" data-envf="name" value="${esc(f.name)}" autocomplete="off" spellcheck="false"
        placeholder="staging" maxlength="24" aria-label="the environment's name">`),
      formField("envCluster", "Cluster", `<select id="envCluster" data-envf="cluster" aria-label="the cluster it deploys to">${
        (d.clusters || []).map(c => `<option value="${esc(c.id)}"${c.id === f.cluster ? " selected" : ""}>${esc(c.name)}</option>`).join("")}</select>`),
      formField("envNs", "Namespace", `<input id="envNs" data-envf="namespace" value="${esc(f.namespace)}" autocomplete="off" spellcheck="false"
        maxlength="63" aria-label="its namespace on the cluster">`),
      formField("envReg", "Registry", `<input id="envReg" data-envf="registry" value="${esc(f.registry)}" autocomplete="off" spellcheck="false"
        placeholder="its git host's" data-ph-short="git host's" aria-label="the registry its images are pushed to">`),
      formField("envWhen", "Deploys", `<select id="envWhen" data-envf="when" aria-label="when it deploys">${
        ENV_WHEN.map(([v, w]) => `<option value="${v}"${v === f.when ? " selected" : ""}>${w}</option>`).join("")}</select>`),
      formField("envBranch", "Branch", `<input id="envBranch" data-envf="branch" value="${esc(f.branch)}"
        autocomplete="off" spellcheck="false" placeholder="main" aria-label="the branch whose pushes it deploys">`, {hidden: f.when !== "push", attrs: "data-envbranch"}),
      `<div class="fcell fwide"><label class="ndcap"><input type="checkbox" data-envf="production"${f.production ? " checked" : ""}> Production: a session's deploy here always asks a person first</label></div>`],
    foot: [i >= 0 ? `<button type="button" class="danger lead" data-envdel>Remove</button>` : "",
      `<button type="button" data-envcancel>Cancel</button>`, `<button type="button" class="primary" data-envsave>Save</button>`]});
  const rows = (d.envs || []).map((e, i) => `<div class="row rnreach rnenv${ed?.i === i ? " open" : ""}" data-i="${i}">${tblLine(ENV_COLS, [
      `${esc(e.name)}${e.production ? ` <span class="pill warn">production</span>` : ""}`,
      e.cluster_name ? `${esc(e.cluster_name)} <span class="dim">/</span> <code>${esc(e.namespace)}</code>`
        : `<span class="warn">its cluster is no longer kept</span>`,
      esc(envWhenSaid(e)),
      ed?.i === i || ro ? "" : `<button type="button" data-envedit="${i}">Edit</button>`])}${ed?.i === i ? form(ed.form, i) : ""}</div>`).join("");
  const fresh = ed?.i === -1 ? `<div class="row rnreach rnenv open" data-i="-1">${form(ed.form, -1)}</div>` : "";
  drawHTML(box, rows || fresh ? tblWrap(ENV_COLS, fresh + rows, "rnreaches rnenvs") : "");
  box.hidden = !rows && !fresh;
  $("rnEnvAdd").hidden = ro;
  $("rnEnvAdd").disabled = ed?.i === -1 || !(d.clusters || []).length;
  // The reason on the row (a dead control says why): who may, or that no
  // cluster is kept to pick from.
  $("rnEnvHint").textContent = ro ? `Changing them is ${d.why || "Space settings Write"}.`
    : !(d.clusters || []).length ? "No cluster is kept yet: an administrator adds one on the Clusters page, under Machines."
    : (d.envs || []).length ? "Saving one makes its namespace ready on its cluster, with a deployer that reaches that namespace alone."
    : "Each environment is a cluster from the Clusters page and a namespace on it this space alone deploys to.";
  const keep = () => {
    if (!rnEnvEdit) return;
    const o = box.querySelector(".rnenv.open");
    if (!o) return;
    for (const el of o.querySelectorAll("[data-envf]")){
      const k = el.dataset.envf;
      rnEnvEdit.form[k] = el.type === "checkbox" ? el.checked : el.value.trim();
    }
    // The namespace follows the name on a new record until it is typed in.
    if (rnEnvEdit.i < 0 && !rnEnvEdit.nsTyped){
      rnEnvEdit.form.namespace = envNamespaceFor(rnEnvEdit.form.name.toLowerCase());
      const ns = o.querySelector('[data-envf="namespace"]');
      if (ns && document.activeElement !== ns) ns.value = rnEnvEdit.form.namespace;
    }
    o.querySelector("[data-envbranch]").hidden = rnEnvEdit.form.when !== "push";
  };
  box.querySelectorAll("[data-envf]").forEach(el => {
    el.oninput = () => { if (el.dataset.envf === "namespace" && rnEnvEdit) rnEnvEdit.nsTyped = true; keep(); };
    el.onchange = keep;
  });
  box.querySelectorAll("[data-envedit]").forEach(b => b.onclick = () => {
    const e = d.envs[+b.dataset.envedit];
    rnEnvEdit = {i: +b.dataset.envedit, nsTyped: true, form: {name: e.name, cluster: e.cluster, namespace: e.namespace,
      registry: e.registry || "", when: e.when || "hand", branch: e.branch || "", production: !!e.production}};
    rnDrawDeploy(true);
  });
  box.querySelectorAll("[data-envcancel]").forEach(b => b.onclick = () => { rnEnvEdit = null; rnDrawDeploy(); });
  box.querySelectorAll("[data-envsave]").forEach(b => b.onclick = () => { keep(); rnEnvSave(b); });
  box.querySelectorAll("[data-envdel]").forEach(b => b.onclick = () => rnEnvRemove(b));
  if (focus) box.querySelector(".rnenv.open [data-envf]")?.focus();
  rnDrawShips();
  rnSpaceRelock();
}

// What each repository deploys (step 4): a sentence each, not a table's
// data, which wraps where it needs to, with Draft from the compose at its
// right where it has neither a chart nor manifests and has a compose file,
// for an account that may write its tree.
function rnDrawShips(){
  const rs = rnDeploy?.repos || [], field = $("rnShipField");
  field.hidden = !rs.length;
  if (!rs.length) return;
  drawHTML($("rnShipRows"), rs.map(r => `<div class="setrow ctlrow rnship"><span class="grow"><b>${esc(projLabel(r.name))}</b> ${
    SHIP_SAID[r.ships] || (r.compose ? "deploys nothing yet: a chart can be drafted from its compose file"
      : "deploys nothing yet: add a Helm chart in <code>deploy/chart</code> or manifests in <code>deploy/k8s</code>")}</span>${
    !r.ships && r.compose && r.may_draft ? `<button type="button" data-shipdraft="${esc(r.name)}">Draft from the compose</button>` : ""}</div>`).join(""));
  $("rnShipRows").querySelectorAll("[data-shipdraft]").forEach(b => b.onclick = () => rnShipDraft(b));
}

// Draft from the compose: the chart written into the repository's tree,
// uncommitted, and the line says what it now deploys.
async function rnShipDraft(btn){
  const repo = btn.dataset.shipdraft;
  busy(btn, "Drafting");
  const j = await postJSON("/api/deploy", {project: repo, action: "draft"});
  if (j.error){
    notify(j.error, true);
    if (btn.isConnected) unbusy(btn, "Draft from the compose");
    return;
  }
  const r = (rnDeploy?.repos || []).find(x => x.name === repo);
  if (r) r.ships = "chart";
  rnDrawShips();
  notify(`A chart is in ${projLabel(repo)}'s deploy/chart, uncommitted: read it and commit it`);
}

// Add environment: the same form at the table's top, the first cluster
// picked and its namespace named for the space.
function rnEnvAddOpen(){
  const c = (rnDeploy?.clusters || [])[0];
  rnEnvEdit = {i: -1, nsTyped: false, form: {name: "", cluster: c?.id || "", namespace: envNamespaceFor("staging"),
    registry: "", when: "hand", branch: "", production: false}};
  rnDrawDeploy(true);
}

// A record's Save: its namespace made ready on its cluster, then the
// space's list as the server answers it. The press rings while the cluster
// is asked; a refusal keeps the record open as it was typed, saying why.
async function rnEnvSave(btn){
  const {i, form} = rnEnvEdit, was = i >= 0 ? rnDeploy.envs[i].name : "";
  busy(btn, "Making it ready");
  const j = await postJSON("/api/deploy", {project: rnFor, action: "save", was, env: form});
  if (j.error){
    notify(j.error, true);
    if (btn.isConnected) unbusy(btn, "Save");
    return;
  }
  rnDeploy.envs = j.envs;
  rnEnvEdit = null;
  rnDrawDeploy();
  notify(`${form.name.toLowerCase()} is ready to deploy to`);
}

async function rnEnvRemove(btn){
  const e = rnDeploy.envs[rnEnvEdit.i];
  if (!await askYes(`Remove ${e.name}? This space stops deploying to it; its namespace and what runs in it stay on the cluster.`,
    {verb: "Remove", danger: true})) return;
  busy(btn, "Removing");
  const j = await postJSON("/api/deploy", {project: rnFor, action: "remove", name: e.name});
  if (j.error){
    notify(j.error, true);
    if (btn.isConnected) unbusy(btn, "Remove");
    return;
  }
  rnDeploy.envs = j.envs;
  rnEnvEdit = null;
  rnDrawDeploy();
}
