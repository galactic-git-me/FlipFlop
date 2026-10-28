/** Accept both the pre-pagination API and the new paged response during a backend restart. */
export function normalizeScoredListingsResponse<T>(data: unknown): { items: T[]; hasMore: boolean; legacy: boolean; total: number } {
  if (Array.isArray(data)) return { items: data as T[], hasMore: false, legacy: true, total: data.length };
  if (data && typeof data === "object" && "items" in data && Array.isArray(data.items)) {
    const hasGlobalTotal = "total" in data && typeof data.total === "number";
    return { items: data.items as T[], hasMore: hasGlobalTotal && "has_more" in data && data.has_more === true, legacy: !hasGlobalTotal, total: hasGlobalTotal ? data.total as number : data.items.length };
  }
  throw new Error("Unexpected scored-listings response from the API");
}
