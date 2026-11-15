// patch(): a redraw that keeps what a person is doing (R244). The new markup
// is patched into what is there: every element it can be matched to is kept
// and brought up to date, so typing, its caret and an IME composition, a fold
// turned and a dialog open outlive a redraw from the poll, and what the
// markup changes on purpose (a Revert, a draft drawn, a section opened by an
// address) still lands. Each rule is held on a scratch element of the real
// page, with markup written here.
import { URL, launch, newPage, ok, done, ready, section } from './lib.mjs';

const browser = await launch();
const page = await newPage(browser, { viewport: { width: 1280, height: 900 } });
await page.goto(URL);
await ready(page);
const cdp = await page.context().newCDPSession(page);

// A scratch element on the page, drawn once with `html`; what each part then
// does is its own.
const fresh = html => page.evaluate(html => {
  document.querySelector('#r244')?.remove();
  const el = document.createElement('div'); el.id = 'r244'; document.body.append(el);
  patch(el, html);
  return el.innerHTML.length;
}, html);

await section("the same markup is no change, and a change keeps the elements it can", async () => {
  await fresh('<div class="a"><b>one</b> <i>two</i></div><p>three</p>');
  const r = await page.evaluate(() => {
    const el = document.querySelector('#r244'), b = el.querySelector('b'), p = el.querySelector('p');
    const same = patch(el, '<div class="a"><b>one</b> <i>two</i></div><p>three</p>');
    const changed = patch(el, '<div class="a on"><b>uno</b> <i>two</i></div><p>three</p>');
    return { same, changed, bKept: el.querySelector('b') === b, pKept: el.querySelector('p') === p,
             text: el.querySelector('b').textContent, cls: el.querySelector('div').className };
  });
  ok(r.same === false && r.changed === true && r.bKept && r.pKept && r.text === 'uno' && r.cls === 'a on',
     `the same markup writes nothing, and a change is written into the elements already there (${JSON.stringify(r)})`);
});

await section("typing, its caret and a composition outlive a redraw", async () => {
  await fresh('<div class="field"><input type="text" data-k="name" value="old"></div><span>3 running</span>');
  await page.evaluate(() => { const f = document.querySelector('#r244 input'); f.focus(); f.value = 'abcd'; f.setSelectionRange(2, 2); });
  await cdp.send('Input.imeSetComposition', { text: 'か', selectionStart: 1, selectionEnd: 1 });
  const r = await page.evaluate(() => {
    const el = document.querySelector('#r244'), f = el.querySelector('input');
    let ended = 0; f.addEventListener('compositionend', () => ended++); f.addEventListener('blur', () => ended++);
    patch(el, '<div class="field"><input type="text" data-k="name" value="old"></div><span>4 running</span>');
    return { kept: el.querySelector('input') === f, focus: document.activeElement === f, value: f.value, caret: f.selectionStart,
             ended, text: el.querySelector('span').textContent };
  });
  await cdp.send('Input.insertText', { text: '' });
  ok(r.kept && r.focus && /^abか?cd$/.test(r.value) && r.caret >= 2 && r.caret <= 3 && r.ended === 0 && r.text === '4 running',
     `the field is kept with its focus, its value, its caret and its composition while the rest moves (${JSON.stringify(r)})`);
  const back = await page.evaluate(() => {
    const el = document.querySelector('#r244'), f = el.querySelector('input');
    f.blur(); f.value = 'typed';
    patch(el, '<div class="field"><input type="text" data-k="name" value="from the server"></div><span>4 running</span>');
    const a = f.value;
    patch(el, '<div class="field"><input type="text" data-k="name" value="from the server"></div><span>5 running</span>');
    return { changedByMarkup: a, keptAfter: f.value };
  });
  ok(back.changedByMarkup === 'from the server' && back.keptAfter === 'from the server',
     `...and a value the markup changes (a Revert, a draft drawn) is the field's value (${JSON.stringify(back)})`);
});

