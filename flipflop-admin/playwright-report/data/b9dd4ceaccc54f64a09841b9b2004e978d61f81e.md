# Instructions

- Following Playwright test failed.
- Explain why, be concise, respect Playwright best practices.
- Provide a snippet of code with the fix, if possible.

# Test info

- Name: cross-listing.spec.ts >> does not offer an eBay API publish when the seller account is disconnected
- Location: tests\e2e\cross-listing.spec.ts:182:5

# Error details

```
Error: locator.click: Error: strict mode violation: getByRole('button', { name: 'Select Atlas Gaming PC RTX 3060' }) resolved to 2 elements:
    1) <button aria-label="Select Atlas Gaming PC RTX 3060" class="flex h-4 w-4 cursor-pointer items-center justify-center rounded border border-slate-600"></button> aka getByRole('row', { name: 'Select Atlas Gaming PC RTX 3060 Atlas Gaming PC RTX 3060 Build 42 · EBAY-42' }).getByLabel('Select Atlas Gaming PC RTX')
    2) <button aria-label="Select Atlas Gaming PC RTX 3060" class="flex h-4 w-4 cursor-pointer items-center justify-center rounded border border-slate-600"></button> aka getByRole('row', { name: 'Select Atlas Gaming PC RTX 3060 Atlas Gaming PC RTX 3060 Build 42 · 420' }).getByLabel('Select Atlas Gaming PC RTX')

Call log:
  - waiting for getByRole('button', { name: 'Select Atlas Gaming PC RTX 3060' })

```

# Page snapshot

