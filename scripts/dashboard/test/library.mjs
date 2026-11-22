// The Library (R170): one page under Build for everything an AerieOS
// installs or runs on a node, as one list of one shape. Opens on the
// harness's stub node, a section per kind always drawn, the rows read from
// /api/library; the search and the chips narrow the list and save nothing;
// a row opens on its description; the verbs are the pages' own (an install
// is the toolchain job, which the bb stub runs in a second).
import { launch, newPage, ok, done, ready, URL, DIR, section, libraryRowsWrong } from './lib.mjs';
import { readFileSync, writeFileSync } from 'node:fs';

const browser = await launch();
const page = await newPage(browser, { viewport: { width: 1280, height: 900 } });
await page.goto(URL);
await ready(page);

// ---- on the rail -------------------------------------------------------
ok(await page.evaluate(() => railGroups().some(g => g.key === 'build' && g.tools[0][0] === 'library') && railAllows('library')),
   'the Library is the Build group\'s first page');
ok(await page.evaluate(() => !railGroups().some(g => g.tools.some(([k]) => k === 'toolchains' || k === 'agents' || k === 'apps'))),
   '...and Toolchains, Agents and Apps are no longer pages of their own on the rail');

// ---- the page ----------------------------------------------------------
await page.evaluate(() => openLibrary());
await page.waitForSelector('.pane .bar #ndPick', { timeout: 20000 });
await page.waitForFunction(() => lib && !lib.nonode && Array.isArray(lib.rows), null, { timeout: 20000 });
// ...pushed by the draw that follows the read, so waited for.
ok(await page.waitForFunction(() => location.hash === '#/build/library/' + encodeURIComponent(libNode), null, { timeout: 10000 }).then(() => true, () => false),
   `the address names the page and its node (${await page.evaluate(() => location.hash)})`);
// Every row the Library has for the node, asked for whole (no view): what
// the checks count against, since the page holds a page of it at most.
const whole = () => page.evaluate(async () => (await getJSON('/api/library?node=' + encodeURIComponent(libNode))).rows || []);
let ALL = await whole();
const HERE = ALL.filter(r => !r.wrong_platform && !r.too_new);
const groupOf = r => r.group || r.kind;
const KINDS = ['agent', 'toolchain', 'pack', 'service', 'app', 'companion'];
// Waits for the page to have drawn what a narrowing asked the server for.
const settled = () => page.waitForFunction(() => !readBusy('library') && !!document.querySelector('.doc .librarytab .libgroups'), null, { timeout: 20000 });

// ---- the front page: shelves, never the whole catalog (R256) ----------------
await page.waitForSelector('.doc .librarytab .libgroup', { timeout: 15000 });
const shelves = await page.$$eval('.doc .librarytab .libgroup', ds => ds.map(d => ({ key: d.dataset.libgroup, cards: d.querySelectorAll('.lcard').length,
  all: d.querySelector('[data-libshelf]')?.textContent.trim() || '' })));
const kindsHere = KINDS.filter(k => HERE.some(r => groupOf(r) === k));
const MINE = HERE.filter(r => r.installed || r.update || r.repin);
ok(kindsHere.every(k => shelves.some(sh => sh.key === k)) && shelves.every(sh => sh.cards <= 8)
   && shelves.filter(sh => sh.key !== 'installed' && sh.cards).map(sh => sh.key).join() === kindsHere.join(),
   `the front page is a shelf per kind, in the page's order, eight cards at most on each (${shelves.map(sh => `${sh.key}:${sh.cards}`).join(', ')})`);
ok(shelves.every(sh => { const n = sh.key === 'installed' ? MINE.length : HERE.filter(r => groupOf(r) === sh.key).length;
  return !sh.cards || (n > sh.cards ? sh.all === `All ${n} ›` : !sh.all); }),
   '...each with All N to its list where it holds more than it shows');
ok(MINE.length ? shelves[0]?.key === 'installed' : !shelves.some(sh => sh.key === 'installed'),
   `...and what is on this node comes first (${MINE.length} installed or with an update)`);
ok(await page.evaluate(() => !(lib.rows || []).length && Array.isArray(lib.shelves)),
   'the page holds the shelves the server picked, never the whole catalog');
// No pack at all is no Tool packs shelf (the operator, 29 Oct), unless the
// catalog has something to say over them.
ok(await page.evaluate(async () => {
  const keep = lib;
  const drawn = async f => { for (const end = Date.now() + 10000; !f() && Date.now() < end;) await new Promise(r => setTimeout(r, 50)); };
  const pack = '.doc .librarytab .libgroup[data-libgroup="pack"]';
  lib = {...lib, shelves: (lib.shelves || []).filter(sh => sh.kind !== 'pack'), catalog_error: '', catalog_repo: ''};
  readMoved('library'); drawPanes(); await drawn(() => !document.querySelector(pack));
  const gone = !document.querySelector(pack);
  lib = {...lib, catalog_error: 'no index'}; readMoved('library'); drawPanes(); await drawn(() => document.querySelector(pack + ' .hint'));
  const said = /no index/.test(document.querySelector(pack)?.textContent || '');
  lib = keep; readMoved('library'); drawPanes();
  return gone && said;
}), 'with no tool pack the Tool packs shelf is not drawn, and the catalog\'s trouble is still said where it would be');
const shape = ALL.map(r => [r.kind, r.tier, typeof r.label, typeof r.about, typeof r.installed, typeof r.verb]);
ok(shape.length > 0 && shape.every(([k, t, l, a, i, v]) => KINDS.includes(k)
   && ['official', 'verified', 'vetted', 'sideloaded'].includes(t) && l === 'string' && a === 'string' && i === 'boolean' && v === 'string'),
   `every row is one shape: kind, tier, label, about, installed, verb (${shape.length} rows)`);
ok(await page.evaluate(() => /Not for this node/.test(document.querySelector('.doc .librarytab .pghead')?.textContent || '') || !lib.facts?.other_platform)
   && await page.evaluate(n => (lib.facts?.other_platform || 0) === n, ALL.filter(r => r.wrong_platform && !r.too_new).length),
   'the head counts the cards not for this node (R170 step 9)');