await section("a row's typing stays in its row when the rows move", async () => {
  const rows = keys => keys.map(k => `<div class="row" data-key="${k}"><span>${k}</span><input type="text" data-f="note" value=""></div>`).join('');
  await fresh(rows(['a', 'b', 'c']));
  const r = await page.evaluate(([three, two]) => {
    const el = document.querySelector('#r244'), c = el.querySelector('[data-key="c"] input');
    c.focus(); c.value = 'for c';
    patch(el, three);             // b taken away and a new one first
    const moved = el.querySelector('[data-key="c"] input');
    const out = { kept: moved === c, focus: document.activeElement === c, value: moved.value,
                  order: [...el.querySelectorAll('.row')].map(x => x.dataset.key).join(''), others: [...el.querySelectorAll('input')].filter(i => i !== c).map(i => i.value).join('|') };
    patch(el, two);
    out.after = el.querySelector('[data-key="c"] input')?.value;
    return out;
  }, [rows(['z', 'a', 'c']), rows(['c', 'a'])]);
  ok(r.kept && r.focus && r.value === 'for c' && r.order === 'zac' && r.others === '|' && r.after === 'for c',
     `rows named by data-key keep their own field through a row added, one taken away and a reorder (${JSON.stringify(r)})`);
  const field = await page.evaluate(() => {
    const el = document.querySelector('#r244');
    el.innerHTML = ''; patch(el, '<input type="text" data-k="host" value="">');
    const f = el.querySelector('input'); f.focus(); f.value = 'typed host';
    patch(el, '<input type="text" data-k="port" value="">');
    const g = el.querySelector('input');
    return { replaced: g !== f, value: g.value, k: g.dataset.k };
  });
  ok(field.replaced && field.value === '' && field.k === 'port',
     `...and another field drawn in the same place is not handed what was typed into the first (${JSON.stringify(field)})`);
  const run = await page.evaluate(() => {
    const el = document.querySelector('#r244');
    el.innerHTML = ''; patch(el, '<p>gone</p><div>one</div><div>two</div><div>three</div>');
    const two = el.querySelectorAll('div')[1];
    patch(el, '<div>one</div><div>two</div><div>three!</div>');
    return { kept: el.querySelectorAll('div')[1] === two, text: el.textContent };
  });
  ok(run.kept && run.text === 'onetwothree!', `...and an unnamed run with its first taken away keeps the rest (${JSON.stringify(run)})`);
});

await section("a fold is the person's, unless the markup changes it", async () => {
  await fresh('<details class="sect"><summary>Storage</summary><div>a</div></details><span>1</span>');
  const r = await page.evaluate(() => {
    const el = document.querySelector('#r244'), d = el.querySelector('details');
    d.open = true;                                                    // the person opened it
    patch(el, '<details class="sect"><summary>Storage</summary><div>a</div></details><span>2</span>');
    const keptOpen = d.open;
    d.open = false;                                                   // and shut it again
    patch(el, '<details class="sect" open><summary>Storage</summary><div>a</div></details><span>3</span>');
    const openedByMarkup = d.open;                                    // an address opens it
    d.open = false;
    patch(el, '<details class="sect" open><summary>Storage</summary><div>a</div></details><span>4</span>');
    return { keptOpen, openedByMarkup, keptShut: !d.open, same: el.querySelector('details') === d };
  });
  ok(r.keptOpen && r.openedByMarkup && r.keptShut && r.same,
     `a fold the person turned stays turned, and one the markup newly opens opens (${JSON.stringify(r)})`);
  const first = await page.evaluate(() => {
    document.querySelector('#r244')?.remove();
    const el = document.createElement('div'); el.id = 'r244'; document.body.append(el);
    patch(el, '<details><summary>x</summary>y</details><b>1</b>');  // the first draw writes it whole
    const d = el.querySelector('details'); d.open = true;
    patch(el, '<details><summary>x</summary>y</details><b>2</b>');
    return d.open;
  });
  ok(first, '...from the first redraw after the first draw too');
});

await section("a dialog open in the markup stays open", async () => {
  await fresh('<div class="row" data-key="web"><span>up</span><dialog class="modal"><input type="text" data-k="image" value="nginx"></dialog></div>');
  const r = await page.evaluate(() => {
    const el = document.querySelector('#r244'), dlg = el.querySelector('dialog');
    dlg.showModal();
    const f = dlg.querySelector('input'); f.focus(); f.value = 'nginx:1.27';
    patch(el, '<div class="row" data-key="web"><span>restarting</span><dialog class="modal"><input type="text" data-k="image" value="nginx"></dialog></div>');
    const out = { kept: el.querySelector('dialog') === dlg, open: dlg.open, value: f.value, focus: document.activeElement === f };
    dlg.close();
    return out;
  });
  ok(r.kept && r.open && r.value === 'nginx:1.27' && r.focus,
     `a row's settings dialog and what is typed in it outlive the row's redraw (${JSON.stringify(r)})`);
});

