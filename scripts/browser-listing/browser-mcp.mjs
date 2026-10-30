// Narrow, domain-scoped Chrome tools. Credentials never enter tool responses.
import fs from 'node:fs/promises';
import path from 'node:path';
import readline from 'node:readline';
import { createHash } from 'node:crypto';
import { createRequire } from 'node:module';
import { parseEnv } from 'node:util';

const job = JSON.parse(await fs.readFile(process.env.FF_BROWSER_JOB_FILE, 'utf8'));
const pack = job.payload;
const require = createRequire(path.join(process.env.FF_ADMIN_DIR, 'package.json'));
const { chromium } = require('playwright');
const domains = { onbuy: ['onbuy.com'], facebook_catalog: ['facebook.com'], vinted: ['vinted.co.uk'], google_shopping: ['google.com'] }[pack.channel];
let context, page, revision = 0, inspected = false, remoteState = 'unknown', mayHaveWritten = false;
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
function sellerAccountPage(url) {
  return (pack.channel === 'onbuy' && url.hostname === 'seller.onbuy.com') ||
    (pack.channel === 'facebook_catalog' && /\/marketplace\/you|\/commerce/.test(url.pathname)) ||
    (pack.channel === 'vinted' && /\/member|\/my_orders|\/my-orders|\/orders|\/transactions/.test(url.pathname)) ||
    (pack.channel === 'google_shopping' && url.hostname === 'merchants.google.com');
}
async function pageIdentity(itemId) {
  const text = await page.locator('body').innerText();
  const hrefs = await page.locator('a[href]').evaluateAll(nodes => nodes.map(n => n.href));
  const values = await page.locator('input:not([type="password"])').evaluateAll(nodes => nodes
    .filter(n => /search|find|keyword/i.test(`${n.type} ${n.name} ${n.placeholder} ${n.getAttribute('aria-label') || ''}`))
    .map(n => n.value || ''));
  const identified = Boolean(itemId) && (page.url().includes(itemId) || text.includes(itemId) || hrefs.some(h => h.includes(itemId)));
  const candidates = [itemId, pack.listing.sku, pack.listing.title].filter(Boolean);
  const searched = values.some(value => value && candidates.includes(value));
  return { text, identified, searched };
}
async function envLogin(args) {
  await browser();
  const username = args.username_ref ? element(args.username_ref) : null, password = args.password_ref ? element(args.password_ref) : null;
  if (!username && !password) throw new Error('Select the username or password field from the current observation');
  if (password && await password.getAttribute('type') !== 'password') throw new Error('Choose the actual password field');
  const prefix = { onbuy: 'FF_ONBUY', facebook_catalog: 'FF_FACEBOOK_MARKETPLACE', vinted: 'FF_VINTED', google_shopping: 'FF_GOOGLE_MERCHANT' }[pack.channel];
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
    action: job.operation === 'withdraw' ? 'Remove this physical build from sale and verify removal in the seller account. Never publish, update stock upward, or delete sold order history.' : ['inspect', 'sale_check'].includes(job.operation) ? 'Read the exact seller listing and order status only. Do not publish, edit, end, relist or delete. Use report_status; a sale requires the exact item ID and a paid seller order reference.' : 'Apply this saved canonical listing. Update active; relist ended; create only after confirming missing. Finish with confirm_listing.', 
    instructions: 'Check seller listings for this exact build before writing. Update active; relist ended; create only after confirming missing. No duplicate listings. Google requires Merchant Center onboarding and approval; do not treat a feed submission as a live listing. Delivery only: never enable pickup. Stop for fees, account creation, MFA, CAPTCHA or a vendor restriction. Use env_login; never request, print or copy secrets.' };
  if (name === 'browser_observe') return snapshot();
  if (name === 'browser_navigate') { await browser(); if (!allowed(args.url)) throw new Error('URL outside this vendor'); await page.goto(args.url); return snapshot(); }
  if (name === 'env_login') return envLogin(args);
  if (name === 'remote_state') {
    await browser();
    if (!revision) throw new Error('Observe the seller page before recording its state');
    if (!['unknown', 'sign_in_required'].includes(args.state)) {
      const { identified, searched } = await pageIdentity(String(args.external_id || pack.previous_listing_id || ''));
      if (args.state === 'missing' && (!sellerAccountPage(new URL(page.url())) || !searched))
        throw new Error('Search the seller account for the exact saved SKU or item ID before confirming a missing listing');
      if (['active', 'ended', 'sold'].includes(args.state) && !identified)
        throw new Error('Observe the exact vendor item ID before recording its state');
    }
    inspected = true; remoteState = args.state;
    return { recorded: true, state: args.state, note: args.note };
  }
  if (name === 'browser_click') {
    await browser();
    if (!inspected) throw new Error('First inspect seller listings and record the remote state');
    if (args.writes_listing && ['inspect', 'sale_check'].includes(job.operation)) throw new Error('This job is read-only; report seller status without changing the listing');
    if (args.writes_listing && !['active', 'ended', 'missing'].includes(remoteState)) throw new Error('Remote listing state must be verified before a listing write');
    const el = element(args.ref);
    const text = ((await el.innerText()) || await el.getAttribute('aria-label') || '').toLowerCase();
    if (['inspect', 'sale_check'].includes(job.operation) && /publish|save listing|delete|end listing|mark as sold|deactivate/.test(text)) throw new Error('Status checks cannot change or withdraw listings');
    if (/pay|purchase|subscribe|boost|promote|delete account|create account|grant access|change password|save password|change email/.test(text)) throw new Error('Paid service or account change requires separate operator review');
    await preflight();
    if (args.writes_listing) mayHaveWritten = true;
    await el.click();
    return snapshot();
  }
  if (name === 'browser_press') {
    await browser();
    if (!['Enter', 'Tab', 'Escape', 'ArrowDown', 'ArrowUp', 'Space'].includes(args.key)) throw new Error('Unsupported page key');
    const el = element(args.ref);
    if (['inspect', 'sale_check'].includes(job.operation) && ['Enter', 'Space'].includes(args.key)) {
      const descriptor = `${await el.getAttribute('type') || ''} ${await el.getAttribute('name') || ''} ${await el.getAttribute('placeholder') || ''} ${await el.getAttribute('aria-label') || ''}`;
      if (!/password|user|email|search|find|keyword/i.test(descriptor)) throw new Error('Status checks may submit only login or search fields');
    }
    await preflight();
    await el.press(args.key);
    return snapshot();
  }
  if (name === 'browser_fill') {
    await browser(); const el = element(args.ref);
    if (await el.getAttribute('type') === 'password') throw new Error('Use env_login for passwords');
    if (['inspect', 'sale_check'].includes(job.operation)) {
      const descriptor = `${await el.getAttribute('type') || ''} ${await el.getAttribute('name') || ''} ${await el.getAttribute('placeholder') || ''} ${await el.getAttribute('aria-label') || ''}`;
      if (!/search|find|keyword/i.test(descriptor)) throw new Error('Status checks may fill only seller-inventory search fields');
    }
    await el.fill(args.value); return { filled: true };
  }
  if (name === 'browser_select') {
    await browser(); const el = element(args.ref);
    if (['inspect', 'sale_check'].includes(job.operation)) {
      const descriptor = `${await el.getAttribute('name') || ''} ${await el.getAttribute('aria-label') || ''}`;
      if (!/filter|sort|search/i.test(descriptor)) throw new Error('Status checks may change only search or filter controls');
    }
    await el.selectOption({ label: args.label }); return snapshot();
  }
  if (name === 'browser_upload') {
    if (['inspect', 'sale_check', 'withdraw'].includes(job.operation)) throw new Error('This job cannot upload photographs');
    await browser(); const files = args.image_indexes.map(i => {
      if (!Number.isInteger(i) || i < 0 || i >= pack.listing.images.length) throw new Error('Choose photographs from the seller pack');
      return path.join(path.dirname(process.env.FF_BROWSER_JOB_FILE), `photo-${i}.jpg`);
    });
    await element(args.ref).setInputFiles(files); return snapshot();
  }
  if (name === 'report_status') {
    await browser(); await preflight();
    const url = new URL(page.url());
    const sellerContext = sellerAccountPage(url);
    const state = args.state;
    if (!['active', 'ended', 'missing', 'sold', 'unknown'].includes(state)) throw new Error('Unknown observed state');
    if (state !== 'active' && state !== 'unknown' && !sellerContext) throw new Error('Confirm this state inside the authenticated seller account, not from a public missing page');
    if (await page.locator('input[type="password"]:visible').count()) throw new Error('Seller sign-in is not complete');
    const itemId = String(args.external_id || pack.previous_listing_id || '');
    const { text, identified, searched } = await pageIdentity(itemId);
    if (state !== 'unknown' && state !== 'missing' && !identified) throw new Error('The exact vendor item identity must be visible in the observed page');
    if (state === 'missing' && !searched) throw new Error('Search the seller inventory for the exact saved item ID or build SKU before confirming it is missing');
    if (state === 'sold' && (pack.channel === 'google_shopping' || !args.order_id || !page.url().includes(args.order_id) || !text.includes(args.order_id) || !/paid|payment received|completed order|ready to ship/i.test(text))) throw new Error('Open the exact paid order detail showing the item ID and order reference; a sold label alone is not proof of sale');
    if (job.operation === 'withdraw' && !['ended', 'missing', 'sold'].includes(state)) throw new Error('Withdrawal must be confirmed before completing this job');
    const result = { status: 'observed', remote_state: state, external_id: itemId || null,
      listing_url: args.listing_url || pack.previous_listing_url || null, order_id: args.order_id || null,
      message: `Seller account observed: ${state}.`, evidence: { verified_at: new Date().toISOString(), url: page.url(),
        note: String(args.note).slice(0, 500), price: args.price ?? null, canonical_changed: args.canonical_changed || false,
        verification_kind: state === 'sold' ? 'seller_order' : 'seller_inventory', order_id: args.order_id || null,
        page_sha256: createHash('sha256').update(text).digest('hex') } };
    await fs.writeFile(process.env.FF_BROWSER_RESULT_FILE, JSON.stringify(result));
    return { recorded: true, state };
  }
  if (name === 'confirm_listing') {
    if (['inspect', 'sale_check', 'withdraw'].includes(job.operation)) throw new Error('Use report_status for this operation; do not publish');
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
  ['remote_state', 'Record the observed remote state. Search exact SKU/item ID in the seller account before declaring a listing missing.', schema({ state: { type: 'string', enum: ['active', 'ended', 'missing', 'sold', 'unknown', 'sign_in_required'] }, note: str, external_id: str }, ['state', 'note'])],
  ['browser_click', 'Click an observed Chrome element; flag listing writes. Paid/account actions are blocked.', schema({ ref: str, writes_listing: bool })],
  ['browser_fill', 'Fill a listing field. Use saved pack data; never put passwords here.', schema({ ref: str, value: str })],
  ['browser_press', 'Press a scoped page key on an observed element.', schema({ ref: str, key: { type: 'string', enum: ['Enter', 'Tab', 'Escape', 'ArrowDown', 'ArrowUp', 'Space'] } })],
  ['browser_select', 'Select an option by its observed label.', schema({ ref: str, label: str })],
  ['browser_upload', 'Upload only seller-pack photographs by index.', schema({ ref: str, image_indexes: { type: 'array', items: { type: 'integer' } } })],
  ['env_login', 'Fill the selected vendor login from the configured local .env.local file without exposing credentials. For two-stage forms provide the currently visible field only.', schema({ username_ref: str, password_ref: str }, [])],
  ['confirm_listing', 'Read back the item page, verify canonical title and price, and persist the real item URL/ID. Call only after remote live state is confirmed.', schema({ url: str, external_id: str })],
  ['report_status', 'Persist verified seller inventory or paid-order status. Public missing pages do not prove withdrawal or sale. Use after an inspect, sale-check or withdrawal job.', schema({ state: { type: 'string', enum: ['active', 'ended', 'missing', 'sold', 'unknown'] }, note: str, external_id: str, listing_url: str, order_id: str, price: { type: 'number' }, canonical_changed: bool }, ['state', 'note'])],
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
