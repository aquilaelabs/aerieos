// What a person does in a browser on a first run, a step per run of person.mjs.
import { readFileSync, writeFileSync } from 'node:fs';
const sleep = ms => new Promise(r => setTimeout(r, ms));
export const steps = {
  // The walk's disks, and its projects' place if it asks, then the landing.
  async movedisks({ page, BASE, shot, tall }){
    await page.goto(BASE); await sleep(7000);
    await page.waitForSelector('[data-setdisksmake]', { timeout: 20000 });
    await page.click('[data-setdisksmake]'); await sleep(1200);
    const m = await page.$('.modal:not([hidden])'); if (!m) throw new Error('Make it asked nothing');
    await (await m.$('button.danger, button.primary')).click();
    await sleep(45000); await tall('72-walk-disks', 2400);
    const cards = await page.evaluate(() => [...document.querySelectorAll('#setupPanel .setstep')].map(c => c.querySelector('h3')?.textContent + ' [' + (c.querySelector('.pill')?.textContent || '') + ']: ' + c.querySelector('.setstepbody')?.innerText.replace(/\s+/g, ' ').slice(0, 400)));
    for (const c of cards.slice(2, 5)) console.log('-', c);
  },
  async moveplace({ page, BASE, shot, tall }){
    await page.goto(BASE); await sleep(7000);
    await page.selectOption('#stickPool', '/mnt/fast');
    await page.click('[data-stickpool]'); await sleep(1500);
    const m = await page.$('.modal:not([hidden])');
    if (m){ console.log((await m.innerText()).replace(/\s+/g, ' ').slice(0, 400)); await (await m.$('button.danger, button.primary')).click(); }
    for (let i = 0; i < 40; i++){ await sleep(5000); if (await page.evaluate(() => !!document.querySelector('[data-moveland]') && !document.querySelector('[data-moveland]').disabled)){ console.log('ready after', (i + 1) * 5, 's'); break; } }
    await tall('72b-walk-placed', 2400);
    const cards = await page.evaluate(() => [...document.querySelectorAll('#setupPanel .setstep')].map(c => c.querySelector('h3')?.textContent + ' [' + (c.querySelector('.pill')?.textContent || '') + ']: ' + c.querySelector('.setstepbody')?.innerText.replace(/\s+/g, ' ').slice(0, 300)));
    for (const c of cards.slice(3, 5)) console.log('-', c);
  },
  async moveland({ page, BASE, shot, tall, args }){
    // What the controller answers the landing with, said whole: a refusal
    // is a toast that is gone before a screenshot is.
    page.on('response', async r => { if (/\/api\/move/.test(r.url()) && r.request().method() === 'POST') console.log('answered', r.status(), (await r.text().catch(() => '')).slice(0, 600)); });
    await page.goto(BASE); await sleep(7000);
    // A browser that lost its place (a new sign-in as setup) is on the plain
    // first run: back to the walk.
    if (!await page.$('[data-moveland]')){ const w = page.locator('text=Walk me through it').first(); if (await w.count()){ await w.click(); await sleep(1500);
      const mv = page.locator('[data-setwalk="move"]').first(); if (await mv.count()) await mv.click().catch(() => {}); await sleep(3000); } }
    await page.waitForSelector('[data-moveland]', { timeout: 30000 });
    await tall('73-walk-land', 2400);
    console.log('land enabled', await page.$eval('[data-moveland]', b => !b.disabled));
    // The token is asked for here only where the first page was not given it.
    if (await page.$('#landTok')) await page.fill('#landTok', readFileSync(new URL('run/move-token.txt', import.meta.url), 'utf8').trim());
    await page.setInputFiles('#landFile', new URL('run/moved.aeriemove', import.meta.url).pathname);
    await page.click('[data-moveland]'); await sleep(1200);
    const m = await page.$('.modal:not([hidden])'); if (!m) throw new Error('Land asked nothing');
    console.log((await m.innerText()).replace(/\s+/g, ' ').slice(0, 400));
    await (await m.$('button.danger, button.primary')).click();
    for (let i = 0; i < 40; i++){ await sleep(3000); const t = await page.evaluate(() => document.querySelector('#toasts, .toast, .notify')?.innerText || ''); if (t){ console.log('said:', t.slice(0, 300)); break; } }
    await sleep(15000); await shot('74-after-land'); console.log(page.url()); console.log((await page.innerText('body')).replace(/\n+/g, ' | ').slice(0, 500));
  },
  async movesignin({ page, BASE, shot, tall, phone }){
    await page.goto(BASE); await sleep(2000);
    await page.fill('#u', 'ada'); await page.fill('#p', 'firstrun-pass');
    await Promise.all([page.waitForNavigation(), page.click('button[type=submit]')]);
    await sleep(8000); await shot('75-signed-in'); console.log(page.url());
    await page.evaluate(() => { document.querySelector('.tourcard button')?.click(); });
    console.log((await page.innerText('body')).replace(/\n+/g, ' | ').slice(0, 900));
    await page.goto(BASE + '#/projects'); await sleep(5000); await tall('76-projects', 1200); console.log((await page.innerText('body')).replace(/\n+/g, ' | ').slice(0, 600));
    await page.goto(BASE + '#/machines/nodes'); await sleep(5000); await tall('77-nodes', 1200); console.log((await page.innerText('body')).replace(/\n+/g, ' | ').slice(0, 700));
  },
  // The first page as it is since the move token is all it asks (R175): yes,
  // a controller is moving here, with the token kept in run/move-token.txt.
  async movetoken({ page, BASE, shot, tall }){
    await page.goto(BASE); await sleep(1500);
    await page.check('input[name=walk][value=move]');
    await page.fill('#mt', readFileSync(new URL('run/move-token.txt', import.meta.url), 'utf8').trim());
    await Promise.all([page.waitForNavigation(), page.click('button[type=submit]')]);
    await sleep(9000);
    await tall('71-moving-here', 2400);
    const cards = await page.evaluate(() => [...document.querySelectorAll('#setupPanel .setstep')].map(c => c.querySelector('h3')?.textContent + ' [' + (c.querySelector('.pill')?.textContent || '') + ']: ' + (c.querySelector('.setstepbody')?.innerText || '').replace(/\s+/g, ' ')));
    for (const c of cards) console.log('-', c.slice(0, 500));
    console.log(page.url());
  },
  // A backup taken from the controller signed in to: what its bundle would
  // carry, then the bundle itself, its token and file kept in run/ as a
  // move's are.
  async backup({ page, BASE }){
    await page.goto(BASE); await sleep(4000);
    const pieces = await page.evaluate(async () => (await (await fetch('/api/move?pieces=1')).json()).pieces || []);
    for (const p of pieces) console.log('piece:', p.label, '|', p.on ? 'carried' : 'not carried', '|', p.size, 'bytes |', (p.about || '').slice(0, 160));
    const r = await page.evaluate(async () => (await fetch('/api/move', { method: 'POST', headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ action: 'backup', carry_key: false, repos: false, stores: [] }) })).json());
    if (!r.ok) throw new Error('no backup: ' + (r.error || JSON.stringify(r)));
    writeFileSync(new URL('run/move-token.txt', import.meta.url), r.token + '\n', { mode: 0o600 });
    console.log('bundle', r.bundle, r.size, 'bytes; counts', JSON.stringify(r.counts));
    const got = await page.request.get(BASE + '/api/move-backup?name=' + encodeURIComponent(r.bundle));
    writeFileSync(new URL('run/moved.aeriemove', import.meta.url), await got.body());
    console.log('downloaded', (await got.body()).length, 'bytes');
  },
  // Sign in as an account the moved controller had: signin NAME PASSWORD.
  async signin({ page, BASE, shot, args }){
    await page.goto(BASE + '/login'); await sleep(1500);
    await page.fill('#u', args[0]); await page.fill('#p', args[1] === '@token' ? readFileSync(new URL('run/move-token.txt', import.meta.url), 'utf8').trim() : args[1]);
    await Promise.all([page.waitForNavigation().catch(() => {}), page.click('button[type=submit]')]);
    await sleep(6000); await shot('75-signed-in');
    console.log(page.url(), '|', (await page.innerText('body')).replace(/\n+/g, ' | ').slice(0, 300));
  },
  // Which machine each space and each container is on, as the controller
  // signed in to says it: its nodes, its spaces' nodes, and the Containers
  // page's rows under each node.
  async where({ page, BASE }){
    await page.goto(BASE); await sleep(4000);
    const got = await page.evaluate(async () => {
      const get = async u => { try { return await (await fetch(u)).json(); } catch (e){ return { error: String(e) }; } };
      const nodes = (await get('/api/v1/nodes')).nodes || [];
      const st = await get('/api/status');
      const rows = [];
      for (const n of nodes){
        const d = await get('/api/docker?node=' + encodeURIComponent(n.id));
        const list = d.instances || d.rows || d.containers || [];
        rows.push([n.name, d.error ? 'says: ' + String(d.error).slice(0, 110) : list.map(r => `${r.project || r.space || '-'}/${r.name || r.instance || '?'}`).join('; ')]);
      }
      return { build: (await get('/api/meta')).version,
               nodes: nodes.map(n => `${n.id} ${n.name} ${n.kind} state=${n.state} live=${!!n.live} own=${!!((n.config || {}).own || n.own)}`),
               spaces: (st.projects || []).map(p => `${p.name} -> ${p.node_name || p.session_at || '-'}`), rows, moved: st.moved_to || '', arrived: !!(await get('/api/move')).arrived };
    });
    console.log('build', got.build, '| arrived by a move:', got.arrived);
    console.log('nodes:'); for (const n of got.nodes) console.log('  ' + n);
    console.log('spaces:'); for (const x of got.spaces) console.log('  ' + x);
    console.log('containers, by the node the Containers page lists them under:'); for (const [n, x] of got.rows) console.log(`  ${n}: ${x || 'none'}`);
  },
  // The next machine's first page: yes, a controller is moving here.
  async movefirst({ page, BASE, shot, tall, phone }){
    await page.goto(BASE); await sleep(1500);
    await page.check('input[name=walk][value=move]');
    await page.fill('#u', 'setup'); await page.fill('#p', 'setup-pass-1'); await page.fill('#p2', 'setup-pass-1');
    await Promise.all([page.waitForNavigation(), page.click('button[type=submit]')]);
    await sleep(9000);
    await tall('71-walk', 2400); await phone('71-walk-phone', 3400);
    const cards = await page.evaluate(() => [...document.querySelectorAll('#setupPanel .setstep')].map(c => c.querySelector('h3')?.textContent + ' [' + (c.querySelector('.pill')?.textContent || '') + ']: ' + c.querySelector('.setstepbody')?.innerText.replace(/\s+/g, ' ')));
    for (const c of cards) console.log('-', c.slice(0, 700));
  },
  // A move, from a machine that has been through a first run: Prepare to move,
  // its token and bundle kept in run/ for moveland on the next machine.
  async moveprepare({ page, BASE, shot, tall }){
    await page.goto(BASE + '#/controller/settings'); await sleep(5000);
    await page.evaluate(() => { document.querySelector('.tourcard button')?.click(); });
    await page.locator('text=Move this controller').first().click(); await sleep(3000);
    await page.waitForSelector('[data-moveprep]', { timeout: 30000 });
    await tall('60-move-before', 1500);
    console.log((await page.innerText('[data-sect="settings:move"], .main, body')).replace(/\n+/g, ' | ').slice(0, 900));
    const repos = page.locator('[data-movepiece="repos"]'); if (await repos.count()) await repos.check();
    await page.click('[data-moveprep]');
    await page.waitForSelector('a[href="/api/move-bundle"]', { timeout: 60000 }); await sleep(800);
    await tall('61-move-armed', 1500);
    const token = await page.evaluate(() => [...document.querySelectorAll('.hint code')].map(c => c.textContent).find(t => t.length > 12));
    writeFileSync(new URL('run/move-token.txt', import.meta.url), token || '');
    console.log('token', token ? `${token.length} characters` : 'NOT SHOWN');
    const [dl] = await Promise.all([page.waitForEvent('download', { timeout: 300000 }), page.click('a[href="/api/move-bundle"]')]);
    await dl.saveAs(new URL('run/moved.aeriemove', import.meta.url).pathname);
    console.log('bundle', dl.suggestedFilename());
  },
  async pageshots({ page, BASE }){
    const go = async (hash, name, h) => {
      await page.setViewportSize({ width: 1440, height: h }); await page.goto(BASE + hash); await sleep(6500);
      await page.evaluate(() => { for (const b of document.querySelectorAll('.tourcard button')) if (/Skip/.test(b.textContent)) { b.click(); break; } document.querySelectorAll('details.sect').forEach(d => { d.open = true; }); }); await sleep(800);
      await page.screenshot({ path: new URL(`run/${name}-desk.png`, import.meta.url).pathname });
      await page.setViewportSize({ width: 393, height: Math.round(h * 1.9) }); await sleep(700);
      await page.evaluate(() => { document.querySelectorAll('details.sect').forEach(d => { d.open = true; }); }); await sleep(500);
      await page.screenshot({ path: new URL(`run/${name}-phone.png`, import.meta.url).pathname });
    };
    await go('#/controller/machine', '50-machine', 4600);
    await go('#/machines/storage', '51-storage', 3400);
    await go('#/controller/settings', '52-settings', 1600);
    console.log('shots');
  },

  async formshot({ page, BASE, phone }){
    await page.goto(BASE + '#/machines/storage'); await sleep(7000);
    await page.evaluate(() => { document.querySelector('.tourcard button')?.click(); const d = document.querySelector('details[data-sect="storage:shares"]'); if (d) d.open = true; });
    await sleep(500);
    await page.selectOption('#stShareExport', 'smb'); await page.fill('#stShareName', 'documents'); await sleep(300);
    await page.locator('.stnewshare').screenshot({ path: new URL('run/41-form-desk.png', import.meta.url).pathname });
    await page.setViewportSize({ width: 393, height: 1400 }); await sleep(500);
    await page.locator('.stnewshare').screenshot({ path: new URL('run/41-form-phone.png', import.meta.url).pathname });
    await page.setViewportSize({ width: 1440, height: 1000 });
    console.log('shot');
  },

  async storageshares({ page, BASE, tall, phone, shot }){
    await page.goto(BASE + '#/machines/storage'); await sleep(7000);
    const sect = await page.$('details[data-sect="storage:shares"]');
    if (sect) await sect.scrollIntoViewIfNeeded();
    await page.evaluate(() => { const d = document.querySelector('details[data-sect="storage:shares"]'); if (d) d.open = true; });
    await sleep(600);
    const say = async () => (await page.$eval('details[data-sect="storage:shares"]', e => e.innerText)).replace(/\n+/g, ' | ').slice(0, 900);
    console.log('BEFORE', await say());
    // A new internal share
    await page.fill('#stShareName', 'documents'); await page.fill('#stSharePath', 'documents');
    await page.click('[data-stshare="set"]'); await sleep(1500);
    for (let i = 0; i < 40; i++){ await sleep(1500); await page.evaluate(() => { if (typeof storageData !== 'undefined') {} }); const t = await page.$eval('details[data-sect="storage:shares"]', e => e.innerText); if (/documents/.test(t.split('A share is a folder')[0])) break; if (i === 15) await page.reload(), await sleep(6000), await page.evaluate(() => { const d = document.querySelector('details[data-sect="storage:shares"]'); if (d) d.open = true; }); }
    console.log('INTERNAL', await say());
    // Edit: export it, private, this person read/write
    await page.click('[data-stshareedit="documents"]'); await sleep(500);
    await page.selectOption('#stShareExport', 'smb'); await sleep(300);
    await shot('40-share-edit');
    await page.selectOption('[data-stwho="ada"]', 'rw');
    await page.locator('details[data-sect="storage:shares"]').screenshot({ path: new URL('run/40-shares-section.png', import.meta.url).pathname }).catch(e => console.log(String(e).slice(0,100)));
    await page.click('[data-stshare="set"]'); await sleep(14000); await page.reload(); await sleep(7000);
    await page.evaluate(() => { const d = document.querySelector('details[data-sect="storage:shares"]'); if (d) d.open = true; });
    console.log('EXPORTED', await say());
  },

  async openproject({ page, BASE, tall, phone, args, shot }){
    await page.goto(BASE + '#/projects/' + (args[0] || 'first-project')); await sleep(7000);
    await tall('21-project', 1300); await phone('21-project-phone', 1500);
    console.log((await page.evaluate(() => document.querySelector('.nb:not([hidden])')?.innerText || document.querySelector('.pane .doc.on')?.innerText || '')).replace(/\n+/g, ' | ').slice(0, 700));
    const go = await page.$('.nb button:has-text("Start agent")');
    if (go){ console.log('Start agent dead?', await go.isDisabled()); await go.click(); await sleep(2500); await shot('22-chooser'); console.log((await page.evaluate(() => document.querySelector('.nbagentmenu, .chooser, .menu:not([hidden]), .pop:not([hidden])')?.innerText || '')).replace(/\n+/g, ' | ').slice(0, 400)); }
  },

  async create({ page, BASE, shot, tall, args }){
    await page.goto(BASE); await sleep(5000);
    await page.click('[data-setproject], .hstart [data-hstart="project"]'); await sleep(1500);
    const m = await page.$('.modal:not([hidden]):has(#pName)');
    const fields = await m.$$eval('input,select,textarea,button', xs => xs.map(x => `${x.tagName}#${x.id}${x.type ? ':' + x.type : ''}${x.disabled ? ':dead' : ''}[${(x.textContent || x.placeholder || '').trim().slice(0, 26)}]`));
    await page.fill('#pName', args[0] || 'first-project');
    await sleep(500); await shot('18-project-filled');
    const go = await m.$('.actbar button.primary, button.primary'); console.log('primary:', await go.innerText(), await go.isDisabled());
    await go.click();
    for (let i = 0; i < 30; i++){ await sleep(2000); const open = await page.$('.modal:not([hidden])'); if (!open) { console.log('dialog closed after', (i + 1) * 2, 's'); break; } }
    await sleep(2500); await tall('19-after-project', 1500);
    console.log('toast:', await page.evaluate(() => [...document.querySelectorAll('.toast, .notice, #notify *')].map(x => x.innerText).join(' | ').slice(0, 400)));
    console.log((await page.evaluate(() => [...document.querySelectorAll('#setupPanel .setstep')].map(x => x.querySelector('h3')?.innerText + ': ' + x.querySelector('.pill')?.innerText).join(' | '))));
  },
  async finish({ page, BASE, shot, tall, phone }){
    await page.goto(BASE); await sleep(5000);
    await page.click('#setupFinish'); await sleep(5000);
    console.log(page.url()); await tall('20-home', 1300); await phone('20-home-phone', 1700);
    console.log((await page.evaluate(() => document.querySelector('.pane .doc.on')?.innerText || '')).replace(/\n+/g, ' | ').slice(0, 900));
  },

  async shares({ page, BASE, shot, tall }){
    await page.goto(BASE); await sleep(5000);
    await tall('15a-shares-before', 1500);
    console.log((await page.evaluate(() => [...document.querySelectorAll('#setupPanel .setstep')].find(x => /^\s*\d\s*Shares/.test(x.textContent))?.innerText || 'no card')).replace(/\n+/g, ' | ').slice(0, 500));
    await page.check('#setShareExport');
    await page.click('[data-setshares]');
    for (let i = 0; i < 60; i++){ await sleep(2000); const t = await page.$eval('#setupPanel', e => e.innerText); if (/Open an exported one/.test(t)) { console.log('shares up after', (i + 1) * 2, 's'); break; } if (i === 59) console.log('never came'); }
    await tall('15-shares', 1500);
    console.log((await page.evaluate(() => [...document.querySelectorAll('#setupPanel .setstep')].find(x => /^\s*\d\s*Shares/.test(x.textContent))?.innerText || '')).replace(/\n+/g, ' | ').slice(0, 500));
  },
  async nameclaude({ page, BASE, shot, tall }){
    await page.goto(BASE); await sleep(5000);
    await page.fill('#setName', 'Ada Lovelace'); await page.fill('#setEmail', 'ada@example.com');
    await page.click('[data-setgit]'); await sleep(3000);
    const t0 = Date.now(); await page.click('[data-setclaude]');
    for (let i = 0; i < 90; i++){ await sleep(3000); const d = await page.evaluate(() => [...document.querySelectorAll('#setupPanel .setstep')].find(x => /Claude Code/.test(x.textContent))?.innerText || ''); if (/done/.test(d)){ console.log('claude done after', Math.round((Date.now() - t0) / 1000), 's:', d.replace(/\n+/g, ' | ').slice(0, 200)); break; } if (i === 89) console.log('claude still:', d.replace(/\n+/g, ' | ').slice(0, 300)); }
    await tall('16-claude', 1500);
  },
  async project({ page, BASE, shot, tall }){
    await page.goto(BASE); await sleep(5000);
    await page.click('[data-setproject]'); await sleep(2000); await shot('17-new-project');
    console.log((await page.evaluate(() => document.querySelector('.modal:not([hidden])')?.innerText || 'no dialog')).replace(/\n+/g, ' | ').slice(0, 700));
  },

  async landing2({ page, BASE, shot }){
    await page.goto(BASE); await sleep(1200); await shot('10-landing');
    console.log((await page.innerText('body')).replace(/\n+/g, ' | ').slice(0, 500));
    await page.fill('#u', 'ada'); await page.fill('#p', 'firstrun-pass'); await page.fill('#p2', 'firstrun-pass');
    await Promise.all([page.waitForNavigation(), page.click('button[type=submit]')]);
    await sleep(5000); console.log(page.url());
  },
  async makeit({ page, BASE, shot, tall }){
    await page.goto(BASE); await sleep(6000);
    await page.waitForSelector('[data-setdisksmake]', { timeout: 20000 });
    await tall('11-disks-before', 1500);
    const plan = await page.evaluate(() => document.querySelector('.setplan')?.parentElement.innerText || '(no plan)'); console.log(plan.slice(0, 700));
    console.log('Make it dead?', await page.$eval('[data-setdisksmake]', b => b.disabled));
    await page.click('[data-setdisksmake]'); await sleep(1200);
    await shot('12-ask');
    const m = await page.$('.modal:not([hidden])'); if (m){ console.log((await m.innerText()).slice(0, 600)); const go = await m.$('button.danger, button.primary'); await go.click(); }
    else throw new Error('Make it asked nothing: the press was lost, and nothing was made');
    await sleep(4000); await tall('13-making', 1500);
    console.log(await page.evaluate(() => (document.querySelector('.notify, #toasts, .toast')?.innerText || '')));
  },
  async jobs({ page, BASE, args }){
    await page.goto(BASE); await sleep(2500);
    const j = await page.evaluate(async () => (await (await fetch('/api/v1/jobs')).json()));
    for (const x of (j.jobs || []).slice(0, Number(args[0] || 8))) console.log(x.id, x.state, x.type, x.spec?.apply || x.spec?.action || '', x.error || '', (x.ended || 0) - (x.started || 0) + 's');
    const id = args[1] || (j.jobs || [])[0]?.id;
    if (id){ const d = await page.evaluate(async i => (await (await fetch('/api/v1/jobs?id=' + i)).json()), id); console.log('--- log of', id); console.log(String(d.log || '').slice(-1800)); }
  },
  async api({ page, BASE, args }){
    await page.goto(BASE); await sleep(2500);
    const r = await page.evaluate(async ([p, b]) => { const o = b ? { method: 'POST', headers: { 'Content-Type': 'application/json' }, body: b } : {}; const t = await (await fetch(p, o)).text(); return t; }, [args[0], args[1] || '']);
    console.log(r.slice(0, Number(args[2] || 3000)));
  },
  async consolepw({ page, BASE, args }){
    await page.goto(BASE); await sleep(4000);
    const r = await page.evaluate(async pw => { await loadNodes(); const n = (nodesList || []).find(x => x.config?.own); const j = await (await postJSON('/api/v1/nodes', { action: 'console', id: n?.id, password: pw })).json(); return { id: n?.id, j, held: state?.held }; }, args[0]);
    console.log(JSON.stringify(r));
    for (let i = 0; i < 20; i++){ await sleep(2000); const d = await page.evaluate(async id => (await (await fetch('/api/v1/jobs?id=' + id)).json()), r.j.job); if (['succeeded','failed','canceled'].includes(d.state)){ console.log(d.state, String(d.log || '').slice(0, 500)); break; } }
  },
  async landing({ page, BASE, shot, phone }){
    await page.goto(BASE); await sleep(1500);
    await shot('01-landing'); console.log(page.url()); console.log((await page.textContent('body')).replace(/\s+/g, ' ').slice(0, 900));
    await phone('01-landing-phone', 900);
  },
  async account({ page, BASE, shot, args }){
    await page.goto(BASE); await page.fill('#u', 'ada'); await page.fill('#p', 'firstrun-pass'); await page.fill('#p2', 'firstrun-pass');
    await Promise.all([page.waitForNavigation(), page.click('button[type=submit]')]);
    await sleep(6000); await shot('02-after-account'); console.log(page.url());
  },
  // press HASH TEXT NAME: the page at HASH, the first visible button reading
  // TEXT pressed, and the page photographed after.
  async press({ page, BASE, tall, args }){
    await page.goto(BASE + (args[0] || '')); await sleep(5000);
    const b = page.locator('button:visible', { hasText: args[1] }).first();
    await b.click(); await sleep(Number(args[3] || 5000));
    await tall(args[2] || 'press', 1600);
    console.log(page.url());
    console.log((await page.evaluate(() => (document.querySelector('.modal:not([hidden])') || document.querySelector('.pane .doc.on') || document.body).innerText)).replace(/\n{2,}/g, '\n').slice(0, 1500));
  },
  // words HASH HEADING...: the text of each section of the page at HASH whose
  // heading reads one of HEADING, as a person reads it.
  async words({ page, BASE, args }){
    await page.goto(BASE + (args[0] || '')); await sleep(9000);
    const got = await page.evaluate(heads => [...document.querySelectorAll('.pane .doc.on details, .pane .doc.on section, .pane .doc.on .card')]
      .filter(s => heads.some(h => (s.querySelector('summary, h2, h3, h4')?.innerText || '').trim().startsWith(h)))
      .map(s => s.innerText.replace(/\n{2,}/g, '\n').slice(0, 3000)), args.slice(1));
    console.log([...new Set(got)].join('\n=====\n'));
  },
  async look({ page, BASE, tall, phone, args }){
    await page.goto(BASE + (args[0] || '')); await sleep(Number(args[2] || 6000));
    await tall(args[1] || 'look', Number(args[3] || 2200));
    console.log(page.url());
    console.log((await page.evaluate(() => (document.querySelector('#setupPanel:not([hidden])') || document.querySelector('.pane .doc.on') || document.body).innerText)).replace(/\n{2,}/g, '\n').slice(0, Number(args[4] || 3500)));
  },
};
