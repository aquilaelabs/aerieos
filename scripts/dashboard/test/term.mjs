// AerieOS's own terminal (R133): a shell tab is drawn by xterm.js in the
// page and joined to /termws, which runs bb-tty in a pty on this
// controller. What is typed reaches the shell and what it prints reaches
// the screen; the screen fits its box and the pty follows; a terminal that
// ends says why under it, and Reconnect opens it again on the same tmux
// session; a tab popped out opens the same terminal on a page of its own
// (terminal.html); a closed tab's socket goes with it. Driven through the
// page, as a person at the dock would.
import { launch, newPage, ok, done, ready, finger, until, quiet, URL, DIR, member, projectKey, OWNER, section, ENGINE, skip } from './lib.mjs';
import { appendFileSync, mkdirSync, readFileSync } from 'node:fs';
import { execFileSync } from 'node:child_process';

const browser = await launch();
const page = await newPage(browser, { viewport: { width: 1280, height: 800 } });
await page.goto(URL);
await ready(page);

// One shell, in the dock.
const id = await page.evaluate(() => { openTab({kind: 'term', arg: 'sh:7:alpha', label: 'own'});
                                       return tabs.find(t => t.arg === 'sh:7:alpha').id; });
await page.evaluate(id => { panes[1] = id; dockUp = true; render(); }, id);
await page.waitForFunction(() => document.querySelector('#pane1 .slot.on.ownterm .xterm'), null, { timeout: 20000 });
ok(await page.evaluate(() => !document.querySelector('#pane1 .slot.on iframe')),
   'the shell tab is drawn by xterm in the page, with no frame');

// What the screen shows, read off xterm's own buffer.
const screen = () => page.evaluate(() => {
  const rec = [...TERMS.values()].find(r => r.el.isConnected && r.term);
  if (!rec) return '';
  const b = rec.term.buffer.active, out = [];
  for (let i = 0; i < b.length; i++) out.push(b.getLine(i)?.translateToString(true) || '');
  return out.join('\n');
});
const waitFor = (re, ms = 20000) => until(async () => re.test(await screen()), ms, 200);

// The text is inset from the pane's edges, and the rows still fit: the
// last row's bottom inside the box.
const inset = await page.evaluate(() => {
  const host = document.querySelector('#pane1 .slot.on .xhost'), x = host.querySelector('.xterm-screen');
  const h = host.getBoundingClientRect(), r = x.getBoundingClientRect();
  return { left: Math.round(r.left - h.left), top: Math.round(r.top - h.top), fits: r.bottom <= h.bottom + 0.5 };
});
ok(inset.left >= 8 && inset.top >= 8 && inset.fits, `the text sits off the pane's edges and fits in it (${JSON.stringify(inset)})`);

// Typing goes down the socket to the shell; its answer comes back up.
await page.click('#pane1 .slot.on .xterm');
await page.keyboard.type('echo own-$((40+2))-terminal\n');
ok(await waitFor(/own-42-terminal/), 'what is typed reaches the shell, and what it prints reaches the screen');

// The pty is the size of the box: stty in tmux's pane says what xterm
// fitted, a row short for tmux's status line.
const dims = await page.evaluate(() => { const r = [...TERMS.values()].find(r => r.term); return [r.term.rows, r.term.cols]; });
await page.keyboard.type('stty size\n');
ok(await waitFor(new RegExp(`\\b(${dims[0]}|${dims[0] - 1}) ${dims[1]}\\b`)), `the pty is the size xterm fitted to its box (${dims.join(' ')})`);

// Ended from inside: the line under it says so, and Reconnect attaches the
// same tmux session again.
await page.keyboard.type('tmux detach\n');
await page.waitForFunction(() => !document.querySelector('#pane1 .slot.on .xend')?.hidden, null, { timeout: 20000 });
const why = await page.$eval('#pane1 .slot.on .xwhy', e => e.textContent);
ok(/ended/.test(why), `a terminal that ends says so under the screen (${why})`);
await page.click('#pane1 .slot.on .xagain');
await page.waitForFunction(() => document.querySelector('#pane1 .slot.on .xend')?.hidden, null, { timeout: 20000 });
ok(await waitFor(/own-42-terminal/), '...and Reconnect attaches the same session, its screen as it was');

