// The Jobs tab: the queue, readable and stoppable. Phase 4 of docs/nodes.md
//: every job the controller has taken (an exec on a node, a compose action
// on a dev instance, an agent self-update), where it was placed, what it is
// doing now, how it ended, and its log. Its own classic script beside
// index.html, per the new-surface rule (§13): same page, same global scope,
// one file per surface.
//
// Chrome comes from docSurface() and the hard rules are held by uniform.mjs;
// this file only fills slots. Data comes from /api/v1/jobs, fetched when the
// "jobs" revision token moves, never from the status poll. The one verb is
// Cancel; a job is never edited, and a finished one is history (door 1).

"use strict";

let jobsList = null;             // last answer, or null before the first
let jobsNodes = {};              // id -> name, from the same answer
let jobsErr = "";
// The chip in force: "" for every job, else a state group's key (JOB_GROUPS).
// A view, never a setting: kept for the page's life, nothing saved; Home's
// "failed today" opens the page on "failed-today" by its address.
let jobsShow = "";
const jobsOpen = new Set();      // ids whose log is unfolded
const jobsLogs = {};             // id -> the log fetched for an unfolded row
let jobsFocus = "";              // a row to bring into view on the next draw (openJob)
const jobsLogsEnded = new Set();  // open rows whose log was read after their job ended
let jobsMarked = "";             // ...and to mark, across redraws, until another is opened

function openJobsTab(){
  // The kind's open hook loads; a second load here asked the queue twice
  // for one press (the quiet-page invariant in uniform.mjs holds it now).
  openTab({kind: "jobs", arg: "__jobs", label: "Jobs"});
}

// One job's row, its log open and brought into view: what a row on Home's
// Last jobs opens.
function openJob(id){
  jobsOpen.add(id);
  jobsFocus = jobsMarked = id;
  openJobsTab();
  loadJobs();
}

function loadJobs(){
  return readKept("jobs", "/api/v1/jobs?n=100", {
    err: said => { jobsErr = said; },
    keep: () => { jobsList = jobsList || []; },
    land: async j => {
      jobsList = j.jobs || [];
      jobsNodes = j.nodes || {};
      // An unfolded log follows its job: refetched with the list, so a running
      // job's tail moves on the same revision that moves its row.
      await Promise.all([...jobsOpen].map(async id => {
        // One that has ended and been read already writes no more:
        // its row was read again on every read of the list.
        const row = jobsList.find(x => x.id === id);
        if (row && ["succeeded", "failed", "canceled"].includes(row.state) && jobsLogs[id] !== undefined
            && jobsLogsEnded.has(id)) return;
        if (row && ["succeeded", "failed", "canceled"].includes(row.state)) jobsLogsEnded.add(id);
        // Its last 4,000 characters, which is all a row draws.
        const r = await getJSON(`/api/v1/jobs?id=${encodeURIComponent(id)}&tail=4000`);
        // A job answers with its own fields, `error` among them for one that
        // failed; a refused request has no id. Reading a failed job's error
        // as the request's kept its log out, so every failed job read "(this
        // job wrote nothing)".
        if (r.id) jobsLogs[id] = r.log || "";
      }));
    },
  });
}

// A job's action: a refusal said, the jobs read again, the answer back.
function jobAct(body){ return poster("/api/v1/jobs", {reload: () => loadJobs()})(body); }

