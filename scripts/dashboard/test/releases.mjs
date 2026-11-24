// Bugs, commits and changelog lines tied in the notebook (R255): a fixed bug
// records the commits that fixed it, its row lists the lines that answer it
// and ties, unties, writes one or says why it needs none; the changelog
// editor shows each line's bugs and the ones the next release owes; and a
// repository's Settings, Releases, holds the release gate and what each of a
// release's files is for. The public CHANGELOG.md names commits alone.
import { launch, newPage, ok, done, ready, until, settled, DIR, URL, takeOn, nbGo, section, openFold, rnSect, sectSave } from './lib.mjs';
import { mkdirSync, writeFileSync, readFileSync } from 'node:fs';
import { execFileSync } from 'node:child_process';
import { fileURLToPath } from 'node:url';
import { dirname, join } from 'node:path';

const P = 'relnotes', A = `${DIR}/ws/${P}`;
const BB = join(dirname(fileURLToPath(import.meta.url)), '..', '..', 'aerie');
const env = { ...process.env, DASHBOARD_STATE: `${DIR}/state`, WORKSPACE: `${DIR}/ws`, BB_BUG_PROJECT: P, BB_VERSION_PROJECT: P };
const bb = (...a) => execFileSync(BB, a, { cwd: A, env }).toString();
// ...for a verb whose exit says whether something is owed: its words either way.
const bbSaid = (...a) => { try { return bb(...a); } catch (e) { return String(e.stdout || ''); } };
const git = (...a) => execFileSync('git', ['-C', A, ...a]).toString().trim();
const bugsOn = () => JSON.parse(readFileSync(`${DIR}/state/bugs.json`, 'utf8')).projects[P] || [];
const bug = n => bugsOn().find(b => b.id === n) || {};
const log = () => readFileSync(`${A}/CHANGELOG.md`, 'utf8');

// A repository with a release, then three fixes after it, each its own commit.
mkdirSync(A, { recursive: true });
git('init', '-q');
git('config', 'user.name', 'dashboard test'); git('config', 'user.email', 'test@example.invalid');
writeFileSync(`${A}/README.md`, 'one\n'); writeFileSync(`${A}/VERSION`, '0.1.0\n');
git('add', '-A'); git('commit', '-qm', 'one'); git('tag', 'v0.1.0');
const fix = n => { writeFileSync(`${A}/README.md`, `one\nfix ${n}\n`); git('commit', '-qam', `fix ${n}`); return git('rev-parse', '--short=7', 'HEAD'); };
const [s1, s2, s3] = [fix(1), fix(2), fix(3)];
writeFileSync(`${A}/CHANGELOG.md`, `# Changelog\n\n## Unreleased\n\n### Fixed\n\n- The picker keeps its selection on rotate (${s1})\n- Menus open on the first press (1111111)\n\n## 0.1.0 - 2026-11-01\n`);
git('add', '-A'); git('commit', '-qm', 'the changelog');
await takeOn(P);
for (const t of ['the picker loses its selection on rotate', 'an export never finishes on a slow disk', 'a menu needs two presses'])
  bb('bug', 'add', t, '--here');
bb('bug', 'fix', 'B1', 'it keeps it', '--commit', s1);
bb('bug', 'fix', 'B2', 'B3', 'exports and menus', '--commit', `${s2},${s3}`);

await section('the commits that fixed a bug, from the CLI', async () => {
  ok(JSON.stringify(bug(1).commits) === JSON.stringify([s1]) && JSON.stringify(bug(3).commits) === JSON.stringify([s2, s3]),
     `aerie bug fix records the commits named, and closes several bugs one commit fixed (${JSON.stringify([bug(1).commits, bug(3).commits])})`);
  ok(new RegExp(`fixed in ${s2}, ${s3}`).test(bb('bug', 'fixed-in', 'B2')), 'aerie bug fixed-in lists them');
  bb('bug', 'fixed-in', 'B2', '--drop', s3);
  ok(JSON.stringify(bug(2).commits) === JSON.stringify([s2]), '...and takes one off');
  let refused = '';
  try { bb('bug', 'fixed-in', 'B2', 'deadbee'); } catch (e) { refused = String(e.stderr || e); }
  ok(/no commit deadbee/.test(refused), `a commit the repository does not hold is refused (${refused.trim().slice(0, 80)})`);
  const owes = bbSaid('changelog', 'missing');
  ok(/B2.*B3|B3.*B2/s.test(owes) && !/\bB1\b/.test(owes),
     'the release check owes a line for the two whose commits no line names, and not for the one a line names');
});

