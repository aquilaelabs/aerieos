'use strict';
// AerieOS's controller as the extension speaks to it: sign in as the
// person, then every call carries their own cookie and nothing wider. What
// they may do is decided by the server on every request (the Files API's
// gate, the terminal's); this file only carries the answers back.
const crypto = require('crypto');
const http = require('http');
const https = require('https');
const tls = require('tls');
const ws = require('./ws');

// The Files API version this extension speaks, said on every call with the
// extension's own release; the server says its own in the projects answer,
// and refuses one older than it keeps (426) in words this shows.
const API = 1;
let RELEASE = '';
try { RELEASE = require('../package.json').version || ''; } catch { RELEASE = ''; }
const SAYS = { 'X-BB-Api': String(API), 'X-BB-App': `vscode/${RELEASE || '0.0.0'}` };

class Refused extends Error {
  constructor(status, message, body) {
    super(message);
    this.status = status;
    this.body = body || {};
  }
}

// A pin of the controller's key, as a node's agent and the Windows
// companion take one (curl's --pinnedpubkey form): sha256// and the base64
// of the sha256 of the key's public half, so a certificate the controller
// remakes over the same key still passes.
const KEY_PIN = 'sha256//';

// `cert` is the peer's certificate as tls hands it, its DER in `raw`: the
// key's public half is read from that, since tls's own `pubkey` is the
// whole SubjectPublicKeyInfo for an RSA key and the bare point for an EC one.
function keyPin(cert) {
  try {
    const spki = new crypto.X509Certificate(cert.raw).publicKey.export({ type: 'spki', format: 'der' });
    return KEY_PIN + crypto.createHash('sha256').update(spki).digest('base64');
  } catch {
    return '';
  }
}

const OTHER_KEY = 'The controller answered with another key than the one this editor trusted when it signed in, '
  + 'so nothing was sent: sign out and in again only if the controller was set up anew.';

// A connection to a controller under its own certificate, which no
// authority signed: held to the key this editor pinned when it first
// signed in, or, with none pinned yet, pinned now and said to `onPin`.
// Nothing is sent on a connection under any other key. It names no server,
// as a node's agent names none: the controller answers a name with that
// name's certificate, which is another key's.
function pinned(host, port, { pin = '', onPin = null } = {}) {
  return new Promise((resolve, reject) => {
    const sock = tls.connect({ host, port, servername: '', rejectUnauthorized: false }, () => {
      const seen = keyPin(sock.getPeerCertificate());
      if (!seen || (pin && seen !== pin)) {
        sock.destroy();
        reject(new Refused(0, OTHER_KEY));
        return;
      }
      if (!pin && onPin) onPin(seen);
      resolve(sock);
    });
    sock.once('error', reject);
  });
}

// What to connect with for `u`: {createConnection} of a pinned socket for a
// controller under its own certificate, else the authorities' check.
async function door(u, { rejectUnauthorized = true, pin = '', onPin = null } = {}) {
  const secure = u.protocol === 'https:' || u.protocol === 'wss:';
  const port = Number(u.port) || (secure ? 443 : 80);
  if (!secure || rejectUnauthorized) return { secure, port, how: { rejectUnauthorized } };
  const sock = await pinned(u.hostname, port, { pin, onPin });
  return { secure: false, port, how: { createConnection: () => sock } };
}

async function request(base, path, { method = 'GET', headers = {}, body = null, ...trust } = {}) {
  const u = new URL(path, base);
  const { secure, port, how } = await door(u, trust);
  return new Promise((resolve, reject) => {
    const req = (secure ? https : http).request({
      host: u.hostname, port, path: u.pathname + u.search, method,
      headers: { Connection: 'close', ...headers, ...(body !== null ? { 'Content-Length': Buffer.byteLength(body) } : {}) },
      // A connection of its own each time: the dashboard answers one request
      // per connection, and Node's pool reusing a closed one hung up the next
      // request, a terminal's upgrade among them. A pinned one is made above.
      ...(how.createConnection ? {} : { agent: false }),
      ...how,
    }, res => {
      const chunks = [];
      res.on('data', d => chunks.push(d));
      res.on('end', () => resolve({ status: res.statusCode, headers: res.headers, body: Buffer.concat(chunks) }));
    });
    req.on('error', reject);
    if (body !== null) req.write(body);
    req.end();
  });
}

