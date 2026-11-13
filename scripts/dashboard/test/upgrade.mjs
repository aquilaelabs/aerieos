// Older installs are not broken by this build (R79): this tree's controller
// started on a copy of every release snapshot of /config it still migrates
// from (test/upgrade/NAME/, written by tools/upgrade-snapshot.py; a release
// whose snapshot was taken again at a later state keeps the earlier one
// beside it as VERSION-stateN), and checked to migrate it and keep
// everything in it.
//
// Each snapshot these ways. As the release left it: the stamp moves to this
// build's state, with a copy under backups/ when it had to move; the owner
// signs in through the form in a browser, every account signs in, and every
// account, space, role on a space, notebook entry (roadmap, bugs, house
// rules, wiki), tool pack and device the manifest lists is still there,
// with the values the manifest gives: the settings, a space's settings and
// the enrolled node as it was. With what a build at its state could have
// stored and a later migration changes, planted as that build wrote it:
// each is in the new shape afterwards, on the file the controller reads.
// And stamped newer than this build: the controller refuses to start, says
// so, and writes nothing.
//
// Once, on the oldest snapshot: a build whose last migration fails. It does
// not start; /config is as it was before the update, byte for byte, with a
// note saying which migration and why; the same build is refused again
// without trying; and the build without that migration starts on it.
//
// What it holds: stateversion.py, statemigrations/, statefile.py, users.py,
// prefs.py and whatever a release's /config is read by. Its own controller
// per case, on its own port and scratch directories, beside the harness's
// world and never in it.
import { launch, ok, done, DIR, sleep, patience } from './lib.mjs';
import { mkdirSync, readFileSync, writeFileSync, existsSync, readdirSync, rmSync, openSync, cpSync } from 'node:fs';
import { execFileSync, spawn } from 'node:child_process';
import { createServer } from 'node:net';
import { fileURLToPath } from 'node:url';

const DASH = fileURLToPath(new URL('..', import.meta.url));
const SNAPS = fileURLToPath(new URL('./upgrade', import.meta.url));
const policy = JSON.parse(execFileSync('python3', [`${DASH}/stateversion.py`, 'policy']).toString());
const BUILD = `${readFileSync(`${DASH}/../../VERSION`, 'utf8').trim()}-dev.1+upgrade`;

const freePort = () => new Promise(res => {
  const s = createServer().listen(0, '127.0.0.1', () => { const p = s.address().port; s.close(() => res(p)); });
});
const basic = (u, pw) => ({ Authorization: 'Basic ' + Buffer.from(`${u}:${pw}`).toString('base64') });

// A snapshot unpacked into a world of its own: config/ and workspace/.
function unpack(ver, tag){
  const w = `${DIR}/upgrade-${ver}-${tag}`;
  rmSync(w, { recursive: true, force: true });
  mkdirSync(w, { recursive: true });
  execFileSync('tar', ['--no-same-owner', '-xzf', `${SNAPS}/${ver}/config.tar.gz`, '-C', w]);
  return w;
}

