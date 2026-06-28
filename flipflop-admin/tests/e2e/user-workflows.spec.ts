import { expect, test, type Page, type Route } from "@playwright/test";

type Source = {
  id: number;
  name: string;
  url: string;
  source_type: string;
  enabled: boolean;
  config?: Record<string, unknown>;
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

function pathFromUrl(url: string): string {
  return new URL(url).pathname.replace(/\/+$/, "");
}

async function json(route: Route, status: number, payload: unknown) {
  await route.fulfill({
    status,
    contentType: "application/json",
    body: JSON.stringify(payload),
    headers: {
      "access-control-allow-origin": "*",
      "access-control-allow-methods": "GET,POST,PATCH,PUT,DELETE,OPTIONS",
      "access-control-allow-headers": "*",
    },
  });
}

async function installWorkflowMocks(page: Page) {
  const now = new Date().toISOString();
  let nextSourceId = 4;
  let nextTermId = 10;

  const settings = {
    max_concurrent_flips: 1,
    auto_buy_autonomous: false,
    auto_buy_daily_limit: 3,
    ollama_base_url: "http://localhost:11434",
    ollama_model: "gemma3:4b",
    openrouter_api_key: "",
    openrouter_primary_model: "google/gemma-4-31b-it:free",
    image_gen_enabled: true,
    image_gen_provider: "pollinations",
    default_sell_platform: "ebay",
    ebay_app_id: "",
  };

  let sources: Source[] = [
    { id: 1, name: "eBay", url: "https://www.ebay.co.uk", source_type: "scrape", enabled: true, config: {} },
    { id: 2, name: "AliExpress", url: "https://www.aliexpress.com", source_type: "scrape", enabled: true, config: {} },
    { id: 3, name: "Temu", url: "https://www.temu.com", source_type: "scrape", enabled: true, config: {} },
  ];

  let terms: SearchTerm[] = [
    {
      id: 1,
      scope: "cases",
      group_name: "Airflow Cases",
      term: "micro atx case",
      source_names: ["eBay"],
      attributes: {},
      enabled: true,
      created_at: now,
    },
    {
      id: 2,
      scope: "accessories",
      group_name: "Peripherals",
      term: "gaming keyboard",
      source_names: ["eBay", "AliExpress"],
      attributes: {},
      enabled: true,
      created_at: now,
    },
  ];

  let flips = [
    {
      id: 101,
      listing_id: 501,
      stage: "ready_to_list",
      total_cost: 220,
      current_estimated_profit: 95,
      current_estimated_resale: 360,
      listing: { title: "Ryzen 5 5600 + RTX 3060 Build" },
    },
  ];

  await page.route("**/*", async (route) => {
    const req = route.request();
    const method = req.method().toUpperCase();
    const path = pathFromUrl(req.url());

    if (method === "OPTIONS") return json(route, 200, {});
    if (!path.includes("/api")) return route.continue();

    if (path === "/api/settings" && method === "GET") return json(route, 200, settings);
    if (path === "/api/settings" && method === "PUT") {
      Object.assign(settings, JSON.parse(req.postData() || "{}"));
      return json(route, 200, settings);
    }

    if (path === "/api/sources" && method === "GET") return json(route, 200, sources);
    if (path === "/api/sources" && method === "POST") {
      const body = JSON.parse(req.postData() || "{}");
      const added: Source = {
        id: nextSourceId++,
        name: String(body.name || "New Source"),
        url: String(body.url || ""),
        source_type: String(body.source_type || "scrape"),
        enabled: body.enabled !== false,
        config: (body.config as Record<string, unknown>) || {},
      };
      sources = [...sources, added];
      return json(route, 200, added);
    }
    if (path.match(/^\/api\/sources\/\d+$/) && method === "PATCH") {
      const id = Number(path.split("/").pop());
      const body = JSON.parse(req.postData() || "{}");
      sources = sources.map((s) => (s.id === id ? { ...s, ...body } : s));
      const updated = sources.find((s) => s.id === id);
      return json(route, 200, updated ?? {});
    }
    if (path.match(/^\/api\/sources\/\d+$/) && method === "DELETE") {
      const id = Number(path.split("/").pop());
      sources = sources.filter((s) => s.id !== id);
      return route.fulfill({ status: 204 });
    }

    if (path.startsWith("/api/source-search-terms") && method === "GET") {
      const u = new URL(req.url());
      const scope = u.searchParams.get("scope");
      const items = scope ? terms.filter((t) => t.scope === scope) : terms;
      const groups = Array.from(new Set(items.map((t) => t.group_name))).sort();
      return json(route, 200, { items, groups, scopes: ["cases", "flip_opportunities", "accessories", "upgrade_parts"] });
    }
    if (path === "/api/source-search-terms" && method === "POST") {
      const body = JSON.parse(req.postData() || "{}");
      const term: SearchTerm = {
        id: nextTermId++,
        scope: String(body.scope || "cases"),
        group_name: String(body.group_name || "Custom"),
        term: String(body.term || ""),
        source_names: (body.source_names as string[]) || [],
        attributes: (body.attributes as Record<string, unknown>) || {},
        enabled: body.enabled !== false,
        created_at: now,
      };
      terms = [...terms, term];
      return json(route, 200, term);
    }
    if (path.match(/^\/api\/source-search-terms\/\d+$/) && method === "PATCH") {
      const id = Number(path.split("/").pop());
      const body = JSON.parse(req.postData() || "{}");
      terms = terms.map((t) => (t.id === id ? { ...t, ...body } : t));
      return json(route, 200, terms.find((t) => t.id === id) ?? {});
    }
    if (path.match(/^\/api\/source-search-terms\/\d+$/) && method === "DELETE") {
      const id = Number(path.split("/").pop());
      terms = terms.filter((t) => t.id !== id);
      return route.fulfill({ status: 204 });
    }

    if (path === "/api/flips" && method === "GET") return json(route, 200, flips);
    if (path.match(/^\/api\/flips\/\d+\/generate-listing$/) && method === "POST") {
      return json(route, 200, {
        titles: ["Gaming PC RTX 3060 Ryzen 5 5600 16GB DDR4", "RTX 3060 Gaming Tower Ready To Play"],
        description: "Fresh thermal paste, tested under load, clean cable management.",
      });
    }
    if (path.match(/^\/api\/flips\/\d+\/generate-images$/) && method === "POST") {
      return json(route, 200, {
        images: [
          "https://example.com/img-1.jpg",
          "https://example.com/img-2.jpg",
          "https://example.com/img-3.jpg",
        ],
      });
    }
    if (path.match(/^\/api\/flips\/\d+\/sold$/) && method === "POST") {
      const id = Number(path.split("/")[3]);
      flips = flips.filter((f) => f.id !== id);
      return json(route, 200, { ok: true });
    }

    if (path === "/api/playbooks" && method === "GET") return json(route, 200, []);
    if (path === "/api/playbooks/proposals" && method === "GET") return json(route, 200, []);
    if (path === "/api/alerts" && method === "GET") return json(route, 200, []);
    if (path === "/api/sources/health" && method === "GET") return json(route, 200, { avg_health_score: 100, items: [] });
    if (path === "/api/listings" && method === "GET") return json(route, 200, []);
    if (path === "/api/listings/stats" && method === "GET") return json(route, 200, { total_listings: 0, gems_count: 0, avg_profit: 0 });
    if (path === "/api/swarms" && method === "GET") return json(route, 200, []);
    if (path === "/api/swarms/scan/status" && method === "GET") return json(route, 200, { running: false, total: 0, completed: 0, current_sites: [], sites: [], started_at: null, finished_at: null, total_found: 0, total_gems: 0 });
    if (path === "/api/parts" && method === "GET") return json(route, 200, []);
    if (path === "/api/parts/cases" && method === "GET") return json(route, 200, []);
    if (path === "/api/demand/summary" && method === "GET") return json(route, 200, { total_listings: 0, total_gems: 0, gem_rate_pct: 0 });
    if (path === "/api/demand/auction-intel" && method === "GET") return json(route, 200, []);
    if (path === "/api/intel/retrain-status" && method === "GET") return json(route, 200, { retrain_ready: false, sold_flips_since: 0, checkpoint: "none", last_flip_id: 0, updated_at: now });
    if (path === "/api/schedule" && method === "GET") return json(route, 200, []);
    if (path.startsWith("/api/schedule/") && method === "GET") return json(route, 200, []);
    if (path === "/api/search-telemetry/recent" && method === "GET") return json(route, 200, { items: [] });
    if (path === "/api/search-telemetry/by-source" && method === "GET") return json(route, 200, { summary: {}, items: {} });
    if (path === "/api/facebook/status" && method === "GET") return json(route, 200, { exists: true, valid: true, expired: false, expiry_warning: false, message: "ok" });

    return json(route, 200, {});
  });
}

test.beforeEach(async ({ page }) => {
  await installWorkflowMocks(page);
});

test("settings general can be edited and saved", async ({ page }) => {
  await page.goto("/settings");
  await expect(page.getByRole("heading", { name: "Settings" })).toBeVisible();

  await page.locator('label:has-text("Default Sell Platform")').locator("xpath=following-sibling::input[1]").fill("facebook");
  await page.getByRole("button", { name: "Save General" }).click();

  await expect(page.getByRole("button", { name: "Saved ✓" })).toBeVisible();
});

test("settings sources and terms workflows work end-to-end", async ({ page }) => {
  await page.goto("/settings");

  await page.getByRole("button", { name: "Data Sources" }).click();
  await page.getByPlaceholder("Source name").fill("BargainHardware");
  await page.getByPlaceholder("Source URL").fill("https://www.bargainhardware.co.uk");
  await page.getByRole("button", { name: "Add Source" }).click();
  await expect(page.getByText("BargainHardware", { exact: true })).toBeVisible();

  const sourceRow = page.locator("div.p-3.rounded-xl", { hasText: "BargainHardware" }).first();
  await sourceRow.getByRole("button").first().click();

  await page.getByRole("button", { name: "Search Terms" }).click();
  await page.getByPlaceholder("New search term").fill("am4 motherboard bundle");
  await page
    .locator("div", { hasText: "Assign new term to data sources" })
    .getByRole("button", { name: "eBay" })
    .first()
    .click();
  await page.getByRole("button", { name: "Add Term" }).click();
  await expect(page.getByText("am4 motherboard bundle")).toBeVisible();

  const termCard = page.locator("div.p-3.rounded-xl", { hasText: "am4 motherboard bundle" }).first();
  await termCard.getByRole("button").first().click();
});

test("selling flow generates content/images and marks sold", async ({ page }) => {
  await page.goto("/selling");
  await expect(page.getByRole("heading", { name: "Sold_Builds" })).toBeVisible();

  await page.getByRole("button", { name: "Generate with Hermes" }).click();
  await expect(page.getByText("Gaming PC RTX 3060 Ryzen 5 5600 16GB DDR4")).toBeVisible();
  await expect(page.getByText("Fresh thermal paste, tested under load, clean cable management.")).toBeVisible();

  await page.getByRole("button", { name: "Generate Images" }).click();
  await expect(page.getByAltText("Product shot 1")).toBeVisible();

  await page.getByRole("button", { name: "Mark as Sold" }).click();
  await page.getByPlaceholder("e.g. 220").fill("400");
  await page.getByRole("button", { name: "Confirm Sale" }).click();

  await expect(page.getByText("No active flips ready to list")).toBeVisible();
});
