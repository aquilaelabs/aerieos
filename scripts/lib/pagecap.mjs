// A page opened to be looked at: what aerie capture shot and aerie capture reel
// share. One launcher for both, and as little of it written down here as can
// be: the browsers are whichever of Playwright's this machine has installed,
// asked of Playwright itself; a screen is a size or any device Playwright
// knows by name; and what else a page can be told (a color scheme, a locale,
// a time zone, less motion) goes through to the browser's context as it is
// named, with no list of them kept here.
//
//   node pagecap.mjs browsers            the engines installed here, a line each
//   node pagecap.mjs devices [WORDS]     Playwright's devices, a line each
//   node pagecap.mjs shot JSON           pictures at rest; prints each file
//   node pagecap.mjs reel JSON           a recording; prints the video's path
//
// NODE_PATH names the Playwright the store carries, PLAYWRIGHT_BROWSERS_PATH
// its browsers, BB_CAPTURE_CHROME the Chromium aerie found (its own launcher
// in the store, where there is one).
import { createRequire } from "node:module";
import fs from "node:fs";
import path from "node:path";

const require = createRequire(import.meta.url);
let pw;
try { pw = require("playwright"); }
catch { console.error("no Playwright here: it is a toolchain the Library installs"); process.exit(4); }

// Where an engine's program is, or "" when it is not installed: Playwright's
// own answer, and for Chromium the one aerie found first.
function programOf(name){
  if (name === "chromium" && process.env.BB_CAPTURE_CHROME && fs.existsSync(process.env.BB_CAPTURE_CHROME))
    return process.env.BB_CAPTURE_CHROME;
  try { const exe = pw[name].executablePath(); return exe && fs.existsSync(exe) ? exe : ""; }
  catch { return ""; }
}

// The browsers this machine can open a page in: every browser type Playwright
// has (whatever it calls them, now and later) whose program is installed.
export function engines(){
  return Object.keys(pw).filter(k => !k.startsWith("_") && pw[k] && typeof pw[k].launch === "function"
                                     && typeof pw[k].executablePath === "function" && programOf(k));
}

// Which of them a run uses: the one named, every one for "all", and the
// first installed when none is named (Chromium where it is there, as before).
function chosen(want){
  const here = engines();
  if (!here.length) fail("no browser here: Playwright's browsers are a toolchain the Library installs", 4);
  if (!want) return [here.includes("chromium") ? "chromium" : here[0]];
  if (want === "all") return here;
  const names = want.split(",").map(s => s.trim()).filter(Boolean);
  const missing = names.filter(n => !here.includes(n));
  if (missing.length) fail(`no browser called ${missing.join(", ")} here: this machine has ${here.join(", ")}`, 2);
  return names;
}

function fail(why, code = 1){ console.error(why); process.exit(code); }

// The context a page opens in: a device's own (its size, density and touch,
// from Playwright's registry), a size given outright over that, and anything
// else by the name Playwright's context takes it under.
function contextFor(engine, o){
  let opt = {};
  if (o.device){
    const d = pw.devices[o.device];
    if (!d) fail(`no device called "${o.device}": aerie capture devices lists them`, 2);
    const { defaultBrowserType: _its, ...its } = d;
    opt = { ...its };
  }
  if (o.width && o.height) opt.viewport = { width: +o.width, height: +o.height };
  else if (!opt.viewport) opt.viewport = { width: 1280, height: 800 };
  if (o.scale) opt.deviceScaleFactor = +o.scale;
  if (o.scheme) opt.colorScheme = o.scheme;
  for (const kv of o.set || []){
    const at = kv.indexOf("=");
    if (at < 1) fail(`--set takes NAME=VALUE (${kv})`, 2);
    let v = kv.slice(at + 1);
    try { v = JSON.parse(v); } catch { /* a plain word */ }
    opt[kv.slice(0, at)] = v;
  }
  // Firefox has no mobile mode to switch on: the device's size, density and
  // touch still hold there, and the page is otherwise Firefox's own.
  if (engine === "firefox") delete opt.isMobile;
  return opt;
}

