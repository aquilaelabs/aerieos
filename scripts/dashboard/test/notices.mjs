// Notifications as a system (R218 step 6, the design's the-dashboard/
// notifications rule): toasts in one stack at a corner, each with its kind's
// icon and its own ×, held while the pointer is over them and each kept on
// the account's record; the bell a short list with See all; and the
// Notifications page, its asks answered on the row with the long part in a
// scrolling box, its history narrowed by chips, deleted and cleared.
import { URL, DIR, launch, newPage, ok, done, ready, sleep, quiet, api, section } from './lib.mjs';
import { writeFileSync, rmSync } from 'node:fs';

const until = async (fn, ms = 15000, step = 200) => {
  const end = Date.now() + ms;
  while (Date.now() < end){ const v = await fn(); if (v) return v; await sleep(step); }
  return null;
};

const browser = await launch();
const page = await newPage(browser, { viewport: { width: 1280, height: 900 } });
await page.goto(URL);
await ready(page);
await api('/api/notices', { action: 'clear' });

// ---- the stack -------------------------------------------------------------
await section("the stack", async () => {
  await page.evaluate(() => { for (let i = 1; i <= 6; i++) notify(`stack ${i}`, i === 6 ? true : i === 5 ? 'warn' : false); });
  const st = await page.evaluate(() => [...document.querySelectorAll('#toast .tst')].map(t => ({
    text: t.querySelector('.tmsg').textContent, cls: t.className, icon: !!t.querySelector('.tic svg'), x: !!t.querySelector('.tx') })));
  ok(st.length === 4 && st.at(-1).text === 'stack 6' && st[0].text === 'stack 3',
     `the toasts stack, the newest at the foot and at most four (${st.map(t => t.text).join(', ')})`);
  ok(/\bbad\b/.test(st.at(-1).cls) && /\bwarn\b/.test(st.at(-2).cls) && st.every(t => t.icon && t.x),
     '...each with its kind\'s icon and its own ×, a failure and a warning in their tones');
  const box = await page.$eval('#toast', el => { const r = el.getBoundingClientRect();
    return { left: r.left, rail: document.getElementById('rail').getBoundingClientRect().right,
             bottom: r.bottom, dock: document.querySelector('#pane1 .bar')?.getBoundingClientRect().top ?? innerHeight,
             newestFoot: [...el.children].at(-1).getBoundingClientRect().top >= el.firstElementChild.getBoundingClientRect().top }; });
  ok(box.left >= box.rail && box.left < box.rail + 30 && box.bottom <= box.dock && box.newestFoot,
     `...at the bottom left, beside the rail and above the dock's line, the newest at the foot (${JSON.stringify(box)})`);
  await page.click('#toast .tst:last-child .tx');
  await until(() => page.evaluate(() => ![...document.querySelectorAll('#toast .tmsg')].some(t => t.textContent === 'stack 6')), 3000);
  ok(true, '...and × takes one away');
  // Held under the pointer: an info toast's four seconds stop while it is read.
  await page.evaluate(() => { document.querySelectorAll('#toast .tst').forEach(t => t.remove()); notify('read me slowly'); });
  await page.hover('#toast .tst');
  await quiet(5000);
  ok(await page.evaluate(() => [...document.querySelectorAll('#toast .tmsg')].some(t => t.textContent === 'read me slowly')),
     'a toast under the pointer stays past its time');
  await page.mouse.move(10, 10);
  await until(() => page.evaluate(() => !document.querySelector('#toast .tst')), 8000);
  ok(await page.evaluate(() => !document.querySelector('#toast .tst')), '...and goes once the pointer leaves');
});

// ---- a toast stays put when a dialog opens ---------------------------------
// One place for the stack (the operator, 24 Oct: it moving beside a dialog
// read as a jump): the same spot with a dialog open, above its backdrop, and
// one in the way of a press is put away by its own ×.
const toastAt = () => page.evaluate(() => { const t = document.querySelector('#toast .tst').getBoundingClientRect();
  return [t.left, t.bottom].map(Math.round); });
