import { expect, test, type BrowserContext, type Page, type Route } from "@playwright/test";
import { SignJWT } from "jose";

const TEST_JWT_SECRET = new TextEncoder().encode("playwright-test-secret");

async function authenticate(context: BrowserContext) {
  const token = await new SignJWT({ email: "e2e@example.test" })
    .setProtectedHeader({ alg: "HS256" })
    .setSubject("1")
    .setAudience("flipflop-admin")
    .setExpirationTime("1h")
    .sign(TEST_JWT_SECRET);
  await context.addCookies([{ name: "admin_session", value: token, domain: "127.0.0.1", path: "/", httpOnly: true }]);
}

type Build = Record<string, unknown> & {
  id: number;
  name: string;
  status: "listed" | "built";
  updated_at: string;
  ebay_listing_id: string | null;
  ebay_listing_url: string | null;
  ebay_listing_status: "active" | "draft" | "never_listed";
  ebay_price: number | null;
  ebay_condition: string;
  storefront_product_id: number | null;
  storefront_live: boolean | null;
  generated_title: string;
  generated_description: string;
  generated_aspects: Record<string, string[]>;
  components: Array<{ slot: string; name: string }>;
  photos: Array<{ url: string; kind: "photo" }>;
  hero_photo_url: string | null;
  last_evaluation: { mid: number } | null;
};

const builds: Build[] = [
  {
    id: 42,
    name: "Atlas Gaming PC",
    status: "listed",
    updated_at: "2026-09-10T10:00:00Z",
    ebay_listing_id: "EBAY-42",
    ebay_listing_url: "https://www.ebay.co.uk/itm/EBAY-42",
    ebay_listing_status: "active",
    ebay_price: 499,
    ebay_condition: "Used",
    storefront_product_id: 420,
    storefront_live: true,
    generated_title: "Atlas Gaming PC RTX 3060",
    generated_description: "A tested gaming PC with clean cable management.",
    generated_aspects: { Features: ["RTX 3060", "16GB RAM"] },
    components: [{ slot: "gpu", name: "RTX 3060" }],
    photos: [{ url: "https://cdn.example.test/atlas.jpg", kind: "photo" }],
    hero_photo_url: null,
    last_evaluation: { mid: 450 },
  },
  {
    id: 43,
    name: "Borealis Workstation",
    status: "built",
    updated_at: "2026-09-09T10:00:00Z",
    ebay_listing_id: "EBAY-43-draft",
    ebay_listing_url: null,
    ebay_listing_status: "draft",
    ebay_price: 699,
    ebay_condition: "Used",
    storefront_product_id: null,
    storefront_live: null,
    generated_title: "Borealis Workstation",
    generated_description: "Quiet workstation, fully tested.",
    generated_aspects: { Features: ["32GB RAM"] },
    components: [{ slot: "cpu", name: "Ryzen 7" }],
    photos: [],
    hero_photo_url: null,
    last_evaluation: { mid: 650 },
  },
];

async function json(route: Route, status: number, payload: unknown) {
  await route.fulfill({ status, contentType: "application/json", body: JSON.stringify(payload) });
}

function summary(build: Build) {
  return { id: build.id, name: build.name, total_cost: 300, component_count: build.components.length, updated_at: build.updated_at };
}

async function installCrossListingMocks(page: Page, ebayConnected = true) {
  await page.route("**/*", async (route) => {
    const request = route.request();
    const path = new URL(request.url()).pathname.replace(/\/+$/, "");
    const apiPath = path.replace(/^\/proxy-api/, "");
    const method = request.method().toUpperCase();
    if (!path.includes("/api") && !path.startsWith("/proxy-api")) return route.continue();
    if (method === "OPTIONS") return json(route, 200, {});
    if (["/playbooks/proposals", "/alerts", "/price-alerts"].includes(apiPath) && method === "GET") return json(route, 200, []);
    if (apiPath === "/manual-builds" && method === "GET") return json(route, 200, builds.map(summary));
    const detail = apiPath.match(/^\/manual-builds\/(\d+)$/);
    if (detail && method === "GET") {
      const build = builds.find((item) => item.id === Number(detail[1]));
      return build ? json(route, 200, build) : json(route, 404, { detail: "Not found" });
    }
    const ebayStatus = apiPath === "/ebay/oauth/status" || apiPath === "/ebay/oauth/status/";
    if (ebayStatus && method === "GET") return json(route, 200, { connected: ebayConnected });
    if (apiPath.match(/^\/manual-builds\/\d+\/post-to-ebay$/) && method === "POST") {
      const id = Number(apiPath.split("/")[2]);
      const build = builds.find((item) => item.id === id)!;
      build.ebay_listing_id = `EBAY-${id}-published`;
      build.ebay_listing_status = "active";
      return json(route, 200, { success: true, listing_id: build.ebay_listing_id, url: `https://www.ebay.co.uk/itm/${build.ebay_listing_id}` });
    }
    if (apiPath.match(/^\/manual-builds\/\d+\/list-on-storefront$/) && method === "POST") {
      const id = Number(apiPath.split("/")[2]);
      const build = builds.find((item) => item.id === id)!;
      build.storefront_product_id ??= id * 10;
      build.storefront_live = true;
      return json(route, 200, { product_id: build.storefront_product_id, build_id: id, storefront_url: `https://www.theflipflop.shop/builds/${id}` });
    }
    return json(route, 200, {});
  });
}

