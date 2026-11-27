// The Settings tab (roadmap R29, then the operator's cut): what is left after
// asking which settings need to exist at all. Two switches, since the Claude
// Code update settings went with the install itself (R47), plus the commit
// identity, which became a project's own setting in its dialog. What is
// exercised for real: the store through the endpoint, the tab's rows, the
// identity landing in the repo's own config through /api/prefs and coming out
// of aerie settings, and bb_setting (the boot scripts' read) run as bash
// against the same file.
import { launch, newPage, ok, skip, done, ready, saveDialog, sectSave, rnSect, splitPick, refreshUntil, openFold, URL, DIR, unfold, until, settled, OWNER, section, pageCall } from './lib.mjs';
import { readFileSync, existsSync, mkdirSync, writeFileSync, rmSync } from 'node:fs';
import { execFileSync } from 'node:child_process';
import { fileURLToPath } from 'node:url';
import { dirname, join } from 'node:path';

const HERE = dirname(fileURLToPath(import.meta.url));
const FILE = `${DIR}/state/settings.json`;
const read = () => existsSync(FILE) ? JSON.parse(readFileSync(FILE, 'utf8')) : {};
const browser = await launch();
const page = await newPage(browser, { viewport: { width: 1280, height: 1000 } });
await page.goto(URL);
await ready(page);
const post = (path, body) => pageCall(page, path, body);

// ---- the tab ---------------------------------------------------------------
await page.evaluate(() => openSettingsTab());
// Controller settings is a page of settings (the operator, 16 Oct): a
// section is picked from its list before its fields are used.
await page.waitForSelector('.settingstab .snav [data-spick="idle"]', { timeout: 15000 }); await splitPick(page, 'idle');
// The section on show, pressed again at a desk, is no change: no fade (B317).
await page.click('.settingstab .snav [data-spick="idle"]');
ok(await page.evaluate(() => !document.querySelector('.fghost')), 'the section on show, pressed again, fades nothing');
// One tree, two products (roadmap R54, step 6): the switch that offers the
// unvetted git hosts, hypervisors and OS families is a developer's (on the
// Debug page, below), off by default, and the header carries the word while
// it is on.
ok(!(await read()).offer_unvetted && await page.$eval('#devtag', e => e.hidden), 'dev features start off, and the header says nothing while they are');
await post('/api/settings', { set: { offer_unvetted: true } });
await page.waitForFunction(() => !document.querySelector('#devtag')?.hidden, null, { timeout: 30000 });
ok(await page.$eval('#devtag', e => e.textContent.trim() === 'dev'),
   '...and says dev once it is on, so two dashboards are never confused');
// ...and each dev feature it offers says so where it is offered (R102, the
// operator, 22 Oct: a page hid two of them with it off and nothing said
// why): the two dev apps' cards in the Library's For you and their
// switches, never the Android app.
await page.evaluate(() => { openLibrary(); loadLibrary(); });
await page.waitForSelector('.pane .doc.on .librarytab .lcard[data-lrow="companion:vscode"]', { timeout: 15000 });
const marked = await page.evaluate(() => Object.fromEntries([...document.querySelectorAll('.pane .doc.on .librarytab .lcard[data-lrow^="companion:"]')]
  .map(c => [c.dataset.lrow.slice('companion:'.length), !!c.querySelector('.lcmeta .pill.devmark')])));
await page.evaluate(() => openSettingsTab());
await page.waitForSelector('.settingstab [data-set="apps_vscode"]', { state: 'attached', timeout: 15000 });
const switches = await page.evaluate(() => ['apps_android', 'apps_vscode', 'apps_companion']
  .map(k => !!document.querySelector(`.settingstab [data-set="${k}"]`)?.closest('label')?.querySelector('.pill.devmark')));
ok(marked.vscode && marked.companion && !marked.android && switches.join() === 'false,true,true',
   `...and a dev feature says dev where it is offered: the VS Code and companion cards and switches, not Android's (${JSON.stringify({ marked, switches })})`);
await post('/api/settings', { set: { offer_unvetted: false } });
await page.waitForFunction(() => document.querySelector('#devtag')?.hidden, null, { timeout: 30000 });
// Reset AerieOS: a red verb at the foot of the tab behind a typed word,
// refused without it, and never pressed here, since it re-executes the
// server this whole suite is talking to. The move itself is proved at the
// module below, on a directory of its own.
ok(await page.$eval('.settingstab [data-group="Reset"] #setReset', b => /Reset AerieOS/.test(b.textContent) && b.classList.contains('danger')),
   'Reset AerieOS sits in its own section as a red verb');
await splitPick(page, 'reset');
await page.click('.settingstab #setReset');
await page.waitForSelector('#resetmodal:not([hidden]) #resetGo', { timeout: 10000 });
ok(await page.$eval('#resetGo', b => b.disabled)
   && await page.$eval('#resetBody .hint.bad', h => /Space files stay/.test(h.textContent)),
   '...which opens a dialog with a typed confirmation, the real button asleep, saying space files stay');
await page.fill('#resetWord', 'reset');
ok(await page.$eval('#resetGo', b => !b.disabled), '...and wakes on the word');
await page.click('#resetKeep');
ok(await page.$eval('#resetmodal', m => m.hidden), '...and Keep it closes it with nothing done');
const noword = await post('/api/reset', { confirm: 'yes' });
ok(noword.status === 400 && /type reset to confirm; nothing was changed/.test(noword.body.error || ''),
   `the endpoint refuses anything but the word (${noword.body.error})`);
await section("+ r.dest +", async () => {
  const { execFileSync } = await import('node:child_process');
  const out = execFileSync('python3', ['-c', `
import importlib.util, json, os, tempfile
from pathlib import Path
spec = importlib.util.spec_from_file_location('s', ${JSON.stringify(new globalThis.URL('../settings.py', import.meta.url).pathname)})
m = importlib.util.module_from_spec(spec); spec.loader.exec_module(m)
d = Path(tempfile.mkdtemp())
(d / 'users.json').write_text('{}'); (d / 'logs').mkdir(); (d / 'logs' / 'a.log').write_text('x')
(d / '.reset-20260101-000000').mkdir(); (d / '.reset-20260101-000000' / 'old').write_text('o')
(d / 'runner-tokens').mkdir()
r = m.reset_state(d); dest = r["dest"]
print(json.dumps({"left": sorted(p.name for p in d.iterdir()), "moved": sorted(p.name for p in dest.iterdir()),
                  "old_kept": (d / '.reset-20260101-000000' / 'old').is_file(), "dest": dest.name, "kept": r["kept"]}))
`], { encoding: 'utf8' });
  const r = JSON.parse(out);
  ok(r.moved.join() === 'logs,users.json' && r.left.join() === '.reset-20260101-000000,' + r.dest + ',runner-tokens'
     && r.old_kept && /^\.reset-\d{8}-\d{6}$/.test(r.dest) && r.kept.join() === 'runner-tokens',
     `the reset moves everything into a dated directory beside it, leaves earlier resets and the root-only token store alone, and says what it kept (${JSON.stringify(r)})`);
});
const groups = await page.$$eval('.settingstab [data-group]', gs => gs.map(g => g.dataset.group));
// No Update window here: the fixture is the container edition, which cannot apply a release to itself (B648).
ok(groups.join('|') === 'Logs|Idle sessions|Storage|Update checks|Vetted catalog|Apps|Mail|Room on the nodes|Backup|Backup copies|Maintenance|Move|Reset',
   `the tab's groups are the ones that survived the question "does this need to exist": the logs, the idle rule, where what grows is kept (the operator, 10 Oct), how often each update check runs (R176), the vetted catalog's address and its mirror (R169), the apps offered (R272), the mail server the bell goes out through (R149), the room a node keeps (R110), the terminal tabs open in (R133), maintenance mode (the owner's), and the reset (${groups.join(', ')})`);
