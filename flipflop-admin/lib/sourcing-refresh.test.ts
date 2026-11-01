import { describe, expect, it } from "vitest";
import { loadSourcingRefresh } from "./sourcing-refresh";

describe("sourcing tab refresh", () => {
  it.each(["stats", "analytics"])("does not request hidden listings on %s", async tab => {
    const urls: string[] = [];
    const result = await loadSourcingRefresh(tab, "/listings", async <T>(url: string) => {
      urls.push(url);
      return { pending: 4 } as T;
    });
    expect(urls).toEqual(["/api/gem-radar/queue-status"]);
    expect(result.failedEndpoints).toEqual([]);
  });
  it("keeps queue data and identifies a failed visible listing request", async () => {
    const result = await loadSourcingRefresh("listings", "/listings", async <T>(url: string) =>
      url === "/listings" ? null : { pending: 4 } as T);
    expect(result.queueData).toEqual({ pending: 4 });
    expect(result.failedEndpoints).toEqual(["Listings"]);
  });
  it("clears failures on the next successful refresh", async () => {
    const result = await loadSourcingRefresh("listings", "/listings", async <T>() => ({ items: [] }) as T);
    expect(result.failedEndpoints).toEqual([]);
  });
  it("still reports queue failure on Stats", async () => {
    const result = await loadSourcingRefresh("stats", "/listings", async () => null);
    expect(result.failedEndpoints).toEqual(["Processing queue"]);
  });
});
