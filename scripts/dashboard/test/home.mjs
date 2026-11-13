// Home (R218 step 5, the design's the-dashboard/home rule): the landing page.
// Tiles across the install, each a link into its page; Attention, the bell's
// own rows; the last ten jobs, each opening its row on the Jobs page; the
// pinned projects at a glance; read whole on open and light when the queue
// moves, never on a timer of its own.
import { URL, launch, newPage, ok, done, ready, sleep } from './lib.mjs';

const auth = { Authorization: 'Basic ' + Buffer.from('test:test').toString('base64') };
const base = URL.replace(/\/$/, '');
const api = async (path, body) => {
  const r = await fetch(base + path, body === undefined ? { headers: auth }
    : { method: 'POST', headers: { ...auth, 'Content-Type': 'application/json' }, body: JSON.stringify(body) });
  return r.status === 204 ? {} : r.json();
};
const until = async (fn, ms = 20000, step = 200) => {
  const end = Date.now() + ms;
  while (Date.now() < end){ const v = await fn(); if (v) return v; await sleep(step); }
  return null;
};

const browser = await launch();
const page = await newPage(browser, { viewport: { width: 1280, height: 900 } });
await page.goto(URL);
await ready(page);

// ---- the page, from the rail, at its own address ----------------------------
await page.click('#rail [data-rail="home"]');
await page.waitForSelector('.doc.on .hometiles .tile', { timeout: 20000 });
ok(await page.evaluate(() => tabOf(panes[0])?.kind === 'home' && location.hash === '#/home'),
   'Home is a page of its own on the rail, at #/home');

// ---- the tiles: across the install, and what /api/home says --------------------
{
  const h = await api('/api/home');
  const tiles = await page.$$eval('.doc.on .hometiles .tile', ts => ts.map(t => ({
    key: t.dataset.htile, value: t.querySelector('.tv')?.textContent, label: t.querySelector('.tl')?.textContent })));
  const by = Object.fromEntries(tiles.map(t => [t.key, t]));
  ok(['nodes', 'containers', 'jobs', 'sessions', 'updates', 'ci'].every(k => by[k]) && tiles.length === 6,
     `six tiles: nodes, containers, jobs, sessions, updates and CI (${tiles.map(t => t.key).join(', ')})`);
  ok(h.nodes && by.nodes.value === String(h.nodes.online) && by.jobs.value === String(h.jobs.running),
     `...the machines' and the queue's numbers are /api/home's (${by.nodes.value} of ${h.nodes?.enrolled} nodes, ${by.jobs.value} jobs running)`);
  ok(Array.isArray(h.jobs.last) && h.jobs.last.length <= 10 && typeof h.jobs.failed_today === 'number',
     `...which carries the last ten jobs and the ones failed today (${h.jobs.last.length} rows, ${h.jobs.failed_today} failed)`);
  // B59: the sessions tile is the number the Sessions page it opens counts.
  const listed = await page.evaluate(() => (state?.sessions || []).length);
  ok(by.sessions.value === String(listed) && listed > 0,
     `...and sessions open is what the Sessions page lists, terminals included (${by.sessions.value} of ${listed})`);
}

// ---- updates due counts each thing behind once (B28) ------------------------
{
  const n = await page.evaluate(() => {
    const was = state.attention;
    state.attention = [
      {kind: 'toolchain', tools: [{name: 'a'}, {name: 'b'}]},
      {kind: 'image', containers: [{name: 'c1'}, {name: 'c2'}, {name: 'c3'}]},
      {kind: 'nginx'}, {kind: 'agent'}, {kind: 'relocate'}, {kind: 'disk'},
      {kind: 'host', what: 'reboot'}, {kind: 'some-kind-added-later'}];
    const got = homeUpdates();
    state.attention = was;
    return got;
  });
  ok(n === 7, `updates due is two toolchains, three containers, nginx and an agent, and no move, failing disk or restart owed (${n})`);
}