await section("The room a node keeps", async () => {
  // The room a node keeps (R110 steps 1 and 5): whole numbers held to their
  // range by the server, the browser's own min and max beside them.
  const room = await page.$eval('[data-group="Room on the nodes"]', g => [...g.querySelectorAll('input[type=number]')]
    .map(i => `${i.dataset.set}=${i.value}:${i.min}-${i.max}`).join(' '));
  const set = async v => (await page.evaluate(async b => (await fetch('/api/settings', {method: 'POST',
    headers: {'Content-Type': 'application/json'}, body: JSON.stringify({set: b})})).json(), v));
  const good = await set({room_floor_gb: 25, container_mem_gb: 4});
  const bad = await set({room_mem_pct: 120});
  await set({room_floor_gb: 10, container_mem_gb: 0});
  ok(room === 'room_floor_gb=10:1-1000 room_mem_pct=92:50-99 container_mem_gb=0:0-1024' && good.ok
     && /whole number from 50 to 99/.test(bad.error || ''),
     `Room on the nodes is three numbers with their ranges, saved in range and refused out of it (${room}; ${JSON.stringify(bad)})`);
});
await section("The vetted catalog", async () => {
  // The vetted catalog (R169 step 6, B444): its address, saved as an
  // address where every text was held to a hostname (B445), and a mirror
  // imported from the page only when its index is the maintainers'.
  await splitPick(page, 'catalog');
  const G = '.settingstab [data-group="Vetted catalog"]';
  const drawn = await page.$eval(G, g => ({ url: g.querySelector('[data-set="catalog_url"]')?.value || '', said: g.textContent.replace(/\s+/g, ' ') }));
  const set = async v => (await page.evaluate(async b => (await fetch('/api/settings', {method: 'POST',
    headers: {'Content-Type': 'application/json'}, body: JSON.stringify({set: b})})).json(), v));
  const good = await set({catalog_url: 'https://example.com/catalog/'});
  const bad = await set({catalog_url: 'ftp://example.com/catalog/'});
  const mail = await set({smtp_port: '587', smtp_from: 'AerieOS <bb@example.com>', tls_email: 'me@example.com'});
  await set({catalog_url: 'https://raw.githubusercontent.com/aquilaelabs/aerieos-catalog/main/', smtp_port: '', smtp_from: '', tls_email: ''});
  ok(/aerieos-catalog/.test(drawn.url) && /No mirror imported/.test(drawn.said) && good.ok && /an address like/.test(bad.error || '') && mail.ok,
     `Vetted catalog draws the catalog's address and says no mirror is held; an address saves, a port, a From line and an email too, and ftp is refused (${drawn.url}; ${bad.error}; ${mail.error || 'mail saved'})`);
  // When the index in use was made, and a mirror held, are the status read's
  // own keys: drawn from there, where the groups are handed its settings part.
  const lines = await page.evaluate(() => {
    const keep = [state.catalog_index, state.catalog_mirror];
    const d = document.createElement('div');
    const read = () => { d.innerHTML = catalogIntro(); return [d.querySelector('[data-catalogmade]')?.textContent || '', d.textContent.replace(/\s+/g, ' '), catalogStatus()]; };
    state.catalog_index = null; state.catalog_mirror = null;
    const none = read();
    state.catalog_index = { made: '2026-10-29T00:00:00Z', read: Math.floor(Date.now() / 1000) - 7200 };
    state.catalog_mirror = { packs: 3, repos: 2, generated: '2026-10-28T00:00:00Z' };
    const some = read();
    [state.catalog_index, state.catalog_mirror] = keep;
    return { none, some };
  });
  ok(lines.none[0] === 'No index has been read yet.' && /No mirror imported/.test(lines.none[1]) && lines.none[2] === 'applies at once'
     && /^The index in use was made 2026-10-29T00:00:00Z, read 2 ?h/.test(lines.some[0]) && /3 entries from 2 repositories, made 2026-10-28/.test(lines.some[1])
     && /a mirror made 2026-10-28T00:00:00Z answers/.test(lines.some[2]),
     `...and says when the index in use was made and what mirror is held, from the status read's own keys (${lines.some[0]} | ${lines.some[2]})`);
  const dir = `${DIR}/mirror-src/catalog-mirror`;
  mkdirSync(`${dir}/repos`, { recursive: true });
  writeFileSync(`${dir}/index.json`, JSON.stringify({ version: 1, generated: '2026-10-29T00:00:00Z', packs: [] }));
  writeFileSync(`${dir}/index.sig`, 'builderbot-catalog-ed25519-signature ' + '00'.repeat(64) + '\n');
  const arc = `${DIR}/mirror.tar.gz`;
  execFileSync('tar', ['-czf', arc, '-C', `${DIR}/mirror-src`, 'catalog-mirror']);
  await page.setInputFiles(`${G} #mirrorFile`, arc);
  await page.waitForFunction(() => [...document.querySelectorAll('#toast .tst')].some(t => /not imported/.test(t.textContent)), null, { timeout: 15000 });
  const toast = await page.$$eval('#toast .tst', ts => ts.map(t => t.textContent.trim()).find(t => /not imported/.test(t)) || '');
  const after = await page.$eval(G, g => g.textContent.replace(/\s+/g, ' '));
  ok(/does not match|no catalog key/.test(toast) && /No mirror imported/.test(after),
     `a mirror whose index another key signed is refused on Import, said, and nothing is held (${toast})`);
  rmSync(`${DIR}/mirror-src`, { recursive: true, force: true });
  rmSync(arc, { force: true });
});
// Sections, and a page of settings (the operator, 16 Oct): a list of them
// beside the one picked, each row saying what is in it, and Revert beside
// each Apply putting the section's fields back to what is saved.
await section("Sections, and a page of settings", async () => {
  const sects = await page.$$eval('.settingstab details.sect', ds => ds.map(d => d.querySelector('summary .t').textContent));
  const rows = await page.$$eval('.settingstab .snav [data-spick]', bs => bs.map(b => ({ k: b.dataset.spick, said: b.querySelector('.rtags .dim')?.textContent || '' })));
  ok(sects.length >= 6 && rows.length === sects.length && rows.every(r => r.said),
     `the tab is a list of its sections beside the one picked, each saying what is in it (${rows.map(r => r.k).join(', ')})`);
  const was = await page.$eval('#idleMin', i => i.value);
  await splitPick(page, 'idle');
  // Apply and Revert sleep until a field differs from what is saved, and
  // again when it is typed back (R218 step 32, as Profile's do).
  const G = '.settingstab [data-group="Idle sessions"]';
  const awake = () => page.$eval(G, g => [g.querySelector('#idleApply').disabled, g.querySelector('[data-srevert]').disabled].join());
  const atRest = await awake();
  // Each read waits for the redraw the typing starts, which a loaded machine
  // can take a moment over.
  const settle = want => page.waitForFunction(([g, w]) => { const e = document.querySelector(g);
    return e && [e.querySelector('#idleApply').disabled, e.querySelector('[data-srevert]').disabled].join() === w; }, [G, want], { timeout: 5000 }).catch(() => {});
  await page.fill('#idleMin', '4321');
  await settle('false,false');
  const changed = await awake();
  await page.fill('#idleMin', was);
  await settle('true,true');
  const back = await awake();
  ok(atRest === 'true,true' && changed === 'false,false' && back === 'true,true',
     `a section's Apply and Revert sleep until a field differs, and again when it is typed back (${atRest} | ${changed} | ${back})`);
  await page.fill('#idleMin', '4321');
  await page.click('.settingstab [data-group="Idle sessions"] [data-srevert]');
  await page.waitForFunction(w => document.getElementById('idleMin')?.value === w, was, { timeout: 10000 });
  ok(true, 'Revert on a section puts its field back to what is saved');
  // Reach from outside is the Network page's now (R165 step 4), with the
  // same builder: its setup steps are there.
  await page.evaluate(() => openNetworkTab());
  await page.waitForSelector('.networktab .snav .rrow', { timeout: 15000 });
  await splitPick(page, 'tunnel');
  ok(await page.$eval('.networktab [data-group="Reach from outside"] .setsteps', ol => ol.querySelectorAll('li').length === 4 && /localhost:\d+/.test(ol.textContent)),
     'the Reach from outside section carries its own setup steps, with the controller\'s port in them, on the Network page');
});

// The home tunnel (R176): a hostname, two secrets never shown back, and the
// controller running cloudflared itself (the harness's stub) from them, with
// the group's line reading the process. The token is nowhere in the page.
await section("The home tunnel", async () => {
  const G = '.networktab [data-group="Reach from outside"]';
  await page.evaluate(() => openNetworkTab());
  await page.waitForSelector('.networktab .snav .rrow', { timeout: 15000 });
  await splitPick(page, 'tunnel');
  const f = await page.$eval(G, g => ({ host: g.querySelector('[data-set="tunnel_host"]')?.type,
    tok: g.querySelector('[data-set="tunnel_token"]')?.type, api: g.querySelector('[data-set="cf_api_token"]')?.type,
    pills: [...g.querySelectorAll('.pill')].map(p => p.textContent), state: g.querySelector('.actbar .state').textContent }));
  ok(f.host === 'text' && f.tok === 'password' && f.api === 'password' && f.pills.filter(p => p === 'not set').length === 2
     && /off: paste a tunnel token/.test(f.state),
     `the Reach from outside group asks for the hostname and two secrets, typed blind, and says the tunnel is off (${JSON.stringify(f)})`);
  const TOKEN = Buffer.from(JSON.stringify({ a: 'a'.repeat(32), t: '12345678-1234-1234-1234-123456789abc', s: 'x' })).toString('base64');
  await page.fill(`${G} [data-set="tunnel_host"]`, 'not a host');
  await page.click(`${G} .setApply`);
  await page.waitForFunction(() => /hostname like/.test(document.getElementById('toast')?.textContent || ''), null, { timeout: 10000 }).catch(() => {});
  ok(await page.evaluate(() => /hostname like/.test(document.getElementById('toast')?.textContent || '')),
     'a hostname that is not one is refused by name');
  await page.fill(`${G} [data-set="tunnel_host"]`, 'bb.example.com');
  await page.fill(`${G} [data-set="tunnel_token"]`, TOKEN);
  await page.click(`${G} .setApply`);
  await page.waitForFunction(sel => /connected: bb\.example\.com/.test(document.querySelector(sel + ' .actbar .state')?.textContent || ''), G, { timeout: 20000 });
  const after = await page.$eval(G, g => ({ pills: [...g.querySelectorAll('.pill')].map(p => p.textContent),
    tok: g.querySelector('[data-set="tunnel_token"]').value, clear: !!g.querySelector('[data-clear="tunnel_token"]') }));
  ok(after.pills.includes('set') && after.tok === '' && after.clear
     && !(await page.evaluate(t => JSON.stringify(state.settings).includes(t), TOKEN)),
     `Apply runs the tunnel and the line reads connected; the token is set, blank in its box and nowhere in the page (${JSON.stringify(after.pills)})`);
  ok(/registered tunnel connection/i.test((await page.evaluate(() => state.settings.tunnel.tail.join('\n')))),
     '...and the process\'s last lines are what the server read');
  // Enroll node fills the hostname in for a node reaching the controller
  // through it.
  await page.evaluate(() => openNodesTab());
  await page.waitForSelector('.pane .bar #ndEnroll', { timeout: 15000 });
  await page.click('.pane .bar #ndEnroll');
  await page.waitForSelector('#ndBody #ndEnReach', { timeout: 10000 });
  await page.selectOption('#ndBody #ndEnReach', 'public');
  ok(await page.$eval('#ndBody #ndEnCtl', e => e.value) === 'https://bb.example.com',
     'Enroll node fills the controller\'s own public hostname in');
  // Asked for by its own public hostname, the controller answers the
  // agent's API and nothing else, whatever rule the tunnel carries
  // (bb.neat.fish served its login through a wide rule, 11 Oct).
  const viaHost = (path) => execFileSync('curl', ['-s', '-o', '/dev/null', '-w', '%{http_code}', '-H', 'Host: bb.example.com',
    '-u', 'test:test', URL.replace(/\/$/, '') + path]).toString();
  ok(viaHost('/api/status') === '403' && viaHost('/') === '403' && viaHost('/api/v1/agent/hello') !== '403',
     `by its own hostname the controller refuses its pages and keeps the agent's API (${viaHost('/api/status')}, ${viaHost('/')})`);
  await page.click('#ndBody #ndEnCancel');
  await page.evaluate(() => openNetworkTab());
  await page.waitForSelector('.networktab .snav .rrow', { timeout: 15000 });
  await splitPick(page, 'tunnel');
  await page.waitForSelector(`${G} [data-clear="tunnel_token"]`, { timeout: 15000 });
  await page.check(`${G} [data-clear="tunnel_token"]`);
  await page.click(`${G} .setApply`);
  await page.waitForFunction(sel => /off: paste a tunnel token/.test(document.querySelector(sel + ' .actbar .state')?.textContent || ''), G, { timeout: 20000 });
  ok(true, '...and taking the token off stops the tunnel');
  await post('/api/settings', { set: { tunnel_host: '' } });
});
// Gone on 7 Oct (the operator): a node's Claude Code is updated when Update
// is pressed, and never before a session starts.
ok(await page.$('.settingstab [data-set="claude_autoupdate"]') === null,
   'no switch updates Claude Code before a session starts');