const browser = await launch();
const page = await newPage(browser, { viewport: { width: 1280, height: 900 } });
await page.goto(URL);
await ready(page);
await page.evaluate(n => openNotebook(n), P);
await nbGo(page, 'bugs');
await page.waitForSelector('#bugList .bug[data-id="1"]', { timeout: 15000 });
const row = n => `#bugList .bug[data-id="${n}"]`;
const open = async n => { if (!await page.$eval(row(n), d => d.open)) await page.click(`${row(n)} > summary`); await page.waitForSelector(`${row(n)}[open] .body`); };
// The row's More menu, opened until its item shows: a redraw the step
// before started (a tie's or an untie's write moving the list) shut the menu
// under the press, and the item waited a minute for nothing (B1046).
const more = async (n, cls) => {
  for (let i = 0; i < 4; i++){
    await page.click(`${row(n)} .macts .more > button`);
    if (await page.waitForSelector(`${row(n)} .actmenu .${cls}`, { state: 'visible', timeout: 5000 }).then(() => true, () => false)) break;
  }
  await page.click(`${row(n)} .actmenu .${cls}`);
};

await section("a fixed bug's row: its commits and its lines", async () => {
  await open(1);
  const facts = await page.$eval(`${row(1)} .facts`, e => e.textContent);
  ok(facts.includes(s1) && /The picker keeps its selection on rotate/.test(facts) && /names its fix commit/.test(facts),
     `Fixed in names its commit, and the line naming that commit is listed as found by it (${facts.replace(/\s+/g, ' ').slice(0, 160)})`);
  ok(!await page.$(`${row(1)} .bowed`), '...so nothing is owed for it');
  await open(2);
  ok(await page.$eval(`${row(2)} .bowed`, e => /No changelog line answers this fix yet/.test(e.textContent)),
     'a fixed bug no line answers says so on its row');
});

await section('tied to a line, and untied', async () => {
  await more(2, 'bTie');
  await page.waitForSelector(`${row(2)} .tiebox select`);
  await page.selectOption(`${row(2)} .tiebox select`, 'Menus open on the first press');
  await page.click(`${row(2)} .tiebox [data-tiego]`);
  await until(() => JSON.stringify(bug(2).changelog) === '["Menus open on the first press"]', 10000);
  ok(JSON.stringify(bug(2).changelog) === '["Menus open on the first press"]' && !/B2/.test(log()),
     'Tie to a line keeps the line\'s words on the bug, and the file names no bug');
  await page.waitForSelector(`${row(2)} [data-untie]`, { timeout: 10000 });
  ok(!await page.$(`${row(2)} .bowed`), '...its row lists the line with a remove, and owes nothing');
  await page.click(`${row(2)} [data-untie]`);
  await until(() => !bug(2).changelog, 10000);
  ok(!bug(2).changelog, 'the remove unties it, the line left as it was');
});

await section('needs no line, and a line written from the row', async () => {
  await open(2);
  await more(2, 'bNoLine');
  await page.fill(`${row(2)} .dropbox textarea`, 'no release had it');
  await page.click(`${row(2)} .dropbox [data-dropgo]`);
  await until(() => /Changelog: needs no line: no release had it/.test(bug(2).notes || ''), 10000);
  ok(/Changelog: needs no line: no release had it/.test(bug(2).notes || ''), 'Needs no line keeps the reason in its notes, as the release check reads it');
  await open(3);
  await more(3, 'bLine');
  const pre = await page.$eval(`${row(3)} .dropbox textarea`, t => t.value);
  await page.fill(`${row(3)} .dropbox textarea`, 'A menu opens on the first press');
  await page.click(`${row(3)} .dropbox [data-dropgo]`);
  await until(() => (bug(3).changelog || []).length, 10000);
  ok(pre === 'a menu needs two presses' && log().includes(`- A menu opens on the first press (${s2}, ${s3})`)
     && JSON.stringify(bug(3).changelog) === '["A menu opens on the first press"]',
     `Write a line starts from the title, files the line under Fixed with the bug's commits, and ties it (${pre})`);
  ok(!/\bB\d/.test(log()), 'the public file names no bug anywhere');
});

