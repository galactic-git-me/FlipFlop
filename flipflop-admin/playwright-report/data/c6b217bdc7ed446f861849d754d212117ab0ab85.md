# Instructions

- Following Playwright test failed.
- Explain why, be concise, respect Playwright best practices.
- Provide a snippet of code with the fix, if possible.

# Test info

- Name: cross-listing.spec.ts >> keeps manual-only destinations manual and links storefront without duplicating its product
- Location: tests\e2e\cross-listing.spec.ts:162:5

# Error details

```
Test timeout of 45000ms exceeded.
```

```
Error: locator.click: Test timeout of 45000ms exceeded.
Call log:
  - waiting for getByRole('button', { name: 'Select Borealis Workstation' })

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
            - generic [ref=e78]: 9+
          - button "Price alerts (2 active)" [ref=e79] [cursor=pointer]:
            - img [ref=e80]
            - generic [ref=e85]: "2"
          - button "Settings" [ref=e86] [cursor=pointer]:
            - img [ref=e87]
    - main [ref=e90]:
      - generic [ref=e91]:
        - generic [ref=e92]:
          - generic [ref=e93]:
            - generic [ref=e94]:
              - img [ref=e95]
              - text: Inventory synchronisation
            - heading "Cross-listing" [level=1] [ref=e98]
            - paragraph [ref=e99]: Review canonical build data, prepare channel payloads, and keep unique computers from selling twice.
          - button "Refresh listings" [ref=e100] [cursor=pointer]:
            - img [ref=e101]
            - text: Refresh listings
        - generic [ref=e106]:
          - generic [ref=e107]:
            - generic [ref=e108]:
              - generic [ref=e109]: eBay UK
              - generic [ref=e110]: Not Connected
            - paragraph [ref=e111]: Connect the existing eBay seller account in Settings.
          - generic [ref=e112]:
            - generic [ref=e113]:
              - generic [ref=e114]: FlipFlop.shop
              - generic [ref=e115]: API
            - paragraph [ref=e116]: Reuses the canonical storefront product; duplicate products are not created here.
          - generic [ref=e117]:
            - generic [ref=e118]:
              - generic [ref=e119]: OnBuy
              - generic [ref=e120]: Manual
            - paragraph [ref=e121]: Seller API/feed onboarding is not configured in this app. Manual listing pack only.
          - generic [ref=e122]:
            - generic [ref=e123]:
              - generic [ref=e124]: Amazon
              - generic [ref=e125]: Requires Approval
            - paragraph [ref=e126]: SP-API requires seller authorization, Product Listing role, marketplace/category requirements and identifiers.
          - generic [ref=e127]:
            - generic [ref=e128]:
              - generic [ref=e129]: Facebook catalog
              - generic [ref=e130]: Manual
            - paragraph [ref=e131]: Catalog/feed route must be configured; personal Marketplace automation is not supported.
          - generic [ref=e132]:
            - generic [ref=e133]:
              - generic [ref=e134]: Vinted
              - generic [ref=e135]: Manual
            - paragraph [ref=e136]: No approved seller integration is configured. Manual-assist export only; no consumer-account automation.
        - generic [ref=e137]:
          - generic [ref=e138]: Failed to fetch
          - button "Retry" [ref=e139] [cursor=pointer]
        - generic [ref=e140]:
          - generic [ref=e141]:
            - generic [ref=e142]:
              - img [ref=e143]
              - textbox "Search listings" [ref=e146]:
                - /placeholder: Search title, build ID or external ID…
            - generic [ref=e147]:
              - combobox "Source filter" [ref=e148]:
                - option "All sources" [selected]
                - option "eBay UK"
                - option "FlipFlop.shop"
              - combobox "Status filter" [ref=e149]:
                - option "All statuses" [selected]
                - option "Live"
                - option "Draft"
                - option "Sold"
                - option "Ended"
                - option "Unavailable"
                - option "Failed"
              - combobox "Sort listings" [ref=e150]:
                - option "Recently updated" [selected]
                - option "Highest price"
                - option "Title"
          - generic [ref=e151]:
            - button "Select all filtered (0)" [ref=e152] [cursor=pointer]: Select all filtered (0)
            - generic [ref=e154]: 0 selected · not refreshed
          - generic [ref=e155]:
            - table [ref=e156]:
              - rowgroup [ref=e157]:
                - row "Listing Source Price / stock Status Updated" [ref=e158]:
                  - columnheader [ref=e159]
                  - columnheader "Listing" [ref=e160]
                  - columnheader "Source" [ref=e161]
                  - columnheader "Price / stock" [ref=e162]
                  - columnheader "Status" [ref=e163]
                  - columnheader "Updated" [ref=e164]
                  - columnheader [ref=e165]
              - rowgroup
            - generic [ref=e166]:
              - img [ref=e167]
              - paragraph [ref=e169]: No source listings match this view.
              - paragraph [ref=e170]: Only listings returned by the connected eBay/storefront integrations are shown.
        - generic [ref=e172]:
          - generic [ref=e173]:
            - generic [ref=e174]:
              - img [ref=e175]
              - text: Destination workflow
            - generic [ref=e178]:
              - button "○eBay UK" [ref=e179] [cursor=pointer]
              - button "○FlipFlop.shop" [ref=e180] [cursor=pointer]
              - button "○OnBuy" [ref=e181] [cursor=pointer]
              - button "○Amazon" [ref=e182] [cursor=pointer]
              - button "○Facebook catalog" [ref=e183] [cursor=pointer]
              - button "○Vinted" [ref=e184] [cursor=pointer]
            - generic [ref=e185]: 0 source listings × 0 destinations = 0 jobs. Manual-only destinations remain manual_action_required.
          - generic [ref=e186]:
            - button "Download manual packs" [disabled] [ref=e187]:
              - img [ref=e188]
              - text: Download manual packs
            - button "Review & submit" [disabled] [ref=e193]:
              - img [ref=e194]
              - text: Review & submit
      - button "Hermes" [ref=e197]:
        - img "Hermes" [ref=e198]
  - alert [ref=e199]
```