// ---- the Debug page (R147) -------------------------------------------------
// Beside Controller settings on a controller started with DEBUG_MODE=1 (the
// harness's), for an account with the debug grant: debug mode said as on,
// Offer dev features, and every project's grants, which a project's settings
// held before. Not advertised (the operator, 26 Oct): it has no tour.
await post('/api/settings', { set: { offer_unvetted: false } });
await page.evaluate(() => openDebugTab());
await page.waitForSelector('.debugtab #dbgDev', { timeout: 15000 });
await page.waitForSelector('.debugtab [data-dbgproj] input[value="@diag"]', { timeout: 15000 });
const dbg = await page.evaluate(() => ({ head: document.querySelector('.debugtab .pghead')?.textContent.replace(/\s+/g, ' ') || '',
  group: groupOf('debug')?.key, hash: location.hash, tour: !!TOUR_STEPS.debug, dev: $('dbgDev').checked,
  settings: SETTING_GROUPS.some(g => g.key === 'debug'), projSettings: !!document.getElementById('rnDebugField') }));
ok(/Debug mode on/.test(dbg.head) && /DEBUG_MODE=1/.test(dbg.head) && dbg.group === 'controller' && dbg.hash === '#/controller/debug'
   && !dbg.tour && !dbg.dev && !dbg.settings && !dbg.projSettings,
   `the Debug page is the Controller group's beside Settings, saying debug mode is on from DEBUG_MODE, with no tour, Settings and a space's settings carrying none of it (${JSON.stringify(dbg)})`);

// ---- saving ----------------------------------------------------------------
await page.check('.debugtab #dbgDev');
await page.click('.debugtab #dbgDevSave');
await page.waitForFunction(() => state?.settings?.settings?.offer_unvetted?.value === true, null, { timeout: 30000 });
ok(read().offer_unvetted === true,
   'Save writes Offer dev features under /config and the poll carries it');
// A project's grant, ticked on its row and saved with the section's Save, is
// the project's own setting, as its settings saved it.
const alphaRow = '.debugtab [data-dbgproj] input[value="@diag"]';
const key = await page.$eval(alphaRow, i => i.closest('[data-dbgproj]').dataset.dbgproj);
const was = await page.$eval(alphaRow, i => i.checked);
await page.click(alphaRow);
await page.click('.debugtab #dbgSave');
await page.waitForFunction(([k, w]) => !!projectList().find(c => c.key === k)?.first?.prefs?.diag === !w, [key, was], { timeout: 30000 });
ok(true, `...and a space's grant ticked on its row is saved with the section's Save (${key}: diagnostics ${!was})`);
await page.click(alphaRow);
await page.click('.debugtab #dbgSave');
await page.waitForFunction(([k, w]) => !!projectList().find(c => c.key === k)?.first?.prefs?.diag === w, [key, was], { timeout: 30000 });
const bad = await post('/api/settings', { set: { offer_unvetted: 'maybe' } });
ok(bad.status === 400, 'a value that is not the setting\'s shape is refused');
ok((await post('/api/settings', { set: { claude_channel: 'stable' } })).status === 400
   && (await post('/api/settings', { set: { claude_autoupdate: true } })).status === 400,
   '...and a key that stopped being a setting is refused too');
// Back off: the rest of this file reads the settings as they started.
await post('/api/settings', { set: { offer_unvetted: false } });

// ---- what the boot script reads ------------------------------------------------
const setting = (key, dflt) => execFileSync('bash', ['-c',
  `. ${JSON.stringify(join(HERE, '..', '..', 'lib', 'common.sh'))}; bb_setting ${key} ${JSON.stringify(dflt)}`],
  { encoding: 'utf8', env: { ...process.env, DASHBOARD_STATE: `${DIR}/state` } });
ok(setting('offer_unvetted', 'true') === 'false',
   'bb_setting hands a boot hook the saved value, a false as the word false so is_true reads it');
ok(setting('nothing_saved', 'dflt') === 'dflt', '...and the default when nothing is saved; no environment variable is read any more');

// ---- the commit identity is the account's ----------------------------------
// Set on the Profile tab, never in a project: two people on one project are
// two authors. It reaches a session as git's environment, and `aerie settings
// --json` is how bb-tty asks for it, for the seat BB_ACCOUNT_UID names.
const prof = await post('/api/profile', { action: 'save',
  profile: { full_name: 'Test Person', email: 'test@example.invalid' } });
ok(prof.status === 200 && prof.body.git.name === 'Test Person' && prof.body.git.email === 'test@example.invalid',
   'an account sets its name and email on its profile, and its commits carry them unless a git identity says otherwise');
const prof2 = await post('/api/profile', { action: 'save', profile: { git_name: 'T. Person', git_email: 'tp@users.noreply.invalid' } });
ok(prof2.body.git.name === 'T. Person' && prof2.body.git.email === 'tp@users.noreply.invalid',
   '...and a git identity of its own outranks them');
// The repository's own config alone: a session's environment carries its
// identity as GIT_CONFIG_KEY_n, which git config would answer with (B146).
const repoEnv = Object.fromEntries(Object.entries(process.env).filter(([k]) => !/^GIT_CONFIG_(COUNT|KEY_|VALUE_)/.test(k)));
const gitc = k => { try { return execFileSync('git', ['-C', `${DIR}/ws/alpha`, 'config', k], { encoding: 'utf8', env: repoEnv }).trim(); } catch { return ''; } };
ok(gitc('user.name') === 'dashboard test' && gitc('user.email') === 'test@example.invalid',
   '...without writing anything into the repository\'s own config, which keeps the fixture\'s');
const owner = JSON.parse(readFileSync(`${DIR}/state/users.json`, 'utf8')).users.test.uid;
const st = JSON.parse(execFileSync('bash', [join(HERE, '..', '..', 'aerie'), 'settings', '--json'],
  { encoding: 'utf8', env: { ...process.env, BUILDERBOT_ROLE: 'controller', BB_TOKEN: '',
    DASHBOARD_STATE: `${DIR}/state`, WORKSPACE: `${DIR}/ws`, BB_PROJECT: 'alpha', BB_ACCOUNT_UID: owner } }));
ok(st.git_name === 'T. Person' && st.git_email === 'tp@users.noreply.invalid',
   '...and aerie settings --json carries it for the seat asking, which is how bb-tty puts it in a session');
const bare = JSON.parse(execFileSync('bash', [join(HERE, '..', '..', 'aerie'), 'settings', '--json'],
  { encoding: 'utf8', env: { ...process.env, BUILDERBOT_ROLE: 'controller', BB_TOKEN: '',
    DASHBOARD_STATE: `${DIR}/state`, WORKSPACE: `${DIR}/ws`, BB_PROJECT: '', BB_ACCOUNT_UID: owner }, cwd: '/' }));