const xWorks = () => page.evaluate(() => {
  const x = document.querySelector('#toast .tst .tx'), r = x.getBoundingClientRect();
  const hit = document.elementFromPoint(r.left + r.width / 2, r.top + r.height / 2);
  return hit === x || x.contains(hit);
});
// A toast in and at rest, and the About dialog's opening over when it is
// open: where the toast is, and what is over its ×, are read then. A toast
// slides up 8px as it comes in.
const toastRests = () => page.waitForFunction(() => {
  const moving = e => e.getAnimations({ subtree: true }).some(a => a.playState === 'running' && Number.isFinite(a.effect?.getComputedTiming().endTime));
  const t = document.querySelector('#toast .tst');
  return !!t && t.getBoundingClientRect().height > 0 && !moving(t) && !moving(document.getElementById('aboutModal'));
}, null, { timeout: 10000 }).catch(() => {});
await section("with a dialog open a toast stays where it was, and its × puts it away", async () => {
  await page.evaluate(() => notify('said before a dialog'));
  await toastRests();
  const before = await toastAt();
  await page.evaluate(() => { document.querySelectorAll('#toast .tst').forEach(t => t.remove()); openAbout(); notify('said over a dialog', 'warn'); });
  await toastRests();
  const during = await toastAt(), pressable = await xWorks();
  await page.click('#toast .tst .tx');
  const gone = await page.waitForFunction(() => !document.querySelector('#toast .tst'), null, { timeout: 3000 }).then(() => true, () => false);
  ok(JSON.stringify(before) === JSON.stringify(during) && pressable && gone,
     `with a dialog open a toast stays where it was, and its × puts it away (${JSON.stringify({ before, during, pressable, gone })})`);
  await page.evaluate(() => { document.querySelectorAll('#toast .tst').forEach(t => t.remove()); closeAbout(); });
});

// ---- every toast is on the record ------------------------------------------
await section("every toast is on the record", async () => {
  const kept = await until(async () => {
    const j = await api('/api/notices');
    return (j.notices || []).some(n => n.text === 'read me slowly') && (j.notices || []).some(n => n.text === 'stack 6' && n.level === 'bad') ? j : null;
  });
  ok(kept, 'every toast is kept on the account\'s record, with its level');
});

// ---- the bell: a short list, and See all ------------------------------------
await section("the bell: a short list, and See all", async () => {
  await page.click('#bBell');
  await page.waitForSelector('#bellPanel:not([hidden]) #bellAll', { timeout: 5000 });
  const recent = await page.$$eval('#bellPanel .bnote:not(.ask):not(.att):not(.asked)', ns => ns.length);
  ok(recent <= 5, `the bell shows the latest five of what was said (${recent})`);
  await page.click('#bellAll');
  await page.waitForFunction(() => tabOf(panes[0])?.kind === 'notices' && location.hash === '#/notifications', null, { timeout: 10000 });
  // Hidden when its closing tween lands.
  ok(await page.waitForFunction(() => document.getElementById('bellPanel').hidden, null, { timeout: 3000 }).then(() => true, () => false),
     'See all shuts the bell and opens the Notifications page, at #/notifications');
});

// ---- the page's history: chips, delete, clear --------------------------------
await section("the page's history", async () => {
  await page.waitForSelector('.noticestab .ntrow', { timeout: 15000 });
  const n0 = await page.$$eval('.noticestab .ntrow', rs => rs.length);
  ok(n0 >= 7, `the history lists what was said (${n0} rows)`);
  // Each row says how long ago, from the seconds the record keeps (B769:
  // handed milliseconds, every row landed in the future and read "just now").
  await page.route('**/api/notices', async r => {
    const res = await r.fetch(); const j = await res.json();
    (j.notices || []).forEach(x => { x.at -= 7200; });
    await r.fulfill({ response: res, json: j });
  });
  await page.evaluate(() => loadNotices());
  const whens = await until(() => page.$$eval('.noticestab .ntrow .sub', rs => rs.map(r => r.textContent))
    .then(t => t.length && t.every(x => /2 h ago/.test(x)) ? t : null), 5000);
  await page.unroute('**/api/notices');
  await page.evaluate(() => loadNotices());
  ok(whens, `a notice said two hours ago reads "2 h ago" (${(whens || []).slice(0, 1).join('')})`);
  // All counts what is kept, once each: a failure is a kind as well (B30).
  {
    // What is kept is the rows the list holds under All (the bar's count
    // went with the page heads: the All chip is that number).
    const kept = await page.evaluate(() => String((noticesData || []).length));
    const allChip = await page.$eval('.noticestab [data-ntchip=""]', b => (/\d+/.exec(b.textContent) || [])[0]);
    ok(kept && kept === allChip, `the All chip counts what is kept (${allChip} of ${kept} kept)`);
  }
  await page.click('.noticestab [data-ntchip="bad"]');
  await page.waitForFunction(() => [...document.querySelectorAll('.noticestab .ntrow')].every(r => r.classList.contains('bad')), null, { timeout: 5000 });
  ok(await page.$$eval('.noticestab .ntrow', rs => rs.length === 1 && /stack 6/.test(rs[0].textContent)),
     'the Failures chip narrows it to the failures');
  // The chip on, pressed again, is no change: no fade (B317).
  await page.waitForFunction(() => !document.querySelector('.fghost'), null, { timeout: 5000 });
  await page.click('.noticestab [data-ntchip="bad"]');
  ok(await page.evaluate(() => !document.querySelector('.fghost')), 'the chip already on, pressed again, fades nothing');
  await page.click('.noticestab [data-ntchip=""]');
  const first = await page.$eval('.noticestab .ntrow', r => r.dataset.nt);
  await page.click(`.noticestab [data-ntdel="${first}"]`);
  await page.waitForFunction(id => !document.querySelector(`.noticestab [data-nt="${id}"]`), first, { timeout: 10000 });
  ok(!(await api('/api/notices')).notices.some(n => n.id === first), 'a row\'s × deletes it, on the record too');
  const says = await page.$eval('#ntClear', b => b.textContent.trim());
  await page.click('#ntClear');
  await page.waitForFunction(() => !document.querySelector('.noticestab .ntrow'), null, { timeout: 10000 });
  ok(says === 'Clear history' && (await api('/api/notices')).notices.length === 0,
     `Clear history empties the record, asked first, and says what it clears: Active is never cleared (${says})`);
});

