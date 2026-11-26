"use strict";
// ---- a space's Discord server (R293) -------------------------------------
// Two places, each where it lives (the connections rule): the space's
// settings hold the connection, its bot's token given once and sealed,
// never shown again, with Forget; the notebook's Discord view, in Ship,
// builds the server out from the repository's deploy/discord.yml: Pull
// writes the server as it stands into the file, Plan says what applying it
// would change (each change a person allows marked), Apply makes it so.
// A person's Apply is every change; a session's waits on a person for what
// removes, changes a permission or reaches members.
//
// Data: GET /api/discord?project= (never the token), read as the section or
// the view comes on and again as the discord token moves.

let rnDc = null;                  // the settings section's read, or null before it

function rnLoadDiscord(name){
  rnDc = null;
  rnDrawDiscord();
  return getJSON(`/api/discord?project=${encodeURIComponent(name)}`).then(j => {
    if (rnFor !== name) return;
    rnDc = j.error ? {error: j.error} : j;
    rnDrawDiscord();
  });
}

function rnDrawDiscord(){
  const sect = document.querySelector('details.rngroup[data-sect="rn:discord"]');
  const box = $("rnDcField");
  if (!sect || !box) return;
  const d = rnDc;
  sect.hidden = !d || !!d.error;
  if (sect.hidden) return;
  const lbl = `<label id="rnDcLabel">Server<span class="help" data-help="a Discord server this space builds out from its deploy/discord.yml: its bot's token, from the application's Bot page on Discord's developer portal, is kept sealed here and never shown again or handed to a session. A user account's token is refused" tabindex="0">?</span></label>`;
  if (d.connected){
    drawHTML(box, `${lbl}<div class="row rnreach"><span class="grow"><b>${esc(d.guild_name || d.guild)}</b> <span class="dim">connected ${
      d.at ? esc(ago(d.at)) : ""}${d.by ? ` by ${esc(principalWords(d.by))}` : ""}</span></span>${d.may ? `<button type="button" class="caution" data-dcforget>Forget</button>` : ""}</div>
      <div class="actbar"><span class="state">The Discord view builds it out.</span><span class="sp"></span><button type="button" data-dcopen>Open the Discord view</button></div>`);
  } else if (!d.may){
    drawHTML(box, `${lbl}<div class="hint">None connected; a person with this space's settings connects one.</div>`);
  } else {
    drawHTML(box, `${lbl}<div class="fgrid">
        <label class="setrow col ctlrow"><span class="lbl">Bot token</span><input id="rnDcToken" type="password" autocomplete="off" spellcheck="false"
          aria-label="the Discord bot's token"></label>
        <label class="setrow col ctlrow"><span class="lbl">Server ID</span><input id="rnDcGuild" autocomplete="off" spellcheck="false" inputmode="numeric"
          placeholder="the one it is in" data-ph-short="its only one" aria-label="the server's ID, where the bot is in several"></label>
      </div>
      <div class="actbar"><span class="state" id="rnDcSay"></span><span class="sp"></span><button type="button" class="primary" data-dcconnect>Connect</button></div>`);
  }
  box.querySelector("[data-dcopen]")?.addEventListener("click", () => { const n = rnFor; closeRename(); openNotebook(n, "discord"); });
  box.querySelector("[data-dcforget]")?.addEventListener("click", async e => {
    if (!await askYes(`Forget ${d.guild_name || "this server"}? Its token goes from here; the bot stays in the server until you kick it there.`, {verb: "Forget", danger: true})) return;
    busy(e.target, "Forgetting");
    const j = await postJSON("/api/discord", {project: rnFor, action: "forget"});
    unbusy(e.target, "Forget");
    if (j.error){ notify(j.error, true); return; }
    rnLoadDiscord(rnFor);
  });
  box.querySelector("[data-dcconnect]")?.addEventListener("click", async e => {
    const say = $("rnDcSay");
    busy(e.target, "Connecting");
    const j = await postJSON("/api/discord", {project: rnFor, action: "connect", token: $("rnDcToken").value, guild: $("rnDcGuild").value});
    unbusy(e.target, "Connect");
    if (j.error){
      drawHTML(say, `${esc(j.error)}${j.invite ? ` <a href="${esc(j.invite)}" target="_blank" rel="noopener">Invite it ↗</a>` : ""}`);
      say.classList.add("bad");
      return;
    }
    notify(`connected to ${j.guild_name}`);
    rnLoadDiscord(rnFor);
  });
}