// The keys bar types down the same socket (step 5): a line typed, then the
// bar's Enter, runs it; nothing went by the server's tmux.
const keysAsked = [];
page.on('request', r => { if (r.url().includes('/api/keys')) keysAsked.push(r.url()); });
await page.click('#pane1 .slot.on .xterm');
await page.keyboard.type('echo kb-$((6*7))');
await page.evaluate(() => { active = 1; return sendKey('enter'); });
ok(await waitFor(/kb-42/) && !keysAsked.length, `the keys bar's Enter goes down the terminal's own socket (${keysAsked.length} asked of the server)`);

// The look is the person's (step 10): their Profile's size, cursor and
// colors reach the open terminal; a project's colors in their own settings
// for it win there.
await section("The look is the person's", async () => {
  const opts = () => page.evaluate(() => { const r = [...TERMS.values()].find(r => r.t.arg === 'sh:7:alpha' && r.term);
    return { size: r.term.options.fontSize, cursor: r.term.options.cursorStyle, bg: r.term.options.theme.background }; });
  const own = async prefs => page.evaluate(async prefs => {
    const r = await (await fetch('/api/users', { method: 'POST', headers: { 'Content-Type': 'application/json' }, body: JSON.stringify({ action: 'prefs', prefs }) })).json();
    await refresh();
    return { r, look: state.term_look };
  }, prefs);
  const saved = await own({ term: { size: 16, cursor: 'bar', blink: false, scheme: 'light' } });
  await page.waitForFunction(() => [...TERMS.values()].some(r => r.t.arg === 'sh:7:alpha' && r.term?.options.fontSize === 16), null, { timeout: 10000 }).catch(() => {});
  const mine = await opts();
  // ...and the room around the text wears the terminal's own color.
  const pad = await page.evaluate(() => getComputedStyle(document.querySelector('#pane1 .slot.on.ownterm')).backgroundColor);
  const said = await page.evaluate(async () => (await fetch('/api/prefs', { method: 'POST', headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({ project: 'alpha', term_scheme: 'red' }) })).status);
  await page.evaluate(() => refresh());
  // Time in which the space's color would have reached the terminal.
  await quiet(1500);
  const there = await opts();
  const padThere = await page.evaluate(() => getComputedStyle(document.querySelector('#pane1 .slot.on.ownterm')).backgroundColor);
  // A space has no colors of its own now (R223): Profile's are every space's.
  ok(pad === 'rgb(250, 250, 250)' && padThere === pad,
     `the room around the text wears the terminal's color, Profile's in every space (${pad} then ${padThere})`);
  ok(mine.size === 16 && mine.cursor === 'bar' && mine.bg === '#fafafa' && there.bg === '#fafafa' && there.size === 16,
     `a terminal takes its person's look from Profile, whatever a space once said (${JSON.stringify(mine)} then ${JSON.stringify(there)}; ${said})`);
  await page.evaluate(async () => fetch('/api/prefs', { method: 'POST', headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({ project: 'alpha', term_scheme: '' }) }));
});