// ---- an ask: answered on the row, its long part in a scrolling box -----------
await section("a chip's change never draws one row over another", async () => {
  // The operator, 23 Nov: rows of different heights slid across the ones
  // fading in and out, their words over each other. Sampled every frame
  // through each change, on a phone's width where rows are tallest.
  await page.setViewportSize({ width: 393, height: 852 });
  await page.evaluate(async () => {
    const long = 'Approved: root on a node (sh -c journalctl --list-boots --no-pager | tail -3; journalctl -b -1 -o short-iso | grep -i -E oom|out of memory|killed process|memory pressure|hung)';
    const items = [];
    for (let i = 0; i < 9; i++) items.push(i % 3 === 0 ? { text: `${long} ${i}`, kind: 'ask' } : { text: `A short thing said ${i}`, kind: 'said' });
    await postJSON('/api/notices', { action: 'add', items });
    loadNotices();
  });
  await page.waitForFunction(() => document.querySelectorAll('.noticestab .ntrow').length >= 9, null, { timeout: 15000 });
  const hits = [];
  for (const chip of ['ask', 'said', '', 'ask', '']){
    const seen = await page.evaluate(async chip => {
      document.querySelector(`.noticestab [data-ntchip="${chip}"]`).click();
      const out = [];
      for (const end = performance.now() + 900; performance.now() < end;){
        await new Promise(r => requestAnimationFrame(r));
        const boxes = [...document.querySelectorAll('.noticestab .ntrow, .noticestab .fghost')]
          .filter(e => e.checkVisibility() && parseFloat(getComputedStyle(e).opacity) > 0.05)
          .map(e => e.getBoundingClientRect()).filter(r => r.bottom > 0 && r.top < innerHeight).sort((a, b) => a.top - b.top);
        for (let i = 1; i < boxes.length; i++)
          if (boxes[i - 1].bottom - boxes[i].top > 3){ out.push(`${Math.round(boxes[i - 1].bottom - boxes[i].top)}px`); break; }
      }
      return out;
    }, chip);
    if (seen.length) hits.push(`${chip || 'all'}: ${seen.length} frames, up to ${seen.sort((a, b) => parseFloat(b) - parseFloat(a))[0]}`);
  }
  ok(!hits.length, `a chip's change draws no row over another in any frame: what leaves goes first, then what stays slides, then what arrives fades in (${hits.join('; ') || 'none'})`);
  // Cleared whole: the next part finds its answer as the newest ask kept.
  await page.evaluate(async () => { await postJSON('/api/notices', { action: 'clear' }); noticesChip = ''; loadNotices(); });
  await page.setViewportSize({ width: 1280, height: 900 });
});