// This tree's controller on that world, as run.sh starts the harness's.
async function start(w, dash = DASH, build = BUILD){
  const port = await freePort();
  const out = openSync(`${w}/server.log`, 'a');
  const proc = spawn('python3', ['-u', `${dash}/server.py`], { stdio: ['ignore', out, out], env: {
    ...process.env, WORKSPACE: `${w}/workspace`, DASHBOARD_STATE: `${w}/config`,
    DASHBOARD_PORT: String(port),
    BUILDER_HOME: `${w}/home`, BB_VERSION: build, BB_BIN: `${DIR}/bin/aerie`,
    BB_DOCKER_BIN: `${DIR}/bin/docker`, BB_ADB_BIN: `${DIR}/bin/adb`, BB_WEBEXT_BIN: `${DIR}/bin/web-ext`,
    BB_DOCTOR_FIXTURE: `${DIR}/doctor.txt`, BB_DEV_DATA_DIR: `${w}/devdata`, BB_ARCHIVE_SPOOL: `${w}/spool`,
    TC_AUTOCHECK: '0', BB_NODE_POLL: '3', BB_CLAUDE_LATEST_URL: 'file:///nonexistent', BB_CLAUDE_CHECK_DELAY: '3600',
    BB_NGINX_TAGS_URL: 'file:///nonexistent', BB_NGINX_CHECK_DELAY: '3600',
    BB_APPS_RELEASES_URL: 'file:///nonexistent', BB_APPS_BOOT_DELAY: '3600',
    BB_IMAGE_DIGESTS_FILE: `${w}/image-digests.json`, BB_IMAGE_CHECK_DELAY: '3600',
    BUILDERBOT_ROLE: 'controller', BB_TOKEN: '', BB_COVERAGE_OUT: '' } });
  const exited = new Promise(res => proc.on('exit', code => res(code)));
  const base = `http://127.0.0.1:${port}`;
  for (let i = 0; i < patience(120); i++){
    const gone = await Promise.race([exited, sleep(250).then(() => undefined)]);
    if (gone !== undefined) return { proc, base, code: gone, log: () => readFileSync(`${w}/server.log`, 'utf8') };
    try { if ((await fetch(`${base}/login`)).status === 200) break; } catch { /* not up yet */ }
  }
  return { proc, base, code: null, exited, log: () => readFileSync(`${w}/server.log`, 'utf8') };
}
const stop = async c => { if (c.code === null){ c.proc.kill('SIGTERM'); await Promise.race([c.exited, sleep(10000)]); c.proc.kill('SIGKILL'); } };

// Every file of a /config with its size and time, but for the one-server
// lock and pid, which are taken before the version is read and are no part
// of the state.
const listing = w => execFileSync('find', [`${w}/config`, '-mindepth', '1', '!', '-name', '.server.lock', '!', '-name', '.server.pid', '-printf', '%p %s %T@\n']).toString();
// ...and every file's content, with the names in `out` left out, and the
// empty files a store's lock is held on (NAME.lock), which any read makes.
// The database by what it holds, not its bytes: a copy of one is the same
// rows in a file laid out anew.
const contents = (w, ...out) => execFileSync('bash', ['-c',
  `cd "$1/config" && find . -mindepth 1 -type f ! -name 'builderbot.db*' ! -name '*.lock' ${['.server.lock', '.server.pid', ...out].map(n => `! -path './${n}' ! -path './${n}/*'`).join(' ')} -print0 | sort -z | xargs -0 sha256sum`, '-', w]).toString()
  + execFileSync('python3', ['-c', `import hashlib, sqlite3, sys
c = sqlite3.connect("file:" + sys.argv[1] + "?mode=ro", uri=True)
print(hashlib.sha256("\\n".join(c.iterdump()).encode()).hexdigest(), " builderbot.db")`, `${w}/config/builderbot.db`]).toString();
// The lines of one listing that are not in the other, either way.
const differs = (a, b) => { const A = new Set(a.split('\n')), B = new Set(b.split('\n'));
  return [...a.split('\n').filter(l => !B.has(l)).map(l => '-' + l.slice(64)), ...b.split('\n').filter(l => !A.has(l)).map(l => '+' + l.slice(64))].join(' '); };

const stampOf = w => JSON.parse(readFileSync(`${w}/config/state.json`, 'utf8'));

