// The Notifications page (R218 step 6, the design's the-dashboard/notifications
// rule), at #/notifications, opened from the bell's See all. Two parts:
//
//   Active (R280, the operator, 24 Nov): every ask, invitation and held
//   change, each a row with what it is and what it would run, its Approve
//   and Deny ON the row, and the long part (a compose file, the lines a push
//   flagged, a release's notes) whole in a scrolling box behind a fold;
//   then what blocks work now, the bell's own rows (needsRows "active").
//   None of it has a ×: it leaves when it is answered or stops being true.
//
//   History: what the page has said to this account, kept on the server
//   (notices.py) across reloads and browsers, newest first, narrowed by
//   chips (what was said, answers to asks, jobs, failures), each row with
//   its own delete, and Clear for the lot or the chip in force.
//
// One classic script beside index.html (docs/design-language.md, Files):
// pure declarations, nothing runs at load.

"use strict";

let noticesData = null;          // the account's notices, or null before the first read
let noticesErr = "";
let noticesChip = "";            // the chip in force: "", a kind, or "bad" for failures

function openNotices(){
  // Every long part shut each time the page is come back to (the operator,
  // 24 Nov): one opened stays open while the page is read, through the
  // redraws the poll makes, and not past it.
  for (const k of Object.keys(sectOpen)) if (/^notices:(ask|okayed):/.test(k)) delete sectOpen[k];
  document.querySelectorAll('details:is([data-sect^="notices:ask:"], [data-sect^="notices:okayed:"])').forEach(d => { d.open = false; });
  openTab({kind: "notices", arg: "__notices", label: "Notifications"});
}

function loadNotices(){
  return reading("notices", async () => {
    const j = await getJSON("/api/notices");
    noticesErr = j.error ? "could not read the notices: " + j.error : "";
    noticesData = j.notices || noticesData || [];
  });
}

// A notice deleted or cleared goes from the page on the press (`gone` picks
// which), and comes back saying why if the server refuses; the list is read
// again once it has answered.
function noticesAct(body, gone){
  const was = noticesData;
  return drawNow(() => {
    if (!gone || !noticesData) return null;
    const going = new Set(noticesData.filter(gone).map(n => String(n.id)));
    noticesData = noticesData.filter(n => !gone(n));
    // Its rows leave (leaveBox) and the page draws without them once gone.
    const rows = [...document.querySelectorAll(".ntrow[data-nt]")].filter(r => going.has(r.dataset.nt));
    let left = rows.length;
    if (!left) drawPanes();
    rows.forEach(r => leaveBox(r, () => { if (--left === 0) drawPanes(); }));
    return () => {
      noticesData = was;
      rows.forEach(r => r.getAnimations().forEach(x => { if (x.id === "leave") x.cancel(); }));
      drawPanes();
    };
  }, () => postJSON("/api/notices", body)).then(async j => { await loadNotices(); return j; });
}

const NOTICE_KINDS = {said: "Said", ask: "Answers", job: "Jobs"};

// Every ask, as a row: what it is and what it would run, its answer on the
// row, and the long part in a scrolling box behind a fold.
function noticesAskRows(){
  const asks = ph?.asks || [];
  return asks.map(a => {
    const [what, body] = askLong(a);
    return `<div class="row stack2 ntask${a.kind === "root" || a.kind === "release-remove" || a.kind === "release-withdraw" ? " bad" : ""}" data-ask="${a.id}">
      <div class="grow">
        <div class="name">${askTag(a)}</div>
        <div class="sub">${esc(a.why || "")}</div>
        <div class="bcmd">${askCmd(a)}</div>
        ${body ? `<details class="ntlong chev"${sectAttr("notices:ask:" + a.id)}><summary>${esc(what)}</summary><pre class="ntbox">${esc(body)}</pre></details>` : ""}
        <div class="sub dim">${a.asker ? esc(a.asker) + "'s session · " : ""}${askLeft(a)}</div>
      </div>
      <div class="actbar">${askActs(a, {deny: "data-ntdeny", allow: "data-ntallow"})}</div>
    </div>`;
  });
}

