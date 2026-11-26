// The Clusters page (R281 step 2): a Kubernetes cluster added from a
// kubeconfig against the stub API server lib.mjs runs (kubeApi, as agent-stub stands
// in for a node), its facts and namespaces drawn, Test, Rename and Forget,
// a cloud CLI's sign-in refused with the way out, the credential never in
// what the page reads, and the cluster a connection Controller settings lists.
import { launch, newPage, ok, done, ready, URL, DIR, section, until, kubeApi } from './lib.mjs';
import { writeFileSync, rmSync } from 'node:fs';

// One a hand made for a space of the same name, without this install's mark.
const api = await kubeApi({ namespaces: [{ metadata: { name: 'alpha-staging', labels: { 'aerieos.io/space': 'alpha' } } }] });
const kubeconfig = user => api.kubeconfig(user);

const browser = await launch();
const page = await newPage(browser, { viewport: { width: 1280, height: 900 } });
await page.goto(URL);
await ready(page);

await section("a cluster added from a kubeconfig", async () => {
  const rail = await page.evaluate(() => RAIL.find(g => g.key === 'machines').tools.map(([k]) => k));
  ok(rail.indexOf('clusters') === rail.indexOf('nodes') + 1, `Clusters is a Machines page beside Nodes (${rail.join(',')})`);
  await page.evaluate(() => openClustersTab());
  await page.waitForSelector('.clusterstab #clName', { timeout: 15000 });
  const asleep = await page.$eval('.clusterstab #clAdd', b => b.disabled);
  await page.fill('.clusterstab #clName', 'lab');
  await page.fill('.clusterstab #clText', kubeconfig('    token: good\n'));
  const awake = await page.$eval('.clusterstab #clAdd', b => !b.disabled);
  ok(asleep && awake, 'with none kept the page is Add cluster, its press asleep until a name and a kubeconfig are in');
  await page.click('.clusterstab #clAdd');
  await page.waitForSelector('.clusterstab details[data-sect^="clusters:c:"]', { timeout: 15000 });
  const row = await page.$eval('.clusterstab details[data-sect^="clusters:c:"]', d => ({
    title: d.querySelector('summary .t')?.textContent, status: d.querySelector('summary')?.textContent.replace(/\s+/g, ' ') }));
  ok(row.title === 'lab' && /v1\.37\.3\+k3s1 · 1 of 2 ready/.test(row.status), `the cluster is a section, its version and nodes ready of all on its heading (${JSON.stringify(row)})`);
  const read = await page.evaluate(async () => JSON.stringify(await (await fetch('/api/clusters')).json()));
  ok(!/good/.test(read), 'what the page reads of it never carries the token');
  await page.click('.clusterstab details[data-sect^="clusters:c:"] > summary');
  await page.waitForSelector('.clusterstab [data-clact="test"]', { state: 'visible', timeout: 10000 });
  const body = await page.$eval('.clusterstab details[data-sect^="clusters:c:"]', d => d.textContent.replace(/\s+/g, ' '));
  ok(/default, alpha-staging/.test(body) && !/\(alpha\)/.test(body) && /a token/.test(body),
     `opened, it says its namespaces, one this install did not make nobody's, and how it signs in (${body.slice(0, 160)})`);
});

await section("a cloud CLI's sign-in is refused, with the way out", async () => {
  const r = await page.evaluate(k => postJSON('/api/clusters', { action: 'add', name: 'eks', kubeconfig: k }),
    kubeconfig('    exec:\n      command: aws\n'));
  // ...and pressed on the page, the press comes back live for another try.
  await page.click('.clusterstab #clAddOpen');
  await page.waitForSelector('.clusterstab #clName', { timeout: 10000 });
  await page.fill('.clusterstab #clName', 'eks');
  await page.fill('.clusterstab #clText', kubeconfig('    exec:\n      command: aws\n'));
  await page.click('.clusterstab #clAdd');
  const back = await page.waitForFunction(() => { const b = document.querySelector('.clusterstab #clAdd'); return b && !b.disabled && !b.classList.contains('busy'); }, null, { timeout: 10000 }).then(() => true, () => false);
  ok(back, 'a refused Add comes back live, what was typed still there');
  await page.click('.clusterstab #clCancel');
  ok(/cloud CLI/.test(r.error || '') && /ServiceAccount's token/.test(r.error || '') && !/`|kubectl/.test(r.error || ''),
     `refused in one sentence saying the way out, its command left to the page's hint (${(r.error || '').slice(0, 90)})`);
  // The refusal's 400 is what was asked for, and the browser logs it.
  page.errors = page.errors.filter(e => !/status of 400 .*\/api\/clusters/.test(e));
});