```yaml
- generic [active] [ref=e1]:
  - complementary [ref=e2]:
    - generic [ref=e3]:
      - img "FlipFlop" [ref=e5]
      - navigation [ref=e6]:
        - link "Sourcing" [ref=e7] [cursor=pointer]:
          - /url: /sourcing
          - img [ref=e8]
          - generic [ref=e11]: Sourcing
        - link "Pre-Built" [ref=e12] [cursor=pointer]:
          - /url: /builds
          - img [ref=e13]
          - generic [ref=e17]: Pre-Built
        - link "Custom Builds" [ref=e18] [cursor=pointer]:
          - /url: /configurator-config
          - img [ref=e19]
          - generic [ref=e22]: Custom Builds
        - link "Curated Builds" [ref=e23] [cursor=pointer]:
          - /url: /pc-builder
          - img [ref=e24]
          - generic [ref=e26]: Curated Builds
        - link "Inventory" [ref=e27] [cursor=pointer]:
          - /url: /inventory
          - img [ref=e28]
          - generic [ref=e31]: Inventory
        - link "Demand" [ref=e32] [cursor=pointer]:
          - /url: /demand
          - img [ref=e33]
          - generic [ref=e35]: Demand
        - link "Cross-listing" [ref=e36] [cursor=pointer]:
          - /url: /cross-listing
          - img [ref=e37]
          - generic [ref=e42]: Cross-listing
        - link "3D Assets" [ref=e43] [cursor=pointer]:
          - /url: /cases-3d-priority
          - img [ref=e44]
          - generic [ref=e47]: 3D Assets
        - link "Problems" [ref=e48] [cursor=pointer]:
          - /url: /problems
          - img [ref=e49]
          - generic [ref=e51]: Problems
  - generic [ref=e52]:
    - banner [ref=e53]:
      - generic [ref=e54]:
        - img [ref=e55]
        - textbox "QUERY MARKET DATA..." [ref=e58]
      - generic [ref=e59]:
        - img "FlipFlop" [ref=e62]
        - generic [ref=e63]:
          - button "Source activity" [ref=e64]:
            - img [ref=e65]
          - button "Favourites" [ref=e71]:
            - img [ref=e72]
          - button "Notifications" [ref=e74]:
            - img [ref=e75]
          - button "Price alerts" [ref=e78] [cursor=pointer]:
            - img [ref=e79]
          - button "Settings" [ref=e84] [cursor=pointer]:
            - img [ref=e85]
    - main [ref=e88]:
      - generic [ref=e89]:
        - generic [ref=e90]:
          - generic [ref=e91]:
            - generic [ref=e92]:
              - img [ref=e93]
              - text: Inventory synchronisation
            - heading "Cross-listing" [level=1] [ref=e96]
            - paragraph [ref=e97]: Review canonical build data, prepare channel payloads, and keep unique computers from selling twice.
          - button "Refresh listings" [ref=e98] [cursor=pointer]:
            - img [ref=e99]
            - text: Refresh listings
        - generic [ref=e104]:
          - generic [ref=e105]:
            - generic [ref=e106]:
              - generic [ref=e107]: eBay UK
              - generic [ref=e108]: Not Connected
            - paragraph [ref=e109]: Connect the existing eBay seller account in Settings.
          - generic [ref=e110]:
            - generic [ref=e111]:
              - generic [ref=e112]: FlipFlop.shop
              - generic [ref=e113]: API
            - paragraph [ref=e114]: Reuses the canonical storefront product; duplicate products are not created here.
          - generic [ref=e115]:
            - generic [ref=e116]:
              - generic [ref=e117]: OnBuy
              - generic [ref=e118]: Manual
            - paragraph [ref=e119]: Seller API/feed onboarding is not configured in this app. Manual listing pack only.
          - generic [ref=e120]:
            - generic [ref=e121]:
              - generic [ref=e122]: Amazon
              - generic [ref=e123]: Requires Approval
            - paragraph [ref=e124]: SP-API requires seller authorization, Product Listing role, marketplace/category requirements and identifiers.
          - generic [ref=e125]:
            - generic [ref=e126]:
              - generic [ref=e127]: Facebook catalog
              - generic [ref=e128]: Manual
            - paragraph [ref=e129]: Catalog/feed route must be configured; personal Marketplace automation is not supported.
          - generic [ref=e130]:
            - generic [ref=e131]:
              - generic [ref=e132]: Vinted
              - generic [ref=e133]: Manual
            - paragraph [ref=e134]: No approved seller integration is configured. Manual-assist export only; no consumer-account automation.
        - generic [ref=e135]:
          - generic [ref=e136]:
            - generic [ref=e137]:
              - img [ref=e138]
              - textbox "Search listings" [ref=e141]:
                - /placeholder: Search title, build ID or external ID…
            - generic [ref=e142]:
              - combobox "Source filter" [ref=e143]:
                - option "All sources" [selected]
                - option "eBay UK"
                - option "FlipFlop.shop"
              - combobox "Status filter" [ref=e144]:
                - option "All statuses" [selected]
                - option "Live"
                - option "Draft"
                - option "Sold"
                - option "Ended"
                - option "Unavailable"
                - option "Failed"
              - combobox "Sort listings" [ref=e145]:
                - option "Recently updated" [selected]
                - option "Highest price"
                - option "Title"
          - generic [ref=e146]:
            - button "Select all filtered (3)" [ref=e147] [cursor=pointer]: Select all filtered (3)
            - generic [ref=e149]: 0 selected · refreshed 21:53
          - table [ref=e151]:
            - rowgroup [ref=e152]:
              - row "Listing Source Price / stock Status Updated" [ref=e153]:
                - columnheader [ref=e154]
                - columnheader "Listing" [ref=e155]
                - columnheader "Source" [ref=e156]
                - columnheader "Price / stock" [ref=e157]
                - columnheader "Status" [ref=e158]
                - columnheader "Updated" [ref=e159]
                - columnheader [ref=e160]
            - rowgroup [ref=e161]:
              - row "Select Atlas Gaming PC RTX 3060 Atlas Gaming PC RTX 3060 Build 42 · EBAY-42 eBay UK £499.00 Qty 1 · Used Live 10/09/2026 Review" [ref=e162]:
                - cell "Select Atlas Gaming PC RTX 3060" [ref=e163]:
                  - button "Select Atlas Gaming PC RTX 3060" [ref=e164] [cursor=pointer]
                - cell "Atlas Gaming PC RTX 3060 Build 42 · EBAY-42" [ref=e165]:
                  - generic [ref=e168]:
                    - generic [ref=e169]: Atlas Gaming PC RTX 3060
                    - generic [ref=e170]: Build 42 · EBAY-42
                - cell "eBay UK" [ref=e171]
                - cell "£499.00 Qty 1 · Used" [ref=e172]:
                  - text: £499.00
                  - generic [ref=e173]: Qty 1 · Used
                - cell "Live" [ref=e174]
                - cell "10/09/2026" [ref=e175]
                - cell "Review" [ref=e176]:
                  - button "Review" [ref=e177] [cursor=pointer]
              - row "Select Atlas Gaming PC RTX 3060 Atlas Gaming PC RTX 3060 Build 42 · 420 FlipFlop.shop £499.00 Qty 1 · Used Live 10/09/2026 Review" [ref=e178]:
                - cell "Select Atlas Gaming PC RTX 3060" [ref=e179]:
                  - button "Select Atlas Gaming PC RTX 3060" [ref=e180] [cursor=pointer]
                - cell "Atlas Gaming PC RTX 3060 Build 42 · 420" [ref=e181]:
                  - generic [ref=e184]:
                    - generic [ref=e185]: Atlas Gaming PC RTX 3060
                    - generic [ref=e186]: Build 42 · 420
                - cell "FlipFlop.shop" [ref=e187]
                - cell "£499.00 Qty 1 · Used" [ref=e188]:
                  - text: £499.00
                  - generic [ref=e189]: Qty 1 · Used
                - cell "Live" [ref=e190]
                - cell "10/09/2026" [ref=e191]
                - cell "Review" [ref=e192]:
                  - button "Review" [ref=e193] [cursor=pointer]
              - row "Select Borealis Workstation Borealis Workstation Build 43 · EBAY-43-draft eBay UK £699.00 Qty 1 · Used Draft 09/09/2026 Review" [ref=e194]:
                - cell "Select Borealis Workstation" [ref=e195]:
                  - button "Select Borealis Workstation" [ref=e196] [cursor=pointer]
                - cell "Borealis Workstation Build 43 · EBAY-43-draft" [ref=e197]:
                  - generic [ref=e198]:
                    - img [ref=e200]
                    - generic [ref=e205]:
                      - generic [ref=e206]: Borealis Workstation
                      - generic [ref=e207]: Build 43 · EBAY-43-draft
                - cell "eBay UK" [ref=e208]
                - cell "£699.00 Qty 1 · Used" [ref=e209]:
                  - text: £699.00
                  - generic [ref=e210]: Qty 1 · Used
                - cell "Draft" [ref=e211]
                - cell "09/09/2026" [ref=e212]
                - cell "Review" [ref=e213]:
                  - button "Review" [ref=e214] [cursor=pointer]
        - generic [ref=e216]:
          - generic [ref=e217]:
            - generic [ref=e218]:
              - img [ref=e219]
              - text: Destination workflow
            - generic [ref=e222]:
              - button "○eBay UK" [ref=e223] [cursor=pointer]
              - button "○FlipFlop.shop" [ref=e224] [cursor=pointer]
              - button "○OnBuy" [ref=e225] [cursor=pointer]
              - button "○Amazon" [ref=e226] [cursor=pointer]
              - button "○Facebook catalog" [ref=e227] [cursor=pointer]
              - button "○Vinted" [ref=e228] [cursor=pointer]
            - generic [ref=e229]: 0 source listings × 0 destinations = 0 jobs. Manual-only destinations remain manual_action_required.
          - generic [ref=e230]:
            - button "Download manual packs" [disabled] [ref=e231]:
              - img [ref=e232]
              - text: Download manual packs
            - button "Review & submit" [disabled] [ref=e237]:
              - img [ref=e238]
              - text: Review & submit
      - button "Hermes" [ref=e241]:
        - img "Hermes" [ref=e242]
  - alert [ref=e243]
```