function noticesWaitingRows(){
  const invites = (state?.invites || []).map(i => `<div class="row stack2" data-invite="${i.id}">
      <div class="grow"><div class="name">${i.kind === "owner" ? `${esc(projLabel(i.project))} offered to you` : `Invited to ${esc(projLabel(i.project))}`}</div>
        <div class="sub">${esc(i.by || "Somebody")} ${i.kind === "owner" ? "offers you ownership" : `invited you${i.role ? ` as ${esc(i.role)}` : ""}`} · ${esc(ago(i.at))}</div></div>
      <div class="actbar"><button type="button" data-ntinvite="${i.id}" data-yes="0">Decline</button>
        <button type="button" class="primary" data-ntinvite="${i.id}" data-yes="1">Accept</button></div></div>`);
  const held = (state?.projects || []).filter(p => p.pending > 0).map(p => `<div class="row stack2">
      <div class="grow"><div class="name">${p.pending} change${p.pending === 1 ? "" : "s"} from a session in ${esc(projLabel(p.name))}</div>
        <div class="sub">waiting for your approval on its notebook</div></div>
      <div class="actbar"><button type="button" data-ntpend="${esc(p.name)}">Review</button></div></div>`);
  return [...noticesAskRows(), ...invites, ...held];
}

function noticesShown(){
  const all = noticesData || [];
  return noticesChip === "bad" ? all.filter(n => n.level === "bad")
    : noticesChip ? all.filter(n => n.kind === noticesChip) : all;
}

function renderNoticesInto(i){
  const d = docSurface(i, "notices");
  if (!d) return;
  if (noticesData === null){
    // Its template (R218 step 16): the History section and its name are the
    // page's own; what was kept is on its way.
    d.setBar(`<span class="dim">${skv(4)}</span>`);
    drawHTML(d.list, skTpl(docSection("notices", "history", "History", "", skRows(5))));
    if (!readBusy("notices")) loadNotices();
    return;
  }
  const all = noticesData, rows = noticesShown(), waiting = noticesWaitingRows(), blocking = needsRows("active");
  // Only the rows on show are built, a page at a time (pageLimit, R228 step 13).
  const lim = pageLimit(d.list, "ntList", rows.length);
  const groups = [...Object.entries(NOTICE_KINDS).map(([k, label]) => ({key: k, label, count: all.filter(n => n.kind === k).length})),
                  {key: "bad", label: "Failures", count: all.filter(n => n.level === "bad").length}];
  // In an action bar as every page's bar action is, which keeps it at the
  // right on a phone too, where it sat at the left once the spacer folded.
  d.setBar(`<span class="sp"></span>
    ${all.length ? `<span class="actbar"><button type="button" class="danger" id="ntClear">${noticesChip && noticesChip !== "bad" ? `Clear ${esc(NOTICE_KINDS[noticesChip].toLowerCase())}` : "Clear all"}</button></span>` : ""}`);
  const html = (noticesErr ? `<div class="hint bad">${esc(noticesErr)}</div>` : "")
    // Active, above History: what waits on an answer, then what blocks
    // work now, none of it with a × (R280). Not drawn with nothing in it
    // (the house rule: what has nothing to act on is not shown); while
    // something waits it opens by itself, and on a phone, one section at a
    // time, it is the one.
    + (waiting.length + blocking.length ? docSection("notices", "active", "Active", String(waiting.length + blocking.length),
                                                     waiting.join("") + (blocking.length ? `<div class="ntneeds">${blocking.join("")}</div>` : ""),
                                                     {loud: waiting.length > 0, prime: true}) : "")
    + docSection("notices", "history", "History", String(rows.length),
                 // Failures overlap the kinds, so All is what is kept.
                 chipBar(groups, noticesChip, "data-ntchip", all.length)
                 + (rows.length ? `<div class="ntlist">${rows.slice(0, lim).map(n => `<div class="row ntrow ${esc(n.level)}" data-nt="${esc(n.id)}">
                       <span class="tic">${TOAST_ICONS[n.level] || TOAST_ICONS.info}</span>
                       <div class="grow"><span class="nttext">${esc(n.text)}</span>
                         <span class="sub dim">${esc(NOTICE_KINDS[n.kind] || n.kind)} · ${esc(ago(n.at))}</span>
                         ${n.detail ? `<details class="ntlong chev"${sectAttr("notices:okayed:" + n.id)}><summary>${esc(n.what || "what was approved")}</summary><pre class="ntbox">${esc(n.detail)}</pre></details>` : ""}</div>
                       ${n.job ? `<button type="button" data-ntjob="${esc(n.job)}">Job</button>` : ""}
                       <button type="button" class="ic" data-ntdel="${esc(n.id)}" aria-label="delete this notice">×</button>
                     </div>`).join("")}</div>`
                   : `<div class="hint">${all.length ? "none of this kind" : "nothing yet: what the page tells you is kept here"}</div>`),
                 {prime: !(waiting.length + blocking.length)});
  // Rows the redraw puts elsewhere (one arriving on top, one whose state
  // sorts it anew) slide there, and a new one fades in (reflow).
  if (!reflow(d.list, ".ntrow[data-nt], .ntask[data-ask]", e => e.dataset.nt ? `nt:${e.dataset.nt}` : `ask:${e.dataset.ask}`, () => patch(d.list, html))) return;
  const list = d.list.querySelector(".ntlist");
  if (list) paginate(list, ":scope > .ntrow", {key: "ntList", noun: "notices", total: rows.length, more: () => renderNoticesInto(i)});
  wireNotices(d.el);
}

