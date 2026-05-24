import { expect, test, type Page, type Route } from '@playwright/test';

type Source = {
  id: number;
  name: string;
  url: string;
  source_type: 'api' | 'scrape';
  enabled: boolean;
  config?: Record<string, unknown>;
  listings_found_total?: number;
  listings_found_last_run?: number;
  last_scraped_at?: string | null;
  last_error?: string | null;
};

type SearchTerm = {
  id: number;
  scope: string;
  group_name: string;
  term: string;
  source_names: string[];
  attributes: Record<string, unknown>;
  enabled: boolean;
  created_at: string;
};

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

function nowIso() {
  return new Date().toISOString();
}

async function installApiMocks(page: Page) {
  let nextSourceId = 3;
  let nextTermId = 3;

  let sources: Source[] = [
    { id: 1, name: 'eBay UK', url: 'https://www.ebay.co.uk', source_type: 'scrape', enabled: true, listings_found_total: 12, listings_found_last_run: 2, last_scraped_at: nowIso(), last_error: null, config: {} },
    { id: 2, name: 'Facebook Marketplace', url: 'https://www.facebook.com/marketplace', source_type: 'scrape', enabled: true, listings_found_total: 8, listings_found_last_run: 1, last_scraped_at: nowIso(), last_error: null, config: {} },
  ];

  let terms: SearchTerm[] = [
    { id: 1, scope: 'cases', group_name: 'Fish Tank / Panoramic Cases', term: 'fish tank pc case', source_names: ['eBay UK'], attributes: {}, enabled: true, created_at: nowIso() },
    { id: 2, scope: 'flip_opportunities', group_name: 'General', term: 'desktop pc', source_names: ['eBay UK', 'Facebook Marketplace'], attributes: {}, enabled: true, created_at: nowIso() },
  ];

  const settings = {
    max_concurrent_flips: 1,
    default_sell_platform: 'ebay',
    auto_buy_autonomous: false,
    auto_buy_daily_limit: 3,
    ollama_base_url: 'http://localhost:11434',
    ollama_model: 'gemma3:4b',
    openrouter_api_key: '',
    openrouter_primary_model: 'google/gemma-4-31b-it:free',
    ebay_app_id: '',
    image_gen_enabled: true,
    image_gen_provider: 'pollinations',
  };

  await page.route('**/*', async (route) => {
    const req = route.request();
    const method = req.method().toUpperCase();
    const url = new URL(req.url());
    const path = url.pathname.replace(/\/+$/, '');

    if (method === 'OPTIONS') return json(route, 200, {});
    if (path === '/health' && method === 'GET') return route.fulfill({ status: 200, contentType: 'application/json', body: JSON.stringify({ status: 'ok' }) });
    if (!path.includes('/api')) return route.continue();

    if (path === '/api/listings' && method === 'GET') {
      return json(route, 200, [{ id: 101, title: 'Ryzen 7 Build', source_name: 'eBay UK', url: 'https://www.ebay.co.uk/itm/123', image_urls: [], classification: 'gem', gem_score: 88, estimated_profit: 120, estimated_resale: 450, estimated_upgrade_cost: 80, price: 250, cpu: 'Ryzen 7 5800X', gpu: 'RTX 3060', ram_gb: 16, first_seen_at: nowIso() }]);
    }
    if (path === '/api/listings/stats' && method === 'GET') return json(route, 200, { total_listings: 1, gems_count: 1, avg_profit: 120 });
    if (path === '/api/swarms' && method === 'GET') return json(route, 200, []);
    if (path === '/api/swarms/scan/status' && method === 'GET') return json(route, 200, { running: false, total: 0, completed: 0, current_sites: [], sites: [], started_at: null, finished_at: null, total_found: 0, total_gems: 0 });
    if (path.endsWith('/trigger') && method === 'POST') return json(route, 200, { ok: true });
    if (path === '/api/flips' && method === 'GET') return json(route, 200, []);
    if (path === '/api/flips' && method === 'POST') return json(route, 200, { ok: true });
    if (path === '/api/parts' && method === 'GET') return json(route, 200, []);
    if (path === '/api/parts/cases' && method === 'GET') return json(route, 200, []);
    if (path === '/api/playbooks' && method === 'GET') return json(route, 200, []);
    if (path === '/api/demand/summary' && method === 'GET') return json(route, 200, { total_listings: 1, total_gems: 1, gem_rate_pct: 100 });
    if (path === '/api/demand/auction-intel' && method === 'GET') return json(route, 200, []);
    if (path === '/api/intel/retrain-status' && method === 'GET') return json(route, 200, { retrain_ready: false, sold_flips_since: 0, checkpoint: 'none', last_flip_id: 0, updated_at: nowIso() });
    if (path === '/api/schedule' && method === 'GET') return json(route, 200, []);
    if (path.startsWith('/api/schedule/') && method === 'GET') return json(route, 200, []);
    if (path === '/api/search-telemetry/recent' && method === 'GET') return json(route, 200, { items: [] });
    if (path === '/api/search-telemetry/by-source' && method === 'GET') return json(route, 200, { summary: {}, items: {} });
    if (path === '/api/alerts' && method === 'GET') return json(route, 200, []);
    if (path === '/api/facebook/status' && method === 'GET') return json(route, 200, { exists: true, valid: true, expired: false, expiry_warning: false, message: 'ok' });

    if (path === '/api/settings' && method === 'GET') return json(route, 200, settings);
    if (path === '/api/settings' && method === 'PUT') {
      Object.assign(settings, req.postDataJSON() ?? {});
      return json(route, 200, settings);
    }

    if (path === '/api/sources' && method === 'GET') return json(route, 200, sources);
    if (path === '/api/sources/health' && method === 'GET') return json(route, 200, { avg_health_score: 95, items: sources.map((s) => ({ id: s.id, name: s.name, enabled: s.enabled, health_score: 95, consecutive_failures: 0, zero_results_streak: 0, cooldown_until: null, last_error: null })) });
    if (path === '/api/sources' && method === 'POST') {
      const body = req.postDataJSON() as Partial<Source>;
      const created: Source = { id: nextSourceId++, name: body.name || `Source ${nextSourceId}`, url: body.url || '', source_type: (body.source_type as 'api' | 'scrape') || 'scrape', enabled: body.enabled ?? true, config: body.config || {}, listings_found_total: 0, listings_found_last_run: 0, last_scraped_at: null, last_error: null };
      sources = [...sources, created];
      return json(route, 201, created);
    }
    const sourcePatch = path.match(/^\/api\/sources\/(\d+)$/);
    if (sourcePatch && method === 'PATCH') {
      const id = Number(sourcePatch[1]);
      const body = req.postDataJSON() as Partial<Source>;
      const idx = sources.findIndex((s) => s.id === id);
      if (idx >= 0) {
        sources[idx] = { ...sources[idx], ...body };
        return json(route, 200, sources[idx]);
      }
      return json(route, 404, { detail: 'Source not found' });
    }
    const sourceDelete = path.match(/^\/api\/sources\/(\d+)$/);
    if (sourceDelete && method === 'DELETE') {
      const id = Number(sourceDelete[1]);
      sources = sources.filter((s) => s.id !== id);
      return json(route, 204, {});
    }
    const sourceTrigger = path.match(/^\/api\/sources\/(\d+)\/scrape$/);
    if (sourceTrigger && method === 'POST') return json(route, 200, { ok: true, queued: true });

    if (path === '/api/source-search-terms' && method === 'GET') {
      const scope = url.searchParams.get('scope');
      const scoped = scope ? terms.filter((t) => t.scope === scope) : terms;
      return json(route, 200, { items: scoped, groups: [...new Set(scoped.map((t) => t.group_name))].sort(), scopes: [...new Set(terms.map((t) => t.scope))].sort() });
    }
    if (path === '/api/source-search-terms' && method === 'POST') {
      const body = req.postDataJSON() as Partial<SearchTerm>;
      const created: SearchTerm = { id: nextTermId++, scope: body.scope || 'cases', group_name: body.group_name || 'Custom', term: body.term || `term-${nextTermId}`, source_names: body.source_names || [], attributes: body.attributes || {}, enabled: body.enabled ?? true, created_at: nowIso() };
      terms = [...terms, created];
      return json(route, 201, created);
    }
    const termPatch = path.match(/^\/api\/source-search-terms\/(\d+)$/);
    if (termPatch && method === 'PATCH') {
      const id = Number(termPatch[1]);
      const body = req.postDataJSON() as Partial<SearchTerm>;
      const idx = terms.findIndex((t) => t.id === id);
      if (idx >= 0) {
        terms[idx] = { ...terms[idx], ...body };
        return json(route, 200, terms[idx]);
      }
      return json(route, 404, { detail: 'Search term not found' });
    }
    const termDelete = path.match(/^\/api\/source-search-terms\/(\d+)$/);
    if (termDelete && method === 'DELETE') {
      const id = Number(termDelete[1]);
      terms = terms.filter((t) => t.id !== id);
      return json(route, 204, {});
    }

    return json(route, 200, {});
  });
}

