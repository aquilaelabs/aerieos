// The Installed page (R172): under Machines beside Nodes and Storage, one
// node picked, what the Library put there by kind, each row opening on
// what the catalog's card does not show: an agent's sign-in, a toolchain's
// path and system packages, a service's Configure from its config block
// (the model router's providers, endpoints, Ollama and projects, saved to
// the router's own record), and Remove.
import { launch, newPage, ok, done, ready, URL, section, until, libraryShow } from './lib.mjs';

const browser = await launch();
const page = await newPage(browser, { viewport: { width: 1280, height: 900 } });
await page.goto(URL);
await ready(page);

// ---- on the rail -------------------------------------------------------
ok(await page.evaluate(() => railGroups().some(g => g.key === 'machines' && g.tools.some(([k]) => k === 'installed')) && railAllows('installed')),
   'Installed is a page under Machines, beside Nodes and Storage');

// ---- the page ----------------------------------------------------------
await page.evaluate(() => openInstalledTab());
await page.waitForSelector('.pane .bar #ndPick', { timeout: 20000 });
await page.waitForFunction(() => inst && !inst.nonode && Array.isArray(inst.rows), null, { timeout: 20000 });
ok(await page.waitForFunction(() => location.hash === '#/machines/installed/' + encodeURIComponent(instNode), null, { timeout: 10000 }).then(() => true, () => false),
   `the address names the page and its node (${await page.evaluate(() => location.hash)})`);
const sects = await page.$$eval('.doc .installedtab details.sect', ds => ds.map(d => d.dataset.sect));
ok(sects.includes('installed:agent') && sects.includes('installed:service') && !sects.includes('installed:app'),
   `a section per kind with anything on the node, never apps or companions (${sects.join(', ')})`);
ok(await page.evaluate(() => inst.rows.filter(r => r.kind === 'agent' && !r.installed && r.agent !== 'claude').length > 0
   && [...document.querySelectorAll('.doc .installedtab .irow[data-irow^="agent:"]')].every(e => { const r = inst.rows.find(x => `${x.kind}:${x.name}` === e.dataset.irow); return r.installed || r.agent === 'claude'; })),
   'an agent not installed is not a row, but Claude Code is, so a sign-in has a place');
ok(await page.$$eval('.doc .installedtab [data-instact="install"]', bs => bs.every(b => b.dataset.instkind === 'service')) && await page.$('.doc .installedtab [data-libact]') === null,
   'nothing installs from here but a configured service: the Library installs');

// ---- an agent's page: its sign-in (R181 step 2) -------------------------
await section("an agent's page", async () => {
  const CL = '.doc .installedtab .irow[data-irow="agent:claude-code"]';
  ok(await page.$eval(CL, r => !r.querySelector('.idetail') && r.querySelector('[data-instopen]')?.textContent.trim() === 'Open'),
     'a row is a row: Open beside its name, nothing opened in place');
  await page.click(`${CL} [data-instopen]`);
  await page.waitForSelector('.doc .thingtab [data-signin][data-siagent="claude"]', { timeout: 10000 });
  const pg = await page.evaluate(() => ({ facts: /session account/.test(document.querySelector('.doc .thingtab').textContent),
    hash: location.hash, want: '#/machines/installed/' + encodeURIComponent(instNode) + '/' + encodeURIComponent('agent:claude-code'),
    back: document.querySelector('.pane .bar .backhead [data-shellback]')?.textContent.trim() || '',
    name: document.querySelector('.pane .bar .backhead .backof')?.textContent.trim() || '' }));
  ok(pg.facts && pg.hash === pg.want && /Installed/.test(pg.back) && /Claude Code/.test(pg.name),
     `Open is Claude Code's own page: its address, the top header's Back to Installed, its facts and this person's sign-in (${JSON.stringify(pg)})`);
  await page.click('.pane .bar [data-shellback]');
  await page.waitForFunction(() => tabOf(panes[0])?.kind === 'installed', null, { timeout: 10000 });
  ok(true, '...and Back returns to the Installed page');
});

