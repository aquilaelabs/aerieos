// A space's Deploy section (R281 step 3): with a cluster kept, the space's
// settings list its Kubernetes environments as records; Add environment's
// Save makes the namespace ready on the cluster (the namespace labeled with
// the space's id and this install's mark, a deployer with a Role and a
// RoleBinding confined to it), a namespace somebody else made is refused
// with the record left open as typed, Edit changes one without asking the
// cluster again, and Remove leaves the cluster as it was. What each
// repository deploys, Draft from the compose writing a chart into its tree
// uncommitted, and a deploy refused where it has nowhere to build (step 4).
// Against the stub API server lib.mjs runs (kubeApi).
import { launch, newPage, ok, done, ready, URL, DIR, section, until, kubeApi } from './lib.mjs';
import { writeFileSync, readFileSync, existsSync } from 'node:fs';
import { execFileSync } from 'node:child_process';

const api = await kubeApi({ namespaces: [{ metadata: { name: 'web', labels: {} } }] });
const browser = await launch();
const page = await newPage(browser, { viewport: { width: 1280, height: 1000 } });
await page.goto(URL);
await ready(page);

const open = async () => {
  await page.evaluate(() => renameProject('alpha', 'project'));
  await page.waitForSelector('#rnmodal:not([hidden])', { timeout: 10000 });
};
const rows = () => page.$$eval('#rnEnvRows .rnenv:not(.open) .tline', ls => ls.map(l => l.textContent.replace(/\s+/g, ' ').trim()));

await section("no cluster kept, no Deploy section", async () => {
  await open();
  await page.waitForFunction(() => rnDeploy !== null, null, { timeout: 10000 });
  ok(await page.$eval('details[data-sect="rn:deploy"]', d => d.hidden), 'with no cluster kept and no environment, the space\'s settings draw no Deploy');
  await page.click('#rnCancel');
  await page.evaluate(async k => postJSON('/api/clusters', { action: 'add', name: 'lab', kubeconfig: k }), api.kubeconfig());
});

await section("an environment saved makes its namespace ready", async () => {
  await open();
  await page.waitForSelector('details[data-sect="rn:deploy"]:not([hidden])', { timeout: 10000 });
  const at = await page.$$eval('#rnmodal details.rngroup', ds => ds.filter(d => getComputedStyle(d).display !== 'none' && !d.hidden).map(d => d.dataset.sect));
  ok(at.indexOf('rn:deploy') > at.indexOf('rn:runs') && at.indexOf('rn:deploy') < at.indexOf('rn:sees'),
     `Deploy is the space's, after where it runs and before what its sessions reach (${at.join(',')})`);
  ok(!await page.$('details[data-sect="rn:deploy"] [data-rnbar]'), 'a list of records has no Save at its foot');
  await page.click('#rnEnvAdd');
  await page.waitForSelector('.rnenv.open [data-envf="name"]', { timeout: 5000 });
  await page.fill('.rnenv.open [data-envf="name"]', 'staging');
  const form = await page.$eval('.rnenv.open', o => ({ cluster: o.querySelector('[data-envf="cluster"]').selectedOptions[0]?.textContent,
    ns: o.querySelector('[data-envf="namespace"]').value, branch: o.querySelector('[data-envbranch]').hidden }));
  ok(form.cluster === 'lab' && form.ns === 'alpha-staging' && form.branch,
     `Add environment opens its form on the cluster kept, the namespace named for the space as the name is typed (${JSON.stringify(form)})`);
  await page.fill('.rnenv.open [data-envf="registry"]', 'ghcr.io/ada/alpha');
  await page.click('.rnenv.open [data-envsave]');
  await page.waitForFunction(() => !document.querySelector('#rnEnvRows .rnenv.open') && document.querySelector('#rnEnvRows .rnenv'), null, { timeout: 15000 });
  const r = await rows();
  ok(r.length === 1 && /^staging/.test(r[0]) && /lab \/ alpha-staging/.test(r[0]) && /by hand/.test(r[0]) && /Edit$/.test(r[0]),
     `Save folds it back to a row: its name, its cluster and namespace, when it deploys, and Edit (${r.join(' | ')})`);
  const ns = api.objs.get('/api/v1/namespaces/alpha-staging');
  const lb = ns?.metadata?.labels || {};
  ok(/^P\d+$/.test(lb['aerieos.io/space'] || '') && /^[0-9a-f]{16}$/.test(lb['aerieos.io/install'] || '') && lb['aerieos.io/env'] === 'staging',
     `the namespace is made, labeled with the space's id and this install's mark (${JSON.stringify(lb)})`);
  const role = api.objs.get('/apis/rbac.authorization.k8s.io/v1/namespaces/alpha-staging/roles/aerie-deployer');
  const bind = api.objs.get('/apis/rbac.authorization.k8s.io/v1/namespaces/alpha-staging/rolebindings/aerie-deployer');
  ok(api.objs.has('/api/v1/namespaces/alpha-staging/serviceaccounts/aerie-deployer') && role?.kind === 'Role'
     && bind?.subjects?.[0]?.name === 'aerie-deployer' && !api.calls.some(c => /clusterrole/.test(c)),
     'and in it a deployer with a Role and a RoleBinding confined to it, nothing cluster-wide');
  const owner = await page.evaluate(async () => {
    const c = (await (await fetch('/api/clusters')).json()).clusters[0];
    await postJSON('/api/clusters', { action: 'test', id: c.id });
    const space = ((await (await fetch('/api/clusters')).json()).clusters[0].facts.namespaces || []).find(n => n.name === 'alpha-staging')?.space;
    const spaces = (await (await fetch('/api/clusters')).json()).clusters[0].spaces;
    return { space, key: reposOf('alpha'), shown: projLabel(space), spaces };
  });
  ok(owner.space === owner.key && owner.shown === 'alpha', `the Clusters page reads it as the space's, by its key, shown by its name (${JSON.stringify(owner)})`);
  ok(JSON.stringify(owner.spaces) === '["alpha"]', `...and names the spaces deploying to it, which its Forget says (${owner.spaces})`);
});

