// First run (R199, R267): after the owner is made, the page is the setup
// page until Finish: four step cards at the reading width with nothing
// beside them (no rail, no panes, so no dock, no search), each with its
// state and its own action; the node's buttons open the Nodes page's own
// dialogs; the name and email step saves to the profile; Finish waits for
// a node and lands on Home, whose Getting started card keeps what is left.
// The fixture starts with setup done, so it is put back to first run here,
// as making the owner does, and Finish puts it right again.
import { URL, launch, newPage, ok, done, sleep, DIR, patience } from './lib.mjs';
import { execFileSync, spawn } from 'node:child_process';
import { mkdirSync, rmSync, openSync } from 'node:fs';
import { createServer } from 'node:net';
import { fileURLToPath } from 'node:url';

const auth = { Authorization: 'Basic ' + Buffer.from('test:test').toString('base64') };
const base = URL.replace(/\/$/, '');
const api = async (path, body) => {
  const r = await fetch(base + path, body === undefined ? { headers: auth }
    : { method: 'POST', headers: { ...auth, 'Content-Type': 'application/json' }, body: JSON.stringify(body) });
  return r.status === 204 ? {} : r.json();
};
const firstRun = async on => api('/api/settings', { set: { setup_done: !on } });

const browser = await launch();
for (const [where, vp] of [['at a desk', { viewport: { width: 1280, height: 900 } }],
                           ['on a phone', { viewport: { width: 390, height: 844 }, isMobile: true, hasTouch: true }]]){
  const r = await firstRun(true);
  ok(!r.error, `first run turned back on for the walk ${where} (${r.error || 'ok'})`);
  const page = await newPage(browser, vp);
  await page.goto(URL);
  await page.waitForFunction(() => typeof state !== 'undefined' && state?.settings && document.body.classList.contains('firstrun'), null, { timeout: 20000 });
  await page.waitForSelector('#setupPanel .setstep', { timeout: 20000 });

  // ---- the page, and nothing beside it ---------------------------------------
  const frame = await page.evaluate(() => {
    const vis = s => { const e = document.querySelector(s); return !!e && e.offsetWidth > 0 && getComputedStyle(e).display !== 'none'; };
    const steps = [...document.querySelectorAll('#setupPanel .setstep')].map(s => ({
      title: s.querySelector('h3')?.textContent.trim(), state: s.querySelector('.setstephead .pill')?.textContent.trim() }));
    const page = document.querySelector('#setupPanel .setuppage').getBoundingClientRect();
    return { steps, rail: vis('#rail'), panes: vis('#panes'), jump: vis('#jump'), bell: vis('#bBell'),
             about: !document.getElementById('aboutModal').hidden, width: Math.round(page.width), inner: innerWidth };
  });
  ok(frame.steps.map(s => s.title).join(' | ') === 'Your first node | Your name and email | Claude Code on your node | A first space',
     `the setup page is four steps, in order, ${where} (${frame.steps.map(s => s.title).join(' | ')})`);
  ok(frame.steps.every(s => /^(to do|waiting|done)$/.test(s.state || '')),
     `...each with its state as a pill (${frame.steps.map(s => s.state).join(', ')})`);
  ok(!frame.rail && !frame.panes && !frame.jump && !frame.bell,
     `...and nothing beside it: no rail, no panes and so no dock, no search, no bell (${JSON.stringify(frame)})`);
  ok(!frame.about, '...and the Getting started guide does not open over it (B839)');
  ok(frame.width <= Math.min(frame.inner, 1100), `...at the reading width (${frame.width} of ${frame.inner})`);

  // ---- the node: the Nodes page's own dialogs, and its state -------------------
  const nodeDone = frame.steps[0].state === 'done';
  if (!nodeDone){
    await page.click('#setupPanel [data-setenroll]');
    await page.waitForFunction(() => !document.getElementById('ndmodal').hidden && document.getElementById('ndBody').textContent.includes('Name'),
      null, { timeout: 10000 });
    ok(true, `Enroll node in the node step opens the Nodes page's own dialog ${where}`);
    await page.keyboard.press('Escape');
    await page.evaluate(() => { document.getElementById('ndmodal').hidden = true; });
  } else {
    ok(await page.evaluate(() => !document.querySelector('#setupPanel [data-setenroll]')),
       `a node answering, the node step is done and offers no Enroll ${where}`);
  }
  ok(await page.evaluate(n => document.getElementById('setupFinish').disabled === !n, nodeDone),
     `Finish ${nodeDone ? 'is live with a node answering' : 'waits for a node'} ${where}`);

  // ---- the name and email: Save wakes on both, and the profile has them --------
  if (frame.steps[1].state !== 'done'){
    const dead0 = await page.evaluate(() => document.querySelector('[data-setgit]').disabled);
    await page.fill('#setName', 'First Runner');
    const dead1 = await page.evaluate(() => document.querySelector('[data-setgit]').disabled);
    await page.fill('#setEmail', 'runner@example.test');
    const dead2 = await page.evaluate(() => document.querySelector('[data-setgit]').disabled);
    ok(dead0 && dead1 && !dead2, `Save sleeps until a name and an email are both typed ${where} (${dead0} ${dead1} ${dead2})`);
    // A read of the disks that found nothing new leaves the page alone, and a
    // draw it does need keeps what was typed, the caret's field and Save too.
    const same = await page.evaluate(async () => {
      const was = document.querySelector('#setName');
      await setupDisksLoad();
      return was === document.querySelector('#setName');
    });
    ok(same, `a read of the disks with nothing new does not draw the page again ${where}`);
    const kept = await page.evaluate(() => {
      document.querySelector('#setEmail').focus();
      setupSig = ''; drawSetup();
      const n = document.querySelector('#setName'), e = document.querySelector('#setEmail');
      return {name: n.value, email: e.value, focus: document.activeElement === e, save: !document.querySelector('[data-setgit]').disabled};
    });
    ok(kept.name === 'First Runner' && kept.email === 'runner@example.test' && kept.focus && kept.save,
       `a draw the page does need keeps the typed name and email, the cursor and Save ${where} (${JSON.stringify(kept)})`);
    await page.click('[data-setgit]');
    await page.waitForFunction(() => [...document.querySelectorAll('#setupPanel .setstep')][1]?.querySelector('.pill')?.textContent === 'done',
      null, { timeout: 15000 }).catch(() => {});
    const prof = await api('/api/profile');
    ok(prof.git_ready !== false && await page.evaluate(() => [...document.querySelectorAll('#setupPanel .setstep')][1].querySelector('.pill').textContent === 'done'),
       `...and saving it readies the commit author and turns the step to done (${JSON.stringify(prof.git || {})})`);
  } else ok(true, `the name and email step is done for an account that has them ${where}`);

  // ---- Finish: Home, and what is left in its card -----------------------------
  if (nodeDone){
    await page.click('#setupFinish');
    await page.waitForFunction(() => !document.body.classList.contains('firstrun'), null, { timeout: 15000 });
    await page.waitForFunction(() => location.hash === '#/home' && document.querySelector('.doc.on .hometiles'), null, { timeout: 20000 });
    const card = await page.evaluate(() => {
      const c = document.querySelector('.doc.on .hstart');
      return c ? { rows: [...c.querySelectorAll('.hsrow')].map(r => `${r.classList.contains('done') ? '✓' : '·'} ${r.querySelector('.grow').textContent}`),
                   count: c.querySelector('h3 .sst')?.textContent } : null;
    });
    ok(card === null || (card.rows.length >= 2 && /^\d+ of \d+$/.test(card.count || '')),
       `Finish lands on Home, where Getting started keeps what is left ${where} (${card ? card.count + ': ' + card.rows.join('; ') : 'all four done'})`);
    if (card){
      // The coding agent's step sends a person where agents are managed.
      const step = await page.$eval('.doc.on .hstart', c => c.querySelector('[data-hstart="claude"]')?.textContent || '');
      ok(step === '' || step === 'Library', `...its coding agent step opens the Library, where agents are installed (${step || 'done'})`);
      await page.click('.doc.on .hstart [data-hstart="hide"]');
      await page.waitForFunction(() => !document.querySelector('.doc.on .hstart'), null, { timeout: 10000 });
      ok(true, '...and Put away takes the card off Home');
      // A node that has dialed in before is still the first node while its
      // agent is quiet (B651): the card drawn with every node's agent not
      // heard from lately keeps the node step done.
      const quiet = await page.evaluate(() => {
        const keep = nodesList, hid = homeStartHidden;
        homeStartHidden = false;
        nodesList = (keep || []).map(n => ({ ...n, live: false, agent: { ...(n.agent || {}), last_seen: n.agent?.last_seen || 1 } }));
        try{ return homeStartHtml(); } finally{ nodesList = keep; homeStartHidden = hid; }
      });
      ok(!quiet.includes('data-hstart="node"'), `...and a node whose agent is quiet is still the first node on the card (B651)${quiet.includes('data-hstart="node"') ? ': the node step came back undone' : ''}`);
      await page.evaluate(() => { try{ localStorage.removeItem('bb.gsHidden'); }catch(e){} });
    }
  } else {
    await firstRun(false);
  }
  await page.close();
}
// Left as the fixture had it.
await firstRun(false);