ok(bare.git_name === 'T. Person', '...for a shell with no project too');
// The projects this one reads (prefs.reads) show in aerie settings, so a
// session knows its own list without the briefing.
await section("The projects this one reads", async () => {
  const envs = { ...process.env, BUILDERBOT_ROLE: 'controller', BB_TOKEN: '', DASHBOARD_STATE: `${DIR}/state`, WORKSPACE: `${DIR}/ws`, BB_PROJECT: 'alpha', BB_ACCOUNT_UID: owner };
  await page.evaluate(async () => (await (await fetch('/api/prefs', { method: 'POST', headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({ project: 'alpha', reads: ['beta'] }) })).json()));
  const text = execFileSync('bash', [join(HERE, '..', '..', 'aerie'), 'settings'], { encoding: 'utf8', env: envs });
  const asJson = JSON.parse(execFileSync('bash', [join(HERE, '..', '..', 'aerie'), 'settings', '--json'], { encoding: 'utf8', env: envs }));
  ok(/^  reads\s+beta$/m.test(text) && asJson.reads.join() === 'beta',
     `aerie settings names the spaces this one reads, as text and as JSON (${(text.match(/^  reads.*$/m) || [''])[0]})`);
  await page.evaluate(async () => (await (await fetch('/api/prefs', { method: 'POST', headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({ project: 'alpha', reads: [] }) })).json()));
});
await page.evaluate(n => renameProject(n), 'alpha');   // the settings form (the row's gear went in R119 step 3)
await page.waitForSelector('#rnmodal:not([hidden])');
// The dialog asks again (17 Sep), but for a different thing: the old field
// was the PROJECT's identity and wrote user.name into the repository, which
// made two people on it one author. This one is the asking ACCOUNT's, on this
// project, and lives in that account's record. The invariant the removal was
// protecting still holds, and is what is asserted: nothing reaches the tree.
ok(!!(await page.$('#rnGitName')) && !!(await page.$('#rnGitEmail')),
   'the space dialog asks for a commit author again, as this account\'s own');
await page.fill('#rnGitName', 'Alter Ego');
await page.fill('#rnGitEmail', 'alter@example.invalid');
await saveDialog(page);
ok(gitc('user.name') === 'dashboard test' && gitc('user.email') === 'test@example.invalid',
   '...and saving it still writes nothing into the repository, which is what the old one got wrong');
const over = JSON.parse(execFileSync('bash', [join(HERE, '..', '..', 'aerie'), 'settings', '--json'],
  { encoding: 'utf8', env: { ...process.env, BUILDERBOT_ROLE: 'controller', BB_TOKEN: '',
    DASHBOARD_STATE: `${DIR}/state`, WORKSPACE: `${DIR}/ws`, BB_PROJECT: 'alpha', BB_ACCOUNT_UID: owner } }));
ok(over.git_name === 'Alter Ego' && over.git_email === 'alter@example.invalid',
   `...and a session here is handed it instead of the Profile's (${over.git_name} <${over.git_email}>)`);
const elsewhere = JSON.parse(execFileSync('bash', [join(HERE, '..', '..', 'aerie'), 'settings', '--json'],
  { encoding: 'utf8', env: { ...process.env, BUILDERBOT_ROLE: 'controller', BB_TOKEN: '',
    DASHBOARD_STATE: `${DIR}/state`, WORKSPACE: `${DIR}/ws`, BB_PROJECT: 'beta', BB_ACCOUNT_UID: owner } }));
ok(elsewhere.git_name === 'T. Person',
   `...on that space only, with every other one still the Profile's (${elsewhere.git_name})`);

// ---- global rules (R63), in each project's notebook --------------------------
// There is no dialog for them (the operator, 2 Oct): they are listed under a
// project's own rules on the Briefing, each with a switch for THIS project,
// and an administrator adds and edits them there for every project. A rule
// typed in one project's notebook comes back out of every project's preamble.
await section("global rules", async () => {
  const auth = OWNER;
  const pre = async p => (await (await fetch(URL.replace(/\/$/, '') + `/api/preamble?project=${p}`, { headers: auth })).json()).text || '';
  const globals = async () => ((await (await fetch(URL.replace(/\/$/, '') + '/api/global-rules', { headers: auth })).json()).rules || []);
  await page.evaluate(() => openSettingsTab());
  await page.waitForSelector('.settingstab .snav [data-spick="logs"]', { timeout: 15000 });
  // Reset last, and no section that only linked to the Nodes page (R218 step 32).
  const order = await page.$$eval('.settingstab .snav [data-spick]', bs => bs.map(b => b.dataset.spick));
  ok(!order.includes('nodes') && order.at(-1) === 'reset', `Controller settings ends on Reset, with no Nodes section (${order.join(', ')})`);
  ok(!(await page.$('#setGlobalRules')) && !(await page.$('#grmodal')),
     'Controller settings has no Global rules dialog any more');

  await page.evaluate(() => openNotebook('alpha', 'briefing'));
  await page.waitForSelector('.nb #rulesBox details.sect[data-sect="briefing:rules"]', { state: 'attached', timeout: 20000 });
  await openFold(page, '.nb #rulesBox details.sect[data-sect="briefing:rules"]');
  await page.waitForSelector('.nb #grAddHere', { timeout: 15000 });
  const shipped = (await globals()).filter(r => r.builtin).map(r => r.name);
  const rows = await page.$$eval('.nb #rlGlobal .grule .btitle', es => es.map(e => e.textContent.trim()));
  ok(shipped.length >= 3 && shipped.every(n => rows.includes(n)),
     `a space's Briefing lists every global rule under its own (${rows.join(', ')})`);

  // An administrator adds one here, for every project.
  await page.click('.nb #grAddHere');
  await page.fill('.nb .grule.editing .grName', 'no-secrets');
  await page.fill('.nb .grule.editing .grText', 'Never write credentials into a repository.');
  await page.click('.nb .grule.editing .grSave');
  await page.waitForFunction(() => [...document.querySelectorAll('.nb #rlGlobal .grule .btitle')].some(e => e.textContent.trim() === 'no-secrets'),
    null, { timeout: 15000 });
  // Stored, asked of the server until it says so: the page lists the rule
  // as it is saved, and under load the list was read a moment before the
  // save had landed (three whole runs of 14 and 15 Nov).
  await until(async () => (await globals()).some(r => r.name === 'no-secrets' && !r.builtin), 15000, 200);
  ok((await globals()).some(r => r.name === 'no-secrets' && !r.builtin), 'an administrator adds a global rule from a space\'s notebook, stored once');
  ok(/Never write credentials/.test(await pre('alpha')) && /Never write credentials/.test(await pre('beta')) && /\(global\)/.test(await pre('beta')),
     '...and every space\'s sessions are handed it, marked global');

  // Switched off for this project alone, staged until the rules section's Save.
  const row = '.nb #rlGlobal .grule:has(.btitle:text-is("no-secrets"))';
  await openFold(page, row);
  await page.click(`${row} .grHere`);
  ok(/Never write credentials/.test(await pre('alpha')), '...a switch is staged, not written, until Save');
  await page.click('.nb [data-ssave="briefing:rules"]');
  // Waited on the server, not the row: the row says "off here" as soon as
  // the switch is staged.
  await page.waitForFunction(async () => ((await (await fetch('/api/rules?project=alpha')).json()).global || [])
    .some(g => g.name === 'no-secrets' && g.off_here), null, { timeout: 15000, polling: 300 });
  ok(!/Never write credentials/.test(await pre('alpha')) && /Never write credentials/.test(await pre('beta')),
     'Save turns it off for this space alone: alpha\'s sessions stop being handed it and beta\'s are not touched');

  // A shipped one off for every project, from the same place.
  const first = shipped[0];
  const srow = `.nb #rlGlobal .grule:has(.btitle:text-is("${first}"))`;
  await openFold(page, srow);
  await page.click(`${srow} .grEvery`);
  await page.waitForFunction(n => (document.querySelector(`.nb #rlGlobal`)?.textContent || '').includes('off everywhere'), first, { timeout: 15000 });
  // Drawn off on the press (the operator, 22 Nov); stored once the server
  // has it, asked until it says so.
  await until(async () => (await globals()).find(r => r.name === first)?.disabled === true, 15000, 200);
  ok((await globals()).find(r => r.name === first)?.disabled === true
     && !(await pre('beta')).includes((await globals()).find(r => r.name === first).text.slice(0, 40)),
     `an administrator turns a shipped rule off for every space from there (${first})`);
  ok(/never write a credential into a repository/.test(await pre('beta')) && /never a success you did not see/.test(await pre('beta')),
     'what nobody would turn off is in the briefing\'s core instead: no credential in a repository, a true report');
  // Put back as they were.
  await fetch(URL.replace(/\/$/, '') + '/api/global-rules', { method: 'POST', headers: { ...auth, 'Content-Type': 'application/json' },
    body: JSON.stringify({ action: 'save', rules: [], disabled: [] }) });
  await fetch(URL.replace(/\/$/, '') + '/api/rules', { method: 'POST', headers: { ...auth, 'Content-Type': 'application/json' },
    body: JSON.stringify({ project: 'alpha', action: 'save', rules: (await (await fetch(URL.replace(/\/$/, '') + '/api/rules?project=alpha', { headers: auth })).json()).rules, globals_off: [] }) });
});

