// The Installed page (R172): under Machines beside Nodes and Storage, one
// node picked, what the Library put there by kind, each row opening on
// what the catalog's card does not show: an agent's sign-in, a toolchain's
// path and system packages, a service's Configure from its config block
// (the model router's providers, endpoints, Ollama and projects, saved to
// the router's own record), and Remove.
import { launch, newPage, ok, done, ready, URL } from './lib.mjs';

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
{
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
}

// ---- the model router's page: Configure, saved to its own record ----------
{
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
}

// ---- a pack that brings a coding agent sits with the agents ---------------
{
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
    instRev++; drawPanes();
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
    inst.rows.pop(); agentsAdopt([]); instRev++; drawPanes();
    return out;
  });
  ok(!got.edit.catalog && got.edit.own && got.edit.remove,
     `a pack kept from the catalog has Remove and no Edit on its row, and one a person added has Edit (${JSON.stringify(got.edit)})`);
  ok(got.here.button && /You are not signed in to Kite on \S+: sign in here, or in the terminal of a Kite session there/.test(got.here.text),
     `a pack agent whose pack says how it signs in has Sign in on its page, and the page says its terminal is the other way (${got.here.text.slice(0, 120)})`);
  ok(got.paste.field && got.paste.link && /sign in to Example, and paste the code it gives you/.test(got.paste.text),
     `its flow that takes a code back draws the link and the field for the code (${got.paste.text.slice(0, 120)})`);
  ok(got.device.code && !got.device.field && /enter this code there/.test(got.device.text),
     `one that shows a code draws the code and no field (${got.device.text.slice(0, 120)})`);
  ok(got.agents && !got.packs, 'a pack that brings a coding agent is a row under Coding agents, not under Tool packs');
  ok(/Kite signs in with an Example account in its own terminal: start a Kite session/.test(got.says) && got.plain === '' && got.away === '',
     `its page says where it signs in, which a plain pack's page and one not installed do not (${got.says.slice(0, 140)})`);
}

// ---- no node ---------------------------------------------------------------
await page.evaluate(() => { openInstalledTab(); nodesList = []; instNode = ''; inst = null; loadInstalled(); });
await page.waitForSelector('.doc .installedtab .instnone', { timeout: 20000 });
ok(await page.evaluate(() => !document.querySelector('.doc .installedtab .irow') && !document.querySelector('.pane .bar #ndPick')),
   'with no node enrolled it says to enroll one');
await page.evaluate(() => { nodesList = null; nodesStale = true; instNode = ''; inst = null; loadInstalled(); });
await page.waitForSelector('.pane .bar #ndPick', { timeout: 20000 });

await done(browser);