await section("a textarea, a box and a pick follow the same rule", async () => {
  await fresh('<textarea data-k="env">A=1</textarea><input type="checkbox" data-k="on"><select data-k="mode"><option value="a" selected>a</option><option value="b">b</option></select><i>1</i>');
  const r = await page.evaluate(() => {
    const el = document.querySelector('#r244'), t = el.querySelector('textarea'), c = el.querySelector('input'), s = el.querySelector('select');
    t.value = 'A=1\nB=2'; c.checked = true; s.value = 'b';
    patch(el, '<textarea data-k="env">A=1</textarea><input type="checkbox" data-k="on"><select data-k="mode"><option value="a" selected>a</option><option value="b">b</option></select><i>2</i>');
    const kept = { t: t.value, c: c.checked, s: s.value };
    patch(el, '<textarea data-k="env">A=9</textarea><input type="checkbox" data-k="on" checked><select data-k="mode"><option value="a">a</option><option value="b" selected>b</option></select><i>3</i>');
    const turned = { t: t.value, c: c.checked, s: s.value };
    patch(el, '<textarea data-k="env">A=1</textarea><input type="checkbox" data-k="on"><select data-k="mode"><option value="a" selected>a</option><option value="b">b</option></select><i>4</i>');
    return { kept, turned, reverted: { t: t.value, c: c.checked, s: s.value } };
  });
  ok(r.kept.t === 'A=1\nB=2' && r.kept.c && r.kept.s === 'b',
     `what the person typed, ticked and picked stays while the markup says what it said (${JSON.stringify(r.kept)})`);
  ok(r.turned.t === 'A=9' && r.turned.c && r.turned.s === 'b' && r.reverted.t === 'A=1' && !r.reverted.c && r.reverted.s === 'a',
     `...and what the markup changes, a Revert's included, is what they hold (${JSON.stringify([r.turned, r.reverted])})`);
});

await section("what the page adds to an element is not the markup's to take away", async () => {
  await fresh('<div class="field"><input type="text" data-k="name" value=""><button type="button" title="save what was changed">Save</button></div><b>1</b>');
  // The page's own: the password managers' ignore marks on a field, and a
  // title taken off and kept as the button's description (untitle).
  await page.waitForFunction(() => document.querySelector('#r244 input')?.hasAttribute('data-bwignore')
    && !document.querySelector('#r244 button').hasAttribute('title'), null, { timeout: 5000 }).catch(() => {});
  const r = await page.evaluate(() => {
    const el = document.querySelector('#r244'), f = el.querySelector('input'), btn = el.querySelector('button');
    f.focus(); f.value = 'typed';
    const before = { marks: f.hasAttribute('data-bwignore'), title: btn.hasAttribute('title'), said: btn.getAttribute('aria-description') };
    patch(el, '<div class="field"><input type="text" data-k="name" value=""><button type="button" title="save what was changed">Save</button></div><b>2</b>');
    return { before, kept: el.querySelector('input') === f, value: f.value, focus: document.activeElement === f,
             marks: f.hasAttribute('data-bwignore') && f.hasAttribute('data-1p-ignore'), title: btn.hasAttribute('title'),
             said: btn.getAttribute('aria-description') };
  });
  ok(r.before.marks && !r.before.title && r.kept && r.value === 'typed' && r.focus && r.marks && !r.title && r.said === 'save what was changed',
     `a field the page marked for password managers is still the same field, its marks kept, and a title it moved is not put back (${JSON.stringify(r)})`);
});

await section("a press's own state is the markup's again at the next draw", async () => {
  await fresh('<button type="button" data-k="abort">Abort</button><button type="button" data-k="measure">Measure now</button><i>1</i>');
  const r = await page.evaluate(() => {
    const el = document.querySelector('#r244'), [ab, me] = el.querySelectorAll('button');
    ab.disabled = true; ab.textContent = 'stopping';           // a press in flight
    busy(me, 'Asking');                                         // busy(): disabled, aria-busy, its dots
    patch(el, '<button type="button" data-k="abort">Abort</button><button type="button" data-k="measure">Measure now</button><i>2</i>');
    return { abort: [ab.isConnected, ab.disabled, ab.textContent], measure: [me.isConnected, me.disabled, me.getAttribute('aria-busy'), me.textContent, !!me.querySelector('.dots')] };
  });
  const back = await page.evaluate(async () => {
    const el = document.querySelector('#r244');
    el.innerHTML = ''; patch(el, '<button type="button" data-nd="gpu-apply">Apply</button><i>1</i>');
    const b = el.querySelector('button');
    // A redraw during the press draws the same button disabled (the job it
    // queued is running): the press's end leaves it so.
    await pressing(b, async () => { patch(el, '<button type="button" data-nd="gpu-apply" disabled>Applying…</button><i>2</i>'); });
    const same = { kept: el.querySelector('button') === b, after: b.disabled };
    // ...and one that draws another button in its place: a new element, so
    // the press's end writes nothing to it.
    patch(el, '<button type="button" data-nd="sync-clean">Clean up</button><i>3</i>');
    const c = el.querySelector('button');
    await pressing(c, async () => { patch(el, '<button type="button" data-nd="to-sync" disabled>Move to a synced copy</button><i>4</i>'); });
    const now = el.querySelector('button');
    return { same, other: { replaced: now !== c, nd: now.dataset.nd, disabled: now.disabled } };
  });
  ok(back.same.kept && back.same.after && back.other.replaced && back.other.nd === 'to-sync' && back.other.disabled,
     `...and a press that ends gives its button back as the markup has it now, and another action's button is never the pressed one renamed (${JSON.stringify(back)})`);
  ok(JSON.stringify(r.abort) === '[true,false,"Abort"]' && JSON.stringify(r.measure) === '[true,false,null,"Measure now",false]',
     `a button a press disabled, relabeled or marked busy is given back by the next draw, as a whole draw gave it back (${JSON.stringify(r)})`);
});

