// A person's editor on a project's files: the controller's Files API
// and the VS Code extension in apps/vscode/, which signs in as the person and can
// do nothing their account cannot. Every check here is the SERVER's answer
// for an account: with read and write, read only, no access, not on the
// project, a role that caps it at read, the editor's switch off, a session's
// token, taken off the project or signed out partway. Then the extension's
// own code, driven under a stand-in for VS Code's API against this server,
// and its terminal, AerieOS's own on /termws.
// No browser.
import { ok, done, sleep, until, DIR, URL, OWNER, OWNER as ADMIN, asSession, section, REPO, aerie } from './lib.mjs';
import { execFileSync } from 'node:child_process';
import { readFileSync, writeFileSync, mkdirSync, symlinkSync, existsSync, statSync, utimesSync } from 'node:fs';
import { createRequire } from 'node:module';
import Module from 'node:module';

const require = createRequire(import.meta.url);
const { Client, Refused, signIn, API } = require(`${REPO}/apps/vscode/lib/client.js`);
const { Term } = require(`${REPO}/apps/vscode/lib/term.js`);
const base = URL.replace(/\/$/, '');
const admin = async (path, body) => {
  const r = await fetch(base + path, { method: 'POST', headers: ADMIN, body: JSON.stringify(body) });
  return { status: r.status, ...(await r.json().catch(() => ({}))) };
};
const env = { ...process.env, DASHBOARD_STATE: `${DIR}/state`, WORKSPACE: `${DIR}/ws` };
const addUser = (name, pw) => aerie(['users', 'add', name, '--role', 'user'],
  { input: `${pw}\n${pw}\n`, env });
const uidOf = n => JSON.parse(readFileSync(`${DIR}/state/users.json`, 'utf8')).users[n].uid;
const tree = `${DIR}/ws/alpha`;
// The answer to one call: its status and words, never a throw.
const as = async (c, project, action, extra = {}) => {
  try { return { status: 200, ...(await c.files(project, action, extra)) }; }
  catch (e) { return { status: e.status || 0, error: e.message }; }
};

// ---- accounts, and what alpha's settings give each ----------------------------
const people = { 'ed.rw': 'edrwpass1', 'ed.r': 'edrpass12', 'ed.none': 'ednonepass1', 'ed.out': 'edoutpass1', 'ed.cap': 'edcappass1',
                 'ed.mem': 'edmempass1' };
for (const [n, pw] of Object.entries(people)) addUser(n, pw);
for (const n of ['ed.rw', 'ed.r', 'ed.none', 'ed.cap', 'ed.mem'])
  await admin('/api/users', { action: 'edit', name: n, projects: ['alpha'] });
// Each holds a role on alpha that gives the files area write, but ed.cap's
// gives read: its rw in the settings is capped at r by the role.
await admin('/api/roles', { action: 'set', name: 'ed-files-w', scope: 'projects',
  perms: { projects: 'write', files: 'write' } });
await admin('/api/roles', { action: 'set', name: 'ed-files-r', scope: 'projects',
  perms: { projects: 'write', files: 'read' } });
// ed.none is on alpha with a role that gives no File access; ed.mem is on it
// with File access and no choice of its own on alpha's list, which is enough: being on the project is what lets a person's editor in.
await admin('/api/roles', { action: 'set', name: 'ed-nofiles', scope: 'projects', perms: { projects: 'write' } });
for (const n of ['ed.rw', 'ed.r', 'ed.mem'])
  await admin('/api/roles', { action: 'assign', name: n, project_roles: { alpha: ['ed-files-w'] } });
await admin('/api/roles', { action: 'assign', name: 'ed.none', project_roles: { alpha: ['ed-nofiles'] } });
await admin('/api/roles', { action: 'assign', name: 'ed.cap', project_roles: { alpha: ['ed-files-r'] } });
const set = await admin('/api/project-ftp', { action: 'set', project: 'alpha', editor: true,
  access: { [uidOf('ed.rw')]: 'rw', [uidOf('ed.r')]: 'r', [uidOf('ed.cap')]: 'rw' } });
