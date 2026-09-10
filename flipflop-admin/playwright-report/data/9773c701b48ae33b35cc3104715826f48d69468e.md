# Instructions

- Following Playwright test failed.
- Explain why, be concise, respect Playwright best practices.
- Provide a snippet of code with the fix, if possible.

# Test info

- Name: cross-listing.spec.ts >> cross-listing loads canonical sources and supports search, status filtering, and review edits
- Location: tests\e2e\cross-listing.spec.ts:121:5

# Error details

```
Error: expect(locator).toBeVisible() failed

Locator: getByText('Atlas Gaming PC RTX 3060')
Expected: visible
Timeout: 10000ms
Error: element(s) not found

Call log:
  - Expect "toBeVisible" with timeout 10000ms
  - waiting for getByText('Atlas Gaming PC RTX 3060')

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
  - button "Notifications": 9+
  - button "Price alerts (2 active)": "2"
  - button "Settings"
- main:
  - text: Inventory synchronisation
  - heading "Cross-listing" [level=1]
  - paragraph: Review canonical build data, prepare channel payloads, and keep unique computers from selling twice.
  - button "Refresh listings"
  - text: eBay UK Not Connected
  - paragraph: Connect the existing eBay seller account in Settings.
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
  - text: Failed to fetch
  - button "Retry"
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
  - button "Select all filtered (0)"
  - text: 0 selected · not refreshed
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
    - rowgroup
  - paragraph: No source listings match this view.
  - paragraph: Only listings returned by the connected eBay/storefront integrations are shown.
  - text: Destination workflow
  - button "○eBay UK"
  - button "○FlipFlop.shop"
  - button "○OnBuy"
  - button "○Amazon"
  - button "○Facebook catalog"
  - button "○Vinted"
  - text: 0 source listings × 0 destinations = 0 jobs. Manual-only destinations remain manual_action_required.
  - button "Download manual packs" [disabled]
  - button "Review & submit" [disabled]
  - button "Hermes":
    - img "Hermes"
- alert
```

# Test source

```ts
  27  |   storefront_live: boolean | null;
  28  |   generated_title: string;
  29  |   generated_description: string;
  30  |   generated_aspects: Record<string, string[]>;
  31  |   components: Array<{ slot: string; name: string }>;
  32  |   photos: Array<{ url: string; kind: "photo" }>;
  33  |   hero_photo_url: string | null;
  34  |   last_evaluation: { mid: number } | null;
  35  | };
  36  | 
  37  | const builds: Build[] = [
  38  |   {
  39  |     id: 42,
  40  |     name: "Atlas Gaming PC",
  41  |     status: "listed",
  42  |     updated_at: "2026-09-10T10:00:00Z",
  43  |     ebay_listing_id: "EBAY-42",
  44  |     ebay_listing_url: "https://www.ebay.co.uk/itm/EBAY-42",
  45  |     ebay_listing_status: "active",
  46  |     ebay_price: 499,
  47  |     ebay_condition: "Used",
  48  |     storefront_product_id: 420,
  49  |     storefront_live: true,
  50  |     generated_title: "Atlas Gaming PC RTX 3060",
  51  |     generated_description: "A tested gaming PC with clean cable management.",
  52  |     generated_aspects: { Features: ["RTX 3060", "16GB RAM"] },
  53  |     components: [{ slot: "gpu", name: "RTX 3060" }],
  54  |     photos: [{ url: "https://cdn.example.test/atlas.jpg", kind: "photo" }],
  55  |     hero_photo_url: null,
  56  |     last_evaluation: { mid: 450 },
  57  |   },
  58  |   {
  59  |     id: 43,
  60  |     name: "Borealis Workstation",
  61  |     status: "built",
  62  |     updated_at: "2026-09-09T10:00:00Z",
  63  |     ebay_listing_id: null,
  64  |     ebay_listing_url: null,
  65  |     ebay_listing_status: "never_listed",
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
> 127 |   await expect(page.getByText("Atlas Gaming PC RTX 3060")).toBeVisible();
      |                                                            ^ Error: expect(locator).toBeVisible() failed
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
  166 |   await page.getByRole("button", { name: "Select Borealis Workstation" }).click();
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