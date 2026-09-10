import { describe, expect, it } from "vitest";
import { capabilities, canonicalFromBuild, sourcesFromBuild } from "@/lib/cross-listing";
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

  it("does not claim unsupported marketplace APIs", () => {
    const matrix = capabilities(true);
    expect(matrix.find((item) => item.channel === "ebay_uk")?.mode).toBe("api");
    expect(matrix.find((item) => item.channel === "onbuy")?.mode).toBe("manual");
    expect(matrix.find((item) => item.channel === "vinted")?.canPublish).toBe(false);
  });
});