await section("an ask: answered on the row, its long part in a scrolling box", async () => {
  const answered = await page.evaluate(async () => {
    const calls = [];
    const real = phFetch;
    phFetch = body => { calls.push(body); return Promise.resolve(); };
    ph = { ...(ph || {}), asks: [{ id: 41, kind: 'container', name: 'web', node_name: 'sandbox', why: 'a container to try the site',
      cmd: ['container', 'new', 'web'], left: 300, asker: 'test', detail: 'services:\n' + '  web:\n    image: nginx\n'.repeat(80) }] };
    drawPanes();
    // The row drawn, its section open and at rest: its box is measured there.
    for (const end = Date.now() + 10000; Date.now() < end;){
      const r = document.querySelector('.noticestab .ntask[data-ask="41"]'), s = r?.closest('details.sect');
      if (r && (!s || (s.open && !s.getAnimations({ subtree: true }).some(a => a.playState === 'running' && Number.isFinite(a.effect?.getComputedTiming().endTime))))) break;
      await new Promise(q => setTimeout(q, 50));
    }
    const row = document.querySelector('.noticestab .ntask[data-ask="41"]');
    const onRow = !!row && !!row.querySelector('.actbar [data-ntallow="41"]') && !!row.querySelector('.actbar [data-ntdeny="41"]')
      && !row.querySelector(':scope details [data-ntallow]');
    const box = row?.querySelector('details.ntlong .ntbox');
    row.querySelector('details.ntlong').open = true;
    const scrolls = box && box.scrollHeight > box.clientHeight;
    row.querySelector('[data-ntallow="41"]').click();
    phFetch = real;
    return { onRow, scrolls, calls };
  });
  ok(answered.onRow, 'an ask is a row with Approve and Deny on it, never only inside its fold');
  ok(answered.scrolls, '...its compose file whole in a box that scrolls inside itself');
  ok(answered.calls.length === 1 && answered.calls[0].action === 'allow' && answered.calls[0].id === 41,
     `...and Approve answers it (${JSON.stringify(answered.calls)})`);
  const rec = await until(async () => ((await api('/api/notices')).notices || []).find(n => n.kind === 'ask'));
  ok(rec && /^Approved: container web on sandbox/.test(rec.text), `...an answer kept on the record as an answer (${rec?.text})`);
  // ...with what it okayed, read again in History behind the same fold (the
  // operator, 23 Nov: an approved push's lines were nowhere to be read).
  ok(rec?.what === 'the compose file' && /^services:\n  web:\n    image: nginx/.test(rec?.detail || ''),
     `...the record keeping what it okayed, whole (${rec?.what}, ${(rec?.detail || '').length} characters)`);
  await page.evaluate(() => { ph = { ...(ph || {}), asks: [] }; loadNotices(); });
  const hist = await until(() => page.evaluate(id => {
    const row = document.querySelector(`.noticestab .ntrow[data-nt="${id}"]`), d = row?.querySelector('details.ntlong');
    if (!d) return null;
    d.open = true;
    const box = d.querySelector('.ntbox');
    return { what: d.querySelector('summary').textContent, scrolls: box.scrollHeight > box.clientHeight, text: box.textContent.slice(0, 20),
             acts: d.querySelectorAll('button').length };
  }, rec.id));
  ok(hist && hist.what === 'the compose file' && hist.scrolls && /^services:/.test(hist.text) && !hist.acts,
     `...and its History row opens it in a box that scrolls inside itself, nothing to press in it (${JSON.stringify(hist)})`);
  // Shut again each time the page is come back to, never remembered past it
  // (the operator, 24 Nov), while one opened stays open through a redraw.
  const histSel = `.noticestab .ntrow[data-nt="${rec.id}"] details.ntlong`;
  await page.evaluate(s => { const d = document.querySelector(s); d.open = false; }, histSel);
  await page.evaluate(s => { const d = document.querySelector(s); window.__ntSlid = false;
    const real = Element.prototype.animate;
    Element.prototype.animate = function(k, o){ if (this === d && Array.isArray(k) && k[0] && 'height' in k[0]) window.__ntSlid = true; return real.call(this, k, o); };
    window.__ntUnslide = () => { Element.prototype.animate = real; }; }, histSel);
  await page.click(`${histSel} > summary`);
  const slid = await page.evaluate(() => { window.__ntUnslide(); return window.__ntSlid; });
  await page.waitForFunction(s => document.querySelector(s)?.open, histSel, { timeout: 5000 }).catch(() => {});
  await page.evaluate(() => loadNotices());
  await sleep(600);
  const keptOpen = await page.evaluate(s => !!document.querySelector(s)?.open, histSel);
  await page.evaluate(() => openJobsTab());
  await page.waitForFunction(() => tabOf(panes[0])?.kind === 'jobs', null, { timeout: 10000 }).catch(() => {});
  await page.evaluate(() => openNotices());
  const back = await until(() => page.evaluate(s => { const d = document.querySelector(s); return d && tabOf(panes[0])?.kind === 'notices' ? { open: d.open } : null; }, histSel));
  ok(slid && keptOpen && back && back.open === false,
     `...sliding open over its height as every fold does, open while the page is read, through its redraw, and shut again when it is come back to (${JSON.stringify({ slid, keptOpen, back })})`);
  // A denial keeps none: what it refused went nowhere.
  const denied = await page.evaluate(async () => {
    const real = phFetch;
    phFetch = () => Promise.resolve();
    ph = { ...(ph || {}), asks: [{ id: 42, kind: 'push', project: 'alpha', why: 'lines that look like a secret',
      cmd: ['git', 'push'], left: 300, asker: 'test', detail: '+ token=abc' }] };
    askAnswer(42, false);
    phFetch = real;
    ph = { ...(ph || {}), asks: [] };
  });
  const no = await until(async () => ((await api('/api/notices')).notices || []).find(n => /^Denied: /.test(n.text)));
  ok(no && !no.detail && !no.what, `...while a denied ask's lines are not kept (${JSON.stringify(no).slice(0, 160)})`);
  await page.evaluate(() => drawPanes());
});