// Everything the manifest lists, read back through the API as the owner.
async function holds(c, m, said){
  const H = basic(m.owner.name, m.owner.password);
  const get = async p => (await fetch(c.base + p, { headers: H })).json();
  const missing = [];
  const users = (await get('/api/users')).users || [];
  for (const n of m.accounts) if (!users.some(u => u.name === n)) missing.push(`account ${n}`);
  const roles = await get('/api/roles');
  // A role is held on a project (R138): each repository the manifest names
  // read as the project the status read says it is in.
  const rows = (await get('/api/status')).projects || [];
  const keyOf = p => rows.find(x => x.name === p)?.project || p;
  for (const r of m.roles) if (!(r in (roles.roles || {}))) missing.push(`role ${r}`);
  for (const [n, pr] of Object.entries(m.project_roles))
    for (const [p, rs] of Object.entries(pr)) for (const r of rs){
      const who = (roles.people || []).find(x => x.name === n);
      if (!(who?.project_roles?.[keyOf(p)] || []).includes(r)) missing.push(`${n}'s ${r} on ${p}`);
    }
  for (const p of m.projects){
    if (!(roles.projects || []).includes(keyOf(p))) missing.push(`space ${p}`);
    const ids = ((await get(`/api/roadmap?project=${p}`)).items || []).map(i => i.id);
    for (const id of m.roadmap[p]) if (!ids.includes(id)) missing.push(`${p} roadmap ${id}`);
    const bugs = ((await get(`/api/bugs?project=${p}`)).bugs || []).map(b => b.id);
    for (const id of m.bugs[p]) if (!bugs.includes(id)) missing.push(`${p} bug ${id}`);
    const rules = ((await get(`/api/rules?project=${p}`)).rules || []).map(r => r.name);
    for (const r of m.rules[p]) if (!rules.includes(r)) missing.push(`${p} rule ${r}`);
    const pages = ((await get(`/api/wiki?project=${p}`)).pages || []).map(pg => pg.name);
    for (const pg of m.wiki[p]) if (!pages.includes(pg)) missing.push(`${p} wiki page ${pg}`);
  }
  const packs = ((await get('/api/toolchains')).items || []).filter(i => i.pack).map(i => i.name);
  for (const t of m.toolpacks) if (!packs.includes(t)) missing.push(`tool pack ${t}`);
  for (const [n, ds] of Object.entries(m.devices)){
    const have = (users.find(u => u.name === n)?.devices || []).map(d => d.name);
    for (const d of ds) if (!have.includes(d)) missing.push(`${n}'s device ${d}`);
  }
  ok(!missing.length, `${said}: every account, role, space, notebook entry, tool pack and device is there`
     + (missing.length ? ` (missing: ${missing.join(', ')})` : ''));
  const refused = [];
  for (const [n, pw] of Object.entries(m.passwords)){
    const r = await fetch(`${c.base}/login`, { method: 'POST', redirect: 'manual',
      headers: { 'Content-Type': 'application/x-www-form-urlencoded' },
      body: new URLSearchParams({ username: n, password: pw, next: '/' }) });
    if (r.status !== 303 || !(r.headers.get('set-cookie') || '').startsWith('bb_session=')) refused.push(n);
  }
  ok(!refused.length, `${said}: every account signs in with its password` + (refused.length ? ` (not: ${refused})` : ''));
}

// The values the manifest gives, read back through the API: a name that is
// still there says nothing of what a migration did to what it holds.
async function values(c, m, said){
  if (!m.values) return;
  const H = basic(m.owner.name, m.owner.password);
  const get = async p => (await fetch(c.base + p, { headers: H })).json();
  const st = await get('/api/status');
  const off = [], set = (st.settings || {}).settings || {};
  for (const [k, v] of Object.entries(m.values.settings || {})){
    // Each setting is served with where its value came from: one a person
    // set is from the settings file, never the default it would also equal.
    const has = set[k] || {};
    if (JSON.stringify(has.value) !== JSON.stringify(v) || has.source !== 'settings') off.push(`setting ${k} is ${JSON.stringify(has)}, was ${JSON.stringify(v)} as set`);
  }
  for (const [p, want] of Object.entries(m.values.prefs || {})){
    const row = (st.projects || []).find(x => x.name === p) || {};
    for (const [k, v] of Object.entries(want)){
      const has = (row.prefs || {})[k] ?? row[k];
      const same = v !== null && typeof v === 'object'
        ? Object.entries(v).every(([kk, vv]) => JSON.stringify((has || {})[kk]) === JSON.stringify(vv))
        : JSON.stringify(has) === JSON.stringify(v);
      if (!same) off.push(`${p}'s ${k} is ${JSON.stringify(has)}, was ${JSON.stringify(v)}`);
    }
  }
  const nodes = (await get('/api/v1/nodes')).nodes || [];
  for (const want of m.values.nodes || []){
    const n = nodes.find(x => x.name === want.name);
    if (!n){ off.push(`node ${want.name} is gone`); continue; }
    const got = { kind: n.kind, user: (n.config || {}).user, cpu: (n.reported || {}).cpu, mem_mb: (n.reported || {}).mem_mb, arch: n.arch };
    for (const [k, v] of Object.entries(want)) if (k !== 'name' && got[k] !== v) off.push(`node ${want.name}'s ${k} is ${JSON.stringify(got[k])}, was ${JSON.stringify(v)}`);
  }
  ok(!off.length, `${said}: the settings, each space's settings and the node hold the values they had` + (off.length ? ` (${off.join('; ')})` : ''));
}