// What the job is, in the words the operator used to start it: a compose
// job says its action and instance, an exec says its command.
function jobTitle(j){
  const s = j.spec || {};
  if (j.type === "compose")
    return `${esc(s.action || "compose")} ${esc(j.project ? projLabel(j.project) : "")}${
      s.instance && s.instance !== "main" ? "/" + esc(s.instance) : ""}`;
  if (j.type === "self-update") return "agent self-update";
  if (j.type === "system") return `apply ${esc(s.apply || "config")} on the node`;
  if (j.type === "toolchain") return `${esc(s.action || "install")} ${esc((s.names || []).join(", "))}`;
  if (j.type === "image") return (s.images || []).length > 1
    ? `${esc(s.action || "add")} ${s.images.length} images` : `${esc(s.action || "add")} image ${esc(s.image || "")}`;
  // A job its caller named in words (nodes.run_wait's title): a shell line
  // is not what a person reads a job list for (the design pass, 4 Oct).
  if (s.title) return esc(s.title);
  // The kinds with no command of their own, each in the words of what it
  // did: a storage walk read as a bare "exec".
  if (j.type === "storage") return "measure the disks";
  // Each coding agent's sign-in, sign-out and install by its own name, every
  // agent's job named <id>-login, -logout and -update.
  // A pack's agent's sign-in and sign-out are one pair of jobs for all of
  // them, the spec naming which.
  const pk = (j.type === "agent-login" || j.type === "agent-logout") && AGENTS.find(a => a.id === s.agent);
  if (pk) return `sign ${esc(pk.name)} ${j.type === "agent-login" ? "in" : "out"}`;
  const ag = (j.type || "").match(/^([a-z]+)-(login|logout|update)$/);
  // By its id or by its program: OpenCode's jobs are named after the
  // program (opencode-update) and its id is open, so its row read "exec".
  const who = ag && AGENTS.find(a => a.id === ag[1] || a.command === ag[1]);
  if (who) return ag[2] === "login" ? `sign ${esc(who.name)} in` : ag[2] === "logout" ? `sign ${esc(who.name)} out`
    : `${s.action === "remove" ? "remove" : "update"} ${esc(who.product)}`;
  if (j.type === "sign") return `sign ${esc(s.file || "a build")}`;
  if (j.type === "tell"){
    const text = String(s.text || "").replace(/\s+/g, " ");
    return `tell ${esc(jobSessionWords(s.session))}: "${esc(text.slice(0, 60))}${text.length > 60 ? "…" : ""}"`;
  }
  if (j.type === "cache-clear") return `clear ${s.project ? esc(projLabel(s.project)) + "'s caches" : "every cache"}`;
  if (j.type === "phones-idle") return "the idle phones' quick-boot snapshots";
  if (j.type === "avd-remove") return `remove ${esc(projLabel(s.project || ""))}'s phone ${esc(s.name || "")}`;
  // Run on another node of the project's set because its primary was not
  // up: said on the row, since the row is where it is looked for.
  const stood = s.fell_over ? " (its primary was not up)" : "";
  const argv = (Array.isArray(s.argv) ? s.argv.join(" ") : "") + stood;
  // A job with a source is a build of that project's tree, and says so
  // before the command (docs/nodes.md §6).
  const src = j.source?.digest ? `${esc(projLabel(j.project || s.project || ""))} · ` : "";
  return `${src}exec ${esc(argv.slice(0, 80))}${argv.length > 80 ? "…" : ""}`;
}

// The session a tell job typed into, by its project rather than by its
// tmux name: "u_525cbd90~claude-hello" is the machine's spelling,
// "Claude on hello" the person's. A shell is named for its project too.
function jobSessionWords(name){
  if (!name) return "a session";
  const b = tmuxBase(name);
  let m;
  if (agentOfSession(b)) return agentSessionWords(name);
  if ((m = /^shell-(.+)-\d+$/.exec(b))) return `a shell on ${projLabel(projFor(m[1]) ?? m[1])}`;
  return b;
}

// Where it stands, in a word: its pill's, and its row's name for a screen reader.
function jobWord(j){
  return j.state === "running" && j.cancel ? "stopping"
       : j.state === "running" && j.step ? j.step : j.state;
}
function jobStatePill(j){
  const cls = {succeeded: "ok", failed: "bad", running: "note",
               assigned: "note", canceled: "warn"}[j.state] || "";
  // A running job is live, and glows.
  const live = j.state === "running" || j.state === "assigned" ? " live" : "";
  return `<span class="pill ${cls}${live} jbstate">${esc(jobWord(j))}</span>`;
}

