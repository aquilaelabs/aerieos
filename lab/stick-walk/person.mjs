// A person's browser against the VM, one step per run, its session kept.
// node person.mjs STEP [args]: steps live in steps.mjs
import { createRequire } from 'node:module';
import { existsSync } from 'node:fs';
const { chromium } = createRequire(import.meta.url)('playwright');
const HERE = new URL('.', import.meta.url).pathname;
const BASE = 'http://127.0.0.1:7690';
const [step, ...args] = process.argv.slice(2);
const { steps } = await import(HERE + 'steps.mjs');
const b = await chromium.launch();
const state = HERE + 'run/browser.json';
const ctx = await b.newContext({ viewport: { width: 1440, height: 1000 }, ...(existsSync(state) ? { storageState: state } : {}) });
const page = await ctx.newPage();
const errors = [];
page.on('pageerror', e => errors.push(String(e).slice(0, 300)));
page.on('console', m => { if (m.type() === 'error') errors.push('console: ' + m.text().slice(0, 200)); });
page.on('dialog', async d => { console.log('[browser dialog]', d.message().slice(0, 400)); await d.accept(); });
const shot = async name => { await page.screenshot({ path: `${HERE}run/${name}.png`, fullPage: false }); console.log('[shot]', `${HERE}run/${name}.png`); };
const tall = async (name, h = 2600) => { const vp = page.viewportSize(); await page.setViewportSize({ width: vp.width, height: h }); await page.waitForTimeout(400); await shot(name); await page.setViewportSize(vp); };
const phone = async (name, h = 3000) => { const vp = page.viewportSize(); await page.setViewportSize({ width: 393, height: h }); await page.waitForTimeout(500); await shot(name); await page.setViewportSize(vp); };
try { await steps[step]({ page, BASE, args, shot, tall, phone, ctx }); }
catch (e){ console.log('[step failed]', String(e).slice(0, 600)); await shot('failed-' + step).catch(() => {}); }
await ctx.storageState({ path: state });
if (errors.length) console.log('[page errors]', errors.slice(0, 8).join(' | '));
await b.close();