// What a build at an older state could have stored and a migration since
// changes, written into the unpacked /config as that build wrote it. What
// to look for afterwards, or null when no migration past `state` has any.
function plantOld(w, state){
  const out = {};
  const uf = `${w}/config/users.json`;
  const users = JSON.parse(readFileSync(uf, 'utf8'));
  if (state < 22){
    // States 21 and 22: a repository's daily snapshot switch saved off, and a
    // person's terminal colors for one space.
    const f = `${w}/config/claude-prefs.json`;
    const d = existsSync(f) ? JSON.parse(readFileSync(f, 'utf8')) : {};
    const uid = Object.values(users.users || users).map(u => u && u.uid).find(Boolean);
    if (uid){
      d.projects = d.projects || {};
      d.projects.alpha = { ...(d.projects.alpha || {}), snapshots_on: false, snapshot_days: 14 };
      d.projects.beta = { ...(d.projects.beta || {}), snapshots_on: true, snapshot_days: 9 };
      d.users = d.users || {};
      d.users[uid] = { ...(d.users[uid] || {}), alpha: { term_scheme: 'red', reply: 'minimal' } };
      writeFileSync(f, JSON.stringify(d));
      out.prefs = { f, uid };
    }
  }
  if (state < 23 && users.users?.cy && users.users?.ada){
    // State 23: the share password a machine that serves shares kept for
    // every account at every sign-in, on an account no share names, and
    // one a person set apart on Profile.
    users.users.cy = { ...users.users.cy, smb_nt: 'C'.repeat(32), smb_at: 5, smb_follows: true };
    users.users.ada = { ...users.users.ada, smb_nt: 'D'.repeat(32), smb_at: 5 };
    writeFileSync(uf, JSON.stringify(users));
    out.shares = { f: uf };
  }
  return Object.keys(out).length ? out : null;
}

async function signIn(browser, c, m, said){
  const ctx = await browser.newContext({ viewport: { width: 1280, height: 800 } });
  await ctx.addInitScript(() => { window.BB_NO_TOUR = true; });     // the tour is tour.mjs's (R94)
  const page = await ctx.newPage();
  await page.goto(c.base + '/');
  await page.waitForURL('**/login**', { timeout: patience(20000) });
  await page.fill('#u', m.owner.name);
  await page.fill('#p', m.owner.password);
  await page.click('button[type=submit]');
  const inside = await page.waitForFunction(() => document.getElementById('rail') !== null,
    null, { timeout: patience(30000) }).then(() => true, () => false);
  ok(inside && !page.url().includes('login'), `${said}: the owner signs in through the form`);
  await ctx.close();
}