ok(!set.error && set.editor === true && set.on === false,
   `alpha's File access opens it in an editor with FTPS left off: a door of its own (${JSON.stringify({ editor: set.editor, on: set.on })})`);

writeFileSync(`${tree}/editor-probe.txt`, 'first line\nneedle in a haystack\n');
mkdirSync(`${tree}/.git`, { recursive: true });
writeFileSync(`${tree}/.git/config`, '[remote "origin"]\n  url = https://x:ghp_secret@example.com/r.git\n');
try { symlinkSync('../beta', `${tree}/editor-escape`); } catch {}

const cookie = {};
for (const [n, pw] of Object.entries(people)) cookie[n] = await signIn(base, n, pw);
const c = Object.fromEntries(Object.keys(people).map(n => [n, new Client(base, cookie[n])]));
await section("the extension signs in as the person, with the cookie the dashboard would give, and a wron", async () => {
  let wrong = null;
  try { await signIn(base, 'ed.rw', 'not-the-password'); } catch (e) { wrong = e; }
  ok(Object.values(cookie).every(Boolean) && wrong instanceof Refused && /Wrong username or password/.test(wrong.message),
     'the extension signs in as the person, with the cookie the dashboard would give, and a wrong password is refused');
});

// ---- which projects each may open ------------------------------------------------
await section("which projects each may open", async () => {
  const mine = {};
  for (const n of Object.keys(people)) mine[n] = (await c[n].projects()).projects;
  const acc = n => (mine[n].find(p => p.name === 'alpha') || {}).access || '';
  ok(acc('ed.rw') === 'rw' && acc('ed.r') === 'r' && acc('ed.cap') === 'r' && acc('ed.none') === '' && acc('ed.out') === ''
     && acc('ed.mem') === 'rw'
     && (await c['ed.rw'].projects()).api === API,
     `each is offered alpha exactly as far as the settings and roles give: rw, r, r capped by a role, none, not on it, and on it with no choice made (${
       Object.keys(people).map(n => `${n}=${acc(n) || '-'}`).join(' ')})`);
});

// ---- reading and writing, as each ----------------------------------------------------
await section("reading and writing, as each", async () => {
  const read = {};
  for (const n of Object.keys(people)) read[n] = await as(c[n], 'alpha', 'read', { path: 'editor-probe.txt' });
  ok(read['ed.rw'].data && read['ed.r'].data && read['ed.cap'].data
     && read['ed.none'].status === 403 && /no file access/.test(read['ed.none'].error)
     && read['ed.out'].status === 400 && /not a space/.test(read['ed.out'].error),
     `a read is the server's to allow: rw, r and the capped read; no access is refused with why, and a space not theirs is not one (${
       read['ed.none'].error} | ${read['ed.out'].error})`);
  const data = Buffer.from('written from an editor\n').toString('base64');
  const w = {};
  for (const n of ['ed.rw', 'ed.r', 'ed.cap'])
    w[n] = await as(c[n], 'alpha', 'write', { path: 'editor-probe.txt', data, overwrite: true });
  ok(w['ed.rw'].ok && readFileSync(`${tree}/editor-probe.txt`, 'utf8') === 'written from an editor\n'
     && w['ed.r'].status === 403 && /read-only/.test(w['ed.r'].error) && w['ed.cap'].status === 403,
     `a write needs read and write: it lands for ed.rw, and read-only and the role-capped account are refused (${w['ed.r'].error})`);
  // A project locked against an account is read-only through this door
  // too, as it is on the page: the lock is the owner's or an
  // administrator's, and ed.rw is neither.
  const lk = await admin('/api/lock', { name: 'alpha', locked: true });
  const held = await as(c['ed.rw'], 'alpha', 'write', { path: 'editor-probe.txt', data, overwrite: true });
  await admin('/api/lock', { name: 'alpha', locked: false });
  ok(!lk.error && held.status === 403 && /read-only/.test(held.error || ''),
     `a locked space refuses ed.rw's write through the Files API (${held.error || JSON.stringify(lk)})`);
  const st = await as(c['ed.r'], 'alpha', 'stat', { path: 'editor-probe.txt' });
  ok(st.readonly === true && (await as(c['ed.rw'], 'alpha', 'stat', { path: '' })).readonly === false,
     '...and stat tells the editor which, so a read-only space opens read-only');
  const rows = execFileSync('python3', ['-c', `
import sqlite3, sys
db = sqlite3.connect(sys.argv[1])
print("\\n".join(f"{p} {a} {t}" for p, a, t in db.execute("SELECT principal, action, target FROM audit WHERE action LIKE 'files-%'")))`,
    `${DIR}/state/builderbot.db`], { encoding: 'utf8' });
  ok(/user:ed\.rw files-write alpha:editor-probe\.txt/.test(rows) && !/ed\.r files-write/.test(rows),
     `every change is on the audit trail under the person's name, and a refused one is not (${rows.trim().split('\n')[0]})`);
});

