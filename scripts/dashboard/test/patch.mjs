// patch: a redraw that keeps what a person is doing. The new markup
// is patched into what is there: every element it can be matched to is kept
// and brought up to date, so typing, its caret and an IME composition, a fold
// turned and a dialog open outlive a redraw from the poll, and what the
// markup changes on purpose (a Revert, a draft drawn, a section opened by an
// address) still lands. Each rule is held on a scratch element of the real
// page, with markup written here.
import { URL, launch, newPage, ok, done, ready, section, ENGINE, skip } from './lib.mjs';

const browser = await launch();
const page = await newPage(browser, { viewport: { width: 1280, height: 900 } });
await page.goto(URL);
await ready(page);
// An IME composition is typed through Chromium's own Input protocol; in
// the other engines the field's focus, value and caret are held without it.
const cdp = ENGINE === 'chromium' ? await page.context().newCDPSession(page) : null;

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
  if (cdp) await cdp.send('Input.imeSetComposition', { text: 'か', selectionStart: 1, selectionEnd: 1 });
  else skip('a composition outlives a redraw', "an IME composition is typed through Chromium's Input protocol");
  const r = await page.evaluate(() => {
    const el = document.querySelector('#r244'), f = el.querySelector('input');
    let ended = 0; f.addEventListener('compositionend', () => ended++); f.addEventListener('blur', () => ended++);
    patch(el, '<div class="field"><input type="text" data-k="name" value="old"></div><span>4 running</span>');
    return { kept: el.querySelector('input') === f, focus: document.activeElement === f, value: f.value, caret: f.selectionStart,
             ended, text: el.querySelector('span').textContent };
  });
  if (cdp) await cdp.send('Input.insertText', { text: '' });
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