// Who stands behind a card, in the words a person reads (the operator, 12
// Nov): Packaged by Aerie for what AerieOS ships or wrote, never the stored
// word official.
const tierPills = await page.$$eval('.doc .librarytab .lcard', cs => cs.map(c => c.querySelector('.lcmeta .pill')?.textContent.trim() || ''));
ok(tierPills.length > 0 && tierPills.every(t => /^(packaged by aerie|verified|vetted|sideloaded)$/.test(t)) && tierPills.includes('packaged by aerie'),
   `the tier reads on every card as a pill, in a person's words (${[...new Set(tierPills)].join(', ')})`);
ok(await page.evaluate(() => libTierWord('official') === 'Packaged by Aerie' && libTierWord('verified') === 'Verified'
     && LIB_TIERS.map(([, l]) => l).join(', ') === 'Packaged by Aerie, Verified, Vetted, Sideloaded'),
   'the tier chips are Packaged by Aerie, Verified, Vetted and Sideloaded');
// ...and to the left of that pill a card names who the tool itself is by
// (the operator, 12 Nov): the tier is the pack's, the maker the tool's.
await section("and to the left of that pill a card names who the tool itself is by", async () => {
  // Found by the search, as a person would find one past a shelf's eight.
  await page.fill('.doc .librarytab #libFind', 'jdk');
  await page.waitForSelector('.librarytab .lcard[data-lrow="toolchain:jdk"]', { timeout: 15000 });
  const by = await page.evaluate(() => { const c = document.querySelector('.librarytab .lcard[data-lrow="toolchain:jdk"] .lcmeta');
    return c && { first: c.firstElementChild?.className, text: c.firstElementChild?.textContent, pill: c.querySelector('.pill')?.textContent,
                  left: c.firstElementChild.getBoundingClientRect().right <= c.querySelector('.pill').getBoundingClientRect().left + 1 }; });
  ok(by && by.first === 'lcby' && by.text === 'Eclipse Adoptium' && by.pill === 'packaged by aerie' && by.left,
     `a card names its tool's maker to the left of the pill that says who packaged it (${JSON.stringify(by)})`);
  // What this build ships, not what the live catalog offers: an entry it
  // lists is the catalog's to name (its own check holds it to that).
  const made = await page.evaluate(all => ({ none: all.filter(r => r.tier !== 'sideloaded' && !r.maker && r.kind !== 'pack' && !r.catalog).map(r => `${r.kind}:${r.name}`),
    lint: makerLine(all.find(r => r.name === 'lint-tools') || {}).replace(/<[^>]+>/g, '') }), ALL);
  ok(!made.none.length && /^Put together by AerieOS from other people's work: shellcheck \(Vidar Holen\), .*ruff \(Astral\)/.test(made.lint),
     `every card AerieOS ships names a maker, and one of several makers' tools is AerieOS's with each credited in its Details (${made.none.join(', ') || 'all named'}; ${made.lint.slice(0, 90)})`);
  await page.fill('.doc .librarytab #libFind', '');
  await page.waitForFunction(() => libQ === '' && !document.querySelector('.doc .librarytab .libone'), null, { timeout: 15000 });
});
ok(await page.evaluate(() => {
  const head = document.querySelector('.doc .librarytab .pghead');
  return !!head && /Installed/.test(head.textContent);
}), 'the head says how many are installed, the way a node\'s head does');

// ---- search and chips ----------------------------------------------------
// The server narrows (R256): the search, a chip or a topic is one sorted
// list, a page of it at a time, and the shelves come back with nothing
// narrowed.
const firstTc = HERE.find(r => r.kind === 'toolchain')?.label || '';
await page.fill('.doc .librarytab #libFind', firstTc.slice(0, 4).toLowerCase());
await page.waitForFunction(q => libQ === q && !!document.querySelector('.doc .librarytab .libone .lcard'), firstTc.slice(0, 4).toLowerCase(), { timeout: 15000 });
ok(await page.evaluate(n => document.querySelectorAll('.doc .librarytab .lcard').length < n
   && document.querySelectorAll('.doc .librarytab .lcard').length > 0
   && document.activeElement?.id === 'libFind' && /[?&]q=/.test(location.hash), HERE.length),
   `the search narrows to one list as it is typed, keeps the caret, and the address carries it (${await page.evaluate(() => location.hash)})`);
await page.fill('.doc .librarytab #libFind', '');
await page.waitForFunction(() => libQ === '' && !document.querySelector('.doc .librarytab .libone'), null, { timeout: 15000 });
ok(await page.evaluate(() => !!document.querySelector('.doc .librarytab .libgroup[data-libshelf], .doc .librarytab .libgroup [data-libshelf]') || document.querySelectorAll('.doc .librarytab .libgroup').length > 1),
   '...and emptied puts the shelves back');
if (await page.$('.doc .librarytab [data-libkind="toolchain"]')){
  await page.click('.doc .librarytab [data-libkind="toolchain"]');
  await page.waitForFunction(() => libKind === 'toolchain' && !readBusy('library') && !!document.querySelector('.doc .librarytab .libone'), null, { timeout: 15000 });
  const tcs = HERE.filter(r => groupOf(r) === 'toolchain');
  ok(await page.evaluate(n => [...document.querySelectorAll('.doc .librarytab .lcard')].every(c => c.dataset.lrow.startsWith('toolchain:'))
     && document.querySelectorAll('.doc .librarytab .lcard').length === Math.min(n, 30) && lib.total === n
     && document.querySelector('.doc .librarytab [data-libkind="toolchain"]').classList.contains('on'), tcs.length),
     `a kind chip is that kind's list alone, a page of it, the chip wearing .on (${tcs.length})`);
  // ...and the source chips count within it (the operator, 31 Oct).
  const facet = await page.evaluate(() => Object.fromEntries([...document.querySelectorAll('.doc .librarytab [data-libtier]')]
    .map(b => [b.dataset.libtier, +(b.querySelector('.pill')?.textContent || 0)])));
  const want = Object.fromEntries(['official', 'verified', 'vetted', 'sideloaded'].map(k => [k, tcs.filter(r => r.tier === k).length]).filter(([, c]) => c));
  ok(!Object.keys(facet).length || Object.entries(want).every(([k, c]) => facet[k] === c),
     `...and the source chips count that kind's cards alone (${JSON.stringify({ want, facet })})`);
  await page.click('.doc .librarytab [data-libkind=""]');
  await page.waitForFunction(() => libKind === '' && !document.querySelector('.doc .librarytab .libone'), null, { timeout: 15000 });
  ok(await page.$$eval('.doc .librarytab .libgroup', ds => ds.length > 1), '...and All puts the shelves back');
} else ok(true, 'one kind only here, so no kind chips (chips need two groups)');