// ---- the model router's page: Configure, saved to its own record ----------
await section("the model router's page", async () => {
  const RTROW = '.doc .installedtab .irow[data-irow="service:model-router"]';
  const RT = '.doc .thingtab';
  ok(await page.$(RTROW) !== null && await page.$eval(RTROW, r => r.querySelector('[data-instact="install"]')?.disabled === true
       && !!r.querySelector('[data-instopen][data-instat="configure"]')),
     'the model router is a Services row with Configure, its Install dead while nothing is behind it');
  await page.click(`${RTROW} [data-instopen][data-instat="configure"]`);
  await page.waitForSelector(`${RT} .icform`, { timeout: 10000 });
  const fields = await page.$$eval(`${RT} .icform [data-icf], ${RT} .icform [data-icadd], ${RT} .icform [data-icproj]`, es => es.map(e => e.dataset.icf || e.dataset.icadd || `proj:${e.value}`));
  ok(fields.includes('anthropic') && fields.includes('openai') && fields.includes('ollama') && fields.includes('custom') && fields.some(f => f.startsWith('proj:')),
     `its page's Configure form is the pack's config block: the providers' keys, the endpoints, Ollama and the spaces (${fields.join(', ')})`);
  await page.fill(`${RT} .icform [data-icf="anthropic"]`, 'sk-ant-test-0000');
  await page.click(`${RT} .icform [data-icadd="custom"]`);
  await page.waitForSelector(`${RT} .icform .icrow[data-iclist="custom"]`, { timeout: 5000 });
  ok(await page.$eval(`${RT} .icform [data-icf="anthropic"]`, i => i.value === 'sk-ant-test-0000'), 'a row added keeps what was typed, as a draft');
  await page.fill(`${RT} .icform .icrow [data-icsub="name"]`, 'groq');
  await page.fill(`${RT} .icform .icrow [data-icsub="base"]`, 'https://api.groq.com/openai/v1');
  await page.fill(`${RT} .icform .icrow [data-icsub="key"]`, 'gsk-test');
  await page.click(`${RT} .icform [data-icsave]`);
  await page.waitForFunction(() => { const r = inst?.rows.find(x => x.kind === 'service'); return r && r.values.anthropic === true && r.values.custom.length === 1; }, null, { timeout: 15000 });
  const saved = await page.evaluate(() => { const r = inst.rows.find(x => x.kind === 'service'); return { anthropic: r.values.anthropic, custom: r.values.custom, ready: r.ready }; });
  ok(saved.anthropic === true && saved.custom[0].name === 'groq' && saved.custom[0].key === true && saved.ready === '',
     `Save keeps the key sealed and shows it only as set, the endpoint with its key as set, and the service is ready to deploy (${JSON.stringify(saved)})`);
  ok(await page.$eval(`${RT} .icform [data-icf="anthropic"]`, i => i.value === '' && /type to replace/.test(i.placeholder))
     && await page.$eval(`${RT} [data-instact="install"]`, b => !b.disabled),
     '...the field empties with "type to replace" in its place, and Install comes live');
  const st = await page.evaluate(async () => (await (await fetch('/api/router?node=' + encodeURIComponent(instNode))).json()));
  ok(st.providers?.anthropic === true && st.custom?.[0]?.name === 'groq', 'what the row saved is the router\'s own record');
  // ...and the Library's card for it says Install is live now, its Details the entry alone.
  await page.evaluate(() => { libNode = instNode; lib = null; openLibrary(); });
  await page.waitForFunction(() => lib && Array.isArray(lib.rows), null, { timeout: 20000 });
  ok(await page.$eval('.doc .librarytab .lcard[data-lrow="service:model-router"]', c => !c.querySelector('[data-libact="install"]').disabled && !c.querySelector('.lcform')),
     'the Library\'s card for it offers Install now and draws no Configure of its own');
});