// ---- a bare-metal install's first run (R90) -----------------------------------
// The container's first run needs a node the person enrolls; a controller
// installed bare metal has one already, its own machine, enrolled by the
// installer, and Finish waits for that one and for no other (the operator,
// 22 Oct). Told by the install's marker in its env file, BB_INSTALL. Each
// on a controller of its own, from a fresh state, beside the harness's.
{
  const DASH = fileURLToPath(new globalThis.URL('..', import.meta.url));
  const LIB = fileURLToPath(new globalThis.URL('../../lib', import.meta.url));
  const freePort = () => new Promise(res => {
    const s = createServer().listen(0, '127.0.0.1', () => { const p = s.address().port; s.close(() => res(p)); });
  });
  const OWNER = { username: 'firstowner', password: 'longenough1' };
  const H = { Authorization: 'Basic ' + Buffer.from(`${OWNER.username}:${OWNER.password}`).toString('base64'),
              'Content-Type': 'application/json' };
  const controller = async (kind, { noOwner = false } = {}) => {
    const w = `${DIR}/firstrun-${kind}`;
    rmSync(w, { recursive: true, force: true });
    for (const d of ['config', 'workspace', 'home']) mkdirSync(`${w}/${d}`, { recursive: true });
    const env = { ...process.env, DASHBOARD_STATE: `${w}/config`, WORKSPACE: `${w}/workspace` };
    // Nobody's yet when asked (a move's destination, R90 step 12).
    if (!noOwner) execFileSync('python3', [`${LIB}/users-verbs.py`, 'claim', `${DASH}/users.py`, OWNER.username],
                               { env: { ...env, BB_USERS_PW: OWNER.password } });
    const port = await freePort();
    const out = openSync(`${w}/server.log`, 'a');
    const proc = spawn('python3', ['-u', `${DASH}/server.py`], { stdio: ['ignore', out, out], env: {
      ...env, DASHBOARD_PORT: String(port), BUILDER_HOME: `${w}/home`,
      BB_DOCTOR_FIXTURE: `${DIR}/doctor.txt`, TC_AUTOCHECK: '0', BB_NODE_POLL: '3',
      BB_CLAUDE_LATEST_URL: 'file:///nonexistent', BB_CLAUDE_CHECK_DELAY: '3600', BB_NGINX_TAGS_URL: 'file:///nonexistent',
      BB_NGINX_CHECK_DELAY: '3600', BB_APPS_RELEASES_URL: 'file:///nonexistent', BB_APPS_BOOT_DELAY: '3600',
      BB_IMAGE_CHECK_DELAY: '3600', BUILDERBOT_ROLE: 'controller', BB_TOKEN: '', BB_COVERAGE_OUT: '',
      ...(kind === 'bare' ? { BB_INSTALL: 'bare-metal' } : {}) } });
    const base = `http://127.0.0.1:${port}`;
    for (let i = 0; i < patience(120); i++){
      try { if ((await fetch(`${base}/login`)).status === 200) break; } catch { /* not up yet */ }
      await sleep(250);
    }
    const post = async (path, body, h = H) => (await fetch(base + path, { method: 'POST', headers: h, body: JSON.stringify(body) })).json();
    await post('/api/settings', { set: { setup_done: false } });
    // A node of it, minted from a shell as the installer mints its own, and
    // answering by its enrollment.
    const enroll = async (name, own) => {
      const tok = execFileSync('python3', [`${LIB}/nodes-verbs.py`, 'enroll-token', `${DASH}/nodes.py`, name, '--user', 'bb',
                                           ...(own ? ['--own'] : [])], { encoding: 'utf8', env }).trim();
      // The own machine's agent is root on a managed machine (the installer
      // provisions it so), which its name and time zone job asks of it.
      // ...and current, as the installer's is: a job this controller sends
      // is refused for an agent behind the one it ships.
      const shipped = async () => own ? (await (await fetch(base + '/api/v1/nodes', { headers: H })).json()).agent || {} : {};
      return { tok, go: async () => post('/api/v1/agent/enroll', { user: 'bb', version: (await shipped()).version || '1', digest: (await shipped()).digest || 'sha256:' + '1'.repeat(64),
        census: { cpu: 2, mem_mb: 4096, arch: 'x86_64', system: 'linux', ...(own ? { administers: true, sandbox: true, disks: OWN_DISKS } : {}) } },
        { Authorization: 'Bearer ' + tok, 'Content-Type': 'application/json' }) };
    };
    const finish = () => post('/api/settings', { set: { setup_done: true } });
    return { base, proc, enroll, finish, land: () => post('/api/move-land', {}), stop: () => proc.kill('SIGTERM') };
  };

  // The own machine's disks (R161 step 3): the stick it runs from, three
  // hard disks of one size, a larger one holding something, and an SSD.
  const TB = 1048576 * 4;
  var OWN_DISKS = [
    { name: 'sda', model: 'Cruzer', serial: 'STICK1', size_mb: 30000, ssd: false, removable: true, system: true, holds: 'nothing', parts: [] },
    { name: 'sdb', model: 'WD Red', serial: 'WD-B', size_mb: TB, ssd: false, removable: false, system: false, holds: 'nothing', parts: [] },
    { name: 'sdc', model: 'WD Red', serial: 'WD-C', size_mb: TB, ssd: false, removable: false, system: false, holds: 'nothing', parts: [] },
    { name: 'sdd', model: 'WD Red', serial: 'WD-D', size_mb: TB, ssd: false, removable: false, system: false, holds: 'nothing', parts: [] },
    { name: 'sde', model: 'Seagate', serial: 'SG-E', size_mb: TB * 2, ssd: false, removable: false, system: false, holds: 'ext4', parts: [] },
    { name: 'nvme0n1', model: 'Samsung 990', serial: 'S-N', size_mb: 1048576, ssd: true, removable: false, system: false, holds: 'nothing', parts: [] }];

  const ctr = await controller('container');
  const none = await ctr.finish();
  ok(/enroll a node that runs sessions first/.test(none.error || ''),
     `the container's first run still needs a node enrolled before Finish (${none.error || 'finished'})`);
  await (await ctr.enroll('box1', false)).go();
  const fin = await ctr.finish();
  ok(!fin.error, `...and finishes once one answers (${fin.error || 'ok'})`);
  // Moving a controller in is the first setup's alone (the operator, 6 Nov):
  // once finished, a landing is refused, never merged.
  const late = await ctr.land();
  ok(/only while a controller is first being set up/.test(late.error || ''), `a move is refused once the setup is finished (${late.error || 'landed'})`);
  ctr.stop();

  const bm = await controller('bare');
  const own = await bm.enroll('thismachine', true);
  const pending = await bm.finish();
  ok(/this machine is still being set up as a node/.test(pending.error || ''),
     `a bare-metal first run waits for its own machine while it is being set up (${pending.error || 'finished'})`);
  const page = await newPage(browser, { httpCredentials: OWNER, extraHTTPHeaders: { Authorization: H.Authorization } });
  await page.goto(bm.base);
  await page.waitForSelector('#setupPanel .setstep', { timeout: 20000 });
  const draw = () => page.evaluate(async () => {
    await loadNodes(); setupSig = ''; drawSetup();
    const s = document.querySelector('#setupPanel .setstep');
    return { title: s?.querySelector('h3')?.textContent.trim(), state: s?.querySelector('.pill')?.textContent.trim(),
             text: s?.querySelector('.setstepbody')?.textContent.trim(), more: s?.querySelector('[data-setenroll]')?.textContent.trim(),
             primary: !!s?.querySelector('[data-setenroll].primary'), finish: document.getElementById('setupFinish')?.disabled };
  });
  const before = await draw();
  ok(before.title === 'This machine' && before.state === 'waiting' && /agent is being installed/.test(before.text) && before.finish,
     `its setup page shows this machine as the node being set up, with where it is, and Finish waits (${JSON.stringify(before)})`);
  ok(before.more === 'Enroll another machine' && !before.primary, '...and offers Enroll for more machines, as an option');

  // ---- its disks (R161 step 3) ------------------------------------------------
  // What they are for and how many may fail, the layout picked from them
  // and said with why, nothing written until Make it names every disk.
  const plans = await page.evaluate(disks => {
    const p = (ds, o) => { const r = setupDiskPlan(ds, o); return { kind: r.main?.kind, layout: r.main?.layout, parity: r.main?.parity, usable: r.main?.usable_mb,
      fail: r.main?.may_fail, fast: r.fast?.layout || '', notes: r.notes.length }; };
    const by = n => disks.find(d => d.name === n);
    const same3 = ['sdb', 'sdc', 'sdd'].map(by);
    return { raidz1: p(same3, { lose: 1 }), mirror: p(same3.slice(0, 2), { lose: 1 }), raidz2: p([...same3, { ...by('sdb'), name: 'sdf' }], { lose: 2 }),
             twoOfThree: p(same3, { lose: 2 }), mixed: p([...same3, by('sde')], { lose: 1 }), fast: p([...same3, by('nvme0n1')], { lose: 1 }),
             forced: p(same3, { lose: 1, layout: 'array' }), stick: p([by('sda')], {}) };
  }, OWN_DISKS);
  const TB4 = 1048576 * 4;
  ok(plans.raidz1.layout === 'raidz1' && plans.raidz1.usable === 2 * TB4 && plans.raidz1.fail === 1
     && plans.mirror.layout === 'mirror' && plans.raidz2.layout === 'raidz2' && plans.raidz2.fail === 2,
     `disks of one size are ZFS: a mirror of two, raidz1 for one failure, raidz2 for two (${JSON.stringify([plans.raidz1, plans.mirror, plans.raidz2])})`);
  ok(plans.twoOfThree.layout === 'raidz1' && plans.twoOfThree.notes === 1, `...two failures asked of three disks says it needs four (${JSON.stringify(plans.twoOfThree)})`);
  ok(plans.mixed.kind === 'array' && plans.mixed.parity.join() === 'sde' && plans.mixed.usable === 3 * TB4 && plans.mixed.fail === 1,
     `disks of mixed sizes are an array, its largest as parity (${JSON.stringify(plans.mixed)})`);
  ok(plans.fast.fast === 'single' && plans.fast.layout === 'raidz1', `an SSD beside hard disks is a fast pool of its own, never a cache (${JSON.stringify(plans.fast)})`);
  ok(plans.forced.kind === 'array' && plans.stick.kind === undefined, '...Advanced forces an array, and the stick the system runs from is never offered');
  await (await bm.enroll('otherbox', false)).go();
  const other = await bm.finish();
  ok(/still being set up as a node/.test(other.error || ''), `another node answering does not finish it (${other.error || 'finished'})`);
  const en = await own.go();
  ok(en.ok, `this machine enrolls (${en.error || 'ok'})`);
  const after = await draw();
  ok(after.state === 'done' && /the machine this controller runs on, is enrolled and answering/.test(after.text) && !after.finish,
     `...and the step is done with Finish open (${JSON.stringify(after)})`);
  // The disks step reads the machine once it answers (a pending node's
  // census is not read): its card, and what Make it sends.
  await page.evaluate(() => setupDisksLoad());
  const drawn = await page.waitForFunction(() => [...document.querySelectorAll('#setupPanel .setstep h3')].some(h => h.textContent === 'Your disks')
    && document.querySelector('#setupPanel .setdisk'), null, { timeout: 20000 }).then(() => true, () => false);
  if (!drawn){
    const why = await page.evaluate(async () => ({ steps: [...document.querySelectorAll('#setupPanel .setstep h3')].map(h => h.textContent),
      own: !!setupSteps().own, bare: state?.bare_metal, read: await (await fetch('/api/storage')).json() }));
    ok(false, `the disks step drew no disks (${JSON.stringify(why).slice(0, 900)})`);
  }
  const card = await page.evaluate(() => {
    const s = [...document.querySelectorAll('#setupPanel .setstep')].find(x => x.querySelector('h3')?.textContent === 'Your disks');
    return { second: [...document.querySelectorAll('#setupPanel .setstep h3')][1]?.textContent, rows: s.querySelectorAll('.setdisk').length,
             held: !s.querySelector('[data-setdiskuse="sde"]').checked && /erases it/.test(s.textContent),
             plan: s.querySelector('.setplan')?.textContent.replace(/\s+/g, ' ').trim(), fast: /fast pool/.test(s.textContent) };
  });
  ok(card.second === 'Your disks' && card.rows === 5 && card.held && /A ZFS raidz1 of 3 disks/.test(card.plan) && /one disk may fail/.test(card.plan) && card.fast,
     `the first run's second step is the disks: each but the stick a row, one holding data kept unless ticked, the plan in words and the SSD a fast pool (${JSON.stringify(card)})`);
  // The disks a stick's plan adopts are the old system's (B637): each a
  // row with whose it is and no box, left out of the plan and of Make it;
  // when every disk is theirs the step points at This machine and makes
  // nothing.
  {
    const some = await page.evaluate(() => {
      const keep = state.firstboot;
      // The new start's page, picked: a plan with disks opens on the walk.
      setupWalk = 'fresh';
      state.firstboot = { ...(keep || {}), adopt: { want: { data: [{ slot: 'disk1', id: 'WD_Red_WD-B', fs: 'xfs' }], parity: [{ slot: 'parity', id: 'Seagate_SG-E' }], pools: [] }, skipped: [] } };
      setupSig = ''; drawSetup();
      const s = [...document.querySelectorAll('#setupPanel .setstep')].find(x => x.querySelector('h3')?.textContent === 'Your disks');
      const theirs = [...s.querySelectorAll('.setdisk.theirs')];
      const out = { theirs: theirs.length, boxes: theirs.filter(x => x.querySelector('input')).length,
                    words: theirs.map(x => x.textContent.replace(/\s+/g, ' ')).join(' | '),
                    mine: [...s.querySelectorAll('.setdisk:not(.theirs) input')].map(i => i.dataset.setdiskuse),
                    plan: s.querySelector('.setplan')?.textContent.replace(/\s+/g, ' ') || '', make: !!s.querySelector('[data-setdisksmake]'),
                    link: s.querySelector('.theirs a.pagelink')?.getAttribute('href') };
      state.firstboot = { ...(keep || {}), adopt: { want: { data: [{ slot: 'disk1', id: 'WD_Red_WD-B' }, { slot: 'disk2', id: 'WD_Red_WD-C' }, { slot: 'disk3', id: 'WD_Red_WD-D' }, { slot: 'disk4', id: 'Samsung_990_S-N' }],
                                                             parity: [{ slot: 'parity', id: 'Seagate_SG-E' }], pools: [] }, skipped: [] } };
      setupSig = ''; drawSetup();
      const t = [...document.querySelectorAll('#setupPanel .setstep')].find(x => x.querySelector('h3')?.textContent === 'Your disks');
      out.all = { pill: t.querySelector('.pill')?.textContent, text: t.textContent.replace(/\s+/g, ' '), make: !!t.querySelector('[data-setdisksmake]'), boxes: t.querySelectorAll('input').length };
      out.all.walk = t.querySelector('[data-setwalk="move"]')?.textContent;
      out.anyLink = document.querySelectorAll('#setupPanel a.pagelink').length;
      state.firstboot = keep; setupWalk = ''; setupSig = ''; drawSetup();
      return out;
    });
    ok(some.theirs === 2 && some.boxes === 0 && /old system's disk1: adopted as it is, in the walk/.test(some.words) && /old system's parity/.test(some.words)
       && !some.link && some.mine.join() === 'sdc,sdd,nvme0n1' && /A ZFS mirror of 2 disks/.test(some.plan) && some.make,
       `the stick's disks are the old system's on the disks step: a row each with whose it is and no box, the plan from the rest, Make it for those alone (${JSON.stringify(some).slice(0, 400)})`);
    ok(some.all.pill === 'in the walk' && /Every disk here belongs to the system the stick's plan came from: 4 data disks, the parity disk/.test(some.all.text)
       && !some.all.make && some.all.boxes === 0 && some.all.walk === 'Walk me through it' && some.anyLink === 0,
       `...and with every disk theirs the step leads into the walk, offers nothing to make, and no link on the page leads where nothing can show (B662) (${JSON.stringify(some.all).slice(0, 300)})`);
  }
  // A new start on a stick (B666, B671; the operator, 4 Nov): the place for the
  // projects is a step, named by itself once a pool is made; a project waits for
  // it; a share is a folder, internal until it is exported.
  {
    const posted = [];
    await page.route('**/api/v1/nodes', async r => {
      const b = r.request().postDataJSON?.() || {};
      if (r.request().method() === 'POST' && (b.action === 'system-pool' || b.action === 'storage-share')){ posted.push(b); return r.fulfill({ json: { ok: true, job: 'j_y' } }); }
      return r.fallback();
    });
    await page.route('**/api/v1/jobs?id=j_y', r => r.fulfill({ json: { id: 'j_y', state: 'succeeded' } }));
    const fresh = await page.evaluate(async () => {
      const keepFb = state.firstboot, n = (nodesList || []).find(x => x.config?.own), was = n.reported, keepD = setupDisks.own;
      // What is drawn here is said here: no read from the server lands under it.
      const keepLoads = [loadNodes, setupDisksLoad];
      loadNodes = async () => {}; setupDisksLoad = async () => {}; setupNodesAt = Date.now() + 60000; setupDisks.at = Date.now() + 60000;
      const panel = () => document.getElementById('setupPanel');
      const step = t => [...panel().querySelectorAll('.setstep')].find(x => x.querySelector('h3')?.textContent === t);
      setupWalk = 'fresh'; state.firstboot = null; setupPlaceTried = '';
      n.reported = { ...was, os_stick: { stick: true, pool: '', ready: false, on_stick: [], written_kb: 1, boot_written_kb: 1 }, pools: [] };
      setupDisks.own = { ...keepD, node: n.id, pools: [], array: null, shares: [] };
      setupSig = ''; drawSetup();
      const out = { titles: [...panel().querySelectorAll('.setstep h3')].map(h => h.textContent),
        projectDead: step('A first space')?.querySelector('[data-setproject]')?.disabled, why: step('A first space')?.innerText.replace(/\s+/g, ' ') };
      // The pools are made: the fast one is the place, by itself, once.
      n.reported = { ...n.reported, pools: [{ name: 'tank', mount: '/mnt/tank' }, { name: 'fast', mount: '/mnt/fast' }] };
      setupDisks.own = { ...setupDisks.own, pools: [{ name: 'tank', mount: '/mnt/tank' }, { name: 'fast', mount: '/mnt/fast' }] };
      setupSig = ''; drawSetup(); setupSig = ''; drawSetup();
      await sleep_(400);
      out.card = step('Shares')?.innerText.replace(/\s+/g, ' '); out.pill = step('Shares')?.querySelector('.pill')?.textContent;
      out.exportOn = document.getElementById('setShareExport')?.checked;
      n.reported = { ...n.reported, os_stick: { ...n.reported.os_stick, pool: '/mnt/fast', ready: true } };
      setupSig = ''; drawSetup();
      out.placed = step('Where the spaces and containers go')?.querySelector('.pill')?.textContent; out.projectLive = !step('A first space')?.querySelector('[data-setproject]')?.disabled;
      // Left unticked, a share is made and not exported.
      step('Shares').querySelector('[data-setshares]').click();
      await sleep_(500);
      setupDisks.own = { ...setupDisks.own, shares: [{ name: 'Media', path: '/mnt/tank/media', smb: { on: false }, nfs: { on: false } }] };
      setupSig = ''; drawSetup();
      out.madeCard = step('Shares')?.innerText.replace(/\s+/g, ' ');
      [loadNodes, setupDisksLoad] = keepLoads; setupNodesAt = 0; setupDisks.at = 0;
      n.reported = was; setupDisks.own = keepD; state.firstboot = keepFb; setupWalk = ''; setupSig = ''; drawSetup();
      return out;
      function sleep_(ms){ return new Promise(r => setTimeout(r, ms)); }
    });
    await page.unroute('**/api/v1/nodes'); await page.unroute('**/api/v1/jobs?id=j_y');
    ok(fresh.titles.includes('Where the spaces and containers go') && fresh.projectDead === true && /Once the spaces have a place/.test(fresh.why),
       `a new start on a stick has a step for where the spaces go, and a space waits for it (B666) (${fresh.titles.join(' | ')})`);
    const named = posted.filter(b => b.action === 'system-pool');
    ok(named.length === 1 && named[0].path === '/mnt/fast', `...and the fast pool is named by itself, once (${JSON.stringify(named)})`);
    ok(fresh.pill === 'optional' && fresh.exportOn === false && /stays on this machine until you export it/.test(fresh.card),
       `a share says what it is, is optional, and is not exported unless asked (${fresh.card?.slice(0, 160)})`);
    ok(fresh.placed === 'done' && fresh.projectLive, '...the step turns done and a space can be made');
    const shares = posted.filter(b => b.action === 'storage-share');
    ok(shares.length === 2 && shares.every(b => b.smb.on === false) && shares[0].path.startsWith('/mnt/tank/'),
       `...and left unticked, the shares are made on the main pool, one at a time, and not served (${JSON.stringify(shares).slice(0, 200)})`);
    ok(/internal: only on this machine/.test(fresh.madeCard), `...and it says so once made (${fresh.madeCard?.slice(0, 120)})`);
  }
  // Moving here (R214): a stick whose plan names disks opens on the walk, its
  // steps in the order they have to happen, each done in place with This
  // machine's and Controller settings' own controls, read from the machine.
  {
    const walk = await page.evaluate(async () => {
      const keep = state.firstboot, n = (nodesList || []).find(x => x.config?.own), was = n.reported;
      const panel = () => document.getElementById('setupPanel');
      const titles = () => [...panel().querySelectorAll('.setstep h3')].map(h => h.textContent);
      const step = t => [...panel().querySelectorAll('.setstep')].find(x => x.querySelector('h3')?.textContent === t);
      const pill = t => step(t)?.querySelector('.pill')?.textContent;
      const words = t => step(t)?.textContent.replace(/\s+/g, ' ') || '';
      const stick = { stick: true, pool: '', ready: false, on_stick: [], written_kb: 1, boot_written_kb: 1 };
      const redraw = rep => { n.reported = { ...was, os_stick: stick, ...rep }; setupSig = ''; drawSetup(); };
      setupWalk = ''; setupLand = { fresh: true, owner: true, stick: true, held: 'the spaces need a place first' };
      state.firstboot = { ...(keep || {}), at: 1, done: [], waiting: [], failed: [], apps_from: { docker: { image: 'x' }, vms: {} },
        adopt: { want: { data: [{ slot: 'disk1', id: 'WD_Red_WD-B', fs: 'xfs' }], parity: [], pools: [{ name: 'cache', fs: 'btrfs', uuid: 'u' }] }, skipped: [] } };
      redraw({});
      const out = { walking: setupWalking(), head: panel().querySelector('h2')?.textContent, titles: titles(),
        first: words('Have these with you'), firstPill: pill('Have these with you'),
        adopt: !!step("The old system's disks")?.querySelector('[data-adopt="adopt"]') && !!step("The old system's disks")?.querySelector('input[name="adoptMode"]'),
        toDo: pill("The old system's disks"), landHeld: step('Land the controller')?.querySelector('[data-moveland]')?.disabled,
        heldWhy: /It waits for the step before/.test(words('Land the controller')) && !/the spaces need a place first/.test(words('Land the controller')), links: panel().querySelectorAll('a.pagelink').length,
        back: words('If you go back'), rail: getComputedStyle(document.getElementById('rail') || document.body).display };
      // In order (the operator, 8 Nov): the pool step waits on the disks,
      // saying so; and a system job in flight holds every step that would
      // start another, the page saying what runs.
      out.orderHeld = !!step('Where the spaces and containers go')?.classList.contains('held')
        && /After step \d+, The old system's disks/.test(words('Where the spaces and containers go'));
      out.orderSaid = [step('Where the spaces and containers go')?.className, titles().join('|'), [...panel().querySelectorAll('section.setstep')].map(c => c.className + ':' + (c.querySelector('h3')?.textContent || '')).join(' / ')].join(' ## ');
      { const jobsWere = n.jobs; n.jobs = [{ id: 'j_1', apply: 'storage-adopt', step: 'mounting /mnt/disk2', started: Math.floor(Date.now() / 1000) - 400 }]; redraw({});
        out.jobBand = panel().querySelector('.setjobband')?.textContent.replace(/\s+/g, ' ') || '';
        out.jobHeld = step("The old system's disks")?.querySelector('[data-adopt="adopt"]')?.disabled === true;
        n.jobs = jobsWere; redraw({}); out.jobGone = !panel().querySelector('.setjobband'); }
      // Adopted writable, not taken over: the walk offers no Take (the
      // operator, 8 Nov: the parity comes after, from This machine), and
      // says where it comes from.
      redraw({ adopted: { writable: true, taken: false, parity: ['sdd'], mounts: [{ where: '/mnt/disk1', fs: 'xfs', ro: false, mounted: true }] } });
      out.noTake = !step("The old system's disks")?.querySelector('[data-adopttake]') && /Take the array over builds/.test(words("The old system's disks"));
      // The two presses at the top (the operator, 9 Nov), in place of a step:
      // live while nothing runs, dead for a job, and the login's says so once
      // the machine has one. Generating shows the password once and sends it.
      { const top = () => panel().querySelector('.setuptitle');
        redraw({ console: { os: true, set: false, open: true } });
        out.conGen = top()?.querySelector('[data-setconsole]')?.textContent;
        out.conOffBtn = top()?.querySelector('[data-setoff]')?.textContent;
        out.conLive = !top()?.querySelector('[data-setconsole]')?.disabled && !top()?.querySelector('[data-setoff]')?.disabled;
        out.conNoStep = !titles().includes('A password for this screen');
        const was = n.jobs; n.jobs = [{ id: 'j_1', apply: 'storage-adopt', started: Math.floor(Date.now() / 1000) }]; redraw({ console: { os: true, set: false, open: true } });
        out.conDead = !!top()?.querySelector('[data-setconsole]')?.disabled && !!top()?.querySelector('[data-setoff]')?.disabled;
        n.jobs = was;
        redraw({ console: { os: true, set: false, open: true } });
        redraw({ console: { os: true, set: true, open: false } });
        out.conAgain = top()?.querySelector('[data-setconsole]')?.textContent;
        redraw({}); out.conNone = !top()?.querySelector('[data-setconsole]') && !!top()?.querySelector('[data-setoff]'); }
      // Adopted read only with the pool not mounted: nowhere to put anything
      // is said, in the step that is stuck.
      redraw({ adopted: { writable: false, mounts: [{ where: '/mnt/disk1', fs: 'xfs', ro: true, mounted: true }] } });
      out.stuck = words('Where the spaces and containers go'); out.doneDisks = pill("The old system's disks");
      out.pick0 = [...(step('Where the spaces and containers go')?.querySelectorAll('#stickPool option') || [])].map(o => o.value);
      // A btrfs cache adopted writable is a pool to pick (B663); a data disk is not.
      redraw({ adopted: { writable: true, mounts: [{ where: '/mnt/disk1', fs: 'xfs', ro: false, mounted: true }, { where: '/mnt/cache', fs: 'btrfs', ro: false, mounted: true }] } });
      out.pick = [...(step('Where the spaces and containers go')?.querySelectorAll('#stickPool option') || [])].map(o => o.value);
      out.backRw = words('If you go back');
      // A projects folder named: the way back says to give it back first, and how
      // from the old system (B665); the step says what it costs before it is pressed.
      out.costs = words('Where the spaces and containers go');
      stick.projects = '/mnt/user/development/projects'; stick.projects_bound = true; setupSig = ''; drawSetup();
      out.backFolder = words('If you go back');
      stick.projects = ''; stick.projects_bound = false;
      stick.ready = true; stick.pool = '/mnt/cache'; setupLand = { fresh: true, owner: true, stick: true, held: '' }; redraw({ adopted: { writable: true, mounts: [{ where: '/mnt/cache', fs: 'btrfs', ro: false, mounted: true }] } });
      out.placed = pill('Where the spaces and containers go'); out.landLive = !step('Land the controller')?.querySelector('[data-moveland]')?.disabled;
      out.landFields = !!step('Land the controller')?.querySelector('#landTok') && !!step('Land the controller')?.querySelector('#landFile');
      // The old controller ran on this machine, so its address cannot answer:
      // the bundle alone; and the token given on the first page is not asked
      // again (the operator, 10 Nov).
      out.oldNoFrom = !step('Land the controller')?.querySelector('#landFrom');
      setupLand = { fresh: true, owner: true, stick: true, held: '', token_kept: true }; setupSig = ''; drawSetup();
      out.keptNoTok = !step('Land the controller')?.querySelector('#landTok') && !!step('Land the controller')?.querySelector('#landFile')
        && /the one you gave on the first page/.test(words('Land the controller'));
      // The two picks: each label over its field, the field and its verb on one line.
      { const sp = step('Where the spaces and containers go'), sel = sp?.querySelector('#stickPool'), go = sp?.querySelector('[data-stickpool]'), lbl = sp?.querySelector('label[for="stickPool"]');
        const r = e => e?.getBoundingClientRect();
        out.pickLine = !!(sel && go && lbl) && Math.abs(r(sel).top + r(sel).height / 2 - (r(go).top + r(go).height / 2)) < 4 && r(lbl).bottom <= r(sel).top + 1; }
      setupLand = { fresh: true, owner: true, stick: true, held: '' }; setupSig = ''; drawSetup();
      setupLand = { fresh: true, owner: true, stick: true, held: 'kept back for a reason' }; setupSig = ''; drawSetup();
      out.heldSaid = /kept back for a reason/.test(words('Land the controller'));
      setupLand = { fresh: false, owner: true, stick: true, held: '' }; setupSig = ''; drawSetup();
      out.notFresh = words('Land the controller');
      // A plain stick, with no plan: the same walk with the steps it has, its own
      // disks made, and not a word of an old system (the operator, 4 Nov).
      { const fb = state.firstboot; state.firstboot = null; setupWalk = 'move'; n.reported = { ...was, os_stick: { ...stick, pool: '', ready: false } };
        setupSig = ''; drawSetup();
        out.plain = { titles: titles(), text: panel().textContent.replace(/\s+/g, ' ') };
        state.firstboot = fb; setupWalk = ''; }
      redraw({ adopted: { writable: true, mounts: [{ where: '/mnt/cache', fs: 'btrfs', ro: false, mounted: true }] } });
      // Typing survives a poll that moved nothing.
      setupLand = { fresh: true, owner: true, stick: true, held: '' }; setupSig = ''; drawSetup();
      const tok = document.getElementById('landTok');
      if (tok){ tok.value = 'typed'; drawSetup(); }
      out.typed = document.getElementById('landTok')?.value;
      // Either way, from either page.
      panel().querySelector('[data-setwalk="fresh"]').click();
      out.fresh = { head: panel().querySelector('h2')?.textContent, kept: localStorage.getItem('bb.setupWalk'), ask: panel().querySelector('[data-setwalk="move"]')?.textContent };
      panel().querySelector('[data-setwalk="move"]').click();
      out.backIn = panel().querySelector('h2')?.textContent;
      // Last, since it waits: a node list read meanwhile would take the
      // block's fixtures with it.
      { redraw({ console: { os: true, set: false, open: true } }); const top = () => panel().querySelector('.setuptitle');
        const sent = [], keep = postJSON, keepAsk = ask; let shown = null;
        const keepLoad = loadNodes;
        ask = async o => { shown = o; return true; }; loadNodes = async () => {};
        postJSON = async (u, b) => { sent.push(b); return new Response('{"ok":true}'); };
        top().querySelector('[data-setconsole]').click();
        for (let t = 0; t < 40 && !shown; t++) await new Promise(r => setTimeout(r, 50));
        out.conShown = shown?.field?.value;
        out.conAsked = shown?.text;
        out.conSent = sent[0];
        await new Promise(r => setTimeout(r, 150));
        postJSON = keep; ask = keepAsk; loadNodes = keepLoad;
      }
      return out;
    });
    if (process.env.BB_SHOTS){
      await page.setViewportSize({ width: 1440, height: 2100 }); await sleep(300);
      await page.screenshot({ path: `${process.env.BB_SHOTS}/walk-desk.png`, fullPage: true });
      await page.setViewportSize({ width: 393, height: 3000 }); await sleep(300);
      await page.screenshot({ path: `${process.env.BB_SHOTS}/walk-phone.png`, fullPage: true });
      await page.setViewportSize({ width: 1280, height: 720 }); await sleep(200);
    }
    await page.evaluate(() => { try{ localStorage.removeItem('bb.setupWalk'); }catch(e){} setupWalk = ''; setupLand = null; state.firstboot = null; loadNodes(); setupSig = ''; drawSetup(); });
    ok(walk.walking && walk.head === 'Moving here' && walk.titles.join(' | ') === "Have these with you | This machine | The old system's disks | Where the spaces and containers go | Land the controller | After it lands | If you go back",
       `a stick whose plan names disks opens on the walk, its steps in the order they have to happen (${walk.titles.join(' | ')})`);
    ok(walk.firstPill === 'read first' && /Move token/.test(walk.first) && /The bundle/.test(walk.first) && /off now/.test(walk.first) && /boot the old system's stick/.test(walk.first),
       `...the token and the bundle said first, that the old controller may be off, and how to go and make them (${walk.first.slice(0, 200)})`);
    ok(walk.adopt && walk.toDo === 'to do' && walk.links === 0, `...the disks adopted in place, with no link leading away (${JSON.stringify([walk.adopt, walk.toDo, walk.links])})`);
    ok(walk.landHeld === true && walk.heldWhy, '...Land waiting on the disks, saying why');
    ok(walk.orderHeld, `...the pool step waits on the disks step, saying which (${walk.orderSaid})`);
    ok(/adopting the old system's disks/.test(walk.jobBand) && /mounting \/mnt\/disk2, 6 min so far/.test(walk.jobBand) && /One job runs on a machine at a time/.test(walk.jobBand) && walk.jobHeld && walk.jobGone,
       `...and while a system job runs every step that would start another waits, the page saying what runs, its step and how long (${walk.jobBand})`);
    ok(walk.noTake, '...and the walk never offers to take the array over: that comes after it, from This machine');
    ok(walk.conGen === 'Generate console login' && walk.conOffBtn === 'Shut down' && walk.conLive && walk.conNoStep,
       `...the top of the page has Generate console login and Shut down, live, and no step asks for a password (${walk.conGen}, ${walk.conOffBtn}, ${walk.conLive}, ${walk.conNoStep})`);
    ok(walk.conDead, '...both dead while the machine runs a job');
    ok(/^[a-z2-9]{4}(-[a-z2-9]{4}){3}$/.test(walk.conShown || '') && walk.conSent?.action === 'console' && walk.conSent?.password === walk.conShown && /log in as admin/.test(walk.conAsked || ''),
       `...Generate sends a password a person can type at a KVM and shows it once, with the name (${walk.conShown}, ${JSON.stringify(walk.conSent)})`);
    ok(walk.conAgain === 'New console login' && walk.conNone, `...it reads New console login once one is set, and Shut down is there on a machine with no such screen (${walk.conAgain}, ${walk.conNone})`);
    ok(walk.heldSaid, '...and a hold with the step before it done says its own reason');
    ok(walk.doneDisks === 'done' && /adopted read only, with no writable pool/.test(walk.stuck) && walk.pick0.join() === '',
       `...a read-only adoption with no pool to write on says so where it stops (${walk.stuck.slice(0, 200)})`);
    ok(walk.pick.includes('/mnt/cache') && !walk.pick.includes('/mnt/disk1'), `...a btrfs pool it adopted is a system pool to pick, a data disk is not (B663) (${walk.pick.join()})`);
    ok(/Its disks are as they were/.test(walk.back) && /parity sync/.test(walk.backRw) && /Forget it/.test(walk.back),
       `...the way back says what it costs as it stands, and to forget a prepared move (${walk.backRw.slice(0, 200)})`);
    ok(/old system cannot read them until they are given back/.test(walk.costs) && /Spaces page stays empty until the controller lands/.test(walk.costs),
       `...naming a spaces folder says what it costs and when the spaces show (${walk.costs.slice(0, 260)})`);
    ok(/Let it go in the step above before you shut down/.test(walk.backFolder) && /bash \/mnt\/user\/development\/projects\/\.aerieos-give-back\.sh/.test(walk.backFolder),
       `...and with one named, the way back says to give it back first and how from the old system (B665) (${walk.backFolder.slice(0, 240)})`);
    ok(walk.oldNoFrom && walk.keptNoTok, `...the land form asks for the bundle alone where the old controller ran here, and not the token given on the first page (${JSON.stringify([walk.oldNoFrom, walk.keptNoTok])})`);
    ok(walk.pickLine, '...the system pool is a label over its field, and the field and its button share a line');
    ok(walk.placed === 'done' && walk.landLive && walk.landFields, `...and once they have a place the land form is live on the page (${JSON.stringify([walk.placed, walk.landLive, walk.landFields])})`);
    ok(/lands only on a fresh controller/.test(walk.notFresh), `...a controller that is not fresh says so in place of the form (${walk.notFresh.slice(0, 120)})`);
    ok(walk.typed === 'typed', '...what is typed survives a redraw that moved nothing');
    ok(walk.plain.titles.join(' | ') === "Have these with you | This machine | Your disks | Where the spaces and containers go | Land the controller | After it lands | If you go back"
       && !/old system/.test(walk.plain.text) && /its address is enough/.test(walk.plain.text) && /Nothing here has touched the old controller/.test(walk.plain.text),
       `...a plain stick takes the same walk with its own disks and no word of an old system (${walk.plain.titles.join(' | ')}; ${(walk.plain.text.match(/.{40}old system.{40}/) || [''])[0]})`);
        ok(walk.fresh.head === 'Set up AerieOS' && walk.fresh.kept === 'fresh' && walk.fresh.ask === 'Walk me through it' && walk.backIn === 'Moving here',
       `...and either way is a press from the other, remembered in this browser (${JSON.stringify(walk.fresh)})`);
  }
  const sent = [];
  let inFlight = false, refused = 0;
  await page.route('**/api/v1/jobs?id=j_x', async r => { inFlight = false; return r.fulfill({ json: { id: 'j_x', state: 'succeeded' } }); });
  await page.route('**/api/v1/nodes', async r => {
    const b = r.request().postDataJSON?.() || {};
    // As the server answers: one system job at a time on a node, a second
    // refused while the first runs (B670), until the job read says it ended.
    if (r.request().method() === 'POST' && /^storage-/.test(b.action || '')){
      if (inFlight) { refused++; return r.fulfill({ status: 400, json: { error: 'a system job is already in flight on this node; one at a time' } }); }
      sent.push(b); inFlight = true; return r.fulfill({ json: { ok: true, job: 'j_x' } });
    }
    return r.fallback();
  });
  const asked = page.dialogs.length;
  await page.click('#setupPanel [data-setdisksmake]');
  await page.waitForFunction(() => document.querySelector('#setupPanel [data-setdisksmake]')?.textContent.includes('Making') || false, null, { timeout: 10000 }).catch(() => {});
  await sleep(500);
  await page.waitForFunction(() => !setupDisks.making, null, { timeout: 20000 });
  await page.unroute('**/api/v1/nodes');
  await page.unroute('**/api/v1/jobs?id=j_x');
  ok(refused === 0, `Make it sends its pools one at a time, so neither is refused for the other (${refused} refused) (B670)`);
  const ask = page.dialogs.slice(asked).join(' ');
  ok(/WD-B/.test(ask) && /WD-C/.test(ask) && /WD-D/.test(ask) && /S-N/.test(ask) && !/SG-E/.test(ask) && !/STICK1/.test(ask) && /erased/.test(ask),
     `Make it names every disk it erases by serial first, and none it keeps (${ask.slice(0, 160)})`);
  ok(sent.length === 2 && sent[0].pool === 'create' && sent[0].layout === 'raidz1' && sent[0].disks.join() === 'sdb,sdc,sdd'
     && sent[1].name === 'fast' && sent[1].layout === 'single' && sent[1].disks.join() === 'nvme0n1',
     `...and makes it with the Storage page's own calls: the raidz1 and the fast pool (${JSON.stringify(sent)})`);
  const fin2 = await bm.finish();
  ok(!fin2.error, `a bare-metal first run finishes with only its own node (${fin2.error || 'ok'})`);
  // This controller (R90 step 8; split the operator, 9 Nov): the rail's
  // Controller group opens on it, with what is the controller's; the machine
  // as a node is on the Nodes page, in its picker and every other node page's
  // but the containers', and a project's node picker names it This machine.
  await page.evaluate(async () => { await refresh(); await loadNodes(); });
  await page.waitForFunction(() => !!state?.own_node, null, { timeout: 15000 }).catch(() => {});
  const rail = await page.evaluate(() => (railGroups().find(g => g.key === 'controller')?.tools || []).filter(([k]) => railAllows(k)).map(([k]) => k));
  ok(rail[0] === 'machine', `the rail's Controller group offers This controller first on a bare-metal install (${rail.join(',')})`);
  await page.evaluate(() => openMachineTab());
  await page.waitForSelector('.machinetab .pghead', { timeout: 15000 });
  const mp = await page.evaluate(() => ({
    head: document.querySelector('.machinetab .pghead')?.textContent.replace(/\s+/g, ' ') || '',
    link: document.querySelector('.machinetab .pghead a.pagelink')?.getAttribute('href') || '',
    updates: !!document.querySelector('.machinetab details[data-sect="nodes:updates"]'),
    row: !!document.querySelector('.machinetab .ndrow'),
    own: ownMachine()?.id }));
  ok(/Release/.test(mp.head) && /Sessions kept apart/.test(mp.head) && mp.updates && !mp.row && mp.link === `#/machines/nodes/${mp.own}`,
     `This controller draws the head and the Updates section, no node row, and links to the machine's row on the Nodes page (${mp.link})`);
  await page.evaluate(() => { openNodesTab(ownMachine().id); nodesRev++; drawPanes(); });
  await page.waitForSelector('.nodestab .ndrow[data-node]', { timeout: 15000 });
  const np = await page.evaluate(() => ({
    tag: !!document.querySelector('.nodestab .ndrow .tag.ndown'),
    sects: [...document.querySelectorAll('.nodestab .ndsections details.sect')].map(d => d.dataset.sect),
    live: Object.fromEntries(['library', 'installed', 'files', 'emulator', 'docker', 'nginx'].map(k => [k, machinesLive(k).some(n => n.id === ownMachine().id)])) }));
  ok(np.tag && np.sects.includes('nodes:health') && np.sects.includes('nodes:advanced'), `the machine is a row on the Nodes page, with a node's sections (${np.sects.join(',')})`);
  ok(np.live.library && np.live.installed && np.live.files && np.live.emulator && np.live.docker && !np.live.nginx,
     `its node is in the Library's and every node page's picker, the Containers page's too, and not the nginx page's (${JSON.stringify(np.live)})`);
  // A held start (R56 step 9): not held on this first boot, armed for the
  // next by its press, and Start says there was nothing to lift.
  const h0 = await page.evaluate(() => state?.held || null);
  ok(h0 && h0.held === false && h0.armed === false, `a bare-metal install's first start is not held (${JSON.stringify(h0)})`);
  const bmH = { Authorization: 'Basic ' + Buffer.from(`${OWNER.username}:${OWNER.password}`).toString('base64'), 'Content-Type': 'application/json' };
  const bmApi = async (path, body) => (await fetch(bm.base + path, body === undefined ? { headers: bmH } : { method: 'POST', headers: bmH, body: JSON.stringify(body) })).json();
  const armed = await bmApi('/api/v1/nodes', { action: 'hold-next', on: true });
  const h1 = await bmApi('/api/status');
  ok(armed.ok && armed.armed === true && h1.held?.armed === true, `Hold the next start arms the restart after this one (${JSON.stringify(armed)})`);
  await bmApi('/api/v1/nodes', { action: 'hold-next', on: false });
  const started = await bmApi('/api/v1/nodes', { action: 'start-held' });
  ok(started.ok && /not held/.test(started.note || ''), `Start with nothing held says so (${JSON.stringify(started)})`);
  // ...and holding the next start is a checkbox beside Reboot and Shut down
  // (R161 step 11), ticked while armed, the head's button gone.
  {
    await bmApi('/api/v1/nodes', { action: 'hold-next', on: true });
    await page.evaluate(async () => { await refresh(); nodesRev++; drawPanes(); });
    const box = await page.evaluate(() => ({
      row: !!document.querySelector('.nodestab details[data-sect="nodes:advanced"] [data-holdnextbox]:checked'),
      head: !!document.querySelector('.nodestab .pghead [data-holdnext]') }));
    ok(box.row && !box.head, `hold the next start is a checkbox in the Reboot or shut down row, ticked while armed (${JSON.stringify(box)})`);
    await bmApi('/api/v1/nodes', { action: 'hold-next', on: false });
  }
  // A stick boot (R161 step 10): The stick section says where docker and the
  // VMs write and what the stick has written, with the system pool picker.
  {
    const st = await page.evaluate(() => {
      const n = ownMachine();
      n.reported = { ...n.reported, os_stick: { stick: true, pool: '', ready: false, on_stick: ['projects'], written_kb: 3145728, boot_written_kb: 20480 },
                     pools: [{ name: 'fast', mount: '/mnt/pools/fast' }] };
      nodesRev++; drawPanes();
      const sect = document.querySelector('.nodestab details[data-sect="nodes:stick"]');
      return { there: !!sect, text: sect?.textContent.replace(/\s+/g, ' ') || '', pick: [...(sect?.querySelectorAll('#stickPool option') || [])].map(o => o.value) };
    });
    ok(st.there && /waiting for a system pool/.test(st.text) && /the configuration, and the spaces/.test(st.text) && /3\.0 GB in its life/.test(st.text)
       && st.pick.includes('/mnt/pools/fast'),
       `a stick boot's The stick says docker and the VMs wait for a system pool, what is still on the stick and what it has written, with the pools to pick (${st.text.slice(0, 160)})`);
  }
  // The disks the stick's plan names (R163 step 9): each found here by its
  // serial or not, the parity disk left alone, read only or writable, Check
  // and Adopt; once adopted, what is mounted and Release.
  {
    const ad = await page.evaluate(() => {
      const n = ownMachine();
      n.reported = { ...n.reported, disks: [{ name: 'sdb', by_id: '/dev/disk/by-id/ata-WDC_X_SER111', serial: 'SER111' },
                                            { name: 'sdc', by_id: '/dev/disk/by-id/ata-ST_P_SERPPP', serial: 'SERPPP' }] };
      state.firstboot = { ...(state.firstboot || {}), at: Math.floor(Date.now() / 1000), done: [], waiting: [], failed: [],
        adopt: { want: { data: [{ slot: 'disk1', id: 'WDC_X_SER111', fs: 'xfs' }, { slot: 'disk2', id: 'WDC_Y_GONE22', fs: 'btrfs' }],
                         parity: [{ slot: 'parity', id: 'ST_P_SERPPP' }], pools: [{ name: 'cache', fs: 'btrfs', uuid: 'u-1' }] },
                 skipped: [{ slot: 'disk3', id: 'WDC_Z_LOCK33', why: 'encrypted: its key is not asked for yet' }] } };
      window.__fbPlan = state.firstboot;
      nodesRev++; drawPanes();
      const sect = document.querySelector('.nodestab details[data-sect="nodes:adopt"]');
      window.__machineSections = [...document.querySelectorAll('.nodestab details.sect')].map(d => `${d.dataset.sect}: ${d.querySelector('summary')?.textContent.replace(/\s+/g, ' ').trim()}`);
      return { there: !!sect, text: sect?.textContent.replace(/\s+/g, ' ') || '',
               radios: [...(sect?.querySelectorAll('input[name="adoptMode"]') || [])].map(r => r.value + (r.checked ? '*' : '')),
               acts: [...(sect?.querySelectorAll('[data-adopt]') || [])].map(x => x.dataset.adopt) };
    });
    if (process.env.BB_SHOTS){
      console.log('[machine sections] ' + (await page.evaluate(() => window.__machineSections.join(' | '))));
      const vp = page.viewportSize();
      const openAll = () => page.evaluate(() => document.querySelectorAll('.nodestab details.sect').forEach(d => { d.open = true; }));
      await openAll();
      await page.setViewportSize({ width: 1440, height: 7000 }); await sleep(500);
      await page.screenshot({ path: `${process.env.BB_SHOTS}/machine-desk.png` });
      await page.setViewportSize({ width: 393, height: 16000 }); await sleep(500);
      await page.screenshot({ path: `${process.env.BB_SHOTS}/machine-phone.png` });
      await page.setViewportSize(vp); await sleep(300);
    }
    ok(ad.there && /here as sdb/.test(ad.text) && /WDC_Y_GONE22 · not on this machine/.test(ad.text) && /here as sdc, left alone/.test(ad.text)
       && /cache/.test(ad.text) && /encrypted/.test(ad.text) && /1 not here/.test(ad.text)
       && ad.radios.join() === 'ro*,rw' && ad.acts.join() === 'dry,adopt',
       `Disks from the stick lists each disk found or not, parity left alone, read only picked, Check and Adopt (${JSON.stringify({ ...ad, text: ad.text.slice(0, 200) })})`);
    const done = await page.evaluate(() => {
      const n = ownMachine();
      n.reported = { ...n.reported, adopted: { from: 'adopted', writable: false, at: 1, parity: ['sdc'],
        mounts: [{ where: '/mnt/disk1', fs: 'xfs', ro: true, mounted: true }, { where: '/mnt/cache', fs: 'btrfs', ro: false, mounted: false }],
        merged: { '/mnt/user': true } } };
      // The page's poll may have put the server's first boot (none) back
      // since the step above: the plan is set again with its shares.
      state.firstboot = { ...(state.firstboot || window.__fbPlan), shares: { rows: [{ name: 'media', path: '/mnt/user/media', smb: { on: true, guest: true, ro: false, tm: false, users: [] }, nfs: { on: false, ro: false, clients: [] } }],
                                 notes: [{ name: 'docs', said: 'secure: its writers by name' }] } };
      nodesRev++; drawPanes();
      const sect = document.querySelector('.nodestab details[data-sect="nodes:adopted"]');
      return { there: !!sect, gone: !document.querySelector('.nodestab details[data-sect="nodes:adopt"]'), text: sect?.textContent.replace(/\s+/g, ' ') || '',
               release: !!sect?.querySelector('[data-adopt="release"]'), serve: !!sect?.querySelector('[data-adoptshares]') };
    });
    ok(done.serve && /1 share \(media\) can be served from \/mnt\/user/.test(done.text) && /docs: secure/.test(done.text),
       `...with the stick's shares to serve from /mnt/user and what of theirs is not carried (${done.text.slice(-160)})`);
    const many = await bmApi('/api/v1/nodes', { action: 'storage-share', id: (await page.evaluate(() => ownMachine()?.id)), share: 'set-many',
      shares: [{ name: 'media', path: '/mnt/user/media', smb: { on: true, guest: true } }] });
    ok(/no share to serve: media: no Samba/.test(many.error || '') && !many.job,
       `serving the shares where no Samba is installed says so for each, with no job (${many.error})`);
    ok(done.there && done.gone && /\/mnt\/disk1xfs, read-only/.test(done.text) && /not mounted yet/.test(done.text) && /sdc, left alone/.test(done.text) && done.release,
       `once adopted, Adopted disks says each mount and Release takes the plan's place (${done.text.slice(0, 200)})`);
    // The folders at /mnt/user's top with no share settings, offered to
    // tick (R163 step 13), and the same section on the Storage page (step 9).
    const folders = await page.evaluate(() => {
      const n = ownMachine();
      n.reported = { ...n.reported, adopted: { ...n.reported.adopted, folders: ['media', 'TV Shows', 'appdata'] }, shares: [{ name: 'appdata', path: '/mnt/user/appdata', smb: { on: true }, nfs: { on: false } }] };
      nodesRev++; drawPanes();
      const sect = document.querySelector('.nodestab details[data-sect="nodes:adopted"]');
      return { offered: [...(sect?.querySelectorAll('[data-adoptfolder]') || [])].map(x => x.dataset.adoptfolder),
               ticked: [...(sect?.querySelectorAll('[data-adoptfolder]:checked') || [])].length, btn: !!sect?.querySelector('[data-adoptfolders]') };
    });
    ok(JSON.stringify(folders.offered) === '["TV Shows"]' && folders.ticked === 0 && folders.btn,
       `a folder with no share settings is offered unticked, and the plan's and the served ones are not (${JSON.stringify(folders)})`);
    // Taking the array over (R163 step 3) and the way back (step 5).
    const take = await page.evaluate(() => {
      const n = ownMachine(), was = n.reported.adopted;
      const read = () => { nodesRev++; drawPanes();
        const sect = document.querySelector('.nodestab details[data-sect="nodes:adopted"]');
        const back = document.querySelector('.nodestab details[data-sect="nodes:adoptback"]');
        return { take: [...(sect?.querySelectorAll('[data-adopttake]') || [])].map(x => x.dataset.adopttake), release: !!sect?.querySelector('[data-adopt="release"]'),
                 status: sect?.querySelector('summary')?.textContent.replace(/\s+/g, ' ') || '', back: back?.textContent.replace(/\s+/g, ' ') || '' }; };
      const old = read();
      n.reported.adopted = { ...was, taken: false };
      // Each share's places, from the old system's settings, set before
      // the takeover and kept across a redraw (R163).
      const fbWas = state.firstboot;
      state.firstboot = { ...fbWas, moves: [{ share: 'TV Shows', land: 'cache', from: 'cache', to: 'array' }, { share: 'isos', land: 'array', from: '', to: '' }], mover_cron: '0 4 * * *' };
      const offered = read();
      const msect = () => document.querySelector('.nodestab details[data-sect="nodes:adopted"]');
      offered.moves = [...(msect()?.querySelectorAll('[data-admove]') || [])].map(r => `${r.dataset.admove}:${r.querySelector('[data-moveland]').value}:${r.querySelector('[data-movemover]').value}`);
      offered.when = [...(msect()?.querySelectorAll('#adoptMoverWhen option') || [])].map(o => o.value);
      const isos = msect()?.querySelector('[data-admove="isos"]');
      if (isos){ isos.querySelector('[data-movemover]').value = 'array>cache'; isos.dispatchEvent(new Event('change', { bubbles: true })); }
      read();
      offered.kept = msect()?.querySelector('[data-admove="isos"] [data-movemover]')?.value || '';
      offered.sent = JSON.stringify(adoptMovesNow());
      state.firstboot = fbWas; adoptMoves.clear(); adoptMoverCron = null;
      n.reported.adopted = { ...was, taken: true, writable: true };
      const taken = read();
      n.reported.adopted = was;
      nodesRev++; drawPanes();
      return { old, offered, taken };
    });
    ok(JSON.stringify(take.offered.moves) === '["TV Shows:cache:cache>array","isos:array:"]' && take.offered.when[0] === '0 4 * * *' && take.offered.when.includes('')
       && take.offered.kept === 'array>cache' && /"share":"isos","land":"array","from":"array","to":"cache"/.test(take.offered.sent),
       `before the takeover each share's places start as the old system had them, with its mover's time first, and a change is kept across a redraw and sent (${JSON.stringify(take.offered)})`);
    // At a phone's width each share's group sits at the field's margin, as
    // its label does, and each bar keeps its buttons on one line apart.
    {
      const vp = page.viewportSize();
      await page.setViewportSize({ width: 393, height: 1600 }); await sleep(400);
      const lay = await page.evaluate(() => {
        const n = ownMachine(), was = [n.reported.adopted, state.firstboot];
        n.reported.adopted = { ...n.reported.adopted, taken: false };
        state.firstboot = { ...state.firstboot, moves: [{ share: 'TV Shows', land: 'cache', from: 'cache', to: 'array' }, { share: 'isos', land: 'array', from: '', to: '' }] };
        nodesRev++; drawPanes();
        const sect = document.querySelector('.nodestab details[data-sect="nodes:adopted"]'); sect.open = true;
        const take = sect.querySelector('#adoptTake'), lbl = take.querySelector('label, .lblrow, .ctllbl') || take.firstElementChild;
        const left = el => Math.round(el.getBoundingClientRect().left);
        const bars = [...sect.querySelectorAll('.actbar')].map(b => { const bs = [...b.querySelectorAll(':scope > button')].map(x => x.getBoundingClientRect());
          return { n: bs.length, tops: new Set(bs.map(r => Math.round(r.top))).size, gaps: bs.slice(1).map((r, i) => Math.round(r.left - bs[i].right)) }; });
        const out = { label: left(lbl), groups: [...take.querySelectorAll('[data-admove]')].map(left), bars };
        [n.reported.adopted, state.firstboot] = was; nodesRev++; drawPanes();
        return out;
      });
      await page.setViewportSize(vp);
      ok(lay.groups.length === 2 && lay.groups.every(x => x === lay.label) && lay.bars.every(b => b.tops === 1 && b.gaps.every(g => g >= 8)) && lay.bars.some(b => b.n === 2),
         `on a phone each share's group sits at the field's margin, and each bar keeps its buttons on one line, apart (${JSON.stringify(lay)})`);
    }
    if (process.env.BB_SHOTS){
      // Each share's places before the takeover, at a desk and on a phone.
      const vp = page.viewportSize();
      await page.evaluate(() => { const n = ownMachine(); window.__adWas = [n.reported.adopted, state.firstboot]; });
      for (const [w, name] of [[1440, 'desk'], [393, 'phone']]){
        await page.setViewportSize({ width: w, height: 1600 }); await sleep(500);
        // Laid over again for each width: the page's poll puts the server's own back.
        await page.evaluate(() => { const n = ownMachine();
          n.reported.adopted = { ...window.__adWas[0], taken: false };
          state.firstboot = { ...window.__adWas[1], moves: [{ share: 'TV Shows', land: 'cache', from: 'cache', to: 'array' }, { share: 'appdata', land: 'cache', from: '', to: '' }, { share: 'isos', land: 'array', from: '', to: '' }], mover_cron: '0 4 * * *', mover_words: 'daily at 4:00' };
          nodesRev++; drawPanes(); const d = document.querySelector('.nodestab details[data-sect="nodes:adopted"]'); if (d) d.open = true; }); await sleep(200);
        await page.locator('.nodestab details[data-sect="nodes:adopted"]').screenshot({ path: `${process.env.BB_SHOTS}/moves-${name}.png` });
      }
      await page.setViewportSize(vp);
      await page.evaluate(() => { const n = ownMachine(); [n.reported.adopted, state.firstboot] = window.__adWas; nodesRev++; drawPanes(); });
    }
    ok(!take.old.take.length && JSON.stringify(take.offered.take) === '["dry","go"]',
       `an agent that has the takeover offers Check the takeover and Take the array over; an older one offers neither (${JSON.stringify([take.old.take, take.offered.take])})`);
    ok(/taken over/.test(take.taken.status) && !take.taken.release && /parity sync that follows rebuilds/.test(take.taken.back)
       && /nothing on its data disks was written here/.test(take.old.back) && /never written/.test(take.old.back),
       `once taken over Release waits, and Going back says a parity sync there; read-only, it says nothing was written (${take.taken.back.slice(0, 160)})`);
    const onStorage = await page.evaluate(async () => {
      window.__fbKeep = state.firstboot || window.__fbPlan;
      openStorageTab(); await new Promise(r => setTimeout(r, 400));
      const own = ownMachine();
      storageList = [{ node: own.id, name: own.name, measured: true, age_s: 60, fs: [], disks: [], projects: [] }];
      storageRev++; drawPanes(); await new Promise(r => setTimeout(r, 200));
      const sect = document.querySelector('.storagetab details[data-sect="storage:adopted"]');
      return { there: !!sect, release: !!sect?.querySelector('[data-adopt="release"]'), folder: !!sect?.querySelector('[data-adoptfolder="TV Shows"]') };
    });
    ok(onStorage.there && onStorage.release && onStorage.folder,
       `the Storage page of the machine draws the same Adopted disks, Release and the folders to serve (${JSON.stringify(onStorage)})`);
    // The Nodes page points to the Containers page, where they are (the
    // operator, 10 Nov: looked for there and never found on the Nodes page).
    const pointer = await page.evaluate(() => {
      openNodesTab(ownMachine().id); state.firstboot = state.firstboot || window.__fbKeep;
      state.firstboot.apps_from = { docker: { image: '/mnt/user/system/docker/docker.img', autostart_file: 'auto' }, vms: { image: '/mnt/user/system/libvirt/libvirt.img' },
                                    networks: { br0: { subnet: '192.168.1.0/24', gateway: '192.168.1.1' } }, containers: 1 };
      window.__fbKeep = state.firstboot; nodesRev++; drawPanes();
      const p = document.querySelector('.nodestab details[data-sect="nodes:adoptapps"]');
      return { there: !!p, button: !!p?.querySelector('[data-oldapps]'), read: !!p?.querySelector('[data-adoptapp]') };
    });
    ok(pointer.there && pointer.button && !pointer.read, `the Nodes page says the old system's containers and VMs are on the Containers page (${JSON.stringify(pointer)})`);
    // ...and what the old system ran (R163 steps 10, 11): read first, then
    // its containers as compose files to download (the operator, 10 Nov:
    // imported from New container, never made here on a press) and its VMs
    // to define and run.
    const apps = await page.evaluate(() => {
      const n = ownMachine();
      openDockerOn(n.id);
      // A status poll between the two evaluates can bring the record back
      // without it (it crashed here under a whole gate's load).
      state.firstboot = state.firstboot || window.__fbKeep;
      state.firstboot.apps_from = { docker: { image: '/mnt/user/system/docker/docker.img', autostart_file: 'auto' }, vms: { image: '/mnt/user/system/libvirt/libvirt.img' },
                                    networks: { br0: { subnet: '192.168.1.0/24', gateway: '192.168.1.1' } }, containers: 1 };
      nodesRev++; drawPanes();
      const unread = document.querySelector('.dmtab details[data-sect="docker:oldapps"]')?.textContent.replace(/\s+/g, ' ') || '';
      n.reported = { ...n.reported, vms_other: [{ name: 'Windows 11', state: 'shut off', autostart: false, vcpus: 4, mem_mb: 8192 }],
        adopted: { ...n.reported.adopted, apps: { docker: { autostart: ['plex'], digests: { plex: 'x@sha256:' + 'a'.repeat(64) } },
                                                   vms: [{ name: 'Windows 11', autostart: true, nvram: true }, { name: 'Ubuntu', autostart: false, nvram: false }],
                                                   said: ['Docker: 1 container ran, 1 started with the machine'] } } };
      nodesRev++; drawPanes();
      // The rows as the controller answers them, laid over the fetch this
      // draw made (it lands after this evaluate).
      adoptPlan = [{ name: 'plex', file: 'plex.yaml', autostart: true, notes: [], network: 'br0', ok: true }];
      nodesRev++; drawPanes();
      const sect = document.querySelector('.dmtab details[data-sect="docker:oldapps"]');
      return { unread, text: sect?.textContent.replace(/\s+/g, ' ') || '',
               acts: [...(sect?.querySelectorAll('[data-adoptapp], [data-adoptnet], [data-adoptvm]') || [])].map(x => x.dataset.adoptapp || x.dataset.adoptnet || x.dataset.adoptvm) };
    });
    ok(/not read yet/.test(apps.unread) && /Read what ran/.test(apps.unread) && /nothing in them changes/.test(apps.unread),
       `before a read, the old system's containers and VMs offer Read what ran, which changes nothing (${apps.unread.slice(0, 160)})`);
    ok(/1 started with the machine/.test(apps.text) && /plex br0 · starts with the machine/.test(apps.text) && /Import a compose file/.test(apps.text)
       && /Windows 11 shut off/.test(apps.text) && /Ubuntu not defined here yet/.test(apps.text)
       && ['read', 'br0', 'zip', 'start', 'autostart-on', 'define'].every(x => apps.acts.includes(x)) && !apps.acts.includes('make'),
       `once read: each container's row, the network it joins and Download compose files, each VM defined or not with Start and start with the machine, Define the VMs (${JSON.stringify(apps.acts)}; ${apps.text.slice(0, 200)})`);
    // Each VM still to define is a tick, ticked; one taken off is not
    // defined, and the button says how many are (the operator, 1 Nov).
    const picked = await page.evaluate(() => {
      const box = document.querySelector('.dmtab [data-adpick="v:Ubuntu"]');
      const was = box?.checked;
      box.checked = false; box.dispatchEvent(new Event('change'));
      const b = document.querySelector('.dmtab [data-adoptapp="define"]');
      const after = { was, label: b?.textContent.trim(), dead: !!b?.disabled };
      adoptSkip.clear();
      return after;
    });
    ok(picked.was === true && picked.label === 'Define the ticked' && picked.dead,
       `a VM untaken is left out and Define waits for one ticked (${JSON.stringify(picked)})`);
    // The zip waits for a read's settings, and the controller makes no
    // container of them on a press any more.
    const own0 = await page.evaluate(() => ownMachine()?.id);
    const zipNone = await (await fetch(bm.base + '/api/old-compose', { headers: bmH })).json().catch(() => ({}));
    const noMake = await bmApi('/api/v1/nodes', { action: 'adopt-apps', op: 'make', id: own0, names: ['plex'] });
    const rowsNone = await bmApi('/api/v1/nodes', { action: 'adopt-apps', op: 'plan', id: own0 });
    ok(/nothing is read yet/.test(zipNone.error || '') && /Import a compose file|compose file/.test(noMake.error || '') && Array.isArray(rowsNone.apps) && rowsNone.networks,
       `the compose files wait for a read, and make is refused for import (${zipNone.error}; ${noMake.error}; ${JSON.stringify(rowsNone)})`);
    // The verb checks before any job: a filesystem it does not take, and a
    // Release with nothing adopted, each refused with why and no job made.
    const own = await page.evaluate(() => ownMachine()?.id);
    const badFs = await bmApi('/api/v1/nodes', { action: 'storage-adopt', id: own, adopt: 'dry', want: { data: [{ slot: 'disk1', id: 'WDC_X_SER111', fs: 'ext4' }] } });
    const noneHeld = await bmApi('/api/v1/nodes', { action: 'storage-adopt', id: own, adopt: 'release' });
    ok(/xfs, btrfs or zfs/.test(badFs.error || '') && !badFs.job && /nothing is adopted/.test(noneHeld.error || '') && !noneHeld.job,
       `storage-adopt refuses a filesystem it does not take and a Release with nothing adopted, before any job (${badFs.error}; ${noneHeld.error})`);
  }
  // Name and time (R161 step 3): the own machine's section, Apply asleep
  // until a field moves, and the press a system job on its node.
  const nt = await page.evaluate(() => {
    const sect = document.querySelector('.nodestab details[data-sect="nodes:machine"]');
    const b = sect?.querySelector('[data-nd="machine-apply"]'), tz = sect?.querySelector('[data-k="machinetz"]');
    const before = b?.disabled;
    if (tz){ tz.value = 'Europe/Paris'; tz.dispatchEvent(new Event('input')); }
    return { there: !!sect, before, after: b?.disabled, zones: tz?.options?.length || 0 };
  });
  ok(nt.there && nt.before === true && nt.after === false && nt.zones > 100,
     `This machine carries Name and time, Apply waking when the zone is typed, the browser's zones offered (${JSON.stringify(nt)})`);
  const mj = await bmApi('/api/v1/nodes', { action: 'machine', id: (await bmApi('/api/status')).own_node, timezone: 'Europe/Paris' });
  ok(mj.ok && mj.job, `the press queues the machine job on the own node (${JSON.stringify(mj)})`);
  const mr = await bmApi('/api/v1/nodes', { action: 'machine', id: (await bmApi('/api/status')).own_node, hostname: 'bad name' });
  ok(/letters, digits and hyphens/.test(mr.error || ''), `...and a name that is not one is refused (${mr.error})`);
  await page.evaluate(() => openNodesTab());
  await page.waitForFunction(() => document.querySelector('#ndPick'), null, { timeout: 15000 }).catch(() => {});
  const picks = await page.evaluate(() => [...document.querySelectorAll('#ndPick option')].map(o => o.textContent));
  ok(picks.some(t => /thismachine.*\(this machine\)/.test(t)) && picks.some(t => /otherbox/.test(t)),
     `...and the Nodes page's picker offers the other node and this machine, named as such (${picks.join(' | ')})`);
  await page.close();
  bm.stop();

  // Moving a controller (R90 step 12, and its second pass R175): a source
  // with a node arms a move (the token shown once, the node told from its
  // next hello, the bundle packed fresh per download), a destination nobody
  // owns pulls the bundle from the source with the token on its first page
  // and restarts on the state, where the node's knock is answered with the
  // challenge it holds; the source learns the landing by asking and marks
  // itself moved, read-only, and a node that never heard the move hears it
  // with its challenge in the moved answer; the destination's Nodes page
  // lists the node not yet here with its follow line until it says hello.
  {
    // The first page asks (the operator, 4 Nov): moving a controller here, or a
    // new start; yes opens the next page on the walk, on any install.
    {
      const lan = await controller('landing', { noOwner: true });
      // A browser of nobody's: the suite's newPage signs in as its own account,
      // which this controller has never heard of.
      const lctx = await browser.newContext({ viewport: { width: 1280, height: 900 } });
      await lctx.addInitScript(() => { window.BB_NO_TOUR = true; });
      const lp = await lctx.newPage();
      await lp.goto(lan.base);
      await lp.waitForSelector('input[name="walk"]', { timeout: 15000 });
      const ask = await lp.evaluate(() => ({ legend: document.querySelector('.moveask legend')?.textContent,
        checked: document.querySelector('input[name="walk"]:checked')?.value, now: document.querySelector('.moveask a')?.getAttribute('href'),
        nobody: /Nobody owns this install yet/.test(document.body.textContent) }));
      ok(/moving a controller here from somewhere else/.test(ask.legend || '') && ask.checked === 'fresh' && ask.now === '/login/move' && ask.nobody,
         `the first page asks whether a controller is moving here, and anywhere but a stick can land it at once (${JSON.stringify(ask)})`);
      if (process.env.BB_SHOTS) await lp.screenshot({ path: `${process.env.BB_SHOTS}/landing-desk.png` });
      await lp.check('input[name="walk"][value="move"]');
      const swap = await lp.evaluate(() => ({ acct: document.querySelector('#forNew').hidden, tok: !document.querySelector('#forMove').hidden, btn: document.querySelector('#setupGo').textContent }));
      ok(swap.acct && swap.tok && swap.btn === 'Continue', `...yes asks for the move token in place of an account (${JSON.stringify(swap)})`);
      await lp.fill('#mt', 'not a token');
      await Promise.all([lp.waitForNavigation(), lp.click('button[type=submit]')]);
      const said = await lp.evaluate(() => ({ err: document.querySelector('.err')?.textContent, moving: document.querySelector('input[name="walk"]:checked')?.value }));
      ok(/not a move token/.test(said.err || '') && said.moving === 'move', `...something that is not one is refused, still on the move (${JSON.stringify(said)})`);
      await lp.fill('#mt', 'A'.repeat(43));
      await Promise.all([lp.waitForNavigation(), lp.click('button[type=submit]')]);
      await lp.waitForFunction(() => document.querySelector('#setupPanel h2')?.textContent === 'Moving here', null, { timeout: 20000 });
      const arrived = await lp.evaluate(() => ({ search: location.search, kept: localStorage.getItem('bb.setupWalk'),
        titles: [...document.querySelectorAll('#setupPanel .setstep h3')].map(h => h.textContent) }));
      ok(arrived.search === '' && arrived.kept === 'move' && arrived.titles.join(' | ') === 'Have these with you | Land the controller | After it lands | If you go back',
         `...yes opens the next page on the walk, with the steps a container install has, the answer kept and off the address (${JSON.stringify(arrived)})`);
      await lctx.close();
      lan.stop();
    }
    const dst = await controller('dst', { noOwner: true });
    const src = await controller('src');
    const sH = { Authorization: 'Basic ' + Buffer.from(`${OWNER.username}:${OWNER.password}`).toString('base64'), 'Content-Type': 'application/json' };
    const sApi = async (path, body) => (await fetch(src.base + path, body === undefined ? { headers: sH } : { method: 'POST', headers: sH, body: JSON.stringify(body) })).json();
    // Settings' Move a controller here is drawn on what the server says of
    // the account: the poll's state.me is a name, never a role, so a box
    // keyed on that was drawn for nobody.
    const land = (await sApi('/api/move')).land || {};
    ok(land.owner === true, `the move's status tells the owner it is theirs to land (${JSON.stringify(land)})`);
    // Backup copies' Back up now and Download likewise.
    const bk = await sApi('/api/backup');
    ok(bk.owner === true, `the backup's status tells the owner Back up now is theirs (${JSON.stringify({owner: bk.owner, error: bk.error})})`);
    const mover = await src.enroll('mover', false);
    const en = await mover.go();
    ok(en.ok && en.token, `the source has a node (${en.error || 'enrolled'})`);
    const nH = { Authorization: 'Bearer ' + en.token, 'Content-Type': 'application/json' };
    const late = await src.enroll('late', false);
    const lateEn = await late.go();
    const lH = { Authorization: 'Bearer ' + lateEn.token, 'Content-Type': 'application/json' };
    const pieces = (await sApi('/api/move?pieces=1')).pieces || [];
    ok(pieces.some(p => p.key === 'state' && p.fixed && p.size > 0) && pieces.some(p => p.key === 'repos' && !p.on) && pieces.some(p => p.key === 'install_key'),
       `what a bundle may carry is listed with sizes, the state fixed and the repositories off (${pieces.map(p => p.key).join(',')})`);
    // A backup to keep (the operator, 6 Nov): its own token, nothing armed.
    const bkp = await sApi('/api/move', { action: 'backup', repos: false, stores: [] });
    const bst = await sApi('/api/move');
    const bfile = await fetch(`${src.base}/api/move-backup?name=${encodeURIComponent(bkp.bundle || '')}`, { headers: sH });
    const blen = (await bfile.arrayBuffer()).byteLength;
    const nofile = await fetch(`${src.base}/api/move-backup?name=..%2Fusers.json`, { headers: sH });
    ok(bkp.ok && bkp.token && /^aerieos-backup-/.test(bkp.bundle || '') && !bst.prepared && bfile.ok && blen === bkp.size && nofile.status === 404,
       `Download a backup packs one under a token of its own, arms no move, and its file downloads by its name alone (${JSON.stringify({ err: bkp.error, prepared: bst.prepared, status: bfile.status, blen, size: bkp.size, other: nofile.status })})`);
    const prep = await sApi('/api/move', { action: 'prepare', to: dst.base, repos: false, stores: [] });
    ok(prep.ok && prep.token && prep.bundle && prep.counts?.state >= 2, `Prepare to move arms the move, packs a bundle and shows a token once (${prep.error || prep.bundle})`);
    const st0 = await sApi('/api/move');
    ok(st0.prepared && st0.heard === 0 && st0.nodes === 2 && !st0.left, `...armed with no life, none of the two nodes having heard it yet (${JSON.stringify({heard: st0.heard, nodes: st0.nodes, left: st0.left})})`);
    const hello = (h, cen = { cpu: 2, mem_mb: 4096, arch: 'x86_64', system: 'linux' }) => fetch(src.base + '/api/v1/agent/hello', { method: 'POST', headers: h,
      body: JSON.stringify({ census: cen, version: '1', digest: 'sha256:' + '1'.repeat(64) }) });
    const told = await (await hello(nH)).json();
    ok(told.move?.url === dst.base && /^[0-9a-f]{64}$/.test(told.move?.expect || ''), `the node hears where it goes and a challenge of its own (${JSON.stringify(told.move)})`);
    ok((await sApi('/api/move')).heard === 1, '...and the source counts it among the nodes that heard');
    const bundle = Buffer.from(await (await fetch(src.base + '/api/move-bundle', { headers: sH })).arrayBuffer());
    ok(bundle.length > 500 && bundle.subarray(0, 8).toString() === 'BBMOVE1\n', `the bundle downloads, sealed and packed fresh (${bundle.length} bytes)`);
    const st1 = await sApi('/api/move');
    ok(st1.bundle && st1.bundle !== prep.bundle && st1.packed_at >= st1.made_at, `...under a new name, the record saying when (${st1.bundle})`);
    const form = new FormData();
    form.append('bundle', new Blob([bundle]), st1.bundle);
    form.append('token', 'not-the-token');
    const bad = await fetch(dst.base + '/setup/move', { method: 'POST', body: form });
    const badText = await bad.text();
    ok(bad.status === 200 && /not this bundle.{0,8}s move token/.test(badText), `another token is refused on the first page (${bad.status}: ${(badText.match(/<p class="err">([^<]*)/) || [])[1] || badText.slice(0, 120).replace(/\s+/g, ' ')})`);
    const pull = new FormData();
    pull.append('token', prep.token);
    pull.append('from', src.base);
    const r = await fetch(dst.base + '/setup/move', { method: 'POST', body: pull });
    const html = await r.text();
    ok(r.status === 200 && /The controller is here now/.test(html), `the destination pulls the bundle from the source with the token on its first page (${r.status}: ${(html.match(/<p class="err">([^<]*)/) || [])[1] || 'landed'})`);
    // Restarted on the state: the process before it still answered from
    // its own memory for a moment, so the node list is what says it is the
    // new one.
    const nodesThere = await (async () => { const end = Date.now() + patience(90000); while (Date.now() < end){
      try { const ns = ((await (await fetch(dst.base + '/api/v1/nodes', { headers: sH })).json()).nodes || []).map(n => n.name);
        if (ns.includes('mover')) return ns; } catch { /* restarting */ }
      await sleep(1000); } return []; })();
    ok(nodesThere.includes('mover') && nodesThere.includes('late'), `restarted on the state, the destination knows the source's accounts and nodes (${nodesThere.join(',')})`);
    const knock = await (await fetch(dst.base + '/api/v1/agent/moved', { method: 'POST', headers: nH, body: JSON.stringify({ node: en.node_id }) })).json();
    ok(knock.answer === told.move.expect, `the node's knock is answered with the challenge it holds (${(knock.answer || '').slice(0, 12)})`);
    const nh = (await (await fetch(dst.base + '/api/v1/nodes', { headers: sH })).json()).move || {};
    ok((nh.not_here || []).map(x => x.name).sort().join(',') === 'late,mover' && (nh.not_here || []).every(x => new RegExp(`^builderbot-agent follow \\S+ [0-9a-f]{64}$`).test(x.line)),
       `the destination's Nodes page lists both as not yet here, each with its follow line (${JSON.stringify((nh.not_here || []).map(x => x.name))})`);
    // The source learns the landing by asking (the destination has no page
    // address to tell it at), marks itself moved, and the late node, which
    // never heard the move, hears it with its challenge in the moved answer.
    const asked = await sApi('/api/move', { action: 'ask' });
    ok(asked.moved === true && asked.how === 'asked' && asked.to === dst.base, `the source asks the destination and marks itself moved on its answer (${JSON.stringify({moved: asked.moved, how: asked.how, err: asked.asked_error})})`);
    const ro = await sApi('/api/prefs', { project: 'alpha', gpu: 'off' });
    const gone = await hello(lH);
    const goneJ = await gone.json();
    ok(/read-only/.test(ro.error || '') && gone.status === 410 && goneJ.to === dst.base && goneJ.move?.url === dst.base && /^[0-9a-f]{64}$/.test(goneJ.move?.expect || ''),
       `...read-only after, telling a late node it moved, where, and its own challenge (${ro.error} / ${gone.status} / ${JSON.stringify(goneJ.move)})`);
    const lateKnock = await (await fetch(dst.base + '/api/v1/agent/moved', { method: 'POST', headers: lH, body: JSON.stringify({ node: lateEn.node_id }) })).json();
    ok(lateKnock.answer === goneJ.move.expect, 'and the late node\'s knock is answered with that challenge');
    ok(/no move is prepared|not withdrawn/.test((await sApi('/api/move', { action: 'forget' })).error || ''), 'Forget it is refused once the move landed');
    await fetch(dst.base + '/api/v1/agent/hello', { method: 'POST', headers: lH, body: JSON.stringify({ census: { cpu: 2, mem_mb: 4096, arch: 'x86_64', system: 'linux' }, version: '1', digest: 'sha256:' + '1'.repeat(64) }) });
    const nh2 = (await (await fetch(dst.base + '/api/v1/nodes', { headers: sH })).json()).move || {};
    ok((nh2.not_here || []).map(x => x.name).join(',') === 'mover', `a node that said hello to the destination is off the not-yet-here list (${JSON.stringify((nh2.not_here || []).map(x => x.name))})`);
    src.stop();
    dst.stop();
  }
  // Forget it withdraws an armed move: the key gone, the nodes told nothing more.
  {
    const src = await controller('src2');
    const sH = { Authorization: 'Basic ' + Buffer.from(`${OWNER.username}:${OWNER.password}`).toString('base64'), 'Content-Type': 'application/json' };
    const sApi = async (path, body) => (await fetch(src.base + path, body === undefined ? { headers: sH } : { method: 'POST', headers: sH, body: JSON.stringify(body) })).json();
    const en = await (await src.enroll('n1', false)).go();
    const nH = { Authorization: 'Bearer ' + en.token, 'Content-Type': 'application/json' };
    const prep = await sApi('/api/move', { action: 'prepare', to: 'http://127.0.0.1:1' });
    const hello = () => fetch(src.base + '/api/v1/agent/hello', { method: 'POST', headers: nH, body: JSON.stringify({ census: { cpu: 2, mem_mb: 4096, arch: 'x86_64', system: 'linux' }, version: '1', digest: 'sha256:' + '1'.repeat(64) }) });
    ok(prep.ok && (await (await hello()).json()).move?.expect, 'armed, the node hears the move');
    ok((await sApi('/api/move', { action: 'forget' })).ok && !(await (await hello()).json()).move?.url && !(await sApi('/api/move')).prepared,
       'Forget it withdraws it: the next hello carries no move, and nothing is armed');
    src.stop();
  }
}
await done(browser);
