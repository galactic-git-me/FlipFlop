// Narrow, domain-scoped Chrome tools. Credentials never enter tool responses.
import fs from 'node:fs/promises';
import path from 'node:path';
import readline from 'node:readline';
import { createRequire } from 'node:module';
import { parseEnv } from 'node:util';

const job = JSON.parse(await fs.readFile(process.env.FF_BROWSER_JOB_FILE, 'utf8'));
const pack = job.payload;
const require = createRequire(path.join(process.env.FF_ADMIN_DIR, 'package.json'));
const { chromium } = require('playwright');
const domains = { onbuy: ['onbuy.com'], facebook_catalog: ['facebook.com'], vinted: ['vinted.co.uk'] }[pack.channel];
let context, page, revision = 0, inspected = false, remoteState = 'unknown', remoteStateNote = '', remoteStateOrderId = null, mayHaveWritten = false;
const allowed = value => {
  const u = new URL(value);
  return u.protocol === 'https:' && !u.username && !u.password && (!u.port || u.port === '443') && domains.some(d => u.hostname === d || u.hostname.endsWith('.' + d));
};
async function browser() {
  if (!context) {
    context = await chromium.launchPersistentContext(process.env.FF_CHROME_PROFILE, { channel: 'chrome', headless: false, acceptDownloads: false });
    await context.route('**/*', async route => {
      const req = route.request();
      if (req.isNavigationRequest() && req.frame() === page?.mainFrame() && !allowed(req.url())) return route.abort();
      await route.continue();
    });
    page = context.pages()[0] || await context.newPage();
    context.on('page', async p => { if (p !== page) await p.close(); });
    await page.goto(pack.seller_url);
  }
  if (!allowed(page.url())) throw new Error('Unexpected vendor page; stop for account review');
}
async function preflight() {
  const r = await fetch(`${process.env.FF_WORKER_API}/${job.id}/preflight`, { method: 'POST',
    headers: { 'content-type': 'application/json', 'x-worker-key': process.env.FF_WORKER_KEY }, body: JSON.stringify({ lease_token: job.lease_token }) });
  if (!r.ok) throw new Error('Build or job changed; stop before publishing');
}
async function snapshot() {
  await browser();
  revision += 1;
  const elements = await page.locator('a,button,input,textarea,select,[role="button"],[role="combobox"],[role="option"],[role="checkbox"],[role="radio"],[contenteditable="true"]').evaluateAll((nodes, rev) => nodes.filter(n => n.getClientRects().length || n.matches('input[type="file"]')).slice(0, 200).map((n, i) => {
    n.setAttribute('data-ff-ref', `${rev}-${i}`);
    return { ref: `${rev}-${i}`, tag: n.tagName, type: n.getAttribute('type'), text: (n.getAttribute('aria-label') || n.innerText || n.getAttribute('placeholder') || n.getAttribute('name') || '').slice(0, 160) };
  }), revision);
  return { url: page.url(), title: await page.title(), text: (await page.locator('body').innerText()).slice(0, 18000), elements };
}
function element(ref) {
  if (!/^\d+-\d+$/.test(String(ref)) || !String(ref).startsWith(`${revision}-`)) throw new Error('Observe the page again; the element reference is stale');
  return page.locator(`[data-ff-ref="${ref}"]`);
}
async function envLogin(args) {
  await browser();
  const username = args.username_ref ? element(args.username_ref) : null, password = args.password_ref ? element(args.password_ref) : null;
  if (!username && !password) throw new Error('Select the username or password field from the current observation');
  if (password && await password.getAttribute('type') !== 'password') throw new Error('Choose the actual password field');
  const prefix = { onbuy: 'FF_ONBUY', facebook_catalog: 'FF_FACEBOOK_MARKETPLACE', vinted: 'FF_VINTED' }[pack.channel];
  let values;
  try { values = parseEnv(await fs.readFile(process.env.FF_CREDENTIALS_FILE, 'utf8')); }
  catch { throw new Error('The local seller credentials file is unavailable; configure FF_CREDENTIALS_FILE'); }
  const login = values[prefix + '_USERNAME'], secret = values[prefix + '_PASSWORD'];
  if (!login || !secret) throw new Error(`Set ${prefix}_USERNAME and ${prefix}_PASSWORD in the local .env.local file`);
  if (username) await username.fill(login);
  if (password) await password.fill(secret);
  return { filled: true, message: 'Credentials filled locally; submit the observed sign-in form.' };
}