// ---- what is never served -----------------------------------------------------------
await section("what is never served", async () => {
  const rw = c['ed.rw'];
  const up = await as(rw, 'alpha', 'read', { path: '../beta/README.md' });
  const git = await as(rw, 'alpha', 'read', { path: '.git/config' });
  const link = await as(rw, 'alpha', 'list', { path: 'editor-escape' });
  const listed = await as(rw, 'alpha', 'list', { path: '' });
  ok(up.status === 400 && git.status === 403 && link.status === 403 && !listed.entries.some(([n]) => n === '.git'),
     `a path out of the space, through .git or through a symlink leading out is refused, and .git is never listed (${
       up.status} ${git.status} ${link.status})`);
  const tok = execFileSync('bash', [`${REPO}/scripts/aerie`, 'users', 'token', 'alpha', 'test'], { encoding: 'utf8', env }).trim();
  const r = await fetch(base + '/api/v1/files', { method: 'POST', body: JSON.stringify({ action: 'list', project: 'alpha', path: '' }),
    headers: asSession(tok) });
  ok(r.status === 403, `a session's token is refused: a session has the tree, and is never a person (${r.status})`);
});

// ---- a save over a newer file, search, and changes as they happen --------------------
await section("a save over a newer file, search, and changes as they happen", async () => {
  const rw = c['ed.rw'];
  const first = await as(rw, 'alpha', 'read', { path: 'editor-probe.txt' });
  writeFileSync(`${tree}/editor-probe.txt`, 'Claude saved this meanwhile\nneedle\n');
  utimesSync(`${tree}/editor-probe.txt`, new Date(), new Date(Date.now() + 5000));
  const late = await as(rw, 'alpha', 'write', { path: 'editor-probe.txt', overwrite: true, mtime: first.mtime,
    data: Buffer.from('mine').toString('base64') });
  ok(late.status === 409 && /changed on the controller/.test(late.error)
     && readFileSync(`${tree}/editor-probe.txt`, 'utf8').startsWith('Claude saved'),
     `a save over a file changed since it was read is refused, and what was saved meanwhile stays (${late.error})`);
  const found = await as(c['ed.r'], 'alpha', 'search', { query: 'needle' });
  const none = await as(c['ed.none'], 'alpha', 'search', { query: 'needle' });
  ok(found.matches?.some(m => m.path === 'editor-probe.txt' && m.line === 2) && none.status === 403
     && !found.matches.some(m => m.path.startsWith('.git')),
     `search finds a line across the tree for an account that may read it, never in .git, and not for one that may not (${found.matches?.length} matches)`);
  const start = await as(c['ed.r'], 'alpha', 'changes', { since: 0 });
  const waiting = as(c['ed.r'], 'alpha', 'changes', { since: start.rev, wait: 15 });
  // Time for the ask to reach the server and be waiting there before the
  // file is written: nothing outside the server says that it is.
  await sleep(500);
  writeFileSync(`${tree}/claude-wrote-this.txt`, 'new\n');
  const t0 = Date.now();
  const got = await waiting;
  ok(got.changes?.some(x => x.path === 'claude-wrote-this.txt' && x.type === 'created') && Date.now() - t0 < 8000,
     `a file a session writes is told to a waiting editor within seconds (${JSON.stringify(got.changes)} in ${Date.now() - t0} ms)`);
});