// ---- nginx and the Scanners are services too (R264) ------------------------
// Installed from their cards in the Library, as the router is; on Installed
// once they are on the node, where Open leads to each one's own page.
await section("nginx and the Scanners are services", async () => {
  await page.evaluate(() => { libNode = instNode; lib = null; openLibrary(); });
  await libraryShow(page, { kind: 'service' });
  const cards = await page.$$eval('.doc .librarytab .lcard[data-lrow^="service:"]', cs => cs.map(c => [c.dataset.lrow, !!c.querySelector('[data-libact="install"]')]));
  ok(['service:nginx', 'service:scanners'].every(k => cards.some(([n, install]) => n === k && install)),
     `the Library's Services hold nginx and the Scanners beside the model router, each with Install (${JSON.stringify(cards)})`);
  await page.evaluate(() => openInstalledTab());
  await page.waitForFunction(() => inst && Array.isArray(inst.rows) && !readBusy('installed'), null, { timeout: 20000 });
  ok(await page.$('.doc .installedtab .irow[data-irow="service:nginx"]') === null
     && await page.evaluate(() => inst.rows.some(r => r.kind === 'service' && r.name === 'nginx' && !r.installed)),
     'one that asks nothing is not on Installed until the Library put it on the node');
  const asked = await page.evaluate(async () => (await postJSON('/api/library', { action: 'install', node: instNode, pack: 'nginx' })));
  ok(asked && !asked.error, `its Install is the nginx page's Deploy (${JSON.stringify(asked).slice(0, 120)})`);
  const row = await until(() => page.evaluate(async () => {
    await loadInstalled();
    const r = document.querySelector('.doc .installedtab .irow[data-irow="service:nginx"]');
    return r && inst.rows.find(x => x.name === 'nginx')?.installed ? r.textContent.replace(/\s+/g, ' ').trim() : null;
  }), 60000, 1500);
  ok(row && /nginx/.test(row) && /deployed/.test(row) && /Open/.test(row) && /Remove/.test(row),
     `once deployed it is a row under Services with Open and Remove (${row})`);
  await page.click('.doc .installedtab .irow[data-irow="service:nginx"] [data-instopen]');
  const there = await page.waitForFunction(() => !!document.querySelector('.doc.on .nginxtab'), null, { timeout: 15000 }).then(() => true, () => false);
  ok(there, 'Open leads to its own page: the routes and certificates for this node');
  page.dialogs.length = 0;
  await page.evaluate(() => openInstalledTab());
  await page.waitForFunction(() => !!document.querySelector('.doc.on .installedtab .irow[data-irow="service:nginx"] [data-instact="remove"]'), null, { timeout: 20000 });
  await page.click('.doc.on .installedtab .irow[data-irow="service:nginx"] [data-instact="remove"]');
  const gone = await until(() => page.evaluate(async () => { await loadInstalled(); return !inst.rows.find(x => x.name === 'nginx')?.installed; }), 60000, 1500);
  ok(gone && /Remove nginx from .*routes and certificates are kept/.test(page.dialogs.join(' ')),
     `Remove asks in the service's own words and takes it off the node (${(page.dialogs.at(-1) || '').slice(0, 120)})`);
});

