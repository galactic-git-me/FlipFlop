# Instructions

- Following Playwright test failed.
- Explain why, be concise, respect Playwright best practices.
- Provide a snippet of code with the fix, if possible.

# Test info

- Name: cross-listing.spec.ts >> publishes a selected build to eBay and reports the accepted listing
- Location: tests\e2e\cross-listing.spec.ts:149:5

# Error details

```
Test timeout of 45000ms exceeded.
```

```
Error: locator.click: Test timeout of 45000ms exceeded.
Call log:
  - waiting for getByRole('button', { name: 'Select Atlas Gaming PC RTX 3060' })

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
  63  |     ebay_listing_id: "EBAY-43-draft",
  64  |     ebay_listing_url: null,
  65  |     ebay_listing_status: "draft",
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
  92  |     const apiPath = path.replace(/^\/proxy-api/, "");
  93  |     const method = request.method().toUpperCase();
  94  |     if (!path.includes("/api") && !path.startsWith("/proxy-api")) return route.continue();
  95  |     if (method === "OPTIONS") return json(route, 200, {});
  96  |     if (apiPath === "/manual-builds" && method === "GET") return json(route, 200, builds.map(summary));
  97  |     const detail = apiPath.match(/^\/manual-builds\/(\d+)$/);
  98  |     if (detail && method === "GET") {
  99  |       const build = builds.find((item) => item.id === Number(detail[1]));
  100 |       return build ? json(route, 200, build) : json(route, 404, { detail: "Not found" });
  101 |     }
  102 |     const ebayStatus = apiPath === "/ebay/oauth/status" || apiPath === "/ebay/oauth/status/";
  103 |     if (ebayStatus && method === "GET") return json(route, 200, { connected: ebayConnected });
  104 |     if (apiPath.match(/^\/manual-builds\/\d+\/post-to-ebay$/) && method === "POST") {
  105 |       const id = Number(apiPath.split("/")[2]);
  106 |       const build = builds.find((item) => item.id === id)!;
  107 |       build.ebay_listing_id = `EBAY-${id}-published`;
  108 |       build.ebay_listing_status = "active";
  109 |       return json(route, 200, { success: true, listing_id: build.ebay_listing_id, url: `https://www.ebay.co.uk/itm/${build.ebay_listing_id}` });
  110 |     }
  111 |     if (apiPath.match(/^\/manual-builds\/\d+\/list-on-storefront$/) && method === "POST") {
  112 |       const id = Number(apiPath.split("/")[2]);
  113 |       const build = builds.find((item) => item.id === id)!;
  114 |       build.storefront_product_id ??= id * 10;
  115 |       build.storefront_live = true;
  116 |       return json(route, 200, { product_id: build.storefront_product_id, build_id: id, storefront_url: `https://www.theflipflop.shop/builds/${id}` });
  117 |     }
  118 |     return json(route, 200, {});
  119 |   });
  120 | }
  121 | 
  122 | test("cross-listing loads canonical sources and supports search, status filtering, and review edits", async ({ page, context }) => {
  123 |   await authenticate(context);
  124 |   await installCrossListingMocks(page);
  125 |   await page.goto("/cross-listing");
  126 | 
  127 |   await expect(page.getByRole("heading", { name: "Cross-listing" })).toBeVisible();
  128 |   await expect(page.getByText("Atlas Gaming PC RTX 3060")).toBeVisible();
  129 |   await expect(page.getByText("eBay UK", { exact: true }).first()).toBeVisible();
  130 |   await expect(page.getByText("FlipFlop.shop", { exact: true }).first()).toBeVisible();
  131 |   await expect(page.getByText("Select all filtered (2)")).toBeVisible();
  132 | 
  133 |   await page.getByLabel("Search listings").fill("Borealis");
  134 |   await expect(page.getByText("Borealis Workstation")).toBeVisible();
  135 |   await expect(page.getByText("Atlas Gaming PC RTX 3060")).toHaveCount(0);
  136 |   await page.getByLabel("Search listings").fill("");
  137 |   await page.getByLabel("Status filter").selectOption("live");
  138 |   await expect(page.getByText("Atlas Gaming PC RTX 3060")).toBeVisible();
  139 |   await expect(page.getByText("Borealis Workstation")).toHaveCount(0);
  140 | 
  141 |   const row = page.locator("tr", { hasText: "Atlas Gaming PC RTX 3060" });
  142 |   await row.getByRole("button", { name: "Review" }).click();
  143 |   await expect(page.getByRole("dialog")).toBeVisible();
  144 |   await page.getByRole("dialog").locator("input").first().fill("Atlas Gaming PC - refreshed title");
  145 |   await page.getByRole("dialog").getByRole("button", { name: "Save review edits" }).click();
  146 |   await expect(page.getByText("Atlas Gaming PC - refreshed title")).toBeVisible();
  147 | });
  148 | 
  149 | test("publishes a selected build to eBay and reports the accepted listing", async ({ page, context }) => {
  150 |   await authenticate(context);
  151 |   await installCrossListingMocks(page);
  152 |   await page.goto("/cross-listing");
> 153 |   await page.getByRole("button", { name: "Select Atlas Gaming PC RTX 3060" }).click();
      |                                                                               ^ Error: locator.click: Test timeout of 45000ms exceeded.
  154 |   await page.getByRole("button", { name: "eBay UK" }).last().click();
  155 |   page.on("dialog", (dialog) => void dialog.accept());
  156 |   await page.getByRole("button", { name: "Review & submit" }).click();
  157 | 
  158 |   await expect(page.getByText("eBay accepted the publish request.")).toBeVisible();
  159 |   await expect(page.getByText("Published", { exact: true }).last()).toBeVisible();
  160 |   await expect(page.getByRole("link", { name: "View listing" })).toHaveAttribute("href", /EBAY-42-published/);
  161 | });
  162 | 
  163 | test("keeps manual-only destinations manual and links storefront without duplicating its product", async ({ page, context }) => {
  164 |   await authenticate(context);
  165 |   await installCrossListingMocks(page);
  166 |   await page.goto("/cross-listing");
  167 |   await page.getByRole("button", { name: "Select Borealis Workstation" }).click();
  168 |   await page.getByRole("button", { name: "FlipFlop.shop" }).last().click();
  169 |   await page.getByRole("button", { name: "OnBuy" }).last().click();
  170 |   await expect(page.getByText("1 source listing × 2 destinations = 2 jobs.")).toBeVisible();
  171 |   page.on("dialog", (dialog) => void dialog.accept());
  172 | 
  173 |   const storefrontRequest = page.waitForRequest("**/proxy-api/manual-builds/43/list-on-storefront");
  174 |   await page.getByRole("button", { name: "Review & submit" }).click();
  175 |   await storefrontRequest;
  176 |   await expect(page.getByText("Linked to the existing storefront product.")).toBeVisible();
  177 |   await expect(page.getByText("Manual action required", { exact: true })).toBeVisible();
  178 |   await expect(page.getByText("Seller API/feed onboarding is not configured in this app. Manual listing pack only.")).toBeVisible();
  179 | });
  180 | 
  181 | test("does not offer an eBay API publish when the seller account is disconnected", async ({ page, context }) => {
  182 |   await authenticate(context);
  183 |   await installCrossListingMocks(page, false);
  184 |   await page.goto("/cross-listing");
  185 |   await expect(page.getByText("Connect the existing eBay seller account in Settings.")).toBeVisible();
  186 |   await page.getByRole("button", { name: "Select Atlas Gaming PC RTX 3060" }).click();
  187 |   await page.getByRole("button", { name: "eBay UK" }).last().click();
  188 |   page.on("dialog", (dialog) => void dialog.accept());
  189 |   await page.getByRole("button", { name: "Review & submit" }).click();
  190 |   await expect(page.getByText("Manual action required", { exact: true })).toBeVisible();
  191 |   await expect(page.getByText("Connect the existing eBay seller account in Settings.")).toHaveCount(2);
  192 | });
  193 | 
```