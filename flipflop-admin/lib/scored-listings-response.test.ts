import { describe, expect, it } from "vitest";
import { normalizeScoredListingsResponse } from "./scored-listings-response";

describe("normalizeScoredListingsResponse", () => {
  it("accepts the running legacy API array without inventing another page", () => {
    const row = { listing_id: "one" };
    expect(normalizeScoredListingsResponse([row])).toEqual({ items: [row], hasMore: false, legacy: true, total: 1 });
  });

  it("accepts the paged API response", () => {
    const row = { listing_id: "two" };
    expect(normalizeScoredListingsResponse({ items: [row], has_more: true, total: 200 })).toEqual({ items: [row], hasMore: true, legacy: false, total: 200 });
  });

  it("does not mistake an old paged response for globally filtered data", () => {
    expect(normalizeScoredListingsResponse({ items: [{ category: "ssd" }], has_more: true })).toEqual({ items: [{ category: "ssd" }], hasMore: false, legacy: true, total: 1 });
  });
});