// ---- a job that fails shows on Home by itself, through the jobs token ----------
{
  const q = await api('/api/v1/nodes', { action: 'exec', id: 'local', argv: ['sh', '-c', 'echo from home; exit 3'] });
  ok(/^j_/.test(q.job || ''), `a job is queued on the controller (${q.job})`);
  const seen = await until(() => page.evaluate(id => !!document.querySelector(`.doc.on [data-hjob="${id}"] .pill.bad`), q.job), 30000);
  ok(seen, '...and once it has failed, its row is on Last jobs with the failed pill, with nothing pressed');
  ok(await page.$eval('.doc.on .hometiles [data-htile="jobs"]', t => !t.classList.contains('bad')
       && /failed today/.test(t.querySelector('.ts.bad')?.textContent || '')),
     '...and the jobs tile says how many failed today, the line in the bad tone rather than the count running');
  ok(await page.$eval('.doc.on .hometiles [data-htile="jobs"]', t => t.getAttribute('href')) === '#/jobs/failed-today',
     '...and opens the Jobs page narrowed to the ones failed today (B74, B113)');
  await page.click(`.doc.on [data-hjob="${q.job}"]`);
  await page.waitForFunction(id => tabOf(panes[0])?.kind === 'jobs'
    && document.querySelector(`.jbrow[data-job="${id}"].focus .jblog`), q.job, { timeout: 15000 });
  ok(true, 'a row on Last jobs opens its job on the Jobs page, brought into view with its log open');
}

// ---- a tile is a link into its page ----------------------------------------
{
  await page.click('#rail [data-rail="home"]');
  await page.waitForSelector('.doc.on .hometiles [data-htile="nodes"]', { timeout: 15000 });
  await page.click('.doc.on .hometiles [data-htile="nodes"]');
  await page.waitForFunction(() => tabOf(panes[0])?.kind === 'nodes', null, { timeout: 15000 });
  ok(true, 'the nodes tile opens the Nodes page');
  await page.click('#rail [data-rail="home"]');
  await page.waitForSelector('.doc.on .hometiles [data-htile="containers"]', { timeout: 15000 });
  await page.click('.doc.on .hometiles [data-htile="containers"]');
  await page.waitForFunction(() => tabOf(panes[0])?.kind === 'docker', null, { timeout: 15000 });
  ok(true, '...and the containers tile the Containers page');
  await page.click('#rail [data-rail="home"]');
  await page.waitForSelector('.doc.on .homegrid', { timeout: 15000 });
  // Updates due are every node's toolchains, images, nginx and agents, which
  // one node's Library never holds: the tile brings Home's own
  // Attention card into view, where they are listed (B73).
  ok(await page.$eval('.doc.on .hometiles [data-htile="updates"]', t => t.getAttribute('href')) === '#/home',
     'the updates tile is a link to Home itself, not one node\'s Library');
  await page.click('.doc.on .hometiles [data-htile="updates"]');
  const marked = await page.waitForFunction(() => tabOf(panes[0])?.kind === 'home'
    && document.querySelector('.doc.on .hattn.focus'), null, { timeout: 5000 }).then(() => true, () => false);
  ok(marked, '...and a press marks the Attention card where the updates are listed');
  ok(await page.evaluate(() => homeTiles().find(t => t.key === 'updates').label === (homeUpdates() === 1 ? 'update due' : 'updates due')),
     '...its label in the singular for one');
}

