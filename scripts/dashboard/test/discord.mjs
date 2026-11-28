// A space's Discord server, against the harness's stand-in for
// Discord's API (discord-stub.py): connected in the space's settings with a
// bot's token that is never shown again, pulled into deploy/discord.yml,
// planned with each change a person allows marked, applied by a person,
// and a session's apply under its Manage Discord dial, what asks always
// waiting on a person.
import { launch, newPage, ok, done, ready, URL, DIR, REPO, section, call, asSession } from './lib.mjs';
import { readFileSync, writeFileSync, existsSync } from 'node:fs';
import { execFileSync } from 'node:child_process';

const TOKEN = 'MTI' + 's'.repeat(60);
const FILE = `${DIR}/ws/alpha/deploy/discord.yml`;
const browser = await launch();
const page = await newPage(browser, { viewport: { width: 1280, height: 1000 } });
await page.goto(URL);
await ready(page);

const settings = async () => {
  await page.evaluate(() => renameProject('alpha', 'project'));
  await page.waitForSelector('#rnmodal:not([hidden])', { timeout: 10000 });
  await page.waitForFunction(() => rnDc !== null, null, { timeout: 10000 });
};

await section("connected in the space's settings, its token never shown again", async () => {
  await settings();
  const sect = 'details[data-sect="rn:discord"]';
  ok(await page.$eval(sect, d => !d.hidden) && !!await page.$(`${sect} #rnDcToken[type="password"]`),
     "the space's settings carry a Discord section asking for a bot's token, masked");
  await page.fill(`${sect} #rnDcToken`, 'not a token');
  await page.click(`${sect} [data-dcconnect]`);
  await page.waitForFunction(() => /does not read as a Discord bot token/.test(document.querySelector('#rnDcSay')?.textContent || ''), null, { timeout: 10000 });
  ok(true, '...and something that is not a bot token is refused in a sentence');
  await page.fill(`${sect} #rnDcToken`, TOKEN);
  await page.click(`${sect} [data-dcconnect]`);
  await page.waitForFunction(() => /Shop community/.test(document.querySelector('#rnDcField')?.textContent || ''), null, { timeout: 10000 });
  const got = await page.evaluate(async () => (await fetch('/api/discord?project=alpha')).text());
  ok(/"guild_name": ?"Shop community"/.test(got) && !got.includes('MTIsss'), `connected to the server the bot is in, and its token is nowhere in what is read back (${got.slice(0, 120)})`);
  const listed = await page.evaluate(async () => (await (await fetch('/api/connections')).json()).rows || []);
  ok(listed.some(r => r.kind === 'discord' && /Shop community/.test(r.name || '')), "...and it is on Controller settings' Connected services");
  await page.evaluate(() => closeRename());
});