// The address is the list (R256): a reload of one with the search in it
// lands on the same list, the read sent before the address was applied
// asked again rather than dropped.
await section("a reload of a list lands on the same list", async () => {
  const word = (HERE.find(r => r.kind === 'toolchain')?.name || 'jdk').slice(0, 3);
  await page.fill('.doc .librarytab #libFind', word);
  await page.waitForFunction(q => libQ === q && /[?&]q=/.test(location.hash) && !!document.querySelector('.doc .librarytab .libone .lcard'), word, { timeout: 15000 });
  const before = await page.$$eval('.doc .librarytab .libone .lcard', cs => cs.map(c => c.dataset.lrow).join());
  await page.reload();
  await ready(page);
  await page.waitForFunction(() => !!document.querySelector('.doc .librarytab .libone .lcard'), null, { timeout: 20000 }).catch(() => {});
  const after = await page.evaluate(() => ({ q: libQ, rows: [...document.querySelectorAll('.doc .librarytab .libone .lcard')].map(c => c.dataset.lrow).join(), box: document.querySelector('#libFind')?.value }));
  ok(after.q === word && after.box === word && after.rows === before, `a reload of a list lands on the same list (${JSON.stringify({ word, before: before.slice(0, 60), after: { ...after, rows: after.rows.slice(0, 60) } })})`);
  await page.fill('.doc .librarytab #libFind', '');
  await page.waitForFunction(() => libQ === '' && !document.querySelector('.doc .librarytab .libone'), null, { timeout: 15000 });
});

// Rows (R256): at a desk a card a line, its head, what it is and its verbs
// side by side; on a phone two lines, the name across the card and the
// verbs beside its pills; anything else under those.
await section("Rows: a card a line at a desk and on a phone", async () => {
  const wrong = [];
  for (const kind of ['toolchain', 'agent', 'update']){
    if (!(await page.$(`.doc .librarytab [data-libkind="${kind}"]`))) continue;
    await page.evaluate(k => { libView = 'list'; libKind = k; libPagesFrom(); shellSync(); loadLibrary(); }, kind);
    await page.waitForFunction(k => libKind === k && !readBusy('library') && !!document.querySelector('.doc .librarytab .libone .lgrid.lrows > .lcard'), kind, { timeout: 15000 });
    for (const width of [1280, 393, 344]){
      await page.setViewportSize({ width, height: width > 600 ? 900 : 851 });
      await page.waitForTimeout(250);
      wrong.push(...(await libraryRowsWrong(page)).map(w => `${kind} at ${width}: ${w}`));
    }
    await page.setViewportSize({ width: 1280, height: 900 });
  }
  ok(!wrong.length, `Rows keep each card's name and its verbs on its own lines, two lines on a phone, at a desk and at 393 and 344 (${wrong.slice(0, 3).join('; ') || 'all well'})`);
  await page.evaluate(() => { libView = ''; libKind = ''; libPagesFrom(); shellSync(); loadLibrary(); });
  await page.waitForFunction(() => libKind === '' && !readBusy('library') && !document.querySelector('.doc .librarytab .libone'), null, { timeout: 15000 });
});

// What runs only on other systems is left out of a list and counted, and
// shown on a press, each card's Install dead with the reason on it.
const off = ALL.find(r => r.wrong_platform && !r.too_new);
if (off){
  await page.click(`.doc .librarytab [data-libkind="${groupOf(off)}"]`);
  await page.waitForSelector('.doc .librarytab .libhidden [data-liball="1"]', { timeout: 15000 });
  const n = ALL.filter(r => r.wrong_platform && !r.too_new && groupOf(r) === groupOf(off)).length;
  ok(await page.$eval('.doc .librarytab .libhidden', (d, n) => new RegExp(`^${n} more`).test(d.textContent.trim()), n)
     && !(await page.$(`.doc .librarytab .lcard[data-lrow="${off.kind}:${off.name}"]`)),
     `a list leaves out what runs only on other systems and says how many (${n})`);
  await page.click('.doc .librarytab .libhidden [data-liball="1"]');
  await page.waitForSelector(`.doc .librarytab .lcard[data-lrow="${off.kind}:${off.name}"]`, { timeout: 15000 });
  ok(await page.$eval(`.doc .librarytab .lcard[data-lrow="${off.kind}:${off.name}"]`, c => /not for this node/.test(c.querySelector('.state')?.textContent || '')
       && [...c.querySelectorAll('[data-libact]')].every(b => b.disabled)) && /[?&]all=1/.test(await page.evaluate(() => location.hash)),
     '...and shown on a press, marked not for this node with its Install dead');
  await page.click('.doc .librarytab .libhidden [data-liball="0"]');
  await page.click('.doc .librarytab [data-libkind=""]');
  await page.waitForFunction(() => libKind === '' && !libAll && !document.querySelector('.doc .librarytab .libone'), null, { timeout: 15000 });
} else ok(true, 'nothing here is for another system');

// The page's buttons on the search's line under the head, the bar empty
// (the operator, 29 Oct: they stood over a gap).
ok(await page.evaluate(() => !!document.querySelector('.doc .librarytab .libsearchrow #libFind')
   && !!document.querySelector('.doc .librarytab .libsearchrow .actbar [data-libcheck]')
   && !document.querySelector('.pane .bar [data-libcheck], .doc .librarytab .docbarrow [data-libcheck]')),
   'Check for updates and Add your own sit on the search\'s line, not in a bar over the head');