// ---- Attention is the bell's rows, and the pinned projects are at a glance ----
{
  const same = await page.evaluate(() => {
    const card = document.querySelector('.doc.on .homegrid .hcard');
    return { home: card.querySelectorAll('.bnote').length, bell: needsRows().length,
             empty: !!card.querySelector('.empty') };
  });
  ok(same.home === same.bell && (same.bell > 0 || same.empty),
     `Attention carries the bell's own rows (${same.home} of ${same.bell})`);
  await page.evaluate(() => setProjectPinned('alpha', true));
  await until(() => page.evaluate(() => !!document.querySelector('.doc.on .hglance [data-hproj="alpha"]')), 15000);
  ok(await page.$eval('.doc.on .hglance [data-hproj="alpha"]', b => b.closest('.hproj').querySelector('.pstate') !== null),
     'a pinned space is on Spaces at a glance, with its session state');
  // In groups, as the Projects page is (R273): the ones in no group first,
  // then each group's name over its cards.
  await page.evaluate(async () => {
    setProjectPinned('beta', true);
    await postJSON('/api/project-group', { name: 'alpha', group: 'Zed' });
    await refresh();
  });
  await until(() => page.evaluate(() => !!document.querySelector('.doc.on .hgroup + .hglance [data-hproj="alpha"]')
    && !!document.querySelector('.doc.on .hglance [data-hproj="beta"]')), 15000);
  const order = await page.$$eval('.doc.on .hsect :is(.hgroup, [data-hproj])',
    els => els.map(e => e.matches('.hgroup') ? '#' + e.firstChild.textContent.trim() : e.dataset.hproj));
  ok(order.slice(-2).join() === '#Zed,alpha' && order.indexOf('beta') < order.indexOf('#Zed'),
     `Spaces at a glance is in groups, the Spaces page's order (${order.join()})`);
  await page.evaluate(async () => {
    setProjectPinned('beta', false);
    await postJSON('/api/project-group', { name: 'alpha', group: '' });
    await refresh();
  });
  await until(() => page.evaluate(() => !document.querySelector('.doc.on .hgroup')), 15000);
  await page.click('.doc.on .hglance [data-hproj="alpha"]');
  await page.waitForFunction(() => tabOf(panes[0])?.kind === 'notebook' && tabOf(panes[0])?.arg === 'alpha', null, { timeout: 15000 });
  ok(true, '...and its name opens the space\'s page');
  await page.click('#rail [data-rail="home"]');
  await page.waitForSelector('.doc.on .homegrid', { timeout: 15000 });
}

// ---- the top bar's search (B72) ------------------------------------------------
{
  ok(await page.$eval('#jump', i => i.placeholder) === 'jump to a page, space, container or node',
     'at 1280 the search\'s whole hint is shown, not cut mid-word');
  await page.fill('#jump', 'zzzz');
  await page.waitForSelector('#jumpList:not([hidden]) .jnone', { timeout: 5000 });
  ok(/nothing matches/.test(await page.$eval('#jumpList .jnone', e => e.textContent)),
     'a search that matches nothing says so');
  await page.fill('#jump', 'a');
  await page.waitForSelector('#jumpList:not([hidden]) .jrow', { timeout: 5000 });
  const n = await page.$$eval('#jumpList .jrow', rs => rs.length);
  await page.keyboard.press('ArrowDown');
  const marked = await page.$$eval('#jumpList .jrow', rs => rs.findIndex(r => r.classList.contains('on')));
  await page.keyboard.press('ArrowUp');
  const back = await page.$$eval('#jumpList .jrow', rs => rs.findIndex(r => r.classList.contains('on')));
  ok(n > 1 && marked === 1 && back === 0, `ArrowDown marks the second row and ArrowUp the first again (${n} rows; ${marked}, ${back})`);
  await page.keyboard.press('ArrowDown');
  const want = await page.$eval('#jumpList .jrow.on .jl', e => e.textContent);
  await page.keyboard.press('Enter');
  await sleep(400);
  ok(await page.$eval('#jumpList', l => l.hidden) && await page.$eval('#jump', i => i.value) === '',
     `...and Enter opens the marked row (${want})`);
  await page.click('#rail [data-rail="home"]');
  await page.waitForSelector('.doc.on .homegrid', { timeout: 15000 });
}

