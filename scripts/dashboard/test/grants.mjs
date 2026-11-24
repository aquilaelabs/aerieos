// What a role grants, held at every door the audit of 24 Nov found open
// (R277, the operator: "there's been a lot of changes and I'm worried it's
// drifted"). Each account here holds one grant, and each knocks at a door a
// grant somewhere else used to open: a role on one space reaching a node's
// services, every container, another space's notebook or a space's router
// key; Accounts Write making an administrator; an administrator taking the
// owner's account; a session going on after its account went.
import { URL, ok, done, launch, asUser, call, mint, section } from './lib.mjs';

const browser = await launch();
const api = async (path, body, h) => (await call(path, body, h)).body;
const stamp = Date.now().toString(36).slice(-5);
const ALPHA = 'alpha';

// The roles: Containers Write on a space, and Accounts Write everywhere.
await api('/api/roles', { action: 'set', name: `box ${stamp}`, scope: 'projects', perms: { containers: 'write' } });
await api('/api/roles', { action: 'set', name: `people ${stamp}`, scope: 'global', perms: { accounts: 'write' } });
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

await section("a role reads only what its areas say", async () => {
  const key = await call(`/api/router-key?project=${ALPHA}`, undefined, boxer);
  const notes = await call(`/api/roadmap?project=${ALPHA}`, undefined, boxer);
  ok(key.status === 403 && notes.status === 403,
     `Containers on alpha is not alpha's router key (Spaces Write) nor its notebook (Spaces Read) (${key.status}, ${notes.status})`);
  const trash = await call('/api/trash', undefined, boxer);
  ok(trash.status === 403, `...nor its bin, which is Space settings Write (${trash.status})`);
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
for (const n of [`box ${stamp}`, `people ${stamp}`]) await api('/api/roles', { action: 'remove', name: n });
await done(browser);