await section("a namespace somebody else made is refused", async () => {
  await page.click('#rnEnvAdd');
  await page.fill('.rnenv.open [data-envf="name"]', 'prod');
  await page.fill('.rnenv.open [data-envf="namespace"]', 'web');
  await page.click('.rnenv.open [data-envsave]');
  const back = await page.waitForFunction(() => { const b = document.querySelector('.rnenv.open [data-envsave]'); return b && !b.disabled && !b.classList.contains('busy'); },
    null, { timeout: 15000 }).then(() => true, () => false);
  const said = await page.evaluate(() => [...document.querySelectorAll('.toast, .tmsg')].map(t => t.textContent.trim()).filter(Boolean).slice(-1)[0] || '');
  const kept = await page.$eval('.rnenv.open', o => [o.querySelector('[data-envf="name"]').value, o.querySelector('[data-envf="namespace"]').value].join());
  ok(back && /not this space's/.test(said) && kept === 'prod,web' && !api.objs.has('/api/v1/namespaces/web/serviceaccounts/aerie-deployer'),
     `refused in one sentence, the record open as typed, the namespace never taken over (${said})`);
  await page.click('.rnenv.open [data-envcancel]');
  page.errors = page.errors.filter(e => !/status of 400 .*\/api\/deploy/.test(e));
});

await section("Edit and Remove", async () => {
  const before = api.calls.length;
  await page.click('#rnEnvRows [data-envedit="0"]');
  await page.selectOption('.rnenv.open [data-envf="when"]', 'push');
  ok(await page.$eval('.rnenv.open [data-envbranch]', l => !l.hidden), 'On a push to a branch asks which branch');
  await page.fill('.rnenv.open [data-envf="branch"]', 'main');
  await page.check('.rnenv.open [data-envf="production"]');
  await page.click('.rnenv.open [data-envsave]');
  await page.waitForFunction(() => !document.querySelector('#rnEnvRows .rnenv.open'), null, { timeout: 15000 });
  const r = await rows();
  ok(/on a push to main/.test(r[0] || '') && /production/.test(r[0] || '') && api.calls.length === before,
     `Edit changes when it deploys and marks it production, asking the cluster nothing (${r.join(' | ')})`);
  page.dialogs.length = 0;
  await page.click('#rnEnvRows [data-envedit="0"]');
  await page.click('.rnenv.open [data-envdel]');
  const gone = await until(async () => (await rows()).length === 0, 10000, 200);
  ok(gone && page.dialogs.some(d => /Remove staging\?/.test(d)) && api.objs.has('/api/v1/namespaces/alpha-staging'),
     'Remove asks first, then the row is gone and its namespace stays on the cluster');
  ok(page.errors.length === 0, `no console error through any of it (${page.errors.slice(0, 2).join(' | ')})`);
});

await section("what each repository deploys, Draft from the compose, and a deploy with nowhere to build", async () => {
  // Step 4: alpha has a compose file and neither a chart nor manifests.
  writeFileSync(`${DIR}/ws/alpha/docker-compose.yml`, 'services:\n  web:\n    build: .\n    ports: ["8080:80"]\n');
  await open();
  await page.waitForSelector('#rnShipField:not([hidden])', { timeout: 10000 });
  const line = () => page.$eval('#rnShipRows', e => e.textContent.replace(/\s+/g, ' ').trim());
  const was = await line();
  ok(/alpha/.test(was) && /drafted from its compose file/.test(was) && !!await page.$('[data-shipdraft="alpha"]'),
     `What deploys names the repository, says it has nothing yet, and offers Draft from the compose (${was})`);
  await page.click('[data-shipdraft="alpha"]');
  const drew = await until(async () => /Helm chart in deploy\/chart/.test(await line()), 10000, 200);
  const web = existsSync(`${DIR}/ws/alpha/deploy/chart/templates/web.yaml`) ? readFileSync(`${DIR}/ws/alpha/deploy/chart/templates/web.yaml`, 'utf8') : '';
  const st = execFileSync('git', ['-C', `${DIR}/ws/alpha`, 'status', '--porcelain', '--', 'deploy']).toString();
  ok(drew && /\.Values\.image\.repository/.test(web) && /^\?\? deploy\//m.test(st) && !await page.$('[data-shipdraft]'),
     `the press writes the chart into the tree, uncommitted, its built service on the deploy's image, and the line says so (${await line()} | ${st.trim()})`);
  await page.click('#rnCancel');
  const cl = await page.evaluate(async () => ((await getJSON('/api/clusters')).clusters || [])[0]?.id);
  await page.evaluate(c => postJSON('/api/deploy', { project: 'alpha', action: 'save', was: '',
    env: { name: 'qa', cluster: c, namespace: 'alpha-qa', registry: '', when: 'hand' } }), cl);
  const r = await page.evaluate(() => postJSON('/api/deploy', { project: 'alpha', action: 'deploy', env: 'qa', ref: 'HEAD' }));
  ok(/alpha has no node to build on/.test(r.error || '') && !r.job, `a deploy with no node to build on is refused, saying so (${r.error})`);
  const rb = await page.evaluate(() => postJSON('/api/deploy', { project: 'alpha', action: 'rollback', env: 'qa' }));
  ok(/no earlier deploy/.test(rb.error || ''), `Roll back with nothing deployed before says so (${rb.error})`);
});

api.close();
await done(browser);