// ---- on a phone the cards stack and nothing scrolls sideways -----------------
{
  await page.setViewportSize({ width: 393, height: 851 });
  await sleep(400);
  const lay = await page.evaluate(() => {
    const [a, b] = [...document.querySelectorAll('.doc.on .homegrid .hcard')].map(c => c.getBoundingClientRect());
    return { stacked: b.top >= a.bottom - 1, over: document.documentElement.scrollWidth - innerWidth,
             tiles: [...document.querySelectorAll('.doc.on .hometiles .tile')].every(t => t.getBoundingClientRect().right <= innerWidth + 1) };
  });
  ok(lay.stacked && lay.over <= 0 && lay.tiles,
     `on a phone Attention and Last jobs stack, and the tiles fit the width (${JSON.stringify(lay)})`);
  await page.setViewportSize({ width: 1280, height: 900 });
}

// ---- no ring where it has no room -------------------------------------------
// A press still waiting after a moment wears a ring (pressHold), and on the
// rail that was a third line under the group pressed, pushing every group
// below it; on a sub-nav it widened the page pressed (the operator, 13 Nov:
// where the wheel would disrupt a small space, like the rail's icons, none
// pops up). A button with room still wears it.
{
  const slow = async r => { await sleep(1200); await r.continue().catch(() => {}); };
  const boxes = () => page.evaluate(() => [...document.querySelectorAll('#rail .ritem, .pane .bar.page .pseg button')]
    .filter(b => b.checkVisibility()).map(b => { const r = b.getBoundingClientRect(); return [r.top, r.left, r.width, r.height].map(Math.round).join(','); }).join(' '));
  const rings = () => page.evaluate(() => [...document.querySelectorAll('button.working, a.btn.working')].map(b => (b.getAttribute('aria-label') || b.textContent).trim().slice(0, 20)));
  await page.click('#rail [data-rail="home"]');
  await page.waitForSelector('.doc.on .hometiles .tile', { timeout: 20000 });
  await sleep(600);
  const before = await boxes();
  await page.route('**/api/**', slow);
  const seen = [], moved = [];
  for (const sel of ['#rail [data-rail="home"]', '.pane .bar.page .pseg button']){
    await page.click(sel);
    for (let i = 0; i < 12; i++){ await sleep(100); seen.push(...await rings()); if (await boxes() !== before) moved.push(sel); }
  }
  ok(seen.length === 0, `a group on the rail and a page of the sub-nav wear no ring while their page reads (${JSON.stringify([...new Set(seen)])})`);
  ok(moved.length === 0, `...and nothing on the rail or the sub-nav moves (${JSON.stringify([...new Set(moved)])})`);
  // A button with room: one in a row of its own, its press starting a slow read.
  const ring = await page.evaluate(async () => {
    const host = document.createElement('div');
    host.style.cssText = 'position:fixed;left:300px;top:300px;width:400px;display:flex;gap:6px;z-index:99';
    host.innerHTML = '<button type="button" id="ringProbe">Read it again</button>';
    document.body.append(host);
    const b = host.firstChild;
    b.onclick = () => { fetch('/api/home'); };
    return true;
  });
  await page.click('#ringProbe');
  const wore = await until(async () => (await rings()).includes('Read it again'), 1500, 50);
  // ...and the same button where one more thing does not fit: its row is as wide as it is.
  await page.evaluate(() => { const b = document.getElementById('ringProbe'); b.classList.remove('working'); b.parentElement.style.cssText += ';width:auto;flex-wrap:wrap;max-width:' + b.offsetWidth + 'px'; });
  await sleep(1500);
  await page.click('#ringProbe');
  let tight = false;
  for (let i = 0; i < 12; i++){ await sleep(100); if ((await rings()).includes('Read it again')) tight = true; }
  ok(ring && wore && !tight, `...while a button with room wears it, and the same button in a row it just fits does not (${wore}, ${tight})`);
  await page.unroute('**/api/**');
  await page.evaluate(() => document.getElementById('ringProbe').parentElement.remove());
  await sleep(1500);
}

ok(page.errors.length === 0, `zero console errors${page.errors.length ? ': ' + page.errors.join(' | ') : ''}`);
await done(browser);