// ---- a job's toast follows the job, and its end is kept ---------------------
await section("a job's toast follows the job, and its end is kept", async () => {
  const q = await api('/api/v1/nodes', { action: 'exec', id: 'local', argv: ['sh', '-c', 'sleep 2; exit 4'] });
  await page.evaluate(id => notifyJob(id, 'a job from the suite'), q.job);
  const live = await page.evaluate(() => [...document.querySelectorAll('#toast .tst.job .tmsg')].map(t => t.textContent));
  ok(live.some(t => /^a job from the suite: /.test(t)), `a job's toast says the job's state as it runs (${live.join(' | ')})`);
  const end = await until(() => page.evaluate(() => [...document.querySelectorAll('#toast .tst.bad .tmsg')]
    .map(t => t.textContent).find(t => /^a job from the suite: failed/.test(t))), 30000);
  ok(end, `...and when it ends, it says how, in the outcome's tone (${end})`);
  const rec = await until(async () => ((await api('/api/notices')).notices || []).find(n => n.kind === 'job' && n.job === q.job));
  ok(rec && rec.level === 'bad', '...and the end is kept on the record as a job\'s, with the job to open');
  await page.evaluate(() => document.querySelectorAll('#toast .tst').forEach(t => t.remove()));
  // What it says of a failure is the reason's first sentence, never the
  // paragraph a node sends with it (which keys it takes, what its console
  // can do): that is the job's own, on its row and in its log.
  const why = await page.evaluate(() => [
    toastWhy("refused: its signature is not the pinned release key's. This node takes only updates signed by the release key it pinned (2eb9add8c0659634…) or its spare (5999f8948f031093…); a controller built from a branch ships an unsigned agent. To allow those on this machine, at its own console: sudo aerieos-agent unsigned on"),
    toastWhy('exit 4'), toastWhy(''), toastWhy('ERROR: could not download https://example.com/a.tgz; the store is as it was'),
    toastWhy('x'.repeat(300)).length, toastWhy('jdk 21.0.13 would not start: see its log')]);
  ok(why[0] === "its signature is not the pinned release key's" && why[1] === 'exit 4' && why[2] === ''
     && why[3] === 'could not download https://example.com/a.tgz' && why[4] === 140 && why[5] === 'jdk 21.0.13 would not start: see its log',
     `...in one sentence: a node's refusal without its keys and its console's verbs, a short reason as it is (${JSON.stringify(why)})`);
});

