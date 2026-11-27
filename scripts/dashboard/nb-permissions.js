// The notebook's Permissions view: everything a session may do on this
// project, in one place (the operator, 22 Oct: the dials were split between
// the Settings view's Agents may and the Git view's push policy). Beside
// Overview and Settings in the Overview group.
// One classic script beside index.html, the shape tab-*.js has (docs/nodes.md
// §13): same page, same global scope, one file per notebook view (R60).
//
// A factory rather than a script that runs: makeNotebook calls it per
// notebook with the notebook's element lookup, its state object and its
// project, and takes back the two functions the rest of the notebook calls.

"use strict";

function nbPermsView({$, nb, project, root}){
  const view = () => root.querySelector('.nbview[data-view="permissions"]');
  // The project settings' own section (rn:claude), lent to this view while it
  // is on screen and handed back to its place in the form on the way out
  // (rnDialsHome), so there is one set of fields, one set of handlers and its
  // own Save and Revert, as the Settings view lends the whole form.
  function lendDials(){
    const host = view()?.querySelector(".permdials > .box");
    // Not a fading view's still copy of it (ghostOf), which holds one too.
    const sect = [...document.querySelectorAll('details[data-sect="rn:claude"]')].find(d => !d.closest(".fghost"));
    if (!host || !sect) return;
    if (sect.parentElement === host && rnFor === project) return;
    rnDialsHome();
    // The form read for this project first, as the Settings view does.
    if (rnFor !== project || rnHost) renameProject(project);
    document.getElementById("rnmodal").hidden = true;      // the page's, outside this notebook
    sect.parentElement.insertBefore(document.createComment(RN_DIALS_MARK), sect);
    sect.open = true;
    host.appendChild(sect);
    // Its edits and its Save heard here too, where they no longer bubble to
    // the form's own box.
    rnWireBox(host);
    rnBars();
  }

  // What a session may do with the remote (roadmap R36), moved here from
  // the Git view: staged until Apply, enforced on the relay; a local commit
  // or merge cannot be forbidden, and the bar says so. The third is whether
  // a push with lines that look sensitive waits on the bell for a person
  // (R219) or goes without the hold.
  let draft = {};
  const GITPOL_DEFAULT = {push: "allow", main: "deny", scan: "hold"};   // prefs.GITPOL_DEFAULT
  function drawPush(){
    const host = view()?.querySelector(".permgit");
    if (!host) return;
    const p = (state?.projects || []).find(x => x.name === project);
    const locked = !!p?.locked_me || !!projWriteWhy(project);
    // Each part the space's default until this repository sets it apart
    // (R294 step 4): "as the space (word)" first, as every dial here is.
    const saved = {}, pol = {...(p?.prefs?.gitpol || {})};
    for (const k of Object.keys(GITPOL_DEFAULT)) saved[k] = rnDialVal(p, `gitpol.${k}`, GITPOL_DEFAULT[k]);
    const pick = k => k in draft ? draft[k] : saved[k];
    const opts = (k, modes) => optionList(rnDialChoices(p, `gitpol.${k}`, modes.map(m => [m, m]), GITPOL_DEFAULT[k]), pick(k));
    const dirty = Object.keys(draft).length > 0;
    // One form (R301), as Agents may beside it is: its three dials, Apply at
    // the foot.
    const body = `<div class="row stack2 gpolicy"><div class="grow">${formBox({fields: [
        formField("permPush", "Push its branches", `<select id="permPush" data-gitpol="push"${locked ? " disabled" : ""}>${opts("push", ["allow", "deny"])}</select>`),
        formField("permMain", "Push to its main branch", `<select id="permMain" data-gitpol="main"${locked ? " disabled" : ""}>${opts("main", ["allow", "deny"])}</select>`),
        formField("permScan", "Hold a push that looks sensitive", `<select id="permScan" data-gitpol="scan"${locked ? " disabled" : ""}>${opts("scan", ["hold", "off"])}</select>`,
          {help: "a push whose added lines look like a token, key, password, email or IP address waits until a person reads it and approves it"})],
        state: `<span class="state">${locked ? "this space is locked: its owner changes these" : `its own branches, one at a time ${helpIcon("Applies to pushes only. Tags, deletions and remote-only branches stay yours; commits and merges here are always allowed.")}`}</span>`,
        foot: [`<button type="button" class="permGitApply"${dirty && !locked ? "" : " disabled"}>Apply</button>`]})}</div></div>`;
    const html = docSection("permissions", "push", "Pushing", `${pol.push || "allow"} · ${pol.main || "deny"}${pol.scan === "off" ? " · unheld" : ""}`, body);
    // Patched (R244): a pick not yet applied stays, and a read that brings
    // nothing new writes nothing.
    if (!patch(host, html)) return;
    wireSections(host);
    host.querySelectorAll("[data-gitpol]").forEach(sel => sel.onchange = () => {
      if (sel.value === saved[sel.dataset.gitpol]) delete draft[sel.dataset.gitpol];
      else draft[sel.dataset.gitpol] = sel.value;
      const b = host.querySelector(".permGitApply"); if (b) b.disabled = !Object.keys(draft).length;
    });
    const pa = host.querySelector(".permGitApply");
    if (pa) pa.onclick = async () => {
      busy(pa, "Applying");
      try{
        // Only what changed: each part sent is this repository's own, and
        // "inherit" gives one back to the space (prefs.set_prefs).
        const j = await postJSON("/api/prefs", {project, gitpol: {...draft}});
        if (j.error) return notify(j.error, true);
        draft = {};
        notify("saved");
        refresh();
      }catch(e){ notify("policy: " + failWords(e), true); }
      finally{ if (pa.isConnected) unbusy(pa, "Apply"); drawPush(); }
    };
  }

  // On the git host (R188): each ability with what the project's token
  // says (its kept measure) and the project's own Allow or Deny over it,
  // staged until Apply as Pushing is. The token sets what is possible; a
  // Deny here takes an ability away whatever the token allows.
  let host = null, hostDraft = {}, hostFor = "";
  // What is picked and not applied is unsaved work, as anything staged in
  // the notebook is: the leave and close questions count it, and answering
  // them drops it. Showing the view again reads the host's facts afresh and
  // keeps it, so nothing but that answer, Apply or the pick put back ends it.
  nb.stage("permissions:githost", {
    count: () => Object.keys(hostDraft).length,
    revert: () => { if (!Object.keys(hostDraft).length) return; hostDraft = {}; if (host) drawHost(); }});
  function loadHost(measure){
    return reading(`${project}:host`, async () => {
      try{
        const j = measure ? await postJSON("/api/forge-access", {project, action: "measure"})
                          : await getJSON("/api/forge-access?project=" + encodeURIComponent(project));
        if (j.error) throw new Error(j.error);
        host = j; hostFor = project;
      }catch(e){ host = {error: failWords(e)}; hostFor = project; }
      drawHost();
    });
  }
  function drawHost(){
    const el = view()?.querySelector(".permhost");
    if (!el) return;
    if (hostFor !== project){ host = null; loadHost(false); }
    const p = (state?.projects || []).find(x => x.name === project);
    const locked = !!p?.locked_me || !!projWriteWhy(project);
    const m = host?.measure || null, rows = host?.rows || [];
    const dirty = Object.keys(hostDraft).length > 0;
    const facts = !host ? `<div class="field">${skRows(2)}</div>`
      : host.error ? `<div class="field"><div class="sub bad">${esc(host.error)}</div></div>`
      : `<div class="row stack2"><div class="grow">${m && m.at ? `<div>${esc(m.forge || m.host || "")} ${esc(m.repo || "")}${m.login ? ` as <b>${esc(m.login)}</b>` : ""}${m.token ? `, a ${esc(m.token)} token` : ""}${m.expires ? `, expiring ${esc(m.expires)}` : ""}</div>
          <div class="sub">measured ${esc(ago(m.at))}${m.error ? ` · <span class="bad">${esc(m.error)}</span>` : ""}</div>${(m.notes || []).map(n => `<div class="sub">${esc(n)}</div>`).join("")}`
          : `<div class="sub">${m?.error ? esc(m.error) : "not measured yet: Measure asks the host what this space's token may do, changing nothing"}</div>`}</div>
          <div class="actbar"><button type="button" class="permHostMeasure"${locked ? " disabled" : ""}>Measure</button></div></div>`;
    const list = rows.map(r => {
      const own = rnDialVal(p, `forgepol.${r.id}`, r.set);
      const set = hostDraft[r.id] || own;
      const tok = r.token === true ? `<span class="ok">the token may</span>` : r.token === false
        ? `the token may not: it needs ${esc(r.needs)}` : "not measured";
      const how = r.verbs.length ? `aerie forge ${r.verbs.join(", ")}` : r.how;
      // One another setting governs has no switch here, only where it is
      // set (B559): its deny was told to sessions and enforced nowhere.
      return `<div class="row"><div class="grow"><div>${esc(r.label)}</div><div class="sub">${tok}${how && !r.fixed ? ` · ${esc(how)}` : ""}</div></div>
        ${r.fixed ? `<span class="state">${esc(r.fixed)}</span>`
          : `<label class="pick"><select aria-label="${esc(r.label)}" data-forgepol="${esc(r.id)}" data-own="${esc(own)}"${locked ? " disabled" : ""}>${optionList(rnDialChoices(p, `forgepol.${r.id}`, [["allow", "allow"], ["deny", "deny"]], r.set), set)}</select></label>`}</div>`;
    }).join("");
    const foot = rows.length ? `<div class="row"><div class="grow"><span class="state">${locked ? "this space is locked: its owner changes these"
      : "a Deny here takes an ability away whatever the token allows; the token decides what is possible"}</span></div>
      <div class="actbar"><button type="button" class="permHostApply"${dirty && !locked ? "" : " disabled"}>Apply</button></div></div>` : "";
    const on = rows.filter(r => r.token !== false && (r.fixed || (hostDraft[r.id] || r.set) === "allow")).length;
    const html = docSection("permissions", "githost", "On the git host",
      rows.length ? `${on} of ${rows.length} allowed` : "", facts + list + foot);
    if (!patch(el, html)) return;
    wireSections(el);
    el.querySelectorAll("[data-forgepol]").forEach(sel => sel.onchange = () => {
      if (sel.value === sel.dataset.own) delete hostDraft[sel.dataset.forgepol]; else hostDraft[sel.dataset.forgepol] = sel.value;
      const b = el.querySelector(".permHostApply"); if (b) b.disabled = !Object.keys(hostDraft).length;
    });
    const mb = el.querySelector(".permHostMeasure");
    if (mb) mb.onclick = async () => { busy(mb, "Measuring"); await loadHost(true); };
    const ab = el.querySelector(".permHostApply");
    if (ab) ab.onclick = async () => {
      busy(ab, "Applying");
      try{
        const j = await postJSON("/api/prefs", {project, forgepol: {...hostDraft}});
        if (j.error) return notify(j.error, true);
        hostDraft = {};
        notify("saved");
        await loadHost(false);
      }catch(e){ notify("git host: " + failWords(e), true); }
      finally{ if (ab.isConnected) unbusy(ab, "Apply"); }
    };
  }

  // The glance (R109): how many of the dials a session meets on its own,
  // asked first, or not at all, read off the section's own pickers, and the
  // push policy as its line.
  function drawGlance(){
    const v = view(), hint = v?.querySelector(".nbglance");
    if (!hint) return;
    const n = {auto: 0, ask: 0, deny: 0};
    // A dial on "as the project" counts as what it inherits (R208 step 6).
    v.querySelectorAll('details[data-sect="rn:claude"] select').forEach(s => {
      const w = s.value === "inherit" ? (s.dataset.inherit || "").replace(/ me$/, "") : s.value;
      if (w in n) n[w]++;
    });
    const pol = {...((state?.projects || []).find(x => x.name === project)?.prefs?.gitpol || {})};
    viewGlance(hint, [{label: "on its own", value: n.auto}, {label: "asks first", value: n.ask},
                      {label: "may not", value: n.deny}],
      // In words, not the dials' values ("pushing its branches allow, to main deny").
      `${{allow: "pushes its branches", ask: "asks before pushing its branches", deny: "never pushes its branches"}[pol.push || "allow"] || ""}; ${
        {allow: "pushes to main", ask: "asks before pushing to main", deny: "never pushes to main"}[pol.main || "deny"] || ""}`);
  }
  function loadPerms(){ lendDials(); drawPush(); hostFor = ""; drawHost(); drawGlance(); }
  function leavePerms(){ rnDialsHome(); }
  return {loadPerms, leavePerms, drawPush: () => { drawPush(); drawGlance(); }};
}