// Installed, the chip after All (the operator, 29 Oct): the cards
// installed on this node, each in its own kind's section; no chip while
// nothing is.
if (HERE.some(r => r.installed)){
ok(await page.evaluate(() => {
  const cs = [...document.querySelectorAll('.doc .librarytab [data-chips="libkind"] .chip')];
  return cs[1]?.dataset.libkind === 'installed' && /^Installed/.test(cs[1].textContent.trim());
}), 'Installed is the chip after All');
await page.click('.doc .librarytab [data-libkind="installed"]');
await page.waitForFunction(() => libKind === 'installed' && !readBusy('library') && !!document.querySelector('.doc .librarytab .libone'), null, { timeout: 15000 });
ok(await page.evaluate(want => {
  const cards = [...document.querySelectorAll('.doc .librarytab .lcard')];
  return cards.length > 0 && cards.length === Math.min(want.length, 30) && cards.every(c => want.includes(c.dataset.lrow));
}, HERE.filter(r => r.installed).map(r => `${r.kind}:${r.name}`)), '...and pressed it lists what is installed here and nothing else');
await page.click('.doc .librarytab [data-libkind=""]');
await page.waitForFunction(() => libKind === '' && !document.querySelector('.doc .librarytab .libone'), null, { timeout: 15000 });
} else ok(!(await page.$('.doc .librarytab [data-libkind="installed"]')), 'nothing installed here, so no Installed chip');

// Updates, the chip after Installed (the operator, 29 Oct): the cards with an
// update due, each in its own section, and no chip while none is.
if (HERE.some(r => r.update || r.repin)){
  ok(await page.evaluate(() => {
    const cs = [...document.querySelectorAll('.doc .librarytab [data-chips="libkind"] .chip')];
    const at = cs.findIndex(c => c.dataset.libkind === 'update');
    return at > 0 && at <= 2 && cs.slice(1, at).every(c => c.dataset.libkind === 'installed') && /^Updates/.test(cs[at].textContent.trim());
  }), 'Updates is the chip after Installed while an update is due');
  await page.click('.doc .librarytab [data-libkind="update"]');
  await page.waitForFunction(() => libKind === 'update' && !readBusy('library') && !!document.querySelector('.doc .librarytab .libone'), null, { timeout: 15000 });
  ok(await page.evaluate(want => {
    const cards = [...document.querySelectorAll('.doc .librarytab .lcard')];
    return cards.length === Math.min(want.length, 30) && cards.every(c => want.includes(c.dataset.lrow));
  }, HERE.filter(r => r.update || r.repin).map(r => `${r.kind}:${r.name}`)), '...and pressed it lists the cards with an update due and no others');
  await page.click('.doc .librarytab [data-libkind=""]');
  await page.waitForFunction(() => libKind === '' && !document.querySelector('.doc .librarytab .libone'), null, { timeout: 15000 });
} else ok(!(await page.$('.doc .librarytab [data-libkind="update"]')), 'no update due here, so no Updates chip');

// ---- Details opens the entry's own page (R183) ------------------------------
// A card stays a card; Details opens that entry's page, a page a press opens
// with the small top header's Back to the Library, its body what Details
// says: the catalog's entry alone.
const ENTRY = k => `.doc .entrytab [data-entry="${k}"]`;
const toEntry = async k => {
  await page.evaluate(k => openEntry(libNode, k), k);
  await page.waitForSelector(`${ENTRY(k)} .ldetail`, { timeout: 15000 });
};
const toLibrary = async () => {
  await page.evaluate(() => openLibrary());
  await page.waitForSelector('.doc .librarytab .lcard', { timeout: 15000 });
};
await section("a toolchain card to open", async () => {
  const key = await page.evaluate(() => document.querySelector('.doc .librarytab .lcard[data-lrow^="toolchain:"]')?.dataset.lrow || '');
  ok(!!key, `a toolchain card to open (${key})`);
  const sel = `.doc .librarytab .lcard[data-lrow="${key}"]`;
  ok(await page.$eval(sel, r => !r.querySelector('.ldetail') && r.querySelector('[data-libmore]').textContent === 'Details'),
     'a card is its name and two lines, with Details, and opens nothing in place');
  await page.click(`${sel} [data-libmore]`);
  await page.waitForSelector(`${ENTRY(key)} .ldetail`, { timeout: 15000 });
  const pg = await page.evaluate(k => ({ hash: location.hash, want: '#/build/library/' + encodeURIComponent(libNode) + '/' + encodeURIComponent(k),
    back: document.querySelector('.pane .bar .backhead [data-shellback]')?.textContent.trim() || '',
    name: document.querySelector('.pane .bar .backhead .backof')?.textContent.trim() || '',
    label: (entryLib?.rows || []).find(r => `${r.kind}:${r.name}` === k)?.label || '' }), key);
  ok(pg.hash === pg.want && /Library/.test(pg.back) && pg.name === pg.label,
     `...Details opens the entry's own page at its own address, its top header's Back to the Library and its name (${JSON.stringify(pg)})`);
  await page.click('.pane .bar [data-shellback]');
  await page.waitForFunction(() => tabOf(panes[0])?.kind === 'library', null, { timeout: 10000 });
  ok(true, '...and Back returns to the Library');
});

