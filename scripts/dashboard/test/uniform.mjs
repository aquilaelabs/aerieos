// The document-tab conformance suite: the hard rules every tab kind is held
// to, generically, so a new tab cannot ship its own idea of the chrome.
//
// This file exists because the rules kept being re-broken: three tabs in a
// row landed with browser-default controls, a filter bar flush against the
// edge, or rows on the sidebar's tighter inset, each fixed by inverting a
// mechanism (the global field skin, the band tokens, the doc-tab groups),
// each found by a person noticing. The mechanisms make conformance cheap;
// this makes deviation LOUD. The rules run for every kind registered in
// TABKINDS that renders a document, discovered from the page itself, so:
//
//   - a new tab kind with no driver below FAILS ("no conformance driver"),
//     which is the enforcement hook: the price of a new tab includes making
//     it conform, not just making it exist;
//   - the rules are computed style and geometry, never class names taken on
//     faith, so passing means the pixels agree, not that the markup claims to.
//
// What is deliberately NOT here: per-kind content checks. Those live in each
// kind's own suite. This file only holds the language every kind shares.
// (lib.mjs's quiet, a pause that is a check of absence, is quietFor here:
// the idle block has a page of its own named quiet.)
import { URL, DIR, launch, newPage, ok, done, ready, sleep, settled, animatedDuring, faded,
         quiet as quietFor, section } from './lib.mjs';

const browser = await launch();
const page = await newPage(browser, { viewport: { width: 1280, height: 900 } });
await page.goto(URL);
await ready(page);

// How each document kind is opened, and what says its content has arrived.
// A new TABKINDS entry must add a line here or the discovery check fails.
// One of three parts (R130): run as one file, uniform held a run's floor at
// six and a half minutes; uniform-b and uniform-c are this file with the
// part set, and each runs the setup above every section and its own
// sections, so the three go side by side on the queue. Run alone with
// BB_UNIFORM_PART unset, this is part a; BB_UNIFORM_PART=all runs them all.
const PART = process.env.BB_UNIFORM_PART || 'a';
const runs = p => PART === 'all' || PART === p;

const DRIVERS = {
  findings: {
    open: async () => {
      await page.evaluate(() => { const c = document.getElementById('cardTools');
        if (c?.classList.contains('closed')) c.querySelector('h2').click(); });
      await page.evaluate(() => openFindingsTab());
    },
    readyWhen: '.fxtab .rule',
  },
  docker: {
    open: () => page.evaluate(() => openDocker()),
    readyWhen: '.dmtab .dmpick',
  },
  // The Library (R170): a section per kind, or the empty band on a box
  // with no agent node.
  library: {
    open: () => page.evaluate(() => openLibrary()),
    readyWhen: '.librarytab .libgroup[data-libgroup="toolchain"], .librarytab .empty',
  },
  // What is installed on a node (R172): a section per kind with anything there.
  installed: {
    open: () => page.evaluate(() => openInstalledTab()),
    readyWhen: '.installedtab details.sect, .installedtab .empty',
  },
  // A machine's files (R224): its roots and the first one's top folder, or
  // the band saying it has none.
  files: {
    open: () => page.evaluate(() => openFilesTab()),
    readyWhen: '.filestab .fxpage, .filestab .empty, .filestab .notice',
  },
  // A Library entry's own page (R183): the first toolchain's on the node.
  entry: {
    open: () => page.evaluate(async () => {
      // One the Library already holds (its shelves, R256), read for nothing
      // more: the entry's page asks /api/library for its own row, and the
      // opening's count holds the page to one ask of it.
      const r = libKnown().find(x => x.kind === 'toolchain' && !x.wrong_platform);
      openEntry(libNode, r ? `toolchain:${r.name}` : 'agent:claude-code');
    }),
    readyWhen: '.entrytab details.sect, .entrytab .notice',
  },
  // An installed thing's own page (R181 step 2): Claude Code's on the node.
  thing: {
    open: () => page.evaluate(async () => {
      if (!inst || !inst.rows) await loadInstalled();
      const r = (inst?.rows || []).find(x => x.kind === 'agent');
      openThing(instNode, r ? `agent:${r.name}` : 'agent:claude-code');
    }),
    readyWhen: '.thingtab details.sect, .thingtab .notice',
  },
  emulator: {
    // The harness's sandbox node reports a store, so the tab draws its head.
    open: () => page.evaluate(() => openEmulator()),
    readyWhen: '.emutab .tchead, .emutab .empty',
  },
  projects: {
    open: () => page.evaluate(() => openProjectsTab()),
    readyWhen: '.projtab .pcard:visible',
  },
  notebook: {
    open: () => page.evaluate(() => openNotebook('alpha', 'roadmap')),
    readyWhen: '.nb .nbview:not([hidden]) .field',
  },
  nodes: {
    // The config plane, not the row: its editors arrive on the tab's own
    // fetch a moment later, and a rule measured on the row alone was
    // measuring a heading over nothing, which is how a mount row's
    // controls came to sit at three different heights unremarked.
    open: () => page.evaluate(() => openNodesTab()),
    readyWhen: '.nodestab .ndconfbody',
  },
  settings: {
    open: () => page.evaluate(() => openSettingsTab()),
    readyWhen: '.settingstab .snav .rrow',
  },
  // The Network page (R165 step 4): Connection and Reach from outside, under its own list.
  network: {
    open: () => page.evaluate(() => openNetworkTab()),
    readyWhen: '.networktab .snav .rrow',
  },
  // The Phone and the CI runner, tools of their own again (R121).
  phone: {
    open: () => page.evaluate(() => openPhoneTab()),
    readyWhen: '.phonetab .row, .doc.on .hint',
  },
  runner: {
    open: () => page.evaluate(() => openRunnerTab()),
    readyWhen: '.runnertab .ndconf, .runnertab .hint',
  },
  notices: {
    open: () => page.evaluate(() => openNotices()),
    readyWhen: '.noticestab details.sect',
  },
  home: {
    open: () => page.evaluate(() => railGo('home')),
    readyWhen: '.hometab .hometiles .tile',
  },
  help: {
    open: () => page.evaluate(() => railGo('help')),
    readyWhen: '.helptab .wkarticle .wkpage',
  },
  // The chat, the dock's Chat tab (R250 step 2): the list, then the page's
  // rules where they apply to a body in the dock.
  chat: {
    open: () => page.evaluate(() => openChatTab()),
    readyWhen: '.chattab .chatlist .chatrow, .chattab .chatlist .hint',
  },
  // Sessions, a page of its own (R250 step 1): the table, or the hint on a
  // box with none running.
  sessions: {
    open: () => page.evaluate(() => railGo('sessions')),
    readyWhen: '.sessionstab .sesstbl, .sessionstab .hint',
  },
  jobs: {
    // Whether the queue has anything in it depends on which suites ran
    // before this one; either drawing carries the bar and the foot band.
    open: () => page.evaluate(() => openJobsTab()),
    readyWhen: '.jobstab .jbrow, .jobstab .empty',
  },
  // The Debug page (R147), the harness starting the controller with
  // DEBUG_MODE=1: ready once its grants section says how many are granted,
  // which it says once the node list its rows offer has landed (its heading
  // shows on a phone, where every fold starts shut).
  debug: {
    open: () => page.evaluate(() => openDebugTab()),
    readyWhen: '.debugtab details[data-sect="debug:grants"] > summary .sst',
  },
  // The Schedules page (R117): the built-in scan's row is always there.
  schedules: {
    open: () => page.evaluate(() => openSchedulesTab()),
    readyWhen: '.schedulestab .schedrow, .schedulestab .empty',
  },
  // The Keys page (R154): the install key's section and what is kept under
  // it, drawn whether the box has a key or none.
  keys: {
    open: () => page.evaluate(() => openKeysTab()),
    readyWhen: '.keystab details[data-sect="keys:kept"]',
  },
  // The Audit page (R158 step 8): the trail's section, with rows or the
  // empty band, drawn for an account that reads the controller's area.
  // This machine (R90 step 8): on the harness's container controller it
  // says it has none, which is the page's own empty.
  machine: {
    open: () => page.evaluate(() => openMachineTab()),
    readyWhen: '.machinetab .ndrow, .machinetab .empty',
  },
  audit: {
    open: () => page.evaluate(() => openAuditTab()),
    readyWhen: '.audittab .auditrow, .audittab .empty',
  },
  storage: {
    // A section per node, or the empty band on a box with none (R169).
    open: () => page.evaluate(() => openStorageTab()),
    readyWhen: '.storagetab [data-stnode], .storagetab .empty',
  },
  nginx: {
    // A section per node, or the empty band on a box with none (R171).
    open: () => page.evaluate(() => openNginxTab()),
    readyWhen: '.nginxtab [data-ngnode], .nginxtab .empty',
  },
  // The Scanners page (R145): the schedule's section is always there.
  scanners: {
    open: () => page.evaluate(() => openScannersTab()),
    readyWhen: '.scannerstab details[data-sect="scanners:schedule"] > summary .sst',
  },
  vms: {
    // A card per project with VMs, or the empty band where there is none
    // or no node has VM host (R91).
    open: () => page.evaluate(() => openVmsTab()),
    readyWhen: '.vmtab [data-vm-key], .vmtab .empty',
  },
  users: {
    // There is always at least one row: the owner, seeded on the first boot,
    // which cannot be deleted and so cannot be absent.
    open: () => page.evaluate(() => openUsersTab()),
    readyWhen: '.userstab [data-upick]',
  },
  roles: {
    // The built-in roles are always there, each a fold.
    open: () => page.evaluate(() => openRolesTab()),
    readyWhen: '.rolestab .rrow',
  },
  profile: {
    open: () => page.evaluate(() => openProfileTab()),
    readyWhen: '.profiletab .snav .rrow',
  },
};

// Every kind that renders a document, from the page's own registry, never a
// hand-kept list here, because a hand-kept list is how a new kind ships
// unmeasured.
const tabKinds = await page.evaluate(() =>
  Object.entries(TABKINDS).filter(([, v]) => v.render).map(([k]) => k));
const undriven = tabKinds.filter(k => !DRIVERS[k]);
// The notebook is one tab kind and EIGHT surfaces, and every loop below
// measured whichever one it happened to be on, which was the Roadmap: the
// driver opens there and bring() focuses a tab it already has. So nine of
// the notebook's views had never been measured for the action-bar language,
// the loose-button rule, destructive-last or the control widths, and six
// words for "delete this row" and 42-word paragraphs grew under a check that
// looked like it covered them (roadmap R70). Each view is a kind of its own
// here, read off the strip the page draws rather than kept as a list, for
// the same reason the tab kinds are.
const NB_VIEWS = await page.evaluate(() =>
  [...new Set([...document.getElementById('nbTpl').content.querySelectorAll('.nbtabs button[data-v]')]
    .map(b => b.dataset.v))]);
for (const v of NB_VIEWS)
  DRIVERS[`notebook:${v}`] = {
    open: () => page.evaluate(w => openNotebook('alpha', w), v),
    readyWhen: `.pane .nb .nbview[data-view="${v}"]:not([hidden])`,
  };
const kinds = tabKinds.flatMap(k => k === 'notebook' ? NB_VIEWS.map(v => `notebook:${v}`) : [k]);
if (runs('a')) ok(undriven.length === 0,
   `every document tab kind has a conformance driver${
     undriven.length ? `; missing: ${undriven.join(', ')} (add it to
     uniform.mjs DRIVERS; the hard rules are the price of a new tab)` : ''}`);

// The band classes the design language names. Content-left must agree across
// every one of them that is visible: this is the rule that was broken three
// different ways before it was a rule. Indented-by-design rows opt out by
// class, and the list of those is deliberately short.
const BANDS = '.field, .row, .rule, .empty, .loading, .fnote, .dmsrc, ' +
              '.macros, .fxproj, .tchead, .tc, .sect>summary';
const INDENTED = [];             // no band is indented on purpose any more

async function measure(kind){
  return page.evaluate(({ BANDS, INDENTED }) => {
    // The tab's own box: the doc pane that is showing. The notebook's root is
    // .nb rather than .doctab and predates the scaffold; same rules apply.
    const host = document.querySelector('.doc.on');
    const box = host?.querySelector(':scope > .doctab, :scope > .nb, :scope > div');
    if (!box) return { err: 'no document box found' };
    const cs = getComputedStyle(box);
    const bands = [...box.querySelectorAll(BANDS)]
      .filter(e => e.offsetHeight > 0 && e.textContent.trim())
      .filter(e => !INDENTED.some(c => e.classList.contains(c)))
      // Nested band-in-band measures the outer one; the inner is content.
      .filter(e => !e.parentElement.closest(BANDS));
    // At a desk content floats as cards (R262): a band in a card (or one
    // that is the card) is where its card stands, the card's edge in line
    // with the page's own content; inside, the card's inset is the card's.
    // A card here is a box edged on both sides; a phone draws none.
    const cardOf = e => {
      if (innerWidth <= 900) return null;
      for (let n = e; n && n !== box; n = n.parentElement){
        const c = getComputedStyle(n);
        if (parseFloat(c.borderLeftWidth) > 0 && parseFloat(c.borderRightWidth) > 0 && c.borderLeftStyle !== 'none'
            && !/^(BUTTON|INPUT|SELECT|TEXTAREA|SPAN|A|CODE)$/.test(n.tagName)) return n;
      }
      return null;
    };
    const leftOf = e => { const card = cardOf(e);
      return Math.round(card ? card.getBoundingClientRect().x
                             : e.getBoundingClientRect().x + parseFloat(getComputedStyle(e).paddingLeft)); };
    // A list beside its detail (a project's Settings view, the Roles page's
    // shape) is two columns: the detail's bands start at one x of their own,
    // beside the list, and are measured apart from the page's.
    // At a desk a settings page's head spans the list and the column both
    // (the operator, 26 Oct), so it stands at the page's x, not the column's.
    const inCol = e => !!e.closest('.ssplit') && !e.closest('.snav') && !(innerWidth > 900 && e.closest('.ssplit > .pghead'));
    const colLefts = [...new Set(bands.filter(inCol).map(leftOf))];
    // A view's lone button beside its tiles shares the glance's line (the
    // operator, 29 Oct): not a band of its own.
    const besideGlance = e => e.matches('.nbhead') && [...e.parentElement.children].some(o => o.matches('.nbglance')
      && o.getBoundingClientRect().top < e.getBoundingClientRect().bottom - 2 && o.getBoundingClientRect().bottom > e.getBoundingClientRect().top + 2);
    const lefts = [...new Set(bands.filter(e => !inCol(e) && !besideGlance(e)).map(leftOf))];
    // Which band sits at each x, for the failure: three numbers say a view is
    // ragged and nothing about where, and the fix is in one band's CSS.
    const who = {};
    for (const e of bands){
      const x = leftOf(e);
      who[x] = who[x] || `${e.tagName.toLowerCase()}.${[...e.classList].join('.')}${
        e.id ? '#' + e.id : ''} in ${e.parentElement?.className || e.parentElement?.tagName}`;
    }
    const ref = document.getElementById('pName');
    const skin = el => { const c = getComputedStyle(el);
      return [c.backgroundColor, c.borderTopLeftRadius, c.borderTopColor,
              c.fontFamily].join('|'); };
    const controls = [...box.querySelectorAll('input, select, textarea')]
      .filter(e => e.offsetHeight > 0)
      .filter(e => !['checkbox', 'radio', 'range', 'file'].includes(e.type));
    const offskin = controls.filter(e => skin(e) !== skin(ref))
      .map(e => e.id || e.className || e.tagName);
    // Meters (design language, Meters): every track in a stack the same
    // width. A stack is the parent that holds more than one track; the
    // widths are rounded, and a stack whose widths are not all one value
    // is reported with them, so the failure names the ragged row.
    const stacks = new Map();
    for (const t of box.querySelectorAll('.track')){
      if (t.offsetHeight === 0) continue;
      const key = t.parentElement?.parentElement;
      if (!key) continue;
      if (!stacks.has(key)) stacks.set(key, []);
      stacks.get(key).push(Math.round(t.getBoundingClientRect().width));
    }
    const ragged = [...stacks.values()].filter(ws => ws.length > 1 && new Set(ws).size > 1);
    // The jump bar's chips sit in a row (the operator, 11 Oct): the notebook's
    // Settings view stacked them one per line, since the dialog's field rule
    // outranked the bar's own.
    const bar = box.querySelector('.sectjump');
    const tops = bar ? [...bar.querySelectorAll('a')].slice(0, 2).map(e => Math.round(e.getBoundingClientRect().top)) : [];
    const jump = bar && bar.offsetHeight ? { dir: getComputedStyle(bar).flexDirection, stacked: tops.length === 2 && tops[0] !== tops[1] } : null;
    // Floating cards at a desk (R262, the operator, 17 Oct): no line runs to
    // the page's edge. A visible top or bottom border spanning the document
    // box from side to side is named; the page's bar band and a notebook's
    // header and view strips are the frame, not content, and keep theirs.
    const edges = [];
    if (innerWidth > 900){
      const br = box.getBoundingClientRect();
      for (const e of box.querySelectorAll('*')){
        if (!e.offsetHeight || e.closest('.docbarrow, .nbtabs, .phead, .modal, .xterm')) continue;
        const c = getComputedStyle(e), r = e.getBoundingClientRect();
        const lined = side => parseFloat(c[`border${side}Width`]) > 0 && c[`border${side}Style`] !== 'none'
          && !/rgba\(\d+, \d+, \d+, 0\)|transparent/.test(c[`border${side}Color`]);
        if ((lined('Top') || lined('Bottom')) && r.left <= br.left + 2 && r.right >= br.right - 2)
          edges.push(`${e.tagName.toLowerCase()}.${[...e.classList].join('.')}${e.id ? '#' + e.id : ''}`);
      }
    }
    return {
      edges: [...new Set(edges)].slice(0, 6),
      jump,
      ragged, stacks: [...stacks.values()].filter(ws => ws.length > 1).length,
      // flush and nbhost are the same treatment in the sheet, and the notebook
      // wears the second for its own reasons; both mean "fills the pane".
      flush: host.classList.contains('flush') || host.classList.contains('nbhost'),
      // A notebook runs the pane's width for its view strip (the operator,
      // 17 Oct): the reading width is its view's, the band under the strip.
      maxw: box.matches('.nb') ? getComputedStyle(box.querySelector('.nbview:not([hidden])') || box).maxWidth : cs.maxWidth,
      bands: bands.length, lefts, colLefts, who,
      controls: controls.length, offskin,
    };
  }, { BANDS, INDENTED });
}

// The page holds twelve tabs, and there are more document kinds than that
// with the terminal beside them. So a kind is brought up by focusing its tab
// when one is open, and otherwise opened, after closing the oldest other
// document when the strip is full.
async function bring(kind){
  // `notebook:<view>` is the notebook's tab with that view showing.
  const view = kind.startsWith('notebook:') ? kind.slice('notebook:'.length) : '';
  const had = await page.evaluate(k => {
    // Among the notebooks, alpha's: another project's would be focused and
    // then asked for a view it never draws.
    const t = tabs.find(x => x.kind === k && (k !== 'notebook' || x.arg === 'alpha'));
    if (t){ focusTab(t.id); return true; }
    if (tabs.length >= 11){
      const old = tabs.find(x => x.kind !== 'term' && x.kind !== k);
      if (old) dropTab(old.id);
    }
    return false;
  }, view ? 'notebook' : kind);
  if (had){
    if (view){
      await page.evaluate(w => getNotebook('alpha').view(w), view);
      await page.waitForSelector(DRIVERS[kind].readyWhen, { timeout: 20000 });
      await settled(page);                // the view's own fetch lands
    }
    return;
  }
  // A fresh open settles before it is measured: a proseline sizes itself to
  // its text once the view's data has landed, a beat after the band shows.
  // Waited for (lib.mjs settled: the requests landed and a quiet beat),
  // not slept: a fixed half second here was paid on every kind in every
  // section of this file (R211).
  await DRIVERS[kind].open();
  await page.waitForSelector(DRIVERS[kind].readyWhen, { timeout: 20000 });
  await settled(page, { quiet: 250 });
}
// The page on show has arrived: its entrance fade (docIn) is over, and what
// it asked for has landed and been drawn, the last band with it.
async function arrived(p = page){
  await p.waitForFunction(() => !document.querySelector('.pane .doc.on')?.getAnimations().length,
                          null, { timeout: 10000 }).catch(() => {});
  await settled(p);
}
// Two frames on from a change to the page: what the change starts in the
// frame after it (a breakpoint's listeners, a transition) has started.
const frames = (p = page) => p.evaluate(() => new Promise(r => requestAnimationFrame(() => requestAnimationFrame(r))));
// Nothing on the page is still moving: every transition and tween that ends
// has ended. One that runs for good (a spinner, a pulse) is not waited for.
async function motionOver(p = page){
  await frames(p);
  await p.waitForFunction(() => !document.getAnimations().some(a => a.playState === 'running'
    && Number.isFinite(a.effect?.getComputedTiming().endTime)), null, { timeout: 10000 }).catch(() => {});
}
// A page at the width it was just given, and drawn for it: the breakpoint's
// listeners run in the frame after the change, then the boxes that fit
// themselves to their width, and what either of them slides comes to rest.
async function atWidth(p, w){
  await p.waitForFunction(w => innerWidth === w, w, { timeout: 10000 }).catch(() => {});
  await motionOver(p);
}


// ---- the section and action-bar language -----------------------------------
// The other half of the document language, and the half that drifts: it is
// carried by shared classes rather than by a scaffold function, so a tab can
// quietly answer differently and nothing notices. These rules are the things
// that must be the SAME on every tab, which is why they are here and not in
// each kind's own suite. A rule that is genuinely one tab's belongs there.
//
// Measured, never taken on faith: the colors and the layout are computed, so
// a tab that restyles .actbar or .danger locally fails even though its markup
// says the right words.
//
// What this cannot see is a surface that is not on screen when it looks: a
// Docker row needs an instance, a project picker needs to be expanded. Those
// are each tab's own fixture and each tab's own suite. What is here is the
// shape, checked on whatever the tab does render.

// A tab strip is navigation, not actions; the document's own footer has its
// own shape (one verb left, its undo right). Everything else that holds two
// or more TEXT buttons is an action bar; icon clusters are exempt by having
// no text, which is what makes a roadmap row's five pictograms legal and a
// row of Up / Down / Remove not.
// `pagemore` joins them: it is the framework's own footer for a long list
// (a count and up to two buttons, drawn by paginate() and nothing else), so
// it is already one bar with one shape everywhere, which is what the rule
// below is for. It reached this check for the first time when the Jobs tab
// was paged, because every other paginated list is in a notebook whose
// fixture is too short to draw one.
// ...and a segmented switch (.pseg: Deploy key / Access token, Dark / Light,
// Cards / List) is one choice, not a set of verbs (R216).
// ...nor a list of rows you open (the Roles tab's accounts and roles, R255
// step 9: the rows-you-open rule), whose rows are rows that happen to be
// pressed, not verbs.
// ...and a row of chips (the chips rule, R216): a view's groups, one in
// force, never a set of verbs. No fixture drew two groups before the
// Library's kinds (R170), which is when the row first met this check.
// ...nor the Files page's places (the operator, 12 Nov: a file explorer's
// column of the node's roots): rows you open, as a list of rows is.
const NOT_A_BAR = ['nbtabs', 'nbgroups', 'nbsub', 'foot', 'pagemore', 'pseg', 'rlist', 'chips', 'fxplaces'];