// On a phone (step 11): a finger dragged down scrolls back through a
// shell's history, by the line, in tmux's copy mode; a press held on a word
// selects it, with grips and Copy; Copy puts it on the clipboard.
// Its drags are real touch through Chromium's gesture recognizer (finger):
// said skipped in the other engines (R263 step 6).
if (ENGINE !== 'chromium') skip('On a phone (step 11)', "its drags are a real touch through Chromium's gesture recognizer");
else await section("On a phone (step 11)", async () => {
  const phone = await newPage(browser, { viewport: { width: 393, height: 800 }, hasTouch: true, isMobile: true });
  await phone.goto(URL);
  await ready(phone);
  await phone.context().grantPermissions(['clipboard-read', 'clipboard-write'], { origin: new globalThis.URL(URL).origin });
  await phone.evaluate(() => { openTab({kind: 'term', arg: 'sh:9:alpha', label: 'thumb'});
    panes[1] = tabs.find(t => t.arg === 'sh:9:alpha').id; dockUp = true; render(); });
  await phone.waitForFunction(() => document.querySelector('#pane1 .slot.on.ownterm .xterm-screen'), null, { timeout: 20000 });
  const shown = () => phone.evaluate(() => {
    const r = [...TERMS.values()].find(r => r.t.arg === 'sh:9:alpha' && r.term), b = r.term.buffer.active, out = [];
    for (let i = 0; i < r.term.rows; i++) out.push(b.getLine(b.viewportY + i)?.translateToString(true) || '');
    return out;
  });
  const until = async (fn, ms = 15000) => { const end = Date.now() + ms;
    while (Date.now() < end){ const got = fn(await shown()); if (got) return got; await new Promise(r => setTimeout(r, 200)); }
    return null; };
  await phone.evaluate(() => { const r = [...TERMS.values()].find(r => r.t.arg === 'sh:9:alpha'); r.term.focus(); });
  // The shell's prompt first: typed before the new shell is up, the line
  // went nowhere and every check after it read an empty screen (B328).
  await until(rows => rows.some(l => /[$#] *$/.test(l)), 20000);
  let typed = null;
  for (let i = 0; i < 3 && !typed; i++){
    await phone.keyboard.type('seq 1 300; echo pick-me-word\n');
    typed = await until(rows => rows.some(l => /^pick-me-word/.test(l)), 8000);
  }
  ok(typed, 'the phone\'s shell runs what is typed into it');
  // The scroll goes down the terminal's own socket, tmux's keys for it
  // (lib/tmux-keys.conf), and the server is asked nothing.
  const asked = [];
  phone.on('request', r => { if (r.url().includes('/api/keys')) asked.push(r.postData() || ''); });
  const box = await phone.$eval('#pane1 .slot.on .xterm-screen', e => { const b = e.getBoundingClientRect(); return { x: b.left + b.width / 2, top: b.top + 20, h: b.height }; });
  // Under a full run's load one drag's lines did not always reach the
  // screen in time (B328): a second drag, said in the result.
  const scrolled = rows => rows.some(l => /\[\d+\/\d+\]/.test(l)) && !rows.some(l => /^pick-me-word/.test(l)) && rows;
  await finger(phone, box.x, box.top, box.x, box.top + box.h * 0.6);
  let back = await until(scrolled, 5000), drags = 1;
  if (!back){ await finger(phone, box.x, box.top, box.x, box.top + box.h * 0.6); drags = 2; back = await until(scrolled); }
  if (!back) console.log('the screen then:', JSON.stringify((await shown()).slice(-8)));
  ok(back && asked.length === 0,
     `a finger dragged down scrolls a shell back into its history, down its own socket (${drags} drag${drags === 1 ? '' : 's'}, ${asked.length} asked of the server)`);
  // Up again, past the bottom: copy mode ends by itself.
  await finger(phone, box.x, box.top + box.h * 0.9, box.x, box.top);
  await finger(phone, box.x, box.top + box.h * 0.9, box.x, box.top);
  const home = await until(rows => !rows.some(l => /\[\d+\/\d+\]/.test(l)) && rows.some(l => /^pick-me-word/.test(l)));
  ok(home, 'a finger dragged up brings it back to the newest, out of copy mode');
  // The word, found on the screen, pressed and held.
  const at = await phone.evaluate(() => {
    const r = [...TERMS.values()].find(r => r.t.arg === 'sh:9:alpha'), b = r.term.buffer.active;
    for (let i = 0; i < r.term.rows; i++){
      const l = b.getLine(b.viewportY + i)?.translateToString(true) || '';
      if (/^pick-me-word/.test(l)){ const c = termCell(r); return { x: c.b.left + 4.5 * c.w, y: c.b.top + (i + 0.5) * c.h }; }
    }
    return null;
  });
  if (at) await finger(phone, at.x, at.y, at.x, at.y, 800);
  await phone.waitForFunction(() => [...TERMS.values()].find(r => r.t.arg === 'sh:9:alpha')?.term.getSelection() === 'pick-me-word'
    && document.querySelectorAll('#pane1 .slot.on .xsel .xgrip').length === 2 && !!document.querySelector('#pane1 .slot.on .xsel .xcopy'),
    null, { timeout: 10000 }).catch(() => {});
  const picked = await phone.evaluate(() => ({ sel: [...TERMS.values()].find(r => r.t.arg === 'sh:9:alpha').term.getSelection(),
    grips: document.querySelectorAll('#pane1 .slot.on .xsel .xgrip').length, copy: !!document.querySelector('#pane1 .slot.on .xsel .xcopy') }));
  ok(at && picked.sel === 'pick-me-word' && picked.grips === 2 && picked.copy,
     `a press held on a word selects it, with a grip at each end and Copy (${JSON.stringify(picked)})`);
  await phone.click('#pane1 .slot.on .xsel .xcopy').catch(() => {});
  const clip = await phone.evaluate(() => navigator.clipboard.readText().catch(e => 'unread: ' + e.message));
  const gone = await phone.evaluate(() => !document.querySelector('#pane1 .slot.on .xsel'));
  ok(clip === 'pick-me-word' && gone, `Copy puts the word on the clipboard and puts the selection away (${clip})`);
  await phone.evaluate(() => dropTab(tabs.find(t => t.arg === 'sh:9:alpha').id));
  await phone.close();
});

// Popped out (R8): the same terminal on a page of its own, terminal.html on
// /termws, the tmux session the tab had; Reattach brings it back.
await section("Popped out (R8)", async () => {
  const [win] = await Promise.all([page.waitForEvent('popup'), page.evaluate(id => popOut(id), id)]);
  await win.waitForSelector('.xterm', { timeout: 20000 });
  // Its socket open and the session's screen drawn: a key typed before
  // the socket opens goes nowhere.
  await win.waitForFunction(() => ws?.readyState === WebSocket.OPEN
    && /\S/.test(document.querySelector('.xterm-rows')?.textContent || ''), null, { timeout: 20000 }).catch(() => {});
  await win.keyboard.type('echo popped-$((7*6))');
  await win.keyboard.press('Enter');
  const seen = await win.waitForFunction(() => /popped-42/.test(document.querySelector('.xterm-rows')?.textContent || ''),
                                         null, { timeout: 10000 }).then(() => true, () => false);
  ok(/\/terminal\?arg=sh%3A7%3Aalpha/.test(win.url()) && seen
     && await page.evaluate(() => !!document.querySelector('#pane1 .slot.on.popped')),
     `a tab popped out opens AerieOS's terminal on a page of its own, typed into like the tab (${win.url().replace(/^https?:\/\/[^/]+/, '')})`);
  await page.evaluate(id => reattachTab(id), id);
  await page.waitForSelector('#pane1 .slot.on.ownterm .xterm', { timeout: 20000 });
  ok(win.isClosed() || await win.evaluate(() => true).catch(() => true), '...and Reattach brings it back into the dock');
});

// The socket and the shell are one: closing the tab closes the socket.
const before = await page.evaluate(() => [...TERMS.values()].filter(r => r.t.arg === 'sh:7:alpha').length);
await page.evaluate(id => dropTab(id), id);
await page.waitForFunction(() => ![...TERMS.values()].some(r => r.t.arg === 'sh:7:alpha'), null, { timeout: 10000 }).catch(() => {});
const after = await page.evaluate(() => [...TERMS.values()].filter(r => r.t.arg === 'sh:7:alpha').map(r => r.key));
ok(before === 1 && after.length === 0, `closing the tab closes its terminal (${before}: ${JSON.stringify(after)})`);

// A log in the dock (R133 step 12): the page's own terminal, read-only, following the controller's log as it is written.
await section("A log in the dock", async () => {
  mkdirSync(`${DIR}/state/logs`, { recursive: true });
  appendFileSync(`${DIR}/state/logs/builderbot.log`, 'log-follow-first\n');
  await page.evaluate(() => openLogTab('log:controller', 'Log: the controller'));
  await page.waitForSelector('#pane1 .slot.on.ownterm .xterm', { timeout: 20000 }).catch(() => {});
  const logText = () => page.evaluate(() => { const r = [...TERMS.values()].find(r => r.t.arg === 'log:controller' && r.term);
    if (!r) return ''; const b = r.term.buffer.active, out = [];
    for (let i = 0; i < b.length; i++) out.push(b.getLine(i)?.translateToString(true) || ''); return out.join('\n'); });
  const seen = re => until(async () => re.test(await logText()), 10000, 250);
  const first = await seen(/log-follow-first/);
  appendFileSync(`${DIR}/state/logs/builderbot.log`, 'log-follow-second\n');
  const second = await seen(/log-follow-second/);
  const ro = await page.evaluate(() => [...TERMS.values()].find(r => r.t.arg === 'log:controller')?.term?.options.disableStdin === true);
  ok(first && second && ro, `the controller's log opens in the dock, read-only, and follows what is written to it (${first} ${second} ${ro})`);
  await page.evaluate(() => dropTab(tabs.find(t => t.arg === 'log:controller').id));
  // A kind it has no reader for ends at once, saying so.
  await page.evaluate(() => openLogTab('log:nothing', 'Log: nothing'));
  await page.waitForFunction(() => [...TERMS.values()].some(r => r.t.arg === 'log:nothing' && r.ended), null, { timeout: 15000 }).catch(() => {});
  const why = await page.evaluate(() => [...TERMS.values()].find(r => r.t.arg === 'log:nothing')?.ended || '');
  ok(/no log of the kind nothing/.test(why), `a log it has no reader for ends saying so (${why})`);
  await page.evaluate(() => dropTab(tabs.find(t => t.arg === 'log:nothing').id));
  // A container's log is decided as its row's Log is, and says why it is
  // refused: one of no instance on record here.
  await page.evaluate(() => openLogTab('log:ctr:alpha:nosuch:alpha-web-1', 'Log: alpha-web-1'));
  await page.waitForFunction(() => [...TERMS.values()].some(r => r.t.arg.startsWith('log:ctr:') && r.ended), null, { timeout: 15000 }).catch(() => {});
  const cwhy = await page.evaluate(() => [...TERMS.values()].find(r => r.t.arg.startsWith('log:ctr:'))?.ended || '');
  ok(/no instance nosuch of alpha on record here/.test(cwhy), `a container's log names why it cannot be followed (${cwhy})`);
  await page.evaluate(() => dropTab(tabs.find(t => t.arg.startsWith('log:ctr:')).id));
  // Any container's log, running or not and nobody's too, is read by the
  // controller as the Containers page reads it (log:dm:NODE:CONTAINER).
  await page.evaluate(() => openLogTab('log:dm::someone-elses', 'Log: someone-elses'));
  const dm = await (await page.waitForFunction(() => {
    const r = [...TERMS.values()].find(x => x.t.arg === 'log:dm::someone-elses'); if (!r) return null;
    const b = r.term?.buffer.active; let text = '';
    for (let i = 0; b && i < b.length; i++) text += b.getLine(i)?.translateToString(true) || '';
    return text.trim() || r.ended ? { text: text.trim().slice(0, 60), ended: r.ended || '' } : null;
  }, null, { timeout: 15000 })).jsonValue();
  ok(dm.text && !dm.ended, `a container nobody here started has its log read into a dock tab (${JSON.stringify(dm)})`);
  await page.evaluate(() => dropTab(tabs.find(t => t.arg === 'log:dm::someone-elses').id));
  await page.evaluate(() => openLogTab('log:dm::bad name', 'Log: bad'));
  await page.waitForFunction(() => [...TERMS.values()].some(r => r.t.arg === 'log:dm::bad name' && r.ended), null, { timeout: 15000 }).catch(() => {});
  ok(/no such container/.test(await page.evaluate(() => [...TERMS.values()].find(r => r.t.arg === 'log:dm::bad name')?.ended || '')),
     '...and a name that is no container is refused, saying so');
  await page.evaluate(() => dropTab(tabs.find(t => t.arg === 'log:dm::bad name').id));
});

// A shell on this controller is an administrator's (B1166, the operator, 25
// Nov): it runs as the dashboard's own account, so an account with Terminal
// Write on a space with no node is told the shell opens on a node; and a
// terminal is its account's alone (R133 step 8): an administrator naming the
// owner's account on the argument opens one of their own, never the owner's
// session, whose screen holds what the owner typed above. (A grant taken
// away ends a terminal it opened, R133 step 9: now a node's shell's, which
// this fixture's nodes do not serve.)
await section("A shell on this controller is an administrator's, and opens as one's own account", async () => {
  const h = OWNER;
  const base = URL.replace(/\/$/, '');
  const account = async (name, role, roles) => {
    await fetch(`${base}/api/users`, { method: 'POST', headers: h,
      body: JSON.stringify({ action: 'add', name, password: `${name}-pass-1`, role }) });
    await member(name);
    if (roles) await fetch(`${base}/api/roles`, { method: 'POST', headers: h,
      body: JSON.stringify({ action: 'assign', name, project_roles: { [projectKey('alpha')]: roles } }) });
    // A shell is refused an account with no author for its commits.
    await fetch(`${base}/api/users`, { method: 'POST', headers: h,
      body: JSON.stringify({ action: 'edit', name, profile: { full_name: name, email: `${name}@example.invalid` } }) });
    await fetch(`${base}/api/users`, { method: 'POST', headers: h,
      body: JSON.stringify({ action: 'edit', name, projects: [projectKey('alpha')] }) });
    // The header sent up front, as lib's pages send theirs: a websocket's
    // handshake carries no credentials the browser was only asked for.
    const ctx = await browser.newContext({ extraHTTPHeaders: { Authorization: 'Basic ' + Buffer.from(`${name}:${name}-pass-1`).toString('base64') } });
    const p = await ctx.newPage();
    await p.goto(URL);
    return { ctx, p };
  };
  const open = (p, arg) => p.evaluate(arg => new Promise(res => {
    const ws = new WebSocket(location.origin.replace(/^http/, 'ws') + '/termws?arg=' + encodeURIComponent(arg) + '&cols=80&rows=20');
    ws.binaryType = 'arraybuffer';
    let seen = '', closed = null;
    ws.onmessage = e => { seen += new TextDecoder().decode(e.data instanceof ArrayBuffer ? e.data : new Uint8Array()); };
    ws.onclose = e => { closed = { code: e.code, reason: e.reason }; };
    setTimeout(() => { try { ws.close(); } catch {} res({ seen, closed }); }, 4000);
  }), arg);
  // ...with a role on alpha that would open a shell there, were it a node's.
  await fetch(`${base}/api/roles`, { method: 'POST', headers: h, body: JSON.stringify({ action: 'set', name: 'termer', scope: 'projects',
    perms: { projects: 'write', terminal: 'write' }, note: 'a suite\'s shell' }) });
  const plain = await account('w.term', 'user', ['termer']);
  const refused = await open(plain.p, 'sh:8:alpha');
  await plain.ctx.close();
  ok(/administrator's/.test(refused.closed?.reason || refused.seen) && /node/.test(refused.closed?.reason || refused.seen),
     `a shell on this controller is refused an account that is not an administrator, saying it opens on a node (${JSON.stringify(refused.closed)})`);
  const admin = await account('w.admin', 'admin');
  const ownerUid = JSON.parse(readFileSync(`${DIR}/state/users.json`, 'utf8')).users.test.uid;
  const forged = await open(admin.p, `u:${ownerUid}:sh:7:alpha`);
  await admin.ctx.close();
  const adminUid = JSON.parse(readFileSync(`${DIR}/state/users.json`, 'utf8')).users['w.admin'].uid;
  let sessions = '';
  await until(() => {
    try { sessions = execFileSync('tmux', ['list-sessions', '-F', '#{session_name}'], { encoding: 'utf8' }); } catch { sessions = ''; }
    return sessions.split('\n').includes(`${adminUid}~shell-alpha-7`);
  });
  ok(!/own-42-terminal/.test(forged.seen) && sessions.split('\n').includes(`${adminUid}~shell-alpha-7`),
     `naming another account on a terminal's argument opens one of your own, never theirs (${forged.seen.replace(/\x1b\[[0-9;?]*[a-zA-Z]/g, '').replace(/\s+/g, ' ').trim().slice(-60)})`);
});

// A terminal closed while a frame of its own is still pending (B802): xterm
// runs the frame after dispose() and reads a renderer that is gone, which
// the console showed as "reading 'dimensions'" whenever a terminal's start
// was a little slow and it was closed at once. Terminals made as termMount
// makes them and dropped by termDrop at a few delays; disposed at once, 18
// of 60 threw.
await section("A terminal closed while a frame of its own is still pending", async () => {
  const before = page.errors.length;
  await page.evaluate(async () => {
    await xtermReady();
    const wait = ms => new Promise(r => setTimeout(r, ms));
    for (let i = 0; i < 60; i++){
      const el = document.createElement('div');
      el.style.cssText = 'position:fixed;left:0;top:0;width:600px;height:300px';
      document.body.append(el);
      const term = new window.Terminal({ scrollback: 5000 });
      const fit = new window.FitAddon.FitAddon();
      term.loadAddon(fit);
      term.open(el);
      try { fit.fit(); } catch (e) { /* a box with no size yet */ }
      term.write('line\r\n'.repeat(1 + i % 40));
      const key = `b802-${i}`;
      TERMS.set(key, { key, el, term, fit, ws: null, ro: null });
      const d = [0, 0, 1, 4, 8, 16, 30][i % 7];
      if (d) await wait(d);
      // Its slot goes before it or after it, as a closed tab's and a redrawn pane's do.
      if (i % 2) el.remove();
      termDrop(key);
      if (!(i % 2)) el.remove();
    }
    await wait(1300);
  });
  const thrown = [...new Set(page.errors.slice(before))];
  ok(thrown.length === 0 && await page.evaluate(() => ![...TERMS.keys()].some(k => k.startsWith('b802-'))),
     `a terminal closed with a frame of its own still pending throws nothing${thrown.length ? ': ' + thrown.join(' | ').slice(0, 200) : ''}`);
});

// A terminal not on show writes nothing until it is shown (R228 step 14),
// but answers a question as it comes: tmux asks who the terminal is as it
// attaches, and an answer held until the tab was shown reached it after it
// had stopped waiting and was typed into the shell as "1;2c0;276;0c".
await section("A terminal not on show holds its output and answers its questions at once", async () => {
  const got = await page.evaluate(async () => {
    await xtermReady();
    const el = document.createElement('div');
    el.style.cssText = 'position:fixed;left:0;top:0;width:600px;height:300px';
    document.body.append(el);
    const term = new window.Terminal({ scrollback: 100 });
    term.open(el);
    const answered = [];
    term.onData(d => answered.push(d));
    const rec = { term, el };
    const enc = s => new TextEncoder().encode(s);
    const text = () => { const b = term.buffer.active; const out = [];
      for (let i = 0; i < b.length; i++) out.push(b.getLine(i)?.translateToString(true) || ''); return out.join('|'); };
    const settle = () => new Promise(r => term.write('', r));
    termShow(rec, false);
    termOut(rec, enc('held line\r\n'));
    await settle();
    const whileAway = text();
    termOut(rec, enc('\x1b[c\x1b[>c'));
    await settle();
    const asked = answered.join('');
    termOut(rec, enc('after it\r\n'));
    await settle();
    const afterAsk = text();
    termShow(rec, true);
    await settle();
    const shown = text();
    term.dispose(); el.remove();
    return { whileAway, asked: JSON.stringify(asked), afterAsk, shown };
  });
  ok(!/held line/.test(got.whileAway), `not on show, what it is sent is not drawn (${got.whileAway.replace(/\|+$/, '') || 'nothing'})`);
  ok(/\\u001b\[\?/.test(got.asked) && /held line/.test(got.afterAsk) && !/after it/.test(got.afterAsk),
     `...a question in it is answered as it comes, with what came before it drawn (${got.asked}; ${got.afterAsk.replace(/\|+$/, '')})`);
  ok(/held line/.test(got.shown) && /after it/.test(got.shown), `...and shown, the rest is drawn (${got.shown.replace(/\|+$/, '')})`);
});

await done(browser);