// ---- the whole description (step 2) -----------------------------------------
// An app's page holds its compose file and what its panel asks for;
// a toolchain's what it adds to a session and its terms.
await section("the whole description", async () => {
  const app = HERE.find(r => r.kind === 'app') ? `app:${HERE.find(r => r.kind === 'app').name}` : '';
  if (app){
    await toEntry(app);
    ok(await page.$eval(ENTRY(app), r => /image:/.test(r.querySelector('.libcompose')?.textContent || '')
       && /Asks for /.test(r.querySelector('.ldetail').textContent) && /New container opens the Containers page/.test(r.querySelector('.ldetail').textContent)),
       `an app's page holds its compose file, what its panel asks for and how New container makes it one (${app})`);
    // ...and whether every image it runs is named by its digest, in one
    // line: the fixture's apps are written in pack format 5, so they are.
    const held = await page.$eval(ENTRY(app), r => r.querySelector('.ldetail .tcheld')?.textContent || '');
    const drawn = await page.evaluate(() => { const d = document.createElement('div');
      const row = h => { d.innerHTML = libDetail({ kind: 'app', name: 'x', label: 'X', port: 1, fields: [], held: h }); return d.querySelector('.tcheld')?.textContent || ''; };
      return [row({ word: 'pinned', why: '' }), row({ word: 'open', why: 'web names its image by a tag alone' }), row(null)]; });
    ok(held === 'Every image it runs is named by its digest.' && drawn[0] === held
       && drawn[1] === 'Its images are named by tag alone: a tag is whatever was last pushed under it.' && drawn[2] === '',
       `...and says in one line whether its images are named by digest (${held} | ${drawn[1]})`);
  } else ok(true, 'no app rows here (the account may not make containers)');
  const tcRow = ALL.find(x => x.kind === 'toolchain' && (x.tool || x.terms?.length));
  const tc = tcRow ? `toolchain:${tcRow.name}` : '';
  if (tc){
    await toEntry(tc);
    ok(await page.$eval(`${ENTRY(tc)} .ldetail`, d => /aerie tool|Licensed|accept/.test(d.textContent)),
       `a toolchain's page says what it adds to a session and its terms (${tc})`);
  }
  if (ALL.some(r => r.kind === 'agent' && r.name === 'claude-code')){
    await toEntry('agent:claude-code');
    ok(await page.$eval(`${ENTRY('agent:claude-code')} .ldetail`, d => /session account/.test(d.textContent) && /Installed page/.test(d.textContent) && !d.querySelector('[data-signin]')),
       "Claude Code's page holds its facts, pointing at the Installed page for this person's sign-in (R172: the Library is the catalog)");
  }
  await toLibrary();
});

// ---- the verbs are the pages' own ------------------------------------------
// Install on a toolchain row that is not installed: the toolchain job on
// the node, which the stub agent answers at once (it fails the install, as
// toolchains.mjs's node tests find), and the row then says what the
// job said: installed, or what failed under the row, as that page does.
await section("the verbs are the pages' own", async () => {
  const name = HERE.find(r => r.kind === 'toolchain' && !r.installed && r.verb === 'install')?.name || '';
  if (name){
    // Found by its name, as a card past a shelf's eight is.
    await page.fill('.doc .librarytab #libFind', name);
    await page.waitForSelector(`.doc .librarytab [data-libact="install"][data-libname="${name}"]`, { timeout: 15000 });
    await page.click(`.doc .librarytab [data-libact="install"][data-libname="${name}"]`);
    await page.waitForFunction(n => lib.job && !lib.job.running && lib.job.action === 'install'
      && (libFind(r => r.kind === 'toolchain' && r.name === n)?.installed || lib.job.errors?.[n]), name, { timeout: 60000 });
    const said = await page.evaluate(n => ({installed: !!libFind(r => r.kind === 'toolchain' && r.name === n)?.installed, err: lib.job.errors?.[n] || ''}), name);
    ok(true, `Install on ${name} ran the toolchain job on the node (${said.installed ? 'installed' : said.err})`);
    ok(await page.$eval(`.doc .librarytab .lcard[data-lrow="toolchain:${name}"]`, (r, s) => s.installed ? !!r.querySelector('[data-libact="remove"]')
       : r.querySelector('.sub.bad')?.textContent === s.err, said),
       said.installed ? '...and an installed row offers Remove' : '...and what failed is said under the row');
    await page.fill('.doc .librarytab #libFind', '');
    await page.waitForFunction(() => libQ === '' && !document.querySelector('.doc .librarytab .libone'), null, { timeout: 15000 });
  } else ok(true, 'nothing uninstalled to install on the stub');
});
// Install on an app row opens New container on that app's panel (R238).
if (await page.$('.doc .librarytab [data-libkind="app"][data-libact="install"]')){
  const id = await page.$eval('.doc .librarytab [data-libkind="app"][data-libact="install"]', b => b.dataset.libname);
  await page.click('.doc .librarytab [data-libkind="app"][data-libact="install"]');
  await page.waitForFunction(() => !document.getElementById('cmodal').hidden, null, { timeout: 10000 });
  await page.waitForFunction(id => cAppCur?.id === id && !document.getElementById('cAppField').hidden, id, { timeout: 10000 });
  ok(await page.$eval('.doc .librarytab [data-libkind="app"][data-libact="install"]', b => b.textContent.trim() === 'New container'),
     `an app's press reads New container, and opens that dialog on ${id}'s panel`);
  const data = await page.evaluate(() => { const e = document.querySelector('#cAppFields [data-avar="DATA"]'); return e ? e.value || e.placeholder : null; });
  ok(data === null || data.endsWith(`apps/${id}`), `...a data folder, where it asks for one, is that app's own, not one app's for every one (${data})`);
  await page.evaluate(() => { $('cmodal').hidden = true; });
}

// ---- the bar's Check for updates (step 5) ------------------------------------
// The check is the Toolchains job's: the bar says it is checking while it
// runs, and the head says when versions were last checked once it ends.
await section("the bar's Check for updates", async () => {
  await page.click('.doc .librarytab [data-libcheck]');
  await page.waitForFunction(() => lib?.job?.action === 'check' && !lib.job.running, null, { timeout: 60000 });
  ok(await page.$eval('.doc .librarytab [data-libcheck]', b => !b.disabled && /check/i.test(b.textContent)),
     'Check for updates runs the check job on the node and the bar comes back');
  // The stub's check leaves no time on the node's record, so the fact is
  // drawn only where the node has one; a fact with nothing to say is left out.
  // ...drawn on the paint after the read lands, so waited for rather than read at once.
  const when = await page.waitForFunction(() => {
    const said = /Versions checked/.test(document.querySelector('.doc .librarytab .pghead')?.textContent || '');
    return said === !!(lib.store?.checked) ? {checked: lib.store?.checked || 0, said} : null;
  }, null, { timeout: 10000 }).then(h => h.jsonValue());
  ok(when.said === !!when.checked, `...and the head says when versions were checked only once the node has a time (${when.checked ? 'said' : 'none yet, not drawn'})`);
});