// A browser of that engine with one context, the credential going to the
// trusted origins and nowhere else. `auth` is a session's token (bbs_...)
// or NAME:PASSWORD; `trust` the origins it may go to, or "named" for the
// URLs it was named with.
async function opened(engine, o, urls, extra = {}){
  const exe = programOf(engine);
  const b = await pw[engine].launch(engine === "chromium" && exe === process.env.BB_CAPTURE_CHROME ? { executablePath: exe } : {});
  const auth = o.auth || "", trust = o.trust || "";
  // Either shape of credential. A session holds a bearer token rather than a
  // password (bug #16), and splitting on ":" produced no credential at all
  // for one, so a session photographing a dashboard page got the LOGIN page
  // and no error, which is the worst way for this to fail.
  const bearer = /^bbs_/.test(auth);
  const [username, password] = !bearer && auth.includes(":") ? auth.split(/:(.*)/) : [null, null];
  const header = bearer ? "Bearer " + auth : username ? "Basic " + Buffer.from(auth).toString("base64") : "";
  // Matched on the whole origin, the controller's own: a port alone
  // let a dev instance, or anybody's page, on :7680 have this session's
  // token. A credential named with --auth goes to the URLs named with it.
  const trusted = new Set(trust === "named" ? [] : trust.split(",").filter(Boolean));
  const mine = new Set(urls.filter(u => {
    try { return trust === "named" || trusted.has(new URL(u).origin); } catch { return false; }
  }).map(u => new URL(u).origin));
  // Credentials go both ways: httpCredentials answers a server that
  // challenges, the preemptive Authorization header satisfies one that
  // deliberately never does (the dashboard, whose challenge-free 401s are
  // what keep browsers from popping their own dialog). The challenge is
  // answered for one trusted origin alone, Playwright's limit.
  const ctx = await b.newContext({ ...contextFor(engine, o), ...extra,
    ...(username && mine.size === 1 ? { httpCredentials: { username, password, origin: [...mine][0] } } : {}) });
  // The header goes to the DASHBOARD and nowhere else. On the context it went
  // to every URL in the run, so a shot of the dashboard and of somebody
  // else's page handed the credential to both (bug #49). Per route, matched
  // on origin.
  if (header && mine.size)
    await ctx.route("**/*", async route => {
      let same = false;
      try { same = mine.has(new URL(route.request().url()).origin); } catch {}
      await route.continue(same ? { headers: { ...route.request().headers(), authorization: header } } : {});
    });
  // ...and a real sign-in, for the cookie. A header added by routing does not
  // reach a WEBSOCKET handshake (Playwright does not intercept those), and
  // the terminal is a websocket on the dashboard's own origin, so a shot of a
  // page with a terminal in it came out with the terminal refused. Best
  // effort: a page that is not an AerieOS dashboard has no /login, and the
  // header above is still what answers for it.
  if (username)
    for (const origin of mine){
      try { await ctx.request.post(origin + "/login", { form: { username, password }, maxRedirects: 0, timeout: 10000 }); } catch {}
    }
  return { b, ctx, mine };
}

// A picture's file for one engine of several: NAME-ENGINE.png.
const named = (file, engine, several) => !several ? file
  : path.join(path.dirname(file), path.basename(file, path.extname(file)) + "-" + engine + (path.extname(file) || ".png"));