// ---- a browser's own time zone (the gear, R218 step 31) -------------------
// A cookie, not the account: a phone abroad and the desk at home each keep
// their own. Every time the page shows goes through fmtTime, so picking a
// zone moves them all, and nothing picked takes the cookie away again. It
// sits in the gear beside the scheme, the other choice that is this
// browser's; the person's own zone is their Profile's (below).
await section("a browser's own time zone", async () => {
  await page.evaluate(() => toggleUiMenu(true));
  await page.waitForSelector('#uiMenu #uiTZ', { timeout: 15000 });
  const zone = 'Pacific/Chatham';          // +12:45: no browser's own zone by accident
  const asleep = await page.$eval('#uiTZApply', b => b.disabled);
  await page.selectOption('#uiTZ', zone);
  ok(asleep && !await page.$eval('#uiTZApply', b => b.disabled),
     'in the gear, picking a zone wakes its Apply, asleep until then');
  await page.click('#uiTZApply');
  const after = await page.evaluate(z => ({
    cookie: document.cookie.includes('bb_tz=' + encodeURIComponent(z)),
    tz: userTZ(),
    same: fmtTime(0, { hour: '2-digit', minute: '2-digit' })
      === new Date(0).toLocaleString([], { hour: '2-digit', minute: '2-digit', timeZone: z }),
  }), zone);
  ok(after.cookie && after.tz === zone && after.same,
     `Apply keeps the zone in a cookie on this browser, and the page's times follow it (${JSON.stringify(after)})`);
  const acct = await (await page.evaluate(() => fetch('/api/profile').then(r => r.text())));
  ok(!acct.includes(zone), '...and nothing of it is stored against the account');
  await page.waitForSelector('#uiMenu #uiTZ', { timeout: 15000 });
  await page.selectOption('#uiTZ', '');
  await page.click('#uiTZApply');
  ok(await page.evaluate(() => !document.cookie.includes('bb_tz=') && userTZ() === ''),
     'This device\'s own takes the cookie away again');
  await page.evaluate(() => { document.cookie = 'bb_tz=Not%2FAZone; path=/'; });
  ok(await page.evaluate(() => userTZ() === ''), 'a zone this browser does not know is ignored, not trusted');
  await page.evaluate(() => { setUserTZ(''); toggleUiMenu(false); });
});

// ---- a person's own time zone (R294 step 8) --------------------------------
// On their Profile, kept with their account: their quiet windows on the bell
// and the times every browser of theirs shows that picked none of its own;
// the gear then offers it first, and this device's own beside it.
await section("a person's own time zone", async () => {
  const zone = 'Pacific/Chatham';
  await page.evaluate(() => openProfileTab());
  await page.waitForSelector('.profiletab #pf_tz', { timeout: 15000 });
  const none = await page.$eval('.profiletab #pf_tz', s => ({ v: s.value, first: s.options[0]?.textContent }));
  await page.selectOption('.profiletab #pf_tz', zone);
  await page.click('.profiletab #pfSave');
  const kept = await refreshUntil(page, () => state?.tz === 'Pacific/Chatham', { timeout: 15000 }).then(() => true, () => false);
  const shown = await page.evaluate(z => ({ tz: userTZ(), cookie: document.cookie.includes('bb_tz='),
    same: fmtTime(0, { hour: '2-digit', minute: '2-digit' }) === new Date(0).toLocaleString([], { hour: '2-digit', minute: '2-digit', timeZone: z }) }), zone);
  ok(none.v === '' && /controller's clock/.test(none.first || '') && kept && shown.tz === zone && !shown.cookie && shown.same,
     `Profile's time zone is the person's own, kept with the account, and a browser that picked none shows times in it (${JSON.stringify({ none, kept, shown })})`);
  await page.evaluate(() => toggleUiMenu(true));
  await page.waitForSelector('#uiMenu #uiTZ', { timeout: 15000 });
  const offered = await page.$$eval('#uiMenu #uiTZ option', os => os.slice(0, 2).map(o => [o.value, o.textContent]));
  await page.selectOption('#uiTZ', 'device');
  await page.click('#uiTZApply');
  const device = await page.evaluate(() => ({ tz: userTZ(), b: browserTZ() }));
  ok(offered[0][0] === '' && /Your own, from your Profile \(Pacific\/Chatham\)/.test(offered[0][1]) && offered[1][0] === 'device'
     && device.tz === '' && device.b === 'device',
     `the gear offers the person's own first and this device's own beside it, which this browser may keep instead (${JSON.stringify({ offered, device })})`);
  const bad = await page.evaluate(() => postJSON('/api/users', { action: 'prefs', prefs: { tz: 'Mars/Base' } }));
  ok(/not a time zone/.test(bad.error || ''), `a zone the controller does not know is refused in words (${bad.error})`);
  await page.evaluate(async () => { setUserTZ(''); toggleUiMenu(false); await postJSON('/api/users', { action: 'prefs', prefs: { tz: '' } }); await refresh(); });
});