// ---- a pack that brings a coding agent sits with the agents ---------------
await section("a pack that brings a coding agent sits with the agents", async () => {
  await page.evaluate(() => openInstalledTab());
  await page.waitForFunction(() => inst && !inst.nonode && Array.isArray(inst.rows)
    && !!document.querySelector('.doc.on .installedtab details.sect[data-sect="installed:agent"]'), null, { timeout: 20000 });
  // Drawn and read in one turn of the page: its next read of the node would
  // take a row the fixture's node does not hold away again.
  const got = await page.evaluate(() => {
    agentsAdopt([{ id: 'kite', name: 'Kite', product: 'Kite CLI', command: 'kite', provider: 'Example' }]);
    const row = { kind: 'pack', group: 'agent', tier: 'vetted', name: 'kite', label: 'Kite', about: 'A coding agent from a pack.', installed: true,
                  version: '1.0', pack: { url: 'https://example.test/kite', commit: 'a'.repeat(40), tier: 'vetted' } };
    inst.rows.push(row);
    readMoved('installed'); drawPanes();
    const at = sel => !!document.querySelector(`.doc.on .installedtab details.sect[data-sect="${sel}"] .irow[data-irow="pack:kite"]`);
    const signin = THING_SECTS.pack.find(s => s[0] === 'signin')[2];
    const out = { agents: at('installed:agent'), packs: at('installed:pack'),
                  says: signin(row).replace(/<[^>]+>/g, ' ').replace(/\s+/g, ' ').trim(),
                  plain: signin({ ...row, group: undefined }), away: signin({ ...row, installed: false }) };
    // One whose pack says how it signs in is signed in here, as a shipped
    // agent is (R233 step 6): the card by what the flow says of itself, a
    // field for a code pasted back, the code itself for one typed on the
    // provider's page.
    agentsAdopt([{ id: 'kite', name: 'Kite', product: 'Kite CLI', command: 'kite', provider: 'Example', signin: true }]);
    const text = h => h.replace(/<[^>]+>/g, ' ').replace(/\s+/g, ' ').trim();
    const was = state.signin;
    out.here = signin(row);
    state.signin = { node: instNode, agent: 'kite', running: true, url: 'https://accounts.example.test/o/auth?x=1', paste: true, waiting: true };
    out.paste = signin(row);
    state.signin = { node: instNode, agent: 'kite', running: true, url: 'https://accounts.example.test/device', paste: false, code: 'WXYZ-1234' };
    out.device = signin(row);
    state.signin = was;
    out.here = { text: text(out.here), button: /data-si="in"/.test(out.here) };
    out.paste = { text: text(out.paste), field: /id="authCode"/.test(out.paste) && !/id="authCode"[^>]* disabled/.test(out.paste), link: /href="https:\/\/accounts\.example\.test\/o\/auth\?x=1"/.test(out.paste) };
    out.device = { text: text(out.device), field: /id="authCode"/.test(out.device), code: /class="sicode">WXYZ-1234</.test(out.device) };
    // Edit is for a pack a person added themselves, here as on the Library.
    out.edit = { catalog: /data-instact="edit"/.test(instActs(row, { install: true })), own: /data-instact="edit"/.test(instActs({ ...row, tier: 'sideloaded' }, { install: true })),
                 remove: /data-instact="remove"/.test(instActs(row, { install: true })) };
    inst.rows.pop(); agentsAdopt([]); readMoved('installed'); drawPanes();
    return out;
  });
  ok(!got.edit.catalog && got.edit.own && got.edit.remove,
     `a pack kept from the catalog has Remove and no Edit on its row, and one a person added has Edit (${JSON.stringify(got.edit)})`);
  // Edit reads the store's rows before it opens the pack's dialog: opened by
  // itself the page holds only a stand-in for them, and the dialog, finding no
  // pack in it, opened as Add your own with an empty address.
  const editOrder = await page.evaluate(async () => {
    toolchains = { name: 'stand-in', job: null, items: [], stub: true };
    const order = [], open0 = tpOpen, load0 = loadToolchains;
    window.loadToolchains = async (...a) => { order.push('read'); const r = await load0(...a); return r; };
    window.tpOpen = name => { order.push(`open ${name} on ${toolchains?.stub ? 'the stand-in' : 'the rows'}`); };
    inst.rows.push({ kind: 'pack', pack: true, name: 'walk-pack', label: 'Walk pack', tier: 'sideloaded', installed: true });
    await instAct(document.createElement('button'), 'edit', 'pack', 'walk-pack');
    inst.rows.pop(); window.tpOpen = open0; window.loadToolchains = load0;
    return order;
  });
  ok(editOrder.join('; ') === 'read; open walk-pack on the rows',
     `Edit on a pack a person added reads the store's rows first, so its own dialog opens (${editOrder.join('; ')})`);
  ok(got.here.button && /You are not signed in to Kite on \S+: sign in here, or in the terminal of a Kite session there/.test(got.here.text),
     `a pack agent whose pack says how it signs in has Sign in on its page, and the page says its terminal is the other way (${got.here.text.slice(0, 120)})`);
  ok(got.paste.field && got.paste.link && /sign in to Example, and paste the code it gives you/.test(got.paste.text),
     `its flow that takes a code back draws the link and the field for the code (${got.paste.text.slice(0, 120)})`);
  ok(got.device.code && !got.device.field && /enter this code there/.test(got.device.text),
     `one that shows a code draws the code and no field (${got.device.text.slice(0, 120)})`);
  ok(got.agents && !got.packs, 'a pack that brings a coding agent is a row under Coding agents, not under Tool packs');
  ok(/Kite signs in with an Example account in its own terminal: start a Kite session/.test(got.says) && got.plain === '' && got.away === '',
     `its page says where it signs in, which a plain pack's page and one not installed do not (${got.says.slice(0, 140)})`);
});

