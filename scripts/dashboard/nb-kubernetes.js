"use strict";
// ---- the notebook's Kubernetes view (R281 step 5) ---------------------------
// What runs in the space's Kubernetes environments: an environment a
// section, its status the workloads ready of all; on its bar Deploy (a
// branch, tag or commit) and Roll back; its workloads as a table, each with
// ready of desired, the version its image is tagged with, where it answers,
// and Restart and Scale; their pods as a table under it, state, restarts and
// node, each pod's Logs a tab in the dock; and its last deploys. Every read
// and press goes through the environment's own deployer (kubeview.py), so
// nothing outside its namespace is drawn or touched.
//
// Data: GET /api/deploy (the environments, their deploys, who may change
// them) and GET /api/kubernetes for each environment; read as the view
// comes on and again as the deploy token moves (an environment saved, a
// deploy started or ended).

const KB_WL_COLS = [{label: "Workload"}, {label: "Ready", num: true}, {label: "Version"}, {label: "Answers at", w: "minmax(0,1.4fr)"},
                    {act: true, w: "auto"}];
const KB_POD_COLS = [{label: "Pod"}, {label: "State"}, {label: "Restarts", num: true}, {label: "Node"}, {act: true, w: "auto"}];
const KB_DEP_COLS = [{label: "When"}, {label: "What"}, {label: "By"}, {label: "State"}];

function nbKubeLoad(nb){
  const {$, project} = nb;
  $("kbSettings").onclick = () => nbKubeSettings(project);
  return reading(`${project}:kubernetes`, async () => {
    const d = await getJSON(`/api/deploy?project=${encodeURIComponent(project)}`);
    if (d.error){ glanceBad($("kbHint"), "Kubernetes", d.error); drawHTML($("kbList"), ""); return; }
    const envs = d.envs || [];
    const got = await Promise.all(envs.map(e => getJSON(`/api/kubernetes?project=${encodeURIComponent(project)}&env=${encodeURIComponent(e.name)}`)));
    nb.kbData = {deploy: d, status: Object.fromEntries(envs.map((e, i) => [e.name, got[i]]))};
    nbKubeDraw(nb);
  });
}

// The space's settings opened at its Deploy section, where environments
// are added and changed.
function nbKubeSettings(project){
  renameProject(project, "project");
  const at = Date.now();
  const look = () => {
    const d = document.querySelector('#rnmodal:not([hidden]) details[data-sect="rn:deploy"]:not([hidden])');
    if (d){ d.open = true; d.scrollIntoView({block: "start"}); return; }
    if (Date.now() - at < 5000) requestAnimationFrame(look);
  };
  requestAnimationFrame(look);
}