async function language(){
  return page.evaluate(({ NOT_A_BAR }) => {
    const host = document.querySelector('.doc.on');
    const box = host?.querySelector(':scope > .doctab, :scope > .nb, :scope > div');
    if (!box) return { err: 'no document box found' };
    const vis = e => e.offsetHeight > 0 || e.offsetWidth > 0;
    const isBtn = c => (c.tagName === 'BUTTON'
                        || (c.tagName === 'A' && c.classList.contains('btn'))) && vis(c);
    const named = e => String(e.className || e.tagName).split(/\s+/)[0] || e.tagName;
    const gone = b => b.classList.contains('danger');
    const loose = [], order = [], layout = [], reds = new Set();
    for (const e of box.querySelectorAll('*')){
      const btns = [...e.children].filter(isBtn);
      if (btns.length < 2) continue;
      if (!btns.some(b => b.textContent.trim())) continue;      // an icon cluster
      if (!e.classList.contains('actbar')){
        if (!NOT_A_BAR.some(c => e.classList.contains(c)))
          loose.push(`${named(e)}(${btns.map(b => b.textContent.trim().slice(0, 12)).join('/')})`);
        continue;
      }
      // Destructive last: not "the last button is destructive", but that
      // nothing safe sits after something that cannot be undone, which is
      // the rule a thumb obeys and a two-Remove bar still satisfies.
      const first = btns.findIndex(gone);
      if (first >= 0 && btns.slice(first).some(b => !gone(b)))
        order.push(`${named(e)}(${btns.map(b => (gone(b) ? '!' : '') + b.textContent.trim().slice(0, 10)).join('/')})`);
      const c = getComputedStyle(e);
      layout.push([c.display, c.flexWrap, c.justifyContent].join('|'));
    }
    // ...and a destructive button LOOKS destructive, the same way everywhere.
    for (const b of box.querySelectorAll('button.danger, a.btn.danger')){
      if (!vis(b) || !b.textContent.trim()) continue;
      reds.add(getComputedStyle(b).color);
    }
    const sects = [...box.querySelectorAll('details.sect > summary')].map(s => {
      const c = getComputedStyle(s);
      return { status: s.querySelector('.sst')?.textContent?.trim() || '',
               // The cursor says whether it folds: a pointer where a press
               // folds it, the plain arrow on a page's section at a desk,
               // which stands open (sectFixed, the operator, 18 Oct).
               skin: [c.minHeight, c.fontWeight, c.cursor === (sectFixed(s.parentElement) ? 'default' : 'pointer') ? 'cursor ok' : `cursor ${c.cursor}`].join('|') };
    });
    // The voices (R210): a button speaks in the page's sans (the key caps
    // on the terminal tab are mono on purpose), never the browser's own
    // default, which a dropped shorthand left every button in (B711); and a
    // notice under a row (.sub.warn, .sub.bad, .notice) is sans behind a
    // bar of its color, so it is told from the mono facts above it.
    // The first family named is what is compared: the page's stacks spell
    // their fallbacks differently (system-ui, -apple-system, ... against
    // system-ui, sans-serif) and all begin with the same face.
    const first = f => f.split(',')[0].trim().replace(/["']/g, '');
    const bodyFont = first(getComputedStyle(document.body).fontFamily);
    const alien = [...box.querySelectorAll('button')].filter(b => {
      const f = getComputedStyle(b).fontFamily;
      return vis(b) && b.textContent.trim() && first(f) !== bodyFont && !/mono/i.test(f);
    }).map(b => `${named(b)} "${b.textContent.trim().slice(0, 12)}" (${first(getComputedStyle(b).fontFamily)})`);
    const flat = [...box.querySelectorAll('.row .sub.warn, .row .sub.bad, .row .sub.note, .notice')].filter(n => {
      const c = getComputedStyle(n);
      return vis(n) && (/mono/i.test(c.fontFamily) || parseFloat(c.borderLeftWidth) < 2);
    }).map(n => `${named(n)} "${n.textContent.trim().slice(0, 20)}"`);
    // Room between words and the buttons under them (R218 step 55, the
    // operator, 18 Oct: text all but touching its buttons): a line of prose,
    // a hint or a facts list followed by an action bar keeps 8px or more.
    const tight = [...box.querySelectorAll('.sub, .hint, .note, p, dl.facts, .notice')].filter(t => {
      const n = t.nextElementSibling;
      if (!n || !vis(t) || !vis(n) || !t.textContent.trim() || !n.matches('.actbar, .acts') || !n.querySelector('button')) return false;
      // Beside them, not under them: a head's one action in its corner.
      if (n.getBoundingClientRect().left >= t.getBoundingClientRect().right - 2) return false;
      return n.getBoundingClientRect().top - t.getBoundingClientRect().bottom < 8;
    }).map(t => `${named(t)} "${t.textContent.trim().slice(0, 20)}"`);
    return { loose, order, layout: [...new Set(layout)], reds: [...reds], sects, alien, flat, tight };
  }, { NOT_A_BAR });
}

// Gathered across every kind and compared at the end: "the same on every tab"
// is not a claim any one tab can fail on its own.
const seenBars = new Set(), seenSects = new Set(), seenReds = new Set();

// ---- a control never spans its container ----------------------------------
// A button, a select, a text field, or a row of them side by side stops
// short of the tab's width at every width (docs/design-language.md,
// Controls). Measured as the union of a row's controls against the box
// holding them, so an action bar whose buttons sit at the right is judged
// on the buttons and not on the bar's own full-width flex box. Terminals
// and logs are not controls; a readonly textarea showing text is a log.
async function spanning(){
  return page.evaluate(() => {
    const host = document.querySelector('.doc.on');
    const box = host?.querySelector(':scope > .doctab, :scope > .nb, :scope > div');
    if (!box) return { err: 'no document box found' };
    const W = box.getBoundingClientRect().width;
    // The rule's own number as well as the surface: a 700px field on a
    // 1080px tab is inside 90% and outside --ctl-w.
    const cap = parseFloat(getComputedStyle(document.documentElement).getPropertyValue('--ctl-w')) * 16 || 480;
    const LIM = Math.min(W * 0.9, cap + 2);
    const CTL = 'input:not([type=checkbox]):not([type=radio]), select, textarea, button';
    const ROWS = '.actbar, .ctlrow, .setcell .ctl, .setfoot, .tcnode, .chips';
    // A tab strip is navigation, and the phone rule for one is the opposite
    // of a control's: its tabs share the row while they fit, and past that
    // it scrolls under a finger with its edges faded as the dock's line does
    // (the operator, 29 Oct).
    const NAV = '.nbtabs, .switch, .subnav, .rlist';
    const vis = e => e.offsetHeight > 0 && e.getBoundingClientRect().width > 0;
    const out = [];
    const seen = new Set();
    for (const row of box.querySelectorAll(ROWS)){
      // The document bar is a band, not a control row (filters at the left,
      // the action at the tab's right edge), so its union spans by design.
      // Its controls are measured one by one below, like any lone control.
      if (row.classList.contains('docbarrow')) continue;
      // A row of chips scrolls sideways where the width runs out (the chips
      // rule: never a row per group), so its union runs past the cap by
      // design; each chip is still a fraction of the width.
      if (row.classList.contains('chips')) continue;
      // A full action bar on a phone (four buttons or more) shares the row
      // between its buttons on purpose (the phone rule both-sizes: at 344px
      // four did not fit), so its union spans by design; each button is
      // still a fraction of the width.
      if (W <= 600 && row.classList.contains('actbar')
          && [...row.children].filter(c => (c.tagName === 'BUTTON' || c.classList.contains('more')) && vis(c)).length >= 4) continue;
      const kids = [...row.querySelectorAll(CTL)].filter(vis);
      kids.forEach(k => seen.add(k));
      if (!kids.length) continue;
      const l = Math.min(...kids.map(k => k.getBoundingClientRect().left));
      const r = Math.max(...kids.map(k => k.getBoundingClientRect().right));
      if (r - l > LIM) out.push(`${row.className.split(' ')[0]} ${Math.round(r - l)}/${Math.round(W)}`);
    }
    for (const e of box.querySelectorAll(CTL)){
      // `.slot` is a terminal pane, not `.term`: that is the terminal
      // COLUMN, which every document tab is inside, so the exclusion took
      // every lone control on every tab with it and this half of the rule
      // measured nothing at all.
      if (seen.has(e) || !vis(e) || e.closest('.slot, .dmlog, pre, .dropbox, .sendbox, ' + NAV)) continue;
      // A prose editor in the notebook is a page, not a control.
      if (e.tagName === 'TEXTAREA' && (e.readOnly || e.closest('.nb'))) continue;
      const w = e.getBoundingClientRect().width;
      if (w > LIM) out.push(`${e.id || e.className.split(' ')[0] || e.tagName} ${Math.round(w)}/${Math.round(W)}`);
    }
    return { wide: out, w: W };
  });
}

// ---- controls in a row line up ---------------------------------------------
// A row of controls sits on one line, and every control box on that line ends
// at the same height. What breaks it is a row that centers its items while
// some of them carry a label above (the design language, Controls): the
// unlabeled select then floats between its neighbor's label and its field,
// which is what the Nodes tab's mount rows did.
//
// Measured on the boxes, not on the wrappers: controls are grouped into lines
// by vertical overlap, so a row that wrapped is several lines and each is
// judged on its own. A checkbox is text with a box beside it rather than a
// control box, and is left out.
async function lineup(){
  return page.evaluate(() => {
    const host = document.querySelector('.doc.on');
    const box = host?.querySelector(':scope > .doctab, :scope > .nb, :scope > div');
    if (!box) return { err: 'no document box found' };
    const CTL = 'input:not([type=checkbox]):not([type=radio]), select, button, textarea.proseline';
    const name = e => `${e.tagName.toLowerCase()}${e.id ? '#' + e.id : ''}${
      e.className && typeof e.className === 'string' && e.className.trim()
        ? '.' + e.className.trim().split(/\s+/)[0] : ''}`;
    // ...and only what is on screen at its own place: a control scrolled
    // under the notebook's foot inside the view's scroller still has a
    // box, and it grouped with the foot's buttons as one line (29 Sep,
    // when the Design view's board grew and pushed its rows down).
    // ...and nothing inside a shut fold: its content keeps a box in Chrome,
    // and the point under it is its own parent's, so a Save at the foot of
    // a shut section read as on screen beside a shut row of another
    // (one section open at a time, 6 Oct).
    const folded = e => {
      for (let d = e.parentElement?.closest('details'); d; d = d.parentElement?.closest('details'))
        if (!d.open && !d.querySelector(':scope > summary')?.contains(e)) return true;
      return false;
    };
    const shown = e => {
      const r = e.getBoundingClientRect();
      const at = document.elementFromPoint(r.left + r.width / 2, r.top + r.height / 2);
      return !!at && (at === e || e.contains(at) || at.contains(e));
    };
    const ctls = [...box.querySelectorAll(CTL)]
      .filter(e => e.offsetHeight > 0 && e.getBoundingClientRect().width > 0
                   && !e.closest('.slot, .dmlog, .pagemore, .rlist, .fxplaces') && !folded(e) && shown(e))
      .map(e => ({ e, r: e.getBoundingClientRect() }))
      .sort((a, b) => a.r.top - b.r.top);
    // One line = boxes whose vertical spans overlap by more than half the
    // shorter of the two. Two controls in different bands never do; two in
    // one row always do, however differently they are aligned.
    const lines = [];
    for (const c of ctls){
      const line = lines.find(l => l.some(o => {
        const over = Math.min(o.r.bottom, c.r.bottom) - Math.max(o.r.top, c.r.top);
        return over > Math.min(o.r.height, c.r.height) / 2;
      }));
      if (line) line.push(c); else lines.push([c]);
    }
    const off = [], sizes = [];
    for (const line of lines){
      if (line.length < 2) continue;
      const lo = Math.min(...line.map(c => c.r.bottom));
      const hi = Math.max(...line.map(c => c.r.bottom));
      if (hi - lo > 1.5)
        // Where each one is, so a line that should not be one says why it is.
        off.push(`${line.map(c => `${name(c.e)}@${Math.round(c.r.bottom)}${
          c.e.closest('[data-sect]') ? `[${c.e.closest('[data-sect]').dataset.sect}]` : ''}`).join(' ')}`);
      // ...and one height (the operator, 29 Sep: a field, a pulldown and a
      // button on one row were three sizes). A prose box that has wrapped
      // to a second line is taller by design and left out; a swatch is a
      // circle of its own.
      const one = line.filter(c => !c.e.closest('.pcpick')
        && !(c.e.matches('textarea.proseline') && c.e.scrollHeight > c.r.height + 2 && c.e.value.length));
      const hs = one.map(c => c.r.height);
      if (one.length > 1 && Math.max(...hs) - Math.min(...hs) > 1.5)
        sizes.push(`${one.map(c => `${name(c.e)}:${Math.round(c.r.height)}`).join(' ')}`);
    }
    return { off, sizes };
  });
}

// A select is ONE line high, at any width.
//
// The page draws its own <select> pickers (appearance:base-select in the
// stylesheet, so the list takes the scheme's colors instead of Android's).
// The one thing a base select does worse than a native one is a label that
// does not fit: a native select truncates it, a base one WRAPS, and a picker
// two lines tall drags its whole row out of shape. It cost the Phone tab's
// node picker at phone width once, where the bar's max-width:88% is what
// squeezes it, so this is measured where it bites rather than only at desktop.
//
// One line is computed from the control's own metrics (its line-height,
// padding and border) rather than from a constant, because the tabs run 12px, 13px
// mono and 16px on a phone.
async function unwrapped(){
  return page.evaluate(() => {
    const host = document.querySelector('.doc.on');
    const box = host?.querySelector(':scope > .doctab, :scope > .nb, :scope > div');
    if (!box) return { err: 'no document box found' };
    const tall = [...box.querySelectorAll('select')]
      .filter(e => e.offsetHeight > 0)
      .filter(e => {
        const c = getComputedStyle(e);
        const lh = c.lineHeight === 'normal'
          ? parseFloat(c.fontSize) * 1.4 : parseFloat(c.lineHeight);
        const one = lh + parseFloat(c.paddingTop) + parseFloat(c.paddingBottom)
                  + parseFloat(c.borderTopWidth) + parseFloat(c.borderBottomWidth);
        return e.getBoundingClientRect().height > one + 6;
      })
      .map(e => `${e.id || e.getAttribute('aria-label') || 'select'}@${
        Math.round(e.getBoundingClientRect().height)}px`);
    return { tall };
  });
}
// ---- tiles and facts (R216) --------------------------------------------------
// A row of tiles is one height with its numbers in the stat voice, and a
// facts grid is labels in the note voice over values in mono: the two
// shapes every tab draws the same way or not at all.
// A section's first thing keeps room under its head, at every width (the
// operator, 19 Oct: on a phone the first field met the head on every page,
// the room having been the desk card's alone). Measured from the head's
// foot to the first box drawn in the body, a page's own section at a page's
// level, not one inside a row or a dialog.
// Every row of controls wears the one class the cap and the line-up rules
// read (R218 step 64): a row kind that forgot it would be capped by nothing,
// or each of its controls capped a second time, which is how three lists of
// row kinds in the stylesheet drifted apart. Field rows, add rows, filter
// rows and picker rows are the kinds the page draws.
function rowsWearTheClass(){
  return page.evaluate(() => [...document.querySelectorAll('.doc.on :is(.setrow, .addbar, .prefrow, .histbar, .logdays, .imgadd, .memadd, .uadd, .ndpaths, .ndname)')]
    .filter(e => !e.classList.contains('ctlrow')).map(e => e.className.split(' ').slice(0, 3).join('.')));
}
// A pulldown in a bar or a row is as wide as its longest answer and no wider
// (the operator, 18 Nov: Sort and the wiki's page stretched across a phone):
// each one on show measured against itself with its longest answer chosen
// and nothing sizing it, which is how wide its longest answer makes it. Wider
// is stretched; narrower is allowed only where its row has no room left,
// which clips it. The pulldowns are the page's own PICKERS (page-docs.js),
// so the check and what sizes them cannot drift apart. The one exception is
// a phone's line of pulldowns beside a row's compact buttons (.pickshare,
// the operator, 22 Nov): there each fills its share flush to the buttons,
// held instead to filling it exactly.
function pickersFit(){
  return page.evaluate(() => {
    const ink = document.createElement('canvas').getContext('2d');
    return [...document.querySelectorAll(PICKERS)].filter(s => s.checkVisibility() && s.options.length && s.closest('.doc.on, .pane .bar')).map(s => {
      const name = s.id || s.getAttribute('aria-label') || '?';
      const w = s.getBoundingClientRect().width;
      const style = s.getAttribute('style'), at = s.selectedIndex;
      ink.font = getComputedStyle(s).font;
      const words = [...s.options].map(o => o.label || o.textContent || '');
      const longest = words.reduce((j, t, i) => ink.measureText(t).width > ink.measureText(words[j]).width ? i : j, 0);
      s.selectedIndex = longest;
      s.style.cssText = (style || '') + ';flex:none;width:auto;max-width:none;min-width:0;justify-self:start';
      const own = s.getBoundingClientRect().width;
      s.selectedIndex = at;
      if (style === null) s.removeAttribute('style'); else s.setAttribute('style', style);
      if (s.closest('.pickshare') && innerWidth <= 600){
        const share = s.parentElement.matches('label.pick') ? s.parentElement : null;
        if (share) return Math.abs(share.getBoundingClientRect().width - w) > 1 ? `${name} is ${Math.round(w)}px in a share of ${Math.round(share.getBoundingClientRect().width)}px it should fill` : '';
        // A bare one reaches the next thing on its line, or the row's end.
        const row = s.parentElement, rs = getComputedStyle(row), me = s.getBoundingClientRect();
        const next = [...row.children].filter(k => k !== s && k.checkVisibility()).map(k => k.getBoundingClientRect())
          .filter(r => Math.abs(r.top - me.top) < 6 && r.left >= me.right - 1).sort((a, b) => a.left - b.left)[0];
        const end = next ? next.left - (parseFloat(rs.columnGap) || 0) : row.getBoundingClientRect().right - parseFloat(rs.paddingRight);
        return Math.abs(end - me.right) > 1 ? `${name} stops ${Math.round(end - me.right)}px short of its line's end` : '';
      }
      if (w > own + 3) return `${name} is ${Math.round(w)}px for ${Math.round(own)}px of its longest answer`;
      if (w >= own - 3) return '';
      // Short of it: only where the row it sits in had no more to give.
      const row = s.parentElement, rs = getComputedStyle(row), kids = [...row.children].filter(k => k.checkVisibility());
      const used = kids.reduce((n, k) => n + k.getBoundingClientRect().width, 0) + (parseFloat(rs.columnGap) || 0) * Math.max(0, kids.length - 1);
      const free = row.getBoundingClientRect().width - parseFloat(rs.paddingLeft) - parseFloat(rs.paddingRight) - used;
      return free > 3
        ? `${name} is ${Math.round(w)}px, short of the ${Math.round(own)}px its longest answer needs, with ${Math.round(free)}px free beside it` : '';
    }).filter(Boolean);
  });
}
// The forms rule (the operator, 4 Nov: fields crammed together, each page its
// own way): a label over its field, never beside it, and fields that do not
// touch. A picker in a band or an action bar sits beside what it filters and
// is not a form's field.
// ...on a page, or in the dialog on show (R273: a dialog's form is on the
// same grid, the operator 23 Nov).
function formsHold(root = '.doc.on'){
  return page.evaluate(root => {
    const out = new Set();
    const say = (e, why) => out.add(`${e.id || e.dataset?.k || e.name || e.getAttribute('aria-label') || e.tagName.toLowerCase()}: ${why}`);
    const bar = '.actbar,.docbarrow,.histbar,.phead,.pghead,.sectjump,.tbl,table,.ndmline,.bar,.fnote,.wkpick,.dsrow,.addbar,.modal[hidden],[hidden],.skel,.term,.xterm';
    const fields = [...document.querySelectorAll(`${root} :is(input:not([type=checkbox]):not([type=radio]):not([type=file]):not([type=hidden]),select,textarea)`)]
      .filter(e => { const r = e.getBoundingClientRect(); return r.width > 0 && r.height > 0 && !e.closest(bar); });
    for (const e of fields){
      const box = e.getBoundingClientRect();
      const holder = e.closest('label');
      const named = holder?.querySelector('.pickw') || (e.id && document.querySelector(`label[for="${CSS.escape(e.id)}"]`)) || e.parentElement?.querySelector(':scope > .lbl');
      if (!named) continue;
      const l = named.getBoundingClientRect();
      if (l.width && l.height && l.bottom > box.top + 2 && l.left < box.left) say(e, 'its label is beside it');
    }
    // Two fields in one column, touching.
    for (const e of fields){
      const a = e.getBoundingClientRect();
      for (const f of fields){
        if (f === e) continue;
        const b = f.getBoundingClientRect();
        if (b.top < a.bottom || b.left >= a.right || b.right <= a.left) continue;
        const gap = b.top - a.bottom;
        if (gap < 4 && !e.closest('.ctlline') && !f.closest('.ctlline')) say(f, `${Math.round(gap)}px under the field above it`);
      }
    }
    return [...out];
  }, root);
}
function headRoom(){
  return page.evaluate(() => {
    const out = [];
    for (const d of document.querySelectorAll('.doc.on details.sect[open]')){
      if (d.parentElement.closest('details.sect, .row, .modal')) continue;
      const s = d.querySelector(':scope > summary'), body = d.querySelector(':scope > .body');
      if (!s || !body || !s.offsetHeight) continue;
      const first = [...body.querySelectorAll('*')].find(e => e.offsetHeight > 0 && e.getBoundingClientRect().width > 0
        && (e.children.length === 0 || /^(INPUT|BUTTON|SELECT|TEXTAREA)$/.test(e.tagName)));
      if (!first) continue;
      const gap = first.getBoundingClientRect().top - s.getBoundingClientRect().bottom;
      if (gap < 6) out.push(`${d.dataset.sect || '?'} ${Math.round(gap)}px`);
    }
    return out;
  });
}
// Nothing in a section sits on its side wall (B864: the Nodes page's
// Network lines and Home's placeholder bars ran to the edge, each kept
// there by a rule of its own page): every line of text and every control
// in an open section's body starts at least 6px in from the section's box,
// and every placeholder bar 6px in from the card or section it waits in.
function sideRoom(){
  return page.evaluate(() => {
    const out = [], seen = new Set();
    const vis = r => r.width > 0 && r.height > 0;
    const say = (where, what, gap) => { const k = `${where} ${what}`; if (!seen.has(k)){ seen.add(k); out.push(`${k} ${Math.round(gap)}px`); } };
    for (const d of document.querySelectorAll('.doc.on details.sect[open]')){
      if (d.parentElement.closest('details.sect, .row, .modal, .skel')) continue;
      const body = d.querySelector(':scope > .body');
      if (!body || !body.offsetHeight) continue;
      const B = d.getBoundingClientRect();
      const walk = document.createTreeWalker(body, NodeFilter.SHOW_TEXT);
      for (let t; (t = walk.nextNode());){
        if (!t.textContent.trim() || t.parentElement.closest('button, select, option, textarea, pre, .tbl, table, [hidden]')) continue;
        const rg = document.createRange(); rg.selectNodeContents(t);
        const r = rg.getBoundingClientRect();
        if (vis(r) && r.left - B.left < 6) say(d.dataset.sect || '?', JSON.stringify(t.textContent.trim().slice(0, 24)), r.left - B.left);
      }
      for (const c of body.querySelectorAll('button, input:not([type=checkbox]):not([type=radio]), select, textarea')){
        if (c.closest('.tbl, table, [hidden]')) continue;
        const r = c.getBoundingClientRect();
        if (vis(r) && r.left - B.left < 6) say(d.dataset.sect || '?', c.tagName.toLowerCase() + (c.textContent.trim() ? ' ' + JSON.stringify(c.textContent.trim().slice(0, 16)) : ''), r.left - B.left);
      }
    }
    for (const bar of document.querySelectorAll('.doc.on .skel .sk-b')){
      const r = bar.getBoundingClientRect();
      if (!vis(r)) continue;
      let box = bar.parentElement;
      for (; box && !box.matches('.doc'); box = box.parentElement){
        const c = getComputedStyle(box);
        if (parseFloat(c.borderLeftWidth) > 0 && c.borderLeftStyle !== 'none') break;
      }
      if (!box || box.matches('.doc')) continue;
      const gap = r.left - box.getBoundingClientRect().left;
      if (gap < 6) say('placeholder', box.className.split(' ').slice(0, 2).join('.'), gap);
    }
    return out;
  });
}
async function glance(){
  return page.evaluate(() => {
    const box = document.querySelector('.pane .doc.on .doctab, .pane .doc.on .nb');
    if (!box) return { err: 'no document' };
    const px = s => parseFloat(s) || 0;
    const stat = getComputedStyle(document.documentElement).getPropertyValue('--f-stat');
    const bad = [];
    for (const row of box.querySelectorAll('.tiles')){
      const ts = [...row.querySelectorAll('.tile')].filter(t => t.offsetHeight);
      const hs = ts.map(t => Math.round(t.getBoundingClientRect().height));
      if (ts.length && Math.max(...hs) - Math.min(...hs) > 1) bad.push(`tiles of ${hs.join('/')}px`);
      for (const t of ts){
        const v = t.querySelector('.tv');
        if (!v || px(getComputedStyle(v).fontSize) < 20) bad.push(`a tile's number at ${v ? getComputedStyle(v).fontSize : 'none'}`);
        if (!t.querySelector('.tl')?.textContent.trim()) bad.push('a tile with no label');
      }
      if (ts.length > 6) bad.push(`${ts.length} tiles in one row`);
    }
    for (const dl of box.querySelectorAll('dl.facts')){
      const dt = dl.querySelector('dt'), dd = dl.querySelector('dd');
      if (!dt || !dd) continue;
      if (!/monospace|Mono|Menlo|Consolas/i.test(getComputedStyle(dd).fontFamily)) bad.push('a fact value not in mono');
      if (px(getComputedStyle(dt).fontSize) > px(getComputedStyle(dd).fontSize)) bad.push('a fact label larger than its value');
      // A column's values start at one line, whatever their labels' length
      // (B76): one x per column of the grid, counted from the facts' own boxes.
      if (CSS.supports('grid-template-columns', 'subgrid')){
        const cols = new Map();
        for (const f of dl.querySelectorAll(':scope > .fact')){
          const v = f.querySelector('dd');
          if (!v || !f.offsetHeight) continue;
          const col = Math.round(f.getBoundingClientRect().left);
          (cols.get(col) || cols.set(col, new Set()).get(col)).add(Math.round(v.getBoundingClientRect().left));
        }
        for (const xs of cols.values()) if (xs.size > 1) bad.push(`a facts grid whose values start at ${[...xs].join('/')}`);
      }
    }
    // A table (R218 step 8): each row's cells start where the header's do,
    // and the header is in the note voice under the cells' size.
    const tbad = [];
    for (const t of box.querySelectorAll('.tbl')){
      const head = t.querySelector(':scope > .thead');
      if (!head || !head.offsetHeight) continue;
      const hx = [...head.children].map(c => Math.round(c.getBoundingClientRect().left));
      for (const line of [...t.querySelectorAll(':scope > :not(.thead) > .tline, :scope > .tline')].filter(l => l.offsetHeight).slice(0, 8)){
        const lx = [...line.children].map(c => Math.round(c.getBoundingClientRect().left));
        if (lx.length !== hx.length || lx.some((x, i) => Math.abs(x - hx[i]) > 1)) tbad.push(`a line at ${lx.join('/')} under a header at ${hx.join('/')}`);
      }
      const th = head.querySelector('.th');
      if (th && px(getComputedStyle(th).fontSize) > px(getComputedStyle(t.querySelector('.td') || th).fontSize) + 0.5) tbad.push('a header larger than its cells');
    }
    return { bad, tbad, tables: box.querySelectorAll('.tbl').length, tiles: box.querySelectorAll('.tiles .tile').length,
             facts: box.querySelectorAll('dl.facts').length, stat: stat.trim() };
  });
}

if (runs('a')) {
// ---- one walk over every kind, at a desk ---------------------------------
// The four readings that change nothing on the page (the box and its bands,
// the button language, what spans, what lines up) are taken on ONE visit to
// each kind. They were four walks over 26 kinds, each paying the bring and
// the settle again (R211: 0.5 to 0.8 s a visit, four times over).
// The row a page's tabs sit in, by page: one height on every page, under a
// group's header or standing alone, with an action in it or not.
// A page a press opens wears its Back header there instead of tabs, and is
// not measured as a tab row.
const tabRow = () => page.evaluate(() => {
  const bar = document.querySelector('#pane0 .bar.page');
  if (!bar || bar.querySelector('.backhead')) return null;
  const row = bar.querySelector(':scope > .subrow') || bar;
  return Math.round(row.getBoundingClientRect().height);
});
const tabRows = {};
for (const kind of kinds){
  if (!DRIVERS[kind]) continue;
  await bring(kind);
  await page.waitForSelector(DRIVERS[kind].readyWhen, { timeout: 20000 });
  await arrived();   // the entrance animation settles, and the last band to arrive is part of the row
  const row = await tabRow();
  if (row !== null) tabRows[kind] = row;
  const m = await measure(kind);
  ok(!m.err, `[${kind}] a document box exists (${m.err || 'ok'})`);
  ok((m.ragged || []).length === 0,
     `[${kind}] every stack of meters has tracks of one width (${m.stacks || 0} stack${m.stacks === 1 ? '' : 's'}${
       m.ragged?.length ? `; ragged: ${m.ragged.map(w => w.join('/')).join('; ')}` : ''})`);
  if (!m.err){
  if (m.jump) ok(m.jump.dir === 'row' && !m.jump.stacked, `[${kind}] its jump bar's chips sit in a row (${m.jump.dir}${m.jump.stacked ? ', stacked' : ''})`);
  ok(m.flush, `[${kind}] fills its pane flush, like every document`);
  ok(m.maxw === '1080px',
     `[${kind}] caps at the document width (got ${m.maxw})`);
  ok(m.bands > 0 && (m.lefts.length === 1 || !m.lefts.length && m.colLefts.length === 1),
     `[${kind}] every band starts at one x (${m.bands} bands at ${
       JSON.stringify(m.lefts)}${m.lefts.length > 1 ? ': ' + m.lefts.map(x => `${x} is ${m.who[x]}`).join('; ') : ''})`);
  if (m.edges) ok(m.edges.length === 0,
     `[${kind}] no line at a desk runs to the page's edge: its content floats as cards${m.edges.length ? `; reaching it: ${m.edges.join(', ')}` : ''}`);
  if (m.colLefts.length) ok(m.colLefts.length === 1,
     `[${kind}] ...and every band in the column beside its list at one x of its own (${JSON.stringify(m.colLefts)}${
       m.colLefts.length > 1 ? ': ' + m.colLefts.map(x => `${x} is ${m.who[x]}`).join('; ') : ''})`);
  // A fold that shows more of a row opens by the page's own triangle
  // (.chev), never the browser's marker, which a summary drawn as a list
  // item shows.
  const marks = await page.evaluate(() => [...document.querySelectorAll('#pane0 details:not(.sect) > summary')]
    .filter(x => x.checkVisibility() && getComputedStyle(x).display === 'list-item')
    .map(x => x.parentElement.className || x.textContent.trim().slice(0, 30)));
  ok(!marks.length, `[${kind}] every fold opens by the page's chevron, never the browser's marker${marks.length ? `; not: ${marks.join(', ')}` : ''}`);
  // A search box in a page's bar keeps a search's room at a desk: the
  // pickers beside it take their own width, never the whole bar.
  const narrow = await page.evaluate(() => [...document.querySelectorAll('#pane0 input[type=search]')]
    .filter(x => x.checkVisibility() && x.getBoundingClientRect().width < 12 * parseFloat(getComputedStyle(document.documentElement).fontSize))
    .map(x => `${x.className || x.getAttribute('aria-label')} ${Math.round(x.getBoundingClientRect().width)}px`));
  ok(!narrow.length, `[${kind}] a search box keeps a search's room${narrow.length ? `; not: ${narrow.join(', ')}` : ''}`);
  ok(m.offskin.length === 0,
     `[${kind}] every control wears the field skin${
       m.offskin.length ? `; not: ${m.offskin.join(', ')}` : ''} (${
       m.controls} checked)`);
  }
  // Nothing between a page's sections, and its pills (its chips and its
  // jump bar) before the first of them (the operator, 25 Oct: a line between
  // Toolchains and Tool packs, and Storage's jump bar mid-page).
  const shape = await page.evaluate(() => {
    const host = document.querySelector('.doc.on');
    if (!host) return { between: [], late: [] };
    const vis = e => e.offsetHeight > 0 || e.offsetWidth > 0;
    const named = e => String(e.className || e.tagName).split(/\s+/)[0] || e.tagName;
    const between = [], late = [], seen = new Set();
    host.querySelectorAll('details.sect').forEach(d => {
      const p = d.parentElement;
      if (!p || seen.has(p)) return;
      seen.add(p);
      const kids = [...p.children].filter(e => e.matches('details.sect') || vis(e));
      const at = kids.map((e, i) => e.matches('details.sect') ? i : -1).filter(i => i >= 0);
      for (let i = (at[0] ?? 0) + 1; i < (at.at(-1) ?? 0); i++)
        if (!kids[i].matches('details.sect')) between.push(named(kids[i]));
    });
    const first = [...host.querySelectorAll('details.sect')].find(vis);
    host.querySelectorAll('.sectjump, [data-chips]').forEach(b => {
      if (first && vis(b) && !first.contains(b) && (first.compareDocumentPosition(b) & Node.DOCUMENT_POSITION_FOLLOWING))
        late.push(named(b));
    });
    // Above the first section, only what a page's top is made of: its
    // tiles, its chips and jump bar, and its head (the operator, 25 Oct: no
    // loose words at a page's top; a page says what it knows the way a
    // node's head does, its name, its state and its facts).
    // Words at its top: a hint or a status line before its first section,
    // or words in its bar beside the controls (a count, an uptime, a name);
    // a notice keeps its own voice and box, and a head is where facts go.
    const loose = [];
    const list = first?.parentElement || host.querySelector('.doclist');
    for (const e of list ? list.children : []){
      if (e === first) break;
      if (!vis(e) || e.closest('.pghead')) continue;
      const w = e.matches('.hint, .headline, .tchead') ? e : e.querySelector(':scope > .hint, :scope > .headline, :scope > .tchead');
      if (w && vis(w)) loose.push(`${named(w)}: ${w.textContent.replace(/\s+/g, ' ').trim().slice(0, 60)}`);
    }
    host.querySelectorAll('.docbarrow .barfacts, .docbarrow > .dim, .docbarrow > span.sub').forEach(w => {
      if (vis(w) && w.textContent.trim()) loose.push(`bar: ${w.textContent.replace(/\s+/g, ' ').trim().slice(0, 60)}`);
    });
    return { between, late, loose };
  });
  ok(shape.loose.length === 0, `[${kind}] its top says what it knows in a head, not in loose words${shape.loose.length ? `; loose: ${shape.loose.join(' | ')}` : ''}`);
  ok(shape.between.length === 0, `[${kind}] nothing stands between its sections${shape.between.length ? `; between: ${shape.between.join(', ')}` : ''}`);
  ok(shape.late.length === 0, `[${kind}] its pills are at its top, before its first section${shape.late.length ? `; after it: ${shape.late.join(', ')}` : ''}`);
  // No button on a line of its own at a page's top (the operator, 29 Oct:
  // "a line in one, weird text above the button on the other"): a bar, a
  // control row or a band over the list holding nothing but buttons, or a
  // head's one action left under its facts rather than in its corner.
  const lone = await page.evaluate(() => {
    const doc = [...document.querySelectorAll('.pane .doc.on')].find(d => d.checkVisibility());
    if (!doc) return [];
    const vis = e => e.checkVisibility({ visibilityProperty: true, opacityProperty: true }) && e.getBoundingClientRect().height > 0;
    const onlyButtons = row => {
      const texts = [...row.querySelectorAll('*')].filter(e => vis(e) && [...e.childNodes].some(n => n.nodeType === 3 && n.textContent.trim()));
      // One button with nothing beside it: a row of several (History,
      // Reorder, Add to roadmap) is a control row and keeps its line.
      const btn = [...row.querySelectorAll('button, a.btn')].filter(vis);
      return btn.length === 1 && !row.querySelector('input:not([type=checkbox]):not([hidden]), select, textarea')
        && texts.every(e => e.closest('button, a.btn'));
    };
    const out = [];
    doc.querySelectorAll(':is(.doctab, .doctab > .doclist, .nbview) > :is(.docbarrow, .nbhead, .field)').forEach(r => {
      // ...unless it shares its line with something (the tiles at its left).
      const b = r.getBoundingClientRect();
      const shares = [...r.parentElement.children].some(o => o !== r && vis(o) && o.getBoundingClientRect().top < b.bottom - 2 && o.getBoundingClientRect().bottom > b.top + 2);
      if (vis(r) && !shares && !r.closest('.pghead') && onlyButtons(r)) out.push(`${r.className.split(' ').slice(0, 3).join('.')}: ${r.textContent.replace(/\s+/g, ' ').trim().slice(0, 40)}`);
    });
    doc.querySelectorAll('.pghead > .actbar').forEach(a => {
      const b = [...a.children].filter(vis);
      if (vis(a) && b.length === 1 && b[0].matches('button, a.btn') && getComputedStyle(a.parentElement).display !== 'grid')
        out.push(`head: ${b[0].textContent.trim().slice(0, 30)} under its facts`);
    });
    return out;
  });
  ok(lone.length === 0, `[${kind}] no button stands on a line of its own at its top${lone.length ? `; alone: ${lone.join(' | ')}` : ''}`);
  const L = await language();
  ok(!L.err, `[${kind}] measurable for the button language (${L.err || 'ok'})`);
  if (!L.err){
  ok(L.loose.length === 0,
     `[${kind}] every set of text buttons is an action bar${
       L.loose.length ? `; not: ${L.loose.join(', ')}` : ''}`);
  ok(L.order.length === 0,
     `[${kind}] nothing safe sits after a verb that cannot be undone${
       L.order.length ? `: ${L.order.join(', ')}` : ''}`);
  ok(L.alien.length === 0,
     `[${kind}] every button speaks in the page's font${L.alien.length ? `; not: ${L.alien.slice(0, 6).join(', ')}` : ''}`);
  ok(L.flat.length === 0,
     `[${kind}] a notice is sans behind a bar of its color${L.flat.length ? `; not: ${L.flat.slice(0, 6).join(', ')}` : ''}`);
  ok(L.tight.length === 0,
     `[${kind}] words keep room from the buttons under them${L.tight.length ? `; not: ${L.tight.slice(0, 6).join(', ')}` : ''}`);
  L.layout.forEach(x => seenBars.add(x));
  L.sects.forEach(x => seenSects.add(x.skin));
  L.reds.forEach(x => seenReds.add(x));
  const wordy = L.sects.filter(x => x.status.length > 24).map(x => x.status);
  ok(wordy.length === 0,
     `[${kind}] a section's status is a word or a number, not a sentence${
       wordy.length ? `: ${JSON.stringify(wordy)}` : ''}`);
  }
  const S = await spanning();
  ok(!S.err && S.wide.length === 0,
     `[${kind}] no control or row of controls spans the tab${
       S.err ? ` (${S.err})` : S.wide.length ? `: ${S.wide.join(', ')}` : ''}`);
  const U = await lineup();
  ok(!U.err && U.off.length === 0,
     `[${kind}] every control on a line ends at the same height${
       U.err ? ` (${U.err})` : U.off.length ? `: ${U.off.join('; ')}` : ''}`);
  ok(!U.err && U.sizes.length === 0,
     `[${kind}] every control on a line is one height${
       U.err ? ` (${U.err})` : U.sizes.length ? `: ${U.sizes.join('; ')}` : ''}`);
  const room = await headRoom();
  ok(room.length === 0,
     `[${kind}] every section's first line keeps room under its head${room.length ? `; touching: ${room.join(', ')}` : ''}`);
  const side = await sideRoom();
  ok(side.length === 0, `[${kind}] nothing in a section or a placeholder sits on its side wall${side.length ? `; on it: ${side.slice(0, 8).join(', ')}` : ''}`);
  const bare = await rowsWearTheClass();
  ok(bare.length === 0, `[${kind}] every row of controls wears .ctlrow${bare.length ? `; not: ${[...new Set(bare)].join(', ')}` : ''}`);
  const forms = await formsHold();
  ok(forms.length === 0, `[${kind}] its forms hold the rule: a label over its field, fields not touching${forms.length ? `; not: ${forms.slice(0, 10).join('; ')}` : ''}`);
  const wide = await pickersFit();
  ok(wide.length === 0, `[${kind}] a pulldown in a bar or a row is as wide as its longest answer, never stretched${wide.length ? `; not: ${wide.slice(0, 8).join('; ')}` : ''}`);
  const G = await glance();
  if (!G.err && (G.tiles || G.facts))
    ok(G.bad.length === 0,
       `[${kind}] its tiles are one height in the stat voice and its facts labels over mono values (${G.tiles} tiles, ${G.facts} grids${
         G.bad.length ? `; ${G.bad.join(', ')}` : ''})`);
  if (!G.err && G.tables)
    ok(G.tbad.length === 0, `[${kind}] its tables line every row's cells up under the header (${G.tables} tables${
      G.tbad.length ? `; ${G.tbad.slice(0, 3).join(', ')}` : ''})`);
}
ok(seenBars.size <= 1,
   `an action bar lays out the same on every tab (${JSON.stringify([...seenBars])})`);
ok(new Set(Object.values(tabRows)).size === 1,
   `a page's tab row is one height on every page, with an action in it or not (${JSON.stringify(tabRows)})`);
// ...and on a phone, the pages that differed: a group's with actions and
// without, and the pages standing alone.
await section("a page's tab row on a phone", async () => {
  await page.setViewportSize({ width: 393, height: 851 });
  const phone = {};
  for (const [g, t] of [['machines', 'nodes'], ['machines', 'storage'], ['containers', 'docker'], ['home'], ['projects'], ['jobs']]) {
    await page.evaluate(([g, t]) => t ? railGo(g, t) : railGo(g), [g, t]);
    await page.waitForSelector('#pane0 .bar.page', { timeout: 15000 }).catch(() => {});
    await arrived();
    const row = await tabRow();
    if (row !== null) phone[t || g] = row;
  }
  await page.setViewportSize({ width: 1280, height: 900 });
  await arrived();
  ok(new Set(Object.values(phone)).size === 1 && Object.values(phone).every(v => v === Object.values(tabRows)[0]),
     `...and the same height on a phone (${JSON.stringify(phone)})`);
});
// A group's head (Machines, Build, Containers) is one row a little taller
// than its tab row, at a desk and on a phone: the node's picker and its
// state pill, no facts line under them (the operator, 17 Nov).
await section("a group's head is one row", async () => {
  const got = {};
  for (const w of [1280, 393]){
    await page.setViewportSize({ width: w, height: w > 900 ? 900 : 851 });
    for (const [g, t] of [['machines', 'nodes'], ['build', 'library'], ['containers', 'docker']]){
      await page.evaluate(([g, t]) => railGo(g, t), [g, t]);
      await page.waitForSelector('#pane0 .bar.page.grouped .phead', { timeout: 15000 }).catch(() => {});
      await arrived();
      got[`${t}@${w}`] = await page.evaluate(() => {
        const h = document.querySelector('#pane0 .bar.page.grouped .phead'), row = document.querySelector('#pane0 .bar.page.grouped > .subrow');
        if (!h || !row) return null;
        const want = parseFloat(getComputedStyle(document.documentElement).getPropertyValue('--ghead-h'));
        return { h: Math.round(h.getBoundingClientRect().height), row: Math.round(row.getBoundingClientRect().height), want, facts: !!h.querySelector('.pfacts') };
      });
    }
  }
  await page.setViewportSize({ width: 1280, height: 900 });
  await arrived();
  const off = Object.entries(got).filter(([, m]) => !m || m.h !== m.want || m.h <= m.row || m.facts).map(([k, m]) => `${k} ${JSON.stringify(m)}`);
  ok(!off.length, `a group's head is one row of --ghead-h, taller than its tab row, with no facts line, at a desk and on a phone${
     off.length ? `; not: ${off.join('; ')}` : ''}`);
});
}

if (runs('a')) {
// ---- one loading line and one empty state -----------------------------------
// docs/design-language.md, Document tabs: `.loading` while it waits and
// `.empty` when there is nothing, inside the list. Read off the SOURCE, since
// an empty state is only on screen when the data happens to be empty, and the
// fixtures are not. Five classes were doing these two jobs (R70 step 3).
await section("one loading line and one empty state", async () => {
  const { readdirSync, readFileSync } = await import('node:fs');
  // Not `new URL`: URL in this file is the dashboard's address, from lib.mjs.
  const here = (await import('node:path')).resolve(import.meta.dirname, '..') + '/';
  const off = [];
  for (const f of readdirSync(here).filter(n => /^(nb-|tab-|page-).*\.js$|^index\.html$/.test(n))){
    readFileSync(here + f, 'utf8').split('\n').forEach((line, i) => {
      if (/<[a-z]+ class="(?!loading)[^"]*">loading…/.test(line)) off.push(`${f}:${i + 1} a loading line not in .loading`);
      if (/class="none"/.test(line)) off.push(`${f}:${i + 1} an empty state in .none`);
      // A <div>: a line of its own. A <span> saying "no AVD uses it" inside a
      // row is a fact about that row, not a list with nothing in it.
      if (/<div class="sub dim">(no |nothing |none )/.test(line)) off.push(`${f}:${i + 1} an empty state in .sub dim`);
    });
  }
  ok(off.length === 0, `a loading line is .loading and an empty state is .empty, in every script${
    off.length ? ': ' + off.join('; ') : ''}`);
});
}

if (runs('a')) {
// ---- colors and corners are tokens -------------------------------------------
// docs/design-language.md, Shape and Color: a hex outside the scheme blocks
// is the default scheme leaking into the other eleven (a danger edge typed
// six times, text on a filled accent in the default's --bg), and a radius
// typed as a number is one a scheme cannot square. Read off the stylesheet.
await section("colors and corners are tokens", async () => {
  const { readFileSync } = await import('node:fs');
  const path = await import('node:path');
  // The stylesheet's files, a cascade layer each (R9 step 4), rule by rule:
  // a scheme's own rules (its tokens, and a hull of its own like Nostromo's,
  // scoped by data-theme or data-mode) define hex; nothing else does.
  const dir = path.resolve(import.meta.dirname, '..');
  const off = [];
  for (const name of ['page-skin.css', 'page-components.css', 'page-surfaces.css', 'page-overrides.css']){
    const css = readFileSync(path.join(dir, name), 'utf8').replace(/\/\*[\s\S]*?\*\//g, m => m.replace(/[^\n]/g, ' '));
    for (const m of css.matchAll(/([^{};]*)\{([^{}]*)\}/g)){
      const sel = m[1].trim();
      if (/data-theme|data-mode|^:root\b|^html\b/.test(sel)) continue;
      const line = css.slice(0, m.index + m[1].length).split('\n').length;
      // Black and white inside a color-mix() are not colors of a scheme, and
      // #2b2b2b is the terminal's own ground (see .slot.ownterm), never a page color.
      const hex = m[2].replace(/#000000|#ffffff|#2b2b2b/g, '');
      if (/#[0-9a-fA-F]{6}\b/.test(hex)) off.push(`${name}:${line}: ${sel.slice(0, 50)}`);
      if (/border-radius:(8|6|4|10)px/.test(m[2])) off.push(`${name}:${line}: ${sel.slice(0, 50)}`);
    }
  }
  ok(off.length === 0, `no hex color and no numbered corner outside the scheme blocks (${off.length ? off.slice(0, 4).join('; ') : 'none'})`);
});
}

if (runs('a')) {
// ---- a fold stays the way it was left ---------------------------------------
// A redraw rebuilds the markup, so a <details> with nothing behind it goes
// back to however it was first drawn: the Docker manager's Details fold shut
// itself on a phone every time a job took a step. A fold is remembered one of
// two ways: a data-sect key, which the page's one toggle listener records
// (sectAttr and docSection both write it), or a list row that carries its own
// identity and whose view keeps the open set itself.
async function forgetfulFolds(){
  return page.evaluate(() => {
    const host = document.querySelector('.doc.on');
    if (!host) return { err: 'no document box found' };
    const own = 'details[data-file], details[data-key], details[data-id], details[data-i], details[data-path], details[data-branch]';
    return { bare: [...host.querySelectorAll('details')]
      .filter(d => !d.dataset.sect && !d.matches(own))
      .map(d => `details.${d.className || '(no class)'} "${
        (d.querySelector('summary')?.textContent || '').trim().slice(0, 30)}"`) };
  });
}
for (const kind of kinds){
  if (!DRIVERS[kind]) continue;
  await bring(kind);
  await page.waitForSelector(DRIVERS[kind].readyWhen, { timeout: 20000 });
  const F = await forgetfulFolds();
  ok(!F.err && F.bare.length === 0,
     `[${kind}] every fold is remembered across a redraw${
       F.err ? ` (${F.err})` : F.bare.length ? `: ${[...new Set(F.bare)].join('; ')}` : ''}`);
  // A poll that brings nothing new writes nothing (R218 step 10): the page,
  // its bar, the rail and the dock stay the very nodes they were, so a
  // pointer resting on one keeps its hover and nothing fades in again. Read
  // over a third status read, the first two letting the page's own fetches
  // land; the header's uptime and the doctor's "ran 2 min ago" are the
  // things that move with time (B814: it aged across a minute in the window).
  // The first two reads and what they set off landed before the third is
  // watched: two fixed pauses of 600 ms were not that under a whole run's
  // load, and the Settings page's own read landed in the window (17 Nov).
  await page.evaluate(async () => { await refresh(); await refresh(); });
  await settled(page, { quiet: 600, cap: 20000 });
  const quietRead = await page.evaluate(async () => {
    const seen = [];
    const name = e => e ? (e.id ? '#' + e.id : e.tagName.toLowerCase() + (typeof e.className === 'string' && e.className ? '.' + e.className.trim().split(/\s+/)[0] : '')) : '?';
    const mo = new MutationObserver(ms => ms.forEach(m => {
      const t = m.target.nodeType === 1 ? m.target : m.target.parentElement;
      // A clock's text (an age a row says, marked .ago), a measure a read
      // brings and the page writes in place (free space, marked .meas), and
      // a terminal's own drawing (what it prints, its cursor), are not the
      // page drawing again for a read: an age crosses a minute between two
      // reads, and free space moves as anything is written.
      if (t?.closest('#uptime, #docWhen, .xterm, .ago, .meas')) return;
      seen.push(`${name(t)} ${m.type === 'attributes' ? '@' + m.attributeName : m.type}`);
    }));
    // ...unless it did bring something: a token the page follows that moved
    // in the window (a node's heartbeat on the Nodes page) is news the page
    // is right to draw (B789), counted as page-poll.js counts it.
    const r0 = { ...revs };
    mo.observe(document.body, { subtree: true, childList: true, characterData: true, attributes: true });
    await refresh(); await new Promise(r => setTimeout(r, 600));
    mo.disconnect();
    const moved = Object.keys(revs).filter(k => k !== 'boot' && r0[k] !== revs[k] && (!REVS_PAGE_ONLY[k] || REVS_PAGE_ONLY[k]()));
    return { seen: [...new Set(seen)], moved };
  });
  ok(quietRead.seen.length === 0 || quietRead.moved.length > 0,
     `[${kind}] a status read that brings nothing new writes nothing${quietRead.seen.length ? ': ' + quietRead.seen.slice(0, 6).join('; ') : ''}${
       quietRead.moved.length ? '; moved: ' + quietRead.moved.join(', ') : ''}`);
  // A draw adds no listener to what the last draw kept (R244 step 3): a
  // patch keeps the page's elements, so a handler wired with
  // addEventListener at every draw is wired once more each time and a press
  // runs it twice. Set as a property (onclick =) it is the same handler
  // again. The page is drawn twice over (a page's render forced, a
  // notebook view shown again, which reads and draws it), and every
  // listener added in that window to an element that was already there, or
  // to window or document, is named. Adding the same function again is
  // nothing in the DOM and is not counted; nor is one that removes itself
  // after its first event.
  const wired = await page.evaluate(async view => {
    if (!window.__lsn){
      const seen = new WeakMap(), add = EventTarget.prototype.addEventListener;
      window.__lsn = { on: false, got: [] };
      EventTarget.prototype.addEventListener = function(type, fn, opts){
        const once = typeof opts === 'object' && opts?.once;
        const cap = typeof opts === 'boolean' ? opts : !!opts?.capture;
        let m = seen.get(this); if (!m) seen.set(this, m = new Map());
        const k = type + (cap ? ':c' : ''), fns = m.get(k) || new Set(); m.set(k, fns);
        if (window.__lsn.on && !once && !fns.has(fn)) window.__lsn.got.push({ el: this, type });
        fns.add(fn);
        return add.call(this, type, fn, opts);
      };
    }
    const name = e => e === window ? 'window' : e === document ? 'document' : e.id ? '#' + e.id
      : e.tagName.toLowerCase() + (typeof e.className === 'string' && e.className ? '.' + e.className.trim().split(/\s+/)[0] : '');
    const draw = async () => {
      if (view) getNotebook('alpha').view(view);
      else { const p = document.getElementById('pane0'); if (p) delete p.dataset.rev; drawPanes(); }
      await new Promise(r => setTimeout(r, 1200));
    };
    await draw();                                    // the first draw's own additions are its first wiring
    const before = new WeakSet([window, document, ...document.querySelectorAll('*')]);
    window.__lsn.got = []; window.__lsn.on = true;
    await draw(); await draw();
    window.__lsn.on = false;
    return [...new Set(window.__lsn.got.filter(x => before.has(x.el)).map(x => `${name(x.el)} ${x.type}`))];
  }, kind.startsWith('notebook:') ? kind.slice('notebook:'.length) : '');
  ok(wired.length === 0, `[${kind}] a draw adds no listener to what the last draw kept${wired.length ? ': ' + wired.slice(0, 6).join('; ') : ''}`);
  // What a draw brings is the draw's own (R9 step 6, drawn): on the page as
  // drawn, every proseline is wired, no title is left to show as a
  // tooltip, and every data-style is applied. A draw that writes markup
  // some way that does not call drawn() leaves one of these behind.
  const brought = await page.evaluate(() => {
    const on = e => !e.closest('template') && !(e instanceof SVGElement);
    const prose = [...document.querySelectorAll('textarea.proseline:not([data-prose])')].filter(on);
    const titled = [...document.querySelectorAll('[title]')].filter(on).filter(e => !e.closest('#termwin, .xterm'));
    const unstyled = [...document.querySelectorAll('[data-style]')].filter(on).filter(e => !e.style.cssText);
    const name = e => e.tagName.toLowerCase() + (e.id ? '#' + e.id : typeof e.className === 'string' && e.className ? '.' + e.className.trim().split(/\s+/)[0] : '');
    return [...prose.map(e => 'proseline ' + name(e)), ...titled.map(e => 'title ' + name(e)), ...unstyled.map(e => 'data-style ' + name(e))];
  });
  ok(brought.length === 0, `[${kind}] what a draw brings is there: proselines wired, no title left, every data-style applied${brought.length ? ': ' + brought.slice(0, 6).join('; ') : ''}`);
}
}

if (runs('a')) {
// ---- a setting is written by Save, never by the pick -----------------------
// docs/design-language.md, Settings: nothing on a tab takes effect until Save
// or Apply is pressed, because a select that writes on the change is a control
// that cannot be reconsidered, and the same section's Save then means two
// different things. The one exception is the color scheme in the gear, which
// is not on a document tab and is not measured here.
//
// Read off the HANDLERS, which is the only place the answer lives: a control
// that writes and one that stages look identical in the markup. The page
// assigns `el.onchange = …` almost everywhere, and a function's own source
// says whether it posts. What this cannot see is a listener added with
// addEventListener, so it is a guard against the easy mistake rather than a
// proof, the easy mistake being the one that shipped: a dial that saved on
// the pick because writing it there was three lines shorter.
//
// Filters and pickers are not settings and are allowed to act at once. They
// give themselves away by calling a LOADER rather than fetching: `loadJobs()`,
// `phFetch(…)`, `loadDocker()`. Only a literal fetch of an /api/ path in the
// handler itself is a write on the pick.
async function writesOnPick(){
  return page.evaluate(() => {
    const host = document.querySelector('.doc.on');
    const box = host?.querySelector(':scope > .doctab, :scope > .nb, :scope > div');
    if (!box) return { err: 'no document box found' };
    const out = [];
    for (const e of box.querySelectorAll('select, input[type=checkbox], input[type=radio]')){
      const src = String(e.onchange || '') + String(e.oninput || '');
      if (/fetch\s*\(\s*["'`]\/api\//.test(src))
        out.push(`${e.tagName.toLowerCase()}${e.id ? '#' + e.id : ''}${
          e.dataset.dmclaude ? '[data-dmclaude]' : ''}`);
    }
    return { wrote: out };
  });
}
for (const kind of kinds){
  if (!DRIVERS[kind]) continue;
  await bring(kind);
  await page.waitForSelector(DRIVERS[kind].readyWhen, { timeout: 20000 });
  const W = await writesOnPick();
  ok(!W.err && W.wrote.length === 0,
     `[${kind}] no setting writes itself on the pick${
       W.err ? ` (${W.err})` : W.wrote.length ? `: ${W.wrote.join(', ')}` : ''}`);
}
}

if (runs('a')) {
// ---- adding goes at the top ------------------------------------------------
// The control that adds to a notebook view is the last button on its control
// row, the primary (R109), its form unrolling under that row; one that adds
// to a section is the first band inside it, above the list. Never at the
// foot, where a phone scrolled past every row to find it. Measured on each
// view that has one, against its head row and the first row of its list.
await section("adding goes at the top", async () => {
  await bring('notebook');
  const misplaced = [];
  for (const v of ['roadmap', 'bugs', 'briefing', 'signing', 'wiki']){
    await page.evaluate(w => getNotebook('alpha').view(w), v);
    await page.waitForFunction(w => document.querySelector(`.nb .nbview[data-view="${w}"] [data-add]`)?.offsetHeight > 0,
                               v, { timeout: 20000 });
    const r = await page.evaluate(w => {
      const view = document.querySelector(`.nb .nbview[data-view="${w}"]`);
      const headEl = view.querySelector(':scope > .nbhead');
      const head = headEl.getBoundingClientRect();
      const acts = [...headEl.querySelectorAll('.actbar > button')].filter(b => b.checkVisibility());
      return [...view.querySelectorAll('[data-add]')].filter(a => a.checkVisibility()).map(a => {
        if (headEl.contains(a)){
          const last = acts[acts.length - 1];
          // The view's own add: on the control row, the primary last.
          return { add: a.dataset.add, belowHead: true, aboveList: true, button: a.tagName === 'BUTTON',
                   last: !!last && last.dataset.add !== undefined && last.classList.contains('primary') };
        }
        const box = a.getBoundingClientRect();
        // The list this control adds to: the nearest following sibling band
        // holding rows, or the section's own list for a rule.
        const list = a.dataset.add === 'rule' ? view.querySelector('#rlList')
                   : a.dataset.add === 'memory' ? view.querySelector('#memList')
                   : a.dataset.add === 'bug' ? view.querySelector('#bugList')
                   : ['key', 'import'].includes(a.dataset.add) ? view.querySelector('#sgBox')
                   : view.querySelector('#roadmapList');
        const row = list?.firstElementChild?.getBoundingClientRect();
        return { add: a.dataset.add, belowHead: box.top >= head.bottom - 1,
                 aboveList: !row || box.bottom <= row.top + 1,
                 button: !!a.querySelector('button'), last: true };
      });
    }, v);
    r.filter(x => !(x.belowHead && x.aboveList && x.button && x.last)).forEach(x => misplaced.push(`${v}:${x.add} ${JSON.stringify(x)}`));
  }
  ok(misplaced.length === 0,
     `every view's add is the primary last on its control row, and a section's sits under the head row and above its list, as a button${
       misplaced.length ? `; not: ${misplaced.join('; ')}` : ''}`);
  // Save and Revert only where something can be staged behind them: a Save
  // under a list that writes through read as a button that did nothing.
  const foots = {};
  for (const v of ['roadmap', 'briefing', 'artifacts', 'design', 'signing', 'bugs', 'analysis', 'tests', 'git']){
    await page.evaluate(w => getNotebook('alpha').view(w), v);
    await page.waitForFunction(w => document.querySelector(`.nb .nbview[data-view="${w}"]`)?.checkVisibility(),
                               v, { timeout: 20000 });
    // The notebook on screen, not the first in the DOM: a second project's
    // notebook may be parked before it. Waited on until the view has drawn
    // (its head row is there), then read once: proving a foot ABSENT by
    // waiting a timeout out cost three seconds a view, four views a run.
    const nbSel = w => `.nbview[data-view="${w}"]`;
    await page.waitForFunction(w => !![...document.querySelectorAll('.nb')].find(n => n.checkVisibility())
      ?.querySelector(`.nbview[data-view="${w}"] .nbhead`), v, { timeout: 15000 });
    // ...and what the view read has landed: a foot is drawn with its section.
    await settled(page);
    foots[v] = await page.evaluate(w => !![...document.querySelectorAll('.nb')]
      .find(n => n.checkVisibility())?.querySelector(`.nbview[data-view="${w}"] .sectbar[data-bar]`), v);
    void nbSel;
  }
  // Artifacts carries one only where a Version can stage a bump, which this
  // fixture's alpha, with no commits, cannot (version.mjs holds that one).
  ok(foots.roadmap && foots.briefing && foots.design && foots.signing && !foots.bugs && !foots.analysis && !foots.tests && !foots.git,
     `a section's own Save and Revert are on the views that stage and on no other (the operator, 5 Oct: there is no foot) (${JSON.stringify(foots)})`);
});
}

if (runs('b')) {
// ---- the notebook's head row ------------------------------------------------
// Every view opens with the same row: its one-line summary left, its History
// right, and that row is the FIRST band of the view, so the History sits at
// one height whichever tab is open. Measured rather than read from the
// markup, because the Briefing tab once put a section above its head and
// every other rule here still passed.
await section("the notebook's head row", async () => {
  await bring('notebook');
  await page.waitForSelector('.nb .nbview:not([hidden]) .field', { timeout: 20000 });
  const views = await page.$$eval('.nb .nbview', vs => vs.map(v => v.dataset.view));
  const heads = {};
  // Read the ruler when it has STOPPED MOVING, rather than after a fixed
  // pause. 150ms was enough on an idle box and not on a loaded one, so the
  // Bugs view came back two pixels lower than every other about one run in
  // three and this check went red for the suite rather than for the page
  // (B116). Two agreeing reads is the condition; the pause was never the
  // thing being tested.
  const still = async (w) => {
    // The view's own reads landed first: a placeholder holds still for two
    // reads 50 ms apart under a whole run's load, and Analysis was measured
    // so, two pixels low (B927).
    await settled(page, { quiet: 300, cap: 15000 });
    let last = null;
    for (let i = 0; i < 80; i++){
      // The head row and the view's first band (the glance, ordered over
      // it), both still, since the first band is what is measured.
      const now = await page.evaluate(x => {
        const v = document.querySelector(`.nb .nbview[data-view="${x}"]`);
        const h = v?.querySelector(':scope > .nbhead');
        const shown = v ? [...v.children].filter(e => e.offsetHeight > 0 || e.offsetWidth > 0) : [];
        return h && shown.length ? `${Math.round(h.getBoundingClientRect().top)}/${
          Math.round(Math.min(...shown.map(e => e.getBoundingClientRect().top)))}` : null;
      }, w);
      if (now !== null && now === last) return;
      last = now;
      await sleep(50);   // the gap between the two reads that have to agree
    }
  };
  for (const v of views){
    await page.evaluate(w => getNotebook('alpha').view(w), v);
    await page.waitForFunction(w => document.querySelector(`.nb .nbview[data-view="${w}"]`)?.checkVisibility(),
                               v, { timeout: 20000 });
    await still(v);
    heads[v] = await page.evaluate(w => {
      const view = document.querySelector(`.nb .nbview[data-view="${w}"]`);
      const shown = [...view.children].filter(e => e.offsetHeight > 0 || e.offsetWidth > 0);
      const first = shown[0];
      const head = view.querySelector(':scope > .nbhead');
      return { first: first ? (first.className || first.tagName).split(/\s+/)[0] : '(nothing)',
               // A row with nothing on it is not drawn (414bbe5), and a page of
               // settings has none (Settings, Permissions: d8cce4c): then the
               // view opens with what would sit under it.
               isHead: !!first && first.classList.contains('nbhead') || !head || !head.offsetHeight,
               drawn: !!head && head.offsetHeight > 0,
               top: head ? Math.round(head.getBoundingClientRect().top) : null,
               // The view's first band, wherever the CSS orders it: since the
               // glance comes before the control row (d5dff08, the operator
               // 29 Oct), the row's own top moves with the tiles over it.
               firstTop: Math.round(Math.min(...shown.map(e => e.getBoundingClientRect().top))),
               height: head ? Math.round(head.getBoundingClientRect().height) : null,
               // The control row (R109): its search and its toggles at the
               // left, its actions in an action bar after its spacer, the
               // primary, where there is one, last.
               right: !head || (() => {
                 const sp = head.querySelector(':scope > .sp');
                 const acts = [...head.querySelectorAll(':scope > .actbar button')].filter(b => b.checkVisibility());
                 const prim = acts.filter(b => b.classList.contains('primary'));
                 return !!sp && acts.every(b => sp.compareDocumentPosition(b) & Node.DOCUMENT_POSITION_FOLLOWING)
                   && prim.length <= 1 && (!prim.length || prim[0] === acts[acts.length - 1]);
               })(),
               // Words on the row: any text outside its controls (Settings,
               // a page of settings, keeps its one line of what it is).
               words: !head || w === 'settings' || w === 'permissions' ? '' : [...head.childNodes].filter(n =>
                 (n.nodeType === 3 && n.textContent.trim()) || (n.nodeType === 1 && n.checkVisibility()
                   && !n.matches('button, input, select, .actbar, .sp, .gbpicker, #dkSeg, .nbsaidslot'))).map(n => n.textContent.trim()).join(' ').slice(0, 60),
               glance: (() => {
                 const bad = [];
                 // The glance is a status line (R274): phrases in its .pgline,
                 // no tiles left.
                 const g = view.querySelector(':scope > .nbglance');
                 if (w !== 'settings' && !g) bad.push('no glance');
                 if (g?.querySelector('.tile')) bad.push('a tile in the glance');
                 if (g) for (const t of g.querySelectorAll('.pgl')) if (!t.closest('.pgline')) bad.push('a phrase out of its line');
                 // Count-first: the line's first phrase is how many of what
                 // the view lists, a figure, before anything it says of them
                 // (one still waiting on its read has no figure yet).
                 const lead = g?.querySelector('.pgline .pgl b')?.textContent.trim();
                 if (lead && !/^\d/.test(lead)) bad.push(`its first phrase reads ${lead.slice(0, 20)}, not a count`);
                 // Every group of chips the view narrows by in one band.
                 const bands = [...view.querySelectorAll(':scope > .lfilter')].filter(b => b.checkVisibility());
                 if (bands.length > 1) bad.push(`${bands.length} chip bands`);
                 // A Save or Revert on a row of its own straight under the view.
                 for (const b of view.querySelectorAll(':scope > .field > .sectbar'))
                   if (b.checkVisibility() && !b.closest('.nbsaid')) bad.push('a loose Save row');
                 // The glance comes after the control row and before the chips.
                 if (g && bands[0] && !(g.compareDocumentPosition(bands[0]) & Node.DOCUMENT_POSITION_FOLLOWING)) bad.push('chips above the tiles');
                 return bad.join(', ');
               })() };
    }, v);
  }
  const notFirst = Object.entries(heads).filter(([, h]) => !h.isHead).map(([v, h]) => `${v} opens with ${h.first}`);
  ok(notFirst.length === 0,
     `every notebook view opens with its head row${notFirst.length ? `; not: ${notFirst.join(', ')}` : ''}`);
  // Within a pixel: a top on a half pixel rounds either way, 212 on one view
  // and 213 on the next with nothing drawn differently (B504, B116).
  const drawnHeads = Object.values(heads).filter(h => h.drawn);
  const topsAt = Object.values(heads).map(h => h.firstTop);
  ok(Math.max(...topsAt) - Math.min(...topsAt) <= 1,
     `...and every view's first band starts at one height (${JSON.stringify(
       Object.fromEntries(Object.entries(heads).map(([v, h]) => [v, h.firstTop])))})`);
  ok(Object.values(heads).every(h => h.right),
     '...with its actions, where it has any, at the right of the row, the primary last');
  ok(Object.values(heads).every(h => !h.words),
     `...and no words on it but its status line in the row's slot, the counts being the glance's tiles (R109; ${JSON.stringify(
       Object.fromEntries(Object.entries(heads).filter(([, h]) => h.words).map(([v, h]) => [v, h.words])))})`);
  const hs = drawnHeads.map(h => h.height);
  ok(Math.max(...hs) - Math.min(...hs) <= 1,
     `...one control high on every view that draws its row, the Containers page's bar (${JSON.stringify(
       Object.fromEntries(Object.entries(heads).filter(([, h]) => h.drawn).map(([v, h]) => [v, h.height])))})`);
  const glance = Object.entries(heads).filter(([, h]) => h.glance).map(([v, h]) => `${v}: ${h.glance}`);
  ok(glance.length === 0,
     `...and under it the glance: tiles in the tiles' shape, then a status line, then one band of chips, and no loose Save row (R109)${
       glance.length ? `; not: ${glance.join('; ')}` : ''}`);
});

// Every row of a notebook's lists opens the room a .row does (--row-y)
// above its first line: a bug, a memory, a rule, a roadmap item, a test, a
// commit, a file and a conversation alike, so the lists read at one pace
// from view to view.
await section("the notebook's lists keep one rhythm", async () => {
  await bring('notebook');
  const views = await page.$$eval('.nb .nbview', vs => vs.map(v => v.dataset.view));
  const off = [], seen = new Set();
  for (const v of views){
    await page.evaluate(w => getNotebook('alpha').view(w), v);
    await page.waitForFunction(w => document.querySelector(`.nb .nbview[data-view="${w}"]`)?.checkVisibility(), v, { timeout: 20000 });
    await sleep(300);
    const got = await page.evaluate(w => {
      const view = document.querySelector(`.nb .nbview[data-view="${w}"]`);
      const want = parseFloat(getComputedStyle(document.documentElement).getPropertyValue('--row-y'));
      const pad = e => parseFloat(getComputedStyle(e).paddingTop) || 0;
      return [...view.querySelectorAll('.row,details.bug,details.mem,details.tst,details.grp,.artrow,.grow[data-sha]')]
        .filter(r => r.checkVisibility()).map(r => {
          // A row that opens has its line in its summary; a roadmap item's
          // line sits in the summary's own line.
          const line = r.matches('details') ? r.querySelector(':scope > summary') : r;
          const inner = r.matches('details.grp') ? r.querySelector(':scope > summary > .roadmap') : null;
          return { kind: r.className.split(/\s+/)[0], top: pad(line) + (line !== r ? pad(r) : 0) + (inner ? pad(inner) : 0), want };
        });
    }, v);
    for (const g of got){ seen.add(g.kind); if (Math.abs(g.top - g.want) > 0.5) off.push(`${v} ${g.kind} ${g.top}px`); }
  }
  ok(!off.length && seen.size >= 4, `every row of a notebook's lists opens --row-y above its first line (${[...seen].join(', ')}${
     off.length ? '; off: ' + [...new Set(off)].join(', ') : ''})`);
});
ok(seenSects.size <= 1,
   `a section heading wears one skin everywhere (${JSON.stringify([...seenSects])})`);
await section("B495: a password manager offers itself only where a password or an", async () => {
  // B495: a password manager offers itself only where a password or an
  // account is asked for; every other field on the page says so, drawn
  // late or not.
  const loud = await page.$$eval('input, textarea', es => es.filter(e => {
    const t = (e.getAttribute('type') || 'text').toLowerCase();
    if (['password', 'hidden', 'checkbox', 'radio', 'file'].includes(t)) return false;
    if (['username', 'current-password', 'new-password', 'one-time-code', 'email'].includes((e.getAttribute('autocomplete') || '').toLowerCase())) return false;
    return e.dataset.bwignore === undefined;
  }).map(e => e.id || e.name || e.className).slice(0, 8));
  ok(loud.length === 0, `every field that is not a password or an account tells password managers to stay away (${JSON.stringify(loud)})`);
  // B533: Bitwarden honors data-bwignore only when its user opts in, and
  // reads one textarea that names a public key as an add-an-SSH-key form,
  // then offers itself on every field labeled name, title or description.
  // So no textarea on the page may read as one, by Bitwarden's own words.
  const sshy = await page.$$eval('textarea', es => es.filter(e => {
    // Each attribute is split on its own, as Bitwarden does: whole, by
    // word, and by word with the spaces taken out ("public key" is publickey).
    const said = [e.id, e.name, e.className, saidOf(e), e.placeholder,
                  e.getAttribute('aria-label'), ...[...(e.labels || [])].map(l => l.textContent)]
      .filter(Boolean).map(v => v.toLowerCase().replace(/-/g, ''));
    const words = new Set(said.flatMap(v => [v, ...v.split(/[^\p{L}\d]+/u),
                                             ...v.replace(/\s/g, '').split(/[^\p{L}\d]+/u)]));
    return ['publickey', 'sshkey'].some(w => words.has(w))
      || said.some(v => /ssh(rsa|ed25519|dss)|ecdsasha2/.test(v));
  }).map(e => e.id || e.className));
  ok(sshy.length === 0, `...and no text box reads to Bitwarden as an SSH public key (${JSON.stringify(sshy)})`);
});
await section("The header's buttons are one box", async () => {
  // The header's buttons are one box (the operator, 5 Oct): the bell stood
  // taller and wider than the bug, gear and sign-out beside it on a desk.
  const hb = await page.$$eval('header > button', bs => bs.filter(b => b.offsetParent).map(b => {
    const r = b.getBoundingClientRect();
    return { id: b.id, h: Math.round(r.height), w: Math.round(r.width) };
  }));
  const icons = hb.filter(b => b.id !== 'bAbout');
  ok(new Set(hb.map(b => b.h)).size === 1 && new Set(icons.map(b => b.w)).size === 1,
     `the header's buttons share one height, and its icon buttons one width (${JSON.stringify(hb)})`);
  // ...and what an icon button holds sits in its middle (the operator, 15
  // Oct: the doctor's dot sat at the start of its button on a phone).
  const offCenter = () => page.$$eval('header > button', bs => bs.filter(b => b.offsetParent && b.id !== 'bAbout').map(b => {
    const r = b.getBoundingClientRect(), c = b.querySelector('svg, .st, span');
    if (!c) return null;
    const q = c.getBoundingClientRect();
    return Math.abs((q.left + q.width / 2) - (r.left + r.width / 2)) > 1.5 ? b.id : null;
  }).filter(Boolean));
  const desk = await offCenter();
  await page.setViewportSize({ width: 393, height: 851 });
  await atWidth(page, 393);
  const phone = await offCenter();
  await page.setViewportSize({ width: 1280, height: 900 });
  await atWidth(page, 1280);
  ok(!desk.length && !phone.length, `...and each icon sits in the middle of its button, at a desk and on a phone (${JSON.stringify({ desk, phone })})`);
});
await section("The frame's lines of controls are one height each, as a page's are", async () => {
  // The frame's lines of controls are one height each, as a page's are
  // (B142): the header's search stood 32px beside 38px buttons, and the
  // dock's + and its pull 30px beside 34px tabs, at every width.
  const frameLines = () => page.$$eval('header, .pane .bar.dockbar', fs => fs.flatMap(f => {
    const cs = [...f.querySelectorAll('button, input, .dtab')].filter(e => e.offsetParent)
      .map(e => ({ e, r: e.getBoundingClientRect() }));
    // A button inside a counted tab (its close) is part of the tab.
    const top = cs.filter(c => !cs.some(o => o !== c && o.e.contains(c.e)));
    const hs = top.map(c => Math.round(c.r.height));
    return top.length > 1 && Math.max(...hs) - Math.min(...hs) > 1.5
      ? [`${f.tagName.toLowerCase()}: ${top.map(c => `${c.e.id || c.e.className.split(' ')[0]}:${Math.round(c.r.height)}`).join(' ')}`] : [];
  }));
  const desk = await frameLines();
  await page.setViewportSize({ width: 393, height: 851 });
  await atWidth(page, 393);
  const phone = await frameLines();
  await page.setViewportSize({ width: 1280, height: 900 });
  await atWidth(page, 1280);
  ok(!desk.length && !phone.length,
     `the header's and the dock's controls are one height each, at a desk and on a phone (${JSON.stringify({ desk, phone })})`);
});
ok(seenReds.size <= 1,
   `a verb that cannot be undone is the same color everywhere (${JSON.stringify([...seenReds])})`);

// The fence inside the one page: a renderer that throws must break its own
// tab and nothing else: before renderGuarded, one bug in one kind's render
// took drawPanes down, and with it the poll, the strip and every terminal.
await section("The fence inside the one page", async () => {
  // Opened here, not only found: part b runs without part a's walk, which
  // is what opened it in the whole file (R130).
  await bring('findings');
  await page.evaluate(() => { const t = tabs.find(x => x.kind === 'findings');
                              if (t) focusTab(t.id); });
  const errsBefore = page.errors.length;
  await page.evaluate(() => {
    window.__realFxRender = TABKINDS.findings.render;
    TABKINDS.findings.render = () => { throw new Error('boom (deliberate)'); };
    readMoved('findings'); drawPanes();
  });
  await page.waitForFunction(() => /renderer failed/.test(
    document.querySelector('.doc.on')?.textContent || ''), null, { timeout: 8000 });
  ok(true, 'a throwing renderer becomes an error band in its own tab');
  // The page is still a page: another kind renders, the strip answers. The
  // Docker tab opened early in this file may have left the strip by now
  // (one more document kind, the Roles tab, pushed it out, 5 Oct), so it is
  // opened again where it is gone, and its picker waited for.
  await page.evaluate(() => {
    const t = tabs.find(x => x.kind === 'docker');
    if (t) focusTab(t.id); else openDocker();
  });
  const alive = await page.waitForSelector('.dmtab .dmpick', { timeout: 15000 }).then(() => true, () => false);
  ok(alive, '...and the rest of the dashboard keeps working around it');
  ok(page.errors.length > errsBefore
     && /boom \(deliberate\)/.test(page.errors[page.errors.length - 1]),
     '...while the error still reaches the console, so a caught bug is not a hidden one');
  // Deliberate, asserted, and now removed: the final zero-errors check below
  // is about bugs this suite did not cause on purpose.
  page.errors.length = errsBefore;
  await page.evaluate(() => {
    TABKINDS.findings.render = window.__realFxRender;
    delete window.__realFxRender;
    readMoved('findings'); drawPanes();
  });
  // Not waited for: the Docker tab is in front now, so the Analysis tab does
  // not draw until the loop below brings it, and a wait for its rows sat out
  // its whole timeout.
});

// A stacked box may not be aligned across its own axis, on every tab, at
// DESKTOP width, which is where it shows.
//
// align-items on a COLUMN flex box is the horizontal axis, so a rule written
// for a line of controls pushes a stacked one to an edge. That is what the
// Settings tab was: three sections in the right third of the surface, each
// starting at a different x, with six hundred pixels of nothing beside them,
// because `.row:has(.setrow){align-items:flex-end}` also matched
// `.row.stack2`. Cheap to measure, and the operator found it rather than
// this suite, which is the reason it is here.
for (const kind of kinds){
  if (!DRIVERS[kind]) continue;
  await bring(kind);
  await page.waitForSelector(DRIVERS[kind].readyWhen, { timeout: 20000 }).catch(() => {});
  await arrived();
  const skewed = await page.evaluate(() => {
    const surf = document.querySelector('.doc.on .doctab, .doc.on .nb');
    if (!surf) return [];
    const out = [];
    surf.querySelectorAll('.row, .sect, .field, .doclist > *').forEach(e => {
      const cs = getComputedStyle(e);
      if (cs.display !== 'flex' || cs.flexDirection !== 'column') return;
      if (['flex-end', 'end', 'center', 'right'].includes(cs.alignItems))
        out.push(`${e.className || e.tagName} is a column aligned ${cs.alignItems}`);
    });
    return [...new Set(out)].slice(0, 4);
  });
  ok(skewed.length === 0, `[${kind}] no stacked box is aligned across its own axis${
    skewed.length ? `: ${skewed.join('; ')}` : ''}`);
}

// A list narrowed two ways shows one All: each row of chips after the first
// names its own first chip (Any source, Any version), where the Library and
// Bugs stacked All 50 over All 50 (31 Oct sweep).
for (const kind of kinds){
  if (!DRIVERS[kind]) continue;
  await bring(kind);
  await page.waitForSelector(DRIVERS[kind].readyWhen, { timeout: 20000 }).catch(() => {});
  await arrived();
  const alls = await page.evaluate(() => {
    const surf = document.querySelector('.doc.on .doctab, .doc.on .nb');
    if (!surf) return 0;
    return [...surf.querySelectorAll('.chips')].filter(c => c.offsetParent
      && (c.querySelector('.chip')?.firstChild?.textContent || '').trim() === 'All').length;
  });
  ok(alls <= 1, `[${kind}] one All chip on a page, each further row of chips naming its own first (${alls})`);
}
}

if (runs('b')) {
// ---- what reads on a filled accent surface, on every scheme -----------------
// Seven places put --ink on --accent-deep: the active tab, a primary button,
// a button that is on, a view bar's current tab, the mobile bar's, an open
// select's chosen row, and the text selection. Twelve schemes swap the accent
// under all of them, and five of those accents were bright enough that the
// text on the fill came out under AA, nostromo worst at 3.56:1, which is the
// one somebody noticed. The active tab is measured because it had BOTH
// failures: the fill was too light, and its name is a `.lbl`, the same class
// as the quiet field-label helper, so it wore that color on top.
//
// Read off the rendered pixels through a canvas rather than computed from the
// tokens: --accent-deep is a relative color now, and the point is what the
// engine actually paints.
await section("what reads on a filled accent surface, on every scheme", async () => {
  const SCHEMES = ['default', 'nostromo', 'slate', 'carbon', 'nocturne', 'moss',
                   'ember', 'abyss', 'plum', 'rust', 'ice', 'sepia'];
  const AA = 4.5;
  const bad = [];
  // The pick measured is the page's sub-nav (R218 step 4: the strip and its
  // active tab are gone): Machines, whose Nodes is on. Its ground is the
  // bar's, showing through a tab with no fill of its own since 17 Oct.
  await page.evaluate(() => railGo('machines', 'nodes'));
  await page.waitForSelector('.pane .bar .subnav button.on', { timeout: 10000 });
  await arrived();
  // ...in both halves of each (R216): the light half writes white on the
  // same darkened accent, and its icons the same.
  for (const [t, mode] of SCHEMES.flatMap(t => [[t, ''], [t, 'light']])) {
    await page.evaluate(([th, m]) => { document.documentElement.dataset.theme = th;
      if (m) document.documentElement.dataset.mode = m; else delete document.documentElement.dataset.mode; }, [t, mode]);
    // Past the tab's own 150ms background transition: a dark half measured
    // 120ms after a light one read a blend of the two, and a fixed wait
    // read one under load too (B811), so its transitions are waited out:
    // begun, by the frame drawn in the new scheme, and then ended, below.
    await frames();
    const r = await page.evaluate(async () => {
      const el = document.querySelector('.pane .bar .subnav button.on');
      if (!el) return { err: 'no sub-nav on show' };
      await Promise.all([el, ...el.querySelectorAll('*')].flatMap(e => e.getAnimations()).map(a => a.finished.catch(() => {})));
      const c = document.createElement('canvas'); c.width = c.height = 1;
      const ctx = c.getContext('2d', { willReadFrequently: true });
      const px = v => { ctx.clearRect(0, 0, 1, 1); ctx.fillStyle = '#000'; ctx.fillRect(0, 0, 1, 1);
                        ctx.fillStyle = v; ctx.fillRect(0, 0, 1, 1);
                        const d = ctx.getImageData(0, 0, 1, 1).data; return [d[0], d[1], d[2]]; };
      const lin = x => { x /= 255; return x <= 0.04045 ? x / 12.92 : Math.pow((x + 0.055) / 1.055, 2.4); };
      const lum = a => 0.2126 * lin(a[0]) + 0.7152 * lin(a[1]) + 0.0722 * lin(a[2]);
      const R = (a, b) => { const x = lum(px(a)), y = lum(px(b));
                            const h = Math.max(x, y), l = Math.min(x, y); return (h + 0.05) / (l + 0.05); };
      // The ground the words are read on: the tab's own, or what shows
      // through it (the sub-nav's tabs have none of their own since 17 Oct).
      let bg = 'rgb(0, 0, 0)';
      for (let a = el; a; a = a.parentElement){
        const c = getComputedStyle(a).backgroundColor;
        if (c && !/^rgba\(.*,\s*0\)$|^transparent$/.test(c)){ bg = c; break; }
      }
      const at = sel => { const k = el.querySelector(sel);
                          return k ? +R(getComputedStyle(k).color, bg).toFixed(2) : null; };
      return { label: +R(getComputedStyle(el).color, bg).toFixed(2), icon: at('.ic') };
    });
    const name = mode ? `${t} (light)` : t;
    if (r.err) { bad.push(`${name}: ${r.err}`); continue; }
    if (!(r.label >= AA)) bad.push(`${name} label ${r.label}`);
    if (r.icon !== null && !(r.icon >= AA)) bad.push(`${name} icons ${r.icon}`);
  }
  await page.evaluate(() => { delete document.documentElement.dataset.theme; delete document.documentElement.dataset.mode; });
  await motionOver();
  ok(bad.length === 0,
     `the active tab's words read on its ground in all ${SCHEMES.length} schemes, dark and light${
       bad.length ? `; under ${AA}:1: ${bad.join(', ')}` : ''}`);
});
// Good, warning and error are one fixed trio (Perch, the warning a true
// yellow): the same three colors on every scheme in each half, a warning's
// band painted from its own wash whatever the scheme or a space's color
// under it, and its words AA on that wash. Mixed over a space's panel, the
// band read as a dirty olive.
await section("good, warning and error are one trio on every scheme, and a warning's band reads", async () => {
  const SCHEMES = await page.evaluate(() => THEMES.map(t => t[0]));
  const bad = [], seen = { dark: new Set(), light: new Set() };
  for (const [t, mode] of SCHEMES.flatMap(t => [[t, ''], [t, 'light']])) {
    const r = await page.evaluate(([th, m]) => {
      const root = document.documentElement;
      root.dataset.theme = th;
      if (m) root.dataset.mode = m; else delete root.dataset.mode;
      const host = document.createElement('div');
      host.className = 'pane'; host.style.cssText = 'position:absolute;left:-9999px;top:0;width:400px';
      // A space's color under it: the band must not follow it.
      host.innerHTML = '<div class="bar proj" style="--panel:#5b2a6e;--line:#8a4fa0"><div class="pnote warn pband"><span class="grow">Restart your session</span></div></div>';
      document.body.appendChild(host);
      const band = host.querySelector('.pband'), cs = getComputedStyle(band), rs = getComputedStyle(root);
      const c = document.createElement('canvas'); c.width = c.height = 1;
      const ctx = c.getContext('2d', { willReadFrequently: true });
      const px = v => { ctx.clearRect(0, 0, 1, 1); ctx.fillStyle = '#000'; ctx.fillRect(0, 0, 1, 1); ctx.fillStyle = v; ctx.fillRect(0, 0, 1, 1);
                        const d = ctx.getImageData(0, 0, 1, 1).data; return [d[0], d[1], d[2]]; };
      const lin = x => { x /= 255; return x <= 0.04045 ? x / 12.92 : Math.pow((x + 0.055) / 1.055, 2.4); };
      const lum = a => 0.2126 * lin(a[0]) + 0.7152 * lin(a[1]) + 0.0722 * lin(a[2]);
      const R = (a, b) => { const x = lum(px(a)), y = lum(px(b)); return (Math.max(x, y) + 0.05) / (Math.min(x, y) + 0.05); };
      // The wash as the page resolves it: a mix over --ground since the
      // operator's see-through band (17 Nov), which a canvas cannot read
      // from the token's text.
      const probe = document.createElement('div');
      probe.style.background = 'var(--warn-wash)';
      document.body.appendChild(probe);
      const wantWash = getComputedStyle(probe).backgroundColor;
      probe.remove();
      const out = { trio: ['--pass', '--warn', '--bad'].map(k => px(rs.getPropertyValue(k).trim()).join(',')).join(' '),
                    wash: px(cs.backgroundColor).join(','), wantWash: px(wantWash).join(','),
                    words: +R(cs.color, cs.backgroundColor).toFixed(2) };
      host.remove();
      return out;
    }, [t, mode]);
    const half = mode ? 'light' : 'dark', name = mode ? `${t} (light)` : t;
    seen[half].add(r.trio);
    if (r.wash !== r.wantWash) bad.push(`${name}: the band is ${r.wash}, not the wash ${r.wantWash}`);
    if (!(r.words >= 4.5)) bad.push(`${name}: the band's words ${r.words}:1`);
  }
  await page.evaluate(() => { delete document.documentElement.dataset.theme; delete document.documentElement.dataset.mode; });
  if (seen.dark.size !== 1) bad.push(`the dark half's trio differs by scheme: ${[...seen.dark].join(' | ')}`);
  if (seen.light.size !== 1) bad.push(`the light half's trio differs by scheme: ${[...seen.light].join(' | ')}`);
  ok(bad.length === 0, `one trio on all ${SCHEMES.length} schemes in each half, and a warning's band its own wash with its words at AA${bad.length ? `: ${bad.join('; ')}` : ''}`);
});

// What floats over the page stands off it (the operator, 18 Nov: a tour's
// card read as part of the page): the tour, the header's pop-outs, a row's
// menu, a help pop, the More sheet and a toast wear --float, a step brighter
// than the panel in the dark half and white in the light, on every scheme,
// with the ink and the quiet words on it at AA and a button on it still
// standing off it.
await section("what floats over the page stands off it on every scheme", async () => {
  const SCHEMES = await page.evaluate(() => THEMES.map(t => t[0]));
  const bad = [];
  for (const [t, mode] of SCHEMES.flatMap(t => [[t, ''], [t, 'light']])) {
    const r = await page.evaluate(([th, m]) => {
      const root = document.documentElement;
      root.dataset.theme = th;
      if (m) root.dataset.mode = m; else delete root.dataset.mode;
      const host = document.createElement('div');
      host.style.cssText = 'position:absolute;left:-9999px;top:0;width:400px';
      host.innerHTML = '<div class="tourcard" style="position:static"><div class="tourstep">1 of 6</div><button type="button">Skip tour</button></div>'
        + '<div class="bellpanel" style="position:static" hidden></div><div class="panelprobe" style="background:var(--panel)"></div>';
      document.body.appendChild(host);
      const card = host.querySelector('.tourcard'), cs = getComputedStyle(card);
      const c = document.createElement('canvas'); c.width = c.height = 1;
      const ctx = c.getContext('2d', { willReadFrequently: true });
      const px = v => { ctx.clearRect(0, 0, 1, 1); ctx.fillStyle = '#000'; ctx.fillRect(0, 0, 1, 1); ctx.fillStyle = v; ctx.fillRect(0, 0, 1, 1);
                        const d = ctx.getImageData(0, 0, 1, 1).data; return [d[0], d[1], d[2]]; };
      const lin = x => { x /= 255; return x <= 0.04045 ? x / 12.92 : Math.pow((x + 0.055) / 1.055, 2.4); };
      const lum = a => 0.2126 * lin(a[0]) + 0.7152 * lin(a[1]) + 0.0722 * lin(a[2]);
      const R = (a, b) => { const x = lum(px(a)), y = lum(px(b)); return (Math.max(x, y) + 0.05) / (Math.min(x, y) + 0.05); };
      const bg = cs.backgroundColor, panel = getComputedStyle(host.querySelector('.panelprobe')).backgroundColor;
      const btn = getComputedStyle(card.querySelector('button')).backgroundColor;
      const out = { lighter: lum(px(bg)) > lum(px(panel)), white: px(bg).join(',') === '255,255,255',
                    ink: +R(cs.color, bg).toFixed(2), dim: +R(getComputedStyle(card.querySelector('.tourstep')).color, bg).toFixed(2),
                    btnOff: px(btn).join(',') !== px(bg).join(',') };
      host.remove();
      return out;
    }, [t, mode]);
    const name = mode ? `${t} (light)` : t;
    if (mode ? !r.white : !r.lighter) bad.push(`${name}: the float is not ${mode ? 'white' : 'brighter than the panel'}`);
    if (!(r.ink >= 4.5) || !(r.dim >= 4.5)) bad.push(`${name}: the words on it ${r.ink}:1, the quiet ones ${r.dim}:1`);
    if (!r.btnOff) bad.push(`${name}: a button on it is its own color`);
  }
  await page.evaluate(() => { delete document.documentElement.dataset.theme; delete document.documentElement.dataset.mode; });
  ok(bad.length === 0, `what floats over the page stands off it on all ${SCHEMES.length} schemes in each half, its words at AA${bad.length ? `: ${bad.join('; ')}` : ''}`);
});
}

if (runs('b')) {
// ---- a document arrives on its own ground, on every scheme ------------------
// A document tab brought to the front fades in (docIn), and the fade was
// on the document box, which painted its own ground: the ground faded in
// with the content, over the pane's black, so every switch to a notebook
// opened on a black pane for its first frames, and nostromo's on the bare
// hull (the operator, 27 Sep). The ground is the stack's now. Measured on
// the first frame itself: whatever the switch starts is held at its start,
// the pane is photographed and its pixels read through a canvas, and that
// frame has to be the ground the settled tab stands on (its commonest
// color) with no black in it. Every kind in one scheme, the notebook in
// every scheme, the schemes read off the page's own list.
await section("a document arrives on its own ground, on every scheme", async () => {
  const frame = async () => {
    const box = await page.$eval('.pane .doc.on', e => {
      const r = e.closest('.stack').getBoundingClientRect();
      return { x: r.x, y: r.y, width: r.width, height: r.height };
    });
    const png = await page.screenshot({ clip: box });
    return page.evaluate(async b64 => {
      const img = new Image();
      img.src = 'data:image/png;base64,' + b64;
      await img.decode();
      const c = document.createElement('canvas');
      c.width = img.width; c.height = img.height;
      const g = c.getContext('2d', { willReadFrequently: true });
      g.drawImage(img, 0, 0);
      const d = g.getImageData(0, 0, c.width, c.height).data;
      let black = 0, n = 0; const count = new Map();
      // Every fourth pixel each way: the ground is most of the pane.
      for (let y = 0; y < c.height; y += 4) for (let x = 0; x < c.width; x += 4){
        const i = (y * c.width + x) * 4; n++;
        if (d[i] < 4 && d[i + 1] < 4 && d[i + 2] < 4) black++;
        const k = (d[i] << 16) | (d[i + 1] << 8) | d[i + 2];
        count.set(k, (count.get(k) || 0) + 1);
      }
      let mode = 0, most = 0;
      for (const [k, m] of count) if (m > most){ most = m; mode = k; }
      return { black: +(black / n).toFixed(3), ground: [mode >> 16, (mode >> 8) & 255, mode & 255] };
    }, png.toString('base64'));
  };
  // A wait that runs out names what was still moving, rather than a timeout alone.
  const atRest = () => page.waitForFunction(() => !document.querySelector('.pane .doc.on')?.getAnimations().length,
                                          null, { timeout: 10000 }).catch(async e => {
    const moving = await page.evaluate(() => { const d = document.querySelector('.pane .doc.on');
      return { doc: d && `${d.id || '?'}.${d.className}`, own: (d?.getAnimations() || []).map(a =>
        `${a.animationName || a.constructor.name}:${a.playState}@${Math.round(a.currentTime ?? -1)} ${a.effect?.target === d ? 'self' : a.effect?.target?.className}`) }; });
    throw new Error(`the page on show never came to rest: ${JSON.stringify(moving)}; ${e.message}`);
  });
  // The switch and the hold in one task, so no frame is painted between them.
  const switchHeld = id => page.evaluate(id => {
    focusTab(id);
    window.__held = document.getAnimations().filter(a => a.playState === 'running' || a.pending);
    window.__held.forEach(a => { a.pause(); a.currentTime = 0; });
    return window.__held.map(a => a.animationName || '').filter(Boolean);
  }, id);
  // Only what is still paused: one the page canceled meanwhile (a page's
  // docOut, whose .leaving comes off at 150ms, while a slow frame was read)
  // play() would restart detached from its rule, and it then held that page
  // at opacity 0 with an animation that never ends, so a later wait for rest
  // ran out on a different kind each run.
  const release = () => page.evaluate(() => {
    (window.__held || []).forEach(a => { if (a.playState === 'paused') a.play(); });
    window.__held = [];
  });
  const tabIdOf = kind => page.evaluate(k => tabs.find(t => t.kind === k)?.id, kind);
  // Only the two document tabs switched between: bring() makes room under
  // the page's tab ceiling by closing one, and the one it closed could be
  // the tab about to be switched to, which then never arrived.
  const onlyDocs = keep => page.evaluate(keep => {
    for (const t of [...tabs]) if (t.kind !== 'term' && !keep.includes(t.kind)) dropTab(t.id);
  }, keep);
  const arrive = async (kind, from) => {
    await onlyDocs([kind, from.split(':')[0]]);
    await bring(kind);
    await bring(from);
    await atRest();
    const id = await tabIdOf(kind);
    if (!id) return { ok: false, said: `no ${kind} tab to switch to` };
    const held = await switchHeld(id);
    // The page going out is still drawn in this frame, fading over it (a
    // crossfade, the operator, 16 Oct): set aside for the reading, so the
    // frame read is the ground the arriving page stands on. Put back by the
    // elements set aside, never by .leaving again: on a loaded box the
    // screenshot outlasts the page's 150ms timer, .leaving was off by then,
    // and the page set aside kept its hidden for good, so the crossfade
    // check read it hidden and the projects page later came to the front
    // with none of its cards visible (B219).
    await page.evaluate(() => { window.__aside = [...document.querySelectorAll('.pane .stack > .doc.leaving')];
      window.__aside.forEach(e => { e.style.visibility = 'hidden'; }); });
    const first = await frame().finally(() => page.evaluate(() => {
      (window.__aside || []).forEach(e => { e.style.visibility = ''; }); window.__aside = []; }));
    await release();
    await atRest();
    // The page that went out has left the stack and nothing is still
    // fading: the frame read next is the page at rest.
    await page.waitForFunction(() => !document.querySelector('.pane .stack > .doc.leaving'),
                               null, { timeout: 10000 }).catch(() => {});
    await motionOver();
    const settled = await frame();
    const off = first.ground.some((v, i) => Math.abs(v - settled.ground[i]) > 2);
    return { ok: first.black < 0.005 && !off && held.includes('docIn'),
             said: `first frame ${first.black * 100}% black on rgb(${first.ground}), settled on rgb(${settled.ground}); ${
                   held.includes('docIn') ? 'faded' : 'nothing faded'}` };
  };
  for (const kind of tabKinds){
    if (!DRIVERS[kind]) continue;
    // A dock tab (the chat, R250 step 2) is not a page brought to the front
    // over another in the same pane: it is the dock's body, which slides up
    // with the dock, and pressing it while it is in front puts the dock down.
    if (await page.evaluate(k => slotFor({kind: k}) === 1, kind)) continue;
    const r = await arrive(kind, kind === 'projects' ? 'notebook:roadmap' : 'projects');
    ok(r.ok, `[${kind}] brought to the front, its first frame is its own ground and only its content fades in (${r.said})`);
  }
  // ...and the page it replaces fades out over the same frames: a crossfade,
  // not a blank between the two (the operator, 16 Oct).
  {
    await onlyDocs(['projects', 'notebook']);
    await bring('notebook:roadmap');
    await bring('projects');
    await atRest();
    // The page going out read in the same task as the switch and the hold:
    // read after it, the page's own 150ms timer had taken .leaving off on a
    // loaded box and the copy read hidden (B795).
    const { held, out } = await page.evaluate(id => {
      focusTab(id);
      window.__held = document.getAnimations().filter(a => a.playState === 'running' || a.pending);
      window.__held.forEach(a => { a.pause(); a.currentTime = 0; });
      // ...in the pane the switch is in: under load the dock's pane can still
      // hold a page of its own leaving, its timer late, and out of sight it
      // read hidden.
      const l = document.querySelector('#pane0 .stack > .doc.leaving');
      return { held: window.__held.map(a => a.animationName || '').filter(Boolean),
               out: l ? getComputedStyle(l).visibility : 'none' };
    }, await tabIdOf('notebook'));
    await release();
    await atRest();
    ok(held.includes('docIn') && held.includes('docOut') && out === 'visible',
       `a switch between two pages is a crossfade, the one going out fading as the one coming in does (${held.join(', ') || 'nothing'}; out ${out})`);
  }
  // The line under a strip slides on transform alone, so the compositor runs
  // it while the press draws the view (the operator, 18 Oct: it stuttered).
  {
    await onlyDocs(['notebook']);
    await bring('notebook:roadmap');
    await atRest();
    const props = await page.evaluate(async () => {
      document.querySelector('.pane .doc.on .nbtabs [data-v="bugs"]').click();
      for (let i = 0; i < 40; i++){
        const a = document.querySelector('.pane .doc.on .nbtabs .nbsub > .slmark')?.getAnimations()[0];
        if (a) return [...new Set(a.effect.getKeyframes().flatMap(k => Object.keys(k)))].filter(k => !['offset', 'easing', 'composite', 'computedOffset'].includes(k));
        await new Promise(r => setTimeout(r, 5));
      }
      return null;
    });
    ok(props && props.join() === 'transform', `a strip's line slides on transform alone (${props ? props.join(', ') : 'no slide'})`);
  }
  // ...and what a press redraws inside a page fades through the same way
  // (the operator, 18 Oct): a settings section, a role and a notebook view,
  // each leaving a still copy fading out on docOut's time while the new part
  // fades in on docIn's, and the copy gone soon after.
  for (const [label, kind, ready, press, ghost, fresh] of [
    ['a settings section picked', 'settings', '.pane .doc.on .ssplit > .snav [data-spick]:not(.on)',
     '.pane .doc.on .ssplit > .snav [data-spick]:not(.on)', '.pane .doc.on .ssplit > .fghost', '.pane .doc.on .ssplit > .scur:not(.fghost)'],
    ['a role picked', 'roles', '.pane .doc.on .rsplit [data-rpick]:not(.on)',
     '.pane .doc.on .rsplit [data-rpick]:not(.on)', '.pane .doc.on .rsplit > .fghost', '.pane .doc.on .rsplit > .rdetail:not(.fghost)'],
    ['a notebook view switched', 'notebook:roadmap', '.pane .doc.on .nbtabs [data-v="bugs"]',
     '.pane .doc.on .nbtabs [data-v="bugs"]', '.pane .doc.on .nbview.fghost', '.pane .doc.on .nbview[data-view="bugs"]:not(.fghost)'],
  ]){
    await onlyDocs([kind.split(':')[0]]);
    await bring(kind);
    await page.waitForSelector(ready, { timeout: 15000 });
    await atRest();
    const r = await page.evaluate(async ([press, ghost, fresh]) => {
      document.querySelector(press).click();
      // A view's switch waits on its leave check (leaveNbView) first.
      for (let i = 0; i < 40 && !document.querySelector(ghost); i++) await new Promise(r => setTimeout(r, 5));
      const g = document.querySelector(ghost), n = document.querySelector(fresh);
      const t = a => a.effect?.getTiming?.() || {};
      return { out: (g?.getAnimations() || []).map(a => t(a).duration)[0] ?? 0, inert: !!g?.inert, ids: !!g?.querySelector('[id]'),
               in: (n?.getAnimations() || []).filter(a => a.id === 'fadein').map(a => `${t(a).duration}@${t(a).delay}`)[0] || '' };
    }, [press, ghost, fresh]);
    await faded(page).catch(() => {});
    const left = await page.$$eval(ghost, gs => gs.length);
    // A pick opens its detail, which on a phone stands over the list: put
    // back, so the phone's pass later finds each list as it was.
    await page.evaluate(() => { for (const k in SPLIT) SPLIT[k].open = false; rolesPhoneOpen = false; });
    ok(r.out === 90 && r.in === '220@60' && r.inert && !r.ids && left === 0,
       `${label} fades through as a rail page does: the old a still copy fading out, the new fading in, the copy gone after (out ${r.out}ms, in ${r.in || 'none'}, inert ${r.inert}, ids ${r.ids}, left ${left})`);
  }
  const schemes = await page.evaluate(() => THEMES.map(t => t[0]));
  const bad = [];
  for (const t of schemes){
    await page.evaluate(th => { document.documentElement.dataset.theme = th; }, t);
    await motionOver();
    const r = await arrive('notebook', 'projects');
    if (!r.ok) bad.push(`${t}: ${r.said}`);
  }
  await page.evaluate(() => { delete document.documentElement.dataset.theme; });
  await motionOver();
  ok(schemes.length > 1 && bad.length === 0,
     `a notebook brought to the front opens on its scheme's ground in all ${schemes.length} schemes, never black${
       bad.length ? `: ${bad.join('; ')}` : ''}`);
});

// Every page's bar is one control high, whatever it holds, and a picker's
// word sits on its line, to its left (the operator, 19 Oct: a picker's word
// above it, a count alone and a count beside a button each made a bar of
// its own height, and the content under each started somewhere else).
await section("Every page's bar is one control high, whatever it holds, and a picker's", async () => {
  const bars = {};
  for (const kind of kinds){
    if (!DRIVERS[kind]) continue;
    await bring(kind);
    await page.waitForSelector(DRIVERS[kind].readyWhen, { timeout: 20000 });
    await arrived();
    const b = await page.evaluate(() => {
      const bar = document.querySelector('.pane .doc.on .doctab > .docbarrow:not([hidden])');
      if (!bar || !bar.offsetHeight) return null;
      const w = bar.querySelector(':scope > label.pick > .pickw'), sel = bar.querySelector(':scope > label.pick > select');
      const mid = e => { const r = e.getBoundingClientRect(); return r.top + r.height / 2; };
      return { h: Math.round(bar.getBoundingClientRect().height), inline: !w || !sel || Math.abs(mid(w) - mid(sel)) <= 2 };
    });
    if (b) bars[kind] = b;
  }
  const hs = [...new Set(Object.values(bars).map(b => b.h))];
  ok(hs.length === 1, `every page's bar is one height, whatever it holds (${JSON.stringify(Object.fromEntries(Object.entries(bars).map(([k, b]) => [k, b.h])))})`);
  const above = Object.entries(bars).filter(([, b]) => !b.inline).map(([k]) => k);
  ok(above.length === 0, `...and a picker's word sits on its line, to its left${above.length ? `; above it: ${above.join(', ')}` : ''}`);
});

// The same page, held to the same rules at phone width: nothing may scroll
// the page sideways, and every text control is 16px so iOS does not zoom a
// layout that cannot zoom back.
// A modal leaves the way it arrived. The arrival is the stylesheet's; the
// leaving is one observer on the hidden attribute, so this is what proves
// every dialog on the page, including one added later, goes out with it.
await section("The same page, held to the same rules at phone width", async () => {
  await page.click('#bAbout');
  await page.waitForSelector('#aboutModal:not([hidden])');
  const left = await animatedDuring(page, async () => {
    await page.click('#aboutClose');
    await page.waitForSelector('#aboutModal', { state: 'hidden' });
  });
  ok(left.some(k => /aboutModal/.test(k)),
     `a modal leaves with a tween rather than vanishing (${left.join(', ') || 'nothing animated'})`);
});
await page.setViewportSize({ width: 393, height: 851 });
// A card turns over to its controls on a tween (R138): Edit, and the back
// is on the screen whole, at a phone's width as at a desk's.
await section("A card turns over to its controls on a tween", async () => {
  // The page on show's: the first card anywhere could be a page out of
  // sight's, never visible, and the wait ran out on it in a whole run.
  await page.evaluate(() => openProjectsTab());
  await page.waitForSelector('.doc.on .pgrid .pcard .pcfront [data-pedit]', { timeout: 10000 });
  const card = await page.$eval('.doc.on .pgrid .pcard', c => c.dataset.pkey);
  const at = `.doc.on .pgrid .pcard[data-pkey="${card}"]`;
  await page.click(`${at} .pcfront [data-pedit]`);
  const mid = await page.$eval(`${at} .pcback`, e => getComputedStyle(e).transform);
  // On its back and the turn over: no transition that ends still runs in it.
  await page.waitForFunction(at => { const c = document.querySelector(at);
    return !!c && c.classList.contains('flipped') && !c.getAnimations({ subtree: true }).some(a => a.playState === 'running'
      && Number.isFinite(a.effect?.getComputedTiming().endTime)); }, at, { timeout: 10000 }).catch(() => {});
  const back = await page.$eval(at, c => { const r = c.querySelector('.pcback').getBoundingClientRect();
    return { flipped: c.classList.contains('flipped'), settled: getComputedStyle(c.querySelector('.pcback')).transform,
             on: r.left >= 0 && r.right <= innerWidth }; });
  ok(back.flipped && back.on && mid !== back.settled && /^(none|matrix\(1, 0, 0, 1, 0, 0\))$/.test(back.settled),
     `a card turns over on a tween on a phone, its back whole on the screen (${JSON.stringify({ mid, ...back })})`);
  await page.click(`${at} .pcback [data-pedit]`);
});
// The card is on its front again, its turn back over.
await page.waitForFunction(() => !document.querySelector('.doc.on .pgrid .pcard.flipped'), null, { timeout: 10000 }).catch(() => {});
await motionOver();
// The same width rule at phone width, on every tab: the cap is min(--ctl-w,
// 88%), and 88% is what bites here.
//
// A phone starts every fold shut, and a control inside a shut fold has no
// line to be measured on. Opened the way a person's press leaves them, which
// is recorded as well as open, so a redraw between here and the measuring
// does not shut them again. (These used to arrive open by accident: the page
// recorded the desktop's default as a choice, and carried it down here.)
const unfold = () => page.evaluate(() => {
  document.querySelectorAll('.doc.on details[data-sect]').forEach(d => {
    sectOpen[d.dataset.sect] = true; d.open = true; });
});
for (const kind of kinds){
  if (!DRIVERS[kind]) continue;
  await bring(kind);
  await page.waitForSelector(DRIVERS[kind].readyWhen, { timeout: 20000 });
  await unfold();
  const S = await spanning();
  ok(!S.err && S.wide.length === 0,
     `[${kind}] no control or row of controls spans the tab at phone width${
       S.err ? ` (${S.err})` : S.wide.length ? `: ${S.wide.join(', ')}` : ''}`);
  await arrived();
  const L = await lineup();
  ok(!L.err && L.off.length === 0,
     `[${kind}] every control on a line ends at the same height at phone width${
       L.err ? ` (${L.err})` : L.off.length ? `: ${L.off.join('; ')}` : ''}`);
  ok(!L.err && L.sizes.length === 0,
     `[${kind}] every control on a line is one height at phone width${
       L.err ? ` (${L.err})` : L.sizes.length ? `: ${L.sizes.join('; ')}` : ''}`);
  // A field too narrow for its placeholder's words shows short ones that
  // fit (the operator, 22 Nov: a field's text has a shorter version where
  // the field is not long enough for it), never the first words of a long
  // one cut off mid-word.
  const phCut = await page.evaluate(() => {
    const c = document.createElement('canvas').getContext('2d'), out = [];
    for (const el of document.querySelectorAll('.doc.on input[placeholder], header input[placeholder]')){
      if (!el.checkVisibility() || el.value || !el.placeholder) continue;
      const cs = getComputedStyle(el); c.font = cs.font;
      const room = el.clientWidth - parseFloat(cs.paddingLeft) - parseFloat(cs.paddingRight);
      if (c.measureText(el.placeholder).width > room + 1) out.push(`${el.id || el.getAttribute('aria-label') || el.className} "${el.placeholder}"`);
    }
    return out;
  });
  ok(phCut.length === 0,
     `[${kind}] no field's placeholder is cut off at phone width${phCut.length ? `: ${phCut.join(', ')}` : ''}`);
  // An action bar on a phone shows at most five text buttons; what a row
  // can do beyond its primary verbs is behind More (R210: seven wrapped to
  // two lines, Remove alone on the second).
  const crowded = await page.$$eval('.doc.on .actbar', bars => bars.map(b => {
    const vis = e => e.offsetHeight > 0 && e.textContent.trim();
    const n = [...b.children].filter(c => c.tagName === 'BUTTON' && vis(c)).length
      + [...b.querySelectorAll(':scope > .more > button')].filter(vis).length;
    return n > 5 ? `${b.className.split(/\s+/).pop()}(${n})` : '';
  }).filter(Boolean));
  ok(crowded.length === 0,
     `[${kind}] an action bar shows at most five buttons at phone width${crowded.length ? `: ${crowded.join(', ')}` : ''}`);
  // A tile's number is read whole at phone width (B150): three to a row,
  // "11.1 TB" was cut to "11.1…" in a third of the screen.
  const cut = await page.$$eval('.doc.on .tile .tv', vs => vs.filter(v => v.offsetParent && v.scrollWidth > v.clientWidth + 1)
    .map(v => v.textContent.trim()));
  ok(cut.length === 0, `[${kind}] every tile's number is whole at phone width${cut.length ? `; cut: ${cut.join(', ')}` : ''}`);
  // No tiles but Home's, and no facts grid open in a page's head unasked
  // (R274, the operator 23 Nov): what a page is about now is its status line.
  const busy = await page.$$eval('.doc.on', ds => ds.flatMap(d => [
    ...[...d.querySelectorAll('.tiles:not(.hometiles)')].filter(e => e.checkVisibility()).map(() => 'tiles'),
    ...[...d.querySelectorAll('.pghead:not(.about) > dl.facts, .pghead:not(.about) > .pghfacts, .pgdet')].filter(e => e.checkVisibility()).map(() => 'a facts grid or a Details fold in the head')]));
  ok(busy.length === 0, `[${kind}] a page's top is its status line, its other facts beside what they describe${busy.length ? `: ${busy.join(', ')}` : ''}`);
  const room = await headRoom();
  ok(room.length === 0,
     `[${kind}] every section's first line keeps room under its head at phone width${room.length ? `; touching: ${room.join(', ')}` : ''}`);
  const sidePh = await sideRoom();
  ok(sidePh.length === 0, `[${kind}] nothing in a section or a placeholder sits on its side wall at phone width${sidePh.length ? `; on it: ${sidePh.slice(0, 8).join(', ')}` : ''}`);
  const W = await unwrapped();
  ok(!W.err && W.tall.length === 0,
     `[${kind}] every select is one line high at phone width${
       W.err ? ` (${W.err})` : W.tall.length ? `; wrapped: ${W.tall.join(', ')}` : ''}`);
  // A sentence is a proseline, not an input. An <input> shows about thirty
  // characters at this width, so a 300-character bug title was a field you
  // could not read what you were editing in. The threshold is the length: a
  // name is 100, a branch is 120, and anything longer than that is prose.
  const P = await page.evaluate(() => {
    const host = document.querySelector('.doc.on');
    const box = host?.querySelector(':scope > .doctab, :scope > .nb, :scope > div');
    if (!box) return { err: 'no document box found' };
    const bad = [...box.querySelectorAll('input[maxlength]')]
      .filter(e => Number(e.getAttribute('maxlength')) > 120)
      .map(e => `${e.id || e.className.split(' ')[0] || 'input'}=${e.getAttribute('maxlength')}`);
    const grew = [...box.querySelectorAll('textarea.proseline')]
      .filter(e => e.offsetHeight > 0 && e.scrollHeight > e.clientHeight + 2)
      .map(e => e.id || e.className.split(' ')[0] || 'proseline');
    return { bad, grew };
  });
  ok(!P.err && P.bad.length === 0,
     `[${kind}] a sentence is a proseline, not an input${
       P.err ? ` (${P.err})` : P.bad.length ? `: ${P.bad.join(', ')}` : ''}`);
  ok(!P.err && P.grew.length === 0,
     `[${kind}] every proseline shows all of itself rather than scrolling inside${
       P.grew.length ? `: ${P.grew.join(', ')}` : ''}`);
}
}
if (runs('c')) {
// Part c is measured at phone width, which part b's walk sets on its way
// (393 by 851); run on its own it starts there itself.
await page.setViewportSize({ width: 393, height: 851 });
// ---- a list of choices is alphabetical -----------------------------------
// Each of these was in the order somebody wrote it in. The exceptions are
// named rather than discovered: Default leads the schemes, and the catch-all
// trails the git hosts.
await section("a list of choices is alphabetical", async () => {
  const lists = await page.evaluate(async () => {
    const out = {};
    out.themes = THEMES.map(t => t[1]);
    // Both catalogs ride along with something else rather than costing a
    // fetch of their own: the forge list with the deploy keys the same dialog
    // wants, the hypervisors with the template the VM dialog renders.
    const f = await (await fetch('/api/pubkeys')).json().catch(() => null);
    out.forges = (f?.forges || []).map(x => x.name);
    const v = await (await fetch('/api/v1/nodes', { method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ action: 'vm-xml' }) })).json().catch(() => null);
    out.hypervisors = (v?.catalog || []).map(x => x.label);
    return out;
  });
  const sorted = (xs, { head = 0, tail = 0 } = {}) => {
    const mid = xs.slice(head, xs.length - tail);
    return mid.join('|') === [...mid].sort((a, b) =>
      a.toLowerCase().localeCompare(b.toLowerCase())).join('|');
  };
  ok(lists.themes.length > 3 && lists.themes[0] === 'Default'
     && sorted(lists.themes, { head: 1 }),
     `the color schemes are alphabetical after Default (${lists.themes.join(', ')})`);
  if (lists.forges.length)
    ok(sorted(lists.forges, { tail: 1 })
       && lists.forges[lists.forges.length - 1] === 'Another git host',
       `the git hosts are alphabetical, with the catch-all last (${lists.forges.join(', ')})`);
  if (lists.hypervisors.length)
    ok(sorted(lists.hypervisors),
       `the hypervisors are alphabetical (${lists.hypervisors.join(', ')})`);
});

// The Tests view needs rows to be measured on, and one of them a continuation
// (a "..." name whose "follows:" line is drawn under it), because that line
// is exactly what scrolled the tab sideways once (a 100% flex basis plus a
// margin, unable to shrink). A registry the fixture does not carry, so a
// two-line run is ingested here; the file reset takes it away again.
await section("The Tests view needs rows to be measured on, and one of them a continuation", async () => {
  const { writeFileSync } = await import('node:fs');
  const { execFileSync } = await import('node:child_process');
  const { fileURLToPath } = await import('node:url');
  const { dirname, join } = await import('node:path');
  const HERE = dirname(fileURLToPath(import.meta.url));
  writeFileSync(`${DIR}/ws/alpha/.bb-test-run.log`,
    '[dashboard-test] == shape.mjs ==\nPASS  [+0.1s] a row long enough to wrap on a phone, which most of them are\n'
    + 'PASS  [+0.1s] ...and a continuation of it, whose follows line is drawn under the name\n'
    + '2 passed, 0 failed in 0.2s\n');
  execFileSync(join(HERE, '..', '..', 'aerie'), ['tests', 'ingest', '.bb-test-run.log'],
    { cwd: `${DIR}/ws/alpha`, env: { ...process.env, BUILDERBOT_ROLE: 'controller', BB_TOKEN: '',
      DASHBOARD_STATE: `${DIR}/state`, WORKSPACE: `${DIR}/ws`, BB_PROJECT: 'alpha' } });
});
// Measured on the document AND on the document box, because the box scrolls
// on its own: the page reported no overflow while the Tests tab scrolled
// sideways inside its pane. The widest offender is named, so the failure
// says what to fix rather than that something is wide. The tab strip is
// the one thing allowed past the edge: it scrolls by design.
const sideways = () => page.evaluate(() => {
  // Every section open for the measurement: on a phone one stands open at a
  // time (R184), and what is folded away is not measured, so the folds are
  // opened here and the one-at-a-time rule is held by its own check below.
  document.querySelectorAll('details.sect').forEach(d => { d.open = true; });
  const host = document.querySelector('.doc.on');
  const box = host?.querySelector(':scope > .doctab, :scope > .nb, :scope > div') || host;
  const controls = [...(host?.querySelectorAll('input, select, textarea') || [])]
    .filter(e => e.offsetHeight > 0)
    .filter(e => !['checkbox', 'radio'].includes(e.type));
  const edge = (box?.getBoundingClientRect().right || document.documentElement.clientWidth) + 1;
  let widest = null;
  // Inside a box that scrolls sideways by design (a diff's pre), what is
  // wide is that box's to scroll, never the page's: all sections stand open
  // on a phone since 8 Oct, so a diff is measured there now. A box that
  // clips with an ellipsis (a closed toolchain row's one line, R218 step
  // 22) hides what is past its edge, and nothing scrolls to it either.
  const scrolls = e => {
    for (let a = e.parentElement; a && a !== box; a = a.parentElement)
      if ((/(auto|scroll)/.test(getComputedStyle(a).overflowX)
           || getComputedStyle(a).textOverflow === 'ellipsis' && /(hidden|clip)/.test(getComputedStyle(a).overflowX))
          && a.getBoundingClientRect().right <= edge) return true;
    return false;
  };
  for (const e of box?.querySelectorAll('*') || []){
    if (e.closest('.nbtabs')) continue;
    if (scrolls(e)) continue;
    const r = e.getBoundingClientRect();
    if (r.width && r.right > edge && (!widest || r.right > widest.right)){
      // Named with its text and its parents, so the failure says where to
      // look rather than "a button": a bare `button.` cost a second run.
      // ...and each parent's width, because the element named is only where
      // the overflow ENDS: a button at the right of a row is past the edge
      // because something else made the row wide.
      const chain = [];
      let row = null;
      for (let a = e.parentElement, n = 0; a && n < 5 && !a.classList.contains('doc'); a = a.parentElement, n++){
        chain.push(`${a.tagName.toLowerCase()}${a.id ? '#' + a.id : ''}.${String(a.className || '').split(/\s+/)[0]}=${Math.round(a.getBoundingClientRect().width)}`);
        if (a.classList.contains('row')) row = a;
      }
      widest = { right: Math.round(r.right),
                 what: `${e.tagName.toLowerCase()}${e.id ? '#' + e.id : ''}.${String(e.className || '').split(/\s+/)[0]}`
                   + ` "${(e.textContent || '').trim().slice(0, 20)}" in ${chain.join(' < ')}`
                   + (row ? `; row: ${row.outerHTML.replace(/\s+/g, ' ').slice(0, 700)}` : '') };
    }
  }
  return {
    overflow: Math.max(document.documentElement.scrollWidth - document.documentElement.clientWidth,
                       box ? box.scrollWidth - box.clientWidth : 0),
    widest,
    // Every control on a phone is the field size (--f-field, 11px mono): a 16px mono
    // field beside an 11px label is the loudest thing on the tab, and the
    // operator asked for smaller text in every box (25 Sep). The 16px that
    // stops iOS Safari zooming the page into a typed field is iOS's alone,
    // under @supports (-webkit-touch-callout: none), a property only it
    // has, so this browser never sees it and this measures the rule for
    // everything else: nothing inflated, pickers included.
    loud: controls.filter(e => parseFloat(getComputedStyle(e).fontSize) >= 16)
      .map(e => e.id || e.className || e.tagName),
  };
});
// A page of sections on a phone opens one at a time, its head the way back
// (the operator, 19 Oct: a Back button of its own was a row spent, and sat
// on the head): the head wears the chevron, and a press on it shows the
// list again.
for (const [kind, root, pick, head, open] of [
  ['settings', '.ssplit', ':scope > .snav [data-spick]', ':scope > .scur > summary', 'sopen'],
  ['profile', '.ssplit', ':scope > .snav [data-spick]', ':scope > .scur > summary', 'sopen'],
  ['users', '.rsplit', ':scope > .rlist [data-upick]', ':scope > .rdetail > .rhead', 'open'],
  ['roles', '.rsplit', ':scope > .rlist [data-rpick]', ':scope > .rdetail > .rhead', 'open'],
]){
  await bring(kind);
  await page.waitForSelector(`.pane .doc.on ${root} ${pick.replace(':scope > ', '> ')}`, { timeout: 15000 });
  await page.waitForFunction(() => !document.querySelector('.pane .doc.on')?.getAnimations().length, null, { timeout: 10000 });
  const r = await page.evaluate(async ([root, pick, head, open]) => {
    const box = document.querySelector(`.pane .doc.on ${root}`);
    box.querySelector(pick).click();
    await new Promise(r => setTimeout(r, 400));
    const box2 = document.querySelector(`.pane .doc.on ${root}`);
    const s = box2.querySelector(head), c = s?.querySelector(':scope > .shback'), t = c?.nextElementSibling;
    const chevron = !!c && c.offsetWidth > 0 && !!t && c.getBoundingClientRect().right <= t.getBoundingClientRect().left;
    const opened = box2.classList.contains(open);
    s?.click();
    await new Promise(r => setTimeout(r, 400));
    const box3 = document.querySelector(`.pane .doc.on ${root}`);
    return { opened, chevron, back: !box3.classList.contains(open) };
  }, [root, pick, head, open]);
  ok(r.opened && r.chevron && r.back, `[${kind}] what is opened from a list on a phone is headed by the way back, a chevron before its name, and a press on its head shows the list (${JSON.stringify(r)})`);
}
for (const kind of kinds){
  if (!DRIVERS[kind]) continue;
  await bring(kind);
  // A tab that was open already is only focused by bring: drawn, and at rest.
  await page.waitForSelector(DRIVERS[kind].readyWhen, { timeout: 20000 }).catch(() => {});
  await arrived();
  // The notebook is six views behind one tab, and each has its own layout;
  // the Tests view is the one that scrolled sideways while the Roadmap, the
  // one this check used to look at, did not.
  // (Every view is a kind of its own now, so this loop meets each once.)
  const views = [''];
  for (const v of views){
    if (v){
      await page.evaluate(w => getNotebook('alpha').view(w), v);
      await page.waitForFunction(w => document.querySelector(`.nb .nbview[data-view="${w}"]`)?.checkVisibility(),
                                 v, { timeout: 20000 });
      await arrived();
    }
    const m = await sideways();
    const tag = v ? `${kind}/${v}` : kind;
    ok(m.overflow <= 0 && !m.widest, `[${tag}] no sideways scroll at phone width (${
      m.overflow}px over${m.widest ? `; ${m.widest.what} reaches ${m.widest.right}px` : ''})`);
    ok(m.loud.length === 0, `[${tag}] no control on a phone is inflated past the field size${
      m.loud.length ? `; inflated: ${m.loud.join(', ')}` : ''}`);
    // One section open at a time on a phone (R184, the operator, 11 Oct):
    // after a draw one stands open, and opening another shuts it. Measured
    // on a surface with two or more sections in one group; the measurement
    // above opened them all, so the draw's state is put back first.
    const sects = await page.evaluate(() => {
      // The sections on show: the notebook keeps every view's in the DOM,
      // and only the view that is on has visible ones.
      const host = document.querySelector('.doc.on');
      const all = [...(host?.querySelectorAll('details.sect') || [])].filter(d => d.dataset.sect && d.checkVisibility());
      const g = all[0] ? sectGroup(all[0]) : null;
      const mine = g ? sectsOf(g) : [];
      if (mine.length >= 2){ oneOpen(g); }
      return { n: mine.length, open: mine.filter(d => d.open).length,
               keys: mine.map(d => d.dataset.sect), openKeys: mine.filter(d => d.open).map(d => d.dataset.sect) };
    });
    // Every section on show is wired (wireSections), with data or without:
    // one that is not snaps open beside the rest on a phone, and the check
    // below needs two sections, which a page with nothing to show does not
    // draw (B171: Storage and nginx, both never wired).
    const loose = await page.evaluate(() => [...(document.querySelector('.doc.on')?.querySelectorAll('details.sect > summary') || [])]
      .filter(s => s.checkVisibility() && !s.onclick).map(s => s.parentElement.dataset.sect || '(no key)'));
    ok(loose.length === 0, `[${tag}] every section is wired to fold as the rest do${loose.length ? `; not: ${loose.join(', ')}` : ''}`);
    if (sects.n >= 2){
      ok(sects.open === 1, `[${tag}] a phone shows one section open after a draw (${sects.open} of ${sects.n})`);
      const other = sects.keys.find(k => !sects.openKeys.includes(k));
      // Pressed through the summary's own handler (wireSections' onclick), as
      // a tap is: a pointer click waits for the summary to be in view, and a
      // view that scrolls inside its pane kept one of them out of it.
      await page.evaluate(k => document.querySelector(`.doc.on details.sect[data-sect="${k}"] > summary`)?.click(), other);
      // The one pressed is the one open, the other's slide shut over: a
      // section sliding shut reads open until its slide ends.
      await page.waitForFunction(k => {
        const host = document.querySelector('.doc.on');
        const all = [...(host?.querySelectorAll('details.sect') || [])].filter(d => d.dataset.sect && d.checkVisibility());
        if (!all[0]) return false;
        const mine = sectsOf(sectGroup(all[0])), open = mine.filter(d => d.open);
        return open.length === 1 && open[0].dataset.sect === k
          && !mine.some(d => d.getAnimations().some(a => a.id === 'fold' && a.playState === 'running'));
      }, other, { timeout: 10000 }).catch(() => {});
      const after = await page.evaluate(k => {
        const host = document.querySelector('.doc.on');
        const all = [...(host?.querySelectorAll('details.sect') || [])].filter(d => d.dataset.sect && d.checkVisibility());
        const g = sectGroup(all[0]);
        const mine = sectsOf(g);
        return { open: mine.filter(d => d.open).map(d => d.dataset.sect), want: k };
      }, other);
      ok(after.open.length === 1 && after.open[0] === other,
         `[${tag}] ...and opening another shuts it: open ${JSON.stringify(after.open)}, pressed ${other}`);
    }
  }
}
}

if (runs('c')) {
// ---- the document and the framework are one thing ---------------------------
// docs/design-language.md is what a session reads; this suite is what holds
// the page. The two drift apart the day a helper is renamed and the document
// still names the old one, so every name the document uses is checked to be
// real on the page, and every helper the framework exposes is checked to be
// in the document: a rename without a rewrite fails here by name.
await section("the document and the framework are one thing", async () => {
  const { readFileSync } = await import('node:fs');
  const { fileURLToPath } = await import('node:url');
  const { dirname, join } = await import('node:path');
  const doc = readFileSync(join(dirname(fileURLToPath(import.meta.url)), '..', '..', '..', 'docs', 'design-language.md'), 'utf8');
  const helpers = ['docSurface', 'docSection', 'renderGuarded', 'busy'];
  const missing = helpers.filter(h => !doc.includes(h));
  ok(missing.length === 0,
     `the design language names every helper the framework exposes${missing.length ? `; not: ${missing.join(', ')}` : ''}`);
  const named = [...doc.matchAll(/`(docSurface|docSection|renderGuarded|busy|wireSections)\b/g)].map(m => m[1]);
  const unreal = await page.evaluate(ns => ns.filter(n => typeof window[n] !== 'function'), [...new Set(named)]);
  ok(unreal.length === 0,
     `...and every helper the document names is a real function on the page${unreal.length ? `; not: ${unreal.join(', ')}` : ''}`);
  // By name, with or without the dot: the document writes a class as it
  // appears in markup as often as as a selector.
  const classes = ['actbar', 'field', 'histbar', 'danger', 'state', 'foot', 'modal', 'ndcap', 'setrow', 'prose'];
  const undocumented = classes.filter(c => !new RegExp(`\\b${c}\\b`).test(doc));
  ok(undocumented.length === 0,
     `...and names the classes the page is measured on${undocumented.length ? `; not: ${undocumented.join(', ')}` : ''}`);
});
}

if (runs('c')) {
// ---- a quiet page is quiet, and a tab opens once (R75 step 4) -------------
// What the page asks the server for is measured, not assumed: the phone's
// device probe filled the Jobs tab for weeks, and the Docker tab asked for
// its listing three times per press, and nothing counted either. With
// nothing happening the page issues its two polls and nothing else, and
// opening a tab asks each endpoint at most once, whichever kind it is. The
// polls, the layout save an open makes, and the node list a picker fills
// are the allowed noise.
await section("a quiet page is quiet, and a tab opens once", async () => {
  const POLLS = new Set(['/api/status', '/api/revs', '/api/presence', '/api/layout', '/api/v1/nodes', '/api/live']);
  await page.evaluate(() => { for (const t of [...tabs]) if (t.kind !== 'term') dropTab(t.id); });
  // With every page put away the page lands on Home, the landing page, whose
  // one read on open is an open's and not a poll: counted from after it.
  await page.waitForFunction(() => tabOf(panes[0])?.kind !== 'home' || (homeData !== null && !readBusy('home')), null, { timeout: 20000 });
  // Which revisions moved over a window, read off the page's own tokens: a
  // re-read a moved token asked for is the page doing its job, not noise
  // (B757: an earlier kind's job finishing inside the window re-read Home,
  // the Emulator page and the Docker page, and failed a run in three).
  // Counted as the page counts them: a token only one page draws (a node's
  // heartbeat, every poll) only while that page is on show.
  // A token that appeared in the window counts as the page counts it
  // (page-poll.js: after the first poll an appearing token is news and its
  // watches fire): Home re-read on the jobs token appearing with a fresh
  // fixture's first job, and failed a run with nothing moved said.
  const MOVED = () => page.evaluate(() => Object.keys(revs).filter(k => k !== 'boot' && window.__r0 && window.__r0[k] !== revs[k]
    && (!REVS_PAGE_ONLY[k] || REVS_PAGE_ONLY[k]())));
  const MARK = () => page.evaluate(() => { window.__r0 = { ...revs }; });
  // Home's light read is a request of its own: opening Home asks the light
  // one, to draw at once, and the whole one behind it (R218 step 5), and
  // counted as one endpoint the pair read as Home asking twice whenever its
  // data had been let go before the open (B788).
  await page.evaluate(() => { window.__f = {}; const f = window.fetch;
    window.fetch = (...a) => { const s = String(a[0]), u = /^\/api\/home\?light=1/.test(s) ? '/api/home?light' : s.split('?')[0];
      window.__f[u] = (window.__f[u] || 0) + 1; return f(...a); }; });
  await MARK();
  await quietFor(8000);
  const idle = await page.evaluate(() => window.__f);
  const idleMoved = await MOVED();
  // Home re-reads on the jobs token and on nothing else.
  const noise = Object.keys(idle).filter(u => !POLLS.has(u) && !(/^\/api\/home/.test(u) && idleMoved.includes('jobs')));
  ok(noise.length === 0, `an idle page asks only its polls (${noise.length ? 'also ' + noise.join(', ') : Object.keys(idle).join(', ')}${idleMoved.length ? '; moved: ' + idleMoved.join(', ') : ''})`);
  // ...and only so often (R218 step 10, against step 1's baseline of the
  // revisions poll x20, the status poll x5 and the node list x4 in thirty
  // seconds on every page): a node's heartbeat moves only its numbers' own
  // token, which only the Nodes page reads, so Home reads neither the node
  // list nor the status poll for it while the stub beats every five seconds.
  // Measured on a page of its own, landed on Home and left alone: this one
  // has walked every kind, and the jobs those started move the node
  // registry's token as they finish, which is news.
  const quiet = await newPage(browser, { viewport: { width: 1280, height: 900 } });
  await quiet.goto(URL); await ready(quiet);
  await quiet.evaluate(() => railGo('home'));
  // Left alone, and Home's own reads in by then, before the count starts.
  await quietFor(5000);
  await quiet.waitForFunction(() => tabOf(panes[0])?.kind !== 'home' || (homeData !== null && !readBusy('home')),
                              null, { timeout: 20000 }).catch(() => {});
  await quiet.evaluate(() => { window.__f = {}; const f = window.fetch;
    window.fetch = (...a) => { const u = String(a[0]).split('?')[0]; window.__f[u] = (window.__f[u] || 0) + 1; return f(...a); }; });
  await quietFor(8000);
  const calm = await quiet.evaluate(() => window.__f);
  await quiet.close();
  ok(!calm['/api/v1/nodes'] && !calm['/api/presence'] && (calm['/api/status'] || 0) <= 1 && (calm['/api/revs'] || 0) <= 6,
     `...and only so often: no node list or presence off their pages, the status poll at most once and the revisions poll at most six times in eight seconds (${JSON.stringify(calm)})`);
  for (const kind of Object.keys(DRIVERS)){
    if (kind.startsWith('notebook:')) continue;
    // The last kind's close lands the page on Home, which is an open of its
    // own and reads Home: let that land before this kind's count starts, or
    // Home's own count holds the landing's reads as well as its open's.
    await settled(page, { quiet: 300, cap: 5000 });
    await page.evaluate(() => { window.__f = {}; });
    await MARK();
    // Attached, not visible: the count is about requests, and a tab that
    // opens behind a switch on a narrow page has still asked for its data.
    // The driver's own way in first; a tab whose button is ghosted right now
    // (Analysis with nothing to analyze) is opened the way a restored layout
    // opens it, since the count is about the open path and not the button.
    let came = true;
    try {
      await DRIVERS[kind].open();
      if (!await page.evaluate(k => tabs.some(t => t.kind === k), kind))
        await page.evaluate(k => openTab({ kind: k, arg: '__' + k, label: k }), kind);
      await page.waitForFunction(k => tabs.some(t => t.kind === k), kind, { timeout: 10000 });
    } catch (e) { came = false; }
    // The window in which an open could ask a second time.
    await quietFor(1200);
    const f = await page.evaluate(() => window.__f);
    if (!came){ ok(false, `[${kind}] opened for the request count (did not come up: ${Object.keys(f).join(', ') || 'no fetch at all'})`); }
    // Once for the open, and once more for each revision that moved inside
    // the window, which the page is right to follow.
    const moved = await MOVED();
    const twice = Object.entries(f).filter(([u, n]) => !POLLS.has(u) && n > 1 + moved.length);
    ok(twice.length === 0, `[${kind}] opening asks each endpoint once (${twice.length ? twice.map(([u, n]) => `${u} x${n}`).join(', ') : Object.keys(f).filter(u => !POLLS.has(u)).join(', ') || 'nothing'}${moved.length ? '; moved: ' + moved.join(', ') : ''})`);
    // ...and closed again, so the tab cap never refuses the next one.
    await page.evaluate(k => { for (const t of [...tabs]) if (t.kind === k) dropTab(t.id); }, kind);
  }
  await page.evaluate(() => { for (const t of [...tabs]) if (t.kind !== 'term') dropTab(t.id); });
});
}

if (runs('c')) {
// ---- a fold lasts for the page, and a reload starts it from the default ---
// Open state is kept while the page lives and never stored (the design
// language, Sections): closed by hand on a desktop, where the default is
// open, it stays closed through the repaints and is open again after a
// reload. Measured on the Nodes tab's Health section: a fixed section
// rather than the first one found, because a tab that is still filling in
// (the Docker manager redraws as its rows land) replaces the element
// between the find and the close, and a close on a detached fold records
// nothing, which read as the rule failing when only the sample had moved.
await section("a fold lasts for the page, and a reload starts it from the default", async () => {
  const kind = 'nodes', key = 'nodes:health';
  const sel = `.doc.on details.sect[data-sect="${key}"]`;
  // Opened if it is not there: the request-count block above closes every
  // tab, and whether one came back before this ran depended on the layout
  // poll, which is the whole of B219.
  const focus = async () => {
    const had = await page.evaluate(k => { const t = tabs.find(x => x.kind === k);
                                           if (t) focusTab(t.id); return !!t; }, kind);
    if (!had) await DRIVERS[kind].open();
    await page.waitForSelector(DRIVERS[kind].readyWhen, { timeout: 20000 });
    await page.waitForSelector(sel, { timeout: 20000 });
  };
  // A desk: the page was narrowed to a phone above, where one section is
  // open by rule, and this block is the desktop's rule (every default open).
  await page.setViewportSize({ width: 1280, height: 900 });
  await atWidth(page, 1280);
  await focus();
  ok(await page.$eval(sel, d => d.open), `[${kind}] a section opens by default on a desktop (${key})`);
  // A press on the summary, not `open = false`: only a fold somebody pressed
  // is recorded, so that markup arriving open is never mistaken for a choice.
  await page.click(sel + ' > summary');
  await page.waitForFunction(k => sectOpen[k] === false, key, { timeout: 5000 });
  ok(true, `[${kind}] a fold closed by hand stays closed for the page (${key})`);
  await page.reload(); await ready(page);
  await focus();
  ok(await page.$eval(sel, d => d.open),
     `[${kind}] ...and a reload starts it from its default, open on a desktop`);
});
}

if (runs('c')) {
// ---- hidden means hidden (design language, Sections and action bars) -----
// Every element carrying the attribute is out of the layout, whatever class
// it wears. A class with a display once beat it: a fold that never closed.
await section("hidden means hidden", async () => {
  const shown = await page.evaluate(() => [...document.querySelectorAll('[hidden]')]
    .filter(e => getComputedStyle(e).display !== 'none')
    .map(e => e.id || e.className || e.tagName).slice(0, 5));
  ok(shown.length === 0, `nothing carrying hidden is displayed${shown.length ? ': ' + shown.join(', ') : ''}`);
});
}

if (runs('c')) {
// ---- dialogs (design language, Dialogs) -----------------------------------
// Opened one by one, and each held to the shape every dialog shares: its
// lines in .field bands (text at box level draws flush against the edge),
// groups headed by a label and never an h4, and the buttons in a .foot.
// Discovered, like the tab kinds: every .modal in the page must be opened by
// a driver here, so a new dialog with none FAILS by its id, which is the
// price of adding one.
const DIALOGS = {
  about: () => openAbout(), newproject: () => openNewProject(), trash: () => openTrash(), out: () => askSignOut(),
  pending: () => openPending('alpha'), report: () => openReport('alpha'),
  phonelend: () => openPhoneLend('alpha'),
  newcontainer: () => openNewContainer(),
  // A new project's first session: opened for a project with no brief, which
  // draws the same dialog with an empty text box.
  firstsession: () => openBrief('alpha', ''),
  senddocker: () => openSendToDocker('ep.silon'), devenv: () => openDevEnv('ep.silon', 'main'),
  relocate: () => openRelocate('ep.silon', 'main'),
  projsettings: () => renameProject('alpha'),
  // Reset AerieOS (the operator, 12 Oct): the nodes to un-enroll first,
  // what un-enrolling does, and the word. Opened, measured, never pressed.
  reset: () => askReset(),
  // A conversation read from a notebook's Sessions view (R83): the
  // account's newest on alpha if it has one, else the same box with nothing
  // said in it, never a 404 the console would count.
  conversation: async () => {
    const c = ((await (await fetch('/api/transcripts?project=alpha')).json()).rows || [])[0];
    if (c) return openConversation('alpha', c.id);
    $('cvBody').innerHTML = '<div class="empty">Nothing said in it yet.</div>';
    $('cvModal').hidden = false;
  },
  // The agent chooser, the house dialog: opened from alpha's Start agent
  // on the Spaces page.
  chooser: async () => { railGo('projects');
    for (let i = 0; i < 40 && !document.querySelector('.projtab [data-c="alpha"]'); i++) await new Promise(r => setTimeout(r, 250));
    resumeFor = null; openClaude('alpha'); },
  // The dialogs a page builds when it opens one, each as it opens empty.
  newvm: () => openNewVm(), useradd: () => usersAddOpen(), rolenew: () => rolesNewOpen(),
  // A repository's move, on a plan of the shape the server answers (one
  // node to bring, nothing else going), and a space's roles for its owner.
  move: () => { moveConfirm({ label: 'beta', from: 'gamma', to: 'alpha', node_why: '', busy: [], things: [], lose: [],
                              nodes: [{ id: 'n_x', name: 'ubu', have: false, as: 'works', instances: [] }] }); },
  roleaccess: () => rolesAccessOpen('test'),
  // The Library's Add your own, a pack's dialog with nothing picked yet.
  addown: () => new Promise(r => libWithToolchains(() => { tpOpen(''); r(); })),
  // A notebook's sheet: alpha's Roadmap history, pressed as a person does.
  sheet: async () => { openNotebook('alpha', 'roadmap');
    let b = null;
    for (let i = 0; i < 40 && !(b = [...document.querySelectorAll('.nb [id="roadmapLog"]')].find(x => x.checkVisibility())); i++)
      await new Promise(r => setTimeout(r, 250));
    b?.click(); },
  // A schedule's form reads the Schedules page's nodes: opened from there.
  schedule: async () => { railGo('jobs', 'schedules');
    for (let i = 0; i < 40 && !schedData; i++) await new Promise(r => setTimeout(r, 250));
    openSchedForm(null); },
  // ...the harness's own answer to a question (lib.mjs) stood aside while
  // it opens, or it is answered before it is measured.
  question: () => { const was = window.__bbAsk; window.__bbAsk = null; ask({ title: 'A question', text: 'Is it so?' }); window.__bbAsk = was; },
  enroll: async () => { openNodesTab();
    for (let i = 0; i < 40 && !document.querySelector('.nodestab button'); i++) await new Promise(r => setTimeout(r, 250));
    [...document.querySelectorAll('.nodestab button')].find(b => /enroll/i.test(b.textContent))?.click(); },
};
// A dialog that keeps a press on the page around it, and why.
const KEEPS_A_STRAY_PRESS = {
  enroll: "it shows an enrollment's one-time token, which a stray press must not take away",
};
const opened = new Set();
async function dialogShape(pg = page){
  return pg.evaluate(() => {
    const m = [...document.querySelectorAll('.modal:not(.inline)')].find(x => !x.hidden);
    if (!m) return { err: 'no dialog opened' };
    const box = m.querySelector('.box');
    const loose = [...box.querySelectorAll('*')].filter(e => {
      // A section's heading is a heading, as the h3 is: a long dialog's
      // groups are sections (the project settings, 7 Oct).
      // ...and so is a fold's that shows more (.chev), which carries its own
      // inset as a section's does.
      if (e.offsetHeight === 0 || e.closest('h3, .field, .foot, details.sect > summary, details.chev > summary')) return false;
      return [...e.childNodes].some(n => n.nodeType === 3 && n.textContent.trim());
    }).map(e => `${e.tagName.toLowerCase()} "${e.textContent.trim().slice(0, 24)}"`);
    // One scroller, not two: a box that scrolls around a part that scrolls
    // too is the half-a-line wobble About had on every size (18 Sep).
    const scrolls = e => e.scrollHeight > e.clientHeight + 1;
    // A text box scrolling its own text is an editor doing its job, not a
    // second scroller in the dialog's layout; so is a listbox scrolling its
    // rows past four (the design language, Controls), which is what keeps
    // a dialog of forty projects short.
    const inner = [...box.querySelectorAll('*')].filter(e => e.offsetHeight && scrolls(e)
      && e.tagName !== 'TEXTAREA' && !e.classList.contains('lbox') && /auto|scroll/.test(getComputedStyle(e).overflowY));
    const nested = scrolls(box) && inner.length
      ? `the box scrolls ${box.scrollHeight - box.clientHeight}px around ${inner[0].id || inner[0].className || inner[0].tagName}, which scrolls too` : '';
    // A dialog of prose (About) may have headings; one of fields may not.
    // The verbs at the foot's right, after its .sp (the dialog's layout
    // rule): six dialogs had none and drew them at the left, under the
    // toast stack's corner (B749).
    const fb = box.querySelector('.foot');
    const btns = fb ? [...fb.querySelectorAll('button')].filter(b => b.offsetWidth) : [];
    const gap = btns.length ? Math.round(fb.getBoundingClientRect().right - Math.max(...btns.map(b => b.getBoundingClientRect().right))) : 0;
    // The census of the one shape (R50 step 81): its title the box's first
    // line, its foot the box's own, centered over the page, its width, and
    // the order of its foot (a state, the spacer, the verbs).
    const r = box.getBoundingClientRect();
    const order = fb ? [...fb.children].filter(e => e.offsetWidth || e.classList.contains('sp')).map(e =>
      e.classList.contains('sp') ? 'sp' : e.classList.contains('state') ? 'state' : e.tagName === 'BUTTON'
        ? (e.classList.contains('primary') ? 'P' : e.classList.contains('danger') || e.dataset.danger ? 'D' : 'b') : e.tagName.toLowerCase()).join(' ') : '';
    const census = { id: m.id || m.className, cls: [...box.classList].filter(c => c !== 'box').join('.') || '-', w: Math.round(r.width),
      // Its title the first line, and one that shows: a notebook's rule hid
      // the sheet's while the element stood first (the dialog walk, 17 Nov).
      title: box.firstElementChild?.tagName === 'H3' && box.firstElementChild.offsetHeight > 0, ownFoot: !!box.querySelector(':scope > .foot, :scope > .dlgbody > .foot'),
      // ...and in Perch's voice (the operator, 23 Nov): the section voice,
      // sentence case, a band a pop-out's height, never small capitals.
      // ...and its foot at the box's foot, a held box's too (R273: a box held
      // at its tallest pane's height showed a shorter pane with its buttons
      // under it and the rest of the height empty below them).
      low: fb ? Math.round(r.bottom - fb.getBoundingClientRect().bottom) : null,
      voice: (h => h ? `${getComputedStyle(h).textTransform} ${parseFloat(getComputedStyle(h).fontSize)} ${getComputedStyle(h).fontWeight} ${Math.round(h.getBoundingClientRect().height)}` : '')(box.querySelector(':scope > h3')),
      mid: r.height < innerHeight - 40 ? Math.round(r.top + r.height / 2 - innerHeight / 2) : 'tall', order };
    return { nested, loose: loose.slice(0, 3), h4: box.classList.contains('prose') ? 0 : box.querySelectorAll('h4').length,
             foot: !!fb && fb.offsetHeight > 0, gap, census };
  });
}
// A button on the page that a dialog is opened from, as a person's press
// leaves the focus on what they pressed; and what the dialog on show took
// for its opener, kept to be found again once it is put away.
const focusProbe = async () => {
  // Once a dialog put away has finished leaving: focus given to the page
  // while one still left went nowhere under a whole run's load, and the next
  // dialog opened with no opener (17 Nov, About).
  for (let i = 0; i < 80 && document.querySelector('.modal.leaving'); i++) await new Promise(r => setTimeout(r, 25));
  let b = document.getElementById('dlgProbe');
  if (!b){
    b = document.createElement('button'); b.id = 'dlgProbe'; b.type = 'button'; b.textContent = 'probe';
    b.style.cssText = 'position:fixed;left:0;top:0;width:8px;height:8px;opacity:.01';
    document.body.appendChild(b);
  }
  b.focus();
};
const keepOpener = () => { window.__dlgOpener = [...document.querySelectorAll('.modal:not(.inline)')].find(m => !m.hidden)?.__opener || null; };
for (const [name, open] of Object.entries(DIALOGS)) {
  await page.evaluate(focusProbe);
  await page.evaluate(open);
  const seen = await page.waitForFunction(() => [...document.querySelectorAll('.modal:not(.inline)')].some(m => !m.hidden),
    null, { timeout: 10000 }).then(() => true).catch(() => false);
  // Its entrance over, and what it reads in and drawn.
  await motionOver();
  await settled(page, { quiet: 250 });
  const d = seen ? await dialogShape() : { err: 'nothing opened' };
  const id = await page.evaluate(() => [...document.querySelectorAll('.modal:not(.inline)')].find(m => !m.hidden)?.id || '');
  if (id) opened.add(id);
  // One shape for every dialog (R50 step 81): its title the box's first
  // line, its foot the box's own, centered over the page, its foot in the
  // rule's order (only a state before the spacer; the primary first among
  // the verbs; anything destructive last), and Escape puts it away.
  const c = d.census || {};
  const toks = String(c.order || '').split(' ').filter(Boolean), sp = toks.indexOf('sp'), verbs = toks.slice(sp + 1);
  const ordered = sp >= 0 && toks.slice(0, sp).every(t => t === 'state')
    && (!verbs.includes('P') || verbs[0] === 'P') && verbs.every((t, i) => t !== 'D' || verbs.slice(i).every(x => x === 'D'));
  ok(!d.err && c.title && c.ownFoot && (c.mid === 'tall' || Math.abs(c.mid) <= 2) && ordered && (c.low === null || c.low <= 2),
     `[dialog ${name}] titled first, its foot its box's own in the rule's order and at the box's foot, centered (${JSON.stringify(c)})`);
  const [tt, tsize, tweight, th] = String(c.voice || '').split(' ');
  ok(!d.err && tt === 'none' && +tsize >= 14 && +tweight >= 600 && +th >= 40,
     `[dialog ${name}] its title in the section voice, sentence case, a band as tall as a pop-out's (${c.voice})`);
  ok(!d.err && d.loose.length === 0 && d.h4 === 0 && d.foot,
     `[dialog ${name}] its lines in .field bands, no h4, buttons in a .foot${
       d.err ? ` (${d.err})` : d.loose.length ? `: loose ${d.loose.join(', ')}` : d.h4 ? `: ${d.h4} h4` : !d.foot ? ': no foot' : ''}`);
  ok(!d.nested, `[dialog ${name}] scrolls in one place${d.nested ? `: ${d.nested}` : ''}`);
  if (!d.err){
    const fh = await formsHold('.modal:not([hidden]):not(.inline) > .box');
    ok(fh.length === 0, `[dialog ${name}] a label over each field, and no field touching the one above it${fh.length ? `: ${fh.join('; ')}` : ''}`);
  }
  ok(!d.err && d.gap <= 32, `[dialog ${name}] its verbs sit at the foot's right (${d.gap}px from its edge)`);
  // The jump bar's chips sit in a row (the operator, 11 Oct): the dialog's
  // field rule stacks a band's children, and the bar is a band.
  const jump = await page.evaluate(() => {
    const bar = [...document.querySelectorAll('.modal:not(.inline)')].find(x => !x.hidden)?.querySelector('.sectjump');
    if (!bar || !bar.offsetHeight) return null;
    const a = [...bar.querySelectorAll('a')].slice(0, 2).map(e => Math.round(e.getBoundingClientRect().top));
    return { dir: getComputedStyle(bar).flexDirection, stacked: a.length === 2 && a[0] !== a[1] };
  });
  if (jump) ok(jump.dir === 'row' && !jump.stacked, `[dialog ${name}] its jump bar's chips sit in a row (${jump.dir}${jump.stacked ? ', stacked' : ''})`);
  // One rhythm down a form. The sandbox VM dialog measured 0, 0, 10, 10, 0
  // between its fields, because a .prefrow carried a gap and the band's own
  // stacked children carried none, so one form read as three depending on
  // which container a field landed in. The token is --field-gap.
  const rhythm = await page.evaluate(() => {
    const m = [...document.querySelectorAll('.modal:not(.inline)')].find(x => !x.hidden);
    const box = m?.querySelector('.box');
    if (!box) return { err: 'no dialog' };
    const css = getComputedStyle(document.documentElement);
    const want = Math.round(parseFloat(css.getPropertyValue('--field-gap')) || 10);
    // A label and the control under it are one thing, so they sit closer.
    const tight = Math.round(parseFloat(css.getPropertyValue('--label-gap')) || 5);
    // Within ONE band, never across two: the gap between bands is their
    // padding twice over and is the band's business, not the form's.
    const odd = [];
    // The jump bar's chips wrap at their own gap, which is not the form's.
    for (const parent of box.querySelectorAll('.field:not(.sectjump), .field .prefrow')) {
      const rows = [...parent.children].filter(e => e.offsetHeight);
      for (let i = 1; i < rows.length; i++) {
        const a = rows[i - 1].getBoundingClientRect(), b = rows[i].getBoundingClientRect();
        if (b.top < a.bottom - 1) continue;            // side by side, not stacked
        const gap = Math.round(b.top - a.bottom);
        const expect = rows[i - 1].tagName === 'LABEL' ? tight : want;
        if (Math.abs(gap - expect) > 1)
          odd.push(`${gap}px (wanted ${expect}) before ${
            rows[i].className || rows[i].tagName.toLowerCase()}`);
      }
    }
    return { want, tight, odd };
  });
  // A dialog holds the page still. Its overlay is the scroller when the box
  // is taller than the screen, and without these two the flick that reaches
  // the end of a dialog carries on into the page behind it, which is what
  // the operator saw on a phone: the whole page moving under the box.
  const still = await page.evaluate(() => {
    const m = [...document.querySelectorAll('.modal:not(.inline)')].find(x => !x.hidden);
    if (!m) return { err: 'no dialog' };
    return { chain: getComputedStyle(m).overscrollBehaviorY,
             locked: getComputedStyle(document.documentElement).overflow };
  });
  ok(!still.err && still.chain === 'contain' && still.locked === 'hidden',
     `[dialog ${name}] holds the page still behind it (overscroll ${still.chain}, page ${still.locked})`);
  ok(!rhythm.err && rhythm.odd.length === 0,
     `[dialog ${name}] one rhythm down the band (${rhythm.want}px, ${rhythm.tight}px under a label)${
       rhythm.err ? ` (${rhythm.err})` : rhythm.odd.length ? `: ${rhythm.odd.join('; ')}` : ''}`);
  // ...a press on the dimmed page around it puts it away (R50 step 81),
  // and so does Escape, each as a person shuts it: opened again for the
  // second. A dialog holding something said once keeps a stray press.
  const shut = () => page.waitForFunction(() => ![...document.querySelectorAll('.modal:not(.inline)')].some(m => !m.hidden),
    null, { timeout: 3000 }).then(() => true).catch(() => false);
  if (!KEEPS_A_STRAY_PRESS[name]){
    await page.mouse.click(3, Math.round((await page.evaluate(() => innerHeight)) - 3));
    ok(await shut(), `[dialog ${name}] a press on the page around it puts it away`);
    await page.evaluate(() => { document.querySelectorAll('.modal').forEach(m => { m.hidden = true; }); resumeFor = null; resumePick = null; });
    await page.evaluate(focusProbe);
    await page.evaluate(open);
    await page.waitForFunction(() => [...document.querySelectorAll('.modal:not(.inline)')].some(m => !m.hidden), null, { timeout: 10000 }).catch(() => {});
    await motionOver();
  }
  await page.evaluate(keepOpener);
  const heldOpen = await page.evaluate(() => history.state?.dlg || 0);
  await page.keyboard.press('Escape');
  const escaped = await page.waitForFunction(() => ![...document.querySelectorAll('.modal')].some(m => !m.hidden && !m.classList.contains('inline')),
    null, { timeout: 3000 }).then(() => true).catch(() => false);
  ok(escaped, `[dialog ${name}] Escape puts it away`);
  // ...and the focus goes back to what opened it, so a keyboard carries on
  // from where the person was (R50 step 81).
  const back = await page.evaluate(() => {
    const o = window.__dlgOpener, a = document.activeElement;
    const say = e => !e ? 'nothing' : e === document.body ? 'body' : e.id || e.dataset?.c || String(e.className || e.tagName.toLowerCase()).slice(0, 30);
    return { opener: say(o), now: say(a), same: !!o && a === o };
  });
  ok(escaped && back.same, `[dialog ${name}] the focus goes back to what opened it (${back.opener}; now on ${back.now})`);
  // ...and Back puts it away with the page under it staying where it was
  // (the operator, 17 Nov). Put away by Escape it gave its entry in the
  // history back, so Back is the dialog's alone; one that keeps a stray
  // press holds none, and Back passes it by.
  if (!KEEPS_A_STRAY_PRESS[name]){
    const given = await page.waitForFunction(() => !history.state?.dlg, null, { timeout: 3000 }).then(() => true).catch(() => false);
    ok(given, `[dialog ${name}] put away, it gives its entry in the history back`);
    await page.evaluate(() => { document.querySelectorAll('.modal').forEach(m => { m.hidden = true; }); resumeFor = null; resumePick = null; });
    await page.evaluate(open);
    await page.waitForFunction(() => [...document.querySelectorAll('.modal:not(.inline)')].some(m => !m.hidden), null, { timeout: 10000 }).catch(() => {});
    await motionOver();
    const was = await page.evaluate(() => ({ hash: location.hash, dlg: history.state?.dlg || 0 }));
    await page.evaluate(() => history.back());
    const away = await shut();
    const now = await page.evaluate(() => location.hash);
    ok(was.dlg && away && now === was.hash, `[dialog ${name}] Back puts it away and the page stays (${was.hash}${was.dlg ? '' : ', held no entry'}${away ? '' : ', still open'}; then ${now})`);
  } else ok(!heldOpen, `[dialog ${name}] holds no entry in the history, so Back passes it by (${KEEPS_A_STRAY_PRESS[name]})`);
  await page.evaluate(() => { document.querySelectorAll('.modal').forEach(m => { m.hidden = true; }); resumeFor = null; resumePick = null; });
}
await page.evaluate(() => document.getElementById('dlgProbe')?.remove());
// A page opened the moment a dialog is put away stays open: the dialog's
// entry is given back after it closes, and a page pushed meanwhile was
// undone by that give-back (cards.mjs, 18 Nov: Settings canceled, then a
// notebook's Signing opened, and the page went back to Spaces).
await section("a page opened as a dialog is put away stays open", async () => {
  await page.evaluate(() => { location.hash = '#/home'; });
  await page.waitForFunction(() => location.hash === '#/home', null, { timeout: 5000 }).catch(() => {});
  await page.evaluate(() => openAbout());
  await page.waitForFunction(() => !document.getElementById('aboutModal').hidden && history.state?.dlg, null, { timeout: 5000 }).catch(() => {});
  // The page opened just after the give-back has begun, as a second press
  // lands: closed, then opened a moment later, in the window it had.
  await page.evaluate(() => new Promise(r => { closeAbout(); setTimeout(() => { railGo('jobs'); r(); }, 2); }));
  await new Promise(r => setTimeout(r, 1500));
  const after = await page.evaluate(() => ({ hash: location.hash, kind: tabOf(panes[0])?.kind || '', dlg: history.state?.dlg || 0 }));
  ok(/^#\/jobs/.test(after.hash) && after.kind === 'jobs' && !after.dlg,
     `a page opened as a dialog is put away stays open, its address with it (${JSON.stringify(after)})`);
});
// ...and again on a small phone, where the room runs out first: every dialog
// is the whole screen, its foot at the bottom, and still scrolls in one place.
await section("and again on a small phone, where the room runs out first", async () => {
  const phone = await newPage(browser, { viewport: { width: 360, height: 740 }, isMobile: true, hasTouch: true });
  await phone.goto(URL); await ready(phone);
  const twice = [], short = [];
  for (const [name, open] of Object.entries(DIALOGS)) {
    await phone.evaluate(open);
    await phone.waitForFunction(() => [...document.querySelectorAll('.modal')].some(m => !m.hidden),
      null, { timeout: 10000 }).catch(() => {});
    await motionOver(phone);
    await settled(phone, { quiet: 250 });
    const d = await dialogShape(phone);
    if (d.nested) twice.push(`${name}: ${d.nested}`);
    // Its box from edge to edge and top to bottom, and its foot's bottom the
    // screen's, however little the dialog holds.
    const fill = await phone.evaluate(() => {
      const modal = [...document.querySelectorAll('.modal:not(.inline)')].find(m => !m.hidden);
      const box = modal?.querySelector('.box');
      if (!box) return 'no dialog';
      const r = box.getBoundingClientRect(), f = box.querySelector(':scope > .foot, :scope > .dlgbody > .foot')?.getBoundingClientRect();
      const off = [r.left, r.top, innerWidth - r.right, innerHeight - r.bottom].map(Math.round);
      // But for a question (R265): a sheet at the foot, edge to edge, as tall
      // as its words and no taller, the page showing above it.
      if (modal.classList.contains('askdlg') && !modal.classList.contains('typed'))
        return off[0] || off[2] || off[3] ? `a question's sheet ${off.join(',')} in from the edges`
          : off[1] < 56 ? `a question's sheet leaves ${off[1]}px of the page showing`
          : Math.abs(box.scrollHeight - r.height) > 2 ? `a question's sheet is ${Math.round(r.height)}px for ${box.scrollHeight}px of words` : '';
      return off.some(v => Math.abs(v) > 1) ? `box ${off.join(',')} in from the edges`
        : f && Math.abs(Math.round(innerHeight - f.bottom)) > 1 ? `foot ${Math.round(innerHeight - f.bottom)}px over the bottom` : '';
    });
    if (fill) short.push(`${name}: ${fill}`);
    await phone.evaluate(() => { document.querySelectorAll('.modal').forEach(m => { m.hidden = true; }); resumeFor = null; resumePick = null; });
  }
  ok(short.length === 0, `on a 360px phone every dialog is the whole screen, its foot at the bottom, and a question a sheet at the foot as tall as its words${short.length ? ': ' + short.join(' | ') : ''}`);
  ok(twice.length === 0, `on a 360px phone every dialog scrolls in one place${twice.length ? ': ' + twice.join(' | ') : ''}`);
  await phone.close();
});
await section("every dialog in the page is measured", async () => {
  const all = await page.evaluate(() => [...document.querySelectorAll('.modal[id]')].map(m => m.id));
  const undriven = all.filter(x => !opened.has(x));
  ok(undriven.length === 0, `every dialog in the page is measured${undriven.length
    ? `: no driver opens ${undriven.join(', ')} (add one to DIALOGS in uniform.mjs)` : ''}`);
});
}

if (runs('c')) {
// ---- a finger, not a pointer (design language, Both sizes) ---------------
// On a touch phone the controls a thumb meets are a thumb's size, and a bar
// that spans the screen fits it even on a fold's 344px cover.
await section("a finger, not a pointer", async () => {
  const phone = await newPage(browser, { viewport: { width: 375, height: 667 }, isMobile: true, hasTouch: true });
  await phone.goto(URL); await ready(phone);
  await phone.evaluate(() => { openNotebook('alpha', 'roadmap'); });
  await phone.waitForSelector('.nb .nbview:not([hidden])', { timeout: 20000 });
  await arrived(phone);
  const small = await phone.evaluate(() => [...document.querySelectorAll(
      '.dockbar button, .nb button, .mobar button')]
    .filter(e => e.offsetHeight > 0)
    .filter(e => { const r = e.getBoundingClientRect(); return r.height < 30 || r.width < 30; })
    .map(e => `${e.className || e.tagName} "${e.textContent.trim().slice(0, 12)}" ${Math.round(e.getBoundingClientRect().width)}x${Math.round(e.getBoundingClientRect().height)}`));
  ok(small.length === 0, `on a touch phone the dock, the notebook and the bar are a thumb's size${small.length ? ': ' + small.slice(0, 4).join(', ') : ''}`);
  await phone.evaluate(() => openNewProject());
  await phone.waitForSelector('.modal:not([hidden]) .foot button', { timeout: 10000 });
  // (The page's own control height, --tap: never a number kept here.)
  const shortFoot = await phone.$$eval('.modal:not([hidden]) .foot button', bs => { const tap = parseFloat(getComputedStyle(document.documentElement).getPropertyValue('--tap'));
    return bs.filter(b => b.getBoundingClientRect().height < tap - 0.5).length; });
  ok(shortFoot === 0, `...and a dialog's buttons are the tap height (${shortFoot} short)`);
  await phone.setViewportSize({ width: 344, height: 882 });
  await phone.evaluate(() => { document.querySelectorAll('.modal').forEach(m => { m.hidden = true; }); resumeFor = null; resumePick = null; });
  await atWidth(phone, 344);
  const cut = await phone.evaluate(() => [...document.querySelectorAll('.mobar > button')]
    .filter(b => b.offsetHeight > 0 && b.getBoundingClientRect().right > innerWidth + 1).map(b => b.textContent.trim()));
  ok(cut.length === 0, `...and the bar fits a fold's 344px cover${cut.length ? `: cut off ${cut.join(', ')}` : ''}`);
  // ...and the top bar's search keeps its 80px there, nothing in the header
  // pushed past the edge to make room (B744, B290).
  const top = await phone.evaluate(() => ({ jump: Math.round(document.getElementById('jump').getBoundingClientRect().width),
    over: [...document.querySelectorAll('header > *')].filter(e => e.offsetWidth > 0 && e.getBoundingClientRect().right > innerWidth + 0.5).map(e => e.id || e.className) }));
  ok(top.jump >= 80 && top.over.length === 0, `...and the top bar's search is at least 80px wide at 344, the header inside the screen (${JSON.stringify(top)})`);
  await phone.context().close();
});
}

ok(page.errors.length === 0,
   `zero console errors${page.errors.length ? ': ' + page.errors[0] : ''}`);
await done(browser);