test("cross-listing loads canonical sources and supports search, status filtering, and review edits", async ({ page, context }) => {
  await authenticate(context);
  await installCrossListingMocks(page);
  await page.goto("/cross-listing");

  await expect(page.getByRole("heading", { name: "Cross-listing" })).toBeVisible();
  await expect(page.getByText("Atlas Gaming PC RTX 3060")).toBeVisible();
  await expect(page.getByText("eBay UK", { exact: true }).first()).toBeVisible();
  await expect(page.getByText("FlipFlop.shop", { exact: true }).first()).toBeVisible();
  await expect(page.getByText("Select all filtered (2)")).toBeVisible();

  await page.getByLabel("Search listings").fill("Borealis");
  await expect(page.getByText("Borealis Workstation")).toBeVisible();
  await expect(page.getByText("Atlas Gaming PC RTX 3060")).toHaveCount(0);
  await page.getByLabel("Search listings").fill("");
  await page.getByLabel("Status filter").selectOption("live");
  await expect(page.getByText("Atlas Gaming PC RTX 3060")).toBeVisible();
  await expect(page.getByText("Borealis Workstation")).toHaveCount(0);

  const row = page.locator("tr", { hasText: "Atlas Gaming PC RTX 3060" });
  await row.getByRole("button", { name: "Review" }).click();
  await expect(page.getByRole("dialog")).toBeVisible();
  await page.getByRole("dialog").locator("input").first().fill("Atlas Gaming PC - refreshed title");
  await page.getByRole("dialog").getByRole("button", { name: "Save review edits" }).click();
  await expect(page.getByText("Atlas Gaming PC - refreshed title")).toBeVisible();
});

test("publishes a selected build to eBay and reports the accepted listing", async ({ page, context }) => {
  await authenticate(context);
  await installCrossListingMocks(page);
  await page.goto("/cross-listing");
  await page.getByRole("button", { name: "Select Atlas Gaming PC RTX 3060" }).click();
  await page.getByRole("button", { name: "eBay UK" }).last().click();
  page.on("dialog", (dialog) => void dialog.accept());
  await page.getByRole("button", { name: "Review & submit" }).click();

  await expect(page.getByText("eBay accepted the publish request.")).toBeVisible();
  await expect(page.getByText("Published", { exact: true }).last()).toBeVisible();
  await expect(page.getByRole("link", { name: "View listing" })).toHaveAttribute("href", /EBAY-42-published/);
});

test("keeps manual-only destinations manual and links storefront without duplicating its product", async ({ page, context }) => {
  await authenticate(context);
  await installCrossListingMocks(page);
  await page.goto("/cross-listing");
  await page.getByRole("button", { name: "Select Borealis Workstation" }).click();
  await page.getByRole("button", { name: "FlipFlop.shop" }).last().click();
  await page.getByRole("button", { name: "OnBuy" }).last().click();
  await expect(page.getByText("1 source listing × 2 destinations = 2 jobs.")).toBeVisible();
  page.on("dialog", (dialog) => void dialog.accept());

  const storefrontRequest = page.waitForRequest("**/proxy-api/manual-builds/43/list-on-storefront");
  await page.getByRole("button", { name: "Review & submit" }).click();
  await storefrontRequest;
  await expect(page.getByText("Linked to the existing storefront product.")).toBeVisible();
  await expect(page.getByText("Manual action required", { exact: true })).toBeVisible();
  await expect(page.getByText("Seller API/feed onboarding is not configured in this app. Manual listing pack only.")).toBeVisible();
});

test("does not offer an eBay API publish when the seller account is disconnected", async ({ page, context }) => {
  await authenticate(context);
  await installCrossListingMocks(page, false);
  await page.goto("/cross-listing");
  await expect(page.getByText("Connect the existing eBay seller account in Settings.")).toBeVisible();
  await page.getByRole("button", { name: "Select Atlas Gaming PC RTX 3060" }).click();
  await page.getByRole("button", { name: "eBay UK" }).last().click();
  page.on("dialog", (dialog) => void dialog.accept());
  await page.getByRole("button", { name: "Review & submit" }).click();
  await expect(page.getByText("Manual action required", { exact: true })).toBeVisible();
  await expect(page.getByText("Connect the existing eBay seller account in Settings.")).toHaveCount(2);
});