// ---- access taken away, partway --------------------------------------------------------
await section("access taken away, partway", async () => {
  await admin('/api/roles', { action: 'assign', name: 'ed.r', project_roles: { alpha: ['ed-nofiles'] } });
  const gone = await as(c['ed.r'], 'alpha', 'read', { path: 'editor-probe.txt' });
  await admin('/api/users', { action: 'edit', name: 'ed.cap', projects: [] });
  const off = await as(c['ed.cap'], 'alpha', 'list', { path: '' });
  await admin('/api/project-ftp', { action: 'set', project: 'alpha', editor: false });
  const shut = await as(c['ed.rw'], 'alpha', 'list', { path: '' });
  await admin('/api/project-ftp', { action: 'set', project: 'alpha', editor: true });
  ok(gone.status === 403 && off.status === 400 && shut.status === 403 && /off in its settings/.test(shut.error),
     `access taken away holds on the next request with the same sign-in: the role's File access, the space, the editor's switch (${gone.status} ${off.status} ${shut.status})`);
  execFileSync('bash', [`${REPO}/scripts/aerie`, 'users', 'passwd', 'ed.rw'], { input: 'edrwpass2\nedrwpass2\n', encoding: 'utf8', env });
  const out = await as(c['ed.rw'], 'alpha', 'list', { path: '' });
  ok(out.status === 401 && /Sign In/.test(out.error), `...and a password change signs the extension out (${out.status}: ${out.error})`);
  cookie['ed.rw'] = await signIn(base, 'ed.rw', 'edrwpass2');
  c['ed.rw'] = new Client(base, cookie['ed.rw']);
});