await section('the changelog editor: each line\'s bugs, and what is owed', async () => {
  // A fourth bug fixed in a commit no line names, owed again.
  bb('bug', 'add', 'the export dialog forgets its folder', '--here');
  writeFileSync(`${A}/README.md`, 'one\nfix 4\n'); git('commit', '-qam', 'fix 4');
  const s4 = git('rev-parse', '--short=7', 'HEAD');
  bb('bug', 'fix', 'B4', 'it remembers', '--commit', s4);
  await nbGo(page, 'artifacts');
  await page.waitForSelector('#verBox [data-verlog]', { timeout: 20000 });
  await page.click('#verBox [data-verlog]');
  await page.waitForSelector('.clog', { timeout: 15000 });
  const owed = await page.$$eval('.clog .clowe', rs => rs.map(r => r.dataset.ow));
  ok(JSON.stringify(owed) === '["4"]', `the band over the lines names the fixed bug the next release owes (${owed})`);
  const pills = await page.$$eval('.clog .clrow', rs => rs.map(r => [...r.querySelectorAll('.clbug')].map(p => p.textContent.replace(/✕/, '').trim())));
  ok(pills.some(p => p.includes('B3')), `a tied line shows its bug as a pill (${JSON.stringify(pills)})`);
  ok(await page.$eval('.clog .clrow', r => !!r.querySelector('.clbug.bycommit') && /B1/.test(r.querySelector('.clbug.bycommit').textContent)
                      && !r.querySelector('.clbug.bycommit .pillx')),
     'a line naming a bug\'s fix commit shows that bug too, with nothing to untie');
  await page.click('.clog .clowe[data-ow="4"] [data-owline]');
  await page.waitForSelector('.clog .clbug.pend', { timeout: 5000 });
  await page.fill('.clog .clrow:has(.clbug.pend) textarea', 'The export dialog remembers its folder');
  await page.click('.clog #clSave');
  await until(() => JSON.stringify(bug(4).changelog) === '["The export dialog remembers its folder"]', 15000);
  ok(log().includes(`- The export dialog remembers its folder (${s4})`) && JSON.stringify(bug(4).changelog) === '["The export dialog remembers its folder"]',
     'Write a line on the band adds it under Fixed with the commit, and Save ties the bug to it');
  await page.waitForFunction(() => !document.querySelector('.clog .clowe') && !document.querySelector('.clog .clbug.pend'), null, { timeout: 15000 });
  ok(true, '...and nothing is owed after it');
  // Reworded in the editor, the line keeps its bug.
  await page.fill('.clog .clrow:has(.clbug:text("B4")) textarea', 'The export dialog keeps the folder you picked');
  await page.click('.clog #clSave');
  await until(() => JSON.stringify(bug(4).changelog) === '["The export dialog keeps the folder you picked"]', 15000);
  ok(JSON.stringify(bug(4).changelog) === '["The export dialog keeps the folder you picked"]', 'a line reworded and saved keeps its bug');
  await page.keyboard.press('Escape');
});

await section("a repository's Releases settings", async () => {
  await page.evaluate(() => getNotebook('relnotes').view('settings'));
  await page.waitForSelector('#rnRelGate', { state: 'attached', timeout: 15000 });
  await rnSect(page, 'releases');
  ok(await page.$eval('#rnRelGate', s => s.value) === 'refuse' && await page.$eval('#rnRelTable', s => s.value) === 'on',
     'a release waits for what is owed, and its notes open with its files, unless set otherwise');
  await page.selectOption('#rnRelGate', 'warn');
  await sectSave(page, 'releases');
  const prefs = () => JSON.parse(readFileSync(`${DIR}/state/claude-prefs.json`, 'utf8')).projects[P] || {};
  await until(() => prefs().release_gate === 'warn', 10000);
  ok(prefs().release_gate === 'warn', 'its Save writes the gate');
  await page.click('#rnRelFiles [data-reladd]');
  await page.fill('#rnRelFiles [data-relname]', 'relnotes-@VER@.apk');
  await page.fill('#rnRelFiles [data-relwhat]', 'The Android app');
  await page.click('#rnRelFiles [data-relsave]');
  await until(() => (prefs().files || []).length === 1, 10000);
  ok(JSON.stringify(prefs().files) === '[{"name":"relnotes-@VER@.apk","what":"The Android app"}]',
     'Add a file writes the record at once, as a record list does');
  ok(await page.$eval('#rnRelFiles', e => /relnotes-@VER@\.apk/.test(e.textContent) && /The Android app/.test(e.textContent)),
     '...and lists it');
  for (const width of [393, 1280]){
    await page.setViewportSize({ width, height: 900 });
    await settled(page);
    const wide = await page.$eval('#rnRelFiles', e => e.scrollWidth <= e.clientWidth + 1);
    ok(wide, `the list fits at ${width}px`);
  }
});

await browser.close();
done();