await section("a pick in a pulldown stays on its value when the list changes under it", async () => {
  const sel = opts => `<select data-ng="host">${opts.map(o => `<option value="${o}">${o}</option>`).join('')}</select><i>${opts.length}</i>`;
  await fresh(sel(['www.example.com', 'api.example.com']));
  const r = await page.evaluate(([two]) => {
    const el = document.querySelector('#r244'), s = el.querySelector('select');
    s.value = 'api.example.com';                                   // the person's pick
    patch(el, two);                                                 // a host added before it, under a redraw
    return { value: s.value, kept: el.querySelector('select') === s, options: [...s.options].map(o => o.value).join(',') };
  }, [sel(['www.example.com', 'two.example.com', 'api.example.com'])]);
  ok(r.kept && r.value === 'api.example.com' && r.options === 'www.example.com,two.example.com,api.example.com',
     `the option picked is still picked by its value, not whatever came to stand in its place (${JSON.stringify(r)})`);
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
    return { abort: [ab.isConnected, ab.disabled, ab.textContent], measure: [me.isConnected, me.disabled, me.getAttribute('aria-busy'), me.textContent, !!me.querySelector('.dots')],
             // ...its ring and the name it ran under with it (Measure now kept
             // its ring for good when only the attributes were given back).
             ring: [me.classList.contains('working'), me.classList.contains('ringrel'), me.getAttribute('aria-label'), me.dataset.busyRing ?? null, me.dataset.busyNamed ?? null] };
  });
  // A button no draw records (the top bar's doctor ↻), its press ended with
  // no word: its words are its own still, never emptied.
  const bare = await page.evaluate(() => {
    const b = document.createElement('button'); b.type = 'button'; b.textContent = '\u21bb';
    document.body.append(b);
    busy(b, 'Running'); unbusy(b);
    const out = { text: b.textContent, disabled: b.disabled, label: b.getAttribute('aria-label'), working: b.classList.contains('working') };
    b.remove();
    return out;
  });
  ok(bare.text === '\u21bb' && !bare.disabled && bare.label === null && !bare.working,
     `a press that ends with no word leaves its button's words as they were (${JSON.stringify(bare)})`);
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
  const label = await page.evaluate(() => {
    const el = document.querySelector('#r244');
    el.innerHTML = ''; patch(el, '<button type="button" data-menuopen><span class="name">master</span></button><i>1</i>');
    const b = el.querySelector('button'), word = b.textContent;
    busy(b, 'Creating');
    patch(el, '<button type="button" data-menuopen><span class="name">picked-new</span></button><i>2</i>');    // the reload the press brought
    b.innerHTML = 'Creating<span class="dots"></span>';                                                       // ...under a word still on it
    unbusy(b, word);                                                                                          // the press's end
    return { name: b.querySelector('.name')?.textContent, busy: b.getAttribute('aria-busy'), disabled: b.disabled };
  });
  ok(label.name === 'picked-new' && label.busy === null && !label.disabled,
     `...and a press that gives its button back gives it as the markup has it now, not the label kept from before the press (${JSON.stringify(label)})`);
  ok(back.same.kept && back.same.after && back.other.replaced && back.other.nd === 'to-sync' && back.other.disabled,
     `...and a press that ends gives its button back as the markup has it now, and another action's button is never the pressed one renamed (${JSON.stringify(back)})`);
  ok(JSON.stringify(r.abort) === '[true,false,"Abort"]' && JSON.stringify(r.measure) === '[true,false,null,"Measure now",false]'
     && JSON.stringify(r.ring) === '[false,false,null,null,null]',
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

await section("an open menu in the surface is kept open, and the draw lands", async () => {
  await fresh('<div class="pick"><button type="button" data-menuopen><span class="name">master</span></button><div class="actmenu" role="menu"><input type="search" id="r244find" value=""></div></div>');
  const r = await page.evaluate(() => {
    const el = document.querySelector('#r244'), menu = el.querySelector('.actmenu'), f = el.querySelector('#r244find');
    f.focus(); f.value = 'picked-new';
    const drew = patch(el, '<div class="pick"><button type="button" data-menuopen><span class="name">picked-new</span></button><div class="actmenu" role="menu"><input type="search" id="r244find" value=""></div></div>');
    return { drew, name: el.querySelector('.name').textContent, menuKept: el.querySelector('.actmenu') === menu && !menu.hidden, value: f.value, focus: document.activeElement === f };
  });
  ok(r.drew && r.name === 'picked-new' && r.menuKept && r.value === 'picked-new' && r.focus,
     `a draw into a surface with its menu open lands, the menu and what is typed in it kept (${JSON.stringify(r)})`);
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

await section("a box open on a card stays in its card while the cards move", async () => {
  // The Spaces grid's shape: cards keyed by their space, a rename's box
  // (askInline, the page's own) open on one of them, and the poll bringing
  // the cards back in another order with that card's words changed.
  const card = (k, name) => `<div class="pcard" data-pkey="${k}" data-key="${k}"><div class="pcname">${name}</div><div class="pcrepos">${k} repos</div></div>`;
  await fresh(`<div class="pgrid">${card('alpha', 'alpha')}${card('beta', 'beta')}</div>`);
  const r = await page.evaluate(([a2, b]) => {
    const el = document.querySelector('#r244'), a = el.querySelector('[data-key="alpha"]');
    askInline(a.querySelector('.pcname'), { label: 'Rename alpha to', value: 'alpha' });
    const box = a.querySelector('.askline'), inp = box?.querySelector('input');
    if (inp){ inp.focus(); inp.value = 'alpha-renamed'; }
    patch(el, `<div class="pgrid">${b}${a2}</div>`);
    const now = el.querySelector('[data-key="alpha"]');
    return { same: now === a, order: [...el.querySelectorAll('.pcard')].map(c => c.dataset.key).join(','), words: now.querySelector('.pcname').textContent,
             box: !!box && box.isConnected && box.closest('.pcard') === a, value: inp?.value, focus: document.activeElement === inp };
  }, [card('alpha', 'alpha, pinned'), card('beta', 'beta')]);
  ok(r.same && r.order === 'beta,alpha' && r.words === 'alpha, pinned' && r.box && r.value === 'alpha-renamed',
     `a card is kept by its key when the grid comes back in another order, and the box open on it stays there with what was typed (${JSON.stringify(r)})`);
  await page.evaluate(() => document.querySelectorAll('.askline').forEach(x => x.__done?.(null)));
});

await section("a copy fading out is never taken for the part it copies", async () => {
  // A press that draws a part again fades a copy of the old one out over it
  // (fadeThrough, chipMove); a poll landing meanwhile matches by key, and the
  // copy carries the key it was copied with.
  await fresh('<div class="list"><div class="row" data-key="r1">one</div><div class="row" data-key="r2">two</div></div>');
  const r = await page.evaluate(() => {
    const el = document.querySelector('#r244'), r1 = el.querySelector('[data-key="r1"]');
    ghostOut(ghostOf(r1), r1.parentNode);
    const ghost = el.querySelector('.fghost');
    patch(el, '<div class="list"><div class="row" data-key="r1">one, changed</div><div class="row" data-key="r2">two</div></div>');
    const rows = [...el.querySelectorAll('.row:not(.fghost)')];
    return { ghost: !!ghost, real: rows[0] === r1, words: r1.textContent, ghostWords: ghost?.textContent, rows: rows.length };
  });
  ok(r.ghost && r.real && r.words === 'one, changed' && r.ghostWords === 'one' && r.rows === 2,
     `the row is brought up to date and the copy fading over it is left to fade (${JSON.stringify(r)})`);
});

await section("the rail keeps the button pressed when the group on show moves", async () => {
  const r = await page.evaluate(() => new Promise(res => {
    const rail = document.getElementById('rail'), was = rail?.querySelector('.ritem.on')?.dataset.rail;
    const go = [...(rail?.querySelectorAll('[data-rail]') || [])].find(b => b.dataset.rail !== was);
    if (!go){ res({ none: true }); return; }
    const btns = [...rail.querySelectorAll('[data-rail]')];
    go.focus(); go.click();
    setTimeout(() => res({ to: go.dataset.rail, on: go.classList.contains('on'), focus: document.activeElement === go,
                            kept: btns.every(b => b.isConnected), back: was }), 600);
  }));
  ok(r.on && r.focus && r.kept, `a group pressed on the rail wears the mark on the same button, which keeps the keyboard's focus (${JSON.stringify(r)})`);
  if (r.back) await page.evaluate(k => railGo(k), r.back);
});

await section("rows that share a key are matched in their order", async () => {
  // Two files in the same state once drew the same key: the second old row
  // was taken for the first new one, its fold and its read with it.
  await fresh('<div class="list"><details class="gfile" data-key="m|1"><summary>a.txt</summary></details><details class="gfile" data-key="m|1"><summary>b.txt</summary></details></div>');
  const r = await page.evaluate(() => {
    const el = document.querySelector('#r244'), [a, b] = el.querySelectorAll('.gfile');
    a.open = true;
    patch(el, '<div class="list"><details class="gfile" data-key="m|1"><summary>a.txt, now</summary></details><details class="gfile" data-key="m|1"><summary>b.txt</summary></details></div>');
    const [a2, b2] = el.querySelectorAll('.gfile');
    return { first: a2 === a, second: b2 === b, open: [a2.open, b2.open], words: [a2.textContent, b2.textContent] };
  });
  ok(r.first && r.second && r.open[0] && !r.open[1] && r.words[0] === 'a.txt, now',
     `the first stays the first and the second the second, the fold turned on the first kept on it (${JSON.stringify(r)})`);
});

await section("the page's own bar at the top of a surface is not another writer's", async () => {
  // A section's jump bar is put before the first section, which in the Git
  // view is the surface's first child: read as another writer's, every draw
  // of the view was written whole, a message being typed with it.
  await fresh('<details class="sect" open><summary><span class="t">Changes</span></summary><textarea id="r244msg"></textarea></details><details class="sect"><summary><span class="t">History</span></summary><i>1</i></details>');
  const r = await page.evaluate(() => {
    const el = document.querySelector('#r244'), t = el.querySelector('#r244msg');
    const nav = document.createElement('nav'); nav.className = 'sectjump'; nav.setAttribute('data-own', ''); el.prepend(nav);
    t.focus(); t.value = 'typed';
    const same = patch(el, '<details class="sect" open><summary><span class="t">Changes</span></summary><textarea id="r244msg"></textarea></details><details class="sect"><summary><span class="t">History</span></summary><i>1</i></details>');
    patch(el, '<details class="sect" open><summary><span class="t">Changes</span></summary><textarea id="r244msg"></textarea></details><details class="sect"><summary><span class="t">History</span></summary><i>2</i></details>');
    return { same, kept: t.isConnected, focus: document.activeElement === t, value: t.value, nav: nav.isConnected && el.firstChild === nav, read: el.querySelector('i').textContent };
  });
  ok(!r.same && r.kept && r.focus && r.value === 'typed' && r.nav && r.read === '2',
     `the same markup is still no change with a jump bar put in at the top, and a change is patched around it, the typing kept (${JSON.stringify(r)})`);
});

await section("a part a press drew by hand keeps the style its data-style gave it", async () => {
  // The Design view draws a board again by its own hand when a color moves
  // (repaintBoard's outerHTML); the next patch read the applied style as an
  // attribute the markup no longer had, and took every block's place away.
  await fresh('<div class="page"><div class="board"><div class="blk" data-style="grid-column:1 / span 4">one</div></div></div><i>1</i>');
  const r = await page.evaluate(async () => {
    const el = document.querySelector('#r244');
    el.querySelector('.board').outerHTML = '<div class="board"><div class="blk" data-style="grid-column:2 / span 3">one</div></div>';
    drawn(el.querySelector('.board'));                                  // as repaintBoard does: what a draw brings, its data-style applied
    const blk = el.querySelector('.blk'), applied = blk.style.gridColumn;
    patch(el, '<div class="page"><div class="board"><div class="blk" data-style="grid-column:2 / span 3">one</div></div></div><i>2</i>');
    return { applied, kept: el.querySelector('.blk') === blk, after: blk.style.gridColumn, read: el.querySelector('i').textContent };
  });
  ok(r.applied === '2 / span 3' && r.kept && r.after === '2 / span 3' && r.read === '2',
     `its place stays when the surface around it is patched (${JSON.stringify(r)})`);
});

await section("what the code takes away for a role it gives back as the markup has it", async () => {
  // A role that may not release hides Release and deadens the fields; a
  // patch keeps what code did to an element, so the look after the role
  // changes gives back exactly what the markup draws: a press drawn dead
  // stays dead.
  await fresh('<div class="v"><button type="button" data-rel>Release</button><button type="button" data-save disabled>Save</button><input class="vstart" value="1.0"><i>1</i></div>');
  const r = await page.evaluate(() => {
    const el = document.querySelector('#r244'), rel = el.querySelector('[data-rel]'), save = el.querySelector('[data-save]'), inp = el.querySelector('.vstart');
    // A draw for the role that may not: patched, given back, taken away.
    const look = (n, may) => {
      patch(el, `<div class="v"><button type="button" data-rel>Release</button><button type="button" data-save disabled>Save</button><input class="vstart" value="1.0"><i>${n}</i></div>`);
      giveBack(el);
      if (!may){ takeAway(rel, true); takeAway(save, true); takeAway(inp); }
    };
    look(1, false); look(2, false);
    const held = { rel: rel.hidden, save: save.hidden, inp: inp.disabled, kept: el.querySelector('.vstart') === inp };
    // ...and one for a role that may.
    look(3, true);
    return { held, rel: [rel.hidden, rel.disabled], save: [save.hidden, save.disabled], inp: inp.disabled, marks: el.querySelectorAll('[data-taken]').length };
  });
  ok(r.held.rel && r.held.save && r.held.inp && r.held.kept && !r.rel[0] && !r.rel[1] && !r.save[0] && r.save[1] && !r.inp && r.marks === 0,
     `taken away by each draw for a role that does not give them, and given back as the markup draws them by the first that does (${JSON.stringify(r)})`);
});

// ---- what a press sends, what a page reads, what a draw brings ---------------

await section("a request that never lands answers in words, and so does one answered in other words", async () => {
  await page.route('**/api/r9-gone', r => r.abort('failed'));
  await page.route('**/api/r9-text', r => r.fulfill({ status: 502, contentType: 'text/html', body: '<h1>Bad Gateway</h1>' }));
  const r = await page.evaluate(async () => ({
    gone: await postJSON('/api/r9-gone', {}),
    read: await getJSON('/api/r9-gone'),
    text: await postJSON('/api/r9-text', {}),
  }));
  await page.unroute('**/api/r9-gone'); await page.unroute('**/api/r9-text');
  ok(r.gone.error === 'the controller did not answer' && r.gone.unreached && r.read.error === 'the controller did not answer'
     && /^the controller answered 502/.test(r.text.error) && !r.text.unreached,
     `postJSON and getJSON answer {error} in words, never throw, and say when nothing landed (${JSON.stringify(r)})`);
});

await section("a kind of read is one at a time: the last asked is made once more, in order, a failure its own asker's", async () => {
  const r = await page.evaluate(async () => {
    const seen = [], gates = [];
    const step = (name, fail) => async () => {
      seen.push('start ' + name);
      await new Promise(res => gates.push(res));
      seen.push('land ' + name);
      if (fail) throw new Error('r9 read failed');
    };
    const settled = {};
    const mark = (name, p) => p.then(() => { settled[name] = 'in after ' + seen.at(-1); }, e => { settled[name] = 'threw ' + e.message; });
    const rev0 = readRev('r9.test');
    const first = mark('first', reading('r9.test', step('a', true)));
    const second = mark('second', reading('r9.test', step('b')));   // asked while a is out
    const third = mark('third', reading('r9.test', step('c')));     // asked again: replaces b
    gates.shift()();                                         // a lands (and throws)
    await new Promise(res => setTimeout(res, 20));
    const busy = readBusy('r9.test'), early = {...settled};
    gates.shift()();                                         // c lands
    await Promise.all([first, second, third]);
    return { seen, busy, early, settled, after: readBusy('r9.test'), revs: readRev('r9.test') - rev0 };
  });
  ok(JSON.stringify(r.seen) === JSON.stringify(['start a', 'land a', 'start c', 'land c']) && r.busy && !r.after && r.revs === 2,
     `two asks while a read is out make one more read, the newest, after it lands, a failure still letting it be made (${JSON.stringify(r.seen)})`);
  ok(r.early.first === 'threw r9 read failed' && !r.early.second && !r.early.third
     && r.settled.second === 'in after land c' && r.settled.third === 'in after land c',
     `...the first ask is answered by its own read, its failure with it, and the two after it by the read made for them (${JSON.stringify(r.early)} ${JSON.stringify(r.settled)})`);
});

// What held a page on its shapes on a controller whose reads take seconds:
// every ask was handed the whole chain, and a kind asked again before each
// read was in never let its first caller go.
await section("an ask is not held by the asks after it", async () => {
  const r = await page.evaluate(async () => {
    const gates = [];
    const step = () => async () => { await new Promise(res => gates.push(res)); };
    let mineIn = false;
    reading('r9.chain', step()).then(() => { mineIn = true; });    // mine, out now
    reading('r9.chain', step());                                   // asked meanwhile
    gates.shift()();                                               // mine lands
    await new Promise(res => setTimeout(res, 20));
    const afterMine = mineIn;
    reading('r9.chain', step());                                   // asked again while the next is out
    gates.shift()(); await new Promise(res => setTimeout(res, 20));
    gates.shift()(); await new Promise(res => setTimeout(res, 20));
    return { afterMine, busy: readBusy('r9.chain') };
  });
  ok(r.afterMine && !r.busy, `the first caller is answered when its own read lands, with more asked behind it (${JSON.stringify(r)})`);
});

await section("an answer a newer ask has overtaken may be left unlanded, never two in a row", async () => {
  const r = await page.evaluate(async () => {
    const landed = [], gates = [];
    const step = name => async overtaken => {
      await new Promise(res => gates.push(res));
      if (overtaken()) return false;
      landed.push(name);
    };
    const rev0 = readRev('r9.skip');
    let aIn = '';
    const p = reading('r9.skip', step('a')).then(() => { aIn = landed.join(','); });
    reading('r9.skip', step('b'));                          // overtakes a
    gates.shift()();                                        // a lands: skipped
    await new Promise(res => setTimeout(res, 20));
    const c = reading('r9.skip', step('c'));                // overtakes b
    gates.shift()();                                        // b lands: landed anyway, a was skipped
    await new Promise(res => setTimeout(res, 20));
    gates.shift()();                                        // c lands
    await Promise.all([p, c]);
    return { landed, aIn, revs: readRev('r9.skip') - rev0 };
  });
  ok(JSON.stringify(r.landed) === JSON.stringify(['b', 'c']) && r.revs === 2 && r.aIn === 'b',
     `an overtaken answer is skipped, the one after it lands though it is overtaken too, only landings move the revision, and whoever asked for the skipped one is answered by the next (${JSON.stringify(r)})`);
});

await section("a press's ring is its own work, and a read the page makes after it holds no button", async () => {
  await page.route('**/api/r9-slow', async r => { await new Promise(res => setTimeout(res, 900)); await r.fulfill({ status: 200, contentType: 'application/json', body: '{}' }); });
  const r = await page.evaluate(async () => {
    const host = document.createElement('div');
    host.id = 'r9ring'; host.style.cssText = 'position:fixed;left:300px;top:300px;width:420px;display:flex;gap:6px;z-index:99';
    document.body.append(host);
    patch(host, '<button type="button" id="r9a">Send it</button><button type="button" id="r9b">Read it</button>');
    const a = host.querySelector('#r9a'), b = host.querySelector('#r9b');
    a.onclick = async () => { await new Promise(res => setTimeout(res, 50)); await postJSON('/api/r9-slow', {}); };
    const gotBack = a.onclick;
    a.click();
    const late = getJSON('/api/r9-slow');                   // the page's own read, after the click
    await new Promise(res => setTimeout(res, 500));
    const held = { a: a.classList.contains('working'), b: b.classList.contains('working') };
    await late; await new Promise(res => setTimeout(res, 700));
    const after = a.classList.contains('working');
    host.remove();
    return { held, after, own: typeof gotBack === 'function' && !/pressRun/.test(String(gotBack)) };
  });
  await page.unroute('**/api/r9-slow');
  ok(r.held.a && !r.held.b && !r.after && r.own,
     `the pressed button wears its ring through what its handler awaits, a later read holds no button, and the handler read back is the one set (${JSON.stringify(r)})`);
});

await section("what a draw brings is the draw's own, at once", async () => {
  const r = await page.evaluate(() => {
    const el = document.createElement('div'); el.id = 'r9drawn'; document.body.append(el);
    drawHTML(el, '<span data-style="color:rgb(1, 2, 3)" title="said">x</span><textarea class="proseline">one line</textarea><input type="text" id="r9f">');
    const sp = el.querySelector('span'), t = el.querySelector('textarea'), f = el.querySelector('input');
    const out = { color: sp.style.color, title: sp.getAttribute('title'), said: sp.getAttribute('aria-description') || sp.getAttribute('aria-label'),
                  prose: t.dataset.prose === '1', fitted: t.style.height !== '', quiet: f.hasAttribute('data-bwignore') };
    patch(el, '<span data-style="color:rgb(1, 2, 3)" title="said">x</span><textarea class="proseline">one line</textarea><input type="text" id="r9f"><b title="new words">y</b>');
    out.later = el.querySelector('b').getAttribute('aria-description') || el.querySelector('b').getAttribute('aria-label');
    el.remove();
    return out;
  });
  ok(r.color === 'rgb(1, 2, 3)' && r.title === null && r.said === 'said' && r.prose && r.fitted && r.quiet && r.later === 'new words',
     `a draw applies data-style, wires and fits a proseline, quiets a field and turns a title into words before it returns, and a patch does the same for what it adds (${JSON.stringify(r)})`);
});

await page.evaluate(() => document.querySelector('#r244')?.remove());
await done(browser);
