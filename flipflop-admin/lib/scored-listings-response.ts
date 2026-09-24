/** Accept both the pre-pagination API and the new paged response during a backend restart. */
export function normalizeScoredListingsResponse<T>(data: unknown): { items: T[]; hasMore: boolean; legacy: boolean; total: number } {
  if (Array.isArray(data)) return { items: data as T[], hasMore: false, legacy: true, total: data.length };
  if (data && typeof data === "object" && "items" in data && Array.isArray(data.items)) {
    return { items: data.items as T[], hasMore: "has_more" in data && data.has_more === true, legacy: false, total: "total" in data && typeof data.total === "number" ? data.total : data.items.length };
  }
  throw new Error("Unexpected scored-listings response from the API");
}