// ---- a project's settings live in its notebook (R119 step 3) ---------------
// The row's gear went, and the form is the notebook's Settings view: the
// same form, moved there while the view is on screen, each section saving
// itself, and back to the dialog when another view is picked.
await section("a project's settings live in its notebook", async () => {
  await page.evaluate(() => { document.querySelectorAll('.modal:not(.inline)').forEach(m => { m.hidden = true; }); });
  // The sidebar's row carries no gear; the Projects page's card offers
  // Settings in its menu by design (R218 step 3), not as a button on its
  // face, and on its back among the named icons (R138, the operator).
  ok(!(await page.$('#projects [data-rn]')) && !(await page.$('.doc .projtab .pcacts:not(.pcfoot) > [data-rn]')),
     'no space row carries a settings button any more');
  await page.evaluate(() => openProjectSettings('alpha'));
  await page.waitForSelector('.nb .nbview[data-view="settings"]:not([hidden]) .nbsettings #rnName', { timeout: 15000 });
  const inView = await page.evaluate(() => ({ name: $('rnName').value, modal: $('rnmodal').hidden,
    close: $('rnCancel').hidden, shown: $('rnName').checkVisibility(),
    bars: [...document.querySelectorAll('.nbsettings .rnbar')].filter(b => b.checkVisibility()).length }));
  ok(inView.name === 'alpha' && inView.modal && inView.close && inView.shown && inView.bars === 1,
     `the notebook's Settings view holds the form, the dialog shut, the section on show with its own Save and Revert (${JSON.stringify(inView)})`);
  // The notebook taken down while it holds the form (B211, the operator,
  // 22 Oct: Settings empty after leaving the project and coming back): the
  // form is handed back first, so the next Settings view has it.
  await page.evaluate(() => getNotebook('alpha').destroy());
  const back = await page.evaluate(() => !!document.querySelector('#rnmodal > .box') && rnHost === null);
  await page.evaluate(() => openProjectSettings('alpha'));
  await page.waitForSelector('.nb .nbview[data-view="settings"]:not([hidden]) .nbsettings #rnName', { timeout: 15000 }).catch(() => {});
  const again = await page.evaluate(() => ({ name: $('rnName').value, shown: $('rnName').checkVisibility() }));
  ok(back && again.name === 'alpha' && again.shown,
     `a notebook taken down hands the form back, and Settings opened again holds it (${back} ${JSON.stringify(again)})`);
  // The sections a list beside the one picked (the operator, 16 Oct: too
  // many open at once to find a setting in): each row names what is in it,
  // a press shows that section alone, and People is on the list.
  // People joins the list when its read lands.
  await page.waitForSelector('.nbsettings .snav [data-spick="people"]', { timeout: 15000 }).catch(() => {});
  const list = await page.evaluate(() => [...document.querySelectorAll('.nbsettings .snav [data-spick]')]
    .map(b => ({ k: b.dataset.spick, on: b.classList.contains('on'), said: b.querySelector('.rtags .dim')?.textContent || '' })));
  ok(list.length >= 8 && list[0].k === 'project' && list[0].on && list.every(r => r.said) && list.some(r => r.k === 'people'),
     `...its sections a list beside the one picked, each saying what is in it, General first, People among them (${list.map(r => r.k).join(', ')})`);
  // Every section listed opens on something: Repository was listed and
  // opened on an empty pane (B813), then on one line and a door to a dialog
  // (the operator, 23 Nov); its credentials are drawn there now.
  {
    const blank = [];
    for (const { k } of list){
      await page.click(`.nbsettings .snav [data-spick="${k}"]`);
      const h = await page.evaluate(k => document.querySelector(`.nbsettings details.rngroup[data-sect="rn:${k}"]`)?.getBoundingClientRect().height || 0, k);
      if (h < 40) blank.push(`${k} ${Math.round(h)}px`);
    }
    await rnSect(page, 'repo');
    await page.waitForSelector('.nbsettings #rnAuthField:not([hidden])', { timeout: 10000 }).catch(() => {});
    const repo = await page.evaluate(() => ({ say: $('rnRepoSay').textContent, go: $('rnRepoGo').checkVisibility(),
      fields: ['rnAuthField', 'rnTestField', 'rnAddrField', 'rnUnlink'].filter(id => $(id).checkVisibility()).join(),
      bar: [...document.querySelectorAll('.nbsettings details[data-sect="rn:repo"] .rnbar')].some(b => b.checkVisibility()) }));
    ok(!blank.length && /Linked to GitHub/.test(repo.say) && !repo.go && repo.fields === 'rnAuthField,rnTestField,rnAddrField,rnUnlink' && repo.bar,
       `...every section listed opens on something, Repository saying what its remote is over its credentials, its Save and Unlink (${blank.join(', ') || 'none blank'}; ${JSON.stringify(repo)})`);
  }
  await rnSect(page, 'yours');
  const one = await page.evaluate(() => [...document.querySelectorAll('.nbsettings details.rngroup')]
    .filter(d => d.checkVisibility()).map(d => d.dataset.sect));
  ok(one.join() === 'rn:yours', `...a row pressed shows its section alone (${one.join()})`);
  ok(!(await page.$eval('.nbsettings .sectjump', e => e.checkVisibility()).catch(() => false)),
     '...with no jump bar over it: the list is how a section is found');
  // People stays when the view is asked for again (B: the form was put back
  // and People hidden until its read landed, on every ask).
  await page.evaluate(() => openProjectSettings('alpha'));
  // What the view reads again in place (People among it) answered.
  await settled(page);
  const still = await page.evaluate(() => ({ people: !document.querySelector('details[data-sect="rn:people"]').hidden,
    pick: document.querySelector('.nbsettings .snav .rrow.on')?.dataset.spick }));
  ok(still.people && still.pick === 'yours', `...and asked for again it keeps People and the section picked (${JSON.stringify(still)})`);
  // The picked row is a lift with the lit color as a bar at its left edge,
  // never a wash of the lit color (the operator, 24 Nov: copper over navy
  // read brown on the default scheme).
  const picked = await page.evaluate(() => {
    const r = document.querySelector('.nbsettings .snav .rrow.on');
    if (!r || !r.checkVisibility()) return null;
    const cs = getComputedStyle(r);
    const probe = document.createElement('i'); probe.style.color = 'var(--lit)'; r.appendChild(probe);
    const lit = getComputedStyle(probe).color; probe.remove();
    return { bar: cs.boxShadow, lit, bg: cs.backgroundColor };
  });
  if (picked){
    const rgb = s => (s.match(/[\d.]+/g) || []).slice(0, 3).map(Number).join(',');
    ok(/inset/.test(picked.bar) && /3px 0px 0px/.test(picked.bar) && picked.bar.includes(rgb(picked.lit).split(',')[0]) && !picked.bg.includes(rgb(picked.lit)),
       `...the picked row lifted with the lit color as a bar at its left, not washed in it (${JSON.stringify(picked)})`);
  } else skip('...the picked row lifted with the lit color as a bar at its left', 'the list is folded away at this width');
  // The box borrowed from the dialog brings no dialog shadow into the view
  // (B702): the scroll-hint class it wore in the dialog is dropped on the way
  // in, and an inline box gets no shadow from that class however it arrives.
  const shade = await page.evaluate(() => {
    const dlg = document.querySelector('#rnmodal > .box') || document.querySelector('.nbsettings > .box');
    dlg.classList.add('scrolldown');
    settingsOut(); settingsInto('alpha', document.querySelector('.nbview[data-view="settings"] .nbsettings'));
    const b = document.querySelector('.nbsettings > .box');
    const moved = { cls: b.className, shadow: getComputedStyle(b).boxShadow };
    b.classList.add('scrolldown');
    return { moved, forced: getComputedStyle(b).boxShadow };
  });
  ok(!/scroll(up|down)/.test(shade.moved.cls) && shade.moved.shadow === 'none' && shade.forced === 'none',
     `...and wears no dialog shadow, with or without the dialog's scroll-hint class (${JSON.stringify(shade)})`);
  // A section's Save writes that section alone, and what is typed in another
  // stays typed (the operator, 10 Oct: one Save for eleven sections).
  await rnSect(page, 'build');
  await page.fill('#rnBuildCmd', 'make one');
  await rnSect(page, 'yours');
  const nameWas = await page.evaluate(() => $('rnGitName').value);
  await page.fill('#rnGitName', 'Typed Not Saved');
  const marks = await page.evaluate(() => [...document.querySelectorAll('.nbsettings .snav [data-spick]')]
    .filter(b => !b.querySelector('.sunsaved').hidden).map(b => b.dataset.spick).sort().join());
  ok(marks === 'build,yours', `...each section holding a change says unsaved on its row (${marks})`);
  const err = await sectSave(page, 'build');
  await refreshUntil(page, () => (state?.projects || []).find(p => p.name === 'alpha')?.prefs?.build === 'make one', { timeout: 20000 });
  const after = await page.evaluate(() => ({
    typed: $('rnGitName').value, yours: !document.querySelector('.rnbar[data-rnbar="yours"] [data-rnsave]').disabled,
    build: document.querySelector('.rnbar[data-rnbar="build"] [data-rnsave]').disabled }));
  ok(!err && after.typed === 'Typed Not Saved' && after.yours && after.build,
     `...Build and test's Save stores the build command and nothing of Yours on this space, whose change stays typed and unsaved (${JSON.stringify(after)})`);
  await rnSect(page, 'yours');
  await page.click('.rnbar[data-rnbar="yours"] [data-rnrevert]');
  // Revert asks first, in the page's question modal (R121), answered a beat
  // after the press.
  await page.waitForFunction(was => $('rnGitName').value === was, nameWas, { timeout: 5000 }).catch(() => {});
  ok(await page.evaluate(was => $('rnGitName').value === was
       && document.querySelector('.rnbar[data-rnbar="yours"] [data-rnrevert]').disabled
       && $('rnBuildCmd').value === 'make one', nameWas),
     '...and its Revert puts Yours on this space back alone');
  // A section's Save is its own fields alone, and refuses one somebody else
  // saved since these settings were opened (the operator, 17 Oct: a save in
  // one section put back another section's change, and a session's change
  // not yet on screen was written over without a word).
  {
    await post('/api/prefs', { project: 'alpha', build: '' });
    await refreshUntil(page, () => !(state?.projects || []).find(p => p.name === 'alpha')?.prefs?.build, { timeout: 20000 });
    await page.evaluate(() => { settingsOut(); openProjectSettings('alpha'); });
    await page.waitForSelector('.nbsettings .snav [data-spick="build"]', { timeout: 15000 });
    // A status read already out, answered before the save below and landing
    // only after Save is pressed, as a loaded box has them (B100): the Save
    // read "what is saved now" from it, and wrote over the other save
    // unseen. Held here, so the order is the one the gate met by chance.
    let release, read = false, caught = false;
    const held = new Promise(r => { release = r; });
    await page.route('**/api/status', async r => {
      if (caught) return r.fallback();
      caught = true;
      const before = await r.fetch();
      read = true;
      await held;
      await r.fulfill({ response: before });
    });
    await page.evaluate(() => { refresh(); });
    await until(() => read, 30000, 100);
    // Elsewhere, after this window opened: a release setting (another
    // section) and the build command (this one), as a session or another
    // window would.
    await post('/api/prefs', { project: 'alpha', release_gate: 'warn', build: 'make theirs' });
    await rnSect(page, 'build');
    await page.fill('#rnBuildCmd', 'make mine');
    // The delay is the case: the read out since before the other save lands after Save is pressed.
    setTimeout(release, 1500);
    const first = await sectSave(page, 'build');
    await page.unroute('**/api/status');
    ok(read, 'a status read sent before the other save was out when Save was pressed');
    const kept = await page.evaluate(() => (state?.projects || []).find(p => p.name === 'alpha')?.prefs?.build);
    ok(/Build changed since these settings were opened/.test(first) && kept === 'make theirs',
       `a field saved elsewhere since the settings opened is not written over unseen: the save is refused, naming it (${first.slice(0, 90)}; saved: ${kept})`);
    const second = await sectSave(page, 'build');
    await refreshUntil(page, () => (state?.projects || []).find(p => p.name === 'alpha')?.prefs?.build === 'make mine', { timeout: 20000 });
    const now = await page.evaluate(() => (state?.projects || []).find(p => p.name === 'alpha')?.prefs || {});
    ok(!second && now.build === 'make mine' && now.release_gate === 'warn',
       `...Save again writes this one's, and leaves what another section saved alone (${JSON.stringify({ build: now.build, release_gate: now.release_gate })})`);
    await post('/api/prefs', { project: 'alpha', build: '', release_gate: 'refuse' });
  }
  // Also works on is drawn from what is saved until a draw has had nodes to
  // draw: one made before the node list arrived marked itself drawn, and the
  // real one read its own empty boxes (B796, seen on dev, 16 Oct).
  {
    const ns = await page.evaluate(async () => (await (await fetch('/api/v1/nodes')).json()).nodes);
    const first = ns.find(n => n.kind !== 'local');
    const other = (await post('/api/v1/nodes', { action: 'enroll', name: 'also-works' })).body;
    await post('/api/prefs', { project: 'alpha', node: first.id, nodes: [first.id, other.id] });
    await refreshUntil(page, () => (state?.projects || []).find(p => p.name === 'alpha')?.prefs?.nodes?.length === 2, { timeout: 20000 });
    // Opened before the node list is known, as a first open is: the picker
    // draws, reads the nodes, and draws again.
    await page.evaluate(() => { getNotebook('alpha')?.view('roadmap'); nodesList = null; openProjectSettings('alpha'); });
    await page.waitForFunction(() => nodesList !== null, null, { timeout: 15000 });
    // The second draw, the one that had nodes to draw, and what it asked for answered.
    await page.waitForFunction(id => $('rnNodesMore').dataset.drawn && document.querySelector(`#rnNodesMore .rnmore[data-id="${id}"]`),
      other.id, { timeout: 15000 }).catch(() => {});
    await settled(page);
    const also = await page.evaluate(id => ({ listed: !!document.querySelector(`#rnNodesMore .rnmore[data-id="${id}"]`),
      unsaved: !document.querySelector('.snav [data-spick="runs"] .sunsaved')?.hidden }), other.id);
    ok(also.listed && !also.unsaved,
       `a space's second node is listed under Also works on when its settings open before the node list is read, and Nodes holds nothing unsaved (${JSON.stringify(also)})`);
    await post('/api/prefs', { project: 'alpha', node: first.id, nodes: [first.id] });
    await post('/api/v1/nodes', { action: 'retire', id: other.id });
  }
  await page.evaluate(() => getNotebook('alpha').view('roadmap'));
  ok(await page.evaluate(() => !!document.querySelector('#rnmodal > .box') && $('rnmodal').hidden),
     '...and picking another view puts the form back where the dialog keeps it');
});