// Where and when: the node by name, and the timings that are known: a
// queued job has only its wait so far, a finished one how long it took.
// The table's cells: when it last moved, and how long it ran
// with its exit code when that was not 0.
function jobNode(j){
  return esc(jobsNodes[j.node] || (j.node ? j.node : "any node that fits"));
}
// A job not over says the clock time it has been waiting or running since
// ("started just now" was cut to "started just" in
// the column, and said nothing a person could check), on a page that
// redraws only when something moves; one that ended, how long ago.
function jobSince(t){
  const day = ms => fmtTime(ms, {dateStyle: "short"});
  return day(t * 1000) === day(Date.now()) ? fmtTime(t * 1000, {hour: "2-digit", minute: "2-digit"}) : ago(t);
}
function jobWhen(j){
  if (j.state === "queued") return `queued ${jobSince(j.queued)}`;
  if (j.started && !j.ended) return `since ${jobSince(j.started)}`;
  return ago(j.ended || j.queued);
}
function jobTook(j){
  const took = j.started && j.ended ? `${Math.max(1, j.ended - j.started)}s` : "";
  // Said once: a reason that already names the exit code keeps it.
  const code = j.exit_code !== null && j.exit_code !== undefined && j.exit_code !== 0
    && !String(j.error || "").includes(`exit ${j.exit_code}`) ? `exit ${esc(String(j.exit_code))}` : "";
  return [took, code].filter(Boolean).join(" · ");
}
// The list's groups by how a job stands, for its chips: what is not
// over, what failed, what was canceled, what succeeded. They partition it.
const JOB_GROUPS = [
  {key: "live", label: "Running or waiting", is: j => !["succeeded", "failed", "canceled"].includes(j.state)},
  {key: "failed", label: "Failed", is: j => j.state === "failed"},
  {key: "canceled", label: "Canceled", is: j => j.state === "canceled"},
  {key: "succeeded", label: "Succeeded", is: j => j.state === "succeeded"},
];
// Home's "N failed today" opens the list on what it counted: the
// failed jobs that ended since today began by the controller's day (Home's
// answer says when; this browser's midnight until it has). Not one of the
// groups that partition the list, so a chip of its own after them.
function jobsToday(){
  const d = new Date(); d.setHours(0, 0, 0, 0);
  return (typeof homeData !== "undefined" && homeData?.jobs?.today) || d.getTime() / 1000;
}
const JOB_TODAY = {key: "failed-today", label: "Failed today",
                   is: j => j.state === "failed" && (j.ended || j.queued || 0) >= jobsToday()};
const JOB_VIEWS = [...JOB_GROUPS, JOB_TODAY];
function jobsShown(list){
  const g = JOB_VIEWS.find(x => x.key === jobsShow);
  return g ? list.filter(g.is) : list;
}
// The page's address names the chip a link opens it on (#/jobs/failed), the
// way a node page's names its node.
function jobsShowSet(v){
  jobsShow = JOB_VIEWS.some(g => g.key === v) ? v : "";
}

// Who asked: every job has an asker, so it is a column and not a line
// under each row, said as principalWords says one. One word, which the By
// column holds whole at a desk beside the Job column's room ("automatic
// update" was cut to "automatic …"); the Kind column beside it says what
// it updated.
function jobBy(j){ return esc(principalWords(j.requested_by)); }
// The Job column has the room: a title wraps at a word only when
// its column holds the longest word, so it takes most of the shares; Node
// and By keep a floor that holds a node's and an account's name whole, and
// the buttons' column is one Cancel wide, not a blank band at the right.
const JOB_COLS = [{label: "Job", w: "minmax(0,4fr)"}, {label: "State", w: "6rem"}, {label: "Kind", w: "6rem"},
                  {label: "Node", w: "minmax(7rem,1fr)"}, {label: "By", w: "minmax(5.5rem,.7fr)"}, {label: "When", w: "6.5rem"},
                  {label: "Took", w: "5rem", num: true}, {act: true, w: "5.5rem"}];

// What a job left behind: the artifacts it delivered into dist/, as the
// download links the Artifacts tab would offer, and the workspace a failed
// build kept on its node for a look (docs/nodes.md §6).
function jobOutputs(j){
  const outs = Array.isArray(j.outputs) ? j.outputs : [];
  const said = outs.map(o => o.kind === "artifact"
    ? `<a href="/api/artifact?project=${encodeURIComponent(j.project)}&path=${
        encodeURIComponent(o.path)}" download>${esc(o.path)}</a>`
    : o.kind === "workspace" ? `workspace kept at <code>${esc(o.path)}</code>`
    // What the build took on its node, its cache beside it.
    : o.kind === "room" ? `took ${esc(humanBytes(o.workspace || 0))}${o.cache ? `, its cache ${esc(humanBytes(o.cache))}` : ""}` : "")
    .filter(Boolean);
  return said.length ? `<div class="sub jbouts">${said.join(" · ")}</div>` : "";
}

// The list under its head, as every page's sections are (the operator, 18
// Oct: Jobs had no head, Home and Machines one), drawn the same by the page
// and by its placeholder.
function jobsSection(body, count){
  return docSection("jobs", "list", "Jobs", count, body);
}