// ---- Add your own: an app of the person's own (step 3) -----------------------
// The bar's Add your own opens one dialog for a tool pack or an app; an app
// is a compose file with the known blanks, looked at before it is kept,
// offered on an Apps card as sideloaded with Edit, and in New container.
await section("Add your own", async () => {
  const COMPOSE = 'services:\n  notes:\n    image: ghcr.io/example/notes:2.4.1\n    ports:\n      - "${PORT}:8080"\n    volumes:\n      - ${DATA}/notes:/data\n';
  await page.evaluate(async () => { await postJSON('/api/nasapps', {action: 'remove', app: 'notes'}); });   // a run cut short may have left it
  await page.click('.doc .librarytab [data-libadd]');
  await page.waitForSelector('#tpmodal:not([hidden]) [data-tpwhat="app"]', { timeout: 10000 });
  ok(await page.$eval('#tpmodal h3', h => h.textContent === 'Add your own'), 'Add your own opens the one dialog, asking what is being added');
  await page.click('#tpmodal [data-tpwhat="app"]');
  await page.waitForSelector('#tpmodal #tpAppCompose');
  await page.fill('#tpmodal #tpAppName', 'Notes');
  await page.fill('#tpmodal #tpAppId', 'notes');
  await page.fill('#tpmodal #tpAppWhat', 'a notebook with a web page');
  await page.fill('#tpmodal #tpAppPort', '8080');
  await page.fill('#tpmodal #tpAppCompose', 'services:\n  notes:\n    image: ghcr.io/example/notes:latest\n');
  await page.click('#tpmodal [data-tplook]');
  await page.waitForFunction(() => tpForm.error || tpForm.seen, null, { timeout: 10000 });
  ok(await page.evaluate(() => /not pinned/.test(tpForm.error) && !document.querySelector('#tpmodal [data-tpadd]')),
     'Look refuses an image that is not pinned to a tag, and nothing can be added until it is');
  await page.fill('#tpmodal #tpAppCompose', COMPOSE);
  await page.click('#tpmodal [data-tplook]');
  await page.waitForSelector('#tpmodal [data-tpadd]', { timeout: 10000 });
  ok(await page.$eval('#tpmodal .tpseen', d => /notes/.test(d.textContent) && /ghcr.io\/example\/notes:2.4.1/.test(d.textContent) && /DATA/.test(d.textContent)),
     '...and a good one is shown as what it runs and the blanks it takes before Add');
  await page.click('#tpmodal [data-tpadd]');
  await page.waitForFunction(() => document.getElementById('tpmodal').hidden, null, { timeout: 15000 });
  // Found by its name, past the Apps shelf's eight.
  await page.fill('.doc .librarytab #libFind', 'notes');
  await page.waitForSelector('.doc .librarytab .lcard[data-lrow="app:notes"]', { timeout: 15000 });
  ok(await page.$eval('.doc .librarytab .lcard[data-lrow="app:notes"]', c => /sideloaded/.test(c.querySelector('.lcmeta').textContent)
     && !!c.querySelector('[data-libact="edit"]') && !!c.querySelector('[data-libact="install"]')),
     'Add keeps it: an Apps card wearing sideloaded, with Install and Edit');
  const offered = await page.evaluate(async () => { cApps = null; return (await loadNasApps()).some(a => a.id === 'notes' && a.tier === 'sideloaded'); });
  ok(offered, '...and New container offers it among the apps');
  await page.click('.doc .librarytab .lcard[data-lrow="app:notes"] [data-libact="edit"]');
  await page.waitForFunction(() => !document.getElementById('tpmodal').hidden && document.querySelector('#tpmodal #tpAppCompose')?.value.includes('notes:2.4.1'), null, { timeout: 10000 });
  ok(await page.$eval('#tpmodal #tpAppId', i => i.disabled && i.value === 'notes'), 'Edit opens it as kept, its id fixed');
  await page.click('#tpmodal [data-tprmapp]');
  // The ask slides in, so it is pressed by the page rather than by a pointer
  // waiting for it to settle; found and pressed in one look, since under a
  // whole run's load it was gone again between a wait and the press (B933).
  await page.waitForFunction(() => { const b = document.querySelector('.modal.askdlg:not([hidden]) [data-ai="0"]');
    if (!b) return false; b.click(); return true; }, null, { timeout: 10000 });
  await page.waitForFunction(() => document.getElementById('tpmodal').hidden && !document.querySelector('.doc .librarytab .lcard[data-lrow="app:notes"]'), null, { timeout: 15000 });
  await page.fill('.doc .librarytab #libFind', '');
  ok(true, 'Remove in there takes it off the catalog, and the card goes');
});