// ---- the extension itself, under a stand-in for VS Code -------------------------------
// The parts of VS Code's API it uses, enough to drive its file system as
// VS Code would: activate, register, stat, read, write, watch.
await section("the extension itself, under a stand-in for VS Code", async () => {
  const fired = [];
  class Emitter { constructor() { this.subs = []; this.event = f => { this.subs.push(f); return { dispose() {} }; }; }
    fire(x) { fired.push(x); this.subs.forEach(f => f(x)); } }
  const settings = { url: base, allowSelfSignedCertificate: false };
  const secrets = new Map([[`aerieos.cookie:${base}`, cookie['ed.rw']]]);
  let provider = null;
  class FsErr extends Error {}
  const vscode = {
    EventEmitter: Emitter,
    Disposable: class { constructor(f) { this.dispose = f; } },
    FileType: { File: 1, Directory: 2 },
    FilePermission: { Readonly: 1 },
    FileChangeType: { Changed: 1, Created: 2, Deleted: 3 },
    FileSystemError: { FileNotFound: u => new FsErr(`notfound ${u}`), FileExists: u => new FsErr(`exists ${u}`),
                       NoPermissions: m => new FsErr(`noperm ${m}`), Unavailable: m => new FsErr(`unavailable ${m}`) },
    Uri: { from: o => ({ ...o, toString() { return `${o.scheme}://${o.authority}${o.path}`; } }) },
    ConfigurationTarget: { Global: 1 },
    workspace: {
      getConfiguration: () => ({ get: k => settings[k], update: async (k, v) => { settings[k] = v; } }),
      registerFileSystemProvider: (s, p) => { provider = p; return { dispose() {} }; },
      onDidChangeConfiguration: () => ({ dispose() {} }),
      workspaceFolders: [],
    },
    window: { showWarningMessage() {}, showErrorMessage: m => errors.push(m), showInformationMessage() {},
              showInputBox: async () => 'again', showQuickPick: async items => items.find(i => i.project === 'alpha') || items[0],
              showTextDocument: async u => { const ed = { uri: u, revealRange: r => { ed.revealed = r; } }; opened.push(ed); return ed; } },
    Position: class { constructor(l, c) { this.line = l; this.character = c; } translate(dl, dc) { return new vscode.Position(this.line + dl, this.character + dc); } },
    Selection: class { constructor(a, b) { this.anchor = a; this.active = b; } },
    Range: class { constructor(a, b) { this.start = a; this.end = b; } },
    commands: { registerCommand: (id, f) => { commands[id] = f; return { dispose() {} }; } },
  };
  const commands = {}, opened = [], errors = [];
  const load = Module._load;
  Module._load = function (req, ...rest) { return req === 'vscode' ? vscode : load.call(this, req, ...rest); };
  const ext = require(`${REPO}/apps/vscode/extension.js`);
  Module._load = load;
  ext.activate({ subscriptions: [], secrets: { get: async k => secrets.get(k), store: async (k, v) => secrets.set(k, v),
                                                delete: async k => secrets.delete(k) } });
  // Any coding agent's session terminal: its argument is the page's.
  ok(ext.AGENTS.map(a => a.id).join() === 'claude,codex,copilot,grok,open' && ext.sessionArg('codex', 'alpha') === 'codex:alpha'
     && ext.sessionArg('grok', 'alpha') === 'grok:alpha'
     && ext.sessionArg('copilot', 'alpha') === 'copilot:alpha' && ext.sessionArg('nope', 'alpha') === 'claude:alpha'
     && ext.sessionArg('codex', 'alpha', '17.5') === 'codex:alpha:b:17.5',
     'the extension opens any live agent\'s session, by the argument the dashboard opens it with');
  const uri = path => vscode.Uri.from({ scheme: 'aerieos', path: '/alpha' + path });
  const dir = await provider.readDirectory(uri('/'));
  const text = Buffer.from(await provider.readFile(uri('/editor-probe.txt'))).toString();
  const s = await provider.stat(uri('/editor-probe.txt'));
  ok(dir.some(([n, t]) => n === 'editor-probe.txt' && t === 1) && !dir.some(([n]) => n === '.git')
     && /Claude saved/.test(text) && s.type === 1 && !s.permissions,
     `the extension's file system lists, reads and stats a space as VS Code asks it to (${dir.length} entries)`);
  await provider.writeFile(uri('/from-vscode.txt'), Buffer.from('saved in VS Code\n'), { create: true, overwrite: false });
  ok(readFileSync(`${tree}/from-vscode.txt`, 'utf8') === 'saved in VS Code\n', '...and a save lands in the project\'s tree');
  writeFileSync(`${tree}/editor-probe.txt`, 'Claude again\n');
  utimesSync(`${tree}/editor-probe.txt`, new Date(), new Date(Date.now() + 9000));
  let refused = null;
  try { await provider.writeFile(uri('/editor-probe.txt'), Buffer.from('stale'), { create: false, overwrite: true }); }
  catch (e) { refused = e; }
  ok(refused && /changed on the controller/.test(refused.message) && readFileSync(`${tree}/editor-probe.txt`, 'utf8') === 'Claude again\n',
     `...a save over a file Claude changed since it was opened is refused, keeping Claude's (${refused?.message})`);
  await commands['aerieos.search']();
  const ed = opened[0];
  ok(!errors.length && ed && /^\/alpha\//.test(ed.uri.path) && ed.selection?.active.character - ed.selection?.anchor.character === 'again'.length,
     `...Search Space Files opens the match it picked with the word selected (${errors[0] || ed?.uri.path})`);
  // The watch follows from the revision its first answer gives: in hand
  // once it asks again, which is the ask that waits.
  const filesWas = Client.prototype.files;
  let following = false;
  Client.prototype.files = function (project, action, extra = {}) {
    if (action === 'changes' && extra.wait) following = true;
    return filesWas.call(this, project, action, extra);
  };
  const w = provider.watch(uri('/'), { recursive: true, excludes: [] });
  await until(() => following, 15000);
  Client.prototype.files = filesWas;
  writeFileSync(`${tree}/watched.txt`, 'appears\n');
  const t0 = Date.now();
  await until(() => fired.flat().some(e => e.uri?.path === '/alpha/watched.txt'), 12000, 200);
  w.dispose();
  ok(fired.flat().some(e => e.uri?.path === '/alpha/watched.txt' && e.type === 2),
     `...and a file a session writes is told to VS Code as created, for open editors to follow (${Date.now() - t0} ms)`);
});