async function run(name, args) {
  if (name === 'seller_pack') return { ...pack, operation: job.operation,
    instructions: ['inspect', 'sale_check'].includes(job.operation)
      ? 'Read-only status check. Inspect this exact vendor listing and seller orders; mark sold only with an exact seller order and preserve its order ID. Call confirm_observation.'
      : job.operation === 'withdraw'
        ? 'End the exact previous listing in seller tools. Verify it is ended, missing, or sold and call confirm_observation. Do not delete accounts or pay fees.'
        : 'Inspect seller listings first. Update active; relist ended; create only after confirming missing. No duplicates. Google Shopping is handled through Merchant API. Delivery only; no pickup. Stop for fees, account creation, MFA, CAPTCHA or vendor restrictions. Use env_login for local credentials without revealing them.' };
  if (name === 'browser_observe') return snapshot();
  if (name === 'browser_navigate') { await browser(); if (!allowed(args.url)) throw new Error('URL outside this vendor'); await page.goto(args.url); return snapshot(); }
  if (name === 'env_login') return envLogin(args);
  if (name === 'remote_state') { inspected = true; remoteState = args.state; remoteStateNote = args.note; remoteStateOrderId = args.order_id || null; return { recorded: true, state: args.state, note: args.note, order_id_recorded: Boolean(remoteStateOrderId) }; }
  if (name === 'browser_click') {
    await browser();
    if (!inspected) throw new Error('First inspect seller listings and record the remote state');
    if (args.writes_listing && !['active', 'ended', 'missing'].includes(remoteState)) throw new Error('Remote listing state must be verified before a listing write');
    const el = element(args.ref);
    const text = ((await el.innerText()) || await el.getAttribute('aria-label') || '').toLowerCase();
    if (/pay|purchase|subscribe|boost|promote|delete account|create account|grant access/.test(text)) throw new Error('Paid service or account change requires separate operator review');
    await preflight();
    if (args.writes_listing) mayHaveWritten = true;
    await el.click();
    return snapshot();
  }
  if (name === 'browser_fill') {
    await browser(); const el = element(args.ref);
    if (await el.getAttribute('type') === 'password') throw new Error('Use env_login for passwords');
    await el.fill(args.value); return { filled: true };
  }
  if (name === 'browser_select') { await browser(); await element(args.ref).selectOption({ label: args.label }); return snapshot(); }
  if (name === 'browser_upload') {
    await browser(); const files = args.image_indexes.map(i => {
      if (!Number.isInteger(i) || i < 0 || i >= pack.listing.images.length) throw new Error('Choose photographs from the seller pack');
      return path.join(path.dirname(process.env.FF_BROWSER_JOB_FILE), `photo-${i}.jpg`);
    });
    await element(args.ref).setInputFiles(files); return snapshot();
  }
  if (name === 'confirm_listing') {
    await browser(); await preflight();
    if (!allowed(args.url) || args.url === pack.seller_url || !args.external_id || !inspected || remoteState !== 'active') throw new Error('Record the confirmed live remote state, item URL and vendor identity before saving');
    await page.goto(args.url);
    const text = await page.locator('body').innerText();
    const title = pack.listing.title.toLowerCase();
    const normalized = text.toLowerCase().replace(/\s+/g, ' ');
    const price = Number(pack.listing.price).toFixed(2);
    const prices = [price, Number(pack.listing.price).toLocaleString('en-GB', { minimumFractionDigits: 2 }), String(pack.listing.price)];
    if (!normalized.includes(title.slice(0, 45)) || !prices.some(p => text.includes(p)) || /listing (?:has been )?(?:removed|expired|ended)|item (?:is )?(?:sold|unavailable)/i.test(text)) throw new Error('Public listing title, saved price or availability could not be confirmed');
    const result = { status: 'succeeded', message: 'Codex confirmed the live vendor listing and saved its identity.', listing_url: page.url(), external_id: args.external_id,
      evidence: { title: pack.listing.title, price: pack.listing.price, verified_at: new Date().toISOString(), url: page.url() } };
    await fs.writeFile(process.env.FF_BROWSER_RESULT_FILE, JSON.stringify(result));
    return { confirmed: true, listing_url: page.url() };
  }
  if (name === 'confirm_observation') {
    await browser(); await preflight();
    if (!['inspect', 'sale_check', 'withdraw'].includes(job.operation) || !inspected || !['active', 'ended', 'missing', 'sold', 'unknown'].includes(remoteState)) throw new Error('This job requires an observed seller listing status before completion');
    if (remoteState === 'sold' && (!remoteStateOrderId || !remoteStateNote)) throw new Error('A seller order ID and evidence note are required to confirm a sale');
    await fs.writeFile(process.env.FF_BROWSER_RESULT_FILE, JSON.stringify({ status: 'observed', message: `Seller-side status checked: ${remoteState}.`, remote_state: remoteState,
      order_id: remoteStateOrderId, external_id: pack.previous_listing_id, listing_url: pack.previous_listing_url,
      evidence: { verified_at: new Date().toISOString(), url: page.url(), note: remoteStateNote } }));
    return { confirmed: true, remote_state: remoteState };
  }
  if (name === 'block_job') {
    const result = { status: mayHaveWritten ? 'needs_review' : 'blocked', message: String(args.reason).slice(0, 500) };
    await fs.writeFile(process.env.FF_BROWSER_RESULT_FILE, JSON.stringify(result));
    return { stopped: true, ...result };
  }
  throw new Error('Unknown tool');
}
const schema = (properties = {}, required = Object.keys(properties)) => ({ type: 'object', properties, required, additionalProperties: false });
const str = { type: 'string' }, bool = { type: 'boolean' };
const definitions = [
  ['seller_pack', 'Read the canonical seller pack and job instructions.', schema()],
  ['browser_observe', 'Observe Chrome with fresh element references.', schema()],
  ['browser_navigate', 'Navigate within the selected vendor only.', schema({ url: str })],
  ['remote_state', 'Record the observed seller-listing state. For sold, provide the seller order ID and exact evidence note.', schema({ state: { type: 'string', enum: ['active', 'ended', 'missing', 'sold', 'unknown', 'sign_in_required'] }, note: str, order_id: str }, ['state', 'note'])],
  ['browser_click', 'Click an observed Chrome element; flag listing writes. Paid/account actions are blocked.', schema({ ref: str, writes_listing: bool })],
  ['browser_fill', 'Fill a listing field. Use saved pack data; never put passwords here.', schema({ ref: str, value: str })],
  ['browser_select', 'Select an option by its observed label.', schema({ ref: str, label: str })],
  ['browser_upload', 'Upload only seller-pack photographs by index.', schema({ ref: str, image_indexes: { type: 'array', items: { type: 'integer' } } })],
  ['env_login', 'Fill the selected vendor login from the configured local .env.local file without exposing credentials. For two-stage forms provide the currently visible field only.', schema({ username_ref: str, password_ref: str }, [])],
  ['confirm_listing', 'Read back the item page, verify canonical title and price, and persist the real item URL/ID. Call only after remote live state is confirmed.', schema({ url: str, external_id: str })],
  ['confirm_observation', 'Record a verified seller-side listing observation. A sold state requires an order ID.', schema()],
  ['block_job', 'Stop with a precise MFA, CAPTCHA, credentials, seller-policy, account or uncertain-publication blocker.', schema({ reason: str })],
].map(([name, description, inputSchema]) => ({ name, description, inputSchema }));
const lines = readline.createInterface({ input: process.stdin });
// Serialize calls: each element reference belongs to one page observation.
for await (const line of lines) {
  let msg;
  try {
    msg = JSON.parse(line);
    if (msg.id === undefined) continue;
    let result;
    if (msg.method === 'initialize') result = { protocolVersion: '2024-11-05', capabilities: { tools: {} }, serverInfo: { name: 'flipflop-chrome', version: '1.0.0' } };
    else if (msg.method === 'tools/list') result = { tools: definitions };
    else if (msg.method === 'tools/call') {
      try { result = { content: [{ type: 'text', text: JSON.stringify(await run(msg.params.name, msg.params.arguments || {})) }] }; }
      catch (e) {
        // CLI exceptions may contain the credential-bearing subprocess result.
        const message = e.code || e.stdout || e.stderr ? 'Browser command failed; check local authentication without printing secrets.' : String(e.message);
        result = { isError: true, content: [{ type: 'text', text: message }] };
      }
    } else if (msg.method === 'ping') result = {};
    else { process.stdout.write(JSON.stringify({ jsonrpc: '2.0', id: msg.id, error: { code: -32601, message: 'Method not found' } }) + '\n'); continue; }
    process.stdout.write(JSON.stringify({ jsonrpc: '2.0', id: msg.id, result }) + '\n');
  } catch { if (msg?.id !== undefined) process.stdout.write(JSON.stringify({ jsonrpc: '2.0', id: msg.id, error: { code: -32603, message: 'Browser worker request failed' } }) + '\n'); }
}
if (context) await context.close();