// ---- an app's own fields (R238) --------------------------------------------
// An app of pack format 4, kept as the catalog's are, opens New container on
// its panel: each kind of field drawn as its answer is, its file read-only,
// a variable it sets refused in the Environment by name; a container made
// from it opens again with Configure on the same panel, its secret kept,
// and Edit the definition by hand leaves it a written container.
await section("an app's panel", async () => {
  const LEDGER = 'services:\n  ledger:\n    image: ghcr.io/example/ledger:3.1.0\n    environment:\n      TZ: ${TZ}\n      DB_PASSWORD: ${DB_PASSWORD}\n'
    + '      CURRENCY: ${CURRENCY}\n      SIGNUPS: ${SIGNUPS}\n      LLM_BASE: ${LLM_URL}\n      LLM_API_KEY: ${LLM_KEY}\n    ports:\n      - "${PORT}:8020"\n      - "${SYNC_PORT}:7070"\n    volumes:\n      - ${BOOKS}:/books\n';
  const FIELDS = [
    {var: 'BOOKS', kind: 'folder', label: 'Its books', default: 'ledger/books', example: '/mnt/tank/ledger', help: '', required: true},
    {var: 'SYNC_PORT', kind: 'port', label: 'Sync port', default: 7070, help: '', required: true},
    {var: 'DB_PASSWORD', kind: 'secret', label: 'Database password', default: '', help: '', required: false},
    {var: 'CURRENCY', kind: 'choice', label: 'Currency', default: 'USD', help: '', required: false,
     choices: [{value: 'EUR', label: 'Euro'}, {value: 'USD', label: 'US dollar'}]},
    {var: 'SIGNUPS', kind: 'switch', label: 'Others may sign up', default: false, help: '', required: false},
    {var: 'LLM_URL', kind: 'router', label: 'Model router', key: 'LLM_KEY', path: '/v1', default: '', help: '', required: false}];
  const f = `${DIR}/state/sideapps.json`;
  let d = {};
  try { d = JSON.parse(readFileSync(f, 'utf8')); } catch { d = {}; }
  d.apps = {...(d.apps || {}), ledger: {name: 'Ledger', what: 'a ledger with a database beside it', port: 8020, media: false, compose: LEDGER,
    secrets: [], by: 'test', at: 1, tier: 'aerie', maker: 'Example Labs', credits: [], fields: FIELDS,
    pin: {url: 'https://example.com/catalog', commit: 'a'.repeat(40), sha256: 'b'.repeat(64), path: 'packs/apps/ledger'}}};
  writeFileSync(f, JSON.stringify(d));
  await page.evaluate(() => { cApps = null; openNewContainerApp('ledger'); });
  await page.waitForFunction(() => cAppCur?.id === 'ledger' && !document.getElementById('cAppField').hidden, null, { timeout: 15000 });
  const drawn = await page.evaluate(() => Object.fromEntries([...document.querySelectorAll('#cAppFields [data-avar]')].map(e =>
    [e.dataset.avar, e.type === 'checkbox' ? 'tick' : e.tagName === 'SELECT' ? `pulldown:${e.value}` : e.list ? 'suggested' : e.type])));
  ok(JSON.stringify(drawn) === JSON.stringify({BOOKS: 'suggested', SYNC_PORT: 'number', DB_PASSWORD: 'password', CURRENCY: 'pulldown:USD', SIGNUPS: 'tick', LLM_URL: 'pulldown:'}),
     `each kind is drawn as its answer is: a folder with suggestions, a port a number, a secret masked, a choice a pulldown at its default, a switch a tick, a model router a pulldown (${JSON.stringify(drawn)})`);
  ok(await page.evaluate(() => { const r = document.querySelector('#cAppFields [data-avar="LLM_URL"]');
       return r.disabled && /No model router is deployed/.test(r.parentElement.querySelector('.hint')?.textContent || ''); }),
     '...and with no model router deployed, the router field is dead with why on its row');
  ok(await page.evaluate(() => /Ledger/.test($('cAppHead').textContent) && /Example Labs/.test($('cAppHead').textContent)
     && !!$('cAppTz') && !!$('cAppPort') && !$('cAppIds')),
     "...headed by its name and who it is by, with AerieOS's own its compose reads (time zone and port) and not one it does not (who it runs as)");
  ok(await page.evaluate(() => $('cYml').readOnly && $('cYml').value.includes('ghcr.io/example/ledger:3.1.0') && $('cTabForm').hidden && !$('cByHandBar').hidden),
     "...its file read-only as the catalog wrote it, no From an image, and Edit the definition by hand under it");
  await page.fill('#cName', 'ledger-one');
  await page.fill('#cAppFields [data-avar="BOOKS"]', '/mnt/tank/ledger');
  await page.evaluate(() => { cSwitch('env'); });
  await page.fill('#cEnv', 'SYNC_PORT=1\n');
  await page.click('#cGo');
  await page.waitForFunction(() => !document.getElementById('cErrWrap').hidden, null, { timeout: 15000 });
  ok(/SYNC_PORT is set in Ledger's fields above, as Sync port/.test(await page.$eval('#cErr', e => e.textContent)),
     'a variable its panel sets, typed in the Environment, is refused by name');
  await page.fill('#cEnv', 'LEDGER_LOG=info\n');
  await page.evaluate(() => { $('cErrWrap').hidden = true; });
  await page.click('#cGo');
  await page.waitForFunction(() => document.getElementById('cmodal').hidden || !document.getElementById('cErrWrap').hidden, null, { timeout: 30000 });
  const madeIt = await page.$eval('#cmodal', m => m.hidden);
  ok(madeIt, `Create makes it${madeIt ? '' : ` (${await page.$eval('#cErr', e => e.textContent)})`}`);
  const read = await page.evaluate(() => postJSON('/api/container', {action: 'read', name: 'ledger-one'}));
  const env = Object.fromEntries((read.env || '').split('\n').filter(Boolean).map(l => [l.split('=')[0], l.slice(l.indexOf('=') + 1)]));
  ok(read.app?.id === 'ledger' && env.BOOKS === '/mnt/tank/ledger' && env.CURRENCY === 'USD' && env.SIGNUPS === 'false' && env.SYNC_PORT === '7070'
     && (env.DB_PASSWORD || '').length >= 20 && env.LEDGER_LOG === 'info' && read.app.extra === 'LEDGER_LOG=info\n' && env.LLM_URL === '' && env.LLM_KEY === '',
     'its environment is the panel\'s values, a secret made for it, and the other variable kept apart; the container keeps which app it came from');
  // Another of the same app is a container of its own (the Library's rule:
  // each press makes another): its ports past the ones ledger-one holds,
  // though nothing answers on them yet, and its folder named for it.
  await page.evaluate(() => { $('cmodal').hidden = true; openNewContainerApp('ledger'); });
  await page.waitForFunction(() => cAppCur?.id === 'ledger' && !document.getElementById('cAppField').hidden, null, { timeout: 15000 });
  const second = await page.evaluate(() => ({ name: $('cName').value, port: $('cAppPort').value,
    sync: document.querySelector('#cAppFields [data-avar="SYNC_PORT"]').value }));
  ok(second.name === 'ledger' && second.port === '8021' && second.sync === '7071',
     `a second from the same app is offered a free name and the ports after the ones the first holds (${JSON.stringify(second)})`);
  const follows = await page.evaluate(() => { cAppRoots = [{path: '/mnt/tank'}]; cAppFollow();
    const b = document.querySelector('#cAppFields [data-avar="BOOKS"]'), at = b.value;
    $('cName').value = 'Ledger Two'; $('cName').dispatchEvent(new Event('input'));
    return { at, now: b.value, offered: [...b.list.options].map(o => o.value) }; });
  ok(follows.at === '/mnt/tank/ledger/books' && follows.now === '/mnt/tank/ledger-two/books' && follows.offered[0] === '/mnt/tank/ledger-two/books',
     `...its folder named for it, following the name as it is typed (${JSON.stringify(follows)})`);
  await page.fill('#cName', 'ledger-one');
  await page.fill('#cAppFields [data-avar="BOOKS"]', '/mnt/tank/ledger2');
  await page.click('#cGo');
  await page.waitForFunction(() => !document.getElementById('cErrWrap').hidden, null, { timeout: 15000 });
  ok(/ledger-one is another container's name: give this Ledger a name of its own/.test(await page.$eval('#cErr', e => e.textContent)),
     "...and a name another container has is refused in the person's words");
  await page.evaluate(() => { $('cErrWrap').hidden = true; $('cmodal').hidden = true; });
  await page.evaluate(() => openEditContainer('ledger-one'));
  await page.waitForFunction(() => cEditing === 'ledger-one' && cAppCur?.id === 'ledger' && !document.getElementById('cAppField').hidden, null, { timeout: 15000 });
  ok(await page.evaluate(s => $('cTitle').textContent === 'Configure ledger-one' && document.querySelector('#cAppFields [data-avar="DB_PASSWORD"]').value === s
     && document.querySelector('#cAppFields [data-avar="BOOKS"]').value === '/mnt/tank/ledger' && $('cEnv').value === 'LEDGER_LOG=info\n', env.DB_PASSWORD),
     'Configure opens the same panel, each value read back from its environment');
  await page.selectOption('#cAppFields [data-avar="CURRENCY"]', 'EUR');
  await page.click('#cGo');
  await page.waitForFunction(() => document.getElementById('cmodal').hidden || !document.getElementById('cErrWrap').hidden, null, { timeout: 30000 });
  const again = await page.evaluate(() => postJSON('/api/container', {action: 'read', name: 'ledger-one'}));
  ok(/CURRENCY=EUR/.test(again.env) && again.app?.values?.DB_PASSWORD === env.DB_PASSWORD,
     '...a value changed in its field is saved there, and the secret is never made again');
  await page.evaluate(() => openEditContainer('ledger-one'));
  await page.waitForFunction(() => cEditing === 'ledger-one' && cAppCur?.id === 'ledger', null, { timeout: 15000 });
  await page.click('#cByHand');
  await page.waitForFunction(() => { const b = document.querySelector('.modal.askdlg:not([hidden]) [data-ai="0"]');
    if (!b) return false; b.click(); return true; }, null, { timeout: 10000 });
  await page.waitForFunction(() => cAppHand && !document.getElementById('cAppLeft').hidden, null, { timeout: 10000 });
  ok(await page.evaluate(() => $('cAppPanel').hidden && /Edited by hand: Ledger's fields no longer apply/.test($('cAppLeft').textContent)
     && !$('cYml').readOnly && /CURRENCY=EUR/.test($('cEnv').value) && /LEDGER_LOG=info/.test($('cEnv').value)),
     'Edit the definition by hand asks first, folds the panel to a line and leaves the file and the environment as text, the values as they stood');
  await page.click('#cGo');
  await page.waitForFunction(() => document.getElementById('cmodal').hidden || !document.getElementById('cErrWrap').hidden, null, { timeout: 30000 });
  const left = await page.evaluate(() => postJSON('/api/container', {action: 'read', name: 'ledger-one'}));
  ok(left.app === null && /CURRENCY=EUR/.test(left.env), '...and saved so, it is a written container like any other');
  await page.evaluate(() => postJSON('/api/devapp', {project: 'ledger-one', instance: 'main', action: 'remove'}));
  // ...gone before the next section: a remove job still running moves the
  // page's reads under whatever comes after it.
  await page.waitForFunction(async () => {
    try { return !!(await postJSON('/api/container', {action: 'read', name: 'ledger-one'})).error; } catch (e) { return true; }
  }, null, { timeout: 60000, polling: 500 });
  delete d.apps.ledger;
  writeFileSync(f, JSON.stringify(d));
});