// ---- no node ---------------------------------------------------------------
// Emptied again until the page says so: a read of the nodes or of the page
// already out lands after the list is emptied and fills it again, as the
// Library's own no-node step met under a gate's load.
await page.evaluate(() => openInstalledTab());
await page.waitForFunction(() => {
  if (document.querySelector('.doc .installedtab .instnone')) return true;
  if (!readBusy('nodes') && !readBusy('installed') && (nodesList?.length || instNode || inst)){ nodesList = []; nodesStale = false; instNode = ''; inst = null; loadInstalled(); }
  return false;
}, null, { timeout: 20000, polling: 300 });
ok(await page.evaluate(() => !document.querySelector('.doc .installedtab .irow') && !document.querySelector('.pane .bar #ndPick')),
   'with no node enrolled it says to enroll one');
await page.evaluate(() => { nodesList = null; nodesStale = true; instNode = ''; inst = null; loadInstalled(); });
await page.waitForSelector('.pane .bar #ndPick', { timeout: 20000 });

// ---- an install's receipt ----------------------------------------------------
// What a pack's install left on a node (R234; the operator, 13 Nov: what it
// downloads from somewhere else had no paper trail): the manifest commit the
// copy came from, when, how many files and how big, one hash over them all,
// and each thing the receipt shows that a person would act on.
await section("an install's receipt", async () => {
  const said = await page.evaluate(() => {
    const host = document.createElement('div');
    const at = Date.UTC(2026, 10, 13, 5, 0, 0) / 1000;
    const rc = more => ({ commit: 'a'.repeat(40), tree: '1'.repeat(64), files: 214, bytes: 50331648, at, stale: '', before: '', differs: [], ...more });
    const text = p => { host.innerHTML = tcReceiptLines(p); return [...host.querySelectorAll('.tcreceipt')].map(e => `${e.classList.contains('warn') ? 'WARN ' : ''}${e.textContent}`); };
    return { plain: text({ installed: true, receipt: rc() }),
             one: text({ installed: true, receipt: rc({ files: 1 }) })[0],
             stale: text({ installed: true, receipt: rc({ stale: 'b'.repeat(40) }) }),
             before: text({ installed: true, receipt: rc({ before: '2'.repeat(64) }) }),
             differs: text({ installed: true, receipt: rc({ differs: [{ node: 'alder', tree: '3'.repeat(64) }, { node: 'birch', tree: '4'.repeat(64) }] }) }),
             cut: text({ installed: true, receipt: rc({ net: 'cut' }) }), open: text({ installed: true, receipt: rc({ net: 'open' }) }),
             seen: (() => {
               // The Look dialog says what a pack declares it downloads, or that it declares none.
               const m = more => ({ manifest: { name: 'hexkit', label: 'Hex kit', platforms: ['linux/amd64'], verbs: {}, steps: [['sh', '{dir}/install.sh']], ...more }, commit: 'c'.repeat(40) });
               const read = seen => { host.innerHTML = tpSeen(seen, null, false); return [...host.querySelectorAll('.sub')].map(e => e.textContent).filter(t => /declares/.test(t)).join(' | '); };
               return [read(m({ fetch: [{ url: 'https://example.com/hexkit.tgz', sha256: 'ab'.repeat(32), to: 'dl/hexkit.tgz' }] })), read(m({})), read(m({ steps: [] }))];
             })(),
             none: [text({ installed: true, receipt: null }).length, text({ installed: false, receipt: rc() }).length] };
  });
  ok(said.plain.length === 1 && /^Installed .+ from manifest aaaaaaaaaaaa: 214 files, 48\.0 MB, receipt 111111111111\.$/.test(said.plain[0]) && / 1 file,/.test(said.one),
     `an installed pack says its receipt: the manifest it came from, when, how many files and how big, and one hash over them (${said.plain[0]})`);
  ok(said.stale.length === 2 && /^WARN This copy is from an earlier manifest: the one kept now is bbbbbbbbbbbb\. Install again takes what that one installs\.$/.test(said.stale[1]),
     `...a copy from an earlier manifest than the one kept now says so, and what to do (${said.stale[1]})`);
  // ...and its row and its Library card say it where the state is read,
  // with Install again to press (B799): it read installed, nothing to press.
  const rows = await page.evaluate(() => {
    const r = { kind: 'toolchain', name: 'zig', label: 'Zig', installed: true, pack: null,
                receipt: { commit: 'a'.repeat(40), tree: '1'.repeat(64), stale: 'b'.repeat(40) } };
    const box = document.createElement('div');
    const words = h => { box.innerHTML = h; return box.textContent.trim(); };
    const presses = h => { box.innerHTML = h; return [...box.querySelectorAll('button')].map(b => `${b.dataset.instact || b.dataset.libact}:${b.textContent}`); };
    const prev = libNode; libNode = libNode || 'n_x';
    const out = { row: words(instState(r)), acts: presses(instActs(r, { install: true })),
                  card: words(libState(r)), verb: presses(libActs(r, { install: true, packs: true })),
                  fresh: words(instState({ ...r, receipt: { ...r.receipt, stale: '' } })) };
    libNode = prev;
    return out;
  });
  ok(rows.row === 'installed from an earlier manifest' && rows.acts[0] === 'update:Install again'
     && rows.card === 'installed from an earlier manifest' && rows.verb.includes('install:Install again') && rows.fresh === 'installed',
     `...and its Installed row and Library card say it with Install again to press (${JSON.stringify(rows)})`);
  ok(said.before.length === 2 && /^WARN The same manifest left other files here the time before \(receipt 222222222222\)/.test(said.before[1]),
     `...the same manifest having left other files here before is said (${said.before[1]})`);
  ok(said.differs.length === 2 && /^WARN The same manifest left other files on alder, birch \(receipt 333333333333, 444444444444\): something its install fetches is not pinned\.$/.test(said.differs[1]),
     `...and so is another node's copy of the same manifest being other files (${said.differs[1]})`);
  ok(said.none.join() === '0,0', '...and one installed before receipts were kept, or not installed, says nothing');
  // Declared downloads (pack format 3): each held to its sha256, and the
  // steps run with no network, or with it on a node that cannot cut it.
  ok(said.cut.length === 2 && /^Its downloads are declared: each matched its sha256, and its install steps ran with no network\.$/.test(said.cut[1])
     && said.open.length === 2 && /this node cannot cut the network for a step, so its install steps ran with it\.$/.test(said.open[1]) && !/^WARN/.test(said.open[1]),
     `a pack that declares its downloads says its steps ran with no network, or that this node could not cut it (${said.cut[1]} | ${said.open[1]})`);
  ok(/^It declares what it downloads, each held to its sha256 before its steps run with no network: dl\/hexkit\.tgz from https:\/\/example\.com\/hexkit\.tgz \(abababababab\)\.$/.test(said.seen[0])
     && /^It declares no downloads: what its install steps fetch is not checked/.test(said.seen[1]) && said.seen[2] === '',
     `...and Look says what it declares it downloads, or that it declares none, before it is added (${JSON.stringify(said.seen)})`);
});

await done(browser);
