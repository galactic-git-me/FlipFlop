# Instructions

- Following Playwright test failed.
- Explain why, be concise, respect Playwright best practices.
- Provide a snippet of code with the fix, if possible.

# Test info

- Name: app-flows.spec.ts >> sidebar navigation smoke across primary app pages
- Location: tests/e2e/app-flows.spec.ts:219:5

# Error details

```
Test timeout of 45000ms exceeded.
```

```
Error: locator.click: Test timeout of 45000ms exceeded.
Call log:
  - waiting for getByRole('link', { name: 'Sourcing' })

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
  122 |     if (path === '/api/settings' && method === 'GET') return json(route, 200, settings);
  123 |     if (path === '/api/settings' && method === 'PUT') {
  124 |       Object.assign(settings, req.postDataJSON() ?? {});
  125 |       return json(route, 200, settings);
  126 |     }
  127 | 
  128 |     // Sources endpoints
  129 |     if (path === '/api/sources' && method === 'GET') return json(route, 200, sources);
  130 |     if (path === '/api/sources/health' && method === 'GET') return json(route, 200, { avg_health_score: 95, items: sources.map((s) => ({ id: s.id, name: s.name, enabled: s.enabled, health_score: 95, consecutive_failures: 0, zero_results_streak: 0, cooldown_until: null, last_error: null })) });
  131 |     if (path === '/api/sources' && method === 'POST') {
  132 |       const body = req.postDataJSON() as Partial<Source>;
  133 |       const created: Source = {
  134 |         id: nextSourceId++,
  135 |         name: body.name || `Source ${nextSourceId}`,
  136 |         url: body.url || '',
  137 |         source_type: (body.source_type as 'api' | 'scrape') || 'scrape',
  138 |         enabled: body.enabled ?? true,
  139 |         config: body.config || {},
  140 |         listings_found_total: 0,
  141 |         listings_found_last_run: 0,
  142 |         last_scraped_at: null,
  143 |         last_error: null,
  144 |       };
  145 |       sources = [...sources, created];
  146 |       return json(route, 201, created);
  147 |     }
  148 |     const sourcePatch = path.match(/^\/api\/sources\/(\d+)$/);
  149 |     if (sourcePatch && method === 'PATCH') {
  150 |       const id = Number(sourcePatch[1]);
  151 |       const body = req.postDataJSON() as Partial<Source>;
  152 |       const idx = sources.findIndex((s) => s.id === id);
  153 |       if (idx >= 0) {
  154 |         sources[idx] = { ...sources[idx], ...body };
  155 |         return json(route, 200, sources[idx]);
  156 |       }
  157 |       return json(route, 404, { detail: 'Source not found' });
  158 |     }
  159 |     const sourceDelete = path.match(/^\/api\/sources\/(\d+)$/);
  160 |     if (sourceDelete && method === 'DELETE') {
  161 |       const id = Number(sourceDelete[1]);
  162 |       sources = sources.filter((s) => s.id !== id);
  163 |       return json(route, 204, {});
  164 |     }
  165 |     const sourceTrigger = path.match(/^\/api\/sources\/(\d+)\/scrape$/);
  166 |     if (sourceTrigger && method === 'POST') return json(route, 200, { ok: true, queued: true });
  167 | 
  168 |     // Source search terms endpoints
  169 |     if (path === '/api/source-search-terms' && method === 'GET') {
  170 |       const scope = url.searchParams.get('scope');
  171 |       const scoped = scope ? terms.filter((t) => t.scope === scope) : terms;
  172 |       return json(route, 200, {
  173 |         items: scoped,
  174 |         groups: [...new Set(scoped.map((t) => t.group_name))].sort(),
  175 |         scopes: [...new Set(terms.map((t) => t.scope))].sort(),
  176 |       });
  177 |     }
  178 |     if (path === '/api/source-search-terms' && method === 'POST') {
  179 |       const body = req.postDataJSON() as Partial<SearchTerm>;
  180 |       const created: SearchTerm = {
  181 |         id: nextTermId++,
  182 |         scope: body.scope || 'cases',
  183 |         group_name: body.group_name || 'Custom',
  184 |         term: body.term || `term-${nextTermId}`,
  185 |         source_names: body.source_names || [],
  186 |         attributes: body.attributes || {},
  187 |         enabled: body.enabled ?? true,
  188 |         created_at: nowIso(),
  189 |       };
  190 |       terms = [...terms, created];
  191 |       return json(route, 201, created);
  192 |     }
  193 |     const termPatch = path.match(/^\/api\/source-search-terms\/(\d+)$/);
  194 |     if (termPatch && method === 'PATCH') {
  195 |       const id = Number(termPatch[1]);
  196 |       const body = req.postDataJSON() as Partial<SearchTerm>;
  197 |       const idx = terms.findIndex((t) => t.id === id);
  198 |       if (idx >= 0) {
  199 |         terms[idx] = { ...terms[idx], ...body };
  200 |         return json(route, 200, terms[idx]);
  201 |       }
  202 |       return json(route, 404, { detail: 'Search term not found' });
  203 |     }
  204 |     const termDelete = path.match(/^\/api\/source-search-terms\/(\d+)$/);
  205 |     if (termDelete && method === 'DELETE') {
  206 |       const id = Number(termDelete[1]);
  207 |       terms = terms.filter((t) => t.id !== id);
  208 |       return json(route, 204, {});
  209 |     }
  210 | 
  211 |     return json(route, 200, {});
  212 |   });
  213 | }
  214 | 
  215 | test.beforeEach(async ({ page }) => {
  216 |   await installApiMocks(page);
  217 | });
  218 | 
  219 | test('sidebar navigation smoke across primary app pages', async ({ page }) => {
  220 |   await page.goto('/');
  221 | 
> 222 |   await page.getByRole('link', { name: 'Sourcing' }).click();
      |                                                      ^ Error: locator.click: Test timeout of 45000ms exceeded.
  223 |   await expect(page).toHaveURL(/\/opportunities$/);
  224 |   await expect(page.getByText('Sourcing')).toBeVisible();
  225 | 
  226 |   await page.getByRole('link', { name: 'Inventory' }).click();
  227 |   await expect(page).toHaveURL(/\/flips$/);
  228 |   await expect(page.getByText('Inventory_Command')).toBeVisible();
  229 | 
  230 |   await page.getByRole('link', { name: 'Marketplace' }).click();
  231 |   await expect(page).toHaveURL(/\/parts$/);
  232 | 
  233 |   await page.getByRole('link', { name: 'Playbooks' }).click();
  234 |   await expect(page).toHaveURL(/\/playbooks$/);
  235 | 
  236 |   await page.getByRole('link', { name: 'Analytics' }).click();
  237 |   await expect(page).toHaveURL(/\/intel$/);
  238 | 
  239 |   await page.getByRole('link', { name: 'Settings' }).click();
  240 |   await expect(page).toHaveURL(/\/settings$/);
  241 |   await expect(page.getByText('Loading settings…')).toHaveCount(0);
  242 | });
  243 | 
  244 | test('settings flow: tabs, source CRUD, term CRUD, source-term assignment', async ({ page }) => {
  245 |   await page.goto('/settings');
  246 |   await expect(page.getByText('Loading settings…')).toHaveCount(0);
  247 | 
  248 |   // Data Sources tab
  249 |   await page.getByRole('button', { name: 'Data Sources' }).click();
  250 |   await expect(page.getByText('Data Sources')).toBeVisible();
  251 | 
  252 |   await page.getByPlaceholder('Source name').fill('Temu Mirror');
  253 |   await page.getByPlaceholder('Source URL').fill('https://www.temu.com');
  254 |   await page.getByRole('button', { name: /Add Source/ }).click();
  255 |   await expect(page.getByText('Temu Mirror')).toBeVisible();
  256 | 
  257 |   // Toggle source off/on
  258 |   const toggleButtons = page.locator('button').filter({ hasText: '' });
  259 |   await toggleButtons.first().click();
  260 | 
  261 |   // Search Terms tab
  262 |   await page.getByRole('button', { name: 'Search Terms' }).click();
  263 |   await expect(page.getByText('Search Terms')).toBeVisible();
  264 | 
  265 |   await page.getByPlaceholder('New search term').fill('motherboard cpu combo');
  266 |   await page.getByRole('button', { name: /Add Term/ }).click();
  267 |   await expect(page.getByText('motherboard cpu combo')).toBeVisible();
  268 | 
  269 |   // Attach term to a source chip
  270 |   const termCard = page.locator('div').filter({ hasText: 'motherboard cpu combo' }).first();
  271 |   await termCard.getByRole('button', { name: 'eBay UK' }).click();
  272 | 
  273 |   // Disable term then delete term
  274 |   const termToggle = termCard.locator('button').first();
  275 |   await termToggle.click();
  276 |   await termCard.getByRole('button').last().click();
  277 |   await expect(page.getByText('motherboard cpu combo')).toHaveCount(0);
  278 | });
  279 | 
  280 | test('opportunities flow: filter panel, search, and scan trigger', async ({ page }) => {
  281 |   await page.goto('/opportunities');
  282 |   await expect(page.getByText('Loading…')).toHaveCount(0);
  283 | 
  284 |   await page.getByRole('button', { name: 'Filters' }).click();
  285 |   await page.getByPlaceholder('Search title, CPU, GPU, location…').fill('Ryzen');
  286 |   await expect(page.getByText('Ryzen 7 Build')).toBeVisible();
  287 | 
  288 |   await page.getByRole('button', { name: /Scan Sources|Scanning…/ }).click();
  289 |   await expect(page.getByRole('button', { name: /Scan Sources|Scanning…/ })).toBeVisible();
  290 | });
  291 | 
```