// ---- a session working with no word from its hooks is said -----------------
// B1009: a coding agent passes over a hook it cannot run, so a session whose
// hooks are gone works on with no gate and says nothing. The heartbeat still
// shows it working; a turn begun and ended with no hook heard is a bell row
// for its account, and it goes when the session does.
await section("a session working with no word from its hooks is said", async () => {
  const users = await api('/api/users');
  const uid = (users.users || []).find(u => u.name === 'test')?.uid;
  const plant = title => writeFileSync(`${DIR}/sandboxdata/sessions.json`,
    JSON.stringify([{ name: `${uid}~claude-alpha`, attached: false, cwd: '/workspace/alpha', created: 1, title }]));
  const beats = () => new Promise(r => setTimeout(r, 12000));     // the stub's poll is five seconds: two of them
  plant('✳ Claude Code'); await beats();                         // seen idle
  plant('◐ Reading the tree'); await beats();                    // then at work, with no prompt's hook before it
  plant('✳ Claude Code');                                        // and done, with no stop's after
  await page.evaluate(() => toggleBell(true));
  const row = await until(() => page.evaluate(() => {
    refresh();
    const r = [...document.querySelectorAll('#bellPanel .bnote.att')].find(n => /working without its guards/.test(n.textContent));
    return r ? r.textContent.replace(/\s+/g, ' ').trim() : null;
  }), 70000, 2000);
  ok(row && /test's Claude session on sandbox/.test(row) && /Restart it under Manage agent/.test(row) && /Open the space/.test(row),
     `a turn worked with nothing heard from the session's hooks is a bell row naming whose it is, where, and what to do (${row})`);
  writeFileSync(`${DIR}/sandboxdata/sessions.json`, '[]');
  const gone = await until(() => page.evaluate(async () => {
    toggleBell(true); await refresh();
    return ![...document.querySelectorAll('#bellPanel .bnote')].some(n => /working without its guards/.test(n.textContent));
  }), 30000, 1500);
  ok(gone, '...and it goes when the session does');
  rmSync(`${DIR}/sandboxdata/sessions.json`, { force: true });
  await page.evaluate(() => toggleBell(false));
});

// ---- a session an outage held is offered back -------------------------------
// R251: a session's gate marks it held while the controller is away, its
// node's agent reports the mark, and once the controller answers the bell
// lists it with a Resume that tells it to pick up from its note.
await section("a session an outage held is offered back", async () => {
  const users = await api('/api/users');
  const uid = (users.users || []).find(u => u.name === 'test')?.uid;
  // As the gate writes it: bb-tty's hook is `bb-gate PROJECT ACCOUNT`, so the
  // mark names the account, and Resume finds its Claude session (B773).
  writeFileSync(`${DIR}/sandboxdata/held.json`, JSON.stringify([{ project: 'alpha', uid, session: uid,
    since: Math.floor(Date.now() / 1000) - 120 }]));
  await page.evaluate(() => toggleBell(true));
  const row = await until(() => page.evaluate(() => {
    refresh();
    const att = [...document.querySelectorAll('#bellPanel .bnote.att')];
    const r = att.find(n => /stopped for the update/.test(n.textContent));
    return r ? `${att.indexOf(r)}: ${r.textContent.replace(/\s+/g, ' ').trim()}` : null;
  }), 30000, 1000);
  ok(row && row.startsWith('0: '), `...first of what needs attention, above the updates (${row})`);
  ok(row && /test's session on sandbox/.test(row) && /Resume/.test(row),
     `a session an outage held is a bell row naming whose it is and where it runs, with Resume (${row})`);
  // It blocks work, so it is Active (R280): over Earlier in the bell with
  // no Dismiss, and on the Notifications page over History with no ×.
  const bellPlace = await page.evaluate(() => {
    const kids = [...document.querySelectorAll('#bellPanel .bgroup, #bellPanel .bnote')];
    const r = kids.find(k => /stopped for the update/.test(k.textContent));
    const head = kids.slice(0, kids.indexOf(r)).reverse().find(k => k.matches('.bgroup'));
    return { under: head?.textContent.trim() || '', dismiss: !!r?.querySelector('[data-bdismiss]') };
  });
  ok(/^Active/.test(bellPlace.under) && !bellPlace.dismiss, `...under Active in the bell, with no Dismiss (${JSON.stringify(bellPlace)})`);
  await page.evaluate(() => { toggleBell(false); openNotices(); });
  const onPage = await until(() => page.evaluate(() => {
    const act = document.querySelector('.noticestab details[data-sect="notices:active"]');
    const r = act && [...act.querySelectorAll('.bnote')].find(n => /stopped for the update/.test(n.textContent));
    const hist = document.querySelector('.noticestab details[data-sect="notices:history"]');
    return r ? { x: !!act.querySelector('[data-ntdel]'), dismiss: !!r.querySelector('[data-bdismiss]'),
                 above: !!(hist && (act.compareDocumentPosition(hist) & Node.DOCUMENT_POSITION_FOLLOWING)) } : null;
  }), 15000, 500);
  ok(onPage && !onPage.x && !onPage.dismiss && onPage.above,
     `...and on the Notifications page it is under Active, above History, with no × and no Dismiss (${JSON.stringify(onPage)})`);
  await page.evaluate(() => toggleBell(true));
  rmSync(`${DIR}/sandboxdata/held.json`, { force: true });
  // Pressed twice before the first send is back: one line, not two (B775).
  await page.evaluate(sel => { const a = document.querySelector(sel); a.click(); a.click(); },
                      `#bellPanel [data-bheld][data-session="${uid}"]`);
  const said = await until(() => page.evaluate(() => [...document.querySelectorAll('#toast .tmsg')]
    .map(t => t.textContent).find(t => /claude-alpha/.test(t))), 15000);
  ok(said && !/no session|not yours/.test(said), `...and Resume types the line into that session (${said})`);
  await quiet(1500);
  const sends = await page.evaluate(() => [...document.querySelectorAll('#toast .tmsg')].filter(t => /claude-alpha/.test(t.textContent)).length);
  ok(sends === 1, `...once, however fast it is pressed again while the first is out (${sends} sends)`);
  // Read off the bell open again: it draws only while it is on screen, and a
  // row read off a shut one is the one it held when it shut.
  const gone = await until(() => page.evaluate(async () => {
    toggleBell(true); await refresh();
    const p = document.getElementById('bellPanel');
    return !p.hidden && ![...p.querySelectorAll('.bnote')].some(n => /stopped for the update/.test(n.textContent));
  }), 20000, 1000);
  ok(gone, `...and the row goes (${await page.evaluate(() => [...document.querySelectorAll('#bellPanel .bnote')]
    .map(n => n.textContent.replace(/\s+/g, ' ').trim().slice(0, 60)).join(' | '))})`);
  await page.evaluate(() => { toggleBell(false); document.querySelectorAll('#toast .tst').forEach(t => t.remove()); });
});