// ---- a service's card: the catalog's entry alone (R172) ----------------------
// The model router is a Services card whose Install is dead until something
// is behind it, set on the Installed page; its Details show the entry and
// draw no Configure of their own.
await section("a service's card", async () => {
  const RT = '.doc .librarytab .lcard[data-lrow="service:model-router"]';
  ok(await page.$(RT) !== null && await page.$eval(RT, c => /packaged by aerie/.test(c.querySelector('.lcmeta').textContent) && c.querySelector('[data-libact="install"]')?.disabled === true),
     'the model router is a Services card, packaged by Aerie, its Install dead while nothing is behind it');
  await toEntry('service:model-router');
  ok(await page.$eval(ENTRY('service:model-router'), c => !c.querySelector('.lcform') && !c.querySelector('[data-signin]') && /Installed page/.test(c.querySelector('.ldetail').textContent)),
     '...and its page is the entry alone, pointing at the Installed page for what is set per node');
  await toLibrary();
});

// ---- no node ---------------------------------------------------------------
// A read of the nodes in flight (the poll's) lands after the list is
// emptied and fills it again, so it is emptied again until the page says
// there is none (B978).
await page.waitForFunction(() => {
  if (document.querySelector('.doc .librarytab .libnone')) return true;
  if (!readBusy('nodes') && !readBusy('library') && (nodesList?.length || libNode || lib)){ nodesList = []; nodesStale = false; libNode = ''; lib = null; loadLibrary(); }
  return false;
}, null, { timeout: 20000, polling: 300 });
ok(await page.evaluate(() => !document.querySelector('.doc .librarytab .lcard') && !document.querySelector('.pane .bar #ndPick')),
   'with no node enrolled it says to enroll one, and offers nothing');
await page.evaluate(() => { nodesList = null; nodesStale = true; libNode = ''; lib = null; loadLibrary(); });
await page.waitForSelector('.pane .bar #ndPick', { timeout: 20000 });

await done(browser);