async function shot(o){
  const use = chosen(o.browser), several = use.length > 1;
  let unanswered = 0, failed = 0;
  for (const engine of use){
    let b, ctx, mine;
    try { ({ b, ctx, mine } = await opened(engine, o, o.urls)); }
    catch (e){
      console.error(`${engine}: did not start (${String(e.message || e).split("\n")[0]}); its system libraries are the provisioner's to install`);
      failed++;
      continue;
    }
    // The downscale, in the browser that took the shot. It used to be
    // imagemagick's convert, which is in the controller's image and on no
    // node. A browser resamples as well and is already here. On a
    // blank page of its own, because a data: image is exactly what a
    // photographed page's own CSP may refuse.
    let scaler = null;
    const shrink = async (file, width) => {
      scaler = scaler || await b.newPage();
      const b64 = fs.readFileSync(file).toString("base64");
      const done = await scaler.evaluate(async ([data, wide]) => {
        const img = new Image();
        img.src = "data:image/png;base64," + data;
        await img.decode();
        if (img.width <= wide) return null;      // never upscale: that adds nothing
        const c = document.createElement("canvas");
        c.width = wide;
        c.height = Math.max(1, Math.round(img.height * wide / img.width));
        const g = c.getContext("2d");
        g.imageSmoothingEnabled = true;
        g.imageSmoothingQuality = "high";
        g.drawImage(img, 0, 0, c.width, c.height);
        return c.toDataURL("image/png").split(",")[1];
      }, [b64, width]);
      // In place, and metadata-free by construction: a fresh encode carries none.
      if (done) fs.writeFileSync(file, Buffer.from(done, "base64"));
    };
    const p = await ctx.newPage();
    const taken = new Set();
    for (const url of o.urls){
      // A page that never goes quiet is still a page, and is shot as it is;
      // one that never answered is not: a browser draws its own error
      // page, and a picture of that with exit 0 read as the site being up.
      let down = "";
      const res = await p.goto(url, { waitUntil: "networkidle" }).catch(e => {
        if (!/timeout/i.test(`${e.name} ${e.message}`)) down = String(e.message).split("\n")[0];
        return null;
      });
      if (down){
        console.error(`${url}: did not answer (${down}); no picture taken`);
        unanswered++;
        continue;
      }
      if (res && res.status() >= 400) console.error(`${url}: answered ${res.status()}; shot as it is`);
      if (+o.wait) await p.waitForTimeout(+o.wait);
      // --drive works the page first, as it does the emulator and a display:
      // its default export gets the page and the context.
      if (o.drive){
        const mod = await import(o.drive);
        await (mod.default || mod.drive)(p, { ctx, browser: b, url, engine });
      }
      let out = o.dest;
      if (o.mode === "dir"){
        // Named from the path so reruns overwrite their own shots, with a
        // counter only for two URLs that share a path. No leading dash or
        // dot, and capped at 80: a long query string made a name longer
        // than a filesystem takes.
        const u = new URL(url);
        const s = ((u.pathname + u.search).replace(/^\/+|\/+$/g, "").replace(/[^A-Za-z0-9._-]+/g, "-").replace(/^[-.]+/, "") || "index").slice(0, 80);
        let name = s, n = 2;
        while (taken.has(name)) name = `${s}-${n++}`;
        taken.add(name);
        out = path.join(o.dest, name + ".png");
      }
      out = named(out, engine, several);
      // At rest, when asked or when it is the dashboard's own page: a shot
      // every quarter second until a whole second of them are the same
      // bytes. A page that never stops moving is taken as it is after six
      // seconds, and said.
      const full = !!o.full;
      const atRest = o.settle === "1" || (o.settle === "" && (() => { try { return mine.has(new URL(url).origin); } catch { return false; } })());
      if (atRest){
        let last = await p.screenshot({ fullPage: full }), still = 0;
        const until = Date.now() + 6000;
        while (Date.now() < until && still < 4){
          await p.waitForTimeout(250);
          const next = await p.screenshot({ fullPage: full });
          still = next.equals(last) ? still + 1 : 0;
          last = next;
        }
        if (still < 4) console.error(`${url}: still moving after six seconds; shot as it is`);
        fs.writeFileSync(out, last);
      } else {
        await p.screenshot({ path: out, fullPage: full });
      }
      if (+o.resize) await shrink(out, +o.resize);
      console.log(out);
    }
    await b.close();
  }
  if (failed) process.exitCode = 1;
  else if (unanswered) process.exitCode = 3;
}

// A page recorded while a script drives it: the driver gets the page and
// the seconds it has. One engine a recording.
async function reel(o){
  const use = chosen(o.browser);
  if (use.length > 1) fail(`a reel is one browser's: name one of ${use.join(", ")}`, 2);
  const engine = use[0];
  const size = contextFor(engine, o).viewport;
  const { b, ctx } = await opened(engine, o, [o.url], { recordVideo: { dir: o.vdir, size } });
  const page = await ctx.newPage();
  const started = Date.now();
  await page.goto(o.url, { waitUntil: "domcontentloaded" }).catch(e => console.error("goto: " + e.message));
  if (o.drive){
    const mod = await import(o.drive);
    await (mod.default || mod.drive)(page, { seconds: +o.seconds, ctx, browser: b, engine });
  }
  const left = +o.seconds * 1000 - (Date.now() - started);
  if (left > 0) await page.waitForTimeout(left);
  await ctx.close();
  await b.close();
}

const [verb, arg = ""] = process.argv.slice(2);
if (verb === "browsers") console.log(engines().join("\n"));
else if (verb === "devices"){
  const words = arg.toLowerCase().split(/\s+/).filter(Boolean);
  for (const [name, d] of Object.entries(pw.devices))
    if (words.every(w => name.toLowerCase().includes(w)))
      console.log(`${name}\t${d.viewport.width}x${d.viewport.height} at ${d.deviceScaleFactor}${d.hasTouch ? ", touch" : ""}`);
}
else if (verb === "shot") shot(JSON.parse(arg)).catch(e => fail(String(e)));
else if (verb === "reel") reel(JSON.parse(arg)).catch(e => fail(String(e)));
else fail("pagecap.mjs browsers | devices [WORDS] | shot JSON | reel JSON", 2);