// ---- on a phone the stack spans the width above the dock's line -------------
// ...or, while a dialog is open there, above its buttons.
await section("on a phone the stack spans the width above the dock's line", async () => {
  await page.setViewportSize({ width: 393, height: 851 });
  await page.evaluate(() => notify('on a phone'));
  // The page at the phone's width and drawn for it: the breakpoint's
  // listeners run before a frame's callbacks.
  await page.waitForFunction(() => innerWidth === 393, null, { timeout: 10000 });
  await page.evaluate(() => new Promise(r => requestAnimationFrame(() => requestAnimationFrame(r))));
  await toastRests();
  const r = await page.$eval('#toast .tst', t => { const b = t.getBoundingClientRect(); return { l: b.left, r: innerWidth - b.right, bottom: b.bottom,
    dock: document.querySelector('#pane1 .bar')?.getBoundingClientRect().top ?? document.getElementById('railbar').getBoundingClientRect().top }; });
  ok(r.l <= 12 && r.r <= 12 && r.bottom <= r.dock, `on a phone a toast spans the width, above the dock's line (${JSON.stringify(r)})`);
  await page.evaluate(() => { document.querySelectorAll('#toast .tst').forEach(t => t.remove()); openAbout(); notify('over a phone dialog', true); });
  await toastRests();
  // A dialog on a phone is the whole screen and covers the dock's line, so
  // the stack there floated over the dialog's words half way up: it sits
  // just above the dialog's foot instead, its buttons.
  const pd = await page.$eval('#toast .tst', t => { const b = t.getBoundingClientRect();
    const f = document.querySelector('#aboutModal > .box .foot')?.getBoundingClientRect();
    return { l: b.left, r: innerWidth - b.right, bottom: Math.round(b.bottom), foot: f ? Math.round(f.top) : null }; });
  const px = await xWorks();
  ok(pd.l <= 12 && pd.r <= 12 && pd.foot !== null && pd.bottom <= pd.foot && pd.foot - pd.bottom <= 12 && px,
     `...and with a dialog open, which is the whole screen, it sits just above the dialog's buttons, its × to put it away (${JSON.stringify({ ...pd, px })})`);
  await page.evaluate(() => { document.querySelectorAll('#toast .tst').forEach(t => t.remove()); closeAbout(); notify('after the phone dialog'); });
  await toastRests();
  const back = await page.$eval('#toast .tst', t => Math.round(t.getBoundingClientRect().bottom));
  ok(Math.abs(back - r.bottom) < 2, `...and back above the dock's line once it is put away (${back} against ${Math.round(r.bottom)})`);
  await page.evaluate(() => document.querySelectorAll('#toast .tst').forEach(t => t.remove()));
  // A question is the one dialog on a phone that is not the whole screen
  // (R265, the operator, 19 Nov: two lines and two buttons were an empty
  // page): a sheet at the foot, as tall as its words, the page showing
  // above it (the theme's veil, see-through: R273); what one press needs a yes for is listed in it, each kind
  // under its heading; and a toast sits above the sheet.
  page.answers.push(() => new Promise(r => setTimeout(() => r(-1), 2500)));
  const asked = page.evaluate(() => askYes('', { title: 'Rebuild alpha?', verb: 'Rebuild', parts: [
    { head: 'Its compose file asks for more than its own directory', lines: ['proxy mounts the docker socket: every container on the node, and root through it'] },
    { head: 'New beside the app, which its last build did not ship', lines: ['proxy'] }, { head: 'Nothing to say', lines: [] }] }));
  await page.waitForSelector('.modal.askdlg:not([hidden]) .askpart', { timeout: 5000 });
  await page.evaluate(() => notify('over a question', true));
  await toastRests();
  const sheet = await page.evaluate(() => {
    const m = document.querySelector('.modal.askdlg:not([hidden])'), b = m.querySelector('.box').getBoundingClientRect();
    const foot = m.querySelector('.foot').getBoundingClientRect(), t = document.querySelector('#toast .tst').getBoundingClientRect();
    return { top: Math.round(b.top), bottom: Math.round(innerHeight - b.bottom), h: Math.round(b.height), w: Math.round(innerWidth - b.width),
             words: Math.round(m.querySelector('.box').scrollHeight), foot: Math.round(innerHeight - foot.bottom),
             parts: [...m.querySelectorAll('.askpart')].map(p => `${p.querySelector('label').textContent}: ${p.querySelectorAll('li').length}`),
             dim: getComputedStyle(m).backgroundColor, toast: Math.round(b.top - t.bottom) };
  });
  ok(sheet.bottom === 0 && sheet.w === 0 && sheet.h < 420 && sheet.top > 300 && Math.abs(sheet.h - sheet.words) <= 2 && sheet.foot < 60
     && /(?:,|\/)\s*0?\.\d+\)$/.test(sheet.dim) && sheet.parts.length === 2 && sheet.toast >= 0 && sheet.toast <= 14,
     `on a phone a question is a sheet at the foot, as tall as its words, over the dimmed page, with what it covers under two headings and a toast above it (${JSON.stringify(sheet)})`);
  ok(await asked === false && page.dialogs.at(-1).includes('asks for more than its own directory:\n\u2022 proxy mounts the docker socket'),
     '...and Cancel is its no, the parts said to whoever answers as words');
  await page.evaluate(() => document.querySelectorAll('#toast .tst').forEach(t => t.remove()));
  // ...and the page there shows one section, History while nothing waits.
  await page.evaluate(() => { openNotices(); notify('one for the phone'); });
  await until(() => page.evaluate(() => !!document.querySelector('.noticestab .ntrow')), 10000);
  const open = await page.$$eval('.noticestab details.sect[open]', ds => ds.map(d => d.dataset.sect));
  ok(open.length === 1 && open[0] === 'notices:history' && !(await page.$('.noticestab details[data-sect="notices:active"]')),
     `on a phone, with nothing waiting, the page is its History, open (${open.join(', ')})`);
  await page.setViewportSize({ width: 1280, height: 900 });
});

// A request that never landed is the controller not answering, said so, and
// the Phone page's own read leaves it to the poll rather than keeping a
// failure (B301).
await section("A request that never landed is the controller not answering, said so, and", async () => {
  const r = await page.evaluate(async () => {
    const words = [failWords(new TypeError('Failed to fetch')), failWords(new Error('quota spent'))];
    const kept = [], realFetch = window.fetch, realNotify = window.notify;
    window.fetch = () => Promise.reject(new TypeError('Failed to fetch'));
    window.notify = m => kept.push(String(m));
    try { await phFetch(); } finally { window.fetch = realFetch; window.notify = realNotify; }
    return { words, kept };
  });
  ok(r.words[0] === 'the controller did not answer' && r.words[1] === 'quota spent' && !r.kept.some(t => /phone/.test(t)),
     `a fetch that never landed is said as the controller not answering, and the Phone page's own read keeps no failure for it (${JSON.stringify(r)})`);
});

ok(page.errors.length === 0, `zero console errors${page.errors.length ? ': ' + page.errors.join(' | ') : ''}`);
await done(browser);