// ---- a project's daily snapshots (R165) ------------------------------------------
// In the project's settings: how many days are kept, and a Snapshots fold
// listing each day with Restore; a restore of one file puts it back, and the
// line it leaves names the snapshot taken first, which undoes it.
await section("a project's daily snapshots", async () => {
  await page.evaluate(() => { document.querySelectorAll('.modal:not(.inline)').forEach(m => { m.hidden = true; }); openProjectSettings('alpha'); });
  await page.waitForSelector('#rnSnapDays', { state: 'attached', timeout: 15000 });
  ok(await page.$eval('#rnSnapDays', i => i.value) === '14', 'a space keeps 14 days of snapshots unless set otherwise');
  // Each number beside its unit, not over it (B51: "days" on a line under
  // its box), at a desk and on a phone.
  {
    await rnSect(page, 'rn:build');
    await openFold(page, 'details.sect[data-sect="rn:build"]');
    const was = page.viewportSize(), apart = [];
    for (const width of [1280, 393]){
      await page.setViewportSize({ width, height: 900 });
      // Laid out at the new width: the breakpoint's listeners run before a frame's callbacks, and what they slide has landed.
      await page.waitForFunction(w => innerWidth === w, width, { timeout: 10000 });
      await page.evaluate(() => new Promise(r => requestAnimationFrame(() => requestAnimationFrame(r))));
      await page.waitForFunction(() => !document.getAnimations().some(a => a.playState === 'running'
        && Number.isFinite(a.effect?.getComputedTiming().endTime)), null, { timeout: 10000 }).catch(() => {});
      // Each count's label over it, naming what it counts (the forms rule,
      // R273: the unit was a word beside the box, the label beside it too).
      apart.push(...(await page.$$eval('#rnCaptureDays, #rnSnapDays, #rnDevKeep', is => is.map(i => {
        const a = i.getBoundingClientRect(), l = document.querySelector(`label[for="${i.id}"]`), b = l?.getBoundingClientRect();
        return b && b.bottom <= a.top + 2 && Math.abs(b.left - a.left) <= 2 && /days|builds/i.test(l.textContent) ? ''
          : `${i.id} ${[a.left, a.top, b?.left, b?.bottom].map(Math.round).join('/')} "${l?.textContent.trim()}" in ${i.closest('.modal, .nb')?.className.split(' ')[0]} ${i.checkVisibility()}`;
      }).filter(Boolean))).map(x => `${width} ${x}`));
    }
    await page.setViewportSize(was);
    ok(apart.length === 0, `Build and test's counts each have their label over them, naming the unit (${apart.join(', ') || 'all over'})`);
  }
  writeFileSync(`${DIR}/ws/alpha/snapped.txt`, 'as it was\n');
  const took = await post('/api/snapshots', { project: 'alpha', action: 'take' });
  ok(took.status === 200 && took.body.files > 0, `Take one now snapshots the tree (${took.body.files} files)`);
  await page.evaluate(() => { openProjectSettings('alpha'); });
  await openFold(page, 'details.sect[data-sect="rn:snapshots"]');
  await page.waitForSelector('#rnSnapRows .snaprec', { timeout: 15000 });
  // The days are a record list (Perch): a row read-only in its columns, a
  // Take one now in the section's own bar over it, and its Restore opening
  // the row in place.
  const shape = await page.$eval('#rnSnapRows', b => ({ take: !!b.querySelector(':scope > .addbar [data-snaptake]'),
    heads: [...b.querySelectorAll('.tbl.snaprecords .thead .th')].map(h => h.textContent.trim()).filter(Boolean),
    shut: !b.querySelector('.snaprec [data-snapfile]') }));
  ok(shape.take && shape.heads.join(',') === 'Taken,Files,Size,Kept' && shape.shut,
     `the days are a record list with Take one now over it, each row shut until its Restore opens it (${JSON.stringify(shape)})`);
  await page.click('#rnSnapRows .snaprec [data-snapopen]');
  await page.waitForSelector('#rnSnapRows .snaprec.open [data-snapfile]', { timeout: 10000 });
  writeFileSync(`${DIR}/ws/alpha/snapped.txt`, 'tampered\n');
  page.dialogs.length = 0;
  await page.fill('#rnSnapRows .snaprec.open [data-snapfile]', 'snapped.txt');
  await page.click('#rnSnapRows .snaprec.open [data-snapone]');
  await page.waitForFunction(() => /restored: 1 written/.test(document.querySelector('#notify, .notify, .toast')?.textContent || '')
                             || document.querySelectorAll('#rnSnapRows .snaprec').length >= 2, null, { timeout: 15000 });
  ok(readFileSync(`${DIR}/ws/alpha/snapped.txt`, 'utf8') === 'as it was\n' && page.dialogs.length === 1
     && /Put snapped.txt back/.test(page.dialogs[0]),
     'Restore file asks, then puts the file back as it was that day');
  const kept = (await page.evaluate(async () => (await (await fetch('/api/snapshots?project=alpha')).json()).days));
  ok(kept.some(d => /before-restore/.test(d.day)), '...having snapshotted the tree first, so the restore can be undone');
  // A day pinned from its row is kept and says so; Unpin lets it go again
  // (R105, the operator, 22 Oct).
  {
    await page.evaluate(() => { openProjectSettings('alpha'); });
    await openFold(page, 'details.sect[data-sect="rn:snapshots"]');
    await page.waitForSelector('#rnSnapRows .snaprec', { timeout: 15000 });
    const day = await page.$eval('#rnSnapRows .snaprec:not([data-day*="before"])', r => r.dataset.day);
    if (!await page.$(`#rnSnapRows .snaprec.open[data-day="${day}"]`)) await page.click(`#rnSnapRows .snaprec[data-day="${day}"] [data-snapopen]`);
    await page.waitForSelector(`#rnSnapRows .snaprec[data-day="${day}"] [data-snappin="pin"]`, { timeout: 15000 });
    // The row says pinned on the press (the operator, 22 Nov), and the
    // server's list is read once it has answered.
    const pinned = page.waitForResponse(r => r.url().endsWith('/api/snapshots') && /"pin"/.test(r.request().postData() || ''), { timeout: 15000 });
    await page.click(`#rnSnapRows .snaprec[data-day="${day}"] [data-snappin]`);
    const atOnce = await page.$eval(`#rnSnapRows .snaprec[data-day="${day}"]`, r => /pinned/.test(r.textContent) && !!r.querySelector('[data-snappin="unpin"]'));
    await pinned;
    await page.waitForSelector(`#rnSnapRows .snaprec[data-day="${day}"] [data-snappin="unpin"]`, { timeout: 15000 });
    const marked = await page.$eval(`#rnSnapRows .snaprec[data-day="${day}"]`, r => /pinned/.test(r.textContent));
    const listed = (await page.evaluate(async () => (await (await fetch('/api/snapshots?project=alpha')).json())));
    const hint = await page.$eval('#rnSnapHint', h => h.textContent);
    const unpinned = page.waitForResponse(r => r.url().endsWith('/api/snapshots') && /"unpin"/.test(r.request().postData() || ''), { timeout: 15000 });
    await page.click(`#rnSnapRows .snaprec[data-day="${day}"] [data-snappin]`);
    await page.waitForSelector(`#rnSnapRows .snaprec[data-day="${day}"] [data-snappin="pin"]`, { timeout: 15000 });
    await unpinned;
    ok(atOnce && marked && listed.days.find(d => d.day === day)?.pinned === true && /1 pinned/.test(hint),
       `Pin keeps a day and its row says pinned on the press, Unpin lets it go again (${day} ${hint})`);
  }
  // The daily snapshot switch is gone (0 days kept takes none), and the API
  // does not take the key back: nothing is stored for it and nothing reads it.
  {
    await rnSect(page, 'rn:build');
    await openFold(page, 'details.sect[data-sect="rn:build"]');
    const drawn = await page.$('#rnSnapOn');
    const r = await post('/api/prefs', { project: 'alpha', snapshots_on: false, term_scheme: 'red' });
    const got = await page.evaluate(async () => {
      const snaps = await (await fetch('/api/snapshots?project=alpha')).json();
      const row = ((await (await fetch('/api/status')).json()).projects || []).find(p => p.name === 'alpha') || {};
      return { on: 'on' in snaps, pref: 'snapshots_on' in (row.prefs || {}), yours: 'term_scheme' in (row.yours || {}) };
    });
    ok(!drawn && r.status < 500 && !got.on && !got.pref && !got.yours,
       `the daily snapshot switch and a space's terminal colors are not drawn, stored or served (${!!drawn} ${r.status} ${JSON.stringify(got)})`);
  }
  // From outside the page, which carries no sign-in: nothing is listed.
  const anon = (await fetch(URL.replace(/\/$/, '') + '/api/snapshots?project=alpha')).status;
  ok(anon === 401 || anon === 403, `...and nothing is listed to a caller who is not signed in (${anon})`);
  rmSync(`${DIR}/ws/alpha/snapped.txt`, { force: true });
});

