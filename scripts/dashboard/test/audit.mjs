// Sign-in hardened: a browser's sign-in is bound to the
// browser it was made in, so its cookie presented from another browser is
// refused; Profile lists the browsers signed in as you, each with Sign out,
// which ends that one's cookie; and the Audit page under Controller reads
// who did what, newest first, narrowed to a person.
import { URL as BASE, launch, newPage, done, ok, settled, patience } from './lib.mjs';

const CHROME = 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/130.0 Safari/537.36';
const PHONE = 'Mozilla/5.0 (iPhone; CPU iPhone OS 17_0 like Mac OS X) AppleWebKit/605.1.15 (KHTML, like Gecko) Version/17.0 Mobile/15E148 Safari/604.1';

// A sign-in by the form, as a browser does it: the cookie out of the 303.
async function cookieFor(ua){
  const r = await fetch(BASE + '/login', { method: 'POST', redirect: 'manual',
    headers: { 'Content-Type': 'application/x-www-form-urlencoded', 'User-Agent': ua },
    body: 'username=test&password=test' });
  const set = r.headers.get('set-cookie') || '';
  return (set.match(/bb_session=([^;]+)/) || [])[1] || '';
}
const status = (cookie, ua) => fetch(BASE + '/api/status', { headers: { Cookie: `bb_session=${cookie}`, 'User-Agent': ua } }).then(r => r.status);

const c1 = await cookieFor(CHROME);
ok(!!c1, 'the form signs a browser in with a cookie');
ok(await status(c1, CHROME) === 200, 'the cookie answers from the browser it was made in');
ok(await status(c1, PHONE) === 401, 'the same cookie from another browser is refused');
ok(await status(c1, CHROME) === 200, '...and still answers from its own');

// Profile lists it, and Sign out there ends it.
const browser = await launch();
const page = await newPage(browser, { userAgent: CHROME });
await page.goto(BASE);
await page.waitForFunction(() => typeof state !== 'undefined' && state && state.repos);
const me = await page.evaluate(async () => (await (await fetch('/api/profile')).json()));
const rows = (me.signins || []);
const mine = rows.find(r => r.agent === 'Chrome on Windows');
ok(rows.length >= 1 && !!mine, `Profile lists the browser signed in, by name (${rows.map(r => r.agent).join(', ') || 'none'})`);
const ended = await page.evaluate(async id => (await postJSON('/api/profile', { action: 'signin-out', id })), mine ? mine.id : 'x');
ok(ended.ok === true && ended.this === false, 'Sign out on another browser\'s row answers that it is not this one');
ok(await status(c1, CHROME) === 401, '...and that browser\'s cookie is nobody\'s from its next request');

// The Audit page: under Controller, rows newest first, narrowed to a person.
await page.evaluate(() => openAuditTab());
await page.waitForSelector('.audittab .auditrow, .audittab .empty', { timeout: patience(20000) });
await settled(page);
const seen = await page.evaluate(() => ({
  rows: [...document.querySelectorAll('.audittab .auditrow')].length,
  refused: [...document.querySelectorAll('.audittab .auditrow')].some(r => /sign-in refused/.test(r.textContent)),
  pickers: !!document.querySelector('#auditPerson') && !!document.querySelector('#auditMachine'),
}));
ok(seen.rows > 0 && seen.pickers, `the Audit page lists what was done, with a person and a machine to pick (${seen.rows} rows)`);
ok(seen.refused, 'the refused cookie is on it as a line of its own');
await page.selectOption('#auditPerson', 'test');
await page.waitForFunction(() => { const rows = [...document.querySelectorAll('.audittab .auditrow')]; return rows.length > 0 && rows.every(r => r.textContent.includes('test')); }, null, { timeout: patience(15000) });
ok(true, 'picked to one person, every row is theirs');

// A notebook's presence beat changes nothing a person reads the audit for,
// and it came every fifteen seconds an open notebook: it is
// not a row, while a write beside it still is.
const audited = await page.evaluate(async () => {
  for (let i = 0; i < 3; i++) await postJSON('/api/presence', { project: 'alpha', client: 'audit-probe', where: 'roadmap' });
  const j = await (await fetch('/api/audit?n=500')).json();
  return { beats: j.rows.filter(r => r.action.startsWith('/api/presence')).length,
           signout: j.rows.some(r => r.action === '/api/profile:signin-out') };
});
ok(audited.beats === 0 && audited.signout, `a presence beat is not an audit row, a sign-out is (${audited.beats} beats on it)`);
await done(browser);