test.beforeEach(async ({ page }) => {
  await installApiMocks(page);
});

test('route-level smoke for primary pages', async ({ page }) => {
  const routes = ['/', '/opportunities', '/flips', '/parts', '/playbooks', '/intel', '/settings', '/logs'];
  for (const route of routes) {
    await page.goto(route);
    await expect(page.locator('body')).toBeVisible();
  }
});

test('settings flow: source and term management', async ({ page }) => {
  await page.goto('/settings');
  await expect(page.getByRole('heading', { name: 'Settings' })).toBeVisible();

  await page.getByRole('button', { name: 'Data Sources' }).click();
  await page.getByPlaceholder('Source name').fill('Temu Mirror');
  await page.getByPlaceholder('Source URL').fill('https://www.temu.com');
  await page.getByRole('button', { name: /Add Source/ }).click();
  await expect(page.getByText('Temu Mirror')).toBeVisible();

  await page.getByRole('button', { name: 'Search Terms' }).click();
  await page.getByPlaceholder('New search term').fill('motherboard cpu combo');
  await page.getByRole('button', { name: /Add Term/ }).click();
  await expect(page.getByText('motherboard cpu combo')).toBeVisible();

  const termRow = page.locator('div.p-3.rounded-xl').filter({ hasText: 'motherboard cpu combo' }).first();
  await termRow.getByRole('button', { name: 'eBay UK' }).click();
  await termRow.locator('button').nth(1).click();
  await expect(page.getByText('motherboard cpu combo')).toHaveCount(0);
});

test('opportunities flow: filter search and scan trigger', async ({ page }) => {
  await page.goto('/opportunities');
  await expect(page.getByRole('heading', { name: 'Sourcing' })).toBeVisible();
  await page.getByPlaceholder('Search title, CPU, GPU, location…').fill('Ryzen');
  await expect(page.getByText('Ryzen 7 Build')).toBeVisible();
  await page.getByRole('button', { name: /Scan Sources|Scanning…/ }).click();
});
