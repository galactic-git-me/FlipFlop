# Instructions

- Following Playwright test failed.
- Explain why, be concise, respect Playwright best practices.
- Provide a snippet of code with the fix, if possible.

# Test info

- Name: cross-listing.spec.ts >> keeps manual-only destinations manual and links storefront without duplicating its product
- Location: tests\e2e\cross-listing.spec.ts:164:5

# Error details

```
Error: expect(locator).toBeVisible() failed

Locator: getByText('Manual action required', { exact: true })
Expected: visible
Timeout: 10000ms
Error: element(s) not found

Call log:
  - Expect "toBeVisible" with timeout 10000ms
  - waiting for getByText('Manual action required', { exact: true })

```

```yaml
- complementary:
  - img "FlipFlop"
  - navigation:
    - link "Sourcing":
      - /url: /sourcing
    - link "Pre-Built":
      - /url: /builds
    - link "Custom Builds":
      - /url: /configurator-config
    - link "Curated Builds":
      - /url: /pc-builder
    - link "Inventory":
      - /url: /inventory
    - link "Demand":
      - /url: /demand
    - link "Cross-listing":
      - /url: /cross-listing
    - link "3D Assets":
      - /url: /cases-3d-priority
    - link "Problems":
      - /url: /problems
- banner:
  - textbox "QUERY MARKET DATA..."
  - img "FlipFlop"
  - button "Source activity"
  - button "Favourites"
  - button "Notifications"
  - button "Price alerts"
  - button "Settings"
- main:
  - text: Inventory synchronisation
  - heading "Cross-listing" [level=1]
  - paragraph: Review canonical build data, prepare channel payloads, and keep unique computers from selling twice.
  - button "Refresh listings"
  - text: eBay UK API
  - paragraph: Uses the existing seller OAuth and manual-build eBay operations.
  - text: FlipFlop.shop API
  - paragraph: Reuses the canonical storefront product; duplicate products are not created here.
  - text: OnBuy Manual
  - paragraph: Seller API/feed onboarding is not configured in this app. Manual listing pack only.
  - text: Amazon Requires Approval
  - paragraph: SP-API requires seller authorization, Product Listing role, marketplace/category requirements and identifiers.
  - text: Facebook catalog Manual
  - paragraph: Catalog/feed route must be configured; personal Marketplace automation is not supported.
  - text: Vinted Manual
  - paragraph: No approved seller integration is configured. Manual-assist export only; no consumer-account automation.
  - textbox "Search listings":
    - /placeholder: Search title, build ID or external ID…
  - combobox "Source filter":
    - option "All sources" [selected]
    - option "eBay UK"
    - option "FlipFlop.shop"
  - combobox "Status filter":
    - option "All statuses" [selected]
    - option "Live"
    - option "Draft"
    - option "Sold"
    - option "Ended"
    - option "Unavailable"
    - option "Failed"
  - combobox "Sort listings":
    - option "Recently updated" [selected]
    - option "Highest price"
    - option "Title"
  - button "Select all filtered (4)"
  - text: 1 selected · refreshed 21:53
  - table:
    - rowgroup:
      - row "Listing Source Price / stock Status Updated":
        - columnheader
        - columnheader "Listing"
        - columnheader "Source"
        - columnheader "Price / stock"
        - columnheader "Status"
        - columnheader "Updated"
        - columnheader
    - rowgroup:
      - row "Select Atlas Gaming PC RTX 3060 Atlas Gaming PC RTX 3060 Build 42 · EBAY-42 eBay UK £499.00 Qty 1 · Used Live 10/09/2026 Review":
        - cell "Select Atlas Gaming PC RTX 3060":
          - button "Select Atlas Gaming PC RTX 3060"
        - cell "Atlas Gaming PC RTX 3060 Build 42 · EBAY-42"
        - cell "eBay UK"
        - cell "£499.00 Qty 1 · Used"
        - cell "Live"
        - cell "10/09/2026"
        - cell "Review":
          - button "Review"
      - row "Select Atlas Gaming PC RTX 3060 Atlas Gaming PC RTX 3060 Build 42 · 420 FlipFlop.shop £499.00 Qty 1 · Used Live 10/09/2026 Review":
        - cell "Select Atlas Gaming PC RTX 3060":
          - button "Select Atlas Gaming PC RTX 3060"
        - cell "Atlas Gaming PC RTX 3060 Build 42 · 420"
        - cell "FlipFlop.shop"
        - cell "£499.00 Qty 1 · Used"
        - cell "Live"
        - cell "10/09/2026"
        - cell "Review":
          - button "Review"
      - row "Select Borealis Workstation Borealis Workstation Build 43 · EBAY-43-draft eBay UK £699.00 Qty 1 · Used Draft 09/09/2026 Review":
        - cell "Select Borealis Workstation":
          - button "Select Borealis Workstation"
        - cell "Borealis Workstation Build 43 · EBAY-43-draft"
        - cell "eBay UK"
        - cell "£699.00 Qty 1 · Used"
        - cell "Draft"
        - cell "09/09/2026"
        - cell "Review":
          - button "Review"
      - row "Select Borealis Workstation Borealis Workstation Build 43 · 430 FlipFlop.shop £699.00 Qty 1 · Used Live 09/09/2026 Review":
        - cell "Select Borealis Workstation":
          - button "Select Borealis Workstation"
        - cell "Borealis Workstation Build 43 · 430"
        - cell "FlipFlop.shop"
        - cell "£699.00 Qty 1 · Used"
        - cell "Live"
        - cell "09/09/2026"
        - cell "Review":
          - button "Review"
  - text: Destination workflow
  - button "○eBay UK"
  - button "✓FlipFlop.shop"
  - button "✓OnBuy"
  - button "○Amazon"
  - button "○Facebook catalog"
  - button "○Vinted"
  - text: 1 source listing × 2 destinations = 2 jobs. Manual-only destinations remain manual_action_required.
  - button "Download manual packs"
  - button "Review & submit"
  - heading "Batch results" [level=2]
  - text: FlipFlop.shopPublished Linked to the existing storefront product.
  - link "View listing":
    - /url: https://www.theflipflop.shop/builds/43
  - text: OnBuyManual Action Required Seller API/feed onboarding is not configured in this app. Manual listing pack only.
  - button "Hermes":
    - img "Hermes"
- alert
```