function renderJobsInto(i){
  const d = docSurface(i, "jobs");
  if (!d) return;
  if (jobsList === null){
    // Its template: the bar's filter and the table's head are
    // the page's own; the count and the rows are on their way.
    d.setBar("");
    drawHTML(d.list, skTpl(jobsSection(skTable(JOB_COLS, 6, "jbtbl"), "")));
    wireJobsTab(d.el);
    loadJobs();
    return;
  }
  if (jobsErr){
    drawHTML(d.list, `<div class="hint bad">${esc(jobsErr)}</div>`);
    return;
  }
  // Its count is its tiles' (no loose words at a
  // page's top).
  d.setBar("");
  const shown = jobsShown(jobsList);
  // Only the rows on show are built, a page at a time (pageLimit),
  // and as far as the row a link asked for (openJob).
  const focusAt = jobsFocus ? shown.findIndex(j => j.id === jobsFocus) : -1;
  const lim = Math.max(pageLimit(d.list, "jbList", shown.length), focusAt + 1);
  const rows = shown.slice(0, lim).map(j => {
    const open = jobsOpen.has(j.id);
    const over = ["succeeded", "failed", "canceled"].includes(j.state);
    return `
    <div class="row stack2 jbrow${j.id === jobsMarked ? " focus" : ""}" data-job="${esc(j.id)}" data-state="${esc(j.state)}">
      ${tblLine(JOB_COLS, [jobTitle(j), jobStatePill(j), esc(j.type), jobNode(j), jobBy(j), jobWhen(j), jobTook(j),
        over || j.cancel || j.may_cancel === false ? "" : `<div class="actbar">
          <button type="button" class="caution" data-jb="cancel"
            title="${j.state === "queued" ? "take it off the queue before it starts"
                     : "stop it where it is: the row moves when the runner reports that it did"}">Cancel</button>
        </div>`], "div", "jbopen",
        // The row's line opens it to what the job wrote (rows-you-open):
        // pressed, or Enter and Space from the keyboard. Named
        // as the job and where it stands, then what the press does: a label
        // of the press alone was all a screen reader said of every row, the
        // line under it being the button's.
        `role="button" tabindex="0" aria-expanded="${open}" aria-label="${jobTitle(j)}, ${esc(jobWord(j))}: ${open ? "fold its log away" : "open its log"}"`)}
      ${j.error ? `<div class="sub jberr warn">${esc(j.error)}</div>` : ""}
      ${jobOutputs(j)}
      ${open ? `<pre class="dmlog jblog" data-tail="1">${
          // Its log on its way, the first time it is opened: a line of its
          // shape, never "wrote nothing" before anybody read it.
          !(j.id in jobsLogs) ? skv(18)
          // "yet" only while there could be more. A job that has ENDED
          // with an empty log is not waiting for anything, and saying it
          // is sends somebody back to look again at nothing.
          : esc((jobsLogs[j.id] || "").slice(-4000)
              || (over ? "(this job wrote nothing)" : "(no output yet)"))}</pre>
        <div class="actbar jbfollow"><button type="button" data-jbfollow="${esc(j.id)}" data-label="${esc(`${j.type || "job"} ${j.id}`)}"
          title="its whole log in a tab of the dock, following it as it is written">Follow in the dock</button></div>` : ""}
    </div>`;
  }).join("");
  // Its status line in its head, as every page's (the tiles rule):
  // what is news, the split of what runs from what waits and the failures
  // of today; the groups' counts are the chips' own, said once there.
  const count = f => jobsList.filter(f).length;
  const running = count(j => j.state === "running"), waiting = count(j => ["queued", "assigned"].includes(j.state));
  const failedToday = count(JOB_TODAY.is);
  const tiles = !jobsList.length ? "" : pageHead({line: [
    {label: "running", value: running, omit: !running},
    {label: "waiting", value: waiting, omit: !waiting},
    {label: "failed today", value: failedToday, tone: "bad", omit: !failedToday},
  ]});
  // Narrowed by how a job stands: a chip per state group with jobs
  // in it, under the tiles; the one a link named stays on even when its
  // group is empty, so the list says so rather than showing everything.
  // Failed today is inside Failed, so All is the list's length, not a sum.
  const chips = chipBar(JOB_VIEWS.map(g => ({key: g.key, label: g.label, count: count(g.is)})), jobsShow, "data-jbshow",
                        jobsList.length);
  const said = JOB_VIEWS.find(g => g.key === jobsShow);
  // Rows the redraw puts elsewhere (one arriving on top, one whose state
  // sorts it anew) slide there, and a new one fades in (reflow).
  reflow(d.list, ".jbrow[data-job]", e => e.dataset.job, () => patch(d.list, tiles + chips + jobsSection(shown.length ? tblWrap(JOB_COLS, rows, "jbtbl")
    : `<div class="empty">${said ? (said.key === "live" ? "nothing is running or waiting"
                                     : `nothing ${said.key === JOB_TODAY.key ? "failed today" : said.key} among the last ${jobsList.length} jobs`)
                                   + ` <button type="button" data-jbshow="">Show every job</button>`
                                 : "no jobs yet: a compose action, an exec on a node, or an agent update will appear here"}</div>`,
    shown.length ? `${shown.length}` : "none")));
  d.list.querySelectorAll("[data-jbfollow]").forEach(b => b.onclick = e => {
    e.stopPropagation();
    openLogTab(`log:job:${b.dataset.jbfollow}`, `Log: ${b.dataset.label}`);
  });
  // Paged like every other long list here. This one grows without bound:
  // every compose action, exec and agent update lands on it forever, so it
  // was the tab most in need of it and the one that had it least.
  // Its section stands open at a desk and takes its turn on a phone.
  wireSections(d.list);
  const tbl = d.list.querySelector(".jbtbl");
  if (tbl) paginate(tbl, ":scope > .jbrow", {key: "jbList", noun: "jobs", total: shown.length, more: () => renderJobsInto(i)});
  if (jobsFocus){
    const row = d.list.querySelector(`.jbrow[data-job="${CSS.escape(jobsFocus)}"]`);
    if (row){ row.scrollIntoView({block: "nearest"}); jobsFocus = ""; }
  }
  wireJobsTab(d.el);
}

