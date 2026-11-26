// The Clusters page (R281 step 2): a Kubernetes cluster added from a
// kubeconfig against a stub API server this file runs (as agent-stub stands
// in for a node), its facts and namespaces drawn, Test, Rename and Forget,
// a cloud CLI's sign-in refused with the way out, the credential never in
// what the page reads, and the cluster a connection Controller settings lists.
import { launch, newPage, ok, done, ready, URL, section, until } from './lib.mjs';
import http from 'node:http';

let token = 'good';
const stub = http.createServer((req, res) => {
  const answers = {
    '/version': { gitVersion: 'v1.37.3+k3s1' },
    '/api/v1/nodes': { items: [{ status: { conditions: [{ type: 'Ready', status: 'True' }] } }, { status: { conditions: [{ type: 'Ready', status: 'False' }] } }] },
    '/api/v1/namespaces': { items: [{ metadata: { name: 'default' } }, { metadata: { name: 'alpha-staging', labels: { 'aerieos.io/space': 'alpha' } } }] },
  };
  const okAuth = req.headers.authorization === 'Bearer ' + token;
  const body = !okAuth ? { message: 'Unauthorized' } : answers[req.url] || { message: 'not found' };
  res.writeHead(!okAuth ? 401 : answers[req.url] ? 200 : 404, { 'Content-Type': 'application/json' });
  res.end(JSON.stringify(body));
});
await new Promise(r => stub.listen(0, '127.0.0.1', r));
const API = `http://127.0.0.1:${stub.address().port}`;
const kubeconfig = user => `apiVersion: v1\nkind: Config\nclusters:\n- cluster:\n    server: ${API}\n  name: lab\ncontexts:\n- context:\n    cluster: lab\n    user: me\n  name: lab\ncurrent-context: lab\nusers:\n- name: me\n  user:\n${user}`;

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
  ok(/alpha-staging \(alpha\)/.test(body) && /a token/.test(body), `opened, it says its namespaces with the space that owns each and how it signs in (${body.slice(0, 160)})`);
});

await section("a cloud CLI's sign-in is refused, with the way out", async () => {
  const r = await page.evaluate(k => postJSON('/api/clusters', { action: 'add', name: 'eks', kubeconfig: k }),
    kubeconfig('    exec:\n      command: aws\n'));
  ok(/cloud CLI/.test(r.error || '') && /kubectl create token/.test(r.error || ''), `refused, saying how to make a token-based one (${(r.error || '').slice(0, 90)})`);
  // The refusal's 400 is what was asked for, and the browser logs it.
  page.errors = page.errors.filter(e => !/status of 400 .*\/api\/clusters/.test(e));
});

await section("Test, Rename and Forget", async () => {
  const conn = await page.evaluate(async () => (await (await fetch('/api/connections')).json()).rows || []);
  ok(conn.some(r => r.kind === 'cluster' && r.name === 'lab' && r.whose === 'shared' && r.by),
     'Connected services lists it, shared by spaces, with who added it');
  token = 'rotated';
  await page.click('.clusterstab [data-clact="test"]');
  await page.waitForFunction(() => /not answering/.test(document.querySelector('.clusterstab details[data-sect^="clusters:c:"] > summary')?.textContent || ''), null, { timeout: 15000 })
    .catch(() => {});
  const down = await page.$eval('.clusterstab details[data-sect^="clusters:c:"]', d => ({ head: d.querySelector('summary').textContent, said: d.textContent }));
  ok(/not answering/.test(down.head) && /401/.test(down.said), `Test on a credential it no longer takes says so on the section (${down.head.replace(/\s+/g, ' ')})`);
  token = 'good';
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

stub.close();
await done(browser);
