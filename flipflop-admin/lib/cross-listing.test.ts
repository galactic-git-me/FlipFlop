import { describe, expect, it } from "vitest";
import { capabilities, canonicalFromBuild, manualChannelOutcome, sourcesFromBuild } from "@/lib/cross-listing";
import type { ManualBuild } from "@/lib/api";

const build = {
  id: 42,
  name: "Test Gaming PC",
  status: "listed",
  components: [{ slot: "gpu", name: "RTX test", price_paid: 100, source: "manual" }],
  photos: [{ url: "https://cdn.example.test/pc.jpg", kind: "photo" }],
  generated_title: "Test Gaming PC",
  generated_description: "A tested build.",
  generated_aspects: { Features: ["Tested"] },
  ebay_listing_id: "123",
  ebay_listing_url: "https://www.ebay.co.uk/itm/123",
  ebay_listing_status: "active",
  ebay_price: 499,
  ebay_condition: "Used",
  storefront_product_id: 7,
  updated_at: "2026-09-10T10:00:00Z",
} as unknown as ManualBuild;

describe("cross-listing normalisation", () => {
  it("preserves one canonical product while representing each live channel identity", () => {
    const sources = sourcesFromBuild(build);
    expect(sources).toHaveLength(2);
    expect(new Set(sources.map((source) => source.canonicalProductId))).toEqual(new Set(["42"]));
    expect(sources.map((source) => source.externalId)).toEqual(["123", "7"]);
    expect(canonicalFromBuild(build).images[0]?.url).toBe("https://cdn.example.test/pc.jpg");
  });

  it("keeps Codex-operated manual channels selectable alongside API channels", () => {
    const matrix = capabilities(true);
    expect(matrix.find((item) => item.channel === "ebay_uk")?.mode).toBe("api");
    expect(matrix.find((item) => item.channel === "flipflop_shop")?.canPublish).toBe(true);
    expect(matrix.find((item) => item.channel === "onbuy")?.canPublish).toBe(true);
    expect(matrix.find((item) => item.channel === "onbuy")?.mode).toBe("manual");
    expect(matrix.find((item) => item.channel === "amazon")?.canPublish).toBe(false);
    expect(matrix.find((item) => item.channel === "facebook_catalog")?.canPublish).toBe(true);
    expect(matrix.find((item) => item.channel === "vinted")?.canPublish).toBe(true);
    expect(matrix.find((item) => item.channel === "google_shopping")?.canPublish).toBe(false);
    expect(matrix.filter((item) => item.mode === "manual").map((item) => item.channel)).toEqual([
      "onbuy",
      "facebook_catalog",
      "vinted",
    ]);
    expect(matrix.filter((item) => item.mode === "manual").every((item) => item.note.includes("Codex Chrome"))).toBe(true);
  });

  it("keeps unsupported channels as previews in development and launches a Codex listing handoff in production", () => {
    const preview = manualChannelOutcome(true, "OnBuy", "Synthetic note", "/dev-listings/onbuy/42");
    expect(preview).toEqual({
      status: "preview",
      message: "OnBuy development preview prepared. No external marketplace was contacted.",
      url: "/dev-listings/onbuy/42",
    });
    const production = manualChannelOutcome(false, "OnBuy", "No seller API is connected.");
    expect(production.status).toBe("manual_action_required");
    expect(production.message).toContain("Codex handoff");
    expect(production.message).toContain("Chrome");
    expect(() => manualChannelOutcome(true, "OnBuy", "note")).toThrow("A development preview URL is required.");
  });

  it("exposes a submitted canonical build before any channel listing exists", () => {
    const canonicalOnly = { ...build, status: "built", ebay_listing_id: null, ebay_listing_status: "never_listed", storefront_product_id: null } as unknown as ManualBuild;
    const sources = sourcesFromBuild(canonicalOnly);
    expect(sources).toHaveLength(1);
    expect(sources[0]?.source).toBe("flipflop_shop");
    expect(sources[0]?.externalId).toBe("not-created");
    expect(sources[0]?.status).toBe("unavailable");
  });

  it("shows a newly-created build as a draft before it is marked built", () => {
    const inProgress = { ...build, status: "in_progress", ebay_listing_id: null, ebay_listing_status: "never_listed", storefront_product_id: null } as unknown as ManualBuild;
    const sources = sourcesFromBuild(inProgress);
    expect(sources).toHaveLength(1);
    expect(sources[0]?.source).toBe("flipflop_shop");
    expect(sources[0]?.status).toBe("draft");
  });

  it("prefers the saved listing price over the canonical evaluation price", () => {
    const priced = { ...build, ebay_price: 2878.65, last_evaluation: { mid: 1450 } } as unknown as ManualBuild;
    expect(canonicalFromBuild(priced).price).toBe(2878.65);
  });
});