# Test source

```ts
  66  |     ebay_price: 699,
  67  |     ebay_condition: "Used",
  68  |     storefront_product_id: null,
  69  |     storefront_live: null,
  70  |     generated_title: "Borealis Workstation",
  71  |     generated_description: "Quiet workstation, fully tested.",
  72  |     generated_aspects: { Features: ["32GB RAM"] },
  73  |     components: [{ slot: "cpu", name: "Ryzen 7" }],
  74  |     photos: [],
  75  |     hero_photo_url: null,
  76  |     last_evaluation: { mid: 650 },
  77  |   },
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
  92  |     const method = request.method().toUpperCase();
  93  |     if (!path.includes("/api")) return route.continue();
  94  |     if (method === "OPTIONS") return json(route, 200, {});
  95  |     if (path === "/api/manual-builds" && method === "GET") return json(route, 200, builds.map(summary));
  96  |     const detail = path.match(/^\/api\/manual-builds\/(\d+)$/);
  97  |     if (detail && method === "GET") {
  98  |       const build = builds.find((item) => item.id === Number(detail[1]));
  99  |       return build ? json(route, 200, build) : json(route, 404, { detail: "Not found" });
  100 |     }
  101 |     const ebayStatus = path === "/api/ebay/oauth/status" || path === "/api/ebay/oauth/status/";
  102 |     if (ebayStatus && method === "GET") return json(route, 200, { connected: ebayConnected });
  103 |     if (path.match(/^\/api\/manual-builds\/\d+\/post-to-ebay$/) && method === "POST") {
  104 |       const id = Number(path.split("/")[3]);
  105 |       const build = builds.find((item) => item.id === id)!;
  106 |       build.ebay_listing_id = `EBAY-${id}-published`;
  107 |       build.ebay_listing_status = "active";
  108 |       return json(route, 200, { success: true, listing_id: build.ebay_listing_id, url: `https://www.ebay.co.uk/itm/${build.ebay_listing_id}` });
  109 |     }
  110 |     if (path.match(/^\/api\/manual-builds\/\d+\/list-on-storefront$/) && method === "POST") {
  111 |       const id = Number(path.split("/")[3]);
  112 |       const build = builds.find((item) => item.id === id)!;
  113 |       build.storefront_product_id ??= id * 10;
  114 |       build.storefront_live = true;
  115 |       return json(route, 200, { product_id: build.storefront_product_id, build_id: id, storefront_url: `https://www.theflipflop.shop/builds/${id}` });
  116 |     }
  117 |     return json(route, 200, {});
  118 |   });
  119 | }
  120 | 
  121 | test("cross-listing loads canonical sources and supports search, status filtering, and review edits", async ({ page, context }) => {
  122 |   await authenticate(context);
  123 |   await installCrossListingMocks(page);
  124 |   await page.goto("/cross-listing");
  125 | 
  126 |   await expect(page.getByRole("heading", { name: "Cross-listing" })).toBeVisible();
  127 |   await expect(page.getByText("Atlas Gaming PC RTX 3060")).toBeVisible();
  128 |   await expect(page.getByText("eBay UK", { exact: true }).first()).toBeVisible();
  129 |   await expect(page.getByText("FlipFlop.shop", { exact: true }).first()).toBeVisible();
  130 |   await expect(page.getByText("Select all filtered (2)")).toBeVisible();
  131 | 
  132 |   await page.getByLabel("Search listings").fill("Borealis");
  133 |   await expect(page.getByText("Borealis Workstation")).toBeVisible();
  134 |   await expect(page.getByText("Atlas Gaming PC RTX 3060")).toHaveCount(0);
  135 |   await page.getByLabel("Search listings").fill("");
  136 |   await page.getByLabel("Status filter").selectOption("live");
  137 |   await expect(page.getByText("Atlas Gaming PC RTX 3060")).toBeVisible();
  138 |   await expect(page.getByText("Borealis Workstation")).toHaveCount(0);
  139 | 
  140 |   const row = page.locator("tr", { hasText: "Atlas Gaming PC RTX 3060" });
  141 |   await row.getByRole("button", { name: "Review" }).click();
  142 |   await expect(page.getByRole("dialog")).toBeVisible();
  143 |   await page.getByRole("dialog").locator("input").first().fill("Atlas Gaming PC - refreshed title");
  144 |   await page.getByRole("dialog").getByRole("button", { name: "Save review edits" }).click();
  145 |   await expect(page.getByText("Atlas Gaming PC - refreshed title")).toBeVisible();
  146 | });
  147 | 
  148 | test("publishes a selected build to eBay and reports the accepted listing", async ({ page, context }) => {
  149 |   await authenticate(context);
  150 |   await installCrossListingMocks(page);
  151 |   await page.goto("/cross-listing");
  152 |   await page.getByRole("button", { name: "Select Atlas Gaming PC RTX 3060" }).click();
  153 |   await page.getByRole("button", { name: "eBay UK" }).last().click();
  154 |   page.on("dialog", (dialog) => void dialog.accept());
  155 |   await page.getByRole("button", { name: "Review & submit" }).click();
  156 | 
  157 |   await expect(page.getByText("eBay accepted the publish request.")).toBeVisible();
  158 |   await expect(page.getByText("Published", { exact: true }).last()).toBeVisible();
  159 |   await expect(page.getByRole("link", { name: "View listing" })).toHaveAttribute("href", /EBAY-42-published/);
  160 | });
  161 | 
  162 | test("keeps manual-only destinations manual and links storefront without duplicating its product", async ({ page, context }) => {
  163 |   await authenticate(context);
  164 |   await installCrossListingMocks(page);
  165 |   await page.goto("/cross-listing");
> 166 |   await page.getByRole("button", { name: "Select Borealis Workstation" }).click();
      |                                                                           ^ Error: locator.click: Test timeout of 45000ms exceeded.
  167 |   await page.getByRole("button", { name: "FlipFlop.shop" }).last().click();
  168 |   await page.getByRole("button", { name: "OnBuy" }).last().click();
  169 |   await expect(page.getByText("1 source listing × 2 destinations = 2 jobs.")).toBeVisible();
  170 |   page.on("dialog", (dialog) => void dialog.accept());
  171 | 
  172 |   const storefrontRequest = page.waitForRequest("**/api/manual-builds/43/list-on-storefront");
  173 |   await page.getByRole("button", { name: "Review & submit" }).click();
  174 |   await storefrontRequest;
  175 |   await expect(page.getByText("Linked to the existing storefront product.")).toBeVisible();
  176 |   await expect(page.getByText("Manual action required", { exact: true })).toBeVisible();
  177 |   await expect(page.getByText("Seller API/feed onboarding is not configured in this app. Manual listing pack only.")).toBeVisible();
  178 | });
  179 | 
  180 | test("does not offer an eBay API publish when the seller account is disconnected", async ({ page, context }) => {
  181 |   await authenticate(context);
  182 |   await installCrossListingMocks(page, false);
  183 |   await page.goto("/cross-listing");
  184 |   await expect(page.getByText("Connect the existing eBay seller account in Settings.")).toBeVisible();
  185 |   await page.getByRole("button", { name: "Select Atlas Gaming PC RTX 3060" }).click();
  186 |   await page.getByRole("button", { name: "eBay UK" }).last().click();
  187 |   page.on("dialog", (dialog) => void dialog.accept());
  188 |   await page.getByRole("button", { name: "Review & submit" }).click();
  189 |   await expect(page.getByText("Manual action required", { exact: true })).toBeVisible();
  190 |   await expect(page.getByText("Connect the existing eBay seller account in Settings.")).toHaveCount(2);
  191 | });
  192 | 
```