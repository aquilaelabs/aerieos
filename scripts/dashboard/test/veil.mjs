// The cover that hides the white flash when a VM's screen appears in a pane.
//
// The flash is the frame's document existing with no background of its own,
// which a browser paints as a white canvas, over whatever the iframe element
// underneath is set to. Firefox on Android does it unconditionally.
//
// The cover used to come off on a fixed 350ms timer, a guess with a wide
// margin around it. It now closes the gap instead: the frame is same-origin
// (noVNC is served from this server), so its <html> is given the pane's own
// color and the cover comes off on the next frame. The clock is only for a
// frame that cannot be reached at all.
//
// Driven against synthetic frames rather than a real screen: the harness
// runs no VM, and what is under test is the release rule.
import { launch, newPage, ok, done, ready, quiet, URL } from './lib.mjs';

const browser = await launch();
const page = await newPage(browser, { viewport: { width: 1280, height: 800 } });
await page.goto(URL);
await ready(page);

// A slot shaped like a pane's. `src` mimics what a screen's frame is: a
// document with no background of its own.
const build = src => page.evaluate(src => {
  document.querySelectorAll('#veiltest').forEach(n => n.remove());
  const slot = document.createElement('div');
  slot.id = 'veiltest'; slot.className = 'slot';
  const f = document.createElement('iframe');
  const v = document.createElement('i'); v.className = 'veil';
  slot.append(f, v); document.body.appendChild(slot);
  const done = new Promise(r => { f.onload = () => r(true); });
  if (src) f.src = src; else f.srcdoc = '<html><body><div>x</div></body></html>';
  return done;
}, src);

const veilState = () => page.evaluate(() => {
  const v = document.querySelector('#veiltest .veil');
  return !v ? 'removed' : v.classList.contains('gone') ? 'fading' : 'covering';
});
const lifted = () => page.waitForFunction(() => {
  const v = document.querySelector('#veiltest .veil');
  return !v || v.classList.contains('gone');
}, { timeout: 3000 });

// ---- the frame it can reach --------------------------------------------
await build();
ok(await page.$eval('#veiltest iframe',
     f => getComputedStyle(f.contentDocument.documentElement).backgroundColor
          === 'rgba(0, 0, 0, 0)'),
   'a terminal frame starts with no background of its own: this is the flash');

const t0 = Date.now();
await page.evaluate(() => unveil(document.querySelector('#veiltest iframe')));
await lifted();
const took = Date.now() - t0;
ok(await page.$eval('#veiltest iframe',
     f => getComputedStyle(f.contentDocument.documentElement).backgroundColor
          === 'rgb(43, 43, 43)'),
   'unveil gives it the pane color, so there is no white left to paint');
// Timed from here, the page's round trips in it: under a whole run's load
// that alone was 133 ms, so the bound is the old floor's side of the line
// with room, not the machine's speed.
ok(took < 250, `...and the cover comes off at once (${took}ms, not the old 350ms floor)`);
await page.waitForFunction(() => !document.querySelector('#veiltest .veil'), { timeout: 3000 });
ok(await veilState() === 'removed', '...then takes itself out of the pane');

// ---- the frame it cannot ------------------------------------------------
// An opaque origin: contentDocument throws, nothing can be dressed, and the
// clock is all there is. This is the proxy-error and disagreeing-engine case.
await build('data:text/html,<p>opaque');
const t1 = Date.now();
await page.evaluate(() => unveil(document.querySelector('#veiltest iframe')));
await quiet(150);
ok(await veilState() === 'covering', 'a frame that cannot be reached stays covered');
await lifted();
const held = Date.now() - t1;
ok(held > 300 && held < 900, `...until the clock backstop (${held}ms)`);

// ---- a pane torn down mid-cover ----------------------------------------
await build('data:text/html,<p>opaque');
await page.evaluate(() => {
  unveil(document.querySelector('#veiltest iframe'));
  document.querySelector('#veiltest').remove();
});
// Past the clock backstop, which is when a timer left behind would fire.
await quiet(600);
ok(page.errors.length === 0, 'a pane replaced while covered raises nothing');

// ---- a screen's tab, as the page itself opens one -------------------------
// The checks above call unveil themselves, so they could not see the page
// failing to: its frame said onload="unveil(this)", which the page's own
// Content-Security-Policy refuses, and nothing else lifted the veil. The
// harness runs no VM, so the frame's page is this server's answer for a
// screen that is not there; the frame still loads, which is all a veil waits for.
const refused = [];
page.on('console', m => { if (/Content Security Policy|Refused to execute inline/i.test(m.text())) refused.push(m.text()); });
// A console tab onto a VM the list does not have is dropped once the list
// lands (vmReapConsoles, B172), which on an idle machine is before the
// checks below look: so the list read here has the VM the tab is onto.
await page.route(u => u.pathname === '/api/vms', async r => {
  const real = await r.fetch();
  const j = await real.json().catch(() => null);
  if (!j || !Array.isArray(j.vms)) return r.fulfill({ response: real });
  await r.fulfill({ response: real, json: { ...j, vms: [...j.vms, { project: 'alpha', name: 'nobody', state: 'running' }] } });
});
await page.evaluate(() => openTab({ kind: 'term', arg: 'screen:alpha:nobody', label: 'screen nobody' }));
await page.waitForSelector('.pane .slot.on iframe', { timeout: 10000 });
ok(await page.$eval('.pane .slot.on iframe', f => !f.hasAttribute('onload')),
   'a screen\'s frame carries no inline handler, which the page\'s own policy would refuse');
const gone = await page.waitForFunction(() => {
  const s = document.querySelector('.pane .slot.on');
  const v = s && s.querySelector('.veil');
  return s && (!v || v.classList.contains('gone'));
}, { timeout: 5000 }).then(() => true, () => false);
ok(gone, 'the veil over a screen the page opened comes off by itself when its frame has loaded');
ok(refused.length === 0, `...and the policy refused nothing (${refused[0] || 'nothing'})`);
ok(!(await page.evaluate(() => [...document.querySelectorAll('script')].length
     && /onload="unveil/.test(String(window.drawPanes)))), 'no template of the panes writes that handler');

// The harness carries no noVNC, so the screen's own page is a 404 here: that
// one line is the fixture's, and anything else is the page's.
const errs = page.errors.filter(e => !/404 \(Not Found\) \[\/novnc\/vnc_lite\.html/.test(e));
ok(errs.length === 0, 'zero console errors');
if (errs.length) console.log(errs);
await done(browser);