// The person's name and password for the cookie a browser would get: the
// same signed token, revoked by a password change or the account's removal.
// The password itself is never kept.
// Under the controller's own certificate the password goes only on a
// connection under the key pinned (opts.pin), or pinned now (opts.onPin).
async function signIn(base, name, password, opts = {}) {
  const body = new URLSearchParams({ username: name, password, next: '/' }).toString();
  const r = await request(base, '/login', {
    method: 'POST', body, ...trusted(opts),
    headers: { 'Content-Type': 'application/x-www-form-urlencoded' },
  });
  const set = [].concat(r.headers['set-cookie'] || []).map(c => /bb_session=([^;]+)/.exec(c)).find(Boolean);
  if (r.status !== 303 || !set || !set[1]) {
    throw new Refused(r.status, /Wrong username or password/.test(r.body.toString())
      ? 'Wrong username or password.' : `sign-in refused (${r.status})`);
  }
  return set[1];
}

// How a call is held: by the authorities, or to the controller's key.
function trusted(opts = {}) {
  return { rejectUnauthorized: opts.rejectUnauthorized !== false, pin: opts.pin || '', onPin: opts.onPin || null };
}

class Client {
  constructor(base, cookie, opts = {}) {
    this.base = base.replace(/\/+$/, '');
    this.cookie = cookie;
    // A key pinned by this client's first call is held by every one after.
    const said = opts.onPin;
    this.tls = trusted({ ...opts, onPin: p => { this.tls.pin = p; if (said) said(p); } });
  }

  headers(extra = {}) {
    return { Cookie: `bb_session=${this.cookie}`, ...SAYS, ...extra };
  }

  async post(path, payload) {
    const r = await request(this.base, path, {
      method: 'POST', body: JSON.stringify(payload), ...this.tls,
      headers: this.headers({ 'Content-Type': 'application/json' }),
    });
    let j = {};
    try { j = JSON.parse(r.body.toString() || '{}'); } catch { j = {}; }
    if (r.status === 401 || (r.status >= 300 && r.status < 400)) {
      throw new Refused(401, 'Not signed in to AerieOS, or the sign-in has expired: AerieOS: Sign In.');
    }
    if (r.status >= 400) throw new Refused(r.status, j.error || `refused (${r.status})`, j);
    return j;
  }

  files(project, action, extra = {}) {
    return this.post('/api/v1/files', { action, project, ...extra });
  }

  // The projects this account may open in an editor, with its access to each.
  async projects() {
    const j = await this.post('/api/v1/files', { action: 'projects' });
    return { api: j.api, projects: j.projects || [], tooOld: controllerTooOld(j) };
  }

  // The dashboard's status, as the page reads it, for what opening an agent's
  // session needs of it: the boot of the machine a new session starts
  // on, without which bb-tty attaches to a running session and starts none,
  // and which of this account's sessions run.
  async status() {
    const r = await request(this.base, '/api/status', { headers: this.headers(), ...this.tls });
    if (r.status === 401 || (r.status >= 300 && r.status < 400)) {
      throw new Refused(401, 'Not signed in to AerieOS, or the sign-in has expired: AerieOS: Sign In.');
    }
    let j = {};
    try { j = JSON.parse(r.body.toString() || '{}'); } catch { j = {}; }
    if (r.status >= 400) throw new Refused(r.status, j.error || `refused (${r.status})`, j);
    return j;
  }

  // A session's terminal: the dashboard's own at /termws, so the same
  // checks decide whose terminal it is and whether it may be typed into. A
  // refusal is the socket closing with why.
  async terminal(arg, cols, rows) {
    const q = `?arg=${encodeURIComponent(arg)}&cols=${cols | 0}&rows=${rows | 0}`;
    const url = this.base.replace(/^http/, 'ws') + `/termws${q}`;
    const { secure, how } = await door(new URL(url), this.tls);
    return ws.connect(url, { headers: this.headers(), secure, ...how });
  }
}

// The plain sentence for a controller older than this extension, from the
// API its projects answer says (none said is 1), or ''. A newer controller
// keeps what this one reads, and refuses it outright once it does not.
function controllerTooOld(answer) {
  const said = (answer || {}).api;
  const theirs = said === undefined || said === null ? 1 : Number(said) || 0;
  return theirs >= API ? ''
    : `AerieOS's Files API is version ${theirs} and this extension needs ${API}: update AerieOS on the controller.`;
}

module.exports = { API, SAYS, KEY_PIN, Client, Refused, signIn, request, keyPin, controllerTooOld };
