# Instructions

- Following Playwright test failed.
- Explain why, be concise, respect Playwright best practices.
- Provide a snippet of code with the fix, if possible.

# Test info

- Name: app-flows.spec.ts >> settings flow: tabs, source CRUD, term CRUD, source-term assignment
- Location: tests/e2e/app-flows.spec.ts:244:5

# Error details

```
Error: expect(locator).toHaveCount(expected) failed

Locator:  getByText('Loading settings…')
Expected: 0
Received: 1
Timeout:  10000ms

Call log:
  - Expect "toHaveCount" with timeout 10000ms
  - waiting for getByText('Loading settings…')
    22 × locator resolved to 1 element
       - unexpected value "1"

```

# Page snapshot

```yaml
- generic [active] [ref=e1]:
  - complementary [ref=e2]:
    - generic [ref=e3]:
      - img "FlipFlop" [ref=e4]
      - paragraph [ref=e5]: Operational v1.0.4
    - button "NEW BUILD" [ref=e6] [cursor=pointer]:
      - img [ref=e7]
      - generic [ref=e8]: NEW BUILD
    - navigation [ref=e9]:
      - link "Dashboard" [ref=e10] [cursor=pointer]:
        - /url: /
        - img [ref=e11]
        - generic [ref=e16]: Dashboard
      - link "Sourcing" [ref=e17] [cursor=pointer]:
        - /url: /opportunities
        - img [ref=e18]
        - generic [ref=e21]: Sourcing
      - link "Build Wizard" [ref=e22] [cursor=pointer]:
        - /url: /chat
        - img [ref=e23]
        - generic [ref=e26]: Build Wizard
      - link "Inventory" [ref=e27] [cursor=pointer]:
        - /url: /flips
        - img [ref=e28]
        - generic [ref=e38]: Inventory
      - link "Playbooks" [ref=e39] [cursor=pointer]:
        - /url: /playbooks
        - img [ref=e40]
        - generic [ref=e42]: Playbooks
      - link "Marketplace" [ref=e43] [cursor=pointer]:
        - /url: /parts
        - img [ref=e44]
        - generic [ref=e48]: Marketplace
      - link "Sold Builds" [ref=e49] [cursor=pointer]:
        - /url: /selling
        - img [ref=e50]
        - generic [ref=e52]: Sold Builds
      - link "Analytics" [ref=e53] [cursor=pointer]:
        - /url: /intel
        - img [ref=e54]
        - generic [ref=e56]: Analytics
      - link "AI Insights" [ref=e57] [cursor=pointer]:
        - /url: /logs
        - img [ref=e58]
        - generic [ref=e66]: AI Insights
      - link "Settings" [ref=e67] [cursor=pointer]:
        - /url: /settings
        - img [ref=e68]
        - generic [ref=e71]: Settings
    - generic [ref=e72]:
      - img [ref=e74]
      - generic [ref=e77]:
        - paragraph [ref=e78]: Specialist Profile
        - paragraph [ref=e79]: Tier 3 Merchant
  - generic [ref=e80]:
    - banner [ref=e81]:
      - generic [ref=e82]:
        - img [ref=e83]
        - textbox "QUERY SETTINGS..." [ref=e86]
      - generic [ref=e87]:
        - img "FlipFlop" [ref=e90]
        - generic [ref=e91]:
          - img [ref=e92]
          - button "Notifications" [ref=e98]:
            - img [ref=e99]
          - img [ref=e102]
    - main [ref=e106]:
      - generic [ref=e107]:
        - img [ref=e108]
        - text: Loading settings…
  - alert [ref=e113]
  - generic [ref=e114]:
    - img [ref=e115]
    - generic [ref=e122]: Backend offline— check the configured API server
    - button "Retry" [ref=e123]:
      - img [ref=e124]
      - text: Retry
    - button [ref=e129]:
      - img [ref=e130]
```

# Test source

```ts
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
  222 |   await page.getByRole('link', { name: 'Sourcing' }).click();
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
> 246 |   await expect(page.getByText('Loading settings…')).toHaveCount(0);
      |                                                     ^ Error: expect(locator).toHaveCount(expected) failed
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