// ---- where the controller keeps what grows (paths.py, the operator, 10 Oct) ----
// Each kind on its own line of the Storage section with the path in use;
// Apply moves what is there to the new path and switches once it is all
// there; a path in the projects or one with something in it is refused in
// words; and the default comes back with what was moved.
await section("where the controller keeps what grows", async () => {
  await page.evaluate(() => { document.querySelectorAll('.modal:not(.inline)').forEach(m => { m.hidden = true; }); openSettingsTab(); });
  await page.waitForSelector('.settingstab .snav [data-spick="paths"]', { timeout: 15000 }); await splitPick(page, 'paths');
  await page.waitForSelector('.settingstab [data-group="Storage"] input[data-path="gitview"]', { timeout: 15000 });
  const names = await page.$$eval('.settingstab input[data-path]', l => l.map(i => i.dataset.path));
  ok(['project-snapshots', 'job-snapshots', 'gitrelay', 'gitview', 'logs'].every(n => names.includes(n)),
     `the Storage section lists each kind that grows (${names.join(', ')})`);
  const before = await page.$eval('.settingstab input[data-path="gitview"]', i => i.value);
  ok(before === `${DIR}/state/gitview`, `...each at its default in the state directory (${before})`);
  const inWs = await post('/api/paths', { name: 'gitview', path: `${DIR}/ws/alpha/gv` });
  ok(inWs.status === 400 && /inside the spaces/.test(inWs.body.error || ''),
     `a path in the spaces is refused: nodes' writes land there (${inWs.body.error})`);
  mkdirSync(`${DIR}/full`, { recursive: true });
  writeFileSync(`${DIR}/full/x`, 'x');
  const full = await post('/api/paths', { name: 'gitview', path: `${DIR}/full` });
  ok(full.status === 400 && /not empty/.test(full.body.error || ''), `...and so is one with something in it (${full.body.error})`);
  mkdirSync(`${DIR}/state/gitview/marker`, { recursive: true });
  writeFileSync(`${DIR}/state/gitview/marker/f`, 'kept');
  const to = `${DIR}/elsewhere/gitview`;
  await page.fill('.settingstab input[data-path="gitview"]', to);
  await page.click('#pathsApply');
  await page.waitForFunction(t => (state?.paths?.paths || []).find(p => p.name === 'gitview' && p.path === t && !p.moving),
                             to, { timeout: 20000 });
  ok(existsSync(`${to}/marker/f`) && !existsSync(`${DIR}/state/gitview/marker`),
     'Apply moves what is there to the new path and switches to it once it has all arrived');
  await page.waitForFunction(() => /default: /.test(document.querySelector('.settingstab [data-group="Storage"]')?.textContent || ''),
                             null, { timeout: 10000 });
  ok(true, '...and the line says what the default was');
  const back = await post('/api/paths', { name: 'gitview', path: '' });
  await page.waitForFunction(d => (state?.paths?.paths || []).find(p => p.name === 'gitview' && p.path === d && !p.moving),
                             `${DIR}/state/gitview`, { timeout: 20000 });
  ok(back.status === 200 && existsSync(`${DIR}/state/gitview/marker/f`),
     '...and an empty path puts it back at its default, with what is there');
});

// ---- Profile's What you may do on a phone (B76) -------------------------------
// One column of facts, every value starting at one line: each began where
// its own label ended, two ragged columns.
await section("Profile's What you may do on a phone", async () => {
  const phone = await newPage(browser, { viewport: { width: 360, height: 780 }, isMobile: true, hasTouch: true });
  await phone.goto(URL);
  await ready(phone);
  await phone.evaluate(() => openProfileTab());
  await phone.waitForSelector('.profiletab [data-spick="may"]', { timeout: 15000 });
  await phone.click('.profiletab [data-spick="may"]');
  await phone.waitForSelector('.profiletab dl.facts:not(.pghfacts) dd', { timeout: 10000 });
  // ...and one of them laid out: there in the page while its section was
  // still opening, none had a height yet and nothing was measured.
  await phone.waitForFunction(() => [...document.querySelectorAll('.profiletab dl.facts:not(.pghfacts) .fact dd')].some(d => d.offsetHeight)
    && !document.querySelector('.profiletab')?.getAnimations({ subtree: true }).some(a => a.playState === 'running' && Number.isFinite(a.effect?.getComputedTiming().endTime)),
    null, { timeout: 10000 }).catch(() => {});
  const xs = await phone.$$eval('.profiletab dl.facts:not(.pghfacts) .fact dd', ds => [...new Set(ds.filter(d => d.offsetHeight)
    .map(d => Math.round(d.getBoundingClientRect().left)))]);
  const over = await phone.evaluate(() => document.documentElement.scrollWidth - innerWidth);
  if (process.env.BB_SHOT_DIR) await phone.screenshot({ path: `${process.env.BB_SHOT_DIR}/profile-may-360.png` });
  ok(xs.length === 1 && over <= 0, `on a phone What you may do lines its values up in one column (starts at ${xs.join('/')})`);
  await phone.close();
});

// ---- a split page's head on a phone (B370) ----------------------------------
// The page's head is on top, as at a desk, not under the list of sections.
await section("a split page's head on a phone", async () => {
  const phone = await newPage(browser, { viewport: { width: 393, height: 852 }, isMobile: true, hasTouch: true });
  await phone.goto(URL);
  await ready(phone);
  const seen = [];
  for (const [open, name] of [['openSettingsTab', 'Controller settings'], ['openProfileTab', 'Profile']]){
    await phone.evaluate(f => window[f](), open);
    await phone.waitForSelector('.pane .doc.on .ssplit > .pghead', { timeout: 15000 });
    // ...laid out, the page before it gone: in the page while it was still
    // coming in, its head had no height and was measured as 0 against 0.
    await phone.waitForFunction(() => {
      const h = document.querySelector('.pane .doc.on .ssplit > .pghead');
      return !!h && h.getBoundingClientRect().height > 0 && !document.querySelector('.pane .doc.leaving');
    }, null, { timeout: 15000 }).catch(() => {});
    seen.push(await phone.$eval('.pane .doc.on .ssplit', s => {
      const h = s.querySelector(':scope > .pghead').getBoundingClientRect(), n = s.querySelector(':scope > .snav').getBoundingClientRect();
      return h.height > 0 && h.bottom <= n.top + 1 ? '' : `${Math.round(h.top)} vs ${Math.round(n.top)}`;
    }).then(x => x && `${name} ${x}`));
  }
  ok(seen.every(x => !x), `on a phone a settings page's head is above its sections (${seen.filter(Boolean).join(', ') || 'both'})`);
  // The chain opens a space's Settings at Repository on a phone too, not on
  // the list of sections, whether the view was elsewhere or already there.
  const at = [];
  for (const how of ['elsewhere', 'already there']){
    if (how === 'elsewhere') await phone.evaluate(() => openProjectsTab());
    await phone.evaluate(() => openProjectSettings('alpha', 'repo'));
    await phone.waitForFunction(() => document.querySelector('.nbsettings details[data-sect="rn:repo"]')?.checkVisibility(), null, { timeout: 15000 }).catch(() => {});
    at.push(await phone.evaluate(how => {
      const repo = document.querySelector('.nbsettings details[data-sect="rn:repo"]'), list = document.querySelector('.nbsettings .snav');
      return repo?.checkVisibility() && !list?.checkVisibility() ? '' : `${how}: ${repo?.checkVisibility() ? 'list shown too' : 'on the list'}`;
    }, how));
    if (how === 'elsewhere') await phone.evaluate(() => { SPLIT['rn:alpha'] = { pick: 'yours', open: true }; rnSplit(rnHost.querySelector(':scope > .box'), 'alpha'); });
  }
  ok(at.every(x => !x), `on a phone the chain opens Repository, not the list (${at.filter(Boolean).join(', ') || 'both ways'})`);
  await phone.close();
});

// ---- Connected services (R294 step 9) --------------------------------------
// Every credential the install holds for an outside service, on Controller
// settings, with who added it; Open goes where it lives, and Forget, an
// administrator's, takes it away at once.
await section("Connected services", async () => {
  const set = await post('/api/settings', { set: { smtp_password: 'hunter2-not-real' } });
  await page.evaluate(() => { connData = null; connAsked = false; openSettingsTab(); });
  await page.waitForSelector('.settingstab .snav [data-spick="connections"]', { timeout: 15000 });
  await page.click('.settingstab .snav [data-spick="connections"]');
  const R = 'details[data-sect="settings:connections"] .conntbl .row';
  await page.waitForFunction(sel => [...document.querySelectorAll(sel)].some(r => /Mail server password/.test(r.textContent)), R, { timeout: 15000 });
  const row = await page.$$eval(R, rs => rs.map(r => ({ text: r.textContent.replace(/\s+/g, ' '), forget: !!r.querySelector('[data-connforget]'), open: !!r.querySelector('[data-conngo]') }))
    .find(r => /Mail server password/.test(r.text)));
  const hidden = !/hunter2/.test(await page.$eval('details[data-sect="settings:connections"]', e => e.innerHTML));
  ok(!set.error && row && /this install's/.test(row.text) && /by /.test(row.text) && row.open && row.forget && hidden,
     `a mail password set is listed as this install's, with who added it, Open and Forget, and never its value (${JSON.stringify(row)})`);
  page.dialogs.length = 0;
  await page.$$eval(R, rs => rs.find(r => /Mail server password/.test(r.textContent))?.querySelector('[data-connforget]')?.click());
  const gone = await until(async () => !(await page.evaluate(async () => (await (await fetch('/api/connections')).json()).rows || []))
    .some(r => r.kind === 'setting' && r.ref === 'smtp_password'), 10000, 200);
  const cleared = await page.evaluate(async () => !(await (await fetch('/api/status')).json()).settings?.smtp_password?.set);
  ok(page.dialogs.some(d => /Forget Mail server password\?/.test(d)) && gone && cleared,
     `Forget asks, then takes it away where it was kept (${JSON.stringify({ asked: page.dialogs.slice(-1), gone, cleared })})`);
});

await done(browser);
