// A space's Deploy section: with a cluster kept, the space's
// settings list its Kubernetes environments as records; Add environment's
// Save makes the namespace ready on the cluster (the namespace labeled with
// the space's id and this install's mark, a deployer with a Role and a
// RoleBinding confined to it), a namespace somebody else made is refused
// with the record left open as typed, Edit changes one without asking the
// cluster again, and Remove leaves the cluster as it was. What each
// repository deploys, Draft from the compose writing a chart into its tree
// uncommitted, and a deploy refused where it has nowhere to build (step 4).
// Against the stub API server lib.mjs runs (kubeApi).
import { launch, newPage, ok, done, ready, URL, DIR, REPO, section, until, kubeApi, call, asSession } from './lib.mjs';
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
  ok(/alpha/.test(was) && /alpha deploys nothing yet: a chart can be drafted from its compose file/.test(was) && !!await page.$('[data-shipdraft="alpha"]'),
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

await section("the Kubernetes view: what runs, Scale, Restart and a pod's log, through the deployer", async () => {
  // The refusals asked for above log their 400s in some engines: this
  // section counts only its own.
  page.errors.length = 0;
  // Step 5: a Deployment and its pod in qa's namespace, as a rollout leaves them.
  const ns = '/apis/apps/v1/namespaces/alpha-qa/deployments';
  api.objs.set(`${ns}/web`, { metadata: { name: 'web' }, spec: { replicas: 2, selector: { matchLabels: { app: 'web' } },
    template: { metadata: { labels: { app: 'web' } }, spec: { containers: [{ name: 'web', image: 'ghcr.io/owner/alpha:abc123def456' }] } } },
    status: { readyReplicas: 1 } });
  api.objs.set('/api/v1/namespaces/alpha-qa/pods/web-1', { metadata: { name: 'web-1', labels: { app: 'web' } }, spec: { nodeName: 'lab-1', containers: [{ name: 'web' }] },
    status: { phase: 'Running', containerStatuses: [{ ready: true, restartCount: 2 }] } });
  api.objs.set('/api/v1/namespaces/alpha-qa/services/web', { metadata: { name: 'web' }, spec: { selector: { app: 'web' }, ports: [{ port: 8080 }] } });
  api.logs.set('web-1', 'GET / 200\nGET /health 200\n');
  await page.evaluate(() => openNotebook('alpha', 'kubernetes'));
  await page.waitForSelector('.pane .nb .nbview[data-view="kubernetes"] details[data-sect="kb:qa"]', { timeout: 20000 });
  const sect = 'details[data-sect="kb:qa"]';
  const wl = await page.$eval(`${sect} .kbwl .row`, r => r.textContent.replace(/\s+/g, ' ').trim());
  const pod = await page.$eval(`${sect} .kbpods .row`, r => r.textContent.replace(/\s+/g, ' ').trim());
  const head = await page.$eval(`${sect} > summary`, s => s.textContent.replace(/\s+/g, ' ').trim());
  ok(/web/.test(wl) && /1 of 2/.test(wl) && /abc123def456/.test(wl) && /web:8080 inside the cluster/.test(wl) && /0 of 1 ready/.test(head),
     `a workload says ready of desired, its version and where it answers, and the section how many are ready (${head} | ${wl})`);
  ok(/web-1/.test(pod) && /Running/.test(pod) && /2/.test(pod) && /lab-1/.test(pod), `its pod says its state, restarts and node (${pod})`);
  const minted = [...api.deployers.values()];
  ok(minted.length && minted.every(n => n === 'alpha-qa') && !api.calls.some(c => /namespaces\/(?!alpha-qa)[^/]+\/(deployments|pods)/.test(c)),
     `read with a deployer token made for alpha-qa, asking nothing outside it (${minted.join(',')})`);
  page.answers.push({ index: 0, text: '3' });
  await page.click(`${sect} [data-kbscale^="qa:deployment:web"]`);
  const scaled = await until(() => api.objs.get(`${ns}/web`)?.spec?.replicas === 3, 10000, 200);
  ok(scaled, 'Scale asks how many and sets the replicas on the cluster');
  page.answers.push(0);
  await page.click(`${sect} [data-kbrestart="qa:deployment:web"]`);
  const restarted = await until(() => !!api.objs.get(`${ns}/web`)?.spec?.template?.metadata?.annotations?.['kubectl.kubernetes.io/restartedAt'], 10000, 200);
  ok(restarted && page.dialogs.some(d => /Restart web\?/.test(d)), 'Restart asks first, then marks the rollout as kubectl rollout restart does');
  await page.click(`${sect} [data-kblogs="qa:web-1"]`);
  const tab = await until(() => page.evaluate(() => tabs.some(t => t.arg === 'log:pod:alpha:qa:web-1' && t.label === 'Log: web-1')), 10000, 200);
  ok(tab, 'a pod\'s Logs opens a tab in the dock');
  const said = await until(() => api.calls.some(c => /\/pods\/web-1\/log\?/.test(c)), 10000, 200);
  const ended = await page.evaluate(() => [...TERMS.values()].find(r => r.t.arg === 'log:pod:alpha:qa:web-1')?.ended || '');
  ok(said && !ended, `its log is read through the deployer and followed (${ended})`);
  await page.evaluate(() => dropTab(tabs.find(t => t.arg === 'log:pod:alpha:qa:web-1').id));
  // A shell in the running pod: a dock tab, the controller the
  // cluster's client as its deployer, keys in and the pod's answer back.
  await page.click(`${sect} [data-kbshell="qa:web-1"]`);
  const opened = await until(() => page.evaluate(() => [...TERMS.values()].some(r => r.t.arg === 'pod:alpha:qa:web-1' && r.ws?.readyState === 1)), 15000, 200);
  await page.evaluate(() => { const r = [...TERMS.values()].find(r => r.t.arg === 'pod:alpha:qa:web-1'); termType(r, new TextEncoder().encode('ls\r')); });
  const echoed = await until(() => page.evaluate(() => {
    const r = [...TERMS.values()].find(r => r.t.arg === 'pod:alpha:qa:web-1');
    const b = r?.term?.buffer?.active; let t = '';
    for (let i = 0; b && i < b.length; i++) t += b.getLine(i)?.translateToString(true) + '\n';
    return /echo: ls/.test(t);
  }), 10000, 200);
  ok(opened && echoed && api.calls.some(c => /^EXEC .*\/namespaces\/alpha-qa\/pods\/web-1\/exec\?/.test(c)) && api.resizes.length > 0,
     `Shell opens a dock tab spliced to the pod's exec as its deployer, keys in and its answer on the screen (${api.calls.filter(c => /^EXEC/.test(c)).join(' ')})`);
  await page.evaluate(() => dropTab(tabs.find(t => t.arg === 'pod:alpha:qa:web-1').id));
  const other = await page.evaluate(() => new Promise(res => {
    const ws = new WebSocket(`${location.origin.replace(/^http/, 'ws')}/termws?arg=${encodeURIComponent('pod:alpha:qa:web-1:../x')}`);
    ws.onclose = e => res(e.reason); ws.onerror = () => {};
  }));
  ok(/not a pod's shell/.test(other), `a pod argument in any other shape is refused (${other})`);
  ok(page.errors.length === 0, `no console error through the view (${page.errors.slice(0, 2).join(' | ')})`);
});

await section("a session's aerie k8s: status at any dial, deploy under Deploy to Kubernetes, production always asked", async () => {
  const tok = execFileSync('bash', [`${REPO}/scripts/aerie`, 'users', 'token', 'alpha', 'test'],
    { encoding: 'utf8', env: { ...process.env, DASHBOARD_STATE: `${DIR}/state`, WORKSPACE: `${DIR}/ws` } }).trim();
  const S = asSession(tok);
  const st = await call('/api/k8s', { project: 'alpha', action: 'status', env: 'qa' }, S);
  ok(st.status === 200 && st.body.envs?.[0]?.workloads?.[0]?.name === 'web', `a session reads what runs in an environment (${JSON.stringify(st.body).slice(0, 120)})`);
  const lg = await call('/api/k8s', { project: 'alpha', action: 'logs', env: 'qa', pod: 'web-1' }, S);
  ok(/GET \/health 200/.test(lg.body.text || ''), 'and a pod\'s log');
  const denied = await call('/api/k8s', { project: 'alpha', action: 'deploy', env: 'qa', ref: 'HEAD', why: 'a fix' }, S);
  ok(denied.status === 403 && /Deploy to Kubernetes/.test(denied.body.error || ''), `at deny a session's deploy is refused, naming the setting (${denied.body.error})`);
  const other = await call('/api/k8s', { project: 'beta', action: 'status' }, S);
  ok(other.status === 403, `and another space's environments are not a session's to read (${other.body.error})`);
  await call('/api/prefs', { project: 'alpha', kube: 'ask' });
  const asked = await call('/api/k8s', { project: 'alpha', action: 'deploy', env: 'qa', ref: 'HEAD', why: 'the fix for testers' }, S);
  ok(asked.status === 200 && asked.body.id && !asked.body.job, `at ask it waits for a person on the bell (${JSON.stringify(asked.body).slice(0, 120)})`);
  const bell = await call('/api/phone');
  const row = (bell.body.asks || []).find(r => r.id === asked.body.id) || {};
  ok(row.kind === 'deploy' && row.env === 'qa' && row.ref === 'HEAD', `the bell's row names the environment and the ref (${JSON.stringify(row).slice(0, 160)})`);
  await call('/api/phone', { action: 'deny', id: asked.body.id });
  await call('/api/prefs', { project: 'alpha', kube: 'auto' });
  const cl = await page.evaluate(async () => ((await getJSON('/api/clusters')).clusters || [])[0]?.id);
  await page.evaluate(c => postJSON('/api/deploy', { project: 'alpha', action: 'save', was: 'qa',
    env: { name: 'qa', cluster: c, namespace: 'alpha-qa', registry: '', when: 'hand', production: true } }), cl);
  const prod = await call('/api/k8s', { project: 'alpha', action: 'deploy', env: 'qa', ref: 'HEAD', why: 'the release' }, S);
  ok(prod.status === 200 && prod.body.id && !prod.body.job, `an environment marked production asks a person even at auto (${JSON.stringify(prod.body).slice(0, 120)})`);
  await call('/api/phone', { action: 'deny', id: prod.body.id });
  await call('/api/prefs', { project: 'alpha', kube: 'deny' });
});

await section("Home's clusters tile and the bell's row for an environment that is not healthy", async () => {
  // Step 7. The stub cluster has two nodes, one of them not ready.
  const home = await call('/api/home');
  ok(home.body.clusters?.all === 1 && home.body.clusters?.ready === 0, `Home counts the clusters kept and how many are ready (${JSON.stringify(home.body.clusters)})`);
  const tile = await page.evaluate(() => { homeData = {...(homeData || {}), clusters: {ready: 0, all: 1}};
    const t = homeTiles().find(x => x.key === 'clusters'); return t && `${t.value} ${t.label} ${t.sub} ${t.tone} ${homeHref('clusters')}`; });
  ok(tile === '0 clusters ready of 1 kept warn #/machines/clusters', `its tile says so, in the warn tone, and opens the Clusters page (${tile})`);
  const row = await page.evaluate(() => attRow({kind: 'deploy', space: 'alpha', env: 'qa', repo: 'alpha', active: true, why: 'web: CrashLoopBackOff', at: Date.now() / 1000 - 120}));
  ok(/qa in alpha is not healthy/.test(row) && /CrashLoopBackOff/.test(row) && /data-bkube="alpha"/.test(row) && !/data-bdismiss/.test(row),
     'the bell\'s row names the environment and what is stuck, opens the Kubernetes view, and has no Dismiss: it leaves when it recovers');
});

api.close();
await done(browser);