await section("Pull, Plan and Apply in the Discord view", async () => {
  await page.evaluate(() => openNotebook('alpha', 'discord'));
  const V = '.pane .nb .nbview[data-view="discord"]';
  // The server named on the view's own row, where a view with buttons alone keeps its words.
  await page.waitForFunction(v => /Shop community/.test(document.querySelector(`${v} > .nbhead .nbsaidslot`)?.textContent || ''), V, { timeout: 15000 });
  ok(/no <code>deploy\/discord.yml<\/code> yet|no deploy\/discord.yml yet/.test(await page.$eval(`${V} #dcList`, e => e.innerHTML)),
     'the view names the server and says the repository has no layout yet');
  await page.click(`${V} #dcPull`);
  for (let i = 0; i < 50 && !existsSync(FILE); i++) await new Promise(r => setTimeout(r, 100));
  const text = existsSync(FILE) ? readFileSync(FILE, 'utf8') : '';
  ok(/name: Moderators/.test(text) && /name: rules/.test(text) && /name: general/.test(text),
     `Pull writes the server as it stands into deploy/discord.yml, uncommitted (${text.slice(0, 80).replace(/\n/g, ' | ')})`);
  // The layout changed by hand: a new role, and #general gone.
  writeFileSync(FILE, text.replace(/\n  - name: general\n    kind: text\n/, '\n').replace(/^roles:\n/m, 'roles:\n  - name: Regulars\n    color: "#3498db"\n')
    + 'automod:\n  - name: No invites\n    keywords: ["discord.gg/*"]\n');
  await page.waitForFunction(v => !document.querySelector(`${v} #dcPlan`)?.disabled, V, { timeout: 10000 });
  await page.click(`${V} #dcPlan`);
  await page.waitForFunction(v => /role Regulars added/.test(document.querySelector(`${v} #dcList`)?.textContent || ''), V, { timeout: 15000 });
  const rows = await page.$$eval(`${V} #dcList .rows .row`, rs => rs.map(r => r.textContent.replace(/\s+/g, ' ').trim()));
  ok(rows.some(r => /^#general removed\s*asks$/.test(r)) && rows.some(r => /^role Regulars added$/.test(r)) && rows.some(r => /AutoMod rule No invites added/.test(r)),
     `Plan lists each change, a removal marked as one a person allows (${rows.join(' | ')})`);
  page.answers.push(0);
  await page.click(`${V} #dcApply`);
  await page.waitForFunction(v => /Applied/.test(document.querySelector(`${v} #dcList`)?.textContent || ''), V, { timeout: 15000 });
  const after = await call('/api/discord', { project: 'alpha', action: 'plan' });
  ok(after.status === 200 && after.body.changes.length === 0, `a person's Apply makes every change, and then nothing is left to change (${after.body.said})`);
});

await section("a session's apply under Manage Discord, what asks always waiting on a person", async () => {
  const tok = execFileSync('bash', [`${REPO}/scripts/aerie`, 'users', 'token', 'alpha', 'test'],
    { encoding: 'utf8', env: { ...process.env, DASHBOARD_STATE: `${DIR}/state`, WORKSPACE: `${DIR}/ws` } }).trim();
  const S = asSession(tok);
  const layout = readFileSync(FILE, 'utf8').replace(/\n  - name: Regulars\n    color: "#3498db"\n/, '\n') + 'pins:\n  rules:\n    - Be kind.\n';
  const plan = await call('/api/discord', { project: 'alpha', action: 'plan', text: layout }, S);
  ok(plan.status === 200 && plan.body.asks === 1, `a session plans freely (${plan.body.said})`);
  const denied = await call('/api/discord', { project: 'alpha', action: 'apply', text: layout, why: 'launch' }, S);
  ok(denied.status === 403 && /Manage Discord/.test(denied.body.error || ''), `at deny a session's apply is refused, naming the setting (${denied.body.error})`);
  const connect = await call('/api/discord', { project: 'alpha', action: 'connect', token: TOKEN }, S);
  ok(connect.status === 403, 'and a session never connects a server');
  await call('/api/prefs', { project: 'alpha', discord: 'auto' });
  const auto = await call('/api/discord', { project: 'alpha', action: 'apply', text: layout, why: 'pin the rules' }, S);
  ok(auto.status === 200 && (auto.body.done || []).some(s => /pinned in #rules/.test(s)) && (auto.body.left || []).some(s => /role Regulars removed/.test(s)) && auto.body.asked,
     `at auto it makes what asks nobody and asks a person for the rest (${JSON.stringify(auto.body).slice(0, 200)})`);
  const bell = await call('/api/phone');
  const row = (bell.body.asks || []).find(r => r.id === auto.body.asked) || {};
  ok(row.kind === 'discord' && /role Regulars removed/.test(row.detail || ''), `the bell's row lists each change it would make (${JSON.stringify(row).slice(0, 160)})`);
  await call('/api/prefs', { project: 'alpha', discord: 'deny' });
});

await browser.close();
done();