# Test source

```ts
  78  | ];
  79  | 
  80  | async function json(route: Route, status: number, payload: unknown) {
  81  |   await route.fulfill({ status, contentType: "application/json", body: JSON.stringify(payload) });
  82  | }
  83  | 
  84  | function summary(build: Build) {
  85  |   return { id: build.id, name: build.name, total_cost: 300, component_count: build.components.length, updated_at: build.updated_at };
  86  | }
  87  | 
  88  | async function installCrossListingMocks(page: Page, ebayConnected = true) {
  89  |   await page.route("**/*", async (route) => {
  90  |     const request = route.request();
  91  |     const path = new URL(request.url()).pathname.replace(/\/+$/, "");
  92  |     const apiPath = path.replace(/^\/proxy-api/, "");
  93  |     const method = request.method().toUpperCase();
  94  |     if (!path.includes("/api") && !path.startsWith("/proxy-api")) return route.continue();
  95  |     if (method === "OPTIONS") return json(route, 200, {});
  96  |     if (["/playbooks/proposals", "/alerts", "/price-alerts"].includes(apiPath) && method === "GET") return json(route, 200, []);
  97  |     if (apiPath === "/manual-builds" && method === "GET") return json(route, 200, builds.map(summary));
  98  |     const detail = apiPath.match(/^\/manual-builds\/(\d+)$/);
  99  |     if (detail && method === "GET") {
  100 |       const build = builds.find((item) => item.id === Number(detail[1]));
  101 |       return build ? json(route, 200, build) : json(route, 404, { detail: "Not found" });
  102 |     }
  103 |     const ebayStatus = apiPath === "/ebay/oauth/status" || apiPath === "/ebay/oauth/status/";
  104 |     if (ebayStatus && method === "GET") return json(route, 200, { connected: ebayConnected });
  105 |     if (apiPath.match(/^\/manual-builds\/\d+\/post-to-ebay$/) && method === "POST") {
  106 |       const id = Number(apiPath.split("/")[2]);
  107 |       const build = builds.find((item) => item.id === id)!;
  108 |       build.ebay_listing_id = `EBAY-${id}-published`;
  109 |       build.ebay_listing_status = "active";
  110 |       return json(route, 200, { success: true, listing_id: build.ebay_listing_id, url: `https://www.ebay.co.uk/itm/${build.ebay_listing_id}` });
  111 |     }
  112 |     if (apiPath.match(/^\/manual-builds\/\d+\/list-on-storefront$/) && method === "POST") {
  113 |       const id = Number(apiPath.split("/")[2]);
  114 |       const build = builds.find((item) => item.id === id)!;
  115 |       build.storefront_product_id ??= id * 10;
  116 |       build.storefront_live = true;
  117 |       return json(route, 200, { product_id: build.storefront_product_id, build_id: id, storefront_url: `https://www.theflipflop.shop/builds/${id}` });
  118 |     }
  119 |     return json(route, 200, {});
  120 |   });
  121 | }
  122 | 
  123 | test("cross-listing loads canonical sources and supports search, status filtering, and review edits", async ({ page, context }) => {
  124 |   await authenticate(context);
  125 |   await installCrossListingMocks(page);
  126 |   await page.goto("/cross-listing");
  127 | 
  128 |   await expect(page.getByRole("heading", { name: "Cross-listing" })).toBeVisible();
  129 |   await expect(page.getByText("Atlas Gaming PC RTX 3060")).toBeVisible();
  130 |   await expect(page.getByText("eBay UK", { exact: true }).first()).toBeVisible();
  131 |   await expect(page.getByText("FlipFlop.shop", { exact: true }).first()).toBeVisible();
  132 |   await expect(page.getByText("Select all filtered (2)")).toBeVisible();
  133 | 
  134 |   await page.getByLabel("Search listings").fill("Borealis");
  135 |   await expect(page.getByText("Borealis Workstation")).toBeVisible();
  136 |   await expect(page.getByText("Atlas Gaming PC RTX 3060")).toHaveCount(0);
  137 |   await page.getByLabel("Search listings").fill("");
  138 |   await page.getByLabel("Status filter").selectOption("live");
  139 |   await expect(page.getByText("Atlas Gaming PC RTX 3060")).toBeVisible();
  140 |   await expect(page.getByText("Borealis Workstation")).toHaveCount(0);
  141 | 
  142 |   const row = page.locator("tr", { hasText: "Atlas Gaming PC RTX 3060" });
  143 |   await row.getByRole("button", { name: "Review" }).click();
  144 |   await expect(page.getByRole("dialog")).toBeVisible();
  145 |   await page.getByRole("dialog").locator("input").first().fill("Atlas Gaming PC - refreshed title");
  146 |   await page.getByRole("dialog").getByRole("button", { name: "Save review edits" }).click();
  147 |   await expect(page.getByText("Atlas Gaming PC - refreshed title")).toBeVisible();
  148 | });
  149 | 
  150 | test("publishes a selected build to eBay and reports the accepted listing", async ({ page, context }) => {
  151 |   await authenticate(context);
  152 |   await installCrossListingMocks(page);
  153 |   await page.goto("/cross-listing");
  154 |   await page.getByRole("button", { name: "Select Atlas Gaming PC RTX 3060" }).click();
  155 |   await page.getByRole("button", { name: "eBay UK" }).last().click();
  156 |   page.on("dialog", (dialog) => void dialog.accept());
  157 |   await page.getByRole("button", { name: "Review & submit" }).click();
  158 | 
  159 |   await expect(page.getByText("eBay accepted the publish request.")).toBeVisible();
  160 |   await expect(page.getByText("Published", { exact: true }).last()).toBeVisible();
  161 |   await expect(page.getByRole("link", { name: "View listing" })).toHaveAttribute("href", /EBAY-42-published/);
  162 | });
  163 | 
  164 | test("keeps manual-only destinations manual and links storefront without duplicating its product", async ({ page, context }) => {
  165 |   await authenticate(context);
  166 |   await installCrossListingMocks(page);
  167 |   await page.goto("/cross-listing");
  168 |   await page.getByRole("button", { name: "Select Borealis Workstation" }).click();
  169 |   await page.getByRole("button", { name: "FlipFlop.shop" }).last().click();
  170 |   await page.getByRole("button", { name: "OnBuy" }).last().click();
  171 |   await expect(page.getByText("1 source listing × 2 destinations = 2 jobs.")).toBeVisible();
  172 |   page.on("dialog", (dialog) => void dialog.accept());
  173 | 
  174 |   const storefrontRequest = page.waitForRequest("**/proxy-api/manual-builds/43/list-on-storefront");
  175 |   await page.getByRole("button", { name: "Review & submit" }).click();
  176 |   await storefrontRequest;
  177 |   await expect(page.getByText("Linked to the existing storefront product.")).toBeVisible();
> 178 |   await expect(page.getByText("Manual action required", { exact: true })).toBeVisible();
      |                                                                           ^ Error: expect(locator).toBeVisible() failed
  179 |   await expect(page.getByText("Seller API/feed onboarding is not configured in this app. Manual listing pack only.")).toBeVisible();
  180 | });
  181 | 
  182 | test("does not offer an eBay API publish when the seller account is disconnected", async ({ page, context }) => {
  183 |   await authenticate(context);
  184 |   await installCrossListingMocks(page, false);
  185 |   await page.goto("/cross-listing");
  186 |   await expect(page.getByText("Connect the existing eBay seller account in Settings.")).toBeVisible();
  187 |   await page.getByRole("button", { name: "Select Atlas Gaming PC RTX 3060" }).click();
  188 |   await page.getByRole("button", { name: "eBay UK" }).last().click();
  189 |   page.on("dialog", (dialog) => void dialog.accept());
  190 |   await page.getByRole("button", { name: "Review & submit" }).click();
  191 |   await expect(page.getByText("Manual action required", { exact: true })).toBeVisible();
  192 |   await expect(page.getByText("Connect the existing eBay seller account in Settings.")).toHaveCount(2);
  193 | });
  194 | 
```