const browser = await launch();
const vers = existsSync(SNAPS) ? readdirSync(SNAPS).filter(v => existsSync(`${SNAPS}/${v}/manifest.json`)).sort() : [];
ok(vers.length > 0, `there is a release snapshot to start on (${vers.join(', ') || 'none'})`);
const taken = [];
for (const ver of vers){
  const m = JSON.parse(readFileSync(`${SNAPS}/${ver}/manifest.json`, 'utf8'));
  if (m.state < policy.supported_from){
    console.log(`  ${ver} (state ${m.state}) is older than this build migrates from (${policy.supported_from}): not started`);
    continue;
  }
  taken.push([m.state, ver]);

  // ---- as the release left it ----
  {
    const w = unpack(ver, 'as-shipped');
    const c = await start(w);
    ok(c.code === null, `${ver}: this build starts on the release's /config` + (c.code === null ? '' : `\n${c.log().slice(-1500)}`));
    if (c.code === null){
      const s = stampOf(w);
      ok(s.state === policy.current, `${ver}: its stamp is this build's state, ${policy.current} (${JSON.stringify(s)})`);
      const copies = existsSync(`${w}/config/backups`) ? readdirSync(`${w}/config/backups`) : [];
      ok(m.state < policy.current ? copies.includes(`before-${BUILD}`) : copies.length === 0,
         `${ver}: a copy before migrating where the state moved, none where it did not (${copies.join(', ') || 'none'})`);
      await holds(c, m, ver);
      await values(c, m, ver);
      await signIn(browser, c, m, ver);
    }
    await stop(c);
  }

  // ---- with what a build at its state stored, in the old shape ----
  if (m.state < policy.current){
    const w = unpack(ver, 'lived-in');
    const planted = plantOld(w, m.state);
    if (planted){
      const c = await start(w);
      ok(c.code === null, `${ver} lived in: this build starts on it` + (c.code === null ? '' : `\n${c.log().slice(-1500)}`));
      if (c.code === null){
        if (planted.shares){
          const us = JSON.parse(readFileSync(planted.shares.f, 'utf8')).users;
          ok(!('smb_nt' in us.cy) && !('smb_follows' in us.cy) && us.cy.password && us.ada.smb_nt === 'D'.repeat(32),
             `${ver} lived in: a share password that followed a sign-in is gone from an account no share names, and one set apart stays (${JSON.stringify([Object.keys(us.cy).filter(k => k.startsWith('smb')), us.ada.smb_nt?.slice(0, 4)])})`);
        }
        if (planted.prefs){
        const d = JSON.parse(readFileSync(planted.prefs.f, 'utf8'));
        const a = d.projects.alpha, b = d.projects.beta, mine = (d.users[planted.prefs.uid] || {}).alpha || {};
        ok(a.snapshot_days === 0 && !('snapshots_on' in a) && b.snapshot_days === 9 && !('snapshots_on' in b),
           `${ver} lived in: a daily snapshot switch saved off is 0 days kept and the switch is gone from the stored settings (${JSON.stringify([a.snapshot_days, a.snapshots_on, b.snapshot_days, b.snapshots_on])})`);
        ok(!('term_scheme' in mine) && mine.reply === 'minimal',
           `${ver} lived in: a person's terminal colors for one space are gone and what they set beside them stays (${JSON.stringify(mine)})`);
        const H = basic(m.owner.name, m.owner.password);
        const snaps = await (await fetch(`${c.base}/api/snapshots?project=alpha`, { headers: H })).json();
        ok(snaps.keep === 0 && !('on' in snaps), `${ver} lived in: and the controller reads it so: alpha keeps 0 days (${JSON.stringify({ keep: snaps.keep, on: snaps.on })})`);
        }
        await holds(c, m, `${ver} lived in`);
      }
      await stop(c);
    }
  }

  // ---- written by a newer build ----
  {
    const w = unpack(ver, 'newer');
    const newer = { state: policy.current + 1, by: '99.0.0' };
    writeFileSync(`${w}/config/state.json`, JSON.stringify(newer));
    // But for the one-server lock, which is taken before the version is read
    // and is no part of the state: an empty file, and the folder's own time.
    const before = listing(w);
    const c = await start(w);
    ok(c.code === 78 && /Downgrades are not supported/.test(c.log()) && /99\.0\.0/.test(c.log()),
       `${ver} stamped newer: this build refuses to start, saying a downgrade is not supported (${c.code}: ${c.log().trim().split('\n').pop()})`);
    ok(listing(w) === before, `${ver} stamped newer: and writes nothing of the state`);
    await stop(c);
  }
}
// ---- a migration that fails ----
// This build's scripts copied, with one more migration that changes a file,
// leaves another and then fails, started on the oldest snapshot: every
// migration before it ran and was stamped, and all of it is undone.
if (taken.length){
  const [state, ver] = taken.sort((a, b) => a[0] - b[0])[0];
  const w = unpack(ver, 'fails');
  const bad = `${w}/scripts`;
  cpSync(`${DASH}/..`, bad, { recursive: true, filter: src =>
    !/\/(__pycache__|node_modules)$/.test(src) && !/\/dashboard\/(test|unit)$/.test(src) });
  const num = String(policy.current + 1).padStart(4, '0');
  writeFileSync(`${bad}/dashboard/statemigrations/${num}_fails_here.py`, `"""Changes a record, leaves a file, then fails."""
from pathlib import Path


def run(ctx):
    state = Path(ctx["state"])
    (state / "users.json").write_text("{}")
    (state / "left-half-done.json").write_text("{}")
    raise RuntimeError("the disk said no")
`);
  const before = contents(w);
  const stamp = JSON.stringify(stampOf(w));
  // A build of its own number, as the next release is: the note it leaves
  // holds that build and no other.
  const badBuild = BUILD.replace('dev.1', 'dev.2');
  let c = await start(w, `${bad}/dashboard`, badBuild);
  const said = c.code === null ? '' : c.log();
  ok(c.code === 78 && said.includes(`${num}_fails_here.py`) && /RuntimeError: the disk said no/.test(said)
     && /did not land/.test(said) && /Start the release this \/config ran before/.test(said),
     `${ver}, a migration that fails: the build does not start, and says which migration, why, and what to start (${c.code}: ${said.trim().split('\n').slice(-2).join(' | ').slice(0, 400)})`);
  await stop(c);
  const note = existsSync(`${w}/config/update-did-not-land.txt`) ? readFileSync(`${w}/config/update-did-not-land.txt`, 'utf8') : '';
  const after = contents(w, 'backups', 'update-did-not-land.txt', 'logs');
  ok(after === before && JSON.stringify(stampOf(w)) === stamp && stampOf(w).state === state,
     `${ver}, a migration that fails: /config is as it was before the update, every file and every row, at state ${state} (${JSON.stringify(stampOf(w))}${after === before ? '' : '; differs: ' + differs(before, after).slice(0, 600)})`);
  ok(note.startsWith(`build ${badBuild}\n`) && note.includes(`${num}_fails_here.py`) && note.includes('the disk said no'),
     `${ver}, a migration that fails: a note in /config says which build, which migration and why (${note.trim().slice(0, 200)})`);
  const aside = existsSync(`${w}/config/backups`) ? readdirSync(`${w}/config/backups`).filter(n => n.startsWith('rolled-back-')) : [];
  ok(aside.length === 1 && existsSync(`${w}/config/backups/${aside[0]}/left-half-done.json`) && !existsSync(`${w}/config/left-half-done.json`),
     `${ver}, a migration that fails: what the failed start left is kept aside under backups/, not in /config (${aside.join(', ') || 'none'})`);
  // The same build again: refused before it touches anything.
  const again = listing(w);
  c = await start(w, `${bad}/dashboard`, badBuild);
  ok(c.code === 78 && /did not land/.test(c.code === null ? '' : c.log().split('\n').slice(-12).join('\n')) && listing(w) === again,
     `${ver}, a migration that fails: the same build started again is refused and writes nothing (${c.code})`);
  await stop(c);
  // The build without that migration starts on it, and the note goes.
  c = await start(w);
  ok(c.code === null, `${ver}, a migration that fails: a build without it starts on that /config` + (c.code === null ? '' : `\n${c.log().slice(-1500)}`));
  if (c.code === null){
    const m = JSON.parse(readFileSync(`${SNAPS}/${ver}/manifest.json`, 'utf8'));
    ok(stampOf(w).state === policy.current && !existsSync(`${w}/config/update-did-not-land.txt`),
       `${ver}, a migration that fails: and migrates it, with the note gone (${JSON.stringify(stampOf(w))})`);
    await holds(c, m, `${ver} after the failed update`);
  }
  await stop(c);
}
await done(browser);