function nbKubeDraw(nb){
  const {$, project} = nb;
  const {deploy: d, status} = nb.kbData || {};
  const envs = d?.envs || [];
  const mayDeploy = !!d?.may_deploy;
  const all = envs.flatMap(e => status[e.name]?.workloads || []);
  const ready = all.filter(w => w.desired > 0 && w.ready >= w.desired).length;
  viewGlance($("kbHint"), all.length ? [{label: "ready", value: ready, sub: `of ${all.length} workload${all.length === 1 ? "" : "s"}`}] : [],
             envs.length ? `${envs.length} environment${envs.length === 1 ? "" : "s"}` : "");
  if (!envs.length){
    drawHTML($("kbList"), `<div class="field"><div class="hint nbempty">${d?.kept
      ? "No environment yet: add one in this space's settings, under Deploy."
      : `No cluster is kept yet: an administrator adds one on the ${pageLink("clusters", "Clusters page")}, then an environment is added in this space's settings, under Deploy.`}</div></div>`);
    return;
  }
  drawHTML($("kbList"), envs.map(e => nbKubeEnvHtml(project, e, status[e.name] || {}, mayDeploy)).join(""));
  nbKubeWire(nb);
}

function nbKubeEnvHtml(project, e, st, may){
  const wl = st.workloads || [];
  const ok = wl.filter(w => w.desired > 0 && w.ready >= w.desired).length;
  const bar = may ? `<div class="actbar">${(e.deploys || []).some((x, i) => i > 0 && x.state === "succeeded")
      ? `<button type="button" data-kbroll="${esc(e.name)}">Roll back</button>` : ""}
    <button type="button" class="primary" data-kbdeploy="${esc(e.name)}">Deploy</button></div>` : "";
  const where = `<div class="sub dim">${esc(e.cluster_name || "its cluster is no longer kept")} / <code>${esc(e.namespace)}</code>${
    e.production ? ` <span class="pill warn">production</span>` : ""}</div>`;
  const body = st.error ? `<div class="sub bad">${esc(st.error)}</div>`
    : !wl.length ? `<div class="hint">Nothing runs in ${esc(e.namespace)} yet: Deploy sends the repository's chart or manifests there.</div>`
    : tblWrap(KB_WL_COLS, wl.map(w => tblLine(KB_WL_COLS, [
        `${esc(w.name)} <span class="dim">${esc(w.kind)}</span>`,
        `<span class="${w.desired > 0 && w.ready < w.desired ? "warn" : ""}">${w.ready} of ${w.desired}</span>`,
        esc(w.version || ""),
        esc((w.addresses || []).join(", ")),
        may ? `<button type="button" data-kbrestart="${esc(e.name)}:${esc(w.kind)}:${esc(w.name)}">Restart</button>${
          w.scales ? `<button type="button" data-kbscale="${esc(e.name)}:${esc(w.kind)}:${esc(w.name)}:${w.desired}">Scale</button>` : ""}` : ""],
        "div", "row")).join(""), "kbwl")
      + (wl.some(w => (w.pods || []).length) ? `<h4 class="kbsub">Pods</h4>` + tblWrap(KB_POD_COLS, wl.flatMap(w => (w.pods || []).map(p => tblLine(KB_POD_COLS, [
        esc(p.name),
        `<span class="${/Running|Succeeded/.test(p.state) && p.ready === p.of ? "" : "warn"}">${esc(p.state)}${p.of ? ` <span class="dim">${p.ready}/${p.of}</span>` : ""}</span>`,
        `<span class="${p.restarts ? "warn" : ""}">${p.restarts}</span>`,
        esc(p.node || ""),
        `<button type="button" data-kblogs="${esc(e.name)}:${esc(p.name)}">Logs</button>`], "div", "row"))).join(""), "kbpods") : "");
  const deps = (e.deploys || []).slice(0, 5);
  const hist = deps.length ? `<h4 class="kbsub">Deploys</h4>` + tblWrap(KB_DEP_COLS, deps.map(x => tblLine(KB_DEP_COLS, [
      esc(ago(x.at)),
      `${esc(x.tag || (x.commit || "").slice(0, 12))}${x.ref && x.ref !== x.tag ? ` <span class="dim">${esc(x.ref)}</span>` : ""}`,
      esc(principalWords(x.by)),
      jobStatePill({state: x.state === "queued" ? "queued" : x.state})], "div", "row")).join(""), "kbdeps") : "";
  return docSection("kb", e.name, e.name, st.error ? "not answering" : wl.length ? `${ok} of ${wl.length} ready` : "nothing deployed",
                    bar + where + body + hist, {cls: st.error ? "bad" : wl.length && ok < wl.length ? "warn" : ""});
}

function nbKubeWire(nb){
  const {$, project} = nb;
  const box = $("kbList");
  const post = (body, btn, word) => { busy(btn, word); return postJSON("/api/kubernetes", {project, ...body}); };
  box.querySelectorAll("[data-kbdeploy]").forEach(b => b.onclick = async () => {
    const e = (nb.kbData.deploy.envs || []).find(x => x.name === b.dataset.kbdeploy);
    const ref = await askText(`Deploy which branch, tag or commit to ${e.name}?`, {value: e.branch || "main", verb: "Deploy", label: "Branch, tag or commit"});
    if (!ref) return;
    busy(b, "Deploying");
    const j = await postJSON("/api/deploy", {project, action: "deploy", env: e.name, ref});
    if (b.isConnected) unbusy(b, "Deploy");
    if (j.error) return notify(j.error, true);
    notifyJob(j.job, `Deploying ${j.tag} to ${e.name}`, () => nbKubeLoad(nb));
    nbKubeLoad(nb);
  });
  box.querySelectorAll("[data-kbroll]").forEach(b => b.onclick = async () => {
    const e = (nb.kbData.deploy.envs || []).find(x => x.name === b.dataset.kbroll);
    const good = (e.deploys || []).find((x, i) => i > 0 && x.state === "succeeded");
    if (!await askYes(`Roll ${e.name} back to ${good.tag}? It is deployed again from its own commit.`, {verb: "Roll back"})) return;
    busy(b, "Rolling back");
    const j = await postJSON("/api/deploy", {project, action: "rollback", env: e.name});
    if (b.isConnected) unbusy(b, "Roll back");
    if (j.error) return notify(j.error, true);
    notifyJob(j.job, `Rolling ${e.name} back to ${j.tag}`, () => nbKubeLoad(nb));
    nbKubeLoad(nb);
  });
  box.querySelectorAll("[data-kbrestart]").forEach(b => b.onclick = async () => {
    const [env, kind, name] = b.dataset.kbrestart.split(":");
    if (!await askYes(`Restart ${name}? Its pods are made again one at a time.`, {verb: "Restart"})) return;
    const j = await post({env, action: "restart", kind, name}, b, "Restarting");
    if (b.isConnected) unbusy(b, "Restart");
    if (j.error) return notify(j.error, true);
    notify(`${name} is restarting`);
    nbKubeLoad(nb);
  });
  box.querySelectorAll("[data-kbscale]").forEach(b => b.onclick = async () => {
    const [env, kind, name, now] = b.dataset.kbscale.split(":");
    const n = await askText(`How many of ${name} should run?`, {value: now, verb: "Scale", label: "Replicas"});
    if (n === null || n === undefined || n === "") return;
    const j = await post({env, action: "scale", kind, name, replicas: n}, b, "Scaling");
    if (b.isConnected) unbusy(b, "Scale");
    if (j.error) return notify(j.error, true);
    notify(`${name} runs ${j.replicas} now`);
    nbKubeLoad(nb);
  });
  box.querySelectorAll("[data-kblogs]").forEach(b => b.onclick = () => {
    const [env, pod] = b.dataset.kblogs.split(":");
    openLogTab(`log:pod:${project}:${env}:${pod}`, `Log: ${pod}`);
  });
}