# Test source

```ts
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
  178 |   await expect(page.getByText("Manual action required", { exact: true })).toBeVisible();
  179 |   await expect(page.getByText("Seller API/feed onboarding is not configured in this app. Manual listing pack only.")).toBeVisible();
  180 | });
  181 | 
  182 | test("does not offer an eBay API publish when the seller account is disconnected", async ({ page, context }) => {
  183 |   await authenticate(context);
  184 |   await installCrossListingMocks(page, false);
  185 |   await page.goto("/cross-listing");
  186 |   await expect(page.getByText("Connect the existing eBay seller account in Settings.")).toBeVisible();
> 187 |   await page.getByRole("button", { name: "Select Atlas Gaming PC RTX 3060" }).click();
      |                                                                               ^ Error: locator.click: Error: strict mode violation: getByRole('button', { name: 'Select Atlas Gaming PC RTX 3060' }) resolved to 2 elements:
  188 |   await page.getByRole("button", { name: "eBay UK" }).last().click();
  189 |   page.on("dialog", (dialog) => void dialog.accept());
  190 |   await page.getByRole("button", { name: "Review & submit" }).click();
  191 |   await expect(page.getByText("Manual action required", { exact: true })).toBeVisible();
  192 |   await expect(page.getByText("Connect the existing eBay seller account in Settings.")).toHaveCount(2);
  193 | });
  194 | 
```