function wireJobsTab(root){
  root.querySelectorAll("[data-jbshow]").forEach(b => b.onclick = () => chipMove(
    () => document.querySelector(".pane .doc.on .jobstab") || root, ".jbrow",
    () => { jobsShowSet(b.dataset.jbshow); readMoved("jobs"); drawPanes(); shellSync(); }));
  // Every tail sits at its own bottom after a draw: the end is where the
  // reason is, the same rule the manager's compose log keeps.
  root.querySelectorAll('.jblog[data-tail="1"]').forEach(t => { t.scrollTop = t.scrollHeight; });
  root.querySelectorAll(".jbrow").forEach(row => {
    const id = row.dataset.job;
    // Opened and shut over its height, as every row that opens is
    // (the log appeared and went with a cut): open, it is
    // drawn at once with what is known and slides open, and slides on to
    // the log's own height when the log lands; shut, it slides closed over
    // its log before it is drawn without it.
    const at = () => document.querySelector(`.pane .doc.on .jobstab .jbrow[data-job="${CSS.escape(id)}"]`);
    const toggle = async () => {
      const el = at();
      if (jobsOpen.has(id)){
        // Shut at the press: a redraw while it slides (its log's read
        // landing, the poll) draws it shut, and the slide is how it looks.
        jobsOpen.delete(id);
        const extra = el ? [...el.querySelectorAll(":scope > .jblog, :scope > .jbfollow")] : [];
        // Marked moved first: drawPanes draws again only what moved.
        if (!el || !extra.length || noMotion()){ readMoved("jobs"); drawPanes(); return; }
        const from = el.offsetHeight;
        extra.forEach(x => { x.hidden = true; });
        const to = el.offsetHeight;
        extra.forEach(x => { x.hidden = false; });
        let drawn = false;
        const shut = () => { if (!drawn){ drawn = true; readMoved("jobs"); drawPanes(); } };
        foldHeight(el, from, to, shut);
        // ...and drawn so however the slide ends, a newer fold on the row
        // having taken its place.
        setTimeout(shut, 400);
        return;
      }
      jobsOpen.add(id);
      const draw = () => { readMoved("jobs"); drawPanes(); };
      if (el) swapBox(el, draw); else draw();
      await loadJobs();
      // On to its log's height, unless it was shut meanwhile.
      const now = at();
      if (now && jobsOpen.has(id)) swapBox(now, () => {});
    };
    const line = row.querySelector(".jbopen");
    // Not a press on its own controls: Cancel, a link, an output.
    if (line){
      line.onclick = e => { if (!e.target.closest("button, a, input, select, label")) toggle(); };
      line.onkeydown = e => { if ((e.key === "Enter" || e.key === " ") && e.target === line){ e.preventDefault(); toggle(); } };
    }
    row.querySelectorAll("[data-jb]").forEach(b => b.onclick = async () => {
      if (b.dataset.jb === "cancel") await jobAct({action: "cancel", id});
    });
  });
}