await section("what the page's code puts in stays when it says so, and nothing else does", async () => {
  await fresh('<div class="doctab"><details class="sect"><summary><span class="t">Images</span></summary><div class="box" data-own><i>reading…</i></div></details><span class="acts"><button type="button" data-nd="test">Test</button></span></div>');
  const r = await page.evaluate(() => {
    const el = document.querySelector('#r244'), tab = el.querySelector('.doctab'), sum = el.querySelector('summary'), box = el.querySelector('.box'), acts = el.querySelector('.acts');
    const nav = document.createElement('nav'); nav.className = 'sectjump'; nav.setAttribute('data-own', ''); tab.prepend(nav);          // a jump bar
    const st = document.createElement('span'); st.className = 'sst'; st.setAttribute('data-own', ''); sum.append(st); st.textContent = '3 images';
    box.innerHTML = '<div class="tiles">3 images</div>';                                                                                  // a fold's read
    acts.innerHTML = '<button type="button" data-nd="update-agent">Update agent</button><button type="button" data-nd="test">Test</button>'; // a part a press drew
    patch(el, '<div class="doctab"><details class="sect"><summary><span class="t">Images</span></summary><div class="box" data-own><i>reading…</i></div></details><span class="acts"><button type="button" data-nd="test">Test now</button></span></div>');
    return { nav: nav.isConnected && tab.firstChild === nav, sst: st.isConnected && st.textContent, read: box.textContent,
             acts: [...el.querySelectorAll('.acts button')].map(b => b.textContent).join('|') };
  });
  const swap = await page.evaluate(() => {
    const el = document.querySelector('#r244');
    el.innerHTML = ''; patch(el, '<div class="grow"><div class="actbar"><button type="button" data-nd="update-agent">Update agent</button></div><div class="ndtest" data-own hidden></div></div>');
    patch(el, '<div class="grow"><div class="ndtest" data-own hidden></div></div>');
    return { stale: !!el.querySelector('[data-nd="update-agent"]'), own: el.querySelectorAll('.ndtest').length };
  });
  ok(!swap.stale && swap.own === 1, `...and a box whose children are its code's is never another element turned into it, old children and all (${JSON.stringify(swap)})`);
  ok(r.nav && r.sst === '3 images' && r.read === '3 images' && r.acts === 'Test now',
     `a jump bar, a status and a fold's read the code marked as its own stay, and a part a press drew by hand follows the markup with nothing stale left (${JSON.stringify(r)})`);
});

await section("a style the markup changes is applied to the element it keeps", async () => {
  await fresh('<div class="dmgroup" data-style="box-shadow:inset 4px 0 0 rgb(47, 198, 255)"><b>ep.silon</b></div><i>1</i>');
  await page.waitForFunction(() => /47, 198, 255/.test(getComputedStyle(document.querySelector('#r244 .dmgroup')).boxShadow), null, { timeout: 5000 }).catch(() => {});
  const r = await page.evaluate(() => {
    const el = document.querySelector('#r244'), g = el.querySelector('.dmgroup');
    patch(el, '<div class="dmgroup" data-style="box-shadow:inset 4px 0 0 rgb(57, 181, 176)"><b>ep.silon</b></div><i>2</i>');
    const recolored = getComputedStyle(g).boxShadow;
    patch(el, '<div class="dmgroup"><b>ep.silon</b></div><i>3</i>');
    return { kept: el.querySelector('.dmgroup') === g, recolored, cleared: getComputedStyle(g).boxShadow };
  });
  ok(r.kept && /57, 181, 176/.test(r.recolored) && r.cleared === 'none',
     `a band given its space's color by the markup takes the new one, and none once the markup draws none (${JSON.stringify(r)})`);
});

await page.evaluate(() => document.querySelector('#r244')?.remove());
await done(browser);