function wireNotices(root){
  wireSections(root);
  // ...and the presses on what blocks work, as the bell and Home wire them.
  wireNeeds(root);
  const clear = root.querySelector("#ntClear");
  if (clear) clear.onclick = async () => {
    const kind = noticesChip && noticesChip !== "bad" ? noticesChip : "";
    if (!await askYes(kind ? `Clear every ${NOTICE_KINDS[kind].toLowerCase()} notice?` : "Clear every notice kept for your account?")) return;
    return noticesAct({action: "clear", kind}, n => !kind || n.kind === kind);
  };
  root.querySelectorAll("[data-ntchip]").forEach(b => b.onclick = () =>
    chipMove(() => document.querySelector(".pane .doc.on"), ".ntrow", () => { noticesChip = b.dataset.ntchip; readMoved("notices"); drawPanes(); }));
  root.querySelectorAll("[data-ntdel]").forEach(b => b.onclick = () =>
    noticesAct({action: "delete", id: b.dataset.ntdel}, n => String(n.id) === b.dataset.ntdel));
  root.querySelectorAll("[data-ntjob]").forEach(b => b.onclick = () => openJob(b.dataset.ntjob));
  root.querySelectorAll("[data-ntallow]").forEach(b => b.onclick = () => askAnswer(Number(b.dataset.ntallow), true, !!b.dataset.session));
  root.querySelectorAll("[data-ntdeny]").forEach(b => b.onclick = () => askAnswer(Number(b.dataset.ntdeny), false));
  root.querySelectorAll("[data-ntinvite]").forEach(b => b.onclick = async () => {
    const yes = b.dataset.yes === "1";
    const j = await postJSON("/api/members", {action: yes ? "accept" : "decline", id: Number(b.dataset.ntinvite)});
    notify(j.error || (yes ? `you are on ${projLabel(j.project)} now` : `declined ${projLabel(j.project)}`), !!j.error, {kind: "ask"});
    refresh();
  });
  root.querySelectorAll("[data-ntpend]").forEach(b => b.onclick = () => { openNotebook(b.dataset.ntpend); openPending(b.dataset.ntpend); });
}
