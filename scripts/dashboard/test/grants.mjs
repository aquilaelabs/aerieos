// What a role grants, held at every door the audit of 24 Nov found open
// (R277, the operator: "there's been a lot of changes and I'm worried it's
// drifted"). Each account here holds one grant, and each knocks at a door a
// grant somewhere else used to open: a role on one space reaching a node's
// services, every container, another space's notebook or a space's router
// key; Accounts Write making an administrator; an administrator taking the
// owner's account; a session going on after its account went.
import { URL, ok, done, launch, asUser, call, mint, section, newPage, ready } from './lib.mjs';

const browser = await launch();
const api = async (path, body, h) => (await call(path, body, h)).body;
const stamp = Date.now().toString(36).slice(-5);
const ALPHA = 'alpha';

// The roles: Containers Write on a space, and Accounts Write everywhere.
await api('/api/roles', { action: 'set', name: `box ${stamp}`, scope: 'projects', perms: { containers: 'write' } });
await api('/api/roles', { action: 'set', name: `people ${stamp}`, scope: 'global', perms: { accounts: 'write' } });
await api('/api/roles', { action: 'set', name: `maker ${stamp}`, scope: 'global', perms: { newprojects: 'write' } });
await api('/api/roles', { action: 'set', name: `cfgread ${stamp}`, scope: 'global', perms: { configure: 'read' } });
await api('/api/roles', { action: 'set', name: `shell ${stamp}`, scope: 'projects', perms: { projects: 'read', terminal: 'write' } });
const made = [];
const account = async (name, pw, extra) => {
  await api('/api/users', { action: 'add', name, password: pw, role: extra?.role || 'user' });
  made.push(name);
  if (extra?.assign) await api('/api/roles', { action: 'assign', name, ...extra.assign });
  return asUser(name, pw);
};
const boxer = await account(`box${stamp}`, 'box-pass-word-1', { assign: { project_roles: { [ALPHA]: [`box ${stamp}`] } } });
const hr = await account(`hr${stamp}`, 'hr-pass-word-1', { assign: { roles: [`people ${stamp}`] } });
const adm = await account(`adm${stamp}`, 'adm-pass-word-1', { role: 'admin' });
const cfgReader = await account(`cr${stamp}`, 'cr-pass-word-1', { assign: { roles: [`cfgread ${stamp}`] } });
const maker = await account(`mk${stamp}`, 'mk-pass-word-1',
  { assign: { roles: [`maker ${stamp}`], project_roles: { [ALPHA]: [`box ${stamp}`] } } });
const sheller = await account(`sh${stamp}`, 'sh-pass-word-1', { assign: { project_roles: { [ALPHA]: [`shell ${stamp}`] } } });
// An author, without which no shell opens for anybody.
await api('/api/users', { action: 'edit', name: `sh${stamp}`, profile: { full_name: 'Shell Holder', email: 'sh@example.invalid' } });
const node = ((await api('/api/v1/nodes')).nodes || []).find(n => n.kind === 'agent' || n.id)?.id || 'local';
// No node: the Containers page's own daemon, which a prune would reach.
const dnode = '';

await section("a role on one space reaches no node's services", async () => {
  const said = [];
  for (const [path, body] of [['/api/nginx', { action: 'deploy', node }], ['/api/router', { action: 'deploy', node }],
                              ['/api/scanners', { action: 'deploy', node }], ['/api/scanners', { action: 'deploy-all' }],
                              ['/api/dockerctl', { action: 'prune', node: dnode }]]){
    const r = await call(path, body, boxer);
    said.push({ what: `${path} ${body.action}`, status: r.status, ok: !!r.body?.ok });
  }
  // The services refused by their own gate; a prune refused before it can
  // reach a daemon (this account's spaces build on no node) or by its gate.
  const svc = said.filter(s => !/prune/.test(s.what)), prune = said.find(s => /prune/.test(s.what));
  ok(svc.every(s => s.status === 403) && prune.status >= 400 && !prune.ok,
     `Containers Write on alpha deploys no node's nginx, router or scanners and prunes no node (${said.map(s => `${s.what}: ${s.status}`).join('; ')})`);
});

await section("a node's services read without Configure Write are drawn without their controls", async () => {
  const view = await call('/api/scanners', undefined, cfgReader);
  const rows = view.body.nodes || [];
  ok(view.status === 200 && rows.length && rows.every(n => n.may === 'read') && view.body.may_all === false,
     `Configure Read reads every node's scanners, each read only (${view.status}, ${rows.map(n => n.may).join(',')}, may_all ${view.body.may_all})`);
  const dep = await call('/api/scanners', { action: 'deploy', node: rows[0]?.node || node }, cfgReader);
  ok(dep.status === 403, `...and deploys them nowhere (${dep.status})`);
  const page = await newPage(browser, { viewport: { width: 1280, height: 1000 },
    httpCredentials: { username: `cr${stamp}`, password: 'cr-pass-word-1' }, extraHTTPHeaders: { Authorization: cfgReader.Authorization } });
  await page.goto(URL); await ready(page);
  await page.evaluate(() => openScannersTab());
  await page.waitForSelector('.scannerstab .svcro', { timeout: 20000 });
  const seen = await page.evaluate(() => {
    const root = document.querySelector('.pane .doc.on .scannerstab') || document.querySelector('.scannerstab');
    const live = [...root.querySelectorAll('button')].filter(b => b.offsetParent !== null && !b.closest('.dochead, .sechead, summary, .docsect > .sh'));
    return { live: live.map(b => b.textContent.trim()), said: /read only/.test(root.textContent) };
  });
  ok(seen.said && !seen.live.some(w => /Deploy|Run now|Update|Remove|Turn (on|off)|Save timetable/.test(w)),
     `the Scanners page says it is read only and draws no Deploy, Run now, Update, Remove or timetable control (${JSON.stringify(seen)})`);
  await page.context().close();
});