// ---- the notebook's Discord view --------------------------------------------

function nbDiscordLoad(nb){
  const {$, project} = nb;
  $("dcPull").onclick = () => nbDiscordAct(nb, "pull");
  $("dcPlan").onclick = () => nbDiscordAct(nb, "plan");
  $("dcApply").onclick = () => nbDiscordAct(nb, "apply");
  return reading(`${project}:discord`, async () => {
    const d = await getJSON(`/api/discord?project=${encodeURIComponent(project)}`);
    nb.dcData = d;
    nbDiscordDraw(nb);
  });
}

function nbDiscordDraw(nb){
  const {$, project} = nb;
  const d = nb.dcData || {};
  if (d.error){ glanceBad($("dcHint"), "Discord", d.error); drawHTML($("dcList"), ""); return; }
  const live = !!d.connected, may = !!d.may;
  $("dcActs").hidden = !live || !may;
  $("dcApply").disabled = $("dcPlan").disabled = !d.layout;
  viewGlance($("dcHint"), [], live ? esc(d.guild_name || d.guild || "") : "");
  if (!live){
    drawHTML($("dcList"), `<div class="field"><div class="hint nbempty">No Discord server connected: ${
      may ? "connect one in this space's settings, under Discord." : "a person with this space's settings connects one."}</div>${
      may ? `<div class="actbar"><span class="sp"></span><button type="button" data-dcsettings>Discord settings</button></div>` : ""}</div>`);
    $("dcList").querySelector("[data-dcsettings]")?.addEventListener("click", () => renameProject(project, "project"));
    return;
  }
  const plan = nb.dcPlan;
  const planHtml = plan ? `<div class="field"><div class="lbl">${plan.applied ? "Applied" : "Applying deploy/discord.yml"}</div>${
    (plan.rows || []).length ? `<div class="rows">${plan.rows.map(r => `<div class="row"><span class="grow">${esc(r.said)}</span>${
      r.asks ? `<span class="pill warn" title="a session's apply waits on a person for this">asks</span>` : ""}${r.left ? `<span class="pill">left</span>` : ""}</div>`).join("")}</div>`
      : `<div class="hint">${esc(plan.said || "nothing to change: the server is as the file says")}</div>`}</div>` : "";
  const layoutHtml = d.layout ? "" : `<div class="field"><div class="hint">This repository has no <code>deploy/discord.yml</code> yet: Pull writes the server as it stands into it, to change and commit.</div></div>`;
  const past = (d.plans || []).map(p => `<div class="row"><span class="grow">${esc(p.said || "")}</span><span class="dim">${
    p.applied ? "applied" : "planned"} by ${esc(principalWords(p.by || ""))} · ${esc(ago(p.at))}</span></div>`).join("");
  drawHTML($("dcList"), layoutHtml + planHtml + (past ? docSection("discord", "plans", "Last plans", String((d.plans || []).length), `<div class="rows">${past}</div>`) : ""));
  wireSections($("dcList"));
}

async function nbDiscordAct(nb, act){
  const {$, project} = nb;
  const btn = $({pull: "dcPull", plan: "dcPlan", apply: "dcApply"}[act]);
  const word = {pull: "Pull", plan: "Plan", apply: "Apply"}[act];
  if (act === "pull" && nb.dcData?.layout && !await askYes("Write the server as it stands over this repository's deploy/discord.yml? Your changes to it that are not committed are lost.", {verb: "Pull"})) return;
  if (act === "apply" && !await askYes("Apply deploy/discord.yml to the server? Every change in the plan is made, removals and permissions included.", {verb: "Apply", danger: true})) return;
  busy(btn, {pull: "Pulling", plan: "Planning", apply: "Applying"}[act]);
  const j = await postJSON("/api/discord", {project, action: act, ...(act === "pull" ? {write: true} : {})});
  unbusy(btn, word);
  if (j.error){ notify(j.error, true); return; }
  if (act === "pull") notify("deploy/discord.yml written: the server as it stands, uncommitted");
  if (act === "plan") nb.dcPlan = {said: j.said, rows: (j.changes || []).map(c => ({said: c.said, asks: c.asks}))};
  if (act === "apply") nb.dcPlan = {applied: true, said: `${(j.done || []).length} made`,
                                    rows: [...(j.done || []).map(s => ({said: s})), ...(j.left || []).map(s => ({said: s, left: true}))]};
  nbDiscordLoad(nb);
}
