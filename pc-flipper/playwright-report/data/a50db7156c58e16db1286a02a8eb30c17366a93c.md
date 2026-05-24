# Instructions

- Following Playwright test failed.
- Explain why, be concise, respect Playwright best practices.
- Provide a snippet of code with the fix, if possible.

# Test info

- Name: app-flows.spec.ts >> app route coverage: primary user flows render without crash screen
- Location: tests/e2e/app-flows.spec.ts:58:5

# Error details

```
Error: expect(locator).toHaveCount(expected) failed

Locator:  getByRole('heading', { name: 'This page couldn’t load' })
Expected: 0
Received: 1
Timeout:  10000ms

Call log:
  - Expect "toHaveCount" with timeout 10000ms
  - waiting for getByRole('heading', { name: 'This page couldn’t load' })
    24 × locator resolved to 1 element
       - unexpected value "1"

```

# Page snapshot

```yaml
- generic [ref=e3]:
  - img [ref=e4]
  - heading "This page couldn’t load" [level=1] [ref=e6]
  - paragraph [ref=e7]: Reload to try again, or go back.
  - generic [ref=e8]:
    - button "Reload" [ref=e10] [cursor=pointer]
    - button "Back" [ref=e11] [cursor=pointer]
```

# Test source

```ts
  1  | import { expect, test, type Page, type Route } from '@playwright/test';
  2  | 
  3  | async function json(route: Route, status: number, payload: unknown) {
  4  |   await route.fulfill({
  5  |     status,
  6  |     contentType: 'application/json',
  7  |     body: JSON.stringify(payload),
  8  |     headers: {
  9  |       'access-control-allow-origin': '*',
  10 |       'access-control-allow-methods': 'GET,POST,PATCH,PUT,DELETE,OPTIONS',
  11 |       'access-control-allow-headers': '*',
  12 |     },
  13 |   });
  14 | }
  15 | 
  16 | async function installApiMocks(page: Page) {
  17 |   await page.route('**/*', async (route) => {
  18 |     const req = route.request();
  19 |     const method = req.method().toUpperCase();
  20 |     const path = new URL(req.url()).pathname.replace(/\/+$/, '');
  21 | 
  22 |     if (method === 'OPTIONS') return json(route, 200, {});
  23 |     if (path === '/health' && method === 'GET') return route.fulfill({ status: 200, contentType: 'application/json', body: JSON.stringify({ status: 'ok' }) });
  24 |     if (!path.includes('/api')) return route.continue();
  25 | 
  26 |     if (path === '/api/settings' && method === 'GET') return json(route, 200, { max_concurrent_flips: 1, auto_buy_autonomous: false, auto_buy_daily_limit: 3, ollama_base_url: 'http://localhost:11434', ollama_model: 'gemma3:4b', openrouter_api_key: '', openrouter_primary_model: 'google/gemma-4-31b-it:free', image_gen_enabled: true, image_gen_provider: 'pollinations', default_sell_platform: 'ebay', ebay_app_id: '' });
  27 |     if (path === '/api/settings' && method === 'PUT') return json(route, 200, { ok: true });
  28 |     if (path === '/api/sources' && method === 'GET') return json(route, 200, []);
  29 |     if (path === '/api/sources/health' && method === 'GET') return json(route, 200, { avg_health_score: 100, items: [] });
  30 |     if (path === '/api/source-search-terms' && method === 'GET') return json(route, 200, { items: [], groups: [], scopes: ['cases', 'flip_opportunities', 'accessories', 'upgrade_parts'] });
  31 |     if (path === '/api/listings' && method === 'GET') return json(route, 200, []);
  32 |     if (path === '/api/listings/stats' && method === 'GET') return json(route, 200, { total_listings: 0, gems_count: 0, avg_profit: 0 });
  33 |     if (path === '/api/swarms' && method === 'GET') return json(route, 200, []);
  34 |     if (path === '/api/swarms/scan/status' && method === 'GET') return json(route, 200, { running: false, total: 0, completed: 0, current_sites: [], sites: [], started_at: null, finished_at: null, total_found: 0, total_gems: 0 });
  35 |     if (path.endsWith('/trigger') && method === 'POST') return json(route, 200, { ok: true });
  36 |     if (path === '/api/flips' && method === 'GET') return json(route, 200, []);
  37 |     if (path === '/api/parts' && method === 'GET') return json(route, 200, []);
  38 |     if (path === '/api/parts/cases' && method === 'GET') return json(route, 200, []);
  39 |     if (path === '/api/playbooks' && method === 'GET') return json(route, 200, []);
  40 |     if (path === '/api/demand/summary' && method === 'GET') return json(route, 200, { total_listings: 0, total_gems: 0, gem_rate_pct: 0 });
  41 |     if (path === '/api/demand/auction-intel' && method === 'GET') return json(route, 200, []);
  42 |     if (path === '/api/intel/retrain-status' && method === 'GET') return json(route, 200, { retrain_ready: false, sold_flips_since: 0, checkpoint: 'none', last_flip_id: 0, updated_at: new Date().toISOString() });
  43 |     if (path === '/api/schedule' && method === 'GET') return json(route, 200, []);
  44 |     if (path.startsWith('/api/schedule/') && method === 'GET') return json(route, 200, []);
  45 |     if (path === '/api/search-telemetry/recent' && method === 'GET') return json(route, 200, { items: [] });
  46 |     if (path === '/api/search-telemetry/by-source' && method === 'GET') return json(route, 200, { summary: {}, items: {} });
  47 |     if (path === '/api/alerts' && method === 'GET') return json(route, 200, []);
  48 |     if (path === '/api/facebook/status' && method === 'GET') return json(route, 200, { exists: true, valid: true, expired: false, expiry_warning: false, message: 'ok' });
  49 | 
  50 |     return json(route, 200, {});
  51 |   });
  52 | }
  53 | 
  54 | test.beforeEach(async ({ page }) => {
  55 |   await installApiMocks(page);
  56 | });
  57 | 
  58 | test('app route coverage: primary user flows render without crash screen', async ({ page }) => {
  59 |   const routes = ['/', '/opportunities', '/chat', '/flips', '/parts', '/playbooks', '/selling', '/intel', '/logs', '/settings'];
  60 | 
  61 |   for (const route of routes) {
  62 |     await page.goto(route);
  63 |     await expect(page.locator('body')).toBeVisible();
> 64 |     await expect(page.getByRole('heading', { name: 'This page couldn’t load' })).toHaveCount(0);
     |                                                                                  ^ Error: expect(locator).toHaveCount(expected) failed
  65 |   }
  66 | });
  67 | 
```