await section("a role reads only what its areas say", async () => {
  const key = await call(`/api/router-key?project=${ALPHA}`, undefined, boxer);
  const notes = await call(`/api/roadmap?project=${ALPHA}`, undefined, boxer);
  ok(key.status === 403 && notes.status === 403,
     `Containers on alpha is not alpha's router key (Spaces Write) nor its notebook (Spaces Read) (${key.status}, ${notes.status})`);
  const trash = await call('/api/trash', undefined, boxer);
  ok(trash.status === 403, `...nor its bin, which is Space settings Write (${trash.status})`);
});

await section("a shell on one space is no shell on every space", async () => {
  // Terminal Write on alpha opens a shell in alpha's tree; one at
  // /workspace, on no space, reaches every space's trees and asks it
  // Everywhere, so the dock draws no + for it.
  const can = (await call('/api/status', undefined, sheller)).body.can || {};
  const bare = await call('/termws?arg=sh%3A1%3A', undefined, sheller);
  const there = await call(`/termws?arg=sh%3A1%3A${ALPHA}`, undefined, sheller);
  ok(can.terminal === true && can['terminal-any'] === false && bare.status === 403
     && /a shell needs Terminal Write Everywhere/.test(bare.body.error || '') && there.status !== 403,
     `Terminal Write on alpha is a shell there and none on no space (can ${can.terminal}/${can['terminal-any']}; ${bare.status} ${bare.body.error || ''}; alpha ${there.status})`);
  const page = await newPage(browser, { viewport: { width: 1280, height: 900 },
    httpCredentials: { username: `sh${stamp}`, password: 'sh-pass-word-1' }, extraHTTPHeaders: { Authorization: sheller.Authorization } });
  await page.goto(URL); await ready(page);
  await page.waitForSelector('.dockline .dtab', { timeout: 15000 }).catch(() => {});
  const dock = await page.evaluate(() => ({ line: !!document.querySelector('.dockline .dtab'), plus: !!document.querySelector('[data-dnew]') }));
  ok(dock.line && !dock.plus, `the dock draws no new shell at /workspace for it (${JSON.stringify(dock)})`);
  await page.context().close();
});

await section("a repository is added to a space by its owner or an administrator", async () => {
  // New spaces Write, and on alpha, but not alpha's owner. A repository is
  // added into its space, named by the space's key.
  const repos = (await api('/api/status')).repos || {};
  const space = Object.keys(repos).find(k => (repos[k].members || []).includes(ALPHA)) || ALPHA;
  const r = await call('/api/create', { project: space, name: `rep${stamp}` }, maker);
  ok(r.status === 403 && /owner or an administrator/.test(r.body.error || ''),
     `New spaces Write and a place on alpha add no repository to it (${r.status} ${r.body.error})`);
});

await section("Accounts Write gives no administrator and an administrator no owner's account", async () => {
  const self = await call('/api/users', { action: 'edit', name: `hr${stamp}`, role: 'admin' }, hr);
  const made = await call('/api/users', { action: 'add', name: `x${stamp}`, password: 'x-pass-word-1', role: 'admin' }, hr);
  ok(self.status >= 400 && made.status >= 400 && /administrator/.test(self.body.error || ''),
     `Accounts Write neither makes itself an administrator nor adds one (${self.status} ${self.body.error}; ${made.status})`);
  const ownerName = ((await api('/api/roles')).people || []).find(p => p.role === 'owner')?.name || 'test';
  const pw = await call('/api/users', { action: 'edit', name: ownerName, password: 'taken-over-1' }, adm);
  ok(pw.status >= 400 && /owner/.test(pw.body.error || ''), `an administrator changes nothing of the owner's account (${pw.status} ${pw.body.error})`);
});

await section("a session goes when its account goes", async () => {
  const tok = mint(ALPHA, `box${stamp}`);
  const before = await call(`/api/roadmap?project=${ALPHA}`, undefined, { Authorization: `Bearer ${tok}` });
  await api('/api/users', { action: 'remove', name: `box${stamp}` });
  made.splice(made.indexOf(`box${stamp}`), 1);
  const after = await call(`/api/roadmap?project=${ALPHA}`, undefined, { Authorization: `Bearer ${tok}` });
  ok(after.status === 401 || after.status === 403, `a session's token is no token once its account is removed (${before.status} before, ${after.status} after)`);
});

for (const n of made) await api('/api/users', { action: 'remove', name: n });
for (const n of [`box ${stamp}`, `people ${stamp}`, `maker ${stamp}`, `cfgread ${stamp}`, `shell ${stamp}`]) await api('/api/roles', { action: 'remove', name: n });
await done(browser);