await section("Test, Rename and Forget", async () => {
  const conn = await page.evaluate(async () => (await (await fetch('/api/connections')).json()).rows || []);
  ok(conn.some(r => r.kind === 'cluster' && r.name === 'lab' && r.whose === 'shared' && r.by),
     'Connected services lists it, shared by spaces, with who added it');
  api.token = 'rotated';
  await page.click('.clusterstab [data-clact="test"]');
  await page.waitForFunction(() => /not answering/.test(document.querySelector('.clusterstab details[data-sect^="clusters:c:"] > summary')?.textContent || ''), null, { timeout: 15000 })
    .catch(() => {});
  const down = await page.$eval('.clusterstab details[data-sect^="clusters:c:"]', d => ({ head: d.querySelector('summary').textContent, said: d.textContent }));
  ok(/not answering/.test(down.head) && /401/.test(down.said), `Test on a credential it no longer takes says so on the section (${down.head.replace(/\s+/g, ' ')})`);
  api.token = 'good';
  page.answers.push({ index: 0, text: 'lab two' });
  await page.click('.clusterstab [data-clact="rename"]');
  await page.waitForFunction(() => document.querySelector('.clusterstab details[data-sect^="clusters:c:"] summary .t')?.textContent === 'lab two', null, { timeout: 15000 }).catch(() => {});
  ok(await page.$eval('.clusterstab details[data-sect^="clusters:c:"] summary .t', e => e.textContent) === 'lab two', 'Rename names it anew');
  page.dialogs.length = 0;
  await page.click('.clusterstab [data-clact="forget"]');
  const gone = await until(async () => (await page.evaluate(async () => (await (await fetch('/api/clusters')).json()).clusters || [])).length === 0, 10000, 200);
  ok(page.dialogs.some(d => /Forget lab two\?/.test(d)) && gone, 'Forget asks first, then the cluster is gone from here');
  ok(page.errors.length === 0, `no console error through any of it (${page.errors.slice(0, 2).join(' | ')})`);
});

// k3s from the Library (R281 step 1): a node running it is one press on the
// page, and one whose cluster is still starting says so in one sentence with
// the press live again. Its record is written as the Library's Install
// leaves it: this world has no k3s to install.
await section("Add k3s on a node", async () => {
  const nid = await page.evaluate(async () => ((await (await fetch('/api/v1/nodes')).json()).nodes || [])
    .find(n => n.kind === 'agent' && n.state !== 'retired' && !n.config?.host_only)?.id);
  const kf = `${DIR}/state/k3s.json`;
  writeFileSync(kf, JSON.stringify({ [nid]: { deployed: 1, token_id: 'abc123', secret: '0123456789abcdef', traefik: false } }));
  await page.evaluate(() => loadClusters());
  const b = await page.waitForSelector('.clusterstab [data-clk3s]', { timeout: 15000 }).catch(() => null);
  ok(!!b && /^Add k3s on /.test(await b.textContent()), 'a node running k3s from the Library is a press of its own on the page');
  page.answers.push({ index: 0, text: 'lab k3s' });
  await b.click();
  // The refusal's own toast, then the press: waited for in that order, since
  // the press is not busy yet while its name is asked.
  await page.waitForFunction(() => [...document.querySelectorAll('.toast, .tmsg')].some(t => /still be starting/.test(t.textContent)),
    null, { timeout: 60000 }).catch(() => {});
  const back = await page.waitForFunction(() => { const x = document.querySelector('.clusterstab [data-clk3s]'); return x && !x.classList.contains('busy') && !x.disabled; },
    null, { timeout: 15000 }).then(() => true, () => false);
  const said = await page.evaluate(() => [...document.querySelectorAll('.toast, .tmsg')].map(t => t.textContent.trim()).filter(t => /k3s|starting/.test(t)).slice(-1)[0] || '');
  ok(back && /still be starting/.test(said), `a cluster that does not say its authority yet is said in one sentence, the press live again (${said})`);
  page.errors = page.errors.filter(e => !/status of 400 .*\/api\/clusters/.test(e));
  rmSync(kf, { force: true });
  await page.evaluate(n => { libNode = n; lib = null; openLibrary(); }, nid);
  const card = await page.waitForSelector('.doc .librarytab .lcard[data-lrow="service:k3s"]', { timeout: 20000 }).catch(() => null);
  ok(!!card, 'k3s has its card in the Library, beside the other services');
  // Its Install reaches k3s's own deploy, as nginx's and the Scanners' do,
  // and Remove takes it off again.
  const inst = await page.evaluate(n => postJSON('/api/library', { action: 'install', node: n, pack: 'k3s' }), nid);
  ok(!inst.error && /^k3s-/.test(inst.name || '') && (inst.job || inst.note), `its Install makes k3s's System container on the node (${JSON.stringify(inst).slice(0, 120)})`);
  const rm = await page.evaluate(n => postJSON('/api/library', { action: 'remove', node: n, pack: 'k3s' }), nid);
  ok(!rm.error, `...and Remove takes it off (${JSON.stringify(rm).slice(0, 120)})`);
  ok(page.errors.length === 0, `no console error (${page.errors.slice(0, 2).join(' | ')})`);
});

api.close();
await done(browser);
