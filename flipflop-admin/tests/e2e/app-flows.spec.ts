import { expect, test, type Page, type Route } from '@playwright/test';

async function json(route: Route, status: number, payload: unknown) {
  await route.fulfill({
    status,
    contentType: 'application/json',
    body: JSON.stringify(payload),
    headers: {
      'access-control-allow-origin': '*',
      'access-control-allow-methods': 'GET,POST,PATCH,PUT,DELETE,OPTIONS',
      'access-control-allow-headers': '*',
    },
  });
}

async function installApiMocks(page: Page) {
  await page.route('**/*', async (route) => {
    const req = route.request();
    const method = req.method().toUpperCase();
    const path = new URL(req.url()).pathname.replace(/\/+$/, '');

    if (method === 'OPTIONS') return json(route, 200, {});
    if (path === '/health' && method === 'GET') return route.fulfill({ status: 200, contentType: 'application/json', body: JSON.stringify({ status: 'ok' }) });
    if (!path.includes('/api')) return route.continue();

    if (path === '/api/settings' && method === 'GET') return json(route, 200, { max_concurrent_flips: 1, auto_buy_autonomous: false, auto_buy_daily_limit: 3, ollama_base_url: 'http://localhost:11434', ollama_model: process.env.NEXT_PUBLIC_OLLAMA_MODEL || '', openrouter_api_key: '', openrouter_primary_model: 'google/gemma-4-31b-it:free', image_gen_enabled: true, image_gen_provider: 'pollinations', default_sell_platform: 'ebay', ebay_app_id: '' });
    if (path === '/api/settings' && method === 'PUT') return json(route, 200, { ok: true });
    if (path === '/api/sources' && method === 'GET') return json(route, 200, []);
    if (path === '/api/sources/health' && method === 'GET') return json(route, 200, { avg_health_score: 100, items: [] });
    if (path === '/api/source-search-terms' && method === 'GET') return json(route, 200, { items: [], groups: [], scopes: ['cases', 'flip_opportunities', 'accessories', 'upgrade_parts'] });
    if (path === '/api/listings' && method === 'GET') return json(route, 200, []);
    if (path === '/api/listings/stats' && method === 'GET') return json(route, 200, { total_listings: 0, gems_count: 0, avg_profit: 0 });
    if (path === '/api/swarms' && method === 'GET') return json(route, 200, []);
    if (path === '/api/swarms/scan/status' && method === 'GET') return json(route, 200, { running: false, total: 0, completed: 0, current_sites: [], sites: [], started_at: null, finished_at: null, total_found: 0, total_gems: 0 });
    if (path.endsWith('/trigger') && method === 'POST') return json(route, 200, { ok: true });
    if (path === '/api/flips' && method === 'GET') return json(route, 200, []);
    if (path === '/api/parts' && method === 'GET') return json(route, 200, []);
    if (path === '/api/parts/cases' && method === 'GET') return json(route, 200, []);
    if (path === '/api/playbooks' && method === 'GET') return json(route, 200, []);
    if (path === '/api/playbooks/proposals' && method === 'GET') return json(route, 200, []);
    if (path === '/api/playbooks/experiments/summary' && method === 'GET') return json(route, 200, { variants: {} });
    if (path === '/api/playbooks/experiments/attribution' && method === 'GET') return json(route, 200, { window_days: 14, variants: {} });
    if (path === '/api/build-wizard/playbooks' && method === 'GET') return json(route, 200, []);
    if (path === '/api/demand/summary' && method === 'GET') return json(route, 200, { total_listings: 0, total_gems: 0, gem_rate_pct: 0 });
    if (path === '/api/demand/auction-intel' && method === 'GET') return json(route, 200, []);
    if (path === '/api/demand/external-signals' && method === 'GET') return json(route, 200, { summary: {}, items: {} });
    if (path === '/api/demand/pricing-multipliers' && method === 'GET') return json(route, 200, { window_days: 14, external_window_days: 3, internal_counts: {}, external_topic_strength: {}, multipliers: {} });
    if (path === '/api/intel/summary' && method === 'GET') return json(route, 200, { total_flips: 0, total_profit: 0, avg_profit: 0, avg_roi_pct: 0, avg_days_to_sell: 0, best_source: null, best_cpu_tier: null });
    if (path === '/api/intel/by-source' && method === 'GET') return json(route, 200, []);
    if (path === '/api/intel/by-cpu' && method === 'GET') return json(route, 200, []);
    if (path === '/api/intel/by-platform' && method === 'GET') return json(route, 200, []);
    if (path === '/api/intel/recommendations' && method === 'GET') return json(route, 200, []);
    if (path === '/api/intel/history' && method === 'GET') return json(route, 200, []);
    if (path === '/api/intel/retrain-status' && method === 'GET') return json(route, 200, { retrain_ready: false, sold_flips_since: 0, checkpoint: 'none', last_flip_id: 0, updated_at: new Date().toISOString() });
    if (path === '/api/intel/models/versions' && method === 'GET') return json(route, 200, { items: [] });
    if (path === '/api/intel/models/runs' && method === 'GET') return json(route, 200, { items: [] });
    if (path === '/api/schedule' && method === 'GET') return json(route, 200, []);
    if (path.startsWith('/api/schedule/') && method === 'GET') return json(route, 200, []);
    if (path === '/api/search-telemetry/recent' && method === 'GET') return json(route, 200, { items: [] });
    if (path === '/api/search-telemetry/by-source' && method === 'GET') return json(route, 200, { summary: {}, items: {} });
    if (path === '/api/alerts' && method === 'GET') return json(route, 200, []);
    if (path === '/api/facebook/status' && method === 'GET') return json(route, 200, { exists: true, valid: true, expired: false, expiry_warning: false, message: 'ok' });

    return json(route, 200, {});
  });
}

test.beforeEach(async ({ page }) => {
  await installApiMocks(page);
});

test('app route coverage: primary user flows render without crash screen', async ({ page }) => {
  const routes = ['/', '/opportunities', '/chat', '/flips', '/parts', '/playbooks', '/selling', '/intel', '/logs', '/settings'];

  for (const route of routes) {
    await page.goto(route);
    await expect(page.locator('body')).toBeVisible();
    await expect(page.getByRole('heading', { name: 'This page couldn’t load' })).toHaveCount(0);
  }
});
