# Instructions

- Following Playwright test failed.
- Explain why, be concise, respect Playwright best practices.
- Provide a snippet of code with the fix, if possible.

# Test info

- Name: app-flows.spec.ts >> opportunities flow: filter panel, search, and scan trigger
- Location: tests/e2e/app-flows.spec.ts:280:5

# Error details

```
Test timeout of 45000ms exceeded.
```

```
Error: locator.click: Test timeout of 45000ms exceeded.
Call log:
  - waiting for getByRole('button', { name: 'Filters' })

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
> 284 |   await page.getByRole('button', { name: 'Filters' }).click();
      |                                                       ^ Error: locator.click: Test timeout of 45000ms exceeded.
  285 |   await page.getByPlaceholder('Search title, CPU, GPU, location…').fill('Ryzen');
  286 |   await expect(page.getByText('Ryzen 7 Build')).toBeVisible();
  287 | 
  288 |   await page.getByRole('button', { name: /Scan Sources|Scanning…/ }).click();
  289 |   await expect(page.getByRole('button', { name: /Scan Sources|Scanning…/ })).toBeVisible();
  290 | });
  291 | 
```