import test from 'node:test';
import assert from 'node:assert/strict';
import fs from 'node:fs/promises';
import os from 'node:os';
import path from 'node:path';
import { spawn } from 'node:child_process';
import { fileURLToPath } from 'node:url';
import readline from 'node:readline';

// Protocol regression tests use a fake browser. No vendor or credentials are read.
async function harness(t) {
  const dir = await fs.mkdtemp(path.join(os.tmpdir(), 'ff-browser-test-'));
  const admin = path.join(dir, 'admin');
  const mod = path.join(admin, 'node_modules/playwright');
  await fs.mkdir(mod, { recursive: true });
  await fs.writeFile(path.join(admin, 'package.json'), '{}');
  await fs.writeFile(path.join(mod, 'index.js'), `
  let current = 'https://www.vinted.co.uk/member/items';
  const page = { url: () => current, goto: async u => { current = u; }, title: async () => 'PROMETHEUS', mainFrame: () => ({}),
    locator: () => ({ innerText: async () => 'PROMETHEUS Gaming PC £1,400.00 available', evaluateAll: async () => [],
      getAttribute: async () => 'text', fill: async () => {}, click: async () => {}, selectOption: async () => {}, setInputFiles: async () => {} }) };
  exports.chromium = { launchPersistentContext: async () => ({ route: async () => {}, pages: () => [page], on: () => {}, close: async () => {} }) };
  `);
  const jobFile = path.join(dir, 'seller-pack.json'), resultFile = path.join(dir, 'result.json');
  const credentialsFile = path.join(dir, '.env.local');
  await fs.writeFile(credentialsFile, 'FF_VINTED_USERNAME="fixture-user"\nFF_VINTED_PASSWORD="fixture-private-value"\n');
  await fs.writeFile(jobFile, JSON.stringify({ id: 1, lease_token: 'lease', operation: 'publish', payload: {
    channel: 'vinted', seller_url: 'https://www.vinted.co.uk/member/items', listing: { title: 'PROMETHEUS Gaming PC', price: 1400, images: [] },
  } }));
  const child = spawn(process.execPath, [fileURLToPath(new URL('./browser-mcp.mjs', import.meta.url))], {
    env: { ...process.env, FF_ADMIN_DIR: admin, FF_BROWSER_JOB_FILE: jobFile, FF_BROWSER_RESULT_FILE: resultFile,
      FF_CREDENTIALS_FILE: credentialsFile, FF_CHROME_PROFILE: path.join(dir, 'profile'), FF_WORKER_API: 'http://127.0.0.1:1' }, stdio: ['pipe', 'pipe', 'pipe'],
  });
  let seq = 0;
  const pending = new Map();
  const lines = readline.createInterface({ input: child.stdout });
  lines.on('line', line => { const msg = JSON.parse(line); pending.get(msg.id)?.(msg.result); pending.delete(msg.id); });
  t.after(async () => {
    child.stdin.end();
    await new Promise(resolve => child.once('exit', resolve));
    await fs.rm(dir, { recursive: true, force: true });
  });
  const rpc = (method, params = {}) => new Promise(resolve => { const id = ++seq; pending.set(id, resolve); child.stdin.write(JSON.stringify({ jsonrpc: '2.0', id, method, params }) + '\n'); });
  const tool = (name, args) => rpc('tools/call', { name, arguments: args });
  return { rpc, tool, resultFile };
}

test('MCP exposes only scoped browser tools and seller pack data', async t => {
  const { rpc, tool } = await harness(t);
  assert.equal((await rpc('initialize')).serverInfo.name, 'flipflop-chrome');
  const tools = (await rpc('tools/list')).tools.map(t => t.name);
  assert(tools.includes('env_login') && tools.includes('confirm_listing'));
  assert(!tools.some(t => /eval|exec|shell|password|get_item/.test(t)));
  const pack = JSON.parse((await tool('seller_pack', {})).content[0].text);
  assert.equal(pack.listing.price, 1400);
  assert(!JSON.stringify(pack).includes('fixture-private-value'));
});

test('navigation rejects external and insecure credential destinations', async t => {
  const { tool } = await harness(t);
  for (const url of ['https://evil.test/items/1', 'https://vinted.co.uk.evil.test/items/1', 'http://www.vinted.co.uk/items/1', 'https://user:secret@www.vinted.co.uk/items/1']) {
    const result = await tool('browser_navigate', { url });
    assert.equal(result.isError, true);
  }
});

test('listing writes require remote reconciliation and a live backend lease', async t => {
  const { tool } = await harness(t);
  await tool('browser_observe', {});
  assert.equal((await tool('browser_click', { ref: '1-0', writes_listing: true })).isError, true);
  await tool('remote_state', { state: 'unknown', note: 'Cannot confirm' });
  assert.equal((await tool('browser_click', { ref: '1-0', writes_listing: true })).isError, true);
  await tool('remote_state', { state: 'missing', note: 'No matching item' });
  assert.equal((await tool('browser_click', { ref: '1-0', writes_listing: true })).isError, true); // lease endpoint unavailable
});

test('blocked outcomes persist without pretending to publish', async t => {
  const { tool, resultFile } = await harness(t);
  const result = await tool('block_job', { reason: 'MFA required' });
  assert.equal(result.isError, undefined);
  const saved = JSON.parse(await fs.readFile(resultFile, 'utf8'));
  assert.equal(saved.status, 'blocked');
  assert.equal(saved.listing_url, undefined);
});

test('arbitrary selectors cannot be injected through element references', async t => {
  const { tool } = await harness(t);
  await tool('browser_observe', {});
  const result = await tool('browser_fill', { ref: '1-0"] input[type=password], [x="', value: 'anything' });
  assert.equal(result.isError, true);
});


test('credential fill reads the private local file without returning either value', async t => {
  const { tool } = await harness(t);
  await tool('browser_observe', {});
  const result = await tool('env_login', { username_ref: '1-0' });
  assert.equal(result.isError, undefined);
  assert.equal(JSON.parse(result.content[0].text).filled, true);
  assert(!JSON.stringify(result).includes('fixture-user'));
  assert(!JSON.stringify(result).includes('fixture-private-value'));
});