// ---- the session's terminal, AerieOS's own ---------------------------------
await section("the session's terminal, AerieOS's own", async () => {
  // Opened, written to and ended through the extension's own client; the
  // reason a terminal ends with, a refusal among them, is what it closes on.
  // With something to type, the shell's prompt is waited for, then `want`
  // in what it prints; with nothing, the reason the server ends it with.
  const run = async (who, arg, type, want) => {
    const t = new Term(who, arg);
    let out = '', why = null;
    t.on('output', s => { out += s; });
    t.on('close', w => { why = w; });
    await t.open(90, 20);
    await until(() => why !== null || (type && /[$#]/.test(out.replace(/\x1b\[[0-9;?]*[a-zA-Z]/g, ''))), 15000);
    if (type && why === null) {
      t.write(type);
      await until(() => why !== null || !want || want.test(out.replace(/\x1b\[[0-9;?]*[a-zA-Z]/g, '').replace(/\s+/g, ' ')), 15000);
    }
    t.close();
    await until(() => why !== null);
    return { out: out.replace(/\x1b\[[0-9;?]*[a-zA-Z]/g, '').replace(/\s+/g, ' '), why };
  };
  const owner = new Client(base, await signIn(base, 'test', 'test'));
  const sh = await run(owner, 'sh:1:alpha', 'echo walk-$((6*7))\r', /walk-42/);
  ok(/walk-42/.test(sh.out),
     `the terminal is the dashboard's, and what is typed runs (${sh.out.slice(-80)})`);
  // Another agent's session as Open Agent Session opens it: the
  // argument names the agent and carries the boot the status gives, which
  // is what lets bb-tty start one that is not running. The fixture has no
  // node, so the server takes it as an agent's session and says there is
  // nowhere to run one.
  {
    const ext = require(`${REPO}/apps/vscode/extension.js`);
    const facts = await ext.sessionFacts(owner, 'alpha');
    const ag = await run(owner, ext.sessionArg('codex', 'alpha', facts.boot));
    ok(typeof facts.boot === 'string' && facts.boot && facts.running instanceof Set
       && /no node to run/.test(ag.why || ''),
       `...and the extension asks the boot a new session needs and opens a ChatGPT one as an agent's (${
         facts.boot}: ${String(ag.why).slice(0, 80)})`);
  }
  // The page the Android app's WebView and a popped-out tab load: the same
  // terminal, on /termws, behind the same sign-in.
  {
    const auth = OWNER;
    const page = await fetch(`${base}/terminal?arg=sh%3A1%3Aalpha`, { headers: auth });
    const body = await page.text();
    const anon = await fetch(`${base}/terminal?arg=sh%3A1%3Aalpha`, { redirect: 'manual' });
    ok(page.status === 200 && /\/termws\?/.test(body) && /vendor\/xterm\.js/.test(body) && anon.status !== 200,
       `...and /terminal is that terminal on a page of its own, for the app and a popped-out tab, behind the sign-in (${
         page.status}, signed out ${anon.status})`);
  }
  const no = await run(c['ed.out'], 'sh:1:alpha');
  ok(no.why, `...and the same server refuses a terminal the account may not open, saying why (${String(no.why).slice(0, 80)})`);
});

// Under a controller's own certificate, which no authority signed: the
// extension took any certificate at all, and sent the person's name and
// password to whoever answered (review of 22 Nov). Now the key is pinned at
// the first sign-in, as a node's agent and the Windows companion pin it,
// and nothing is sent on a connection under another key.
await section("under the controller's own certificate the extension holds the key it pinned", async () => {
  const https = require('node:https');
  const crypto = require('node:crypto');
  const { KEY_PIN } = require(`${REPO}/apps/vscode/lib/client.js`);
  const dir = `${DIR}/vscode-tls`;
  mkdirSync(dir, { recursive: true });
  const pair = name => {
    execFileSync('openssl', ['req', '-x509', '-newkey', 'ec', '-pkeyopt', 'ec_paramgen_curve:prime256v1', '-nodes',
      '-keyout', `${dir}/${name}.key`, '-out', `${dir}/${name}.crt`, '-days', '1', '-subj', '/CN=aerieos'], { stdio: 'ignore' });
    return { key: readFileSync(`${dir}/${name}.key`), cert: readFileSync(`${dir}/${name}.crt`) };
  };
  const pinOf = ({ cert }) => KEY_PIN + crypto.createHash('sha256')
    .update(new crypto.X509Certificate(cert).publicKey.export({ type: 'spki', format: 'der' })).digest('base64');
  // A door that answers a sign-in, a call and a terminal's upgrade (refused,
  // so reaching it is said by its status), and remembers what it was asked
  // and the server name each connection named.
  const asked = [];
  const door = keys => new Promise(resolve => {
    const s = https.createServer(keys, (req, res) => {
      asked.push([req.url, req.socket.servername || '']);
      if (req.url === '/login') { res.writeHead(303, { 'Set-Cookie': 'bb_session=tok; Path=/', Location: '/' }); res.end(); return; }
      res.writeHead(200, { 'Content-Type': 'application/json' });
      res.end('{"api":1,"projects":[]}');
    });
    s.on('upgrade', (req, sock) => { asked.push([req.url.split('?')[0], req.socket.servername || '']); sock.end('HTTP/1.1 403 Forbidden\r\nContent-Length: 0\r\nConnection: close\r\n\r\n'); });
    s.listen(0, () => resolve(s));
  });
  const one = pair('one'), two = pair('two');
  const [s1, s2] = [await door(one), await door(two)];
  const at1 = `https://localhost:${s1.address().port}`, at2 = `https://localhost:${s2.address().port}`;
  const tried = async f => { try { return { ok: await f() }; } catch (e) { return { error: e.message, status: e.status }; } };
  try {
    // Held to the authorities (the setting off): refused, nothing asked.
    const ca = await tried(() => signIn(at1, 'ed.rw', 'pw'));
    ok(ca.error && asked.length === 0, `...with the setting off, a certificate no authority signed is refused before anything is sent (${String(ca.error).slice(0, 60)})`);
    // The first sign-in pins the key it was answered under.
    let pinned = '';
    const first = await tried(() => signIn(at1, 'ed.rw', 'pw', { rejectUnauthorized: false, onPin: p => { pinned = p; } }));
    ok(first.ok === 'tok' && pinned === pinOf(one) && asked.length === 1 && asked[0][1] === '',
       `...the first sign-in under the controller's own certificate pins its key, naming no server (${pinned.slice(0, 16)}..., ${JSON.stringify(asked)})`);
    // Under that pin: a call and a terminal reach it.
    const c1 = new Client(at1, 'tok', { rejectUnauthorized: false, pin: pinned });
    const call = await tried(() => c1.projects());
    const term = await tried(() => c1.terminal('sh:1:alpha', 80, 24));
    ok(call.ok && term.status === 403 && asked.map(a => a[0]).join(' ') === '/login /api/v1/files /termws',
       `...and a call and a terminal under the key it pinned reach the controller (${JSON.stringify(asked.map(a => a[0]))})`);
    // Another key at the address: refused, and nothing sent, the password included.
    const n = asked.length;
    const other = await tried(() => signIn(at2, 'ed.rw', 'pw', { rejectUnauthorized: false, pin: pinned }));
    const c2 = new Client(at2, 'tok', { rejectUnauthorized: false, pin: pinned });
    const otherCall = await tried(() => c2.projects());
    const otherTerm = await tried(() => c2.terminal('sh:1:alpha', 80, 24));
    ok([other, otherCall, otherTerm].every(r => /another key than the one this editor trusted/.test(r.error || '')) && asked.length === n,
       `...and another key is refused for a sign-in, a call and a terminal with nothing sent (${String(other.error).slice(0, 70)})`);
    // A client with no pin yet pins on its first call and holds it after.
    let later = '';
    const c3 = new Client(at1, 'tok', { rejectUnauthorized: false, onPin: p => { later = p; } });
    await tried(() => c3.projects());
    ok(later === pinOf(one) && c3.tls.pin === later, `...and a client with no key pinned yet pins it on its first call and holds it (${later.slice(0, 16)}...)`);
  } finally {
    s1.close();
    s2.close();
  }
});

await done();
